# Water Agent Governance Framework Architecture

> Where things live: see [`docs/REPO_MAP.md`](docs/REPO_MAP.md).

## Overview

The Water Agent Governance Framework is a cognitive governance middleware for LLM-driven agent-based models of human-water interactions. It provides skill-based governance, memory, and reflection capabilities designed for coupled human-water simulations — including flood risk adaptation, irrigation water management, and water resource policy evaluation.

The framework's extensible architecture allows new water sub-domains to be added through configuration (YAML skill registries + domain validators) without modifying the core broker.

**Version**: v0.6.0 (semver). Pre-v0.3.0 the project used a different
internal versioning scheme; v0.29.0 → v0.3.0 (2026-05-27) was a
deliberate semver reset. See `CHANGELOG.md` for the full release
timeline.

---

## Core Design Principles

### 1. Extensible Water-Domain Core

The `broker/` directory contains **reusable components** designed for coupled human-water ABMs, extensible to new water sub-domains:

- Core governance pipeline (skill proposal → validation → execution) is domain-independent
- Water sub-domain logic (flood adaptation, irrigation management) lives in `examples/<domain>/`
- Configuration-driven behavior via YAML skill registries and validator definitions

### 2. Protocol-Based Dependency Injection

Domain-specific code can extend broker capabilities without modifying broker source:

```python
# broker/interfaces/enrichment.py - Generic Protocol
class PositionEnricher(Protocol):
    def assign_position(self, profile) -> PositionData: ...

# examples/multi_agent/environment/depth_sampler.py - Domain Implementation
class DepthSampler:  # Implicitly implements PositionEnricher
    def assign_position(self, profile) -> PositionData:
        # MA-specific flood zone assignment
        ...
```

### 3. Extensions Pattern for Domain Data

Generic data structures support domain-specific extensions:

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    agent_id: str
    family_size: int
    extensions: Dict[str, Any]  # Domain-specific data here

# Domain code adds extensions
profile.extensions["flood"] = FloodExposureData(...)
profile.extensions["trading"] = TradingPreferences(...)
```

---

## Directory Structure

This tree is regenerated from the real layout (2 levels, one-line purpose
per directory) — the previous version of this section described
`broker/components/` as nine flat files; the package was split into
subpackages some time ago and the doc was never updated.

```
broker/                          # Core governance middleware
├── agents/                      # BaseAgent + agent-state loading/protocols + the decider registry (deciders.py, PR-8) that lets one run hold rule-based, hybrid and LLM agents
├── calibration/                 # Benchmark comparison (EPI) + numeric parameter optimizer (PR-7) -- generic, no water tokens
├── components/                  # Domain-independent pipeline components, 11 subpackages
│   ├── analytics/               # Audit trace writer (audit.py), drift/feedback/observable-state tracking
│   ├── cognitive/                # Reflection engine + orchestrator, cognitive trace dataclass
│   ├── context/                  # LLM prompt/context construction (builder, providers, tiered)
│   ├── coordination/             # GameMaster/coordinator, conflict resolution, message pool
│   ├── events/                   # Environment + multi-agent event managers
│   ├── governance/                # Skill registry/retriever, validator registry, domain-validator dispatch
│   ├── memory/                    # MemoryEngine ABC + implementations, seeding, factory -- the PRODUCTION tree
│   ├── orchestration/             # Phase execution ordering, saga transaction coordinator
│   ├── prompt_templates/          # Generic memory-template contracts
│   ├── social/                    # Social graph, perception filter, social-media post/dedup
│   └── validation/                # Readiness-profile analysis (Phase 6O-C)
├── config/                       # Config schema (schema.py) + memory-policy loader
├── core/                          # Governance pipeline entrypoint: propose -> validate -> retry -> execute
│                                  #   (skill_broker_engine.py, _retry_loop.py, _advise.py, experiment_runner.py, ...)
├── coupling/                      # External-model coupling layer (adapter/contract/grid+BMI+subprocess sources)
├── domains/                       # Domain metadata registry + the `water/` domain pack (flood/irrigation PMT, utility, memory strategies, calibration's water-coupled modules -- see docs/guides/calibration_guide.md)
├── governance/                    # Rule-type dataclasses (rule_types.py) shared by the YAML rule engine
├── interfaces/                    # Protocol + dataclass definitions (enrichment, schemas, skill_types, ...)
├── memory/                        # Standalone research toolkit (persistence/checkpoint/replay) -- NOT the production tree, see below
├── modules/
│   └── survey/                    # Generic CSV/Excel survey loading + profile creation
├── simulation/                    # Simulation engine, environment state, state manager
├── tools/                         # Operator CLIs (scaffold_domain, validate_prompt, compare_audit_csv, calibrate, ...)
├── utils/                         # Config loading, LLM API utilities, logging, retry formatting, ...
└── validators/                    # AgentValidator rule engine (production path) + the five governance-framework validators

examples/                          # Domain-specific implementations (non-exhaustive; see `examples/` for the full list)
├── multi_agent/flood/             # Multi-agent flood simulation (Paper 3)
│   ├── environment/               # Flood-specific enrichers (depth_sampler.py, rcv_generator.py)
│   ├── survey/                    # MA-specific survey processing (flood_survey_loader.py, mg_classifier.py, ...)
│   └── run_unified_experiment.py
├── single_agent/                  # Single-agent flood experiments (Nature Water paper)
├── irrigation_abm/                 # Irrigation domain (CRSS agents)
├── vaccination_demo/               # Single-agent non-water reference domain
└── coupling_examples/              # Standalone coupling-archetype worked examples (archetype_c_subprocess/, ...)
```

---

## Two memory trees, and which to use

The repository contains **two separate memory packages**. They are
intentionally distinct and must not be merged:

| Path | Role | Use when |
|------|------|----------|
| `broker/components/memory/` | **Production integration.** The memory engine ABC + implementations (`HumanCentric`, window, etc.) wired into the governance pipeline. Config-driven via `agent_types.yaml → memory_config`. | You are building or running a domain experiment. New domains extend **this** tree. |
| `broker/memory/` | **Research toolkit.** Standalone persistence / checkpoint / replay utilities used by analysis scripts and reproducibility tooling. Not on the per-decision governance hot path. | You are writing offline analysis, checkpoint, or replay code. |

**Why two trees:** the production engine is optimised for the
per-decision retrieval contract (`retrieve()` returns `List[Dict]`, see
`broker/INVARIANTS.md` Invariant 1); the research toolkit is optimised
for whole-experiment serialization. Collapsing them would force one set
of code to satisfy two incompatible contracts. A new contributor
extending agent memory behaviour should almost always touch
`broker/components/memory/` only.

## External-model coupling

`broker/` never imports from `examples/` (`broker/interfaces/
enrichment.py`). External simulators couple to WAGF by implementing
`broker/interfaces/environment_protocols.py::EnvironmentProtocol` (or
its tiered/social variants) in Python. A non-Python model (R, CSV,
REST) needs a thin Python adapter that satisfies the Protocol; the
`wagf-coupling-designer` skill walks through writing that adapter.
There is no hardcoded external-API integration inside `broker/`.

---

## Extensible Design Patterns (v0.3.0+)

### 1. Protocol-Based Dependency Injection

**Problem**: broker/modules/survey/ was importing from examples/multi_agent/

**Solution**: PEP 544 Protocols define interfaces without implementation coupling.

```python
# broker/interfaces/enrichment.py
from typing import Protocol, NamedTuple

class PositionData(NamedTuple):
    zone_name: str
    base_depth_m: float
    flood_probability: float

class PositionEnricher(Protocol):
    """Protocol for position/location enrichment."""
    def assign_position(self, profile) -> PositionData: ...

# Domain implementations satisfy the protocol implicitly:

# examples/multi_agent/environment/depth_sampler.py
class DepthSampler:
    def assign_position(self, profile) -> PositionData:
        # MA-specific: flood zone based on income, prior experience
        ...

# examples/trading_sim/location_sampler.py (hypothetical)
class TradingLocationSampler:
    def assign_position(self, profile) -> PositionData:
        # Trading-specific: market region based on assets
        ...
```

**Usage**:
```python
from broker.modules.survey import initialize_agents_from_survey

# Generic (no enrichers)
profiles, stats = initialize_agents_from_survey(survey_path)

# With domain-specific enrichers
profiles, stats = initialize_agents_from_survey(
    survey_path,
    position_enricher=DepthSampler(seed=42),
    value_enricher=RCVGenerator(seed=42)
)
```

### 2. Extensions Pattern for Domain-Specific Data

**Problem**: SurveyRecord and AgentProfile contained MA-specific fields.

**Solution**: Generic base classes + domain-specific extensions.

```python
# broker/modules/survey/survey_loader.py
@dataclass
class SurveyRecord:
    """Generic survey record."""
    record_id: str
    family_size: int
    income_bracket: str
    housing_status: str
    # No flood fields - generic!

# examples/multi_agent/survey/flood_survey_loader.py
@dataclass
class FloodSurveyRecord(SurveyRecord):
    """MA-specific survey record with flood fields."""
    flood_experience: bool = False
    financial_loss: bool = False
```

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    """Generic agent profile."""
    agent_id: str
    family_size: int
    extensions: Dict[str, Any] = field(default_factory=dict)

# Domain code adds extensions:
profile.extensions["flood"] = SimpleNamespace(
    flood_zone="Zone_A",
    base_depth_m=1.5,
    flood_probability=0.25
)
```

### 3. Config-Driven Domain Logic

**Problem**: Memory tags hardcoded as "MG" → "subsidy".

**Solution**: Load tags from agent_types.yaml.

```yaml
# examples/multi_agent/ma_agent_types.yaml
household_mg:
  memory:
    retrieval_tags: ["subsidy", "vulnerability", "financial_hardship"]
    window_size: 3

household_nmg:
  memory:
    retrieval_tags: ["insurance", "elevation", "adaptation"]
    window_size: 5
```

```python
# broker/components/memory.py
def _get_relevant_tags(self, agent_type: str) -> List[str]:
    """Load retrieval tags from config (not hardcoded)."""
    cfg = load_agent_config()
    memory_config = cfg.get_memory_config(agent_type)
    return memory_config.get("retrieval_tags", ["general"])
```

### 4. Classification Generalization

**Problem**: `is_mg` field was MA-specific (Marginalized Group).

**Solution**: Generic classification fields with backward-compatible aliases.

```python
# broker/modules/survey/agent_initializer.py
@dataclass
class AgentProfile:
    # Generic classification
    is_classified: bool = False
    classification_score: int = 0
    classification_criteria: Dict[str, bool] = field(default_factory=dict)

    # Backward compatibility aliases for MA code
    @property
    def is_mg(self) -> bool:
        return self.is_classified

    @property
    def mg_score(self) -> int:
        return self.classification_score
```

---

## Component Interactions

```
┌─────────────────────────────────────────────────────────────────┐
│                        broker/ (Generic)                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐     │
│  │ SurveyLoader │───▶│AgentInitializer│───▶│ AgentProfile │     │
│  │   (generic)  │    │   (generic)   │    │  (generic)   │     │
│  └──────────────┘    └──────────────┘    └──────────────┘     │
│         │                   │                    │              │
│         │            ┌──────┴──────┐             │              │
│         │            │  Protocols  │             │              │
│         │            └──────┬──────┘             │              │
│         │                   │                    │              │
└─────────┼───────────────────┼────────────────────┼──────────────┘
          │                   │                    │
          ▼                   ▼                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                   examples/multi_agent/ (MA Domain)             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │FloodSurveyLoader│  │DepthSampler  │  │ profile.extensions│   │
│  │  (extends)     │  │(PositionEnricher)│  │   ["flood"]    │   │
│  └────────────────┘  └──────────────┘  └─────────────────┘    │
│                                                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐    │
│  │  MGClassifier  │  │ RCVGenerator │  │ MAAgentProfile  │    │
│  │(MA-specific)   │  │(ValueEnricher)│  │   (extends)     │    │
│  └────────────────┘  └──────────────┘  └─────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Configuration System

### Agent Type Configuration

```yaml
# examples/multi_agent/ma_agent_types.yaml
household_owner:
  cognitive_config:
    stimulus_key: "flood_depth_m"
    arousal_threshold: 2.0
    ema_alpha: 0.3

  memory_config:
    engine: "humancentric"
    window_size: 3
    top_k_significant: 2
    retrieval_tags: ["insurance", "elevation"]

  skills:
    - elevate
    - purchase_insurance
    - relocate
```

### Loading Configuration

```python
from broker.utils.agent_config import load_agent_config

cfg = load_agent_config()
cog = cfg.get_cognitive_config("household_owner")
mem = cfg.get_memory_config("household_owner")
```

---

## LLM call safeguard (backoff + abort-rate stop)

`broker/utils/llm_safeguard.py` is a generic, opt-in safeguard against LLM
provider failures, added for spec item 24 of the irrigation v3 case study
(audit gap F42, "no LLM backoff or abort-rate stop"). It has two independent
parts, both driven by one `global_config.llm_safeguard` block:

```yaml
global_config:
  llm_safeguard:
    enabled: true
    backoff_max_retries: 3        # positive integer, capped at 8
    backoff_initial_seconds: 2    # positive integer; delay doubles each retry
    backoff_max_seconds: 60       # positive integer; caps EACH delay (not the total)
    abort_window: 50              # positive integer; rolling count of decisions
    abort_threshold: 0.5          # fraction in (0, 1] -- 0 is rejected
```

1. **Backoff on a TRANSPORT failure only.** `wrap_llm_invoke_with_backoff`
   wraps the callable `ExperimentRunner.get_llm_invoke` returns, so every LLM
   call in the framework goes through it without any other call site
   changing. Retried: the call raising `OSError` (this includes `requests.
   exceptions.ConnectionError`), or it returning normally with
   `LLMStats.transport_error is True` (the shape `_invoke_ollama_direct` /
   `create_provider_invoke` already use for a connection failure or an HTTP
   5xx they caught internally; `create_llm_invoke`'s own closure carries that
   flag into its final `LLMStats` too, since it -- not
   `_invoke_ollama_direct` -- is what the wrapper actually wraps on the
   Ollama path every shipped domain uses). NOT retried, even though each can
   also carry `success=False`: a timeout (the inner call already waited its
   own configured timeout; the wrapper does not wait again on top of that),
   an HTTP 4xx (a persistent client-side problem), empty or thinking-only
   content (the model's own empty-content retry loop already tried), or any
   other exception such as `TypeError`. Each delay is capped at
   `backoff_max_seconds` regardless of `backoff_initial_seconds` or how many
   retries remain. Every retry is logged; if every retry fails, the wrapper
   gives up and the decision fails AT ONCE -- the format-retry loop and the
   governance retry loop (`broker/core/_retry_loop.py`) both recognise a
   spent, still-transport-failing call and stop re-prompting the same dead
   endpoint instead of paying the full backoff schedule again on every
   remaining attempt; a normal (non-transport) failure is retried by those
   loops exactly as before. Every attempt's calls and tokens are folded into
   the returned `LLMStats` (`calls`, `prompt_tokens_total`,
   `response_tokens_total` sum across attempts). The new `backoff_retries`
   field is `total_calls - stats.calls` (the final attempt's own call count):
   the calls spent on the OTHER, non-final backoff attempts, not a count of
   backoff rounds -- one round can itself cost more than one inner call,
   since `create_llm_invoke`'s own closure has its own short empty-content
   retry loop. The final attempt's own calls are excluded on purpose: they
   are already reflected in that attempt's own `retries`, so folding them
   into `backoff_retries` too would double-count them (fix round 3's
   `calls - 1` formula did exactly that whenever the final, successful
   attempt itself cost more than one raw call). `broker/core/_retry_loop.py` reads
   `backoff_retries` and calls `GovernanceAuditor.log_backoff_retry()` that
   many times, which folds into `total_extra_llm_calls` in
   `governance_summary.json` the same way `empty_content_retries` already
   does. Every domain's `governance_summary.json` gains this
   `backoff_retries` counter (0 when never triggered, including when the
   safeguard is disabled), not only a domain that enables the safeguard.

2. **Abort-rate stop, early.** `LLMAbortTracker`, owned by `SkillBrokerEngine`,
   keeps a rolling window of the last `abort_window` DECISIONS (one entry per
   `process_step` call). A decision counts as failed when the provider call
   ultimately did not succeed, or its output never parsed
   (`skill_proposal is None`, the same condition that already drives
   `GovernanceAuditor.log_parse_error()`). It aborts as soon as the failure
   COUNT in the current window reaches `ceil(abort_threshold * abort_window)`
   -- which can happen well before the window is full, catching a badly
   broken endpoint sooner than waiting for a full window would. When it fires
   it raises `LLMFailureRateAborted`, carrying `observed_rate`, `window`,
   `threshold`, `failed_count`, and `decisions_in_window` (the last of which
   can be less than `window` for an early-stop abort). `ExperimentRunner.
   _run_agents_sequential` / `_run_agents_parallel` let this exception
   through instead of converting it into another ABORTED row (the parallel
   path also calls `executor.shutdown(wait=True, cancel_futures=True)`
   first, so no queued agent starts after the abort), so `run()`'s existing
   `finally` still flushes the audit writers and JSONL traces
   (`GenericAuditWriter.finalize`) and the reproducibility manifest records
   `run_status: aborted_llm_failure_rate` with all five of those values,
   before the process exits non-zero.

Both mechanisms read the identical resolved `LLMSafeguardConfig` (via
`AgentTypeConfig.get_llm_safeguard_config()`) and are OFF by default
(`enabled: false`): `wrap_llm_invoke_with_backoff` then returns its input
UNCHANGED and `LLMAbortTracker.record` is a no-op, so a domain that never
sets this block has a byte-identical audit CSV and simulation log. Its
manifest and `governance_summary.json` are NOT untouched, though: EVERY
domain's manifest gains an `llm_safeguard` key (`enabled: false` and the
defaults, for a domain that never opts in) and EVERY domain's
`governance_summary.json` gains the `backoff_retries` counter described
above (0 when unused) -- these are unconditional, additive fields, not
something only an opted-in domain sees. `run_status` /
`llm_safeguard_abort` remain conditional on an actual abort. It is enabled
in `examples/irrigation_abm/config/agent_types.yaml` for the v3 corpus,
which also sets `audit.corrected_status_columns: true` so its audit schema
does not depend on whether any particular run happened to hit a parse
failure or an abort -- a domain that enables the safeguard without also
turning that flag on keeps whatever audit-row behavior it already had for
an unparsable decision (the safeguard does not force it on).

**For any other domain runner's `main()`:** if you enable this safeguard, wrap
your call to `runner.run(...)` in `try/finally` and move every post-run
provenance patch, manifest enrichment, and simulation-log save into the
`finally` block, letting the exception propagate afterward. `ExperimentRunner.
run()`'s own `finally` already flushes the audit writer and manifest
regardless of how the run ends, but a domain runner's OWN post-`run()` code
(anything your `main()` does after the call returns) does not run at all if
`run()` raises unless you wrap it the same way --
`examples/irrigation_abm/run_experiment.py`'s `main()` is the reference
implementation of this pattern. One consequence worth stating plainly: a
simulation log built by accumulating rows across years (as
`run_experiment.py`'s does) exists after an abort only if at least one year
fully completed before the abort fired -- an abort partway through year one
leaves nothing to save, and the `finally` block's save is a no-op, not a
bug.

**Known limit: a HUNG endpoint is much slower to abort on than a DEAD one.**
The backoff wrapper and the format/governance-loop early-break both key off
`transport_error`, which is only ever set for a connection that was refused
or reset -- never for a timeout. A HUNG server (one that accepts the
connection but never answers) times out instead, which the wrapper
deliberately never retries and which never sets `transport_error`, so the
early-break added in fix round 3 never triggers for it either; the decision
falls back to paying the full per-call timeout on every attempt, exactly as
it did before this safeguard existed. At `examples/irrigation_abm`'s own
numbers that is 3 format-retry attempts x 2 inner `create_llm_invoke`
attempts x its 120s model timeout = 12 minutes for ONE decision to give up,
so reaching that domain's 25-failure early-stop
(`ceil(abort_threshold * abort_window)` = `ceil(0.5 * 50)`) takes roughly
5 hours against a persistently HUNG endpoint, versus roughly 26 minutes
(25 decisions x the ~62s backoff-then-give-up schedule) against a
persistently DEAD one. Both eventually abort; a hung endpoint is just far
slower to.

---

## Appraisal freeze and the per-attempt audit options

Five generic, opt-in options, added for the irrigation v3 governance (WP3 of
`.research/design_specs/irrigation_v3_spec_2026-09-28.md`). Each default
reproduces the shipped behaviour, so a domain that sets none of them (flood
included) writes a byte-identical audit CSV (checked with
`broker.tools.compare_audit_csv` on flood mock runs):

```yaml
global_config:
  governance:
    appraisal_freeze: true                 # default false
    rule_id_prefix: false                  # default true
    hide_registry_backstop_reports: true   # default false
  audit:
    attempt_columns: true                  # default false
    state_columns: [key_a, key_b]          # default: none
```

1. **Appraisal freeze** (`broker/core/_appraisal_freeze.py`). Within one
   decision, every validation pass checks the proposal against each
   construct label (a reasoning key containing `_LABEL`, the parser's own
   test) as the agent FIRST STATED it in that decision, never against a
   later restatement. Why: a rule conditioned on a label the model writes
   itself can otherwise be passed on retry by rewriting the label, with no
   new information about the world. `SkillBrokerEngine.process_step` starts
   the frozen set with the labels the first PARSED attempt states (format
   retries carry no rule content) and keeps it in the decision's own
   validation context (under a private key, so the engine, shared across
   worker threads, holds no per-decision state).
   `SkillBrokerEngine._run_validators` -- the one place every validation pass
   goes through -- first adds any label the attempt states for the first
   time (a non-blank value; a label already frozen is never replaced), then
   gives the validators a copy of the proposal carrying the labels as first
   stated. So a label the first attempt omitted is recovered from the first
   attempt that states it, and relabelling still cannot pass a rule. The
   governance retries, the feasible-set probe of a retry prompt
   (`RetryMixin._probe_feasible_skills`: the "actions that pass every rule"
   line reads the same labels as the rules) and the advisory re-validations
   all read them. The attempt's own skill, magnitude, parameters and
   non-label reasoning are untouched, and the audit trail keeps the labels
   the model actually wrote (`final_labels`, `appraisal_drift`,
   `attempt_labels`). The frozen value of a label equals its `initial_labels`
   value whenever the first parsed attempt carried it non-blank; otherwise
   it is the first NON-BLANK value of that label in `attempt_labels` (a
   blank is recorded as `KEY=` and the freeze does not treat it as
   stated). With the freeze on, the engine
   refuses to start when a thinking rule reads a reasoning field that is not
   a construct label (it would silently escape the freeze), when an agent
   type enables `multi_skill` (a secondary proposal is validated outside the
   retry sequence), or when its config has no callable `items()` to check;
   `ExperimentRunner` refuses it together with `enable_cognitive_cache` (a
   cache hit re-validates a proposal from an earlier decision).
2. **`rule_id_prefix`** (`AgentValidator`). `false` drops the
   `[Rule: <id>] ` prefix from YAML identity- and thinking-rule messages, so
   a retry prompt states a rule in the words of its `message` and never
   shows an internal rule id. A YAML thinking rule may also carry a
   `suggestion:`, rendered as the retry report's "Suggestion:" line; a rule
   without one adds no metadata key.
3. **`hide_registry_backstop_reports`** (`RetryMixin._retry_report_results`).
   When an identity rule has already blocked an attempt (an off-menu answer),
   the registry's backstop results for the same skill --
   `precondition_violation` and `output_schema_violation`, which repeat the
   block in internal field names -- are left out of the retry text. They
   stay in the audit trail (`failed_rules`, `error_messages`,
   `attempt_failed_rules`).
4. **`attempt_columns`**. Adds, in step with `attempt_skills`:
   `attempt_labels` (each attempt's construct labels, `KEY=VALUE` pairs
   joined by `,`, attempts joined by `|`), `attempt_failed_rules` (the ids of
   the rules that returned an ERROR on each attempt, named exactly as
   `failed_rules` names them: the result's `rule_id`, else `Unknown`) and
   `appraisal_relabeled` (True when an attempt states a label with a value
   other than the one that label was first stated with in the decision, the
   value the freeze holds; stating a label for the first time, or leaving
   one out, is not a relabel). `failed_rules` pools every attempt;
   these keep them apart. On an `ABORTED` sentinel row all three read
   `unobserved`. Refused together with an advisory channel
   (`governance.advise` / `governance.advise_mode`), whose extra attempt the
   columns do not record.
5. **`state_columns`**. Each listed key of the decision's agent state (the
   state every validator saw) becomes a `state_<key>` column, on every row
   including an `ABORTED` sentinel; a key the state does not carry is written
   as `unobserved`. Irrigation logs its supply rule's inputs this way, so an
   arm that does not run the rule can be scored post hoc on exactly the
   numbers the live rule reads.

Every manifest also gains `appraisal_freeze_resolved`,
`rule_id_prefix_resolved`, `thinking_rules_resolved`,
`identity_rules_resolved` and `custom_validators_resolved` (additive keys,
like `llm_safeguard`). Tested in `broker/tests/test_appraisal_freeze.py`
(generic) and `examples/irrigation_abm/tests/test_v3_governance.py`
(irrigation, end to end).

---

## Retry-text, dashboard and reflection options

Four more generic, opt-in options, added for the irrigation v3 prompt (WP4 of
`.research/design_specs/irrigation_v3_spec_2026-09-28.md`). Each default
reproduces the shipped behaviour; on flood mock runs the audit CSVs compare
IDENTICAL and the raw traces, prompts included, are unchanged:

```yaml
global_config:
  governance:
    plain_action_names: true                          # default false
    placebo_closer: "Please reconsider your decision."  # default: the adapter's closer
  reflection:
    keep_latest_only: true                            # default false
<agent_type>:
  feedback:
    show_trend: false                                 # default true
    tracked_metrics:
      - { name: flag, source: flag, display: false }  # default true
```

1. **`plain_action_names`** (`RetryMixin._governance_retry_loop`). A retry
   report names the blocked action as the feasible-action line does, the
   skill id with spaces ("increase demand"), not the raw id. Retry text only.
2. **`placebo_closer`** (`render_intervention_prompt`). The closing sentence
   of a `retry_feedback_mode: placebo` retry; the shipped closer refers to
   "the violations above", which a placebo prompt does not show.
3. **`keep_latest_only`** (`broker/components/cognitive/reflection.py
   (store_reflection_memory)`, `HumanCentricMemoryEngine.remove_by_type`).
   Storing a reflection first removes the agent's earlier memories of the
   same `type`, from working and long-term memory. Later memories keep the
   timestamps they would have had without the removal, so decay ages do not
   shift. An engine without `remove_by_type` raises. A domain runner that
   skips storing a new reflection (the irrigation runner drops empty
   summaries, summaries with a figure foreign to the agent's memory, and
   unreadable or failed replies) calls `remove_by_type` itself, so the
   agent keeps no reflection older than the latest round.
4. **`show_trend`** and a metric's **`display`** (`FeedbackDashboardProvider`).
   `show_trend: false` drops the TREND line; `display: false` keeps a tracked
   metric out of the table and the trend line but usable in assertions (for
   example a 0/1 flag that selects a warning's wording).

Two text changes have no switch; each changes a prompt only in a run that
reaches it, and neither was reached by the flood mock runs checked above:

- The empty feasible-set line (`RetryMixin._format_feasible_line`) names the
  cause when the attempt failed the response-format check (a required field
  left out): that check fails for every action the probe tries, so "No action
  passes every rule this step" would otherwise read as if the rules ruled out
  every action. Other empty sets render as before. A run whose model leaves
  out a required field sees the new wording, in any domain.
- `generate_batch_reflection_prompt` says "1 agent" for a one-agent batch,
  where it said "1 agents". `examples/governed_flood` reaches it whenever a
  year's reflection candidates leave one agent in the last batch (a candidate
  count one more than a multiple of its `batch_size`, 10 in its config), so such a
  flood run's reflection prompt differs by that one letter.

A placebo retry through an adapter without `format_intervention_prompt`
raises when `placebo_closer` is set, since that adapter cannot render a
closer. Tested in `broker/tests/test_wp4_framework_options.py` (generic) and
`examples/irrigation_abm/tests/test_v3_prompt.py` (irrigation, end to end).

---

## Migration Guide

For release-to-release migration notes see `CHANGELOG.md`. Notable
historical migrations:

- **Unreleased**: `initial_proposal_columns` (opt-in via
  `global_config.audit.initial_proposal_columns`, default OFF) adds three
  key-gated audit CSV columns, `initial_skill`, `initial_labels`, and
  `attempt_skills`, recording the agent's FIRST proposal before any
  governance retry. `SkillBrokerEngine.process_step`
  (`broker/core/skill_broker_engine.py`) snapshots the attempt-0 proposal
  before `RetryMixin._governance_retry_loop` (`broker/core/_retry_loop.py`)
  reassigns `skill_proposal` on each retry, so the existing `proposed_skill`
  column already records only the LAST attempt; these columns restore the
  proposal-stage value so first-attempt and last-proposal analyses can be
  told apart. Same byte-identity discipline as the v0.6.0 EXECUTED-stage
  columns below: flag-OFF emits no key, so frozen baselines are unaffected.
  Tested in `broker/tests/test_initial_proposal_columns_p0_1a.py`.
- **v0.6.0 (2026-06-10)**: Phase 6V environment-coupling layer
  (`broker/coupling/`: contract + adapter + BMI hosting + ContinuousBundle;
  three worked examples incl. multi-agent period-end settlement and
  reservoir continuous control) + audit schema "2" (`.schema.json`
  sidecars, JSONL=truth) + opt-in EXECUTED-stage audit columns +
  Invariant 6 run-integrity + the INVARIANTS.md accepted-risks ledger.
  All coupling default-OFF; frozen v21 / paper-3 byte-identity preserved.
- **v0.5.1 (2026-05-28)**: SocialMediaProvider live-wire (Phase 6T-E.B)
  + cross-channel dedup + Y1 fix (Phase 6T-G) — opt-in via
  `global_config.social_feeds.enable` (default `false`). Paper-3
  v21 byte-identity preserved.
- **v0.4.0 (2026-05-28)**: Phase 6U identifier-generalization series
  complete (broker/ generic namespace has zero domain-flavored
  identifiers; PMT/utility/financial/narrative_diffusion metadata
  moved to `broker/validators/governance/frameworks/`).
- **v0.3.0 (2026-05-27)**: Phase 6T interface opening (Post,
  FollowerNetwork, InstitutionalLifecycleHandler, PerceptionPack
  social-media hooks) + silent-failure F1-F5 superset. Semver reset
  (v0.29.0 → v0.3.0).
- **Pre-v0.3.0 (legacy v0.28 → v0.29)**:
  1. SurveyRecord no longer has flood fields → use FloodSurveyRecord.
  2. AgentProfile uses extensions dict → access via
     `profile.extensions["flood"]`.
  3. Enrichers use Protocol pattern → pass domain-specific enrichers
     explicitly. (Original migration guide:
     `.tasks/handoff/task-029-migration-guide.md`.)

---

## Future Development

### Adding a New Water Sub-Domain

1. Create `examples/<new_water_domain>/` directory
2. Define skill registry YAML (e.g., `skill_registry.yaml` with domain-specific actions)
3. Implement domain validators (physical constraints, behavioral rules)
4. Implement domain environment (state transitions, feedback mechanisms)
5. Create domain-specific `agent_types.yaml` with prompt templates
6. Use broker/ components (ExperimentBuilder, SkillBrokerEngine, memory engines)

**Current water domains**:
- `examples/single_agent/` — Flood household adaptation (100 agents, PMT-based decisions)
- `examples/multi_agent/irrigation_abm/` — Irrigation water management (78 CRSS agents)

---

## Reflection Module

The reflection engine at `broker/components/cognitive/reflection.py` performs
year-end consolidation of agent memories into structured insights. It operates
on a multi-modal trigger model, a YAML-driven question taxonomy, and a
domain-adapter protocol for cross-domain portability.

### Trigger modes (`agent_types.yaml → global_config.reflection.triggers`)

| Mode                    | Fires when                                       |
|-------------------------|--------------------------------------------------|
| `crisis`                | Domain-salient event occurs (e.g., flood year)  |
| `periodic_interval`     | Every K years regardless of events               |
| `decision_types`        | Agent just executed one of the listed skills    |
| `institutional_threshold` | Policy metric change exceeds the threshold    |

### Question categories

Three **present-moment** question classes are specified per `agent_type` in
the YAML:

1. **Risk salience** — what risks feel most urgent now
2. **Social comparison** — have neighbours' choices influenced thinking
3. **Value trade-off** — cost-vs-safety balance

The framework reserves a fourth **temporal-coherence** question class,
conditionally injected when sequence-level rules (M1/M2/M3 — see
`broker/components/governance/temporal_rules/`) trigger. Temporal questions
are specified in `agent_types.yaml` under `reflection.temporal_questions`;
live injection is deferred to follow-up work.

### Domain adapter (`DomainReflectionAdapter`)

Defined at `broker/components/cognitive/adapters.py`. Concrete adapter for
flood at `examples/single_agent/adapters/flood_adapter.py`. New domains plug
in by implementing `compute_importance()` and `classify_emotion()` callbacks;
framework code is never domain-specific.

### Full design specification

The complete reflection taxonomy, V2 temporal extension path, edge-case
handling, and cross-domain integration guidelines are documented in
`.ai/reflection_taxonomy_design_2026-04-19.md`.

---

## Related Documents

- [Reflection Taxonomy Design](.ai/reflection_taxonomy_design_2026-04-19.md) — current + V2 extension spec
- [Framework Invariants](broker/INVARIANTS.md) — architectural contracts
- [Task-029 Migration Guide](.tasks/handoff/task-029-migration-guide.md)
- [Task-029 Audit Report](.tasks/handoff/task-029-audit-report.md)
- [MA Experiment Guide](examples/multi_agent/README.md)
- [Mixed Populations](docs/guides/mixed_populations.md) — declaring rule-based, hybrid and LLM deciders per agent type, and how to read the resulting audit rows
