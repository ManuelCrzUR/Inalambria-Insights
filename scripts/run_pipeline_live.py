#!/usr/bin/env python3
"""
run_pipeline_live.py - Ejecuta el pipeline con interfaz en vivo

Muestra una sola pantalla que se actualiza en tiempo real mientras:
1. Lee el parquet
2. Normaliza el texto
3. Extrae plantillas
"""

import sys
import time
from pathlib import Path
from rich.live import Live
from rich.layout import Layout
from datetime import datetime

# Asegura que el paquete 'pipeline' sea encontrado al ejecutar desde cualquier directorio
sys.path.insert(0, str(Path(__file__).parent.parent))

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.text_normalizer import TextNormalizer
from pipeline.monitor.progress_ui_live import PipelineLiveUI
from pipeline.stages import TemplateExtractor


def main():
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

        # FASE 3: EXTRAER
        print("[Fase 3/3] Extrayendo plantillas...")
        time.sleep(1)

        extractor = TemplateExtractor()
        templates_extracted = 0
        unique_template_ids: set = set()

        for chunk in normalized_data:
            if "NormalizedMessage" in chunk.columns:
                for msg_text in chunk["NormalizedMessage"]:
                    template = extractor.extract_text(msg_text)
                    unique_template_ids.add(template.template_id)
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

        # Actualizar última vez
        layout["header"].update(ui._render_header())
        layout["phase"].update(ui._render_current_phase())
        layout["completed"].update(ui._render_completed_phases())
        layout["info"].update(ui._render_info())
        time.sleep(2)

    # ========================================================================
    # RESUMEN FINAL (fuera del Live)
    # ========================================================================

    print("\n" * 2)
    ui.show_summary()

    elapsed = (time.time() - ui.start_time.timestamp())
    print(f"\n📊 Estadísticas finales:")
    print(f"   📖 Lectura: {chunk_num} row_groups ({total_messages:,} mensajes)")
    print(f"   🔧 Normalización: {processed:,} mensajes")
    print(f"   🎯 Plantillas: {templates_extracted:,} procesadas / {len(unique_template_ids):,} únicas")
    print(f"   ⏱️  Tiempo total: {elapsed:.2f}s\n")


if __name__ == "__main__":
    main()
