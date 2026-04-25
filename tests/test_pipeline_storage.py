"""
test_pipeline_storage.py - Tests para PipelineStorage (batch + streaming)

Cubre:
    - API Streaming: append_template(), append_unique_template(), close_jsonl_files()
    - API Batch (legacy): save_split(), save_unique_templates() para datasets pequeños
    - Guardado de metadata JSON
    - Deduplicación on-the-fly
    - O(1) memoria durante streaming
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from pipeline.core.models import Template
from pipeline.stages import MessageSplitter, SplitResult
from pipeline.storage import PipelineStorage


# ============================================================================
# HELPERS Y FIXTURES
# ============================================================================

def make_template(
    text: str,
    applied_rules=None,
    template_id: str = "test123456789ab",
    client_name: str = "TestClient"
) -> Template:
    """Crea un Template mínimo para pruebas."""
    return Template(
        template_text=text,
        template_id=template_id,
        original_message=text,
        cleaned_message=text,
        phone_number="+573001234567",
        status_id=3,
        client_name=client_name,
        applied_rules=applied_rules if applied_rules is not None else []
    )


@pytest.fixture
def tmp_storage(tmp_path):
    """PipelineStorage que escribe en directorio temporal."""
    storage = PipelineStorage(output_dir=tmp_path)
    return storage


# ============================================================================
# TESTS: API STREAMING
# ============================================================================

class TestStreamingAppend:
    """Tests para append_template() - streaming sin acumular."""

    def test_append_template_crea_jsonl(self, tmp_storage):
        """append_template() crea archivo JSONL."""
        t = make_template("msg1", applied_rules=["amount"])
        tmp_storage.append_template(t)
        tmp_storage.close_jsonl_files()

        path = tmp_storage.output_dir / "templates_with_placeholders.jsonl"
        assert path.exists()

    def test_append_template_separa_categorias(self, tmp_storage):
        """append_template() separa con/sin placeholders en archivos distintos."""
        t1 = make_template("msg1", applied_rules=["amount"], template_id="id1")
        t2 = make_template("msg2", applied_rules=[], template_id="id2")

        tmp_storage.append_template(t1)
        tmp_storage.append_template(t2)
        tmp_storage.close_jsonl_files()

        path_with = tmp_storage.output_dir / "templates_with_placeholders.jsonl"
        path_pure = tmp_storage.output_dir / "templates_pure_messages.jsonl"

        assert path_with.exists()
        assert path_pure.exists()

        with path_with.open() as f:
            lines_with = f.readlines()
        with path_pure.open() as f:
            lines_pure = f.readlines()

        assert len(lines_with) == 1
        assert len(lines_pure) == 1

    def test_append_template_jsonl_es_valido(self, tmp_storage):
        """Las líneas del JSONL de streaming son JSON válidos."""
        t = make_template("msg1", applied_rules=["amount", "date"])
        tmp_storage.append_template(t)
        tmp_storage.close_jsonl_files()

        path = tmp_storage.output_dir / "templates_with_placeholders.jsonl"
        with path.open() as f:
            record = json.loads(f.readline())

        assert record["template_id"] == "test123456789ab"
        assert record["applied_rules"] == ["amount", "date"]
        assert "timestamp" in record


class TestStreamingUnique:
    """Tests para append_unique_template() - deduplicación on-the-fly."""

    def test_append_unique_deduplica(self, tmp_storage):
        """append_unique_template() deduplica por template_id."""
        t1 = make_template("msg1", applied_rules=["amount"], template_id="id1")
        t2 = make_template("msg1", applied_rules=["amount"], template_id="id1")  # Duplicado
        t3 = make_template("msg2", applied_rules=["otp"], template_id="id2")

        tmp_storage.append_unique_template(t1)
        tmp_storage.append_unique_template(t2)  # No se guarda (duplicado)
        tmp_storage.append_unique_template(t3)
        tmp_storage.close_jsonl_files()

        path = tmp_storage.output_dir / "unique_templates.jsonl"
        with path.open() as f:
            lines = f.readlines()

        assert len(lines) == 2  # Solo 2 IDs únicos

    def test_append_unique_mantiene_frequency_en_memoria(self, tmp_storage):
        """append_unique_template() cuenta frequency internamente."""
        # Nota: La frequency actual es siempre 1 (simplificado)
        # Para full-featured, requeriría actualizar JSONL on-the-fly
        t1 = make_template("msg", applied_rules=["amount"], template_id="id1")
        t2 = make_template("msg", applied_rules=["amount"], template_id="id1")

        tmp_storage.append_unique_template(t1)
        tmp_storage.append_unique_template(t2)
        tmp_storage.close_jsonl_files()

        path = tmp_storage.output_dir / "unique_templates.jsonl"
        with path.open() as f:
            record = json.loads(f.readline())

        # El registro guardado tiene frequency=1 (se guarda solo la primera vez)
        assert record["frequency"] == 1


# ============================================================================
# TESTS: API BATCH (LEGACY)
# ============================================================================

class TestBatchSaveSplit:
    """Tests para save_split() - legacy para datasets pequeños."""

    def test_save_split_crea_parquets(self, tmp_storage):
        """save_split() crea 2 archivos Parquet."""
        split = SplitResult(
            with_placeholders=[make_template("msg", applied_rules=["amt"], template_id="id1")],
            pure_messages=[make_template("msg2", applied_rules=[], template_id="id2")]
        )

        paths = tmp_storage.save_split(split)

        assert paths["with_placeholders"].exists()
        assert paths["pure_messages"].exists()

    def test_save_split_parquet_legible(self, tmp_storage):
        """Parquet guardado es legible con pandas."""
        split = SplitResult(
            with_placeholders=[make_template("msg", applied_rules=["amount"], template_id="id1")],
            pure_messages=[]
        )

        paths = tmp_storage.save_split(split)
        df = pd.read_parquet(paths["with_placeholders"])

        assert len(df) == 1
        assert df.iloc[0]["template_id"] == "id1"


class TestBatchSaveUnique:
    """Tests para save_unique_templates() - legacy."""

    def test_save_unique_templates_deduplica(self, tmp_storage):
        """save_unique_templates() deduplica por template_id."""
        templates = [
            make_template("msg1", applied_rules=["amount"], template_id="id1"),
            make_template("msg1", applied_rules=["amount"], template_id="id1"),  # Duplicado
            make_template("msg2", applied_rules=["otp"], template_id="id2"),
        ]

        path = tmp_storage.save_unique_templates(templates)

        with path.open() as f:
            lines = f.readlines()

        assert len(lines) == 2

    def test_save_unique_templates_cuenta_frecuencia(self, tmp_storage):
        """save_unique_templates() cuantifica frequency correctamente."""
        templates = [
            make_template("msg1", applied_rules=["amount"], template_id="id1"),
            make_template("msg1", applied_rules=["amount"], template_id="id1"),
            make_template("msg1", applied_rules=["amount"], template_id="id1"),
            make_template("msg2", applied_rules=["otp"], template_id="id2"),
        ]

        path = tmp_storage.save_unique_templates(templates)

        with path.open() as f:
            records = [json.loads(line) for line in f]

        id1_record = [r for r in records if r["template_id"] == "id1"][0]
        id2_record = [r for r in records if r["template_id"] == "id2"][0]

        assert id1_record["frequency"] == 3
        assert id2_record["frequency"] == 1


# ============================================================================
# TESTS: METADATA
# ============================================================================

class TestMetadata:
    """Tests para save_metadata()."""

    def test_save_metadata_crea_json_valido(self, tmp_storage):
        """save_metadata() crea JSON válido."""
        data = {
            "total_messages": 6712400,
            "unique_templates": 2847,
            "timestamp": datetime.now(),
        }

        path = tmp_storage.save_metadata(data)

        with path.open() as f:
            loaded = json.load(f)

        assert loaded["total_messages"] == 6712400
        assert loaded["unique_templates"] == 2847


# ============================================================================
# TESTS: CLOSE Y CLEANUP
# ============================================================================

class TestClose:
    """Tests para close_jsonl_files()."""

    def test_close_jsonl_files_cierra_sin_error(self, tmp_storage):
        """close_jsonl_files() cierra archivos sin error."""
        t = make_template("msg1", applied_rules=["amount"])
        tmp_storage.append_template(t)

        # No debe lanzar error
        tmp_storage.close_jsonl_files()

        # Los handles deben estar cerrados
        assert len(tmp_storage._jsonl_files) == 0

    def test_close_jsonl_files_twice_es_seguro(self, tmp_storage):
        """Llamar close_jsonl_files() dos veces es seguro."""
        t = make_template("msg1", applied_rules=["amount"])
        tmp_storage.append_template(t)

        tmp_storage.close_jsonl_files()
        # No debe lanzar error
        tmp_storage.close_jsonl_files()


# ============================================================================
# TESTS: INTEGRACIÓN
# ============================================================================

class TestIntegracionStreaming:
    """Tests de flujo E2E con streaming."""

    def test_flujo_streaming_e2e(self, tmp_storage):
        """Flujo E2E: Templates → append streaming → close → leer."""
        from pipeline.stages import TemplateExtractor
        from pipeline.core.models import NormalizedMessage

        msgs = [
            NormalizedMessage(
                original_message="saldo $100.000",
                cleaned_message="saldo $100.000",
                phone_number="+573001234567",
                status_id=3,
                client_name="Banco"
            ),
            NormalizedMessage(
                original_message="gracias",
                cleaned_message="gracias",
                phone_number="+573001234567",
                status_id=3,
                client_name="Banco"
            ),
        ]

        extractor = TemplateExtractor()
        templates = extractor.extract_batch(msgs)

        for t in templates:
            tmp_storage.append_template(t)
            tmp_storage.append_unique_template(t)

        tmp_storage.close_jsonl_files()

        # Verificar archivos existen y son legibles
        path_with = tmp_storage.output_dir / "templates_with_placeholders.jsonl"
        path_pure = tmp_storage.output_dir / "templates_pure_messages.jsonl"
        path_unique = tmp_storage.output_dir / "unique_templates.jsonl"

        assert path_with.exists()
        assert path_pure.exists()
        assert path_unique.exists()

        with path_with.open() as f:
            assert len(f.readlines()) == 1  # 1 con placeholders

        with path_pure.open() as f:
            assert len(f.readlines()) == 1  # 1 puro

        with path_unique.open() as f:
            assert len(f.readlines()) == 2  # 2 templates únicos


# ============================================================================
# TESTS: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Edge cases y comportamientos especiales."""

    def test_timestamp_se_serializa_correctamente(self, tmp_storage):
        """timestamp en streaming se serializa sin error."""
        t = make_template("test", applied_rules=["amount"])  # Con placeholders
        t.timestamp = datetime(2025, 4, 24, 12, 30, 45)

        tmp_storage.append_template(t)
        tmp_storage.close_jsonl_files()

        path = tmp_storage.output_dir / "templates_with_placeholders.jsonl"
        with path.open() as f:
            record = json.loads(f.readline())

        assert record["timestamp"] is not None

    def test_append_sin_close_mantiene_archivos_abiertos(self, tmp_storage):
        """Si no llamas close(), los archivos quedan open pero válidos."""
        t = make_template("msg1", applied_rules=["amount"])
        tmp_storage.append_template(t)

        # Sin cerrar explícitamente
        path = tmp_storage.output_dir / "templates_with_placeholders.jsonl"

        # El archivo existe aunque esté abierto
        assert path.exists()

        # Al limpiar (destructor), pytest cierra los handles
        tmp_storage.close_jsonl_files()
