"""PR-5 — offline replay: snapshots, masking, the determinism gate.

These tests pin the things that make an ablation readable rather than
merely runnable:

1. A snapshot loads from a run directory and reports which fidelity
   regime produced it (today: ``prompt_only``, and only ``prompt_only``).
2. A mask SUBSTITUTES a neutral rendering and never deletes the span,
   and a rendering that raises costs one arm rather than the whole grid.
3. The determinism gate passes on a deterministic decider, fails on one
   that disagrees with itself, and fails on one that agrees with itself
   because it returned nothing at all.
4. The refusals are refusals: governance replay, executed-stage replay
   and an unregistered domain all stop rather than reporting a number.
5. The new DomainPack hook defaults to ``{}`` and leaves the shipped
   packs alone.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import types
from pathlib import Path

import pytest

from _pr5_run_fixture import FLOOD_CONFIG, write_run_dir as _write_run_dir
from broker.experiments.replay import (
    ARM_BASELINE,
    ARM_CONTROL,
    ARM_MASKED,
    FIDELITY_PROMPT_ONLY,
    FactorMap,
    MaskSpec,
    apply_mask,
    bind_seed,
    build_replay_decider,
    determinism_check,
    load_snapshots,
    replay_decision,
    resolve_model,
)

@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    return _write_run_dir(tmp_path)


@pytest.fixture()
def flood_masks() -> FactorMap:
    from examples.single_agent.flood_factor_masks import FLOOD_FACTOR_MASKS
    return FactorMap(FLOOD_FACTOR_MASKS)


@pytest.fixture()
def validators_module(request) -> str:
    """A throwaway module satisfying the --validators-module contract.

    Registered in ``sys.modules`` so ``importlib.import_module`` finds it
    without writing a file the repo would then have to own.
    """
    name = "_pr5_fake_validators"
    module = types.ModuleType(name)
    module.calls = []

    def build_custom_validators(config):
        module.calls.append(config)
        return []

    module.build_custom_validators = build_custom_validators
    sys.modules[name] = module
    request.addfinalizer(lambda: sys.modules.pop(name, None))
    return name


# ─────────────────────────────────────────────────────────────────────
# 1. Loading
# ─────────────────────────────────────────────────────────────────────

class TestSnapshotLoading:
    def test_loads_one_snapshot_per_decision(self, run_dir: Path):
        snapshots = load_snapshots(run_dir)
        assert len(snapshots) == 4
        assert {s.agent_id for s in snapshots} == {"Agent_1", "Agent_2"}
        assert {s.year for s in snapshots} == {1, 2}

    def test_carries_provenance(self, run_dir: Path):
        snapshot = load_snapshots(run_dir)[0]
        assert snapshot.git_commit == "deadbeefcafe0000000000000000000000000000"
        assert snapshot.run_dir == str(run_dir)
        assert snapshot.trace_file == "household_traces.jsonl"
        assert snapshot.model == "mock"

    def test_todays_traces_are_prompt_only(self, run_dir: Path):
        """The audit writer records the rendered prompt, not the context
        dict the builder returned, so nothing can be rebuilt today."""
        assert all(s.fidelity == FIDELITY_PROMPT_ONLY for s in load_snapshots(run_dir))

    def test_a_context_snapshot_does_not_unlock_a_second_regime(
        self, tmp_path: Path, caplog,
    ):
        """C2: ``context_rebuilt`` was a label with no implementation
        behind it. A trace carrying the context is still replayed by
        editing the prompt text, and says so out loud."""
        run = _write_run_dir(tmp_path, n_agents=1, n_years=1)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        trace = json.loads(lines[1])
        trace["context_snapshot"] = {"personal": {"id": "Agent_1"}, "state": {}}
        lines[1] = json.dumps(trace)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report: dict = {}
        with caplog.at_level(logging.WARNING):
            snapshot = load_snapshots(run, report=report)[0]
        assert snapshot.fidelity == FIDELITY_PROMPT_ONLY
        assert report["n_context_snapshot_ignored"] == 1
        assert "context-level replay is not implemented" in caplog.text

    def test_reference_action_defaults_to_the_proposal(self, run_dir: Path):
        snapshot = load_snapshots(run_dir)[0]
        assert snapshot.reference_action() == "buy_insurance"
        assert snapshot.reference_action("executed") == "buy_insurance"
        with pytest.raises(ValueError):
            snapshot.reference_action("whatever")

    def test_missing_raw_dir_is_an_error_not_an_empty_list(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            load_snapshots(tmp_path)

    def test_prompt_less_traces_are_skipped(self, tmp_path: Path):
        run = _write_run_dir(tmp_path, n_agents=1, n_years=1)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        trace = json.loads(lines[1])
        trace["input"] = ""
        lines.append(json.dumps(trace))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert len(load_snapshots(run)) == 1

    def test_intake_counts_reach_the_caller(self, tmp_path: Path):
        """P2: "6 snapshots" needs a denominator. The report says how
        many trace rows the files held and where the rest went."""
        run = _write_run_dir(tmp_path, n_agents=2, n_years=2)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        trace = json.loads(lines[1])
        trace["input"] = ""
        lines.append(json.dumps(trace))
        lines.append("{not json at all")
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report: dict = {}
        snapshots = load_snapshots(run, report=report)
        assert len(snapshots) == 4
        assert report["n_traces_read"] == 5      # 4 real + 1 prompt-less
        assert report["n_dropped_malformed"] == 1
        assert report["n_skipped_no_prompt"] == 1
        assert report["n_snapshots"] == 4

    def test_limit_still_warns_about_dropped_traces(self, tmp_path: Path, caplog):
        """S5: the --limit early return used to jump over the warning,
        so a run that silently dropped ABORTED rows looked clean."""
        run = _write_run_dir(tmp_path, n_agents=2, n_years=2)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        blank = json.loads(lines[1])
        blank["input"] = ""
        lines.insert(1, json.dumps(blank))
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        report: dict = {}
        with caplog.at_level(logging.WARNING):
            snapshots = load_snapshots(run, limit=1, report=report)
        assert len(snapshots) == 1
        assert report["n_skipped_no_prompt"] == 1
        assert "carried no prompt" in caplog.text


class TestModelResolution:
    def test_the_flag_wins(self, run_dir: Path):
        model, source = resolve_model(run_dir, "gemma4:e4b")
        assert model == "gemma4:e4b"
        assert "cli" in source

    def test_otherwise_the_run_manifest(self, run_dir: Path):
        model, source = resolve_model(run_dir, None)
        assert model == "mock"
        assert "manifest" in source

    def test_with_neither_it_refuses_rather_than_defaulting_to_mock(
        self, tmp_path: Path,
    ):
        """P2: a silent 'mock' fallback returns the first numbered option
        for every prompt, so the whole table would read as exact zeros."""
        run = _write_run_dir(tmp_path, n_agents=1, n_years=1)
        manifest = json.loads(
            (run / "reproducibility_manifest.json").read_text(encoding="utf-8"))
        manifest.pop("model")
        (run / "reproducibility_manifest.json").write_text(
            json.dumps(manifest), encoding="utf-8")
        with pytest.raises(ValueError, match="Defaulting to 'mock' is refused"):
            resolve_model(run, None)


# ─────────────────────────────────────────────────────────────────────
# 2. Masking
# ─────────────────────────────────────────────────────────────────────

class TestMasking:
    def test_neutral_rendering_replaces_and_never_deletes(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        spec = flood_masks["neighbor_adoption_history"]
        result = apply_mask(snapshot.prompt, spec, ARM_MASKED)

        assert result.applied
        assert "I observe 25% of neighbors elevated" not in result.prompt
        assert "No information about neighbours is available." in result.prompt
        # The line still exists; only its content changed.
        assert len(result.prompt.splitlines()) == len(snapshot.prompt.splitlines())
        assert result.perturbation_chars > 0

    def test_every_declared_factor_matches_a_real_prompt(self, run_dir, flood_masks):
        """A pattern that matches nothing produces a null result that
        looks exactly like a null finding. Pin all four."""
        snapshot = load_snapshots(run_dir)[0]
        for name in flood_masks.names:
            result = apply_mask(snapshot.prompt, flood_masks[name], ARM_MASKED)
            assert result.applied, f"{name}: {result.reason}"
            assert result.matches >= 1

    def test_history_factors_are_named_for_the_span_they_cover(self, flood_masks):
        """P1-e: the patterns match EVERY remembered year, so the names
        say history. A name implying "this year" over a mask that wipes
        the whole memory window is the kind of label a reader trusts."""
        assert set(flood_masks.names) == {
            "neighbor_adoption_history", "flood_experience_history",
            "grant_availability_history", "insurance_trust",
        }
        for name in ("neighbor_adoption_history", "flood_experience_history",
                     "grant_availability_history"):
            assert "remember" in flood_masks[name].description.lower()

    def test_paraphrase_control_keeps_the_information(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        result = apply_mask(snapshot.prompt,
                            flood_masks["neighbor_adoption_history"], ARM_CONTROL)
        assert result.applied
        assert "25%" in result.prompt and "0%" in result.prompt
        assert "I observe 25% of neighbors elevated" not in result.prompt

    def test_arms_perturb_comparable_amounts(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        for name in flood_masks.names:
            masked = apply_mask(snapshot.prompt, flood_masks[name], ARM_MASKED)
            control = apply_mask(snapshot.prompt, flood_masks[name], ARM_CONTROL)
            ratio = (min(masked.perturbation_chars, control.perturbation_chars)
                     / max(masked.perturbation_chars, control.perturbation_chars))
            assert ratio >= 0.5, (
                f"{name}: masked edits {masked.perturbation_chars} chars, control "
                f"edits {control.perturbation_chars}; not severity-matched."
            )

    def test_baseline_arm_returns_the_prompt_untouched(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        result = apply_mask(snapshot.prompt,
                            flood_masks["neighbor_adoption_history"], ARM_BASELINE)
        assert result.prompt == snapshot.prompt
        assert result.perturbation_chars == 0

    def test_absent_factor_is_reported_not_counted_as_a_null(self, flood_masks):
        result = apply_mask("A prompt about nothing in particular.",
                            flood_masks["neighbor_adoption_history"], ARM_MASKED)
        assert not result.applied
        assert not result.factor_present
        assert "absent" in result.reason

    def test_missing_control_is_reported_not_silently_skipped(self):
        spec = MaskSpec(provider="p", key="k", neutral="Nothing is known.",
                        paraphrase=None, pattern=r"anything")
        result = apply_mask("anything at all", spec, ARM_CONTROL)
        assert not result.applied
        assert "no severity-matched paraphrase" in result.reason

    def test_empty_neutral_rendering_is_refused(self):
        with pytest.raises(ValueError, match="neutral"):
            MaskSpec(provider="p", key="k", neutral="   ", pattern="x")

    def test_empty_paraphrase_is_refused(self):
        with pytest.raises(ValueError, match="paraphrase"):
            MaskSpec(provider="p", key="k", neutral="ok", paraphrase="", pattern="x")

    def test_bad_pattern_is_refused_at_declaration(self):
        with pytest.raises(ValueError, match="does not compile"):
            MaskSpec(provider="p", key="k", neutral="ok", pattern="([")

    def test_expected_sign_must_be_a_direction(self):
        with pytest.raises(ValueError, match="expected_sign"):
            MaskSpec(provider="p", key="k", neutral="ok", pattern="x", expected_sign=0)

    def test_expected_sign_defaults_to_minus_one_and_reaches_to_dict(self):
        spec = MaskSpec(provider="p", key="k", neutral="ok", pattern="x")
        assert spec.expected_sign == -1
        assert spec.to_dict()["expected_sign"] == -1

    def test_callable_rendering_returning_empty_is_reported_not_raised(self):
        """W7: a rendering that fails costs its own arm, not the grid.

        Before this the ValueError escaped ``re.subn`` and aborted the
        whole run, so one factor's stale vocabulary threw away every
        other factor's rows."""
        spec = MaskSpec(provider="p", key="k", neutral=lambda m: "", pattern="x")
        result = apply_mask("x", spec, ARM_MASKED)
        assert not result.applied
        assert "mask rendering failed" in result.reason
        assert "never deletes" in result.reason

    def test_a_paraphrase_that_raises_is_reported_not_raised(self):
        def _explode(matched: str) -> str:
            raise ValueError("vocabulary drifted")

        spec = MaskSpec(provider="p", key="k", neutral="Nothing is known.",
                        paraphrase=_explode, pattern="x")
        result = apply_mask("x", spec, ARM_CONTROL)
        assert not result.applied
        assert "vocabulary drifted" in result.reason

    def test_every_occurrence_is_masked(self, flood_masks):
        prompt = ("- Year 1: I observe 25% of neighbors elevated and 0% relocated.\n"
                  "- Year 2: I observe 50% of neighbors elevated and 0% relocated.\n")
        result = apply_mask(prompt, flood_masks["neighbor_adoption_history"], ARM_MASKED)
        assert result.matches == 2
        assert "I observe" not in result.prompt


# ─────────────────────────────────────────────────────────────────────
# 3. The determinism gate
# ─────────────────────────────────────────────────────────────────────

def _deterministic_invoke(prompt: str) -> str:
    return '{"decision": 1}'


def _dead_backend(prompt: str):
    """What ``create_llm_invoke`` returns when Ollama is not running.

    ``invoke`` exhausts its retries and returns ``("", stats)``; the
    parser returns ``None`` for empty text.
    """
    return "", None


class _Flipper:
    """A decider that answers the same question differently each time."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        return '{"decision": %d}' % (1 if self.calls % 2 else 2)


class TestDeterminismGate:
    def test_passes_on_a_deterministic_decider(self, run_dir):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        report = determinism_check(snapshot, _deterministic_invoke, n=5, decider=decider)
        assert report.verified
        assert report.k_identical == 5
        assert report.distinct_raw_outputs == 1
        assert report.n_empty_raw == 0
        assert report.n_unparsed == 0
        assert "deterministic:" in report.summary_line

    def test_fails_on_a_decider_that_disagrees_with_itself(self, run_dir):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        report = determinism_check(snapshot, _Flipper(), n=5, decider=decider)
        assert not report.verified
        assert report.k_identical < 5
        assert "No delta-P" in report.note

    def test_an_unreachable_backend_does_not_pass_by_being_consistent(self, run_dir):
        """P0-A: five identical empty replies is the most consistent
        backend imaginable and the least informative. Before this the
        gate saw k == n and passed, and every delta-P downstream was a
        difference between two absences."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        report = determinism_check(snapshot, _dead_backend, n=5, decider=decider)

        assert report.k_identical == 5          # they ARE identical
        assert report.verified is False         # and that is not enough
        assert report.n_empty_raw == 5
        assert report.n_unparsed == 5
        assert "identical but not a decision" in report.note
        assert "check the backend" in report.note
        assert "empty" in report.summary_line

    def test_an_unparsable_but_non_empty_backend_also_fails(self, run_dir):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        report = determinism_check(
            snapshot, lambda prompt: "I would rather not say.", n=4, decider=decider)
        assert report.k_identical == 4
        assert report.n_empty_raw == 0
        assert report.n_unparsed == 4
        assert report.verified is False

    def test_needs_at_least_two_replays(self, run_dir):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        with pytest.raises(ValueError):
            determinism_check(snapshot, _deterministic_invoke, n=1, decider=decider)

    def test_same_action_via_different_words_is_not_deterministic(self, run_dir):
        """Identity is required on the raw text too: landing in the same
        bucket twice is luck, not determinism."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        seen = {"n": 0}

        def _same_action_different_text(prompt: str) -> str:
            seen["n"] += 1
            return '{"decision": 1}' if seen["n"] % 2 else '{"decision": "1"}'

        report = determinism_check(snapshot, _same_action_different_text, n=4,
                                   decider=decider)
        assert report.distinct_skills == ["buy_insurance"]
        assert not report.verified


# ─────────────────────────────────────────────────────────────────────
# 4. Replay through the production path
# ─────────────────────────────────────────────────────────────────────

class TestReplayDecision:
    def test_parse_only_replay_reproduces_the_recorded_decision(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        result = replay_decision(
            snapshot, mask=None, control=None, seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks, decider=decider,
        )
        assert result.arm == ARM_BASELINE
        assert result.skill == "buy_insurance"
        assert result.decision_action == "buy_insurance"
        assert result.matches_trace is True
        assert result.governance_evaluated is False
        assert result.validator_verdict == "not_evaluated"
        assert result.fidelity == FIDELITY_PROMPT_ONLY

    def test_masked_replay_records_the_diff_and_the_match_count(
        self, run_dir, flood_masks,
    ):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        result = replay_decision(
            snapshot, mask={"neighbor_adoption_history"}, control=None, seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks, decider=decider,
        )
        assert result.arm == ARM_MASKED
        assert result.factor == "neighbor_adoption_history"
        assert result.factor_present
        assert result.n_matches == 1
        assert result.perturbation_chars > 0
        assert result.matches_trace is None  # only the baseline arm can match

    def test_n_matches_counts_every_span_the_mask_replaced(self, tmp_path, flood_masks):
        """P1-e: the row has to say how much of the prompt this mask took
        out. One bullet and five bullets are different interventions and
        were indistinguishable in the table."""
        run = _write_run_dir(tmp_path, n_agents=1, n_years=1)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        trace = json.loads(lines[1])
        trace["input"] = trace["input"].replace(
            "- Year 1:",
            "- Year 1: I observe 10% of neighbors elevated and 0% relocated.\n- Year 1:",
        )
        lines[1] = json.dumps(trace)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        snapshot = load_snapshots(run)[0]
        decider = build_replay_decider(run, model="mock")
        result = replay_decision(
            snapshot, mask={"neighbor_adoption_history"}, control=None, seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks, decider=decider,
        )
        assert result.n_matches == 2
        assert result.to_row()["n_matches"] == 2

    def test_the_prompt_diff_keeps_both_sides(self, run_dir, flood_masks):
        """W2: the removed text used to be able to eat the whole 400-char
        budget, leaving no evidence that anything was put in its place —
        which is the difference between a substitution and a deletion."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        result = replay_decision(
            snapshot, mask={"neighbor_adoption_history"}, control=None, seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks, decider=decider,
        )
        assert result.prompt_diff.startswith("removed: ")
        assert " => added: " in result.prompt_diff
        assert "I observe 25% of neighbors elevated" in result.prompt_diff
        assert "No information about neighbours" in result.prompt_diff

    def test_an_arm_whose_factor_is_absent_never_calls_the_decider(
        self, run_dir, flood_masks,
    ):
        """S1: that arm's prompt is byte-identical to the baseline this
        cell already holds, so the call buys a duplicate of a result the
        run has. The row is still written, marked as skipped."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        ghost = FactorMap({"ghost": MaskSpec(
            provider="p", key="k", pattern=r"a phrase that never appears",
            neutral="Nothing is known.", paraphrase="Nothing at all is known.",
        )})
        calls = {"n": 0}

        def _counting(prompt: str) -> str:
            calls["n"] += 1
            return '{"decision": 1}'

        result = replay_decision(
            snapshot, mask={"ghost"}, control=None, seed=42,
            llm_invoke=_counting, factor_map=ghost, decider=decider,
        )
        assert calls["n"] == 0
        assert result.decider_called is False
        assert result.factor_present is False
        assert result.validator_verdict == "not_run"
        assert "absent" in result.mask_reason
        assert result.to_row()["decider_called"] is False

    def test_an_arm_with_no_control_declared_also_skips_the_call(
        self, run_dir,
    ):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        no_control = FactorMap({"trust": MaskSpec(
            provider="p", key="k", pattern=r"insurance company",
            neutral="insurer", paraphrase=None,
        )})
        calls = {"n": 0}

        def _counting(prompt: str) -> str:
            calls["n"] += 1
            return '{"decision": 1}'

        result = replay_decision(
            snapshot, mask={"trust"}, control="paraphrase", seed=42,
            llm_invoke=_counting, factor_map=no_control, decider=decider,
        )
        assert calls["n"] == 0
        assert result.decider_called is False
        assert "no severity-matched paraphrase" in result.mask_reason

    def test_a_trace_that_recorded_nothing_is_not_a_match(self, tmp_path, flood_masks):
        """P1-c: ``None == None`` counted "the trace recorded no action"
        and "the replay reproduced the trace" as the same fact, so a
        corpus that recorded nothing reported perfect reproduction."""
        run = _write_run_dir(tmp_path, n_agents=1, n_years=1)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        trace = json.loads(lines[1])
        trace["skill_proposal"] = {}
        trace["approved_skill"] = {}
        lines[1] = json.dumps(trace)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        snapshot = load_snapshots(run)[0]
        assert snapshot.reference_action() is None
        decider = build_replay_decider(run, model="mock")
        result = replay_decision(
            snapshot, mask=None, control=None, seed=42,
            llm_invoke=lambda prompt: "no decision here",
            factor_map=flood_masks, decider=decider,
        )
        assert result.skill is None
        assert result.recorded_skill is None
        assert result.matches_trace is None

    def test_control_arm_selects_the_paraphrase(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        result = replay_decision(
            snapshot, mask={"neighbor_adoption_history"}, control="paraphrase", seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks, decider=decider,
        )
        assert result.arm == ARM_CONTROL
        assert "Neighbour uptake" in result.prompt_diff

    def test_unknown_factor_raises(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        with pytest.raises(KeyError):
            replay_decision(snapshot, mask={"not_a_factor"}, control=None, seed=1,
                            llm_invoke=_deterministic_invoke,
                            factor_map=flood_masks, decider=decider)

    def test_unknown_control_raises(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        with pytest.raises(ValueError, match="control"):
            replay_decision(snapshot, mask={"neighbor_adoption_history"}, control="shuffle",
                            seed=1, llm_invoke=_deterministic_invoke,
                            factor_map=flood_masks, decider=decider)

    def test_executed_stage_without_governance_refuses(self, run_dir, flood_masks):
        """P1-b: parse-only replay never runs a validator, so there is no
        executed action; anchoring on one would compare the recorded
        executed skill against a column of '__unparsed__'."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        with pytest.raises(ValueError, match="needs a governance decider"):
            replay_decision(snapshot, mask=None, control=None, seed=1,
                            llm_invoke=_deterministic_invoke,
                            factor_map=flood_masks, decider=decider,
                            action_stage="executed")


class TestGovernanceReplayRefusals:
    def test_without_a_validators_module_it_refuses(self, run_dir):
        """P0-B: a run directory does not record the custom validators
        the experiment wired in. Rebuilding the engine without them runs
        governance with ZERO domain validators while every row still says
        governance_evaluated=true."""
        with pytest.raises(ValueError, match="--validators-module"):
            build_replay_decider(run_dir, model="mock", with_governance=True)

    def test_the_refusal_names_what_is_missing(self, run_dir):
        with pytest.raises(ValueError) as excinfo:
            build_replay_decider(run_dir, model="mock", with_governance=True)
        message = str(excinfo.value)
        assert "with_custom_validators" in message
        assert "build_custom_validators(config) -> list" in message

    def test_a_module_without_the_contract_function_is_refused(
        self, run_dir, request,
    ):
        name = "_pr5_empty_validators"
        sys.modules[name] = types.ModuleType(name)
        request.addfinalizer(lambda: sys.modules.pop(name, None))
        with pytest.raises(AttributeError, match="build_custom_validators"):
            build_replay_decider(run_dir, model="mock", with_governance=True,
                                 validators_module=name)

    def test_with_a_validators_module_the_engine_carries_them(
        self, run_dir, validators_module,
    ):
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True,
            validators_module=validators_module)
        assert decider.governance_evaluated
        assert decider.engine.custom_validators == []
        assert validators_module in decider.validators_source
        assert decider.financial_constraints is False
        # Replay still writes nothing and executes nothing.
        assert decider.engine.audit_writer is None
        assert decider.engine.simulation_engine is None

    def test_replaying_refuses_because_the_trace_has_no_option_set(
        self, run_dir, flood_masks, validators_module,
    ):
        """P1-a: without ``available_skills`` the engine offers the
        domain's full action list, re-offering elevation to a household
        that already elevated — the R5 term IBR excludes on purpose."""
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True,
            validators_module=validators_module)
        with pytest.raises(ValueError, match="available_skills"):
            replay_decision(snapshot, mask=None, control=None, seed=42,
                            llm_invoke=_deterministic_invoke,
                            factor_map=flood_masks, decider=decider)

    def test_passing_a_snapshot_moves_the_refusal_earlier(
        self, run_dir, validators_module,
    ):
        """Residual (code-reviewer): with a loaded snapshot in hand — the
        CLI always has one before it builds the decider — the missing
        ``available_skills`` refusal fires inside build_replay_decider
        itself, before the adapter and the registry load, rather than
        only surfacing on the first replay_decision call."""
        snapshot = load_snapshots(run_dir)[0]
        with pytest.raises(ValueError, match="available_skills"):
            build_replay_decider(
                run_dir, model="mock", with_governance=True,
                validators_module=validators_module, snapshot=snapshot)

    def test_without_a_snapshot_the_early_check_is_skipped(
        self, run_dir, validators_module,
    ):
        """The default (and every caller that predates this parameter)
        builds successfully; the identical refusal still waits at the
        first replay_decision call (see the late-check test above)."""
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True,
            validators_module=validators_module)
        assert decider.governance_evaluated

    def test_governance_without_a_registry_refuses(
        self, tmp_path, run_dir, validators_module,
    ):
        """A verdict from a guessed registry is worse than no verdict."""
        lonely_config = tmp_path / "lonely" / "agent_types.yaml"
        lonely_config.parent.mkdir()
        lonely_config.write_text(FLOOD_CONFIG.read_text(encoding="utf-8"),
                                 encoding="utf-8")
        with pytest.raises(FileNotFoundError, match="skill_registry.yaml"):
            build_replay_decider(run_dir, model="mock", agent_config=lonely_config,
                                 with_governance=True,
                                 validators_module=validators_module)

    def test_the_run_directory_is_untouched(self, run_dir, validators_module):
        before = sorted(p.name for p in (run_dir / "raw").iterdir())
        build_replay_decider(run_dir, model="mock", with_governance=True,
                             validators_module=validators_module)
        assert sorted(p.name for p in (run_dir / "raw").iterdir()) == before


class TestGovernanceReplayExecutesOnce:
    """Item 7 (code-reviewer): every other governance test above pins a
    REFUSAL — the branch that never reaches SkillBrokerEngine.process_step
    at all. Nothing in this file drove the engine path to a verdict, so a
    break in ``_decide_with_engine`` (or in the wiring between
    ``build_replay_decider(with_governance=True)`` and it) could pass
    every other test here and still be dead code. This test supplies the
    one thing a real run has and a synthetic trace does not —
    ``context["available_skills"]`` — at the fixture level, so the engine
    runs end to end on the mock decider against the throwaway
    ``build_custom_validators`` module ``validators_module`` already
    builds (returning ``[]``), and checks a verdict comes back."""

    def test_available_skills_lets_governance_run(
        self, run_dir, flood_masks, validators_module,
    ):
        snapshot = load_snapshots(run_dir)[0]
        snapshot.context["available_skills"] = [
            "buy_insurance", "elevate_house", "relocate", "do_nothing",
        ]
        decider = build_replay_decider(
            run_dir, model="mock", with_governance=True,
            validators_module=validators_module)

        result = replay_decision(
            snapshot, mask=None, control=None, seed=42,
            llm_invoke=_deterministic_invoke, factor_map=flood_masks,
            decider=decider)

        assert result.decider_called is True
        assert result.governance_evaluated is True
        assert result.validator_verdict not in (None, "not_evaluated", "not_run")
        # _deterministic_invoke always answers option 1 ("Buy flood
        # insurance" in PROMPT_TEMPLATE), so the proposal this produces
        # is pinned rather than merely "something came back".
        assert result.skill == "buy_insurance"


class TestSeedBinding:
    def test_a_decider_without_a_seed_parameter_says_so(self):
        bound, applied = bind_seed(_deterministic_invoke, 42)
        assert bound is _deterministic_invoke
        assert applied is False

    def test_a_kwargs_catch_all_does_not_count_as_accepting_a_seed(self):
        """W5: a ``**kwargs`` wrapper may forward the seed to something
        that ignores it, and a decorated ``(*args, **kwargs)`` callable
        says nothing about what it wraps. ``seeds_applied_to_decider`` is
        the column a reader uses to decide whether the seeds mean
        anything, so it stays False unless the seed provably lands."""
        def _wrapper(prompt: str, **kwargs):
            return '{"decision": 1}'

        bound, applied = bind_seed(_wrapper, 42)
        assert applied is False
        assert bound is _wrapper

    def test_a_decider_with_a_seed_parameter_receives_it(self):
        seen = {}

        def _seeded(prompt: str, seed: int = 0) -> str:
            seen["seed"] = seed
            return '{"decision": 1}'

        bound, applied = bind_seed(_seeded, 7)
        assert applied is True
        bound("prompt")
        assert seen["seed"] == 7

    def test_replay_row_records_whether_the_seed_landed(self, run_dir, flood_masks):
        snapshot = load_snapshots(run_dir)[0]
        decider = build_replay_decider(run_dir, model="mock")
        result = replay_decision(snapshot, mask=None, control=None, seed=42,
                                 llm_invoke=_deterministic_invoke,
                                 factor_map=flood_masks, decider=decider)
        assert result.seed == 42
        assert result.seed_applied is False

    def test_the_production_backends_take_no_seed(self):
        """The guide says every backend create_llm_invoke returns today
        has the signature invoke(prompt). Pin it, so the claim fails here
        rather than in a paper."""
        from broker.utils.llm_utils import create_llm_invoke
        from broker.experiments.replay import _accepts_seed
        assert _accepts_seed(create_llm_invoke("mock")) is False


# ─────────────────────────────────────────────────────────────────────
# 5. The DomainPack hook
# ─────────────────────────────────────────────────────────────────────

class TestContextMaskDefaultsHook:
    def test_default_pack_returns_empty(self):
        from broker.domains.default import DefaultDomainPack
        assert DefaultDomainPack().context_mask_defaults() == {}

    def test_shipped_packs_declare_nothing_by_default(self):
        """The hook is additive: no frozen pack gained a factor, so no
        existing run or test changes behaviour."""
        import examples.governed_flood  # noqa: F401 - registration side-effect
        import examples.irrigation_abm  # noqa: F401 - registration side-effect
        from broker.domains.registry import DomainPackRegistry

        for domain in ("flood", "irrigation"):
            pack = DomainPackRegistry.get_or_default(domain)
            assert pack.context_mask_defaults() == {}

    def test_default_pack_still_satisfies_the_protocol(self):
        from broker.domains.default import DefaultDomainPack
        from broker.domains.protocol import DomainPack
        assert isinstance(DefaultDomainPack(), DomainPack)

    def test_flood_pack_still_satisfies_the_protocol(self):
        import examples.governed_flood  # noqa: F401
        from broker.domains.protocol import DomainPack
        from broker.domains.registry import DomainPackRegistry
        assert isinstance(DomainPackRegistry.get("flood"), DomainPack)

    def test_a_registered_domain_reads_its_hook(self):
        import examples.governed_flood  # noqa: F401
        assert FactorMap.from_domain("flood").names == []

    def test_an_unregistered_domain_is_an_error_not_an_empty_map(self):
        """S2: ``get_or_default`` answers with DefaultDomainPack for any
        name it does not know, so a typo came back as "this domain
        declares no factors" — a sentence about the domain, not about
        the spelling."""
        with pytest.raises(KeyError, match="not registered"):
            FactorMap.from_domain("no_such_domain")

    def test_masked_flood_pack_registers_under_a_second_name(self):
        from examples.single_agent import flood_factor_masks
        from broker.domains.registry import DomainPackRegistry

        name = flood_factor_masks.register("flood_masked_test")
        pack = DomainPackRegistry.get(name)
        assert set(pack.context_mask_defaults()) == {
            "neighbor_adoption_history", "flood_experience_history",
            "grant_availability_history", "insurance_trust",
        }
        # The production pack is untouched.
        assert DomainPackRegistry.get("flood").context_mask_defaults() == {}

    def test_registering_the_masked_pack_as_flood_is_refused(self):
        from examples.single_agent import flood_factor_masks
        with pytest.raises(ValueError, match="Refusing"):
            flood_factor_masks.register("flood")


# ─────────────────────────────────────────────────────────────────────
# 6. Optional: the real PR-3 baseline run
# ─────────────────────────────────────────────────────────────────────

BASELINE_ENV = "WAGF_PR5_BASELINE_RUN"


@pytest.mark.skipif(
    not os.environ.get(BASELINE_ENV),
    reason=f"set {BASELINE_ENV} to a finished flood run directory to enable",
)
class TestAgainstRecordedBaselineRun:
    def test_loads_and_masks_a_real_run(self):
        from examples.single_agent.flood_factor_masks import FLOOD_FACTOR_MASKS

        run = Path(os.environ[BASELINE_ENV])
        snapshots = load_snapshots(run)
        assert snapshots
        assert all(s.fidelity == FIDELITY_PROMPT_ONLY for s in snapshots)

        factor_map = FactorMap(FLOOD_FACTOR_MASKS)
        applied = {
            name: sum(
                1 for s in snapshots
                if apply_mask(s.prompt, factor_map[name], ARM_MASKED).applied
            )
            for name in factor_map.names
        }
        assert applied["neighbor_adoption_history"] == len(snapshots)
        assert applied["insurance_trust"] == len(snapshots)
