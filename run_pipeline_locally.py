#!/usr/bin/env python3
"""
Script para ejecutar el pipeline localmente leyendo datos de Google Drive.
Descargar parquets → Procesar → Generar métricas → Guardar resultados

Uso:
    python run_pipeline_locally.py --folder-id "<FOLDER_ID_DE_DRIVE>"

    O con archivo de config:
    python run_pipeline_locally.py --config config.json
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd
import logging
from dataclasses import dataclass

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuración del pipeline local"""
    drive_folder_id: Optional[str] = None  # Folder ID de Drive donde están los parquets
    output_dir: Path = Path.home() / ".cache" / "twnel_pipeline" / "reports"
    db_path: Path = Path.home() / ".cache" / "twnel_pipeline" / "pipeline.db"
    upload_to_drive: bool = False  # Subir resultados a Drive
    drive_output_folder: Optional[str] = None  # Folder ID destino en Drive
    sample_size: Optional[int] = None  # Procesar solo N templates (para testing)

    @classmethod
    def from_json(cls, path: str) -> "PipelineConfig":
        """Cargar configuración desde JSON"""
        with open(path) as f:
            data = json.load(f)
        return cls(**data)


class DriveDataLoader:
    """Descarga parquets de Google Drive"""

    def __init__(self):
        """Inicializar autenticación con Drive"""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from googleapiclient.discovery import build
            from googleapiclient.http import MediaIoBaseDownload
            import os

            SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
            creds = None
            token_file = Path.home() / '.cache' / 'twnel_drive_token.json'

            # Cargar token existente
            if token_file.exists():
                creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

            # Si no hay token o es inválido, pedir autorización
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    # Autorización interactiva (abre navegador)
                    flow = InstalledAppFlow.from_client_secrets_file(
                        'client_secret_drive.json',
                        SCOPES
                    )
                    creds = flow.run_local_server(port=0)

                # Guardar token para futuras ejecuciones
                token_file.parent.mkdir(parents=True, exist_ok=True)
                with open(token_file, 'w') as f:
                    f.write(creds.to_json())

            self.drive = build('drive', 'v3', credentials=creds)
            self.credentials = creds
            logger.info("✅ Autenticado con Google Drive")
        except FileNotFoundError:
            logger.error("❌ No se encontró 'client_secret_drive.json'")
            logger.info("📝 Sigue estos pasos para obtenerlo:")
            logger.info("   1. Ve a https://console.cloud.google.com/apis/credentials")
            logger.info("   2. Crea un 'OAuth 2.0 Client ID' tipo 'Desktop application'")
            logger.info("   3. Descárgalo como JSON y renómbralo a 'client_secret_drive.json'")
            logger.info("   4. Coloca el archivo en: " + str(Path.cwd() / "client_secret_drive.json"))
            raise
        except Exception as e:
            logger.error(f"❌ Error autenticando con Drive: {e}")
            raise

    def download_parquets(self, folder_id: str) -> List[pd.DataFrame]:
        """
        Descargar todos los parquets de una carpeta en Drive

        Returns:
            Lista de DataFrames con los datos
        """
        try:
            from googleapiclient.http import MediaIoBaseDownload
            import io

            logger.info(f"Buscando parquets en carpeta {folder_id}...")

            # Buscar archivos .parquet
            query = f"'{folder_id}' in parents and trashed=false and mimeType='application/octet-stream' and name contains '.parquet'"
            results = self.drive.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)', pageSize=100).execute()
            file_list = results.get('files', [])

            # Si no encuentra con octet-stream, intentar con extension
            if not file_list:
                query = f"'{folder_id}' in parents and trashed=false and name contains '.parquet'"
                results = self.drive.files().list(q=query, spaces='drive', fields='files(id, name, mimeType)', pageSize=100).execute()
                file_list = results.get('files', [])

            if not file_list:
                logger.warning("⚠️  No se encontraron archivos .parquet en Drive")
                return []

            dfs = []
            for file in file_list:
                try:
                    logger.info(f"  Descargando {file['name']}...")

                    # Descargar a buffer
                    request = self.drive.files().get_media(fileId=file['id'])
                    fh = io.BytesIO()
                    downloader = MediaIoBaseDownload(fh, request)

                    done = False
                    while not done:
                        status, done = downloader.next_chunk()

                    # Leer desde buffer
                    fh.seek(0)
                    df = pd.read_parquet(fh)
                    dfs.append(df)
                    logger.info(f"  ✅ {file['name']} cargado ({len(df)} filas)")
                except Exception as e:
                    logger.warning(f"  ⚠️  Error descargando {file['name']}: {e}")
                    continue

            logger.info(f"Total: {len(dfs)} archivos descargados")
            return dfs

        except Exception as e:
            logger.error(f"Error descargando parquets: {e}")
            raise


class LocalPipelineRunner:
    """Ejecuta el pipeline localmente"""

    def __init__(self, config: PipelineConfig):
        self.config = config
        self.config.output_dir.mkdir(parents=True, exist_ok=True)
        self.config.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Importar componentes del pipeline
        from pipeline.stages.template_extractor import TemplateExtractor
        from pipeline.stages.rule_classifier import RuleClassifier
        from pipeline.storage import SQLTemplateStore, DatabaseConfig, DatabaseType, TemplateMetadata

        self.extractor = TemplateExtractor()
        self.rule_classifier = RuleClassifier()

        db_config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=str(self.config.db_path)
        )
        self.sql_store = SQLTemplateStore(config=db_config)

        logger.info(f"Pipeline configurado. BD: {self.config.db_path}")

    async def initialize(self):
        """Inicializar base de datos"""
        await self.sql_store.initialize()
        logger.info("✅ BD inicializada")

    async def process_data(self, dfs: List[pd.DataFrame]):
        """
        Procesar datos a través del pipeline

        Args:
            dfs: Lista de DataFrames cargados desde Drive
        """
        if not dfs:
            logger.error("No hay datos para procesar")
            return

        # Concatenar todos los DataFrames
        df = pd.concat(dfs, ignore_index=True)
        logger.info(f"Total de mensajes a procesar: {len(df)}")

        # Normalizar columnas esperadas
        df = self._normalize_columns(df)

        # Extraer templates únicos
        templates = self._extract_templates(df)
        logger.info(f"Templates únicos extraídos: {len(templates)}")

        # Clasificar con L0 (RuleClassifier)
        from pipeline.storage import TemplateMetadata

        classified = []
        unclassified = []

        for i, (template_id, template_data) in enumerate(templates.items()):
            if self.config.sample_size and i >= self.config.sample_size:
                logger.info(f"Límite de sample alcanzado ({self.config.sample_size})")
                break

            template_text = template_data['template_text']
            client_name = template_data.get('client_name')
            original_message = template_data['original_message']
            frequency = template_data['frequency']

            # Clasificar con L0
            rule_match = self.rule_classifier.classify(template_text, client_name)

            if rule_match:
                classified.append({
                    'template_id': template_id,
                    'template_text': template_text,
                    'label': rule_match.label,
                    'rule_name': rule_match.rule_name,
                    'confidence': rule_match.confidence,
                    'level': 'rule',
                    'original_message': original_message,
                    'frequency': frequency,
                    'client_name': client_name,
                })

                # Guardar en SQL
                from pipeline.stages.classifier.orchestrator import ClassificationResult
                result = ClassificationResult(
                    template_id=template_id,
                    template_text=template_text,
                    label=rule_match.label,
                    category=rule_match.label.split('::')[0] if '::' in rule_match.label else rule_match.label,
                    subcategory=rule_match.label.split('::')[1] if '::' in rule_match.label else '',
                    confidence=rule_match.confidence,
                    level_used='rule',
                    rule_name=rule_match.rule_name
                )

                metadata = TemplateMetadata(
                    original_message=original_message,
                    client_name=client_name,
                    frequency=frequency,
                    phone_number=template_data.get('phone_number'),
                    operator_name=template_data.get('operator_name'),
                )

                await self.sql_store.upsert(result, metadata)
            else:
                unclassified.append({
                    'template_id': template_id,
                    'template_text': template_text,
                    'original_message': original_message,
                    'frequency': frequency,
                    'client_name': client_name,
                })

            if (i + 1) % 100 == 0:
                logger.info(f"  Procesados {i + 1}/{len(templates)} templates...")

        # Generar reportes
        self._generate_reports(df, classified, unclassified)
        logger.info("✅ Pipeline completado")

    def _normalize_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Normalizar columnas esperadas"""
        # Renombrar 'text' a 'message' si existe
        if 'text' in df.columns and 'message' not in df.columns:
            df = df.rename(columns={'text': 'message'})

        # Columnas con defaults
        for col in ['frequency', 'client_name', 'phone_number', 'operator_name']:
            if col not in df.columns:
                df[col] = None

        df['frequency'] = df['frequency'].fillna(1).astype(int)
        return df

    def _extract_templates(self, df: pd.DataFrame) -> Dict:
        """
        Extraer templates únicos

        Returns:
            Dict con template_id → {template_text, original_message, frequency, ...}
        """
        templates = {}

        for _, row in df.iterrows():
            message = row['message']

            # Extraer template
            extracted = self.extractor.extract_text(message)
            template_text = extracted.template_text
            applied_rules = extracted.applied_rules

            # Usar template_text como ID (determinístico)
            template_id = hash(template_text) & 0x7FFFFFFF  # ID positivo
            template_id = f"tpl_{template_id:016d}"

            if template_id not in templates:
                templates[template_id] = {
                    'template_text': template_text,
                    'original_message': message,
                    'frequency': row['frequency'],
                    'client_name': row['client_name'],
                    'phone_number': row['phone_number'],
                    'operator_name': row['operator_name'],
                    'applied_rules': applied_rules,
                }
            else:
                templates[template_id]['frequency'] += row['frequency']

        return templates

    def _generate_reports(self, df: pd.DataFrame, classified: List[Dict], unclassified: List[Dict]):
        """Generar reportes en CSV y métricas en texto"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Métricas
        total_templates = len(classified) + len(unclassified)
        classified_count = len(classified)
        unclassified_count = len(unclassified)
        coverage = (classified_count / total_templates * 100) if total_templates > 0 else 0

        total_messages = df.shape[0]
        classified_msgs = sum(t['frequency'] for t in classified)
        msg_coverage = (classified_msgs / total_messages * 100) if total_messages > 0 else 0

        # Reporte de texto
        report_text = f"""
╔════════════════════════════════════════════════════════════════╗
║           📊 RULE CLASSIFIER - REPORTE LOCAL                   ║
╚════════════════════════════════════════════════════════════════╝

Timestamp: {datetime.now().isoformat()}
BD Local: {self.config.db_path}

📊 MÉTRICAS DE COBERTURA - RuleClassifier (L0)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎯 COBERTURA POR TEMPLATES:
   Clasificados:     {classified_count:,} / {total_templates:,} ({coverage:.1f}%)
   Sin clasificar:   {unclassified_count:,} / {total_templates:,} ({100-coverage:.1f}%)

📱 COBERTURA POR MENSAJES:
   Clasificados:     {classified_msgs:,} ({msg_coverage:.1f}%)
   Sin clasificar:   {total_messages - classified_msgs:,} ({100-msg_coverage:.1f}%)
   Total:            {total_messages:,}

💰 AHORRO ESTIMADO (vs LLM para todos):
   Sin L0: ${total_templates * 0.0001:.2f} (LLM x todos)
   Con L0: ${unclassified_count * 0.0001:.2f} (LLM x sin clasificar)
   Ahorro: ${(total_templates - unclassified_count) * 0.0001:.2f} ({coverage:.1f}%) 🎉

📂 DISTRIBUCIÓN POR CATEGORÍA (Clasificados)
────────────────────────────────────────────────────────────────
"""

        if classified:
            df_classified = pd.DataFrame(classified)
            category_counts = df_classified['label'].value_counts()
            for label, count in category_counts.items():
                msgs = sum(t['frequency'] for t in classified if t['label'] == label)
                pct = (msgs / classified_msgs * 100) if classified_msgs > 0 else 0
                report_text += f"  {label:40} {count:4} templates | {msgs:8,} msgs ({pct:5.1f}%)\n"

        report_text += f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📁 Archivos generados en: {self.config.output_dir}
"""

        print(report_text)

        # Guardar reporte
        report_path = self.config.output_dir / f"reporte_{timestamp}.txt"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report_text)
        logger.info(f"✅ Reporte: {report_path}")

        # CSVs
        if classified:
            csv_path = self.config.output_dir / f"classified_templates_{timestamp}.csv"
            pd.DataFrame(classified).to_csv(csv_path, index=False)
            logger.info(f"✅ Clasificados: {csv_path}")

        if unclassified:
            csv_path = self.config.output_dir / f"unclassified_templates_{timestamp}.csv"
            # Top 100 por frecuencia
            df_unclass = pd.DataFrame(unclassified).sort_values('frequency', ascending=False).head(100)
            df_unclass.to_csv(csv_path, index=False)
            logger.info(f"✅ Top 100 sin clasificar: {csv_path}")


async def main():
    """Función principal"""
    import argparse

    parser = argparse.ArgumentParser(description="Ejecutar pipeline localmente con datos de Drive")
    parser.add_argument('--folder-id', help='Folder ID de Google Drive con parquets')
    parser.add_argument('--config', help='Archivo de configuración JSON')
    parser.add_argument('--sample-size', type=int, help='Procesar solo N templates (para testing)')
    parser.add_argument('--output-dir', help='Directorio de salida (default: ~/.cache/twnel_pipeline/reports)')
    parser.add_argument('--no-drive-auth', action='store_true', help='No autenticar con Drive (solo datos locales)')

    args = parser.parse_args()

    # Cargar configuración
    if args.config:
        config = PipelineConfig.from_json(args.config)
    else:
        config = PipelineConfig(
            drive_folder_id=args.folder_id,
            sample_size=args.sample_size,
        )
        if args.output_dir:
            config.output_dir = Path(args.output_dir)

    logger.info("🚀 Iniciando pipeline local...")
    logger.info(f"Output: {config.output_dir}")
    logger.info(f"BD: {config.db_path}")

    # Cargar datos
    dfs = []
    if config.drive_folder_id and not args.no_drive_auth:
        try:
            loader = DriveDataLoader()
            dfs = loader.download_parquets(config.drive_folder_id)
        except Exception as e:
            logger.error(f"Error cargando de Drive, continuando sin datos: {e}")

    if not dfs and not args.no_drive_auth:
        logger.warning("⚠️  No se cargaron datos. Usa --no-drive-auth para omitir Drive")
        return

    # Ejecutar pipeline
    runner = LocalPipelineRunner(config)
    await runner.initialize()
    await runner.process_data(dfs)


if __name__ == '__main__':
    asyncio.run(main())
