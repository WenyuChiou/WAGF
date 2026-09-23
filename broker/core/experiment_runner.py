"""
Experiment Runner — simulation loop engine.

Extracted from experiment.py (Phase 2.1 split).
"""
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
import inspect
import json
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

from broker.agents import BaseAgent
from ..interfaces.skill_types import ApprovedSkill, SkillOutcome, SkillBrokerResult, ExecutionResult, SkillProposal
from ..interfaces.lifecycle_protocols import PreYearHook, PostStepHook, PostYearHook
from .skill_broker_engine import SkillBrokerEngine
from ..components.context.builder import BaseAgentContextBuilder
from ..components.memory.engine import MemoryEngine, WindowMemoryEngine, HierarchicalMemoryEngine
from ..utils.agent_config import GovernanceAuditor
from ..utils.logging import logger
from .efficiency import CognitiveCache


def _rebuild_cached_proposal(
    cached_proposal: Optional[Dict[str, Any]],
    *,
    skill_name: str,
    agent_id: str,
    reasoning: Dict[str, Any],
    agent_type: str,
) -> SkillProposal:
    """Reconstruct a SkillProposal from a cognitive-cache ``skill_proposal`` dict.

    The legacy inline reconstruction copied only four fields and silently dropped
    the 6W multi-dimensional ``parameters`` setpoint dict, losing multi-dim actions
    on every cache-hit replay. This helper threads ``parameters`` back. The remaining
    fields are passed explicitly because the two cache-hit reconstructions
    intentionally differ (proposed vs approved skill_name; cached vs current
    agent_type). ``parameters`` defaults to ``{}`` when the key is absent, so a
    frozen-domain cached entry (which never carries it) reconstructs byte-identically.
    """
    return SkillProposal(
        skill_name=skill_name,
        agent_id=agent_id,
        reasoning=reasoning,
        agent_type=agent_type,
        parameters=(cached_proposal or {}).get("parameters", {}),
    )


_HOOK_PROTOCOLS = {
    "pre_year": (PreYearHook, 3),
    "pre_step": (PreYearHook, 3),
    "post_step": (PostStepHook, 2),
    "post_year": (PostYearHook, 2),
    # same 2-arg (year, agents) shape as post_year — fires after the step's
    # agent loop completes (naming kept for backward compat).
    "post_step_end": (PostYearHook, 2),
}


def _accepts_hook_args(hook_fn: Callable, arg_count: int) -> bool:
    try:
        inspect.signature(hook_fn).bind(*([object()] * arg_count))
    except ValueError:
        # inspect.signature() cannot introspect some C-extension callables;
        # fail open (assume valid) rather than block execution.
        return True
    except TypeError:
        return False
    return True


def _validate_hooks(hooks_dict: Dict[str, Callable]) -> None:
    """Validate hook names (hard) + signatures (warning-only diagnostics).

    F7 (2026-06-10 review): an UNKNOWN hook name used to be silently skipped —
    register ``post_year_end`` (typo) and the run completes green with the
    hook never firing, the purest silent-feature-loss. Unknown names now
    RAISE (every caller in the repo uses canonical names, so this breaks
    nothing); signature mismatches stay warning-only (lambdas/*args wrappers
    are legitimate).
    """
    for name, hook_fn in hooks_dict.items():
        expected = _HOOK_PROTOCOLS.get(name)
        if not expected:
            raise ValueError(
                f"Unknown lifecycle hook name '{name}'. Valid names: "
                f"{sorted(_HOOK_PROTOCOLS)}. (A misspelled hook would "
                f"silently never fire — refusing instead.)"
            )
        protocol, arg_count = expected
        if not isinstance(hook_fn, protocol) or not _accepts_hook_args(hook_fn, arg_count):
            logger.warning(
                f"[Lifecycle:Diagnostic] Hook '{name}' does not match "
                f"{protocol.__name__} protocol signature. "
                f"See broker.interfaces.lifecycle_protocols for expected signatures."
            )


@dataclass
class ExperimentConfig:
    """Configuration container for an experiment."""
    model: str = "gpt-4"
    num_years: int = 1
    num_steps: Optional[int] = None  # Generic alias for num_years
    semantic_thresholds: tuple = (0.3, 0.7) # PR 3: Configurable heuristics
    governance_profile: str = "default"
    output_dir: Path = Path("results")
    experiment_name: str = "modular_exp"
    seed: int = 42
    verbose: bool = False
    workers: int = 1  # Number of parallel workers for LLM calls (1=sequential)
    phase_order: Optional[List[List[str]]] = None  # Agent type groups for phased execution
    # 2026-06-10 review F4: CognitiveCache decision reuse is OPT-IN (default OFF).
    # When previously always-on, cache hits emitted NO audit row (denominator
    # shrink, the F1 class), dropped magnitude_pct, and replayed state changes
    # without execute_skill (a coupled world never saw the action). v21 row
    # counts (3276/3276) prove zero hits ever fired in frozen runs, so the
    # OFF default is byte-identical for them.
    enable_cognitive_cache: bool = False

class ExperimentRunner:
    """Engine that runs the simulation loop."""
    def __init__(self,
                 broker: SkillBrokerEngine,
                 sim_engine: Any,
                 agents: Dict[str, BaseAgent],
                 config: ExperimentConfig,
                 memory_engine: Optional[MemoryEngine] = None,
                 hooks: Optional[Dict[str, Callable]] = None):
        self.broker = broker
        self.sim_engine = sim_engine
        self.agents = agents
        self.config = config
        self.step_counter = 0
        self.memory_engine = memory_engine or WindowMemoryEngine(window_size=3)
        self.hooks = hooks or {}

        # Git state, captured HERE rather than at finalize. See the note in
        # _collect_reproducibility_metadata: sampling it ten hours later recorded whether
        # the tree was dirty when the run ended, and named a commit the run never ran.
        # Construction is the earliest unambiguous point and is seconds from launch.
        try:
            import subprocess
            self._git_commit_at_launch = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            ).decode().strip()
            self._git_dirty_at_launch = len(subprocess.check_output(
                ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
            ).decode().strip()) > 0
        except Exception:
            self._git_commit_at_launch = "unavailable"
            self._git_dirty_at_launch = None

        # Sync verbosity
        self.broker.log_prompt = self.config.verbose

        # Cache for llm_invoke functions per agent type
        self._llm_cache = {}

        # PR-8: per-agent-type decider declarations, read once from config.
        # The CALLABLE is not cached for non-default deciders — see
        # get_decider — only the declaration is.
        self._decider_spec_cache = {}
        self._decider_factory_cache = {}
        self._domain_deciders_registered = False

        # [Efficiency Hub] Cognitive Caching for decision reuse — opt-in (F4).
        # None = disabled: hash/get/put are skipped (all side-effect-free).
        # The early context build itself stays UNCONDITIONAL — universal-engine
        # retrieve() mutates EMA state per call and frozen baselines were
        # produced with two builds per step (see the loop-site note).
        if config.enable_cognitive_cache:
            persistence_path = config.output_dir / "cognitive_cache.json"
            self.efficiency = CognitiveCache(persistence_path=persistence_path)
        else:
            self.efficiency = None

    @property
    def hooks(self) -> Dict[str, Callable]:
        """Lifecycle hooks.

        Wholesale assignment validates hook signatures with warning-only
        diagnostics. In-place mutation such as ``runner.hooks.update(...)``
        intentionally bypasses validation; this remains a non-breaking
        diagnostic feature, not a gate.
        """
        return self._hooks

    @hooks.setter
    def hooks(self, hooks_dict: Dict[str, Callable]) -> None:
        _validate_hooks(hooks_dict)
        self._hooks = hooks_dict

    @property
    def llm_invoke(self) -> Callable:
        """Legacy default llm_invoke."""
        return self.get_llm_invoke("default")

    def get_llm_invoke(self, agent_type: str) -> Callable:
        """Create or return cached llm_invoke for a specific agent type.

        Supports per-type model names via ``llm_params.model`` in YAML:

        .. code-block:: yaml

            government:
              llm_params:
                model: llama3.3:70b   # overrides CLI --model for this type

        If ``model`` is not specified in ``llm_params``, the CLI/builder model
        (``self.config.model``) is used as fallback.
        """
        if agent_type not in self._llm_cache:
            from broker.utils.llm_utils import create_llm_invoke
            # Get parameters from config if available
            overrides = {}
            if hasattr(self.broker, 'config') and self.broker.config:
                overrides = self.broker.config.get_llm_params(agent_type)

            # Per-type model name: llm_params.model overrides CLI model.
            # Keep backward compatibility with legacy placeholder values.
            model_override = overrides.pop("model", None)
            if isinstance(model_override, str) and model_override.strip().lower() in {
                "",
                "command-line-override",
                "cli-override",
            }:
                model_override = None
            model_name = model_override or self.config.model

            self._llm_cache[agent_type] = create_llm_invoke(
                model_name,
                verbose=self.config.verbose,
                overrides=overrides
            )
        return self._llm_cache[agent_type]

    # ------------------------------------------------------------------
    # PR-8: deciders — get_llm_invoke generalised to "whatever decides"
    # ------------------------------------------------------------------

    def get_decider_spec(self, agent_type: str):
        """The ``decider:`` this agent type declares, defaulting to ``llm``.

        Cached per type: the answer comes from config and cannot change
        during a run, and it is consulted once per agent per step.
        """
        # getattr, not self._decider_spec_cache: several tests (and the
        # audit-conservation harness) build a runner with
        # ``ExperimentRunner.__new__`` and never run __init__, and a
        # provenance cache is not a reason for those to stop working.
        cache = getattr(self, "_decider_spec_cache", None)
        if cache is None:
            cache = {}
            self._decider_spec_cache = cache
        cached = cache.get(agent_type)
        if cached is not None:
            return cached
        from broker.agents.deciders import DEFAULT_DECIDER_SPEC
        spec = DEFAULT_DECIDER_SPEC
        config = getattr(getattr(self, "broker", None), "config", None)
        getter = getattr(config, "get_decider", None) if config else None
        if callable(getter):
            spec = getter(agent_type)
        cache[agent_type] = spec
        return spec

    def get_decider(
        self,
        agent_type: str,
        *,
        agent: Any = None,
        agent_id: Optional[str] = None,
        env: Optional[Dict] = None,
    ) -> Callable:
        """The callable that decides for this agent — LLM or otherwise.

        The generalisation of :meth:`get_llm_invoke`, and its superset:
        for an agent type that declares no ``decider:`` (every type in
        every frozen config) this returns the SAME OBJECT
        ``get_llm_invoke(agent_type)`` returns, from the same cache. So
        the call sites below could be switched from one to the other
        without a single byte moving in any existing corpus — which is
        the property that let this land at all.

        The BINDING to this agent and this period is redone per step
        rather than cached, because a rule table reads the agent's
        CURRENT state and this period's environment; a decider cached at
        year one would answer year thirteen from year one's numbers, and
        the audit trail would look entirely reasonable. What IS cached
        per agent type is the resolved factory and the config block it
        reads — the registry lookup and the domain-pack registration
        sweep, which cannot change during a run (review P1-c).
        """
        spec = self.get_decider_spec(agent_type)
        if spec.is_default:
            return self.get_llm_invoke(agent_type)

        factory, type_block = self._resolve_decider_factory(agent_type, spec)
        # A decider that never calls a model must not force one into
        # existence. `create_llm_invoke` constructs a provider client,
        # and for a cloud provider that means credentials — a purely
        # rule-based population would otherwise fail for want of a key
        # it was never going to use. `hybrid` resolves it on the first
        # decision no rule matched; `llm` resolves it here, so the plain
        # default keeps returning the identical cached object.
        if spec.name == "llm":
            llm_invoke = self.get_llm_invoke(agent_type)
        else:
            def llm_invoke(prompt, **kw):
                fn = self.get_llm_invoke(agent_type)
                return fn(prompt, **kw) if kw else fn(prompt)

        return self._build_decider(spec, factory, type_block, {
            "llm_invoke": llm_invoke,
            "agent": agent,
            "agent_id": agent_id if agent_id is not None else getattr(agent, "id", None),
            "agent_type": agent_type,
            "env": env,
            "seed": getattr(getattr(self, "config", None), "seed", None),
            "runner": self,
        })

    def _resolve_decider_factory(self, agent_type: str, spec):
        """``(factory, agent_type_config)`` for a declared decider, cached.

        The registry lookup and the DomainPack registration sweep are
        answered from config and cannot change during a run, so doing
        them per agent per step was pure repetition. Cached here; the
        per-step binding stays per-step.
        """
        cache = getattr(self, "_decider_factory_cache", None)
        if cache is None:
            cache = {}
            self._decider_factory_cache = cache
        cached = cache.get(agent_type)
        if cached is not None:
            return cached

        from broker.agents.deciders import DeciderRegistry, register_domain_deciders
        if not getattr(self, "_domain_deciders_registered", False):
            register_domain_deciders(self._resolve_governance_domain())
            self._domain_deciders_registered = True

        factory = DeciderRegistry.get(spec.name)
        config = getattr(getattr(self, "broker", None), "config", None)
        type_block = {}
        if config is not None and hasattr(config, "get"):
            try:
                type_block = config.get(agent_type) or {}
            except Exception:  # noqa: BLE001 — a config read must not abort a step
                type_block = {}
        cache[agent_type] = (factory, type_block)
        return factory, type_block

    @staticmethod
    def _build_decider(spec, factory, type_block, runtime):
        """``DeciderRegistry.build`` with the factory already resolved."""
        from broker.agents.deciders import DeciderRegistry

        return DeciderRegistry.build(spec, type_block, runtime, factory=factory)

    def _resolve_declared_deciders(self) -> Dict[str, str]:
        """Build every DECLARED non-default decider once, before year one.

        Review P1-c. Before this, ``get_decider`` was evaluated inside the
        per-agent ``try``, so a factory that could not be built at all —
        an unregistered name, a rule table with no ``default_action``, a
        ``parametric`` target whose module does not import — was caught by
        the exception handler that exists for a model timing out. Every
        agent of that type became an ABORTED sentinel stamped with the
        decider it never ran, the run finished, and the process exited 0
        with a CSV that looks like a mixed-population corpus in which one
        arm simply crashed a lot. That is precisely the "no silent
        fallback to llm" promise the module docstrings make, broken by the
        placement of a ``try``.

        Building here means the traceback arrives before any row is
        written, naming the agent type and the decider. Nothing is cached
        from the probe build except the factory: the probe binds no agent,
        so it cannot be reused as a decision-maker.
        """
        resolved: Dict[str, str] = {}
        agents = getattr(self, "agents", None) or {}
        values = agents.values() if hasattr(agents, "values") else agents
        types = []
        for agent in values:
            atype = getattr(agent, "agent_type", "default")
            if atype not in types:
                types.append(atype)
        for agent_type in types:
            spec = self.get_decider_spec(agent_type)
            if spec.is_default:
                continue
            factory, type_block = self._resolve_decider_factory(agent_type, spec)
            # The probe binds no agent on purpose: every built-in does its
            # validation (rule-table parse, `default_action` presence,
            # target import) at BUILD time, and a probe carrying a real
            # agent would be one more object that could be mistaken for a
            # live decider.
            self._build_decider(spec, factory, type_block, {
                "llm_invoke": self.get_llm_invoke(agent_type),
                "agent": None,
                "agent_id": None,
                "agent_type": agent_type,
                "env": None,
                "seed": getattr(getattr(self, "config", None), "seed", None),
                "runner": self,
            })
            resolved[agent_type] = spec.name
        if resolved:
            logger.info(
                "[Decider] resolved declared deciders before year 1: %s",
                ", ".join(f"{k}={v}" for k, v in sorted(resolved.items())),
            )
        return resolved

    def _decider_kwargs(self, agent_type: str) -> Dict[str, Any]:
        """``{"decider": name}`` for a declared decider, ``{}`` for the default.

        Omitted rather than passed as ``"llm"`` on the default path so
        the ``process_step`` call is argument-for-argument what it was
        before PR-8. Brokers that are not ``SkillBrokerEngine`` — test
        doubles, and any downstream engine implementing the same seam —
        keep working untouched, and only a run that actually declares a
        decider needs a broker that understands the keyword.
        """
        spec = self.get_decider_spec(agent_type)
        return {} if spec.is_default else {
            "decider": self._decider_audit_name(agent_type)}

    def _decider_audit_name(self, agent_type: str) -> str:
        """The name the ``decider`` audit column should carry for this type.

        Normally the declared name. When a domain has deliberately
        REPLACED a built-in (P1-d), ``<name>@<domain>`` — otherwise a CSV
        holding rows from the built-in ``rule_based`` and from a domain's
        replacement for it calls both ``rule_based`` and cannot be read.
        """
        name = self.get_decider_spec(agent_type).name
        try:
            from broker.agents.deciders import DeciderRegistry

            return DeciderRegistry.audit_label(name)
        except Exception:  # noqa: BLE001 — provenance label only
            return name

    def _resolve_governance_domain(self) -> Optional[str]:
        """``global_config.governance.domain``, or None when undeclared."""
        config = getattr(self.broker, "config", None)
        raw = getattr(config, "_config", None) if config is not None else None
        if not isinstance(raw, dict):
            return None
        domain = (
            raw.get("global_config", {})
            .get("governance", {})
            .get("domain")
        )
        return str(domain) if domain else None

    @property
    def current_step(self) -> int:
        """Alias for the simulation loop cycle."""
        # This returns the current year/cycle index
        return getattr(self, '_current_year', 0)

    def run(self, llm_invoke: Optional[Callable] = None):
        """Standardized simulation loop.

        ITERATION SEQUENCE (documented 2026-06-10 — previously emergent):
        1. ``sim_engine.advance_step()`` (or ``advance_year``) -> env dict
        2. ``pre_step`` hook, then ``pre_year`` hook (BOTH fire if registered)
        3. active-agent filter -> ``phase_order`` partition (unmatched types
           run as a trailing phase, with a warning)
        4. per phase: agent loop (sequential or ThreadPool) -> then, per
           result: ``_apply_state_changes`` + ``post_step`` hook (interleaved
           per agent; REJECTED/UNCERTAIN reach post_step WITHOUT state/memory
           application; ABORTED results carry ``skill_proposal=None`` — hooks
           must tolerate that)
        5. after ALL phases: ``post_step_end`` then ``post_year`` (both fire)
        6. ``_finalize_step``; finally-guaranteed ``_finalize_experiment``.

        INTRA-PERIOD VISIBILITY (three channels, three latencies — the
        MA-complex review finding): (a) THIS env dict is created once per
        period — values copied INTO it before phase 1 (e.g. a domain
        pre_year snapshotting its global state) stay frozen for the period
        unless a post_step hook mutates the dict in place at a phase
        boundary (the deliberate live-channel idiom); (b) live shared
        OBJECTS referenced from contexts (social feeds, interaction hubs)
        are read at prompt-build time -> same-period; (c) per-agent
        ``dynamic_state`` applies per phase. Validators consume (a).

        ``llm_invoke`` is accepted for backward compatibility but has NEVER
        had an effect: the agent-loop methods always build their own
        per-agent-type invoke via ``get_llm_invoke()`` (config-driven model +
        verbosity), ignoring the threaded parameter. Callers passing a custom
        invoke (e.g. a REST-backed LLM, or ``create_llm_invoke(model,
        verbose=False)`` expecting to control verbosity) were silently
        misrouted to the config default — warn instead of pretending
        (2026-06-09 architecture review P1-10).
        """
        if llm_invoke is not None and llm_invoke is not self.llm_invoke:
            # self.llm_invoke is the cached get_llm_invoke("default") — passing
            # it back in (as run_unified_experiment does) is harmless, so only
            # a genuinely different invoke (custom/REST-backed, or a fresh
            # create_llm_invoke with different verbosity) triggers the warning.
            logger.warning(
                "[ExperimentRunner] run(llm_invoke=...) is IGNORED — the loop "
                "uses per-agent-type invokes from config (get_llm_invoke). "
                "Configure model/verbosity via ExperimentConfig instead."
            )
        llm_invoke = llm_invoke or self.llm_invoke
        run_id = f"exp_{random.randint(1000, 9999)}"
        logger.info(f"Starting Experiment: {self.config.experiment_name} | Model: {self.config.model}")

        # Inject model name into broker for audit trace enrichment
        self.broker._model_name = self.config.model

        # 0. Fool-proof Schema Validation
        # ... (keep existing validation code)
        if hasattr(self.broker, 'model_adapter') and getattr(self.broker.model_adapter, 'agent_config', None):
            config = self.broker.model_adapter.agent_config
            types = set(a.agent_type for a in self.agents.values() if hasattr(a, 'agent_type'))
            logger.debug(f"[Governance:Diagnostic] Initializing with Profile: {self.config.governance_profile}")
            for atype in types:
                issues = config.validate_schema(atype)
                for issue in issues:
                    logger.warning(f"[Governance:Diagnostic] {issue}")

        # PR-8 review P1-c: build every DECLARED decider now, before the
        # first row exists. A decider that cannot be built at all is a
        # config error, and a config error must not arrive as a per-agent
        # exception inside the loop's handler — that handler turns it into
        # an ABORTED sentinel and the run exits 0. Nothing here runs for a
        # config that declares no decider: `get_decider_spec` answers from
        # the cache and every type is the default.
        self._resolve_declared_deciders()

        # Determine total iterations (backward compatible)
        iterations = self.config.num_steps or self.config.num_years

        try:
            for step in range(1, iterations + 1):
                self._current_year = step # internal tracker
                # Environment update (Attempt advance_step first, fallback to advance_year)
                if hasattr(self.sim_engine, 'advance_step'):
                    env = self.sim_engine.advance_step()
                else:
                    env = self.sim_engine.advance_year() if self.sim_engine else {}

                # Ensure current_year is in env (Standardized)
                if env is None: env = {}
                if "current_year" not in env:
                    env["current_year"] = step

                # Print status using generic term if steps used, otherwise year
                term = "Step" if self.config.num_steps else "Year"
                logger.info(f"--- {term} {step} ---")

                # --- Lifecycle Hook: Pre-Step / Pre-Year ---
                # Dual trigger for generic compatibility
                if "pre_step" in self.hooks:
                    self._call_hook("pre_step", step, env, self.agents)
                if "pre_year" in self.hooks:
                    self._call_hook("pre_year", step, env, self.agents)

                # Filter only active agents (Generic approach)
                active_agents = [
                    a for a in self.agents.values()
                    if getattr(a, 'is_active', True)
                ]

                # Partition agents into phases (if phase_order configured)
                if self.config.phase_order:
                    agent_phases = self._partition_by_phase(active_agents)
                else:
                    agent_phases = [active_agents]  # Single phase (backward compatible)

                # Execute each phase sequentially, agents within phase sequential or parallel
                for phase_agents in agent_phases:
                    if not phase_agents:
                        continue
                    if self.config.workers > 1:
                        results = self._run_agents_parallel(phase_agents, run_id, llm_invoke, env)
                    else:
                        results = self._run_agents_sequential(phase_agents, run_id, llm_invoke, env)

                    # Apply results and trigger post-step hooks
                    for agent, result in results:
                        if result.outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
                            # REJECTED: no state change, no memory — only audit trace
                            if "post_step" in self.hooks:
                                self._call_hook("post_step", agent, result)
                            continue
                        if result.execution_result and result.execution_result.success:
                            self._apply_state_changes(agent, result)
                        if "post_step" in self.hooks:
                            self._call_hook("post_step", agent, result)

                # --- Lifecycle Hook: Post-Step-End / Post-Year ---
                # Dual trigger for generic compatibility
                if "post_step_end" in self.hooks:
                    self._call_hook("post_step_end", step, self.agents)
                if "post_year" in self.hooks:
                    self._call_hook("post_year", step, self.agents)

                self._finalize_step(step)
        finally:
            self._finalize_experiment(iterations)

    def _call_hook(self, name: str, *args) -> None:
        """Invoke a lifecycle hook with named failure context (F7, 2026-06-10).

        A raising hook used to kill the batch mid-year with NOTHING naming the
        hook (an ABORTED result's ``skill_proposal=None`` flowing into a naive
        ``post_step`` is the canonical trigger). We log the hook name + year
        loudly, then RE-RAISE — deliberately no swallow-and-continue option:
        silent hook failure is the v0.88.15 class, and run()'s try/finally
        already guarantees audit finalize on the way out.
        """
        try:
            self.hooks[name](*args)
        except Exception:
            logger.error(
                f"[Lifecycle:HookError] hook '{name}' raised at "
                f"{'step' if self.config.num_steps else 'year'} "
                f"{getattr(self, '_current_year', '?')} — re-raising "
                f"(run aborts; audit finalize guaranteed by run()'s finally).",
                exc_info=True,
            )
            raise

    def _finalize_experiment(self, iterations: int):
        """Finalize outputs even if the run exits early."""
        # ORDER IS LOAD-BEARING: finalize() is what writes the audit CSV(s).
        # `_collect_reproducibility_metadata()` below calls `record_run_integrity`,
        # whose coverage block READS those CSVs — run it first and coverage comes
        # back empty, which reads as "nothing missing" rather than "not measured".
        # Do not move this call below the manifest build.
        if hasattr(self.broker.audit_writer, 'finalize'):
            self.broker.audit_writer.finalize()

        # The CONFIGURED expectation, recorded for the coverage block. It has to
        # come from here because `_collect_reproducibility_metadata` never sees
        # `iterations`, and the coverage block cannot derive it: a run cut short
        # at year 9 of 13 produces a 9-year grid that looks complete.
        # Per agent TYPE, because each type gets its own audit CSV and pooling
        # them multiplies one type's agents by another type's years.
        self._configured_expectation = self._configured_grid_expectation(iterations)

        summary_path = self.config.output_dir / "governance_summary.json"

        # Phase 32: Create Reproducibility Manifest (enhanced per WRR reviewer feedback)
        # ``json`` is imported at module level so the silent-failure
        # regression test in ``broker/tests/test_silent_failure_fixes.py``
        # can patch ``broker.core.experiment_runner.json.dump`` to
        # simulate a disk-full failure (F3).
        import shutil

        manifest = {
            "model": self.config.model,
            "seed": self.config.seed,
            # The memory engine's own seed, distinct from config.seed. It decides which
            # memories are promoted to the long-term store, so two runs differing only in
            # it are different experiments -- and it reached no artifact until 2026-08-06,
            # which made `--memory-seed` unrecoverable from a finished corpus. None when
            # the engine does not carry one.
            #
            # The isinstance guard is not defensive padding. Tests construct the runner with
            # MagicMock engines, and a bare getattr returns a Mock rather than None, which
            # is not JSON-serialisable and takes the whole manifest write down. This project's
            # own plan file records that this exact class has bitten twice before; it bit a
            # third time when this line was first written without the guard, and the suite
            # caught it. Coerce to a known type, never trust the attribute's presence.
            "memory_seed": (
                _ms if isinstance(_ms := getattr(self.memory_engine, "seed", None), int)
                else None
            ),
            "memory_engine_class": type(self.memory_engine).__name__,
            "num_years": iterations,
            "governance_profile": self.config.governance_profile,
            "agent_types_config": str(self.broker.model_adapter.config_path) if hasattr(self.broker.model_adapter, 'config_path') else "unknown",
            # Generic, additive: a domain runner that derives agent_types_config
            # from an original file (e.g. a domain runner that adds a coupling key
            # --coupling flag, which writes an isolated copy with one added key)
            # sets `runner.broker._derived_from_config` to the ORIGINAL path right
            # after build() - same pattern as `_retry_feedback_mode` below. None
            # when no runner ever sets it, so an un-derived config is unaffected.
            # isinstance-guarded the same way `memory_seed` above is: tests
            # construct the runner with a MagicMock broker, and a bare getattr
            # returns a Mock (not JSON-serialisable, takes the whole manifest
            # write down) rather than None. Checked against the CONCRETE
            # ``pathlib.Path`` class, not ``os.PathLike``: ``MagicMock``
            # implements ``__fspath__`` (Python 3.8+), so
            # ``isinstance(mock, os.PathLike)`` is True for an unconfigured
            # Mock and would let a junk string through here.
            "derived_from_config": (
                str(_dfc) if isinstance(
                    _dfc := getattr(self.broker, "_derived_from_config", None),
                    (str, Path),
                ) else None
            ),
        }
        manifest.update(self._collect_reproducibility_metadata())
        # Memory write policy snapshot (populated if the engine is wrapped by
        # PolicyFilteredMemoryEngine). This captures the policy and dropped-count
        # summary so the audit trace explains any "missing" memories unambiguously.
        try:
            from broker.components.memory.policy_filter import PolicyFilteredMemoryEngine
            if isinstance(self.memory_engine, PolicyFilteredMemoryEngine):
                manifest["memory_write_policy"] = self.memory_engine.stats()
        except Exception:
            # Never let manifest enrichment fail the experiment
            pass

        # Copy configuration for future audit (with CLI overrides applied)
        if hasattr(self.broker.model_adapter, 'config_path') and self.broker.model_adapter.config_path:
            config_src = Path(self.broker.model_adapter.config_path)
            if config_src.exists():
                try:
                    import yaml
                    with open(config_src, 'r', encoding='utf-8') as f:
                        config_data = yaml.safe_load(f)

                    # Inject CLI overrides so snapshot reflects actual run
                    if 'global_config' not in config_data:
                        config_data['global_config'] = {}
                    if 'llm' not in config_data['global_config']:
                        config_data['global_config']['llm'] = {}

                    # Override model with actual CLI value
                    config_data['global_config']['llm']['model'] = self.config.model

                    # Add metadata about this specific run
                    config_data['metadata'] = config_data.get('metadata', {})
                    config_data['metadata']['actual_model'] = self.config.model
                    config_data['metadata']['seed'] = self.config.seed
                    config_data['metadata']['governance_profile'] = self.config.governance_profile
                    # Silent-failure P1 (review round 2): record the RESOLVED
                    # retry_feedback_mode here too. A CLI override
                    # (examples/single_agent/run_flood.py
                    # --retry-feedback-mode) changes the ENGINE attribute
                    # only -- it never touches the on-disk YAML this block
                    # just read -- so without this line the snapshot silently
                    # showed the pre-override YAML value (almost always
                    # "full") for exactly the runs where an operator most
                    # needed the snapshot to say "placebo".
                    config_data['metadata']['retry_feedback_mode'] = getattr(
                        self.broker, "_retry_feedback_mode", "full")

                    with open(self.config.output_dir / "config_snapshot.yaml", 'w', encoding='utf-8') as f:
                        yaml.dump(config_data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
                except Exception:
                    # Fallback to simple copy if YAML processing fails
                    shutil.copy(config_src, self.config.output_dir / "config_snapshot.yaml")

        # F3 fix (post-Phase-6T silent-failure audit, 2026-05-27):
        # pre-fix the manifest write was UNWRAPPED — an OSError
        # (disk full, read-only path, permission denied) propagated
        # out of `_finalize_experiment` BEFORE `save_summary` could
        # run, leaving the run with audit CSV + JSONL but no
        # governance_summary.json. Downstream consumers (paper-
        # reproducibility scripts, swarmlab, abm-reproducibility-
        # checker skill) silently fell back to recomputing or
        # crashed; none surfaced the underlying disk-state.
        #
        # Fix: each output write is now an independent try/except.
        # The summary save MUST run regardless of whether the
        # manifest write succeeded — summary is the more
        # important artifact for governance reproducibility.
        try:
            with open(self.config.output_dir / "reproducibility_manifest.json", 'w') as f:
                json.dump(manifest, f, indent=2)
        except (OSError, TypeError, ValueError) as e:
            # TypeError/ValueError matter as much as OSError here: json.dump raises
            # TypeError on a non-serialisable value, so a single bad entry anywhere
            # in `manifest` would abort this block and STARVE the summary save
            # below — defeating the whole point of splitting these into independent
            # try/excepts. A duck-typed or Mock broker injecting a Mock into
            # metadata is exactly that case, and OSError never caught it.
            logger.error(
                f"[Finalize] reproducibility_manifest.json write "
                f"failed: {e}. Continuing — summary save is the "
                f"load-bearing artifact and runs next.",
                exc_info=True,
            )

        try:
            self.broker.auditor.save_summary(summary_path)
        except OSError as e:
            logger.error(
                f"[Finalize] governance_summary.json save failed: "
                f"{e}. Audit CSV + raw JSONL traces are already "
                f"written; downstream consumers can reconstruct the "
                f"summary from those if needed.",
                exc_info=True,
            )

    def _configured_grid_expectation(self, iterations: int) -> dict:
        """This runner's configured agent x year grid.

        S2: the arithmetic lives in
        ``broker.core.run_integrity.configured_grid_expectation`` so the
        single-agent ``run_flood`` path computes it identically instead of
        keeping a second inline copy. This method is the runner's spelling of
        the same call.

        ``getattr``, not ``self.agents``: this runs from ``_finalize_experiment``
        on a FINISHED run, and a partially-built runner (every test that drives
        finalize on an ``__new__``'d instance) has no ``agents`` attribute at
        all. A bare attribute read would raise before the helper's own guard
        could catch it, and take the finalize path down over a side artifact.
        """
        from broker.core.run_integrity import configured_grid_expectation

        return configured_grid_expectation(
            getattr(self, "agents", None), iterations
        )

    def _collect_reproducibility_metadata(self) -> dict:
        """Collect model digest, git state, and config hashes for reproducibility."""
        metadata = {}

        # 1. Query Ollama for model digest
        try:
            import requests
            r = requests.post(
                "http://localhost:11434/api/show",
                json={"name": self.config.model},
                timeout=5,
            )
            if r.status_code == 200:
                info = r.json()
                metadata["model_digest"] = info.get("digest") or info.get("modified_at", "unknown")
                details = info.get("details", {})
                metadata["model_family"] = details.get("family", "unknown")
                metadata["model_parameter_size"] = details.get("parameter_size", "unknown")
                metadata["model_quantization"] = details.get("quantization_level", "unknown")
        except Exception:
            metadata["model_digest"] = "unavailable"

        # 2. Git state, sampled at CONSTRUCTION rather than here.
        #
        # This method runs from _finalize_experiment, which on a 42-year real-LLM run is
        # about ten hours after launch. Sampling `git status` here answered a question
        # nobody asked: it recorded whether the tree was dirty when the run FINISHED.
        # `SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:404` reads the field as a
        # launch-time statement and fails the run on it, so an unrelated commit made
        # while a run was finalising failed a run whose own code path had zero drift
        # (seed 42, 2026-08-06 -- see runs/_logs/seed42_provenance_attestation.md).
        #
        # `git_commit` had the same defect and it is worse there: the recorded commit was
        # one made DURING the run, so the manifest named code the run never executed.
        #
        # Both are now captured in __init__ and replayed here. The finalize-time values
        # are kept alongside under `_at_finalize` names, because a difference between the
        # two is itself informative -- it says the tree moved while the run was in flight.
        metadata["git_commit"] = getattr(self, "_git_commit_at_launch", "unavailable")
        metadata["git_dirty"] = getattr(self, "_git_dirty_at_launch", None)
        try:
            import subprocess
            metadata["git_commit_at_finalize"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
            ).decode().strip()
            metadata["git_dirty_at_finalize"] = len(subprocess.check_output(
                ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
            ).decode().strip()) > 0
        except Exception:
            metadata["git_commit_at_finalize"] = "unavailable"
            metadata["git_dirty_at_finalize"] = None

        # 3. LLM config snapshot
        try:
            from broker.utils.llm_utils import LLM_CONFIG, timeout_env_status
            metadata["thinking_mode"] = LLM_CONFIG.thinking_mode
            metadata["temperature"] = LLM_CONFIG.temperature
            metadata["top_p"] = LLM_CONFIG.top_p
            metadata["num_ctx"] = LLM_CONFIG.num_ctx
            metadata["num_predict"] = LLM_CONFIG.num_predict
            # The timeout this run ACTUALLY used, not the YAML constant: it is
            # the larger of the configured value for this model and the
            # WAGF_LLM_TIMEOUT floor (see LLMConfig.get_timeout). Recorded
            # because a run that was given extra headroom and a run that hit
            # the default are otherwise indistinguishable in the artifact —
            # and "did this model time out, or is it slow?" is the first
            # question asked of a partial batch. Additive field: nothing reads
            # a fixed manifest key set, and byte-identity recipes compare the
            # CSVs, not the manifest.
            metadata["llm_timeout_seconds_effective"] = LLM_CONFIG.get_timeout(
                self.config.model
            )
            # The effective value alone cannot tell "nothing was set" from
            # "something was set and rejected" — both record 120, and the
            # second is a run whose operator believed it had more headroom.
            _raw, _rejected = timeout_env_status()
            metadata["llm_timeout_env_raw"] = _raw
            metadata["llm_timeout_env_rejected"] = _rejected
        except Exception:
            pass

        # 3b. Red-team objection 3 ablation (default "full"; see
        # AgentTypeConfig.get_governance_retry_feedback_mode and
        # RetryMixin._governance_retry_loop). Read off the RESOLVED broker
        # attribute, not re-derived from config, so a CLI override
        # (examples/single_agent/run_flood.py --retry-feedback-mode) is
        # reflected here too. Additive field, same as
        # llm_timeout_seconds_effective above: byte-identity recipes compare
        # the CSVs, not the manifest.
        #
        # ITS OWN try/except (review round 2, S3), not folded into block 3
        # above: this field must be recorded independently of whatever else
        # is or is not available on `self` (a partially-built runner reaching
        # this method before `self.broker` is assigned, or a test double
        # carrying only `.config`, e.g. test_llm_timeout_env_override.py's
        # manifest test) and must never be ABLE to take thinking_mode /
        # temperature / the timeout fields down with it if it were ever to
        # raise. Double-getattr belt-and-braces on top of the isolated try:
        # `self.broker` itself can raise AttributeError (there is no
        # `.broker` attribute at all) before getattr's default would apply to
        # `_retry_feedback_mode`.
        try:
            metadata["retry_feedback_mode"] = getattr(
                getattr(self, "broker", None), "_retry_feedback_mode", "full")
        except Exception:
            metadata["retry_feedback_mode"] = "full"

        # 4. Hash config files
        try:
            import hashlib
            config_path = getattr(self.broker.model_adapter, "config_path", None)
            if config_path:
                from pathlib import Path
                cp = Path(config_path)
                if cp.exists():
                    h = hashlib.sha256(cp.read_bytes()).hexdigest()[:12]
                    metadata["config_hash"] = h
        except Exception:
            pass

        # 4b. Hash of the ORIGINAL config a derived copy came from (additive;
        # same isinstance guard as `derived_from_config` above, so a MagicMock
        # test double never reaches hashlib.sha256 / the JSON write). config_hash
        # above is a byte hash of the DERIVED file (config_path, which a
        # deriving runner repoints at the copy) and is therefore not comparable
        # to this one - see that runner's derive helper docstring.
        # ALWAYS present, default None: every domain's manifest carries this
        # key (matches `derived_from_config`, and the CHANGELOG sentence that
        # both are null unless a runner sets `_derived_from_config`).
        metadata["derived_from_config_sha256"] = None
        try:
            import hashlib
            from pathlib import Path
            _dfc = getattr(self.broker, "_derived_from_config", None)
            # Checked against the CONCRETE `pathlib.Path` class, not
            # `os.PathLike`: `MagicMock` implements `__fspath__` (Python
            # 3.8+), so `isinstance(mock, os.PathLike)` is True for an
            # unconfigured Mock and would let a junk string through here.
            if isinstance(_dfc, (str, Path)):
                _dfc_path = Path(_dfc)
                if _dfc_path.exists():
                    metadata["derived_from_config_sha256"] = hashlib.sha256(
                        _dfc_path.read_bytes()
                    ).hexdigest()[:12]
        except Exception as exc:
            logger.warning(
                "[Finalize] derived_from_config_sha256 skipped: %s", exc
            )

        # 5. Timestamp and Python version
        import sys
        from datetime import datetime
        metadata["timestamp"] = datetime.now().isoformat()
        metadata["python_version"] = sys.version.split()[0]

        # 5.4. Governance-resolution provenance (F9 + F10, 2026-06-10 review).
        #     F10: the manifest recorded only the INTENDED profile
        #     (config.governance_profile); rule loading keys on the
        #     GOVERNANCE_PROFILE env var, so a stale/typo'd env value could
        #     load different rules than the manifest claimed. Record the
        #     RESOLVED value too — a mismatch is now visible in the artifact.
        #     F9: agent types whose RAW config block resolves to {} are
        #     listed (a renamed/typo'd type is completely unknown to the
        #     YAML — the strongest silent-zero-governance signal). NOTE this
        #     raw-block check does NOT catch "block exists but the active
        #     profile resolves zero thinking_rules" — that state is
        #     legitimate by design (ablation `disabled` profile,
        #     documented_unconstrained_skills-only types), so instead of
        #     judging it we RECORD the per-type resolved rule count below
        #     and let the artifact reader decide.
        try:
            import os
            metadata["governance_profile_resolved"] = os.environ.get(
                "GOVERNANCE_PROFILE", "default").lower()
            agent_cfg = getattr(getattr(self.broker, "model_adapter", None),
                                "agent_config", None)
            if agent_cfg is not None and hasattr(agent_cfg, "get"):
                active_types = sorted({
                    getattr(a, "agent_type", "default")
                    for a in self.agents.values()
                })
                zero_rule_types = [
                    t for t in active_types if not agent_cfg.get(t)
                ]
                if zero_rule_types:
                    metadata["agent_types_with_zero_rules"] = zero_rule_types
                if hasattr(agent_cfg, "get_thinking_rules"):
                    metadata["thinking_rules_resolved_counts"] = {
                        t: len(agent_cfg.get_thinking_rules(t))
                        for t in active_types
                    }
            # P0-1c: pin the ARM identity, not just the profile name. Three fields,
            # each recording something a reader cannot recover from the YAML alone.
            #
            # max_retries_resolved is the load-bearing one: SkillBrokerEngine.__init__
            # resolves `max_retries if max_retries != 3 else config.get_governance_retries()`,
            # so an explicit constructor argument SILENTLY beats the YAML — an arm
            # intended as one-retry can quietly run as three, which would break the
            # call-matching the enforcement decomposition depends on. Verify arms from
            # the manifest, never from the config file.
            # Coerced to plain JSON-safe scalars, and shape-checked before use.
            # This block runs inside a try/except, but the manifest is serialised
            # LATER and outside it, so a non-serialisable value here would poison
            # the ENTIRE manifest rather than just dropping one key. Duck-typed
            # brokers (tests, alternate hosts) must degrade to a null, never crash
            # the run's provenance record.
            spec = getattr(self.broker, "_advise_spec", None)
            if isinstance(spec, dict) and isinstance(spec.get("rule_ids"), (list, tuple)):
                metadata["advise_spec_resolved"] = {
                    "mode": str(spec.get("mode", "off")),
                    "rule_ids": sorted(str(r) for r in spec["rule_ids"]),
                }
            else:
                metadata["advise_spec_resolved"] = None
            framing = getattr(self.broker, "_intervention_framing", "legacy")
            metadata["intervention_framing_resolved"] = (
                framing if isinstance(framing, str) else "legacy")
            retries = getattr(self.broker, "max_retries", None)
            # bool is a subclass of int, so exclude it explicitly: recording
            # `true` as a retry count would look plausible and be wrong.
            metadata["max_retries_resolved"] = (
                retries if isinstance(retries, int) and not isinstance(retries, bool)
                else None)
        except Exception as exc:
            logger.debug(f"[Integrity] governance-resolution provenance skipped: {exc}")

        # 5.5. Coupled-world provenance (Phase 6V inc 3, review P0-3). Duck-typed
        #     on purpose: NO broker.coupling import here (flag-OFF runs must never
        #     load that module), and frozen-path raw engines simply lack the
        #     method -> key absent -> manifest unchanged. A coupled run's manifest
        #     must pin the hosted model + contract identity, not just the LLM.
        #     Only a dict result counts as provenance — a Mock/garbage return
        #     (e.g. MagicMock engines in tests) is ignored, never serialized.
        coupling_prov = None
        try:
            prov_fn = getattr(self.sim_engine, "get_provenance", None)
            if callable(prov_fn):
                candidate = prov_fn()
                if isinstance(candidate, dict):
                    coupling_prov = candidate
        except Exception as exc:
            logger.debug(f"[Integrity] coupling provenance skipped: {exc}")
        if coupling_prov is not None:
            metadata["coupling_provenance"] = coupling_prov

        # 5.6. Coupling-RETROFIT provenance (PR-9, F1 remediation). A domain
        #     that validates its own physical-state handoff inline (because
        #     its shape does not fit EnvironmentCouplingAdapter's single-dict
        #     model — see examples/irrigation_abm/irrigation_coupling.py)
        #     reports that fact via this DISTINCT, generically-named hook
        #     rather than ``get_provenance`` — reusing that hook would make
        #     this block's sibling below falsely claim
        #     ``coupling_adapter: True`` for an engine that was never
        #     wrapped. Same duck-typed / no-import-on-absence discipline as
        #     5.5: a raw engine without this method leaves the manifest
        #     unchanged.
        retrofit_meta = None
        retrofit_error = None
        try:
            retrofit_fn = getattr(self.sim_engine, "get_coupling_retrofit_metadata", None)
            if callable(retrofit_fn):
                candidate = retrofit_fn()
                if isinstance(candidate, dict):
                    retrofit_meta = candidate
        except Exception as exc:
            # Review P2: this used to be logger.debug and nothing else, so an
            # engine whose hook RAISED produced a manifest that looked exactly
            # like an engine with no hook at all — the guard reporting its own
            # status is the last place a swallowed failure should hide. Record
            # WHICH failure, and say it at warning level.
            retrofit_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "[Integrity] coupling retrofit metadata unavailable (%s) — "
                "run_integrity.json records the failure rather than an absent "
                "hook.", retrofit_error,
            )
        if retrofit_meta is not None:
            metadata["coupling_retrofit_metadata"] = retrofit_meta
        if retrofit_error is not None:
            metadata["coupling_retrofit_metadata_error"] = retrofit_error

        # 6. Run-integrity provenance contract (Invariant 6): record the RUNTIME memory
        #    engine actually instantiated. config_snapshot.yaml records the CONFIG;
        #    self.memory_engine is the runtime truth, and __init__ silently falls back to
        #    WindowMemoryEngine when no engine is passed — exactly the class of silent
        #    config/runtime divergence Invariant 6 makes inspectable. Writes
        #    run_integrity.json as a side artifact + embeds the audit here. Never raises.
        try:
            from broker.core.run_integrity import record_run_integrity
            refl_kwargs = {}
            if hasattr(self, "reflection_engine"):
                refl_kwargs["reflection_engine"] = self.reflection_engine
            # Coupled runs (sim_engine is an EnvironmentCouplingAdapter) get the
            # runtime fact recorded via the existing ``extra`` extension point —
            # config_snapshot captures the YAML flag layer, but "the engine WAS
            # the adapter" is runtime truth (the Invariant-6 divergence class).
            # Keyed on the VALIDATED provenance from 5.5 (not bare hasattr) so
            # frozen-path / mock engines leave run_integrity.json unchanged.
            if coupling_prov is not None:
                refl_kwargs["extra"] = {
                    "coupling_adapter": True,
                    "sim_engine_class": type(self.sim_engine).__name__,
                }
            # PR-9 (F1): a distinct key from "coupling_adapter" above — this
            # engine reports its OWN inline contract guard, it was never
            # wrapped in EnvironmentCouplingAdapter, so it must never set
            # coupling_adapter=True. Merged (not overwritten) in case a
            # future domain reports both from the same run.
            if retrofit_meta is not None:
                refl_kwargs["extra"] = {**refl_kwargs.get("extra", {}), **retrofit_meta}
            if retrofit_error is not None:
                refl_kwargs["extra"] = {
                    **refl_kwargs.get("extra", {}),
                    "coupling_retrofit_metadata_error": retrofit_error,
                }
            # The configured grid, set by _finalize_experiment just before this
            # runs. Absent on any path that reaches here without finalizing, in
            # which case the coverage block reports "not measured".
            refl_kwargs.update(getattr(self, "_configured_expectation", {}) or {})
            metadata["run_integrity"] = record_run_integrity(
                self.config.output_dir,
                memory_engine=self.memory_engine,
                governance_mode=self.config.governance_profile,
                seed=self.config.seed,
                # The RESOLVED flag, not the YAML's requested one: this is the
                # value the engine actually read, so a flag that failed closed
                # is visible in the artifact rather than only in a log line.
                corrected_status_columns=getattr(
                    self.broker, "_corrected_status_columns", None
                ),
                # isinstance-guarded for the same reason `memory_seed` above is:
                # a MagicMock broker returns a Mock from getattr, and Mock + int
                # raises — which would take the whole integrity record down.
                sentinel_write_failures=(
                    (_bs if isinstance(_bs := getattr(
                        self.broker, "_audit_sentinel_write_failures", 0), int) else 0)
                    + (_rs if isinstance(_rs := getattr(
                        self, "_aborted_trace_write_failures", 0), int) else 0)
                ),
                verbose=False,
                **refl_kwargs,
            )
        except Exception as exc:
            # Manifest enrichment must never fail the run, but don't swallow silently —
            # a module/import error here is a real bug worth surfacing in debug logs.
            logger.debug(f"[Integrity] run_integrity enrichment skipped: {exc}")

        return metadata

    def _apply_state_changes(self, agent: BaseAgent, result: Any):
        """Update agent attributes and memory from execution results.

        Also stores action context on agent._last_action_context for
        deferred feedback by domain pre_year hooks.
        """
        # 1. Update State Flags using canonical method
        if result.execution_result and result.execution_result.state_changes:
            agent.apply_delta(result.execution_result.state_changes)

        # 2. Store action context for deferred feedback by domain pre_year hooks
        action_ctx = {
            "skill_name": result.approved_skill.skill_name,
            "year": getattr(self, '_current_year', 0),
        }
        params = result.approved_skill.parameters or {}
        if params.get("magnitude_pct") is not None:
            action_ctx["magnitude_pct"] = params["magnitude_pct"]
            action_ctx["magnitude_fallback"] = params.get("magnitude_fallback", False)
        if result.execution_result and result.execution_result.action_context:
            action_ctx.update(result.execution_result.action_context)
        agent._last_action_context = action_ctx

        # 3. Legacy immediate memory (kept for backward compat; filtered by
        #    DecisionFilteredMemoryEngine in baseline parity experiments)
        action_desc = result.approved_skill.skill_name.replace("_", " ").capitalize()
        timestamp_prefix = f"Year {self._current_year}: " if hasattr(self, '_current_year') else ""
        memory_content = f"{timestamp_prefix}Decided to: {action_desc}"
        # Phase 6C-v2 (2026-05-10): delegate per-skill emotion/importance
        # to DomainPack instead of hardcoding flood skill names. Flood
        # pack returns the same (major, 0.7) / (positive, 0.6) values
        # the pre-refactor block used; non-flood skills fall through to
        # the routine 0.1 default below.
        memory_metadata = None
        try:
            from broker.domains.registry import DomainPackRegistry
            domain_name = (
                getattr(self.config, "domain", None)
                or getattr(self, "_domain", None)
            )
            # Phase 6R-D-4 (2026-05-26): SkillPack-narrowed accessor —
            # skill_emotion_metadata is owned by SkillPack.
            pack = DomainPackRegistry.get_skill_pack(domain_name)
            pack_metadata = pack.skill_emotion_metadata(
                result.approved_skill.skill_name
            )
            if pack_metadata:
                memory_metadata = dict(pack_metadata)
                memory_metadata.setdefault("source", "personal")
        except ImportError:
            pass

        if memory_metadata is None:
            memory_metadata = {
                "emotion": "routine", "importance": 0.1, "source": "personal"
            }

        if hasattr(self.memory_engine, 'add_memory_for_agent'):
            self.memory_engine.add_memory_for_agent(agent, memory_content, memory_metadata)
        else:
            self.memory_engine.add_memory(agent.id, memory_content, memory_metadata)

    def _partition_by_phase(self, agents: List) -> List[List]:
        """Partition agents into ordered phases based on config.phase_order.

        Each entry in phase_order is a list of agent_type strings.
        Agents whose type matches a phase are grouped together.
        Any agents not matching any phase are appended at the end.
        """
        phase_order = self.config.phase_order or []
        phases: List[List] = [[] for _ in phase_order]
        unmatched = []

        type_to_phase = {}
        for idx, type_group in enumerate(phase_order):
            for atype in type_group:
                type_to_phase[atype] = idx

        for agent in agents:
            atype = getattr(agent, 'agent_type', 'default')
            if atype in type_to_phase:
                phases[type_to_phase[atype]].append(agent)
            else:
                unmatched.append(agent)

        if unmatched:
            # F7 (2026-06-10 review): a typo'd phase_order entry (e.g.
            # 'goverment') silently ran that agent type LAST — inverting the
            # institutional ordering phase_order exists to guarantee. Loud
            # one-line warning naming the unmatched types (warning, not raise:
            # a trailing phase for undeclared types is documented behavior).
            unmatched_types = sorted({getattr(a, 'agent_type', 'default') for a in unmatched})
            logger.warning(
                f"[Lifecycle:PhaseOrder] agent type(s) {unmatched_types} match NO "
                f"phase_order entry {self.config.phase_order} — they run as a "
                f"TRAILING phase. If ordering matters for them, fix the "
                f"phase_order spelling."
            )
            phases.append(unmatched)
        return phases

    def _finalize_step(self, step: int):
        """Unified finalization logic per cycle."""
        # Notify audit writer to flush if needed
        if hasattr(self.broker.audit_writer, 'finalize'):
             # Future: per-step flushing could be added here
             pass

    def _finalize_year(self, year: int):
        """Legacy alias for _finalize_step."""
        self._finalize_step(year)

    def _run_agents_sequential(self, agents: List, run_id: str, llm_invoke: Callable, env: Dict) -> List:
        """Execute agent steps sequentially. Default mode."""
        results = []
        for agent in agents:
            # PR-8 review P1-c: a DECLARED decider is bound OUTSIDE the try.
            # The handler below exists for a decision that failed at
            # runtime — a model timing out — and turns what it catches into
            # an ABORTED sentinel. A decider that cannot be built is not
            # that: it is a config error, and swallowing it produced a run
            # that exited 0 with one arm entirely aborted. The default path
            # is untouched — `llm` still resolves inside the try, from the
            # same cache, at the same point it always did.
            _atype = getattr(agent, 'agent_type', 'default')
            _declared_decider = (
                None if self.get_decider_spec(_atype).is_default
                else self.get_decider(
                    _atype, agent=agent, agent_id=agent.id, env=env)
            )
            try:
                self.step_counter += 1

                # [Efficiency Hub] Cognitive Cache Check (opt-in, F4).
                # NOTE (F4 byte-identity correction, 2026-06-10): the early
                # context build is UNCONDITIONAL even with the cache disabled —
                # UniversalCognitiveEngine.retrieve() updates its EMA surprise
                # predictor per call (universal.py:_compute_surprise), so every
                # frozen baseline (SA-flood) was produced with TWO builds per
                # step. Skipping this build would halve the EMA update count
                # and break mock byte-reproduction. Only the side-effect-free
                # hash/get/put are gated. (The double build stays a documented
                # perf debt, not a correctness lever.)
                ctx_builder = self.broker.context_builder
                # Build context early to compute hash
                context = ctx_builder.build(agent.id, env_context=env)
                context_hash = None
                cached_data = None
                if self.efficiency is not None:
                    context_hash = self.efficiency.compute_hash(context)
                    cached_data = self.efficiency.get(context_hash)
                if cached_data:
                    logger.info(f"[Efficiency] Cache HIT for {agent.id} (Hash={context_hash[:8]}). Bypassing LLM.")
                    # Reconstruct result from cache

                    # Restore reasoning metadata to ensure AuditWriter can find appraisals
                    cached_proposal = cached_data.get("skill_proposal") or {}
                    proposal = _rebuild_cached_proposal(
                        cached_proposal,
                        skill_name=(cached_proposal.get("skill_name") or self.broker.skill_registry.get_default_skill()),
                        agent_id=agent.id,
                        reasoning=cached_proposal.get("reasoning", {}),
                        agent_type=cached_proposal.get("agent_type", "default"),
                    )

                    # Basic reconstruction (Logic here should match SkillBrokerResult structure)
                    result = SkillBrokerResult(
                        outcome=SkillOutcome(cached_data.get("outcome", "APPROVED")),
                        skill_proposal=proposal, # Restore proposal for audit
                        approved_skill=ApprovedSkill(
                            skill_name=(cached_data.get("approved_skill", {}).get("skill_name") or self.broker.skill_registry.get_default_skill()),
                            agent_id=agent.id,
                            approval_status="APPROVED",
                            execution_mapping=cached_data.get("approved_skill", {}).get("mapping", "sim.noop")
                        ),
                        execution_result=ExecutionResult(
                            success=True,
                            state_changes=cached_data.get("execution_result", {}).get("state_changes", {})
                        ),
                        validation_errors=[],
                        retry_count=0
                    )
                    if hasattr(self.broker, "_run_validators"):
                        # validation re-run intentionally uses the APPROVED skill_name
                        # + the CURRENT agent's agent_type (not the cached/proposed ones);
                        # only `parameters` is threaded from the cached proposal.
                        cached_proposal_obj = _rebuild_cached_proposal(
                            cached_proposal,
                            skill_name=(cached_data.get("approved_skill", {}).get("skill_name") or self.broker.skill_registry.get_default_skill()),
                            agent_id=agent.id,
                            reasoning=cached_proposal.get("reasoning", {}),
                            agent_type=getattr(agent, 'agent_type', 'default'),
                        )
                        # Wrap context the same way process_step() does for custom validators
                        cache_validation_context = {
                            "agent_state": context,
                            "agent_type": getattr(agent, 'agent_type', 'default'),
                            "env_state": env,
                            **context.get("state", {}),
                            **env
                        }
                        val_results = self.broker._run_validators(cached_proposal_obj, cache_validation_context)
                        if not all(v.valid for v in val_results):
                            logger.warning(f"[Efficiency] Cache HIT for {agent.id} INVALIDATED by governance. Re-running.")
                            self.efficiency.invalidate(context_hash)
                        else:
                            results.append((agent, result))
                            continue
                    else:
                        results.append((agent, result))
                        continue

                result = self.broker.process_step(
                    agent_id=agent.id,
                    step_id=self.step_counter,
                    run_id=run_id,
                    seed=self.config.seed + self.step_counter,
                    # PR-8: argument-for-argument what it was before for
                    # every agent type that declares no `decider:`.
                    llm_invoke=(_declared_decider if _declared_decider is not None
                                else self.get_llm_invoke(_atype)),
                    agent_type=_atype,
                    env_context=env,
                    **self._decider_kwargs(_atype),
                )

                # Store validated result in cache (opt-in, F4)
                if self.efficiency is not None and result.outcome in [SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS]:
                    # We store the raw_output or structured decision
                    self.efficiency.put(context_hash, result.to_dict())

                results.append((agent, result))
            except Exception as e:
                # F1 fix (post-Phase-6T silent-failure audit, 2026-05-27):
                # pre-fix path logged + dropped the agent from `results`,
                # shrinking the audit-CSV denominator silently — the
                # v0.88.15-class bug (green tests, plausible numbers,
                # biased science). Cross-model comparison especially at
                # risk: small Gemma variants timed out more often, so
                # their effective N differed from the larger models'
                # without any signal in the output artifacts.
                logger.error(
                    f"[Sequential] Agent {agent.id} failed: {e}",
                    exc_info=True,
                )
                self._write_aborted_trace(agent, run_id, env, e)
                error_result = SkillBrokerResult(
                    outcome=SkillOutcome.ABORTED,
                    skill_proposal=None,
                    approved_skill=None,
                    execution_result=None,
                    validation_errors=[
                        f"agent_step_exception: {type(e).__name__}: "
                        f"{str(e)[:500]}"
                    ],
                )
                results.append((agent, error_result))
        return results

    def _write_aborted_trace(
        self,
        agent,
        run_id: str,
        env: Dict,
        error: Exception,
        step_id: Optional[int] = None,
    ) -> None:
        """F1 fix (post-Phase-6T audit, 2026-05-27): emit a sentinel
        audit trace for an agent whose step raised.

        Without this trace, the failed agent vanishes from the audit
        CSV — the v0.88.15-class denominator-shrink pattern. The
        sentinel carries enough context (agent_id, agent_type, year,
        step_id, error_type, error_msg) for downstream consumers to
        detect + filter aborted steps. Most other fields are empty
        / None — the audit row builder fills them with defaults.

        Robust against audit-writer failure: a secondary
        audit-write exception is caught + logged so it never masks
        the original step exception.

        Shared by ``_run_agents_sequential`` (F1) and
        ``_run_agents_parallel`` (F4 — pre-existing same-pattern bug
        in the parallel path; not in scope for this commit but the
        helper is structured so the F4 fix is a one-line addition).
        """
        from datetime import datetime

        error_type = type(error).__name__
        error_msg = str(error)[:500]
        agent_type = getattr(agent, 'agent_type', 'default')
        # F6 (2026-06-10 review): under workers>1 every parallel failure used
        # to surface after ALL submissions, so self.step_counter was the LAST
        # agent's step — every sentinel carried the wrong step_id/seed. The
        # parallel path now threads the SUBMITTED step_id; the sequential path
        # passes None and keeps the live counter (correct there).
        sentinel_step = step_id if step_id is not None else self.step_counter

        try:
            audit_writer = getattr(self.broker, 'audit_writer', None)
            if audit_writer is None:
                return
            trace = {
                "run_id": run_id,
                "step_id": sentinel_step,
                "timestamp": datetime.now().isoformat(),
                "year": env.get("current_year") if isinstance(env, dict) else None,
                "seed": self.config.seed + sentinel_step,
                "agent_id": agent.id,
                "agent_type": agent_type,
                "model": getattr(self, '_model_name', 'unknown'),
                "decision_source": "exception",
                "validated": False,
                "fallback_activated": False,
                "status": "ABORTED_EXCEPTION",
                "outcome": SkillOutcome.ABORTED.value,
                "validation_errors": [
                    f"agent_step_exception: {error_type}: {error_msg}"
                ],
                "retry_count": 0,
                "format_retries": 0,
            }
            # P1a: the `status` key above is TOP-LEVEL, but `trace_to_csv_row`
            # reads the status column off `approved_skill` — so this sentinel's
            # CSV cell has always said `UNKNOWN`, and the one row written to
            # make a crashed step visible named the crash nowhere the CSV
            # reader could see it. Giving it an `approved_skill` with an empty
            # skill name and the real status fixes the cell.
            #
            # Under the corrected-columns flag ONLY: `approved_skill` also
            # feeds `final_skill` and `mapping`, and a frozen corpus rerun with
            # the flag OFF must stay byte-identical, `UNKNOWN` included. With
            # the flag OFF this row is NOT countable from the CSV (`status`
            # is the only signal `audit_coverage` reads); it survives only in
            # `raw/*_traces.jsonl` as `decision_source == "exception"`.
            if getattr(self.broker, "_corrected_status_columns", False) is True:
                trace["approved_skill"] = {
                    "skill_name": "", "status": "ABORTED_EXCEPTION", "mapping": "",
                }
                trace["executed_skill"] = ""
                trace["executed_via_fallback"] = False
                trace["execution_path"] = "aborted"
            # PR-8: attribute the crashed step to whatever was SUPPOSED to
            # decide it. Without this the one row written to make a crash
            # visible is the one row with no decider, so a mixed-population
            # CSV grouped by `decider` shows a blank category and the
            # per-decider census silently loses the row. Emits nothing when
            # the columns are off, so no frozen corpus gains a key.
            # The PATH is forced to "aborted" (review P1-c): the step
            # crashed, so no decision path was taken, and letting the
            # sentinel inherit the decider's default path would put a row
            # in the per-decider census as though it had decided.
            decider_extra = getattr(self.broker, "_decider_audit_extra", None)
            if callable(decider_extra):
                try:
                    trace.update(decider_extra(
                        self._decider_audit_name(agent_type), path="aborted"))
                except Exception as exc:  # noqa: BLE001 — provenance only
                    logger.debug(f"[AbortedTrace] decider provenance: {exc}")
            audit_writer.write_trace(agent_type, trace)
        except Exception as audit_err:
            # P2d: count it. This is a row that should exist and does not —
            # the denominator hole the F1 fix was written to close, and until
            # now it lived only in the console log.
            self._aborted_trace_write_failures = (
                getattr(self, "_aborted_trace_write_failures", 0) + 1
            )
            logger.error(
                f"[AbortedTrace] Secondary audit-writer failure for "
                f"agent {agent.id} (original error was "
                f"{error_type}: {error_msg}): {audit_err}",
                exc_info=True,
            )

    def _run_agents_parallel(self, agents: List, run_id: str, llm_invoke: Callable, env: Dict) -> List:
        """Execute agent steps in parallel using ThreadPoolExecutor."""
        results = []

        def process_agent(agent, step_id, declared_decider=None):
            # ``declared_decider`` is bound on the SUBMITTING thread (see
            # the submit loop) — PR-8 review P1-c. Everything raised inside
            # this function is caught at ``future.result()`` and turned into
            # an ABORTED sentinel, which is right for a decision that failed
            # at runtime and wrong for a decider that could not be built.
            # [Efficiency Hub] Cognitive Cache Check (opt-in, F4). Early
            # context build is UNCONDITIONAL — see the sequential-path note
            # (universal engine's EMA updates per build; frozen baselines
            # were produced with two builds per step).
            ctx_builder = self.broker.context_builder
            context = ctx_builder.build(agent.id, env_context=env)
            context_hash = None
            cached_data = None
            if self.efficiency is not None:
                context_hash = self.efficiency.compute_hash(context)
                cached_data = self.efficiency.get(context_hash)
            if cached_data:
                logger.info(f"[Efficiency:Parallel] Cache HIT for {agent.id} (Hash={context_hash[:8]}). Bypassing LLM.")

                cached_proposal = cached_data.get("skill_proposal") or {}
                proposal = _rebuild_cached_proposal(
                    cached_proposal,
                    skill_name=(cached_proposal.get("skill_name") or self.broker.skill_registry.get_default_skill()),
                    agent_id=agent.id,
                    reasoning=cached_proposal.get("reasoning", {}),
                    agent_type=cached_proposal.get("agent_type", "default"),
                )

                result = SkillBrokerResult(
                    outcome=SkillOutcome(cached_data.get("outcome", "APPROVED")),
                    skill_proposal=proposal,
                    approved_skill=ApprovedSkill(
                        skill_name=(cached_data.get("approved_skill", {}).get("skill_name") or self.broker.skill_registry.get_default_skill()),
                        agent_id=agent.id,
                        approval_status="APPROVED",
                        execution_mapping=cached_data.get("approved_skill", {}).get("mapping", "sim.noop")
                    ),
                    execution_result=ExecutionResult(
                        success=True,
                        state_changes=cached_data.get("execution_result", {}).get("state_changes", {})
                    ),
                    validation_errors=[],
                    retry_count=0
                )
                if hasattr(self.broker, "_run_validators"):
                    # validation re-run intentionally uses the APPROVED skill_name
                    # + the CURRENT agent's agent_type (not the cached/proposed ones);
                    # only `parameters` is threaded from the cached proposal.
                    cached_proposal_obj = _rebuild_cached_proposal(
                        cached_proposal,
                        skill_name=(cached_data.get("approved_skill", {}).get("skill_name") or self.broker.skill_registry.get_default_skill()),
                        agent_id=agent.id,
                        reasoning=cached_proposal.get("reasoning", {}),
                        agent_type=getattr(agent, 'agent_type', 'default'),
                    )
                    # Wrap context the same way process_step() does for custom validators
                    cache_validation_context = {
                        "agent_state": context,
                        "agent_type": getattr(agent, 'agent_type', 'default'),
                        "env_state": env,
                        **context.get("state", {}),
                        **env
                    }
                    val_results = self.broker._run_validators(cached_proposal_obj, cache_validation_context)
                    if not all(v.valid for v in val_results):
                        logger.warning(f"[Efficiency:Parallel] Cache HIT for {agent.id} INVALIDATED by governance. Re-running.")
                        self.efficiency.invalidate(context_hash)
                    else:
                        return agent, result
                else:
                    return agent, result

            _atype = getattr(agent, 'agent_type', 'default')
            result = self.broker.process_step(
                agent_id=agent.id,
                step_id=step_id,
                run_id=run_id,
                seed=self.config.seed + step_id,
                # PR-8: argument-for-argument what it was before for every
                # agent type that declares no `decider:`.
                llm_invoke=(declared_decider if declared_decider is not None
                            else self.get_llm_invoke(_atype)),
                agent_type=_atype,
                env_context=env,
                **self._decider_kwargs(_atype),
            )

            if self.efficiency is not None and result.outcome in [SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS]:
                self.efficiency.put(context_hash, result.to_dict())

            return agent, result

        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {}
            for agent in agents:
                self.step_counter += 1
                # PR-8 review P1-c: bind a DECLARED decider here, on the
                # submitting thread, so a build failure raises out of this
                # loop instead of arriving at `future.result()` where the
                # F4 handler would file it as an aborted agent-year.
                _atype = getattr(agent, 'agent_type', 'default')
                _declared = (
                    None if self.get_decider_spec(_atype).is_default
                    else self.get_decider(
                        _atype, agent=agent, agent_id=agent.id, env=env)
                )
                # F6: keep the SUBMITTED step_id with the future so a failure
                # sentinel carries the right step/seed (post-submission,
                # self.step_counter is already the last agent's value).
                futures[executor.submit(
                    process_agent, agent, self.step_counter, _declared,
                )] = (agent, self.step_counter)

            for future in as_completed(futures):
                try:
                    agent, result = future.result()
                    results.append((agent, result))
                except Exception as e:
                    # F4 fix (post-Phase-6T silent-failure audit,
                    # 2026-05-27): parallel mirror of F1. The
                    # ``_write_aborted_trace`` helper was deliberately
                    # designed during the F1 fix so this becomes a
                    # one-line shim instead of duplicating sentinel
                    # logic across two exception handlers. Without
                    # this fix, ``workers > 1`` runs (e.g.
                    # ``--workers 4`` for MA flood scale-up) had the
                    # same v0.88.15-class denominator-shrink: failed
                    # agents vanished from the audit CSV.
                    failed_agent, failed_step = futures[future]
                    logger.error(
                        f"[Parallel] Agent {failed_agent.id} failed: {e}",
                        exc_info=True,
                    )
                    self._write_aborted_trace(failed_agent, run_id, env, e,
                                              step_id=failed_step)
                    error_result = SkillBrokerResult(
                        outcome=SkillOutcome.ABORTED,
                        skill_proposal=None,
                        approved_skill=None,
                        execution_result=None,
                        validation_errors=[
                            f"agent_step_exception: {type(e).__name__}: "
                            f"{str(e)[:500]}"
                        ],
                    )
                    results.append((failed_agent, error_result))

        return results
