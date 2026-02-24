"""
Keyword-based construct classifier for post-hoc trace analysis.

**FLOOD DOMAIN (PMT)**: Default keyword dictionaries extract Threat
Perception (TP) and Coping Perception (CP) labels from flood household
adaptation traces using Protection Motivation Theory terminology.

**IRRIGATION DOMAIN (WSA/ACA)**: For irrigation traces, supply custom
keyword dictionaries via ``ta_keywords`` and ``ca_keywords`` constructor
parameters, or use Tier 1 only (explicit label regex) which is
domain-agnostic.

Three-tier strategy:

    Tier 1   — Explicit label regex: ``VH``, ``H``, ``M``, ``L``, ``VL``
               (domain-agnostic — works for any structured label output)
    Tier 1.5 — Qualifier precedence: detects "low risk", "moderate concern"
               framing and overrides naive keyword hits (fixes negation
               problem where "low risk of flooding" would match H keyword
               "risk of flood")
    Tier 2   — Keyword matching from curated dictionaries
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
        "chance", "vulnerable", "vulnerability",
        # Fear Arousal — adjective and noun forms (Witte, 1992)
        "afraid", "anxious", "anxiety", "worried", "worry",
        "concerned", "concern", "frightened",
        "emergency", "flee",
        # Threat salience — common LLM narrative expressions
        "significant risk", "significant threat", "significant concern",
        "ongoing risk", "ongoing threat", "persistent risk", "persistent threat",
        "real risk", "real threat", "serious risk", "serious threat",
        "substantial risk", "substantial threat",
        "growing risk", "growing threat", "growing concern",
        "increasing risk", "increasing threat",
        "heightened risk", "heightened threat",
        "flood risk", "risk of flood", "threat of flood",
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
        """Classify free text into a PMT level.

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
