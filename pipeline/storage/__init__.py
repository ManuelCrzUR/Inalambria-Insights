"""Storage - Persistencia y lectura de datos

Módulos:
- pipeline_storage.py: JSONL append-only (clasificaciones)
- database.py: Configuración SQL, schema, inicialización
- sql_template_store.py: Persistencia SQL con metadata
"""

from pipeline.storage.pipeline_storage import PipelineStorage
from pipeline.storage.database import DatabaseConfig, DatabaseType, DatabaseInitializer
from pipeline.storage.sql_template_store import SQLTemplateStore, TemplateMetadata

__all__ = [
    "PipelineStorage",
    "DatabaseConfig",
    "DatabaseType",
    "DatabaseInitializer",
    "SQLTemplateStore",
    "TemplateMetadata",
]
