"""PR-5 — the ablation grid, the withholding rule, and the CLI.

The tests that matter most here are the two falsification pairs:

* A decider that genuinely uses the factor must show a delta-P against
  the baseline AND beat the severity-matched paraphrase control. If the
  tool cannot detect a factor it was built to detect, nothing else it
  reports is worth reading.
* A decider that is merely sensitive to being edited must show the SAME
  movement in both arms, so ``effect_vs_control`` collapses to zero.
  This is the control earning its place: without it, the first decider
  and the second look identical.

Everything else pins the honesty rails — every effect quantity withheld
on a non-deterministic backend, a p-value withheld when too few pairs
moved to produce one, the fidelity regime stamped on every row, a
missing control reported rather than ignored, and every refusal
refusing.
"""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import types
from pathlib import Path

import pytest

from _pr5_run_fixture import write_run_dir
from broker.experiments.ablation import AblationDesign, run_ablation
from broker.experiments.replay import (
    ARM_BASELINE,
    ARM_CONTROL,
    ARM_MASKED,
    FactorMap,
    MaskSpec,
    build_replay_decider,
    load_snapshots,
)
from broker.experiments import metrics as _metrics

MASKS = "examples.single_agent.flood_factor_masks:FLOOD_FACTOR_MASKS"

# The neighbour cue as INFORMATION, not as a literal string: the
# paraphrase changes the wording but keeps "N% elevated", so a decider
# keyed on this pattern sees the factor in both the baseline and the
# control arms and loses it only under the mask.
_NEIGHBOUR_INFO = re.compile(r"\d+%\s+(?:of neighbors\s+)?elevated")


def _insensitive(prompt: str) -> str:
    """Always the same answer. The built-in mock behaves like this."""
    return '{"decision": 1}'


def _uses_the_factor(prompt: str) -> str:
    """Elevates when it can see neighbours elevating; insures otherwise."""
    return ('{"decision": 2}' if _NEIGHBOUR_INFO.search(prompt)
            else '{"decision": 1}')


def _sensitive_to_any_edit(prompt: str) -> str:
    """Flips whenever the neighbour SENTENCE is not the one it memorised.

    A perfectly reasonable-looking decider that is in fact reacting to
    the edit, not to the factor: the paraphrase disturbs it exactly as
    much as the mask does.
    """
    return ('{"decision": 1}'
            if "I observe 25% of neighbors elevated and 0% relocated." in prompt
            else '{"decision": 2}')


def _dead_backend(prompt: str) -> str:
    """What a stopped Ollama server produces: an empty reply, every time."""
    return ""


class _NonDeterministic:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, prompt: str) -> str:
        self.calls += 1
        return '{"decision": %d}' % (1 if self.calls % 2 else 4)


@pytest.fixture()
def run_dir(tmp_path: Path) -> Path:
    return write_run_dir(tmp_path, n_agents=3, n_years=2)


@pytest.fixture()
def flood_masks() -> FactorMap:
    from examples.single_agent.flood_factor_masks import FLOOD_FACTOR_MASKS
    return FactorMap(FLOOD_FACTOR_MASKS)


@pytest.fixture()
def pieces(run_dir, flood_masks):
    return load_snapshots(run_dir), build_replay_decider(run_dir, model="mock"), flood_masks


@pytest.fixture()
def elevating_pieces(tmp_path, flood_masks):
    """A run whose traces record ``elevate_house`` — the action the
    factor-using decider below returns at baseline. delta-P is anchored
    on the recorded action, so a fixture that recorded something else
    would be exercising the anchor-mismatch path instead."""
    run = write_run_dir(tmp_path / "elevating", n_agents=3, n_years=2,
                        recorded_skill="elevate_house")
    return load_snapshots(run), build_replay_decider(run, model="mock"), flood_masks


@pytest.fixture()
def validators_module(request) -> str:
    name = "_pr5_cli_validators"
    module = types.ModuleType(name)
    module.build_custom_validators = lambda config: []
    sys.modules[name] = module
    request.addfinalizer(lambda: sys.modules.pop(name, None))
    return name


def _design(**kwargs) -> AblationDesign:
    base = dict(factors=["neighbor_adoption_history"], seeds=(42, 43),
                n_replicates=1, determinism_n=2)
    base.update(kwargs)
    return AblationDesign(**base)


# ─────────────────────────────────────────────────────────────────────
# Falsification: can it find a factor that IS used?
# ─────────────────────────────────────────────────────────────────────

class TestDetectsACausalFactor:
    def test_masking_a_used_factor_moves_the_action(self, elevating_pieces):
        snapshots, decider, masks = elevating_pieces
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        # Baseline elevates; masked cannot see the neighbours and insures.
        assert block["delta_p_masked_mean"] == pytest.approx(-1.0)
        assert block["jsd_masked_mean"] == pytest.approx(1.0)
        assert block["directional_consistency"]["consistency"] == pytest.approx(1.0)
        assert block["directional_consistency"]["expected_sign"] == -1

    def test_the_control_arm_does_not_move(self, elevating_pieces):
        snapshots, decider, masks = elevating_pieces
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        assert block["delta_p_control_mean"] == pytest.approx(0.0)
        assert block["effect_vs_control"] == pytest.approx(-1.0)
        assert "difference of -1.000" in block["verdict"]

    def test_the_verdict_carries_its_sample_size(self, elevating_pieces):
        """P1-d: an effect and a p-value read the same at n=6 as at
        n=600 unless the sentence says which it was."""
        snapshots, decider, masks = elevating_pieces
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=masks)
        verdict = result.summary["factors"]["neighbor_adoption_history"]["verdict"]
        assert f"Based on {len(snapshots)} snapshot(s) carrying the factor" in verdict
        assert f"{len(snapshots)} of which moved" in verdict

    def test_a_p_value_from_too_few_moving_pairs_is_withheld(self, elevating_pieces):
        """P1-d: with 6 non-zero pairs the two-sided exact test cannot
        return anything below 2**-5 = 0.031, so "p = 0.031" is the
        smallest number the design can produce, not a measurement."""
        snapshots, decider, masks = elevating_pieces
        assert len(snapshots) < _metrics.MIN_PAIRS
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        message = block["p_value_withheld"]
        assert message.startswith(
            f"p withheld: n_nonzero={len(snapshots)} below minimum "
            f"{_metrics.MIN_PAIRS}")
        assert "attainable floor" in message
        assert message in block["verdict"]
        assert "p=" not in block["verdict"]

        test = block["wilcoxon_masked_vs_control"]
        assert test["p_value"] is None          # not the field to quote
        assert test["p_value_below_minimum"] is not None   # still auditable
        assert test["n_nonzero"] == len(snapshots)

    def test_enough_moving_pairs_report_a_p_value(self, tmp_path, flood_masks):
        run = write_run_dir(tmp_path / "many", n_agents=5, n_years=2,
                            recorded_skill="elevate_house")
        snapshots = load_snapshots(run)
        assert len(snapshots) >= _metrics.MIN_PAIRS
        decider = build_replay_decider(run, model="mock")
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=flood_masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["p_value_withheld"] is None
        assert block["wilcoxon_masked_vs_control"]["p_value"] is not None
        assert "p=" in block["verdict"]

    def test_per_snapshot_delta_p_is_exposed(self, elevating_pieces):
        snapshots, decider, masks = elevating_pieces
        result = run_ablation(snapshots, _design(), _uses_the_factor,
                              decider=decider, factor_map=masks)
        assert result.delta_p is not None
        assert set(result.delta_p["neighbor_adoption_history"]) == {
            s.snapshot_id for s in snapshots}
        assert all(v == pytest.approx(-1.0)
                   for v in result.delta_p["neighbor_adoption_history"].values())


class TestSeparatesAFactorFromAnyEdit:
    def test_an_edit_sensitive_decider_moves_in_both_arms(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _sensitive_to_any_edit,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        assert block["delta_p_masked_mean"] == pytest.approx(-1.0)
        assert block["delta_p_control_mean"] == pytest.approx(-1.0)

    def test_effect_vs_control_collapses_to_zero(self, pieces):
        """The whole point of the control arm: without it, this decider
        is indistinguishable from one that uses the factor."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _sensitive_to_any_edit,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        assert block["effect_vs_control"] == pytest.approx(0.0)
        assert "no evidence" in block["verdict"]

    def test_an_insensitive_decider_moves_in_neither_arm(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["delta_p_masked_mean"] == pytest.approx(0.0)
        assert block["effect_vs_control"] == pytest.approx(0.0)

    def test_a_stack_of_zeros_says_it_may_be_the_decider(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        sensitivity = result.summary["decider_prompt_sensitivity"]
        assert sensitivity["n_changed"] == 0
        assert "first numbered option" in sensitivity["note"]


# ─────────────────────────────────────────────────────────────────────
# The withholding rule
# ─────────────────────────────────────────────────────────────────────

class TestDeltaPWithheldOnNonDeterministicBackends:
    def test_delta_p_is_none(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=4),
                              _NonDeterministic(), decider=decider, factor_map=masks)
        assert result.delta_p is None
        assert result.determinism_verified is False

    def test_the_summary_says_k_of_n(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=4),
                              _NonDeterministic(), decider=decider, factor_map=masks)
        message = result.summary["delta_p_withheld"]
        assert message.startswith("ΔP withheld: backend non-deterministic")
        assert "identical" in message

    def test_every_effect_quantity_is_nulled_not_just_delta_p(self, pieces):
        """C1: JSD, KL and directional consistency come from the same
        replays as delta-P. Leaving them populated in a withheld block
        left three numbers a reader could quote out of a table whose
        headline had just been refused."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=4),
                              _NonDeterministic(), decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        for key in ("delta_p_masked_mean", "delta_p_control_mean",
                    "effect_vs_control", "wilcoxon_baseline_vs_masked",
                    "wilcoxon_baseline_vs_control", "wilcoxon_masked_vs_control",
                    "jsd_masked_mean", "jsd_control_mean",
                    "kl_masked_mean", "kl_control_mean",
                    "directional_consistency"):
            assert block[key] is None, f"{key} survived the withholding"
        assert block["withheld"] is True
        assert "withheld" in block["verdict"]

    def test_the_counts_that_explain_the_withholding_survive(self, pieces):
        """Nulling the effects must not null the diagnosis. The reader
        still needs to know how many snapshots carried the factor."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=4),
                              _NonDeterministic(), decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["n_snapshots_with_factor"] == len(snapshots)
        assert block["severity"]["n_pairs"] == len(snapshots)

    def test_the_raw_samples_are_still_written(self, pieces):
        """The replays happened; they are data. Only the inference is
        withheld, and each row carries the verdict that withheld it."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=4),
                              _NonDeterministic(), decider=decider, factor_map=masks)
        assert result.samples
        assert all(row["determinism_verified"] is False for row in result.samples)

    def test_a_replicate_disagreement_also_withholds(self, pieces):
        """Determinism can pass the gate and break later. A cell whose
        replicates disagree fails the run, not just that cell."""
        snapshots, decider, masks = pieces
        calls = {"n": 0}
        gated = min(len(snapshots), 5)

        def _stable_then_not(prompt: str) -> str:
            calls["n"] += 1
            # The gate (2 calls on each of the gated snapshots) is
            # stable; the grid that follows is not.
            if calls["n"] <= 2 * gated:
                return '{"decision": 1}'
            return '{"decision": %d}' % (1 if calls["n"] % 2 else 4)

        result = run_ablation(snapshots, _design(n_replicates=2, determinism_n=2),
                              _stable_then_not, decider=decider, factor_map=masks)
        assert result.determinism_verified is False
        assert result.determinism["runtime_replicate_stable"] is False
        assert "disagreed across replicates" in result.summary["delta_p_withheld"]


class TestAnUnreachableBackendIsNotADeterministicOne:
    def test_the_gate_fails_on_identical_empty_replies(self, pieces):
        """P0-A: the gate passed vacuously when every reply was the same
        empty string, and the ablation then reported a full grid of
        exact zeros as though the factors did nothing."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=3),
                              _dead_backend, decider=decider, factor_map=masks)

        assert result.determinism["k_identical"] == result.determinism["n"]
        assert result.determinism_verified is False
        assert result.determinism["n_empty_raw"] == result.determinism["n"]
        assert result.determinism["n_unparsed"] == result.determinism["n"]
        assert "identical but not a decision" in result.summary["delta_p_withheld"]
        assert "check the backend" in result.summary["delta_p_withheld"]

    def test_the_summary_counts_the_empty_and_unparsed_replies(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=3),
                              _dead_backend, decider=decider, factor_map=masks)
        quality = result.summary["decision_quality"]
        assert quality["n_decider_calls"] > 0
        assert quality["n_empty_outputs"] == quality["n_decider_calls"]
        assert quality["n_unparsed"] == quality["n_decider_calls"]
        assert quality["n_errors"] == quality["n_decider_calls"]
        assert "without a usable action" in quality["note"]

    def test_a_factor_whose_baselines_returned_nothing_gets_no_verdict(
        self, pieces,
    ):
        """P0-A: even if the gate somehow passed, a factor measured
        against baselines that produced no decision has no difference to
        report — only two absences."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(determinism_n=3),
                              _dead_backend, decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["withheld"] is True
        assert block["n_baseline_replays_without_a_decision"] > 0
        assert "returned no decision" in block["verdict"]


def _empty_for_masked_neighbor_arm(prompt: str) -> str:
    """Item 1 (hunter): no decision ONLY for neighbor_adoption_history's
    MASKED arm. Baseline and control both answer normally, so the
    determinism gate — which replays only the unmasked baseline prompt —
    still passes and ``n_baseline_replays_without_a_decision`` stays
    zero. Before the fix this let a masked arm's
    ``ReplayResult.produced_no_decision`` through unnoticed: the masked
    distribution is 100% ``__unparsed__``, the baseline distribution is
    100% the recorded action, so delta-P saturates at exactly -1.000 and
    the factor block reports it with ``withheld: false`` — indistinguish-
    able from a real, maximal effect."""
    if "No information about neighbours is available." in prompt:
        return ""
    return '{"decision": 1}'


class TestArmNoDecisionAlsoWithholds:
    """P1 (hunter): the withholding guard used to read only baseline
    rows. A masked or control arm that came back with no decision is
    counted here too."""

    def test_a_masked_only_no_decision_arm_is_withheld(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(),
                              _empty_for_masked_neighbor_arm,
                              decider=decider, factor_map=masks)
        # The gate only ever sees the unmasked prompt, so it still
        # passes — this is not the non-deterministic-backend path.
        assert result.determinism_verified is True
        block = result.summary["factors"]["neighbor_adoption_history"]

        assert block["withheld"] is True
        assert block["delta_p_masked_mean"] is None
        assert block["n_baseline_replays_without_a_decision"] == 0
        assert block["n_arm_replays_without_a_decision"] > 0
        assert "returned no decision" in block["verdict"]
        assert "masked/control" in block["verdict"]

    def test_falsifies_against_the_pre_fix_reading(self, pieces):
        """The guard this replaces read only baseline rows. Reproducing
        that narrower check against the same replay data must show
        exactly the failure the review reported: withheld=False and a
        delta-P saturated at -1.000, not merely "some other number"."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(),
                              _empty_for_masked_neighbor_arm,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]

        n_baseline_no_decision = block["n_baseline_replays_without_a_decision"]
        pre_fix_withheld = bool(n_baseline_no_decision)
        assert pre_fix_withheld is False, (
            "the baseline-only reading would not have withheld this block"
        )
        # delta_p_masked_mean is nulled by the (correct) post-fix
        # withholding; recompute the raw masked-vs-baseline probability
        # gap the pre-fix code would have reported instead, from the raw
        # samples every row still carries.
        masked_labels = {
            row["skill"] for row in result.samples
            if row["factor"] == "neighbor_adoption_history"
            and row["arm"] == "masked"
        }
        baseline_labels = {
            row["skill"] for row in result.samples
            if row["arm"] == "baseline"
        }
        assert masked_labels == {None}          # every masked reply parsed nothing
        assert baseline_labels == {"buy_insurance"}   # every baseline reply parsed
        # P(masked, recorded_action) - P(baseline, recorded_action) = 0 - 1 = -1.000,
        # exactly the saturated, indistinguishable-from-real-effect number
        # the review reported.


# ─────────────────────────────────────────────────────────────────────
# Shape of the run
# ─────────────────────────────────────────────────────────────────────

class TestGridShapeAndProvenance:
    def test_sample_count_is_the_declared_grid(self, pieces):
        snapshots, decider, masks = pieces
        design = _design(factors=["neighbor_adoption_history",
                                  "grant_availability_history"],
                         seeds=(42, 43), n_replicates=2)
        result = run_ablation(snapshots, design, _insensitive,
                              decider=decider, factor_map=masks)
        # per snapshot x seed x replicate: 1 baseline + 2 factors x 2 arms
        expected = len(snapshots) * 2 * 2 * (1 + 2 * 2)
        assert len(result.samples) == expected

    def test_the_baseline_is_shared_across_factors(self, pieces):
        """Running it once per factor would triple the cost and change
        nothing — the baseline prompt does not depend on the factor."""
        snapshots, decider, masks = pieces
        design = _design(factors=["neighbor_adoption_history",
                                  "grant_availability_history"])
        result = run_ablation(snapshots, design, _insensitive,
                              decider=decider, factor_map=masks)
        baselines = [r for r in result.samples if r["arm"] == ARM_BASELINE]
        assert len(baselines) == len(snapshots) * 2   # snapshots x seeds
        assert {r["factor"] for r in baselines} == {""}

    def test_every_row_carries_the_fidelity_regime(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        assert {row["fidelity"] for row in result.samples} == {"prompt_only"}
        assert result.summary["fidelity_regimes"] == {"prompt_only": len(snapshots)}

    def test_every_row_carries_its_match_count(self, pieces):
        """P1-e: one masked bullet and five masked bullets are different
        interventions, and the table has to be able to tell them apart."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        masked = [r for r in result.samples if r["arm"] == ARM_MASKED]
        assert masked
        assert all(r["n_matches"] >= 1 for r in masked)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["matches_mean"] == pytest.approx(1.0)
        assert block["matches_max"] == 1

    def test_all_three_arms_are_present(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        assert {row["arm"] for row in result.samples} == {
            ARM_BASELINE, ARM_MASKED, ARM_CONTROL}

    def test_dropping_the_control_is_reported_in_the_verdict(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(controls=()), _uses_the_factor,
                              decider=decider, factor_map=masks)
        block = result.summary["factors"]["neighbor_adoption_history"]
        assert block["control_arm_present"] is False
        assert "cannot be separated from a generic sensitivity" in block["verdict"]

    def test_provenance_reaches_the_summary(self, pieces):
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        assert result.summary["git_commit"].startswith("deadbeefcafe")
        assert result.summary["model"] == "mock"
        assert result.summary["model_used"] == "mock"
        assert "cli" in result.summary["model_source"]
        assert result.summary["validators_source"].startswith("none (parse-only")
        assert result.summary["baseline_reproduces_trace"]["rate"] == pytest.approx(1.0)
        assert result.summary["baseline_reproduces_trace"]["n_recorded_missing"] == 0

    def test_a_corpus_that_recorded_nothing_reports_no_reproduction_rate(
        self, tmp_path, flood_masks,
    ):
        """P1-c: comparing None to None as equality made a run where
        nothing was recorded report a perfect 1.0."""
        run = write_run_dir(tmp_path / "blank", n_agents=2, n_years=1)
        path = run / "raw" / "household_traces.jsonl"
        lines = path.read_text(encoding="utf-8").strip().split("\n")
        for index in range(1, len(lines)):
            trace = json.loads(lines[index])
            trace["skill_proposal"] = {}
            trace["approved_skill"] = {}
            lines[index] = json.dumps(trace)
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

        snapshots = load_snapshots(run)
        decider = build_replay_decider(run, model="mock")
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=flood_masks)
        block = result.summary["baseline_reproduces_trace"]
        assert block["rate"] is None
        assert block["n"] == 0
        assert block["n_recorded_missing"] == len(snapshots) * 2
        assert "not perfect" in block["note"]

    def test_the_seed_caveat_is_stated(self, pieces):
        """The mock decider takes no seed. Saying "seeds 42,43" without
        that caveat would describe pairing that never happened."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        assert result.summary["seeds_applied_to_decider"] is False
        assert "labels, not draws" in result.summary["seeds_note"]

    def test_an_undeclared_factor_is_refused(self, pieces):
        snapshots, decider, masks = pieces
        with pytest.raises(KeyError):
            run_ablation(snapshots, _design(factors=["nonsense"]), _insensitive,
                         decider=decider, factor_map=masks)

    def test_a_design_needs_a_factor(self):
        with pytest.raises(ValueError):
            AblationDesign(factors=[])

    def test_an_unknown_control_is_refused(self):
        with pytest.raises(ValueError, match="control"):
            AblationDesign(factors=["x"], controls=("shuffle",))

    def test_the_gate_samples_rather_than_gating_everything(self, pieces):
        """S1: the gate asks about the backend, not about one prompt.
        Gating all 3,276 snapshots of a real corpus costs more than the
        grid it guards."""
        snapshots, decider, masks = pieces
        assert len(snapshots) > 2
        result = run_ablation(snapshots, _design(determinism_snapshots=2),
                              _insensitive, decider=decider, factor_map=masks)
        assert result.determinism["gate_snapshots"] == 2
        assert result.determinism["n"] == 2 * 2   # 2 snapshots x determinism_n

    def test_zero_gate_snapshots_is_refused(self):
        with pytest.raises(ValueError, match="determinism_snapshots"):
            AblationDesign(factors=["x"], determinism_snapshots=0)

    def test_executed_stage_needs_governance(self, pieces):
        snapshots, decider, masks = pieces
        with pytest.raises(ValueError, match="governance decider"):
            run_ablation(snapshots, _design(action_stage="executed"), _insensitive,
                         decider=decider, factor_map=masks)


# ─────────────────────────────────────────────────────────────────────
# P2 (hunter): "declares no control" vs "its control failed to render"
# ─────────────────────────────────────────────────────────────────────

def _insurance_status_masks(paraphrase) -> FactorMap:
    """A one-factor map targeting a literal sentence every fixture
    prompt carries, so these tests do not depend on the shipped flood
    masks or their "Year N: " anchor at all."""
    return FactorMap({
        "insurance_status": MaskSpec(
            provider="p", key="k",
            pattern=r"You currently do not have flood insurance\.",
            neutral="No information about insurance status is available.",
            paraphrase=paraphrase,
        ),
    })


def _raises_vocabulary_drifted(matched: str) -> str:
    raise ValueError("insurance_status paraphrase vocabulary drifted")


class TestControlNotDeclaredVsRenderingFailed:
    def test_no_paraphrase_declared_is_counted_as_not_declared(self, run_dir):
        """Branch A: MaskSpec.paraphrase=None. has_control is False for
        every snapshot by construction, so every occurrence lands under
        n_snapshots_control_not_declared, never
        n_snapshots_control_rendering_failed."""
        snapshots = load_snapshots(run_dir)
        decider = build_replay_decider(run_dir, model="mock")
        masks = _insurance_status_masks(paraphrase=None)
        result = run_ablation(
            snapshots, _design(factors=["insurance_status"]), _insensitive,
            decider=decider, factor_map=masks)
        block = result.summary["factors"]["insurance_status"]

        assert block["control_arm_present"] is False
        assert block["n_snapshots_control_not_declared"] > 0
        assert block["n_snapshots_control_rendering_failed"] == 0
        assert "declares no severity-matched paraphrase control" in block["verdict"]
        assert "failed to render" not in block["verdict"]

    def test_a_paraphrase_that_always_raises_is_counted_as_rendering_failed(
        self, run_dir,
    ):
        """Branch B: MaskSpec.paraphrase is declared (has_control=True)
        but the callable raises on every occurrence — apply_mask reports
        applied=False, factor_present=False (see _substitute), so this
        lands under n_snapshots_control_rendering_failed instead, with a
        different verdict sentence pointing at mask_reason."""
        snapshots = load_snapshots(run_dir)
        decider = build_replay_decider(run_dir, model="mock")
        masks = _insurance_status_masks(paraphrase=_raises_vocabulary_drifted)
        result = run_ablation(
            snapshots, _design(factors=["insurance_status"]), _insensitive,
            decider=decider, factor_map=masks)
        block = result.summary["factors"]["insurance_status"]

        assert block["control_arm_present"] is False
        assert block["n_snapshots_control_rendering_failed"] > 0
        assert block["n_snapshots_control_not_declared"] == 0
        assert "failed to render" in block["verdict"]
        assert "see mask_reason" in block["verdict"]
        assert "declares no severity-matched" not in block["verdict"]

        control_rows = [
            row for row in result.samples
            if row["factor"] == "insurance_status" and row["arm"] == ARM_CONTROL
        ]
        assert control_rows
        assert all("vocabulary drifted" in row["mask_reason"] for row in control_rows)


class TestFactorAbsentFromAPrompt:
    def test_absent_snapshots_are_counted_not_scored_as_null(self, pieces):
        snapshots, decider, masks = pieces
        never_matches = FactorMap({"ghost": MaskSpec(
            provider="p", key="k", pattern=r"a phrase that never appears",
            neutral="Nothing is known.", paraphrase="Nothing at all is known.",
        )})
        result = run_ablation(snapshots, _design(factors=["ghost"]), _insensitive,
                              decider=decider, factor_map=never_matches)
        block = result.summary["factors"]["ghost"]
        assert block["n_snapshots_with_factor"] == 0
        assert block["n_snapshots_factor_absent"] == len(snapshots)
        assert "nothing was measured" in block["verdict"]

    def test_absent_arms_cost_no_decider_calls(self, pieces):
        """S1: an arm whose mask changed nothing has the baseline's own
        prompt, so calling the decider buys a duplicate."""
        snapshots, decider, masks = pieces
        never_matches = FactorMap({"ghost": MaskSpec(
            provider="p", key="k", pattern=r"a phrase that never appears",
            neutral="Nothing is known.", paraphrase="Nothing at all is known.",
        )})
        calls = {"n": 0}

        def _counting(prompt: str) -> str:
            calls["n"] += 1
            return '{"decision": 1}'

        design = _design(factors=["ghost"], determinism_n=2,
                         determinism_snapshots=1)
        result = run_ablation(snapshots, design, _counting,
                              decider=decider, factor_map=never_matches)
        # 2 gate calls + one baseline per snapshot per seed. The masked
        # and control arms are skipped entirely.
        assert calls["n"] == 2 + len(snapshots) * 2
        assert result.summary["decision_quality"]["n_calls_skipped_no_edit"] == (
            len(snapshots) * 2 * 2)
        assert result.summary["decider_prompt_sensitivity"]["n_compared"] == 0
        assert result.summary["decider_prompt_sensitivity"][
            "n_arms_excluded_factor_absent"] == len(snapshots) * 2 * 2

    def test_sensitivity_does_not_dilute_its_denominator_with_skipped_arms(
        self, pieces,
    ):
        """W8: counting arms that never edited anything as "compared"
        divides real changes by a pile of cells where nothing happened,
        and a factor missing from most prompts reports a reassuringly
        low sensitivity that is an artefact of the denominator."""
        snapshots, decider, masks = pieces
        mixed = FactorMap({
            "present": masks["neighbor_adoption_history"],
            "ghost": MaskSpec(
                provider="p", key="k", pattern=r"never appears anywhere",
                neutral="Nothing is known.", paraphrase="Nothing at all is known."),
        })
        result = run_ablation(snapshots, _design(factors=["present", "ghost"]),
                              _sensitive_to_any_edit,
                              decider=decider, factor_map=mixed)
        sensitivity = result.summary["decider_prompt_sensitivity"]
        # Only the 'present' factor's two arms edited anything.
        assert sensitivity["n_compared"] == len(snapshots) * 2 * 2
        assert sensitivity["n_changed"] == sensitivity["n_compared"]
        assert sensitivity["change_rate"] == pytest.approx(1.0)


class TestSeverityIsPairedPerSnapshot:
    def test_the_block_reports_the_worst_pair_not_only_the_mean(self, pieces):
        """S3: means of masked chars and control chars can agree while
        no individual snapshot is matched. The minimum is what the
        severity claim rests on."""
        snapshots, decider, masks = pieces
        result = run_ablation(snapshots, _design(), _insensitive,
                              decider=decider, factor_map=masks)
        severity = result.summary["factors"]["neighbor_adoption_history"]["severity"]
        assert severity["n_pairs"] == len(snapshots)
        assert severity["min_ratio"] is not None
        assert severity["mean_ratio"] is not None
        assert severity["matched"] is True
        assert severity["n_below_floor"] == 0

    def test_a_lopsided_control_fails_every_pair(self, pieces):
        snapshots, decider, masks = pieces
        lopsided = FactorMap({"trust": MaskSpec(
            provider="p", key="k",
            pattern=r"You have slight doubts about the insurance company\.",
            neutral=("You have no particular view of the insurance company, and "
                     "nothing in your experience has given you one either way."),
            paraphrase="You have slight doubts about the insurance company.!",
        )})
        result = run_ablation(snapshots, _design(factors=["trust"]), _insensitive,
                              decider=decider, factor_map=lopsided)
        severity = result.summary["factors"]["trust"]["severity"]
        assert severity["matched"] is False
        assert severity["n_below_floor"] == len(snapshots)
        assert "very different amounts" in severity["note"]
        # The caveat travels into the verdict, in the severity block's
        # own words rather than a generic sentence.
        verdict = result.summary["factors"]["trust"]["verdict"]
        assert "Caveat:" in verdict
        assert "very different amounts" in verdict


# ─────────────────────────────────────────────────────────────────────
# The CLI, end to end
# ─────────────────────────────────────────────────────────────────────

class TestCli:
    def test_list_factors(self, run_dir, capsys):
        from broker.tools.ablate_factor import main

        code = main([str(run_dir), "--masks", MASKS, "--list-factors"])
        assert code == 0
        declared = json.loads(capsys.readouterr().out)
        assert set(declared) == {"neighbor_adoption_history",
                                 "flood_experience_history",
                                 "grant_availability_history", "insurance_trust"}
        assert declared["neighbor_adoption_history"]["has_control"] is True
        assert declared["neighbor_adoption_history"]["expected_sign"] == -1

    def test_no_factor_source_is_refused(self, run_dir):
        from broker.tools.ablate_factor import main
        with pytest.raises(SystemExit, match="no factors declared"):
            main([str(run_dir), "--factor", "neighbor_adoption_history"])

    def test_unknown_factor_exits_nonzero(self, run_dir, capsys):
        from broker.tools.ablate_factor import main
        code = main([str(run_dir), "--masks", MASKS, "--factor", "nonsense"])
        assert code == 2
        assert "not declared" in capsys.readouterr().err

    def test_an_unregistered_domain_exits_nonzero(self, run_dir, capsys):
        """S2: --domain no_such_thing used to fall through to
        DefaultDomainPack and print "No factors declared for this
        domain", which reads as a fact about the domain."""
        from broker.tools.ablate_factor import main
        code = main([str(run_dir), "--domain", "no_such_domain",
                     "--factor", "anything"])
        assert code == 2
        assert "not registered" in capsys.readouterr().err

    def test_full_mock_ablation_writes_all_three_outputs(self, run_dir, tmp_path):
        """Two factors x two seeds x two replicates, through the real
        ModelAdapter and the built-in mock decider."""
        from broker.tools.ablate_factor import main

        out = tmp_path / "ablation"
        started = time.time()
        code = main([
            str(run_dir),
            "--masks", MASKS,
            "--factor", "neighbor_adoption_history,grant_availability_history",
            "--control", "paraphrase",
            "--seeds", "42,43", "--replicates", "2",
            "--model", "mock", "--determinism-n", "2",
            "--out", str(out),
        ])
        elapsed = time.time() - started

        assert code == 0
        assert elapsed < 60, f"end-to-end ablation took {elapsed:.1f}s"
        assert (out / "ablation_samples.csv").is_file()
        assert (out / "ablation_summary.json").is_file()
        assert (out / "determinism_report.json").is_file()

        with open(out / "ablation_samples.csv", encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        n_snapshots = len(load_snapshots(run_dir))
        assert len(rows) == n_snapshots * 2 * 2 * (1 + 2 * 2)
        for column in ("snapshot_id", "factor", "arm", "seed", "replicate",
                       "skill", "fidelity", "determinism_verified",
                       "n_matches", "decider_called", "action_stage",
                       "decision_action"):
            assert column in rows[0]

        summary = json.loads((out / "ablation_summary.json").read_text(encoding="utf-8"))
        assert summary["determinism_verified"] is True
        assert summary["delta_p_withheld"] is None
        assert summary["governance_evaluated"] is False
        assert summary["model_used"] == "mock"
        assert summary["trace_intake"]["n_traces_read"] == n_snapshots
        assert summary["decision_quality"]["n_empty_outputs"] == 0
        assert set(summary["factors"]) == {"neighbor_adoption_history",
                                           "grant_availability_history"}
        assert set(summary["factor_specs"]) == {"neighbor_adoption_history",
                                                "grant_availability_history"}

        determinism = json.loads(
            (out / "determinism_report.json").read_text(encoding="utf-8"))
        assert determinism["verified"] is True
        assert determinism["k_identical"] == determinism["n"]
        assert determinism["gate_snapshots"] == min(n_snapshots, 5)

    def test_default_output_directory_is_under_the_run(self, run_dir):
        from broker.tools.ablate_factor import main
        code = main([
            str(run_dir), "--masks", MASKS,
            "--factor", "insurance_trust", "--model", "mock",
            "--determinism-n", "2", "--limit", "2",
        ])
        assert code == 0
        assert (run_dir / "ablation" / "ablation_summary.json").is_file()

    def test_with_governance_without_a_validators_module_exits_nonzero(
        self, run_dir, capsys,
    ):
        """P0-B, at the CLI boundary."""
        from broker.tools.ablate_factor import main
        code = main([
            str(run_dir), "--masks", MASKS,
            "--factor", "grant_availability_history", "--model", "mock",
            "--determinism-n", "2", "--limit", "2", "--with-governance",
        ])
        assert code == 2
        err = capsys.readouterr().err
        assert "--validators-module" in err
        assert "ZERO domain validators" in err

    def test_with_governance_and_a_module_still_refuses_on_the_option_set(
        self, run_dir, capsys, validators_module,
    ):
        """P1-a: the trace does not record available_skills, so a
        governance replay would re-offer one-way skills."""
        from broker.tools.ablate_factor import main
        code = main([
            str(run_dir), "--masks", MASKS,
            "--factor", "grant_availability_history", "--model", "mock",
            "--determinism-n", "2", "--limit", "2", "--with-governance",
            "--validators-module", validators_module,
        ])
        assert code == 2
        assert "available_skills" in capsys.readouterr().err

    def test_action_stage_executed_without_governance_exits_nonzero(
        self, run_dir, capsys,
    ):
        """P1-b: a parse-only replay produces no executed action."""
        from broker.tools.ablate_factor import main
        code = main([
            str(run_dir), "--masks", MASKS,
            "--factor", "insurance_trust", "--model", "mock",
            "--action-stage", "executed",
        ])
        assert code == 2
        assert "--action-stage executed needs --with-governance" in capsys.readouterr().err

    def test_a_validators_module_without_governance_exits_nonzero(
        self, run_dir, capsys, validators_module,
    ):
        from broker.tools.ablate_factor import main
        code = main([
            str(run_dir), "--masks", MASKS,
            "--factor", "insurance_trust", "--model", "mock",
            "--validators-module", validators_module,
        ])
        assert code == 2
        assert "only means something with --with-governance" in capsys.readouterr().err

    def test_a_run_without_a_recorded_model_exits_nonzero(
        self, tmp_path, capsys,
    ):
        """P2: no silent 'mock'. The mock decider returns the first
        numbered option whatever the prompt says."""
        from broker.tools.ablate_factor import main
        run = write_run_dir(tmp_path / "modelless", n_agents=1, n_years=1)
        manifest_path = run / "reproducibility_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest.pop("model")
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

        code = main([str(run), "--masks", MASKS, "--factor", "insurance_trust"])
        assert code == 2
        assert "Defaulting to 'mock' is refused" in capsys.readouterr().err

    def test_a_missing_run_directory_exits_nonzero(self, tmp_path, capsys):
        from broker.tools.ablate_factor import main
        code = main([str(tmp_path / "nope"), "--masks", MASKS,
                     "--factor", "insurance_trust"])
        assert code == 2
        assert "not a directory" in capsys.readouterr().err

    @pytest.mark.parametrize("source_mode", ["disabled", "auto", "enabled"])
    def test_replay_uses_source_manifest_thinking_mode_and_restores_global(
        self, run_dir, tmp_path, monkeypatch, source_mode,
    ):
        from broker.tools import ablate_factor
        from broker.utils import llm_utils

        manifest_path = run_dir / "reproducibility_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["thinking_mode"] = source_mode
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        original_mode = "enabled" if source_mode != "enabled" else "disabled"
        monkeypatch.setattr(llm_utils.LLM_CONFIG, "thinking_mode", original_mode)
        observed = []

        monkeypatch.setattr(ablate_factor, "build_replay_decider", lambda *a, **k: object())
        monkeypatch.setattr(ablate_factor, "_print_report", lambda result: None)

        def fake_run(*args, **kwargs):
            observed.append(llm_utils.LLM_CONFIG.thinking_mode)
            return types.SimpleNamespace(summary={}, samples=[], determinism={})

        monkeypatch.setattr(ablate_factor, "run_ablation", fake_run)

        code = ablate_factor.main([
            str(run_dir), "--masks", MASKS, "--factor", "insurance_trust",
            "--model", "mock", "--out", str(tmp_path / "out"),
        ])

        assert code == 0
        assert observed == [source_mode]
        assert llm_utils.LLM_CONFIG.thinking_mode == original_mode
        summary = json.loads(
            (tmp_path / "out" / "ablation_summary.json").read_text(encoding="utf-8")
        )
        assert summary["cli"]["thinking_mode"] == source_mode

    def test_legacy_manifest_without_thinking_mode_replays_as_auto(
        self, run_dir, tmp_path, monkeypatch,
    ):
        from broker.tools import ablate_factor
        from broker.utils import llm_utils

        monkeypatch.setattr(llm_utils.LLM_CONFIG, "thinking_mode", "disabled")
        observed = []
        monkeypatch.setattr(ablate_factor, "build_replay_decider", lambda *a, **k: object())
        monkeypatch.setattr(ablate_factor, "_print_report", lambda result: None)

        def fake_run(*args, **kwargs):
            observed.append(llm_utils.LLM_CONFIG.thinking_mode)
            return types.SimpleNamespace(summary={}, samples=[], determinism={})

        monkeypatch.setattr(ablate_factor, "run_ablation", fake_run)

        code = ablate_factor.main([
            str(run_dir), "--masks", MASKS, "--factor", "insurance_trust",
            "--model", "mock", "--out", str(tmp_path / "out"),
        ])

        assert code == 0
        assert observed == ["auto"]
        assert llm_utils.LLM_CONFIG.thinking_mode == "disabled"
        summary = json.loads(
            (tmp_path / "out" / "ablation_summary.json").read_text(encoding="utf-8")
        )
        assert summary["cli"]["thinking_mode"] == "auto"

    @pytest.mark.parametrize("invalid_mode", [False, "off", "sometimes", None])
    def test_invalid_source_manifest_thinking_mode_is_refused(
        self, run_dir, monkeypatch, capsys, invalid_mode,
    ):
        from broker.tools import ablate_factor

        manifest_path = run_dir / "reproducibility_manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["thinking_mode"] = invalid_mode
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        run_spy = types.SimpleNamespace(called=False)

        def fake_run(*args, **kwargs):
            run_spy.called = True

        monkeypatch.setattr(ablate_factor, "run_ablation", fake_run)

        code = ablate_factor.main([
            str(run_dir), "--masks", MASKS, "--factor", "insurance_trust",
            "--model", "mock",
        ])

        assert code == 2
        assert run_spy.called is False
        error = capsys.readouterr().err
        assert "thinking_mode" in error
        assert "auto, disabled, enabled" in error
