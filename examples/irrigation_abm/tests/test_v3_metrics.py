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
        "lb_non_ag_total_maf": CFG.lb_non_ag_total_maf, "paper_water_margin": 0.4,
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
               "typical_step_af": 100.0, "magnitude_pct": "", "lb_junior_tier_cut_fraction": "" if sb else 0.0}
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
    assert {rule: a["disagreements"] for rule, a in agreement.items()} == {r: 0 for r in vm.ALL_RULES}
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


def _recovery_sim(tmp_path: Path, ratios: Sequence[float], requests: Sequence[float]) -> vm.SimLog:
    n = len(ratios)
    hydrology = _load_hydrology_table()
    system = system_years(n, [13.0] * n, [11.0] * n, [0] * n)
    for t in system:
        system[t]["calendar_year"] = hydrology[CFG.sim_start_year + t - 1]["source_calendar_year"]
    years = {("UB1", t): {"ub_subbasin_ratio": ratios[t - 1], "request": requests[t - 1] / 2}
             for t in range(1, n + 1)}
    years.update({("UB2", t): {"ub_subbasin_ratio": ratios[t - 1], "request": requests[t - 1] / 2}
                  for t in range(1, n + 1)})
    path = write_run(tmp_path / "r4", fql_manifest(42), sim_rows(system, years))
    return vm.load_sim_log(path)


def test_drought_recovery_hand_computed(tmp_path):
    sim = _recovery_sim(tmp_path, [1.0, 0.8, 0.9, 1.0, 1.0, 1.0], [100, 90, 80, 90, 101, 105])
    (spell,) = vm.drought_recovery(sim, "x", "strict")
    assert (spell["subbasin"], spell["start_year"], spell["end_year"], spell["dry_years"]) == (
        "UT1", 2020, 2021, 2)
    # reference: the 2019 total, 100; 2022 has 90, 2023 has 101, so j = 2
    assert (spell["reference_request_af"], spell["status"], spell["recovery_years"]) == (100, "recovered", 2)


@pytest.mark.parametrize("ratios,requests,status,censored_by", [
    ([0.8, 1.0, 1.0], [100, 90, 100], "no reference", ""),            # starts in year 1: skipped
    ([1.0, 0.8, 1.0], [100, 90, 95], "censored", "end of run"),
    ([1.0, 0.8, 1.0, 0.7, 1.0], [100, 90, 95, 80, 120], "censored", "next spell"),
    ([1.0, 0.8, 0.7, 1.0], [100, 90, 101, 100], "recovered", ""),     # a dry year above the reference is no recovery
])
def test_drought_recovery_censored_and_skipped(tmp_path, ratios, requests, status, censored_by):
    spell = vm.drought_recovery(_recovery_sim(tmp_path, ratios, requests), "x", "strict")[0]
    assert (spell["status"], spell["censored_by"]) == (status, censored_by)
    if status == "recovered":
        assert spell["recovery_years"] == 1  # j counts from the last spell year


def test_drought_recovery_compares_float_safely(tmp_path):
    """The reference total 0.1 + 0.2 = 0.30000000000000004 and a later total
    of exactly 0.3 count as equal: recovered, not censored."""
    spell = vm.drought_recovery(_recovery_sim(tmp_path, [1.0, 0.8, 1.0], [0.1 + 0.2, 0.1, 0.3]), "x", "strict")[0]
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


# =============================================================================
# Pilot gate checks on the fixtures
# =============================================================================

def test_p1_closure_and_a_residual(tmp_path, strict_run):
    assert vm.gate_p1([strict_run])["passed"] is True
    broken = vm.load_run(fixture_run(tmp_path, "strict", STRICT_DECISIONS, name="broken", unbalance={2: 1e-6}))
    check = vm.gate_p1([broken])
    assert check["passed"] is False and "2020" in check["reason"]


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
    return vm.load_run(fixture_run(tmp_path, "strict", STRICT_DECISIONS, prompt_for=prompt_for), keep_prompts=True)


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
    fixed-demand replay: tiers {0: 10, 1: 10, 2: 14, 3: 8}, Mead minimum
    1 January storage 7.0652 MAF."""
    profiles = vm.make_profiles(True, 0, 7, 0.4, "hy2021")
    rows, condition, env = vm.run_fixed_demand_replay("A", profiles, 42, 7, True)
    years = sorted({r["year"] for r in rows})
    tiers = Counter(next(r["shortage_tier"] for r in rows if r["year"] == y) for y in years)
    assert dict(tiers) == {0: 10, 1: 10, 2: 14, 3: 8}
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
        if "Lesson Learned" in prompt:
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
                 "v3_metrics.md"):
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
    for heading in ("## IBR (item 19)", "## Executed feasibility violation rate", "## Supply-rule exposure",
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
    assert checks["P7"]["details"]["strict_agreement"][SUP]["live"] > 0
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
