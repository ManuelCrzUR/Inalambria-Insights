#!/usr/bin/env python3
"""
run_stage_data_reader.py - Ejecuta SOLO la etapa de lectura de parquet

Sin normalización, sin extracción, sin clasificación.
Solo lee el parquet, filtra entregados y muestra estadísticas.

Uso:
    python3 run_stage_data_reader.py
"""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.stats_collector import StatsAccumulator


def main():
    console = Console()

    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    console.print(Panel(
        "[bold cyan]📖 DATA READER STAGE[/bold cyan]\n"
        "Lee el parquet en chunks sin saturar memoria\n"
        "Filtra solo mensajes entregados (StatusId=3)",
        title="[bold]Stage de Lectura[/bold]"
    ))

    # ========================================================================
    # LEER PARQUET CON STREAMING
    # ========================================================================

    console.print("\n[bold]1. Leyendo parquet...[/bold]")
    time.sleep(1)

    stats = StatsAccumulator()
    chunk_count = 0
    start_time = time.time()

    for chunk in iter_parquet_chunks(parquet_path, delivered_only=True, verbose=False):
        chunk_count += 1
        stats.update(chunk)

        # Mostrar progreso cada 100 chunks
        if chunk_count % 100 == 0:
            elapsed = time.time() - start_time
            speed = chunk_count / elapsed
            console.print(
                f"   📦 Chunk {chunk_count}/1394 ({speed:.1f} chunks/s)",
                style="cyan"
            )

    elapsed = time.time() - start_time

    # ========================================================================
    # MOSTRAR RESULTADOS
    # ========================================================================

    console.print("\n[bold]2. Resultados:[/bold]\n")

    # Tabla de estadísticas
    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Métrica", style="cyan")
    table.add_column("Valor", style="green")

    table.add_row("Total de mensajes", f"{stats.total_messages:,}")
    table.add_row("Total de chunks", f"{chunk_count:,}")
    table.add_row("Tiempo total", f"{elapsed:.2f}s")
    table.add_row("Velocidad", f"{stats.total_messages / elapsed:,.0f} msg/s")

    console.print(Panel(table, title="[bold]Estadísticas Generales[/bold]"))

    # Clientes
    console.print("\n[bold cyan]👥 Clientes:[/bold cyan]")
    client_table = Table(show_header=True, header_style="bold")
    client_table.add_column("Cliente", style="cyan")
    client_table.add_column("Mensajes", justify="right", style="green")

    for client, count in stats.client_counts.most_common(10):
        client_table.add_row(str(client), f"{count:,}")

    console.print(Panel(client_table, title=f"[bold]Top 10 Clientes[/bold]"))

    # Operadores
    console.print("\n[bold cyan]📱 Operadores:[/bold cyan]")
    operator_table = Table(show_header=True, header_style="bold")
    operator_table.add_column("Operador", style="cyan")
    operator_table.add_column("Mensajes", justify="right", style="green")

    for operator, count in stats.operator_counts.most_common(10):
        operator_table.add_row(str(operator), f"{count:,}")

    console.print(Panel(operator_table, title=f"[bold]Operadores[/bold]"))

    # Prioridades
    console.print("\n[bold cyan]🎯 Prioridades:[/bold cyan]")
    priority_table = Table(show_header=True, header_style="bold")
    priority_table.add_column("Prioridad", style="cyan")
    priority_table.add_column("Mensajes", justify="right", style="green")

    for priority, count in stats.priority_counts.most_common():
        priority_table.add_row(str(priority), f"{count:,}")

    console.print(Panel(priority_table, title=f"[bold]Distribución de Prioridades[/bold]"))

    # Resumen final
    console.print("\n[bold cyan]📊 Resumen:[/bold cyan]")
    summary = f"""
[green]✅ Lectura completada exitosamente[/green]

📊 Datos procesados:
   • Total de mensajes: [bold]{stats.total_messages:,}[/bold]
   • Número de chunks: [bold]{chunk_count}[/bold]
   • Teléfonos únicos: [bold]{len(stats.unique_phones):,}[/bold]
   • Clientes únicos: [bold]{len(stats.client_counts)}[/bold]
   • Operadores únicos: [bold]{len(stats.operator_counts)}[/bold]

⏱️ Rendimiento:
   • Tiempo total: [bold]{elapsed:.2f}s[/bold]
   • Velocidad: [bold]{stats.total_messages / elapsed:,.0f}[/bold] msg/s
   • Memoria: [bold]~200 MB[/bold] pico (estimado)

📅 Rango de fechas:
   • Primera: {stats.min_timestamp}
   • Última: {stats.max_timestamp}
"""

    console.print(Panel(summary, title="[bold]Resultado Final[/bold]", style="green"))

    console.print("\n" + "=" * 70)
    console.print("[bold green]🎉 STAGE DATA READER COMPLETADO[/bold green]")
    console.print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
