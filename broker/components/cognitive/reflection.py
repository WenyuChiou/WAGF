"""
Reflection Engine - Cognitive consolidation for long-term memory resilience.

Implements "Year-End Reflection" to combat memory erosion (the Goldfish Effect).
Inspired by Park et al. (2023) Generative Agents reflection architecture.

Domain-agnostic via the ``DomainReflectionAdapter`` pattern and the
``DomainPack`` reflection hooks:
- Attach a domain adapter (FloodAdapter, IrrigationAdapter, etc.) or
  register a DomainPack to supply importance scoring, status/trait text,
  and reflection questions.
- With neither, the engine is domain-neutral: prompts carry only the
  generic identity line and importance is the base score (the legacy
  flood-domain fallbacks were removed in Phase 6H Items 4 and 9).
- New domains define reflection questions in ``agent_types.yaml`` or via
  ``DomainPack.reflection_questions()``.
"""
from typing import Dict, Any, List, Optional, Callable, Mapping, Sequence, Union, TYPE_CHECKING
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
import json
import re

from broker.utils.logging import setup_logger
from .adapters import DomainReflectionAdapter

logger = setup_logger(__name__)


def _memory_text(m: Any) -> str:
    """Coerce a memory item (dict from humancentric engine, or legacy str) to text."""
    if isinstance(m, dict):
        return str(m.get("content", ""))
    return str(m)


# ---------------------------------------------------------------------------
# Grounded reflection (case-study spec item 45 (a)-(e), 2026-10-07; both
# example domains opt in through their YAML). Every piece below is opt-in: the
# four ``reflection`` keys read by
# ``AgentTypeConfig.get_reflection_grounding`` all default to false, the new
# keyword arguments of ``ReflectionEngine.generate_batch_reflection_prompt``
# default to the shipped prompt, and a domain that calls none of the helpers
# renders, stores and logs exactly what it did before.
#
# Timing contract (45a, ``reflection.year_outcome``): a domain hook that sets
# this key promises that the reflection written at the end of a period sees
# that period's own settled outcome. ``add_year_outcome`` is the enforcement
# point: it raises when the key is on and the hook supplies no outcome item.
# ---------------------------------------------------------------------------

#: The ``reflection`` YAML keys of the grounded mechanism, in the order the
#: spec lists them. Each is a YAML bool, default false.
GROUNDING_KEYS = ("year_outcome", "year_lines", "program_facts", "lesson_no_numbers")

#: Heading of the program-written record in a reflection prompt (45c).
RECORD_HEADING = (
    "### Record (written by the simulation and stored with your lesson; "
    "do not restate it)"
)

#: The last line of a reflection prompt that carries a program-written
#: record (45c): the model writes the lesson only, with no year or number.
LESSON_ONLY_INSTRUCTION = (
    "In the JSON value, write only the lesson: one or two sentences in the first person. "
    "Do not write any year, amount, percentage or other number; the record "
    "above is stored with your lesson."
)

#: Shown once, after the original prompt, when a lesson failed a check (45e).
REFLECTION_RETRY_NOTE = (
    "### Correction\n"
    "Your previous answer could not be stored because {reasons}. "
    "Answer again, following every instruction above."
)

# A four-digit calendar year (1800-2199) not inside a longer number.
_CALENDAR_YEAR = re.compile(r"(?<![\d.,])(?:1[89]|2[01])\d{2}(?![\d.,]*\d)")
# Any number written with digits, with its separators ("1,000", "17.5").
_ANY_NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


@dataclass(frozen=True)
class LessonProblem:
    """A blocking problem or report-only semantic flag (45e).

    ``code`` is a short tag, counted per year in the run log and the
    manifest; ``message`` is a plain clause shown to the model in the one
    retry ("it names a year (2031)")."""
    code: str
    message: str


def _strip_lesson_preamble(text: str) -> str:
    """Remove short, recognizable leading filler, preserving lesson prose.

    A label is stripped only at the start or after a reflection/answer
    preamble of at most six words. A sentence such as "One lesson: cut
    early." is substantive text, even though it contains a lesson label.
    "Here is ...:" openers have the same six-word bound. Short leading
    "My lesson:", "The lesson:", "Key lesson:" and "Lesson learned:"
    labels are also removed.
    """
    while True:
        original = text
        text = re.sub(r"^Sure\b[!.,:]\s*", "", text, count=1, flags=re.I)
        opener = re.match(r"^(Here is\b[^.!?:]*):\s*", text, flags=re.I)
        if opener and len(opener.group(1).split()) <= 6:
            text = text[opener.end():]
        text = re.sub(
            r"^(?:(?:My|The|Key)\s+lesson|Lesson\s+learned):\s*",
            "", text, count=1, flags=re.I,
        )
        label = re.match(r"^([^.!?]*?)\blesson:\s*", text, flags=re.I)
        if label:
            prefix = label.group(1).strip()
            filler = re.match(r"^(?:my|your|the)\s+(?:reflection|response|answer)\b", prefix, flags=re.I)
            if not prefix or (filler and len(prefix.split()) <= 6):
                text = text[label.end():]
        if text == original:
            break
    return text.strip()


_LESSON_STRIP_CHARS = " \t\n\"'“”‘’,"


def normalize_lesson_text(text: str) -> str:
    """One clean line: internal whitespace collapsed, quotes, whitespace and
    commas stripped from both ends (a JSON-residue copy such as '"...",'
    reads as its text). The default ``normalize`` of
    ``run_checked_reflection``."""
    return " ".join((text or "").split()).strip(_LESSON_STRIP_CHARS)


def lesson_number_problems(lesson: str) -> List[LessonProblem]:
    """The generic safety-net check behind ``reflection.lesson_no_numbers``.

    A lesson may contain no calendar year and no other number written with
    digits, because the program writes every year and amount of a grounded
    reflection itself (45c). Numbers spelled out in words are not checked.
    Domain-neutral: it knows nothing about what the numbers measure."""
    text = lesson or ""
    problems: List[LessonProblem] = []
    years = list(dict.fromkeys(_CALENDAR_YEAR.findall(text)))
    if years:
        problems.append(LessonProblem("year", f"it names a year ({', '.join(years)})"))
    others = [n for n in dict.fromkeys(_ANY_NUMBER.findall(text)) if n not in years]
    if others:
        problems.append(LessonProblem("number", f"it contains a number ({', '.join(others)})"))
    return problems


def add_year_outcome(items: Sequence[Any], outcome_item: Any, *, required: bool) -> List[Any]:
    """Reflection input with the settled outcome of the period just ended (45a).

    ``items`` are the retrieved memories; ``outcome_item`` the domain's
    line for the period just ended (a memory dict or a string). It is
    appended unless the same text is already among ``items`` (a domain that
    writes that line to memory before reflecting). ``required`` is
    ``reflection.year_outcome``: when True, a missing ``outcome_item``
    raises instead of letting a reflection be written without the outcome
    of the period it reflects on."""
    if outcome_item is None:
        if required:
            raise ValueError(
                "reflection.year_outcome is on, but the domain supplied no outcome "
                "for the period just ended; the reflection would be written without it."
            )
        return list(items)
    present = {_memory_text(m).strip() for m in items}
    if _memory_text(outcome_item).strip() in present:
        return list(items)
    return list(items) + [outcome_item]


def order_by_year(items: Sequence[Any]) -> List[Any]:
    """``items`` sorted by their ``"year"`` key, oldest first, ties kept in
    the given order (45b). Every item must be a dict with a numeric
    ``"year"``: the domain states the period each line is about (the
    memory engine's payload does not carry it), and a missing one raises
    rather than being placed by guess."""
    for m in items:
        year = m.get("year") if isinstance(m, dict) else None
        if isinstance(year, bool) or not isinstance(year, (int, float)):
            raise ValueError(
                "reflection.year_lines needs a numeric 'year' on every reflection "
                f"input item; got {m!r}."
            )
    return sorted(items, key=lambda m: m["year"])


def compose_lesson_with_facts(fact_lines: Optional[Sequence[str]], lesson: str) -> str:
    """The text of a grounded reflection (45c): the program-written fact
    lines, then "Lesson: " and the model's lesson. Without fact lines it is
    the lesson alone, as before."""
    facts = [str(f).strip() for f in (fact_lines or []) if str(f).strip()]
    if not facts:
        return lesson
    return " ".join(facts) + " Lesson: " + lesson


def _per_agent_lines(value: Any, agent_id: str, n_agents: int, name: str) -> List[str]:
    """Resolve a per-agent line option: None, a sequence of lines (a
    one-agent batch only) or a mapping from agent id to lines."""
    if value is None:
        return []
    if isinstance(value, Mapping):
        return [str(v) for v in (value.get(agent_id) or [])]
    if isinstance(value, (list, tuple)):
        if n_agents != 1:
            raise ValueError(
                f"generate_batch_reflection_prompt: {name} given as a list is only "
                f"defined for a one-agent batch; this batch has {n_agents} agents. "
                "Pass a mapping from agent id to lines instead."
            )
        return [str(v) for v in value]
    raise TypeError(f"generate_batch_reflection_prompt: {name} must be a list or a mapping, got {type(value).__name__}.")


@dataclass
class CheckedReflection:
    """The result of one checked reflection call (45e).

    ``outcome`` is one of ``ReflectionCheckTally.OUTCOMES``: "stored" (the
    first lesson passed), "stored_after_retry" (it failed, the one retry
    passed), or "dropped" (the allowed attempts failed, or the checker raised).
    Junk and unreadable replies are drop reasons, not outcomes. ``insight`` and
    ``lesson`` are set only for the two stored outcomes; ``last_insight``
    is the last reply that parsed at all (stored or not), for the domain's
    reflection log."""
    outcome: str
    insight: Optional["ReflectionInsight"] = None
    last_insight: Optional["ReflectionInsight"] = None
    lesson: str = ""
    first_problems: List[LessonProblem] = field(default_factory=list)
    final_problems: List[LessonProblem] = field(default_factory=list)
    flags: List[LessonProblem] = field(default_factory=list)
    calls: int = 0
    error: str = ""


class ReflectionCheckTally:
    """Per-period counts of checked reflections (45e), for the run log and
    the manifest. "retried" counts the lessons that needed the one retry,
    whether it passed or not; problem codes are counted on first attempts,
    one per code per reflection."""

    OUTCOMES = ("stored", "stored_after_retry", "dropped")

    def __init__(self) -> None:
        self._counts: Dict[Any, Counter] = {}
        self._problems: Dict[Any, Counter] = {}
        self._retried: Counter = Counter()
        self._dropped_problems: Counter = Counter()
        self._flags: Dict[Any, Counter] = {}

    def add(self, period: Any, result: CheckedReflection) -> None:
        if result.outcome not in self.OUTCOMES:
            raise ValueError(f"ReflectionCheckTally: unknown outcome {result.outcome!r}.")
        counts = self._counts.setdefault(period, Counter())
        counts[result.outcome] += 1
        if result.calls > 1 or (result.calls == 0 and result.outcome in ("stored_after_retry", "dropped")):
            self._retried[period] += 1
        if result.outcome == "dropped":
            self._dropped_problems.update(dict.fromkeys(p.code for p in result.final_problems).keys())
        problems = self._problems.setdefault(period, Counter())
        for code in dict.fromkeys(p.code for p in result.first_problems):
            problems[code] += 1
        if result.insight is not None:
            if getattr(result.insight, "parse", "strict") in ("lenient", "plain_text"):
                counts["recovered_lenient"] += 1
            flags = self._flags.setdefault(period, Counter())
            flags.update(dict.fromkeys(p.code for p in result.flags).keys())

    def counts(self, period: Any) -> Dict[str, int]:
        c = self._counts.get(period, Counter())
        out = {k: int(c.get(k, 0)) for k in self.OUTCOMES}
        out["stored_total"] = out["stored"] + out["stored_after_retry"]
        out["retried"] = int(self._retried.get(period, 0))
        out["recovered_lenient"] = int(c.get("recovered_lenient", 0))
        return out

    def log_line(self, period: Any) -> str:
        c = self.counts(period)
        return (f"stored {c['stored_total']} ({c['stored_after_retry']} after one retry), "
                f"retried {c['retried']}, dropped {c['dropped']}, "
                f"recovered lenient {c['recovered_lenient']}, "
                f"flagged by reason {dict(sorted(self._flags.get(period, {}).items()))}")

    def summary(self) -> Dict[str, Any]:
        periods = sorted(self._counts, key=lambda p: (str(type(p)), p))
        per_period = {str(p): {**self.counts(p),
                               "first_attempt_problems": dict(sorted(self._problems.get(p, {}).items())),
                               "flagged_by_reason": dict(sorted(self._flags.get(p, {}).items()))}
                      for p in periods}
        totals = Counter()
        problems = Counter()
        flags = Counter()
        for p in periods:
            totals.update(self.counts(p))
            problems.update(self._problems.get(p, {}))
            flags.update(self._flags.get(p, {}))
        return {"per_period": per_period, "totals": dict(totals),
                "first_attempt_problems": dict(sorted(problems.items())),
                "dropped_by_reason": dict(sorted(self._dropped_problems.items())),
                "flagged_by_reason": dict(sorted(flags.items()))}


def _reply_text(raw: Any) -> str:
    return raw[0] if isinstance(raw, tuple) else raw


def _dedup_problems(problems: Sequence[LessonProblem]) -> List[LessonProblem]:
    seen = set()
    out = []
    for p in problems:
        if p.code not in seen:
            seen.add(p.code)
            out.append(p)
    return out


def run_checked_reflection(
    engine: "ReflectionEngine",
    *,
    prompt: str,
    agent_id: str,
    period: Any,
    llm_call: Callable[[str], Any],
    normalize: Optional[Callable[[str], str]] = None,
    checker: Optional[Callable[[str], Sequence[LessonProblem]]] = None,
    lesson_no_numbers: bool = False,
    retries: int = 1,
    log_path: Optional[Union[str, Path]] = None,
    year_created: Any = None,
    reflection_input: Optional[Sequence[Any]] = None,
) -> CheckedReflection:
    """Check one full lesson before storage, with one retry by default.

    Numbers (when enabled), junk (no letters or fewer than three words),
    lessons over 500 characters, and foreign figures block storage. Domain
    semantic reasons are report-only flags, measured on every stored lesson;
    they never cause a retry or drop. Preambles are removed before checks.
    Checker and normalization errors are logged as ``checker_error`` drops.
    Every attempt, including clean first attempts, is written to ``log_path``
    when supplied. ``year_created`` defaults to ``period``.
    """
    if retries < 0:
        raise ValueError("run_checked_reflection: retries must be 0 or more.")
    norm = normalize or normalize_lesson_text
    input_text = (
        [_memory_text(item) for item in reflection_input]
        if reflection_input is not None else None
    )
    attempts: List[Dict[str, Any]] = []

    def _problems(lesson: str):
        found: List[LessonProblem] = []
        if not any(c.isalpha() for c in lesson) or len(lesson.split()) < 3:
            found.append(LessonProblem("empty", "the answer has no letters or fewer than three words"))
        if len(lesson) > 500:
            found.append(LessonProblem("too_long", "the lesson exceeds the 500-character limit"))
        if lesson_no_numbers:
            found.extend(lesson_number_problems(lesson))
        domain = list(checker(lesson)) if checker is not None else []
        found.extend(p for p in domain if p.code == "foreign_figure")
        flags = [p for p in domain if p.code != "foreign_figure"]
        return _dedup_problems(found), _dedup_problems(flags)

    def _ask(text: str):
        raw = None
        try:
            raw = _reply_text(llm_call(text))
            insights = engine.parse_batch_reflection_response(
                raw, [agent_id], period if year_created is None else year_created,
                allow_plain_text=True)
            return raw, insights.get(agent_id), ""
        except Exception as e:
            return raw, None, f"{type(e).__name__}: {e}"

    result = CheckedReflection(outcome="dropped")
    current_prompt = prompt
    for attempt in range(retries + 1):
        raw, insight, error = _ask(current_prompt)
        result.calls += 1
        if insight is not None:
            insight.reflection_input = input_text
            result.last_insight = insight
        lesson = ""
        flags: List[LessonProblem] = []
        try:
            if insight is None:
                # Trivial unstructured replies are junk; unreadable objects
                # and failed calls use the no_reply retry path.
                junk = isinstance(raw, str) and bool(raw.strip()) and (
                    not any(c.isalpha() for c in raw) or
                    (not re.search(r"[{}\[\]]", raw) and len(raw.split()) < 3))
                problems = [LessonProblem("empty", "the answer has no letters or fewer than three words")]
                if not junk:
                    problems = [LessonProblem("no_reply", "no readable answer was found")]
            else:
                lesson = norm(_strip_lesson_preamble(norm(str(insight.summary or ""))))
                problems, flags = _problems(lesson)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
            problems = [LessonProblem("checker_error", "the lesson checker failed")]
            flags = []
            logger.error("[Reflection] checker failed for %s in period %s: %s",
                         agent_id, period, error)
        attempts.append({"attempt": attempt, "raw_reply": raw, "lesson": lesson,
                         "parse": getattr(insight, "parse", "strict"),
                         "problems": [{"code": p.code, "message": p.message} for p in problems],
                         "flags": [{"code": p.code, "message": p.message} for p in flags],
                         "error": error})
        if attempt == 0:
            result.first_problems = list(problems)
        if insight is not None and not problems:
            result.outcome = "stored" if attempt == 0 else "stored_after_retry"
            insight.summary = lesson
            result.insight = insight
            result.lesson = lesson
            result.flags = flags
            result.final_problems = []
            break
        result.final_problems = list(problems)
        result.error = error
        if any(p.code == "checker_error" for p in problems):
            result.outcome = "dropped"
            break
        if attempt < retries:
            reasons = "; ".join(p.message for p in problems)
            current_prompt = prompt + "\n\n" + REFLECTION_RETRY_NOTE.format(reasons=reasons)
        else:
            result.outcome = "dropped"

    if log_path is not None:
        try:
            path = Path(log_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                for a in attempts:
                    row = {"agent_id": agent_id, "period": period,
                           "outcome": result.outcome, **a}
                    if input_text is not None:
                        row["reflection_input"] = input_text
                    f.write(json.dumps(row,
                                       ensure_ascii=False, default=str) + "\n")
        except OSError as e:
            logger.error(f"[Reflection] could not write the check log {log_path}: {e}")
    return result


def record_reflection_checks(output_dir: Union[str, Path], tally: ReflectionCheckTally,
                             settings: Dict[str, Any]) -> None:
    """Add the checked-reflection counts (45e) to this run's
    ``reproducibility_manifest.json`` under ``reflection_checks``, after the
    runner wrote it. Additive; a missing manifest or a write error is
    printed and never fails the run (the posture of the domains' other
    provenance patches)."""
    try:
        path = Path(output_dir) / "reproducibility_manifest.json"
        if not path.exists():
            print(f"[Provenance] WARNING: no reproducibility_manifest.json in {output_dir}; "
                  "reflection check counts not recorded there.")
            return
        with open(path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["reflection_checks"] = {"settings": dict(settings), **tally.summary()}
        with open(path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        print(f"[Provenance] WARNING: could not record the reflection check counts "
              f"in reproducibility_manifest.json: {e}")


def store_reflection_memory(
    memory_engine: Any,
    agent_id: str,
    content: str,
    metadata: Dict[str, Any],
    *,
    keep_latest_only: bool = False,
) -> int:
    """Store one reflection as a memory of ``agent_id``.

    ``keep_latest_only`` is the opt-in ``reflection.keep_latest_only``
    option (default False; ``AgentTypeConfig.get_reflection_keep_latest_only``).
    When True, the agent's earlier memories of the same type
    (``metadata["type"]``) are removed first, through the engine's
    ``remove_by_type``, so memory holds only the latest reflection. When
    False this is exactly ``memory_engine.add_memory(agent_id, content,
    metadata)``. Returns how many stored items were removed (0 when off).
    """
    removed = 0
    if keep_latest_only:
        memory_type = metadata.get("type")
        if not memory_type:
            raise ValueError(
                "store_reflection_memory: keep_latest_only needs metadata['type'] "
                "to know which earlier memories the new one replaces."
            )
        removed = memory_engine.remove_by_type(agent_id, memory_type)
    memory_engine.add_memory(agent_id, content, metadata)
    return removed

if TYPE_CHECKING:
    from cognitive_governance.v1_prototype.reflection import (
        ReflectionTemplate,
        ReflectionMemoryIntegrator,
    )

@dataclass
class ReflectionInsight:
    """A consolidated semantic insight derived from multiple episodic memories."""
    summary: str                      # Concise high-level insight
    source_memory_count: int = 0      # How many memories contributed
    importance: float = 1.0           # Consolidated importance score (0-1)
    year_created: int = 0             # When this insight was generated
    domain_tags: List[str] = field(default_factory=list)  # e.g., ["event_type", "impact", "response"]
    parse: str = "strict"             # Reply parsing provenance (spec item 45n)


@dataclass
class AgentReflectionContext:
    """Agent identity context for personalized reflection prompts.

    Domain-neutral: generic identity fields plus ``custom_traits`` for
    domain-specific data. The former domain-specific context fields were
    removed in Phase 6H Item 9 — a domain routes such data through
    ``custom_traits``.

    Phase 6R-B-4 (audit cluster E item #17, 2026-05-26): ``agent_type``
    is now REQUIRED (no default). Pre-fix the field defaulted to the
    literal ``"household"`` — a flood-domain string in generic code
    that misrouted any reflection-prompt builder forgetting to supply
    an explicit agent_type. Construction raises ``ValueError`` on
    missing/empty agent_type via the ``__post_init__`` validator below.
    """
    agent_id: str
    agent_type: str                        # REQUIRED. household | government | institution | commuter | ...
    name: str = ""                         # Display name if available
    years_in_sim: int = 0                  # Agent age in simulation
    mg_status: bool = False                # Marginalized group
    recent_decision: str = ""              # Last skill chosen
    custom_traits: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        # Phase 6R-B-4: empty / None / whitespace-only agent_type is a
        # malformed-agent symptom. Surface immediately instead of
        # silently routing through a flood-domain identity in the
        # reflection prompt. ``__post_init__`` fires only at
        # construction; post-construction mutation (``ctx.agent_type =
        # ""``) is NOT re-validated — caller responsibility, matches
        # the 6R-B-1 / 6R-B-2 raise pattern.
        normalised = (self.agent_type or "").strip() if isinstance(
            self.agent_type, str
        ) else ""
        if not normalised:
            raise ValueError(
                f"AgentReflectionContext: agent_id={self.agent_id!r} has "
                f"empty/missing agent_type (whitespace-only also rejected). "
                f"Every reflection-prompt consumer MUST declare "
                f"agent_type explicitly. Previously this defaulted to "
                f"the literal 'household' string — a flood-domain leak "
                f"in generic code. (Phase 6R-B-4, audit cluster E #17.)"
            )


# Generic last-resort reflection questions -- deliberately domain-neutral
# (no flood / water / insurance wording). Used ONLY when neither the
# agent_types.yaml ``reflection.questions`` block (per-agent-type or
# domain-wide) nor a DomainPack.reflection_questions() supplies any.
# Domain authors define their own questions in agent_types.yaml; the
# resolution order is implemented in
# ``AgentTypeConfig.get_reflection_questions(agent_type)``.
_DEFAULT_REFLECTION_QUESTIONS: List[str] = [
    "What worked well in your decisions this period, and what did not?",
    "Did your actions match the conditions you observed?",
    "What pattern do you notice across recent events, and what would "
    "you do differently?",
]

class ReflectionTrigger(Enum):
    """Types of events that can trigger reflection."""
    CRISIS = "crisis"
    PERIODIC = "periodic"
    DECISION = "decision"
    INSTITUTIONAL = "institutional"


@dataclass
class ReflectionTriggerConfig:
    """Configuration for reflection triggers."""
    crisis: bool = True
    periodic_interval: int = 5
    decision_types: List[str] = field(default_factory=list)
    institutional_threshold: float = 0.05
    method: str = "hybrid"
    batch_size: int = 10
    importance_boost: float = 0.85


class ReflectionEngine:
    """
    Triggers periodic cognitive consolidation for agents.
    
    At defined intervals (e.g., end of year), prompts the LLM to synthesize
    past episodic memories into high-level "Lessons Learned". These insights
    are then stored with raised importance scores to ensure long-term retention.
    """
    
    def __init__(
        self,
        reflection_interval: int = 1,      # Trigger reflection every N years/epochs
        max_insights_per_reflection: int = 2,  # How many insights to generate per cycle
        insight_importance_boost: float = 0.9,  # Importance score for new insights
        output_path: Optional[str] = None,       # Path to save reflection logs
        llm_client=None,
        template: Optional["ReflectionTemplate"] = None,
        integrator: Optional["ReflectionMemoryIntegrator"] = None,
        adapter: Optional[DomainReflectionAdapter] = None,
    ):
        self.reflection_interval = reflection_interval
        self.max_insights = max_insights_per_reflection
        self.importance_boost = insight_importance_boost
        self.reflection_history: Dict[str, List[ReflectionInsight]] = {}
        self.output_path = output_path
        self.llm_client = llm_client
        self.template = template
        self.integrator = integrator
        self.adapter = adapter
        
        # Initialize log file if path provided
        if self.output_path:
            p = Path(self.output_path)
            p.parent.mkdir(parents=True, exist_ok=True)
            # Write header if file doesn't exist (for CSV) or just append (for JSONL)
            # We'll use JSONL for flexibility
            if not p.exists():
                with open(p, 'w', encoding='utf-8') as f:
                    pass

    
    def should_reflect(self, agent_id: str, current_year: int) -> bool:
        """Check if it's time for an agent to perform reflection."""
        if self.reflection_interval <= 0:
            return False
        return current_year > 0 and current_year % self.reflection_interval == 0

    def should_reflect_triggered(
        self,
        agent_id: str,
        agent_type: str,
        current_year: int,
        trigger: ReflectionTrigger,
        trigger_config: Optional[ReflectionTriggerConfig] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Check if reflection should fire based on trigger type and agent type."""
        if trigger_config is None:
            trigger_config = ReflectionTriggerConfig()

        context = context or {}

        if trigger == ReflectionTrigger.CRISIS:
            if not trigger_config.crisis:
                return False
            return True

        if trigger == ReflectionTrigger.PERIODIC:
            interval = trigger_config.periodic_interval
            if interval <= 0:
                return False
            return current_year > 0 and current_year % interval == 0

        if trigger == ReflectionTrigger.DECISION:
            decision = context.get("decision", "")
            return decision in trigger_config.decision_types

        if trigger == ReflectionTrigger.INSTITUTIONAL:
            # Phase 6C-v3 (2026-05-10): institutional agent-type set is
            # configurable via ``ReflectionEngine.institutional_agent_types``
            # (constructor arg) instead of hardcoded ("government",
            # "insurance"). New domains supply their own set.
            institutional_types = getattr(
                self, "_institutional_agent_types", ("government", "insurance"),
            )
            if agent_type not in institutional_types:
                return False
            policy_change = abs(context.get("policy_change_magnitude", 0.0))
            return policy_change > trigger_config.institutional_threshold

        return False

    @staticmethod
    def load_trigger_config(config_dict: Optional[Dict[str, Any]] = None) -> ReflectionTriggerConfig:
        """Load ReflectionTriggerConfig from a dict (typically from YAML)."""
        if not config_dict:
            return ReflectionTriggerConfig()

        triggers = config_dict.get("triggers", config_dict)
        return ReflectionTriggerConfig(
            crisis=triggers.get("crisis", True),
            periodic_interval=triggers.get("periodic_interval", 5),
            decision_types=triggers.get("decision_types", []),
            institutional_threshold=triggers.get("institutional_threshold", 0.05),
            method=config_dict.get("method", "hybrid"),
            batch_size=config_dict.get("batch_size", 10),
            importance_boost=config_dict.get("importance_boost", 0.85),
        )
    
    def generate_reflection_prompt(
        self,
        agent_id: str,
        memories: List[str],
        current_year: int,
        tick_label: str = "Year",
    ) -> str:
        """
        Generate a prompt asking the LLM to synthesize memories into insights.

        This is domain-agnostic; the memories themselves contain the domain context.
        ``tick_label`` names the decision period in prompt text ("Year" default —
        byte-identical to pre-3-5; a sub-annual domain passes e.g. "Day").
        """
        if not memories:
            return ""

        memories_text = "\n".join([f"- {_memory_text(m)}" for m in memories])

        return f"""You are reflecting on your experiences from the past {self.reflection_interval} {tick_label.lower()}(s).

**Your Recent Memories:**
{memories_text}

**Task:** Summarize the key lessons you have learned from these experiences. 
Focus on:
1. What patterns or trends have you noticed?
2. What actions proved beneficial or harmful?
3. How will this influence your future decisions?

Provide a concise summary (2-3 sentences) that captures the most important insight.
"""

    @staticmethod
    def extract_agent_context(agent, year: int = 0) -> AgentReflectionContext:
        """Extract a domain-neutral reflection context from an agent.

        Builds only generic identity fields. Domain-specific data goes in
        ``custom_traits`` — a domain populates it at its own reflection
        call site (Phase 6H Item 9; this method no longer reads any
        flood-specific agent attribute).
        """
        # Phase 6R-B-4 (audit cluster E item #17): no fallback to the
        # literal 'household' — if the agent has no agent_type
        # attribute, raise via AgentReflectionContext.__post_init__
        # with a clear message naming the offending agent.
        agent_type = getattr(agent, 'agent_type', None)
        return AgentReflectionContext(
            agent_id=getattr(agent, 'id', str(agent)),
            agent_type=agent_type,
            name=getattr(agent, 'name', ''),
            years_in_sim=year,
            mg_status=getattr(agent, 'mg_status', False),
            recent_decision=getattr(agent, 'last_decision', ''),
            custom_traits=dict(getattr(agent, 'custom_traits', {}) or {}),
        )

    def generate_personalized_reflection_prompt(
        self,
        context: AgentReflectionContext,
        memories: List[str],
        current_year: int,
        reflection_questions: Optional[List[str]] = None,
        tick_label: str = "Year",
    ) -> str:
        """Generate a personalized reflection prompt with agent identity.

        Domain-specific status text is provided by the registered
        DomainPack via ``reflection_status_text`` (Phase 6H Item 9). With
        no pack registered the prompt carries only the generic identity
        line. A new domain registers a DomainPack rather than subclassing
        this method.
        """
        if not memories:
            return ""

        memories_text = "\n".join([f"- {_memory_text(m)}" for m in memories])

        identity_lines = [f"You are {context.agent_id}"]
        if context.name:
            identity_lines[0] += f" ({context.name})"
        identity_lines[0] += f", a {context.agent_type} agent in {tick_label} {current_year}."

        # Phase 6C-v2 / 6H Item 9: domain-specific status text comes from
        # the registered DomainPack. Scan all packs and use the first
        # non-None status line — packs gate eligibility internally
        # (e.g. FloodDomainPack checks agent_type=="household"). With no
        # registered pack the prompt carries only the generic identity
        # line (the legacy hardcoded flood fallback was removed in 6H
        # Item 9).
        try:
            from broker.domains.registry import DomainPackRegistry
            for name in DomainPackRegistry.domains():
                pack = DomainPackRegistry.get(name)
                if pack is None:
                    continue
                status_line = pack.reflection_status_text(context)
                if status_line:
                    identity_lines.append(status_line)
                    break
        except ImportError:
            pass

        identity_block = "\n".join(identity_lines)

        # Phase 6H Item 4: questions resolved by the caller via
        # AgentTypeConfig.get_reflection_questions(agent_type); the generic
        # fallback below is used only when the caller passes nothing.
        questions = reflection_questions or _DEFAULT_REFLECTION_QUESTIONS
        q_text = "\n".join([f"- {q}" for q in questions])

        return f"""{identity_block}

**Your Recent Memories:**
{memories_text}

**Reflection Questions:**
{q_text}

**Task:** Based on your experiences and situation, provide a 2-3 sentence personal reflection capturing what you've learned and how it will shape your future decisions. Speak in first person.
"""

    def generate_personalized_batch_prompt(
        self,
        batch_data: List[Dict[str, Any]],
        current_year: int,
        tick_label: str = "Year",
    ) -> str:
        """Generate batch prompt with per-agent identity context."""
        if not batch_data:
            return ""

        lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} agents in {tick_label} {current_year}."]
        lines.append("Instructions: Provide a personalized 2-sentence reflection for each agent based on their unique situation and memories.\n")

        lines.append("### Agent Data")
        for item in batch_data:
            agent_id = item.get("agent_id", "Unknown")
            ctx = item.get("context")
            memories = item.get("memories", [])
            mem_text = " ".join(_memory_text(m) for m in memories) if memories else "(No memories)"

            if ctx:
                identity = f"[{ctx.agent_type}"
                # Domain trait labels via the active DomainPack
                # (Phase 6H Item 9 — replaces the hardcoded flood traits
                # block). Pack-scan mirrors the reflection_status_text
                # path used by the individual prompt above.
                traits = []
                try:
                    from broker.domains.registry import DomainPackRegistry
                    for _name in DomainPackRegistry.domains():
                        _pack = DomainPackRegistry.get(_name)
                        if _pack is None:
                            continue
                        traits = _pack.reflection_trait_labels(ctx)
                        if traits:
                            break
                except ImportError:
                    pass
                if traits:
                    identity += f", {', '.join(traits)}"
                identity += "]"
            else:
                identity = "[household]"

            lines.append(f"{agent_id} {identity} Memories: {mem_text}")

        lines.append("\n### Output Requirement")
        lines.append("Return ONLY a JSON object mapping Agent IDs to personalized reflection strings. Each reflection should reference the agent's specific situation. No filler.")

        return "\n".join(lines)

    def compute_dynamic_importance(
        self,
        context,
        base_importance: float = 0.9,
    ) -> float:
        """Compute variable importance based on agent state.

        Resolution order (Phase 6H Item 9): an attached
        DomainReflectionAdapter → the first registered DomainPack that
        exposes ``compute_importance`` → the generic ``base_importance``.
        The legacy flood-keyword fallback was removed; a domain supplies
        importance scoring via its DomainPack or adapter.

        Args:
            context: AgentReflectionContext dataclass **or** plain dict.
            base_importance: Default importance when no domain supplies one.

        Returns:
            Importance score in [0.0, 1.0].
        """
        # Normalise context to a dict ONCE — domain compute_importance
        # implementations expect a mapping. The adapter path always did
        # this; the pack-scan below previously passed the raw context,
        # which broke a dict-only adapter (e.g. IrrigationAdapter calls
        # context.get(...)) when handed an AgentReflectionContext
        # dataclass. Both paths now share the normalised dict (6H Item 9).
        if hasattr(context, "__dataclass_fields__"):
            from dataclasses import asdict
            ctx_dict = asdict(context)
        elif isinstance(context, dict):
            ctx_dict = context
        else:
            ctx_dict = {"context": context}

        # --- Adapter path (domain-agnostic) ---
        if self.adapter is not None:
            return self.adapter.compute_importance(ctx_dict, base_importance)

        # First registered pack exposing compute_importance wins (mirrors the
        # reflection_status_text convention above); multi-domain runs must
        # ensure only one pack is eligible.
        try:
            from broker.domains.registry import DomainPackRegistry
            for name in DomainPackRegistry.domains():
                pack = DomainPackRegistry.get(name)
                if pack is None:
                    continue
                fn = getattr(pack, "compute_importance", None)
                if callable(fn):
                    importance = fn(ctx_dict, base_importance)
                    if isinstance(importance, (int, float)):
                        return round(min(1.0, max(0.0, importance)), 2)
        except ImportError:
            pass

        # No adapter and no DomainPack supplied an importance score →
        # the generic base score. The legacy flood-keyword fallback
        # (IMPORTANCE_PROFILES) was removed in Phase 6H Item 9; a domain
        # supplies scoring via its DomainPack.compute_importance or a
        # DomainReflectionAdapter.
        return round(min(1.0, max(0.0, base_importance)), 2)

    def parse_reflection_response(
        self,
        raw_response: str,
        source_memory_count: int,
        current_year: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[ReflectionInsight]:
        """Parse LLM response into a ReflectionInsight.

        If an adapter is attached and *context* is provided, the importance
        score is computed dynamically instead of using the static boost.
        """
        if not raw_response or len(raw_response.strip()) < 10:
            return None

        # Clean and truncate if needed
        summary = raw_response.strip()[:500]

        # Dynamic importance via adapter when context is available
        importance = self.importance_boost
        if self.adapter is not None and context is not None:
            importance = self.adapter.compute_importance(context, self.importance_boost)

        return ReflectionInsight(
            summary=summary,
            source_memory_count=source_memory_count,
            importance=importance,
            year_created=current_year,
            domain_tags=[]
        )

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM client."""
        if self.llm_client is None:
            raise RuntimeError("ReflectionEngine requires llm_client for prompt execution.")
        if callable(self.llm_client):
            return self.llm_client(prompt)
        if hasattr(self.llm_client, "generate"):
            return self.llm_client.generate(prompt)
        raise RuntimeError("ReflectionEngine llm_client is not callable or compatible.")

    def reflect(self, agent_id: str, memories: List[str], context: dict):
        """Legacy reflection flow using built-in prompt + parse."""
        current_year = int(context.get("current_year", 0)) if context else 0
        prompt = self.generate_reflection_prompt(agent_id, memories, current_year)
        if not prompt:
            return None
        response = self._call_llm(prompt)
        return self.parse_reflection_response(response, len(memories), current_year)

    def reflect_v2(self, agent_id: str, memories: list, context: dict):
        """v2 reflection using SDK templates."""
        if self.template:
            prompt = self.template.generate_prompt(agent_id, memories, context)
            response = self._call_llm(prompt)
            insight = self.template.parse_response(response, memories, context)

            if self.integrator:
                self.integrator.process_reflection(agent_id, response, memories, context)

            return insight
        return self.reflect(agent_id, memories, context)
    
    def store_insight(self, agent_id: str, insight: ReflectionInsight) -> None:
        """Store a reflection insight for an agent."""
        if agent_id not in self.reflection_history:
            self.reflection_history[agent_id] = []
        self.reflection_history[agent_id].append(insight)
        
        # Log to file if configured
        if self.output_path:
            import json
            from dataclasses import asdict
            entry = asdict(insight)
            reflection_input = getattr(insight, "reflection_input", None)
            if reflection_input is not None:
                entry["reflection_input"] = list(reflection_input)
            entry["agent_id"] = agent_id
            entry["timestamp"] = datetime.now().isoformat()
            try:
                with open(self.output_path, 'a', encoding='utf-8') as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception as e:
                logger.error(f"[Reflection] Failed to write log: {e}")

        logger.info(f"[Reflection] Agent {agent_id} | New insight stored | Importance: {insight.importance:.2f}")
    
    def get_insights(self, agent_id: str, top_k: int = 3) -> List[ReflectionInsight]:
        """Retrieve top insights for an agent, sorted by importance."""
        insights = self.reflection_history.get(agent_id, [])
        return sorted(insights, key=lambda x: x.importance, reverse=True)[:top_k]
    
    def format_insights_for_context(self, agent_id: str, top_k: int = 2) -> str:
        """Format insights as a string for injection into agent context."""
        insights = self.get_insights(agent_id, top_k)
        if not insights:
            return ""
        
        lines = ["**Long-Term Lessons (Reflections):**"]
        for i, insight in enumerate(insights, 1):
            lines.append(f"{i}. (Year {insight.year_created}) {insight.summary}")
        return "\n".join(lines)
    
    # =========================================================================
    # BATCH REFLECTION (Efficiency Optimization)
    # =========================================================================
    def generate_batch_reflection_prompt(
        self,
        batch_data: List[Dict[str, Any]],
        current_year: int,
        reflection_questions: Optional[List[str]] = None,
        persona_instruction: Optional[str] = None,
        tick_label: str = "Year",
        *,
        year_lines: bool = False,
        fact_lines: Optional[Union[Sequence[str], Mapping[str, Sequence[str]]]] = None,
        rule_lines: Optional[Union[Sequence[str], Mapping[str, Sequence[str]]]] = None,
    ) -> str:
        """
        Generate a prompt for batch reflection across multiple agents.
        Optimized for smaller models like Llama 3.2.

        Args:
            batch_data: Per-agent dicts with agent_id, memories, and optional context.
            current_year: Current simulation year.
            reflection_questions: Optional domain-specific guidance questions
                from YAML config (global_config.reflection.questions).
            persona_instruction: Optional instruction to enforce a specific persona
                viewpoint (e.g., "Speak in first person as the agent").
            tick_label: Decision-period noun for prompt text ("Year" default —
                byte-identical to pre-3-5; sub-annual domains pass e.g. "Day").
            year_lines: ``reflection.year_lines`` (45b, default False): each
                agent's memories one per line ("- " bullets), oldest first by
                the ``"year"`` key every item must carry
                (``order_by_year``). False keeps the shipped single
                space-joined paragraph.
            fact_lines: ``reflection.program_facts`` (45c, default None):
                program-written fact lines shown under ``RECORD_HEADING``,
                followed by ``LESSON_ONLY_INSTRUCTION`` (no years or numbers in
                the answer). A list for a one-agent batch, or a mapping from
                agent id to lines.
            rule_lines: Optional rules of the simulation that apply to the
                agent (e.g. how shared resources are allocated), shown after its
                memories under "Rules that apply to {agent_id}:". Same shapes
                as ``fact_lines``; default None.

        With all three left at their defaults the prompt is byte-identical
        to the one before these options existed.
        """
        if not batch_data:
            return ""

        # "1 agent", not "1 agents": a domain that reflects one agent per
        # call reads a grammatical header; every other batch size renders
        # byte-for-byte as before.
        agents_noun = "agent" if len(batch_data) == 1 else "agents"
        lines = [f"### Background\nYou are a Reflection Assistant for {len(batch_data)} {agents_noun} in a simulation ({tick_label} {current_year})."]
        
        if persona_instruction:
            lines.append(f"Instructions: {persona_instruction}")
        else:
            lines.append("Instructions: Summarize each agent's memories into a 2-sentence 'Lesson Learned'.")

        if reflection_questions:
            lines.append("Focus your reflections on:")
            for q in reflection_questions:
                lines.append(f"  - {q}")

        lines.append("")

        lines.append("### Task Data to Process")
        n_agents = len(batch_data)
        facts_by_agent: List[tuple] = []
        for item in batch_data:
            agent_id = item.get("agent_id", "Unknown")
            memories = item.get("memories", [])
            if year_lines and memories:
                # 45b: one line per memory, oldest first.
                lines.append(f"{agent_id} Memories:")
                lines.extend(f"- {_memory_text(m)}" for m in order_by_year(memories))
            else:
                mem_text = " ".join(_memory_text(m) for m in memories) if memories else "(No memories recorded)"
                lines.append(f"{agent_id} Memories: {mem_text}")
            rules = _per_agent_lines(rule_lines, agent_id, n_agents, "rule_lines")
            if rules:
                lines.append(f"Rules that apply to {agent_id}:")
                lines.extend(f"- {r}" for r in rules)
            facts = _per_agent_lines(fact_lines, agent_id, n_agents, "fact_lines")
            if facts:
                facts_by_agent.append((agent_id, facts))

        if facts_by_agent:
            # 45c: the record the program writes and stores with the lesson.
            lines.append("")
            lines.append(RECORD_HEADING)
            for agent_id, facts in facts_by_agent:
                lines.append(f"{agent_id} Record:")
                lines.extend(f"- {f}" for f in facts)

        lines.append("\n### Output Requirement")
        lines.append("Return ONLY the JSON object mapping Agent IDs to strings. No conversational filler.")
        if facts_by_agent:
            lines.append(LESSON_ONLY_INSTRUCTION)

        return "\n".join(lines)
    
    def parse_batch_reflection_response(
        self,
        raw_response: str,
        batch_agent_ids: List[str],
        current_year: int,
        *,
        allow_plain_text: bool = False,
    ) -> Dict[str, Optional[ReflectionInsight]]:
        """
        Robust multi-stage parser for batch reflections.
        Handles JSON, Markdown, and Heuristic Line-parsing. When the batch
        holds exactly one agent id, a one-key JSON reply with a non-blank
        string value is read for that agent whatever the key is called.
        ``allow_plain_text`` is opt-in for the checked one-agent call; all
        other callers retain the structured-reply requirement.
        """
        import json
        import re
        
        results: Dict[str, Optional[ReflectionInsight]] = {aid: None for aid in batch_agent_ids}
        
        if not raw_response or len(raw_response.strip()) < 5:
            logger.warning("[Reflection:Batch] Empty or trivial response.")
            return results
        
        # --- Stage 1: Standard JSON Extraction & Repair ---
        json_content = raw_response
        # Find latest/outermost { } block
        json_match = re.search(r'(\{.*\})', raw_response, re.DOTALL)
        if json_match:
            json_content = json_match.group(1)
        
        success = False
        data = None
        try:
            # Try to repair common small-model JSON errors
            repaired = json_content.strip()
            # Quote Agent IDs if unquoted (e.g. Agent_001: "...")
            repaired = re.sub(r'(?<!")(\bAgent_\d+\b)(?!")', r'"\1"', repaired)
            # Clean trailing commas (e.g. "key": "val", })
            repaired = re.sub(r',\s*\}', '}', repaired)
            
            data = json.loads(repaired)
            if isinstance(data, dict):
                for aid in batch_agent_ids:
                    # Case-insensitive key lookup for robustness
                    found_key = next((k for k in data.keys() if k.lower() == aid.lower()), None)
                    if found_key and isinstance(data[found_key], str):
                        results[aid] = self._create_insight(data[found_key], current_year, truncate=not allow_plain_text)

                # Single-agent batch (batch_size 1): small models often answer
                # under a shortened or generic key ("Agent_1", the tail of a
                # compound id) instead of the exact id. The prompt held only
                # this agent's memories, so a one-key reply can only be about
                # this agent.
                if (len(batch_agent_ids) == 1 and results[batch_agent_ids[0]] is None
                        and len(data) == 1):
                    sole_key, sole_value = next(iter(data.items()))
                    if isinstance(sole_value, str) and sole_value.strip():
                        results[batch_agent_ids[0]] = self._create_insight(sole_value, current_year, truncate=not allow_plain_text)
                        logger.info("[Reflection:Batch] Single-id reply read under key %r for %s",
                                    sole_key, batch_agent_ids[0])

                if any(v is not None for v in results.values()):
                    success = True
                    logger.info("[Reflection:Batch] Stage 1 (JSON) parsing successful.")
        except Exception as e:
            logger.debug(f"[Reflection:Batch] Stage 1 failed: {e}")

        # Only a one-agent reply can be attributed without an exact id.
        # These off-schema forms retain the complete value for the usual
        # normalization and checks, including years, numbers and length.
        if len(batch_agent_ids) == 1 and results[batch_agent_ids[0]] is None:
            value = None
            try:
                if not isinstance(data, dict):
                    data = json.loads(json_content)
                if isinstance(data, dict) and isinstance(data.get("lesson"), str):
                    candidate = data["lesson"]
                    if candidate.strip():
                        value = candidate
            except Exception:
                quoted = r'"(?:[^"\\]|\\.)*"'
                chained = re.fullmatch(
                    rf'\{{\s*{quoted}\s*:\s*(?P<middle>{quoted})\s*:\s*(?P<lesson>{quoted})\s*,?\s*\}}',
                    json_content.strip(), re.DOTALL)
                if chained:
                    try:
                        middle = json.loads(chained.group("middle"))
                        candidate = json.loads(chained.group("lesson"))
                        middle_is_id_like = (
                            not re.search(r"[.!?]", middle) and len(middle.split()) <= 6
                            and len(middle.split()) < len(candidate.split())
                        )
                        if candidate.strip() and middle_is_id_like:
                            value = candidate
                        else:
                            return results  # Rejected chains must not reach legacy recovery.
                    except Exception:
                        return results  # An invalid escape remains an unreadable reply.
            if value is not None:
                insight = self._create_insight(value, current_year, truncate=not allow_plain_text)
                insight.parse = "lenient"
                results[batch_agent_ids[0]] = insight
                success = True
            elif (isinstance(data, dict) and isinstance(data.get("lesson"), str)
                  and not data["lesson"].strip()):
                return results

        # Checked one-agent replies must retain the whole value. The legacy
        # fallback stages split on quotes/newlines and would hide later
        # numbers or length violations. Unreadable objects use the retry.
        if allow_plain_text and len(batch_agent_ids) == 1:
            aid = batch_agent_ids[0]
            if results[aid] is None and not re.search(r"[{}\[\]]", raw_response):
                value = re.sub(
                    rf"^\s*[\"*']?{re.escape(aid)}[\"*']?\s*[:\-]\s*",
                    "", raw_response, count=1, flags=re.I)
                results[aid] = self._create_insight(value, current_year, truncate=False)
                results[aid].parse = "plain_text"
            return results

        # --- Stage 2: Regex Fallback (Key: Value Pattern) ---
        if not success or any(v is None for v in results.values()):
            logger.info("[Reflection:Batch] Attempting Stage 2 (Regex) parsing...")
            for aid in batch_agent_ids:
                if results[aid] is not None: continue
                # Match "Agent_XXX": "Insight..." or **Agent_XXX**: Insight...
                pattern = rf'["\*\']?{re.escape(aid)}["\*\']?\s*[:\-]\s*["\']?([^"\'\n\r]+)["\']?'
                match = re.search(pattern, raw_response, re.IGNORECASE)
                if match:
                    results[aid] = self._create_insight(match.group(1).strip(), current_year, truncate=not allow_plain_text)
            
            if any(v is not None for v in results.values()):
                success = True

        # --- Stage 3: Heuristic Line Parsing (Final Resort) ---
        if not success or any(v is None for v in results.values()):
            logger.info("[Reflection:Batch] Attempting Stage 3 (Heuristic) parsing...")
            lines = raw_response.split('\n')
            for line in lines:
                for aid in batch_agent_ids:
                    if results[aid] is not None: continue
                    if aid.lower() in line.lower() and (':' in line or '-' in line):
                        # Extract everything after the delimiter
                        parts = re.split(r'[:\-]', line, 1)
                        if len(parts) > 1 and len(parts[1].strip()) > 10:
                            results[aid] = self._create_insight(parts[1].strip(), current_year, truncate=not allow_plain_text)
        
        # A one-agent batch can use a checked plain-text lesson. Structured
        # replies that failed the earlier stages remain unreadable.
        if (allow_plain_text and len(batch_agent_ids) == 1 and results[batch_agent_ids[0]] is None
                and not re.search(r"[{}\[\]]", raw_response)):
            results[batch_agent_ids[0]] = self._create_insight(raw_response, current_year, truncate=False)

        return results

    def _create_insight(
        self, text: str, year: int, context: Optional[Dict[str, Any]] = None, *, truncate: bool = True
    ) -> ReflectionInsight:
        """Helper to create a standard insight object.

        Uses adapter-based importance when context is provided.
        """
        importance = self.importance_boost
        if self.adapter is not None and context is not None:
            importance = self.adapter.compute_importance(context, self.importance_boost)

        return ReflectionInsight(
            summary=text.strip()[:500] if truncate else text.strip(),
            source_memory_count=0,
            importance=importance,
            year_created=year,
            domain_tags=[]
        )

    def clear(self, agent_id: str) -> None:
        """Clear reflection history for an agent."""
        if agent_id in self.reflection_history:
            del self.reflection_history[agent_id]
