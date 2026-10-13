"""Agent-decision environment for the irrigation v3 historical hindcast."""
from __future__ import annotations

import csv
import hashlib
from dataclasses import replace
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from examples.irrigation_abm.analysis.hindcast_v3 import (
    LB_DIVERSION_SHA256,
    OBSERVED_CSV_SHA256,
    TIER_START_YEAR,
    UB_DEPLETION_SHA256,
    HistoricalIrrigationEnvironment,
    load_observed,
    observed_requests,
)
from examples.irrigation_abm.irrigation_env import (
    UB_SUBBASINS,
    IrrigationEnvironment,
    WaterSystemConfig,
)


HINDCAST_FIRST_YEAR = 2000
HINDCAST_LAST_YEAR = 2018
HINDCAST_ANCHOR_YEAR = HINDCAST_FIRST_YEAR - 1

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(__file__).resolve().parent / "data"
HINDCAST_PRECIP_CSV = DATA_DIR / "hindcast_precip_v3.csv"
HINDCAST_PRECIP_SHA256 = "9989fb2d9bbc77c4a4c873b202a371510d9ecf9ea285229899e1c42a58c97a41"
PRECIP_SOURCE_CSV = (
    REPO_ROOT
    / "ref"
    / "CRSS_DB"
    / "CRSS_DB"
    / "HistoricalData"
    / "PrismWinterPrecip_NOAA_Winter_1905-2018.csv"
)
PRECIP_SOURCE_SHA256 = "3859730d4ce90e786566fb469c05e7fc74d9a63a5c0d0d2c18d15d98fd24d973"
MEAD_LEVELS_CSV = (
    REPO_ROOT
    / "ref"
    / "CRSS_DB"
    / "CRSS_DB"
    / "HistoricalData"
    / "Lake_Mead_Historical_WaterLevels.csv"
)
MEAD_LEVELS_SHA256 = "38bb2a315112ba861154eeef849afbd4f4ab3d88f3d91683a8b3952b9da48bbd"
AGENT_TEXT_HANDLING = (
    "unchanged: all projection text kept; spec section 6 items F1 to F6 await the PI"
)
HINDCAST_LIMITS = [
    "B=X contains window",
    "A_s=c_s*Q_s contains window",
    "5.2 MAF fitted 2003-2018",
    "FQL tables trained through 2018",
]


def _sha256_checked_bytes(path: Path, expected: str) -> bytes:
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(
            f"{path} has sha256 {actual}, expected {expected}; refusing to use unverified data."
        )
    return data


def hindcast_config_kwargs(config: Optional[WaterSystemConfig] = None) -> Dict[str, Any]:
    """Return the calendar window and recorded 1 January 2000 reservoir state."""
    observed = load_observed()
    dead_pool_maf = (
        config.powell_dead_pool_maf if config is not None else WaterSystemConfig().powell_dead_pool_maf
    )
    anchor = observed[HINDCAST_ANCHOR_YEAR]
    return {
        "sim_start_year": HINDCAST_FIRST_YEAR,
        "sim_end_year": HINDCAST_LAST_YEAR,
        "mead_initial_elevation": anchor["mead_elev_ft_eoy"],
        "powell_initial_storage_maf": anchor["powell_live_af_eoy"] / 1e6 + dead_pool_maf,
    }


def reanchor_profiles(profiles: Iterable[Any]) -> list[Any]:
    """Copy profiles with their two historical-use fields set to 1998 and 1999."""
    profile_list = list(profiles)
    requests = observed_requests(profile_list, [HINDCAST_ANCHOR_YEAR - 1, HINDCAST_ANCHOR_YEAR])
    return [
        replace(
            profile,
            actual_2018_diversion=requests[HINDCAST_ANCHOR_YEAR][profile.agent_id],
            actual_2017_diversion=requests[HINDCAST_ANCHOR_YEAR - 1][profile.agent_id],
        )
        for profile in profile_list
    ]


def _hindcast_precip_inches() -> Dict[int, Dict[str, float]]:
    text = _sha256_checked_bytes(HINDCAST_PRECIP_CSV, HINDCAST_PRECIP_SHA256).decode("utf-8")
    rows: Dict[int, Dict[str, float]] = {}
    for row in csv.DictReader(text.splitlines()):
        year_text = row.get("") or row.get("year")
        if year_text is None:
            raise ValueError(f"{HINDCAST_PRECIP_CSV} has no year column")
        rows[int(year_text)] = {group: float(row[group]) for group in UB_SUBBASINS}
    return rows


def _mead_dec_levels() -> Dict[int, float]:
    text = _sha256_checked_bytes(MEAD_LEVELS_CSV, MEAD_LEVELS_SHA256).decode("utf-8-sig")
    return {int(row["Year"]): float(row["DEC"]) for row in csv.DictReader(text.splitlines())}


def initial_pf_prev(profiles: Iterable[Any]) -> Dict[str, int]:
    """Return H&Y preceding-factor flags for the recorded 1998 to 1999 change."""
    precip = _hindcast_precip_inches()
    mead = _mead_dec_levels()
    previous = precip[HINDCAST_ANCHOR_YEAR - 1]
    current = precip[HINDCAST_ANCHOR_YEAR]
    lower_basin_flag = int(
        mead[HINDCAST_ANCHOR_YEAR - 1] >= mead[HINDCAST_ANCHOR_YEAR - 2]
    )
    out: Dict[str, int] = {}
    for profile in profiles:
        if profile.basin == "upper_basin":
            group = profile.precip_group
            if group not in UB_SUBBASINS:
                raise ValueError(
                    f"{profile.agent_id}: precip_group={group!r} is not one of {UB_SUBBASINS}"
                )
            out[profile.agent_id] = int(current[group] > previous[group])
        else:
            out[profile.agent_id] = lower_basin_flag
    return out


def hindcast_provenance(
    config: WaterSystemConfig,
    *,
    fql_init: Optional[str] = None,
    fql_init_dir: Optional[Any] = None,
    code_commit: Optional[str] = None,
    git_dirty: Optional[bool] = None,
) -> Dict[str, Any]:
    """Return the manifest block that identifies a hindcast run and its pinned inputs."""
    block: Dict[str, Any] = {
        "mode": "hindcast",
        "window": [HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR],
        "anchor_year": HINDCAST_ANCHOR_YEAR,
        "observed_csv_sha256": OBSERVED_CSV_SHA256,
        "precip_csv_sha256": HINDCAST_PRECIP_SHA256,
        "precip_source_sha256": PRECIP_SOURCE_SHA256,
        "ub_depletion_sha256": UB_DEPLETION_SHA256,
        "lb_diversion_sha256": LB_DIVERSION_SHA256,
        "mead_levels_sha256": MEAD_LEVELS_SHA256,
        "tier_start_year": TIER_START_YEAR,
        "pre2008_release_rule": "LROC stand-in (assumption)",
        "powell_release_mode": config.powell_release_mode,
        "lb_non_ag_total_maf": config.lb_non_ag_total_maf,
        "lb_return_flow_fraction": config.lb_return_flow_fraction,
        "agent_text_handling": AGENT_TEXT_HANDLING,
        "limits": list(HINDCAST_LIMITS),
        "code_commit": code_commit,
        "git_dirty": git_dirty,
    }
    if fql_init is not None or fql_init_dir is not None:
        block.update(
            {
                "fql_init": fql_init,
                "fql_init_dir": str(fql_init_dir) if fql_init_dir is not None else None,
                "fql_trained_through": 2018,
            }
        )
    return block


class HindcastAgentEnvironment(HistoricalIrrigationEnvironment):
    """Historical inputs with the ordinary request-reset and agent-decision path."""
    # Inherits tier 0 before 2008 and the Powell stand-in from analysis/hindcast_v3.py (HistoricalIrrigationEnvironment).

    def __init__(
        self,
        config: WaterSystemConfig,
        *,
        observed: Optional[Dict[int, Dict[str, float]]] = None,
        coupling_contract_active: bool = False,
    ) -> None:
        _sha256_checked_bytes(HINDCAST_PRECIP_CSV, HINDCAST_PRECIP_SHA256)
        _sha256_checked_bytes(PRECIP_SOURCE_CSV, PRECIP_SOURCE_SHA256)
        mead = _mead_dec_levels()
        IrrigationEnvironment.__init__(
            self,
            config,
            coupling_contract_active=coupling_contract_active,
        )
        self._observed = observed if observed is not None else load_observed()
        self._requests_by_year: Dict[int, Dict[str, float]] = {}
        self._observed_release = False
        trend_seed_year = HINDCAST_ANCHOR_YEAR - 1
        if trend_seed_year not in mead:
            raise ValueError(
                f"pinned Lake Mead record has no December {trend_seed_year} level"
            )
        self._mead_history = [mead[trend_seed_year]]

    def advance_year(self) -> Dict[str, Any]:
        return IrrigationEnvironment.advance_year(self)

    def _ub_subbasin_supply_row_for_year(self, year: int) -> Dict[str, float]:
        return {f"q_{subbasin}_af": self._row(year)[f"q_{subbasin}_af"] for subbasin in UB_SUBBASINS}
