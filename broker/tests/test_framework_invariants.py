"""Framework invariant tests — broker/INVARIANTS.md.

These tests encode the architectural contracts in broker/INVARIANTS.md as
executable checks. They run in CI and block merges that break invariants.

Test groups:
    T1: audit sentinel detection (Invariant 2)
    T2: parallel-API consistency (Invariant 3)
    T3: dormant-field policy — every audit column has a writer (Invariant 4)
    T4: domain-genericity — no domain-specific tokens in broker/ core (Invariant 5)
    T5: memory type contract (Invariant 1) — parked, see docstring

Motivating incident: 2026-04-19 NW flood cross-model experiments shipped with
silent memory pipeline leaks that would have been caught by any of these tests.

Some tests are intentionally opinionated — they use grep-style codebase
scans rather than pure unit tests because the invariants are about codebase
structure, not individual function behavior. False positives can be resolved
by editing allow-lists documented in each test.
"""
from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List, Set

import pytest

from broker.components.analytics.audit import (
    detect_audit_sentinels,
    detect_audit_sentinels_in_csv,
    _SUSPICIOUS_COLUMN_DEFAULTS,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
BROKER_ROOT = REPO_ROOT / "broker"


# =============================================================================
# T1: AuditWriter sentinel detection — Invariant 2 (audit integrity)
# =============================================================================

class TestAuditSentinelDetection:
    """Invariant 2: hardcoded placeholders masquerading as real data must be
    detected at experiment finalization."""

    def test_empty_rows_returns_no_warnings(self):
        """Trivial: empty input never flags."""
        assert detect_audit_sentinels([]) == []

    def test_tiny_run_skips_detection(self):
        """Fewer than _SENTINEL_MIN_ROWS observations → skip (avoid false
        positives on sanity tests)."""
        rows = [{"mem_top_emotion": "neutral"} for _ in range(10)]
        assert detect_audit_sentinels(rows, min_rows=50) == []

    def test_constant_neutral_emotion_flagged(self):
        """The exact 2026-04-19 NW flood leak pattern — 1000 rows, all
        mem_top_emotion="neutral" — MUST fire a warning."""
        rows = [{"mem_top_emotion": "neutral"} for _ in range(100)]
        warnings = detect_audit_sentinels(rows)
        assert any("mem_top_emotion" in w for w in warnings)
        assert any("neutral" in w for w in warnings)

    def test_variety_no_false_positive(self):
        """A healthy experiment with varied emotions MUST NOT be flagged."""
        emotions = ["neutral", "critical", "positive", "major", "routine"]
        rows = [
            {"mem_top_emotion": emotions[i % len(emotions)]}
            for i in range(100)
        ]
        warnings = detect_audit_sentinels(rows)
        mem_emotion_warnings = [w for w in warnings if "mem_top_emotion" in w]
        assert mem_emotion_warnings == []

    def test_all_cognitive_columns_detected(self):
        """All four cog_* columns default-constant → four warnings."""
        rows = [
            {
                "cog_is_novel_state": False,
                "cog_surprise_value": 0.0,
                "cog_margin_to_switch": 0.0,
                "cog_system_mode": "",
            }
            for _ in range(100)
        ]
        warnings = detect_audit_sentinels(rows)
        for col in ["cog_is_novel_state", "cog_surprise_value",
                    "cog_margin_to_switch", "cog_system_mode"]:
            assert any(col in w for w in warnings), f"missing warning for {col}"

    def test_varied_column_with_placeholder_subset_not_flagged(self):
        """If a column has mostly placeholder but some real values, it is NOT
        a silent-constant leak (it IS populated; variability is low but
        non-zero)."""
        rows = [{"mem_top_emotion": "neutral"} for _ in range(99)]
        rows.append({"mem_top_emotion": "critical"})
        warnings = detect_audit_sentinels(rows)
        mem_emotion_warnings = [w for w in warnings if "mem_top_emotion" in w]
        assert mem_emotion_warnings == []

    def test_real_nw_csv_detected_if_available(self):
        """Regression anchor: the real 2026-04-19 pre-fix NW audit CSV MUST
        fire multiple warnings when rechecked. If the file is absent (e.g.
        in a clean checkout), skip gracefully."""
        csv_path = (
            REPO_ROOT
            / "examples"
            / "single_agent"
            / "results"
            / "JOH_FINAL"
            / "gemma4_26b"
            / "Group_C"
            / "Run_1"
            / "household_governance_audit.csv"
        )
        if not csv_path.exists():
            pytest.skip(f"Reference CSV not available: {csv_path}")
        warnings = detect_audit_sentinels_in_csv(str(csv_path))
        # The pre-Codex-fix CSV should exhibit at least the 4 cog_* leaks
        # (cognitive module parked for V2) plus memory pipeline leaks.
        assert len(warnings) >= 4, (
            f"Expected ≥4 sentinel warnings on pre-fix NW audit CSV; got "
            f"{len(warnings)}: {warnings}"
        )


# =============================================================================
# T2: Parallel-API consistency — Invariant 3
# =============================================================================

class TestParallelAPIConsistency:
    """Invariant 3: if foo() and foo_for_y() exist on the same concept,
    metadata classification must be identical between both paths."""

    def _build_minimal_engine(self):
        from broker.components.memory.engines.humancentric import (
            HumanCentricMemoryEngine,
        )
        return HumanCentricMemoryEngine()

    def _build_agent(self, agent_id: str = "Agent_1"):
        return SimpleNamespace(
            id=agent_id,
            memory=[],
            memory_config={},
        )

    def test_add_memory_and_add_memory_for_agent_classify_identically(self):
        """Adding the same critical-emotion content via both methods must
        result in the same stored emotion classification (when explicit
        metadata is passed)."""
        engine_a = self._build_minimal_engine()
        engine_b = self._build_minimal_engine()
        content = "Flood event caused loss of property and emergency damage"
        metadata = {"emotion": "critical", "source": "personal", "importance": 0.9}

        engine_a.add_memory("Agent_1", content, metadata=metadata)
        engine_b.add_memory_for_agent(
            self._build_agent(), content, metadata=metadata
        )

        # Storage check: both engines must have exactly one memory
        mems_a = engine_a.working.get("Agent_1", [])
        mems_b = engine_b.working.get("Agent_1", [])
        assert len(mems_a) == 1 and len(mems_b) == 1

        # Critical invariant: emotion classification must match
        assert mems_a[0].get("emotion") == mems_b[0].get("emotion"), (
            f"add_memory got emotion={mems_a[0].get('emotion')!r} but "
            f"add_memory_for_agent got emotion={mems_b[0].get('emotion')!r} "
            f"— Invariant 3 violated."
        )


# =============================================================================
# T3: Dormant-field policy — every audit column has a writer (Invariant 4)
# =============================================================================

class TestDormantFieldPolicy:
    """Invariant 4: audit CSV columns that exist in the schema must be
    populated by at least one production code path, OR be explicitly
    documented as reserved.

    Implementation note: audit.py uses aggregation-based CSV composition
    where many columns derive from nested dicts (mem_audit, social_audit,
    cognitive_audit, rule_breakdown). Directly grepping the CSV column name
    yields only audit.py as a writer — too strict. Instead we verify the
    upstream DICT KEY has a writer in broker/ production code. If the dict
    is populated, its derived columns are considered populated.
    """

    # Map of audit dict keys to the CSV columns they populate (audit.py:307+).
    # Each dict key MUST have at least one writer in non-audit broker/ code.
    _AUDIT_AGGREGATE_KEYS: Dict[str, List[str]] = {
        "memory_audit": [
            "mem_retrieved_count", "mem_cognitive_system", "mem_surprise",
            "mem_retrieval_mode", "mem_top_emotion", "mem_top_source",
        ],
        "social_audit": [
            # Phase 6N-A (2026-05-23): the visible-actions columns are
            # now domain-dynamic (audit.py iterates the dict and writes
            # ``social_<key>`` for whatever the domain supplies). Only
            # the three columns produced unconditionally regardless of
            # domain are tracked here as static columns.
            "social_gossip_count", "social_neighbor_count",
            "social_network_density",
        ],
        "cognitive_audit": [
            "cog_system_mode", "cog_surprise_value",
            "cog_is_novel_state", "cog_margin_to_switch",
        ],
        "rule_breakdown": [
            "rules_personal_hit", "rules_social_hit", "rules_thinking_hit",
            "rules_physical_hit", "rules_semantic_hit",
        ],
    }

    # Dict keys that are documented as reserved-for-future-use. Their columns
    # will still appear in CSV (with None/placeholder) but the invariant
    # allows the upstream dict itself to be absent, flagging only via
    # sentinel detector (Invariant 2), not as hard test failure.
    _RESERVED_DICT_KEYS: Set[str] = {
        "cognitive_audit",   # V2 cognitive module — see INVARIANTS.md §4
        # TECH-DEBT (2026-04-19 audit): social_audit is referenced by
        # audit.py export logic but no broker/core/ file currently writes
        # it into trace objects. Should be populated by InteractionHub +
        # skill_broker_engine. Fix deferred to Phase D of the framework
        # hardening plan.
        "social_audit",
        # TECH-DEBT (2026-04-19 audit): rule_breakdown helper exists at
        # broker/validators/governance.py but its result is never merged
        # into the audit trace dict. Should be wired in skill_broker_engine
        # when composing traces. Deferred to Phase D.
        "rule_breakdown",
    }

    def _find_upstream_writer(self, dict_key: str) -> int:
        """Count production files under broker/ (excluding tests and
        audit.py itself) that write to the upstream dict key."""
        count = 0
        # Match patterns like: trace["memory_audit"] = ... or "memory_audit":
        patterns = [
            re.compile(r'["\']' + re.escape(dict_key) + r'["\']\s*:'),  # key in dict literal
            re.compile(r'\[\s*["\']' + re.escape(dict_key) + r'["\']\s*\]\s*='),  # subscript assign
        ]
        skip_names = {"audit.py", "__init__.py"}
        for path in BROKER_ROOT.rglob("*.py"):
            if "_audit_tmp_" in str(path) or "__pycache__" in str(path):
                continue
            if "tests" in path.parts:
                continue
            if path.name in skip_names and "analytics" in path.parts:
                continue  # skip audit.py (the reader) and its __init__
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            if any(p.search(text) for p in patterns):
                count += 1
        return count

    def test_audit_aggregate_keys_have_upstream_writers(self):
        """For every aggregate dict key (memory_audit, social_audit,
        cognitive_audit, rule_breakdown) the audit.py expects from traces,
        at least one non-audit file must write it — OR it must be in
        _RESERVED_DICT_KEYS."""
        orphans: List[str] = []
        for dict_key, columns in self._AUDIT_AGGREGATE_KEYS.items():
            if dict_key in self._RESERVED_DICT_KEYS:
                continue
            writers = self._find_upstream_writer(dict_key)
            if writers < 1:
                orphans.append(
                    f"'{dict_key}' (populates columns: {', '.join(columns)})"
                )
        assert not orphans, (
            f"Audit aggregate dict keys have no upstream writer: {orphans}. "
            f"Either populate them in production code or add the dict key "
            f"to _RESERVED_DICT_KEYS with documentation."
        )


# =============================================================================
# T4: Domain-genericity — Invariant 5
# =============================================================================

class TestDomainGenericity:
    """Invariant 5: every generic broker/ subtree must be domain-agnostic.
    The only non-generic trees are broker/domains/water/ (the domain home)
    and broker/tests/. Domain-specific tokens belong in examples/<domain>/,
    broker/domains/<domain>/, or behind adapter protocols.

    (Before 2026-05-20 this scanned only components/ + core/ and used
    lowercase ``WSA_label``/``ACA_label`` tokens that never matched the
    uppercase production identifiers — the harness-engineering audit
    surfaced both bugs.)"""

    # Known domain-specific tokens that MUST NOT appear in generic code.
    # Each entry pairs the token with a note about what domain it belongs to.
    _DOMAIN_TOKENS: Dict[str, str] = {
        "flood_count": "flood domain",
        "flood_zone": "flood domain",
        "flood_depth": "flood domain",
        "elevated": "flood domain",
        "WSA_LABEL": "irrigation domain",
        "ACA_LABEL": "irrigation domain",
        "drought_tier": "drought domain (future)",
        # Phase 6J-B (2026-05-22): ma_manager.py event dispatch de-flooded
        # — the get_agent_impact flood event-type chain moved to
        # FloodDomainPack.agent_impact_handlers(). These two tokens are
        # now clean across generic broker/ and guard that work.
        "flooded": "flood domain",
        "flood_damage": "flood domain",
        # Phase 6J-E (2026-05-22): finalises the token set. The three
        # tokens deferred from 6J-B are added with TECH-DEBT(6K)
        # allowlist entries for the leak sites — the memory subsystem +
        # the flood-specific events/generators/flood.py file relocate
        # in a future "memory plugin" phase. simulation_protocols.py was
        # de-flooded (docstring example → generic).
        "flood_occurred": "flood domain",
        "flood_event": "flood domain",
        "flood_depth_m": "flood domain",
        # Flood / water-domain infrastructure identifiers — after
        # Phase 6K-D the only remaining occurrence in generic broker
        # is broker/simulation/environment.py's docstring (already
        # FP-allowlisted below). The tokens stay here so any future
        # re-introduction into generic broker code is caught at gate
        # time.
        "NFIP": "flood domain (US National Flood Insurance Program)",
        "FEMA": "flood domain (US Federal Emergency Management Agency)",
        # Flood / drought / irrigation infrastructure + construct
        # identifiers that are currently CLEAN across generic broker/
        # (verified by Phase 6J-E grep). Adding them locks the
        # cleanliness so a future regression is caught at gate time.
        "PRB": "flood domain (Passaic River Basin)",
        "SFHA": "flood domain (Special Flood Hazard Area, FEMA)",
        "CRSS": "irrigation domain (Colorado River Simulation System)",
        "shortage_tier": "irrigation domain (USBR DCP shortage tiers)",
        "drought_index": "drought domain",
        "buyout": "flood domain skill",
        "buyout_program": "flood domain skill",
        # Phase 6M-A (2026-05-23): PMT-construct field names — the
        # last deferred-from-6J-E tokens. The Phase 6L deferral plan
        # imagined a Pydantic class-hierarchy refactor, but the Phase
        # 6M Explore found `ReasoningSchema` was dead code (0 imports,
        # 0 instantiations) and the remaining mentions were docstring
        # examples + a posthoc backwards-compat default. Tokens added
        # now; the residual live mentions are FP-allowlisted below
        # (each with a comment justifying why).
        "threat_appraisal": "flood domain (PMT construct field)",
        "coping_appraisal": "flood domain (PMT construct field)",
        # Phase 6N-A (2026-05-23): the audit writer's social-context
        # block (audit.py §6) used to hardcode ``elevated_neighbors`` /
        # ``relocated_neighbors`` keys when reading the visible-actions
        # dict — flood-domain skill names baked into a generic
        # writer. Migrated to a dynamic ``social_<key>`` pass-through
        # so domain-specific keys flow without hardcoding. Tokens
        # added now to lock the cleanliness.
        "elevated_neighbors": "flood domain (social context key)",
        "relocated_neighbors": "flood domain (social context key)",
        # NOTE: still deferred:
        #   elevate_house / buy_insurance / relocate / maintain_demand
        #     (skill names referenced in many generic memory/validator
        #     docstrings, comments, and protocol examples — Phase 6J-E
        #     Explore verified ZERO live code references; keeping the
        #     grounded examples aids readability).
        #   do_nothing — explicitly evaluated and rejected (too common
        #     a phrase to enforce as a domain token).
    }

    # Files/paths where domain tokens are allowed — e.g., examples/, domain
    # adapter sub-folders, documentation, test fixtures.
    # Entries prefixed with "TECH-DEBT:" are documented architectural debt
    # from the 2026-04-19 audit; they should be migrated to domain adapters
    # and removed from this allow-list in a future cleanup pass.
    _ALLOWLIST_PATTERNS: List[str] = [
        "tests/",
        "domain_adapters/",
        # Historical/audit/report docs that DESCRIBE past domain leakage
        "_AUDIT_",
        "INVARIANTS.md",
        # (Phase 6H Item 9 DONE 2026-05-21: reflection.py fully de-flooded
        #  -- status-text / importance / batch-traits fallbacks removed,
        #  AgentReflectionContext flood fields removed, extract_agent_context
        #  domain-neutral. reflection.py is now token-free; entry removed.)
        # (Phase 6H Item 7 DONE 2026-05-22: the flood-coupled
        #  FinancialCostProvider deleted from providers.py; the
        #  canonical copy lives at broker/domains/water/providers.py.
        #  providers.py is now token-free -- entry removed.)
        # (Phase 6I DONE 2026-05-22: the last 4 real-code TECH-DEBT
        #  entries from the 2026-04-19 audit + agent_initializer.py are
        #  de-flooded -- agent_initializer position field-write uses a
        #  generic enricher.profile_field_map (6I-B); InteractionHub
        #  visible-action / action-label vocabulary is caller-supplied
        #  via broker.domains.water.interaction_specs (6I-C);
        #  create_flood_observables relocated to
        #  broker/domains/water/observables.py (6I-D); ImpactEventGenerator
        #  generalised -- mitigation field / event labels are config (6I-E);
        #  unified_context_builder core_state keys are domain-neutral
        #  (6I-F). All five entries removed; the I5 allowlist now holds
        #  only docstring/comment false positives.)
        # =====================================================================
        # HARNESS-ENGINEERING AUDIT (2026-05-20): the I5 scan was extended
        # from components/+core/ to ALL generic broker/ subtrees, and the
        # WSA_label/ACA_label tokens were case-fixed to WSA_LABEL/ACA_LABEL.
        # Both bugs had kept the entries below silently invisible. Triaged
        # into two classes; full catalogue in
        # .ai/2026/05/20/harness_audit_{A,B,C}_*.md.
        # ---------------------------------------------------------------------
        # FP — domain token appears ONLY in docstrings / comments / protocol
        # path examples; the code itself is domain-agnostic. Permanent.
        "interfaces/environment_protocols.py",       # FP: protocol path examples
        "interfaces/event_generator.py",             # FP: docstring example
        "memory/unified_engine.py",                  # FP: docstring example
        "memory/strategies/base.py",                 # FP: generic strategy docstring
        "memory/strategies/ema.py",                  # FP: generic strategy docstring + soft default
        "memory/strategies/multidimensional.py",     # FP: generic strategy docstring
        "memory/strategies/symbolic.py",             # FP: generic strategy docstring + soft default
        "memory/strategies/hybrid.py",               # FP: generic strategy docstring + soft default
        "governance/rule_types.py",                  # FP: docstring Example:: blocks
        "simulation/state_manager.py",               # FP: docstring example
        "simulation/environment.py",                 # FP: docstring examples
        "validators/governance/base_validator.py",   # FP: comment construct examples
        "config/schema.py",                          # FP: Field() description examples
        "config/agent_types/base.py",                # FP: docstring example
        "utils/retry_formatter.py",                  # FP: comment example
        # (Phase 6K-D (2026-05-22) closed both 6J-E FP entries —
        #  ``agents/base.py`` constraint-class docstring no longer
        #  references NFIP / FEMA by name, and ``components/context/providers.py``
        #  DYNAMO Literature reference no longer names NFIP. Both files
        #  are now NFIP/FEMA-token-free; entries removed.)
        # Phase 6M-A (2026-05-23) FP additions — the PMT-construct
        # tokens (``threat_appraisal`` / ``coping_appraisal``) added to
        # the guard above carry tail mentions in three generic files;
        # each is either a docstring example, a deletion-marker
        # comment, or a documented backwards-compat default. None
        # is live PMT-coupled production code post-6M-A:
        "components/response_format.py",             # FP: docstring `Usage:` + construct-mapping examples (the builder body is YAML-driven; see Phase 6M Explore notes)
        "interfaces/schemas.py",                     # FP: deletion-marker comment recording where ``ReasoningSchema`` previously lived (Phase 6M-A removed the dead class)
        "validators/posthoc/unified_rh.py",          # FP: PMT-flavoured ``ta_col``/``ca_col`` defaults retained for backwards compat with a docstring caveat — graceful-degradation guard at ~line 177 catches misuse on non-PMT DataFrames
        # Phase 6K-A (2026-05-22) closed the three memory-subsystem
        # TECH-DEBT(6K) entries via DomainPack.memory_policy().
        # Phase 6K-B (2026-05-22) closed the fourth: the whole-file
        # flood-specific hazard generator relocated from
        # ``broker/components/events/generators/flood.py`` to
        # ``broker/domains/water/event_generators/flood.py``. All four
        # 6K allowlist entries are now removed.
        # ---------------------------------------------------------------------
        # KNOWN-DEBT(6H) — genuine domain leak in generic broker/ code.
        # Each migrates in the Phase 6H DomainPack v2 refactor; removing an
        # entry MUST be paired with the migration, or the test regresses.
        # (Phase 6H Item 5d DONE 2026-05-21: appraisal_grounding_audit.py
        #  relocated to broker/domains/water/tools/ -- skip-listed,
        #  entry removed.)
        # (Phase 6H Item 5 DONE 2026-05-21: FLOOD_DEPTH_DESCRIPTORS relocated
        #  to examples/governed_flood/adapters/flood_perception.py; the
        #  HouseholdPerceptionFilter is DomainPack-wired -- interfaces/
        #  perception.py is flood-free, entry removed.)
        # (Phase 6H Item 1 DONE 2026-05-21: validators/calibration/ relocated
        #  to broker/domains/water/calibration/ — entry removed, no longer in
        #  the generic-broker scan scope.)
        # (Phase 6H Item 8 DONE 2026-05-21: thinking_rule_posthoc.py +
        #  unified_rh.py de-flooded -- transition columns / irreversible
        #  states are parameters; the water-domain CVRunner supplies the
        #  flood values. Both entries removed.)
        # (Phase 6H Item 6 DONE 2026-05-21: validate_affordability()
        #  de-flooded via DomainPack.affordability_constraints();
        #  dead :282-286 debug comment removed -- entry removed.)
    ]

    def _is_allowlisted(self, path: Path) -> bool:
        path_str = str(path).replace("\\", "/")
        return any(pat in path_str for pat in self._ALLOWLIST_PATTERNS)

    def _scan_generic_paths(self) -> List[Path]:
        """Scan every generic broker/ subtree.

        Per INVARIANTS.md §I5 the only non-generic trees are the domain
        home (broker/domains/water/) and the test tree (broker/tests/);
        everything else under broker/ must be domain-agnostic.
        """
        results: List[Path] = []
        skip_prefixes = (
            str(BROKER_ROOT / "tests"),
            str(BROKER_ROOT / "domains" / "water"),
        )
        for path in BROKER_ROOT.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            if str(path).startswith(skip_prefixes):
                continue
            if self._is_allowlisted(path):
                continue
            results.append(path)
        return results

    @pytest.mark.parametrize("token,domain", list(_DOMAIN_TOKENS.items()))
    def test_no_unmarked_domain_token_in_generic_code(self, token, domain):
        """For each known domain token, assert it does NOT appear in
        non-allowlisted broker/components/ or broker/core/ files."""
        pattern = re.compile(r'\b' + re.escape(token) + r'\b')
        violations: List[str] = []
        for path in self._scan_generic_paths():
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for i, line in enumerate(text.splitlines(), start=1):
                if pattern.search(line):
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}:{i}"
                    )
        assert not violations, (
            f"Domain token '{token}' ({domain}) leaked into generic broker "
            f"code at:\n  " + "\n  ".join(violations) +
            f"\nEither move to examples/<domain>/ or add path to "
            f"_ALLOWLIST_PATTERNS with a justification comment."
        )


# =============================================================================
# T5: Memory type contract — Invariant 1 (PARKED until Codex Fix B lands)
# =============================================================================

class TestMemoryTypeContract:
    """Invariant 1: retrieve() must preserve metadata.

    Activated after Codex Fix B landed on feat/memory-pipeline-v2 (commit
    129e33a). HumanCentricMemoryEngine.retrieve() now returns List[Dict].
    """

    def test_humancentric_retrieve_returns_list_of_dicts_with_metadata(self):
        from broker.components.memory.engines.humancentric import (
            HumanCentricMemoryEngine,
        )
        engine = HumanCentricMemoryEngine()
        agent = SimpleNamespace(id="Agent_1", memory=[], memory_config={})
        engine.add_memory_for_agent(
            agent, "critical flood damage event",
            metadata={"emotion": "critical", "importance": 0.9, "source": "personal"},
        )
        retrieved = engine.retrieve(agent, top_k=5)
        assert len(retrieved) >= 1
        first = retrieved[0]
        assert isinstance(first, dict), (
            f"retrieve() must return List[Dict], got {type(first).__name__}"
        )
        assert "content" in first, (
            f"retrieved memory missing 'content' key: {first}"
        )
        assert "emotion" in first, (
            f"retrieved memory missing 'emotion' key: {first}"
        )
        assert first["emotion"] == "critical", (
            f"critical emotion not preserved through retrieve; got {first['emotion']!r}"
        )

    def test_retrieve_content_only_returns_list_of_strings(self):
        """Backwards-compat shim: retrieve_content_only() must return
        plain List[str] for callers that explicitly want strings."""
        from broker.components.memory.engines.humancentric import (
            HumanCentricMemoryEngine,
        )
        engine = HumanCentricMemoryEngine()
        agent = SimpleNamespace(id="Agent_1", memory=[], memory_config={})
        engine.add_memory_for_agent(
            agent, "routine event — uneventful day",
            metadata={"emotion": "routine", "importance": 0.1, "source": "personal"},
        )
        content = engine.retrieve_content_only(agent, top_k=5)
        assert len(content) >= 1
        assert all(isinstance(c, str) for c in content), (
            f"retrieve_content_only must return List[str]"
        )


# =============================================================================
# T6: No silent domain default — Invariant 5 (Phase 6J-A)
# =============================================================================

class TestNoSilentDomainDefault:
    """Invariant 5 corollary: when a domain / framework is not declared,
    generic broker code must resolve to the domain-neutral GENERIC
    framework — never silently to the flood PMT framework.

    The I5 token scan (TestDomainGenericity) catches a *named* leak; this
    catches a *behavioural* one (a silent fallback can't be grepped)."""

    def test_generic_rating_scale_is_not_the_pmt_object(self):
        """RatingScaleRegistry.GENERIC must be a standalone scale, not an
        alias of the flood PMT scale object."""
        from broker.interfaces.rating_scales import (
            RatingScaleRegistry, FrameworkType,
        )
        generic = RatingScaleRegistry.get(FrameworkType.GENERIC)
        pmt = RatingScaleRegistry.get(FrameworkType.PMT)
        assert generic is not pmt
        assert generic.framework == FrameworkType.GENERIC

    def test_unknown_framework_falls_back_to_generic_not_pmt(self):
        """An unregistered framework name must resolve to GENERIC."""
        from broker.interfaces.rating_scales import (
            RatingScaleRegistry, FrameworkType,
        )
        scale = RatingScaleRegistry.get_by_name("some_unregistered_domain")
        assert scale.framework == FrameworkType.GENERIC

    def test_universal_context_defaults_to_generic_framework(self):
        """A UniversalContext with no declared framework — constructed or
        deserialised — must default to GENERIC, not PMT."""
        from broker.interfaces.context_types import (
            UniversalContext, PsychologicalFrameworkType,
        )
        ctx = UniversalContext(agent_id="probe")
        assert ctx.framework == PsychologicalFrameworkType.GENERIC
        ctx2 = UniversalContext.from_dict({"agent_id": "probe"})
        assert ctx2.framework == PsychologicalFrameworkType.GENERIC


class TestNoReverseDomainImport:
    """I5 architectural guard — added 2026-05-24 (Phase 6N-F-7).

    Catches the failure mode the token-based ``TestDomainGenericity`` grep
    cannot see: a module-level ``from broker.domains.water...`` import in a
    generic broker/ subtree. Such an import binds the framework to a
    specific domain at package-load time, regardless of whether any
    *_LABEL token leaks into the source. The original incident motivating
    this guard: ``broker/validators/governance/__init__.py`` carrying a
    top-level ``from broker.domains.water.validator_bundles import
    build_domain_validators`` (fixed in the same commit that added this
    test).

    Permitted patterns (intentional Phase 6H transition convention):
      - Function-local imports (inside def / async def).
      - PEP 562 ``__getattr__`` lazy hooks.
      - Imports under ``if TYPE_CHECKING:`` (zero runtime cost).
    """

    def _is_type_checking_guard(self, test_node) -> bool:
        """Recognise `if TYPE_CHECKING:` (bare name or attribute form)."""
        import ast
        if isinstance(test_node, ast.Name) and test_node.id == "TYPE_CHECKING":
            return True
        if isinstance(test_node, ast.Attribute) and test_node.attr == "TYPE_CHECKING":
            return True
        return False

    def _module_level_imports(self, tree):
        """Yield ImportFrom nodes that execute at module-load time.

        Walks ``tree.body`` directly. Imports nested inside FunctionDef /
        AsyncFunctionDef / ClassDef are excluded (function-local /
        __getattr__ patterns, by design).

        C2/C3 (code-reviewer round 2): descends into every module-level
        control-flow branch that executes at load time:
          - ``if`` body AND ``orelse`` (closes the TYPE_CHECKING-then-else
            bypass where the real import sits in the else branch).
          - ``try`` body, ``except`` handlers, ``orelse``, AND
            ``finalbody`` (the try/except ImportError fallback pattern).
        ``if TYPE_CHECKING:`` BODY is the one explicit exclusion (zero
        runtime cost); the same if's else still runs when TYPE_CHECKING
        is False and must be scanned.
        """
        import ast
        for node in tree.body:
            if isinstance(node, ast.ImportFrom):
                yield node
            elif isinstance(node, ast.If):
                body_iter = (
                    []
                    if self._is_type_checking_guard(node.test)
                    else node.body
                )
                for sub in list(body_iter) + list(node.orelse):
                    if isinstance(sub, ast.ImportFrom):
                        yield sub
            elif isinstance(node, ast.Try):
                clauses = [node.body, node.orelse, node.finalbody]
                clauses.extend(handler.body for handler in node.handlers)
                for clause in clauses:
                    for sub in clause:
                        if isinstance(sub, ast.ImportFrom):
                            yield sub

    def test_no_module_level_water_domain_import_in_generic_broker(self):
        import ast
        from pathlib import Path

        broker_root = Path(__file__).resolve().parents[1]

        # Subtrees we EXCLUDE from the scan:
        # - broker/domains/: the domain extension point itself (water
        #   subpackage is by-design water-specific; default.py + protocol.py
        #   are generic but inside the same tree, so easier to skip
        #   wholesale and let TestDomainGenericity's token scan cover them).
        # - broker/tests/: tests are allowed to import water adapters when
        #   asserting domain-pack contracts.
        excluded_prefixes = (
            broker_root / "domains",
            broker_root / "tests",
        )

        violations = []
        for path in broker_root.rglob("*.py"):
            # W2 (code-reviewer round 2): Path.is_relative_to() normalises
            # Windows backslash/forward-slash separators cleanly. Python 3.9+
            # — this repo requires 3.10+ per pyproject.toml.
            if any(path.is_relative_to(p) for p in excluded_prefixes):
                continue
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (UnicodeDecodeError, SyntaxError):
                continue

            for node in self._module_level_imports(tree):
                mod = node.module or ""
                if mod.startswith("broker.domains.water"):
                    rel = path.relative_to(broker_root.parent)
                    violations.append(f"{rel}:{node.lineno}  from {mod}")

        assert not violations, (
            "Module-level reverse imports from broker.domains.water found "
            "in generic broker/ — these bind the framework to a single "
            "domain at package-load time. Convert to function-local OR "
            "PEP 562 __getattr__ lazy hook, OR move under "
            "`if TYPE_CHECKING:`.\n"
            "Violations:\n  " + "\n  ".join(violations)
        )
