"""Replay one recorded agent-year decision, with one context factor removed.

What this module gives you
--------------------------
``load_snapshots(run_dir)`` turns a finished run's JSONL traces into
:class:`DecisionSnapshot` objects — one per agent-year decision, each
carrying the prompt that agent actually saw. ``replay_decision`` sends
that prompt back through the decider with one factor neutralised, and
``determinism_check`` establishes whether the decider is even capable of
supporting a comparison.

Fidelity: one regime, and the column that keeps it honest
---------------------------------------------------------
Every row carries a ``fidelity`` column, and today that column has
exactly one value: ``prompt_only``. The saved trace carries the rendered
prompt but not the context that produced it, so the replay edits the
prompt text directly with a regular expression. Everything downstream is
production-faithful — same parser, same validators — but the
intervention is a string substitution rather than a context edit.

``AuditWriter`` records ``input`` (the rendered prompt), ``memory_pre``,
``social_audit``, ``environment_context`` and ``state_before``, which are
derived summaries; it does not record ``context`` as
``TieredContextBuilder.build`` returned it, and several of that dict's
branches (``local.spatial``, ``institutional``, ``global``,
``system_prompt``, ``available_skills``, the rendered options text) are
not recoverable from the summaries.

A context-level replay — edit the context where the model builder
declared the factor, then re-render through the domain's own template —
is NOT implemented here, and no code path in this package pretends
otherwise. A trace that already carries a ``context_snapshot`` key gets a
warning and is still replayed as ``prompt_only``. The column stays so
that the schema is forward-compatible: when the audit writer starts
recording the builder's context, a second value can be added without
changing the shape of any table already published.

Why the mask is a substitution and never a deletion
---------------------------------------------------
Removing a sentence changes the prompt's shape as well as its content.
The model then sees a stimulus unlike anything in the run, and a
behaviour change no longer isolates the factor. So a
:class:`MaskSpec` replaces the factor's span with a documented neutral
rendering ("No information about tolls is available.") and this module
refuses an empty replacement.

Reconstruction is verified, not asserted
----------------------------------------
When a governance engine is supplied, replaying the UNMASKED prompt
should return the decision the trace recorded. ``replay_decision``
reports ``matches_trace`` per row so the caller can check that the
reconstruction reproduces the original before reading anything into the
masked arms. A trace that recorded no action at all reports
``matches_trace=None`` rather than counting "no action" against "no
action" as agreement.
"""
from __future__ import annotations

import copy
import difflib
import importlib
import inspect
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from broker.utils.logging import logger

# ─────────────────────────────────────────────────────────────────────
# Vocabulary
# ─────────────────────────────────────────────────────────────────────

#: The only fidelity regime that exists. Kept as a named column rather
#: than dropped, so a future context-level replay can add a second value
#: without changing the shape of any published table.
FIDELITY_PROMPT_ONLY = "prompt_only"

ARM_BASELINE = "baseline"
ARM_MASKED = "masked"
ARM_CONTROL = "paraphrase_control"
ARMS = (ARM_BASELINE, ARM_MASKED, ARM_CONTROL)

#: The verdict a row carries when the decider was never called for it —
#: a factor-absent arm, or an arm whose factor declares no control.
VERDICT_NOT_RUN = "not_run"

#: A replacement rendering: either a ``re.sub`` template (backreferences
#: such as ``\1`` work) or a callable taking the matched text.
Rendering = Union[str, Callable[[str], str]]


# ─────────────────────────────────────────────────────────────────────
# Factor declaration
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MaskSpec:
    """How to neutralise one named factor in an agent's context.

    ``provider`` / ``key`` name the factor's home in the context dict.
    They are documentation: the replay edits the rendered prompt, not the
    context, so nothing reads them at run time. They exist so a reader
    can find the code that produced the span.

    ``pattern`` is the regular expression that finds the factor's span in
    the rendered prompt. Every occurrence is replaced, because a factor
    that appears in three memory bullets is present three times. Say so
    in ``description``: "the neighbour line" and "every neighbour line
    the agent remembers" are different factors, and a pattern that
    matches all of them is the second one.

    ``neutral`` is the rendering that replaces it. ``paraphrase`` is the
    severity-matched control: same information, different wording,
    similar edit size. ``paraphrase=None`` is allowed and means the
    control arm cannot run for this factor — the ablation then says so
    rather than reporting the masked arm as though it stood alone.

    ``expected_sign`` is the direction the factor's own story predicts
    for the masked arm's delta-P. The default ``-1`` says "removing this
    factor should make the recorded action LESS likely", which is what a
    reasoning trace that cites the factor as a reason implies. Declare
    ``+1`` for a factor whose removal should make the action MORE likely
    (a deterrent), and the directional-consistency number is then scored
    against the direction this domain actually claims rather than a
    framework-wide assumption.
    """

    provider: str
    key: str
    neutral: Rendering
    paraphrase: Optional[Rendering] = None
    pattern: Optional[str] = None
    description: str = ""
    expected_sign: int = -1

    def __post_init__(self) -> None:
        if isinstance(self.neutral, str) and not self.neutral.strip():
            raise ValueError(
                f"MaskSpec for {self.provider}.{self.key}: 'neutral' is empty. "
                "A mask replaces a factor with its documented neutral "
                "rendering; deleting the span makes the prompt "
                "off-distribution and the result uninterpretable."
            )
        if isinstance(self.paraphrase, str) and not self.paraphrase.strip():
            raise ValueError(
                f"MaskSpec for {self.provider}.{self.key}: 'paraphrase' is "
                "empty. Pass None to declare that this factor has no "
                "severity-matched control."
            )
        if self.expected_sign not in (-1, 1):
            raise ValueError(
                f"MaskSpec for {self.provider}.{self.key}: expected_sign must "
                f"be -1 or +1 (got {self.expected_sign!r}). Zero is not a "
                "prediction, and a factor with no predicted direction should "
                "say so in its description instead."
            )
        if self.pattern is not None:
            try:
                re.compile(self.pattern)
            except re.error as exc:
                raise ValueError(
                    f"MaskSpec for {self.provider}.{self.key}: pattern does "
                    f"not compile ({exc})."
                ) from exc

    @property
    def has_control(self) -> bool:
        return self.paraphrase is not None

    def to_dict(self) -> Dict[str, Any]:
        """JSON-safe description (callables render as ``<callable>``)."""
        def _render(value: Optional[Rendering]) -> Optional[str]:
            if value is None:
                return None
            return value if isinstance(value, str) else "<callable>"

        return {
            "provider": self.provider,
            "key": self.key,
            "pattern": self.pattern,
            "neutral": _render(self.neutral),
            "paraphrase": _render(self.paraphrase),
            "has_control": self.has_control,
            "expected_sign": self.expected_sign,
            "description": self.description,
        }


class FactorMap:
    """The factors a domain declares as ablatable: name -> MaskSpec."""

    def __init__(self, specs: Optional[Dict[str, MaskSpec]] = None) -> None:
        specs = specs or {}
        bad = [k for k, v in specs.items() if not isinstance(v, MaskSpec)]
        if bad:
            raise TypeError(
                f"FactorMap entries must be MaskSpec instances; "
                f"{sorted(bad)} are not."
            )
        self._specs: Dict[str, MaskSpec] = dict(specs)

    @classmethod
    def from_domain(cls, domain: Optional[str]) -> "FactorMap":
        """Read ``DomainPack.context_mask_defaults()`` for ``domain``.

        An unregistered name is an error, not an empty map.
        ``DomainPackRegistry.get_or_default`` answers with
        ``DefaultDomainPack`` for any name it does not know, and that
        pack declares no factors — so a typo in ``--domain`` would come
        back as "this domain declares nothing to ablate" and read like a
        finding about the domain rather than a misspelling.
        """
        from broker.domains.registry import DomainPackRegistry

        registered = DomainPackRegistry.get(domain) if domain else None
        if registered is None:
            known = sorted(DomainPackRegistry.domains())
            raise KeyError(
                f"Domain {domain!r} is not registered, so it declares no "
                f"ablatable factors. Registered: {known}. Import the module "
                "that registers the pack first (--import-module), or pass "
                "--masks <module:attr> to name the factor dict directly. "
                "Falling through to DefaultDomainPack would answer 'no "
                "factors declared', which reads like a fact about the domain "
                "rather than a misspelled name."
            )

        hook = getattr(registered, "context_mask_defaults", None)
        if hook is None:
            logger.warning(
                "[Ablation] DomainPack for %r has no context_mask_defaults() "
                "hook (pack predates PR-5 or does not subclass "
                "DefaultDomainPack); treating as no declared factors.",
                domain,
            )
            return cls({})
        return cls(hook() or {})

    def __contains__(self, name: object) -> bool:
        return name in self._specs

    def __getitem__(self, name: str) -> MaskSpec:
        return self._specs[name]

    def __len__(self) -> int:
        return len(self._specs)

    @property
    def names(self) -> List[str]:
        return sorted(self._specs)

    def get(self, name: str) -> Optional[MaskSpec]:
        return self._specs.get(name)

    def describe(self) -> Dict[str, Any]:
        return {name: spec.to_dict() for name, spec in sorted(self._specs.items())}


# ─────────────────────────────────────────────────────────────────────
# Applying a mask to a rendered prompt
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MaskApplication:
    """The result of editing one prompt for one arm."""

    arm: str
    prompt: str
    matches: int
    perturbation_chars: int
    applied: bool
    reason: str = ""

    @property
    def factor_present(self) -> bool:
        return self.matches > 0


def _perturbation_chars(before: str, after: str) -> int:
    """Characters this edit touched, counted over the diff.

    Used to check that the masked and control arms perturb the prompt by
    a similar amount. If they do not, "the factor moved the model" and
    "the bigger edit moved the model" are not separable.
    """
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    changed = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            changed += max(i2 - i1, j2 - j1)
    return changed


def _substitute(
    prompt: str, pattern: str, rendering: Rendering,
) -> Tuple[str, int, str]:
    """Replace every occurrence of ``pattern``.

    Returns ``(text, n_matches, failure_reason)``. A rendering callable
    that raises is a declaration bug in ONE factor — the flood
    ``insurance_trust`` paraphrase raises when
    ``FloodContextBuilder._verbalize_trust`` emits a phrase it does not
    know. Letting that exception out aborts the whole grid, so every
    other factor's rows are lost to one factor's stale vocabulary. It is
    caught here and returned as a reason instead; the row is written with
    ``applied=False`` and the run continues.
    """
    if callable(rendering):
        def _repl(match: "re.Match") -> str:
            replacement = rendering(match.group(0))
            if not isinstance(replacement, str) or not replacement.strip():
                raise ValueError(
                    "A mask rendering returned an empty replacement for "
                    f"{match.group(0)!r}. A mask substitutes; it never deletes."
                )
            return replacement
        try:
            text, matches = re.subn(pattern, _repl, prompt)
        except ValueError as exc:
            return prompt, 0, f"mask rendering failed: {exc}"
        return text, matches, ""
    try:
        text, matches = re.subn(pattern, rendering, prompt)
    except re.error as exc:
        return prompt, 0, f"mask rendering is not a valid template: {exc}"
    return text, matches, ""


def apply_mask(prompt: str, spec: MaskSpec, arm: str) -> MaskApplication:
    """Produce the prompt for one arm of one factor.

    ``baseline`` returns the prompt untouched. ``masked`` substitutes the
    neutral rendering. ``paraphrase_control`` substitutes the control
    rendering, or reports that the factor declares none.

    A zero-match result is not an error: the factor may be genuinely
    absent from this decision (an agent with nobody nearby to observe, a
    period in which the cue never arose). The application is marked
    ``applied=False`` and the
    ablation excludes the snapshot from that factor's statistics instead
    of counting it as a null effect.
    """
    if arm not in ARMS:
        raise ValueError(f"Unknown arm {arm!r}; expected one of {ARMS}.")

    if arm == ARM_BASELINE:
        return MaskApplication(arm, prompt, matches=1, perturbation_chars=0,
                               applied=True, reason="baseline (unmodified)")

    if not spec.pattern:
        return MaskApplication(
            arm, prompt, matches=0, perturbation_chars=0, applied=False,
            reason="no prompt pattern declared; prompt-text replay needs one",
        )

    rendering: Optional[Rendering]
    if arm == ARM_MASKED:
        rendering = spec.neutral
    else:
        rendering = spec.paraphrase
        if rendering is None:
            return MaskApplication(
                arm, prompt, matches=0, perturbation_chars=0, applied=False,
                reason="factor declares no severity-matched paraphrase control",
            )

    edited, matches, failure = _substitute(prompt, spec.pattern, rendering)
    if failure:
        logger.warning("[Ablation] %s.%s (%s arm): %s",
                       spec.provider, spec.key, arm, failure)
        return MaskApplication(
            arm, prompt, matches=0, perturbation_chars=0, applied=False,
            reason=failure,
        )
    if matches == 0:
        return MaskApplication(
            arm, prompt, matches=0, perturbation_chars=0, applied=False,
            reason="factor absent from this prompt (pattern matched nothing)",
        )
    return MaskApplication(
        arm, edited, matches=matches,
        perturbation_chars=_perturbation_chars(prompt, edited),
        applied=True,
        reason="",
    )


# ─────────────────────────────────────────────────────────────────────
# Snapshots
# ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DecisionSnapshot:
    """Everything needed to rebuild ONE agent-year decision offline."""

    snapshot_id: str
    agent_id: str
    year: int
    step_id: str
    agent_type: str
    prompt: str
    context: Dict[str, Any]
    fidelity: str
    seed: Optional[int]
    model: str
    proposed_skill: Optional[str]
    executed_skill: Optional[str]
    outcome: Optional[str]
    parse_layer: Optional[str]
    env_context: Dict[str, Any]
    state_before: Dict[str, Any]
    memory_pre: List[Any]
    run_dir: str
    git_commit: Optional[str]
    trace_index: int
    trace_file: str

    def reference_action(self, stage: str = "proposed") -> Optional[str]:
        """The action a delta-P is measured against.

        ``proposed`` (the default) is the LLM's own choice — the thing
        its reasoning text explains, and therefore the thing a
        faithfulness probe is about. ``executed`` is what the governance
        layer let through; the project's EXECUTED-ONLY rule for headline
        governance metrics lives there, but a mechanism probe that used
        it would be measuring the validators as much as the model.
        """
        if stage == "executed":
            return self.executed_skill
        if stage == "proposed":
            return self.proposed_skill
        raise ValueError(f"Unknown action stage {stage!r}; use 'proposed' or 'executed'.")

def _as_int(value: Any, default: Optional[int] = None) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_manifest(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "reproducibility_manifest.json"
    if not path.is_file():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle) or {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("[Ablation] could not read %s (%s); provenance "
                       "columns will be blank.", path, exc)
        return {}


def _load_config_snapshot(run_dir: Path) -> Dict[str, Any]:
    path = run_dir / "config_snapshot.yaml"
    if not path.is_file():
        return {}
    try:
        import yaml
        with open(path, "r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}
    except Exception as exc:  # noqa: BLE001 — config is advisory here
        logger.warning("[Ablation] could not read %s (%s); falling back to "
                       "the manifest for model and config paths.", path, exc)
        return {}


def resolve_model(
    run_dir: Union[str, Path],
    cli_model: Optional[str] = None,
    *,
    manifest: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Decide which decider model this replay uses. Returns (model, source).

    One resolution, used by the decider and by the summary, so a run
    cannot be executed against one model and reported against another.
    ``--model`` wins; otherwise the model the run itself recorded; and if
    neither exists this raises. It never falls back to ``mock``: a mock
    decider returns the first numbered option whatever the prompt says,
    so a silent fallback would produce a full table of exact zeros that
    reads like "no factor matters".
    """
    if cli_model:
        return str(cli_model), "cli --model"
    manifest = manifest if manifest is not None else _load_manifest(Path(run_dir))
    recorded = manifest.get("model")
    if recorded:
        return str(recorded), "run manifest (reproducibility_manifest.json)"
    raise ValueError(
        f"No decider model for {run_dir}: --model was not given and "
        "reproducibility_manifest.json records none. Pass --model "
        "explicitly. Defaulting to 'mock' is refused — the mock decider "
        "returns the first numbered option whatever the prompt says, so "
        "every factor would come back with a delta-P of exactly zero and "
        "the table would read like a finding."
    )


def _rebuild_context(trace: Dict[str, Any], agent_id: str, agent_type: str) -> Dict[str, Any]:
    """Assemble the closest thing the trace supports to the build() dict.

    Mirrors ``TieredContextBuilder.build``'s shape: ``personal`` holds the
    agent's attributes, ``state`` is the scalar subset used for identity
    rules, ``environment_context`` holds the env dict. It is a
    reconstruction from summaries, not the original object, which is
    exactly why replay verifies itself against the recorded decision
    instead of assuming this is right.

    What it cannot rebuild is ``available_skills``. The audit trace does
    not record the option set the agent was offered, and that set is not
    the domain's full action list: a context builder removes one-way
    skills an agent has already taken, so an agent that has made an
    irreversible change is not offered it a second time. Governance
    replay refuses for that reason — see
    :class:`_SnapshotContextBuilder`.
    """
    state_before = dict(trace.get("state_before") or {})
    context: Dict[str, Any] = {
        "agent_id": agent_id,
        "agent_type": agent_type,
        "personal": dict(state_before),
        "state": {
            k: v for k, v in state_before.items()
            if isinstance(v, (bool, int, float, str)) and k != "name"
        },
        "environment_context": dict(trace.get("environment_context") or {}),
        "memory": list(trace.get("memory_pre") or []),
    }
    context["personal"]["memory"] = list(trace.get("memory_pre") or [])
    return context


def load_snapshots(
    run_dir: Union[str, Path],
    *,
    agent_type: Optional[str] = None,
    limit: Optional[int] = None,
    report: Optional[Dict[str, Any]] = None,
) -> List[DecisionSnapshot]:
    """Read every recorded decision under ``run_dir/raw/*_traces.jsonl``.

    Traces whose ``input`` is empty are skipped with a warning — an
    ABORTED sentinel row records that a step produced no decision, and
    there is no prompt to replay.

    Pass ``report`` (a dict) to receive the intake counts:
    ``n_traces_read``, ``n_dropped_malformed``, ``n_skipped_no_prompt``,
    ``n_skipped_agent_type`` and ``n_snapshots``. The ablation summary
    carries them so "6 snapshots" can be read against "how many rows the
    files held", instead of a number with no denominator.
    """
    run_dir = Path(run_dir)
    intake: Dict[str, Any] = report if report is not None else {}
    intake.update({"n_traces_read": 0, "n_dropped_malformed": 0,
                   "n_skipped_no_prompt": 0, "n_skipped_agent_type": 0,
                   "n_snapshots": 0, "limit": limit,
                   "n_context_snapshot_ignored": 0})

    raw_dir = run_dir / "raw"
    if not raw_dir.is_dir():
        raise FileNotFoundError(
            f"{run_dir} has no raw/ subdirectory — replay needs the JSONL "
            "traces, not just the summary CSVs."
        )
    jsonl_files = sorted(raw_dir.glob("*_traces.jsonl"))
    if not jsonl_files:
        raise FileNotFoundError(f"No *_traces.jsonl files under {raw_dir}.")

    from broker.tools.recover_csv_from_jsonl import _read_jsonl_safely_with_metadata

    manifest = _load_manifest(run_dir)
    config_snapshot = _load_config_snapshot(run_dir)
    default_model = (
        manifest.get("model")
        or (config_snapshot.get("metadata") or {}).get("actual_model")
        or "unknown"
    )
    git_commit = manifest.get("git_commit")

    snapshots: List[DecisionSnapshot] = []
    hit_limit = False
    for jsonl_path in jsonl_files:
        if hit_limit:
            break
        traces, skipped, _meta = _read_jsonl_safely_with_metadata(jsonl_path)
        intake["n_traces_read"] += len(traces)
        intake["n_dropped_malformed"] += skipped
        if skipped:
            logger.warning("[Ablation] %s: %d unreadable line(s) skipped.",
                           jsonl_path.name, skipped)
        for index, trace in enumerate(traces):
            this_type = trace.get("agent_type") or "default"
            if agent_type and this_type != agent_type:
                intake["n_skipped_agent_type"] += 1
                continue
            prompt = trace.get("input") or ""
            if not prompt:
                intake["n_skipped_no_prompt"] += 1
                continue

            proposal = trace.get("skill_proposal") or {}
            approved = trace.get("approved_skill") or {}
            agent_id = str(trace.get("agent_id") or f"agent_{index}")
            year = _as_int(trace.get("year"), 0) or 0

            # C2: there is no context-level replay. A trace that carries
            # the builder's context is still replayed by editing the
            # prompt text, and says so out loud rather than implying a
            # fidelity the code does not implement.
            context_snapshot = trace.get("context_snapshot")
            if isinstance(context_snapshot, dict) and context_snapshot:
                intake["n_context_snapshot_ignored"] += 1
            context = _rebuild_context(trace, agent_id, this_type)

            snapshots.append(DecisionSnapshot(
                snapshot_id=f"{agent_id}|y{year}|{index}",
                agent_id=agent_id,
                year=year,
                step_id=str(trace.get("step_id") or year),
                agent_type=this_type,
                prompt=prompt,
                context=context,
                fidelity=FIDELITY_PROMPT_ONLY,
                seed=_as_int(trace.get("seed")),
                model=str(trace.get("model") or default_model),
                proposed_skill=proposal.get("skill_name"),
                executed_skill=approved.get("skill_name"),
                outcome=trace.get("outcome") or approved.get("status"),
                parse_layer=proposal.get("parse_layer"),
                env_context=dict(trace.get("environment_context") or {}),
                state_before=dict(trace.get("state_before") or {}),
                memory_pre=list(trace.get("memory_pre") or []),
                run_dir=str(run_dir),
                git_commit=git_commit,
                trace_index=index,
                trace_file=jsonl_path.name,
            ))
            if limit is not None and len(snapshots) >= limit:
                hit_limit = True
                break

    # S5: these warnings are the only place a reader learns that rows
    # were dropped, so they must fire on the --limit path too. Before
    # this they sat after a `return` that --limit took.
    if intake["n_skipped_no_prompt"]:
        logger.warning(
            "[Ablation] %d trace(s) carried no prompt (ABORTED sentinel rows) "
            "and cannot be replayed.", intake["n_skipped_no_prompt"],
        )
    if intake["n_context_snapshot_ignored"]:
        logger.warning(
            "[Ablation] %d trace(s) carry a context_snapshot, but context-level "
            "replay is not implemented; using prompt_only. The mask edits the "
            "rendered prompt text, not the context the builder returned.",
            intake["n_context_snapshot_ignored"],
        )
    intake["n_snapshots"] = len(snapshots)
    return snapshots


# ─────────────────────────────────────────────────────────────────────
# The decider seam
# ─────────────────────────────────────────────────────────────────────

class _SnapshotContextBuilder:
    """Feeds one snapshot's context and one arm's prompt to the engine.

    ``SkillBrokerEngine.process_step`` asks its context builder for a
    context and then for a prompt. Swapping this in for the duration of a
    replay lets the ENTIRE production path downstream of that call run
    untouched — the same parse retries, the same validators, the same
    governance retry loop — without a line of the year loop or of
    ``skill_broker_engine.py`` changing.

    It refuses when the reconstructed context has no ``available_skills``.
    ``SkillBrokerEngine._inject_filtered_skills`` treats that key as the
    context builder's pre-filtered option set and, when it is missing,
    offers the domain's FULL action list instead. An agent that took a
    one-way action in year 3 would be offered it again in year 4, the
    governance layer would score that offer, and the resulting
    repeat-adoption rate is the R5 term the project's IBR definition
    excludes precisely because it is an artefact. The audit trace does
    not record the option set, so this refusal is not a configuration
    problem the operator can work around — it is the honest state of the
    trace format.
    """

    def __init__(
        self, snapshot: DecisionSnapshot, prompt: str,
        *, require_available_skills: bool = False,
    ) -> None:
        self._snapshot = snapshot
        self._prompt = prompt
        self._require_available_skills = require_available_skills
        self.memory_engine = None
        self.prompt_templates: Dict[str, str] = {}

    def build(self, agent_id: str, **kwargs: Any) -> Dict[str, Any]:
        context = self._snapshot.context
        if self._require_available_skills and not context.get("available_skills"):
            raise ValueError(
                "Governance replay needs the option set the agent was "
                "actually offered, and this trace does not record it. "
                "WAGF's audit writer does not persist "
                "context['available_skills'], so the rebuilt context has "
                "none, and SkillBrokerEngine._inject_filtered_skills then "
                "falls back to the domain's full action list — re-offering "
                "the one-way skills the live run had removed, so an agent "
                "is offered an irreversible action it has already taken. "
                "The validators would score that offer and inflate exactly "
                "the repeat-adoption term the project's IBR definition "
                "excludes. --with-governance is "
                "therefore unavailable until the audit writer records "
                "available_skills; run without it and read the proposal."
            )
        # S6: a deep copy per call. process_step mutates what the builder
        # returns — _inject_filtered_skills overwrites available_skills
        # and _inject_options_text writes into context['personal'] — so a
        # shallow copy leaks one arm's option text into the next arm's
        # context and the arms stop being independent.
        return copy.deepcopy(context)

    def format_prompt(self, context: Dict[str, Any]) -> str:
        return self._prompt


def _accepts_seed(llm_invoke: Callable) -> bool:
    """Does this decider take a ``seed`` keyword?

    Only a NAMED ``seed`` parameter counts. A ``**kwargs`` catch-all used
    to count, which was wrong twice over: a wrapper that forwards
    ``**kwargs`` to something that ignores ``seed`` would have been
    reported as seeded, and a decorated callable whose signature is
    ``(*args, **kwargs)`` would have been reported as seeded no matter
    what it wraps. ``seeds_applied_to_decider`` is the column a reader
    uses to decide whether the seed column means anything, so it has to
    be false unless the seed provably has somewhere to go.
    """
    try:
        signature = inspect.signature(llm_invoke)
    except (TypeError, ValueError):
        return False
    for name, param in signature.parameters.items():
        if name == "seed" and param.kind in (
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
            inspect.Parameter.KEYWORD_ONLY,
        ):
            return True
    return False


def bind_seed(llm_invoke: Callable, seed: Optional[int]) -> tuple:
    """Return ``(one_arg_callable, seed_applied)``.

    The production decider contract is ``llm_invoke(prompt)`` — there is
    nowhere for a per-call seed to go. A decider that accepts a ``seed``
    keyword gets it; one that does not is called as-is and the row
    records ``seed_applied=False``, so nobody reads a column of distinct
    seeds as evidence of paired sampling that never happened.

    Every backend ``broker.utils.llm_utils.create_llm_invoke`` returns
    today — the mock, the Ollama direct path, the cloud provider
    wrappers — has the signature ``invoke(prompt)``. So in practice this
    returns ``False`` for every real run, and the guide says so.
    """
    if seed is None or not _accepts_seed(llm_invoke):
        return llm_invoke, False

    def _seeded(prompt: str):
        return llm_invoke(prompt, seed=seed)

    return _seeded, True


class ReplayDecider:
    """Runs a prompt through the same parse (and optionally governance) path.

    Two modes, and every row says which one produced it:

    ``engine`` supplied
        ``process_step`` runs with a snapshot-backed context builder, so
        parsing, validators and the governance retry loop are the
        production code, byte for byte. ``governance_evaluated`` is True.

    ``model_adapter`` only
        The prompt goes to the decider and the raw text through the
        production ``ModelAdapter``. Parsing is faithful; no validator
        runs, so ``validator_verdict`` is ``not_evaluated``. This is the
        mode a run directory alone supports: a run records its agent
        config but not its skill registry or custom validators, and
        inventing either would make the verdict fiction.
    """

    def __init__(
        self,
        model_adapter: Any = None,
        engine: Any = None,
        *,
        source: str = "unknown",
        validators_source: str = "none (parse-only: no validator ran)",
        financial_constraints: Optional[bool] = None,
        model: Optional[str] = None,
        model_source: str = "unknown",
    ) -> None:
        if model_adapter is None and engine is None:
            raise ValueError(
                "ReplayDecider needs either a model_adapter (parse-only) or a "
                "SkillBrokerEngine (parse + governance)."
            )
        self.model_adapter = model_adapter or getattr(engine, "model_adapter", None)
        self.engine = engine
        self.source = source
        self.validators_source = validators_source
        self.financial_constraints = financial_constraints
        self.model = model
        self.model_source = model_source

    @property
    def governance_evaluated(self) -> bool:
        return self.engine is not None

    def decide(
        self,
        snapshot: DecisionSnapshot,
        prompt: str,
        llm_invoke: Callable,
        seed: Optional[int] = None,
    ) -> Dict[str, Any]:
        invoke, seed_applied = bind_seed(llm_invoke, seed)
        if self.engine is not None:
            result = self._decide_with_engine(snapshot, prompt, invoke, seed)
        else:
            result = self._decide_parse_only(snapshot, prompt, invoke)
        result["seed_applied"] = seed_applied
        result["governance_evaluated"] = self.governance_evaluated
        result["decider_called"] = True
        return result

    # -- engine path ---------------------------------------------------

    def _decide_with_engine(
        self, snapshot: DecisionSnapshot, prompt: str,
        invoke: Callable, seed: Optional[int],
    ) -> Dict[str, Any]:
        engine = self.engine
        original_builder = engine.context_builder
        engine.context_builder = _SnapshotContextBuilder(
            snapshot, prompt, require_available_skills=True)
        try:
            outcome = engine.process_step(
                agent_id=snapshot.agent_id,
                step_id=_as_int(snapshot.step_id, snapshot.year) or snapshot.year,
                run_id=f"replay_{snapshot.snapshot_id}",
                seed=seed if seed is not None else (snapshot.seed or 0),
                llm_invoke=invoke,
                agent_type=snapshot.agent_type,
                env_context=dict(snapshot.env_context),
            )
        finally:
            engine.context_builder = original_builder

        proposal = outcome.skill_proposal
        approved = outcome.approved_skill
        return {
            "skill": getattr(proposal, "skill_name", None),
            "executed_skill": getattr(approved, "skill_name", None),
            "parse_layer": getattr(proposal, "parse_layer", None),
            "parse_confidence": getattr(proposal, "parse_confidence", None),
            "validator_verdict": getattr(approved, "approval_status", None) or str(outcome.outcome),
            "validation_errors": list(outcome.validation_errors or []),
            "retry_count": outcome.retry_count,
            "format_retries": outcome.format_retries,
            "raw_output": getattr(proposal, "raw_output", "") or "",
            "error": None,
        }

    # -- parse-only path -----------------------------------------------

    def _decide_parse_only(
        self, snapshot: DecisionSnapshot, prompt: str, invoke: Callable,
    ) -> Dict[str, Any]:
        response = invoke(prompt)
        raw_output = response[0] if isinstance(response, tuple) else response
        if not isinstance(raw_output, str):
            raw_output = str(raw_output)

        parse_context = {
            **copy.deepcopy(snapshot.context),
            "agent_id": snapshot.agent_id,
            "agent_type": snapshot.agent_type,
            "retry_attempt": 0,
            "current_year": snapshot.env_context.get("current_year", snapshot.year),
        }
        proposal = self.model_adapter.parse_output(raw_output, parse_context)
        return {
            "skill": getattr(proposal, "skill_name", None),
            "executed_skill": None,
            "parse_layer": getattr(proposal, "parse_layer", None),
            "parse_confidence": getattr(proposal, "parse_confidence", None),
            "validator_verdict": "not_evaluated",
            "validation_errors": [],
            "retry_count": 0,
            "format_retries": 0,
            "raw_output": raw_output,
            "error": None if proposal is not None else "unparsable output",
        }


#: What ``--validators-module`` must expose. Kept as a constant so the
#: error message, the guide and the loader cannot drift apart.
VALIDATORS_MODULE_CONTRACT = "build_custom_validators(config) -> list"


def load_custom_validators(spec: str, config: Any) -> List[Callable]:
    """Import ``spec`` and call its ``build_custom_validators(config)``.

    ``spec`` is a plain module import path (not ``module:attr``): the
    contract is one named function, so there is nothing to choose.
    """
    module = importlib.import_module(spec)
    builder = getattr(module, "build_custom_validators", None)
    if builder is None:
        raise AttributeError(
            f"--validators-module {spec!r} does not expose "
            f"{VALIDATORS_MODULE_CONTRACT}. Add a module-level function of "
            "that name returning the same list the experiment passes to "
            "ExperimentBuilder.with_custom_validators()."
        )
    validators = builder(config)
    if validators is None or isinstance(validators, (str, bytes)) or not hasattr(
            validators, "__iter__"):
        raise TypeError(
            f"{spec}.build_custom_validators(config) must return a list of "
            f"validator callables; got {type(validators).__name__}."
        )
    return list(validators)


def build_replay_decider(
    run_dir: Union[str, Path],
    *,
    model: Optional[str] = None,
    agent_config: Optional[Union[str, Path]] = None,
    with_governance: bool = False,
    validators_module: Optional[str] = None,
    snapshot: Optional[DecisionSnapshot] = None,
) -> ReplayDecider:
    """Build a decider for ``run_dir`` from what that run recorded.

    The agent config comes from the run's ``reproducibility_manifest``
    (``agent_types_config``) when that file is still on disk, else from
    the run's own ``config_snapshot.yaml`` — which carries the same
    parsing rules and governance rules, so parsing stays faithful even
    when the original config has moved.

    ``with_governance=True`` additionally builds validators and the skill
    registry (``skill_registry.yaml`` beside the agent config) and wires
    a ``SkillBrokerEngine`` with ``simulation_engine=None`` and
    ``audit_writer=None``: governance runs, nothing executes, nothing is
    written. It REQUIRES ``validators_module``. A run directory records
    the agent config but not the ``custom_validators`` list the
    experiment wired in (``ExperimentBuilder.with_custom_validators``),
    and rebuilding the engine without them runs the irrigation domain
    with zero domain validators while every row still reports
    ``governance_evaluated=true`` — a verdict about a governance stack
    that was not there. If the registry is missing, this raises rather
    than falling back to parse-only silently.

    Residual (code-reviewer): pass ``snapshot`` — any one loaded snapshot
    from this run, it is only inspected, never replayed here — and a
    missing ``context["available_skills"]`` refuses right here, after the
    ``--validators-module`` check and before the ``skill_registry.yaml``
    check and the registry/engine construction that follows them,
    instead of only at the first ``replay_decision`` call. The CLI
    already has its snapshots loaded before it builds the decider, so
    this lets the refusal land alongside those two rather than after the
    (comparatively expensive) registry and engine construction has
    already run. It is deliberately checked AFTER ``--validators-module``
    — a missing flag is the simpler fix and should be the first thing a
    caller sees, not a second true-but-less-actionable refusal about a
    trace format limitation every run shares today. ``snapshot=None``
    (the default, and every direct caller that predates this parameter)
    skips this early check; the identical refusal in
    ``_SnapshotContextBuilder.build`` still fires on the first actual
    replay either way, because a run's snapshots can vary in which
    context keys survived the trace.
    """
    run_dir = Path(run_dir)
    manifest = _load_manifest(run_dir)
    resolved_model, model_source = resolve_model(run_dir, model, manifest=manifest)

    if agent_config is not None:
        config_path = Path(agent_config)
    else:
        recorded = manifest.get("agent_types_config")
        config_path = Path(recorded) if recorded else Path()
        if not config_path.is_file():
            config_path = run_dir / "config_snapshot.yaml"
    if not config_path.is_file():
        raise FileNotFoundError(
            f"No agent config for {run_dir}: the manifest points at "
            f"{manifest.get('agent_types_config')!r} (missing) and "
            f"{run_dir / 'config_snapshot.yaml'} does not exist either. "
            "Pass --agent-config explicitly."
        )

    # P2 (both reviewers): refuse BOTH replay paths for a config that
    # declares a non-LLM decider on any agent type, checked here — with
    # the config already loaded — so it guards the branch below
    # regardless of which one a caller reaches.
    #
    # The GOVERNANCE path (`_decide_with_engine`, reached under
    # `with_governance=True`) calls `SkillBrokerEngine.process_step`
    # without a `decider=` argument, so it always runs the row's
    # `llm_invoke` — never the rule table or parametric object that
    # actually produced a non-LLM row. Every row of a mixed-population
    # corpus would replay through the model and come back reading
    # `decider: llm`, silently wrong for whichever rows a rule or a
    # calibrated object decided.
    #
    # The PARSE-ONLY path (the default, `with_governance=False`) is no
    # safer for those same rows: it feeds the row's STORED PROMPT to the
    # model adapter as though an LLM produced the reply, which is
    # meaningless for a row a rule table decided from the agent's own
    # state and never read that prompt to produce at all.
    from broker.agents.deciders import DEFAULT_DECIDER_NAME
    from broker.utils.agent_config import AgentTypeConfig

    decider_config = AgentTypeConfig.load(str(config_path))
    declared_deciders = decider_config.declared_decider_names()
    if any(name != DEFAULT_DECIDER_NAME for name in declared_deciders):
        raise ValueError(
            "replay/ablation supports LLM-decided rows only; this config "
            f"declares deciders {declared_deciders} — filter the corpus to "
            "decider == 'llm' rows or drop --with-governance"
        )

    from broker.utils.model_adapter import get_adapter

    adapter = get_adapter(resolved_model, config_path=str(config_path))
    adapter.config_path = str(config_path)
    adapter.project_dir = config_path.parent

    if not with_governance:
        return ReplayDecider(model_adapter=adapter, source=str(config_path),
                             model=resolved_model, model_source=model_source)

    if not validators_module:
        raise ValueError(
            "--with-governance needs --validators-module. A run directory "
            "records its agent config but NOT the custom validators the "
            "experiment wired in through "
            "ExperimentBuilder.with_custom_validators() — irrigation passes "
            "irrigation_governance_validator, multi-agent flood passes its "
            "structural validators, and none of that reaches any artifact. "
            "Rebuilding SkillBrokerEngine from the run alone would replay "
            "with ZERO domain validators while every row reported "
            "governance_evaluated=true. Pass --validators-module <import "
            f"path> exposing {VALIDATORS_MODULE_CONTRACT} (return the same "
            "list the experiment passes), or drop --with-governance and read "
            "the proposal only."
        )

    if snapshot is not None and not snapshot.context.get("available_skills"):
        raise ValueError(
            "Governance replay needs the option set the agent was actually "
            "offered, and this trace does not record it. WAGF's audit "
            "writer does not persist context['available_skills'], so the "
            "rebuilt context has none, and "
            "SkillBrokerEngine._inject_filtered_skills then falls back to "
            "the domain's full action list — re-offering the one-way "
            "skills the live run had removed, so an agent is offered an "
            "irreversible action it has already taken. The validators "
            "would score that offer and inflate exactly the "
            "repeat-adoption term the project's IBR definition excludes. "
            "--with-governance is therefore unavailable until the audit "
            "writer records available_skills; run without it and read the "
            "proposal."
        )

    registry_path = config_path.parent / "skill_registry.yaml"
    if not registry_path.is_file():
        raise FileNotFoundError(
            f"Governance replay needs {registry_path}, which does not exist. "
            "A run directory records its agent config but not its skill "
            "registry, so the validators cannot be rebuilt from the run "
            "alone. Point --agent-config at the domain's config directory, "
            "or drop --with-governance and read the proposal only."
        )

    from broker.components.governance.registry import SkillRegistry
    from broker.validators import AgentValidator
    from broker.core.skill_broker_engine import SkillBrokerEngine

    registry = SkillRegistry()
    registry.register_from_yaml(str(registry_path))
    # Already loaded (and checked for a non-LLM decider) above; `.load()`
    # is a path-keyed cache, so re-fetching here would return the same
    # object anyway — reusing the variable just says so.
    config = decider_config

    # The live path takes this from the context builder
    # (experiment_builder.py: enable_financial_constraints=getattr(
    # ctx_builder, "enable_financial_constraints", False)). A run
    # directory has no context builder, so the config is the only
    # surviving declaration; it is read here rather than left at the
    # constructor default, which would silently drop the affordability
    # rules from a replay of a run that had them.
    raw_config = getattr(config, "_config", {}) or {}
    financial_constraints = bool(
        (raw_config.get("global_config", {}) or {})
        .get("governance", {}).get("financial_constraints", False)
    )
    validator = AgentValidator(
        config_path=str(config_path),
        enable_financial_constraints=financial_constraints,
    )
    custom_validators = load_custom_validators(validators_module, config)

    reg_skills = set(getattr(registry, "skills", {}) or {})
    if reg_skills:
        adapter.valid_skills = reg_skills

    engine = SkillBrokerEngine(
        skill_registry=registry,
        model_adapter=adapter,
        validators=[validator],
        simulation_engine=None,   # replay decides; it never advances a world
        context_builder=None,     # swapped per snapshot by ReplayDecider
        config=config,
        audit_writer=None,        # replay writes no audit rows
        custom_validators=custom_validators,
        domain_physical_dispatch=config.get_governance_physical_dispatch(),
    )
    return ReplayDecider(
        model_adapter=adapter, engine=engine, source=str(config_path),
        validators_source=(
            f"{validators_module}.build_custom_validators "
            f"({len(custom_validators)} custom validator(s)) + AgentValidator"
        ),
        financial_constraints=financial_constraints,
        model=resolved_model, model_source=model_source,
    )


# ─────────────────────────────────────────────────────────────────────
# Replay
# ─────────────────────────────────────────────────────────────────────

@dataclass
class ReplayResult:
    """One replayed decision: one snapshot, one factor, one arm, one seed."""

    snapshot_id: str
    agent_id: str
    year: int
    factor: str
    arm: str
    seed: Optional[int]
    replicate: int
    skill: Optional[str]
    executed_skill: Optional[str]
    parse_layer: Optional[str]
    validator_verdict: Optional[str]
    governance_evaluated: bool
    fidelity: str
    factor_present: bool
    n_matches: int
    mask_reason: str
    perturbation_chars: int
    prompt_diff: str
    raw_output: str
    seed_applied: bool
    action_stage: str
    decision_action: Optional[str]
    recorded_skill: Optional[str]
    matches_trace: Optional[bool]
    decider_called: bool = True
    error: Optional[str] = None

    @property
    def produced_no_decision(self) -> bool:
        """Was this a call that came back without a usable action?

        True only for rows where the decider actually ran. A row skipped
        because its factor was absent is not evidence about the backend.
        """
        if not self.decider_called:
            return False
        return self.decision_action is None or not (self.raw_output or "").strip()

    def to_row(self) -> Dict[str, Any]:
        row = asdict(self)
        row["prompt_diff"] = self.prompt_diff.replace("\n", "\\n")
        row["raw_output"] = self.raw_output.replace("\n", "\\n")
        return row


#: Per-SIDE clip for ``prompt_diff``. Each side is clipped independently
#: and says how much it dropped, so a long removal can never push the
#: replacement text out of the column — which is the half a reader needs
#: to confirm the mask put a sentence there rather than deleting one.
PROMPT_DIFF_SIDE_CHARS = 400


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return f"{text[:limit]}…[+{len(text) - limit} chars truncated]"


def _prompt_diff(before: str, after: str,
                 max_chars_per_side: int = PROMPT_DIFF_SIDE_CHARS) -> str:
    """What the mask removed and what it put there, as one line.

    Both halves are recorded: ``removed: … => added: …``. The two sides
    are clipped separately. The earlier single-string form clipped the
    joined diff at 400 characters, which meant a factor matching several
    long memory bullets spent the whole budget on the removed text and
    the row recorded no replacement at all — exactly the evidence needed
    to tell a substitution from a deletion.
    """
    if before == after:
        return ""
    removed: List[str] = []
    added: List[str] = []
    for line in difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        lineterm="", n=0, fromfile="baseline", tofile="arm",
    ):
        if line.startswith(("+++", "---")):
            continue
        if line.startswith("-"):
            removed.append(line[1:])
        elif line.startswith("+"):
            added.append(line[1:])
    return (f"removed: {_clip(' | '.join(removed), max_chars_per_side)}"
            f" => added: {_clip(' | '.join(added), max_chars_per_side)}")


def replay_decision(
    snapshot: DecisionSnapshot,
    mask: Optional[Set[str]] = None,
    control: Optional[str] = None,
    seed: Optional[int] = None,
    llm_invoke: Optional[Callable] = None,
    *,
    factor_map: Optional[FactorMap] = None,
    decider: Optional[ReplayDecider] = None,
    replicate: int = 0,
    action_stage: str = "proposed",
) -> ReplayResult:
    """Re-run one recorded decision with ``mask`` neutralised.

    ``mask`` names the factors to remove (``None`` or empty = the
    baseline arm). ``control="paraphrase"`` swaps the neutral rendering
    for the severity-matched control instead, which is the arm that makes
    a masked-arm effect interpretable.

    The decision goes through ``decider``, which is the production parse
    path and, when it was built with a governance engine, the production
    validator path too. Nothing here re-implements either.

    When the mask changes nothing — the factor is absent from this
    prompt, or the factor declares no control — the decider is NOT
    called. That arm's prompt would be byte-identical to the baseline
    already computed for this cell, so the call is a duplicate of a
    result the run holds; on a real backend it is also the single
    largest avoidable cost in the grid. The row is still written, with
    ``decider_called=False`` and the reason, so the cell is visible as
    skipped rather than absent.
    """
    if llm_invoke is None:
        raise ValueError("replay_decision needs an llm_invoke callable.")
    if decider is None:
        raise ValueError(
            "replay_decision needs a decider; build one with "
            "build_replay_decider(run_dir)."
        )
    if control not in (None, "paraphrase"):
        raise ValueError(
            f"Unknown control {control!r}; the only control arm is 'paraphrase'."
        )
    if action_stage == "executed" and not decider.governance_evaluated:
        raise ValueError(
            "action_stage='executed' needs a governance decider. Parse-only "
            "replay produces no executed action — nothing ran the validators, "
            "so there is no post-governance decision to compare against and "
            "every executed-stage distribution would be a column of "
            "'__unparsed__'."
        )

    factors = sorted(mask or ())
    if factors and factor_map is None:
        raise ValueError("Masking factors requires a factor_map.")

    arm = ARM_BASELINE
    if factors:
        arm = ARM_CONTROL if control == "paraphrase" else ARM_MASKED

    prompt = snapshot.prompt
    factor_present = True
    reason = ""
    perturbation = 0
    n_matches = 0
    any_applied = not factors
    for name in factors:
        spec = factor_map.get(name) if factor_map else None
        if spec is None:
            raise KeyError(
                f"Factor {name!r} is not declared by this domain. Declared: "
                f"{factor_map.names if factor_map else []}."
            )
        application = apply_mask(prompt, spec, arm)
        if not application.applied:
            factor_present = False
            reason = application.reason
            continue
        any_applied = True
        prompt = application.prompt
        perturbation += application.perturbation_chars
        n_matches += application.matches

    recorded = snapshot.reference_action(action_stage)

    if not any_applied:
        # S1: nothing was edited, so this arm's prompt is the baseline's.
        # Do not spend a decider call to learn that.
        return ReplayResult(
            snapshot_id=snapshot.snapshot_id,
            agent_id=snapshot.agent_id,
            year=snapshot.year,
            factor="+".join(factors),
            arm=arm,
            seed=seed,
            replicate=replicate,
            skill=None,
            executed_skill=None,
            parse_layer=None,
            validator_verdict=VERDICT_NOT_RUN,
            governance_evaluated=decider.governance_evaluated,
            fidelity=snapshot.fidelity,
            factor_present=False,
            n_matches=0,
            mask_reason=reason or "no factor applied to this prompt",
            perturbation_chars=0,
            prompt_diff="",
            raw_output="",
            seed_applied=False,
            action_stage=action_stage,
            decision_action=None,
            recorded_skill=recorded,
            matches_trace=None,
            decider_called=False,
            error=None,
        )

    result = decider.decide(snapshot, prompt, llm_invoke, seed)
    skill = result.get("skill")
    executed = result.get("executed_skill")
    decision_action = executed if action_stage == "executed" else skill

    # P1-c: "the trace recorded nothing" and "the replay reproduced the
    # trace" are different facts. Comparing None to None as equality made
    # a run where nothing was ever recorded report a perfect 1.0
    # reproduction rate.
    if arm != ARM_BASELINE or recorded is None:
        matches_trace = None
    else:
        matches_trace = decision_action == recorded

    return ReplayResult(
        snapshot_id=snapshot.snapshot_id,
        agent_id=snapshot.agent_id,
        year=snapshot.year,
        factor="+".join(factors) if factors else "",
        arm=arm,
        seed=seed,
        replicate=replicate,
        skill=skill,
        executed_skill=executed,
        parse_layer=result.get("parse_layer"),
        validator_verdict=result.get("validator_verdict"),
        governance_evaluated=bool(result.get("governance_evaluated")),
        fidelity=snapshot.fidelity,
        factor_present=factor_present,
        n_matches=n_matches,
        mask_reason=reason,
        perturbation_chars=perturbation,
        prompt_diff=_prompt_diff(snapshot.prompt, prompt),
        raw_output=result.get("raw_output") or "",
        seed_applied=bool(result.get("seed_applied")),
        action_stage=action_stage,
        decision_action=decision_action,
        recorded_skill=recorded,
        matches_trace=matches_trace,
        decider_called=True,
        error=result.get("error"),
    )


# ─────────────────────────────────────────────────────────────────────
# The determinism gate
# ─────────────────────────────────────────────────────────────────────

@dataclass
class DeterminismReport:
    """Whether this decider returns the same answer to the same question.

    The gate exists because a delta-P is a difference between two
    conditions. If replaying ONE condition twice already produces two
    answers, the difference between conditions is not attributable to the
    intervention. Ollama's gemma builds fail this at a fixed seed (Phase
    6R-D-4 measured a ~166-line diff between two identical-seed runs);
    the mock decider passes it trivially.

    Identity alone is not enough to pass. When the Ollama server is down,
    ``create_llm_invoke``'s invoke returns ``("", stats)`` after its
    retries, the parser returns ``None`` for empty text, and every replay
    comes back identical — identically empty. That is the most
    consistent backend imaginable and the least informative, so
    ``n_empty_raw`` and ``n_unparsed`` gate the verdict alongside
    ``k_identical``.
    """

    n: int
    k_identical: int
    verified: bool
    distinct_skills: List[Optional[str]]
    distinct_raw_outputs: int
    seed: Optional[int]
    seed_applied: bool
    n_empty_raw: int = 0
    n_unparsed: int = 0
    snapshot_ids: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def summary_line(self) -> str:
        tail = (f"; {self.n_empty_raw} empty reply/replies, "
                f"{self.n_unparsed} unparsed")
        if self.verified:
            return (f"deterministic: {self.k_identical} of {self.n} replays "
                    f"identical (skill and raw text){tail}")
        return (f"NON-deterministic: {self.k_identical} of {self.n} replays "
                f"identical (skill and raw text){tail}")


#: What the gate says when the replies agreed because there were no
#: replies. Named so the CLI, the tests and the guide quote one string.
EMPTY_BACKEND_NOTE = (
    "identical but not a decision — check the backend. Every replay came "
    "back empty or unparsable, which is what a stopped Ollama server looks "
    "like: create_llm_invoke returns ('', stats) after its retries and the "
    "parser returns None for empty text. Identical nothing is not evidence "
    "of a deterministic decider."
)


def determinism_check(
    snapshot: DecisionSnapshot,
    llm_invoke: Callable,
    n: int = 5,
    *,
    decider: Optional[ReplayDecider] = None,
    seed: Optional[int] = None,
) -> DeterminismReport:
    """Replay the UNMASKED snapshot ``n`` times and compare every output.

    Passing requires three things at once: every reply identical on both
    the parsed skill and the raw text; no reply empty; and at least one
    reply that parsed. A decider that returns the same action via
    different words is not deterministic — it merely happened to land in
    the same bucket. A decider that returns nothing at all, n times, is
    not deterministic either; it is unreachable.
    """
    if n < 2:
        raise ValueError("determinism_check needs n >= 2 to compare anything.")
    if decider is None:
        raise ValueError("determinism_check needs a decider.")

    skills: List[Optional[str]] = []
    raws: List[str] = []
    seed_applied = False
    for _ in range(n):
        outcome = decider.decide(snapshot, snapshot.prompt, llm_invoke, seed)
        skills.append(outcome.get("skill"))
        raws.append(outcome.get("raw_output") or "")
        seed_applied = bool(outcome.get("seed_applied"))

    pairs = list(zip(skills, raws))
    first = pairs[0]
    k_identical = sum(1 for pair in pairs if pair == first)
    n_empty_raw = sum(1 for raw in raws if not raw.strip())
    n_unparsed = sum(1 for skill in skills if skill is None)

    identical = k_identical == n
    verified = identical and n_empty_raw == 0 and n_unparsed < n

    if verified:
        note = ""
    elif identical:
        note = EMPTY_BACKEND_NOTE
    else:
        note = ("Same prompt, same seed, different output. No delta-P can be "
                "attributed to an intervention against this backend.")

    return DeterminismReport(
        n=n,
        k_identical=k_identical,
        verified=verified,
        distinct_skills=sorted({s for s in skills}, key=lambda v: (v is None, v)),
        distinct_raw_outputs=len(set(raws)),
        seed=seed,
        seed_applied=seed_applied,
        n_empty_raw=n_empty_raw,
        n_unparsed=n_unparsed,
        snapshot_ids=[snapshot.snapshot_id],
        note=note,
    )


def merge_determinism_reports(reports: Sequence[DeterminismReport]) -> DeterminismReport:
    """Combine per-snapshot checks into the run-level gate."""
    if not reports:
        return DeterminismReport(
            n=0, k_identical=0, verified=False, distinct_skills=[],
            distinct_raw_outputs=0, seed=None, seed_applied=False,
            note="No determinism check ran, so determinism is unestablished.",
        )
    total_n = sum(r.n for r in reports)
    total_k = sum(r.k_identical for r in reports)
    total_empty = sum(r.n_empty_raw for r in reports)
    total_unparsed = sum(r.n_unparsed for r in reports)
    verified = all(r.verified for r in reports)
    failing = [r.snapshot_ids[0] for r in reports if not r.verified and r.snapshot_ids]
    empty_only = (not verified
                  and all(r.k_identical == r.n for r in reports)
                  and (total_empty or total_unparsed == total_n))
    if verified:
        note = ""
    elif empty_only:
        note = EMPTY_BACKEND_NOTE
    else:
        note = (f"{len(failing)} of {len(reports)} snapshot(s) returned different "
                f"output for the same prompt and seed: {failing[:5]}")
    return DeterminismReport(
        n=total_n,
        k_identical=total_k,
        verified=verified,
        distinct_skills=sorted(
            {s for r in reports for s in r.distinct_skills},
            key=lambda v: (v is None, v),
        ),
        distinct_raw_outputs=sum(r.distinct_raw_outputs for r in reports),
        seed=reports[0].seed,
        seed_applied=any(r.seed_applied for r in reports),
        n_empty_raw=total_empty,
        n_unparsed=total_unparsed,
        snapshot_ids=[sid for r in reports for sid in r.snapshot_ids],
        note=note,
    )
