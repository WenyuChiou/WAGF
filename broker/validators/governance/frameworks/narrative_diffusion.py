"""
Narrative-diffusion framework — generic narrative-amplification theory
for social-media-style propagation channels.

Phase 6T-F prep (2026-05-27). Generic by design — not coupled to
flood, vaccination, traffic, or any specific domain. Per the
genericity audit at
``.research/social_media_genericity_audit.md``, the construct
vocabulary (salience / virality / audience_fit /
narrative_consistency) is applicable to any domain modeling
narrative-amplification dynamics:

- Flood paper-3 social-media influencer
- Vaccination misinformation account
- Traffic news propagator
- Disaster early-warning rumor channel
- Misinformation research generally

Genericity invariant
====================
This module MUST NOT import from ``broker.domains.water`` or any
``examples.*`` package. The CLASS lives in
``broker/validators/governance/frameworks/`` (a generic broker home),
not in ``broker/domains/<one-specific-domain>/`` — different from
``UtilityFramework`` / ``FinancialFramework`` whose classes stay in
``broker/domains/water/`` because their ``get_expected_behavior``
methods are flood-paper-3-coupled (deferred to a separate refactor).
The new ``NarrativeDiffusionFramework`` has no such coupling — its
``get_expected_behavior`` returns generic narrative-amplification
verbs (``"amplify"`` / ``"counter_narrative"`` / etc.) that any
domain can map to its own concrete skill names.
"""
from __future__ import annotations

from typing import Dict, List

from broker.core.psychometric import (
    ConstructDef,
    PsychologicalFramework,
    ValidationResult,
)


class NarrativeDiffusionFramework(PsychologicalFramework):
    """Generic narrative-diffusion framework for social-media-style
    propagation agents.

    Constructs (the four-construct base):

    - ``SALIENCE`` — how relevant the narrative is to the current
      moment (VL/L/M/H/VH).
    - ``VIRALITY`` — how likely the narrative is to spread (VL/L/M/H/VH).
    - ``AUDIENCE_FIT`` — how well the narrative matches the agent's
      audience (VL/L/M/H/VH).
    - ``NARRATIVE_CONSISTENCY`` — how consistent the narrative is
      with the agent's prior positions / brand (VL/L/M/H/VH).

    A high SALIENCE + high VIRALITY combination suggests amplification;
    high NARRATIVE_CONSISTENCY + low AUDIENCE_FIT suggests holding the
    narrative without push; etc.

    Expected-behavior vocabulary is intentionally generic:
    ``amplify`` / ``counter_narrative`` / ``share`` / ``stay_silent``.
    Domain packs MAP these to their concrete skill names (e.g. flood
    paper-3's ``amplify_event`` / ``post_counter_narrative`` /
    ``share_success_story`` / ``maintain_silence``).
    """

    @property
    def name(self) -> str:
        return "Narrative Diffusion"

    def get_constructs(self) -> Dict[str, ConstructDef]:
        """Return Narrative Diffusion constructs."""
        return {
            "SALIENCE": ConstructDef(
                name="Salience",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description=(
                    "How relevant the narrative is to the current "
                    "moment / event context"
                ),
            ),
            "VIRALITY": ConstructDef(
                name="Virality",
                values=["VL", "L", "M", "H", "VH"],
                required=True,
                description=(
                    "How likely the narrative is to spread via the "
                    "follower network"
                ),
            ),
            "AUDIENCE_FIT": ConstructDef(
                name="Audience Fit",
                values=["VL", "L", "M", "H", "VH"],
                required=False,
                description=(
                    "How well the narrative matches the publishing "
                    "agent's audience demographics"
                ),
            ),
            "NARRATIVE_CONSISTENCY": ConstructDef(
                name="Narrative Consistency",
                values=["VL", "L", "M", "H", "VH"],
                required=False,
                description=(
                    "How consistent the narrative is with the agent's "
                    "prior positions / brand"
                ),
            ),
        }

    def validate_coherence(self, appraisals: Dict[str, str]) -> ValidationResult:
        """Validate Narrative Diffusion coherence.

        Checks required constructs are present + values are in the
        declared label set. Emits a WARNING (not ERROR) when an
        agent shows very-high VIRALITY but very-low SALIENCE — that
        combination is plausible (e.g. clickbait) but unusual enough
        to flag.
        """
        errors: List[str] = []
        warnings: List[str] = []

        required_check = self.validate_required_constructs(appraisals)
        if not required_check.valid:
            return required_check

        value_check = self.validate_construct_values(appraisals)
        if not value_check.valid:
            return value_check

        salience = appraisals.get("SALIENCE", "M").upper()
        virality = appraisals.get("VIRALITY", "M").upper()

        if virality == "VH" and salience == "VL":
            warnings.append(
                "Very-high virality with very-low salience — possible "
                "clickbait or astroturfing signal"
            )

        return ValidationResult(
            valid=True,
            errors=errors,
            warnings=warnings,
            metadata={
                "salience": salience,
                "virality": virality,
                "audience_fit": appraisals.get("AUDIENCE_FIT", ""),
                "narrative_consistency": appraisals.get(
                    "NARRATIVE_CONSISTENCY", ""
                ),
            },
        )

    def get_expected_behavior(self, appraisals: Dict[str, str]) -> List[str]:
        """Return expected narrative-amplification actions given
        appraisals.

        Generic verbs — domain packs map to concrete skill names. A
        flood-paper-3 ``social_media_influencer`` pack would map:

        - ``amplify`` → ``amplify_event``
        - ``counter_narrative`` → ``post_counter_narrative``
        - ``share`` → ``share_success_story``
        - ``stay_silent`` → ``maintain_silence``

        A vaccination_ma misinformation account might map the same
        verbs to ``boost_post`` / ``debunk_claim`` / ``share_video``
        / ``go_dark``.
        """
        salience = appraisals.get("SALIENCE", "M").upper()
        virality = appraisals.get("VIRALITY", "M").upper()
        consistency = appraisals.get("NARRATIVE_CONSISTENCY", "M").upper()

        high_band = {"H", "VH"}
        low_band = {"L", "VL"}

        if salience in high_band and virality in high_band:
            return ["amplify", "share"]
        if consistency in low_band and salience in high_band:
            return ["counter_narrative"]
        if salience in low_band and virality in low_band:
            return ["stay_silent"]
        return ["share"]
