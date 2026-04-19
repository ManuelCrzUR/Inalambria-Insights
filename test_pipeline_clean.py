#!/usr/bin/env python3
"""
test_pipeline_clean.py - Demo MEJORADA del pipeline

Flujo limpio:
1. FASE 1: Leer parquet (% en vivo, UNA sola pantalla)
2. FASE 2: Normalizar (% en vivo, UNA sola pantalla)
3. FASE 3: Extraer plantillas (% en vivo, UNA sola pantalla)

Sin scroll, sin múltiples pantallas. UNA interfaz que se actualiza.
"""

import sys
import time

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.monitor.progress_ui_live import PipelineLiveUI


def main():
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    # Crear interfaz
    ui = PipelineLiveUI()

    # ========================================================================
    # FASE 1: LEER PARQUET
    # ========================================================================

    print("Iniciando lectura...\n")
    time.sleep(1)

    # Contar total de row_groups primero
    total_chunks = 1394  # Conocemos que son 1394

    chunk_num = 0
    all_data = []

    def phase1_read():
        nonlocal chunk_num
        nonlocal all_data

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

            # Actualizar menos frecuente (cada 10 chunks) para no saturar
            if chunk_num >= total_chunks:
                return False  # Terminar

            return True  # Continuar

    # Ejecutar fase 1
    print("\n[Fase 1/3] Leyendo parquet...\n")
    phase1_read()
    ui.complete_phase()

    print(f"✅ Lectura completada: {chunk_num} row_groups\n")
    time.sleep(2)

    # ========================================================================
    # FASE 2: NORMALIZAR
    # ========================================================================

    print("[Fase 2/3] Normalizando texto...\n")
    time.sleep(1)

    total_messages = sum(len(c) for c in all_data)
    processed = 0

    def phase2_normalize():
        nonlocal processed

        for chunk in all_data:
            if "Message" in chunk.columns:
                for msg in chunk["Message"]:
                    # Simular normalización
                    _ = str(msg).lower().strip()
                    processed += 1

                    # Actualizar UI cada 50k mensajes
                    if processed % 50000 == 0:
                        ui.update_phase(
                            "🔧 Normalización de Texto",
                            processed=processed,
                            total=total_messages,
                            **{
                                "Speed": f"{processed / (time.time() - ui.start_time.timestamp()):,.0f} msg/s",
                            }
                        )

            if processed >= total_messages:
                return False

            return True

    # Ejecutar fase 2
    phase2_normalize()
    ui.complete_phase()

    print(f"✅ Normalización completada: {processed} mensajes\n")
    time.sleep(2)

    # ========================================================================
    # FASE 3: EXTRAER PLANTILLAS (simular)
    # ========================================================================

    print("[Fase 3/3] Extrayendo plantillas...\n")
    time.sleep(1)

    templates_extracted = 0

    def phase3_extract():
        nonlocal templates_extracted

        for chunk in all_data:
            if "Message" in chunk.columns:
                # Simular extracción
                templates_extracted += len(chunk)

                # Actualizar UI cada 50k
                if templates_extracted % 50000 == 0:
                    ui.update_phase(
                        "🎯 Extracción de Plantillas",
                        processed=templates_extracted,
                        total=total_messages,
                        **{
                            "Speed": f"{templates_extracted / (time.time() - ui.start_time.timestamp()):,.0f} templates/s",
                        }
                    )

            if templates_extracted >= total_messages:
                return False

            return True

    # Ejecutar fase 3
    phase3_extract()
    ui.complete_phase()

    print(f"✅ Extracción completada: {templates_extracted} plantillas\n")

    # ========================================================================
    # RESUMEN FINAL
    # ========================================================================

    ui.show_summary()

    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETADO")
    print("=" * 70)

    elapsed = (time.time() - ui.start_time.timestamp())
    print(f"\nTiempo total: {elapsed:.2f}s")
    print(f"📖 Lectura: {chunk_num} row_groups ({total_messages:,} mensajes)")
    print(f"🔧 Normalización: {processed:,} mensajes")
    print(f"🎯 Plantillas: {templates_extracted:,} extraídas\n")


if __name__ == "__main__":
    main()
