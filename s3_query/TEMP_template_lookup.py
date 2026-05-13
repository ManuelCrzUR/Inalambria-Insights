"""
TEMP_template_lookup.py - Carga CSV de clasificaciones de plantillas

Lee all_rule_classifications.csv y construye un dict para lookups rápidos.
~300k filas × ~150 bytes ≈ 45MB en RAM (manejable).
"""

import pandas as pd
from pathlib import Path
from typing import Dict, Optional


def load_classifications(csv_path: str | Path) -> Dict[str, Dict]:
    """
    Lee CSV de clasificaciones → dict {template_id: {categoria, subcategoria, label, ...}}

    El CSV debe tener columnas:
    - 'ID Plantilla' o 'id_plantilla': identificador único (se convierte a string)
    - 'Categoría' o 'categoria': categoría principal
    - 'Subcategoría' o 'subcategoria': subcategoría
    - 'Etiqueta' o 'etiqueta': label corto (opcional)

    Args:
        csv_path: Ruta al CSV (str o Path)

    Returns:
        Dict donde key=template_id (str) y value={categoria, subcategoria, label, ...}

    Raises:
        FileNotFoundError: Si el CSV no existe
        KeyError: Si faltan columnas requeridas
    """
    csv_path = Path(csv_path)
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV no encontrado: {csv_path}")

    df = pd.read_csv(csv_path, encoding="utf-8")

    # Normalizar nombres de columnas a minúsculas para robustez
    df.columns = df.columns.str.lower().str.replace(" ", "_")

    # Identificar columnas clave (con o sin espacio)
    required_cols = {"id_plantilla", "categoría", "subcategoría"}

    # Buscar variaciones
    id_col = None
    for col in df.columns:
        if "id" in col and "plantilla" in col:
            id_col = col
            break
    if not id_col:
        raise KeyError("No encontrada columna 'ID Plantilla'")

    cat_col = None
    for col in df.columns:
        if "categoría" in col or "categoria" in col:
            cat_col = col
            break
    if not cat_col:
        raise KeyError("No encontrada columna 'Categoría'")

    subcat_col = None
    for col in df.columns:
        if "subcategoría" in col or "subcategoria" in col:
            subcat_col = col
            break
    if not subcat_col:
        raise KeyError("No encontrada columna 'Subcategoría'")

    # Columnas opcionales
    label_col = None
    for col in df.columns:
        if "etiqueta" in col or "label" in col:
            label_col = col
            break

    # Construir dict
    lookup = {}
    for _, row in df.iterrows():
        template_id = str(row[id_col])
        lookup[template_id] = {
            "categoria": row[cat_col],
            "subcategoria": row[subcat_col],
            "label": row[label_col] if label_col else None,
        }

    return lookup


def get_category_info(
    template_id: str, lookup: Dict[str, Dict], default: Optional[Dict] = None
) -> Dict:
    """
    Busca categoría/subcategoría para un template_id.

    Args:
        template_id: ID de template (string)
        lookup: Dict retornado por load_classifications()
        default: Dict default si template_id no está en lookup

    Returns:
        Dict {categoria, subcategoria, label} o default
    """
    if default is None:
        default = {"categoria": "unknown", "subcategoria": "unknown", "label": None}

    return lookup.get(template_id, default)
