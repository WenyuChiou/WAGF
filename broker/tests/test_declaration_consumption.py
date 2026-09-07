"""Declaration-consumption invariant (Wave 4, 2026-06-09 architecture review).

THE SYSTEMIC VACCINE for the d1cf7c3 bug class: a surface that is
REGISTERED/DECLARED but never CONSUMED in production, with green tests
exercising the dead code directly so nothing notices. The review found
independent instances in all eight architecture dimensions (registry PHYSICAL
dispatch dead in every production run; multi_agent_env_keys /
institutional_lifecycle_handlers / MemoryPack hooks / temporal+behavioural
slots / builtin_checks all declared-but-unconsumed). Each was found by
archaeology; this test makes the gap a CI failure instead.

Two invariants:

1. EVERY DomainPack protocol method has at least one production call site
   (attribute call or getattr-string) OR an explicit entry in DORMANT_HOOKS
   below with a justification + date. Two-sided: a new zero-consumer hook
   fails CI, and a dormant hook that GAINS a consumer must be removed from
   the allowlist (so the list never rots into cover).

2. EVERY ValidatorRegistry slot has at least one ``get_checks(..., "<slot>")``
   dispatch literal in production broker code — a slot in VALID_SLOTS is a
   promise the engine can dispatch it (temporal/behavioural were deleted in
   the Wave-4 slot-honesty pass precisely because no such site ever existed).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]

# ---------------------------------------------------------------------------
# The dormancy ledger. Every entry is a DELIBERATE, dated decision — not a
# shrug. Adding here requires a reason a reviewer can audit; removing happens
# the moment a production consumer ships (the test forces it).
# ---------------------------------------------------------------------------
DORMANT_HOOKS = {
    "builtin_checks": (
        "DEPRECATED 2026-06-10 (Wave 4): third wiring vocabulary for "
        "validator checks; zero consumers ever. Register via "
        "ValidatorRegistry instead. Kept only to avoid breaking out-of-tree "
        "packs; remove at the next major protocol revision."
    ),
    "action_taxonomy": (
        "Dormant 2026-06-10: taxonomies load from skill_registry.yaml via "
        "load_action_taxonomy_from_skill_registry; the pack hook awaits its "
        "first consumer (wire or remove when taxonomy goes pack-driven)."
    ),
    # param_specs: NO LONGER DORMANT as of 6W-B7 — examples/reservoir_control_multidim
    # (pack + __init__) calls pack.param_specs() and feeds it to
    # make_parameter_bounds_validator. Entry removed (a consumed hook must not sit in
    # the dormancy ledger).
    "credibility_tiers": (
        "No DIRECT production caller 2026-06-10: the only read is the "
        "transitive chain providers.py -> pack.credibility_weight(tier_id) "
        "-> self.credibility_tiers() INSIDE default.py, which this scan "
        "excludes as a declaration site. Promote out of this ledger when a "
        "consumer calls the hook directly (review fix-4 wording)."
    ),
    "initial_memory_templates": (
        "Dormant 2026-06-10: flood seeds memories via "
        "FloodMemoryTemplateProvider (Phase 6B-2 path), irrigation via its "
        "CSV memory column; the hook awaits the first template-driven domain."
    ),
    "multi_agent_env_keys": (
        "Declaration manifest BY DESIGN (Wave 3 / 3-9a, 2026-06-10): the "
        "consumer is the two-sided drift lock in "
        "test_ma_env_keys_declaration.py, deliberately a test (the bespoke "
        "MA lifecycle file owns write semantics; the hook is the "
        "machine-checked ownership inventory)."
    ),
    "reflection_persona": (
        "Dormant 2026-06-10: reflection personas currently flow through "
        "prompts/config (reflection.py reflection_persona() on the ENGINE "
        "side); the pack hook has no reader. Wire into the engine prompt "
        "path or remove. (The ReflectionOrchestrator this note used to "
        "name was itself removed 2026-09 as dead code — see org-3 notes "
        "below — so this hook still awaits its first real consumer.)"
    ),
}


def _protocol_methods() -> set:
    proto = (REPO / "broker" / "domains" / "protocol.py").read_text(encoding="utf-8")
    return set(re.findall(r"^\s+def ([a-z_][\w]*)\(self", proto, re.M))


def _production_corpus() -> str:
    """All broker/ + examples/ .py code EXCLUDING tests, the declaration sites
    (protocol.py / default.py), and the paper3 analysis tree."""
    chunks = []
    for base in ("broker", "examples"):
        for p in (REPO / base).rglob("*.py"):
            s = p.as_posix()
            if "/tests/" in s or "__pycache__" in s or "/paper3/" in s:
                continue
            if s.endswith("domains/protocol.py") or s.endswith("domains/default.py"):
                continue
            chunks.append(p.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def _has_consumer(method: str, corpus: str) -> bool:
    # attribute call:   anything.method(   |  getattr-string: getattr(x, "method"
    if re.search(r"\.\s*" + re.escape(method) + r"\s*\(", corpus):
        return True
    if re.search(r"getattr\([^,)]+,\s*[\"']" + re.escape(method) + r"[\"']", corpus):
        return True
    return False


def test_every_domain_pack_hook_is_consumed_or_explicitly_dormant():
    corpus = _production_corpus()
    methods = _protocol_methods()
    dead = {m for m in methods if not _has_consumer(m, corpus)}

    undeclared_dead = dead - set(DORMANT_HOOKS)
    assert not undeclared_dead, (
        "DomainPack hook(s) with ZERO production consumers and no dormancy "
        f"entry: {sorted(undeclared_dead)}. This is the d1cf7c3 bug class "
        "(declared surface nothing dispatches). Either wire a production "
        "consumer or add a dated, justified entry to DORMANT_HOOKS in this "
        "test — silence is not an option."
    )

    stale_dormant = set(DORMANT_HOOKS) - dead
    assert not stale_dormant, (
        f"DORMANT_HOOKS entries now HAVE production consumers: {sorted(stale_dormant)}. "
        "Remove them from the allowlist — a stale dormancy ledger is cover, "
        "not bookkeeping."
    )


def test_every_validator_slot_has_a_dispatch_site():
    from broker.components.governance.validator_registry import VALID_SLOTS

    dispatch_corpus = []
    for p in (REPO / "broker").rglob("*.py"):
        s = p.as_posix()
        if "/tests/" in s or "__pycache__" in s:
            continue
        dispatch_corpus.append(p.read_text(encoding="utf-8", errors="replace"))
    big = "\n".join(dispatch_corpus)

    undispatchable = [
        slot for slot in VALID_SLOTS
        if not re.search(r"get_checks\([^)]*[\"']" + re.escape(slot) + r"[\"']", big)
    ]
    assert not undispatchable, (
        f"VALID_SLOTS member(s) with NO get_checks dispatch site in broker/: "
        f"{undispatchable}. A slot is a promise the engine can dispatch it — "
        "add the dispatch site with the slot, or don't add the slot "
        "(temporal/behavioural were deleted 2026-06-10 for exactly this)."
    )


def test_deleted_slots_stay_deleted():
    """temporal/behavioural were never registered or dispatched by any
    production code in their lifetime. Re-adding one requires a dispatch
    site (previous test) — this lock just makes the deletion explicit."""
    from broker.components.governance.validator_registry import VALID_SLOTS

    assert "temporal" not in VALID_SLOTS
    assert "behavioural" not in VALID_SLOTS


def test_registering_deleted_slot_raises():
    from broker.components.governance.validator_registry import ValidatorRegistry

    with pytest.raises(ValueError, match="slot must be one of"):
        ValidatorRegistry.register("some_domain", "temporal", [lambda *a: []])
