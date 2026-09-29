"""
LLM Utilities - Shared model invocation methods.

Provides common logic for:
- Initializing LLM providers (e.g., ChatOllama)
- Standardized invocation with error handling
- Model-specific parameter tuning (e.g., num_predict)
- LLM-level retry tracking for audit

v2.0: invoke functions now return (content, stats) tuple for thread-safety.
v2.1: Added global LLM_CONFIG for configurable parameters.
"""
import logging
import math
import os
import time
from pathlib import Path
from typing import Callable, Dict, Set, Tuple, Union, Optional, Any
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)


# Name of the env var that raises a floor under LLMConfig.get_timeout().
LLM_TIMEOUT_ENV_VAR = "WAGF_LLM_TIMEOUT"

# Upper bound on an accepted floor. A socket timeout is handed to select()/poll()
# as an INT_MAX-millisecond deadline, so anything above ~2_147_483 s raises a bare
# OverflowError ("timeout doesn't fit into C timeval") inside requests.post —
# BEFORE the connection is even attempted, and NOT as a requests.exceptions.*, so
# `_invoke_ollama_direct`'s catch-all turns it into a failed call for EVERY call
# in the run. A plausible extra-zeros typo (600 -> 6000000) lands squarely in that
# window. The cap sits well below the hard limit: no single model call is a day.
_MAX_TIMEOUT_SECONDS = 86_400

# Raw env values already reported as unusable, so a per-call read does not
# emit one warning line per LLM invocation. Keyed on the raw string, so
# correcting the value and then breaking it again still says so.
_WARNED_BAD_TIMEOUT_VALUES: Set[str] = set()


def _env_timeout_floor() -> int:
    """Minimum LLM timeout requested via ``WAGF_LLM_TIMEOUT``, else 0.

    Returns 0 — meaning "no floor", not "no time" — when the variable is
    unset, blank, unparseable, non-positive, or above
    ``_MAX_TIMEOUT_SECONDS``. A bad value is logged once rather than
    swallowed: a typo must not decide how the run behaves silently. Both ends
    are guarded, and for the same reason — reading 0 seconds out of a typo
    would make every Ollama call time out instantly, and accepting 6000000
    would make every one raise OverflowError before connecting. Either way
    the batch fails and looks like a model fault rather than a shell mistake.

    A fractional value rounds UP, so the floor is never lower than asked.
    """
    raw = os.environ.get(LLM_TIMEOUT_ENV_VAR)
    if raw is None or not raw.strip():
        return 0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        if raw not in _WARNED_BAD_TIMEOUT_VALUES:
            _WARNED_BAD_TIMEOUT_VALUES.add(raw)
            _LOGGER.warning(
                "%s=%r is not a number — IGNORING it and using the configured "
                "timeout. Set it to a positive number of seconds.",
                LLM_TIMEOUT_ENV_VAR, raw,
            )
        return 0
    # isfinite rejects nan and ±inf; `<= 0` rejects zero and negatives. The
    # isfinite check is what catches NaN — `nan <= 0` is False, so the
    # comparison alone would let it through. (Either order works in an `or`
    # chain; what matters is that both checks are present.)
    if not math.isfinite(value) or value <= 0:
        if raw not in _WARNED_BAD_TIMEOUT_VALUES:
            _WARNED_BAD_TIMEOUT_VALUES.add(raw)
            _LOGGER.warning(
                "%s=%r is not a positive finite number of seconds — IGNORING "
                "it and using the configured timeout.",
                LLM_TIMEOUT_ENV_VAR, raw,
            )
        return 0
    if value > _MAX_TIMEOUT_SECONDS:
        if raw not in _WARNED_BAD_TIMEOUT_VALUES:
            _WARNED_BAD_TIMEOUT_VALUES.add(raw)
            _LOGGER.warning(
                "%s=%r is above the %d s maximum — IGNORING it and using the "
                "configured timeout. A socket timeout that large raises "
                "OverflowError inside requests, failing every call. Did you "
                "mean %d?",
                LLM_TIMEOUT_ENV_VAR, raw, _MAX_TIMEOUT_SECONDS,
                _MAX_TIMEOUT_SECONDS,
            )
        return 0
    return math.ceil(value)


def timeout_env_status() -> Tuple[Optional[str], bool]:
    """``(raw WAGF_LLM_TIMEOUT value, was it set but unusable)``.

    For the reproducibility manifest. The effective timeout alone cannot
    distinguish "the operator set nothing" from "the operator set 6000000 and
    it was rejected" — both record 120 — and the second is a run someone
    believed had 100 minutes of headroom. Recording the raw string and the
    rejection flag makes that visible in the artifact instead of only in a
    log line nobody kept.

    A value that parsed fine but sits BELOW the configured timeout is not
    "rejected": it was read and applied, the ``max()`` rule simply left the
    configured value on top.
    """
    raw = os.environ.get(LLM_TIMEOUT_ENV_VAR)
    was_set = bool(raw and raw.strip())
    return raw, was_set and _env_timeout_floor() == 0


# =============================================================================
# Global LLM Configuration (can be modified before creating invoke functions)
# =============================================================================
@dataclass
class LLMConfig:
    """
    Global configuration for LLM parameters.

    Modify these values before calling create_llm_invoke() to customize behavior.
    Set a value to None to use Ollama's default.

    Example:
        from broker.utils.llm_utils import LLM_CONFIG
        LLM_CONFIG.temperature = 1.0
        LLM_CONFIG.top_p = 0.95
    """
    # Sampling parameters (None = use Ollama default)
    temperature: Optional[float] = None
    top_p: Optional[float] = None
    top_k: Optional[int] = None

    # Context/generation limits
    num_predict: int = -1      # -1 = unlimited
    num_ctx: int = 16384       # Context window size

    # Provider selection
    use_chat_api: bool = False  # False = OllamaLLM (completion), True = ChatOllama (chat)

    # Retry settings (Phase 40: Configurable)
    max_retries: int = 2

    # Timeout settings — configurable instead of hardcoded model-name checks
    timeout: int = 120                   # Default timeout (seconds) for standard models
    timeout_large_model: int = 600       # Extended timeout for large/slow models
    large_model_patterns: tuple = ("26b", "27b", "30b", "32b", "70b")  # Patterns that trigger extended timeout

    # Model-specific quirks — configurable instead of hardcoded if-chains
    # Keys are substring patterns matched against model name (case-insensitive).
    # Supported quirk fields: min_retries, append_suffix, strip_think_tags
    model_quirks: Dict[str, Dict[str, Any]] = field(default_factory=lambda: {
        "deepseek": {"min_retries": 5},
        "qwen3": {"append_suffix": "/no_think", "strip_think_tags": True},
    })

    # Thinking mode control for reasoning models (Gemma 4, DeepSeek R1, Qwen3, etc.)
    #   "auto"     = don't modify LLM call, strip <think> tags from output (default, backward compat)
    #   "disabled" = actively disable thinking (set think=false in Ollama options + strip tags)
    #   "enabled"  = keep thinking tokens in output for audit/analysis
    thinking_mode: str = "auto"
    thinking_budget_tokens: Optional[int] = None  # Optional: limit thinking token count

    def to_ollama_params(self) -> Dict[str, Any]:
        """Convert config to Ollama parameter dict, excluding None values."""
        params = {
            "num_predict": self.num_predict,
            "num_ctx": self.num_ctx,
        }
        # Only include sampling params if explicitly set
        if self.temperature is not None:
            params["temperature"] = self.temperature
        if self.top_p is not None:
            params["top_p"] = self.top_p
        if self.top_k is not None:
            params["top_k"] = self.top_k
        return params

    def get_timeout(self, model: str) -> int:
        """Return appropriate timeout based on model name patterns.

        ``WAGF_LLM_TIMEOUT`` raises a FLOOR under the configured value for
        every model: the result is ``max(configured, env)``, never less. A
        slow host can therefore be given more headroom without editing
        ``agent_types.yaml`` — which matters because that file is hashed into
        ``config_hash`` in the reproducibility manifest, so raising a timeout
        by editing it would look like a config change in every later
        comparison.

        The env var is read HERE, per call, not in
        :func:`_load_global_config`. That keeps ``LLM_CONFIG`` construction
        byte-for-byte what the YAML says (so ``config_hash`` and the manifest's
        other ``LLM_CONFIG`` fields still describe the file, not the shell),
        and it means a value exported after import still takes effect. The cost
        is one ``os.environ`` lookup per Ollama call, against a call that is
        about to wait seconds for a model.

        A value that is missing, unparseable, non-positive, or absurdly large
        is IGNORED and logged once — never silently treated as zero (every
        request would time out instantly) and never passed through at a size
        a socket cannot carry (every request would raise before connecting).

        SCOPE: this covers the direct-Ollama path every experiment runs on
        (``_invoke_ollama_direct``). It does NOT reach the separate
        ``providers/`` stack (``providers/llm_provider.py``'s own
        ``LLMConfig.timeout``, used by httpx), which no experiment path
        currently reaches — only ``providers.factory`` / ``providers/smoke.py``.
        """
        model_lower = model.lower()
        if any(p in model_lower for p in self.large_model_patterns):
            configured = self.timeout_large_model
        else:
            configured = self.timeout
        return max(int(configured), _env_timeout_floor())

    def apply_model_quirks(self, model: str, prompt: str, max_retries: int) -> tuple:
        """Apply model-specific quirks and return (modified_prompt, modified_max_retries)."""
        model_lower = model.lower()
        for pattern, quirks in self.model_quirks.items():
            if pattern in model_lower:
                if "min_retries" in quirks:
                    max_retries = max(max_retries, quirks["min_retries"])
                suffix = quirks.get("append_suffix", "")
                if suffix and suffix not in prompt:
                    prompt = prompt + "\n" + suffix
        return prompt, max_retries

    def should_strip_thinking(self) -> bool:
        """Whether to strip <think> tags from LLM output before parsing."""
        return self.thinking_mode in ("auto", "disabled")

    def apply_thinking_control(self, model: str, options: dict) -> dict:
        """Deprecated shim: kept for backward compatibility. Use get_think_flag() instead.

        Note: Ollama's `think` parameter is a TOP-LEVEL request field, NOT inside
        options. This method historically put it in options (a no-op). Use
        get_think_flag() to retrieve the top-level flag, and add it to the request
        dict at the call site.
        """
        if self.thinking_mode == "enabled" and self.thinking_budget_tokens:
            options["think_budget"] = self.thinking_budget_tokens
        return options

    def get_think_flag(self) -> Optional[bool]:
        """Return the value for Ollama's top-level `think` request field.

        Returns:
            True  → enable thinking
            False → disable thinking
            None  → leave unset (use Ollama default)
        """
        if self.thinking_mode == "enabled":
            return True
        if self.thinking_mode == "disabled":
            return False
        return None  # auto → don't touch the flag


# Global instance - modify this to change default behavior
from broker.utils.agent_config import load_agent_config

# ... (Previous code)

# Global instance - modify this to change default behavior
def _load_global_config() -> LLMConfig:
    try:
        cwd_config = Path.cwd() / "agent_types.yaml"
        package_config = Path(__file__).parent / "agent_types.yaml"
        config_path = cwd_config if cwd_config.exists() else package_config
        if not config_path.exists():
            return LLMConfig()

        # Load agent_types.yaml via helper
        config = load_agent_config(str(config_path))

        # Access global_config.llm using .get("global_config")
        # Note: AgentTypeConfig.get() works for any top-level key
        global_llm = config.get("global_config").get("llm", {})

        # Load model quirks from config, falling back to defaults
        quirks_raw = global_llm.get("model_quirks")
        quirks = (
            {k: dict(v) for k, v in quirks_raw.items()}
            if quirks_raw
            else {
                "deepseek": {"min_retries": 5},
                "qwen3": {"append_suffix": "/no_think", "strip_think_tags": True},
            }
        )

        # Load large model patterns from config, falling back to defaults
        patterns_raw = global_llm.get("large_model_patterns")
        patterns = tuple(patterns_raw) if patterns_raw else ("27b", "30b", "32b", "70b")

        return LLMConfig(
            temperature=global_llm.get("temperature"),
            top_p=global_llm.get("top_p"),
            top_k=global_llm.get("top_k"),
            num_ctx=global_llm.get("num_ctx", 16384),
            num_predict=global_llm.get("num_predict", 2048),
            max_retries=global_llm.get("max_retries", 2),
            timeout=global_llm.get("timeout", 120),
            timeout_large_model=global_llm.get("timeout_large_model", 600),
            large_model_patterns=patterns,
            model_quirks=quirks,
            thinking_mode=global_llm.get("thinking_mode", "auto"),
            thinking_budget_tokens=global_llm.get("thinking_budget_tokens"),
        )
    except Exception as e:
        _LOGGER.warning(f"Could not load global LLM config: {e}. Using defaults.")
        return LLMConfig()

LLM_CONFIG = _load_global_config()


def resolve_ollama_params(overrides: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Merge ``overrides`` onto ``LLM_CONFIG`` exactly as ``create_llm_invoke`` does.

    Single source of truth for "what sampling/context params does this run
    actually send for a given agent type" (Ollama requests only; see
    ``is_cloud_provider_model`` for why a cloud-provider agent type is
    recorded differently). Reused by ``create_llm_invoke`` (to build the
    invoke closure's Ollama options) and by
    ``ExperimentRunner._collect_reproducibility_metadata`` (to record
    ``llm_params_resolved`` in the reproducibility manifest, r19 G7/G8).

    Before this helper existed, the manifest read the ``LLM_CONFIG`` singleton
    directly and never saw the per-agent-type override
    (``AgentTypeConfig.get_llm_params(agent_type)``, merged in as overrides by
    ``ExperimentRunner.get_llm_invoke``): one domain's per-type block sending
    temperature=0.8/top_p=0.9/top_k=40 and another sending none of the three
    (Ollama's modelfile defaults apply instead) both recorded
    whatever ``LLM_CONFIG`` held globally (null for both), even though the
    actual sampled values differed. Any future caller that needs "what does
    this run really send" must call this function rather than read
    ``LLM_CONFIG`` or an overrides dict alone, so the two paths cannot drift
    apart again.

    ``overrides`` is read-only here: a fresh dict is returned and the input is
    never mutated.
    """
    params = LLM_CONFIG.to_ollama_params()
    if overrides:
        params.update(overrides)
    params.pop("model", None)
    return params


def _elapsed_ms(t0: float) -> float:
    """Milliseconds since ``t0`` (a ``time.perf_counter()`` reading)."""
    return (time.perf_counter() - t0) * 1000.0


@dataclass
class LLMStats:
    """Statistics from a single LLM invocation."""
    retries: int = 0
    success: bool = True
    # LLM-level retry tracking (045-H)
    empty_content_retries: int = 0  # LLM returned empty content, retry triggered
    empty_content_failure: bool = False  # Terminal: empty after all retries exhausted
    # R5-C: Token monitoring
    prompt_tokens: int = 0   # Prompt token count from Ollama (prompt_eval_count)
    response_tokens: int = 0  # Response token count from Ollama (eval_count)
    num_ctx: int = 0          # Context window size used for this call
    context_utilization: float = 0.0  # prompt_tokens / num_ctx
    # 2026-09-15: per-call timing + multi-attempt accounting.
    #
    # `latency_ms` / `tokens_per_second` describe the LAST provider call this
    # object reports on; `calls` / `prompt_tokens_total` / `response_tokens_total`
    # cover EVERY call it made, which for `create_llm_invoke`'s returned function
    # includes its internal empty-content retries.
    #
    # 0.0 in a timing field means "this invoke path reported no timing" — the
    # mock model, a rule/parametric decider, a provider that raised before the
    # request left — NOT a call that took no time. Same reading as the token
    # fields, which have meant "not reported" since R5-C.
    latency_ms: float = 0.0
    tokens_per_second: float = 0.0
    calls: int = 1
    prompt_tokens_total: int = 0
    response_tokens_total: int = 0
    # Spec item 24 fix round (audit gap: 1,638 real HTTP calls vs 1,170
    # reported): backoff-layer bookkeeping, both additive and both defaulting
    # to their pre-fix-round values so a call site that never sets them is
    # unaffected.
    #
    # `transport_error` is an internal signal ONLY, from an invoke function to
    # `broker.utils.llm_safeguard.wrap_llm_invoke_with_backoff`: "this specific
    # failure was a connection-type transport failure (OSError, or an HTTP 5xx
    # status), safe to retry" -- as opposed to a timeout (the inner layer
    # already waited the configured timeout, retrying it again would double
    # that wait for no benefit), an HTTP 4xx (a persistent client-side
    # problem no retry fixes), empty/thinking-only content (the model's own
    # empty-content retry loop already tried and failed), or a generic
    # exception such as TypeError (a bug, not a transport blip). Deliberately
    # excluded from `to_dict()` -- it exists to route ONE retry decision, not
    # to be reported.
    transport_error: bool = False
    # `backoff_retries` is how many times wrap_llm_invoke_with_backoff retried
    # THIS call after a transport failure. Read by `broker/core/_retry_loop.py`
    # to call `GovernanceAuditor.log_backoff_retry()` once per retry, the same
    # pattern `empty_content_retries` already uses -- so a backoff retry counts
    # toward `total_extra_llm_calls` in the audit / governance_summary.json,
    # instead of being invisible the way it was before this field existed.
    backoff_retries: int = 0

    def to_dict(self) -> Dict:
        d = {
            "llm_retries": self.retries,
            "llm_success": self.success,
            "empty_content_retries": self.empty_content_retries,
            "empty_content_failure": self.empty_content_failure,
            "backoff_retries": self.backoff_retries,
        }
        if self.prompt_tokens > 0:
            d["prompt_tokens"] = self.prompt_tokens
            d["response_tokens"] = self.response_tokens
            d["num_ctx"] = self.num_ctx
            d["context_utilization"] = round(self.context_utilization, 4)
        return d


def accumulate_llm_stats(total: Dict[str, Any], stats: Any) -> None:
    """Fold one ``LLMStats`` into a decision's ``total_llm_stats`` dict.

    Single source of truth for the four sites that aggregate LLM statistics
    into ONE audit row: the two loops in ``broker/core/_retry_loop.py`` and the
    two advisory passes in ``broker/core/_advise_pass.py``. They previously
    carried four near-identical copies of this arithmetic, which is how the
    advisory copy came to use ``getattr`` defaults the retry-loop copy did not.

    Column semantics, stated once so the CSV reader does not have to infer them:

    * ``prompt_tokens`` / ``response_tokens`` / ``num_ctx`` /
      ``context_utilization`` / ``llm_latency_ms`` / ``tokens_per_second``
      describe the LAST attempt that reported tokens — all six, one call. They
      are per-call measurements, so ``context_utilization`` equals
      ``prompt_tokens / num_ctx`` for the same call, which a running sum never
      could, and throughput computed from the row is that call's throughput.
    * ``prompt_tokens_peak`` / ``num_ctx_peak`` are the widest single attempt of
      the decision, kept because the LAST attempt is not always the widest: the
      advisory pass runs BEFORE the governance retry loop and its prompt appends
      header + rule text, so an advised decision can peak mid-way. They stay out
      of the CSV projection (JSONL only) and exist so the context-budget
      tripwire in ``GenericAuditWriter.write_trace`` keeps watching the worst
      call rather than the last one.
    * ``prompt_tokens_total`` / ``response_tokens_total`` answer the BUDGET
      question — summed over every attempt of the decision, including the
      empty-content retries inside a single ``llm_invoke`` call.
    * ``llm_calls_total`` counts those attempts. It differs from the flag-gated
      ``llm_calls``, which counts ``llm_invoke`` CALLS and so under-counts a
      decision whose provider retried internally.

    A caller whose ``llm_invoke`` RAISED or returned a bare string never reaches
    this function and must add its own ``+= 1`` — both retry loops and both
    advisory passes do. Counting at the call site INSTEAD, as a flat 1, is not
    equivalent and was briefly wrong here: ``stats.calls`` is N when the
    provider returned empty content N-1 times inside one ``llm_invoke``, so a
    flat 1 left ``llm_calls_total`` and ``prompt_tokens_total`` computed over
    different attempt sets, and the per-call average derived from the pair was
    wrong by exactly the internal-retry factor.

    ``getattr`` throughout: deciders and test doubles hand back stats objects
    that predate these fields, and an audit row must never fail to be written
    because a stats object was thin.
    """
    total["llm_calls_total"] = (
        total.get("llm_calls_total", 0)
        + max(int(getattr(stats, "calls", 1) or 1), 1)
    )

    prompt_tokens = int(getattr(stats, "prompt_tokens", 0) or 0)
    response_tokens = int(getattr(stats, "response_tokens", 0) or 0)
    if prompt_tokens > 0:
        num_ctx = int(getattr(stats, "num_ctx", 0) or 0)
        utilization = round(
            float(getattr(stats, "context_utilization", 0.0) or 0.0), 4)
        total["prompt_tokens"] = prompt_tokens
        total["response_tokens"] = response_tokens
        total["num_ctx"] = num_ctx
        total["context_utilization"] = utilization
        # Timing belongs to the SAME attempt as the tokens beside it. Writing it
        # outside this branch spliced two calls into one row: a decision whose
        # last attempt timed out after an earlier one succeeded published that
        # attempt's tokens next to the timeout's 600 000 ms and a
        # `tokens_per_second` of 0.0, so throughput computed per row was wrong by
        # two orders of magnitude and the 0.0 looked like "not measured" next to
        # a non-zero response_tokens. A failed final attempt now leaves the
        # previous attempt's six numbers standing, which is the reading the
        # column names already promise.
        total["llm_latency_ms"] = round(
            float(getattr(stats, "latency_ms", 0.0) or 0.0), 3)
        total["tokens_per_second"] = round(
            float(getattr(stats, "tokens_per_second", 0.0) or 0.0), 3)
        # Widest attempt, not last: `>=` alone is not enough because the cloud
        # path reports num_ctx=0 and so utilization 0.0 on EVERY call, which
        # would let a 100-token final attempt overwrite a 5000-token peak. Tie
        # on utilization, break on the prompt.
        peak_util = float(total.get("context_utilization_peak", 0.0) or 0.0)
        peak_prompt = int(total.get("prompt_tokens_peak", 0) or 0)
        if (utilization, prompt_tokens) >= (peak_util, peak_prompt):
            total["context_utilization_peak"] = utilization
            total["prompt_tokens_peak"] = prompt_tokens
            total["num_ctx_peak"] = num_ctx

    # A stats object that predates the `*_total` fields — a legacy provider
    # shim, a test double, anything not built by this module — still made a call
    # whose tokens belong in the decision's budget. Falling back to the per-call
    # number keeps a total from reading 0 next to a non-zero per-call count,
    # which is the shape of an undercount nobody would question. Each side falls
    # back INDEPENDENTLY: an object carrying one field and not the other is
    # exactly the half-migrated shim this guard exists for.
    reported_prompt_total = getattr(stats, "prompt_tokens_total", None)
    if reported_prompt_total is None:
        reported_prompt_total = prompt_tokens
    reported_response_total = getattr(stats, "response_tokens_total", None)
    if reported_response_total is None:
        reported_response_total = response_tokens
    total["prompt_tokens_total"] = (
        total.get("prompt_tokens_total", 0) + int(reported_prompt_total or 0))
    total["response_tokens_total"] = (
        total.get("response_tokens_total", 0) + int(reported_response_total or 0))


# =============================================================================
# Abstract LLM Provider Interface (Phase 25 PR7)
# =============================================================================
from abc import ABC, abstractmethod

class LLMProvider(ABC):
    """
    Abstract base class for LLM providers.
    
    Enables multi-provider support (Ollama, OpenAI, Anthropic, etc.)
    without changing broker code.
    """
    
    @abstractmethod
    def invoke(self, prompt: str) -> Tuple[str, LLMStats]:
        """
        Invoke the LLM and return (content, stats) tuple.
        
        Args:
            prompt: The input prompt string
            
        Returns:
            Tuple of (response_content, LLMStats)
        """
        ...
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model identifier."""
        ...


# Type alias for the invoke function signature (legacy compatibility)
LLMInvokeFunc = Callable[[str], Tuple[str, LLMStats]]


# Cloud providers create_llm_invoke routes to the modern provider factory
# (create_provider_invoke) instead of the direct-Ollama path, given a model
# string of the shape "<provider>:<name>". Hoisted to module level (it used
# to be a local inside create_llm_invoke) so is_cloud_provider_model below can
# reuse the SAME list rather than a second, possibly-drifting copy.
KNOWN_CLOUD_PROVIDERS = ("gemini", "openai", "azure", "anthropic", "claude")


def is_cloud_provider_model(model: str) -> bool:
    """Whether ``model`` routes through the cloud-provider factory, not Ollama.

    Mirrors ``create_llm_invoke``'s own routing check exactly (a ``mock``-
    prefixed name never counts, even if it happens to contain a colon), so
    this can be reused elsewhere (the reproducibility manifest gates
    ``llm_model_defaults`` / ``llm_sampling_seeded`` on it, since neither
    concept applies to a request Ollama never receives) without a second,
    independently-maintained copy of the same rule.
    """
    if not isinstance(model, str) or model.lower().startswith("mock"):
        return False
    if ":" not in model:
        return False
    provider_type = model.split(":", 1)[0].lower()
    return provider_type in KNOWN_CLOUD_PROVIDERS


def _build_ollama_options(model: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """Build the Ollama ``options`` dict exactly as ``_invoke_ollama_direct`` sends it.

    Extracted so ``ollama_sampling_is_seeded`` can inspect the REAL request
    options for a ``seed`` key instead of a hardcoded belief about whether one
    is sent (the two must never drift apart the way the manifest's
    ``temperature``/``top_p`` singleton drifted from the per-call overrides,
    r19 G7/G8). Behaviour is unchanged: this is the same dict construction
    that lived inline in ``_invoke_ollama_direct`` before.
    """
    # Standardize options: only include sampling params if explicitly set
    # (None / missing = use Ollama model default, e.g. temperature ~0.8)
    options = {
        "num_predict": params.get("num_predict", 2048),
        "num_ctx": params.get("num_ctx", 8192 if "8b" in model.lower() or "14b" in model.lower() else 4096),
    }
    if "temperature" in params:
        options["temperature"] = params["temperature"]
    if "top_p" in params:
        options["top_p"] = params["top_p"]
    if "top_k" in params:
        options["top_k"] = params["top_k"]

    # Apply thinking budget (if any) into options; think flag is top-level
    # (set at the request-dict level in _invoke_ollama_direct, not here).
    options = LLM_CONFIG.apply_thinking_control(model, options)
    return options


def ollama_sampling_is_seeded() -> bool:
    """Whether the Ollama request options this run sends include a ``seed`` key.

    Reads the truth from :func:`_build_ollama_options`, the same builder
    ``_invoke_ollama_direct`` calls for every request, instead of a hardcoded
    ``False``. Ollama's ``seed`` option is not added anywhere in the options
    builder today, so this reads ``False``; the day a seed IS wired in, this
    flips automatically with no reproducibility-manifest code to remember to
    update (r19 G8: today's runs are unseeded and that fact was previously
    unstated in the manifest). Model-independent by design: the builder is
    shared code, so whether a seed is sent does not vary by model. Callers
    that need "is Ollama even in the request path for this run" (a cloud
    provider never reaches this builder at all) check
    :func:`is_cloud_provider_model` separately.
    """
    probe_options = _build_ollama_options("probe-model", {})
    return "seed" in probe_options


def _parse_ollama_modelfile_parameters(modelfile_text: str) -> Dict[str, Any]:
    """Parse ``PARAMETER`` lines out of an ``ollama show --modelfile`` output.

    Each line has the shape ``PARAMETER <key> <value>``; ``value`` may be
    quoted (e.g. ``PARAMETER stop "<end_of_turn>"``). ``stop`` is ALWAYS
    returned as a list, even when the modelfile has exactly one ``PARAMETER
    stop ...`` line: a caller iterating stop tokens should never have to
    branch on ``isinstance(..., list)`` first, and Ollama's own format treats
    stop as inherently multi-valued (one line per token). Any OTHER repeated
    key also collects into a list. Numeric-looking values are coerced to
    int/float; everything else stays a string. Unparseable or unrelated lines
    are skipped, never raised on: this feeds a best-effort manifest field,
    not a control path.
    """
    params: Dict[str, Any] = {}
    for line in modelfile_text.splitlines():
        line = line.strip()
        if not line.startswith("PARAMETER "):
            continue
        rest = line[len("PARAMETER "):].strip()
        parts = rest.split(None, 1)
        if len(parts) != 2:
            continue
        key, raw_value = parts
        value = raw_value.strip()
        if len(value) >= 2 and value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        parsed_value: Any = value
        try:
            parsed_value = int(value)
        except ValueError:
            try:
                parsed_value = float(value)
            except ValueError:
                parsed_value = value
        if key == "stop":
            params.setdefault("stop", []).append(parsed_value)
        elif key in params:
            existing = params[key]
            if isinstance(existing, list):
                existing.append(parsed_value)
            else:
                params[key] = [existing, parsed_value]
        else:
            params[key] = parsed_value
    return params


def capture_ollama_modelfile_defaults(
    model: str, timeout: int = 10,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Return ``(parsed PARAMETER dict, error message)`` from ``ollama show <model> --modelfile``.

    For the reproducibility manifest's ``llm_model_defaults`` (r19 G7): the
    per-call overrides recorded by :func:`resolve_ollama_params` describe what
    THIS run explicitly sent; a key that run never set (e.g. a type sends
    no ``top_k`` override) falls through to whatever the model's own Ollama
    modelfile declares, and that value was previously invisible in any
    artifact. Never raises: Ollama being absent, the model being unknown to
    it, or a slow/hung daemon must not fail manifest collection. On any
    failure the first element is ``None`` and the second names why.

    Decoding: ``encoding="utf-8", errors="replace"`` so a modelfile containing
    non-UTF-8 bytes (a stray byte in a LICENSE block, an odd locale on the
    host) degrades to replacement characters in that field rather than
    raising ``UnicodeDecodeError`` and losing the whole manifest field to the
    catch-all below.
    """
    import subprocess
    try:
        result = subprocess.run(
            ["ollama", "show", model, "--modelfile"],
            capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        if result.returncode != 0:
            stderr = (result.stderr or "").strip()[:200]
            return None, f"'ollama show {model} --modelfile' exited {result.returncode}: {stderr}"
        return _parse_ollama_modelfile_parameters(result.stdout), None
    except FileNotFoundError:
        return None, "ollama executable not found on PATH"
    except subprocess.TimeoutExpired:
        return None, f"'ollama show {model} --modelfile' timed out after {timeout}s"
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def _invoke_ollama_direct(model: str, prompt: str, params: Dict[str, Any], verbose: bool) -> Tuple[str, LLMStats]:
    """
    Phase 46: Invoke Ollama direct via API to avoid LangChain/Python 3.14 issues
    and enable native JSON-mode.
    """
    import requests
    import json

    url = "http://localhost:11434/api/generate"

    # Phase 47: Global Disable of Strict JSON Mode
    # User Request: "Turn it off for all" to fix DeepSeek R1 <think> tokens.
    # We rely on the prompt to enforce JSON structure.
    options = _build_ollama_options(model, params)

    data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": None, # DISABLED globally for Reasoning Model compatibility
        "options": options,
    }

    # Ollama's `think` parameter is a TOP-LEVEL request field, not inside options.
    think_flag = LLM_CONFIG.get_think_flag()
    if think_flag is not None:
        data["think"] = think_flag
        if verbose:
            _LOGGER.debug(f" [LLM:Direct] Setting top-level think={think_flag} for model '{model}'")
    
    # Wall clock around the request itself, so the recorded latency is the cost
    # the run actually paid for this call (queueing at the server included) and
    # not a figure derived from the server's own self-report.
    t0 = time.perf_counter()
    try:
        # Config-driven timeout: large/slow models get extended timeout
        timeout = LLM_CONFIG.get_timeout(model)
        response = requests.post(url, json=data, timeout=timeout)
        latency_ms = _elapsed_ms(t0)

        if response.status_code == 200:
            result = response.json()
            content = result.get('response', '')
            if verbose:
                _LOGGER.debug(f" [LLM:Direct] Model '{model}' responded successfully ({len(content)} chars).")
            # R5-C: Extract token counts from Ollama response
            prompt_tokens = result.get('prompt_eval_count', 0) or 0
            response_tokens = result.get('eval_count', 0) or 0
            ctx = options.get("num_ctx", 4096)
            ctx_util = prompt_tokens / ctx if ctx > 0 and prompt_tokens > 0 else 0.0
            # `eval_duration` is generation-only nanoseconds (it excludes prompt
            # evaluation and model load), so eval_count / eval_duration is the
            # decode rate — comparable across models in a way that
            # response_tokens / latency_ms is not. Guarded on its own: a server
            # that reports the duration as a string or omits it must not turn a
            # good reply into a failed call via the catch-all below, which the
            # retry loop would then read as empty content.
            try:
                eval_duration_ns = float(result.get('eval_duration', 0) or 0)
                tokens_per_second = (
                    response_tokens / (eval_duration_ns / 1e9)
                    if eval_duration_ns > 0 and response_tokens > 0 else 0.0
                )
            except (TypeError, ValueError, ZeroDivisionError):
                tokens_per_second = 0.0
            stats = LLMStats(
                retries=0, success=True,
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                num_ctx=ctx,
                context_utilization=ctx_util,
                latency_ms=latency_ms,
                tokens_per_second=tokens_per_second,
                calls=1,
                prompt_tokens_total=prompt_tokens,
                response_tokens_total=response_tokens,
            )
            return content, stats
        else:
            _LOGGER.error(f" [LLM:Direct] Model '{model}' HTTP Error {response.status_code}: {response.text}")
            # Spec item 24 fix round: transport_error=True only for 5xx (a
            # server-side condition a retry can plausibly ride out); a 4xx is
            # a persistent client-side problem (bad request body, auth) that
            # retrying will not fix, so it is left False -- the backoff
            # wrapper reads this flag to decide whether to retry at all.
            return "", LLMStats(
                retries=0, success=False, latency_ms=latency_ms,
                transport_error=(response.status_code >= 500),
            )
    except requests.exceptions.Timeout:
        _LOGGER.error(f" [LLM:Direct] Model '{model}' timed out after {timeout}s. Consider increasing timeout for this model.")
        # transport_error stays False (default) on purpose: this call already
        # waited the full configured timeout, so the backoff wrapper must not
        # retry it and wait again for no benefit (spec item 24 fix round).
        return "", LLMStats(retries=0, success=False, latency_ms=_elapsed_ms(t0))
    except requests.exceptions.ConnectionError:
        _LOGGER.error(f" [LLM:Direct] Model '{model}' connection refused. Is Ollama running at {url}?")
        # transport_error=True: a refused/reset connection is exactly the
        # transient failure the backoff wrapper exists to retry.
        return "", LLMStats(retries=0, success=False, latency_ms=_elapsed_ms(t0), transport_error=True)
    except Exception as e:
        _LOGGER.error(f" [LLM:Direct] Model '{model}' unexpected error: {type(e).__name__}: {e}")
        # transport_error stays False: an unclassified exception (a bug, a
        # parsing error in this function) is not assumed safe to retry.
        return "", LLMStats(retries=0, success=False, latency_ms=_elapsed_ms(t0))


def create_llm_invoke(model: str, verbose: bool = False, overrides: Optional[Dict[str, Any]] = None) -> LLMInvokeFunc:
    """
    Creates an invocation function for a given model using LangChain-Ollama.
    Includes robust error collection and diagnostic logging.
    
    Args:
        model: Model identifier
        verbose: Enable diagnostic logging
        overrides: Optional parameter overrides (num_predict, num_ctx, etc.)
    
    Returns:
        A callable that takes prompt str and returns (content, LLMStats) tuple.
    """
    # Phase 0.3: Route to modern provider factory ONLY for known cloud providers
    # This prevents "gemma3:4b" from being split into provider="gemma3"
    # (is_cloud_provider_model / KNOWN_CLOUD_PROVIDERS, module-level so the
    # reproducibility manifest can reuse the identical check, not a second
    # locally-scoped copy of the same list).
    if is_cloud_provider_model(model):
        parts = model.split(":", 1)
        provider_type = parts[0].lower()
        model_name = parts[1]

        # Build config dict for factory
        config = {
            "type": provider_type,
            "model": model_name
        }

        # Apply overrides if present (e.g. temperature). Note for anything
        # reading llm_params_resolved in the manifest: this is the RAW
        # overrides dict, never merged with LLM_CONFIG/resolve_ollama_params
        # (those are Ollama-request concepts; num_ctx/num_predict/etc. from
        # LLM_CONFIG are never applied here). See ExperimentRunner.get_llm_invoke,
        # which records this same raw dict for a cloud-provider agent type,
        # for exactly this reason.
        if overrides:
            config.update(overrides)

        return create_provider_invoke(config, verbose=verbose)


    # Domain-agnostic mock for testing — returns minimal JSON that
    # ModelAdapter can parse.  No PMT-specific constructs here; the
    # governance retry loop and ResponseFormatBuilder handle the rest.
    if model.lower().startswith("mock"):
        import json as _json
        def mock_invoke(prompt: str) -> Tuple[str, LLMStats]:
            import re
            stats = LLMStats(retries=0, success=True)

            # Extract the first numbered option from prompt (works for any domain)
            option_pattern = r'(\d+)\.\s+\w+'
            options = re.findall(option_pattern, prompt)
            decision_id = int(options[0]) if options else 1

            # Return minimal valid JSON — no domain-specific construct names
            content = _json.dumps({"decision": decision_id})
            return content, stats
        return mock_invoke
    
    try:
        from langchain_ollama import ChatOllama
        from langchain_ollama import OllamaLLM

        # Build params from global config, merged with any per-agent-type
        # overrides, via the shared helper, so this can never diverge from
        # what ExperimentRunner records in the reproducibility manifest's
        # llm_params_resolved (r19 G7/G8, see resolve_ollama_params docstring).
        # 'model' is stripped by the helper (it's passed explicitly above).
        ollama_params = resolve_ollama_params(overrides)

        # Select provider based on config
        if LLM_CONFIG.use_chat_api:
            _LOGGER.info(f" [LLM:Init] Using ChatOllama for model: {model}")
            llm = ChatOllama(model=model, **ollama_params)
        else:
            _LOGGER.info(f" [LLM:Init] Using OllamaLLM for model: {model}")
            llm = OllamaLLM(model=model, **ollama_params)
        
        def invoke(prompt: str) -> Tuple[str, LLMStats]:
            debug_llm = verbose

            if debug_llm:
                _LOGGER.debug(f"\n [LLM:Input] (len={len(prompt)}) Prompt begins: {repr(prompt[:100])}...")
            
            # Phase 40: Use global or override retry limit
            max_llm_retries = overrides.get("max_retries", LLM_CONFIG.max_retries) if overrides else LLM_CONFIG.max_retries

            # Apply config-driven model quirks (replaces hardcoded DeepSeek/Qwen3 logic)
            current_prompt = prompt
            current_prompt, max_llm_retries = LLM_CONFIG.apply_model_quirks(
                model, current_prompt, max_llm_retries,
            )

            llm_retries = 0
            empty_content_retries = 0  # 045-H: Track empty content retries specifically

            # 2026-09-15: every return below used to build a FRESH LLMStats and
            # so threw away everything `_invoke_ollama_direct` had measured —
            # which is why `prompt_tokens` / `response_tokens` / `num_ctx` /
            # `context_utilization` read 0 on every row of every released audit
            # CSV despite the extraction working since R5-C. These carry the
            # measurement across.
            calls_made = 0
            acc_prompt_tokens = 0
            acc_response_tokens = 0
            last_stats = LLMStats(retries=0, success=False, calls=0)

            def _final_stats(success: bool, *, empty_failure: bool = False) -> LLMStats:
                """The loop's stats: last attempt's measurements + all-attempt totals."""
                return LLMStats(
                    retries=llm_retries, success=success,
                    empty_content_retries=empty_content_retries,
                    empty_content_failure=empty_failure,
                    prompt_tokens=last_stats.prompt_tokens,
                    response_tokens=last_stats.response_tokens,
                    num_ctx=last_stats.num_ctx,
                    context_utilization=last_stats.context_utilization,
                    latency_ms=last_stats.latency_ms,
                    tokens_per_second=last_stats.tokens_per_second,
                    # A call that raised before returning stats still happened;
                    # counting 0 would under-report the run's call budget.
                    calls=max(calls_made, 1),
                    prompt_tokens_total=acc_prompt_tokens,
                    response_tokens_total=acc_response_tokens,
                    # Spec item 24 fix round 3 (CRITICAL 1): without this,
                    # _invoke_ollama_direct's transport_error=True (set on a
                    # ConnectionError or an HTTP 5xx) never survived this
                    # reconstruction, so broker.utils.llm_safeguard's backoff
                    # wrapper -- which wraps THIS closure, not
                    # _invoke_ollama_direct directly -- always saw
                    # transport_error=False and never retried a single real
                    # Ollama connection failure. Verified with the real
                    # create_llm_invoke('gemma3:4b').
                    transport_error=getattr(last_stats, "transport_error", False),
                )

            for attempt in range(max_llm_retries):
                try:
                    # Phase 46F: UNIVERSAL DIRECT API for ALL Ollama models
                    # This bypasses LangChain entirely and ensures:
                    # 1. Native JSON mode (format: "json") for strict output
                    # 2. Consistent behavior across all model families
                    # 3. Avoids Python 3.14 compatibility issues
                    # LangChain path is deprecated but preserved for potential cloud providers
                    content, stats = _invoke_ollama_direct(model, current_prompt, ollama_params, debug_llm)
                    calls_made += 1
                    acc_prompt_tokens += stats.prompt_tokens
                    acc_response_tokens += stats.response_tokens
                    last_stats = stats

                    if debug_llm:
                        _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(content[:200] if content else '')}...")
                    
                    # Strip thinking tokens (<think>...</think>) based on config
                    import re
                    stripped_content = content
                    if content and LLM_CONFIG.should_strip_thinking():
                        stripped_content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                        if debug_llm and stripped_content != content.strip():
                            _LOGGER.debug(f" [LLM:ThinkStrip] Removed thinking tokens (mode={LLM_CONFIG.thinking_mode}), extracted: {repr(stripped_content[:100])}...")
                    elif content:
                        stripped_content = content.strip()
                    
                    if stripped_content and stripped_content.strip():
                        return content, _final_stats(True)  # Return full content for logging
                    else:
                        llm_retries += 1
                        empty_content_retries += 1  # 045-H: Track empty content retries
                        if attempt < max_llm_retries - 1:
                            if content and not stripped_content.strip():
                                _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned ONLY thinking content. Appending 'Please continue'.")
                                current_prompt += " \nPlease continue and output the JSON."
                            else:
                                _LOGGER.warning(f" [LLM:Retry] Model '{model}' returned truly empty content. Retrying...")
                                current_prompt += " "
                        else:
                            _LOGGER.error(f" [LLM:Error] Model '{model}' returned empty content after {max_llm_retries} attempts.")
                            return "", _final_stats(False, empty_failure=True)
                except (ConnectionError, OSError) as e:
                    llm_retries += 1
                    _LOGGER.error(f" [LLM:Error] Connection to Ollama failed for '{model}': {e}")
                    if attempt < max_llm_retries - 1:
                        current_prompt += " "
                        continue
                    return "", _final_stats(False)
                except Exception as e:
                    llm_retries += 1
                    _LOGGER.error(f" [LLM:Error] {type(e).__name__} during call to '{model}': {e}")
                    if attempt < max_llm_retries - 1:
                        current_prompt += " "
                        continue
                    return "", _final_stats(False)
            return "", _final_stats(False)
        
        return invoke
    # Both branches below previously returned ``lambda p: ('{"decision": 1}', LLMStats())``
    # and logged a warning. That is not a fallback to the mock model -- the requested-mock
    # path above parses the prompt and selects an option, while this constant answers every
    # prompt in a run identically. A 42-year, 78-agent experiment would complete, write
    # 3,276 rows, pass its row-count and join checks, and be indistinguishable from a real
    # run in every artifact it produces.
    #
    # The failure direction was wrong. Constructing an LLM fails at startup or not at all,
    # so raising costs an operator thirty seconds; the silent constant costs ten GPU-hours
    # and yields a corpus that looks real. Verified before changing: no test and no caller
    # depends on the old behaviour -- `test_mock_models_bypass_factory_and_ollama` asserts
    # ollama is never touched for mock models, so it takes the branch above, and
    # `test_cloud_provider_routing` installs a working fake.
    #
    # Reachability is not hypothetical: this environment already warns that Pydantic V1 is
    # incompatible with Python 3.14, and any dependency update that turns that warning into
    # an exception would, before this change, have silently converted every subsequent run
    # into constant output. Corrected 2026-08-06.
    except ImportError as e:
        raise RuntimeError(
            f"Cannot construct an LLM for model {model!r}: langchain-ollama is not "
            f"importable ({e}). Install it, or pass a model name beginning with 'mock' "
            f"if a mock run is what you want."
        ) from e
    except Exception as e:
        raise RuntimeError(
            f"Cannot construct an LLM for model {model!r}: {e}"
        ) from e


def create_provider_invoke(config: Dict[str, Any], verbose: bool = False) -> LLMInvokeFunc:
    """
    Creates an invocation function using the new v0.3 Provider Factory.
    This is the modern way to instantiate LLMs (Gemini, OpenAI, Ollama).
    
    Args:
        config: Provider configuration (type, model, temperature, etc.)
        verbose: Enable diagnostic logging
        
    Returns:
        A callable that takes prompt str and returns (content, LLMStats) tuple.
    """
    from providers.factory import create_provider
    provider = create_provider(config)
    
    def invoke(prompt: str) -> Tuple[str, LLMStats]:
        if verbose:
            _LOGGER.debug(f"\n [LLM:Input] {provider.provider_name}:{provider.config.model} Prompt begins: {repr(prompt[:100])}...")
        
        t0 = time.perf_counter()
        try:
            # Note: Provider handles its own internal configuration (temp, tokens)
            response = provider.invoke(prompt)
            latency_ms = _elapsed_ms(t0)

            # Map usage stats to framework standard. Every shipped provider
            # (`providers/ollama.py`, `openai_provider.py`, `anthropic.py`,
            # `gemini.py`) fills LLMResponse.usage with prompt_tokens /
            # completion_tokens; this function used to build an empty LLMStats
            # and drop all of it, which is the cloud-provider twin of the
            # `create_llm_invoke` drop. `num_ctx` stays 0: a hosted provider
            # does not report the window it used, and inventing one would make
            # context_utilization a fabricated ratio.
            # Guarded on its own, NOT by the catch-all below. `usage` is only
            # annotated as a dict (providers/llm_provider.py) and a third-party
            # provider can hand back an SDK object, or counts as strings —
            # either of which would raise, be caught below, and turn a
            # SUCCESSFUL model reply into `("", success=False)`, which the retry
            # loop reads as empty content. Instrumentation must never decide
            # whether a call succeeded.
            try:
                usage = getattr(response, "usage", None) or {}
                prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
                response_tokens = int(usage.get("completion_tokens", 0) or 0)
            except (AttributeError, TypeError, ValueError):
                _LOGGER.warning(
                    " [LLM:Stats] %s returned an unreadable `usage`; the reply "
                    "stands, token counts for this call are recorded as 0.",
                    provider.provider_name,
                )
                prompt_tokens = response_tokens = 0
            stats = LLMStats(
                retries=0,
                success=True,
                prompt_tokens=prompt_tokens,
                response_tokens=response_tokens,
                latency_ms=latency_ms,
                calls=1,
                prompt_tokens_total=prompt_tokens,
                response_tokens_total=response_tokens,
            )

            if verbose:
                _LOGGER.debug(f" [LLM:Output] Raw Content: {repr(response.content[:200])}...")

            return response.content, stats
        except (ConnectionError, OSError) as e:
            _LOGGER.error(f" [LLM:Error] {provider.provider_name} connection failed: {e}")
            # Spec item 24 fix round: transport_error=True, the same signal
            # _invoke_ollama_direct sends for its own ConnectionError branch --
            # a connection failure is what the backoff wrapper retries.
            return "", LLMStats(retries=0, success=False, latency_ms=_elapsed_ms(t0), transport_error=True)
        except Exception as e:
            _LOGGER.error(f" [LLM:Error] {provider.provider_name} {type(e).__name__}: {e}")
            # transport_error stays False: an unclassified provider exception
            # (auth failure, malformed request, SDK bug) is not retried.
            return "", LLMStats(retries=0, success=False, latency_ms=_elapsed_ms(t0))

    return invoke


# =============================================================================
# LEGACY COMPATIBILITY (Deprecated - use tuple return directly)
# =============================================================================

# Thread-local storage for backward compatibility
_llm_stats = {"current_retries": 0, "current_success": True}

def get_llm_stats() -> dict:
    """
    DEPRECATED: Get the last LLM call's retry stats for audit logging.
    Prefer using the tuple return value from invoke directly.
    """
    return _llm_stats.copy()

def create_legacy_invoke(model: str, verbose: bool = False) -> Callable[[str], str]:
    """
    Creates a legacy invoke function that returns only content (not tuple).
    Updates global _llm_stats for backward compatibility.
    """
    tuple_invoke = create_llm_invoke(model, verbose)
    
    def legacy_invoke(prompt: str) -> str:
        global _llm_stats
        content, stats = tuple_invoke(prompt)
        _llm_stats = {"current_retries": stats.retries, "current_success": stats.success}
        return content
    
    return legacy_invoke


