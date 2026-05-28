# AI-assisted setup guide

WAGF ships AI agent infrastructure for getting from `git clone` to a
working experiment without reading the manual cover-to-cover. The
path depends on which AI coding tool you use.

This guide is bundled with the repo — your AI agent (or you, reading
along) should be able to follow it without any external dependencies.

---

## Path 1 — Claude Code (the bundled-skills path)

The repo ships **7 WAGF-specific skills** under `.claude/skills/`,
all tracked in git. When you open this directory in Claude Code,
they appear in the skill picker automatically.

### Recommended first invocation (new researcher)

```
/skill wagf-quickstart
```

Walks the 5-tier onboarding: environment check → smoke test → first
experiment → audit-trace analysis → reproducibility check. Each tier
ends with a confirm-go-no-go prompt; you can stop after any tier.

### Lifecycle skills (use after `wagf-quickstart` puts you on solid ground)

| When you want to... | Invoke | Output |
|---|---|---|
| Build a new domain (from research question to working experiment) | `/skill wagf-domain-builder` | S0–S7 structured interview; ends with a runnable domain skeleton via `broker.tools.scaffold_domain` |
| Couple your LLM agents to an external simulator (Python / R / CSV / REST) | `/skill wagf-coupling-designer` | Coupling contract + mock adapter + real-model adapter scaffold |
| Plan an experiment matrix (model × governance × seed × metric) | `/skill wagf-experiment-designer` | Reproducible matrix written to `.research/experiment_matrix.yml` |
| Analyse audit traces (IBR / EHE / rejection taxonomy) | `/skill llm-agent-audit-trace-analyzer` | Paper-ready metric tables + figures |
| Verify external-model coupling (units, time steps, feedback double-count) | `/skill model-coupling-contract-checker` | Audit report with concrete findings |
| Pre-submission reproducibility audit | `/skill abm-reproducibility-checker` | Pass/fail per criterion + missing-artefact list |

Each skill has a `SKILL.md` + `references/` subdirectory under
`.claude/skills/<skill-name>/`. Open the SKILL.md for the full
trigger / refusal / output contract.

### Routing precedence (when both a generic and WAGF skill could match)

| User asks about | Prefer WAGF skill | Over generic |
|---|---|---|
| Reading audit CSVs | `llm-agent-audit-trace-analyzer` | `data-analyst` |
| Designing an experiment | `wagf-experiment-designer` | `project-planner` |
| Reproducibility / pre-submission | `abm-reproducibility-checker` | `code-review` |
| External-model integration | `model-coupling-contract-checker` | `system-architecture` |
| First run | `wagf-quickstart` | `python-expert` |

---

## Path 2 — Cursor / Cline / Aider / Codex CLI

The repo's `AGENTS.md` is the cross-tool agent reference. It uses
the OpenSkills format and is consumable by any agent that follows
the AGENTS.md convention. Point your tool at it:

- **Cursor**: drop `AGENTS.md` content into `.cursorrules` (or
  reference it from there) — Cursor reads `.cursorrules` at session
  start.
- **Cline**: add `AGENTS.md` to your project context window via
  Cline's `Add context` action.
- **Codex CLI**: Codex reads `AGENTS.md` automatically when
  invoked in a repo that ships one.
- **Aider**: pass `--read AGENTS.md` (or `/read AGENTS.md` inside
  the chat) so the rules are in context.

The WAGF-specific skill catalogue inside `AGENTS.md` mirrors the
Claude Code skill set above. Your agent will see the same skill
names + trigger conditions, just expressed in OpenSkills schema.

### Minimal first prompts (works for any of the above)

```
I just cloned WAGF. Walk me through the quickstart per `AGENTS.md`.

Then: I want to build a domain for <my topic>. Walk me through
wagf-domain-builder.
```

The agent will pick up the skill descriptions from AGENTS.md and
follow the same S0–S7 interview path.

---

## Path 3 — Plain Python / no AI assistant

If you prefer to read your way in (or your AI tool doesn't read
AGENTS.md), every skill has a paper trail in `docs/guides/`:

| Skill | Documented at |
|---|---|
| `wagf-quickstart` | `docs/guides/quickstart_guide.md` |
| `wagf-domain-builder` | `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` + `docs/guides/domain_pack_guide.md` |
| `wagf-coupling-designer` | `docs/guides/integration_guide.md` |
| `wagf-experiment-designer` | `docs/guides/experiment_design_guide.md` |
| `llm-agent-audit-trace-analyzer` | (analysis recipes live next to the data; see `examples/single_agent/analysis/`) |
| `model-coupling-contract-checker` | `docs/guides/integration_guide.md` (coupling-audit section) |
| `abm-reproducibility-checker` | `docs/checklists/` (pre-submission audit checklist) |

Plus four end-to-end domain examples:

- `examples/single_agent/` — Nature Water Paper 1b reference (flood single-agent, 4 skills)
- `examples/irrigation_abm/` — 78 CRSS agents × 42-year irrigation
- `examples/multi_agent/flood/` — Paper 3 multi-agent flood (400 agents × 13 years, 7 agent types)
- `examples/vaccination_demo/` — Non-water reference using Health Belief Model (HBM)
- `examples/_test_fixtures/fake_traffic/` — Minimum-surface non-water genericity gate (validates that broker truly is domain-pluggable)

---

## Anti-hallucination posture (relevant to all 3 paths)

Every WAGF skill carries an explicit refusal protocol. They WILL refuse to:

- Invent metric formulas not in the canonical implementations under
  `examples/<domain>/analysis/`
- Auto-fill your research question, hypothesis, or model choice
- Declare a result reproducible without git-blame cross-reference
- Pretend the environment is fine when `check_env.py` reports RED
- Pool data across different code commits without flagging

If your agent ignores these refusal protocols and confabulates, file
an issue — it's a skill bug, not user error.

---

## Where this guide fits

- Top-level `README.md` introduces WAGF in 2 paragraphs.
- `CONTRIBUTING.md` explains how to contribute code.
- This file (`docs/AI_ASSISTED_SETUP.md`) explains how to onboard *with
  AI help*, across 3 different AI tooling stacks.
- `ARCHITECTURE.md` is the deep dive into broker internals (for after
  you've onboarded and want to extend).
- `AGENTS.md` is the machine-readable agent catalogue (skill schema +
  refusal protocols).

For maintenance / contribution conventions for AI agents *acting on
the repo* (commit-style, branch policy, gate triggers), see
`AGENTS.md` directly.
