---
name: wagf-quickstart
description: First-time WAGF setup walkthrough — environment check, smoke test, first experiment, and handoff to the lifecycle skills. Use when the user says "I just cloned WAGF", "set up WAGF", "first WAGF run", "I'm new to this", "where do I start with WAGF", or opens a Claude Code session in a freshly-cloned WAGF repo without a clear task.
---

# WAGF Quickstart — First-Time Setup

The single entry-point skill for a researcher who just cloned this
repo and wants to be productive within ~40 minutes. This skill itself
does very little; it orchestrates four phases and hands off to the
existing lifecycle skills at the right moments.

Researcher progress is tracked in `.wagf-quickstart-status.json` so a
returning user resumes from the last completed phase rather than
starting over.

## When to Use

Load this skill the moment a user opens a session in a WAGF repo and
says any of:

- "I just cloned WAGF, help me set this up."
- "Set up WAGF."
- "First WAGF run."
- "I'm new to this — where do I start?"
- "Help me get WAGF working."

Also load this skill PROACTIVELY when:

- The session opens in a directory containing `broker/INVARIANTS.md`
  AND no `.research/` folder AND no `.wagf-quickstart-status.json` —
  this signals a fresh clone with no work done yet.

Do NOT use this skill for:

- An experienced WAGF user who knows what they want → load the
  matching lifecycle skill directly (`wagf-experiment-designer`,
  `llm-agent-audit-trace-analyzer`, `wagf-verification-ladder`,
  `model-coupling-contract-checker`, `abm-reproducibility-checker`).
- Generic "how do I run a Python project" questions → defer to
  whatever the user actually wants.

## The four-phase workflow

Each phase has an entry condition, a runnable artefact, and a clear
hand-off rule. Skip nothing; refuse to advance if the prior phase did
not produce its expected output.

### Phase 1 — Environment check (~3 min)

**Goal**: confirm the user can run any WAGF script at all.

**Run**:

```bash
python .claude/skills/wagf-quickstart/scripts/check_env.py
```

**What it validates**:
- Python ≥ 3.10
- `pip install -r requirements.txt` resolves (probe-mode; doesn't
  install)
- Ollama daemon is reachable at `http://localhost:11434`
- At least one supported model is pulled. `gemma3:4b` is the
  recommended onboarding model (small enough to run on a CPU laptop
  in a pinch, large enough to produce sensible WAGF behaviour).

**Outputs**:
- Verdict: GREEN / YELLOW / RED.
- Numbered remediation list if YELLOW or RED (e.g.,
  "1. Install Ollama: https://ollama.com/download");
  "2. Run: ollama pull gemma3:4b").
- Records phase-1 status to `.wagf-quickstart-status.json`.

**Refuse to advance** if RED. Show the remediation list and wait for
the user to fix. One exception: the Ollama and model checks matter only
from Phase 3 on (Phase 2 runs on the built-in mock), so if Python and the
imports are fine and only Ollama or the model is missing, Phase 2 may run
first.

### Phase 2 — First run: a block and a repair (~2 min)

**Goal**: show the user, on a runnable example, one blocked attempt with
its reason, the repaired answer, and the change in the toy model's state.

This is the same first step the front-page `README.md` gives. It uses the
built-in mock, so it needs no Ollama and no model download.

**Run** (the user picks a fresh `--output` directory each time):

```bash
python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4 --seed 42 --output .tmp/readme-reservoir
```

**What to show the user after the run**: the summary the script prints
under `Block and repair in this run:`

- `attempt 1  BLOCKED:` the dead-pool rule's reason (year 3);
- `attempt 2  APPROVED:` the repaired answer (50% of demand);
- `executed` the toy reservoir's release target before and after;
- `effect` storage before and after, against the dead pool.

Then point to `<output>/operator_governance_audit.csv` (year 3 row:
`status` APPROVED, `retry_count` 1, `failed_rules` `dead_pool_violation`)
and `<output>/raw/operator_traces.jsonl` (full reason and executed change).
The answers are scripted: say plainly that this shows the loop, not a result.

**Optional second step**: the two paper cases in the README (flood, then
irrigation), same mock, fresh output directories.

**Refuse to advance** if the run crashes, the summary is missing, or
`operator_governance_audit.csv` is missing or empty. Inspect stdout for the
actual error and recommend the fix from `references/troubleshooting.md`.

**Record** phase-2 status with the output directory, so Phase 4's
analyser can find it later.

### Phase 3 — First real experiment (~30 min planning + multi-hour run)

**Goal**: turn the user's research question into a runnable matrix.

**This phase is delegated** to the
`wagf-experiment-designer` skill. Do NOT replicate its workflow
here. Instead:

1. Ask the user (in plain language): "What question do you want to
   answer with WAGF? E.g., 'Does governance reduce hallucinated
   actions in flood adaptation?'"
2. Pre-fill defaults appropriate for a first-time user:
   - **Domain**: irrigation or flood (ask).
   - **Models**: 1 model, default `gemma3:4b` (already pulled in
     Phase 1).
   - **Conditions**: `[strict, disabled]`.
   - **Seeds**: 3 (smallest useful median and range; bump to 5 later).
   - **Time horizon**: domain default (irrigation 42 yr, flood 10 yr).
   - **Social-media propagation** (v0.5.1+, opt-in): OFF by default
     and recommended OFF for first runs. Researchers studying
     narrative diffusion or social-influence effects can enable it
     later via the two-layer flag (`global_config.social_feeds.enable`
     in YAML AND the DomainPack `social_feeds_default_enabled()`
     hook). When OFF, runs are byte-identical to pre-v0.5.1 output.
     Reference implementation: `broker/components/context/providers.py`.
3. Hand off explicitly: "Now loading
   `wagf-experiment-designer` with these defaults — confirm or
   override."
4. After the matrix is written, `wagf-experiment-designer` produces
   `.research/wagf_experiment_matrix.yml`,
   `.research/metrics_plan.md`, and `.research/run_plan.md`. The
   researcher then runs the bat in `run_plan.md`.

**Refuse to advance** if the user has not chosen a domain or has not
provided a research question (even one sentence).

**Record** phase-3 status with the `.research/` artefact paths.

### Phase 4 — First analysis (~5 min after run completes)

**Goal**: turn the run output into paper-ready governance metrics.

**This phase is delegated** to the
`llm-agent-audit-trace-analyzer` skill.

1. Wait for `simulation_log.csv` to appear in the run output dir
   (the user runs the bat themselves; this skill does not babysit
   the LLM run).
2. When the user returns and says "the run is done" or "analyse the
   results", hand off: "Now loading
   `llm-agent-audit-trace-analyzer` to compute governance metrics."
3. After the analyser writes `analysis/governance_summary.md`, point
   the user at the next three skills:
   - `wagf-verification-ladder` — if they built or modified a
     domain and need the setup-test-smoke-real-LLM done ladder.
   - `model-coupling-contract-checker` — if they added an external
     model.
   - `abm-reproducibility-checker` — before they submit a paper.

**Record** phase-4 status with the `analysis/` artefact paths.

## State file

The skill maintains `.wagf-quickstart-status.json` at the repo root:

```json
{
  "phase_1_env": {"completed": true, "verdict": "GREEN", "ts": "..."},
  "phase_2_smoke": {"completed": true, "ts": "...", "run_dirs": ["..."]},
  "phase_3_experiment": {"completed": false, "matrix_path": null},
  "phase_4_analysis": {"completed": false, "report_path": null}
}
```

When invoked, the skill reads this file FIRST and resumes at the
first incomplete phase rather than starting over.

## Refusal Protocol

The skill MUST refuse to:

1. Pretend the environment is fine when `check_env.py` reports RED
   or any required tool is missing. Show the remediation list and
   stop.
2. Skip phases. No Phase 3 without successful Phase 2; no Phase 4
   without a real `simulation_log.csv` from Phase 3.
3. Auto-fill the user's research question. Phase 3 input must come
   from the user, even if the rest is defaulted.
4. Continue if the smoke test produces zero output. The broker is
   broken in that case; debug rather than mask.
5. Replace the lifecycle skills' content. Always hand off via
   explicit "now load <skill>" cues.

## Bundled resources

- `references/environment_check.md` — full env-check rubric with
  per-platform install instructions.
- `references/smoke_test_recipe.md` — the exact commands to run
  Phase 2 and how to interpret the output diff.
- `references/first_experiment_template.md` — the pre-filled defaults
  for Phase 3 (per domain).
- `references/troubleshooting.md` — common failures (Ollama not
  running, model not pulled, Python version mismatch) with one-line
  fixes.
- `scripts/check_env.py` — runnable environment validator.

## Acceptance criteria

The skill is ready when:

- A user typing "I just cloned WAGF, help me set this up" in a
  freshly-cloned repo gets a useful response within 5 messages
  (env check + smoke test + Phase 3 prompt).
- `check_env.py` returns GREEN on this repo (Python 3.14, Ollama
  with `gemma3:4b`, `gemma4:e2b` present).
- The reservoir command in Phase 2 prints a blocked attempt, its reason,
  an approved retry and the change in the toy reservoir, and writes
  `operator_governance_audit.csv`.
- The hand-off to `wagf-experiment-designer` produces a valid
  `.research/wagf_experiment_matrix.yml` with the user's research
  question filled in (not auto-invented).
- `.wagf-quickstart-status.json` is created and updated correctly
  across phases.
