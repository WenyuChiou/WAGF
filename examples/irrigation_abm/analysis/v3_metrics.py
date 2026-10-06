"""Irrigation case v3 metrics (WP6): the numbers the paper reports, and the pilot gate.

Every definition is written out, with its formula and the columns it reads, in
``examples/irrigation_abm/docs/v3_metrics.md`` (the reference the Methods cite).
Sources: ``.research/design_specs/irrigation_v3_spec_2026-09-28.md`` (WP6, the pilot
gate of section 4 with checks P1-P10 and reports R1-R4, WP7, PI items 16, 19, 21, 23,
25-28 and 30) and the audit columns of ``docs/AUDIT_SCHEMA.md``. It supersedes the
prototype ``SUBMISSION_2026/reviewer_prep_2026-09-05/scripts/r43_irrigation_v3_metrics.py``.

Inputs
    LLM run (``run_experiment.py --output``): ``reproducibility_manifest.json``,
    ``simulation_log.csv``, ``irrigation_farmer_governance_audit.csv`` and
    ``raw/irrigation_farmer_traces.jsonl``.
    FQL reference seed (``run_fql_baseline.py --output``): the manifest and
    ``simulation_log.csv``.
    Fixed-demand replay (this module's ``replay`` command, item 21): the manifest,
    ``simulation_log.csv`` and ``supply_rule_condition.csv``.

Fail-loud contract
    A missing file or column, a blank cell where a number is required, or two
    artifacts of one run that disagree raise ``MetricsError``. Runs whose manifests
    differ in code commit, water-system configuration, model or seed scheme, or
    break a spec 7.2 value, raise ``ProvenanceError`` unless
    ``allow_mixed_provenance`` is set; a run from a dirty tree is refused unless
    ``allow_dirty`` (or ``allow_mixed_provenance``) is set. Every override is
    written into the output. No value is filled with a default.

CLI
    python examples/irrigation_abm/analysis/v3_metrics.py metrics \\
        --runs RUN_DIR [RUN_DIR ...] --fql FQL_DIR [FQL_DIR ...] [--replays DIR] \\
        --out OUT_DIR [--allow-mixed-provenance] [--allow-dirty]
    python examples/irrigation_abm/analysis/v3_metrics.py p5c-sample \\
        --runs STRICT_42_DIR DISABLED_42_DIR --out OUT_DIR
    python examples/irrigation_abm/analysis/v3_metrics.py pilot-gate \\
        --runs STRICT_42_DIR DISABLED_42_DIR --fql FQL_DIR [FQL_DIR ...] \\
        [--replays DIR] [--p5c-review REVIEW.json] --out OUT_DIR
    python examples/irrigation_abm/analysis/v3_metrics.py replay \\
        (--real | --agents N) --years 42 --seed 42 --out DIR

``--runs`` and ``--fql`` take run directories, or a parent directory whose immediate
subdirectories are run directories (``results/fql_raw`` holding ``seed42`` ...).
The pilot gate writes ``v3_pilot_gate_report.json`` and exits 0 only if every gated
check passes and no provenance override (``--allow-mixed-provenance``,
``--allow-dirty``) is in force. ``p5c-sample`` writes the P5(c) review template
(run labels, commits, the sampled prompts and their sha256) and the prompt texts.
"""
from __future__ import annotations

import argparse
import csv
import dataclasses
import hashlib
import itertools
import json
import math
import re
import statistics
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

import numpy as np
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.irrigation_abm.irrigation_env import (  # noqa: E402
    HYDROLOGY_V3_SHA256,
    LB_PRIORITY_SPLIT_SHA256,
    MEAD_CAPACITY_SHA256,
    POWELL_CURVE_ACTIVE_STORAGE_MAF,
    POWELL_CURVE_ELEVATION_FT,
    UB_SUBBASIN_ENVELOPE_SHA256,
    UB_SUBBASIN_VARIANT_MEANS_SHA256,
    IrrigationEnvironment,
    WaterSystemConfig,
    _UB_SUBBASIN_SUPPLY_VARIANT_FILES,
    _load_hydrology_table,
    _load_lb_priority_split_table,
    _load_ub_subbasin_supply_table,
    _load_ub_subbasin_variant_means,
)
from examples.irrigation_abm.irrigation_personas import (  # noqa: E402
    FULL_SUPPLY_RATIO,
    format_share,
    supply_ratio,
)
from examples.irrigation_abm.validators.irrigation_validators import (  # noqa: E402
    SUPPLY_RULE_FIELDS,
)

# =============================================================================
# Pre-registered definitions (spec WP6; PI items 9, 16, 19, 21, 28)
# =============================================================================

INCREASE = "increase_demand"
KEEP = "maintain_demand"
DECREASE = "decrease_demand"

RULE_SUPPLY = "supply_gap_block_increase"
RULE_CAP = "water_right_cap"
RULE_FLOOR = "minimum_utilisation_floor"
RULE_TR1 = "high_scarcity_no_increase"
RULE_TR3 = "low_scarcity_no_decrease"
FEASIBILITY_RULES = (RULE_SUPPLY, RULE_CAP, RULE_FLOOR)
THINKING_RULES = (RULE_TR1, RULE_TR3)
ALL_RULES = FEASIBILITY_RULES + THINKING_RULES
# The skill each rule blocks (spec 3.1, 3.3, 3.4).
BLOCKED_SKILL = {
    RULE_SUPPLY: INCREASE, RULE_CAP: INCREASE, RULE_FLOOR: DECREASE,
    RULE_TR1: INCREASE, RULE_TR3: DECREASE,
}

WSA_KEY = "WSA_LABEL"
ACA_KEY = "ACA_LABEL"
LEVELS = ("VL", "L", "M", "H", "VH")
# Item 9: TR1 = WSA High or Very High with an increase; TR3 = WSA Very Low or
# Low with a decrease. Cross-checked against the strict profile of
# config/agent_types.yaml on every metrics and gate run
# (``assert_thinking_rules_match_config``), so the post hoc rule is the live one.
TR1_WSA = frozenset({"H", "VH"})
TR3_WSA = frozenset({"VL", "L"})
HIGH_LEVELS = frozenset({"H", "VH"})  # R2: TR2 reads WSA and ACA High or Very High

ARMS = ("strict", "disabled", "placebo", "silent", "feasibility_only")
SEED_ARMS = ("strict", "disabled", "placebo", "silent")
# Paired comparisons across seeds (difference = first minus second).
PAIRED_COMPARISONS = (
    ("strict", "disabled"), ("placebo", "strict"), ("silent", "strict"),
    ("placebo", "disabled"), ("silent", "disabled"), ("placebo", "silent"),
)
# Rules live in each arm (spec 3.1); every other rule is scored post hoc.
LIVE_RULES = {
    "strict": frozenset(ALL_RULES),
    "placebo": frozenset(ALL_RULES),
    "silent": frozenset(ALL_RULES),
    "feasibility_only": frozenset(FEASIBILITY_RULES),
    "disabled": frozenset({RULE_CAP, RULE_FLOOR}),
}

AUDIT_CSV = "irrigation_farmer_governance_audit.csv"
# Decisions with no decision: ABORTED (nothing parsed) and the runner's
# ABORTED_EXCEPTION sentinel (ExperimentRunner._write_aborted_trace: the agent
# step raised, so no prompt or supply state was logged). Both stay in N.
EXCEPTION_STATUS = "ABORTED_EXCEPTION"
ABORTED_STATUSES = ("ABORTED", EXCEPTION_STATUS)
SIM_LOG = "simulation_log.csv"
TRACES = Path("raw") / "irrigation_farmer_traces.jsonl"
MANIFEST = "reproducibility_manifest.json"
REPLAY_CONDITION_CSV = "supply_rule_condition.csv"
UNOBSERVED = "unobserved"
REPLAY_RUNNER = "v3_metrics_replay"
FQL_RUNNER = "run_fql_baseline"
CONFIG_PATH = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "agent_types.yaml"
SKILL_REGISTRY_PATH = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "skill_registry.yaml"
AGENT_TYPE = "irrigation_farmer"
PROMPT_TEMPLATE_PATH = REPO_ROOT / "examples" / "irrigation_abm" / "config" / "prompts" / "irrigation_farmer.txt"
REF_PARAMS_CSV = REPO_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
REF_CRSS_DB = REPO_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
REF_PRECIP_CSV = REF_CRSS_DB / "HistoricalData" / "PrismWinterPrecip_ST_NOAA_Future.csv"

# A reservoir sits at its dead pool when its storage is within this of the
# dead pool: the tolerance of the prompt's own dead-pool sentence
# (irrigation_personas.build_water_situation_text).
DEAD_POOL_TOL_MAF = 1e-6
AF_TOL = 1e-6           # acre-ft, for equalities between two logged volumes
MAF_TOL = 1e-9          # MAF, for equalities between two logged flows
FT_TOL = 1e-6           # ft, for the Mead elevation cross-check
KGE_MIN_YEARS = 3       # Pearson r of two points is always +1 or -1
# Item 21: replay B holds every agent at 0.99 of its water right.
REPLAY_B_RIGHT_SHARE = 0.99
# Hung and Yang (2021, p. 15): "both reservoirs are depleted in 2034" (P3 context).
HY2021_DEPLETION_YEAR = 2034
# The 1 January 2018 Lake Mead level the 2019 Lower Basin trend flag compares
# with (IrrigationEnvironment.__init__, ``_mead_history``); pinned by a test.
MEAD_JAN1_2018_FT = 1082.52

# Pilot gate thresholds, as pre-registered in spec section 4 (with the
# orchestrator updates of 2026-09-29). Never tuned here.
P1_TOL_MAF = 1e-9
P4_UB_2019_MAF = (2.6, 3.6)
P4_LB_2019_MAF = (2.4, 3.0)
P5_BANNED_PHRASES = (  # spec WP4, test_banned_phrases_absent
    "conservation practices", "financial", "technolog", "records", "other water users",
    "operational flexibility", "Drought index", "TREND", "[Rule:", "Bureau of Reclamation",
    "Year 1:", "minimum release", "shared by all Lower Basin users",
)
P5C_MIN_PROMPTS = 20
P5C_YEARS = (2019, 2028, 2034, 2048, 2060)
P7_STRICT_GOV_RETRY_MAX = 0.50
P7_DISABLED_GOV_RETRY_MAX = 0.005
P7_PARSE_RETRY_MAX = 0.05
P8_UNREADABLE_MAX = 0.005
P10_MEAD_MIN_FT = (895.0, 1082.0)
P10_TIER3_YEARS = (0, 42)
# Item 36f/36g (2026-10-05 design-basis audit + fix proposals, spec item
# 36): these are the sums of IrrigationAgentProfile.water_right over the
# 56 Upper Basin / 22 Lower Basin agents, which moved from 4.932/4.177 MAF
# when the water-right formula became basin-specific (UB: 1.4 x peak
# only, no grid-top term; LB: grid top alone, no margin). Actual sums at
# the default paper_water_margin (0.4): UB 4.95026 MAF, LB 4.26635 MAF;
# rounded up slightly here since these are upper BOUNDS, not pins.
P10_UB_RIGHTS_MAF = 4.951
P10_LB_RIGHTS_MAF = 4.267
# P8 and P10: each CSV of a pilot run holds 3,276 rows (78 agents x 42 years),
# counted on the files, never taken from the run's own configured grid.
FULL_CORPUS_ROWS = 78 * 42
# Spec section 4: the pilot pair is strict seed 42 and disabled seed 42.
PILOT_SEED = 42
# Spec 7.2: values every manifest must show (``appraisal_freeze`` is checked
# on the LLM runs, which record it as ``appraisal_freeze_resolved``).
SPEC_72_VALUES = {"paper_water_margin": 0.4, "cluster_method": "hy2021", "ub_supply_mode": "subbasin"}


# =============================================================================
# Errors and cell parsing
# =============================================================================

class MetricsError(RuntimeError):
    """A missing file or column, a blank or malformed cell, or two artifacts of
    one run that disagree. Raised, never papered over."""


class ProvenanceError(MetricsError):
    """Runs whose manifests differ in code commit, water-system configuration,
    model or seed scheme, pooled without ``allow_mixed_provenance``."""


def _cell(row: Mapping[str, Optional[str]], column: str, where: str) -> str:
    if column not in row:
        raise MetricsError(f"{where}: column {column!r} is missing")
    value = row[column]
    if value is None:
        raise MetricsError(f"{where}: column {column!r} has no value (short CSV row)")
    return value


def _num(row: Mapping[str, Optional[str]], column: str, where: str) -> float:
    text = _cell(row, column, where).strip()
    if text == "" or text.lower() in ("nan", "none", UNOBSERVED):
        raise MetricsError(f"{where}: {column} is {text!r} where a number is required")
    try:
        value = float(text)
    except ValueError as exc:
        raise MetricsError(f"{where}: {column}={text!r} is not a number") from exc
    if not math.isfinite(value):
        raise MetricsError(f"{where}: {column}={text!r} is not finite")
    return value


def _opt_num(row: Mapping[str, Optional[str]], column: str, where: str) -> Optional[float]:
    if _cell(row, column, where).strip() == "":
        return None
    return _num(row, column, where)


def _int_cell(row: Mapping[str, Optional[str]], column: str, where: str) -> int:
    value = _num(row, column, where)
    if value != int(value):
        raise MetricsError(f"{where}: {column}={value!r} is not a whole number")
    return int(value)


def _bool_cell(row: Mapping[str, Optional[str]], column: str, where: str) -> bool:
    text = _cell(row, column, where).strip()
    if text == "True":
        return True
    if text == "False":
        return False
    raise MetricsError(f"{where}: {column}={text!r} is not True or False")


def _read_csv(path: Path, required: Sequence[str]) -> List[Dict[str, str]]:
    if not path.is_file():
        raise MetricsError(f"missing {path}")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        header = list(reader.fieldnames or [])
        missing = [c for c in required if c not in header]
        if missing:
            raise MetricsError(f"{path}: missing required columns {missing}")
        rows = list(reader)
    if not rows:
        raise MetricsError(f"{path}: no data rows")
    return rows


def _stated(value: Optional[str]) -> bool:
    return value is not None and str(value).strip() != ""


def level(value: Optional[str]) -> Optional[str]:
    """A construct label as the rules compare it: stripped and upper-cased;
    None when blank. The parser already writes the five codes; a value outside
    them is kept as written, matches neither TR1 nor TR3, and is counted."""
    if not _stated(value):
        return None
    return str(value).strip().upper()


def _git_head() -> Optional[str]:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT),
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip() or None
    except Exception:  # noqa: BLE001 - recorded as None in the output, never guessed
        return None


def analysis_config() -> WaterSystemConfig:
    """The water-system constants this module reads (dead pools, capacities,
    tier thresholds, start year, initial Mead level). The provenance guard
    checks every run's recorded configuration against it, so each constant
    used here is the run's own."""
    return WaterSystemConfig()


def assert_thinking_rules_match_config(config_path: Path = CONFIG_PATH) -> None:
    """The post hoc TR1/TR3 sets must be the live ones: read the strict
    profile's thinking rules and compare them with the item 9 definitions."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    rules = raw["irrigation_farmer"]["governance"]["strict"]["thinking_rules"]
    found = {}
    for rule in rules:
        conditions = rule.get("conditions") or []
        if len(conditions) != 1 or conditions[0].get("construct") != WSA_KEY:
            raise MetricsError(
                f"{config_path}: thinking rule {rule.get('id')!r} is not one WSA condition")
        found[rule["id"]] = (frozenset(conditions[0]["values"]), tuple(rule["blocked_skills"]))
    expected = {RULE_TR1: (TR1_WSA, (INCREASE,)), RULE_TR3: (TR3_WSA, (DECREASE,))}
    if found != expected:
        raise MetricsError(
            f"{config_path}: strict thinking rules {found} differ from the pre-registered "
            f"TR1/TR3 definitions {expected} (item 9)."
        )


def assert_short_year_window_matches_config(config_path: Path = CONFIG_PATH) -> None:
    """R5b's K window (item 33c, reviewer fix, 2026-10-01) must be the same
    one the dashboard shows: config/agent_types.yaml's
    irrigation_farmer.feedback.trend_window, never a copy of that number."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    window = raw["irrigation_farmer"]["feedback"]["trend_window"]
    if window != R5B_SHORT_YEAR_WINDOW:
        raise MetricsError(
            f"{config_path}: irrigation_farmer.feedback.trend_window={window!r} differs from "
            f"R5B_SHORT_YEAR_WINDOW={R5B_SHORT_YEAR_WINDOW!r} (item 33c, R5b's shown-years window)")


# =============================================================================
# Run identity and the provenance guard
# =============================================================================

_MISSING = object()


def _dig(manifest: Mapping[str, Any], path: Sequence[str]) -> Any:
    node: Any = manifest
    for key in path:
        if not isinstance(node, Mapping) or key not in node:
            return _MISSING
        node = node[key]
    return node


@dataclass(frozen=True)
class RunInfo:
    """One run directory: an LLM run, an FQL reference seed or a replay."""

    path: Path
    kind: str                  # "llm", "fql" or "replay"
    arm: str                   # LLM arm, "fql", or "replay_A" / "replay_B"
    seed: Optional[int]
    manifest: Dict[str, Any] = field(repr=False, compare=False)

    @property
    def label(self) -> str:
        return f"{self.arm}_seed{self.seed}" if self.seed is not None else self.arm


def llm_arm(manifest: Mapping[str, Any], where: str) -> str:
    """The arm of an LLM run, from its manifest (never from its directory
    name): the governance profile plus the retry feedback mode (spec 3.1)."""
    profile = manifest.get("governance_profile")
    resolved = manifest.get("governance_profile_resolved", profile)
    if profile is None or resolved != profile:
        raise MetricsError(f"{where}: governance_profile {profile!r} / resolved {resolved!r}")
    mode = manifest.get("retry_feedback_mode")
    if mode is None:
        raise MetricsError(f"{where}: manifest has no retry_feedback_mode")
    if profile == "strict" and mode in ("full", "placebo", "silent"):
        return {"full": "strict", "placebo": "placebo", "silent": "silent"}[mode]
    if profile in ("feasibility_only", "disabled") and mode == "full":
        return profile
    raise MetricsError(f"{where}: profile {profile!r} with retry_feedback_mode {mode!r} is no v3 arm")


def read_run_info(path: Path) -> RunInfo:
    path = Path(path)
    manifest_path = path / MANIFEST
    if not manifest_path.is_file():
        raise MetricsError(f"{path}: no {MANIFEST}; refusing a run without provenance")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    runner = manifest.get("runner")
    if runner == FQL_RUNNER:
        return RunInfo(path, "fql", "fql", int(manifest["seed"]), manifest)
    if runner == REPLAY_RUNNER:
        kind = manifest.get("replay_kind")
        if kind not in ("A", "B"):
            raise MetricsError(f"{path}: replay_kind {kind!r} is not A or B")
        return RunInfo(path, "replay", f"replay_{kind}", int(manifest["seed"]), manifest)
    if "governance_profile" in manifest and "model" in manifest:
        if "seed" not in manifest:
            raise MetricsError(f"{path}: LLM manifest has no seed")
        return RunInfo(path, "llm", llm_arm(manifest, str(path)), int(manifest["seed"]), manifest)
    raise MetricsError(f"{path}: manifest is neither an LLM run, an FQL run nor a replay")


def expand_run_dirs(paths: Sequence[str]) -> List[Path]:
    """A run directory holds a manifest; otherwise its immediate
    subdirectories that hold one are taken, in name order."""
    out: List[Path] = []
    for raw in paths:
        p = Path(raw)
        if (p / MANIFEST).is_file():
            out.append(p)
            continue
        if not p.is_dir():
            raise MetricsError(f"{p}: no such run directory")
        children = sorted(c for c in p.iterdir() if c.is_dir() and (c / MANIFEST).is_file())
        if not children:
            raise MetricsError(f"{p}: neither a run directory nor a parent of run directories")
        out.extend(children)
    return out


# Water-system keys each runner records, as paths into its manifest.
# run_experiment.py records the config fields and the two sub-basin table
# checksums at top level (_record_water_system_config_provenance; spec 7.2)
# and the other data checksums inside coupling_retrofit_metadata;
# run_fql_baseline.py and the replays record pinned_v3_data_checksums and the
# full water_system_config. Every key is required: a manifest without one
# cannot be verified and is refused.
_LLM_WATER_KEYS: Dict[str, Tuple[str, ...]] = {
    "hold_requests_fixed": ("hold_requests_fixed",),
    "powell_release_mode": ("powell_release_mode",),
    "powell_post2026_equalization": ("powell_post2026_equalization",),
    "lb_non_ag_total_maf": ("lb_non_ag_total_maf",),
    # Item 36e (2026-10-05); Opus review P2-2: 0.0 by default (every
    # existing run); a non-zero CPU-sensitivity run is refused when
    # pooled with the default reference, through the same "differs from
    # this analysis" check every other water-system key already uses.
    "lb_return_flow_fraction": ("lb_return_flow_fraction",),
    # 2026-10-06 CPU rerun finding: same treatment as lb_return_flow_fraction
    # just above -- 0.10 by default (every existing run); a 0 or 0.05 x W
    # CPU-sensitivity run is refused when pooled with the default
    # reference, so an LLM run and an FQL run under a different
    # --min-utilisation-fraction can never be silently mixed.
    "min_utilisation_fraction": ("min_utilisation_fraction",),
    "paper_water_margin": ("paper_water_margin",),
    "lb_tributary_source": ("coupling_retrofit_metadata", "water_system_lb_tributary_source"),
    "lb_priority_mode": ("coupling_retrofit_metadata", "water_system_lb_priority_mode"),
    "ub_supply_mode": ("ub_supply_mode",),
    "ub_subbasin_supply_variant": ("ub_subbasin_supply_variant",),
    "hydrology_v3_sha256": ("coupling_retrofit_metadata", "water_system_hydrology_v3_sha256"),
    "mead_capacity_sha256": ("coupling_retrofit_metadata", "water_system_mead_capacity_sha256"),
    "lb_priority_split_sha256": ("coupling_retrofit_metadata", "water_system_lb_priority_split_sha256"),
    "ub_subbasin_supply_sha256": ("ub_subbasin_supply_v3_sha256",),
    "ub_subbasin_envelope_sha256": ("ub_subbasin_envelope_v3_sha256",),
    "ub_subbasin_variant_means_sha256": ("ub_subbasin_variant_means_v3_sha256",),
}
_FQL_WATER_KEYS: Dict[str, Tuple[str, ...]] = {
    "hold_requests_fixed": ("hold_requests_fixed",),
    "powell_release_mode": ("powell_release_mode",),
    "powell_post2026_equalization": ("powell_post2026_equalization",),
    "lb_non_ag_total_maf": ("lb_non_ag_total_maf",),
    "lb_return_flow_fraction": ("water_system_config", "lb_return_flow_fraction"),
    "min_utilisation_fraction": ("water_system_config", "min_utilisation_fraction"),
    "paper_water_margin": ("paper_water_margin",),
    "lb_tributary_source": ("water_system_config", "lb_tributary_source"),
    "lb_priority_mode": ("lb_priority_mode",),
    "ub_supply_mode": ("ub_supply_mode",),
    "ub_subbasin_supply_variant": ("ub_subbasin_supply_variant",),
    "hydrology_v3_sha256": ("pinned_v3_data_checksums", "hydrology_v3_csv"),
    "mead_capacity_sha256": ("pinned_v3_data_checksums", "mead_capacity_usbr2009_1ft_csv"),
    "lb_priority_split_sha256": ("pinned_v3_data_checksums", "lb_priority_split_v3_csv"),
    "ub_subbasin_supply_sha256": ("pinned_v3_data_checksums", "ub_subbasin_supply_v3_csv"),
    "ub_subbasin_envelope_sha256": ("pinned_v3_data_checksums", "ub_subbasin_envelope_v3_csv"),
    "ub_subbasin_variant_means_sha256": ("pinned_v3_data_checksums", "ub_subbasin_variant_means_v3_csv"),
}


def water_system_signature(info: RunInfo) -> Dict[str, Any]:
    """The water-system keys this run's runner records (see the two maps)."""
    mapping = _LLM_WATER_KEYS if info.kind == "llm" else _FQL_WATER_KEYS
    signature: Dict[str, Any] = {}
    for key, path in mapping.items():
        value = _dig(info.manifest, path)
        if value is _MISSING:
            raise MetricsError(
                f"{info.path}: manifest has no {'.'.join(path)}; cannot verify its water system")
        signature[key] = value
    return signature


def _analysis_water_expectations() -> Dict[str, Any]:
    cfg = analysis_config()
    variant = cfg.ub_subbasin_supply_variant
    return {
        "powell_release_mode": cfg.powell_release_mode,
        "powell_post2026_equalization": cfg.powell_post2026_equalization,
        "lb_non_ag_total_maf": cfg.lb_non_ag_total_maf,
        "lb_return_flow_fraction": cfg.lb_return_flow_fraction,
        "min_utilisation_fraction": cfg.min_utilisation_fraction,
        "lb_tributary_source": cfg.lb_tributary_source,
        "lb_priority_mode": cfg.lb_priority_mode,
        "ub_supply_mode": cfg.ub_supply_mode,
        "ub_subbasin_supply_variant": variant,
        "hydrology_v3_sha256": HYDROLOGY_V3_SHA256,
        "mead_capacity_sha256": MEAD_CAPACITY_SHA256,
        "lb_priority_split_sha256": LB_PRIORITY_SPLIT_SHA256,
        "ub_subbasin_supply_sha256": _UB_SUBBASIN_SUPPLY_VARIANT_FILES[variant][1],
        "ub_subbasin_envelope_sha256": UB_SUBBASIN_ENVELOPE_SHA256,
        "ub_subbasin_variant_means_sha256": UB_SUBBASIN_VARIANT_MEANS_SHA256,
    }


def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _dirty_reasons(info: RunInfo, commit: Any) -> List[str]:
    """Why a run's commit may not identify its code: the tree was dirty at
    launch or at finalize, or HEAD moved during the run (spec 7.2:
    ``git_dirty: false``). Keys a runner does not write are not read."""
    reasons = []
    if info.manifest.get("git_dirty") is not False:
        reasons.append(f"git_dirty={info.manifest.get('git_dirty')!r}")
    at_finalize = info.manifest.get("git_dirty_at_finalize", _MISSING)
    if at_finalize is not _MISSING and at_finalize is not False:
        reasons.append(f"git_dirty_at_finalize={at_finalize!r}")
    final_commit = info.manifest.get("git_commit_at_finalize", _MISSING)
    if final_commit is not _MISSING and final_commit != commit:
        reasons.append(f"git_commit_at_finalize {final_commit!r} is not git_commit {commit!r}")
    return reasons


def check_provenance(infos: Sequence[RunInfo], allow_mixed: bool = False,
                     allow_dirty: bool = False) -> Dict[str, Any]:
    """Refuse to pool runs whose manifests differ in code commit,
    water-system configuration, model or seed scheme (spec WP6 item 9).

    Also refused: a run from a dirty tree (``_dirty_reasons``) unless
    ``allow_dirty``; a manifest breaking a spec 7.2 value (``SPEC_72_VALUES``,
    and ``appraisal_freeze`` true in every LLM run) or without
    ``step_bin_source``; an aborted run, an LLM or FQL run with
    ``hold_requests_fixed`` true, a replay without it, an FQL reference that
    is not raw FQL (``no_governance``), FQL seeds with different warm starts,
    duplicate seeds within an arm, and runs whose recorded water system differs
    from the constants this module reads. With ``allow_mixed`` every such
    difference, dirty runs included, is kept in the returned record (written
    to provenance.json and the markdown) instead of raising; ``allow_dirty``
    overrides the dirty-tree refusal only, and is recorded the same way."""
    problems: List[str] = []
    warnings: List[str] = []
    dirty_runs: List[str] = []
    record: Dict[str, Any] = {
        "analysis_git_head": _git_head(),
        "allow_mixed_provenance": bool(allow_mixed),
        "allow_dirty": bool(allow_dirty),
        "runs": [],
    }
    commits: Dict[str, List[str]] = defaultdict(list)
    for info in infos:
        commit = info.manifest.get("git_commit") if info.kind == "llm" else info.manifest.get("git_head")
        dirty = info.manifest.get("git_dirty")
        record["runs"].append({"label": info.label, "kind": info.kind, "path": str(info.path),
                               "code_commit": commit, "git_dirty": dirty})
        if not commit or commit == "unavailable":
            problems.append(f"{info.label}: no code commit recorded")
        commits[str(commit)].append(info.label)
        reasons = _dirty_reasons(info, commit)
        if reasons:
            dirty_runs.append(f"{info.label}: {'; '.join(reasons)}; the commit does not identify its code")
        # Any aborted run_status refuses pooling, not only the LLM
        # safeguard's own "aborted_llm_failure_rate": ExperimentRunner also
        # records "aborted_journal_divergence" / "aborted_journal_write_error"
        # (broker/core/experiment_runner.py (ExperimentRunner.run)) for the
        # crash-resume journal's own abort path, and the docs (`v3_metrics.md`
        # section 10) already describe the refusal generically as "an
        # aborted run" -- matched by prefix, not a fixed set of known values,
        # so a future abort reason needs no update here to already be refused.
        _run_status = info.manifest.get("run_status")
        if isinstance(_run_status, str) and _run_status.startswith("aborted"):
            problems.append(f"{info.label}: run aborted (run_status={_run_status!r})")
        # Spec 7.2 values, on every manifest.
        for key, expected in SPEC_72_VALUES.items():
            value = info.manifest.get(key, _MISSING)
            if value is _MISSING:
                problems.append(f"{info.label}: manifest has no {key} (spec 7.2)")
            elif value != expected:
                problems.append(f"{info.label}: {key} = {value!r}; spec 7.2 requires {expected!r}")
        if "step_bin_source" not in info.manifest:
            problems.append(f"{info.label}: manifest has no step_bin_source (spec 7.2)")
        if info.kind == "llm" and info.manifest.get("appraisal_freeze_resolved") is not True:
            problems.append(f"{info.label}: appraisal_freeze_resolved = "
                            f"{info.manifest.get('appraisal_freeze_resolved')!r}; spec 7.2 requires "
                            "appraisal_freeze true")
    record["dirty_runs"] = dirty_runs
    record["dirty_override_applied"] = bool(dirty_runs) and bool(allow_dirty)
    if dirty_runs and not allow_dirty:
        problems.extend(dirty_runs)
    if len(commits) > 1:
        problems.append(f"code commit differs: {dict(commits)}")
    record["code_commits"] = dict(commits)
    if record["analysis_git_head"] and len(commits) == 1:
        (only,) = commits
        if only != record["analysis_git_head"]:
            warnings.append(
                f"the runs were made at {only} and this analysis runs at "
                f"{record['analysis_git_head']}")

    llm = [i for i in infos if i.kind == "llm"]
    fql = [i for i in infos if i.kind == "fql"]
    replays = [i for i in infos if i.kind == "replay"]

    # Model: one model across the LLM runs.
    models = sorted({str(i.manifest.get("model")) for i in llm})
    record["model"] = models
    if len(models) > 1:
        problems.append(f"model differs across LLM runs: {models}")

    # Worker count (broker/core/experiment_runner.py (ExperimentConfig.workers),
    # recorded by broker/core/experiment_runner.py
    # (ExperimentRunner._collect_reproducibility_metadata); F14/F41
    # parallel-determinism review, F43 crash-resume journal review). A
    # missing key is NOT defaulted to the dataclass's own workers=1: this
    # guard has no "a missing key equals its historical default" precedent
    # for any other late-added field. The one place a late key IS allowed
    # to be silently absent (git_dirty_at_finalize / git_commit_at_finalize
    # in _dirty_reasons above) SKIPS that one check entirely rather than
    # assuming a value, and those are secondary cross-checks, not fields
    # this guard pools runs on -- cluster_method and step_bin_source just
    # below are the actual precedent for an identifying field, and they too
    # read a missing key as the plain `.get()` default (None) with no
    # override, so a run that never recorded it differs from one that did.
    # A pool where every run alike lacks `workers` reads as one shared None
    # (no problem); a pool mixing an explicit value with an absent key is
    # exactly the ambiguity this guard exists to catch -- workers>1 is
    # proven to produce the same outputs as workers=1 (broker/core/
    # experiment_runner.py (ExperimentRunner._run_agents_parallel)'s
    # submission-order sort), but "this manifest does not say" is not the
    # same claim as "this run used 1 worker."
    #
    # Also checked here, paired with each run's own `workers`: its
    # `source_workers` (broker/utils/llm_journal.py
    # (LLMJournalManager.provenance_metadata), present only on a resumed
    # run) -- the worker count the REPLAYED portion of THIS run's output
    # actually came from, which can differ from the run's own `workers` by
    # design (resuming at a different worker count is supported). A run
    # that crashed under workers=4 and was resumed at workers=1 therefore
    # carries `workers=1, source_workers=4`: this run ITSELF touched two
    # distinct worker counts and is refused below regardless of what else
    # is in the pool.
    #
    # Opus review of WP7 launcher, item 4(b) (bug fix): the previous
    # implementation compared the raw ``(workers, source_workers)`` tuple
    # across runs, e.g. a fresh run's ``(4, None)`` against a same-workers
    # RESUMED run's ``(4, 4)`` -- two different tuples, so every resumed
    # run was refused as "mixed" even when every run in the pool, resumed
    # or not, was consistently at workers=4. The correct rule: per run, the
    # set of distinct values among {workers} and source_workers (when
    # present) must itself be a singleton (a run whose own history touched
    # two different worker counts is refused on its own, independent of
    # the rest of the pool); only once every run clears that does the
    # single value from each run get compared ACROSS the pool.
    per_run_workers: Dict[str, Any] = {}
    for i in llm:
        source_workers = i.manifest.get("source_workers")
        values = {i.manifest.get("workers")}
        if source_workers is not None:
            values.add(source_workers)
        if len(values) > 1:
            problems.append(
                f"{i.label}: workers={i.manifest.get('workers')!r} but "
                f"source_workers={source_workers!r} -- this run itself mixed "
                f"worker counts across a crash and its resume"
            )
            continue
        per_run_workers[i.label] = next(iter(values))
    distinct_workers = {json.dumps(_jsonable(v)) for v in per_run_workers.values()}
    if len(distinct_workers) > 1:
        problems.append(
            f"workers differs across LLM runs: "
            f"{dict(sorted(per_run_workers.items()))}"
        )

    # Seed scheme.
    by_arm: Dict[str, List[int]] = defaultdict(list)
    for i in llm + fql + replays:
        by_arm[i.arm].append(i.seed)
    for arm, seeds in by_arm.items():
        if len(seeds) != len(set(seeds)):
            problems.append(f"{arm}: duplicate seeds {sorted(seeds)}")
    memory_seeds = [i.manifest.get("memory_seed") for i in llm]
    if any(m is None for m in memory_seeds):
        problems.append("an LLM manifest has no memory_seed")
        scheme = "unknown"
    elif len(set(memory_seeds)) <= 1:
        scheme = f"memory_seed fixed at {memory_seeds[0]}" if memory_seeds else "no LLM runs"
    elif all(i.manifest.get("memory_seed") == i.seed for i in llm):
        scheme = "memory_seed equals seed"
    else:
        scheme = "mixed"
        problems.append(
            "seed scheme differs: memory_seed is neither one value nor equal to seed in "
            f"every LLM run ({[(i.label, i.manifest.get('memory_seed')) for i in llm]})")
    record["seed_scheme"] = scheme

    # Runner-specific design flags.
    for i in llm + fql:
        if i.manifest.get("hold_requests_fixed") is not False:
            problems.append(f"{i.label}: hold_requests_fixed={i.manifest.get('hold_requests_fixed')!r} "
                            "(only replays hold requests fixed, item 21)")
    for i in replays:
        if i.manifest.get("hold_requests_fixed") is not True:
            problems.append(f"{i.label}: a replay must hold requests fixed (item 21)")
    if sorted(i.arm for i in replays) not in ([], ["replay_A", "replay_B"]):
        problems.append(f"replays must be one A and one B, got {sorted(i.arm for i in replays)}")
    for i in fql:
        if i.manifest.get("no_governance") is not True:
            problems.append(f"{i.label}: the FQL reference must be raw FQL (no_governance true)")
    for key in ("fql_init", "fql_init_dir"):
        values = sorted({json.dumps(i.manifest.get(key)) for i in fql})
        if len(values) > 1:
            problems.append(f"FQL seeds differ in {key}: {values}")
    for key in ("cluster_method", "step_bin_source"):
        values = {json.dumps(_jsonable(i.manifest.get(key)), sort_keys=True) for i in infos}
        if len(values) > 1:
            problems.append(f"{key} differs across runs")

    # Water system: every recorded key equal across all runs (replays aside
    # for hold_requests_fixed, checked above), and equal to the analysis
    # constants.
    expectations = _analysis_water_expectations()
    values: Dict[str, Dict[str, List[str]]] = defaultdict(lambda: defaultdict(list))
    not_recorded: Dict[str, List[str]] = defaultdict(list)
    all_keys = list(_FQL_WATER_KEYS)
    for info in infos:
        signature = water_system_signature(info)
        for key in all_keys:
            if key == "hold_requests_fixed":
                continue
            if key not in signature:
                not_recorded[key].append(info.label)
                continue
            values[key][json.dumps(_jsonable(signature[key]))].append(info.label)
    water: Dict[str, Any] = {}
    for key in all_keys:
        if key == "hold_requests_fixed":
            continue
        seen = values.get(key, {})
        water[key] = {"values": {k: v for k, v in seen.items()},
                      "not_recorded_by": not_recorded.get(key, [])}
        if len(seen) > 1:
            problems.append(f"water system differs in {key}: {dict(seen)}")
        if key in expectations and seen:
            expected = json.dumps(_jsonable(expectations[key]))
            if set(seen) != {expected}:
                problems.append(f"{key}: runs recorded {sorted(seen)}, this analysis reads {expected}")
    record["water_system"] = water
    # The full config of the FQL runs and replays against the analysis one.
    reference = _jsonable(dataclasses.asdict(analysis_config()))
    for key in ("seed", "hold_requests_fixed"):
        reference.pop(key, None)
    for info in fql + replays:
        recorded = _jsonable(info.manifest.get("water_system_config"))
        if not isinstance(recorded, dict):
            problems.append(f"{info.label}: no water_system_config in the manifest")
            continue
        recorded = {k: v for k, v in recorded.items() if k not in ("seed", "hold_requests_fixed")}
        if recorded != reference:
            diff = sorted(k for k in set(recorded) | set(reference) if recorded.get(k) != reference.get(k))
            problems.append(f"{info.label}: water_system_config differs from this analysis in {diff}")

    record["warnings"] = warnings
    record["differences"] = problems
    record["override_applied"] = bool(problems) and bool(allow_mixed)
    if problems and not allow_mixed:
        raise ProvenanceError(
            "refusing to pool runs with different or incomplete provenance (pass "
            "allow_dirty for runs from a dirty tree, or allow_mixed_provenance, to override "
            "and record it):\n  " + "\n  ".join(problems))
    return record


# =============================================================================
# Simulation log
# =============================================================================

SYSTEM_FLOAT_COLUMNS = (
    "lake_mead_level", "mead_storage_maf", "mead_storage_end_maf", "powell_storage_maf",
    "powell_storage_end_maf", "natural_flow_maf", "ub_non_farm_maf", "lb_tributary_maf",
    "ub_delivered_maf", "powell_evap_maf", "mead_evap_maf", "powell_spill_maf",
    "mead_spill_maf", "lb_delivered_maf", "lb_non_ag_delivered_maf", "mexico_delivered_maf",
    "lb_shortage_volume_maf",
)
SYSTEM_INT_COLUMNS = ("shortage_tier", "calendar_year")
# Item 36e (lb_return_flow_fraction, 2026-10-05) columns: logged by every
# run at or after that commit (irrigation_env.py's settlement result
# always carries them, build_simulation_log_row always writes them), but
# NOT in SYSTEM_FLOAT_COLUMNS/SIM_REQUIRED -- kept optional, defaulting to
# 0.0 when a row's CSV predates the column, so loading an OLDER run never
# breaks. 0.0 for either factor is also exactly the value that makes
# gate_p1's lb_phys_ratio * lb_return_flow_maf correction (below) a no-op,
# matching the pre-item-36e residual formula bit for bit.
SYSTEM_OPTIONAL_FLOAT_COLUMNS = ("lb_phys_ratio", "lb_return_flow_maf")
AGENT_COLUMNS = (
    "agent_id", "year", "basin", "cluster", "request", "diversion", "water_right", "base_af",
    "ub_subbasin", "ub_subbasin_ratio", "precipitation_mm", "precipitation_flag",
    "typical_step_af", "magnitude_pct", "lb_junior_tier_cut_fraction",
)
SIM_REQUIRED = AGENT_COLUMNS + SYSTEM_FLOAT_COLUMNS + SYSTEM_INT_COLUMNS


@dataclass
class SimLog:
    """``simulation_log.csv`` of one run: per agent-year rows and the per-year
    water-system values every row of a year carries."""

    path: Path
    rows: Dict[Tuple[str, int], Dict[str, str]]
    agents: Tuple[str, ...]
    years: Tuple[int, ...]           # loop years 1..n
    basin: Dict[str, str]
    cluster: Dict[str, str]
    subbasin: Dict[str, Optional[str]]
    system: Dict[int, Dict[str, float]]
    sim_start_year: int

    def sim_year(self, year: int) -> int:
        return self.sim_start_year + year - 1

    def num(self, agent: str, year: int, column: str) -> float:
        return _num(self.rows[(agent, year)], column, f"{self.path} [{agent}, year {year}]")

    def opt_num(self, agent: str, year: int, column: str) -> Optional[float]:
        return _opt_num(self.rows[(agent, year)], column, f"{self.path} [{agent}, year {year}]")


def load_sim_log(run_dir: Path) -> SimLog:
    path = Path(run_dir) / SIM_LOG
    raw = _read_csv(path, SIM_REQUIRED)
    cfg = analysis_config()
    hydrology = _load_hydrology_table()
    rows: Dict[Tuple[str, int], Dict[str, str]] = {}
    basin: Dict[str, str] = {}
    cluster: Dict[str, str] = {}
    subbasin: Dict[str, Optional[str]] = {}
    for n, row in enumerate(raw, start=2):
        where = f"{path}:{n}"
        agent = _cell(row, "agent_id", where)
        year = _int_cell(row, "year", where)
        if (agent, year) in rows:
            raise MetricsError(f"{where}: duplicate row for {agent}, year {year}")
        rows[(agent, year)] = row
        b = _cell(row, "basin", where)
        if b not in ("upper_basin", "lower_basin"):
            raise MetricsError(f"{where}: basin {b!r}")
        sb = _cell(row, "ub_subbasin", where).strip() or None
        for store, value, name in ((basin, b, "basin"), (cluster, _cell(row, "cluster", where), "cluster"),
                                   (subbasin, sb, "ub_subbasin")):
            if agent in store and store[agent] != value:
                raise MetricsError(f"{where}: {name} of {agent} changes from {store[agent]!r} to {value!r}")
            store[agent] = value
        if b == "lower_basin" and sb is not None:
            raise MetricsError(f"{where}: Lower Basin agent with ub_subbasin {sb!r}")
    agents = tuple(sorted(basin))
    years = tuple(sorted({y for _, y in rows}))
    if years != tuple(range(1, len(years) + 1)):
        raise MetricsError(f"{path}: loop years {years} are not 1..n")
    missing = [(a, y) for a in agents for y in years if (a, y) not in rows]
    if missing:
        raise MetricsError(f"{path}: {len(missing)} agent-years missing, e.g. {missing[:3]}")
    system: Dict[int, Dict[str, float]] = {}
    for y in years:
        values: Optional[Dict[str, float]] = None
        for a in agents:
            where = f"{path} [{a}, year {y}]"
            row = rows[(a, y)]
            current = {c: _num(row, c, where) for c in SYSTEM_FLOAT_COLUMNS}
            current.update({c: float(_int_cell(row, c, where)) for c in SYSTEM_INT_COLUMNS})
            current.update({c: (_num(row, c, where) if c in row else 0.0) for c in SYSTEM_OPTIONAL_FLOAT_COLUMNS})
            if values is None:
                values = current
            elif current != values:
                diff = sorted(k for k in current if current[k] != values[k])
                raise MetricsError(f"{where}: per-year water-system values differ between agents in {diff}")
        sim_year = cfg.sim_start_year + y - 1
        if sim_year not in hydrology:
            raise MetricsError(f"{path}: year {y} maps to {sim_year}, outside the hydrology table")
        if int(values["calendar_year"]) != hydrology[sim_year]["source_calendar_year"]:
            raise MetricsError(
                f"{path}: year {y} logs source calendar year {int(values['calendar_year'])}, "
                f"the hydrology table maps {sim_year} to {hydrology[sim_year]['source_calendar_year']}")
        system[y] = values
    return SimLog(path, rows, agents, years, basin, cluster, subbasin, system, cfg.sim_start_year)


# =============================================================================
# Audit rows: one decision each
# =============================================================================

AUDIT_REQUIRED = (
    "agent_id", "year", "status", "execution_path", "executed_skill", "proposed_skill",
    "final_skill", "retry_count", "format_retries", "llm_success", "initial_skill",
    "initial_labels", "final_labels", "attempt_skills", "attempt_labels",
    "attempt_failed_rules", "appraisal_relabeled", "error_messages", "timestamp",
) + tuple(f"state_{k}" for k in SUPPLY_RULE_FIELDS)


@dataclass(frozen=True)
class Attempt:
    """One parsed or unparsable attempt of a decision (``attempt_*`` columns)."""

    skill: Optional[str]                   # None: the attempt did not parse
    labels: Optional[Dict[str, str]]       # None: the attempt did not parse
    failed_rules: Optional[Tuple[str, ...]]  # None: did not parse; (): passed

    @property
    def parsed(self) -> bool:
        return self.skill is not None


@dataclass(frozen=True)
class Decision:
    """One audit row: the agent's decision for one year, all its attempts."""

    agent_id: str
    year: int
    status: str
    execution_path: str
    executed_skill: Optional[str]
    proposed_skill: str
    attempts: Tuple[Attempt, ...]          # empty for an ABORTED row
    retry_count: int
    format_retries: int
    llm_success: Optional[bool]
    keep_request_af: Optional[float]       # None only on an ABORTED_EXCEPTION row
    expected_at_keep_af: Optional[float]
    supply_ratio: Optional[float]
    physical_ratio: Optional[float]
    first_wsa: Optional[str]
    first_aca: Optional[str]
    final_wsa: Optional[str]
    wsa_relabeled: bool
    error_messages: str
    timestamp: str
    crashed: bool = False                  # the ABORTED_EXCEPTION sentinel

    @property
    def aborted(self) -> bool:
        """No decision: ABORTED or ABORTED_EXCEPTION (``execution_path``
        aborted). In N, never a violation, no readable final proposal."""
        return self.execution_path == "aborted"

    @property
    def final_proposal(self) -> Optional[str]:
        """The skill of the last attempt; None when it did not parse (or no
        attempt parsed): a decision with no readable final proposal."""
        return self.attempts[-1].skill if self.attempts else None

    @property
    def first_proposal(self) -> Optional[str]:
        return self.attempts[0].skill if self.attempts else None

    @property
    def retried(self) -> bool:
        return self.retry_count > 0

    @property
    def parse_retried(self) -> bool:
        """P7's parse retry: the first-attempt loop asked again
        (``format_retries`` > 0), or a governance retry came back unparsable
        (an empty group in the ``attempt_*`` columns)."""
        return self.format_retries > 0 or any(not a.parsed for a in self.attempts)

    @property
    def supply_condition(self) -> Optional[bool]:
        """The supply rule's condition (spec 3.3): the expected delivery at the
        keep request, net of a declared junior-priority cut, is below
        FULL_SUPPLY_RATIO of it. None (unknown) on an ABORTED_EXCEPTION row,
        which logs no supply state."""
        if self.physical_ratio is None:
            return None
        return self.physical_ratio < FULL_SUPPLY_RATIO

    def condition(self, rule: str, at_cap: Optional[bool], at_floor: Optional[bool]) -> Optional[bool]:
        """Whether ``rule``'s condition held for this decision (None: unknown,
        an ABORTED row has no ``state_before`` for the cap and floor)."""
        if rule == RULE_SUPPLY:
            return self.supply_condition
        if rule == RULE_TR1:
            return self.first_wsa in TR1_WSA
        if rule == RULE_TR3:
            return self.first_wsa in TR3_WSA
        if rule == RULE_CAP:
            return at_cap
        if rule == RULE_FLOOR:
            return at_floor
        raise MetricsError(f"unknown rule {rule!r}")


def _parse_pairs(text: str, sep: str, where: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    if text == "":
        return out
    for part in text.split(sep):
        if "=" not in part:
            raise MetricsError(f"{where}: label item {part!r} has no '='")
        key, value = part.split("=", 1)
        if key in out:
            raise MetricsError(f"{where}: label {key!r} stated twice in one attempt")
        out[key] = value
    return out


def _first_stated(initial: Mapping[str, str], attempts: Sequence[Attempt], key: str) -> Optional[str]:
    """Item 28: the label from ``initial_labels`` when it is stated there,
    else the first NON-BLANK value in ``attempt_labels``, in attempt order."""
    if _stated(initial.get(key)):
        return level(initial[key])
    for attempt in attempts:
        if attempt.labels is not None and _stated(attempt.labels.get(key)):
            return level(attempt.labels[key])
    return None


def _wsa_relabeled(attempts: Sequence[Attempt]) -> bool:
    """WSA only (WP3 review): True when an attempt states a WSA other than
    the first stated one. A first statement or an omission is no relabel."""
    first: Optional[str] = None
    for attempt in attempts:
        if attempt.labels is None or not _stated(attempt.labels.get(WSA_KEY)):
            continue
        value = level(attempt.labels[WSA_KEY])
        if first is None:
            first = value
        elif value != first:
            return True
    return False


def parse_decision(row: Mapping[str, str], where: str) -> Decision:
    agent = _cell(row, "agent_id", where)
    year = _int_cell(row, "year", where)
    where = f"{where} [{agent}, year {year}]"
    status = _cell(row, "status", where)
    path = _cell(row, "execution_path", where)
    if (status in ABORTED_STATUSES) != (path == "aborted"):
        raise MetricsError(f"{where}: status {status!r} with execution_path {path!r}")
    crashed = status == EXCEPTION_STATUS
    retry_count = _int_cell(row, "retry_count", where)
    format_retries = _int_cell(row, "format_retries", where)
    success_text = _cell(row, "llm_success", where).strip()
    llm_success = None if success_text == "" else _bool_cell(row, "llm_success", where)
    executed = _cell(row, "executed_skill", where).strip() or None
    # The ABORTED_EXCEPTION sentinel logs no supply state (the step raised
    # before its context was written): its cells may be blank, nowhere else.
    read = _opt_num if crashed else _num
    state = {k: read(row, f"state_{k}", where) for k in SUPPLY_RULE_FIELDS}
    if state["full_supply_ratio"] is not None and state["full_supply_ratio"] != FULL_SUPPLY_RATIO:
        raise MetricsError(
            f"{where}: logged full_supply_ratio {state['full_supply_ratio']} differs from "
            f"FULL_SUPPLY_RATIO {FULL_SUPPLY_RATIO} of this analysis")
    initial: Dict[str, str] = {}
    if path == "aborted":
        # ABORTED writes "unobserved"; the exception sentinel leaves them blank.
        allowed = (UNOBSERVED, "") if crashed else (UNOBSERVED,)
        for column in ("attempt_labels", "attempt_failed_rules"):
            if _cell(row, column, where) not in allowed:
                raise MetricsError(f"{where}: {status} row with {column}={row[column]!r}")
        if executed is not None:
            raise MetricsError(f"{where}: ABORTED row executed {executed!r}")
        attempts: Tuple[Attempt, ...] = ()
    else:
        skills = _cell(row, "attempt_skills", where).split("|")
        labels = _cell(row, "attempt_labels", where).split("|")
        rules = _cell(row, "attempt_failed_rules", where).split("|")
        if not len(skills) == len(labels) == len(rules) == retry_count + 1:
            raise MetricsError(
                f"{where}: attempt columns hold {len(skills)}/{len(labels)}/{len(rules)} "
                f"attempts, retry_count is {retry_count}")
        parsed: List[Attempt] = []
        for k, (s, lab, rul) in enumerate(zip(skills, labels, rules)):
            if s == "":
                if lab != "" or rul != "":
                    raise MetricsError(f"{where}: unparsable attempt {k} carries labels or rules")
                parsed.append(Attempt(None, None, None))
            else:
                parsed.append(Attempt(s, _parse_pairs(lab, ",", f"{where} attempt {k}"),
                                      tuple(rul.split(",")) if rul else ()))
        attempts = tuple(parsed)
        if not attempts[0].parsed:
            raise MetricsError(f"{where}: first attempt did not parse on a non-ABORTED row")
        if _cell(row, "initial_skill", where) != attempts[0].skill:
            raise MetricsError(f"{where}: initial_skill {row['initial_skill']!r} is not attempt 0's skill")
        initial = _parse_pairs(_cell(row, "initial_labels", where), "|", f"{where} initial_labels")
        if initial != attempts[0].labels:
            raise MetricsError(f"{where}: initial_labels {initial} differ from attempt 0 {attempts[0].labels}")
        if executed is None:
            raise MetricsError(f"{where}: a non-ABORTED decision executed nothing")
        if path == "approved" and executed != attempts[-1].skill:
            raise MetricsError(f"{where}: approved row executed {executed!r}, final attempt {attempts[-1].skill!r}")
    final_labels = _parse_pairs(_cell(row, "final_labels", where), "|", f"{where} final_labels")
    if attempts and attempts[-1].parsed and final_labels != attempts[-1].labels:
        raise MetricsError(f"{where}: final_labels {final_labels} differ from the last attempt {attempts[-1].labels}")
    if attempts and not attempts[-1].parsed and final_labels:
        raise MetricsError(f"{where}: final_labels set although the last attempt did not parse")
    wsa_relabeled = _wsa_relabeled(attempts)
    if path != "aborted":
        relabeled_any = _bool_cell(row, "appraisal_relabeled", where)
        if wsa_relabeled and not relabeled_any:
            raise MetricsError(f"{where}: WSA relabelled but appraisal_relabeled is False")
    return Decision(
        agent_id=agent, year=year, status=status, execution_path=path,
        executed_skill=executed, proposed_skill=_cell(row, "proposed_skill", where),
        attempts=attempts, retry_count=retry_count, format_retries=format_retries,
        llm_success=llm_success,
        keep_request_af=state["supply_keep_request_af"],
        expected_at_keep_af=state["supply_expected_at_keep_af"],
        supply_ratio=state["supply_ratio"], physical_ratio=state["supply_physical_ratio"],
        first_wsa=_first_stated(initial, attempts, WSA_KEY),
        first_aca=_first_stated(initial, attempts, ACA_KEY),
        final_wsa=level(final_labels.get(WSA_KEY)),
        wsa_relabeled=wsa_relabeled,
        error_messages=_cell(row, "error_messages", where),
        timestamp=_cell(row, "timestamp", where),
        crashed=crashed,
    )


def load_decisions(run_dir: Path) -> Dict[Tuple[str, int], Decision]:
    path = Path(run_dir) / AUDIT_CSV
    rows = _read_csv(path, AUDIT_REQUIRED)
    out: Dict[Tuple[str, int], Decision] = {}
    for n, row in enumerate(rows, start=2):
        decision = parse_decision(row, f"{path}:{n}")
        key = (decision.agent_id, decision.year)
        if key in out:
            raise MetricsError(f"{path}:{n}: second decision for {key}")
        out[key] = decision
    return out


# =============================================================================
# Raw traces: the state before the decision and the first-attempt prompt
# =============================================================================

_RE_OPTION = re.compile(r"^(\d+)\. (Increase|Keep|Decrease) your request", re.M)


def parse_menu(prompt: str, where: str) -> Tuple[str, ...]:
    """The options a first-attempt prompt offers, in order ("increase",
    "keep", "decrease"), numbered 1..n."""
    found = [(int(m.group(1)), m.group(2).lower()) for m in _RE_OPTION.finditer(prompt)]
    if not found:
        raise MetricsError(f"{where}: no option menu in the first-attempt prompt")
    if [n for n, _ in found] != list(range(1, len(found) + 1)):
        raise MetricsError(f"{where}: menu numbering {[n for n, _ in found]}")
    kinds = tuple(k for _, k in found)
    if len(set(kinds)) != len(kinds):
        raise MetricsError(f"{where}: an option appears twice in the menu {kinds}")
    return kinds


@dataclass(frozen=True)
class TraceRecord:
    agent_id: str
    year: int
    at_cap: Optional[bool]          # None on an ABORTED sentinel (no state_before)
    at_floor: Optional[bool]
    base_af: Optional[float]
    water_right_af: Optional[float]
    menu: Tuple[str, ...]
    prompt: Optional[str] = field(default=None, repr=False)
    crashed: bool = False           # ABORTED_EXCEPTION sentinel: no prompt was logged


def load_traces(run_dir: Path, keep_prompts: bool = False) -> Dict[Tuple[str, int], TraceRecord]:
    path = Path(run_dir) / TRACES
    if not path.is_file():
        raise MetricsError(f"missing {path}")
    out: Dict[Tuple[str, int], TraceRecord] = {}
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, start=1):
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if "_metadata" in rec:
                continue
            where = f"{path}:{n}"
            agent, year = rec.get("agent_id"), rec.get("year")
            if agent is None or year is None:
                raise MetricsError(f"{where}: trace without agent_id or year")
            key = (str(agent), int(year))
            if key in out:
                raise MetricsError(f"{where}: second trace for {key}")
            prompt = rec.get("input")
            aborted = rec.get("execution_path") == "aborted"
            crashed = aborted and rec.get("status") == EXCEPTION_STATUS
            if not isinstance(prompt, str) or not prompt.strip():
                if not crashed:
                    raise MetricsError(f"{where}: trace without its first-attempt prompt (input)")
                prompt = None  # the step raised before its prompt was logged
            state = rec.get("state_before")
            if not state:
                if not aborted:
                    raise MetricsError(f"{where}: no state_before on a decision that was not aborted")
                at_cap = at_floor = None
                base = water_right = None
            else:
                for k in ("at_allocation_cap", "below_minimum_utilisation", "current_request", "water_right"):
                    if k not in state:
                        raise MetricsError(f"{where}: state_before has no {k}")
                at_cap = state["at_allocation_cap"]
                at_floor = state["below_minimum_utilisation"]
                if not isinstance(at_cap, bool) or not isinstance(at_floor, bool):
                    raise MetricsError(f"{where}: cap or floor flag is not a bool")
                base = float(state["current_request"])
                water_right = float(state["water_right"])
            out[key] = TraceRecord(key[0], key[1], at_cap, at_floor, base, water_right,
                                   () if prompt is None else parse_menu(prompt, where),
                                   prompt if keep_prompts else None, crashed=crashed)
    if not out:
        raise MetricsError(f"{path}: no traces")
    return out


# =============================================================================
# One loaded run
# =============================================================================

@dataclass
class LoadedRun:
    info: RunInfo
    sim: SimLog
    decisions: Dict[Tuple[str, int], Decision] = field(default_factory=dict)
    traces: Dict[Tuple[str, int], TraceRecord] = field(default_factory=dict)
    replay_condition: Dict[Tuple[str, int], bool] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.info.label

    def ordered(self) -> List[Decision]:
        return [self.decisions[k] for k in sorted(self.decisions, key=lambda k: (k[1], k[0]))]


def load_run(path: Path, keep_prompts: bool = False, info: Optional[RunInfo] = None) -> LoadedRun:
    info = info or read_run_info(path)
    sim = load_sim_log(info.path)
    run = LoadedRun(info, sim)
    if info.kind == "llm":
        run.decisions = load_decisions(info.path)
        run.traces = load_traces(info.path, keep_prompts=keep_prompts)
        grid = set(sim.rows)
        for name, keys in (("audit CSV", set(run.decisions)), ("traces", set(run.traces))):
            if keys != grid:
                raise MetricsError(
                    f"{info.path}: {name} and simulation_log.csv cover different agent-years "
                    f"({len(keys - grid)} only in the {name}, {len(grid - keys)} only in the log)")
        for key, decision in run.decisions.items():
            trace = run.traces[key]
            if decision.crashed != trace.crashed:
                raise MetricsError(f"{info.path} {key}: the audit and the trace disagree on an "
                                   f"{EXCEPTION_STATUS} step")
            if not decision.crashed:  # the exception sentinel logs no keep request
                base = sim.opt_num(key[0], key[1], "base_af")
                if base is None or abs(base - decision.keep_request_af) > AF_TOL:
                    raise MetricsError(f"{info.path} {key}: base_af {base} differs from the logged keep "
                                       f"request {decision.keep_request_af}")
                if trace.base_af is not None and abs(trace.base_af - decision.keep_request_af) > AF_TOL:
                    raise MetricsError(f"{info.path} {key}: state_before current_request differs from the "
                                       "keep request")
            if (trace.at_cap is None) != decision.aborted:
                raise MetricsError(f"{info.path} {key}: a state_before is missing on a decision that ran")
    elif info.kind == "replay":
        rows = _read_csv(info.path / REPLAY_CONDITION_CSV, ("agent_id", "year", "supply_condition"))
        for n, row in enumerate(rows, start=2):
            where = f"{info.path / REPLAY_CONDITION_CSV}:{n}"
            run.replay_condition[(_cell(row, "agent_id", where), _int_cell(row, "year", where))] = (
                _bool_cell(row, "supply_condition", where))
        if set(run.replay_condition) != set(sim.rows):
            raise MetricsError(f"{info.path}: supply_rule_condition.csv and the log differ in agent-years")
    return run


# =============================================================================
# Item 19: IBR, final-label IBR, relabel rate
# =============================================================================

def _pct(numerator: float, denominator: float) -> Optional[float]:
    return None if denominator == 0 else 100.0 * numerator / denominator


def ibr_metrics(decisions: Sequence[Decision]) -> Dict[str, Any]:
    """Primary IBR (item 19): decisions whose FINAL proposal violates TR1 or
    TR3, judged on the first-stated WSA (item 28), over all decisions;
    TR1 and TR3 separately and summed. Beside it: the same count on the
    final attempt's WSA, and the WSA relabel rate over retried decisions."""
    n = len(decisions)
    if n == 0:
        raise MetricsError("ibr_metrics: no decisions")
    tr1 = tr3 = tr1_final = tr3_final = 0
    retried = relabeled = 0
    no_wsa = off_scale = unreadable = final_wsa_missing = 0
    for d in decisions:
        final = d.final_proposal
        if final is None:
            unreadable += 1
        if d.first_wsa is None:
            no_wsa += 1
        elif d.first_wsa not in LEVELS:
            off_scale += 1
        v1 = final == INCREASE and d.first_wsa in TR1_WSA
        v3 = final == DECREASE and d.first_wsa in TR3_WSA
        if v1 and v3:
            raise MetricsError(f"{d.agent_id} {d.year}: violates TR1 and TR3 at once")
        tr1 += v1
        tr3 += v3
        if final is not None and d.final_wsa is None:
            final_wsa_missing += 1
        tr1_final += final == INCREASE and d.final_wsa in TR1_WSA
        tr3_final += final == DECREASE and d.final_wsa in TR3_WSA
        if d.retried:
            retried += 1
            relabeled += d.wsa_relabeled
    return {
        "decisions": n,
        "ibr_tr1_count": tr1, "ibr_tr3_count": tr3,
        "ibr_tr1_pct": _pct(tr1, n), "ibr_tr3_pct": _pct(tr3, n), "ibr_pct": _pct(tr1 + tr3, n),
        "ibr_final_label_tr1_pct": _pct(tr1_final, n), "ibr_final_label_tr3_pct": _pct(tr3_final, n),
        "ibr_final_label_pct": _pct(tr1_final + tr3_final, n),
        "retried_decisions": retried, "relabeled_decisions": relabeled,
        "relabel_rate_pct": _pct(relabeled, retried),
        "first_wsa_missing": no_wsa, "first_wsa_off_scale": off_scale,
        "final_wsa_missing": final_wsa_missing,
        "unreadable_final_proposals": unreadable,
    }


# =============================================================================
# Items 10, 19: executed feasibility violation rate
# =============================================================================

def executed_violations(run: LoadedRun) -> Dict[str, Any]:
    """Decisions whose EXECUTED action violates the supply rule (post hoc, on
    the logged state_supply_* inputs and FULL_SUPPLY_RATIO), the water-right
    cap or the minimum-use floor (flags read from state_before), over all
    decisions; and the union of the three."""
    counts = {RULE_SUPPLY: 0, RULE_CAP: 0, RULE_FLOOR: 0, "total": 0}
    for key, d in run.decisions.items():
        trace = run.traces[key]
        e = d.executed_skill
        if e is not None and trace.at_cap is None:
            raise MetricsError(f"{run.label} {key}: executed {e!r} without a state_before")
        sup = e == INCREASE and d.supply_condition
        cap = e == INCREASE and bool(trace.at_cap)
        flo = e == DECREASE and bool(trace.at_floor)
        counts[RULE_SUPPLY] += sup
        counts[RULE_CAP] += cap
        counts[RULE_FLOOR] += flo
        counts["total"] += sup or cap or flo
    n = len(run.decisions)
    return {
        "exec_supply_count": counts[RULE_SUPPLY], "exec_cap_count": counts[RULE_CAP],
        "exec_floor_count": counts[RULE_FLOOR], "exec_total_count": counts["total"],
        "exec_supply_pct": _pct(counts[RULE_SUPPLY], n), "exec_cap_pct": _pct(counts[RULE_CAP], n),
        "exec_floor_pct": _pct(counts[RULE_FLOOR], n), "exec_total_pct": _pct(counts["total"], n),
    }


# =============================================================================
# Live rule firings against the post hoc predicates, attempt by attempt
# =============================================================================

def attempt_predicates(d: Decision, trace: TraceRecord) -> List[Optional[Dict[str, Tuple[bool, bool]]]]:
    """Per attempt: {rule: (post hoc predicate, live firing)}; None for an
    unparsable attempt. TR1 and TR3 read the WSA frozen at that attempt:
    the first non-blank WSA stated in attempts 0..k (the appraisal freeze,
    spec 3.8, item 28)."""
    out: List[Optional[Dict[str, Tuple[bool, bool]]]] = []
    frozen: Optional[str] = None
    for attempt in d.attempts:
        if not attempt.parsed:
            out.append(None)
            continue
        if frozen is None and attempt.labels is not None and _stated(attempt.labels.get(WSA_KEY)):
            frozen = level(attempt.labels[WSA_KEY])
        live = set(attempt.failed_rules or ())
        predicate = {
            RULE_SUPPLY: attempt.skill == INCREASE and d.supply_condition,
            RULE_TR1: attempt.skill == INCREASE and frozen in TR1_WSA,
            RULE_TR3: attempt.skill == DECREASE and frozen in TR3_WSA,
            RULE_CAP: attempt.skill == INCREASE and bool(trace.at_cap),
            RULE_FLOOR: attempt.skill == DECREASE and bool(trace.at_floor),
        }
        out.append({rule: (predicate[rule], rule in live) for rule in ALL_RULES})
    return out


def rule_agreement(run: LoadedRun) -> Dict[str, Dict[str, Any]]:
    """For each rule live in the run's arm: attempts checked, predicate hits,
    live blocks and disagreements (P7 requires 0 for the supply rule, TR1 and
    TR3 in strict). Rules scored post hoc in the arm are not compared: they
    cannot fire."""
    live_rules = LIVE_RULES[run.info.arm]
    out = {rule: {"attempts": 0, "predicate": 0, "live": 0, "disagreements": 0, "examples": []}
           for rule in ALL_RULES if rule in live_rules}
    for key, d in run.decisions.items():
        for k, preds in enumerate(attempt_predicates(d, run.traces[key])):
            if preds is None:
                continue
            for rule, tally in out.items():
                predicate, live = preds[rule]
                tally["attempts"] += 1
                tally["predicate"] += predicate
                tally["live"] += live
                if predicate != live:
                    tally["disagreements"] += 1
                    if len(tally["examples"]) < 5:
                        tally["examples"].append(
                            f"{key[0]} year {key[1]} attempt {k}: predicate {predicate}, live {live}")
    return out


# =============================================================================
# Rule census (SI) and supply-rule exposure
# =============================================================================

def rule_census(run: LoadedRun) -> List[Dict[str, Any]]:
    """Per rule: decisions on which its condition held, first-attempt,
    final-proposal and executed violations, and live blocks (decisions and
    attempts). Cap and floor conditions are unknown on ABORTED rows and
    counted apart."""
    rows = []
    for rule in ALL_RULES:
        blocked = BLOCKED_SKILL[rule]
        held = unknown = first = final = executed = live_decisions = live_attempts = 0
        for key, d in run.decisions.items():
            trace = run.traces[key]
            condition = d.condition(rule, trace.at_cap, trace.at_floor)
            fired = [rule in (a.failed_rules or ()) for a in d.attempts]
            live_decisions += any(fired)
            live_attempts += sum(fired)
            if condition is None:
                unknown += 1
                continue
            if not condition:
                continue
            held += 1
            first += d.first_proposal == blocked
            final += d.final_proposal == blocked
            executed += d.executed_skill == blocked
        rows.append({
            "run": run.label, "arm": run.info.arm, "seed": run.info.seed, "rule": rule,
            "family": "feasibility" if rule in FEASIBILITY_RULES else "thinking",
            "enforcement": "live" if rule in LIVE_RULES[run.info.arm] else "post hoc",
            "decisions": len(run.decisions), "condition_held": held, "condition_unknown": unknown,
            "first_attempt_violations": first, "final_proposal_violations": final,
            "executed_violations": executed, "live_blocked_decisions": live_decisions,
            "live_blocked_attempts": live_attempts,
        })
    return rows


def mead_first_dead_pool_year(sim: SimLog, cfg: WaterSystemConfig) -> Optional[int]:
    """The first simulation year whose 1 January Lake Mead storage is at its
    dead pool (the state its decisions see); None if never."""
    for y in sim.years:
        if sim.system[y]["mead_storage_maf"] <= cfg.mead_dead_pool_maf + DEAD_POOL_TOL_MAF:
            return sim.sim_year(y)
    return None


def supply_exposure(run: LoadedRun, cfg: WaterSystemConfig) -> List[Dict[str, Any]]:
    """Share of agent-years on which the supply rule's condition holds (the
    state is fixed within a decision, so this is the first attempt's), by
    basin, before and after Mead's first dead-pool year; with live blocks
    and the first attempts that proposed an increase under the condition.
    An ABORTED_EXCEPTION row logs no supply state: its condition is unknown,
    counted apart and left out of the share's denominator."""
    dead_pool_year = mead_first_dead_pool_year(run.sim, cfg)
    rows = []
    for basin in ("upper_basin", "lower_basin", "all"):
        for period in ("before_dead_pool", "from_dead_pool", "all"):
            agent_years = held = unknown = live = increase_first = 0
            for (agent, year), d in run.decisions.items():
                if basin != "all" and run.sim.basin[agent] != basin:
                    continue
                sim_year = run.sim.sim_year(year)
                if period == "before_dead_pool" and dead_pool_year is not None and sim_year >= dead_pool_year:
                    continue
                if period == "from_dead_pool" and (dead_pool_year is None or sim_year < dead_pool_year):
                    continue
                agent_years += 1
                live += any(RULE_SUPPLY in (a.failed_rules or ()) for a in d.attempts)
                condition = d.supply_condition
                if condition is None:
                    unknown += 1
                    continue
                held += condition
                increase_first += condition and d.first_proposal == INCREASE
            rows.append({
                "run": run.label, "arm": run.info.arm, "seed": run.info.seed, "basin": basin,
                "period": period, "mead_first_dead_pool_year": dead_pool_year,
                "agent_years": agent_years, "condition_held": held, "condition_unknown": unknown,
                "condition_pct": _pct(held, agent_years - unknown),
                "first_attempt_increase_under_condition": increase_first,
                "live_blocked_decisions": live,
            })
    return rows


def replay_supply_condition(run: LoadedRun) -> Dict[str, int]:
    """Agent-years of a fixed-demand replay on which the supply rule's
    condition holds, by basin (R1 context)."""
    out = {"upper_basin": 0, "lower_basin": 0, "all": 0, "agent_years": len(run.replay_condition)}
    for (agent, _year), held in run.replay_condition.items():
        if held:
            out[run.sim.basin[agent]] += 1
            out["all"] += 1
    return out


# =============================================================================
# Reservoir outcomes
# =============================================================================

def mead_elevation_ft(storage_maf: float) -> float:
    """Lake Mead elevation on the model's own USBR 2009 curve
    (IrrigationEnvironment._storage_to_elevation)."""
    return float(np.interp(storage_maf, IrrigationEnvironment._STORAGE_MAF, IrrigationEnvironment._ELEVATION_FT))


def powell_elevation_ft(storage_maf: float, cfg: WaterSystemConfig) -> float:
    """Lake Powell elevation, reporting only (IrrigationEnvironment._powell_elevation_ft)."""
    active = max(0.0, storage_maf - cfg.powell_dead_pool_maf)
    return float(np.interp(active, POWELL_CURVE_ACTIVE_STORAGE_MAF, POWELL_CURVE_ELEVATION_FT))


def reservoir_outcomes(sim: SimLog, cfg: WaterSystemConfig) -> Dict[str, Any]:
    """Lake Mead minimum (lowest end-of-year elevation: 1 January of the next
    year, 1 January 2020 to 1 January 2061 on a full run) and its date,
    declared tier counts (2019-2060), dead-pool dates of both reservoirs
    (end-of-year storage within DEAD_POOL_TOL_MAF of the dead pool), and the
    Powell minimum (lowest end-of-year storage, first date)."""
    years = sim.years
    end_elev = {}
    for y in years:
        end_elev[y] = mead_elevation_ft(sim.system[y]["mead_storage_end_maf"])
        if y + 1 in sim.system and abs(sim.system[y + 1]["lake_mead_level"] - end_elev[y]) > FT_TOL:
            raise MetricsError(
                f"{sim.path}: year {y} ends at {end_elev[y]} ft, year {y + 1} starts at "
                f"{sim.system[y + 1]['lake_mead_level']} ft")
        if y + 1 in sim.system and abs(sim.system[y + 1]["powell_storage_maf"] - sim.system[y]["powell_storage_end_maf"]) > MAF_TOL:
            raise MetricsError(f"{sim.path}: Powell storage does not carry from year {y} to {y + 1}")
    mead_min = min(end_elev.values())
    mead_min_year = min(y for y in years if end_elev[y] == mead_min)
    powell_end = {y: sim.system[y]["powell_storage_end_maf"] for y in years}
    powell_min = min(powell_end.values())
    powell_min_year = min(y for y in years if powell_end[y] == powell_min)
    tiers = {k: 0 for k in range(4)}
    for y in years:
        tier = int(sim.system[y]["shortage_tier"])
        if tier not in tiers:
            raise MetricsError(f"{sim.path}: shortage_tier {tier} in year {y}")
        tiers[tier] += 1
    mead_dead = [sim.sim_year(y) + 1 for y in years
                 if sim.system[y]["mead_storage_end_maf"] <= cfg.mead_dead_pool_maf + DEAD_POOL_TOL_MAF]
    powell_dead = [sim.sim_year(y) + 1 for y in years
                   if powell_end[y] <= cfg.powell_dead_pool_maf + DEAD_POOL_TOL_MAF]
    return {
        "mead_min_ft": mead_min, "mead_min_jan1_year": sim.sim_year(mead_min_year) + 1,
        "tier0_years": tiers[0], "tier1_years": tiers[1], "tier2_years": tiers[2], "tier3_years": tiers[3],
        "mead_dead_pool_dates": mead_dead, "mead_dead_pool_count": len(mead_dead),
        "mead_first_dead_pool_jan1": mead_dead[0] if mead_dead else None,
        "powell_dead_pool_dates": powell_dead, "powell_dead_pool_count": len(powell_dead),
        "powell_first_dead_pool_jan1": powell_dead[0] if powell_dead else None,
        "powell_min_maf": powell_min, "powell_min_jan1_year": sim.sim_year(powell_min_year) + 1,
        "powell_min_ft": powell_elevation_ft(powell_min, cfg),
    }


# =============================================================================
# KGE (Gupta et al. 2009) against the FQL reference ensemble mean
# =============================================================================

# Item 30: the headline KGE is on Lake Mead, aggregate use (the UB+LB totals)
# and the UB; the LB request total is read against its own FQL benchmark.
HEADLINE_SERIES = ("mead_jan1_ft", "total_request_maf", "total_delivered_maf", "ub_request_maf",
                   "ub_delivered_maf", "lb_request_maf", "lb_delivered_maf")
P10_KGE_SERIES = ("mead_jan1_ft", "ub_request_maf", "lb_request_maf")
SUBBASIN_PREFIXES = ("ub_subbasin_request_maf:", "ub_subbasin_delivered_maf:")
LB_AGENT_PREFIX = "lb_agent_request_af:"
_BASIN_TOTALS = ("total_request_maf", "total_delivered_maf", "ub_request_maf", "lb_request_maf",
                 "ub_delivered_maf", "lb_delivered_maf")


def system_series(sim: SimLog) -> Dict[str, Dict[int, float]]:
    """The KGE series of one run, keyed by simulation year: Lake Mead 1
    January elevation; the UB+LB, UB and LB request and delivery totals (MAF,
    the agricultural agents only); each UB sub-basin's request and delivery
    totals; each LB agent's request (acre-ft)."""
    out: Dict[str, Dict[int, float]] = defaultdict(dict)
    for y in sim.years:
        year = sim.sim_year(y)
        out["mead_jan1_ft"][year] = sim.system[y]["lake_mead_level"]
        totals: Dict[str, float] = defaultdict(float)
        for a in sim.agents:
            request = sim.num(a, y, "request")
            delivered = sim.num(a, y, "diversion")
            prefix = "ub" if sim.basin[a] == "upper_basin" else "lb"
            for p in (prefix, "total"):
                totals[f"{p}_request_maf"] += request / 1e6
                totals[f"{p}_delivered_maf"] += delivered / 1e6
            sb = sim.subbasin[a]
            if sb is not None:
                totals[f"ub_subbasin_request_maf:{sb}"] += request / 1e6
                totals[f"ub_subbasin_delivered_maf:{sb}"] += delivered / 1e6
            if prefix == "lb":
                out[f"{LB_AGENT_PREFIX}{a}"][year] = request
        for name in _BASIN_TOTALS:
            totals.setdefault(name, 0.0)
        for name, value in totals.items():
            out[name][year] = value
    return dict(out)


@dataclass(frozen=True)
class Kge:
    kge: Optional[float]
    r: Optional[float]
    beta: Optional[float]   # mean ratio
    alpha: Optional[float]  # sd ratio (ddof 1)
    n: int
    note: str = ""

    def as_dict(self, prefix: str = "") -> Dict[str, Any]:
        return {f"{prefix}kge": self.kge, f"{prefix}r": self.r, f"{prefix}beta": self.beta,
                f"{prefix}alpha": self.alpha, f"{prefix}n": self.n, f"{prefix}note": self.note}


def _is_constant(x: np.ndarray) -> bool:
    """True when the range of ``x`` is within 1e-12 of its magnitude."""
    return float(np.max(x) - np.min(x)) <= 1e-12 * max(1.0, float(np.max(np.abs(x))))


CONSTANT_SIM_NOTE = "simulated series is constant: r := 0, alpha := 0 (convention)"
# replays.csv: what the convention-scored KGE cells of a fixed-demand replay are.
REPLAY_CONVENTION_NOTE = ("the series in kge_convention_series are constant by design (requests held fixed, "
                          "hold_requests_fixed) and scored by the r := 0, alpha := 0 convention: a no-change "
                          "floor, not a model result")


def kge(sim: Sequence[float], ref: Sequence[float]) -> Kge:
    """KGE = 1 - sqrt((r - 1)^2 + (alpha - 1)^2 + (beta - 1)^2) with r the
    Pearson correlation, alpha = sd(sim)/sd(ref) (ddof 1) and beta =
    mean(sim)/mean(ref) (Gupta et al. 2009, original form).

    Convention (stated assumption, orchestrator 2026-10-01): a constant
    simulated series against a reference that is not constant gets r := 0
    and alpha := 0, so KGE = 1 - sqrt(2 + (beta - 1)^2); it is scored, not
    dropped, so a median over agents never leaves out the agents whose
    requests did not move. Undefined (kge None, with the reason) only for
    fewer than KGE_MIN_YEARS points, a constant reference or a zero
    reference mean."""
    s = np.asarray(sim, dtype=float)
    o = np.asarray(ref, dtype=float)
    if s.shape != o.shape or s.ndim != 1:
        raise MetricsError(f"kge: shapes {s.shape} and {o.shape}")
    n = int(s.size)
    if n < KGE_MIN_YEARS:
        return Kge(None, None, None, None, n, f"fewer than {KGE_MIN_YEARS} years")
    if not (np.all(np.isfinite(s)) and np.all(np.isfinite(o))):
        raise MetricsError("kge: non-finite value in a series")
    # Constancy by range, not by sd: the sd of identical floats can come out
    # as rounding noise (about 1e-16), which would give a meaningless r.
    if _is_constant(o):
        return Kge(None, None, None, None, n, "reference series is constant")
    mean_o, mean_s = float(o.mean()), float(s.mean())
    if mean_o == 0.0:
        return Kge(None, None, None, None, n, "reference mean is zero")
    beta = mean_s / mean_o
    if _is_constant(s):
        return Kge(1.0 - math.sqrt(2.0 + (beta - 1.0) ** 2), 0.0, beta, 0.0, n, CONSTANT_SIM_NOTE)
    sd_o, sd_s = float(o.std(ddof=1)), float(s.std(ddof=1))
    r = float(np.corrcoef(s, o)[0, 1])
    alpha = sd_s / sd_o
    value = 1.0 - math.sqrt((r - 1.0) ** 2 + (alpha - 1.0) ** 2 + (beta - 1.0) ** 2)
    return Kge(value, r, beta, alpha, n)


@dataclass
class Reference:
    """The FQL reference: each seed's series and their ensemble mean."""

    seeds: List[int]
    series: Dict[int, Dict[str, Dict[int, float]]]
    mean: Dict[str, Dict[int, float]]
    years: Tuple[int, ...]


def build_reference(fql_runs: Sequence[LoadedRun]) -> Reference:
    if not fql_runs:
        raise MetricsError("no FQL reference runs")
    series = {}
    for run in fql_runs:
        if run.info.kind != "fql":
            raise MetricsError(f"{run.label} is not an FQL run")
        series[run.info.seed] = system_series(run.sim)
    seeds = sorted(series)
    names = set(series[seeds[0]])
    years = tuple(sorted(series[seeds[0]]["mead_jan1_ft"]))
    for seed in seeds:
        if set(series[seed]) != names:
            raise MetricsError(f"FQL seed {seed} has different series (agents or sub-basins) than seed {seeds[0]}")
        for name in names:
            if tuple(sorted(series[seed][name])) != years:
                raise MetricsError(f"FQL seed {seed} covers different years in {name}")
    mean = {name: {y: float(np.mean([series[s][name][y] for s in seeds])) for y in years} for name in names}
    return Reference(seeds, series, mean, years)


def _aligned(run_series: Mapping[int, float], ref: Mapping[int, float], what: str) -> Tuple[List[float], List[float]]:
    if tuple(sorted(run_series)) != tuple(sorted(ref)):
        raise MetricsError(f"{what}: run years {sorted(run_series)[:3]}... differ from the reference years")
    years = sorted(ref)
    return [run_series[y] for y in years], [ref[y] for y in years]


def kge_against_reference(series: Mapping[str, Mapping[int, float]], reference: Reference, label: str) -> Dict[str, Kge]:
    missing = sorted(set(reference.mean) - set(series))
    extra = sorted(set(series) - set(reference.mean))
    if missing or extra:
        raise MetricsError(f"{label}: series differ from the FQL reference (missing {missing[:3]}, extra {extra[:3]})")
    return {name: kge(*_aligned(series[name], reference.mean[name], f"{label} {name}")) for name in reference.mean}


def reference_benchmark(reference: Reference) -> Dict[int, Dict[str, Kge]]:
    """Each FQL seed against the mean of the other seeds (spec WP6), per series."""
    if len(reference.seeds) < 2:
        return {}
    out: Dict[int, Dict[str, Kge]] = {}
    for seed in reference.seeds:
        others = [s for s in reference.seeds if s != seed]
        out[seed] = {}
        for name in reference.mean:
            rest = {y: float(np.mean([reference.series[s][name][y] for s in others])) for y in reference.years}
            out[seed][name] = kge(*_aligned(reference.series[seed][name], rest, f"FQL seed {seed} {name}"))
    return out


def _median(values: Sequence[float]) -> Optional[float]:
    return float(statistics.median(values)) if values else None


def lb_agent_summary(kges: Mapping[str, Kge]) -> Dict[str, Any]:
    """Median of the per-agent LB request KGE over the agents with a KGE,
    with the count of agents scored by the constant-series convention
    (``constant_sim``, included in the median) and of agents without a KGE
    (``undefined``: a constant reference, the same in every arm)."""
    agents = [k for name, k in kges.items() if name.startswith(LB_AGENT_PREFIX)]
    values = [k.kge for k in agents if k.kge is not None]
    return {"median": _median(values), "defined": len(values),
            "constant_sim": sum(1 for k in agents if k.note == CONSTANT_SIM_NOTE),
            "undefined": sum(1 for k in agents if k.kge is None)}


# =============================================================================
# R4 (item 23): drought recovery of each UB sub-basin. Dry-year definition
# reworked 2026-10-01 (reviewer fix, item 33c): see ub_subbasin_dry_years.
# =============================================================================

def _at_least(value: float, reference: float) -> bool:
    """value >= reference, with float noise at the edge counted as equal."""
    return value >= reference or math.isclose(value, reference, rel_tol=1e-9, abs_tol=AF_TOL)


# The threshold-level method of hydrological drought (ub_subbasin_dry_years):
# no source sets this percentile for an irrigation sub-basin, so it is a
# named, stated ASSUMPTION (item 34), never a tuned value.
UB_DRY_YEAR_PERCENTILE = 20.0


def _ub_subbasin_available_af(sim: SimLog, cfg: WaterSystemConfig) -> Dict[str, Dict[int, float]]:
    """A_s(t) (acre-ft, WP1b item 20) for every UB sub-basin present in
    ``sim``, by loop year, from the run's own ``ub_subbasin_supply_variant``
    (``_load_ub_subbasin_supply_table``: the module's existing, checksum-
    pinned data access -- this function never copies a supply number).
    Shared by ``ub_subbasin_dry_years`` (R4, R5c) and ``r5d_ub_little_spare``."""
    table = _load_ub_subbasin_supply_table(cfg.ub_subbasin_supply_variant)
    sub_basins = sorted({sb for sb in sim.subbasin.values() if sb is not None})
    out: Dict[str, Dict[int, float]] = {}
    for sb in sub_basins:
        series: Dict[int, float] = {}
        for y in sim.years:
            sim_year = sim.sim_year(y)
            if sim_year not in table:
                raise MetricsError(
                    f"{sim.path}: year {y} (sim_year {sim_year}) is outside the ub_subbasin_supply "
                    f"table for variant {cfg.ub_subbasin_supply_variant!r}")
            series[y] = table[sim_year][f"a_{sb}_af"]
        out[sb] = series
    return out


def _ub_subbasin_dry_threshold(cfg: WaterSystemConfig, sub_basin: str) -> float:
    """The UB_DRY_YEAR_PERCENTILE-th percentile of one UB sub-basin's A_s
    over the FULL ub_subbasin_supply_v3 table for cfg's own
    ``ub_subbasin_supply_variant`` -- every row the table holds (42 on the
    real data), never just the years one run happens to cover (item 34:
    "the 42-year trace"). A run shorter than the full table (a pilot run, a
    test fixture) therefore gets the SAME threshold, hence the same dry
    years, as the full table restricted to its own years
    (test_ub_subbasin_dry_years_uses_the_full_table_not_the_runs_own_years,
    test_v3_metrics.py)."""
    table = _load_ub_subbasin_supply_table(cfg.ub_subbasin_supply_variant)
    values = [row[f"a_{sub_basin}_af"] for row in table.values()]
    return float(np.percentile(values, UB_DRY_YEAR_PERCENTILE))


def ub_subbasin_dry_years(sim: SimLog, cfg: WaterSystemConfig) -> Dict[str, Set[int]]:
    """Exogenous hydrological dry years (item 34; replaces the realised-
    shortage definition this docstring describes below). Per UB sub-basin,
    a dry year is one whose sub-basin supply A_s(t)
    (``_ub_subbasin_available_af``) is below the UB_DRY_YEAR_PERCENTILE-th
    percentile of that sub-basin's A_s over the FULL supply table
    (``_ub_subbasin_dry_threshold``, "the 42-year trace", not just this
    run's own years): the threshold-level method of hydrological drought, a
    stated ASSUMPTION (no source sets a percentile for this; Brunner and
    Tallaksen 2019 and irrigation_v3_drought_rule_scan_2026-10-01.md Q2 give
    classes, not a cutoff). A_s is a hydrology input, fixed before any agent
    decides, so these dry years are identical for every arm and seed that
    shares a ``ub_subbasin_supply_variant``, whatever years each run itself
    covers (test_ub_subbasin_dry_years_independent_of_agent_behaviour,
    test_v3_metrics.py).

    Replaces: dry year = ``ub_subbasin_ratio`` < FULL_SUPPLY_RATIO, the
    settled share at the members' FINAL, post-decision requests. That
    definition was endogenous: at a level supply (A_s at or above the sum
    of the sub-basin's keep requests) a dry year existed only when some
    member's request rose that year and pushed the sub-basin over its
    available supply, so an arm whose agents increase more produced more,
    and longer, spells for a reason that had nothing to do with the water
    available; and under the appraisal freeze, an agent's own increase in a
    level year could itself turn that year dry and then (item 29c's
    sharing clause) lower its own later first-stated WSA, so R5c's "WSA
    dulls within a dry spell" reading was partly true by construction,
    not only by appraisal."""
    available = _ub_subbasin_available_af(sim, cfg)
    out: Dict[str, Set[int]] = {}
    for sb, series in available.items():
        threshold = _ub_subbasin_dry_threshold(cfg, sb)
        out[sb] = {y for y, a in series.items() if a < threshold}
    return out


def drought_recovery(sim: SimLog, cfg: WaterSystemConfig, label: str, arm: str = "") -> List[Dict[str, Any]]:
    """R4 (item 23), the study's definition (orchestrator, 2026-10-01; dry
    year redefined by reviewer fix, 2026-10-01: see ``ub_subbasin_dry_years``).

    Per UB sub-basin (``ub_subbasin``), a dry spell is a maximal run of
    consecutive ``ub_subbasin_dry_years`` years. Its reference is the
    sub-basin's total ``request`` in the last year before the spell; a spell
    that starts in the first year has no reference and is skipped (status
    "no reference", counted). The recovery time is the smallest j >= 1 such
    that the total request in (last spell year + j) is at or above the
    reference (``_at_least``). A spell is censored when that is not reached
    before the next spell starts or the run ends. The same function scores
    every LLM run and every FQL seed."""
    spells: List[Dict[str, Any]] = []
    groups: Dict[str, List[str]] = defaultdict(list)
    for a in sim.agents:
        if sim.subbasin[a] is not None:
            groups[sim.subbasin[a]].append(a)
    dry_years = ub_subbasin_dry_years(sim, cfg)
    first, last = sim.years[0], sim.years[-1]
    for sb in sorted(groups):
        members = groups[sb]
        dry = dry_years[sb]
        request: Dict[int, float] = {y: sum(sim.num(a, y, "request") for a in members) for y in sim.years}
        y = first
        while y <= last:
            if y not in dry:
                y += 1
                continue
            start = y
            while y + 1 <= last and (y + 1) in dry:
                y += 1
            end = y
            record = {"run": label, "arm": arm, "subbasin": sb, "members": len(members),
                      "start_year": sim.sim_year(start), "end_year": sim.sim_year(end),
                      "dry_years": end - start + 1, "reference_request_af": None,
                      "recovery_years": None, "status": "", "censored_by": ""}
            if start == first:
                record["status"] = "no reference"
            else:
                reference = request[start - 1]
                record["reference_request_af"] = reference
                record["status"], record["censored_by"] = "censored", "end of run"
                for u in range(end + 1, last + 1):
                    if u in dry:
                        record["censored_by"] = "next spell"
                        break
                    if _at_least(request[u], reference):
                        record["status"], record["censored_by"] = "recovered", ""
                        record["recovery_years"] = u - end
                        break
            spells.append(record)
            y = end + 1
    return spells


def recovery_summary(spells: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Pooled R4 counts: spells with a reference, how many recovered and were
    censored, the median recovery years among the recovered spells, and the
    skipped spells that had no reference."""
    scored = [s for s in spells if s["status"] != "no reference"]
    recovered = [s["recovery_years"] for s in scored if s["status"] == "recovered"]
    return {
        "r4_spells": len(scored), "r4_recovered": len(recovered),
        "r4_censored": sum(s["status"] == "censored" for s in scored),
        "r4_median_recovery_years": _median(recovered),
        "r4_no_reference": len(spells) - len(scored),
    }


def recovery_table(spells: Sequence[Mapping[str, Any]], groups: Sequence[str],
                   group_key: str = "arm") -> List[Dict[str, Any]]:
    """R4 per sub-basin and pooled, for each group in ``groups`` (an LLM arm
    with its seeds pooled, or "fql", the FQL seeds pooled). A group with no
    spell still gets its pooled row, with zero counts."""
    rows: List[Dict[str, Any]] = []
    for group in groups:
        mine = [s for s in spells if s[group_key] == group]
        for sb in sorted({s["subbasin"] for s in mine}) + ["pooled"]:
            subset = mine if sb == "pooled" else [s for s in mine if s["subbasin"] == sb]
            rows.append({group_key: group, "subbasin": sb, **recovery_summary(subset)})
    return rows


# =============================================================================
# R5 (item 33c; pre-registered 2026-10-01, `irrigation_v3_drought_rule_scan_
# 2026-10-01.md` Q6): first-stated WSA against the supply headline, the
# agent's short-year history and item-31 dry spells. Report-only: never
# gated (v3_pilot_gate's checks read none of this), never part of the IBR,
# never a refusal, never changes the runner, prompts or governance. Computed
# for LLM runs only; the FQL reference states no appraisal.
# =============================================================================

# This module's own ordinal code for a first-stated WSA level, used only by
# R5b and R5c's means; no other part of this module orders WSA numerically.
WSA_ORDINAL: Dict[str, int] = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}

# R5a's five bands are REPORT-ONLY analysis bins (item 36a, 2026-10-05
# design-basis audit + fix proposals, spec item 36a): before 2026-10-05
# these were irrigation_personas.build_water_situation_text's own
# headline bands; as of item 36a that function's headline collapsed to
# TWO states at FULL_SUPPLY_RATIO (no agent reads a "slightly short" /
# "well short" / "critical" distinction any more), but the five-way
# split survives HERE, for reporting only, so R5a's pre-registered
# analysis is unaffected. The top edge is FULL_SUPPLY_RATIO (imported
# above, never copied here); the other three edges (0.95, 0.80, 0.50)
# are literals in r5a_headline_band below, with no importable constant
# and no longer cross-checked against build_water_situation_text's own
# source (which no longer states them) -- see
# test_r5a_band_edges_are_the_five_retired_prompt_bands (test_v3_metrics.py).
# "short" renamed to "moderately_short" (Opus review P3-6, 2026-10-06):
# since item 36a the prompt's own headline is two states, "sufficient"
# and "short" (everything below FULL_SUPPLY_RATIO) -- a bare "short"
# band here, in [0.80, 0.95), read as if it were that SAME prompt state,
# when it is one fifth of a report-only split the agent never reads.
R5A_BANDS = ("sufficient", "slightly_short", "moderately_short", "well_short", "critical")
R5B_SHORT_YEAR_WINDOW = 5  # config/agent_types.yaml irrigation_farmer.feedback.trend_window
R5C_POST_SPELL_YEARS = 3  # item 33c: "the 3 years after the spell ends"


def r5a_headline_band(r_share: float) -> str:
    """The five-way REPORT-ONLY band for r = supply_ratio (Decision.
    supply_ratio, state_supply_ratio). Before item 36a (2026-10-05) these
    five bands were exactly irrigation_personas.build_water_situation_text's
    own prompt headline; as of item 36a that function's headline is TWO
    states only (sufficient / short, at FULL_SUPPLY_RATIO) -- the agent
    never reads the "slightly short" / "well short" / "critical"
    distinction below. R5a keeps the five-way split as an analysis bin
    only, so the pre-registered report is unaffected by the prompt
    change; the three interior edges (0.95, 0.80, 0.50) are this
    function's own literals now, not a copy of anything in the prompt."""
    if r_share >= FULL_SUPPLY_RATIO:
        return "sufficient"
    if r_share >= 0.95:
        return "slightly_short"
    if r_share >= 0.80:
        return "moderately_short"
    if r_share >= 0.50:
        return "well_short"
    return "critical"


def _new_wsa_tally() -> Dict[str, Any]:
    return {"n": 0, "sum_wsa": 0, "aborted_excluded": 0, "blank_wsa_excluded": 0, "off_scale_excluded": 0}


def _add_decision_to_wsa_tally(tally: Dict[str, Any], d: Decision) -> None:
    """Item 33c's exclusion rule for R5b and R5c: an ABORTED or
    ABORTED_EXCEPTION row is excluded and counted under aborted_excluded; a
    decision with no first-stated WSA under blank_wsa_excluded; one whose
    first-stated WSA is stated but is not one of the five construct levels
    under off_scale_excluded (reviewer fix, 2026-10-01: the ibr_metrics
    split of first_wsa_missing from first_wsa_off_scale). None of these is
    ever silently dropped from the mean."""
    if d.aborted:
        tally["aborted_excluded"] += 1
        return
    if d.first_wsa is None:
        tally["blank_wsa_excluded"] += 1
        return
    if d.first_wsa not in WSA_ORDINAL:
        tally["off_scale_excluded"] += 1
        return
    tally["n"] += 1
    tally["sum_wsa"] += WSA_ORDINAL[d.first_wsa]


def _wsa_category(first_wsa: Optional[str]) -> str:
    """first_wsa as an R5a cell key: "missing" (no statement, including
    every ABORTED row) or "off_scale" (stated, but not one of the five
    construct levels) are counted apart (reviewer fix, 2026-10-01), never
    merged, as ibr_metrics splits first_wsa_missing from first_wsa_off_scale."""
    if first_wsa is None:
        return "missing"
    if first_wsa not in WSA_ORDINAL:
        return "off_scale"
    return first_wsa


R5A_WSA_CATEGORIES = list(LEVELS) + ["missing", "off_scale"]


def r5a_wsa_by_band(run: LoadedRun) -> List[Dict[str, Any]]:
    """R5a: first-stated WSA distribution by the prompt's supply headline
    band, over this run's decisions. A decision whose state_supply_ratio is
    unknown (the ABORTED_EXCEPTION sentinel, which logs no supply state) has
    no band and is counted under band "unknown_no_supply_state" rather than
    dropped. See _wsa_category for the missing/off_scale split."""
    counts: Dict[Tuple[Optional[str], str], int] = defaultdict(int)
    for d in run.decisions.values():
        band = r5a_headline_band(d.supply_ratio) if d.supply_ratio is not None else None
        counts[(band, _wsa_category(d.first_wsa))] += 1
    rows: List[Dict[str, Any]] = []
    for band in R5A_BANDS:
        for wsa in R5A_WSA_CATEGORIES:
            rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                        "band": band, "first_wsa": wsa, "decisions": counts.get((band, wsa), 0)})
    for wsa in R5A_WSA_CATEGORIES:
        n = counts.get((None, wsa), 0)
        if n:
            rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                        "band": "unknown_no_supply_state", "first_wsa": wsa, "decisions": n})
    return rows


def r5a_band_summary(rows: Sequence[Mapping[str, Any]], groups: Sequence[str]) -> List[Dict[str, Any]]:
    """R5a pooled by arm (seeds summed), with each cell's share of its
    arm+band total. Every real band (R5A_BANDS) always gets its zero cells
    (the recovery_table pattern); "unknown_no_supply_state" is pooled and
    emitted too, for whichever arm actually logged an ABORTED_EXCEPTION
    decision (reviewer fix, 2026-10-01: it was silently dropped from this
    summary before, even though r5a_wsa_by_band already counted it)."""
    pooled = {(r["arm"], r["band"], r["first_wsa"]): r["decisions"]
             for r in _sum_by(rows, ("arm", "band", "first_wsa"), ("decisions",))}
    band_totals: Dict[Tuple[str, str], int] = defaultdict(int)
    for (arm, band, _wsa), n in pooled.items():
        band_totals[(arm, band)] += n
    out: List[Dict[str, Any]] = []
    for arm in groups:
        bands = list(R5A_BANDS)
        if (arm, "unknown_no_supply_state") in band_totals:
            bands.append("unknown_no_supply_state")
        for band in bands:
            total = band_totals.get((arm, band), 0)
            for wsa in R5A_WSA_CATEGORIES:
                n = pooled.get((arm, band, wsa), 0)
                out.append({"arm": arm, "band": band, "first_wsa": wsa, "decisions": n,
                            "band_total_decisions": total, "pct_of_band": _pct(n, total)})
    return out


def r5b_wsa_by_short_years(run: LoadedRun) -> List[Dict[str, Any]]:
    """R5b: mean first-stated WSA (WSA_ORDINAL) by K, the number of short
    years (that year's final delivery below FULL_SUPPLY_RATIO of its
    request, irrigation_personas.supply_ratio on simulation_log's diversion
    and request) among the agent's last R5B_SHORT_YEAR_WINDOW shown years,
    the dashboard history window (config/agent_types.yaml
    irrigation_farmer.feedback.trend_window; pinned by
    assert_short_year_window_matches_config). full_window marks whether the
    window actually held all R5B_SHORT_YEAR_WINDOW years (reviewer fix,
    2026-10-01: False in years 2..R5B_SHORT_YEAR_WINDOW, when fewer years
    have been shown yet, so a K of, say, 2 does not mean the same thing with
    2 years shown as with 5). A decision in the first simulated year has no
    shown prior year at all; it is counted under k_short_years "no_window"
    rather than silently folded into K = 0."""
    sim = run.sim
    tallies: Dict[Tuple[int, bool], Dict[str, Any]] = defaultdict(_new_wsa_tally)
    no_window = 0
    for (agent, y), d in run.decisions.items():
        if y <= sim.years[0]:
            no_window += 1
            continue
        window = list(range(max(sim.years[0], y - R5B_SHORT_YEAR_WINDOW), y))
        full_window = len(window) >= R5B_SHORT_YEAR_WINDOW
        k = sum(1 for yy in window if supply_ratio(sim.num(agent, yy, "diversion"),
                                                   sim.num(agent, yy, "request")) < FULL_SUPPLY_RATIO)
        _add_decision_to_wsa_tally(tallies[(k, full_window)], d)
    rows: List[Dict[str, Any]] = []
    for k in range(0, R5B_SHORT_YEAR_WINDOW + 1):
        for full_window in (True, False):
            t = tallies.get((k, full_window), _new_wsa_tally())
            rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                        "k_short_years": k, "full_window": full_window,
                        "n_in_mean": t["n"], "sum_first_wsa": t["sum_wsa"],
                        "mean_first_wsa": (t["sum_wsa"] / t["n"]) if t["n"] else None,
                        "aborted_excluded": t["aborted_excluded"], "blank_wsa_excluded": t["blank_wsa_excluded"],
                        "off_scale_excluded": t["off_scale_excluded"], "no_window_excluded": 0})
    rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                "k_short_years": "no_window", "full_window": None,
                "n_in_mean": 0, "sum_first_wsa": 0, "mean_first_wsa": None,
                "aborted_excluded": 0, "blank_wsa_excluded": 0, "off_scale_excluded": 0,
                "no_window_excluded": no_window})
    return rows


def r5b_summary_table(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """R5b pooled by arm: counts and WSA-ordinal totals summed over seeds,
    the mean recomputed from the pooled sums (never averaging already
    per-run means)."""
    pooled = _sum_by(rows, ("arm", "k_short_years", "full_window"),
                     ("n_in_mean", "sum_first_wsa", "aborted_excluded", "blank_wsa_excluded",
                      "off_scale_excluded", "no_window_excluded"))
    for row in pooled:
        row["mean_first_wsa"] = row["sum_first_wsa"] / row["n_in_mean"] if row["n_in_mean"] else None
    return pooled


def r5c_wsa_by_spell_year(run: LoadedRun, cfg: WaterSystemConfig) -> List[Dict[str, Any]]:
    """R5c: mean first-stated WSA by year within each item-31 UB dry spell
    (the same spells as drought_recovery/R4, including the reviewer's
    exogenous A_s-percentile redefinition: position_type "in_spell",
    position 1, 2, 3... counted from the spell's first dry year) and in the
    R5C_POST_SPELL_YEARS years after it ends (position_type "after_spell",
    position 1..3). UB sub-basins only: drought_recovery groups agents by
    ub_subbasin, which is blank for every Lower Basin agent, so R5c is
    UB-only too, like R4 (spec item 33c). A year that is both N years after
    one spell and inside the next is counted on both axes: they answer
    different questions and are not mutually exclusive. Because the spells
    no longer depend on agent decisions, R5c's positions are identical
    across arms and seeds too."""
    sim = run.sim
    spells = drought_recovery(sim, cfg, run.label, run.info.arm)
    groups: Dict[str, List[str]] = defaultdict(list)
    for a in sim.agents:
        if sim.subbasin[a] is not None:
            groups[sim.subbasin[a]].append(a)
    last = sim.years[-1]
    tallies: Dict[Tuple[str, int], Dict[str, Any]] = defaultdict(_new_wsa_tally)
    for spell in spells:
        start = spell["start_year"] - sim.sim_start_year + 1
        end = spell["end_year"] - sim.sim_start_year + 1
        members = groups[spell["subbasin"]]
        for y in range(start, end + 1):
            for agent in members:
                d = run.decisions.get((agent, y))
                if d is None:
                    raise MetricsError(f"{run.label}: no decision for {agent} year {y} (R5c in_spell)")
                _add_decision_to_wsa_tally(tallies[("in_spell", y - start + 1)], d)
        for offset in range(1, R5C_POST_SPELL_YEARS + 1):
            y = end + offset
            if y > last:
                break
            for agent in members:
                d = run.decisions.get((agent, y))
                if d is None:
                    raise MetricsError(f"{run.label}: no decision for {agent} year {y} (R5c after_spell)")
                _add_decision_to_wsa_tally(tallies[("after_spell", offset)], d)
    rows: List[Dict[str, Any]] = []
    for (position_type, position), t in sorted(tallies.items(), key=lambda kv: (kv[0][0] != "in_spell", kv[0][1])):
        rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                    "position_type": position_type, "position": position,
                    "n_in_mean": t["n"], "sum_first_wsa": t["sum_wsa"],
                    "mean_first_wsa": (t["sum_wsa"] / t["n"]) if t["n"] else None,
                    "aborted_excluded": t["aborted_excluded"], "blank_wsa_excluded": t["blank_wsa_excluded"],
                    "off_scale_excluded": t["off_scale_excluded"]})
    return rows


def r5c_summary_table(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """R5c pooled by arm, the same way as r5b_summary_table."""
    pooled = _sum_by(rows, ("arm", "position_type", "position"),
                     ("n_in_mean", "sum_first_wsa", "aborted_excluded", "blank_wsa_excluded",
                      "off_scale_excluded"))
    for row in pooled:
        row["mean_first_wsa"] = row["sum_first_wsa"] / row["n_in_mean"] if row["n_in_mean"] else None
    return pooled


# R5d's splits (reviewer fix, item 33c, 2026-10-01; spec 33b: how often an
# Upper Basin increase takes water from others while a drought persists at a
# level supply). "overall" is the original, pre-reviewer definition, now
# also excluding at-cap decisions (see _r5d_population).
R5D_SPLITS: Tuple[Tuple[str, Dict[str, str]], ...] = (
    ("overall", {}),
    ("basin=upper_basin", {"basin_filter": "upper_basin"}),
    ("basin=lower_basin", {"basin_filter": "lower_basin"}),
    ("last_year=short", {"last_year_filter": "short"}),
    ("last_year=not_short", {"last_year_filter": "not_short"}),
    ("last_year=first_year", {"last_year_filter": "first_year"}),
    # Crossed (reviewer fix, item 34): spec 33b's own scenario, an Upper
    # Basin agent proposing while a drought persists at a level supply, read
    # through the prompt's last-year-short framing rather than the hydrology
    # (item 31/34 dry-spell) framing of R5c.
    ("basin=upper_basin,last_year=short", {"basin_filter": "upper_basin", "last_year_filter": "short"}),
)


def _r5d_population(run: LoadedRun, basin_filter: Optional[str] = None,
                    last_year_filter: Optional[str] = None) -> Dict[str, int]:
    """One R5d split's tally. Eligible = first-stated WSA not High or Very
    High AND the supply rule's condition False (neither TR1 nor the supply
    rule could act). Excluded and counted beside, never folded into the
    denominator: ABORTED/ABORTED_EXCEPTION, a blank or off-scale
    first-stated WSA, and (reviewer fix, item 34) an at-cap decision: the
    menu does not OFFER increase_demand there, but an off-menu increase can
    still be PROPOSED (the LLM is not restricted to the menu) and is then
    blocked by the water-right cap, not by TR1 or the supply rule -- a
    different blocking mechanism, so it does not belong in "neither TR1 nor
    the supply rule could act" either way. Fixture d6 in
    test_r5d_hand_computed is exactly this case: at the cap, first proposal
    increase_demand, blocked by the cap (and the two registry backstops).
    ``basin_filter`` restricts to "upper_basin" or "lower_basin";
    ``last_year_filter`` to "short", "not_short" or "first_year" (no prior
    shown year: the prompt's first-year sentence states no shortfall, spec
    4.3)."""
    sim = run.sim
    eligible = increases = 0
    excl_aborted = excl_blank = excl_off_scale = excl_at_cap = 0
    for (agent, y), d in run.decisions.items():
        if basin_filter is not None and sim.basin[agent] != basin_filter:
            continue
        if last_year_filter is not None:
            if y == sim.years[0]:
                category = "first_year"
            else:
                prior_short = supply_ratio(sim.num(agent, y - 1, "diversion"),
                                           sim.num(agent, y - 1, "request")) < FULL_SUPPLY_RATIO
                category = "short" if prior_short else "not_short"
            if category != last_year_filter:
                continue
        if d.aborted:
            excl_aborted += 1
            continue
        if d.first_wsa is None:
            excl_blank += 1
            continue
        if d.first_wsa not in WSA_ORDINAL:
            excl_off_scale += 1
            continue
        if run.traces[(agent, y)].at_cap:
            excl_at_cap += 1
            continue
        condition = d.supply_condition
        if condition is None:
            raise MetricsError(f"{run.label} {agent} {y}: supply_condition is unknown on a "
                              "decision that was not aborted")
        if d.first_wsa in TR1_WSA or condition:
            continue  # TR1 or the supply rule could act: not an R5d decision
        eligible += 1
        increases += d.first_proposal == INCREASE
    return {"eligible_decisions": eligible, "first_proposal_increases": increases,
           "excluded_aborted": excl_aborted, "excluded_blank_wsa": excl_blank,
           "excluded_off_scale_wsa": excl_off_scale, "excluded_at_cap": excl_at_cap}


def r5d_rows(run: LoadedRun) -> List[Dict[str, Any]]:
    """R5d with the reviewer's splits: the pooled row ("overall"), by basin,
    by whether last year was short as the prompt shows it, and the crossed
    Upper-Basin-and-last-year-short row."""
    rows = []
    for split, kwargs in R5D_SPLITS:
        tally = _r5d_population(run, **kwargs)
        rows.append({"run": run.label, "arm": run.info.arm, "seed": run.info.seed, "split": split,
                    **tally, "share_pct": _pct(tally["first_proposal_increases"], tally["eligible_decisions"])})
    return rows


def r5d_summary_table(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """R5d pooled by arm and split."""
    pooled = _sum_by(rows, ("arm", "split"),
                     ("eligible_decisions", "first_proposal_increases", "excluded_aborted",
                      "excluded_blank_wsa", "excluded_off_scale_wsa", "excluded_at_cap"))
    for row in pooled:
        row["share_pct"] = _pct(row["first_proposal_increases"], row["eligible_decisions"])
    return pooled


def r5d_ub_little_spare(run: LoadedRun, cfg: WaterSystemConfig) -> Dict[str, Any]:
    """R5d-UB-little-spare (item 34; spec 33b; REPLACES r5d_ub_zero_sum,
    2026-10-01). r5d_ub_zero_sum's strict zero-sum condition (the supply
    rule's condition False AND A_s(t) <= the sub-basin's keep-request sum)
    is near-empty by construction: for a UB sub-basin, every member's
    settled ratio at the keep requests is the SAME shared factor,
    min(1, A_s / sum of keep requests) (spec WP1b.3), so the supply rule's
    condition is False exactly when that factor is at least
    FULL_SUPPLY_RATIO, i.e. A_s is ALREADY at least FULL_SUPPLY_RATIO times
    the keep-request sum -- "A_s <= the keep-request sum" can then only add
    the razor-thin band [FULL_SUPPLY_RATIO, 1) of it, and its hand test
    needed a ratio the water system cannot actually produce from the A_s
    and keep requests it assumed.

    This metric instead asks whether the sub-basin's unused water, A_s(t)
    minus the sum of its members' keep requests that year (never negative
    when the supply rule did not fire, up to float tolerance), is smaller
    than the DECIDING agent's own typical step -- ``typical_step_af``,
    simulation_log.csv's own column (spec 2.5: the median of the agent's
    own step distribution; the same number the option texts show, "your
    typical step of about {s} acre-ft", irrigation_personas.
    build_option_texts). When 0 <= unused < typical_step_af, even one
    ordinary-sized increase by this agent cannot be absorbed by the
    sub-basin's unused water and must come out of other members' shares
    (spec 29c's sharing clause). Among such decisions, the share of first
    proposals that are increases.

    The keep-request sum is read from Decision.keep_request_af
    (``state_supply_keep_request_af``, logged for every decision), never
    from a settled, POST-decision total: that is exactly the endogenous
    quantity the reviewer flagged for R4 and R5c. A member whose keep
    request is unknown (the ABORTED_EXCEPTION sentinel) makes that
    sub-basin-year's sum unknown; every other decision in that sub-basin-
    year is then excluded and counted under excluded_unknown_sum rather
    than reported as computable from a partial sum."""
    sim = run.sim
    available = _ub_subbasin_available_af(sim, cfg)
    groups: Dict[str, List[str]] = defaultdict(list)
    for a in sim.agents:
        if sim.subbasin[a] is not None:
            groups[sim.subbasin[a]].append(a)
    eligible = increases = excluded_aborted = excluded_unknown_sum = 0
    for sb, members in groups.items():
        for y in sim.years:
            member_decisions = [run.decisions[(m, y)] for m in members]
            known = all(d.keep_request_af is not None for d in member_decisions)
            keep_sum = sum(d.keep_request_af for d in member_decisions) if known else None
            a_s = available[sb][y]
            for agent, d in zip(members, member_decisions):
                if d.aborted:
                    excluded_aborted += 1
                    continue
                condition = d.supply_condition
                if condition is None:
                    raise MetricsError(f"{run.label} {d.agent_id} {d.year}: supply_condition is "
                                      "unknown on a decision that was not aborted")
                if condition:
                    continue  # the supply rule could act: not this population
                if keep_sum is None:
                    excluded_unknown_sum += 1
                    continue
                unused = a_s - keep_sum
                step = sim.num(agent, y, "typical_step_af")
                if not (0 <= unused < step):
                    continue  # plenty of spare water (or, rarely, a float-noise negative)
                eligible += 1
                increases += d.first_proposal == INCREASE
    return {"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
           "eligible_decisions": eligible, "first_proposal_increases": increases,
           "share_pct": _pct(increases, eligible),
           "excluded_aborted": excluded_aborted, "excluded_unknown_sum": excluded_unknown_sum}


def r5d_ub_little_spare_summary(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    """R5d-UB-little-spare pooled by arm."""
    pooled = _sum_by(rows, ("arm",), ("eligible_decisions", "first_proposal_increases",
                                      "excluded_aborted", "excluded_unknown_sum"))
    for row in pooled:
        row["share_pct"] = _pct(row["first_proposal_increases"], row["eligible_decisions"])
    return pooled


# =============================================================================
# Statistics: per-arm description, exact sign-flip test
# =============================================================================

def describe(values: Sequence[Optional[float]]) -> Dict[str, Any]:
    vals = [float(v) for v in values if v is not None]
    n = len(vals)
    return {
        "n": n, "n_missing": len(values) - n,
        "mean": statistics.fmean(vals) if n else None,
        "sd": statistics.stdev(vals) if n >= 2 else None,
        "median": statistics.median(vals) if n else None,
        "min": min(vals) if n else None, "max": max(vals) if n else None,
    }


def sign_flip_test(diffs: Sequence[float]) -> Dict[str, Any]:
    """Exact two-sided sign-flip (paired permutation) test of the mean paired
    difference: p = share of the 2^n sign assignments whose |mean| is at
    least the observed one. A zero difference keeps its value under either
    sign, so with z zero differences the smallest attainable p is
    2^(z + 1) / 2^n (capped at 1); with none it is 2 / 2^n, 0.0625 at
    n = 5, so no two-sided p below 0.05 is possible with five pairs."""
    n = len(diffs)
    if n < 2:
        return {"n_pairs": n, "mean_diff": diffs[0] if n else None, "p_two_sided": None,
                "p_floor": None, "zero_diffs": sum(1 for d in diffs if d == 0.0),
                "note": "fewer than 2 pairs: no test"}
    observed = abs(sum(diffs)) / n
    count = 0
    for signs in itertools.product((1.0, -1.0), repeat=n):
        stat = abs(sum(s * d for s, d in zip(signs, diffs))) / n
        if stat >= observed * (1.0 - 1e-12) - 1e-15:
            count += 1
    zeros = sum(1 for d in diffs if d == 0.0)
    return {"n_pairs": n, "mean_diff": sum(diffs) / n, "p_two_sided": count / 2 ** n,
            "p_floor": min(1.0, 2.0 ** (zeros + 1) / 2 ** n), "zero_diffs": zeros, "note": ""}


# =============================================================================
# One LLM run: every per-run metric
# =============================================================================

def run_metrics(run: LoadedRun, reference: Reference, cfg: WaterSystemConfig) -> Dict[str, Any]:
    """The per-run row of every scalar metric, plus the run's tables."""
    if run.info.kind != "llm":
        raise MetricsError(f"{run.label}: run_metrics takes an LLM run")
    decisions = run.ordered()
    row: Dict[str, Any] = {"run": run.label, "arm": run.info.arm, "seed": run.info.seed,
                           "path": str(run.info.path)}
    row.update(ibr_metrics(decisions))
    row.update(executed_violations(run))
    exposure = supply_exposure(run, cfg)
    for e in exposure:
        if e["period"] == "all":
            suffix = {"upper_basin": "_ub", "lower_basin": "_lb", "all": ""}[e["basin"]]
            row[f"supply_condition{suffix}_pct"] = e["condition_pct"]
            if e["basin"] == "all":
                row["supply_live_blocked_decisions"] = e["live_blocked_decisions"]
    reservoir = reservoir_outcomes(run.sim, cfg)
    row.update(reservoir)
    kges = kge_against_reference(system_series(run.sim), reference, run.label)
    for name in HEADLINE_SERIES:
        row[f"kge_{name}"] = kges[name].kge
    lb = lb_agent_summary(kges)
    row["kge_lb_agent_request_median"] = lb["median"]
    row["kge_lb_agent_defined"] = lb["defined"]
    row["kge_lb_agent_constant_sim"] = lb["constant_sim"]
    row["kge_lb_agent_undefined"] = lb["undefined"]
    episodes = drought_recovery(run.sim, cfg, run.label, run.info.arm)
    row.update(recovery_summary(episodes))
    return {
        "row": row, "exposure": exposure, "census": rule_census(run),
        "agreement": rule_agreement(run), "kge": kges, "recovery": episodes,
    }


def _kge_rows(label: str, kind: str, kges: Mapping[str, Kge]) -> List[Dict[str, Any]]:
    return [{"run": label, "kind": kind, "series": name, **k.as_dict()} for name, k in sorted(kges.items())]


# =============================================================================
# Metrics over a corpus
# =============================================================================

PAIRED_METRICS = (
    "ibr_pct", "ibr_tr1_pct", "ibr_tr3_pct", "ibr_final_label_pct", "relabel_rate_pct",
    "exec_supply_pct", "exec_total_pct", "supply_condition_pct", "mead_min_ft", "tier3_years",
) + tuple(f"kge_{n}" for n in HEADLINE_SERIES) + ("kge_lb_agent_request_median",)
# The executed feasibility rates are 0 by construction in strict, placebo and
# silent, so they are compared only in the pairs that include disabled.
EXEC_PAIRED_ARM = "disabled"
SUMMARY_METRICS = (
    "ibr_pct", "ibr_tr1_pct", "ibr_tr3_pct", "ibr_final_label_pct", "ibr_final_label_tr1_pct",
    "ibr_final_label_tr3_pct", "relabel_rate_pct",
    "exec_supply_pct", "exec_cap_pct", "exec_floor_pct", "exec_total_pct",
    "supply_condition_pct", "supply_condition_ub_pct", "supply_condition_lb_pct",
    "supply_live_blocked_decisions", "mead_min_ft", "mead_min_jan1_year", "tier0_years",
    "tier1_years", "tier2_years", "tier3_years", "mead_dead_pool_count", "powell_dead_pool_count",
    "powell_min_maf", "powell_min_jan1_year",
) + tuple(f"kge_{n}" for n in HEADLINE_SERIES) + (
    "kge_lb_agent_request_median", "kge_lb_agent_constant_sim", "kge_lb_agent_undefined",
    "r4_spells", "r4_recovered", "r4_censored", "r4_median_recovery_years",
)


@dataclass
class MetricsResult:
    provenance: Dict[str, Any]
    per_run: List[Dict[str, Any]]
    fql_per_seed: List[Dict[str, Any]]
    replays: List[Dict[str, Any]]
    arm_summary: List[Dict[str, Any]]
    paired: List[Dict[str, Any]]
    feasibility_vs_ranges: List[Dict[str, Any]]
    census: List[Dict[str, Any]]
    exposure: List[Dict[str, Any]]
    agreement: List[Dict[str, Any]]
    kge_rows: List[Dict[str, Any]]
    benchmark_rows: List[Dict[str, Any]]
    benchmark_summary: List[Dict[str, Any]]
    recovery: List[Dict[str, Any]]
    recovery_summary: List[Dict[str, Any]]
    lb_agent_rows: List[Dict[str, Any]]
    lb_agent_ceilings: List[Dict[str, Any]]
    r5a: List[Dict[str, Any]]
    r5a_summary: List[Dict[str, Any]]
    r5b: List[Dict[str, Any]]
    r5b_summary: List[Dict[str, Any]]
    r5c: List[Dict[str, Any]]
    r5c_summary: List[Dict[str, Any]]
    r5d: List[Dict[str, Any]]
    r5d_summary: List[Dict[str, Any]]
    r5d_little_spare: List[Dict[str, Any]]
    r5d_little_spare_summary: List[Dict[str, Any]]
    notes: List[str]


def _replay_infos(replay_dir: Optional[Path]) -> List[RunInfo]:
    if replay_dir is None:
        return []
    infos = [read_run_info(Path(replay_dir) / kind) for kind in ("A", "B")]
    for info in infos:
        if info.kind != "replay":
            raise MetricsError(f"{info.path}: not a replay directory")
    return infos


def _infos_of(paths: Sequence[str], kind: str) -> List[RunInfo]:
    infos = [read_run_info(p) for p in expand_run_dirs(paths)]
    wrong = [str(i.path) for i in infos if i.kind != kind]
    if wrong:
        raise MetricsError(f"expected {kind} runs, got other runs: {wrong}")
    return infos


SERIES_LABELS = {
    "mead_jan1_ft": "Lake Mead 1 January elevation",
    "total_request_maf": "UB+LB request TOTAL (aggregate use; item 30 headline)",
    "total_delivered_maf": "UB+LB delivered TOTAL (aggregate use; item 30 headline)",
    "ub_request_maf": "UB request total",
    "lb_request_maf": "LB request TOTAL (sum over the LB agents; item 30 benchmark)",
    "ub_delivered_maf": "UB delivered total",
    "lb_delivered_maf": "LB delivered total",
}


def series_label(name: str) -> str:
    if name in SERIES_LABELS:
        return SERIES_LABELS[name]
    if name.startswith(LB_AGENT_PREFIX):
        return f"LB agent {name[len(LB_AGENT_PREFIX):]} request"
    for prefix, what in zip(SUBBASIN_PREFIXES, ("request", "delivered")):
        if name.startswith(prefix):
            return f"UB sub-basin {name[len(prefix):]} {what} total"
    return name


def lb_agent_ceilings(bench: Mapping[int, Mapping[str, Kge]]) -> Dict[str, Dict[str, Any]]:
    """Item 30: each LB agent's OWN FQL-versus-FQL ceiling, the median across
    FQL seeds of that agent's request KGE against the mean of the other
    seeds (agents whose KGE is undefined in every seed have no ceiling)."""
    if not bench:
        return {}
    names = sorted(n for n in next(iter(bench.values())) if n.startswith(LB_AGENT_PREFIX))
    out: Dict[str, Dict[str, Any]] = {}
    for name in names:
        values = [bench[s][name].kge for s in bench if bench[s][name].kge is not None]
        out[name[len(LB_AGENT_PREFIX):]] = {"ceiling": _median(values), "seeds_defined": len(values),
                                            "seeds": len(bench)}
    return out


def benchmark_tables(reference: Reference) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]],
                                                    Dict[int, Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    """FQL against FQL: each seed's KGE against the mean of the other seeds.
    Returns per-seed rows, a per-series summary (median and range across
    seeds; for ``lb_request_maf`` this median is the item 30 benchmark of the
    LB request TOTAL, not a per-agent figure), per-seed headline scalars and
    each LB agent's own ceiling (``lb_agent_ceilings``)."""
    bench = reference_benchmark(reference)
    rows: List[Dict[str, Any]] = []
    per_seed: Dict[int, Dict[str, Any]] = {}
    for seed, kges in bench.items():
        rows.extend(_kge_rows(f"fql_seed{seed}", "fql_vs_other_seeds", kges))
        per_seed[seed] = {f"bench_kge_{n}": kges[n].kge for n in HEADLINE_SERIES}
    summary: List[Dict[str, Any]] = []
    if bench:
        names = sorted(next(iter(bench.values())))
        for name in names:
            values = [bench[s][name].kge for s in bench if bench[s][name].kge is not None]
            summary.append({"series": name, "label": series_label(name), "seeds": len(bench),
                            "defined": len(values), "median": _median(values),
                            "min": min(values) if values else None, "max": max(values) if values else None})
    return rows, summary, per_seed, lb_agent_ceilings(bench)


def compute_metrics(run_dirs: Sequence[str], fql_dirs: Sequence[str], replay_dir: Optional[str] = None,
                    allow_mixed_provenance: bool = False, allow_dirty: bool = False) -> MetricsResult:
    """Every WP6 metric over a corpus of LLM runs, read against the FQL
    reference (and the fixed-demand replays, when given)."""
    assert_thinking_rules_match_config()
    assert_short_year_window_matches_config()
    cfg = analysis_config()
    llm_infos = _infos_of(run_dirs, "llm")
    fql_infos = _infos_of(fql_dirs, "fql")
    replay_infos = _replay_infos(Path(replay_dir) if replay_dir else None)
    provenance = check_provenance(llm_infos + fql_infos + replay_infos, allow_mixed_provenance, allow_dirty)
    notes: List[str] = []

    fql_runs = [load_run(i.path, info=i) for i in fql_infos]
    reference = build_reference(fql_runs)
    benchmark_rows, benchmark_summary, bench_per_seed, ceilings = benchmark_tables(reference)
    if len(reference.seeds) < 2:
        notes.append("Only one FQL seed: the FQL-against-FQL benchmark is not computable.")
    lb_agent_ceiling_rows = [{"agent": agent, **c} for agent, c in sorted(ceilings.items())]

    kge_rows: List[Dict[str, Any]] = []
    recovery: List[Dict[str, Any]] = []
    fql_per_seed = []
    for run in fql_runs:
        seed_row = {"run": run.label, "seed": run.info.seed, **reservoir_outcomes(run.sim, cfg)}
        seed_row.update(bench_per_seed.get(run.info.seed, {}))
        episodes = drought_recovery(run.sim, cfg, run.label, "fql")
        recovery.extend(episodes)
        seed_row.update(recovery_summary(episodes))
        fql_per_seed.append(seed_row)

    replays = []
    for info in replay_infos:
        run = load_run(info.path, info=info)
        kges = kge_against_reference(system_series(run.sim), reference, run.label)
        kge_rows.extend(_kge_rows(run.label, "replay", kges))
        condition = replay_supply_condition(run)
        lb = lb_agent_summary(kges)
        convention = [f"kge_{n}" for n in HEADLINE_SERIES if kges[n].note == CONSTANT_SIM_NOTE]
        if lb["constant_sim"]:
            convention.append("kge_lb_agent_request_median")
        replays.append({"run": run.label, **{f"kge_{n}": kges[n].kge for n in HEADLINE_SERIES},
                        "kge_lb_agent_request_median": lb["median"],
                        "kge_convention_series": convention,
                        "kge_note": REPLAY_CONVENTION_NOTE if convention else "",
                        "supply_condition_ub_agent_years": condition["upper_basin"],
                        "supply_condition_lb_agent_years": condition["lower_basin"],
                        "agent_years": condition["agent_years"],
                        **reservoir_outcomes(run.sim, cfg)})
    if not replay_infos:
        notes.append("No replay directory given: the KGE floor and ceiling (replays A and B) are not reported.")

    per_run, census, exposure, agreement, lb_agent_rows = [], [], [], [], []
    r5a, r5b, r5c, r5d, r5d_little_spare = [], [], [], [], []
    for info in sorted(llm_infos, key=lambda i: (ARMS.index(i.arm), i.seed)):
        run = load_run(info.path, info=info)
        result = run_metrics(run, reference, cfg)
        per_run.append(result["row"])
        census.extend(result["census"])
        exposure.extend(result["exposure"])
        for rule, tally in result["agreement"].items():
            agreement.append({"run": run.label, "arm": info.arm, "seed": info.seed, "rule": rule,
                              "attempts": tally["attempts"], "predicate": tally["predicate"],
                              "live": tally["live"], "disagreements": tally["disagreements"],
                              "examples": " | ".join(tally["examples"])})
        kge_rows.extend(_kge_rows(run.label, "llm", result["kge"]))
        for name, k in sorted(result["kge"].items()):
            if name.startswith(LB_AGENT_PREFIX):
                agent = name[len(LB_AGENT_PREFIX):]
                own = ceilings.get(agent, {})
                lb_agent_rows.append({"run": run.label, "arm": info.arm, "seed": info.seed, "agent": agent,
                                      "kge": k.kge, "note": k.note, "ceiling": own.get("ceiling"),
                                      "ceiling_seeds_defined": own.get("seeds_defined")})
        recovery.extend(result["recovery"])
        r5a.extend(r5a_wsa_by_band(run))
        r5b.extend(r5b_wsa_by_short_years(run))
        r5c.extend(r5c_wsa_by_spell_year(run, cfg))
        r5d.extend(r5d_rows(run))
        r5d_little_spare.append(r5d_ub_little_spare(run, cfg))
        del run

    arm_summary = []
    for arm in ARMS:
        rows = [r for r in per_run if r["arm"] == arm]
        if not rows:
            continue
        for metric in SUMMARY_METRICS:
            arm_summary.append({"arm": arm, "metric": metric, **describe([r.get(metric) for r in rows])})
    for metric in SUMMARY_METRICS:
        key = metric.replace("kge_", "bench_kge_") if metric.startswith("kge_") else metric
        values = [r.get(key) for r in fql_per_seed if key in r]
        if values:
            arm_summary.append({"arm": "fql", "metric": metric, **describe(values)})

    paired = []
    for first, second in PAIRED_COMPARISONS:
        a = {r["seed"]: r for r in per_run if r["arm"] == first}
        b = {r["seed"]: r for r in per_run if r["arm"] == second}
        seeds = sorted(set(a) & set(b))
        if not seeds:
            continue
        for metric in PAIRED_METRICS:
            if metric.startswith("exec_") and EXEC_PAIRED_ARM not in (first, second):
                continue  # 0 on both sides by construction
            pairs = [s for s in seeds if a[s].get(metric) is not None and b[s].get(metric) is not None]
            test = sign_flip_test([a[s][metric] - b[s][metric] for s in pairs])
            row = {"comparison": f"{first} - {second}", "metric": metric,
                   "seeds": " ".join(str(s) for s in pairs), **test}
            if metric == "kge_lb_agent_request_median":
                # Beside the median: per paired seed, the agents scored by the
                # constant-series convention and the agents without a KGE.
                for side, rows_by_seed in (("first", a), ("second", b)):
                    for count in ("constant_sim", "undefined"):
                        row[f"lb_agents_{count}_{side}"] = " ".join(
                            str(rows_by_seed[s][f"kge_lb_agent_{count}"]) for s in pairs)
            paired.append(row)

    feasibility = []
    ranges = {arm: {m: describe([r.get(m) for r in per_run if r["arm"] == arm]) for m in SUMMARY_METRICS}
              for arm in ("strict", "disabled")}
    for r in per_run:
        if r["arm"] != "feasibility_only":
            continue
        for metric in SUMMARY_METRICS:
            value = r.get(metric)
            entry = {"run": r["run"], "metric": metric, "value": value}
            for arm in ("strict", "disabled"):
                d = ranges[arm][metric]
                entry[f"{arm}_n"] = d["n"]
                entry[f"{arm}_min"] = d["min"]
                entry[f"{arm}_max"] = d["max"]
                entry[f"within_{arm}_range"] = (None if value is None or d["n"] == 0
                                                else d["min"] <= value <= d["max"])
            feasibility.append(entry)

    groups = [a for a in ARMS if any(r["arm"] == a for r in per_run)] + (["fql"] if fql_runs else [])
    llm_arms = [a for a in groups if a != "fql"]
    r5a_summary = r5a_band_summary(r5a, llm_arms)
    r5b_summary = r5b_summary_table(r5b)
    r5c_summary = r5c_summary_table(r5c)
    r5d_summary = r5d_summary_table(r5d)
    r5d_little_spare_summary_rows = r5d_ub_little_spare_summary(r5d_little_spare)
    return MetricsResult(provenance, per_run, fql_per_seed, replays, arm_summary, paired, feasibility,
                         census, exposure, agreement, kge_rows, benchmark_rows, benchmark_summary,
                         recovery, recovery_table(recovery, groups), lb_agent_rows, lb_agent_ceiling_rows,
                         r5a, r5a_summary, r5b, r5b_summary, r5c, r5c_summary, r5d, r5d_summary,
                         r5d_little_spare, r5d_little_spare_summary_rows,
                         notes)


# =============================================================================
# P5: invented text. (a) banned phrases, (b) every number against the log
# =============================================================================

_DIGIT = re.compile(r"\d")
_R = {
    "persona": re.compile(r"^You are (?P<agent>.+?), an agricultural water user .*?holding a water right of "
                          r"(?P<w>[\d,]+) acre-ft/year\."),
    "year": re.compile(r"^It is now the year (\d{4})\. You (use|divert) water in the (Upper|Lower) Colorado River Basin\.$"),
    "precip": re.compile(r"^Winter precipitation (in your sub-basin|averaged over the Upper Basin) this year was "
                         r"(\d+) mm \((above|below) last year\)\.$"),
    "flow_share": re.compile(r"^The natural flow of the rivers your sub-basin draws on is (\d+%) of its "
                             r"(1971-2018) average this year\.$"),
    "nf": re.compile(r"^Natural flow on the river this year is forecast at ([\d.]+) million acre-ft\.$"),
    "powell": re.compile(r"^Lake Powell holds ([\d.]+) million acre-ft on 1 January\.$"),
    "mead": re.compile(r"^Lake Mead was at ([\d,]+) feet above sea level on 1 January \((rising|declining) from last year\)\.$"),
    "tier": re.compile(r"^A Tier (\d) Lower Basin shortage applies this year \(Lake Mead was below ([\d,]+) feet on 1 January\): "),
    "tier_volume": re.compile(r"by ([\d,]+) acre-ft in total"),
    "senior": re.compile(r"above ([\d,]+) acre-ft by about"),
    "about_pct": re.compile(r"by about (\d+%)"),
    "capacity": re.compile(r"limited to the ([\d.]+) million acre-ft delivery capacity"),
    "last_year": re.compile(r"^Last year you requested ([\d,]+) acre-ft and received ([\d,]+) acre-ft \(([\d.]+%) delivered\)"),
    "first_year": re.compile(r"^In (\d{4}) you (used|diverted) ([\d,]+) acre-ft\.$"),
    "expect_full": re.compile(r"^If you request the ([\d,]+) acre-ft you received last year, you can expect full delivery this year\.$"),
    "expect_short": re.compile(r"^If you request the ([\d,]+) acre-ft you received last year, you can expect ([\d,]+) acre-ft "
                               r"\(([\d.]+%)\) this year, because "),
    "right": re.compile(r"^Your water right is ([\d,]+) acre-ft/year; last year's delivery was (\d+%) of it\.$"),
    "dash_row": re.compile(r"^\s*(\d{4}) \|\s+([\d,]+) \|\s+([\d,]+)\s*$"),
    "dash_warn": re.compile(r"^WARNING: You requested ([\d,]+) AF and received ([\d,]+) AF \(([\d.]+)% unmet\)\."),
    "reflection": re.compile(r"^- Consolidated Reflection \(written in (\d{4})\): (.*)$"),
    "memory": re.compile(r"^- Year (\d{4}): "),
    "mem_chose": re.compile(r"You chose to (increase|maintain|decrease) demand(?: \(by (\d+)%\))?\."),
    "mem_applied": re.compile(r"^- Year \d{4}: (?:no valid decision was read; |no valid proposal was made; "
                              r"|your proposal to (?:increase|maintain|decrease) demand was rejected; )?"
                              r"(increase|maintain|decrease) demand was applied"),
    "mem_no_decision": re.compile(r"^- Year \d{4}: no valid decision was read; your request stayed at the "
                                  r"amount you received the year before\."),
    "mem_req": re.compile(r"You requested ([\d,]+) acre-ft and received ([\d,]+) acre-ft\."),
    "mem_short": re.compile(r"Shortfall: ([\d,]+) acre-ft \(([\d.]+)% unmet\)"),
    "mem_ub_trend": re.compile(r"That winter's precipitation (?:in your sub-basin|in the Upper Basin) was "
                               r"(above|below) the previous winter's\."),
    "mem_lb_trend": re.compile(r"On 1 January that year Lake Mead was (higher|lower) than a year earlier\."),
    "opt_inc": re.compile(r"^(\d+)\. Increase your request to about ([\d,]+) acre-ft: the ([\d,]+) acre-ft you received "
                          r"last year plus your typical step of about ([\d,]+) acre-ft"
                          r"(?: \(your water right stops it at ([\d,]+) acre-ft\))?\.$"),
    "opt_keep": re.compile(r"^(\d+)\. Keep your request at ([\d,]+) acre-ft, the amount you received last year\.$"),
    "opt_dec": re.compile(r"^(\d+)\. Decrease your request to about ([\d,]+) acre-ft: the ([\d,]+) acre-ft you received "
                          r"last year minus your typical step of about ([\d,]+) acre-ft"
                          r"(?: \(the minimum-use floor stops it at ([\d,]+) acre-ft\))?\.$"),
    "choices_a": re.compile(r'"decision" MUST be the NUMERIC ID \(([^)]*)\) from the options list'),
    "choices_b": re.compile(r'choose ONE from: ([^>"]*)>'),
}
NO_TIER_SENTENCE = "No Lower Basin shortage applies this year."
POWELL_DEAD_POOL_SENTENCE = "Lake Powell is at its dead-pool floor on 1 January; releases are limited to inflow."


def _f0(x: float) -> str:
    return f"{x:,.0f}"


def _choices_text(n: int) -> str:
    """The decision-id list of a menu of n options, as the context builder
    writes it (broker/components/context/tiered.py, valid_choices_text)."""
    ids = [str(i + 1) for i in range(n)]
    return ", ".join(ids[:-1]) + ", or " + ids[-1] if n > 1 else ids[0]


def static_fragments(config_path: Path = CONFIG_PATH, template_path: Path = PROMPT_TEMPLATE_PATH) -> List[str]:
    """Template text that carries digits but no logged value: the literal
    template lines and the response-format field texts of the YAML."""
    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    shared = raw.get("shared", {})
    fragments: List[str] = []
    for f in shared.get("response_format", {}).get("fields", []):
        for key in ("description", "reason_hint"):
            text = f.get(key)
            if isinstance(text, str) and _DIGIT.search(text):
                fragments.append(text.strip())
    for line in Path(template_path).read_text(encoding="utf-8").splitlines():
        if "{" not in line and _DIGIT.search(line):
            fragments.append(line.strip())
    for line in str(shared.get("rating_scale", "")).splitlines():
        if _DIGIT.search(line):
            fragments.append(line.strip())
    return fragments


_RETRY_ORIGINAL_PROMPT = "<the first-attempt prompt, scanned with the prompts>"


class _FeasibleLineInputs:
    """The engine attributes ``RetryMixin._format_feasible_line`` reads: the
    step's skill map, the retry-exhaustion policy and the skill registry."""

    def __init__(self, skill_map: Dict[str, str], on_retry_exhausted: str, registry: Any):
        self._skill_map, self._on_retry_exhausted, self.skill_registry = skill_map, on_retry_exhausted, registry

    def _step_skill_map(self, agent_type: str, context: Dict) -> Dict[str, str]:
        return self._skill_map


def retry_text_samples(config_path: Path = CONFIG_PATH,
                       registry_path: Path = SKILL_REGISTRY_PATH) -> Dict[str, str]:
    """P5(a) for the retry prompts, which the runs do not log: the retry
    wrapper and the feasible-action lines, rendered by the broker's own code
    (``render_intervention_prompt``, ``RetryMixin._format_feasible_line``)
    with this domain's settings from the config (framing, placebo closer,
    plain action names, reports per retry, retry-exhaustion policy, and the
    registry's default skill). The reports carry every thinking and identity
    rule message and suggestion of every profile in the config. Not here:
    the first-attempt prompt a retry repeats (scanned with the prompts) and
    the supply rule's text, built per decision (scanned from the logged
    ``error_messages``)."""
    from broker.components.governance.registry import SkillRegistry
    from broker.core._advise import render_intervention_prompt
    from broker.core._retry_loop import RetryMixin
    from broker.interfaces.skill_types import InterventionReport
    from broker.utils.agent_config import AgentTypeConfig
    from broker.utils.parsing import get_adapter

    previous = AgentTypeConfig._instance  # loading a config must not repoint the process-wide handle
    try:
        config = AgentTypeConfig.load(str(config_path))
        adapter = get_adapter("mock", config_path=str(config_path))
        framing = config.get_governance_intervention_framing()
        closer = config.get_governance_placebo_closer()
        plain = config.get_governance_plain_action_names()
        max_reports = config.get_governance_max_reports()
        on_exhausted = config.get_governance_on_retry_exhausted()
    finally:
        AgentTypeConfig._instance = previous
    registry = SkillRegistry()
    registry.register_from_yaml(str(registry_path))

    raw = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    reports: List[Any] = []
    seen: Set[Tuple[str, str]] = set()
    for profile in raw[AGENT_TYPE]["governance"].values():
        if not isinstance(profile, dict):
            continue
        for rule in list(profile.get("thinking_rules") or []) + list(profile.get("identity_rules") or []):
            for skill in rule.get("blocked_skills") or []:
                if (rule["id"], skill) in seen:
                    continue
                seen.add((rule["id"], skill))
                reports.append(InterventionReport(
                    rule_id=rule["id"], blocked_skill=skill.replace("_", " ") if plain else skill,
                    violation_summary=str(rule.get("message", "")),
                    suggested_correction=rule.get("suggestion"), severity="ERROR"))

    def wrapper(**kwargs: Any) -> str:
        text, _shown = render_intervention_prompt(adapter, _RETRY_ORIGINAL_PROMPT, reports,
                                                  framing=framing, **kwargs)
        return text.replace(_RETRY_ORIGINAL_PROMPT, "")

    samples = {
        "full retry, every configured rule report": wrapper(max_reports=None),
        "full retry, reports truncated": wrapper(max_reports=max_reports),
        "placebo retry": wrapper(max_reports=max_reports, include_reports=False,
                                 **({} if closer is None else {"closer": closer})),
    }
    for menu in ((INCREASE, KEEP, DECREASE), (KEEP, DECREASE), (INCREASE, KEEP)):
        inputs = _FeasibleLineInputs({str(i + 1): s for i, s in enumerate(menu)}, on_exhausted, registry)
        for k in range(len(menu) + 1):
            for passing in itertools.combinations(menu, k):
                for missing in ((False,) if passing else (False, True)):
                    name = (f"feasible line, menu {'/'.join(menu)}, passing {'/'.join(passing) or 'none'}"
                            + (", a required field missing" if missing else ""))
                    samples[name] = RetryMixin._format_feasible_line(
                        inputs, list(passing), AGENT_TYPE, {}, missing_fields=missing)
    return samples


def banned_phrase_hits(texts: Mapping[str, str]) -> Tuple[Dict[str, int], List[str]]:
    """P5(a) on named texts: hits per banned phrase, and where."""
    hits: Dict[str, int] = defaultdict(int)
    where: List[str] = []
    for name, text in texts.items():
        for phrase in P5_BANNED_PHRASES:
            if phrase in text:
                hits[phrase] += 1
                where.append(f"{name}: {phrase!r}")
    return dict(hits), where


@dataclass
class PromptAudit:
    prompts: int = 0
    numeric_lines: int = 0
    mismatches: List[str] = field(default_factory=list)
    unchecked: List[str] = field(default_factory=list)
    reflection_lines: int = 0
    banned_hits: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    banned_hits_in_reflections: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    banned_examples: List[str] = field(default_factory=list)


class _Line:
    """One prompt line. Spans verified against the log are recorded; a digit
    outside every verified span is an unchecked number."""

    def __init__(self, text: str, where: str, audit: PromptAudit):
        self.text, self.where, self.audit = text, where, audit
        self.spans: List[Tuple[int, int]] = []

    def cover(self, m: "re.Match[str]", group: Any = 0) -> None:
        if m.group(group) is not None:
            self.spans.append(m.span(group))

    def expect(self, m: "re.Match[str]", group: Any, expected: str, what: str) -> None:
        self.cover(m, group)
        if m.group(group) != expected:
            self.audit.mismatches.append(f"{self.where}: {what}: prompt {m.group(group)!r}, log {expected!r}")

    def check(self, ok: bool, what: str) -> None:
        if not ok:
            self.audit.mismatches.append(f"{self.where}: {what}")

    def finish(self) -> None:
        covered = [False] * len(self.text)
        for a, b in self.spans:
            for i in range(a, b):
                covered[i] = True
        if any(ch.isdigit() and not covered[i] for i, ch in enumerate(self.text)):
            self.audit.unchecked.append(f"{self.where}: {self.text.strip()[:200]}")


class PromptChecker:
    """P5(b): every number in a first-attempt prompt matches the run's logs
    (simulation_log.csv and the audit's logged supply-rule inputs), the v3
    sentences of irrigation_personas (spec 4.1 to 4.5) read back line by
    line. Sub-basin flow shares and senior entitlements are compared with the
    pinned data tables the environment reads. Reflection text is the model's
    own and is checked by P6 instead."""

    def __init__(self, run: LoadedRun, cfg: WaterSystemConfig, variant: str):
        self.run, self.cfg, self.variant = run, cfg, variant
        self.fragments = static_fragments()
        self.priority = _load_lb_priority_split_table()

    def flow_share(self, subbasin: str, sim_year: int) -> float:
        q = _load_ub_subbasin_supply_table(self.variant)[sim_year][f"q_{subbasin}_af"]
        return q / _load_ub_subbasin_variant_means()[self.variant][subbasin]

    def senior_entitlement(self, agent: str) -> Optional[float]:
        entry = self.priority.get(agent)
        return None if entry is None else entry["senior_entitlement_af"]

    def _mead(self, year: int) -> float:
        return self.run.sim.system[year]["lake_mead_level"] if year >= 1 else MEAD_JAN1_2018_FT

    def _reason(self, line: _Line, frac: Optional[float]) -> None:
        for m in _R["about_pct"].finditer(line.text):
            line.expect(m, 1, f"{frac:.0%}" if frac is not None else "(no fraction logged)", "junior-priority cut share")
        for m in _R["capacity"].finditer(line.text):
            line.expect(m, 1, f"{self.cfg.ub_infrastructure_cap_maf:.1f}", "Upper Basin delivery capacity")

    def audit(self, key: Tuple[str, int], prompt: str, out: PromptAudit) -> None:
        run, sim, cfg = self.run, self.run.sim, self.cfg
        agent, t = key
        d = run.decisions[key]
        trace = run.traces[key]
        year = sim.sim_year(t)
        upper = sim.basin[agent] == "upper_basin"
        system = sim.system[t]
        w = sim.num(agent, t, "water_right")
        base = d.keep_request_af
        out.prompts += 1
        for i, raw in enumerate(prompt.split("\n")):
            text = raw.rstrip()
            where = f"{run.label} {agent} {year} line {i}"
            stripped = text.strip()
            for phrase in P5_BANNED_PHRASES:
                if phrase in text:
                    out.banned_hits[phrase] += 1
                    if stripped.startswith("- Consolidated Reflection"):
                        out.banned_hits_in_reflections[phrase] += 1
                    if len(out.banned_examples) < 10:
                        out.banned_examples.append(f"{where}: {phrase!r}")
            if stripped == NO_TIER_SENTENCE:
                if upper or int(system["shortage_tier"]) != 0:
                    out.mismatches.append(f"{where}: no-shortage sentence, tier {int(system['shortage_tier'])}")
            if stripped == POWELL_DEAD_POOL_SENTENCE:
                if system["powell_storage_maf"] > cfg.powell_dead_pool_maf + DEAD_POOL_TOL_MAF:
                    out.mismatches.append(f"{where}: Powell dead-pool sentence above the dead pool")
            if not _DIGIT.search(text):
                continue
            out.numeric_lines += 1
            line = _Line(text, where, out)
            self._line(line, agent, t, year, upper, system, w, base, d, trace, out)
            for fragment in self.fragments:
                start = text.find(fragment)
                while start >= 0:
                    line.spans.append((start, start + len(fragment)))
                    start = text.find(fragment, start + 1)
            line.finish()

    def _line(self, line: _Line, agent: str, t: int, year: int, upper: bool, system: Mapping[str, float],
              w: float, base: float, d: Decision, trace: TraceRecord, out: PromptAudit) -> None:
        """Verify one digit-bearing line. Each handler checks every number its
        sentence carries and then covers the sentence's whole match (its
        literal text is the builder's, e.g. "on 1 January"). Wildcards (the
        persona text, a reason phrase) are never covered: a digit there is
        unchecked unless a sub-pattern verifies it."""
        sim, cfg, text = self.run.sim, self.cfg, line.text
        m = _R["persona"].match(text)
        if m:
            line.cover(m, "agent")
            line.check(m.group("agent") == agent, f"persona names {m.group('agent')!r}")
            line.expect(m, "w", _f0(w), "persona water right")
            return
        m = _R["year"].match(text)
        if m:
            line.expect(m, 1, str(year), "year")
            line.check((m.group(2) == "use") == upper and (m.group(3) == "Upper") == upper, "basin wording")
            line.cover(m)
            return
        m = _R["precip"].match(text)
        if m:
            p = sim.opt_num(agent, t, "precipitation_mm")
            flag = sim.opt_num(agent, t, "precipitation_flag")
            line.check(upper and p is not None and flag is not None, "precipitation line without a logged value")
            line.expect(m, 2, f"{p:.0f}" if p is not None else "(none)", "winter precipitation")
            line.check((m.group(3) == "above") == (flag == 1), "precipitation above/below")
            line.check((m.group(1) == "in your sub-basin") == (sim.subbasin[agent] is not None), "precipitation scope")
            line.cover(m)
            return
        m = _R["flow_share"].match(text)
        if m:
            sb = sim.subbasin[agent]
            if sb is None:
                line.check(False, "sub-basin flow line for an agent without a sub-basin")
            else:
                line.expect(m, 1, f"{self.flow_share(sb, year):.0%}", "sub-basin flow share")
            line.cover(m)
            return
        m = _R["nf"].match(text)
        if m:
            line.expect(m, 1, f"{system['natural_flow_maf']:.1f}", "natural flow")
            line.cover(m)
            return
        m = _R["powell"].match(text)
        if m:
            line.expect(m, 1, f"{system['powell_storage_maf']:.1f}", "Lake Powell storage")
            line.check(system["powell_storage_maf"] > cfg.powell_dead_pool_maf + DEAD_POOL_TOL_MAF,
                       "Powell storage stated at the dead pool")
            line.cover(m)
            return
        m = _R["mead"].match(text)
        if m:
            level_now = system["lake_mead_level"]
            line.expect(m, 1, _f0(level_now), "Lake Mead level")
            line.check((m.group(2) == "rising") == (level_now >= self._mead(t - 1)), "Lake Mead rising/declining")
            line.cover(m)
            return
        m = _R["tier"].match(text)
        if m:
            tier = int(system["shortage_tier"])
            line.expect(m, 1, str(tier), "declared tier")
            threshold = {1: cfg.mead_shortage_tier1, 2: cfg.mead_shortage_tier2,
                         3: cfg.mead_shortage_tier3}.get(int(m.group(1)))
            line.expect(m, 2, _f0(threshold) if threshold is not None else "(none)", "tier threshold")
            line.cover(m)
            for mv in _R["tier_volume"].finditer(text):
                line.expect(mv, 1, _f0(system["lb_shortage_volume_maf"] * 1e6), "declared shortage volume")
                line.cover(mv)
            for ms in _R["senior"].finditer(text):
                senior = self.senior_entitlement(agent)
                line.expect(ms, 1, _f0(senior) if senior is not None else "(none)", "senior entitlement")
                line.cover(ms)
            self._reason(line, sim.opt_num(agent, t, "lb_junior_tier_cut_fraction"))
            return
        m = _R["last_year"].match(text)
        if m:
            line.cover(m)
            if t == 1:
                line.check(False, "last-year sentence in the first year")
                return
            req, dlv = sim.num(agent, t - 1, "request"), sim.num(agent, t - 1, "diversion")
            line.expect(m, 1, _f0(req), "last year's request")
            line.expect(m, 2, _f0(dlv), "last year's delivery")
            line.expect(m, 3, format_share(supply_ratio(dlv, req)), "last year's delivered share")
            self._reason(line, sim.opt_num(agent, t - 1, "lb_junior_tier_cut_fraction"))
            return
        m = _R["first_year"].match(text)
        if m:
            line.check(t == 1, "first-year sentence after the first year")
            line.expect(m, 1, str(year - 1), "the year before the run")
            line.check((m.group(2) == "used") == upper, "used/diverted wording")
            line.expect(m, 3, _f0(base), "2018 use")
            line.cover(m)
            return
        m = _R["expect_full"].match(text)
        if m:
            line.expect(m, 1, _f0(base), "keep request")
            line.check(d.supply_ratio >= FULL_SUPPLY_RATIO, "full delivery stated while r < FULL_SUPPLY_RATIO")
            line.cover(m)
            return
        m = _R["expect_short"].match(text)
        if m:
            line.expect(m, 1, _f0(base), "keep request")
            line.expect(m, 2, _f0(d.expected_at_keep_af), "expected delivery")
            line.expect(m, 3, format_share(d.supply_ratio), "expected share r")
            line.check(d.supply_ratio < FULL_SUPPLY_RATIO, "a shortfall stated while r >= FULL_SUPPLY_RATIO")
            line.cover(m)
            self._reason(line, sim.opt_num(agent, t, "lb_junior_tier_cut_fraction"))
            return
        m = _R["right"].match(text)
        if m:
            line.expect(m, 1, _f0(w), "water right")
            line.expect(m, 2, f"{base / w:.0%}" if w > 0 else "0%", "last delivery as a share of the right")
            line.cover(m)
            return
        m = _R["dash_row"].match(text)
        if m:
            tk = int(m.group(1)) - sim.sim_start_year + 1
            line.cover(m)
            if not 1 <= tk < t:
                line.check(False, f"dashboard row for {m.group(1)}")
                return
            line.expect(m, 2, _f0(sim.num(agent, tk, "request")), "dashboard request")
            line.expect(m, 3, _f0(sim.num(agent, tk, "diversion")), "dashboard supply")
            return
        m = _R["dash_warn"].match(text)
        if m:
            line.cover(m)
            if t == 1:
                line.check(False, "dashboard warning in the first year")
                return
            req, dlv = sim.num(agent, t - 1, "request"), sim.num(agent, t - 1, "diversion")
            line.expect(m, 1, _f0(req), "warning request")
            line.expect(m, 2, _f0(dlv), "warning supply")
            unmet = (1.0 - dlv / req) * 100.0 if req > 0 else 0.0
            line.expect(m, 3, f"{unmet:.1f}", "warning unmet share")
            return
        m = _R["reflection"].match(text)
        if m:
            line.cover(m)  # the model's own text: P6 checks it
            out.reflection_lines += 1
            return
        m = _R["memory"].match(text)
        if m:
            tk = int(m.group(1)) - sim.sim_start_year + 1
            line.cover(m)
            if not 1 <= tk < t:
                line.check(False, f"memory line for {m.group(1)}")
                return
            req, dlv = sim.num(agent, tk, "request"), sim.num(agent, tk, "diversion")
            past = f"memory line for {m.group(1)}"
            # The action the line states against what the audit says was
            # executed that year: "You chose to X" only for an approved
            # decision that executed X; "X was applied" only where a default
            # stood in for a blocked or unreadable answer.
            dk = self.run.decisions.get((agent, tk))
            executed = dk.executed_skill if dk else None
            path = dk.execution_path if dk else None
            mc = _R["mem_chose"].search(text)
            if mc:
                line.check(path == "approved" and executed == f"{mc.group(1)}_demand",
                           f"{past}: states 'You chose to {mc.group(1)} demand', the audit executed "
                           f"{executed!r} ({path})")
                if mc.group(2) is not None:
                    mag = sim.opt_num(agent, tk, "magnitude_pct")
                    line.expect(mc, 2, f"{mag:.0f}" if mag is not None else "(none)", f"{past}: realised change")
                line.cover(mc)
            ma = _R["mem_applied"].search(text)
            if ma:
                line.check(path in ("rejected_default", "rejected_proposal", "fallback")
                           and executed == f"{ma.group(1)}_demand",
                           f"{past}: states '{ma.group(1)} demand was applied', the audit executed "
                           f"{executed!r} ({path})")
            mn = _R["mem_no_decision"].search(text)
            if mn:
                # Nothing executed that year, so the request stayed at the base.
                base_k = sim.opt_num(agent, tk, "base_af")
                line.check(dk is not None and executed is None,
                           f"{past}: states that no valid decision was read, the audit executed "
                           f"{executed!r} ({path})")
                line.check(base_k is not None and abs(req - base_k) <= AF_TOL,
                           f"{past}: states that the request stayed at last year's receipt, the log has "
                           f"request {req} and base {base_k}")
            if not (mc or ma or mn):
                line.check(False, f"{past}: names no decision")
            mr = _R["mem_req"].search(text)
            if mr is None:
                line.check(False, f"{past}: no request sentence")
            else:
                line.expect(mr, 1, _f0(req), f"{past}: request")
                line.expect(mr, 2, _f0(dlv), f"{past}: delivery")
                line.cover(mr)
            share = supply_ratio(dlv, req)
            ms = _R["mem_short"].search(text)
            if ms:
                line.expect(ms, 1, _f0(max(0.0, req - dlv)), f"{past}: shortfall")
                line.expect(ms, 2, f"{(1.0 - share) * 100.0:.1f}", f"{past}: unmet share")
                line.cover(ms)
            line.check(("Demand fully met." in text) == (share >= FULL_SUPPLY_RATIO)
                       and (ms is not None) == (share < FULL_SUPPLY_RATIO), f"{past}: full/short wording")
            self._reason(line, sim.opt_num(agent, tk, "lb_junior_tier_cut_fraction"))
            if upper:
                mt = _R["mem_ub_trend"].search(text)
                flag = sim.opt_num(agent, tk, "precipitation_flag")
                line.check(mt is not None and flag is not None and (mt.group(1) == "above") == (flag == 1),
                           f"{past}: precipitation trend")
            else:
                mt = _R["mem_lb_trend"].search(text)
                line.check(mt is not None and (mt.group(1) == "higher") == (self._mead(tk) >= self._mead(tk - 1)),
                           f"{past}: Lake Mead trend")
            if mt is not None:
                line.cover(mt)
            return
        typical = sim.num(agent, t, "typical_step_af")
        b_r, s_r, w_r, f_r = round(base), round(typical), round(w), round(w * self.cfg.min_utilisation_fraction)
        m = _R["opt_inc"].match(text)
        if m:
            line.expect(m, 2, _f0(min(b_r + s_r, w_r)), "increase target")
            line.expect(m, 3, _f0(b_r), "increase base")
            line.expect(m, 4, _f0(s_r), "typical step")
            if b_r + s_r > w_r:
                line.check(m.group(5) is not None, "increase capped without the water-right clause")
                if m.group(5) is not None:
                    line.expect(m, 5, _f0(w_r), "water right in the increase option")
            else:
                line.check(m.group(5) is None, "water-right clause on an uncapped increase")
            line.cover(m)
            return
        m = _R["opt_keep"].match(text)
        if m:
            line.expect(m, 2, _f0(b_r), "keep request")
            line.cover(m)
            return
        m = _R["opt_dec"].match(text)
        if m:
            line.expect(m, 2, _f0(max(b_r - s_r, f_r)), "decrease target")
            line.expect(m, 3, _f0(b_r), "decrease base")
            line.expect(m, 4, _f0(s_r), "typical step")
            if b_r - s_r < f_r:
                line.check(m.group(5) is not None, "decrease floored without the floor clause")
                if m.group(5) is not None:
                    line.expect(m, 5, _f0(f_r), "floor in the decrease option")
            else:
                line.check(m.group(5) is None, "floor clause on an unfloored decrease")
            line.cover(m)
            return
        for name in ("choices_a", "choices_b"):
            for mc in _R[name].finditer(text):
                line.expect(mc, 1, _choices_text(len(trace.menu)), "decision ids")
                line.cover(mc)


def _memory_block(prompt: str) -> List[str]:
    """The memory lines of a prompt: the "- " lines right after "Your memory includes:"."""
    lines = prompt.split("\n")
    out: List[str] = []
    for i, line in enumerate(lines):
        if line.strip() == "Your memory includes:":
            for nxt in lines[i + 1:]:
                if not nxt.startswith("- "):
                    break
                out.append(nxt[2:])
            break
    return out


def reflection_checks(run: LoadedRun) -> Dict[str, Any]:
    """P6: stored reflections quoting a figure absent from the memory they
    were written from (the non-reflection memory lines of the agent's
    prompt in the year the reflection was written, the input
    IrrigationLifecycleHooks._batch_reflect retrieves; the runner's own
    _foreign_figures rule); prompts with more than one reflection line;
    reflection lines not written in the previous calendar year."""
    from examples.irrigation_abm.run_experiment import _REFLECTION_MEMORY_PREFIX, _foreign_figures

    memories = {key: _memory_block(trace.prompt or "") for key, trace in run.traces.items()}
    if any(trace.prompt is None and not trace.crashed for trace in run.traces.values()):
        raise MetricsError(f"{run.label}: reflection checks need the prompts (keep_prompts)")
    unknown_source = 0  # the prompt a reflection was written from is an ABORTED_EXCEPTION step's
    pattern = re.compile(r"^" + re.escape(_REFLECTION_MEMORY_PREFIX) + r" \(written in (\d{4})\): (.*)$")
    foreign = multiple = wrong_year = reflections = 0
    examples: List[str] = []
    for (agent, t), lines in memories.items():
        found = [pattern.match(line) for line in lines if line.startswith(_REFLECTION_MEMORY_PREFIX)]
        if any(m is None for m in found):
            raise MetricsError(f"{run.label} {agent} {t}: a reflection line has no 'written in' year")
        reflections += len(found)
        if len(found) > 1:
            multiple += 1
        year = run.sim.sim_year(t)
        for m in found:
            if int(m.group(1)) != year - 1:
                wrong_year += 1
                if len(examples) < 10:
                    examples.append(f"{agent} {year}: written in {m.group(1)}")
            source = run.traces.get((agent, t - 1))
            if source is not None and source.crashed:
                unknown_source += 1  # no prompt to compare with: reported, not judged
                continue
            own = [line for line in memories.get((agent, t - 1), []) if not line.startswith(_REFLECTION_MEMORY_PREFIX)]
            bad = _foreign_figures(m.group(2), " ".join(own))
            if bad:
                foreign += 1
                if len(examples) < 10:
                    examples.append(f"{agent} {year}: figures {bad} not in its memory")
    return {"reflection_lines": reflections, "foreign_figure_reflections": foreign,
            "prompts_with_several_reflections": multiple, "reflections_not_from_previous_year": wrong_year,
            "reflections_with_no_source_prompt": unknown_source, "examples": examples}


# =============================================================================
# Pilot gate (spec section 4): P1-P10 and the reported R1-R4
# =============================================================================

def _check(check_id: str, title: str, gated: bool, passed: Optional[bool], reason: str,
           details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"id": check_id, "title": title, "gated": gated, "passed": passed, "reason": reason,
            "details": _jsonable(details or {})}


def gate_p1(runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    worst: Dict[str, float] = {}
    failures = []
    for run in runs:
        largest = 0.0
        for y in run.sim.years:
            s = run.sim.system[y]
            # Item 36e (lb_return_flow_fraction, 2026-10-06 CPU rerun
            # finding): "lb_return_flow_maf" is logged UNSCALED by phi
            # (irrigation_env.py's own field comment), so the amount
            # actually charged against Mead's outflow this year is
            # lb_delivered_maf minus lb_phys_ratio * lb_return_flow_maf,
            # not lb_delivered_maf alone -- the same correction
            # hindcast_v3.py's run_hindcast() already applies to its own
            # mass-balance assertion. Default lb_return_flow_fraction=0.0
            # makes lb_return_flow_maf (and this term) 0.0, so this is a
            # no-op, byte-identical to the pre-correction formula, for
            # every run at the v3 production default.
            lb_return_charged_maf = s["lb_phys_ratio"] * s["lb_return_flow_maf"]
            residual = ((s["powell_storage_end_maf"] - s["powell_storage_maf"])
                        + (s["mead_storage_end_maf"] - s["mead_storage_maf"])
                        - (s["natural_flow_maf"] - s["ub_non_farm_maf"] + s["lb_tributary_maf"]
                           - s["ub_delivered_maf"] - s["powell_evap_maf"] - s["mead_evap_maf"]
                           - (s["lb_delivered_maf"] - lb_return_charged_maf
                              + s["lb_non_ag_delivered_maf"] + s["mexico_delivered_maf"])
                           - s["mead_spill_maf"]))
            largest = max(largest, abs(residual))
            if abs(residual) >= P1_TOL_MAF:
                failures.append(f"{run.label} {run.sim.sim_year(y)}: residual {residual:.3e} MAF")
        worst[run.label] = largest
    return _check("P1", "physics closure", True, not failures,
                  "every yearly residual below 1e-9 MAF" if not failures else "; ".join(failures[:5]),
                  {"largest_residual_maf": worst, "failures": failures})


def gate_p2(runs: Sequence[LoadedRun], cfg: WaterSystemConfig) -> Dict[str, Any]:
    hydrology = _load_hydrology_table()
    failures = []
    for run in runs:
        sim = run.sim
        for (agent, y), row in sim.rows.items():
            req, dlv, w = sim.num(agent, y, "request"), sim.num(agent, y, "diversion"), sim.num(agent, y, "water_right")
            if not (dlv <= req + AF_TOL and req <= w + AF_TOL):
                failures.append(f"{run.label} {agent} {sim.sim_year(y)}: delivered {dlv}, request {req}, right {w}")
        for y in sim.years:
            s = sim.system[y]
            for name, lo, hi in (("powell_storage_maf", cfg.powell_dead_pool_maf, cfg.powell_capacity_maf),
                                 ("powell_storage_end_maf", cfg.powell_dead_pool_maf, cfg.powell_capacity_maf),
                                 ("mead_storage_maf", cfg.mead_dead_pool_maf, cfg.mead_capacity_maf),
                                 ("mead_storage_end_maf", cfg.mead_dead_pool_maf, cfg.mead_capacity_maf)):
                if not lo - MAF_TOL <= s[name] <= hi + MAF_TOL:
                    failures.append(f"{run.label} {sim.sim_year(y)}: {name} {s[name]} outside [{lo}, {hi}]")
            table = hydrology[sim.sim_year(y)]["lees_ferry_cy_natural_flow_af"] / 1e6
            if abs(s["natural_flow_maf"] - table) > MAF_TOL:
                failures.append(f"{run.label} {sim.sim_year(y)}: natural flow {s['natural_flow_maf']} vs table {table}")
        first = sim.system[sim.years[0]]["lake_mead_level"]
        if abs(first - cfg.mead_initial_elevation) > FT_TOL:
            failures.append(f"{run.label}: Lake Mead on 1 January {sim.sim_start_year} is {first} ft, "
                            f"not {cfg.mead_initial_elevation}")
    return _check("P2", "mass and bounds", True, not failures,
                  "0 violations" if not failures else f"{len(failures)} violations: " + "; ".join(failures[:5]),
                  {"violations": failures[:50], "violation_count": len(failures)})


def report_p3(runs: Sequence[LoadedRun], replays: Sequence[LoadedRun], cfg: WaterSystemConfig) -> Dict[str, Any]:
    """Spec section 4, P3 (reported): the first date of the lowest Powell
    storage and the dead-pool dates of both reservoirs, on the window of
    reservoir_outcomes (1 January after each simulated year), beside Hung and
    Yang's depletion year and the two fixed-demand replays."""
    details: Dict[str, Any] = {}
    for run in list(runs) + list(replays):
        r = reservoir_outcomes(run.sim, cfg)
        details[run.label] = {
            "lowest_powell_storage_maf": r["powell_min_maf"],
            "first_jan1_of_lowest_powell_storage": r["powell_min_jan1_year"],
            "powell_dead_pool_jan1": r["powell_dead_pool_dates"],
            "mead_dead_pool_jan1": r["mead_dead_pool_dates"],
        }
    details["hung_yang_2021"] = f"both reservoirs depleted in {HY2021_DEPLETION_YEAR} (p. 15)"
    if not replays:
        details["replays"] = "not supplied"
    return _check("P3", "reservoir timing", False, None, "reported, not gated", details)


def gate_p4(runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    details, failures = {}, []
    for run in runs:
        sim = run.sim
        ub = sum(sim.num(a, 1, "request") for a in sim.agents if sim.basin[a] == "upper_basin") / 1e6
        lb = sum(sim.num(a, 1, "request") for a in sim.agents if sim.basin[a] == "lower_basin") / 1e6
        details[run.label] = {"ub_2019_request_maf": ub, "lb_2019_request_maf": lb}
        if not P4_UB_2019_MAF[0] <= ub <= P4_UB_2019_MAF[1]:
            failures.append(f"{run.label}: UB {ub:.3f} MAF outside {list(P4_UB_2019_MAF)}")
        if not P4_LB_2019_MAF[0] <= lb <= P4_LB_2019_MAF[1]:
            failures.append(f"{run.label}: LB {lb:.3f} MAF outside {list(P4_LB_2019_MAF)}")
    return _check("P4", "unit sanity (2019 request totals)", True, not failures,
                  "both basins inside their ranges" if not failures else "; ".join(failures), details)


P5C_TEMPLATE = "p5c_review_template.json"


def prompt_sha256(prompt: str) -> str:
    """The sha256 of a prompt's text as logged (UTF-8)."""
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def _sample_prompt(run: LoadedRun, agent: str, t: int) -> str:
    trace = run.traces.get((agent, t))
    if trace is None or trace.prompt is None:
        raise MetricsError(f"{run.label}: no logged prompt for {agent} in {run.sim.sim_year(t)} "
                           "(load the run with keep_prompts)")
    return trace.prompt


def p5c_review_template(runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    """The P5(c) record to fill in, tied to the pilot: each run's label and
    code commit and, for each prompt of its reading sample
    (``select_p5c_sample``), the agent, the year and the sha256 of the
    prompt text the reviewer reads."""
    entries = []
    for run in runs:
        entries.append({"label": run.label, "git_commit": run.info.manifest.get("git_commit"), "prompts": [
            {"agent": agent, "year": run.sim.sim_year(t),
             "prompt_sha256": prompt_sha256(_sample_prompt(run, agent, t)),
             "sentences_without_source": None, "notes": ""}
            for agent, t in select_p5c_sample(run)]})
    return {
        "spec": ".research/design_specs/irrigation_v3_spec_2026-09-28.md section 4, P5(c)",
        "instructions": ("Read each prompt in full (p5c_prompts/) with a claim map. Per prompt, set "
                         "sentences_without_source to the number of sentences with no model or state source. "
                         "Fill in reviewer, and reviewer_wrote_code (true or false). Do not edit labels, "
                         "commits, agents, years or hashes: the gate refuses a record that does not match "
                         "the pilot runs."),
        "reviewer": "", "reviewer_wrote_code": None, "runs": entries,
    }


def read_p5c_review(path: Optional[str]) -> Optional[Dict[str, Any]]:
    if path is None:
        return None
    review = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(review, dict):
        raise MetricsError(f"{path}: the P5(c) review record is not a JSON object")
    return review


def check_p5c_review(review: Mapping[str, Any], runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    """Refuse a P5(c) record that is not tied to this pilot pair: it must
    name both runs with their git_commit, list exactly each run's reading
    sample (``select_p5c_sample``) and give, for each prompt, the sha256 of
    the run's logged prompt text and a count of sentences without a source.
    Returns the reviewer, whether the reviewer wrote code, and the totals."""
    problems: List[str] = []
    reviewer = review.get("reviewer")
    if not isinstance(reviewer, str) or not reviewer.strip():
        problems.append("no reviewer named")
    wrote_code = review.get("reviewer_wrote_code")
    if not isinstance(wrote_code, bool):
        problems.append(f"reviewer_wrote_code is {wrote_code!r}, not true or false")
    entries = [e for e in (review.get("runs") or []) if isinstance(e, dict)]
    by_label = {e.get("label"): e for e in entries}
    wanted = sorted(run.label for run in runs)
    if sorted(map(str, by_label)) != wanted or len(entries) != len(runs):
        problems.append(f"the record names runs {sorted(map(str, by_label))}, not the pilot pair {wanted}")
    reviewed = unsourced = 0
    for run in runs:
        entry = by_label.get(run.label)
        if entry is None:
            continue
        commit = run.info.manifest.get("git_commit")
        if entry.get("git_commit") != commit:
            problems.append(f"{run.label}: git_commit {entry.get('git_commit')!r} is not the run's {commit!r}")
        sample = select_p5c_sample(run)
        prompts = [p for p in (entry.get("prompts") or []) if isinstance(p, dict)]
        listed = [(p.get("agent"), p.get("year")) for p in prompts]
        wanted_prompts = [(agent, run.sim.sim_year(t)) for agent, t in sample]
        if listed != wanted_prompts:
            problems.append(f"{run.label}: the record lists {listed}, not the reading sample {wanted_prompts}")
            continue
        for p, (agent, t) in zip(prompts, sample):
            where = f"{run.label} {agent} {run.sim.sim_year(t)}"
            if p.get("prompt_sha256") != prompt_sha256(_sample_prompt(run, agent, t)):
                problems.append(f"{where}: prompt_sha256 does not match the run's logged prompt")
            count = p.get("sentences_without_source")
            if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                problems.append(f"{where}: sentences_without_source is {count!r}, not a count")
            else:
                unsourced += count
            reviewed += 1
    if problems:
        raise MetricsError("refusing the P5(c) review record (write it with p5c-sample for this pilot pair, "
                           "then fill it in):\n  " + "\n  ".join(problems))
    return {"reviewer": reviewer, "reviewer_wrote_code": wrote_code, "prompts_reviewed": reviewed,
            "sentences_without_source": unsourced}


def gate_p5(runs: Sequence[LoadedRun], cfg: WaterSystemConfig, review: Optional[Dict[str, Any]],
            variant: str) -> Dict[str, Any]:
    """``review``: the summary ``check_p5c_review`` returns, or None."""
    audit = PromptAudit()
    error_hits: Dict[str, int] = defaultdict(int)
    no_prompt = 0
    for run in runs:
        checker = PromptChecker(run, cfg, variant)
        for key in sorted(run.traces, key=lambda k: (k[1], k[0])):
            if run.traces[key].crashed:  # an ABORTED_EXCEPTION step: no prompt was sent
                no_prompt += 1
                continue
            checker.audit(key, run.traces[key].prompt or "", audit)
        for d in run.decisions.values():
            for phrase in P5_BANNED_PHRASES:
                if phrase in d.error_messages:
                    error_hits[phrase] += 1
    retry_texts = retry_text_samples()
    retry_hits, retry_where = banned_phrase_hits(retry_texts)
    banned = sum(audit.banned_hits.values()) + sum(error_hits.values()) + sum(retry_hits.values())
    a_ok = banned == 0
    b_ok = not audit.mismatches and not audit.unchecked
    if review is None:
        c_ok, c_reason = False, "P5(c) review record not supplied (--p5c-review; template: p5c-sample)"
    else:
        c_ok = (review["prompts_reviewed"] >= P5C_MIN_PROMPTS and review["sentences_without_source"] == 0
                and review["reviewer_wrote_code"] is False)
        c_reason = (f"{review['prompts_reviewed']} prompts of the reading sample reviewed by "
                    f"{review['reviewer']} (wrote code: {review['reviewer_wrote_code']}), "
                    f"{review['sentences_without_source']} sentences without a source")
    reason = (f"(a) {banned} banned-phrase hits; (b) {len(audit.mismatches)} mismatches and "
              f"{len(audit.unchecked)} unchecked numeric lines over {audit.prompts} prompts; (c) {c_reason}")
    return _check("P5", "invented text", True, a_ok and b_ok and c_ok, reason, {
        "a_banned_hits_in_prompts": dict(audit.banned_hits),
        "a_banned_hits_in_reflection_lines": dict(audit.banned_hits_in_reflections),
        "a_banned_hits_in_rule_texts": dict(error_hits),
        "a_banned_hits_in_retry_texts": retry_hits,
        "a_retry_texts_scanned": len(retry_texts),
        "a_examples": audit.banned_examples + retry_where[:10],
        "a_scope": ("first-attempt prompts (trace input); the logged rule texts (error_messages); the retry "
                    "wrapper (full and placebo, with every configured rule message and suggestion) and the "
                    "feasible-action lines, rendered by the broker from the config (retry_text_samples). "
                    "Retry prompts are not logged; a silent retry repeats the first-attempt prompt"),
        "b_prompts": audit.prompts, "b_steps_without_a_prompt": no_prompt, "b_numeric_lines": audit.numeric_lines,
        "b_mismatches": audit.mismatches[:50], "b_mismatch_count": len(audit.mismatches),
        "b_unchecked": audit.unchecked[:50], "b_unchecked_count": len(audit.unchecked),
        "b_reflection_lines_skipped": audit.reflection_lines,
        "c_review": review, "c_passed": c_ok,
    })


def gate_p6(runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    details, failures = {}, []
    for run in runs:
        r = reflection_checks(run)
        details[run.label] = r
        for key in ("foreign_figure_reflections", "prompts_with_several_reflections",
                    "reflections_not_from_previous_year"):
            if r[key]:
                failures.append(f"{run.label}: {key} = {r[key]}")
    return _check("P6", "reflection contamination", True, not failures,
                  "0; 0; 0" if not failures else "; ".join(failures), details)


def gate_p7(strict: LoadedRun, disabled: LoadedRun) -> Dict[str, Any]:
    def share(run: LoadedRun, test) -> float:
        return sum(1 for d in run.decisions.values() if test(d)) / len(run.decisions)
    gov_strict = share(strict, lambda d: d.retried)
    gov_disabled = share(disabled, lambda d: d.retried)
    parse = {run.label: share(run, lambda d: d.parse_retried) for run in (strict, disabled)}
    agreement = rule_agreement(strict)
    disagreements = {rule: agreement[rule]["disagreements"] for rule in (RULE_SUPPLY, RULE_TR1, RULE_TR3)}
    failures = []
    if gov_strict > P7_STRICT_GOV_RETRY_MAX:
        failures.append(f"strict governance-retry share {gov_strict:.3%} > {P7_STRICT_GOV_RETRY_MAX:.0%}")
    if gov_disabled > P7_DISABLED_GOV_RETRY_MAX:
        failures.append(f"disabled governance-retry share {gov_disabled:.3%} > {P7_DISABLED_GOV_RETRY_MAX:.1%}")
    for label, value in parse.items():
        if value > P7_PARSE_RETRY_MAX:
            failures.append(f"{label} parse-retry share {value:.3%} > {P7_PARSE_RETRY_MAX:.0%}")
    for rule, n in disagreements.items():
        if n:
            failures.append(f"strict {rule}: {n} disagreements between live blocks and the post hoc predicate")
    return _check("P7", "retry rates and rule liveness", True, not failures,
                  "all within thresholds, 0 disagreements" if not failures else "; ".join(failures), {
                      "strict_governance_retry_share": gov_strict,
                      "disabled_governance_retry_share": gov_disabled,
                      "parse_retry_share": parse, "strict_agreement": agreement,
                  })


def gate_p8(runs: Sequence[LoadedRun], expected_rows: Optional[int] = None) -> Dict[str, Any]:
    """Spec section 4, P8: no ``llm_success`` False; no missing agent-year,
    counted on the files: each CSV holds ``expected_rows`` rows (3,276 = 78
    agents x 42 years; ``FULL_CORPUS_ROWS``), every agent in every year (the
    run's own configured grid is reported, never used); rows with no
    readable decision <= 0.5 percent."""
    expected = FULL_CORPUS_ROWS if expected_rows is None else int(expected_rows)
    details, failures = {}, []
    for run in runs:
        configured = _dig(run.info.manifest, ("run_integrity", "configured_grid_rows"))
        llm_false = sum(1 for d in run.decisions.values() if d.llm_success is False)
        unreadable = sum(1 for d in run.decisions.values() if d.final_proposal is None)
        share = unreadable / len(run.decisions)
        audit_rows, log_rows = len(run.decisions), len(run.sim.rows)
        grid = len(run.sim.agents) * len(run.sim.years)
        details[run.label] = {"required_rows": expected, "audit_rows": audit_rows, "log_rows": log_rows,
                              "agents": len(run.sim.agents), "years": len(run.sim.years),
                              "missing_agent_years": grid - log_rows,
                              "configured_grid_rows": None if configured is _MISSING else configured,
                              "llm_success_false": llm_false, "no_readable_decision": unreadable,
                              "no_readable_decision_share": share,
                              "aborted_exception_rows": sum(1 for d in run.decisions.values() if d.crashed)}
        if llm_false:
            failures.append(f"{run.label}: {llm_false} rows with llm_success False")
        if audit_rows != expected or log_rows != expected:
            failures.append(f"{run.label}: {audit_rows} audit and {log_rows} log rows; P8 requires {expected} "
                            "in each (78 agents x 42 years)")
        if grid != log_rows:
            failures.append(f"{run.label}: {grid - log_rows} agent-years missing from the agent x year grid")
        if share > P8_UNREADABLE_MAX:
            failures.append(f"{run.label}: {share:.3%} rows without a readable decision")
    return _check("P8", "LLM failures", True, not failures,
                  "0; 0; within 0.5%" if not failures else "; ".join(failures), details)


def gate_p9(strict: LoadedRun, disabled: LoadedRun) -> Dict[str, Any]:
    details, failures = {}, []
    sets: Dict[str, Dict[str, Set[Tuple[str, ...]]]] = {}
    for run in (strict, disabled):
        forbidden = unclassified = 0
        classes: Dict[str, Set[Tuple[str, ...]]] = defaultdict(set)
        for key, trace in run.traces.items():
            if trace.at_cap is None:
                unclassified += 1
                continue
            cls = "cap" if trace.at_cap else ("floor" if trace.at_floor else "neither")
            if trace.at_cap and trace.at_floor:
                cls = "cap_and_floor"
            if trace.at_cap and "increase" in trace.menu:
                forbidden += 1
            if trace.at_floor and "decrease" in trace.menu:
                forbidden += 1
            classes[cls].add(tuple(sorted(trace.menu)))
        sets[run.label] = classes
        details[run.label] = {"forbidden_offers": forbidden, "aborted_rows_unclassified": unclassified,
                              "option_sets": {k: sorted(v) for k, v in classes.items()}}
        if forbidden:
            failures.append(f"{run.label}: {forbidden} offers of a hidden option")
        several = [k for k, v in classes.items() if len(v) > 1]
        if several:
            failures.append(f"{run.label}: more than one option set in class {several}")
    s, d = sets[strict.label], sets[disabled.label]
    for cls in sorted(set(s) & set(d)):
        if s[cls] != d[cls]:
            failures.append(f"class {cls}: strict offers {sorted(s[cls])}, disabled {sorted(d[cls])}")
    details["classes_in_one_run_only"] = sorted(set(s) ^ set(d))
    return _check("P9", "menu parity", True, not failures,
                  "0 hidden options offered; same option set per class" if not failures else "; ".join(failures),
                  details)


def gate_p10(rows: Mapping[str, Mapping[str, Any]], strict_label: str, runs: Sequence[LoadedRun],
             expected_rows: Optional[int] = None) -> Dict[str, Any]:
    """Spec section 4, P10, as written there: the IBR in [0, 100] and equal
    to its TR1 part plus its TR3 part, over all 3,276 decisions
    (``expected_rows``); the final-label IBR and the relabel rate in
    [0, 100]; strict executed feasibility rates 0; Mead minimum and Tier-3
    years in range; the basin request totals within the rights every year;
    three KGE values finite."""
    expected = FULL_CORPUS_ROWS if expected_rows is None else int(expected_rows)
    failures = []
    for run in runs:
        r = rows[run.label]
        if not (0.0 <= r["ibr_pct"] <= 100.0) or abs(r["ibr_pct"] - r["ibr_tr1_pct"] - r["ibr_tr3_pct"]) > 1e-9:
            failures.append(f"{run.label}: IBR {r['ibr_pct']} vs TR1 {r['ibr_tr1_pct']} + TR3 {r['ibr_tr3_pct']}")
        if r["decisions"] != expected:
            failures.append(f"{run.label}: the IBR is over {r['decisions']} decisions, not all {expected} "
                            "(78 agents x 42 years)")
        for key in ("ibr_final_label_pct", "relabel_rate_pct"):
            if r[key] is not None and not 0.0 <= r[key] <= 100.0:
                failures.append(f"{run.label}: {key} {r[key]} outside [0, 100]")
        if not P10_MEAD_MIN_FT[0] <= r["mead_min_ft"] <= P10_MEAD_MIN_FT[1]:
            failures.append(f"{run.label}: Lake Mead minimum {r['mead_min_ft']:.1f} ft outside {list(P10_MEAD_MIN_FT)}")
        if not P10_TIER3_YEARS[0] <= r["tier3_years"] <= P10_TIER3_YEARS[1]:
            failures.append(f"{run.label}: {r['tier3_years']} Tier-3 years")
        series = system_series(run.sim)
        # Added guard (orchestrator, 2026-10-01): under the constant-series
        # KGE convention a run whose requests never moved still has a finite
        # KGE, so P10 checks for that run directly.
        total = np.asarray([v for _, v in sorted(series["total_request_maf"].items())], dtype=float)
        if _is_constant(total):
            failures.append(f"{run.label}: the UB+LB request total is the same in every year "
                            f"({total[0]:.6f} MAF): no request ever changed (a degenerate run)")
        for name, bound in (("ub_request_maf", P10_UB_RIGHTS_MAF), ("lb_request_maf", P10_LB_RIGHTS_MAF)):
            over = [y for y, v in series[name].items() if v > bound + MAF_TOL]
            if over:
                failures.append(f"{run.label}: {name} above {bound} MAF in {over[:5]}")
        for name in P10_KGE_SERIES:
            value = r[f"kge_{name}"]
            if value is None or not math.isfinite(value):
                failures.append(f"{run.label}: KGE {name} is not finite ({value})")
    s = rows[strict_label]
    for key in ("exec_supply_pct", "exec_cap_pct", "exec_floor_pct"):
        if s[key] != 0.0:
            failures.append(f"strict {key} = {s[key]}")
    return _check("P10", "metric sanity", True, not failures,
                  "all hold" if not failures else "; ".join(failures[:8]),
                  {label: {k: rows[label][k] for k in ("ibr_pct", "ibr_tr1_pct", "ibr_tr3_pct",
                                                        "ibr_final_label_pct", "relabel_rate_pct",
                                                        "exec_supply_pct", "exec_cap_pct", "exec_floor_pct",
                                                        "mead_min_ft", "tier3_years", "kge_mead_jan1_ft",
                                                        "kge_ub_request_maf", "kge_lb_request_maf")}
                   for label in rows})


def report_r1(strict: LoadedRun, disabled: LoadedRun, replays: Sequence[LoadedRun]) -> Dict[str, Any]:
    details: Dict[str, Any] = {}
    for run in (strict, disabled):
        details[run.label] = {row["rule"]: {k: row[k] for k in ("enforcement", "condition_held",
                                                                "condition_unknown", "first_attempt_violations",
                                                                "live_blocked_decisions")}
                              for row in rule_census(run)}
    for replay in replays:
        details[f"{replay.label}_supply_condition_agent_years"] = replay_supply_condition(replay)
    strict_census = details[strict.label]
    not_binding = [rule for rule, v in strict_census.items() if v["live_blocked_decisions"] == 0]
    details["not_binding_in_the_pilot"] = not_binding
    return _check("R1", "rule reach", False, None, "reported", details)


def report_r2(disabled: LoadedRun) -> Dict[str, Any]:
    by_cluster: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for (agent, _year), d in disabled.decisions.items():
        trace = disabled.traces[(agent, _year)]
        for group in (disabled.sim.cluster[agent], "all"):
            c = by_cluster[group]
            c["decisions"] += 1
            both_high = d.first_wsa in HIGH_LEVELS and d.first_aca in HIGH_LEVELS
            c["tr2_condition_and_keep"] += both_high and d.first_proposal == KEEP
            c["tr1_tr2_leave_only_decrease"] += both_high and not bool(trace.at_floor)
            c["tr1_tr2_leave_nothing_at_floor"] += both_high and bool(trace.at_floor)
    details = {}
    for group, c in sorted(by_cluster.items()):
        n = c["decisions"]
        details[group] = {"decisions": n,
                          "tr2_condition_and_keep_pct": _pct(c["tr2_condition_and_keep"], n),
                          "tr1_tr2_leave_only_decrease_pct": _pct(c["tr1_tr2_leave_only_decrease"], n),
                          "tr1_tr2_leave_nothing_at_floor_pct": _pct(c["tr1_tr2_leave_nothing_at_floor"], n)}
    return _check("R2", "TR2 re-measurement (disabled)", False, None, "reported", details)


def run_hours(run: LoadedRun) -> Optional[float]:
    """Wall-clock hours from the first audit row to the manifest's finalize
    time (setup and the first decision's own time excluded)."""
    stamp = run.info.manifest.get("timestamp")
    if not stamp:
        return None
    first = min(datetime.fromisoformat(d.timestamp) for d in run.decisions.values() if d.timestamp)
    return (datetime.fromisoformat(stamp) - first).total_seconds() / 3600.0


def report_r3(runs: Sequence[LoadedRun]) -> Dict[str, Any]:
    return _check("R3", "GPU hours per run", False, None, "reported",
                  {run.label: {"wall_hours_first_decision_to_finalize": run_hours(run)} for run in runs})


def report_r4(runs: Sequence[LoadedRun], fql_runs: Sequence[LoadedRun], cfg: WaterSystemConfig) -> Dict[str, Any]:
    """Item 23 (reported, never gated): R4 per sub-basin and pooled, for each
    pilot run and the FQL seeds pooled, by the definition of drought_recovery."""
    spells: List[Dict[str, Any]] = []
    for run in runs:
        spells.extend(drought_recovery(run.sim, cfg, run.label, run.label))
    for run in fql_runs:
        spells.extend(drought_recovery(run.sim, cfg, run.label, "fql"))
    groups = [run.label for run in runs] + (["fql"] if fql_runs else [])
    return _check("R4", "drought recovery (UB sub-basins)", False, None, "reported",
                  {"by_subbasin_and_pooled": recovery_table(spells, groups), "spells": spells})


def pilot_infos(strict_dir: str, disabled_dir: str) -> Tuple[RunInfo, RunInfo]:
    """The pilot pair (spec section 4): strict seed 42 and disabled seed 42."""
    strict_info, disabled_info = read_run_info(Path(strict_dir)), read_run_info(Path(disabled_dir))
    if strict_info.arm != "strict" or disabled_info.arm != "disabled":
        raise MetricsError(f"the pilot pair must be strict and disabled, got {strict_info.arm} and {disabled_info.arm}")
    for info in (strict_info, disabled_info):
        if info.seed != PILOT_SEED:
            raise MetricsError(f"the pilot pair is seed {PILOT_SEED} (spec section 4); "
                               f"{info.path} is seed {info.seed}")
    return strict_info, disabled_info


def pilot_gate(strict_dir: str, disabled_dir: str, fql_dirs: Sequence[str], replay_dir: Optional[str] = None,
               p5c_review: Optional[str] = None, allow_mixed_provenance: bool = False,
               allow_dirty: bool = False, expected_rows: Optional[int] = None) -> Dict[str, Any]:
    """Spec section 4: the gated checks P1-P10 (P3 reported) and R1-R4.
    ``passed`` is True only if every gated check passes and no provenance
    override is in force: a gate run under ``allow_mixed_provenance`` or
    ``allow_dirty`` never passes. ``expected_rows`` (default
    ``FULL_CORPUS_ROWS``, 3,276) is the row count P8 and P10 require."""
    assert_thinking_rules_match_config()
    cfg = analysis_config()
    expected = FULL_CORPUS_ROWS if expected_rows is None else int(expected_rows)
    strict_info, disabled_info = pilot_infos(strict_dir, disabled_dir)
    fql_infos = _infos_of(fql_dirs, "fql")
    replay_infos = _replay_infos(Path(replay_dir) if replay_dir else None)
    provenance = check_provenance([strict_info, disabled_info] + fql_infos + replay_infos,
                                  allow_mixed_provenance, allow_dirty)
    review_record = read_p5c_review(p5c_review)
    strict = load_run(strict_info.path, keep_prompts=True, info=strict_info)
    disabled = load_run(disabled_info.path, keep_prompts=True, info=disabled_info)
    review = None if review_record is None else check_p5c_review(review_record, [strict, disabled])
    fql_runs = [load_run(i.path, info=i) for i in fql_infos]
    replays = [load_run(i.path, info=i) for i in replay_infos]
    reference = build_reference(fql_runs)
    rows = {run.label: run_metrics(run, reference, cfg)["row"] for run in (strict, disabled)}
    # The sub-basin supply variant of the flow-share sentence: the analysis
    # config's, which the provenance guard checked against every run that
    # records one (the LLM runner does not; its commit fixes the default).
    variant = cfg.ub_subbasin_supply_variant
    checks = [
        gate_p1([strict, disabled]), gate_p2([strict, disabled], cfg), report_p3([strict, disabled], replays, cfg),
        gate_p4([strict, disabled]), gate_p5([strict, disabled], cfg, review, variant), gate_p6([strict, disabled]),
        gate_p7(strict, disabled), gate_p8([strict, disabled], expected), gate_p9(strict, disabled),
        gate_p10(rows, strict.label, [strict, disabled], expected),
    ]
    reported = [report_r1(strict, disabled, replays), report_r2(disabled), report_r3([strict, disabled]),
                report_r4([strict, disabled], fql_runs, cfg)]
    gated_passed = all(c["passed"] for c in checks if c["gated"])
    overrides = [flag for flag, on in (("--allow-mixed-provenance", allow_mixed_provenance),
                                       ("--allow-dirty", allow_dirty)) if on]
    return _jsonable({
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "spec": ".research/design_specs/irrigation_v3_spec_2026-09-28.md section 4",
        "runs": {"strict": str(strict_info.path), "disabled": str(disabled_info.path),
                 "fql": [str(i.path) for i in fql_infos], "replays": [str(i.path) for i in replay_infos]},
        "pilot_seeds": [strict_info.seed, disabled_info.seed], "required_rows": expected,
        "provenance": provenance, "provenance_overrides": overrides, "checks": checks, "reported": reported,
        "gated_checks_passed": gated_passed, "passed": gated_passed and not overrides,
        "metrics": rows,
    })


def select_p5c_sample(run: LoadedRun) -> List[Tuple[str, int]]:
    """The P5(c) reading sample of one run: for each of the years 2019, 2028,
    2034, 2048 and 2060 that the run has, one Upper and one Lower Basin
    prompt; the Lower Basin picks rotate through the three clusters (all
    Upper Basin agents are Aggressive) and the agents through sorted ids."""
    clusters = ("aggressive", "forward_looking_conservative", "myopic_conservative")
    picks: List[Tuple[str, int]] = []
    years = [y for y in P5C_YEARS if y - run.sim.sim_start_year + 1 in run.sim.years]
    for i, year in enumerate(years):
        t = year - run.sim.sim_start_year + 1
        for basin in ("upper_basin", "lower_basin"):
            # an ABORTED_EXCEPTION step sent no prompt, so it cannot be read
            pool = sorted(a for a in run.sim.agents if run.sim.basin[a] == basin
                          and not (run.decisions.get((a, t)) and run.decisions[(a, t)].crashed))
            if basin == "lower_basin":
                wanted = clusters[i % len(clusters)]
                pool = [a for a in pool if run.sim.cluster[a] == wanted] or pool
            if pool:
                picks.append((pool[i % len(pool)], t))
    return picks


def write_p5c_sample(runs: Sequence[LoadedRun], out_dir: Path) -> Path:
    """The ``p5c-sample`` command: the review template (``P5C_TEMPLATE``,
    from ``p5c_review_template``) and, under ``p5c_prompts/<run>/``, each
    sampled prompt's text exactly as logged (its sha256 is in the
    template)."""
    out_dir = Path(out_dir)
    template = p5c_review_template(runs)
    for run, entry in zip(runs, template["runs"]):
        folder = out_dir / "p5c_prompts" / run.label
        folder.mkdir(parents=True, exist_ok=True)
        for prompt, (agent, t) in zip(entry["prompts"], select_p5c_sample(run)):
            name = f"{prompt['year']}_{re.sub(r'[^A-Za-z0-9]+', '_', agent).strip('_')}.txt"
            (folder / name).write_text(_sample_prompt(run, agent, t), encoding="utf-8", newline="")
            prompt["prompt_file"] = f"p5c_prompts/{run.label}/{name}"
    path = out_dir / P5C_TEMPLATE
    path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    return path


# =============================================================================
# Fixed-demand replays (item 21): water system only, no decisions
# =============================================================================

def make_profiles(real: bool, n_agents: int, seed: int, paper_water_margin: float, cluster_method: str):
    if real:
        from examples.irrigation_abm.irrigation_personas import create_profiles_from_data
        return create_profiles_from_data(
            params_csv_path=str(REF_PARAMS_CSV), crss_db_dir=str(REF_CRSS_DB),
            rng=np.random.default_rng(seed), paper_water_margin=paper_water_margin,
            cluster_method=cluster_method)
    from examples.irrigation_abm.run_experiment import _create_synthetic_profiles
    return _create_synthetic_profiles(n_agents, seed)


def run_fixed_demand_replay(kind: str, profiles: Sequence[Any], years: int, seed: int,
                            real: bool) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], IrrigationEnvironment]:
    """Replay A (every agent's request held at its 2018 use) or B (at 0.99 of
    its water right) with ``WaterSystemConfig.hold_requests_fixed = True``
    (item 21): the requests stay as set, the WP2 reset is skipped. Returns
    simulation_log.csv rows (the runners' own row builder), the supply rule's
    condition per agent-year (the validator's own input helper, at the held
    request), and the environment."""
    from examples.irrigation_abm.irrigation_personas import build_simulation_log_row, read_lake_mead_level_for_log
    from examples.irrigation_abm.validators.irrigation_validators import supply_rule_fields

    if kind not in ("A", "B"):
        raise MetricsError(f"replay kind {kind!r} is not A or B")
    env = IrrigationEnvironment(WaterSystemConfig(seed=seed, hold_requests_fixed=True))
    env.initialize_from_profiles(list(profiles))
    if real:
        if not REF_PRECIP_CSV.is_file():
            raise MetricsError(f"missing {REF_PRECIP_CSV}")
        env.load_crss_precipitation(str(REF_PRECIP_CSV))
    if kind == "B":
        for aid in env.agent_ids:
            env.update_agent_request(aid, REPLAY_B_RIGHT_SHARE * env.get_agent_state(aid)["water_right"])
    by_id = {p.agent_id: p for p in profiles}
    log_rows: List[Dict[str, Any]] = []
    condition_rows: List[Dict[str, Any]] = []
    for t in range(1, years + 1):
        env.advance_year()
        for aid in env.agent_ids:
            fields = supply_rule_fields(env.get_agent_context(aid), env.get_agent_state(aid))
            condition_rows.append({
                "agent_id": aid, "year": t,
                "supply_physical_ratio": fields["supply_physical_ratio"],
                "supply_condition": fields["supply_physical_ratio"] < FULL_SUPPLY_RATIO,
            })
        settlement = env.settle_year()
        basin_request_af = (settlement["ub_request_maf"] + settlement["lb_request_maf"]) * 1e6
        for aid in env.agent_ids:
            state = env.get_agent_state(aid)
            context = env.get_agent_context(aid)
            profile = by_id[aid]
            log_rows.append(build_simulation_log_row(
                agent_id=aid, year=t, cluster=profile.cluster, basin=profile.basin,
                yearly_decision="N/A", wsa_label="N/A", aca_label="N/A", agent_state=state,
                drought_index=env.global_state.get("drought_index", 0),
                shortage_tier=env.institutions.get("colorado_compact", {}).get("shortage_tier", 0),
                lake_mead_level=read_lake_mead_level_for_log(env),
                mead_storage_maf=env._mead_storage[-1] if env._mead_storage else 0,
                settlement=settlement, basin_request_af=basin_request_af, memory="",
                base_af=state.get("base_af"), precipitation_mm=context.get("precipitation"),
                precipitation_flag=context.get("precipitation_flag"),
            ))
    return log_rows, condition_rows, env


def write_replays(out_dir: Path, real: bool, n_agents: int, years: int, seed: int,
                  paper_water_margin: float = 0.4, cluster_method: str = "hy2021") -> List[Path]:
    """Write replays A and B to ``out_dir/A`` and ``out_dir/B``, each with its
    simulation log, supply-rule condition table and manifest."""
    import pandas as pd
    from examples.irrigation_abm.run_fql_baseline import _git_provenance, _pinned_v3_data_checksums

    written = []
    for kind in ("A", "B"):
        profiles = make_profiles(real, n_agents, seed, paper_water_margin, cluster_method)
        rows, condition, env = run_fixed_demand_replay(kind, profiles, years, seed, real)
        target = Path(out_dir) / kind
        target.mkdir(parents=True, exist_ok=True)
        frame = pd.DataFrame(rows)
        frame["precipitation_flag"] = frame["precipitation_flag"].astype("Int64")
        frame.to_csv(target / SIM_LOG, index=False)
        write_csv(target / REPLAY_CONDITION_CSV, condition)
        cfg = env.config
        manifest = {
            "runner": REPLAY_RUNNER, "replay_kind": kind,
            "definition": ("A: every agent's request held at its 2018 use" if kind == "A"
                           else f"B: every agent's request held at {REPLAY_B_RIGHT_SHARE} of its water right"),
            "seed": seed, "years": years, "real": bool(real), "n_agents": len(profiles),
            "paper_water_margin": paper_water_margin, "paper_water_margin_applied": bool(real),
            "cluster_method": cluster_method, "cluster_method_applied": bool(real),
            "step_bin_source": {p.agent_id: getattr(p, "step_bin_source", None) for p in profiles},
            "hold_requests_fixed": cfg.hold_requests_fixed,
            "powell_release_mode": cfg.powell_release_mode,
            "powell_post2026_equalization": cfg.powell_post2026_equalization,
            "lb_non_ag_total_maf": cfg.lb_non_ag_total_maf,
            "ub_supply_mode": cfg.ub_supply_mode,
            "ub_subbasin_supply_variant": cfg.ub_subbasin_supply_variant,
            "lb_priority_mode": cfg.lb_priority_mode,
            **_git_provenance(REPO_ROOT),
            "pinned_v3_data_checksums": _pinned_v3_data_checksums(cfg.ub_subbasin_supply_variant),
            "water_system_config": dataclasses.asdict(cfg),
        }
        (target / MANIFEST).write_text(json.dumps(_jsonable(manifest), indent=2), encoding="utf-8")
        written.append(target)
    return written


# =============================================================================
# Output
# =============================================================================

def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return "|".join(str(v) for v in value)
    if isinstance(value, dict):
        return json.dumps(_jsonable(value), sort_keys=True)
    return value


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Optional[Sequence[str]] = None) -> None:
    if columns is None:
        columns = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: _csv_value(row.get(k)) for k in columns})


def _fmt(value: Any, digits: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}"
    return str(value)


def _md_table(headers: Sequence[str], rows: Sequence[Sequence[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


_METRIC_DIGITS = {"mead_min_ft": 1, "powell_min_maf": 3, "mead_min_jan1_year": 0, "powell_min_jan1_year": 0}


def _summary_cell(entry: Mapping[str, Any], metric: str) -> str:
    digits = _METRIC_DIGITS.get(metric, 3 if metric.startswith("kge") else 2)
    if entry["n"] == 0:
        return "n/a"
    text = _fmt(entry["mean"], digits)
    if entry["sd"] is not None:
        text += f" +- {_fmt(entry['sd'], digits)}"
    if entry["n"] > 1:
        text += f" [{_fmt(entry['min'], digits)}, {_fmt(entry['max'], digits)}]"
    return f"{text} (n={entry['n']})"


def _median_cell(entry: Mapping[str, Any], digits: int = 3) -> str:
    """Median first (the FQL leave-one-out benchmark), then mean and sd."""
    if entry["n"] == 0:
        return "n/a"
    sd = f" +- {_fmt(entry['sd'], digits)}" if entry["sd"] is not None else ""
    return f"median {_fmt(entry['median'], digits)} (mean {_fmt(entry['mean'], digits)}{sd}, n={entry['n']})"


def _sum_by(rows: Sequence[Mapping[str, Any]], keys: Sequence[str], fields: Sequence[str]) -> List[Dict[str, Any]]:
    """Sum ``fields`` over rows grouped by ``keys`` (first-seen order)."""
    groups: Dict[Tuple[Any, ...], Dict[str, Any]] = {}
    for row in rows:
        key = tuple(row[k] for k in keys)
        if key not in groups:
            groups[key] = {**{k: row[k] for k in keys}, "runs": 0, **{f: 0 for f in fields}}
        groups[key]["runs"] += 1
        for f in fields:
            groups[key][f] += row[f]
    return list(groups.values())


def metrics_markdown(result: MetricsResult) -> str:
    """The human summary. Per-run detail stays in the CSVs."""
    p = result.provenance
    arms = [a for a in ARMS if any(r["arm"] == a for r in result.per_run)]
    lines = ["# Irrigation v3 metrics (WP6)", "",
             "Definitions: examples/irrigation_abm/docs/v3_metrics.md. Rates are percentages of all decisions "
             "unless stated. KGE is agreement with the FQL reference (the source model's decision rule in the "
             "same water system), not validation. Cells: mean +- sd [min, max] (n) over seeds.", ""]
    lines += ["## Provenance", "",
              f"- code commit(s): {', '.join(p['code_commits'])}; analysis at {p['analysis_git_head']}",
              f"- model: {', '.join(p['model']) or 'n/a'}; seed scheme: {p['seed_scheme']}",
              f"- runs: {len(result.per_run)} LLM, {len(result.fql_per_seed)} FQL seeds, "
              f"{len(result.replays)} replays"]
    not_recorded = sorted(k for k, v in p["water_system"].items() if v["not_recorded_by"])
    if not_recorded:
        lines.append("- water-system keys not recorded by every runner (compared where recorded): "
                     + ", ".join(not_recorded))
    if p.get("dirty_override_applied"):
        lines.append(f"- PROVENANCE OVERRIDE (--allow-dirty): {len(p['dirty_runs'])} runs from a dirty tree are "
                     "pooled; their commit does not identify their code:")
        lines.extend(f"  - {d}" for d in p["dirty_runs"])
    lines.extend(f"- warning: {w}" for w in p["warnings"])
    if p["override_applied"]:
        lines.append("- PROVENANCE OVERRIDE (allow_mixed_provenance): the runs pooled here differ in:")
        lines.extend(f"  - {d}" for d in p["differences"])
    lines.extend(f"- note: {note}" for note in result.notes)
    lines.append("")

    index = {(e["arm"], e["metric"]): e for e in result.arm_summary}

    def summary_table(metrics: Sequence[str], include_fql: bool = False) -> str:
        cols = arms + (["fql"] if include_fql else [])
        body = [[metric] + [_summary_cell(index[(a, metric)], metric) if (a, metric) in index else "n/a"
                            for a in cols] for metric in metrics]
        return _md_table(["metric"] + cols, body)

    lines += ["## IBR (item 19)", "",
              summary_table(("ibr_pct", "ibr_tr1_pct", "ibr_tr3_pct", "ibr_final_label_pct",
                             "ibr_final_label_tr1_pct", "ibr_final_label_tr3_pct",
                             "relabel_rate_pct")), "",
              "relabel_rate_pct is a share of retried decisions (WSA only). The share of relabels made with no "
              "change in r (RB 6.4; r is the expected delivery ratio at the keep request) is not reported: r is "
              "fixed within a decision, so that share is always 100%.", ""]
    lines += ["## Executed feasibility violation rate (items 10, 19)", "",
              summary_table(("exec_supply_pct", "exec_cap_pct", "exec_floor_pct", "exec_total_pct")), ""]
    lines += ["## Supply-rule exposure", "", summary_table(("supply_condition_pct", "supply_condition_ub_pct",
                                                           "supply_condition_lb_pct",
                                                           "supply_live_blocked_decisions")), ""]
    by_period = []
    for arm in arms:
        for basin in ("upper_basin", "lower_basin"):
            for period in ("before_dead_pool", "from_dead_pool"):
                rows = [e for e in result.exposure
                        if e["arm"] == arm and e["basin"] == basin and e["period"] == period]
                d = describe([e["condition_pct"] for e in rows])
                by_period.append([arm, basin, period, sum(e["agent_years"] for e in rows),
                                  _summary_cell(d, "condition_pct"),
                                  sum(e["live_blocked_decisions"] for e in rows)])
    lines += ["By basin, before and from Mead's first dead-pool year (condition share per run; agent-years "
              "and live blocks summed over seeds):", "",
              _md_table(["arm", "basin", "period", "agent-years", "condition %", "live blocks"], by_period), ""]
    agreement = _sum_by(result.agreement, ("arm", "rule"), ("attempts", "predicate", "live", "disagreements"))
    if agreement:
        lines += ["Live blocks against the post hoc predicates, attempt by attempt, rules live in the arm "
                  "(summed over seeds; P7 needs 0 disagreements):", "",
                  _md_table(["arm", "rule", "runs", "attempts", "predicate", "live", "disagreements"],
                            [[a["arm"], a["rule"], a["runs"], a["attempts"], a["predicate"], a["live"],
                              a["disagreements"]] for a in agreement]), ""]
    lines += ["## Reservoir outcomes", "",
              summary_table(("mead_min_ft", "mead_min_jan1_year", "tier0_years", "tier1_years", "tier2_years",
                             "tier3_years", "mead_dead_pool_count", "powell_dead_pool_count", "powell_min_maf",
                             "powell_min_jan1_year"), include_fql=True), ""]
    kge_body = []
    for metric in (f"kge_{n}" for n in HEADLINE_SERIES):
        fql = index.get(("fql", metric))
        kge_body.append([metric] + [_summary_cell(index[(a, metric)], metric) if (a, metric) in index else "n/a"
                                    for a in arms] + [_median_cell(fql) if fql else "n/a"])
    lines += ["## KGE against the FQL ensemble mean (Gupta et al. 2009)", "",
              _md_table(["metric"] + arms + ["fql, leave-one-out"], kge_body), "",
              "Rows: " + "; ".join(f"kge_{n} = {SERIES_LABELS[n]}" for n in HEADLINE_SERIES) + ". The fql "
              "column is the MEDIAN across FQL seeds of each seed's KGE against the mean of the other seeds, "
              "with the mean and sd beside it. For kge_lb_request_maf that median is the item 30 benchmark: "
              "the median KGE of the LB request TOTAL, not a per-agent figure. A constant simulated series is "
              "scored with r := 0 and alpha := 0 (convention), so its KGE is 1 - sqrt(2 + (beta - 1)^2); n/a "
              "marks a constant reference.", ""]
    if result.benchmark_summary:
        lines += ["FQL against FQL, per series (each seed against the mean of the other seeds; median and range "
                  "across seeds):", "",
                  _md_table(["series", "label", "seeds", "defined", "median", "min", "max"],
                            [[b["series"], b["label"], b["seeds"], b["defined"], _fmt(b["median"], 3),
                              _fmt(b["min"], 3), _fmt(b["max"], 3)] for b in result.benchmark_summary
                             if not b["series"].startswith(LB_AGENT_PREFIX)]), ""]
    if result.lb_agent_ceilings:
        per_agent: Dict[Tuple[str, str], List[Optional[float]]] = defaultdict(list)
        for r in result.lb_agent_rows:
            per_agent[(r["agent"], r["arm"])].append(r["kge"])
        median_rows = []
        for arm in arms:
            arm_runs = [r for r in result.per_run if r["arm"] == arm]
            median_rows.append([arm, _summary_cell(describe([r["kge_lb_agent_request_median"] for r in arm_runs]),
                                                   "kge"),
                                " ".join(str(r["kge_lb_agent_constant_sim"]) for r in arm_runs),
                                " ".join(str(r["kge_lb_agent_undefined"]) for r in arm_runs)])
        lines += ["LB per agent: the per-run median over LB agents of each agent's request KGE "
                  "(kge_lb_agent_request_median), beside the agents scored by the constant-series convention "
                  "(in the median) and the agents without a KGE (constant reference; left out, the same agents "
                  "in every arm), per run:", "",
                  _md_table(["arm", "median over LB agents", "constant-sim agents per run",
                             "undefined agents per run"], median_rows), "",
                  "LB per-agent request KGE against each agent's own ceiling. An agent's ceiling is computed per "
                  "agent: the median, across FQL seeds, of that agent's request KGE against the mean of the other "
                  "seeds.", "",
                  _md_table(["LB agent", "own ceiling", "seeds defined"] + arms,
                            [[c["agent"], _fmt(c["ceiling"], 3), f"{c['seeds_defined']}/{c['seeds']}"]
                             + [_summary_cell(describe(per_agent[(c["agent"], arm)]), "kge") for arm in arms]
                             for c in result.lb_agent_ceilings]), ""]
    subbasins = sorted({row["series"].split(":", 1)[1] for row in result.kge_rows
                        if row["series"].startswith(SUBBASIN_PREFIXES[0])})
    if subbasins:
        body = []
        for sb in subbasins:
            for prefix in SUBBASIN_PREFIXES:
                name = f"{prefix}{sb}"
                cells = []
                for arm in arms:
                    labels = {r["run"] for r in result.per_run if r["arm"] == arm}
                    values = [row["kge"] for row in result.kge_rows if row["run"] in labels and row["series"] == name]
                    cells.append(_summary_cell(describe(values), "kge"))
                bench = next((b for b in result.benchmark_summary if b["series"] == name), None)
                body.append([name] + cells + [_fmt(bench["median"], 3) if bench else "n/a"])
        lines += ["UB per sub-basin (request and delivery totals):", "",
                  _md_table(["series"] + arms + ["FQL median"], body), ""]
    if result.replays:
        lines += ["Replays A (2018 use held) and B (0.99 W held), item 21: the KGE floor and ceiling. Cells "
                  "marked (c) are constant by design (requests held fixed, hold_requests_fixed) and scored by "
                  "the r := 0, alpha := 0 convention, 1 - sqrt(2 + (beta - 1)^2): a no-change floor, not a "
                  "model result (replays.csv: kge_convention_series, kge_note).", "",
                  _md_table(["replay"] + [f"kge_{n}" for n in HEADLINE_SERIES] + ["Mead min ft", "Tier-3 years"],
                            [[r["run"]] + [_fmt(r[f"kge_{n}"], 3)
                                           + (" (c)" if f"kge_{n}" in r["kge_convention_series"] else "")
                                           for n in HEADLINE_SERIES]
                             + [_fmt(r["mead_min_ft"], 1), r["tier3_years"]] for r in result.replays]), ""]
    if result.recovery_summary:
        lines += ["## R4 drought recovery (items 23, 31, 34; reported, never gated)", "",
                  "Per UB sub-basin, a dry spell is a maximal run of consecutive years whose sub-basin supply "
                  f"A_s(t) is below the {UB_DRY_YEAR_PERCENTILE:.0f}th percentile of that sub-basin's own A_s "
                  "over the full supply table (item 34; a stated assumption, never the settled, post-decision "
                  "ub_subbasin_ratio); its reference is the sub-basin total request in the last year before "
                  "the spell; the recovery time is the smallest j >= 1 with the total request in (last spell "
                  "year + j) at or above the reference; a spell is censored when that is not reached before the "
                  "next spell or the end of the run. Spells starting in the first year have no reference and "
                  "are counted apart. Seeds pooled per arm; FQL seeds pooled.", "",
                  _md_table(["arm", "sub-basin", "spells", "recovered", "censored", "median recovery years",
                             "no reference"],
                            [[r["arm"], r["subbasin"], r["r4_spells"], r["r4_recovered"], r["r4_censored"],
                              _fmt(r["r4_median_recovery_years"], 1), r["r4_no_reference"]]
                             for r in result.recovery_summary]), ""]
    comparisons = [f"{a} - {b}" for a, b in PAIRED_COMPARISONS
                   if any(t["comparison"] == f"{a} - {b}" for t in result.paired)]
    if comparisons:
        cell = {(t["comparison"], t["metric"]): t for t in result.paired}
        body = []
        for metric in PAIRED_METRICS:
            row = [metric]
            for comp in comparisons:
                t = cell.get((comp, metric))
                if t is None and metric.startswith("exec_") and EXEC_PAIRED_ARM not in comp.split(" - "):
                    row.append("0 by construction")
                elif t is None or t["n_pairs"] == 0:
                    row.append("n/a")
                else:
                    row.append(f"{_fmt(t['mean_diff'], 3)} (p {_fmt(t['p_two_sided'], 3)}, n {t['n_pairs']})")
            body.append(row)
        floors = sorted({t["p_floor"] for t in result.paired if t["p_floor"] is not None})
        lines += ["## Paired comparisons across seeds (exact sign-flip test)", "",
                  "Mean paired difference (first minus second) with its two-sided p, over the seeds where both "
                  "values exist (paired_tests.csv lists them). The smallest attainable p is 2^(z + 1) / 2^n with "
                  "z the zero differences (2 / 2^n = 0.0625 at n = 5 when none is zero): "
                  f"{', '.join(_fmt(f, 4) for f in floors) or 'n/a'} here. The executed feasibility rates are "
                  "compared only in the pairs with disabled; elsewhere both sides are 0 by construction.", "",
                  _md_table(["metric"] + comparisons, body), ""]
    if result.feasibility_vs_ranges:
        lines += ["## Feasibility-only run against the five-seed ranges (descriptive, no test)", "",
                  _md_table(["metric", "value", "strict range", "inside", "disabled range", "inside"],
                            [[f["metric"], _fmt(f["value"], 3),
                              f"[{_fmt(f['strict_min'], 3)}, {_fmt(f['strict_max'], 3)}]",
                              _fmt(f["within_strict_range"]),
                              f"[{_fmt(f['disabled_min'], 3)}, {_fmt(f['disabled_max'], 3)}]",
                              _fmt(f["within_disabled_range"])] for f in result.feasibility_vs_ranges
                             if f["metric"] in PAIRED_METRICS]), ""]
    census = _sum_by(result.census, ("arm", "rule", "enforcement"),
                     ("condition_held", "condition_unknown", "first_attempt_violations",
                      "final_proposal_violations", "executed_violations", "live_blocked_decisions"))
    lines += ["## Rule census (SI; summed over seeds)", "",
              _md_table(["arm", "rule", "enforcement", "runs", "condition", "unknown", "first attempt",
                         "final proposal", "executed", "live blocks"],
                        [[c["arm"], c["rule"], c["enforcement"], c["runs"], c["condition_held"],
                          c["condition_unknown"], c["first_attempt_violations"], c["final_proposal_violations"],
                          c["executed_violations"], c["live_blocked_decisions"]] for c in census]), ""]

    def r5_cell(rows: Sequence[Mapping[str, Any]], key: str, value: Any, arm: str) -> str:
        row = next((r for r in rows if r.get(key) == value and r["arm"] == arm), None)
        if row is None or row["mean_first_wsa"] is None:
            return "n/a"
        return f"{row['mean_first_wsa']:.2f} (n={row['n_in_mean']})"

    def r5b_cell(arm: str, k: Any, full_window: Optional[bool]) -> str:
        row = next((r for r in result.r5b_summary if r["arm"] == arm and r["k_short_years"] == k
                   and r["full_window"] == full_window), None)
        if row is None or row["mean_first_wsa"] is None:
            return "n/a"
        return f"{row['mean_first_wsa']:.2f} (n={row['n_in_mean']})"

    def r5c_cell(rows: Sequence[Mapping[str, Any]], position_type: str, position: int, arm: str) -> str:
        row = next((r for r in rows if r["position_type"] == position_type and r["position"] == position
                   and r["arm"] == arm), None)
        if row is None or row["mean_first_wsa"] is None:
            return "n/a"
        return f"{row['mean_first_wsa']:.2f} (n={row['n_in_mean']})"

    if result.r5a_summary:
        lines += ["## R5: appraisal against the supply headline and multi-year drought "
                  "(items 33b, 34; report-only, pre-registered 2026-10-01; never gated)", "",
                  "First-stated WSA ordinal for R5b and R5c's means: VL=1, L=2, M=3, H=4, VH=5. In every "
                  "mean or share below, ABORTED, ABORTED_EXCEPTION, a blank first-stated WSA ('missing') "
                  "and a stated-but-off-scale one ('off_scale') are excluded and counted beside it, never "
                  "silently dropped. Per-run detail: r5a_wsa_by_band.csv, r5b_wsa_by_short_years.csv, "
                  "r5c_wsa_by_spell_year.csv, r5d_unblocked_increase_share.csv, r5d_ub_little_spare.csv. R4 "
                  "and R5c's dry years are the exogenous threshold-level definition (ub_subbasin_dry_years, "
                  f"item 34): below the {UB_DRY_YEAR_PERCENTILE:.0f}th percentile of the sub-basin's own A_s "
                  "over the FULL supply table for the variant (the 42-year trace, not just this run's own "
                  "years), a stated assumption, identical in every arm and seed.", "",
                  "### R5a: first-stated WSA by the supply headline band (counts, pooled over seeds)", ""]
        for arm in arms:
            body = []
            bands = list(R5A_BANDS)
            if any(r["arm"] == arm and r["band"] == "unknown_no_supply_state" for r in result.r5a_summary):
                bands.append("unknown_no_supply_state")
            for band in bands:
                cells = [next((r["decisions"] for r in result.r5a_summary if r["arm"] == arm
                              and r["band"] == band and r["first_wsa"] == wsa), 0)
                        for wsa in R5A_WSA_CATEGORIES]
                total = next((r["band_total_decisions"] for r in result.r5a_summary
                             if r["arm"] == arm and r["band"] == band), 0)
                body.append([band] + cells + [total])
            lines += [f"{arm}:", "", _md_table(["band"] + R5A_WSA_CATEGORIES + ["total"], body), ""]
        if result.r5b_summary:
            lines += ["### R5b: mean first-stated WSA by short years in the last "
                      f"{R5B_SHORT_YEAR_WINDOW} shown years", "",
                      "full_window = True: all 5 years were shown (years 6+); False: fewer were (years "
                      "2-5, so a given K means less). Year 1 decisions (no shown prior year) are under "
                      "k_short_years = no_window in the exclusions table below, not folded into K = 0.", "",
                      "full_window = True:", "",
                      _md_table(["k short years"] + arms,
                                [[k] + [r5b_cell(a, k, True) for a in arms]
                                 for k in range(R5B_SHORT_YEAR_WINDOW + 1)]), "",
                      "full_window = False:", "",
                      _md_table(["k short years"] + arms,
                                [[k] + [r5b_cell(a, k, False) for a in arms]
                                 for k in range(R5B_SHORT_YEAR_WINDOW + 1)]), "",
                      "Exclusions (summed over seeds, k and full_window):", "",
                      _md_table(["arm", "aborted", "blank WSA", "off-scale WSA", "no_window"],
                                [[a, sum(r["aborted_excluded"] for r in result.r5b_summary if r["arm"] == a),
                                  sum(r["blank_wsa_excluded"] for r in result.r5b_summary if r["arm"] == a),
                                  sum(r["off_scale_excluded"] for r in result.r5b_summary if r["arm"] == a),
                                  sum(r["no_window_excluded"] for r in result.r5b_summary if r["arm"] == a)]
                                 for a in arms]), ""]
        if result.r5c_summary:
            positions = sorted({(r["position_type"], r["position"]) for r in result.r5c_summary},
                               key=lambda p: (p[0] != "in_spell", p[1]))
            lines += ["### R5c: mean first-stated WSA by year within a UB dry spell (items 31, 34) and after it "
                      "(UB sub-basins only, as in R4)", "",
                      _md_table(["position"] + arms,
                                [[f"{pt} {p}"] + [r5c_cell(result.r5c_summary, pt, p, a) for a in arms]
                                 for pt, p in positions]), "",
                      "Exclusions (summed over seeds and position):", "",
                      _md_table(["arm", "aborted", "blank WSA", "off-scale WSA"],
                                [[a, sum(r["aborted_excluded"] for r in result.r5c_summary if r["arm"] == a),
                                  sum(r["blank_wsa_excluded"] for r in result.r5c_summary if r["arm"] == a),
                                  sum(r["off_scale_excluded"] for r in result.r5c_summary if r["arm"] == a)]
                                 for a in arms]), ""]
        else:
            lines += ["### R5c: mean first-stated WSA by year within a UB dry spell (items 31, 34) and after it",
                      "", "No UB dry spell in this corpus (UB sub-basins only, as in R4).", ""]
        if result.r5d_summary:
            splits = [s for s, _ in R5D_SPLITS if any(r["split"] == s for r in result.r5d_summary)]
            body = []
            for split in splits:
                row_cells = []
                for a in arms:
                    r = next((r for r in result.r5d_summary if r["arm"] == a and r["split"] == split), None)
                    row_cells.append("n/a" if r is None or r["eligible_decisions"] == 0
                                     else f"{_fmt(r['share_pct'], 1)}% (n={r['eligible_decisions']})")
                body.append([split] + row_cells)
            lines += ["### R5d: first proposals that are increases where neither TR1 nor the supply rule "
                      "could act (spec 33b), by split (item 33c)", "",
                      _md_table(["split"] + arms, body), "",
                      "overall's exclusions (summed over seeds; aborted, blank WSA, off-scale WSA, "
                      "at-cap -- increase not on the menu):", "",
                      _md_table(["arm", "aborted", "blank WSA", "off-scale WSA", "at-cap"],
                                [[a] + [next((r[f"excluded_{k}"] for r in result.r5d_summary
                                             if r["arm"] == a and r["split"] == "overall"), 0)
                                       for k in ("aborted", "blank_wsa", "off_scale_wsa", "at_cap")]
                                 for a in arms]), ""]
        if result.r5d_little_spare_summary:
            lines += ["### R5d-UB-little-spare: first proposals that are increases where the supply rule "
                      "did not fire and the sub-basin's unused water (A_s minus the sum of the members' "
                      "Decision.keep_request_af) is below the deciding agent's own typical_step_af (item "
                      "34; spec 33b)", "",
                      _md_table(["arm", "eligible", "increases", "share %", "excl. aborted",
                                 "excl. unknown sum"],
                                [[r["arm"], r["eligible_decisions"], r["first_proposal_increases"],
                                  _fmt(r["share_pct"], 1), r["excluded_aborted"], r["excluded_unknown_sum"]]
                                 for r in result.r5d_little_spare_summary]), ""]
    return "\n".join(lines)


def write_metrics(result: MetricsResult, out_dir: Path) -> List[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tables = {
        "per_run_metrics.csv": result.per_run, "fql_per_seed.csv": result.fql_per_seed,
        "replays.csv": result.replays, "arm_summary.csv": result.arm_summary,
        "paired_tests.csv": result.paired, "feasibility_only_vs_ranges.csv": result.feasibility_vs_ranges,
        "rule_census.csv": result.census, "supply_exposure.csv": result.exposure,
        "rule_agreement.csv": result.agreement, "kge.csv": result.kge_rows,
        "kge_fql_benchmark.csv": result.benchmark_rows, "kge_fql_benchmark_summary.csv": result.benchmark_summary,
        "lb_agent_kge.csv": result.lb_agent_rows, "lb_agent_ceilings.csv": result.lb_agent_ceilings,
        "drought_recovery.csv": result.recovery, "drought_recovery_summary.csv": result.recovery_summary,
        "r5a_wsa_by_band.csv": result.r5a, "r5a_wsa_by_band_summary.csv": result.r5a_summary,
        "r5b_wsa_by_short_years.csv": result.r5b, "r5b_wsa_by_short_years_summary.csv": result.r5b_summary,
        "r5c_wsa_by_spell_year.csv": result.r5c, "r5c_wsa_by_spell_year_summary.csv": result.r5c_summary,
        "r5d_unblocked_increase_share.csv": result.r5d,
        "r5d_unblocked_increase_share_summary.csv": result.r5d_summary,
        "r5d_ub_little_spare.csv": result.r5d_little_spare,
        "r5d_ub_little_spare_summary.csv": result.r5d_little_spare_summary,
    }
    written = []
    for name, rows in tables.items():
        write_csv(out_dir / name, rows)
        written.append(out_dir / name)
    (out_dir / "provenance.json").write_text(json.dumps(_jsonable(result.provenance), indent=2), encoding="utf-8")
    (out_dir / "v3_metrics.md").write_text(metrics_markdown(result), encoding="utf-8")
    return written + [out_dir / "provenance.json", out_dir / "v3_metrics.md"]


def write_pilot_gate(report: Mapping[str, Any], out_dir: Path, sample: Mapping[str, Sequence[Tuple[str, int]]]) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "v3_pilot_gate_report.json"
    path.write_text(json.dumps(_jsonable(report), indent=2), encoding="utf-8")
    lines = ["# Irrigation v3 pilot gate", "", f"Passed: {_fmt(report['passed'])}", ""]
    if report.get("provenance_overrides"):
        lines += [f"Provenance override in force ({', '.join(report['provenance_overrides'])}): a gate run under "
                  "an override never passes (every gated check passed: "
                  f"{_fmt(report['gated_checks_passed'])}).", ""]
    lines += [_md_table(["check", "title", "gated", "passed", "reason"],
                        [[c["id"], c["title"], _fmt(c["gated"]), _fmt(c["passed"]), c["reason"]]
                         for c in list(report["checks"]) + list(report["reported"])]), "",
              "## P5(c) reading sample", "",
              "The review template, tied to these runs (labels, commits, prompts and their sha256), and the "
              "prompt texts: `v3_metrics.py p5c-sample --runs STRICT42 DISABLED42 --out DIR`.", ""]
    for label, picks in sample.items():
        lines.append(f"- {label}: " + ", ".join(f"{agent} ({year})" for agent, year in picks))
    (out_dir / "v3_pilot_gate_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


# =============================================================================
# CLI
# =============================================================================

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Irrigation v3 metrics and pilot gate (WP6).")
    sub = parser.add_subparsers(dest="command", required=True)
    m = sub.add_parser("metrics", help="every WP6 metric over a corpus")
    m.add_argument("--runs", nargs="+", required=True, help="LLM run directories (or their parents)")
    m.add_argument("--fql", nargs="+", required=True, help="FQL reference seed directories (or their parent)")
    m.add_argument("--replays", default=None, help="output of the replay command (A/ and B/)")
    m.add_argument("--out", required=True)
    m.add_argument("--allow-mixed-provenance", action="store_true",
                   help="pool runs whose manifests differ; every difference is written to the output")
    m.add_argument("--allow-dirty", action="store_true",
                   help="pool runs from a dirty tree; the override is written to the output")
    s = sub.add_parser("p5c-sample", help="write the P5(c) review template and the sampled prompt texts")
    s.add_argument("--runs", nargs=2, required=True, metavar=("STRICT", "DISABLED"))
    s.add_argument("--out", required=True)
    g = sub.add_parser("pilot-gate", help="spec section 4: exit 0 only if every gated check passes and no "
                                          "provenance override is given")
    g.add_argument("--runs", nargs=2, required=True, metavar=("STRICT", "DISABLED"))
    g.add_argument("--fql", nargs="+", required=True)
    g.add_argument("--replays", default=None)
    g.add_argument("--p5c-review", default=None,
                   help="the filled-in P5(c) record written by p5c-sample for this pilot pair")
    g.add_argument("--out", required=True)
    g.add_argument("--allow-mixed-provenance", action="store_true", help="never exits 0")
    g.add_argument("--allow-dirty", action="store_true", help="never exits 0")
    r = sub.add_parser("replay", help="write the fixed-demand replays A and B (item 21)")
    source = r.add_mutually_exclusive_group(required=True)
    source.add_argument("--real", action="store_true", help="the 78 CRSS agents")
    source.add_argument("--agents", type=int, help="synthetic agents (mock corpora)")
    r.add_argument("--years", type=int, default=42)
    r.add_argument("--seed", type=int, default=42)
    r.add_argument("--paper-water-margin", type=float, default=0.4)
    r.add_argument("--cluster-method", default="hy2021", choices=["hy2021", "legacy_centroid"])
    r.add_argument("--out", required=True)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "metrics":
        result = compute_metrics(args.runs, args.fql, args.replays, args.allow_mixed_provenance, args.allow_dirty)
        for path in write_metrics(result, Path(args.out)):
            print(f"[v3_metrics] wrote {path}")
        return 0
    if args.command == "p5c-sample":
        infos = pilot_infos(args.runs[0], args.runs[1])
        runs = [load_run(info.path, keep_prompts=True, info=info) for info in infos]
        path = write_p5c_sample(runs, Path(args.out))
        print(f"[v3_metrics] wrote the P5(c) review template {path}")
        return 0
    if args.command == "pilot-gate":
        report = pilot_gate(args.runs[0], args.runs[1], args.fql, args.replays, args.p5c_review,
                            args.allow_mixed_provenance, args.allow_dirty)
        sample = {}
        for path in args.runs:
            run = load_run(Path(path))
            sample[run.label] = select_p5c_sample(run)
        path = write_pilot_gate(report, Path(args.out), sample)
        print(f"[v3_metrics] pilot gate {'PASSED' if report['passed'] else 'FAILED'}: {path}")
        if report["provenance_overrides"]:
            print(f"  provenance override in force ({', '.join(report['provenance_overrides'])}): "
                  "the gate cannot pass")
        for c in report["checks"]:
            print(f"  {c['id']} {'pass' if c['passed'] else ('fail' if c['gated'] else 'reported')}: {c['reason']}")
        return 0 if report["passed"] else 1
    if args.command == "replay":
        for path in write_replays(Path(args.out), args.real, args.agents or 0, args.years, args.seed,
                                  args.paper_water_margin, args.cluster_method):
            print(f"[v3_metrics] wrote replay {path}")
        return 0
    raise MetricsError(f"unknown command {args.command!r}")


if __name__ == "__main__":
    sys.exit(main())
