#!/usr/bin/env python3
"""
test_full_parquet.py - Procesa TODO el parquet (6.7M registros) sin "Killed"

Usa: data_reader.iter_parquet_chunks() + stats_collector.StatsAccumulator

Patrón: Divide y Vencerás
- Lee row_group por row_group (~50k filas c/u)
- Acumula estadísticas
- Libera memoria del chunk
- Repite hasta terminar

Memory footprint: ~200MB constante (vs 6GB si cargas TODO)
Tiempo esperado: 2-3 minutos
"""

import sys
import time

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator


def main():
    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    print("\n" + "=" * 70)
    print("  🚀 PROCESANDO 6.7M REGISTROS (Divide y Vencerás)")
    print("=" * 70)
    print("\nParquet: SmsData_2025_12_15.parquet")
    print("Filas: 6,968,574")
    print("Estrategia: Row groups + StatsAccumulator")
    print("Memory: ~200MB (vs 6GB si cargas TODO)\n")

    # Inicializar acumulador
    stats = StatsAccumulator()

    # Contador de tiempo
    start = time.time()

    # FLUJO PRINCIPAL: Iterate → Process → Liberate
    print("Iniciando procesamiento...\n")

    try:
        for chunk in iter_parquet_chunks(parquet_path, delivered_only=True, verbose=True):
            # Actualizar estadísticas con este chunk
            stats.update(chunk)

            # Mostrar progreso cada chunk
            stats.print_progress()

            # El chunk se libera automáticamente al salir del loop

    except KeyboardInterrupt:
        print("\n⏸️  Procesamiento interrumpido por usuario")
        return
    except Exception as e:
        print(f"\n❌ Error durante procesamiento: {e}")
        import traceback
        traceback.print_exc()
        return

    # Tiempo total
    elapsed = time.time() - start

    # MOSTRAR RESULTADOS
    stats.print_report()

    # Estadísticas de performance
    print(f"⏱️  PERFORMANCE:")
    print(f"   Tiempo total: {elapsed:.2f}s ({elapsed/60:.2f} min)")
    print(f"   Velocidad: {stats.total_messages/elapsed:,.0f} msg/seg")
    print(f"   Chunks procesados: {stats.chunks_processed}")

    print(f"\n✨ ¡ÉXITO! Procesados {stats.total_messages:,} mensajes sin 'Killed'")
    print(f"   (Esto demuestra que la solución funciona para datos reales)\n")


if __name__ == "__main__":
    main()
