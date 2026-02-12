"""
Model Adapter ABC — abstract interface for LLM output parsing.

Extracted from model_adapter.py (Phase 2.2 split).
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from ...interfaces.skill_types import SkillProposal


class ModelAdapter(ABC):
    """
    Abstract base class for model adapters.

    Each LLM type (Ollama, OpenAI, Anthropic) has its own adapter
    that normalizes output into SkillProposal format.
    """

    @abstractmethod
    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.

        Args:
            raw_output: Raw text output from LLM
            context: Current context (for skill mapping)

        Returns:
            SkillProposal or None if parsing fails
        """
        pass

    @abstractmethod
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """
        Format retry prompt with validation errors.

        Args:
            original_prompt: The original prompt sent to LLM
            errors: List of validation errors

        Returns:
            Formatted retry prompt
        """
        pass
