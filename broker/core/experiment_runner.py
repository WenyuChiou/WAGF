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
from ..utils.llm_safeguard import (
    LLMSafeguardConfig, LLMFailureRateAborted, wrap_llm_invoke_with_backoff,
)
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
    # Crash-resume journal (broker/utils/llm_journal.py), both default None
    # so no existing run changes a single byte. llm_journal_path: when set,
    # every LLM call this run makes is appended to that JSONL file.
    # resume_journal_path: when set, a prior run's journal to replay from --
    # see ExperimentRunner._build_llm_journal_manager and
    # broker.utils.llm_journal.LLMJournalManager for the mechanism.
    llm_journal_path: Optional[Path] = None
    resume_journal_path: Optional[Path] = None

# Substrings that identify the runner's own immediate decision memories
# (written by ExperimentRunner._apply_state_changes). Domains that filter
# these lines out of memory (e.g. a baseline-parity proxy engine) should
# match on both markers.
DECISION_MEMORY_MARKER = "Decided to:"
FALLBACK_MEMORY_MARKER = "default action applied:"


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
        self._capture_model_metadata_at_launch()
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

        # Crash-resume journal (broker/utils/llm_journal.py), built lazily by
        # run() -- see _build_llm_journal_manager -- so a caller that sets an
        # identifying-config attribute on the runner between build() and
        # run() (the same `runner.broker._xxx = ...` idiom already used for
        # _derived_from_config / _retry_feedback_mode) is picked up before
        # the header is written. None for every run that never sets
        # ExperimentConfig.llm_journal_path / resume_journal_path, which
        # keeps get_llm_invoke's wrapping chain byte-identical to before
        # this feature existed.
        self._llm_journal = None

        # r19 G7/G8: the merged Ollama sampling/context params actually
        # resolved for each agent type this run creates an invoke for (see
        # get_llm_invoke and _collect_reproducibility_metadata's
        # llm_params_resolved block). Populated lazily, same lifecycle as
        # _llm_cache: an agent type never invoked never appears here.
        self._llm_resolved_params: Dict[str, Dict[str, Any]] = {}
        from broker.utils.llm_utils import ollama_thinking_sequence
        self._llm_thinking_started = ollama_thinking_sequence()
        self._llm_thinking_observations = {}

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
            # A cache hit replays a proposal from an EARLIER decision and
            # re-validates it outside process_step, where the appraisal
            # freeze (global_config.governance.appraisal_freeze) has no
            # first-stated labels to read; refused rather than letting a hit
            # silently bypass the freeze.
            if getattr(broker, "_appraisal_freeze", False) is True:
                raise ValueError(
                    "ExperimentConfig.enable_cognitive_cache cannot be combined "
                    "with global_config.governance.appraisal_freeze: a cache hit "
                    "re-validates a proposal outside the decision whose first "
                    "stated labels the freeze reads. Turn one of them off."
                )
            persistence_path = config.output_dir / "cognitive_cache.json"
            self.efficiency = CognitiveCache(persistence_path=persistence_path)
        else:
            self.efficiency = None

    def _capture_model_metadata_at_launch(self) -> None:
        """Capture a real model digest once, before the experiment starts.

        Mock and cloud-provider runs never contact Ollama.  A successful
        ``/api/show`` response is retained by ``llm_utils`` for thinking-mode
        capability resolution.  Ollama versions whose show response omits a
        digest use the matching entry in ``/api/tags``; ``modified_at`` is
        deliberately never accepted as a digest.
        """
        model_metadata: Dict[str, Any] = {"model_digest": None}
        try:
            import http.client
            import requests
            from broker.utils.llm_utils import (
                get_ollama_base_url,
                get_ollama_show_metadata,
                is_cloud_provider_model,
                is_mock_model,
            )

            model = getattr(self.config, "model", None)
            if not isinstance(model, str) or is_mock_model(model) or is_cloud_provider_model(model):
                self._model_metadata_at_launch = model_metadata
                return

            endpoint = get_ollama_base_url().rstrip("/")
            info = get_ollama_show_metadata(model, base_url=endpoint, refresh=True)
            details = info.get("details") if isinstance(info.get("details"), dict) else {}
            model_metadata.update({
                "model_family": details.get("family", "unknown"),
                "model_parameter_size": details.get("parameter_size", "unknown"),
                "model_quantization": details.get("quantization_level", "unknown"),
            })
            digest = info.get("digest")
            if not isinstance(digest, str) or not digest.strip():
                tags_response = requests.get(f"{endpoint}/api/tags", timeout=5)
                tags_response.raise_for_status()
                tags = tags_response.json()
                models = tags.get("models", []) if isinstance(tags, dict) else []
                match = next((
                    item for item in models
                    if isinstance(item, dict)
                    and item.get("name", item.get("model")) in (
                        model, model if ":" in model else f"{model}:latest")
                ), None)
                digest = match.get("digest") if match is not None else None
            model_metadata["model_digest"] = (
                digest.strip() if isinstance(digest, str) and digest.strip() else None
            )
        except (
            OSError,
            ValueError,
            TypeError,
            requests.RequestException,
            http.client.HTTPException,
        ):
            model_metadata["model_digest"] = None
        if model_metadata["model_digest"] is None:
            logger.warning(
                "[Reproducibility] Local model digest is unavailable at launch "
                "for %r; the manifest will record model_digest=null.",
                model,
            )
        self._model_metadata_at_launch = model_metadata

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
            from broker.utils.llm_utils import (
                create_llm_invoke, resolve_ollama_params, is_cloud_provider_model,
            )
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

            # r19 G7/G8: record the SAME thing create_llm_invoke is about to
            # send, via the shared helper, so the reproducibility manifest can
            # report what this agent type actually sends instead of the
            # LLM_CONFIG singleton alone. Computed here rather than re-derived
            # at finalize time so it can never disagree with the invoke this
            # cache entry is about to hold. The resolved model name is stored
            # alongside the params (llm_params_resolved[<type>]["model"]),
            # since a per-type llm_params.model override means different
            # agent types in the same run can send to different models.
            #
            # Cloud-provider models (is_cloud_provider_model, the SAME check
            # create_llm_invoke's own routing uses) never reach
            # resolve_ollama_params at all: create_provider_invoke's config is
            # {"type", "model"} updated with the RAW overrides dict, never
            # merged with LLM_CONFIG. Recording resolve_ollama_params() for a
            # cloud model would show num_ctx/num_predict/temperature values
            # the provider path never even looks at, so the raw overrides are
            # recorded instead: that IS what the provider path receives.
            if is_cloud_provider_model(model_name):
                resolved_params = dict(overrides)
            else:
                resolved_params = resolve_ollama_params(overrides)
            resolved_params["model"] = model_name if isinstance(model_name, str) else None

            # getattr, not a bare self._llm_resolved_params: several tests
            # build a runner with ExperimentRunner.__new__ and never run
            # __init__ (see get_decider_spec for the same pattern), and this
            # provenance cache is not a reason for those to break.
            resolved_cache = getattr(self, "_llm_resolved_params", None)
            if resolved_cache is None:
                resolved_cache = {}
                self._llm_resolved_params = resolved_cache
            resolved_cache[agent_type] = resolved_params

            raw_invoke = create_llm_invoke(
                model_name,
                verbose=self.config.verbose,
                overrides=overrides
            )
            # Scope wire observations to this runner, even when other runners
            # use the same model concurrently. Enter inside the callable so
            # every worker thread gets its own context; journal replay skips it.
            from broker.utils.llm_utils import capture_ollama_thinking
            observations = getattr(self, "_llm_thinking_observations", None)
            if observations is None:
                observations = self._llm_thinking_observations = {}

            def observed_invoke(*args, **kwargs):
                with capture_ollama_thinking(observations):
                    return raw_invoke(*args, **kwargs)

            # Spec item 24 (audit gap F42): backoff on a transient provider
            # failure, wired HERE because this is the one choke point every
            # LLM call in the framework passes through (the format-retry
            # loop, the governance retry loop, the advisory pass, the
            # hybrid decider all call get_llm_invoke(agent_type) or reuse
            # this cache entry). A no-op wrapper (returns raw_invoke
            # unchanged) unless global_config.llm_safeguard.enabled is true,
            # which is what keeps every domain that has not opted in
            # byte-identical.
            backoff_wrapped = wrap_llm_invoke_with_backoff(
                observed_invoke, self._resolve_llm_safeguard_config(),
            )
            # Crash-resume journal (broker/utils/llm_journal.py), wired
            # OUTSIDE (on top of) the backoff wrapper so a replayed call
            # skips backoff sleeps entirely -- it is answered from the
            # journal and never reaches backoff_wrapped or raw_invoke at
            # all. None for every run that never sets
            # ExperimentConfig.llm_journal_path / resume_journal_path (see
            # _build_llm_journal_manager), which keeps this cache entry
            # exactly backoff_wrapped, unchanged, for every existing run.
            journal = getattr(self, "_llm_journal", None)
            self._llm_cache[agent_type] = (
                journal.wrap(agent_type, backoff_wrapped) if journal is not None
                else backoff_wrapped
            )
        return self._llm_cache[agent_type]

    def _resolve_llm_safeguard_config(self) -> LLMSafeguardConfig:
        """Resolved ``global_config.llm_safeguard`` (spec item 24), cached
        after the first call.

        Read off ``self.broker.config`` -- the SAME ``AgentTypeConfig``
        ``SkillBrokerEngine.__init__`` reads for its own copy (the abort-rate
        tracker) -- so the backoff wrapper here and the abort tracker there
        can never resolve to different settings for one run. Defensive the
        same way ``overrides`` just above is: a broker/config predating this
        feature, or a MagicMock test double, degrades to the disabled
        default rather than raising.
        """
        cached = getattr(self, "_llm_safeguard_cfg", None)
        if cached is not None:
            return cached
        get_cfg = None
        if hasattr(self.broker, 'config') and self.broker.config:
            get_cfg = getattr(self.broker.config, "get_llm_safeguard_config", None)
        raw = get_cfg() if callable(get_cfg) else None
        resolved = (
            LLMSafeguardConfig.from_dict(raw) if isinstance(raw, dict)
            else LLMSafeguardConfig()
        )
        self._llm_safeguard_cfg = resolved
        return resolved

    def _build_llm_journal_manager(self):
        """The run's :class:`~broker.utils.llm_journal.LLMJournalManager`,
        or ``None`` when neither journal config field is set.

        Called once, as the first statement of :meth:`run`, so it runs
        before ``self.llm_invoke`` (hence ``get_llm_invoke("default")``) is
        touched by anything else in ``run`` -- see that method's own first
        lines. Building it any later would let an earlier ``get_llm_invoke``
        call cache an agent type's invoke WITHOUT journal wrapping forever
        (the cache never re-wraps an already-cached entry).

        The header's identifying config is built from whatever this
        generic layer already knows (model, seed, the memory engine's own
        seed, governance profile, step/year count, git commit + dirty
        flag at launch) PLUS ``self._llm_journal_identifying_extra`` when
        a caller set that attribute directly on the runner between
        ``build()`` and ``run()`` -- the same idiom this codebase already
        uses for ``runner.broker._derived_from_config`` and
        ``runner.broker._retry_feedback_mode``. A domain CLI flag with no
        generic home has no place in this generic dict; it belongs in
        that extra mapping, set by the domain's own runner script, which
        is also where the actual "refuse to resume on a changed
        identifying setting" check belongs
        (broker.utils.llm_journal.check_identifying_config).
        """
        journal_path = getattr(self.config, "llm_journal_path", None)
        resume_path = getattr(self.config, "resume_journal_path", None)
        if not journal_path and not resume_path:
            return None
        from broker.utils.llm_journal import LLMJournalManager

        header: Dict[str, Any] = {
            "model": self.config.model,
            "seed": self.config.seed,
            "memory_seed": (
                _ms if isinstance(_ms := getattr(self.memory_engine, "seed", None), int)
                else None
            ),
            "governance_profile": self.config.governance_profile,
            "num_years": self.config.num_years,
            "num_steps": self.config.num_steps,
            # NOT an identifying field for resume (a domain's own
            # allowed_to_differ must list it, and a domain runner's own
            # identifying-config dict deliberately leaves --workers out
            # for exactly this reason): recorded here so a LATER provenance guard reading
            # this run's own header as a resume SOURCE (see
            # broker.utils.llm_journal.LLMJournalManager.provenance_metadata's
            # source_workers) can tell what worker count the replayed
            # portion of a resumed run actually came from.
            "workers": self.config.workers,
            # Reuses the SAME capture __init__ already made (see its own
            # comment on why construction time, not finalize time, is the
            # right moment) -- no extra git subprocess call. Sampling
            # params and prompt templates live in files a domain's own
            # preflight check hashes separately (its own
            # _llm_journal_identifying_extra); code identity itself is
            # generic and belongs here.
            "git_commit": getattr(self, "_git_commit_at_launch", "unavailable"),
            "git_dirty": getattr(self, "_git_dirty_at_launch", None),
        }
        extra = getattr(self, "_llm_journal_identifying_extra", None)
        if isinstance(extra, dict):
            header.update(extra)

        return LLMJournalManager(
            header=header,
            output_path=Path(journal_path) if journal_path else None,
            resume_from=Path(resume_path) if resume_path else None,
        )

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
           per agent). REJECTED/UNCERTAIN rows get ``_apply_state_changes``
           only when the broker actually executed a skill on them (the
           registry default run as a fallback, or the kept proposal under
           ``on_retry_exhausted: keep_proposal``); rows where nothing executed
           reach post_step with no state/memory application. ABORTED results
           carry ``skill_proposal=None``; hooks must tolerate that.
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
        # Crash-resume journal: built HERE, as the first statement of run(),
        # before anything below touches self.llm_invoke (hence
        # get_llm_invoke) -- see _build_llm_journal_manager's own docstring
        # for why the ordering matters. getattr-guarded: a runner built via
        # __new__ in a test, bypassing __init__, has no _llm_journal
        # attribute at all, and that must not turn into an AttributeError
        # here.
        from broker.utils.llm_journal import JournalReplayDivergence, JournalWriteError
        from broker.utils.llm_utils import ollama_thinking_sequence
        self._llm_thinking_started = ollama_thinking_sequence()
        observations = getattr(self, "_llm_thinking_observations", None)
        if observations is None:
            self._llm_thinking_observations = {}
        else:
            observations.clear()
        if getattr(self, "_llm_journal", None) is None:
            self._llm_journal = self._build_llm_journal_manager()
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
        # Spec item 24 fix round: reset at the TOP of every run(), not only
        # set on abort. Without this, a SECOND run() on the same instance
        # (a reused runner, a test harness) that finishes cleanly would still
        # carry the FIRST run's abort and stamp a clean corpus's manifest
        # with run_status: aborted_llm_failure_rate.
        self._llm_safeguard_abort = None
        # Crash-resume journal: same reset-at-the-top discipline as the
        # safeguard abort above, for the SAME reason (a reused runner's
        # second run() must not inherit the first run's abort stamp).
        self._llm_journal_abort = None
        # Opus review of WP7 launcher, round 2 (non-blocking): the generic
        # abort added in round 1 needs the SAME reset-at-the-top discipline
        # as the two above, for the same reason.
        self._generic_abort = None
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
                            # The broker may still have EXECUTED a skill on this
                            # row: the registry default as a fallback, or the
                            # agent's own proposal under keep_proposal. Apply
                            # what executed (state + action context + memory)
                            # exactly once, here; when nothing executed (no
                            # engine, no registered default, failed execution)
                            # the row changes no state and writes no memory.
                            if self._executed_on_rejected_row(result):
                                self._apply_state_changes(agent, result)
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
                # Crash-resume journal: the step-end marker. Written AFTER
                # _finalize_step so a crash mid-step (before this line runs)
                # leaves the journal with no marker for this step, and a
                # resume correctly treats the whole step as partial (see
                # broker.utils.llm_journal.load_journal_for_resume). For a
                # step still being replayed this also raises
                # JournalReplayDivergence if any of that step's recorded
                # calls were never consumed -- deliberately NOT caught here,
                # same as LLMFailureRateAborted below: this must stop the
                # run, not become another ABORTED row.
                journal = getattr(self, "_llm_journal", None)
                if journal is not None:
                    journal.step_end(step)
        except LLMFailureRateAborted as exc:
            # Spec item 24: stash the exception BEFORE `finally` runs, so
            # `_finalize_experiment`'s manifest build (unconditional, below)
            # can see it and record `run_status` -- reading it off `self`
            # rather than threading it through `_finalize_experiment`'s
            # signature, since `finally` cannot see the exception object
            # directly. Re-raised unchanged: the run still exits non-zero
            # with a one-line reason (this exception's own message).
            self._llm_safeguard_abort = exc
            raise
        except (JournalReplayDivergence, JournalWriteError) as exc:
            # Crash-resume journal: same stash-before-finally treatment as
            # LLMFailureRateAborted above, for the same reason -- the
            # manifest build in _finalize_experiment's unconditional
            # finally must be able to see this and record run_status.
            self._llm_journal_abort = exc
            raise
        except BaseException as exc:
            # Opus review of WP7 launcher, item 3(a): the two guards above only
            # cover their own two narrow exception families. Any OTHER
            # exception escaping the loop above (a provider error, a bug in a
            # hook, anything not LLMFailureRateAborted/JournalReplayDivergence/
            # JournalWriteError) used to fall straight through to `finally`
            # with neither `_llm_safeguard_abort` nor `_llm_journal_abort` set,
            # so `_finalize_experiment`'s manifest build below added no
            # `run_status` key at all -- indistinguishable from a normal
            # completion that merely covered fewer years than configured. Same
            # stash-before-finally pattern as the two guards above, generalised.
            # Round 2 (non-blocking): BaseException, not Exception, so
            # KeyboardInterrupt and SystemExit are recorded too -- still
            # re-raised unchanged either way, this only adds a record of why.
            self._generic_abort = exc
            raise
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
        # Spec item 24 (audit gap F42): when the LLM-failure abort-rate
        # safeguard stopped this run, say so IN THE MANIFEST, not only in the
        # exception that already ended the process. `run()`'s own
        # except-before-finally clause sets `self._llm_safeguard_abort`
        # before this method runs (it is called from that `finally`), so the
        # value is available here regardless of how deep inside the step the
        # raise happened. Absent (no key at all, not `null`) on every run the
        # safeguard did not abort -- including every run where it was never
        # enabled -- so an unrelated corpus's manifest never grows this key.
        _llm_abort = getattr(self, "_llm_safeguard_abort", None)
        if _llm_abort is not None:
            manifest["run_status"] = "aborted_llm_failure_rate"
            manifest["llm_safeguard_abort"] = {
                "observed_rate": _llm_abort.observed_rate,
                "window": _llm_abort.window,
                "threshold": _llm_abort.threshold,
                # Fix round 3, WARNING 3: the raw counts behind
                # observed_rate. decisions_in_window can be LESS than
                # window -- the early-stop rule can fire before the window
                # ever fills (broker/utils/llm_safeguard.py:LLMAbortTracker).
                "failed_count": _llm_abort.failed_count,
                "decisions_in_window": _llm_abort.decisions_in_window,
            }
        # Crash-resume journal abort (same posture as the safeguard abort
        # just above): a divergence or a journal-write failure stopped the
        # run, so the manifest says so instead of looking like a clean
        # finish that merely happened to cover fewer years than configured.
        _journal_abort = getattr(self, "_llm_journal_abort", None)
        if _journal_abort is not None:
            from broker.utils.llm_journal import JournalReplayDivergence
            manifest["run_status"] = (
                "aborted_journal_divergence"
                if isinstance(_journal_abort, JournalReplayDivergence)
                else "aborted_journal_write_error"
            )
            manifest["llm_journal_abort"] = {
                "type": type(_journal_abort).__name__,
                "message": str(_journal_abort),
            }
        # Opus review of WP7 launcher, item 3(a): any exception other than the
        # two narrow families above, stashed by run()'s new third except
        # clause. Same absent-unless-it-happened posture as the two blocks
        # above: a normal run never sets `_generic_abort`, so this adds
        # nothing to a clean manifest.
        _generic_abort = getattr(self, "_generic_abort", None)
        if _generic_abort is not None:
            manifest["run_status"] = "aborted_exception"
            manifest["aborted_exception_type"] = type(_generic_abort).__name__
            manifest["aborted_exception_message"] = str(_generic_abort)
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

        # Crash-resume journal: close the output file handle. Every record
        # was already flushed + fsync'd at write time (see
        # broker.utils.llm_journal.LLMJournalWriter), so this is cleanup,
        # not a durability requirement -- it runs whether the loop above
        # finished cleanly, aborted, or raised, same as every other
        # finalize step in this method.
        journal = getattr(self, "_llm_journal", None)
        if journal is not None:
            journal.close()

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

        # 1. Model identity captured at launch.  A runner made with __new__
        # in a focused unit test has no launch cache, so populate it lazily;
        # normal runs never perform model I/O during finalization.
        if not hasattr(self, "_model_metadata_at_launch"):
            self._capture_model_metadata_at_launch()
        metadata.update(dict(self._model_metadata_at_launch))

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

        # 3. LLM config snapshot.
        #
        # r19 G7: `temperature` / `top_p` (and `num_ctx` / `num_predict`
        # below) reflect the module-level LLM_CONFIG singleton ONLY: the
        # run-wide default from agent_types.yaml's global_config.llm block,
        # or a CLI flag such as --temperature. They are kept for backward
        # compatibility with anything reading this manifest by these exact
        # keys (golden tests included). They are NOT what any individual
        # agent type actually sent to Ollama: `llm_params_resolved` below
        # holds the MERGED dict per agent type (these same run-wide
        # num_ctx/num_predict values PLUS whatever that type's llm_params
        # block, AgentTypeConfig.get_llm_params, overrode via
        # ExperimentRunner.get_llm_invoke), and top_k is never recorded up
        # here at all even when a type did override it. See
        # llm_params_resolved below for the per-agent-type truth.
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

        # Thinking metadata is derived from a separate observation snapshot.
        # Keep it isolated from the scalar config fields above: an observation
        # bookkeeping failure must not erase independently available sampling,
        # context, or timeout provenance from the manifest.
        try:
            from broker.utils.llm_utils import get_llm_thinking_metadata
            thinking_models = [self.config.model]
            resolved = getattr(self, "_llm_resolved_params", {})
            if isinstance(resolved, dict):
                thinking_models.extend(
                    p.get("model") for p in resolved.values() if isinstance(p, dict)
                )
            metadata["llm_thinking"] = get_llm_thinking_metadata(
                thinking_models,
                since_sequence=getattr(self, "_llm_thinking_started", None),
                observations=getattr(self, "_llm_thinking_observations", None),
            )
        except Exception as exc:
            logger.debug(f"[Integrity] llm_thinking skipped: {exc}")

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

        # 3c. Resolved per-agent-type LLM params (r19 G7/G8, verified
        #     2026-09-23). The gap block 3 documents: one domain's per-type
        #     block sending temperature=0.8/top_p=0.9/top_k=40 while another
        #     sends none of the three (the model's own Ollama modelfile
        #     defaults apply), and both previously recorded null/absent
        #     here. `resolved_cache`
        #     is populated lazily by get_llm_invoke, one entry per agent type
        #     this run actually created an invoke for, so this reports what
        #     was REALLY sent (the MERGED dict: LLM_CONFIG's run-wide
        #     num_ctx/num_predict plus whatever that type overrode, exactly
        #     as sent to Ollama; a cloud-provider agent type instead gets its
        #     raw overrides dict, since that path never merges with
        #     LLM_CONFIG at all, see get_llm_invoke), not a hypothetical merge
        #     for every configured type. Each entry also carries "model": the
        #     resolved model name for that agent type, since a per-type
        #     llm_params.model override means different agent types in the
        #     same run can send to different models. An agent type whose
        #     decider never calls get_llm_invoke (e.g. a non-LLM decider) has
        #     no entry, which is correct: it never sent Ollama sampling
        #     params at all.
        #
        #     Own try/except: must never take block 3's timeout/thinking_mode
        #     fields down with it if `self._llm_resolved_params` is ever
        #     something unexpected (e.g. a bare MagicMock in a test double).
        try:
            resolved = dict(getattr(self, "_llm_resolved_params", {}) or {})
            metadata["llm_params_resolved"] = {
                k: dict(v) for k, v in resolved.items() if isinstance(v, dict)
            }
        except Exception as exc:
            metadata["llm_params_resolved"] = None
            logger.debug(f"[Integrity] llm_params_resolved skipped: {exc}")

        # 3d. Every distinct model's OWN Ollama modelfile defaults, for
        #     cross-reference against 3c: a sampling key a given agent type
        #     never overrode (e.g. a type's unset top_k) falls through to
        #     this value at inference time, and that value was previously
        #     invisible in any artifact. Keyed by model name (a run can use
        #     more than one model across agent types via llm_params.model),
        #     one `ollama show --modelfile` call per DISTINCT model, not per
        #     agent type: the modelfile is a property of the model, not of
        #     the agent type. The distinct-model set comes from 3c's
        #     `llm_params_resolved["model"]` entries; when that is empty (no
        #     agent type has resolved a model yet, e.g. no LLM decider has
        #     run, or a test double that never called get_llm_invoke) this
        #     falls back to `self.config.model`, matching the single-model
        #     behaviour this had before per-agent-type models existed. The
        #     mock model and any cloud-provider model (is_cloud_provider_model)
        #     are excluded from the ollama-show call: mock never talks to
        #     Ollama at all (key omitted entirely), and a cloud-provider model
        #     is a real model identity but not an Ollama one (key present,
        #     value None, paired with "not an Ollama model" in
        #     llm_model_defaults_error). Never raises: Ollama absent, not
        #     running, or a slow daemon must not fail manifest collection,
        #     and the reason is recorded alongside the null so an operator
        #     does not have to guess "not applicable" from "the tool failed"
        #     (10s timeout inside the capture call, per model).
        try:
            from broker.utils.llm_utils import (
                capture_ollama_modelfile_defaults, is_cloud_provider_model, is_mock_model,
            )
            resolved_for_models = dict(getattr(self, "_llm_resolved_params", {}) or {})
            distinct_models = sorted({
                v["model"] for v in resolved_for_models.values()
                if isinstance(v, dict) and isinstance(v.get("model"), str)
                and not is_mock_model(v["model"])
            })
            if not distinct_models:
                fallback_model = getattr(self.config, "model", None)
                if isinstance(fallback_model, str) and not is_mock_model(fallback_model):
                    distinct_models = [fallback_model]

            if not distinct_models:
                metadata["llm_model_defaults"] = None
            else:
                defaults_by_model: Dict[str, Any] = {}
                errors_by_model: Dict[str, str] = {}
                for model_name in distinct_models:
                    if is_cloud_provider_model(model_name):
                        defaults_by_model[model_name] = None
                        errors_by_model[model_name] = "not an Ollama model"
                        continue
                    defaults, err = capture_ollama_modelfile_defaults(model_name)
                    defaults_by_model[model_name] = defaults
                    if err is not None:
                        errors_by_model[model_name] = err
                        logger.warning(
                            "[Integrity] llm_model_defaults unavailable for %r: %s",
                            model_name, err,
                        )
                metadata["llm_model_defaults"] = defaults_by_model
                if errors_by_model:
                    metadata["llm_model_defaults_error"] = errors_by_model
        except Exception as exc:
            metadata["llm_model_defaults"] = None
            # Same dict-keyed-by-model shape as the per-model errors above
            # (not a bare string): a caller reading llm_model_defaults_error
            # should never have to branch on its type. "_collection" names a
            # failure in computing the distinct-model set itself (before any
            # per-model capture could even start), not a real model name.
            metadata["llm_model_defaults_error"] = {
                "_collection": f"{type(exc).__name__}: {exc}",
            }
            logger.debug(f"[Integrity] llm_model_defaults skipped: {exc}")

        # 3e. Whether Ollama sampling was seeded (r19 G8). Reads the truth off
        #     the request-options builder (see llm_utils.ollama_sampling_is_seeded)
        #     rather than a literal `False` here, so this cannot silently go
        #     stale if a seed is ever wired into the request path. `None`
        #     (not `False`) when every distinct model this run resolved is a
        #     cloud-provider model: those requests never reach
        #     _invoke_ollama_direct at all, so "was Ollama sampling seeded"
        #     does not apply, and `False` would misleadingly imply an
        #     unseeded Ollama call happened. Defaults to `False` on failure:
        #     "unknown" would be a worse claim than "not proven seeded" for a
        #     reproducibility field whose whole purpose is not overclaiming.
        try:
            from broker.utils.llm_utils import (
                ollama_sampling_is_seeded, is_cloud_provider_model, is_mock_model,
            )
            resolved_for_models = dict(getattr(self, "_llm_resolved_params", {}) or {})
            distinct_models = {
                v["model"] for v in resolved_for_models.values()
                if isinstance(v, dict) and isinstance(v.get("model"), str)
                and not is_mock_model(v["model"])
            }
            non_cloud_models = {m for m in distinct_models if not is_cloud_provider_model(m)}
            if distinct_models and not non_cloud_models:
                metadata["llm_sampling_seeded"] = None
            else:
                metadata["llm_sampling_seeded"] = ollama_sampling_is_seeded()
        except Exception as exc:
            metadata["llm_sampling_seeded"] = False
            logger.debug(f"[Integrity] llm_sampling_seeded skipped: {exc}")

        # 3f. LLM-failure safeguard (spec item 24, audit gap F42): backoff +
        #     abort-rate stop, resolved once by `_resolve_llm_safeguard_config`
        #     (the same values `SkillBrokerEngine.__init__` independently
        #     resolves for its abort tracker -- both read
        #     AgentTypeConfig.get_llm_safeguard_config(), so they cannot
        #     disagree for one run). Recorded regardless of whether this run
        #     aborted: an operator comparing two corpora needs the settings
        #     on a run that finished cleanly too. `None` only when resolution
        #     itself failed (never for "not configured" -- that reads as the
        #     disabled defaults, same as every other domain).
        try:
            from dataclasses import asdict
            metadata["llm_safeguard"] = asdict(self._resolve_llm_safeguard_config())
        except Exception as exc:
            metadata["llm_safeguard"] = None
            logger.debug(f"[Integrity] llm_safeguard skipped: {exc}")

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

        # 5.05. Parallel worker count (ExperimentConfig.workers; F14/F41
        #     parallel-determinism review, F43 crash-resume journal review).
        #     Recorded so a provenance guard pooling runs after the fact
        #     (e.g. a domain's analysis script) can tell whether every run
        #     in a pool used the same worker count, even
        #     though workers>1 is proven to produce the SAME outputs as
        #     workers=1 (_run_agents_parallel's submission-order sort) --
        #     this field is provenance, not a correctness signal.
        #     isinstance-guarded like max_retries_resolved below (same
        #     reason: several tests build this runner with `self.config` as
        #     a bare MagicMock(), which answers ANY attribute access with
        #     another Mock rather than raising -- that would otherwise
        #     write a non-JSON-serialisable value into this dict and break
        #     manifest serialisation for a test that never touched this
        #     field at all). bool excluded the same way, though no known
        #     caller could set workers to a bool.
        _workers = getattr(self.config, "workers", None)
        metadata["workers"] = (
            _workers if isinstance(_workers, int) and not isinstance(_workers, bool)
            else None
        )

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
                    # Which rules, not only how many: two arms with the same
                    # count and different rules are different arms.
                    metadata["thinking_rules_resolved"] = {
                        t: [str(r.id) for r in agent_cfg.get_thinking_rules(t)]
                        for t in active_types
                    }
                if hasattr(agent_cfg, "get_identity_rules"):
                    metadata["identity_rules_resolved"] = {
                        t: [str(r.id) for r in agent_cfg.get_identity_rules(t)]
                        for t in active_types
                    }
                _get_prefix = getattr(agent_cfg, "get_governance_rule_id_prefix", None)
                if callable(_get_prefix):
                    _prefix = _get_prefix()
                    metadata["rule_id_prefix_resolved"] = (
                        _prefix if isinstance(_prefix, bool) else None)
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
            # Appraisal freeze (global_config.governance.appraisal_freeze) as
            # the ENGINE resolved it, and the custom validator callables the
            # engine actually runs (by name) -- an arm that dropped a domain
            # validator bridge is visible here, not only in the runner code.
            _freeze = getattr(self.broker, "_appraisal_freeze", None)
            metadata["appraisal_freeze_resolved"] = (
                _freeze if isinstance(_freeze, bool) else None)
            _custom = getattr(self.broker, "custom_validators", None)
            metadata["custom_validators_resolved"] = (
                [str(getattr(f, "__name__", type(f).__name__)) for f in _custom]
                if isinstance(_custom, (list, tuple)) else None)
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
                reflection_enabled=getattr(self, "reflection_enabled", None),
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

        # 7. Crash-resume journal provenance (broker/utils/llm_journal.py).
        #    Present ONLY for a run that resumed from a source journal:
        #    provenance_metadata() returns None for every normal run (never
        #    resumed), so a run that never touches
        #    ExperimentConfig.resume_journal_path keeps exactly its current
        #    manifest key set -- no new key, not even a null one.
        try:
            journal = getattr(self, "_llm_journal", None)
            if journal is not None:
                journal_provenance = journal.provenance_metadata()
                if journal_provenance is not None:
                    metadata.update(journal_provenance)
        except Exception as exc:
            logger.debug(f"[Integrity] llm_journal provenance skipped: {exc}")

        return metadata

    @staticmethod
    def _executed_on_rejected_row(result: Any) -> bool:
        """True iff the broker ran a skill on a REJECTED/UNCERTAIN row and it succeeded.

        ``executed_skill`` is set by ``SkillBrokerEngine.process_step`` only when
        the simulation engine was actually called (registry default fallback, or
        the kept proposal under ``keep_proposal``). Standalone mode (no engine)
        leaves it None, so domains whose hooks handle rejected rows themselves
        see no generic state or memory application on those rows.
        """
        return bool(
            isinstance(getattr(result, "executed_skill", None), str)
            and getattr(result, "executed_skill")
            and result.execution_result is not None
            and result.execution_result.success
        )

    def _apply_state_changes(self, agent: BaseAgent, result: Any):
        """Update agent attributes and memory from execution results.

        Also stores action context on agent._last_action_context for
        deferred feedback by domain pre_year hooks.

        Approved rows (APPROVED / RETRY_SUCCESS) describe the approved skill.
        Rejected rows (REJECTED / UNCERTAIN) that reach here had a skill
        executed by the broker (see ``_executed_on_rejected_row``); their
        action context names the skill that EXECUTED, not the blocked
        proposal, and carries ``was_fallback`` (True when the registry default
        ran in place of the proposal) plus ``proposed_skill`` (the blocked
        proposal on REJECTED; None on UNCERTAIN, where no usable proposal
        existed), so domain feedback builders can say the default action was
        applied after the proposal was rejected instead of "you chose".
        """
        rejected_row = result.outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN)
        if rejected_row:
            executed_name = getattr(result, "executed_skill", None) or result.approved_skill.skill_name
            was_fallback = bool(getattr(result, "executed_via_fallback", False))
            proposed_name = (
                result.approved_skill.skill_name
                if result.outcome == SkillOutcome.REJECTED and result.approved_skill
                else None
            )
        else:
            executed_name = result.approved_skill.skill_name
            was_fallback = False
            proposed_name = None

        # 1. Update State Flags using canonical method
        if result.execution_result and result.execution_result.state_changes:
            agent.apply_delta(result.execution_result.state_changes)

        # 2. Store action context for deferred feedback by domain pre_year hooks
        action_ctx = {
            "skill_name": executed_name,
            "year": getattr(self, '_current_year', 0),
        }
        # A fallback skill runs with no parameters of its own; the rejected
        # proposal's parameters (already cleared by the broker) never apply.
        params = {} if was_fallback else (result.approved_skill.parameters or {})
        if params.get("magnitude_pct") is not None:
            action_ctx["magnitude_pct"] = params["magnitude_pct"]
            action_ctx["magnitude_fallback"] = params.get("magnitude_fallback", False)
        # Wording of the memory line on a rejected row, from the agent type's
        # memory config: "explicit" (default, the shipped text naming the
        # rejected proposal) or "neutral" (names the rule(s) and the executed
        # action, not the proposal).
        _mem_cfg = getattr(agent, "memory_config", None)
        line_style = (
            _mem_cfg.get("rejection_line_style", "explicit")
            if isinstance(_mem_cfg, dict) else "explicit"
        )
        if line_style not in ("explicit", "neutral"):
            raise ValueError(
                f"memory.rejection_line_style {line_style!r} is not 'explicit' or 'neutral'"
            )
        blocking_rules = list(getattr(result, "blocking_rule_ids", None) or [])
        if rejected_row:
            # Keys added only on rejected rows so approved-row contexts keep
            # exactly the keys they always had.
            action_ctx["was_fallback"] = was_fallback
            action_ctx["proposed_skill"] = proposed_name
            if line_style == "neutral":
                # Only under the opt-in style, so default runs keep the
                # exact rejected-row key set.
                action_ctx["blocking_rules"] = blocking_rules
        if result.execution_result and result.execution_result.action_context:
            action_ctx.update(result.execution_result.action_context)
        agent._last_action_context = action_ctx

        # 3. Legacy immediate memory (kept for backward compat; filtered by
        #    DecisionFilteredMemoryEngine in baseline parity experiments).
        #    Generic opt-out (2026-09-26): a domain whose pre_year/post_year
        #    hook already writes its own outcome line for the period can set
        #    memory.runner_decision_line: false on the agent type to skip
        #    this generic line entirely, instead of writing it and relying
        #    on a filtering memory engine downstream (the flood pattern,
        #    unchanged here). Default True keeps every existing run
        #    byte-identical; a domain that turns this off is by definition
        #    changing its own memory stream (see CHANGELOG).
        runner_decision_line = (
            _mem_cfg.get("runner_decision_line", True)
            if isinstance(_mem_cfg, dict) else True
        )
        if not isinstance(runner_decision_line, bool):
            raise ValueError(
                f"memory.runner_decision_line must be a bool, got "
                f"{runner_decision_line!r}"
            )
        if not runner_decision_line:
            return
        action_desc = executed_name.replace("_", " ").capitalize()
        timestamp_prefix = f"Year {self._current_year}: " if hasattr(self, '_current_year') else ""
        if was_fallback and line_style == "neutral":
            if len(blocking_rules) == 1:
                rule_part = f"under rule {blocking_rules[0]}, "
            elif blocking_rules:
                rule_part = f"under rules ({', '.join(blocking_rules)}), "
            else:
                rule_part = ""
            memory_content = (
                f"{timestamp_prefix}{rule_part}{FALLBACK_MEMORY_MARKER} {action_desc}"
            )
        elif was_fallback and proposed_name:
            proposed_desc = proposed_name.replace("_", " ")
            memory_content = (
                f"{timestamp_prefix}Proposal to {proposed_desc} was rejected; "
                f"{FALLBACK_MEMORY_MARKER} {action_desc}"
            )
        elif was_fallback:
            memory_content = (
                f"{timestamp_prefix}No valid proposal; "
                f"{FALLBACK_MEMORY_MARKER} {action_desc}"
            )
        else:
            memory_content = f"{timestamp_prefix}{DECISION_MEMORY_MARKER} {action_desc}"
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
            pack_metadata = pack.skill_emotion_metadata(executed_name)
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
        # Crash-resume journal: same re-raise-before-the-broad-handler
        # treatment as LLMFailureRateAborted below -- see that except
        # clause's own comment. Imported here (not module level) so a run
        # that never touches the journal feature pays no import cost.
        from broker.utils.llm_journal import JournalReplayDivergence
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
            except LLMFailureRateAborted:
                # Spec item 24: the abort-rate safeguard tripped inside this
                # agent's process_step. This must NOT fall into the broad
                # handler below -- that one turns a raising step into another
                # ABORTED row and keeps the run going, which is exactly what
                # this exception exists to prevent. Re-raise past run()'s
                # loop, whose except/finally records it in the manifest and
                # flushes the audit writers before the run actually stops.
                raise
            except JournalReplayDivergence:
                # Crash-resume journal: a replayed call found no matching
                # recorded answer. Same reasoning as LLMFailureRateAborted
                # just above -- the broad handler below would turn this into
                # one more ABORTED row and let the run continue serving
                # OTHER agents from a journal already proven to not match
                # the rebuilt state, which is exactly the silent-divergence
                # outcome this exception exists to prevent. Re-raise past
                # run()'s loop.
                raise
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
        """Execute agent steps in parallel using ThreadPoolExecutor.

        Returns results in SUBMISSION order (the same order
        ``_run_agents_sequential`` would produce), never thread-completion
        order. ``run()``'s apply loop reads this return value to drive
        ``_apply_state_changes`` and the ``post_step`` hook per agent, in
        order; anything those two read or write that is SHARED across
        agents (a shared ``random.Random`` some memory engines draw from on
        consolidation, e.g. ``HumanCentricMemoryEngine._add_memory_internal``)
        only becomes deterministic across worker counts if that loop sees a
        fixed order. See the sort right before the final ``return`` below.
        """
        # Crash-resume journal: same re-raise-before-the-broad-handler
        # treatment as LLMFailureRateAborted below -- see that except
        # clause's own comment (JournalWriteError is caught there too,
        # alongside JournalReplayDivergence, though only the latter can
        # actually be raised from in here -- see that comment for why).
        # _run_agents_sequential has the analogous clause for
        # JournalReplayDivergence only. Imported here (not module level) so
        # a run that never touches the journal feature pays no import cost.
        from broker.utils.llm_journal import JournalReplayDivergence, JournalWriteError
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
                _, submitted_step_id = futures[future]
                try:
                    agent, result = future.result()
                    results.append((submitted_step_id, agent, result))
                except LLMFailureRateAborted:
                    # Spec item 24: same reasoning as the sequential path's
                    # identical clause -- must escape this handler, not
                    # become another ABORTED row. `future.result()` re-raises
                    # whatever the worker thread raised, so this is reached
                    # exactly when some agent's process_step tripped the
                    # abort-rate window.
                    #
                    # Fix round: cancel_futures=True drops every QUEUED-but-
                    # not-yet-started submission so those agents never even
                    # begin (a future already running cannot be interrupted
                    # mid-call in Python threading, but one that has not
                    # started yet now never will). wait=True blocks until the
                    # in-flight ones finish, which the `with` block's own
                    # __exit__ would do anyway -- doing it here explicitly,
                    # before `raise`, means the executor is already fully
                    # drained by the time this exception reaches run()'s
                    # finally, instead of racing it.
                    executor.shutdown(wait=True, cancel_futures=True)
                    raise
                except (JournalReplayDivergence, JournalWriteError):
                    # Crash-resume journal: same reasoning as the
                    # LLMFailureRateAborted clause just above -- a
                    # divergence raised inside THIS worker's process_step
                    # must escape this handler, not become another ABORTED
                    # row. Without this clause the broad `except Exception`
                    # below would catch it, the run would keep submitting
                    # agents, and every OTHER worker would go on being
                    # served from a journal already proven to not match the
                    # rebuilt state -- exactly the silent-divergence outcome
                    # this exception exists to prevent. `future.result()`
                    # re-raises whatever the worker thread raised, so this
                    # is reached exactly when some agent's process_step hit
                    # one of these.
                    #
                    # _run_agents_sequential's own clause catches only
                    # JournalReplayDivergence, not JournalWriteError: a
                    # write failure is never raised synchronously from
                    # inside a call this loop makes (LLMJournalManager.
                    # _record_call_safely stores it as a STICKY error
                    # instead of raising), it only ever surfaces later, from
                    # LLMJournalManager.step_end -- which both execution
                    # paths call from run()'s own loop, never from in here.
                    # JournalWriteError is caught here too, alongside
                    # JournalReplayDivergence, purely for symmetry with
                    # run()'s own top-level `except (JournalReplayDivergence,
                    # JournalWriteError)`: harmless (this arm of the except
                    # tuple can never actually match on this path today) in
                    # exchange for not having to revisit this clause if a
                    # future change ever makes a write failure raise
                    # synchronously instead.
                    #
                    # cancel_futures=True, same as the abort clause: every
                    # agent is already SUBMITTED by this point (the
                    # executor.submit() loop above runs to completion before
                    # this result loop ever starts), so the real gain here
                    # is not "fewer agents run" -- it is that this method
                    # never returns a `results` list for this step at all:
                    # the exception propagates straight out, before run()'s
                    # apply loop (_apply_state_changes + post_step, per
                    # agent) ever sees a step built on an unproven rebuild,
                    # and without one more agent's failure being misfiled as
                    # a spurious ABORTED_EXCEPTION row for what is actually
                    # a whole-run integrity problem. cancel_futures=True
                    # additionally drops whichever QUEUED-but-not-yet-
                    # started agents the executor had not gotten to yet (a
                    # real savings whenever workers < len(agents)); an
                    # already-running future cannot be interrupted mid-call,
                    # but wait=True blocks until those finish, so the
                    # executor is fully drained before this reaches run()'s
                    # own except/finally instead of racing it.
                    executor.shutdown(wait=True, cancel_futures=True)
                    raise
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
                    failed_agent, _ = futures[future]
                    logger.error(
                        f"[Parallel] Agent {failed_agent.id} failed: {e}",
                        exc_info=True,
                    )
                    self._write_aborted_trace(failed_agent, run_id, env, e,
                                              step_id=submitted_step_id)
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
                    results.append((submitted_step_id, failed_agent, error_result))

        # feat/v3-parallel-determinism: reorder to SUBMISSION order. The loop
        # above builds `results` in as_completed()'s THREAD-COMPLETION order.
        # Callers (run()'s apply loop: _apply_state_changes and the
        # post_step hook, per agent, in list order) must see the same order
        # regardless of worker count or which thread happens to finish
        # first. That is what keeps a shared-state read/write inside that
        # loop (e.g. the one `random.Random` draw
        # HumanCentricMemoryEngine._add_memory_internal makes on
        # consolidation) deterministic across workers. `step_id` is unique
        # and strictly increasing in SUBMISSION order within this call (one
        # `self.step_counter += 1` per agent, in the submit loop above), so
        # a sort by it exactly reconstructs that order. At workers == 1,
        # completion order already equals submission order, so this sort is
        # a no-op there.
        results.sort(key=lambda item: item[0])
        return [(agent, result) for _, agent, result in results]
