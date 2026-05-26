# Edit-Pass Checklist

S5 makes four surgical edits to the scaffolded skeleton. After each edit, run the same static validator and stop if it is not clean.

Run from `examples/<domain>_demo/` unless the command shows a repo-root path.

```bash
python -m broker.tools.validate_prompt config/agent_types.yaml
```

Clean output starts with `OK:` and ends with `agent type(s) clean`. Any `ERROR` means the next edit waits.

## Edit 1 - Prompt Template

File: `config/prompts/<agent_type>.txt`.

Replace the generic situation narrative with the domain-specific decision context. Keep `{narrative_persona}`, `{memory}`, `{skills}`, `{rating_scale}`, and `{response_format}` unchanged; the broker fills them. Add custom placeholders only if your lifecycle hook or DomainPack supplies them.

```text
It is time to consider your annual vaccination decision.
Available actions: {skills}
{response_format}
```

Validate:

```bash
python -m broker.tools.validate_prompt config/agent_types.yaml
```

Expected clean output:

```text
OK: config/agent_types.yaml - 1 agent type(s) clean
```

Common pitfall: hand-writing a JSON example instead of using `{response_format}`. That recreates the Finding 4 typo bug where prompt keys drift from `response_format.fields[].key`.

## Edit 2 - DomainPack

File: `adapters/<domain>_pack.py`.

Override `name`, `reflection_status_text`, and `importance_profiles` at minimum. Add `compute_importance`, `classify_emotion`, `event_handlers`, or `extreme_actions` only when the domain needs them for the first smoke.

**Phase 6Q-G (2026-05-26) registration contract**: if your domain depends on the water psychometric frameworks (`pmt` / `cognitive_appraisal` / `utility` / `financial`) — i.e. your `psychological_framework: …` YAML field is one of those — you MUST add `import broker.domains.water  # noqa: F401` to your `examples/<domain>/__init__.py` BEFORE `DomainPackRegistry.register(...)`. Auto-discovery in `broker/domains/__init__.py` was removed in 6Q-G; consumers now declare their dependency explicitly. See `examples/governed_flood/__init__.py` for the reference pattern. If your domain registers its own framework (like vaccination_demo's HBM) you do NOT need the water import.

```python
@property
def name(self) -> str:
    return "vaccination"
```

```python
def importance_profiles(self):
    return {"outbreak": 0.95, "stable_year": 0.45}
```

Validate:

```bash
python -m broker.tools.validate_prompt config/agent_types.yaml
```

Expected clean output:

```text
OK: config/agent_types.yaml - 1 agent type(s) clean
```

Common pitfall: forgetting to override `name`. The DomainPack registry then reports `default` or the wrong domain, and the run falls back to generic behavior.

## Edit 3 - Validators

File: `validators/<domain>_validators.py`.

Replace the placeholder check with 2-3 real physical, personal, social, semantic, temporal, or behavioural checks. Do not register thinking checks in Python; thinking-level coherence belongs in YAML `thinking_rules:` (NOT `rules:` — the broker's `get_thinking_rules()` at `broker/utils/agent_config.py:859` recognises only `thinking_rules` or `coherence_rules`).

```python
def no_recent_revaccination(skill_proposal, context):
    if skill_proposal.skill_id != "get_vaccinated":
        return True, None
```

```python
return False, ValidationReport(
    check_id="no_recent_revaccination", severity=ValidationSeverity.ERROR
)
```

Each check returns `(passed: bool, report: ValidationReport | None)`. Use Python validators for physical or state feasibility, not for cognitive-theory consistency.

Validate:

```bash
python -m broker.tools.validate_prompt config/agent_types.yaml
```

Expected clean output:

```text
OK: config/agent_types.yaml - 1 agent type(s) clean
```

Common pitfall: registering slot `thinking` in Python. The valid Python slots are `physical`, `personal`, `social`, `semantic`, `temporal`, and `behavioural` only; Phase 6C-v4 Finding 1 came from putting thinking checks in the registry.

## Edit 4 - YAML Thinking Rules

File: `config/agent_types.yaml`.

Add 1-2 coherence rules under the agent type's `thinking_rules:` block (NOT `rules:` — Phase 6N-C 2026-05-23 finding: the broker's `get_thinking_rules()` loader at `broker/utils/agent_config.py:859` only recognises `thinking_rules` or `coherence_rules`; a `rules:` block is silently ignored). Tie each rule to framework constructs, and use `ERROR` for behavior you want governance to block. Use `WARNING` only for audit notes; small LLMs show about 0% behavior effect from warnings per `MEMORY.md`.

Each condition must use the **canonical short shape** `{ construct: X, values: [...] }` (Phase 6N-E 2026-05-24 finding: the verbose `RuleCondition`-flavoured shape `{ type: construct, field: X, operator: "in", values: [...] }` is silently treated as dead config by `agent_validator.py::_run_rule_set` because `cond.get("construct")` returns None for that shape; the post-Phase-6N-E defensive evaluator falls back to `cond.get("field")` but new YAML should use the canonical short shape):

```yaml
thinking_rules:
  - id: high_susceptibility_high_severity_high_efficacy_no_refuse
    level: ERROR
    blocked_skills: [refuse]
    conditions:
      - { construct: SUSCEPTIBILITY_LABEL, values: ["H", "VH"] }
      - { construct: SEVERITY_LABEL,       values: ["H", "VH"] }
      - { construct: SELF_EFFICACY_LABEL,  values: ["H", "VH"] }
    message: "High susceptibility + high severity + high self-efficacy should not lead to refusal."
```

Validate:

```bash
python -m broker.tools.validate_prompt config/agent_types.yaml
```

Expected clean output:

```text
OK: config/agent_types.yaml - 1 agent type(s) clean
```

Common pitfall: writing prescriptive rules that leave the agent no plausible action. Governance should block incoherent reasoning, not force the research result.

## Post-Edit Smoke

After all four config edits have clean validator output AND edit 5 has rewritten the scaffolded TODO `run_experiment.py` into a working ExperimentBuilder entry point (use `examples/vaccination_demo/run_experiment.py` as reference), run the mock smoke from the repo root:

```bash
python examples/<domain>_demo/run_experiment.py \
    --model gemma3:4b --years 2 --agents 3 \
    --seed 42 --output results/smoke_42
```

The explicit `--seed 42 --output results/smoke_42` flags make the run reproducible and put the audit CSV at the same path the verify-done check (`stage_outputs.md` S6 row) expects. Without these, the audit lands in `results/smoke/` and seed-based reproducibility is lost.

Verify the audit CSV at `results/smoke_42/individual_governance_audit.csv` has `years * agents` rows, no `[Adapter:Error]` blocks appeared in stdout, and every `proposed_skill` is one of the declared skill IDs.
