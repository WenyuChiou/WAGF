# multi_agent/

Container directory for multi-agent WAGF experiments. Today it holds one
domain:

- **[flood/](flood/)** — the primary multi-agent water-sector reference
  implementation (institutional agents + households, Passaic River Basin
  study). Start with `flood/README.md`; the longer research-oriented
  description is in `flood/README_research.md` (Chinese: `flood/README_zh.md`).
  Run with `python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b`.

- **flood/paper3/** — the Paper 3 experiment batch scripts (six `.bat`
  launchers) and their own `tests/` directory, nested inside `flood/`
  rather than a sibling of it. See `docs/REPO_MAP.md` section 6 for the
  full launcher index.

If a second multi-agent domain is added later, index it here the same
way rather than nesting it inside `flood/`.
