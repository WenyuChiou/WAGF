# Domain Articulation Questions

Ask these in order during S0 and write the answers to `.research/<domain>_brief.md`. Do not scaffold until every answer is present.

## Q1. "What's your research domain?"

Why: the domain name becomes the package name, output directory, YAML domain key, and DomainPack registry key.

Use: normalize to 1-2 words in lowercase snake_case, such as `vaccination` or `energy_use`.

Example answer: `vaccination` - individuals decide whether to take a seasonal vaccine.

## Q2. "What decision does one agent make each timestep?"

Why: WAGF skills are actions, so the decision statement is the root of S1.

Use: convert the verb phrase into 3-5 skill IDs in `skills_design_patterns.md`.

Example answer: "Each individual chooses whether to get vaccinated, delay, or refuse this year."

## Q3. "What is one timestep in your model?"

Why: prompt wording, memory cadence, external-model sync, and smoke-run row counts depend on cadence.

Use: record one of `year`, `month`, `day`, or `decision_point_triggered`; if event-triggered, name the trigger.

Example answer: `year` - the vaccination agent makes one seasonal decision per simulated year.

## Q4. "Is there an external model involved?"

Why: this branches the workflow into the coupling path or the no-coupling path.

Use: if yes, hand off to `.claude/skills/wagf-coupling-designer/SKILL.md` at S2 and S3; if no, skip straight from S1 to S4.

Example answer: "No external model for the first build; outbreak severity is generated inside `run_experiment.py`."

## Q5. "Which cognitive framework should govern the agent's reasoning?"

Why: the framework determines appraisal constructs, YAML rules, and any custom registration required before smoke testing.

Use: choose from `pmt`, `utility`, `financial`, `hbm`, `tpb`, or `custom`; use `cognitive_framework_chooser.md` before finalizing.

Example answer: "HBM fits because vaccination is a health-behavior decision; use `--framework custom` and register HBM-style constructs."

## Q6. "Is this single-agent or multi-agent?"

Why: this skill is v1 single-agent only; multi-agent needs a different orchestration design.

Use: if the user says multi-agent, say: "Multi-agent domain building is deferred to v2. We can build the single-agent version first, or stop here and capture the multi-agent requirements."

Example answer: "Single-agent for now; each individual acts independently with a shared outbreak signal."

## Q7. "Do you already have a baseline or counterfactual?"

Why: baselines shape the later experiment matrix but should not block the first domain scaffold.

Use: record whether they have FQL, expert heuristic, observational data, or no baseline yet; hand this to `.claude/skills/wagf-experiment-designer/SKILL.md` after S6.

Example answer: "Use an expert heuristic baseline: vaccinate during outbreak years, delay otherwise."

## Q8. "What would convince you the first smoke run is useful?"

Why: a first domain is not a paper result; it needs a narrow success check that audit traces are meaningful.

Use: define a concrete S6 check beyond "script runs", such as non-empty audit CSV, declared skill IDs only, and at least one governance rejection if validators should fire.

Example answer: "For 3 agents over 2 years, I expect 6 audit rows, no `[Adapter:Error]` blocks, and at least one refusal blocked when susceptibility and self-efficacy are both high."
