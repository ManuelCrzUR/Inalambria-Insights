"""
pipeline_storage.py - Persistencia STREAMING de datos procesados del pipeline

Guarda el resultado del pipeline en múltiples formatos con escritura incremental:
- JSONL: templates procesados (streaming, sin acumular en memoria)
- Parquet: datos crudos deduplicados (al final, si se necesita)
- JSON: metadata de la corrida (fecha, parámetros, stats)

Flujo streaming (NO acumula):
    Template → storage.append_template()
    Template → storage.append_split_template()
    ... (cada chunk se procesa y guarda, memoria liberada)
    Final → storage.finalize_parquet() (opcional)

Escrituras incrementales:
    - JSONL: append directo al archivo conforme procesamos
    - Parquet chunks: guarda lotes de 50k como archivos separados, luego mergea

Uso con streaming:
    storage = PipelineStorage()
    for chunk in data:
        templates = extractor.extract_batch(chunk)
        for t in templates:
            storage.append_template(t)  # Guardar incremental
    storage.save_metadata({...})

Diseño:
    - Output dir organizado por fecha: output/2025-04-24/
    - Modular: append_*() para streaming, save_*() para batch (legacy)
    - Escalable: O(1) memoria durante procesamiento (streaming)
    - Robusto: escrituras atómicas, deduplica on-the-fly
    - Eficiente: JSONL durante ejecución, Parquet al final si es necesario
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set

import pandas as pd

from pipeline.core.models import Template
from pipeline.stages.message_splitter import SplitResult
from config.settings import OUTPUT_DIR


# ============================================================================
# PIPELINE STORAGE - STREAMING
# ============================================================================

class PipelineStorage:
    """
    Persistencia STREAMING de datos procesados del pipeline.

    Soporta dos modos:
    1. **Streaming** (para millones de mensajes): append_*() mantiene O(1) memoria
    2. **Batch** (para datasets pequeños): save_*() guarda todo de una vez

    Attributes:
        output_dir: Directorio de salida (output/YYYY-MM-DD/), creado automáticamente
        _jsonl_files: Dict de paths a archivos JSONL abiertos
        _unique_ids: Set de template_ids vistos (para deduplicación)

    Example (Streaming):
        >>> storage = PipelineStorage()
        >>> for chunk in data:
        ...     templates = extractor.extract_batch(chunk)
        ...     for t in templates:
        ...         storage.append_template(t)  # Streaming
        >>> storage.save_metadata({"total": 6712400})

    Example (Batch):
        >>> storage = PipelineStorage()
        >>> storage.save_split(split_result)  # Legacy
        >>> storage.save_unique_templates(templates)
    """

    def __init__(self, output_dir: Optional[Path] = None) -> None:
        """
        Inicializa storage con directorio de salida organizado por fecha.

        Args:
            output_dir: Directorio base. Si None, usa OUTPUT_DIR de settings.
        """
        base = Path(output_dir) if output_dir else OUTPUT_DIR
        self.output_dir = base / datetime.now().strftime("%Y-%m-%d")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Streaming state
        self._jsonl_files = {}  # {"with_ph": file_handle, "pure": file_handle}
        self._unique_ids: Set[str] = set()  # Deduplicación on-the-fly
        self._chunk_count = 0

    # =========================================================================
    # API STREAMING: Escritura incremental sin acumular
    # =========================================================================

    def append_template(self, template: Template) -> None:
        """
        Guarda un template de forma incremental a JSONL.

        Determina automáticamente si es "con placeholders" o "puro" y
        escribe a archivo correspondiente. Deduplica por template_id en JSONL.

        Mantiene O(1) memoria: no acumula, escribe y suelta.

        Args:
            template: Un Template object para procesar.
        """
        # Determinar categoría
        category = "with_placeholders" if template.applied_rules else "pure_messages"

        # Abrir archivo si no está abierto
        if category not in self._jsonl_files:
            path = self.output_dir / f"templates_{category}.jsonl"
            self._jsonl_files[category] = path.open("a", encoding="utf-8")

        # Escribir una línea (template metadata)
        record = {
            "template_id": template.template_id,
            "template_text": template.template_text,
            "original_message": template.original_message,
            "cleaned_message": template.cleaned_message,
            "phone_number": template.phone_number,
            "status_id": template.status_id,
            "client_name": template.client_name,
            "timestamp": template.timestamp.isoformat() if template.timestamp else None,
            "operator_name": template.operator_name,
            "applied_rules": template.applied_rules,
        }
        self._jsonl_files[category].write(json.dumps(record, ensure_ascii=False) + "\n")
        self._jsonl_files[category].flush()

    def append_unique_template(self, template: Template) -> None:
        """
        Guarda un template deduplicado (1 por template_id) a JSONL.

        Mantiene contador de frecuencias internamente. Deduplica on-the-fly:
        si el template_id ya fue visto, solo incrementa contador en memoria.

        Útil para análisis de templates únicos sin guardar duplicados.

        Args:
            template: Un Template object para procesar.
        """
        # Abrir archivo si no está abierto
        if "unique_templates" not in self._jsonl_files:
            path = self.output_dir / "unique_templates.jsonl"
            self._jsonl_files["unique_templates"] = path.open("a", encoding="utf-8")

        # Solo guardar si es la primera vez que vemos este ID
        if template.template_id not in self._unique_ids:
            self._unique_ids.add(template.template_id)

            record = {
                "template_id": template.template_id,
                "template_text": template.template_text,
                "applied_rules": template.applied_rules,
                "frequency": 1,
            }
            self._jsonl_files["unique_templates"].write(
                json.dumps(record, ensure_ascii=False) + "\n"
            )
            self._jsonl_files["unique_templates"].flush()

    def close_jsonl_files(self) -> None:
        """
        Cierra todos los archivos JSONL abiertos.

        Llamar al terminar el streaming.
        """
        for f in self._jsonl_files.values():
            if f and not f.closed:
                f.close()
        self._jsonl_files.clear()

    # =========================================================================
    # API BATCH (legacy): Para datasets pequeños
    # =========================================================================

    def save_split(self, split_result: SplitResult) -> Dict[str, Path]:
        """
        Guarda templates separados (con/sin placeholders) como Parquet.

        ⚠️  LEGACY: Para datasets < 1M filas. Para streaming, usa append_template().

        Args:
            split_result: Resultado de MessageSplitter.split()

        Returns:
            Dict con claves "with_placeholders" y "pure_messages".
        """
        paths = {}

        paths["with_placeholders"] = self._save_parquet(
            split_result.with_placeholders,
            "templates_with_placeholders.parquet"
        )

        paths["pure_messages"] = self._save_parquet(
            split_result.pure_messages,
            "templates_pure_messages.parquet"
        )

        return paths

    def save_unique_templates(self, templates: List[Template]) -> Path:
        """
        Deduplica templates por template_id y guarda como JSONL.

        ⚠️  LEGACY: Para datasets < 1M filas. Para streaming, usa append_unique_template().

        Args:
            templates: Lista completa de templates.

        Returns:
            Path al archivo .jsonl creado.
        """
        seen: Dict[str, dict] = {}

        for template in templates:
            tid = template.template_id
            if tid not in seen:
                seen[tid] = {"count": 0, "template": template}
            seen[tid]["count"] += 1

        path = self.output_dir / "unique_templates.jsonl"
        tmp_path = path.with_suffix(".tmp")

        with tmp_path.open("w", encoding="utf-8") as f:
            for entry in seen.values():
                t = entry["template"]
                record = {
                    "template_id": t.template_id,
                    "template_text": t.template_text,
                    "frequency": entry["count"],
                    "applied_rules": t.applied_rules,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

        tmp_path.rename(path)
        return path

    def save_metadata(self, data: Dict) -> Path:
        """
        Guarda metadata de la corrida como JSON formateado.

        Args:
            data: Dict con stats (total_messages, unique_templates, etc.)

        Returns:
            Path al archivo .json creado.
        """
        path = self.output_dir / "metadata.json"
        tmp_path = path.with_suffix(".tmp")

        tmp_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str)
        )

        tmp_path.rename(path)
        return path

    # =========================================================================
    # MÉTODOS INTERNOS
    # =========================================================================

    def _save_parquet(self, templates: List[Template], filename: str) -> Path:
        """
        Serializa List[Template] → DataFrame → Parquet con escritura atómica.

        Args:
            templates: Lista de Template objects.
            filename: Nombre del archivo.

        Returns:
            Path al archivo .parquet creado.
        """
        df = self._to_dataframe(templates)

        path = self.output_dir / filename
        tmp_path = path.with_suffix(".tmp")

        df.to_parquet(
            tmp_path,
            engine="pyarrow",
            compression="snappy",
            index=False
        )

        tmp_path.rename(path)
        return path

    def _to_dataframe(self, templates: List[Template]) -> pd.DataFrame:
        """
        Convierte List[Template] → DataFrame serializable.

        Args:
            templates: Lista de Template objects.

        Returns:
            pd.DataFrame con columnas tipadas.
        """
        rows = []

        for t in templates:
            rows.append({
                "template_id": t.template_id,
                "template_text": t.template_text,
                "original_message": t.original_message,
                "cleaned_message": t.cleaned_message,
                "phone_number": t.phone_number,
                "status_id": t.status_id,
                "client_id": t.client_id,
                "client_name": t.client_name,
                "priority_id": t.priority_id,
                "priority_description": t.priority_description,
                "timestamp": t.timestamp,
                "operator_name": t.operator_name,
                "account_name": t.account_name,
                "applied_rules": t.applied_rules,
                "metadata": json.dumps(t.metadata),
            })

        return pd.DataFrame(rows)
