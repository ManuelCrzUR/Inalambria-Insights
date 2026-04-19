#!/usr/bin/env python3
"""
test_pipeline_monitor.py - Demo de la interfaz visual del pipeline

Muestra:
1. Monitor de progreso en tiempo real
2. Lectura del parquet con % de progreso
3. Simulación de text_normalizer.py

Ejecución:
    python3 test_pipeline_monitor.py
"""

import sys
import time
from collections import Counter

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.monitor.progress_monitor import PipelineMonitor, StageStatus
from pipeline.monitor.progress_ui import PipelineUI


def simulate_normalize(text: str) -> str:
    """Simula normalización de texto (sin hacer nada realmente)"""
    # En la versión real, esto limpiaría espacios, caracteres especiales, etc.
    time.sleep(0.0001)  # Simula procesamiento
    return text.lower()


def main():
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    # 1. Crear monitor
    monitor = PipelineMonitor()
    ui = PipelineUI(monitor)

    # 2. Agregar stages
    reader_stage = monitor.add_stage("📖 Data Reader (iter_parquet_chunks)")
    normalizer_stage = monitor.add_stage("🔧 Text Normalizer")
    stats_stage = monitor.add_stage("📊 Stats Collector")

    # 3. Mostrar inicio
    ui.display()
    time.sleep(1)

    # ========================================================================
    # STAGE 1: DATA READER
    # ========================================================================

    print("\n[1/3] Iniciando Data Reader...")
    time.sleep(1)

    reader_stage.start(total_items=1394)  # 1394 row_groups

    try:
        for chunk_num, chunk in enumerate(iter_parquet_chunks(parquet_path), 1):
            # Actualizar stage
            reader_stage.increment(
                1,
                chunk_rows=len(chunk),
                total_rows=len(chunk) * chunk_num
            )

            # Mostrar UI
            if chunk_num % 50 == 0:  # Actualizar cada 50 chunks
                ui.display()
                time.sleep(0.1)

            # ================================================================
            # STAGE 2: TEXT NORMALIZER (en paralelo)
            # ================================================================

            if chunk_num == 1:
                normalizer_stage.start(total_items=len(chunk) * 1394)

            # Simular normalización
            normalized_count = 0
            if "Message" in chunk.columns:
                for msg in chunk["Message"]:
                    normalize_text = simulate_normalize(str(msg))
                    normalized_count += 1

            normalizer_stage.increment(
                normalized_count,
                speed=f"{normalizer_stage.items_per_second:,.0f} msg/s"
            )

            # ================================================================
            # STAGE 3: STATS (en paralelo)
            # ================================================================

            if chunk_num == 1:
                stats_stage.start(total_items=len(chunk) * 1394)

            # Contar estadísticas
            clients = Counter(chunk.get("ClientName", []))
            operators = Counter(chunk.get("OperatorName", []))

            stats_stage.increment(
                len(chunk),
                unique_clients=len(clients),
                unique_operators=len(operators)
            )

        reader_stage.complete()
        normalizer_stage.complete()
        stats_stage.complete()

    except KeyboardInterrupt:
        print("\n\n⏸️  Pipeline interrumpido por usuario")
        return
    except Exception as e:
        reader_stage.error(str(e))
        monitor.add_error(str(e))
        ui.display()
        return

    # 4. Mostrar resumen final
    ui.display_summary()

    print("\n" + "=" * 70)
    print("✅ PIPELINE COMPLETADO")
    print("=" * 70)
    print(f"\nTiempo total: {monitor.elapsed_seconds:.2f}s")
    print(f"Data Reader: {reader_stage.processed_items} row_groups leídos")
    print(f"Text Normalizer: {normalizer_stage.processed_items} mensajes normalizados")
    print(f"Stats: {stats_stage.processed_items} registros procesados\n")


if __name__ == "__main__":
    main()
