"""Irrigation case v3, Work Package 6: the metrics module.

Spec: .research/design_specs/irrigation_v3_spec_2026-09-28.md, WP6 and section
4 (pilot gate P1-P10, reports R1-R4), PI items 16, 19, 21, 23, 28 and 30.
Definitions: examples/irrigation_abm/docs/v3_metrics.md.

Two parts:
- hand-computed synthetic fixtures (3 agents x 3 years, the same nine
  decisions in a strict and a disabled run) for every metric, with the edge
  cases the spec names: a blank and an omitted first WSA, a relabel, an
  off-menu answer, blocked against executed, an exhausted decision and an
  ABORTED row; plus the provenance guard's mixed-commit refusal;
- an end-to-end mock corpus: all five arms through the real runner with a
  scripted model (no Ollama), three short FQL seeds and the two replays,
  through the ``metrics`` and ``pilot-gate`` commands.
"""
from __future__ import annotations

import csv
import dataclasses
import inspect
import json
import re
import shutil
import sys
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from examples.irrigation_abm import irrigation_personas as personas
from examples.irrigation_abm.analysis import v3_metrics as vm
from examples.irrigation_abm.irrigation_env import (
    HYDROLOGY_V3_SHA256, LB_PRIORITY_SPLIT_SHA256, MEAD_CAPACITY_SHA256, UB_SUBBASIN_ENVELOPE_SHA256,
    UB_SUBBASIN_VARIANT_MEANS_SHA256, IrrigationEnvironment, WaterSystemConfig, _UB_SUBBASIN_SUPPLY_VARIANT_FILES,
    _load_hydrology_table,
)

REPO = Path(__file__).resolve().parents[3]
CRSS_PARAMS_CSV = REPO / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
CRSS_DB_DIR = REPO / "ref" / "CRSS_DB" / "CRSS_DB"
_REAL_REF_AVAILABLE = CRSS_PARAMS_CSV.is_file() and CRSS_DB_DIR.is_dir()
needs_ref = pytest.mark.skipif(not _REAL_REF_AVAILABLE, reason="CRSS reference data not found under ref/")

INC, KEEP, DEC = vm.INCREASE, vm.KEEP, vm.DECREASE
TR1, TR3, SUP, CAP, FLOOR = vm.RULE_TR1, vm.RULE_TR3, vm.RULE_SUPPLY, vm.RULE_CAP, vm.RULE_FLOOR
CFG = WaterSystemConfig()
COMMIT = "c" * 40
OLD_LB_PRIORITY_SPLIT_SHA256 = (
    "0b4462d7ea5a3364f433bc84847232d1a42a17e36329e8dbfa2143b6d195d165"
)


@pytest.fixture(autouse=True)
def _restore_profile_env(monkeypatch):
    monkeypatch.setenv("GOVERNANCE_PROFILE", "strict")
    yield


# =============================================================================
# Fixture writer: one run directory from hand-written decisions
# =============================================================================

def llm_manifest(arm: str, seed: int = 42, commit: str = COMMIT, model: str = "mock",
                 grid: int = 9, agents: Sequence[str] = ()) -> Dict[str, Any]:
    profile = {"placebo": "strict", "silent": "strict"}.get(arm, arm)
    mode = arm if arm in ("placebo", "silent") else "full"
    return {
        "model": model, "seed": seed, "memory_seed": 42, "governance_profile": profile,
        "governance_profile_resolved": profile, "retry_feedback_mode": mode,
        "git_commit": commit, "git_dirty": False, "timestamp": "2026-09-30T10:00:00",
        "hold_requests_fixed": False, "powell_release_mode": CFG.powell_release_mode,
        "powell_post2026_equalization": CFG.powell_post2026_equalization,
        "lb_non_ag_total_maf": CFG.lb_non_ag_total_maf,
        # Item 36e (2026-10-05); Opus review P2-2: 0.0 by default.
        "lb_return_flow_fraction": CFG.lb_return_flow_fraction,
        "lb_p56_in_tier": CFG.lb_p56_in_tier,
        # 2026-10-06 CPU rerun finding: 0.10 by default.
        "min_utilisation_fraction": CFG.min_utilisation_fraction,
        "paper_water_margin": 0.4,
        "cluster_method": "hy2021", "step_bin_source": {a: None for a in agents},
        "ub_supply_mode": CFG.ub_supply_mode, "ub_subbasin_supply_variant": CFG.ub_subbasin_supply_variant,
        "ub_subbasin_supply_v3_sha256": _UB_SUBBASIN_SUPPLY_VARIANT_FILES[CFG.ub_subbasin_supply_variant][1],
        "ub_subbasin_envelope_v3_sha256": UB_SUBBASIN_ENVELOPE_SHA256,
        "ub_subbasin_variant_means_v3_sha256": UB_SUBBASIN_VARIANT_MEANS_SHA256,
        "appraisal_freeze_resolved": True,
        "coupling_retrofit_metadata": {
            "water_system_lb_tributary_source": CFG.lb_tributary_source,
            "water_system_lb_priority_mode": CFG.lb_priority_mode,
            "water_system_hydrology_v3_sha256": HYDROLOGY_V3_SHA256,
            "water_system_mead_capacity_sha256": MEAD_CAPACITY_SHA256,
            "water_system_lb_priority_split_sha256": LB_PRIORITY_SPLIT_SHA256,
        },
        "run_integrity": {"configured_grid_rows": grid},
    }


def fql_manifest(seed: int, commit: str = COMMIT, agents: Sequence[str] = ()) -> Dict[str, Any]:
    from examples.irrigation_abm.run_fql_baseline import _pinned_v3_data_checksums
    return {
        "runner": "run_fql_baseline", "seed": seed, "git_head": commit, "git_dirty": False,
        "no_governance": True, "fql_init": "zero", "fql_init_dir": None, "hold_requests_fixed": False,
        "powell_release_mode": CFG.powell_release_mode,
        "powell_post2026_equalization": CFG.powell_post2026_equalization,
        "lb_non_ag_total_maf": CFG.lb_non_ag_total_maf, "ub_supply_mode": CFG.ub_supply_mode,
        "ub_subbasin_supply_variant": CFG.ub_subbasin_supply_variant, "lb_priority_mode": CFG.lb_priority_mode,
        "paper_water_margin": 0.4, "cluster_method": "hy2021", "step_bin_source": {a: None for a in agents},
        "pinned_v3_data_checksums": _pinned_v3_data_checksums(CFG.ub_subbasin_supply_variant),
        "water_system_config": dataclasses.asdict(WaterSystemConfig(seed=seed)),
        "lb_p56_in_tier": CFG.lb_p56_in_tier,
    }


def system_years(n: int, mead_ends: Sequence[float], powell_ends: Sequence[float],
                 tiers: Sequence[int], unbalance: Optional[Dict[int, float]] = None) -> Dict[int, Dict[str, float]]:
    """Per-year water-system values that close the P1 identity (plus an
    optional residual per year) and chain storages and Mead levels."""
    hydrology = _load_hydrology_table()
    out = {}
    mead, powell = 12.679, CFG.powell_initial_storage_maf
    for t in range(1, n + 1):
        year = CFG.sim_start_year + t - 1
        nf = hydrology[year]["lees_ferry_cy_natural_flow_af"] / 1e6
        values = {
            "lake_mead_level": CFG.mead_initial_elevation if t == 1 else vm.mead_elevation_ft(mead),
            "mead_storage_maf": mead, "powell_storage_maf": powell, "powell_storage_end_maf": powell_ends[t - 1],
            "natural_flow_maf": nf, "ub_non_farm_maf": 1.2213, "lb_tributary_maf": 0.8, "ub_delivered_maf": 3.0,
            "powell_evap_maf": 0.4, "mead_evap_maf": 0.5, "powell_spill_maf": 0.0, "mead_spill_maf": 0.0,
            "lb_delivered_maf": 2.6, "lb_non_ag_delivered_maf": 5.2, "mexico_delivered_maf": 1.5,
            "lb_shortage_volume_maf": 0.0, "shortage_tier": tiers[t - 1],
            "calendar_year": hydrology[year]["source_calendar_year"],
        }
        rhs = (nf - 1.2213 + 0.8 - 3.0 - 0.4 - 0.5 - (2.6 + 5.2 + 1.5) - 0.0)
        # the Mead end storage is given; Powell's end storage closes the year
        values["mead_storage_end_maf"] = mead_ends[t - 1]
        values["powell_storage_end_maf"] = powell + rhs - (mead_ends[t - 1] - mead) + (unbalance or {}).get(t, 0.0)
        out[t] = values
        mead, powell = mead_ends[t - 1], values["powell_storage_end_maf"]
    return out


AGENTS = {  # agent: (basin, cluster, sub-basin, water right)
    "UB1": ("upper_basin", "aggressive", "UT1", 2000.0),
    "UB2": ("upper_basin", "aggressive", "UT1", 3000.0),
    "LB1": ("lower_basin", "myopic_conservative", None, 4000.0),
}


def sim_rows(system: Dict[int, Dict[str, float]], agent_years: Dict[Tuple[str, int], Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for (agent, t), values in sorted(agent_years.items(), key=lambda kv: (kv[0][1], kv[0][0])):
        basin, cluster, sb, w = AGENTS.get(agent, values.get("_identity"))
        row = {"agent_id": agent, "year": t, "basin": basin, "cluster": cluster, "water_right": w,
               "request": 1000.0, "diversion": 1000.0, "base_af": 1000.0,
               "ub_subbasin": sb or "", "ub_subbasin_ratio": 1.0 if sb else "",
               "precipitation_mm": 100.0 if basin == "upper_basin" else "",
               "precipitation_flag": 1 if basin == "upper_basin" else "",
               "typical_step_af": 100.0, "magnitude_pct": "", "lb_junior_tier_cut_fraction": "" if sb else 0.0,
               "lb_junior_ceiling_af": "", "lb_tier_ceiling_af": "",
               "lb_junior_entitlement_af": "", "lb_p56_entitlement_af": "",
               "lb_p56_in_tier": CFG.lb_p56_in_tier}
        row.update({k: v for k, v in values.items() if not k.startswith("_")})
        row.update(system[t])
        rows.append(row)
    return rows


def labels_text(labels: Optional[Dict[str, str]], sep: str) -> str:
    return "" if not labels else sep.join(f"{k}={v}" for k, v in labels.items())


Attempt = Tuple[Optional[str], Optional[Dict[str, str]], Optional[Sequence[str]]]


def audit_row(agent: str, t: int, attempts: Sequence[Attempt], *, executed: Optional[str],
              status: str = "APPROVED", path: str = "approved", physical: float = 1.0,
              keep: float = 1000.0, format_retries: int = 0, llm_success: str = "True",
              error_messages: str = "", crashed: bool = False) -> Dict[str, Any]:
    """``crashed``: the runner's ABORTED_EXCEPTION sentinel as it writes it
    (blank attempt and supply-state cells, llm_success left at True)."""
    if crashed:
        status, path = vm.EXCEPTION_STATUS, "aborted"
    if path == "aborted":
        skills = labels = rules = ""
        initial_skill = initial = final = relabeled = ""
        if not crashed:
            labels, rules, relabeled = vm.UNOBSERVED, vm.UNOBSERVED, vm.UNOBSERVED
        retry_count = 0
    else:
        skills = "|".join(s or "" for s, _, _ in attempts)
        labels = "|".join("" if s is None else labels_text(lab, ",") for s, lab, _ in attempts)
        rules = "|".join("" if s is None else ",".join(r or ()) for s, _, r in attempts)
        initial_skill = attempts[0][0]
        initial = labels_text(attempts[0][1], "|")
        final = labels_text(attempts[-1][1], "|") if attempts[-1][0] is not None else ""
        first: Dict[str, str] = {}
        relabeled = "False"
        for s, lab, _ in attempts:
            for k, v in (lab or {}).items():
                if v.strip() and first.setdefault(k, v) != v:
                    relabeled = "True"
        retry_count = len(attempts) - 1
    expected = keep * physical
    row = {
        "agent_id": agent, "year": t, "status": status, "execution_path": path,
        "executed_skill": executed or "", "proposed_skill": attempts[-1][0] if attempts and attempts[-1][0] else "",
        "final_skill": executed or "", "retry_count": retry_count, "format_retries": format_retries,
        "llm_success": llm_success, "initial_skill": initial_skill, "initial_labels": initial,
        "final_labels": final, "attempt_skills": skills, "attempt_labels": labels,
        "attempt_failed_rules": rules, "appraisal_relabeled": relabeled, "error_messages": error_messages,
        "timestamp": f"2026-09-30T09:00:{t:02d}",
        "state_supply_keep_request_af": keep, "state_supply_expected_at_keep_af": expected,
        "state_supply_ratio": round(physical, 6), "state_supply_physical_ratio": round(physical, 6),
        "state_full_supply_ratio": personas.FULL_SUPPLY_RATIO,
    }
    if crashed:
        row.update({f"state_{k}": "" for k in ("supply_keep_request_af", "supply_expected_at_keep_af",
                                                "supply_ratio", "supply_physical_ratio", "full_supply_ratio")})
    return row


def menu_prompt(agent: str, t: int, options: Sequence[str]) -> str:
    texts = {"increase": "Increase your request to about 1,100 acre-ft: the 1,000 acre-ft you received last year "
                         "plus your typical step of about 100 acre-ft.",
             "keep": "Keep your request at 1,000 acre-ft, the amount you received last year.",
             "decrease": "Decrease your request to about 900 acre-ft: the 1,000 acre-ft you received last year "
                         "minus your typical step of about 100 acre-ft."}
    body = "\n".join(f"{i + 1}. {texts[o]}" for i, o in enumerate(options))
    return f"Now, choose one of the following water management actions:\n{body}\n"


def trace(agent: str, t: int, *, at_cap: bool = False, at_floor: bool = False, aborted: bool = False,
          keep: float = 1000.0, prompt: Optional[str] = None, crashed: bool = False) -> Dict[str, Any]:
    if crashed:  # ExperimentRunner._write_aborted_trace: no input, no state_before
        return {"agent_id": agent, "year": t, "status": vm.EXCEPTION_STATUS, "execution_path": "aborted"}
    options = [o for o, hidden in (("increase", at_cap), ("keep", False), ("decrease", at_floor)) if not hidden]
    rec = {"agent_id": agent, "year": t, "input": prompt or menu_prompt(agent, t, options)}
    if aborted:
        rec["execution_path"] = "aborted"
    else:
        rec["state_before"] = {"at_allocation_cap": at_cap, "below_minimum_utilisation": at_floor,
                               "current_request": keep, "water_right": AGENTS[agent][3]}
    return rec


def write_run(directory: Path, manifest: Dict[str, Any], sims: List[Dict[str, Any]],
              audits: Optional[List[Dict[str, Any]]] = None, traces: Optional[List[Dict[str, Any]]] = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / vm.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    vm.write_csv(directory / vm.SIM_LOG, sims)
    if audits is not None:
        vm.write_csv(directory / vm.AUDIT_CSV, audits)
    if traces is not None:
        (directory / "raw").mkdir(exist_ok=True)
        lines = [json.dumps({"_metadata": {"audit_schema_version": "2"}})] + [json.dumps(t) for t in traces]
        (directory / vm.TRACES).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return directory


# The nine decisions (agent, year) of the hand-computed fixture, as each arm
# records them. Physical supply ratio 0.9 = the supply rule's condition holds
# (UB2 in years 2 and 3); LB1 sits at its water right in year 2 (cap).
P_SHORT = 0.9
STRICT_DECISIONS = {
    # d1: TR1 blocks H + increase; the retry relabels to M (still blocked under
    # the freeze), then keeps. Final keep, first WSA H, final WSA M: a relabel.
    ("UB1", 1): dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [TR1]),
                              (INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [TR1]),
                              (KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP),
    # d2: exhausted: TR3 blocks L + decrease four times; keep executes.
    ("UB2", 1): dict(attempts=[(DEC, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [TR3])] * 4,
                     executed=KEEP, status="REJECTED", path="rejected_default"),
    ("LB1", 1): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP),
    # d4: blank first WSA (recorded as WSA_LABEL=): the format check fires;
    # the retry states VH with an increase (TR1), then keeps.
    ("UB1", 2): dict(attempts=[(KEEP, {"WSA_LABEL": "", "ACA_LABEL": "M"}, ["Unknown"]),
                              (INC, {"WSA_LABEL": "VH", "ACA_LABEL": "M"}, [TR1]),
                              (KEEP, {"WSA_LABEL": "VH", "ACA_LABEL": "M"}, [])], executed=KEEP),
    # d5: the supply rule blocks an increase (physical ratio 0.9).
    ("UB2", 2): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [SUP]),
                              (KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP, physical=P_SHORT),
    # d6: off-menu: an increase at the water-right cap, blocked by the identity
    # rule and the two registry backstops.
    ("LB1", 2): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"},
                                [CAP, "output_schema_violation", "precondition_violation"]),
                               (KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP),
    # d7: ABORTED: nothing parsed.
    ("UB1", 3): dict(attempts=[], executed=None, status="ABORTED", path="aborted", format_retries=3, llm_success=""),
    # d8: exhausted under two rules (supply and TR1); keep executes.
    ("UB2", 3): dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "H"}, [TR1, SUP])] * 4, executed=KEEP,
                     status="REJECTED", path="rejected_default", physical=P_SHORT),
    ("LB1", 3): dict(attempts=[(INC, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [])], executed=INC),
}
DISABLED_DECISIONS = {
    ("UB1", 1): dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [])], executed=INC),
    ("UB2", 1): dict(attempts=[(DEC, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [])], executed=DEC),
    ("LB1", 1): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP),
    # d4: the first attempt OMITS the WSA; the retry states VH and increases,
    # approved: TR1 is counted only through the item 28 fallback.
    ("UB1", 2): dict(attempts=[(KEEP, {"ACA_LABEL": "M"}, ["Unknown"]),
                              (INC, {"WSA_LABEL": "VH", "ACA_LABEL": "M"}, [])], executed=INC),
    ("UB2", 2): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=INC, physical=P_SHORT),
    ("LB1", 2): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"},
                                [CAP, "output_schema_violation", "precondition_violation"]),
                               (KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP),
    ("UB1", 3): dict(attempts=[], executed=None, status="ABORTED", path="aborted", format_retries=3, llm_success=""),
    ("UB2", 3): dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "H"}, [])], executed=INC, physical=P_SHORT),
    ("LB1", 3): dict(attempts=[(INC, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [])], executed=INC),
}
AT_CAP = {("LB1", 2)}


def fixture_run(tmp_path: Path, arm: str, decisions: Dict[Tuple[str, int], Dict[str, Any]], *,
                seed: int = 42, commit: str = COMMIT, name: Optional[str] = None,
                mead_ends: Sequence[float] = (13.0, 12.0, 11.5), powell_ends: Sequence[float] = (11.0, 10.0, 9.0),
                tiers: Sequence[int] = (0, 0, 1), unbalance: Optional[Dict[int, float]] = None,
                prompt_for=None) -> Path:
    system = system_years(3, mead_ends, powell_ends, tiers, unbalance)
    agent_years = {}
    for (agent, t), spec in decisions.items():
        values: Dict[str, Any] = {}
        if spec.get("physical", 1.0) < 1.0:
            values["ub_subbasin_ratio"] = spec["physical"]
            values["diversion"] = 1000.0 * spec["physical"]
        agent_years[(agent, t)] = values
    audits = [audit_row(a, t, **spec) for (a, t), spec in decisions.items()]
    traces = [trace(a, t, at_cap=(a, t) in AT_CAP, aborted=spec.get("path") == "aborted",
                    prompt=prompt_for(a, t) if prompt_for else None, crashed=spec.get("crashed", False))
              for (a, t), spec in decisions.items()]
    return write_run(tmp_path / (name or f"{arm}_seed{seed}"),
                     llm_manifest(arm, seed, commit, agents=sorted(AGENTS)), sim_rows(system, agent_years),
                     audits, traces)


@pytest.fixture
def strict_run(tmp_path):
    return vm.load_run(fixture_run(tmp_path, "strict", STRICT_DECISIONS), keep_prompts=True)


@pytest.fixture
def disabled_run(tmp_path):
    return vm.load_run(fixture_run(tmp_path, "disabled", DISABLED_DECISIONS), keep_prompts=True)


# =============================================================================
# Single sources and pre-registered definitions
# =============================================================================

def test_full_supply_ratio_and_rules_are_the_live_ones():
    assert vm.FULL_SUPPLY_RATIO is personas.FULL_SUPPLY_RATIO
    vm.assert_thinking_rules_match_config()


def test_thinking_rule_drift_in_the_config_is_refused(tmp_path):
    raw = (REPO / "examples" / "irrigation_abm" / "config" / "agent_types.yaml").read_text(encoding="utf-8")
    drifted = raw.replace('values: ["H", "VH"]', 'values: ["VH"]', 1)
    assert drifted != raw
    path = tmp_path / "agent_types.yaml"
    path.write_text(drifted, encoding="utf-8")
    with pytest.raises(vm.MetricsError, match="pre-registered"):
        vm.assert_thinking_rules_match_config(path)


def test_mead_2018_level_is_the_environment_seed():
    assert IrrigationEnvironment(WaterSystemConfig())._mead_history[0] == vm.MEAD_JAN1_2018_FT


@pytest.mark.parametrize("arm", vm.ARMS)
def test_arm_comes_from_the_manifest(arm):
    assert vm.llm_arm(llm_manifest(arm), "m") == arm


def test_unknown_arm_is_refused():
    bad = llm_manifest("disabled")
    bad["retry_feedback_mode"] = "placebo"
    with pytest.raises(vm.MetricsError, match="no v3 arm"):
        vm.llm_arm(bad, "m")


# =============================================================================
# Item 19: IBR, final-label IBR, relabel rate (hand computed)
# =============================================================================

def test_ibr_strict_hand_computed(strict_run):
    m = vm.ibr_metrics(strict_run.ordered())
    # TR1: only d8 ends on increase with a high first WSA; TR3: d2 (exhausted)
    assert (m["decisions"], m["ibr_tr1_count"], m["ibr_tr3_count"]) == (9, 1, 1)
    assert m["ibr_pct"] == pytest.approx(200 / 9) and m["ibr_tr1_pct"] == pytest.approx(100 / 9)
    assert m["ibr_pct"] == pytest.approx(m["ibr_tr1_pct"] + m["ibr_tr3_pct"])
    assert m["ibr_final_label_pct"] == pytest.approx(200 / 9)
    # retried: d1, d2, d4, d5, d6, d8; the only WSA relabel is d1 (H to M).
    # d4's blank-then-VH is a first statement, not a relabel.
    assert (m["retried_decisions"], m["relabeled_decisions"]) == (6, 1)
    assert m["relabel_rate_pct"] == pytest.approx(100 / 6)
    assert "relabel_no_r_change_pct" not in m  # dropped: 100 percent by construction
    assert (m["first_wsa_missing"], m["unreadable_final_proposals"]) == (1, 1)  # d7, ABORTED


def test_ibr_disabled_hand_computed_with_the_first_label_fallback(disabled_run):
    m = vm.ibr_metrics(disabled_run.ordered())
    # TR1: d1 (H), d4 (VH only through the fallback: the first attempt
    # omitted the WSA), d8 (H); TR3: d2 (L).
    assert (m["ibr_tr1_count"], m["ibr_tr3_count"]) == (3, 1)
    assert m["ibr_pct"] == pytest.approx(400 / 9)
    assert m["ibr_final_label_pct"] == pytest.approx(400 / 9)
    assert (m["retried_decisions"], m["relabeled_decisions"]) == (2, 0)  # d4, d6
    assert m["relabel_rate_pct"] == 0.0
    d4 = disabled_run.decisions[("UB1", 2)]
    assert d4.first_wsa == "VH" and d4.attempts[0].labels == {"ACA_LABEL": "M"}


def _set_ub1_2019_tier_cut(path: Path, *, manifest_field: bool = False) -> Path:
    rows = list(csv.DictReader(open(path / vm.SIM_LOG, encoding="utf-8")))
    for row in rows:
        if (row["agent_id"], row["year"]) == ("UB1", "1"):
            row.update(request="1200", diversion="1000", gap_reason="lb_junior_tier_cut")
    vm.write_csv(path / vm.SIM_LOG, rows)
    if manifest_field:
        manifest = json.loads((path / vm.MANIFEST).read_text(encoding="utf-8"))
        manifest["tier_cut_restore"] = {"spec": "45p/45q"}
        (path / vm.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    return path


def test_historical_run_keeps_old_tr1_unless_analysis_override_is_explicit(tmp_path):
    path = _set_ub1_2019_tier_cut(
        fixture_run(tmp_path, "disabled", DISABLED_DECISIONS, name="historical"))
    historical = vm.load_run(path)
    overridden = vm.load_run(path, apply_tier_cut_restore=True)
    old_d, new_d = historical.decisions[("UB1", 2)], overridden.decisions[("UB1", 2)]
    assert (old_d.previous_gap_reason, old_d.previous_request_af) == ("lb_junior_tier_cut", 1200.0)
    assert old_d.tier_cut_restore_enabled is False
    assert new_d.tier_cut_restore_enabled is True
    assert vm.ibr_metrics(historical.ordered())["ibr_tr1_count"] == 3
    assert vm.ibr_metrics(overridden.ordered())["ibr_tr1_count"] == 2


@pytest.mark.parametrize(
    ("column", "value"),
    [
        # Native broker payloads are pipe-delimited rule IDs, not the
        # retired exception precondition. No state flag column is present.
        ("rule_exceptions_used", "high_scarcity_no_increase"),
        ("rule_exceptions_used", "water_right_cap|high_scarcity_no_increase"),
        ("rule_exceptions_used", "tier_cut_restore_available"),
        ("state_tier_cut_restore_available", "False"),
    ],
)
def test_45q_audit_columns_without_manifest_field_fail_loudly(tmp_path, column, value):
    path = _set_ub1_2019_tier_cut(
        fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="lost_manifest_write"))
    audit = path / vm.AUDIT_CSV
    with open(audit, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    rows[0].append(column)
    for n, row in enumerate(rows[1:]):
        row.append(value if n == 0 else "")
    with open(audit, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    with pytest.raises(vm.MetricsError, match="lacks 'tier_cut_restore'"):
        vm.load_run(path)


@pytest.mark.parametrize("payload", ["", "high_scarcity_no_increase_other"])
def test_blank_generic_rule_exception_column_is_valid_for_current_runs(tmp_path, payload):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="blank_generic_exceptions")
    audit = path / vm.AUDIT_CSV
    with open(audit, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    rows[0].append("rule_exceptions_used")
    for row in rows[1:]:
        row.append(payload)
    with open(audit, "w", encoding="utf-8", newline="") as fh:
        csv.writer(fh).writerows(rows)
    vm.load_run(path)


def test_manifest_field_enables_45p_and_45q_tr1_without_random_step_reconstruction(tmp_path):
    path = _set_ub1_2019_tier_cut(
        fixture_run(tmp_path, "disabled", DISABLED_DECISIONS, name="recorded"),
        manifest_field=True,
    )
    run = vm.load_run(path)
    decision = run.decisions[("UB1", 2)]
    assert decision.tier_cut_restore_enabled is True
    assert decision.tr1(INC, "VH") is False
    census = {row["rule"]: row for row in vm.rule_census(run)}
    assert census[TR1]["condition_held"] == 2


def test_historical_p7_agreement_changes_only_under_explicit_override(tmp_path):
    path = _set_ub1_2019_tier_cut(
        fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="historical_strict"))
    base = vm.rule_agreement(vm.load_run(path))[TR1]
    overridden = vm.rule_agreement(
        vm.load_run(path, apply_tier_cut_restore=True))[TR1]
    assert base["disagreements"] == 0
    assert overridden["disagreements"] == 1


def test_first_stated_wsa_skips_a_blank(strict_run):
    d4 = strict_run.decisions[("UB1", 2)]
    assert d4.attempts[0].labels["WSA_LABEL"] == ""
    assert d4.first_wsa == "VH" and not d4.wsa_relabeled


def test_relabel_rate_is_wsa_only(tmp_path):
    """An ACA-only change is a relabel for appraisal_relabeled, not for the
    WSA relabel rate."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [TR1]),
                                          (KEEP, {"WSA_LABEL": "H", "ACA_LABEL": "VH"}, [])], executed=KEEP)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions))
    d = run.decisions[("LB1", 1)]
    assert not d.wsa_relabeled
    assert vm.ibr_metrics(run.ordered())["relabeled_decisions"] == 1  # still only d1


def test_final_label_ibr_reads_the_final_wsa(tmp_path):
    """A REJECTED increase whose WSA moved H to M: primary IBR counts it
    (first WSA), the final-label IBR does not (final WSA)."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("UB2", 3)] = dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "H"}, [TR1, SUP])]
                                 + [(INC, {"WSA_LABEL": "M", "ACA_LABEL": "H"}, [TR1, SUP])] * 3,
                                 executed=KEEP, status="REJECTED", path="rejected_default", physical=P_SHORT)
    m = vm.ibr_metrics(vm.load_run(fixture_run(tmp_path, "strict", decisions)).ordered())
    assert m["ibr_tr1_count"] == 1
    assert m["ibr_final_label_tr1_pct"] == 0.0
    assert m["relabeled_decisions"] == 2  # d1 and this one


# =============================================================================
# Opus review P2-1 (2026-10-07): pin the three IBR variants (first proposal,
# final proposal = primary, executed) against four hand-picked decisions per
# rule, built directly as Decision/Attempt (no CSV round-trip needed: these
# are the only fields ibr_metrics reads).
# =============================================================================

def _ibr_decision(agent: str, year: int, skills: Sequence[str], wsa: str, executed: Optional[str]) -> vm.Decision:
    """A minimal Decision for ibr_metrics: ``skills`` is the proposed skill
    of each successive attempt (the frozen WSA ``wsa`` throughout, no
    relabel); ``executed`` is the actually executed skill."""
    attempts = tuple(vm.Attempt(s, {"WSA_LABEL": wsa}, ()) for s in skills)
    return vm.Decision(
        agent_id=agent, year=year, status="APPROVED", execution_path="approved",
        executed_skill=executed, proposed_skill=skills[-1], attempts=attempts,
        retry_count=len(skills) - 1, format_retries=0, llm_success=True,
        keep_request_af=1000.0, expected_at_keep_af=1000.0, supply_ratio=1.0, physical_ratio=1.0,
        first_wsa=wsa, first_aca=None, final_wsa=wsa, wsa_relabeled=False,
        error_messages="", timestamp="2026-10-07T00:00:00",
    )


def test_ibr_first_proposal_final_proposal_executed_hand_computed():
    """Four TR1 decisions (WSA H, increase) plus their TR3 mirror (WSA L,
    decrease), pinning the first-proposal, final-proposal (primary) and
    executed shares exactly, per Opus review P2-1:

    - exhausted (I,I,I,I -> executed maintain): first=violates, final=
      violates (the blocked proposal stays final, item 37a), executed=does
      not (the registry default never violates TR1/TR3).
    - I then K (one retry succeeds): first=violates, final=does not,
      executed=does not.
    - disabled-style I -> I (never retried, not live): first=violates,
      final=violates, executed=violates (nothing blocked it).
    - K (never an issue): none of the three violate.

    Over the 8 decisions (4 TR1 + 4 TR3 mirror), each variant's TR1 and TR3
    sub-counts are equal (3/3, 2/2, 1/1), so the combined first/final/
    executed shares come out to the flood-analogue 75% / 50% / 25% exactly,
    all over the SAME N = 8.
    """
    decisions = [
        # TR1 (WSA H, increase_demand):
        _ibr_decision("TR1a", 1, [INC, INC, INC, INC], "H", executed=KEEP),   # exhausted
        _ibr_decision("TR1b", 1, [INC, KEEP], "H", executed=KEEP),            # I then K
        _ibr_decision("TR1c", 1, [INC], "H", executed=INC),                  # disabled-style
        _ibr_decision("TR1d", 1, [KEEP], "H", executed=KEEP),                 # K
        # TR3 mirror (WSA L, decrease_demand):
        _ibr_decision("TR3a", 1, [DEC, DEC, DEC, DEC], "L", executed=KEEP),
        _ibr_decision("TR3b", 1, [DEC, KEEP], "L", executed=KEEP),
        _ibr_decision("TR3c", 1, [DEC], "L", executed=DEC),
        _ibr_decision("TR3d", 1, [KEEP], "L", executed=KEEP),
    ]
    m = vm.ibr_metrics(decisions)
    assert m["decisions"] == 8
    # Final proposal (primary, item 37a): 2 of 4 per rule (exhausted + disabled-style).
    assert (m["ibr_tr1_count"], m["ibr_tr3_count"]) == (2, 2)
    assert m["ibr_pct"] == pytest.approx(50.0)
    # First proposal (paper_scope C2 companion, not item 37): 3 of 4 per rule
    # (every attempt-0 proposal except the never-an-issue K decision).
    assert (m["ibr_first_proposal_tr1_count"], m["ibr_first_proposal_tr3_count"]) == (3, 3)
    assert m["ibr_first_proposal_pct"] == pytest.approx(75.0)
    # Executed (item 37/37a companion): 1 of 4 per rule (only the
    # disabled-style decision, never blocked, executes the violating skill).
    assert (m["ibr_executed_tr1_count"], m["ibr_executed_tr3_count"]) == (1, 1)
    assert m["ibr_executed_pct"] == pytest.approx(25.0)
    # The same TR1+TR3=combined sum identity the code checks in gate_p10,
    # pinned here for all three variants.
    assert m["ibr_pct"] == pytest.approx(m["ibr_tr1_pct"] + m["ibr_tr3_pct"])
    assert m["ibr_first_proposal_pct"] == pytest.approx(
        m["ibr_first_proposal_tr1_pct"] + m["ibr_first_proposal_tr3_pct"])
    assert m["ibr_executed_pct"] == pytest.approx(m["ibr_executed_tr1_pct"] + m["ibr_executed_tr3_pct"])


# =============================================================================
# Item 37d (2026-10-07): the primary IBR steps back to the agent's LAST
# PARSED attempt when the literal last attempt did not parse (status
# REJECTED_FALLBACK), instead of treating it as no violation. Hand-built
# Decisions, no CSV round-trip needed (ibr_metrics reads only attempts,
# first_wsa and executed_skill).
# =============================================================================

def _stepback_decision(agent: str, skills: Sequence[Optional[str]], wsa: str) -> vm.Decision:
    """Like ``_ibr_decision`` (frozen WSA throughout, no relabel), but
    ``skills`` may end in one or more ``None`` entries: an attempt that did
    not parse. ``skills`` itself must not be empty (an ABORTED decision,
    with no attempts at all, is a separate, pre-existing case)."""
    attempts = tuple(
        vm.Attempt(s, {"WSA_LABEL": wsa}, ()) if s is not None else vm.Attempt(None, None, None)
        for s in skills
    )
    last_parsed = next((s for s in reversed(skills) if s is not None), None)
    unparsed_tail = skills[-1] is None
    return vm.Decision(
        agent_id=agent, year=1,
        status="REJECTED_FALLBACK" if unparsed_tail else "APPROVED",
        # docs/AUDIT_SCHEMA.md: execution_path = "fallback" is the real value
        # for status REJECTED_FALLBACK ("rejected_default" is a different
        # path -- a REJECTED row under on_retry_exhausted = default).
        execution_path="fallback" if unparsed_tail else "approved",
        executed_skill=KEEP, proposed_skill=last_parsed or KEEP,
        attempts=attempts, retry_count=len(skills) - 1, format_retries=0, llm_success=True,
        keep_request_af=1000.0, expected_at_keep_af=1000.0, supply_ratio=1.0, physical_ratio=1.0,
        first_wsa=wsa, first_aca=None, final_wsa=None if unparsed_tail else wsa,
        wsa_relabeled=False, error_messages="", timestamp="2026-10-07T00:00:00",
    )


def test_primary_ibr_steps_back_to_last_parsed_attempt():
    """Spec item 37d: three hand-built decisions pin the step-back rule and
    its two companion counts."""
    decisions = [
        # (a) increase, increase, unparsed: steps back to increase; WSA H
        # -> a TR1 violation found ONLY by stepping back (the literal last
        # attempt is unparsed, so final_proposal alone would read None).
        _stepback_decision("a", [INC, INC, None], wsa="H"),
        # (b) increase, keep, unparsed: steps back to keep -> no violation,
        # even though the literal last attempt is also unparsed.
        _stepback_decision("b", [INC, KEEP, None], wsa="H"),
        # (c) unparsed only: no parsed attempt anywhere -> no violation
        # (same as an unreadable final_proposal), but still a
        # last-attempt-unparsed row. The WSA here is a hand-built
        # convenience (Decision.first_wsa is set directly, not derived from
        # attempts): through parse_decision a non-ABORTED row's first
        # attempt always parses, so a real "every attempt unparsed" audit
        # row with a stated WSA is unreachable -- this case exists only to
        # pin last_parsed_proposal's defensive None return.
        _stepback_decision("c", [None], wsa="H"),
    ]
    m = vm.ibr_metrics(decisions)
    assert m["decisions"] == 3
    assert (m["ibr_tr1_count"], m["ibr_tr3_count"]) == (1, 0)
    assert m["ibr_pct"] == pytest.approx(100 / 3)
    assert m["ibr_pct"] == pytest.approx(m["ibr_tr1_pct"] + m["ibr_tr3_pct"])
    # all three decisions end on an unparsed attempt (unlike unreadable_
    # final_proposals, which would also count a fully-aborted decision --
    # none of these is aborted, so the two counts agree here).
    assert m["last_attempt_unparsed_n"] == 3
    assert m["unreadable_final_proposals"] == 3
    # only (a) is a violation found exclusively through the step-back.
    assert m["ibr_stepback_violations_n"] == 1


def test_primary_ibr_stepback_mirrors_tr3():
    """Same shape, the TR3 (decrease, low WSA) mirror of case (a)."""
    decisions = [_stepback_decision("d", [DEC, DEC, None], wsa="L")]
    m = vm.ibr_metrics(decisions)
    assert (m["ibr_tr1_count"], m["ibr_tr3_count"]) == (0, 1)
    assert (m["last_attempt_unparsed_n"], m["ibr_stepback_violations_n"]) == (1, 1)


def test_primary_ibr_stepback_does_not_affect_other_companions():
    """Item 37d changes only the primary (step-back) count: the executed
    share, the first-proposal share and the final-label IBR still read the
    literal last attempt / first attempt / executed skill, so an unparsed
    literal last attempt leaves them at their pre-item-37d values."""
    decisions = [_stepback_decision("a", [INC, INC, None], wsa="H")]
    m = vm.ibr_metrics(decisions)
    assert m["ibr_tr1_count"] == 1          # found via step-back
    assert m["ibr_first_proposal_tr1_count"] == 1   # attempt 0 was already an increase under WSA H
    assert m["ibr_executed_tr1_count"] == 0  # executed_skill is KEEP in this fixture
    assert m["ibr_final_label_tr1_pct"] == 0.0  # final_wsa is None (unparsed last attempt)
    assert m["unreadable_final_proposals"] == 1  # final_proposal (literal last attempt) is still None


def _strict_decisions_with_fallback_tr1(agent_year: Tuple[str, int] = ("LB1", 1)
                                        ) -> Dict[Tuple[str, int], Dict[str, Any]]:
    """STRICT_DECISIONS with ``agent_year`` replaced by a real
    REJECTED_FALLBACK row (execution_path "fallback"): two parsed
    increase attempts under WSA H (a live TR1 block each time), then an
    unparsed last attempt -- the CSV-round-trip shape of item 37d's
    worked example."""
    decisions = dict(STRICT_DECISIONS)
    decisions[agent_year] = dict(
        attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [TR1]),
                 (INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [TR1]),
                 (None, None, None)],
        executed=KEEP, status="REJECTED_FALLBACK", path="fallback")
    return decisions


def test_primary_ibr_steps_back_through_csv_round_trip(tmp_path):
    """Item 37d through the real audit CSV / ``parse_decision`` path (not a
    hand-built ``Decision``): a REJECTED_FALLBACK row whose last attempt is
    unparsed but an earlier one parsed as a TR1 violation."""
    run = vm.load_run(fixture_run(tmp_path, "strict", _strict_decisions_with_fallback_tr1()))
    d = run.decisions[("LB1", 1)]
    assert d.status == "REJECTED_FALLBACK" and d.execution_path == "fallback"
    assert not d.aborted and d.last_attempt_unparsed
    assert d.final_proposal is None and d.last_parsed_proposal == INC and d.first_wsa == "H"
    m = vm.ibr_metrics(run.ordered())
    # The original (LB1, 1) (d3) contributed 0 violations (final was KEEP);
    # replacing it with this fallback row adds exactly one TR1 violation,
    # found only by the step-back, beside d8's pre-existing one; TR3 (d2)
    # is untouched.
    assert (m["ibr_tr1_count"], m["ibr_tr3_count"]) == (2, 1)
    assert m["last_attempt_unparsed_n"] == 1
    assert m["ibr_stepback_violations_n"] == 1


def test_stepback_violations_never_exceed_unparsed_rows(strict_run, disabled_run, tmp_path):
    """Item 37d invariant: ``ibr_stepback_violations_n`` counts a SUBSET of
    ``last_attempt_unparsed_n`` (a step-back violation requires a
    last-attempt-unparsed row; the converse need not hold -- cases (b) and
    (c) of the hand-built test above are unparsed-tail rows with no
    violation), checked over several differently-shaped runs."""
    hand_built = vm.ibr_metrics([
        _stepback_decision("a", [INC, INC, None], wsa="H"),
        _stepback_decision("b", [INC, KEEP, None], wsa="H"),
        _stepback_decision("c", [None], wsa="H"),
        _stepback_decision("d", [DEC, DEC, None], wsa="L"),
    ])
    assert hand_built["ibr_stepback_violations_n"] <= hand_built["last_attempt_unparsed_n"]
    for run in (strict_run, disabled_run):  # no unparsed-tail rows: 0 <= 0
        m = vm.ibr_metrics(run.ordered())
        assert m["ibr_stepback_violations_n"] <= m["last_attempt_unparsed_n"]
    fallback_run = vm.load_run(
        fixture_run(tmp_path, "strict", _strict_decisions_with_fallback_tr1(), name="fallback_check"))
    m = vm.ibr_metrics(fallback_run.ordered())
    assert m["ibr_stepback_violations_n"] <= m["last_attempt_unparsed_n"]


def test_ibr_metrics_checks_the_unreadable_split_invariant():
    """Item 37d: ``ibr_metrics`` itself raises if ``unreadable_final_proposals``
    ever disagreed with ``#{ABORTED rows} + last_attempt_unparsed_n`` -- the
    only two disjoint reasons ``final_proposal`` can be None. Exercised here
    directly over a mix of an ABORTED decision, an unparsed-tail decision
    and an ordinary one; the check passes silently (no raise) when the
    split is consistent, which it always is by construction."""
    aborted = vm.Decision(
        agent_id="e", year=1, status="ABORTED", execution_path="aborted",
        executed_skill=None, proposed_skill="", attempts=(), retry_count=0, format_retries=0,
        llm_success=None, keep_request_af=None, expected_at_keep_af=None, supply_ratio=None,
        physical_ratio=None, first_wsa=None, first_aca=None, final_wsa=None, wsa_relabeled=False,
        error_messages="", timestamp="2026-10-07T00:00:00",
    )
    decisions = [_stepback_decision("a", [INC, INC, None], wsa="H"), aborted,
                _stepback_decision("d", [KEEP], wsa="M")]
    m = vm.ibr_metrics(decisions)  # would raise MetricsError on a split mismatch
    assert m["unreadable_final_proposals"] == 2  # "a" (unparsed tail) and the aborted row
    assert m["last_attempt_unparsed_n"] == 1     # "a" only; the aborted row has no attempts at all


# =============================================================================
# Items 10, 19: executed feasibility violations; census; exposure; agreement
# =============================================================================

def test_executed_violations_blocked_versus_executed(strict_run, disabled_run):
    strict = vm.executed_violations(strict_run)
    assert strict["exec_total_count"] == 0  # every blocked proposal ended in keep
    disabled = vm.executed_violations(disabled_run)
    # d5 and d8: increases executed while the supply condition held
    assert (disabled["exec_supply_count"], disabled["exec_cap_count"], disabled["exec_floor_count"]) == (2, 0, 0)
    assert disabled["exec_supply_pct"] == pytest.approx(200 / 9)
    assert disabled["exec_total_pct"] == pytest.approx(200 / 9)


def test_executed_cap_violation_counts_an_increase_at_the_cap(tmp_path):
    decisions = dict(DISABLED_DECISIONS)
    decisions[("LB1", 2)] = dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=INC)
    run = vm.load_run(fixture_run(tmp_path, "disabled", decisions))
    m = vm.executed_violations(run)
    assert (m["exec_cap_count"], m["exec_total_count"]) == (1, 3)


def test_rule_census_hand_computed(strict_run):
    census = {row["rule"]: row for row in vm.rule_census(strict_run)}
    assert {k: census[TR1][k] for k in ("condition_held", "first_attempt_violations",
                                        "final_proposal_violations", "executed_violations",
                                        "live_blocked_decisions")} == {
        "condition_held": 3, "first_attempt_violations": 2, "final_proposal_violations": 1,
        "executed_violations": 0, "live_blocked_decisions": 3}
    assert (census[TR3]["condition_held"], census[TR3]["first_attempt_violations"],
            census[TR3]["final_proposal_violations"], census[TR3]["live_blocked_decisions"]) == (2, 1, 1, 1)
    assert (census[SUP]["condition_held"], census[SUP]["first_attempt_violations"],
            census[SUP]["final_proposal_violations"], census[SUP]["live_blocked_decisions"]) == (2, 2, 1, 2)
    # the off-menu answer: the cap's condition held once, on d6; the ABORTED
    # row has no state_before, so its cap and floor conditions are unknown
    assert (census[CAP]["condition_held"], census[CAP]["condition_unknown"],
            census[CAP]["first_attempt_violations"], census[CAP]["final_proposal_violations"],
            census[CAP]["live_blocked_decisions"]) == (1, 1, 1, 0, 1)
    assert census[FLOOR]["condition_held"] == 0 and census[FLOOR]["enforcement"] == "live"


def test_supply_exposure_by_basin_and_period(tmp_path):
    """Mead reaches its dead pool at the end of year 2, so 1 January of year
    3 (2021) is the first dead-pool decision year."""
    run = vm.load_run(fixture_run(tmp_path, "strict", STRICT_DECISIONS,
                                  mead_ends=(13.0, CFG.mead_dead_pool_maf, CFG.mead_dead_pool_maf)))
    rows = {(r["basin"], r["period"]): r for r in vm.supply_exposure(run, CFG)}
    assert rows[("all", "all")]["mead_first_dead_pool_year"] == 2021
    assert (rows[("upper_basin", "all")]["agent_years"], rows[("upper_basin", "all")]["condition_held"]) == (6, 2)
    assert rows[("upper_basin", "all")]["condition_pct"] == pytest.approx(100 / 3)
    assert (rows[("upper_basin", "before_dead_pool")]["condition_held"],
            rows[("upper_basin", "from_dead_pool")]["condition_held"]) == (1, 1)
    assert rows[("lower_basin", "all")]["condition_pct"] == 0.0
    assert rows[("all", "all")]["live_blocked_decisions"] == 2


def test_agreement_zero_on_the_fixture_and_a_planted_disagreement(tmp_path, strict_run):
    agreement = vm.rule_agreement(strict_run)
    assert {rule: a["disagreements"] for rule, a in agreement.items()} == {
        r: 0 for r in vm.ALL_RULES if r != vm.RULE_BENEFICIAL_USE}  # legacy fixture
    # TR1 on d4's retry reads the WSA frozen at that attempt (VH, first stated there)
    assert agreement[TR1]["live"] == 2 + 1 + 4
    # plant a supply block where the condition does not hold
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 3)] = dict(attempts=[(INC, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [SUP]),
                                          (KEEP, {"WSA_LABEL": "L", "ACA_LABEL": "M"}, [])], executed=KEEP)
    planted = vm.rule_agreement(vm.load_run(fixture_run(tmp_path, "strict", decisions, name="planted")))
    assert planted[SUP]["disagreements"] == 1
    assert "LB1 year 3 attempt 0" in planted[SUP]["examples"][0]


def test_disabled_agreement_covers_only_its_live_rules(disabled_run):
    assert set(vm.rule_agreement(disabled_run)) == {CAP, FLOOR}


# =============================================================================
# Fail loudly
# =============================================================================

def _rewrite_audit(path: Path, edit) -> None:
    with open(path / vm.AUDIT_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    rows = edit(rows)
    vm.write_csv(path / vm.AUDIT_CSV, rows)


def test_missing_column_is_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    _rewrite_audit(path, lambda rows: [{k: v for k, v in r.items() if k != "attempt_labels"} for r in rows])
    with pytest.raises(vm.MetricsError, match="attempt_labels"):
        vm.load_run(path)


def test_unobserved_state_and_a_foreign_tolerance_are_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    _rewrite_audit(path, lambda rows: [{**r, "state_supply_physical_ratio": "unobserved"} for r in rows])
    with pytest.raises(vm.MetricsError, match="where a number is required"):
        vm.load_run(path)
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="other")
    _rewrite_audit(path, lambda rows: [{**r, "state_full_supply_ratio": "0.99"} for r in rows])
    with pytest.raises(vm.MetricsError, match="FULL_SUPPLY_RATIO"):
        vm.load_run(path)


def test_inconsistent_attempt_columns_are_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    _rewrite_audit(path, lambda rows: [{**r, "retry_count": "5"} if r["agent_id"] == "UB1" and r["year"] == "1"
                                       else r for r in rows])
    with pytest.raises(vm.MetricsError, match="retry_count"):
        vm.load_run(path)


def test_an_aborted_exception_row_is_an_aborted_decision(tmp_path, disabled_run):
    """The runner's sentinel for an agent step that raised (no prompt, no
    supply state, blank attempt cells) is a decision: in N, never a
    violation, a row with no readable decision under P8; its supply
    condition is unknown and counted apart."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[], executed=None, crashed=True)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions), keep_prompts=True)
    d, tr = run.decisions[("LB1", 1)], run.traces[("LB1", 1)]
    assert (d.aborted, d.crashed, d.final_proposal, d.supply_condition) == (True, True, None, None)
    assert tr.crashed and tr.prompt is None and tr.menu == ()
    m = vm.ibr_metrics(run.ordered())
    assert (m["decisions"], m["ibr_tr1_count"], m["ibr_tr3_count"], m["unreadable_final_proposals"]) == (9, 1, 1, 2)
    assert vm.executed_violations(run)["exec_total_count"] == 0
    p8 = vm.gate_p8([run], expected_rows=9)["details"][run.label]
    assert (p8["no_readable_decision"], p8["aborted_exception_rows"]) == (2, 1)
    census = {r["rule"]: r for r in vm.rule_census(run)}
    assert (census[SUP]["condition_unknown"], census[CAP]["condition_unknown"]) == (1, 2)
    lb = {(r["basin"], r["period"]): r for r in vm.supply_exposure(run, CFG)}[("lower_basin", "all")]
    assert (lb["agent_years"], lb["condition_unknown"], lb["condition_pct"]) == (3, 1, 0.0)
    # P5 and P6 skip the step that sent no prompt; P9 counts it with the ABORTED row
    p5 = vm.gate_p5([run], CFG, None, CFG.ub_subbasin_supply_variant)["details"]
    assert (p5["b_prompts"], p5["b_steps_without_a_prompt"]) == (8, 1)
    assert vm.reflection_checks(run)["reflection_lines"] == 0
    assert vm.gate_p9(run, disabled_run)["details"][run.label]["aborted_rows_unclassified"] == 2
    # the reading sample never picks it (LB1 was the only LB agent in 2019)
    assert vm.select_p5c_sample(run) == [("UB1", 1)]


def test_an_aborted_exception_row_with_attempts_is_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", {**STRICT_DECISIONS,
                                            ("LB1", 1): dict(attempts=[], executed=None, crashed=True)})
    _rewrite_audit(path, lambda rows: [{**r, "attempt_labels": "WSA_LABEL=H"} if r["status"] == vm.EXCEPTION_STATUS
                                       else r for r in rows])
    with pytest.raises(vm.MetricsError, match="ABORTED_EXCEPTION row with attempt_labels"):
        vm.load_run(path)


def test_audit_and_log_must_cover_the_same_agent_years(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    _rewrite_audit(path, lambda rows: rows[:-1])
    with pytest.raises(vm.MetricsError, match="cover different agent-years"):
        vm.load_run(path)


# =============================================================================
# Provenance guard (spec WP6 item 9)
# =============================================================================

def test_mixed_commit_is_refused_and_recorded_with_the_override(tmp_path):
    a = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=42))
    b = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=43, commit="d" * 40))
    with pytest.raises(vm.ProvenanceError, match="code commit differs"):
        vm.check_provenance([a, b])
    record = vm.check_provenance([a, b], allow_mixed=True)
    assert record["override_applied"] is True
    assert any("code commit differs" in d for d in record["differences"])


@pytest.mark.parametrize("change,message", [
    (lambda m: m.update(model="gemma3:4b"), "model differs"),
    (lambda m: m.update(memory_seed=7), "seed scheme"),
    (lambda m: m.update(lb_non_ag_total_maf=5.0), "water system differs in lb_non_ag_total_maf"),
    # Item 36e (2026-10-05); Opus review P2-2: a non-zero LB return-flow
    # CPU sensitivity run is refused when pooled with the (0.0) default.
    (lambda m: m.update(lb_return_flow_fraction=0.2), "water system differs in lb_return_flow_fraction"),
    (lambda m: m["coupling_retrofit_metadata"].update(water_system_hydrology_v3_sha256="0" * 64),
     "hydrology_v3_sha256"),
    (lambda m: m.update(hold_requests_fixed=True), "hold_requests_fixed"),
    (lambda m: m.update(run_status="aborted_llm_failure_rate"), "aborted"),
    # Opus review follow-up item 2: any run_status PREFIXED "aborted" is
    # refused, not only the LLM safeguard's own exact "aborted_llm_failure_rate"
    # -- this is a value the LLM safeguard never writes (it is
    # ExperimentRunner.run's own crash-resume-journal abort path), proving
    # the check is a prefix match rather than happening to special-case two
    # known literals.
    (lambda m: m.update(run_status="aborted_journal_divergence"), "aborted"),
    # Opus review follow-up item 1: a run's own `workers` can agree with
    # every other run in the pool while its `source_workers` (present only
    # on a resumed run; see broker.utils.llm_journal.LLMJournalManager.
    # provenance_metadata) reveals its replayed portion actually came from
    # a DIFFERENT worker count -- refused even though plain `workers` alone
    # (both manifests omit it here, matching llm_manifest()'s own baseline)
    # would see no difference at all.
    (lambda m: m.update(source_workers=4), "workers"),
    (lambda m: m.update(ub_supply_mode="lees_ferry_pool"), "water system differs in ub_supply_mode"),
    (lambda m: m.update(ub_subbasin_envelope_v3_sha256="0" * 64), "ub_subbasin_envelope_sha256"),
    (lambda m: m.update(ub_subbasin_variant_means_v3_sha256="0" * 64), "ub_subbasin_variant_means_sha256"),
    # spec 7.2 values, checked as values, not only compared across runs
    (lambda m: m.update(paper_water_margin=0.5), "paper_water_margin = 0.5; spec 7.2 requires 0.4"),
    (lambda m: m.update(cluster_method="legacy_centroid"), "spec 7.2 requires 'hy2021'"),
    (lambda m: m.update(ub_supply_mode="lees_ferry_pool"), "spec 7.2 requires 'subbasin'"),
    (lambda m: m.update(appraisal_freeze_resolved=False), "appraisal_freeze true"),
    (lambda m: m.pop("appraisal_freeze_resolved"), "appraisal_freeze true"),
    (lambda m: m.pop("step_bin_source"), "no step_bin_source"),
])
def test_provenance_guard_refusals(tmp_path, change, message):
    a = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=42))
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=43)
    manifest = json.loads((path / vm.MANIFEST).read_text(encoding="utf-8"))
    change(manifest)
    (path / vm.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(vm.ProvenanceError, match=message):
        vm.check_provenance([a, vm.read_run_info(path)])


@pytest.mark.parametrize("change,message", [
    ({"git_dirty": True}, "git_dirty=True"),
    ({"git_dirty": None}, "git_dirty=None"),
    ({"git_dirty_at_finalize": True}, "git_dirty_at_finalize=True"),
    ({"git_commit_at_finalize": "d" * 40}, "git_commit_at_finalize"),
])
def test_a_dirty_run_is_refused_unless_an_override_is_recorded(tmp_path, change, message):
    a = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=42))
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=43)
    manifest = json.loads((path / vm.MANIFEST).read_text(encoding="utf-8"))
    manifest.update(change)
    (path / vm.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    b = vm.read_run_info(path)
    with pytest.raises(vm.ProvenanceError, match=message):
        vm.check_provenance([a, b])
    record = vm.check_provenance([a, b], allow_dirty=True)
    assert record["allow_dirty"] is True and record["dirty_override_applied"] is True
    assert record["override_applied"] is False and record["differences"] == []
    assert len(record["dirty_runs"]) == 1 and record["dirty_runs"][0].startswith("strict_seed43")
    mixed = vm.check_provenance([a, b], allow_mixed=True)
    assert mixed["override_applied"] is True and any(message in d for d in mixed["differences"])


def test_llm_manifest_without_the_sub_basin_keys_is_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    manifest = json.loads((path / vm.MANIFEST).read_text(encoding="utf-8"))
    del manifest["ub_subbasin_supply_v3_sha256"]
    (path / vm.MANIFEST).write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(vm.MetricsError, match="ub_subbasin_supply_v3_sha256"):
        vm.check_provenance([vm.read_run_info(path)])


def test_llm_runner_records_the_sub_basin_keys_the_fql_runner_records(tmp_path):
    """Spec 7.2: the LLM runner writes ub_supply_mode, the variant and the
    two pinned table checksums; for the variant in use they are the values
    the FQL runner records, so the guard compares like with like."""
    from examples.irrigation_abm.run_experiment import _record_water_system_config_provenance
    from examples.irrigation_abm.run_fql_baseline import _pinned_v3_data_checksums
    manifest_path = tmp_path / "reproducibility_manifest.json"
    manifest_path.write_text(json.dumps({"seed": 42}), encoding="utf-8")
    config = WaterSystemConfig(ub_subbasin_supply_variant="rho_0_2")
    _record_water_system_config_provenance(tmp_path, config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    fql = _pinned_v3_data_checksums("rho_0_2")
    assert manifest["ub_supply_mode"] == config.ub_supply_mode
    assert manifest["ub_subbasin_supply_variant"] == "rho_0_2"
    assert manifest["ub_subbasin_supply_v3_sha256"] == fql["ub_subbasin_supply_v3_csv"]
    assert manifest["ub_subbasin_supply_v3_sha256"] == _UB_SUBBASIN_SUPPLY_VARIANT_FILES["rho_0_2"][1]
    assert manifest["ub_subbasin_supply_v3_sha256"] != _UB_SUBBASIN_SUPPLY_VARIANT_FILES["recommended"][1]
    assert manifest["ub_subbasin_envelope_v3_sha256"] == fql["ub_subbasin_envelope_v3_csv"]
    assert manifest["ub_subbasin_envelope_v3_sha256"] == UB_SUBBASIN_ENVELOPE_SHA256
    assert manifest["ub_subbasin_variant_means_v3_sha256"] == fql["ub_subbasin_variant_means_v3_csv"]
    assert manifest["ub_subbasin_variant_means_v3_sha256"] == UB_SUBBASIN_VARIANT_MEANS_SHA256


def test_llm_runner_keeps_the_other_keys_when_the_checksum_lookup_fails(tmp_path, monkeypatch, capsys):
    from examples.irrigation_abm import irrigation_env
    from examples.irrigation_abm.run_experiment import _record_water_system_config_provenance
    manifest_path = tmp_path / "reproducibility_manifest.json"
    manifest_path.write_text(json.dumps({"seed": 42}), encoding="utf-8")
    config = WaterSystemConfig()
    monkeypatch.setattr(irrigation_env, "_UB_SUBBASIN_SUPPLY_VARIANT_FILES", {})
    _record_water_system_config_provenance(tmp_path, config)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["powell_release_mode"] == config.powell_release_mode
    assert manifest["ub_supply_mode"] == config.ub_supply_mode
    assert manifest["ub_subbasin_supply_variant"] == config.ub_subbasin_supply_variant
    assert "ub_subbasin_supply_v3_sha256" not in manifest
    assert "ub_subbasin_envelope_v3_sha256" not in manifest
    assert "ub_subbasin_variant_means_v3_sha256" not in manifest
    assert "sub-basin table checksums" in capsys.readouterr().out


def test_fql_reference_must_be_raw_and_share_the_commit(tmp_path):
    run = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS))
    fql = fql_manifest(42, agents=sorted(AGENTS))
    fql["no_governance"] = False
    sims = sim_rows(system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1)),
                    {(a, t): {} for a in AGENTS for t in (1, 2, 3)})
    info = vm.read_run_info(write_run(tmp_path / "fql", fql, sims))
    with pytest.raises(vm.ProvenanceError, match="raw FQL"):
        vm.check_provenance([run, info])


def test_fql_nonzero_return_flow_fraction_refused_against_the_default_reference(tmp_path):
    """Item 36e (2026-10-05); Opus review P2-2: an FQL/replay manifest
    whose water_system_config.lb_return_flow_fraction is non-zero is
    refused when pooled against the analysis's own default (0.0) --
    through the generic full-dataclass-dump comparison
    (check_provenance), which needs no per-key wiring since
    dataclasses.asdict(WaterSystemConfig(...)) already carries every
    field, including this one."""
    run = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS))
    fql = fql_manifest(42, agents=sorted(AGENTS))
    fql["water_system_config"]["lb_return_flow_fraction"] = 0.2
    sims = sim_rows(system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1)),
                    {(a, t): {} for a in AGENTS for t in (1, 2, 3)})
    info = vm.read_run_info(write_run(tmp_path / "fql", fql, sims))
    with pytest.raises(vm.ProvenanceError, match="lb_return_flow_fraction"):
        vm.check_provenance([run, info])


def test_fql_nonzero_min_utilisation_fraction_refused_against_the_default_reference(tmp_path):
    """2026-10-06 CPU rerun finding: same treatment as
    test_fql_nonzero_return_flow_fraction_refused_against_the_default_reference
    just above -- an FQL/replay manifest whose
    water_system_config.min_utilisation_fraction differs from the
    analysis's own default (0.10) is refused when pooled, through the
    same generic full-dataclass-dump comparison (check_provenance)."""
    run = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS))
    fql = fql_manifest(42, agents=sorted(AGENTS))
    fql["water_system_config"]["min_utilisation_fraction"] = 0.0
    sims = sim_rows(system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1)),
                    {(a, t): {} for a in AGENTS for t in (1, 2, 3)})
    info = vm.read_run_info(write_run(tmp_path / "fql", fql, sims))
    with pytest.raises(vm.ProvenanceError, match="min_utilisation_fraction"):
        vm.check_provenance([run, info])


def test_p56_tier_sensitivity_cannot_be_pooled_with_the_default(tmp_path):
    run = vm.read_run_info(fixture_run(tmp_path, "strict", STRICT_DECISIONS))
    fql = fql_manifest(42, agents=sorted(AGENTS))
    fql["lb_p56_in_tier"] = "proportional"
    fql["water_system_config"]["lb_p56_in_tier"] = "proportional"
    sims = sim_rows(system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1)),
                    {(a, t): {} for a in AGENTS for t in (1, 2, 3)})
    info = vm.read_run_info(write_run(tmp_path / "fql_p56", fql, sims))
    with pytest.raises(vm.ProvenanceError, match="lb_p56_in_tier"):
        vm.check_provenance([run, info])


@pytest.mark.parametrize("kind", ["llm", "fql"])
def test_pre_ceiling_manifests_get_checksum_gated_historical_p56_marker(tmp_path, kind):
    if kind == "llm":
        manifest = llm_manifest("strict", agents=sorted(AGENTS))
        manifest.pop("lb_p56_in_tier")
        manifest["coupling_retrofit_metadata"]["water_system_lb_priority_split_sha256"] = (
            OLD_LB_PRIORITY_SPLIT_SHA256)
    else:
        manifest = fql_manifest(42, agents=sorted(AGENTS))
        manifest.pop("lb_p56_in_tier")
        manifest["water_system_config"].pop("lb_p56_in_tier")
        manifest["pinned_v3_data_checksums"]["lb_priority_split_v3_csv"] = (
            OLD_LB_PRIORITY_SPLIT_SHA256)
    info = vm.read_run_info(write_run(tmp_path / kind, manifest, []))
    assert vm.water_system_signature(info)["lb_p56_in_tier"] == "legacy_request_proportional"


@pytest.mark.parametrize("kind", ["llm", "fql"])
def test_current_split_manifest_missing_p56_mode_fails_loudly(tmp_path, kind):
    if kind == "llm":
        manifest = llm_manifest("strict", agents=sorted(AGENTS))
        manifest.pop("lb_p56_in_tier")
    else:
        manifest = fql_manifest(42, agents=sorted(AGENTS))
        manifest.pop("lb_p56_in_tier")
        manifest["water_system_config"].pop("lb_p56_in_tier")
    info = vm.read_run_info(write_run(tmp_path / kind, manifest, []))
    with pytest.raises(vm.MetricsError, match="lb_p56_in_tier"):
        vm.water_system_signature(info)


def test_missing_manifest_is_refused(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS)
    (path / vm.MANIFEST).unlink()
    with pytest.raises(vm.MetricsError, match="without provenance"):
        vm.read_run_info(path)


# =============================================================================
# KGE, the FQL benchmark, statistics
# =============================================================================

def test_kge_hand_computed():
    k = vm.kge([1.0, 2.0, 3.0, 4.0], [2.0, 4.0, 6.0, 8.0])
    # r = 1, alpha = 0.5, beta = 0.5: KGE = 1 - sqrt(0.5)
    assert (k.r, k.alpha, k.beta) == pytest.approx((1.0, 0.5, 0.5))
    assert k.kge == pytest.approx(1.0 - 0.5 ** 0.5)


def test_kge_undefined_cases_and_the_constant_series_convention():
    assert vm.kge([1.0, 2.0], [1.0, 2.0]).note.startswith("fewer than")
    assert vm.kge([1.0, 2.0, 3.0], [5.0, 5.0, 5.0]).note == "reference series is constant"
    assert vm.kge([1.0, 2.0, 3.0], [-1.0, 0.0, 1.0]).note == "reference mean is zero"
    # a constant simulated series against a moving reference: r := 0 and
    # alpha := 0, beta = 3 / (7 / 3), KGE = 1 - sqrt(2 + (beta - 1)^2)
    k = vm.kge([3.0, 3.0, 3.0], [1.0, 2.0, 4.0])
    assert (k.r, k.alpha, k.note) == (0.0, 0.0, vm.CONSTANT_SIM_NOTE)
    assert k.beta == pytest.approx(9 / 7)
    assert k.kge == pytest.approx(1.0 - (2.0 + (2 / 7) ** 2) ** 0.5)
    # identical sums that differ only by rounding still count as constant
    k = vm.kge([0.1 + 0.2, 0.3, 0.30000000000000004], [1.0, 2.0, 4.0])
    assert k.note == vm.CONSTANT_SIM_NOTE and k.r == 0.0


def test_lb_agent_summary_scores_constant_agents_and_counts_them():
    kges = {"lb_agent_request_af:A": vm.kge([5.0, 5.0, 5.0], [1.0, 2.0, 4.0]),   # constant: scored
            "lb_agent_request_af:B": vm.kge([1.0, 2.0, 4.0], [1.0, 2.0, 4.0]),   # 1.0
            "lb_agent_request_af:C": vm.kge([1.0, 2.0, 4.0], [3.0, 3.0, 3.0]),   # constant reference
            "lb_request_maf": vm.kge([1.0, 2.0, 4.0], [1.0, 2.0, 4.0])}
    s = vm.lb_agent_summary(kges)
    assert (s["defined"], s["constant_sim"], s["undefined"]) == (2, 1, 1)
    assert s["median"] == pytest.approx((kges["lb_agent_request_af:A"].kge + 1.0) / 2)


def test_system_series_carries_the_aggregate_totals(strict_run):
    """Item 30: the headline KGE is on Mead, aggregate use (UB+LB) and the UB."""
    series = vm.system_series(strict_run.sim)
    for year in series["mead_jan1_ft"]:
        for what in ("request", "delivered"):
            assert series[f"total_{what}_maf"][year] == pytest.approx(
                series[f"ub_{what}_maf"][year] + series[f"lb_{what}_maf"][year])
    assert {"total_request_maf", "total_delivered_maf"} <= set(vm.HEADLINE_SERIES)
    assert "UB+LB request TOTAL" in vm.series_label("total_request_maf")
    assert "kge_total_request_maf" in vm.PAIRED_METRICS


def _fql_run(tmp_path: Path, seed: int, requests: Sequence[float]) -> vm.LoadedRun:
    system = system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1))
    years = {(a, t): {"request": requests[t - 1] if a == "LB1" else 1000.0} for a in AGENTS for t in (1, 2, 3)}
    path = write_run(tmp_path / f"fql{seed}", fql_manifest(seed, agents=sorted(AGENTS)), sim_rows(system, years))
    return vm.load_run(path)


def test_reference_mean_and_leave_one_out_benchmark(tmp_path):
    runs = [_fql_run(tmp_path, s, r) for s, r in ((42, (1000, 1100, 1200)), (43, (1000, 1200, 1400)),
                                                  (44, (1000, 1300, 1600)))]
    ref = vm.build_reference(runs)
    assert ref.mean["lb_agent_request_af:LB1"] == {2019: 1000, 2020: 1200, 2021: 1400}
    bench = vm.reference_benchmark(ref)
    # seed 42 against the mean of 43 and 44 (1000, 1250, 1500): r = 1,
    # beta = 1100 / 1250, alpha = 100 / 250
    expected = 1.0 - ((1100 / 1250 - 1) ** 2 + (100 / 250 - 1) ** 2) ** 0.5
    assert bench[42]["lb_agent_request_af:LB1"].kge == pytest.approx(expected)
    assert bench[42]["lb_request_maf"].kge == pytest.approx(expected)
    # UB requests are constant in every seed: no KGE, with the reason
    assert bench[42]["ub_request_maf"].note == "reference series is constant"
    # item 30: the LB request TOTAL benchmark is labelled as such, and the
    # LB agent's own ceiling is the median of its leave-one-out KGE
    rows, summary, per_seed, ceilings = vm.benchmark_tables(ref)
    total = next(s for s in summary if s["series"] == "lb_request_maf")
    assert "TOTAL" in total["label"] and "item 30" in total["label"]
    assert total["median"] == pytest.approx(sorted(bench[s]["lb_request_maf"].kge for s in bench)[1])
    assert ceilings["LB1"]["ceiling"] == pytest.approx(
        sorted(bench[s]["lb_agent_request_af:LB1"].kge for s in bench)[1])


def test_lb_agent_ceilings_are_computed_per_agent():
    def k(value):
        return vm.Kge(value, None, None, None, 5)
    bench = {42: {"lb_agent_request_af:A": k(0.1), "lb_agent_request_af:B": k(0.5), "lb_request_maf": k(0.9)},
             43: {"lb_agent_request_af:A": k(0.3), "lb_agent_request_af:B": k(None), "lb_request_maf": k(0.2)},
             44: {"lb_agent_request_af:A": k(0.2), "lb_agent_request_af:B": k(0.7), "lb_request_maf": k(0.4)}}
    assert vm.lb_agent_ceilings(bench) == {
        "A": {"ceiling": 0.2, "seeds_defined": 3, "seeds": 3},
        "B": {"ceiling": 0.6, "seeds_defined": 2, "seeds": 3}}
    assert vm.series_label("lb_agent_request_af:A") == "LB agent A request"


def test_sign_flip_test_exact_values():
    t = vm.sign_flip_test([1.0, 2.0, 3.0, 4.0, 5.0])
    assert (t["p_two_sided"], t["p_floor"], t["zero_diffs"]) == (0.0625, 0.0625, 0)
    assert vm.sign_flip_test([3.0, -1.0, 2.0])["p_two_sided"] == 0.5
    assert vm.sign_flip_test([1.0, -1.0])["p_two_sided"] == 1.0
    assert vm.sign_flip_test([2.0])["p_two_sided"] is None
    # a zero difference keeps its value under either sign: with z zeros the
    # floor is 2^(z + 1) / 2^n, here 4 / 32, and these diffs attain it
    t = vm.sign_flip_test([0.0, 1.0, 2.0, 3.0, 4.0])
    assert (t["zero_diffs"], t["p_floor"], t["p_two_sided"]) == (1, 0.125, 0.125)
    t = vm.sign_flip_test([0.0, 0.0, 0.0])
    assert (t["p_floor"], t["p_two_sided"]) == (1.0, 1.0)


def test_describe():
    d = vm.describe([1.0, 3.0, None])
    assert (d["n"], d["n_missing"], d["mean"], d["median"], d["min"], d["max"]) == (2, 1, 2.0, 2.0, 1.0, 3.0)
    assert d["sd"] == pytest.approx(2 ** 0.5)
    assert vm.describe([5.0])["sd"] is None
    assert vm.describe([1.0, 2.0, 9.0])["median"] == 2.0


# =============================================================================
# Reservoir outcomes and R4
# =============================================================================

def test_reservoir_outcomes_hand_computed(strict_run):
    r = vm.reservoir_outcomes(strict_run.sim, CFG)
    assert r["mead_min_ft"] == pytest.approx(vm.mead_elevation_ft(11.5))
    assert r["mead_min_jan1_year"] == 2022  # the end of 2021
    assert (r["tier0_years"], r["tier1_years"], r["tier3_years"]) == (2, 1, 0)
    assert r["mead_dead_pool_dates"] == [] and r["powell_dead_pool_dates"] == []


def test_dead_pool_dates(tmp_path):
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS,
                       mead_ends=(13.0, CFG.mead_dead_pool_maf, CFG.mead_dead_pool_maf + 1e-7))
    r = vm.reservoir_outcomes(vm.load_sim_log(path), CFG)
    assert r["mead_dead_pool_dates"] == [2021, 2022] and r["mead_first_dead_pool_jan1"] == 2021


def _patch_ub_supply(monkeypatch, a_s: Dict[str, Dict[int, float]], variant: Optional[str] = None) -> None:
    """Monkeypatch vm._load_ub_subbasin_supply_table (the module's existing,
    checksum-pinned data access for A_s(t)) to return a_{sb}_af =
    a_s[sb][sim_year], instead of reading the committed CSV. ``a_s`` is
    keyed by sub-basin then by the real sim_year (CFG.sim_start_year + loop
    year - 1). Used by every test below that needs a controlled A_s trace
    (item 34: dry years now come from A_s, never from a settled,
    post-decision ub_subbasin_ratio)."""
    variant = variant or CFG.ub_subbasin_supply_variant

    def fake(v: str) -> Dict[int, Dict[str, float]]:
        assert v == variant, f"expected variant {variant!r}, got {v!r}"
        years = sorted({y for series in a_s.values() for y in series})
        return {y: {"source_calendar_year": y,
                    **{f"a_{sb}_af": series[y] for sb, series in a_s.items() if y in series}}
                for y in years}

    monkeypatch.setattr(vm, "_load_ub_subbasin_supply_table", fake)


def _recovery_sim(monkeypatch, tmp_path: Path, a_s: Sequence[float], requests: Sequence[float],
                  ratio: float = 1.0) -> vm.SimLog:
    """A UT1 sim (UB1 + UB2) of len(a_s) years for drought_recovery tests.
    Dry years now come from A_s (monkeypatched via _patch_ub_supply), never
    from ub_subbasin_ratio, which this sim holds at a constant ``ratio``
    (irrelevant to the dry-year definition; see
    test_ub_subbasin_dry_years_independent_of_agent_behaviour). ``requests``
    is the sub-basin's total request each year, for the recovery reference."""
    n = len(a_s)
    hydrology = _load_hydrology_table()
    system = system_years(n, [13.0] * n, [11.0] * n, [0] * n)
    for t in system:
        system[t]["calendar_year"] = hydrology[CFG.sim_start_year + t - 1]["source_calendar_year"]
    _patch_ub_supply(monkeypatch, {"UT1": {CFG.sim_start_year + t - 1: a_s[t - 1] for t in range(1, n + 1)}})
    years = {("UB1", t): {"ub_subbasin_ratio": ratio, "request": requests[t - 1] / 2}
             for t in range(1, n + 1)}
    years.update({("UB2", t): {"ub_subbasin_ratio": ratio, "request": requests[t - 1] / 2}
                  for t in range(1, n + 1)})
    path = write_run(tmp_path / "r4", fql_manifest(42), sim_rows(system, years))
    return vm.load_sim_log(path)


def test_drought_recovery_hand_computed(monkeypatch, tmp_path):
    """A_s(UT1) = [100,100,20,25,100,100,100,100]: the 20th percentile of
    this 8-year trace is 55.0 (verified against numpy directly), so years 3
    and 4 (values 20, 25) are dry -- a 2-year spell, identical to whatever
    ub_subbasin_ratio the agents happened to settle at (item 34)."""
    sim = _recovery_sim(monkeypatch, tmp_path, [100, 100, 20, 25, 100, 100, 100, 100],
                        [100, 100, 90, 80, 90, 101, 105, 110])
    (spell,) = vm.drought_recovery(sim, CFG, "x", "strict")
    assert (spell["subbasin"], spell["start_year"], spell["end_year"], spell["dry_years"]) == (
        "UT1", 2021, 2022, 2)
    # reference: year 2's total, 100; year 5 has 90, year 6 has 101, so j = 2
    assert (spell["reference_request_af"], spell["status"], spell["recovery_years"]) == (100, "recovered", 2)


@pytest.mark.parametrize("a_s,requests,status,censored_by", [
    # dry at year 1 only: starts in year 1, skipped (no reference).
    ([10, 1000, 1010, 1020, 1030], [100, 90, 100, 100, 100], "no reference", ""),
    # dry at year 2 only; years 3-5 never reach the year-1 reference (100).
    ([1000, 10, 1020, 1030, 1040], [100, 90, 95, 96, 97], "censored", "end of run"),
    # dry at years 2 and 5 (separate 1-year spells): the first spell's
    # recovery search (years 3-4, below reference) is interrupted by the
    # second spell starting at year 5.
    ([1000, 10, 1020, 1030, 11, 1040, 1050, 1060], [100, 90, 95, 96, 80, 120, 105, 110],
     "censored", "next spell"),
    # dry at years 2-3 (one 2-year spell); year 3's request (101) is ABOVE
    # the year-1 reference (100) but is INSIDE the spell, so it must not
    # trigger an early "recovered" -- recovery is only checked from year 4.
    ([1000, 10, 11, 1020, 1030, 1040, 1050, 1060], [100, 90, 101, 100, 105, 110, 115, 120],
     "recovered", ""),
])
def test_drought_recovery_censored_and_skipped(monkeypatch, tmp_path, a_s, requests, status, censored_by):
    spell = vm.drought_recovery(_recovery_sim(monkeypatch, tmp_path, a_s, requests), CFG, "x", "strict")[0]
    assert (spell["status"], spell["censored_by"]) == (status, censored_by)
    if status == "recovered":
        assert spell["recovery_years"] == 1  # j counts from the last spell year


def test_drought_recovery_compares_float_safely(monkeypatch, tmp_path):
    """The reference total 0.1 + 0.2 = 0.30000000000000004 and a later total
    of exactly 0.3 count as equal: recovered, not censored. A_s = [1000, 10,
    1020] is dry at year 2 only (verified against numpy)."""
    spell = vm.drought_recovery(
        _recovery_sim(monkeypatch, tmp_path, [1000, 10, 1020], [0.1 + 0.2, 0.1, 0.3]), CFG, "x", "strict")[0]
    assert spell["reference_request_af"] > 0.3
    assert (spell["status"], spell["recovery_years"]) == ("recovered", 1)


def test_recovery_table_per_subbasin_and_pooled():
    def spell(run, arm, sb, status, years=None):
        return {"run": run, "arm": arm, "subbasin": sb, "status": status, "recovery_years": years}
    spells = [spell("a", "strict", "UT1", "recovered", 1), spell("a", "strict", "UT1", "recovered", 3),
              spell("b", "strict", "WY", "censored"), spell("b", "strict", "WY", "no reference"),
              spell("f", "fql", "UT1", "recovered", 2)]
    rows = {(r["arm"], r["subbasin"]): r for r in vm.recovery_table(spells, ["strict", "disabled", "fql"])}
    keys = ("r4_spells", "r4_recovered", "r4_censored", "r4_median_recovery_years", "r4_no_reference")
    assert tuple(rows[("strict", "UT1")][k] for k in keys) == (2, 2, 0, 2.0, 0)
    assert tuple(rows[("strict", "WY")][k] for k in keys) == (1, 0, 1, None, 1)
    assert tuple(rows[("strict", "pooled")][k] for k in keys) == (3, 2, 1, 2.0, 1)
    assert tuple(rows[("disabled", "pooled")][k] for k in keys) == (0, 0, 0, None, 0)  # no spell, still a row
    assert tuple(rows[("fql", "pooled")][k] for k in keys) == (1, 1, 0, 2.0, 0)


def test_ub_subbasin_dry_years_independent_of_agent_behaviour(monkeypatch, tmp_path):
    """The reviewer's point (item 34): dry years come only from A_s
    (hydrology), never from the settled ub_subbasin_ratio. Two sims that
    differ only in their agents' settled ratios (as strict vs disabled
    might, or a run that increases a lot vs one that never does) get the
    identical dry-year set."""
    a_s = [100, 100, 20, 25, 100, 100, 100, 100]
    requests = [100] * 8
    sim_never_short = _recovery_sim(monkeypatch, tmp_path / "a", a_s, requests, ratio=1.0)
    sim_always_short = _recovery_sim(monkeypatch, tmp_path / "b", a_s, requests, ratio=0.3)
    dry_a = vm.ub_subbasin_dry_years(sim_never_short, CFG)
    dry_b = vm.ub_subbasin_dry_years(sim_always_short, CFG)
    assert dry_a == dry_b == {"UT1": {3, 4}}


def test_ub_subbasin_dry_years_uses_the_full_table_not_the_runs_own_years(monkeypatch, tmp_path):
    """Item 34: the dry-year threshold is the UB_DRY_YEAR_PERCENTILE-th
    percentile of the FULL ub_subbasin_supply_v3 table for the variant (the
    "42-year trace"), not of whatever years one run happens to cover.
    A_s(UT1) = [60,60,60,60,20,20,20,20] over the full 8-year table gives
    threshold 20.0 exactly (verified against numpy), so years 5-8 (value
    20, not STRICTLY below 20) are NOT dry. A short run covering only years
    1-5 ([60,60,60,60,20]), if it wrongly computed its own percentile from
    just those 5 values, would get threshold 52.0 and flag year 5 as dry
    (also verified against numpy); using the full table's threshold it
    correctly has none."""
    full_a_s = {CFG.sim_start_year + t - 1: v for t, v in
               enumerate([60, 60, 60, 60, 20, 20, 20, 20], start=1)}
    _patch_ub_supply(monkeypatch, {"UT1": full_a_s})
    n = 5
    system = system_years(n, [13.0] * n, [11.0] * n, [0] * n)
    years = {("UB1", t): {"ub_subbasin_ratio": 1.0, "request": 50.0} for t in range(1, n + 1)}
    years.update({("UB2", t): {"ub_subbasin_ratio": 1.0, "request": 50.0} for t in range(1, n + 1)})
    path = write_run(tmp_path / "short", fql_manifest(42), sim_rows(system, years))
    short_sim = vm.load_sim_log(path)
    assert vm.ub_subbasin_dry_years(short_sim, CFG) == {"UT1": set()}


# =============================================================================
# R5 (item 33c; pre-registered 2026-10-01; item 34, 2026-10-01: fixes to the
# dry-year definition, R5d and some smaller gaps): report-only, never gated.
# =============================================================================

def test_r5a_headline_band_edges():
    """The middle band is "moderately_short", not "short" (Opus review
    P3-6, 2026-10-06): since item 36a the prompt's own headline is two
    states, "sufficient" and "short", and a bare "short" ANALYSIS bin
    here would read as if it were that same prompt state."""
    f = personas.FULL_SUPPLY_RATIO
    assert vm.r5a_headline_band(f) == "sufficient"
    assert vm.r5a_headline_band(f - 1e-9) == "slightly_short"
    assert vm.r5a_headline_band(0.95) == "slightly_short"
    assert vm.r5a_headline_band(0.95 - 1e-9) == "moderately_short"
    assert vm.r5a_headline_band(0.80) == "moderately_short"
    assert vm.r5a_headline_band(0.80 - 1e-9) == "well_short"
    assert vm.r5a_headline_band(0.50) == "well_short"
    assert vm.r5a_headline_band(0.50 - 1e-9) == "critical"


def test_r5a_band_edges_are_the_five_retired_prompt_bands():
    """Item 36a (2026-10-05 design-basis audit + fix proposals, spec item
    36a): irrigation_personas.build_water_situation_text's headline
    collapsed from five bands to two (sufficient / short) at
    FULL_SUPPLY_RATIO; its source no longer states 0.95/0.80/0.50 at all,
    so r5a_headline_band's three interior edges can no longer be
    cross-checked against that function's source (the pre-2026-10-05 form
    of this test). This instead pins r5a_headline_band's own literals
    directly, so the five REPORT-ONLY bins (R5A_BANDS) stay exactly what
    the pre-item-36a prompt headline used to print, for the pre-registered
    R5a analysis. FULL_SUPPLY_RATIO, the top edge, is still imported,
    never copied, in both functions."""
    src = inspect.getsource(personas.build_water_situation_text)
    # No numeric literal threshold on r_share remains in the prompt
    # function -- only the symbolic FULL_SUPPLY_RATIO edge.
    assert re.findall(r"r_share >= (0\.\d+)", src) == []
    assert "r_share >= FULL_SUPPLY_RATIO" in src
    src_r5a = inspect.getsource(vm.r5a_headline_band)
    found = [float(x) for x in re.findall(r"r_share >= (0\.\d+)", src_r5a)]
    assert found == [0.95, 0.80, 0.50]


def test_r5b_window_matches_config():
    """R5b's K window must be the dashboard's own trend_window (item 34),
    never a copy of that number."""
    vm.assert_short_year_window_matches_config()


def test_r5b_window_mismatch_is_refused(tmp_path):
    import yaml as _yaml
    raw = _yaml.safe_load(vm.CONFIG_PATH.read_text(encoding="utf-8"))
    raw["irrigation_farmer"]["feedback"]["trend_window"] = 3
    bad = tmp_path / "agent_types.yaml"
    bad.write_text(_yaml.dump(raw), encoding="utf-8")
    with pytest.raises(vm.MetricsError, match="trend_window"):
        vm.assert_short_year_window_matches_config(bad)


def test_r5a_wsa_by_band_hand_computed(strict_run):
    """Band "sufficient" (ratio 1.0): d1(H), d2(L), d3(M), d4(VH), d6(M),
    d7(ABORTED, missing), d9(L) = 7 decisions. Band "moderately_short"
    (ratio 0.9, the supply rule's condition; renamed from "short", Opus
    review P3-6, 2026-10-06): d5(M), d8(H) = 2 decisions."""
    rows = vm.r5a_wsa_by_band(strict_run)
    assert len(rows) == 35  # 5 real bands x 7 wsa categories, always emitted
    assert sum(r["decisions"] for r in rows) == 9
    by_cell = {(r["band"], r["first_wsa"]): r["decisions"] for r in rows}
    assert by_cell[("sufficient", "H")] == 1 and by_cell[("sufficient", "L")] == 2
    assert by_cell[("sufficient", "M")] == 2 and by_cell[("sufficient", "VH")] == 1
    assert by_cell[("sufficient", "VL")] == 0 and by_cell[("sufficient", "missing")] == 1  # d7
    assert by_cell[("sufficient", "off_scale")] == 0
    assert by_cell[("moderately_short", "H")] == 1 and by_cell[("moderately_short", "M")] == 1
    assert by_cell[("moderately_short", "VL")] == 0
    assert by_cell[("slightly_short", "VL")] == 0  # an empty band still gets its zero cells
    assert by_cell[("critical", "missing")] == 0


def test_r5a_unknown_band_for_aborted_exception(tmp_path):
    """The ABORTED_EXCEPTION sentinel logs no supply state: it has no band
    (r5a_headline_band needs a ratio) and is counted under
    "unknown_no_supply_state", never dropped."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[], executed=None, crashed=True)  # was d3, WSA=M, "sufficient"
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions), keep_prompts=True)
    rows = {(r["band"], r["first_wsa"]): r["decisions"] for r in vm.r5a_wsa_by_band(run)}
    assert rows[("unknown_no_supply_state", "missing")] == 1
    assert rows[("sufficient", "M")] == 1  # d6 only now; d3 moved to "unknown"
    assert sum(rows.values()) == 9


def test_r5a_band_summary_emits_unknown_band(tmp_path):
    """Reviewer fix, 2026-10-01: a pooled r5a_band_summary must still show
    the "unknown_no_supply_state" band for an arm that has one -- it was
    silently dropped from the pooled summary before, even though the
    per-run table (r5a_wsa_by_band) already counted it."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[], executed=None, crashed=True)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions), keep_prompts=True)
    pooled = vm.r5a_band_summary(vm.r5a_wsa_by_band(run), ["strict"])
    unknown = [r for r in pooled if r["band"] == "unknown_no_supply_state"]
    assert unknown and sum(r["decisions"] for r in unknown) == 1
    assert next(r for r in unknown if r["first_wsa"] == "missing")["decisions"] == 1


def test_r5a_off_scale_wsa_is_counted_separately(tmp_path):
    """A first-stated WSA that is neither blank nor one of the five
    construct levels is counted under "off_scale", never merged with
    "missing" (reviewer fix, 2026-10-01: the ibr_metrics split of
    first_wsa_missing from first_wsa_off_scale)."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[(KEEP, {"WSA_LABEL": "MAYBE", "ACA_LABEL": "M"}, [])], executed=KEEP)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions), keep_prompts=True)
    assert run.decisions[("LB1", 1)].first_wsa == "MAYBE"
    rows = {(r["band"], r["first_wsa"]): r["decisions"] for r in vm.r5a_wsa_by_band(run)}
    assert rows[("sufficient", "off_scale")] == 1  # was d3, WSA=M; now off-scale
    assert rows[("sufficient", "M")] == 1  # d6 only
    assert rows[("sufficient", "missing")] == 1  # d7, still ABORTED


def test_r5b_wsa_by_short_years_hand_computed(strict_run):
    """K = short years (ratio < FULL_SUPPLY_RATIO) among up to 5 prior shown
    years. Year 1 decisions (d1, d2, d3) have no prior year: no_window.
    K=0: d4(VH=5), d5(M=3), d6(M=3), d9(L=2) valid, plus d7 ABORTED (also
    K=0, since UB1 was never short in years 1-2). K=1: d8(H=4), because
    UB2 was short (ratio 0.9) in year 2. The fixture only has 3 years, so
    the window never reaches R5B_SHORT_YEAR_WINDOW (5): every real bucket is
    full_window=False."""
    rows = {(r["k_short_years"], r["full_window"]): r for r in vm.r5b_wsa_by_short_years(strict_run)}
    k0 = rows[(0, False)]
    assert (k0["n_in_mean"], k0["sum_first_wsa"], k0["aborted_excluded"], k0["blank_wsa_excluded"],
            k0["off_scale_excluded"]) == (4, 13, 1, 0, 0)
    assert k0["mean_first_wsa"] == pytest.approx(3.25)
    k1 = rows[(1, False)]
    assert (k1["n_in_mean"], k1["sum_first_wsa"]) == (1, 4)
    assert k1["mean_first_wsa"] == pytest.approx(4.0)
    for k in (2, 3, 4, 5):
        assert rows[(k, False)]["n_in_mean"] == 0 and rows[(k, False)]["mean_first_wsa"] is None
        assert rows[(k, True)]["n_in_mean"] == 0  # full_window never occurs in a 3-year fixture
    no_window = rows[("no_window", None)]
    assert no_window["no_window_excluded"] == 3  # UB1/UB2/LB1 year 1
    assert sum(r["n_in_mean"] + r["aborted_excluded"] + r["blank_wsa_excluded"] + r["off_scale_excluded"]
              for r in rows.values()) + no_window["no_window_excluded"] == 9


def test_r5b_blank_wsa_is_excluded_and_counted(tmp_path):
    """A decision whose only attempt states no WSA at all (not a relabel,
    not a fallback: genuinely never stated) is excluded from the mean and
    counted under blank_wsa_excluded, never silently dropped."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 3)] = dict(attempts=[(KEEP, {"WSA_LABEL": "", "ACA_LABEL": "M"}, [])], executed=KEEP)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions), keep_prompts=True)
    assert run.decisions[("LB1", 3)].first_wsa is None and not run.decisions[("LB1", 3)].aborted
    rows = {(r["k_short_years"], r["full_window"]): r for r in vm.r5b_wsa_by_short_years(run)}
    # k=0 loses d9 (L=2) to blank_wsa_excluded; d4, d5, d6 remain (sum 11, n 3)
    k0 = rows[(0, False)]
    assert (k0["n_in_mean"], k0["sum_first_wsa"], k0["blank_wsa_excluded"], k0["aborted_excluded"]) == (3, 11, 1, 1)
    assert k0["mean_first_wsa"] == pytest.approx(11 / 3)
    k1 = rows[(1, False)]
    assert (k1["n_in_mean"], k1["mean_first_wsa"]) == (1, pytest.approx(4.0))
    assert rows[("no_window", None)]["no_window_excluded"] == 3


def _r5c_run(monkeypatch, tmp_path: Path) -> vm.LoadedRun:
    """UB1 and UB2 (sub-basin UT1) and LB1 (no sub-basin), 8 years, reusing
    the A_s trace of test_drought_recovery_hand_computed (dry years 3-4, the
    20th percentile, verified against numpy): a 2-year dry spell and 3
    recovered years (5-7, the R5c post-spell window), with years 1, 2 and 8
    as padding. UB2's year 4 is ABORTED, to exercise the exclusion rule
    inside a spell."""
    n = 8
    a_s = [100, 100, 20, 25, 100, 100, 100, 100]
    system = system_years(n, [13.0] * n, [11.0] * n, [0] * n)
    _patch_ub_supply(monkeypatch, {"UT1": {CFG.sim_start_year + t - 1: a_s[t - 1] for t in range(1, n + 1)}})
    agent_years = {}
    for t in range(1, n + 1):
        agent_years[("UB1", t)] = {"request": 1000.0, "diversion": 1000.0}
        agent_years[("UB2", t)] = {"request": 1000.0, "diversion": 1000.0}
        agent_years[("LB1", t)] = {"request": 1000.0, "diversion": 1000.0}
    wsa = {
        ("UB1", 3): "H", ("UB2", 3): "M",         # in_spell position 1
        ("UB1", 4): "VH",                         # in_spell position 2; UB2 ABORTED
        ("UB1", 5): "M", ("UB2", 5): "L",         # after_spell offset 1
        ("UB1", 6): "L", ("UB2", 6): "L",         # after_spell offset 2
        ("UB1", 7): "VL", ("UB2", 7): "M",        # after_spell offset 3
    }
    decisions = {}
    for t in range(1, n + 1):
        for agent in ("UB1", "UB2", "LB1"):
            if (agent, t) == ("UB2", 4):
                decisions[(agent, t)] = dict(attempts=[], executed=None, status="ABORTED", path="aborted",
                                             format_retries=0, llm_success="")
                continue
            label = wsa.get((agent, t), "M")  # LB1's label and the padding years are never read by R5c
            decisions[(agent, t)] = dict(attempts=[(KEEP, {"WSA_LABEL": label, "ACA_LABEL": "M"}, [])],
                                         executed=KEEP)
    audits = [audit_row(a, t, **spec) for (a, t), spec in decisions.items()]
    traces = [trace(a, t, aborted=spec.get("path") == "aborted") for (a, t), spec in decisions.items()]
    path = write_run(tmp_path / "r5c", llm_manifest("strict", agents=sorted(AGENTS)),
                     sim_rows(system, agent_years), audits, traces)
    return vm.load_run(path, keep_prompts=True)


def test_r5c_wsa_by_spell_year_hand_computed(monkeypatch, tmp_path):
    run = _r5c_run(monkeypatch, tmp_path)
    rows = {(r["position_type"], r["position"]): r for r in vm.r5c_wsa_by_spell_year(run, CFG)}
    assert (rows[("in_spell", 1)]["n_in_mean"], rows[("in_spell", 1)]["mean_first_wsa"]) == (
        2, pytest.approx(3.5))  # UB1=H(4), UB2=M(3)
    assert (rows[("in_spell", 2)]["n_in_mean"], rows[("in_spell", 2)]["mean_first_wsa"],
            rows[("in_spell", 2)]["aborted_excluded"]) == (1, pytest.approx(5.0), 1)  # UB1=VH(5); UB2 ABORTED
    assert (rows[("after_spell", 1)]["n_in_mean"], rows[("after_spell", 1)]["mean_first_wsa"]) == (
        2, pytest.approx(2.5))  # UB1=M(3), UB2=L(2)
    assert (rows[("after_spell", 2)]["n_in_mean"], rows[("after_spell", 2)]["mean_first_wsa"]) == (
        2, pytest.approx(2.0))  # UB1=L(2), UB2=L(2)
    assert (rows[("after_spell", 3)]["n_in_mean"], rows[("after_spell", 3)]["mean_first_wsa"]) == (
        2, pytest.approx(2.0))  # UB1=VL(1), UB2=M(3)
    # LB1 (no sub-basin) never appears: 2+1+2+2+2 = 9 of UB1/UB2's 10
    # decisions across the 5 positions (one, UB2 year 4, is aborted_excluded
    # above), none of LB1's 8.
    assert sum(r["n_in_mean"] for r in rows.values()) == 9
    assert sum(r["aborted_excluded"] for r in rows.values()) == 1


def test_r5d_hand_computed(strict_run):
    """Splits (item 34). Overall: eligible = d2 (decrease), d3 (keep), d9
    (increase); d1/d4/d8 excluded via TR1 (WSA H/VH, not counted anywhere:
    TR1 could act), d5 via the supply rule's condition (physical ratio 0.9,
    also not counted: the supply rule could act), d7 (ABORTED), and d6 via
    excluded_at_cap: at the cap, the menu does not OFFER increase_demand,
    but d6's first attempt PROPOSES it anyway (an off-menu increase, the
    LLM is not restricted to the menu) and it is blocked by the cap (and
    the two registry backstops), not by TR1 or the supply rule -- so it
    belongs to neither population and is counted apart."""
    rows = {r["split"]: r for r in vm.r5d_rows(strict_run)}
    assert strict_run.decisions[("LB1", 2)].first_proposal == INC  # d6: an off-menu increase, not "impossible"
    overall = rows["overall"]
    assert (overall["eligible_decisions"], overall["first_proposal_increases"]) == (3, 1)
    assert overall["share_pct"] == pytest.approx(100 / 3)
    assert (overall["excluded_aborted"], overall["excluded_at_cap"],
            overall["excluded_blank_wsa"], overall["excluded_off_scale_wsa"]) == (1, 1, 0, 0)

    ub = rows["basin=upper_basin"]
    assert (ub["eligible_decisions"], ub["first_proposal_increases"], ub["excluded_aborted"]) == (1, 0, 1)
    lb = rows["basin=lower_basin"]
    assert (lb["eligible_decisions"], lb["first_proposal_increases"], lb["excluded_at_cap"]) == (2, 1, 1)

    first_year = rows["last_year=first_year"]  # d1, d2, d3 (year 1, no prior year)
    assert (first_year["eligible_decisions"], first_year["first_proposal_increases"]) == (2, 0)
    not_short = rows["last_year=not_short"]  # d4, d5, d6, d7, d9
    assert (not_short["eligible_decisions"], not_short["first_proposal_increases"],
            not_short["excluded_aborted"], not_short["excluded_at_cap"]) == (1, 1, 1, 1)
    short = rows["last_year=short"]  # only d8 (UB2's year 2 was short)
    assert (short["eligible_decisions"], short["share_pct"]) == (0, None)

    # Crossed (item 34): Upper Basin AND last year short. d8 is UB2's year
    # 3, the only last_year=short decision in the fixture, and it is UB --
    # same population as the plain last_year=short split above.
    crossed = rows["basin=upper_basin,last_year=short"]
    assert (crossed["eligible_decisions"], crossed["share_pct"]) == (0, None)


def _r5d_little_spare_run(monkeypatch, tmp_path: Path) -> vm.LoadedRun:
    """UB1 (typical_step_af 50) and UB2 (typical_step_af 15), sub-basin
    UT1, 4 years, for r5d_ub_little_spare. Every ratio is
    round(min(1, A_s / 2000), 6), the water system's own formula for a UB
    sub-basin's settled share at the keep requests (spec WP1b.3), so (item
    34, replacing r5d_ub_zero_sum's hand test) no decision asserts a ratio
    the environment could not actually produce from its A_s and keep
    requests. Year 1: A_s 3000 (1000 AF unused): plenty of spare water for
    both agents' steps. Year 2: A_s 2020 (20 AF unused, ratio still capped
    at 1.0): little spare for UB1 (step 50 > 20) but not for UB2 (step
    15 < 20, a typical UB2 increase would fit). Year 3: A_s 1900 (ratio
    0.95): the supply rule fires, so neither agent counts either way.
    Year 4: A_s 2020 again, but UB2 is the ABORTED_EXCEPTION sentinel, so
    the pool's keep-request sum is unknown."""
    n = 4
    a_s_by_year = {1: 3000.0, 2: 2020.0, 3: 1900.0, 4: 2020.0}
    keep_sum = 2000.0
    ratio_by_year = {t: round(min(1.0, a_s_by_year[t] / keep_sum), 6) for t in range(1, n + 1)}
    _patch_ub_supply(monkeypatch, {"UT1": {CFG.sim_start_year + t - 1: a_s_by_year[t] for t in range(1, n + 1)}})
    system = system_years(n, [13.0] * n, [11.0] * n, [0] * n)
    agent_years = {}
    for t in range(1, n + 1):
        agent_years[("UB1", t)] = {"request": 1000.0, "diversion": 1000.0 * ratio_by_year[t],
                                   "typical_step_af": 50.0}
        agent_years[("UB2", t)] = {"request": 1000.0, "diversion": 1000.0 * ratio_by_year[t],
                                   "typical_step_af": 15.0}
    decisions = {
        ("UB1", 1): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=KEEP, physical=ratio_by_year[1]),
        ("UB2", 1): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=KEEP, physical=ratio_by_year[1]),
        ("UB1", 2): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=INC, physical=ratio_by_year[2]),
        ("UB2", 2): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=KEEP, physical=ratio_by_year[2]),
        ("UB1", 3): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [SUP]),
                                   (KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=KEEP, physical=ratio_by_year[3]),
        ("UB2", 3): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=KEEP, physical=ratio_by_year[3]),
        ("UB1", 4): dict(attempts=[(INC, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])],
                         executed=INC, physical=ratio_by_year[4]),
        ("UB2", 4): dict(attempts=[], executed=None, crashed=True),
    }
    audits = [audit_row(a, t, **spec) for (a, t), spec in decisions.items()]
    traces = [trace(a, t, aborted=spec.get("path") == "aborted", crashed=spec.get("crashed", False))
             for (a, t), spec in decisions.items()]
    path = write_run(tmp_path / "r5d_little_spare", llm_manifest("strict", agents=sorted(AGENTS)),
                     sim_rows(system, agent_years), audits, traces)
    return vm.load_run(path, keep_prompts=True)


def test_r5d_ub_little_spare_hand_computed(monkeypatch, tmp_path):
    """Eligible: only UB1's year 2 (20 AF unused < its 50 AF typical step),
    an increase. UB2's year 2 does not count (20 AF unused is NOT below its
    smaller 15 AF step). Year 1 has plenty of spare water for both agents'
    steps; year 3's ratio (0.95) means the supply rule fires, excluding
    both; year 4 has UB2 crashed, so UB1 -> excluded_unknown_sum and UB2 ->
    excluded_aborted (not approximated from a partial sum)."""
    run = _r5d_little_spare_run(monkeypatch, tmp_path)
    row = vm.r5d_ub_little_spare(run, CFG)
    assert (row["eligible_decisions"], row["first_proposal_increases"]) == (1, 1)
    assert row["share_pct"] == pytest.approx(100.0)
    assert (row["excluded_aborted"], row["excluded_unknown_sum"]) == (1, 1)


def test_r5_summary_tables_pool_by_arm(strict_run, disabled_run):
    """Pooling (as compute_metrics would, across seeds within an arm) sums
    counts and recomputes the mean or share from the pooled sums."""
    r5a = vm.r5a_wsa_by_band(strict_run) + vm.r5a_wsa_by_band(disabled_run)
    pooled_a = {(r["arm"], r["band"], r["first_wsa"]): r for r in vm.r5a_band_summary(r5a, ["strict", "disabled"])}
    assert pooled_a[("strict", "sufficient", "H")]["decisions"] == 1
    assert pooled_a[("strict", "sufficient", "H")]["band_total_decisions"] == 7

    r5b = vm.r5b_wsa_by_short_years(strict_run)
    pooled_b = {(r["k_short_years"], r["full_window"]): r for r in vm.r5b_summary_table(r5b)}
    assert pooled_b[(0, False)]["mean_first_wsa"] == pytest.approx(3.25)  # one run pooled: unchanged

    r5d = vm.r5d_rows(strict_run) + vm.r5d_rows(disabled_run)
    pooled_d = {(r["arm"], r["split"]): r for r in vm.r5d_summary_table(r5d)}
    overall_strict = pooled_d[("strict", "overall")]
    assert overall_strict["eligible_decisions"] == 3 and overall_strict["share_pct"] == pytest.approx(100 / 3)


def test_r5_never_changes_the_pilot_gate_verdict():
    """Item 33c: R5 is report-only, computed only by the ``metrics`` command.
    pilot_gate's source (its gated checks and its "reported" R1-R4 list)
    names no R5 function or field, so no future wiring mistake can reach it
    without a visible diff here."""
    src = inspect.getsource(vm.pilot_gate)
    assert "r5" not in src.lower()


# =============================================================================
# Pilot gate checks on the fixtures
# =============================================================================

def test_p1_closure_and_a_residual(tmp_path, strict_run):
    assert vm.gate_p1([strict_run])["passed"] is True
    broken = vm.load_run(fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="broken", unbalance={2: 1e-6}))
    check = vm.gate_p1([broken])
    assert check["passed"] is False and "2020" in check["reason"]


def test_p1_default_run_has_no_return_flow_correction(strict_run):
    """The default fixture (no lb_phys_ratio / lb_return_flow_maf columns
    in its CSV, matching lb_return_flow_fraction=0.0's production default)
    must load those two optional columns as exactly 0.0, making gate_p1's
    return-flow correction a no-op -- byte-identical to the pre-correction
    formula."""
    for y in strict_run.sim.years:
        s = strict_run.sim.system[y]
        assert s["lb_phys_ratio"] == 0.0
        assert s["lb_return_flow_maf"] == 0.0


def test_p1_accounts_for_lb_return_flow_fraction(tmp_path):
    """2026-10-06 CPU rerun finding (irrigation_v3_cpu_rerun_2026-10-06.md
    section 4(iii)): a non-default lb_return_flow_fraction charges Mead's
    outflow LESS by lb_phys_ratio * lb_return_flow_maf every year
    (irrigation_env.py settle_year, line ~3796); gate_p1's mass-balance
    check must add that term back (the same correction hindcast_v3.py's
    run_hindcast() already applies), or every run with a non-zero fraction
    fails P1 at face value even though mass balance actually holds (the
    real sensitivity run: residual up to 0.77 MAF/yr uncorrected)."""
    phys_ratio, return_flow_maf = 0.95, 0.2
    charged = phys_ratio * return_flow_maf
    system = system_years(3, (13.0, 12.0, 11.5), (11.0, 10.0, 9.0), (0, 0, 1),
                          unbalance={t: charged for t in (1, 2, 3)})
    agent_years = {}
    for (agent, t), spec in STRICT_DECISIONS.items():
        values: Dict[str, Any] = {"lb_phys_ratio": phys_ratio, "lb_return_flow_maf": return_flow_maf}
        if spec.get("physical", 1.0) < 1.0:
            values["ub_subbasin_ratio"] = spec["physical"]
            values["diversion"] = 1000.0 * spec["physical"]
        agent_years[(agent, t)] = values
    audits = [audit_row(a, t, **spec) for (a, t), spec in STRICT_DECISIONS.items()]
    traces = [trace(a, t, at_cap=(a, t) in AT_CAP, aborted=spec.get("path") == "aborted",
                    crashed=spec.get("crashed", False))
              for (a, t), spec in STRICT_DECISIONS.items()]
    path = write_run(tmp_path / "strict_lbflow", llm_manifest("strict", agents=sorted(AGENTS)),
                     sim_rows(system, agent_years), audits, traces)
    run = vm.load_run(path, keep_prompts=True)

    check = vm.gate_p1([run])
    assert check["passed"] is True, check["reason"]
    assert check["details"]["largest_residual_maf"][run.label] < 1e-9


def test_p2_bounds(tmp_path, strict_run):
    assert vm.gate_p2([strict_run], CFG)["passed"] is True
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="over")
    rows = list(csv.DictReader(open(path / vm.SIM_LOG, encoding="utf-8")))
    rows[0]["diversion"] = "1000.5"
    vm.write_csv(path / vm.SIM_LOG, rows)
    assert vm.gate_p2([vm.load_run(path)], CFG)["passed"] is False


def test_p7_rates_and_agreement(strict_run, disabled_run):
    check = vm.gate_p7(strict_run, disabled_run)
    # strict: 6 of 9 retried (> 50 percent); disabled: 2 of 9 (> 0.5 percent);
    # the ABORTED row's 3 format retries: 1 of 9 (> 5 percent)
    assert check["details"]["strict_governance_retry_share"] == pytest.approx(6 / 9)
    assert check["details"]["disabled_governance_retry_share"] == pytest.approx(2 / 9)
    assert check["passed"] is False
    assert "disagreements" not in check["reason"]


def test_p7_parse_share_counts_an_unparsable_governance_retry(tmp_path, disabled_run):
    """A governance retry that came back unparsable (an empty attempt group)
    is a parse retry, although format_retries is 0."""
    decisions = dict(STRICT_DECISIONS)
    decisions[("LB1", 1)] = dict(attempts=[(INC, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [TR1]),
                                          (None, None, None),
                                          (KEEP, {"WSA_LABEL": "H", "ACA_LABEL": "M"}, [])], executed=KEEP)
    run = vm.load_run(fixture_run(tmp_path, "strict", decisions))
    d = run.decisions[("LB1", 1)]
    assert d.format_retries == 0 and d.parse_retried and not d.attempts[1].parsed
    check = vm.gate_p7(run, disabled_run)
    # this row and the ABORTED row (3 format retries): 2 of 9
    assert check["details"]["parse_retry_share"][run.label] == pytest.approx(2 / 9)
    assert check["details"]["parse_retry_share"][disabled_run.label] == pytest.approx(1 / 9)


def test_p8_counts_the_rows_on_the_files(strict_run):
    # the fixture manifest says configured_grid_rows = 9: P8 ignores it and
    # requires 3,276 rows (78 agents x 42 years) in each CSV
    check = vm.gate_p8([strict_run])
    assert check["passed"] is False and "9 audit and 9 log rows; P8 requires 3276" in check["reason"]
    check = vm.gate_p8([strict_run], expected_rows=9)
    details = check["details"][strict_run.label]
    assert (details["no_readable_decision"], details["llm_success_false"], details["audit_rows"],
            details["missing_agent_years"]) == (1, 0, 9, 0)
    assert check["passed"] is False and "requires" not in check["reason"]  # 1 of 9 without a readable decision
    assert "rows without a readable decision" in check["reason"]


def _p10_rows(*runs: vm.LoadedRun) -> Dict[str, Dict[str, Any]]:
    """The per-run values P10 reads (the KGE values are placeholders: P10
    checks only that they are finite)."""
    return {run.label: {**vm.ibr_metrics(run.ordered()), **vm.executed_violations(run),
                        **vm.reservoir_outcomes(run.sim, CFG), **{f"kge_{n}": 0.5 for n in vm.P10_KGE_SERIES}}
            for run in runs}


def test_p10_fails_a_run_whose_requests_never_changed(tmp_path, strict_run, disabled_run):
    """Under the constant-series convention a run whose requests never moved
    still has a finite KGE; P10 checks for it directly."""
    # the hand fixture requests 1,000 acre-ft every year: degenerate
    check = vm.gate_p10(_p10_rows(strict_run, disabled_run), strict_run.label, [strict_run, disabled_run],
                        expected_rows=9)
    assert "strict_seed42: the UB+LB request total is the same in every year (0.003000 MAF)" in check["reason"]
    # one executed increase moves the total: no longer degenerate
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="moving")
    with open(path / vm.SIM_LOG, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    for row in rows:
        if (row["agent_id"], row["year"]) == ("LB1", "3"):
            row["request"] = row["diversion"] = "1100.0"
    vm.write_csv(path / vm.SIM_LOG, rows)
    moving = vm.load_run(path)
    check = vm.gate_p10(_p10_rows(moving, disabled_run), moving.label, [moving, disabled_run], expected_rows=9)
    assert "strict_seed42: the UB+LB request total" not in check["reason"]
    assert "disabled_seed42: the UB+LB request total is the same in every year" in check["reason"]


def test_p10_requires_the_ibr_over_all_decisions_of_a_full_run(strict_run, disabled_run):
    rows = _p10_rows(strict_run, disabled_run)
    check = vm.gate_p10(rows, strict_run.label, [strict_run, disabled_run])
    assert "the IBR is over 9 decisions, not all 3276" in check["reason"]
    check = vm.gate_p10(rows, strict_run.label, [strict_run, disabled_run], expected_rows=9)
    assert "decisions, not all" not in check["reason"]


def test_p9_menus_and_a_forbidden_offer(tmp_path, strict_run, disabled_run):
    assert vm.gate_p9(strict_run, disabled_run)["passed"] is True
    bad = vm.load_run(fixture_run(tmp_path, "disabled", DISABLED_DECISIONS, name="bad",
                                  prompt_for=lambda a, t: menu_prompt(a, t, ["increase", "keep", "decrease"])))
    check = vm.gate_p9(strict_run, bad)
    assert check["passed"] is False and "hidden option" in check["reason"]


def test_r2_tr2_remeasurement(disabled_run):
    details = vm.report_r2(disabled_run)["details"]
    # d8 (UB2, 2021) is the only decision with WSA and ACA both H or above; it increased
    assert details["all"]["decisions"] == 9
    assert details["all"]["tr2_condition_and_keep_pct"] == 0.0
    assert details["all"]["tr1_tr2_leave_only_decrease_pct"] == pytest.approx(100 / 9)


# =============================================================================
# P5(b) prompt numbers and P6 reflections on hand-written prompts
# =============================================================================

def _prompt_run(tmp_path, prompts: Dict[Tuple[str, int], str]) -> vm.LoadedRun:
    def prompt_for(a, t):
        menu = menu_prompt(a, t, ["keep", "decrease"] if (a, t) in AT_CAP else ["increase", "keep", "decrease"])
        return prompts.get((a, t), "") + "\n" + menu
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS, prompt_for=prompt_for)
    # P6 uses the actual recorded input. These fixtures explicitly supply it;
    # legacy missing-input skip behavior has a separate regression test.
    (path / "reflection_log.jsonl").write_text("".join(
        json.dumps({"agent_id": a, "period": 2018 + t,
                    "reflection_input": text}) + "\n"
        for (a, t), text in prompts.items()), encoding="utf-8")
    return vm.load_run(path, keep_prompts=True)


def test_p5b_checks_numbers_and_flags_unknown_lines(tmp_path):
    good = ("It is now the year 2020. You use water in the Upper Colorado River Basin.\n"
            "Your water right is 2,000 acre-ft/year; last year's delivery was 50% of it.\n"
            "Last year you requested 1,000 acre-ft and received 1,000 acre-ft (100% delivered).")
    run = _prompt_run(tmp_path, {("UB1", 2): good,
                                 ("UB2", 2): good.replace("2,000", "3,000").replace("50%", "33%")
                                 .replace("received 1,000", "received 900").replace("100%", "90.0%")
                                 + ", because a stated reason.",
                                 ("LB1", 3): "Lake Mead was at 1,234 feet above sea level on 1 January "
                                             "(rising from last year).\nSomething 42 happened."})
    audit = vm.PromptAudit()
    checker = vm.PromptChecker(run, CFG, CFG.ub_subbasin_supply_variant)
    for key in sorted(run.traces):
        checker.audit(key, run.traces[key].prompt, audit)
    # UB2 2020: the log says 900 received (ratio 0.9 in 2020 is year 2, not
    # last year): last year's delivery was the full 1,000
    assert any("UB2 2020" in m and "last year's delivery" in m for m in audit.mismatches)
    assert not any("UB1 2020" in m for m in audit.mismatches)
    assert any("Lake Mead level" in m and "1,234" in m for m in audit.mismatches)
    assert len(audit.unchecked) == 1 and "Something 42 happened." in audit.unchecked[0]


def test_p6_reflection_checks(tmp_path):
    memory_2020 = ("Your memory includes:\n- Year 2019: You chose to maintain demand. You requested 1,000 acre-ft "
                   "and received 1,000 acre-ft. Demand fully met. That winter's precipitation in your sub-basin "
                   "was above the previous winter's.\n")
    prompts = {
        ("UB1", 2): memory_2020,
        ("UB1", 3): ("Your memory includes:\n- Consolidated Reflection (written in 2020): I kept 1,000 acre-ft "
                     "and saw 5,555 acre-ft elsewhere.\n- Consolidated Reflection (written in 2019): old.\n"),
    }
    r = vm.reflection_checks(_prompt_run(tmp_path, prompts))
    assert r["reflection_lines"] == 2
    assert r["foreign_figure_reflections"] == 1  # 5,555 is not in UB1's 2020 memory
    assert r["prompts_with_several_reflections"] == 1
    assert r["reflections_not_from_previous_year"] == 1


def _write_reflection_check_rows(run: vm.LoadedRun, rows: List[Dict[str, Any]]) -> None:
    (run.info.path / "reflection_checks.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_p6_carries_only_after_same_agent_drop_and_uses_writing_year_figures(tmp_path):
    writing_prompt = "Your memory includes:\n- Year 2018: You requested 1,111 acre-ft.\n"
    middle_prompt = "Your memory includes:\n- Year 2019: You requested 6,666 acre-ft.\n"
    shown_prompt = (
        "Your memory includes:\n"
        "- Consolidated Reflection (written in 2019): I learned from 1,111 acre-ft.\n"
        "- Year 2020: You requested 7,777 acre-ft.\n"
    )
    run = _prompt_run(tmp_path / "carried", {
        ("UB1", 1): writing_prompt, ("UB1", 2): middle_prompt, ("UB1", 3): shown_prompt,
    })
    _write_reflection_check_rows(run, [{"agent_id": "UB1", "period": 2020, "outcome": "dropped"}])

    result = vm.reflection_checks(run)
    assert result["carried_after_drop"] == 1
    assert result["reflections_not_from_previous_year"] == 0
    assert result["foreign_figure_reflections"] == 0
    assert vm.gate_p6([run])["passed"] is True

    later_only = _prompt_run(
        tmp_path / "later_only",
        {("UB1", 1): writing_prompt, ("UB1", 2): middle_prompt,
         ("UB1", 3): shown_prompt.replace("from 1,111", "from 6,666")},
    )
    _write_reflection_check_rows(later_only, [
        {"agent_id": "UB1", "period": 2020, "outcome": "dropped"},
    ])
    later_result = vm.reflection_checks(later_only)
    assert later_result["carried_after_drop"] == 1
    assert later_result["foreign_figure_reflections"] == 1
    assert vm.gate_p6([later_only])["passed"] is False


@pytest.mark.parametrize("rows", [
    [],
    [{"agent_id": "UB2", "period": 2020, "outcome": "dropped"}],
])
def test_p6_two_year_old_reflection_without_its_agents_drop_stays_gated(tmp_path, rows):
    reflected = ("Your memory includes:\n- Consolidated Reflection (written in 2019): "
                 "I learned to keep my request steady.\n")
    run = _prompt_run(tmp_path, {("UB1", 3): reflected})
    _write_reflection_check_rows(run, rows)
    result = vm.reflection_checks(run)
    assert result["carried_after_drop"] == 0
    assert result["reflections_not_from_previous_year"] == 1
    assert vm.gate_p6([run])["passed"] is False


def _item45_run(tmp_path, prompts: Dict[Tuple[str, int], str], floor_menu: bool = False) -> vm.LoadedRun:
    """The strict fixture with UB1 short in 2019 (900 of 1,000 received) and
    its 2020 keep request at that receipt, so the 2020 memory line carries
    the item-45g clause; ``floor_menu`` drops LB1's decrease in 2021."""
    decisions = {k: dict(v) for k, v in STRICT_DECISIONS.items()}
    decisions[("UB1", 1)]["physical"] = 0.9
    decisions[("UB1", 2)]["keep"] = 900.0  # the logged keep request is that receipt

    def prompt_for(a, t):
        hidden = (a, t) in AT_CAP
        options = ["keep"] if hidden else ["increase", "keep"]
        if not (floor_menu and (a, t) == ("LB1", 3)) and not hidden:
            options.append("decrease")
        elif hidden:
            options = ["keep", "decrease"]
        return prompts.get((a, t), "") + "\n" + menu_prompt(a, t, options)

    path = fixture_run(tmp_path, "strict", decisions, prompt_for=prompt_for)
    rows = list(csv.DictReader(open(path / vm.SIM_LOG, encoding="utf-8")))
    for row in rows:
        if (row["agent_id"], row["year"]) == ("UB1", "2"):
            row["request"] = row["diversion"] = row["base_af"] = "900.0"
    vm.write_csv(path / vm.SIM_LOG, rows)
    lines = (path / vm.TRACES).read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines[1:], start=1):
        rec = json.loads(line)
        if (rec["agent_id"], rec["year"]) == ("UB1", 2):
            rec["state_before"]["current_request"] = 900.0
            lines[i] = json.dumps(rec)
    (path / vm.TRACES).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return vm.load_run(path, keep_prompts=True)


def _ub1_memory_2021(checker: vm.PromptChecker, share_2020: Optional[str] = None, clause: bool = True) -> str:
    p19 = f"{checker.flow_share('UT1', 2019):.0%}"
    p20 = share_2020 or f"{checker.flow_share('UT1', 2020):.0%}"
    keep = (", so your request fell from 1,000 acre-ft to the 900 acre-ft you received the year before"
            if clause else "")
    return ("Your memory includes:\n"
            "- Year 2019: You chose to maintain demand. You requested 1,000 acre-ft and received 900 acre-ft. "
            "Shortfall: 100 acre-ft (10.0% unmet), because a stated reason. That winter's precipitation in "
            "your sub-basin was above the previous winter's. The natural flow of the rivers your sub-basin "
            f"draws on was {p19} of its 1971-2018 average that year.\n"
            f"- Year 2020: You chose to maintain demand{keep}. You requested 900 acre-ft and received 900 "
            "acre-ft. Demand fully met. That winter's precipitation in your sub-basin was above the previous "
            f"winter's. The natural flow of the rivers your sub-basin draws on was {p20} of its 1971-2018 "
            "average that year.\n")


@pytest.mark.parametrize(
    ("mode", "p56_included", "p56_sentence"),
    [
        ("zero", 0.0,
         "Priority-5/6 water is not available in a tier year; your 20,000 acre-ft "
         "priority-5/6 entitlement adds no water to the tier ceiling."),
        ("proportional", 14_936.0,
         "About 14,936 acre-ft of your 20,000 acre-ft "
         "priority-5/6 entitlement is included in the tier ceiling."),
    ],
)
def test_p5b_reads_every_ceiling_and_p56_sentence_number(tmp_path, mode, p56_included, p56_sentence):
    run = _prompt_run(tmp_path, {})
    key = ('LB1', 2)
    junior_ceiling = 59_744.0 + p56_included
    tier_ceiling = 5_940.0 + junior_ceiling
    run.sim.rows[key].update(
        lb_junior_tier_cut_fraction='0.2532',
        lb_senior_entitlement_af='5940',
        lb_junior_entitlement_af='100000',
        lb_junior_ceiling_af=str(junior_ceiling),
        lb_tier_ceiling_af=str(tier_ceiling),
        lb_p56_entitlement_af='20000',
        lb_p56_in_tier=mode,
    )
    run.sim.system[2].update(shortage_tier=2, lb_shortage_volume_maf=0.417)
    run.info.manifest['lb_p56_in_tier'] = mode
    run.info.manifest['water_system_lb_p56_in_tier'] = mode
    checker = vm.PromptChecker(run, CFG, CFG.ub_subbasin_supply_variant)
    checker.priority = dict(checker.priority)
    checker.priority['LB1'] = {
        'senior_entitlement_af': 5_940.0,
        'junior_entitlement_af': 100_000.0,
        'p56_entitlement_af': 20_000.0,
    }
    text = (
        "A Tier 2 Lower Basin shortage applies this year (Lake Mead was below 1,050 feet on "
        "1 January): it reduces Lower Basin deliveries by 417,000 acre-ft in total, taken "
        "from non-agricultural users and from junior-priority agricultural water. "
        f"This tier limits your junior-priority water this year to about {junior_ceiling:,.0f} "
        "acre-ft "
        f"({junior_ceiling / 100_000:.0%} of your 100,000 acre-ft junior-priority entitlement). "
        f"A request at or below your {tier_ceiling:,.0f} acre-ft tier ceiling is not reduced by "
        f"the tier. {p56_sentence} The delivery available under that ceiling is reduced only if "
        "Lake Mead cannot supply all Lower Basin withdrawals this year."
    )
    good = vm.PromptAudit()
    checker.audit(key, text, good)
    assert not good.mismatches and not good.unchecked
    replacements = [
        (f'{junior_ceiling:,.0f}', f'{junior_ceiling - 1:,.0f}'),
        (f'{tier_ceiling:,.0f}', f'{tier_ceiling - 1:,.0f}'),
        (f'{junior_ceiling / 100_000:.0%}', '1%'),
        ('100,000', '100,001'),
        ('20,000', '20,001'),
    ]
    if mode == 'proportional':
        replacements.append(('14,936', '14,935'))
    for correct, wrong in replacements:
        bad = vm.PromptAudit()
        checker.audit(key, text.replace(correct, wrong), bad)
        assert bad.mismatches, (correct, wrong)

    # Corrupt prompt and log together: P5 must still reject them against the
    # pinned entitlement row, f, and mode rather than trusting the CSV.
    for column, correct, wrong, message in [
        ("lb_junior_ceiling_af", f"{junior_ceiling:,.0f}", f"{junior_ceiling - 100:,.0f}",
         "logged junior-priority ceiling disagrees"),
        ("lb_tier_ceiling_af", f"{tier_ceiling:,.0f}", f"{tier_ceiling - 100:,.0f}",
         "logged total tier ceiling disagrees"),
    ]:
        original = run.sim.rows[key][column]
        run.sim.rows[key][column] = str(float(original) - 100.0)
        bad = vm.PromptAudit()
        checker.audit(key, text.replace(correct, wrong), bad)
        assert any(message in item for item in bad.mismatches), bad.mismatches
        run.sim.rows[key][column] = original

    original_entitlement = run.sim.rows[key]["lb_junior_entitlement_af"]
    run.sim.rows[key]["lb_junior_entitlement_af"] = "100001"
    bad = vm.PromptAudit()
    checker.audit(key, text.replace("100,000", "100,001"), bad)
    assert any("logged junior entitlement disagrees" in item for item in bad.mismatches)
    run.sim.rows[key]["lb_junior_entitlement_af"] = original_entitlement

    original_mode = run.sim.rows[key]["lb_p56_in_tier"]
    run.sim.rows[key]["lb_p56_in_tier"] = "invented"
    bad = vm.PromptAudit()
    checker.audit(key, text, bad)
    assert any("invalid or missing lb_p56_in_tier" in item for item in bad.mismatches)
    run.sim.rows[key]["lb_p56_in_tier"] = original_mode

    # A non-holder row (f=0) must not carry the holder-only ceiling sentence,
    # even when a synthetic row happens to retain a positive entitlement.
    original_fraction = run.sim.rows[key]["lb_junior_tier_cut_fraction"]
    run.sim.rows[key]["lb_junior_tier_cut_fraction"] = "0"
    bad = vm.PromptAudit()
    checker.audit(key, text, bad)
    assert any("junior ceiling sentence holder eligibility" in item
               for item in bad.mismatches)
    assert any("priority-5/6 sentence holder eligibility" in item
               for item in bad.mismatches)
    run.sim.rows[key]["lb_junior_tier_cut_fraction"] = original_fraction


@pytest.mark.parametrize("column", [
    "lb_junior_ceiling_af", "lb_tier_ceiling_af", "lb_junior_entitlement_af",
    "lb_p56_entitlement_af", "lb_p56_in_tier",
])
def test_p5b_new_ceiling_log_fields_fail_loud_when_missing(tmp_path, column):
    run = _prompt_run(tmp_path, {})
    key = ("LB1", 2)
    run.info.manifest["lb_p56_in_tier"] = "zero"
    run.sim.rows[key].update(
        lb_junior_tier_cut_fraction="0.2532", lb_junior_ceiling_af="74680",
        lb_tier_ceiling_af="80620", lb_junior_entitlement_af="100000",
        lb_p56_entitlement_af="0", lb_p56_in_tier="zero",
    )
    del run.sim.rows[key][column]
    checker = vm.PromptChecker(run, CFG, CFG.ub_subbasin_supply_variant)
    checker.priority = dict(checker.priority)
    checker.priority["LB1"] = {
        "senior_entitlement_af": 5_940.0,
        "junior_entitlement_af": 100_000.0,
        "p56_entitlement_af": 0.0,
    }
    text = (
        "A Tier 2 Lower Basin shortage applies this year (Lake Mead was below 1,050 feet on "
        "1 January): it reduces Lower Basin deliveries by 417,000 acre-ft in total, taken "
        "from non-agricultural users and from junior-priority agricultural water. This tier "
        "limits your junior-priority water this year to about 74,680 acre-ft (75% of your "
        "100,000 acre-ft junior-priority entitlement). A request at or below your 80,620 "
        "acre-ft tier ceiling is not reduced by the tier."
    )
    with pytest.raises(vm.MetricsError, match=column):
        checker.audit(key, text, vm.PromptAudit())


def test_p5b_rejects_the_removed_restoration_sentence(tmp_path):
    run = _prompt_run(tmp_path, {})
    run.info.manifest['water_system_lb_p56_in_tier'] = 'zero'
    key = ("LB1", 2)
    checker = vm.PromptChecker(run, CFG, CFG.ub_subbasin_supply_variant)
    text = ("Last year's tier cut was a fixed share of the junior-priority water you requested; "
            "it did not change your water right. If you choose to keep your request, you ask for "
            "the reduced 3,826 acre-ft you received last year. To return toward the 4,798 acre-ft "
            "you requested last year, choose to increase your request.")
    audit = vm.PromptAudit()
    checker.audit(key, text, audit)
    assert any("removed tier-restoration sentence" in message for message in audit.mismatches)


def test_p5b_reads_the_item_45_memory_and_floor_sentences(tmp_path):
    """Spec item 45f/g/i: the flow share of a memory line, the keep clause
    and the floor sentence are read back against the log; a wrong share, a
    missing clause, a clause on a line that is not a keep after a short year
    and a floor sentence beside a decrease are each a mismatch."""
    probe = vm.PromptChecker(_item45_run(tmp_path / "probe", {}), CFG, CFG.ub_subbasin_supply_variant)
    floor = "A decrease is not offered because your request is at or below the minimum-use floor of 400 acre-ft (10% of your water right)."

    def audit(prompts, floor_menu=False, sub="x"):
        run = _item45_run(tmp_path / sub, prompts, floor_menu)
        out = vm.PromptAudit()
        checker = vm.PromptChecker(run, CFG, CFG.ub_subbasin_supply_variant)
        for key in sorted(run.traces):
            checker.audit(key, run.traces[key].prompt, out)
        return out

    good = audit({("UB1", 3): _ub1_memory_2021(probe), ("LB1", 3): floor}, floor_menu=True, sub="good")
    # (the fixture's menu text keeps base 1,000 for UB1 in 2020; only the
    # 2021 lines under test are judged here)
    mine = [m for m in good.mismatches if "UB1 2021" in m or "LB1 2021" in m]
    assert not mine, mine
    assert not any("UB1 2021" in u or "LB1 2021" in u for u in good.unchecked), good.unchecked
    bad = audit({("UB1", 3): _ub1_memory_2021(probe, share_2020="1%", clause=False),
                 ("UB2", 3): _ub1_memory_2021(probe).replace("UB1", "UB2"),
                 ("LB1", 3): floor.replace("400", "500")}, sub="bad")
    joined = "\n".join(bad.mismatches)
    assert "memory line for 2020: sub-basin flow share" in joined
    assert "UB1 2021" in joined and "a keep after a short year without the change clause" in joined
    assert "UB2 2021" in joined and "change-in-request clause on a line that is not a keep after a short year" in joined
    assert "minimum-use floor: prompt '500'" in joined
    assert "floor sentence beside a decrease on the menu" in joined


def test_p6_reads_back_the_program_facts_of_a_grounded_reflection(tmp_path):
    """Spec item 45c: a grounded reflection's facts are checked against the
    log and its lesson for digits; the lesson's figures are checked against
    the memory of the year it was written and the next year's prompt."""
    memory_2020 = ("Your memory includes:\n- Year 2019: You chose to maintain demand. You requested 1,000 acre-ft "
                   "and received 1,000 acre-ft. Demand fully met.\n")
    fact = ("2020: you asked for 1,000 acre-ft, the same as the 1,000 acre-ft you received the year before, "
            "and you received 900 acre-ft (10.0% unmet).")
    good = ("Your memory includes:\n- Consolidated Reflection (written in 2020): " + fact
            + " Lesson: I learned to keep my request.\n- Year 2020: You chose to maintain demand. You requested "
              "1,000 acre-ft and received 900 acre-ft. Shortfall: 100 acre-ft (10.0% unmet).\n")
    r = vm.reflection_checks(_prompt_run(tmp_path / "good", {("UB2", 2): memory_2020, ("UB2", 3): good}))
    assert (r["grounded_reflection_lines"], r["facts_read"], r["fact_mismatches"], r["lessons_with_numbers"],
            r["foreign_figure_reflections"]) == (1, 1, 0, 0, 0), r
    wrong = good.replace("received 900 acre-ft (10.0%", "received 950 acre-ft (10.0%").replace(
        "I learned to keep my request.", "I learned that 1,000 acre-ft and 7,777 acre-ft differ.")
    r = vm.reflection_checks(_prompt_run(tmp_path / "bad", {("UB2", 2): memory_2020, ("UB2", 3): wrong}))
    assert (r["fact_mismatches"], r["lessons_with_numbers"], r["foreign_figure_reflections"]) == (1, 1, 1), r
    assert vm.gate_p6([_prompt_run(tmp_path / "gate", {("UB2", 2): memory_2020, ("UB2", 3): wrong})])["passed"] is False


def test_p6_rejects_unmatched_fact_digits_and_zero_parsed_facts(tmp_path):
    memory = "Your memory includes:\n- Year 2019: You requested 1,000 acre-ft and received 1,000 acre-ft.\n"
    unmatched = ("Your memory includes:\n- Consolidated Reflection (written in 2020): note 42; "
                 "Lesson: I learned to keep my request.\n")
    run = _prompt_run(tmp_path / "unmatched", {("UB1", 2): memory, ("UB1", 3): unmatched})
    result = vm.reflection_checks(run)
    assert result["facts_read"] == 0
    assert result["fact_texts_with_unmatched_digits"] == 1
    assert vm.gate_p6([run])["passed"] is False


def test_p6_old_style_reflection_without_program_facts_still_passes(tmp_path):
    old_style = ("Your memory includes:\n- Consolidated Reflection (written in 2020): "
                 "I learned to keep my request close to what I received.\n")
    run = _prompt_run(tmp_path, {("UB1", 3): old_style})
    result = vm.reflection_checks(run)
    assert (result["reflection_lines"], result["grounded_reflection_lines"], result["facts_read"]) == (1, 0, 0)
    assert vm.gate_p6([run])["passed"] is True


def test_p6_rejects_more_grounded_reflection_lines_than_parsed_facts(tmp_path):
    fact = "2020: you asked for 1,000 acre-ft and you received 1,000 acre-ft (fully met)."
    reflected = ("Your memory includes:\n"
                 f"- Consolidated Reflection (written in 2020): {fact} Lesson: I learned to keep my request.\n"
                 "- Consolidated Reflection (written in 2020): facts unavailable Lesson: "
                 "I learned to watch what I received.\n")
    run = _prompt_run(tmp_path, {("UB1", 3): reflected})
    run.info.manifest["reflection_checks"] = {"settings": {"program_facts": True}}
    result = vm.reflection_checks(run)
    assert (result["grounded_reflection_lines"], result["facts_read"]) == (2, 1)
    check = vm.gate_p6([run])
    assert check["passed"] is False
    assert "grounded_reflection_lines = 2 > facts_read = 1" in check["reason"]


def test_p6_reports_manifest_tallies_and_2020_plus_reflection_share(tmp_path):
    memory = "Your memory includes:\n- Year 2019: You requested 1,000 acre-ft and received 1,000 acre-ft.\n"
    fact = ("2020: you asked for 1,000 acre-ft, the same as the 1,000 acre-ft you received the year before, "
            "and you received 1,000 acre-ft (fully met).")
    reflected = ("Your memory includes:\n- Consolidated Reflection (written in 2020): " + fact
                 + " Lesson: I learned to keep my request.\n")
    path = fixture_run(tmp_path, "strict", STRICT_DECISIONS,
                       prompt_for=lambda a, t: ({("UB1", 2): memory, ("UB1", 3): reflected}.get((a, t), "")
                                                + "\n" + menu_prompt(a, t, ["increase", "keep", "decrease"])))
    manifest_path = path / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["reflection_checks"] = {
        "settings": {"lesson_no_numbers": True},
        "totals": {"stored": 2, "stored_after_retry": 1, "dropped": 1, "retried": 2},
        "dropped_by_reason": {"number": 1},
        "flagged_by_reason": {"precipitation_rule": 2, "always_full": 1},
        "per_period": {"2020": {"flagged_by_reason": {"precipitation_rule": 2, "always_full": 1}}},
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    loaded = vm.load_run(path, keep_prompts=True)
    report = vm.reflection_checks(loaded)
    assert report["manifest_reflection_checks"] == manifest["reflection_checks"]
    assert report["manifest_reflection_check_totals"] == manifest["reflection_checks"]["totals"]
    assert report["manifest_reflection_dropped_by_reason"] == {"number": 1}
    assert report["manifest_reflection_flagged_by_reason"] == {"precipitation_rule": 2, "always_full": 1}
    assert report["decision_prompts_2020_plus"] == 6
    assert report["decision_prompts_2020_plus_with_reflection"] == 1
    assert report["decision_prompts_2020_plus_reflection_share"] == pytest.approx(1 / 6)
    assert report["decision_prompts_2020_plus_reflection_share_pct"] == pytest.approx(100 / 6)
    gate = vm.gate_p6([loaded])
    gate_details = gate["details"][loaded.label]
    assert gate_details["manifest_reflection_check_totals"] == manifest["reflection_checks"]["totals"]
    assert gate_details["manifest_reflection_dropped_by_reason"] == {"number": 1}
    assert gate_details["manifest_reflection_flagged_by_reason"] == {"precipitation_rule": 2, "always_full": 1}
    assert gate_details["manifest_reflection_checks"]["per_period"]["2020"]["flagged_by_reason"] == {
        "precipitation_rule": 2, "always_full": 1}
    vm.write_pilot_gate(
        {"passed": True, "checks": [gate], "reported": []},
        tmp_path / "gate_report",
        {},
    )
    markdown = (tmp_path / "gate_report" / "v3_pilot_gate_report.md").read_text(encoding="utf-8")
    assert (f"flagged_by_reason (report-only): {loaded.label}: "
            "always_full=1, precipitation_rule=2") in markdown


def test_p6_clean_grounded_three_agent_four_year_mock_run_passes_end_to_end(tmp_path):
    decisions = {
        (agent, t): dict(attempts=[(KEEP, {"WSA_LABEL": "M", "ACA_LABEL": "M"}, [])], executed=KEEP)
        for agent in AGENTS for t in range(1, 5)
    }
    system = system_years(4, (13.0, 12.0, 11.5, 11.0), (11.0, 10.0, 9.0, 8.0), (0, 0, 1, 1))
    agent_years = {(agent, t): {} for agent in AGENTS for t in range(1, 5)}

    def prompt(agent, t):
        if t == 1:
            return menu_prompt(agent, t, ["increase", "keep", "decrease"])
        written = CFG.sim_start_year + t - 2
        fact = (f"{written}: you asked for 1,000 acre-ft and you received 1,000 acre-ft (fully met).")
        return ("Your memory includes:\n"
                f"- Consolidated Reflection (written in {written}): {fact} "
                "Lesson: I learned to keep my request close to what I received.\n"
                + menu_prompt(agent, t, ["increase", "keep", "decrease"]))

    manifest = llm_manifest("strict", grid=12, agents=sorted(AGENTS))
    manifest["reflection_checks"] = {
        "settings": {"program_facts": True, "lesson_no_numbers": True},
        "totals": {"stored": 9, "stored_after_retry": 0, "retried": 0, "dropped": 0},
        "dropped_by_reason": {},
        # Semantic flags are measurements. A nonzero total cannot fail P6.
        "flagged_by_reason": {"precipitation_rule": 2},
        "per_period": {"2020": {"flagged_by_reason": {"precipitation_rule": 2}}},
    }
    path = write_run(
        tmp_path / "grounded_mock",
        manifest,
        sim_rows(system, agent_years),
        [audit_row(agent, t, **spec) for (agent, t), spec in decisions.items()],
        [trace(agent, t, prompt=prompt(agent, t)) for agent in AGENTS for t in range(1, 5)],
    )
    run = vm.load_run(path, keep_prompts=True)
    check = vm.gate_p6([run])
    details = check["details"][run.label]
    assert check["passed"] is True, check
    assert (details["reflection_lines"], details["grounded_reflection_lines"], details["facts_read"]) == (9, 9, 9)
    assert details["decision_prompts_2020_plus_reflection_share"] == 1.0
    assert details["manifest_reflection_flagged_by_reason"] == {"precipitation_rule": 2}


def test_p6_actual_grounded_mock_run_passes_end_to_end(tmp_path, monkeypatch):
    from examples.irrigation_abm.tests.test_v3_prompt import ScriptedLLM, _run

    llm = ScriptedLLM(lambda agent, year, attempt: ("M", "M", "Keep"))
    out = _run(monkeypatch, tmp_path / "actual_grounded_mock", llm,
               "--agents", "3", "--years", "4", "--seed", "7")
    run = vm.load_run(out, keep_prompts=True)
    check = vm.gate_p6([run])
    details = check["details"][run.label]
    assert details["manifest_reflection_checks"]["settings"]["program_facts"] is True
    assert details["facts_read"] > 0
    assert details["grounded_reflection_lines"] == details["facts_read"]
    assert check["passed"] is True, check


def test_p6_lesson_digits_fail_only_when_the_manifest_enables_the_check(tmp_path):
    memory = "Your memory includes:\n- Year 2019: You requested 1,000 acre-ft and received 1,000 acre-ft.\n"
    fact = ("2020: you asked for 1,000 acre-ft, the same as the 1,000 acre-ft you received the year before, "
            "and you received 1,000 acre-ft (fully met).")
    reflected = ("Your memory includes:\n- Consolidated Reflection (written in 2020): " + fact
                 + " Lesson: I learned 2 useful habits.\n")
    run = _prompt_run(tmp_path / "digits", {("UB1", 2): memory, ("UB1", 3): reflected})
    run.info.manifest["reflection_checks"] = {"settings": {"lesson_no_numbers": True}, "totals": {},
                                               "dropped_by_reason": {}}
    assert vm.gate_p6([run])["passed"] is False
    run.info.manifest["reflection_checks"]["settings"]["lesson_no_numbers"] = False
    assert vm.gate_p6([run])["passed"] is True


def test_p6_scans_facts_and_lesson_when_the_source_prompt_crashed(tmp_path):
    fact = ("2020: you asked for 1,000 acre-ft, the same as the 1,000 acre-ft you received the year before, "
            "and you received 1,000 acre-ft (fully met).")
    reflected = ("Your memory includes:\n- Consolidated Reflection (written in 2020): " + fact
                 + " Lesson: I learned 2 useful habits.\n")
    run = _prompt_run(tmp_path, {("UB1", 3): reflected})
    run.traces[("UB1", 2)] = dataclasses.replace(run.traces[("UB1", 2)], prompt=None, crashed=True)
    run.info.manifest["reflection_checks"] = {"settings": {"lesson_no_numbers": True}, "totals": {},
                                               "dropped_by_reason": {}}
    result = vm.reflection_checks(run)
    assert result["reflection_input_check_skipped"] == 1
    assert result["facts_read"] == 1
    assert result["lessons_with_numbers"] == 1
    assert vm.gate_p6([run])["passed"] is False


def test_p6_change_direction_uses_printed_integer_amounts(tmp_path):
    fact = ("2020: you asked for 1,000 acre-ft, the same as the 1,000 acre-ft you received the year before, "
            "and you received 1,000 acre-ft (fully met).")
    reflected = ("Your memory includes:\n- Consolidated Reflection (written in 2020): " + fact
                 + " Lesson: I learned to keep my request steady.\n")
    path = fixture_run(
        tmp_path, "strict", STRICT_DECISIONS,
        prompt_for=lambda a, t: ((reflected + "\n") if (a, t) == ("UB1", 3) else "")
        + menu_prompt(a, t, ["keep"]),
    )
    rows = list(csv.DictReader(open(path / vm.SIM_LOG, encoding="utf-8")))
    for row in rows:
        if (row["agent_id"], row["year"]) == ("UB1", "1"):
            row["diversion"] = "1000.4"
        elif (row["agent_id"], row["year"]) == ("UB1", "2"):
            row["request"] = row["diversion"] = "1000.45"
    vm.write_csv(path / vm.SIM_LOG, rows)
    run = vm.load_run(path, keep_prompts=True)
    result = vm.reflection_checks(run)
    assert result["facts_read"] == 1
    assert result["fact_mismatches"] == 0
    assert vm.gate_p6([run])["passed"] is True


def _filled_review(template: Dict[str, Any], wrote_code: bool = False) -> Dict[str, Any]:
    review = json.loads(json.dumps(template))
    review.update(reviewer="someone else", reviewer_wrote_code=wrote_code)
    for entry in review["runs"]:
        for prompt in entry["prompts"]:
            prompt["sentences_without_source"] = 0
    return review


def test_p5c_record_is_tied_to_the_pilot_runs(strict_run, disabled_run):
    template = vm.p5c_review_template([strict_run, disabled_run])
    entry = template["runs"][0]
    assert (entry["label"], entry["git_commit"]) == (strict_run.label, COMMIT)
    # three years, so only 2019 is sampled: one UB and one LB prompt per run
    assert [(p["agent"], p["year"]) for p in entry["prompts"]] == [("UB1", 2019), ("LB1", 2019)]
    assert entry["prompts"][0]["prompt_sha256"] == vm.prompt_sha256(strict_run.traces[("UB1", 1)].prompt)
    assert template["reviewer_wrote_code"] is None  # left for the reviewer
    assert vm.check_p5c_review(_filled_review(template), [strict_run, disabled_run]) == {
        "reviewer": "someone else", "reviewer_wrote_code": False, "prompts_reviewed": 4,
        "sentences_without_source": 0}


@pytest.mark.parametrize("tamper,message", [
    (lambda r: r["runs"][0]["prompts"][0].update(prompt_sha256="0" * 64), "prompt_sha256 does not match"),
    (lambda r: r["runs"][0]["prompts"].pop(), "not the reading sample"),
    (lambda r: r["runs"][0]["prompts"][0].update(agent="UB2"), "not the reading sample"),
    (lambda r: r["runs"][1].update(git_commit="d" * 40), "is not the run's"),
    (lambda r: r["runs"].pop(), "not the pilot pair"),
    (lambda r: r["runs"][0]["prompts"][0].update(sentences_without_source=None), "not a count"),
    (lambda r: r.update(reviewer=""), "no reviewer named"),
    (lambda r: r.update(reviewer_wrote_code="no"), "not true or false"),
])
def test_p5c_record_not_tied_to_the_pilot_is_refused(strict_run, disabled_run, tamper, message):
    review = _filled_review(vm.p5c_review_template([strict_run, disabled_run]))
    tamper(review)
    with pytest.raises(vm.MetricsError, match=message):
        vm.check_p5c_review(review, [strict_run, disabled_run])


def test_p5a_scans_the_retry_wrapper_and_the_feasible_lines():
    texts = vm.retry_text_samples()
    joined = "\n".join(texts.values())
    assert texts["placebo retry"].strip().endswith("Please reconsider your decision.")  # the config's closer
    assert "Your proposed action 'increase demand' was BLOCKED." in joined  # plain_action_names
    assert "Under this rule an increase is not available in this decision." in joined  # a rule suggestion
    assert "Actions that pass every rule this step: 1 (increase demand), 2 (maintain demand)." in joined
    assert "Actions that pass every rule this step: 1 (maintain demand)." in joined  # the cap menu
    assert "if this continues, the default action (maintain demand) will be applied." in joined
    assert vm.banned_phrase_hits(texts) == ({}, [])
    assert vm.banned_phrase_hits({"x": "a TREND here"}) == ({"TREND": 1}, ["x: 'TREND'"])


def test_p5a_counts_a_banned_phrase_in_the_retry_texts(strict_run, monkeypatch):
    monkeypatch.setattr(vm, "P5_BANNED_PHRASES", vm.P5_BANNED_PHRASES + ("Please reconsider",))
    check = vm.gate_p5([strict_run], CFG, None, CFG.ub_subbasin_supply_variant)
    assert check["details"]["a_banned_hits_in_retry_texts"]["Please reconsider"] >= 1
    assert check["passed"] is False
    assert check["details"]["a_retry_texts_scanned"] == len(vm.retry_text_samples())


@pytest.mark.parametrize("text,gated,lesson_hits", [
    ("- Consolidated Reflection (written in 2019): My demand was fully met. Lesson: I trust my records.", False, 1),
    ("- Consolidated Reflection (written in 2019): records say demand was met. Lesson: I trust my demand.", True, 0),
    ("A heading with records.", True, 0),
    ("- Consolidated Reflection records (written in 2019): Facts. Lesson: I trust my demand.", True, 0),
    ("- Consolidated Reflection (written in 2019): I trust my records.", False, 1),
    ("- Consolidated Reflection (written in 2019): Facts. Lesson: I trust my demand. Lesson: I trust my records.", False, 1),
    ("- Consolidated Reflection (written in 2019): records say demand was met. Lesson: I trust my records.", True, 1),
])
def test_p5a_gates_program_text_and_reports_reflection_lessons(tmp_path, text, gated, lesson_hits):
    run = _prompt_run(tmp_path, {("UB1", 2): text})
    review = {"prompts_reviewed": vm.P5C_MIN_PROMPTS, "sentences_without_source": 0,
              "reviewer_wrote_code": False, "reviewer": "independent"}
    check = vm.gate_p5([run], CFG, review, CFG.ub_subbasin_supply_variant)
    details = check["details"]
    assert bool(details["a_banned_hits_in_prompts"].get("records", 0)) is gated
    assert details["a_banned_hits_in_reflection_lessons"].get("records", 0) == lesson_hits
    assert bool(details["a_reflection_lesson_examples"]) is bool(lesson_hits)
    assert ("(a) 0 banned-phrase hits" in check["reason"]) is not gated
    assert check["passed"] is not gated


def test_p5a_gates_grounded_reflection_without_lesson_separator(tmp_path):
    text = "- Consolidated Reflection (written in 2019): records say demand was met."
    run = _prompt_run(tmp_path, {("UB1", 2): text})
    run.info.manifest["reflection_checks"] = {"settings": {"program_facts": True}}
    review = {"prompts_reviewed": vm.P5C_MIN_PROMPTS, "sentences_without_source": 0,
              "reviewer_wrote_code": False, "reviewer": "independent"}
    check = vm.gate_p5([run], CFG, review, CFG.ub_subbasin_supply_variant)
    assert check["passed"] is False
    assert check["details"]["a_banned_hits_in_prompts"]["records"] == 1
    assert check["details"]["a_banned_hits_in_reflection_lines"]["records"] == 1
    assert check["details"]["a_banned_hits_in_reflection_lessons"] == {}


def test_pilot_pair_must_be_seed_42(tmp_path):
    strict = fixture_run(tmp_path, "strict", STRICT_DECISIONS, seed=43)
    disabled = fixture_run(tmp_path, "disabled", DISABLED_DECISIONS, seed=43)
    with pytest.raises(vm.MetricsError, match="pilot pair is seed 42"):
        vm.pilot_gate(str(strict), str(disabled), [str(tmp_path / "no_fql")])
    with pytest.raises(vm.MetricsError, match="pilot pair is seed 42"):
        vm.main(["p5c-sample", "--runs", str(strict), str(disabled), "--out", str(tmp_path / "p5c")])


# =============================================================================
# Fixed-demand replay A reproduces the pinned regression (item 21)
# =============================================================================

@needs_ref
def test_replay_a_matches_the_pinned_2018_fixed_demand_values():
    """test_v3_water_system.py (TestMassBalanceClosureV3) pins the 2018
    fixed-demand replay: tiers {0: 7, 1: 11, 2: 16, 3: 8} (item 36c,
    2026-10-05 design-basis audit + fix proposals, spec item 36c: moved
    from {0: 10, 1: 10, 2: 14, 3: 8} by the post2026 Equalization default
    move, hold_2026 -> extend_slope), Mead minimum 1 January storage
    unchanged at 7.0652 MAF."""
    profiles = vm.make_profiles(True, 0, 7, 0.4, "hy2021")
    rows, condition, env = vm.run_fixed_demand_replay("A", profiles, 42, 7, True)
    years = sorted({r["year"] for r in rows})
    tiers = Counter(next(r["shortage_tier"] for r in rows if r["year"] == y) for y in years)
    assert dict(tiers) == {0: 7, 1: 11, 2: 16, 3: 8}
    assert min(r["mead_storage_maf"] for r in rows) == pytest.approx(7.0652, abs=1e-3)
    assert env.config.hold_requests_fixed is True
    # every agent's request is its 2018 use in every year
    assert len({(r["agent_id"], r["request"]) for r in rows}) == 78
    assert len(condition) == 78 * 42


# =============================================================================
# End to end: five arms through the real runner, FQL seeds, replays
# =============================================================================

YEARS, N_AGENTS = 4, 6


class ScriptedModel:
    """A deterministic stand-in for the model (no Ollama): per agent, a fixed
    behaviour that exercises the rules; per seed, Agent_003 alternates."""

    def __init__(self, seed: int, real: bool = False):
        self.seed, self.real = seed, real
        self.calls: Counter = Counter()
        self.lock = threading.Lock()

    def answer(self, agent: str, year: int, attempt: int):
        if self.real:
            h = sum(map(ord, agent)) + year
            wsa = ("VL", "L", "M", "H", "VH")[h % 5]
            return wsa, "M", ("Increase", "Increase", "Decrease", "Keep")[h % 4] if attempt == 0 else "Keep"
        i = int(agent[-1])
        if agent == "Agent_003" and year == 2020:
            return "GARBAGE"
        if i == 0:   # TR1, then a relabel to M, then keep
            return [("H", "M", "Increase"), ("M", "M", "Increase")][attempt] if attempt < 2 else ("M", "M", "Keep")
        if i == 1:   # TR3, then keep
            return ("L", "M", "Decrease") if attempt == 0 else ("L", "M", "Keep")
        if i == 2:   # three answers without a WSA: the first parsed attempt omits it
            if attempt < 3:
                return None, "M", "Keep"
            return ("VH", "H", "Increase") if attempt == 3 else ("VH", "H", "Keep")
        if i == 3:   # persists on VH + increase in alternate years: exhausted in strict
            return ("VH", "VH", "Increase") if (self.seed + year) % 2 else ("M", "M", "Keep")
        if i == 4:
            return "VL", "M", "Increase"
        return "H", "H", "Decrease"

    def __call__(self, prompt: str):
        from broker.utils.llm_utils import LLMStats
        stats = LLMStats(retries=0, success=True)
        if "You are a Reflection Assistant" in prompt:
            ids = re.findall(r"^(.+?) Memories:", prompt, flags=re.M)
            return json.dumps({a: "I learned to watch my supply before changing my request." for a in ids}), stats
        agent = re.search(r"You are (.+?), an agricultur", prompt).group(1)
        year = int(re.search(r"It is now the year (\d{4})", prompt).group(1))
        with self.lock:
            attempt = self.calls[(agent, year)]
            self.calls[(agent, year)] += 1
        menu = {m.group(2): int(m.group(1)) for m in re.finditer(
            r"^(\d+)\. (Increase|Keep|Decrease) your request", prompt, flags=re.M)}
        answer = self.answer(agent, year, attempt)
        if answer == "GARBAGE":
            return "no decision here", stats
        wsa, aca, choice = answer
        payload: Dict[str, Any] = {"reasoning": "Scripted answer."}
        if wsa is not None:
            payload["water_scarcity_assessment"] = {"label": wsa, "reason": "Scripted."}
        payload["adaptive_capacity_assessment"] = {"label": aca, "reason": "Scripted."}
        payload["decision"] = menu.get(choice, menu["Keep"])
        return "<<<DECISION_START>>>\n" + json.dumps(payload) + "\n<<<DECISION_END>>>", stats


ARM_ARGS = {"strict": [], "placebo": ["--retry-feedback-mode", "placebo"],
            "silent": ["--retry-feedback-mode", "silent"], "disabled": ["--governance-mode", "disabled"],
            "feasibility_only": ["--governance-mode", "feasibility_only"]}


def _run_llm(mp: pytest.MonkeyPatch, out: Path, arm: str, seed: int, real: bool = False) -> Path:
    import broker.utils.llm_utils as llm_utils
    from broker.utils.agent_config import AgentTypeConfig
    from examples.irrigation_abm import run_experiment
    model = ScriptedModel(seed, real)
    mp.setattr(run_experiment, "create_llm_invoke", lambda model_name, verbose=False: model)
    mp.setattr(llm_utils, "create_llm_invoke", lambda model_name, verbose=False, overrides=None: model)
    size = ["--real", "--years", "3"] if real else ["--years", str(YEARS), "--agents", str(N_AGENTS)]
    mp.setattr(sys, "argv", ["run_experiment.py", "--model", "mock", "--output", str(out), "--workers", "1",
                             "--seed", str(seed), *size, *ARM_ARGS[arm]])
    run_experiment.main()
    AgentTypeConfig.clear_cache()
    return out


def _run_fql(mp: pytest.MonkeyPatch, out: Path, seed: int, real: bool = False) -> Path:
    from examples.irrigation_abm import run_fql_baseline
    size = (["--real", "--fql-init", "calibrated", "--years", "3"] if real
            else ["--fql-init", "zero", "--years", str(YEARS), "--agents", str(N_AGENTS)])
    mp.setattr(sys, "argv", ["run_fql_baseline.py", "--no-governance", "--seed", str(seed),
                             "--output", str(out), *size])
    run_fql_baseline.main()
    return out


@pytest.fixture(scope="module")
def mock_corpus(tmp_path_factory):
    root = tmp_path_factory.mktemp("v3_corpus")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GOVERNANCE_PROFILE", "strict")
        for arm in vm.ARMS:
            for seed in ([42] if arm == "feasibility_only" else [42, 43]):
                _run_llm(mp, root / "runs" / f"{arm}_seed{seed}", arm, seed)
        for seed in (42, 43, 44):
            _run_fql(mp, root / "fql" / f"seed{seed}", seed)
        vm.main(["replay", "--agents", str(N_AGENTS), "--years", str(YEARS), "--seed", "42",
                 "--out", str(root / "replays")])
    return root


def _independent_ibr(run_dir: Path) -> Tuple[int, int, int]:
    """TR1 and TR3 counts and decisions, recomputed straight from the CSV."""
    with open(run_dir / vm.AUDIT_CSV, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    tr1 = tr3 = 0
    for row in rows:
        if row["execution_path"] == "aborted":
            continue
        initial = dict(p.split("=", 1) for p in row["initial_labels"].split("|") if p)
        wsa = initial.get("WSA_LABEL", "")
        if not wsa:
            for group in row["attempt_labels"].split("|"):
                labels = dict(p.split("=", 1) for p in group.split(",") if p)
                if labels.get("WSA_LABEL"):
                    wsa = labels["WSA_LABEL"]
                    break
        final = row["attempt_skills"].split("|")[-1]
        tr1 += final == INC and wsa in ("H", "VH")
        tr3 += final == DEC and wsa in ("VL", "L")
    return tr1, tr3, len(rows)


def test_e2e_metrics_over_all_five_arms(mock_corpus, tmp_path):
    """The mock runs come from this worktree, which may be dirty: --allow-dirty
    pools them and records the override."""
    out = tmp_path / "metrics"
    assert vm.main(["metrics", "--runs", str(mock_corpus / "runs"), "--fql", str(mock_corpus / "fql"),
                    "--replays", str(mock_corpus / "replays"), "--out", str(out), "--allow-dirty"]) == 0
    for name in ("per_run_metrics.csv", "arm_summary.csv", "paired_tests.csv", "feasibility_only_vs_ranges.csv",
                 "rule_census.csv", "supply_exposure.csv", "rule_agreement.csv", "kge.csv",
                 "kge_fql_benchmark_summary.csv", "lb_agent_kge.csv", "lb_agent_ceilings.csv",
                 "drought_recovery.csv", "drought_recovery_summary.csv", "replays.csv", "provenance.json",
                 "v3_metrics.md", "r5a_wsa_by_band.csv", "r5a_wsa_by_band_summary.csv",
                 "r5b_wsa_by_short_years.csv", "r5b_wsa_by_short_years_summary.csv",
                 "r5c_wsa_by_spell_year.csv", "r5c_wsa_by_spell_year_summary.csv",
                 "r5d_unblocked_increase_share.csv", "r5d_unblocked_increase_share_summary.csv",
                 "r5d_ub_little_spare.csv", "r5d_ub_little_spare_summary.csv"):
        assert (out / name).is_file(), name
    # spec 7.2: the LLM manifests now record the sub-basin keys, so every
    # water-system key is compared across all runs
    provenance = json.loads((out / "provenance.json").read_text(encoding="utf-8"))
    assert all(not v["not_recorded_by"] for v in provenance["water_system"].values())
    assert len(provenance["water_system"]["ub_supply_mode"]["values"]) == 1
    assert len(provenance["water_system"]["ub_subbasin_variant_means_sha256"]["values"]) == 1
    assert provenance["allow_dirty"] is True and provenance["differences"] == []
    assert provenance["dirty_override_applied"] is bool(provenance["dirty_runs"])
    rows = {r["run"]: r for r in csv.DictReader(open(out / "per_run_metrics.csv", encoding="utf-8"))}
    assert sorted(rows) == sorted(f"{a}_seed{s}" for a in vm.ARMS for s in ([42] if a == "feasibility_only" else [42, 43]))
    for label, row in rows.items():
        tr1, tr3, n = _independent_ibr(mock_corpus / "runs" / label)
        assert int(row["decisions"]) == n == YEARS * N_AGENTS
        assert (int(row["ibr_tr1_count"]), int(row["ibr_tr3_count"])) == (tr1, tr3), label
        assert float(row["ibr_pct"]) == pytest.approx(float(row["ibr_tr1_pct"]) + float(row["ibr_tr3_pct"]))
        assert int(row["unreadable_final_proposals"]) == 1  # Agent_003 2020 is ABORTED in every arm
        if row["arm"] != "disabled":
            assert float(row["exec_total_pct"]) == 0.0
    # thinking rules cut the IBR in the governed arms only
    assert float(rows["strict_seed42"]["ibr_pct"]) < float(rows["disabled_seed42"]["ibr_pct"])
    assert float(rows["feasibility_only_seed42"]["ibr_pct"]) == pytest.approx(float(rows["disabled_seed42"]["ibr_pct"]))
    # Agent_002's first parsed attempt omits the WSA; in disabled its VH +
    # increase on the retry is a TR1 violation only through the item 28
    # fallback to attempt_labels
    disabled = vm.load_run(mock_corpus / "runs" / "disabled_seed42")
    fallback = [d for (a, _), d in disabled.decisions.items() if a == "Agent_002"]
    assert fallback and all(d.attempts[0].labels.get("WSA_LABEL") is None and d.first_wsa == "VH"
                            and d.final_proposal == INC for d in fallback)
    agreement = list(csv.DictReader(open(out / "rule_agreement.csv", encoding="utf-8")))
    assert agreement and all(a["disagreements"] == "0" for a in agreement)
    paired = list(csv.DictReader(open(out / "paired_tests.csv", encoding="utf-8")))
    sd = next(t for t in paired if t["comparison"] == "strict - disabled" and t["metric"] == "ibr_pct")
    assert (sd["n_pairs"], sd["p_floor"], sd["seeds"]) == ("2", "0.5", "42 43")
    # the executed rates only where disabled is one side; seeds = the seeds paired
    exec_rows = [t for t in paired if t["metric"].startswith("exec_")]
    assert exec_rows and all("disabled" in t["comparison"].split(" - ") for t in exec_rows)
    assert all(len(t["seeds"].split()) == int(t["n_pairs"]) for t in paired)
    lb = next(t for t in paired if t["comparison"] == "strict - disabled"
              and t["metric"] == "kge_lb_agent_request_median")
    assert len(lb["lb_agents_constant_sim_first"].split()) == len(lb["lb_agents_undefined_second"].split()) == 2
    assert {"kge_total_request_maf", "kge_total_delivered_maf"} <= {t["metric"] for t in paired}
    for label, row in rows.items():
        assert row["kge_total_request_maf"] != "" and row["kge_lb_agent_constant_sim"] != "", label
    summary_metrics = {r["metric"] for r in csv.DictReader(open(out / "arm_summary.csv", encoding="utf-8"))}
    assert {"kge_lb_agent_constant_sim", "kge_lb_agent_undefined", "kge_total_request_maf"} <= summary_metrics
    md = (out / "v3_metrics.md").read_text(encoding="utf-8")
    for heading in ("## IBR (items 37, 37a)",
                    "## IBR by attempt: first proposal vs final proposal vs executed (items 37, 37a)",
                    "## Executed feasibility violation rate", "## Supply-rule exposure",
                    "## KGE against the FQL ensemble mean", "## R4 drought recovery", "## Paired comparisons",
                    "## Feasibility-only run against the five-seed ranges", "## Rule census"):
        assert heading in md
    assert "the median KGE of the LB request TOTAL, not a per-agent figure" in md
    assert "| fql, leave-one-out |" in md and "| median " in md  # item 30: the FQL median
    # replays: the held request series are marked as convention-scored floors
    replays = list(csv.DictReader(open(out / "replays.csv", encoding="utf-8")))
    assert len(replays) == 2
    for r in replays:
        assert "kge_total_request_maf" in r["kge_convention_series"].split("|"), r["run"]
        assert "no-change floor, not a model result" in r["kge_note"]
    assert " (c) |" in md
    assert "r is fixed within a decision, so that share is always 100%" in md
    assert "0 by construction" in md and "2^(z + 1) / 2^n" in md
    assert "provisional" not in md and "relabel_no_r_change" not in md
    assert chr(0x2014) not in md  # no em dash
    summary = list(csv.DictReader(open(out / "drought_recovery_summary.csv", encoding="utf-8")))
    assert {r["arm"] for r in summary} == set(vm.ARMS) | {"fql"}
    assert all(r["subbasin"] == "pooled" for r in summary)  # synthetic agents have no sub-basin


def test_e2e_mixed_provenance_refused_then_recorded(mock_corpus, tmp_path):
    runs = tmp_path / "runs"
    shutil.copytree(mock_corpus / "runs" / "strict_seed42", runs / "strict_seed42")
    shutil.copytree(mock_corpus / "runs" / "disabled_seed42", runs / "disabled_seed42")
    manifest_path = runs / "disabled_seed42" / vm.MANIFEST
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["git_commit"] = "0" * 40
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    args = ["metrics", "--runs", str(runs), "--fql", str(mock_corpus / "fql"), "--out", str(tmp_path / "out"),
            "--allow-dirty"]
    with pytest.raises(vm.ProvenanceError, match="code commit differs"):
        vm.main(args)
    assert vm.main(args + ["--allow-mixed-provenance"]) == 0
    md = (tmp_path / "out" / "v3_metrics.md").read_text(encoding="utf-8")
    assert "PROVENANCE OVERRIDE" in md and "code commit differs" in md
    assert json.loads((tmp_path / "out" / "provenance.json").read_text(encoding="utf-8"))["override_applied"] is True


def test_e2e_pilot_gate_on_the_mock_pair(mock_corpus, tmp_path):
    """The synthetic pair is too small for P4, P8 and P10 (24 rows, not
    3,276) and has no P5(c) record; every other gated check runs on real
    runner output. --allow-dirty alone already keeps the gate from passing."""
    code = vm.main(["pilot-gate", "--runs", str(mock_corpus / "runs" / "strict_seed42"),
                    str(mock_corpus / "runs" / "disabled_seed42"), "--fql", str(mock_corpus / "fql"),
                    "--replays", str(mock_corpus / "replays"), "--out", str(tmp_path), "--allow-dirty"])
    report = json.loads((tmp_path / "v3_pilot_gate_report.json").read_text(encoding="utf-8"))
    checks = {c["id"]: c for c in report["checks"]}
    assert code == 1 and report["passed"] is False
    assert report["provenance_overrides"] == ["--allow-dirty"] and report["required_rows"] == 3276
    assert "never passes" in (tmp_path / "v3_pilot_gate_report.md").read_text(encoding="utf-8")
    assert checks["P4"]["passed"] is False
    assert "P8 requires 3276" in checks["P8"]["reason"] and "not all 3276" in checks["P10"]["reason"]
    assert "not supplied" in checks["P5"]["reason"]
    assert checks["P5"]["details"]["a_retry_texts_scanned"] > 0
    # Regression (WP6 fix round): Agent_003's 2020 decision is ABORTED in
    # both runs; before the fix every later prompt repeated its 2019 action
    # in the 2020 memory line, which P5(b) caught as mismatches.
    assert checks["P5"]["details"]["b_mismatch_count"] == 0, checks["P5"]["details"]["b_mismatches"]
    assert checks["P5"]["details"]["b_unchecked_count"] == 0
    for run in ("strict_seed42", "disabled_seed42"):
        prompt = vm.load_traces(mock_corpus / "runs" / run, keep_prompts=True)[("Agent_003", 4)].prompt
        memory = [line for line in prompt.splitlines() if line.startswith("- Year 2020:")]
        assert memory and memory[0].startswith(
            "- Year 2020: no valid decision was read; your request stayed at the amount you received the "
            "year before. You requested "), (run, memory)
    for check_id in ("P1", "P2", "P6", "P9"):
        assert checks[check_id]["passed"] is True, checks[check_id]["reason"]
    assert checks["P3"]["gated"] is False
    assert {r["id"] for r in report["reported"]} == {"R1", "R2", "R3", "R4"}


def test_r5_functions_monkeypatched_to_raise_do_not_change_pilot_gate(mock_corpus, tmp_path, monkeypatch):
    """Empirical companion to test_r5_never_changes_the_pilot_gate_verdict
    (reviewer fix, 2026-10-01): even if every R5 function were wired into
    pilot_gate by mistake, its verdict on the mock pair is byte-for-byte
    unchanged from test_e2e_pilot_gate_on_the_mock_pair, because it never
    calls them. drought_recovery, ub_subbasin_dry_years and
    _ub_subbasin_available_af are deliberately NOT in this list: report_r4
    legitimately calls them inside pilot_gate (R4 is a real, intentional
    "reported" item), and that must keep working."""
    def boom(*a, **k):
        raise AssertionError("pilot_gate must not call an R5 function")
    for name in ("r5a_wsa_by_band", "r5a_band_summary", "r5b_wsa_by_short_years", "r5b_summary_table",
                "r5c_wsa_by_spell_year", "r5c_summary_table", "r5d_rows", "r5d_summary_table",
                "r5d_ub_little_spare", "r5d_ub_little_spare_summary"):
        monkeypatch.setattr(vm, name, boom)
    code = vm.main(["pilot-gate", "--runs", str(mock_corpus / "runs" / "strict_seed42"),
                    str(mock_corpus / "runs" / "disabled_seed42"), "--fql", str(mock_corpus / "fql"),
                    "--replays", str(mock_corpus / "replays"), "--out", str(tmp_path), "--allow-dirty"])
    report = json.loads((tmp_path / "v3_pilot_gate_report.json").read_text(encoding="utf-8"))
    assert code == 1 and report["passed"] is False
    assert report["provenance_overrides"] == ["--allow-dirty"] and report["required_rows"] == 3276
    assert {r["id"] for r in report["reported"]} == {"R1", "R2", "R3", "R4"}


@pytest.fixture(scope="module")
def real_pilot(tmp_path_factory):
    if not _REAL_REF_AVAILABLE:
        pytest.skip("CRSS reference data not found under ref/")
    root = tmp_path_factory.mktemp("v3_real")
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("GOVERNANCE_PROFILE", "strict")
        _run_llm(mp, root / "strict_seed42", "strict", 42, real=True)
        _run_llm(mp, root / "disabled_seed42", "disabled", 42, real=True)
        for seed in (42, 43, 44):
            _run_fql(mp, root / "fql" / f"seed{seed}", seed, real=True)
        vm.main(["replay", "--real", "--years", "3", "--seed", "42", "--out", str(root / "replays")])
    return root


def _gate(root: Path, out: Path, strict: Optional[Path] = None, review: Optional[Path] = None,
          flags: Sequence[str] = ("--allow-dirty",)) -> Tuple[int, Dict[str, Any]]:
    args = ["pilot-gate", "--runs", str(strict or root / "strict_seed42"), str(root / "disabled_seed42"),
            "--fql", str(root / "fql"), "--replays", str(root / "replays"), "--out", str(out), *flags]
    if review is not None:
        args += ["--p5c-review", str(review)]
    code = vm.main(args)
    return code, json.loads((out / "v3_pilot_gate_report.json").read_text(encoding="utf-8"))


def _clean_copy(root: Path, dest: Path) -> Path:
    """The pilot pair, FQL seeds and replays with every manifest marked
    clean, as runs from a clean worktree of the tag record it (spec 7.2)."""
    shutil.copytree(root, dest)
    for path in dest.rglob(vm.MANIFEST):
        manifest = json.loads(path.read_text(encoding="utf-8"))
        manifest["git_dirty"] = False
        if "git_dirty_at_finalize" in manifest:
            manifest["git_dirty_at_finalize"] = False
        path.write_text(json.dumps(manifest), encoding="utf-8")
    return dest


def _write_review(root: Path, out: Path, wrote_code: bool = False) -> Path:
    """Run p5c-sample and fill in its template as a reviewer would."""
    assert vm.main(["p5c-sample", "--runs", str(root / "strict_seed42"), str(root / "disabled_seed42"),
                    "--out", str(out)]) == 0
    review = _filled_review(json.loads((out / vm.P5C_TEMPLATE).read_text(encoding="utf-8")), wrote_code)
    path = out / "p5c_review.json"
    path.write_text(json.dumps(review), encoding="utf-8")
    return path


def test_e2e_real_pilot_pair_passes_only_clean_and_without_an_override(real_pilot, tmp_path, monkeypatch):
    """78 real agents, three years, scripted answers. With the row count of a
    three-year run and its 4-prompt reading sample in place of the 42-year
    ones, every gated check passes, including P5(b) on real-format prompts
    (sub-basin, Powell and Lower Basin tier sentences), P5(c) on a record
    tied to the runs, and P7's live-versus-post-hoc agreement with live
    supply-rule blocks; the gate exits 0 only for clean manifests and no
    provenance override."""
    monkeypatch.setattr(vm, "FULL_CORPUS_ROWS", 78 * 3)
    monkeypatch.setattr(vm, "P5C_MIN_PROMPTS", 4)
    root = _clean_copy(real_pilot, tmp_path / "clean")
    review = _write_review(root, tmp_path / "p5c")
    prompts = sorted((tmp_path / "p5c" / "p5c_prompts").rglob("*.txt"))
    template = json.loads((tmp_path / "p5c" / vm.P5C_TEMPLATE).read_text(encoding="utf-8"))
    assert len(prompts) == 4 and all(p["prompt_file"] for e in template["runs"] for p in e["prompts"])
    for entry in template["runs"]:  # each file is the hashed text, byte for byte
        for p in entry["prompts"]:
            text = (tmp_path / "p5c" / p["prompt_file"]).read_bytes().decode("utf-8")
            assert vm.prompt_sha256(text) == p["prompt_sha256"]
    code, report = _gate(root, tmp_path / "gate", review=review, flags=())
    checks = {c["id"]: c for c in report["checks"]}
    assert code == 0 and report["passed"] is True, {k: c["reason"] for k, c in checks.items()}
    assert checks["P5"]["details"]["b_prompts"] == 2 * 78 * 3
    assert checks["P5"]["details"]["c_review"]["prompts_reviewed"] == 4
    # The three-year item-49 fixture has no supply-rule blocks: requests
    # stay below that predicate after the beneficial-use clamp.  The separate
    # 42-year governance test exercises live supply blocks and agreement.
    assert checks["P7"]["details"]["strict_agreement"][SUP]["live"] == 0
    # the same runs under an override never pass
    for flag in ("--allow-dirty", "--allow-mixed-provenance"):
        code, report = _gate(root, tmp_path / f"gate{flag}", review=review, flags=(flag,))
        assert code == 1 and report["passed"] is False and report["gated_checks_passed"] is True, flag
        assert report["provenance_overrides"] == [flag]
    # a reviewer who wrote the code fails P5(c)
    review = _write_review(root, tmp_path / "p5c_author", wrote_code=True)
    code, report = _gate(root, tmp_path / "gate_author", review=review, flags=())
    p5 = next(c for c in report["checks"] if c["id"] == "P5")
    assert code == 1 and p5["passed"] is False and p5["details"]["c_passed"] is False


def test_e2e_real_pilot_runs_from_a_dirty_tree_are_refused(real_pilot, tmp_path):
    root = _clean_copy(real_pilot, tmp_path / "clean")
    path = root / "disabled_seed42" / vm.MANIFEST
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest["git_dirty"] = True
    path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(vm.ProvenanceError, match="disabled_seed42: git_dirty=True"):
        _gate(root, tmp_path / "gate", flags=())


def test_e2e_real_pilot_gate_catches_a_wrong_prompt_number(real_pilot, tmp_path):
    strict = tmp_path / "strict_seed42"
    shutil.copytree(real_pilot / "strict_seed42", strict)
    path = strict / vm.TRACES
    lines = path.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        rec = json.loads(line)
        if rec.get("agent_id") and "Your water right is " in rec.get("input", ""):
            rec["input"] = re.sub(r"Your water right is ([\d,]+)", "Your water right is 1,234,567", rec["input"], count=1)
            lines[i] = json.dumps(rec)
            break
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    code, report = _gate(real_pilot, tmp_path / "out", strict=strict)
    p5 = next(c for c in report["checks"] if c["id"] == "P5")
    assert code == 1 and p5["passed"] is False
    assert p5["details"]["b_mismatch_count"] == 1 and "1,234,567" in p5["details"]["b_mismatches"][0]
