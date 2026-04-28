"""
test_classifier_orchestrator.py - Tests del orquestador ClassifierStage

Tests unitarios con mocks de Panel y Arbiter (sin llamadas reales a OpenAI).
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.core.models import ClassificationResult
from pipeline.stages.classifier.base import PanelVote
from pipeline.stages.classifier.orchestrator import ClassifierStage
from pipeline.stages.classifier.storage import ClassificationStore


@pytest.fixture
def mock_panel():
    """Panel mock que siempre devuelve votos."""
    panel = AsyncMock()
    panel.classify_parallel = AsyncMock()
    return panel


@pytest.fixture
def mock_arbiter():
    """Arbiter mock que siempre devuelve un veredicto."""
    arbiter = AsyncMock()
    arbiter.arbitrate = AsyncMock()
    return arbiter


@pytest.fixture
def mock_store(tmp_path):
    """Store mock que persiste en un archivo temporal."""
    store = ClassificationStore(tmp_path / "test_classifications.jsonl")
    store.ensure_parent_exists()
    return store


@pytest.fixture
def classifier_stage(mock_panel, mock_arbiter, mock_store):
    """ClassifierStage con mocks."""
    return ClassifierStage(
        panel=mock_panel,
        arbiter=mock_arbiter,
        store=mock_store,
        agreement_threshold=0.7,
        concurrency=5,
    )


@pytest.mark.asyncio
async def test_agreement_with_high_confidence(classifier_stage, mock_panel):
    """
    Test 1: Panel de acuerdo con confidences altas
    → No se llama arbiter, level="panel_agreement"
    """
    # Setup: ambos jueces votaron lo mismo con confianza alta
    vote1 = PanelVote(label="banking::otp_2fa", confidence=0.95, model_name="gpt-4o-mini")
    vote2 = PanelVote(label="banking::otp_2fa", confidence=0.92, model_name="gpt-5-nano")
    mock_panel.classify_parallel.return_value = (vote1, vote2)

    # Ejecutar
    result = await classifier_stage.classify_template(
        template_id="abc123",
        template_text="Tu código es [OTP]",
        applied_rules=["otp"],
        client_name="Bancolombia",
        frequency=10,
    )

    # Verificar
    assert result.label == "banking::otp_2fa"
    assert result.confidence == 0.92  # min(0.95, 0.92)
    assert result.level_used == "panel_agreement"
    assert result.agreement is True
    assert result.panel_judge_1 == "banking::otp_2fa"
    assert result.panel_judge_2 == "banking::otp_2fa"
    # Arbiter no debería ser llamado
    classifier_stage.arbiter.arbitrate.assert_not_called()


@pytest.mark.asyncio
async def test_disagreement_labels(classifier_stage, mock_panel, mock_arbiter):
    """
    Test 2: Panel en desacuerdo (labels distintos)
    → Se llama arbiter, level="arbiter"
    """
    # Setup: jueces votaron diferente
    vote1 = PanelVote(label="banking::transaction_alerts", confidence=0.8, model_name="gpt-4o-mini")
    vote2 = PanelVote(label="lending_and_credit::loan_offer_response", confidence=0.75, model_name="gpt-5-nano")
    mock_panel.classify_parallel.return_value = (vote1, vote2)

    arbiter_response = {
        "label": "banking::transaction_alerts",
        "confidence": 0.85,
        "reasoning": "El voto 1 es más preciso según el contexto del cliente."
    }
    mock_arbiter.arbitrate.return_value = arbiter_response

    # Ejecutar
    result = await classifier_stage.classify_template(
        template_id="def456",
        template_text="Tu transacción de [AMOUNT] fue aprobada",
        applied_rules=["amount"],
        client_name="Éxito",
        frequency=5,
    )

    # Verificar
    assert result.label == "banking::transaction_alerts"
    assert result.level_used == "arbiter"
    assert result.agreement is False
    # Arbiter fue llamado
    mock_arbiter.arbitrate.assert_called_once()


@pytest.mark.asyncio
async def test_low_confidence_triggers_arbiter(classifier_stage, mock_panel, mock_arbiter):
    """
    Test 3: Labels iguales pero confidences por debajo del threshold
    → Se llama arbiter (threshold=0.7, min(0.6, 0.65) < 0.7)
    """
    # Setup: mismo label pero confianzas bajas
    vote1 = PanelVote(label="collections::extrajudicial_notice", confidence=0.6, model_name="gpt-4o-mini")
    vote2 = PanelVote(label="collections::extrajudicial_notice", confidence=0.65, model_name="gpt-5-nano")
    mock_panel.classify_parallel.return_value = (vote1, vote2)

    arbiter_response = {
        "label": "collections::extrajudicial_notice",
        "confidence": 0.72,
        "reasoning": "Menciona cobro explícitamente, es clara."
    }
    mock_arbiter.arbitrate.return_value = arbiter_response

    # Ejecutar
    result = await classifier_stage.classify_template(
        template_id="ghi789",
        template_text="Tienes una deuda de [AMOUNT]. Comunícate",
        applied_rules=["amount"],
        client_name="Recuperadora",
        frequency=2,
    )

    # Verificar
    assert result.level_used == "arbiter"
    # Arbiter fue llamado porque min(0.6, 0.65) < 0.7
    mock_arbiter.arbitrate.assert_called_once()


@pytest.mark.asyncio
async def test_arbiter_abstain(classifier_stage, mock_panel, mock_arbiter):
    """
    Test 4: Arbiter responde ABSTAIN
    → needs_human_review=True, level="human_review"
    """
    # Setup: desacuerdo en el panel
    vote1 = PanelVote(label="telecom::offer_response", confidence=0.7, model_name="gpt-4o-mini")
    vote2 = PanelVote(label="utilities::bill_notification", confidence=0.68, model_name="gpt-5-nano")
    mock_panel.classify_parallel.return_value = (vote1, vote2)

    arbiter_response = {
        "label": "ABSTAIN",
        "confidence": 0.0,
        "reasoning": "El mensaje es genuinamente ambiguo sin más contexto del cliente."
    }
    mock_arbiter.arbitrate.return_value = arbiter_response

    # Ejecutar
    result = await classifier_stage.classify_template(
        template_id="jkl012",
        template_text="Tenemos una oferta especial para ti",
        applied_rules=[],
        client_name="Unknown",
        frequency=1,
    )

    # Verificar
    assert result.label == "ABSTAIN"
    assert result.needs_human_review is True
    assert result.level_used == "human_review"
    assert result.arbiter_abstained is True


@pytest.mark.asyncio
async def test_exception_handling(classifier_stage, mock_panel):
    """
    Test 5: Panel lanza excepción
    → result con metadata["error"], level="error", no rompe el stream
    """
    # Setup: panel lanza excepción
    mock_panel.classify_parallel.side_effect = ValueError("API timeout")

    # Ejecutar
    result = await classifier_stage.classify_template(
        template_id="mno345",
        template_text="Algún mensaje",
        applied_rules=[],
        client_name="Test",
        frequency=1,
    )

    # Verificar
    assert result.label == "ERROR"
    assert result.level_used == "error"
    assert result.needs_human_review is True
    assert "error" in result.metadata
    assert "API timeout" in result.metadata["error"]


@pytest.mark.asyncio
async def test_classify_stream(classifier_stage):
    """
    Test 6: Stream de templates se procesa correctamente
    → Todos son persistidos en store antes de yield
    """
    # Setup: simular stream de 3 templates
    templates = [
        {
            "template_id": "t1",
            "template_text": "Template 1",
            "applied_rules": ["otp"],
            "client_name": "Client1",
            "frequency": 5,
        },
        {
            "template_id": "t2",
            "template_text": "Template 2",
            "applied_rules": ["amount"],
            "client_name": "Client2",
            "frequency": 3,
        },
        {
            "template_id": "t3",
            "template_text": "Template 3",
            "applied_rules": [],
            "client_name": "Client3",
            "frequency": 1,
        },
    ]

    async def template_iterator():
        for t in templates:
            yield t

    # Mock para que todos retornen acuerdo del panel
    async def mock_classify(*args, **kwargs):
        return ClassificationResult(
            template_id=kwargs.get("template_id"),
            template_text=kwargs.get("template_text"),
            applied_rules=kwargs.get("applied_rules", []),
            frequency=kwargs.get("frequency", 1),
            label="banking::otp_2fa",
            category="banking",
            subcategory="otp_2fa",
            confidence=0.9,
            level_used="panel_agreement",
            agreement=True,
        )

    classifier_stage.classify_template = mock_classify

    # Ejecutar stream
    results = []
    async for result in classifier_stage.classify_stream(template_iterator()):
        results.append(result)

    # Verificar
    assert len(results) == 3
    assert all(r.label == "banking::otp_2fa" for r in results)
    # Verificar que fueron persistidos (leer del store)
    processed_ids = await classifier_stage.store.load_processed_ids()
    assert "t1" in processed_ids
    assert "t2" in processed_ids
    assert "t3" in processed_ids
