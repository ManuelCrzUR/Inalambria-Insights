"""
template_extractor.py - Extracción de placeholders en mensajes SMS

Convierte un NormalizedMessage en un Template reemplazando contenido
variable predecible (montos, fechas, teléfonos, OTPs, etc.) con tokens
genéricos. Esto permite deduplicar mensajes en templates únicos.

Flujo:
    NormalizedMessage (texto limpio)
    → TemplateExtractor.extract()
    → Template (texto con [URL], [AMT], [DATE], etc.)

Uso básico:
    extractor = TemplateExtractor()
    template = extractor.extract(normalized_msg)

    # Con reglas personalizadas:
    extractor = TemplateExtractor(rules=mis_reglas)

Diseño:
    - Los patrones se compilan UNA vez en __init__ (no en cada llamada).
    - Las reglas se aplican en orden de prioridad (menor primero).
    - La regla OTP es contextual: dispara solo si el texto contiene
      palabras trigger (código, clave, otp, pin, etc.) y reemplaza
      únicamente el número, preservando el contexto.
    - El template_id es MD5[:16] del template_text (determinista).
"""

import re
import hashlib
from typing import List, Optional, Tuple

from pipeline.core.models import NormalizedMessage, RegexRuleConfig, Template


# ============================================================================
# REGLAS DE PLACEHOLDERS (orden de prioridad: menor número = primero)
# ============================================================================

PLACEHOLDER_RULES: List[RegexRuleConfig] = [
    RegexRuleConfig(
        name="url",
        pattern=r"https?://\S+|www\.\S+",
        placeholder="[URL]",
        priority=10,
    ),
    RegexRuleConfig(
        name="amount",
        # Formatos colombianos: $1.234.567, $1,250,000.50, $50.000
        pattern=r"\$\s?[\d][,\.\d]*",
        placeholder="[AMT]",
        priority=20,
    ),
    RegexRuleConfig(
        name="date",
        # Numéricas: 14/12/2025, 14-12-2025, 14.12.2025
        # Con texto: 14 dic 2025, 14 de diciembre de 2025
        pattern=(
            r"\b\d{1,2}[\/\-\.]\d{1,2}[\/\-\.]\d{2,4}\b"
            r"|"
            r"\b\d{1,2}\s+(?:de\s+)?"
            r"(?:ene(?:ro)?|feb(?:rero)?|mar(?:zo)?|abr(?:il)?|may(?:o)?|"
            r"jun(?:io)?|jul(?:io)?|ago(?:sto)?|sep(?:tiembre)?|"
            r"oct(?:ubre)?|nov(?:iembre)?|dic(?:iembre)?)"
            r"(?:\s+(?:de\s+)?\d{2,4})?\b"
        ),
        placeholder="[DATE]",
        priority=30,
    ),
    RegexRuleConfig(
        name="time",
        # 14:30, 2:30 p.m., 9:00am, 23:59:59
        pattern=r"\b\d{1,2}:\d{2}(?::\d{2})?(?:\s*[ap]\.?m\.?)?\b",
        placeholder="[TIME]",
        priority=40,
    ),
    RegexRuleConfig(
        name="phone",
        # Teléfonos colombianos: 3001234567, +573001234567, 57 300 123 4567
        # El \s? solo aplica cuando hay prefijo +57/57, no consume el espacio previo
        pattern=r"(?:(?:\+57|57)\s?)?\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b",
        placeholder="[PHONE]",
        priority=50,
    ),
    RegexRuleConfig(
        name="otp",
        # Número de 4-8 dígitos. Solo se activa si el texto contiene
        # palabras trigger (ver _OTP_TRIGGER_RE). El reemplazo es especial:
        # conserva el contexto y solo sustituye el número (ver _apply_rules).
        pattern=r"\b\d{4,8}\b",
        placeholder="[OTP]",
        priority=60,
    ),
    RegexRuleConfig(
        name="number",
        # Cualquier número restante (catch-all)
        pattern=r"\b\d+(?:[,\.]\d+)*\b",
        placeholder="[NUM]",
        priority=70,
    ),
]

# Palabras que indican que un número corto es un código OTP/verificación.
# Se compila una sola vez a nivel de módulo.
_OTP_TRIGGER_RE = re.compile(
    r"c[oó]digo|clave|otp|pin|contrase[ñn]a|token|"
    r"verificaci[oó]n|código de seguridad|código temporal",
    re.IGNORECASE | re.UNICODE,
)


# ============================================================================
# EXTRACTOR PRINCIPAL
# ============================================================================

class TemplateExtractor:
    """
    Convierte NormalizedMessage → Template reemplazando contenido variable
    con placeholders genéricos.

    Attributes:
        rules: Lista de RegexRuleConfig activas, ordenadas por prioridad.

    Example:
        >>> extractor = TemplateExtractor()
        >>> template = extractor.extract(normalized_msg)
        >>> print(template.template_text)
        "tu código otp es [OTP] válido por [NUM] minutos"
    """

    def __init__(self, rules: Optional[List[RegexRuleConfig]] = None) -> None:
        """
        Inicializa el extractor y compila los patrones regex.

        Args:
            rules: Reglas a usar. Si es None, usa PLACEHOLDER_RULES por defecto.
        """
        self.rules = rules if rules is not None else PLACEHOLDER_RULES

        # Compilar UNA sola vez, ordenados por prioridad, solo los habilitados
        self._compiled: List[Tuple[re.Pattern, str, str]] = [
            (re.compile(rule.pattern, re.IGNORECASE | re.UNICODE), rule.placeholder, rule.name)
            for rule in sorted(self.rules, key=lambda r: r.priority)
            if rule.enabled
        ]

    # -------------------------------------------------------------------------
    # API PÚBLICA
    # -------------------------------------------------------------------------

    def extract(self, msg: NormalizedMessage) -> Template:
        """
        Extrae placeholders de un NormalizedMessage y devuelve un Template.

        Args:
            msg: Mensaje normalizado (texto ya en lowercase, sin ruido).

        Returns:
            Template con el texto transformado y metadata del mensaje original.
        """
        template_text, applied_rules = self._apply_rules(msg.cleaned_message)
        template_id = self._compute_id(template_text)

        return Template(
            template_text=template_text,
            template_id=template_id,
            original_message=msg.original_message,
            cleaned_message=msg.cleaned_message,
            phone_number=msg.phone_number,
            status_id=msg.status_id,
            client_id=msg.client_id,
            client_name=msg.client_name,
            priority_id=msg.priority_id,
            priority_description=msg.priority_description,
            timestamp=msg.timestamp,
            operator_name=msg.operator_name,
            account_name=msg.account_name,
            applied_rules=applied_rules,
            metadata=msg.metadata,
        )

    def extract_batch(self, msgs: List[NormalizedMessage]) -> List[Template]:
        """
        Extrae placeholders de una lista de mensajes.

        Args:
            msgs: Lista de NormalizedMessage a procesar.

        Returns:
            Lista de Templates en el mismo orden que la entrada.
        """
        return [self.extract(msg) for msg in msgs]

    # -------------------------------------------------------------------------
    # LÓGICA INTERNA
    # -------------------------------------------------------------------------

    def _apply_rules(self, text: str) -> Tuple[str, List[str]]:
        """
        Aplica las reglas en orden de prioridad sobre el texto.

        La regla 'otp' es especial: solo se activa si el texto contiene
        palabras trigger (código, clave, otp, pin, etc.), evitando
        que números cortos genéricos se marquen como [OTP].

        Args:
            text: Texto normalizado (lowercase).

        Returns:
            Tupla (texto_con_placeholders, lista_de_reglas_aplicadas).
            La lista solo incluye reglas que efectivamente dispararon.
        """
        applied: List[str] = []
        is_otp_context = bool(_OTP_TRIGGER_RE.search(text))

        for pattern, placeholder, name in self._compiled:
            if name == "otp" and not is_otp_context:
                # Sin palabras trigger → los números cortos caen en [NUM]
                continue

            new_text, count = pattern.subn(placeholder, text)
            if count > 0:
                text = new_text
                applied.append(name)

        return text, applied

    @staticmethod
    def _compute_id(template_text: str) -> str:
        """
        Genera un ID determinista de 16 chars (MD5) para el template_text.

        Args:
            template_text: Texto con placeholders ya aplicados.

        Returns:
            Primeros 16 caracteres del hash MD5 en hexadecimal.
        """
        return hashlib.md5(template_text.encode("utf-8")).hexdigest()[:16]
