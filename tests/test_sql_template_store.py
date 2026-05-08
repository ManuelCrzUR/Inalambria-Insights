"""
test_sql_template_store.py - Tests para SQLTemplateStore

Verifica:
1. Inicialización de schema
2. Idempotencia (INSERT OR IGNORE)
3. Metadata del mensaje original
4. Queries y análisis
5. Actualización de frecuencia
"""

import pytest
import pytest_asyncio
import asyncio
import json
from datetime import datetime
from pathlib import Path
import tempfile

from pipeline.core.models import ClassificationResult
from pipeline.storage.database import DatabaseConfig, DatabaseType
from pipeline.storage.sql_template_store import SQLTemplateStore, TemplateMetadata


@pytest.fixture
def temp_db():
    """Crea una BD temporal para tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = DatabaseConfig(
            db_type=DatabaseType.SQLITE,
            sqlite_path=Path(tmpdir) / "test.db",
        )
        yield config


@pytest_asyncio.fixture
async def store(temp_db):
    """Crea un store inicializado para tests."""
    store = SQLTemplateStore(config=temp_db)
    await store.initialize()
    return store


class TestInitialization:
    """Tests de inicialización de schema."""

    @pytest.mark.asyncio
    async def test_initialize_creates_db_file(self, temp_db):
        """La inicialización crea el archivo .db."""
        assert not temp_db.sqlite_path.exists()

        store = SQLTemplateStore(config=temp_db)
        await store.initialize()

        assert temp_db.sqlite_path.exists()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, temp_db):
        """Inicializar múltiples veces es seguro."""
        store = SQLTemplateStore(config=temp_db)
        await store.initialize()
        await store.initialize()  # No error

        assert store._initialized

    @pytest.mark.asyncio
    async def test_table_created_with_indices(self, temp_db):
        """El schema incluye tabla e índices."""
        store = SQLTemplateStore(config=temp_db)
        await store.initialize()

        conn = store._get_connection()
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='classified_templates'"
        )
        assert cursor.fetchone() is not None

        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indices = cursor.fetchall()
        assert len(indices) > 0  # Al menos hay algunos índices

        conn.close()


class TestUpsert:
    """Tests de inserción con idempotencia."""

    @pytest.mark.asyncio
    async def test_upsert_new_record(self, store):
        """Insertar un nuevo registro retorna True."""
        result = ClassificationResult(
            template_id="test001",
            template_text="ingresa [OTP] en [ENTIDAD_BANCARIA]",
            label="banking::otp_2fa",
            category="banking",
            subcategory="otp_2fa",
            confidence=1.0,
            level_used="rule",
        )

        inserted = await store.upsert(result)
        assert inserted is True

    @pytest.mark.asyncio
    async def test_upsert_duplicate_skips(self, store):
        """Insertar el mismo ID dos veces: primera=True, segunda=False."""
        result = ClassificationResult(
            template_id="test002",
            template_text="prueba",
            label="test::label",
            category="test",
            confidence=0.9,
            level_used="arbiter",
        )

        first = await store.upsert(result)
        second = await store.upsert(result)

        assert first is True
        assert second is False  # INSERT OR IGNORE

    @pytest.mark.asyncio
    async def test_upsert_with_metadata(self, store):
        """Upsert con metadata del mensaje original."""
        result = ClassificationResult(
            template_id="test003",
            template_text="texto [ENTIDAD_BANCARIA]",
            label="banking::alert",
            category="banking",
            confidence=0.95,
            level_used="panel_agreement",
        )

        metadata = TemplateMetadata(
            original_message="mensaje original sin procesar",
            cleaned_message="mensaje original sin procesar",
            client_name="Bancolombia",
            client_id=123,
            phone_number="3001234567",
            operator_name="Movistar",
            account_name="test_account",
            priority_description="Alto",
            timestamp=datetime(2025, 5, 8, 10, 30, 0),
        )

        inserted = await store.upsert(result, metadata)
        assert inserted is True

        # Verificar que la metadata se guardó
        record = await store.get("test003")
        assert record is not None
        assert record["client_name"] == "Bancolombia"
        assert record["phone_number"] == "3001234567"
        assert record["original_message"] == "mensaje original sin procesar"

    @pytest.mark.asyncio
    async def test_upsert_with_rule_classifier(self, store):
        """Upsert de un resultado del L0 RuleClassifier."""
        result = ClassificationResult(
            template_id="test_rule_001",
            template_text="[OTP] [ENTIDAD_BANCARIA]",
            label="banking::otp_2fa",
            category="banking",
            subcategory="otp_2fa",
            confidence=1.0,
            level_used="rule",
            metadata={"rule_name": "banking_otp_2fa"},  # Del RuleClassifier
        )

        inserted = await store.upsert(result)
        assert inserted is True

        record = await store.get("test_rule_001")
        assert record["rule_name"] == "banking_otp_2fa"
        assert record["level_used"] == "rule"
        assert record["confidence"] == 1.0

    @pytest.mark.asyncio
    async def test_upsert_with_panel_votes(self, store):
        """Upsert con votos del panel heterogéneo."""
        result = ClassificationResult(
            template_id="test_panel_001",
            template_text="prueba",
            label="banking::transaction_alerts",
            category="banking",
            confidence=0.88,
            level_used="panel_agreement",
            panel_judge_1="banking::transaction_alerts",
            panel_judge_1_conf=0.88,
            panel_judge_2="banking::transaction_alerts",
            panel_judge_2_conf=0.88,
        )

        await store.upsert(result)

        record = await store.get("test_panel_001")
        assert record["panel_judge_1"] == "banking::transaction_alerts"
        assert record["panel_judge_1_conf"] == 0.88

    @pytest.mark.asyncio
    async def test_upsert_with_arbiter_data(self, store):
        """Upsert con decisión del árbitro."""
        result = ClassificationResult(
            template_id="test_arbiter_001",
            template_text="prueba",
            label="banking::fraud_alerts",
            category="banking",
            confidence=0.92,
            level_used="arbiter",
            arbiter_label="banking::fraud_alerts",
            arbiter_reasoning="Detectó patrón de fraude basado en presencia de tokens",
            arbiter_abstained=False,
        )

        await store.upsert(result)

        record = await store.get("test_arbiter_001")
        assert record["arbiter_label"] == "banking::fraud_alerts"
        assert "fraude" in record["arbiter_reasoning"]
        assert record["arbiter_abstained"] == 0


class TestQueries:
    """Tests de consultas de análisis."""

    @pytest_asyncio.fixture
    async def populated_store(self, store):
        """Store con varios registros para consultas."""
        # Insertar diferentes tipos de resultados
        results = [
            ClassificationResult(
                template_id=f"rule_{i}",
                template_text=f"plantilla {i}",
                label="banking::otp_2fa",
                category="banking",
                confidence=1.0,
                level_used="rule",
                metadata={"rule_name": "banking_otp_2fa"},
            )
            for i in range(5)
        ]

        results += [
            ClassificationResult(
                template_id=f"panel_{i}",
                template_text=f"plantilla {i}",
                label="healthcare::eps",
                category="healthcare",
                confidence=0.87,
                level_used="panel_agreement",
            )
            for i in range(3)
        ]

        results += [
            ClassificationResult(
                template_id=f"arbiter_{i}",
                template_text=f"plantilla {i}",
                label="digital_services::otp_2fa",
                category="digital_services",
                confidence=0.78,
                level_used="arbiter",
                needs_human_review=(i == 2),  # Una requiere revisión
            )
            for i in range(3)
        ]

        for result in results:
            await store.upsert(result)

        return store

    @pytest.mark.asyncio
    async def test_query_by_level(self, populated_store):
        """Consultar resultados por nivel."""
        rules = await populated_store.query_by_level("rule")
        assert len(rules) == 5
        assert all(r["level_used"] == "rule" for r in rules)

        panel = await populated_store.query_by_level("panel_agreement")
        assert len(panel) == 3

    @pytest.mark.asyncio
    async def test_query_by_confidence(self, populated_store):
        """Consultar resultados en rango de confianza."""
        high_conf = await populated_store.query_by_confidence(min_conf=0.99)
        assert len(high_conf) == 5  # Los del L0 rule

        medium_conf = await populated_store.query_by_confidence(
            min_conf=0.75, max_conf=0.90
        )
        assert len(medium_conf) == 6  # panel (0.87) + arbiter (0.78)

    @pytest.mark.asyncio
    async def test_query_by_client(self, populated_store):
        """Consultar resultados por cliente."""
        metadata = TemplateMetadata(
            client_name="Bancolombia",
            original_message="test",
        )

        result = ClassificationResult(
            template_id="bancolombia_001",
            template_text="test",
            label="banking::alert",
            category="banking",
            level_used="rule",
        )

        await populated_store.upsert(result, metadata)

        bancolombia = await populated_store.query_by_client("Bancolombia")
        assert len(bancolombia) == 1
        assert bancolombia[0]["client_name"] == "Bancolombia"

    @pytest.mark.asyncio
    async def test_query_needing_review(self, populated_store):
        """Consultar plantillas que necesitan revisión."""
        review = await populated_store.query_needing_review()
        assert len(review) == 1  # Solo la que marcamos con needs_human_review=True

    @pytest.mark.asyncio
    async def test_stats_by_level(self, populated_store):
        """Estadísticas agregadas por nivel."""
        stats = await populated_store.stats_by_level()

        # Debe haber 3 niveles: rule, panel_agreement, arbiter
        assert len(stats) == 3

        # Verificar que los conteos son correctos
        stat_dict = {s["level_used"]: s for s in stats}
        assert stat_dict["rule"]["count"] == 5
        assert stat_dict["panel_agreement"]["count"] == 3
        assert stat_dict["arbiter"]["count"] == 3

        # El L0 debe tener confianza promedio 1.0
        assert stat_dict["rule"]["avg_confidence"] == 1.0


class TestUpdateFrequency:
    """Tests de actualización de frecuencia."""

    @pytest.mark.asyncio
    async def test_update_frequency_increments(self, store):
        """update_frequency incrementa el contador."""
        result = ClassificationResult(
            template_id="freq_001",
            template_text="test",
            label="test::label",
            category="test",
            level_used="rule",
            frequency=1,
        )

        await store.upsert(result)

        # Primera actualización
        updated = await store.update_frequency(
            "freq_001", datetime.now().isoformat()
        )
        assert updated is True

        record = await store.get("freq_001")
        assert record["frequency"] == 2

        # Segunda actualización
        await store.update_frequency(
            "freq_001", datetime.now().isoformat()
        )
        record = await store.get("freq_001")
        assert record["frequency"] == 3

    @pytest.mark.asyncio
    async def test_update_frequency_nonexistent(self, store):
        """update_frequency en ID inexistente retorna False."""
        updated = await store.update_frequency(
            "nonexistent", datetime.now().isoformat()
        )
        assert updated is False


class TestGet:
    """Tests de consulta individual."""

    @pytest.mark.asyncio
    async def test_get_existing(self, store):
        """get() retorna un registro existente."""
        result = ClassificationResult(
            template_id="get_test_001",
            template_text="prueba",
            label="test::label",
            category="test",
            level_used="rule",
        )

        await store.upsert(result)
        record = await store.get("get_test_001")

        assert record is not None
        assert record["template_id"] == "get_test_001"
        assert record["label"] == "test::label"

    @pytest.mark.asyncio
    async def test_get_nonexistent(self, store):
        """get() retorna None si no existe."""
        record = await store.get("nonexistent")
        assert record is None


class TestConcurrency:
    """Tests de concurrencia con asyncio.Lock."""

    @pytest.mark.asyncio
    async def test_concurrent_upserts(self, store):
        """Múltiples inserciones concurrentes sin race conditions."""
        results = [
            ClassificationResult(
                template_id=f"concurrent_{i}",
                template_text=f"plantilla {i}",
                label="test::label",
                category="test",
                level_used="rule",
            )
            for i in range(10)
        ]

        # Ejecutar concurrentemente
        tasks = [store.upsert(r) for r in results]
        inserted = await asyncio.gather(*tasks)

        assert all(inserted)  # Todos deben retornar True

        # Verificar que se insertaron todos
        for i in range(10):
            record = await store.get(f"concurrent_{i}")
            assert record is not None
