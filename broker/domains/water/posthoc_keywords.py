"""Water-domain PMT keyword dictionaries for post-hoc trace analysis.

Phase 6J-D (2026-05-22): relocated from
``broker/validators/posthoc/keyword_classifier.py`` so generic broker
post-hoc code carries no flood-PMT defaults. Water-domain callers
(``broker/domains/water/calibration/cv_runner.py``,
``broker/domains/water/calibration/micro_validator.py``) construct
``KeywordClassifier`` with these dicts explicitly.

Domain mapping:
    Flood:      TP (Threat Perception)  / CP (Coping Perception)   — PMT
    Irrigation: WSA (Water Scarcity Assessment) / ACA (Adaptive
                Capacity Assessment) — Dual Appraisal Framework.
                Irrigation traces use Tier-1 (label regex) only — supply
                WSA/ACA-specific dicts here only when Tier-2 narrative
                keyword matching is needed.
"""
from typing import Dict, List


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


__all__ = ["TA_KEYWORDS", "CA_KEYWORDS"]
