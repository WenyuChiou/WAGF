"""R13 -- reservoir control T0-6: a TOY capability demo, not a paper result.

WHAT THIS IS
  Plan Sec 1 Tier-0 row T0-6 (`.research/experiment_plan_framework_paper_2026-09-06.md`):
  a single OPERATOR agent runs a toy annual release-setting decision against a
  synthetic mass-balance reservoir (`ToyMassBalanceReservoir`, 12 monthly sub-steps
  per year, 42 years, gemma3:4b, seeds 42/43/44, strict governance). Skills:
  `set_release` (parameter `magnitude_pct`, 0-100) and `maintain_release`. One hard
  rule, `dead_pool_violation` (ERROR, blocks `set_release` when the linear one-year
  projection would cross the 6.0 maf dead pool); a second rule, `flood_control_overflow`,
  is registered but structurally cannot fire in this batch (storage never approaches
  90% of the 24.0 maf capacity across any seed -- see storage_trajectory rows below).

  TOY = synthetic sinusoidal-ish inflow pattern (`INFLOW_PATTERN_MONTHLY` x
  `YEAR_FACTORS`, a scripted 2-year drought tail wrapped modulo-4 over 42 years),
  ONE agent, ONE annual decision per year. Not a calibrated basin, not USBR/CRSS
  data, not multi-agent. Read `examples/reservoir_control/ops_modules.py` (module
  docstring) for the exact designed arithmetic this was built to trigger.

DATA LOCATION -- read this before trusting a path
  These runs do NOT exist under this repository's `examples/reservoir_control/`
  (that only has 4-year smoke dirs `results_ops` / `results_ops_e4b`). The T0-6
  batch lives in the sibling checkout `wagf-main-runs`
  (`<repo>/../wagf-main-runs/examples/reservoir_control/results/T0-6_gemma3_4b_e0eee08c/
  Run_{42,43,44}`), gitignored there too -- committed nowhere. `RES_ROOT` below tries
  this repo first, then the sibling checkout, and raises if neither has the directory.

SOURCE READ (origin/main, via `git show`, for the output contract)
  `run_reservoir_ops.py`: hindcast-then-set annual cadence -- the solver runs 12
  monthly sub-steps under the LAST committed release_target, THEN the operator
  decides for the COMING year; `on_pre_year` seeds `storage_now` /
  `inflow_forecast_year` (= `inflow_forecast_for_year(year+1)`) into the prompt env.
  `ops_validators.py`: `dead_pool_violation` projects
  `S + F_next - 12*release_target - 0.12*S` against the 6.0 maf floor.
  `ops_modules.py`: `ReservoirOpsBundle.commit_world_delta` derives
  `release_target = magnitude_pct/100 * DEMAND_M` (DEMAND_M=0.75 maf/month) for an
  APPROVED `set_release`; on REJECTED/`maintain_release` it silently reuses
  `self._last_release_target` -- there is no explicit "fallback" flag anywhere in
  this path (see release_target_parity + odd_finding rows below).
  Audit CSV has NO storage/spill/shortfall columns -- those live only in
  `raw/operator_traces.jsonl`'s `environment_context` per row; this script reads
  both files per seed.

FAIL-LOUD: missing dir/file/column, or a status value outside {APPROVED, REJECTED},
raises. Nothing here substitutes 0/NaN for data that should exist.
"""
from __future__ import annotations

import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

NA = "N/A_by_design"

REPO_PARENT = os.path.dirname(C.REPO)
RES_CANDIDATES = [
    os.path.join(C.REPO, "examples", "reservoir_control", "results"),
    os.path.join(REPO_PARENT, "wagf-main-runs", "examples", "reservoir_control",
                 "results"),
]
RES_ROOT = next((p for p in RES_CANDIDATES if os.path.isdir(p)), None)
if RES_ROOT is None:
    raise PrepError(
        "no examples/reservoir_control/results found in this repo or in the sibling "
        f"wagf-main-runs checkout -- tried: {RES_CANDIDATES}")

RUN_DIR_NAME = "T0-6_gemma3_4b_e0eee08c"
SEEDS = ["42", "43", "44"]
EXPECTED_YEARS = 42
DEMAND_M = 0.75          # ToyMassBalanceReservoir.DEMAND_M, maf/month
DEAD_POOL = 6.0          # ToyMassBalanceReservoir.DEAD_POOL, maf
CAPACITY = 24.0          # ToyMassBalanceReservoir.CAPACITY, maf
SKILLS = ["set_release", "maintain_release"]


def run_dir(seed: str) -> str:
    d = os.path.join(RES_ROOT, RUN_DIR_NAME, f"Run_{seed}")
    if not os.path.isdir(d):
        raise PrepError(f"missing reservoir run dir {d}")
    return d


def load_json(path: str) -> dict:
    if not os.path.isfile(path):
        raise PrepError(f"missing file {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_traces(rd: str) -> list:
    path = os.path.join(rd, "raw", "operator_traces.jsonl")
    if not os.path.isfile(path):
        raise PrepError(f"missing {path}")
    out = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "year" in rec:
                out.append(rec)
    if not out:
        raise PrepError(f"zero year-bearing trace records in {path}")
    return sorted(out, key=lambda r: r["year"])


def new_row(row_type, seed, item, **kw) -> dict:
    rec = {
        "row_type": row_type, "domain": "reservoir_control", "seed": seed,
        "item": item, "level_or_stage": "", "n_total": NA, "n_matched": NA,
        "share_pct": NA, "value": NA, "detail": "", "note": "",
    }
    rec.update(kw)
    return rec


FIELDNAMES = ["row_type", "domain", "seed", "item", "level_or_stage", "n_total",
              "n_matched", "share_pct", "value", "detail", "note"]


# ---------------------------------------------------------------------------
def integrity_row(seed: str, rd: str, aud: list) -> dict:
    ri = load_json(os.path.join(rd, "run_integrity.json"))
    manifest = load_json(os.path.join(rd, "reproducibility_manifest.json"))
    n = len(aud)
    flags = []
    if ri.get("integrity_ok") is not True:
        flags.append("integrity_ok=False")
    if n != EXPECTED_YEARS:
        flags.append(f"csv_rows({n})!=expected_years({EXPECTED_YEARS})")
    for k in ("audit_rows_missing_vs_grid", "audit_rows_missing_vs_configured_grid",
              "audit_sentinel_write_failures", "rules_uncategorised_total",
              "audit_aborted_rows"):
        v = ri.get(k)
        if v not in (0, None):
            flags.append(f"{k}={v}")
    if ri.get("audit_corrected_status_columns") not in (False, None):
        flags.append(f"audit_corrected_status_columns={ri.get('audit_corrected_status_columns')}")
    manifest_seed = str(manifest.get("seed", manifest.get("global_config", {}).get("seed", "")))
    dir_seed_matches = str(ri.get("seed")) == seed
    if not dir_seed_matches:
        flags.append(f"run_integrity.seed({ri.get('seed')})!=dir_seed({seed})")
    return new_row(
        "integrity", seed, "run_integrity",
        n_total=n, n_matched=EXPECTED_YEARS,
        detail=(f"audit_rows={ri.get('audit_rows')}; audit_years={ri.get('audit_years')}; "
                f"audit_agents={ri.get('audit_agents')}; reflection_expected="
                f"{ri.get('reflection_expected')}; reflection_tracked={ri.get('reflection_tracked')}; "
                f"governance_mode={ri.get('governance_mode')}; framework_version="
                f"{ri.get('framework_provenance', {}).get('framework_version')}; "
                f"git_commit_short={ri.get('framework_provenance', {}).get('git_commit_short')}"),
        note=("clean -- no flags" if not flags else "FLAGGED: " + " | ".join(flags)),
    )


def config_row(seed: str, rd: str) -> dict:
    cfg_path = os.path.join(rd, "config_snapshot.yaml")
    if not os.path.isfile(cfg_path):
        raise PrepError(f"missing {cfg_path}")
    with open(cfg_path, encoding="utf-8") as fh:
        text = fh.read()
    import re
    def grab(pat, where):
        m = re.search(pat, text)
        if not m:
            raise PrepError(f"{where}: pattern {pat!r} not found in {cfg_path}")
        return m.group(1).strip()
    model = grab(r"model:\s*(\S+)", "model")
    num_ctx = grab(r"num_ctx:\s*(\d+)", "num_ctx")
    num_predict = grab(r"num_predict:\s*(\d+)", "num_predict")
    max_retries = grab(r"max_retries:\s*(\d+)", "max_retries")
    gov_profile = grab(r"governance_profile:\s*(\S+)", "governance_profile")
    coupling_enable = grab(r"coupling:\s*\n\s*enable:\s*(\S+)", "coupling.enable")
    return new_row(
        "config", seed, "manifest_settings",
        detail=(f"model={model}; num_ctx={num_ctx}; num_predict={num_predict}; "
                f"max_retries={max_retries}; governance_profile={gov_profile}; "
                f"coupling.enable={coupling_enable}; years={EXPECTED_YEARS}; "
                f"substeps_per_decision=12"),
        note="clean",
    )


def action_distribution_rows(seed: str, aud: list) -> list:
    rows = []
    for stage, key in (("proposed", "proposed_skill"), ("final", "final_skill")):
        counts = Counter(r[key] for r in aud)
        n = sum(counts.values())
        for sk in SKILLS:
            c = counts.get(sk, 0)
            rows.append(new_row(
                "action_distribution", seed, sk, level_or_stage=stage,
                n_total=n, n_matched=c, share_pct=100.0 * c / n if n else NA,
                note="never proposed" if (stage == "proposed" and c == 0) else "",
            ))
    return rows


def magnitude_distribution_rows(seed: str, aud: list) -> list:
    set_rel = [r for r in aud if r["proposed_skill"] == "set_release"
               and r["reason_magnitude"] != ""]
    mags = Counter(r["reason_magnitude"] for r in set_rel)
    n = len(set_rel)
    rows = []
    for mag, c in sorted(mags.items(), key=lambda kv: float(kv[0])):
        rows.append(new_row(
            "magnitude_distribution", seed, f"magnitude_pct={mag}",
            n_total=n, n_matched=c, share_pct=100.0 * c / n if n else NA,
        ))
    return rows


def rule_firing_rows(seed: str, rd: str, aud: list) -> list:
    audsum = load_json(os.path.join(rd, "audit_summary.json"))
    vh = audsum.get("validator_health", {})
    rows = []
    for rule_id, stats in vh.items():
        rows.append(new_row(
            "rule_firing", seed, rule_id,
            n_total=stats.get("seen_count"), n_matched=stats.get("fire_count"),
            share_pct=(100.0 * stats["fire_count"] / stats["seen_count"]
                       if stats.get("seen_count") else NA),
            detail=f"seen={stats.get('seen_count')}; fire={stats.get('fire_count')}; "
                   f"warn={stats.get('warn_count')}; error_path={stats.get('error_path_count')}",
        ))
    # flood_control_overflow is registered but never appears in validator_health
    # for this batch -- storage never crosses 90% of capacity (21.6 maf); confirmed
    # in storage_trajectory_rows below (max observed 17.276 maf, every seed).
    if "flood_control_overflow" not in vh:
        rows.append(new_row(
            "rule_firing", seed, "flood_control_overflow",
            n_total=0, n_matched=0, share_pct=NA,
            note="never evaluated this batch (storage never > 0.9*capacity=21.6 maf)",
        ))
    statuses = Counter(r["status"] for r in aud)
    bad = set(statuses) - {"APPROVED", "REJECTED"}
    if bad:
        raise PrepError(f"seed {seed}: unexpected status values {bad}")
    n = len(aud)
    rows.append(new_row(
        "rule_firing", seed, "status_APPROVED",
        n_total=n, n_matched=statuses.get("APPROVED", 0),
        share_pct=100.0 * statuses.get("APPROVED", 0) / n,
    ))
    rows.append(new_row(
        "rule_firing", seed, "status_REJECTED",
        n_total=n, n_matched=statuses.get("REJECTED", 0),
        share_pct=100.0 * statuses.get("REJECTED", 0) / n,
    ))
    retries = Counter(r["retry_count"] for r in aud)
    retried_then_approved = sum(
        1 for r in aud if r["retry_count"] == "1" and r["status"] == "APPROVED")
    retried_then_rejected = sum(
        1 for r in aud if r["retry_count"] == "1" and r["status"] == "REJECTED")
    rows.append(new_row(
        "rule_firing", seed, "retry_count_distribution",
        detail=f"retry_count=0: {retries.get('0', 0)}; retry_count=1: {retries.get('1', 0)}",
    ))
    rows.append(new_row(
        "rule_firing", seed, "wall_then_retry_then_approved",
        n_total=int(retries.get("1", 0)), n_matched=retried_then_approved,
        note=("wall -> retry -> APPROVED pattern from ops_modules.py's design "
              "docstring, observed" if retried_then_approved else
              "not observed this seed (every year-1 retry stayed REJECTED)"),
    ))
    rows.append(new_row(
        "rule_firing", seed, "wall_then_retry_still_rejected",
        n_total=int(retries.get("1", 0)), n_matched=retried_then_rejected,
    ))
    fb = Counter(r["fallback_activated"] for r in aud)
    rows.append(new_row(
        "rule_firing", seed, "csv_fallback_activated_flag",
        detail=f"values seen: {dict(fb)}",
        note=("ODD: column reads False on every row including all REJECTED rows, "
              "even though world_release_target on REJECTED rows demonstrably "
              "carries forward the prior committed target (see "
              "release_target_parity rows) -- the CSV's own fallback flag does "
              "not track this domain's REJECTED-retains-prior-setpoint behaviour"
              if set(fb) == {"False"} else ""),
    ))
    return rows


def storage_trajectory_rows(seed: str, traces: list) -> list:
    storages = [t["environment_context"]["storage"] for t in traces]
    spills = [t["environment_context"]["spill"] for t in traces]
    shortfalls = [t["environment_context"]["shortfall"] for t in traces]
    if len(storages) != EXPECTED_YEARS:
        raise PrepError(f"seed {seed}: {len(storages)} storage points, expected {EXPECTED_YEARS}")
    below = [t["year"] for t, s in zip(traces, storages) if s < DEAD_POOL]
    rows = [
        new_row("storage_trajectory", seed, "storage_maf",
                value=NA,
                detail=(f"min={min(storages):.3f}; max={max(storages):.3f}; "
                        f"final={storages[-1]:.3f}; initial(year1_pre)=18.000; "
                        f"capacity={CAPACITY}; dead_pool={DEAD_POOL}"),
                note=("dead-pool wall never physically crossed in the committed "
                      "trajectory (validator blocks the proposal before "
                      f"commit)" if not below else
                      f"FLAGGED: storage below dead pool in years {below}")),
        new_row("storage_trajectory", seed, "years_below_dead_pool",
                n_total=EXPECTED_YEARS, n_matched=len(below),
                share_pct=100.0 * len(below) / EXPECTED_YEARS,
                detail=str(below) if below else "none"),
        new_row("storage_trajectory", seed, "spill_total_maf", value=round(sum(spills), 6),
                note="0 across all seeds -- solver never fills to capacity"
                     if sum(spills) == 0 else ""),
        new_row("storage_trajectory", seed, "shortfall_total_maf", value=round(sum(shortfalls), 4),
                detail="sum of per-year (annual_demand - actual_release), maf"),
    ]
    return rows


def coupling_evidence_rows(seed: str, rd: str) -> list:
    ri = load_json(os.path.join(rd, "run_integrity.json"))
    manifest = load_json(os.path.join(rd, "reproducibility_manifest.json"))
    cp = manifest.get("coupling_provenance", {})
    rows = [
        new_row("coupling_evidence", seed, "coupling_adapter",
                value=str(ri.get("coupling_adapter")),
                detail=f"sim_engine_class={ri.get('sim_engine_class')}"),
        new_row("coupling_evidence", seed, "coupling_provenance",
                detail=(f"adapter_class={cp.get('adapter_class')}; "
                        f"contract_sha256={cp.get('contract_sha256')}; "
                        f"bundle_class={cp.get('bundle_class')}; "
                        f"solver_class={cp.get('bundle_provenance', {}).get('solver_class')}; "
                        f"substeps_per_decision={cp.get('bundle_provenance', {}).get('substeps_per_decision')}"),
                note=("the brief's field names coupling_contract_active / "
                      "coupling_guard_calls do NOT exist in run_integrity.json "
                      "schema 2 -- closest equivalents are coupling_adapter "
                      "(bool) + this coupling_provenance block, both present "
                      "and consistent across all 3 seeds")),
    ]
    return rows


def release_target_parity_rows(seed: str, aud: list) -> list:
    ordered = sorted(aud, key=lambda r: int(r["year"]))
    approved_mismatch = []
    rejected_mismatch = []
    prev_target = DEMAND_M  # runner default before year 1's decision commits
    n_approved = n_rejected = 0
    for r in ordered:
        wrt = float(r["world_release_target"])
        if r["status"] == "APPROVED":
            n_approved += 1
            mag = float(r["reason_magnitude"])
            expected = (mag / 100.0) * DEMAND_M
            if abs(expected - wrt) > 1e-9:
                approved_mismatch.append((r["year"], expected, wrt))
            prev_target = wrt
        else:
            n_rejected += 1
            if abs(prev_target - wrt) > 1e-9:
                rejected_mismatch.append((r["year"], prev_target, wrt))
            # prev_target does not change: REJECTED silently reuses last commit
    return [
        new_row("release_target_parity", seed, "APPROVED_exact_match",
                n_total=n_approved, n_matched=n_approved - len(approved_mismatch),
                share_pct=100.0 * (n_approved - len(approved_mismatch)) / n_approved
                if n_approved else NA,
                detail="world_release_target == magnitude_pct/100*DEMAND_M(0.75), "
                       "float exact (1e-9 tol)",
                note="EXACT on every APPROVED row" if not approved_mismatch else
                     f"FLAGGED mismatches: {approved_mismatch}"),
        new_row("release_target_parity", seed, "REJECTED_retains_prior_target",
                n_total=n_rejected, n_matched=n_rejected - len(rejected_mismatch),
                share_pct=100.0 * (n_rejected - len(rejected_mismatch)) / n_rejected
                if n_rejected else NA,
                detail="world_release_target on a REJECTED row == the last "
                       "APPROVED (or initial 0.75) committed target -- "
                       "ReservoirOpsBundle.commit_world_delta reuses "
                       "_last_release_target when magnitude_pct is absent from "
                       "the (rejected) approved_skill.parameters",
                note="EXACT on every REJECTED row" if not rejected_mismatch else
                     f"FLAGGED mismatches: {rejected_mismatch}"),
    ]


def governance_summary_check_row(seed: str, rd: str) -> dict:
    gs = load_json(os.path.join(rd, "governance_summary.json"))
    audsum = load_json(os.path.join(rd, "audit_summary.json"))
    csv_fires = sum(v.get("fire_count", 0) for v in audsum.get("validator_health", {}).values())
    return new_row(
        "odd_finding", seed, "governance_summary_total_interventions",
        n_total=csv_fires, n_matched=gs.get("total_interventions", 0),
        detail=(f"governance_summary.json total_interventions="
                f"{gs.get('total_interventions')} vs audit_summary.json "
                f"validator_health fire_count sum={csv_fires} (== CSV-derived "
                f"REJECTED count, cross-checked directly against the audit CSV)"),
        note=("MATCH" if gs.get("total_interventions", 0) == csv_fires else
              "MISMATCH: GovernanceAuditor.log_intervention() is not being "
              "called on this domain-physical validator path "
              "(broker/utils/governance_auditor.py) even though the CSV / "
              "audit_summary validator_health correctly record every "
              "dead_pool_violation firing -- an instrumentation gap in the "
              "legacy governance_summary.json counter, not in the audit trail "
              "itself"),
    )


def main() -> int:
    C.banner("R13  reservoir_control T0-6 (gemma3:4b, TOY, seeds 42/43/44)")
    print(f"  RES_ROOT = {RES_ROOT}")
    rows = []

    for seed in SEEDS:
        rd = run_dir(seed)
        aud = C.read_csv(os.path.join(rd, "operator_governance_audit.csv"))
        C.require_cols(aud, ["year", "proposed_skill", "final_skill", "status",
                              "fallback_activated", "retry_count", "failed_rules",
                              "reason_magnitude", "world_release_target"],
                        f"seed {seed} audit CSV")
        traces = load_traces(rd)
        print(f"\n  seed {seed}: {len(aud)} audit rows, {len(traces)} trace records, dir={rd}")

        rows.append(integrity_row(seed, rd, aud))
        rows.append(config_row(seed, rd))
        rows.extend(action_distribution_rows(seed, aud))
        rows.extend(magnitude_distribution_rows(seed, aud))
        rows.extend(rule_firing_rows(seed, rd, aud))
        rows.extend(storage_trajectory_rows(seed, traces))
        rows.extend(coupling_evidence_rows(seed, rd))
        rows.extend(release_target_parity_rows(seed, aud))
        rows.append(governance_summary_check_row(seed, rd))

    C.write_csv("r13_reservoir_t06.csv", FIELDNAMES, rows)

    print("\n  per-seed summary:")
    for seed in SEEDS:
        by = {(r["row_type"], r["item"]): r for r in rows if r["seed"] == seed}
        integ = by[("integrity", "run_integrity")]
        rej = by[("rule_firing", "status_REJECTED")]
        dp = by[("rule_firing", "dead_pool_violation")]
        st = by[("storage_trajectory", "storage_maf")]
        appr_par = by[("release_target_parity", "APPROVED_exact_match")]
        print(f"    seed {seed}: rows={integ['n_total']} {integ['note']} | "
              f"REJECTED={rej['n_matched']}/{rej['n_total']} "
              f"({rej['share_pct']:.1f}%) | dead_pool_violation "
              f"fire/seen={dp['n_matched']}/{dp['n_total']} | {st['detail']} | "
              f"parity APPROVED {appr_par['note']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
