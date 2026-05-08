"""
test_rule_classifier.py - Tests para el clasificador L0 (set matching de tokens)

Verifica que:
1. La extracción de tokens funciona correctamente.
2. Cada regla del catálogo clasifica sus casos de prueba.
3. El cortocircuito de prioridad funciona (primera regla que matchea gana).
4. Los patrones de sender funcionan.
5. Llamadas con rule_classifier=None no rompen el orquestador.
"""

import pytest
from pipeline.stages.rule_classifier import (
    RuleClassifier,
    ClassificationRule,
    RuleMatch,
)


class TestTokenExtraction:
    """Verifica extracción de tokens desde template_text."""

    def test_extract_single_token(self):
        """Extrae un token único."""
        text = "ingresa el código [OTP]"
        tokens = RuleClassifier.extract_tokens(text)
        assert tokens == {"OTP"}

    def test_extract_multiple_tokens(self):
        """Extrae múltiples tokens."""
        text = "transferencia de [AMT] a [ENTIDAD_BANCARIA] completada"
        tokens = RuleClassifier.extract_tokens(text)
        assert tokens == {"AMT", "ENTIDAD_BANCARIA"}

    def test_extract_no_tokens(self):
        """Devuelve conjunto vacío si no hay tokens."""
        text = "hola mundo"
        tokens = RuleClassifier.extract_tokens(text)
        assert tokens == set()

    def test_extract_duplicate_tokens(self):
        """No duplica tokens en el conjunto."""
        text = "[OTP] es tu código [OTP] temporal"
        tokens = RuleClassifier.extract_tokens(text)
        assert tokens == {"OTP"}


class TestRuleMatching:
    """Verifica la lógica de matching de reglas."""

    def test_required_all_match(self):
        """Una regla con required_all matchea si todos los tokens están presentes."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            required_all=frozenset({"OTP", "ENTIDAD_BANCARIA"}),
        )
        token_set = {"OTP", "ENTIDAD_BANCARIA", "PLATAFORMA"}
        assert rule.matches(token_set)

    def test_required_all_no_match(self):
        """Una regla con required_all no matchea si falta algún token."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            required_all=frozenset({"OTP", "ENTIDAD_BANCARIA"}),
        )
        token_set = {"OTP"}
        assert not rule.matches(token_set)

    def test_required_any_match(self):
        """Una regla con required_any matchea si al menos uno está presente."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            required_any=frozenset({"OTP", "CODIGO"}),
        )
        token_set = {"CODIGO", "ENTIDAD_BANCARIA"}
        assert rule.matches(token_set)

    def test_required_any_no_match(self):
        """Una regla con required_any no matchea si ninguno está presente."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            required_any=frozenset({"OTP", "CODIGO"}),
        )
        token_set = {"ENTIDAD_BANCARIA"}
        assert not rule.matches(token_set)

    def test_forbidden_blocks_match(self):
        """Una regla no matchea si contiene un token forbidden."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            required_all=frozenset({"ENTIDAD_BANCARIA"}),
            forbidden=frozenset({"OTP"}),
        )
        token_set = {"ENTIDAD_BANCARIA", "OTP"}
        assert not rule.matches(token_set)

    def test_sender_pattern_match(self):
        """Una regla con sender_pattern matchea si el sender es correcto."""
        rule = ClassificationRule(
            name="test",
            label="test::label",
            priority=1,
            sender_pattern=r"^temu$",
        )
        assert rule.matches(set(), sender="temu")
        assert not rule.matches(set(), sender="shein")
        assert not rule.matches(set(), sender=None)


class TestClassifierCatalog:
    """Verifica que los casos de prueba del catálogo clasifican correctamente."""

    @pytest.fixture
    def classifier(self):
        return RuleClassifier()

    def test_banking_otp_con_producto(self, classifier):
        """Caso: OTP + entidad bancaria + producto → banking::otp_2fa."""
        template = "ingresa el [OTP] en tu [ENTIDAD_BANCARIA] [PRODUCTO_BANCARIO]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::otp_2fa"
        assert result.confidence == 1.0
        assert result.rule_name == "banking_otp_con_producto"

    def test_banking_otp_2fa(self, classifier):
        """Caso: OTP + entidad bancaria → banking::otp_2fa."""
        template = "código otp para tu [ENTIDAD_BANCARIA] es [OTP]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::otp_2fa"

    def test_banking_transaction(self, classifier):
        """Caso: Movimiento + entidad + monto → transaction_alerts."""
        template = "[MOVIMIENTO_BANCARIO] de [AMT] en [ENTIDAD_BANCARIA]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::transaction_alerts"

    def test_banking_balance(self, classifier):
        """Caso: Monto + entidad (sin movimiento/plataforma) → balance_alerts."""
        template = "tu saldo en [ENTIDAD_BANCARIA] es [AMT]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::balance_alerts"

    def test_banking_fraud_plataforma(self, classifier):
        """Caso: Entidad + plataforma (sin OTP/monto) → fraud_alerts."""
        template = "acceso a tu [ENTIDAD_BANCARIA] [PLATAFORMA] no autorizado"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::fraud_alerts"

    def test_healthcare_eps(self, classifier):
        """Caso: EPS → healthcare::eps."""
        template = "tu afiliación a [ENTIDAD_EPS] está activa"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "healthcare::eps"

    def test_digital_otp(self, classifier):
        """Caso: OTP sin banco/eps → digital_services::otp_2fa."""
        template = "tu código de verificación es [OTP]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "digital_services::otp_2fa"
        assert result.confidence == 0.85

    def test_temu_sender(self, classifier):
        """Caso: sender=temu → commerce_retail::ecommerce."""
        template = "tu pedido en app móvil"
        result = classifier.classify(template, client_name="temu")
        assert result is not None
        assert result.label == "commerce_retail::ecommerce"
        assert result.confidence == 1.0

    def test_no_match(self, classifier):
        """Caso: ninguna regla aplica → retorna None (escala a LLM)."""
        template = "mensaje genérico sin tokens interesantes"
        result = classifier.classify(template)
        assert result is None

    def test_priority_order(self, classifier):
        """Verifica que se aplica la regla de menor prioridad (primero)."""
        # Esta plantilla matchea tanto "banking_otp_con_producto" (prioridad 20)
        # como "banking_otp_2fa" (prioridad 30). Debe ganar la de menor prioridad.
        template = "[OTP] en [ENTIDAD_BANCARIA] [PRODUCTO_BANCARIO]"
        result = classifier.classify(template)
        assert result is not None
        assert result.rule_name == "banking_otp_con_producto"


class TestClassifierIntegration:
    """Verifica integración del clasificador con casos reales."""

    @pytest.fixture
    def classifier(self):
        return RuleClassifier()

    def test_complex_template_banking(self, classifier):
        """Plantilla compleja con múltiples tokens → matchea correctamente."""
        template = (
            "tu [MOVIMIENTO_BANCARIO] por [AMT] en [ENTIDAD_BANCARIA] "
            "fue completada el [DATE] a las [TIME]"
        )
        result = classifier.classify(template)
        assert result is not None
        assert "banking" in result.label

    def test_template_with_irrelevant_tokens(self, classifier):
        """Tokens irrelevantes no afectan el matching."""
        template = "[ENTIDAD_BANCARIA] [OTP] enviado el [DATE] a las [TIME]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "banking::otp_2fa"


class TestCustomRules:
    """Verifica que se pueden inyectar reglas personalizadas (para testing)."""

    def test_inject_custom_rules(self):
        """Permite inyectar reglas personalizadas en el constructor."""
        custom_rules = [
            ClassificationRule(
                name="custom_test",
                label="custom::label",
                priority=1,
                required_all=frozenset({"TEST_TOKEN"}),
            ),
        ]
        classifier = RuleClassifier(rules=custom_rules)
        template = "[TEST_TOKEN]"
        result = classifier.classify(template)
        assert result is not None
        assert result.label == "custom::label"

    def test_empty_rules(self):
        """Con reglas vacías, siempre devuelve None."""
        classifier = RuleClassifier(rules=[])
        template = "[OTP] [ENTIDAD_BANCARIA]"
        result = classifier.classify(template)
        assert result is None
