"""Fixed paper measures, without changing the existing v3 metrics.

IBR judges the executed action against all six rules, using FIRST-stated WSA
even if later relabelled. The 0.5 AF tolerance applies only to request bounds.
EHE is Shannon entropy of increase/keep/decrease divided by log2(3).
Hindcasts score 1 January 2001..2019 (2000..2018 end storages), excluding the
observed starting anchor. Bias is simulated minus observed. Shortage counts
refer to tiers declared DURING the corresponding simulation years 2000..2018.

FQL's executed skill is simulation_log.csv/yearly_decision, never fql_raw_skill
or the sign of its sampled delta. Behavioural measures are not applicable.
Current FQL logs lack the pre-decision supply physical ratio; final settlement
ratios cannot replace it. Missing inputs produce labelled None values, with
the identifiable per-rule counts retained.

    python -m examples.irrigation_abm.analysis.paper_measures projection \\
        --runs DIR [DIR ...] --out CSV
    python -m examples.irrigation_abm.analysis.paper_measures hindcast \\
        --runs DIR [DIR ...] --out CSV

The hindcast table includes the recorded-diversion replay, keep-1999 and
request-B paths, computed by hindcast_v3.run_hindcast, and a constant-level
benchmark at the observed 1 January 2000 level. Input folders are read-only.
"""
from __future__ import annotations

import argparse
import csv
import math
import statistics
import subprocess
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from examples.irrigation_abm.analysis import v3_metrics as vm

TOLERANCE_AF = 0.5
FIRST_YEAR, LAST_YEAR = 2000, 2018
BEHAVIOURAL_RULES = ("TR1", "TR3")
PHYSICAL_RULES = ("supply", "limit", "right", "floor")
BOUND_RULES = ("limit", "right", "floor")
REFERENCE_PHYSICS = ("lb_non_ag_total_maf", "powell_release_mode", "lb_return_flow_fraction")
ACTIONS = (vm.INCREASE, vm.KEEP, vm.DECREASE)


def _finite(value: Any, where: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise vm.MetricsError(f"{where}: missing or invalid number {value!r}") from exc
    if not math.isfinite(number):
        raise vm.MetricsError(f"{where}: non-finite number")
    return number


def _integer(value: Any, where: str) -> int:
    number = _finite(value, where)
    if number != int(number):
        raise vm.MetricsError(f"{where}: expected an integer")
    return int(number)


def rule_flags(decision: vm.Decision, request_af: float, water_right_af: float,
               peak_obs_af: float | None, *, behavioural: bool = True,
               min_utilisation_fraction: float | None = None) -> dict[str, bool | None]:
    """Post hoc executed-action predicates; None denotes an unavailable input."""
    action = decision.executed_skill
    if action not in ACTIONS:
        raise vm.MetricsError(f"{decision.agent_id}, {decision.year}: invalid executed action {action!r}")
    request = _finite(request_af, "request")
    right = _finite(water_right_af, "water right")
    if right <= 0 or request < 0:
        raise vm.MetricsError("request must be nonnegative and water right positive")
    peak = None if peak_obs_af is None else _finite(peak_obs_af, "peak_obs_af")
    if peak is not None and peak <= 0:
        raise vm.MetricsError("peak_obs_af must be positive")
    inc, dec = action == vm.INCREASE, action == vm.DECREASE
    if min_utilisation_fraction is None:
        min_utilisation_fraction = vm.WaterSystemConfig().min_utilisation_fraction
    return {
        "TR1": (inc and decision.first_wsa in vm.TR1_WSA) if behavioural else None,
        "TR3": (dec and decision.first_wsa in vm.TR3_WSA) if behavioural else None,
        "supply": decision.supply_condition if inc else False,
        "limit": (request > min(right, peak) + TOLERANCE_AF if peak is not None else None) if inc else False,
        "right": inc and request > right + TOLERANCE_AF,
        "floor": dec and request < min_utilisation_fraction * right - TOLERANCE_AF,
    }


def _count_complete(values: Iterable[bool | None]) -> int | None:
    items = list(values)
    return None if any(value is None for value in items) else sum(bool(value) for value in items)


def _pct(count: int | None, n: int) -> float | None:
    return 100 * count / n if count is not None and n else None


def ibr_summary(decisions: Iterable[vm.Decision], rows: Mapping[tuple[str, int], Mapping[str, Any]],
                peaks: Mapping[str, float | None], *, behavioural: bool = True,
                min_utilisation_fraction: float | None = None) -> dict[str, Any]:
    """One decision breaking multiple rules contributes once to each union.

    Aborted decisions with no executed skill are excluded from the denominator.
    First-proposal behavioural counts use that same executed-decision cohort.
    A union is reported only when every constituent predicate is available.
    """
    decisions = list(decisions)
    executed = [d for d in decisions if d.executed_skill is not None and not d.aborted]
    flags = []
    first = []
    for d in executed:
        key = (d.agent_id, d.year)
        if key not in rows:
            raise vm.MetricsError(f"simulation row missing for {key}")
        row = rows[key]
        flags.append(rule_flags(d, row.get("request"), row.get("water_right"),
                                peaks.get(d.agent_id), behavioural=behavioural,
                                min_utilisation_fraction=min_utilisation_fraction))
        first.append((d.first_proposal == vm.INCREASE and d.first_wsa in vm.TR1_WSA)
                     or (d.first_proposal == vm.DECREASE and d.first_wsa in vm.TR3_WSA))
    n = len(executed)
    counts = {rule: _count_complete(f[rule] for f in flags)
              for rule in BEHAVIOURAL_RULES + PHYSICAL_RULES}
    if not behavioural:
        counts.update({rule: None for rule in BEHAVIOURAL_RULES})
    physical_complete = all(counts[rule] is not None for rule in PHYSICAL_RULES)
    physical = sum(any(f[rule] for rule in PHYSICAL_RULES) for f in flags) if physical_complete else None
    beh = sum(any(f[rule] for rule in BEHAVIOURAL_RULES) for f in flags) if behavioural else None
    combined = None
    if behavioural and physical_complete:
        combined = sum(any(f.values()) for f in flags)
    bounds = None
    if all(counts[rule] is not None for rule in BOUND_RULES):
        bounds = sum(any(f[rule] for rule in BOUND_RULES) for f in flags)
    missing = [rule for rule in PHYSICAL_RULES if counts[rule] is None]
    return {
        "n": n, "n_aborted": sum(d.aborted for d in decisions),
        "ibr_count": combined, "ibr_pct": _pct(combined, n),
        "ibr_scope": "all six rules" if behavioural else "not applicable",
        "behavioural_count": beh, "behavioural_ibr_pct": _pct(beh, n),
        "behavioural_note": "first-stated scarcity" if behavioural else "not applicable",
        "physical_count": physical, "physical_ibr_pct": _pct(physical, n),
        "physical_note": "complete" if physical_complete else "unavailable inputs: " + ", ".join(missing),
        "physical_excluding_supply_count": bounds,
        "physical_excluding_supply_pct": _pct(bounds, n),
        "physical_excluding_supply_note": "limit/right/floor union; excluding supply",
        **{f"{rule}_count": count for rule, count in counts.items()},
        "first_behavioural_count": sum(first) if behavioural else None,
        "first_behavioural_pct": _pct(sum(first), n) if behavioural else None,
    }


def action_entropy(actions: Iterable[str]) -> dict[str, Any]:
    """Normalized Shannon entropy and shares (fractions, not percentages)."""
    counts = dict.fromkeys(ACTIONS, 0)
    for action in actions:
        if action not in counts:
            raise vm.MetricsError(f"unknown executed action {action!r}")
        counts[action] += 1
    n = sum(counts.values())
    shares = [counts[action] / n if n else None for action in ACTIONS]
    entropy = -sum(p * math.log2(p) for p in shares if p) / math.log2(3) if n else None
    return {"ehe": entropy, "increase_share": shares[0], "keep_share": shares[1],
            "decrease_share": shares[2]}


def _metadata(info: vm.RunInfo, *, commit: str | None = None) -> dict[str, Any]:
    commit_key = "git_head" if info.kind == "fql" else "git_commit"
    commit = commit if commit is not None else info.manifest.get(commit_key)
    if not isinstance(commit, str) or not commit.strip():
        raise vm.MetricsError(f"{info.path}: missing commit provenance ({commit_key})")
    return {"run": info.path.name, "commit": commit, "kind": info.kind,
            "arm": info.arm, "seed": info.seed}


def _profiles(run: vm.LoadedRun) -> Sequence[Any]:
    manifest = run.info.manifest
    for key in ("paper_water_margin", "cluster_method"):
        if key not in manifest:
            raise vm.MetricsError(f"{run.info.path}: missing profile provenance {key}")
    return vm.make_profiles(True, len(run.sim.agents), run.info.seed,
                            _finite(manifest["paper_water_margin"], "paper_water_margin"),
                            manifest["cluster_method"])


def _floor_fraction(manifest: Mapping[str, Any]) -> float:
    """Use the recorded floor, refusing a different analysis configuration."""
    configured = vm.WaterSystemConfig().min_utilisation_fraction
    sources = [("manifest", manifest)]
    if isinstance(manifest.get("water_system_config"), Mapping):
        sources.append(("water_system_config", manifest["water_system_config"]))
    fraction = configured
    for where, source in sources:
        if "min_utilisation_fraction" in source:
            fraction = _finite(source["min_utilisation_fraction"], where + " min_utilisation_fraction")
            if fraction != configured:
                raise vm.MetricsError(f"{where}: min_utilisation_fraction={fraction} differs from config {configured}")
    return fraction


def _fql_decision(key: tuple[str, int], row: Mapping[str, Any]) -> vm.Decision:
    # Only a specifically logged PRE-decision physical ratio can score supply.
    # The final lb_phys_ratio/ub_subbasin_ratio describe a different settlement.
    ratio = row.get("supply_physical_ratio")
    physical = _finite(ratio, "supply_physical_ratio") if ratio not in (None, "") else None
    return vm.Decision(
        agent_id=key[0], year=key[1], status="FQL", execution_path="fql",
        executed_skill=row.get("yearly_decision"), proposed_skill="", attempts=(),
        retry_count=0, format_retries=0, llm_success=None,
        keep_request_af=None, expected_at_keep_af=None, supply_ratio=None,
        physical_ratio=physical, first_wsa=None, first_aca=None, final_wsa=None,
        wsa_relabeled=False, error_messages="", timestamp="",
    )


def projection_run(path: Path, *, profiles: Sequence[Any] | None = None) -> dict[str, Any]:
    run = vm.load_run(Path(path), keep_prompts=False)
    if run.info.manifest.get("hindcast"):
        raise vm.MetricsError(f"{path}: use the hindcast command for a hindcast run")
    if run.info.kind not in ("llm", "fql"):
        raise vm.MetricsError(f"{path}: expected an LLM or FQL run")
    profiles = profiles if profiles is not None else _profiles(run)
    peaks = {p.agent_id: p.peak_obs_af for p in profiles}
    if run.info.kind == "fql":
        decisions = [_fql_decision(key, row) for key, row in run.sim.rows.items()]
        # Missing final actions must not silently shrink FQL's denominator.
        if any(d.executed_skill not in ACTIONS for d in decisions):
            raise vm.MetricsError(f"{path}: missing or invalid FQL yearly_decision action")
    else:
        decisions = list(run.decisions.values())
    floor = _floor_fraction(run.info.manifest)
    actions = [d.executed_skill for d in decisions if d.executed_skill is not None and not d.aborted]
    return {**_metadata(run.info),
            **ibr_summary(decisions, run.sim.rows, peaks, behavioural=run.info.kind == "llm",
                          min_utilisation_fraction=floor),
            **action_entropy(actions)}


def hindcast_scores(jan1_years: Sequence[int], simulated: Sequence[float], observed: Sequence[float],
                    tiers: Sequence[int]) -> dict[str, Any]:
    """Score paired January levels; tie for largest departure uses earliest date."""
    n = len(jan1_years)
    if not n or any(len(values) != n for values in (simulated, observed, tiers)):
        raise vm.MetricsError("hindcast series must have equal, nonzero lengths")
    years = [_integer(y, "January year") for y in jan1_years]
    if years != sorted(set(years)):
        raise vm.MetricsError("January years must be strictly increasing")
    sim = [_finite(x, "simulated Mead") for x in simulated]
    obs = [_finite(x, "observed Mead") for x in observed]
    shortage = [_integer(tier, "shortage tier") for tier in tiers]
    if any(tier not in (0, 1, 2, 3) for tier in shortage):
        raise vm.MetricsError("shortage tier must be 0..3")
    score = vm.kge(sim, obs)
    differences = [s - o for s, o in zip(sim, obs)]
    absolute = [abs(d) for d in differences]
    largest = max(range(n), key=absolute.__getitem__)
    return {"n_years": n, "scored_dates": ";".join(f"{y}-01-01" for y in years),
            "kge": score.kge, "r": score.r, "alpha": score.alpha, "beta": score.beta,
            "kge_note": score.note, "mae_ft": statistics.mean(absolute),
            "bias_ft": statistics.mean(differences), "max_abs_departure_ft": absolute[largest],
            "max_abs_departure_date": f"{years[largest]}-01-01",
            "n_above_19_9_ft": sum(d > 19.9 for d in absolute),
            "n_shortage_years": sum(tier > 0 for tier in shortage)}


def hindcast_run(path: Path) -> dict[str, Any]:
    """Read historical logs directly: load_run's SimLog validates projection years.

    All rows of each calendar year must agree on the system-level values and
    cover the same agents. End storage is converted with the repository's
    Mead curve, giving the following January including the terminal 2019 value.
    """
    from examples.irrigation_abm.analysis import hindcast_v3 as hv
    from examples.irrigation_abm.analysis import hindcast_v3_agents_score as hs

    info = vm.read_run_info(Path(path))
    if info.kind not in ("llm", "fql"):
        raise vm.MetricsError(f"{path}: expected an LLM or FQL hindcast run")
    try:
        manifest, _, _ = hs._manifest(info.path, info.kind)
        commit = hs._code_commit(manifest, where=info.path / vm.MANIFEST)
        dirty = hs._dirty_tree(manifest, where=info.path / vm.MANIFEST)
    except hs.ScoreError as exc:
        raise vm.MetricsError(str(exc)) from exc
    _floor_fraction(manifest)
    system: dict[int, tuple[float, int]] = {}
    grid: set[tuple[str, int]] = set()
    log = info.path / vm.SIM_LOG
    with log.open(encoding="utf-8-sig", newline="") as stream:
        for line, row in enumerate(csv.DictReader(stream), 2):
            where = f"{log}:{line}"
            year = _integer(row.get("calendar_year"), where + " calendar_year")
            loop = _integer(row.get("year"), where + " year")
            agent = row.get("agent_id")
            if not agent or year not in range(FIRST_YEAR, LAST_YEAR + 1) or loop != year - FIRST_YEAR + 1:
                raise vm.MetricsError(f"{where}: invalid agent or hindcast year")
            key = (agent, year)
            if key in grid:
                raise vm.MetricsError(f"{where}: duplicate agent-year")
            grid.add(key)
            value = (_finite(row.get("mead_storage_end_maf"), where + " end storage"),
                     _integer(row.get("shortage_tier"), where + " shortage_tier"))
            if year in system and system[year] != value:
                raise vm.MetricsError(f"{where}: system values differ between agents")
            system[year] = value
    expected = {(agent, year) for agent, _ in grid for year in range(FIRST_YEAR, LAST_YEAR + 1)}
    if not grid or grid != expected:
        raise vm.MetricsError(f"{log}: incomplete 2000..2018 agent-year grid")
    years = list(range(FIRST_YEAR, LAST_YEAR + 1))
    record = hv.load_observed()
    return {**_metadata(info, commit=commit), "git_dirty": dirty,
        **{key: manifest["hindcast"][key] for key in REFERENCE_PHYSICS}, **hindcast_scores(
        [y + 1 for y in years], [vm.mead_elevation_ft(system[y][0]) for y in years],
        [record[y]["mead_elev_ft_eoy"] for y in years], [system[y][1] for y in years])}


def hindcast_references(*, run_rows: Sequence[Mapping[str, Any]] = ()) -> list[dict[str, Any]]:
    """Default-physics paths and constant level; reject incomparable run rows."""
    from examples.irrigation_abm.analysis import hindcast_v3 as hv

    config = vm.WaterSystemConfig()
    physics = {key: getattr(config, key) for key in REFERENCE_PHYSICS}
    for row in run_rows:
        for key, expected in physics.items():
            if row.get(key) != expected:
                raise vm.MetricsError(f"{row.get('run')}: reference {key}={expected!r} differs from run {row.get(key)!r}")
    record = hv.load_observed()
    profiles = hv.load_profiles()
    years = range(FIRST_YEAR - 1, LAST_YEAR + 1)
    recorded = hv.observed_requests(profiles, years)
    limits = {}
    for p in profiles:
        peak = _finite(p.peak_obs_af, f"{p.agent_id} peak_obs_af")
        if peak <= 0:
            raise vm.MetricsError(f"{p.agent_id}: nonpositive observed peak")
        limits[p.agent_id] = min(p.water_right, peak)
    paths = {"recorded_diversion_replay": recorded,
             "keep_1999": {y: dict(recorded[1999]) for y in years},
             "request_B": {y: dict(limits) for y in years}}
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parents[3],
                            check=True, capture_output=True, text=True).stdout.strip()
    dirty = bool(subprocess.run(["git", "status", "--porcelain"], cwd=Path(__file__).resolve().parents[3],
                                check=True, capture_output=True, text=True).stdout.strip())
    output = []
    for name, requests in paths.items():
        result = hv.run_hindcast(FIRST_YEAR, LAST_YEAR, profiles=profiles, observed=record, requests=requests)
        series = result.series
        output.append({"run": name, "commit": commit, "git_dirty": dirty, **physics,
                       "kind": "reference", "arm": name, "seed": None,
                       **hindcast_scores([s["jan1"] for s in series], [s["mead_elev_sim"] for s in series],
                                          [s["mead_elev_obs"] for s in series], [s["tier_during_year"] for s in series])})
    name = "constant_level_jan1_2000"
    anchor = record[FIRST_YEAR - 1]["mead_elev_ft_eoy"]
    # The observed 1213.94 ft anchor is above the first shortage threshold.
    if anchor < config.mead_shortage_tier1:
        raise vm.MetricsError("constant-level anchor unexpectedly falls below the no-shortage threshold")
    output.append({"run": name, "commit": commit, "git_dirty": dirty, **physics,
                   "kind": "reference", "arm": name, "seed": None,
                   **hindcast_scores([y + 1 for y in range(FIRST_YEAR, LAST_YEAR + 1)],
                       [anchor] * (LAST_YEAR - FIRST_YEAR + 1),
                       [record[y]["mead_elev_ft_eoy"] for y in range(FIRST_YEAR, LAST_YEAR + 1)],
                       [0] * (LAST_YEAR - FIRST_YEAR + 1))})
    return output


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("projection", "hindcast"):
        sub = subparsers.add_parser(command)
        sub.add_argument("--runs", type=Path, nargs="+", required=True)
        sub.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    destination = args.out.resolve()
    if any(destination.is_relative_to(path.resolve()) for path in args.runs):
        raise vm.MetricsError("--out must be outside every input run folder")
    measure = projection_run if args.command == "projection" else hindcast_run
    rows = [measure(path) for path in args.runs]
    if args.command == "hindcast":
        rows.extend(hindcast_references(run_rows=rows))
    columns = list(dict.fromkeys(key for row in rows for key in row))
    with destination.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows to {destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
