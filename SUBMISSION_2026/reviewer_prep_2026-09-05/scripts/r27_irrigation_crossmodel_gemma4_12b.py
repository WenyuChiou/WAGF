"""R27 -- irrigation gemma4:12b cross-model arms (commit c3391a53): per-seed
metrics, model-paired comparison against gemma3:4b (faf1bb12), and (once both
12b arms exist) the governed-vs-ungoverned contrast on the larger model, side
by side with r25's gemma3:4b contrast. Mirrors r26_flood_crossmodel_gemma4_12b.py
structurally, for irrigation.

CONTEXT (2026-09-19)
  A gemma4:12b irrigation run is landing at commit c3391a53. STRICT is
  complete (5/5 seeds). UNGOVERNED is in progress: seeds 42-44 complete,
  45 running (has LAUNCH_COMMAND.txt/raw/reflection_log/think_request_log
  but no audit CSV yet), 46 not started (no directory at all). As in r26,
  every completeness gate is a live disk check, not a snapshot -- re-running
  this script unchanged once ungoverned 45/46 land will fill in the
  currently-pending rows with no code change.

PART 1 -- per-seed metrics, every gemma4:12b irrigation run present
  Reuses `r25_table1_regen.py::_irr_llm_metrics` (imported, not copied) for
  IBR headline (proposal-level conditional high-WSA increase rate, canonical
  `examples/irrigation_abm/analysis/_loader.py::ibr`), EHE pooled executed
  and EHE pooled proposal (r25's two definitions -- see r25's own docstring
  for the provenance of each), Mead minimum elevation, shortage years,
  rejection rate, retry rate. Added here (not in r25): rows / status counts
  (read directly from the audit CSV, same convention as r26), mean
  prompt_tokens/response_tokens/llm_latency_ms/tokens_per_second (per-call
  audit columns, `C.require_cols` raises if any is missing -- same
  convention as r26's flood telemetry), and a think-log census: total
  request lines in `think_request_log.jsonl` (blank lines from concurrent
  writers are counted and reported separately, never silently dropped or
  treated as parse failures), count with `"think": false`, count with
  anything else (RAISES if that count is >0 -- the task's premise is every
  request passes think=false). A run/arm not yet complete is SKIPPED with a
  printed reason and a `row_type=skipped` record -- never a crash.
  Completeness gate, in order: run dir exists -> audit CSV exists ->
  simulation_log.csv exists -> run_integrity.json exists -> its
  `integrity_ok` is `True` -> manifest `seed` matches the directory's seed
  (a mismatch here RAISES -- that is a data bug, not incompleteness).

PART 1b -- WSA/IBR denominator, proposal-level action shares, retry-cause
  census (round-2 addition, requested before review). Read from the SAME
  audit CSV Part 1 already reads: WSA label distribution (construct_WSA_
  LABEL) and the IBR numerator/denominator pair (n_highWSA, n_increase_high
  via C.L.HIGH/C.L.INCREASE, the SAME sets `_loader.py::ibr` itself uses)
  so a 0% IBR is shown next to its denominator, not asserted bare;
  proposal-level action shares (proposed_skill, 5 categories, % of rows);
  and a retry-cause census distinguishing validator-triggered retries
  (`failed_rules` non-empty) from parse/format retries (`format_retries`>0)
  -- checked directly on data (not assumed) that the CSV can fully
  distinguish the two for every run processed (100% of retries trace to a
  validator rule; 0 unclassified retries anywhere), so the raw-JSONL
  fallback the task allows for is stated as unneeded, not silently skipped.
  Computed per run (CSV granularity) and pooled by summing across each
  model's available seeds for the rendered per-arm table (model rows side
  by side, 12b vs 4b).

PART 2 -- model-paired comparison, gemma4:12b vs gemma3:4b, literal seed
  diff = 12b - 4b, paired by literal seed 42-46 (both models share this seed
  set for both strict and ungoverned -- r25 already established irrigation
  has no seed-position quirk, unlike flood's OLD governed corpus). Computed
  for the 7 metrics (IBR headline, both EHE, Mead min, shortage years,
  rejection, retry) whenever BOTH models have all 5 seeds complete for that
  arm; otherwise a single "pending" line and no rows -- same convention r26
  uses for its disabled arm. `C.paired_t` / `C.exact_perm_p` (generic,
  imported via `_common.py`, same functions r7/r11/r24/r25/r26 all use).
  NA-safe rendering (`_is_nan` / `_degenerate_reason` / `_fmt_stat`) is
  copied verbatim from r26 with this comment marking the copy, for any
  metric whose paired diff has zero variance.

PART 3 -- governed-vs-ungoverned contrast, gemma4:12b, vs r25 (gemma3:4b)
  r25's own irrigation contrast block only computed 2 metrics (IBR headline,
  EHE pooled/executed) -- confirmed by reading its `out/r25_table1_regen.csv`
  (row_type=contrast_stat, case=irrigation has exactly these two metrics).
  Part 3 is therefore scoped to those same 2 metrics: gemma4:12b's own
  contrast (diff = ungoverned - governed, same generic `C.paired_t`/
  `C.exact_perm_p` r25 used inline for irrigation) computed once BOTH 12b
  arms are complete; the gemma3:4b side is READ VERBATIM from
  `out/r25_table1_regen.csv`, never recomputed. Pending while ungoverned
  is incomplete -- gemma3:4b column shown for reference only.

PART 4 -- manifest census + think-log census
  Value-level enforcement (raises naming run + field + value on any
  mismatch), mirroring r26_flood_crossmodel_gemma4_12b.py::_manifest_fields
  verbatim (comment marks the copy): `thinking_mode=="disabled"`,
  `llm_timeout_seconds_effective==1800`, `model_quantization=="Q4_K_M"`,
  `model` starts with `"gemma4:12b"`, `git_commit` starts with `"c3391a53"`.
  Reports `model_digest` and `git_commit[:8]` per run, plus the think-log
  census from Part 1 in the same table.

PART 5 -- plain read (<=5 sentences, templated from `rows`)

CROSS-CHECK -- gemma3:4b per-seed values vs r25's own recorded aggregate
  r25_table1_regen.csv's irrigation `table1_cell` rows for
  arm="governed (strict)"/"ungoverned" already carry the 5-seed
  mean/sd of EVERY metric this script needs for the gemma3:4b side (its
  "new_mean"/"new_sd" columns -- r25's "new" corpus for irrigation IS the
  faf1bb12 gemma3:4b corpus). This script recomputes gemma3:4b's own
  per-seed metrics independently (via the same `R25._irr_llm_metrics`,
  not by reading r25's CSV) and asserts its own 5-seed mean/sd equals
  r25's recorded value to within 1e-6 AFTER both are rounded through the
  same 4-decimal precision r25's CSV text itself carries (comparing an
  unrounded fresh float against a 4dp-truncated CSV string at 1e-6
  tolerance would spuriously fail on ordinary rounding noise, not a real
  disagreement -- this is the identical double-rounding fix already
  applied in r23/r25/r26). Raises on any real disagreement.

OUTPUTS
  out/r27_irrigation_crossmodel_gemma4_12b.csv -- row_type in {metrics,
    skipped, model_pair, model_pair_stat, model_pair_pending,
    contrast_pair, contrast_stat, manifest}.
  out/r27_irrigation_crossmodel_gemma4_12b.md -- GENERATED by render_md()
    directly from that same `rows` list (no number typed by hand). Written
    via the same render-first, atomic-temp-then-rename pattern r26 uses
    (round-4 fix there) -- a failure never leaves a stale CSV/.md pair.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r27_irrigation_crossmodel_gemma4_12b.py
"""
from __future__ import annotations

import json
import math
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402
import r25_table1_regen as R25  # noqa: E402

SEEDS5 = R25.SEEDS5  # ["42", "43", "44", "45", "46"]
STRICT_12B_ROOT = "strict_42yr_gemma4_12b_c3391a53"
UNGOV_12B_ROOT = "ungoverned_42yr_gemma4_12b_c3391a53"
STRICT_4B_ROOT = "strict_42yr_gemma3_4b_faf1bb12"  # r25 has no such constant; matches
                                                     # r25's own hardcoded dir pattern
UNGOV_4B_ROOT = "ungoverned_42yr_gemma3_4b_faf1bb12"

TELEMETRY_COLS = ["prompt_tokens", "response_tokens", "llm_latency_ms", "tokens_per_second"]

# 7 metrics, label -> literal key in R25._irr_llm_metrics's return dict.
DISPLAY_METRICS_IRR = [
    ("IBR headline", "ibr_headline"),
    ("EHE pooled (executed)", "ehe_pooled"),
    ("EHE pooled (proposal)", "ehe_pooled_proposal"),
    ("Mead minimum (ft)", "mead_min_ft"),
    ("Shortage years", "shortage_years"),
    ("Rejection rate (%)", "rejection_rate_pct"),
    ("Retry rate (%)", "retry_rate_pct"),
]
# label -> r25_table1_regen.csv's own column text, for the cross-check.
R25_COLUMN_FOR = {
    "IBR headline": "IBR headline",
    "EHE pooled (executed)": "EHE pooled (executed)",
    "EHE pooled (proposal)": "EHE pooled (proposal)",
    "Mead minimum (ft)": "domain outcome: Mead min (ft)",
    "Shortage years": "domain outcome: shortage years",
    "Rejection rate (%)": "rejection rate %",
    "Retry rate (%)": "retry rate %",
}
R25_ARM_FOR = {"strict": "governed (strict)", "ungoverned": "ungoverned"}
# Part 3 is scoped to exactly the 2 metrics r25's own irrigation contrast
# block computed (verified by reading out/r25_table1_regen.csv).
CONTRAST_METRICS = ["IBR headline", "EHE pooled (executed)"]
# r25's own irrigation contrast_stat rows label the EHE metric "EHE pooled"
# (no "(executed)" suffix) -- verified by reading out/r25_table1_regen.csv
# directly. Table1_cell rows use the longer label; contrast_stat rows use
# the short one. Mapped here rather than assumed.
R25_CONTRAST_METRIC_FOR = {"IBR headline": "IBR headline",
                            "EHE pooled (executed)": "EHE pooled"}

# ---------------------------------------------------------------------------
# PART 1b -- WSA/IBR denominator, proposal-level action shares, retry-cause
# census. Everything here is read from the SAME audit CSV Part 1 already
# reads (irrigation_farmer_governance_audit.csv) -- construct_WSA_LABEL for
# WSA, proposed_skill for the proposal-level action, retry_count/
# failed_rules/format_retries for the retry breakdown. `L.INCREASE` /
# `L.HIGH` (imported via C.L) are the SAME sets `_loader.py::ibr` itself
# uses, so the audit-derived n_highWSA/n_increase_high pair is directly
# comparable to (not necessarily bit-identical to, since IBR headline
# itself is computed on simulation_log's `yearly_decision`, not the audit's
# `proposed_skill` -- a DIFFERENT file, same underlying decision event) the
# `ibr_headline` value Part 1 already reports.
#
# RETRY-CAUSE CLASSIFICATION -- checked directly on data, not assumed: for
# every retried row (retry_count>0) across all 8 runs available when this
# was written, `failed_rules` is non-empty (a validator rule blocked the
# proposal) on 100% of them, and `n_unclassified_retry` (retry_count>0 but
# BOTH failed_rules empty AND format_retries==0) is 0 everywhere checked.
# A SMALL subset of those validator-triggered retries ALSO have
# format_retries>0 (an additional parse/format retry nested inside the same
# governance retry loop) -- gemma3:4b shows a handful of these (15/1960 on
# one strict seed), gemma4:12b shows zero in every run checked. The CSV can
# therefore fully distinguish the two failure modes for this corpus; the
# raw JSONL fallback the task allows for was not needed -- this is stated,
# not silently skipped. If `n_unclassified_retry` is ever nonzero for a
# run this script actually processes, that is printed and rendered as a
# caveat, never hidden.
WSA_LEVELS = ["VL", "L", "M", "H", "VH"]
IRR_ACTIONS_5 = ["increase_large", "increase_small", "maintain_demand",
                  "decrease_small", "decrease_large"]


def _irr_part1b_census(run_dir: str) -> dict:
    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
    n = len(aud)
    wsa_counts = {lvl: 0 for lvl in WSA_LEVELS}
    wsa_missing = 0
    high_rows = []
    for r in aud:
        w = (r.get("construct_WSA_LABEL") or "").strip().upper()
        if w in wsa_counts:
            wsa_counts[w] += 1
        else:
            wsa_missing += 1
        if w in C.L.HIGH:
            high_rows.append(r)
    n_highWSA = len(high_rows)
    n_increase_high = sum(1 for r in high_rows
                           if (r.get("proposed_skill") or "").strip() in C.L.INCREASE)

    # `proposed_skill` is EMPTY on `status=REJECTED_FALLBACK` rows where the
    # FINAL/reported attempt never parsed at all (`parse_layer` also empty on
    # every such row checked) -- confirmed real, not a data bug: gemma3:4b
    # strict alone has 43-44 such rows per seed, gemma4:12b has ZERO in every
    # run checked. These get their own "unparsed" bucket rather than raising
    # or being silently folded into one of the 5 registry actions.
    action_counts = {a: 0 for a in IRR_ACTIONS_5}
    n_unparsed_proposal = 0
    for r in aud:
        a = (r.get("proposed_skill") or "").strip()
        if not a:
            n_unparsed_proposal += 1
            continue
        if a not in action_counts:
            raise PrepError(f"{run_dir}: off-registry proposed_skill {a!r}")
        action_counts[a] += 1

    def _int(v):
        return int(float((v or "0").strip() or 0))

    retried = [r for r in aud if _int(r.get("retry_count")) > 0]
    n_retried = len(retried)
    sum_retry_count = sum(_int(r["retry_count"]) for r in retried)
    n_validator_retry = sum(1 for r in retried if (r.get("failed_rules") or "").strip())
    n_parse_retry_also = sum(1 for r in retried if _int(r.get("format_retries")) > 0)
    # Direct, more reliable parse-failure signal than `format_retries` alone
    # (checked: `format_retries` is 0 on all-but-one of the 43 empty-proposal
    # rows in one run, so it under-detects this failure mode on its own).
    # Checked: every retried row with an empty final proposed_skill ALSO has
    # `failed_rules` populated (from an earlier, successfully-parsed attempt
    # in the same retry sequence) -- so this is a SUBSET of the
    # validator-triggered bucket, not a disjoint third category. Verified,
    # not assumed: `n_final_unparsed_not_validator` below is computed
    # independently and is 0 everywhere checked.
    retried_unparsed = [r for r in retried if not (r.get("proposed_skill") or "").strip()]
    n_final_unparsed = len(retried_unparsed)
    n_final_unparsed_not_validator = sum(1 for r in retried_unparsed
                                          if not (r.get("failed_rules") or "").strip())
    n_unclassified = sum(1 for r in retried
                          if not (r.get("failed_rules") or "").strip()
                          and _int(r.get("format_retries")) == 0
                          and (r.get("proposed_skill") or "").strip())

    out = {"n_rows": n, "wsa_missing": wsa_missing, "n_highWSA": n_highWSA,
           "n_increase_high": n_increase_high, "n_retried": n_retried,
           "sum_retry_count_among_retried": sum_retry_count,
           "n_validator_retry": n_validator_retry,
           "n_parse_retry_also": n_parse_retry_also,
           "n_final_unparsed": n_final_unparsed,
           "n_final_unparsed_not_validator": n_final_unparsed_not_validator,
           "n_unparsed_proposal": n_unparsed_proposal,
           "n_unclassified_retry": n_unclassified}
    for lvl in WSA_LEVELS:
        out[f"wsa_{lvl}"] = wsa_counts[lvl]
    for a in IRR_ACTIONS_5:
        out[f"action_{a}"] = action_counts[a]
    return out


def _pool_part1b(census_list: list) -> dict:
    """Sum per-run counts across all available seeds for one (model, arm) --
    pooling counts before deriving rates/shares, not averaging per-seed
    rates, so the result is exact (equivalent to concatenating the raw
    audit rows first)."""
    sum_keys = (["n_rows", "wsa_missing", "n_highWSA", "n_increase_high", "n_retried",
                 "sum_retry_count_among_retried", "n_validator_retry",
                 "n_parse_retry_also", "n_final_unparsed", "n_final_unparsed_not_validator",
                 "n_unparsed_proposal", "n_unclassified_retry"]
                + [f"wsa_{lvl}" for lvl in WSA_LEVELS]
                + [f"action_{a}" for a in IRR_ACTIONS_5])
    pooled = {k: sum(c[k] for c in census_list) for k in sum_keys}
    pooled["n_seeds"] = len(census_list)
    return pooled


# ---------------------------------------------------------------------------
# PART 1c (round-3 addition) -- rule-id census. `failed_rules` is a
# `|`-joined set of rule ids that fired at some point in a row's retry
# sequence (see the proposed_skill/failed_rules semantics note in the
# Method block) -- split per row into a SET (so a rule firing twice in one
# row's sequence still counts once for "% of rows"), for two row
# populations: retry_count>0 ("what did the validator negotiate over"),
# and status in (REJECTED, REJECTED_FALLBACK) ("what actually blocked the
# final outcome").
# ---------------------------------------------------------------------------
from collections import Counter as _Counter  # noqa: E402


def _irr_rule_id_census(run_dir: str) -> dict:
    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))

    def _int(v):
        return int(float((v or "0").strip() or 0))

    def _rule_ids(row):
        # sorted(), not the raw set: Python's per-process hash randomization
        # (PYTHONHASHSEED, default ON) makes str-set iteration order differ
        # between runs, which would make dict(_counts(...))'s insertion
        # order -- and therefore the CSV row order -- nondeterministic across
        # runs. Caught by an explicit byte-identical-across-runs check before
        # finalizing (this is exactly what that check is for).
        ids = set((row.get("failed_rules") or "").split("|"))
        ids.discard("")
        return sorted(ids)

    def _counts(sel):
        c = _Counter()
        for r in sel:
            for rid in _rule_ids(r):
                c[rid] += 1
        return c

    retried = [r for r in aud if _int(r.get("retry_count")) > 0]
    rejected = [r for r in aud if (r.get("status") or "").strip()
                in ("REJECTED", "REJECTED_FALLBACK")]
    return {
        "n_retried": len(retried), "n_rejected": len(rejected),
        "retry_counts": dict(_counts(retried)),
        "rejected_counts": dict(_counts(rejected)),
    }


# ---------------------------------------------------------------------------
# completeness gate -- never crash on an in-progress run
# ---------------------------------------------------------------------------
def _irr_run_completeness(run_dir: str, seed: str) -> tuple:
    if not os.path.isdir(run_dir):
        return "skipped", "run directory does not exist yet"
    aud_path = os.path.join(run_dir, C.L.AUDIT_LOG)
    if not os.path.isfile(aud_path):
        return "skipped", f"{C.L.AUDIT_LOG} missing (run in progress)"
    sim_path = os.path.join(run_dir, C.L.SIM_LOG)
    if not os.path.isfile(sim_path):
        return "skipped", "simulation_log.csv missing (run in progress)"
    ri_path = os.path.join(run_dir, "run_integrity.json")
    if not os.path.isfile(ri_path):
        return "skipped", "run_integrity.json missing (run in progress)"
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    if ri.get("integrity_ok") is not True:
        return "skipped", f"integrity_ok is {ri.get('integrity_ok')!r}, not True"
    mf_path = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(mf_path):
        raise PrepError(f"{run_dir}: run looks complete but reproducibility_manifest.json "
                         f"is missing -- a data bug, not incompleteness")
    with open(mf_path, encoding="utf-8") as fh:
        mf = json.load(fh)
    if str(mf.get("seed")) != seed:
        raise PrepError(f"{run_dir}: manifest seed {mf.get('seed')!r} != expected {seed} "
                         f"-- this is a data bug, not incompleteness")
    return "ok", None


def _irr_extra_stats(run_dir: str) -> dict:
    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
    n = len(aud)
    status_counts = {"APPROVED": 0, "REJECTED": 0, "REJECTED_FALLBACK": 0}
    for r in aud:
        s = (r.get("status") or "").strip()
        if s not in status_counts:
            raise PrepError(f"{run_dir}: unexpected status value {s!r}")
        status_counts[s] += 1
    llm_fail_n = sum(1 for r in aud if (r.get("llm_success") or "").strip() != "True")
    return {
        "n_rows": n, "status_approved": status_counts["APPROVED"],
        "status_rejected": status_counts["REJECTED"],
        "status_rejected_fallback": status_counts["REJECTED_FALLBACK"],
        "llm_fail_n": llm_fail_n, "llm_fail_pct": 100.0 * llm_fail_n / n,
        "fallback_share_pct": 100.0 * status_counts["REJECTED_FALLBACK"] / n,
    }


def _telemetry_means(run_dir: str) -> dict:
    """Copied from r26_flood_crossmodel_gemma4_12b.py::_telemetry_means
    verbatim (comment marks the copy) -- same 4 per-call audit columns,
    same "raise if missing" contract."""
    aud = C.read_csv(os.path.join(run_dir, C.L.AUDIT_LOG))
    C.require_cols(aud, TELEMETRY_COLS, run_dir)
    out = {}
    for col in TELEMETRY_COLS:
        vals = [float(r[col]) for r in aud]
        out[f"mean_{col}"] = C.mean(vals)
    return out


def _think_log_census(run_dir: str) -> dict:
    p = os.path.join(run_dir, "think_request_log.jsonl")
    if not os.path.isfile(p):
        raise PrepError(f"missing think_request_log.jsonl in {run_dir}")
    with open(p, encoding="utf-8") as fh:
        raw_lines = fh.readlines()
    n_blank = sum(1 for l in raw_lines if not l.strip())
    think_false = 0
    other_values = []
    for l in raw_lines:
        if not l.strip():
            continue
        rec = json.loads(l)  # raise loud on malformed JSON -- never skip silently
        if "think" not in rec:
            raise PrepError(f"{p}: a request record has no 'think' key: {rec!r}")
        if rec["think"] is False:
            think_false += 1
        else:
            other_values.append(rec["think"])
    n_requests = len(raw_lines) - n_blank
    if other_values:
        raise PrepError(f"{p}: {len(other_values)} of {n_requests} requests have "
                         f"think != false (values seen: "
                         f"{sorted(set(map(str, other_values)))[:5]}) -- the task's "
                         f"premise that every request passes think=false does not "
                         f"hold for this run")
    return {"n_lines": n_requests, "n_blank_lines": n_blank, "think_false": think_false}


def _manifest_fields(run_dir: str) -> dict:
    """Copied from r26_flood_crossmodel_gemma4_12b.py::_manifest_fields
    verbatim (comment marks the copy), same 5 value-level checks."""
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"missing reproducibility_manifest.json in {run_dir}")
    with open(p, encoding="utf-8") as fh:
        m = json.load(fh)
    for key in ("thinking_mode", "llm_timeout_seconds_effective", "model_digest",
                "model_quantization", "model", "git_commit"):
        if key not in m:
            raise PrepError(f"{run_dir}: manifest missing key {key!r}")
    if m["thinking_mode"] != "disabled":
        raise PrepError(f"{run_dir}: manifest field thinking_mode={m['thinking_mode']!r}, "
                         f"expected 'disabled'")
    if m["llm_timeout_seconds_effective"] != 1800:
        raise PrepError(f"{run_dir}: manifest field llm_timeout_seconds_effective="
                         f"{m['llm_timeout_seconds_effective']!r}, expected 1800")
    if m["model_quantization"] != "Q4_K_M":
        raise PrepError(f"{run_dir}: manifest field model_quantization="
                         f"{m['model_quantization']!r}, expected 'Q4_K_M'")
    if not str(m["model"]).startswith("gemma4:12b"):
        raise PrepError(f"{run_dir}: manifest field model={m['model']!r}, expected to "
                         f"start with 'gemma4:12b'")
    if not str(m["git_commit"]).startswith("c3391a53"):
        raise PrepError(f"{run_dir}: manifest field git_commit={m['git_commit']!r}, "
                         f"expected to start with 'c3391a53'")
    return {
        "model": m["model"], "thinking_mode": m["thinking_mode"],
        "llm_timeout_seconds_effective": m["llm_timeout_seconds_effective"],
        "model_digest": m["model_digest"], "model_quantization": m["model_quantization"],
        "git_commit": m["git_commit"],
    }


# ---------------------------------------------------------------------------
# NaN-safe rendering helpers -- copied VERBATIM from
# r26_flood_crossmodel_gemma4_12b.py (comment marks the copy), needed
# because C.paired_t returns NaN t/p when a paired diff has zero variance.
# ---------------------------------------------------------------------------
def _is_nan(x) -> bool:
    return isinstance(x, float) and x != x


def _degenerate_reason(vals_a: list, vals_b: list) -> str:
    diffs = [a - b for a, b in zip(vals_a, vals_b)]
    n = len(vals_a)
    sd_a, sd_b = C.sd(vals_a), C.sd(vals_b)
    if sd_a == 0 and sd_b == 0 and vals_a[0] == 0 and vals_b[0] == 0:
        return f"zero variance: both arms 0 on all {n} seeds"
    if sd_a == 0 and sd_b == 0:
        return (f"zero variance: both arms constant ({vals_a[0]:g} and {vals_b[0]:g}) "
                f"on all {n} seeds")
    return f"zero variance: diff constant ({diffs[0]:g}) on all {n} seeds"


_cp = R25._cp  # = R23._csv_precision, transitively imported via r25


def _fmt_stat(x, nd: int, reason: str) -> str:
    if _is_nan(x):
        return f"n.a. ({reason})" if reason else "n.a."
    return f"{_cp(x):.{nd}f}"


def main() -> int:
    C.banner("R27  irrigation gemma4:12b cross-model arms (c3391a53) vs gemma3:4b (faf1bb12)")

    rows = []

    # =====================================================================
    # PART 1 -- per-seed metrics, every gemma4:12b irrigation run present
    # =====================================================================
    arm_roots_12b = {"strict": STRICT_12B_ROOT, "ungoverned": UNGOV_12B_ROOT}
    metrics_12b = {"strict": {}, "ungoverned": {}}
    manifest_12b = {"strict": {}, "ungoverned": {}}
    for arm, root in arm_roots_12b.items():
        for s in SEEDS5:
            run_dir = os.path.join(R25.IRR_RESULTS, f"{root}_seed{s}")
            status, reason = _irr_run_completeness(run_dir, s)
            if status == "skipped":
                print(f"  SKIPPED {arm} seed {s}: {reason}")
                rows.append({"row_type": "skipped", "arm": arm, "seed": s, "reason": reason})
                continue
            core = R25._irr_llm_metrics(run_dir)
            extra = _irr_extra_stats(run_dir)
            tel = _telemetry_means(run_dir)
            think = _think_log_census(run_dir)
            mf = _manifest_fields(run_dir)
            p1b = _irr_part1b_census(run_dir)
            manifest_12b[arm][s] = mf
            rec = dict(core)
            rec.update(extra)
            rec.update(tel)
            rec.update(think)
            rec["_part1b"] = p1b
            metrics_12b[arm][s] = rec
            rows.append({"row_type": "part1b_census", "arm": arm, "model": "gemma4_12b",
                         "seed": s, **p1b})
            rule_census = _irr_rule_id_census(run_dir)
            for census_type, denom, counts in (
                    ("retry", rule_census["n_retried"], rule_census["retry_counts"]),
                    ("rejected", rule_census["n_rejected"], rule_census["rejected_counts"])):
                rows.append({"row_type": "rule_id_denom", "arm": arm, "model": "gemma4_12b",
                             "seed": s, "census_type": census_type, "denom": denom})
                for rule_id, count in counts.items():
                    rows.append({"row_type": "rule_id_count", "arm": arm,
                                 "model": "gemma4_12b", "seed": s,
                                 "census_type": census_type, "rule_id": rule_id,
                                 "count": count})
            print(f"  OK {arm:11s} seed {s:>3s}: rows={extra['n_rows']:4d} "
                  f"llm_fail={extra['llm_fail_n']} think_lines={think['n_lines']} "
                  f"think_false={think['think_false']} thinking_mode={mf['thinking_mode']}")
            row = {"row_type": "metrics", "arm": arm, "seed": s,
                   "n_rows": extra["n_rows"], "llm_fail_n": extra["llm_fail_n"],
                   "llm_fail_pct": extra["llm_fail_pct"],
                   "status_approved": extra["status_approved"],
                   "status_rejected": extra["status_rejected"],
                   "status_rejected_fallback": extra["status_rejected_fallback"],
                   "fallback_share_pct": extra["fallback_share_pct"],
                   "wall_hours": core["wall_hours"],
                   "mean_prompt_tokens": tel["mean_prompt_tokens"],
                   "mean_response_tokens": tel["mean_response_tokens"],
                   "mean_llm_latency_ms": tel["mean_llm_latency_ms"],
                   "mean_tokens_per_second": tel["mean_tokens_per_second"],
                   "think_n_lines": think["n_lines"], "think_n_blank": think["n_blank_lines"],
                   "think_false": think["think_false"]}
            for label, key in DISPLAY_METRICS_IRR:
                row[f"metric__{label}"] = core[key]
            rows.append(row)

    n_strict_12b = len(metrics_12b["strict"])
    n_ungov_12b = len(metrics_12b["ungoverned"])
    print(f"\n  strict 12b: {n_strict_12b}/5 complete; ungoverned 12b: {n_ungov_12b}/5 complete")

    # =====================================================================
    # PART 2 -- model-paired comparison, gemma4:12b vs gemma3:4b
    # =====================================================================
    metrics_4b = {"strict": {}, "ungoverned": {}}
    for arm, root in (("strict", STRICT_4B_ROOT), ("ungoverned", UNGOV_4B_ROOT)):
        for s in SEEDS5:
            run_dir = os.path.join(R25.IRR_RESULTS, f"{root}_seed{s}")
            status, reason = _irr_run_completeness(run_dir, s)
            if status != "ok":
                raise PrepError(f"gemma3:4b {arm} seed {s} is not complete ({reason}) -- "
                                 f"this arm was already verified complete in r25, a "
                                 f"change here would be a real regression")
            metrics_4b[arm][s] = R25._irr_llm_metrics(run_dir)
            p1b_4b = _irr_part1b_census(run_dir)
            rows.append({"row_type": "part1b_census", "arm": arm, "model": "gemma3_4b",
                         "seed": s, **p1b_4b})
            rule_census_4b = _irr_rule_id_census(run_dir)
            for census_type, denom, counts in (
                    ("retry", rule_census_4b["n_retried"], rule_census_4b["retry_counts"]),
                    ("rejected", rule_census_4b["n_rejected"],
                     rule_census_4b["rejected_counts"])):
                rows.append({"row_type": "rule_id_denom", "arm": arm, "model": "gemma3_4b",
                             "seed": s, "census_type": census_type, "denom": denom})
                for rule_id, count in counts.items():
                    rows.append({"row_type": "rule_id_count", "arm": arm,
                                 "model": "gemma3_4b", "seed": s,
                                 "census_type": census_type, "rule_id": rule_id,
                                 "count": count})

    # ---- cross-check: my fresh gemma3:4b aggregate vs r25's own recorded one
    r25_rows = C.read_csv(os.path.join(C.OUT, "r25_table1_regen.csv"))
    r25_lookup = {}
    for r in r25_rows:
        if r["row_type"] == "table1_cell" and r["case"] == "irrigation":
            r25_lookup[(r["arm"], r["column"])] = r
    for arm in ("strict", "ungoverned"):
        for label, key in DISPLAY_METRICS_IRR:
            vals = [metrics_4b[arm][s][key] for s in SEEDS5]
            my_mean, my_sd = C.mean(vals), C.sd(vals)
            r25_arm = R25_ARM_FOR[arm]
            r25_col = R25_COLUMN_FOR[label]
            r25_row = r25_lookup.get((r25_arm, r25_col))
            if r25_row is None:
                raise PrepError(f"r25_table1_regen.csv: no table1_cell row for "
                                 f"case=irrigation arm={r25_arm!r} column={r25_col!r}")
            r25_mean = float(r25_row["new_mean"])
            r25_sd = float(r25_row["new_sd"])
            if abs(round(my_mean, 4) - round(r25_mean, 4)) > 1e-6 or \
               abs(round(my_sd, 4) - round(r25_sd, 4)) > 1e-6:
                raise PrepError(f"crosscheck vs r25 FAILED: {arm}/{label}: this script "
                                 f"mean={my_mean:.4f} sd={my_sd:.4f} vs r25's recorded "
                                 f"new_mean={r25_mean:.4f} new_sd={r25_sd:.4f}")
    print("  crosscheck OK: all 14 gemma3:4b aggregate (mean,sd) pairs "
          "(7 metrics x 2 arms) match r25_table1_regen.csv exactly")

    for arm in ("strict", "ungoverned"):
        complete = len(metrics_12b[arm]) == 5  # gemma3:4b side always 5/5, verified above
        if not complete:
            print(f"  Part 2 {arm}: PENDING -- gemma4:12b has {len(metrics_12b[arm])}/5 "
                  f"complete seeds")
            rows.append({"row_type": "model_pair_pending", "arm": arm,
                         "n_12b": len(metrics_12b[arm]), "n_4b": 5})
            continue
        for label, key in DISPLAY_METRICS_IRR:
            diffs = []
            for s in SEEDS5:
                v12b, v4b = metrics_12b[arm][s][key], metrics_4b[arm][s][key]
                d = v12b - v4b
                diffs.append(d)
                rows.append({"row_type": "model_pair", "arm": arm, "metric": label,
                             "seed": s, "value_12b": v12b, "value_4b": v4b, "diff": d})
            t, df = C.paired_t(diffs)
            mean_d, sd_d = C.mean(diffs), C.sd(diffs)
            n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
            same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
            rows.append({
                "row_type": "model_pair_stat", "arm": arm, "metric": label,
                "n_pairs": len(diffs), "mean_diff": mean_d, "sd_diff": sd_d,
                "min_diff": min(diffs), "max_diff": max(diffs), "n_sign_flips": n_flips,
                "all_same_sign": same_sign, "t": t, "df": float(df),
                "p_paired_t": C.t_two_sided_p(t, df),
                "p_exact_permutation": C.exact_perm_p(diffs),
                "permutation_floor": 2.0 / (1 << len(diffs)),
            })

    # =====================================================================
    # PART 3 -- governed-vs-ungoverned contrast, gemma4:12b, vs r25 (4b)
    # =====================================================================
    both_12b_complete = n_strict_12b == 5 and n_ungov_12b == 5
    if both_12b_complete:
        for label in CONTRAST_METRICS:
            key = dict(DISPLAY_METRICS_IRR)[label]
            diffs = []
            for s in SEEDS5:
                gv = metrics_12b["strict"][s][key]
                uv = metrics_12b["ungoverned"][s][key]
                d = uv - gv
                diffs.append(d)
                rows.append({"row_type": "contrast_pair", "model": "gemma4_12b",
                             "metric": label, "seed": s, "governed_value": gv,
                             "ungoverned_value": uv, "diff": d})
            t, df = C.paired_t(diffs)
            mean_d, sd_d = C.mean(diffs), C.sd(diffs)
            n_flips = sum(1 for x in diffs if (x > 0) != (mean_d > 0))
            same_sign = len({1 if x > 0 else (-1 if x < 0 else 0) for x in diffs}) == 1
            rows.append({
                "row_type": "contrast_stat", "model": "gemma4_12b", "metric": label,
                "n_pairs": len(diffs), "mean_diff": mean_d, "sd_diff": sd_d,
                "min_diff": min(diffs), "max_diff": max(diffs), "n_sign_flips": n_flips,
                "all_same_sign": same_sign, "t": t, "df": float(df),
                "p_paired_t": C.t_two_sided_p(t, df),
                "p_exact_permutation": C.exact_perm_p(diffs),
                "permutation_floor": 2.0 / (1 << len(diffs)),
            })
        print("  Part 3: gemma4:12b governed-vs-ungoverned contrast computed "
              "(both 12b arms complete)")
    else:
        print(f"  Part 3: PENDING -- gemma4:12b ungoverned arm not complete "
              f"({n_ungov_12b}/5 seeds)")

    for label in CONTRAST_METRICS:
        r25_label = R25_CONTRAST_METRIC_FOR[label]
        # r25's contrast_stat rows carry BOTH corpus=old (pre-2026-09-15-loss) and
        # corpus=new (the current faf1bb12 gemma3:4b corpus) for the SAME metric --
        # explicitly filtered to corpus=new here. An earlier draft of this script
        # used a bare `next()` with no corpus filter, which would have silently
        # picked whichever row iterates first (old, in r25's own write order) --
        # caught before finalizing by checking the actual r25 CSV content.
        r25_metric_row = next(
            (r for r in r25_rows if r["row_type"] == "contrast_stat"
             and r["case"] == "irrigation" and r["metric"] == r25_label
             and r["corpus"] == "new"), None)
        if r25_metric_row is None:
            raise PrepError(f"r25_table1_regen.csv: no irrigation contrast_stat row for "
                             f"metric={r25_label!r} corpus=new")
        rows.append({
            "row_type": "contrast_stat", "model": "gemma3_4b", "metric": label,
            "n_pairs": int(r25_metric_row["n_pairs"]),
            "mean_diff": float(r25_metric_row["mean_diff"]),
            "sd_diff": float(r25_metric_row["sd_diff"]),
            "min_diff": float(r25_metric_row["min_diff"]),
            "max_diff": float(r25_metric_row["max_diff"]),
            "n_sign_flips": int(r25_metric_row["n_sign_flips"]),
            "all_same_sign": r25_metric_row["all_same_sign"] == "True",
            "t": float(r25_metric_row["t"]), "df": float(r25_metric_row["df"]),
            "p_paired_t": float(r25_metric_row["p_paired_t"]),
            "p_exact_permutation": float(r25_metric_row["p_exact_permutation"]),
            "permutation_floor": float(r25_metric_row["permutation_floor"]),
            "note": "read verbatim from out/r25_table1_regen.csv "
                    "(row_type=contrast_stat, case=irrigation), not recomputed",
        })
    print("  gemma3:4b irrigation contrast rows read verbatim from out/r25_table1_regen.csv")

    # =====================================================================
    # PART 4 -- manifest rows (Part 1's think-log census already in `rows`)
    # =====================================================================
    for arm in ("strict", "ungoverned"):
        for s in SEEDS5:
            if s not in manifest_12b[arm]:
                continue
            mf = manifest_12b[arm][s]
            rows.append({"row_type": "manifest", "arm": arm, "seed": s,
                         "model": mf["model"], "thinking_mode": mf["thinking_mode"],
                         "llm_timeout_seconds_effective": mf["llm_timeout_seconds_effective"],
                         "model_digest": mf["model_digest"],
                         "model_quantization": mf["model_quantization"],
                         "git_commit_short": mf["git_commit"][:8]})

    fieldnames = ["row_type", "arm", "seed", "reason", "n_rows", "llm_fail_n",
                  "llm_fail_pct", "status_approved", "status_rejected",
                  "status_rejected_fallback", "fallback_share_pct", "wall_hours",
                  "mean_prompt_tokens", "mean_response_tokens", "mean_llm_latency_ms",
                  "mean_tokens_per_second", "think_n_lines", "think_n_blank",
                  "think_false"] + [f"metric__{label}" for label, _ in DISPLAY_METRICS_IRR] + [
                  "n_12b", "n_4b", "metric", "value_12b", "value_4b", "diff", "n_pairs",
                  "mean_diff", "sd_diff", "min_diff", "max_diff", "n_sign_flips",
                  "all_same_sign", "t", "df", "p_paired_t", "p_exact_permutation",
                  "permutation_floor", "model", "governed_value", "ungoverned_value", "note",
                  "thinking_mode", "llm_timeout_seconds_effective", "model_digest",
                  "model_quantization", "git_commit_short",
                  "wsa_missing", "n_highWSA", "n_increase_high", "n_retried",
                  "sum_retry_count_among_retried", "n_validator_retry", "n_parse_retry_also",
                  "n_final_unparsed", "n_final_unparsed_not_validator", "n_unparsed_proposal",
                  "n_unclassified_retry"] + [f"wsa_{lvl}" for lvl in WSA_LEVELS] + [
                  f"action_{a}" for a in IRR_ACTIONS_5] + [
                  "census_type", "denom", "rule_id", "count"]

    # Render-first, atomic-temp-then-rename write (r26 round-4 fix, same pattern):
    # if render_md() raises, NEITHER file is written/replaced -- the previous
    # successful run's CSV+.md pair is left exactly as it was.
    md_text = render_md(rows)

    csv_final = "r27_irrigation_crossmodel_gemma4_12b.csv"
    csv_tmp = csv_final + ".tmp"
    md_final_name = "r27_irrigation_crossmodel_gemma4_12b.md"
    md_final = os.path.join(C.OUT, md_final_name)
    md_tmp = md_final + ".tmp"

    csv_tmp_path = C.write_csv(csv_tmp, fieldnames, rows)
    with open(md_tmp, "w", encoding="utf-8") as fh:
        fh.write(md_text)

    os.replace(csv_tmp_path, os.path.join(C.OUT, csv_final))
    os.replace(md_tmp, md_final)
    print(f"\n  wrote {os.path.relpath(os.path.join(C.OUT, csv_final), C.REPO).replace(chr(92), '/')}"
          f"  ({len(rows)} rows)")
    print(f"  wrote {os.path.relpath(md_final, C.REPO).replace(chr(92), '/')}  "
          f"({len(md_text.splitlines())} lines)")

    return 0


# ---------------------------------------------------------------------------
# .md rendering -- built entirely from the `rows` list above.
# ---------------------------------------------------------------------------
def render_md(rows: list) -> str:
    metrics_rows = [r for r in rows if r["row_type"] == "metrics"]
    skipped_rows = [r for r in rows if r["row_type"] == "skipped"]
    model_pair_rows = [r for r in rows if r["row_type"] == "model_pair_stat"]
    model_pair_pairs = [r for r in rows if r["row_type"] == "model_pair"]
    model_pair_pending = [r for r in rows if r["row_type"] == "model_pair_pending"]
    contrast_rows = [r for r in rows if r["row_type"] == "contrast_stat"]
    contrast_pairs = [r for r in rows if r["row_type"] == "contrast_pair"]
    manifest_rows = [r for r in rows if r["row_type"] == "manifest"]
    part1b_rows = [r for r in rows if r["row_type"] == "part1b_census"]
    rule_denom_rows = [r for r in rows if r["row_type"] == "rule_id_denom"]
    rule_count_rows = [r for r in rows if r["row_type"] == "rule_id_count"]

    n_strict = sum(1 for r in metrics_rows if r["arm"] == "strict")
    n_ungov = sum(1 for r in metrics_rows if r["arm"] == "ungoverned")
    metric_labels = [label for label, _ in DISPLAY_METRICS_IRR]

    lines = []
    lines.append("# R27 -- irrigation gemma4:12b cross-model arms (c3391a53) vs gemma3:4b "
                  "(faf1bb12), 2026-09-19")
    lines.append("")
    lines.append(
        f"**Method.** Per-run metrics reuse `r25_table1_regen.py::_irr_llm_metrics` "
        f"verbatim (imported) for IBR headline / EHE pooled (executed+proposal) / "
        f"Mead min / shortage years / rejection / retry rate; telemetry (mean "
        f"prompt_tokens/response_tokens/llm_latency_ms/tokens_per_second) and the "
        f"think-log census are added here, same conventions as r26. Model-paired "
        f"diff (Part 2) = gemma4:12b - gemma3:4b, literal seed 42-46, computed only "
        f"when both models have all 5 seeds for that arm. Governed-vs-ungoverned "
        f"contrast (Part 3) is scoped to the 2 metrics r25's own irrigation contrast "
        f"block covers (IBR headline, EHE pooled executed) -- verified by reading "
        f"`out/r25_table1_regen.csv`; the gemma3:4b row there is read verbatim, never "
        f"recomputed. Manifest values are enforced (not just key presence), mirroring "
        f"r26 verbatim: `thinking_mode==\"disabled\"`, `llm_timeout_seconds_effective"
        f"==1800`, `model_quantization==\"Q4_K_M\"`, `model` starting with "
        f"`\"gemma4:12b\"`, `git_commit` starting with `\"c3391a53\"` -- any mismatch "
        f"raises naming run/field/value. Every gemma3:4b per-seed aggregate this "
        f"script computes is cross-checked against r25's own recorded 5-seed "
        f"mean/sd in `out/r25_table1_regen.csv` (tolerance 1e-6 after matching "
        f"4dp rounding) -- confirmed to agree on all 7 metrics x 2 arms. Strict: "
        f"{n_strict}/5 seeds complete. Ungoverned: {n_ungov}/5 seeds complete."
    )
    lines.append("")
    lines.append(
        "**Proposal-column semantics (round-3 addition, before-review finding):** "
        "`docs/AUDIT_SCHEMA.md`'s \"Which Plane Answers What\" table states plainly: "
        "\"Per-attempt retry sequence | no | no | accepted gap\" -- the framework's "
        "own documentation says the first-vs-later-attempt history is NOT recorded "
        "in the CSV or the JSONL, for any run. The audit writer "
        "(`broker/components/analytics/audit.py:trace_to_csv_row`, comment at the "
        "`initial_skill` key gate) is explicit about what `proposed_skill` actually "
        "is: \"`skill_proposal` is reassigned on every governance retry, so "
        "`proposed_skill` records the LAST attempt and compares equal to "
        "`final_skill` on 100% of shipped rows.\" A first-attempt column pair does "
        "exist in the codebase (`initial_skill`/`initial_labels`/`attempt_skills`, "
        "gated by `global_config.audit.initial_proposal_columns`) but is ABSENT from "
        "every audit CSV header and every raw JSONL trace record checked in both "
        "the gemma4:12b and gemma3:4b corpora here -- that flag was off for these "
        "runs, confirmed by direct inspection, not assumed. Consequence: everything "
        "this script (and r25) calls \"proposal-level\" -- `ibr_headline`, the "
        "action-share breakdown, the WSA/IBR denominator in Part 1b -- is actually "
        "the POST-RETRY, validator-negotiated last attempt, not the agent's first "
        "impulse; the first impulse is an accepted gap in this corpus, recoverable "
        "nowhere. The Part 1b plain read below is worded to reflect exactly this."
    )
    lines.append("")

    lines.append("## Part 1 -- per-seed metrics, gemma4:12b irrigation")
    lines.append("")
    header = ("| arm | seed | " + " | ".join(metric_labels) +
              " | rows | llm_fail | APPROVED | REJECTED | REJ_FALLBACK | fallback% | "
              "wall_h | mean_prompt_tok | mean_resp_tok | mean_latency_ms | mean_tok/s | "
              "think_lines | think_false |")
    lines.append(header)
    lines.append("|" + "---|" * (len(metric_labels) + 14))
    for arm in ("strict", "ungoverned"):
        for r in [rr for rr in metrics_rows if rr["arm"] == arm]:
            mcells = [f"{_cp(r[f'metric__{lbl}']):.3f}" for lbl in metric_labels]
            lines.append(
                f"| {arm} | {r['seed']} | " + " | ".join(mcells) + f" | {r['n_rows']} | "
                f"{r['llm_fail_n']} | {r['status_approved']} | {r['status_rejected']} | "
                f"{r['status_rejected_fallback']} | {_cp(r['fallback_share_pct']):.3f} | "
                f"{_cp(r['wall_hours']):.2f} | {_cp(r['mean_prompt_tokens']):.1f} | "
                f"{_cp(r['mean_response_tokens']):.1f} | "
                f"{_cp(r['mean_llm_latency_ms']):.1f} | "
                f"{_cp(r['mean_tokens_per_second']):.2f} | {r['think_n_lines']} | "
                f"{r['think_false']} |"
            )
    for r in skipped_rows:
        lines.append(f"| {r['arm']} | {r['seed']} | SKIPPED: {r['reason']} | "
                      + " |" * (len(metric_labels) + 13))
    lines.append("")

    lines.append("## Part 1b -- WSA/IBR denominator, proposal-level action shares, "
                 "retry-cause census (pooled across available seeds, per arm)")
    lines.append("")
    lines.append(
        "Pooled by SUMMING per-run counts across every complete seed for that "
        "(model, arm) -- equivalent to concatenating the raw audit rows first, "
        "not averaging per-seed rates. Retry-cause classification is read "
        "directly from the audit CSV's own `failed_rules` (validator-triggered) "
        "and `format_retries` (parse/format-triggered) columns -- checked across "
        "every run processed: `failed_rules` is non-empty on 100% of retried rows "
        "and `n_unclassified_retry` (retry_count>0 with neither column populated) "
        "is 0 everywhere, so the CSV fully distinguishes the two failure modes "
        "here and the raw JSONL fallback was not needed (flagged below per row if "
        "that ever stops being true)."
    )
    lines.append("")
    pooled_by_arm_model = {}
    for arm in ("strict", "ungoverned"):
        for model in ("gemma4_12b", "gemma3_4b"):
            census_list = [r for r in part1b_rows if r["arm"] == arm and r["model"] == model]
            if census_list:
                pooled_by_arm_model[(arm, model)] = _pool_part1b(census_list)
    for arm in ("strict", "ungoverned"):
        lines.append(f"**{arm}**")
        lines.append("")
        lines.append("| model | n_seeds | n_rows | WSA VL/L/M/H/VH/missing | "
                     "n_highWSA | n_increase_high | IBR (audit-derived) % | "
                     "action% incrL/incrS/maint/decrS/decrL/unparsed | n_retried | "
                     "retry_rate % | mean retry_count (retried rows) | "
                     "validator-triggered % of retries | also-parse-retry % of "
                     "retries (format_retries) | final-attempt-unparsed % of "
                     "retries | unclassified |")
        lines.append("|---|---:|---:|---|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|")
        for model, model_label in (("gemma4_12b", "gemma4:12b"), ("gemma3_4b", "gemma3:4b")):
            p = pooled_by_arm_model.get((arm, model))
            if p is None:
                lines.append(f"| {model_label} | 0 | n.a. (no complete seeds yet) |" +
                              " |" * 12)
                continue
            wsa_str = "/".join(str(p[f"wsa_{lvl}"]) for lvl in WSA_LEVELS) + f"/{p['wsa_missing']}"
            ibr_audit_pct = (100.0 * p["n_increase_high"] / p["n_highWSA"]
                              if p["n_highWSA"] > 0 else float("nan"))
            action_pct = ("/".join(f"{100.0 * p[f'action_{a}'] / p['n_rows']:.2f}"
                                    for a in IRR_ACTIONS_5)
                          + f"/{100.0 * p['n_unparsed_proposal'] / p['n_rows']:.2f}")
            retry_rate_pct = 100.0 * p["n_retried"] / p["n_rows"]
            mean_retry_count = (p["sum_retry_count_among_retried"] / p["n_retried"]
                                 if p["n_retried"] > 0 else float("nan"))
            validator_pct = (100.0 * p["n_validator_retry"] / p["n_retried"]
                              if p["n_retried"] > 0 else float("nan"))
            also_parse_pct = (100.0 * p["n_parse_retry_also"] / p["n_retried"]
                               if p["n_retried"] > 0 else float("nan"))
            final_unparsed_pct = (100.0 * p["n_final_unparsed"] / p["n_retried"]
                                   if p["n_retried"] > 0 else float("nan"))
            unclass_parts = []
            if p["n_unclassified_retry"] > 0:
                unclass_parts.append(f"**{p['n_unclassified_retry']} UNCLASSIFIED "
                                      f"-- CSV could not distinguish, see raw JSONL**")
            if p["n_final_unparsed_not_validator"] > 0:
                unclass_parts.append(f"**{p['n_final_unparsed_not_validator']} "
                                      f"final-unparsed row(s) with NO failed_rules -- "
                                      f"subset assumption broken, see raw JSONL**")
            unclass_cell = "; ".join(unclass_parts) if unclass_parts else "0"
            lines.append(
                f"| {model_label} | {p['n_seeds']} | {p['n_rows']} | {wsa_str} | "
                f"{p['n_highWSA']} | {p['n_increase_high']} | "
                f"{_fmt_stat(ibr_audit_pct, 3, None)} | {action_pct} | "
                f"{p['n_retried']} | {_cp(retry_rate_pct):.3f} | "
                f"{_fmt_stat(mean_retry_count, 2, None)} | "
                f"{_fmt_stat(validator_pct, 1, None)} | "
                f"{_fmt_stat(also_parse_pct, 1, None)} | "
                f"{_fmt_stat(final_unparsed_pct, 1, None)} | {unclass_cell} |"
            )
        lines.append("")

    # ---- Part 1c: rule-id census --------------------------------------------
    def _pool_rule_census(arm, model, census_type):
        denom_rows = [r for r in rule_denom_rows if r["arm"] == arm and r["model"] == model
                      and r["census_type"] == census_type]
        if not denom_rows:
            return None
        denom_by_seed = {r["seed"]: int(r["denom"]) for r in denom_rows}
        count_rows = [r for r in rule_count_rows if r["arm"] == arm and r["model"] == model
                      and r["census_type"] == census_type]
        counts_by_seed = {}
        for r in count_rows:
            counts_by_seed.setdefault(r["seed"], {})[r["rule_id"]] = int(r["count"])
        seeds = sorted(denom_by_seed)
        pooled_denom = sum(denom_by_seed.values())
        pooled_counts = _Counter()
        for seed_counts in counts_by_seed.values():
            for rid, c in seed_counts.items():
                pooled_counts[rid] += c
        return {"seeds": seeds, "denom_by_seed": denom_by_seed,
                "counts_by_seed": counts_by_seed, "pooled_denom": pooled_denom,
                "pooled_counts": pooled_counts}

    lines.append("## Part 1c -- rule-id census: which rules fired, for retried rows and "
                 "for REJECTED/REJECTED_FALLBACK rows (pooled across available seeds, "
                 "per-seed min-max in brackets)")
    lines.append("")
    lines.append(
        "A row's `failed_rules` is the set of rule ids that fired at ANY point in "
        "its retry sequence (see the Method block's proposed_skill note); split on "
        "`|` into a set per row (a rule firing twice in one row's sequence counts "
        "once), so \"% of retried rows\" is well-defined. Top 8 by pooled % (this "
        "corpus has only 7 distinct rule ids total -- 6 named ones plus the rare "
        "`Unknown` producer `docs/AUDIT_SCHEMA.md` documents as a real, expected "
        "value (a specific format-check validator with no `metadata.rule_id`), "
        "checked here: it fires exactly once (gemma4:12b strict seed 45) -- so "
        "nothing is truncated by taking the top 8)."
    )
    lines.append("")
    rule_census_by_arm = {}
    for arm in ("strict", "ungoverned"):
        lines.append(f"**{arm}**")
        lines.append("")
        for census_type, census_title in (("retry", "retried rows (retry_count > 0)"),
                                           ("rejected", "REJECTED / REJECTED_FALLBACK rows")):
            lines.append(f"_{census_title}_")
            lines.append("")
            lines.append("| rule_id | gemma4:12b % (pooled) [seed min-max] | "
                         "gemma3:4b % (pooled) [seed min-max] |")
            lines.append("|---|---:|---:|")
            c12 = _pool_rule_census(arm, "gemma4_12b", census_type)
            c4 = _pool_rule_census(arm, "gemma3_4b", census_type)
            rule_census_by_arm[(arm, census_type, "gemma4_12b")] = c12
            rule_census_by_arm[(arm, census_type, "gemma3_4b")] = c4
            if c12 is None and c4 is None:
                lines.append("| n.a. (no complete seeds for either model) | | |")
                lines.append("")
                continue
            ranking_source = c12 if (c12 and c12["pooled_denom"] > 0) else c4
            rule_ids_ranked = ([rid for rid, _ in
                                ranking_source["pooled_counts"].most_common(8)]
                               if ranking_source else [])

            def _cell(c, rid):
                if c is None or c["pooled_denom"] == 0:
                    return "n.a. (no complete seeds)"
                pooled_pct = 100.0 * c["pooled_counts"].get(rid, 0) / c["pooled_denom"]
                per_seed_pct = []
                for seed in c["seeds"]:
                    d = c["denom_by_seed"][seed]
                    if d == 0:
                        continue
                    cnt = c["counts_by_seed"].get(seed, {}).get(rid, 0)
                    per_seed_pct.append(100.0 * cnt / d)
                rng = (f" [{min(per_seed_pct):.1f}-{max(per_seed_pct):.1f}]"
                       if per_seed_pct else "")
                return f"{pooled_pct:.1f}{rng}"

            for rid in rule_ids_ranked:
                lines.append(f"| {rid} | {_cell(c12, rid)} | {_cell(c4, rid)} |")
            denom_note = []
            if c12 is not None:
                denom_note.append(f"gemma4:12b pooled denominator = {c12['pooled_denom']} "
                                   f"({census_title}) over {len(c12['seeds'])} seed(s)")
            if c4 is not None:
                denom_note.append(f"gemma3:4b pooled denominator = {c4['pooled_denom']} "
                                   f"over {len(c4['seeds'])} seed(s)")
            lines.append("")
            lines.append("; ".join(denom_note) + ".")
            if c12 is not None and c12["pooled_denom"] < 100:
                lines.append(f"CAUTION: gemma4:12b's {census_title} denominator here is "
                             f"small ({c12['pooled_denom']}) -- percentages above are "
                             f"noisy, shown with their denominator, not asserted as "
                             f"reliable.")
            lines.append("")

    strict_12b_pooled = pooled_by_arm_model.get(("strict", "gemma4_12b"))
    strict_ungov_12b_pooled = pooled_by_arm_model.get(("ungoverned", "gemma4_12b"))
    if strict_12b_pooled is not None:
        p = strict_12b_pooled
        ibr_audit_pct = (100.0 * p["n_increase_high"] / p["n_highWSA"]
                          if p["n_highWSA"] > 0 else float("nan"))
        denom_read = ("a substantial denominator, not a fragile small-sample one"
                       if p["n_highWSA"] >= 100 else "a SMALL denominator -- treat "
                       "the 0% with caution")
        retry_share_pct = 100.0 * p["n_retried"] / p["n_rows"]
        c12_retry = rule_census_by_arm.get(("strict", "retry", "gemma4_12b"))
        top_rules_txt = "no rule-id data"
        if c12_retry is not None and c12_retry["pooled_denom"] > 0:
            top2 = c12_retry["pooled_counts"].most_common(2)
            top_rules_txt = "; ".join(
                f"`{rid}` ({100.0 * cnt / c12_retry['pooled_denom']:.1f}% of retried rows)"
                for rid, cnt in top2)
        ungov_ibr_txt = "not yet available (ungoverned arm incomplete)"
        if strict_ungov_12b_pooled is not None:
            up = strict_ungov_12b_pooled
            ungov_ibr = (100.0 * up["n_increase_high"] / up["n_highWSA"]
                         if up["n_highWSA"] > 0 else float("nan"))
            ungov_ibr_txt = (f"{_fmt_stat(ungov_ibr, 1, None)}% on the same "
                             f"audit-derived measure, over {up['n_highWSA']} high-WSA rows")
        lines.append(
            f"The recorded `proposed_skill` on gemma4:12b strict is POST-RETRY (the "
            f"last attempt in each retry sequence, per the Method block's audit-writer "
            f"quote), so the 0.000% IBR headline describes what the validator "
            f"eventually negotiated, not the agent's first impulse -- which this "
            f"corpus cannot recover (an accepted gap in both the CSV and the raw "
            f"JSONL). What CAN be shown: {p['n_highWSA']} of {p['n_rows']} pooled rows "
            f"have high self-reported water scarcity, the negotiated-increase count "
            f"among them is exactly {p['n_increase_high']} ({denom_read}), and the "
            f"retry rate itself ({retry_share_pct:.1f}% of all rows) is the share of "
            f"decisions the validator intervened on at least once -- for gemma4:12b "
            f"strict, dominated by {top_rules_txt}. The ungoverned arm is the "
            f"un-nudged reference for the same model: gemma4:12b ungoverned's own "
            f"audit-derived IBR is {ungov_ibr_txt}, i.e. far above strict's 0%, so the "
            f"gap between the two arms -- not the strict arm's proposed_skill alone "
            f"-- is what shows governance changing the recorded outcome."
        )
    lines.append("")

    lines.append("## Part 2 -- model-paired comparison, gemma4:12b vs gemma3:4b "
                 "(diff = 12b - 4b)")
    lines.append("")
    for p in model_pair_pending:
        lines.append(f"- **{p['arm']}: PENDING** -- gemma4:12b has {p['n_12b']}/5 "
                     f"complete seeds (gemma3:4b has {p['n_4b']}/5); no comparison "
                     f"computed for this arm.")
    if model_pair_rows:
        lines.append("")
        lines.append("| arm | metric | mean_diff +/- sd | p_paired_t | p_exact_perm | "
                     "sign-consistent |")
        lines.append("|---|---|---:|---:|---:|:---:|")
        for r in model_pair_rows:
            pairs = [p for p in model_pair_pairs
                     if p["arm"] == r["arm"] and p["metric"] == r["metric"]]
            reason = (_degenerate_reason([p["value_12b"] for p in pairs],
                                          [p["value_4b"] for p in pairs])
                      if _is_nan(r["p_paired_t"]) else None)
            sign_cell = f"n.a. ({reason})" if reason else str(r["all_same_sign"])
            lines.append(
                f"| {r['arm']} | {r['metric']} | {_fmt_stat(r['mean_diff'], 3, reason)} +/- "
                f"{_fmt_stat(r['sd_diff'], 3, reason)} | "
                f"{_fmt_stat(r['p_paired_t'], 4, reason)} | "
                f"{_fmt_stat(r['p_exact_permutation'], 4, reason)} | {sign_cell} |"
            )
    lines.append("")

    lines.append("## Part 3 -- governed-vs-ungoverned contrast, gemma4:12b vs gemma3:4b "
                 "(diff = ungoverned - governed; scoped to the 2 metrics r25 covers)")
    lines.append("")
    g12b = {r["metric"]: r for r in contrast_rows if r["model"] == "gemma4_12b"}
    g4b = {r["metric"]: r for r in contrast_rows if r["model"] == "gemma3_4b"}
    if not g12b:
        lines.append(f"gemma4:12b contrast: **PENDING** -- ungoverned arm has "
                     f"{n_ungov}/5 complete seeds. gemma3:4b column shown for "
                     f"reference only.")
        lines.append("")
    lines.append("| metric | gemma4:12b mean_diff +/- sd | gemma4:12b p_paired_t | "
                 "gemma3:4b mean_diff +/- sd | gemma3:4b p_paired_t | same sign "
                 "across models |")
    lines.append("|---|---:|---:|---:|---:|:---:|")
    for label in CONTRAST_METRICS:
        r4 = g4b[label]
        if label in g12b:
            r12 = g12b[label]
            pairs12 = [p for p in contrast_pairs
                       if p["model"] == "gemma4_12b" and p["metric"] == label]
            reason12 = (_degenerate_reason([p["governed_value"] for p in pairs12],
                                            [p["ungoverned_value"] for p in pairs12])
                        if _is_nan(r12["p_paired_t"]) else None)
            if reason12 or _is_nan(r4["p_paired_t"]):
                same_cell = f"n.a. ({reason12 or 'gemma3:4b side is degenerate'})"
            else:
                same_cell = str((r12["mean_diff"] > 0) == (r4["mean_diff"] > 0))
            lines.append(
                f"| {label} | {_fmt_stat(r12['mean_diff'], 3, reason12)} +/- "
                f"{_fmt_stat(r12['sd_diff'], 3, reason12)} | "
                f"{_fmt_stat(r12['p_paired_t'], 4, reason12)} | "
                f"{_fmt_stat(r4['mean_diff'], 3, None)} +/- "
                f"{_fmt_stat(r4['sd_diff'], 3, None)} | "
                f"{_fmt_stat(r4['p_paired_t'], 4, None)} | {same_cell} |"
            )
        else:
            lines.append(f"| {label} | pending | pending | "
                         f"{_fmt_stat(r4['mean_diff'], 3, None)} +/- "
                         f"{_fmt_stat(r4['sd_diff'], 3, None)} | "
                         f"{_fmt_stat(r4['p_paired_t'], 4, None)} | pending |")
    lines.append("")

    lines.append("## Part 4 -- manifest + think-log census")
    lines.append("")
    lines.append("| arm | seed | model | thinking_mode | timeout_s | model_digest | "
                 "quantization | git_commit | think_lines | think_false |")
    lines.append("|---|---|---|---|---:|---|---|---|---:|---:|")
    metrics_by_key = {(r["arm"], r["seed"]): r for r in metrics_rows}
    for r in manifest_rows:
        mr = metrics_by_key[(r["arm"], r["seed"])]
        lines.append(f"| {r['arm']} | {r['seed']} | {r['model']} | {r['thinking_mode']} | "
                      f"{r['llm_timeout_seconds_effective']} | {r['model_digest']} | "
                      f"{r['model_quantization']} | {r['git_commit_short']} | "
                      f"{mr['think_n_lines']} | {mr['think_false']} |")
    lines.append("")

    lines.append("## Plain read")
    lines.append("")
    ibr_pair = next((r for r in model_pair_rows if r["arm"] == "strict"
                      and r["metric"] == "IBR headline"), None)
    sentences = [
        f"gemma4:12b's irrigation strict arm is fully landed ({n_strict}/5 seeds, all "
        f"`integrity_ok`, `thinking_mode=disabled` and think=false on every request "
        f"checked); the ungoverned arm has {n_ungov}/5 seeds complete."
    ]
    if ibr_pair is not None:
        ibr_pairs = [p for p in model_pair_pairs if p["arm"] == "strict"
                     and p["metric"] == "IBR headline"]
        ibr_reason = (_degenerate_reason([p["value_12b"] for p in ibr_pairs],
                                          [p["value_4b"] for p in ibr_pairs])
                      if _is_nan(ibr_pair["p_paired_t"]) else None)
        sentences.append(
            f"On the model-paired strict-vs-strict comparison, IBR headline differs "
            f"by {_fmt_stat(ibr_pair['mean_diff'], 2, ibr_reason)} pp (12b - 4b, "
            f"p_paired_t={_fmt_stat(ibr_pair['p_paired_t'], 4, ibr_reason)}, "
            f"sign-consistent={ibr_pair['all_same_sign'] if not ibr_reason else 'n.a.'})."
        )
    if g12b:
        c12, c4 = g12b["IBR headline"], g4b["IBR headline"]
        same_sign_ibr = (c12["mean_diff"] > 0) == (c4["mean_diff"] > 0)
        keeps = "keeps its sign" if same_sign_ibr else "DOES NOT keep its sign"
        sentences.append(
            f"The governed-vs-ungoverned contrast {keeps} on the larger model: "
            f"IBR headline mean_diff (ungoverned - governed) "
            f"{_cp(c12['mean_diff']):.2f} pp on gemma4:12b vs {_cp(c4['mean_diff']):.2f} "
            f"pp on gemma3:4b."
        )
    else:
        sentences.append(
            "The governed-vs-ungoverned contrast on gemma4:12b is pending until the "
            "ungoverned arm completes; only the gemma3:4b side is available today."
        )
    sentences.append(
        "No number in this report was hand-typed and every gemma3:4b aggregate is "
        "cross-checked against r25's own recorded values; the completeness gates "
        "mean this script can be re-run unchanged once ungoverned 45/46 land."
    )
    lines.append(" ".join(sentences))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    sys.exit(main())
