"""
Normalization utilities for LLM output parsing.

Pure utility functions with only `re` as dependency.
Extracted from model_adapter.py for reuse across parsing modules.
"""
import re
from typing import Dict, List, Optional

# Pre-compiled regex patterns for hot-path operations
_THINK_TAG_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

# Universal framework-level normalization defaults
# (Domain-independent ordinal scale and boolean mappings)
FRAMEWORK_NORMALIZATION_MAP = {
    # 5-level ordinal scale (VL-VH, used by PMT and dual-appraisal frameworks)
    "very low": "VL", "verylow": "VL", "v low": "VL", "v.low": "VL",
    "low": "L",
    "medium": "M", "med": "M", "moderate": "M", "mid": "M", "middle": "M",
    "high": "H", "hi": "H",
    "very high": "VH", "veryhigh": "VH", "v high": "VH", "v.high": "VH",

    # Boolean variations
    "true": "True", "yes": "True", "1": "True", "on": "True",
    "false": "False", "no": "False", "0": "False", "off": "False",
}


def normalize_construct_value(
    value: str,
    allowed_values: Optional[List[str]] = None,
    custom_mapping: Optional[Dict[str, str]] = None,
) -> str:
    """
    Normalize common LLM output variations to canonical forms.

    Args:
        value: Raw value from LLM
        allowed_values: Optional list of allowed values to check against
        custom_mapping: Optional agent-specific mapping (e.g., from config)

    Returns:
        Normalized value if found in mappings, otherwise original value
    """
    if not isinstance(value, str):
        return value

    normalized = value.strip()
    lower_val = normalized.lower()

    # 1. Try agent-specific custom mapping (highest priority)
    if custom_mapping and lower_val in custom_mapping:
        normalized = custom_mapping[lower_val]
    # 2. Try universal framework defaults
    elif lower_val in FRAMEWORK_NORMALIZATION_MAP:
        normalized = FRAMEWORK_NORMALIZATION_MAP[lower_val]

    # 3. If allowed_values provided, check case-insensitive match
    if allowed_values:
        for allowed in allowed_values:
            if normalized.lower() == allowed.lower():
                return allowed

    return normalized
