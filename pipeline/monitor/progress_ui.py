"""
progress_ui.py - Interfaz visual del pipeline con Rich

Renderiza el progreso en la terminal de forma bonita y colorida.
Actualiza en tiempo real sin scroll (usa Panel con refresh).
"""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .progress_monitor import PipelineMonitor, StageStatus


class PipelineUI:
    """
    Interfaz visual del pipeline con Rich.

    Muestra:
    - Progreso general
    - Estado de cada stage
    - Estadísticas en tiempo real
    - Velocidad de procesamiento
    - ETA
    """

    def __init__(self, monitor: PipelineMonitor):
        self.monitor = monitor
        self.console = Console()

    def render_header(self) -> Panel:
        """Renderiza el header con título"""
        title = "[bold cyan]🚀 Pipeline SMS - Monitor en Tiempo Real[/bold cyan]"
        subtitle = f"Elapsed: {self.monitor.elapsed_seconds:.1f}s"
        return Panel(
            Text(subtitle, justify="right"),
            title=title,
            style="blue",
            expand=True
        )

    def render_overall_progress(self) -> Panel:
        """Renderiza progreso general"""
        percentage = self.monitor.overall_percentage
        bar_length = 30
        filled = int((percentage / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Color dinámico según progreso
        if percentage < 33:
            color = "red"
        elif percentage < 66:
            color = "yellow"
        else:
            color = "green"

        progress_text = f"[{color}]{bar}[/{color}] {percentage:.1f}%"
        return Panel(
            progress_text,
            title="[bold]Progreso General[/bold]",
            expand=True
        )

    def render_stages_table(self) -> Panel:
        """Renderiza tabla de stages con detalles"""
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Stage", style="cyan")
        table.add_column("Estado", justify="center")
        table.add_column("Progreso", justify="center")
        table.add_column("Velocidad", justify="right")
        table.add_column("ETA", justify="right")

        for stage in self.monitor.get_all_stages():
            # Estado con emoji
            status_emoji = {
                StageStatus.PENDING: "⏳",
                StageStatus.RUNNING: "⏳",
                StageStatus.COMPLETED: "✅",
                StageStatus.ERROR: "❌",
                StageStatus.PAUSED: "⏸️ "
            }

            emoji = status_emoji.get(stage.status, "❓")
            status_text = f"{emoji} {stage.status.value}"

            # Barra de progreso
            bar_length = 15
            filled = int((stage.percentage / 100) * bar_length)
            bar = "█" * filled + "░" * (bar_length - filled)
            progress = f"[cyan]{bar}[/cyan] {stage.percentage:.0f}%"

            # Velocidad
            if stage.items_per_second > 0:
                speed_text = f"{stage.items_per_second:,.0f} items/s"
            else:
                speed_text = "—"

            # ETA
            if stage.status == StageStatus.RUNNING:
                eta_text = str(stage.eta_timedelta)
            elif stage.status == StageStatus.COMPLETED:
                elapsed = f"{stage.elapsed_seconds:.1f}s"
                eta_text = f"✅ {elapsed}"
            else:
                eta_text = "—"

            table.add_row(
                stage.name,
                status_text,
                progress,
                speed_text,
                eta_text
            )

        return Panel(
            table,
            title="[bold]Stages del Pipeline[/bold]",
            expand=True
        )

    def render_stats(self) -> Panel:
        """Renderiza estadísticas adicionales"""
        stats = self.monitor.get_summary()

        # Obtener info de cada stage activo
        info_lines = []

        for name, stage in self.monitor.stages.items():
            if stage.status == StageStatus.RUNNING:
                # Información adicional del stage
                if stage.additional_info:
                    for key, value in stage.additional_info.items():
                        info_lines.append(
                            f"[yellow]{name}[/yellow] → {key}: {value}"
                        )

        if not info_lines:
            info_text = "[dim]Esperando datos...[/dim]"
        else:
            info_text = "\n".join(info_lines)

        return Panel(
            info_text,
            title="[bold]Info en Tiempo Real[/bold]",
            expand=True
        )

    def render_errors(self) -> Panel:
        """Renderiza errores si los hay"""
        if not self.monitor.global_errors:
            error_text = "[green]✅ Sin errores[/green]"
            style = "green"
        else:
            error_text = "\n".join(
                f"[red]❌ {error}[/red]"
                for error in self.monitor.global_errors[-5:]  # Últimos 5
            )
            style = "red"

        return Panel(
            error_text,
            title="[bold]Errores[/bold]",
            style=style,
            expand=True
        )

    def display(self) -> None:
        """Muestra el panel completo"""
        # Limpiar pantalla
        self.console.clear()

        # Header
        self.console.print(self.render_header())
        self.console.print()

        # Progreso general
        self.console.print(self.render_overall_progress())
        self.console.print()

        # Tabla de stages
        self.console.print(self.render_stages_table())
        self.console.print()

        # Estadísticas
        self.console.print(self.render_stats())
        self.console.print()

        # Errores
        self.console.print(self.render_errors())

    def display_summary(self) -> None:
        """Muestra resumen final al completar"""
        summary = self.monitor.get_summary()

        self.console.clear()

        # Header
        header = Panel(
            "[bold green]✅ Pipeline Completado[/bold green]",
            style="green"
        )
        self.console.print(header)
        self.console.print()

        # Tabla final
        table = Table(show_header=False)
        table.add_column("Métrica", style="cyan")
        table.add_column("Valor", style="green")

        table.add_row(
            "Tiempo total",
            f"{summary['elapsed_seconds']:.2f}s"
        )

        for name, stage_data in summary["stages"].items():
            table.add_row(
                f"{name}",
                f"✅ {stage_data['processed']} items"
            )

        self.console.print(Panel(table, title="[bold]Resumen Final[/bold]"))
