"""Score 2000-2018 irrigation agent hindcasts against recorded diversions."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from examples.irrigation_abm.analysis.hindcast_v3 import (  # noqa: E402
    LB_DIVERSION_CSV,
    LB_DIVERSION_SHA256,
    UB_DEPLETION_CSV,
    UB_DEPLETION_SHA256,
    load_profiles,
    observed_requests,
)
from examples.irrigation_abm.analysis.v3_metrics import CONSTANT_SIM_NOTE, Kge, kge  # noqa: E402
from examples.irrigation_abm.hindcast_env import (  # noqa: E402
    HINDCAST_FIRST_YEAR,
    HINDCAST_LAST_YEAR,
    HINDCAST_PRECIP_SHA256,
    MEAD_LEVELS_SHA256,
    OBSERVED_CSV_SHA256,
    PRECIP_SOURCE_SHA256,
)
from examples.irrigation_abm.irrigation_env import UB_SUBBASINS, WaterSystemConfig  # noqa: E402

MANIFEST = "reproducibility_manifest.json"
SIM_LOG = "simulation_log.csv"
SCORES_CSV = "hindcast_v3_agent_scores.csv"
REPORT_MD = "hindcast_v3_agent_scores.md"
YEARS = tuple(range(HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR + 1))
HISTORICAL_YEARS = (HINDCAST_FIRST_YEAR - 1,) + YEARS
QUANTITIES = ("request", "diversion")
LB_PREFIX = "lb:"
UB_PREFIX = "ub:"
MOCK_WARNING = "mock run: scores have no meaning"
DIRTY_WARNING = "run from a modified tree"
LLM_CONFIGURATION_FIELDS = (
    "model", "model_digest", "config_hash", "derived_from_config_sha256",
    "cluster_method", "paper_water_margin", "beneficial_use_limit", "keepfix_package",
    "memory_engine_class", "retry_feedback_mode", "llm_params_resolved",
    "thinking_mode", "llm_thinking", "llm_safeguard", "workers",
    "powell_release_mode", "powell_post2026_equalization", "lb_non_ag_total_maf",
    "lb_return_flow_fraction", "min_utilisation_fraction", "ub_supply_mode",
    "ub_subbasin_supply_variant", "lb_p56_in_tier", "ub_subbasin_supply_v3_sha256",
    "ub_subbasin_envelope_v3_sha256", "ub_subbasin_variant_means_v3_sha256",
)
PHYSICAL_FIELDS = (
    "cluster_method", "paper_water_margin", "hold_requests_fixed", "powell_release_mode",
    "powell_post2026_equalization", "lb_non_ag_total_maf", "lb_return_flow_fraction",
    "min_utilisation_fraction", "ub_supply_mode", "ub_subbasin_supply_variant",
    "lb_p56_in_tier",
)
HINDCAST_FIELDS = (
    "mode", "window", "anchor_year", "observed_csv_sha256", "precip_csv_sha256",
    "precip_source_sha256", "ub_depletion_sha256", "lb_diversion_sha256",
    "mead_levels_sha256", "tier_start_year", "pre2008_release_rule",
    "powell_release_mode", "lb_non_ag_total_maf", "lb_return_flow_fraction",
    "agent_text_handling", "limits",
)
FQL_PINNED_CHECKSUM_FIELDS = {
    "ub_subbasin_supply_v3_sha256": "ub_subbasin_supply_v3_csv",
    "ub_subbasin_envelope_v3_sha256": "ub_subbasin_envelope_v3_csv",
    "ub_subbasin_variant_means_v3_sha256": "ub_subbasin_variant_means_v3_csv",
}
SHARED_PINNED_CHECKSUM_FIELDS = {
    "hydrology_v3_sha256": "hydrology_v3_csv",
    "mead_capacity_sha256": "mead_capacity_usbr2009_1ft_csv",
    "lb_priority_split_sha256": "lb_priority_split_v3_csv",
}


class ScoreError(RuntimeError):
    """A run or historical input does not satisfy the scoring contract."""


def _checked_bytes(path: Path, expected_sha256: str) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise ScoreError(f"cannot read {path}: {exc}") from exc
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected_sha256:
        raise ScoreError(f"{path}: sha256 {actual}, expected {expected_sha256}")
    return data


def _finite(text: str | None, *, where: str) -> float:
    if text is None or not text.strip():
        raise ScoreError(f"{where}: missing numeric value")
    try:
        value = float(text)
    except ValueError as exc:
        raise ScoreError(f"{where}: {text!r} is not numeric") from exc
    if not math.isfinite(value):
        raise ScoreError(f"{where}: {text!r} is not finite")
    return value


def _whole_number(text: str | None, *, where: str) -> int:
    value = _finite(text, where=where)
    if value != int(value):
        raise ScoreError(f"{where}: {text!r} is not a whole number")
    return int(value)


def _historical_table(path: Path, sha256: str, scale_to_maf: float) -> dict[str, dict[int, float]]:
    data = _checked_bytes(path, sha256).decode("utf-8-sig")
    reader = csv.DictReader(data.splitlines())
    header = list(reader.fieldnames or [])
    if len(header) < 2:
        raise ScoreError(f"{path}: expected a year column and at least one series")
    year_column = header[0]
    names = header[1:]
    if not year_column.strip() == "":
        raise ScoreError(f"{path}: first column must be the unnamed year index")
    out = {name: {} for name in names}
    seen_years: set[int] = set()
    for line_number, row in enumerate(reader, 2):
        year = _whole_number(row.get(year_column), where=f"{path}:{line_number} year")
        if year in seen_years:
            raise ScoreError(f"{path}:{line_number}: duplicate year {year}")
        seen_years.add(year)
        if year not in HISTORICAL_YEARS:
            continue
        for name in names:
            value = _finite(row.get(name), where=f"{path}:{line_number} {name}")
            if value < 0:
                raise ScoreError(f"{path}:{line_number} {name}: negative volume {value}")
            out[name][year] = value * scale_to_maf
    missing_years = sorted(set(HISTORICAL_YEARS) - seen_years)
    if missing_years:
        raise ScoreError(f"{path}: missing historical years {missing_years}")
    return out


def recorded_series() -> dict[str, dict[int, float]]:
    """Return pinned recorded series in MAF, including the 1999 anchor."""
    ub = _historical_table(UB_DEPLETION_CSV, UB_DEPLETION_SHA256, 1.0 / 1000.0)
    lb = _historical_table(LB_DIVERSION_CSV, LB_DIVERSION_SHA256, 1.0 / 1_000_000.0)
    if tuple(ub) != tuple(UB_SUBBASINS):
        raise ScoreError(f"{UB_DEPLETION_CSV}: subbasins {tuple(ub)} do not match {tuple(UB_SUBBASINS)}")
    if len(lb) != 22:
        raise ScoreError(f"{LB_DIVERSION_CSV}: expected 22 agents, found {len(lb)}")
    result = {f"{UB_PREFIX}{name}": values for name, values in ub.items()}
    result.update({f"{LB_PREFIX}{name}": values for name, values in lb.items()})
    result[f"{UB_PREFIX}total"] = {
        year: sum(ub[name][year] for name in UB_SUBBASINS) for year in HISTORICAL_YEARS
    }
    result[f"{LB_PREFIX}total"] = {
        year: sum(lb[name][year] for name in lb) for year in HISTORICAL_YEARS
    }
    return result


def benchmark_series(
    recorded: Mapping[str, Mapping[int, float]] | None = None,
) -> dict[str, dict[str, dict[int, float]]]:
    """Build labelled persistence and constant-at-1999 benchmark series."""
    observed = recorded if recorded is not None else recorded_series()
    return {
        "persistence_recorded_prior_year": {
            name: {year: float(values[year - 1]) for year in YEARS}
            for name, values in observed.items()
        },
        "constant_recorded_1999": {
            name: {year: float(values[HINDCAST_FIRST_YEAR - 1]) for year in YEARS}
            for name, values in observed.items()
        },
    }


def _required(mapping: Mapping[str, Any], key: str, *, where: Path | str) -> Any:
    if key not in mapping:
        raise ScoreError(f"{where}: missing required manifest key {key!r}")
    return mapping[key]


def _required_values(
    mapping: Mapping[str, Any], fields: Sequence[str], *, where: Path | str,
) -> dict[str, Any]:
    return {key: _required(mapping, key, where=where) for key in fields}


def _manifest(run_dir: Path, kind: str) -> tuple[dict[str, Any], int, str]:
    path = run_dir / MANIFEST
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ScoreError(f"cannot read valid {path}: {exc}") from exc
    hindcast = manifest.get("hindcast")
    if not isinstance(hindcast, dict):
        raise ScoreError(f"{path}: missing hindcast manifest block; projection runs cannot be scored")
    _required_values(hindcast, HINDCAST_FIELDS, where=f"{path} hindcast")
    expected_window = [HINDCAST_FIRST_YEAR, HINDCAST_LAST_YEAR]
    if hindcast["mode"] != "hindcast" or hindcast["window"] != expected_window:
        raise ScoreError(f"{path}: expected hindcast mode and window {expected_window}")
    if hindcast["anchor_year"] != HINDCAST_FIRST_YEAR - 1:
        raise ScoreError(f"{path}: expected anchor_year {HINDCAST_FIRST_YEAR - 1}")
    for key, expected in (
        ("observed_csv_sha256", OBSERVED_CSV_SHA256),
        ("precip_csv_sha256", HINDCAST_PRECIP_SHA256),
        ("precip_source_sha256", PRECIP_SOURCE_SHA256),
        ("mead_levels_sha256", MEAD_LEVELS_SHA256),
    ):
        if hindcast[key] != expected:
            raise ScoreError(f"{path}: {key} does not match the scorer")
    if hindcast["ub_depletion_sha256"] != UB_DEPLETION_SHA256:
        raise ScoreError(f"{path}: Upper Basin historical pin does not match the scorer")
    if hindcast["lb_diversion_sha256"] != LB_DIVERSION_SHA256:
        raise ScoreError(f"{path}: Lower Basin historical pin does not match the scorer")
    seed = _required(manifest, "seed", where=path)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ScoreError(f"{path}: seed must be an integer")
    if kind == "fql":
        if _required(manifest, "runner", where=path) != "run_fql_baseline":
            raise ScoreError(f"{path}: --fql requires runner run_fql_baseline")
        fql_init = _required(manifest, "fql_init", where=path)
        if fql_init != "calibrated":
            raise ScoreError(f"{path}: hindcast FQL must use calibrated initialization")
        if _required(hindcast, "fql_trained_through", where=f"{path} hindcast") != 2018:
            raise ScoreError(f"{path}: expected fql_trained_through=2018")
        arm = "fql"
    else:
        if manifest.get("runner") == "run_fql_baseline":
            raise ScoreError(f"{path}: FQL run was passed through --llm")
        arm = str(manifest.get("governance_profile_resolved", manifest.get("governance_profile", ""))).strip()
        if not arm:
            raise ScoreError(f"{path}: missing resolved LLM governance arm")
        model = str(_required(manifest, "model", where=path)).strip()
        if not model:
            raise ScoreError(f"{path}: model must be a non-empty string")
    return manifest, seed, arm


def _signature(values: Mapping[str, Any]) -> str:
    return json.dumps(values, sort_keys=True)


def _code_commit(manifest: Mapping[str, Any], *, where: Path) -> str:
    hindcast = _required(manifest, "hindcast", where=where)
    fields = [("hindcast.code_commit", hindcast["code_commit"])] if "code_commit" in hindcast else []
    fields.extend((key, manifest[key]) for key in ("git_commit", "git_head") if key in manifest)
    if not fields:
        raise ScoreError(f"{where}: missing code commit (hindcast.code_commit or git_commit/git_head)")
    if "git_commit_at_finalize" in manifest:
        fields.append(("git_commit_at_finalize", manifest["git_commit_at_finalize"]))
    for key, value in fields:
        if not isinstance(value, str) or not value.strip():
            raise ScoreError(f"{where}: {key} must be a non-empty code commit string")
    first_key, commit = fields[0]
    commit = commit.strip()
    for key, value in fields[1:]:
        if value.strip() != commit:
            raise ScoreError(f"{where}: conflicting code commits: {first_key}={commit}, {key}={value}")
    return commit


def _dirty_tree(manifest: Mapping[str, Any], *, where: Path) -> bool:
    hindcast = _required(manifest, "hindcast", where=where)
    fields = [("hindcast.git_dirty", hindcast["git_dirty"])] if "git_dirty" in hindcast else []
    fields.extend((key, manifest[key]) for key in ("git_dirty", "git_dirty_at_finalize") if key in manifest)
    if not fields:
        raise ScoreError(f"{where}: missing dirty-tree manifest field")
    for key, value in fields:
        if not isinstance(value, bool):
            raise ScoreError(f"{where}: {key} must be a boolean dirty-tree field")
    return any(value for _, value in fields)


def _llm_signature(manifest: Mapping[str, Any], *, where: Path) -> str:
    """Normalize required LLM configuration fields, excluding governance mode."""
    return _signature(_required_values(manifest, LLM_CONFIGURATION_FIELDS, where=where))


def _ensemble_signature(manifest: Mapping[str, Any]) -> str:
    """Backward-compatible name for the required LLM ensemble signature."""
    return _llm_signature(manifest, where=Path(MANIFEST))


def _physical_signature(manifest: Mapping[str, Any], kind: str, *, where: Path) -> str:
    """Normalize physical fields shared by the structurally different run manifests."""
    values = _required_values(manifest, PHYSICAL_FIELDS, where=where)
    hindcast = _required(manifest, "hindcast", where=where)
    if not isinstance(hindcast, Mapping):
        raise ScoreError(f"{where}: hindcast must be an object")
    values["hindcast"] = _required_values(hindcast, HINDCAST_FIELDS, where=f"{where} hindcast")
    if kind == "llm":
        for field in FQL_PINNED_CHECKSUM_FIELDS:
            values[field] = _required(manifest, field, where=where)
        coupling = _required(manifest, "coupling_retrofit_metadata", where=where)
        if not isinstance(coupling, Mapping):
            raise ScoreError(f"{where}: coupling_retrofit_metadata must be an object")
        values["lb_priority_mode"] = _required(
            coupling, "water_system_lb_priority_mode", where=f"{where} coupling_retrofit_metadata",
        )
        values["lb_tributary_source"] = _required(
            coupling, "water_system_lb_tributary_source", where=f"{where} coupling_retrofit_metadata",
        )
        for field in SHARED_PINNED_CHECKSUM_FIELDS:
            values[field] = _required(
                coupling, f"water_system_{field}", where=f"{where} coupling_retrofit_metadata",
            )
    else:
        pinned = _required(manifest, "pinned_v3_data_checksums", where=where)
        if not isinstance(pinned, Mapping):
            raise ScoreError(f"{where}: pinned_v3_data_checksums must be an object")
        for field, nested_field in FQL_PINNED_CHECKSUM_FIELDS.items():
            values[field] = _required(pinned, nested_field, where=f"{where} pinned_v3_data_checksums")
        values["lb_priority_mode"] = _required(manifest, "lb_priority_mode", where=where)
        water_system = _required(manifest, "water_system_config", where=where)
        if not isinstance(water_system, Mapping):
            raise ScoreError(f"{where}: water_system_config must be an object")
        values["lb_tributary_source"] = _required(
            water_system, "lb_tributary_source", where=f"{where} water_system_config",
        )
        for field, nested_field in SHARED_PINNED_CHECKSUM_FIELDS.items():
            values[field] = _required(pinned, nested_field, where=f"{where} pinned_v3_data_checksums")
    return _signature(values)


def _fql_signature(manifest: Mapping[str, Any], *, where: Path) -> str:
    water_system = _required(manifest, "water_system_config", where=where)
    if not isinstance(water_system, Mapping):
        raise ScoreError(f"{where}: water_system_config must be an object")
    water_system = _required_values(
        water_system, tuple(WaterSystemConfig.__dataclass_fields__),
        where=f"{where} water_system_config",
    )
    values = {
        "fql_init": _required(manifest, "fql_init", where=where),
        "fql_init_dir_name": _required(manifest, "fql_init_dir_name", where=where),
        "fql_init_per_agent": _required(manifest, "fql_init_per_agent", where=where),
        "no_governance": _required(manifest, "no_governance", where=where),
        "crss_db_input_checksums": _required(manifest, "crss_db_input_checksums", where=where),
        "water_system_config": {key: value for key, value in water_system.items() if key != "seed"},
    }
    return _signature(values)


def _load_run_series(
    run_dir: Path, kind: str,
) -> tuple[dict[str, dict[str, dict[int, float]]], int, str]:
    _, seed, arm = _manifest(run_dir, kind)
    path = run_dir / SIM_LOG
    try:
        stream = path.open(encoding="utf-8-sig", newline="")
    except OSError as exc:
        raise ScoreError(f"cannot read {path}: {exc}") from exc
    with stream:
        reader = csv.DictReader(stream)
        required = {"agent_id", "year", "calendar_year", "basin", "ub_subbasin", *QUANTITIES}
        missing = sorted(required - set(reader.fieldnames or ()))
        if missing:
            raise ScoreError(f"{path}: missing columns {missing}")
        rows = list(reader)
    expected_rows = len(YEARS) * 78
    if len(rows) != expected_rows:
        raise ScoreError(f"{path}: expected {expected_rows} rows, found {len(rows)}")

    recorded = recorded_series()
    expected_lb = {name.removeprefix(LB_PREFIX) for name in recorded if name.startswith(LB_PREFIX)} - {"total"}
    profiles = load_profiles()
    expected_identity = {
        profile.agent_id: (profile.basin, profile.precip_group or "") for profile in profiles
    }
    if len(expected_identity) != 78:
        raise ScoreError("profile data does not contain 78 unique agent identities")
    by_year: dict[int, set[str]] = defaultdict(set)
    identity: dict[str, tuple[str, str]] = {}
    totals: dict[str, dict[str, dict[int, float]]] = {
        quantity: defaultdict(lambda: defaultdict(float)) for quantity in QUANTITIES
    }
    seen: set[tuple[int, str]] = set()
    for line_number, row in enumerate(rows, 2):
        where = f"{path}:{line_number}"
        year = _whole_number(row.get("calendar_year"), where=f"{where} calendar_year")
        loop_year = _whole_number(row.get("year"), where=f"{where} year")
        if year not in YEARS or loop_year != year - HINDCAST_FIRST_YEAR + 1:
            raise ScoreError(f"{where}: calendar/loop year identity is invalid ({year}, {loop_year})")
        agent = (row.get("agent_id") or "").strip()
        if not agent:
            raise ScoreError(f"{where}: blank agent_id")
        key = (year, agent)
        if key in seen:
            raise ScoreError(f"{where}: duplicate agent/year {agent!r}/{year}")
        seen.add(key)
        basin = (row.get("basin") or "").strip()
        subbasin = (row.get("ub_subbasin") or "").strip()
        if basin == "upper_basin":
            if subbasin not in UB_SUBBASINS:
                raise ScoreError(f"{where}: invalid Upper Basin subbasin {subbasin!r}")
        elif basin == "lower_basin":
            if subbasin:
                raise ScoreError(f"{where}: Lower Basin row has subbasin {subbasin!r}")
            if agent not in expected_lb:
                raise ScoreError(f"{where}: unknown Lower Basin agent {agent!r}")
        else:
            raise ScoreError(f"{where}: invalid basin {basin!r}")
        prior = identity.setdefault(agent, (basin, subbasin))
        if prior != (basin, subbasin):
            raise ScoreError(f"{where}: agent {agent!r} changed basin/subbasin identity")
        by_year[year].add(agent)
        for quantity in QUANTITIES:
            af = _finite(row.get(quantity), where=f"{where} {quantity}")
            if af < 0:
                raise ScoreError(f"{where}: {quantity} is negative")
            if basin == "upper_basin":
                totals[quantity][f"{UB_PREFIX}{subbasin}"][year] += af / 1_000_000.0
                totals[quantity][f"{UB_PREFIX}total"][year] += af / 1_000_000.0
            else:
                totals[quantity][f"{LB_PREFIX}{agent}"][year] = af / 1_000_000.0
                totals[quantity][f"{LB_PREFIX}total"][year] += af / 1_000_000.0

    all_agents = set(identity)
    if identity != expected_identity:
        missing = sorted(set(expected_identity) - all_agents)
        extra = sorted(all_agents - set(expected_identity))
        changed = sorted(agent for agent in all_agents & set(expected_identity)
                         if identity[agent] != expected_identity[agent])
        raise ScoreError(
            f"{path}: agent identities differ from pinned profiles; "
            f"missing={missing}, extra={extra}, changed={changed}"
        )
    for year in YEARS:
        missing_agents = sorted(all_agents - by_year[year])
        extra_agents = sorted(by_year[year] - all_agents)
        if missing_agents or extra_agents:
            raise ScoreError(f"{path}: year {year} agent identities differ; missing={missing_agents}, extra={extra_agents}")
    found_lb = {agent for agent, (basin, _) in identity.items() if basin == "lower_basin"}
    if found_lb != expected_lb:
        raise ScoreError(f"{path}: Lower Basin identities differ; missing={sorted(expected_lb-found_lb)}, extra={sorted(found_lb-expected_lb)}")
    if sum(1 for basin, _ in identity.values() if basin == "upper_basin") != 56:
        raise ScoreError(f"{path}: expected 56 Upper Basin agents")
    expected_series = set(recorded)
    for quantity in QUANTITIES:
        if set(totals[quantity]) != expected_series:
            raise ScoreError(f"{path}: {quantity} series differ from recorded identities")
    return {q: {s: dict(v) for s, v in totals[q].items()} for q in QUANTITIES}, seed, arm


def _recorded_replay_series() -> dict[str, dict[int, float]]:
    """Build replay series independently from per-agent observed requests."""
    profiles = load_profiles()
    identities = {profile.agent_id: (profile.basin, profile.precip_group or "") for profile in profiles}
    if len(identities) != 78:
        raise ScoreError("profile data does not contain 78 unique agent identities")
    per_agent = observed_requests(profiles, YEARS)
    totals: dict[str, dict[int, float]] = defaultdict(lambda: defaultdict(float))
    for year in YEARS:
        if set(per_agent.get(year, {})) != set(identities):
            raise ScoreError(f"recorded replay year {year}: agent identities differ from pinned profiles")
        for agent, af in per_agent[year].items():
            basin, subbasin = identities[agent]
            maf = float(af) / 1_000_000.0
            if basin == "upper_basin":
                totals[f"{UB_PREFIX}{subbasin}"][year] += maf
                totals[f"{UB_PREFIX}total"][year] += maf
            elif basin == "lower_basin":
                totals[f"{LB_PREFIX}{agent}"][year] = maf
                totals[f"{LB_PREFIX}total"][year] += maf
            else:
                raise ScoreError(f"recorded replay: invalid basin {basin!r} for {agent!r}")
    return {series: dict(values) for series, values in totals.items()}


def _recorded_replay_sanity(observed: Mapping[str, Mapping[int, float]]) -> Kge:
    replay = _recorded_replay_series()
    if set(replay) != set(observed):
        raise ScoreError("recorded replay sanity series differ from recorded series")
    expected = (1.0, 1.0, 1.0, 1.0)
    for quantity in QUANTITIES:
        for series in sorted(observed):
            value = _score(replay[series], observed[series])
            actual = (value.kge, value.r, value.alpha, value.beta)
            if any(component is None or not math.isclose(component, target, rel_tol=1e-10, abs_tol=1e-10)
                   for component, target in zip(actual, expected)):
                raise ScoreError(
                    f"recorded replay sanity failed for {quantity}/{series}: {value}"
                )
    return Kge(1.0, 1.0, 1.0, 1.0, len(YEARS))


def _score(simulated: Mapping[int, float], observed: Mapping[int, float]) -> Kge:
    return kge([simulated[year] for year in YEARS], [observed[year] for year in YEARS])


def _row(
    run: str, kind: str, arm: str, model: str, seed: int | str,
    series: str, quantity: str, value: Kge,
) -> dict[str, Any]:
    basin = ("upper_basin" if series.startswith(UB_PREFIX) else "lower_basin"
             if series.startswith(LB_PREFIX) or series == "lb_agent_summary" else "sanity")
    return {
        "run": run,
        "kind": kind,
        "arm": arm,
        "model": model,
        "seed": seed,
        "series": series,
        "basin": basin,
        "quantity": quantity,
        "kge": value.kge,
        "r": value.r,
        "alpha": value.alpha,
        "beta": value.beta,
        "n": value.n,
        "convention_scored": int(value.note == CONSTANT_SIM_NOTE),
        "undefined": int(value.kge is None),
        "note": value.note,
        "warning": "",
    }


def _lb_summary(
    rows: Sequence[dict[str, Any]], *, run: str, kind: str, arm: str, model: str,
    seed: int | str, quantity: str,
) -> dict[str, Any]:
    agents = [row for row in rows if row["run"] == run and row["quantity"] == quantity
              and row["series"].startswith(LB_PREFIX) and row["series"] != f"{LB_PREFIX}total"]
    values = [float(row["kge"]) for row in agents if row["kge"] is not None]
    if not values:
        raise ScoreError(f"{run}: no defined Lower Basin agent KGE values for {quantity}")
    convention_count = sum(int(row["convention_scored"]) for row in agents)
    undefined_count = sum(int(row["undefined"]) for row in agents)
    summary = _row(run, kind, arm, model, seed, "lb_agent_summary", quantity,
                   Kge(None, None, None, None, len(values)))
    summary["kge"] = float(statistics.median(values))
    summary["convention_scored"] = convention_count
    summary["undefined"] = undefined_count
    summary["note"] = (
        f"median KGE over Lower Basin agents; {convention_count} of 22 agents "
        f"convention-scored, {undefined_count} undefined"
    )
    return summary


def _write_csv(rows: Sequence[dict[str, Any]], path: Path) -> None:
    fields = ("run", "kind", "arm", "model", "seed", "series", "basin", "quantity",
              "kge", "r", "alpha", "beta", "n", "convention_scored", "undefined",
              "note", "warning")
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _fmt(value: float | None) -> str:
    return "NA" if value is None else f"{value:.3f}"


def _summary_rows(
    rows: Sequence[dict[str, Any]], kind: str,
) -> list[tuple[str, str, str, str, list[float], int, int, int, str]]:
    grouped: dict[tuple[str, str, str, str], list[float]] = defaultdict(list)
    counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    convention_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    undefined_counts: dict[tuple[str, str, str, str], int] = defaultdict(int)
    warnings: dict[tuple[str, str, str, str], set[str]] = defaultdict(set)
    for row in rows:
        if row["kind"] != kind:
            continue
        key = (str(row["arm"]), str(row["model"]), str(row["series"]), str(row["quantity"]))
        counts[key] += 1
        convention_counts[key] += int(row["convention_scored"])
        undefined_counts[key] += int(row["undefined"])
        warnings[key].add(str(row["warning"]))
        if row["kge"] is not None:
            grouped[key].append(float(row["kge"]))
    return [(*key, grouped[key], counts[key], convention_counts[key], undefined_counts[key],
             _combine_warnings(*warnings[key]))
            for key in sorted(counts)]


def _combine_warnings(*warnings: str) -> str:
    return "; ".join(sorted({part for warning in warnings for part in warning.split("; ") if part}))


def _count_label(convention_count: int, undefined_count: int) -> str:
    return f"{convention_count} convention, {undefined_count} undefined"


def _write_report(rows: Sequence[dict[str, Any]], path: Path) -> None:
    sanity = next(row for row in rows if row["kind"] == "sanity")
    dirty_runs = sorted({str(row["run"]) for row in rows if DIRTY_WARNING in row["warning"]})
    provenance = "; ".join(f"{run}: {DIRTY_WARNING}" for run in dirty_runs)
    warning = str(sanity["warning"])
    lines = [
        "# Irrigation v3 agent hindcast scores",
        "",
        f"Recorded replay sanity: KGE={sanity['kge']:.3f}, r={sanity['r']:.3f}, "
        f"alpha={sanity['alpha']:.3f}, beta={sanity['beta']:.3f} (printed once).",
        "",
        warning,
        "" if warning else "",
        "Request is the primary decision comparison. Diversion is secondary.",
        "",
        f"All tables use {len(YEARS)} annual points per series. B=X contains the window for 48/56 UB and 8/22 LB agents; c_s uses the full record, so sub-basin KGE is not independent of the envelope. Calibrated FQL is in-sample.",
        "",
        "## Labelled benchmarks",
        "",
        provenance,
        "",
        "| Benchmark | Model | Series | KGE | Counts | Warning |",
        "|---|---|---|---:|---|---|",
    ]
    for arm, model, series, _, values, _, convention, undefined, row_warning in _summary_rows(rows, "benchmark"):
        row_warning = _combine_warnings(row_warning, warning)
        lines.append(f"| {arm} | {model} | {series} | {_fmt(values[0] if values else None)} | "
                     f"{_count_label(convention, undefined)} | {row_warning} |")
    lines.extend([
        "",
        "## FQL benchmark",
        "",
        provenance,
        "",
        "| Model | Series | Quantity | Mean KGE | Minimum | Maximum | n seeds | Counts | Warning |",
        "|---|---|---:|---:|---:|---:|---:|---|---|",
    ])
    for _, model, series, quantity, values, count, convention, undefined, row_warning in _summary_rows(rows, "fql"):
        row_warning = _combine_warnings(row_warning, warning)
        mean = statistics.mean(values) if values else None
        lines.append(f"| {model} | {series} | {quantity} | {_fmt(mean)} | "
                     f"{_fmt(min(values) if values else None)} | "
                     f"{_fmt(max(values) if values else None)} | {count} | "
                     f"{_count_label(convention, undefined)} | {row_warning} |")
    if not _summary_rows(rows, "fql"):
        lines.append(f"| not applicable | No FQL runs supplied | | | | | 0 | 0 convention, 0 undefined | {warning} |")
    lines.extend([
        "",
        "## LLM arms",
        "",
        provenance,
        "",
        "| Arm | Model | Series | Quantity | Median KGE | Uncertainty | n distinct seeds | Counts | Warning |",
        "|---|---|---|---:|---:|---:|---:|---|---|",
    ])
    for arm, model, series, quantity, values, count, convention, undefined, row_warning in _summary_rows(rows, "llm"):
        row_warning = _combine_warnings(row_warning, warning)
        uncertainty = ("none (n=1)" if count == 1 else
                       f"{min(values):.3f} to {max(values):.3f}" if values else "undefined")
        median = statistics.median(values) if values else None
        lines.append(f"| {arm} | {model} | {series} | {quantity} | {_fmt(median)} | "
                     f"{uncertainty} | {count} | {_count_label(convention, undefined)} | "
                     f"{row_warning} |")
    if not _summary_rows(rows, "llm"):
        lines.append(f"| No LLM runs supplied | not applicable | | | | | 0 | "
                     f"0 convention, 0 undefined | {warning} |")
    lines.extend([
        "",
        "## Interpretation limits",
        "",
        f"Each KGE uses {len(YEARS)} annual points. The years are autocorrelated, so no p-values or bootstrap intervals are reported.",
        "",
        "B = X uses the full 1971-2018 record, and the sub-basin envelope coefficient c_s also uses the full record. Upper Basin sub-basin KGE is therefore not independent of the envelope. FQL tables were trained through 2018 and are an in-sample benchmark. Persistence means the prior year's recorded value; constant means the recorded 1999 anchor. LLM ranges describe distinct supplied seeds, while the sampler itself is not seeded.",
        "",
    ])
    path.write_text("\n".join(lines), encoding="utf-8")


def score_runs(
    llm_dirs: Sequence[str | Path],
    fql_dirs: Sequence[str | Path],
    out_dir: str | Path,
    *,
    allow_mock: bool = False,
    allow_dirty: bool = False,
) -> list[dict[str, Any]]:
    """Validate runs, score all series, write CSV and Markdown, and return rows."""
    if not llm_dirs and not fql_dirs:
        raise ScoreError("supply at least one --llm or --fql run directory")
    observed = recorded_series()
    rows: list[dict[str, Any]] = []
    seen_paths: set[Path] = set()
    seen_seed_arm: set[tuple[str, str, int]] = set()
    llm_signature: str | None = None
    fql_signature: str | None = None
    physical_signature: str | None = None
    first_commit: tuple[Path, str] | None = None
    has_mock = False
    for kind, directories in (("llm", llm_dirs), ("fql", fql_dirs)):
        for raw_dir in directories:
            run_dir = Path(raw_dir).resolve()
            if run_dir in seen_paths:
                raise ScoreError(f"run directory supplied more than once: {run_dir}")
            seen_paths.add(run_dir)
            manifest_path = run_dir / MANIFEST
            manifest, _, manifest_arm = _manifest(run_dir, kind)
            commit = _code_commit(manifest, where=manifest_path)
            if first_commit is None:
                first_commit = (run_dir, commit)
            elif commit != first_commit[1]:
                raise ScoreError(
                    f"mixed code commits: {first_commit[0]}={first_commit[1]}, {run_dir}={commit}"
                )
            dirty = _dirty_tree(manifest, where=manifest_path)
            if dirty and not allow_dirty:
                raise ScoreError(f"{run_dir}: {DIRTY_WARNING}; requires --allow-dirty")
            manifest_model = ("fql:calibrated" if kind == "fql"
                              else str(manifest["model"]).strip())
            run_physical_signature = _physical_signature(manifest, kind, where=manifest_path)
            if physical_signature is None:
                physical_signature = run_physical_signature
            elif physical_signature != run_physical_signature:
                raise ScoreError(f"{run_dir}: mixed physical inputs across supplied runs")
            if kind == "llm":
                run_llm_signature = _llm_signature(manifest, where=manifest_path)
                if llm_signature is None:
                    llm_signature = run_llm_signature
                elif llm_signature != run_llm_signature:
                    raise ScoreError(
                        f"{run_dir}: mixed model/configuration/calibration inputs across LLM governance arms"
                    )
                if manifest_model == "mock":
                    if not allow_mock:
                        raise ScoreError(f"{run_dir}: model 'mock' requires --allow-mock")
                    has_mock = True
            else:
                run_fql_signature = _fql_signature(manifest, where=manifest_path)
                if fql_signature is None:
                    fql_signature = run_fql_signature
                elif fql_signature != run_fql_signature:
                    raise ScoreError(f"{run_dir}: mixed model/configuration/calibration inputs in FQL runs")
            simulated, seed, arm = _load_run_series(run_dir, kind)
            model = manifest_model
            if arm != manifest_arm:
                raise ScoreError(f"{run_dir}: manifest identity changed while loading the simulation")
            seed_key = (kind, arm, seed)
            if seed_key in seen_seed_arm:
                raise ScoreError(f"duplicate {kind} arm/seed {arm}/{seed}")
            seen_seed_arm.add(seed_key)
            label = str(run_dir)
            start = len(rows)
            for quantity in QUANTITIES:
                for series in sorted(observed):
                    rows.append(_row(label, kind, arm, model, seed, series, quantity,
                                     _score(simulated[quantity][series], observed[series])))
                rows.append(_lb_summary(rows[start:], run=label, kind=kind, arm=arm, model=model,
                                        seed=seed, quantity=quantity))
            if dirty:
                for row in rows[start:]:
                    row["warning"] = DIRTY_WARNING

    benchmarks = benchmark_series(observed)
    for label, series_map in benchmarks.items():
        start = len(rows)
        for series in sorted(observed):
            rows.append(_row(label, "benchmark", label, "not applicable", "", series, "benchmark",
                             _score(series_map[series], observed[series])))
        rows.append(_lb_summary(rows[start:], run=label, kind="benchmark", arm=label,
                                model="not applicable",
                                seed="", quantity="benchmark"))
    sanity = _recorded_replay_sanity(observed)
    rows.append(_row("recorded_replay", "sanity", "sanity", "not applicable", "",
                     "recorded_replay", "sanity", sanity))
    if has_mock:
        for row in rows:
            row["warning"] = _combine_warnings(str(row["warning"]), MOCK_WARNING)

    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    _write_csv(rows, output / SCORES_CSV)
    _write_report(rows, output / REPORT_MD)
    return rows


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--llm", nargs="*", default=[], metavar="DIR", help="LLM hindcast run directories")
    parser.add_argument("--fql", nargs="*", default=[], metavar="DIR", help="FQL hindcast run directories")
    parser.add_argument("--out", required=True, type=Path, help="output directory")
    parser.add_argument("--allow-mock", action="store_true", help="score mock runs with a prominent warning")
    parser.add_argument("--allow-dirty", action="store_true", help="score runs from modified trees with a warning")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        rows = score_runs(args.llm, args.fql, args.out, allow_mock=args.allow_mock, allow_dirty=args.allow_dirty)
    except ScoreError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    print(f"Wrote {len(rows)} score rows to {args.out / SCORES_CSV}")
    print(f"Recorded replay sanity: KGE=1, r=1, alpha=1, beta=1 (n={len(YEARS)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
