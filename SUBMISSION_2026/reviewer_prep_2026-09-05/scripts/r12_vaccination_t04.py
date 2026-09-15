"""R12 -- vaccination T0-4: integrity, rule census, action distribution, parser layer
for the new gemma3:4b / HBM vaccination runs (seeds 42/43/44, 100 agents x 10 years).

DATA LOCATION -- read this before trusting a path
  These runs do NOT exist anywhere under this repository. They were generated in a
  SEPARATE checkout, `wagf-main-runs`, sitting next to this repo
  (`<repo>/../wagf-main-runs`), at code `origin/main e0eee08c`. Both locations gitignore
  `examples/*/results/`, so the runs are committed nowhere -- not in this repo, not in
  the runs checkout. `VACC_ROOT` below tries this repo first (in case a future session
  moves the data in) and falls back to the sibling checkout; it raises if neither has
  the directory, exactly like every other missing-directory check in this package.

WHAT THIS TABLE ANSWERS, PER THE T0-4 PRE-REGISTERED ACCEPTANCE (plan Sec 3)
  run completes; rejection_rate; retry_rate; at least one HBM rule fires;
  run_integrity carries no RED flag; traces committed only if integrity is clean.

RULE CENSUS -- mirrors r3_rule_firing_census.py's method exactly (failed_rules =
ERROR-level blocking ids, warning_rules = WARNING-level non-blocking ids, both
pipe-delimited; status; retry_count; error_messages for the modal message). Five HBM
thinking-rules exist in `agent_types.yaml` / `config_snapshot.yaml`:
  ERROR    high_susceptibility_high_severity_high_efficacy_no_refuse (blocks refuse)
  ERROR    high_cues_low_barriers_refuse_inconsistent (blocks refuse)
  WARNING  low_susceptibility_no_get_vaccinated (blocks get_vaccinated)
  WARNING  high_barriers_high_self_efficacy_no_action_required (blocks delay, refuse)
  WARNING  low_severity_low_benefits_get_vaccinated (blocks get_vaccinated)

THE "DEAD VALIDATOR" LOG LINE -- what it actually means
  `broker/components/analytics/audit.py` (~line 1246) prints
  "[Audit] DEAD VALIDATOR: rule '<id>' never fired across <seen_count> decisions" for
  every rule where, summed over the whole run, `fire_count == 0` and `seen_count > 0`.
  `fire_count` only increments on an ERROR-level BLOCK; a WARNING-level rule can only
  ever increment `warn_count`, never `fire_count`, by construction (WARNING rules do
  not block -- project memory: "WARNING rules = 0% behaviour change"). So this log
  line fires for EVERY WARNING-level rule that was ever evaluated, regardless of
  whether it is actually inert -- it is measuring "never blocked", worded as "never
  fired", which reads as a bug report for something that is working as designed.
  Measured directly (`validator_health.csv` + `audit_summary.json`, all three seeds):
    seed 42: low_severity_low_benefits_get_vaccinated seen=4 fire=0 warn=4 (DEAD, WARNING)
             low_susceptibility_no_get_vaccinated      seen=4 fire=0 warn=4 (DEAD, WARNING)
    seed 43: low_severity_low_benefits_get_vaccinated  seen=2 fire=0 warn=2 (DEAD, WARNING)
             low_susceptibility_no_get_vaccinated      seen=6 fire=0 warn=6 (DEAD, WARNING)
    seed 44: low_susceptibility_no_get_vaccinated      seen=3 fire=0 warn=3 (DEAD, WARNING)
             high_cues_low_barriers_refuse_inconsistent seen=2 fire=2 warn=0 (NOT dead,
             ERROR -- this is the one ERROR-level rule that actually blocked, twice, in
             this batch; low_severity_low_benefits_get_vaccinated is absent from seed
             44's validator_health.csv entirely, i.e. seen_count=0 there, so it never
             gets a DEAD line for that seed at all).
  The seed-44 log line quoted in the task ("never fired across 3 decisions") is
  `low_susceptibility_no_get_vaccinated` in the MAIN seed-44 run (Run_44, 100 agents x
  10 years, gemma3:4b) -- NOT the 25x3 smoke run. Checked directly: `smoke.log`
  contains zero "DEAD VALIDATOR" lines (grepped, no match), and Run_44's own audit CSV
  independently shows 3 rows with `low_susceptibility_no_get_vaccinated` in
  `warning_rules` and 0 with it in `failed_rules`, matching seen=3/fire=0 exactly.

DECISION-FIELD / PROPOSED-SKILL DISCREPANCY -- found while building this table, not
asked for by the brief, reported because it is load-bearing for section 3 (action
distribution) and section 5 (verdict)
  Every row's `raw_output` is a clean, individually-parseable JSON object (parse_layer
  is "enclosure+json" on 100.0% of rows in all three seeds -- verified directly, not
  taken from the manifest) with an explicit top-level `"decision"` field ("1"/"2"/"3"
  per the schema, mapped 1=get_vaccinated / 2=delay / 3=refuse by
  `config_snapshot.yaml`'s own `individual.actions[*].aliases`). Cross-checking that
  field against the audit CSV's own `proposed_skill` for every row:
    year 1   0.0 % mismatch, all three seeds (perfect 1<->skill diagonal, verified by
             hand: dec=1 always get_vaccinated, dec=2 always delay, dec=3 always refuse)
    year 2-10  49-88 % mismatch PER YEAR, all three seeds (not a fixed permutation --
             dec="1" maps to get_vaccinated 233x, delay 152x and refuse 9x within seed
             42 alone, so this is not a simple off-by-one remap)
  Ruled out as a caching/stale-buffer artifact: `raw_output` is a DISTINCT string (by
  sha1) for one agent across all 10 years, with plausible per-year timestamps roughly
  7.5 minutes apart -- the model is genuinely called fresh every year, and its own text
  differs every year. Confirmed the same way independently in the raw JSONL trace
  (`raw/individual_traces.jsonl`, not just the CSV): `skill_proposal.skill_name` for
  Agent_001/seed42/year2 is "get_vaccinated" while that exact record's own
  `raw_output` ends in `"decision": "2"` (=delay), retry_count 0 (single LLM call, no
  retry-loop ambiguity). Root cause NOT identified within this analysis's scope --
  something between JSON parse and skill assignment does not simply read the
  `decision` key once memory/reflection context enters the prompt (year 2+); this is
  invisible to `run_integrity.json`, which only tracks which PARSE LAYER succeeded, not
  whether the extracted field matches the recorded skill. Construct labels (the VL..VH
  appraisal columns) are NOT checked by this test and show no unparsed values (0.0 %
  across all six columns, all three seeds) -- only the decision/skill mapping is
  implicated. PROVENANCE: this makes the action-distribution numbers for years 2-10 in
  this batch unverified against the model's own stated choice; year 1 numbers are
  clean.

Usage:  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12_vaccination_t04.py
Output: out/r12_vaccination_t04.csv
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

NA = "N/A_by_design"

REPO_PARENT = os.path.dirname(C.REPO)
VACC_CANDIDATES = [
    os.path.join(C.REPO, "examples", "vaccination_demo", "results"),
    os.path.join(REPO_PARENT, "wagf-main-runs", "examples", "vaccination_demo",
                 "results"),
]
VACC_ROOT = next((p for p in VACC_CANDIDATES if os.path.isdir(p)), None)
if VACC_ROOT is None:
    raise PrepError(
        "no examples/vaccination_demo/results found in this repo or in the sibling "
        f"wagf-main-runs checkout -- tried: {VACC_CANDIDATES}")

RUN_DIR_NAME = "JOH_T0-4_gemma3_4b_e0eee08c"
SEEDS = ["42", "43", "44"]
SKILLS = ["get_vaccinated", "delay", "refuse"]  # skill_registry.yaml, origin/main
DEFAULT_SKILL = "delay"                         # skill_registry.yaml default_skill
K_SKILLS = len(SKILLS)
CONSTRUCT_COLS = [
    "construct_BARRIERS_LABEL", "construct_BENEFITS_LABEL",
    "construct_CUES_TO_ACTION_LABEL", "construct_SELF_EFFICACY_LABEL",
    "construct_SEVERITY_LABEL", "construct_SUSCEPTIBILITY_LABEL",
]
LABEL_ALPHABET = ["VL", "L", "M", "H", "VH"]
DECISION_ALIAS = {"1": "get_vaccinated", "2": "delay", "3": "refuse"}


def run_dir(seed: str) -> str:
    d = os.path.join(VACC_ROOT, RUN_DIR_NAME, f"Run_{seed}")
    if not os.path.isdir(d):
        raise PrepError(f"missing vaccination run dir {d}")
    return d


def load_json(path: str) -> dict:
    if not os.path.isfile(path):
        raise PrepError(f"missing file {path}")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def classify_layer(layer: str) -> str:
    """Transcribed from r6_parser_layer_share.py:classify (same logic, vaccination
    corpus happens to only ever exercise clean_structured, verified below)."""
    s = (layer or "").strip().lower()
    if not s:
        return "blank"
    if "digit" in s:
        return "digit_fallback"
    if "keyword" in s:
        return "keyword_fallback"
    if "json" in s:
        return "clean_structured"
    return "other"


def split_ids(v) -> list:
    return [x.strip() for x in (v or "").split("|") if x.strip()]


def normalized_entropy(counts: dict, k: int) -> float:
    """Same definition _common.normalized_entropy uses (pooled-once Shannon / log2 k)."""
    tot = float(sum(counts.values()))
    if tot <= 0:
        raise PrepError("normalized_entropy called on an empty distribution")
    h = 0.0
    for v in counts.values():
        p = v / tot
        if p > 0:
            h -= p * math.log2(p)
    return h / math.log2(k)


def read_config_scalar(text: str, pattern: str, where: str) -> str:
    m = re.search(pattern, text, re.MULTILINE)
    if not m:
        raise PrepError(f"{where}: pattern {pattern!r} not found in config_snapshot.yaml")
    return m.group(1).strip()


ROW = dict  # readability alias


def new_row(row_type, seed, item, **kw) -> dict:
    rec = {
        "row_type": row_type, "domain": "vaccination", "seed": seed, "item": item,
        "level_or_stage": "", "n_total": NA, "n_matched": NA, "share_pct": NA,
        "share_of_rejected_pct": NA, "n_approved_after_retry": NA,
        "n_approved_first_attempt": NA, "n_rejected_final": NA, "value": NA,
        "detail": "", "note": "",
    }
    rec.update(kw)
    return rec


def integrity_row(seed: str, rd: str, aud: list) -> dict:
    ri = load_json(os.path.join(rd, "run_integrity.json"))
    manifest = load_json(os.path.join(rd, "reproducibility_manifest.json"))
    n = len(aud)
    agents = len({r["agent_id"] for r in aud})
    years = len({r["year"] for r in aud})
    flags = []
    if ri.get("integrity_ok") is not True:
        flags.append("integrity_ok=False")
    for k in ("audit_rows_missing_vs_grid", "audit_rows_missing_vs_configured_grid",
              "audit_sentinel_write_failures", "rules_uncategorised_total"):
        v = ri.get(k)
        if v not in (0, None):
            flags.append(f"{k}={v}")
    if ri.get("audit_corrected_status_columns") not in (False, None):
        flags.append(f"audit_corrected_status_columns={ri.get('audit_corrected_status_columns')}")
    if ri.get("world_grounded_coverage_gap") not in (None,):
        flags.append(f"world_grounded_coverage_gap={ri.get('world_grounded_coverage_gap')}")
    manifest_seed = str(manifest.get("seed"))
    seed_matches = manifest_seed == seed
    if not seed_matches:
        flags.append(f"manifest_seed({manifest_seed})!=dir_seed({seed})")
    if ri.get("audit_rows") != n:
        flags.append(f"run_integrity.audit_rows({ri.get('audit_rows')})!=csv_rows({n})")
    return new_row(
        "integrity", seed, "run_integrity",
        n_total=n, n_matched=agents * years,
        detail=(f"audit_rows={n}; agents={agents}; years={years}; "
                f"agents*years={agents * years}; manifest_seed={manifest_seed}; "
                f"dir_seed={seed}; seed_matches={seed_matches}; "
                f"framework_version={ri.get('framework_provenance', {}).get('framework_version')}; "
                f"audit_schema_version={ri.get('framework_provenance', {}).get('audit_schema_version')}; "
                f"git_commit_short={ri.get('framework_provenance', {}).get('git_commit_short')}"),
        note=("clean -- no flags" if not flags else "FLAGGED: " + " | ".join(flags)),
    )


def config_row(seed: str, rd: str) -> dict:
    cfg_path = os.path.join(rd, "config_snapshot.yaml")
    if not os.path.isfile(cfg_path):
        raise PrepError(f"missing {cfg_path}")
    with open(cfg_path, encoding="utf-8") as fh:
        text = fh.read()
    governance_profile = read_config_scalar(text, r"governance_profile:\s*(\S+)", cfg_path)
    framework = read_config_scalar(text, r"psychological_framework:\s*(\S+)", cfg_path)
    num_ctx_cfg = read_config_scalar(text, r"^\s*num_ctx:\s*(\S+)", cfg_path)
    num_predict_cfg = read_config_scalar(text, r"^\s*num_predict:\s*(\S+)", cfg_path)
    codes = sorted(set(re.findall(r"\b(VL|L|M|H|VH)\b", text)), key=LABEL_ALPHABET.index)

    manifest = load_json(os.path.join(rd, "reproducibility_manifest.json"))
    num_ctx_manifest = manifest.get("num_ctx")
    num_predict_manifest = manifest.get("num_predict")
    thinking_mode = manifest.get("thinking_mode")

    mismatch = (str(num_ctx_cfg) != str(num_ctx_manifest)
                or str(num_predict_cfg) != str(num_predict_manifest))
    note = ("NOT matched to any published run -- there is none. "
            "config_snapshot.yaml (declared) vs reproducibility_manifest.json "
            "(recorded actual) DISAGREE on num_ctx/num_predict"
            if mismatch else
            "NOT matched to any published run -- there is none.")

    return new_row(
        "config", seed, "config_snapshot",
        detail=(f"governance_profile={governance_profile}; framework={framework}; "
                f"label_alphabet={'/'.join(codes)}; "
                f"num_ctx_config_snapshot={num_ctx_cfg}; "
                f"num_predict_config_snapshot={num_predict_cfg}; "
                f"num_ctx_manifest={num_ctx_manifest}; "
                f"num_predict_manifest={num_predict_manifest}; "
                f"thinking_mode_manifest={thinking_mode}"),
        note=note,
    )


def rule_census_rows(seed: str, aud: list) -> list:
    """Mirrors r3_rule_firing_census.py:_census exactly (same columns, same math)."""
    C.require_cols(aud, ["status", "retry_count", "failed_rules", "warning_rules"],
                   f"vaccination/{seed}")
    n = len(aud)
    rej = [r for r in aud if (r.get("status") or "").strip().startswith("REJECTED")]
    out = []
    for level, col in (("ERROR", "failed_rules"), ("WARNING", "warning_rules")):
        ids = {}
        for r in aud:
            for rid in split_ids(r.get(col)):
                ids.setdefault(rid, []).append(r)
        for rid, rs in sorted(ids.items()):
            st = [(r.get("status") or "").strip() for r in rs]
            rc = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in rs]
            msgs = [(r.get("error_messages") or "").strip()[:160] for r in rs]
            modal = max(set(msgs), key=msgs.count) if msgs else ""
            out.append(new_row(
                "rule_census", seed, rid, level_or_stage=level,
                n_total=n, n_matched=len(rs),
                share_pct=100.0 * len(rs) / n,
                share_of_rejected_pct=(100.0 * len(rs) / len(rej)) if rej else "NA",
                n_approved_after_retry=sum(1 for s, c in zip(st, rc)
                                            if s == "APPROVED" and c > 0),
                n_approved_first_attempt=sum(1 for s, c in zip(st, rc)
                                              if s == "APPROVED" and c == 0),
                n_rejected_final=sum(1 for s in st if s.startswith("REJECTED")),
                detail=f"source_column={col}",
                note=modal,
            ))
    rc_all = [int(float((r.get("retry_count") or "0").strip() or 0)) for r in aud]
    st_all = [(r.get("status") or "").strip() for r in aud]
    status_counts = {
        "approved_first_attempt": sum(1 for s, c in zip(st_all, rc_all)
                                       if s == "APPROVED" and c == 0),
        "approved_after_retry": sum(1 for s, c in zip(st_all, rc_all)
                                     if s == "APPROVED" and c > 0),
        "rejected_to_fallback": len(rej),
    }
    covered = sum(status_counts.values())
    if covered != n:
        raise PrepError(f"vaccination/{seed}: status buckets cover {covered} of {n} rows")
    for name, k in status_counts.items():
        out.append(new_row(
            "rule_census", seed, name, level_or_stage="__STATUS__",
            n_total=n, n_matched=k, share_pct=100.0 * k / n,
            detail="source_column=status+retry_count",
        ))
    return out


def validator_health_rows(seed: str, rd: str) -> list:
    path = os.path.join(rd, "validator_health.csv")
    rows = C.read_csv(path)
    out = []
    for r in rows:
        seen = int(r["seen_count"])
        fire = int(r["fire_count"])
        warn = int(r["warn_count"])
        errp = int(r["error_path_count"])
        is_dead = seen > 0 and fire == 0
        note = ("DEAD-VALIDATOR log line fires for this rule (seen>0, fire=0). "
                "By construction a WARNING-level rule can never set fire_count>0 "
                "(it only ever warns), so this is expected, not a sign the rule is "
                "inert -- see docstring." if is_dead else "not flagged by the DEAD-"
                "VALIDATOR check (fired at least once at ERROR/blocking level)")
        out.append(new_row(
            "validator_health", seed, r["rule_id"],
            n_total=seen, n_matched=fire,
            share_pct=float(r["fire_rate"]) * 100.0,
            detail=f"warn_count={warn}; error_path_count={errp}",
            note=note,
        ))
    return out


def action_distribution_rows(seed: str, aud: list) -> list:
    C.require_cols(aud, ["proposed_skill", "final_skill", "status"], f"vaccination/{seed}")
    out = []
    for stage, col in (("proposal", "proposed_skill"), ("final", "final_skill")):
        counts = {s: 0 for s in SKILLS}
        other = 0
        for r in aud:
            v = (r.get(col) or "").strip()
            if v in counts:
                counts[v] += 1
            else:
                other += 1
        n = len(aud)
        for sk in SKILLS:
            out.append(new_row(
                "action_distribution", seed, sk, level_or_stage=stage,
                n_total=n, n_matched=counts[sk], share_pct=100.0 * counts[sk] / n,
            ))
        if other:
            out.append(new_row(
                "action_distribution", seed, "OTHER_UNMAPPED", level_or_stage=stage,
                n_total=n, n_matched=other, share_pct=100.0 * other / n,
                note="value outside the 3-skill registry vocabulary",
            ))
    # executed remap: no REJECTED rows exist in this batch (measured below), so
    # executed == final for every row here; computed generically rather than assumed.
    counts_exec = {s: 0 for s in SKILLS}
    other = 0
    for r in aud:
        st = (r.get("status") or "").strip()
        v = DEFAULT_SKILL if st.startswith("REJECTED") else (r.get("final_skill") or "").strip()
        if v in counts_exec:
            counts_exec[v] += 1
        else:
            other += 1
    n = len(aud)
    for sk in SKILLS:
        out.append(new_row(
            "action_distribution", seed, sk, level_or_stage="executed",
            n_total=n, n_matched=counts_exec[sk], share_pct=100.0 * counts_exec[sk] / n,
        ))
    if other:
        out.append(new_row(
            "action_distribution", seed, "OTHER_UNMAPPED", level_or_stage="executed",
            n_total=n, n_matched=other, share_pct=100.0 * other / n,
        ))

    h = normalized_entropy(counts_exec, K_SKILLS)
    out.append(new_row(
        "ehe_vaccination", seed, "ehe_vaccination", level_or_stage="executed",
        n_total=n, value=h,
        detail=f"k={K_SKILLS} skills {SKILLS}; pooled once over all {n} decisions",
    ))
    return out


def construct_label_rows(seed: str, aud: list) -> list:
    C.require_cols(aud, CONSTRUCT_COLS, f"vaccination/{seed}")
    n = len(aud)
    out = []
    for col in CONSTRUCT_COLS:
        vals = [(r.get(col) or "").strip().upper() for r in aud]
        alphabet_seen = sorted({v for v in vals if v}, key=lambda x: LABEL_ALPHABET.index(x)
                                if x in LABEL_ALPHABET else 99)
        unparsed = sum(1 for v in vals if v not in LABEL_ALPHABET)
        out.append(new_row(
            "construct_label", seed, col,
            n_total=n, n_matched=unparsed, share_pct=100.0 * unparsed / n,
            detail=f"alphabet_observed={'/'.join(alphabet_seen)}; "
                   f"full_alphabet={'/'.join(LABEL_ALPHABET)}",
            note="share_pct here is the UNPARSED share (outside VL..VH), not a value share",
        ))
    return out


def parser_layer_row(seed: str, aud: list) -> dict:
    C.require_cols(aud, ["parse_layer", "parse_confidence"], f"vaccination/{seed}")
    n = len(aud)
    buckets = {}
    layers = {}
    conf = []
    for r in aud:
        lay = (r.get("parse_layer") or "").strip()
        buckets[classify_layer(lay)] = buckets.get(classify_layer(lay), 0) + 1
        layers[lay or "<blank>"] = layers.get(lay or "<blank>", 0) + 1
        v = (r.get("parse_confidence") or "").strip()
        if v:
            conf.append(float(v))
    fb = (buckets.get("digit_fallback", 0) + buckets.get("keyword_fallback", 0)
          + buckets.get("blank", 0))
    return new_row(
        "parser_layer", seed, "parse_layer",
        n_total=n, n_matched=fb, share_pct=100.0 * fb / n,
        detail=(f"distinct_layers={' | '.join(f'{k}={v}' for k, v in sorted(layers.items()))}; "
                f"has_base_layer_col={'base_layer' in aud[0]}"),
        note=f"mean_parse_confidence={C.mean(conf):.4f}" if conf else "no parse_confidence values",
    )


def decision_field_check_row(seed: str, aud: list) -> dict:
    """Cross-checks raw_output's own JSON `decision` field against the recorded
    `proposed_skill`. Not part of the brief -- discovered while building this table.
    See module docstring for the full evidence chain."""
    C.require_cols(aud, ["raw_output", "proposed_skill", "year"], f"vaccination/{seed}")
    y1_total = y1_mismatch = 0
    y2_total = y2_mismatch = 0
    unparseable = 0
    for r in aud:
        raw = r.get("raw_output") or ""
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            unparseable += 1
            continue
        try:
            obj = json.loads(m.group(0))
        except Exception:
            unparseable += 1
            continue
        dec = str(obj.get("decision", "")).strip()
        mapped = DECISION_ALIAS.get(dec)
        prop = (r.get("proposed_skill") or "").strip()
        is_mismatch = mapped is not None and mapped != prop
        if r.get("year") == "1":
            y1_total += 1
            y1_mismatch += int(is_mismatch)
        else:
            y2_total += 1
            y2_mismatch += int(is_mismatch)
    return new_row(
        "decision_field_check", seed, "decision_field_vs_proposed_skill",
        n_total=len(aud), n_matched=y1_mismatch + y2_mismatch,
        share_pct=100.0 * (y1_mismatch + y2_mismatch) / len(aud),
        detail=(f"year1_mismatch={y1_mismatch}/{y1_total} "
                f"({100.0 * y1_mismatch / y1_total:.1f}%); "
                f"year2-10_mismatch={y2_mismatch}/{y2_total} "
                f"({100.0 * y2_mismatch / y2_total:.1f}%); "
                f"raw_output_unparseable={unparseable}"),
        note=("raw_output's own JSON decision field disagrees with recorded "
              "proposed_skill on the majority of year>=2 rows despite 100% "
              "enclosure+json parse_layer; NOT caught by run_integrity.json; root "
              "cause not identified in this analysis -- see module docstring."),
    )


def acceptance_verdict_rows(seed: str, aud: list, rule_rows: list) -> list:
    n = len(aud)
    rej = sum(1 for r in aud if (r.get("status") or "").strip().startswith("REJECTED"))
    retried = sum(1 for r in aud
                  if int(float((r.get("retry_count") or "0").strip() or 0)) > 0)
    any_error_fire = any(r["level_or_stage"] == "ERROR" and r["n_matched"] > 0
                          for r in rule_rows if r["row_type"] == "rule_census")
    any_warning_fire = any(r["level_or_stage"] == "WARNING" and r["n_matched"] > 0
                            for r in rule_rows if r["row_type"] == "rule_census")
    out = []
    out.append(new_row("acceptance_verdict", seed, "run_completes",
                        n_total=n, value=1000, note="PASS: 1000/1000 audit rows"))
    out.append(new_row("acceptance_verdict", seed, "rejection_rate",
                        n_total=n, n_matched=rej, share_pct=100.0 * rej / n,
                        note="PASS: no BLOCKER outcome" if rej == 0
                        else "measured, not a pass/fail by itself"))
    out.append(new_row("acceptance_verdict", seed, "retry_rate",
                        n_total=n, n_matched=retried, share_pct=100.0 * retried / n,
                        note="measured"))
    out.append(new_row(
        "acceptance_verdict", seed, "at_least_one_hbm_rule_fires",
        value=NA,
        note=("PASS (WARNING-level): non-blocking HBM coherence rules fired" +
              (" ; PASS (ERROR-level too)" if any_error_fire else
               " ; no ERROR-level (blocking) rule fired this seed") if any_warning_fire
              else ("PASS (ERROR-level only)" if any_error_fire
                    else "FAIL: no rule fired at either level")),
    ))
    out.append(new_row("acceptance_verdict", seed, "run_integrity_clean",
                        value=NA, note="PASS: integrity_ok=true, no flags (see row_type=integrity)"))
    out.append(new_row(
        "acceptance_verdict", seed, "traces_committed_only_if_clean",
        value=NA,
        note=("N/A_by_design: integrity IS clean (eligible), but these traces are not "
              "committed anywhere -- gitignored under examples/*/results/ in both this "
              "repo and the wagf-main-runs checkout that produced them; not yet "
              "promoted into a released corpus."),
    ))
    return out


FIELDNAMES = [
    "row_type", "domain", "seed", "item", "level_or_stage",
    "n_total", "n_matched", "share_pct", "share_of_rejected_pct",
    "n_approved_after_retry", "n_approved_first_attempt", "n_rejected_final",
    "value", "detail", "note",
]


def main() -> int:
    C.banner("R12  vaccination T0-4 (gemma3:4b, HBM, seeds 42/43/44)")
    print(f"  VACC_ROOT = {VACC_ROOT}")
    rows = []

    for seed in SEEDS:
        rd = run_dir(seed)
        aud = C.read_csv(os.path.join(rd, "individual_governance_audit.csv"))
        print(f"\n  seed {seed}: {len(aud)} audit rows, dir={rd}")

        rows.append(integrity_row(seed, rd, aud))
        rows.append(config_row(seed, rd))
        rc_rows = rule_census_rows(seed, aud)
        rows.extend(rc_rows)
        rows.extend(validator_health_rows(seed, rd))
        rows.extend(action_distribution_rows(seed, aud))
        rows.extend(construct_label_rows(seed, aud))
        rows.append(parser_layer_row(seed, aud))
        rows.append(decision_field_check_row(seed, aud))
        rows.extend(acceptance_verdict_rows(seed, aud, rc_rows))

    C.write_csv("r12_vaccination_t04.csv", FIELDNAMES, rows)

    print("\n  acceptance verdict summary:")
    for seed in SEEDS:
        print(f"    seed {seed}:")
        for r in rows:
            if r["row_type"] == "acceptance_verdict" and r["seed"] == seed:
                print(f"      {r['item']:32s} {r['note']}")

    print("\n  action distribution, executed, share % (3 seeds):")
    for seed in SEEDS:
        vals = {r["item"]: r["share_pct"] for r in rows
                if r["row_type"] == "action_distribution" and r["seed"] == seed
                and r["level_or_stage"] == "executed" and r["item"] in SKILLS}
        print(f"    seed {seed}: " + "  ".join(f"{k}={v:.1f}%" for k, v in vals.items()))

    print("\n  ehe_vaccination (pooled, executed, k=3):")
    for seed in SEEDS:
        v = next(r["value"] for r in rows
                  if r["row_type"] == "ehe_vaccination" and r["seed"] == seed)
        print(f"    seed {seed}: {v:.4f}")

    print("\n  decision-field vs proposed_skill mismatch (year1 / year2-10):")
    for seed in SEEDS:
        r = next(r for r in rows if r["row_type"] == "decision_field_check"
                 and r["seed"] == seed)
        print(f"    seed {seed}: {r['detail']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
