"""
database.py - Configuración de base de datos SQL

Centraliza:
- Conexión a BD local (SQLite) o remota (PostgreSQL)
- Schema SQL (tabla, índices, constraints)
- Inicialización y migraciones
- Logging de queries (debug)

Diseño:
- SQLite local (default) para desarrollo/testing
- PostgreSQL remote (configurable) para producción
- Esquema idéntico en ambos (migraciones genéricas)
- Compilación de DDL una sola vez a nivel de módulo
"""

import sqlite3
import asyncio
import logging
from pathlib import Path
from typing import Optional
from enum import Enum

logger = logging.getLogger(__name__)


class DatabaseType(Enum):
    """Tipos de base de datos soportados."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


# ============================================================================
# SCHEMA SQL (genérico, funciona en SQLite y PostgreSQL)
# ============================================================================

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS classified_templates (
    -- Identificación de la plantilla
    template_id         TEXT PRIMARY KEY,
    template_text       TEXT NOT NULL,

    -- Clasificación final
    label               TEXT NOT NULL,
    category            TEXT NOT NULL,
    subcategory         TEXT NOT NULL DEFAULT '',
    confidence          REAL NOT NULL DEFAULT 0.0,

    -- Trazabilidad del nivel de clasificación
    level_used          TEXT NOT NULL,
    -- "rule" = RuleClassifier, "panel_agreement" = Panel acuerdo,
    -- "arbiter" = Árbitro, "human_review" = Pendiente revisión humana

    rule_name           TEXT,
    -- Solo cuando level_used = "rule" (nombre de la regla que matcheó)

    -- Metadata del mensaje ORIGINAL (para análisis de comportamiento)
    original_message    TEXT,
    cleaned_message     TEXT,
    client_name         TEXT,
    client_id           INTEGER,
    phone_number        TEXT,
    operator_name       TEXT,
    account_name        TEXT,
    priority_description TEXT,

    -- Votos del Panel LLM (L1)
    panel_judge_1       TEXT,
    panel_judge_1_conf  REAL,
    panel_judge_2       TEXT,
    panel_judge_2_conf  REAL,

    -- Veredicto del Árbitro (L2)
    arbiter_label       TEXT,
    arbiter_reasoning   TEXT,
    arbiter_abstained   INTEGER DEFAULT 0,  -- SQLite no tiene BOOLEAN

    -- Estado y frecuencia
    needs_human_review  INTEGER NOT NULL DEFAULT 0,
    frequency           INTEGER NOT NULL DEFAULT 1,
    applied_rules       TEXT,  -- JSON array serializado

    -- Timestamps (ISO 8601)
    timestamp_original  TEXT,  -- Cuando se envió el mensaje original
    first_seen          TEXT,  -- Primera vez que vimos esta plantilla
    last_seen           TEXT,  -- Última vez que vimos esta plantilla
    classified_at       TEXT NOT NULL  -- Cuando se clasificó

    -- Nota: Sin extra metadata TEXT para mantener performance
    -- Si necesitas más campos, agregar después
);

-- Índices para queries frecuentes (optimización)
CREATE INDEX IF NOT EXISTS idx_label              ON classified_templates(label);
CREATE INDEX IF NOT EXISTS idx_level_used         ON classified_templates(level_used);
CREATE INDEX IF NOT EXISTS idx_category           ON classified_templates(category);
CREATE INDEX IF NOT EXISTS idx_client_name        ON classified_templates(client_name);
CREATE INDEX IF NOT EXISTS idx_needs_review       ON classified_templates(needs_human_review)
    WHERE needs_human_review = 1;
CREATE INDEX IF NOT EXISTS idx_classified_at      ON classified_templates(classified_at);
CREATE INDEX IF NOT EXISTS idx_confidence         ON classified_templates(confidence);

-- Índice compuesto: queries típicas de análisis
CREATE INDEX IF NOT EXISTS idx_level_category     ON classified_templates(level_used, category);
"""


# ============================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# ============================================================================

class DatabaseConfig:
    """Configuración centralizada para la base de datos."""

    def __init__(
        self,
        db_type: DatabaseType = DatabaseType.SQLITE,
        sqlite_path: Optional[Path] = None,
        postgres_url: Optional[str] = None,
        echo_sql: bool = False,
    ):
        """
        Inicializa la configuración.

        Args:
            db_type: SQLITE o POSTGRESQL
            sqlite_path: Ruta al archivo .db (default: ~/.cache/pipeline.db)
            postgres_url: URL de conexión PostgreSQL (env var si no se proporciona)
            echo_sql: True para loguear todas las queries (debug)
        """
        self.db_type = db_type
        self.echo_sql = echo_sql

        if db_type == DatabaseType.SQLITE:
            self.sqlite_path = sqlite_path or (
                Path.home() / ".cache" / "twnel_pipeline" / "pipeline.db"
            )
        else:
            self.postgres_url = postgres_url or "postgresql://user:pass@localhost/pipeline"

    @property
    def connection_string(self) -> str:
        """Retorna el string de conexión apropiado."""
        if self.db_type == DatabaseType.SQLITE:
            return f"sqlite:///{self.sqlite_path}"
        return self.postgres_url


# ============================================================================
# INICIALIZADOR DE BASE DE DATOS
# ============================================================================

class DatabaseInitializer:
    """
    Inicializa y gestiona el schema de la base de datos.

    Responsabilidades:
    - Crear tabla y índices si no existen
    - Validar schema (para migraciones futuras)
    - Logging de operaciones
    """

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self._initialized = False

    async def initialize(self) -> None:
        """
        Crea la tabla y índices si no existen.

        Idempotente: es seguro llamar múltiples veces.
        """
        if self._initialized:
            return

        if self.config.db_type == DatabaseType.SQLITE:
            await self._initialize_sqlite()
        else:
            await self._initialize_postgresql()

        self._initialized = True
        logger.info(f"Database initialized: {self.config.db_type.value}")

    async def _initialize_sqlite(self) -> None:
        """Crea schema en SQLite."""
        self.config.sqlite_path.parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.config.sqlite_path)
        try:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
            logger.info(f"SQLite database created at {self.config.sqlite_path}")
        finally:
            conn.close()

    async def _initialize_postgresql(self) -> None:
        """Crea schema en PostgreSQL (stub para implementación futura)."""
        # TODO: Implementar cuando necesitemos soporte PostgreSQL
        logger.warning("PostgreSQL initialization not yet implemented")
        raise NotImplementedError("PostgreSQL support coming soon")

    @staticmethod
    def get_default_config(local: bool = True) -> DatabaseConfig:
        """
        Retorna la configuración por defecto.

        Args:
            local: True para SQLite local, False para PostgreSQL remota
        """
        return DatabaseConfig(
            db_type=DatabaseType.SQLITE if local else DatabaseType.POSTGRESQL,
        )
