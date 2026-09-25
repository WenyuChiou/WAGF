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
        # call for the consolidated-reflection insight (unaffected by this
        # branch's fix -- included to confirm that, not to endorse it).
        #
        # KNOWN, PRE-EXISTING, OUT-OF-SCOPE BUG (not touched here): the real
        # _batch_reflect call (run_experiment.py) passes
        # {"significance": insight.importance, ...}, but
        # HumanCentricMemoryEngine._add_memory_internal
        # (broker/components/memory/engines/humancentric.py) only reads
        # metadata.get("importance", 0.5) -- "significance" is never the key
        # it looks for, so every reflection memory's importance silently
        # falls back to the hardcoded 0.5 default regardless of the actual
        # insight.importance value passed in. The 0.5 asserted below is
        # that bug's constant, not a deliberately calibrated value; it is
        # asserted so a change to this call site doesn't silently drift
        # without a green/red test noticing, not as a claim that 0.5 is
        # correct.
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
