"""
conftest.py - Fixtures compartidas para todos los tests

pytest carga este archivo automáticamente.
Las fixtures definidas aquí están disponibles en todos los archivos test_*.py
sin necesidad de importarlas.
"""

import pytest
from pathlib import Path

# Directorio raíz del proyecto
ROOT_DIR = Path(__file__).parent.parent

# Directorio de fixtures (datos de prueba)
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_messages():
    """Lista de mensajes SMS de ejemplo para tests."""
    return [
        "Hola, tienes un pago pendiente de $150.000",
        "  Mensaje con espacios extra  ",
        "MENSAJE EN MAYÚSCULAS",
        "Mensaje con   múltiples    espacios",
        "",  # mensaje vacío
    ]


@pytest.fixture
def sample_normalized_messages():
    """Versiones normalizadas esperadas de sample_messages."""
    return [
        "hola, tienes un pago pendiente de $150.000",
        "mensaje con espacios extra",
        "mensaje en mayúsculas",
        "mensaje con múltiples espacios",
        "",
    ]


@pytest.fixture
def fixtures_dir():
    """Ruta al directorio de fixtures."""
    return FIXTURES_DIR


@pytest.fixture
def root_dir():
    """Ruta a la raíz del proyecto."""
    return ROOT_DIR
