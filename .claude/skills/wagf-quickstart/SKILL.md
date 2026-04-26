---
name: wagf-quickstart
description: First-time WAGF setup walkthrough — environment check, smoke test, first experiment, and handoff to the four lifecycle skills. Use when the user says "I just cloned WAGF", "set up WAGF", "first WAGF run", "I'm new to this", "where do I start with WAGF", or opens a Claude Code session in a freshly-cloned WAGF repo without a clear task.
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
  `llm-agent-audit-trace-analyzer`, `model-coupling-contract-checker`,
  `abm-reproducibility-checker`).
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
the user to fix.

### Phase 2 — Smoke test (~5 min)

**Goal**: confirm the broker pipeline produces meaningful behavioural
diff (governed vs ungoverned).

**Run** (in order):

```bash
python examples/quickstart/01_barebone.py
python examples/quickstart/02_governance.py
```

`01_barebone.py` runs without governance; `02_governance.py` runs the
same scenario through the full broker pipeline. Both are short
(~5 agents × 2 years).

**What to show the user after the runs**:
- A 3-line diff: skill distribution from `01_` vs `02_` (typically
  governance reduces the increase / inaction rate).
- Confirm `examples/quickstart/results/<run_dir>/simulation_log.csv`
  was written.

**Refuse to advance** if either script crashes or
`simulation_log.csv` is missing/empty. Inspect stdout for the actual
error and recommend the fix from
`references/troubleshooting.md`.

**Record** phase-2 status with the path of each run dir, so Phase 4's
analyser can find them later.

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
   - **Seeds**: 3 (smallest meaningful paired-t; bump to 5 later).
   - **Time horizon**: domain default (irrigation 42 yr, flood 10 yr).
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
   the user at the next two skills:
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
- `examples/quickstart/01_barebone.py` and
  `02_governance.py` both produce a `simulation_log.csv` after Phase 2.
- The hand-off to `wagf-experiment-designer` produces a valid
  `.research/wagf_experiment_matrix.yml` with the user's research
  question filled in (not auto-invented).
- `.wagf-quickstart-status.json` is created and updated correctly
  across phases.
