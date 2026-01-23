"""
Preprocessors for model adapter output normalization.
"""
from typing import Dict, Any, List, Callable
import re

from .json_repair import json_extract_preprocessor
from .adapters.deepseek import deepseek_preprocessor


class GenericRegexPreprocessor:
    """Configurable regex-based preprocessor."""

    def __init__(self, patterns: List[Dict[str, Any]]):
        self.patterns = patterns

    def __call__(self, text: str) -> str:
        if not text:
            return ""
        for pattern_cfg in self.patterns:
            pattern = pattern_cfg.get("pattern", "")
            repl = pattern_cfg.get("repl", "")
            if pattern:
                text = re.sub(pattern, repl, text, flags=re.DOTALL)
        return text.strip()


class SmartRepairPreprocessor:
    """
    Generalized preprocessor to repair common LLM JSON errors.
    Automatically quotes unquoted string values and repairs common syntax issues.
    """

    def __init__(self, specific_values: List[str] = None):
        self.specific_values = [v.upper() for v in specific_values] if specific_values else None

    def __call__(self, text: str) -> str:
        if not text:
            return ""

        if self.specific_values:
            labels = "|".join(re.escape(v) for v in self.specific_values)
            text = re.sub(
                rf'([\'\"]?\w+[\'\"]?):\s*({labels})\b(?![@\w\'\"])',
                r'\1: "\2"',
                text,
                flags=re.IGNORECASE,
            )
        else:
            def quote_match(match):
                key_part = match.group(1)
                val = match.group(2)
                if val.lower() in ["true", "false", "null"] or re.match(r"^-?\d+(\.\d+)?$", val):
                    return f"{key_part}: {val}"
                return f'{key_part}: "{val}"'

            text = re.sub(
                r'([\'\"]?\w+[\'\"]?):\s*([a-zA-Z_][\w-]*)\b(?![@\w\'\"])',
                quote_match,
                text,
            )

        text = re.sub(
            r'([\'\"]?(?:decision|choice|action)[\'\"]?):\s*(\d)\b(?![@\w\'\"])',
            r'\1: "\2"',
            text,
            flags=re.IGNORECASE,
        )

        text = re.sub(r'("[\'\"]?)\s*\n\s*(["\'\w])', r"\1,\n\2", text)

        return text


def get_preprocessor(p_cfg: Dict[str, Any]) -> Callable[[str], str]:
    """Factory for preprocessors based on config."""
    p_type = p_cfg.get("type", "identity").lower()
    if p_type == "deepseek":
        return deepseek_preprocessor
    if p_type == "json_extract":
        return json_extract_preprocessor
    if p_type == "smart_repair":
        return SmartRepairPreprocessor(p_cfg.get("quote_values"))
    if p_type == "regex":
        return GenericRegexPreprocessor(p_cfg.get("patterns", []))
    return lambda x: x
