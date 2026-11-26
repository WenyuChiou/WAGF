"""Memory engine and reflection settings for ``python -m broker.run``.

Read from the case YAML (design decisions, Wenyu 2026-11-25):

- ``global_config.memory.engine_type`` picks one engine for the whole run:
  ``window`` (the default, as before) or ``humancentric``.
- ``global_config.memory.window_size`` caps what the window engine keeps only
  when it is written; unset, the engine keeps its last 100 items as before.
- Reflection runs only with ``global_config.reflection.enabled: true``: every
  ``interval`` years, and in a year an agent ran a skill listed in
  ``triggers.decision_types``. Each lesson is stored as a memory of type
  ``reflection`` with importance ``importance_boost``; the humancentric engine
  moves such an item to long-term memory (importance >= its
  consolidation_threshold), where ``top_k_significant`` keeps retrieving it.
- Where the engines' own defaults disagree, broker.run applies the table
  below. Every effective value is recorded in ``broker_run.json``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any

from broker.components.cognitive.reflection import (
    ReflectionEngine,
    _memory_text,
    store_reflection_memory,
)
from broker.components.context.providers import DEFAULT_RETRIEVAL_TOP_K
from broker.components.memory.engine import WindowMemoryEngine
from broker.components.memory.factory import create_memory_engine, validate_fraction
from broker.components.memory.registry import HUMANCENTRIC_PASSTHROUGH_KEYS
from broker.utils.llm_utils import is_mock_model

logger = logging.getLogger(__name__)

ENGINES = ("window", "humancentric")
_ENGINE_ALIASES = {"human_centric": "humancentric"}
_REFUSED_ENGINES = {
    "importance": "deprecated",
    "hierarchical": "deprecated",
    "universal": "a research engine that only the multi-agent flood runner builds",
}

# Window the window engine is built with when the YAML has no
# global_config.memory.window_size (it then keeps its last 100 items, so the
# value changes nothing). Named so the parameter table can read it.
DEFAULT_WINDOW_SIZE = 3
# broker.run's own defaults for the humancentric engine, where the engine
# constructor (window 3), the registry factory (window 5) and the
# hierarchical engine (top_k_significant 3) disagree.
HUMANCENTRIC_DEFAULTS = {"window_size": 3, "top_k_significant": 2, "ranking_mode": "legacy"}
# Keys of global_config.memory the humancentric engine reads on broker.run.
_HUMANCENTRIC_KEYS = (
    "window_size", "top_k_significant", "consolidation_probability", "decay_rate",
    *HUMANCENTRIC_PASSTHROUGH_KEYS,
)
_HUMANCENTRIC_INT_KEYS = ("window_size", "top_k_significant", "max_working", "max_longterm", "seed")

# broker.run's reflection defaults. importance_boost is 0.9 as in
# ReflectionEngine and get_reflection_config (ReflectionTriggerConfig says 0.85).
REFLECTION_DEFAULTS = {"interval": 1, "importance_boost": 0.9}
# Start of every reflection memory line broker.run stores.
REFLECTION_PREFIX = "Reflection (year"


def _block(raw, scope, name):
    holder = raw.get(scope) or {}
    if not isinstance(holder, dict):
        raise ValueError(f"{scope} must be a mapping")
    block = holder.get(name) or {}
    if not isinstance(block, dict):
        raise ValueError(f"{scope}.{name} must be a mapping")
    return block


def _int_at_least(where, value, low):
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(f"{where} must be an integer >= {low}, got {value!r}")
    return value


@dataclass
class MemorySettings:
    """The engine broker.run builds and the arguments it passes."""

    engine: str
    params: dict

    def record(self, retrieval_top_k):
        params = dict(self.params)
        if self.engine == "window" and not params.pop("enforce_window"):
            params["window_size"] = None  # not set: the engine keeps its last 100 items
        else:
            params.pop("enforce_window", None)
        return {"engine": self.engine, **params, "retrieval_top_k": retrieval_top_k}


def memory_settings(raw, seed) -> MemorySettings:
    """Read ``global_config.memory`` into the engine broker.run builds.

    The humancentric engine is seeded with ``memory.seed`` when set, else the
    run seed, so its stochastic consolidation repeats run to run.
    """
    block = _block(raw, "global_config", "memory")
    engine = block.get("engine_type", "window")
    if not isinstance(engine, str) or not engine.strip():
        raise ValueError(f"global_config.memory.engine_type must be a string, got {engine!r}")
    name = engine.strip().lower()
    name = _ENGINE_ALIASES.get(name, name)
    if name not in ENGINES:
        why = _REFUSED_ENGINES.get(name, "not a memory engine")
        raise ValueError(
            f"global_config.memory.engine_type {engine!r} is {why}; python -m broker.run "
            f"offers {' and '.join(ENGINES)}"
        )
    if name == "window":
        if "window_size" in block:
            size = _int_at_least("global_config.memory.window_size", block["window_size"], 1)
            return MemorySettings("window", {"window_size": size, "enforce_window": True})
        return MemorySettings("window", {"window_size": DEFAULT_WINDOW_SIZE, "enforce_window": False})

    params = {**HUMANCENTRIC_DEFAULTS, "seed": seed}
    params.update({key: block[key] for key in _HUMANCENTRIC_KEYS if key in block})
    for key in _HUMANCENTRIC_INT_KEYS:
        if key in params:
            # window_size 0 would leave the prompt with no recent memories.
            _int_at_least(f"global_config.memory.{key}", params[key], 1 if key == "window_size" else 0)
    if params["ranking_mode"] not in ("legacy", "weighted"):
        raise ValueError(
            f"global_config.memory.ranking_mode must be legacy or weighted, got {params['ranking_mode']!r}"
        )
    for key in ("consolidation_probability", "decay_rate"):
        if key in params:
            validate_fraction(f"global_config.memory.{key}", params[key])
    if params.get("decay_by_calendar_year") is True:
        # The engine raises on any memory without metadata['year'], and the
        # decision memories ExperimentRunner writes have none: every agent
        # turn from year 2 on would fail.
        raise ValueError(
            "global_config.memory.decay_by_calendar_year needs a year on every memory, and the "
            "decision memories python -m broker.run writes carry none; leave it off"
        )
    return MemorySettings("humancentric", params)


def build_memory_engine(settings: MemorySettings):
    if settings.engine == "window":
        return WindowMemoryEngine(**settings.params)
    return create_memory_engine("humancentric", dict(settings.params))


@dataclass
class ReflectionSettings:
    """Reflection as broker.run runs it; ``enabled`` False means none at all."""

    enabled: bool = False
    interval: int = REFLECTION_DEFAULTS["interval"]
    importance_boost: float = REFLECTION_DEFAULTS["importance_boost"]
    decision_types: tuple = ()
    keep_latest_only: bool = False
    persona_instruction: str | None = None

    def record(self):
        if not self.enabled:
            return {"enabled": False}
        return {
            "enabled": True,
            "interval": self.interval,
            "importance_boost": self.importance_boost,
            "decision_types": list(self.decision_types),
            "keep_latest_only": self.keep_latest_only,
            "persona_instruction": self.persona_instruction,
        }


_TRIGGER_REFUSALS = {
    "periodic_interval": "the period is reflection.interval",
    "institutional_threshold": "the institutional trigger needs a policy-change signal from the domain",
}


def reflection_settings(raw, config, memory: MemorySettings) -> ReflectionSettings:
    """Read ``global_config.reflection`` (over the legacy ``shared.reflection``).

    Off unless ``enabled: true``, so a YAML that already has a reflection
    block (every scaffolded domain does) runs as before. With it on, keys
    broker.run cannot honour are refused rather than ignored.
    """
    block = {**_block(raw, "shared", "reflection"), **_block(raw, "global_config", "reflection")}
    enabled = block.get("enabled", False)
    if not isinstance(enabled, bool):
        raise ValueError(f"reflection.enabled must be true or false, got {enabled!r}")
    if not enabled:
        return ReflectionSettings()

    interval = _int_at_least("reflection.interval", block.get("interval", REFLECTION_DEFAULTS["interval"]), 1)
    boost = block.get("importance_boost", REFLECTION_DEFAULTS["importance_boost"])
    validate_fraction("reflection.importance_boost", boost)
    if block.get("batch_size", 1) != 1:
        raise ValueError(
            f"python -m broker.run reflects one agent per call; set reflection.batch_size to 1 "
            f"or remove it (got {block['batch_size']!r})"
        )
    triggers = block.get("triggers") or {}
    if not isinstance(triggers, dict):
        raise ValueError("reflection.triggers must be a mapping")
    decision_types = ()
    for key, value in triggers.items():
        if key == "decision_types":
            if not isinstance(value, list) or not all(isinstance(s, str) and s for s in value):
                raise ValueError("reflection.triggers.decision_types must be a list of skill names")
            decision_types = tuple(value)
        elif key == "crisis":
            if value is not False:
                raise ValueError(
                    "reflection.triggers.crisis needs a crisis signal from the domain, which "
                    "python -m broker.run does not have; set it to false or remove it"
                )
        else:
            why = _TRIGGER_REFUSALS.get(key, "not a trigger python -m broker.run reads")
            raise ValueError(f"reflection.triggers.{key}: {why}; remove it")
    grounded = [key for key, on in config.get_reflection_grounding().items() if on]
    if grounded:
        raise ValueError(
            f"reflection.{', reflection.'.join(grounded)}: grounded reflection is run only by the "
            f"irrigation paper runner, not by python -m broker.run"
        )
    keep_latest_only = config.get_reflection_keep_latest_only()
    if keep_latest_only and memory.engine == "window":
        raise ValueError(
            "reflection.keep_latest_only needs an engine that can remove earlier reflections; "
            "set global_config.memory.engine_type to humancentric"
        )
    persona = block.get("persona_instruction")
    if persona is not None and (not isinstance(persona, str) or not persona.strip()):
        raise ValueError("reflection.persona_instruction must be a non-empty string")
    return ReflectionSettings(
        enabled=True, interval=interval, importance_boost=float(boost),
        decision_types=decision_types, keep_latest_only=keep_latest_only,
        persona_instruction=persona.strip() if persona else None,
    )


@dataclass
class ReflectionHook:
    """``post_year`` hook that runs reflection after the case's own post_year.

    For each active agent that is due, the agent's retrieved memories (earlier
    reflections left out) go into a reflection prompt; the model's lesson is
    logged to ``reflection_log.jsonl`` and stored as a memory. Under a mock
    model the lesson is a fixed line, so mock runs stay deterministic. A
    failed model call is counted and logged, and the run goes on.
    """

    settings: ReflectionSettings
    config: Any
    memory_engine: Any
    model: str
    output_dir: Path
    inner: Any = None
    runner: Any = None  # set once the runner is built
    counts: dict = field(default_factory=lambda: {
        "reflections_stored": 0, "replies_not_stored": 0, "failed_calls": 0,
    })

    def __post_init__(self):
        # No output_path: ReflectionEngine.store_insight logs a failed write
        # and goes on, so this hook writes reflection_log.jsonl itself and a
        # failed write stops the run instead of being counted as stored.
        self.engine = ReflectionEngine(
            reflection_interval=self.settings.interval,
            insight_importance_boost=self.settings.importance_boost,
        )
        self.log_path = Path(self.output_dir) / "reflection_log.jsonl"
        self._stored = {}  # agent id -> reflection memories this hook has stored

    def _log(self, agent_id, insight):
        """One line per stored reflection, in ReflectionEngine.store_insight's format."""
        entry = asdict(insight)
        entry["reflection_input"] = list(insight.reflection_input)
        entry["agent_id"] = agent_id
        entry["timestamp"] = datetime.now().isoformat()
        with open(self.log_path, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def __call__(self, year, agents):
        if self.inner is not None:
            self.inner(year, agents)
        for agent in agents.values():
            if getattr(agent, "is_active", True) and self._due(agent, year):
                self._reflect(agent, year)

    def _due(self, agent, year):
        if self.engine.should_reflect(agent.id, year):
            return True
        action = getattr(agent, "_last_action_context", None) or {}
        return (bool(self.settings.decision_types) and action.get("year") == year
                and action.get("skill_name") in self.settings.decision_types)

    def _memories(self, agent):
        mem_cfg = getattr(agent, "memory_config", None)
        mem_cfg = mem_cfg if isinstance(mem_cfg, dict) else {}
        top_k = int(mem_cfg.get("retrieval_top_k", DEFAULT_RETRIEVAL_TOP_K))
        # Earlier reflections are left out before the retrieval limit, so they
        # never take the slots of the other memories.
        if isinstance(self.memory_engine, WindowMemoryEngine):
            # The window engine returns the latest top_k items: ask for one
            # more per reflection stored, then keep the latest top_k others.
            # top_k 0 or less keeps the engine's own reading (0 is every
            # memory), the same memories the decision prompt gets.
            extra = self._stored.get(agent.id, 0) if top_k > 0 else 0
            items = self.memory_engine.retrieve(agent, top_k=top_k + extra)
            items = [m for m in items if not _memory_text(m).startswith(REFLECTION_PREFIX)]
            return items[-top_k:] if top_k > 0 else items
        # The humancentric engine's own option ranks without reflections (in
        # both ranking modes) and then appends the latest one, dropped here.
        items = self.memory_engine.retrieve(agent, top_k=top_k, reflection_slot="separate")
        return [m for m in items if not _memory_text(m).startswith(REFLECTION_PREFIX)]

    def _uses_mock(self, agent_type):
        """Whether this agent type's decisions run on the mock model.

        get_llm_invoke records the model it resolved for the type
        (llm_params.model, else the run model). A type it has no record for
        got its invoke from the case's run.mock slot, which is loaded only
        under a mock run model, so the run model decides.
        """
        resolved = (getattr(self.runner, "_llm_resolved_params", None) or {}).get(agent_type) or {}
        return is_mock_model(resolved.get("model") or self.model)

    def _call(self, agent_type, prompt, year, count):
        # The invoke this type's decisions use. Fetched first, even on the mock
        # path, so get_llm_invoke has recorded the model _uses_mock reads.
        invoke = self.runner.get_llm_invoke(agent_type)
        if self._uses_mock(agent_type):
            return f"(mock model) Year {year} reflection over {count} memories."
        raw = invoke(prompt)
        return raw[0] if isinstance(raw, tuple) else raw

    def _reflect(self, agent, year):
        memories = self._memories(agent)
        if not memories:
            return
        context = ReflectionEngine.extract_agent_context(agent, year)
        prompt = self.engine.generate_personalized_reflection_prompt(
            context, memories, year,
            reflection_questions=self.config.get_reflection_questions(agent.agent_type),
        )
        if self.settings.persona_instruction:
            prompt = f"{self.settings.persona_instruction}\n\n{prompt}"
        try:
            text = self._call(agent.agent_type, prompt, year, len(memories))
        except Exception as exc:  # one agent's failed call must not stop the run
            self.counts["failed_calls"] += 1
            logger.warning("[broker.run] reflection call failed for %s in year %s: %s", agent.id, year, exc)
            return
        insight = self.engine.parse_reflection_response(text if isinstance(text, str) else "",
                                                        len(memories), year)
        if insight is None:
            self.counts["replies_not_stored"] += 1
            return
        insight.reflection_input = [_memory_text(m) for m in memories]
        self._log(agent.id, insight)  # an OSError here stops the run
        self.engine.store_insight(agent.id, insight)
        store_reflection_memory(
            self.memory_engine, agent.id, f"{REFLECTION_PREFIX} {year}): {insight.summary}",
            {"importance": insight.importance, "type": "reflection", "source": "personal",
             "emotion": "major", "year": year},
            keep_latest_only=self.settings.keep_latest_only,
        )
        self._stored[agent.id] = self._stored.get(agent.id, 0) + 1
        self.counts["reflections_stored"] += 1
