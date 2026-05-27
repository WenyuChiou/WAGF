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
    cognition_import = (
        f"from .cognition import register_{domain}_framework\n"
        f"register_{domain}_framework()\n"
    ) if framework == "custom" else "# Using pre-registered framework — no cognition module needed.\n"

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
        from broker.domains.registry import register as _register_domain
        from .adapters.{domain}_pack import {domain.title().replace("_", "")}DomainPack

        _register_domain("{domain}", {domain.title().replace("_", "")}DomainPack())
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
        python {domain}/run_experiment.py --model gemma3:4b --years 3 --agents 5
        ```

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
    return dedent(f"""
        \"\"\"{domain} validator registrations.

        Phase 6C-v4 reminder: only ('physical', 'personal', 'social', 'semantic',
        'temporal', 'behavioural') slots accept Python BuiltinChecks. Thinking-
        level rules must go via the YAML ``rules:`` block in
        ``config/agent_types.yaml``, not here.
        \"\"\"
        from broker.components.governance.validator_registry import ValidatorRegistry
        from broker.components.governance.base_check import BuiltinCheck

        from .{domain}_validators import placeholder_physical_check


        def register():
            \"\"\"Idempotent registration of all {domain} validators.\"\"\"
            ValidatorRegistry.register(
                BuiltinCheck(
                    id="{domain}_placeholder",
                    slot="physical",
                    func=placeholder_physical_check,
                    description="Placeholder physical check — replace with real domain rule.",
                ),
                overwrite=True,
            )


        register()
        """).lstrip()


def gen_validators(domain: str) -> str:
    return dedent(f"""
        \"\"\"{domain} validator check functions.

        Each check receives (skill_proposal, validation_context) and returns
        a (passed, ValidationReport-or-None) tuple. See
        broker/components/governance/base_check.py for the protocol.
        \"\"\"
        from broker.components.governance.base_check import (
            ValidationReport, ValidationSeverity,
        )


        def placeholder_physical_check(skill_proposal, context):
            \"\"\"Always passes — replace with a real physical-feasibility rule.

            Examples of real checks:
              * 'budget check': reject if cost > agent.budget
              * 'cooldown check': reject if action taken too recently
              * 'eligibility check': reject if agent state precludes action
            \"\"\"
            return True, None
        """).lstrip()


def gen_domain_pack(domain: str) -> str:
    class_name = domain.title().replace("_", "") + "DomainPack"
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

            def reflection_status_text(self, agent: Any) -> str:
                \"\"\"One-line summary of agent's state for use in reflection prompts.\"\"\"
                return f"{{agent.agent_id}} status: TODO — describe."

            # --- Importance scoring --------------------------------------------------

            def importance_profiles(self) -> Dict[str, float]:
                \"\"\"Event-type → base importance score (0-1). Used by the memory engine.\"\"\"
                return {{
                    "default_event": 0.5,
                }}

            def compute_importance(
                self,
                event: Dict[str, Any],
                agent: Any,
                context: Optional[Dict[str, Any]] = None,
            ) -> float:
                \"\"\"Per-event importance. Override for context-sensitive scoring.\"\"\"
                profiles = self.importance_profiles()
                return profiles.get(event.get("type", ""), 0.5)

            # --- Skill-emotion mapping (optional) -----------------------------------

            def classify_emotion(self, decision: Dict[str, Any]) -> str:
                \"\"\"Map a decision to one of: neutral, hopeful, fearful, resigned.\"\"\"
                return "neutral"

            def skill_emotion_metadata(self) -> Dict[str, Dict[str, str]]:
                \"\"\"Optional: per-skill emotional flavor.\"\"\"
                return {{}}

            # --- Multi-agent group barrier text (optional) --------------------------

            def mg_barrier_text(self, agent: Any) -> str:
                return ""

            def extreme_actions(self) -> Set[str]:
                \"\"\"Skill IDs flagged as 'extreme' for prompt warnings.\"\"\"
                return set()
        """).lstrip()


def gen_run_experiment(domain: str) -> str:
    return dedent(f"""
        \"\"\"{domain} experiment entry point — minimal scaffolded version.

        Replace the SyntheticAgent / SyntheticEnvironment stubs with your real
        ABM, then plug into ExperimentBuilder.
        \"\"\"
        import argparse
        import sys
        from pathlib import Path

        # Add package to path so imports resolve when run as a script.
        sys.path.insert(0, str(Path(__file__).parent.parent))

        # Register DomainPack + validators (side-effect imports).
        import {domain}  # noqa: F401


        def main():
            parser = argparse.ArgumentParser()
            parser.add_argument("--model", default="gemma3:4b")
            parser.add_argument("--years", type=int, default=3)
            parser.add_argument("--agents", type=int, default=5)
            parser.add_argument("--seed", type=int, default=42)
            parser.add_argument("--output", default="results/smoke")
            args = parser.parse_args()

            print(f"[{domain}] scaffolded run — model={{args.model}}, years={{args.years}}, agents={{args.agents}}")
            print("TODO: replace this stub with ExperimentBuilder wiring.")
            print("See examples/vaccination_demo/run_experiment.py for a working reference.")


        if __name__ == "__main__":
            main()
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
    write(f"adapters/{domain}_pack.py", gen_domain_pack(domain))
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
                from broker.validators.governance.thinking_validator import (
                    register_framework_metadata,
                )


                def register_{domain}_framework() -> None:
                    register_framework_metadata(
                        framework_name="{domain}_framework",
                        constructs=["PRIMARY_LABEL"],
                        label_order=["VL", "L", "M", "H", "VH"],
                        label_mappings={{
                            "VL": "very_low",
                            "L": "low",
                            "M": "medium",
                            "H": "high",
                            "VH": "very_high",
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
