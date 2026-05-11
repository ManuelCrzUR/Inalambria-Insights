#!/usr/bin/env python3
"""
export_all_classifications.py - Exporta TODAS las clasificaciones L0 con label válido

Genera CSV y HTML con cada plantilla clasificada, ordenadas por frecuencia.

Uso:
    python3 scripts/export_all_classifications.py 2026-05-10
    python3 scripts/export_all_classifications.py 2026-05-10 --csv
    python3 scripts/export_all_classifications.py 2026-05-10 --html
"""

import sys
import json
import argparse
import csv
from pathlib import Path
from datetime import datetime


def export_all_classifications(output_date: str, output_dir: Path = None):
    """Exporta TODAS las clasificaciones con label válido."""

    if output_dir is None:
        output_dir = Path("/home/manuel-cruz/Desktop/Twnel/prod_pipeline/output") / output_date

    rule_classifications_path = output_dir / "rule_classifications.jsonl"

    if not rule_classifications_path.exists():
        print(f"❌ Archivo no encontrado: {rule_classifications_path}")
        return None

    classifications = []
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

                classifications.append({
                    'template_id': result.get('template_id', ''),
                    'template_text': result.get('template_text', ''),
                    'label': result.get('label', ''),
                    'category': result.get('category', ''),
                    'subcategory': result.get('subcategory', ''),
                    'frequency': result.get('frequency', 1),
                    'confidence': result.get('confidence', 0.0),
                    'rule_name': result.get('metadata', {}).get('rule_name', ''),
                    'applied_rules': ', '.join(result.get('applied_rules', [])),
                })

                if total_lines % 500000 == 0:
                    print(f"  ✓ Procesados {total_lines:,} líneas...")

            except json.JSONDecodeError as e:
                print(f"⚠️  Error JSON en línea {total_lines}: {e}")
                continue

    print(f"\n✅ Análisis completado:")
    print(f"   Total de líneas: {total_lines:,}")
    print(f"   Con label válido: {valid_lines:,}")
    print(f"   Sin label (skipped): {skipped_lines:,}")

    # Ordenar por frecuencia descendente
    classifications_sorted = sorted(classifications, key=lambda x: x['frequency'], reverse=True)

    return classifications_sorted, output_dir


def generate_csv(classifications, output_dir: Path):
    """Genera CSV con TODAS las clasificaciones."""
    csv_path = output_dir / "all_rule_classifications.csv"

    print(f"\n📝 Generando CSV: {csv_path}")
    print(f"   Escribiendo {len(classifications):,} registros...")

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'ID Plantilla',
            'Plantilla (Template)',
            'Etiqueta (Label)',
            'Categoría',
            'Subcategoría',
            'Regla Usada',
            'Frecuencia',
            'Confianza',
            'Reglas Aplicadas (Regex)'
        ])

        for data in classifications:
            writer.writerow([
                data['template_id'],
                data['template_text'],
                data['label'],
                data['category'],
                data['subcategory'],
                data['rule_name'],
                data['frequency'],
                f"{data['confidence']:.2f}",
                data['applied_rules'],
            ])

    print(f"✅ CSV guardado en: {csv_path}")
    return csv_path


def generate_html(classifications, output_dir: Path):
    """Genera HTML interactivo con TODAS las clasificaciones."""
    html_path = output_dir / "all_rule_classifications.html"

    print(f"📊 Generando HTML: {html_path}")
    print(f"   Escribiendo {len(classifications):,} registros...")

    total_frequency = sum(data['frequency'] for data in classifications)

    html_content = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Todas las Clasificaciones L0</title>
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
            max-width: 1400px;
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

        .controls {{
            padding: 20px;
            background: #f8f9fa;
            border-bottom: 1px solid #e0e0e0;
            display: flex;
            gap: 20px;
            align-items: center;
            flex-wrap: wrap;
        }}

        .search-box {{
            flex: 1;
            min-width: 250px;
        }}

        .search-box input {{
            width: 100%;
            padding: 10px 15px;
            border: 1px solid #ddd;
            border-radius: 6px;
            font-size: 1em;
        }}

        .search-box input:focus {{
            outline: none;
            border-color: #667eea;
            box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
        }}

        .stats {{
            display: flex;
            gap: 20px;
            flex-wrap: wrap;
        }}

        .stat {{
            padding: 10px 15px;
            background: white;
            border-radius: 6px;
            border-left: 4px solid #667eea;
        }}

        .stat-label {{
            font-size: 0.85em;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .stat-value {{
            font-size: 1.4em;
            font-weight: bold;
            color: #333;
        }}

        .table-container {{
            padding: 20px;
            overflow-x: auto;
            max-height: 80vh;
            overflow-y: auto;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.93em;
        }}

        thead {{
            background: #f8f9fa;
            border-bottom: 2px solid #667eea;
            position: sticky;
            top: 0;
            z-index: 10;
        }}

        thead th {{
            padding: 12px 15px;
            text-align: left;
            font-weight: 600;
            color: #333;
            text-transform: uppercase;
            font-size: 0.8em;
            letter-spacing: 0.5px;
            white-space: nowrap;
        }}

        tbody td {{
            padding: 10px 15px;
            border-bottom: 1px solid #e0e0e0;
            color: #555;
        }}

        tbody tr:hover {{
            background: #f8f9fa;
        }}

        .template-text {{
            font-family: "Monaco", "Courier New", monospace;
            font-size: 0.9em;
            background: #f5f5f5;
            padding: 8px 12px;
            border-radius: 4px;
            max-width: 400px;
            word-break: break-word;
            color: #333;
        }}

        .label {{
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            background: #e3f2fd;
            color: #1565c0;
        }}

        .frequency {{
            font-weight: bold;
            color: #667eea;
        }}

        .confidence {{
            display: inline-block;
            padding: 4px 8px;
            background: #f3e5f5;
            color: #6a1b9a;
            border-radius: 4px;
            font-weight: 600;
        }}

        .rule-name {{
            font-size: 0.9em;
            color: #666;
            font-style: italic;
        }}

        footer {{
            padding: 20px;
            text-align: center;
            color: #999;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            font-size: 0.9em;
        }}

        .info-box {{
            margin: 15px 0;
            padding: 15px;
            background: #e3f2fd;
            border-left: 4px solid #1976d2;
            border-radius: 4px;
            color: #0d47a1;
        }}

        @media (max-width: 768px) {{
            header h1 {{
                font-size: 1.8em;
            }}

            .controls {{
                flex-direction: column;
                align-items: stretch;
            }}

            .search-box {{
                min-width: 100%;
            }}

            .stats {{
                flex-direction: column;
            }}

            table {{
                font-size: 0.85em;
            }}

            thead th, tbody td {{
                padding: 8px;
            }}

            .template-text {{
                max-width: 250px;
                font-size: 0.85em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>📋 Todas las Clasificaciones L0</h1>
            <p>Plantillas individuales clasificadas con reglas • Ordenadas por Frecuencia</p>
        </header>

        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="🔍 Buscar por plantilla, etiqueta o regla...">
            </div>
            <div class="stats">
                <div class="stat">
                    <div class="stat-label">Total Registros</div>
                    <div class="stat-value">{len(classifications):,}</div>
                </div>
                <div class="stat">
                    <div class="stat-label">Frecuencia Total</div>
                    <div class="stat-value">{total_frequency:,}</div>
                </div>
            </div>
        </div>

        <div class="info-box">
            💡 <strong>Tip:</strong> Usa el buscador para filtrar por etiqueta (ej: "banking"), regla (ej: "banking_otp") o texto de plantilla
        </div>

        <div class="table-container">
            <table id="dataTable">
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Plantilla (Template)</th>
                        <th>Etiqueta</th>
                        <th>Categoría</th>
                        <th>Subcategoría</th>
                        <th>Regla</th>
                        <th style="text-align: right;">Frecuencia</th>
                        <th style="text-align: center;">Confianza</th>
                    </tr>
                </thead>
                <tbody id="tableBody">
"""

    for idx, data in enumerate(classifications, 1):
        html_content += f"""                    <tr class="data-row" data-template="{data['template_text'].lower()}" data-label="{data['label'].lower()}" data-rule="{data['rule_name'].lower()}">
                        <td>{idx}</td>
                        <td><div class="template-text">{data['template_text']}</div></td>
                        <td><span class="label">{data['label']}</span></td>
                        <td>{data['category']}</td>
                        <td>{data['subcategory']}</td>
                        <td><span class="rule-name">{data['rule_name']}</span></td>
                        <td style="text-align: right;"><span class="frequency">{data['frequency']:,}</span></td>
                        <td style="text-align: center;"><span class="confidence">{data['confidence']:.2f}</span></td>
                    </tr>
"""

    html_content += f"""                </tbody>
            </table>
        </div>

        <footer>
            <p>Generado automáticamente por export_all_classifications.py</p>
            <p style="margin-top: 10px;">📊 Total de plantillas clasificadas con L0: {len(classifications):,}</p>
        </footer>
    </div>

    <script>
        // Búsqueda en tiempo real
        const searchInput = document.getElementById('searchInput');
        const tableRows = document.querySelectorAll('.data-row');

        searchInput.addEventListener('keyup', function() {{
            const searchTerm = this.value.toLowerCase();

            tableRows.forEach(row => {{
                const template = row.getAttribute('data-template');
                const label = row.getAttribute('data-label');
                const rule = row.getAttribute('data-rule');

                const matches = template.includes(searchTerm) ||
                               label.includes(searchTerm) ||
                               rule.includes(searchTerm);

                row.style.display = matches ? '' : 'none';
            }});

            // Actualizar contador
            const visibleRows = Array.from(tableRows).filter(row => row.style.display !== 'none');
            console.log(`Mostrando ${{visibleRows.length}} de ${{tableRows.length}} registros`);
        }});
    </script>
</body>
</html>
"""

    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"✅ HTML guardado en: {html_path}")
    return html_path


def main():
    parser = argparse.ArgumentParser(
        description="Exporta TODAS las clasificaciones L0 (solo labels válidos)"
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
    print(f"📋 Exportando TODAS las clasificaciones L0")
    print(f"{'='*70}\n")

    result = export_all_classifications(args.output_date)

    if result is None:
        return 1

    classifications, output_dir = result

    if not classifications:
        print("\n⚠️  No hay clasificaciones con label válido.")
        return 1

    print(f"\n📋 Primeras 5 plantillas clasificadas:")
    for idx, data in enumerate(classifications[:5], 1):
        print(f"  {idx}. {data['template_text'][:60]:60s} → {data['label']}")

    # Generar archivos
    if generate_both or args.csv:
        generate_csv(classifications, output_dir)

    if generate_both or args.html:
        generate_html(classifications, output_dir)

    print(f"\n✅ Exportación completada exitosamente!\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
