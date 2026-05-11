# vaccination_ma_demo — multi-agent vaccination reference

The multi-agent counterpart to `examples/vaccination_demo/`. Built in
Phase 6E to prove that WAGF's multi-agent path is domain-generic — the
same kind of regression target that `vaccination_demo` is for the
single-agent path.

## Three agent types

| Type | Count | Role |
|---|---|---|
| `health_authority` | 1 | Issues `advisory_none / advisory_mild / advisory_strong` each year |
| `community_org` | 2 | Runs `org_none / org_education / org_clinic` outreach |
| `individual` | N | Chooses `get_vaccinated / delay / refuse` per HBM |

Default smoke: 1 HA + 2 CO + 3 individuals × 3 years = 18 traces.

## How the multi-agent coupling works

Cross-agent state lives in a single `env` dict mutated by lifecycle
hooks. Each year:

```
pre_year → set outbreak severity, alias self.env to runner env
   ↓
[phase 1] health_authority decides → post_step writes env["advisory_*"]
   ↓
[phase 2] community_org decides   → post_step writes env["community_*"]
   ↓
[phase 3] individual decides       → reads env["advisory_*"], env["community_*"]
   ↓
post_year → aggregate vaccination_rate
```

The keys in `lifecycle_hooks.DYNAMIC_WHITELIST` (mirrored in
`run_experiment.py`) are the contract: they get auto-injected as
`{placeholder}` substitutions in each agent's prompt template.

Per Phase 6E Phase 1 verdict (`.ai/ma_vaccination_findings_2026-05-10.md`):
this pattern is domain-generic — no broker/ edits required to wire it
up. A future PhD adding `crop_yield` from a government agent to
household's `{yield_status_text}` prompt placeholder edits 3 files
(lifecycle hook, run script's whitelist, prompt template) — none of
them under `broker/`.

## Quick start

```bash
# 1. Validate schema
python -m broker.tools.validate_prompt examples/vaccination_ma_demo/config/agent_types.yaml

# 2. Smoke run (gemma3:1b for speed, ~3 min)
python examples/vaccination_ma_demo/run_experiment.py \
    --model gemma3:1b --years 2 --agents 2 --seed 42 \
    --output examples/vaccination_ma_demo/results/smoke_42

# 3. Verify cross-agent state in audit
python -c "
import pandas as pd
for kind in ['health_authority', 'community_org', 'individual']:
    df = pd.read_csv(f'examples/vaccination_ma_demo/results/smoke_42/{kind}_governance_audit.csv')
    print(f'{kind}: {len(df)} rows, skills: {sorted(df.proposed_skill.unique())}')"
```

Expected output:
```
health_authority: 2 rows, skills: ['advisory_mild', 'advisory_none']  (or any 2)
community_org:    4 rows, skills: ['org_education', 'org_none']        (or any subset)
individual:       4 rows, skills: ['delay', 'get_vaccinated']          (or any subset)
```

## Pattern reuse from single-agent vaccination_demo

- **HBM cognitive framework**: re-imported via `cognition/__init__.py`
- **Recent-dose physical check**: re-registered for `individual` agent type
- **DomainPack**: subclasses `VaccinationDomainPack` and extends
  `reflection_status_text` for the 2 new institutional types
- **Individual prompt**: adapted from `vaccination_demo/.../individual.txt`
  with cross-agent state injection points added

## Known gotchas (from Phase 6E findings)

1. **`hub=None`** must be passed explicitly to `TieredContextBuilder` —
   the constructor's `hub` is required-positional even though the body
   handles `None` correctly. (Broker fix proposed in Phase 6E findings.)

2. **`self.env = env` aliasing** in `pre_year` is REQUIRED when no
   simulation engine. Without it, mid-year cross-agent writes don't
   propagate to subsequent agents' context. (Documentation fix
   proposed.)

3. **`skill_registry.yaml` uses `skill_id:` (not `id:`)** — different
   from `agent_types.yaml` actions which use `id:`. WAGF has two YAML
   conventions for skill identity; document carefully when scaffolding.

## Reference

- `.ai/ma_vaccination_demo_spec_2026-05-10.md` — full Phase 6E spec
- `.ai/ma_vaccination_findings_2026-05-10.md` — BLOCKER inventory
- `examples/vaccination_demo/` — single-agent counterpart (HBM reference)
- `examples/multi_agent/flood/run_unified_experiment.py:1213-1263` —
  the flood example's `dynamic_whitelist` pattern this demo mirrors
