"""
test_template_extractor_new_tokens.py - Tests para los nuevos placeholder tokens

Verifica que los 5 nuevos tokens (entidad_bancaria, plataforma, entidad_eps,
producto_bancario, movimiento_bancario) se extraen correctamente sin romper
los tokens existentes.
"""

import pytest
from pipeline.core.models import NormalizedMessage
from pipeline.stages.template_extractor import TemplateExtractor


def make_msg(text: str) -> NormalizedMessage:
    """Helper para crear NormalizedMessage con valores por defecto."""
    return NormalizedMessage(
        original_message=text,
        cleaned_message=text.lower(),
        status_id=1,
        phone_number="3001234567",
    )


class TestNewPlaceholderTokens:
    """Tests para los 5 nuevos tokens semánticos."""

    @pytest.fixture
    def extractor(self):
        return TemplateExtractor()

    # ── ENTIDAD_BANCARIA ────────────────────────────────────────────────

    def test_bancolombia_token(self, extractor):
        """Extrae [ENTIDAD_BANCARIA] para 'Bancolombia'."""
        template = extractor.extract(make_msg("Bancolombia te informa..."))
        assert "[ENTIDAD_BANCARIA]" in template.template_text
        assert "entidad_bancaria" in template.applied_rules

    def test_davivienda_token(self, extractor):
        """Extrae [ENTIDAD_BANCARIA] para 'Davivienda'."""
        template = extractor.extract(make_msg("Davivienda alert"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text

    def test_nequi_token(self, extractor):
        """Extrae [ENTIDAD_BANCARIA] para 'Nequi'."""
        template = extractor.extract(make_msg("Tu Nequi"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text

    def test_bbva_token(self, extractor):
        """Extrae [ENTIDAD_BANCARIA] para 'BBVA'."""
        template = extractor.extract(make_msg("BBVA informa"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text

    def test_scotiabank_token(self, extractor):
        """Extrae [ENTIDAD_BANCARIA] para 'Scotiabank'."""
        template = extractor.extract(make_msg("Scotiabank"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text

    # ── PLATAFORMA ──────────────────────────────────────────────────────

    def test_app_movil_token(self, extractor):
        """Extrae [PLATAFORMA] para 'app móvil'."""
        template = extractor.extract(make_msg("Ingresa a tu app móvil"))
        assert "[PLATAFORMA]" in template.template_text
        assert "plataforma" in template.applied_rules

    def test_banca_virtual_token(self, extractor):
        """Extrae [PLATAFORMA] para 'banca virtual'."""
        template = extractor.extract(make_msg("acceso a banca virtual"))
        assert "[PLATAFORMA]" in template.template_text

    def test_portal_web_token(self, extractor):
        """Extrae [PLATAFORMA] para 'portal web'."""
        template = extractor.extract(make_msg("en portal web de"))
        assert "[PLATAFORMA]" in template.template_text

    def test_app_solo_token(self, extractor):
        """Extrae [PLATAFORMA] para 'app' (word boundary)."""
        template = extractor.extract(make_msg("descarga la app ahora"))
        assert "[PLATAFORMA]" in template.template_text

    # ── ENTIDAD_EPS ─────────────────────────────────────────────────────

    def test_nueva_eps_token(self, extractor):
        """Extrae [ENTIDAD_EPS] para 'Nueva EPS'."""
        template = extractor.extract(make_msg("Nueva EPS te informa"))
        assert "[ENTIDAD_EPS]" in template.template_text
        assert "entidad_eps" in template.applied_rules

    def test_famisanar_token(self, extractor):
        """Extrae [ENTIDAD_EPS] para 'Famisanar'."""
        template = extractor.extract(make_msg("Famisanar"))
        assert "[ENTIDAD_EPS]" in template.template_text

    def test_sanitas_token(self, extractor):
        """Extrae [ENTIDAD_EPS] para 'Sanitas'."""
        template = extractor.extract(make_msg("Tu afiliación a Sanitas"))
        assert "[ENTIDAD_EPS]" in template.template_text

    # ── PRODUCTO_BANCARIO ───────────────────────────────────────────────

    def test_cuenta_ahorros_token(self, extractor):
        """Extrae [PRODUCTO_BANCARIO] para 'cuenta de ahorros'."""
        template = extractor.extract(make_msg("tu cuenta de ahorros"))
        assert "[PRODUCTO_BANCARIO]" in template.template_text
        assert "producto_bancario" in template.applied_rules

    def test_tarjeta_credito_token(self, extractor):
        """Extrae [PRODUCTO_BANCARIO] para 'tarjeta de crédito'."""
        template = extractor.extract(make_msg("tu tarjeta de crédito"))
        assert "[PRODUCTO_BANCARIO]" in template.template_text

    def test_tarjeta_debito_token(self, extractor):
        """Extrae [PRODUCTO_BANCARIO] para 'tarjeta débito'."""
        template = extractor.extract(make_msg("tarjeta débito"))
        assert "[PRODUCTO_BANCARIO]" in template.template_text

    def test_credito_hipotecario_token(self, extractor):
        """Extrae [PRODUCTO_BANCARIO] para 'crédito hipotecario'."""
        template = extractor.extract(make_msg("crédito hipotecario"))
        assert "[PRODUCTO_BANCARIO]" in template.template_text

    # ── MOVIMIENTO_BANCARIO ─────────────────────────────────────────────

    def test_transferencia_token(self, extractor):
        """Extrae [MOVIMIENTO_BANCARIO] para 'transferencia'."""
        template = extractor.extract(make_msg("tu transferencia fue"))
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text
        assert "movimiento_bancario" in template.applied_rules

    def test_debito_token(self, extractor):
        """Extrae [MOVIMIENTO_BANCARIO] para 'débito'."""
        template = extractor.extract(make_msg("débito en tu cuenta"))
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text

    def test_consignacion_token(self, extractor):
        """Extrae [MOVIMIENTO_BANCARIO] para 'consignación'."""
        template = extractor.extract(make_msg("consignación confirmada"))
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text

    def test_pago_exitoso_token(self, extractor):
        """Extrae [MOVIMIENTO_BANCARIO] para 'pago exitoso'."""
        template = extractor.extract(make_msg("pago exitoso completado"))
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text

    # ── PRIORIDAD: los nuevos tokens se aplican ANTES de [URL] y [NUM] ───

    def test_priority_bancaria_before_url(self, extractor):
        """[ENTIDAD_BANCARIA] se extrae antes que [URL]."""
        template = extractor.extract(make_msg("Bancolombia: visita www.bancolombia.com"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text
        assert "bancolombia" not in template.template_text.lower()

    def test_priority_bancaria_before_number(self, extractor):
        """[ENTIDAD_BANCARIA] no se convierte en [NUM]."""
        template = extractor.extract(make_msg("tu Bancolombia alert"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text
        assert "bancolombia" not in template.template_text

    # ── COMBINACIONES: múltiples tokens nuevos en una plantilla ──────────

    def test_combination_entidad_producto(self, extractor):
        """Múltiples tokens: [ENTIDAD_BANCARIA] + [PRODUCTO_BANCARIO]."""
        template = extractor.extract(make_msg("tu cuenta de ahorros en Bancolombia"))
        assert "[ENTIDAD_BANCARIA]" in template.template_text
        assert "[PRODUCTO_BANCARIO]" in template.template_text

    def test_combination_movimiento_monto(self, extractor):
        """Múltiples tokens: [MOVIMIENTO_BANCARIO] + [AMT] + [ENTIDAD_BANCARIA]."""
        template = extractor.extract(make_msg("transferencia de $100.000 a Davivienda"))
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text
        assert "[AMT]" in template.template_text
        assert "[ENTIDAD_BANCARIA]" in template.template_text

    def test_combination_all_new_tokens(self, extractor):
        """Los 5 nuevos tokens en una sola plantilla (caso extremo)."""
        msg = make_msg(
            "transferencia de $500 desde tu tarjeta de crédito "
            "en Bancolombia app móvil. Famisanar te informa."
        )
        template = extractor.extract(msg)
        assert "[MOVIMIENTO_BANCARIO]" in template.template_text
        assert "[AMT]" in template.template_text
        assert "[PRODUCTO_BANCARIO]" in template.template_text
        assert "[ENTIDAD_BANCARIA]" in template.template_text
        assert "[PLATAFORMA]" in template.template_text
        assert "[ENTIDAD_EPS]" in template.template_text

    # ── REGRESIÓN: los tokens existentes no se rompen ────────────────────

    def test_regression_otp_still_works(self, extractor):
        """El token [OTP] existente sigue funcionando."""
        template = extractor.extract(make_msg("tu código otp es 1234"))
        assert "[OTP]" in template.template_text

    def test_regression_url_still_works(self, extractor):
        """El token [URL] existente sigue funcionando."""
        template = extractor.extract(make_msg("visita www.ejemplo.com"))
        assert "[URL]" in template.template_text

    def test_regression_amount_still_works(self, extractor):
        """El token [AMT] existente sigue funcionando."""
        template = extractor.extract(make_msg("monto: $1.234.567"))
        assert "[AMT]" in template.template_text

    def test_regression_date_still_works(self, extractor):
        """El token [DATE] existente sigue funcionando."""
        template = extractor.extract(make_msg("fecha: 25/12/2025"))
        assert "[DATE]" in template.template_text

    def test_regression_phone_still_works(self, extractor):
        """El token [PHONE] existente sigue funcionando."""
        template = extractor.extract(make_msg("llamar a 3001234567"))
        assert "[PHONE]" in template.template_text
