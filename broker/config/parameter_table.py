"""The parameter table: every tunable number the broker reads, its range and its defaults.

``docs/references/parameter_table.md`` is generated from this module and must
not be edited by hand::

    python -m broker.config.parameter_table --write docs/references/parameter_table.md
    python -m broker.config.parameter_table --check docs/references/parameter_table.md

Nothing here repeats a default as a number. Each default is read from the code
that applies it: a constructor signature, an accessor called on an empty
config, a dataclass field, a ``_DEFAULTS`` entry or a named module constant.
When two consumers apply different defaults, the row lists each one.

``accepted_keys()`` harvests the numeric keys the code accepts, also from the
code. ``missing_rows()`` lists any accepted key without a row, so a new
parameter cannot be added without a row here (the test fails until it has one).
``accepted_section_keys()`` is what ``AgentTypeConfig.load(strict_keys=True)``
checks the keys inside each covered section against.
"""

from __future__ import annotations

import argparse
import dataclasses
import functools
import importlib
import importlib.util
import inspect
import ast
import os
import re
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, FrozenSet, List, Optional, Tuple


class _Missing:
    """Returned by a default function that cannot find its value in the code."""

    def __repr__(self) -> str:
        return "MISSING"


MISSING = _Missing()

GROUPS = ("fraction", "count", "with-unit", "exception")


@dataclass(frozen=True)
class Consumer:
    """One piece of code that applies a default for a row."""

    label: str                    # what the code is, e.g. "HumanCentricMemoryEngine"
    source: str                   # "file (Symbol)"
    default: Callable[[], Any]    # zero-argument; returns the default as the code applies it
    read_by: str                  # which runners reach this code


@dataclass(frozen=True)
class Row:
    path: str                     # YAML path, e.g. global_config.memory.decay_rate
    group: str                    # one of GROUPS
    meaning: str                  # one plain sentence
    range: str                    # e.g. "[0, 1]", "integer >= 1"
    unit: str                     # "" when the value has none
    consumers: Tuple[Consumer, ...]
    also_in: str = ""             # other places the key can sit


# ---------------------------------------------------------------------------
# Default readers. Each returns a zero-argument function.
# ---------------------------------------------------------------------------

def _load(module: str, attr: Optional[str] = None) -> Any:
    mod = importlib.import_module(module)
    return getattr(mod, attr) if attr else mod


def _param_default(parameter: inspect.Parameter) -> Any:
    return MISSING if parameter.default is inspect.Parameter.empty else parameter.default


def sig(module: str, symbol: str, param: str) -> Callable[[], Any]:
    """Default of ``param`` in the signature of ``module.symbol`` (a class or a function).

    ``symbol`` may be dotted for a method, e.g. ``AgentTypeConfig.get_governance_retries``.
    """
    def read() -> Any:
        target = _load(module)
        for part in symbol.split("."):
            target = getattr(target, part)
        parameter = inspect.signature(target).parameters.get(param)
        return MISSING if parameter is None else _param_default(parameter)
    return read


def registry_factory(engine: str, param: str) -> Callable[[], Any]:
    """Default of ``param`` in the signature of a memory-registry factory."""
    def read() -> Any:
        registry = _load("broker.components.memory.registry")
        parameter = inspect.signature(registry.MemoryEngineRegistry._engines[engine]).parameters.get(param)
        return MISSING if parameter is None else _param_default(parameter)
    return read


def accessor(method: str, *path: str) -> Callable[[], Any]:
    """Value an ``AgentTypeConfig`` accessor returns on an empty config, at ``path``."""
    def read() -> Any:
        from broker.utils.agent_config import AgentTypeConfig
        config = AgentTypeConfig()
        config._config = {}
        value: Any = getattr(config, method)()
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return MISSING
            value = value[key]
        return value
    return read


def multi_skill_max_skills() -> Callable[[], Any]:
    """``max_skills`` that ``get_multi_skill_config`` returns for a block that only says enabled."""
    def read() -> Any:
        from broker.utils.agent_config import AgentTypeConfig
        config = AgentTypeConfig()
        config._config = {"agent": {"multi_skill": {"enabled": True}}}
        return config.get_multi_skill_config("agent").get("max_skills", MISSING)
    return read


def const(module: str, name: str) -> Callable[[], Any]:
    """A module-level constant."""
    def read() -> Any:
        return getattr(_load(module), name, MISSING)
    return read


def dict_entry(module: str, name: str, key: str) -> Callable[[], Any]:
    """An entry of a module-level dict, e.g. ``_DEFAULTS["abort_window"]``."""
    def read() -> Any:
        table = getattr(_load(module), name, None)
        return table.get(key, MISSING) if isinstance(table, dict) else MISSING
    return read


def field_default(module: str, cls: str, name: str) -> Callable[[], Any]:
    """Default of a dataclass field."""
    def read() -> Any:
        for item in dataclasses.fields(_load(module, cls)):
            if item.name == name:
                if item.default is not dataclasses.MISSING:
                    return item.default
                if item.default_factory is not dataclasses.MISSING:
                    return item.default_factory()
        return MISSING
    return read


def llm_yaml_default(name: str) -> Callable[[], Any]:
    """What ``_load_global_config`` applies when the ``llm`` block lacks ``name``.

    Runs the real function in an empty folder with a stand-in config loader, so
    the answer is whatever the code does, and the loader's cache is untouched.
    """
    def read() -> Any:
        llm_utils = _load("broker.utils.llm_utils")

        class _Empty:
            def get(self, key, default=None):
                return {"llm": {}} if key == "global_config" else default

        previous = Path.cwd()
        original = llm_utils.load_agent_config
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "agent_types.yaml").write_text("global_config:\n  llm: {}\n", encoding="utf-8")
            os.chdir(folder)
            llm_utils.load_agent_config = lambda *args, **kwargs: _Empty()
            try:
                built = llm_utils._load_global_config()
            finally:
                llm_utils.load_agent_config = original
                os.chdir(previous)
        return getattr(built, name, MISSING)
    return read


# ---------------------------------------------------------------------------
# Who reads what: the "read by" wording, kept in one place.
# ---------------------------------------------------------------------------

RB_HC = ("paper runners that build HumanCentricMemoryEngine (single_agent, governed_flood, "
         "irrigation_abm, multi_agent/flood), and broker.run with engine_type humancentric "
         "for the keys it does not set itself")
RB_REG_HC = ("registry factory \"humancentric\" (create_memory_engine), which broker.run calls for "
             "engine_type humancentric; broker.run passes its own window_size and top_k_significant")
RB_UNIVERSAL = ("UniversalCognitiveEngine through create_memory_engine (single_agent and "
                "multi_agent/flood, selector `universal`); broker.run does not")
RB_ACC_MEM = "accessor get_global_memory_config; only multi_agent/flood reads it"
RB_RUN_WINDOW = ("broker.run with the window engine when the YAML has no window_size: the engine "
                 "then keeps its last 100 items, so this value changes nothing (a written "
                 "window_size caps what it keeps)")
RB_RUN_HC = "broker.run with engine_type humancentric"
RB_RUN_REFL = "broker.run, when reflection.enabled is true"
RB_WINDOW_DIRECT = "direct WindowMemoryEngine(...) calls (quickstart, cat_model, reservoir examples)"
RB_HIER = "registry factory \"hierarchical\" (deprecated engine)"
RB_PROVIDER = "MemoryProvider, in every runner that builds prompts with TieredContextBuilder, broker.run included"
RB_REFLECTION = ("paper runners through get_reflection_config (single_agent, governed_flood, "
                 "irrigation_abm); broker.run reads the block itself")
RB_TRIGGER = "ReflectionTriggerConfig, filled by load_trigger_config, which no runner calls"
RB_REFL_ENGINE = "ReflectionEngine built by the paper runners; broker.run passes its own values"
RB_ACCESSOR_ONLY = "accessor only; no runner reads it"
RB_GOVERNANCE = "SkillBrokerEngine, so every runner, broker.run included"
RB_SAFEGUARD = "SkillBrokerEngine and ExperimentRunner, so every runner, broker.run included (no-op while enabled is false)"
RB_LLM_YAML = ("LLM_CONFIG, built at import from the agent_types.yaml in the current folder; "
               "every runner, broker.run included")
RB_LLM_NOFILE = "LLM_CONFIG when the current folder has no agent_types.yaml"
RB_RUN = "broker.run only"
RB_PARSE = "unified response parser, every runner that uses it, broker.run included"
RB_SOCIAL = "SocialMediaProvider, only when social_feeds is switched on (multi_agent/flood reads the YAML)"

_HC_SRC = "broker/components/memory/engines/humancentric.py (HumanCentricMemoryEngine.__init__)"
_UNI_SRC = "broker/components/memory/universal.py (UniversalCognitiveEngine.__init__)"
_REG_SRC = "broker/components/memory/registry.py (_register_builtins, humancentric factory)"
_ACC_MEM_SRC = "broker/utils/agent_config.py (AgentTypeConfig.get_global_memory_config)"
_REFL_ACC_SRC = "broker/utils/agent_config.py (AgentTypeConfig.get_reflection_config)"
_TRIG_SRC = "broker/components/cognitive/reflection.py (ReflectionTriggerConfig)"
_ENGINE_SRC = "broker/components/cognitive/reflection.py (ReflectionEngine.__init__)"

_HCM = "broker.components.memory.engines.humancentric"
_UNI = "broker.components.memory.universal"
_REFL = "broker.components.cognitive.reflection"


def _hc(param: str) -> Consumer:
    return Consumer("HumanCentricMemoryEngine", _HC_SRC, sig(_HCM, "HumanCentricMemoryEngine", param), RB_HC)


def _uni(param: str) -> Consumer:
    return Consumer("UniversalCognitiveEngine", _UNI_SRC, sig(_UNI, "UniversalCognitiveEngine", param), RB_UNIVERSAL)


def _acc_mem(key: str) -> Consumer:
    return Consumer("get_global_memory_config", _ACC_MEM_SRC, accessor("get_global_memory_config", key), RB_ACC_MEM)


def _reg_hc(param: str) -> Consumer:
    return Consumer("registry humancentric factory", _REG_SRC, registry_factory("humancentric", param), RB_REG_HC)


def _run_hc(key: str) -> Consumer:
    return Consumer("broker.run humancentric defaults", "broker/run/_memory.py (HUMANCENTRIC_DEFAULTS)",
                    dict_entry("broker.run._memory", "HUMANCENTRIC_DEFAULTS", key), RB_RUN_HC)


def _run_refl(key: str) -> Consumer:
    return Consumer("broker.run reflection defaults", "broker/run/_memory.py (REFLECTION_DEFAULTS)",
                    dict_entry("broker.run._memory", "REFLECTION_DEFAULTS", key), RB_RUN_REFL)


def _trig(name: str, read_by: str = RB_TRIGGER) -> Consumer:
    return Consumer("ReflectionTriggerConfig", _TRIG_SRC, field_default(_REFL, "ReflectionTriggerConfig", name), read_by)


def _refl_acc(key: str) -> Consumer:
    return Consumer("get_reflection_config", _REFL_ACC_SRC, accessor("get_reflection_config", key), RB_REFLECTION)


def _gov_acc(method: str, read_by: str, *path: str) -> Consumer:
    return Consumer(method, f"broker/utils/agent_config.py (AgentTypeConfig.{method})",
                    accessor(method, *path), read_by)


def _llm_pair(name: str) -> Tuple[Consumer, Consumer]:
    return (
        Consumer("_load_global_config (llm block present, key absent)",
                 "broker/utils/llm_utils.py (_load_global_config)", llm_yaml_default(name), RB_LLM_YAML),
        Consumer("LLMConfig()", "broker/utils/llm_utils.py (LLMConfig)",
                 field_default("broker.utils.llm_utils", "LLMConfig", name), RB_LLM_NOFILE),
    )


def _safeguard(key: str) -> Consumer:
    return Consumer("llm_safeguard defaults", "broker/utils/llm_safeguard.py (_DEFAULTS)",
                    dict_entry("broker.utils.llm_safeguard", "_DEFAULTS", key), RB_SAFEGUARD)


def _run(key: str) -> Consumer:
    return Consumer("broker.run defaults", "broker/run/_entry.py (_DEFAULTS)",
                    dict_entry("broker.run._entry", "_DEFAULTS", key), RB_RUN)


_G = "global_config"


def _build_rows() -> Tuple[Row, ...]:
    mem = f"{_G}.memory"
    refl = f"{_G}.reflection"
    gov = f"{_G}.governance"
    mem_also = "`shared.memory` (legacy) and an agent block, `<agent_type>.memory`"
    refl_also = "`shared.reflection` (legacy) and an agent block, `<agent_type>.reflection`"
    rows: List[Row] = []
    add = rows.append

    # -- fractions: memory ---------------------------------------------------
    add(Row(f"{mem}.decay_rate", "fraction",
            "How fast a memory fades as it ages (the lambda in e to the minus lambda times age).",
            "[0, 1]", "", (
                _hc("decay_rate"), _reg_hc("decay_rate"), _uni("decay_rate"), _acc_mem("decay_rate"),
            ), mem_also))
    add(Row(f"{mem}.consolidation_probability", "fraction",
            "Chance that an important memory moves into long-term memory "
            "(the engines also accept the spelling consolidation_prob).",
            "[0, 1]", "", (
                _reg_hc("consolidation_probability"), _hc("consolidation_prob"),
                _uni("consolidation_prob"), _acc_mem("consolidation_probability"),
            ), mem_also))
    add(Row(f"{mem}.consolidation_threshold", "fraction",
            "Lowest importance at which a memory can move into long-term memory.",
            "[0, 1]", "", (_hc("consolidation_threshold"), _uni("consolidation_threshold"),
                           _acc_mem("consolidation_threshold")), mem_also))
    add(Row(f"{mem}.forgetting_threshold", "fraction",
            "Memories whose strength falls below this are dropped.",
            "[0, 1]", "", (_hc("forgetting_threshold"),), mem_also))
    for name, text in (
        ("W_recency", "Weight of recency in the weighted memory ranking."),
        ("W_importance", "Weight of importance in the weighted memory ranking."),
        ("W_context", "Weight of match with the current situation in the weighted memory ranking."),
    ):
        add(Row(f"{mem}.{name}", "fraction", text, "[0, 1]", "", (_hc(name), _uni(name)), mem_also))
    add(Row(f"{mem}.W_relevance", "fraction",
            "Weight of query relevance in the weighted ranking (0 switches it off).",
            "[0, 1]", "", (_hc("W_relevance"),), mem_also))
    add(Row(f"{mem}.W_interference", "fraction",
            "Weight of the penalty for look-alike memories in the weighted ranking (0 switches it off).",
            "[0, 1]", "", (_hc("W_interference"),), mem_also))
    add(Row(f"{mem}.interference_cap", "fraction",
            "Upper limit on the look-alike penalty.", "[0, 1]", "", (_hc("interference_cap"),), mem_also))
    add(Row(f"{mem}.ema_alpha", "fraction",
            "Smoothing weight of the running average the universal engine compares each new "
            "stimulus against.", "[0, 1]", "", (_uni("ema_alpha"),), mem_also))
    for key, text in (
        ("recency", "Recency weight, as the runners read it (they pass it on as W_recency)."),
        ("importance", "Importance weight, as the runners read it (they pass it on as W_importance)."),
        ("context", "Context weight, as the runners read it (they pass it on as W_context)."),
    ):
        add(Row(f"{mem}.retrieval_weights.{key}", "fraction", text, "[0, 1]", "",
                (Consumer("HumanCentricMemoryEngine (W_" + key + ")", _HC_SRC,
                          sig(_HCM, "HumanCentricMemoryEngine", "W_" + key),
                          "paper runners map this key to the W_ weight; irrigation_abm falls back to "
                          "its adapter's weights when the key is absent"),),
                "an agent block, `<agent_type>.memory.retrieval_weights`"))

    # -- fractions: reflection ----------------------------------------------
    add(Row(f"{refl}.importance_boost", "fraction",
            "Importance given to a stored reflection.", "[0, 1]", "", (
                _refl_acc("importance_boost"),
                Consumer("ReflectionEngine", _ENGINE_SRC, sig(_REFL, "ReflectionEngine", "insight_importance_boost"),
                         RB_REFL_ENGINE),
                _trig("importance_boost"), _run_refl("importance_boost"),
            ), refl_also))
    add(Row(f"{refl}.base_importance", "fraction",
            "Importance a reflection gets when no domain rule supplies one. Accessor only: no "
            "production caller passes it on yet.", "[0, 1]", "", (
                _refl_acc("base_importance"),
                Consumer("ReflectionEngine.compute_dynamic_importance", _ENGINE_SRC,
                         sig(_REFL, "ReflectionEngine.compute_dynamic_importance", "base_importance"),
                         "accessor only; no runner passes the YAML value on"),
            ), refl_also))
    add(Row(f"{refl}.triggers.institutional_threshold", "fraction",
            "Size of a policy change (as a fraction) that makes an institution reflect.",
            "[0, 1]", "", (_trig("institutional_threshold"),), refl_also))

    # -- fractions: governance ----------------------------------------------
    drift_acc = "get_drift_config"
    for key, text in (
        ("entropy_threshold", "Action diversity (entropy) below this raises the low-diversity alert."),
        ("stagnation_threshold", "Share of stagnant agents above this raises the stagnation alert."),
        ("collapse_threshold", "Share of one action above this raises the mode-collapse alert."),
        ("jaccard_stagnation_threshold", "Similarity above this marks an agent as stagnant."),
    ):
        add(Row(f"{gov}.drift.{key}", "fraction", text, "[0, 1]", "", (
            _gov_acc(drift_acc, RB_ACCESSOR_ONLY, key),
            Consumer("DriftDetector", "broker/components/analytics/drift.py (DriftDetector.__init__)",
                     sig("broker.components.analytics.drift", "DriftDetector", key), RB_ACCESSOR_ONLY),
        ), "`shared.governance.drift` (legacy)"))
    pop_read = "multi_agent/flood runner, when cross-agent validation is on"
    for key, text in (
        ("echo_threshold", "Share of one skill above which the echo-chamber check fires."),
        ("entropy_threshold", "Diversity (entropy) below this is flagged by the cross-agent check."),
        ("deadlock_threshold", "Rejection rate above which the deadlock check fires."),
    ):
        add(Row(f"{gov}.population.{key}", "fraction", text, "[0, 1]", "", (
            _gov_acc("get_population_governance_config", pop_read, key),
            Consumer("CrossAgentValidator",
                     "broker/validators/governance/cross_agent_validator.py (CrossAgentValidator.__init__)",
                     sig("broker.validators.governance.cross_agent_validator", "CrossAgentValidator", key),
                     pop_read),
        ), "`shared.governance.population` (legacy)"))
    add(Row(f"{gov}.population.quorum_threshold", "fraction",
            "Share of agents that must pass for the council's majority mode to pass.", "[0, 1]", "", (
                _gov_acc("get_population_governance_config",
                         "accessor read by multi_agent/flood, which does not use this key (no council there)",
                         "quorum_threshold"),
                Consumer("CouncilValidator", "broker/validators/agent/council.py (CouncilValidator.__init__)",
                         sig("broker.validators.agent.council", "CouncilValidator", "quorum_threshold"),
                         "direct CouncilValidator(...) calls; no runner passes the YAML value"),
            ), "`shared.governance.population` (legacy)"))
    pol = f"{gov}.memory.resolution_importance_policy"
    for key, text in (
        ("approved", "Importance of the memory written when an action is approved."),
        ("denied", "Importance of the memory written when an action is denied."),
    ):
        add(Row(f"{pol}.{key}", "fraction", text, "[0, 1]", "", (
            _gov_acc("get_bridge_importance_config", "multi_agent/flood runner, through MemoryBridge", key),
            Consumer("MemoryBridge", "broker/components/memory/bridge.py (_DEFAULT_RESOLUTION_IMPORTANCE)",
                     dict_entry("broker.components.memory.bridge", "_DEFAULT_RESOLUTION_IMPORTANCE", key),
                     "multi_agent/flood runner, through MemoryBridge"),
        ), "`shared.governance.memory.resolution_importance_policy` (legacy)"))

    add(Row(f"{_G}.llm_safeguard.abort_threshold", "fraction",
            "Share of failed model calls (over abort_window decisions) that stops the run. "
            "Must be above 0.", "(0, 1]", "", (_safeguard("abort_threshold"),)))

    # -- counts --------------------------------------------------------------
    add(Row(f"{mem}.window_size", "count",
            "How many of an agent's most recent memories the engine keeps in its short-term window.",
            "integer >= 1", "", (
                _hc("window_size"), _reg_hc("window_size"), _uni("window_size"), _acc_mem("window_size"),
                Consumer("WindowMemoryEngine", "broker/components/memory/engines/window.py (WindowMemoryEngine.__init__)",
                         sig("broker.components.memory.engines.window", "WindowMemoryEngine", "window_size"),
                         RB_WINDOW_DIRECT),
                Consumer("broker.run", "broker/run/_memory.py (DEFAULT_WINDOW_SIZE)",
                         const("broker.run._memory", "DEFAULT_WINDOW_SIZE"), RB_RUN_WINDOW),
                _run_hc("window_size"),
            ), mem_also))
    add(Row(f"{mem}.top_k_significant", "count",
            "How many long-term memories the engine adds to the recent window when it retrieves.",
            "integer >= 0", "", (
                _hc("top_k_significant"), _reg_hc("top_k_significant"), _uni("top_k_significant"),
                _acc_mem("top_k_significant"),
                Consumer("registry hierarchical factory", "broker/components/memory/registry.py (_hierarchical_factory)",
                         registry_factory("hierarchical", "top_k_significant"), RB_HIER),
                _run_hc("top_k_significant"),
            ), mem_also))
    add(Row(f"{mem}.max_working", "count",
            "Largest number of items in working memory; 0 means no limit.", "integer >= 0", "",
            (_hc("max_working"),), mem_also))
    add(Row(f"{mem}.max_longterm", "count",
            "Largest number of items in long-term memory; 0 means no limit.", "integer >= 0", "",
            (_hc("max_longterm"),), mem_also))
    add(Row(f"{mem}.seed", "count",
            "Random seed of the memory engine; absent means unseeded.", "integer", "", (
                _hc("seed"), _uni("seed")), mem_also))
    add(Row("<agent_type>.memory.retrieval_top_k", "count",
            "How many memories go into the prompt. Read from the agent's own memory block, not from "
            "global_config. The window engine returns at most this many (fewer when window_size is "
            "smaller); the humancentric engine in legacy ranking ignores it and returns window_size "
            "recent plus top_k_significant long-term items.",
            "integer >= 1", "", (
                Consumer("MemoryProvider", "broker/components/context/providers.py (DEFAULT_RETRIEVAL_TOP_K)",
                         const("broker.components.context.providers", "DEFAULT_RETRIEVAL_TOP_K"), RB_PROVIDER),
            )))
    add(Row(f"{refl}.interval", "count",
            "Reflect every this many years.", "integer >= 1", "", (
                _refl_acc("interval"),
                Consumer("ReflectionEngine", _ENGINE_SRC, sig(_REFL, "ReflectionEngine", "reflection_interval"),
                         RB_REFL_ENGINE),
                _run_refl("interval"),
            ), refl_also))
    add(Row(f"{refl}.batch_size", "count",
            "How many agents reflect in one model call. broker.run asks one agent per call and "
            "refuses any other value.", "integer >= 1", "", (
                _refl_acc("batch_size"), _trig("batch_size", RB_TRIGGER),
            ), refl_also))
    add(Row(f"{refl}.triggers.periodic_interval", "count",
            "Reflect on a schedule every this many years.", "integer >= 1", "",
            (_trig("periodic_interval"),), refl_also))
    add(Row("<agent_type>.multi_skill.max_skills", "count",
            "How many skills one decision may name when the agent block turns multi_skill on. "
            "A larger value is capped at 2. Read from the agent's own block. Leave multi_skill off "
            "when the action number is on [0, 1] (see the note after the tables).",
            "integer 1 to 2", "", (
                Consumer("get_multi_skill_config",
                         "broker/utils/agent_config.py (AgentTypeConfig.get_multi_skill_config)",
                         multi_skill_max_skills(), RB_PARSE),
            )))
    add(Row(f"{gov}.max_retries", "count",
            "How many times a rejected decision is sent back to the model.", "integer >= 0", "", (
                Consumer("get_governance_retries", "broker/utils/agent_config.py (AgentTypeConfig.get_governance_retries)",
                         sig("broker.utils.agent_config", "AgentTypeConfig.get_governance_retries", "default"),
                         RB_GOVERNANCE),
                Consumer("SkillBrokerEngine", "broker/core/skill_broker_engine.py (SkillBrokerEngine.__init__)",
                         sig("broker.core.skill_broker_engine", "SkillBrokerEngine", "max_retries"), RB_GOVERNANCE),
            ), "`shared.governance.max_retries` (legacy)"))
    add(Row(f"{gov}.max_reports_per_retry", "count",
            "How many rule reports are shown to the model on a retry.", "integer >= 1", "", (
                Consumer("get_governance_max_reports",
                         "broker/utils/agent_config.py (AgentTypeConfig.get_governance_max_reports)",
                         sig("broker.utils.agent_config", "AgentTypeConfig.get_governance_max_reports", "default"),
                         RB_GOVERNANCE),
            ), "`shared.governance.max_reports_per_retry` (legacy)"))
    add(Row(f"{gov}.retrieval.top_n", "count",
            "How many candidate skills are shown to the model.", "integer >= 1", "", (
                _gov_acc("get_retrieval_config", RB_GOVERNANCE, "top_n"),
                Consumer("SkillRetriever", "broker/components/governance/retriever.py (SkillRetriever.__init__)",
                         sig("broker.components.governance.retriever", "SkillRetriever", "top_n"),
                         "direct SkillRetriever(...) calls; SkillBrokerEngine always passes the accessor value"),
            ), "`shared.governance.retrieval` (legacy)"))
    add(Row(f"{gov}.drift.history_window", "count",
            "How many recent decisions per agent the drift monitor keeps.", "integer >= 1", "", (
                _gov_acc(drift_acc, RB_ACCESSOR_ONLY, "history_window"),
                Consumer("DriftDetector", "broker/components/analytics/drift.py (DriftDetector.__init__)",
                         sig("broker.components.analytics.drift", "DriftDetector", "history_window"),
                         RB_ACCESSOR_ONLY),
            ), "`shared.governance.drift` (legacy)"))
    llm = f"{_G}.llm"
    for name, text, rng in (
        ("num_ctx", "Context window size, in tokens.", "integer >= 1"),
        ("num_predict", "Most tokens the model may generate; -1 means no limit.", "integer >= 1, or -1 for no limit"),
        ("max_retries", "Times a failed model call is tried again.", "integer >= 0"),
        ("thinking_budget_tokens", "Optional cap on thinking tokens.", "integer >= 1"),
    ):
        add(Row(f"{llm}.{name}", "count", text, rng, "", _llm_pair(name)))
    for name, text in (
        ("backoff_max_retries", "Times a failed model call is tried again, with growing waits (at most 8)."),
        ("abort_window", "Number of recent decisions the abort rate is measured over."),
    ):
        add(Row(f"{_G}.llm_safeguard.{name}", "count", text, "integer >= 1", "", (_safeguard(name),)))
    for name, text in (
        ("years", "Number of simulated years."),
        ("agent_count", "Number of agents the default agents factory creates for a single-type case (mutually exclusive with run.population)."),
        ("workers", "Number of workers."),
    ):
        add(Row(f"{_G}.run.{name}", "count", text, "integer >= 1", "", (_run(name),)))
    add(Row(f"{_G}.run.seed", "count", "Simulation seed.", "integer", "", (_run("seed"),)))
    add(Row(f"{_G}.social_feeds.top_k", "count",
            "Most posts shown to an agent per decision.", "integer >= 1", "", (
                Consumer("SocialMediaProvider", "broker/components/context/providers.py (SocialMediaProvider.__init__)",
                         sig("broker.components.context.providers", "SocialMediaProvider", "top_k"), RB_SOCIAL),
                Consumer("TieredContextBuilder", "broker/components/context/tiered.py (TieredContextBuilder.__init__)",
                         sig("broker.components.context.tiered", "TieredContextBuilder", "social_feeds_top_k"),
                         RB_SOCIAL),
            )))

    # -- values with units ---------------------------------------------------
    for name, text in (
        ("timeout", "Wait for one model call, for a standard model."),
        ("timeout_large_model", "Wait for one model call, for a model whose name matches large_model_patterns."),
    ):
        add(Row(f"{llm}.{name}", "with-unit", text, "seconds > 0", "seconds", _llm_pair(name)))
    add(Row(f"{_G}.llm_safeguard.backoff_initial_seconds", "with-unit",
            "First wait before a failed model call is tried again; later waits grow.",
            "seconds > 0", "seconds", (_safeguard("backoff_initial_seconds"),)))
    add(Row(f"{_G}.llm_safeguard.backoff_max_seconds", "with-unit",
            "Longest single wait before a retry.", "seconds > 0", "seconds", (_safeguard("backoff_max_seconds"),)))
    add(Row("<agent_type>.parsing.proximity_window", "with-unit",
            "How far after a keyword the parser looks for its value. Read from the agent's own "
            "parsing block.", "characters >= 1", "characters", (
                Consumer("unified adapter", "broker/utils/parsing/unified_adapter.py (DEFAULT_PROXIMITY_WINDOW)",
                         const("broker.utils.parsing.unified_adapter", "DEFAULT_PROXIMITY_WINDOW"), RB_PARSE),
            )))
    add(Row(f"{_G}.social_feeds.half_life_years", "with-unit",
            "Years after which a post counts for half as much.", "years > 0", "years", (
                Consumer("SocialMediaProvider", "broker/components/context/providers.py (SocialMediaProvider.__init__)",
                         sig("broker.components.context.providers", "SocialMediaProvider", "half_life_years"),
                         RB_SOCIAL),
                Consumer("TieredContextBuilder", "broker/components/context/tiered.py (TieredContextBuilder.__init__)",
                         sig("broker.components.context.tiered", "TieredContextBuilder", "social_feeds_half_life_years"),
                         RB_SOCIAL),
            )))

    # -- exceptions ------------------------------------------------------------
    add(Row(f"{mem}.arousal_threshold", "exception",
            "How surprising a stimulus must be to switch the universal engine to its slow, "
            "deliberate mode. Compared with an unbounded surprise score, so it is not a fraction; "
            "99.0 keeps every year in the fast mode.", "any number >= 0", "surprise score", (
                _uni("arousal_threshold"), _hc("arousal_threshold"),
            ), mem_also))
    add(Row(f"{gov}.retrieval.min_score", "exception",
            "Lowest keyword score a skill needs to be shown. The score adds keyword weights and a "
            "2.0 bonus for an exact match, so it is unbounded.", "finite number >= 0", "keyword score", (
                _gov_acc("get_retrieval_config", RB_GOVERNANCE, "min_score"),
                Consumer("SkillRetriever", "broker/components/governance/retriever.py (SkillRetriever.__init__)",
                         sig("broker.components.governance.retriever", "SkillRetriever", "min_score"),
                         "direct SkillRetriever(...) calls"),
            ), "`shared.governance.retrieval` (legacy)"))
    for name, text in (
        ("temperature", "Sampling temperature, on the provider's own scale."),
        ("top_p", "Nucleus sampling cut-off, on the provider's own scale."),
        ("top_k", "Number of top tokens sampled from, on the provider's own scale."),
    ):
        add(Row(f"{llm}.{name}", "exception", text + " Absent means the provider's default.",
                "the provider's scale", "", _llm_pair(name)))
    return tuple(rows)


@functools.lru_cache(maxsize=1)
def rows() -> Tuple[Row, ...]:
    return _build_rows()


# ---------------------------------------------------------------------------
# What the code accepts
# ---------------------------------------------------------------------------

# A name in FRACTION_PARAMETERS belongs to one section. Adding a name there
# without adding it here fails ``_fraction_homes`` (and so the tests).
_FRACTION_HOME = {
    "decay_rate": "memory", "consolidation_prob": "memory", "consolidation_probability": "memory",
    "consolidation_threshold": "memory", "forgetting_threshold": "memory",
    "W_recency": "memory", "W_importance": "memory", "W_context": "memory",
    "W_relevance": "memory", "W_interference": "memory", "interference_cap": "memory",
    "ema_alpha": "memory",
    "importance_boost": "reflection", "base_importance": "reflection",
    "institutional_threshold": "reflection.triggers",
}

# Spellings of the same key. The first is what the code accepts, the second the row.
_ALIASES = {"memory": {"consolidation_prob": "consolidation_probability"}}

# Keys of ReflectionTriggerConfig read under ``reflection.triggers``; the rest
# (method, batch_size, importance_boost) are read from the reflection block itself.
_TRIGGER_LEVEL = ("crisis", "periodic_interval", "decision_types", "institutional_threshold")

# Keys read only from an agent's own block, never from global_config.
_AGENT_ONLY = {"memory": ("retrieval_top_k",)}

# Keys that are not numbers. Each is checked against a consumer by the tests.
# "file (Symbol)" is where the code reads it.
_NONNUMERIC: Dict[str, Dict[str, str]] = {
    "memory": {
        "composed_retrieval": "broker/components/context/providers.py (MemoryProvider.provide)",
        "engine": "broker/config/agent_types/base.py (MemoryConfigSpec.from_dict)",
        "engine_type": "broker/config/agent_types/base.py (MemoryConfigSpec.from_dict)",
        "surprise_strategy": "broker/config/agent_types/base.py (MemoryConfigSpec.from_dict)",
        "rejection_line_style": "broker/config/decision_wording.py (memory_line_style)",
        "runner_decision_line": "broker/core/experiment_runner.py (ExperimentRunner)",
        "retrieval_weights": "examples/single_agent/run_flood.py (memory engine setup)",
        "source_patterns": "broker/components/memory/engines/humancentric.py (HumanCentricMemoryEngine)",
        "event_memory_5_2_1": "examples/single_agent/run_flood.py (_flood_memory_5_2_1_enabled)",
        "scorer": "examples/multi_agent/flood/run_unified_experiment.py (build_memory_engine)",
        "reserve_types": "examples/irrigation_abm/run_experiment.py (memory engine setup)",
    },
    "reflection": {
        "enabled": "examples/single_agent/run_flood.py (_reflection_enabled)",
        "questions": "broker/utils/agent_config.py (get_reflection_questions)",
        "persona_instruction": "examples/single_agent/run_flood.py (_grounded_reflection)",
        "method": "broker/components/cognitive/reflection.py (load_trigger_config)",
        "triggers": "broker/components/cognitive/reflection.py (load_trigger_config)",
        "crisis": "broker/components/cognitive/reflection.py (load_trigger_config)",
        "decision_types": "broker/components/cognitive/reflection.py (load_trigger_config)",
        "keep_latest_only": "broker/utils/agent_config.py (get_reflection_keep_latest_only)",
        "year_outcome": "broker/components/cognitive/reflection.py (GROUNDING_KEYS)",
        "year_lines": "broker/components/cognitive/reflection.py (GROUNDING_KEYS)",
        "program_facts": "broker/components/cognitive/reflection.py (GROUNDING_KEYS)",
        "lesson_no_numbers": "broker/components/cognitive/reflection.py (GROUNDING_KEYS)",
    },
    "reflection.triggers": {
        "crisis": "broker/components/cognitive/reflection.py (load_trigger_config)",
        "decision_types": "broker/components/cognitive/reflection.py (load_trigger_config)",
    },
    "llm_safeguard": {
        "enabled": "broker/utils/llm_safeguard.py (validate_llm_safeguard_dict)",
    },
}

_SECTIONS = (
    "memory", "reflection", "reflection.triggers", "governance.retrieval", "governance.drift",
    "governance.population", "governance.memory.resolution_importance_policy", "llm_safeguard",
)

_NUMERIC_ANNOTATIONS = frozenset({"int", "float", "Optional[int]", "Optional[float]", "int | None", "float | None"})


def _numeric(default: Any, annotation: Any = None) -> bool:
    if isinstance(default, bool):
        return False
    if isinstance(default, (int, float)):
        return True
    if default is None and annotation is not None:
        text = annotation if isinstance(annotation, str) else repr(annotation)
        text = text.replace("typing.", "").replace("<class '", "").replace("'>", "")
        return text in _NUMERIC_ANNOTATIONS
    return False


def _params(target: Any) -> Dict[str, inspect.Parameter]:
    return {name: p for name, p in inspect.signature(target).parameters.items()
            if p.kind not in (p.VAR_KEYWORD, p.VAR_POSITIONAL)}


def _alias(section: str, key: str) -> str:
    return _ALIASES.get(section, {}).get(key, key)


def _fraction_homes() -> Dict[str, List[str]]:
    from broker.components.memory.factory import FRACTION_PARAMETERS

    unplaced = sorted(set(FRACTION_PARAMETERS) - set(_FRACTION_HOME))
    stale = sorted(set(_FRACTION_HOME) - set(FRACTION_PARAMETERS))
    if unplaced or stale:
        raise RuntimeError(
            "FRACTION_PARAMETERS and parameter_table._FRACTION_HOME differ: "
            f"no section for {unplaced}, no longer a fraction: {stale}. Give each name a section."
        )
    homes: Dict[str, List[str]] = {}
    for name, section in _FRACTION_HOME.items():
        homes.setdefault(section, []).append(name)
    return homes


def _module_dict_keys(module: str, name: str) -> List[str]:
    """Keys of a module-level dict literal, read without importing the module.

    ``AgentTypeConfig.load`` calls the key check while ``llm_utils`` may still
    be importing (it loads the config at import time), and
    ``llm_safeguard`` imports ``llm_utils``. Reading the literal avoids that cycle.
    """
    loaded = sys.modules.get(module)
    table = getattr(loaded, name, None) if loaded is not None else None
    if isinstance(table, dict):
        return list(table)
    spec = importlib.util.find_spec(module)
    tree = ast.parse(Path(spec.origin).read_text(encoding="utf-8"))
    for node in tree.body:
        target = node.target if isinstance(node, ast.AnnAssign) else (node.targets[0] if isinstance(node, ast.Assign) else None)
        if isinstance(target, ast.Name) and target.id == name:
            return [ast.literal_eval(key) for key in node.value.keys]
    raise RuntimeError(f"{module}.{name} is not a dict literal")


@functools.lru_cache(maxsize=1)
def _harvest() -> Tuple[Dict[str, Dict[str, List[str]]], Dict[str, Dict[str, List[str]]]]:
    """Return (numeric, other) keys per section, each key with the sources that accept it."""
    from broker.components.memory import registry
    from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
    from broker.components.memory.universal import UniversalCognitiveEngine
    from broker.components.cognitive.reflection import GROUNDING_KEYS, ReflectionTriggerConfig

    numeric: Dict[str, Dict[str, List[str]]] = {s: {} for s in _SECTIONS}
    other: Dict[str, Dict[str, List[str]]] = {s: {} for s in _SECTIONS}

    def note(table, section, key, source):
        table[section].setdefault(_alias(section, key), []).append(source)

    # memory: the two engines, as the registry factories pass YAML through.
    hc = _params(HumanCentricMemoryEngine)
    factory = _params(registry.MemoryEngineRegistry._engines["humancentric"])
    for name, p in factory.items():
        note(numeric if _numeric(p.default, p.annotation) else other, "memory", name,
             "registry humancentric factory")
    for name in registry.HUMANCENTRIC_PASSTHROUGH_KEYS:
        p = hc[name]
        note(numeric if _numeric(p.default, p.annotation) else other, "memory", name,
             "HumanCentricMemoryEngine (registry passthrough)")
    for name, p in _params(UniversalCognitiveEngine).items():
        if name == "persistence":  # an object, never a YAML value
            continue
        note(numeric if _numeric(p.default, p.annotation) else other, "memory", name,
             "UniversalCognitiveEngine")
    for key, value in accessor("get_global_memory_config")().items():
        note(numeric if _numeric(value) else other, "memory", key, "get_global_memory_config")
    note(numeric, "memory", "retrieval_top_k", "MemoryProvider (DEFAULT_RETRIEVAL_TOP_K)")

    # reflection and its triggers.
    for key, value in accessor("get_reflection_config")().items():
        note(numeric if _numeric(value) else other, "reflection", key, "get_reflection_config")
    for item in dataclasses.fields(ReflectionTriggerConfig):
        is_num = _numeric(item.default if item.default is not dataclasses.MISSING else None, item.type)
        note(numeric if is_num else other, "reflection", item.name, "ReflectionTriggerConfig")
        if item.name in _TRIGGER_LEVEL:
            note(numeric if is_num else other, "reflection.triggers", item.name, "ReflectionTriggerConfig")
    for key in GROUNDING_KEYS:
        note(other, "reflection", key, "GROUNDING_KEYS")

    # governance sub-blocks, from the accessor default dicts.
    for method, section in (
        ("get_retrieval_config", "governance.retrieval"),
        ("get_drift_config", "governance.drift"),
        ("get_population_governance_config", "governance.population"),
        ("get_bridge_importance_config", "governance.memory.resolution_importance_policy"),
    ):
        for key, value in accessor(method)().items():
            note(numeric if _numeric(value) else other, section, key, method)

    # llm_safeguard: the defaults dict.
    defaults = None
    mod = sys.modules.get("broker.utils.llm_safeguard")
    if mod is not None and isinstance(getattr(mod, "_DEFAULTS", None), dict):
        defaults = mod._DEFAULTS
    for key in _module_dict_keys("broker.utils.llm_safeguard", "_DEFAULTS"):
        value = defaults.get(key) if defaults is not None else (0 if key != "enabled" else False)
        note(numeric if _numeric(value) else other, "llm_safeguard", key, "llm_safeguard._DEFAULTS")

    # FRACTION_PARAMETERS, each in its section.
    for section, names in _fraction_homes().items():
        for name in names:
            note(numeric, section, name, "FRACTION_PARAMETERS")

    # Keys that are not numbers, each tied to a consumer (the tests read the consumer).
    for section, keys in _NONNUMERIC.items():
        for key, consumer in keys.items():
            note(other, section, key, consumer)
    # A numeric key never doubles as a non-numeric one.
    for section in _SECTIONS:
        for key in list(other[section]):
            if key in numeric[section]:
                del other[section][key]
    return numeric, other


def accepted_section_keys() -> Dict[str, FrozenSet[str]]:
    """Every key (numeric or not) the code accepts inside each covered section.

    Used by ``AgentTypeConfig.load(strict_keys=True)``. Aliases are included.
    """
    numeric, other = _harvest()
    out: Dict[str, FrozenSet[str]] = {}
    for section in _SECTIONS:
        keys = set(numeric[section]) | set(other[section])
        keys |= set(_ALIASES.get(section, {}))
        out[section] = frozenset(keys)
    # Trigger fields can also sit directly in the reflection block (load_trigger_config).
    out["reflection"] = out["reflection"] | out["reflection.triggers"]
    return out


def accepted_keys() -> Dict[str, List[str]]:
    """Numeric keys the code accepts, as YAML path -> sources that accept them.

    ``missing_rows()`` compares this with the table's rows.
    """
    from broker.components.memory.factory import RETRIEVAL_WEIGHT_KEYS

    numeric, _ = _harvest()
    out: Dict[str, List[str]] = {}

    def put(path: str, sources: List[str]) -> None:
        merged = out.setdefault(path, [])
        for item in sources:
            if item not in merged:
                merged.append(item)

    prefixes = {
        "memory": f"{_G}.memory", "reflection": f"{_G}.reflection",
        "reflection.triggers": f"{_G}.reflection.triggers",
        "governance.retrieval": f"{_G}.governance.retrieval", "governance.drift": f"{_G}.governance.drift",
        "governance.population": f"{_G}.governance.population",
        "governance.memory.resolution_importance_policy":
            f"{_G}.governance.memory.resolution_importance_policy",
        "llm_safeguard": f"{_G}.llm_safeguard",
    }
    for section, keys in numeric.items():
        for key, sources in keys.items():
            if section == "reflection" and key in _TRIGGER_LEVEL:
                put(f"{prefixes['reflection.triggers']}.{key}", sources)  # also readable at reflection level
            elif section == "reflection" and key not in ("interval", "batch_size", "importance_boost", "base_importance"):
                continue
            elif key in _AGENT_ONLY.get(section, ()):
                put(f"<agent_type>.{section}.{key}", sources)
            else:
                put(f"{prefixes[section]}.{key}", sources)
    for key in RETRIEVAL_WEIGHT_KEYS:
        put(f"{_G}.memory.retrieval_weights.{key}", ["RETRIEVAL_WEIGHT_KEYS"])

    # governance (top level): the retries accessors.
    for method, key in (("get_governance_retries", "max_retries"), ("get_governance_max_reports", "max_reports_per_retry")):
        parameter = inspect.signature(getattr(_load("broker.utils.agent_config").AgentTypeConfig, method)).parameters["default"]
        if _numeric(parameter.default):
            put(f"{_G}.governance.{key}", [method])

    # llm: the numeric fields of LLMConfig.
    llm_utils = _load("broker.utils.llm_utils")
    for item in dataclasses.fields(llm_utils.LLMConfig):
        default = item.default if item.default is not dataclasses.MISSING else None
        if _numeric(default, item.type):
            put(f"{_G}.llm.{item.name}", ["LLMConfig"])

    # run: the numeric entries of _entry._DEFAULTS.
    for key, value in _load("broker.run._entry")._DEFAULTS.items():
        if _numeric(value):
            put(f"{_G}.run.{key}", ["broker/run/_entry.py _DEFAULTS"])

    # literals lifted into constants, and provider parameters.
    put("<agent_type>.parsing.proximity_window", ["DEFAULT_PROXIMITY_WINDOW"])
    if isinstance(multi_skill_max_skills()(), int):
        put("<agent_type>.multi_skill.max_skills", ["get_multi_skill_config"])
    providers = _load("broker.components.context.providers")
    for name, p in _params(providers.SocialMediaProvider).items():
        if name in ("top_k", "half_life_years") and _numeric(p.default):
            put(f"{_G}.social_feeds.{name}", ["SocialMediaProvider"])
    return out


def missing_rows() -> List[str]:
    """Accepted numeric keys that have no row in the table."""
    have = {row.path for row in rows()}
    return sorted(path for path in accepted_keys() if path not in have)


def rows_without_default() -> List[Tuple[str, str]]:
    """(path, consumer label) for every consumer whose default function finds no value."""
    out = []
    for row in rows():
        for consumer in row.consumers:
            if consumer.default() is MISSING:
                out.append((row.path, consumer.label))
    return out


def problems() -> List[str]:
    """Everything wrong with the table: missing rows, missing defaults, out-of-range defaults."""
    found = [f"accepted key has no row: {path}" for path in missing_rows()]
    found += [f"no default found: {path} ({label})" for path, label in rows_without_default()]
    for row in rows():
        for consumer in row.consumers:
            value = consumer.default()
            if value is MISSING:
                continue
            if row.group == "fraction" and not (isinstance(value, (int, float)) and not isinstance(value, bool)
                                                and 0 <= value <= 1):
                found.append(f"fraction default outside [0, 1]: {row.path} ({consumer.label}) = {value!r}")
            if row.group == "count" and not (value is None or (isinstance(value, int) and not isinstance(value, bool))):
                found.append(f"count default is not an integer: {row.path} ({consumer.label}) = {value!r}")
    return found


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _fmt(value: Any) -> str:
    if value is MISSING:
        return "MISSING"
    return f"`{value!r}`"


def _cell(text: str) -> str:
    return text.replace("|", "\\|").replace("\n", " ")


def _row_lines(row: Row) -> str:
    defaults = "<br>".join(f"{_fmt(c.default())} {_cell(c.label)}" for c in row.consumers)
    read_by = "<br>".join(_cell(c.read_by) for c in row.consumers)
    rng = row.range + (f" ({row.unit})" if row.unit and row.unit not in row.range else "")
    also = f" Also in: {row.also_in}." if row.also_in else ""
    return (f"| `{row.path}` | {_cell(row.meaning)}{_cell(also)} | {_cell(rng)} | {defaults} | {read_by} |")


_HEADER = "| YAML path | Meaning | Range | Default, by consumer | Read by |\n|---|---|---|---|---|"

_INTRO = """\
# Parameter table

> Generated. Do not edit by hand. Rebuild it with
> `python -m broker.config.parameter_table --write docs/references/parameter_table.md`;
> `--check` exits 1 when this file differs from what the code now produces.
> Source: `broker/config/parameter_table.py`.

This is the one place to read the numbers the broker reads from `agent_types.yaml`,
their ranges, and the default each piece of code applies. Every default below is read
from that code when this file is built, not copied. Some keys have more than one default
because two pieces of code apply different ones; each is listed with the code that uses it
and which runners reach that code.

**Reading the "Read by" column.** `broker.run` is the generic entry point. It reads only the
keys marked as reaching it. It builds a `WindowMemoryEngine`, which ignores `window_size`
when it retrieves and returns the last `retrieval_top_k` items, so on `broker.run` the memory
shown to the model is set by `retrieval_top_k`. Paper runners (single_agent, governed_flood,
irrigation_abm, multi_agent/flood) build their own memory engines and read more keys.

**Where a key can sit.** Keys under `memory` and `reflection` can sit in `global_config`, in the
legacy `shared` block, and in an agent block. The `governance` keys sit in `global_config`, or
in the legacy `shared.governance`. `llm_safeguard` sits in `global_config` only. The path in the
first column is the `global_config` form.
"""


_ACTION_NUMBER = """## The agent's action number

The number an agent attaches to its action (how much to release, how much to cut) is not a broker
key. A new case declares it as a numeric response field named `magnitude`, with `min: 0` and
`max: 1`, so 0.5 means half. The parser clamps the model's answer to that range and records a
warning, so the prompt must say "fraction". `validate_prompt` warns when such a field allows more
than 1, and `python -m broker.run --strict-keys` refuses it. Do not turn on `multi_skill` for a
case with a [0, 1] action number: its second action reads whole numbers only. How to declare the
field, and the scaffold flag that writes it: `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`, section
"The action number".
"""


def render_markdown() -> str:
    """The whole parameter table document, deterministic (sorted, no timestamps)."""
    parts = [_INTRO]
    titles = {
        "fraction": ("1. Fractions on [0, 1]",
                     "Every continuous framework parameter is on [0, 1]. Values outside it are refused when "
                     "the YAML is loaded."),
        "count": ("2. Counts", "Whole numbers, with no unit."),
        "with-unit": ("3. Values with units", "Numbers in seconds, years or characters."),
        "exception": ("4. Exceptions",
                      "Numbers that are not fractions, each for a stated reason."),
    }
    for group in GROUPS:
        title, lead = titles[group]
        group_rows = sorted((r for r in rows() if r.group == group), key=lambda r: r.path)
        parts.append(f"## {title}\n\n{lead}\n\n{_HEADER}\n" + "\n".join(_row_lines(r) for r in group_rows) + "\n")
    parts.append(_ACTION_NUMBER)
    parts.append(_where_defaults_come_from())
    return "\n".join(parts).rstrip("\n") + "\n"


def _where_defaults_come_from() -> str:
    _, other = _harvest()
    lines = [
        "## 5. Where defaults come from",
        "",
        "There is no single registry in the code. Each default is applied by one of these, and "
        "this document reads them all:",
        "",
        "- Memory engines: `HumanCentricMemoryEngine.__init__` "
        "(`broker/components/memory/engines/humancentric.py`), `UniversalCognitiveEngine.__init__` "
        "(`broker/components/memory/universal.py`) and the registry factories "
        "(`broker/components/memory/registry.py`, `_register_builtins`).",
        "- `AgentTypeConfig` accessors called on an empty config: `get_global_memory_config`, "
        "`get_reflection_config`, `get_retrieval_config`, `get_drift_config`, "
        "`get_population_governance_config`, `get_bridge_importance_config`, `get_governance_retries`, "
        "`get_governance_max_reports`.",
        "- Model settings: `LLMConfig` and `_load_global_config` in `broker/utils/llm_utils.py`; "
        "`_DEFAULTS` in `broker/utils/llm_safeguard.py`.",
        "- `broker.run`: `_DEFAULTS` and `DEFAULT_WINDOW_SIZE` in `broker/run/_entry.py`.",
        "- Reflection: `ReflectionTriggerConfig` and `ReflectionEngine` in "
        "`broker/components/cognitive/reflection.py`.",
        "- Named constants: `DEFAULT_RETRIEVAL_TOP_K` (`broker/components/context/providers.py`) and "
        "`DEFAULT_PROXIMITY_WINDOW` (`broker/utils/parsing/unified_adapter.py`).",
        "- Two typed loaders, `MemoryConfigSpec` (`broker/config/agent_types/base.py`) and "
        "`MemoryConfig` (`broker/config/schema.py`), carry their own defaults (for example "
        "`window_size` 5 and `arousal_threshold` 0.5). No runner builds an engine from them.",
        "",
        "Paper runners also pass their own literals when they read a key (for example "
        "`window_size` from a command-line flag, or `arousal_threshold` 0.5 or 1.0). Those literals "
        "live in the runners, which this table does not read.",
        "",
        "**Accessors with no runner.** `get_drift_config` has no caller outside tests: the drift "
        "settings are read by no runner. `get_population_governance_config` and "
        "`get_bridge_importance_config` are read only by the multi_agent/flood runner, which uses "
        "the `echo`, `entropy` and `deadlock` thresholds and the resolution importances; no runner "
        "uses `quorum_threshold`.",
        "",
        "**Never read.** `global_config.cognitive_config` is read by no code. Strict key checking "
        "reports it.",
        "",
        "**Case inputs that are not broker keys.** The three FQL values used by the irrigation case "
        "(sigma 1.22, regret 2.22 and 1.54) are inputs of that case, not broker keys, and have no row.",
        "",
        "**Physical setpoints.** Setpoints of a case, such as reservoir levels or release limits, are "
        "the case's own model values. They are declared in its coupling contract (`VarSpec` lower and "
        "upper limits, with units) or in its `parameters:` block. They get no broker row.",
        "",
        "### Keys that are not numbers",
        "",
        "Strict key checking also accepts these, each read by the code shown:",
        "",
    ]
    for section in _SECTIONS:
        keys = sorted(other[section].items())
        if not keys:
            continue
        lines.append(f"- `{section}`: " + "; ".join(f"`{key}` ({sources[0]})" for key, sources in keys))
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m broker.config.parameter_table",
                                     description="Write or check the generated parameter table.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--write", metavar="PATH", help="write the table to PATH")
    group.add_argument("--check", metavar="PATH", help="exit 1 when PATH differs from the table")
    args = parser.parse_args(argv)
    text = render_markdown()
    if args.write:
        Path(args.write).write_text(text, encoding="utf-8", newline="\n")
        return 0
    try:
        current = Path(args.check).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"parameter_table: could not read {args.check}: {exc}", file=sys.stderr)
        return 1
    if current.replace("\r\n", "\n") != text:
        print(f"parameter_table: {args.check} is out of date; rebuild it with --write", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
