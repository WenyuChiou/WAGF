"""R12b -- vaccination T0-4b: parity / governance sanity / uptake, options-text-parity
FIX arm (commit 88c21542, seeds 42/43/44, 100 agents x 10 years).

RELATIONSHIP TO r12_vaccination_t04.py -- this is a NEW, independent script.
r12_vaccination_t04.py is untouched and still targets the OLD/REJECTED arm
(e0eee08c) with a fixed digit->skill alias table. This script targets the NEW
(fixed) arm by default, decodes each row's own rendered "Available actions"
menu from raw/individual_traces.jsonl (not an assumed fixed order -- this is
the direct test of whether the options-text-parity fix actually holds), and
does not read validator_health.csv (that file does not exist for the new
arm -- see DEAD VALIDATOR FILE note below). --old-arm reruns the identical
three tables against the OLD/REJECTED arm for a reproducible side-by-side.

DEAD VALIDATOR FILE -- validator_health.csv
  broker/components/analytics/audit.py only writes validator_health.csv when
  its in-memory summary dict is non-empty, and that dict only gains an entry
  when a validation_result carries a rule_id (i.e. a rule's own precondition
  matched something -- see audit.py:1041-1055, 1208-1211). It is not a
  general "rule engine was invoked this row" counter. Governance sanity here
  is therefore read directly off individual_governance_audit.csv's own
  failed_rules/warning_rules/retry_count/status columns, which every run
  writes unconditionally -- no dependency on validator_health.csv either way.

FAIL-LOUD CONTRACT (matches _common.py) -- missing directory, missing file,
missing column, empty denominator -> raise PrepError. Nothing here
substitutes 0/NaN for data that should exist.

Usage:
  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12b_vaccination_t04b.py
  python SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r12b_vaccination_t04b.py --old-arm

Output:
  out/r12b_vaccination_parity.csv      -- per (arm, seed, year) parity + an ALL-years row
  out/r12b_vaccination_governance.csv  -- per (arm, seed) status/rule-fire/retry/integrity, long format
  out/r12b_vaccination_uptake.csv      -- per (arm, seed, year) annual + cumulative uptake
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _common as C  # noqa: E402
from _common import PrepError  # noqa: E402

REPO_PARENT = os.path.dirname(C.REPO)

NEW_ROOT = os.path.join(C.REPO, "examples", "vaccination_demo", "results")
NEW_DIR_NAME = "JOH_T0-4b_gemma3_4b_88c21542"
NEW_ARM_LABEL = "NEW_88c21542"

OLD_ROOT = os.path.join(REPO_PARENT, "wagf-main-runs", "examples",
                         "vaccination_demo", "results")
OLD_DIR_NAME = "JOH_T0-4_gemma3_4b_e0eee08c"
OLD_ARM_LABEL = "REJECTED_e0eee08c"

SEEDS = ["42", "43", "44"]
SKILLS = ["get_vaccinated", "delay", "refuse"]
DEFAULT_SKILL = "delay"  # skill_registry.yaml default_skill (matches r12)

# Keyword rules to decode the "Available actions" menu independent of digit
# order -- verified against the corpus prose in both arms (grep-checked, not
# assumed): the three action descriptions are fixed text, only their digit
# position (and, pre-fix, their presence at all past year 1) can vary.
MENU_KEYWORDS = [
    ("get_vaccinated", re.compile(r"receive a single dose|recommended vaccine", re.I)),
    ("delay", re.compile(r"postpone the vaccination", re.I)),
    ("refuse", re.compile(r"decline vaccination", re.I)),
]
AVAILABLE_ACTIONS_RE = re.compile(r"Available actions:\s*(.*?)\n\s*\n", re.S)
MENU_LINE_RE = re.compile(r"^\s*(\d+)\.\s*(.+)$", re.M)
DECISION_RE = re.compile(r'"decision"\s*:\s*"?(\d+)"?')


def run_dir(root: str, dir_name: str, seed: str) -> str:
    d = os.path.join(root, dir_name, f"Run_{seed}")
    if not os.path.isdir(d):
        raise PrepError(f"missing vaccination run dir {d}")
    return d


def read_jsonl_by_step(path: str) -> dict:
    if not os.path.isfile(path):
        raise PrepError(f"missing raw trace file {path}")
    by_step = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "step_id" in obj:
                by_step[int(obj["step_id"])] = obj
    if not by_step:
        raise PrepError(f"zero step-keyed records in {path}")
    return by_step


def decode_menu(input_text: str):
    """Returns the digit->skill mapping, or None if the prompt genuinely
    carries no renderable menu (the pre-fix '[N/A]' placeholder bug -- this
    is a fact about the OLD arm's prompts, not a parse failure, so it is a
    distinct return value, not an exception)."""
    m = AVAILABLE_ACTIONS_RE.search(input_text or "")
    if not m:
        raise PrepError("no 'Available actions:' block found in rendered prompt")
    block = m.group(1)
    if block.strip() in ("[N/A]", "N/A", ""):
        return None
    mapping = {}
    for digit, text in MENU_LINE_RE.findall(block):
        skill = next((sk for sk, pat in MENU_KEYWORDS if pat.search(text)), None)
        if skill is None:
            raise PrepError(f"menu line for digit {digit} matched no keyword rule: {text!r}")
        mapping[digit] = skill
    if set(mapping.values()) != set(SKILLS):
        raise PrepError(f"decoded menu does not cover all 3 skills: {mapping}")
    return mapping


def decode_decision_digit(raw_output: str):
    m = DECISION_RE.search(raw_output or "")
    return m.group(1) if m else None


# ---------------------------------------------------------------------------
# table 1: parity
# ---------------------------------------------------------------------------
def parity_rows(arm_label: str, seed: str, rd: str) -> list:
    audit = C.read_csv(os.path.join(rd, "individual_governance_audit.csv"))
    C.require_cols(audit, ["step_id", "agent_id", "year", "proposed_skill"], f"{arm_label}/{seed}")
    by_step = read_jsonl_by_step(os.path.join(rd, "raw", "individual_traces.jsonl"))

    per_year = {}
    for r in audit:
        step_id = int(r["step_id"])
        year = r["year"]
        jr = by_step.get(step_id)
        if jr is None:
            raise PrepError(f"{arm_label}/{seed}: no jsonl record for step_id={step_id}")
        if jr.get("agent_id") != r["agent_id"] or str(jr.get("year")) != str(year):
            raise PrepError(f"{arm_label}/{seed}: step_id={step_id} key mismatch "
                             f"(csv agent_id/year={r['agent_id']}/{year}, "
                             f"jsonl={jr.get('agent_id')}/{jr.get('year')})")
        menu = decode_menu(jr.get("input") or "")
        n, m, no_menu = per_year.setdefault(year, [0, 0, 0])
        if menu is None:
            # Pre-fix '[N/A]' placeholder: no menu was rendered, so a digit
            # cannot be decoded to a skill at all. Counted separately, not
            # folded into parity_pct's denominator -- decodability and
            # correctness are different facts.
            per_year[year] = [n + 1, m, no_menu + 1]
            continue
        digit = decode_decision_digit(jr.get("raw_output") or "")
        decoded = menu.get(digit) if digit is not None else None
        proposed = (r.get("proposed_skill") or "").strip()
        is_match = decoded is not None and decoded == proposed
        per_year[year] = [n + 1, m + int(is_match), no_menu]

    out = []
    tot_n = tot_m = tot_nomenu = 0
    for year in sorted(per_year, key=int):
        n, m, no_menu = per_year[year]
        tot_n += n
        tot_m += m
        tot_nomenu += no_menu
        decodable = n - no_menu
        out.append({"arm": arm_label, "seed": seed, "year": year,
                     "n": n, "n_match": m, "n_no_menu_rendered": no_menu,
                     "parity_pct_of_decodable": (100.0 * m / decodable) if decodable else "NA"})
    decodable_tot = tot_n - tot_nomenu
    out.append({"arm": arm_label, "seed": seed, "year": "ALL",
                "n": tot_n, "n_match": tot_m, "n_no_menu_rendered": tot_nomenu,
                "parity_pct_of_decodable": (100.0 * tot_m / decodable_tot) if decodable_tot else "NA"})
    return out


# ---------------------------------------------------------------------------
# table 2: governance sanity (long format: arm, seed, metric, key, value)
# ---------------------------------------------------------------------------
def governance_rows(arm_label: str, seed: str, rd: str) -> list:
    audit = C.read_csv(os.path.join(rd, "individual_governance_audit.csv"))
    C.require_cols(audit, ["status", "retry_count", "failed_rules", "warning_rules"],
                   f"{arm_label}/{seed}")
    out = []

    def bump(d, k):
        d[k] = d.get(k, 0) + 1

    status_counts, retry_dist, failed, warn = {}, {}, {}, {}
    for r in audit:
        bump(status_counts, (r.get("status") or "").strip())
        rc = (r.get("retry_count") or "0").strip() or "0"
        bump(retry_dist, rc)
        for rid in (r.get("failed_rules") or "").split("|"):
            rid = rid.strip()
            if rid:
                bump(failed, rid)
        for rid in (r.get("warning_rules") or "").split("|"):
            rid = rid.strip()
            if rid:
                bump(warn, rid)

    for k, v in sorted(status_counts.items()):
        out.append({"arm": arm_label, "seed": seed, "metric": "status", "key": k, "value": v})
    for k, v in sorted(retry_dist.items()):
        out.append({"arm": arm_label, "seed": seed, "metric": "retry_count", "key": k, "value": v})
    for k, v in sorted(failed.items()):
        out.append({"arm": arm_label, "seed": seed, "metric": "failed_rule_ERROR", "key": k, "value": v})
    for k, v in sorted(warn.items()):
        out.append({"arm": arm_label, "seed": seed, "metric": "warning_rule_WARNING", "key": k, "value": v})
    if not failed and not warn:
        out.append({"arm": arm_label, "seed": seed, "metric": "warning_rule_WARNING",
                     "key": "(none fired)", "value": 0})

    ri_path = os.path.join(rd, "run_integrity.json")
    if not os.path.isfile(ri_path):
        raise PrepError(f"missing {ri_path}")
    with open(ri_path, encoding="utf-8") as fh:
        ri = json.load(fh)
    out.append({"arm": arm_label, "seed": seed, "metric": "integrity",
                "key": "integrity_ok", "value": ri.get("integrity_ok")})
    for k in ("audit_rows_missing_vs_grid", "audit_rows_missing_vs_configured_grid",
              "audit_sentinel_write_failures", "rules_uncategorised_total"):
        v = ri.get(k, None)
        if v not in (0, None):
            out.append({"arm": arm_label, "seed": seed, "metric": "integrity_anomaly",
                        "key": k, "value": v})
    return out


# ---------------------------------------------------------------------------
# table 3: uptake
# ---------------------------------------------------------------------------
def uptake_rows(arm_label: str, seed: str, rd: str) -> list:
    audit = C.read_csv(os.path.join(rd, "individual_governance_audit.csv"))
    C.require_cols(audit, ["agent_id", "year", "final_skill", "status"], f"{arm_label}/{seed}")
    agents = sorted({r["agent_id"] for r in audit})
    years = sorted({int(r["year"]) for r in audit})
    by_year = {y: {} for y in years}
    for r in audit:
        by_year[int(r["year"])][r["agent_id"]] = r

    ever = set()
    out = []
    for y in years:
        annual = 0
        for aid, r in by_year[y].items():
            status = (r.get("status") or "").strip()
            executed = DEFAULT_SKILL if status.startswith("REJECTED") else (r.get("final_skill") or "").strip()
            if executed == "get_vaccinated":
                annual += 1
                ever.add(aid)
        out.append({"arm": arm_label, "seed": seed, "year": y,
                     "annual_share_pct": 100.0 * annual / len(agents),
                     "cumulative_share_pct": 100.0 * len(ever) / len(agents)})
    return out


def collect(arm_label: str, root: str, dir_name: str):
    parity, gov, uptake = [], [], []
    for seed in SEEDS:
        rd = run_dir(root, dir_name, seed)
        parity.extend(parity_rows(arm_label, seed, rd))
        gov.extend(governance_rows(arm_label, seed, rd))
        uptake.extend(uptake_rows(arm_label, seed, rd))
    return parity, gov, uptake


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--old-arm", action="store_true",
                     help="target the OLD/REJECTED e0eee08c arm instead of the NEW 88c21542 arm")
    args = ap.parse_args()

    if args.old_arm:
        arm_label, root, dir_name = OLD_ARM_LABEL, OLD_ROOT, OLD_DIR_NAME
    else:
        arm_label, root, dir_name = NEW_ARM_LABEL, NEW_ROOT, NEW_DIR_NAME

    C.banner(f"R12b  vaccination T0-4b  arm={arm_label}  seeds={SEEDS}")
    print(f"  root = {os.path.join(root, dir_name)}")

    parity, gov, uptake = collect(arm_label, root, dir_name)

    C.write_csv("r12b_vaccination_parity.csv",
                ["arm", "seed", "year", "n", "n_match", "n_no_menu_rendered",
                 "parity_pct_of_decodable"], parity)
    C.write_csv("r12b_vaccination_governance.csv",
                ["arm", "seed", "metric", "key", "value"], gov)
    C.write_csv("r12b_vaccination_uptake.csv",
                ["arm", "seed", "year", "annual_share_pct", "cumulative_share_pct"], uptake)

    print("\n  parity, ALL-years row per seed:")
    for row in parity:
        if row["year"] == "ALL":
            pct = row["parity_pct_of_decodable"]
            pct_s = f"{pct:.2f}%" if isinstance(pct, float) else str(pct)
            print(f"    seed {row['seed']}: {row['n_match']}/{row['n']} match "
                  f"({row['n_no_menu_rendered']} no-menu-rendered) -> {pct_s} of decodable")

    print("\n  final (year-10) cumulative uptake per seed:")
    by_seed_year = {}
    for row in uptake:
        by_seed_year.setdefault(row["seed"], {})[row["year"]] = row["cumulative_share_pct"]
    for seed in SEEDS:
        years = by_seed_year.get(seed, {})
        if years:
            last_y = max(years)
            print(f"    seed {seed}: {years[last_y]:.1f}%")

    print("\n  governance: rule fires per seed:")
    for seed in SEEDS:
        fires = [r for r in gov if r["seed"] == seed
                 and r["metric"] in ("failed_rule_ERROR", "warning_rule_WARNING")
                 and r["key"] != "(none fired)"]
        print(f"    seed {seed}: {[(r['metric'], r['key'], r['value']) for r in fires] or '(none)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
