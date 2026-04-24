"""
message_splitter.py - Separación de mensajes con y sin placeholders

Después del TemplateExtractor, los mensajes se dividen en dos grupos:
1. CON placeholders aplicados (applied_rules no vacío)
2. SIN placeholders (texto puro, applied_rules vacío)

Esto permite análisis diferenciados: deduplicación por template_id
para los primeros, y análisis de texto puro para los segundos.

Flujo:
    List[Template] (resultado del extractor)
    → MessageSplitter.split()
    → SplitResult(with_placeholders, pure_messages)
"""

from dataclasses import dataclass, field
from typing import List
from pipeline.core.models import Template


@dataclass
class SplitResult:
    """
    Resultado de la separación de mensajes por presencia de placeholders.

    Attributes:
        with_placeholders: Templates donde ≥1 regla disparó (applied_rules no vacío)
        pure_messages: Templates donde ninguna regla disparó (applied_rules vacío)
    """

    with_placeholders: List[Template] = field(default_factory=list)
    """Mensajes que tuvieron placeholders reemplazados."""

    pure_messages: List[Template] = field(default_factory=list)
    """Mensajes de texto puro (sin placeholders reemplazados)."""

    @property
    def total(self) -> int:
        """Total de mensajes en ambos grupos."""
        return len(self.with_placeholders) + len(self.pure_messages)

    @property
    def placeholder_ratio(self) -> float:
        """Proporción de mensajes con placeholders (0.0-1.0)."""
        if self.total == 0:
            return 0.0
        return len(self.with_placeholders) / self.total

    def __repr__(self) -> str:
        return (
            f"SplitResult("
            f"with_placeholders={len(self.with_placeholders):,}, "
            f"pure_messages={len(self.pure_messages):,}, "
            f"ratio={self.placeholder_ratio:.1%})"
        )


class MessageSplitter:
    """
    Separa una lista de Templates en dos grupos:
    - Con placeholders: aplicaron ≥1 regla de extracción
    - Sin placeholders: ninguna regla disparó (texto puro)

    La lógica es simple: examina `template.applied_rules`.
    Si está vacío → pure message. Si no → tiene placeholders.

    Example:
        >>> splitter = MessageSplitter()
        >>> templates = extractor.extract_batch(normalized_msgs)
        >>> result = splitter.split(templates)
        >>> print(f"Placeholders: {len(result.with_placeholders)}")
        >>> print(f"Pure text: {len(result.pure_messages)}")
    """

    def split(self, templates: List[Template]) -> SplitResult:
        """
        Separa una lista de templates en dos grupos.

        Args:
            templates: Lista de Template objects del TemplateExtractor.

        Returns:
            SplitResult con ambos grupos preservando metadata completa.
        """
        with_placeholders: List[Template] = []
        pure_messages: List[Template] = []

        for template in templates:
            # applied_rules vacío → ninguna regla disparó
            if template.applied_rules:
                with_placeholders.append(template)
            else:
                pure_messages.append(template)

        return SplitResult(
            with_placeholders=with_placeholders,
            pure_messages=pure_messages
        )

    def split_batch(
        self,
        templates: List[Template],
        chunk_size: int = 10_000
    ) -> SplitResult:
        """
        Separa templates procesando en chunks.

        Útil para listas muy grandes (6.7M+ mensajes) para evitar
        picos de memoria. Procesa en chunks y acumula resultados.

        Args:
            templates: Lista completa de templates.
            chunk_size: Tamaño de chunk para procesamiento (default 10k).

        Returns:
            SplitResult acumulado de todos los chunks.
        """
        result = SplitResult()

        for i in range(0, len(templates), chunk_size):
            chunk = templates[i:i + chunk_size]
            chunk_result = self.split(chunk)

            result.with_placeholders.extend(chunk_result.with_placeholders)
            result.pure_messages.extend(chunk_result.pure_messages)

        return result
