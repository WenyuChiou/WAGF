"""Phase 6Q-F-2 (2026-05-26) — End-to-end genericity gate for a
non-water domain.

Phase 6Q-F-1 (commit fdd0dcf) landed the structural + sys-modules
gates using an inline ``FakeTrafficDomainPack`` defined in the test
file itself. That gate proves the **dispatcher** path stays
water-module-free for a non-water domain.

This file (Phase 6Q-F-2) promotes the fixture to a proper package at
``examples/_test_fixtures/fake_traffic/`` with YAML configs +
MockTrafficLLM responses, then exercises **deeper layers** of the
broker pipeline that the 6Q-F-1 gate didn't touch:

  - Skill registry YAML parsing for a non-water domain
  - Agent-type YAML parsing with `psychological_framework: ""`
    (FRAMEWORK_ESCAPE_HATCH path)
  - DomainPack registration via the explicit-import contract
    (Phase 6Q-G)
  - Mock LLM responses produce parseable broker payloads
  - sys.modules cleanliness under the new package import

**Scope: 6Q-F-2-a (foundation, this commit)** — fixture package +
construct-time assertions. The 1-year synthetic ``ExperimentRunner.run``
+ audit-CSV assertions land in **6Q-F-2-b** (next session).

Why split:
  - 6Q-F-2-a is read-only verification of the fixture package
    structure + import graph; ~150 LOC test, ~250 LOC fixtures.
  - 6Q-F-2-b is full runtime trace exercise that needs broker
    `ExperimentBuilder` config knobs + lifecycle hook wiring,
    closer to ~400 LOC + ~2 hr.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────
# Module-scoped registry teardown (Phase 6Q-F-2-b)
# ─────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True, scope="module")
def _cleanup_traffic_registration():
    """Phase 6Q-F-2-b (2026-05-26): import-side-effect protection.

    Importing ``examples._test_fixtures.fake_traffic`` runs
    ``DomainPackRegistry.register("traffic", ...)`` at module-load
    time. ``DomainPackRegistry._packs`` is class-level state, so
    the "traffic" pack persists for the entire pytest session,
    visible to any later test that calls
    ``DomainPackRegistry.list_domains()`` or relies on a clean
    registry. Snapshot + restore around this module's tests so
    other files aren't polluted.
    """
    from broker.domains.registry import DomainPackRegistry
    saved = dict(DomainPackRegistry._packs)
    yield
    DomainPackRegistry.clear()
    for name, pack in saved.items():
        # Re-register via the bypass path to avoid the Phase 6Q-D-5
        # smoke-test side effect on already-validated packs.
        DomainPackRegistry._packs[name] = pack


# ─────────────────────────────────────────────────────────────────────
# Fixture package import gate
# ─────────────────────────────────────────────────────────────────────

class TestFakeTrafficPackageImport:
    """The fixture package must import + register cleanly."""

    def test_package_importable(self):
        # If the package __init__ has an unhandled exception this would
        # raise — assertion via successful import.
        import examples._test_fixtures.fake_traffic  # noqa: F401

    def test_domain_pack_registered(self):
        import examples._test_fixtures.fake_traffic  # noqa: F401
        from broker.domains.registry import DomainPackRegistry
        from examples._test_fixtures.fake_traffic.pack import (
            FakeTrafficDomainPack,
        )

        pack = DomainPackRegistry.get("traffic")
        assert pack is not None, (
            "FakeTrafficDomainPack not registered after package import"
        )
        assert isinstance(pack, FakeTrafficDomainPack)

    def test_pack_uses_escape_hatch_framework(self):
        """The fixture's psychological_framework() must return the
        FRAMEWORK_ESCAPE_HATCH sentinel — this domain has no
        registered psychometric framework, by design."""
        import examples._test_fixtures.fake_traffic  # noqa: F401
        from broker.domains.registry import DomainPackRegistry
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_ESCAPE_HATCH,
        )

        pack = DomainPackRegistry.get_or_default("traffic")
        assert pack.psychological_framework() == FRAMEWORK_ESCAPE_HATCH


# ─────────────────────────────────────────────────────────────────────
# YAML config parse gate
# ─────────────────────────────────────────────────────────────────────

class TestTrafficYAMLConfigs:
    """YAML files parse + contain the expected non-water structure."""

    FIXTURE_DIR = (
        Path(__file__).resolve().parents[2]
        / "examples" / "_test_fixtures" / "fake_traffic"
    )

    def test_skill_registry_parses(self):
        import yaml
        path = self.FIXTURE_DIR / "traffic_skill_registry.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["domain"] == "traffic"
        skill_ids = [s["skill_id"] for s in data["skills"]]
        # 5 commuter skills + 1 dispatcher skill = 6 total.
        assert len(skill_ids) == 6
        assert "take_alternate_route" in skill_ids
        assert "switch_to_transit" in skill_ids
        assert "announce_advisory" in skill_ids
        # Sanity: no flood-domain skill names leaked.
        assert "elevate_house" not in skill_ids
        assert "buy_insurance" not in skill_ids
        assert "relocate" not in skill_ids

    def test_agent_types_parses_with_escape_hatch_framework(self):
        import yaml
        path = self.FIXTURE_DIR / "traffic_agent_types.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        assert data["global_config"]["governance"]["domain"] == "traffic"
        # Phase 6Q-D contract: framework="" is the escape hatch sentinel.
        assert data["commuter"]["psychological_framework"] == ""
        assert data["dispatcher"]["psychological_framework"] == ""
        # Phase 6Q-C contract: stimulus_key is required for memory engine.
        assert data["global_config"]["memory"]["stimulus_key"] == "congestion_level"


# ─────────────────────────────────────────────────────────────────────
# Mock LLM response gate
# ─────────────────────────────────────────────────────────────────────

class TestMockTrafficLLM:
    """Mock responses parse as valid broker JSON payloads."""

    def test_responses_parse_as_json(self):
        from examples._test_fixtures.fake_traffic.mock_responses import (
            MOCK_TRAFFIC_RESPONSES,
        )
        for key, response in MOCK_TRAFFIC_RESPONSES.items():
            # Extract JSON between the broker's standard delimiters.
            start = response.index("<<<DECISION_START>>>") + len(
                "<<<DECISION_START>>>"
            )
            end = response.index("<<<DECISION_END>>>")
            payload = json.loads(response[start:end].strip())
            assert "reasoning" in payload, f"{key}: missing reasoning"
            assert "decision" in payload, f"{key}: missing decision"
            assert isinstance(payload["decision"], int)
            assert 1 <= payload["decision"] <= 5

    def test_mock_llm_class_year_dispatch(self):
        """Phase 6Q-F-2-b: invoke() now matches the broker's
        Callable[[str], str] contract. Year + agent_type dispatch is
        driven by external state on the mock (current_year /
        current_agent_type)."""
        from examples._test_fixtures.fake_traffic.mock_responses import MockTrafficLLM
        mock = MockTrafficLLM()
        # Commuter responses are year-keyed via current_year.
        for year in [1, 2, 3]:
            mock.current_year = year
            response = mock.invoke("ignored prompt")
            assert "<<<DECISION_START>>>" in response
            assert "<<<DECISION_END>>>" in response
        # Dispatcher gets its own response via current_agent_type.
        mock.current_year = 1
        mock.current_agent_type = "dispatcher"
        dispatcher_response = mock.invoke("ignored prompt")
        assert "<<<DECISION_START>>>" in dispatcher_response
        # call_count tracks ALL invocations.
        assert mock.call_count == 4

    def test_responses_contain_no_flood_vocabulary(self):
        from examples._test_fixtures.fake_traffic.mock_responses import (
            MOCK_TRAFFIC_RESPONSES,
        )
        # Regression guard — fake_traffic mocks must use traffic
        # vocabulary only. If a future copy-paste leaks flood words
        # into these canned responses, this fires.
        for key, response in MOCK_TRAFFIC_RESPONSES.items():
            low = response.lower()
            assert "flood" not in low, (
                f"{key}: flood vocabulary leaked into traffic mock"
            )
            assert "elevate_house" not in low
            assert "buy_insurance" not in low


# ─────────────────────────────────────────────────────────────────────
# sys.modules cleanliness (subprocess gate)
# ─────────────────────────────────────────────────────────────────────

# The structural runtime gate added in Phase 6Q-F-1 already proves
# `broker.components.governance.domain_validator_dispatch.build_domain_validators("traffic")`
# doesn't load `broker.domains.water.*`. Phase 6Q-F-2-a EXTENDS that
# to the new fixture-package import path: importing
# `examples._test_fixtures.fake_traffic` should NOT pull water in.
# (The fixture package explicitly does NOT import broker.domains.water
# — only governed_flood / irrigation_abm do, per Phase 6Q-G.)


# ─────────────────────────────────────────────────────────────────────
# Broker registry loaders (Phase 6Q-F-2-b)
# ─────────────────────────────────────────────────────────────────────

class TestTrafficYAMLConsumedByBrokerRegistries:
    """Phase 6Q-F-2-b: exercise the broker's SkillRegistry +
    AgentTypeRegistry YAML loaders with the non-water traffic
    configs. Pre-fix the gates were YAML-shape assertions only
    (TestTrafficYAMLConfigs above); this layer proves the loaders
    accept non-water configs without crashing.
    """

    FIXTURE_DIR = (
        Path(__file__).resolve().parents[2]
        / "examples" / "_test_fixtures" / "fake_traffic"
    )

    def test_skill_registry_loads_traffic_yaml(self):
        from broker.components.governance.registry import SkillRegistry
        reg = SkillRegistry()
        reg.register_from_yaml(str(self.FIXTURE_DIR / "traffic_skill_registry.yaml"))
        # 6 skills registered (5 commuter + 1 dispatcher)
        assert len(reg.skills) == 6
        assert "take_alternate_route" in reg.skills
        assert "switch_to_transit" in reg.skills
        assert "announce_advisory" in reg.skills
        # Default skill loaded from top-level YAML key.
        assert reg._default_skill == "do_nothing"
        # No flood-domain skill names leaked into the registry.
        assert "elevate_house" not in reg.skills
        assert "buy_insurance" not in reg.skills

    def test_agent_type_registry_loads_traffic_yaml(self):
        from broker.config.agent_types.registry import AgentTypeRegistry
        reg = AgentTypeRegistry()
        reg.load_from_yaml(self.FIXTURE_DIR / "traffic_agent_types.yaml")
        commuter = reg.get("commuter")
        dispatcher = reg.get("dispatcher")
        assert commuter is not None
        assert dispatcher is not None


_SUBPROCESS_SCRIPT = r"""
import sys, json
from broker.domains.registry import DomainPackRegistry
import examples._test_fixtures.fake_traffic  # noqa: F401 — registers traffic pack
# Verify registration succeeded.
assert DomainPackRegistry.get("traffic") is not None
# Dump water modules in sys.modules.
water = sorted(m for m in sys.modules if m.startswith("broker.domains.water"))
print(json.dumps({"water_modules": water}))
"""


class TestFakeTrafficSysModulesCleanliness:
    """Importing the traffic fixture package must NOT pull water
    modules into sys.modules. Subprocess-isolated."""

    def test_traffic_fixture_does_not_load_water(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS_SCRIPT],
            capture_output=True,
            text=True,
            cwd=str(repo),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"gate script failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        payload = json.loads(result.stdout.strip().split("\n")[-1])
        assert not payload["water_modules"], (
            f"importing fake_traffic fixture leaked water modules: "
            f"{payload['water_modules']}"
        )


# ─────────────────────────────────────────────────────────────────────
# Phase 6Q-F-2-c — validate-time escape-hatch gate
# ─────────────────────────────────────────────────────────────────────
# Existing tests at broker/tests/test_dispatcher_cascade_defense.py:100-126
# and broker/tests/test_genericity_runtime_gate.py:118-125 cover
# ``ThinkingValidator(framework=FRAMEWORK_ESCAPE_HATCH)`` CONSTRUCTION
# only. The 6Q-F-2-c E2E test below drives a full retry loop through
# ``validate()`` on the escape-hatch path — so we need a fast, isolated
# guard that validate-time behaviour stays graceful (no KeyError on
# empty ``_constructs``, no crash from absent label registry). If this
# class fails, the full E2E test below will fail with a much more
# expensive trace — so it runs first by file order.

class TestThinkingValidatorEscapeHatchValidateTime:
    """``ThinkingValidator(framework="")`` must execute ``validate()``
    cleanly when constructs and built-in checks are both empty.

    The escape-hatch path is the contract for any non-water domain
    that did not register a psychometric framework (per Phase 6Q-D).
    The fake_traffic fixture exercises exactly this path via its
    ``psychological_framework: ""`` YAML declaration.
    """

    def test_escape_hatch_validate_empty_state(self):
        from broker.validators.governance.thinking_validator import (
            ThinkingValidator,
            FRAMEWORK_ESCAPE_HATCH,
        )
        # builtin_checks=[] disables domain defaults so this stays a
        # pure base-class + YAML-rules-loop check (matches the
        # dispatcher's escape-hatch branch in build_domain_validators).
        validator = ThinkingValidator(
            framework=FRAMEWORK_ESCAPE_HATCH,
            builtin_checks=[],
        )
        # No constructs registered, no rules supplied, empty reasoning.
        results = validator.validate(
            skill_name="do_nothing",
            rules=[],
            context={"reasoning": {}, "state": {}},
        )
        assert isinstance(results, list)
        assert len(results) == 0
        # Sanity: the validator carries the escape-hatch sentinel.
        assert validator.framework == FRAMEWORK_ESCAPE_HATCH
        assert validator._constructs == {}

    def test_escape_hatch_validate_with_framework_agnostic_rule(self):
        from broker.governance.rule_types import GovernanceRule, RuleCondition
        from broker.validators.governance.thinking_validator import (
            ThinkingValidator,
            FRAMEWORK_ESCAPE_HATCH,
        )
        # A precondition-typed rule with no ``framework=`` field is
        # framework-agnostic per ``_validate_yaml_rules`` lines 354-357:
        # ``rule_framework = getattr(rule, 'framework', None)`` → None,
        # so the ``if rule_framework and rule_framework != framework``
        # skip never fires.
        rule = GovernanceRule(
            id="test_escape_hatch_precondition_rule",
            category="thinking",
            conditions=[
                RuleCondition(
                    type="precondition",
                    field="ready_state",
                    operator="==",
                    values=[True],
                )
            ],
            blocked_skills=["take_alternate_route"],
            level="ERROR",
            message="Cannot take alternate route when ready_state is True.",
        )
        validator = ThinkingValidator(
            framework=FRAMEWORK_ESCAPE_HATCH,
            builtin_checks=[],
        )
        results = validator.validate(
            skill_name="take_alternate_route",
            rules=[rule],
            context={"reasoning": {}, "state": {"ready_state": True}},
        )
        # Rule should trigger at least once — the same rule is
        # evaluated by both the base-class YAML path (``super().validate``
        # at thinking_validator.py:318) and the multi-condition path
        # (``_validate_yaml_rules`` at :322), so the precise count is an
        # internal evaluator detail. The point of this regression guard
        # is that validate-time does NOT crash on the escape-hatch path
        # when no constructs are registered, and that ERROR-level rule
        # metadata flows through correctly.
        assert isinstance(results, list)
        assert len(results) >= 1
        # Every triggered result must reference our rule and report
        # an ERROR-level block. The two evaluation paths
        # (``super().validate`` and ``_validate_yaml_rules``) populate
        # slightly different metadata key-sets — only the multi-condition
        # path injects ``framework`` — so we only assert keys both
        # paths agree on. The framework-leak guard belongs to the
        # multi-condition path; assert it on the subset of results that
        # carry it.
        for result in results:
            assert result.valid is False  # ERROR-level
            assert result.metadata["rule_id"] == "test_escape_hatch_precondition_rule"
        framework_tagged = [
            r for r in results if "framework" in r.metadata
        ]
        assert framework_tagged, (
            "at least one result must carry the framework key "
            "(emitted by _validate_yaml_rules)"
        )
        for result in framework_tagged:
            assert result.metadata["framework"] == FRAMEWORK_ESCAPE_HATCH


# ─────────────────────────────────────────────────────────────────────
# Phase 6Q-F-2-c — Full 1-year ExperimentRunner.run E2E gate
# ─────────────────────────────────────────────────────────────────────
# Layer 5 closure (per ~/.claude/plans/breezy-dazzling-knuth.md): drive
# ExperimentBuilder + ExperimentRunner end-to-end against the
# non-water fake_traffic domain, then assert the audit trace contains
# only traffic vocabulary AND no broker.domains.water.* module was
# newly imported during the run.

_FIXTURE_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples" / "_test_fixtures" / "fake_traffic"
)


class _TrafficSimulation:
    """Minimal traffic environment stub. Mirrors the
    ``TinySimulation`` pattern in
    ``examples/quickstart/01_barebone.py`` — the broker pipeline
    only requires ``advance_year()`` returning a dict and
    ``execute_skill()`` returning an ``ExecutionResult``."""

    def __init__(self):
        self.year = 0

    def advance_year(self):
        self.year += 1
        return {
            "current_year": self.year,
            "situation": (
                f"Year {self.year}: heavy congestion forecast on commuter routes."
            ),
            "congestion_level": 0.7,
        }

    def execute_skill(self, approved_skill):
        from broker.interfaces.skill_types import ExecutionResult
        return ExecutionResult(success=True, state_changes={})


def _build_traffic_agents():
    """3 agents — 2 commuters + 1 dispatcher. Constructed in Python
    (mirroring quickstart) rather than YAML-loaded because the
    AgentTypeRegistry path is already verified by
    ``TestTrafficYAMLConsumedByBrokerRegistries`` (6Q-F-2-b)."""
    from broker.agents import BaseAgent, AgentConfig
    from broker.agents.base import StateParam, Skill

    commuter_skills = [
        Skill("take_alternate_route", "Take alternate route", "delay_minutes", "decrease"),
        Skill("delay_departure", "Delay departure", "delay_minutes", "decrease"),
        Skill("switch_to_transit", "Switch to transit", "delay_minutes", "decrease"),
        Skill("carpool", "Carpool", "delay_minutes", "decrease"),
        Skill("do_nothing", "Do nothing", None, "none"),
    ]
    dispatcher_skills = [
        Skill("announce_advisory", "Announce advisory", "advisories_issued", "increase"),
    ]
    commuter_state = [
        StateParam("delay_minutes", (0, 120), 0.0, "Total commute delay"),
    ]
    dispatcher_state = [
        StateParam("advisories_issued", (0, 365), 0.0, "Advisories issued YTD"),
    ]

    def _commuter(name: str) -> BaseAgent:
        return BaseAgent(AgentConfig(
            name=name,
            agent_type="commuter",
            state_params=commuter_state,
            objectives=[],
            constraints=[],
            skills=commuter_skills,
        ))

    def _dispatcher(name: str) -> BaseAgent:
        return BaseAgent(AgentConfig(
            name=name,
            agent_type="dispatcher",
            state_params=dispatcher_state,
            objectives=[],
            constraints=[],
            skills=dispatcher_skills,
        ))

    return {
        "commuter_1": _commuter("commuter_1"),
        "commuter_2": _commuter("commuter_2"),
        "dispatcher_1": _dispatcher("dispatcher_1"),
    }


@pytest.fixture(scope="module")
def _traffic_e2e_run(tmp_path_factory):
    """Module-scoped fixture: build + run the 1-year traffic
    experiment ONCE. Subsequent tests inspect the captured audit
    artifacts. Keeps the slow part out of every test.

    Snapshots ``sys.modules`` before importing any broker module so
    the no-water-leak assertion can diff cleanly.
    """
    # Snapshot BEFORE any broker import inside this fixture body —
    # the registry / fixture imports at module-top already happened,
    # but the runtime path inside ExperimentRunner.run() must not
    # newly pull water modules.
    modules_before = set(sys.modules.keys())

    from broker.core.experiment import ExperimentBuilder
    from broker.components.memory.engine import WindowMemoryEngine

    # Self-checking guard: the in-fixture imports themselves must
    # not pull water modules. If a future refactor of
    # ExperimentBuilder adds a conditional ``broker.domains.water``
    # import at load time, the post-run sys.modules diff would
    # silently include it as "pre-existing" rather than catching it.
    pre_run_water = sorted(
        m for m in (set(sys.modules) - modules_before)
        if m.startswith("broker.domains.water")
    )
    assert not pre_run_water, (
        f"importing ExperimentBuilder or WindowMemoryEngine pulled "
        f"water modules into sys.modules: {pre_run_water}. The 6Q-F-2-c "
        f"runtime gate requires these load paths to stay water-free."
    )

    output_dir = tmp_path_factory.mktemp("traffic_e2e_out")

    agents = _build_traffic_agents()
    sim = _TrafficSimulation()

    captured_decisions = []

    def _pre_year(year, env, agents_):
        # Mirror quickstart pattern — runner injects current_year into
        # env automatically, so no mutation needed here.
        return None

    def _post_step(agent, result):
        approved = getattr(result, "approved_skill", None)
        captured_decisions.append({
            "agent_name": getattr(agent, "name", "?"),
            "agent_type": getattr(agent, "agent_type", "?"),
            "skill_name": approved.skill_name if approved else None,
            "approval_status": approved.approval_status if approved else None,
        })

    runner = (
        ExperimentBuilder()
        .with_model("mock")
        .with_years(1)
        .with_agents(agents)
        .with_simulation(sim)
        .with_skill_registry(str(_FIXTURE_DIR / "traffic_skill_registry.yaml"))
        .with_memory_engine(WindowMemoryEngine(window_size=3))
        .with_governance("strict", str(_FIXTURE_DIR / "traffic_agent_types.yaml"))
        .with_exact_output(str(output_dir))
        .with_workers(1)
        .with_seed(42)
        .with_lifecycle_hooks(pre_year=_pre_year, post_step=_post_step)
    ).build()

    error = None
    try:
        runner.run()
    except Exception as e:  # noqa: BLE001 — surface for assertion
        error = e

    modules_after = set(sys.modules.keys())
    newly_loaded_water = sorted(
        m for m in (modules_after - modules_before)
        if m.startswith("broker.domains.water")
    )

    return {
        "error": error,
        "output_dir": Path(output_dir),
        "captured_decisions": captured_decisions,
        "newly_loaded_water_modules": newly_loaded_water,
        "runner": runner,
    }


class TestTrafficE2ERuntime:
    """Phase 6Q-F-2-c — drive the broker end-to-end against
    fake_traffic and assert post-run invariants."""

    def test_run_completes_without_crash(self, _traffic_e2e_run):
        assert _traffic_e2e_run["error"] is None, (
            f"ExperimentRunner.run() raised: {_traffic_e2e_run['error']!r}"
        )

    def test_audit_artifacts_contain_traffic_skills_no_flood_leak(
        self, _traffic_e2e_run,
    ):
        # The broker partitions audit output per agent_type:
        #   ``<agent_type>_governance_audit.csv`` (canonical CSV row dump) +
        #   ``<agent_type>_traces.jsonl`` (streaming JSONL trace).
        # The presence of BOTH the commuter-prefixed AND the
        # dispatcher-prefixed file is itself a genericity-proof: the
        # broker handled two heterogeneous non-water agent types
        # without collapsing either onto a default partition.
        output_dir: Path = _traffic_e2e_run["output_dir"]
        all_files = sorted(p.name for p in output_dir.rglob("*"))

        csv_files = list(output_dir.rglob("*_governance_audit.csv"))
        jsonl_files = list(output_dir.rglob("*_traces.jsonl"))
        assert csv_files or jsonl_files, (
            f"no audit files written under {output_dir} — "
            f"contents: {all_files}"
        )

        commuter_outputs = [
            p for p in (csv_files + jsonl_files) if "commuter" in p.name
        ]
        dispatcher_outputs = [
            p for p in (csv_files + jsonl_files) if "dispatcher" in p.name
        ]
        assert commuter_outputs, (
            f"no commuter-partitioned audit found — contents: {all_files}"
        )
        assert dispatcher_outputs, (
            f"no dispatcher-partitioned audit found — contents: {all_files}"
        )

        # Concatenate all audit text for the vocabulary scan.
        audit_text = "\n".join(
            p.read_text(encoding="utf-8")
            for p in (csv_files + jsonl_files)
        )
        assert audit_text.strip(), "all audit files are empty"

        # Whitelisted traffic vocabulary appears.
        traffic_vocab = {
            "take_alternate_route", "delay_departure", "switch_to_transit",
            "carpool", "do_nothing", "announce_advisory",
        }
        present = {v for v in traffic_vocab if v in audit_text}
        assert present, (
            f"no traffic skill name found in audit. Vocab checked: "
            f"{sorted(traffic_vocab)}. Audit excerpt: {audit_text[:400]!r}"
        )

        # Regression guard: no water-domain vocabulary leaks into the
        # non-water audit. Comparison is case-insensitive on the raw
        # text; flood-skill names cover the headline water-domain
        # surface (elevation / insurance / buyout / etc.).
        lowered = audit_text.lower()
        flood_vocab = [
            "elevate_house", "buy_insurance", "do_buyout", "do_relocate",
            "elevation_year", "flood_depth_m",
        ]
        leaks = [w for w in flood_vocab if w in lowered]
        assert not leaks, (
            f"flood-domain vocabulary leaked into traffic audit: {leaks}"
        )

    def test_no_water_modules_loaded_during_run(self, _traffic_e2e_run):
        leaked = _traffic_e2e_run["newly_loaded_water_modules"]
        assert not leaked, (
            f"ExperimentRunner.run() pulled water modules into "
            f"sys.modules: {leaked}"
        )

    def test_reproducibility_manifest_written(self, _traffic_e2e_run):
        output_dir: Path = _traffic_e2e_run["output_dir"]
        manifests = list(output_dir.rglob("reproducibility_manifest.json"))
        snapshots = list(output_dir.rglob("config_snapshot.yaml"))
        assert manifests, (
            f"reproducibility_manifest.json missing under {output_dir}"
        )
        assert snapshots, f"config_snapshot.yaml missing under {output_dir}"
        # Parse to confirm valid JSON / YAML.
        json.loads(manifests[0].read_text(encoding="utf-8"))
        import yaml as _yaml
        _yaml.safe_load(snapshots[0].read_text(encoding="utf-8"))

    def test_post_step_hook_captured_decisions(self, _traffic_e2e_run):
        # Sanity that the runner exercised the agents at least once
        # — 3 agents × 1 year ≥ 3 decisions captured (assuming none
        # of them rejected before reaching post_step).
        decisions = _traffic_e2e_run["captured_decisions"]
        assert len(decisions) >= 3, (
            f"expected ≥3 captured post_step decisions, got {len(decisions)}: "
            f"{decisions}"
        )
        # Every captured agent_type must be one of the two traffic
        # agent types.
        for d in decisions:
            assert d["agent_type"] in {"commuter", "dispatcher"}, (
                f"unexpected agent_type in capture: {d!r}"
            )
