"""R31 -- flood relocation sensitivity: recompute the flood IBR metrics and
the r28 JS distance with relocate agent-years excluded, next to the
original values, plus the relocation share (reused from r28) and a
common-action-set diversity index. CPU-only, existing runs only, no LLM
calls.

EXACT EXCLUSION RULE (stated once, applied uniformly to every recomputed
metric below): an agent-year is EXCLUDED iff its NORMALIZED action for
that year is "relocate". Normalization is each metric's own existing
canonical function, never reimplemented here:
  - IBR (audit-CSV rows): `_common.py::flood_normalize_action` applied to
    the audit's `final_skill` column (`C.flood_final`, the SAME action
    function r23/r24/r25/r26's "IBR headline" / ibr_uncond_final already
    uses) -- this maps "relocate"/"relocated"/"already_relocated" (all
    three raw spellings observed in this corpus, verified below) to one
    canonical "relocate" token before the equality check.
  - JS distance (simulation_log rows, via `gen_fig3_regen.py`,
    read-only): `_normalise_decision()` applied to `yearly_decision`,
    same three-spelling mapping.
  VERIFIED (not assumed) that this rule captures BOTH the transition
  year AND every persisting post-relocation year, not just the moment of
  relocation: spot-checked JOH_strict_gemma3_4b_faf1bb12/Run_42's most-
  relocated agent, whose `yearly_decision` reads "relocate" in the
  transition year and "relocated" (past tense) in every year after --
  both normalize to "relocate" and are excluded. An agent who relocates
  is therefore removed from the sample for every year from relocation
  onward, not just the one decision year -- this is what "drop agent-
  years whose action is relocate" means in this script, stated so the
  reader does not have to infer it.

PART 1 -- IBR, original vs relocate-excluded, per seed and pooled
  Per (model, arm, seed): the 3 IBR conditionings (uncond, tp_not_medium,
  tp_high) at the "final" action level -- exactly r23/r24/r25/r26's own
  `_rep_metric`/`LEVELS["final"]`/`C.flood_ibr_components` machinery,
  imported not re-derived -- computed on the FULL audit rows (original)
  and on the audit rows with relocate-final agent-years excluded
  (relocate_excluded). "Pooled" = all 5 seeds' (already TP-conditioned,
  already relocate-filtered where applicable) rows concatenated BEFORE
  computing one ibr_pct, not an average of 5 per-seed rates -- reported
  alongside the per-seed mean+-sd, never confused with it. Governed
  (strict) - no-validator (disabled) paired contrast, both versions,
  paired t df=4 / exact permutation / sign consistency (n=5).

PART 2 -- JS distance, original vs relocate-excluded
  Reuses `gen_fig3_regen.py::load_all_runs()`/`PROT_STATES` (imported
  read-only, exactly as r28 does) and this script's own copy of r28's
  `_js_distance`/`_state_dist` logic (r28 is committed, not modified;
  the two helper functions are transcribed verbatim with a comment
  marking the copy, since r28's own versions are private module-level
  functions with no seam to inject a relocate-exclusion filter without
  editing r28 itself). Same 3 comparisons as r28 (gov_vs_rb, dis_vs_rb,
  gov_vs_dis), same per-year -> per-seed-mean -> mean+-sd-over-seeds
  pipeline, computed twice (original / relocate_excluded), plus the
  governed-to-rulebased minus no-validator-to-rulebased paired contrast
  for both versions.

PART 3 -- relocation share (REUSED from r28, not recomputed) + diversity
  index (NEW, on a different variable than r28/r23's EHE)
  Relocation share: `out/r28_trajectory_vs_traditional.csv`
  row_type=flood_relocation_arm_summary rows, read verbatim.
  Diversity index: normalized Shannon entropy (k=5) of the POOLED (all
  years x all seeds pooled into one count table, not averaged per-year)
  `prot_state` distribution, per arm, on `gen_fig3_regen.py`'s own
  PROT_STATES = ['No protection','Insurance only','Elevation only',
  'Insurance + Elevation','Relocated'] -- the SAME 5-state space governed,
  no-validator AND rule-based already share (that is what makes it a
  "common action set... across LLM and rule-based arms", the task's own
  phrasing; it is the STATE space, not the 4-action `_normalise_decision`
  vocabulary, which rule-based and LLM arms do NOT share in the same
  cardinality). Labelled `diversity_index` throughout, never called EHE,
  to avoid confusion with r23's EHE (which pools `yearly_decision`, a
  different variable). Computed original and relocate_excluded (state
  space drops to 4 non-empty categories once "Relocated" rows are
  excluded by construction).

COMPLETENESS GATE
  Missing run dir/audit/simulation_log -> row_type=skipped, printed
  reason, excluded from aggregates/contrasts.

OUTPUTS
  out/r31_flood_relocation_sensitivity.csv -- row_type in {skipped,
    ibr_seed, ibr_pooled, ibr_seed_summary, ibr_contrast, js_seed_mean,
    js_summary, js_contrast, relocation_share, diversity_index}.
  out/r31_flood_relocation_sensitivity.md -- GENERATED by render_md()
    directly from that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r31_flood_relocation_sensitivity.py
        python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r31_flood_relocation_sensitivity.py --corpus defaults

--corpus (added 2026-09-23, see _common.py::flood_corpus_dirs) -- affects
ONLY the gemma3_4b strict/disabled dirs in Part 1/2 (the gemma4_12b rows
have no separate "defaults" corpus concept here and are unaffected -- r26's
own --corpus is orthogonal, not threaded through this script). v08
(default): EXACTLY the behaviour documented above, byte-identical output.
defaults: gemma3_4b strict/disabled read the no-sampling-params re-run;
Part 2's `FIG3.GOV_DIR`/`FIG3.DISABLED_DIR` are monkey-patched at runtime
(never faf1bb12) the same way r28 does it; `FIG3.RULEBASED_DIR` is
unchanged. Every completeness gate already in this script tolerates 0/5
seeds landed (true today for every defaults dir), so Part 1/2/3 already
render PENDING gracefully -- no new PENDING branch was needed. Writes
out/r31_flood_relocation_sensitivity_defaults.{md,csv}.
"""
from __future__ import annotations

import argparse
import math
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r23_flood_strict_regen as R23  # noqa: E402  READ-ONLY: NEW_SEEDS/LEVELS/COND.
import r26_flood_crossmodel_gemma4_12b as R26  # noqa: E402  READ-ONLY: 12b arm roots.
import r28_trajectory_vs_traditional as R28  # noqa: E402  READ-ONLY: FIG3 handle, PROT_STATES.

FIG3 = R28.FIG3  # gen_fig3_regen.py, already imported read-only by r28

SEEDS5 = R23.NEW_SEEDS  # ["42","43","44","45","46"]
MODELS = ["gemma3_4b", "gemma4_12b"]


def _flood_arm_roots(corpus: str) -> dict:
    """{(model, arm): root_dir_name}. gemma3_4b strict/disabled route through
    `C.flood_corpus_dirs(corpus)` (v08 == today's literals, defaults == the
    no-sampling-params re-run); gemma4_12b has no separate defaults corpus
    here, always r26's v08 (c3391a53) roots."""
    strict_root, _ = C.flood_corpus_dirs(corpus)["strict"]
    disabled_root, _ = C.flood_corpus_dirs(corpus)["disabled"]
    return {
        ("gemma3_4b", "strict"): strict_root,
        ("gemma3_4b", "disabled"): disabled_root,
        ("gemma4_12b", "strict"): R26.STRICT_12B_ROOT,
        ("gemma4_12b", "disabled"): R26.DISABLED_12B_ROOT,
    }
IBR_CONDITIONINGS = ["uncond", "tp_not_medium", "tp_high"]
PROT_STATES = R28.PROT_STATES
VERSIONS = ["original", "relocate_excluded"]


# =============================================================================
# completeness (same shape as r26's own gate)
# =============================================================================
def _flood_run_completeness(run_dir: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist"
    if not os.path.isfile(os.path.join(run_dir, C.FLOOD_AUDIT)):
        return "skipped", "household_governance_audit.csv missing"
    if not os.path.isfile(os.path.join(run_dir, C.FLOOD_SIM)):
        return "skipped", "simulation_log.csv missing"
    return "ok", None


# =============================================================================
# Part 1 -- IBR, original vs relocate-excluded
# =============================================================================
def _ibr_pct(rows: list, cond_name: str) -> float:
    cfn = R23.COND[cond_name]
    sel = [r for r in rows if cfn(C.flood_normalize_tp(r.get("construct_TP_LABEL")))]
    if not sel:
        raise PrepError(f"_ibr_pct: empty denominator for conditioning={cond_name}")
    return C.flood_ibr_components(sel, C.flood_final)["ibr_pct"]


def _relocate_excluded(aud_rows: list) -> list:
    return [r for r in aud_rows if C.flood_final(r) != "relocate"]


def _part1_ibr(rows: list, flood_arm_roots: dict) -> dict:
    """Returns {(model, arm, version, cond): {seed: ibr_pct}}."""
    per_cell: dict = {}
    pooled_rows: dict = {}  # (model, arm, version) -> list of audit rows across all 5 seeds
    for model in MODELS:
        for arm in ("strict", "disabled"):
            root = flood_arm_roots[(model, arm)]
            pooled_rows[(model, arm, "original")] = []
            pooled_rows[(model, arm, "relocate_excluded")] = []
            for seed in SEEDS5:
                run_dir = os.path.join(C.FLOOD_RESULTS, root, f"Run_{seed}")
                status, reason = _flood_run_completeness(run_dir)
                if status == "skipped":
                    print(f"  SKIPPED {model} {arm} seed {seed}: {reason}")
                    rows.append({"row_type": "skipped", "model": model, "arm": arm,
                                 "seed": seed, "reason": reason})
                    continue
                aud = C.read_csv(os.path.join(run_dir, C.FLOOD_AUDIT))
                C.require_cols(aud, ["construct_TP_LABEL", "final_skill"], run_dir)
                aud_excl = _relocate_excluded(aud)
                n_excluded = len(aud) - len(aud_excl)
                pooled_rows[(model, arm, "original")].extend(aud)
                pooled_rows[(model, arm, "relocate_excluded")].extend(aud_excl)
                for version, vrows in (("original", aud), ("relocate_excluded", aud_excl)):
                    for cond in IBR_CONDITIONINGS:
                        pct = _ibr_pct(vrows, cond)
                        rows.append({"row_type": "ibr_seed", "model": model, "arm": arm,
                                     "seed": seed, "version": version, "condition": cond,
                                     "n_rows": len(vrows), "n_excluded": n_excluded,
                                     "ibr_pct": pct})
                        per_cell.setdefault((model, arm, version, cond), {})[seed] = pct

    for (model, arm, version), all_rows in pooled_rows.items():
        if not all_rows:
            continue
        for cond in IBR_CONDITIONINGS:
            pct = _ibr_pct(all_rows, cond)
            rows.append({"row_type": "ibr_pooled", "model": model, "arm": arm,
                         "version": version, "condition": cond, "n_rows": len(all_rows),
                         "ibr_pct": pct})

    for (model, arm, version, cond), by_seed in per_cell.items():
        n = len(by_seed)
        vals = list(by_seed.values())
        rows.append({"row_type": "ibr_seed_summary", "model": model, "arm": arm,
                     "version": version, "condition": cond, "n_seeds": n,
                     "ibr_pct_mean": C.mean(vals),
                     "ibr_pct_sd": C.sd(vals) if n >= 2 else float("nan")})
    return per_cell


def _part1_contrast(rows: list, per_cell: dict) -> None:
    for model in MODELS:
        for version in VERSIONS:
            for cond in IBR_CONDITIONINGS:
                gov = per_cell.get((model, "strict", version, cond), {})
                dis = per_cell.get((model, "disabled", version, cond), {})
                common = sorted(set(gov) & set(dis))
                if len(common) < 2:
                    rows.append({"row_type": "skipped", "section": "ibr_contrast",
                                 "model": model, "version": version, "condition": cond,
                                 "reason": f"only {len(common)} seeds common to both arms"})
                    continue
                diffs = [gov[s] - dis[s] for s in common]
                t, df = C.paired_t(diffs)
                mean_d, sd_d = C.mean(diffs), C.sd(diffs)
                n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
                same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
                rows.append({
                    "row_type": "ibr_contrast", "model": model, "version": version,
                    "condition": cond, "n_pairs": len(diffs), "mean_diff": mean_d,
                    "sd_diff": sd_d, "min_diff": min(diffs), "max_diff": max(diffs),
                    "n_sign_flips": n_flips, "all_same_sign": same_sign, "t": t,
                    "df": float(df), "p_paired_t": C.t_two_sided_p(t, df),
                    "p_exact_permutation": C.exact_perm_p(diffs),
                    "permutation_floor": 2.0 / (1 << len(diffs)),
                })


# =============================================================================
# Part 2 -- JS distance, original vs relocate-excluded
# =============================================================================
# Transcribed verbatim from r28_trajectory_vs_traditional.py (r28 is
# committed, not modified/imported-around; these are private module-level
# helpers there with no seam to add a relocate-exclusion filter, so the
# math is copied here, not re-derived).
def _js_distance(p: list, q: list) -> float:
    if len(p) != len(q):
        raise PrepError(f"_js_distance: length mismatch {len(p)} vs {len(q)}")
    if abs(sum(p) - 1.0) > 1e-6 or abs(sum(q) - 1.0) > 1e-6:
        raise PrepError(f"_js_distance: inputs are not probability vectors "
                         f"(sum p={sum(p)}, sum q={sum(q)})")
    m = [(pi + qi) / 2.0 for pi, qi in zip(p, q)]

    def _kl(a, b):
        s = 0.0
        for ai, bi in zip(a, b):
            if ai > 0:
                s += ai * math.log2(ai / bi)
        return s

    jsd = 0.5 * _kl(p, m) + 0.5 * _kl(q, m)
    if jsd < -1e-9 or jsd > 1.0 + 1e-9:
        raise PrepError(f"_js_distance: JS divergence {jsd} outside [0,1] -- numeric bug")
    return math.sqrt(min(max(jsd, 0.0), 1.0))


def _state_dist(df_year: pd.DataFrame) -> list:
    n = len(df_year)
    if n == 0:
        raise PrepError("_state_dist: zero rows for this year")
    counts = df_year["prot_state"].value_counts()
    unexpected = set(counts.index) - set(PROT_STATES)
    if unexpected:
        raise PrepError(f"_state_dist: prot_state values outside PROT_STATES: {unexpected}")
    return [counts.get(s, 0) / n for s in PROT_STATES]


def _relocate_excluded_df(df: pd.DataFrame) -> pd.DataFrame:
    action_norm = df["yearly_decision"].apply(FIG3._normalise_decision)
    return df[action_norm != "relocate"]


def _part2_js(rows: list) -> dict:
    presence = {
        "gov": R28._flood_seed_dirs_present(FIG3.GOV_DIR),
        "disabled": R28._flood_seed_dirs_present(FIG3.DISABLED_DIR),
        "rulebased": R28._flood_seed_dirs_present(FIG3.RULEBASED_DIR),
    }
    complete_seeds = {k: [s for s, ok in v.items() if ok] for k, v in presence.items()}
    common_seeds = sorted(set(complete_seeds["gov"]) & set(complete_seeds["disabled"])
                           & set(complete_seeds["rulebased"]), key=int)
    if len(common_seeds) < 2:
        print(f"  Part 2 JS: PENDING -- only {len(common_seeds)} seeds complete on all "
              f"three arms")
        return {}

    data = FIG3.load_all_runs()
    for key in ("gov", "disabled", "rulebased"):
        if len(data[key]) != len(complete_seeds[key]):
            raise PrepError(f"gen_fig3_regen.load_all_runs() returned {len(data[key])} "
                             f"'{key}' runs but this script's own check found "
                             f"{len(complete_seeds[key])} -- refusing to guess seed order")
    seed_labels = [str(s) for s in FIG3.RUN_SEEDS]
    dfs = {key: dict(zip(seed_labels, data[key])) for key in ("gov", "disabled", "rulebased")}

    comparisons = [("gov_vs_rb", "gov", "rulebased"), ("dis_vs_rb", "disabled", "rulebased"),
                   ("gov_vs_dis", "gov", "disabled")]
    per_seed_year_mean: dict = {(c, v): {} for c, _, _ in comparisons for v in VERSIONS}

    for seed in common_seeds:
        raw = {"gov": dfs["gov"][seed], "disabled": dfs["disabled"][seed],
               "rulebased": dfs["rulebased"][seed]}
        excl = {k: _relocate_excluded_df(df) for k, df in raw.items()}
        for version, df_by_key in (("original", raw), ("relocate_excluded", excl)):
            per_year_js = {c: [] for c, _, _ in comparisons}
            for year in R28.FLOOD_YEARS:
                dist = {}
                for key, df in df_by_key.items():
                    df_y = df[df["year"] == year]
                    if len(df_y) == 0:
                        # every relocate-excluded row for this arm/year/seed
                        # was dropped -- report and skip this year for every
                        # comparison touching this key rather than crash.
                        dist[key] = None
                    else:
                        dist[key] = _state_dist(df_y)
                for comp_name, key_a, key_b in comparisons:
                    if dist[key_a] is None or dist[key_b] is None:
                        print(f"  SKIPPED js[{version}] {comp_name} seed {seed} year {year}: "
                              f"empty distribution after relocate exclusion")
                        continue
                    js = _js_distance(dist[key_a], dist[key_b])
                    per_year_js[comp_name].append(js)
            for comp_name, _, _ in comparisons:
                if not per_year_js[comp_name]:
                    continue
                year_mean = C.mean(per_year_js[comp_name])
                per_seed_year_mean[(comp_name, version)][seed] = year_mean
                rows.append({"row_type": "js_seed_mean", "comparison": comp_name,
                             "version": version, "seed": seed, "mean_over_years": year_mean,
                             "n_years": len(per_year_js[comp_name])})

    for (comp_name, version), by_seed in per_seed_year_mean.items():
        n = len(by_seed)
        if n == 0:
            continue
        vals = list(by_seed.values())
        rows.append({"row_type": "js_summary", "comparison": comp_name, "version": version,
                     "n_seeds": n, "mean_over_years_mean": C.mean(vals),
                     "mean_over_years_sd": C.sd(vals) if n >= 2 else float("nan")})

    for version in VERSIONS:
        gr = per_seed_year_mean.get(("gov_vs_rb", version), {})
        dr = per_seed_year_mean.get(("dis_vs_rb", version), {})
        common = sorted(set(gr) & set(dr))
        if len(common) < 2:
            rows.append({"row_type": "skipped", "section": "js_contrast", "version": version,
                         "reason": f"only {len(common)} seeds common"})
            continue
        diffs = [gr[s] - dr[s] for s in common]
        t, df = C.paired_t(diffs)
        mean_d, sd_d = C.mean(diffs), C.sd(diffs)
        n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
        same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
        rows.append({
            "row_type": "js_contrast", "version": version, "n_pairs": len(diffs),
            "mean_diff": mean_d, "sd_diff": sd_d, "min_diff": min(diffs),
            "max_diff": max(diffs), "n_sign_flips": n_flips, "all_same_sign": same_sign,
            "t": t, "df": float(df), "p_paired_t": C.t_two_sided_p(t, df),
            "p_exact_permutation": C.exact_perm_p(diffs),
            "permutation_floor": 2.0 / (1 << len(diffs)),
        })
    return dfs


# =============================================================================
# Part 3 -- relocation share (reused) + diversity index (new)
# =============================================================================
def _part3_relocation_share(rows: list, corpus: str) -> None:
    r28_csv_name = f"r28_trajectory_vs_traditional{C.corpus_suffix(corpus)}.csv"
    r28_path = os.path.join(C.OUT, r28_csv_name)
    if not os.path.isfile(r28_path):
        raise PrepError(f"missing {r28_path} -- run r28_trajectory_vs_traditional.py "
                         f"--corpus {corpus} first")
    r28_rows = C.read_csv(r28_path)
    n = 0
    for r in r28_rows:
        if r["row_type"] == "flood_relocation_arm_summary":
            rows.append({"row_type": "relocation_share", "arm": r["arm"],
                         "n_seeds": r["n_seeds"], "share_min": float(r["share_min"]),
                         "share_max": float(r["share_max"]), "share_mean": float(r["share_mean"]),
                         "share_sd": float(r["share_sd"]),
                         "note": f"read verbatim from out/{r28_csv_name} "
                                 "(row_type=flood_relocation_arm_summary), not recomputed"})
            n += 1
    if n == 0:
        if corpus != "v08":
            print(f"  Part 3a: PENDING -- {r28_csv_name} has 0 flood_relocation_arm_summary "
                  f"rows yet (r28 --corpus {corpus} is itself pending)")
            return
        raise PrepError(f"{r28_csv_name}: found 0 flood_relocation_arm_summary rows")
    print(f"  Part 3a: carried {n} relocation_share rows from r28, verbatim")


def _part3_diversity(rows: list, dfs: dict) -> None:
    if not dfs:
        print("  Part 3b: PENDING -- Part 2's flood DataFrames not available")
        return
    for key in ("gov", "disabled", "rulebased"):
        all_df = pd.concat(dfs[key].values(), ignore_index=True)
        for version, df in (("original", all_df), ("relocate_excluded",
                                                     _relocate_excluded_df(all_df))):
            counts = {s: int((df["prot_state"] == s).sum()) for s in PROT_STATES}
            total = sum(counts.values())
            if total == 0:
                rows.append({"row_type": "diversity_index", "arm": key, "version": version,
                             "n_agent_years": 0, "diversity_index": float("nan")})
                continue
            div = C.normalized_entropy(counts, k=5)
            rows.append({"row_type": "diversity_index", "arm": key, "version": version,
                         "n_agent_years": total, "diversity_index": div})


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "model", "arm", "seed", "version", "condition",
    "n_rows", "n_excluded", "ibr_pct", "n_seeds", "ibr_pct_mean", "ibr_pct_sd",
    "n_pairs", "mean_diff", "sd_diff", "min_diff", "max_diff", "n_sign_flips",
    "all_same_sign", "t", "df", "p_paired_t", "p_exact_permutation", "permutation_floor",
    "comparison", "mean_over_years", "n_years", "mean_over_years_mean", "mean_over_years_sd",
    "share_min", "share_max", "share_mean", "share_sd", "note",
    "n_agent_years", "diversity_index", "reason",
]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="R31 -- flood relocation sensitivity (gemma3_4b strict/disabled are "
                     "--corpus-aware; gemma4_12b and the JS/IBR math are not)")
    C.add_corpus_arg(parser)
    args = parser.parse_args()
    corpus = args.corpus
    suffix = C.corpus_suffix(corpus)

    C.banner(f"R31  Flood relocation sensitivity: IBR + JS distance with relocate "
             f"agent-years excluded (gemma3_4b corpus={corpus})")
    rows: list = []

    print("\n-- Part 1: IBR, original vs relocate-excluded --")
    flood_arm_roots = _flood_arm_roots(corpus)
    per_cell = _part1_ibr(rows, flood_arm_roots)
    _part1_contrast(rows, per_cell)

    print(f"\n-- Part 2: JS distance, original vs relocate-excluded (corpus={corpus}) --")
    if corpus != "v08":
        import pathlib
        gov_root, dis_root = flood_arm_roots[("gemma3_4b", "strict")], \
            flood_arm_roots[("gemma3_4b", "disabled")]
        orig_gov_dir, orig_dis_dir = FIG3.GOV_DIR, FIG3.DISABLED_DIR
        FIG3.GOV_DIR = pathlib.Path(C.FLOOD_RESULTS) / gov_root
        FIG3.DISABLED_DIR = pathlib.Path(C.FLOOD_RESULTS) / dis_root
        print(f"  FIG3.GOV_DIR -> {FIG3.GOV_DIR}")
        print(f"  FIG3.DISABLED_DIR -> {FIG3.DISABLED_DIR}")
        try:
            dfs = _part2_js(rows)
        finally:
            FIG3.GOV_DIR, FIG3.DISABLED_DIR = orig_gov_dir, orig_dis_dir
    else:
        dfs = _part2_js(rows)

    print("\n-- Part 3: relocation share (reused) + diversity index --")
    _part3_relocation_share(rows, corpus)
    _part3_diversity(rows, dfs)

    md_text = render_md(rows, corpus)

    csv_final = f"r31_flood_relocation_sensitivity{suffix}.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, f"r31_flood_relocation_sensitivity{suffix}.md")
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
_cp = lambda x: float(C.fmt(x))  # noqa: E731


def _find(rows, row_type, **kw):
    out = []
    for r in rows:
        if r.get("row_type") != row_type:
            continue
        if all(r.get(k) == v for k, v in kw.items()):
            out.append(r)
    return out


def render_md(rows: list, corpus: str = "v08") -> str:
    lines = []
    lines.append("# R31 -- flood relocation sensitivity")
    lines.append("")
    lines.append("Source: `r31_flood_relocation_sensitivity.py`. Every number below is read "
                 "live from the `rows` list this script writes to the paired CSV. Exclusion "
                 "rule: an agent-year is dropped iff its normalized action is \"relocate\" "
                 "(covers the raw spellings relocate/relocated/already_relocated -- see "
                 "module docstring for the empirical spot-check confirming this captures "
                 "every post-relocation year, not just the transition year).")
    lines.append("")
    if corpus != "v08":
        lines.append(
            f"> **gemma3_4b corpus: {corpus}.** {C.flood_sampling_method_text(corpus)}. "
            f"gemma4_12b rows are UNCHANGED (no separate defaults corpus exists for them "
            f"here)."
        )
        lines.append("")

    lines.append("## Part 1 -- IBR headline (uncond, final level), original vs "
                 "relocate-excluded")
    lines.append("")
    lines.append("| model | arm | version | n_seeds | mean +/- sd (%) | pooled (%) |")
    lines.append("|---|---|---|---|---|---|")
    for model in MODELS:
        for arm in ("strict", "disabled"):
            for version in VERSIONS:
                s = _find(rows, "ibr_seed_summary", model=model, arm=arm, version=version,
                          condition="uncond")
                p = _find(rows, "ibr_pooled", model=model, arm=arm, version=version,
                          condition="uncond")
                if not s or not p:
                    lines.append(f"| {model} | {arm} | {version} | -- | pending | pending |")
                    continue
                sr, pr = s[0], p[0]
                lines.append(f"| {model} | {arm} | {version} | {sr['n_seeds']} | "
                             f"{_cp(sr['ibr_pct_mean']):.2f} +/- {_cp(sr['ibr_pct_sd']):.2f} | "
                             f"{_cp(pr['ibr_pct']):.2f} |")
    lines.append("")

    lines.append("### Governed - no-validator contrast, IBR headline (uncond, final), "
                 "both versions")
    lines.append("")
    lines.append("| model | version | n_pairs | mean_diff (pp) | t | p (paired t) | "
                 "p (exact perm) | all_same_sign |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for model in MODELS:
        for version in VERSIONS:
            recs = _find(rows, "ibr_contrast", model=model, version=version, condition="uncond")
            if not recs:
                lines.append(f"| {model} | {version} | -- | -- | -- | -- | -- | PENDING |")
                continue
            r = recs[0]
            lines.append(f"| {model} | {version} | {r['n_pairs']} | "
                         f"{_cp(r['mean_diff']):.2f} | {_cp(r['t']):.3f} | "
                         f"{_cp(r['p_paired_t']):.4f} | {_cp(r['p_exact_permutation']):.4f} | "
                         f"{r['all_same_sign']} |")
    lines.append("")

    lines.append("## Part 2 -- JS distance to rule-based, original vs relocate-excluded")
    lines.append("")
    lines.append("| comparison | version | n_seeds | mean_over_years mean +/- sd |")
    lines.append("|---|---|---|---|")
    for comp in ("gov_vs_rb", "dis_vs_rb", "gov_vs_dis"):
        for version in VERSIONS:
            recs = _find(rows, "js_summary", comparison=comp, version=version)
            if not recs:
                lines.append(f"| {comp} | {version} | -- | pending |")
                continue
            r = recs[0]
            lines.append(f"| {comp} | {version} | {r['n_seeds']} | "
                         f"{_cp(r['mean_over_years_mean']):.4f} +/- "
                         f"{_cp(r['mean_over_years_sd']):.4f} |")
    lines.append("")
    lines.append("### Paired contrast (governed-to-rulebased minus no-validator-to-rulebased "
                 "JS distance), both versions")
    lines.append("")
    lines.append("| version | n_pairs | mean_diff | t | p (paired t) | p (exact perm) | "
                 "all_same_sign |")
    lines.append("|---|---|---|---|---|---|---|")
    for version in VERSIONS:
        recs = _find(rows, "js_contrast", version=version)
        if not recs:
            lines.append(f"| {version} | -- | -- | -- | -- | -- | PENDING |")
            continue
        r = recs[0]
        lines.append(f"| {version} | {r['n_pairs']} | {_cp(r['mean_diff']):.4f} | "
                     f"{_cp(r['t']):.3f} | {_cp(r['p_paired_t']):.4f} | "
                     f"{_cp(r['p_exact_permutation']):.4f} | {r['all_same_sign']} |")
    lines.append("")

    lines.append("## Part 3a -- relocation share (reused verbatim from r28)")
    lines.append("")
    lines.append("| arm | n_seeds | share_min % | share_max % | share_mean +/- sd % |")
    lines.append("|---|---|---|---|---|")
    for arm in ("rulebased", "gov", "disabled"):
        recs = _find(rows, "relocation_share", arm=arm)
        if not recs:
            lines.append(f"| {arm} | -- | -- | -- | pending |")
            continue
        r = recs[0]
        lines.append(f"| {arm} | {r['n_seeds']} | {_cp(r['share_min']):.2f} | "
                     f"{_cp(r['share_max']):.2f} | {_cp(r['share_mean']):.2f} +/- "
                     f"{_cp(r['share_sd']):.2f} |")
    lines.append("")

    lines.append("## Part 3b -- diversity index (pooled 5-state normalized entropy on "
                 "`prot_state`, common action set across LLM and rule-based arms)")
    lines.append("")
    lines.append("| arm | version | n_agent_years | diversity_index |")
    lines.append("|---|---|---|---|")
    for arm in ("gov", "disabled", "rulebased"):
        for version in VERSIONS:
            recs = _find(rows, "diversity_index", arm=arm, version=version)
            if not recs:
                lines.append(f"| {arm} | {version} | -- | pending |")
                continue
            r = recs[0]
            lines.append(f"| {arm} | {version} | {r['n_agent_years']} | "
                         f"{_cp(r['diversity_index']):.4f} |")
    lines.append("")

    # ---- Plain read -------------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    ibr_orig = _find(rows, "ibr_contrast", version="original", condition="uncond")
    ibr_excl = _find(rows, "ibr_contrast", version="relocate_excluded", condition="uncond")
    if ibr_orig and ibr_excl:
        same_dir = all((o["mean_diff"] > 0) == (e["mean_diff"] > 0)
                       for o, e in zip(ibr_orig, ibr_excl))
        sentences.append(
            "Excluding relocate-final agent-years " +
            ("does NOT flip" if same_dir else "FLIPS") +
            " the sign of the governed-minus-no-validator IBR-headline contrast for any "
            "model checked."
        )
    js_orig = _find(rows, "js_contrast", version="original")
    js_excl = _find(rows, "js_contrast", version="relocate_excluded")
    if js_orig and js_excl:
        o, e = js_orig[0], js_excl[0]
        sentences.append(
            f"The governed-vs-no-validator JS-distance-to-rulebased contrast moves from "
            f"mean_diff={_cp(o['mean_diff']):.4f} (original) to "
            f"mean_diff={_cp(e['mean_diff']):.4f} (relocate-excluded), "
            f"{'the same sign' if (o['mean_diff']>0)==(e['mean_diff']>0) else 'a SIGN FLIP'} "
            f"-- context for how much of the original contrast the relocation-share "
            f"difference alone was responsible for."
        )
    rb_share = _find(rows, "relocation_share", arm="rulebased")
    gov_share = _find(rows, "relocation_share", arm="gov")
    if rb_share and gov_share:
        sentences.append(
            f"Rule-based relocates {_cp(rb_share[0]['share_mean']):.2f}% of agent-years on "
            f"average vs governed's {_cp(gov_share[0]['share_mean']):.2f}% (reused from r28, "
            f"not recomputed here)."
        )
    div_gov = _find(rows, "diversity_index", arm="gov", version="original")
    div_rb = _find(rows, "diversity_index", arm="rulebased", version="original")
    if div_gov and div_rb:
        sentences.append(
            f"On the common 5-state action set, governed's pooled diversity_index="
            f"{_cp(div_gov[0]['diversity_index']):.3f} vs rule-based's "
            f"{_cp(div_rb[0]['diversity_index']):.3f} (original, both arms) -- the same "
            f"state space both the IBR and JS analyses above already share."
        )
    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method -----------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "Exclusion rule stated once at the top of this document and in the module docstring: "
        "normalized action == \"relocate\" (via `_common.py::flood_normalize_action` for "
        "audit rows / `gen_fig3_regen.py::_normalise_decision` for simulation_log rows, both "
        "imported, neither re-derived), applied per agent-year. IBR headline = the "
        "unconditional, final-level flood IBR (`_common.py::flood_ibr_components`, R1+R3+R4 "
        "over total, same definition r23/r24/r25/r26 already use for this column) -- pooled "
        "= all 5 seeds' rows concatenated before one ibr_pct calculation, distinct from the "
        "mean of 5 per-seed rates (both reported). JS distance = `gen_fig3_regen.py`'s own "
        "5-state `prot_state` classification (imported, not re-derived) with `_js_distance`/"
        "`_state_dist` TRANSCRIBED VERBATIM from `r28_trajectory_vs_traditional.py` (r28 is "
        "committed, not modified; these are private functions there with no seam for a "
        "relocate filter without editing r28 itself). Relocation share is READ, not "
        "recomputed, from `out/r28_trajectory_vs_traditional.csv`. diversity_index = "
        "`_common.py::normalized_entropy` (k=5) on the POOLED (all years x all seeds) "
        "`prot_state` count table per arm -- the same 5-state space rule-based and both LLM "
        "arms already share via `gen_fig3_regen.py`'s classification, which is what makes it "
        "a common action set across LLM and rule-based arms (as opposed to "
        "`_normalise_decision`'s 4-action vocabulary, which rule-based and LLM arms populate "
        "at different cardinalities)."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
