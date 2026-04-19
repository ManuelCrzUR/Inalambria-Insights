#!/usr/bin/env python3
"""
run_stage_text_normalizer.py - Ejecuta SOLO la etapa de normalización de texto

1. Lee el parquet
2. Normaliza cada mensaje (lowercase, strip, espacios)
3. Muestra estadísticas de normalización

Uso:
    python3 run_stage_text_normalizer.py
"""

import sys
import time
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.layout import Layout

sys.path.insert(0, '/home/manuel-cruz/Desktop/Twnel/prod_pipeline')

from pipeline.core.data_reader import iter_parquet_chunks
from pipeline.core.text_normalizer import TextNormalizer
from pipeline.monitor.progress_ui_live import PipelineLiveUI


def main():
    console = Console()

    parquet_path = "/home/manuel-cruz/Desktop/Twnel/Diciembre2025-20260330T205027Z-1-003/Diciembre2025/day=15/SmsData_2025_12_15.parquet"

    console.print(Panel(
        "[bold cyan]🔧 TEXT NORMALIZER STAGE[/bold cyan]\n"
        "Normaliza mensajes SMS:\n"
        "  • Lowercase\n"
        "  • Strip espacios inicio/final\n"
        "  • Normalizar espacios múltiples",
        title="[bold]Stage de Normalización[/bold]"
    ))

    # ========================================================================
    # LEER + NORMALIZAR CON INTERFAZ EN VIVO
    # ========================================================================

    console.print("\n[bold]1. Leyendo y normalizando parquet...[/bold]\n")
    time.sleep(1)

    ui = PipelineLiveUI()
    normalizer = TextNormalizer()

    # Layout para Live UI
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="phase", size=8),
        Layout(name="completed", size=3),
        Layout(name="info", size=3),
    )

    # Variables de tracking
    all_data = []
    total_chunks = 1394
    chunk_num = 0
    normalized_data = []
    processed = 0

    with Live(layout, refresh_per_second=4) as live:
        # Subfase: Lectura
        for chunk in iter_parquet_chunks(parquet_path, delivered_only=True, verbose=False):
            chunk_num += 1
            all_data.append(chunk)

            if chunk_num % 100 == 0:
                ui.update_phase(
                    "📖 Lectura del Parquet",
                    processed=chunk_num,
                    total=total_chunks,
                    **{"Rows/chunk": len(chunk)}
                )
                layout["header"].update(ui._render_header())
                layout["phase"].update(ui._render_current_phase())
                layout["completed"].update(ui._render_completed_phases())
                layout["info"].update(ui._render_info())

        ui.complete_phase()
        time.sleep(1)

        # Subfase: Normalización
        total_messages = sum(len(c) for c in all_data)

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
                            **{"Chunk": f"{chunk_idx + 1}/1394"}
                        )
                        layout["header"].update(ui._render_header())
                        layout["phase"].update(ui._render_current_phase())
                        layout["completed"].update(ui._render_completed_phases())
                        layout["info"].update(ui._render_info())

                df["NormalizedMessage"] = normalized_messages
            normalized_data.append(df)

        ui.complete_phase()
        time.sleep(1)

        # Última actualización
        layout["header"].update(ui._render_header())
        layout["phase"].update(ui._render_current_phase())
        layout["completed"].update(ui._render_completed_phases())
        layout["info"].update(ui._render_info())
        time.sleep(1)

    # ========================================================================
    # ANÁLISIS DE NORMALIZACIÓN
    # ========================================================================

    console.print("\n[bold]2. Analizando resultados...[/bold]\n")
    time.sleep(1)

    # Recopilar estadísticas de normalización
    total_normalized = sum(len(c) for c in normalized_data)
    original_chars = 0
    normalized_chars = 0
    samples_changed = 0
    max_length_original = 0
    max_length_normalized = 0

    for chunk in normalized_data:
        if "Message" in chunk.columns and "NormalizedMessage" in chunk.columns:
            original = chunk["Message"].fillna("")
            normalized = chunk["NormalizedMessage"].fillna("")

            original_chars += original.str.len().sum()
            normalized_chars += normalized.str.len().sum()
            samples_changed += (original != normalized).sum()
            max_length_original = max(max_length_original, original.str.len().max())
            max_length_normalized = max(max_length_normalized, normalized.str.len().max())

    # Mostrar estadísticas
    console.print("[bold cyan]📊 Estadísticas de Normalización:[/bold cyan]\n")

    stats_table = Table(show_header=True, header_style="bold magenta")
    stats_table.add_column("Métrica", style="cyan")
    stats_table.add_column("Valor", style="green")

    stats_table.add_row("Total de mensajes normalizados", f"{total_normalized:,}")
    stats_table.add_row("Mensajes modificados", f"{samples_changed:,}")
    stats_table.add_row("% de mensajes modificados", f"{100 * samples_changed / total_normalized:.1f}%")
    stats_table.add_row("Total caracteres (original)", f"{original_chars:,}")
    stats_table.add_row("Total caracteres (normalizado)", f"{normalized_chars:,}")
    stats_table.add_row("Caracteres removidos", f"{original_chars - normalized_chars:,}")
    stats_table.add_row("Largo máximo original", f"{max_length_original}")
    stats_table.add_row("Largo máximo normalizado", f"{max_length_normalized}")

    console.print(Panel(stats_table, title="[bold]Detalles de Normalización[/bold]"))

    # Ejemplos
    console.print("\n[bold cyan]💡 Ejemplos de Normalización:[/bold cyan]\n")

    examples_shown = 0
    for chunk in normalized_data:
        if "Message" in chunk.columns and "NormalizedMessage" in chunk.columns:
            for orig, norm in zip(chunk["Message"], chunk["NormalizedMessage"]):
                if orig != norm and examples_shown < 5:
                    console.print(f"  Original:   [yellow]{orig}[/yellow]")
                    console.print(f"  Normalizado: [green]{norm}[/green]\n")
                    examples_shown += 1
            if examples_shown >= 5:
                break

    # Resumen final
    console.print("[bold cyan]✅ Resumen de la Normalización:[/bold cyan]")
    summary = f"""
[green]✅ Normalización completada exitosamente[/green]

📊 Datos procesados:
   • Total de mensajes: [bold]{total_normalized:,}[/bold]
   • Mensajes modificados: [bold]{samples_changed:,}[/bold] ({100 * samples_changed / total_normalized:.1f}%)
   • Caracteres eliminados: [bold]{original_chars - normalized_chars:,}[/bold]

📏 Longitud de mensajes:
   • Original (máx): [bold]{max_length_original}[/bold] caracteres
   • Normalizado (máx): [bold]{max_length_normalized}[/bold] caracteres

🔧 Operaciones aplicadas:
   ✓ Lowercase conversion
   ✓ Trim espacios inicio/final
   ✓ Normalizar espacios múltiples
"""

    console.print(Panel(summary, title="[bold]Resultado Final[/bold]", style="green"))

    console.print("\n" + "=" * 70)
    console.print("[bold green]🎉 STAGE TEXT NORMALIZER COMPLETADO[/bold green]")
    console.print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
