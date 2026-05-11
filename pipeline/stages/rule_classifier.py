"""
rule_classifier.py - Clasificador L0 basado en set matching de tokens

Antes de invocar el Panel LLM, evalúa si la plantilla es determinísticamente
clasificable mediante reglas de presencia/ausencia de tokens.

Flujo:
    template_text (con [TOKENS] normalizados)
    → extract_tokens()
    → evaluate rules (in order of priority)
    → first match → RuleMatch
    → miss → None (escala al Panel LLM)

Diseño:
    - Los patrones regex de sender se compilan UNA vez en __init__.
    - La evaluación es cortocircuito: forbidden → required_all → required_any.
    - Complejidad O(R × T) donde R = reglas (~20), T = tokens por template (~10).
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Set, FrozenSet


# Regex compilado UNA vez: extrae tokens como [TOKEN_NAME]
_TOKEN_RE = re.compile(r"\[([A-Z_]+)\]")


@dataclass(frozen=True)
class ClassificationRule:
    """
    Define una regla de clasificación basada en presencia/ausencia de tokens.

    Atributos:
        name:           Identificador único de la regla (para trazabilidad).
        label:          Etiqueta de taxonomía resultante (ej: 'banking::otp_2fa').
        priority:       Orden de evaluación. Menor = primero. Las reglas más
                        específicas (más condiciones) deben tener prioridad más baja.
        required_all:   Todos estos tokens DEBEN estar presentes.
        required_any:   Al menos UNO de estos tokens debe estar presente.
                        Si está vacío, no aplica esta condición.
        forbidden:      Ninguno de estos tokens puede estar presente.
                        Permite evitar falsos positivos.
        sender_pattern: Regex opcional sobre client_name (sender).
                        Útil para senders como "Temu" que clasifican directamente.
        confidence:     Confianza del resultado. Default 1.0 para reglas
                        determinísticas; puede ser menor para heurísticas.
    """
    name: str
    label: str
    priority: int
    required_all: FrozenSet[str] = field(default_factory=frozenset)
    required_any: FrozenSet[str] = field(default_factory=frozenset)
    forbidden: FrozenSet[str] = field(default_factory=frozenset)
    sender_pattern: Optional[str] = None
    confidence: float = 1.0

    def matches(self, token_set: Set[str], sender: Optional[str] = None) -> bool:
        """
        Evalúa si esta regla aplica dado el conjunto de tokens y el sender.

        Orden de evaluación (cortocircuito):
        1. sender_pattern (si existe): debe hacer match → si no, False inmediato.
        2. forbidden: ninguno puede estar en token_set.
        3. required_all: todos deben estar en token_set.
        4. required_any: al menos uno debe estar en token_set (si se definió).
        """
        # 1. Sender check
        if self.sender_pattern:
            if not sender or not re.search(
                self.sender_pattern, sender, re.IGNORECASE
            ):
                return False

        # 2. Forbidden check
        if self.forbidden & token_set:
            return False

        # 3. Required all
        if not self.required_all <= token_set:
            return False

        # 4. Required any (solo si se definió)
        if self.required_any and not (self.required_any & token_set):
            return False

        return True


@dataclass
class RuleMatch:
    """Resultado de una clasificación por reglas."""
    label: str
    confidence: float
    rule_name: str
    matched_tokens: Set[str]


# ============================================================================
# CATÁLOGO DE REGLAS
# ============================================================================

CLASSIFICATION_RULES: List[ClassificationRule] = sorted([

    # ── REGLAS DE SENDER DIRECTO (máxima especificidad) ─────────────────
    ClassificationRule(
        name="temu_sender",
        label="commerce_retail::ecommerce",
        priority=10,
        sender_pattern=r"^temu$",
        confidence=1.0,
    ),
    ClassificationRule(
        name="shein_sender",
        label="commerce_retail::ecommerce",
        priority=11,
        sender_pattern=r"^shein$",
        confidence=1.0,
    ),

    # ── UTILIDADES (agua, luz, seguros) ──────────────────────────────────
    ClassificationRule(
        name="utilities_water",
        label="utilities::water",
        priority=12,
        required_all=frozenset({"ACUEDUCTO", "FACTURA", "URL"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="utilities_light",
        label="utilities::light",
        priority=13,
        required_all=frozenset({"LUZ", "FACTURA", "URL"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="utilities_insurance_renewal",
        label="utilities::insurance_renewal",
        priority=14,
        required_all=frozenset({"SEGUROS", "ACTIVAR", "SOAT"}),
        confidence=1.0,
    ),

    # ── DIGITAL SERVICES ─────────────────────────────────────────────────
    ClassificationRule(
        name="telegram_login",
        label="digital_services::log_in",
        priority=15,
        required_all=frozenset({"TELEGRAM", "LOGIN"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="apps_otp",
        label="digital_services::otp_2fa",
        priority=16,
        required_all=frozenset({"APPS", "OTP"}),
        confidence=0.95,
    ),

    # ── BANKING: SOLUCIONES DE PAGO ──────────────────────────────────────
    ClassificationRule(
        name="banking_payment_solutions",
        label="banking::payment_solutions",
        priority=17,
        required_all=frozenset({"ENTIDAD_BANCARIA", "PRODUCTO_BANCARIO", "ALTERNATIVA_PAGO"}),
        confidence=1.0,
    ),

    # ── EXCLUSIONES (no clasificar) ──────────────────────────────────────
    ClassificationRule(
        name="exclude_phone_otp",
        label="",  # Empty label para omitir clasificación
        priority=18,
        required_all=frozenset({"PHONE", "OTP"}),
        confidence=0.0,
    ),

    # ── BANKING: combinaciones de 3 tokens (más específicas) ────────────
    ClassificationRule(
        name="banking_otp_con_producto",
        label="banking::otp_2fa",
        priority=20,
        required_all=frozenset({"ENTIDAD_BANCARIA", "OTP", "PRODUCTO_BANCARIO"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="banking_tx_completa",
        label="banking::transaction_alerts",
        priority=21,
        required_all=frozenset({
            "ENTIDAD_BANCARIA", "MOVIMIENTO_BANCARIO", "AMT"
        }),
        confidence=1.0,
    ),
    ClassificationRule(
        name="banking_fraud_plataforma",
        label="banking::fraud_alerts",
        priority=22,
        required_all=frozenset({"ENTIDAD_BANCARIA", "PLATAFORMA"}),
        forbidden=frozenset({"OTP", "AMT", "MOVIMIENTO_BANCARIO"}),
        confidence=1.0,
    ),

    # ── BANKING: combinaciones de 2 tokens ──────────────────────────────
    ClassificationRule(
        name="banking_otp_2fa",
        label="banking::otp_2fa",
        priority=30,
        required_all=frozenset({"ENTIDAD_BANCARIA", "OTP"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="banking_transaction",
        label="banking::transaction_alerts",
        priority=31,
        required_all=frozenset({"ENTIDAD_BANCARIA", "MOVIMIENTO_BANCARIO"}),
        required_any=frozenset({"AMT", "PRODUCTO_BANCARIO"}),
        confidence=1.0,
    ),
    ClassificationRule(
        name="banking_balance",
        label="banking::balance_alerts",
        priority=32,
        required_all=frozenset({"ENTIDAD_BANCARIA", "AMT"}),
        forbidden=frozenset({"OTP", "MOVIMIENTO_BANCARIO", "PLATAFORMA"}),
        confidence=0.9,
    ),

    # ── HEALTHCARE ───────────────────────────────────────────────────────
    ClassificationRule(
        name="healthcare_eps",
        label="healthcare::eps",
        priority=40,
        required_all=frozenset({"ENTIDAD_EPS"}),
        confidence=1.0,
    ),

    # ── DIGITAL SERVICES ─────────────────────────────────────────────────
    ClassificationRule(
        name="digital_otp",
        label="digital_services::otp_2fa",
        priority=50,
        required_all=frozenset({"OTP"}),
        forbidden=frozenset({"ENTIDAD_BANCARIA", "ENTIDAD_EPS"}),
        confidence=0.85,
    ),

], key=lambda r: r.priority)


# ============================================================================
# CLASIFICADOR L0
# ============================================================================

class RuleClassifier:
    """
    Clasificador L0 basado en set matching de tokens.

    Evalúa las reglas en orden de prioridad y retorna el primer match.
    Si ninguna regla aplica, retorna None → el orquestador escala al LLM.

    Complejidad: O(R × T) donde R = reglas, T = tokens por template.
    En práctica O(1) dado el tamaño pequeño de ambos conjuntos.
    """

    def __init__(self, rules: Optional[List[ClassificationRule]] = None):
        # Reglas ya ordenadas por prioridad en el catálogo.
        # Permitir inyección para testing.
        self._rules = rules if rules is not None else CLASSIFICATION_RULES

        # Compilar sender patterns una sola vez.
        self._compiled_senders = {
            rule.name: re.compile(rule.sender_pattern, re.IGNORECASE)
            for rule in self._rules
            if rule.sender_pattern
        }

    @staticmethod
    def extract_tokens(template_text: str) -> Set[str]:
        """
        Extrae el conjunto de tokens presentes en un template_text.

        Ejemplo:
            "ingresa [OTP] en [ENTIDAD_BANCARIA]" → {"OTP", "ENTIDAD_BANCARIA"}

        El token se extrae sin los corchetes para comparar con frozensets
        en las reglas.
        """
        return set(_TOKEN_RE.findall(template_text))

    def classify(
        self,
        template_text: str,
        client_name: Optional[str] = None,
    ) -> Optional[RuleMatch]:
        """
        Clasifica un template por reglas.

        Args:
            template_text: texto del template con tokens normalizados.
            client_name:   sender/cliente (para reglas de sender_pattern).

        Returns:
            RuleMatch si alguna regla aplica, None si ninguna matchea.
            None indica que debe escalar al panel LLM.
        """
        token_set = self.extract_tokens(template_text)

        for rule in self._rules:
            if rule.matches(token_set, sender=client_name):
                return RuleMatch(
                    label=rule.label,
                    confidence=rule.confidence,
                    rule_name=rule.name,
                    matched_tokens=token_set & (
                        rule.required_all | rule.required_any
                    ),
                )

        return None
