"""Parse case settings, assemble a runner, and record entry-point provenance."""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import sys
from typing import Any

import yaml

from broker.agents import AgentConfig, BaseAgent, Skill
from broker.components.context.builder import TieredContextBuilder
from broker.components.memory.engine import WindowMemoryEngine
from broker.core.experiment_builder import ExperimentBuilder
from broker.interfaces.skill_types import ExecutionResult
from broker.utils.agent_config import AgentTypeConfig, NON_AGENT_TOP_LEVEL_KEYS, UnknownConfigKeysError
from broker.utils.llm_utils import LLM_CONFIG, is_mock_model

from ._imports import SlotError, parse_slot, resolve_slot, valid_module_name, vet_import_target
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
    world: Any = None
    agents: dict[str, BaseAgent] | None = None


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


_SLOT_NAMES = ("world", "agents", "hooks", "validators", "mock")
# Short-term window of the WindowMemoryEngine built when the YAML has no
# global_config.memory.window_size. Named so the parameter table can read it.
DEFAULT_WINDOW_SIZE = 3
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
    if settings["strict_keys"]:
        from broker.tools.validate_prompt import magnitude_scale_problems

        for where, key, reason in magnitude_scale_problems(raw):
            raise RunError(
                f"{config_path}: response field {key!r} in {where!r} has {reason}; the action "
                f"number of a new case is on [0, 1] (set min: 0 and max: 1), or name the field "
                f"something other than magnitude or magnitude_pct (--strict-keys is on)"
            )
    ctx = RunContext(
        config_path=config_path, case_dir=case_dir, config=config, raw=raw,
        model=settings["model"], years=settings["years"], agent_count=settings["agent_count"],
        seed=settings["seed"], output_dir=output_dir, skill_registry_path=registry_path,
        profile=settings["governance"], workers=settings["workers"],
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
    types = [name for name, block in ctx.raw.items()
             if name not in NON_AGENT_TOP_LEVEL_KEYS and isinstance(block, dict)]
    if len(types) != 1:
        found = ", ".join(map(str, types)) or "none"
        raise RunError(f"default agents require exactly one agent type (found: {found}). Set run.agents to a factory")
    agent_type = types[0]
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
    skills = [
        Skill(
            skill_id=item["skill_id"],
            description=item.get("description", item["skill_id"]),
            affected_param=None,
            direction="none",
        )
        for item in items
        if "eligible_agent_types" not in item or agent_type in item["eligible_agent_types"]
    ]
    agents = {}
    for index in range(1, ctx.agent_count + 1):
        name = f"{agent_type}_{index}"
        agents[name] = BaseAgent(AgentConfig(
            name=name, agent_type=agent_type, state_params=[], objectives=[], constraints=[],
            skills=skills.copy(),
        ))
    return agents


def _mock_invokes(mock_factory, ctx, agent_types):
    if mock_factory is None:
        return {}
    result = mock_factory(ctx)
    if callable(result):
        return dict.fromkeys(agent_types, result)
    if not isinstance(result, Mapping):
        raise SlotError("run.mock must return a callable or a mapping of agent types to callables")
    for agent_type, invoke in result.items():
        if agent_type not in agent_types:
            raise SlotError(f"run.mock returned unknown agent type {agent_type!r}")
        if not callable(invoke):
            raise SlotError(f"run.mock must return a callable for agent type {agent_type!r}")
    return result


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
    mock_factory = _slot_factory("mock", ctx, slots, allowed_modules, loaded)
    invokes = _mock_invokes(mock_factory, ctx, agent_types)

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
            templates[agent_type] = template
    if len(agent_types) == 1 and templates:
        templates["default"] = templates[agent_types[0]]
    memory_cfg = ctx.raw.get("global_config", {}).get("memory", {}) or {}
    memory = WindowMemoryEngine(window_size=memory_cfg.get("window_size", DEFAULT_WINDOW_SIZE))
    config_path = str(ctx.config_path)
    context_builder = TieredContextBuilder(
        agents=ctx.agents, hub=None, prompt_templates=templates,
        yaml_path=config_path, memory_engine=memory,
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
    if phase_order is not None:
        builder.with_phase_order(phase_order)
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
    runner._llm_cache.update(invokes)
    return runner, after_run


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
    runner, after_run = _build_runner(ctx, slots, phase_order, args.allow_module, loaded)
    return Prepared(runner, ctx, after_run, slots, phase_order, args, loaded)


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
    }
    if provenance:
        record.update(provenance)
    ctx.output_dir.mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "broker_run.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")


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

    print(f"[broker.run] {ctx.config_path} | model={ctx.model} years={ctx.years} "
          f"agents={len(ctx.agents)} output={ctx.output_dir}")
    # Written before the run so a failed run still leaves its record.
    _write_run_record(prepared, argv, "started", provenance())
    runner.run()
    if after_run is not None:
        after_run(ctx.output_dir)
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
