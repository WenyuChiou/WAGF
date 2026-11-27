"""Parse case settings, assemble a runner, and record entry-point provenance."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import re
import string
import sys
from typing import Any

import yaml

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.components.context.builder import TieredContextBuilder
from broker.components.context.providers import DEFAULT_RETRIEVAL_TOP_K
from broker.core.experiment_builder import ExperimentBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.agent_config import AgentTypeConfig, UnknownConfigKeysError
from broker.utils.llm_utils import LLM_CONFIG, is_mock_model

from ._imports import SlotError, parse_slot, resolve_slot, valid_module_name, vet_import_target
from ._memory import (
    DEFAULT_WINDOW_SIZE,  # re-exported: the parameter table reads it here
    MemorySettings,
    REFLECTION_PREFIX,
    ReflectionHook,
    ReflectionSettings,
    build_memory_engine,
    memory_settings,
    reflection_settings,
    rejection_line_styles,
)
from broker.components.memory.origin_gate import install_origin_gate
from ._provenance import capture_launch_environment, launch_checks, manifest_problem


@dataclass
class Coupled:
    """A coupling contract and its sources, optionally tied to a domain."""

    contract: Any
    sources: Any
    domain: str | None = None


@dataclass
class RunContext:
    """Effective run settings and case objects available to slot factories."""

    config_path: Path
    case_dir: Path
    config: AgentTypeConfig
    raw: dict
    model: str
    years: int
    agent_count: int
    seed: int
    output_dir: Path
    skill_registry_path: Path
    profile: str
    workers: int
    memory: MemorySettings = None
    reflection: ReflectionSettings = None
    world: Any = None
    agents: dict[str, BaseAgent] | None = None
    social: Any = None
    coordinator: Any = None
    population: dict[str, int] | None = None


class StepWorld:
    """Minimal yearly world for cases without a simulation factory."""

    def __init__(self):
        self.current_year = 0

    def advance_step(self):
        self.current_year += 1
        return {"current_year": self.current_year}

    def execute_skill(self, approved_skill):
        return ExecutionResult(success=True, state_changes={})


class RunError(ValueError):
    """Invalid CLI or case settings detected before execution."""


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise RunError(message)


_SLOT_NAMES = ("world", "agents", "hooks", "validators", "mock", "social", "coordinator")
_DEFAULTS = {
    "model": "mock",
    "years": 1,
    "agent_count": 1,
    "seed": 42,
    "governance": "default",
    "workers": 1,
    "strict_keys": False,
}
_RUN_TYPES = {
    **{name: str for name in _SLOT_NAMES},
    **{name: type(default) for name, default in _DEFAULTS.items()},
    "output": str,
    "skill_registry": str,
    "phase_order": list,
    "population": dict,
}
_POSITIVE_SETTINGS = {"years", "agent_count", "workers"}


def _parse_args(argv):
    parser = _Parser(prog="python -m broker.run", description="Run a broker case from agent-types YAML.")
    parser.add_argument("config", metavar="CONFIG", help="agent-types YAML")
    parser.add_argument("--model", help="model name (default: mock)")
    parser.add_argument("--years", type=int, help="number of simulation years")
    parser.add_argument("--agents", type=int, dest="agent_count", help="requested agent count")
    parser.add_argument("--seed", type=int, help="simulation seed")
    parser.add_argument("--output", metavar="DIR", help="exact output directory, relative to the current directory")
    parser.add_argument("--governance", metavar="PROFILE", help="governance profile")
    parser.add_argument("--skill-registry", metavar="PATH", help="registry YAML, relative to the current directory")
    parser.add_argument("--workers", type=int, help="number of workers")
    parser.add_argument("--thinking-mode", choices=("auto", "disabled", "enabled"))
    parser.add_argument("--strict-keys", action=argparse.BooleanOptionalAction, default=None,
                        help="refuse a YAML that holds a key no code reads (default: off; "
                             "run.strict_keys in the YAML sets it, the command line wins)")
    parser.add_argument("--strict-provenance", action="store_true",
                        help="refuse a run with uncommitted changes, a missing Ollama model digest, a failed "
                             "metadata query or a failed manifest write (mock and cloud models have no digest; "
                             "that check does not apply to them)")
    parser.add_argument("--slot", action="append", default=[], metavar="NAME=MODULE:ATTR",
                        help=f"override a factory ({', '.join(_SLOT_NAMES)})")
    parser.add_argument("--allow-module", action="append", default=[], metavar="DOTTED.NAME",
                        help="allow this exact external module in a YAML slot")
    return parser.parse_args(argv)


def _read_yaml(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, yaml.YAMLError) as exc:
        raise RunError(f"could not read {path}: {exc}") from exc


def _run_block(raw):
    global_config = raw.get("global_config", {})
    if not isinstance(global_config, dict):
        raise RunError("global_config must be a mapping")
    run = global_config.get("run", {})
    if not isinstance(run, dict):
        raise RunError("global_config.run must be a mapping")
    for key, value in run.items():
        expected = _RUN_TYPES.get(key)
        if expected is None:
            raise RunError(f"unknown global_config.run key {key!r}")
        if type(value) is not expected:
            raise RunError(f"run.{key} must be of type {expected.__name__}")
        if key in _SLOT_NAMES:
            parse_slot(key, value)
    if "phase_order" in run and not all(
        isinstance(phase, list) and all(isinstance(name, str) for name in phase)
        for phase in run["phase_order"]
    ):
        raise RunError("run.phase_order must be a list of lists of agent-type strings")
    if "population" in run:
        if "agent_count" in run:
            raise RunError("set run.population or run.agent_count, not both")
        population = run["population"]
        if not population:
            raise RunError("run.population must be a non-empty mapping of agent types to counts")
        total = 0
        for agent_type, count in population.items():
            if type(agent_type) is not str or not agent_type.strip() or "\0" in agent_type:
                raise RunError(f"run.population key must be a non-empty string, got {agent_type!r}")
            if type(count) is not int or count < 0:
                raise RunError(
                    f"run.population[{agent_type!r}] must be a non-negative integer, got {count!r}"
                )
            total += count
        if total < 1:
            raise RunError("run.population must instantiate at least 1 agent in total")
    return run


def _plan_slots(run, args):
    slots = {name: (run[name], "yaml") for name in _SLOT_NAMES if name in run}
    for override in args.slot:
        name, separator, spec = override.partition("=")
        if not separator or name not in _SLOT_NAMES:
            raise RunError(f"--slot expects NAME=module:attr for {', '.join(_SLOT_NAMES)}, got {override!r}")
        parse_slot(name, spec)
        slots[name] = (spec, "cli")
    for module in args.allow_module:
        if not valid_module_name(module):
            raise RunError(f"--allow-module expects a dotted module name, got {module!r}")
    return slots


def _setting(args, run, name, default=None):
    cli = getattr(args, name)
    value = cli if cli is not None else run.get(name, default)
    option = "agents" if name == "agent_count" else name.replace("_", "-")
    label = f"--{option}" if cli is not None else f"run.{name}"
    if name in _POSITIVE_SETTINGS and value < 1:
        raise RunError(f"{label} must be at least 1")
    if isinstance(value, str) and (not value.strip() or "\0" in value):
        raise RunError(f"{label} must be a non-empty string without NUL characters")
    return value


def _prepare_run(argv):
    args = _parse_args(argv)
    if not args.config.strip() or "\0" in args.config:
        raise RunError("CONFIG must be a non-empty path without NUL characters")
    config_path = Path(os.path.realpath(args.config))
    config_dir = config_path.parent
    case_dir = config_dir.parent if os.path.normcase(config_dir.name) == "config" else config_dir
    raw = _read_yaml(config_path)
    if not isinstance(raw, dict):
        raise RunError(f"agent-types YAML must be a mapping in {config_path}")
    run = _run_block(raw)
    if "population" in run and args.agent_count is not None:
        raise RunError("--agents cannot be combined with run.population")
    slots = _plan_slots(run, args)
    settings = {name: _setting(args, run, name, default) for name, default in _DEFAULTS.items()}
    output = _setting(args, run, "output", f"results/{config_path.stem}")
    registry = _setting(args, run, "skill_registry", "skill_registry.yaml")
    output_dir = Path(os.path.abspath(output if args.output is not None else case_dir / output))
    registry_path = Path(os.path.abspath(registry if args.skill_registry is not None else config_dir / registry))
    if (output_dir / "reproducibility_manifest.json").exists():
        raise RunError(f"{output_dir} already holds a completed run "
                       f"(reproducibility_manifest.json is present); point --output at a "
                       f"new directory")
    try:
        config = AgentTypeConfig.load(str(config_path), force_reload=True,
                                      strict_keys=settings["strict_keys"])
    except UnknownConfigKeysError as exc:
        raise RunError(
            f"{config_path} holds {len(exc.keys)} key(s) no code reads: " + ", ".join(exc.keys)
            + " (remove them, or leave out --strict-keys / run.strict_keys)"
        ) from exc
    except ImportError as exc:  # The strict key check imports its key lists lazily.
        raise RunError(f"{config_path}: the strict key check could not run ({exc})") from exc
    except ValueError as exc:  # e.g. a memory fraction outside [0, 1]
        raise RunError(f"{config_path}: {exc}") from exc
    population: dict[str, int] | None = None
    effective_agent_count = settings["agent_count"]
    if "population" in run:
        declared_types = config.agent_type_names()
        declared_set = set(declared_types)
        population = dict(run["population"])
        for agent_type in population:
            if agent_type not in declared_set:
                raise RunError(
                    f"run.population names undeclared agent type {agent_type!r}; "
                    f"declared agent types: {declared_types}"
                )
        effective_agent_count = sum(population.values())
        unpopulated = [
            name for name in declared_types
            if name != "default" and population.get(name, 0) == 0
        ]
        if unpopulated:
            print(
                f"broker.run: note: declared agent type(s) {unpopulated} have count 0 "
                f"in run.population and will not be instantiated",
                file=sys.stderr,
            )
    if settings["strict_keys"]:
        from broker.tools.validate_prompt import magnitude_scale_problems

        for where, key, reason in magnitude_scale_problems(raw):
            raise RunError(
                f"{config_path}: response field {key!r} in {where!r} has {reason}; the action "
                f"number of a new case is on [0, 1] (set min: 0 and max: 1), or name the field "
                f"something other than magnitude or magnitude_pct (--strict-keys is on)"
            )
    try:
        memory = memory_settings(raw, settings["seed"])
        reflection = reflection_settings(raw, config, memory)
    except ValueError as exc:
        raise RunError(f"{config_path}: {exc}") from exc
    ctx = RunContext(
        config_path=config_path, case_dir=case_dir, config=config, raw=raw,
        model=settings["model"], years=settings["years"], agent_count=effective_agent_count,
        seed=settings["seed"], output_dir=output_dir, skill_registry_path=registry_path,
        profile=settings["governance"], workers=settings["workers"],
        memory=memory, reflection=reflection, population=population,
    )
    return ctx, slots, run.get("phase_order"), args


def _vet_decider_targets(node, ctx, allowed_modules, where="yaml", _seen=None):
    """Hold every ``decider.params.target`` to the case-folder import rule.

    The parametric decider imports its target by name at build time
    (broker/agents/deciders.py, parametric_decider_factory), so a YAML could
    otherwise name any module through it.
    """
    # YAML aliases can repeat a node or make it contain itself; visit each once.
    _seen = set() if _seen is None else _seen
    if isinstance(node, (Mapping, list)):
        if id(node) in _seen:
            return
        _seen.add(id(node))
    if isinstance(node, Mapping):
        decider = node.get("decider")
        params = decider.get("params") if isinstance(decider, Mapping) else None
        if isinstance(params, Mapping) and "target" in params:
            vet_import_target(f"{where}.decider.params.target", params["target"],
                              ctx.case_dir, allowed_modules=allowed_modules)
        for key, value in node.items():
            _vet_decider_targets(value, ctx, allowed_modules, f"{where}.{key}", _seen)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            _vet_decider_targets(item, ctx, allowed_modules, f"{where}[{index}]", _seen)


def _slot_factory(name, ctx, slots, allowed_modules, loaded):
    if name not in slots or (name == "mock" and not is_mock_model(ctx.model)):
        return None
    spec, source = slots[name]
    factory = resolve_slot(name, spec, ctx.case_dir, from_cli=source == "cli", allowed_modules=allowed_modules)
    module = sys.modules.get(getattr(factory, "__module__", None) or "")
    loaded[name] = getattr(module, "__file__", None)
    return factory


def _default_agents(ctx):
    if ctx.population is not None:
        plan = [(agent_type, count) for agent_type, count in ctx.population.items() if count > 0]
    else:
        types = ctx.config.agent_type_names()
        if len(types) != 1:
            found = ", ".join(map(str, types)) or "none"
            raise RunError(
                f"default agents require exactly one agent type (found: {found}). Set run.agents to a factory"
            )
        plan = [(types[0], ctx.agent_count)]

    registry = _read_yaml(ctx.skill_registry_path)
    if not isinstance(registry, dict):
        raise RunError(f"skill registry YAML must be a mapping in {ctx.skill_registry_path}")
    items = registry.get("skills", [])
    if not isinstance(items, list) or not all(
        isinstance(item, dict) and isinstance(item.get("skill_id"), str)
        and isinstance(item.get("eligible_agent_types", []), list)
        for item in items
    ):
        raise RunError(
            f"skills in {ctx.skill_registry_path} must be a list of mappings, each with a "
            f"string skill_id (and eligible_agent_types, if given, a list)"
        )

    default_skill = registry.get("default_skill")
    known_skill_ids = {item["skill_id"] for item in items}

    agents = {}
    for agent_type, count in plan:
        skills = [
            Skill(
                skill_id=item["skill_id"],
                description=item.get("description", item["skill_id"]),
                affected_param=None,
                direction="none",
            )
            for item in items
            if (
                "eligible_agent_types" not in item
                or "*" in item["eligible_agent_types"]
                or agent_type in item["eligible_agent_types"]
            )
        ]
        if not skills:
            raise RunError(
                f"agent type {agent_type!r} has no eligible skills in {ctx.skill_registry_path}"
            )
        if (
            ctx.population is not None
            and isinstance(default_skill, str)
            and default_skill in known_skill_ids
            and default_skill not in {skill.skill_id for skill in skills}
        ):
            raise RunError(
                f"skill registry default_skill {default_skill!r} is not eligible for populated "
                f"agent type {agent_type!r}"
            )
        for index in range(1, count + 1):
            name = f"{agent_type}_{index}"
            if name in agents:
                raise RunError(f"duplicate generated agent id {name!r}")
            agents[name] = BaseAgent(AgentConfig(
                name=name, agent_type=agent_type, state_params=[], objectives=[], constraints=[],
                skills=skills.copy(),
            ))
    return agents


def _mock_invokes(mock_factory, ctx, agent_types, inactive_types=()):
    if mock_factory is None:
        return {}
    result = mock_factory(ctx)
    if callable(result):
        return dict.fromkeys(agent_types, result)
    if not isinstance(result, Mapping):
        raise SlotError("run.mock must return a callable or a mapping of agent types to callables")
    active_set = set(agent_types)
    allowed_types = active_set | set(inactive_types)
    filtered = {}
    for agent_type, invoke in result.items():
        if agent_type not in allowed_types:
            raise SlotError(f"run.mock returned unknown agent type {agent_type!r}")
        if not callable(invoke):
            raise SlotError(f"run.mock must return a callable for agent type {agent_type!r}")
        if agent_type in active_set:
            filtered[agent_type] = invoke
    return filtered


def _require_coupling_enabled(ctx, world):
    from broker.coupling.flag import resolve_coupling_enabled
    from broker.domains.registry import DomainPackRegistry

    global_config = ctx.raw.get("global_config")
    governance = global_config.get("governance") if isinstance(global_config, Mapping) else None
    domain = world.domain or (governance.get("domain") if isinstance(governance, Mapping) else None)
    pack = DomainPackRegistry.get(domain) if domain else None
    enabled, source = resolve_coupling_enabled(ctx.raw, pack)
    if not enabled:
        if source == "yaml":
            where = "global_config.coupling.enable is false"
        elif pack is None:
            where = "global_config.coupling.enable is not set" + (
                f" and no {domain!r} domain pack is registered" if domain else "")
        else:
            where = f"global_config.coupling.enable is not set and the {domain!r} domain pack defaults to off"
        raise RunError(
            f"run.world returned Coupled(...) but coupling is off ({where}), so the "
            f"coupling contract, relations and feasibility bounds would not run. Set "
            f"global_config.coupling.enable: true, or return a plain world"
        )


def _is_context_provider(obj: Any) -> bool:
    from broker.components.context.providers import ContextProvider

    return isinstance(obj, ContextProvider) or callable(getattr(obj, "provide", None))


def _resolve_social_slot(social_obj: Any, period_getter: Any, memory: Any) -> tuple[Any, list[Any] | None]:
    from broker.components.analytics.interaction import InteractionHub

    if isinstance(social_obj, InteractionHub) or (
        hasattr(social_obj, "environment") and callable(getattr(social_obj, "build_tiered_context", None))
    ):
        return social_obj, None
    if callable(getattr(social_obj, "as_context_provider", None)):
        provider = social_obj.as_context_provider(period_getter, memory_engine=memory)
        if not _is_context_provider(provider):
            raise SlotError("run.social.as_context_provider() must return a ContextProvider")
        return None, [provider]
    if _is_context_provider(social_obj):
        return None, [social_obj]
    if isinstance(social_obj, Sequence) and not isinstance(social_obj, (str, bytes)):
        providers = list(social_obj)
        if all(_is_context_provider(provider) for provider in providers):
            return None, providers
    raise SlotError(
        "run.social must return a ContextProvider, a sequence of ContextProviders, "
        "an object with as_context_provider(), or an InteractionHub"
    )


def _chain_hook(name: str, first: Any, second: Any):
    if name in ("pre_year", "pre_step"):
        def chained(year, env, agents):
            first(year, env, agents)
            second(year, env, agents)
        return chained
    if name in ("post_year", "post_step_end"):
        def chained(year, agents):
            first(year, agents)
            second(year, agents)
        return chained
    if name == "post_step":
        def chained(agent, result):
            first(agent, result)
            second(agent, result)
        return chained

    def chained(*args, **kwargs):
        first(*args, **kwargs)
        second(*args, **kwargs)

    return chained


def _resolve_coordinator_slot(coord_obj: Any, hooks: dict[str, Any]) -> tuple[dict[str, Any], Any]:
    as_hooks = getattr(coord_obj, "as_hooks", None)
    if callable(as_hooks):
        merged = as_hooks(hooks)
        if not isinstance(merged, Mapping) or not all(
            isinstance(k, str) and callable(v) for k, v in merged.items()
        ):
            raise SlotError("run.coordinator.as_hooks() must return a mapping of hook names to callables")
        result = dict(merged)
        return result, result.pop("after_run", None)

    if isinstance(coord_obj, Mapping):
        if not all(isinstance(k, str) and callable(v) for k, v in coord_obj.items()):
            raise SlotError("run.coordinator mapping must map hook names to callables")
        coord_hooks = dict(coord_obj)
        extra_after_run = coord_hooks.pop("after_run", None)
        result = dict(hooks)
        for name, fn in coord_hooks.items():
            existing = result.get(name)
            result[name] = _chain_hook(name, fn, existing) if existing is not None else fn
        return result, extra_after_run

    raise SlotError(
        "run.coordinator must return an object with as_hooks() or a mapping of hook names to callables"
    )


def _build_runner(ctx, slots, phase_order, allowed_modules, loaded):
    world_factory = _slot_factory("world", ctx, slots, allowed_modules, loaded)
    world = world_factory(ctx) if world_factory is not None else StepWorld()
    ctx.world = world.sources if isinstance(world, Coupled) else world

    agents_factory = _slot_factory("agents", ctx, slots, allowed_modules, loaded)
    ctx.agents = agents_factory(ctx) if agents_factory is not None else _default_agents(ctx)
    if not isinstance(ctx.agents, dict) or not ctx.agents or not all(
        isinstance(name, str) and isinstance(agent, BaseAgent) for name, agent in ctx.agents.items()
    ):
        raise SlotError("run.agents must return a non-empty dictionary of names to BaseAgent instances")
    if ctx.population is not None and agents_factory is not None:
        expected_counts = {atype: c for atype, c in ctx.population.items() if c > 0}
        actual_counts: dict[str, int] = {}
        for agent in ctx.agents.values():
            actual_counts[agent.agent_type] = actual_counts.get(agent.agent_type, 0) + 1
        if actual_counts != expected_counts:
            raise RunError(
                f"run.agents returned agent counts {actual_counts} which do not match "
                f"run.population {expected_counts}"
            )

    hooks_factory = _slot_factory("hooks", ctx, slots, allowed_modules, loaded)
    hooks = hooks_factory(ctx) if hooks_factory is not None else {}
    if not isinstance(hooks, Mapping) or not all(isinstance(k, str) and callable(v) for k, v in hooks.items()):
        raise SlotError("run.hooks must return a mapping of hook names to callables")
    hooks = dict(hooks)
    after_run = hooks.pop("after_run", None)

    validators_factory = _slot_factory("validators", ctx, slots, allowed_modules, loaded)
    validators = validators_factory(ctx) if validators_factory is not None else ()
    if not isinstance(validators, Sequence) or isinstance(validators, (str, bytes)) or not all(
        callable(validator) for validator in validators
    ):
        raise SlotError("run.validators must return a sequence of callables")

    agent_types = tuple(dict.fromkeys(agent.agent_type for agent in ctx.agents.values()))
    active_set = set(agent_types)
    inactive_declared_types = (
        (set(ctx.config.agent_type_names()) - active_set - {"default"})
        | {k for k, v in (ctx.population or {}).items() if v == 0}
    ) if ctx.population is not None else set()

    effective_phase_order = phase_order
    if phase_order is not None:
        allowed_phase_types = active_set | inactive_declared_types
        unknown = [name for phase in phase_order for name in phase if name not in allowed_phase_types]
        if unknown:
            raise RunError(
                f"run.phase_order names unknown agent type(s) {unknown}; "
                f"available agent types: {sorted(active_set)}"
            )
        if ctx.population is not None:
            seen_in_phases: set[str] = set()
            duplicates: list[str] = []
            for phase in phase_order:
                for name in phase:
                    if name in seen_in_phases and name not in duplicates:
                        duplicates.append(name)
                    seen_in_phases.add(name)
            if duplicates:
                raise RunError(
                    f"run.phase_order assigns agent type(s) {duplicates} to more than one phase"
                )
            missing_active = [atype for atype in agent_types if atype not in seen_in_phases]
            if missing_active:
                raise RunError(
                    f"run.phase_order omits populated agent type(s) {missing_active}"
                )
            pruned = [
                [name for name in phase if name in active_set]
                for phase in phase_order
            ]
            effective_phase_order = [phase for phase in pruned if phase]
    elif len(agent_types) > 1:
        print(
            f"broker.run: warning: multiple agent types {list(agent_types)} running without "
            f"run.phase_order; all agents will execute in a single phase in population order.",
            file=sys.stderr,
        )

    mock_factory = _slot_factory("mock", ctx, slots, allowed_modules, loaded)
    invokes = _mock_invokes(mock_factory, ctx, agent_types, inactive_types=inactive_declared_types)

    templates = {}
    for agent_type in agent_types:
        ctx.config.get_framework_for_agent_type(agent_type)
        # get_prompt_template() falls back to the inline template, or to "",
        # when the declared file is missing, so the run would quietly use a
        # built-in prompt. Refuse instead. With both forms set, the loaders
        # disagree (get_prompt_template prefers the file, ExperimentBuilder
        # puts the inline one in the context builder), so refuse that too.
        block = ctx.config.get(agent_type)
        template_file = block.get("prompt_template_file")
        if template_file and block.get("prompt_template"):
            raise RunError(
                f"{agent_type}: set prompt_template or prompt_template_file, not both"
            )
        if template_file:
            resolved = ctx.config._resolve_template_path(str(template_file))
            if resolved is None or not resolved.is_file():
                raise RunError(
                    f"{agent_type}.prompt_template_file {str(template_file)!r} was not found at "
                    f"{resolved}. Write the path from the YAML file's folder, for example "
                    f"prompts/{agent_type}.txt"
                )
            try:
                resolved.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as exc:
                raise RunError(
                    f"{agent_type}.prompt_template_file {resolved} could not be read: {exc}"
                ) from exc
        template = ctx.config.get_prompt_template(agent_type)
        if template:
            _warn_undeclared_prompt_placeholders(ctx, agent_type, template)
            templates[agent_type] = template
        elif len(agent_types) > 1:
            print(
                f"broker.run: warning: {agent_type}: no prompt_template or prompt_template_file "
                f"configured; multi-type run will fall back to the built-in template.",
                file=sys.stderr,
            )
    if len(agent_types) == 1 and templates:
        templates["default"] = templates[agent_types[0]]
    memory = build_memory_engine(ctx.memory)
    try:
        styles = rejection_line_styles(ctx.config, dict.fromkeys(a.agent_type for a in ctx.agents.values()))
    except ValueError as exc:
        raise RunError(str(exc)) from exc
    # Invariant 7: every memory write is tagged with its origin and logged to
    # memory_log.jsonl. Writes while the builder seeds agent profiles count as
    # seed writes; any untagged write after that raises.
    built = {}
    period_getter = lambda: getattr(built.get("runner"), "_current_year", 0)
    gate = install_origin_gate(
        memory, ctx.output_dir, period=period_getter,
        reflection_prefix=REFLECTION_PREFIX)

    hub = None
    extend_providers = None
    social_factory = _slot_factory("social", ctx, slots, allowed_modules, loaded)
    if social_factory is not None:
        social_obj = social_factory(ctx)
        hub, extend_providers = _resolve_social_slot(social_obj, period_getter, memory)
        ctx.social = social_obj

    coordinator_factory = _slot_factory("coordinator", ctx, slots, allowed_modules, loaded)
    if coordinator_factory is not None:
        coord_obj = coordinator_factory(ctx)
        hooks, coord_after_run = _resolve_coordinator_slot(coord_obj, hooks)
        if coord_after_run is not None:
            if after_run is not None:
                prev_after_run = after_run
                after_run = lambda out_dir: (coord_after_run(out_dir), prev_after_run(out_dir))
            else:
                after_run = coord_after_run
        ctx.coordinator = coord_obj

    reflection_hook = None
    if ctx.reflection.enabled:
        # Runs after the case's own post_year, once the year's state is settled.
        reflection_hook = ReflectionHook(
            ctx.reflection, ctx.config, memory, ctx.model, ctx.output_dir,
            inner=hooks.get("post_year"),
        )
        hooks["post_year"] = reflection_hook
    config_path = str(ctx.config_path)
    context_builder = TieredContextBuilder(
        agents=ctx.agents, hub=hub, prompt_templates=templates,
        yaml_path=config_path, memory_engine=memory,
        extend_providers=extend_providers,
    )
    builder = (
        ExperimentBuilder()
        .with_model(ctx.model)
        .with_years(ctx.years)
        .with_agents(ctx.agents)
        .with_skill_registry(str(ctx.skill_registry_path))
        .with_memory_engine(memory)
        .with_context_builder(context_builder)
        .with_exact_output(str(ctx.output_dir))
        .with_workers(ctx.workers)
        .with_seed(ctx.seed)
    )
    try:
        builder.with_governance(ctx.profile, config_path)
    except SystemExit as exc:
        raise RunError(str(exc)) from exc
    if isinstance(world, Coupled):
        # ExperimentBuilder only logs at info level and runs the model unwrapped
        # when the flag is off (paper runners rely on that). Here the world slot
        # asked for coupling, so an off flag would silently drop every coupled
        # check: refuse instead.
        _require_coupling_enabled(ctx, world)
        builder.with_coupling(world.contract, world.sources, domain=world.domain)
    else:
        builder.with_simulation(world)
    if hooks:
        try:
            builder.with_lifecycle_hooks(**hooks)
        except ValueError as exc:
            raise SlotError(f"run.hooks: {exc}") from exc
    if validators_factory is not None:
        builder.with_custom_validators(list(validators))
    if effective_phase_order is not None:
        builder.with_phase_order(effective_phase_order)
    if reflection_hook is not None:
        builder.with_reflection_engine(reflection_hook.engine)
    if not ctx.skill_registry_path.is_file():
        raise RunError(f"skill registry file does not exist: {ctx.skill_registry_path}")
    if ctx.output_dir.exists() and not ctx.output_dir.is_dir():
        raise RunError(f"output path is not a directory: {ctx.output_dir}")
    try:
        runner = builder.build()
    except SlotError:
        raise
    except ValueError as exc:  # The builder's own configuration checks.
        raise RunError(f"the case could not be built: {exc}") from exc
    if isinstance(world, Coupled) and ctx.workers > 1:
        raise RunError(
            "coupled runs require --workers 1 "
            "(AR-3: parallel workers are not supported with a coupled model)"
        )
    built["runner"] = runner
    gate.seeding = False
    if ctx.population is not None and inactive_declared_types:
        _dflag = getattr(getattr(runner.broker, "config", None), "get_audit_decider_columns", None)
        if callable(_dflag) and _dflag() is True:
            from broker.core.run_integrity import set_declared_deciders

            set_declared_deciders(ctx.config.declared_decider_names(agent_types=agent_types))
    runner.tag_memory_origin = True
    runner.rejection_line_styles = styles
    for agent in runner.agents.values():
        # A new dict: the agent type's memory block itself stays as loaded.
        mem_cfg = agent.memory_config if isinstance(getattr(agent, "memory_config", None), dict) else {}
        agent.memory_config = {**mem_cfg, "rejection_line_style": styles[agent.agent_type]}
    runner._llm_cache.update(invokes)
    # A case with no rules still gets validator_health.csv.
    audit_writer = getattr(getattr(runner, "broker", None), "audit_writer", None)
    if audit_writer is not None and hasattr(audit_writer, "config"):
        audit_writer.config.always_write_validator_health = True
    if reflection_hook is not None:
        reflection_hook.runner = runner
        runner._reflection_hook = reflection_hook
        runner.reflection_enabled = True  # run_integrity.json records it
    return runner, after_run, reflection_hook


_FALLBACK_PLACEHOLDER_RE = re.compile(
    r"\{([a-zA-Z_][a-zA-Z0-9_]*)(?:\.[a-zA-Z_][a-zA-Z0-9_]*|\[[^\[\]{}]+\])*(?:![sra])?(?::[^{}]*)?\}"
)


def _extract_format_placeholders(template: str) -> set[str]:
    """Return root identifier placeholders parsed the same way ``SafeFormatter`` does."""
    names: set[str] = set()
    try:
        for _literal, field_name, format_spec, _conversion in string.Formatter().parse(template):
            if field_name:
                root = field_name.split(".", 1)[0].split("[", 1)[0]
                if root.isidentifier():
                    names.add(root)
            if format_spec:
                names.update(_extract_format_placeholders(format_spec))
    except ValueError:
        masked = template.replace("{{", "").replace("}}", "")
        names.update(_FALLBACK_PLACEHOLDER_RE.findall(masked))
    return names


def _warn_undeclared_prompt_placeholders(
    ctx: RunContext, agent_type: str, template: str
) -> None:
    """Warn on stderr when YAML-declared ``template_vars`` omits a prompt placeholder."""
    from broker.tools.validate_prompt import (
        BROKER_FILLED_PLACEHOLDERS,
        resolve_domain_extensions,
        collect_template_vars,
    )

    raw = ctx.raw if isinstance(ctx.raw, Mapping) else {}
    block = raw.get(agent_type)
    if not isinstance(block, Mapping):
        return
    inherit_shared = block.get("inherit_shared", True) is not False
    shared = (
        raw.get("shared")
        if inherit_shared and isinstance(raw.get("shared"), Mapping)
        else {}
    )
    if "template_vars" not in shared and "template_vars" not in block:
        return
    declared_vars = (
        collect_template_vars(shared.get("template_vars"))
        | collect_template_vars(block.get("template_vars"))
    )
    response_format = block.get("response_format") or shared.get("response_format") or {}
    fields = (response_format.get("fields") if isinstance(response_format, Mapping) else None) or []
    field_keys = {
        f["key"] for f in fields
        if isinstance(f, Mapping) and isinstance(f.get("key"), str) and f["key"]
    }
    known = (
        BROKER_FILLED_PLACEHOLDERS
        | resolve_domain_extensions(dict(raw))
        | field_keys
        | declared_vars
    )
    unknown = sorted(p for p in _extract_format_placeholders(template) if p not in known)
    if unknown:
        print(
            f"broker.run: warning: {agent_type}: prompt contains undeclared placeholder(s) "
            f"{unknown} (not in template_vars or broker-filled set; SafeFormatter renders "
            f"missing keys as [N/A]). Run `python -m broker.tools.validate_prompt "
            f"{ctx.config_path}` to inspect.",
            file=sys.stderr,
        )


@dataclass
class Prepared:
    """A built, not yet run case: what ``main`` runs, for tests and wrappers."""

    runner: Any
    ctx: RunContext
    after_run: Any
    slots: dict
    phase_order: Any
    args: argparse.Namespace
    slot_files: dict = field(default_factory=dict)  # slot name -> file it was loaded from
    reflection_hook: Any = None  # the post_year reflection hook, when reflection is on


def prepare(argv) -> Prepared:
    """Parse ``argv`` and build the runner without running it.

    Raises ``SlotError`` or ``RunError`` (both ``ValueError``) for a bad command
    line, run block, slot or builder configuration.
    """
    ctx, slots, phase_order, args = _prepare_run(list(argv))
    if args.thinking_mode is not None:
        LLM_CONFIG.thinking_mode = args.thinking_mode
    _vet_decider_targets(ctx.raw, ctx, args.allow_module)
    loaded = {}
    runner, after_run, reflection_hook = _build_runner(ctx, slots, phase_order, args.allow_module, loaded)
    return Prepared(runner, ctx, after_run, slots, phase_order, args, loaded, reflection_hook)


def _retrieval_top_k(ctx):
    """Per agent type: how many memories its prompt asks the engine for."""
    types = dict.fromkeys(agent.agent_type for agent in (ctx.agents or {}).values())
    return {
        agent_type: (ctx.config.get_memory_config(agent_type) or {}).get(
            "retrieval_top_k", DEFAULT_RETRIEVAL_TOP_K)
        for agent_type in types
    }


def _write_run_record(prepared, argv, status, provenance=None):
    ctx, args = prepared.ctx, prepared.args
    used = prepared.slot_files  # the mock slot is absent under a real model
    record = {
        "status": status,
        "config": str(ctx.config_path),
        "case_dir": str(ctx.case_dir),
        "slots": {name: prepared.slots[name][0] for name in used},
        "slot_sources": {name: prepared.slots[name][1] for name in used},
        "slot_files": dict(used),
        "allow_modules": args.allow_module,
        "model": ctx.model,
        "thinking_mode": LLM_CONFIG.thinking_mode,
        "years": ctx.years,
        "agent_count": ctx.agent_count,
        "seed": ctx.seed,
        "governance": ctx.profile,
        "workers": ctx.workers,
        "phase_order": prepared.phase_order,
        "skill_registry": str(ctx.skill_registry_path),
        "output_dir": str(ctx.output_dir),
        "argv": argv,
        "memory": ctx.memory.record(_retrieval_top_k(ctx)),
        "reflection": ctx.reflection.record(),
        # Invariant 7 (broker/INVARIANTS.md): the runner's memory line style
        # per agent type, and memory writes per origin (memory_log.jsonl).
        "rejection_line_style": dict(getattr(prepared.runner, "rejection_line_styles", {}) or {}),
        "memory_writes_by_origin": dict(getattr(
            getattr(prepared.runner.memory_engine, "origin_gate", None), "counts", {}) or {}),
    }
    if prepared.reflection_hook is not None:
        record["reflection"].update(prepared.reflection_hook.counts)
    if ctx.population is not None:
        record["population"] = dict(ctx.population)
    if provenance:
        record.update(provenance)
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "broker_run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


#: Output folder of the last run this process finished (read by ``python -m broker.run``).
LAST_RUN_OUTPUT = None


def main(argv=None) -> int:
    """Run a case.

    Returns 2 for CLI, run-block, slot or build errors, and for a run that
    ``--strict-provenance`` refused before it started. Returns 1 when
    ``--strict-provenance`` is set and the manifest write failed after the run.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        try:
            prepared = prepare(argv)
        except SystemExit as exc:  # argparse's --help path.
            if exc.code == 0:
                return 0
            raise
    except (SlotError, RunError) as exc:
        print(f"broker.run: {exc}", file=sys.stderr)
        return 2
    runner, ctx, after_run = prepared.runner, prepared.ctx, prepared.after_run

    capture_launch_environment(runner)
    checks, problems = launch_checks(runner, ctx.model)
    strict = prepared.args.strict_provenance

    def provenance():
        return {"strict_provenance": strict, "provenance_checks": dict(checks),
                "provenance_problems": list(problems)}

    if strict and problems:
        print(f"broker.run: --strict-provenance refused this run: {'; '.join(problems)}", file=sys.stderr)
        _write_run_record(prepared, argv, "refused_provenance", provenance())
        return 2
    if problems:
        print(f"broker.run: provenance check: {'; '.join(problems)} (add --strict-provenance to refuse)",
              file=sys.stderr)

    # flush: with output sent to a file the header would otherwise land after
    # the run's own lines
    print(f"[broker.run] {ctx.config_path} | model={ctx.model} years={ctx.years} "
          f"agents={len(ctx.agents)} output={ctx.output_dir}", flush=True)
    # Written before the run so a failed run still leaves its record.
    _write_run_record(prepared, argv, "started", provenance())
    from broker.utils.provenance_requirements import RunRecordsError
    try:
        runner.run()
    except RunRecordsError as exc:
        # A mandatory run record could not be written: the run is not a usable run.
        print(f"broker.run: {exc}", file=sys.stderr)
        _write_run_record(prepared, argv, "records_failed", provenance())
        return 1
    if after_run is not None:
        after_run(ctx.output_dir)
    # `python -m broker.run` (broker/run/__main__.py) reads this and checks the mandatory run
    # records of the finished run (broker/utils/provenance_requirements.py), exiting non-zero
    # when they are incomplete, with or without --strict-provenance.
    global LAST_RUN_OUTPUT
    LAST_RUN_OUTPUT = ctx.output_dir
    counts = prepared.reflection_hook.counts if prepared.reflection_hook is not None else {}
    if counts.get("failed_calls") or counts.get("replies_not_stored"):
        print(f"broker.run: reflection: {counts['reflections_stored']} stored, "
              f"{counts['failed_calls']} model calls failed, {counts['replies_not_stored']} replies "
              f"too short to store (see broker_run.json)", file=sys.stderr)
    problem = manifest_problem(ctx.output_dir)
    checks["manifest_write"] = "pass" if problem is None else "fail"
    if problem is not None:
        problems.append(problem)
        if not strict:
            print(f"broker.run: provenance check: {problem} (add --strict-provenance to refuse)",
                  file=sys.stderr)
    if strict and problem is not None:
        print(f"broker.run: --strict-provenance: {problem}", file=sys.stderr)
        _write_run_record(prepared, argv, "provenance_failed", provenance())
        return 1
    _write_run_record(prepared, argv, "completed", provenance())
    return 0
