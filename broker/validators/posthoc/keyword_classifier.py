"""
Keyword-based construct classifier for post-hoc trace analysis.

Generic, domain-agnostic. Tier 1 (explicit label regex) + Tier 1.5
(qualifier precedence) work for any structured label output. Tier 2
(keyword matching) requires keyword dictionaries supplied by the caller
— the broker carries no domain-specific defaults (Phase 6J-D,
2026-05-22). The water-domain PMT keyword dictionaries previously
hardcoded here live at
``broker/domains/water/posthoc_keywords.py``.

Three-tier strategy:

    Tier 1   — Explicit label regex: ``VH``, ``H``, ``M``, ``L``, ``VL``
               (domain-agnostic — works for any structured label output)
    Tier 1.5 — Qualifier precedence: detects "low risk", "moderate concern"
               framing and overrides naive keyword hits (fixes the
               negation problem where e.g. "low risk of X" would match
               an H keyword "risk of X")
    Tier 2   — Keyword matching from caller-supplied dictionaries
               (omit ``ta_keywords`` / ``ca_keywords`` to skip Tier 2 and
               run domain-agnostic Tier-1/1.5-only classification)

Tier 1 catches structured labels emitted by governed pipelines
(Groups B/C); Tier 2 handles unstructured narratives (Group A) when a
domain supplies its keyword vocabulary.

References:
    Rogers, R. W. (1975). A protection motivation theory of fear appeals
        and attitude change. J. Psychol., 91(1), 93-114.
    Maddux, J. E., & Rogers, R. W. (1983). Protection motivation and
        self-efficacy. J. Exp. Soc. Psychol., 19(5), 469-479.
"""

import re
from typing import Dict, List, Optional


class KeywordClassifier:
    """Three-tier construct classifier (domain-agnostic).

    Tier 1 (explicit label regex) and Tier 1.5 (qualifier precedence)
    are domain-agnostic. Tier 2 (keyword matching) is opt-in: pass
    domain-specific keyword dictionaries to enable it; omit them to
    run Tier-1/1.5 only. Water-domain dictionaries live at
    ``broker.domains.water.posthoc_keywords``.

    Parameters
    ----------
    ta_keywords : dict, optional
        Threat-appraisal keyword dict (``{"H": [...], "L": [...]}``).
        ``None`` (default) skips Tier 2 for threat classification.
    ca_keywords : dict, optional
        Coping-appraisal keyword dict. ``None`` skips Tier 2 for coping.
    """

    def __init__(
        self,
        ta_keywords: Optional[Dict[str, List[str]]] = None,
        ca_keywords: Optional[Dict[str, List[str]]] = None,
    ):
        # Phase 6J-D (2026-05-22): no flood-PMT default; ``None`` is a
        # legitimate Tier-1/1.5-only mode.
        self.ta_keywords = ta_keywords
        self.ca_keywords = ca_keywords

    # ------------------------------------------------------------------
    # Core classification
    # ------------------------------------------------------------------

    # Qualifier patterns that override naive keyword matching.
    # LLM narratives frequently wrap H keywords inside low/moderate framing,
    # e.g. "low risk of flooding", "moderate concern".  Without qualifier
    # precedence, substring matching misclassifies these as H.
    _LOW_QUALIFIERS = re.compile(
        r"remains?\s+low|perceive[ds]?\s+low|low\s+risk|low\s+but"
        r"|minimal|no\s+immediate\s+threat|unlikely\s+to|not\s+high"
        r"|low\s+level|low\s+perceived|perceive.*\blow\b",
        re.IGNORECASE,
    )
    _MOD_QUALIFIERS = re.compile(
        r"\bmoderate\b|\bmoderately\b",
        re.IGNORECASE,
    )
    _ESCALATION_OVERRIDE = re.compile(
        r"severe|critical|extreme|catastrophic|devastating|emergency",
        re.IGNORECASE,
    )

    @staticmethod
    def classify_label(
        text: str,
        keywords: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """Classify free text into a construct level (``VH``/``H``/``M``/``L``/``VL``).

        Three-tier strategy:

        Tier 1:   Explicit categorical codes (VH/H/M/L/VL).
        Tier 1.5: Qualifier precedence — "low risk", "moderate concern"
                  override naive keyword hits (fixes negation problem).
        Tier 2:   Keyword match against *keywords* dict.

        Returns one of ``"VH"``, ``"H"``, ``"M"``, ``"L"``, ``"VL"``.
        """
        if not isinstance(text, str):
            return "M"
        upper = text.upper().strip()

        # Tier 1 — exact stand-alone labels
        if upper in ("VH", "H", "M", "L", "VL"):
            return upper
        if re.search(r"\bVH\b", upper):
            return "VH"
        if re.search(r"\bVL\b", upper):
            return "VL"
        # Only match bare H/L/M when they appear as isolated tokens,
        # not inside words.  Tier 1 is for structured label output.
        if re.search(r"\bH\b", upper):
            return "H"
        if re.search(r"\bL\b", upper):
            return "L"
        if re.search(r"\bM\b", upper):
            return "M"

        # Tier 1.5 — qualifier precedence (handles negation/framing)
        has_low = bool(KeywordClassifier._LOW_QUALIFIERS.search(text))
        has_mod = bool(KeywordClassifier._MOD_QUALIFIERS.search(text))
        if has_low:
            # Allow escalation override: "low but ... devastating" → H
            if KeywordClassifier._ESCALATION_OVERRIDE.search(text):
                return "H"
            return "L"
        if has_mod:
            if KeywordClassifier._ESCALATION_OVERRIDE.search(text):
                return "H"
            return "M"

        # Tier 2 — keyword matching
        if keywords:
            if any(w.upper() in upper for w in keywords.get("H", [])):
                return "H"
            if any(w.upper() in upper for w in keywords.get("L", [])):
                return "L"

        return "M"

    def classify_threat(self, text: str) -> str:
        """Classify threat appraisal text → TP level."""
        return self.classify_label(text, self.ta_keywords)

    def classify_coping(self, text: str) -> str:
        """Classify coping appraisal text → CP level."""
        return self.classify_label(text, self.ca_keywords)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def classify_dataframe(self, df, ta_col: str, ca_col: str):
        """Add ``ta_level`` and ``ca_level`` columns to a DataFrame.

        Parameters
        ----------
        df : pandas.DataFrame
            Must contain *ta_col* and *ca_col* columns.
        ta_col, ca_col : str
            Column names holding raw appraisal text.

        Returns
        -------
        pandas.DataFrame
            Same frame with ``ta_level`` and ``ca_level`` added.
        """
        df = df.copy()
        df["ta_level"] = df[ta_col].apply(self.classify_threat)
        df["ca_level"] = df[ca_col].apply(self.classify_coping)
        return df
