#!/usr/bin/env python3
"""
run_stage_classifier.py - Script standalone para clasificar plantillas con LLM

Clasifica un archivo JSONL de plantillas únicas usando el panel heterogéneo
(gpt-4o-mini + gpt-5-nano) y el árbitro (gpt-5.4).

Flujo:
1. Carga taxonomía desde config/taxonomy.json
2. Inicializa panel, árbitro, store, orquestador
3. Lee template_ids ya procesados (resume)
4. Itera input JSONL, salta templates ya clasificados
5. Clasifica en paralelo con límite de concurrencia
6. Persiste en output JSONL append-only
7. Reporta estadísticas finales (distribución de labels, % acuerdo, etc.)

Uso:
    python scripts/run_stage_classifier.py \\
        --input output/2026-04-24/unique_templates.jsonl \\
        --output output/2026-04-24/classifications.jsonl \\
        --limit 100 \\
        --concurrency 5 \\
        --threshold 0.7

Env vars:
    OPENAI_API_KEY: requerida para llamadas a OpenAI
    MODEL_PANEL_1, MODEL_PANEL_2, MODEL_ARBITER: overrides de modelos
    CLASSIFIER_AGREEMENT_THRESHOLD: threshold de acuerdo del panel
"""

import asyncio
import json
import argparse
import sys
from pathlib import Path
from collections import defaultdict
from typing import Optional

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel

# Añade la raíz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings
from pipeline.core.io_utils import iter_jsonl
from pipeline.core.models import ClassificationResult
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
    except json.JSONDecodeError as e:
        console.print(f"[red]Error: Taxonomía JSON inválida: {e}[/red]")
        sys.exit(1)


async def classify_templates(
    input_path: Path,
    output_path: Path,
    limit: Optional[int] = None,
    concurrency: int = 10,
    threshold: float = 0.7,
) -> None:
    """
    Clasifica plantillas del input JSONL y persiste en output JSONL.

    Args:
        input_path: path a unique_templates.jsonl
        output_path: path al classifications.jsonl (salida)
        limit: máximo de templates a clasificar (None = sin límite)
        concurrency: llamadas LLM paralelas simultáneas
        threshold: confidence mínima para acuerdo del panel
    """

    # Validar API key
    if not settings.OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no está configurada[/red]")
        sys.exit(1)

    # Cargar taxonomía
    console.print("[cyan]Cargando taxonomía...[/cyan]")
    taxonomy = load_taxonomy(settings.TAXONOMY_PATH)
    console.print(f"[green]✓ Taxonomía cargada: {len(taxonomy['labels'])} etiquetas[/green]")

    # Inicializar componentes
    console.print("[cyan]Inicializando panel, árbitro, store...[/cyan]")
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

    # Cargar IDs ya procesados (resume)
    console.print("[cyan]Verificando templates ya procesados...[/cyan]")
    processed_ids = await store.load_processed_ids()
    console.print(f"[green]✓ {len(processed_ids)} templates ya clasificados[/green]")

    # Leer input JSONL, filtrar ya procesados, aplicar límite
    console.print(f"[cyan]Leyendo {input_path}...[/cyan]")
    try:
        all_templates = list(iter_jsonl(input_path))
    except FileNotFoundError:
        console.print(f"[red]Error: Input JSONL no encontrado: {input_path}[/red]")
        sys.exit(1)

    # Filtrar templates ya procesados
    pending_templates = [
        t for t in all_templates
        if t.get("template_id") not in processed_ids
    ]

    # Aplicar límite
    if limit is not None:
        pending_templates = pending_templates[:limit]

    total_to_classify = len(pending_templates)
    console.print(
        f"[green]✓ {total_to_classify} nuevos templates a clasificar "
        f"(de {len(all_templates)} totales)[/green]"
    )

    if total_to_classify == 0:
        console.print("[yellow]No hay nuevos templates para clasificar.[/yellow]")
        return

    # Crear async iterator de templates
    async def template_iterator():
        for template in pending_templates:
            yield template

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
            "[cyan]Clasificando...", total=total_to_classify
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

    summary_table.add_row("Templates clasificados", str(stats["total"]))
    summary_table.add_row("Acuerdo panel", f"{stats['panel_agreement']} ({100*stats['panel_agreement']/max(stats['total'],1):.1f}%)")
    summary_table.add_row("Árbitro intervino", f"{stats['arbiter']} ({100*stats['arbiter']/max(stats['total'],1):.1f}%)")
    summary_table.add_row("Revisión humana", f"{stats['human_review']} ({100*stats['human_review']/max(stats['total'],1):.1f}%)")
    summary_table.add_row("Errores", f"{stats['errors']} ({100*stats['errors']/max(stats['total'],1):.1f}%)")

    console.print(summary_table)

    # Top etiquetas
    console.print("\n")
    top_labels_table = Table(title="Top 10 Etiquetas Más Frecuentes")
    top_labels_table.add_column("Etiqueta", style="cyan")
    top_labels_table.add_column("Frecuencia", style="green")

    for label, count in sorted(stats["labels"].items(), key=lambda x: x[1], reverse=True)[:10]:
        top_labels_table.add_row(label, str(count))

    console.print(top_labels_table)

    # Top categorías
    console.print("\n")
    top_cats_table = Table(title="Top 10 Categorías Más Frecuentes")
    top_cats_table.add_column("Categoría", style="cyan")
    top_cats_table.add_column("Frecuencia", style="green")

    for cat, count in sorted(stats["categories"].items(), key=lambda x: x[1], reverse=True)[:10]:
        top_cats_table.add_row(cat, str(count))

    console.print(top_cats_table)

    console.print(f"\n[green]✓ Resultados guardados en: {output_path}[/green]")


def main():
    parser = argparse.ArgumentParser(
        description="Clasificar plantillas de SMS con panel LLM + árbitro"
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Path al JSONL de plantillas únicas (ej: output/2026-04-24/unique_templates.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Path al JSONL de salida (ej: output/2026-04-24/classifications.jsonl). "
        "Default: mismo directorio que input, nombre 'classifications.jsonl'",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Máximo número de templates a clasificar (None = todos)",
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

    # Derivar output path si no se proporciona
    if args.output is None:
        args.output = args.input.parent / "classifications.jsonl"

    console.print(
        Panel(
            f"[bold cyan]Clasificador LLM - Panel + Árbitro[/bold cyan]\n"
            f"Input:       {args.input}\n"
            f"Output:      {args.output}\n"
            f"Limit:       {args.limit or 'Sin límite'}\n"
            f"Concurrency: {args.concurrency}\n"
            f"Threshold:   {args.threshold}",
            title="[bold]Configuración[/bold]",
        )
    )

    # Ejecutar clasificación
    asyncio.run(
        classify_templates(
            input_path=args.input,
            output_path=args.output,
            limit=args.limit,
            concurrency=args.concurrency,
            threshold=args.threshold,
        )
    )


if __name__ == "__main__":
    main()
