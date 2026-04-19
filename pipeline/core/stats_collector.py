"""
stats_collector.py - Acumulador de estadísticas para streaming

Diseño:
- StatsAccumulator recibe chunks de DataFrames
- Acumula contadores, sets, etc sin cargar TODO en memoria
- Cada chunk se procesa y libera
- Al final, genera reporte completo

Patrón: Divide y Vencerás para análisis de datos grandes.
"""

from collections import Counter, defaultdict
from typing import Dict, List, Set, Optional
from datetime import datetime
import pandas as pd


class StatsAccumulator:
    """
    Acumula estadísticas sobre mensajes SMS de forma incremental.

    Cada chunk de datos se procesa y libera inmediatamente.
    Nunca carga todo el archivo en memoria.

    Uso:
        stats = StatsAccumulator()

        for chunk in iter_parquet_chunks(parquet_path):
            stats.update(chunk)
            stats.print_progress()

        stats.report()
    """

    def __init__(self):
        """Inicializa acumuladores vacíos."""
        # Contadores
        self.total_messages = 0
        self.client_counts: Counter = Counter()
        self.operator_counts: Counter = Counter()
        self.priority_counts: Counter = Counter()

        # Sets (para contar únicos)
        self.unique_phones: Set[str] = set()

        # Otros
        self.min_timestamp: Optional[datetime] = None
        self.max_timestamp: Optional[datetime] = None

        # Progreso
        self.chunks_processed = 0

    def update(self, df_chunk: pd.DataFrame) -> None:
        """
        Actualiza estadísticas con un chunk de datos.

        Args:
            df_chunk: DataFrame con mensajes (típicamente un row_group)
        """
        self.chunks_processed += 1

        # Contar mensajes
        chunk_size = len(df_chunk)
        self.total_messages += chunk_size

        # Clientes
        if "ClientName" in df_chunk.columns:
            client_values = df_chunk["ClientName"].value_counts()
            self.client_counts.update(client_values)

        # Operadores
        if "OperatorName" in df_chunk.columns:
            op_values = df_chunk["OperatorName"].value_counts()
            self.operator_counts.update(op_values)

        # Prioridades (ID + Description)
        if "PriorityId" in df_chunk.columns and "PriorityDescription" in df_chunk.columns:
            priorities = df_chunk.groupby(["PriorityId", "PriorityDescription"]).size()
            for (pid, pdesc), count in priorities.items():
                self.priority_counts[(pid, pdesc)] += count

        # Teléfonos únicos
        if "PhoneNumber" in df_chunk.columns:
            phones = df_chunk["PhoneNumber"].unique()
            self.unique_phones.update(phones)

        # Timestamps
        if "ArrivalDate" in df_chunk.columns:
            valid_timestamps = pd.to_datetime(
                df_chunk["ArrivalDate"], errors="coerce"
            )
            valid_timestamps = valid_timestamps[valid_timestamps.notna()]

            if len(valid_timestamps) > 0:
                chunk_min = valid_timestamps.min()
                chunk_max = valid_timestamps.max()

                if self.min_timestamp is None:
                    self.min_timestamp = chunk_min
                else:
                    self.min_timestamp = min(self.min_timestamp, chunk_min)

                if self.max_timestamp is None:
                    self.max_timestamp = chunk_max
                else:
                    self.max_timestamp = max(self.max_timestamp, chunk_max)

    def print_progress(self) -> None:
        """Imprime progreso actual."""
        print(f"   → Chunk {self.chunks_processed}: {self.total_messages:,} mensajes acumulados")

    def report(self) -> Dict:
        """
        Genera reporte completo de estadísticas.

        Returns:
            Dict con todas las estadísticas
        """
        report_data = {
            "total_messages": self.total_messages,
            "chunks_processed": self.chunks_processed,
            "unique_clients": len(self.client_counts),
            "unique_operators": len(self.operator_counts),
            "unique_phones": len(self.unique_phones),
            "unique_priorities": len(self.priority_counts),
            "min_timestamp": self.min_timestamp,
            "max_timestamp": self.max_timestamp,
        }

        return report_data

    def print_report(self) -> None:
        """Imprime reporte formateado en la consola."""
        print("\n" + "=" * 70)
        print("📊 ESTADÍSTICAS FINALES")
        print("=" * 70)

        print(f"\n📈 VOLUMEN:")
        print(f"   Mensajes totales: {self.total_messages:,}")
        print(f"   Chunks procesados: {self.chunks_processed}")

        print(f"\n🏢 DIMENSIONES:")
        print(f"   Clientes únicos: {len(self.client_counts)}")
        print(f"   Operadores únicos: {len(self.operator_counts)}")
        print(f"   Números de teléfono únicos: {len(self.unique_phones):,}")
        print(f"   Prioridades distintas: {len(self.priority_counts)}")

        print(f"\n🏆 TOP 5 CLIENTES:")
        for i, (client, count) in enumerate(self.client_counts.most_common(5), 1):
            pct = (count / self.total_messages) * 100
            bar = "█" * int(pct / 2)
            print(f"   {i}. {client:40} | {count:8,} ({pct:5.1f}%) {bar}")

        print(f"\n📱 DISTRIBUCIÓN DE OPERADORES:")
        for operator, count in self.operator_counts.most_common():
            pct = (count / self.total_messages) * 100
            bar = "█" * int(pct / 3)
            print(f"   {operator:20} | {count:8,} ({pct:5.1f}%) {bar}")

        print(f"\n⚡ DISTRIBUCIÓN DE PRIORIDADES:")
        for (pid, pdesc), count in sorted(self.priority_counts.items()):
            pct = (count / self.total_messages) * 100
            bar = "█" * int(pct / 2)
            print(f"   ID={pid} | {pdesc:25} | {count:8,} ({pct:5.1f}%) {bar}")

        if self.min_timestamp and self.max_timestamp:
            print(f"\n📅 RANGO TEMPORAL:")
            print(f"   Inicio: {self.min_timestamp}")
            print(f"   Final: {self.max_timestamp}")
            duration = (self.max_timestamp - self.min_timestamp).total_seconds() / 3600
            print(f"   Duración: {duration:.1f} horas")

        print("\n" + "=" * 70)
        print("✅ ANÁLISIS COMPLETADO")
        print("=" * 70 + "\n")
