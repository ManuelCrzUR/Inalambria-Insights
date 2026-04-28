#!/usr/bin/env python3
"""
run_pipeline_live.py - Ejecuta el pipeline con interfaz en vivo

Muestra una sola pantalla que se actualiza en tiempo real mientras:
1. Lee el parquet
2. Normaliza el texto
3. Extrae plantillas
4. (Opcional) Clasifica plantillas con LLM panel + árbitro

Uso:
    python scripts/run_pipeline_live.py                    # Sin clasificación
    python scripts/run_pipeline_live.py --classify         # Con clasificación LLM
    python scripts/run_pipeline_live.py --classify --concurrency 5
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

# Asegura que el paquete 'pipeline' sea encontrado al ejecutar desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.text_normalizer import TextNormalizer
from pipeline.core.models import NormalizedMessage
from pipeline.monitor.progress_ui_live import PipelineLiveUI
from pipeline.stages import TemplateExtractor, MessageSplitter
from pipeline.storage import PipelineStorage
from pipeline.stages.classifier import (
    HeterogeneousPanel,
    Arbiter,
    ClassifierStage,
    ClassificationStore,
)


def main(classify: bool = False, concurrency: int = 10, threshold: float = 0.7):
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/data/raw/diciembre-2025/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    ui = PipelineLiveUI()

    # Crear layout
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="phase", size=8),
        Layout(name="completed", size=3),
        Layout(name="info", size=3),
    )

    print("\n🚀 Iniciando pipeline con interfaz en vivo...\n")
    time.sleep(1)

    # ========================================================================
    # EJECUTAR CON LIVE UPDATES (TODO dentro del with Live)
    # ========================================================================

    with Live(layout, refresh_per_second=4) as live:
        # FASE 1: LEER
        print("[Fase 1/3] Leyendo parquet...")
        time.sleep(1)

        all_data = []
        total_chunks = 1394
        chunk_num = 0

        for chunk in iter_parquet_chunks(parquet_path, verbose=False):
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

            # Actualizar pantalla
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

                        # ⚠️ CRÍTICO: Actualizar pantalla DENTRO del loop
                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

                df["NormalizedMessage"] = normalized_messages
            normalized_data.append(df)

        ui.complete_phase()
        time.sleep(1)

        # FASE 3: EXTRAER (con STREAMING storage — sin acumular)
        print("[Fase 3/3] Extrayendo plantillas...")
        time.sleep(1)

        extractor = TemplateExtractor()
        storage = PipelineStorage()

        templates_extracted = 0
        unique_template_ids = set()  # Para contar únicos sin acumular templates
        unique_pure_texts = set()

        for chunk in normalized_data:
            if "NormalizedMessage" in chunk.columns:
                for msg_text in chunk["NormalizedMessage"]:
                    template = extractor.extract_text(msg_text)

                    # STREAMING: guardar incremental (sin acumular en memoria)
                    storage.append_template(template)
                    storage.append_unique_template(template)

                    # Solo contar (no guardar) para stats
                    if template.applied_rules:
                        unique_template_ids.add(template.template_id)
                    else:
                        unique_pure_texts.add(template.cleaned_message)

                    templates_extracted += 1

                    if templates_extracted % 50000 == 0 or templates_extracted == total_messages:
                        ui.update_phase(
                            "🎯 Extracción de Plantillas",
                            processed=templates_extracted,
                            total=total_messages,
                            **{
                                "Plantillas únicas": len(unique_template_ids),
                            }
                        )

                        # Actualizar pantalla
                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

        ui.complete_phase()

        # FASE 4 (OPCIONAL): CLASIFICAR con LLM
        if classify:
            print("[Fase 4/4] Clasificando plantillas con LLM...")
            time.sleep(1)

            # Cargar taxonomía
            try:
                with open(settings.TAXONOMY_PATH, "r", encoding="utf-8") as f:
                    taxonomy = json.load(f)
            except Exception as e:
                print(f"[ERROR] No se pudo cargar taxonomía: {e}")
                classify = False

            if classify and settings.OPENAI_API_KEY:
                # Inicializar componentes de clasificación
                panel = HeterogeneousPanel(
                    api_key=settings.OPENAI_API_KEY,
                    taxonomy_data=taxonomy
                )
                arbiter = Arbiter(
                    api_key=settings.OPENAI_API_KEY,
                    taxonomy_data=taxonomy
                )

                # Store en el mismo directorio que las templates
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

                # Cargar templates únicas del archivo ya generado
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

                # Crear async iterator de templates
                async def template_iterator():
                    for template in unique_templates_list:
                        yield template

                # Clasificar (async)
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

                            # Actualizar pantalla
                            layout["header"].update(ui._render_header())
                            layout["phase"].update(ui._render_current_phase())
                            layout["completed"].update(ui._render_completed_phases())
                            layout["info"].update(ui._render_info())

                # Ejecutar loop async
                asyncio.run(run_classification())
                ui.complete_phase()
            else:
                if not settings.OPENAI_API_KEY:
                    print(
                        "[WARNING] OPENAI_API_KEY no configurada, saltando clasificación"
                    )

        # Cerrar archivos JSONL después de streaming
        storage.close_jsonl_files()

        unique_templates = len(unique_template_ids)
        unique_pure_messages = len(unique_pure_texts)

        # Actualizar última vez
        layout["header"].update(ui._render_header())
        layout["phase"].update(ui._render_current_phase())
        layout["completed"].update(ui._render_completed_phases())
        layout["info"].update(ui._render_info())
        time.sleep(2)

    # ========================================================================
    # METADATA FINAL
    # ========================================================================

    storage.save_metadata({
        "pipeline_date": datetime.now().isoformat(),
        "total_messages": templates_extracted,
        "unique_templates": unique_templates,
        "unique_pure_messages": unique_pure_messages,
        "processing_time_seconds": time.time() - ui.start_time.timestamp(),
        "parquet_file": str(parquet_path),
        "data_source": "diciembre-2025",
        "mode": "streaming",
    })

    # ========================================================================
    # RESUMEN FINAL (fuera del Live)
    # ========================================================================

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
    if classify:
        print(f"   🤖 Clasificadas: {classified_count:,}")
    print(f"   ⏱️  Tiempo total: {elapsed:.2f}s")
    print(f"\n💾 Datos guardados (streaming) en: {storage.output_dir}/")
    print(f"   ├─ templates_with_placeholders.jsonl    (streaming)")
    print(f"   ├─ templates_pure_messages.jsonl        (streaming)")
    print(f"   ├─ unique_templates.jsonl               (deduplicado)")
    if classify:
        print(f"   ├─ classifications.jsonl                (LLM)")
    print(f"   └─ metadata.json                        (stats)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ejecutar pipeline SMS con interfaz en vivo")
    parser.add_argument(
        "--classify",
        action="store_true",
        help="Activar etapa de clasificación LLM (panel + árbitro)"
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
        help="Confidence mínima para acuerdo panel (default: 0.7)"
    )

    args = parser.parse_args()
    main(
        classify=args.classify,
        concurrency=args.concurrency,
        threshold=args.threshold
    )
