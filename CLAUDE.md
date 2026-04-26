# CLAUDE.md — WAGF project memory for AI agents

This file is loaded by Claude Code (and other LLM-driven dev agents)
on every session opened in the WAGF repository. Its purpose is
**discoverability**: tell the agent which WAGF skills are available
and when to load each one.

For repo conventions (commit style, branch naming, test policy), see
`AGENTS.md`. For architecture, see `ARCHITECTURE.md` and
`broker/INVARIANTS.md`.

---

## Five WAGF skills are bundled with this repo

The skills live in `.claude/skills/` and are loaded automatically when
Claude Code is opened in this directory. Prefer these over generic
skills (`data-analyst`, `debugger`, `python-expert`) when the user's
question matches a WAGF skill's trigger.

| Need | Skill | Typical user phrasing |
|------|-------|------------------------|
| **Onboarding / first run** | `wagf-quickstart` | "I just cloned WAGF, help me set this up", "first WAGF run", "where do I start" |
| **Plan an experiment** | `wagf-experiment-designer` | "design an experiment", "plan an ablation", "compare strict vs disabled" |
| **Analyse audit traces** | `llm-agent-audit-trace-analyzer` | "analyse these traces", "compute governance metrics", "summarize rejection and retry outcomes" |
| **Verify external-model coupling** | `model-coupling-contract-checker` | "check ABM-model coupling", "audit feedback loop", "verify units between WAGF and X model" |
| **Pre-submission audit** | `abm-reproducibility-checker` | "audit reproducibility", "prepare for submission", "check this experiment folder" |

Full chooser table: `docs/skills/wagf-skills.md`.

## First-turn-of-session behaviour

When a session opens in this repo and the user has not yet stated a
task, prefer to ask: "Are you new to WAGF, or returning to existing
work?" Then:

- New user → suggest invoking `wagf-quickstart`.
- Returning user → ask which lifecycle stage they're at and load the
  matching skill.
- Active development with paper context → defer to
  `academic-writing-skills` for paper edits and to the WAGF skills
  for data work.

Do NOT silently assume the user wants to invoke any skill; the user
remains the source of intent.

## Routing precedence (when both a generic and WAGF skill could match)

| User asks about | Prefer WAGF skill | Over generic |
|-----------------|------------------|--------------|
| Reading audit CSVs | `llm-agent-audit-trace-analyzer` | `data-analyst` |
| Designing an experiment | `wagf-experiment-designer` | `project-planner` |
| Reproducibility / pre-submission | `abm-reproducibility-checker` | `code-review` |
| External-model integration | `model-coupling-contract-checker` | `system-architecture` |
| Set up first run | `wagf-quickstart` | `python-expert` |

For paper-writing work, defer to `academic-writing-skills` (manuscript
prose / submission workflow). The WAGF skills do NOT duplicate
paper-writing tools.

For literature work, defer to `research-hub` /
`academic-researcher`. The WAGF skills do NOT duplicate Zotero or
literature-management tools.

## Anti-hallucination posture

Every WAGF skill carries an explicit Refusal Protocol section. When
loaded, the skill will refuse to:

- Invent metric formulas not in the canonical implementations under
  `examples/<domain>/analysis/`.
- Auto-fill the user's research question, hypothesis, or model choice.
- Declare a result reproducible without git-blame cross-reference.
- Pretend the environment is fine when `check_env.py` reports RED.
- Pool data across different code commits without flagging.

Honour these refusals when relaying the skill's output to the user.

## Working in this repo (quick orientation)

| Path | What lives there |
|------|------------------|
| `broker/` | Framework core: governance pipeline, memory engines, validators, audit writer, lifecycle hooks. See `broker/INVARIANTS.md` for the 5 framework invariants. |
| `examples/single_agent/` | Flood domain (Nature Water Paper 1b reference experiment). |
| `examples/irrigation_abm/` | Irrigation domain (CRSS 78 agents × 42 yr). |
| `examples/multi_agent/flood/` | Multi-agent flood (Paper 3). |
| `examples/quickstart/` | Smoke-test scripts used by `wagf-quickstart` Phase 2. |
| `paper/nature_water/` | NW paper drafts + figure scripts (gitignored). |
| `tests/` and `broker/tests/` | pytest suites. Run `pytest tests/ broker/` before any commit. |
| `.ai/` | Session-local AI workspace (briefs, audit reports, status files). |
| `.research/` | Per-project research artefacts (experiment matrices, design briefs). |

## Active development conventions

- All new code must keep `pytest tests/ broker/` green
  (1947+ tests pass on the latest main).
- Memory engine API: `retrieve()` returns `List[Dict]` per
  `broker/INVARIANTS.md` Invariant 1. Use
  `retrieve_content_only()` for legacy plain-string consumers.
- IBR formula = R1 + R3 + R4 (R5 excluded per EDT2). Canonical at
  `examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py:100`.
- Reproducibility manifests are mandatory; written by
  `broker/core/experiment_runner.py:_collect_reproducibility_metadata`.
- Directory naming should embed the relevant code commit hash, not
  just a version tag (the 2026-04-25 v21 dir-naming-vs-code-state
  mismatch motivated this convention).

## Do NOT do without explicit user approval

- Modify production code in `broker/` while an experiment batch is
  running (mid-run subprocess imports may break).
- Touch paper drafts in `paper/nature_water/drafts/` without first
  loading `academic-writing-skills`.
- Commit data files (audit CSVs, simulation logs) to git — they
  should stay in `examples/*/results/`.
- Create new top-level directories without a stated need.

---

## Related files

- `AGENTS.md` — repo conventions for AI agents (commit style, branch
  policy, code review).
- `ARCHITECTURE.md` — broker pipeline + component overview.
- `broker/INVARIANTS.md` — five framework invariants and their CI
  guards.
- `docs/skills/wagf-skills.md` — full WAGF skill chooser table.
- `README.md` — human-facing project README.
