"""Flood Fig 2: consistency with appraisal and variety of household actions.

Panel (a) answers the variety half of SQ1 with household protection STATES.
Its pooled EHE annotations are the pre-registered variety number, computed
on yearly DECISIONS, not protection states. Rule-based EHE (0.61) belongs in
the caption, not on the canvas. Panel (b) addresses variety where the validator
acts: blocked first proposals are redistributed across protective actions,
compared with unforced choices in the same appraisal region, rather than
funnelled into one action. Panel (c) answers the consistency half of SQ1.
The supplementary appraisal grid describes where contradictions sit (about
97% in TA=H, CA=M without the validator); it is not itself an answer to SQ1.
All measures follow paper_measures; the earlier Nature Water figure supplies
visual style and state mapping only. One CLI run writes both figures.

    python -m examples.single_agent.analysis.fig2_flood_sq1 \\
        --results-root DIR --out-dir DIR
"""
from __future__ import annotations

import argparse
import math
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import gridspec
from matplotlib.colors import LinearSegmentedColormap, Normalize
from matplotlib.patches import Patch, Rectangle, Wedge

from examples.single_agent.analysis import flood_ibr_v2 as audit
from examples.single_agent.analysis import paper_measures as measures
from examples.single_agent.analysis.paper_measures import MetricsError, projection_run

SEEDS = set(range(42, 47))
YEARS = range(1, 11)
MODEL = "gemma3:4b"
# Flood years are fixed by the scenario, not read from the runs; the post-run
# checks (flood_run_checks.py, 2026-10-16) found floods in years 3, 4 and 9 in all 15 runs.
FLOOD_YEARS = (3, 4, 9)
GROUPS = {
    "strict": ("Governed LLM", "#0072B2"),
    "disabled": ("Governed LLM (no validator)", "#D55E00"),
}
RULEBASED_COMMIT = "186abb29"
STATES = ("DN", "FI", "HE", "FI+HE", "RL")
STATE_COLORS = dict(zip(STATES, ("#0072B2", "#E69F00", "#009E73", "#D55E00", "#CC79A7")))
STATE_MAP = {
    "Do Nothing": "DN", "Only Flood Insurance": "FI", "Only House Elevation": "HE",
    "Both Flood Insurance and House Elevation": "FI+HE",
    "Relocate": "RL", "Already relocated": "RL",
}
LEVELS = ("VL", "L", "M", "H", "VH")
ACTION_STATES = {"do_nothing": "DN", "buy_insurance": "FI", "elevate_house": "HE", "relocate": "RL"}
BAR_SEGMENTS = ("DN", "DN_default", "FI", "HE", "RL")


def _finite(row: dict[str, Any], key: str, run: Path) -> float:
    value = row.get(key)
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise MetricsError(f"{run}: {key} must be present and finite, got {value!r}") from exc
    if not math.isfinite(number):
        raise MetricsError(f"{run}: {key} must be finite, got {value!r}")
    return number


def _runs(folder: Path) -> list[Path]:
    if not folder.is_dir():
        raise MetricsError(f"Missing group folder: {folder}")
    runs = sorted(path for path in folder.glob("Run_*") if path.is_dir())
    expected_names = {f"Run_{seed}" for seed in SEEDS}
    if len(runs) != 5 or {path.name for path in runs} != expected_names:
        raise MetricsError(
            f"{folder}: expected exactly 5 run folders Run_42 through Run_46; "
            f"found {[path.name for path in runs]}"
        )
    return runs


def _load_group(results_root: Path, profile: str, commit: str) -> list[dict[str, Any]]:
    folder = results_root / f"JOH_{profile}_defaults_gemma3_4b_{commit}"
    rows = []
    for run in _runs(folder):
        row = {**projection_run(run), "run": run}
        if row.get("seed") not in SEEDS or run.name != f"Run_{row['seed']}":
            raise MetricsError(f"{run}: expected matching seed in 42..46, got {row.get('seed')!r}")
        recorded = (row.get("governance_profile"), row.get("retry_feedback_mode"), row.get("model"))
        if recorded != (profile, "full", MODEL) or not str(row.get("commit") or "").startswith(commit):
            raise MetricsError(f"{run}: manifest says profile/feedback/model {recorded}, "
                               f"commit {row.get('commit')!r}; expected ({profile!r}, 'full', {MODEL!r}), {commit}")
        years = {key for key in row if re.fullmatch(r"year_\d+_ehe", key)}
        if years != {f"year_{year}_ehe" for year in YEARS}:
            raise MetricsError(f"{run}: expected yearly EHE for years 1..10 only, got {sorted(years)}")
        for key in ("n_aborted", "physical_count"):
            if row.get(key) != 0:
                raise MetricsError(f"{run}: expected {key} == 0, got {row.get(key)!r}")
        for key in ("first_behavioural_pct", "behavioural_ibr_pct", "ehe"):
            _finite(row, key, run)
        if profile == "disabled":
            difference = abs(row["first_behavioural_pct"] - row["behavioural_ibr_pct"])
            if difference >= 1e-9:
                raise MetricsError(
                    f"{run}: no-validator first_behavioural_pct must equal "
                    f"behavioural_ibr_pct within abs diff < 1e-9; got {difference}"
                )
        for year in YEARS:
            _finite(row, f"year_{year}_ehe", run)
        rows.append(row)
    if {row["seed"] for row in rows} != SEEDS:
        raise MetricsError(f"{folder}: expected seeds 42..46 exactly once")
    return rows


def _load_rulebased_group(results_root: Path, directory: str) -> list[dict[str, Any]]:
    rows = []
    for run in _runs(results_root / directory):
        row = {**projection_run(run), "run": run}
        if not str(row.get("commit") or "").startswith(RULEBASED_COMMIT):
            raise MetricsError(f"{run}: rule-based commit must start with {RULEBASED_COMMIT}; got {row.get('commit')!r}")
        if row.get("seed") not in SEEDS or run.name != f"Run_{row['seed']}":
            raise MetricsError(f"{run}: expected matching seed in 42..46")
        _finite(row, "ehe", run)
        rows.append(row)
    return rows


def protection_state(row: Mapping[str, Any]) -> str:
    """Earlier _map_state_col mapping and column priority; an unknown state raises."""
    column = "cumulative_state" if "cumulative_state" in row else "decision"
    if column not in row:
        raise MetricsError("Missing cumulative_state/decision protection state")
    if row[column] not in STATE_MAP:
        raise MetricsError(f"Unknown protection state {row[column]!r} in {column}")
    return STATE_MAP[row[column]]


def _boolean_state(row: Mapping[str, Any]) -> str:
    values = {}
    for key in ("relocated", "elevated", "has_insurance"):
        value = str(row.get(key, "")).strip().lower()
        if value not in {"true", "false", "1", "0", "1.0", "0.0", "yes", "no"}:
            raise MetricsError(f"{row.get('agent_id')}, {row.get('year')}: invalid {key} boolean")
        values[key] = value in {"true", "1", "1.0", "yes"}
    if values["relocated"]:
        return "RL"
    if values["elevated"]:
        return "FI+HE" if values["has_insurance"] else "HE"
    return "FI" if values["has_insurance"] else "DN"


def _check_state_agreement(sim_frames: Sequence[Sequence[Mapping[str, Any]]], label: str) -> None:
    total = disagreements = 0
    examples = []
    for seed_index, frame in enumerate(sim_frames):
        for row in frame:
            total += 1
            mapped, booleans = protection_state(row), _boolean_state(row)
            if mapped != booleans:
                disagreements += 1
                if len(examples) < 5:
                    examples.append(f"seed {42 + seed_index}, agent {row.get('agent_id')}, year {row.get('year')}: "
                                    f"mapped {mapped}, booleans {booleans}; {dict(row)}")
    print(f"{label} state cross-check: {total - disagreements}/{total} agreements; {disagreements} disagreements")
    if disagreements:
        raise MetricsError(f"{label}: {disagreements} state disagreements; " + "; ".join(examples))


def _load_simulations(rows: Sequence[Mapping[str, Any]], label: str) -> list[list[dict[str, str]]]:
    frames = []
    for result in rows:
        path = Path(result["run"]) / "simulation_log.csv"
        columns, frame = measures._csv(path)
        required = {"agent_id", "year", "relocated", "elevated", "has_insurance"}
        if required - columns or not {"cumulative_state", "decision"} & columns:
            raise MetricsError(f"{path}: missing protection-state columns")
        keys = [measures._key(row, str(path)) for row in frame]
        if len(set(keys)) != len(keys):
            raise MetricsError(f"{path}: duplicate agent-year")
        if {int(key[1]) for key in keys} != set(YEARS):
            raise MetricsError(f"{path}: expected simulation years 1..10 only")
        frames.append(frame)
    return frames


def state_counts(sim_frames: Sequence[Sequence[Mapping[str, Any]]]) -> dict[int, dict[str, float]]:
    """Mean counts across seeds; count relocation once and drop later rows."""
    if not sim_frames:
        raise MetricsError("No simulation frames for protection counts")
    counts = {year: dict.fromkeys(STATES, 0.0) for year in YEARS}
    for frame in sim_frames:
        normalized = []
        seen = set()
        relocated_year = {}
        for row in frame:
            agent, year_text = measures._key(row, "protection counts")
            year = int(year_text)
            if year not in YEARS or (agent, year) in seen:
                raise MetricsError(f"Protection counts: duplicate/out-of-range agent-year {(agent, year)}")
            seen.add((agent, year))
            state = protection_state(row)
            normalized.append((agent, year, state))
            if state == "RL":
                relocated_year[agent] = min(year, relocated_year.get(agent, year))
        for agent, year, state in normalized:
            if year <= relocated_year.get(agent, 11):
                counts[year][state] += 1 / len(sim_frames)
    return counts


def _load_executed_decisions(run: Path) -> list[audit.Decision]:
    """Use projection_run's CSV, key normalization and decision parser."""
    path = run / "household_governance_audit.csv"
    _, raw_rows = measures._csv(path)
    decisions, seen = [], set()
    for line, raw in enumerate(raw_rows, 2):
        where = f"{path}:{line}"
        key = measures._key(raw, where)
        if key in seen or int(key[1]) not in YEARS:
            raise MetricsError(f"{where}: duplicate/out-of-range audit decision {key}")
        seen.add(key)
        decisions.append(audit.parse_decision({**raw, "agent_id": key[0], "year": key[1]}, where))
    return [d for d in decisions if not d.aborted]


def first_proposal_rule(d: audit.Decision) -> str | None:
    """Exactly the first-proposal behavioural predicates in ibr_summary."""
    tp, cp = (measures._label(d.first_labels, key) for key in ("TP_LABEL", "CP_LABEL"))
    proposal = measures._action(d.first_proposal, "blocked decisions: first proposal")
    flags = {
        "R1": proposal == "do_nothing" and tp in {"H", "VH"} and cp in {"M", "H", "VH"},
        "R3": proposal == "relocate" and tp in {"VL", "L"},
        "R4": proposal == "elevate_house" and tp in {"VL", "L"},
    }
    return next((rule for rule, flagged in flags.items() if flagged), None)


def _r1_region(d: audit.Decision) -> bool:
    tp, cp = (measures._label(d.first_labels, key) for key in ("TP_LABEL", "CP_LABEL"))
    return tp in {"H", "VH"} and cp in {"M", "H", "VH"}


def blocked_action_counts(decisions: Sequence[audit.Decision]) -> dict[str, Any]:
    """Final actions for blocked proposals and unforced R1-region choices."""
    counts = {bar: dict.fromkeys(BAR_SEGMENTS, 0) for bar in ("blocked", "accepted")}
    counts["blocked_outside_r1"] = 0
    for d in decisions:
        if d.aborted:
            continue
        rule = first_proposal_rule(d)
        in_region = _r1_region(d)
        if rule:
            bar = "blocked"
            counts["blocked_outside_r1"] += not in_region
        elif in_region:
            bar = "accepted"
        else:
            continue
        action = measures._action(d.executed_skill, "blocked decisions: executed action")
        segment = ACTION_STATES[action]
        if segment == "DN" and d.execution_path == "rejected_default":
            segment = "DN_default"
        counts[bar][segment] += 1
    return counts


def _print_blocked_counts(label: str, counts: Mapping[str, Any]) -> None:
    for bar in ("blocked", "accepted"):
        actions = counts[bar]
        n = sum(actions.values())
        shares = ", ".join(f"{state}={count} ({100 * count / n:.2f}%)" if n else f"{state}=0 (NA)"
                           for state, count in actions.items())
        print(f"{label} {bar}: n={n}; {shares}")
        protective = sum(actions[state] for state in ("FI", "HE", "RL"))
        shares = ", ".join(f"{state}={100 * actions[state] / protective:.2f}%" if protective else f"{state}=NA"
                           for state in ("FI", "HE", "RL"))
        print(f"{label} {bar} protective actions only: n={protective}; {shares}")
    print(f"{label} blocked decisions outside R1 appraisal region: {counts['blocked_outside_r1']}")


def _load_blocked_counts(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    pooled = blocked_action_counts([])
    for result in rows:
        run = Path(result["run"])
        counts = blocked_action_counts(_load_executed_decisions(run))
        n = sum(counts["blocked"].values())
        if n != result.get("first_behavioural_count"):
            raise MetricsError(f"{run}: blocked {n} != first_behavioural_count "
                               f"{result.get('first_behavioural_count')!r}")
        print(f"Governed LLM {run.name} cross-check: blocked {n} == first_behavioural_count {n}")
        _print_blocked_counts(f"Governed LLM seed {result['seed']}", counts)
        for bar in ("blocked", "accepted"):
            for segment in BAR_SEGMENTS:
                pooled[bar][segment] += counts[bar][segment]
        pooled["blocked_outside_r1"] += counts["blocked_outside_r1"]
    _print_blocked_counts("Governed LLM pooled", pooled)
    print(f"Pooled default after rejections: {pooled['blocked']['DN_default']}; "
          f"summed projection_run behavioural_count: {sum(row['behavioural_count'] for row in rows)}")
    return pooled


def _load_grid_records(rows: Sequence[Mapping[str, Any]], label: str) -> list[dict[str, Any]]:
    records = []
    for result in rows:
        run = Path(result["run"])
        executed = _load_executed_decisions(run)
        pre = measures._pre_elevation(run, {(d.agent_id, d.year) for d in executed}) if executed else {}
        run_records = []
        for d in executed:
            key = (d.agent_id, d.year)
            if key not in pre:
                raise MetricsError(f"{run}: missing pre-decision elevation for {key}")
            flags = measures.rule_flags(d, pre[key])
            run_records.append({"ta": measures._label(d.first_labels, "TP_LABEL"),
                                "ca": measures._label(d.first_labels, "CP_LABEL"),
                                "action": d.executed_skill,
                                "flagged": any(flags[r] for r in ("R1", "R3", "R4"))})
        flagged = sum(record["flagged"] for record in run_records)
        if flagged != result.get("behavioural_count"):
            raise MetricsError(f"{run}: flagged {flagged} != behavioural_count {result.get('behavioural_count')!r}")
        print(f"{label} {run.name} cross-check: flagged {flagged} == behavioural_count {result['behavioural_count']}")
        records.extend(run_records)
    missing = sum(not r["ta"] or not r["ca"] for r in records)
    print(f"{label} grid: {missing} decisions omitted for missing first-stated labels")
    return records


def grid_cells(records: Sequence[Mapping[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    """Pool decisions by first-stated appraisal; retain counts in masked cells."""
    cells = {(ta, ca): {"n": 0, "flagged": 0, "actions": dict.fromkeys(ACTION_STATES, 0)}
             for ta in LEVELS for ca in LEVELS}
    for record in records:
        ta, ca = record.get("ta"), record.get("ca")
        if not ta or not ca:
            continue
        if (ta, ca) not in cells or record.get("action") not in ACTION_STATES:
            raise MetricsError(f"Invalid appraisal/action grid record: {record}")
        cell = cells[ta, ca]
        cell["n"] += 1
        cell["flagged"] += bool(record["flagged"])
        cell["actions"][record["action"]] += 1
    for cell in cells.values():
        n = cell["n"]
        cell["share"] = cell["flagged"] / n if n else None
        cell["mask"] = "n=0" if n == 0 else "n<30" if n < 30 else None
    return cells


def _grid_vmax(grids: Sequence[Mapping[tuple[str, str], Mapping[str, Any]]]) -> float:
    largest = max((cell["share"] for cells in grids for cell in cells.values()
                   if cell["mask"] is None), default=0.0)
    upper = max(0.25, math.ceil(largest / 0.05) * 0.05)
    if upper > 0.25:
        print(f"Raised appraisal-action inconsistency colour upper limit from 0.25 to {upper:.2f}")
    return upper


def _values(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([row[key] for row in rows], dtype=float)


def _summary(label: str, rows: list[dict[str, Any]], key: str) -> None:
    values = _values(rows, key)
    per_seed = ", ".join(f"{row['seed']}={value:.2f}" for row, value in zip(rows, values))
    print(f"{label}: per seed [{per_seed}]; median {np.median(values):.2f}; "
          f"min {values.min():.2f}; max {values.max():.2f}")


def _draw_grid(ax, cells, title, color, cmap, norm, show_ylabel):
    ax.set(xlim=(-0.5, 4.5), ylim=(-0.5, 4.5), aspect="equal")
    ax.set_xticks(range(5), LEVELS)
    ax.set_yticks(range(5), LEVELS if show_ylabel else [""] * 5)
    ax.set_xlabel("Coping appraisal (CA)", labelpad=3)
    if show_ylabel:
        ax.set_ylabel("Threat appraisal (TA)", labelpad=2)
    ax.set_title(title, color=color, fontweight="bold", fontsize=7.4, pad=7)
    maximum = max((cell["n"] for cell in cells.values() if cell["mask"] is None), default=1)
    for i, ta in enumerate(LEVELS):
        for j, ca in enumerate(LEVELS):
            cell = cells[ta, ca]
            masked = cell["mask"] is not None
            ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1,
                                   facecolor="#DDDDDD" if masked else cmap(norm(cell["share"])),
                                   edgecolor="#DDDDDD", linewidth=0.4))
            if masked:
                ax.text(j, i, cell["mask"], ha="center", va="center", fontsize=6, color="#707070")
                continue
            # Retain the earlier figure's square-root radius scaling and limits.
            radius = 0.16 + (0.44 - 0.16) * math.sqrt(cell["n"] / maximum)
            start = 90.0
            for action, state in ACTION_STATES.items():
                fraction = cell["actions"][action] / cell["n"]
                if fraction:
                    end = start - fraction * 360
                    ax.add_patch(Wedge((j, i), radius, min(start, end), max(start, end),
                                       facecolor=STATE_COLORS[state], edgecolor="white", linewidth=0.7))
                    start = end
            ax.text(j + 0.43, i + 0.43, f"{cell['share']:.2f}", ha="right", va="top",
                    fontsize=6, color="#333333", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.12", facecolor="white",
                              edgecolor="#AAAAAA", linewidth=0.4, alpha=0.85))
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color("#CCCCCC")


def _draw_blocked_bars(ax, counts):
    labels = ("Blocked first proposals,\nfinal action", "Same appraisal, accepted\nat first proposal")
    for y, bar, label in zip((1, 0), ("blocked", "accepted"), labels):
        n = sum(counts[bar].values())
        ax.text(0, y + 0.28, f"{label} (n={n})", fontsize=7, va="bottom")
        left = 0.0
        for segment in BAR_SEGMENTS:
            share = 100 * counts[bar][segment] / n if n else 0
            default = segment == "DN_default"
            color = STATE_COLORS["DN" if default else segment]
            ax.barh(y, share, left=left, height=0.34, color=color,
                    edgecolor="white", linewidth=0.5, hatch="////" if default else None, zorder=2)
            if share >= 5:
                ax.text(left + share / 2, y, f"{share:.0f}%", ha="center", va="center",
                        fontsize=7, color="black" if segment == "FI" else "white", fontweight="bold",
                        bbox=dict(facecolor=color, edgecolor="none", pad=0.8) if default else None)
            left += share
    ax.set(xlim=(0, 100), ylim=(-0.4, 1.85), xlabel="Share of decisions (%)")
    ax.set_xticks(range(0, 101, 20))
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.set_axisbelow(True)
    ax.grid(axis="x", alpha=0.25)
    ax.set_title("Where blocked decisions went", fontsize=7.4, fontweight="bold", pad=7)
    ax.legend([Patch(facecolor=STATE_COLORS["DN"], edgecolor="white", hatch="////")],
              ["Do nothing (default after rejections)"], loc="upper left",
              bbox_to_anchor=(0, -0.25), fontsize=6.5, frameon=False, borderaxespad=0)


def _save_figure(fig, out_dir: Path, stem: str) -> None:
    try:
        out_dir.mkdir(parents=True, exist_ok=True)
        for extension in ("png", "pdf"):
            destination = out_dir / f"{stem}.{extension}"
            fig.savefig(destination, dpi=300, facecolor="white")
            print(f"Wrote {destination}")
    finally:
        plt.close(fig)


def _plot_supplement(cells, out_dir: Path) -> None:
    fig = plt.figure(figsize=(7.2, 4.3))
    spec = fig.add_gridspec(1, 2, left=0.085, right=0.985, bottom=0.29, top=0.9, wspace=0.15)
    cmap = LinearSegmentedColormap.from_list("incons", ["#2C7FB8", "#FFFFBF", "#D7301F"], N=256)
    norm = Normalize(vmin=0, vmax=_grid_vmax(list(cells.values())))
    axes = []
    for index, (profile, (title, color)) in enumerate(GROUPS.items()):
        ax = fig.add_subplot(spec[index])
        axes.append(ax)
        _draw_grid(ax, cells[profile], title, color, cmap, norm, index == 0)
    left, right = axes[0].get_position(), axes[1].get_position()
    legend_y = min(left.y0, right.y0) - 0.095
    fig.legend([Patch(facecolor=STATE_COLORS[state], edgecolor="white") for state in ACTION_STATES.values()],
               list(ACTION_STATES.values()), loc="upper center", bbox_to_anchor=((left.x0 + right.x1) / 2, legend_y),
               ncol=4, fontsize=6.5, handlelength=0.8, columnspacing=1, frameon=False)
    cax = fig.add_axes([left.x0 + 0.035, legend_y - 0.075, right.x1 - left.x0 - 0.07, 0.012])
    cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), cax=cax, orientation="horizontal")
    cb.set_label("Appraisal-action inconsistency", fontsize=7, labelpad=2)
    cb.ax.tick_params(labelsize=6)
    _save_figure(fig, out_dir, "FigS_flood_appraisal_grid")


def _plot(groups, counts, cells, blocked, out_dir: Path) -> None:
    plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Arial", "Helvetica"],
                         "font.size": 7.5, "axes.labelsize": 7.5, "axes.labelweight": "bold",
                         "axes.spines.top": False, "axes.spines.right": False,
                         "xtick.labelsize": 6.5, "ytick.labelsize": 6.5,
                         "pdf.fonttype": 42, "ps.fonttype": 42})
    fig = plt.figure(figsize=(7.2, 6.2))
    outer = gridspec.GridSpec(2, 1, height_ratios=[1, 1], left=0.085, right=0.985,
                             top=0.86, bottom=0.19, hspace=0.55)
    top = outer[0].subgridspec(1, 3, wspace=0.15)
    axes_a = []
    for index, profile in enumerate(("strict", "disabled", "rulebased")):
        ax = fig.add_subplot(top[index], sharey=axes_a[0] if axes_a else None)
        axes_a.append(ax)
        title, color = GROUPS.get(profile, ("Rule-based", "#666666"))
        bottom = np.zeros(10)
        for year in FLOOD_YEARS:
            ax.axvspan(year - 0.36, year + 0.36, color="#F5DADA", alpha=0.42, zorder=0)
        for state in STATES:
            values = [counts[profile][year][state] for year in YEARS]
            ax.bar(list(YEARS), values, bottom=bottom, width=0.75, color=STATE_COLORS[state],
                   edgecolor="white", linewidth=0.4, zorder=2)
            bottom += values
        ax.set_title(title, color=color, fontweight="bold", fontsize=7.4, pad=24)
        ax.set(xlim=(0.5, 10.5), ylim=(0, 110), xlabel="Year")
        ax.set_xticks(list(YEARS))
        ax.set_yticks(range(0, 101, 20))
        ax.tick_params(axis="x", labelsize=6)
        if index == 0:
            ax.set_ylabel("Households")
        else:
            ax.tick_params(labelleft=False)
        for year in FLOOD_YEARS:
            ax.text(year, 106, "F", ha="center", va="center", fontsize=7.3,
                    color="#D94B4B", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.22,rounding_size=0.03",
                              facecolor="#F9EFEF", edgecolor="#EBCACA", linewidth=0.8))
        if profile in GROUPS:
            values = _values(groups[profile], "ehe")
            ax.text(0.99, 1.015, f"EHE {np.median(values):.2f} ({values.min():.2f}\u2013{values.max():.2f})",
                    transform=ax.transAxes, ha="right", va="bottom", fontsize=6.7)
    fig.legend([Patch(facecolor=STATE_COLORS[state], edgecolor="white") for state in STATES],
               STATES, loc="upper center", bbox_to_anchor=(0.53, 0.99), ncol=5, fontsize=7,
               handlelength=1, handletextpad=0.3, columnspacing=1.2,
               frameon=True, edgecolor="#888888")

    lower = outer[1].subgridspec(1, 2, width_ratios=[1.5, 1], wspace=0.45)
    ax_b = fig.add_subplot(lower[0])
    _draw_blocked_bars(ax_b, blocked)

    ax_c = fig.add_subplot(lower[1])
    bars = [("Governed:\nfirst proposal", "strict", "first_behavioural_pct", 0.45),
            ("Governed:\nexecuted", "strict", "behavioural_ibr_pct", 1.0),
            ("No validator:\nexecuted", "disabled", "behavioural_ibr_pct", 1.0)]
    largest = 0.0
    for x, (_, profile, key, alpha) in enumerate(bars):
        values = _values(groups[profile], key)
        largest = max(largest, float(values.max()))
        ax_c.bar(x, np.median(values), width=0.6, color=GROUPS[profile][1], alpha=alpha)
        ax_c.vlines(x, values.min(), values.max(), color="black", lw=0.8)
        ax_c.scatter([x] * len(values), values, s=6, color="black", zorder=3)
        ax_c.annotate(f"{np.median(values):.2f}%", (x, values.max()), xytext=(0, 4),
                      textcoords="offset points", ha="center", va="bottom", fontsize=6)
    ax_c.set_xticks(range(3), [item[0] for item in bars], fontsize=5.8, rotation=35, ha="right")
    ax_c.set_ylabel("Decisions contradicting the\nhousehold's own appraisal (%)", fontsize=7, labelpad=2)
    ax_c.set_ylim(0, largest * 1.25 if largest else 1)
    ax_c.set_title("What the validator removed", fontsize=7.4, fontweight="bold", pad=7)
    ax_c.set_axisbelow(True)
    ax_c.grid(axis="y", alpha=0.25)
    for ax, letter, x in ((axes_a[0], "a", 0.015), (ax_b, "b", 0.015),
                          (ax_c, "c", ax_c.get_position().x0 - 0.045)):
        fig.text(x, ax.get_position().y1 + (0.056 if letter == "a" else 0.025), letter,
                 fontsize=10, fontweight="bold", va="bottom")
    _save_figure(fig, out_dir, "Fig2_flood_sq1")
    _plot_supplement(cells, out_dir)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-root", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--commit", default="9c4ba160")
    parser.add_argument("--rulebased-dir", default="rulebased_5seed_186abb29")
    args = parser.parse_args(argv)
    results_root = args.results_root.resolve()
    out_dir = args.out_dir.resolve()
    if out_dir.is_relative_to(results_root):
        raise MetricsError("--out-dir must be outside --results-root")
    try:
        groups = {profile: _load_group(results_root, profile, args.commit) for profile in GROUPS}
        groups["rulebased"] = _load_rulebased_group(results_root, args.rulebased_dir)
        counts, cells = {}, {}
        for profile, rows in groups.items():
            label = GROUPS.get(profile, ("Rule-based", "#666666"))[0]
            frames = _load_simulations(rows, label)
            _check_state_agreement(frames, label)
            counts[profile] = state_counts(frames)
            for year, states in counts[profile].items():
                print(f"{label} year {year} mean states: " + ", ".join(f"{s}={states[s]:.2f}" for s in STATES))
            _summary(f"Pooled EHE {label}", rows, "ehe")
            if profile in GROUPS:
                cells[profile] = grid_cells(_load_grid_records(rows, label))
                for (ta, ca), cell in cells[profile].items():
                    share = f"{cell['share']:.4f}" if cell["share"] is not None else "NA"
                    print(f"{label} grid TA={ta} CA={ca}: n={cell['n']}, flagged={cell['flagged']}, share={share}")
        for label, profile, key in (("Governed first proposal", "strict", "first_behavioural_pct"),
                                    ("Governed executed", "strict", "behavioural_ibr_pct"),
                                    ("No validator executed", "disabled", "behavioural_ibr_pct")):
            _summary(label, groups[profile], key)
        print("Group title and panel (c) colours: governed #0072B2; no validator #D55E00 (earlier palette)")
        blocked = _load_blocked_counts(groups["strict"])
        _plot(groups, counts, cells, blocked, out_dir)
    except MetricsError:
        raise
    except (OSError, ValueError, TypeError, KeyError, OverflowError) as exc:
        raise MetricsError(f"Fig 2: {exc}") from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
