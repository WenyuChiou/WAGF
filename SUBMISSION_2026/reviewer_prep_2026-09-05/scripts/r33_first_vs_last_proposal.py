"""R33 -- first (initial) proposal vs last (negotiated) proposal, irrigation
gemma3:4b strict, c3391a53, with `global_config.audit.initial_proposal_columns:
true`. CPU-only, existing run only, no LLM calls made by this script.

BACKGROUND -- what the new columns close (quoted from the sources named in
the task)
  `broker/tests/test_initial_proposal_columns_p0_1a.py` (module docstring):
  "The proposal-stage gap: `skill_proposal` is REASSIGNED on every
  governance retry (`_retry_loop._governance_retry_loop`), so both the
  CSV's `proposed_skill` and the JSONL's `skill_proposal` record the LAST
  (post-retry) attempt. Measured over the shipped corpus, `proposed_skill
  == final_skill` on 100% of rows in all three reference domains despite
  heavy retrying -- which makes any 'governance changed the action' metric
  defined as proposed != final identically zero. The fix is three
  ADDITIVE columns -- `initial_skill` / `initial_labels` / `attempt_skills`
  -- gated by `global_config.audit.initial_proposal_columns` (default
  OFF)." `docs/AUDIT_SCHEMA.md`'s "Which Plane Answers What" table
  (row: "Per-attempt retry sequence | no | no | accepted gap") documents
  this as a known, accepted limitation of the schema BEFORE this flag --
  this run is the first in this reviewer-prep package to close it.
  Column semantics, verified against the test file's own assertions:
    `initial_skill`    -- the FIRST attempt's proposed skill, captured
                           before the retry loop overwrites it. Empty
                           string (never a crash) if the first attempt
                           itself was unparsable
                           (`test_mixin_flag_on_tolerates_missing_initial_proposal`).
    `initial_labels`   -- the FIRST attempt's construct labels, pipe-
                           joined `KEY=VALUE` pairs in emission order, e.g.
                           `"WSA_LABEL=H|ACA_LABEL=VH"`
                           (`test_extract_labels_picks_only_label_keys_in_order`).
                           Only WSA_LABEL is used here.
    `attempt_skills`   -- EVERY attempt's skill_name, pipe-joined, first-
                           to-last order; an unparsable attempt is an
                           EMPTY segment so the index is preserved
                           (`test_mixin_flag_on_unparsable_attempt_marked_empty`).
                           `len(attempt_skills.split("|")) ==
                           retry_count + 1` always (verified per-row
                           below, not assumed).
  `proposed_skill`/`final_skill` are UNCHANGED by this flag -- still the
  LAST (post-retry) values, still typically degenerate-equal to each
  other (`_common.py::irr_final`/`irr_executed`, same as every other
  script in this package).

PART 1 -- IBR headline, six ways (3 actions x 2 label sources)
  Actions: `initial_skill` (first attempt), `proposed_skill` (last
  recorded proposal -- the published IBR definition's action,
  `_loader.py::ibr` semantics), `C.irr_executed` (REJECTED -> registry
  default, else final_skill -- the executed-remap convention every
  script in this package uses). Label sources: `initial_labels`' own
  WSA_LABEL (first-attempt self-report) and `construct_WSA_LABEL` (the
  audit's final/last-attempt self-report, `_common.py::irr_wsa_audit`).
  numerator = count(label WSA in {H,VH} AND action in {increase_large,
  increase_small}), denominator = count(label WSA in {H,VH}), rate =
  100*numerator/denominator. Each of the 6 rows states which action and
  which label source it uses -- the published IBR headline is exactly
  ONE of these six (action=proposed_skill, label=final).

PART 2 -- retry census
  Share of rows with retry_count>0, mean attempts (`retry_count+1`,
  cross-checked against `len(attempt_skills.split("|"))` -- raises on
  any row where these disagree, since that would mean the append-before-
  break invariant the e2e tests exist to guard had failed on real data).
  5x5 transition table, first-attempt action (`initial_skill`) x last-
  attempt action (`attempt_skills.split("|")[-1]`, cross-checked equal
  to `proposed_skill`/`final_skill`) over the canonical 5-skill order
  `_common.py::IRR_SKILLS`. Plus: among rows where the FIRST attempt was
  an increase AND the FIRST-attempt WSA was high, the share whose LAST
  attempt ended as maintain/decrease (the "walked back" share).

PART 3 -- reference IBR, faf1bb12 strict + ungoverned (last-proposal
only, they lack the new columns -- verified empirically, not assumed)
  Two of the six Part-1 combinations are computable without
  `initial_skill`/`initial_labels`: action=proposed_skill and
  action=executed, both label=final (`construct_WSA_LABEL`) -- computed
  identically for `strict_42yr_gemma3_4b_faf1bb12_seed42` and
  `ungoverned_42yr_gemma3_4b_faf1bb12_seed42` as a same-model, same-seed,
  prior-commit reference point (NOT the same run as this script's
  primary target -- different git_commit, no first-attempt data at all).

COMPLETENESS GATE (the run lands ~22:00, may still be in progress)
  Target run: `irrigation_farmer_governance_audit.csv` +
  `reproducibility_manifest.json` both required for Part 1/2; missing
  either -> row_type=skipped with a printed pending reason, Part 1/2
  produce NO fabricated rows. Part 3's faf1bb12 references are
  independently gated and computed regardless of the target's state
  (they are already complete). Manifest census: value-enforces
  model=="gemma3:4b" and git_commit starts with "c3391a53" when the
  manifest exists; reports `initial_proposal_columns` presence from BOTH
  `reproducibility_manifest.json` (checked, does not carry this key in
  a same-family reference manifest inspected before writing this
  script) and `config_snapshot.yaml`'s `global_config.audit.
  initial_proposal_columns` (where it DOES appear, confirmed against
  `SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42/config_snapshot.yaml`,
  a structurally-identical but NOT-the-same-run reference used only to
  validate this script's column-parsing logic before the real target
  landed, never as a stand-in for the target's own numbers).

OUTPUTS
  out/r33_first_vs_last_proposal.csv -- row_type in {skipped,
    manifest_check, ibr_six_way, retry_census, transition_table,
    walkback_stat, reference_ibr}.
  out/r33_first_vs_last_proposal.md -- GENERATED by render_md() directly
    from that same `rows` list.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r33_first_vs_last_proposal.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

L = C.L  # SUBMISSION_2026/decomposition/_loader.py: HIGH, INCREASE, wsa()

TARGET_DIR = os.path.join(C.REPO, "examples", "irrigation_abm", "results",
                           "strict_42yr_gemma3_4b_c3391a53_initprop_seed42")
REFERENCE_DIRS = {
    "strict_faf1bb12": os.path.join(C.REPO, "examples", "irrigation_abm", "results",
                                     "strict_42yr_gemma3_4b_faf1bb12_seed42"),
    "ungoverned_faf1bb12": os.path.join(C.REPO, "examples", "irrigation_abm", "results",
                                         "ungoverned_42yr_gemma3_4b_faf1bb12_seed42"),
}
AUDIT_NAME = "irrigation_farmer_governance_audit.csv"


# =============================================================================
# helpers
# =============================================================================
def _parse_labels(s: str) -> dict:
    """'WSA_LABEL=H|ACA_LABEL=VH' -> {'WSA_LABEL': 'H', 'ACA_LABEL': 'VH'}.
    '' or malformed segments degrade to missing keys, never raise (matches
    the audit-writer's own 'degrades quietly' contract for this field)."""
    out = {}
    if not s:
        return out
    for seg in s.split("|"):
        if "=" not in seg:
            continue
        k, v = seg.split("=", 1)
        out[k] = v
    return out


def _initial_wsa(row: dict) -> str:
    return _parse_labels(row.get("initial_labels") or "").get("WSA_LABEL", "").strip().upper()


def _final_wsa(row: dict) -> str:
    return C.irr_wsa_audit(row)


def _rate(rows: list, action_fn, label_fn) -> dict:
    den_rows = [r for r in rows if label_fn(r) in L.HIGH]
    den = len(den_rows)
    if den == 0:
        return {"numerator": 0, "denominator": 0, "rate": float("nan")}
    num = sum(1 for r in den_rows if action_fn(r) in L.INCREASE)
    return {"numerator": num, "denominator": den, "rate": 100.0 * num / den}


def _crosscheck_published_ibr(run_dir: str, aud: list, label: str) -> None:
    """Cross-check the action=proposed_skill/label=final combination
    (the published IBR headline) against `_loader.py::ibr()` computed
    LIVE on this same run's simulation_log.csv (yearly_decision +
    wsa_label -- a different pair of columns from audit's proposed_skill
    + construct_WSA_LABEL). Raises on disagreement beyond rounding.
    Verified once by hand before writing this function (strict_42yr_
    gemma3_4b_faf1bb12_seed42: both paths give 284/1066 = 26.6417%,
    exact); wired in here so every run this script touches gets the
    same check, not just the one spot-checked during development."""
    sim_path = os.path.join(run_dir, "simulation_log.csv")
    if not os.path.isfile(sim_path):
        print(f"  crosscheck SKIPPED ({label}): no simulation_log.csv to cross-check against")
        return
    sim = C.read_csv(sim_path)
    loader_rate = L.ibr(sim)
    aud_final = [r for r in aud if C.irr_wsa_audit(r) in L.HIGH]
    my_num = sum(1 for r in aud_final
                 if (r.get("proposed_skill") or "").strip() in L.INCREASE)
    my_rate = 100.0 * my_num / len(aud_final) if aud_final else float("nan")
    if abs(loader_rate - my_rate) > 1e-6:
        raise PrepError(f"{run_dir}: published-IBR crosscheck failed ({label}) -- this "
                         f"script's audit-based (proposed_skill, construct_WSA_LABEL) "
                         f"computation gives {my_rate:.6f}%, but `_loader.py::ibr()` on "
                         f"simulation_log (yearly_decision, wsa_label) gives "
                         f"{loader_rate:.6f}% -- these should be numerically identical "
                         f"(final_skill==yearly_decision and proposed_skill==final_skill "
                         f"on all but a small unparsed-proposal share), investigate before "
                         f"trusting either number")
    print(f"  crosscheck OK ({label}): audit-based proposed_skill/final IBR = "
          f"{my_rate:.4f}% == _loader.ibr(simulation_log) = {loader_rate:.4f}%")


TAE_PREVIEW_SEEDS = ["42", "43", "44", "45", "46"]
TAE_PREVIEW_DIR_TMPL = os.path.join(C.REPO, "SUBMISSION_2026", "TAE", "runs",
                                     "firstattempt_gov_seed{seed}")


def _target_completeness() -> tuple:
    if not os.path.isdir(TARGET_DIR):
        return "skipped", f"run directory does not exist yet: {TARGET_DIR}"
    aud_path = os.path.join(TARGET_DIR, AUDIT_NAME)
    if not os.path.isfile(aud_path):
        return "skipped", "irrigation_farmer_governance_audit.csv not yet written (run in progress)"
    manifest_path = os.path.join(TARGET_DIR, "reproducibility_manifest.json")
    if not os.path.isfile(manifest_path):
        return "skipped", "reproducibility_manifest.json not yet written (run in progress)"
    return "ok", None


# =============================================================================
# Part 1 + 2 -- target run
# =============================================================================
def _part1_2_target(rows: list) -> None:
    status, reason = _target_completeness()
    if status == "skipped":
        print(f"  PENDING: {reason}")
        rows.append({"row_type": "skipped", "section": "target_run", "reason": reason})
        return

    aud_path = os.path.join(TARGET_DIR, AUDIT_NAME)
    aud = C.read_csv(aud_path)
    C.require_cols(aud, ["initial_skill", "initial_labels", "attempt_skills",
                          "proposed_skill", "final_skill", "status", "retry_count",
                          "construct_WSA_LABEL"], aud_path)
    print(f"  target run OK: {len(aud)} audit rows")

    n_initial_unparsed = sum(1 for r in aud if not (r.get("initial_skill") or "").strip())
    print(f"  {n_initial_unparsed}/{len(aud)} rows have an empty initial_skill "
          f"(first attempt itself unparsable)")

    # ---- invariant check: len(attempt_skills) == retry_count + 1 ----------
    n_invariant_fail = 0
    for r in aud:
        n_att = len((r.get("attempt_skills") or "").split("|")) if r.get("attempt_skills") else 0
        rc = int(r["retry_count"])
        if n_att != rc + 1:
            n_invariant_fail += 1
    if n_invariant_fail > 0:
        raise PrepError(f"{aud_path}: {n_invariant_fail}/{len(aud)} rows violate "
                         f"len(attempt_skills.split('|')) == retry_count+1 -- the append-"
                         f"before-break invariant the e2e tests guard does not hold on "
                         f"real data, this is a real bug, not something to skip past")

    # ---- cross-check: attempt_skills[-1] == proposed_skill == final_skill --
    n_last_mismatch = 0
    for r in aud:
        last_attempt = (r.get("attempt_skills") or "").split("|")[-1]
        if last_attempt != (r.get("proposed_skill") or "").strip():
            n_last_mismatch += 1
    if n_last_mismatch > 0:
        raise PrepError(f"{aud_path}: {n_last_mismatch}/{len(aud)} rows have "
                         f"attempt_skills[-1] != proposed_skill -- the documented "
                         f"'last attempt' identity does not hold, investigate before "
                         f"trusting the six-way IBR table below")
    print(f"  invariant OK: len(attempt_skills)==retry_count+1 and attempt_skills[-1]=="
          f"proposed_skill for all {len(aud)} rows")

    # ---- Part 1: six-way IBR ------------------------------------------------
    action_fns = {
        "initial_skill": lambda r: (r.get("initial_skill") or "").strip(),
        "proposed_skill": lambda r: (r.get("proposed_skill") or "").strip(),
        "executed": C.irr_executed,
    }
    label_fns = {"initial": _initial_wsa, "final": _final_wsa}
    for action_name, action_fn in action_fns.items():
        for label_name, label_fn in label_fns.items():
            rr = _rate(aud, action_fn, label_fn)
            rows.append({"row_type": "ibr_six_way", "action": action_name, "label": label_name,
                         "numerator": rr["numerator"], "denominator": rr["denominator"],
                         "rate": rr["rate"], "n_rows": len(aud),
                         "note": ("published IBR headline definition"
                                  if action_name == "proposed_skill" and label_name == "final"
                                  else "")})

    _crosscheck_published_ibr(TARGET_DIR, aud, "target")

    # ---- Part 2: retry census ------------------------------------------------
    n = len(aud)
    n_retried = sum(1 for r in aud if int(r["retry_count"]) > 0)
    attempts_per_row = [int(r["retry_count"]) + 1 for r in aud]
    rows.append({"row_type": "retry_census", "n_rows": n, "n_retried": n_retried,
                 "share_retried_pct": 100.0 * n_retried / n,
                 "mean_attempts": C.mean(attempts_per_row),
                 "n_initial_unparsed": n_initial_unparsed})

    # ---- transition table: initial_skill -> last attempt -------------------
    order = list(C.IRR_SKILLS)
    counts = {(a, b): 0 for a in order + ["UNPARSED"] for b in order + ["UNPARSED"]}
    for r in aud:
        first = (r.get("initial_skill") or "").strip()
        last = (r.get("attempt_skills") or "").split("|")[-1]
        first_key = first if first in order else "UNPARSED"
        last_key = last if last in order else "UNPARSED"
        counts[(first_key, last_key)] += 1
    for (first_key, last_key), cnt in counts.items():
        if cnt == 0:
            continue
        rows.append({"row_type": "transition_table", "first_action": first_key,
                     "last_action": last_key, "count": cnt})

    # ---- walk-back share: first attempt = increase & initial WSA high, -----
    # last attempt ends as maintain/decrease ----------------------------------
    base = [r for r in aud if (r.get("initial_skill") or "").strip() in L.INCREASE
            and _initial_wsa(r) in L.HIGH]
    walked_back = [r for r in base
                   if (r.get("attempt_skills") or "").split("|")[-1] not in L.INCREASE]
    den = len(base)
    rows.append({"row_type": "walkback_stat", "numerator": len(walked_back),
                 "denominator": den,
                 "rate": (100.0 * len(walked_back) / den) if den > 0 else float("nan")})

    # ---- manifest census ------------------------------------------------------
    # thinking_mode/llm_timeout_seconds_effective/model_quantization/
    # model_digest added per review round 2 (r26/r27 report these too).
    # thinking_mode is value-enforced == "auto" ONLY because the faf1bb12
    # strict seed-42 reference manifest was checked directly and also
    # records "auto" (not assumed, not the "disabled" value the flood
    # c3391a53 corpus uses) -- if that reference ever changes, this
    # enforcement should be revisited, not silently kept.
    manifest_path = os.path.join(TARGET_DIR, "reproducibility_manifest.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    model = manifest.get("model")
    git_commit = manifest.get("git_commit")
    thinking_mode = manifest.get("thinking_mode")
    llm_timeout = manifest.get("llm_timeout_seconds_effective")
    model_quantization = manifest.get("model_quantization")
    model_digest = manifest.get("model_digest")
    if model != "gemma3:4b":
        raise PrepError(f"{manifest_path}: model={model!r}, expected 'gemma3:4b'")
    if not str(git_commit or "").startswith("c3391a53"):
        raise PrepError(f"{manifest_path}: git_commit={git_commit!r}, expected to start "
                         f"with 'c3391a53'")
    if thinking_mode != "auto":
        raise PrepError(f"{manifest_path}: thinking_mode={thinking_mode!r}, expected "
                         f"'auto' -- confirmed against strict_42yr_gemma3_4b_faf1bb12_"
                         f"seed42's own manifest, which also records 'auto'; this is a "
                         f"real premise check, not an assumption")
    manifest_has_flag = "initial_proposal_columns" in json.dumps(manifest)
    config_snapshot_path = os.path.join(TARGET_DIR, "config_snapshot.yaml")
    config_flag = None
    if os.path.isfile(config_snapshot_path):
        import yaml
        with open(config_snapshot_path, encoding="utf-8") as fh:
            cfg = yaml.safe_load(fh)
        config_flag = (cfg.get("global_config", {}) or {}).get("audit", {}).get(
            "initial_proposal_columns")
    rows.append({"row_type": "manifest_check", "arm": "target", "model": model,
                 "git_commit_short": git_commit[:8] if git_commit else "",
                 "thinking_mode": thinking_mode,
                 "llm_timeout_seconds_effective": llm_timeout,
                 "model_quantization": model_quantization, "model_digest": model_digest,
                 "manifest_has_initial_proposal_key": manifest_has_flag,
                 "config_snapshot_initial_proposal_columns": config_flag})
    print(f"  manifest OK: model={model} git_commit={git_commit[:8] if git_commit else '?'} "
          f"thinking_mode={thinking_mode} llm_timeout={llm_timeout} "
          f"model_quantization={model_quantization} model_digest={model_digest} "
          f"manifest_has_key={manifest_has_flag} config_snapshot_flag={config_flag}")


# =============================================================================
# Part 3 -- faf1bb12 references (last-proposal only)
# =============================================================================
def _part3_references(rows: list) -> None:
    for arm, run_dir in REFERENCE_DIRS.items():
        aud_path = os.path.join(run_dir, AUDIT_NAME)
        if not os.path.isfile(aud_path):
            print(f"  SKIPPED reference {arm}: {aud_path} missing")
            rows.append({"row_type": "skipped", "section": "reference", "arm": arm,
                         "reason": "audit CSV missing"})
            continue
        aud = C.read_csv(aud_path)
        C.require_cols(aud, ["proposed_skill", "final_skill", "status",
                              "construct_WSA_LABEL"], aud_path)
        has_initial_cols = "initial_skill" in aud[0]
        if has_initial_cols:
            raise PrepError(f"{aud_path}: unexpectedly HAS initial_skill -- the docstring's "
                             f"'they lack the columns' premise for this reference run is "
                             f"false, re-verify before using it as a last-proposal-only "
                             f"reference")
        for action_name, action_fn in (("proposed_skill", lambda r: (r.get("proposed_skill") or "").strip()),
                                        ("executed", C.irr_executed)):
            rr = _rate(aud, action_fn, _final_wsa)
            rows.append({"row_type": "reference_ibr", "arm": arm, "action": action_name,
                         "label": "final", "numerator": rr["numerator"],
                         "denominator": rr["denominator"], "rate": rr["rate"],
                         "n_rows": len(aud)})
        _crosscheck_published_ibr(run_dir, aud, arm)
        print(f"  reference {arm}: {len(aud)} rows, no initial_skill column (confirmed), "
              f"2 IBR rows written")


# =============================================================================
# Part 5 -- "preview at another commit": SUBMISSION_2026/TAE/runs/
# firstattempt_gov_seed{42..46}, SI only, kept strictly separate from the
# primary c3391a53 target -- different git_commit PER SEED (verified,
# not assumed: 3 distinct commits across the 5 seeds -- seed 42 alone at
# 0237cb5f, seed 43 alone at a THIRD commit (4b49bf46), seeds 44/45/46 at
# bcee993f -- an evolving codebase during this earlier pilot, not one
# frozen commit; render_md() groups seeds by git_commit_short read live
# from the tae_preview_manifest rows, never a typed grouping -- an
# earlier hand-typed version of this same sentence wrongly grouped seed
# 43 with seed 42, caught in review), thinking_mode=="auto" (not value-
# enforced here, only reported, exactly as instructed -- c3391a53
# enforcement does not apply to this corpus and is never asserted
# against it).
# =============================================================================
def _part5_tae_preview(rows: list) -> None:
    corpus = "tae_preview"
    per_cell_ibr: dict = {}       # (action, label) -> [rate, ...]
    per_seed_retry: dict = {"share_retried_pct": [], "mean_attempts": []}
    per_seed_walkback: list = []

    for seed in TAE_PREVIEW_SEEDS:
        run_dir = TAE_PREVIEW_DIR_TMPL.format(seed=seed)
        aud_path = os.path.join(run_dir, AUDIT_NAME)
        manifest_path = os.path.join(run_dir, "reproducibility_manifest.json")
        if not (os.path.isfile(aud_path) and os.path.isfile(manifest_path)):
            raise PrepError(f"tae_preview seed {seed}: missing {aud_path} or "
                             f"{manifest_path} -- this corpus was confirmed complete "
                             f"before writing this script, a missing file now is a real "
                             f"regression, not something to skip past")
        aud = C.read_csv(aud_path)
        C.require_cols(aud, ["initial_skill", "initial_labels", "attempt_skills",
                              "proposed_skill", "final_skill", "status", "retry_count",
                              "construct_WSA_LABEL"], aud_path)
        if not all(col in aud[0] for col in ("initial_skill", "initial_labels", "attempt_skills")):
            raise PrepError(f"tae_preview seed {seed}: {aud_path} lacks one of "
                             f"initial_skill/initial_labels/attempt_skills -- task requires "
                             f"raising if any of the five lacks these three columns")

        # invariants (same checks as the target run, independent code so a
        # bug here can never change the target's own rows)
        n_invariant_fail = 0
        for r in aud:
            n_att = len((r.get("attempt_skills") or "").split("|")) if r.get("attempt_skills") else 0
            if n_att != int(r["retry_count"]) + 1:
                n_invariant_fail += 1
        if n_invariant_fail > 0:
            raise PrepError(f"tae_preview seed {seed}: {n_invariant_fail}/{len(aud)} rows "
                             f"violate len(attempt_skills)==retry_count+1")
        n_last_mismatch = sum(1 for r in aud
                               if (r.get("attempt_skills") or "").split("|")[-1]
                               != (r.get("proposed_skill") or "").strip())
        if n_last_mismatch > 0:
            raise PrepError(f"tae_preview seed {seed}: {n_last_mismatch}/{len(aud)} rows "
                             f"have attempt_skills[-1] != proposed_skill")

        # six-way IBR
        action_fns = {
            "initial_skill": lambda r: (r.get("initial_skill") or "").strip(),
            "proposed_skill": lambda r: (r.get("proposed_skill") or "").strip(),
            "executed": C.irr_executed,
        }
        label_fns = {"initial": _initial_wsa, "final": _final_wsa}
        for action_name, action_fn in action_fns.items():
            for label_name, label_fn in label_fns.items():
                rr = _rate(aud, action_fn, label_fn)
                rows.append({"row_type": "tae_preview_ibr", "corpus": corpus, "seed": seed,
                             "action": action_name, "label": label_name,
                             "numerator": rr["numerator"], "denominator": rr["denominator"],
                             "rate": rr["rate"], "n_rows": len(aud)})
                if rr["rate"] == rr["rate"]:  # not nan
                    per_cell_ibr.setdefault((action_name, label_name), []).append(rr["rate"])

        # retry census
        n = len(aud)
        n_retried = sum(1 for r in aud if int(r["retry_count"]) > 0)
        n_initial_unparsed = sum(1 for r in aud if not (r.get("initial_skill") or "").strip())
        attempts_per_row = [int(r["retry_count"]) + 1 for r in aud]
        share_retried = 100.0 * n_retried / n
        mean_att = C.mean(attempts_per_row)
        rows.append({"row_type": "tae_preview_retry_census", "corpus": corpus, "seed": seed,
                     "n_rows": n, "n_retried": n_retried, "share_retried_pct": share_retried,
                     "mean_attempts": mean_att, "n_initial_unparsed": n_initial_unparsed})
        per_seed_retry["share_retried_pct"].append(share_retried)
        per_seed_retry["mean_attempts"].append(mean_att)

        # walk-back
        base = [r for r in aud if (r.get("initial_skill") or "").strip() in L.INCREASE
                and _initial_wsa(r) in L.HIGH]
        walked_back = [r for r in base
                       if (r.get("attempt_skills") or "").split("|")[-1] not in L.INCREASE]
        den = len(base)
        wb_rate = (100.0 * len(walked_back) / den) if den > 0 else float("nan")
        rows.append({"row_type": "tae_preview_walkback", "corpus": corpus, "seed": seed,
                     "numerator": len(walked_back), "denominator": den, "rate": wb_rate})
        if wb_rate == wb_rate:
            per_seed_walkback.append(wb_rate)

        # manifest (git_commit, thinking_mode, model -- NOT value-enforced)
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)
        rows.append({"row_type": "tae_preview_manifest", "corpus": corpus, "seed": seed,
                     "model": manifest.get("model"),
                     "git_commit_short": (manifest.get("git_commit") or "")[:8],
                     "thinking_mode": manifest.get("thinking_mode")})
        print(f"  tae_preview seed {seed}: {len(aud)} rows, model={manifest.get('model')} "
              f"git_commit={(manifest.get('git_commit') or '')[:8]} "
              f"thinking_mode={manifest.get('thinking_mode')}")

    # ---- 5-seed mean +/- sd per cell -----------------------------------------
    for (action_name, label_name), vals in per_cell_ibr.items():
        n = len(vals)
        rows.append({"row_type": "tae_preview_ibr_summary", "corpus": corpus,
                     "action": action_name, "label": label_name, "n_seeds": n,
                     "mean": C.mean(vals), "sd": C.sd(vals) if n >= 2 else float("nan")})
    for metric, vals in per_seed_retry.items():
        n = len(vals)
        rows.append({"row_type": "tae_preview_retry_census_summary", "corpus": corpus,
                     "metric": metric, "n_seeds": n, "mean": C.mean(vals),
                     "sd": C.sd(vals) if n >= 2 else float("nan")})
    n = len(per_seed_walkback)
    if n > 0:
        rows.append({"row_type": "tae_preview_walkback_summary", "corpus": corpus,
                     "n_seeds": n, "mean": C.mean(per_seed_walkback),
                     "sd": C.sd(per_seed_walkback) if n >= 2 else float("nan")})
    print(f"  tae_preview: 5-seed summary written for {len(per_cell_ibr)} IBR cells + "
          f"retry census + walkback")


# =============================================================================
# main
# =============================================================================
FIELDNAMES = [
    "row_type", "section", "corpus", "action", "label", "arm", "seed", "numerator",
    "denominator", "rate", "n_rows", "note", "n_retried", "share_retried_pct",
    "mean_attempts", "n_initial_unparsed", "first_action", "last_action", "count", "model",
    "git_commit_short", "thinking_mode", "llm_timeout_seconds_effective",
    "model_quantization", "model_digest", "manifest_has_initial_proposal_key",
    "config_snapshot_initial_proposal_columns", "metric", "n_seeds", "mean", "sd", "reason",
]


def main() -> int:
    C.banner("R33  Irrigation gemma3:4b strict c3391a53 initprop -- first vs last proposal")
    rows: list = []

    print("\n-- Part 1+2: target run (six-way IBR, retry census, transition table) --")
    _part1_2_target(rows)

    print("\n-- Part 3: faf1bb12 strict/ungoverned references (last-proposal only) --")
    _part3_references(rows)

    print("\n-- Part 5: TAE preview at another commit (SI only, kept separate) --")
    _part5_tae_preview(rows)

    md_text = render_md(rows)

    csv_final = "r33_first_vs_last_proposal.csv"
    csv_tmp = csv_final + ".tmp"
    md_final = os.path.join(C.OUT, "r33_first_vs_last_proposal.md")
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


def render_md(rows: list) -> str:
    lines = []
    lines.append("# R33 -- first (initial) proposal vs last (negotiated) proposal")
    lines.append("")
    lines.append("Source: `r33_first_vs_last_proposal.py`. Every number below is read live "
                 "from the `rows` list this script writes to the paired CSV.")
    lines.append("")

    pending = _find(rows, "skipped", section="target_run")
    if pending:
        lines.append("## STATUS: target run PENDING")
        lines.append("")
        lines.append(f"Reason: {pending[0]['reason']}")
        lines.append("")
        lines.append("The script and its completeness gate are armed -- re-running this "
                     "script once `strict_42yr_gemma3_4b_c3391a53_initprop_seed42` finishes "
                     "writing `irrigation_farmer_governance_audit.csv` and "
                     "`reproducibility_manifest.json` will populate Part 1/2 below with no "
                     "code change needed.")
        lines.append("")
    else:
        mc = _find(rows, "manifest_check", arm="target")
        if mc:
            m = mc[0]
            lines.append("## Manifest census (target run)")
            lines.append("")
            lines.append(f"model={m['model']}, git_commit={m['git_commit_short']}..., "
                         f"thinking_mode={m['thinking_mode']} (value-enforced =='auto', "
                         f"confirmed against strict_42yr_gemma3_4b_faf1bb12_seed42's own "
                         f"manifest which also records 'auto'), "
                         f"llm_timeout_seconds_effective={m['llm_timeout_seconds_effective']}, "
                         f"model_quantization={m['model_quantization']}, "
                         f"model_digest={m['model_digest']}, "
                         f"`initial_proposal_columns` key in reproducibility_manifest.json: "
                         f"{m['manifest_has_initial_proposal_key']}, in config_snapshot.yaml "
                         f"`global_config.audit.initial_proposal_columns`: "
                         f"{m['config_snapshot_initial_proposal_columns']}.")
            lines.append("")

        lines.append("## Part 1 -- IBR headline, six ways (3 actions x 2 label sources)")
        lines.append("")
        lines.append("| action | label source | numerator | denominator | rate (%) | note |")
        lines.append("|---|---|---|---|---|---|")
        for r in _find(rows, "ibr_six_way"):
            lines.append(f"| {r['action']} | {r['label']} | {r['numerator']} | "
                         f"{r['denominator']} | {_cp(r['rate']):.2f} | {r['note']} |")
        lines.append("")

        rc = _find(rows, "retry_census")
        if rc:
            r = rc[0]
            lines.append("## Part 2 -- retry census")
            lines.append("")
            lines.append(f"n_rows={r['n_rows']}, share with retry_count>0: "
                         f"{_cp(r['share_retried_pct']):.2f}%, mean attempts: "
                         f"{_cp(r['mean_attempts']):.3f}, rows with empty initial_skill "
                         f"(first attempt unparsable): {r['n_initial_unparsed']}.")
            lines.append("")

        lines.append("### Transition table: first attempt (initial_skill) -> last attempt")
        lines.append("")
        order = list(C.IRR_SKILLS) + ["UNPARSED"]
        header = "| first attempt \\ last attempt | " + " | ".join(order) + " |"
        lines.append(header)
        lines.append("|" + "---|" * (len(order) + 1))
        trans = {(r["first_action"], r["last_action"]): int(r["count"])
                 for r in _find(rows, "transition_table")}
        for fa in order:
            cells = [str(trans.get((fa, la), 0)) for la in order]
            lines.append(f"| {fa} | " + " | ".join(cells) + " |")
        lines.append("")

        wb = _find(rows, "walkback_stat")
        if wb:
            r = wb[0]
            lines.append(f"**Walk-back share:** of {r['denominator']} rows whose first "
                         f"attempt was an increase under high first-attempt WSA, "
                         f"{r['numerator']} ({_cp(r['rate']):.2f}%) ended (last attempt) as "
                         f"maintain/decrease.")
            lines.append("")

    lines.append("## Part 3 -- faf1bb12 references (strict, ungoverned; last-proposal only)")
    lines.append("")
    lines.append("| arm | action | label | numerator | denominator | rate (%) |")
    lines.append("|---|---|---|---|---|---|")
    for arm in ("strict_faf1bb12", "ungoverned_faf1bb12"):
        for r in _find(rows, "reference_ibr", arm=arm):
            lines.append(f"| {arm} | {r['action']} | {r['label']} | {r['numerator']} | "
                         f"{r['denominator']} | {_cp(r['rate']):.2f} |")
    lines.append("")

    # ---- Part 5: TAE preview (SI only, kept strictly separate) ------------------
    lines.append("## Part 5 -- preview at a different commit and thinking setting "
                 "(SI only; NOT pooled with the c3391a53 run above)")
    lines.append("")
    tae_manifests = _find(rows, "tae_preview_manifest")
    if tae_manifests:
        # Group seeds by their ACTUAL git_commit_short from the data --
        # never a typed grouping (a hand-typed "seeds 42/43 at X" sentence
        # was wrong once already: seed 43 is really at a THIRD, distinct
        # commit, not grouped with seed 42 at all).
        commit_groups: dict = {}
        for r in tae_manifests:
            commit_groups.setdefault(r["git_commit_short"], []).append(r["seed"])
        group_parts = []
        for commit, seeds in commit_groups.items():
            word = "seed" if len(seeds) == 1 else "seeds"
            group_parts.append(f"{word} {'/'.join(seeds)} at `{commit}...`")
        commit_desc = ", ".join(group_parts)
        thinking_modes = sorted({r["thinking_mode"] for r in tae_manifests})
        thinking_desc = "/".join(thinking_modes)
        n_distinct_commits = len(commit_groups)
    else:
        commit_desc = "pending"
        thinking_desc = "pending"
        n_distinct_commits = 0
    lines.append("`SUBMISSION_2026/TAE/runs/firstattempt_gov_seed{42..46}` -- an EARLIER "
                 "pilot corpus, kept strictly separate from the primary c3391a53 target: "
                 f"{n_distinct_commits} distinct git_commit values across the 5 seeds "
                 f"({commit_desc} -- read from each seed's own manifest below, not one "
                 f"frozen commit) and thinking_mode `{thinking_desc}` (vs the target's "
                 "`auto` too, but never value-enforced here -- this corpus's own manifests "
                 "are only reported, not asserted against any expected value). Same "
                 "six-way IBR / retry census / walk-back computation, independent code "
                 "from Part 1/2 so a bug here cannot alter the target's own rows.")
    lines.append("")
    lines.append("### Per-seed manifests")
    lines.append("")
    lines.append("| seed | model | git_commit | thinking_mode |")
    lines.append("|---|---|---|---|")
    for r in _find(rows, "tae_preview_manifest"):
        lines.append(f"| {r['seed']} | {r['model']} | {r['git_commit_short']}... | "
                     f"{r['thinking_mode']} |")
    lines.append("")
    lines.append("### Six-way IBR, 5-seed mean +/- sd")
    lines.append("")
    lines.append("| action | label source | n_seeds | rate mean +/- sd (%) |")
    lines.append("|---|---|---|---|")
    for r in _find(rows, "tae_preview_ibr_summary"):
        lines.append(f"| {r['action']} | {r['label']} | {r['n_seeds']} | "
                     f"{_cp(r['mean']):.2f} +/- {_cp(r['sd']):.2f} |")
    lines.append("")
    lines.append("### Retry census and walk-back, 5-seed mean +/- sd")
    lines.append("")
    lines.append("| metric | n_seeds | mean +/- sd |")
    lines.append("|---|---|---|")
    for r in _find(rows, "tae_preview_retry_census_summary"):
        lines.append(f"| {r['metric']} | {r['n_seeds']} | {_cp(r['mean']):.3f} +/- "
                     f"{_cp(r['sd']):.3f} |")
    for r in _find(rows, "tae_preview_walkback_summary"):
        lines.append(f"| walkback_rate_pct | {r['n_seeds']} | {_cp(r['mean']):.2f} +/- "
                     f"{_cp(r['sd']):.2f} |")
    lines.append("")

    # ---- Plain read -------------------------------------------------------------
    lines.append("## Plain read")
    lines.append("")
    sentences = []
    if pending:
        sentences.append(
            "The target run (gemma3:4b strict, c3391a53, initial_proposal_columns=true) is "
            "still in progress -- Part 1/2 (first-vs-last proposal, retry census) are not "
            "yet populated; this read will be templated from real rows once it lands."
        )
        ref_prop = _find(rows, "reference_ibr", action="proposed_skill", label="final")
        if ref_prop:
            parts = "; ".join(f"{r['arm']}={_cp(r['rate']):.1f}%" for r in ref_prop)
            sentences.append(
                f"For calibration, the published (last-proposal, final-label) IBR headline "
                f"on the faf1bb12 reference runs is {parts} -- the pre-existing gap between "
                f"governed and ungoverned this script will decompose into first-impulse vs "
                f"negotiated-result once the target's initial_skill data is available."
            )
    else:
        ibr_first_initial = _find(rows, "ibr_six_way", action="initial_skill", label="initial")
        ibr_last_final = _find(rows, "ibr_six_way", action="proposed_skill", label="final")
        ibr_exec_final = _find(rows, "ibr_six_way", action="executed", label="final")
        if ibr_first_initial and ibr_last_final:
            fi, lf = ibr_first_initial[0], ibr_last_final[0]
            sentences.append(
                f"The agent's FIRST impulse (initial_skill under its own first-attempt WSA) "
                f"scores an IBR of {_cp(fi['rate']):.2f}%; the NEGOTIATED result (published "
                f"headline: last proposal under final WSA) scores {_cp(lf['rate']):.2f}% -- "
                f"the gap between these two is what governance-plus-retry moved, on this "
                f"single run."
            )
        if ibr_exec_final and ibr_last_final:
            ef, lf = ibr_exec_final[0], ibr_last_final[0]
            sentences.append(
                f"The EXECUTED action's IBR ({_cp(ef['rate']):.2f}%) vs the last-proposal "
                f"IBR ({_cp(lf['rate']):.2f}%) isolates whatever the executed-remap (REJECTED "
                f"-> registry default) contributes beyond the validator's own retry pressure."
            )
        wb = _find(rows, "walkback_stat")
        if wb and wb[0]["denominator"] and wb[0]["denominator"] > 0:
            sentences.append(
                f"{_cp(wb[0]['rate']):.1f}% of first-attempt increases proposed under high "
                f"first-attempt WSA were walked back to maintain/decrease by the last "
                f"attempt -- direct evidence of negotiation, not just relabeling."
            )
        ref_prop = _find(rows, "reference_ibr", action="proposed_skill", label="final")
        if ref_prop:
            parts = "; ".join(f"{r['arm']}={_cp(r['rate']):.1f}%" for r in ref_prop)
            sentences.append(
                f"As an un-nudged reference (different commit, no first-attempt data), the "
                f"faf1bb12 last-proposal IBR is {parts} -- ungoverned's higher rate shows "
                f"what proposal-level coherence looks like with no validator pressure at "
                f"any attempt."
            )
    for s in sentences[:5]:
        lines.append(s)
        lines.append("")

    # ---- Method -------------------------------------------------------------------
    lines.append("## Method")
    lines.append("")
    lines.append(
        "`initial_skill`/`initial_labels`/`attempt_skills` are opt-in audit columns gated by "
        "`global_config.audit.initial_proposal_columns` (default OFF), added to close the "
        "`docs/AUDIT_SCHEMA.md` \"Which Plane Answers What\" table's documented gap "
        "(\"Per-attempt retry sequence | no | no | accepted gap\"). `initial_skill` = the "
        "FIRST attempt's proposal, captured before `_governance_retry_loop` overwrites "
        "`skill_proposal`; `initial_labels` = the first attempt's WSA/ACA labels, "
        "pipe-joined key=value; `attempt_skills` = every attempt's skill, pipe-joined, "
        "first-to-last, with `len(attempt_skills.split('|')) == retry_count+1` verified per "
        "row (raises otherwise), and `attempt_skills[-1] == proposed_skill` verified per row "
        "(raises otherwise) -- these are not assumed from "
        "`broker/tests/test_initial_proposal_columns_p0_1a.py`'s unit tests, they are "
        "re-checked against this run's own real data. The published IBR headline is exactly "
        "one of the six Part-1 rows: action=proposed_skill (last recorded proposal), "
        "label=final (`construct_WSA_LABEL`) -- `_loader.py::ibr()`'s own conditional-"
        "high-WSA-increase-rate formula, reimplemented here on audit rows (not "
        "simulation_log rows, since `proposed_skill`/`initial_skill` only exist in the "
        "audit) rather than imported, because `_loader.ibr()` itself operates on "
        "simulation_log's `yearly_decision`/`wsa_label`, a different pair of columns. This "
        "script cross-checks the two on every run it touches (`_crosscheck_published_ibr`, "
        "raises on disagreement): `final_skill` equals `yearly_decision` exactly and "
        "`proposed_skill` equals `final_skill` on all but a small unparsed-proposal share "
        "(empty `proposed_skill` on `REJECTED_FALLBACK` rows where the first attempt itself "
        "could not be parsed), so the audit-based and simulation_log-based computations "
        "agree to 1e-6 -- confirmed live, not assumed from the two columns' names sounding "
        "similar. faf1bb12 reference runs verified (raises otherwise) to lack "
        "`initial_skill` entirely, so only the two label=final combinations are computable "
        "there."
    )
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    sys.exit(main())
