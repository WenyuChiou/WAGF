# vaccination_demo — WAGF non-water reference example

> **What this is**: a **Tier-2 showcase** demonstrating that WAGF
> (originally built for water-resource modelling) plugs cleanly into a
> non-water domain.  Vaccination decision-making, framed by the **Health
> Belief Model** (Rosenstock 1974; Carpenter 2010), with 3 actions
> (`get_vaccinated`, `delay`, `refuse`).
>
> **L3-1 chain (2026-05-23 / 2026-05-24)** brought the original PoC to
> Tier-2 showcase quality across four steps:
> - **L3-1A**: agent population sampled from literature-grounded
>   distributions (US Census 2020 ACS age + Pew Research 2024
>   trust-in-public-health + CDC high-risk-group probability;
>   default `--agents 25`) — see
>   [`data/persona_distributions.yaml`](data/persona_distributions.yaml).
> - **L3-1B**: all six HBM constructs tracked end-to-end
>   (susceptibility / severity / benefits / barriers / self-efficacy /
>   cues-to-action). YAML schema + prompt + parser + audit CSV all aligned.
> - **L3-1C**: 5 YAML thinking-rules covering the HBM coherence space
>   (tightened to canonical `{ construct: X, values: [...] }` shape
>   post-Phase-6N-E so they actually fire).
> - **L3-1D**: 5-year outbreak schedule anchored on COVID-19 2020-2024
>   timeline; per-year severity / supply / side-effect signal +
>   plain-language description flow into the LLM prompt via the
>   `env_context`-flattening broker fix. See
>   [`data/outbreak_schedule.yaml`](data/outbreak_schedule.yaml).
> - **L3-1E**: 3-seed × 2-model batch runner
>   ([`run_vaccination_batch.sh`](run_vaccination_batch.sh) /
>   [`.bat`](run_vaccination_batch.bat)) +
>   [`summary.py`](summary.py) for batch decision-statistics table.
>
> **What this is NOT**: a paper-grade calibrated vaccination ABM.  No
> IRB-approved primary survey behind the agent population (the
> distributions are honest reference points, not fitted survey data);
> no comparison with established public-health intervention benchmarks
> (no CDC vaccination-rate target validation).  See the Limitations
> section below.

## Why this example exists

Phase 6C-v2 / v3 (2026-05-10) refactored WAGF to be **domain-agnostic**:
a new application area should plug in with **0 broker/ source edits**.
This demo validates that claim.  If you're applying WAGF to a brand-new
topic (epidemiology, traffic, finance, education, ...), copy this
directory as a starting skeleton.

## Directory tour

```
vaccination_demo/
├── __init__.py             Registers HBM + validators + DomainPack
├── cognition/              HBM framework metadata
│   └── hbm_framework.py    register_framework_metadata("hbm", ...)
├── adapters/
│   └── vaccination_pack.py VaccinationDomainPack (DomainPack subclass)
├── validators/
│   └── vaccination_validators.py  3 check functions
├── config/
│   ├── skill_registry.yaml  3 skills + preconditions
│   ├── agent_types.yaml     persona, response schema, reflection
│   └── prompts/individual.txt   HBM-framed LLM prompt
├── run_experiment.py        Synthetic agent generator + sim + main()
└── results/                 Smoke output (gitignored)
```

## Run the smoke

Requires Ollama with a small model loaded (3B params is enough for the
PoC; the smoke run takes ~15 min wallclock).

```bash
ollama pull gemma3:1b   # 815 MB

cd <repo-root>
# Minimal fast smoke (5 agents, ~3 min). Omit --agents to use the
# L3-1A default of 25 (Tier-2 showcase scope; ~10-15 min on gemma3:1b).
python examples/vaccination_demo/run_experiment.py \
    --model gemma3:1b \
    --years 3 \
    --agents 5 \
    --seed 42 \
    --output examples/vaccination_demo/results/smoke
```

After completion, inspect:

- `results/smoke/individual_governance_audit.csv` — per-decision trace
- `results/smoke/reflection_log.jsonl` — year-end reflections
- `results/smoke/reproducibility_manifest.json` — pip / git / config hash
- `results/smoke/audit_summary.json` — high-level run stats

## What the framework provides for you

| Layer | Where it lives | What you don't have to write |
|---|---|---|
| Skill registry | `config/skill_registry.yaml` | YAML only — no Python |
| Validator pipeline | `validators/__init__.py` registers checks | Broker runs validators; you write check functions |
| Memory engine | `WindowMemoryEngine(window_size=5)` in run_experiment | Broker handles retrieval / consolidation / decay |
| LLM adapter | `--model gemma3:1b` in run_experiment | Broker dispatches to Ollama via standard adapter |
| Audit CSV writer + sentinel detector | All in broker | Columns auto-populated from trace dict |
| Reflection engine | `reflection.questions` in YAML | Broker triggers at year-end |
| Cross-agent observable | Single-agent demo — N/A | (would be free for multi-agent too) |
| Cognitive framework | `register_framework_metadata("hbm", ...)` | One call in `cognition/__init__.py` |

## What you DO write (for your new domain)

1. **Skills** — `config/skill_registry.yaml` (decision options)
2. **Agent persona** — `config/agent_types.yaml` (framework choice +
   reflection questions)
3. **Prompt template** — `config/prompts/<agent_type>.txt`. Use the
   broker-filled `{response_format}` placeholder rather than a
   hand-written inline JSON example — the JSON shape is auto-derived from
   `shared.response_format.fields` so YAML and prompt stay in sync. The
   hand-roll pattern caused the Finding 4 typo-bug surfaced in Phase 6C-v4
   (`susceptibility_appraisal` vs `susceptibility_assessment`).
4. **Validator checks** — `validators/<domain>_validators.py` (Python
   functions, ~80 LOC total in this PoC)
5. **DomainPack** — `adapters/<domain>_pack.py` (the 13-method facade,
   ~150 LOC, but many methods return empty defaults)
6. **Cognitive framework registration** — `cognition/<framework>.py`
   (only if not reusing PMT / utility / financial; ~80 LOC)
7. **Synthetic agent generator + env + lifecycle hooks** —
   `run_experiment.py` (~150 LOC, mostly orchestration)
8. **`__init__.py`** at the package level — registers all of the above

**Total user code**: ~600 LOC.  **Broker edits**: 0.

## Health Belief Model (HBM) — quick primer

HBM proposes that health-related action depends on six perceptions:

| Construct | What it captures | This demo's label |
|---|---|---|
| Susceptibility | "How likely am I to get the illness?" | `SUSCEPTIBILITY_LABEL` |
| Severity | "How bad would it be?" | (in prompt only) |
| Benefits | "How much would action help?" | (in prompt only) |
| Barriers | "What's the cost / inconvenience?" | (in prompt only) |
| Self-Efficacy | "Can I actually do this?" | `SELF_EFFICACY_LABEL` |
| Cues to Action | External triggers (outbreak, neighbour) | (in prompt only) |

This PoC explicitly tracks `SUSCEPTIBILITY_LABEL` + `SELF_EFFICACY_LABEL`
as the validator-checked constructs.  The other four enter the LLM's
reasoning but are not gated by Tier-2 thinking rules.  A research-grade
HBM ABM would track all six.

## Validator design

Three checks demonstrate WAGF's three-tier governance:

1. **Physical (state-precondition)** —
   `vaccination_recent_dose_no_revaccinate` blocks `get_vaccinated`
   when `weeks_since_dose < 26`.  Mirrors the seasonal-cycle protocol.
2. **Thinking — HBM coherence (BLOCKING, ERROR)** — 5 rules live in
   `config/agent_types.yaml` under `thinking_rules:` (L3-1C 2026-05-23,
   expanded from 2 → 5 covering all 6 HBM constructs):
   - `high_susceptibility_high_severity_high_efficacy_no_refuse`
     blocks `refuse` when all three are H/VH (clearest irrationality).
   - `high_cues_low_barriers_refuse_inconsistent` blocks `refuse` when
     external pressure is high and no documented barrier exists.
3. **Thinking — HBM coherence (WARNING, log-only)** — 3 rules logged
   to the audit CSV without blocking (small-LLM behaviour-influence
   per `MEMORY.md` is ~0% for WARNING; included for post-hoc audit):
   `low_susceptibility_no_get_vaccinated`,
   `high_barriers_high_self_efficacy_no_action_required`,
   `low_severity_low_benefits_get_vaccinated`.

## Known caveats (Phase 6C-v3 outstanding)

- **Cost-based affordability** — not implemented.  Phase 6C-v3 left a
  `$150K` hardcode in `AgentValidator` (flood-domain).  This PoC uses a
  "free vaccine" assumption and skips that path; an extension that
  wants per-agent insurance copay logic would need Group G fixes from
  the v4 plan first.
- **Multi-agent dynamics** (neighbour gossip, community immunity) —
  out of scope.  Single-agent only.  The
  `social/config.py:AGENT_SOCIAL_SPECS` hardcode (Group E v4) would
  need a fix before scaling this demo up.
- **Post-hoc calibration** — `conservatism_diagnostic.py` etc. hardcode
  `construct_TP_LABEL`.  A non-PMT calibration script needs Group F v4.

These do NOT block the runtime pipeline; they only matter when extending
the demo beyond the PoC scope.

## Reference

- `docs/guides/HOW_TO_ADD_A_NEW_DOMAIN.md` — the 7-step walkthrough
- `broker/domains/protocol.py` — DomainPack Protocol
- `broker/INVARIANTS.md` — cross-version comparability log
- `.ai/domain_pack_design_2026-05-10.md` — Phase 6C-v2 architectural plan
- `.ai/phase6c_v3_full_plan_2026-05-10.md` — outstanding v4 BLOCKERs
