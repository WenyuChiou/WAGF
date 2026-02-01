"""
Keyword-based construct classifier for post-hoc trace analysis.

**FLOOD DOMAIN (PMT)**: Default keyword dictionaries extract Threat
Perception (TP) and Coping Perception (CP) labels from flood household
adaptation traces using Protection Motivation Theory terminology.

**IRRIGATION DOMAIN (WSA/ACA)**: For irrigation traces, supply custom
keyword dictionaries via ``ta_keywords`` and ``ca_keywords`` constructor
parameters, or use Tier 1 only (explicit label regex) which is
domain-agnostic.

Two-tier strategy:

    Tier 1 — Explicit label regex: ``VH``, ``H``, ``M``, ``L``, ``VL``
             (domain-agnostic — works for any structured label output)
    Tier 2 — Keyword matching from curated dictionaries
             (default dictionaries are PMT/flood-specific)

This formalizes the SQ1 analysis methodology (``master_report.py``) into
a reusable module.  Tier 1 catches structured labels emitted by governed
pipelines (Groups B/C); Tier 2 handles unstructured narratives (Group A).

Domain Mapping:
    Flood:      TP (Threat Perception) / CP (Coping Perception)   — PMT
    Irrigation: WSA (Water Scarcity Assessment) / ACA (Adaptive
                Capacity Assessment) — Dual Appraisal Framework

References:
    Rogers, R. W. (1975). A protection motivation theory of fear appeals
        and attitude change. J. Psychol., 91(1), 93-114.
    Maddux, J. E., & Rogers, R. W. (1983). Protection motivation and
        self-efficacy. J. Exp. Soc. Psychol., 19(5), 469-479.
"""

import re
from typing import Dict, List, Optional


# PMT keyword dictionaries — curated from literature review (FLOOD DOMAIN)
# For irrigation domain (WSA/ACA), override via KeywordClassifier constructor.
TA_KEYWORDS: Dict[str, List[str]] = {
    "H": [
        # Perceived Severity (Rogers, 1975; Maddux & Rogers, 1983)
        "severe", "critical", "extreme", "catastrophic", "significant harm",
        "dangerous", "bad", "devastating",
        # Perceived Susceptibility / Vulnerability
        "susceptible", "likely", "high risk", "exposed", "probability",
        "chance", "vulnerable",
        # Fear Arousal
        "afraid", "anxious", "worried", "concerned", "frightened",
        "emergency", "flee",
    ],
    "L": [
        "minimal", "safe", "none", "low", "unlikely", "no risk",
        "protected", "secure",
    ],
}

CA_KEYWORDS: Dict[str, List[str]] = {
    "H": [
        "grant", "subsidy", "effective", "capable", "confident", "support",
        "benefit", "protection", "affordable", "successful", "prepared",
        "mitigate", "action plan",
    ],
    "L": [
        "expensive", "costly", "unable", "uncertain", "weak", "unaffordable",
        "insufficient", "debt", "financial burden",
    ],
}


class KeywordClassifier:
    """Two-tier construct classifier (default: PMT/flood; extensible to other domains).

    Default keyword dictionaries are tuned for **flood domain PMT** constructs
    (TP/CP).  For **irrigation domain** (WSA/ACA) or other domains, supply
    custom keyword dictionaries or rely on Tier 1 (label regex) only.

    Parameters
    ----------
    ta_keywords : dict, optional
        Override threat-appraisal keyword dict (default: ``TA_KEYWORDS``).
        For irrigation: supply WSA-specific keywords.
    ca_keywords : dict, optional
        Override coping-appraisal keyword dict (default: ``CA_KEYWORDS``).
        For irrigation: supply ACA-specific keywords.
    """

    def __init__(
        self,
        ta_keywords: Optional[Dict[str, List[str]]] = None,
        ca_keywords: Optional[Dict[str, List[str]]] = None,
    ):
        self.ta_keywords = ta_keywords or TA_KEYWORDS
        self.ca_keywords = ca_keywords or CA_KEYWORDS

    # ------------------------------------------------------------------
    # Core classification
    # ------------------------------------------------------------------

    @staticmethod
    def classify_label(
        text: str,
        keywords: Optional[Dict[str, List[str]]] = None,
    ) -> str:
        """Classify free text into a PMT level.

        Tier 1: Explicit categorical codes (VH/H/M/L/VL).
        Tier 2: Keyword match against *keywords* dict.

        Returns one of ``"VH"``, ``"H"``, ``"M"``, ``"L"``, ``"VL"``.
        """
        if not isinstance(text, str):
            return "M"
        upper = text.upper()

        # Tier 1 — explicit labels (order matters: VH/VL before H/L)
        if re.search(r"\bVH\b", upper):
            return "VH"
        if re.search(r"\bH\b", upper):
            return "H"
        if re.search(r"\bVL\b", upper):
            return "VL"
        if re.search(r"\bL\b", upper):
            return "L"
        if re.search(r"\bM\b", upper):
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
