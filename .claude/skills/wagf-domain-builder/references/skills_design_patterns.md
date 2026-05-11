# Skills Design Patterns

S1 turns the user's timestep decision into 3-5 WAGF skills. The output must be a comma-separated `--skills` string for `broker.tools.scaffold_domain`.

Good skill IDs are lowercase snake_case verbs or verb phrases. Include a default or no-change option unless the domain truly has no inaction path.

## Pattern 1 - Scaling

Use scaling when the decision changes a quantity up, down, or not at all. This is the most common pattern: irrigation demand, thermostat setpoint, consumption level, application dose, or budget allocation.

Three-action form:

```text
increase, maintain, decrease
```

Five-action form:

```text
increase_large, increase_small, maintain, decrease_small, decrease_large
```

Concrete examples:

- `examples/irrigation_abm/`: `increase_large`, `increase_small`, `maintain_demand`, `decrease_small`, `decrease_large`.
- Vaccination dose-count variant: `increase_doses`, `maintain_schedule`, `decrease_doses` if the agent controls dose count rather than yes/no adoption.
- Energy thermostat variant: `raise_setpoint`, `maintain_setpoint`, `lower_setpoint`.

Map to scaffolder:

```bash
python -m broker.tools.scaffold_domain irrigation \
  --output examples/irrigation_demo \
  --skills "increase_large,increase_small,maintain_demand,decrease_small,decrease_large"
```

Choose 3 actions when direction is the research signal and magnitude is incidental. Choose 5 only when the difference between large and small changes matters for the hypothesis, validators, or external model.

Anti-patterns:

- Binary `{increase, decrease}` with no maintain action; the LLM has no stable default and may oscillate.
- Very similar names such as `increase_more` and `increase_much`; small LLMs confuse near-synonyms.
- Encoding numbers in skill IDs such as `increase_8_percent`; put magnitudes in descriptions, validators, or a hierarchical parameter.

## Pattern 2 - Categorical

Use categorical skills when options are discrete and unordered. The agent is choosing between qualitatively different actions, not moving along a numeric scale.

Concrete examples:

- `examples/vaccination_demo/`: `get_vaccinated`, `delay`, `refuse`.
- `examples/governed_flood/`: `do_nothing`, `buy_insurance`, `elevate_house`, `relocate`.
- Transit mode choice: `drive`, `take_transit`, `bike`, `walk`.

Map to scaffolder:

```bash
python -m broker.tools.scaffold_domain vaccination \
  --output examples/vaccination_demo \
  --skills "get_vaccinated,delay,refuse" \
  --framework custom
```

Keep categorical spaces under 6 choices until parsing quality has been verified. Small local models degrade once the prompt asks them to distinguish too many options with similar consequences.

Anti-patterns:

- More than 6 options in the first scaffold; collapse rare choices into an "other" baseline until the parser is proven stable.
- Action names that mix decision and rationale, such as `refuse_because_low_risk`; rationale belongs in reasoning fields.
- Options that are not mutually exclusive, such as `buy_insurance` and `ask_for_grant`, unless the timestep truly requires choosing only one.

## Pattern 3 - Hierarchical

Use hierarchical skills when the agent must choose a primary action and a continuous or ordinal magnitude. This is rare in first-domain builds because it adds YAML schema, parser, and validator surface area.

Concrete examples:

- Irrigation agent chooses `adjust_demand` plus `magnitude_pct`.
- Energy agent chooses `shift_load` plus `shift_hours`.
- Crop agent chooses `apply_fertilizer` plus `kg_per_ha`.

Map to scaffolder:

```bash
python -m broker.tools.scaffold_domain irrigation \
  --output examples/irrigation_demo \
  --skills "increase_demand,maintain_demand,decrease_demand"
```

Then add a `secondary_choice` field in `config/agent_types.yaml`, such as `magnitude_pct`, and validate it in `validators/<domain>_validators.py`.

Use this only when the magnitude is necessary for the research question or external model. If the magnitude is just "small vs large", Pattern 1 is cheaper and more robust.

Anti-patterns:

- Asking the LLM for an unrestricted float without bounds; validators will reject or clamp too much.
- Treating magnitude as prose in `reasoning`; downstream models need a structured field.
- Adding hierarchical output before `validate_prompt` is clean for the simpler action-only scaffold.

## Shared Checks

Every S1 skill list should pass these checks:

- 3-5 skill IDs for the first build.
- Lowercase snake_case.
- One obvious default option.
- Skill names appear exactly in the prompt, `actions:`, and `skill_registry.yaml`.
- Extreme or irreversible actions are named clearly enough for YAML rules to block when reasoning is incoherent.

## Decision Tree

Is your decision a quantity? Use Pattern 1.

Is your decision a discrete choice between unordered options? Use Pattern 2.

Do you need a magnitude alongside the choice? Use Pattern 3, but start with Pattern 1 if small/large bins answer the research question.

If none fits, pause S1 and restate Q2 from `domain_articulation_questions.md` until the action surface is concrete.
