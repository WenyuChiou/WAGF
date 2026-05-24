# vaccination_demo — WAGF non-water reference example

> **What this is**: a Tier-2 showcase demonstrating that WAGF
> (originally built for water-resource modelling) plugs cleanly into a
> non-water domain.  Vaccination decision-making, framed by the **Health
> Belief Model** (Rosenstock 1974; Carpenter 2010), with 3 actions
> (`get_vaccinated`, `delay`, `refuse`).  As of L3-1A (2026-05-23), the
> agent population is sampled from **literature-grounded distributions**
> (US Census 2020 ACS age + Pew Research 2024 trust-in-public-health
> + CDC high-risk-group probability) — see
> [`data/persona_distributions.yaml`](data/persona_distributions.yaml).
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
2. **Thinking — HBM coherence (BLOCKING)** —
   `vaccination_high_susceptibility_high_efficacy_no_refuse` blocks
   `refuse` when the LLM rated `SUSCEPTIBILITY=H/VH` and
   `SELF_EFFICACY=H/VH`.  Detects inconsistent reasoning.
3. **Thinking — HBM coherence (WARNING)** —
   `vaccination_low_susceptibility_no_immediate_action` flags
   `get_vaccinated` when `SUSCEPTIBILITY=VL`.  Not blocking — could
   be altruistic; the audit still records the unusual combination.

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
