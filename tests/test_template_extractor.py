"""
test_template_extractor.py - Tests para el módulo de extracción de placeholders

Cubre:
    - Una prueba por cada regla (url, amount, date, time, phone, otp, number)
    - Mensaje sin placeholders (texto debe quedar intacto)
    - Múltiples placeholders en un mismo mensaje
    - OTP con contexto vs sin contexto
    - extract_batch()
    - Regla desactivada (enabled=False)
    - Determinismo del template_id
"""

import pytest
from pipeline.core.models import NormalizedMessage, RegexRuleConfig
from pipeline.stages.template_extractor import TemplateExtractor, PLACEHOLDER_RULES


# ============================================================================
# FIXTURE BASE
# ============================================================================

def make_msg(texto: str) -> NormalizedMessage:
    """Crea un NormalizedMessage mínimo para pruebas."""
    return NormalizedMessage(
        original_message=texto,
        cleaned_message=texto,
        phone_number="+573001234567",
        status_id=3,
    )


@pytest.fixture
def extractor() -> TemplateExtractor:
    return TemplateExtractor()


# ============================================================================
# PRUEBAS POR REGLA
# ============================================================================

class TestReglaUrl:
    def test_url_con_https(self, extractor):
        t = extractor.extract(make_msg("descarga la app en https://banco.com/app ahora"))
        assert "[URL]" in t.template_text
        assert "https://banco.com/app" not in t.template_text
        assert "url" in t.applied_rules

    def test_url_con_www(self, extractor):
        t = extractor.extract(make_msg("visita www.mitienda.co para más info"))
        assert "[URL]" in t.template_text
        assert "www" not in t.template_text
        assert "url" in t.applied_rules

    def test_url_no_aplica_sin_url(self, extractor):
        t = extractor.extract(make_msg("hola, gracias por contactarnos"))
        assert "url" not in t.applied_rules


class TestReglaAmount:
    def test_monto_con_punto_miles(self, extractor):
        t = extractor.extract(make_msg("su pago de $1.250.000 fue exitoso"))
        assert "[AMT]" in t.template_text
        assert "$1.250.000" not in t.template_text
        assert "amount" in t.applied_rules

    def test_monto_con_coma(self, extractor):
        t = extractor.extract(make_msg("saldo disponible: $85,000.50"))
        assert "[AMT]" in t.template_text
        assert "amount" in t.applied_rules

    def test_monto_simple(self, extractor):
        t = extractor.extract(make_msg("recarga de $5000 aplicada"))
        assert "[AMT]" in t.template_text
        assert "amount" in t.applied_rules


class TestReglaDate:
    def test_fecha_numerica_slash(self, extractor):
        t = extractor.extract(make_msg("su cita es el 14/12/2025"))
        assert "[DATE]" in t.template_text
        assert "date" in t.applied_rules

    def test_fecha_numerica_guion(self, extractor):
        t = extractor.extract(make_msg("vence el 31-01-2026"))
        assert "[DATE]" in t.template_text
        assert "date" in t.applied_rules

    def test_fecha_con_texto(self, extractor):
        t = extractor.extract(make_msg("próximo pago: 5 de enero de 2026"))
        assert "[DATE]" in t.template_text
        assert "date" in t.applied_rules

    def test_fecha_abreviada(self, extractor):
        t = extractor.extract(make_msg("recordatorio: 20 dic 2025"))
        assert "[DATE]" in t.template_text
        assert "date" in t.applied_rules

class TestReglaPercentage:
    def test_porcentaje_simple(self, extractor):
        t = extractor.extract(make_msg("tasa de interés: 3% mensual"))
        assert "[PCT]" in t.template_text
        assert "3%" not in t.template_text
        assert "percentage" in t.applied_rules

    def test_porcentaje_con_punto_decimal(self, extractor):
        t = extractor.extract(make_msg("descuento aplicado: 15.5% en tu compra"))
        assert "[PCT]" in t.template_text
        assert "15.5%" not in t.template_text
        assert "percentage" in t.applied_rules

    def test_porcentaje_con_coma_decimal(self, extractor):
        # Formato colombiano con coma
        t = extractor.extract(make_msg("rendimiento: 8,25% anual"))
        assert "[PCT]" in t.template_text
        assert "8,25%" not in t.template_text
        assert "percentage" in t.applied_rules

    def test_porcentaje_sin_decimales(self, extractor):
        t = extractor.extract(make_msg("iva incluido: 19%"))
        assert "[PCT]" in t.template_text
        assert "19%" not in t.template_text
        assert "percentage" in t.applied_rules

    def test_multiplos_porcentajes(self, extractor):
        t = extractor.extract(make_msg("tasa base 5% + comisión 0.5% = 5.5% total"))
        assert t.template_text.count("[PCT]") == 3
        assert "percentage" in t.applied_rules

    def test_porcentaje_con_contexto(self, extractor):
        t = extractor.extract(make_msg("su rendimiento fue del 12.75% superior al benchmark"))
        assert "[PCT]" in t.template_text
        assert "percentage" in t.applied_rules

    def test_porcentaje_no_aplica_sin_porcentaje(self, extractor):
        t = extractor.extract(make_msg("tu saldo disponible es normal"))
        assert "[PCT]" not in t.template_text
        assert "percentage" not in t.applied_rules

    def test_porcentaje_cero(self, extractor):
        t = extractor.extract(make_msg("aumento de 0% sobre el monto base"))
        assert "[PCT]" in t.template_text
        assert "percentage" in t.applied_rules

    def test_porcentaje_cien(self, extractor):
        t = extractor.extract(make_msg("descuento de 100% válido solo hoy"))
        assert "[PCT]" in t.template_text
        assert "percentage" in t.applied_rules

class TestReglaTime:
    def test_hora_simple(self, extractor):
        t = extractor.extract(make_msg("su pedido llega a las 14:30"))
        assert "[TIME]" in t.template_text
        assert "time" in t.applied_rules

    def test_hora_con_am_pm(self, extractor):
        t = extractor.extract(make_msg("apertura a las 9:00 a.m."))
        assert "[TIME]" in t.template_text
        assert "time" in t.applied_rules


class TestReglaPhone:
    def test_telefono_10_digitos(self, extractor):
        t = extractor.extract(make_msg("llame al 3001234567 para soporte"))
        assert "[PHONE]" in t.template_text
        assert "3001234567" not in t.template_text
        assert "phone" in t.applied_rules

    def test_telefono_con_prefijo_57(self, extractor):
        t = extractor.extract(make_msg("contáctenos al +573001234567"))
        assert "[PHONE]" in t.template_text
        assert "phone" in t.applied_rules

    def test_espacio_preservado_antes_del_placeholder(self, extractor):
        t = extractor.extract(make_msg("llama al 3001234567."))
        assert "al [PHONE]" in t.template_text


class TestReglaOtp:
    def test_otp_con_palabra_codigo(self, extractor):
        t = extractor.extract(make_msg("tu código es 482931 no lo compartas"))
        assert "[OTP]" in t.template_text
        assert "482931" not in t.template_text
        assert "otp" in t.applied_rules

    def test_otp_con_palabra_clave(self, extractor):
        t = extractor.extract(make_msg("su clave temporal es 7823"))
        assert "[OTP]" in t.template_text
        assert "otp" in t.applied_rules

    def test_numero_corto_sin_contexto_es_num(self, extractor):
        # Sin palabras trigger → número de 4-8 dígitos debe ser [NUM], no [OTP]
        t = extractor.extract(make_msg("tienes 3 días y 4500 puntos acumulados"))
        assert "[OTP]" not in t.template_text
        assert "otp" not in t.applied_rules
        assert "[NUM]" in t.template_text

    def test_otp_con_palabra_token(self, extractor):
        t = extractor.extract(make_msg("ingresa el token 99312 para continuar"))
        assert "[OTP]" in t.template_text
        assert "otp" in t.applied_rules


class TestReglaNumer:
    def test_numero_generico(self, extractor):
        t = extractor.extract(make_msg("tienes 3 mensajes pendientes"))
        assert "[NUM]" in t.template_text
        assert "number" in t.applied_rules

    def test_numero_referencia(self, extractor):
        t = extractor.extract(make_msg("referencia de pago: 7823456"))
        assert "[NUM]" in t.template_text
        assert "number" in t.applied_rules


# ============================================================================
# CASOS COMBINADOS
# ============================================================================

class TestCasosCombinados:
    def test_sin_placeholders(self, extractor):
        texto = "hola, gracias por contactarnos. su solicitud fue recibida."
        t = extractor.extract(make_msg(texto))
        assert t.template_text == texto
        assert t.applied_rules == []

    def test_multiples_placeholders(self, extractor):
        texto = "su pago de $150.000 fue exitoso el 14/12/2025 a las 14:30."
        t = extractor.extract(make_msg(texto))
        assert "[AMT]" in t.template_text
        assert "[DATE]" in t.template_text
        assert "[TIME]" in t.template_text
        assert "amount" in t.applied_rules
        assert "date" in t.applied_rules
        assert "time" in t.applied_rules
        
    def test_porcentaje_con_monto_y_fecha(self, extractor):
        texto = "su crédito de $500.000 con tasa del 3.5% vence el 20/12/2025"
        t = extractor.extract(make_msg(texto))
        assert "[AMT]" in t.template_text
        assert "[PCT]" in t.template_text
        assert "[DATE]" in t.template_text
        assert "amount" in t.applied_rules
        assert "percentage" in t.applied_rules
        assert "date" in t.applied_rules

    def test_url_y_telefono(self, extractor):
        texto = "descarga la app en https://banco.com/app o llama al 3001234567."
        t = extractor.extract(make_msg(texto))
        assert "[URL]" in t.template_text
        assert "[PHONE]" in t.template_text
        assert "url" in t.applied_rules
        assert "phone" in t.applied_rules

    def test_otp_completo(self, extractor):
        texto = "tu código otp es 482931 válido por 5 minutos. no lo compartas."
        t = extractor.extract(make_msg(texto))
        assert "[OTP]" in t.template_text
        assert "[NUM]" in t.template_text
        assert "otp" in t.applied_rules
        assert "number" in t.applied_rules


# ============================================================================
# EXTRACT BATCH
# ============================================================================

class TestExtractBatch:
    def test_batch_devuelve_mismo_orden(self, extractor):
        msgs = [
            make_msg("pago de $50.000 aprobado"),
            make_msg("hola, sin datos variables"),
            make_msg("tu código es 1234"),
        ]
        templates = extractor.extract_batch(msgs)
        assert len(templates) == 3
        assert "[AMT]" in templates[0].template_text
        assert templates[1].applied_rules == []
        assert "[OTP]" in templates[2].template_text

    def test_batch_vacio(self, extractor):
        assert extractor.extract_batch([]) == []


# ============================================================================
# REGLAS PERSONALIZADAS Y DESACTIVADAS
# ============================================================================

class TestReglasPersonalizadas:
    def test_regla_desactivada_no_aplica(self):
        reglas = [
            RegexRuleConfig(name="url", pattern=r"https?://\S+", placeholder="[URL]", priority=10, enabled=False),
            RegexRuleConfig(name="number", pattern=r"\b\d+\b", placeholder="[NUM]", priority=70),
        ]
        extractor = TemplateExtractor(rules=reglas)
        t = extractor.extract(make_msg("visita https://banco.com para más info"))
        assert "[URL]" not in t.template_text
        assert "url" not in t.applied_rules

    def test_reglas_personalizadas_se_usan(self):
        reglas = [
            RegexRuleConfig(name="custom", pattern=r"\bCOLOMBIA\b", placeholder="[PAIS]", priority=10),
        ]
        extractor = TemplateExtractor(rules=reglas)
        t = extractor.extract(make_msg("bienvenido a COLOMBIA"))
        assert "[PAIS]" in t.template_text
        assert "custom" in t.applied_rules


# ============================================================================
# DETERMINISMO DEL TEMPLATE ID
# ============================================================================

class TestTemplateId:
    def test_mismo_texto_mismo_id(self, extractor):
        texto = "su pago de $150.000 fue aprobado"
        t1 = extractor.extract(make_msg(texto))
        t2 = extractor.extract(make_msg(texto))
        assert t1.template_id == t2.template_id

    def test_textos_distintos_ids_distintos(self, extractor):
        t1 = extractor.extract(make_msg("pago de $50.000 aprobado"))
        t2 = extractor.extract(make_msg("pago de $100.000 aprobado"))
        # Ambos generan el mismo template (mismo patrón)
        assert t1.template_id == t2.template_id

    def test_templates_distintos_ids_distintos(self, extractor):
        t1 = extractor.extract(make_msg("su pago fue aprobado"))
        t2 = extractor.extract(make_msg("su pago fue rechazado"))
        assert t1.template_id != t2.template_id

    def test_id_tiene_16_chars(self, extractor):
        t = extractor.extract(make_msg("cualquier mensaje"))
        assert len(t.template_id) == 16
