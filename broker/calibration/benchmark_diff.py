"""
Compare two benchmark tables and list where they disagree.

Why this exists: a project can end up with two tables of empirical
benchmarks for the same metrics — one feeding a generic
:class:`~broker.calibration.benchmark_registry.BenchmarkRegistry`, one
hardcoded inside a domain's own validation pipeline — and they drift
apart. The same metric name then carries two different plausible
ranges, so "the observed value is inside the empirical range" means
two different things depending on which table the code reached for.
Nothing crashes; the numbers just stop being comparable, and a report
that does not name its table is not checkable.

This module does not reconcile anything. Choosing which range is
right is a judgement about the literature, and belongs to a human. All
it does is make the disagreements enumerable, so a test can pin them
and they cannot quietly become invisible.

Two shapes of table are accepted, and either side may use either:

* a list of :class:`~broker.calibration.benchmark_registry.Benchmark`
  objects (``rate_low`` / ``rate_high`` / ``weight``);
* a plain dict ``{metric_name: {"range": (low, high), "weight": w}}``.

Metric names that mean the same thing but are spelled differently in
the two tables are handled by an explicit ``aliases`` mapping supplied
by the caller — this module has no opinion about which names are
synonyms, because that is domain knowledge.

Usage::

    from broker.calibration.benchmark_diff import diff_benchmark_tables

    report = diff_benchmark_tables(
        left=TABLE_A, right=TABLE_B,
        left_name="registry table", right_name="pipeline table",
        aliases={"metric_a": "metric_a_subset"},
    )
    print(report.to_markdown())
    assert not report.range_disagreements   # or pin them in a test
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

BenchmarkTable = Union[Iterable[Any], Mapping[str, Mapping[str, Any]]]
"""Either a list of ``Benchmark`` objects or a ``{name: {range, weight}}`` dict."""


@dataclass(frozen=True)
class BenchmarkSpec:
    """One table's opinion about one metric, in a table-shape-neutral form."""

    metric: str
    rate_low: float
    rate_high: float
    weight: float

    @property
    def as_range(self) -> Tuple[float, float]:
        return (self.rate_low, self.rate_high)


@dataclass(frozen=True)
class BenchmarkDisagreement:
    """One metric on which the two tables do not say the same thing.

    ``kind`` is one of:

    ``"range"``
        Both tables define the metric; the bounds differ.
    ``"weight"``
        Both tables define the metric with the same bounds; the weight
        differs, so the same observations produce different weighted
        scores.
    ``"only_in_left"`` / ``"only_in_right"``
        One table defines the metric and the other does not — either a
        genuine gap, or a name mismatch the caller has not declared in
        ``aliases``.
    """

    metric: str
    kind: str
    left: Optional[BenchmarkSpec]
    right: Optional[BenchmarkSpec]
    note: str = ""


@dataclass
class BenchmarkDiff:
    """Everything two benchmark tables disagree about."""

    left_name: str
    right_name: str
    disagreements: List[BenchmarkDisagreement] = field(default_factory=list)
    agreements: List[str] = field(default_factory=list)
    aliases_applied: Dict[str, str] = field(default_factory=dict)

    @property
    def range_disagreements(self) -> List[BenchmarkDisagreement]:
        return [d for d in self.disagreements if d.kind == "range"]

    @property
    def weight_disagreements(self) -> List[BenchmarkDisagreement]:
        return [d for d in self.disagreements if d.kind == "weight"]

    @property
    def only_in_one(self) -> List[BenchmarkDisagreement]:
        return [
            d for d in self.disagreements
            if d.kind in ("only_in_left", "only_in_right")
        ]

    def to_rows(self) -> List[Dict[str, Any]]:
        """Flat rows, one per disagreement — for a table or a CSV."""
        rows: List[Dict[str, Any]] = []
        for d in self.disagreements:
            rows.append({
                "metric": d.metric,
                "kind": d.kind,
                f"{self.left_name}_range": (
                    list(d.left.as_range) if d.left else None
                ),
                f"{self.left_name}_weight": d.left.weight if d.left else None,
                f"{self.right_name}_range": (
                    list(d.right.as_range) if d.right else None
                ),
                f"{self.right_name}_weight": d.right.weight if d.right else None,
                "note": d.note,
            })
        return rows

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left_name": self.left_name,
            "right_name": self.right_name,
            "n_disagreements": len(self.disagreements),
            "n_agreements": len(self.agreements),
            "aliases_applied": dict(self.aliases_applied),
            "disagreements": self.to_rows(),
            "agreements": list(self.agreements),
        }

    def to_markdown(self) -> str:
        """A markdown table of the disagreements, ready to paste into a doc."""
        header = (
            f"| Metric | Disagreement | {self.left_name} | "
            f"{self.right_name} |\n|---|---|---|---|"
        )
        if not self.disagreements:
            return header + "\n| _(none)_ | | | |"
        lines = [header]
        for d in self.disagreements:
            left = (
                f"[{d.left.rate_low}, {d.left.rate_high}] w={d.left.weight}"
                if d.left else "—"
            )
            right = (
                f"[{d.right.rate_low}, {d.right.rate_high}] w={d.right.weight}"
                if d.right else "—"
            )
            note = f" ({d.note})" if d.note else ""
            lines.append(f"| `{d.metric}` | {d.kind}{note} | {left} | {right} |")
        return "\n".join(lines)


def normalize_table(table: BenchmarkTable) -> Dict[str, BenchmarkSpec]:
    """Turn either accepted table shape into ``{metric: BenchmarkSpec}``.

    Raises ``ValueError`` on an entry it cannot read, rather than
    skipping it — a benchmark silently dropped from a comparison is the
    exact failure this module exists to prevent.
    """
    out: Dict[str, BenchmarkSpec] = {}
    if isinstance(table, Mapping):
        for metric, cfg in table.items():
            if not isinstance(cfg, Mapping) or "range" not in cfg:
                raise ValueError(
                    f"benchmark entry {metric!r} must be a mapping with a "
                    f"'range' key; got {cfg!r}"
                )
            bounds = cfg["range"]
            if not (isinstance(bounds, (list, tuple)) and len(bounds) == 2):
                raise ValueError(
                    f"benchmark entry {metric!r} has range {bounds!r}; "
                    f"expected a (low, high) pair"
                )
            key = str(metric)
            if key in out:
                raise ValueError(
                    f"duplicate metric name {key!r} in benchmark table "
                    f"(two entries collapse to the same key after string "
                    f"conversion) — silently keeping only the last one "
                    f"would drop the other from every comparison; rename "
                    f"one of the source keys"
                )
            out[key] = BenchmarkSpec(
                metric=key,
                rate_low=float(bounds[0]),
                rate_high=float(bounds[1]),
                weight=float(cfg.get("weight", 1.0)),
            )
        return out

    for item in table:
        metric = getattr(item, "metric", None)
        low = getattr(item, "rate_low", None)
        high = getattr(item, "rate_high", None)
        if metric is None or low is None or high is None:
            raise ValueError(
                f"benchmark entry {item!r} has no metric/rate_low/rate_high; "
                f"pass a Benchmark object or a {{metric: {{range, weight}}}} dict"
            )
        key = str(metric)
        if key in out:
            raise ValueError(
                f"duplicate metric name {key!r} in a list-shaped benchmark "
                f"table — two Benchmark entries share this metric; "
                f"silently keeping only the last one would drop the other "
                f"from every comparison. Remove or rename the duplicate."
            )
        out[key] = BenchmarkSpec(
            metric=key,
            rate_low=float(low),
            rate_high=float(high),
            weight=float(getattr(item, "weight", 1.0)),
        )
    return out


def diff_benchmark_tables(
    left: BenchmarkTable,
    right: BenchmarkTable,
    left_name: str = "left",
    right_name: str = "right",
    aliases: Optional[Mapping[str, str]] = None,
) -> BenchmarkDiff:
    """List every point on which two benchmark tables disagree.

    Parameters
    ----------
    left, right : list of Benchmark, or ``{metric: {range, weight}}`` dict
        The two tables to compare.
    left_name, right_name : str
        Labels used in the rendered table, so a reader can tell which
        column came from where.
    aliases : mapping, optional
        ``{left_metric_name: right_metric_name}`` for metrics that mean
        the same thing under different spellings. Applied to the left
        table's names before matching, and recorded on the result so
        the rendered table shows which pairings were assumed rather
        than observed.

    Returns
    -------
    BenchmarkDiff
    """
    left_specs = normalize_table(left)
    right_specs = normalize_table(right)
    alias_map = dict(aliases or {})

    applied: Dict[str, str] = {}
    renamed_left: Dict[str, BenchmarkSpec] = {}
    renamed_left_source: Dict[str, str] = {}
    for metric, spec in left_specs.items():
        target = alias_map.get(metric, metric)
        if target != metric and target in right_specs:
            applied[metric] = target
        if target in renamed_left:
            prior_metric = renamed_left_source[target]
            if prior_metric == target:
                reason = (
                    f"{metric!r} aliases to {target!r}, which is already "
                    f"a metric name in {left_name} in its own right"
                )
            elif metric == target:
                reason = (
                    f"{metric!r} is a metric name in {left_name} in its "
                    f"own right, but {prior_metric!r} already aliases to "
                    f"that same name"
                )
            else:
                reason = (
                    f"both {prior_metric!r} and {metric!r} alias to the "
                    f"same target {target!r}"
                )
            raise ValueError(
                f"alias collision in {left_name}: {reason}. Silently "
                f"keeping only the last one would drop one metric's "
                f"benchmark entirely from the diff — fix the alias map "
                f"(or the source table) so each left metric maps to a "
                f"distinct name."
            )
        renamed_left[target] = spec
        renamed_left_source[target] = metric

    diff = BenchmarkDiff(
        left_name=left_name, right_name=right_name, aliases_applied=applied,
    )

    for metric in sorted(set(renamed_left) | set(right_specs)):
        left_spec = renamed_left.get(metric)
        right_spec = right_specs.get(metric)
        alias_note = ""
        for original, target in applied.items():
            if target == metric:
                alias_note = f"matched via alias {original} -> {target}"

        if left_spec is None:
            diff.disagreements.append(BenchmarkDisagreement(
                metric=metric, kind="only_in_right",
                left=None, right=right_spec,
                note=f"not defined in {left_name}; check for a name mismatch",
            ))
            continue
        if right_spec is None:
            diff.disagreements.append(BenchmarkDisagreement(
                metric=metric, kind="only_in_left",
                left=left_spec, right=None,
                note=f"not defined in {right_name}; check for a name mismatch",
            ))
            continue

        if left_spec.as_range != right_spec.as_range:
            diff.disagreements.append(BenchmarkDisagreement(
                metric=metric, kind="range",
                left=left_spec, right=right_spec, note=alias_note,
            ))
        elif left_spec.weight != right_spec.weight:
            diff.disagreements.append(BenchmarkDisagreement(
                metric=metric, kind="weight",
                left=left_spec, right=right_spec, note=alias_note,
            ))
        else:
            diff.agreements.append(metric)

    return diff


# ---------------------------------------------------------------------------
# CLI: render the disagreement table for two tables named on the command line
# ---------------------------------------------------------------------------

def _load_table(spec: str) -> BenchmarkTable:
    """Import ``module.path:attr`` and return the attribute — a benchmark
    table, in either shape :func:`normalize_table` accepts.

    Deliberately does not ship a default pair of tables: this module is
    domain-agnostic (see the module docstring), so it has no opinion
    about which two tables a caller wants compared. Point it at
    whichever module-level names hold your tables, e.g.
    ``examples.my_domain.benchmarks:TABLE_A``.
    """
    if ":" not in spec:
        raise ValueError(f"expected 'module.path:attr', got {spec!r} (missing ':')")
    module_path, attr = spec.split(":", 1)
    import importlib

    module = importlib.import_module(module_path)
    if not hasattr(module, attr):
        raise AttributeError(f"{module_path!r} has no attribute {attr!r}")
    return getattr(module, attr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--left", required=True,
        help="'module.path:attr' pointing at a benchmark table (a list of "
             "Benchmark objects, or a {metric: {range, weight}} dict).",
    )
    parser.add_argument("--right", required=True, help="Same shape as --left.")
    parser.add_argument("--left-name", default="left", help="Label for --left in the rendered table.")
    parser.add_argument("--right-name", default="right", help="Label for --right in the rendered table.")
    parser.add_argument(
        "--aliases", default=None,
        help="Optional {left_metric: right_metric} mapping for metrics that "
             "mean the same thing under different spellings — a path to a "
             "JSON file, or an inline JSON string.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        left = _load_table(args.left)
        right = _load_table(args.right)
    except (ValueError, ImportError, AttributeError) as exc:
        print(f"ERROR: could not load a table: {exc}", file=sys.stderr)
        return 2

    aliases: Optional[Dict[str, str]] = None
    if args.aliases:
        path = Path(args.aliases)
        raw = path.read_text(encoding="utf-8") if path.exists() else args.aliases
        try:
            aliases = json.loads(raw)
        except json.JSONDecodeError as exc:
            print(f"ERROR: could not parse --aliases: {exc}", file=sys.stderr)
            return 2

    try:
        diff = diff_benchmark_tables(
            left=left, right=right,
            left_name=args.left_name, right_name=args.right_name,
            aliases=aliases,
        )
    except ValueError as exc:
        # Includes the duplicate-metric-name and alias-collision refusals
        # in normalize_table / diff_benchmark_tables above — surfaced as
        # a normal CLI error, not a traceback.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(diff.to_markdown())
    print(
        f"\n{len(diff.disagreements)} disagreement(s), "
        f"{len(diff.agreements)} agreement(s)"
        + (f", {len(diff.aliases_applied)} alias(es) applied" if diff.aliases_applied else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
