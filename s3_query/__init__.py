"""
s3_query - Módulo para scoring de teléfonos vía DuckDB + S3

Conjunto de utilidades para consultar datos de SMS de S3 sin descargas masivas,
usando DuckDB con la extensión httpfs y hive partition pushdown.

Componentes:
  - TEMP_s3_scanner.py: Consulta S3 con DuckDB, retorna DataFrames
  - TEMP_template_lookup.py: Carga CSV de clasificaciones
  - TEMP_aggregator.py: Agrega mensajes → JSON de scoring
  - TEMP_phone_scorer.py: Orquesta todo
"""

# Imports condicionales para permitir testing sin duckdb
try:
    from .TEMP_s3_scanner import scan_messages
except ImportError:
    scan_messages = None

try:
    from .TEMP_template_lookup import load_classifications
except ImportError:
    load_classifications = None

try:
    from .TEMP_phone_scorer import score_phones
except ImportError:
    score_phones = None

__all__ = [
    "scan_messages",
    "load_classifications",
    "score_phones",
]
