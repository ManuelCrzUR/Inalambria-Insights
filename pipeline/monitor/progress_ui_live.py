"""
progress_ui_live.py - Interfaz visual MEJORADA con Live (actualización en tiempo real)

UNA sola pantalla que se actualiza sin scroll.
Usa Rich.Live para mantener el contenido en el mismo lugar.

Flujo:
1. FASE 1: Leer parquet (% en vivo)
2. FASE 2: Normalizar (% en vivo)
3. FASE 3: Extraer plantillas (% en vivo)
"""

from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from rich.layout import Layout
from rich.live import Live
from datetime import datetime, timedelta


class PipelineLiveUI:
    """
    Interfaz en tiempo real con actualización sin scroll.

    Mantiene UNA sola pantalla que se actualiza en vivo.
    """

    def __init__(self):
        self.console = Console()
        self.current_phase = None
        self.phase_progress = 0
        self.phase_total = 0
        self.start_time = datetime.now()

        # Histórico de fases completadas
        self.completed_phases = []

    def update_phase(self, phase_name: str, processed: int, total: int, **info) -> None:
        """Actualiza la fase actual"""
        self.current_phase = phase_name
        self.phase_progress = processed
        self.phase_total = total
        self.phase_info = info

    def complete_phase(self) -> None:
        """Marca la fase actual como completada"""
        if self.current_phase:
            self.completed_phases.append(self.current_phase)
            elapsed = (datetime.now() - self.start_time).total_seconds()
            self.current_phase = None

    def _render_header(self) -> Panel:
        """Header con título y tiempo transcurrido"""
        elapsed = (datetime.now() - self.start_time).total_seconds()
        title = "[bold cyan]🚀 Pipeline SMS[/bold cyan]"
        subtitle = f"⏱️  {elapsed:.1f}s"
        return Panel(
            Text(subtitle, justify="right"),
            title=title,
            style="blue"
        )

    def _render_current_phase(self) -> Panel:
        """Renderiza la fase actual con barra de progreso"""
        if not self.current_phase:
            return Panel(
                "[green]✅ Completado[/green]",
                title="[bold]Estado[/bold]"
            )

        # Calcular porcentaje
        if self.phase_total == 0:
            percentage = 0
        else:
            percentage = (self.phase_progress / self.phase_total) * 100

        # Barra visual
        bar_length = 40
        filled = int((percentage / 100) * bar_length)
        bar = "█" * filled + "░" * (bar_length - filled)

        # Color dinámico
        if percentage < 33:
            color = "red"
        elif percentage < 66:
            color = "yellow"
        else:
            color = "green"

        progress_text = f"[{color}]{bar}[/{color}] {percentage:.1f}%"

        # Información adicional
        info_lines = [progress_text]

        if self.phase_total > 0:
            info_lines.append(
                f"[cyan]{self.phase_progress:,} / {self.phase_total:,}[/cyan]"
            )

        # Velocidad y ETA
        elapsed = (datetime.now() - self.start_time).total_seconds()
        if elapsed > 0 and self.phase_progress > 0:
            speed = self.phase_progress / elapsed
            remaining = self.phase_total - self.phase_progress
            eta_seconds = remaining / speed if speed > 0 else 0

            info_lines.append(
                f"[yellow]Velocidad:[/yellow] {speed:,.0f} items/s | "
                f"[yellow]ETA:[/yellow] {int(eta_seconds // 60)}:{int(eta_seconds % 60):02d}"
            )

        content = "\n".join(info_lines)
        return Panel(
            content,
            title=f"[bold]{self.current_phase}[/bold]"
        )

    def _render_completed_phases(self) -> Panel:
        """Renderiza fases completadas"""
        if not self.completed_phases:
            return Panel(
                "[dim]Esperando...[/dim]",
                title="[bold]Fases Completadas[/bold]"
            )

        content = "\n".join(
            f"[green]✅ {phase}[/green]"
            for phase in self.completed_phases
        )
        return Panel(content, title="[bold]Completadas[/bold]")

    def _render_info(self) -> Panel:
        """Renderiza información adicional de la fase"""
        if not hasattr(self, 'phase_info') or not self.phase_info:
            return Panel(
                "[dim]—[/dim]",
                title="[bold]Info[/bold]"
            )

        info_lines = []
        for key, value in self.phase_info.items():
            info_lines.append(f"{key}: {value}")

        content = "\n".join(info_lines)
        return Panel(content, title="[bold]Info[/bold]")

    def render(self) -> Panel:
        """Renderiza el layout completo"""
        return Panel(
            "\n".join([
                str(self._render_header()),
                str(self._render_current_phase()),
                str(self._render_completed_phases()),
                str(self._render_info()),
            ]),
            style="blue"
        )

    def show_live(self, update_callback) -> None:
        """
        Muestra la interfaz en vivo con actualizaciones.

        Args:
            update_callback: Función que actualiza el estado.
                            Debe retornar False cuando termina.
        """
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=3),
            Layout(name="phase", size=8),
            Layout(name="completed", size=3),
            Layout(name="info", size=3),
        )

        with Live(layout, refresh_per_second=4, console=self.console) as live:
            while True:
                # Actualizar estado
                should_continue = update_callback()
                if not should_continue:
                    break

                # Renderizar componentes
                layout["header"].update(self._render_header())
                layout["phase"].update(self._render_current_phase())
                layout["completed"].update(self._render_completed_phases())
                layout["info"].update(self._render_info())

    def show_summary(
        self,
        unique_templates: int = 0,
        unique_pure_messages: int = 0,
        total_messages: int = 0,
    ) -> None:
        """
        Muestra resumen final con estadísticas opcionales del análisis.

        Args:
            unique_templates: Plantillas únicas detectadas (con placeholders).
            unique_pure_messages: Mensajes únicos sin placeholders.
            total_messages: Total de mensajes procesados.
        """
        self.console.clear()

        elapsed = (datetime.now() - self.start_time).total_seconds()

        summary_text = f"""
[green]✅ PIPELINE COMPLETADO[/green]

[bold]Resumen:[/bold]
  Tiempo total: {elapsed:.2f}s
  Fases: {len(self.completed_phases)}
"""

        # Agregar estadísticas si se proporcionan
        if total_messages > 0:
            summary_text += f"""
[bold cyan]📊 Resultados del Análisis:[/bold cyan]
  🎯 Plantillas únicas (con placeholders): {unique_templates:,}
  📝 Mensajes únicos (texto puro):         {unique_pure_messages:,}
  📬 Total procesados:                     {total_messages:,}
"""

        summary_text += "\n[bold]Fases completadas:[/bold]\n"

        for phase in self.completed_phases:
            summary_text += f"  ✅ {phase}\n"

        self.console.print(Panel(
            summary_text,
            style="green",
            title="[bold cyan]Pipeline SMS[/bold cyan]"
        ))
