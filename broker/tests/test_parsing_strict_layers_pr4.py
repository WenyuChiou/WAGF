"""PR-4: ``global_config.parsing.strict_layers`` (default OFF).

``UnifiedAdapter.parse_output`` resolves a decision through a chain of eleven
fallback routes. Five of them can decide a row from a DIGIT, and only one of
those five is gated by the per-agent-type ``parsing.strict_mode`` YAML key --
which is also the key whose name promises the gating. In a TAE submission run
343 of 3,276 rows (10.47%) were decided by the ungated naked-digit route
alone.

``strict_layers`` disables every digit route that is not scoped to a decision
line, and leaves the decision-line routes running because ``Decision: 3`` is
what the prompt asks the model to emit. What each route does under the flag:

===  ==========================================  ==========================
  #  Route                                       ON behaviour
===  ==========================================  ==========================
  1  enclosure extraction                        unchanged
  2  JSON decision-key resolution                unchanged
  3  json_plus_digit recovery                    DISABLED + warning
  4  JSON-decode exception                       records a warning
  5  keyword decision-line digit                 FIRES, re-anchored
  6  keyword choice phrase ("I choose 3")        FIRES
  7  keyword skill-name recovery (dead OFF)      FIRES, decision-line only
  8  naked digit anywhere                        DISABLED + warning
  9  bracket/digit LAST RESORT (both arms)       DISABLED + warning
 10  domain default                              unchanged
 11  return None -> retry                        warnings no longer lost
===  ==========================================  ==========================

Routes 5 and 6 are relabelled ``parse_layer == "keyword+digit"`` (from a flat
``"keyword"``) so ``parse_layer_digit_share`` keeps counting them: "the digit
routes are closed" is true only of the routes that are, and the counter has to
keep being able to say so. Route 7 gets its own ``"fuzzy_name"`` layer at the
0.50 recovery tier.

Every flag-ON expectation below is FALSIFIED against the same input parsed by
``broker/utils/parsing/unified_adapter.py`` exactly as it stood at
``HEAD_COMMIT`` -- fetched live via ``git show``, never hand-transcribed, so a
mistake in retyping the old code cannot masquerade as a passing test. A test
that only asserts the new behaviour cannot tell a real fix from a no-op.
"""
from __future__ import annotations

import copy
import logging
import re
import subprocess
import sys
import types
from pathlib import Path
from types import SimpleNamespace

import pytest

from broker.core._audit_helpers import AuditMixin, _classify_decision_source
from broker.core._retry_loop import RetryMixin
from broker.interfaces.skill_types import SkillOutcome, SkillProposal
from broker.utils.agent_config import AgentTypeConfig
from broker.utils.model_adapter import UnifiedAdapter
from broker.utils.parsing.unified_adapter import (
    DECISION_VALUE_DIGIT_RE,
    _PARSING_FLAG_WARNED,
    _sanitize_warning,
    resolve_strict_layers_flag,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = str(Path("examples/single_agent/agent_types.yaml"))
CTX = {"agent_id": "H0001", "agent_type": "household"}
CTX_RETRY = dict(CTX, retry_attempt=1)

#: The commit this PR-4 stack branch was cut from (stack PR-3 tip).
HEAD_COMMIT = "fece4ed4"


# ---------------------------------------------------------------------------
# Adversarial fixture texts
#
# Each avoids naming a household skill alias BY ACCIDENT: "relocated" and
# "moved" do not match `\brelocate\b` / `\bmove\b`, and none contains a bare
# "wait" / "nothing" / "he" / "insurance" except where the fixture is about
# exactly that. Verified against the real actions block, not eyeballed.
# ---------------------------------------------------------------------------

# Route 8. The digit describes a FACT ABOUT NEIGHBOURS, not the agent's choice.
TEXT_PROSE_DIGIT = (
    "I have thought about this for years. About 3 of my neighbors relocated "
    "after the last flood, but I remain undecided about what to do."
)

# Route 8, JSON variant: the digit lives in an unrelated JSON field.
TEXT_JSON_STRAY_DIGIT = (
    '{"strategy": "gather more information", "confidence": 3, '
    '"reasoning": "still evaluating before committing"}'
)

# Routes 10/11: nothing parses and there is no digit to guess from either.
TEXT_UNPARSEABLE = (
    "I have thought about this for a long time and I remain deeply uncertain "
    "about what to do given everything happening around here."
)

# Route 7's verified false positive. Names exactly one skill alias
# ("insurance") in prose that NEGATES it, with no decision line anywhere.
TEXT_NEGATION_PROSE = (
    "After weighing the costs again, in the end I will not purchase "
    "insurance this year."
)

# Route 3 in isolation: JSON parses, no decision key, and the trailing digit
# is NOT behind a decision keyword, so no keyword route can recover it either.
TEXT_JSON_PLUS_DIGIT_NO_KEYWORD = (
    "<<<DECISION_START>>>\n"
    '{"strategy": "gather more information"}\n'
    "3 households nearby have already left\n"
    "<<<DECISION_END>>>"
)

# Route 3 suppressed, route 5 then legitimately recovers the SAME digit --
# "Decision: 3" is the contract, and the flag must not break it.
TEXT_JSON_PLUS_DIGIT_RECOVERY = (
    "<<<DECISION_START>>>\n"
    '{"strategy": "gather more information"} Decision: 3\n'
    "<<<DECISION_END>>>"
)

# Route 5, clean: the decision-line digit that must keep working.
TEXT_DECISION_LINE_DIGIT = "Decision: 3\nThat is what I have settled on."

# Route 5's false positive: a digit on the decision line that is NOT the
# decision. Flag-OFF `re.search(r'(\d)')` scopes to the LINE, not the VALUE.
TEXT_DECISION_LINE_PROSE_DIGIT = "Decision: I will revisit this in 2 or three years."

# Route 9 in isolation: "12" has no single-digit word boundary, so route 8's
# `\b(\d)\b` misses it entirely and only the bracket/digit layer's
# `findall(r'(\d)')` -> last candidate "2" can claim the row.
TEXT_MULTIDIGIT = (
    "I estimate around 12 households in my area face similar risk this year."
)

# The happy path: nothing in this PR may touch it.
TEXT_CLEAN_JSON = (
    "<<<DECISION_START>>>\n"
    '{"decision": 2, "magnitude_pct": 10}\n'
    "<<<DECISION_END>>>"
)

ADVERSARIAL_TEXTS = {
    "clean_json": TEXT_CLEAN_JSON,
    "decision_line_digit": TEXT_DECISION_LINE_DIGIT,
    "decision_line_prose_digit": TEXT_DECISION_LINE_PROSE_DIGIT,
    "json_plus_digit_no_keyword": TEXT_JSON_PLUS_DIGIT_NO_KEYWORD,
    "json_plus_digit_recovery": TEXT_JSON_PLUS_DIGIT_RECOVERY,
    "json_stray_digit": TEXT_JSON_STRAY_DIGIT,
    "multidigit": TEXT_MULTIDIGIT,
    "negation_prose": TEXT_NEGATION_PROSE,
    "prose_digit": TEXT_PROSE_DIGIT,
    "unparseable": TEXT_UNPARSEABLE,
}


# ---------------------------------------------------------------------------
# Adapter construction helpers
# ---------------------------------------------------------------------------

def _make_adapter(*, strict_layers: bool = False, strict_mode: "bool | None" = None,
                  trim_aliases: bool = False, adapter_cls=UnifiedAdapter):
    """A household ``UnifiedAdapter`` over a PRIVATE deep-copy of the real
    single_agent config, so mutating it never touches the shared
    ``AgentTypeConfig`` cache other tests read (the pattern
    ``broker/tests/test_params_extractor.py`` established).

    ``trim_aliases`` cuts the household actions down to bare skill ids. The
    shipped alias lists are rich enough ("insurance", "move", "wait") that
    route 1b claims every decision line before route 7 can, so route 7 is only
    reachable on a domain whose aliases do NOT already spell out the spaced
    form -- which is the domain shape route 7 exists for.
    """
    AgentTypeConfig.clear_cache()
    adapter = adapter_cls(agent_type="household", config_path=CONFIG_PATH)
    adapter.agent_config._config = copy.deepcopy(adapter.agent_config._config)
    global_config = adapter.agent_config._config.setdefault("global_config", {})
    global_config.setdefault("parsing", {})["strict_layers"] = strict_layers
    if strict_mode is not None:
        adapter.agent_config._config["household"]["parsing"]["strict_mode"] = strict_mode
    if trim_aliases:
        adapter.agent_config._config["household"]["actions"] = [
            {"id": "buy_insurance", "aliases": ["buy_insurance"], "description": "x"},
            {"id": "relocate", "aliases": ["relocate"], "description": "y"},
        ]
    AgentTypeConfig.clear_cache()
    return adapter


def _sig(proposal):
    """The full serialised proposal — ``to_dict()`` is what actually reaches
    the JSONL trace and (via ``trace_to_csv_row``) the audit CSV, so comparing
    it is comparing the published bytes rather than a hand-picked subset that
    could omit exactly the field a regression moved.
    """
    return None if proposal is None else proposal.to_dict()


def _layer(proposal):
    """(skill, parse_layer, parse_confidence) — the triple every route table
    assertion below is about."""
    if proposal is None:
        return None
    return (proposal.skill_name, proposal.parse_layer, proposal.parse_confidence)


def _warnings(proposal):
    return tuple(proposal.parsing_warnings) if proposal is not None else ()


def _suppressions(proposal):
    return tuple(w for w in _warnings(proposal) if "suppressed candidate digit" in w)


@pytest.fixture(scope="module")
def head_unified_adapter_cls():
    """``broker/utils/parsing/unified_adapter.py`` exactly as it stood at
    HEAD_COMMIT, BEFORE any PR-4 edit — fetched live via ``git show``.

    Executed into a synthetic module registered under the REAL package name
    (``broker.utils.parsing``) so its relative imports resolve against the
    current, otherwise-unchanged sibling modules, exactly as they did when
    this file was HEAD. The module is popped from ``sys.modules`` right after
    ``exec`` (imports run once, at exec time); the returned class still holds
    a normal reference to ``mod.__dict__`` as its ``__globals__``.

    FAILS, never skips, when the commit is unreachable. This fixture is the
    only thing standing behind the byte-identity invariant, and a skip would
    let CI go green having proven nothing — which is precisely the
    local-green-is-not-shipped-green failure. Two ways it can go unreachable,
    and both are fixable rather than skippable: a shallow clone (the CI
    checkouts pass ``fetch-depth: 0`` for this reason), and a rebase or squash
    of the stack that rewrites ``HEAD_COMMIT`` out of existence. On a squash,
    RE-PIN this constant to the new pre-PR-4 commit — do not restore the skip.
    """
    result = subprocess.run(
        ["git", "show", f"{HEAD_COMMIT}:broker/utils/parsing/unified_adapter.py"],
        cwd=str(REPO_ROOT), capture_output=True, text=True, encoding="utf-8",
    )
    if result.returncode != 0:
        pytest.fail(
            f"git show {HEAD_COMMIT}:broker/utils/parsing/unified_adapter.py failed: "
            f"{result.stderr.strip()}\n"
            f"The flag-OFF byte-identity guard cannot run without the pre-PR-4 "
            f"snapshot. If this is a shallow clone, set `fetch-depth: 0` on the "
            f"checkout. If the stack was rebased or squashed, re-pin HEAD_COMMIT "
            f"to the new pre-PR-4 commit. Do NOT convert this back to a skip."
        )
    source = result.stdout
    assert "strict_layers" not in source, (
        f"the {HEAD_COMMIT} snapshot unexpectedly mentions strict_layers — "
        f"wrong commit, or PR-4 landed before {HEAD_COMMIT}. This fixture must "
        f"capture PRE-PR-4 code or every falsification below is vacuous."
    )
    mod_name = "broker.utils.parsing._pr4_head_snapshot"
    mod = types.ModuleType(mod_name)
    mod.__file__ = f"<git show {HEAD_COMMIT}:broker/utils/parsing/unified_adapter.py>"
    mod.__package__ = "broker.utils.parsing"
    sys.modules[mod_name] = mod
    try:
        exec(compile(source, mod.__file__, "exec"), mod.__dict__)
    finally:
        sys.modules.pop(mod_name, None)
    return mod.UnifiedAdapter


# ---------------------------------------------------------------------------
# 1. Flag-OFF byte identity against HEAD
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("strict_mode", [True, False], ids=["strict", "relaxed"])
@pytest.mark.parametrize("retry", [False, True], ids=["first", "retry"])
@pytest.mark.parametrize("name", sorted(ADVERSARIAL_TEXTS))
def test_flag_off_byte_identical_to_head(name, retry, strict_mode, head_unified_adapter_cls):
    """HARD CONSTRAINT: flag OFF (the default), ``parse_output`` serialises
    byte-for-byte as it did at HEAD, on every adversarial fixture, in both
    ``strict_mode`` regimes and on both the first attempt and a retry —
    the full grid, because the routes this PR touches are gated on all three.
    """
    text = ADVERSARIAL_TEXTS[name]
    ctx = CTX_RETRY if retry else CTX
    current = _make_adapter(strict_layers=False, strict_mode=strict_mode)
    head = _make_adapter(strict_layers=False, strict_mode=strict_mode,
                         adapter_cls=head_unified_adapter_cls)
    current_sig = _sig(current.parse_output(text, ctx))
    head_sig = _sig(head.parse_output(text, ctx))
    assert current_sig == head_sig, (
        f"flag-OFF parse_output for {name!r} (strict_mode={strict_mode}, "
        f"retry={retry}) diverged from HEAD ({HEAD_COMMIT})"
    )


def test_flag_off_keyword_layer_matches_head_directly(head_unified_adapter_cls):
    """The same guarantee for ``_parse_keywords`` on its own, so a divergence
    there cannot be masked by a later layer in ``parse_output`` happening to
    reach the same answer."""
    current = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    for text in ADVERSARIAL_TEXTS.values():
        assert (current._parse_keywords(text, "household", CTX)
                == head._parse_keywords(text, "household", CTX)), text[:60]


def test_flag_off_never_stamps_strict_layers_applied():
    """The D5 provenance attribute must not exist flag-OFF — ``getattr`` on
    the audit side then resolves False and classification is unchanged."""
    off = _make_adapter(strict_layers=False, strict_mode=False)
    proposal = off.parse_output(TEXT_UNPARSEABLE, CTX)
    assert proposal is not None
    assert not hasattr(proposal, "strict_layers_applied")


def test_strict_layers_applied_never_serialises():
    """D5: the attribute rides the object, never the trace. ``to_dict()``
    builds from an explicit key list, and this test is what stops someone
    "tidying" it into a dataclass field and silently adding a JSONL/CSV key to
    every published corpus."""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    off = _make_adapter(strict_layers=False, strict_mode=False)
    p_on = on.parse_output(TEXT_UNPARSEABLE, CTX)
    p_off = off.parse_output(TEXT_UNPARSEABLE, CTX)
    assert p_on.strict_layers_applied is True
    assert "strict_layers_applied" not in p_on.to_dict()
    assert set(p_on.to_dict()) == set(p_off.to_dict())


# ---------------------------------------------------------------------------
# 2. Route table — flag-ON behaviour, each falsified against HEAD
# ---------------------------------------------------------------------------

def test_route8_naked_digit_disabled_prose(head_unified_adapter_cls):
    """Route 8. "3 of my neighbors relocated" is a fact about neighbours.
    Flag-OFF the ungated naked-digit layer makes it the agent's decision."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    assert _layer(off.parse_output(TEXT_PROSE_DIGIT, CTX)) == ("relocate", "digit", 0.50)
    # Falsification: HEAD does the same wrong thing, so the fix is real.
    assert _layer(head.parse_output(TEXT_PROSE_DIGIT, CTX)) == ("relocate", "digit", 0.50)
    assert on.parse_output(TEXT_PROSE_DIGIT, CTX) is None


def test_route8_naked_digit_disabled_json(head_unified_adapter_cls):
    """Route 8, JSON variant: the digit is an unrelated ``"confidence": 3``,
    and flag-OFF the row is also stamped 0.95 — the schema's HIGHEST
    confidence — because the tier check tested "json" before "digit"."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    expected_off = ("relocate", "enclosure+json+digit", 0.95)
    assert _layer(off.parse_output(TEXT_JSON_STRAY_DIGIT, CTX)) == expected_off
    assert _layer(head.parse_output(TEXT_JSON_STRAY_DIGIT, CTX)) == expected_off
    assert on.parse_output(TEXT_JSON_STRAY_DIGIT, CTX) is None


def test_route8_strict_mode_true_returns_none_under_flag(head_unified_adapter_cls):
    """The ``strict_mode: true`` regime explicitly: a suppressed row does NOT
    become a default, it becomes ``None`` -> retry -> REJECTED_FALLBACK or an
    ABORTED sentinel. ``decision_source == "default_substituted"`` is
    unreachable here, which is why the docs state both regimes."""
    on = _make_adapter(strict_layers=True, strict_mode=True)
    head = _make_adapter(strict_layers=False, strict_mode=True,
                         adapter_cls=head_unified_adapter_cls)
    assert on.parse_output(TEXT_PROSE_DIGIT, CTX) is None
    assert head.parse_output(TEXT_PROSE_DIGIT, CTX) is not None


def test_route8_disabled_row_falls_to_default_with_warning(head_unified_adapter_cls):
    """The ``strict_mode: false`` regime, on a DIGIT-BEARING input — the row
    genuinely had a digit to take and did not take it. (An input with no digit
    would reach ``default`` flag-OFF too and prove nothing.)"""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    off = _make_adapter(strict_layers=False, strict_mode=False)
    head = _make_adapter(strict_layers=False, strict_mode=False,
                         adapter_cls=head_unified_adapter_cls)

    p_on = on.parse_output(TEXT_PROSE_DIGIT, CTX)
    p_off = off.parse_output(TEXT_PROSE_DIGIT, CTX)
    p_head = head.parse_output(TEXT_PROSE_DIGIT, CTX)

    assert _layer(p_off) == _layer(p_head) == ("relocate", "digit", 0.50)
    assert _layer(p_on) == ("do_nothing", "default", 0.20)  # parsing.default_skill
    assert any("naked-digit layer" in w for w in _suppressions(p_on))
    assert any("Default skill 'do_nothing' used." in w for w in _warnings(p_on))
    # Falsification: neither OFF nor HEAD carries a STRICT_LAYERS warning.
    assert not any("STRICT_LAYERS" in w for w in _warnings(p_off))
    assert not any("STRICT_LAYERS" in w for w in _warnings(p_head))


def test_route8_warning_only_when_a_digit_was_actually_available(head_unified_adapter_cls):
    """The suppression warning marks the rows where the flag CHANGED the
    answer. An unconditional "this layer is disabled" line on every row that
    reaches route 8 restates the config and buries the rows that matter."""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    p_digitless = on.parse_output(TEXT_UNPARSEABLE, CTX)
    p_digit = on.parse_output(TEXT_PROSE_DIGIT, CTX)
    assert _suppressions(p_digitless) == ()
    assert any("naked-digit layer" in w for w in _suppressions(p_digit))


def test_route3_json_plus_digit_disabled(head_unified_adapter_cls):
    """Route 3. Its keyword prefix ``(?:decision|choice|id|:)?`` is OPTIONAL,
    so it takes any digit trailing the JSON block — here "3 households nearby
    have already left"."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)
    on_relaxed = _make_adapter(strict_layers=True, strict_mode=False)

    expected_off = ("relocate", "json_plus_digit", 0.95)
    assert _layer(off.parse_output(TEXT_JSON_PLUS_DIGIT_NO_KEYWORD, CTX)) == expected_off
    assert _layer(head.parse_output(TEXT_JSON_PLUS_DIGIT_NO_KEYWORD, CTX)) == expected_off
    assert on.parse_output(TEXT_JSON_PLUS_DIGIT_NO_KEYWORD, CTX) is None

    p = on_relaxed.parse_output(TEXT_JSON_PLUS_DIGIT_NO_KEYWORD, CTX)
    assert _layer(p) == ("do_nothing", "default", 0.20)
    assert any("json_plus_digit recovery" in w for w in _suppressions(p))


def test_route3_disabled_but_route5_still_recovers_the_contract(head_unified_adapter_cls):
    """Disabling route 3 must not cost the row a legitimate ``Decision: 3``
    that happens to sit after a JSON block: route 5 picks it up, and the row
    lands at the DIGIT tier (0.50) instead of the JSON tier (0.95) that
    flag-OFF awarded it."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    p_off = off.parse_output(TEXT_JSON_PLUS_DIGIT_RECOVERY, CTX)
    p_head = head.parse_output(TEXT_JSON_PLUS_DIGIT_RECOVERY, CTX)
    p_on = on.parse_output(TEXT_JSON_PLUS_DIGIT_RECOVERY, CTX)

    assert _layer(p_off) == _layer(p_head) == ("relocate", "json_plus_digit", 0.95)
    assert _layer(p_on) == ("relocate", "enclosure+json+keyword+digit", 0.50)
    assert any("json_plus_digit recovery" in w for w in _suppressions(p_on))


def test_route5_decision_line_digit_still_fires_and_is_labelled(head_unified_adapter_cls):
    """Route 5 SURVIVES — ``Decision: 3`` is the documented prompt contract —
    but stops hiding inside a flat "keyword" at the 0.70 tier."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    p_off = off.parse_output(TEXT_DECISION_LINE_DIGIT, CTX)
    p_head = head.parse_output(TEXT_DECISION_LINE_DIGIT, CTX)
    p_on = on.parse_output(TEXT_DECISION_LINE_DIGIT, CTX)

    assert _layer(p_off) == _layer(p_head) == ("relocate", "keyword", 0.70)
    assert _layer(p_on) == ("relocate", "keyword+digit", 0.50)
    # The point of the relabel: audit.audit_coverage counts "digit" by
    # substring, so this row is now visible in parse_layer_digit_share.
    assert "digit" in p_on.parse_layer
    assert "digit" not in p_off.parse_layer


def test_route5_anchor_rejects_a_digit_that_is_not_the_decision(head_unified_adapter_cls):
    """Route 5's flag-OFF ``re.search(r'(\\d)')`` scopes to the decision LINE,
    not to the decision VALUE, so "revisit this in 2 or three years" resolves
    to skill 2. The anchored form requires the digit to BE the value."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    expected_off = ("elevate_house", "keyword", 0.70)
    assert _layer(off.parse_output(TEXT_DECISION_LINE_PROSE_DIGIT, CTX)) == expected_off
    assert _layer(head.parse_output(TEXT_DECISION_LINE_PROSE_DIGIT, CTX)) == expected_off
    assert on.parse_output(TEXT_DECISION_LINE_PROSE_DIGIT, CTX) is None


@pytest.mark.parametrize("raw_val,expected", [
    # ACCEPT — the decision-line value, in the shapes it really arrives in.
    (': "3",', "3"),        # SmartRepairPreprocessor's rewrite of `Decision: 3`
    (': "3"', "3"),
    (": 3", "3"),
    ("= 3", "3"),
    (": [3]", "3"),         # the documented `[N]` alias shape
    (": (3)", "3"),
    (": `3`", "3"),
    ('": 3', "3"),          # quote BEFORE the colon, from `"decision": 3`
    ("': 3,", "3"),         # single-quoted JSON — the commonest small-model shape
    ("is 3", "3"),          # "my decision is 3"
    ("**3** is final.", "3"),
    # REJECT — prose sits between the keyword and the digit.
    (": i will revisit this in 2 or three years.", None),
    (": relocate within 3 years", None),
    (": my third choice is 2", None),
    ("is my third choice, 2", None),
    (": we lost 2 homes last year, still deciding", None),
])
def test_route5_anchor_regex_shape(raw_val, expected):
    """The anchor pinned directly, against the PRODUCTION constant — not a
    literal retyped here, which would assert nothing about the code and would
    keep passing after someone edited the parser.

    The wrapper class has to be this wide because the layer sees PREPROCESSED
    text: ``Decision: 3`` reaches it as ``: "3",``, and ``"decision": 3`` /
    ``{'decision': 3,`` put the quote BEFORE the separator. Single-quoted JSON
    is the commonest malformed-JSON shape from small models and is exactly the
    case where the JSON layer fails and route 5 is what catches the contract —
    a narrower anchor would have rejected the contract it exists to honour.
    """
    m = DECISION_VALUE_DIGIT_RE.match(raw_val)
    assert (m.group(1) if m else None) == expected


@pytest.mark.parametrize("raw_val,expected", [
    # ACCEPT -- a short lead-in from the whitelist (option|choice|number|#|
    # ->|>|is|my choice is) between the separator and the digit.
    (": option 3", "3"),
    (": Option 3".lower(), "3"),
    (": #3", "3"),
    (": number 3", "3"),
    (": -> 3", "3"),
    (": >>> 3", "3"),
    (": my choice is 3", "3"),
    # REJECT -- prose sits between the keyword and the digit, even when a
    # whitelisted word (here "option") appears later in the same string: the
    # anchor is `.match`, not `.search`, so a match sitting mid-string can
    # never be reached.
    (": i will revisit this in 2 or three years time.", None),
    (": i will not relocate this year (option 3 is too costly for the 2 "
     "of us).", None),
])
def test_route5_anchor_regex_lead_in_whitelist(raw_val, expected):
    """Reviewer follow-up on the PR-4 diff: the anchor was too narrow to
    accept legitimate decision-line shapes a model reasonably produces
    (``Decision: Option 3``, ``Decision: #3``, ``Decision: -> 3``, ...)
    while it must keep rejecting prose that merely mentions a digit or an
    option number in passing. Pinned against the PRODUCTION constant, same
    discipline as ``test_route5_anchor_regex_shape`` above.
    """
    m = DECISION_VALUE_DIGIT_RE.match(raw_val)
    assert (m.group(1) if m else None) == expected


def test_route5_lead_in_whitelist_shapes_survive_the_flag():
    """The lead-in shapes end to end, through ``parse_output``: each must
    still resolve under the flag, at the digit tier -- widening the anchor
    must not cost the row its parse_layer/parse_confidence classification."""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    off = _make_adapter(strict_layers=False, strict_mode=False)
    for text in (
        "Decision: Option 3",
        "Decision: option 3",
        "Decision: #3",
        "Decision: number 3",
        "Decision: -> 3",
        "Decision: >>> 3",
        "Decision: my choice is 3",
    ):
        p_on = on.parse_output(text, CTX)
        p_off = off.parse_output(text, CTX)
        assert p_off is not None and p_off.skill_name == "relocate", text
        assert p_on is not None, f"flag ON lost the lead-in contract for {text!r}"
        assert p_on.skill_name == "relocate", text
        assert "digit" in p_on.parse_layer, (text, p_on.parse_layer)
        assert p_on.parse_confidence == 0.50, (text, p_on.parse_confidence)


def test_route5_anchor_rejection_is_recorded():
    """C2: an anchor rejection is a SUPPRESSION, and every other suppression
    under this flag records itself. Silent, an over-tight anchor would surface
    only as an unexplained rise in `default` / ABORTED rows."""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    sink = []
    res = on._parse_keywords(
        "Decision: I will revisit this in 2 or three years.", "household", CTX,
        strict_layers=True, warnings_sink=sink,
    )
    assert res is None
    assert any("rejected by the value anchor" in w and " 2 " in w for w in sink), sink
    # Through parse_output, the reason reaches the row that took the default.
    p = on.parse_output(TEXT_DECISION_LINE_PROSE_DIGIT, CTX)
    assert _layer(p) == ("do_nothing", "default", 0.20)
    assert any("rejected by the value anchor" in w for w in _warnings(p))


def test_route5_contract_shapes_survive_the_flag():
    """The shapes above, end to end: each must still resolve under the flag,
    at the digit tier. A hardening pass that silently drops the documented
    contract is a regression wearing a feature's name."""
    on = _make_adapter(strict_layers=True, strict_mode=False)
    off = _make_adapter(strict_layers=False, strict_mode=False)
    for text in (
        'Decision: 3',
        '"decision": 3',
        "<<<DECISION_START>>>\n{'decision': 3,\n<<<DECISION_END>>>",
        "my decision is 3",
        "Decision: (3)",
        "Decision: `3`",
        "The decision **3** is final.",
    ):
        p_on = on.parse_output(text, CTX)
        p_off = off.parse_output(text, CTX)
        assert p_off is not None and p_off.skill_name == "relocate", text
        assert p_on is not None, f"flag ON lost the contract for {text!r}"
        assert p_on.skill_name == "relocate", text
        assert "digit" in p_on.parse_layer, (text, p_on.parse_layer)


def test_route9_bracket_digit_disabled_relaxed_arm(head_unified_adapter_cls):
    """Route 9, ``strict_mode: false`` arm. "12" has no single-digit word
    boundary, so route 8 cannot claim it — only route 9's
    ``findall(r'(\\d)')[-1]`` can, which isolates this route."""
    off = _make_adapter(strict_layers=False, strict_mode=False)
    head = _make_adapter(strict_layers=False, strict_mode=False,
                         adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True, strict_mode=False)

    expected_off = ("elevate_house", "digit_fallback", 0.50)
    assert _layer(off.parse_output(TEXT_MULTIDIGIT, CTX)) == expected_off
    assert _layer(head.parse_output(TEXT_MULTIDIGIT, CTX)) == expected_off

    p_on = on.parse_output(TEXT_MULTIDIGIT, CTX)
    assert _layer(p_on) == ("do_nothing", "default", 0.20)
    assert any("bracket/digit last-resort layer" in w for w in _suppressions(p_on))
    assert not any("Retry-based extraction from digit" in w for w in _warnings(p_on))


def test_route9_bracket_digit_disabled_retry_arm(head_unified_adapter_cls):
    """Route 9's OTHER arm, the one a ``strict_mode: true`` operator does not
    know exists: ``retry_attempt > 0`` bypasses strict_mode entirely, so the
    guessing happens on exactly the attempt where the model already failed to
    answer cleanly once."""
    off = _make_adapter(strict_layers=False, strict_mode=True)
    head = _make_adapter(strict_layers=False, strict_mode=True,
                         adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True, strict_mode=True)

    # First attempt: strict_mode blocks it, so the retry is what differs.
    assert off.parse_output(TEXT_MULTIDIGIT, CTX) is None

    expected_retry = ("elevate_house", "digit_fallback", 0.50)
    assert _layer(off.parse_output(TEXT_MULTIDIGIT, CTX_RETRY)) == expected_retry
    assert _layer(head.parse_output(TEXT_MULTIDIGIT, CTX_RETRY)) == expected_retry
    assert on.parse_output(TEXT_MULTIDIGIT, CTX_RETRY) is None


def test_route7_whole_text_search_would_be_a_false_positive():
    """Why route 7 is scoped rather than simply un-deadened. A whole-text
    ``re.search`` — the obvious "fix" — resolves this NEGATED sentence to
    buy_insurance at the keyword tier (0.70): the opposite of what the agent
    said, recorded with more confidence than a decision-line digit gets."""
    adapter = _make_adapter(strict_layers=False)
    valid_skills = adapter.agent_config.get_valid_actions("household")
    naive = set()
    for s in valid_skills:
        for variant in (s.lower(), s.lower().replace("_", " ")):
            if re.search(rf"\b{re.escape(variant)}\b", TEXT_NEGATION_PROSE.lower()):
                naive.add(s)
                break
    assert naive == {"insurance"}, (
        "fixture drifted: this test is only meaningful while a whole-text "
        "search resolves this negated sentence to exactly one skill"
    )


def test_route7_scoping_refuses_the_negated_prose(head_unified_adapter_cls):
    """Route 7 under the flag: no decision line exists, so it cannot fire at
    all — the whole-text false positive above never gets the chance."""
    off = _make_adapter(strict_layers=False)
    head = _make_adapter(strict_layers=False, adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True)

    assert off._parse_keywords(TEXT_NEGATION_PROSE, "household", CTX) is None
    assert head._parse_keywords(TEXT_NEGATION_PROSE, "household", CTX) is None
    assert on._parse_keywords(
        TEXT_NEGATION_PROSE, "household", CTX, strict_layers=True) is None
    assert on.parse_output(TEXT_NEGATION_PROSE, CTX) is None


def test_route7_fires_on_a_real_decision_line(head_unified_adapter_cls):
    """Route 7 is scoped, not merely disabled under another name: when the
    model DOES name the skill on its decision line, the layer resolves it,
    with its own parse_layer and the 0.50 recovery tier."""
    text = "Decision: I lean towards buy insurance for my family."
    off = _make_adapter(strict_layers=False, trim_aliases=True)
    head = _make_adapter(strict_layers=False, trim_aliases=True,
                         adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True, trim_aliases=True)

    # Dead flag-OFF: the `in` test compares the model's text against the regex
    # SOURCE string, so only a model that emits `\bbuy insurance\b` verbatim
    # can trip it. HEAD agrees — the bug predates PR-4.
    assert off._parse_keywords(text, "household", CTX) is None
    assert head._parse_keywords(text, "household", CTX) is None

    sink = []
    res = on._parse_keywords(text, "household", CTX,
                             strict_layers=True, warnings_sink=sink)
    assert res["skill_name"] == "buy_insurance"
    assert res["reasoning"] == {"parse_mode": "fuzzy_name"}
    assert any("skill-name recovery" in w for w in sink)

    p_on = on.parse_output(text, CTX)
    assert _layer(p_on) == ("buy_insurance", "fuzzy_name", 0.50)
    assert any("skill-name recovery" in w for w in _warnings(p_on))
    assert off.parse_output(text, CTX) is None


def test_route4_json_exception_now_recorded(head_unified_adapter_cls):
    """Route 4. A row that fell all the way through to the default carried no
    record of WHY the JSON attempt failed — the ``except`` was a bare
    ``pass``."""
    off = _make_adapter(strict_layers=False, strict_mode=False)
    head = _make_adapter(strict_layers=False, strict_mode=False,
                         adapter_cls=head_unified_adapter_cls)
    on = _make_adapter(strict_layers=True, strict_mode=False)

    def has_json_warning(p):
        return any("JSON parse attempt failed" in w for w in _warnings(p))

    assert not has_json_warning(off.parse_output(TEXT_UNPARSEABLE, CTX))
    assert not has_json_warning(head.parse_output(TEXT_UNPARSEABLE, CTX))
    assert has_json_warning(on.parse_output(TEXT_UNPARSEABLE, CTX))


def test_route1_and_2_and_10_untouched(head_unified_adapter_cls):
    """Routes 1, 2 and 10 — the happy path and the plain default — must read
    identically in both flag states. A hardening pass that quietly moves the
    common case is worse than no pass."""
    for strict_mode, text in ((True, TEXT_CLEAN_JSON), (False, TEXT_UNPARSEABLE)):
        off = _make_adapter(strict_layers=False, strict_mode=strict_mode)
        on = _make_adapter(strict_layers=True, strict_mode=strict_mode)
        assert _layer(off.parse_output(text, CTX)) == _layer(on.parse_output(text, CTX))


def test_new_warnings_carry_no_pipe():
    """D6: ``trace_to_csv_row`` joins parsing_warnings with "|", so a pipe
    inside one warning splits it in two for anyone parsing the field back."""
    assert _sanitize_warning("a | b | c") == "a / b / c"
    on = _make_adapter(strict_layers=True, strict_mode=False)
    for text in ADVERSARIAL_TEXTS.values():
        proposal = on.parse_output(text, CTX)
        for warning in _warnings(proposal):
            if "STRICT_LAYERS" in warning:
                assert "|" not in warning, warning


# ---------------------------------------------------------------------------
# 3. decision_source + the split-brain the flag used to have (D5)
# ---------------------------------------------------------------------------

def _approved(status="APPROVED"):
    return SimpleNamespace(skill_name="do_nothing", approval_status=status,
                           execution_mapping={})


def _proposal(parse_layer, *, applied=False):
    p = SkillProposal(
        skill_name="do_nothing", agent_id="A1", reasoning={},
        agent_type="household", parse_layer=parse_layer, parse_confidence=0.20,
    )
    if applied:
        p.strict_layers_applied = True
    return p


def test_classifier_reclassifies_only_approved_default():
    approved = _approved("APPROVED")
    default_off = _proposal("default")
    default_on = _proposal("default", applied=True)
    json_on = _proposal("enclosure+json", applied=True)

    # A proposal parsed with the flag OFF has no attribute: unchanged.
    assert _classify_decision_source(approved, default_off) == "llm_reasoned"
    assert _classify_decision_source(approved, default_on) == "default_substituted"
    # A real JSON parse is untouched even under the flag.
    assert _classify_decision_source(approved, json_on) == "llm_reasoned"

    # REJECTED_FALLBACK / REJECTED were already distinguishable from a real
    # decision via approval_status; the flag must not touch them.
    assert _classify_decision_source(
        _approved("REJECTED_FALLBACK"), default_on) == "fallback_default"
    assert _classify_decision_source(
        _approved("REJECTED"), default_on) == "validator_rejected"
    # Terminal parse failure and the legacy no-proposal call shape.
    assert _classify_decision_source(None, default_on) == "parse_failure"
    assert _classify_decision_source(approved, None) == "llm_reasoned"


def test_classifier_has_no_second_config_read():
    """D5, the split brain, asserted STRUCTURALLY rather than by example.

    The earlier draft resolved ``parsing.strict_layers`` a second time here,
    off the ENGINE's config, while the parser resolved it off the ADAPTER's —
    the same object in production, routinely different in tests and in any
    embedding that builds them separately. A proposal parsed under the flag
    could then be classified as though it had not been.

    The fix is that this function has NO config input at all, so there is
    nothing to disagree with. An example-based test cannot pin that: the bug
    would return the moment someone re-added a config parameter with a
    plausible default. Pin the signature instead, and pin the removal of the
    resolver that used to feed it.
    """
    import inspect

    import broker.core._audit_helpers as helpers

    params = list(inspect.signature(_classify_decision_source).parameters)
    assert params == ["approved_skill", "skill_proposal"], (
        f"a config/flag parameter is back on _classify_decision_source ({params}); "
        f"the parser is the only place strict_layers may be resolved"
    )
    assert not hasattr(helpers, "_parsing_strict_layers_flag"), (
        "the audit-side parsing-flag resolver is back — that is the second "
        "read this decision removed"
    )


class _StubWriter:
    def __init__(self):
        self.traces = []

    def write_trace(self, agent_type, trace, history=None):
        self.traces.append((agent_type, trace))


class _AuditHost(AuditMixin):
    """Minimal AuditMixin host exposing ONLY ``get_log_fields`` — deliberately
    no ``get_audit_corrected_status_columns`` and no
    ``get_parsing_strict_layers``, so this exercises the split-brain shape."""

    def __init__(self):
        self.audit_writer = _StubWriter()
        self.config = SimpleNamespace(get_log_fields=lambda agent_type: [])


def test_write_audit_trace_reclassifies_end_to_end():
    """Through the REAL write path, not just the classifier in isolation."""
    def write_one(applied: bool):
        host = _AuditHost()
        host._write_audit_trace(
            agent_type="household", context={}, run_id="r", step_id="Y1",
            timestamp="2026-09-01T00:00:00", env_context={"current_year": 1},
            seed=42, agent_id="A1", all_valid=True,
            prompt="p", raw_output="o", context_hash="h",
            memory_pre=[], memory_post=[],
            skill_proposal=_proposal("default", applied=applied),
            approved_skill=_approved("APPROVED"), execution_result=None,
            outcome=SkillOutcome.APPROVED,
            retry_count=0, format_retry_count=0, total_llm_stats={},
            all_validation_history=[],
        )
        return host.audit_writer.traces[-1][1]

    assert write_one(False)["decision_source"] == "llm_reasoned"
    assert write_one(True)["decision_source"] == "default_substituted"


def test_aborted_sentinel_carries_parsing_warnings():
    """D6: the ABORTED sentinel is the only row an unparsable step gets, and
    without this it says nothing about why the step failed. Empty warnings
    leave ``skill_proposal`` None, byte-identical to PR-3's sentinel."""
    host = _AuditHost()
    common = dict(
        agent_type="household", run_id="r", step_id="Y1",
        timestamp="2026-09-01T00:00:00", env_context={"current_year": 1},
        seed=42, agent_id="A1", raw_output="the model's text",
        format_retry_count=2,
    )
    host._write_aborted_sentinel_trace(**common)
    assert host.audit_writer.traces[-1][1]["skill_proposal"] is None

    host._write_aborted_sentinel_trace(
        parsing_warnings=["STRICT_LAYERS: suppressed candidate digit 3 -> relocate"],
        **common,
    )
    proposal_field = host.audit_writer.traces[-1][1]["skill_proposal"]
    assert proposal_field["parsing_warnings"] == [
        "STRICT_LAYERS: suppressed candidate digit 3 -> relocate"
    ]
    # raw_output is repeated because trace_to_csv_row reads that column off
    # skill_proposal FIRST; omitting it would blank the column.
    assert proposal_field["raw_output"] == "the model's text"


# ---------------------------------------------------------------------------
# 4. Retry loop: warnings from a failed attempt are not lost (D6)
# ---------------------------------------------------------------------------

class _FakeAuditor:
    def __getattr__(self, _name):
        return lambda *a, **k: None


class _ScriptedAdapter:
    """Returns a scripted sequence from ``parse_output``, stashing
    ``last_parse_warnings`` on each None exactly as UnifiedAdapter does under
    the flag."""

    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def parse_output(self, raw_output, context):
        item = self.script[self.calls] if self.calls < len(self.script) else None
        self.calls += 1
        if item is None:
            self.last_parse_warnings = [f"STRICT_LAYERS: attempt {self.calls} suppressed 3"]
            return None
        return item

    def format_retry_prompt(self, prompt, errors):
        return prompt


class _RetryHost(RetryMixin):
    def __init__(self, adapter):
        self.model_adapter = adapter
        self.auditor = _FakeAuditor()
        self.config = SimpleNamespace(get=lambda agent_type: {"parsing": {}})


def _run_retry(script):
    host = _RetryHost(_ScriptedAdapter(script))
    proposal, _raw, retries, _stats = host._invoke_llm_with_retries(
        "prompt", lambda p: "raw model text", {}, "A1", "household", {"current_year": 1},
    )
    return host, proposal, retries


def test_retry_loop_merges_stashed_warnings_into_the_next_proposal():
    """A failed attempt's warnings belong to the decision, and the decision
    is the row that eventually gets written."""
    later = SkillProposal(skill_name="relocate", agent_id="A1", reasoning={},
                          agent_type="household", parsing_warnings=["own warning"])
    host, proposal, retries = _run_retry([None, later])
    assert retries == 1
    assert proposal.parsing_warnings == [
        "STRICT_LAYERS: attempt 1 suppressed 3", "own warning",
    ]
    # Drained, so it cannot leak into the next agent's proposal.
    assert host.model_adapter.last_parse_warnings == []


def test_retry_loop_restashes_when_every_attempt_fails():
    """No proposal to merge into: the warnings go back on the adapter for the
    ABORTED sentinel to write."""
    host, proposal, _retries = _run_retry([None, None, None, None])
    assert proposal is None
    assert host.model_adapter.last_parse_warnings == [
        "STRICT_LAYERS: attempt 1 suppressed 3",
        "STRICT_LAYERS: attempt 2 suppressed 3",
        "STRICT_LAYERS: attempt 3 suppressed 3",
    ]


def test_retry_loop_clears_a_stale_stash_before_starting():
    """The leak this guards: an aborted step in a run WITHOUT
    ``audit.corrected_status_columns`` writes no sentinel, so nothing drains
    the stash — and the next agent's proposal would inherit another agent's
    parse warnings."""
    good = SkillProposal(skill_name="relocate", agent_id="A2", reasoning={},
                         agent_type="household")
    adapter = _ScriptedAdapter([good])
    adapter.last_parse_warnings = ["STRICT_LAYERS: left over from a previous step"]
    host = _RetryHost(adapter)
    proposal, _raw, _retries, _stats = host._invoke_llm_with_retries(
        "prompt", lambda p: "raw", {}, "A2", "household", {"current_year": 2},
    )
    assert proposal.parsing_warnings == []


def test_retry_loop_is_a_noop_when_the_flag_is_off():
    """Flag-OFF the adapter never creates the attribute, so every line of the
    D6 plumbing is a no-op and the proposal is untouched."""
    good = SkillProposal(skill_name="relocate", agent_id="A1", reasoning={},
                         agent_type="household", parsing_warnings=["own"])
    adapter = _ScriptedAdapter([good])
    assert not hasattr(adapter, "last_parse_warnings")
    host = _RetryHost(adapter)
    proposal, _raw, _retries, _stats = host._invoke_llm_with_retries(
        "prompt", lambda p: "raw", {}, "A1", "household", {"current_year": 1},
    )
    assert proposal.parsing_warnings == ["own"]
    assert not hasattr(adapter, "last_parse_warnings")


def test_retry_loop_stash_does_not_leak_across_threads():
    """C1. ``ExperimentRunner._run_agents_parallel`` submits ONE engine — and
    therefore one adapter — to a ThreadPoolExecutor whenever ``--workers > 1``.
    A plain instance attribute for the stash is a data race there, with two
    failure modes: agent A's suppression warning written onto agent B's audit
    row (a fabricated per-row fact inside the one feature whose whole purpose
    is per-row provenance), and B's drain erasing A's stash so A's reason
    reaches nothing at all.

    Both are driven here against the REAL ``UnifiedAdapter`` stash, on the real
    ``_invoke_llm_with_retries``, from two threads on one shared adapter.

    Both orderings were confirmed to REPRODUCE against the pre-fix shape (a
    plain instance attribute) before this test was written, so it is not
    vacuous: pre-fix FAST's proposal carries
    ``['STRICT_LAYERS: SLOW suppressed 3']`` and SLOW's stash is ``[]``.
    """
    import threading

    adapter = UnifiedAdapter.__new__(UnifiedAdapter)
    adapter.format_retry_prompt = lambda prompt, errors: prompt
    fast_drained = threading.Event()   # FAST is past its drain-at-start
    slow_stashed = threading.Event()   # SLOW's stash is live
    fast_done = threading.Event()      # FAST's whole step is over
    results = {}

    def parse_output(raw_output, context):
        if context.get("agent_id") == "SLOW":
            if not slow_stashed.is_set():   # stash once, on the first attempt
                adapter.last_parse_warnings = ["STRICT_LAYERS: SLOW suppressed 3"]
                slow_stashed.set()
                # Hold the stash live across FAST's ENTIRE parse-and-drain,
                # which is the window a shared attribute exposes.
                fast_done.wait(timeout=5)
            return None
        return SkillProposal(skill_name="relocate", agent_id="FAST",
                             reasoning={}, agent_type="household")

    adapter.parse_output = parse_output

    def llm_invoke_for(agent_id):
        def _invoke(_prompt):
            if agent_id == "FAST":
                fast_drained.set()            # drain-at-start already ran
                slow_stashed.wait(timeout=5)  # ...and SLOW has now stashed
            else:
                fast_drained.wait(timeout=5)
            return "raw"
        return _invoke

    def run(agent_id):
        proposal, _r, _c, _s = _RetryHost(adapter)._invoke_llm_with_retries(
            "p", llm_invoke_for(agent_id), {"agent_id": agent_id}, agent_id,
            "household", {"current_year": 1},
        )
        results[agent_id] = proposal
        # The re-stash is thread-local BY DESIGN, so it has to be read on the
        # thread that made it — reading from the main thread would see an
        # empty local and pass whatever the code did.
        results[agent_id + ":stash"] = list(adapter.last_parse_warnings)
        adapter.last_parse_warnings = []
        if agent_id == "FAST":
            fast_done.set()

    fast = threading.Thread(target=run, args=("FAST",))
    slow = threading.Thread(target=run, args=("SLOW",))
    fast.start()
    slow.start()
    fast.join(timeout=10)
    fast_done.set()
    slow.join(timeout=10)

    # Contamination: FAST never had a suppressed digit of its own.
    assert results["FAST"].parsing_warnings == [], (
        "SLOW's suppression warning leaked onto FAST's proposal — the "
        "shared-adapter race, fabricating a per-row audit fact"
    )
    assert results["FAST:stash"] == []
    # Destruction: FAST's drain must not have erased SLOW's live stash, so
    # SLOW's own reason is still there for its ABORTED sentinel to write.
    assert results["SLOW"] is None
    assert results["SLOW:stash"] == ["STRICT_LAYERS: SLOW suppressed 3"], (
        "SLOW lost its own suppression reason to FAST's drain — the row that "
        "records the parse failure would say nothing about why"
    )


def test_stash_is_only_the_flag_s_own_warnings_and_is_attempt_tagged():
    """W4. Stashing the WHOLE warning list would prepend a failed attempt's
    ``STRICT_MODE: Failed to parse any valid decision`` diagnostic onto
    whichever LATER attempt succeeded, so an analyst counting rows whose
    parsing_warnings mention a failed parse over-counts exactly under the flag.
    The attempt tag is what keeps a merged warning distinguishable from one
    this row produced."""
    on = _make_adapter(strict_layers=True, strict_mode=True)
    assert on.parse_output(TEXT_PROSE_DIGIT, CTX) is None
    stashed = on.last_parse_warnings
    assert stashed, "a suppressed strict_mode:true row must stash its reason"
    assert all(w.startswith("attempt 0: STRICT_LAYERS:") for w in stashed), stashed
    assert not any("STRICT_MODE: Failed to parse" in w for w in stashed), stashed
    on.last_parse_warnings = []


def test_end_to_end_aborted_step_carries_the_suppression_reason():
    """D6 through the REAL ``SkillBrokerEngine.process_step``: a step whose
    every attempt is suppressed ends ABORTED, and under
    ``audit.corrected_status_columns`` its sentinel row reaches the audit CSV
    carrying WHY. Without this the one row that records a parse failure says
    nothing about the digit that was refused, and the operator who turned the
    flag on cannot tell a hardening effect from a broken prompt.
    """
    from unittest.mock import MagicMock

    from broker.components.analytics.audit import trace_to_csv_row
    from broker.components.governance.registry import SkillRegistry
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.interfaces.skill_types import SkillDefinition
    from broker.tests.test_corrected_status_columns_pr3 import _Ctx, _Sim, _StubWriter

    registry = SkillRegistry()
    registry.register(SkillDefinition(
        skill_id="do_nothing", description="d", eligible_agent_types=["*"],
        preconditions=[], institutional_constraints={},
        allowed_state_changes=[], implementation_mapping="do_nothing",
    ))
    registry.set_default_skill("do_nothing")

    # A REAL UnifiedAdapter with the flag ON, parsing REAL digit-bearing prose
    # that no route may claim. Stubbing parse_output here would test the engine
    # against a mock of the very thing under test and would never exercise the
    # parser-stash -> retry-restash -> engine-read -> sentinel chain as one path.
    adapter = _make_adapter(strict_layers=True, strict_mode=True)
    adapter.last_parse_warnings = []

    config = MagicMock()
    config.get_log_fields.return_value = []
    config.get_governance_retries.return_value = 1
    config.get_governance_max_reports.return_value = 1
    config.get_multi_skill_config.return_value = {}
    config.get_parsing_config.return_value = {}
    config.get_governance_on_retry_exhausted.return_value = "default"
    config.get_audit_corrected_status_columns.return_value = True

    engine = SkillBrokerEngine(
        skill_registry=registry, model_adapter=adapter, validators=[],
        simulation_engine=_Sim(), context_builder=_Ctx(), config=config,
    )
    engine.audit_writer = _StubWriter()
    result = engine.process_step(
        agent_id="A1", step_id=1, run_id="r", seed=42,
        llm_invoke=lambda p: TEXT_PROSE_DIGIT, agent_type="household",
        env_context={"current_year": 1},
    )

    assert result.outcome is SkillOutcome.ABORTED
    assert len(engine.audit_writer.traces) == 1
    row = trace_to_csv_row(engine.audit_writer.traces[0][1])
    assert row["status"] == "ABORTED"
    assert "suppressed candidate digit 3" in row["parsing_warnings"], row["parsing_warnings"]
    assert "attempt 0:" in row["parsing_warnings"], row["parsing_warnings"]
    # The sentinel must not lose the columns PR-3 put on it.
    assert row["raw_output"] == TEXT_PROSE_DIGIT
    assert row["execution_path"] == "aborted"
    adapter.last_parse_warnings = []


# ---------------------------------------------------------------------------
# 5. get_parsing_strict_layers() + resolve_strict_layers_flag()
# ---------------------------------------------------------------------------

def _cfg(global_config=None) -> AgentTypeConfig:
    cfg = AgentTypeConfig.__new__(AgentTypeConfig)
    cfg._config = {"global_config": global_config or {}}
    return cfg


def test_getter_default_off():
    assert _cfg().get_parsing_strict_layers() is False
    assert _cfg({"parsing": {}}).get_parsing_strict_layers() is False


def test_getter_explicit_on():
    assert _cfg({"parsing": {"strict_layers": True}}).get_parsing_strict_layers() is True


def test_getter_non_dict_parsing_block_is_off():
    """A malformed scalar block reads as OFF and never raises."""
    assert _cfg({"parsing": "yes"}).get_parsing_strict_layers() is False


def test_getter_is_independent_of_audit_flags():
    cfg = _cfg({"parsing": {"strict_layers": True},
                "audit": {"corrected_status_columns": True}})
    assert cfg.get_parsing_strict_layers() is True
    assert cfg.get_audit_corrected_status_columns() is True
    assert _cfg({"parsing": {"strict_layers": True}}).get_audit_corrected_status_columns() is False


def test_resolver_missing_getter_is_off_silently():
    """A config predating the flag has no getter — OFF, and nothing to warn
    about."""
    assert resolve_strict_layers_flag(SimpleNamespace()) is False


def test_resolver_getter_raises_warns_and_reads_off(caplog):
    class _Raiser:
        def get_parsing_strict_layers(self):
            raise ValueError("malformed parsing block")

    _PARSING_FLAG_WARNED.clear()
    with caplog.at_level(logging.WARNING):
        assert resolve_strict_layers_flag(_Raiser()) is False
    assert any("strict_layers is being read OFF" in r.getMessage() for r in caplog.records)
    _PARSING_FLAG_WARNED.clear()


def test_resolver_non_bool_warns_and_reads_off(caplog):
    class _Stringy:
        def get_parsing_strict_layers(self):
            return "true"  # a YAML string, not a bool

    _PARSING_FLAG_WARNED.clear()
    with caplog.at_level(logging.WARNING):
        assert resolve_strict_layers_flag(_Stringy()) is False
    assert any("rather than a bool" in r.getMessage() for r in caplog.records)
    _PARSING_FLAG_WARNED.clear()


def test_resolver_dedup_key_is_the_reason_not_the_exception_text():
    """D7. Keying the warn-once set on the exception's MESSAGE lets a getter
    whose message carries anything variable mint a fresh key every call: the
    set grows without bound and the "once" never holds."""
    class _Variable:
        def __init__(self):
            self.n = 0

        def get_parsing_strict_layers(self):
            self.n += 1
            raise ValueError(f"failure number {self.n}")

    _PARSING_FLAG_WARNED.clear()
    cfg = _Variable()
    for _ in range(20):
        assert resolve_strict_layers_flag(cfg) is False
    assert len(_PARSING_FLAG_WARNED) == 1
    _PARSING_FLAG_WARNED.clear()


def test_pr3_sibling_resolver_has_the_same_dedup_fix():
    """The defect this PR's comment criticises was still live in PR-3's
    ``_corrected_status_flag`` warn-once set — same unbounded growth, same
    never-holding "once". A comment that describes a bug the neighbouring file
    still has is a comment that will be believed and be wrong."""
    from broker.core._audit_helpers import _FLAG_WARNED, _corrected_status_flag

    class _Variable:
        def __init__(self):
            self.n = 0

        def get_audit_corrected_status_columns(self):
            self.n += 1
            raise ValueError(f"failure number {self.n}")

    _FLAG_WARNED.clear()
    cfg = _Variable()
    for _ in range(20):
        assert _corrected_status_flag(cfg) is False
    assert len(_FLAG_WARNED) == 1
    _FLAG_WARNED.clear()


def test_resolver_explicit_bool_passthrough():
    assert resolve_strict_layers_flag(
        SimpleNamespace(get_parsing_strict_layers=lambda: True)) is True
    assert resolve_strict_layers_flag(
        SimpleNamespace(get_parsing_strict_layers=lambda: False)) is False


def test_engine_init_clears_the_warned_set():
    """D7: without the reset, a SECOND run in the same process is told
    nothing, and "the flag silently read OFF" is exactly what the warning
    exists to surface."""
    from broker.core.skill_broker_engine import SkillBrokerEngine
    from broker.utils.agent_config import load_agent_config

    AgentTypeConfig.clear_cache()
    _PARSING_FLAG_WARNED.add("getter_raised")
    SkillBrokerEngine(
        skill_registry=SimpleNamespace(get=lambda s: None),
        model_adapter=SimpleNamespace(),
        validators=[],
        simulation_engine=None,
        context_builder=None,
        config=load_agent_config(CONFIG_PATH),
        skill_retriever=SimpleNamespace(retrieve=lambda *a: []),
    )
    assert _PARSING_FLAG_WARNED == set()
    AgentTypeConfig.clear_cache()


# ---------------------------------------------------------------------------
# 6. validate_prompt config-time checks (D8)
# ---------------------------------------------------------------------------

def _issues(cfg):
    from broker.tools.validate_prompt import check_global_config_keys
    return check_global_config_keys(cfg)


def _messages(cfg):
    return [i.message for i in _issues(cfg)]


def test_validate_prompt_accepts_a_real_bool():
    assert _issues({"global_config": {"parsing": {"strict_layers": True}}}) == []
    assert _issues({"global_config": {"parsing": {"strict_layers": False}}}) == []


@pytest.mark.parametrize("value", ["false", "true", "yes", 1, None])
def test_validate_prompt_warns_on_a_non_bool(value):
    """The quoted string ``"false"`` is the expensive one: TRUTHY in Python,
    so a reader skims it as off while a naive consumer reads it as on, and the
    resolver's answer (off, one log line) matches neither reading reliably."""
    messages = _messages({"global_config": {"parsing": {"strict_layers": value}}})
    assert any("strict_layers must be a bool" in m for m in messages), messages


def test_validate_prompt_string_bool_gets_the_unquoted_hint():
    messages = _messages({"global_config": {"parsing": {"strict_layers": "false"}}})
    assert any("strict_layers: false` without quotes" in m for m in messages), messages


def test_validate_prompt_warns_on_a_per_agent_strict_layers():
    """Every OTHER key under ``parsing:`` is per-agent-type, so putting this
    one beside them is the obvious mistake — and it is silent."""
    messages = _messages({
        "household": {"agent_type": "household",
                      "parsing": {"strict_mode": True, "strict_layers": True}},
        "global_config": {},
    })
    assert any("read ONLY from global_config.parsing" in m for m in messages), messages


def test_validate_prompt_per_agent_check_survives_a_missing_global_config():
    """A YAML with no ``global_config`` block at all is exactly the config
    this warning exists for, so it must run before the early return."""
    messages = _messages({
        "household": {"agent_type": "household", "parsing": {"strict_layers": True}},
    })
    assert any("read ONLY from global_config.parsing" in m for m in messages), messages


def test_validate_prompt_warns_on_a_top_level_parsing_block():
    """The same mistake one level up, and just as silent — nothing reads a
    top-level ``parsing:`` block either."""
    messages = _messages({"parsing": {"strict_layers": True}, "global_config": {}})
    assert any("read ONLY from global_config.parsing" in m for m in messages), messages


def test_validate_prompt_leaves_per_agent_strict_mode_alone():
    """``strict_mode`` IS genuinely per-agent-type and must not be warned on."""
    messages = _messages({
        "household": {"agent_type": "household", "parsing": {"strict_mode": True}},
        "global_config": {"parsing": {"strict_layers": True}},
    })
    assert messages == []


def test_validate_prompt_warns_on_an_unknown_parsing_key():
    messages = _messages({"global_config": {"parsing": {"strict_layer": True}}})
    assert any("unrecognized key 'strict_layer'" in m for m in messages), messages
