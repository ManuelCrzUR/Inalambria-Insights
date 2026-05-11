#!/usr/bin/env python3
"""
run_pipeline_flexible.py - Ejecuta el pipeline con días específicos

Uso:
    python scripts/run_pipeline_flexible.py 14              # Un día
    python scripts/run_pipeline_flexible.py 14,15,18        # Múltiples días
    python scripts/run_pipeline_flexible.py all             # Todos los días
    python scripts/run_pipeline_flexible.py 15 --classify   # Con clasificación
"""

import sys
import time
import asyncio
import argparse
import json
from pathlib import Path
from rich.live import Live
from rich.layout import Layout
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.text_normalizer import TextNormalizer
from pipeline.core.models import NormalizedMessage, ClassificationResult
from pipeline.monitor.progress_ui_live import PipelineLiveUI
from pipeline.stages import TemplateExtractor, MessageSplitter
from pipeline.storage import PipelineStorage
from pipeline.stages.classifier import (
    HeterogeneousPanel,
    Arbiter,
    ClassifierStage,
    ClassificationStore,
)
from pipeline.stages.rule_classifier import RuleClassifier


DATA_BASE_PATH = Path("/home/manuel-cruz/Desktop/Twnel/data/raw/diciembre-2025/Diciembre2025")
MONTH = "12"
YEAR = "2025"


def get_parquet_path(day: int) -> Path:
    """Construye el path al parquet para un día específico."""
    day_folder = DATA_BASE_PATH / f"day={day}"
    parquet_file = day_folder / f"SmsData_{YEAR}_{MONTH}_{day:02d}.parquet"
    return parquet_file


def process_day(day: int, classify: bool = False, concurrency: int = 10, threshold: float = 0.7):
    """Procesa un solo día."""
    parquet_path = get_parquet_path(day)

    if not parquet_path.exists():
        print(f"❌ Archivo no encontrado: {parquet_path}")
        return False

    print(f"\n{'='*70}")
    print(f"📅 Procesando: day={day}")
    print(f"{'='*70}\n")

    # Variables para tracking (inicializar aquí)
    classified_with_rules = 0
    matched_rules = 0

    ui = PipelineLiveUI()
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="phase", size=8),
        Layout(name="completed", size=3),
        Layout(name="info", size=3),
    )

    with Live(layout, refresh_per_second=4) as live:
        # FASE 1: LEER
        print("[Fase 1/3] Leyendo parquet...")
        time.sleep(1)

        all_data = []
        total_chunks = 1394
        chunk_num = 0

        for chunk in iter_parquet_chunks(str(parquet_path), verbose=False):
            chunk_num += 1
            all_data.append(chunk)

            ui.update_phase(
                "📖 Lectura del Parquet",
                processed=chunk_num,
                total=total_chunks,
                **{
                    "Rows/chunk": len(chunk),
                    "Total rows": sum(len(c) for c in all_data),
                }
            )

            layout["header"].update(ui._render_header())
            layout["phase"].update(ui._render_current_phase())
            layout["completed"].update(ui._render_completed_phases())
            layout["info"].update(ui._render_info())

        ui.complete_phase()
        time.sleep(1)

        # FASE 2: NORMALIZAR
        print("[Fase 2/3] Normalizando texto...")
        time.sleep(1)

        total_messages = sum(len(c) for c in all_data)
        normalizer = TextNormalizer()
        normalized_data = []
        processed = 0

        for chunk_idx, chunk in enumerate(all_data):
            df = chunk.copy()
            if "Message" in df.columns:
                normalized_messages = []
                for msg_idx, msg in enumerate(df["Message"]):
                    normalized = normalizer.normalize_message(msg)
                    normalized_messages.append(normalized)
                    processed += 1

                    if processed % 50000 == 0 or processed == total_messages:
                        ui.update_phase(
                            "🔧 Normalización de Texto",
                            processed=processed,
                            total=total_messages,
                            **{
                                "Chunk": f"{chunk_idx + 1}/1394",
                            }
                        )

                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

                df["NormalizedMessage"] = normalized_messages
            normalized_data.append(df)

        ui.complete_phase()
        time.sleep(1)

        # FASE 3: EXTRAER (con DEDUPLICACIÓN y AGREGACIÓN de FRECUENCIAS)
        print("[Fase 3/3] Extrayendo plantillas (deduplicando y contando frecuencias)...")
        time.sleep(1)

        extractor = TemplateExtractor()
        storage = PipelineStorage()

        templates_extracted = 0

        # Diccionarios para agregar por template_id (con frecuencias)
        unique_templates_map = {}  # {template_id: {template_obj, frequency}}
        unique_pure_texts_map = {}  # {cleaned_message: frequency}

        for chunk in normalized_data:
            if "NormalizedMessage" in chunk.columns:
                for msg_text in chunk["NormalizedMessage"]:
                    template = extractor.extract_text(msg_text)
                    templates_extracted += 1

                    # Guardar en streaming (para compatibilidad)
                    storage.append_template(template)

                    # AGREGACIÓN: Acumular por template_id
                    if template.applied_rules:
                        # Plantilla con placeholders
                        if template.template_id not in unique_templates_map:
                            unique_templates_map[template.template_id] = {
                                "template": template,
                                "frequency": 0
                            }
                        unique_templates_map[template.template_id]["frequency"] += 1
                    else:
                        # Plantilla pura (sin placeholders)
                        if template.cleaned_message not in unique_pure_texts_map:
                            unique_pure_texts_map[template.cleaned_message] = 0
                        unique_pure_texts_map[template.cleaned_message] += 1

                    if templates_extracted % 50000 == 0 or templates_extracted == total_messages:
                        ui.update_phase(
                            "🎯 Extracción de Plantillas (deduplicando)",
                            processed=templates_extracted,
                            total=total_messages,
                            **{
                                "Plantillas únicas": len(unique_templates_map),
                                "Textos puros únicos": len(unique_pure_texts_map),
                            }
                        )

                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

        # GUARDAR plantillas únicas con frecuencias agregadas
        print("[Post-procesamiento] Guardando plantillas únicas con frecuencias...")
        unique_templates_path = Path(storage.output_dir) / "unique_templates.jsonl"
        with open(unique_templates_path, "w", encoding="utf-8") as f:
            for template_id, data in unique_templates_map.items():
                template = data["template"]
                frequency = data["frequency"]

                # Crear dict con frecuencia agregada
                unique_template_dict = {
                    "template_id": template.template_id,
                    "template_text": template.template_text,
                    "applied_rules": template.applied_rules,
                    "frequency": frequency,  # ✅ Frecuencia acumulada
                    "client_name": template.client_name,
                }
                f.write(json.dumps(unique_template_dict, ensure_ascii=False) + "\n")

        ui.complete_phase()

        # FASE 4: CLASIFICACIÓN L0 CON REGLAS
        print("[Fase 4/4] Clasificando plantillas con reglas L0...")
        time.sleep(1)

        rule_classifier = RuleClassifier()
        rule_classifications_path = Path(storage.output_dir) / "rule_classifications.jsonl"

        # Cargar templates únicas
        unique_templates_path = Path(storage.output_dir) / "unique_templates.jsonl"
        if unique_templates_path.exists():
            with open(unique_templates_path, "r", encoding="utf-8") as f:
                unique_templates_list = [
                    json.loads(line.strip())
                    for line in f
                    if line.strip()
                ]

            with open(rule_classifications_path, "w", encoding="utf-8") as out_f:
                for template_data in unique_templates_list:
                    classified_with_rules += 1

                    # Clasificar con L0
                    rule_match = rule_classifier.classify(
                        template_data.get("template_text", ""),
                        client_name=template_data.get("client_name")
                    )

                    if rule_match:
                        matched_rules += 1
                        # Crear ClassificationResult
                        result = ClassificationResult(
                            template_id=template_data.get("template_id", ""),
                            template_text=template_data.get("template_text", ""),
                            applied_rules=template_data.get("applied_rules", []),
                            frequency=template_data.get("frequency", 1),
                            label=rule_match.label,
                            category=rule_match.label.split("::")[0] if "::" in rule_match.label else rule_match.label,
                            subcategory=rule_match.label.split("::")[1] if "::" in rule_match.label else "",
                            confidence=rule_match.confidence,
                            level_used="rule",
                            agreement=True,
                            metadata={"rule_name": rule_match.rule_name},
                        )
                    else:
                        # No match - reserved for LLM classification
                        result = ClassificationResult(
                            template_id=template_data.get("template_id", ""),
                            template_text=template_data.get("template_text", ""),
                            applied_rules=template_data.get("applied_rules", []),
                            frequency=template_data.get("frequency", 1),
                            level_used="pending",
                        )

                    out_f.write(json.dumps(result.to_dict()) + "\n")

                    if classified_with_rules % 100 == 0:
                        ui.update_phase(
                            "📋 Clasificación L0 (Reglas)",
                            processed=classified_with_rules,
                            total=len(unique_templates_list),
                            **{
                                "Coincidencias": f"{matched_rules}",
                                "Pending": f"{classified_with_rules - matched_rules}",
                            }
                        )
                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

        ui.complete_phase()

        # FASE 5 (OPCIONAL): CLASIFICAR CON LLM
        if classify:
            print("[Fase 4/4] Clasificando plantillas...")
            time.sleep(1)

            try:
                with open(settings.TAXONOMY_PATH, "r", encoding="utf-8") as f:
                    taxonomy = json.load(f)
            except Exception as e:
                print(f"[ERROR] No se pudo cargar taxonomía: {e}")
                classify = False

            if classify and settings.OPENAI_API_KEY:
                panel = HeterogeneousPanel(
                    api_key=settings.OPENAI_API_KEY,
                    taxonomy_data=taxonomy
                )
                arbiter = Arbiter(
                    api_key=settings.OPENAI_API_KEY,
                    taxonomy_data=taxonomy
                )

                output_dir = Path(storage.output_dir)
                classifications_path = output_dir / settings.CLASSIFICATIONS_OUTPUT_FILENAME
                store = ClassificationStore(classifications_path)
                store.ensure_parent_exists()

                classifier_stage = ClassifierStage(
                    panel=panel,
                    arbiter=arbiter,
                    store=store,
                    agreement_threshold=threshold,
                    concurrency=concurrency,
                )

                unique_templates_path = output_dir / "unique_templates.jsonl"
                try:
                    with open(unique_templates_path, "r", encoding="utf-8") as f:
                        unique_templates_list = [
                            json.loads(line.strip())
                            for line in f
                            if line.strip()
                        ]
                except Exception as e:
                    print(f"[ERROR] No se pudo cargar unique_templates: {e}")
                    unique_templates_list = []

                async def template_iterator():
                    for template in unique_templates_list:
                        yield template

                classified_count = 0
                classification_stats = {
                    "panel_agreement": 0,
                    "arbiter": 0,
                    "human_review": 0,
                    "errors": 0,
                }

                async def run_classification():
                    nonlocal classified_count
                    async for result in classifier_stage.classify_stream(
                        template_iterator()
                    ):
                        classified_count += 1
                        classification_stats[result.level_used] = (
                            classification_stats.get(result.level_used, 0) + 1
                        )

                        if classified_count % 10 == 0 or classified_count == len(
                            unique_templates_list
                        ):
                            ui.update_phase(
                                "🤖 Clasificación LLM",
                                processed=classified_count,
                                total=len(unique_templates_list),
                                **{
                                    "Panel acuerdo": f"{classification_stats['panel_agreement']}",
                                    "Árbitro": f"{classification_stats['arbiter']}",
                                }
                            )

                            layout["header"].update(ui._render_header())
                            layout["phase"].update(ui._render_current_phase())
                            layout["completed"].update(ui._render_completed_phases())
                            layout["info"].update(ui._render_info())

                asyncio.run(run_classification())
                ui.complete_phase()
            else:
                if not settings.OPENAI_API_KEY:
                    print("[WARNING] OPENAI_API_KEY no configurada, saltando clasificación")

        storage.close_jsonl_files()

        unique_templates = len(unique_templates_map)
        unique_pure_messages = len(unique_pure_texts_map)

        layout["header"].update(ui._render_header())
        layout["phase"].update(ui._render_current_phase())
        layout["completed"].update(ui._render_completed_phases())
        layout["info"].update(ui._render_info())
        time.sleep(2)

    storage.save_metadata({
        "pipeline_date": datetime.now().isoformat(),
        "total_messages": templates_extracted,
        "unique_templates": unique_templates,
        "unique_pure_messages": unique_pure_messages,
        "processing_time_seconds": time.time() - ui.start_time.timestamp(),
        "parquet_file": str(parquet_path),
        "day": day,
        "data_source": "diciembre-2025",
        "mode": "streaming",
        "l0_classification": {
            "total_classified": classified_with_rules,
            "matched_rules": matched_rules,
            "pending_llm": classified_with_rules - matched_rules,
            "coverage_percentage": (matched_rules / classified_with_rules * 100) if classified_with_rules > 0 else 0,
        }
    })

    print("\n" * 2)
    ui.show_summary(
        unique_templates=unique_templates,
        unique_pure_messages=unique_pure_messages,
        total_messages=templates_extracted,
    )

    elapsed = (time.time() - ui.start_time.timestamp())
    print(f"\n📝 Detalles técnicos:")
    print(f"   📖 Lectura: {chunk_num} row_groups ({total_messages:,} mensajes)")
    print(f"   🔧 Normalización: {processed:,} mensajes")
    print(f"   🎯 Plantillas: {templates_extracted:,} procesadas")
    print(f"       └─ Con placeholders (únicas): {unique_templates:,}")
    print(f"       └─ Texto puro (únicos): {unique_pure_messages:,}")
    print(f"   📋 Clasificación L0 (Reglas):")
    print(f"       └─ Coincidencias: {matched_rules:,}/{classified_with_rules:,} ({matched_rules/classified_with_rules*100:.1f}%)")
    print(f"       └─ Pending para LLM: {classified_with_rules - matched_rules:,}")
    if classify:
        print(f"   🤖 Clasificadas (LLM): {classified_count:,}")
    print(f"   ⏱️  Tiempo total: {elapsed:.2f}s")
    print(f"\n💾 Datos guardados en: {storage.output_dir}/\n")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Ejecutar pipeline SMS con días específicos"
    )
    parser.add_argument(
        "days",
        nargs="?",
        default="all",
        help="Días a procesar: número (14), lista (14,15,18) o 'all' (default: all)"
    )
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Activar clasificación LLM"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Llamadas LLM paralelas (default: 10)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Confidence mínima (default: 0.7)"
    )

    args = parser.parse_args()

    # Parsear días
    if args.days.lower() == "all":
        days = [14, 15, 18, 19, 23]
    else:
        try:
            days = [int(d.strip()) for d in args.days.split(",")]
        except ValueError:
            print(f"❌ Error: formato inválido para días. Usa: 14 o 14,15,18 o all")
            sys.exit(1)

    print(f"\n🚀 Iniciando pipeline para días: {days}")
    print(f"   Clasificación: {'✅ SÍ' if args.classify else '❌ NO'}")

    success_count = 0
    failed_days = []

    for day in days:
        try:
            if process_day(
                day,
                classify=args.classify,
                concurrency=args.concurrency,
                threshold=args.threshold
            ):
                success_count += 1
            else:
                failed_days.append(day)
        except Exception as e:
            print(f"❌ Error procesando day={day}: {e}")
            failed_days.append(day)

    # Resumen final
    print(f"\n{'='*70}")
    print(f"📊 RESUMEN FINAL")
    print(f"{'='*70}")
    print(f"✅ Días procesados correctamente: {success_count}/{len(days)}")
    if failed_days:
        print(f"❌ Días fallidos: {failed_days}")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
