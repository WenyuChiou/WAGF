"""Four ablatable context factors for the single-agent flood household.

What this file is
-----------------
A worked example of ``DomainPack.context_mask_defaults()``. It declares
four things a flood household's prompt says, and for each one: where to
find it in the rendered prompt, what to put there instead, and a
severity-matched paraphrase to compare that against.

Nothing here edits a frozen file. ``FloodDomainPack`` and its seven
mixins stay exactly as they are; the masks arrive through a subclass
registered under a SECOND domain name (``flood_masked``), so the
production ``"flood"`` pack — and every paper run that depends on it —
is untouched.

Why three factors carry a ``_history`` suffix
---------------------------------------------
The flood household prompt (``config/prompts/household.txt``) renders
flood/grant/neighbour OBSERVATIONS in exactly one place: the
``{memory}`` block, which carries the agent's remembered YEARLY
bullets. In year 6 an agent sees five "Year N: Elevation grants are
available." lines, one per remembered year, and a mask replaces every
one of them.

The template mentions neighbours and floods elsewhere too, but not as
observations these masks are declared to touch. Line 7 renders ``You
{trust_neighbors_text} your neighbors' judgment.`` — a static stance
sentence about how much the agent trusts its neighbours' judgement in
general, not a memory of what any neighbour did. Line 19 renders a
static ``Note: If no flood occurred this year, since no immediate
threat, most people would choose "Do Nothing."`` — a prompt-engineering
nudge, not a memory of what happened this year. Neither line is matched
by any pattern below: verified against the unrendered template, 0
matches for every factor. ``neighbor_adoption_history`` needs the
literal "I observe N% of neighbors elevated..." phrasing only the
memory bullet emits; ``flood_experience_history`` needs the literal,
capitalised "No flood occurred this year." with a trailing period,
which the Note line's lowercase, comma-continued clause ("If no flood
occurred this year, since...") never produces. All three memory
patterns are also anchored on the "Year N: " prefix every memory bullet
carries (``FinalParityHook.pre_year`` in ``run_flood.py`` writes
every bullet as ``f"Year {year}: ..."``), which rules out a future
static line ever matching by accident — a static instruction is never
inside a "Year N: " bullet.

So the factor these masks remove is not "this year's grant signal". It
is "everything this agent remembers about grants". The names say so.
Three of the four are named ``*_history`` for that reason, and their
descriptions state the span rather than implying a single current line.

There is deliberately no ``grant_availability_current`` or
``flood_experience_current``, and the reason is a property of the prompt
rather than a gap in this file. The memory written at the end of year N
is read in year N+1, so the most recent bullet an agent sees describes
LAST year; the current year's grant status and flood outcome never
appear as their own line. ``examples/single_agent/run_flood.py``
(``FinalParityHook.pre_year``) writes them into memory, and
``household.txt`` has no other placeholder that carries them. A
``_current`` variant would therefore have to anchor on a line that does
not exist, match nothing, and report a null effect indistinguishable
from a null finding. If a future template renders the current year's
institutional signal directly, add the ``_current`` variant then — the
pattern will have something to match.

``insurance_trust`` has no suffix because it genuinely is a single
current sentence: ``FloodContextBuilder._verbalize_trust`` renders the
agent's trust level once per prompt, from the agent's present state.

Where the renderings come from
------------------------------
The patterns match the strings the flood pipeline actually emits, not
strings invented here. ``insurance_trust`` enumerates the four phrases
``FloodContextBuilder._verbalize_trust`` can produce
(``examples/single_agent/run_flood.py``); the memory bullets come from
the yearly memory templates. If those renderings change, these patterns
stop matching — and the ablation reports "factor absent from this
prompt" for every snapshot rather than silently measuring nothing, which
is how you find out.

What these masks deliberately do NOT cover
------------------------------------------
``grant_availability_history`` masks every remembered grant sentence. It
leaves the seeded background memory ("The city previously introduced a
program offering elevation support to residents") in place, because that
is a different cue — prior institutional history written at setup rather
than a signal the agent observed year by year. An ablation over this
factor therefore removes the observed signal, not the agent's whole
notion of grants, and a null result should be read with that in mind.
"""
from __future__ import annotations

import re
from typing import Any, Dict

from broker.experiments.replay import MaskSpec

#: Domain name the masked pack registers under. Deliberately NOT "flood":
#: re-registering "flood" would swap the production pack out from under
#: every run in the process.
MASKED_DOMAIN_NAME = "flood_masked"


# ─────────────────────────────────────────────────────────────────────
# Paraphrase renderings (severity-matched controls)
# ─────────────────────────────────────────────────────────────────────

_FLOOD_DAMAGE_RE = re.compile(r"\$[\d,]+")

#: The "Year N: " label ``flood_experience_history``'s pattern anchors
#: on (item 6c) — captured so this callable can split it back off
#: ``matched``, which now includes it, and put the same label back on
#: the paraphrase it returns.
_YEAR_PREFIX_RE = re.compile(r"^(Year \d+: )")


def _paraphrase_flood_experience(matched: str) -> str:
    """Reword the flood outcome, keeping the year label, the outcome and
    the amount.

    The control must carry the SAME information as the original: if it
    dropped the damage figure it would be a second mask, and the
    comparison would answer nothing. ``matched`` is the WHOLE regex
    match — label included, since the pattern anchors on it — so this
    splits the label off, reworks the sentence, and puts the label back;
    the substitution replaces the whole match, so whatever this function
    returns is what stands in the label's place too.
    """
    prefix_match = _YEAR_PREFIX_RE.match(matched)
    prefix = prefix_match.group(1) if prefix_match else ""
    body = matched[len(prefix):]
    if body.startswith("Got flooded"):
        amount = _FLOOD_DAMAGE_RE.search(body)
        figure = amount.group(0) if amount else "an unrecorded sum"
        return f"{prefix}My house sustained {figure} of damage in a flood."
    return f"{prefix}This year went by without any flooding."


#: One rewording per trust level, each chosen so its edit size is close
#: to the neutral rendering's (measured ratios 0.82-0.97; the ablation
#: reports the ratio per run, so drift shows up rather than hiding).
_TRUST_PARAPHRASE = {
    "strongly trust": "You have a high level of confidence in the insurance company.",
    "moderately trust": "You have a fair amount of faith in the insurance company.",
    "have slight doubts about": "You are not entirely convinced by the insurance company.",
    "deeply distrust": "You have almost no faith at all in the insurance company.",
}


def _paraphrase_insurance_trust(matched: str) -> str:
    for phrase, rendering in _TRUST_PARAPHRASE.items():
        if phrase in matched:
            return rendering
    # Never silently return the original: an unchanged control arm would
    # look like a perfect null and hide that the vocabulary drifted. The
    # ablation catches this ValueError per arm, writes the row with
    # applied=False and the reason, and carries on with the other
    # factors — one stale phrase does not cost the whole grid.
    raise ValueError(
        f"insurance_trust paraphrase has no rendering for {matched!r}. "
        "FloodContextBuilder._verbalize_trust emitted a phrase this mask "
        "does not know about; add it to _TRUST_PARAPHRASE."
    )


# ─────────────────────────────────────────────────────────────────────
# The declarations
# ─────────────────────────────────────────────────────────────────────

FLOOD_FACTOR_MASKS: Dict[str, MaskSpec] = {
    "neighbor_adoption_history": MaskSpec(
        provider="SocialProvider",
        key="local.neighbor_action_summary",
        # Item 6c: anchored on the "Year N: " prefix every memory bullet
        # carries (group 1), so a static instruction line elsewhere in
        # the template can never match by accident. The neutral and
        # paraphrase renderings put the same label back via \1 — the
        # substitution replaces the whole match, prefix included.
        pattern=r"(Year \d+: )I observe (\d+)% of neighbors elevated and (\d+)% relocated\.",
        neutral=r"\1No information about neighbours is available.",
        paraphrase=r"\1Neighbour uptake stands at \2% elevated, \3% relocated.",
        description=(
            "Every neighbour-observation bullet the agent remembers, across "
            "all past years — not just the most recent one. The prompt "
            "renders one such line per remembered year and the mask replaces "
            "them all. The paraphrase keeps both percentages in each line and "
            "changes only the wording."
        ),
    ),
    "flood_experience_history": MaskSpec(
        provider="EnvironmentEventProvider",
        key="environment_context.flood_event",
        # Item 6c: same "Year N: " anchor as the other two _history
        # factors; see _paraphrase_flood_experience for why the callable
        # splits the label back off before rewording.
        pattern=(
            r"(Year \d+: )(?:Got flooded with \$[\d,]+ damage on my house"
            r"|No flood occurred this year)\."
        ),
        # Item 6b: "This year's" was wrong for a factor that removes
        # EVERY remembered year's bullet, not just the current one — each
        # masked occurrence describes a different past year, not "this
        # year". "That year" reads correctly wherever the mask lands.
        neutral=r"\1The flood outcome for that year is not recorded.",
        paraphrase=_paraphrase_flood_experience,
        description=(
            "Every remembered year's flood outcome and damage figure, across "
            "the agent's whole memory window — the prompt carries one bullet "
            "per year and the mask replaces them all. The paraphrase "
            "preserves the outcome and the amount in each. There is no "
            "'current year' variant: the current year's flood outcome is "
            "written to memory after the decision, so it is not in this "
            "prompt at all."
        ),
    ),
    "grant_availability_history": MaskSpec(
        provider="InstitutionalProvider",
        key="environment_context.grant_available",
        # Item 6c: same "Year N: " anchor as the other two _history
        # factors.
        pattern=r"(Year \d+: )Elevation grants are available\.",
        neutral=r"\1No information about elevation grants is available.",
        paraphrase=r"\1Grants for elevating a home are on offer.",
        description=(
            "Every remembered year in which elevation grants were on offer, "
            "not this year's signal alone — the prompt carries one bullet per "
            "such year and the mask replaces them all. Does not touch the "
            "seeded memory about the city's earlier programme; see this "
            "module's docstring for why there is no '_current' variant."
        ),
    ),
    "insurance_trust": MaskSpec(
        provider="NarrativeProvider",
        key="personal.trust_insurance_text",
        pattern=(
            r"You (?:strongly trust|moderately trust|have slight doubts about"
            r"|deeply distrust) the insurance company\."
        ),
        neutral="You have no particular view of the insurance company.",
        paraphrase=_paraphrase_insurance_trust,
        description=(
            "How much the agent trusts the insurer right now, verbalised once "
            "per prompt by FloodContextBuilder._verbalize_trust from the "
            "agent's present state. This one genuinely is a single current "
            "sentence, which is why it carries no '_history' suffix. The "
            "paraphrase keeps the trust level and changes the phrasing."
        ),
    ),
}


class FloodFactorMaskMixin:
    """Adds ``context_mask_defaults()`` to a flood DomainPack."""

    def context_mask_defaults(self) -> Dict[str, Any]:
        return dict(FLOOD_FACTOR_MASKS)


def build_masked_flood_pack():
    """Return a ``FloodDomainPack`` subclass that declares the masks.

    Imported lazily so this module can be read (and its
    ``FLOOD_FACTOR_MASKS`` dict used directly) without pulling the whole
    flood example into the process.
    """
    from examples.governed_flood.adapters.flood_pack import FloodDomainPack

    class FloodDomainPackWithMasks(FloodFactorMaskMixin, FloodDomainPack):
        """The frozen flood pack, plus the ablation hook. Nothing else."""

        name: str = MASKED_DOMAIN_NAME

    return FloodDomainPackWithMasks


def register(name: str = MASKED_DOMAIN_NAME) -> str:
    """Register the masked pack under ``name`` and return that name.

    Registering under ``"flood"`` is refused: the production pack is what
    every paper run resolves, and replacing it in-process to run an
    ablation is exactly the kind of quiet substitution this framework
    exists to make impossible.
    """
    if name == "flood":
        raise ValueError(
            "Refusing to register the masked pack as 'flood'. Use a distinct "
            f"name (default {MASKED_DOMAIN_NAME!r}) so the production pack "
            "stays the one every run resolves."
        )
    from broker.domains.registry import DomainPackRegistry

    DomainPackRegistry.register(name, build_masked_flood_pack()())
    return name
