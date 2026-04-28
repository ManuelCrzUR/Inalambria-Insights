#!/usr/bin/env python3
"""
run_classifier_frequent_templates.py - Clasificar solo plantillas frecuentes

Clasifica SOLO las plantillas que aparecen más de 1 vez en los datos.
Esto representa el 73.54% de los mensajes pero solo el 6.39% de plantillas únicas.

Flujo:
1. Lee templates_with_placeholders.jsonl
2. Cuenta frecuencias de cada plantilla
3. Filtra solo plantillas con frequency > 1
4. Las clasifica con panel + árbitro
5. Guarda resultados en JSONL

Uso:
    python scripts/run_classifier_frequent_templates.py \\
        --output output/2026-04-28/classifications_frequent.jsonl \\
        --concurrency 10 \\
        --threshold 0.7
"""

import asyncio
import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict, Counter

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from pipeline.stages.classifier import (
    HeterogeneousPanel,
    Arbiter,
    ClassifierStage,
    ClassificationStore,
)


console = Console()


def load_taxonomy(taxonomy_path: Path) -> dict:
    """Carga la taxonomía desde JSON."""
    try:
        with open(taxonomy_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        console.print(f"[red]Error: Taxonomía no encontrada en {taxonomy_path}[/red]")
        sys.exit(1)


async def classify_frequent_templates(
    templates_path: Path,
    output_path: Path,
    concurrency: int = 10,
    threshold: float = 0.7,
) -> None:
    """
    Clasifica plantillas frecuentes (frequency > 1).

    Args:
        templates_path: path a templates_with_placeholders.jsonl
        output_path: path al classifications_frequent.jsonl (salida)
        concurrency: llamadas LLM paralelas
        threshold: confidence mínima para acuerdo del panel
    """

    # Validar API key
    if not settings.OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no está configurada[/red]")
        sys.exit(1)

    # Fase 1: Contar frecuencias
    console.print("[cyan]Fase 1/3: Contando frecuencias de plantillas...[/cyan]")
    templates_dict = defaultdict(int)

    with open(templates_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i % 500000 == 0 and i > 0:
                console.print(f"  Procesadas {i:,} líneas...")
            try:
                obj = json.loads(line.strip())
                template_text = obj.get("template_text")
                if template_text:
                    templates_dict[template_text] += 1
            except:
                pass

    # Filtrar solo frequent
    frequent_templates = {
        template: count
        for template, count in templates_dict.items()
        if count > 1
    }

    total_frequent = len(frequent_templates)
    total_messages_frequent = sum(frequent_templates.values())
    total_all_messages = sum(templates_dict.values())

    console.print(f"[green]✓ Plantillas totales: {len(templates_dict):,}[/green]")
    console.print(f"[green]✓ Plantillas frecuentes (>1): {total_frequent:,} ({total_frequent/len(templates_dict)*100:.2f}%)[/green]")
    console.print(f"[green]✓ Mensajes que representan: {total_messages_frequent:,} ({total_messages_frequent/total_all_messages*100:.2f}%)[/green]")

    # Fase 2: Inicializar componentes
    console.print("\n[cyan]Fase 2/3: Inicializando panel, árbitro, store...[/cyan]")

    taxonomy = load_taxonomy(settings.TAXONOMY_PATH)
    panel = HeterogeneousPanel(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)
    arbiter = Arbiter(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = ClassificationStore(output_path)

    classifier_stage = ClassifierStage(
        panel=panel,
        arbiter=arbiter,
        store=store,
        agreement_threshold=threshold,
        concurrency=concurrency,
    )

    # Fase 3: Clasificar
    console.print(f"\n[cyan]Fase 3/3: Clasificando {total_frequent:,} plantillas frecuentes...[/cyan]\n")

    # Crear async iterator de plantillas
    async def template_iterator():
        for template_text, freq in frequent_templates.items():
            yield {
                "template_id": None,  # Se generará durante la clasificación
                "template_text": template_text,
                "applied_rules": [],  # No disponibles aquí
                "client_name": "Unknown",
                "frequency": freq,
            }

    # Estadísticas en vivo
    stats = {
        "total": 0,
        "panel_agreement": 0,
        "arbiter": 0,
        "human_review": 0,
        "errors": 0,
        "labels": defaultdict(int),
        "categories": defaultdict(int),
    }

    # Clasificar con progress bar
    with Progress(
        SpinnerColumn(),
        BarColumn(),
        TaskProgressColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task(
            "[cyan]Clasificando...", total=total_frequent
        )

        async for result in classifier_stage.classify_stream(template_iterator()):
            stats["total"] += 1
            stats["labels"][result.label] += 1
            stats["categories"][result.category] += 1

            if result.level_used == "panel_agreement":
                stats["panel_agreement"] += 1
            elif result.level_used == "arbiter":
                stats["arbiter"] += 1
            elif result.level_used == "human_review":
                stats["human_review"] += 1
            elif result.level_used == "error":
                stats["errors"] += 1

            progress.update(task, advance=1)

    # Reportar estadísticas
    console.print("\n")
    console.print(Panel("[bold cyan]Clasificación Completa[/bold cyan]"))

    summary_table = Table(title="Resumen")
    summary_table.add_column("Métrica", style="cyan")
    summary_table.add_column("Valor", style="green")

    summary_table.add_row("Plantillas clasificadas", str(stats["total"]))
    summary_table.add_row(
        "Acuerdo panel",
        f"{stats['panel_agreement']} ({100*stats['panel_agreement']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Árbitro intervino",
        f"{stats['arbiter']} ({100*stats['arbiter']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Revisión humana",
        f"{stats['human_review']} ({100*stats['human_review']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Errores",
        f"{stats['errors']} ({100*stats['errors']/max(stats['total'],1):.1f}%)"
    )

    console.print(summary_table)

    # Top etiquetas
    console.print("\n")
    top_labels_table = Table(title="Top 15 Etiquetas Más Frecuentes")
    top_labels_table.add_column("Etiqueta", style="cyan")
    top_labels_table.add_column("Frecuencia", style="green")
    top_labels_table.add_column("% de Plantillas", style="yellow")

    for label, count in sorted(stats["labels"].items(), key=lambda x: x[1], reverse=True)[:15]:
        pct = (count / stats["total"]) * 100
        top_labels_table.add_row(label, str(count), f"{pct:.2f}%")

    console.print(top_labels_table)

    # Top categorías
    console.print("\n")
    top_cats_table = Table(title="Top 10 Categorías Más Frecuentes")
    top_cats_table.add_column("Categoría", style="cyan")
    top_cats_table.add_column("Frecuencia", style="green")
    top_cats_table.add_column("% de Plantillas", style="yellow")

    for cat, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True)[:10]:
        pct = (count / stats["total"]) * 100
        top_cats_table.add_row(cat, str(count), f"{pct:.2f}%")

    console.print(top_cats_table)

    # Impacto en mensajes
    console.print("\n")
    impact_panel = Panel(
        f"[bold]Plantillas clasificadas: {stats['total']:,}[/bold]\n"
        f"Representan: [bold green]{total_messages_frequent:,} mensajes[/bold green]\n"
        f"Porcentaje total de mensajes: [bold yellow]{total_messages_frequent/total_all_messages*100:.2f}%[/bold yellow]",
        title="[bold]Impacto en Datos Originales[/bold]"
    )
    console.print(impact_panel)

    console.print(f"\n[green]✓ Resultados guardados en: {output_path}[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Clasificar plantillas frecuentes (frequency > 1) con panel LLM + árbitro"
    )
    parser.add_argument(
        "--templates",
        type=Path,
        default=Path("/home/manuel-cruz/Desktop/Twnel/prod_pipeline/output/2026-04-24/templates_with_placeholders.jsonl"),
        help="Path al JSONL de templates_with_placeholders",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path al JSONL de salida (ej: output/2026-04-28/classifications_frequent.jsonl)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Llamadas LLM paralelas simultáneas (default: 10)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.7,
        help="Confidence mínima para acuerdo del panel (0.0-1.0, default: 0.7)",
    )

    args = parser.parse_args()

    console.print(
        Panel(
            f"[bold cyan]Clasificador LLM - Plantillas Frecuentes[/bold cyan]\n"
            f"Templates: {args.templates}\n"
            f"Output:    {args.output}\n"
            f"Concurrency: {args.concurrency}\n"
            f"Threshold:   {args.threshold}",
            title="[bold]Configuración[/bold]",
        )
    )

    asyncio.run(
        classify_frequent_templates(
            templates_path=args.templates,
            output_path=args.output,
            concurrency=args.concurrency,
            threshold=args.threshold,
        )
    )


if __name__ == "__main__":
    main()
