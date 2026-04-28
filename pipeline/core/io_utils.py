"""
io_utils.py - Utilidades de I/O para el pipeline

Funciones reutilizables para lectura/escritura de archivos (JSONL, etc.)
"""

import json
from pathlib import Path
from typing import Iterator, Any


def iter_jsonl(path: Path) -> Iterator[dict]:
    """
    Itera un archivo JSONL línea por línea.

    Salta líneas vacías. Si una línea es JSON inválido, la saltea con warning.

    Args:
        path: Path al archivo JSONL

    Yields:
        dict: cada línea deserializada como JSON

    Raises:
        FileNotFoundError: si el archivo no existe
    """
    if not path.exists():
        raise FileNotFoundError(f"Archivo JSONL no encontrado: {path}")

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                yield json.loads(line)
            except json.JSONDecodeError as e:
                import warnings
                warnings.warn(
                    f"Línea {line_num} en {path} es JSON inválido, la saltamos. "
                    f"Error: {e}"
                )


def read_jsonl(path: Path) -> list[dict]:
    """
    Lee todo un archivo JSONL en memoria.

    Args:
        path: Path al archivo JSONL

    Returns:
        list[dict]: todas las líneas deserializadas

    Raises:
        FileNotFoundError: si el archivo no existe
    """
    return list(iter_jsonl(path))
