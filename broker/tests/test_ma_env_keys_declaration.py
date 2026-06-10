"""Drift-lock for FloodPack.multi_agent_env_keys (Wave 3 item 3-9a).

The 2026-06-09 architecture review's dim-8 dead-path hunt found
``multi_agent_env_keys()`` declared on SetupPack with ZERO production
consumers since Phase 6T-C. The fix makes it a MACHINE-CHECKED ownership
manifest: the flood pack declares the complete inventory of env-dict keys the
bespoke MA lifecycle file writes, and THIS test is the consumer — it re-scans
``lifecycle_hooks.py`` with the same extraction the declaration was built
from and asserts EQUALITY, so:

* adding an env write to the lifecycle file without declaring it -> FAIL
  (undeclared ownership — the trampling hazard the hook exists to prevent);
* removing a write while the declaration still lists it -> FAIL
  (stale manifest — the false-confidence failure mode).

Also locks the 3-9b consumption: the influencer runner resolves its handler
through the pack's institutional_lifecycle_handlers() map, not a direct
class import.
"""
from __future__ import annotations

import re
from pathlib import Path

import examples.governed_flood  # noqa: F401 — registers the flood pack

from broker.domains.registry import DomainPackRegistry

REPO = Path(__file__).resolve().parents[2]
LIFECYCLE = REPO / "examples" / "multi_agent" / "flood" / "orchestration" / "lifecycle_hooks.py"

# The same extraction the declaration was built from (2026-06-10):
# self.env["key"] = ... and self.env.setdefault("key", ...)
# NOTE: self.env.update({...}) bulk-writes are NOT caught by this regex
# (verified absent from lifecycle_hooks.py today). If the lifecycle file is
# ever refactored to use env.update(), extend the scan to also extract
# literal string keys from update({...}) calls — otherwise this lock goes
# silently incomplete.
_ENV_WRITE_RE = re.compile(r'self\.env(?:\.setdefault\(|\[)\s*["\']([A-Za-z_][\w]*)["\']')


def _scan_lifecycle_env_writes() -> set:
    src = LIFECYCLE.read_text(encoding="utf-8")
    return set(_ENV_WRITE_RE.findall(src))


def test_flood_pack_declares_exactly_the_lifecycle_env_writes():
    pack = DomainPackRegistry.get("flood")
    declared = pack.multi_agent_env_keys()
    scanned = _scan_lifecycle_env_writes()
    undeclared = scanned - declared
    stale = declared - scanned
    assert not undeclared, (
        "lifecycle_hooks.py writes env keys the flood pack does not declare "
        f"in multi_agent_env_keys(): {sorted(undeclared)}. Add them to "
        "FloodSetupMixin.multi_agent_env_keys (the ownership manifest)."
    )
    assert not stale, (
        "FloodSetupMixin.multi_agent_env_keys declares keys lifecycle_hooks.py "
        f"no longer writes: {sorted(stale)}. Remove them — a stale manifest is "
        "the false-confidence failure mode this lock exists to prevent."
    )


def test_default_pack_returns_empty_set():
    """Domains without multi-agent runs keep the pre-6T-C silent contract."""
    from broker.domains.default import DefaultDomainPack

    assert DefaultDomainPack().multi_agent_env_keys() == set()


def test_influencer_runner_resolves_handler_via_pack_map():
    """3-9b consumption lock: the --with-influencer block must consult
    institutional_lifecycle_handlers() (the production dispatch map), never
    direct-import the handler class again. Source-level lock on the exact
    regression (the map was registered 6T-F.2 but bypassed until 2026-06-10);
    the map's CONTENT is functionally locked below."""
    src = (REPO / "examples" / "multi_agent" / "flood" / "run_unified_experiment.py").read_text(encoding="utf-8")
    assert "institutional_lifecycle_handlers()" in src
    assert "from examples.governed_flood.adapters.influencer_lifecycle import" not in src, (
        "run_unified_experiment.py direct-imports InfluencerLifecycleHandler again — "
        "resolve it via the pack's institutional_lifecycle_handlers() map instead."
    )


def test_pack_map_yields_working_influencer_handler():
    """Functional half of the 3-9b lock: the pack map resolves to a handler
    exposing the lifecycle verbs the runner calls."""
    pack = DomainPackRegistry.get("flood")
    handlers = pack.institutional_lifecycle_handlers()
    handler = handlers["social_media_influencer"]
    assert callable(getattr(handler, "post_decision", None)), (
        "pack-resolved influencer handler lacks post_decision — the verb the "
        "6T-F.5 runner dispatches"
    )
