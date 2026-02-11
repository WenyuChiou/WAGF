"""
Parsing audit utilities extracted from UnifiedAdapter.

Standalone functions for list-item detection, numeric value parsing,
and demographic grounding audits.  Each function accepts an explicit
``config`` (the parsing-config dict) instead of relying on ``self``.

Extracted from model_adapter.py to reduce file size and improve testability.
"""
import re
from typing import Any, Dict, List, Optional

from .normalization import normalize_construct_value
from .logging import logger


# ---------------------------------------------------------------------------
# 1. is_list_item  (was UnifiedAdapter._is_list_item)
# ---------------------------------------------------------------------------

def is_list_item(text: str, start: int, end: int, config: Dict[str, Any]) -> bool:
    """Determine if a matched token is part of an option list like VL/L/M.

    Args:
        text: Full text being parsed.
        start: Start index of the matched token.
        end: End index of the matched token.
        config: Parsing config dict (used for ``list_delimiters``).

    Returns:
        True if the token appears to be embedded in a slash/pipe-delimited list.
    """
    if start < 0 or end > len(text):
        return False

    # Load delimiters from config (framework default if missing)
    list_chars = config.get("list_delimiters", ['/', '|', '\\'])

    # Check trailing context (ignoring spaces AND optional quotes from preprocessor)
    next_char_idx = end
    while next_char_idx < len(text) and (text[next_char_idx].isspace() or text[next_char_idx] in ['"', "'"]):
        next_char_idx += 1

    # Check preceding context
    prev_char_idx = start - 1
    while prev_char_idx >= 0 and (text[prev_char_idx].isspace() or text[prev_char_idx] in ['"', "'"]):
        prev_char_idx -= 1

    # Indicators of a list: slashes or pipes
    if next_char_idx < len(text) and text[next_char_idx] in list_chars:
        return True
    if prev_char_idx >= 0 and text[prev_char_idx] in list_chars:
        return True
    return False


# ---------------------------------------------------------------------------
# 2. parse_numeric_value  (was UnifiedAdapter._parse_numeric_value)
# ---------------------------------------------------------------------------

def parse_numeric_value(
    raw_val: Any,
    field_config: Dict[str, Any],
    warnings: List[str],
    config: Dict[str, Any],
) -> Optional[float]:
    """Parse a numeric value from LLM output with config-driven validation.

    Args:
        raw_val: Raw value from JSON (could be int, float, or string).
        field_config: Numeric field config with min/max/unit/sign constraints.
        warnings: List to append parsing warnings.
        config: Parsing config dict (reserved for future logging control).

    Returns:
        Parsed and validated float value, or None if invalid.
    """
    key = field_config.get("key", "numeric")
    min_val = field_config.get("min")
    max_val = field_config.get("max")
    sign = field_config.get("sign", "positive_only")

    # 1. Try direct float conversion
    try:
        parsed = float(raw_val)
    except (ValueError, TypeError):
        # 2. Try regex extraction from string (handles echoed placeholders)
        if isinstance(raw_val, str):
            # Handle negative numbers if sign allows
            if sign == "both" or sign == "negative_only":
                match = re.search(r'([+-]?\d+(?:\.\d+)?)', raw_val)
            else:
                match = re.search(r'(\d+(?:\.\d+)?)', raw_val)

            if match:
                parsed = float(match.group(1))
            else:
                warnings.append(f"Could not parse numeric value for '{key}': {raw_val}")
                return None
        else:
            return None

    # 3. Apply sign validation
    if sign == "positive_only" and parsed < 0:
        warnings.append(f"Negative value for '{key}' ({parsed}) ignored - expected positive")
        return None
    elif sign == "negative_only" and parsed > 0:
        warnings.append(f"Positive value for '{key}' ({parsed}) ignored - expected negative")
        return None

    # 4. Apply range clamping
    if min_val is not None and parsed < min_val:
        warnings.append(f"Value for '{key}' ({parsed}) below min ({min_val}), clamped")
        parsed = min_val
    if max_val is not None and parsed > max_val:
        warnings.append(f"Value for '{key}' ({parsed}) above max ({max_val}), clamped")
        parsed = max_val

    return parsed


# ---------------------------------------------------------------------------
# 3. audit_demographic_grounding  (was UnifiedAdapter._audit_demographic_grounding)
# ---------------------------------------------------------------------------

def audit_demographic_grounding(
    reasoning: Dict,
    context: Dict,
    parsing_cfg: Dict,
    config: Dict[str, Any],
) -> Dict:
    """Audit if the LLM cites the qualitative demographic anchors provided in context.

    Generic implementation: looks for overlap between qualitative persona/history
    and the 'reasoning' fields.

    Args:
        reasoning: Parsed reasoning dict from the LLM response.
        context: Full agent context (persona, history, etc.).
        parsing_cfg: Parsing config for this agent type.
        config: The adapter's ``self.config`` (used as fallback for *parsing_cfg*).

    Returns:
        Dict with ``score``, ``cited_anchors``, and ``total_anchors``.
    """
    if parsing_cfg is None:
        parsing_cfg = config

    score = 0.0
    cited_anchors: List[str] = []

    # 1. Extract Target Anchors from Context
    # Source fields are configurable via 'audit_context_fields' in parsing config
    # Default fields are domain-agnostic
    default_fields = ["narrative_persona", "experience_summary"]
    context_fields = parsing_cfg.get("audit_context_fields", default_fields)
    sources = {field: context.get(field, "") for field in context_fields}

    # Short-circuit: skip keyword extraction if all sources are empty/N/A
    if not any(v and v != "[N/A]" for v in sources.values()):
        return {"score": 0.0, "details": "No anchors found in context"}

    # 2. Extract Keywords (Simple stopword filtering)
    # Generic English stopwords - domain-specific stopwords should be in config
    default_blacklist = {
        "you", "are", "a", "the", "in", "of", "to", "and", "with",
        "this", "that", "have", "from", "for", "on", "is", "it", "be",
        "as", "at", "by",
    }
    # Load additional stopwords from config (domain-specific terms)
    config_blacklist = set(parsing_cfg.get("audit_blacklist", []))
    blacklist = default_blacklist | config_blacklist
    # Topic words that are too generic to count as grounding
    # v1.1: Load from config 'audit_stopwords'
    topic_stopwords = set(
        parsing_cfg.get("audit_stopwords", ["decision", "choice", "action", "reason"])
    )

    anchors: set = set()

    for src_type, text in sources.items():
        if not text or text == "[N/A]":
            continue
        # Normalize and extract significant words
        clean_text = re.sub(r'[^\w\s]', ' ', text.lower())
        words = set(
            w for w in clean_text.split()
            if len(w) > 4 and w not in blacklist and w not in topic_stopwords
        )
        anchors.update(words)

    if not anchors:
        return {"score": 0.0, "details": "No anchors found in context"}

    # 3. Check Reasoning for Citations
    # Flatten reasoning to string
    reasoning_text = " ".join([str(v) for v in reasoning.values()]).lower()

    # Exact match or contained match?
    # For years (2012), exact word boundary is needed: \b2012\b
    # For words, simple substring is risky ("income" in "outcome"). Use word boundaries.

    hit_anchors = []
    for a in anchors:
        if a and re.search(r'\b' + re.escape(str(a)) + r'\b', reasoning_text):
            hit_anchors.append(a)

    # 4. Scoring
    # 1 hit = 0.5 (Weak), 2+ hits = 1.0 (Strong)
    if len(hit_anchors) >= 2:
        score = 1.0
    elif len(hit_anchors) == 1:
        score = 0.5

    return {
        "score": score,
        "cited_anchors": hit_anchors,
        "total_anchors": list(anchors),
    }
