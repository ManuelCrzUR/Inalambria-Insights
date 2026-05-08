"""
classifier - Etapa de clasificación LLM (Panel + Árbitro) + L0 Rule-based

Expone los componentes públicos para uso en el pipeline.
"""

from pipeline.stages.classifier.base import PanelVote, BaseClassifier
from pipeline.stages.classifier.panel import HeterogeneousPanel
from pipeline.stages.classifier.arbiter import Arbiter
from pipeline.stages.classifier.orchestrator import ClassifierStage
from pipeline.stages.classifier.storage import ClassificationStore
from pipeline.stages.rule_classifier import RuleClassifier, ClassificationRule, RuleMatch

__all__ = [
    "PanelVote",
    "BaseClassifier",
    "HeterogeneousPanel",
    "Arbiter",
    "ClassifierStage",
    "ClassificationStore",
    "RuleClassifier",
    "ClassificationRule",
    "RuleMatch",
]
