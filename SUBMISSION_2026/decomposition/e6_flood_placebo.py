"""ESTIMATOR e6 -- FLOOD PLACEBO / NEGATIVE CONTROL for the post-treatment-conditioning defect.

=============================================================================
THE ESTIMAND, IN WORDS
=============================================================================
In the flood testbed, run the SAME two contrasts the irrigation headline runs -- one that
conditions on the agent's own post-treatment self-report and one that does not -- and ask how
far apart they are.

Concretely, for each flood model cell and each arm (validators ON = "governed", validators OFF
= "ungoverned"):

  CONDITIONAL rate   R = P( action == do_nothing | self-reported threat appraisal in {H,VH} )
  UNCONDITIONAL rate U = P( action == do_nothing )   over every parsed active decision
  HIGH share         s = P( self-reported threat appraisal in {H,VH} )

`do_nothing` is not an arbitrary choice: it is exactly the action the flood testbed's ONLY
ERROR-level appraisal-conditioned theory rule forbids. From every flood config_snapshot.yaml,
household.governance.strict.thinking_rules:

    id: extreme_threat_block   construct: TP_LABEL   when_above: [H, VH]
    blocked_skills: [do_nothing]   level: ERROR

So R is the structural twin of the irrigation IBR/AAI: "share of decisions that claimed a high
appraisal and then took the action the theory forbids at a high appraisal". Irrigation conditions
on high WATER SCARCITY appraisal (WSA) and counts increases; flood conditions on high THREAT
appraisal (TP) and counts do-nothings. Same shape, different construct, different action set.

The estimand of e6 is the PLACEBO CONTRAST:

    composition component of the flood gap,  and  (conditional gap - unconditional gap),

measured on a testbed where the theory rules almost never bind, so governance has almost no
opportunity to move the self-report. This is a NEGATIVE CONTROL on the instrument, not a new
causal estimate of anything.

=============================================================================
THE IDENTIFYING ASSUMPTION (and it is weak on purpose)
=============================================================================
e6 identifies NO causal effect. It is a falsification test of a MECHANISM STORY, and the only
thing it assumes is:

  (A) Flood and irrigation share the same harness, the same governance code path, the same audit
      writer and the same appraisal-label vocabulary {VL,L,M,H,VH}, so a difference between the
      two testbeds cannot be an artifact of the measurement instrument.

The mechanism story under test is: "the irrigation conditional gap is inflated because governance
moves the conditioning variable". That story makes a sharp, checkable prediction -- where
enforcement pressure is near zero, the conditioning variable should not move, and the conditional
and unconditional contrasts should agree.

=============================================================================
WHAT WOULD FALSIFY THE RESULT
=============================================================================
  F1. Flood shows a LARGE high-appraisal shift between arms (say |ds| > 10 pp) despite a
      near-zero rejection rate. Then the shift is not caused by enforcement pressure, and the
      "governance moves the mediator" story is wrong or badly incomplete.
  F2. Flood's composition component is a large fraction of its unconditional gap. Then
      composition contamination is generic to the harness, not specific to binding rules, and it
      cannot be used to argue that the irrigation number is special.
  F3. Flood's conditional and unconditional gaps disagree strongly in SIGN. Then "drop the
      conditioning and see what survives" is not a stable estimator anywhere and e2/e3's
      irrigation numbers inherit that instability.
  F4. The flood corpus turns out not to be a comparable pair (unmatched seeds, partial runs), in
      which case e6 identifies nothing and must say so. -- SEE THE DATA-INTEGRITY SECTION: this
      one PARTIALLY FIRES, and the script reports it rather than averaging over it.

=============================================================================
DECOMPOSITION ARITHMETIC (declared explicitly)
=============================================================================
This is the SAME arithmetic as estimator e3, verified by reading e3_decomposition.py rather than
assumed: e3's `comp_sym` = SUM_a (s_g,a - s_u,a) * 0.5*(r_g,a + r_u,a) and `behv_sym` =
SUM_a sbar_a * (r_g,a - r_u,a). On the two-stratum partition {HIGH, LOW} those collapse term by
term to the expressions below, because s_g,LOW - s_u,LOW = -(s_g,HIGH - s_u,HIGH). e3 additionally
reports untreated-reference and governed-reference three-fold variants; e6 reports only the
symmetric one, which is e3's headline and the only one free of index-number ambiguity.

The exact two-stratum Oaxaca-Blinder / Kitagawa split with symmetric (average) weights:

  strata k in {HIGH, LOW}         HIGH = appraisal in {H,VH};  LOW = the other parsed levels
  arm a in {g = governed, u = ungoverned}
  s_a  = share of parsed active decisions in stratum HIGH
  r_a^k = rate of the forbidden action within stratum k
  U_a  = s_a * r_a^H + (1 - s_a) * r_a^L

  ds     = s_g - s_u                sbar   = (s_g + s_u)/2
  dr^k   = r_g^k - r_u^k            rbar^k = (r_g^k + r_u^k)/2

  BEHAVIOUR   = sbar * dr^H + (1 - sbar) * dr^L
  COMPOSITION = ds * (rbar^H - rbar^L)
  IDENTITY    U_g - U_u  ==  BEHAVIOUR + COMPOSITION        (exact; asserted at runtime)

COMPOSITION is the part of the unconditional gap attributable purely to the treatment having
moved agents between strata, holding within-stratum behaviour at its arm-average.

A SECOND identity matters just as much, and the flood data forced it into this script. The gap
between the two estimands is NOT composition alone:

  dR = dr^H  (the conditional gap is, by definition, the within-HIGH effect)
  dR - dU  ==  (1 - sbar) * (dr^H - dr^L)  -  COMPOSITION      (exact; asserted at runtime)
               \______ HETEROGENEITY ______/

HETEROGENEITY is the part driven by the treatment hitting the two strata UNEQUALLY. A rule that
forbids an action only at a high appraisal is by construction a stratum-targeted treatment, so
dr^H and dr^L should be expected to differ, and the conditional and unconditional estimands
should be expected to differ, even when composition is exactly zero. Reporting only COMPOSITION
would have hidden this.

=============================================================================
SIGN CONVENTIONS, IN WORDS
=============================================================================
  * Every gap is  governed MINUS ungoverned.  NEGATIVE means governance LOWERED the rate.
  * R and U count the FORBIDDEN action, so LOWER IS BETTER behaviour and a NEGATIVE gap is the
    direction the paper claims as the governance benefit. This matches _loader.py's convention
    for irrigation (published headline -23.02 pp), and this module never flips it to "+23.0 pp".
  * ds = s_governed - s_ungoverned. In irrigation ds is strongly NEGATIVE (governance suppresses
    high self-reported scarcity). The brief quotes the same quantity with the opposite sign
    ("+45.5 pp shift", ungoverned minus governed); both are printed to avoid any confusion.

=============================================================================
DATA INTEGRITY -- READ THIS BEFORE READING ANY NUMBER
=============================================================================
Verified on disk by this script, not assumed:
  * The six v1 flood cells (JOH_FINAL vs JOH_ABLATION_DISABLED) have MISMATCHED SEED SETS.
    Governed Run_1..Run_5 carry seeds {42, 4202, 4203, 45, 46}; the no-validator arm carries
    {42, 43, 44, 45, 46}. Only THREE seeds are shared. Run_2 and Run_3 are NOT a matched pair in
    any of those six cells. Paired contrasts there use n=3 (df=2) and are labelled degraded.
  * The three v2 flood cells (gemma4_*, JOH_FINAL_v2 vs JOH_ABLATION_DISABLED_v2) are balanced
    at 5 matched seeds.
  * simulation_log.csv is COMPLETE at 1000 rows (100 agents x 10 years) in every flood run.
  * household_governance_audit.csv is SHORTER than 1000 in every run. This script tests, per run,
    whether the shortfall is exactly the set of post-relocation rows (agents that have already
    left and make no further decision) or a genuine trace drop, and reports the residual.
  * examples/single_agent/results/_DATA_DEFECTS_2026-05-30.md documents a reflection confound in
    no-validator Run_1/2/3 of the six v1 models. Those defective runs now sit in
    _QUARANTINE_reflection_missing_2026-05-30/ and the live JOH_ABLATION_DISABLED Run_1/2/3
    directories carry reflection logs. This script checks reflection-log presence per run and
    flags any run that lacks one.

Nothing under examples/ is written. This script writes only e6_flood_placebo.csv next to itself.

Usage:  python SUBMISSION_2026/decomposition/e6_flood_placebo.py [--csv PATH]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys

sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
import _loader as L  # noqa: E402  canonical loader; stats helpers + irrigation side-by-side

HERE = os.path.abspath(os.path.dirname(__file__))
REPO = L.REPO
FLOOD_RESULTS = os.path.join(REPO, "examples", "single_agent", "results")

SIM = "simulation_log.csv"
AUD = "household_governance_audit.csv"

# ---- flood-specific definitions. NOT the irrigation ones. --------------------
HIGH = frozenset({"H", "VH"})                       # same vocabulary as irrigation
LABEL_LEVELS = frozenset({"VL", "L", "M", "H", "VH"})
FORBIDDEN = frozenset({"do_nothing"})               # extreme_threat_block blocked_skills
FLOOD_DEFAULT_SKILL = "do_nothing"                  # agent_types.yaml household default_skill
APPRAISAL_COL = "threat_appraisal"                  # sim log; audit twin is construct_TP_LABEL
ACTION_COL = "yearly_decision"
INACTIVE_MARK = "relocated"                         # already-relocated: no decision was made
EXPECTED_SIM_ROWS = 1000                            # 100 agents x 10 years

# (cell label, governed root, governed group, ungoverned root, ungoverned group)
CELL_SETS = [
    ("v1", "JOH_FINAL", "Group_C", "JOH_ABLATION_DISABLED", "Group_C_disabled"),
    ("v2", "JOH_FINAL_v2", "Group_C", "JOH_ABLATION_DISABLED_v2", "Group_C_disabled"),
]
ANCHOR_CELL = "gemma3_4b"        # the model the Nature Water flood testbed reports
MIN_GAP_FOR_SHARE = 3.0          # pp; below this a composition/total SHARE is noise (e3's guard)


class DataError(RuntimeError):
    pass


# =============================================================================
# discovery
# =============================================================================
def _read_csv(path):
    if not os.path.isfile(path):
        raise DataError(f"missing file {path}")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise DataError(f"file present but zero data rows: {path}")
    return rows


def _seed_of(run_dir):
    """Seed from reproducibility_manifest.json. Never inferred from the Run_N name."""
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise DataError(f"no reproducibility_manifest.json in {run_dir}")
    j = json.load(open(p, encoding="utf-8"))
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() == "seed":
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(j)
    if not found:
        raise DataError(f"no seed key in {p}")
    if len({str(x) for x in found}) != 1:
        raise DataError(f"conflicting seeds {found} in {p}")
    return str(found[0])


def discover(root, group):
    """{seed: run_dir} for every run under results/<root>/<model>/<group>/Run_*."""
    out = {}
    base = os.path.join(FLOOD_RESULTS, root)
    if not os.path.isdir(base):
        raise DataError(f"missing flood root {base}")
    for model in sorted(os.listdir(base)):
        d = os.path.join(base, model, group)
        if not os.path.isdir(d):
            continue
        per = {}
        for run in sorted(os.listdir(d)):
            rd = os.path.join(d, run)
            if not os.path.isdir(rd) or not os.path.isfile(os.path.join(rd, SIM)):
                continue
            s = _seed_of(rd)
            if s in per:
                raise DataError(f"duplicate seed {s} in {d}")
            per[s] = rd
        if per:
            out[model] = per
    return out


# =============================================================================
# per-run measurement
# =============================================================================
def appraisal(row):
    return (row.get(APPRAISAL_COL) or "").strip().upper()


def act(row):
    return (row.get(ACTION_COL) or "").strip()


def measure_run(run_dir):
    """Every quantity e6 needs from one flood run. Pure counting; nothing dropped silently."""
    sim = _read_csv(os.path.join(run_dir, SIM))
    n_all = len(sim)

    inactive = [r for r in sim if act(r) == INACTIVE_MARK]
    active = [r for r in sim if act(r) != INACTIVE_MARK]
    parsed = [r for r in active if appraisal(r) in LABEL_LEVELS]
    unparsed = [r for r in active if appraisal(r) not in LABEL_LEVELS]

    hi = [r for r in parsed if appraisal(r) in HIGH]
    lo = [r for r in parsed if appraisal(r) not in HIGH]

    def rate(rows):
        return float("nan") if not rows else 100.0 * sum(1 for r in rows if act(r) in FORBIDDEN) / len(rows)

    m = {
        "run_dir": run_dir,
        "n_all": n_all,
        "n_inactive": len(inactive),
        "n_active": len(active),
        "n_parsed": len(parsed),
        "n_unparsed": len(unparsed),
        "n_high": len(hi),
        "n_low": len(lo),
        "R_cond": rate(hi),                 # conditional on HIGH appraisal (published style)
        "r_low": rate(lo),
        "U_uncond": rate(parsed),           # unconditional over parsed active decisions
        "U_designfixed": 100.0 * sum(1 for r in sim if act(r) in FORBIDDEN) / n_all,
        "s_high": float("nan") if not parsed else 100.0 * len(hi) / len(parsed),
        "pct_unparsed": 100.0 * len(unparsed) / len(active) if active else float("nan"),
        "pct_inactive": 100.0 * len(inactive) / n_all,
        "has_reflection": os.path.getsize(os.path.join(run_dir, "reflection_log.jsonl")) > 1000
        if os.path.isfile(os.path.join(run_dir, "reflection_log.jsonl")) else False,
    }

    # ---- audit cross-check: enforcement pressure + intent-vs-world action -----
    ap = os.path.join(run_dir, AUD)
    if os.path.isfile(ap):
        aud = _read_csv(ap)
        m["n_audit"] = len(aud)
        rej = [r for r in aud if (r.get("status") or "").strip().startswith("REJECTED")]
        m["pct_rejected"] = 100.0 * len(rej) / len(aud)
        # is the audit shortfall exactly the post-relocation rows?
        ks = {(r["agent_id"], r["year"]) for r in sim}
        ka = {(r["agent_id"], r["year"]) for r in aud}
        sim_only = ks - ka
        inact_keys = {(r["agent_id"], r["year"]) for r in inactive}
        m["audit_only_keys"] = len(ka - ks)
        m["sim_only_keys"] = len(sim_only)
        m["sim_only_not_relocated"] = len(sim_only - inact_keys)
        # yearly_decision vs final_skill, and V_intent vs V_world on the audit
        smap = {(r["agent_id"], r["year"]): r for r in sim}
        agree = vi = vw = den = 0
        for r in aud:
            s = smap.get((r["agent_id"], r["year"]))
            if s is None:
                continue
            if act(s) == (r.get("final_skill") or "").strip():
                agree += 1
            tp = (r.get("construct_TP_LABEL") or "").strip().upper()
            if tp not in HIGH:
                continue
            den += 1
            final = (r.get("final_skill") or "").strip()
            status = (r.get("status") or "").strip()
            executed = FLOOD_DEFAULT_SKILL if status.startswith("REJECTED") else final
            vi += final in FORBIDDEN
            vw += executed in FORBIDDEN
        m["pct_decision_eq_final"] = 100.0 * agree / len(aud) if aud else float("nan")
        m["V_intent"] = 100.0 * vi / den if den else float("nan")
        m["V_world"] = 100.0 * vw / den if den else float("nan")
    else:
        m["n_audit"] = -1
        for k in ("pct_rejected", "pct_decision_eq_final", "V_intent", "V_world"):
            m[k] = float("nan")
        for k in ("audit_only_keys", "sim_only_keys", "sim_only_not_relocated"):
            m[k] = -1
    return m


# =============================================================================
# decomposition (arithmetic declared in the docstring; identity asserted)
# =============================================================================
def decompose(g, u):
    """Exact symmetric two-stratum Oaxaca-Blinder split of the UNCONDITIONAL gap."""
    s_g, s_u = g["s_high"] / 100.0, u["s_high"] / 100.0
    rH_g, rH_u = g["R_cond"], u["R_cond"]
    rL_g, rL_u = g["r_low"], u["r_low"]
    if any(x != x for x in (s_g, s_u, rH_g, rH_u, rL_g, rL_u)):
        return None
    ds = s_g - s_u
    sbar = (s_g + s_u) / 2.0
    beh = sbar * (rH_g - rH_u) + (1 - sbar) * (rL_g - rL_u)
    comp = ds * ((rH_g + rH_u) / 2.0 - (rL_g + rL_u) / 2.0)
    dU = g["U_uncond"] - u["U_uncond"]
    resid = dU - (beh + comp)
    if abs(resid) > 1e-9:
        raise DataError(f"decomposition identity broken by {resid:.3e} pp")
    dR = rH_g - rH_u
    hetero = (1 - sbar) * ((rH_g - rH_u) - (rL_g - rL_u))
    resid2 = (dR - dU) - (hetero - comp)
    if abs(resid2) > 1e-9:
        raise DataError(f"heterogeneity identity broken by {resid2:.3e} pp")
    return {
        "dR_cond": dR,
        "dU_uncond": dU,
        "ds_high_pp": (s_g - s_u) * 100.0,
        "rH_g": rH_g, "rH_u": rH_u, "rL_g": rL_g, "rL_u": rL_u,
        "dr_high": rH_g - rH_u,
        "dr_low": rL_g - rL_u,
        "behaviour": beh,
        "composition": comp,
        "heterogeneity": hetero,
        "comp_share": abs(comp) / (abs(beh) + abs(comp)) if (abs(beh) + abs(comp)) > 0 else float("nan"),
        "cond_minus_uncond": dR - dU,
        "identity_residual": resid,
        "identity_residual2": resid2,
    }


def paired(diffs):
    t, df = L.paired_t(diffs)
    return t, df, L.t_two_sided_p(t, df)


def fmt(x, w=8, d=2, pct=False):
    if x != x:
        return " " * (w - 3) + "n/a"
    return f"{x:>{w}.{d}f}" + ("%" if pct else "")


# =============================================================================
# irrigation side-by-side, computed with the IDENTICAL arithmetic
# =============================================================================
def irrigation_reference():
    """Anchor irrigation cell (gemma3:4b) through the same decomposition, for contrast."""
    _, prefix = L.ANCHOR
    seeds = L.paired_seeds(prefix)
    rows = []
    for s in seeds:
        per = {}
        for arm in ("governed", "ungoverned"):
            rr = L.load_run(L.run_dir(arm, prefix, s))
            parsed = [r for r in rr if L.wsa(r) in L.LABEL_LEVELS]
            hi = [r for r in parsed if L.is_high(r)]
            lo = [r for r in parsed if not L.is_high(r)]
            per[arm] = {
                "s_high": 100.0 * len(hi) / len(parsed),
                "R_cond": 100.0 * sum(1 for r in hi if L.is_increase(r)) / len(hi),
                "r_low": 100.0 * sum(1 for r in lo if L.is_increase(r)) / len(lo),
                "U_uncond": 100.0 * sum(1 for r in parsed if L.is_increase(r)) / len(parsed),
            }
        d = decompose(per["governed"], per["ungoverned"])
        d["seed"] = s
        rows.append(d)
    return seeds, rows


# =============================================================================
# main
# =============================================================================
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "e6_flood_placebo.csv"))
    args = ap.parse_args()

    print("=" * 100)
    print("ESTIMATOR e6 -- FLOOD PLACEBO / NEGATIVE CONTROL")
    print("=" * 100)
    print(f"repo         : {REPO}")
    print(f"flood results: {FLOOD_RESULTS}")
    print("conditioning : threat_appraisal in {H,VH}   (POST-TREATMENT -- the defect under study)")
    print("forbidden act: do_nothing   (extreme_threat_block, the ONLY ERROR-level")
    print("               appraisal-conditioned flood thinking rule; blocked_skills=[do_nothing])")
    print("sign         : every gap is GOVERNED minus UNGOVERNED; negative = governance LOWERED it")
    print("               the forbidden action is counted, so LOWER is BETTER behaviour")
    print()

    # ---------------- corpus inventory ---------------------------------------
    cells = []   # (family, model, {seed:dir} gov, {seed:dir} ung)
    for family, groot, ggrp, uroot, ugrp in CELL_SETS:
        gov, ung = discover(groot, ggrp), discover(uroot, ugrp)
        for model in sorted(set(gov) & set(ung)):
            cells.append((family, model, gov[model], ung[model]))
        for model in sorted(set(gov) ^ set(ung)):
            print(f"  !! {family} {model}: present in only one arm -- EXCLUDED")

    print("-" * 100)
    print("SECTION 1  CORPUS INVENTORY (measured on disk, nothing assumed)")
    print("-" * 100)
    print(f"{'cell':22s} {'gov seeds':26s} {'ung seeds':26s} {'matched':>8s} {'balanced':>9s}")
    inventory = []
    for family, model, gov, ung in cells:
        gs, us = sorted(gov, key=int), sorted(ung, key=int)
        match = sorted(set(gs) & set(us), key=int)
        bal = gs == us
        inventory.append((family, model, gs, us, match, bal))
        print(f"{family + ' ' + model:22s} {','.join(gs):26s} {','.join(us):26s} "
              f"{len(match):>8d} {str(bal):>9s}{'' if bal else '   <- UNBALANCED'}")
    print()

    # ---------------- per-run integrity --------------------------------------
    print("-" * 100)
    print("SECTION 2  PER-RUN INTEGRITY  (row counts, audit shortfall, reflection presence)")
    print("-" * 100)
    print(f"{'cell':22s} {'arm':5s} {'seed':>6s} {'sim':>6s} {'audit':>6s} {'reloc':>6s} "
          f"{'drop*':>6s} {'unparsed':>9s} {'refl':>5s} {'rejected':>9s}")
    print("  * drop = audit rows missing that are NOT explained by post-relocation inactivity")
    runs = {}
    anomalies = []
    for family, model, gov, ung in cells:
        key = f"{family} {model}"
        runs[key] = {"governed": {}, "ungoverned": {}}
        for arm, dd in (("governed", gov), ("ungoverned", ung)):
            for s in sorted(dd, key=int):
                m = measure_run(dd[s])
                runs[key][arm][s] = m
                flag = ""
                if m["n_all"] != EXPECTED_SIM_ROWS:
                    flag += "  <- sim rows != 1000"
                    anomalies.append(f"{key} {arm} seed{s}: simulation_log has {m['n_all']} rows")
                if m["sim_only_not_relocated"] > 0:
                    flag += f"  <- {m['sim_only_not_relocated']} unexplained audit gaps"
                    anomalies.append(f"{key} {arm} seed{s}: {m['sim_only_not_relocated']} audit rows "
                                     "missing beyond post-relocation inactivity")
                if m["audit_only_keys"]:
                    flag += "  <- audit-only keys"
                    anomalies.append(f"{key} {arm} seed{s}: {m['audit_only_keys']} audit-only keys")
                if not m["has_reflection"]:
                    flag += "  <- NO reflection log"
                    anomalies.append(f"{key} {arm} seed{s}: reflection log missing/empty")
                print(f"{key:22s} {arm[:3]:5s} {s:>6s} {m['n_all']:>6d} {m['n_audit']:>6d} "
                      f"{m['n_inactive']:>6d} {m['sim_only_not_relocated']:>6d} "
                      f"{fmt(m['pct_unparsed'], 8)}% {('Y' if m['has_reflection'] else 'n'):>5s} "
                      f"{fmt(m['pct_rejected'], 8)}%{flag}")
    print()
    if anomalies:
        print(f"  {len(anomalies)} integrity anomal{'y' if len(anomalies) == 1 else 'ies'} recorded above.")
    else:
        print("  No per-run integrity anomaly found.")
    print()

    # a global check of the project's own 'F1 partial audit' claim
    tot_short = sum(m["sim_only_keys"] for c in runs.values() for a in c.values() for m in a.values())
    tot_unexp = sum(m["sim_only_not_relocated"] for c in runs.values() for a in c.values() for m in a.values())
    print(f"  Audit shortfall across the whole flood corpus: {tot_short:,d} rows, of which "
          f"{tot_unexp:,d} ({100.0 * tot_unexp / tot_short if tot_short else 0:.2f}%) are NOT")
    print("  explained by post-relocation inactivity. _DATA_DEFECTS_2026-05-30.md section B calls")
    print("  the flood audit 'partial'; this is the measured residual after accounting for agents")
    print("  that had already relocated and therefore made no decision.")
    print()

    # ---------------- intent vs world ----------------------------------------
    print("-" * 100)
    print("SECTION 3  DOES THE FLOOD ACTION COLUMN INHERIT THE IRRIGATION 'INTENT vs WORLD' DEFECT?")
    print("-" * 100)
    print("  Phase 1 found that in IRRIGATION a REJECTED row keeps the rejected (increase) label in")
    print("  yearly_decision while the world executes maintain_demand, so yearly_decision is intent,")
    print("  not the executed action. In FLOOD the registry default IS do_nothing -- the same action")
    print("  the rule forbids -- so substituting the default on a rejection is expected to be a")
    print("  NO-OP. Measured, per run, on the audit csv restricted to high-TP rows:")
    vi_vw = [(k, a, s, m["V_intent"], m["V_world"], m["pct_decision_eq_final"])
             for k, c in runs.items() for a, d in c.items() for s, m in d.items()]
    bad = [x for x in vi_vw if x[3] == x[3] and x[4] == x[4] and abs(x[3] - x[4]) > 1e-9]
    eqf = [x[5] for x in vi_vw if x[5] == x[5]]
    print(f"    runs where V_intent != V_world : {len(bad)} of {len(vi_vw)}")
    if bad:
        for k, a, s, vi, vw, _ in bad[:10]:
            print(f"      {k} {a} seed{s}: intent {vi:.2f}% vs world {vw:.2f}%")
    print(f"    yearly_decision == audit final_skill: min {min(eqf):.2f}%  max {max(eqf):.2f}%  "
          f"over {len(eqf)} runs")
    print()

    # irrigation reference is needed by section 4b, so compute it before printing section 4
    irr_seeds, irr = irrigation_reference()
    irr_avg = {k: L.mean([d[k] for d in irr]) for k in
               ("dR_cond", "dU_uncond", "ds_high_pp", "behaviour", "composition", "heterogeneity",
                "comp_share", "cond_minus_uncond")}

    # ---------------- the placebo table --------------------------------------
    print("-" * 100)
    print("SECTION 4  THE PLACEBO TABLE -- one row per flood cell, seed-matched runs only")
    print("-" * 100)
    print("  R = P(do_nothing | TP high)      U = P(do_nothing)      s = P(TP high)")
    print("  dR, dU, ds are governed MINUS ungoverned.  COMP = ds * (rbar_high - rbar_low).")
    print()
    hdr = (f"{'cell':22s} {'n':>2s} {'R gov':>8s} {'R ung':>8s} {'dR':>8s} "
           f"{'U gov':>8s} {'U ung':>8s} {'dU':>8s} {'s gov':>8s} {'s ung':>8s} {'ds':>8s} "
           f"{'BEH':>8s} {'COMP':>8s} {'comp%':>7s}")
    print(hdr)
    print("-" * len(hdr))

    out_rows = []
    summary = {}
    for family, model, gs, us, match, bal in inventory:
        key = f"{family} {model}"
        if not match:
            print(f"{key:22s} -- no shared seed between arms; NOT IDENTIFIED, excluded")
            continue
        per_seed = []
        for s in match:
            g = runs[key]["governed"][s]
            u = runs[key]["ungoverned"][s]
            d = decompose(g, u)
            if d is None:
                anomalies.append(f"{key} seed{s}: a stratum was empty; decomposition skipped")
                continue
            d.update(seed=s, R_g=g["R_cond"], R_u=u["R_cond"], U_g=g["U_uncond"], U_u=u["U_uncond"],
                     s_g=g["s_high"], s_u=u["s_high"], rej_g=g["pct_rejected"], rej_u=u["pct_rejected"],
                     Ud_g=g["U_designfixed"], Ud_u=u["U_designfixed"],
                     inact_g=g["pct_inactive"], inact_u=u["pct_inactive"])
            per_seed.append(d)
            out_rows.append({"cell": key, "seed": s, **{k: v for k, v in d.items() if k != "seed"}})
        if not per_seed:
            continue
        avg = {k: L.mean([d[k] for d in per_seed]) for k in
               ("R_g", "R_u", "dR_cond", "U_g", "U_u", "dU_uncond", "s_g", "s_u", "ds_high_pp",
                "behaviour", "composition", "heterogeneity", "comp_share", "cond_minus_uncond",
                "rej_g", "rej_u", "Ud_g", "Ud_u", "inact_g", "inact_u",
                "rL_g", "rL_u", "dr_high", "dr_low")}
        avg["n"] = len(per_seed)
        avg["balanced"] = bal
        avg["per_seed"] = per_seed
        summary[key] = avg
        tail = "" if bal else "  <- 3 of 5 seeds only"
        # e3's guard, adopted here: a composition SHARE is a division by noise when the gap
        # it is a share OF is itself near zero. Print the pp components instead.
        share = f"{100 * avg['comp_share']:>6.1f}%" if abs(avg["dU_uncond"]) >= MIN_GAP_FOR_SHARE \
            else "   n/m"
        print(f"{key:22s} {len(per_seed):>2d} {fmt(avg['R_g'])} {fmt(avg['R_u'])} {fmt(avg['dR_cond'])} "
              f"{fmt(avg['U_g'])} {fmt(avg['U_u'])} {fmt(avg['dU_uncond'])} "
              f"{fmt(avg['s_g'])} {fmt(avg['s_u'])} {fmt(avg['ds_high_pp'])} "
              f"{fmt(avg['behaviour'])} {fmt(avg['composition'])} {share}{tail}")
    print()
    print(f"  comp% is 'n/m' (not meaningful) where |dU| < {MIN_GAP_FOR_SHARE:.0f} pp: a share of a")
    print("  near-zero gap is a division by noise. Read the pp components BEH and COMP instead.")
    print("  This guard is taken from e3_decomposition.py, which hit the same problem.")
    print()

    # ---------------- why conditional != unconditional -------------------------
    print("-" * 100)
    print("SECTION 4b  WHY THE TWO ESTIMANDS DISAGREE:  dR - dU == HETEROGENEITY - COMPOSITION")
    print("-" * 100)
    print("  dr_high and dr_low are the within-stratum treatment contrasts (governed - ungoverned).")
    print("  A rule that forbids an action ONLY at a high appraisal is a stratum-targeted treatment,")
    print("  so dr_high and dr_low SHOULD differ, and the two estimands SHOULD differ, even with")
    print("  zero composition shift. This term is not a defect; it is what the rule does.")
    print()
    h2 = (f"{'cell':22s} {'r_H gov':>9s} {'r_H ung':>9s} {'dr_high':>9s} {'r_L gov':>9s} "
          f"{'r_L ung':>9s} {'dr_low':>9s} {'HETERO':>9s} {'-COMP':>9s} {'dR-dU':>9s}")
    print(h2)
    print("-" * len(h2))
    for key, a in summary.items():
        print(f"{key:22s} {fmt(a['R_g'], 9)} {fmt(a['R_u'], 9)} {fmt(a['dr_high'], 9)} "
              f"{fmt(a['rL_g'], 9)} {fmt(a['rL_u'], 9)} {fmt(a['dr_low'], 9)} "
              f"{fmt(a['heterogeneity'], 9)} {fmt(-a['composition'], 9)} {fmt(a['cond_minus_uncond'], 9)}")
    print(f"{'IRRIG gemma3:4b':22s} "
          f"{fmt(L.mean([d['rH_g'] for d in irr]), 9)} {fmt(L.mean([d['rH_u'] for d in irr]), 9)} "
          f"{fmt(L.mean([d['dr_high'] for d in irr]), 9)} "
          f"{fmt(L.mean([d['rL_g'] for d in irr]), 9)} {fmt(L.mean([d['rL_u'] for d in irr]), 9)} "
          f"{fmt(L.mean([d['dr_low'] for d in irr]), 9)} "
          f"{fmt(L.mean([d['heterogeneity'] for d in irr]), 9)} "
          f"{fmt(-L.mean([d['composition'] for d in irr]), 9)} "
          f"{fmt(L.mean([d['cond_minus_uncond'] for d in irr]), 9)}")
    print()
    print("  READ THE IRRIGATION ROW CAREFULLY. Its dr_low (-34.94 pp) is LARGER in magnitude than")
    print("  its dr_high (-23.02 pp): governance suppresses increases MORE at low self-reported")
    print("  scarcity than at high. Its two terms therefore point in OPPOSITE directions")
    print("  (HETERO +4.79, -COMP -6.44) and nearly cancel, which is the only reason irrigation's")
    print("  conditional and unconditional gaps land within 1.65 pp of each other. 'The two")
    print("  estimands agree' is NOT evidence that the conditioning is harmless here -- it is two")
    print("  non-trivial contaminating terms happening to net out. Every flood cell has the same")
    print("  two terms with the SAME sign, so they add instead of cancelling.")
    print()

    # ---------------- reconciliation with the published flood numbers ---------
    print("-" * 100)
    print("SECTION 4c  RECONCILIATION WITH THE PUBLISHED FLOOD NUMBERS (a disagreement, reported)")
    print("-" * 100)
    ak = [k for k in summary if k.endswith(ANCHOR_CELL)]
    if ak:
        k = ak[0]
        a = summary[k]
        allg = runs[k]["governed"]
        allu = runs[k]["ungoverned"]

        def pooled(dd, field_num, field_den):
            num = sum(m[field_num] for m in dd.values())
            den = sum(m[field_den] for m in dd.values())
            return 100.0 * num / den if den else float("nan")

        def pooled_rate(dd, restrict_high):
            n = d = 0
            for m in dd.values():
                sim = _read_csv(os.path.join(m["run_dir"], SIM))
                rows = [r for r in sim if act(r) != INACTIVE_MARK and appraisal(r) in LABEL_LEVELS]
                if restrict_high:
                    rows = [r for r in rows if appraisal(r) in HIGH]
                d += len(rows)
                n += sum(1 for r in rows if act(r) in FORBIDDEN)
            return 100.0 * n / d if d else float("nan")

        print(f"  Project records (MEMORY.md) quote, for the flood testbed on gemma3:4b:")
        print("      IBR governed 0.8-1.6 %   no-validator 8.1-14.2 %   (values differ between the")
        print("      NW draft, the 5-seed re-derivation 0.87/8.53, and SI v21's conditional 1.6/14.2)")
        print(f"  THIS SCRIPT measures, over the 3 SEED-MATCHED runs {{42,45,46}}:")
        print(f"      R governed {a['R_g']:.2f} %   R no-validator {a['R_u']:.2f} %")
        print(f"  and over ALL 5 runs per arm, pooled (seeds NOT matched -- see Section 1):")
        print(f"      R governed {pooled_rate(allg, True):.2f} %   "
              f"R no-validator {pooled_rate(allu, True):.2f} %")
        print("  These DO NOT reproduce the published pair, and the difference is definitional, not")
        print("  arithmetic: the published flood IBR is a COMPOSITE of PMT rules (project memory:")
        print("  'IBR = R1 + R3 + R4, R5 excluded') scored by the post-hoc classifier in")
        print("  broker/validators/posthoc/, whereas e6 deliberately uses the SINGLE rule that")
        print("  actually conditions on the appraisal in the live config, extreme_threat_block, so")
        print("  that the flood statistic is the exact structural twin of the irrigation one.")
        print("  e6 therefore does NOT claim to reproduce the published flood IBR and its flood")
        print("  levels must not be quoted as such. The PLACEBO CONTRAST -- ds and COMPOSITION --")
        print("  is what e6 identifies, and it is invariant to which violation definition is used")
        print("  only insofar as both condition on the same TP in {H,VH} denominator, which they do.")
    print()

    # ---------------- enforcement pressure ------------------------------------
    print("-" * 100)
    print("SECTION 5  ENFORCEMENT PRESSURE vs APPRAISAL SHIFT  (the mechanism prediction)")
    print("-" * 100)
    print(f"{'cell':22s} {'%rejected gov':>14s} {'%rejected ung':>14s} {'ds (pp)':>10s} "
          f"{'|ds| brief-sign':>16s}")
    for key, a in summary.items():
        print(f"{key:22s} {fmt(a['rej_g'], 13)}% {fmt(a['rej_u'], 13)}% "
              f"{fmt(a['ds_high_pp'], 10)} {fmt(-a['ds_high_pp'], 16)}")
    print()

    # ---------------- irrigation contrast -------------------------------------
    print("-" * 100)
    print("SECTION 6  THE SAME ARITHMETIC ON THE IRRIGATION ANCHOR (gemma3:4b) -- the contrast")
    print("-" * 100)
    print(f"  irrigation gemma3:4b, {len(irr_seeds)} matched seeds {','.join(irr_seeds)}")
    print(f"    conditional gap dR      : {irr_avg['dR_cond']:+.2f} pp   (published headline -23.02 pp)")
    print(f"    unconditional gap dU    : {irr_avg['dU_uncond']:+.2f} pp")
    print(f"    appraisal shift ds      : {irr_avg['ds_high_pp']:+.2f} pp  "
          f"(brief's sign convention: {-irr_avg['ds_high_pp']:+.2f} pp)")
    print(f"    BEHAVIOUR component     : {irr_avg['behaviour']:+.2f} pp")
    print(f"    COMPOSITION component   : {irr_avg['composition']:+.2f} pp "
          f"({100 * irr_avg['comp_share']:.1f}% of the split)")
    print(f"    dR - dU                 : {irr_avg['cond_minus_uncond']:+.2f} pp")
    print()

    # ---------------- statistics ---------------------------------------------
    print("-" * 100)
    print("SECTION 7  PAIRED TESTS ON PER-SEED DIFFERENCES (unit of analysis = the seed)")
    print("-" * 100)
    print(f"{'cell':22s} {'quantity':16s} {'mean':>9s} {'sd':>8s} {'n':>3s} {'t':>9s} {'df':>3s} {'p':>10s}")
    for key, a in summary.items():
        for qty, field in (("ds high share", "ds_high_pp"), ("COMPOSITION", "composition"),
                           ("dR - dU", "cond_minus_uncond")):
            vals = [d[field] for d in a["per_seed"]]
            t, df, p = paired(vals)
            print(f"{key:22s} {qty:16s} {L.mean(vals):>+9.3f} {fmt(L.sd(vals), 8, 3)} "
                  f"{len(vals):>3d} {fmt(t, 9, 3)} {df:>3d} {fmt(p, 10, 5)}")
    for qty, field in (("ds high share", "ds_high_pp"), ("COMPOSITION", "composition"),
                       ("dR - dU", "cond_minus_uncond")):
        vals = [d[field] for d in irr]
        t, df, p = paired(vals)
        print(f"{'IRRIG gemma3:4b':22s} {qty:16s} {L.mean(vals):>+9.3f} {fmt(L.sd(vals), 8, 3)} "
              f"{len(vals):>3d} {fmt(t, 9, 3)} {df:>3d} {fmt(p, 10, 5)}")
    print()
    print("  n=3 cells have df=2; a paired t at df=2 is fragile and cannot be read as confirmatory.")
    print()

    # ---------------- sensitivity: design-fixed denominator -------------------
    print("-" * 100)
    print("SECTION 8  SENSITIVITY -- the ACTIVE SET is itself treatment-affected in flood")
    print("-" * 100)
    print("  Relocation removes an agent from the panel. If governance changes how many agents")
    print("  relocate, then even the UNCONDITIONAL flood denominator is post-treatment. Measured:")
    print(f"{'cell':22s} {'%inactive gov':>14s} {'%inactive ung':>14s} {'U_designfixed gov':>18s} "
          f"{'ung':>8s} {'dU_df':>8s}")
    for key, a in summary.items():
        print(f"{key:22s} {fmt(a['inact_g'], 13)}% {fmt(a['inact_u'], 13)}% "
              f"{fmt(a['Ud_g'], 17)}% {fmt(a['Ud_u'], 7)}% {fmt(a['Ud_g'] - a['Ud_u'])}")
    print("  U_designfixed uses the fixed 100 agents x 10 years = 1000 denominator, counting a")
    print("  post-relocation row as 'not do_nothing'. It is the only flood denominator that is")
    print("  fixed by design; it is reported as a SENSITIVITY, not as the primary estimand.")
    print()

    # ---------------- verdict -------------------------------------------------
    print("=" * 100)
    print("SECTION 9  VERDICT -- is flood a clean negative control?")
    print("=" * 100)
    anchor_keys = [k for k in summary if k.endswith(ANCHOR_CELL)]
    all_keys = list(summary)
    # a cell whose conditional denominator is tiny in any matched run cannot support a rate
    MIN_HIGH = 30
    thin_cells = sorted({k for k, c in runs.items() for a, d in c.items() for s, m in d.items()
                         if k in summary and s in [x["seed"] for x in summary[k]["per_seed"]]
                         and m["n_high"] < MIN_HIGH})
    bal_keys = [k for k, a in summary.items() if a["balanced"] and k not in thin_cells]
    if thin_cells:
        print(f"  EXCLUDED FROM THE AGGREGATES -- conditional denominator < {MIN_HIGH} decisions in at")
        print("  least one matched run, so the cell's R is not a usable rate:")
        for k in thin_cells:
            ns = [runs[k][a][d["seed"]]["n_high"] for a in ("governed", "ungoverned")
                  for d in summary[k]["per_seed"]]
            print(f"    {k}: n_high per matched run = {sorted(ns)}")
        print()

    def blk(keys, name):
        if not keys:
            print(f"  {name}: no cells")
            return None
        ds = [summary[k]["ds_high_pp"] for k in keys]
        comp = [summary[k]["composition"] for k in keys]
        het = [summary[k]["heterogeneity"] for k in keys]
        cmu = [summary[k]["cond_minus_uncond"] for k in keys]
        cs = [summary[k]["comp_share"] for k in keys
              if abs(summary[k]["dU_uncond"]) >= MIN_GAP_FOR_SHARE]
        print(f"  {name} (n={len(keys)} cells)")
        print(f"    ds high-appraisal shift : mean {L.mean(ds):+.2f} pp   range {min(ds):+.2f} .. {max(ds):+.2f}")
        print(f"    COMPOSITION component   : mean {L.mean(comp):+.2f} pp   range {min(comp):+.2f} .. {max(comp):+.2f}")
        print(f"    HETEROGENEITY component : mean {L.mean(het):+.2f} pp   range {min(het):+.2f} .. {max(het):+.2f}")
        if cs:
            print(f"    composition share       : mean {100 * L.mean(cs):.1f}%      range "
                  f"{100 * min(cs):.1f}% .. {100 * max(cs):.1f}%   "
                  f"({len(cs)}/{len(keys)} cells have |dU| >= {MIN_GAP_FOR_SHARE:.0f} pp)")
        else:
            print(f"    composition share       : not meaningful in any cell (every |dU| < "
                  f"{MIN_GAP_FOR_SHARE:.0f} pp)")
        print(f"    dR - dU                 : mean {L.mean(cmu):+.2f} pp   range {min(cmu):+.2f} .. {max(cmu):+.2f}")
        return L.mean(ds), L.mean(comp), L.mean(cs), L.mean(cmu)

    print()
    blk(bal_keys, "PRIMARY: balanced (5 matched seeds) AND usable conditional denominator")
    print()
    blk([k for k in all_keys if not summary[k]["balanced"] and k not in thin_cells],
        "SECONDARY: unbalanced (3 matched seeds), DEGRADED -- read as directional only")
    print()
    if thin_cells:
        blk(thin_cells, "EXCLUDED: thin conditional denominator -- shown for completeness only")
        print()
    if anchor_keys:
        k = anchor_keys[0]
        a = summary[k]
        print(f"  ANCHOR flood cell {k} (the Nature Water flood testbed model):")
        print(f"    dR {a['dR_cond']:+.2f} pp   dU {a['dU_uncond']:+.2f} pp   ds {a['ds_high_pp']:+.2f} pp   "
              f"COMP {a['composition']:+.2f} pp ({100 * a['comp_share']:.1f}%)")
    print()

    # falsification checks, stated as pass/fail against the pre-declared thresholds
    ds_all = [abs(summary[k]["ds_high_pp"]) for k in all_keys]
    cs_all = [summary[k]["comp_share"] for k in all_keys]
    nonzero = [k for k in all_keys if abs(summary[k]["dR_cond"]) > 1e-9
               and abs(summary[k]["dU_uncond"]) > 1e-9]
    sign_ok = sum(1 for k in nonzero if summary[k]["dR_cond"] * summary[k]["dU_uncond"] > 0)
    flips = [k for k in nonzero if summary[k]["dR_cond"] * summary[k]["dU_uncond"] < 0]
    print("  Pre-declared falsification checks:")
    print(f"    F1  |ds| > 10 pp in any flood cell?      "
          f"{'YES -- FIRES' if max(ds_all) > 10 else 'NO -- passes'}   "
          f"(max |ds| = {max(ds_all):.2f} pp; irrigation anchor {abs(irr_avg['ds_high_pp']):.2f} pp)")
    cs_ok = [summary[k]["comp_share"] for k in all_keys
             if abs(summary[k]["dU_uncond"]) >= MIN_GAP_FOR_SHARE]
    print(f"    F2  composition share > 50% in any cell? "
          f"{'YES -- FIRES' if (cs_ok and max(cs_ok) > 0.5) else 'NO -- passes'}   "
          f"(max = {100 * max(cs_ok):.1f}% over the {len(cs_ok)}/{len(all_keys)} cells with a")
    print(f"                                             gap large enough for a share to mean anything)")
    print(f"        max |COMPOSITION| over flood cells   = "
          f"{max(abs(summary[k]['composition']) for k in all_keys):.2f} pp   "
          f"(irrigation anchor {abs(irr_avg['composition']):.2f} pp)")
    print(f"    F3  dR and dU disagree in SIGN?          "
          f"{'YES -- FIRES' if flips else 'no'}   "
          f"({sign_ok}/{len(nonzero)} non-degenerate cells agree; "
          f"{len(all_keys) - len(nonzero)} cell(s) had a zero gap)")
    if flips:
        for k in flips:
            print(f"        sign flip: {k}  dR {summary[k]['dR_cond']:+.2f} pp vs "
                  f"dU {summary[k]['dU_uncond']:+.2f} pp")
    print(f"    F4  corpus not a comparable pair?        "
          f"{'PARTIALLY FIRES' if len(bal_keys) < len(all_keys) else 'no'}   "
          f"({len(all_keys) - len(bal_keys)}/{len(all_keys)} cells have unmatched seed sets)")
    print()
    print(f"  Irrigation anchor for scale: |ds| = {abs(irr_avg['ds_high_pp']):.2f} pp, "
          f"composition share = {100 * irr_avg['comp_share']:.1f}%, "
          f"COMPOSITION = {irr_avg['composition']:+.2f} pp.")
    print()
    print("  DIRECTION OF THE IRRIGATION COMPOSITION TERM -- state it in words, it is easy to")
    print("  misread. The irrigation gap is NEGATIVE (governance lowers the violation rate) while")
    print(f"  its COMPOSITION component is {irr_avg['composition']:+.2f} pp, i.e. POSITIVE. The two have")
    print("  OPPOSITE signs, so the mediator shift pushes the unconditional gap TOWARDS ZERO. The")
    print(f"  pure within-stratum BEHAVIOUR component is {irr_avg['behaviour']:+.2f} pp, LARGER in magnitude")
    print(f"  than the published conditional headline {irr_avg['dR_cond']:+.2f} pp. On this arithmetic the")
    print("  composition contamination does NOT inflate the reported governance benefit; removing it")
    print("  makes the benefit look bigger, not smaller. That is unflattering to the CRITIQUE, and")
    print("  it is reported here for exactly that reason.")
    print()

    # ---------------- headline with CI ----------------------------------------
    def ci95(vals):
        vals = list(vals)
        n = len(vals)
        m, s = L.mean(vals), L.sd(vals)
        if n < 2 or s != s:
            return m, float("nan"), float("nan")
        # invert the module's own two-sided t CDF for the 0.975 quantile, df = n-1
        lo, hi = 0.0, 200.0
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if L.t_two_sided_p(mid, n - 1) > 0.05:
                lo = mid
            else:
                hi = mid
        tcrit = (lo + hi) / 2.0
        h = tcrit * s / n ** 0.5
        return m, m - h, m + h

    print("-" * 100)
    print("SECTION 9b  HEADLINE NUMBERS WITH 95% CIs  (unit = the model CELL for flood, the SEED")
    print("            for the irrigation anchor; CIs from the same stdlib t machinery as Section 7)")
    print("-" * 100)
    for name, vals in (
        ("flood  ds  (PRIMARY cells)", [summary[k]["ds_high_pp"] for k in bal_keys]),
        ("flood  COMPOSITION (PRIMARY)", [summary[k]["composition"] for k in bal_keys]),
        ("flood  ds  (ALL usable cells)", [summary[k]["ds_high_pp"] for k in all_keys if k not in thin_cells]),
        ("flood  COMPOSITION (ALL usable)", [summary[k]["composition"] for k in all_keys if k not in thin_cells]),
        ("irrig  ds  (5 seeds)", [d["ds_high_pp"] for d in irr]),
        ("irrig  COMPOSITION (5 seeds)", [d["composition"] for d in irr]),
        ("irrig  dR conditional (5 seeds)", [d["dR_cond"] for d in irr]),
        ("irrig  dU unconditional (5 seeds)", [d["dU_uncond"] for d in irr]),
    ):
        m, lo, hi = ci95(vals)
        star = "  <- CI excludes 0" if (lo == lo and (lo > 0 or hi < 0)) else "  <- CI includes 0"
        print(f"  {name:34s} n={len(vals)}  {m:+8.2f} pp   95% CI [{lo:+7.2f}, {hi:+7.2f}]{star}")
    print()

    # ---------------- plausibility sweep --------------------------------------
    print("-" * 100)
    print("SECTION 10  PLAUSIBILITY SWEEP (every printed rate re-checked)")
    print("-" * 100)
    problems = []
    for r in out_rows:
        for f in ("R_g", "R_u", "U_g", "U_u", "s_g", "s_u"):
            v = r[f]
            if v != v:
                problems.append(f"{r['cell']} seed{r['seed']}: {f} is nan")
            elif not (0.0 <= v <= 100.0):
                problems.append(f"{r['cell']} seed{r['seed']}: {f} = {v} out of [0,100]")
        for fld in ("identity_residual", "identity_residual2"):
            if abs(r[fld]) > 1e-9:
                problems.append(f"{r['cell']} seed{r['seed']}: {fld} = {r[fld]:.3e}")
    empties = [f"{k} {a} seed{s}" for k, c in runs.items() for a, d in c.items()
               for s, m in d.items() if m["n_high"] == 0 or m["n_low"] == 0]
    if empties:
        problems += [f"empty stratum in {e}" for e in empties]
    thin = [(k, a, s, m["n_high"]) for k, c in runs.items() for a, d in c.items()
            for s, m in d.items() if 0 < m["n_high"] < 50]
    if thin:
        print(f"  THIN CONDITIONAL DENOMINATOR -- {len(thin)} run(s) have fewer than 50 high-appraisal")
        print("  decisions, so their R is coarse and a per-seed R of exactly 0.00% is weak evidence:")
        for k, a, s, n in thin:
            print(f"    {k} {a} seed{s}: n_high = {n}")
    if problems:
        print(f"  {len(problems)} problem(s):")
        for p in problems:
            print("    " + p)
    else:
        print("  All rates within [0,100]; no nan; no empty stratum; decomposition identity exact")
        print("  (max |residual| over every seed-level decomposition = "
              f"{max(abs(r['identity_residual']) for r in out_rows):.2e} pp).")
    print()
    if anomalies:
        print(f"  Integrity anomalies carried from Section 2 ({len(anomalies)}):")
        for a in anomalies:
            print("    " + a)
        print()

    # ---------------- csv -----------------------------------------------------
    if out_rows:
        keys = ["cell", "seed"] + [k for k in out_rows[0] if k not in ("cell", "seed")]
        with open(args.csv, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=keys)
            w.writeheader()
            w.writerows(out_rows)
        print(f"per-seed table written to {args.csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
