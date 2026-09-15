"""R11 -- flood seed-matched 7-pair table, using the 2026-09-06 T0-1/T0-2 top-up runs.

WHAT THIS ADDS THAT R2/R4/R7 DO NOT HAVE
  R2/R4/R7 all note that flood governed and no-validator carry only THREE shared
  seeds (42, 45, 46) and that the published pairing is by RUN INDEX, not by seed.
  Two small top-up batches close that gap without touching any published run:
    JOH_T0-1_strict_gemma3_4b_e0eee08c/Run_43, Run_44     -- governed,   seeds 43/44
    JOH_T0-2_disabled_gemma3_4b_e0eee08c/Run_4202, Run_4203 -- no-validator, seeds
                                                                4202/4203
  Combined with the five already-published runs per arm, BOTH arms now carry the
  same seven seeds: {42, 43, 44, 45, 46, 4202, 4203}. This script is the first
  flood table that pairs governed vs no-validator BY SEED at n=7 (df=6) instead of
  n=3 (df=2).

WHERE EACH SEED'S DATA COMES FROM (mixed provenance -- read PROVENANCE rows)
  governed:      42, 4202, 4203, 45, 46  -> published JOH_FINAL/gemma3_4b/Group_C
                 43, 44                  -> NEW top-up batch (root depends on --variant)
  no-validator:  42, 43, 44, 45, 46      -> published JOH_ABLATION_DISABLED/.../Group_C_disabled
                 4202, 4203              -> NEW top-up batch (root depends on --variant)
  For seeds 43, 44, 4202, 4203 the governed and no-validator side of the pair were
  produced by DIFFERENT CODE COMMITS (published corpus vs origin/main e0eee08c).
  This script reads both manifests and reports every provenance field that differs
  -- it does not decide whether the difference matters, it makes it visible.

  --variant matched (DEFAULT): the 2026-09-07 top-up, inference settings matched to
    the published no-validator arm (num_ctx=8192, num_predict=4096, thinking_mode=
    disabled): JOH_T0-1b_strict_gemma3_4b_e0eee08c_matched/Run_43,44 (governed),
    JOH_T0-2b_disabled_gemma3_4b_e0eee08c_matched/Run_4202,4203 (no-validator). This
    is the table and statistics reported in the README/SUMMARY.
  --variant unmatched: the original 2026-09-06 top-up (num_ctx=4096, num_predict=
    2048, thinking_mode=auto -- NOT matched to the published arm):
    JOH_T0-1_strict_gemma3_4b_e0eee08c/Run_43,44 and
    JOH_T0-2_disabled_gemma3_4b_e0eee08c/Run_4202,4203. Superseded by matched as the
    headline table; kept runnable so the old numbers can be regenerated on demand.
    Writes to r11_flood_seed_matched_unmatched.csv, not the canonical output file.

METRICS (identical definitions to r2/r4/r7, transcribed via _common, never redefined)
  ibr_<cond>_<level>  cond in {uncond, tp_not_medium, tp_high}, level in
                      {proposal, final, executed}. IBR = (R1+R3+R4)/total*100,
                      R5 excluded. 9 cells.
  ehe_pooled_simlog_published   H/log2(4) on simulation_log.yearly_decision,
                      pooled once over the whole run -- the Extended Data Table 2
                      definition (r7's ehe_flood_pooled_simlog_PUBLISHED).
  rejection_rate_pct  % of audit rows whose status starts with REJECTED (r3's
                      rejected_to_fallback convention).
  retry_rate_pct      % of audit rows with retry_count > 0 (r9's share_retried_pct
                      convention).

PROPOSAL vs FINAL vs EXECUTED IN FLOOD
  The README states these three levels coincide row-for-row in flood (unlike
  irrigation, where 108 rows disagree). This script does not repeat that claim: it
  counts proposal!=final, final!=executed and proposal!=executed on every audit row
  of all 14 (arm, seed) run instances and reports the exact counts in LEVEL_DISAGREEMENT
  rows -- print both anyway, as the brief asks, backed by a number instead of an
  assertion.

STATISTICS
  Per metric: paired t on the 7 per-seed differences (df=6), the exact two-sided
  sign-flip permutation p over all 2^7=128 sign patterns (floor 2/128=0.015625),
  the sign-flip count (r7's convention: differences whose sign disagrees with the
  sign of the mean difference), and mean/sd of governed, no-validator and the
  difference. Alongside, for every metric r7 already computed under the OLD n=5
  run-index pairing (published-only, noval_arm=live), this script copies r7's
  mean_diff / p_paired_t / p_exact_permutation / n_sign_flips verbatim from
  out/r7_seed_robustness.csv so the two pairings sit side by side. A metric r7 never
  computed (the three proposal-level IBR cells, rejection_rate, retry_rate) carries
  N/A_by_design in the r7_n5_* columns, not NA -- it was never computed there, it
  did not come out empty.

INTEGRITY OF THE FOUR NEW RUNS (whichever --variant is selected)
  Read first, before any metric: simulation_log row count (must be 1000 = 100
  agents x 10 years -- raises otherwise), audit row count (expected LESS than 1000,
  because an agent that has relocated makes no further decision), run_integrity.json
  (raises if integrity_ok is not literally True), the manifest seed (must match the
  seed the run directory name implies), and config_snapshot.yaml's governance_profile
  line. For --variant matched ONLY, also raises unless the manifest's num_ctx,
  num_predict and thinking_mode are IDENTICAL to the published no-validator arm's
  reference manifest (read live from JOH_ABLATION_DISABLED/.../Group_C_disabled
  seed 42, not hardcoded) -- the whole point of the matched batch is that inference
  settings no longer confound the comparison, so a silent settings drift must fail
  loud, not print a caveat. --variant unmatched skips this check by design: those
  runs are known not to match (num_ctx=4096/num_predict=2048/thinking_mode=auto),
  that mismatch is exactly what the SENSITIVITY rows measure.

SENSITIVITY: matched vs unmatched, same seed and same arm (row_type=sensitivity)
  Independent of --variant, always computed from both top-up batches on disk. For
  each of the 4 new seeds (43, 44 governed; 4202, 4203 no-validator), compares the
  matched run against the unmatched run of the SAME seed and SAME arm on
  ibr_uncond_final, ibr_tp_not_medium_final (the threat-relevant conditioning),
  ehe_pooled_simlog_published, rejection_rate_pct and retry_rate_pct. This isolates
  the effect of num_ctx/num_predict/thinking_mode alone -- code commit, seed, model
  and governance arm are held fixed between the two rows of each comparison.

CONFIG SNAPSHOT DIFF (stdlib difflib, no third-party YAML parser)
  Diffs the new governed Run_43 config_snapshot.yaml against the published
  Group_C Run_1 (seed 42) snapshot, and the new no-validator Run_4202 snapshot
  against the published Group_C_disabled Run_1 snapshot. Reports line-level added
  and removed counts plus the shallow (<=6-space-indent) keys introduced by any
  added line, so a reviewer can see whether the newer code commit only ADDED schema
  surface (expected: yes) or also CHANGED an existing governance rule (would be a
  problem: the active ruleset must be byte-identical across commits for a fair
  comparison).

OUTPUT
  out/r11_flood_seed_matched.csv (--variant matched, default) or
  out/r11_flood_seed_matched_unmatched.csv (--variant unmatched) -- row_type in
  {integrity, config_diff, provenance, level_disagreement, pair, stat, sensitivity}.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r11_flood_seed_matched.py
        python .../r11_flood_seed_matched.py --variant unmatched
"""
from __future__ import annotations

import argparse
import csv
import difflib
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

MODEL = "gemma3_4b"
GOV_PUB = ("JOH_FINAL", "Group_C")
DIS_PUB = ("JOH_ABLATION_DISABLED", "Group_C_disabled")
# --variant matched (default): inference settings matched to the published no-validator
# arm (num_ctx=8192, num_predict=4096, thinking_mode=disabled).
GOV_NEW_ROOT_MATCHED = "JOH_T0-1b_strict_gemma3_4b_e0eee08c_matched"
DIS_NEW_ROOT_MATCHED = "JOH_T0-2b_disabled_gemma3_4b_e0eee08c_matched"
# --variant unmatched: the original top-up, num_ctx=4096/num_predict=2048/thinking=auto.
GOV_NEW_ROOT_UNMATCHED = "JOH_T0-1_strict_gemma3_4b_e0eee08c"
DIS_NEW_ROOT_UNMATCHED = "JOH_T0-2_disabled_gemma3_4b_e0eee08c"

SENS_METRICS = ["ibr_uncond_final", "ibr_tp_not_medium_final",
                 "ehe_pooled_simlog_published", "rejection_rate_pct", "retry_rate_pct"]

SEEDS = ["42", "43", "44", "45", "46", "4202", "4203"]
COND = {
    "uncond": lambda tp: True,
    "tp_not_medium": lambda tp: tp in ("VL", "L", "H", "VH"),
    "tp_high": lambda tp: tp in ("H", "VH"),
}
LEVELS = {"proposal": C.flood_proposal, "final": C.flood_final, "executed": C.flood_executed}
METRICS = [f"ibr_{c}_{l}" for c in COND for l in LEVELS] + [
    "ehe_pooled_simlog_published", "rejection_rate_pct", "retry_rate_pct"]
R7_KEY = {
    "ibr_uncond_final": "ibr_flood_uncond_final",
    "ibr_uncond_executed": "ibr_flood_uncond_executed",
    "ibr_tp_not_medium_final": "ibr_flood_tp_not_medium_final",
    "ibr_tp_not_medium_executed": "ibr_flood_tp_not_medium_executed",
    "ibr_tp_high_final": "ibr_flood_tp_high_final",
    "ibr_tp_high_executed": "ibr_flood_tp_high_executed",
    "ehe_pooled_simlog_published": "ehe_flood_pooled_simlog_PUBLISHED",
}
NAD = "N/A_by_design"


def _new_run(root, run):
    rd = os.path.join(C.FLOOD_RESULTS, root, run)
    if not os.path.isdir(rd):
        raise PrepError(f"missing new run dir {rd}")
    seed = C.flood_seed_of(rd)
    return seed, rd


def _manifest(rd):
    p = os.path.join(rd, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"missing manifest {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _run_integrity(rd):
    p = os.path.join(rd, "run_integrity.json")
    if not os.path.isfile(p):
        return None
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def _governance_profile(rd):
    p = os.path.join(rd, "config_snapshot.yaml")
    if not os.path.isfile(p):
        raise PrepError(f"missing config_snapshot.yaml in {rd}")
    prof = None
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            if line.strip().startswith("governance_profile:"):
                prof = line.strip().split(":", 1)[1].strip()
    if prof is None:
        raise PrepError(f"{p}: no governance_profile line found")
    return prof


def _metrics_for(rd):
    aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
    sim = C.read_csv(os.path.join(rd, C.FLOOD_SIM))
    C.require_cols(aud, ["year", "proposed_skill", "final_skill", "status",
                         "retry_count", "construct_TP_LABEL"], rd)
    out = {"_n_audit_rows": len(aud), "_n_simlog_rows": len(sim)}
    for cname, cfn in COND.items():
        sel = [r for r in aud if cfn(C.flood_normalize_tp(r.get("construct_TP_LABEL")))]
        if not sel:
            raise PrepError(f"{rd}/{cname}: empty denominator")
        for lvl, fn in LEVELS.items():
            out[f"ibr_{cname}_{lvl}"] = C.flood_ibr_components(sel, fn)["ibr_pct"]
    counts = {a: 0 for a in C.FLOOD_ACTION_ORDER}
    for r in sim:
        counts[C.flood_normalize_action(r.get("yearly_decision"))] += 1
    out["ehe_pooled_simlog_published"] = C.normalized_entropy(counts, k=4)
    st = [(r.get("status") or "").strip() for r in aud]
    rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
    n = len(aud)
    out["rejection_rate_pct"] = 100.0 * sum(1 for s in st if s.startswith("REJECTED")) / n
    out["retry_rate_pct"] = 100.0 * sum(1 for c in rc if c > 0) / n
    prop = [C.flood_proposal(r) for r in aud]
    fin = [C.flood_final(r) for r in aud]
    exe = [C.flood_executed(r) for r in aud]
    out["_n_prop_ne_final"] = sum(1 for p, f in zip(prop, fin) if p != f)
    out["_n_final_ne_executed"] = sum(1 for f, e in zip(fin, exe) if f != e)
    out["_n_prop_ne_executed"] = sum(1 for p, e in zip(prop, exe) if p != e)
    return out


def _config_diff(path_pub, path_new):
    a = open(path_pub, encoding="utf-8").read().splitlines()
    b = open(path_new, encoding="utf-8").read().splitlines()
    sm = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    added, removed = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "delete"):
            removed.extend(a[i1:i2])
        if tag in ("replace", "insert"):
            added.extend(b[j1:j2])
    key_re = re.compile(r"^(\s*)([A-Za-z_][A-Za-z0-9_]*):")
    seen, added_keys = set(), []
    for line in added:
        m = key_re.match(line)
        if m and len(m.group(1)) <= 6 and m.group(2) not in seen:
            seen.add(m.group(2))
            added_keys.append(m.group(2))
    return {
        "n_lines_removed": len(removed), "n_lines_added": len(added),
        "removed_lines": "; ".join(removed[:10]),
        "added_shallow_keys": "; ".join(added_keys),
    }


def _load_r7():
    p = os.path.join(C.OUT, "r7_seed_robustness.csv")
    if not os.path.isfile(p):
        raise PrepError(f"missing {p} -- run r7_seed_robustness.py first")
    with open(p, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    out = {}
    for r in rows:
        if (r["domain"] == "flood" and r["noval_arm"] == "live"
                and r["pairing"] == "run_index_n5_published"
                and r["test_family"] == "paired_one_sample_t_on_differences"):
            out[r["metric"]] = r
    if not out:
        raise PrepError(f"{p}: no matching flood run_index_n5_published rows found")
    return out


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--variant", choices=["matched", "unmatched"], default="matched",
                    help="which T0-1/T0-2 top-up batch backs the 4 new seeds in the "
                         "main 7-pair table and stats (default: matched). "
                         "'unmatched' reproduces the superseded 4096/2048/auto table.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    variant = args.variant
    GOV_NEW_ROOT = GOV_NEW_ROOT_MATCHED if variant == "matched" else GOV_NEW_ROOT_UNMATCHED
    DIS_NEW_ROOT = DIS_NEW_ROOT_MATCHED if variant == "matched" else DIS_NEW_ROOT_UNMATCHED

    C.banner(f"R11  flood seed-matched 7-pair table (variant={variant})")
    rows = []

    gov_pub_runs = C.flood_runs(GOV_PUB[0], MODEL, GOV_PUB[1])
    dis_pub_runs = C.flood_runs(DIS_PUB[0], MODEL, DIS_PUB[1])
    gov_pub_by_seed = {s: d for _, (s, d) in gov_pub_runs.items()}
    dis_pub_by_seed = {s: d for _, (s, d) in dis_pub_runs.items()}

    # published no-validator arm's manifest is the live reference for the settings
    # check below -- read from disk, never hardcoded, so a changed published corpus
    # would change what "matched" is checked against too.
    ref_manifest = _manifest(dis_pub_by_seed["42"])
    ref_num_ctx = ref_manifest.get("num_ctx")
    ref_num_predict = ref_manifest.get("num_predict")
    ref_thinking_mode = ref_manifest.get("thinking_mode")
    if variant == "matched" and (ref_num_ctx is None or ref_num_predict is None
                                  or ref_thinking_mode is None):
        raise PrepError("published no-validator reference manifest (seed 42) is "
                         "missing num_ctx/num_predict/thinking_mode -- cannot check "
                         "--variant matched settings against it")

    new43_seed, new43_dir = _new_run(GOV_NEW_ROOT, "Run_43")
    new44_seed, new44_dir = _new_run(GOV_NEW_ROOT, "Run_44")
    new4202_seed, new4202_dir = _new_run(DIS_NEW_ROOT, "Run_4202")
    new4203_seed, new4203_dir = _new_run(DIS_NEW_ROOT, "Run_4203")
    if (new43_seed, new44_seed) != ("43", "44"):
        raise PrepError(f"T0-1 seeds not 43/44: got {new43_seed}, {new44_seed}")
    if (new4202_seed, new4203_seed) != ("4202", "4203"):
        raise PrepError(f"T0-2 seeds not 4202/4203: got {new4202_seed}, {new4203_seed}")

    GOV_DIR = dict(gov_pub_by_seed)
    GOV_DIR["43"], GOV_DIR["44"] = new43_dir, new44_dir
    GOV_SRC = {s: f"published:{GOV_PUB[0]}/{MODEL}/{GOV_PUB[1]}" for s in gov_pub_by_seed}
    GOV_SRC["43"] = f"new:{GOV_NEW_ROOT}/Run_43"
    GOV_SRC["44"] = f"new:{GOV_NEW_ROOT}/Run_44"

    DIS_DIR = dict(dis_pub_by_seed)
    DIS_DIR["4202"], DIS_DIR["4203"] = new4202_dir, new4203_dir
    DIS_SRC = {s: f"published:{DIS_PUB[0]}/{MODEL}/{DIS_PUB[1]}" for s in dis_pub_by_seed}
    DIS_SRC["4202"] = f"new:{DIS_NEW_ROOT}/Run_4202"
    DIS_SRC["4203"] = f"new:{DIS_NEW_ROOT}/Run_4203"

    missing = [s for s in SEEDS if s not in GOV_DIR or s not in DIS_DIR]
    if missing:
        raise PrepError(f"seeds missing from one arm: {missing}")

    print(f"  {len(SEEDS)} seed-matched pairs: {SEEDS}")
    for s in SEEDS:
        print(f"    seed {s:>5s}  governed <- {GOV_SRC[s]:60s}  "
              f"no-val <- {DIS_SRC[s]}")

    # ---- 1. integrity of the four NEW runs ---------------------------------
    for arm, seed, rd in (("governed", "43", new43_dir), ("governed", "44", new44_dir),
                          ("ungoverned", "4202", new4202_dir),
                          ("ungoverned", "4203", new4203_dir)):
        aud = C.read_csv(os.path.join(rd, C.FLOOD_AUDIT))
        sim = C.read_csv(os.path.join(rd, C.FLOOD_SIM))
        if len(sim) != 1000:
            raise PrepError(f"{rd}: simulation_log has {len(sim)} rows, expected 1000")
        ri = _run_integrity(rd)
        if ri is None:
            raise PrepError(f"{rd}: no run_integrity.json")
        if ri.get("integrity_ok") is not True:
            raise PrepError(f"{rd}: integrity_ok is {ri.get('integrity_ok')!r}, not True")
        manifest_seed = str(C.flood_seed_of(rd))
        if manifest_seed != seed:
            raise PrepError(f"{rd}: manifest seed {manifest_seed} != expected {seed}")
        gp = _governance_profile(rd)
        gm_new = _manifest(rd)
        m_num_ctx = gm_new.get("num_ctx")
        m_num_predict = gm_new.get("num_predict")
        m_thinking_mode = gm_new.get("thinking_mode")
        settings_match = (m_num_ctx == ref_num_ctx and m_num_predict == ref_num_predict
                           and m_thinking_mode == ref_thinking_mode)
        if variant == "matched" and not settings_match:
            raise PrepError(
                f"{rd}: inference settings do not match the published no-validator "
                f"arm's reference (num_ctx {m_num_ctx!r} vs {ref_num_ctx!r}, "
                f"num_predict {m_num_predict!r} vs {ref_num_predict!r}, "
                f"thinking_mode {m_thinking_mode!r} vs {ref_thinking_mode!r})")
        rows.append({
            "row_type": "integrity", "arm": arm, "seed": seed,
            "run_dir": os.path.relpath(rd, C.REPO).replace("\\", "/"),
            "n_audit_rows": len(aud), "n_simlog_rows": len(sim),
            "expected_simlog_rows": 1000,
            "audit_rows_missing_vs_grid": ri.get("audit_rows_missing_vs_grid"),
            "integrity_ok": ri.get("integrity_ok"),
            "manifest_seed": manifest_seed,
            "config_snapshot_governance_profile": gp,
            "run_integrity_governance_mode": ri.get("governance_mode"),
            "framework_version": ri.get("framework_provenance", {}).get("framework_version"),
            "git_commit_short": ri.get("framework_provenance", {}).get("git_commit_short"),
            "reflection_expected": ri.get("reflection_expected"),
            "reflection_engine_wired": ri.get("reflection_engine_wired"),
            "reflection_log_entries": ri.get("reflection_log_entries"),
            "manifest_num_ctx": m_num_ctx, "manifest_num_predict": m_num_predict,
            "manifest_thinking_mode": m_thinking_mode,
            "ref_published_num_ctx": ref_num_ctx, "ref_published_num_predict": ref_num_predict,
            "ref_published_thinking_mode": ref_thinking_mode,
            "settings_match_published_disabled_arm": settings_match,
        })
        print(f"  integrity  {arm:11s} seed {seed:>5s}  audit={len(aud):4d}  "
              f"simlog={len(sim):4d}  integrity_ok={ri.get('integrity_ok')}  "
              f"governance_profile={gp}  reflection_expected={ri.get('reflection_expected')}  "
              f"num_ctx={m_num_ctx}/num_predict={m_num_predict}/thinking={m_thinking_mode}  "
              f"settings_match_published={settings_match}")

    # ---- 2. config_snapshot.yaml diff: new commit vs a published Group_C run
    gov_diff = _config_diff(
        os.path.join(gov_pub_by_seed["42"], "config_snapshot.yaml"),
        os.path.join(new43_dir, "config_snapshot.yaml"))
    rows.append({"row_type": "config_diff",
                 "comparison": "governed: published Group_C seed42 -> new T0-1 seed43",
                 **gov_diff})
    dis_diff = _config_diff(
        os.path.join(dis_pub_by_seed["42"], "config_snapshot.yaml"),
        os.path.join(new4202_dir, "config_snapshot.yaml"))
    rows.append({"row_type": "config_diff",
                 "comparison": "no-validator: published Group_C_disabled seed42 -> new T0-2 seed4202",
                 **dis_diff})
    print(f"\n  config_snapshot diff (governed): +{gov_diff['n_lines_added']} / "
          f"-{gov_diff['n_lines_removed']} lines; new shallow keys: "
          f"{gov_diff['added_shallow_keys']}")
    print(f"  config_snapshot diff (no-validator): +{dis_diff['n_lines_added']} / "
          f"-{dis_diff['n_lines_removed']} lines; new shallow keys: "
          f"{dis_diff['added_shallow_keys']}")

    # ---- 3. provenance for the 4 mixed-commit seeds ------------------------
    for seed, gov_is_new in (("43", True), ("44", True), ("4202", False), ("4203", False)):
        gm = _manifest(GOV_DIR[seed])
        dm = _manifest(DIS_DIR[seed])
        rec = {"row_type": "provenance", "seed": seed,
               "governed_source": GOV_SRC[seed], "ungoverned_source": DIS_SRC[seed]}
        for f in ("python_version", "git_commit", "num_ctx", "num_predict", "thinking_mode"):
            rec[f"governed_{f}"] = gm.get(f, "ABSENT_FROM_MANIFEST")
            rec[f"ungoverned_{f}"] = dm.get(f, "ABSENT_FROM_MANIFEST")
        rows.append(rec)
        print(f"  provenance seed {seed:>5s}  gov.git_commit={rec['governed_git_commit']}  "
              f"noval.git_commit={rec['ungoverned_git_commit']}  "
              f"gov.num_ctx={rec['governed_num_ctx']}/num_predict={rec['governed_num_predict']}  "
              f"noval.num_ctx={rec['ungoverned_num_ctx']}/num_predict={rec['ungoverned_num_predict']}")

    # ---- 4. metrics per seed per arm --------------------------------------
    gov_m = {s: _metrics_for(GOV_DIR[s]) for s in SEEDS}
    dis_m = {s: _metrics_for(DIS_DIR[s]) for s in SEEDS}

    n_pf = sum(gov_m[s]["_n_prop_ne_final"] + dis_m[s]["_n_prop_ne_final"] for s in SEEDS)
    n_fe = sum(gov_m[s]["_n_final_ne_executed"] + dis_m[s]["_n_final_ne_executed"] for s in SEEDS)
    n_pe = sum(gov_m[s]["_n_prop_ne_executed"] + dis_m[s]["_n_prop_ne_executed"] for s in SEEDS)
    total_audit = sum(gov_m[s]["_n_audit_rows"] + dis_m[s]["_n_audit_rows"] for s in SEEDS)
    for s in SEEDS:
        for arm, m in (("governed", gov_m[s]), ("ungoverned", dis_m[s])):
            rows.append({
                "row_type": "level_disagreement", "seed": s, "arm": arm,
                "n_audit_rows": m["_n_audit_rows"],
                "n_proposal_ne_final": m["_n_prop_ne_final"],
                "n_final_ne_executed": m["_n_final_ne_executed"],
                "n_proposal_ne_executed": m["_n_prop_ne_executed"],
            })
    rows.append({"row_type": "level_disagreement", "seed": "TOTAL", "arm": "both",
                 "n_audit_rows": total_audit, "n_proposal_ne_final": n_pf,
                 "n_final_ne_executed": n_fe, "n_proposal_ne_executed": n_pe})
    print(f"\n  proposal/final/executed disagreement across all {len(SEEDS)*2} run "
          f"instances ({total_audit} audit rows total): "
          f"proposal!=final {n_pf}, final!=executed {n_fe}, proposal!=executed {n_pe}")

    r7 = _load_r7()
    for m in METRICS:
        pairs = [(s, gov_m[s][m], dis_m[s][m]) for s in SEEDS]
        for s, g, u in pairs:
            rows.append({
                "row_type": "pair", "metric": m, "seed": s,
                "value_governed": g, "value_ungoverned": u, "diff": g - u,
                "governed_source": GOV_SRC[s], "ungoverned_source": DIS_SRC[s],
            })
        g_all = [g for _, g, _ in pairs]
        u_all = [u for _, _, u in pairs]
        d = [g - u for g, u in zip(g_all, u_all)]
        t, df = C.paired_t(d)
        stat = {
            "row_type": "stat", "metric": m, "n_pairs": len(d),
            "mean_governed": C.mean(g_all), "sd_governed": C.sd(g_all),
            "mean_ungoverned": C.mean(u_all), "sd_ungoverned": C.sd(u_all),
            "mean_diff": C.mean(d), "sd_diff": C.sd(d),
            "min_diff": min(d), "max_diff": max(d),
            "n_sign_flips": sum(1 for x in d if (x > 0) != (C.mean(d) > 0)),
            "all_same_sign": len({1 if x > 0 else (-1 if x < 0 else 0) for x in d}) == 1,
            "t": t, "df": float(df),
            "p_paired_t": C.t_two_sided_p(t, df),
            "p_exact_permutation": C.exact_perm_p(d),
            "permutation_floor": 2.0 / (1 << len(d)),
        }
        r7key = R7_KEY.get(m)
        rr = r7.get(r7key) if r7key else None
        if rr is not None:
            stat["r7_n5_mean_diff"] = rr["mean_diff"]
            stat["r7_n5_p_paired_t"] = rr["p_paired_t"]
            stat["r7_n5_p_exact_permutation"] = rr["p_exact_permutation"]
            stat["r7_n5_n_sign_flips"] = rr["n_sign_flips"]
            stat["r7_n5_note"] = ("out/r7_seed_robustness.csv "
                                  "pairing=run_index_n5_published noval_arm=live "
                                  f"metric={r7key}")
        else:
            stat["r7_n5_mean_diff"] = NAD
            stat["r7_n5_p_paired_t"] = NAD
            stat["r7_n5_p_exact_permutation"] = NAD
            stat["r7_n5_n_sign_flips"] = NAD
            stat["r7_n5_note"] = "metric not computed in r7 (new in r11)"
        rows.append(stat)

    # ---- 5. sensitivity: matched vs unmatched, same seed and same arm -----
    print(f"\n  sensitivity (matched {ref_num_ctx}/{ref_num_predict}/{ref_thinking_mode} vs "
          f"unmatched 4096/2048/auto), same seed + same arm, same code commit:")
    sens_specs = [
        ("governed", "43", GOV_NEW_ROOT_MATCHED, GOV_NEW_ROOT_UNMATCHED),
        ("governed", "44", GOV_NEW_ROOT_MATCHED, GOV_NEW_ROOT_UNMATCHED),
        ("ungoverned", "4202", DIS_NEW_ROOT_MATCHED, DIS_NEW_ROOT_UNMATCHED),
        ("ungoverned", "4203", DIS_NEW_ROOT_MATCHED, DIS_NEW_ROOT_UNMATCHED),
    ]
    for arm, seed, matched_root, unmatched_root in sens_specs:
        run_name = f"Run_{seed}"
        m_seed, m_dir = _new_run(matched_root, run_name)
        u_seed, u_dir = _new_run(unmatched_root, run_name)
        if m_seed != seed or u_seed != seed:
            raise PrepError(f"sensitivity {run_name}: matched seed {m_seed}, "
                             f"unmatched seed {u_seed}, expected {seed}")
        m_metrics = _metrics_for(m_dir)
        u_metrics = _metrics_for(u_dir)
        for metric in SENS_METRICS:
            mv, uv = m_metrics[metric], u_metrics[metric]
            rows.append({
                "row_type": "sensitivity", "arm": arm, "seed": seed, "metric": metric,
                "value_matched": mv, "value_unmatched": uv,
                "diff_matched_minus_unmatched": mv - uv,
                "matched_run_dir": os.path.relpath(m_dir, C.REPO).replace("\\", "/"),
                "unmatched_run_dir": os.path.relpath(u_dir, C.REPO).replace("\\", "/"),
            })
            print(f"    seed {seed:>5s} {arm:11s} {metric:26s} "
                  f"matched={mv:9.3f}  unmatched={uv:9.3f}  diff={mv - uv:+9.3f}")

    out_name = ("r11_flood_seed_matched.csv" if variant == "matched"
                else "r11_flood_seed_matched_unmatched.csv")
    base = ["row_type", "metric", "seed", "arm", "n_pairs", "mean_governed", "sd_governed",
            "mean_ungoverned", "sd_ungoverned", "mean_diff", "sd_diff", "min_diff",
            "max_diff", "n_sign_flips", "all_same_sign", "t", "df", "p_paired_t",
            "p_exact_permutation", "permutation_floor", "r7_n5_mean_diff",
            "r7_n5_p_paired_t", "r7_n5_p_exact_permutation", "r7_n5_n_sign_flips",
            "r7_n5_note", "value_governed", "value_ungoverned", "diff",
            "value_matched", "value_unmatched", "diff_matched_minus_unmatched"]
    extra = sorted({k for r in rows for k in r} - set(base))
    C.write_csv(out_name, base + extra, rows)

    print(f"\n  {'metric':30s} {'gov':>9s} {'noval':>9s} {'diff':>9s} "
          f"{'p_n7':>9s} {'perm_n7':>8s} {'flips':>6s}  |  "
          f"{'r7 diff_n5':>11s} {'r7 p_n5':>9s}")
    for r in rows:
        if r["row_type"] != "stat":
            continue
        r7d = r["r7_n5_mean_diff"]
        r7p = r["r7_n5_p_paired_t"]
        r7d_s = f"{float(r7d):11.3f}" if r7d not in (NAD,) else f"{NAD:>11s}"
        r7p_s = f"{float(r7p):9.5f}" if r7p not in (NAD,) else f"{NAD:>9s}"
        print(f"  {r['metric']:30s} {r['mean_governed']:9.3f} {r['mean_ungoverned']:9.3f} "
              f"{r['mean_diff']:9.3f} {r['p_paired_t']:9.5f} "
              f"{r['p_exact_permutation']:8.4f} {r['n_sign_flips']:6d}  |  {r7d_s} {r7p_s}")
    print("\n  n=7 permutation floor 2/128 = 0.015625 (vs n=5 floor 0.0625, n=3 floor 0.25).")
    print(f"  variant={variant}  ->  wrote {out_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
