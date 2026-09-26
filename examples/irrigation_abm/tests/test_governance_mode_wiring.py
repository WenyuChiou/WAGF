"""Regression tests for two bugs fixed on feat/irrigation-case-alignment
(commit 80d38322 and this follow-up commit):

(a) run_experiment.py's builder used to pass
    ``with_custom_validators([irrigation_governance_validator])``
    unconditionally, regardless of ``--governance-mode``. That validator
    (water right cap, drought severity, magnitude cap, demand floor/ceiling,
    curtailment awareness, compact allocation, ...) is a SECOND, independent
    governance layer on top of the YAML thinking/identity rules, so a
    ``--governance-mode disabled`` run was never actually ungoverned. Fixed
    by branching ``custom_validators`` on ``governance_mode``.

(b) ``HumanCentricMemoryEngine`` was constructed without
    ``emotion_keywords``, and ``IrrigationLifecycleHooks.pre_year`` called
    ``memory_engine.add_memory(aid, feedback)`` (no agent object), so
    ``_classify_emotion``/``_classify_source``
    (broker/components/memory/engines/humancentric.py) always fell back to
    generic keyword/pattern banks that don't share label names with the
    YAML's custom ``emotional_weights``/``source_weights`` -- every yearly
    outcome-feedback memory line scored a ~0.03 importance floor regardless
    of content. Fixed by passing ``emotion_keywords=irr_mem.get(
    "emotion_keywords")`` into the constructor and switching the call site
    to ``add_memory_for_agent(agent, feedback)`` so the agent's
    ``memory_config`` (auto-populated by
    ``broker/core/experiment_builder.py``'s Phase-12 injection) is
    consulted.

Both were verified to FAIL against a `git archive origin/main --
examples/irrigation_abm` snapshot of the pre-fix code and PASS against the
current tree; see the commit body for the fail-before/pass-after transcript.
(An earlier version of this file pinned (b) only via a reconstructed copy
of main()'s HumanCentricMemoryEngine(...) call -- code-review caught that
this would stay green even if the real fix in run_experiment.py were
reverted, since it never actually executed main() or pre_year. See
TestMemoryImportanceWiring's docstring for which tests now exercise the
real code paths versus which one is a YAML/engine calibration check.)

(c) The persona rewrite (irrigation_personas.py's ``_CLUSTER_PERSONAS`` /
    ``build_narrative_persona``) must render the agriculture-water-user
    framing and must never render the removed individual-farmer wording.

(d) run_ungoverned_experiment.py's argv-forwarding must actually forward
    "--governance-mode disabled" (TestUngovernedWrapperForwarding); the
    source-text pin in broker/tests/test_coupling_retrofit_pr9.py only
    checks that the wrapper imports and calls run_experiment's main, not
    what it passes to it.

(e) (a later follow-up fix -- see this commit's message for the
    fail-before/pass-after transcript) IrrigationLifecycleHooks._batch_reflect
    stored the consolidated reflection memory under metadata key
    "significance", but HumanCentricMemoryEngine._add_memory_internal
    (broker/components/memory/engines/humancentric.py) only reads
    metadata.get("importance", 0.5) -- "significance" was never the key
    it looked for, so every irrigation reflection's importance silently
    fell back to the 0.5 default regardless of insight.importance (in
    production, the adapter's compute_dynamic_importance score --
    IrrigationAdapter.compute_importance returns 0.55-0.95 depending on
    supply_ratio/drought_count/decision; the YAML's
    reflection.importance_boost only applies when no adapter is
    attached, which irrigation's own construction never does). Fixed by
    renaming the key to "importance" in run_experiment.py's
    _batch_reflect. See TestBatchReflectImportanceKey below, and the
    updated historical note
    in TestMemoryImportanceWiring.test_four_sample_lines_hit_expected_importance,
    which previously documented this as a known, out-of-scope bug.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

BASE = PROJECT_ROOT / "examples" / "irrigation_abm"
CONFIG_DIR = BASE / "config"


class _StopBeforeRun(Exception):
    """Raised by a monkeypatched ExperimentBuilder.build() to abort
    run_experiment.main() right after the builder is fully configured, but
    before .build() constructs the real engine or any simulation executes
    (no LLM calls, no result files beyond what main() writes before that
    point)."""


@pytest.fixture
def captured_build(monkeypatch):
    """Patch ExperimentBuilder.build to record self.custom_validators (the
    actual list of validator callables) AND self.memory_engine (the actual
    HumanCentricMemoryEngine instance main() constructed), then abort before
    running. Recording the real engine object -- not a reconstruction --
    is what lets test_main_passes_emotion_keywords_to_memory_engine below
    catch a regression in main()'s own HumanCentricMemoryEngine(...) call,
    as opposed to only pinning a copy of that call written into the test.

    Also saves/restores broker.utils.llm_utils.LLM_CONFIG's num_ctx/
    num_predict: main() calls apply_to_llm_config(), which mutates that
    module-level singleton and never restores it, so back-to-back
    disabled/strict invocations in the same test session could otherwise
    leak state across tests.
    """
    from broker.core.experiment_builder import ExperimentBuilder
    from broker.utils.llm_utils import LLM_CONFIG

    monkeypatch.setattr(LLM_CONFIG, "num_ctx", LLM_CONFIG.num_ctx)
    monkeypatch.setattr(LLM_CONFIG, "num_predict", LLM_CONFIG.num_predict)

    captured: dict = {}

    def fake_build(self):
        captured["custom_validators"] = list(self.custom_validators)
        captured["memory_engine"] = self.memory_engine
        raise _StopBeforeRun()

    monkeypatch.setattr(ExperimentBuilder, "build", fake_build)
    return captured


def _run_main_with_governance_mode(tmp_path, governance_mode):
    from examples.irrigation_abm.run_experiment import main

    argv = [
        "run_experiment.py",
        "--model", "mock",
        "--years", "1",
        "--agents", "2",
        "--seed", "42",
        "--workers", "1",
        "--output", str(tmp_path / f"gm_{governance_mode}"),
        "--governance-mode", governance_mode,
    ]
    old_argv = sys.argv
    sys.argv = argv
    try:
        with pytest.raises(_StopBeforeRun):
            main()
    finally:
        sys.argv = old_argv


class TestGovernanceModeCustomValidators:
    """(a) --governance-mode disabled/strict must build the engine with the
    right custom-validator list. Asserted on the actual builder object's
    attribute (a list of real callables), not on source text."""

    def test_disabled_mode_has_empty_custom_validators(self, tmp_path, captured_build):
        _run_main_with_governance_mode(tmp_path, "disabled")
        assert captured_build["custom_validators"] == []

    def test_strict_mode_has_irrigation_governance_validator(self, tmp_path, captured_build):
        from examples.irrigation_abm.validators.irrigation_validators import (
            irrigation_governance_validator,
        )

        _run_main_with_governance_mode(tmp_path, "strict")
        cv = captured_build["custom_validators"]
        assert len(cv) == 1
        assert cv[0] is irrigation_governance_validator


class _FakeAgent:
    """Minimal stand-in for BaseAgent: only .id and .memory_config are read
    by HumanCentricMemoryEngine.add_memory_for_agent()."""

    def __init__(self, agent_id, memory_config):
        self.id = agent_id
        self.memory_config = memory_config


def _build_memory_engine_like_run_experiment():
    """Reproduce run_experiment.py's HumanCentricMemoryEngine(...) call,
    kwarg for kwarg, against the real (current) agent_types.yaml."""
    from broker.components.memory.engine import HumanCentricMemoryEngine
    from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter

    with open(CONFIG_DIR / "agent_types.yaml", encoding="utf-8") as f:
        cfg_data = yaml.safe_load(f)
    global_cfg = cfg_data["global_config"]
    irr_cfg = cfg_data["irrigation_farmer"]
    irr_mem = irr_cfg.get("memory", {})
    gm = global_cfg.get("memory", {})
    rw = irr_mem.get("retrieval_weights", {})
    adapter_rw = IrrigationAdapter().retrieval_weights

    engine = HumanCentricMemoryEngine(
        window_size=5,
        top_k_significant=gm.get("top_k_significant", 2),
        consolidation_prob=gm.get("consolidation_probability", 0.7),
        consolidation_threshold=gm.get("consolidation_threshold", 0.6),
        decay_rate=gm.get("decay_rate", 0.1),
        emotional_weights=irr_mem.get("emotional_weights"),
        source_weights=irr_mem.get("source_weights"),
        emotion_keywords=irr_mem.get("emotion_keywords"),
        W_recency=rw.get("recency", adapter_rw.get("W_recency", 0.3)),
        W_importance=rw.get("importance", adapter_rw.get("W_importance", 0.4)),
        W_context=rw.get("context", adapter_rw.get("W_context", 0.3)),
        ranking_mode=irr_mem.get("ranking_mode", "weighted"),
        seed=42,
    )
    return engine, irr_mem


class TestMemoryImportanceWiring:
    """(b) emotion_keywords must reach the engine from the YAML, and the
    add_memory_for_agent() call (what pre_year actually uses) must let
    per-agent source_patterns fire instead of falling back to generic
    banks.

    test_main_passes_emotion_keywords_to_memory_engine and
    test_pre_year_uses_add_memory_for_agent_not_add_memory are the two
    tests that actually exercise run_experiment.py's own code (main()'s
    HumanCentricMemoryEngine(...) call, and
    IrrigationLifecycleHooks.pre_year's memory-engine call site,
    respectively) and would fail if either fix were reverted there.
    test_four_sample_lines_hit_expected_importance further down is a
    calibration check on the YAML's emotion_keywords/emotional_weights/
    source_weights/source_patterns against HumanCentricMemoryEngine's
    classifier -- it reconstructs its OWN engine instance rather than one
    built by run_experiment.py, so on its own it would NOT catch main() or
    pre_year regressing back to the pre-fix call shape; it exists to pin
    that the YAML's keyword/pattern lists actually produce the intended
    labels, which is a separate (also real) bug this branch fixed.
    """

    def test_main_passes_emotion_keywords_to_memory_engine(self, tmp_path, captured_build):
        """Runs run_experiment.main() for real (up to the point .build() is
        called) and asserts the ACTUAL constructed HumanCentricMemoryEngine
        instance has the YAML's emotion_keywords -- catches a regression to
        the pre-fix call, which omitted that kwarg entirely."""
        with open(CONFIG_DIR / "agent_types.yaml", encoding="utf-8") as f:
            cfg_data = yaml.safe_load(f)
        yaml_emotion_keywords = cfg_data["irrigation_farmer"]["memory"]["emotion_keywords"]

        _run_main_with_governance_mode(tmp_path, "strict")

        engine = captured_build["memory_engine"]
        assert engine is not None
        assert engine.emotion_keywords == yaml_emotion_keywords
        assert "critical" not in engine.emotion_keywords  # not the generic default bank

    def test_pre_year_uses_add_memory_for_agent_not_add_memory(self, tmp_path):
        """Unit-tests IrrigationLifecycleHooks.pre_year directly (real
        IrrigationEnvironment + a real IrrigationAgentProfile, but a mocked
        memory_engine on a stub runner) and asserts the year>1
        outcome-feedback write calls add_memory_for_agent, never
        add_memory. Fails if pre_year reverts to
        memory_engine.add_memory(aid, feedback)."""
        from unittest.mock import MagicMock
        from types import SimpleNamespace

        from broker.agents import AgentConfig, BaseAgent
        from examples.irrigation_abm.irrigation_env import (
            IrrigationEnvironment,
            WaterSystemConfig,
        )
        from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
        from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

        profile = IrrigationAgentProfile(
            agent_id="TestAgent", basin="lower_basin", cluster="aggressive",
            water_right=100_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_from_profiles([profile])

        config = AgentConfig(
            name="TestAgent", agent_type="irrigation_farmer",
            state_params=[], objectives=[], constraints=[], skills=[],
        )
        agent = BaseAgent(config)
        agent.custom_attributes = {}
        agents = {"TestAgent": agent}

        runner_stub = SimpleNamespace(memory_engine=MagicMock())
        hooks = IrrigationLifecycleHooks(
            env, runner_stub, [profile], reflection_engine=None, output_dir=tmp_path,
        )
        hooks.metrics_tracker = None
        hooks.feedback_config = {}

        # Year 1: build_action_outcome_feedback's memory write only fires
        # for year > 1 (no prior-year outcome to report).
        hooks.pre_year(1, {}, agents)
        runner_stub.memory_engine.add_memory_for_agent.assert_not_called()
        runner_stub.memory_engine.add_memory.assert_not_called()

        # Year 2: must use add_memory_for_agent (so per-agent memory_config
        # is consulted), never the agent-less add_memory.
        hooks.pre_year(2, {}, agents)
        runner_stub.memory_engine.add_memory_for_agent.assert_called_once()
        runner_stub.memory_engine.add_memory.assert_not_called()
        called_agent = runner_stub.memory_engine.add_memory_for_agent.call_args.args[0]
        assert called_agent is agent

    def test_four_sample_lines_hit_expected_importance(self):
        """YAML/engine calibration check (see class docstring): pins that
        the current emotion_keywords/emotional_weights/source_weights/
        source_patterns in agent_types.yaml actually produce the intended
        labels and weights against HumanCentricMemoryEngine's classifier,
        for four representative memory lines."""
        from examples.irrigation_abm.irrigation_personas import (
            build_action_outcome_feedback,
        )

        engine, irr_mem = _build_memory_engine_like_run_experiment()

        shortfall = build_action_outcome_feedback(
            action_ctx={"skill_name": "decrease_small", "magnitude_pct": 5.0},
            year=3, request=100_000, diversion=80_000,
            drought_index=0.42, preceding_factor=0,
        )
        fully_met_increase = build_action_outcome_feedback(
            action_ctx={"skill_name": "increase_small", "magnitude_pct": 4.0},
            year=3, request=100_000, diversion=100_000,
            drought_index=0.10, preceding_factor=1,
        )
        fully_met_maintain = build_action_outcome_feedback(
            action_ctx={"skill_name": "maintain_demand"},
            year=3, request=100_000, diversion=100_000,
            drought_index=0.10, preceding_factor=1,
        )
        reflection_line = (
            "Consolidated Reflection: I learned to balance water demand carefully."
        )

        # add_memory_for_agent: mirrors IrrigationLifecycleHooks.pre_year's
        # actual call for the three outcome-feedback lines.
        agent_a = _FakeAgent("Agent_shortfall", memory_config=irr_mem)
        engine.add_memory_for_agent(agent_a, shortfall)
        agent_b = _FakeAgent("Agent_increase", memory_config=irr_mem)
        engine.add_memory_for_agent(agent_b, fully_met_increase)
        agent_c = _FakeAgent("Agent_maintain", memory_config=irr_mem)
        engine.add_memory_for_agent(agent_c, fully_met_maintain)

        # add_memory with explicit metadata: mirrors _batch_reflect's actual
        # call shape for the consolidated-reflection insight.
        #
        # HISTORICAL NOTE (fixed by a later follow-up commit -- see class
        # (e) in this module's docstring and TestBatchReflectImportanceKey
        # below): the real
        # _batch_reflect call (run_experiment.py) used to pass
        # {"significance": insight.importance, ...}, but
        # HumanCentricMemoryEngine._add_memory_internal
        # (broker/components/memory/engines/humancentric.py) only reads
        # metadata.get("importance", 0.5) -- "significance" was never the
        # key it looked for, so every reflection memory's importance
        # silently fell back to the hardcoded 0.5 default regardless of the
        # actual insight.importance value passed in. That call site now
        # passes "importance" instead. This test still constructs the
        # metadata dict directly with the legacy "significance" key,
        # deliberately, to document that HumanCentricMemoryEngine falls
        # back to 0.5 for any key it doesn't recognize; the 0.5 asserted
        # below is that fallback constant, not a claim that "significance"
        # is a supported alias for "importance".
        engine.add_memory(
            "Agent_reflection",
            reflection_line,
            {"significance": 0.9, "emotion": "major", "source": "personal", "type": "reflection"},
        )

        def importance_of(agent_id):
            return round(engine.working[agent_id][-1]["importance"], 4)

        assert importance_of("Agent_shortfall") == 1.0
        assert engine.working["Agent_shortfall"][-1]["emotion"] == "water_crisis"
        assert engine.working["Agent_shortfall"][-1]["source"] == "personal"

        assert importance_of("Agent_increase") == 0.8
        assert engine.working["Agent_increase"][-1]["emotion"] == "strategic_choice"

        assert importance_of("Agent_maintain") == 0.6
        assert engine.working["Agent_maintain"][-1]["emotion"] == "positive_outcome"

        assert importance_of("Agent_reflection") == 0.5


class TestPreYearReportsPriorYearOutcome:
    """F05 (2026-09-25 audit): by the time pre_year(year) runs,
    env.advance_year(year) has already recomputed agent_state["diversion"]
    under YEAR's own provisional settlement
    (irrigation_env.py: IrrigationEnvironment.advance_year), for
    whatever request was last set (year-1's decision). Reading
    agent_state/ctx directly for the "last year" memory line therefore
    silently reports year t's re-derivation of year t-1's request, mislabeled
    as year t-1 -- disagreeing with what post_year(year-1) actually logged
    to simulation_log.csv for year t-1. post_year now snapshots each year's
    own outcome onto agent._last_year_outcome before the NEXT advance_year
    call can touch it, and pre_year reads that snapshot instead."""

    def test_year2_memory_reports_year1_diversion_not_year2_recomputation(self, tmp_path, monkeypatch):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        from broker.agents import AgentConfig, BaseAgent
        from broker.interfaces.skill_types import ApprovedSkill
        from examples.irrigation_abm.irrigation_env import (
            IrrigationEnvironment,
            WaterSystemConfig,
        )
        from examples.irrigation_abm.irrigation_personas import IrrigationAgentProfile
        from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

        profile = IrrigationAgentProfile(
            agent_id="TestAgent", basin="lower_basin", cluster="aggressive",
            water_right=100_000.0,
        )
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_from_profiles([profile])

        # Force a deterministic, DIFFERENT curtailment tier each year (see
        # TestIrrigationEnvironment.test_shortage_tier_computation for these
        # exact mead-level -> tier mappings) so the SAME request produces a
        # different diversion in year 1 vs year 2's re-derivation.
        mead_levels = iter([1100.0, 1030.0])  # tier 0 (0%), then tier 2 (10%)
        # Supply-side redesign (2026-09-25): the 1 January level is read
        # from committed storage via _storage_to_elevation inside
        # advance_year (the old _generate_lake_mead_level is retired).
        monkeypatch.setattr(env, "_storage_to_elevation", lambda _s: next(mead_levels))

        config = AgentConfig(
            name="TestAgent", agent_type="irrigation_farmer",
            state_params=[], objectives=[], constraints=[], skills=[],
        )
        agent = BaseAgent(config)
        agent.custom_attributes = {}
        agents = {"TestAgent": agent}

        runner_stub = SimpleNamespace(memory_engine=MagicMock(), _current_year=1)
        hooks = IrrigationLifecycleHooks(
            env, runner_stub, [profile], reflection_engine=None, output_dir=tmp_path,
        )
        hooks.metrics_tracker = None
        hooks.feedback_config = {}

        # --- Year 1: healthy conditions, no curtailment ---
        env.advance_year()
        assert env._agents["TestAgent"]["curtailment_ratio"] == 0.0
        hooks.pre_year(1, {}, agents)  # year 1: no prior-year memory write

        skill = ApprovedSkill(
            skill_name="maintain_demand", agent_id="TestAgent",
            approval_status="APPROVED", execution_mapping="env.execute_skill",
        )
        skill.parameters = {}
        result = env.execute_skill(skill)
        agent._last_action_context = {"skill_name": "maintain_demand", "year": 1}
        hooks.post_step(agent, SimpleNamespace(
            approved_skill=skill, execution_result=result, skill_proposal=None,
        ))
        hooks.post_year(1, agents)

        year1_diversion = hooks.logs[-1]["diversion"]

        # --- Year 2: severe curtailment re-derives year 1's OWN request ---
        runner_stub._current_year = 2
        env.advance_year()
        assert env._agents["TestAgent"]["curtailment_ratio"] == pytest.approx(0.10)
        # Sanity: advance_year(2) DID overwrite agent["diversion"] in place,
        # under year 2's curtailment, for year 1's unchanged request -- this
        # is the corrupted value the pre-fix pre_year read directly.
        assert env._agents["TestAgent"]["diversion"] != pytest.approx(year1_diversion)

        hooks.pre_year(2, {}, agents)

        runner_stub.memory_engine.add_memory_for_agent.assert_called_once()
        feedback_text = runner_stub.memory_engine.add_memory_for_agent.call_args.args[1]
        assert f"received {year1_diversion:,.0f} acre-ft" in feedback_text
        assert f"received {env._agents['TestAgent']['diversion']:,.0f} acre-ft" not in feedback_text


class TestBatchReflectImportanceKey:
    """(e) IrrigationLifecycleHooks._batch_reflect must store the
    consolidated-reflection memory under the "importance" metadata key,
    not "significance" -- see class (e) in this module's docstring.

    test_batch_reflect_stores_insight_importance_not_default drives
    _batch_reflect itself (real HumanCentricMemoryEngine, a stub
    reflection engine and runner, adapter=None) and would fail if the
    call site reverted to "significance" (the stored value would
    silently be 0.5 instead of the stub insight's 0.9).
    test_batch_reflect_uses_adapter_dynamic_importance_end_to_end covers
    the production path the first test deliberately skips: irrigation
    always attaches a real IrrigationAdapter, so _batch_reflect's
    dynamic-importance override replaces insight.importance before the
    fixed metadata key is built; this drives that full chain with a real
    IrrigationAdapter and pins its drought_year (0.95) / "critical"
    output landing in the stored memory.
    test_reflection_ranks_above_met_after_increase_in_retrieve documents
    the intended consequence for a synthetic 4-memory agent: with the
    r42-style wired outcome-line importances (1.0 / 0.8 / 0.6, per
    TestMemoryImportanceWiring.test_four_sample_lines_hit_expected_importance)
    plus a 0.9 reflection stored via the fixed "importance" key, and
    W_recency zeroed to isolate importance as the sole ranking input
    (see that test's own docstring for why: at the engine's real
    W_recency=0.3, the reflection is also the most-recently-added
    memory, so recency alone would make it edge out the "fully met
    after increase" line even at the pre-fix 0.5 importance, which
    would not actually guard the fix), retrieve(top_k=3) ranks the
    reflection above the "fully met after increase" (0.8) outcome line.
    """

    @staticmethod
    def _fake_llm_invoke(agent_type):
        def _invoke(prompt):
            return "RAW_REFLECTION_TEXT"
        return _invoke

    def test_batch_reflect_stores_insight_importance_not_default(self):
        from types import SimpleNamespace

        from broker.agents import AgentConfig, BaseAgent
        from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

        engine, _irr_mem = _build_memory_engine_like_run_experiment()

        config = AgentConfig(
            name="Agent_1", agent_type="irrigation_farmer",
            state_params=[], objectives=[], constraints=[], skills=[],
        )
        agent = BaseAgent(config)
        agent.custom_attributes = {}
        agent.is_active = True

        # Seed a prior memory so retrieve(top_k=10) is non-empty and the
        # agent enters the reflection batch (mirrors a farmer who has
        # accumulated at least one outcome-feedback memory before the
        # year-end reflection call).
        engine.add_memory_for_agent(agent, "I requested less water than usual this year.")

        insight = SimpleNamespace(
            importance=0.9,
            summary="I learned to balance water demand carefully.",
        )

        class _StubReflectionEngine:
            # Falsy adapter: skips _batch_reflect's dynamic-importance
            # override and adapter-based emotion classification, so the
            # stub insight's importance=0.9 and the "major" fallback
            # emotion pass through to the memory-engine call unchanged.
            adapter = None

            def generate_batch_reflection_prompt(
                self, batch, year, reflection_questions=None, persona_instruction=None,
            ):
                return "PROMPT"

            def parse_batch_reflection_response(self, text, batch_ids, year):
                return {batch_ids[0]: insight}

            def store_insight(self, aid, ins):
                pass

        runner_stub = SimpleNamespace(
            broker=SimpleNamespace(config=SimpleNamespace(get_reflection_config=lambda: {})),
            agents={"Agent_1": agent},
            memory_engine=engine,
            get_llm_invoke=self._fake_llm_invoke,
        )

        hooks = IrrigationLifecycleHooks(
            # F08: _batch_reflect now always calls env.get_agent_state(aid)
            # to build water_right_pct/supply_ratio (real IrrigationEnvironment
            # shape); an empty dict is a safe stub here since adapter=None
            # means this test's assertions never depend on those values.
            env=SimpleNamespace(get_agent_state=lambda aid: {}),
            runner=runner_stub,
            profiles=[],
            reflection_engine=_StubReflectionEngine(),
            output_dir=None,
        )

        hooks._batch_reflect(year=3)

        stored = engine.working["Agent_1"][-1]
        assert stored["content"] == "Consolidated Reflection: I learned to balance water demand carefully."
        assert stored["importance"] == pytest.approx(0.9)

    def test_batch_reflect_uses_adapter_dynamic_importance_end_to_end(self):
        """test_batch_reflect_stores_insight_importance_not_default above
        stubs the adapter out (adapter=None) to isolate the key-rename
        fix; in production, irrigation always attaches a real
        IrrigationAdapter (run_experiment.py's
        ReflectionEngine(..., adapter=irrigation_adapter)), which means
        _batch_reflect's dynamic-importance override
        (self.reflection_engine.compute_dynamic_importance ->
        adapter.compute_importance) ALWAYS replaces insight.importance
        before the (now-fixed) metadata dict is built -- so what actually
        reaches the "importance" key in production is the adapter's
        score, not the YAML's static reflection.importance_boost.

        F08+F33 (2026-09-25 audit) follow-up: _batch_reflect's own
        context-building was ALSO wrong -- ``env.get_supply_ratio()``
        never existed on the real IrrigationEnvironment (always the 1.0
        fallback), and ``water_right_pct`` read the raw acre-foot
        entitlement from custom_attributes instead of a 0-1 fraction --
        so in production this branch never actually fired; the fixed
        0.90 the audit measured came from the OTHER always-true branch
        (see IrrigationAdapter.compute_importance's docstring). This test
        now drives _batch_reflect with a real IrrigationAdapter and a
        stub env whose get_agent_state() reports diversion/request = 0.5
        (< 0.60), so IrrigationAdapter.compute_importance's drought_year
        branch fires (0.95, overriding the stub insight's placeholder 0.2
        -- chosen so the assertion only passes if the override actually
        ran) and adapter.classify_emotion returns "water_crisis" (a real
        irrigation_farmer.memory.emotional_weights key) for the same
        low-supply context, pinning the full corrected chain end to
        end."""
        from types import SimpleNamespace

        from broker.agents import AgentConfig, BaseAgent
        from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter
        from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

        engine, _irr_mem = _build_memory_engine_like_run_experiment()

        config = AgentConfig(
            name="Agent_drought", agent_type="irrigation_farmer",
            state_params=[], objectives=[], constraints=[], skills=[],
        )
        agent = BaseAgent(config)
        agent.custom_attributes = {
            "years_farming": 4,
            "has_efficient_system": False,
            "cluster": "aggressive",
        }
        agent.is_active = True
        # F08: recent_decision now comes from _last_action_context (set by
        # the real runner's _apply_state_changes), not
        # custom_attributes["last_decision"] (never written in production).
        agent._last_action_context = {"skill_name": "maintain_demand"}
        # F08: drought_count now comes from this plain attribute (set by
        # post_year's cumulative counter), not
        # custom_attributes["drought_count"] (never written in production).
        agent.drought_count = 2

        engine.add_memory_for_agent(agent, "I requested less water than usual this year.")

        # Placeholder importance (0.2) deliberately does NOT match the
        # adapter's drought_year score (0.95): the assertion below only
        # passes if compute_dynamic_importance's override actually ran.
        insight = SimpleNamespace(
            importance=0.2,
            summary="Water was scarce and I had to cut back sharply.",
        )

        class _StubReflectionEngineWithAdapter:
            def __init__(self):
                self.adapter = IrrigationAdapter()

            def generate_batch_reflection_prompt(
                self, batch, year, reflection_questions=None, persona_instruction=None,
            ):
                return "PROMPT"

            def parse_batch_reflection_response(self, text, batch_ids, year):
                return {batch_ids[0]: insight}

            def store_insight(self, aid, ins):
                pass

            def compute_dynamic_importance(self, context, base_importance=0.9):
                # Mirrors ReflectionEngine.compute_dynamic_importance's
                # adapter branch (broker/components/cognitive/reflection.py).
                return self.adapter.compute_importance(context, base_importance)

        class _StubEnvForBatchReflect:
            """Same shape as IrrigationEnvironment.get_agent_state(): a
            50% delivery ratio (diversion/request) so
            IrrigationAdapter.compute_importance's drought_year branch
            fires, matching this test's original intent."""

            def get_agent_state(self, agent_id):
                return {"water_right": 200_000.0, "request": 100_000.0, "diversion": 50_000.0}

        runner_stub = SimpleNamespace(
            broker=SimpleNamespace(config=SimpleNamespace(get_reflection_config=lambda: {})),
            agents={"Agent_drought": agent},
            memory_engine=engine,
            get_llm_invoke=self._fake_llm_invoke,
        )

        hooks = IrrigationLifecycleHooks(
            env=_StubEnvForBatchReflect(),
            runner=runner_stub,
            profiles=[],
            reflection_engine=_StubReflectionEngineWithAdapter(),
            output_dir=None,
        )

        hooks._batch_reflect(year=5)

        stored = engine.working["Agent_drought"][-1]
        assert stored["importance"] == pytest.approx(
            IrrigationAdapter.importance_profiles["drought_year"]
        )
        assert stored["emotion"] == "water_crisis"


class TestIrrigationAdapterRealisticInputs:
    """F08+F33 (2026-09-25 audit): with real (correctly-scaled) inputs,
    IrrigationAdapter.compute_importance/classify_emotion must actually
    discriminate between contrasting agent situations, and
    classify_emotion's output must always be a key present in
    irrigation_farmer.memory.emotional_weights -- the old "important"
    label was not one, so HumanCentricMemoryEngine._apply_decay silently
    fell back to its own 0.1 default for every irrigation reflection
    regardless of the classified emotion."""

    def test_severe_shortfall_vs_fully_met_yield_different_importance_and_valid_emotion(self):
        from examples.irrigation_abm.adapters.irrigation_adapter import IrrigationAdapter

        with open(CONFIG_DIR / "agent_types.yaml", encoding="utf-8") as f:
            cfg_data = yaml.safe_load(f)
        valid_emotion_keys = set(cfg_data["irrigation_farmer"]["memory"]["emotional_weights"])

        adapter = IrrigationAdapter()

        severe_shortfall_ctx = {
            "water_right_pct": 0.9,        # near cap, high pressure
            "supply_ratio": 0.4,           # delivered only 40% of request
            "recent_decision": "increase_demand",
            "drought_count": 3,
        }
        fully_met_ctx = {
            "water_right_pct": 0.3,        # well under water right
            "supply_ratio": 1.0,           # demand fully met
            "recent_decision": "maintain_demand",
            "drought_count": 0,
        }

        severe_importance = adapter.compute_importance(severe_shortfall_ctx)
        met_importance = adapter.compute_importance(fully_met_ctx)
        assert severe_importance != met_importance
        assert severe_importance > met_importance

        severe_emotion = adapter.classify_emotion("increase_demand", severe_shortfall_ctx)
        met_emotion = adapter.classify_emotion("maintain_demand", fully_met_ctx)
        assert severe_emotion in valid_emotion_keys
        assert met_emotion in valid_emotion_keys
        assert severe_emotion != met_emotion

    def test_reflection_ranks_above_met_after_increase_in_retrieve(self):
        """Isolates the ranking consequence of the fix from recency: with
        the engine's own production weights (W_recency=0.3), the
        reflection is also the most-recently-added memory, so it would
        edge out the "fully met after increase" line on recency ALONE
        even at the pre-fix 0.5 importance (verified by hand: 0.5071 vs
        0.5000 vs 0.4857) -- that would make this assertion pass whether
        or not the key-rename fix is present, which is not a regression
        test. Zeroing W_recency (and W_context, moot here since no
        contextual_boosters are passed) isolates importance as the only
        scoring input, so the assertion is driven purely by the stored
        "importance" value -- exactly what the key-rename fix wires
        correctly. Verified by hand: with W_recency=0, importance=0.9
        (fixed) ranks [shortfall 0.5000, reflection 0.4500, increase
        0.4000] (reflection in top_k=3, above increase); importance=0.5
        (the pre-fix bug's constant) ranks [shortfall 0.5000, increase
        0.4000, maintain 0.3000] (reflection dropped out of top_k=3
        entirely)."""
        from examples.irrigation_abm.irrigation_personas import (
            build_action_outcome_feedback,
        )

        engine, irr_mem = _build_memory_engine_like_run_experiment()
        # Pins the WEIGHTED-mode arithmetic. Irrigation itself runs the
        # composed ("legacy") retrieval since 2026-09-26 (SI section 3.8),
        # so the mode is set explicitly here.
        engine.ranking_mode = "weighted"
        engine.W_recency = 0.0
        engine.W_context = 0.0
        agent = _FakeAgent("Agent_ranking", memory_config=irr_mem)

        shortfall = build_action_outcome_feedback(
            action_ctx={"skill_name": "decrease_small", "magnitude_pct": 5.0},
            year=3, request=100_000, diversion=80_000,
            drought_index=0.42, preceding_factor=0,
        )
        fully_met_increase = build_action_outcome_feedback(
            action_ctx={"skill_name": "increase_small", "magnitude_pct": 4.0},
            year=3, request=100_000, diversion=100_000,
            drought_index=0.10, preceding_factor=1,
        )
        fully_met_maintain = build_action_outcome_feedback(
            action_ctx={"skill_name": "maintain_demand"},
            year=3, request=100_000, diversion=100_000,
            drought_index=0.10, preceding_factor=1,
        )

        # Added in chronological order matching a real year: outcome
        # feedback lines land during pre_year; the consolidated reflection
        # lands last (post_year -> _batch_reflect), via the FIXED
        # "importance" key.
        engine.add_memory_for_agent(agent, shortfall)           # importance 1.0
        engine.add_memory_for_agent(agent, fully_met_increase)  # importance 0.8
        engine.add_memory_for_agent(agent, fully_met_maintain)  # importance 0.6
        engine.add_memory(
            "Agent_ranking",
            "Consolidated Reflection: I learned to balance water demand carefully.",
            {"importance": 0.9, "emotion": "major", "source": "personal", "type": "reflection"},
        )

        results = engine.retrieve(agent, top_k=3)
        contents = [r["content"] for r in results]

        assert fully_met_maintain not in contents, (
            "the lowest-importance (0.6) outcome line should be the one "
            f"bumped out of top_k=3; got {contents!r}"
        )
        assert "Consolidated Reflection: I learned to balance water demand carefully." in contents
        assert fully_met_increase in contents

        reflection_idx = contents.index(
            "Consolidated Reflection: I learned to balance water demand carefully."
        )
        increase_idx = contents.index(fully_met_increase)
        assert reflection_idx < increase_idx, (
            "a 0.9 reflection should outrank the 0.8 fully-met-after-increase "
            f"outcome line in top_k=3 retrieval when ranked by importance "
            f"alone; got order {contents!r}"
        )


class TestPersonaGenericWording:
    """(c) every cluster's narrative persona uses the agriculture-water-user
    framing and none of the removed individual-farmer wording."""

    _BANNED_SUBSTRINGS = ("acres", "crop", "farming for", "neighbor", "farmer")

    @pytest.mark.parametrize(
        "cluster",
        ["aggressive", "forward_looking_conservative", "myopic_conservative"],
    )
    def test_persona_wording(self, cluster):
        from examples.irrigation_abm.irrigation_personas import (
            IrrigationAgentProfile,
            build_narrative_persona,
        )

        profile = IrrigationAgentProfile(
            agent_id="TestAgent",
            basin="lower_basin",
            cluster=cluster,
            water_right=123_456.0,
        )

        seen_variants = set()
        for seed in range(20):
            text = build_narrative_persona(profile, rng=np.random.default_rng(seed))
            seen_variants.add(text)
            assert "agriculture water user" in text
            assert "water right of" in text
            lowered = text.lower()
            for banned in self._BANNED_SUBSTRINGS:
                assert banned not in lowered, (
                    f"{cluster} persona text still contains {banned!r}: {text!r}"
                )

        # both template variants for this cluster get exercised somewhere
        # across 20 different seeds.
        assert len(seen_variants) >= 2, (
            f"only one template variant observed for {cluster!r} across 20 seeds"
        )


class TestUngovernedWrapperForwarding:
    """broker/tests/test_coupling_retrofit_pr9.py::
    test_ungoverned_forwards_to_run_experiment_main only pins that
    run_ungoverned_experiment.py's source imports and calls
    run_experiment's main -- it does not check WHAT gets forwarded, so it
    would not catch someone dropping "--governance-mode disabled" from
    _build_forwarding_argv (the one line that actually makes the wrapper
    "ungoverned"). These two tests exercise run_ungoverned_experiment.main()
    for real and pin that behavior instead."""

    def test_forwards_governance_mode_disabled(self, monkeypatch, tmp_path):
        import examples.irrigation_abm.run_ungoverned_experiment as run_ungoverned

        recorded: dict = {}

        def fake_run_experiment_main():
            recorded["argv"] = list(sys.argv)

        monkeypatch.setattr(run_ungoverned, "_run_experiment_main", fake_run_experiment_main)

        old_argv = sys.argv
        sys.argv = [
            "run_ungoverned_experiment.py",
            "--model", "mock", "--years", "1", "--agents", "2", "--seed", "42",
            "--output", str(tmp_path),
        ]
        try:
            run_ungoverned.main()
        finally:
            sys.argv = old_argv

        argv = recorded["argv"]
        assert "--governance-mode" in argv
        assert argv[argv.index("--governance-mode") + 1] == "disabled"

    def test_wrapper_end_to_end_builds_with_empty_custom_validators(self, tmp_path, captured_build):
        """Stronger, end-to-end version of the above: drives the wrapper's
        real main() (which forwards into run_experiment.main(), which
        reaches the same patched ExperimentBuilder.build() the other tests
        in this file use) and asserts the resulting custom_validators list
        is empty -- the actual governance behavior the wrapper exists to
        provide, exercised through the wrapper's own entry point rather
        than by calling run_experiment.py directly."""
        import examples.irrigation_abm.run_ungoverned_experiment as run_ungoverned

        old_argv = sys.argv
        sys.argv = [
            "run_ungoverned_experiment.py",
            "--model", "mock", "--years", "1", "--agents", "2", "--seed", "42",
            "--output", str(tmp_path),
        ]
        try:
            with pytest.raises(_StopBeforeRun):
                run_ungoverned.main()
        finally:
            sys.argv = old_argv

        assert captured_build["custom_validators"] == []
