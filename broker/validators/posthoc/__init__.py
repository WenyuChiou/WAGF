"""
Post-hoc validators for offline analysis of simulation traces.

Unlike runtime governance validators (which intercept and retry proposals),
post-hoc validators classify trace data after simulation completion.  They
are used for:
- Group A keyword-based PMT classification (no structured labels at runtime)
- Cross-group R_H computation with consistent methodology
- Paper-level analysis and verification

Classes:
    PostHocValidator: Abstract base for post-hoc analysis modules
    KeywordClassifier: domain-agnostic Tier-1/1.5 label classifier; supply
        caller-owned ``ta_keywords`` / ``ca_keywords`` to enable Tier 2.
        Water-domain PMT dicts live at
        ``broker.domains.water.posthoc_keywords``.
    ThinkingRulePostHoc: V1/V2/V3 verification rules on classified traces
    compute_hallucination_rate: Unified R_H computation across groups
"""

from broker.validators.posthoc.keyword_classifier import KeywordClassifier
from broker.validators.posthoc.thinking_rule_posthoc import ThinkingRulePostHoc
from broker.validators.posthoc.unified_rh import compute_hallucination_rate

__all__ = [
    "KeywordClassifier",
    "ThinkingRulePostHoc",
    "compute_hallucination_rate",
]
