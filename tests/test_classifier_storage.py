"""
test_classifier_storage.py - Tests de ClassificationStore

Tests de persistencia JSONL, resume, y manejo de concurrencia.
"""

import pytest
import json
import asyncio
from pathlib import Path
from pipeline.core.models import ClassificationResult
from pipeline.stages.classifier.storage import ClassificationStore


@pytest.fixture
def store(tmp_path):
    """Crea un store temporal para tests."""
    store = ClassificationStore(tmp_path / "test.jsonl")
    store.ensure_parent_exists()
    return store


@pytest.mark.asyncio
async def test_append_and_load_processed_ids(store):
    """
    Test 1: Append de resultados y carga de template_ids ya procesados
    """
    # Crear y persistir 3 resultados
    result1 = ClassificationResult(
        template_id="id1",
        template_text="text1",
        applied_rules=["otp"],
        label="banking::otp_2fa",
        category="banking",
        subcategory="otp_2fa",
        confidence=0.9,
        level_used="panel_agreement",
    )

    result2 = ClassificationResult(
        template_id="id2",
        template_text="text2",
        applied_rules=["amount"],
        label="banking::transaction_alerts",
        category="banking",
        subcategory="transaction_alerts",
        confidence=0.85,
        level_used="panel_agreement",
    )

    result3 = ClassificationResult(
        template_id="id3",
        template_text="text3",
        applied_rules=[],
        label="ABSTAIN",
        category="ABSTAIN",
        subcategory="",
        confidence=0.0,
        level_used="human_review",
        needs_human_review=True,
    )

    # Append
    await store.append(result1)
    await store.append(result2)
    await store.append(result3)

    # Crear nuevo store para simular reload
    new_store = ClassificationStore(store.jsonl_path)
    processed = await new_store.load_processed_ids()

    # Verificar
    assert processed == {"id1", "id2", "id3"}


@pytest.mark.asyncio
async def test_resume_skips_processed(store):
    """
    Test 2: Resume salta templates ya procesados
    """
    # Append inicial
    result1 = ClassificationResult(
        template_id="skip_me",
        template_text="ya procesado",
        applied_rules=[],
        label="banking::otp_2fa",
        category="banking",
        subcategory="otp_2fa",
        confidence=0.9,
        level_used="panel_agreement",
    )
    await store.append(result1)

    # Reload para verificar
    new_store = ClassificationStore(store.jsonl_path)
    processed = await new_store.load_processed_ids()

    assert "skip_me" in processed


@pytest.mark.asyncio
async def test_concurrent_appends(store, tmp_path):
    """
    Test 3: Múltiples appends concurrentes son seguros (asyncio.Lock)
    """
    # Crear 10 resultados
    async def append_result(idx):
        result = ClassificationResult(
            template_id=f"concurrent_{idx}",
            template_text=f"text_{idx}",
            applied_rules=[],
            label=f"label_{idx}",
            category=f"cat_{idx}",
            subcategory="",
            confidence=0.5 + (idx * 0.01),
            level_used="panel_agreement",
        )
        await store.append(result)

    # Ejecutar 10 appends en paralelo
    await asyncio.gather(*[append_result(i) for i in range(10)])

    # Verificar que todas se escribieron
    processed = await store.load_processed_ids()
    assert len(processed) == 10
    assert all(f"concurrent_{i}" in processed for i in range(10))

    # Verificar que el JSONL tiene exactamente 10 líneas válidas
    valid_lines = 0
    with open(store.jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                json.loads(line)  # Verificar que es JSON válido
                valid_lines += 1

    assert valid_lines == 10


@pytest.mark.asyncio
async def test_corrupted_line_tolerance(store):
    """
    Test 4: load_processed_ids es robusto a líneas JSON corruptas
    """
    # Append válido
    result = ClassificationResult(
        template_id="valid_id",
        template_text="valid",
        applied_rules=[],
        label="banking::otp_2fa",
        category="banking",
        subcategory="otp_2fa",
        confidence=0.9,
        level_used="panel_agreement",
    )
    await store.append(result)

    # Insertar línea corrupta manualmente
    with open(store.jsonl_path, "a", encoding="utf-8") as f:
        f.write("{ corrupted json\n")

    # Append otro válido después
    result2 = ClassificationResult(
        template_id="valid_id_2",
        template_text="valid2",
        applied_rules=[],
        label="banking::otp_2fa",
        category="banking",
        subcategory="otp_2fa",
        confidence=0.9,
        level_used="panel_agreement",
    )
    await store.append(result2)

    # load_processed_ids debería saltar la línea corrupta
    new_store = ClassificationStore(store.jsonl_path)
    processed = await new_store.load_processed_ids()

    # Debe tener 2 IDs válidos (skip la corrupta)
    assert "valid_id" in processed
    assert "valid_id_2" in processed
    assert len(processed) == 2


@pytest.mark.asyncio
async def test_iter_classifications(store):
    """
    Test 5: iter_classifications devuelve todos los resultados en orden
    """
    # Append varios resultados
    for i in range(5):
        result = ClassificationResult(
            template_id=f"iter_{i}",
            template_text=f"text_{i}",
            applied_rules=[],
            label=f"label_{i}",
            category=f"cat_{i}",
            subcategory="",
            confidence=0.5 + i * 0.1,
            level_used="panel_agreement",
        )
        await store.append(result)

    # Iterar
    results = list(store.iter_classifications())

    # Verificar
    assert len(results) == 5
    assert all("iter_" in r["template_id"] for r in results)
    # Verificar que están en orden
    for i, result in enumerate(results):
        assert result["template_id"] == f"iter_{i}"


@pytest.mark.asyncio
async def test_nonexistent_file_returns_empty(tmp_path):
    """
    Test 6: load_processed_ids en archivo que no existe devuelve set vacío
    """
    store = ClassificationStore(tmp_path / "nonexistent.jsonl")
    processed = await store.load_processed_ids()

    assert processed == set()


@pytest.mark.asyncio
async def test_ensure_parent_exists(tmp_path):
    """
    Test 7: ensure_parent_exists crea directorios si no existen
    """
    nested_path = tmp_path / "deep" / "nested" / "path" / "test.jsonl"
    store = ClassificationStore(nested_path)

    assert not nested_path.parent.exists()
    store.ensure_parent_exists()
    assert nested_path.parent.exists()
