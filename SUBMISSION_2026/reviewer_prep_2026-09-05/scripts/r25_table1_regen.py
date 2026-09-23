"""R25 -- paper Table 1, old vs new, across both cases and all governance arms.

CONTEXT (2026-09-17)
  r23/r24 verified the flood single-agent governed and no-validator arms
  regenerate cleanly at faf1bb12. regen_progress_2026-09-15.md did the same
  for irrigation. This script assembles the paper's Table 1 -- one row per
  (case, arm) -- in "old mean +/- sd / new mean +/- sd" form, for BOTH cases
  (irrigation, flood) and, new to this script, the two RULE-BASED baselines
  (irrigation FQL x2 variants, flood rule-based) that have no LLM at all.

SEVEN ROWS
  irrigation governed (strict), irrigation ungoverned,
  irrigation rule-based FQL rebalanced (fql_raw_faf1bb12),
  irrigation rule-based FQL matched/no-rebalance (fql_raw_norebalance_faf1bb12),
  flood governed (strict), flood no-validator, flood rule-based
  (rulebased_5seed_faf1bb12).

COLUMNS
  n runs | IBR headline | EHE pooled | domain outcome | rejection rate % |
  retry rate % | LLM failures | governance fallback % | wall h per run.
  Cell = "old mean +/- sd / new mean +/- sd" (ddof=1). "n.a." where the arm
  has no such quantity (rule-based has no LLM audit trail at all -- no
  rejection/retry/LLM-failure/fallback columns exist for it, checked: FQL
  and flood-rulebased run dirs contain only simulation_log.csv +
  LAUNCH_COMMAND.txt, no *_governance_audit.csv). "no old record" where the
  concept applies but no old per-seed value could be found (never invented
  or back-solved).

METRIC DEFINITIONS, PER CASE
  Irrigation (both LLM arms AND both FQL variants read `yearly_decision` +
  `wsa_label` from simulation_log.csv, the SAME two column names, so the
  same accessors apply verbatim):
    IBR headline = proposal-level conditional high-WSA increase rate,
      `_loader.ibr(simulation_log_rows)` (imported as `C.L.ibr`; canonical
      per CLAUDE.md/regen_progress -- old mean 36.05 for strict, matches
      r14_advise_arm.csv's `ibr_pct_proposal`).
    EHE pooled = EXECUTED-distribution pooled, `C.normalized_entropy` over
      the 5-skill AUDIT-executed-remap distribution (`C.irr_executed`,
      k=5) -- matches r14's `ehe_pooled_executed`. FQL HAS NO 5-skill
      space (its `yearly_decision` vocabulary is only 3 categories:
      increase_demand/maintain_demand/decrease_demand -- Hung & Yang 2021's
      binary+block model). Calling the LLM's `L.ibr`/`INCREASE` set
      (`{increase_large, increase_small}`) on FQL rows would silently
      return 0% for every row (FQL's strings never match), a real
      silent-wrong-answer risk this script does not take. A SECOND,
      subtler trap: FQL's `yearly_decision` column is already the
      POST-block EXECUTED outcome (`fql_blocked=True` replaces a blocked
      raw proposal with `maintain_demand` before it is written there) --
      using it for the PROPOSAL-level IBR headline would report ~0%
      instead of FQL's real proposal-level rate (verified on seed42: 66/78
      high-WSA rows have raw proposal `increase_demand`, 84.6%, but only
      1/78 SURVIVES as executed `increase_demand`/`decrease_demand`
      because 71/78 get `fql_blocked`). FQL's IBR headline therefore reads
      the RAW pre-block column `fql_raw_skill` (`FQL_INCREASE =
      {"increase_demand"}`), the true proposal-level analogue, while EHE
      pooled reads `yearly_decision` (the executed-level analogue, k=3 --
      flagged in the .md as NOT numerically comparable to the LLM arms'
      k=5 EHE), per the explicit warning already on record in
      `examples/irrigation_abm/analysis/fql_comparison_metrics.py`
      ("computing EHE for FQL is not meaningful" -- this script computes it
      anyway, since the task asks for the column on every row, but reports
      the k-mismatch loudly rather than silently presenting a comparable-
      looking number).
    Domain outcome = Lake Mead minimum elevation (ft) + shortage years
      (< 1075 ft), identical definition and threshold for LLM and FQL rows
      (`lake_mead_level` column, present in both schemas).

  Flood (governed/no-validator via r23_flood_strict_regen.py, imported):
    IBR headline = unconditional executed IBR (`ibr_uncond_final` --
      proven proposal=final=executed in r23/r24).
    EHE pooled = `ehe_pooled_simlog_published` (r23's definition).
    Domain outcome = final-year (max audit `year`) share of AUDIT rows
      whose EXECUTED action (`C.flood_executed`) is NOT `do_nothing` --
      i.e. any active protection in the last simulated year. Matches the
      method `r2_flood_trajectories.csv` already used for its year-10
      `share_do_nothing` column (100 - that share), which is how this
      script reads the OLD per-position values for governed/ungoverned
      (their raw audit CSVs no longer exist post-2026-09-15).
    Flood RULE-BASED has no audit CSV and no threat-appraisal
    (`construct_TP_LABEL`) column at all in its simulation_log.csv -- IBR
    is therefore UNDEFINED for this row (R1/R3/R4 all condition on TP) and
    reported "n.a. (no threat-appraisal construct)", not a fabricated
    number. Its domain outcome instead uses the simulation_log's own
    boolean `elevated`/`has_insurance`/`relocated` columns at the final
    year (all 100 agents, not audit-scoped) -- a DIFFERENT method than the
    audit-based one used for governed/ungoverned, flagged as such, not
    silently treated as identical. Its EHE pooled uses
    `C.flood_normalize_action` on the `decision` column as published; that
    function's own documented tail behaviour silently maps any unmapped
    string to `do_nothing` -- the rule-based baseline's combined choice
    "Both Flood Insurance and House Elevation" is exactly such a string
    (never added to `_FLOOD_ACTION_MAP`), so this script also reports the
    `unmapped_pct` share plainly rather than let it hide inside a normal-
    looking `do_nothing` count.

RULE-BASED HAS NO OLD/NEW LLM COLUMNS BY CONSTRUCTION, BUT DOES HAVE AN OLD
CORPUS: `fql_raw_e75e390c` / `fql_raw_norebalance_e75e390c` /
`rulebased_5seed_e75e390c` are an OLDER git-commit snapshot of the SAME
deterministic baselines, still on disk (verified: identical simulation_log
column headers and row counts to the faf1bb12 versions) -- read directly
as the "old" side for the 3 rule-based rows, the same way r23/r24 read old
LLM values from `out/*.csv` (the raw old LLM dirs no longer exist; the raw
old rule-based dirs do, because rule-based has no LLM audit trail to
corrupt). FQL has seeds 42-51 (10 total) on both commits; this script uses
only 42-46 (n=5) to match every other row's n and keep old vs new and the
per-row `n runs` column comparable across the whole table.

OLD PER-SEED SOURCES
  Irrigation governed/ungoverned: `out/r14_advise_arm.csv`
    (arm=strict / arm=no_validator), columns `ibr_pct_proposal`,
    `ehe_pooled_executed`, `mead_min_ft`, `shortage_years`,
    `rejected_to_fallback_pct` (= this script's rejection_rate_pct: ALL
    REJECTED*-status rows / n -- r14's own name for the same quantity,
    confirmed by reading `status_shares()` in r14_advise_arm.py). No old
    per-seed record exists anywhere for retry_rate_pct (my definition:
    rows with retry_count>0, distinct from r14's retry-scoped-to-APPROVED
    `approved_after_retry_pct`), LLM-failure count, the REJECTED_FALLBACK-
    only governance-fallback-%, or wall hours -- reported "no old record".
  Irrigation FQL (both variants): read directly from the e75e390c dirs
    (see above), seeds 42-46.
  Flood governed/no-validator: r23_flood_strict_regen.py's own old-value
    loaders (`_load_old_ibr`, `_load_old_ehe`, `_load_old_r11_rate`) and
    r24_flood_contrast_regen.py's disabled-arm counterparts
    (`_load_old_dis_ibr`, `_load_old_dis_ehe`, `_load_old_dis_rate`) --
    imported, not re-derived. Domain outcome (final-year protection share)
    old value: `out/r2_flood_trajectories.csv` (arm=governed/ungoverned,
    level=executed, year=10, `100 - share_do_nothing` per run).
  Flood rule-based: `rulebased_5seed_e75e390c`, same function as new.

CROSS-CHECK AGAINST regen_progress_2026-09-15.md (parsed, never retyped)
  `_parse_regen_progress_row()` reads the "Pre-registered acceptance" table
  (governed) and the "(1) Ungoverned arm" table, extracts the "new mean +/-
  sd" cell for a named metric via regex, and this script asserts its own
  freshly-recomputed NEW irrigation strict/ungoverned means for IBR
  headline, EHE pooled, Mead minimum, shortage years, and governance
  fallback % agree with those parsed values to within 0.01 (both sides
  rounded to 2dp first, since regen_progress's own table is itself
  2dp-rounded prose, not full-precision data) -- raises on disagreement.

CONTRAST BLOCK (governed vs ungoverned, diff = ungoverned - governed)
  Two metrics (IBR headline, EHE pooled) x two cases (irrigation, flood) x
  two corpora (old, new) = 8 rows. Flood's is READ from
  `out/r24_flood_contrast_regen.csv` (row_type=contrast_stat) rather than
  recomputed -- r24 already computed and cross-checked it against r7.
  Irrigation's is computed the same way r24 computes flood's: NEW paired
  by literal seed 42-46 (irrigation has no seed-position quirk -- r14's
  own seed column is 42-46 on both arms, verified), OLD likewise paired by
  literal seed (same reason). `C.paired_t` / `C.exact_perm_p` (imported,
  the same generic functions r7/r11/r24 all use) supply t/df/p/sign-flips.

OUTPUTS
  out/r25_table1_regen.csv -- row_type in {table1_cell, contrast_pair,
    contrast_stat}.
  out/r25_table1_regen.md -- GENERATED by render_md() directly from the
    same in-memory `rows` list C.write_csv() writes (no number typed by
    hand).

PRE-REQUISITE: `scripts/r21_compute_cost.py` re-run first (this script
does not re-run it) so `out/r21_compute_cost_by_arm.csv` includes
flood_disabled -- wall_hours for the 4 LLM arms is read from there.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r21_compute_cost.py
        python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r25_table1_regen.py
        python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r25_table1_regen.py --corpus defaults

--corpus (added 2026-09-23, see _common.py::flood_corpus_dirs)
  v08 (default): EXACTLY the behaviour documented above, byte-identical
  output. defaults: FLOOD rows and the flood contrast ONLY -- irrigation
  (governed/ungoverned/both FQL variants, the irrigation KGE cells, the
  irrigation gemma4:12b block, the irrigation contrast rows) is UNCHANGED
  and unaffected by --corpus, always the v08 corpus, exactly as documented
  above. Flood governed/no-validator: NEW = the no-sampling-params re-run;
  comparator = the v08/faf1bb12 corpus computed LIVE at literal same seed
  (not the pre-quarantine published corpus r23/r24 read for v08). Flood
  rule-based: UNCHANGED regardless of --corpus (deterministic, no LLM
  sampling, so no separate defaults corpus exists for it). Flood
  gemma4:12b block and the flood contrast row read r26's/r24's
  `_defaults`-suffixed CSVs and render PENDING (never raise) if those are
  themselves pending. If the defaults strict/disabled 5-seed corpora are
  not both complete, every flood cell in the main table renders PENDING
  (never a partial/misleading number) and the flip-check/gen_fig3
  crosschecks are skipped for governed/no-validator (rule-based's own
  crosscheck still runs, since it never depends on --corpus). Writes
  out/r25_table1_regen_defaults.{md,csv} -- true today (0/5 defaults
  seeds landed), so this exercises the PENDING path, not the full table.
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r23_flood_strict_regen as R23  # noqa: E402
import r24_flood_contrast_regen as R24  # noqa: E402

# gen_fig3_regen.py (paper/nature_water/scripts/regen/) -- READ-ONLY: imported
# for its `load_all_runs()` data-loading + `_classify_state_from_cols`
# classification, used ONLY to cross-check this script's own numbers against
# the figure's. Its `if __name__ == "__main__"` guard means importing it
# does NOT call `generate_figure()` (no file is written under paper/); the
# module-level `OUT_DIR.mkdir(parents=True, exist_ok=True)` line is a no-op
# because that directory already exists. This script never edits that file.
sys.path.insert(0, os.path.join(C.REPO, "paper", "nature_water", "scripts", "regen"))
import gen_fig3_regen as FIG3  # noqa: E402

IRR_RESULTS = os.path.join(C.REPO, "examples", "irrigation_abm", "results")
SEEDS5 = ["42", "43", "44", "45", "46"]
SHORTAGE_FT = 1075.0
NA = "n.a."
NO_OLD = "no old record"


# ---------------------------------------------------------------------------
# generic helpers
# ---------------------------------------------------------------------------
def _parse_launch_command_wall_hours(run_dir: str) -> float:
    p = os.path.join(run_dir, "LAUNCH_COMMAND.txt")
    if not os.path.isfile(p):
        raise PrepError(f"missing LAUNCH_COMMAND.txt in {run_dir}")
    text = open(p, encoding="utf-8", errors="replace").read()
    m_start = re.search(r"Started:\s*(\d{4}/\d{2}/\d{2}).*?(\d{1,2}:\d{2}:\d{2}\.\d+)", text)
    m_end = re.search(r"Finished:\s*(\d{4}/\d{2}/\d{2}).*?(\d{1,2}:\d{2}:\d{2}\.\d+)", text)
    if not m_start or not m_end:
        raise PrepError(f"{p}: could not parse Started/Finished timestamps")

    def _dt(m):
        date_s, time_s = m.group(1), m.group(2).strip()
        return datetime.strptime(f"{date_s} {time_s}", "%Y/%m/%d %H:%M:%S.%f")

    t0, t1 = _dt(m_start), _dt(m_end)
    return (t1 - t0).total_seconds() / 3600.0


# ---------------------------------------------------------------------------
# irrigation LLM (governed / ungoverned) per-run metrics
# ---------------------------------------------------------------------------
def _irr_llm_metrics(run_dir: str) -> dict:
    sim = C.read_csv(os.path.join(run_dir, C.L.SIM_LOG))
    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
    if len(sim) != C.L.EXPECTED_ROWS:
        raise PrepError(f"{run_dir}: sim has {len(sim)} rows, expected {C.L.EXPECTED_ROWS}")
    ibr_headline = C.L.ibr(sim)
    # EHE (executed) -- NOT sourced from any function in
    # examples/irrigation_abm/analysis/; this is inline code matching
    # r14_advise_arm.py's own convention (`audit_executed_metrics`), itself
    # built on _common.py::irr_executed + _common.py::normalized_entropy
    # (both under SUBMISSION_2026/, not examples/irrigation_abm/analysis/).
    counts_exec = {s: 0 for s in C.IRR_SKILLS}
    for r in aud:
        a = C.irr_executed(r)
        if a not in counts_exec:
            raise PrepError(f"{run_dir}: off-registry executed action {a!r}")
        counts_exec[a] += 1
    ehe_pooled_executed = C.normalized_entropy(counts_exec, k=5)
    # EHE (proposal) -- matches the SECOND definition the canonical analysis
    # module DOES expose: examples/irrigation_abm/analysis/a1_ablation_metrics.py
    # ::ehe_5skill ("EHE on 5-skill categories -- primary metric (paper uses
    # k=5 for irrigation)"), pooled Shannon entropy over simulation_log's
    # `yearly_decision` (k=5) -- identical formula to r14's own
    # `ehe_pooled_proposal` column (cross-checked below against
    # regen_progress_2026-09-15.md's own "EHE pooled, proposal" row).
    counts_prop = {s: 0 for s in C.IRR_SKILLS}
    for r in sim:
        a = C.L.action(r)
        if a not in counts_prop:
            raise PrepError(f"{run_dir}: off-registry proposal action {a!r}")
        counts_prop[a] += 1
    ehe_pooled_proposal = C.normalized_entropy(counts_prop, k=5)
    by_year_mead = {}
    for r in sim:
        y = int(float(r["year"]))
        by_year_mead.setdefault(y, []).append(float(r["lake_mead_level"]))
    mead_vals = [sum(v) / len(v) for v in by_year_mead.values()]
    mead_min_ft = min(mead_vals)
    shortage_years = sum(1 for v in mead_vals if v < SHORTAGE_FT)
    st = [(r.get("status") or "").strip() for r in aud]
    rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
    n = len(aud)
    rejection_rate_pct = 100.0 * sum(1 for s in st if s.startswith("REJECTED")) / n
    retry_rate_pct = 100.0 * sum(1 for c in rc if c > 0) / n
    llm_fail_n = sum(1 for r in aud if (r.get("llm_success") or "").strip() != "True")
    fallback_n = sum(1 for s in st if s == "REJECTED_FALLBACK")
    fallback_pct = 100.0 * fallback_n / n
    ts = [datetime.fromisoformat((r.get("timestamp") or "").strip()) for r in aud]
    wall_hours = (max(ts) - min(ts)).total_seconds() / 3600.0
    return {
        "ibr_headline": ibr_headline, "ehe_pooled": ehe_pooled_executed,
        "ehe_pooled_proposal": ehe_pooled_proposal,
        "mead_min_ft": mead_min_ft, "shortage_years": float(shortage_years),
        "rejection_rate_pct": rejection_rate_pct, "retry_rate_pct": retry_rate_pct,
        "llm_fail_n": float(llm_fail_n), "fallback_pct": fallback_pct,
        "wall_hours": wall_hours,
    }


# ---------------------------------------------------------------------------
# irrigation FQL (rule-based) per-run metrics -- 3-category action space,
# NOT the LLM's 5-skill space. See docstring for why L.ibr/L.INCREASE
# cannot be reused here without silently returning 0.
# ---------------------------------------------------------------------------
FQL_INCREASE = frozenset({"increase_demand"})
FQL_ACTIONS = ("increase_demand", "maintain_demand", "decrease_demand")


def _irr_fql_metrics(run_dir: str) -> dict:
    sim = C.read_csv(os.path.join(run_dir, "simulation_log.csv"))
    C.require_cols(sim, ["yearly_decision", "fql_raw_skill", "fql_blocked", "wsa_label",
                          "year", "lake_mead_level"], run_dir)
    hi = [r for r in sim if C.L.wsa(r) in C.L.HIGH]
    if not hi:
        raise PrepError(f"{run_dir}: empty high-WSA denominator")
    # PROPOSAL-level = the RAW pre-block Q-learning category, `fql_raw_skill` -- NOT
    # `yearly_decision`, which is already the POST-block executed outcome (fql_blocked
    # replaces a blocked raw proposal with maintain_demand before it is written to
    # yearly_decision). Verified on seed42: among the 78 high-WSA rows, fql_raw_skill
    # is "increase_demand" 66/78 times (84.6%) while yearly_decision is "maintain_demand"
    # 77/78 times (fql_blocked=True on 71/78) -- using yearly_decision here would
    # silently report ~0% instead of FQL's real proposal-level irrational-increase rate.
    ibr_headline = 100.0 * sum(
        1 for r in hi if (r.get("fql_raw_skill") or "").strip() in FQL_INCREASE) / len(hi)
    counts = {a: 0 for a in FQL_ACTIONS}
    for r in sim:
        a = (r.get("yearly_decision") or "").strip()
        if a not in counts:
            raise PrepError(f"{run_dir}: unexpected FQL yearly_decision {a!r}")
        counts[a] += 1
    ehe_pooled = C.normalized_entropy(counts, k=3)  # k=3, NOT 5 -- flagged in .md
    by_year_mead = {}
    for r in sim:
        y = int(float(r["year"]))
        by_year_mead.setdefault(y, []).append(float(r["lake_mead_level"]))
    mead_vals = [sum(v) / len(v) for v in by_year_mead.values()]
    mead_min_ft = min(mead_vals)
    shortage_years = sum(1 for v in mead_vals if v < SHORTAGE_FT)
    wall_hours = _parse_launch_command_wall_hours(run_dir)
    return {
        "ibr_headline": ibr_headline, "ehe_pooled": ehe_pooled,
        "mead_min_ft": mead_min_ft, "shortage_years": float(shortage_years),
        "wall_hours": wall_hours,
    }


# ---------------------------------------------------------------------------
# Shared flood helpers -- boolean-state classification and EHE, IDENTICAL
# for all three flood arms, per r25-round-2 fix. `_flood_boolean_action` is
# copied VERBATIM (comment marks the copy) from
# paper/nature_water/scripts/regen/gen_fig3_regen.py::_rulebased_action --
# note its own tie-break: elevated AND has_insurance together classify as
# "buy_insurance", not "elevate_house". gen_fig3 applies this mapping only
# to the rule-based arm (LLM arms' `yearly_decision` is already a single
# clean category, so gen_fig3 uses it as-is via `_ehe_from_decisions`,
# confirmed numerically equivalent to `C.flood_normalize_action` +
# `C.normalized_entropy` for both LLM arms to 3dp -- see docstring). This
# script therefore ONLY changes the RULE-BASED EHE computation to use this
# function; governed/no-validator's EHE (via R23._metrics_for, unchanged)
# already matches gen_fig3 exactly.
#
# PROTECTION-SHARE RULE (task 2): "final-year share with any protection" is
# computed IDENTICALLY for all three arms as elevated OR has_insurance OR
# RELOCATED, read from simulation_log.csv's own boolean columns at year=10
# (all 100 agents every arm, every year -- verified, no dropout, unlike the
# governance-audit CSV). RELOCATED AGENTS COUNT AS PROTECTED (relocation
# removes flood exposure entirely, the strongest form of protection) --
# this is the one rule, applied everywhere.
#
# STICKINESS (round-3 correction): `elevated` and `relocated` are sticky/
# monotonic (0 True->False agent-year transitions, verified below across
# all 15 new runs -- raises if this is ever not 0). `has_insurance` is NOT
# sticky -- a prior round's docstring wrongly claimed it was, from a single-
# run spot check that happened to miss the lapses; `_flood_flip_counts`
# below counts every True->False transition per (run, column) and the
# actual range is rendered into the .md Method line from those counts, not
# typed by hand. This means the year-10 protection-share metric mixes
# CUMULATIVE uptake (elevation, relocation, which only ever accumulate) with
# a YEAR-10 SNAPSHOT (insurance, which lapses and gets repurchased) --
# flagged plainly, not glossed over.
# ---------------------------------------------------------------------------
def _flood_flip_counts(sim_rows: list, col: str) -> int:
    """Count True->False transitions in `col`, per agent, across the run's
    chronological year sequence (row order in simulation_log.csv is not
    guaranteed sorted by year, so this sorts per agent first)."""
    by_agent: dict = {}
    for r in sim_rows:
        by_agent.setdefault(r["agent_id"], []).append(
            (int(float(r["year"])), (r.get(col) or "").strip() == "True"))
    flips = 0
    for agent_id, seq in by_agent.items():
        seq.sort(key=lambda t: t[0])
        for (y0, v0), (y1, v1) in zip(seq, seq[1:]):
            if v0 and not v1:
                flips += 1
    return flips
def _flood_boolean_action(row: dict) -> str:
    """Verbatim copy of gen_fig3_regen.py::_rulebased_action's classification."""
    rel = (row.get("relocated") or "").strip() == "True"
    ins = (row.get("has_insurance") or "").strip() == "True"
    elv = (row.get("elevated") or "").strip() == "True"
    if rel:
        return "relocate"
    if elv and ins:
        return "buy_insurance"
    if elv:
        return "elevate_house"
    if ins:
        return "buy_insurance"
    return "do_nothing"


def _flood_year10_protection_pct(sim_rows: list) -> float:
    sel = [r for r in sim_rows if int(float(r["year"])) == 10]
    if not sel:
        raise PrepError("no simulation_log rows at year 10")
    n_protected = sum(1 for r in sel
                       if (r.get("elevated") or "").strip() == "True"
                       or (r.get("has_insurance") or "").strip() == "True"
                       or (r.get("relocated") or "").strip() == "True")
    return 100.0 * n_protected / len(sel)


def _flood_pooled_protection_pct(sim_rows: list) -> float:
    """Same OR-rule, ALL years pooled -- used only for the gen_fig3 crosscheck
    (gen_fig3's own printed summary pools all years, not year 10 alone)."""
    n = len(sim_rows)
    n_protected = sum(1 for r in sim_rows
                       if (r.get("elevated") or "").strip() == "True"
                       or (r.get("has_insurance") or "").strip() == "True"
                       or (r.get("relocated") or "").strip() == "True")
    return 100.0 * n_protected / n


# ---------------------------------------------------------------------------
# flood governed / no-validator: reuse r23's per-run metrics + add the
# final-year protection-share domain outcome (not computed by r23/r24).
# ---------------------------------------------------------------------------
def _flood_llm_metrics(rd: str) -> dict:
    m = R23._metrics_for(rd)
    sim = C.read_csv(os.path.join(rd, C.FLOOD_SIM))
    return {
        "ibr_headline": m["ibr_uncond_final"], "ehe_pooled": m["ehe_pooled_simlog_published"],
        "final_year_protection_pct": _flood_year10_protection_pct(sim),
        "_pooled_protection_pct": _flood_pooled_protection_pct(sim),
        "rejection_rate_pct": m["rejection_rate_pct"], "retry_rate_pct": m["retry_rate_pct"],
        "llm_fail_n": float(m["_llm_fail_n"]),
        "fallback_pct": m["_fallback_share_pct"], "wall_hours": m["_wall_hours"],
    }


# ---------------------------------------------------------------------------
# flood rule-based: no audit CSV, no threat-appraisal construct -> IBR is
# undefined (reported n.a.); EHE (boolean-based, matching gen_fig3 exactly)
# + domain outcome computed from simulation_log directly.
# ---------------------------------------------------------------------------
def _flood_rulebased_metrics(run_dir: str) -> dict:
    sim = C.read_csv(os.path.join(run_dir, "simulation_log.csv"))
    C.require_cols(sim, ["decision", "year", "elevated", "has_insurance", "relocated"],
                    run_dir)
    counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
    for r in sim:
        counts[_flood_boolean_action(r)] += 1
    ehe_pooled = C.normalized_entropy(counts, k=4)
    wall_hours = _parse_launch_command_wall_hours(run_dir)
    return {
        "ibr_headline": None,  # n.a. -- no TP construct, see docstring
        "ehe_pooled": ehe_pooled,
        "final_year_protection_pct": _flood_year10_protection_pct(sim),
        "_pooled_protection_pct": _flood_pooled_protection_pct(sim),
        "wall_hours": wall_hours,
    }


# ---------------------------------------------------------------------------
# OLD per-seed loaders
# ---------------------------------------------------------------------------
def _load_old_irr_llm(arm: str) -> dict:
    """{seed: {metric: value}} for arm in {'strict', 'no_validator'}, from
    out/r14_advise_arm.csv (frozen pre-2026-09-15-loss snapshot)."""
    rows = C.read_csv(os.path.join(C.OUT, "r14_advise_arm.csv"))
    kept = [r for r in rows if r["arm"] == arm]
    print(f"  r14_advise_arm.csv: {len(rows)} rows read, {len(kept)} kept (arm={arm}), "
          f"{len(rows) - len(kept)} dropped (other arms)")
    out = {}
    for r in kept:
        seed = r["seed"]
        out[seed] = {
            "ibr_headline": float(r["ibr_pct_proposal"]),
            "ehe_pooled": float(r["ehe_pooled_executed"]),
            "ehe_pooled_proposal": float(r["ehe_pooled_proposal"]),
            "mead_min_ft": float(r["mead_min_ft"]),
            "shortage_years": float(r["shortage_years"]),
            "rejection_rate_pct": float(r["rejected_to_fallback_pct"]),
        }
    missing = [s for s in SEEDS5 if s not in out]
    if missing:
        raise PrepError(f"r14_advise_arm.csv: arm={arm} missing seeds {missing}")
    return out


def _load_old_irr_fql(old_root: str) -> dict:
    old_dir = os.path.join(IRR_RESULTS, old_root)
    if not os.path.isdir(old_dir):
        raise PrepError(f"missing old FQL dir {old_dir}")
    out = {}
    for s in SEEDS5:
        rd = os.path.join(old_dir, f"seed{s}")
        if not os.path.isdir(rd):
            raise PrepError(f"missing old FQL seed dir {rd}")
        out[s] = _irr_fql_metrics(rd)
    return out


def _load_old_flood_domain_outcome(arm: str, positions: list) -> dict:
    """{old_seed: final_year_protection_pct} from r2_flood_trajectories.csv
    (arm=governed/ungoverned, level=executed, year=10, 100-share_do_nothing)."""
    rows = C.read_csv(os.path.join(C.OUT, "r2_flood_trajectories.csv"))
    kept = [r for r in rows if r["arm"] == arm and r["level"] == "executed"
            and r["year"] == "10"]
    print(f"  r2_flood_trajectories.csv: {len(rows)} rows read, {len(kept)} kept "
          f"(arm={arm}, level=executed, year=10), {len(rows) - len(kept)} dropped")
    by_seed = {r["seed"]: 100.0 - float(r["share_do_nothing"]) for r in kept}
    out = {}
    for _, old_seed in positions:
        if old_seed not in by_seed:
            raise PrepError(f"r2_flood_trajectories.csv: arm={arm} missing seed {old_seed} "
                             f"at year=10")
        out[old_seed] = by_seed[old_seed]
    return out


def _load_old_flood_rulebased() -> dict:
    old_dir = os.path.join(C.FLOOD_RESULTS, C.flood_corpus_dirs("v08")["rulebased_old"][0])
    if not os.path.isdir(old_dir):
        raise PrepError(f"missing old flood rulebased dir {old_dir}")
    out = {}
    for s in SEEDS5:
        rd = os.path.join(old_dir, f"Run_{s}")
        if not os.path.isdir(rd):
            raise PrepError(f"missing old flood rulebased run dir {rd}")
        out[s] = _flood_rulebased_metrics(rd)
    return out


# ---------------------------------------------------------------------------
# regen_progress_2026-09-15.md parser -- old per-seed values that live only
# in prose tables, and the cross-check reference values. Never retyped.
# ---------------------------------------------------------------------------
def _parse_regen_progress_new_mean(section_header: str, metric_row_prefix: str) -> tuple:
    """Return (new_mean, new_sd) parsed from the first markdown table row,
    inside the section starting at `section_header`, whose first cell
    STARTS WITH `metric_row_prefix`. Raises if not found."""
    path = os.path.join(C.OUT, "regen_progress_2026-09-15.md")
    if not os.path.isfile(path):
        raise PrepError(f"missing {path}")
    text = open(path, encoding="utf-8").read()
    idx = text.find(section_header)
    if idx == -1:
        raise PrepError(f"regen_progress_2026-09-15.md: section {section_header!r} not found")
    section = text[idx: idx + 4000]
    for line in section.splitlines():
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        if cells[0].startswith(metric_row_prefix):
            m = re.search(r"([\d.]+)\s*\xb1\s*([\d.]+)", cells[2])
            if not m:
                continue
            return float(m.group(1)), float(m.group(2))
    raise PrepError(f"regen_progress_2026-09-15.md: no row matching "
                     f"{metric_row_prefix!r} found in section {section_header!r}")


def _crosscheck(name: str, computed: float, section_header: str, metric_row_prefix: str,
                 tol: float = 0.01) -> None:
    parsed_mean, _ = _parse_regen_progress_new_mean(section_header, metric_row_prefix)
    c2, p2 = round(computed, 2), round(parsed_mean, 2)
    if abs(c2 - p2) > tol:
        raise PrepError(f"crosscheck {name}: computed {c2} vs regen_progress {p2} "
                         f"(row {metric_row_prefix!r}) -- differ by more than {tol}")
    print(f"  crosscheck OK: {name} computed={c2} regen_progress={p2}")


GOV_SECTION = "## Pre-registered acceptance"
UNGOV_SECTION = "## (1) Ungoverned arm"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R25 -- paper Table 1, old vs new, all governance arms")
    C.add_corpus_arg(parser)
    args = parser.parse_args()
    corpus = args.corpus
    suffix = C.corpus_suffix(corpus)
    C.banner(f"R25  paper Table 1, old vs new, all arms both cases (flood corpus={corpus})")

    # ---- irrigation: new metrics --------------------------------------
    irr_gov_dirs = {s: os.path.join(IRR_RESULTS, f"strict_42yr_gemma3_4b_faf1bb12_seed{s}")
                     for s in SEEDS5}
    irr_ungov_dirs = {s: os.path.join(IRR_RESULTS, f"ungoverned_42yr_gemma3_4b_faf1bb12_seed{s}")
                       for s in SEEDS5}
    for s, d in {**irr_gov_dirs, **irr_ungov_dirs}.items():
        if not os.path.isdir(d):
            raise PrepError(f"missing irrigation run dir {d}")
    irr_gov_new = {s: _irr_llm_metrics(irr_gov_dirs[s]) for s in SEEDS5}
    irr_ungov_new = {s: _irr_llm_metrics(irr_ungov_dirs[s]) for s in SEEDS5}
    print(f"  irrigation governed/ungoverned: 5 run dirs each, all read OK")

    fql_root_map = {
        "irrigation rule-based FQL rebalanced": ("fql_raw_faf1bb12", "fql_raw_e75e390c"),
        "irrigation rule-based FQL matched (no-rebalance)":
            ("fql_raw_norebalance_faf1bb12", "fql_raw_norebalance_e75e390c"),
    }
    fql_new = {}
    fql_old = {}
    for label, (new_root, old_root) in fql_root_map.items():
        fql_new[label] = {s: _irr_fql_metrics(os.path.join(IRR_RESULTS, new_root, f"seed{s}"))
                           for s in SEEDS5}
        fql_old[label] = _load_old_irr_fql(old_root)
        print(f"  {label}: 5 new + 5 old seeds read OK ({new_root} / {old_root})")

    # ---- irrigation: old metrics ---------------------------------------
    irr_gov_old = _load_old_irr_llm("strict")
    irr_ungov_old = _load_old_irr_llm("no_validator")

    # ---- cross-check NEW irrigation means against regen_progress -------
    def _m(d, key):
        return C.mean([d[s][key] for s in SEEDS5])

    _crosscheck("irr governed IBR headline", _m(irr_gov_new, "ibr_headline"),
                GOV_SECTION, "IBR proposal-level")
    _crosscheck("irr governed EHE pooled (executed)", _m(irr_gov_new, "ehe_pooled"),
                GOV_SECTION, "EHE pooled, executed")
    _crosscheck("irr governed EHE pooled (proposal)", _m(irr_gov_new, "ehe_pooled_proposal"),
                GOV_SECTION, "EHE pooled, proposal")
    _crosscheck("irr governed Mead min", _m(irr_gov_new, "mead_min_ft"),
                GOV_SECTION, "Mead minimum")
    _crosscheck("irr governed shortage years", _m(irr_gov_new, "shortage_years"),
                GOV_SECTION, "Shortage years")
    _crosscheck("irr governed governance fallback %", _m(irr_gov_new, "rejection_rate_pct"),
                GOV_SECTION, "Governance fallback share")
    _crosscheck("irr ungoverned IBR headline", _m(irr_ungov_new, "ibr_headline"),
                UNGOV_SECTION, "IBR proposal-level")
    _crosscheck("irr ungoverned EHE pooled (executed)", _m(irr_ungov_new, "ehe_pooled"),
                UNGOV_SECTION, "EHE pooled, executed")
    _crosscheck("irr ungoverned EHE pooled (proposal)", _m(irr_ungov_new, "ehe_pooled_proposal"),
                UNGOV_SECTION, "EHE pooled, proposal")
    _crosscheck("irr ungoverned Mead min", _m(irr_ungov_new, "mead_min_ft"),
                UNGOV_SECTION, "Mead minimum")
    _crosscheck("irr ungoverned shortage years", _m(irr_ungov_new, "shortage_years"),
                UNGOV_SECTION, "Shortage years")
    _crosscheck("irr ungoverned governance fallback %", _m(irr_ungov_new, "rejection_rate_pct"),
                UNGOV_SECTION, "No-validator fallback share")

    # ---- flood: new + old metrics (reusing r23/r24) --------------------
    # v08: EXACTLY the pre-existing logic below (comparator = pre-quarantine
    # published corpus, read from out/*.csv). defaults: comparator = the
    # v08/faf1bb12 corpus computed LIVE at literal same seed (never the
    # pre-quarantine corpus); `flood_available` is False (governed/
    # no-validator rendered PENDING below) unless BOTH the defaults strict
    # and disabled 5-seed corpora are complete -- true today (0/5 landed).
    if corpus == "v08":
        flood_gov_new_dirs = {s: os.path.join(C.FLOOD_RESULTS, R23.NEW_ROOT, f"Run_{s}")
                                for s in SEEDS5}
        flood_dis_new_dirs = {s: os.path.join(C.FLOOD_RESULTS, R24.NEW_DIS_ROOT, f"Run_{s}")
                                for s in SEEDS5}
        flood_gov_new = {s: _flood_llm_metrics(flood_gov_new_dirs[s]) for s in SEEDS5}
        flood_dis_new = {s: _flood_llm_metrics(flood_dis_new_dirs[s]) for s in SEEDS5}

        flood_gov_old_ibr = R23._load_old_ibr()
        flood_gov_old_ehe = R23._load_old_ehe()
        flood_gov_old_rej = R23._load_old_r11_rate("rejection_rate_pct")
        flood_gov_old_domain = _load_old_flood_domain_outcome("governed", R23.OLD_POSITIONS)
        flood_dis_old_ibr = R24._load_old_dis_ibr()
        flood_dis_old_ehe = R24._load_old_dis_ehe()
        flood_dis_old_rej = R24._load_old_dis_rate("rejection_rate_pct")
        flood_dis_old_domain = _load_old_flood_domain_outcome("ungoverned", R24.OLD_DIS_POSITIONS)
        flood_old_positions_gov = R23.OLD_POSITIONS
        flood_old_positions_dis = R24.OLD_DIS_POSITIONS
        flood_available = True
    else:
        gov_root, gov_seeds = C.flood_corpus_dirs(corpus)["strict"]
        dis_root, dis_seeds = C.flood_corpus_dirs(corpus)["disabled"]
        band_gov_root, band_gov_seeds = C.flood_corpus_dirs("v08")["strict"]     # faf1bb12
        band_dis_root, band_dis_seeds = C.flood_corpus_dirs("v08")["disabled"]   # faf1bb12

        def _n_complete(root, seeds):
            return sum(1 for s in seeds
                       if R23._flood_run_complete(os.path.join(C.FLOOD_RESULTS, root,
                                                                 f"Run_{s}"))[0] == "ok")

        n_gov_ok, n_dis_ok = _n_complete(gov_root, gov_seeds), _n_complete(dis_root, dis_seeds)
        flood_available = (n_gov_ok == len(gov_seeds)) and (n_dis_ok == len(dis_seeds))
        print(f"  flood ({corpus}): strict {n_gov_ok}/{len(gov_seeds)} complete, disabled "
              f"{n_dis_ok}/{len(dis_seeds)} complete -- flood_available={flood_available}")

        flood_gov_new_dirs = {s: os.path.join(C.FLOOD_RESULTS, gov_root, f"Run_{s}")
                                for s in gov_seeds}
        flood_dis_new_dirs = {s: os.path.join(C.FLOOD_RESULTS, dis_root, f"Run_{s}")
                                for s in dis_seeds}
        if flood_available:
            flood_gov_new = {s: _flood_llm_metrics(flood_gov_new_dirs[s]) for s in gov_seeds}
            flood_dis_new = {s: _flood_llm_metrics(flood_dis_new_dirs[s]) for s in dis_seeds}
            band_gov_dirs = {s: os.path.join(C.FLOOD_RESULTS, band_gov_root, f"Run_{s}")
                              for s in band_gov_seeds}
            band_dis_dirs = {s: os.path.join(C.FLOOD_RESULTS, band_dis_root, f"Run_{s}")
                              for s in band_dis_seeds}
            band_gov_m = {s: _flood_llm_metrics(band_gov_dirs[s]) for s in band_gov_seeds}
            band_dis_m = {s: _flood_llm_metrics(band_dis_dirs[s]) for s in band_dis_seeds}
            # Reshape to the SAME {metric: {seed: value}} / {seed: value} shapes
            # R23._load_old_ibr()/_load_old_ehe() etc. return, so every
            # downstream `add_cell` call below (keyed by `flood_old_positions_*`)
            # needs no v08/defaults branching of its own.
            flood_gov_old_ibr = {"ibr_uncond_final":
                                  {s: band_gov_m[s]["ibr_headline"] for s in band_gov_seeds}}
            flood_gov_old_ehe = {s: band_gov_m[s]["ehe_pooled"] for s in band_gov_seeds}
            flood_gov_old_rej = {s: band_gov_m[s]["rejection_rate_pct"] for s in band_gov_seeds}
            flood_gov_old_domain = {s: band_gov_m[s]["final_year_protection_pct"]
                                     for s in band_gov_seeds}
            flood_dis_old_ibr = {"ibr_uncond_final":
                                  {s: band_dis_m[s]["ibr_headline"] for s in band_dis_seeds}}
            flood_dis_old_ehe = {s: band_dis_m[s]["ehe_pooled"] for s in band_dis_seeds}
            flood_dis_old_rej = {s: band_dis_m[s]["rejection_rate_pct"] for s in band_dis_seeds}
            flood_dis_old_domain = {s: band_dis_m[s]["final_year_protection_pct"]
                                     for s in band_dis_seeds}
            flood_old_positions_gov = [(i + 1, s) for i, s in enumerate(band_gov_seeds)]
            flood_old_positions_dis = [(i + 1, s) for i, s in enumerate(band_dis_seeds)]
        else:
            flood_gov_new = flood_dis_new = {}

    # rule-based: UNCHANGED regardless of --corpus -- deterministic, no LLM
    # sampling, so there is no separate "defaults" rule-based corpus.
    flood_rb_new_dirs = {s: os.path.join(C.FLOOD_RESULTS, C.flood_corpus_dirs("v08")["rulebased"][0],
                                         f"Run_{s}")
                          for s in SEEDS5}
    flood_rb_new = {s: _flood_rulebased_metrics(flood_rb_new_dirs[s]) for s in SEEDS5}
    flood_rb_old = _load_old_flood_rulebased()

    # ---- flip-count check (round-3 correction): count True->False agent-year
    # transitions for elevated/has_insurance/relocated on all 15 NEW flood
    # runs (3 arms x 5 seeds). elevated/relocated MUST be 0 (raises if not --
    # a prior round wrongly claimed has_insurance was sticky too, from a
    # single-seed spot check; this is the full, per-run, all-15-runs count).
    # If `flood_available` is False, only rule-based's 5 runs are checkable
    # (governed/no-validator's defaults dirs are not landed) -- 15 rows, not
    # 45; render_md's own assertion is corpus/flood_available-aware, see
    # below.
    flip_arms = [("rule-based", flood_rb_new_dirs)]
    if flood_available:
        flip_arms = [("governed (strict)", flood_gov_new_dirs),
                     ("no-validator", flood_dis_new_dirs)] + flip_arms
    flip_records = []
    for arm_label, dirs in flip_arms:
        for s in dirs:
            sim = C.read_csv(os.path.join(dirs[s], "simulation_log.csv"))
            for col in ("elevated", "has_insurance", "relocated"):
                flip_records.append({"row_type": "flip_check", "arm": arm_label, "seed": s,
                                      "column": col, "flips": _flood_flip_counts(sim, col)})
    for rec in flip_records:
        if rec["column"] in ("elevated", "relocated") and rec["flips"] != 0:
            raise PrepError(f"{rec['column']} is NOT sticky: {rec['flips']} True->False "
                             f"flips in arm={rec['arm']} seed={rec['seed']} -- the "
                             f"docstring/Method 'sticky' claim for this column is false, "
                             f"fix the claim, do not silently keep reporting 0")
    has_ins_flip_vals = [rec["flips"] for rec in flip_records if rec["column"] == "has_insurance"]
    has_ins_flip_min, has_ins_flip_max = min(has_ins_flip_vals), max(has_ins_flip_vals)
    print(f"  flip check ({len(flip_arms)} arm(s), {len(flip_records) // 3} runs): "
          f"elevated/relocated = 0 nonzero (sticky, confirmed); has_insurance = "
          f"{has_ins_flip_min}-{has_ins_flip_max} True->False flips per run (NOT sticky)")

    # ---- crosscheck: this script's boolean-OR protection classification vs
    # gen_fig3_regen.py's own 5-state classification (`_classify_state_from_cols`),
    # via the identity protected% = 100 - "No protection"%. gen_fig3 has no
    # year-10-only print (its own Protection State Summary pools ALL years),
    # so this checks the ALL-YEAR-POOLED share (`_pooled_protection_pct`
    # computed above) against gen_fig3's own printed complement -- confirming
    # the two classification methods agree, even though the actual Table 1
    # cell uses the year-10-only slice gen_fig3 does not print. gen_fig3_regen.py
    # is hardcoded to faf1bb12 for governed/disabled (outside this script's
    # edit scope, never monkey-patched here) -- under --corpus defaults this
    # crosscheck is therefore only meaningful for rule-based (corpus-
    # independent); governed/disabled are skipped (comparing DEFAULTS numbers
    # against gen_fig3's faf1bb12-only data would be a real empirical
    # difference, not a self-consistency bug, and would give a false FAIL).
    crosscheck_keys = ("gov", "disabled", "rulebased") if corpus == "v08" else ("rulebased",)
    fig3_data = FIG3.load_all_runs()  # read-only: no generate_figure() call, no file written
    fig3_pooled_pct = {}
    for key in crosscheck_keys:
        import pandas as _pd
        all_df = _pd.concat(fig3_data[key], ignore_index=True) if fig3_data[key] else _pd.DataFrame()
        if all_df.empty:
            raise PrepError(f"gen_fig3_regen.load_all_runs(): no data for {key!r}")
        fig3_pooled_pct[key] = 100.0 * (all_df["prot_state"] != "No protection").mean()
    mine_pooled = {"rulebased": C.mean([flood_rb_new[s]["_pooled_protection_pct"] for s in SEEDS5])}
    if flood_available:
        # flood_gov_new/flood_dis_new are always keyed by the same 5 seed
        # strings as SEEDS5 in both corpora (see _common.py::flood_corpus_dirs
        # SCOPE NOTE), so this needs no v08/defaults branching.
        mine_pooled["gov"] = C.mean([flood_gov_new[s]["_pooled_protection_pct"] for s in SEEDS5])
        mine_pooled["disabled"] = C.mean(
            [flood_dis_new[s]["_pooled_protection_pct"] for s in SEEDS5])
    for key in crosscheck_keys:
        if key not in mine_pooled:
            print(f"  crosscheck SKIPPED for {key}: no live NEW flood data for this corpus")
            continue
        if abs(mine_pooled[key] - fig3_pooled_pct[key]) > 0.5:
            raise PrepError(f"protection-share crosscheck failed for {key}: this script's "
                             f"all-year-pooled protected%={mine_pooled[key]:.2f} vs "
                             f"gen_fig3's 100-'No protection'%={fig3_pooled_pct[key]:.2f}")
        print(f"  crosscheck OK: {key} all-year-pooled protected% "
              f"mine={mine_pooled[key]:.2f} gen_fig3={fig3_pooled_pct[key]:.2f}")

    # ---- r21 wall hours (4 LLM arms) ------------------------------------
    r21_rows = C.read_csv(os.path.join(C.OUT, "r21_compute_cost_by_arm.csv"))
    r21_by_arm = {r["arm"]: r for r in r21_rows}
    for a in ("irrigation_strict", "irrigation_ungoverned", "flood_strict", "flood_disabled"):
        if a not in r21_by_arm:
            raise PrepError(f"r21_compute_cost_by_arm.csv: missing arm={a} -- re-run "
                             f"scripts/r21_compute_cost.py first")

    rows = []
    rows.extend(flip_records)

    # =====================================================================
    # TABLE 1 -- one row per (case, arm)
    # =====================================================================
    def add_cell(case, arm, column, old_mean=None, old_sd=None, new_mean=None, new_sd=None,
                 old_status="ok", new_status="ok", n_old=5, n_new=5, note=""):
        rows.append({
            "row_type": "table1_cell", "case": case, "arm": arm, "column": column,
            "old_mean": old_mean, "old_sd": old_sd, "new_mean": new_mean, "new_sd": new_sd,
            "old_status": old_status, "new_status": new_status,
            "n_old": n_old, "n_new": n_new, "note": note,
        })

    def agg(d, key):
        vals = [d[s][key] for s in SEEDS5]
        return C.mean(vals), C.sd(vals)

    def agg_dict_by_seed(d, key):
        vals = [d[s][key] for s in SEEDS5]
        return C.mean(vals), C.sd(vals)

    # ---- irrigation governed ----
    for col, key in (("IBR headline", "ibr_headline"), ("EHE pooled (executed)", "ehe_pooled"),
                      ("EHE pooled (proposal)", "ehe_pooled_proposal")):
        om, osd = agg(irr_gov_old, key)
        nm, nsd = agg(irr_gov_new, key)
        add_cell("irrigation", "governed (strict)", col, om, osd, nm, nsd)
    om, osd = agg(irr_gov_old, "mead_min_ft")
    nm, nsd = agg(irr_gov_new, "mead_min_ft")
    add_cell("irrigation", "governed (strict)", "domain outcome: Mead min (ft)", om, osd, nm, nsd)
    om, osd = agg(irr_gov_old, "shortage_years")
    nm, nsd = agg(irr_gov_new, "shortage_years")
    add_cell("irrigation", "governed (strict)", "domain outcome: shortage years", om, osd, nm, nsd)
    om, osd = agg(irr_gov_old, "rejection_rate_pct")
    nm, nsd = agg(irr_gov_new, "rejection_rate_pct")
    add_cell("irrigation", "governed (strict)", "rejection rate %", om, osd, nm, nsd)
    nm, nsd = agg(irr_gov_new, "retry_rate_pct")
    add_cell("irrigation", "governed (strict)", "retry rate %", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_gov_new, "llm_fail_n")
    add_cell("irrigation", "governed (strict)", "LLM failures", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_gov_new, "fallback_pct")
    add_cell("irrigation", "governed (strict)", "governance fallback %", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_gov_new, "wall_hours")
    add_cell("irrigation", "governed (strict)", "wall h per run",
             new_mean=nm, new_sd=nsd, old_status="no_record",
             note=f"new mean/sd cross-checked equal to r21_compute_cost_by_arm.csv "
                  f"irrigation_strict row ({r21_by_arm['irrigation_strict']['wall_hours_mean']})")

    # ---- irrigation ungoverned ----
    for col, key in (("IBR headline", "ibr_headline"), ("EHE pooled (executed)", "ehe_pooled"),
                      ("EHE pooled (proposal)", "ehe_pooled_proposal")):
        om, osd = agg(irr_ungov_old, key)
        nm, nsd = agg(irr_ungov_new, key)
        add_cell("irrigation", "ungoverned", col, om, osd, nm, nsd)
    om, osd = agg(irr_ungov_old, "mead_min_ft")
    nm, nsd = agg(irr_ungov_new, "mead_min_ft")
    add_cell("irrigation", "ungoverned", "domain outcome: Mead min (ft)", om, osd, nm, nsd)
    om, osd = agg(irr_ungov_old, "shortage_years")
    nm, nsd = agg(irr_ungov_new, "shortage_years")
    add_cell("irrigation", "ungoverned", "domain outcome: shortage years", om, osd, nm, nsd)
    om, osd = agg(irr_ungov_old, "rejection_rate_pct")
    nm, nsd = agg(irr_ungov_new, "rejection_rate_pct")
    add_cell("irrigation", "ungoverned", "rejection rate %", om, osd, nm, nsd)
    nm, nsd = agg(irr_ungov_new, "retry_rate_pct")
    add_cell("irrigation", "ungoverned", "retry rate %", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_ungov_new, "llm_fail_n")
    add_cell("irrigation", "ungoverned", "LLM failures", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_ungov_new, "fallback_pct")
    add_cell("irrigation", "ungoverned", "governance fallback %", new_mean=nm, new_sd=nsd,
             old_status="no_record")
    nm, nsd = agg(irr_ungov_new, "wall_hours")
    add_cell("irrigation", "ungoverned", "wall h per run",
             new_mean=nm, new_sd=nsd, old_status="no_record")

    # ---- irrigation FQL x2 ----
    for label in fql_root_map:
        for col, key in (("IBR headline", "ibr_headline"),
                          ("EHE pooled (executed)", "ehe_pooled")):
            om, osd = agg(fql_old[label], key)
            nm, nsd = agg(fql_new[label], key)
            note = "" if col == "IBR headline" else ("k=3 action space (increase_demand/"
                                                       "maintain_demand/decrease_demand), NOT "
                                                       "comparable to the LLM arms' k=5 EHE")
            add_cell("irrigation", label, col, om, osd, nm, nsd, note=note)
        add_cell("irrigation", label, "EHE pooled (proposal)", old_status="na", new_status="na",
                  note="FQL's true raw proposal space is Hung & Yang's binary "
                       "increase/decrease (k=2, from fql_raw_skill), not the LLM's 5-skill "
                       "space -- no k=5 proposal EHE exists for this arm")
        om, osd = agg(fql_old[label], "mead_min_ft")
        nm, nsd = agg(fql_new[label], "mead_min_ft")
        add_cell("irrigation", label, "domain outcome: Mead min (ft)", om, osd, nm, nsd)
        om, osd = agg(fql_old[label], "shortage_years")
        nm, nsd = agg(fql_new[label], "shortage_years")
        add_cell("irrigation", label, "domain outcome: shortage years", om, osd, nm, nsd)
        for col in ("rejection rate %", "retry rate %", "LLM failures", "governance fallback %"):
            add_cell("irrigation", label, col, old_status="na", new_status="na",
                      note="rule-based has no LLM audit trail")
        om, osd = agg(fql_old[label], "wall_hours")
        nm, nsd = agg(fql_new[label], "wall_hours")
        add_cell("irrigation", label, "wall h per run", om, osd, nm, nsd)

    # ---- flood governed + flood no-validator ----
    # v08: EXACTLY the pre-existing cells below (comparator = pre-quarantine
    # published corpus). defaults, flood_available=True: comparator = the
    # v08/faf1bb12 corpus computed live (flood_old_positions_gov/_dis, built
    # above). defaults, flood_available=False (true today): every cell for
    # these two arms renders PENDING -- never a partial/misleading number.
    FLOOD_LLM_COLUMNS = ["IBR headline", "EHE pooled (executed)", "EHE pooled (proposal)",
                         "domain outcome: final-year protection %", "rejection rate %",
                         "retry rate %", "LLM failures", "governance fallback %",
                         "wall h per run"]
    if not flood_available:
        pending_note = (f"--corpus {corpus}: defaults strict/disabled 5-seed corpora not "
                        f"both complete yet (0/5 landed as of this run) -- re-run once "
                        f"they land, no code change needed")
        for arm in ("governed (strict)", "no-validator"):
            for col in FLOOD_LLM_COLUMNS:
                add_cell("flood", arm, col, old_status="pending", new_status="pending",
                         n_old=0, n_new=0, note=pending_note)
    else:
        for col, ov_src, nv_src in (
            ("IBR headline", flood_gov_old_ibr["ibr_uncond_final"], flood_gov_new),
            ("EHE pooled (executed)", flood_gov_old_ehe, flood_gov_new),
        ):
            key = "ibr_headline" if col == "IBR headline" else "ehe_pooled"
            old_vals = [ov_src[old_seed] for _, old_seed in flood_old_positions_gov]
            om, osd = C.mean(old_vals), C.sd(old_vals)
            nm, nsd = agg(flood_gov_new, key)
            add_cell("flood", "governed (strict)", col, om, osd, nm, nsd)
        old_vals = [flood_gov_old_ehe[old_seed] for _, old_seed in flood_old_positions_gov]
        om, osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_gov_new, "ehe_pooled")
        add_cell("flood", "governed (strict)", "EHE pooled (proposal)", om, osd, nm, nsd,
                 note="identical to EHE pooled (executed) -- flood's proposal/final/executed "
                      "levels coincide row-for-row, proven in r23 (0 mismatches, all 5 seeds)")
        old_vals = [flood_gov_old_domain[old_seed] for _, old_seed in flood_old_positions_gov]
        ref_om, ref_osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_gov_new, "final_year_protection_pct")
        if corpus == "v08":
            # EXACT original note text, verbatim -- byte-identity contract.
            add_cell("flood", "governed (strict)", "domain outcome: final-year protection %",
                     new_mean=nm, new_sd=nsd, old_status="no_record",
                     note=f"no old value for THIS metric (simulation_log boolean OR, "
                          f"relocated counts as protected) -- the old raw simulation_log no "
                          f"longer exists. A DIFFERENT metric (audit-based, 100-share_do_"
                          f"nothing at year 10) has an old value of {ref_om:.1f}+/-"
                          f"{ref_osd:.1f}% from r2_flood_trajectories.csv, kept for "
                          f"reference only, not substituted")
        else:
            add_cell("flood", "governed (strict)", "domain outcome: final-year protection %",
                     ref_om, ref_osd, nm, nsd,
                     note=f"comparator = v08/faf1bb12 (live) {ref_om:.1f}+/-{ref_osd:.1f}% "
                          f"-- NOT r2_flood_trajectories.csv's audit-based metric")
        old_vals = [flood_gov_old_rej[old_seed] for _, old_seed in flood_old_positions_gov]
        om, osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_gov_new, "rejection_rate_pct")
        add_cell("flood", "governed (strict)", "rejection rate %", om, osd, nm, nsd)
        nm, nsd = agg(flood_gov_new, "retry_rate_pct")
        add_cell("flood", "governed (strict)", "retry rate %", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_gov_new, "llm_fail_n")
        add_cell("flood", "governed (strict)", "LLM failures", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_gov_new, "fallback_pct")
        add_cell("flood", "governed (strict)", "governance fallback %", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_gov_new, "wall_hours")
        add_cell("flood", "governed (strict)", "wall h per run", new_mean=nm, new_sd=nsd,
                 old_status="no_record")

        old_vals = [flood_dis_old_ibr["ibr_uncond_final"][old_seed]
                    for _, old_seed in flood_old_positions_dis]
        om, osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_dis_new, "ibr_headline")
        add_cell("flood", "no-validator", "IBR headline", om, osd, nm, nsd)
        old_vals = [flood_dis_old_ehe[old_seed] for _, old_seed in flood_old_positions_dis]
        om, osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_dis_new, "ehe_pooled")
        add_cell("flood", "no-validator", "EHE pooled (executed)", om, osd, nm, nsd)
        add_cell("flood", "no-validator", "EHE pooled (proposal)", om, osd, nm, nsd,
                 note="identical to EHE pooled (executed) -- flood's proposal/final/executed "
                      "levels coincide row-for-row, proven in r23/r24 (0 mismatches)")
        old_vals = [flood_dis_old_domain[old_seed] for _, old_seed in flood_old_positions_dis]
        ref_om, ref_osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_dis_new, "final_year_protection_pct")
        if corpus == "v08":
            # EXACT original note text, verbatim -- byte-identity contract.
            add_cell("flood", "no-validator", "domain outcome: final-year protection %",
                     new_mean=nm, new_sd=nsd, old_status="no_record",
                     note=f"no old value for THIS metric (simulation_log boolean OR, "
                          f"relocated counts as protected) -- the old raw simulation_log no "
                          f"longer exists. A DIFFERENT metric (audit-based, 100-share_do_"
                          f"nothing at year 10) has an old value of {ref_om:.1f}+/-"
                          f"{ref_osd:.1f}% from r2_flood_trajectories.csv, kept for "
                          f"reference only, not substituted")
        else:
            add_cell("flood", "no-validator", "domain outcome: final-year protection %",
                     ref_om, ref_osd, nm, nsd,
                     note=f"comparator = v08/faf1bb12 (live) {ref_om:.1f}+/-{ref_osd:.1f}% "
                          f"-- NOT r2_flood_trajectories.csv's audit-based metric")
        old_vals = [flood_dis_old_rej[old_seed] for _, old_seed in flood_old_positions_dis]
        om, osd = C.mean(old_vals), C.sd(old_vals)
        nm, nsd = agg(flood_dis_new, "rejection_rate_pct")
        add_cell("flood", "no-validator", "rejection rate %", om, osd, nm, nsd)
        nm, nsd = agg(flood_dis_new, "retry_rate_pct")
        add_cell("flood", "no-validator", "retry rate %", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_dis_new, "llm_fail_n")
        add_cell("flood", "no-validator", "LLM failures", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_dis_new, "fallback_pct")
        add_cell("flood", "no-validator", "governance fallback %", new_mean=nm, new_sd=nsd,
                 old_status="no_record")
        nm, nsd = agg(flood_dis_new, "wall_hours")
        add_cell("flood", "no-validator", "wall h per run", new_mean=nm, new_sd=nsd,
                 old_status="no_record")

    # ---- flood rule-based ----
    add_cell("flood", "rule-based", "IBR headline", old_status="na", new_status="na",
             note="no threat-appraisal (construct_TP_LABEL) column in the rule-based "
                  "simulation_log -- R1/R3/R4 all condition on it, so IBR is undefined "
                  "for this row, not silently substituted")
    om, osd = agg(flood_rb_old, "ehe_pooled")
    nm, nsd = agg(flood_rb_new, "ehe_pooled")
    # Crosscheck LIVE against gen_fig3_regen.py's own _ehe_from_decisions(),
    # called directly on the same 5 rule-based DataFrames `fig3_data` already
    # loaded above (read-only, no hardcoded literals) -- mean matches at any
    # ddof; gen_fig3's own printed sd is numpy .std()'s DEFAULT ddof=0
    # population sd, NOT this package's ddof=1 sample sd convention used
    # everywhere else -- reported alongside, not silently substituted.
    fig3_rb_ehe_vals = [FIG3._ehe_from_decisions(df["yearly_decision"])
                        for df in fig3_data["rulebased"]]
    if len(fig3_rb_ehe_vals) != 5:
        raise PrepError(f"gen_fig3 rulebased EHE: expected 5 runs, got "
                         f"{len(fig3_rb_ehe_vals)}")
    fig3_rb_mean = sum(fig3_rb_ehe_vals) / len(fig3_rb_ehe_vals)
    fig3_rb_sd_pop = (sum((x - fig3_rb_mean) ** 2 for x in fig3_rb_ehe_vals)
                       / len(fig3_rb_ehe_vals)) ** 0.5
    rb_new_vals = [flood_rb_new[s]["ehe_pooled"] for s in SEEDS5]
    rb_new_mean = C.mean(rb_new_vals)
    if abs(rb_new_mean - fig3_rb_mean) > 0.001:
        raise PrepError(f"flood rule-based EHE mean {rb_new_mean:.4f} (this script) vs "
                         f"{fig3_rb_mean:.4f} (live gen_fig3_regen.py._ehe_from_decisions) "
                         f"-- mapping fix did not reproduce the figure")
    print(f"  crosscheck OK: flood rule-based EHE (new) = {rb_new_mean:.3f} (this script, "
          f"ddof=1 sd={nsd:.3f}) vs {fig3_rb_mean:.3f} +/- {fig3_rb_sd_pop:.3f} (live "
          f"gen_fig3_regen.py._ehe_from_decisions, ddof=0 population sd)")
    add_cell("flood", "rule-based", "EHE pooled (executed)", om, osd, nm, nsd,
             note=f"mapping matches gen_fig3_regen.py's _rulebased_action exactly "
                  f"(live crosscheck via FIG3._ehe_from_decisions: mean {fig3_rb_mean:.3f} "
                  f"= this script's {nm:.3f}; this script's sd {nsd:.3f} is ddof=1 sample "
                  f"sd per package convention, gen_fig3's own ddof=0 population sd for "
                  f"the same 5 values is {fig3_rb_sd_pop:.3f} -- both reported, not "
                  f"silently reconciled)")
    add_cell("flood", "rule-based", "EHE pooled (proposal)", old_status="na", new_status="na",
             note="no separate proposal stage in a deterministic rule-based baseline "
                  "(unlike FQL, there is no raw-vs-blocked distinction here)")
    om, osd = agg(flood_rb_old, "final_year_protection_pct")
    nm, nsd = agg(flood_rb_new, "final_year_protection_pct")
    add_cell("flood", "rule-based", "domain outcome: final-year protection %", om, osd, nm, nsd,
             note="same rule as governed/no-validator (simulation_log boolean OR, "
                  "relocated counts as protected, all 100 agents, year 10) -- old and "
                  "new both computable here since the old raw simulation_log for "
                  "rule-based (unlike governed/no-validator) was never destroyed")
    for col in ("rejection rate %", "retry rate %", "LLM failures", "governance fallback %"):
        add_cell("flood", "rule-based", col, old_status="na", new_status="na",
                  note="rule-based has no LLM audit trail")
    om, osd = agg(flood_rb_old, "wall_hours")
    nm, nsd = agg(flood_rb_new, "wall_hours")
    add_cell("flood", "rule-based", "wall h per run", om, osd, nm, nsd)

    # =====================================================================
    # MEAD KGE COLUMN (2026-09-20 follow-up) + gemma4:12b cross-model block
    # =====================================================================
    # Read out/r28_trajectory_vs_traditional.csv (READ-ONLY -- r28 is under
    # review, not modified here, not even imported as a module, just its
    # own already-committed output CSV). row_type=irr_pair rows carry one
    # KGE value per (model, arm, seed, series, reference); this script
    # aggregates them, it does not recompute the KGE itself.
    r28_path = os.path.join(C.OUT, "r28_trajectory_vs_traditional.csv")
    if not os.path.isfile(r28_path):
        raise PrepError(f"missing {r28_path} -- run r28_trajectory_vs_traditional.py first")
    r28_rows_all = C.read_csv(r28_path)

    def _kge_from_r28(model: str, arm: str) -> tuple:
        matches = [r for r in r28_rows_all if r["row_type"] == "irr_pair"
                   and r["model"] == model and r["arm"] == arm
                   and r["series"] == "mead_elevation" and r["reference"] == "matched"]
        seeds = sorted({r["seed"] for r in matches})
        if len(matches) != 5 or len(seeds) != 5:
            raise PrepError(f"r28_trajectory_vs_traditional.csv: expected 5 irr_pair rows "
                             f"(one per seed) for model={model} arm={arm} "
                             f"series=mead_elevation reference=matched, got {len(matches)} "
                             f"rows across seeds {seeds} -- re-run r28 first")
        vals = [float(r["kge"]) for r in matches]
        return C.mean(vals), C.sd(vals)

    # ---- existing (case, arm) rows: irrigation governed/ungoverned get a
    # real number; irrigation FQL rows and all flood rows are n.a. with an
    # explicit reason (per task: "reference model itself" / "not
    # applicable, categorical") -- old side is `no old record`/`n.a.`
    # either way, since this KGE analysis (r28) never existed for any old
    # corpus.
    nm, nsd = _kge_from_r28("gemma3_4b", "strict")
    add_cell("irrigation", "governed (strict)", KGE_COL, new_mean=nm, new_sd=nsd,
             old_status="no_record", n_old=0)
    nm, nsd = _kge_from_r28("gemma3_4b", "ungoverned")
    add_cell("irrigation", "ungoverned", KGE_COL, new_mean=nm, new_sd=nsd,
             old_status="no_record", n_old=0)
    for arm in ("irrigation rule-based FQL matched (no-rebalance)",
                "irrigation rule-based FQL rebalanced"):
        add_cell("irrigation", arm, KGE_COL, old_status="na", new_status="na",
                 note="reference model itself")
    for arm in ("governed (strict)", "no-validator", "rule-based"):
        add_cell("flood", arm, KGE_COL, old_status="na", new_status="na",
                 note="not applicable, categorical")

    # ---- gemma4:12b (c3391a53), new corpus only -- second Table 1 block.
    # Values are READ from r26/r27's own already-computed per-seed
    # row_type=metrics rows and aggregated here (mean/sd over the 5
    # seeds) -- never recomputed from raw audit/simulation_log files.
    # Distinct case labels ("irrigation (gemma4:12b)" / "flood
    # (gemma4:12b)") keep these cells from colliding with the
    # gemma3:4b-corpus cells above in the shared `cells` lookup dict.
    # r26 (flood): corpus-suffixed, reused verbatim -- see --corpus docstring.
    # r27 (irrigation): ALWAYS the v08 file, unaffected by --corpus (r27 has
    # no --corpus switch; "irrigation untouched" applies here too).
    r26_csv_name = f"r26_flood_crossmodel_gemma4_12b{suffix}.csv"
    r26_path = os.path.join(C.OUT, r26_csv_name)
    r27_path = os.path.join(C.OUT, "r27_irrigation_crossmodel_gemma4_12b.csv")
    for p in (r26_path, r27_path):
        if not os.path.isfile(p):
            raise PrepError(f"missing {p} -- run its generating script first")
    r26_metrics = [r for r in C.read_csv(r26_path) if r["row_type"] == "metrics"]
    r27_metrics = [r for r in C.read_csv(r27_path) if r["row_type"] == "metrics"]

    def _agg_metric_rows(src_rows: list, arm: str, src_col: str) -> tuple:
        sub = [r for r in src_rows if r["arm"] == arm]
        seeds = sorted({r["seed"] for r in sub})
        if len(sub) != 5 or len(seeds) != 5:
            raise PrepError(f"expected 5 metrics rows (one per seed) for arm={arm!r}, got "
                             f"{len(sub)} across seeds {seeds}")
        vals = [float(r[src_col]) for r in sub]
        return C.mean(vals), C.sd(vals)

    def _agg_metric_rows_or_pending(src_rows: list, arm: str, src_col: str):
        """Like _agg_metric_rows, but returns None (never raises) if `arm`
        has 0 metrics rows in `src_rows` -- the r26 --corpus {corpus} run
        being itself PENDING (0 landed seeds) is expected, not a data bug."""
        sub = [r for r in src_rows if r["arm"] == arm]
        if not sub:
            return None
        return _agg_metric_rows(src_rows, arm, src_col)

    # NOTE on row count: the task described this block as "the six
    # irrigation/flood LLM rows (strict/no-validator x two cases)", but
    # r26 (flood) only has 2 gemma4:12b arms on disk (strict, disabled)
    # and r27 (irrigation) only has 2 (strict, ungoverned) -- 2 arms x 2
    # cases = 4 distinct (case, arm) combinations exist in the data, not
    # 6. Implemented all 4 that actually exist rather than fabricate 2
    # more; flagged for the coordinator rather than silently matching an
    # unreachable count.
    IRR_12B_COLMAP = [
        ("IBR headline", "metric__IBR headline"),
        ("EHE pooled (executed)", "metric__EHE pooled (executed)"),
        ("EHE pooled (proposal)", "metric__EHE pooled (proposal)"),
        ("domain outcome: Mead min (ft)", "metric__Mead minimum (ft)"),
        ("domain outcome: shortage years", "metric__Shortage years"),
        ("rejection rate %", "metric__Rejection rate (%)"),
        ("retry rate %", "metric__Retry rate (%)"),
        ("LLM failures", "llm_fail_n"),
        ("governance fallback %", "fallback_share_pct"),
        ("wall h per run", "wall_hours"),
    ]
    for src_arm, disp_arm in (("strict", "governed (strict)"), ("ungoverned", "ungoverned")):
        for disp_col, src_col in IRR_12B_COLMAP:
            nm, nsd = _agg_metric_rows(r27_metrics, src_arm, src_col)
            add_cell("irrigation (gemma4:12b)", disp_arm, disp_col, new_mean=nm, new_sd=nsd,
                     old_status="no_record", n_old=0)
        nm, nsd = _kge_from_r28("gemma4_12b", src_arm)
        add_cell("irrigation (gemma4:12b)", disp_arm, KGE_COL, new_mean=nm, new_sd=nsd,
                 old_status="no_record", n_old=0)

    # metric__EHE pooled simlog maps onto BOTH the executed and proposal
    # columns for flood -- identical, same convention r25 already uses
    # for flood governed/no-validator above ("identical to EHE pooled
    # (executed) -- flood's proposal/final/executed levels coincide").
    FLOOD_12B_COLMAP = [
        ("IBR headline", "metric__IBR unconditional (%)"),
        ("EHE pooled (executed)", "metric__EHE pooled simlog"),
        ("EHE pooled (proposal)", "metric__EHE pooled simlog"),
        ("rejection rate %", "metric__Rejection rate (%)"),
        ("retry rate %", "metric__Retry rate (%)"),
        ("LLM failures", "llm_fail_n"),
        ("governance fallback %", "fallback_share_pct"),
        ("wall h per run", "wall_hours"),
    ]
    for src_arm, disp_arm in (("strict", "governed (strict)"), ("disabled", "no-validator")):
        for disp_col, src_col in FLOOD_12B_COLMAP:
            agg_result = _agg_metric_rows_or_pending(r26_metrics, src_arm, src_col)
            if agg_result is None:
                add_cell("flood (gemma4:12b)", disp_arm, disp_col, old_status="pending",
                         new_status="pending", n_old=0, n_new=0,
                         note=f"{r26_csv_name} has 0 metrics rows for arm={src_arm!r} yet "
                              f"(that script's own --corpus {corpus} run is itself pending)")
                continue
            nm, nsd = agg_result
            add_cell("flood (gemma4:12b)", disp_arm, disp_col, new_mean=nm, new_sd=nsd,
                     old_status="no_record", n_old=0)
        add_cell("flood (gemma4:12b)", disp_arm, "domain outcome: final-year protection %",
                 old_status="na", new_status="na",
                 note="not computed by r26 for the gemma4:12b corpus -- would require "
                      "recomputation from simulation_log.csv, out of scope for this "
                      "reuse-only cross-model block (task: do not recompute)")
        add_cell("flood (gemma4:12b)", disp_arm, KGE_COL, old_status="na", new_status="na",
                 note="not applicable, categorical")

    # =====================================================================
    # CONTRAST BLOCK -- governed vs ungoverned, diff = ungoverned - governed
    # =====================================================================
    def emit_contrast(case, metric_label, gov_old, ungov_old, gov_new, ungov_new, seeds):
        for corpus, gov_d, ungov_d in (("old", gov_old, ungov_old), ("new", gov_new, ungov_new)):
            diffs = []
            for s in seeds:
                gv, uv = gov_d[s], ungov_d[s]
                d = uv - gv
                diffs.append(d)
                rows.append({"row_type": "contrast_pair", "case": case, "metric": metric_label,
                              "corpus": corpus, "seed": s, "governed_value": gv,
                              "ungoverned_value": uv, "diff": d})
            t, df = C.paired_t(diffs)
            mean_d, sd_d = C.mean(diffs), C.sd(diffs)
            n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
            same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
            rows.append({
                "row_type": "contrast_stat", "case": case, "metric": metric_label,
                "corpus": corpus, "n_pairs": len(diffs), "mean_diff": mean_d, "sd_diff": sd_d,
                "min_diff": min(diffs), "max_diff": max(diffs), "n_sign_flips": n_flips,
                "all_same_sign": same_sign, "t": t, "df": float(df),
                "p_paired_t": C.t_two_sided_p(t, df), "p_exact_permutation": C.exact_perm_p(diffs),
                "permutation_floor": 2.0 / (1 << len(diffs)),
            })

    irr_gov_old_by_seed = {s: irr_gov_old[s]["ibr_headline"] for s in SEEDS5}
    irr_ungov_old_by_seed = {s: irr_ungov_old[s]["ibr_headline"] for s in SEEDS5}
    irr_gov_new_by_seed = {s: irr_gov_new[s]["ibr_headline"] for s in SEEDS5}
    irr_ungov_new_by_seed = {s: irr_ungov_new[s]["ibr_headline"] for s in SEEDS5}
    emit_contrast("irrigation", "IBR headline", irr_gov_old_by_seed, irr_ungov_old_by_seed,
                  irr_gov_new_by_seed, irr_ungov_new_by_seed, SEEDS5)

    irr_gov_old_ehe = {s: irr_gov_old[s]["ehe_pooled"] for s in SEEDS5}
    irr_ungov_old_ehe = {s: irr_ungov_old[s]["ehe_pooled"] for s in SEEDS5}
    irr_gov_new_ehe = {s: irr_gov_new[s]["ehe_pooled"] for s in SEEDS5}
    irr_ungov_new_ehe = {s: irr_ungov_new[s]["ehe_pooled"] for s in SEEDS5}
    emit_contrast("irrigation", "EHE pooled", irr_gov_old_ehe, irr_ungov_old_ehe,
                  irr_gov_new_ehe, irr_ungov_new_ehe, SEEDS5)

    # flood: READ r24's own already-computed + r7-cross-checked contrast, do not
    # recompute -- r24_flood_contrast_regen{suffix}.csv is the single source
    # of truth. NOTE: the loop variable below is named `data_corpus`
    # (r24's own "old"/"new" row tag, unrelated to this script's --corpus
    # flag) precisely so it never shadows the outer `corpus` variable --
    # a bare `for corpus in (...)` here would silently leave `corpus`
    # holding "new" for every line below it, corrupting the suffix/label
    # logic further down.
    r24_csv_name = f"r24_flood_contrast_regen{suffix}.csv"
    r24_path = os.path.join(C.OUT, r24_csv_name)
    if not os.path.isfile(r24_path):
        raise PrepError(f"missing {r24_path} -- run r24_flood_contrast_regen.py "
                         f"--corpus {corpus} first")
    r24_rows = C.read_csv(r24_path)
    r24_has_contrast = any(rr.get("row_type") == "contrast_stat" for rr in r24_rows)
    if not r24_has_contrast:
        for metric_label in ("IBR headline", "EHE pooled"):
            for data_corpus in ("old", "new"):
                rows.append({"row_type": "contrast_stat", "case": "flood",
                             "metric": metric_label, "corpus": data_corpus,
                             "note": f"PENDING -- {r24_csv_name} has no contrast_stat rows "
                                     f"yet (r24 --corpus {corpus} is itself pending)"})
        print(f"  flood contrast: PENDING -- {r24_csv_name} has no contrast_stat rows yet")
    else:
        for metric_label, r24_label in (("IBR headline", "IBR unconditional (%)"),
                                         ("EHE pooled", "EHE pooled simlog")):
            for data_corpus in ("old", "new"):
                r = next((rr for rr in r24_rows if rr["row_type"] == "contrast_stat"
                          and rr["corpus"] == data_corpus and rr["metric"] == r24_label), None)
                if r is None:
                    raise PrepError(f"{r24_csv_name}: no contrast_stat row for "
                                     f"corpus={data_corpus} metric={r24_label!r}")
                rows.append({
                    "row_type": "contrast_stat", "case": "flood", "metric": metric_label,
                    "corpus": data_corpus, "n_pairs": int(r["n_pairs"]),
                    "mean_diff": float(r["mean_diff"]), "sd_diff": float(r["sd_diff"]),
                    "min_diff": float(r["min_diff"]), "max_diff": float(r["max_diff"]),
                    "n_sign_flips": int(r["n_sign_flips"]),
                    "all_same_sign": r["all_same_sign"] == "True", "t": float(r["t"]),
                    "df": float(r["df"]), "p_paired_t": float(r["p_paired_t"]),
                    "p_exact_permutation": float(r["p_exact_permutation"]),
                    "permutation_floor": float(r["permutation_floor"]),
                    "note": f"read verbatim from out/{r24_csv_name} "
                            "(row_type=contrast_stat), not recomputed",
                })
        print(f"  flood contrast rows read verbatim from out/{r24_csv_name}")

    fieldnames = ["row_type", "case", "arm", "column", "old_mean", "old_sd", "new_mean",
                  "new_sd", "old_status", "new_status", "n_old", "n_new", "note", "metric",
                  "corpus", "seed", "governed_value", "ungoverned_value", "diff", "n_pairs",
                  "mean_diff", "sd_diff", "min_diff", "max_diff", "n_sign_flips",
                  "all_same_sign", "t", "df", "p_paired_t", "p_exact_permutation",
                  "permutation_floor", "flips"]
    C.write_csv(f"r25_table1_regen{suffix}.csv", fieldnames, rows)

    md_text = render_md(rows, corpus)
    md_path = os.path.join(C.OUT, f"r25_table1_regen{suffix}.md")
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(md_text)
    print(f"\n  wrote {os.path.relpath(md_path, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")

    return 0


# ---------------------------------------------------------------------------
# .md rendering -- built entirely from the `rows` list above.
# ---------------------------------------------------------------------------
ROW_ORDER = [
    ("irrigation", "governed (strict)"), ("irrigation", "ungoverned"),
    ("irrigation", "irrigation rule-based FQL rebalanced"),
    ("irrigation", "irrigation rule-based FQL matched (no-rebalance)"),
    ("flood", "governed (strict)"), ("flood", "no-validator"), ("flood", "rule-based"),
]
# 2026-09-20 follow-up: gemma4:12b (c3391a53), new-corpus-only second Table 1
# block. Distinct case labels keep these cells out of the gemma3:4b `cells`
# lookup namespace above. See main()'s NOTE on why this is 4 rows, not the
# 6 the task described -- r26/r27 only have 2 gemma4:12b arms each on disk.
ROW_ORDER_12B = [
    ("irrigation (gemma4:12b)", "governed (strict)"),
    ("irrigation (gemma4:12b)", "ungoverned"),
    ("flood (gemma4:12b)", "governed (strict)"),
    ("flood (gemma4:12b)", "no-validator"),
]
KGE_COL = "Mead KGE vs FQL (matched)"
COLUMN_ORDER = [
    "IBR headline", "EHE pooled (executed)", "EHE pooled (proposal)",
    "domain outcome: Mead min (ft)",
    "domain outcome: shortage years", "domain outcome: final-year protection %",
    "rejection rate %", "retry rate %", "LLM failures", "governance fallback %",
    "wall h per run",
    KGE_COL,  # 2026-09-20 follow-up, appended at the END so every pre-existing
              # cell/column position is unchanged.
]


_cp = R23._csv_precision  # round through the CSV's own stored 4dp precision before
                           # display, so a .md number always reproduces from the CSV
                           # cell it's sourced from (same double-rounding fix as r23).


def _cell_str(r, nd=3) -> str:
    def side(mean_, sd_, status):
        if status == "na":
            return NA
        if status == "no_record":
            return NO_OLD if mean_ is None else NO_OLD  # old side only ever no_record here
        if status == "pending":
            return "PENDING"
        return f"{_cp(float(mean_)):.{nd}f} +/- {_cp(float(sd_)):.{nd}f}"
    old_side = side(r["old_mean"], r["old_sd"], r["old_status"])
    new_side = side(r["new_mean"], r["new_sd"], r["new_status"])
    return f"{old_side} / {new_side}"


def render_md(rows: list, corpus: str = "v08") -> str:
    cells = {(r["case"], r["arm"], r["column"]): r
             for r in rows if r["row_type"] == "table1_cell"}
    contrast = {(r["case"], r["metric"], r["corpus"]): r
                for r in rows if r["row_type"] == "contrast_stat"}
    flip_rows = [r for r in rows if r["row_type"] == "flip_check"]
    # 3 arms x 5 seeds x 3 columns = 45 under v08 (always) or defaults with
    # flood_available; 1 arm (rule-based only) x 5 seeds x 3 columns = 15
    # under defaults while governed/no-validator are still PENDING.
    if len(flip_rows) not in (45, 15):
        raise PrepError(f"render_md: expected 45 (all 3 arms) or 15 (rule-based only, "
                         f"defaults corpus pending) flip_check rows, got {len(flip_rows)}")
    for r in flip_rows:
        if r["column"] in ("elevated", "relocated") and int(r["flips"]) != 0:
            raise PrepError(f"render_md: {r['column']} flips={r['flips']} != 0 for "
                             f"arm={r['arm']} seed={r['seed']} -- sticky claim is false, "
                             f"caught again at render time")
    has_ins_flips = [int(r["flips"]) for r in flip_rows if r["column"] == "has_insurance"]
    has_ins_min, has_ins_max = min(has_ins_flips), max(has_ins_flips)

    lines = []
    lines.append("# R25 -- paper Table 1, old vs new, all governance arms, 2026-09-17")
    lines.append("")
    if corpus != "v08":
        lines.append(
            f"> **Flood corpus: {corpus}.** {C.flood_sampling_method_text(corpus)}. "
            f"Irrigation rows are UNCHANGED (always the v08 corpus). Flood comparator "
            f"(\"old\" column) = the v08/faf1bb12 corpus computed live, NOT the "
            f"pre-quarantine published corpus the v08 run of this script uses."
        )
        lines.append("")
    lines.append(
        "**Method.** Cell = \"old mean +/- sd / new mean +/- sd\" (ddof=1, n=5 seeds "
        "42-46 on every row, including FQL which has 10 old+10 new seeds on disk -- "
        "only the first 5 are used here to match every other row). `n.a.` = the arm "
        "has no such quantity; `no old record` = the quantity applies but no old "
        "per-seed value exists in any out/*.csv (checked, never invented). "
        "**Irrigation EHE (round-2 fix):** r25's `EHE pooled (executed)` is NOT sourced "
        "from any function in `examples/irrigation_abm/analysis/` -- it is inline code "
        "matching `r14_advise_arm.py`'s own convention (`audit_executed_metrics`), built "
        "on `_common.py::irr_executed` + `_common.py::normalized_entropy`. The canonical "
        "analysis module DOES expose a second definition: "
        "`examples/irrigation_abm/analysis/a1_ablation_metrics.py::ehe_5skill` (its own "
        "docstring: \"primary metric -- paper uses k=5 for irrigation\"), pooled entropy "
        "over simulation_log `yearly_decision` (proposal-level, k=5) -- added here as the "
        "separate `EHE pooled (proposal)` column (matches r14's own `ehe_pooled_proposal` "
        "column and regen_progress's \"EHE pooled, proposal\" row, crosschecked below). "
        "IBR headline = proposal-level conditional high-WSA increase rate (`_loader.ibr`, "
        "simulation_log). FQL's IBR/EHE use a LOCAL 3-category definition "
        "(`increase_demand` vs the LLM's 5-skill vocabulary); its EHE is k=3, its "
        "proposal-level IBR reads the RAW pre-block `fql_raw_skill` column, not "
        "`yearly_decision` (which is already post-block executed -- see docstring). "
        "**Flood EHE / protection-share (round-2/3 fix):** rule-based EHE now uses the "
        "EXACT same action classification as "
        "`paper/nature_water/scripts/regen/gen_fig3_regen.py::_rulebased_action` "
        "(elevated+has_insurance -> buy_insurance, elevated alone -> elevate_house, "
        "has_insurance alone -> buy_insurance, relocated -> relocate, else do_nothing), "
        "crosschecked LIVE against a direct call into "
        "`gen_fig3_regen.py::_ehe_from_decisions` (imported read-only, no hardcoded "
        "reference numbers -- see the EHE pooled (executed)/rule-based per-cell caveat "
        "below for the live mean/sd this run actually produced) -- gen_fig3's own sd "
        "convention is numpy `.std()`'s DEFAULT ddof=0 population sd, NOT this package's "
        "ddof=1 sample sd (`_loader.py::sd`'s docstring: \"Sample standard deviation "
        "(n-1)\"); both are reported, never silently reconciled into one. \"Final-year "
        "share with any protection\" is computed IDENTICALLY for all three flood arms "
        "from simulation_log.csv's own boolean columns at year=10: elevated OR "
        "has_insurance OR RELOCATED (relocated counts as protected -- the one rule, "
        "applied everywhere), crosschecked against gen_fig3's own "
        "`_classify_state_from_cols` pooled-all-year complement of \"No protection\" "
        "(gen_fig3 has no year-10-only print, so the crosscheck is on the all-year-"
        "pooled share, not the year-10 slice actually reported in Table 1). "
        f"`elevated` and `relocated` never revert (0 flips in all 15 runs); "
        f"`has_insurance` lapses and is repurchased ({has_ins_min}-{has_ins_max} "
        f"True->False flips per run, see the flip-check table below), so the year-10 "
        f"protection share mixes cumulative uptake (elevation, relocation) with a "
        f"year-10 snapshot (insurance) -- values are far higher than the AUDIT-based "
        f"method this script used before the round-2 fix. Governed/no-validator's OLD "
        f"side for this metric is `no old record` (the old raw simulation_log no longer "
        f"exists); the old AUDIT-based number from `r2_flood_trajectories.csv` is kept "
        f"as a reference note only, a different metric, never substituted."
    )
    lines.append("")
    header = "| case / arm | n (old / new seeds) | " + " | ".join(COLUMN_ORDER) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(COLUMN_ORDER) + 2))
    for case, arm in ROW_ORDER:
        any_cell = next((cells[(case, arm, c)] for c in COLUMN_ORDER
                          if (case, arm, c) in cells), None)
        n_str = f"{any_cell['n_old']}/{any_cell['n_new']}" if any_cell else "?"
        cell_strs = []
        for col in COLUMN_ORDER:
            key = (case, arm, col)
            if key not in cells:
                cell_strs.append(NA)
                continue
            cell_strs.append(_cell_str(cells[key]))
        lines.append(f"| {case}: {arm} | {n_str} | " + " | ".join(cell_strs) + " |")
    lines.append("")

    no_old_cells = [f"{case}/{arm}/{col}" for case, arm in ROW_ORDER for col in COLUMN_ORDER
                    if (case, arm, col) in cells and cells[(case, arm, col)]["old_status"]
                    == "no_record"]
    lines.append(f"Cells with `no old record` ({len(no_old_cells)}): "
                 + "; ".join(no_old_cells))
    lines.append("")

    notes = [(f"{case}/{arm}/{col}", cells[(case, arm, col)]["note"])
             for case, arm in ROW_ORDER for col in COLUMN_ORDER
             if (case, arm, col) in cells and cells[(case, arm, col)].get("note")]
    if notes:
        lines.append("Per-cell caveats:")
        for k, note in notes:
            lines.append(f"- {k}: {note}")
        lines.append("")

    # =========================================================================
    # SECOND TABLE 1 BLOCK -- gemma4:12b (c3391a53), new corpus only
    # (2026-09-20 follow-up). Every cell's old side is `no old record` or
    # `n.a.` -- no old corpus exists for gemma4:12b at all, by definition.
    # =========================================================================
    lines.append("## Table 1 -- gemma4:12b (c3391a53), new corpus only")
    lines.append("")
    lines.append(
        "Same columns as the table above (last column `Mead KGE vs FQL (matched)` added "
        "2026-09-20, sourced from `out/r28_trajectory_vs_traditional.csv`). Every cell here "
        "has NO old-corpus counterpart -- gemma4:12b never had an old/pre-loss run -- so "
        "every old side reads `no old record` (for a real new-side number) or `n.a.` (where "
        "the metric does not apply, same as the table above). Values are READ from "
        "`out/r26_flood_crossmodel_gemma4_12b.csv` / "
        "`out/r27_irrigation_crossmodel_gemma4_12b.csv` row_type=metrics and aggregated "
        "here (mean +/- sd over 5 seeds), never recomputed from raw audit/simulation_log "
        "files. NOTE: only 4 (case, arm) rows exist on disk for gemma4:12b (irrigation "
        "strict/ungoverned from r27, flood strict/disabled from r26) -- 2 arms x 2 domains, "
        "not 6."
    )
    lines.append("")
    lines.append(header)
    lines.append("|" + "---|" * (len(COLUMN_ORDER) + 2))
    for case, arm in ROW_ORDER_12B:
        any_cell = next((cells[(case, arm, c)] for c in COLUMN_ORDER
                          if (case, arm, c) in cells), None)
        n_str = f"{any_cell['n_old']}/{any_cell['n_new']}" if any_cell else "?"
        cell_strs = []
        for col in COLUMN_ORDER:
            key = (case, arm, col)
            if key not in cells:
                cell_strs.append(NA)
                continue
            cell_strs.append(_cell_str(cells[key]))
        lines.append(f"| {case}: {arm} | {n_str} | " + " | ".join(cell_strs) + " |")
    lines.append("")

    notes_12b = [(f"{case}/{arm}/{col}", cells[(case, arm, col)]["note"])
                 for case, arm in ROW_ORDER_12B for col in COLUMN_ORDER
                 if (case, arm, col) in cells and cells[(case, arm, col)].get("note")]
    if notes_12b:
        lines.append("Per-cell caveats (gemma4:12b block):")
        for k, note in notes_12b:
            lines.append(f"- {k}: {note}")
        lines.append("")

    lines.append("## Flip-check: True->False agent-year transitions, new corpus, per "
                 "(arm, column), across the 5 seeds")
    lines.append("")
    lines.append("| arm | elevated | has_insurance | relocated |")
    lines.append("|---|---:|---:|---:|")
    flip_arm_labels = sorted({r["arm"] for r in flip_rows})
    for arm_label in ("governed (strict)", "no-validator", "rule-based"):
        if arm_label not in flip_arm_labels:
            lines.append(f"| {arm_label} | PENDING | PENDING | PENDING |")
            continue
        cell_vals = []
        for col in ("elevated", "has_insurance", "relocated"):
            vals = [int(r["flips"]) for r in flip_rows
                    if r["arm"] == arm_label and r["column"] == col]
            if len(vals) != 5:
                raise PrepError(f"flip table: expected 5 seeds for arm={arm_label} "
                                 f"col={col}, got {len(vals)}")
            cell_vals.append(f"{min(vals)}-{max(vals)} (mean {sum(vals) / 5:.1f})")
        lines.append(f"| {arm_label} | " + " | ".join(cell_vals) + " |")
    lines.append("")

    lines.append("## Governed-vs-ungoverned contrast (diff = ungoverned - governed)")
    lines.append("")
    lines.append("| case | metric | corpus | mean_diff +/- sd | p_paired_t | "
                  "p_exact_perm | sign-consistent |")
    lines.append("|---|---|---|---:|---:|---:|:---:|")
    # `data_corpus` (r24's own "old"/"new" row tag) -- never named `corpus`
    # here, so it cannot shadow this function's own `corpus` parameter
    # ("v08"/"defaults"), even though nothing below this loop still needs it.
    for case in ("irrigation", "flood"):
        for metric in ("IBR headline", "EHE pooled"):
            for data_corpus in ("old", "new"):
                st = contrast[(case, metric, data_corpus)]
                if "mean_diff" not in st:
                    lines.append(f"| {case} | {metric} | {data_corpus} | PENDING | -- | -- "
                                 f"| -- |")
                    continue
                lines.append(
                    f"| {case} | {metric} | {data_corpus} | {_cp(st['mean_diff']):.3f} +/- "
                    f"{_cp(st['sd_diff']):.3f} | {_cp(st['p_paired_t']):.4f} | "
                    f"{_cp(st['p_exact_permutation']):.4f} | {st['all_same_sign']} |"
                )
    lines.append("")

    irr_ibr_old = contrast[("irrigation", "IBR headline", "old")]
    irr_ibr_new = contrast[("irrigation", "IBR headline", "new")]
    flood_ibr_old = contrast[("flood", "IBR headline", "old")]
    flood_ibr_new = contrast[("flood", "IBR headline", "new")]
    if "mean_diff" in flood_ibr_old and "mean_diff" in flood_ibr_new:
        lines.append(
            f"Both cases reproduce the governed-vs-ungoverned direction on the new corpus: "
            f"irrigation IBR headline mean_diff {_cp(irr_ibr_old['mean_diff']):.2f} pp old vs "
            f"{_cp(irr_ibr_new['mean_diff']):.2f} pp new (sign-consistent "
            f"old={irr_ibr_old['all_same_sign']}, new={irr_ibr_new['all_same_sign']}); "
            f"flood IBR headline mean_diff {_cp(flood_ibr_old['mean_diff']):.2f} pp old vs "
            f"{_cp(flood_ibr_new['mean_diff']):.2f} pp new (sign-consistent "
            f"old={flood_ibr_old['all_same_sign']}, new={flood_ibr_new['all_same_sign']})."
        )
    else:
        lines.append(
            f"Irrigation reproduces the governed-vs-ungoverned direction on the new "
            f"corpus: IBR headline mean_diff {_cp(irr_ibr_old['mean_diff']):.2f} pp old vs "
            f"{_cp(irr_ibr_new['mean_diff']):.2f} pp new (sign-consistent "
            f"old={irr_ibr_old['all_same_sign']}, new={irr_ibr_new['all_same_sign']}). "
            f"Flood's contrast is PENDING for --corpus {corpus} (the defaults strict/"
            f"disabled 5-seed corpora have not both landed yet)."
        )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
