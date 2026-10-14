"""Read-only contamination check for ``prompt_information: simple`` runs.

The checker reads the exact decision prompts saved in the raw irrigation trace
and the exact reflection prompts saved by the irrigation domain hook.  Legacy
reflection logs are also read: although they do not preserve the complete
reflection prompt, their ``reflection_input`` fields preserve model-readable
memory lines and are therefore still useful evidence.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import json
from pathlib import Path
import re
from typing import Any, Iterable, Iterator, Mapping, Pattern, Sequence


def _rx(*patterns: str) -> tuple[Pattern[str], ...]:
    return tuple(re.compile(pattern, re.IGNORECASE | re.DOTALL) for pattern in patterns)


# This is the single canonical inventory used by both the scanner and its
# tests.  Patterns identify the pre-registered removed sentence families; they
# deliberately avoid generic phrases such as "water right", "minimum-use
# floor", and "governance rule" because those remain in option/rejection text.
REMOVED_SENTENCE_FAMILIES: dict[str, tuple[Pattern[str], ...]] = {
    "k6_senior_tier_text": _rx(
        r"A shortage tier is set from Lake Mead's level on 1 January, before anyone's request",
    ),
    "supply_headline": _rx(
        r"Water supply is (?:sufficient for your full request|short of your request) this year\.",
    ),
    "keep_request_expectation": _rx(
        r"If you request the [\d,]+ acre-ft you received last year, you can expect\b",
    ),
    "increase_request_expectation": _rx(
        r"If you increase your request to about [\d,]+ acre-ft, you can expect\b",
    ),
    "lower_basin_tier_details": _rx(
        r"\(Lake Mead was below [\d,]+ feet on 1 January\):\s+it reduces\b",
        r"This tier limits your junior-priority water this year\b",
        r"A request at or below your [\d,]+ acre-ft tier ceiling is not reduced by the tier\b",
        r"Priority-5/6 water is not available in a tier year\b",
        r"priority-5/6 entitlement is included in the tier ceiling\b",
        r"(?:Your delivery|The delivery available under that ceiling) is reduced only if Lake Mead\b",
    ),
    "shortfall_reason": _rx(
        r"Last year you requested [^\n]+?\([\d.]+% delivered\), because\b",
        r"Shortfall: [\d,]+ acre-ft \([\d.]+% unmet\), because\b",
    ),
    "upper_basin_natural_flow": _rx(
        r"The natural flow of the rivers your sub-basin draws on (?:is|was) [\d.]+% of its 1971-2018 average",
        r"Natural flow on the river this year is forecast at [\d,.]+ million acre-ft\.",
    ),
    "water_right_delivery_share": _rx(
        r"Your water right is [\d,]+ acre-ft/year; last year's delivery was [\d.]+% of it\.",
    ),
    "land_need": _rx(
        r"Your fields can use about [\d,]+ acre-ft of water a year:",
    ),
    "field_use_clause": _rx(
        r"The more water you receive, up to what your fields can use, the more you can produce\.",
    ),
    "feedback_dashboard": _rx(
        r"PERFORMANCE HISTORY",
        r"Year\s*\|\s*request \(AF\)\s*\|\s*received \(AF\)",
        r"(?:^|\n)TREND:\s",
        r"WARNING:\s*You requested [\d,]+ AF and received [\d,]+ AF\s*"
        r"\([\d.]+% unmet\)\.\s*The reason is stated in your water situation above\.",
    ),
    "appraisal_guidance": _rx(
        r"First, assess your WATER SUPPLY situation by considering:",
        r"Next, assess your ADAPTIVE CAPACITY by considering:",
        r"- (?:Water Supply Outlook|Demand-Supply Balance|Capacity to Adjust|Cost of Change|Benefit of Keeping):",
    ),
    "keep_asks_received_note": _rx(
        r"If you received less than you requested last year, keeping your request asks only for the amount you received",
    ),
    "floor_no_decrease_note": _rx(
        r"A decrease is not offered because your request is at or below the minimum-use floor of [\d,]+ acre-ft",
    ),
    "allocation_rules": _rx(
        r"Rules that apply to [^:\n]+:",
        r"In a year with a declared shortage tier, your junior-priority water is limited to a fixed share of your entitlement\.",
        r"A declared shortage does not by itself reduce your delivery; only Lake Mead's physical availability does\.",
    ),
    "sharing_sentence": _rx(
        r"When water is (?:physically )?short,? it is shared in proportion to requests",
        r"When water is short, a larger request would not add water\.",
    ),
}


@dataclass(frozen=True)
class Occurrence:
    run: str
    agent: str
    year: Any
    family: str
    source: str


@dataclass(frozen=True)
class CheckResult:
    run: str
    occurrences: tuple[Occurrence, ...]
    readable_prompts: int
    retry_feedback_occurrences: tuple[Occurrence, ...] = ()
    lesson_occurrences: tuple[Occurrence, ...] = ()
    malformed_records: int = 0
    missing_raw_input: bool = False
    missing_reflection_recorder: bool = False
    reflection_prompt_log_complete: bool = True
    retry_suffix_mismatches: int = 0

    @property
    def complete(self) -> bool:
        return not (
            self.malformed_records
            or self.missing_raw_input
            or self.missing_reflection_recorder
            or not self.reflection_prompt_log_complete
        )


def _family_spans(text: str, patterns: Iterable[Pattern[str]]) -> tuple[tuple[int, int], ...]:
    """Return distinct matches, collapsing overlapping aliases of one family."""
    candidates = sorted(
        (match.start(), match.end())
        for pattern in patterns
        for match in pattern.finditer(text)
    )
    distinct: list[tuple[int, int]] = []
    for start, end in candidates:
        if any(start < prior_end and prior_start < end
               for prior_start, prior_end in distinct):
            continue
        distinct.append((start, end))
    return tuple(distinct)


def scan_text(text: str) -> tuple[str, ...]:
    """Return removed family names found in one model-readable text."""
    if not isinstance(text, str) or not text.strip():
        return ()
    return tuple(
        family
        for family, patterns in REMOVED_SENTENCE_FAMILIES.items()
        if _family_spans(text, patterns)
    )


def _flatten_text(value: Any) -> Iterator[str]:
    """Yield prompt text from a string, list, or message-like mapping."""
    if isinstance(value, str):
        if value.strip():
            yield value
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        for item in value:
            yield from _flatten_text(item)
        return
    if isinstance(value, Mapping):
        for key in ("content", "text", "prompt"):
            if key in value:
                yield from _flatten_text(value[key])
                return


def _records(path: Path) -> tuple[list[tuple[int, Mapping[str, Any]]], int]:
    records: list[tuple[int, Mapping[str, Any]]] = []
    malformed = 0
    try:
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, 1):
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, TypeError):
                    malformed += 1
                    continue
                if isinstance(row, Mapping):
                    records.append((line_number, row))
                else:
                    malformed += 1
    except (OSError, UnicodeError):
        if path.exists():
            malformed += 1
    return records, malformed


def _identity(row: Mapping[str, Any], fallback_run: str) -> tuple[str, str, Any]:
    run = str(row.get("run_id") or row.get("run") or fallback_run)
    agent = str(row.get("agent_id") or row.get("agent") or "unknown")
    year = next(
        (row[key] for key in ("year", "period", "year_created", "step_id")
         if row.get(key) is not None),
        "unknown",
    )
    return run, agent, year


def _append_hits(
    target: list[Occurrence], text: str, identity: tuple[str, str, Any], source: str
) -> None:
    run, agent, year = identity
    for family, patterns in REMOVED_SENTENCE_FAMILIES.items():
        target.extend(
            Occurrence(run, agent, year, family, f"{source}:char-{start}")
            for start, _end in _family_spans(text, patterns)
        )


def _split_stored_reflection(text: str) -> tuple[str, str | None]:
    if " Lesson: " not in text:
        return text, None
    program, lesson = text.split(" Lesson: ", 1)
    return program, lesson


def _scan_model_text(
    text: str,
    identity: tuple[str, str, Any],
    source: str,
    occurrences: list[Occurrence],
    lessons: list[Occurrence],
) -> None:
    """Gate program text while reporting inline stored lessons separately."""
    for line_number, line in enumerate(text.splitlines() or [text], 1):
        program, lesson = _split_stored_reflection(line)
        line_source = f"{source}:line-{line_number}"
        _append_hits(occurrences, program, identity, line_source)
        if lesson is not None:
            _append_hits(lessons, lesson, identity, line_source + ":lesson")


def _audit_retry_feedback(path: Path, fallback_run: str) -> tuple[list[Occurrence], int]:
    hits: list[Occurrence] = []
    malformed = 0
    if not path.exists():
        return hits, malformed
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            if not reader.fieldnames or "error_messages" not in reader.fieldnames:
                return hits, 1
            for line_number, row in enumerate(reader, 2):
                text = row.get("error_messages", "")
                if text:
                    _append_hits(
                        hits, text,
                        (fallback_run, str(row.get("agent_id") or "unknown"),
                         row.get("year") or row.get("step_id") or "unknown"),
                        f"{path.name}:{line_number}:error_messages",
                    )
    except (csv.Error, OSError, UnicodeError):
        malformed += 1
    return hits, malformed


def check_run(run_dir: str | Path) -> CheckResult:
    """Scan every prompt record available below ``run_dir`` without writing."""
    directory = Path(run_dir)
    fallback_run = directory.name or str(directory)
    occurrences: list[Occurrence] = []
    retry_feedback: list[Occurrence] = []
    lesson_occurrences: list[Occurrence] = []
    readable_prompts = 0
    malformed = 0
    raw_inputs = 0
    retry_suffix_mismatches = 0

    raw_relative = Path("raw") / "irrigation_farmer_traces.jsonl"
    raw_rows, bad = _records(directory / raw_relative)
    malformed += bad
    for line_number, row in raw_rows:
        identity = _identity(row, fallback_run)
        inputs = list(_flatten_text(row.get("input")))
        if inputs:
            raw_inputs += 1
            readable_prompts += 1
            prompt = inputs[0]
            _scan_model_text(
                prompt, identity, f"{raw_relative.as_posix()}:{line_number}:input",
                occurrences, lesson_occurrences,
            )
        else:
            prompt = ""
        for index, memory in enumerate(_flatten_text(row.get("memory_pre"))):
            readable_prompts += 1
            source = f"{raw_relative.as_posix()}:{line_number}:memory_pre[{index}]"
            _scan_model_text(memory, identity, source, occurrences, lesson_occurrences)
        for index, retry in enumerate(_flatten_text(row.get("retry_prompts"))):
            source = f"{raw_relative.as_posix()}:{line_number}:retry_prompts[{index}]"
            if prompt and retry.endswith(prompt):
                _append_hits(retry_feedback, retry[:-len(prompt)], identity, source + ":prefix")
            else:
                retry_suffix_mismatches += 1
                _append_hits(occurrences, retry, identity, source + ":suffix-mismatch")

    memory_path = directory / 'simulation_log.csv'
    if memory_path.exists():
        try:
            with memory_path.open('r', encoding='utf-8', newline='') as stream:
                reader = csv.DictReader(stream, strict=True)
                for line_number, row in enumerate(reader, 2):
                    for index, memory in enumerate((row.get('memory') or '').split(' | ')):
                        if memory.strip():
                            readable_prompts += 1
                            _scan_model_text(
                                memory, _identity(row, fallback_run),
                                f'simulation_log.csv:{line_number}:memory[{index}]',
                                occurrences, lesson_occurrences,
                            )
        except (csv.Error, OSError, UnicodeError):
            malformed += 1

    reflection_log_exists = any(
        (directory / name).exists()
        for name in ("reflection_checks.jsonl", "reflection_log.jsonl")
    )
    for reflection_input_name in ("reflection_checks.jsonl", "reflection_log.jsonl"):
        reflection_input_source, bad = _records(directory / reflection_input_name)
        malformed += bad
        for line_number, row in reflection_input_source:
            identity = _identity(row, fallback_run)
            for index, text in enumerate(_flatten_text(row.get("reflection_input"))):
                readable_prompts += 1
                _scan_model_text(
                    text, identity,
                    f"{reflection_input_name}:{line_number}:reflection_input[{index}]",
                    occurrences, lesson_occurrences,
                )
            if reflection_input_name == "reflection_log.jsonl":
                for index, summary in enumerate(_flatten_text(row.get("summary"))):
                    readable_prompts += 1
                    source = f"{reflection_input_name}:{line_number}:summary[{index}]"
                    if " Lesson: " in summary:
                        _scan_model_text(
                            summary, identity, source, occurrences, lesson_occurrences
                        )
                    else:
                        _append_hits(lesson_occurrences, summary, identity, source + ":lesson")

    prompts_path = directory / "reflection_prompts.jsonl"
    prompt_rows, bad = _records(prompts_path)
    malformed += bad
    recorded_reflection_prompts = 0
    for line_number, row in prompt_rows:
        identity = _identity(row, fallback_run)
        prompts = list(_flatten_text(row.get("prompt")))
        if not prompts:
            continue
        recorded_reflection_prompts += 1
        readable_prompts += 1
        prompt = prompts[0]
        source = f"{prompts_path.name}:{line_number}:prompt"
        _scan_model_text(
            prompt, identity, source, occurrences, lesson_occurrences
        )

    audit_hits, bad = _audit_retry_feedback(
        directory / "irrigation_farmer_governance_audit.csv", fallback_run
    )
    retry_feedback.extend(audit_hits)
    malformed += bad

    manifest_complete = True
    manifest_path = directory / "reproducibility_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, Mapping):
                malformed += 1
            else:
                manifest_complete = manifest.get("reflection_prompt_log_complete", True) is not False
        except (json.JSONDecodeError, OSError, UnicodeError):
            malformed += 1

    return CheckResult(
        fallback_run, tuple(occurrences), readable_prompts,
        tuple(retry_feedback), tuple(lesson_occurrences), malformed,
        missing_raw_input=raw_inputs == 0,
        missing_reflection_recorder=reflection_log_exists and recorded_reflection_prompts == 0,
        reflection_prompt_log_complete=manifest_complete,
        retry_suffix_mismatches=retry_suffix_mismatches,
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Find full-information sentence families in a finished simple irrigation run."
    )
    parser.add_argument("run_dir", type=Path, help="finished irrigation run directory")
    args = parser.parse_args(argv)
    result = check_run(args.run_dir)

    if result.retry_feedback_occurrences:
        print(f"{result.run}: retry feedback (unchanged by design): "
              f"{len(result.retry_feedback_occurrences)} occurrence(s)")
        for family, count in sorted(Counter(hit.family for hit in result.retry_feedback_occurrences).items()):
            print(f"retry feedback (unchanged by design)\t{family}\t{count}")
    if result.lesson_occurrences:
        print(f"{result.run}: model-written lessons: "
              f"{len(result.lesson_occurrences)} occurrence(s)")
        for family, count in sorted(Counter(hit.family for hit in result.lesson_occurrences).items()):
            print(f"model-written lessons\t{family}\t{count}")
    if not result.complete:
        print(
            f"{result.run}: incomplete evidence (missing raw input: {result.missing_raw_input}; "
            f"missing reflection recorder: {result.missing_reflection_recorder}; "
            f"recorder flag complete: {result.reflection_prompt_log_complete}; "
            f"malformed records skipped: {result.malformed_records})"
        )
        return 2
    for hit in result.occurrences:
        print(f"{hit.run}\t{hit.agent}\t{hit.year}\t{hit.family}\t{hit.source}")
    if result.occurrences or result.retry_suffix_mismatches:
        print(
            f"{result.run}: {len(result.occurrences)} removed-sentence occurrence(s), "
            f"{result.retry_suffix_mismatches} retry suffix mismatch(es) "
            f"in {result.readable_prompts} readable prompt(s)"
        )
        return 1
    print(f"{result.run}: clean ({result.readable_prompts} readable prompt(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
