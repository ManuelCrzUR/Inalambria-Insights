#!/usr/bin/env python3
"""
test_classifier_10.py - Clasificar 10 plantillas frecuentes y mostrar resultados
"""

import asyncio
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from config import settings
from pipeline.stages.classifier import (
    HeterogeneousPanel,
    Arbiter,
    ClassifierStage,
    ClassificationStore,
)
from pipeline.core.io_utils import iter_jsonl
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

console = Console()

async def test_10_templates():
    """Clasifica 10 plantillas y muestra resultados detallados"""

    # Validar API key
    if not settings.OPENAI_API_KEY:
        console.print("[red]Error: OPENAI_API_KEY no está configurada[/red]")
        return

    console.print(Panel("[bold cyan]TEST: Clasificador con 10 Plantillas[/bold cyan]"))
    console.print(f"[cyan]Modelos configurados:[/cyan]")
    console.print(f"  • Panel 1: {settings.MODEL_PANEL_1}")
    console.print(f"  • Panel 2: {settings.MODEL_PANEL_2}")
    console.print(f"  • Arbiter: {settings.MODEL_ARBITER}\n")

    # Cargar taxonomía
    try:
        with open(settings.TAXONOMY_PATH, 'r', encoding='utf-8') as f:
            taxonomy = json.load(f)
        console.print(f"[green]✓ Taxonomía cargada: {len(taxonomy['labels'])} etiquetas[/green]\n")
    except Exception as e:
        console.print(f"[red]✗ Error cargando taxonomía: {e}[/red]")
        return

    # Leer 10 plantillas frecuentes
    templates_input = Path("output/2026-04-24/templates_with_placeholders.jsonl")

    console.print(f"[cyan]Leyendo plantillas de: {templates_input}[/cyan]")

    # Contar frecuencias primero
    templates_dict = defaultdict(int)
    count = 0
    for obj in iter_jsonl(templates_input):
        template_text = obj.get("template_text")
        if template_text:
            templates_dict[template_text] += 1
        count += 1
        if count >= 5000000:  # Limitar lectura para acelerar
            break

    # Filtrar solo frecuentes (>1) y tomar primeros 10
    frequent_templates = [
        {"template_text": t, "frequency": f}
        for t, f in sorted(templates_dict.items(), key=lambda x: x[1], reverse=True)
        if f > 1
    ][:10]

    console.print(f"[green]✓ Plantillas frecuentes encontradas (primeras 10)[/green]\n")

    # Mostrar plantillas a clasificar
    table_input = Table(title="Plantillas a Clasificar")
    table_input.add_column("ID", style="cyan")
    table_input.add_column("Frequency", style="magenta")
    table_input.add_column("Template", style="yellow")

    for i, t in enumerate(frequent_templates, 1):
        template_short = (t["template_text"][:60] + "...") if len(t["template_text"]) > 60 else t["template_text"]
        table_input.add_row(str(i), str(t["frequency"]), template_short)

    console.print(table_input)
    console.print()

    # Inicializar componentes
    console.print("[cyan]Inicializando Panel, Arbiter, Store...[/cyan]")
    panel = HeterogeneousPanel(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)
    arbiter = Arbiter(api_key=settings.OPENAI_API_KEY, taxonomy_data=taxonomy)
    output_path = Path("output/2026-04-28/test_10_classifications.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    store = ClassificationStore(output_path)

    classifier_stage = ClassifierStage(
        panel=panel,
        arbiter=arbiter,
        store=store,
        agreement_threshold=0.7,
        concurrency=2,  # Menos concurrencia para 10 templates
    )
    console.print("[green]✓ Componentes inicializados\n[/green]")

    # Crear async iterator de plantillas
    async def template_iterator():
        for i, t_dict in enumerate(frequent_templates, 1):
            yield {
                "template_id": None,
                "template_text": t_dict["template_text"],
                "applied_rules": [],
                "client_name": "Test",
                "frequency": t_dict["frequency"],
            }

    # Estadísticas
    stats = {
        "total": 0,
        "panel_agreement": 0,
        "arbiter": 0,
        "human_review": 0,
        "errors": 0,
        "labels": defaultdict(int),
        "categories": defaultdict(int),
        "results": [],
    }

    console.print("[cyan]Clasificando plantillas...\n[/cyan]")

    # Clasificar
    async for result in classifier_stage.classify_stream(template_iterator()):
        stats["total"] += 1
        stats["labels"][result.label] += 1
        stats["categories"][result.category] += 1
        stats["results"].append(result)

        if result.level_used == "panel_agreement":
            stats["panel_agreement"] += 1
        elif result.level_used == "arbiter":
            stats["arbiter"] += 1
        elif result.level_used == "human_review":
            stats["human_review"] += 1
        elif result.level_used == "error":
            stats["errors"] += 1

        # Mostrar cada resultado conforme se procesa
        console.print(f"\n[bold]#{stats['total']}[/bold]")
        console.print(f"  Template: {result.template_text[:70]}...")
        console.print(f"  [cyan]Label:[/cyan] {result.label}")
        console.print(f"  [cyan]Category:[/cyan] {result.category}")
        console.print(f"  [cyan]Confidence:[/cyan] {result.confidence:.2f}")
        console.print(f"  [cyan]Level Used:[/cyan] {result.level_used}")

        if result.level_used == "panel_agreement":
            console.print(f"  [green]✓ Panel agreement (Mini: {result.panel_judge_1}, Nano: {result.panel_judge_2})[/green]")
        elif result.level_used == "arbiter":
            console.print(f"  [yellow]→ Arbiter resolved ({result.panel_judge_1} vs {result.panel_judge_2})[/yellow]")
        elif result.level_used == "human_review":
            console.print(f"  [red]⚠ Needs human review[/red]")

    # Resumen final
    console.print("\n" + "="*70)
    console.print(Panel("[bold cyan]RESUMEN[/bold cyan]"))

    summary_table = Table(title="Estadísticas de Clasificación")
    summary_table.add_column("Métrica", style="cyan")
    summary_table.add_column("Valor", style="green")

    summary_table.add_row("Total clasificadas", str(stats["total"]))
    summary_table.add_row(
        "Panel agreement",
        f"{stats['panel_agreement']} ({100*stats['panel_agreement']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Arbiter resueltos",
        f"{stats['arbiter']} ({100*stats['arbiter']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Human review",
        f"{stats['human_review']} ({100*stats['human_review']/max(stats['total'],1):.1f}%)"
    )
    summary_table.add_row(
        "Errores",
        f"{stats['errors']} ({100*stats['errors']/max(stats['total'],1):.1f}%)"
    )

    console.print(summary_table)

    # Top labels
    console.print("\n")
    top_labels_table = Table(title="Etiquetas Asignadas")
    top_labels_table.add_column("Etiqueta", style="cyan")
    top_labels_table.add_column("Cantidad", style="green")
    top_labels_table.add_column("Porcentaje", style="yellow")

    for label, count in sorted(stats["labels"].items(), key=lambda x: x[1], reverse=True):
        pct = (count / stats["total"]) * 100
        top_labels_table.add_row(label, str(count), f"{pct:.1f}%")

    console.print(top_labels_table)

    # Guardar resultados en JSON para inspección
    console.print(f"\n[green]✓ Resultados guardados en: {output_path}[/green]")
    console.print(f"[green]✓ Total de líneas en JSONL: {stats['total']}[/green]")

    # Mostrar contenido del JSONL
    console.print("\n" + "="*70)
    console.print("[bold cyan]CONTENIDO DEL JSONL (primeros 3 resultados)[/bold cyan]\n")

    with open(output_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i >= 3:
                break
            data = json.loads(line.strip())
            console.print(f"[bold]Resultado #{i+1}:[/bold]")
            console.print(json.dumps(data, indent=2, ensure_ascii=False)[:300] + "...")
            console.print()

if __name__ == "__main__":
    asyncio.run(test_10_templates())
