#!/usr/bin/env python
"""
Cross-Layer Analysis: Constructs x Reasoning x Memory in Flood ABM
-------------------------------------------------------------------
Analyses:
  1. Do construct labels (SP, PA) match reasoning text?
  2. Do memory contents align with construct changes?
  3. Construct change -> proposal change (chi-squared)?
  4. Surprising patterns (informed-but-inactive, distrust-but-insured)

Pools across seeds 42, 123, 456.
"""

import json, csv, re, os, sys
from collections import Counter, defaultdict
from pathlib import Path
import warnings
warnings.filterwarnings("ignore")

_PAPER3_OVERRIDE = os.environ.get("PAPER3_TRACE_DIR")
_PAPER3_OUTPUT_OVERRIDE = os.environ.get("PAPER3_OUTPUT_DIR")

# ---------- paths ----------------------------------------------------------
if _PAPER3_OVERRIDE:
    _TRACE_DIR = Path(os.path.normpath(_PAPER3_OVERRIDE))
    BASE = _TRACE_DIR.parent.parent
    SEEDS = [int(_TRACE_DIR.parent.name.replace("seed_", ""))]
    MODEL = _TRACE_DIR.name
else:
    BASE = Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
                r"\examples\multi_agent\flood\paper3\results\paper3_hybrid_v2")
    SEEDS = [42, 123, 456]
    MODEL = "gemma3_4b_strict"
AGENT_TYPES = ["household_owner", "household_renter"]
OUT_DIR = Path(os.path.normpath(_PAPER3_OUTPUT_OVERRIDE)) if _PAPER3_OUTPUT_OVERRIDE else Path(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
               r"\examples\multi_agent\flood\paper3\analysis\tables")

# ---------- keyword sets ---------------------------------------------------
INST_KW = re.compile(
    r"government|subsidy|fema|nfip|insurance\s+program|grant|support|policy|crs|discount|blue\s*acres|njdep",
    re.I)
DISTRUST_KW = re.compile(
    r"no\s+help|don.?t\s+trust|government\s+won.?t|on\s+my\s+own|no\s+support|abandoned|inadequate|insufficient|lack\s+of|distrust|skeptic|doubt",
    re.I)
PA_HIGH_KW = re.compile(
    r"community|home|family|belong|roots|neighborhood|memories|attachment|ties|heritage|generations|loved|tradition",
    re.I)
PA_LOW_KW = re.compile(
    r"want\s+to\s+leave|move\s+away|relocat|new\s+start|elsewhere|no\s+ties|leave\s+area|fresh\s+start|detach|uprooted",
    re.I)

MEM_INST_KW = re.compile(
    r"subsid|insurance|government|approved|fema|nfip|crs|discount|grant|program|blue\s*acres",
    re.I)
MEM_REJECT_KW = re.compile(
    r"reject|denied|blocked|cannot\s+afford|failed|damage|loss|unafford|too\s+expensive|insufficient",
    re.I)

# ---------- load traces + audit CSV ----------------------------------------
def load_traces():
    """Return list of dicts with unified fields."""
    records = []
    for seed in SEEDS:
        for at in AGENT_TYPES:
            jpath = BASE / f"seed_{seed}" / MODEL / "raw" / f"{at}_traces.jsonl"
            if not jpath.exists():
                print(f"  WARN: missing {jpath}")
                continue
            with open(jpath, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    sp = d.get("skill_proposal") or {}
                    reasoning_dict = sp.get("reasoning") or {}

                    # Construct labels from reasoning dict
                    sp_label = reasoning_dict.get("SP_LABEL", "")
                    pa_label = reasoning_dict.get("PA_LABEL", "")
                    tp_label = reasoning_dict.get("TP_LABEL", "")
                    cp_label = reasoning_dict.get("CP_LABEL", "")

                    # Reasoning text fields
                    sp_reason = reasoning_dict.get("SP_REASON", "")
                    pa_reason = reasoning_dict.get("PA_REASON", "")
                    tp_reason = reasoning_dict.get("TP_REASON", "")
                    main_reasoning = reasoning_dict.get("reasoning", "")

                    # Full raw output as fallback
                    raw = d.get("raw_output", "")

                    # Memory
                    mem_pre = d.get("memory_pre", [])
                    mem_audit = d.get("memory_audit", {})

                    # Skill
                    skill_name = sp.get("skill_name", "")
                    outcome = d.get("outcome", "")

                    records.append({
                        "seed": seed,
                        "agent_type": at,
                        "agent_id": d.get("agent_id", ""),
                        "year": d.get("year", 0),
                        "sp_label": sp_label.strip().upper() if sp_label else "",
                        "pa_label": pa_label.strip().upper() if pa_label else "",
                        "tp_label": tp_label.strip().upper() if tp_label else "",
                        "cp_label": cp_label.strip().upper() if cp_label else "",
                        "sp_reason": sp_reason or "",
                        "pa_reason": pa_reason or "",
                        "tp_reason": tp_reason or "",
                        "main_reasoning": main_reasoning or "",
                        "raw_output": raw,
                        "mem_pre": mem_pre,
                        "mem_audit": mem_audit,
                        "skill_name": skill_name,
                        "outcome": outcome,
                    })
    return records


def pct(n, d):
    return f"{100*n/d:.1f}%" if d else "N/A"


def search_text(text, pattern):
    return bool(pattern.search(text)) if text else False


# ======================================================================
# ANALYSIS 1: Do Constructs Match Reasoning Text?
# ======================================================================
def analysis_1(records):
    print("=" * 72)
    print("ANALYSIS 1: Do Construct Labels Match Reasoning Text?")
    print("=" * 72)

    results_rows = []

    # ---- SP analysis ----
    sp_groups = {"H": [], "M": [], "L": []}
    for r in records:
        lab = r["sp_label"]
        if lab in sp_groups:
            # Combine SP reason + main reasoning + raw output for thorough search
            combined = " ".join([r["sp_reason"], r["main_reasoning"], r["raw_output"]])
            sp_groups[lab].append(combined)

    print("\n--- SP (Stakeholder Perception) x Institutional Keywords ---")
    for lab in ["H", "M", "L"]:
        texts = sp_groups[lab]
        n = len(texts)
        n_inst = sum(1 for t in texts if search_text(t, INST_KW))
        n_dist = sum(1 for t in texts if search_text(t, DISTRUST_KW))
        print(f"  SP={lab}: N={n}, institutional mention={pct(n_inst, n)} ({n_inst}/{n}), "
              f"distrust mention={pct(n_dist, n)} ({n_dist}/{n})")
        results_rows.append({
            "analysis": "A1_SP_institutional",
            "group": f"SP={lab}",
            "N": n,
            "pct_institutional": pct(n_inst, n),
            "n_institutional": n_inst,
            "pct_distrust": pct(n_dist, n),
            "n_distrust": n_dist,
        })

    # Gradient test
    rates = {}
    for lab in ["H", "M", "L"]:
        n = len(sp_groups[lab])
        if n:
            rates[lab] = sum(1 for t in sp_groups[lab] if search_text(t, INST_KW)) / n
        else:
            rates[lab] = 0
    gradient = rates.get("H", 0) > rates.get("M", 0) > rates.get("L", 0)
    print(f"\n  Gradient test (H > M > L for institutional mentions): "
          f"{'YES — construct is grounded' if gradient else 'NO — no clear gradient'}")
    print(f"    H={rates.get('H',0):.3f}, M={rates.get('M',0):.3f}, L={rates.get('L',0):.3f}")

    # ---- PA analysis ----
    pa_groups = {"H": [], "M": [], "L": []}
    for r in records:
        lab = r["pa_label"]
        if lab in pa_groups:
            combined = " ".join([r["pa_reason"], r["main_reasoning"], r["raw_output"]])
            pa_groups[lab].append(combined)

    print("\n--- PA (Place Attachment) x Attachment/Relocation Keywords ---")
    for lab in ["H", "M", "L"]:
        texts = pa_groups[lab]
        n = len(texts)
        n_high = sum(1 for t in texts if search_text(t, PA_HIGH_KW))
        n_low = sum(1 for t in texts if search_text(t, PA_LOW_KW))
        print(f"  PA={lab}: N={n}, attachment keywords={pct(n_high, n)} ({n_high}/{n}), "
              f"detachment keywords={pct(n_low, n)} ({n_low}/{n})")
        results_rows.append({
            "analysis": "A1_PA_attachment",
            "group": f"PA={lab}",
            "N": n,
            "pct_institutional": pct(n_high, n),
            "n_institutional": n_high,
            "pct_distrust": pct(n_low, n),
            "n_distrust": n_low,
        })

    pa_rates_high = {}
    pa_rates_low = {}
    for lab in ["H", "M", "L"]:
        n = len(pa_groups[lab])
        if n:
            pa_rates_high[lab] = sum(1 for t in pa_groups[lab] if search_text(t, PA_HIGH_KW)) / n
            pa_rates_low[lab] = sum(1 for t in pa_groups[lab] if search_text(t, PA_LOW_KW)) / n
        else:
            pa_rates_high[lab] = pa_rates_low[lab] = 0
    gradient_pa_h = pa_rates_high.get("H",0) > pa_rates_high.get("M",0) > pa_rates_high.get("L",0)
    gradient_pa_l = pa_rates_low.get("L",0) > pa_rates_low.get("M",0) > pa_rates_low.get("H",0)
    print(f"\n  Gradient test (attachment kw: H > M > L): "
          f"{'YES' if gradient_pa_h else 'NO'}")
    print(f"    H={pa_rates_high.get('H',0):.3f}, M={pa_rates_high.get('M',0):.3f}, L={pa_rates_high.get('L',0):.3f}")
    print(f"  Gradient test (detachment kw: L > M > H): "
          f"{'YES' if gradient_pa_l else 'NO'}")
    print(f"    L={pa_rates_low.get('L',0):.3f}, M={pa_rates_low.get('M',0):.3f}, H={pa_rates_low.get('H',0):.3f}")

    return results_rows


# ======================================================================
# ANALYSIS 2: Do Memory Contents Align with Construct Changes?
# ======================================================================
def analysis_2(records):
    print("\n" + "=" * 72)
    print("ANALYSIS 2: Memory Contents x Construct Changes")
    print("=" * 72)

    results_rows = []

    # Build per-agent timeseries: (seed, agent_id) -> sorted by year
    agent_ts = defaultdict(list)
    for r in records:
        key = (r["seed"], r["agent_id"])
        agent_ts[key].append(r)
    for k in agent_ts:
        agent_ts[k].sort(key=lambda x: x["year"])

    # SP transitions
    sp_up_mems = []    # list of memory lists
    sp_down_mems = []
    sp_same_mems = []

    sp_order = {"L": 0, "M": 1, "H": 2}

    for key, ts in agent_ts.items():
        for i in range(1, len(ts)):
            prev_sp = ts[i-1]["sp_label"]
            curr_sp = ts[i]["sp_label"]
            if prev_sp not in sp_order or curr_sp not in sp_order:
                continue
            mems = ts[i]["mem_pre"]
            mem_text = " ".join(mems) if isinstance(mems, list) else str(mems)

            if sp_order[curr_sp] > sp_order[prev_sp]:
                sp_up_mems.append(mem_text)
            elif sp_order[curr_sp] < sp_order[prev_sp]:
                sp_down_mems.append(mem_text)
            else:
                sp_same_mems.append(mem_text)

    print("\n--- SP Transitions and Memory Content ---")
    for label, mems, desc in [
        ("SP_UP", sp_up_mems, "SP increased (L->M, M->H)"),
        ("SP_DOWN", sp_down_mems, "SP decreased (H->M, M->L)"),
        ("SP_SAME", sp_same_mems, "SP stayed same"),
    ]:
        n = len(mems)
        n_inst = sum(1 for m in mems if search_text(m, MEM_INST_KW))
        n_rej = sum(1 for m in mems if search_text(m, MEM_REJECT_KW))
        n_any = sum(1 for m in mems if m.strip())
        print(f"  {desc}: N={n}")
        print(f"    With any memory: {pct(n_any, n)} ({n_any}/{n})")
        print(f"    Institutional memory: {pct(n_inst, n)} ({n_inst}/{n})")
        print(f"    Rejection/failure memory: {pct(n_rej, n)} ({n_rej}/{n})")
        results_rows.append({
            "analysis": "A2_memory_SP",
            "group": label,
            "N": n,
            "n_with_memory": n_any,
            "pct_institutional_mem": pct(n_inst, n),
            "n_institutional_mem": n_inst,
            "pct_rejection_mem": pct(n_rej, n),
            "n_rejection_mem": n_rej,
        })

    # Key question
    up_inst_rate = sum(1 for m in sp_up_mems if search_text(m, MEM_INST_KW)) / max(len(sp_up_mems),1)
    down_rej_rate = sum(1 for m in sp_down_mems if search_text(m, MEM_REJECT_KW)) / max(len(sp_down_mems),1)
    same_inst_rate = sum(1 for m in sp_same_mems if search_text(m, MEM_INST_KW)) / max(len(sp_same_mems),1)
    print(f"\n  KEY: SP-up institutional mem rate={up_inst_rate:.3f} vs SP-same={same_inst_rate:.3f}")
    print(f"  KEY: SP-down rejection mem rate={down_rej_rate:.3f}")

    return results_rows


# ======================================================================
# ANALYSIS 3: Construct Change -> Proposal Change?
# ======================================================================
def analysis_3(records):
    print("\n" + "=" * 72)
    print("ANALYSIS 3: Construct Change -> Proposal Change (Chi-squared)")
    print("=" * 72)

    results_rows = []

    PROTECTIVE = {"elevate_house", "buy_insurance", "buy_flood_insurance",
                  "purchase_insurance", "relocate", "relocate_out",
                  "relocate_within", "buyout", "apply_buyout",
                  "buy_contents_insurance", "emergency_preparedness"}
    DO_NOTHING = {"do_nothing", "maintain_status_quo", "no_action"}

    def is_protective(s):
        s = s.lower().strip()
        return s in PROTECTIVE or "insur" in s or "elevat" in s or "relocat" in s or "buyout" in s

    def is_do_nothing(s):
        s = s.lower().strip()
        return s in DO_NOTHING or "do_nothing" in s or "nothing" in s

    sp_order = {"L": 0, "M": 1, "H": 2}

    # Build per-agent timeseries
    agent_ts = defaultdict(list)
    for r in records:
        key = (r["seed"], r["agent_id"])
        agent_ts[key].append(r)
    for k in agent_ts:
        agent_ts[k].sort(key=lambda x: x["year"])

    # Track transitions
    sp_up_to_protect = 0
    sp_up_stay_nothing = 0
    sp_up_other = 0
    sp_same_to_protect = 0
    sp_same_stay_nothing = 0
    sp_same_other = 0
    sp_down_to_nothing = 0
    sp_down_stay_protect = 0
    sp_down_other = 0

    sp_up_actions = Counter()
    sp_down_actions = Counter()
    sp_same_actions = Counter()

    for key, ts in agent_ts.items():
        for i in range(1, len(ts)):
            prev_sp = ts[i-1]["sp_label"]
            curr_sp = ts[i]["sp_label"]
            prev_skill = ts[i-1]["skill_name"]
            curr_skill = ts[i]["skill_name"]

            if prev_sp not in sp_order or curr_sp not in sp_order:
                continue

            sp_delta = sp_order[curr_sp] - sp_order[prev_sp]

            if sp_delta > 0:  # SP went up
                sp_up_actions[curr_skill] += 1
                if is_do_nothing(prev_skill) and is_protective(curr_skill):
                    sp_up_to_protect += 1
                elif is_do_nothing(prev_skill) and is_do_nothing(curr_skill):
                    sp_up_stay_nothing += 1
                else:
                    sp_up_other += 1
            elif sp_delta < 0:  # SP went down
                sp_down_actions[curr_skill] += 1
                if is_protective(prev_skill) and is_do_nothing(curr_skill):
                    sp_down_to_nothing += 1
                elif is_protective(prev_skill) and is_protective(curr_skill):
                    sp_down_stay_protect += 1
                else:
                    sp_down_other += 1
            else:  # SP stayed same
                sp_same_actions[curr_skill] += 1
                if is_do_nothing(prev_skill) and is_protective(curr_skill):
                    sp_same_to_protect += 1
                elif is_do_nothing(prev_skill) and is_do_nothing(curr_skill):
                    sp_same_stay_nothing += 1
                else:
                    sp_same_other += 1

    print("\n--- SP UP transitions ---")
    print(f"  N total transitions: {sp_up_to_protect + sp_up_stay_nothing + sp_up_other}")
    print(f"  do_nothing -> protective: {sp_up_to_protect}")
    print(f"  do_nothing -> do_nothing: {sp_up_stay_nothing}")
    print(f"  other: {sp_up_other}")
    print(f"  Action distribution: {sp_up_actions.most_common(8)}")

    print("\n--- SP DOWN transitions ---")
    print(f"  N total transitions: {sp_down_to_nothing + sp_down_stay_protect + sp_down_other}")
    print(f"  protective -> do_nothing: {sp_down_to_nothing}")
    print(f"  protective -> protective: {sp_down_stay_protect}")
    print(f"  other: {sp_down_other}")
    print(f"  Action distribution: {sp_down_actions.most_common(8)}")

    print("\n--- SP SAME transitions ---")
    print(f"  N total transitions: {sp_same_to_protect + sp_same_stay_nothing + sp_same_other}")
    print(f"  do_nothing -> protective: {sp_same_to_protect}")
    print(f"  do_nothing -> do_nothing: {sp_same_stay_nothing}")
    print(f"  other: {sp_same_other}")
    print(f"  Action distribution: {sp_same_actions.most_common(8)}")

    # Chi-squared: 2x2 contingency
    # Rows: SP-UP vs SP-SAME
    # Cols: switched-to-protective vs stayed-do-nothing
    a = sp_up_to_protect
    b = sp_up_stay_nothing
    c = sp_same_to_protect
    d = sp_same_stay_nothing
    total = a + b + c + d

    print(f"\n--- Chi-squared Contingency Table ---")
    print(f"                  Switched-to-protective  Stayed-do-nothing  Total")
    print(f"  SP went UP      {a:>22}  {b:>17}  {a+b:>5}")
    print(f"  SP stayed same  {c:>22}  {d:>17}  {c+d:>5}")
    print(f"  Total           {a+c:>22}  {b+d:>17}  {total:>5}")

    results_rows.append({
        "analysis": "A3_contingency",
        "group": "SP_UP_to_protect", "N": a,
    })
    results_rows.append({
        "analysis": "A3_contingency",
        "group": "SP_UP_stay_nothing", "N": b,
    })
    results_rows.append({
        "analysis": "A3_contingency",
        "group": "SP_SAME_to_protect", "N": c,
    })
    results_rows.append({
        "analysis": "A3_contingency",
        "group": "SP_SAME_stay_nothing", "N": d,
    })

    if total > 0 and (a+b) > 0 and (c+d) > 0 and (a+c) > 0 and (b+d) > 0:
        try:
            from scipy.stats import chi2_contingency
            table = [[a, b], [c, d]]
            chi2, p, dof, expected = chi2_contingency(table, correction=True)
            print(f"\n  Chi-squared = {chi2:.4f}, p = {p:.6f}, dof = {dof}")
            print(f"  Expected: {expected}")
            if p < 0.05:
                print("  ** SIGNIFICANT (p < 0.05): SP change IS associated with behavior change **")
            else:
                print("  Not significant at p < 0.05")
            results_rows.append({
                "analysis": "A3_chi2",
                "group": "chi2_test",
                "N": total,
                "chi2": f"{chi2:.4f}",
                "p_value": f"{p:.6f}",
            })
        except ImportError:
            # Manual chi-squared
            E_a = (a+b)*(a+c)/total
            E_b = (a+b)*(b+d)/total
            E_c = (c+d)*(a+c)/total
            E_d = (c+d)*(b+d)/total
            chi2 = sum((o-e)**2/e for o,e in [(a,E_a),(b,E_b),(c,E_c),(d,E_d)] if e>0)
            print(f"\n  Chi-squared (manual) = {chi2:.4f}")
    else:
        print("\n  Cannot compute chi-squared: insufficient counts in cells.")

    # Also: broader analysis — protective action rate by SP change direction
    print("\n--- Protective Action Rate by SP Change Direction ---")
    for label, action_ctr in [("SP_UP", sp_up_actions), ("SP_DOWN", sp_down_actions), ("SP_SAME", sp_same_actions)]:
        total_acts = sum(action_ctr.values())
        prot_acts = sum(v for k,v in action_ctr.items() if is_protective(k))
        print(f"  {label}: {pct(prot_acts, total_acts)} protective ({prot_acts}/{total_acts})")
        results_rows.append({
            "analysis": "A3_protective_rate",
            "group": label,
            "N": total_acts,
            "n_protective": prot_acts,
            "pct_protective": pct(prot_acts, total_acts),
        })

    return results_rows


# ======================================================================
# ANALYSIS 4: Surprising Patterns
# ======================================================================
def analysis_4(records):
    print("\n" + "=" * 72)
    print("ANALYSIS 4: Surprising Patterns (Impossible in Traditional ABMs)")
    print("=" * 72)

    results_rows = []

    PROTECTIVE_SET = {"elevate_house", "buy_insurance", "buy_flood_insurance",
                      "purchase_insurance", "relocate", "relocate_out",
                      "relocate_within", "buyout", "apply_buyout",
                      "buy_contents_insurance", "emergency_preparedness"}

    def is_protective(s):
        s = s.lower().strip()
        return s in PROTECTIVE_SET or "insur" in s or "elevat" in s or "relocat" in s or "buyout" in s

    def is_do_nothing(s):
        s = s.lower().strip()
        return "do_nothing" in s or "nothing" in s or s == "no_action"

    # --- 4d: High TP + High SP but do_nothing ---
    print("\n--- 4d: Informed-but-Inactive (TP=H + SP=H + do_nothing) ---")
    paradox_cases = []
    for r in records:
        if r["tp_label"] == "H" and r["sp_label"] == "H" and is_do_nothing(r["skill_name"]):
            paradox_cases.append(r)

    total_high_tp_sp = sum(1 for r in records if r["tp_label"]=="H" and r["sp_label"]=="H")
    print(f"  Total TP=H + SP=H: {total_high_tp_sp}")
    print(f"  Of those, chose do_nothing: {len(paradox_cases)} ({pct(len(paradox_cases), total_high_tp_sp)})")
    results_rows.append({
        "analysis": "A4_informed_inactive",
        "group": "TP=H_SP=H",
        "N": total_high_tp_sp,
        "n_do_nothing": len(paradox_cases),
        "pct_do_nothing": pct(len(paradox_cases), total_high_tp_sp),
    })

    # Sample reasoning
    print(f"\n  Sample reasoning from informed-but-inactive agents (up to 10):")
    for case in paradox_cases[:10]:
        reasoning_text = case["main_reasoning"] or case["raw_output"][:400]
        print(f"\n    Agent {case['agent_id']} (seed={case['seed']}, yr={case['year']}):")
        print(f"      SP reason: {case['sp_reason'][:200]}")
        print(f"      Main reasoning: {reasoning_text[:250]}")

    # --- 4e: Low SP but buy insurance ---
    print("\n\n--- 4e: Distrust-but-Insured (SP=L + insurance action) ---")
    distrust_insured = []
    total_sp_low = sum(1 for r in records if r["sp_label"] == "L")
    for r in records:
        if r["sp_label"] == "L" and "insur" in r["skill_name"].lower():
            distrust_insured.append(r)

    print(f"  Total SP=L: {total_sp_low}")
    print(f"  Of those, bought insurance: {len(distrust_insured)} ({pct(len(distrust_insured), total_sp_low)})")
    results_rows.append({
        "analysis": "A4_distrust_insured",
        "group": "SP=L",
        "N": total_sp_low,
        "n_insured": len(distrust_insured),
        "pct_insured": pct(len(distrust_insured), total_sp_low),
    })

    print(f"\n  Sample reasoning from distrust-but-insured agents (up to 10):")
    for case in distrust_insured[:10]:
        reasoning_text = case["main_reasoning"] or case["raw_output"][:400]
        print(f"\n    Agent {case['agent_id']} (seed={case['seed']}, yr={case['year']}):")
        print(f"      SP reason: {case['sp_reason'][:200]}")
        print(f"      Main reasoning: {reasoning_text[:250]}")

    # --- Additional: Action distribution by SP level ---
    print("\n\n--- Action Distribution by SP Level ---")
    sp_action_dist = defaultdict(Counter)
    for r in records:
        if r["sp_label"] in ("H", "M", "L"):
            sp_action_dist[r["sp_label"]][r["skill_name"]] += 1

    for lab in ["H", "M", "L"]:
        total_n = sum(sp_action_dist[lab].values())
        print(f"\n  SP={lab} (N={total_n}):")
        for skill, cnt in sp_action_dist[lab].most_common(8):
            print(f"    {skill}: {cnt} ({pct(cnt, total_n)})")

    # --- Additional: TP=H + CP=H but do_nothing ---
    print("\n\n--- Bonus: High Threat + High Coping but do_nothing ---")
    tp_cp_high_nothing = []
    total_tp_cp_high = sum(1 for r in records if r["tp_label"]=="H" and r["cp_label"]=="H")
    for r in records:
        if r["tp_label"] == "H" and r["cp_label"] == "H" and is_do_nothing(r["skill_name"]):
            tp_cp_high_nothing.append(r)
    print(f"  Total TP=H + CP=H: {total_tp_cp_high}")
    print(f"  Of those, chose do_nothing: {len(tp_cp_high_nothing)} ({pct(len(tp_cp_high_nothing), total_tp_cp_high)})")

    for case in tp_cp_high_nothing[:5]:
        reasoning_text = case["main_reasoning"] or case["raw_output"][:400]
        print(f"\n    Agent {case['agent_id']} (seed={case['seed']}, yr={case['year']}):")
        print(f"      Reasoning: {reasoning_text[:250]}")

    return results_rows


# ======================================================================
# MAIN
# ======================================================================
def main():
    print("Loading traces from 3 seeds x 2 agent types...")
    records = load_traces()
    print(f"Loaded {len(records)} total trace records")

    # Quick stats
    valid_sp = sum(1 for r in records if r["sp_label"] in ("H","M","L"))
    valid_pa = sum(1 for r in records if r["pa_label"] in ("H","M","L"))
    has_mem = sum(1 for r in records if r["mem_pre"])
    print(f"  With valid SP label: {valid_sp}")
    print(f"  With valid PA label: {valid_pa}")
    print(f"  With memories: {has_mem}")
    print(f"  Unique agents: {len(set(r['agent_id'] for r in records))}")
    print(f"  Years: {sorted(set(r['year'] for r in records))}")
    print(f"  Skills: {Counter(r['skill_name'] for r in records).most_common()}")
    print()

    all_rows = []
    all_rows.extend(analysis_1(records))
    all_rows.extend(analysis_2(records))
    all_rows.extend(analysis_3(records))
    all_rows.extend(analysis_4(records))

    # Save CSV
    out_path = OUT_DIR / "rq3_crosslayer_analysis.csv"
    if all_rows:
        fieldnames = sorted(set(k for row in all_rows for k in row.keys()))
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            w.writerows(all_rows)
        print(f"\n\nResults saved to: {out_path}")
    else:
        print("\nNo results to save.")


if __name__ == "__main__":
    main()
