"""
settings.py - Configuración centralizada del pipeline

Todas las rutas y parámetros se definen aquí.
Para personalizar, crea un archivo .env en la raíz del proyecto.

Uso:
    from config.settings import DATA_DIR, CHUNK_SIZE
"""

from pathlib import Path
import os

# Directorio raíz del proyecto (dos niveles arriba de este archivo)
BASE_DIR = Path(__file__).parent.parent

# ============================================================
# RUTAS
# ============================================================

DATA_DIR = Path(os.getenv("DATA_DIR", BASE_DIR / "data"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", BASE_DIR / "output"))
PARQUET_PATH = DATA_DIR / os.getenv("PARQUET_FILENAME", "sms.parquet")

# ============================================================
# LOGGING
# ============================================================

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = OUTPUT_DIR / "pipeline.log"

# ============================================================
# RENDIMIENTO
# ============================================================

CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "50000"))
MAX_MEMORY_MB = int(os.getenv("MAX_MEMORY_MB", "500"))

# ============================================================
# PIPELINE
# ============================================================

# Filtrar solo mensajes entregados (StatusId=3)
DELIVERED_ONLY = os.getenv("DELIVERED_ONLY", "true").lower() == "true"

# Umbral Redis: apariciones mínimas para promover a caché
REDIS_THRESHOLD = int(os.getenv("REDIS_THRESHOLD", "50"))

# Días máximos de inactividad para mantener en Redis
REDIS_TTL_DAYS = int(os.getenv("REDIS_TTL_DAYS", "90"))
