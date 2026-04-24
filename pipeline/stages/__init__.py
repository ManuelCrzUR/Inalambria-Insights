"""Stages - Pasos composables del pipeline"""

from pipeline.stages.template_extractor import TemplateExtractor, PLACEHOLDER_RULES
from pipeline.stages.message_splitter import MessageSplitter, SplitResult

__all__ = ["TemplateExtractor", "PLACEHOLDER_RULES", "MessageSplitter", "SplitResult"]
