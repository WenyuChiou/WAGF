"""Run the factor x arm x seed x replicate grid over a set of snapshots.

The grid
--------
For every recorded decision, every declared factor is replayed in up to
three arms:

``baseline``            the prompt exactly as the agent saw it
``masked``              the factor replaced by its neutral rendering
``paraphrase_control``  the factor reworded, information preserved

Every arm runs at the same seeds, so the comparison is within-decision.
The baseline is computed once per (snapshot, seed, replicate) and shared
across factors, because the baseline prompt does not depend on which
factor is under test — running it once per factor would triple the cost
and add nothing.

An arm whose mask changed nothing — the factor is absent from this
prompt, or declares no paraphrase control — never reaches the decider.
Its prompt would be byte-identical to the baseline this cell already
holds. The row is still written, with ``decider_called=False`` and the
reason, so a skipped cell is visible rather than missing.

Replicates
----------
With a verified-deterministic decider, replicates are redundant by
construction and exist as a monitor: if two replicates of the SAME cell
disagree, determinism broke mid-run and the run says so rather than
averaging over it.

The gate
--------
Before any grid runs, a SAMPLE of the snapshots is replayed unmasked
``determinism_n`` times each (``determinism_snapshots``, five by
default — the gate is about the backend, not about any one prompt, and
gating every snapshot in a 3,276-row corpus costs more than the grid).
Passing needs three things at once: identical replies, no empty reply,
and at least one reply that parsed. If the decider fails any of them,
this module still writes the sample table (the raw replays are data) but
``AblationResult.delta_p`` is ``None`` and every per-factor effect
quantity is nulled with ``withheld: true``. There is no flag to override
that: a delta-P over a backend that disagrees with itself is a
measurement of the backend's noise, and a delta-P over a backend that
returned nothing is a measurement of nothing.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Callable, Dict, List, Optional, Sequence

from broker.experiments import metrics as _metrics
from broker.experiments.replay import (
    ARM_BASELINE,
    ARM_CONTROL,
    ARM_MASKED,
    DecisionSnapshot,
    DeterminismReport,
    FactorMap,
    ReplayDecider,
    ReplayResult,
    determinism_check,
    merge_determinism_reports,
    replay_decision,
)
from broker.utils.logging import logger

UNPARSED_LABEL = "__unparsed__"

#: How many snapshots the determinism gate samples when the design does
#: not say. The gate is a question about the backend; five prompts
#: answers it, and gating all of them costs more than the grid it guards.
#: ``determinism_snapshots=None`` still means "every snapshot".
DEFAULT_DETERMINISM_SNAPSHOTS = 5

#: The per-factor refusal when this factor's own replays came back
#: without a decision — on either side of the pair. Formatted with
#: (n_total_no_decision, n_total_rows, n_baseline_no_decision,
#: n_arm_no_decision): a masked or control arm that produced no decision
#: saturates delta-P at -1.000 exactly as a no-decision baseline does, so
#: both sides are counted and named separately.
NO_DECISION_VERDICT = (
    "verdict withheld: {0} of {1} replays (baseline {2}, masked/control {3}) "
    "returned no decision"
)


@dataclass(frozen=True)
class AblationDesign:
    """What to run. Nothing here is inferred from the data."""

    factors: Sequence[str]
    controls: Sequence[str] = ("paraphrase",)
    seeds: Sequence[int] = (42,)
    n_replicates: int = 1
    action_stage: str = "proposed"
    determinism_n: int = 5
    determinism_snapshots: Optional[int] = DEFAULT_DETERMINISM_SNAPSHOTS

    def __post_init__(self) -> None:
        if not self.factors:
            raise ValueError("An ablation design needs at least one factor.")
        if not self.seeds:
            raise ValueError("An ablation design needs at least one seed.")
        if self.n_replicates < 1:
            raise ValueError("n_replicates must be >= 1.")
        if self.determinism_n < 2:
            raise ValueError("determinism_n must be >= 2 to compare anything.")
        if self.determinism_snapshots is not None and self.determinism_snapshots < 1:
            raise ValueError(
                "determinism_snapshots must be >= 1, or None for every "
                "snapshot. Zero would run no gate at all and report the "
                "result as though one had passed."
            )
        if self.action_stage not in ("proposed", "executed"):
            raise ValueError(
                f"Unknown action_stage {self.action_stage!r}; "
                "use 'proposed' or 'executed'."
            )
        for control in self.controls:
            if control != "paraphrase":
                raise ValueError(
                    f"Unknown control arm {control!r}; only 'paraphrase' exists."
                )

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        for key in ("factors", "controls", "seeds"):
            data[key] = list(data[key])
        return data


@dataclass
class AblationResult:
    """Long-format samples plus the summary they support."""

    samples: List[Dict[str, Any]]
    summary: Dict[str, Any]
    determinism: Dict[str, Any]
    delta_p: Optional[Dict[str, Dict[str, float]]]

    @property
    def determinism_verified(self) -> bool:
        return bool(self.determinism.get("verified"))


def _cell_key(snapshot_id: str, factor: str, arm: str, seed: Optional[int]) -> tuple:
    return (snapshot_id, factor, arm, seed)


def _skill_label(result: ReplayResult) -> str:
    """The action this row contributes to a distribution.

    ``ReplayResult.decision_action`` is already the stage-appropriate
    action: the proposal by default, the post-governance action under
    ``--action-stage executed``. Reading ``skill`` here instead was the
    bug that let an executed-stage run anchor its delta-P on the
    executed action while building every distribution from proposals.
    """
    return (result.decision_action if result.decision_action is not None
            else UNPARSED_LABEL)


def _decider_calls(cells: Dict[tuple, List[ReplayResult]]) -> List[ReplayResult]:
    return [r for results in cells.values() for r in results if r.decider_called]


def run_ablation(
    snapshots: Sequence[DecisionSnapshot],
    design: AblationDesign,
    llm_invoke: Callable,
    *,
    decider: ReplayDecider,
    factor_map: FactorMap,
    load_report: Optional[Dict[str, Any]] = None,
) -> AblationResult:
    """Execute the design and summarise it.

    Raises ``KeyError`` if the design names a factor the domain does not
    declare — an ablation over an undeclared factor would silently mask
    nothing and report a null effect.
    """
    if not snapshots:
        raise ValueError("run_ablation needs at least one snapshot.")
    missing = [f for f in design.factors if f not in factor_map]
    if missing:
        raise KeyError(
            f"Factors {missing} are not declared by this domain. "
            f"Declared: {factor_map.names}."
        )
    if design.action_stage == "executed" and not decider.governance_evaluated:
        raise ValueError(
            "action_stage='executed' needs a governance decider. Parse-only "
            "replay produces no executed action, so every executed-stage "
            "distribution would be a column of '__unparsed__'."
        )

    # ── 1. The gate ────────────────────────────────────────────────
    gate_snapshots = list(snapshots)
    if design.determinism_snapshots is not None:
        gate_snapshots = gate_snapshots[:design.determinism_snapshots]
    reports: List[DeterminismReport] = [
        determinism_check(
            snapshot, llm_invoke, n=design.determinism_n,
            decider=decider, seed=design.seeds[0],
        )
        for snapshot in gate_snapshots
    ]
    gate = merge_determinism_reports(reports)
    if not gate.verified:
        logger.warning("[Ablation] determinism gate FAILED — %s", gate.summary_line)
        if gate.note:
            logger.warning("[Ablation] %s", gate.note)

    # ── 2. The grid ────────────────────────────────────────────────
    samples: List[Dict[str, Any]] = []
    cells: Dict[tuple, List[ReplayResult]] = {}

    def _record(result: ReplayResult) -> None:
        cells.setdefault(
            _cell_key(result.snapshot_id, result.factor, result.arm, result.seed), []
        ).append(result)

    arms: List[tuple] = [(ARM_MASKED, None)]
    if "paraphrase" in design.controls:
        arms.append((ARM_CONTROL, "paraphrase"))

    for snapshot in snapshots:
        for seed in design.seeds:
            for replicate in range(design.n_replicates):
                base = replay_decision(
                    snapshot, mask=None, control=None, seed=seed,
                    llm_invoke=llm_invoke, factor_map=factor_map,
                    decider=decider, replicate=replicate,
                    action_stage=design.action_stage,
                )
                _record(base)
                for factor in design.factors:
                    for arm, control in arms:
                        result = replay_decision(
                            snapshot, mask={factor}, control=control, seed=seed,
                            llm_invoke=llm_invoke, factor_map=factor_map,
                            decider=decider, replicate=replicate,
                            action_stage=design.action_stage,
                        )
                        _record(result)

    # ── 3. Replicate agreement: determinism, measured during the run ─
    # Only cells the decider actually ran can disagree; a skipped arm has
    # no output and would otherwise look perfectly stable.
    unstable_cells = [
        key for key, results in cells.items()
        if len({(_skill_label(r), r.raw_output)
                for r in results if r.decider_called}) > 1
    ]
    runtime_stable = not unstable_cells
    if not runtime_stable:
        logger.warning(
            "[Ablation] %d cell(s) returned different output across replicates "
            "of the same prompt and seed; determinism broke mid-run.",
            len(unstable_cells),
        )
    determinism_verified = gate.verified and runtime_stable

    # Long-format rows carry the verdict so a table read on its own
    # cannot be mistaken for one that passed the gate.
    for results in cells.values():
        for result in results:
            row = result.to_row()
            row["determinism_verified"] = determinism_verified
            row["decider_source"] = decider.source
            samples.append(row)
    samples.sort(key=lambda r: (r["snapshot_id"], r["factor"], r["arm"],
                                r["seed"] if r["seed"] is not None else -1,
                                r["replicate"]))

    # ── 4. Vocabulary ──────────────────────────────────────────────
    vocabulary = sorted({
        _skill_label(r) for r in _decider_calls(cells)
    } | {
        snapshot.reference_action(design.action_stage)
        for snapshot in snapshots
        if snapshot.reference_action(design.action_stage)
    })

    # ── 5. Did the decider actually decide anything? ───────────────
    calls = _decider_calls(cells)
    decision_quality = {
        "n_decider_calls": len(calls),
        "n_calls_skipped_no_edit": sum(
            1 for results in cells.values() for r in results if not r.decider_called),
        "n_errors": sum(1 for r in calls if r.error),
        "n_empty_outputs": sum(1 for r in calls if not (r.raw_output or "").strip()),
        "n_unparsed": sum(1 for r in calls if r.decision_action is None),
        "note": "",
    }
    if calls and decision_quality["n_unparsed"] == len(calls):
        decision_quality["note"] = (
            "Every replay that reached the decider came back without a usable "
            "action. Nothing in this table supports an inference; check the "
            "backend before reading anything else."
        )
    elif decision_quality["n_empty_outputs"] or decision_quality["n_errors"]:
        decision_quality["note"] = (
            f"{decision_quality['n_empty_outputs']} empty and "
            f"{decision_quality['n_unparsed']} unparsable reply/replies out of "
            f"{len(calls)} decider calls. Those rows carry no action and are "
            "counted as '__unparsed__' in every distribution."
        )

    # ── 6. Per-factor summary ──────────────────────────────────────
    withheld_message = None
    if not determinism_verified:
        withheld_message = (
            f"ΔP withheld: backend non-deterministic "
            f"({gate.k_identical} of {gate.n} identical)"
            + ("" if runtime_stable else
               f"; {len(unstable_cells)} cell(s) also disagreed across replicates")
        )
        if gate.note:
            withheld_message += f". {gate.note}"

    factor_blocks: Dict[str, Any] = {}
    delta_p: Optional[Dict[str, Dict[str, float]]] = {} if determinism_verified else None

    for factor in design.factors:
        block = _summarise_factor(
            factor=factor,
            spec=factor_map[factor],
            snapshots=snapshots,
            cells=cells,
            design=design,
            vocabulary=vocabulary,
            determinism_verified=determinism_verified,
            withheld_message=withheld_message,
        )
        factor_blocks[factor] = block["summary"]
        if delta_p is not None:
            delta_p[factor] = block["per_snapshot_delta_p"]

    fidelity_counts: Dict[str, int] = {}
    for snapshot in snapshots:
        fidelity_counts[snapshot.fidelity] = fidelity_counts.get(snapshot.fidelity, 0) + 1

    seed_applied = all(r.seed_applied for r in calls) if calls else False
    summary = {
        "n_snapshots": len(snapshots),
        "n_samples": len(samples),
        "run_dir": snapshots[0].run_dir,
        "git_commit": snapshots[0].git_commit,
        "model": snapshots[0].model,
        "model_used": decider.model or snapshots[0].model,
        "model_source": decider.model_source,
        "action_stage": design.action_stage,
        "design": design.to_dict(),
        "trace_intake": dict(load_report) if load_report else {
            "note": ("Not recorded: run_ablation was called without the "
                     "load_snapshots report, so the number of traces read, "
                     "dropped and skipped is unknown for this run."),
        },
        "fidelity_regimes": fidelity_counts,
        "governance_evaluated": decider.governance_evaluated,
        "decider_source": decider.source,
        "validators_source": decider.validators_source,
        "financial_constraints": decider.financial_constraints,
        "seeds_applied_to_decider": seed_applied,
        "seeds_note": "" if seed_applied else (
            "The decider callable does not accept a seed, so every seed "
            "column holds a repeat of the same unseeded call. Rows are "
            "paired by construction, but the seeds are labels, not draws. "
            "Every backend create_llm_invoke returns today has the "
            "signature invoke(prompt), so this is the normal state."
        ),
        "decision_quality": decision_quality,
        "baseline_reproduces_trace": _baseline_reproduction(cells),
        "decider_prompt_sensitivity": _prompt_sensitivity(cells, determinism_verified),
        "determinism_verified": determinism_verified,
        "delta_p_withheld": withheld_message,
        "factors": factor_blocks,
    }

    determinism = gate.to_dict()
    determinism["runtime_replicate_stable"] = runtime_stable
    determinism["unstable_cells"] = [list(key) for key in unstable_cells[:20]]
    determinism["gate_snapshots"] = len(gate_snapshots)
    determinism["gate_snapshots_requested"] = design.determinism_snapshots
    determinism["verified"] = determinism_verified

    return AblationResult(
        samples=samples, summary=summary,
        determinism=determinism, delta_p=delta_p,
    )


def _baseline_reproduction(cells: Dict[tuple, List[ReplayResult]]) -> Dict[str, Any]:
    """Did the unmasked replay return the decision the trace recorded?

    A reconstruction that cannot reproduce the original decision is not a
    reconstruction, whatever the masked arms then show. Reported, not
    enforced: a deliberate cross-model replay is expected to disagree.

    Rows whose trace recorded no action at all are counted separately
    under ``n_recorded_missing``. Folding them in as matches — which
    ``None == None`` did — let a corpus that recorded nothing report a
    perfect reproduction rate.
    """
    baselines = [
        r for results in cells.values() for r in results
        if r.arm == ARM_BASELINE and r.decider_called
    ]
    comparable = [r for r in baselines if r.matches_trace is not None]
    n_recorded_missing = sum(1 for r in baselines if r.recorded_skill is None)
    if not comparable:
        return {
            "n": 0, "matched": 0, "rate": None,
            "n_recorded_missing": n_recorded_missing,
            "note": (
                "No baseline row carried a recorded decision to compare. "
                f"{n_recorded_missing} of {len(baselines)} baseline replay(s) "
                "had nothing recorded in the trace, so agreement is "
                "unmeasured — not perfect."
            ),
        }
    matched = sum(1 for r in comparable if r.matches_trace)
    rate = matched / len(comparable)
    note = ""
    if rate != 1.0:
        note = (
            "Some unmasked replays did not reproduce the recorded decision. "
            "Check the model, the agent config and the fidelity regime "
            "before reading the masked arms."
        )
    if n_recorded_missing:
        note += (
            f" {n_recorded_missing} baseline replay(s) had no recorded action "
            "in the trace and are excluded from the rate rather than counted "
            "as agreement."
        )
    return {
        "n": len(comparable),
        "matched": matched,
        "rate": rate,
        "n_recorded_missing": n_recorded_missing,
        "note": note.strip(),
    }


def _prompt_sensitivity(
    cells: Dict[tuple, List[ReplayResult]], determinism_verified: bool,
) -> Dict[str, Any]:
    """How often ANY edit that actually happened changed the decision.

    The denominator counts only arms whose factor was present and whose
    prompt therefore differed from the baseline. Counting factor-absent
    arms as well would divide the changes by a pile of cells where the
    prompt was never edited, and a tool that masks a factor missing from
    most prompts would report a reassuringly low sensitivity that is an
    artefact of the denominator.

    Zero is a real finding and an ambiguous one. It means either that
    none of these factors is used, or that this decider does not read the
    edited parts of the prompt — the built-in ``mock`` decider, for
    instance, returns the first numbered option whatever else the prompt
    says, so every factor comes back with a delta-P of exactly zero. The
    note below says so, rather than letting a reader take a stack of
    clean zeros for a scientific result.
    """
    baseline_by_key: Dict[tuple, str] = {}
    for key, results in cells.items():
        snapshot_id, factor, arm, seed = key
        if arm == ARM_BASELINE and results and results[0].decider_called:
            baseline_by_key[(snapshot_id, seed)] = _skill_label(results[0])

    compared = 0
    changed = 0
    skipped_absent = 0
    for key, results in cells.items():
        snapshot_id, factor, arm, seed = key
        if arm == ARM_BASELINE or not results:
            continue
        row = results[0]
        if not row.decider_called or not row.factor_present:
            skipped_absent += 1
            continue
        base = baseline_by_key.get((snapshot_id, seed))
        if base is None:
            continue
        compared += 1
        if _skill_label(row) != base:
            changed += 1

    rate = (changed / compared) if compared else None
    note = ""
    # Residual (code-reviewer): this block reads the same replays the
    # determinism gate just failed on. A non-deterministic or empty
    # backend can produce a "sensitivity" number by accident — a
    # coin-flip decider changes its answer whether or not the prompt
    # changed — so it is withheld the same way the effect fields are,
    # rather than left to look like an independent measurement.
    if not determinism_verified:
        note = (
            "Withheld: the determinism gate did not pass, so these are the "
            "same non-deterministic (or empty/unparsable) backend calls the "
            "gate already flagged. A change rate computed from them measures "
            "backend noise, not sensitivity to the edited prompt text."
        )
    elif compared and changed == 0:
        note = (
            "No edit to any prompt changed any decision. Either none of "
            "these factors is used by this decider, or this decider does "
            "not read the edited parts of the prompt — the built-in 'mock' "
            "decider always returns the first numbered option, so it "
            "produces exactly this pattern by construction."
        )
    elif not compared:
        note = (
            "No arm edited its prompt, so sensitivity is unmeasured. Every "
            "masked and control arm was skipped because its factor was "
            "absent or declared no control."
        )
    return {"n_compared": compared, "n_changed": changed,
            "n_arms_excluded_factor_absent": skipped_absent,
            "change_rate": rate, "note": note,
            "withheld": not determinism_verified}


#: Every per-factor quantity that describes an EFFECT. All of them are
#: nulled together when the run cannot support an inference, so a reader
#: cannot pick a surviving number out of a withheld block. JSD, KL and
#: directional consistency belong here: they are computed from the same
#: replays as delta-P and mean exactly as little when the backend
#: disagreed with itself.
EFFECT_FIELDS = (
    "delta_p_masked_mean",
    "delta_p_control_mean",
    "effect_vs_control",
    "wilcoxon_baseline_vs_masked",
    "wilcoxon_baseline_vs_control",
    "wilcoxon_masked_vs_control",
    "jsd_masked_mean",
    "jsd_control_mean",
    "kl_masked_mean",
    "kl_control_mean",
    "directional_consistency",
)


def _summarise_factor(
    *,
    factor: str,
    spec: Any,
    snapshots: Sequence[DecisionSnapshot],
    cells: Dict[tuple, List[ReplayResult]],
    design: AblationDesign,
    vocabulary: Sequence[str],
    determinism_verified: bool,
    withheld_message: Optional[str],
) -> Dict[str, Any]:
    per_snapshot_delta_p: Dict[str, float] = {}
    masked_deltas: List[float] = []
    control_deltas: List[float] = []
    masked_jsd: List[float] = []
    control_jsd: List[float] = []
    masked_kl: List[float] = []
    control_kl: List[float] = []
    severity_pairs: List[Sequence[float]] = []
    match_counts: List[int] = []
    n_absent = 0
    n_control_not_declared = 0
    n_control_rendering_failed = 0
    n_baseline_mismatch = 0
    n_baseline_no_decision = 0
    n_baseline_rows = 0
    n_arm_no_decision = 0
    n_arm_rows = 0
    control_available = False
    #: Whether this design even asked the grid to run the control arm.
    #: A factor whose control never ran because ``--control none`` was
    #: passed has not "failed to render" — it was never attempted — so
    #: that case is reported as "not declared" rather than as a failure.
    control_requested = "paraphrase" in design.controls

    for snapshot in snapshots:
        action = snapshot.reference_action(design.action_stage)

        def _labels(arm: str, factor_name: str) -> List[str]:
            out: List[str] = []
            for seed in design.seeds:
                results = cells.get(_cell_key(snapshot.snapshot_id, factor_name, arm, seed))
                if results and results[0].decider_called:
                    out.append(_skill_label(results[0]))
            return out

        masked_results = [
            cells.get(_cell_key(snapshot.snapshot_id, factor, ARM_MASKED, seed))
            for seed in design.seeds
        ]
        masked_flat = [r[0] for r in masked_results if r]
        if not masked_flat:
            continue
        if not any(r.factor_present for r in masked_flat):
            n_absent += 1
            continue

        # P1 (hunter): a masked replay that came back with no decision
        # saturates delta-P at -1.000 exactly as a no-decision baseline
        # does. Counted here, alongside the baseline count below, so
        # withholding fires on either side of the pair.
        n_arm_rows += len(masked_flat)
        n_arm_no_decision += sum(
            1 for r in masked_flat if r.produced_no_decision)

        baseline_flat = [
            row for results in (
                cells.get(_cell_key(snapshot.snapshot_id, "", ARM_BASELINE, seed))
                for seed in design.seeds
            ) if results for row in results
        ]
        n_baseline_rows += len(baseline_flat)
        n_baseline_no_decision += sum(
            1 for r in baseline_flat if r.produced_no_decision)

        p_base = _metrics.action_distribution(_labels(ARM_BASELINE, ""), vocabulary)
        p_mask = _metrics.action_distribution(_labels(ARM_MASKED, factor), vocabulary)

        # delta-P is anchored on the action the TRACE recorded, because
        # that is the action whose stated reason is under test. If the
        # unmasked replay never produces it, the anchor is one this
        # decider does not use and the delta-P below is near-meaningless.
        if _metrics.probability_of(p_base, action) == 0.0:
            n_baseline_mismatch += 1

        d_mask = (_metrics.probability_of(p_mask, action)
                  - _metrics.probability_of(p_base, action))
        masked_deltas.append(d_mask)
        masked_jsd.append(_metrics.jensen_shannon_divergence(p_base, p_mask))
        masked_kl.append(_metrics.kl_divergence(p_base, p_mask))
        masked_chars = sum(r.perturbation_chars for r in masked_flat) / len(masked_flat)
        match_counts.extend(r.n_matches for r in masked_flat if r.decider_called)
        per_snapshot_delta_p[snapshot.snapshot_id] = d_mask

        control_results = [
            cells.get(_cell_key(snapshot.snapshot_id, factor, ARM_CONTROL, seed))
            for seed in design.seeds
        ]
        control_flat = [r[0] for r in control_results if r]
        n_arm_rows += len(control_flat)
        n_arm_no_decision += sum(
            1 for r in control_flat if r.produced_no_decision)
        if control_flat and any(r.factor_present for r in control_flat):
            control_available = True
            p_ctrl = _metrics.action_distribution(_labels(ARM_CONTROL, factor), vocabulary)
            control_deltas.append(
                _metrics.probability_of(p_ctrl, action)
                - _metrics.probability_of(p_base, action)
            )
            control_jsd.append(_metrics.jensen_shannon_divergence(p_base, p_ctrl))
            control_kl.append(_metrics.kl_divergence(p_base, p_ctrl))
            control_chars = (
                sum(r.perturbation_chars for r in control_flat) / len(control_flat))
            # S3: the pair is per snapshot. Averaging masked chars over
            # all snapshots and control chars over all snapshots and
            # dividing the two means hides a factor that matches one
            # bullet here and five there.
            severity_pairs.append((masked_chars, control_chars))
        else:
            # P2 (hunter): which of the two reasons this factor has no
            # control on this snapshot travels separately, because they
            # call for different fixes — one is a declaration the domain
            # never made, the other is a render that broke on this
            # prompt. ``spec.has_control`` is a per-factor constant, so
            # this can never be ambiguous: if the factor declares no
            # control, EVERY occurrence lands here for that reason; if it
            # does declare one, landing here means the render failed.
            if control_requested and spec.has_control:
                n_control_rendering_failed += 1
            else:
                n_control_not_declared += 1
            control_deltas.append(float("nan"))
            severity_pairs.append((masked_chars, 0.0))

    def _mean(values: Sequence[Optional[float]]) -> Optional[float]:
        clean = [v for v in values if v is not None and v == v]  # drop None/NaN
        return sum(clean) / len(clean) if clean else None

    paired = [
        (m, c) for m, c in zip(masked_deltas, control_deltas) if c == c
    ]
    masked_paired = [m for m, _ in paired]
    control_paired = [c for _, c in paired]

    expected_sign = getattr(spec, "expected_sign", -1)
    summary: Dict[str, Any] = {
        "n_snapshots_with_factor": len(masked_deltas),
        "n_snapshots_factor_absent": n_absent,
        "n_snapshots_control_not_declared": n_control_not_declared,
        "n_snapshots_control_rendering_failed": n_control_rendering_failed,
        "n_snapshots_baseline_never_produced_the_recorded_action": n_baseline_mismatch,
        "n_baseline_replays_without_a_decision": n_baseline_no_decision,
        "n_baseline_replays": n_baseline_rows,
        "n_arm_replays_without_a_decision": n_arm_no_decision,
        "n_arm_replays": n_arm_rows,
        "control_arm_present": control_available,
        "expected_sign": expected_sign,
        "matches_mean": (sum(match_counts) / len(match_counts)) if match_counts else None,
        "matches_max": max(match_counts) if match_counts else None,
        "severity": _metrics.severity_match_paired(severity_pairs),
        "min_pairs_for_p": _metrics.MIN_PAIRS,
        "withheld": False,
        "p_value_withheld": None,
    }

    # P0-A / P1 (hunter): the baseline OR the masked/control arm this
    # factor is measured against came back without a decision, so the
    # "difference" between arms is a difference that includes an
    # absence. Checking only the baseline side let a masked or control
    # arm's ReplayResult.produced_no_decision saturate delta-P at
    # -1.000 with withheld staying false.
    n_total_no_decision = n_baseline_no_decision + n_arm_no_decision
    no_decision_message = None
    if n_total_no_decision:
        n_total_rows = (n_baseline_rows + n_arm_rows) or n_total_no_decision
        no_decision_message = NO_DECISION_VERDICT.format(
            n_total_no_decision, n_total_rows,
            n_baseline_no_decision, n_arm_no_decision)

    if not determinism_verified or no_decision_message:
        message = withheld_message or no_decision_message
        if withheld_message and no_decision_message:
            message = f"{withheld_message}. {no_decision_message}"
        summary.update({key: None for key in EFFECT_FIELDS})
        summary.update({
            "withheld": True,
            "delta_p_withheld": message,
            "verdict": message,
        })
        return {"summary": summary, "per_snapshot_delta_p": {}}

    summary.update({
        "jsd_masked_mean": _mean(masked_jsd),
        "jsd_control_mean": _mean(control_jsd),
        "kl_masked_mean": _mean(masked_kl),
        "kl_control_mean": _mean(control_kl),
        "directional_consistency": _metrics.directional_consistency(
            masked_deltas, expected_sign=expected_sign),
    })

    mean_masked = _mean(masked_deltas)
    mean_control = _mean(control_deltas)
    effect_vs_control = (
        None if (mean_masked is None or mean_control is None)
        else mean_masked - mean_control
    )

    w_masked = (_metrics.wilcoxon_signed_rank(masked_deltas)
                if masked_deltas else None)
    w_control = (_metrics.wilcoxon_signed_rank([c for c in control_deltas if c == c])
                 if any(c == c for c in control_deltas) else None)
    w_versus = (_metrics.wilcoxon_signed_rank(masked_paired, control_paired)
                if paired else None)

    p_withheld = _p_withheld_message(w_versus)
    summary.update({
        "delta_p_masked_mean": mean_masked,
        "delta_p_control_mean": mean_control,
        "effect_vs_control": effect_vs_control,
        "wilcoxon_baseline_vs_masked": _mark_p(w_masked),
        "wilcoxon_baseline_vs_control": _mark_p(w_control),
        "wilcoxon_masked_vs_control": _mark_p(w_versus),
        "delta_p_withheld": None,
        "p_value_withheld": p_withheld,
        "verdict": _verdict(factor, mean_masked, mean_control,
                            effect_vs_control, w_versus, control_available,
                            summary["severity"], n_baseline_mismatch,
                            len(masked_deltas), p_withheld,
                            n_control_rendering_failed),
    })
    return {"summary": summary, "per_snapshot_delta_p": per_snapshot_delta_p}


def _p_withheld_message(test: Optional[Dict[str, Any]]) -> Optional[str]:
    """The refusal text when a p-value comes from too few moving pairs."""
    if not test or test.get("p_value") is None:
        return None
    n_nonzero = int(test.get("n_nonzero") or 0)
    if n_nonzero >= _metrics.MIN_PAIRS:
        return None
    floor = _metrics.attainable_p_floor(n_nonzero)
    floor_text = "undefined" if floor is None else f"{floor:.4g}"
    return (
        f"p withheld: n_nonzero={n_nonzero} below minimum "
        f"{_metrics.MIN_PAIRS} (attainable floor 2^-({n_nonzero}-1) = "
        f"{floor_text}; the smallest p this many pairs can produce, reached "
        "whenever they all move the same way)"
    )


def _mark_p(test: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Copy a Wilcoxon result, moving an underpowered p out of ``p_value``.

    The number is kept — under ``p_value_below_minimum``, with the
    refusal beside it — because an auditor should be able to see it. It
    just stops being the field a reader quotes by reflex.
    """
    if test is None:
        return None
    marked = dict(test)
    message = _p_withheld_message(test)
    if message:
        marked["p_value_below_minimum"] = marked.pop("p_value")
        marked["p_value"] = None
        marked["p_withheld"] = message
    else:
        marked["p_withheld"] = None
    return marked


def _verdict(
    factor: str,
    mean_masked: Optional[float],
    mean_control: Optional[float],
    effect_vs_control: Optional[float],
    w_versus: Optional[Dict[str, Any]],
    control_available: bool,
    severity: Dict[str, Any],
    n_baseline_mismatch: int = 0,
    n_measured: int = 0,
    p_withheld: Optional[str] = None,
    n_control_rendering_failed: int = 0,
) -> str:
    """One sentence a reader can act on, with the caveats attached."""
    if mean_masked is None:
        return f"No snapshot carried factor {factor!r}; nothing was measured."
    n_nonzero = int((w_versus or {}).get("n_nonzero") or 0)
    # P1-d: the sample size travels with the claim. A verdict quoting an
    # effect and a p-value without saying how many snapshots produced
    # them reads the same at n=6 as at n=600.
    size_text = (f" Based on {n_measured} snapshot(s) carrying the factor, "
                 f"{n_nonzero} of which moved.")
    anchor_caveat = "" if not n_baseline_mismatch else (
        f" Caveat: on {n_baseline_mismatch} of {n_measured} snapshots the "
        f"unmasked replay never produced the recorded action, so ΔP is "
        f"anchored on an action this decider does not choose."
    )
    if not control_available:
        # P2 (hunter): "declares no control" and "declared one but it
        # failed to render on this run" are different facts, and call for
        # different fixes — one needs a MaskSpec.paraphrase, the other
        # needs the pattern or the callable looked at (see mask_reason).
        if n_control_rendering_failed:
            return (
                f"Removing {factor!r} moved the reported action's probability "
                f"by {mean_masked:+.3f} on average, but its severity-matched "
                f"control failed to render on {n_control_rendering_failed} "
                f"snapshot(s) — see mask_reason — so the number cannot be "
                f"separated from a generic sensitivity to any edit of that "
                f"size." + size_text + anchor_caveat
            )
        return (
            f"Removing {factor!r} moved the reported action's probability by "
            f"{mean_masked:+.3f} on average, but this factor declares no "
            f"severity-matched paraphrase control, so the number cannot be "
            f"separated from a generic sensitivity to any edit of that size."
            + size_text + anchor_caveat
        )
    p_value = (w_versus or {}).get("p_value")
    # P2 (hunter): the verdict quotes p without saying how it was
    # computed. scipy exact and a tie-corrected normal approximation are
    # different tests with different assumptions; the method travels with
    # the number wherever the number is read, not only in the JSON.
    method_text = (w_versus or {}).get("method")
    if p_value is None:
        # "undefined" here just restates "every pair tied" — the test
        # never ran, so there is no method to name.
        p_text = "p undefined (every pair tied)"
    elif p_withheld:
        p_text = f"{p_withheld}, {method_text}" if method_text else p_withheld
    else:
        p_text = (f"p={p_value:.4g}, {method_text}" if method_text
                  else f"p={p_value:.4g}")
    caveat = anchor_caveat + ("" if severity.get("matched") else (
        " Caveat: " + (severity.get("note") or
                       "the two arms edited very different amounts of text, so "
                       "the comparison is not yet severity-matched.")
    ))
    if effect_vs_control is None:
        return (f"Masked ΔP {mean_masked:+.3f}; control incomparable."
                + size_text + caveat)
    if abs(effect_vs_control) < 1e-9:
        return (
            f"Masking {factor!r} (ΔP {mean_masked:+.3f}) moved the action no "
            f"more than the severity-matched paraphrase did "
            f"(ΔP {mean_control:+.3f}); {p_text}. This run gives no evidence "
            f"that {factor!r} is what the decision used." + size_text + caveat
        )
    return (
        f"Masking {factor!r} moved the reported action's probability by "
        f"{mean_masked:+.3f} against {mean_control:+.3f} for the "
        f"severity-matched paraphrase, a difference of "
        f"{effect_vs_control:+.3f} ({p_text}, paired Wilcoxon across "
        f"snapshots)." + size_text + caveat
    )
