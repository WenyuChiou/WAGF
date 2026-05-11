# How to add a new domain to WAGF

This guide walks through plugging a non-water topic — e.g., **vaccination decision-making** — into the WAGF framework. After Phase 6C-v2 (2026-05-10), adding a new domain requires **one class** (a `DomainPack`) and **one registration call**. Zero edits to `broker/`.

## Prerequisites

- Python 3.10+, the WAGF repo cloned, `pip install -e .` run.
- A model/LLM you can call (the irrigation example uses `gemma3:4b` via Ollama; small smoke tests use `gemma3:1b`).
- Familiarity with the existing irrigation example at `examples/irrigation_abm/` is the fastest way to get the gestalt.

## Architectural overview

WAGF treats each domain as a **plug-in** built from these registry-driven layers:

| Layer | What it does | Where it lives |
|---|---|---|
| **DomainPack** | Single facade for all domain-specific behavior (reflection text, emotion classification, event handlers, etc.) | Your example package, registered to `DomainPackRegistry` |
| **Skill registry** | YAML-driven list of available skills with preconditions and conflicts | `examples/<your_domain>/config/skill_registry.yaml` |
| **Validator checks** | Python functions that veto invalid skill proposals | `examples/<your_domain>/validators/` |
| **Validator rules** | YAML-driven cross-field veto rules | `examples/<your_domain>/config/agent_types.yaml` |
| **Memory engine** | Choice of memory engine (window / humancentric / hierarchical) | YAML, references engines registered in `MemoryEngineRegistry` |
| **Prompt template** | The chat template that frames each turn for the LLM | `examples/<your_domain>/config/prompts/<agent_type>.txt` |
| **Lifecycle hooks** | Year-by-year orchestration (env update → agent context → reflection → memory) | `examples/<your_domain>/run_experiment.py` |

The broker pipeline calls into your `DomainPack` for any domain-specific decision; everything else is YAML-driven. **No `broker/` edits.**

## 7-step walkthrough — vaccination decision example

We'll build a minimal vaccination-decision ABM. Agents are individuals deciding whether to vaccinate based on perceived risk (Health Belief Model), social pressure, and recent outbreak signals.

### Step 1 — Scaffold the example directory

```
examples/vaccination_abm/
├── __init__.py                # registers DomainPack
├── adapters/
│   ├── __init__.py
│   ├── vaccination_adapter.py # importance/emotion (~100 LOC)
│   └── vaccination_pack.py    # DomainPack subclass (~150 LOC)
├── config/
│   ├── agent_types.yaml       # agent personas + reflection questions
│   ├── skill_registry.yaml    # skills + preconditions
│   └── prompts/
│       └── individual.txt     # LLM prompt template
├── validators/
│   ├── __init__.py            # registers checks with ValidatorRegistry
│   └── vaccination_validators.py  # check functions (~80-200 LOC)
└── run_experiment.py          # lifecycle hooks + main entry (~80-200 LOC)
```

Copy `examples/irrigation_abm/` as a starting skeleton, then strip out water-specific files.

### Step 2 — Define skills in `config/skill_registry.yaml`

```yaml
domain: vaccination
default_skill: delay     # falls back here when validator rejects all options

skills:
  - skill_id: get_vaccinated
    description: "Receive a single vaccine dose"
    eligible_agent_types: ["individual"]
    preconditions:
      - "not vaccinated"   # framework's state-gate filters this out post-vaccination
    institutional_constraints:
      once_only: false      # can re-vaccinate (boosters)
    allowed_state_changes:
      - vaccinated

  - skill_id: delay
    description: "Wait for more information before deciding"
    eligible_agent_types: ["individual"]
    preconditions: []
    institutional_constraints:
      cost_type: "free"

  - skill_id: refuse
    description: "Decline vaccination"
    eligible_agent_types: ["individual"]
    preconditions: []
    institutional_constraints:
      cost_type: "free"
```

### Step 3 — Define agent personas in `config/agent_types.yaml`

**Critical**: this YAML is the single biggest source of confusion for new-domain users. The minimal example below shows ALL required blocks — leaving any out causes silent parser / validator failures (Phase 6C-v4 finding inventory at the end of this doc).

```yaml
# =============================================================================
# GLOBAL CONFIGURATION
# =============================================================================
global_config:
  memory:
    window_size: 5
    consolidation_threshold: 0.6
    decay_rate: 0.1

  reflection:
    interval: 1
    batch_size: 5
    persona_instruction: "Summarize each agent's vaccination journey..."
    questions:
      - "Has your perceived susceptibility to infection changed this year?"
      - "Did the perceived benefits outweigh the barriers?"
    triggers:
      crisis: true
      periodic_interval: 2
      decision_types: [get_vaccinated, refuse]

  llm:
    model: "command-line-override"
    num_ctx: 4096
    num_predict: 1024
    max_retries: 2

  governance:
    max_retries: 3
    domain: vaccination               # REQUIRED — must match skill_registry.yaml domain

# =============================================================================
# SHARED — rating scale + response schema seen by ALL agent types
# =============================================================================
shared:
  rating_scale: |
    ### RATING SCALE (You MUST use EXACTLY one of these codes):
    VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

  response_format:
    delimiter_start: "<<<DECISION_START>>>"
    delimiter_end: "<<<DECISION_END>>>"
    fields:
      # Each `key` MUST match what the LLM emits in JSON AND what the
      # parser extracts. Mismatches between `key` here and the JSON
      # example in your prompt template cause silent parser rejection.
      - { key: "reasoning", type: "text", required: true,
          description: "Explain your thought process in 2-3 sentences." }
      - {
          key: "susceptibility_assessment",          # ← JSON key in LLM output
          type: "appraisal",                          # ← {label, reason} pair
          required: true,
          construct: "SUSCEPTIBILITY_LABEL",          # ← label extracted to this key in reasoning dict
          reason_hint: "One sentence on how likely you feel to be infected.",
        }
      - {
          key: "self_efficacy_assessment",
          type: "appraisal",
          required: true,
          construct: "SELF_EFFICACY_LABEL",
          reason_hint: "One sentence on your confidence to vaccinate.",
        }

# =============================================================================
# AGENT TYPE — individual
# =============================================================================
individual:
  agent_type: individual
  psychological_framework: hbm                # ← MUST be pre-registered (see Step 4)
  prompt_template_file: prompts/individual.txt   # ← relative to THIS yaml's dir
  inherit_shared: true

  # ---------------------------------------------------------------------------
  # actions: REQUIRED. Without this block parser.get_valid_actions("individual")
  # returns [] and every LLM output is silently rejected. skill_registry.yaml's
  # `eligible_agent_types: ["individual"]` is NOT auto-translated here.
  # ---------------------------------------------------------------------------
  actions:
    - id: get_vaccinated
      aliases: ["1", "get_vaccinated", "vaccinate", "[get_vaccinated]"]
      description: >
        Receive a single dose of the seasonal vaccine this year.
    - id: delay
      aliases: ["2", "delay", "wait", "postpone", "[delay]"]
      description: >
        Postpone the decision; reconsider next year.
    - id: refuse
      aliases: ["3", "refuse", "decline", "skip", "[refuse]"]
      description: >
        Decline vaccination this year.

  # ---------------------------------------------------------------------------
  # parsing: REQUIRED. The `constructs:` block tells the parser HOW to extract
  # appraisal labels from nested JSON. Without it, the agent_validator rejects
  # responses with "missing required fields".
  # ---------------------------------------------------------------------------
  parsing:
    decision_keywords: ["decision", "choice", "action", "selected_action"]
    default_skill: "delay"                    # ← must match skill_registry.yaml default_skill
    strict_mode: true
    preprocessor:
      { type: "smart_repair", quote_values: ["VL", "L", "M", "H", "VH"] }
    proximity_window: 35

    constructs:
      SUSCEPTIBILITY_LABEL:
        keywords: ["susceptibility_assessment", "perceived_susceptibility", "susceptibility"]
        regex: "(?i)\\b(VL|L|M|H|VH)\\b"
      SUSCEPTIBILITY_REASON:
        keywords: ["susceptibility_assessment", "perceived_susceptibility", "susceptibility"]
        regex: ".*"
      SELF_EFFICACY_LABEL:
        keywords: ["self_efficacy_assessment", "perceived_self_efficacy", "self_efficacy"]
        regex: "(?i)\\b(VL|L|M|H|VH)\\b"
      SELF_EFFICACY_REASON:
        keywords: ["self_efficacy_assessment", "perceived_self_efficacy", "self_efficacy"]
        regex: ".*"

  # log_fields: which appraisal keys to surface in audit CSV `reason_*` columns
  log_fields: ["susceptibility_assessment", "self_efficacy_assessment"]

  # (Optional) Tier-2 thinking rules — YAML-driven HBM coherence checks
  # consumed by ThinkingValidator. Add only the rules you want to enforce.
  rules:
    - id: high_susceptibility_high_efficacy_no_refuse
      level: ERROR
      blocked_skills: [refuse]
      conditions:
        - { type: construct, field: SUSCEPTIBILITY_LABEL, operator: "in", values: ["H", "VH"] }
        - { type: construct, field: SELF_EFFICACY_LABEL, operator: "in", values: ["H", "VH"] }
      message: "HBM coherence: high susceptibility + high self-efficacy should not lead to refusal."
```

### Step 4 — Implement validator checks

```python
# examples/vaccination_abm/validators/vaccination_validators.py

from broker.interfaces.skill_types import ValidationResult

def vaccinated_no_revaccinate_in_short_window(skill_name, rules, context):
    """Block re-vaccination if last dose < 6 months ago."""
    if skill_name != "get_vaccinated":
        return []
    weeks_since = context.get("weeks_since_dose", 999)
    if weeks_since < 26:  # 6 months
        return [ValidationResult(
            valid=False,
            validator_name="vaccinated_no_revaccinate_in_short_window",
            errors=["Vaccination too recent (less than 6 months ago)."],
            metadata={"category": "physical", "rule_id": "physical_short_window"}
        )]
    return []

VACCINATION_PHYSICAL_CHECKS = (vaccinated_no_revaccinate_in_short_window,)
```

```python
# examples/vaccination_abm/validators/__init__.py

from broker.components.governance.validator_registry import ValidatorRegistry
from .vaccination_validators import VACCINATION_PHYSICAL_CHECKS

ValidatorRegistry.register("vaccination", "physical", list(VACCINATION_PHYSICAL_CHECKS))
```

### Step 5 — Implement `DomainPack`

```python
# examples/vaccination_abm/adapters/vaccination_pack.py

from typing import Any, Dict, List, Optional, Set
from broker.domains.protocol import DomainPack, EventHandler


def _handle_outbreak(event, gs):
    gs["infection_pressure"] = event.data.get("severity", 0.5)
    gs["outbreak_message"] = event.description


def _handle_vaccine_rollout(event, gs):
    gs["vaccine_supply"] = event.data.get("doses", 0)
    gs["rollout_message"] = event.description


class VaccinationDomainPack:
    """DomainPack for vaccination decision-making example."""

    name: str = "vaccination"

    # ─── Reflection ───────────────────────────────────────────────
    def reflection_status_text(self, context: Any) -> Optional[str]:
        if getattr(context, "agent_type", None) != "individual":
            return None
        parts = []
        if getattr(context, "vaccinated", False):
            weeks = getattr(context, "weeks_since_dose", 0)
            parts.append(f"you received your last dose {weeks} weeks ago")
        else:
            parts.append("you are unvaccinated")
        if getattr(context, "had_infection", False):
            parts.append("you've recovered from a prior infection")
        return f"Current status: {', '.join(parts)}." if parts else None

    def reflection_questions(self) -> List[str]:
        return []  # uses agent_types.yaml questions

    def reflection_persona(self) -> Optional[str]:
        return None

    # ─── Memory / importance / emotion ─────────────────────────────
    def importance_profiles(self) -> Dict[str, float]:
        return {
            "first_outbreak": 0.95,
            "side_effect_event": 0.88,
            "stable_year": 0.55,
        }

    def compute_importance(self, context: Any, base: float = 0.7) -> float:
        importance = base
        if context.get("outbreak_severity", 0) > 0.6:
            importance = self.importance_profiles()["first_outbreak"]
        return min(1.0, max(0.0, importance))

    def classify_emotion(self, decision: str, context: Any) -> str:
        if decision == "get_vaccinated" and context.get("outbreak_severity", 0) > 0.6:
            return "critical"
        if decision == "refuse":
            return "major"
        return "minor"

    def emotional_keywords(self) -> Dict[str, str]:
        return {"outbreak": "critical", "side_effect": "major"}

    def retrieval_weights(self) -> Dict[str, float]:
        return {"W_recency": 0.40, "W_importance": 0.40, "W_context": 0.20}

    # ─── Skills ────────────────────────────────────────────────────
    def skill_emotion_metadata(self, skill_name: str) -> Dict[str, Any]:
        return {
            "get_vaccinated": {"emotion": "major", "importance": 0.85, "source": "personal"},
            "refuse":         {"emotion": "major", "importance": 0.70, "source": "personal"},
            "delay":          {"emotion": "minor", "importance": 0.40, "source": "personal"},
        }.get(skill_name, {})

    def extreme_actions(self) -> Set[str]:
        return set()  # vaccination has no irreversible one-way actions

    # ─── Events ────────────────────────────────────────────────────
    def event_handlers(self) -> Dict[str, EventHandler]:
        return {
            "outbreak": _handle_outbreak,
            "vaccine_rollout": _handle_vaccine_rollout,
        }

    # ─── Context provider hooks ────────────────────────────────────
    def mg_barrier_text(self, profile: Dict[str, Any]) -> str:
        return ""  # no MG-specific narrative for this minimal example

    # ─── Validators / templates ────────────────────────────────────
    def builtin_checks(self) -> Dict[str, List]:
        return {}   # already registered via ValidatorRegistry

    def initial_memory_templates(self, profile: Dict[str, Any]) -> List[Any]:
        return []
```

### Step 6 — Register the pack at import time

```python
# examples/vaccination_abm/__init__.py

"""Vaccination decision-making ABM."""
from broker.domains.registry import DomainPackRegistry
from examples.vaccination_abm.adapters.vaccination_pack import VaccinationDomainPack

DomainPackRegistry.register("vaccination", VaccinationDomainPack())
```

### Step 7 — Run a smoke test

```bash
python examples/vaccination_abm/run_experiment.py \
    --model gemma3:1b --years 3 --agents 5 --seed 42 \
    --output results/smoke_vacc
```

Verify:
- ✅ No `[Governance:Diagnostic] Key collision` warnings (you used distinct YAML field names)
- ✅ No `[DomainPack] No pack registered for 'vaccination'` warning (your `__init__.py` registered)
- ✅ `results/smoke_vacc/individual_governance_audit.csv` has `proposed_skill / final_skill / status` columns
- ✅ At least one trace shows `validator_rejected` (your check fires correctly)
- ✅ Reflection prompts include "you are unvaccinated" (your `reflection_status_text` is wired)

## Common pitfalls

### Setup-time pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| All traces have `proposed_skill = default_skill_name` | YAML missing `default_skill:` | Add to `skill_registry.yaml` top level |
| `[DomainPack] No pack registered` warning | Pack class not imported / not registered | Verify `examples/<your_domain>/__init__.py` runs at startup |
| Reflection prompt has no domain text | `reflection_status_text` returns `None` for your agent_type | Check the `getattr(context, "agent_type", None) == "individual"` gate |
| `rules_*_hit` columns are 0 | Validator checks don't set `metadata["category"]` | Add `metadata={"category": "physical"}` (or appropriate slot) to ValidationResult |
| Audit `state_before` missing your key fields | Your env-state dict and your agent-state dict have key collisions | Use distinct names (e.g., `agent_outbreak_severity` for agent state, `outbreak_severity` for env) |
| LLM proposes invalid skill names | Skill registry / prompt mismatch | Ensure prompt's enum matches `skill_registry.yaml` skill_ids |

### Parser / validator pitfalls (Phase 6C-v4 findings)

These 6 BLOCKERs were surfaced by the `examples/vaccination_demo/` PoC on 2026-05-10 and fixed in Phase 6C-v4. They are the single most common reason a freshly-scaffolded new domain produces 0 valid LLM decisions:

| # | Symptom | Root cause | Fix |
|---|---|---|---|
| 1 | `ValueError: slot must be one of (physical, personal, social, semantic, ...)` when registering Python checks | `ValidatorRegistry` does not accept `"thinking"` as a slot — thinking-validator checks come from YAML `rules:` block, not the registry | Either move thinking checks into `agent_types.yaml: rules:` (preferred), or use the YAML-driven path. Python `BuiltinCheck` callables can only register under physical/personal/social/semantic slots. |
| 2 | Prompt template renders with `[N/A]` literals | Unfilled custom `{placeholder}` — broker only auto-fills `{narrative_persona}, {memory}, {skills}, {rating_scale}` and any agent-attribute `{xxx}` | Use only the 4 standard placeholders; for custom narrative, set agent attributes (e.g. `agent.water_situation_text`) in your lifecycle hook |
| 3 | Logs say `Empty/Null response received` but Ollama responds (verify via curl) | The log message conflated LLM-empty with parser-side rejection. Post-v4 the broker distinguishes: `LLM returned empty response (...)` vs `LLM responded (N chars) but parser rejected — see [Adapter:Error] diagnostic above` | If you see the second message, look at the `[Adapter:Error]` diagnostic block which shows `raw_output`, `parse_layer reached`, `expected keys`, `valid skills for this agent_type`. The diagnostic names the exact gap. |
| 4 | `[Adapter:Error]` diagnostic says LLM JSON keys don't match expected | YAML `shared.response_format.fields[].key` (e.g. `susceptibility_assessment`) must match the EXACT key the LLM emits in JSON (per your prompt example) | Sync prompt template's JSON example keys with YAML schema keys. Currently manual; v5 will auto-derive `{response_format}` from YAML to eliminate this risk. |
| 5 | `[Adapter:Error]` diagnostic shows `valid skills for this agent_type: []` | Missing `actions:` block under your agent type in `agent_types.yaml` | Add `actions:` block listing every skill ID + aliases. `skill_registry.yaml`'s `eligible_agent_types` is NOT auto-translated. See Step 3 example above. |
| 6 | `[Governance:Initial] ... missing required fields: <appraisal_key>, ...` even though LLM JSON contains those keys | Missing `parsing.constructs:` block. Parser doesn't know to extract `appraisal_key.label` → `APPRAISAL_LABEL` construct without this mapping | Add `parsing:` block with `constructs:` mapping each construct name to its JSON key + label regex. See Step 3 example above. |

If your smoke run produces 0 traces and the error doesn't match any row above, run with the in-built diagnostic by checking the `[Adapter:Error]` block in stdout. The diagnostic was added in Phase 6C-v4 (commit `bd86634`) specifically to make new-domain debugging tractable.

### One-command scaffolding (Phase 6C-v4 cycle 4, 2026-05-10)

You almost never want to hand-write the directory + YAML + DomainPack from scratch. Generate a minimal working skeleton with one command:

```bash
python -m broker.tools.scaffold_domain energy_consumer \
    --output examples/energy_demo \
    --skills "increase_use,maintain_use,decrease_use"
```

This writes 10 files (12 with `--framework custom`) that already:

- Pass `validate_prompt` clean on first run (no manual sync needed)
- Use the broker-filled `{response_format}` placeholder (no hand-rolled JSON to drift)
- Include all 6 required YAML blocks identified by the Phase 6C-v4 BLOCKER inventory
- Wire up DomainPack registration, validator registry, and a stub `run_experiment.py`

Pass `--framework custom` to also scaffold a `cognition/` package with framework-registration boilerplate (use this when your domain needs a NEW psychological model like HBM, TPB, etc.). Otherwise the default uses pre-registered PMT and skips `cognition/` entirely.

Next, edit `config/prompts/agent.txt`, the DomainPack adapter, and `run_experiment.py` to describe your specific domain. The scaffold is a starting point — not a finished example.

### Pre-flight check before first run (Phase 6C-v4 cycle 3, 2026-05-10)

Before running your first experiment, run the static validator to catch the 6 BLOCKERs at config time:

```bash
python -m broker.tools.validate_prompt examples/<your_domain>/config/agent_types.yaml
```

Exit codes:

- `0` — clean (or only WARN-level issues)
- `1` — at least one ERROR (will produce 0 valid LLM decisions if run)

The CLI checks:

1. Each agent type declares `actions:` (either top-level or nested under `parsing.actions`)
2. Every `response_format.fields[].construct` has a matching `parsing.constructs:` entry
3. Inline JSON example keys in the prompt match `response_format.fields[].key` (catches the Finding 4 typo case — `susceptibility_appraisal` vs `susceptibility_assessment`)
4. Every `{placeholder}` in the prompt is either broker-filled or YAML-declared (WARN; many domains intentionally fill custom placeholders via lifecycle hooks)
5. The `prompt_template_file` path actually resolves (handles both `yaml-dir-relative` and `example-root-relative` conventions)

To restrict checking to one agent type:

```bash
python -m broker.tools.validate_prompt agent_types.yaml --agent-type household_owner
```

Use `--strict` to fail on warnings as well as errors (useful in CI).

### Multi-agent orchestration: `from_domain()`

Multi-agent experiments use `PhaseOrchestrator` for execution ordering. The default `PhaseOrchestrator()` returns the flood-specific 4-phase template (government / insurance → household_* → resolution → observation). For non-water domains use `from_domain()`:

```python
from broker.components.orchestration.phases import PhaseOrchestrator

# Flood (or omit domain — backward-compat default)
orch = PhaseOrchestrator.from_domain("flood")

# Anything else: vaccination, traffic, energy, ...
orch = PhaseOrchestrator.from_domain("vaccination")
```

`from_domain("<any-non-flood-string>")` returns a 3-phase template with `agent_types=None` in the first phase, meaning **auto-discover all agents** regardless of `agent_type`. This is what makes a fresh non-water domain Just Work without enumerating every agent_type in YAML.

If you need fully custom phase ordering, write a phase YAML and load it via `PhaseOrchestrator.from_yaml(...)`.

### Custom social specs: `register_social_spec()`

If your domain's agents have different social graph topology than the water-domain defaults (spatial + household_* / global + government), register them at domain import time:

```python
# In examples/<your_domain>/__init__.py
from broker.components.social.config import (
    register_social_spec, SocialGraphSpec,
)

register_social_spec(
    "vaccination_individual",
    SocialGraphSpec(graph_type="spatial", radius=3),
)
register_social_spec(
    "energy_consumer",
    SocialGraphSpec(graph_type="global"),
)
```

Without registration, unknown agent types fall back to `DEFAULT_SOCIAL_SPEC` (spatial, radius=2). The fallback works but is rarely what a domain author wants — register explicitly for clarity.

### Building a multi-agent domain (Phase 6E, 2026-05-10)

The single-agent walkthrough above (`examples/vaccination_demo/`) is the easier path. Multi-agent domains (multiple agent types interacting via cross-agent state) need a few extra wiring steps — proven end-to-end by the `examples/vaccination_ma_demo/` reference (3 agent types: health_authority → community_org → individual).

**The cross-agent coupling pattern (the load-bearing one)**:

WAGF multi-agent uses an **env-dict-whitelist** pattern. There is NO direct agent-to-agent method call. Instead:

1. A lifecycle hook's `pre_year` / `post_step` writes cross-agent state to a shared `env` dict (e.g. `env["advisory_strength_label"] = "strong"`).
2. The `TieredContextBuilder` is constructed with `dynamic_whitelist=[...keys...]`. Whitelisted keys are auto-injected into EVERY agent's context.
3. Each agent's prompt template references the keys as `{placeholder}` substitutions.

This pipeline (`env → whitelist → context → template_vars → SafeFormatter`) has **zero flood-specific branching in broker/** per Phase 6E Phase 1 trace audit. The whitelist literal in your domain's `run_experiment.py` IS the abstraction point — declaring `crop_yield`, `advisory_strength`, `commute_congestion`, or any other domain-specific cross-agent variable is one-line.

**Concrete pattern (from `examples/vaccination_ma_demo/run_experiment.py`)**:

```python
from broker.components.context.tiered import TieredContextBuilder, load_prompt_templates

# Cross-agent state keys — must match keys the lifecycle hook writes
# AND placeholders the prompt templates reference
DYNAMIC_WHITELIST = [
    "year",
    "advisory_strength_label",
    "advisory_text",
    "outbreak_severity_label",
    "community_support_text",
]

ctx_builder = TieredContextBuilder(
    agents=agents,
    # hub omitted (or hub=None) for non-spatial domains — no
    # InteractionHub means no gossip / neighbor sharing
    memory_engine=memory_engine,
    yaml_path=str(CONFIG_YAML),
    dynamic_whitelist=DYNAMIC_WHITELIST,
    prompt_templates=load_prompt_templates(str(CONFIG_YAML)),
)

runner = (
    ExperimentBuilder()
    .with_agents(agents)
    .with_lifecycle_hooks(
        pre_year=hooks.pre_year,
        post_step=hooks.post_step,
        post_year=lambda year, ags: hooks.post_year(year, ags, memory_engine),
    )
    .with_context_builder(ctx_builder)
    .with_phase_order(
        [["health_authority"], ["community_org"], ["individual"]]
    )
    # ... rest of builder chain
).build()
```

**`with_phase_order([[t1], [t2], [t3]])`** — agents whose `agent_type` matches `t1` execute first; their `post_step` writes new env values; then `t2`'s context_builder reads those values before deciding. Within a phase, agents execute in the order they appear in the agent dict. This is what gives you "institutional → intermediary → citizen" cross-tier information flow.

**CRITICAL — the dual-dict gotcha (Phase 6E Finding #3)**:

When you DON'T provide a `.with_simulation(env)` engine, `ExperimentRunner` creates a fresh `env = {}` at the start of each year and passes it to your `pre_year(year, env, agents)`. If your lifecycle hook keeps its own `self.env` dict separately, **mid-year writes to `self.env` won't propagate to `ctx_builder`** because `ctx_builder` reads from the runner's `env`, not yours.

The fix is one line — alias `self.env = env` in pre_year so the two are the same dict for the rest of the year:

```python
def pre_year(self, year, env, agents):
    # First sync any persistent state we carried over from last year:
    env.update(self.env)
    # Then ALIAS self.env to runner's env — post_step writes now land
    # directly in the dict ctx_builder reads.
    self.env = env
    self.env["year"] = year
    # ... rest of pre_year
```

Flood Paper 3 doesn't hit this because it uses `.with_simulation(TieredEnvironment(...))` which returns a persistent env dict that `advance_year` mutates in place. For multi-agent domains WITHOUT a simulation engine, use the aliasing pattern above.

**Reference**: `examples/vaccination_ma_demo/` — full multi-agent reference example. `lifecycle_hooks.py:pre_year` is the canonical aliasing implementation. `.ai/ma_vaccination_findings_2026-05-10.md` documents the Phase 6E build's 3 BLOCKERs (the aliasing pattern is Finding #3).

**Skill registry schema asymmetry**: `skill_registry.yaml` uses `- skill_id: <id>` (different from `agent_types.yaml` actions block which uses `- id: <id>`). This is an artefact of WAGF's history. The `validate_prompt` CLI does not check skill_registry.yaml's schema; the broker raises `KeyError('skill_id')` at experiment-build time if you use the wrong field. Phase 6C-v4 `scaffold_domain` was patched in Phase 6E to emit the correct field; if you hand-write a skill_registry.yaml, use `skill_id:`.

## What you DO NOT have to do

- ✗ Edit `broker/components/cognitive/reflection.py` — DomainPack handles it
- ✗ Edit `broker/core/experiment_runner.py` — DomainPack handles it
- ✗ Edit `broker/components/events/ma_manager.py` — DomainPack handles it
- ✗ Edit `broker/domains/water/validator_bundles.py` — registry handles it
- ✗ Edit `broker/components/context/providers.py` — DomainPack handles it

## Reference

- `examples/irrigation_abm/` — reference implementation (water demand)
- `examples/governed_flood/` — reference implementation (flood adaptation)
- `examples/vaccination_demo/` — first non-water reference example (HBM-based, ~600 LOC)
- `broker/domains/protocol.py` — DomainPack Protocol contract
- `broker/domains/default.py` — DefaultDomainPack no-op fallback
- `broker/domains/registry.py` — DomainPackRegistry semantics
- `tests/test_domain_pack_contract.py` — regression tests; copy/paste pattern for your own pack
- `.ai/domain_pack_design_2026-05-10.md` — full architectural rationale
- `.ai/vaccination_poc_findings_2026-05-10.md` — 6-BLOCKER inventory + lessons learned (single-agent)
- `examples/vaccination_ma_demo/` — multi-agent reference example (3 agent types via env-dict-whitelist pattern)
- `.ai/ma_vaccination_findings_2026-05-10.md` — Phase 6E multi-agent BLOCKER inventory (3 findings)
- `tests/test_multi_agent_coupling.py` — integration tests covering Findings #1 and #3

## Asking for help

Open an issue at the WAGF repo with the tag `new-domain` and your example
package as a tarball. Include the smoke test output and which step failed.
