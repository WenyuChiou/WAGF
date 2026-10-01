"""Historical hindcast of the irrigation v3 water system against observed Lake Mead and Lake Powell.

What it does
    Drives the committed ``IrrigationEnvironment`` with observed calendar-year inputs (USBR natural
    flow at Lees Ferry and intervening natural flow to below Hoover Dam, the Upper Basin sub-basin
    supply A_s = c_s x Q_s, and Hung and Yang's observed Upper Basin depletions and Lower Basin
    diversions as requests held fixed within each year) from the observed 1 January reservoir
    storages, and scores the simulated 1 January Mead and Powell against the USBR record with the
    rule pre-registered on 2026-09-29 (.research/design_specs/irrigation_v3_hindcast_2026-09-29.md,
    section 1), applied to the 1 January values after the start:
      M1  Lake Mead elevation MAE <= 25 ft
      M2  Mead elevation change over the window: observed sign, sim/obs ratio in [0.5, 1.5]
      M3  combined Powell + Mead total storage: |mean bias| <= 2.5 MAF, and its change over the
          window with the observed sign and a ratio in [0.5, 1.5]
    It also runs the split-sample check of the Lower Basin non-farm constant
    (``WaterSystemConfig.lb_non_ag_total_maf``): the record-implied value is derived on 2003-2010
    and scored on 2011-2018, and the reverse.

Minimal subclass (the only code this needs beyond the public config)
    ``HistoricalIrrigationEnvironment`` overrides
      (1) the four per-year data lookups (``_natural_flow_for_year``, ``_lb_tributary_for_year``,
          ``_ub_subbasin_available_maf_for_year``, ``_calendar_year_for``), which in the committed
          environment read the sha256-pinned 2019-2060 trace tables;
      (2) ``_compute_shortage_tier``: no tier before 2008 (the 2007 Interim Guidelines);
      (3) ``advance_year``: with ``hold_requests_fixed=True`` the environment never resets requests,
          but its own ``advance_year`` commits last year's settlement at the CURRENT requests, so the
          subclass commits that settlement first (the same ``settle_year`` + ``_commit_settlement``
          pair ``advance_year`` uses), then installs this year's observed requests, then calls the
          committed ``advance_year``, which plans the Powell release from them;
      (4) optionally ``_plan_powell_release`` (``observed_release=True``, a diagnostic only).
    Water-balance physics is untouched. Validated 2026-09-29: bitwise identical to a variant that sets
    the requests through ``_reset_requests_to_base`` instead.

Data (sha256-pinned below): examples/irrigation_abm/data/hindcast_observed_v3.csv (sources and
units in hindcast_observed_v3_sources.csv; built by tools/make_hindcast_observed_v3.py), and the
H&Y files ref/CRSS_DB/CRSS_DB/HistoricalData/{UB_historical_annual_depletion,
LB_historical_annual_diversion}.csv.

Usage:
    python examples/irrigation_abm/analysis/hindcast_v3.py [--lb-non-ag-total-maf 5.2] [--out DIR]
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.irrigation_abm.irrigation_env import (  # noqa: E402
    POWELL_EQ_ELEVATION_FT_BY_YEAR, POWELL_MIN_OBJECTIVE_RELEASE_MAF,
    UB_SUBBASINS, IrrigationEnvironment, PowellReleasePlan, WaterSystemConfig,
)
from examples.irrigation_abm.irrigation_personas import create_profiles_from_data  # noqa: E402

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
OBSERVED_CSV = DATA_DIR / "hindcast_observed_v3.csv"
OBSERVED_CSV_SHA256 = "847428b679c9e894ff1f57cbcd28738fc1b55a8d45e8389fd25852280848a37d"
CRSS_DB_DIR = REPO_ROOT / "ref" / "CRSS_DB" / "CRSS_DB"
PARAMS_CSV = REPO_ROOT / "ref" / "RL-ABM-CRSS" / "ALL_colorado_ABM_params_cal_1108.csv"
UB_DEPLETION_CSV = CRSS_DB_DIR / "HistoricalData" / "UB_historical_annual_depletion.csv"
UB_DEPLETION_SHA256 = "097fc2cbf48529b8f691f0cc76002e84b7ca9140cdf202ef797326d5d1910542"
LB_DIVERSION_CSV = CRSS_DB_DIR / "HistoricalData" / "LB_historical_annual_diversion.csv"
LB_DIVERSION_SHA256 = "efabba8031457a3f8029b87be3992cb134562f8dadefd4411aff9655b2cd121c"

TIER_START_YEAR = 2008        # 2007 Interim Guidelines shortage tiers apply from 2008
M1_MAX_MAE_FT = 25.0          # pre-registered 2026-09-29
M3_MAX_BIAS_MAF = 2.5         # pre-registered 2026-09-29
RATIO_BAND = (0.5, 1.5)       # pre-registered 2026-09-29
SPLIT_HALVES = ((2003, 2010), (2011, 2018))


def _sha256_checked_bytes(path: Path, expected: str) -> bytes:
    data = Path(path).read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        raise ValueError(f"{path} has sha256 {actual}, expected {expected}; refusing to use unverified data.")
    return data


def load_observed(path: Path = OBSERVED_CSV) -> Dict[int, Dict[str, float]]:
    """Rows keyed by calendar year (1999-2018). Reservoir columns are end-of-December values."""
    text = _sha256_checked_bytes(path, OBSERVED_CSV_SHA256).decode("utf-8")
    return {int(r["year"]): {k: float(v) for k, v in r.items() if k != "year"}
            for r in csv.DictReader(text.splitlines())}


def load_profiles(seed: int = 0):
    """The 78 real agents (the seed only affects persona text, not water rights or grid tops)."""
    return create_profiles_from_data(str(PARAMS_CSV), str(CRSS_DB_DIR), rng=np.random.default_rng(seed))


def observed_requests(profiles, years: Iterable[int]) -> Dict[int, Dict[str, float]]:
    """Per-agent observed requests (AF). LB: H&Y's diversion file. UB: the sub-basin's depletion (kaf)
    split across its agents by the same grid-top share create_profiles_from_data uses for 2018."""
    import io
    import pandas as pd

    ub = pd.read_csv(io.BytesIO(_sha256_checked_bytes(UB_DEPLETION_CSV, UB_DEPLETION_SHA256)), index_col=0)
    lb = pd.read_csv(io.BytesIO(_sha256_checked_bytes(LB_DIVERSION_CSV, LB_DIVERSION_SHA256)), index_col=0)
    group_top: Dict[str, float] = {}
    for p in profiles:
        if p.basin == "upper_basin":
            group_top[p.precip_group] = group_top.get(p.precip_group, 0.0) + p.grid_top_af
    out: Dict[int, Dict[str, float]] = {}
    for y in years:
        out[y] = {
            p.agent_id: (float(ub.loc[y, p.precip_group]) * 1000.0 * p.grid_top_af / group_top[p.precip_group]
                         if p.basin == "upper_basin" else float(lb.loc[y, p.agent_id]))
            for p in profiles
        }
    return out


class HistoricalIrrigationEnvironment(IrrigationEnvironment):
    """The v3 environment on historical calendar years (see the module docstring)."""

    def __init__(self, config: WaterSystemConfig, observed: Dict[int, Dict[str, float]],
                 requests_by_year: Dict[int, Dict[str, float]], *, observed_release: bool = False):
        if not config.hold_requests_fixed:
            raise ValueError("HistoricalIrrigationEnvironment needs WaterSystemConfig(hold_requests_fixed=True)")
        super().__init__(config)
        self._observed = observed
        self._requests_by_year = requests_by_year
        self._observed_release = observed_release

    def _row(self, year: int) -> Dict[str, float]:
        if year not in self._observed:
            raise ValueError(f"no observed row for calendar year {year}")
        return self._observed[year]

    # (1) per-year data: calendar years, not the 2019-2060 trace tables
    def _natural_flow_for_year(self, year: int) -> float:
        return self._row(year)["lees_ferry_natural_af"] / 1e6

    def _lb_tributary_for_year(self, year: int) -> float:
        if self.config.lb_tributary_source == "constant":
            return float(self.config.lb_tributary_maf)
        return self._row(year)["intervening_natural_af"] / 1e6

    def _ub_subbasin_available_maf_for_year(self, year: int) -> Dict[str, float]:
        return {s: self._row(year)[f"a_{s}_af"] / 1e6 for s in UB_SUBBASINS}

    def _calendar_year_for(self, year: int) -> int:
        return int(year)

    # (2) no shortage tiers before the 2007 Interim Guidelines
    def _compute_shortage_tier(self) -> int:
        if self._current_year < TIER_START_YEAR:
            return 0
        return super()._compute_shortage_tier()

    # (3) observed requests, held fixed within each year
    def advance_year(self) -> Dict[str, Any]:
        if self._snapshot is not None:
            self._commit_settlement(self.settle_year(), year=self._current_year)
            self._snapshot = None
        for aid, af in self._requests_by_year[self._current_year + 1].items():
            self._agents[aid]["request"] = float(af)
        return super().advance_year()

    # (4) diagnostic only: the observed Glen Canyon release (USGS 09380000) replaces the balancing rule
    def _plan_powell_release(self, *args, **kwargs) -> float:
        planned = super()._plan_powell_release(*args, **kwargs)
        if self._observed_release:
            return self._row(self._current_year)["lees_ferry_release_af"] / 1e6
        return planned

    # (5) pre-2008 LROC stand-in (re-review 2026-09-29 round 4, LOW 10a):
    # moved OUT of the production ig2007-tiers method, which the real
    # 2019-2060 corpus never calls for a year this early -- only this
    # hindcast (primary window from 2000; the secondary window, reported
    # not gated, from 1990) ever does. year >= 2008 delegates unchanged to
    # the production tiers. ASSUMPTION, not ROD content (design memo
    # section 3): the ROD's own p. 15 description of pre-2008 operations
    # states only the 8.23 MAF/yr "minimum objective release" concept, no
    # elevation number, so this reuses the FIRST published Equalization
    # elevation (3,636 ft, water year 2008) as the pre-Guidelines
    # equalization threshold -- our own stand-in, not something the ROD
    # states for this period. No 1,105 ft proviso and no April step (the
    # ROD describes neither before the Guidelines exist). The hindcast
    # headline (M1/M3/KGE) depends on this stand-in for the 8 pre-2008
    # years of the primary 2000-2018 window (docs/irrigation_model_caveats.md
    # caveat 17).
    def _plan_powell_release_ig2007(
        self, nf, s_p, s_m, trib, shortage_volume, mexico,
        ub_requested_maf, lb_requested_maf, *, year,
        ub_requested_by_subbasin_maf=None, ub_available_by_subbasin_maf=None,
    ) -> PowellReleasePlan:
        if year >= 2008:
            return super()._plan_powell_release_ig2007(
                nf, s_p, s_m, trib, shortage_volume, mexico,
                ub_requested_maf, lb_requested_maf, year=year,
                ub_requested_by_subbasin_maf=ub_requested_by_subbasin_maf,
                ub_available_by_subbasin_maf=ub_available_by_subbasin_maf,
            )
        cfg = self.config
        pieces = self._plan_powell_release_projected_pieces(
            nf, s_p, s_m, shortage_volume, mexico,
            lb_requested_maf=lb_requested_maf, ub_requested_maf=ub_requested_maf,
            ub_requested_by_subbasin_maf=ub_requested_by_subbasin_maf,
            ub_available_by_subbasin_maf=ub_available_by_subbasin_maf,
        )
        p0 = s_p + pieces.inflow_plan - pieces.e_p_plan - cfg.powell_dead_pool_maf
        m0 = s_m + trib - pieces.e_m_estimate - pieces.o_projected - cfg.mead_dead_pool_maf
        r_bal = (p0 - m0) / 2.0
        a_p = max(0.0, s_p - cfg.powell_dead_pool_maf)
        eq_ft = POWELL_EQ_ELEVATION_FT_BY_YEAR[2008]
        a_eq = self._powell_active_storage_at(eq_ft)
        if a_p >= a_eq:
            r_floor = p0 - a_eq  # release that keeps Powell exactly at the EQ elevation on 31 Dec
            release = max(POWELL_MIN_OBJECTIVE_RELEASE_MAF, min(r_bal, r_floor))
            tier, rule = "LROC", "LROC equalization"
        else:
            release, tier, rule = POWELL_MIN_OBJECTIVE_RELEASE_MAF, "LROC", "LROC 8.23"
        return PowellReleasePlan(
            release_maf=min(release, pieces.available_p_plan), tier=tier, rule=rule,
            powell_jan1_ft=self._powell_elevation_ft(s_p), eq_elevation_ft=eq_ft,
        )


def mead_total_maf(elevation_ft: float) -> float:
    """Total storage (incl. dead storage) on the model's own USBR 2009 curve."""
    return float(np.interp(elevation_ft, IrrigationEnvironment._ELEVATION_FT, IrrigationEnvironment._STORAGE_MAF))


def mead_elevation_ft(total_maf: float) -> float:
    return float(np.interp(total_maf, IrrigationEnvironment._STORAGE_MAF, IrrigationEnvironment._ELEVATION_FT))


def _kge(sim: np.ndarray, obs: np.ndarray) -> float:
    """Kling-Gupta efficiency (Gupta et al. 2009)."""
    r = float(np.corrcoef(sim, obs)[0, 1])
    return float(1.0 - np.sqrt((r - 1.0) ** 2 + (sim.std() / obs.std() - 1.0) ** 2 + (sim.mean() / obs.mean() - 1.0) ** 2))


@dataclass
class HindcastResult:
    first: int
    last: int
    lb_non_ag_total_maf: float
    observed_release: bool
    # Re-review 2026-09-29 round 5, L2: the RESOLVED mode (env.config's own
    # value, never the possibly-None input param), so every result -- including
    # one that relied on WaterSystemConfig's own default -- reports which rule
    # it actually ran under.
    powell_release_mode: str = "ig2007_tiers"
    metrics: Dict[str, float] = field(default_factory=dict)
    gate: Dict[str, bool] = field(default_factory=dict)
    series: List[Dict[str, float]] = field(default_factory=list)

    @property
    def passes(self) -> bool:
        return all(self.gate.values())


def run_hindcast(first: int = 2000, last: int = 2018, *, lb_non_ag_total_maf: Optional[float] = None,
                 powell_release_mode: Optional[str] = None,
                 powell_post2026_equalization: Optional[str] = None,
                 observed_release: bool = False, profiles=None, observed=None, requests=None) -> HindcastResult:
    """Simulate calendar years first..last from the observed 1 January storages of ``first`` and score
    the 1 January values of first+1..last+1. ``lb_non_ag_total_maf=None`` uses the config default.
    ``powell_release_mode`` (re-review 2026-09-29 round 4, LOW 6): "ig2007_tiers" (the config default,
    unset) or "storage_balancing" -- lets a caller reproduce the pre-item-26/27 hindcast numbers
    (13.0 ft / +1.09 MAF / KGE 0.74 at 5.2 MAF; ``test_v3_powell_tiers.py::TestStorageBalancingHindcast``)
    without a separate driver. ``powell_post2026_equalization`` is accepted for the same reason but never
    exercised by this 2000-2018 window (the SI's own post-2026 sensitivity uses the 2019-2060 projection
    instead)."""
    observed = observed if observed is not None else load_observed()
    profiles = profiles if profiles is not None else load_profiles()
    requests = requests if requests is not None else observed_requests(profiles, range(first, last + 1))
    dead_pool = WaterSystemConfig().powell_dead_pool_maf
    kw: Dict[str, Any] = dict(
        hold_requests_fixed=True, sim_start_year=first, sim_end_year=last,
        mead_initial_elevation=observed[first - 1]["mead_elev_ft_eoy"],
        powell_initial_storage_maf=observed[first - 1]["powell_live_af_eoy"] / 1e6 + dead_pool,
    )
    if lb_non_ag_total_maf is not None:
        kw["lb_non_ag_total_maf"] = float(lb_non_ag_total_maf)
    if powell_release_mode is not None:
        kw["powell_release_mode"] = str(powell_release_mode)
    if powell_post2026_equalization is not None:
        kw["powell_post2026_equalization"] = str(powell_post2026_equalization)
    env = HistoricalIrrigationEnvironment(WaterSystemConfig(**kw), observed, requests, observed_release=observed_release)
    env.initialize_from_profiles(profiles)
    res = HindcastResult(first, last, env.config.lb_non_ag_total_maf, observed_release,
                        powell_release_mode=env.config.powell_release_mode)
    for t in range(first, last + 1):
        env.advance_year()
        st = env.settle_year()
        dS = (st["powell_storage_end_maf"] - st["powell_storage_maf"]) + (st["mead_storage_end_maf"] - st["mead_storage_maf"])
        flux = (st["natural_flow_maf"] + st["lb_tributary_maf"] - st["ub_non_farm_maf"] - st["ub_delivered_maf"]
                - st["powell_evap_maf"] - st["mead_evap_maf"] - st["lb_delivered_maf"] - st["lb_non_ag_delivered_maf"]
                - st["mexico_delivered_maf"] - st["mead_spill_maf"])
        assert abs(dS - flux) < 1e-9, f"mass balance does not close in {t}"
        o = observed[t]
        res.series.append({
            "jan1": t + 1, "tier_during_year": env._compute_shortage_tier(),
            "mead_elev_sim": mead_elevation_ft(st["mead_storage_end_maf"]), "mead_elev_obs": o["mead_elev_ft_eoy"],
            "mead_total_sim": st["mead_storage_end_maf"], "mead_total_obs": mead_total_maf(o["mead_elev_ft_eoy"]),
            "powell_total_sim": st["powell_storage_end_maf"], "powell_total_obs": o["powell_live_af_eoy"] / 1e6 + dead_pool,
            "powell_elev_sim": env._powell_elevation_ft(st["powell_storage_end_maf"]),
            "powell_elev_obs": o["powell_elev_ft_eoy"],
            "release_sim": st["powell_release_maf"], "release_obs": o["lees_ferry_release_af"] / 1e6,
        })
    _score(res, observed, dead_pool)
    return res


def _score(res: HindcastResult, observed: Dict[int, Dict[str, float]], dead_pool: float) -> None:
    s = res.series
    me_sim = np.array([x["mead_elev_sim"] for x in s]); me_obs = np.array([x["mead_elev_obs"] for x in s])
    c_sim = np.array([x["mead_total_sim"] + x["powell_total_sim"] for x in s])
    c_obs = np.array([x["mead_total_obs"] + x["powell_total_obs"] for x in s])
    pe_sim = np.array([x["powell_elev_sim"] for x in s]); pe_obs = np.array([x["powell_elev_obs"] for x in s])
    rel_sim = np.array([x["release_sim"] for x in s]); rel_obs = np.array([x["release_obs"] for x in s])
    o0 = observed[res.first - 1]
    me0 = o0["mead_elev_ft_eoy"]
    c0 = mead_total_maf(me0) + o0["powell_live_af_eoy"] / 1e6 + dead_pool
    d_me_obs, d_me_sim = me_obs[-1] - me0, me_sim[-1] - me0
    d_c_obs, d_c_sim = c_obs[-1] - c0, c_sim[-1] - c0
    res.metrics = {
        "M1_mead_mae_ft": float(np.abs(me_sim - me_obs).mean()),
        "M2_mead_change_ratio": float(d_me_sim / d_me_obs),
        "M3_combined_bias_maf": float((c_sim - c_obs).mean()),
        "M3_combined_change_ratio": float(d_c_sim / d_c_obs),
        "mead_bias_ft": float((me_sim - me_obs).mean()),
        "mead_rmse_ft": float(np.sqrt(((me_sim - me_obs) ** 2).mean())),
        "mead_kge": _kge(me_sim, me_obs),
        "combined_rmse_maf": float(np.sqrt(((c_sim - c_obs) ** 2).mean())),
        "combined_kge": _kge(c_sim, c_obs),
        "mead_change_obs_ft": float(d_me_obs), "mead_change_sim_ft": float(d_me_sim),
        # re-review 2026-09-29 round 4 (LOW 6): release RMSE/r and Powell
        # elevation MAE, reported (not gated) in the design memo's own
        # headline table -- computed here so main() need not re-derive
        # them from a second driver script.
        "powell_mae_ft": float(np.abs(pe_sim - pe_obs).mean()),
        "release_rmse_maf": float(np.sqrt(((rel_sim - rel_obs) ** 2).mean())),
        "release_r": float(np.corrcoef(rel_sim, rel_obs)[0, 1]),
    }
    lo, hi = RATIO_BAND
    res.gate = {
        "M1": res.metrics["M1_mead_mae_ft"] <= M1_MAX_MAE_FT,
        "M2": bool(np.sign(d_me_sim) == np.sign(d_me_obs)) and lo <= res.metrics["M2_mead_change_ratio"] <= hi,
        "M3_bias": abs(res.metrics["M3_combined_bias_maf"]) <= M3_MAX_BIAS_MAF,
        "M3_change": bool(np.sign(d_c_sim) == np.sign(d_c_obs)) and lo <= res.metrics["M3_combined_change_ratio"] <= hi,
    }


def record_implied_non_ag(years: Iterable[int], *, profiles=None, observed=None, requests=None) -> float:
    """Mean over ``years`` of the Lower Basin non-farm withdrawal that closes the model's own Lake Mead
    balance given the record:
        N(t) = intervening natural flow + observed release - observed change in Mead storage
               - model Mead evaporation at the observed 1 January storage
               - the 22 LB agents' observed diversions (clipped to the water right, as the model does)
               - the model's Mexico delivery at the observed 1 January elevation
    (no tier cut: no Lower Basin shortage was declared before 2022)."""
    years = list(years)
    observed = observed if observed is not None else load_observed()
    profiles = profiles if profiles is not None else load_profiles()
    requests = requests if requests is not None else observed_requests(profiles, years)
    env = IrrigationEnvironment(WaterSystemConfig())
    wr = {p.agent_id: p.water_right for p in profiles}
    lb_ids = [p.agent_id for p in profiles if p.basin != "upper_basin"]
    vals = []
    for t in years:
        h0, h1 = observed[t - 1]["mead_elev_ft_eoy"], observed[t]["mead_elev_ft_eoy"]
        s0, s1 = mead_total_maf(h0), mead_total_maf(h1)
        vals.append((observed[t]["intervening_natural_af"] + observed[t]["lees_ferry_release_af"]) / 1e6
                    - (s1 - s0) - env._mead_evaporation_maf(s0)
                    - sum(min(requests[t][a], wr[a]) for a in lb_ids) / 1e6
                    - env._mexico_delivery_maf(h0))
    return float(np.mean(vals))


def split_sample(value: Optional[float] = None, *, powell_release_mode: Optional[str] = None,
                 powell_post2026_equalization: Optional[str] = None,
                 profiles=None, observed=None) -> List[Dict[str, Any]]:
    """Derive the record-implied constant on each half and score the other half with it (model release
    rule), then score ``value`` (default: the config default) on each half, then repeat the held-out
    runs with the observed release to isolate the Lake Mead side.

    ``powell_release_mode`` / ``powell_post2026_equalization`` (re-review 2026-09-29 round 5, L2: this
    function previously ignored both, so ``main()``'s ``--powell-release-mode`` only ever reached the
    "pre-registered" and "reference 5.0" rows, never the split-sample ones): threaded into every
    ``run_hindcast`` call below, exactly like ``run_hindcast`` itself threads them into
    ``WaterSystemConfig``. ``None`` (default) leaves the config's own default in effect, as before."""
    observed = observed if observed is not None else load_observed()
    profiles = profiles if profiles is not None else load_profiles()
    requests = observed_requests(profiles, range(SPLIT_HALVES[0][0], SPLIT_HALVES[1][1] + 1))
    kw = dict(profiles=profiles, observed=observed, requests=requests)
    mode_kw: Dict[str, Any] = {}
    if powell_release_mode is not None:
        mode_kw["powell_release_mode"] = powell_release_mode
    if powell_post2026_equalization is not None:
        mode_kw["powell_post2026_equalization"] = powell_post2026_equalization
    derived = {h: record_implied_non_ag(range(h[0], h[1] + 1), **kw) for h in SPLIT_HALVES}
    rows = []
    for (cal, score) in ((SPLIT_HALVES[0], SPLIT_HALVES[1]), (SPLIT_HALVES[1], SPLIT_HALVES[0])):
        for obs_rel in (False, True):
            r = run_hindcast(score[0], score[1], lb_non_ag_total_maf=derived[cal], observed_release=obs_rel,
                             **mode_kw, **kw)
            rows.append({"case": f"derived on {cal[0]}-{cal[1]}", "window": f"{score[0]}-{score[1]}", "result": r})
    for half in SPLIT_HALVES:
        r = run_hindcast(half[0], half[1], lb_non_ag_total_maf=value, **mode_kw, **kw)
        rows.append({"case": "fixed value", "window": f"{half[0]}-{half[1]}", "result": r})
    return rows


def _row(case: str, window: str, r: HindcastResult) -> Dict[str, Any]:
    m, g = r.metrics, r.gate
    return {"case": case, "window": window,
            # Re-review 2026-09-29 round 5, L2: which rule this row actually
            # ran under -- was previously invisible once a row came out of
            # split_sample(), which had no way to receive it at all.
            "powell_release_mode": r.powell_release_mode,
            "lb_non_ag_total_maf": round(r.lb_non_ag_total_maf, 3),
            "release": "observed" if r.observed_release else "model rule",
            "M1_mae_ft": round(m["M1_mead_mae_ft"], 1), "M2_ratio": round(m["M2_mead_change_ratio"], 2),
            "M3_bias_maf": round(m["M3_combined_bias_maf"], 2), "M3_ratio": round(m["M3_combined_change_ratio"], 2),
            "M1": g["M1"], "M2": g["M2"], "M3_bias": g["M3_bias"], "M3_change": g["M3_change"],
            "mead_bias_ft": round(m["mead_bias_ft"], 1), "mead_rmse_ft": round(m["mead_rmse_ft"], 1),
            "mead_kge": round(m["mead_kge"], 2),
            # re-review 2026-09-29 round 4 (LOW 6): reported (not gated) in
            # the design memo's own headline table.
            "powell_mae_ft": round(m["powell_mae_ft"], 1),
            "release_rmse_maf": round(m["release_rmse_maf"], 2), "release_r": round(m["release_r"], 2)}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--lb-non-ag-total-maf", type=float, default=None,
                    help="LB non-farm total (MAF); default: WaterSystemConfig's default")
    ap.add_argument("--powell-release-mode", choices=["ig2007_tiers", "storage_balancing"], default=None,
                    help="Powell release rule (re-review 2026-09-29 round 4, LOW 6); "
                         "default: WaterSystemConfig's default (ig2007_tiers)")
    ap.add_argument("--powell-post2026-equalization", choices=["hold_2026", "extend_slope"], default=None,
                    help="post-2026 Equalization elevation extension; unused by this 2000-2018 window "
                         "(accepted for CLI parity with WaterSystemConfig)")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "examples" / "irrigation_abm" / "results" / "hindcast_v3")
    a = ap.parse_args()
    observed, profiles = load_observed(), load_profiles()
    value = a.lb_non_ag_total_maf
    mode_kw: Dict[str, Any] = {}
    if a.powell_release_mode is not None:
        mode_kw["powell_release_mode"] = a.powell_release_mode
    if a.powell_post2026_equalization is not None:
        mode_kw["powell_post2026_equalization"] = a.powell_post2026_equalization
    rows = [_row("pre-registered", "2000-2018", run_hindcast(2000, 2018, lb_non_ag_total_maf=value,
                                                             profiles=profiles, observed=observed, **mode_kw))]
    effective = value if value is not None else WaterSystemConfig().lb_non_ag_total_maf
    if abs(effective - 5.0) > 1e-12:
        rows.append(_row("reference 5.0", "2000-2018", run_hindcast(2000, 2018, lb_non_ag_total_maf=5.0,
                                                                   profiles=profiles, observed=observed, **mode_kw)))
    rows += [_row(x["case"], x["window"], x["result"])
             for x in split_sample(value, profiles=profiles, observed=observed, **mode_kw)]
    a.out.mkdir(parents=True, exist_ok=True)
    path = a.out / "hindcast_v3_summary.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    cols = list(rows[0])
    print("| " + " | ".join(cols) + " |")
    print("|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(str(r[c]) for c in cols) + " |")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
