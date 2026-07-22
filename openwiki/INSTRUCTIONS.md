# Repository wiki brief — WAGF (governed_broker_framework)

<!-- User-authored brief. OpenWiki reads this file for scope and priorities;
     it is not generated documentation and must never be rewritten by wiki
     init/update/chat runs. -->

## Audience

1. Coding agents (Claude Code, Codex delegates, Hermes) orienting in this
   repository before making changes — the primary consumer.
2. External researchers using WAGF (public MIT repo) who need a
   where-does-X-live layer on top of the README.

## Scope and priorities (in order)

1. **Broker package map.** `broker/` sub-packages (agents, components,
   config, core, coupling, domains, governance, interfaces, memory):
   each one's responsibility, and the concrete "where do I add a new
   domain / a new governance rule / a new coupling" answers. This is the
   page delegates need most.
2. **Governance pipeline flow.** How a decision travels: LLM proposal →
   feasibility screening → behavioral-theory checks → retry with feedback
   → state mutation. LINK to `ARCHITECTURE.md` and `broker/INVARIANTS.md`
   for depth — the wiki page is the orientation summary, not a restatement.
3. **Running experiments.** The `examples/` map: which example is which
   entry point (quickstart, governed_flood, irrigation_abm, multi_agent,
   vaccination_demo, reservoir_control...), how a run is invoked, where
   configs live, and which operations write/overwrite results.
4. **Testing.** How to run the suite, test layout, what CI (test.yml) runs.
5. **Paper/analysis tooling.** Pointers only: where compile/run scripts
   live and what they orchestrate — do NOT document manuscript content.

## Constraints

- Code is the source of truth; where docs and code disagree, document the
  code and flag the discrepancy.
- Prefer LINKING to existing docs (README.md, ARCHITECTURE.md,
  broker/INVARIANTS.md, DATA.md, CONTRIBUTING.md, examples/README.md)
  over restating them — this repo is unusually well-documented; the wiki
  is the thin orientation layer on top.
- NEVER read or quote .env files, API keys, or credentials.
- **NEVER quote, summarize, or reference the content of `paper/`
  manuscripts, unpublished result numbers, or survey-derived data** —
  this is a public wiki over an active research project. Pointing at a
  script's existence is fine; its scientific findings are not.
- Do not document `_archive/` or `ref/`.
- Keep the wiki small: quickstart plus at most ~5 section pages. Depth
  over breadth; no stub pages. English only.
