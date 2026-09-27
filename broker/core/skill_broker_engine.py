"""
Skill Broker Engine - Main orchestrator for Skill-Governed Architecture.

The Skill Broker retains the three-layer architecture:
  LLM Agent → Governed Broker → Simulation/World

Key changes from Action-based to Skill-based:
- LLM outputs SkillProposal (abstract behavior) instead of action/tool
- Broker validates skills through registry and validators
- Execution happens ONLY through simulation engine (system-only)

MCP Role (if used):
- MCP is ONLY for execution substrate (tool access, sandbox, logging)
- MCP does NOT participate in governance or decision-making
- MCP is NOT exposed to LLM agents

Validator pipeline (maps 1:1 to Nature Water Methods v4 six-step sequence):
  1. Schema validation          — AgentValidator schema check + registry schema
  2. Action legality            — AgentValidator + governance/type_validator
  3. Physical feasibility       — domain PHYSICAL checks run via custom_validators, OR (opt-in,
                                  default-OFF) registry dispatch in _run_validators when a config sets
                                  global_config.governance.dispatch_domain_physical (domain_physical_dispatch)
  4. Institutional compliance   — institutional/social/economic validators
                                  (grouped under one Methods step, three code labels)
  5. Magnitude plausibility     — numeric bounds, ADVISORY ONLY (execution resamples)
  6. Theory consistency         — thinking_validator + PMT/WSA-ACA built-ins

Retry termination (implemented in _retry_loop.py):
- Up to 3 revision attempts per proposal.
- Early exit when the SAME deterministic rule set blocks consecutive retries.
- On termination, registry default skill executes (maintain_demand for irrigation,
  do_nothing for flood), ensuring simulation advances.

Steps 1-4 and 6 are BINDING (rejection on failure). Step 5 is ADVISORY —
out-of-range magnitudes are corrected at execution time via bounded Gaussian
resampling rather than rejected. The audit trail records advisory flags
alongside binding rejections so reviewers can distinguish the two.
"""
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime

from ..interfaces.skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill, InterventionReport,
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from ..components.governance.registry import SkillRegistry
from ..utils.model_adapter import ModelAdapter
from ..validators import AgentValidator
from ..components.memory.engine import MemoryEngine
from ..components.context.builder import ContextBuilder, BaseAgentContextBuilder
from ..utils.agent_config import (
    GovernanceAuditor, load_agent_config,
    resolve_framework_aware_labels as _resolve_framework_aware_labels,
)
from ..components.analytics.interaction import InteractionHub
from ..components.analytics.audit import AuditWriter
from ..components.governance.retriever import SkillRetriever
from ..utils.logging import logger

from ._retry_loop import RetryMixin
from ._audit_helpers import (
    AuditMixin, _extract_construct_labels, _corrected_status_flag,
)
from ._advise import ADVISE_DENY as _ADVISE_DENY_IDS, demote
from ._advise_pass import AdviseMixin
from ._skill_filtering import SkillFilterMixin, assert_rendered_prompt_shows_options


def _reset_uncategorised_rules() -> None:
    """Clear the process-global uncategorised-rule tally for a new run.

    Imported lazily for the same reason ``_safe_rule_breakdown`` imports
    ``get_rule_breakdown`` lazily: the governance package imports core types, so
    a module-level import here would close a startup import cycle.

    Failure is caught because a side-artifact tally must never stop an engine
    from being built — but it is reported at WARNING, not swallowed: the
    consequence is a `rules_uncategorised_*` block in ``run_integrity.json``
    carrying a PREVIOUS run's rule ids alongside this one's, which is precisely
    the kind of plausible-but-wrong number this PR exists to remove.
    """
    try:
        from ..validators.governance import reset_uncategorised_rules

        reset_uncategorised_rules()
    except Exception as exc:  # pragma: no cover - governance import is present
        logger.warning(
            "[Audit] could not reset the uncategorised-rule tally (%s: %s); "
            "run_integrity.json's rules_uncategorised_* may include rule ids "
            "from an earlier run in this process.",
            type(exc).__name__, exc,
        )


class SkillBrokerEngine(RetryMixin, AdviseMixin, AuditMixin, SkillFilterMixin):
    """
    Skill-Governed Broker Engine.
    
    The Broker MUST:
    - Build bounded context (READ-ONLY)
    - Parse LLM output via ModelAdapter → SkillProposal
    - Validate skills through registry + validators
    - Produce ApprovedSkill (NOT execute directly)
    - Route to simulation engine for execution (SYSTEM-ONLY)
    - Write complete audit traces
    
    The Broker MUST NOT:
    - Make decisions (LLM does this)
    - Mutate state directly (Simulation does this)
    - Execute skills (Simulation does this)
    """
    
    def __init__(
        self,
        skill_registry: SkillRegistry,
        model_adapter: ModelAdapter,
        validators: List[AgentValidator],
        simulation_engine: Any,
        context_builder: Any,
        config: Optional[Any] = None,
        skill_retriever: Optional[SkillRetriever] = None,
        audit_writer: Optional[Any] = None,
        max_retries: int = 3,
        log_prompt: bool = False,
        custom_validators: Optional[List[Callable]] = None, # New parameter
        # opt-in registry PHYSICAL dispatch: a domain string (all agent types)
        # or an {agent_type: domain} mapping (per-agent-type routing, Wave 3)
        domain_physical_dispatch: Optional[Any] = None,
    ):
        self.skill_registry = skill_registry
        self.model_adapter = model_adapter
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.context_builder = context_builder
        self.config = config or load_agent_config()
        self.custom_validators = custom_validators or [] # Store custom validators
        # Opt-in (default None/OFF): when set, _run_validators also dispatches the
        # named domain's registry PHYSICAL checks. Keeps the registry physical path
        # usable in the simple ExperimentBuilder path without changing any frozen
        # domain (which leaves this None). See AgentTypeConfig.get_governance_physical_dispatch.
        self.domain_physical_dispatch = domain_physical_dispatch
        
        if skill_retriever:
            self.skill_retriever = skill_retriever
        else:
            global_skills = self.config.get_global_skills("default")
            full_disclosure = self.config.get_full_disclosure_agent_types()
            # Phase 6H Item 3: top_n / min_score resolved from
            # DomainPack.retrieval_policy() + YAML governance.retrieval,
            # falling back to framework defaults (top_n=3, min_score=0.05).
            retrieval_cfg = self.config.get_retrieval_config()
            self.skill_retriever = SkillRetriever(
                top_n=retrieval_cfg.get("top_n", 3),
                min_score=retrieval_cfg.get("min_score", 0.05),
                global_skills=global_skills,
                full_disclosure_agent_types=full_disclosure
            )
            
        # PR-4 (D7): reset the parsing-flag warn-once set per engine. The set
        # exists so a raising or non-bool `get_parsing_strict_layers` is
        # reported once instead of once per decision; without this reset a
        # SECOND run in the same process (a batch loop, a test session) is told
        # nothing at all, and "the flag silently read OFF" is exactly the
        # failure the warning exists to surface. Import is local and guarded:
        # a caller may have swapped in an adapter module that does not define
        # it, and an engine must not fail to construct over a log-dedup set.
        # PR-3's sibling `_audit_helpers._FLAG_WARNED` has the identical
        # per-process dedup shape and the identical reason to reset here, so
        # it rides the same try block.
        try:
            from ..utils.parsing.unified_adapter import _PARSING_FLAG_WARNED
            _PARSING_FLAG_WARNED.clear()
            from ._audit_helpers import _FLAG_WARNED
            _FLAG_WARNED.clear()
        except ImportError:  # pragma: no cover - defensive
            pass

        self.audit_writer = audit_writer
        self.max_retries = max_retries if max_retries != 3 else self.config.get_governance_retries(max_retries)
        self.max_reports = self.config.get_governance_max_reports()
        self.log_prompt = log_prompt

        # P0-1c: resolve the ADVISE arm spec ONCE into immutable instance state.
        # getattr-guarded because tests and alternate config objects predate these
        # getters (same defensive idiom as the audit flags). Never written to during
        # process_step -- the engine is shared across a ThreadPoolExecutor.
        _get_advise = getattr(self.config, "get_governance_advise", None)
        _spec = _get_advise() if callable(_get_advise) else None
        # Coerced, not trusted: a MagicMock config returns a truthy Mock here, and a
        # Mock supports __getitem__, so `_spec["mode"]` would yield another Mock that
        # compares False against every mode string -- silently taking a branch nobody
        # chose. Only a genuine dict with a known mode counts as configured.
        _VALID_MODES = ("off", "advise", "placebo", "resample", "wrapper")
        if isinstance(_spec, dict) and _spec.get("mode") in _VALID_MODES:
            self._advise_spec = _spec
            self._advise_mode = _spec["mode"]
        else:
            self._advise_spec = None
            self._advise_mode = "off"
        # Belt-and-braces against the control-arm footgun: the config getter already
        # forces rule_ids=[] when mode="off", and this re-asserts it here so a
        # hand-built spec (tests, programmatic callers) cannot demote rules in a
        # mode that never issues the advisory call -- which would silently strip
        # enforcement while telling the model nothing.
        self._advise_rule_ids = (
            frozenset(self._advise_spec["rule_ids"])
            if (self._advise_spec and self._advise_mode != "off") else frozenset()
        )
        # Coerced for the same reason as _on_retry_exhausted below: a MagicMock
        # config returns a Mock from this getter, which would then reach
        # format_intervention_prompt and raise mid-run rather than degrading.
        _get_framing = getattr(self.config, "get_governance_intervention_framing", None)
        _framing = _get_framing() if callable(_get_framing) else "legacy"
        self._intervention_framing = _framing if _framing in ("legacy", "neutral") else "legacy"
        # `bool(MagicMock())` is True, so a bare-Mock config would silently switch
        # per-decision call counting on. Require a real bool.
        _get_acols = getattr(self.config, "get_audit_advise_columns", None)
        _acols = _get_acols() if callable(_get_acols) else False
        self._count_llm_calls = _acols if isinstance(_acols, bool) else False
        # Retry-exhaustion policy (model-builder choice; see the getter's docstring).
        # COERCED to a known string rather than stored raw: tests build this engine
        # with MagicMock configs, and a Mock is truthy and compares unequal to any
        # string, so an unrecognised value must degrade to "default" here and every
        # branch below must test POSITIVELY for "keep_proposal".
        _get_ore = getattr(self.config, "get_governance_on_retry_exhausted", None)
        _ore = _get_ore() if callable(_get_ore) else "default"
        self._on_retry_exhausted = _ore if _ore in ("default", "keep_proposal") else "default"
        # PR-6: the SOFT-RULE channel (off | record | feedback). Distinct from
        # `_advise_mode` above, which is the P0-1c arm spec that DEMOTES rules
        # authored as ERROR. This one governs rules already authored as WARNING.
        # Coerced to a known string for the same MagicMock reason as the rest.
        _get_soft = getattr(self.config, "get_governance_advise_mode", None)
        _soft = _get_soft() if callable(_get_soft) else "off"
        self._soft_advise_mode = _soft if _soft in ("off", "record", "feedback") else "off"
        # Red-team objection 3: the RETRY-FEEDBACK ablation (full | placebo |
        # silent, default full). Governs ONLY the LLM-facing text of the
        # BLOCKING governance retry loop (`RetryMixin._governance_retry_loop`)
        # -- the validator still decides WHEN a proposal is rejected (same
        # rules, same schedule, same `on_retry_exhausted` fallback); under
        # "placebo" the retry prompt is the adapter's wrapper-only rendering
        # (header + closer + original prompt, no rules block --
        # `format_intervention_prompt(..., include_reports=False)`, opus W1
        # design), isolating "the model got another attempt with the same
        # governance framing" from "the model was told a specific rule".
        # Under "silent" the retry prompt is the ORIGINAL prompt, byte for
        # byte, on every attempt -- no header, no closer, no framing at all --
        # a strictly more content-free control than "placebo".
        # Distinct from `_advise_mode` / `_soft_advise_mode` above, which
        # govern the separate NON-BLOCKING advisory channel and share no
        # state with this one, including their OWN, differently-mechanised
        # `mode="placebo"` (same-shape reports, placebo text) which this is
        # not. Coerced to a known string for the same MagicMock reason as the
        # rest.
        # Feasible-set line on every ERROR retry (default OFF). Coerced to a
        # real bool for the same MagicMock reason as the rest: bool(Mock()) is
        # True and would switch probing on in every mocked test.
        _get_fsf = getattr(self.config, "get_governance_feasible_set_feedback", None)
        _fsf = _get_fsf() if callable(_get_fsf) else False
        self._feasible_set_feedback = _fsf if isinstance(_fsf, bool) else False
        # Resolved here (config-getter coercion for the same MagicMock reason
        # as the rest of __init__), then applied through set_retry_feedback_mode
        # below so construction and a later CLI override (run_flood.py /
        # run_experiment.py's --retry-feedback-mode) go through the SAME path
        # and both get the W2 advisory-conflict check, not just construction.
        _get_rfm = getattr(self.config, "get_governance_retry_feedback_mode", None)
        _rfm = _get_rfm() if callable(_get_rfm) else "full"
        self.set_retry_feedback_mode(
            _rfm if _rfm in ("full", "placebo", "silent") else "full"
        )
        # PR-6 review P1-b: FRAMEWORK-AWARE LABELS parity. Two evaluators read
        # this flag from two places — AgentValidator from the config object it
        # was constructed with, the ThinkingValidator from whatever the
        # dispatcher resolved — and before this check they could disagree
        # silently, so one evaluator recorded a `construct_missing` WARNING for a
        # construct the other fabricated as "M" and fired on. State the resolved
        # value once per engine and say so loudly when the two do not match.
        self._framework_aware_labels = _resolve_framework_aware_labels(self.config)
        self._log_framework_aware_label_parity()
        # PR-3: opt-in corrected status/truth columns. Resolved once, coerced to
        # a real bool for the same reason as _count_llm_calls above.
        self._corrected_status_columns = _corrected_status_flag(self.config)
        # P1e: state the RESOLVED value once per engine. The flag fails closed
        # by design, so "I set it in YAML" and "it never reached the engine"
        # produce identical artifacts unless the engine says which happened.
        logger.info(
            "[Audit] corrected_status_columns=%s "
            "(ON adds execution_path, corrects fallback_activated / rules_*_hit "
            "/ mem_top_*, and writes a row for aborted steps)",
            self._corrected_status_columns,
        )
        # P2d: sentinel rows that could not be written. Surfaced in
        # run_integrity.json — a failed sentinel write is a missing row, which
        # is the same denominator hole the sentinel exists to close.
        self._audit_sentinel_write_failures = 0
        # C1: the uncategorised-rule tally is a module global, so a second run
        # in the same interpreter (a seed sweep driven from one script) would
        # otherwise report the FIRST run's rule ids as well as its own. Cleared
        # here, next to the counter above, because engine construction is the
        # one point every run passes through exactly once.
        _reset_uncategorised_rules()
        # PR-6 P1-a: same reasoning for the world-rule evaluability tally — a
        # seed sweep in one interpreter would otherwise carry the first run's
        # unevaluable-row count into the second run's run_integrity.json.
        try:
            from broker.core.run_integrity import reset_world_rule_evaluability

            reset_world_rule_evaluability()
        except Exception as exc:  # noqa: BLE001 — side-artifact tally only
            logger.debug(f"[Integrity] world-rule tally reset skipped: {exc}")
        # PR-8: same reasoning for the per-decider row census.
        try:
            from broker.core.run_integrity import (
                reset_decider_row_counts, set_declared_deciders,
            )

            reset_decider_row_counts()
            # P1-b: the census can only see an arm that produced a row.
            # Record what the CONFIG asked for, here, where the config
            # object is in hand — that is the only way run_integrity can
            # report an arm that produced NONE, which is the failure a
            # mixed-population CSV cannot show on its own. Recorded only
            # when the columns are on, so a plain all-LLM run leaves the
            # keys absent exactly as before.
            _dflag = getattr(self.config, "get_audit_decider_columns", None)
            _dnames = getattr(self.config, "declared_decider_names", None)
            if callable(_dflag) and callable(_dnames) and _dflag() is True:
                set_declared_deciders(_dnames())
        except Exception as exc:  # noqa: BLE001 — side-artifact census only
            logger.debug(f"[Integrity] decider census reset skipped: {exc}")


        self.stats = {
            "total": 0,
            "approved": 0,
            "retry_success": 0,
            "rejected": 0,
            "aborted": 0
        }
        self.auditor = GovernanceAuditor()

    def set_retry_feedback_mode(self, mode: str) -> None:
        """Set the red-team objection 3 retry-feedback arm (full | placebo |
        silent) and re-run the W2 advisory-conflict check against the NEW
        value.

        Called from __init__ with the config-resolved default, so behaviour
        is identical to before this method existed when no override is
        given. ALSO called directly by a CLI override
        (examples/single_agent/run_flood.py,
        examples/irrigation_abm/run_experiment.py's --retry-feedback-mode)
        instead of those callers poking `self._retry_feedback_mode` on the
        already-built engine -- doing that bypassed the warning below
        entirely, so an operator overriding to "silent"/"placebo" on a run
        with an advisory channel already on got no warning at all, unlike a
        run where the same combination was set in YAML from the start.

        Raises ValueError on an unrecognised mode: unlike __init__'s own
        config-getter coercion (a MagicMock config's return value silently
        degrades to "full" so unit tests with mocked configs never take an
        unintended branch), a caller of this PUBLIC method is passing a
        literal string on purpose, so an unrecognised one is refused loudly
        rather than silently reinterpreted as "full".
        """
        if mode not in ("full", "placebo", "silent"):
            raise ValueError(
                f"retry_feedback_mode={mode!r} is not 'full', 'placebo', or "
                "'silent'."
            )
        self._retry_feedback_mode = mode
        logger.info("[Governance] retry_feedback_mode=%s", self._retry_feedback_mode)
        # W2 (review round 2): a placebo/silent retry arm exists to isolate
        # rule content from "another attempt", but if the ADVISE channel
        # (demoted ERROR rules, `_advise_mode`) or the SOFT-RULE channel
        # (WARNING rules under `feedback`, `_soft_advise_mode`) is also live,
        # either one can still put rule-specific content into a DIFFERENT
        # prompt within the same decision (the one-shot advisory call),
        # quietly reintroducing exactly the content this arm exists to
        # remove and making a "placebo"/"silent" corpus not actually
        # content-free. Named here so the operator sees which attribute(s)
        # are the conflict, at every point the resolved mode changes.
        if self._retry_feedback_mode in ("placebo", "silent") and (
            self._advise_mode != "off" or self._soft_advise_mode != "off"
        ):
            logger.warning(
                "[Governance] retry_feedback_mode=%s while _advise_mode=%r "
                "and/or _soft_advise_mode=%r is not 'off', the retry PROMPT is "
                "content-free, but an advisory call from either channel can "
                "still show this decision rule-specific content in a "
                "DIFFERENT prompt within the same decision. A published "
                "%r corpus meant to be content-free end-to-end should "
                "set both to 'off'.",
                self._retry_feedback_mode, self._advise_mode, self._soft_advise_mode,
                self._retry_feedback_mode,
            )

    def _log_framework_aware_label_parity(self) -> None:
        """PR-6 P1-b: state the resolved flag once, and name any disagreement.

        Two evaluators answer "the model did not report this construct"
        differently unless they read the same flag: ``AgentValidator`` records a
        ``construct_missing`` WARNING and does not fire; ``ThinkingValidator``
        with the flag OFF fabricates ``"M"`` and fires. Half-wiring the flag
        therefore does not produce a half-fixed run — it produces a run where
        the two disagree about the SAME rule on the SAME decision, with nothing
        in the audit trail saying so. Log-only: this must never stop an engine
        from being built, and the mismatch is a configuration problem the
        operator has to see, not an exception mid-batch.
        """
        try:
            engine_value = bool(self._framework_aware_labels)
            dispatch_value = _resolve_framework_aware_labels(None)
            seen = {"engine/AgentValidator": engine_value,
                    "dispatch/ThinkingValidator": dispatch_value}
            for v in getattr(self, "validators", None) or []:
                if hasattr(v, "framework_aware_labels"):
                    seen[f"validator:{type(v).__name__}"] = bool(
                        v.framework_aware_labels)
            if len(set(seen.values())) > 1:
                logger.warning(
                    "[Validators] validators.framework_aware_labels DISAGREES "
                    "across evaluators: %s. The two condition evaluators then "
                    "answer a missing construct differently on the same "
                    "decision — one records construct_missing and does not "
                    "fire, the other assumes 'M' and fires. Load one config, or "
                    "pass the flag explicitly to build_domain_validators().",
                    seen,
                )
            elif engine_value:
                logger.info(
                    "[Validators] framework_aware_labels=True (labels resolve "
                    "against the agent type's registered alphabet; a missing "
                    "construct records construct_missing and never assumes a "
                    "middle value)")
        except Exception as exc:  # noqa: BLE001 — a log must not break construction
            logger.debug(f"[Validators] framework-aware parity check skipped: {exc}")

    def process_step(
        self,
        agent_id: str,
        step_id: int,
        run_id: str,
        seed: int,
        llm_invoke: Callable[[str], str],
        agent_type: str = "default",
        env_context: Dict[str, Any] = None,
        decider: Optional[str] = None,
        render_check: bool = True,
    ) -> SkillBrokerResult:
        """
        Process one complete decision step through skill governance.

        Flow:
        ① Build bounded context (READ-ONLY)
        ② LLM output → ModelAdapter → SkillProposal
        ③ Skill validation (registry + validators)
        ④ ApprovedSkill creation
        ⑤ Execution (simulation engine ONLY)
        ⑥ Audit trace

        ``llm_invoke`` has never been required to be an LLM — step ② is
        "whatever this callable returns, parsed and validated" and has
        been since the first version. PR-8 names that: ``decider`` is the
        registered name of what ``llm_invoke`` actually is, recorded on
        the audit row so a rule-based agent and a model-driven one are
        distinguishable in the CSV while going through identical
        validation. ``None`` means the default, ``"llm"``.

        ``render_check`` (round 5, 2026-09): gates the options-text
        parity POST-RENDER assertion (``assert_rendered_prompt_shows_options``)
        that runs right after step ②'s prompt is built. Default ``True``
        for every live call — this is the check that catches a prompt
        template whose ``{options_text}``/name-based legend never
        actually rendered (e.g. the ``BaseAgentContextBuilder`` +
        ``{options_text}`` gap ``examples/cat_model/run_cat.py`` had).
        ``broker/experiments/replay.py`` passes ``render_check=False`` —
        LOAD-BEARING, not belt-and-braces: replay feeds a RECORDED
        prompt from a PAST run into a freshly rebuilt engine, whose
        ``dynamic_skill_map`` is reconstructed independently right now,
        and the check only accepts an exact ``options_text`` match or
        every skill id present by name (round 6 removed an earlier
        shape/arity path that used to tolerate a differently-worded
        historical menu of the same size — it was unsound, see
        ``_skill_filtering.py``). Without this opt-out a replayed prompt
        whose label wording no longer matches today's rendering would
        fail the check even though nothing is actually wrong. Correct
        here regardless: replay's entire point is re-validating an
        already-happened decision against today's governance rules, not
        re-proving that some earlier run's rendering pipeline worked.
        """
        self.stats["total"] += 1
        timestamp = datetime.now().isoformat()

        # PR-8: a hybrid decider records per call which path answered.
        # Cleared here so a value left by the PREVIOUS agent on this
        # thread can never be attributed to this row.
        try:
            from broker.agents.deciders import DEFAULT_DECIDER_NAME, clear_decider_path
            clear_decider_path()
            decider = decider or DEFAULT_DECIDER_NAME
        except Exception:  # noqa: BLE001 — provenance must not break a step
            decider = decider or "llm"

        # ① Build bounded context (READ-ONLY)
        context = self.context_builder.build(agent_id, step_id=step_id, run_id=run_id, env_context=env_context)
        self._inject_filtered_skills(context, agent_type)
        context_hash = self._hash_context(context)

        # Phase 28: Dynamic Skill Retrieval (RAG)
        # Re-alignment: Only apply RAG for advanced engines (Hierarchical, Importance, HumanCentric)
        # to maintain parity for the baseline WindowMemoryEngine benchmarks.
        should_rag = self.skill_retriever and context.get("available_skills")
        if should_rag:
            from broker.components.memory.engine import WindowMemoryEngine
            # Safely check for WindowMemoryEngine to maintain legacy parity
            mem_engine = getattr(self.context_builder, 'memory_engine', None)
            if not mem_engine and hasattr(self.context_builder, 'hub'):
                mem_engine = getattr(self.context_builder.hub, 'memory_engine', None)
            
            if isinstance(mem_engine, WindowMemoryEngine):
                should_rag = False
        
        if should_rag:
            raw_skill_ids = context["available_skills"]
            # Convert IDs to full definitions for retriever
            eligible_skills = []
            for sid in raw_skill_ids:
                s_def = self.skill_registry.get(sid)
                if s_def:
                    eligible_skills.append(s_def)
            
            # Retrieve top relevant skills
            retrieved_skills = self.skill_retriever.retrieve(context, eligible_skills)
            logger.debug(f" [RAG] Retrieved {len(retrieved_skills)} relevant skills for {agent_id}")
            
            # Update context with retrieved skill IDs
            context["available_skills"] = [s.skill_id for s in retrieved_skills]
            # Also store full definitions for ContextBuilder to show descriptions if needed
            context["retrieved_skill_definitions"] = retrieved_skills
            self._inject_options_text(
                context, [s.skill_id for s in retrieved_skills], agent_type=agent_type,
            )

        # Robust memory extraction for audit (handles nesting and stringification)
        raw_mem = context.get("memory")
        if raw_mem is None and "personal" in context:
            raw_mem = context["personal"].get("memory")
            
        if isinstance(raw_mem, str):
            # Convert bulleted string back to list for cleaner JSON logs
            memory_pre = [m.lstrip("- ").strip() for m in raw_mem.split("\n") if m.strip()]
        else:
            memory_pre = list(raw_mem).copy() if raw_mem else []
        
        # ② LLM output → ModelAdapter → SkillProposal (with retry for empty/failed parse)
        prompt = self.context_builder.format_prompt(context)
        # Post-render options-text parity check (2026-09, round 4): every
        # check upstream (_assert_options_text_parity et al.) verifies the
        # un-rendered TEMPLATE STRING, not what actually made it into
        # `prompt` above — a legend delivered through some OTHER filled
        # placeholder is invisible to a template-only scan. This is the
        # single point every rendered prompt in this broker passes
        # through, right before the model sees it. `render_check=False`
        # (round 5) is replay.py's documented opt-out — see this
        # method's docstring for why.
        if render_check:
            _personal_for_render_check = context.get("personal", {}) if isinstance(context, dict) else {}
            assert_rendered_prompt_shows_options(
                agent_type,
                prompt,
                _personal_for_render_check.get("dynamic_skill_map"),
                _personal_for_render_check.get("options_text"),
            )
        else:
            # Round 6: make a skipped check countable, not just inferable
            # from the `replay_` run_id prefix convention — surfaced as
            # run_integrity.json's `render_check_skipped_rows` (absent,
            # not zero, on every non-replay run).
            try:
                from broker.core.run_integrity import note_render_check_skipped
                note_render_check_skipped()
            except Exception as exc:  # noqa: BLE001 — a side counter must not break a step
                logger.debug(f"[Integrity] render_check_skipped tally skipped: {exc}")
        skill_proposal, raw_output, format_retry_count, total_llm_stats = (
            self._invoke_llm_with_retries(prompt, llm_invoke, context, agent_id, agent_type, env_context)
        )

        if skill_proposal is None:
            self.stats["aborted"] += 1
            self.auditor.log_parse_error()
            if format_retry_count > 0:
                self.auditor.log_structural_fault_terminal(format_retry_count)
            logger.error(f" [LLM:Error] Model returned unparsable output after retries for {agent_id}.")
            # PR-3: this early return skips the single _write_audit_trace call
            # site below, so pre-PR-3 an unparsable step left NO row in either
            # the JSONL or the CSV — the arm with more parse failures silently
            # ran a smaller denominator. Under corrected_status_columns a
            # sentinel row conserves the agent x year count instead.
            if self.audit_writer and self._corrected_status_columns:
                self._write_aborted_sentinel_trace(
                    agent_type=agent_type, run_id=run_id, step_id=step_id,
                    timestamp=timestamp, env_context=env_context, seed=seed,
                    agent_id=agent_id, raw_output=raw_output,
                    format_retry_count=format_retry_count,
                    # P1b: the real call is still in scope here. Without these
                    # the sentinel row would report a successful zero-token
                    # call that retrieved no memories — a fabricated
                    # measurement on the one row created to make a failure
                    # visible.
                    llm_stats=total_llm_stats,
                    memory_pre=memory_pre,
                    prompt=prompt,
                    # PR-4 (D6): the parser's own account of why this step
                    # never produced a decision. Empty unless
                    # parsing.strict_layers is on, in which case the sentinel
                    # is the only row that can carry it.
                    parsing_warnings=list(
                        getattr(self.model_adapter, "last_parse_warnings", None) or []
                    ),
                    # PR-8: the sentinel carries the same decider columns as
                    # every other row, so a mixed-population CSV has one
                    # column set rather than two.
                    decider=decider,
                )
            return self._create_result(SkillOutcome.ABORTED, None, None, None, ["Parse error after retries"], format_retries=format_retry_count)

        if format_retry_count > 0:
            self.auditor.log_structural_fault_resolved(format_retry_count)
            logger.info(f" [Broker:StructuralFault] {format_retry_count} format issue(s) fixed by retry for {agent_id}")

        # ③ Skill validation
        # Standardization (Phase 9/12): Decouple domain-specific keys
        if env_context is None:
            env_context = {}

        flat_state = context.get("state", {})
        flat_env = env_context

        # Diagnostic: warn on key collisions between agent state and env context
        if __debug__:
            collisions = set(flat_state.keys()) & set(flat_env.keys())
            if collisions:
                logger.warning(
                    f"[Governance:Diagnostic] Key collision in validation context: "
                    f"{collisions}. env_context takes precedence. "
                    f"Consider using distinct key names."
                )

        validation_context = {
            "agent_state": context,
            "agent_type": agent_type,
            "env_state": env_context,  # The "New Standard" source of truth
            **flat_state,              # Flatten agent state for custom validators
            **flat_env,                # Flat injection for legacy validator lookups
        }

        # Inject proposed magnitude into validation context (activates magnitude_cap_check)
        if skill_proposal and skill_proposal.magnitude_pct is not None:
            validation_context["proposed_magnitude"] = skill_proposal.magnitude_pct
        # 6W-B4: parallel lift of the multi-field setpoint dict (activates
        # ParameterBoundsValidator). Frozen domains carry parameters=={} -> key never
        # added -> validation_context byte-identical; proposed_magnitude path unchanged.
        if skill_proposal and skill_proposal.parameters:
            validation_context["proposed_parameters"] = dict(skill_proposal.parameters)

        validation_results = self._run_validators(skill_proposal, validation_context)
        all_validation_history = list(validation_results)
        all_valid = all(v.valid for v in validation_results)
        
        # Track initial errors for audit summary
        initial_rule_ids = set()
        for v in validation_results:
            initial_rule_ids.update(v.metadata.get("rules_hit", []))
        
        # Diagnostic summary for User
        if self.log_prompt:
            reasoning = skill_proposal.reasoning or {}
            label_parts = []
            
            # Dynamic Label Extraction from reasoning
            # Try to get labels (config-driven)
            if self.config:
                log_fields = self.config.get_log_fields(agent_type)
                for field_name in log_fields:
                    val = None
                    # Try various casing and suffix variants
                    for variants in [field_name, field_name.upper(), f"{field_name}_LABEL", field_name.capitalize(), field_name.lower()]:
                        if variants in reasoning:
                            val = reasoning[variants]
                            break
                    if val:
                        label_parts.append(f"{field_name}: {val}")
            
            # Legacy Fallback for Strategy/Confidence if not in log_fields
            if not any("Strategy" in p for p in label_parts) and "Strategy" in reasoning:
                label_parts.append(f"Strategy: {reasoning['Strategy']}")
            if not any("Confidence" in p for p in label_parts) and "Confidence" in reasoning:
                label_parts.append(f"Confidence: {reasoning['Confidence']}")

        # Log initial validation failure (before retry loop) for diagnostic clarity
        if not all_valid:
            initial_errors = [e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors]
            choice_name = skill_proposal.skill_name if skill_proposal else "parsing_failed"
            logger.warning(f" [Governance:Initial] {agent_id} | Choice: '{choice_name}' | Validation FAILED | Errors: {initial_errors}")

        # Log WARNING-level observations (non-blocking)
        for v in validation_results:
            if v.valid and hasattr(v, 'warnings') and v.warnings:
                logger.info(f" [Governance:Warning] {agent_id} | {v.warnings[0]}")

        # P0-1a: snapshot the FIRST proposal before the retry loop reassigns
        # `skill_proposal`. Cheap and unconditional (two locals); the values are
        # only written to the trace when the initial_proposal_columns flag is ON,
        # so flag-OFF runs stay byte-identical.
        initial_skill = skill_proposal.skill_name if skill_proposal else None
        initial_labels = _extract_construct_labels(skill_proposal)
        attempt_skills: List[Optional[str]] = [initial_skill]
        # One group per failed attempt, filled by the retry loop only when
        # feasible_set_feedback is on (then surfaced as an audit column).
        feasible_by_attempt: Optional[List[List[str]]] = (
            [] if self._feasible_set_feedback else None
        )

        # P0-1c: the single-shot advisory pass. No-op (returns its inputs, zero LLM
        # calls) unless an arm config declares global_config.governance.advise. Runs
        # BEFORE the retry loop so the advisory prompt is built from the same
        # attempt-0 proposal and the same reports arm C's first retry uses.
        skill_proposal, raw_output, validation_results, all_valid, advise_info = (
            self._advisory_pass(
                all_valid=all_valid, skill_proposal=skill_proposal,
                validation_results=validation_results,
                all_validation_history=all_validation_history,
                validation_context=validation_context,
                prompt=prompt, llm_invoke=llm_invoke, context=context,
                agent_id=agent_id, agent_type=agent_type,
                env_context=env_context, raw_output=raw_output,
                total_llm_stats=total_llm_stats,
                attempt_skills=attempt_skills,
            )
        )

        # PR-6: the SOFT-RULE channel. No-op (returns its inputs and an EMPTY info
        # dict, zero LLM calls) unless a config sets
        # global_config.governance.advise_mode. Runs after the P0-1c advisory pass
        # so `record` reports the findings of whatever proposal is actually going
        # into the retry loop, and before that loop so `feedback`'s advice reaches
        # the model while the decision is still open.
        skill_proposal, raw_output, validation_results, all_valid, soft_advise_info = (
            self._soft_rule_pass(
                all_valid=all_valid, skill_proposal=skill_proposal,
                validation_results=validation_results,
                all_validation_history=all_validation_history,
                validation_context=validation_context,
                prompt=prompt, llm_invoke=llm_invoke, context=context,
                agent_id=agent_id, agent_type=agent_type,
                env_context=env_context, raw_output=raw_output,
                total_llm_stats=total_llm_stats,
                attempt_skills=attempt_skills,
            )
        )

        # Governance retry loop
        skill_proposal, raw_output, validation_results, all_validation_history, all_valid, retry_count = (
            self._governance_retry_loop(
                all_valid=all_valid, skill_proposal=skill_proposal,
                validation_results=validation_results,
                all_validation_history=all_validation_history,
                validation_context=validation_context,
                prompt=prompt, llm_invoke=llm_invoke, context=context,
                agent_id=agent_id, agent_type=agent_type,
                env_context=env_context, raw_output=raw_output,
                total_llm_stats=total_llm_stats,
                attempt_skills=attempt_skills,
                feasible_by_attempt=feasible_by_attempt,
            )
        )

        # ④ Create ApprovedSkill or use fallback
        approved_skill, outcome = self._build_approved_skill(
            all_valid=all_valid, skill_proposal=skill_proposal,
            agent_id=agent_id, agent_type=agent_type,
            retry_count=retry_count, validation_results=validation_results,
            initial_rule_ids=initial_rule_ids,
        )
        
        # FINAL STEP SUMMARY (Console)
        if retry_count > 0:
             pass # Already logged success above
        
        # ④b Multi-skill: validate + build secondary (if enabled)
        secondary_proposal = None
        secondary_approved = None
        secondary_execution = None
        composite_errors = []
        ms_cfg = self.config.get_multi_skill_config(agent_type) if self.config else {}
        if ms_cfg and skill_proposal and all_valid:
            sec_skill = skill_proposal.reasoning.get("_secondary_skill_name")
            sec_mag = skill_proposal.reasoning.get("_secondary_magnitude_pct")
            if sec_skill:
                secondary_proposal = SkillProposal(
                    skill_name=sec_skill,
                    agent_id=agent_id,
                    reasoning={"_source": "secondary"},
                    magnitude_pct=sec_mag,
                )
                # Composite conflict check
                comp_result = self.skill_registry.check_composite_conflicts(
                    [skill_proposal.skill_name, sec_skill]
                )
                if not comp_result.valid:
                    composite_errors.extend(comp_result.errors)
                    logger.warning(f" [Multi-Skill] {agent_id} | Composite conflict: {comp_result.errors}")
                    secondary_proposal = None  # Drop conflicting secondary
                elif sec_skill == skill_proposal.skill_name:
                    composite_errors.append(f"Primary and secondary are the same: '{sec_skill}'")
                    secondary_proposal = None
                else:
                    # Validate secondary individually. F5 (2026-06-10): against
                    # the SECONDARY's own magnitude — validation_context still
                    # holds the primary's, so magnitude caps never applied to
                    # secondaries pre-fix. Copy, don't mutate (the primary's
                    # context must stay intact for the retry loop).
                    sec_context = dict(validation_context)
                    if sec_mag is not None:
                        sec_context["proposed_magnitude"] = sec_mag
                    else:
                        sec_context.pop("proposed_magnitude", None)
                    # 6W-B4: secondary's own setpoint dict (not the primary's, copied above)
                    if secondary_proposal and secondary_proposal.parameters:
                        sec_context["proposed_parameters"] = dict(secondary_proposal.parameters)
                    else:
                        sec_context.pop("proposed_parameters", None)
                    sec_validation = self._run_validators(
                        secondary_proposal, sec_context
                    )
                    sec_valid = all(v.valid for v in sec_validation if v)
                    if sec_valid:
                        sec_params = {}
                        if sec_mag is not None:
                            sec_params["magnitude_pct"] = sec_mag
                        secondary_approved = ApprovedSkill(
                            skill_name=sec_skill,
                            agent_id=agent_id,
                            approval_status="APPROVED",
                            validation_results=sec_validation,
                            execution_mapping=self.skill_registry.get_execution_mapping(sec_skill) or "",
                            parameters=sec_params,
                        )
                    else:
                        sec_errs = [e for v in sec_validation if v for e in v.errors]
                        composite_errors.extend(sec_errs)
                        logger.warning(f" [Multi-Skill] {agent_id} | Secondary '{sec_skill}' failed: {sec_errs}")
                        secondary_proposal = None

        # ⑤ Execution (simulation engine ONLY — skip if REJECTED)
        # F3 (2026-06-10): track what ACTUALLY executed, separately from the
        # approved/blocked proposal — on REJECTED the registry default skill
        # runs as fallback while final_skill records the blocked proposal.
        # Surfaced in the audit trace only when the opt-in flag is ON (see
        # AgentTypeConfig.get_audit_executed_columns; default-OFF keeps
        # frozen-baseline CSVs byte-identical).
        #
        # PR-3: `execution_path` names WHICH of these branches ran, so the
        # audit row states the remap rule instead of leaving an analyst to
        # re-derive it from `status` plus the domain's `on_retry_exhausted`
        # policy (which the CSV does not carry). Computed unconditionally —
        # it is one local string — and surfaced only under the flag.
        executed_skill: Optional[str] = None
        executed_via_fallback = False
        execution_path = "not_executed"
        if self.simulation_engine and outcome not in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
            execution_result = self.simulation_engine.execute_skill(approved_skill)
            executed_skill = approved_skill.skill_name
            execution_path = "approved"
            # ⑤b Sequential secondary execution
            if secondary_approved and execution_result.success:
                secondary_execution = self.simulation_engine.execute_skill(secondary_approved)
        elif outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
            # REJECTED: execute the registry's default skill as fallback so the
            # agent's state is recalculated (instead of a full no-op that
            # freezes state).
            if self.simulation_engine and self._keeps_rejected_proposal(
                    outcome, approved_skill, validation_results):
                # Model-builder opt-in: this domain treats a persistent
                # rule-violating choice as the observable, so the agent's OWN final
                # proposal executes and nothing "fell back".
                # approved_skill already carries that proposal and its execution
                # mapping (_build_approved_skill), so it is executed as-is.
                execution_result = self.simulation_engine.execute_skill(approved_skill)
                executed_skill = approved_skill.skill_name
                executed_via_fallback = False
                execution_path = "rejected_proposal"
            elif self.simulation_engine:
                # Phase 6J-E (2026-05-22): get_default_skill() now raises
                # if unconfigured (Phase 6J-C), so the only branch left to
                # guard is whether the configured id is actually registered.
                fallback_skill = self.skill_registry.get_default_skill()
                if self.skill_registry.exists(fallback_skill):
                    fallback = ApprovedSkill(
                        skill_name=fallback_skill,
                        agent_id=approved_skill.agent_id,
                        approval_status="REJECTED_FALLBACK",
                    )
                    execution_result = self.simulation_engine.execute_skill(fallback)
                    executed_skill = fallback_skill
                    executed_via_fallback = True
                    # UNCERTAIN = the parser never produced a usable choice
                    # (approval_status is already REJECTED_FALLBACK);
                    # REJECTED = a real proposal was blocked and the registry
                    # default took its place. Both run the default skill, but
                    # only the second is the row where `final_skill` lies.
                    execution_path = (
                        "fallback" if outcome is SkillOutcome.UNCERTAIN
                        else "rejected_default"
                    )
                else:
                    logger.warning(f"Default skill '{fallback_skill}' not in registry for {approved_skill.agent_id}")
                    execution_result = ExecutionResult(success=False, state_changes={})
            else:
                execution_result = ExecutionResult(success=False, state_changes={})
        else:
            # Standalone mode: Default to pseudo-execution.
            #
            # P2-4: this branch reports success=True and records the approved
            # skill as executed although NOTHING ran — there is no simulation
            # engine to run it. Labelling it `approved` made those rows
            # indistinguishable from a row where the engine really did execute
            # the approved skill, in a column whose whole purpose is to say
            # what happened. `approved_no_engine` keeps `executed_skill` (the
            # approved skill IS the action the run attributes to the agent, and
            # every downstream executed-only analysis depends on it) while
            # naming the fact that no engine confirmed it.
            execution_result = ExecutionResult(
                success=True,
                state_changes={}
            )
            executed_skill = approved_skill.skill_name if approved_skill else None
            execution_path = "approved_no_engine" if approved_skill else "not_executed"

        # Capture memory state after execution (before experiment-layer updates)
        memory_post = self._get_memory_snapshot(agent_id)

        # ⑥ Audit trace
        if self.audit_writer:
            self._write_audit_trace(
                agent_type=agent_type, context=context,
                run_id=run_id, step_id=step_id, timestamp=timestamp,
                env_context=env_context, seed=seed, agent_id=agent_id,
                all_valid=all_valid, prompt=prompt, raw_output=raw_output,
                context_hash=context_hash, memory_pre=memory_pre,
                memory_post=memory_post, skill_proposal=skill_proposal,
                approved_skill=approved_skill, execution_result=execution_result,
                outcome=outcome, retry_count=retry_count,
                format_retry_count=format_retry_count,
                total_llm_stats=total_llm_stats,
                all_validation_history=all_validation_history,
                executed_skill=executed_skill,
                executed_via_fallback=executed_via_fallback,
                execution_path=execution_path,
                initial_skill=initial_skill,
                initial_labels=initial_labels,
                attempt_skills=attempt_skills,
                advise_info=advise_info,
                soft_advise_info=soft_advise_info,
                decider=decider,
                feasible_by_attempt=feasible_by_attempt,
            )

        result = SkillBrokerResult(
            outcome=outcome,
            skill_proposal=skill_proposal,
            approved_skill=approved_skill,
            execution_result=execution_result,
            validation_errors=[e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors],
            retry_count=retry_count,
            format_retries=format_retry_count,
            secondary_proposal=secondary_proposal,
            secondary_approved=secondary_approved,
            secondary_execution=secondary_execution,
            composite_validation_errors=composite_errors,
            executed_skill=executed_skill,
            executed_via_fallback=executed_via_fallback,
        )
        # The rule ids that blocked the final attempt (empty when it passed).
        # A plain attribute, NOT a dataclass field, so dataclasses.asdict and
        # every serialised trace stay unchanged; read by
        # ExperimentRunner._apply_state_changes for the neutral memory line.
        result.blocking_rule_ids = (
            [] if all_valid else sorted(self._extract_blocking_rule_ids(validation_results))
        )
        return result
    
    def _build_approved_skill(
        self, *, all_valid: bool, skill_proposal, agent_id: str,
        agent_type: str, retry_count: int, validation_results: List,
        initial_rule_ids: set,
    ):
        """Build ApprovedSkill for both approved and rejected paths.

        Returns (approved_skill, outcome). May mutate skill_proposal on
        the rejection path (clears magnitude_pct, sets magnitude_fallback).
        """
        _params = {}
        # 6W-B5: multi-field setpoints flow into ApprovedSkill.parameters so the
        # already-N-capable commit_world_delta consumes them. Applied FIRST; the
        # legacy magnitude_pct/magnitude_fallback are set LAST so the legacy scalar
        # still wins those keys (backward path). Frozen domains: parameters=={} ->
        # this update is a no-op -> _params built byte-identically to pre-6W.
        if skill_proposal and skill_proposal.parameters:
            _params.update(skill_proposal.parameters)
        if skill_proposal and skill_proposal.magnitude_pct is not None:
            _params["magnitude_pct"] = skill_proposal.magnitude_pct
            _params["magnitude_fallback"] = skill_proposal.magnitude_fallback

        if all_valid and skill_proposal:
            approved_skill = ApprovedSkill(
                skill_name=skill_proposal.skill_name,
                agent_id=agent_id,
                approval_status="APPROVED",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(skill_proposal.skill_name) or "",
                parameters=_params,
            )
            outcome = SkillOutcome.RETRY_SUCCESS if retry_count > 0 else SkillOutcome.APPROVED
            if retry_count > 0:
                self.stats["retry_success"] += 1
                ratings = []
                for k, v in (skill_proposal.reasoning or {}).items():
                    if "_LABEL" in k:
                        ratings.append(f"{k}={v}")
                rating_str = f" | {' | '.join(ratings)}" if ratings else ""
                logger.warning(
                    f" [Governance:Success] {agent_id} | Fixed after {retry_count} retries"
                    f" | Choice: '{skill_proposal.skill_name}'{rating_str}"
                )
                for rule_id in initial_rule_ids:
                    self.auditor.log_intervention(rule_id, success=True, is_final=True)
            else:
                self.stats["approved"] += 1
        else:
            # RETRY EXHAUSTION: proceed with REJECTED status for audit
            is_generic_fallback = (skill_proposal is None or skill_proposal.parse_layer == "default")

            if skill_proposal and skill_proposal.magnitude_pct is not None:
                # Don't mutate the original SkillProposal — carry values via _params
                # (the proposal may be referenced by audit writer, memory, or cache)
                _params = {"magnitude_pct": None, "magnitude_fallback": True}
            else:
                # 6W-B5: a REJECTED proposal must NOT carry live setpoints into the
                # fallback ApprovedSkill. For a pure multi-param domain (magnitude_pct
                # is None) the bridge left the setpoint dict in _params; clear it so
                # "rejection discards setpoints" is self-contained, not reliant on the
                # caller's non-REJECTED execution guard. Byte-safe: when magnitude_pct
                # is None, _params was already {} pre-6W for frozen domains.
                _params = {}

            fallout_skill = (
                skill_proposal.skill_name if not is_generic_fallback
                else self.config.get_parsing_config(agent_type).get(
                    "default_skill", self.skill_registry.get_default_skill()
                )
            )

            approved_skill = ApprovedSkill(
                skill_name=fallout_skill,
                agent_id=agent_id,
                approval_status="REJECTED" if not is_generic_fallback else "REJECTED_FALLBACK",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(fallout_skill) or "",
                parameters=_params,
            )
            outcome = SkillOutcome.REJECTED if not is_generic_fallback else SkillOutcome.UNCERTAIN

            if is_generic_fallback:
                logger.error(f" [Governance:Exhausted] {agent_id} | Parsing failed. Forcing fallback: '{fallout_skill}'")
            else:
                logger.error(f" [Governance:Exhausted] {agent_id} | Retries failed. Proceeding with REJECTED choice: '{fallout_skill}'")

            self.stats["rejected"] += 1
            for v in validation_results:
                for rule_id in v.metadata.get("rules_hit", []):
                    self.auditor.log_intervention(rule_id, success=False, is_final=True)

        return approved_skill, outcome

    def _keeps_rejected_proposal(self, outcome, approved_skill,
                                 validation_results=None) -> bool:
        """True iff this decision should execute the agent's own rejected proposal.

        Four conditions, all required:

        1. the domain opted in (``on_retry_exhausted: keep_proposal``);
        2. the outcome is ``REJECTED`` — a real proposal that failed validation.
           ``UNCERTAIN`` means the parser never produced a usable choice, so there is
           nothing of the agent's to preserve and the default must run;
        3. the proposal names a REGISTERED skill. Membership validation can fail and
           still leave a bogus name on the proposal, and executing an unregistered
           skill would silently do nothing useful (or, in a domain whose executor
           applies side effects before matching a branch, something arbitrary).
           Mirrors the ``exists()`` guard the default path already applies;
        4. **no HARD-constraint rule was among the blockers.** This is the safety
           condition INVARIANTS AR-1a states, enforced here in code rather than left
           as prose. ``keep_proposal`` exists to preserve *behaviourally incoherent*
           choices — violating a theory rule is possible, just irrational. It must
           never resurrect a *world-infeasible* one: re-doing an irreversible action,
           exceeding an allocation cap, or paying for something unaffordable would
           put the simulated world into a state it cannot occupy, and some domain
           executors would double-charge or double-apply rather than refuse.

        On (4), note what the marker can and cannot do. ``constraint_type``/
        ``expected_terminal`` are set per validator TIER (identity + affordability =
        hard, thinking = soft), so they are the YAML section in disguise. That makes
        them reliable for what they DO flag — an identity/affordability blocker really
        is an affordance — but they under-flag: a domain may encode a physical
        constraint as a thinking rule, and this guard will not catch it. So it is a
        floor, not a proof. Classifying each rule remains the domain owner's call.
        """
        if self._on_retry_exhausted != "keep_proposal":
            return False
        if outcome is not SkillOutcome.REJECTED:
            return False
        name = getattr(approved_skill, "skill_name", None)
        if not name or not self.skill_registry.exists(name):
            return False
        for v in (validation_results or []):
            if v is None or getattr(v, "valid", True):
                continue
            meta = getattr(v, "metadata", None) or {}
            if (meta.get("constraint_type") == "hard"
                    or meta.get("expected_terminal") is True
                    or meta.get("deterministic") is True):
                logger.info(
                    "[Governance:Exhausted] keep_proposal declined for "
                    f"{getattr(approved_skill, 'agent_id', '?')}: "
                    f"'{name}' was blocked by a hard-constraint rule "
                    f"{meta.get('rules_hit') or meta.get('rule_id')}; running the "
                    "registry default instead (INVARIANTS AR-1a)."
                )
                return False
            if set(meta.get("rules_hit") or []) & _ADVISE_DENY_IDS:
                return False
        return True

    def _run_validators(self, proposal: SkillProposal, context: Dict) -> List[ValidationResult]:
        """Run all validators on the skill proposal."""
        if context is None:
            context = {}

        proposal_agent_type = getattr(proposal, "agent_type", None)
        agent_type = context.get("agent_type")
        if not agent_type and proposal_agent_type and proposal_agent_type != "default":
            agent_type = proposal_agent_type

        if agent_type:
            scoped_context = dict(context)
            scoped_context.setdefault("agent_type", agent_type)
            if "base_type" not in scoped_context:
                get_base_type = getattr(self.config, "get_base_type", None)
                if callable(get_base_type):
                    try:
                        base_type = get_base_type(agent_type)
                    except Exception:
                        base_type = None
                    if isinstance(base_type, str) and base_type:
                        scoped_context["base_type"] = base_type
            context = scoped_context

        results = []
        for validator in self.validators:
            result = validator.validate(proposal, context, self.skill_registry)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)

        # Run custom validators
        for custom_validator_func in self.custom_validators:
            custom_results = custom_validator_func(proposal, context, self.skill_registry)
            if isinstance(custom_results, list):
                results.extend(custom_results)
            else:
                results.append(custom_results)

        # Registry-driven domain PHYSICAL dispatch (OPT-IN, default OFF). When a run
        # declares global_config.governance.dispatch_domain_physical, the engine runs
        # that domain's registered PHYSICAL-slot checks here — the production-faithful
        # alternative to a per-domain custom_validators bridge. PHYSICAL slot ONLY (not
        # the full build_domain_validators 5-tuple), so a domain that also registered
        # personal/social checks does not get them silently activated. When None
        # (every frozen domain), this is a strict no-op -> byte-identical.
        # Wave 3 (review P1-2): also accepts a {agent_type: domain} mapping for
        # mixed-domain experiments — each proposal routes to ITS agent type's
        # domain; agent types absent from the mapping get no registry dispatch.
        if self.domain_physical_dispatch:
            dispatch_domain = self.domain_physical_dispatch
            if isinstance(dispatch_domain, dict):
                dispatch_domain = dispatch_domain.get(
                    getattr(proposal, "agent_type", None) if proposal else None
                )
            if dispatch_domain:
                from broker.components.governance.validator_registry import ValidatorRegistry
                from broker.validators.governance.physical_validator import PhysicalValidator
                phys_checks = ValidatorRegistry.get_checks(dispatch_domain, "physical")
                if phys_checks:
                    phys = PhysicalValidator(builtin_checks=phys_checks)
                    phys.set_mode(ValidatorRegistry.get_validator_mode(dispatch_domain, "physical"))
                    sn = getattr(proposal, "skill_name", "") if proposal else ""
                    results.extend(phys.validate(sn, [], context))

        # Registry-level: validate LLM output against skill's output_schema
        if (proposal and proposal.skill_name and self.skill_registry
                and self.skill_registry.exists(proposal.skill_name)):
            output_fields = {}
            if proposal.magnitude_pct is not None:
                output_fields["magnitude_pct"] = proposal.magnitude_pct
            # 6W: multi-dimensional setpoints live on proposal.parameters, not as
            # first-class proposal attributes — surface them so a skill whose
            # output_schema lists each setpoint as a required field can see them.
            # Empty {} for frozen single-scalar domains -> output_fields unchanged
            # -> byte-identical (magnitude_pct path untouched). Reserved scalar keys
            # are excluded so a setpoint named magnitude_pct/magnitude_fallback can
            # never clobber the first-class value (mirrors the _audit_helpers
            # proposed_param_* exclusion).
            for _pk, _pv in (proposal.parameters or {}).items():
                if _pk not in ("magnitude_pct", "magnitude_fallback"):
                    output_fields[_pk] = _pv
            # Reverse-lookup: find which numbered option maps to this skill_name
            # so the 'decision' field expected by output_schema is populated.
            agent_ctx = context.get("agent_state", {})
            personal = agent_ctx.get("personal", {}) if isinstance(agent_ctx, dict) else {}
            skill_map = personal.get("dynamic_skill_map", {})
            for num_str, sid in skill_map.items():
                if sid == proposal.skill_name:
                    try:
                        output_fields["decision"] = int(num_str)
                    except (ValueError, TypeError):
                        output_fields["decision"] = num_str
                    break
            schema_result = self.skill_registry.validate_output_schema(
                proposal.skill_name, output_fields
            )
            if schema_result:
                if not schema_result.valid:
                    schema_result.metadata["rules_hit"] = ["output_schema_violation"]
                    # rule_id so the audit CSV's failed_rules column names this
                    # producer instead of "Unknown" (2026-06-10 e4b finding).
                    # Byte-safe: zero output_schema violations exist in the
                    # frozen mock baselines (verified before adding).
                    schema_result.metadata.setdefault("rule_id", "output_schema_violation")
                    logger.debug(f"[OutputSchema] {proposal.skill_name}: {schema_result.errors}")
                results.append(schema_result)

        # Registry-level: check YAML preconditions against agent state
        if (proposal and proposal.skill_name and self.skill_registry
                and self.skill_registry.exists(proposal.skill_name)):
            agent_ctx = context.get("agent_state", {})
            state = agent_ctx.get("state", {}) if isinstance(agent_ctx, dict) else {}
            precond_result = self.skill_registry.check_preconditions(
                proposal.skill_name, state
            )
            if precond_result:
                if not precond_result.valid:
                    precond_result.metadata["rules_hit"] = ["precondition_violation"]
                    # Named for failed_rules attribution (review W1, same
                    # byte-safety basis as output_schema_violation: zero
                    # precondition violations in the frozen mock baselines —
                    # every frozen failed_rules cell is the single "Unknown"
                    # from the format check).
                    precond_result.metadata.setdefault("rule_id", "precondition_violation")
                    logger.debug(f"[Precondition] {proposal.skill_name}: {precond_result.errors}")
                results.append(precond_result)

        # P0-1c: the ADVISE disposition rewrite, applied at this single return so
        # EVERY validation pass in a decision agrees — the first pass, the retry
        # loop's re-validation (_retry_loop.py), the multi-skill secondary path, and
        # the advisory pass's own re-validation. Applying it anywhere earlier would
        # let the retry loop re-derive the rule UN-demoted and block on it, and would
        # permanently desync EarlyExit's prev/current blocking-rule comparison.
        # Flag OFF => empty allowlist => demote() returns this same list object.
        return demote(results, self._advise_rule_ids)

    def _create_result(self, outcome, proposal, approved, execution, errors, format_retries: int = 0) -> SkillBrokerResult:
        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=proposal,
            approved_skill=approved,
            execution_result=execution,
            validation_errors=errors,
            retry_count=0,
            format_retries=format_retries
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        total = self.stats["total"]
        if total == 0:
            return {**self.stats, "approval_rate": "N/A"}
        
        approved = self.stats["approved"] + self.stats["retry_success"]
        return {
            **self.stats,
            "approval_rate": f"{approved/total*100:.1f}%",
            "first_pass_rate": f"{self.stats['approved']/total*100:.1f}%"
        }
