"""
sql_template_store.py - Persistencia SQL de resultados clasificados

Responsabilidades:
- Guardar ClassificationResult en SQL con trazabilidad
- Mantener metadata del mensaje original
- Soporte para consultas y análisis
- Idempotencia (no duplicar registros)

Diseño:
- Insert or ignore: si template_id ya existe, no sobrescribe
- Async operations con asyncio.Lock para concurrencia
- Compilación de statements una sola vez
- Logging de cada operación (para auditoría)

Uso:
    store = SQLTemplateStore(config=db_config)
    await store.initialize()
    await store.upsert(classification_result, template_metadata)

    # Análisis
    results = await store.query_by_level("rule")
    low_conf = await store.query_by_confidence_range(0.0, 0.7)
"""

import sqlite3
import json
import asyncio
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import asdict
from datetime import datetime

from pipeline.core.models import ClassificationResult
from pipeline.storage.database import DatabaseConfig, DatabaseInitializer

logger = logging.getLogger(__name__)


# ============================================================================
# SQL STATEMENTS (compilados una sola vez)
# ============================================================================

INSERT_OR_IGNORE = """
INSERT OR IGNORE INTO classified_templates (
    template_id,
    template_text,
    label,
    category,
    subcategory,
    confidence,
    level_used,
    rule_name,
    original_message,
    cleaned_message,
    client_name,
    client_id,
    phone_number,
    operator_name,
    account_name,
    priority_description,
    panel_judge_1,
    panel_judge_1_conf,
    panel_judge_2,
    panel_judge_2_conf,
    arbiter_label,
    arbiter_reasoning,
    arbiter_abstained,
    needs_human_review,
    frequency,
    applied_rules,
    timestamp_original,
    first_seen,
    last_seen,
    classified_at
) VALUES (
    ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?, ?, ?,
    ?, ?, ?, ?, ?, ?
)
"""

UPDATE_FREQUENCY = """
UPDATE classified_templates
SET frequency = frequency + 1,
    last_seen = ?
WHERE template_id = ?
"""

SELECT_BY_ID = "SELECT * FROM classified_templates WHERE template_id = ?"

SELECT_BY_LEVEL = """
SELECT * FROM classified_templates
WHERE level_used = ?
ORDER BY classified_at DESC
"""

SELECT_BY_CONFIDENCE = """
SELECT * FROM classified_templates
WHERE confidence >= ? AND confidence <= ?
ORDER BY confidence ASC
"""

SELECT_BY_CLIENT = """
SELECT * FROM classified_templates
WHERE client_name = ?
ORDER BY classified_at DESC
"""

SELECT_NEEDING_REVIEW = """
SELECT * FROM classified_templates
WHERE needs_human_review = 1
ORDER BY classified_at DESC
"""

COUNT_BY_LEVEL = """
SELECT level_used, COUNT(*) as count, AVG(confidence) as avg_confidence
FROM classified_templates
GROUP BY level_used
"""


# ============================================================================
# TEMPLATE METADATA DTO
# ============================================================================

class TemplateMetadata:
    """
    Contiene metadata del mensaje original (opcional).

    Se pasa a SQLTemplateStore.upsert() para guardar información
    adicional sin modificar ClassificationResult.
    """

    def __init__(
        self,
        original_message: Optional[str] = None,
        cleaned_message: Optional[str] = None,
        client_name: Optional[str] = None,
        client_id: Optional[int] = None,
        phone_number: Optional[str] = None,
        operator_name: Optional[str] = None,
        account_name: Optional[str] = None,
        priority_description: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ):
        self.original_message = original_message
        self.cleaned_message = cleaned_message
        self.client_name = client_name
        self.client_id = client_id
        self.phone_number = phone_number
        self.operator_name = operator_name
        self.account_name = account_name
        self.priority_description = priority_description
        self.timestamp = timestamp

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a dict para fácil acceso."""
        return asdict(self)


# ============================================================================
# SQL TEMPLATE STORE
# ============================================================================

class SQLTemplateStore:
    """
    Almacenamiento SQL de clasificaciones con metadata del mensaje original.

    Patrón:
    1. Initialize(): crea tabla e índices
    2. upsert(): inserta o ignora (INSERT OR IGNORE idempotente)
    3. update_frequency(): incrementa contador de apariciones
    4. query_*(): consultas para análisis y debugging

    Thread-safe con asyncio.Lock.
    """

    def __init__(self, config: Optional[DatabaseConfig] = None):
        """
        Inicializa el store.

        Args:
            config: DatabaseConfig (default: SQLite local ~/.cache/)
        """
        self.config = config or DatabaseConfig()
        self.initializer = DatabaseInitializer(self.config)
        self.lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Crea tabla e índices. Idempotente."""
        if self._initialized:
            return
        await self.initializer.initialize()
        self._initialized = True

    def _get_connection(self) -> sqlite3.Connection:
        """Abre conexión a SQLite. Usa sqlite3.Row para fácil acceso."""
        if self.config.db_type.value != "sqlite":
            raise NotImplementedError("Solo SQLite es soportado ahora")

        conn = sqlite3.connect(self.config.sqlite_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def upsert(
        self,
        result: ClassificationResult,
        metadata: Optional[TemplateMetadata] = None,
    ) -> bool:
        """
        Inserta un resultado de clasificación con metadata del mensaje.

        INSERT OR IGNORE: si template_id ya existe, no lo sobrescribe.
        Esto es correcto porque:
        - La clasificación por reglas (L0) es determinística
        - La clasificación por LLM es costosa, reutilizar es bueno
        - En caso de cambio de regla, se debe usar un template_id distinto

        Args:
            result: ClassificationResult a persistir
            metadata: TemplateMetadata opcional (cliente, mensaje original, etc.)

        Returns:
            True si se insertó nuevo, False si ya existía (skip)
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    INSERT_OR_IGNORE,
                    (
                        result.template_id,
                        result.template_text,
                        result.label,
                        result.category,
                        result.subcategory,
                        result.confidence,
                        result.level_used,
                        result.metadata.get("rule_name"),
                        metadata.original_message if metadata else None,
                        metadata.cleaned_message if metadata else None,
                        metadata.client_name if metadata else None,
                        metadata.client_id if metadata else None,
                        metadata.phone_number if metadata else None,
                        metadata.operator_name if metadata else None,
                        metadata.account_name if metadata else None,
                        metadata.priority_description if metadata else None,
                        result.panel_judge_1,
                        result.panel_judge_1_conf,
                        result.panel_judge_2,
                        result.panel_judge_2_conf,
                        result.arbiter_label,
                        result.arbiter_reasoning,
                        int(result.arbiter_abstained) if result.arbiter_abstained else 0,
                        int(result.needs_human_review),
                        result.frequency,
                        json.dumps(result.applied_rules, ensure_ascii=False),
                        metadata.timestamp.isoformat() if metadata and metadata.timestamp else None,
                        result.classified_at,  # first_seen
                        result.classified_at,  # last_seen (actualiza con update_frequency)
                        result.classified_at,
                    ),
                )
                conn.commit()
                inserted = cursor.rowcount > 0

                if inserted:
                    logger.debug(
                        f"Inserted {result.template_id} "
                        f"({result.category}::{result.subcategory}, "
                        f"level={result.level_used})"
                    )
                else:
                    logger.debug(f"Skipped {result.template_id} (already exists)")

                return inserted

            finally:
                conn.close()

    async def update_frequency(
        self, template_id: str, last_seen: str
    ) -> bool:
        """
        Incrementa el contador de apariciones de una plantilla.

        Llamar en re-procesos para actualizar frecuencia sin duplicar.

        Args:
            template_id: template_id a actualizar
            last_seen: ISO string de la última vez que vimos esta plantilla

        Returns:
            True si se actualizó, False si no existía
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                cursor = conn.execute(
                    UPDATE_FREQUENCY,
                    (last_seen, template_id),
                )
                conn.commit()
                updated = cursor.rowcount > 0

                if updated:
                    logger.debug(f"Updated frequency for {template_id}")

                return updated

            finally:
                conn.close()

    async def get(self, template_id: str) -> Optional[Dict]:
        """
        Retorna un registro completo por template_id.

        Returns:
            Dict con todos los campos o None si no existe
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                row = conn.execute(SELECT_BY_ID, (template_id,)).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    async def query_by_level(self, level: str, limit: int = 100) -> List[Dict]:
        """
        Obtiene resultados por nivel de clasificación.

        Args:
            level: "rule" | "panel_agreement" | "arbiter" | "human_review"
            limit: máximo de resultados

        Returns:
            Lista de dicts ordenados por classified_at DESC
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    f"{SELECT_BY_LEVEL} LIMIT {limit}",
                    (level,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def query_by_confidence(
        self, min_conf: float = 0.0, max_conf: float = 1.0, limit: int = 100
    ) -> List[Dict]:
        """
        Obtiene resultados en un rango de confianza.

        Útil para encontrar casos de baja confianza que necesitan revisión.

        Args:
            min_conf: confianza mínima (default: 0.0)
            max_conf: confianza máxima (default: 1.0)
            limit: máximo de resultados

        Returns:
            Lista de dicts ordenados por confidence ASC
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    f"{SELECT_BY_CONFIDENCE} LIMIT {limit}",
                    (min_conf, max_conf),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def query_by_client(self, client_name: str, limit: int = 100) -> List[Dict]:
        """
        Obtiene resultados para un cliente específico.

        Útil para análisis por cliente/comportamiento de la API.

        Args:
            client_name: nombre del cliente
            limit: máximo de resultados

        Returns:
            Lista de dicts ordenados por classified_at DESC
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    f"{SELECT_BY_CLIENT} LIMIT {limit}",
                    (client_name,),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def query_needing_review(self, limit: int = 100) -> List[Dict]:
        """
        Obtiene plantillas que necesitan revisión humana.

        Típicamente: arbiter se abstuvo (ABSTAIN) o confianza muy baja.

        Args:
            limit: máximo de resultados

        Returns:
            Lista de dicts ordenados por classified_at DESC
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(
                    f"{SELECT_NEEDING_REVIEW} LIMIT {limit}",
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def stats_by_level(self) -> List[Dict]:
        """
        Estadísticas agregadas por nivel de clasificación.

        Retorna count y avg_confidence por level_used.
        Útil para medir impacto del L0 RuleClassifier.

        Returns:
            [
                {"level_used": "rule", "count": 500, "avg_confidence": 0.99},
                {"level_used": "panel_agreement", "count": 300, "avg_confidence": 0.88},
                ...
            ]
        """
        async with self.lock:
            conn = self._get_connection()
            try:
                rows = conn.execute(COUNT_BY_LEVEL).fetchall()
                return [dict(row) for row in rows]
            finally:
                conn.close()

    async def export_csv(self, output_path: Path, limit: int = 10000) -> int:
        """
        Exporta registros a CSV para análisis externo.

        Args:
            output_path: dónde guardar el CSV
            limit: máximo de registros a exportar

        Returns:
            Número de registros exportados
        """
        try:
            import pandas as pd
        except ImportError:
            logger.error("pandas required for CSV export: pip install pandas")
            return 0

        async with self.lock:
            conn = self._get_connection()
            try:
                df = pd.read_sql_query(
                    f"SELECT * FROM classified_templates LIMIT {limit}",
                    conn,
                )
                df.to_csv(output_path, index=False)
                logger.info(f"Exported {len(df)} rows to {output_path}")
                return len(df)
            finally:
                conn.close()
