# Governance pipeline: one decision, end to end

Every agent decision in WAGF flows through `SkillBrokerEngine.process_step()` in `broker/core/skill_broker_engine.py` — the orchestrator of the three-layer architecture (LLM Agent → Governed Broker → Simulation/World). The engine is assembled from three mixins in the same package: `RetryMixin` (`broker/core/_retry_loop.py`), `AuditMixin` (`broker/core/_audit_helpers.py`), and `SkillFilterMixin` (`broker/core/_skill_filtering.py`). The contract is strict: the broker builds context and validates, the LLM decides, and only the simulation engine mutates state. This page is the orientation summary; for design depth see [ARCHITECTURE.md](../../ARCHITECTURE.md) and for the binding rules the broker must never break, [broker/INVARIANTS.md](../../broker/INVARIANTS.md).

## Stage by stage

### 1. Bounded context (read-only)

`process_step()` calls `self.context_builder.build(agent_id, ...)`, injects the agent-type-filtered skill list (`SkillFilterMixin._inject_filtered_skills`), and hashes the context for the audit trail. When a non-window memory engine is active, `SkillRetriever` (`broker/components/governance/retriever.py`) performs RAG-style skill retrieval — narrowing `context["available_skills"]` to the top-N relevant skills (defaults `top_n=3`, `min_score=0.05`, overridable via the DomainPack/YAML retrieval policy).

### 2. LLM proposal and parse retries

The formatted prompt goes to the caller-supplied `llm_invoke`; raw output is parsed by `ModelAdapter.parse_output()` into a `SkillProposal` (`broker/interfaces/skill_types.py`) — an abstract skill name plus reasoning constructs, optional `magnitude_pct`, and optional multi-field `parameters`. Malformed output triggers the **format/parse retry loop**, `RetryMixin._invoke_llm_with_retries` (up to 2 extra attempts, with `ModelAdapter.format_retry_prompt` feedback). Still unparsable → the step returns `SkillOutcome.ABORTED`. This loop is distinct from the governance retry loop below: it fixes broken JSON, not rejected decisions.

### 3. Validation (feasibility, legality, theory)

`SkillBrokerEngine._run_validators()` runs, in order: the configured `AgentValidator` list (`broker/validators/agent/agent_validator.py`), any `custom_validators` callables, an opt-in registry dispatch of domain PHYSICAL checks (`domain_physical_dispatch`, default OFF, via `ValidatorRegistry` + `PhysicalValidator`), and two registry-level checks on `SkillRegistry` — `validate_output_schema()` and `check_preconditions()`. The engine docstring maps this onto a six-step sequence: schema validation, action legality, physical feasibility, institutional compliance, magnitude plausibility, and theory consistency. Steps 1–4 and 6 are **binding** (rejection); step 5 (magnitude) is **advisory** — out-of-range magnitudes are corrected at execution time by bounded resampling, not rejected.

The rule vocabulary lives in `broker/governance/rule_types.py`: `RuleCategory` (personal / social / thinking / physical / semantic), `RuleLevel` (`ERROR` blocks and forces retry; `WARNING` only logs), and YAML-driven `GovernanceRule`/`RuleCondition` (construct, precondition, expression, social condition types). Category-specific validators — `PersonalValidator`, `SocialValidator`, `ThinkingValidator` (behavioral-theory / PMT construct coherence), `PhysicalValidator`, `SemanticGroundingValidator` — live in `broker/validators/governance/`; per-agent-type skill eligibility is `TypeValidator` (`broker/governance/type_validator.py`). All are domain-agnostic; domains inject constructs, skill IDs, and thresholds via YAML (see the broker package map and `examples/`).

### 4. Retry with feedback

On a binding failure, `RetryMixin._governance_retry_loop` re-invokes the LLM up to `max_retries` times (default 3, config-overridable). Each failed `ValidationResult` becomes an `InterventionReport` (rule id, blocked skill, violation summary, suggested correction) that `ModelAdapter.format_retry_prompt` folds into the retry prompt — this is the "explainable governance" seam. An **early-exit** fires when the identical blocking-rule set recurs on consecutive attempts *and* every blocker is flagged deterministic (e.g. affordability from static income — retrying is futile); construct-based rules never early-exit because revised LLM reasoning may pass.

### 5. Approval or fallback

`_build_approved_skill()` produces an `ApprovedSkill` and an outcome: `APPROVED` (first pass) or `RETRY_SUCCESS`; on exhaustion, `REJECTED` (the blocked proposal is recorded) or `UNCERTAIN`/`REJECTED_FALLBACK` (parse-level failure, registry default skill substituted). A rejected proposal's magnitude and setpoint parameters are cleared so live values never leak into the fallback.

### 6. Execution (system-only)

Only `self.simulation_engine.execute_skill(approved_skill)` mutates state. On `REJECTED`/`UNCERTAIN` the engine executes `SkillRegistry.get_default_skill()` as fallback instead (status `REJECTED_FALLBACK`) so agent state is still recalculated and the simulation always advances. If multi-skill is enabled for the agent type, a validated secondary skill executes sequentially after a successful primary (composite-conflict checked via `SkillRegistry.check_composite_conflicts`).

### 7. Audit trace

`AuditMixin._write_audit_trace` hands one complete record to the `GenericAuditWriter` (`broker/components/analytics/audit.py`): prompt + raw LLM output, context hash, memory before/after, the full validation history (including advisory warnings, so reviewers can distinguish binding from advisory), retry and format-retry counts, and a decision-source classification (`llm_reasoned` / `validator_rejected` / `fallback_default` / `parse_failure`). Outputs per run: `raw/{agent_type}_traces.jsonl`, `{agent_type}_governance_audit.csv`, `audit_summary.json`, and `validator_health.csv` (+ per-agent-type variant) with rule fire/warn/error-path counts — the primary dataset for governance analyses (see [DATA.md](../../DATA.md)).

## Where to change what

- **Add or tune a governance rule** — YAML rule definitions consumed via `GovernanceRule.from_dict` (`broker/governance/rule_types.py`); per-domain rule files live with the domain configs under `examples/` and `broker/domains/`.
- **New validator category / domain checks** — subclass `BaseValidator` in `broker/validators/governance/`, or register PHYSICAL checks in `broker/components/governance/validator_registry.py`.
- **Retry policy** — `max_retries` and max intervention reports come from the agent config (`get_governance_retries` / `get_governance_max_reports`); the loop itself is `broker/core/_retry_loop.py`.
- **Hard boundaries you must not cross** (broker never decides, never mutates state; execution is simulation-only) — [broker/INVARIANTS.md](../../broker/INVARIANTS.md).
