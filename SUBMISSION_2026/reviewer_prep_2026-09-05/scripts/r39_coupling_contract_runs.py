"""R39 -- irrigation coupling-CONTEXT-CONTRACT run: does the PR-9 (F1)
config-switchable guard on ``IrrigationEnvironment.get_agent_context()``
fire cleanly (active, guard_calls>0, no CouplingViolation) for a real-LLM
strict run, and does enabling it change measured outcomes vs the matched
faf1bb12 seed-42 comparator and the 5-seed band? CPU-only (GPU busy -- no
LLM calls, existing/landing CSVs only).

QUESTION -- CORRECTED 2026-09-23 (see below)
  Author decision (A), 2026-09-22, corrected 2026-09-23 after a coordinator
  review of this script's FIRST version: the coupling switch irrigation
  actually has config-only access to is NOT the v0.6 broker/coupling/
  two-layer flag (``global_config.coupling.enable`` ->
  ``EnvironmentCouplingAdapter`` -- irrigation genuinely has no
  InterfaceBundle/CouplingContract wiring it into THAT flag, and that
  finding from the first version of this script stands). It is a SEPARATE,
  earlier PR-9 (F1) retrofit: ``global_config.coupling.context_contract``,
  a fail-loud guard on ``IrrigationEnvironment.get_agent_context()`` (the
  per-agent physical-state handoff into the LLM prompt), config-switchable
  via ``--config-dir`` exactly the way ``retry_feedback_mode`` was for the
  placebo variant. This script's ORIGINAL version incorrectly concluded no
  config-only irrigation coupling arm was possible at all -- that
  conclusion was WRONG for THIS mechanism (right only for the unrelated
  v0.6 adapter flag). The stale first-version outputs are preserved at
  ``out/_pending/r39_coupling_contract_runs_STALE_pre-correction.{csv,md}``
  for the record, not deleted.

  Construction-line proof (quoted verbatim,
  examples/irrigation_abm/run_experiment.py:640-646):
    coupling_contract_active = AgentTypeConfig.load(
        str(agent_config_path)
    ).get_coupling_context_contract()
    if coupling_contract_active:
        print("[coupling] context_contract=True — get_agent_context() fails loud on a missing field")
    config = WaterSystemConfig(seed=seed)
    env = IrrigationEnvironment(config, coupling_contract_active=coupling_contract_active)
  where ``agent_config_path = config_dir / "agent_types.yaml"`` and
  ``config_dir`` resolves from ``--config-dir`` when passed (line 482).
  ``run_ungoverned_experiment.py`` has the IDENTICAL construction line and
  flag read (added for exactly this reason: a flag protecting only the
  governed arm would confound a governed-vs-ungoverned comparison) BUT
  ``config_dir = base / "config"`` is HARD-CODED there with NO
  ``--config-dir`` override registered (confirmed via `--help`, 2026-09-23)
  -- so the ungoverned arm is DROPPED from this experiment; only strict
  runs.

RUN LAYOUT
  ctxcontract run (LAUNCHED by
  launchers/extras2_2026-09-23/01_irrigation_coupling.bat, strict seed 42
  ONLY): examples/irrigation_abm/results/
  strict_42yr_gemma3_4b_83fa97e1_ctxcontract_seed42. Comparators, ALREADY
  COMPLETE: the exact-seed match strict_42yr_gemma3_4b_faf1bb12_seed42, plus
  the 5-seed band from strict_42yr_gemma3_4b_faf1bb12_seed{42..46}.

PART 1 -- comparator band (faf1bb12 strict, 5 seeds 42-46)
  Same construction as this script's first version's Part 1, narrowed to
  the strict arm only (ungoverned dropped, see QUESTION above): mean and
  sample sd (``_common.py::mean``/``sd``, canonical ``_loader.py::mean``/
  ``sd``, n-1) computed LIVE from the 5 already-complete faf1bb12 strict
  seeds, via ``R25._irr_llm_metrics()``. Band = mean +/- 2*sd.

PART 2 -- ctxcontract-run completeness + contract-check
  Completeness: same 4-gate ``_irr_run_completeness`` as before. If
  complete, reads run_integrity.json's TOP-LEVEL fields (confirmed by
  reading broker/core/experiment_runner.py:1050-1093 and
  broker/core/run_integrity.py:653-654 ``audit.update(extra)`` -- the
  ``coupling_retrofit_metadata`` dict IrrigationEnvironment.
  get_coupling_retrofit_metadata() returns is merged FLAT into the same
  ``audit`` dict ``record_run_integrity`` writes, so these are direct
  top-level keys, not nested under a "coupling_retrofit_metadata" key --
  confirmed for the analogous ``coupling_adapter``/``sim_engine_class``
  pair on cat_model's own run_integrity.json, 2026-09-22):
    coupling_contract_active (bool)
    coupling_contract_fields (dict: field name -> "presence+range" or
      "presence+type", 15 entries when populated)
    coupling_contract_uncovered_keys (list: ["agent_id", "shortage_tier",
      "year"])
    coupling_guard_calls (int -- count of calls that PASSED)
  NO SEPARATE VIOLATION-COUNT FIELD EXISTS (grepped
  examples/irrigation_abm/irrigation_coupling.py and
  broker/coupling/adapter.py, 2026-09-23): ``guard_agent_context_sources``
  RAISES ``CouplingViolation`` (the same exception class the v0.6 adapter
  uses, reused here) naming every failing field, it does not count
  violations. A violation is therefore evidenced by ABSENCE of a clean
  completion (the run crashes, or run_integrity.json's integrity_ok is not
  True), never by a nonzero counter -- this script treats
  ``integrity_ok is True`` as "no violation occurred", named explicitly
  rather than silently assumed.

PART 3 -- outcome check: exact-seed match + band check
  Per metric: (a) the ctxcontract run's value side by side with
  strict_42yr_gemma3_4b_faf1bb12_seed42's own value (informational --
  real-LLM gemma3:4b generation is not guaranteed byte-identical run to
  run even at the same seed, so an exact match is not required, only
  reported); (b) whether the ctxcontract value falls inside Part 1's
  5-seed band (the actual pass/fail evidence, since the band's spread
  captures real seed-to-seed variation the same model/config produces).

DECISION RULE
  "The contract is enforced at runtime without changing behaviour" requires
  ALL of: coupling_contract_active is True; coupling_guard_calls > 0;
  coupling_contract_fields has exactly 15 entries and
  coupling_contract_uncovered_keys == ["agent_id", "shortage_tier", "year"]
  (i.e. the guard covers what the source code declares -- a drift here
  would mean this script's own assumptions are stale); integrity_ok is
  True (no violation); and every one of the 5 canonical metrics (IBR
  headline, EHE pooled executed, EHE pooled proposal, Mead min ft,
  shortage years) falls inside its Part-1 band. Any single failure -> the
  plain-read section names exactly which check failed and its actual
  value.

COMPLETENESS GATE
  Same 4-gate ``_irr_run_completeness`` this script's first version used.

OUTPUTS
  out/r39_coupling_contract_runs.csv -- row_type in {comparator_metric,
    band, skipped, contract_check, outcome_check}.
  out/r39_coupling_contract_runs.md -- GENERATED by render_md() directly
    from that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r39_coupling_contract_runs.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402  READ-ONLY: _irr_llm_metrics.

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
COMPARATOR_SEEDS = ["42", "43", "44", "45", "46"]
CTXCONTRACT_SEED = "42"
ARM = "strict"  # ungoverned dropped -- run_ungoverned_experiment.py has no --config-dir
METRICS = ["ibr_headline", "ehe_pooled", "ehe_pooled_proposal", "mead_min_ft", "shortage_years"]
METRIC_LABELS = {
    "ibr_headline": "IBR headline (%)",
    "ehe_pooled": "EHE pooled executed",
    "ehe_pooled_proposal": "EHE pooled proposal",
    "mead_min_ft": "Mead min (ft)",
    "shortage_years": "Shortage years",
}
EXPECTED_UNCOVERED_KEYS = ["agent_id", "shortage_tier", "year"]
EXPECTED_FIELD_COUNT = 15


def _comparator_dir(seed: str) -> str:
    return os.path.join(IRR_RESULTS, f"{ARM}_42yr_gemma3_4b_faf1bb12_seed{seed}")


def _ctxcontract_dir() -> str:
    return os.path.join(IRR_RESULTS, f"{ARM}_42yr_gemma3_4b_83fa97e1_ctxcontract_seed{CTXCONTRACT_SEED}")


# =============================================================================
# completeness (identical 4-gate contract to r35's own _irr_run_completeness)
# =============================================================================
def _irr_run_completeness(run_dir: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist yet"
    if not os.path.isfile(os.path.join(run_dir, C.L.AUDIT_LOG)):
        return "skipped", f"{C.L.AUDIT_LOG} missing (run in progress)"
    if not os.path.isfile(os.path.join(run_dir, C.L.SIM_LOG)):
        return "skipped", f"{C.L.SIM_LOG} missing (run in progress)"
    ri_path = os.path.join(run_dir, "run_integrity.json")
    if not os.path.isfile(ri_path):
        return "skipped", "run_integrity.json missing (run in progress)"
    return "ok", None


# =============================================================================
# Part 1 -- comparator band from the 5 faf1bb12 strict seeds
# =============================================================================
def _part1(rows: list) -> dict:
    """Returns {metric: (mean, sd, lo, hi)}."""
    band: dict = {}
    per_metric = {m: [] for m in METRICS}
    for seed in COMPARATOR_SEEDS:
        run_dir = _comparator_dir(seed)
        status, reason = _irr_run_completeness(run_dir)
        if status == "skipped":
            raise PrepError(f"{run_dir}: comparator expected ALREADY COMPLETE, got "
                             f"skipped ({reason}) -- the faf1bb12 corpus this band "
                             f"depends on is not what this script assumes")
        m = R25._irr_llm_metrics(run_dir)
        for metric in METRICS:
            val = float(m[metric])
            per_metric[metric].append(val)
            rows.append({"row_type": "comparator_metric", "metric": metric, "seed": seed,
                         "value": val})
    for metric in METRICS:
        vals = per_metric[metric]
        mn, sdv = C.mean(vals), C.sd(vals)
        lo, hi = mn - 2 * sdv, mn + 2 * sdv
        band[metric] = (mn, sdv, lo, hi)
        degenerate = sdv == 0.0
        rows.append({"row_type": "band", "metric": metric, "n_seeds": len(vals),
                     "mean": mn, "sd": sdv, "band_lo": lo, "band_hi": hi,
                     "degenerate": degenerate})
        print(f"  {METRIC_LABELS[metric]:22s} mean={mn:.4f} sd={sdv:.4f} "
              f"band=({lo:.4f}, {hi:.4f}){' DEGENERATE (sd=0)' if degenerate else ''}")
    return band


# =============================================================================
# Part 2 -- ctxcontract-run completeness + contract-check
# =============================================================================
def _part2(rows: list) -> dict:
    """Returns metrics_dict or None."""
    run_dir = _ctxcontract_dir()
    status, reason = _irr_run_completeness(run_dir)
    if status == "skipped":
        print(f"  PENDING: {reason}")
        rows.append({"row_type": "skipped", "section": "contract_check", "reason": reason})
        return None
    ri_path = os.path.join(run_dir, "run_integrity.json")
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    contract_active = ri.get("coupling_contract_active") is True
    contract_fields = ri.get("coupling_contract_fields")
    uncovered_keys = ri.get("coupling_contract_uncovered_keys")
    guard_calls = ri.get("coupling_guard_calls")
    integrity_ok = ri.get("integrity_ok") is True
    field_count = len(contract_fields) if isinstance(contract_fields, dict) else None
    fields_as_expected = (field_count == EXPECTED_FIELD_COUNT
                          and isinstance(uncovered_keys, list)
                          and sorted(uncovered_keys) == sorted(EXPECTED_UNCOVERED_KEYS))
    rows.append({"row_type": "contract_check", "contract_active": contract_active,
                 "field_count": field_count, "uncovered_keys": uncovered_keys,
                 "guard_calls": guard_calls, "integrity_ok": integrity_ok,
                 "fields_as_expected": fields_as_expected})
    m = R25._irr_llm_metrics(run_dir)
    return {metric: float(m[metric]) for metric in METRICS}


# =============================================================================
# Part 3 -- outcome check: exact-seed match + band check
# =============================================================================
def _part3(rows: list, band: dict, ctx_vals) -> None:
    if ctx_vals is None:
        for metric in METRICS:
            rows.append({"row_type": "skipped", "section": "outcome_check", "metric": metric,
                         "reason": "ctxcontract run has not landed"})
        return
    same_seed_dir = _comparator_dir(CTXCONTRACT_SEED)
    same_seed_status, same_seed_reason = _irr_run_completeness(same_seed_dir)
    same_seed_vals = (R25._irr_llm_metrics(same_seed_dir) if same_seed_status == "ok" else None)
    for metric in METRICS:
        mn, sdv, lo, hi = band[metric]
        v = ctx_vals[metric]
        degenerate = sdv == 0.0
        if degenerate:
            in_band = (v == mn)
            note = "exact-match PASS" if in_band else "degenerate (zero-width band)"
        else:
            in_band = lo <= v <= hi
            note = "PASS" if in_band else ("above band" if v > hi else "below band")
        same_seed_val = (float(same_seed_vals[metric]) if same_seed_vals is not None else None)
        rows.append({"row_type": "outcome_check", "metric": metric, "value": v,
                     "band_lo": lo, "band_hi": hi, "degenerate": degenerate,
                     "in_band": in_band, "note": note, "same_seed_value": same_seed_val})


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "metric", "seed", "value", "n_seeds", "mean", "sd",
    "band_lo", "band_hi", "degenerate", "contract_active", "field_count", "uncovered_keys",
    "guard_calls", "integrity_ok", "fields_as_expected", "in_band", "note",
    "same_seed_value", "reason",
]


def main() -> int:
    C.banner("R39  Irrigation coupling-CONTEXT-CONTRACT run (strict seed 42, ungoverned dropped)")
    rows: list = []

    print("\n-- Part 1: comparator band from the 5 faf1bb12 strict seeds (42-46) --")
    band = _part1(rows)

    print("\n-- Part 2: ctxcontract-run completeness + contract-check --")
    ctx_vals = _part2(rows)

    print("\n-- Part 3: outcome check (exact-seed match + band check) --")
    _part3(rows, band, ctx_vals)

    md_text = render_md(rows)

    csv_final = "r39_coupling_contract_runs.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r39_coupling_contract_runs.md")
    md_tmp = md_final + ".tmp"

    csv_tmp_path = C.write_csv(csv_tmp, FIELDNAMES, rows)
    with open(md_tmp, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    os.replace(csv_tmp_path, os.path.join(C.OUT, csv_final))
    os.replace(md_tmp, md_final)
    print(f"\n  wrote {os.path.relpath(os.path.join(C.OUT, csv_final), C.REPO).replace(chr(92), '/')}"
          f"  ({len(rows)} rows)")
    print(f"  wrote {os.path.relpath(md_final, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")
    return 0


# =============================================================================
# .md rendering
# =============================================================================
def _cp(x) -> float:
    return float(C.fmt(x))


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R39 -- irrigation coupling-CONTEXT-CONTRACT run (strict seed 42)")
    lines.append("")
    lines.append(
        "**CORRECTED 2026-09-23**: this script's FIRST version wrongly concluded no "
        "config-only irrigation coupling arm was possible -- true only for the unrelated "
        "v0.6 `broker/coupling/` two-layer adapter flag, not for irrigation's own PR-9 (F1) "
        "`global_config.coupling.context_contract` guard, which IS config-switchable via "
        "`--config-dir`. Stale first-version outputs preserved at "
        "`out/_pending/r39_coupling_contract_runs_STALE_pre-correction.{csv,md}`, not "
        "deleted. The ungoverned arm is dropped from this experiment: "
        "`run_ungoverned_experiment.py` reads the same flag but has no `--config-dir` "
        "override to ever reach this variant (confirmed via `--help`, 2026-09-23)."
    )
    lines.append("")
    lines.append("Source: `r39_coupling_contract_runs.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV.")
    lines.append("")

    # ---- Part 1: comparator band -----------------------------------------------
    lines.append("## Part 1 -- comparator band (faf1bb12 strict, 5 seeds 42-46)")
    lines.append("")
    lines.append("| metric | mean | sample sd | band lo | band hi | degenerate |")
    lines.append("|---|---|---|---|---|---|")
    for metric in METRICS:
        recs = _find(rows, "band", metric=metric)
        if not recs:
            lines.append(f"| {METRIC_LABELS[metric]} | PENDING | -- | -- | -- | -- |")
            continue
        r = recs[0]
        lines.append(f"| {METRIC_LABELS[metric]} | {_cp(r['mean']):.4f} | "
                     f"{_cp(r['sd']):.4f} | {_cp(r['band_lo']):.4f} | "
                     f"{_cp(r['band_hi']):.4f} | {r['degenerate']} |")
    lines.append("")

    # ---- Part 2: contract-check ---------------------------------------------
    lines.append("## Part 2 -- ctxcontract-run completeness + contract-check "
                 "(run_integrity.json, top-level fields)")
    lines.append("")
    lines.append("| run landed | contract_active | guard_calls | field_count (expect 15) | "
                 "uncovered_keys matches expected | integrity_ok (no violation) |")
    lines.append("|---|---|---|---|---|---|")
    recs = _find(rows, "contract_check")
    if not recs:
        pend = _find(rows, "skipped", section="contract_check")
        reason = pend[0]["reason"] if pend else "no data"
        lines.append(f"| PENDING ({reason}) | -- | -- | -- | -- | -- |")
    else:
        r = recs[0]
        lines.append(f"| yes | {r['contract_active']} | {r['guard_calls']} | "
                     f"{r['field_count']} | {r['fields_as_expected']} | {r['integrity_ok']} |")
    lines.append("")

    # ---- Part 3: outcome check ---------------------------------------------
    lines.append("## Part 3 -- outcome check: exact-seed match + band check")
    lines.append("")
    lines.append("| metric | ctxcontract value | faf1bb12 seed42 value (informational) | "
                 "band | result |")
    lines.append("|---|---|---|---|---|")
    for metric in METRICS:
        recs = _find(rows, "outcome_check", metric=metric)
        if not recs:
            lines.append(f"| {METRIC_LABELS[metric]} | PENDING | -- | -- | PENDING |")
            continue
        r = recs[0]
        band_cell = f"[{_cp(r['band_lo']):.4f}, {_cp(r['band_hi']):.4f}]"
        same_seed_cell = (f"{_cp(r['same_seed_value']):.4f}" if r["same_seed_value"] is not None
                          else "n.a.")
        lines.append(f"| {METRIC_LABELS[metric]} | {_cp(r['value']):.4f} | {same_seed_cell} | "
                     f"{band_cell} | {r['note']} |")
    lines.append("")

    # ---- Plain read -----------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    contract_recs = _find(rows, "contract_check")
    if not contract_recs:
        sentences.append(
            "The ctxcontract run (strict, seed 42) has not landed. Part 1's faf1bb12 "
            "comparator band (already complete, 5 seeds) is fully populated now; Parts 2/3 "
            "populate automatically, no code change needed, once "
            "`launchers/extras2_2026-09-23/01_irrigation_coupling.bat` completes it."
        )
    else:
        r = contract_recs[0]
        checks = [
            ("contract_active is True", r["contract_active"] is True),
            ("guard_calls > 0", isinstance(r["guard_calls"], int) and r["guard_calls"] > 0),
            ("fields_as_expected (15 fields, uncovered_keys matches)", r["fields_as_expected"]),
            ("integrity_ok is True (no violation)", r["integrity_ok"] is True),
        ]
        outcome_recs = _find(rows, "outcome_check")
        band_fails = [o for o in outcome_recs if o["in_band"] is False]
        all_pass = all(ok for _label, ok in checks) and not band_fails
        if all_pass:
            sentences.append(
                "PASS: coupling_contract_active=True, "
                f"coupling_guard_calls={r['guard_calls']}, the 15-field/3-uncovered-key "
                "shape matches this script's static-code assumptions, integrity_ok=True "
                "(no CouplingViolation), and all 5 metrics land inside the faf1bb12 "
                "5-seed band -- the context contract is enforced at runtime without "
                "changing behaviour."
            )
        else:
            for label, ok in checks:
                if not ok:
                    sentences.append(f"FAIL: {label} -- got "
                                     f"{r.get(label.split(' ')[0], '(see Part 2 table)')!r}.")
            for o in band_fails:
                sentences.append(f"FAIL: {METRIC_LABELS.get(o['metric'], o['metric'])} = "
                                 f"{_cp(o['value']):.4f} is {o['note']} "
                                 f"[{_cp(o['band_lo']):.4f}, {_cp(o['band_hi']):.4f}].")
    for s in sentences[:6]:
        lines.append(s)
        lines.append("")

    lines.append("## Method")
    lines.append("")
    lines.append(
        "All 5 metrics are `r25_table1_regen.py::_irr_llm_metrics()`, imported, not "
        "re-derived. Band = mean +/- 2*sample-sd over the 5 already-complete faf1bb12 "
        "strict seeds (42-46), sd via the canonical `_loader.py::mean`/`sd` (n-1). "
        "`coupling_contract_active` / `coupling_contract_fields` / "
        "`coupling_contract_uncovered_keys` / `coupling_guard_calls` are read as TOP-LEVEL "
        "`run_integrity.json` fields -- confirmed by reading "
        "`broker/core/experiment_runner.py:1050-1093` (the `coupling_retrofit_metadata` "
        "dict `IrrigationEnvironment.get_coupling_retrofit_metadata()` returns is merged "
        "into `refl_kwargs['extra']`) and `broker/core/run_integrity.py:653-654` "
        "(`audit.update(extra)` -- a flat merge, not a nested key), the same mechanism "
        "confirmed for the analogous `coupling_adapter`/`sim_engine_class` pair on "
        "`examples/cat_model/results/run_integrity.json`. There is no separate "
        "violation-COUNT field anywhere in this codebase (grepped "
        "`examples/irrigation_abm/irrigation_coupling.py` and "
        "`broker/coupling/adapter.py`, 2026-09-23): `guard_agent_context_sources` RAISES "
        "`CouplingViolation`, it does not count -- `integrity_ok is True` is this script's "
        "explicit, named proxy for \"no violation occurred\", not an assumption. The "
        "exact-seed comparison (Part 3) is informational only, since real-LLM gemma3:4b "
        "generation is not guaranteed byte-identical run to run at the same seed; the band "
        "check is the actual pass/fail evidence."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
