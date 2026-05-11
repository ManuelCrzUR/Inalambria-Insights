#!/usr/bin/env python3
"""
analyze_rule_classifications.py - Analiza resultados de clasificación L0

Genera CSV y HTML con resultados ordenados por frecuencia (descendente).
Solo incluye clasificaciones que tienen label no vacío.

Uso:
    python3 scripts/analyze_rule_classifications.py 2026-05-10
    python3 scripts/analyze_rule_classifications.py 2026-05-10 --html
    python3 scripts/analyze_rule_classifications.py 2026-05-10 --csv
"""

import sys
import json
import argparse
import csv
from pathlib import Path
from collections import defaultdict
from datetime import datetime


def analyze_classifications(output_date: str, output_dir: Path = None):
    """Analiza resultados de clasificación L0 con label no vacío."""

    if output_dir is None:
        output_dir = Path("/home/manuel-cruz/Desktop/Twnel/prod_pipeline/output") / output_date

    rule_classifications_path = output_dir / "rule_classifications.jsonl"

    if not rule_classifications_path.exists():
        print(f"❌ Archivo no encontrado: {rule_classifications_path}")
        return None

    # Agregar resultados por label única
    classifications = defaultdict(lambda: {
        'label': '',
        'category': '',
        'subcategory': '',
        'rule_name': '',
        'frequency': 0,
        'confidence': 0.0,
        'count': 0,  # Cuántas plantillas únicas
    })

    total_lines = 0
    valid_lines = 0
    skipped_lines = 0

    print(f"📖 Leyendo {rule_classifications_path}...")

    with open(rule_classifications_path, 'r', encoding='utf-8') as f:
        for line in f:
            total_lines += 1

            try:
                result = json.loads(line)

                # Solo incluir si tiene label no vacío
                if not result.get('label') or result['label'].strip() == '':
                    skipped_lines += 1
                    continue

                valid_lines += 1
                label = result['label']

                # Acumular datos
                classifications[label]['label'] = result['label']
                classifications[label]['category'] = result.get('category', '')
                classifications[label]['subcategory'] = result.get('subcategory', '')
                classifications[label]['frequency'] += result.get('frequency', 1)
                classifications[label]['rule_name'] = result.get('metadata', {}).get('rule_name', '')
                classifications[label]['confidence'] = result.get('confidence', 0.0)
                classifications[label]['count'] += 1

                if total_lines % 500000 == 0:
                    print(f"  ✓ Procesados {total_lines:,} líneas...")

            except json.JSONDecodeError as e:
                print(f"⚠️  Error JSON en línea {total_lines}: {e}")
                continue

    print(f"\n✅ Análisis completado:")
    print(f"   Total de líneas: {total_lines:,}")
    print(f"   Con label válido: {valid_lines:,}")
    print(f"   Sin label (skipped): {skipped_lines:,}")
    print(f"   Labels únicos: {len(classifications):,}")

    # Ordenar por frecuencia descendente
    sorted_classifications = sorted(
        classifications.items(),
        key=lambda x: x[1]['frequency'],
        reverse=True
    )

    return sorted_classifications, output_dir


def generate_csv(sorted_classifications, output_dir: Path):
    """Genera CSV con resultados."""
    csv_path = output_dir / "rule_classifications_report.csv"

    print(f"\n📝 Generando CSV: {csv_path}")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Rango',
            'Etiqueta (label)',
            'Categoría',
            'Subcategoría',
            'Regla Usada',
            'Frecuencia Total',
            'Plantillas Únicas',
            'Confianza Promedio'
        ])

        for idx, (label, data) in enumerate(sorted_classifications, 1):
            avg_confidence = data['confidence']
            writer.writerow([
                idx,
                data['label'],
                data['category'],
                data['subcategory'],
                data['rule_name'],
                data['frequency'],
                data['count'],
                f"{avg_confidence:.2f}"
            ])

    print(f"✅ CSV guardado en: {csv_path}")
    return csv_path


def generate_html(sorted_classifications, output_dir: Path):
    """Genera HTML interactivo con resultados."""
    html_path = output_dir / "rule_classifications_report.html"

    print(f"📊 Generando HTML: {html_path}")

    total_frequency = sum(data['frequency'] for _, data in sorted_classifications)
    total_plantillas = sum(data['count'] for _, data in sorted_classifications)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Resultados Clasificación L0 - Reglas</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 40px 20px;
            text-align: center;
        }}

        header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        header p {{
            font-size: 1.1em;
            opacity: 0.9;
        }}

        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            padding: 30px 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
        }}

        .stat-box {{
            text-align: center;
            padding: 20px;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .stat-box h3 {{
            color: #667eea;
            font-size: 0.9em;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }}

        .stat-box .value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}

        .table-container {{
            padding: 30px 20px;
            overflow-x: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.95em;
        }}

        thead {{
            background: #f8f9fa;
            border-bottom: 2px solid #667eea;
        }}

        thead th {{
            padding: 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            text-transform: uppercase;
            font-size: 0.85em;
            letter-spacing: 0.5px;
        }}

        tbody td {{
            padding: 12px 15px;
            border-bottom: 1px solid #e0e0e0;
            color: #555;
        }}

        tbody tr:hover {{
            background: #f8f9fa;
        }}

        tbody tr:nth-child(odd) {{
            background: #fafbfc;
        }}

        .rank {{
            font-weight: bold;
            color: #667eea;
            min-width: 50px;
        }}

        .label {{
            font-weight: 600;
            color: #333;
        }}

        .bar-container {{
            background: #e0e0e0;
            border-radius: 4px;
            height: 20px;
            overflow: hidden;
            position: relative;
        }}

        .bar {{
            background: linear-gradient(90deg, #667eea, #764ba2);
            height: 100%;
            border-radius: 4px;
            display: flex;
            align-items: center;
            justify-content: flex-end;
            padding-right: 5px;
            color: white;
            font-size: 0.8em;
            font-weight: bold;
        }}

        .confidence {{
            display: inline-block;
            padding: 4px 8px;
            background: #e3f2fd;
            color: #1565c0;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.9em;
        }}

        footer {{
            padding: 20px;
            text-align: center;
            color: #999;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            font-size: 0.9em;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            .stats {{
                grid-template-columns: 1fr;
                gap: 10px;
            }}

            table {{
                font-size: 0.85em;
            }}

            thead th, tbody td {{
                padding: 10px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📊 Resultados Clasificación L0 (Reglas)</h1>
            <p>Pipeline SMS - Day 15 • Ordenado por Frecuencia (Descendente)</p>
        </header>

        <div class="stats">
            <div class="stat-box">
                <h3>📋 Labels Únicos</h3>
                <div class="value">{len(sorted_classifications):,}</div>
            </div>
            <div class="stat-box">
                <h3>📈 Frecuencia Total</h3>
                <div class="value">{total_frequency:,}</div>
            </div>
            <div class="stat-box">
                <h3>🎯 Plantillas Únicas</h3>
                <div class="value">{total_plantillas:,}</div>
            </div>
            <div class="stat-box">
                <h3>⏱️ Generado</h3>
                <div class="value">{datetime.now().strftime('%H:%M:%S')}</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Etiqueta (Label)</th>
                        <th>Categoría</th>
                        <th>Subcategoría</th>
                        <th>Regla Usada</th>
                        <th style="text-align: center;">Frecuencia</th>
                        <th style="text-align: center;">% Distribución</th>
                        <th style="text-align: center;">Plantillas</th>
                        <th style="text-align: center;">Confianza</th>
                    </tr>
                </thead>
                <tbody>
"""

    for idx, (label, data) in enumerate(sorted_classifications, 1):
        pct = (data['frequency'] / total_frequency * 100) if total_frequency > 0 else 0

        html_content += f"""                    <tr>
                        <td class="rank">{idx}</td>
                        <td class="label">{data['label']}</td>
                        <td>{data['category']}</td>
                        <td>{data['subcategory']}</td>
                        <td>{data['rule_name']}</td>
                        <td style="text-align: right; font-weight: bold;">{data['frequency']:,}</td>
                        <td style="text-align: center;">
                            <div class="bar-container">
                                <div class="bar" style="width: {pct}%;">{pct:.1f}%</div>
                            </div>
                        </td>
                        <td style="text-align: right;">{data['count']:,}</td>
                        <td style="text-align: center;">
                            <span class="confidence">{data['confidence']:.2f}</span>
                        </td>
                    </tr>
"""

    html_content += """                </tbody>
            </table>
        </div>

        <footer>
            <p>Generado automáticamente por analyze_rule_classifications.py</p>
            <p style="margin-top: 10px; opacity: 0.7;">Solo se incluyen clasificaciones con label no vacío</p>
        </footer>
    </div>
</body>
</html>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ HTML guardado en: {html_path}")
    return html_path


def main():
    parser = argparse.ArgumentParser(
        description="Analiza resultados de clasificación L0 (solo labels válidos)"
    )
    parser.add_argument(
        'output_date',
        help='Fecha del output (ej: 2026-05-10)'
    )
    parser.add_argument(
        '--csv',
        action='store_true',
        help='Generar solo CSV'
    )
    parser.add_argument(
        '--html',
        action='store_true',
        help='Generar solo HTML'
    )
    parser.add_argument(
        '--both',
        action='store_true',
        help='Generar ambos (default si no se especifica)'
    )

    args = parser.parse_args()

    # Si no especifica formato, generar ambos
    generate_both = args.both or (not args.csv and not args.html)

    print(f"\n{'='*70}")
    print(f"📊 Analizando clasificaciones L0")
    print(f"{'='*70}\n")

    result = analyze_classifications(args.output_date)

    if result is None:
        return 1

    sorted_classifications, output_dir = result

    if not sorted_classifications:
        print("\n⚠️  No hay clasificaciones con label válido.")
        return 1

    print(f"\n📊 Top 10 por Frecuencia:")
    for idx, (label, data) in enumerate(sorted_classifications[:10], 1):
        print(f"  {idx:2d}. {data['label']:40s} → {data['frequency']:10,} ({data['count']:,} plantillas)")

    # Generar archivos
    if generate_both or args.csv:
        generate_csv(sorted_classifications, output_dir)

    if generate_both or args.html:
        generate_html(sorted_classifications, output_dir)

    print(f"\n✅ Análisis completado exitosamente!\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
