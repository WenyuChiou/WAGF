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
            "social_gossip_count", "social_elevated_neighbors",
            "social_relocated_neighbors", "social_neighbor_count",
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
    """Invariant 5: broker/components/ and broker/core/ must be
    domain-agnostic. Domain-specific tokens belong in examples/<domain>/ or
    behind adapter protocols."""

    # Known domain-specific tokens that MUST NOT appear in generic code.
    # Each entry pairs the token with a note about what domain it belongs to.
    _DOMAIN_TOKENS: Dict[str, str] = {
        "flood_count": "flood domain",
        "flood_zone": "flood domain",
        "flood_depth": "flood domain",
        "elevated": "flood domain",
        "WSA_label": "irrigation domain",
        "ACA_label": "irrigation domain",
        "drought_tier": "drought domain (future)",
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
        # Memory template for flood is intentionally domain-bound; it should
        # be migrated to a domain subfolder (tech debt). For now allow it.
        "prompt_templates/memory_templates.py",
        # agent_initializer.py has historical flood fields in AgentProfile
        # dataclass; documented as tech debt in INVARIANTS.md.
        "core/agent_initializer.py",
        # Reflection.py has flood logic; migration to DomainReflectionAdapter
        # is scheduled for Phase D. For now allow but document.
        "components/cognitive/reflection.py",
        # adapters.py IS the DomainReflectionAdapter protocol — docstrings
        # intentionally reference domain-specific examples (flood_count,
        # drought_severity) to illustrate the abstraction boundary. This
        # is the correct architectural pattern, not leakage.
        "components/cognitive/adapters.py",
        # TECH-DEBT (2026-04-19 audit): files below contain flood-specific
        # token references discovered during framework audit. Each is
        # catalogued for future domain-adapter migration. Removing from
        # this allow-list MUST be paired with the corresponding domain
        # adapter implementation, or the test will regress.
        "components/analytics/interaction.py",       # elevated/flood observations
        "components/analytics/observable.py",        # elevated neighbors
        "components/context/providers.py",           # flood_zone custom_attr
        "components/context/tiered.py",              # elevated state field
        "components/memory/content_types.py",        # elevated in generic memory tag
        "components/memory/engines/humancentric.py", # flood_depth test fixture
        "components/events/generators/impact.py",    # elevated neighbors event
        "core/unified_context_builder.py",           # elevated status render
        "core/_skill_filtering.py",                  # elevated precondition
    ]

    def _is_allowlisted(self, path: Path) -> bool:
        path_str = str(path).replace("\\", "/")
        return any(pat in path_str for pat in self._ALLOWLIST_PATTERNS)

    def _scan_generic_paths(self) -> List[Path]:
        results: List[Path] = []
        for root in [BROKER_ROOT / "components", BROKER_ROOT / "core"]:
            for path in root.rglob("*.py"):
                if "__pycache__" in path.parts:
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
