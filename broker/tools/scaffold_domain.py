"""Generate a minimal working WAGF domain skeleton (Phase 6C-v4 cycle 4 Part B).

The goal is to compress the "new domain" cost from ~600 LOC of boilerplate
to one shell command. The generated skeleton:

* Passes ``broker.tools.validate_prompt`` immediately.
* Uses the broker-filled ``{response_format}`` placeholder (the right
  pattern — no hand-rolled JSON to drift from YAML).
* Includes all 6 required YAML blocks identified by the Phase 6C-v4
  BLOCKER inventory (actions, parsing.constructs, log_fields, etc).
* Supports pre-registered cognitive frameworks (``pmt``, ``utility``,
  ``financial``, ``narrative_diffusion``, ``generic``); pass
  ``--framework custom`` to also scaffold a placeholder ``cognition/``
  package.

Usage::

    python -m broker.tools.scaffold_domain energy_consumer \\
        --output examples/energy_demo \\
        --skills "increase_use,maintain_use,decrease_use"

After scaffolding, edit the generated YAML / prompt / DomainPack to match
your domain, then run::

    python -m broker.tools.validate_prompt examples/energy_demo/config/agent_types.yaml
    python examples/energy_demo/run_experiment.py --model gemma3:4b --years 2 --agents 3

Reference:
- ``docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md`` — full schema + walkthrough
- ``examples/vaccination_demo/`` — production reference example

Generated runner: sys.path / import safety
--------------------------------------------
``gen_run_experiment()`` below emits a runner script that inserts two
things onto ``sys.path`` and imports the scaffolded package by its
on-disk directory name rather than a hardcoded domain literal. Both
choices are deliberate and were tightened after a 2026-08 review found
the first cut unsafe with a custom ``--output``:

* **Repo-root insert is guarded, not unconditional.** The runner always
  adds its own container directory (``_CONTAINER_DIR``, e.g. ``examples/``
  for the default layout) to ``sys.path`` so the scaffolded package
  imports. It also wants the *repo root* on the path, so a sibling WAGF
  checkout's installed ``broker`` package can't silently shadow the one
  next to this file. With the *default* output location
  (``examples/<domain>_demo/``) that repo root is exactly
  ``_CONTAINER_DIR.parent``, harmless to insert. But with a **custom**
  ``--output`` (e.g. a directory outside the repo entirely),
  ``_CONTAINER_DIR.parent`` can be an arbitrary directory — inserting an
  arbitrary path at ``sys.path[0]`` risks a same-named module or package
  sitting in that directory shadowing a stdlib or site-packages module
  for the rest of the process. The runner therefore only inserts
  ``_REPO_ROOT`` when it actually looks like the WAGF repo root (a
  ``broker/__init__.py`` exists directly under it); otherwise it's
  skipped and ``broker`` falls back to the normal pip-install lookup.
* **Import target is the on-disk directory name, not a hardcoded domain
  literal**, because ``--output``'s basename need not equal the domain
  name (default output is ``<domain>_demo/``, e.g. domain
  ``energy_consumer`` writes to ``energy_consumer_demo/``). Deriving the
  import target from the runner's own file location means it can't
  diverge from where the package was actually written, even if the
  directory is later renamed or copied.
* **The import-identity check after that import** (comparing
  ``Path(_pkg.__file__).resolve().parent`` against ``_PKG_DIR``) guards
  against the remaining failure mode: a *different*, already-installed
  package happening to share the scaffolded directory's name (a
  site-packages name collision) would otherwise import silently and
  the runner would proceed against the wrong code with no error. The
  check turns that into an immediate, actionable ``SystemExit`` instead
  of confusing runtime behavior.

Added: 2026-05-10.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from textwrap import dedent
from typing import List


# ---------------------------------------------------------------------------
# Template generators
# ---------------------------------------------------------------------------

def gen_package_init(domain: str, framework: str) -> str:
    """Top-level ``__init__.py`` — registers DomainPack + validators."""
    # NOTE: the continuation line carries the same 8-space indent as the
    # dedent() template body below, so dedent strips it uniformly. A bare
    # column-0 continuation here would zero-out dedent's common prefix and
    # emit an __init__.py with IndentationError (the custom-framework path
    # bug caught in the 2026-06-03 review).
    cognition_import = (
        f"from .cognition import register_{domain}_framework\n"
        f"        register_{domain}_framework()"
    ) if framework == "custom" else "# Using pre-registered framework — no cognition module needed."

    return dedent(f"""
        \"\"\"WAGF domain package: {domain}.

        Scaffolded by ``broker.tools.scaffold_domain``. Edit each module to
        describe your domain. After edits, run::

            python -m broker.tools.validate_prompt config/agent_types.yaml

        before invoking any experiment.
        \"\"\"
        # Step 1 (custom framework only): register cognitive framework metadata
        # so ThinkingValidator can resolve it from YAML.
        {cognition_import}
        # Step 2: register validators with the broker's ValidatorRegistry.
        from . import validators  # noqa: F401  (side-effect import)

        # Step 3: register the DomainPack so broker pipeline uses our overrides.
        from broker.domains.registry import DomainPackRegistry
        from .adapters.{domain}_pack import {domain.title().replace("_", "")}DomainPack

        DomainPackRegistry.register("{domain}", {domain.title().replace("_", "")}DomainPack())
        """).lstrip()


def gen_readme(domain: str, skills: List[str]) -> str:
    return dedent(f"""
        # {domain} — WAGF domain skeleton

        Scaffolded by ``broker.tools.scaffold_domain``.

        ## Quick start

        ```bash
        # 1. Validate the scaffolded config
        python -m broker.tools.validate_prompt {domain}/config/agent_types.yaml

        # 2. Run a smoke experiment
        python {domain}/run_experiment.py --model mock --years 2 --agents 2
        ```

        Note: mock-model runs show `[Broker:Retry]` / missing-construct warnings
        by design — the mock LLM returns blank output and governance catches +
        retries it. A completed run with audit output under `results/smoke`
        means the wiring is correct.

        ## Skills declared
        {chr(10).join(f"- `{s}`" for s in skills)}

        ## Next steps

        1. Edit `config/prompts/agent.txt` — describe the decision the LLM is
           making and the world state. Keep the `{{response_format}}`
           placeholder; it auto-renders the JSON shape from the YAML schema.
        2. Edit `config/skill_registry.yaml` if you need to add / rename skills.
        3. Edit `validators/{domain}_validators.py` — replace the placeholder
           check with real domain rules.
        4. Edit `adapters/{domain}_pack.py` — fill in `importance_profiles`,
           `event_handlers`, and any domain-specific hooks.
        5. Edit `run_experiment.py` — replace the synthetic agent generator
           and environment stub with your actual ABM.

        ## Reference
        - `examples/vaccination_demo/` — full non-water reference (HBM-based)
        - `examples/irrigation_abm/` — water demand reference
        - `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` — complete walkthrough
        """).lstrip()


def gen_skill_registry(domain: str, skills: List[str]) -> str:
    # `skill_registry.yaml` uses `skill_id:` (different from `agent_types.yaml`
    # actions which use `id:`). Phase 6E Finding #2: an earlier version of
    # this scaffold emitted `id:` and the broker's
    # GovernanceRegistry.register_from_yaml raised KeyError('skill_id') at
    # build time. Keep this aligned with the parser at
    # broker/components/governance/registry.py:70.
    skill_yaml = "\n".join(
        (f"  - skill_id: {s}\n"
         f"    domain: {domain}\n"
         f"    description: TODO — describe what skill '{s}' does.\n"
         f'    eligible_agent_types: ["agent"]')
        for s in skills
    )
    # Phase 6Q-E (2026-05-26): generic placeholder, was previously
    # ``"do_nothing"`` which is a flood-domain-specific skill name
    # registered in ``examples/governed_flood/config/skill_registry.yaml``
    # — a new-domain scaffold inherited flood-skill vocabulary in its
    # generated YAML. The placeholder only fires when ``--skills`` is
    # empty; in that case the value points to a non-existent skill
    # and experiment_builder catches it. Renaming to a TODO-marker
    # makes the intent visible.
    default = skills[0] if skills else "TODO_default_skill"
    return (
        f"# Skill registry for the {domain} domain.\n"
        f"# Scaffolded by broker.tools.scaffold_domain. Edit descriptions to\n"
        f"# match your decision semantics.\n"
        f"domain: {domain}\n"
        f"default_skill: {default}\n"
        f"skills:\n"
        f"{skill_yaml}\n"
    )


def gen_agent_types_yaml(domain: str, skills: List[str], framework: str) -> str:
    framework_value = f"{domain}_framework" if framework == "custom" else framework
    valid_choices = ", ".join(str(i + 1) for i in range(len(skills)))
    decision_desc = (
        f"Numeric ID, choose ONE from: {valid_choices} ("
        + ", ".join(f"{i + 1}={s}" for i, s in enumerate(skills))
        + ")"
    )

    # Build skill actions block at the EXACT indent the final YAML needs.
    # `actions:` lives at column 2 under `agent:`, so list items go at 4.
    # We use a marker that dedent won't touch and replace it AFTER dedent.
    skill_actions = "\n".join(
        (f"    - id: {s}\n"
         f'      aliases: ["{i + 1}", "{s}", "[{s}]"]\n'
         f"      description: >\n"
         f"        TODO — describe action '{s}'.")
        for i, s in enumerate(skills)
    )

    template = dedent(f"""
        # {domain} agent types config.
        # Scaffolded by broker.tools.scaffold_domain. EVERY block below is
        # required for the parser/validator pipeline to work — do NOT delete
        # one without consulting docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md.

        global_config:
          memory:
            window_size: 5
            consolidation_threshold: 0.6
            top_k_significant: 2
            decay_rate: 0.1

          reflection:
            interval: 1
            batch_size: 5
            importance_boost: 0.85
            persona_instruction: >
              Summarize each agent's recent decisions in first person, 2-3 sentences.
            questions:
              - "What changed in your situation this period?"
              - "Did your previous decision turn out as expected?"
            triggers:
              periodic_interval: 2

          llm:
            model: "command-line-override"
            num_ctx: 4096
            num_predict: 1024
            max_retries: 2

          governance:
            max_retries: 3
            max_reports_per_retry: 3
            domain: {domain}
            # Opt-in: dispatch this domain's registered PHYSICAL checks directly.
            # Default-OFF elsewhere so frozen paper runs stay byte-identical.
            dispatch_domain_physical: true

        shared:
          rating_scale: |
            ### RATING SCALE (You MUST use EXACTLY one of these codes):
            VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

          response_format:
            delimiter_start: "<<<DECISION_START>>>"
            delimiter_end: "<<<DECISION_END>>>"
            fields:
              - {{ key: "reasoning", type: "text", required: true,
                  description: "Explain your thought process in 2-3 sentences BEFORE choosing." }}
              - {{
                  key: "primary_assessment",
                  type: "appraisal",
                  required: true,
                  construct: "PRIMARY_LABEL",
                  reason_hint: "One sentence on your primary appraisal of the situation.",
                }}
              - {{
                  key: "decision",
                  type: "choice",
                  required: true,
                  description: "{decision_desc}",
                }}

        agent:
          agent_type: agent
          psychological_framework: {framework_value}
          prompt_template_file: prompts/agent.txt
          inherit_shared: true

          actions:
        __SKILL_ACTIONS_MARKER__

          constructs:
            primary: ["PRIMARY_LABEL"]
            secondary: []
            all: ["PRIMARY_LABEL"]

          parsing:
            decision_keywords: ["decision", "choice", "action"]
            default_skill: "{skills[0] if skills else 'TODO_default_skill'}"
            strict_mode: true
            preprocessor:
              {{ type: "smart_repair", quote_values: ["VL", "L", "M", "H", "VH"] }}
            proximity_window: 35
            constructs:
              PRIMARY_LABEL:
                keywords: ["primary_assessment", "primary"]
                regex: "(?i)\\\\b(VL|L|M|H|VH)\\\\b"
              PRIMARY_REASON:
                keywords: ["primary_assessment", "primary"]
                regex: ".*"

          log_fields: ["primary_assessment"]

          rules: []
        """).lstrip()
    # Inject skill action items at the marker AFTER dedent so the marker's
    # original indentation can't influence dedent's common-prefix computation.
    return template.replace("__SKILL_ACTIONS_MARKER__", skill_actions)


def gen_prompt(domain: str, skills: List[str]) -> str:
    skill_list = "\n".join(
        f"- {i + 1} = {s} (TODO: describe consequence)"
        for i, s in enumerate(skills)
    )
    return dedent(f"""
        {{narrative_persona}}

        It is time to make your annual {domain} decision.

        Your memory of recent events:
        {{memory}}

        Consider your situation, then assess your primary appraisal and choose
        ONE action below.

        Available actions: {{skills}}
        {skill_list}

        {{rating_scale}}

        Please respond using the EXACT JSON format below.
        - Use EXACTLY one of: VL, L, M, H, VH for the appraisal label.
        - "decision" MUST be the NUMERIC ID.

        {{response_format}}
        """).lstrip()


def gen_validators_init(domain: str) -> str:
    checks_const = f"{domain.upper()}_PHYSICAL_CHECKS"
    return dedent(f"""
        \"\"\"{domain} validator registrations.

        Phase 6C-v4 reminder: only ('physical', 'personal', 'social',
        'semantic') slots accept Python checks. Thinking-level
        rules must go via the YAML ``thinking_rules:`` block in
        ``config/agent_types.yaml`` (consumed by ThinkingValidator), not here.

        Registration mirrors examples/vaccination_demo/validators/__init__.py:
        ``ValidatorRegistry.register(domain, slot, checks_list)`` at import time.
        \"\"\"
        from .{domain}_validators import {checks_const}

        try:
            from broker.components.governance.validator_registry import ValidatorRegistry

            ValidatorRegistry.register("{domain}", "physical", list({checks_const}))
        except ImportError:
            # broker not importable (e.g. minimal install) — skip registration.
            pass
        """).lstrip()


def gen_validators(domain: str) -> str:
    checks_const = f"{domain.upper()}_PHYSICAL_CHECKS"
    return dedent(f"""
        \"\"\"{domain} validator check functions.

        Each check has signature ``(skill_name, rules, context) -> List[ValidationResult]``.
        Return ``[]`` to PASS; return ``[ValidationResult(valid=False, ...)]`` to REJECT.
        Only the physical / personal / social / semantic
        slots accept Python checks; thinking-level coherence rules go in
        ``config/agent_types.yaml`` under the ``thinking_rules:`` key (consumed by
        ThinkingValidator), NOT here. Reference: examples/vaccination_demo/validators/.
        \"\"\"
        from __future__ import annotations

        from typing import Any, Dict, List

        from broker.governance.rule_types import GovernanceRule
        from broker.interfaces.skill_types import ValidationResult


        def placeholder_physical_check(
            skill_name: str, rules: List[GovernanceRule], context: Dict[str, Any]
        ) -> List[ValidationResult]:
            \"\"\"Always passes — replace with a real physical-feasibility rule.

            Examples of real checks (state-precondition / immutability):
              * budget check: reject if cost > agent budget
              * cooldown check: reject if action taken too recently
              * eligibility check: reject if agent state precludes action

            Reject by returning a populated list, e.g.::

                if int(context.get("budget", 0)) < cost:
                    return [ValidationResult(
                        valid=False,
                        validator_name="{domain}_budget",
                        errors=["insufficient budget for this action"],
                        # deterministic blocks let the retry loop EarlyExit
                        # instead of burning all retries.
                        metadata={{
                            "category": "physical",
                            "deterministic": True,
                        }},
                    )]
            \"\"\"
            return []


        {checks_const} = (
            placeholder_physical_check,
        )
        """).lstrip()


def gen_domain_pack(domain: str, framework: str = "pmt") -> str:
    class_name = domain.title().replace("_", "") + "DomainPack"
    # Match gen_agent_types_yaml's framework resolution (custom -> <domain>_framework).
    framework_value = f"{domain}_framework" if framework == "custom" else framework
    return dedent(f"""
        \"\"\"{domain} DomainPack.

        Subclass of DefaultDomainPack — only override what differs from the
        no-op defaults. Most methods can stay as the parent's default while you
        prototype.
        \"\"\"
        from typing import Any, Dict, List, Optional, Set

        from broker.domains.default import DefaultDomainPack


        class {class_name}(DefaultDomainPack):
            \"\"\"DomainPack for the {domain} domain.

            See broker/domains/protocol.py for the full method list — most
            hooks have sensible no-op defaults from DefaultDomainPack you
            can ignore at first.
            \"\"\"

            # --- Identity / labels --------------------------------------------------

            @property
            def name(self) -> str:
                return "{domain}"

            def psychological_framework(self) -> str:
                \"\"\"Framework label the ThinkingValidator resolves for this
                domain — MUST match config/agent_types.yaml's
                ``psychological_framework``. Dispatch reads THIS (the pack), not
                the YAML field, so leaving DefaultDomainPack's "" escape-hatch
                would silently ignore your YAML framework choice. For a 'custom'
                framework, register its metadata first (see cognition/).\"\"\"
                return "{framework_value}"

            def reflection_status_text(self, context: Any) -> Optional[str]:
                \"\"\"One-line agent-state summary for reflection prompts (canonical
                signature — consumers pass a reflection context, not the agent).\"\"\"
                return f"{{getattr(context, 'agent_id', 'agent')}} status: TODO — describe."

            # --- Importance scoring --------------------------------------------------

            def importance_profiles(self) -> Dict[str, float]:
                \"\"\"Event-type → base importance score (0-1). Used by the memory engine.\"\"\"
                return {{
                    "default_event": 0.5,
                }}

            def compute_importance(self, context: Any, base: float = 0.5) -> float:
                \"\"\"Per-event importance (consumers call (context, base); keep this
                signature). Customize by inspecting context; defaults to
                DefaultDomainPack behavior.\"\"\"
                return super().compute_importance(context, base)

            # --- Skill-emotion mapping (optional) -----------------------------------

            def classify_emotion(self, decision: str, context: Any) -> str:
                \"\"\"Map a decision to one emotion. Keep this consumer-call signature;
                customize by inspecting decision/context.\"\"\"
                return super().classify_emotion(decision, context)

            def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
                \"\"\"Optional per-skill emotional flavor. Keep the skill_name
                parameter; experiment_runner calls this per skill.\"\"\"
                return super().skill_emotion_metadata(skill_name)

            # --- Multi-agent group barrier text (optional) --------------------------

            def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
                \"\"\"Barrier text from the agent's profile dict (canonical signature).\"\"\"
                return ""

            def extreme_actions(self) -> Set[str]:
                \"\"\"Skill IDs flagged as 'extreme' for prompt warnings.\"\"\"
                return set()
        """).lstrip()


def gen_run_experiment(domain: str) -> str:
    return dedent(f"""
        \"\"\"{domain} experiment entry point - minimal runnable smoke.

        Replace SyntheticEnvironment with your real ABM as the domain matures.
        \"\"\"
        from __future__ import annotations

        import argparse
        import sys
        from pathlib import Path

        # Path setup + package import below are guarded/checked on purpose --
        # see scaffold_domain.py's "Generated runner: sys.path / import
        # safety" docstring section for the rationale.
        _PKG_DIR = Path(__file__).resolve().parent
        _CONTAINER_DIR = _PKG_DIR.parent  # e.g. examples/, for the default output layout
        sys.path.insert(0, str(_CONTAINER_DIR))
        _REPO_ROOT = _CONTAINER_DIR.parent
        if (_REPO_ROOT / "broker" / "__init__.py").exists():
            sys.path.insert(0, str(_REPO_ROOT))

        import yaml  # noqa: E402

        import importlib  # noqa: E402
        _pkg = importlib.import_module(_PKG_DIR.name)  # noqa: E402
        _pkg_file = getattr(_pkg, "__file__", None)  # noqa: E402
        if _pkg_file is None or Path(_pkg_file).resolve().parent != _PKG_DIR:
            raise SystemExit(
                f"Imported '{{_PKG_DIR.name}}' from {{_pkg_file}}, not "
                f"{{_PKG_DIR}}. Rename the scaffold directory to something unique."
            )

        from broker.agents import AgentConfig, BaseAgent, Skill  # noqa: E402
        from broker.components.memory.engine import WindowMemoryEngine  # noqa: E402
        from broker.core.experiment import ExperimentBuilder  # noqa: E402
        from broker.interfaces.skill_types import ExecutionResult  # noqa: E402

        HERE = Path(__file__).resolve().parent
        CONFIG = HERE / "config"


        class SyntheticEnvironment:
            \"\"\"Small stand-in for the domain ABM used by scaffold smoke runs.\"\"\"

            def __init__(self):
                self.current_year = 0

            def advance_step(self):
                self.current_year += 1
                return {{
                    "current_year": self.current_year,
                    # TODO: replace with a domain variable from your ABM.
                    "domain_signal": 0.5,
                }}

            def execute_skill(self, approved_skill):
                return ExecutionResult(success=True, state_changes={{}})


        def load_declared_skills():
            data = yaml.safe_load(
                (CONFIG / "skill_registry.yaml").read_text(encoding="utf-8")
            ) or {{}}
            return [
                Skill(
                    skill_id=item["skill_id"],
                    description=item.get("description", item["skill_id"]),
                    affected_param=None,
                    direction="none",
                )
                for item in data.get("skills", [])
            ]


        def build_agents(count, skills):
            return {{
                f"agent_{{i}}": BaseAgent(
                    AgentConfig(
                        name=f"agent_{{i}}",
                        agent_type="agent",
                        state_params=[],
                        objectives=[],
                        constraints=[],
                        skills=skills,
                    )
                )
                for i in range(1, count + 1)
            }}


        def main(argv=None):
            parser = argparse.ArgumentParser()
            parser.add_argument("--model", default="gemma3:4b")
            parser.add_argument("--years", type=int, default=3)
            parser.add_argument("--agents", type=int, default=5)
            parser.add_argument("--seed", type=int, default=42)
            parser.add_argument("--output", default="results/smoke")
            args = parser.parse_args(argv)

            output_path = Path(args.output)
            if not output_path.is_absolute():
                output_path = HERE / output_path

            skills = load_declared_skills()
            if not skills:
                raise SystemExit("No skills found in config/skill_registry.yaml")
            agents = build_agents(args.agents, skills)

            runner = (
                ExperimentBuilder()
                .with_model(args.model)
                .with_years(args.years)
                .with_agents(agents)
                .with_simulation(SyntheticEnvironment())
                .with_skill_registry(str(CONFIG / "skill_registry.yaml"))
                .with_memory_engine(WindowMemoryEngine(window_size=3))
                .with_governance("strict", str(CONFIG / "agent_types.yaml"))
                .with_exact_output(str(output_path))
                .with_workers(1)
                .with_seed(args.seed)
            ).build()

            print(
                f"[{domain}] smoke run | model={{args.model}} "
                f"years={{args.years}} agents={{args.agents}}"
            )
            runner.run()
            print(f"Done. Audit + traces under: {{output_path}}")
            return 0


        if __name__ == "__main__":
            raise SystemExit(main())
        """).lstrip()


# ---------------------------------------------------------------------------
# File-system writer
# ---------------------------------------------------------------------------

def scaffold(
    domain: str,
    output_dir: Path,
    skills: List[str],
    framework: str,
    force: bool = False,
) -> List[Path]:
    """Write the full skeleton. Returns the list of created paths.

    Raises FileExistsError if any target file exists and ``force=False``.
    """
    if output_dir.exists() and any(output_dir.iterdir()) and not force:
        raise FileExistsError(
            f"Output dir {output_dir} is non-empty. Pass --force to overwrite."
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "adapters").mkdir(exist_ok=True)
    (output_dir / "validators").mkdir(exist_ok=True)
    (output_dir / "config").mkdir(exist_ok=True)
    (output_dir / "config" / "prompts").mkdir(exist_ok=True)

    written: List[Path] = []

    def write(rel_path: str, content: str) -> None:
        full = output_dir / rel_path
        full.write_text(content, encoding="utf-8")
        written.append(full)

    write("__init__.py", gen_package_init(domain, framework))
    write("README.md", gen_readme(domain, skills))
    write("config/skill_registry.yaml", gen_skill_registry(domain, skills))
    write("config/agent_types.yaml", gen_agent_types_yaml(domain, skills, framework))
    write("config/prompts/agent.txt", gen_prompt(domain, skills))
    write("validators/__init__.py", gen_validators_init(domain))
    write(f"validators/{domain}_validators.py", gen_validators(domain))
    write("adapters/__init__.py", "")
    write(f"adapters/{domain}_pack.py", gen_domain_pack(domain, framework))
    write("run_experiment.py", gen_run_experiment(domain))

    if framework == "custom":
        cognition_dir = output_dir / "cognition"
        cognition_dir.mkdir(exist_ok=True)
        (cognition_dir / "__init__.py").write_text(
            dedent(f"""
                from .{domain}_framework import register_{domain}_framework
                __all__ = ["register_{domain}_framework"]
                """).lstrip(),
            encoding="utf-8",
        )
        (cognition_dir / f"{domain}_framework.py").write_text(
            dedent(f"""
                \"\"\"{domain} cognitive framework registration.

                Replace the construct list with your psychological model's
                latent variables (e.g. HBM: SUSCEPTIBILITY/SEVERITY/...,
                TPB: ATTITUDE/NORMS/CONTROL, etc).
                \"\"\"
                from broker.validators.governance.frameworks import (
                    register_behavioral_framework,
                )


                def register_{domain}_framework() -> None:
                    register_behavioral_framework(
                        name="{domain}_framework",
                        # constructs: primary / secondary / all — replace the
                        # placeholder labels with your model's latent variables;
                        # they MUST match parsing.constructs in agent_types.yaml.
                        constructs={{
                            "primary": "PRIMARY_LABEL",
                            "secondary": "PRIMARY_LABEL",
                            "all": ["PRIMARY_LABEL"],
                        }},
                        # label_order: ordinal mapping (worst -> best)
                        label_order={{"VL": 0, "L": 1, "M": 2, "H": 3, "VH": 4}},
                        # label_mappings: free-text variant -> canonical (optional)
                        label_mappings={{
                            "VERY LOW": "VL", "LOW": "L", "MEDIUM": "M",
                            "HIGH": "H", "VERY HIGH": "VH",
                        }},
                    )
                """).lstrip(),
            encoding="utf-8",
        )
        written.extend([
            cognition_dir / "__init__.py",
            cognition_dir / f"{domain}_framework.py",
        ])

    return written


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a minimal working WAGF domain skeleton.",
    )
    parser.add_argument(
        "domain",
        help="Domain name (lowercase, snake_case). e.g. 'energy_consumer'.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. Default: examples/<domain>_demo/",
    )
    parser.add_argument(
        "--skills",
        default="action_a,action_b,action_c",
        help="Comma-separated skill IDs. Default: action_a,action_b,action_c",
    )
    parser.add_argument(
        "--framework",
        choices=[
            "pmt",
            "utility",
            "financial",
            "narrative_diffusion",
            "generic",
            "custom",
        ],
        default="pmt",
        help=(
            "Cognitive framework. default 'pmt' is retained for backward-compat; "
            "new domains are encouraged to choose 'generic' or one of the "
            "registered frameworks. 'custom' scaffolds a cognition/ package "
            "with a framework registration boilerplate."
        ),
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite non-empty output directory.",
    )
    args = parser.parse_args(argv)

    if not args.domain.replace("_", "").isalnum() or not args.domain.islower():
        print(
            f"ERROR: domain name must be lowercase snake_case (got '{args.domain}')",
            file=sys.stderr,
        )
        return 1

    skills = [s.strip() for s in args.skills.split(",") if s.strip()]
    if not skills:
        print("ERROR: --skills must list at least one skill", file=sys.stderr)
        return 1

    output_dir = args.output or Path("examples") / f"{args.domain}_demo"

    try:
        written = scaffold(args.domain, output_dir, skills, args.framework, args.force)
    except FileExistsError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    print(f"Scaffolded {len(written)} files in {output_dir}/:")
    for p in written:
        print(f"  {p.relative_to(output_dir.parent) if output_dir.parent != Path('.') else p}")

    yaml_path = output_dir / "config" / "agent_types.yaml"
    print("\nNext steps:")
    print(f"  1. python -m broker.tools.validate_prompt {yaml_path}")
    print(f"  2. Edit {output_dir}/config/prompts/agent.txt to describe the domain")
    print(f"  3. Edit {output_dir}/adapters/{args.domain}_pack.py to fill in domain hooks")
    print(f"  4. python {output_dir}/run_experiment.py --model gemma3:4b --years 2 --agents 3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
