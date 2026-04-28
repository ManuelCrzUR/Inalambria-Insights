from typing import Protocol, List, Optional
from dataclasses import dataclass, field
from pipeline.core.models import ClassificationResult

@dataclass
class PanelVote:
    """Representa el voto individual de un modelo del panel."""
    label: str
    confidence: float
    model_name: str
    raw_response: Optional[dict] = None

class BaseClassifier(Protocol):
    """Interfaz estándar para componentes de clasificación."""
    async def classify(self, template_text: str, applied_rules: List[str], client_name: Optional[str] = None) -> PanelVote:
        ...
