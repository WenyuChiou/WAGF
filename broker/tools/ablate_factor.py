"""Test whether a context factor is what a recorded decision actually used.

Usage
-----
    python -m broker.tools.ablate_factor <run_dir> --factor F [--factor G] \\
        [--control paraphrase] --seeds 42,43 --replicates 3 \\
        --model mock --masks <module:attr> --out <dir>

    python -m broker.tools.ablate_factor <run_dir> --masks <module:attr> \\
        --list-factors

Writes ``ablation_samples.csv`` (one row per replay),
``ablation_summary.json`` (the per-factor verdict) and
``determinism_report.json`` (the gate) into ``--out``.

What it answers, and what it does not
-------------------------------------
It answers: when this factor is replaced by a neutral rendering and the
same decision is replayed at the same seed, does the probability of the
action the agent chose move — and does it move MORE than when the same
factor is merely reworded?

It does not answer whether the agent's reasoning text was honest. A
factor can be causal and unmentioned, or mentioned and inert. The
ablation measures behaviour under intervention; the reasoning text is a
separate observable that this tool never treats as evidence.

Where the factors come from
---------------------------
A domain declares them through ``DomainPack.context_mask_defaults()``.
Point ``--domain`` at a registered pack, or ``--masks`` at a module
attribute holding the dict directly (for example
``examples.single_agent.flood_factor_masks:FLOOD_FACTOR_MASKS``). With
neither, the CLI stops: guessing at a prompt's wording would produce a
mask that matches nothing and a null result that means nothing.

Three refusals worth knowing before you run it
-----------------------------------------------
``--model`` is resolved once — the flag if given, else the model the run
recorded, else the tool stops. It never falls back to ``mock``, whose
decider returns the first numbered option whatever the prompt says.

``--with-governance`` needs ``--validators-module``, and is in any case
unavailable on today's traces: the audit writer does not record the
option set the agent was offered, and replaying governance without it
re-offers one-way skills. Both refusals name what is missing.

``--action-stage executed`` needs ``--with-governance``, because a
parse-only replay produces no post-governance action to compare against.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import csv
import dataclasses
import importlib
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from broker.experiments.ablation import (
    DEFAULT_DETERMINISM_SNAPSHOTS,
    AblationDesign,
    AblationResult,
    run_ablation,
)
from broker.experiments.replay import (
    FactorMap,
    ReplayResult,
    build_replay_decider,
    load_snapshots,
    resolve_model,
)


_THINKING_MODES = ("auto", "disabled", "enabled")


def _load_source_thinking_mode(run_dir: Path) -> str:
    """Return the source run's mode; pre-field manifests historically used auto."""
    manifest_path = run_dir / "reproducibility_manifest.json"
    if not manifest_path.is_file():
        return "auto"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"could not read {manifest_path} to recover thinking_mode: {exc}"
        ) from exc
    if not isinstance(manifest, dict):
        raise ValueError(
            f"{manifest_path} must contain a JSON object to recover thinking_mode"
        )
    if "thinking_mode" not in manifest:
        return "auto"
    mode = manifest["thinking_mode"]
    if not isinstance(mode, str) or mode not in _THINKING_MODES:
        raise ValueError(
            f"source manifest thinking_mode must be one of "
            f"{', '.join(_THINKING_MODES)}; got {mode!r}"
        )
    return mode


@contextmanager
def _temporary_thinking_mode(mode: str):
    """Scope replay request behavior without leaking into later runs."""
    from broker.utils.llm_utils import LLM_CONFIG

    previous = LLM_CONFIG.thinking_mode
    LLM_CONFIG.thinking_mode = mode
    try:
        yield
    finally:
        LLM_CONFIG.thinking_mode = previous


def _load_masks(spec: str) -> FactorMap:
    """Import ``module:attr`` and wrap it as a FactorMap."""
    if ":" not in spec:
        raise ValueError(
            f"--masks expects 'module:attribute' (got {spec!r}), for example "
            "examples.single_agent.flood_factor_masks:FLOOD_FACTOR_MASKS"
        )
    module_name, attr = spec.split(":", 1)
    module = importlib.import_module(module_name)
    value = getattr(module, attr)
    if isinstance(value, FactorMap):
        return value
    if callable(value) and not isinstance(value, dict):
        value = value()
    return FactorMap(dict(value))


def _resolve_factor_map(args: argparse.Namespace) -> FactorMap:
    if args.masks:
        return _load_masks(args.masks)
    if args.domain:
        if args.import_module:
            importlib.import_module(args.import_module)
        return FactorMap.from_domain(args.domain)
    raise SystemExit(
        "ERROR: no factors declared. Pass --domain <registered pack> or "
        "--masks <module:attr>. A run directory does not record which parts "
        "of its prompt are which factor, and inventing patterns would "
        "produce a mask that matches nothing."
    )


def _parse_int_list(text: str, flag: str) -> List[int]:
    try:
        return [int(part) for part in text.split(",") if part.strip()]
    except ValueError as exc:
        raise SystemExit(f"ERROR: {flag} expects comma-separated integers ({exc}).")


#: Column order for ``ablation_samples.csv`` when the grid produced zero
#: rows. Derived from ``ReplayResult``'s own field order plus the two
#: columns ``run_ablation`` adds to every row (see
#: ``AblationResult.samples``), so a header written on an empty run can
#: never drift from the header a populated run would have written.
_SAMPLE_CSV_COLUMNS: List[str] = [
    f.name for f in dataclasses.fields(ReplayResult)
] + ["determinism_verified", "decider_source"]


def _write_csv(
    path: Path, rows: List[Dict[str, Any]],
    fieldnames: Optional[List[str]] = None,
) -> None:
    """Write ``rows`` as CSV. Small (item 8): a zero-row ablation still
    writes a header when the caller can name one, instead of an empty
    file that cannot be told apart from "the write never happened"."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows and not fieldnames:
        path.write_text("", encoding="utf-8")
        return
    columns = list(rows[0].keys()) if rows else list(fieldnames)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, default=str)
        handle.write("\n")


def _print_report(result: AblationResult) -> None:
    summary = result.summary
    print(f"run_dir:   {summary['run_dir']}")
    print(f"commit:    {summary['git_commit']}")
    print(f"model:     {summary['model_used']}  (from {summary['model_source']})  "
          f"(governance {'evaluated' if summary['governance_evaluated'] else 'NOT evaluated'})")
    print(f"validators: {summary['validators_source']}")
    intake = summary.get("trace_intake") or {}
    if "n_traces_read" in intake:
        print(f"traces:    read {intake['n_traces_read']}, "
              f"malformed {intake['n_dropped_malformed']}, "
              f"no prompt {intake['n_skipped_no_prompt']}, "
              f"used {intake['n_snapshots']}")
    print(f"snapshots: {summary['n_snapshots']}  samples: {summary['n_samples']}")
    print(f"fidelity:  {summary['fidelity_regimes']}")
    quality = summary["decision_quality"]
    print(f"decider:   {quality['n_decider_calls']} call(s), "
          f"{quality['n_empty_outputs']} empty, {quality['n_unparsed']} unparsed, "
          f"{quality['n_errors']} error(s); "
          f"{quality['n_calls_skipped_no_edit']} arm(s) skipped (no edit)")
    if quality["note"]:
        print(f"  {quality['note']}")
    reproduction = summary["baseline_reproduces_trace"]
    if reproduction["rate"] is not None:
        print(f"baseline reproduces trace: {reproduction['matched']}/{reproduction['n']}")
    if reproduction["note"]:
        print(f"  {reproduction['note']}")
    print(f"determinism: {'VERIFIED' if summary['determinism_verified'] else 'FAILED'}")
    if summary["delta_p_withheld"]:
        print(f"  {summary['delta_p_withheld']}")
    # Residual (code-reviewer): printed below the determinism line, not
    # above it — this block reads the same replays that line just
    # verdicted, so a reader should already know whether to trust it
    # before seeing the number.
    sensitivity = summary["decider_prompt_sensitivity"]
    if sensitivity["change_rate"] is not None:
        print(f"edits that changed a decision: {sensitivity['n_changed']}"
              f"/{sensitivity['n_compared']}")
    if sensitivity["note"]:
        print(f"  {sensitivity['note']}")
    if summary["seeds_note"]:
        print(f"seeds: {summary['seeds_note']}")
    print()
    for factor, block in summary["factors"].items():
        print(f"[{factor}]")
        print(f"  {block['verdict']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ablate_factor",
        description=(
            "Replay recorded decisions with one context factor neutralised, "
            "against a severity-matched paraphrase control."
        ),
    )
    parser.add_argument("run_dir", type=Path,
                        help="Finished experiment directory (needs raw/*_traces.jsonl).")
    parser.add_argument("--factor", action="append", default=[],
                        help="Factor to ablate. Repeat, or pass a comma-separated list.")
    parser.add_argument("--control", choices=["paraphrase", "none"], default="paraphrase",
                        help="Control arm. 'none' drops it — the masked effect is then "
                             "uninterpretable and the summary says so. Default: paraphrase.")
    parser.add_argument("--seeds", default="42",
                        help="Comma-separated seeds, applied identically to every arm.")
    parser.add_argument("--replicates", type=int, default=1,
                        help="Repeats per cell; a within-run determinism monitor.")
    parser.add_argument("--model", default=None,
                        help="Decider model. Default: the model the run's manifest "
                             "recorded. With neither, the tool stops rather than "
                             "falling back to 'mock'.")
    parser.add_argument("--out", type=Path, required=False, default=None,
                        help="Output directory. Default: <run_dir>/ablation.")
    parser.add_argument("--domain", default=None,
                        help="Registered DomainPack whose context_mask_defaults() declares "
                             "the factors.")
    parser.add_argument("--import-module", default=None,
                        help="Module to import first, so its pack registers "
                             "(e.g. examples.single_agent.flood_factor_masks).")
    parser.add_argument("--masks", default=None,
                        help="module:attribute holding the factor -> MaskSpec dict.")
    parser.add_argument("--agent-config", type=Path, default=None,
                        help="agent_types.yaml to parse with. Default: the path the run's "
                             "manifest recorded, else the run's config_snapshot.yaml.")
    parser.add_argument("--with-governance", action="store_true",
                        help="Also re-run validators. Needs --validators-module and "
                             "skill_registry.yaml beside the agent config, and is "
                             "unavailable on traces that do not record available_skills "
                             "(all of them today). Refuses rather than guessing.")
    parser.add_argument("--validators-module", default=None,
                        help="Import path of a module exposing "
                             "build_custom_validators(config) -> list, returning the "
                             "same list the experiment passed to "
                             "ExperimentBuilder.with_custom_validators(). Required by "
                             "--with-governance: a run directory does not record it.")
    parser.add_argument("--action-stage", choices=["proposed", "executed"], default="proposed",
                        help="Which recorded action delta-P is measured against, and which "
                             "action the replay distributions are built from. Default: "
                             "proposed (the choice the reasoning text explains). "
                             "'executed' needs --with-governance.")
    parser.add_argument("--determinism-n", type=int, default=5,
                        help="Unmasked replays per gated snapshot.")
    parser.add_argument("--determinism-snapshots", type=int,
                        default=DEFAULT_DETERMINISM_SNAPSHOTS,
                        help=f"How many snapshots the gate samples (default "
                             f"{DEFAULT_DETERMINISM_SNAPSHOTS}); 0 gates every snapshot. "
                             "The gate is a question about the backend, not about one "
                             "prompt.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Use only the first N snapshots.")
    parser.add_argument("--agent-type", default=None,
                        help="Restrict to one agent type.")
    parser.add_argument("--list-factors", action="store_true",
                        help="Print the declared factors and exit.")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        factor_map = _resolve_factor_map(args)
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — a bad --masks is user error
        print(f"ERROR: could not load factors: {exc}", file=sys.stderr)
        return 2

    if args.list_factors:
        if not len(factor_map):
            print("No factors declared for this domain.")
            return 1
        print(json.dumps(factor_map.describe(), indent=2))
        return 0

    run_dir = args.run_dir.resolve()
    if not run_dir.is_dir():
        print(f"ERROR: {run_dir} is not a directory", file=sys.stderr)
        return 2

    factors: List[str] = []
    for entry in args.factor:
        factors.extend(part.strip() for part in entry.split(",") if part.strip())
    if not factors:
        print("ERROR: no --factor given. Run with --list-factors to see what "
              "this domain declares.", file=sys.stderr)
        return 2
    unknown = [f for f in factors if f not in factor_map]
    if unknown:
        print(f"ERROR: {unknown} not declared by this domain. Declared: "
              f"{factor_map.names}", file=sys.stderr)
        return 2

    if args.action_stage == "executed" and not args.with_governance:
        print(
            "ERROR: --action-stage executed needs --with-governance. The "
            "executed action is what the validators let through, and a "
            "parse-only replay never runs them — every executed-stage "
            "distribution would be a column of '__unparsed__'.",
            file=sys.stderr,
        )
        return 2
    if args.validators_module and not args.with_governance:
        print(
            "ERROR: --validators-module only means something with "
            "--with-governance. Without it no validator runs at all, so "
            "naming a validator module would suggest a governance verdict "
            "the run never produced.",
            file=sys.stderr,
        )
        return 2

    load_report: Dict[str, Any] = {}
    try:
        snapshots = load_snapshots(run_dir, agent_type=args.agent_type,
                                   limit=args.limit, report=load_report)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    if not snapshots:
        print(f"ERROR: no replayable decisions in {run_dir}", file=sys.stderr)
        return 1

    # ONE model resolution, shared by the decider and the summary, so a
    # run cannot be executed against one model and reported against
    # another. It refuses rather than defaulting to 'mock'.
    try:
        model, model_source = resolve_model(run_dir, args.model)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        source_thinking_mode = _load_source_thinking_mode(run_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    design = AblationDesign(
        factors=factors,
        controls=() if args.control == "none" else ("paraphrase",),
        seeds=_parse_int_list(args.seeds, "--seeds"),
        n_replicates=args.replicates,
        action_stage=args.action_stage,
        determinism_n=args.determinism_n,
        determinism_snapshots=(None if args.determinism_snapshots == 0
                               else args.determinism_snapshots),
    )

    with _temporary_thinking_mode(source_thinking_mode):
        try:
            # Residual (code-reviewer): snapshots are already loaded above, so
            # the missing-available_skills refusal can fire here, before the
            # adapter and the registry load, instead of only on the first
            # replay later in the run.
            decider = build_replay_decider(
                run_dir, model=model, agent_config=args.agent_config,
                with_governance=args.with_governance,
                validators_module=args.validators_module,
                snapshot=snapshots[0],
            )
        except FileNotFoundError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        except (ValueError, AttributeError, TypeError, ImportError) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

        from broker.utils.llm_utils import create_llm_invoke

        llm_invoke = create_llm_invoke(model)

        try:
            result = run_ablation(
                snapshots, design, llm_invoke,
                decider=decider, factor_map=factor_map,
                load_report=load_report,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    result.summary["factor_specs"] = {
        name: factor_map[name].to_dict() for name in factors
    }
    result.summary["cli"] = {
        "model": model,
        "model_source": model_source,
        "thinking_mode": source_thinking_mode,
        "control": args.control,
        "with_governance": bool(args.with_governance),
        "validators_module": args.validators_module,
        "action_stage": args.action_stage,
    }

    out_dir = (args.out or (run_dir / "ablation")).resolve()
    _write_csv(out_dir / "ablation_samples.csv", result.samples,
               fieldnames=_SAMPLE_CSV_COLUMNS)
    _write_json(out_dir / "ablation_summary.json", result.summary)
    _write_json(out_dir / "determinism_report.json", result.determinism)

    _print_report(result)
    print()
    print(f"wrote {out_dir / 'ablation_samples.csv'}")
    print(f"wrote {out_dir / 'ablation_summary.json'}")
    print(f"wrote {out_dir / 'determinism_report.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
