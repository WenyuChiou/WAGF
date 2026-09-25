# Irrigation ABM — WAGF Adaptation of Hung & Yang (2021)

LLM-driven reproduction of the Colorado River Basin irrigation ABM from Hung & Yang (2021, *Water Resources Research*). 78 agricultural water users make annual demand decisions using natural-language reasoning — guided by governance rules and episodic memory — instead of Fuzzy Q-Learning (FQL).

**Key terms**: CRSS (Colorado River Simulation System), MAF (million acre-feet), AF (acre-feet), DCP (Drought Contingency Plan), USBR (U.S. Bureau of Reclamation).

---

## 1. Quick Start

```bash
# Smoke test (5 synthetic agents, 5 years)
python run_experiment.py --model gemma3:4b --years 5 --agents 5

# Validation (10 synthetic agents, 10 years)
python run_experiment.py --model gemma3:4b --years 10 --agents 10 --seed 42

# Production (78 real CRSS agents, 42 years — requires ref/CRSS_DB data)
python run_experiment.py --model gemma3:4b --years 42 --real --seed 42 --num-ctx 8192 --num-predict 4096
```

### Key CLI Flags

| Flag | Default | Description |
| :--- | :------ | :---------- |
| `--model` | `gemma3:1b` | Ollama model name |
| `--years` | `5` | Simulation years |
| `--agents` | `5` | Number of agents (synthetic mode) |
| `--real` | disabled | Use 78 real CRSS agents instead of synthetic |
| `--seed` | `42` | Random seed for reproducibility |
| `--workers` | `1` | Parallel LLM workers |

Run `python run_experiment.py --help` for all flags (memory, magnitude, context window, etc.).

### Project Structure

```text
irrigation_abm/
  run_experiment.py          # Main runner (ExperimentBuilder pipeline)
  irrigation_env.py          # Water system simulation environment
  irrigation_personas.py     # Cluster persona builder + context helpers
  config/
    agent_types.yaml         # Agent config, governance rules, personas
    skill_registry.yaml      # Available irrigation skills
    policies/                # Domain-specific governance policies
    prompts/                 # LLM prompt templates
  validators/
    irrigation_validators.py # 12 custom governance validators
  learning/
    fql.py                   # Reference FQL algorithm (not used by LLM runner)
```

### Output Files

```text
results/<run_name>/
  simulation_log.csv                     # Year, agent, skill, constructs, magnitude
  irrigation_farmer_governance_audit.csv # Governance interventions
  governance_summary.json                # Aggregate audit stats
  config_snapshot.yaml                   # Reproducibility snapshot
  raw/irrigation_farmer_traces.jsonl     # Full LLM traces
  reflection_log.jsonl                   # Memory consolidation events
```

### v0.6 Coupling Layer (optional, default OFF)

Pass `--coupling` to wrap `IrrigationEnvironment` in
`broker.coupling.EnvironmentCouplingAdapter`, using the `IrrigationBundle`
+ `CouplingContract` defined in `coupling_modules.py`:

```bash
python run_experiment.py --model mock --agents 5 --years 3 --seed 42 --coupling
python run_ungoverned_experiment.py --model mock --agents 5 --years 3 --seed 42 --coupling
```

This is the same flag `global_config.coupling.enable: true` in the
agent_types YAML resolves to (`broker/coupling/flag.py`); `--coupling`
just writes that key into a derived copy of the config, and OVERRIDES an
explicit `enable: false` already there (the resolved source is then
reported as `cli`, not `yaml`). The derived copy is written to
`<output>/agent_types.coupling.yaml`, a PERSISTENT file (not deleted at
process exit, so a finished or failed run can still be inspected); the
frozen on-disk `agent_types.yaml` is never edited, so a bare re-run of
any existing command is unaffected. `prompt_template_file` is rewritten
to an absolute path when it resolves against the source config
directory; otherwise it is left as is and reported with a printed line,
since it now lives in a different directory than the original file.
`reproducibility_manifest.json` records the original path in a
`derived_from_config` field (and its byte hash in
`derived_from_config_sha256`), next to the
derived path in `agent_types_config`.

The contract validates, every period, that the world-side observations
`IrrigationEnvironment.advance_year()` produces (`year`,
`total_available_water`, `drought_index`, `total_basin_demand`) and the
per-agent committed demand (`request`) stay within their declared units
and bounds, raising `CouplingViolation` instead of silently accepting an
out-of-range or malformed value. Those bounds are COMPUTED from the
loaded config and agents, not typed-in constants: `total_available_water`
from `config.upper_basin_allocation + config.lower_basin_allocation`
(times the `[0.7, 1.0]` range `advance_year()`'s own variability formula
is limited to), and `request` / `total_basin_demand` from the maximum and
summed `water_right` of the agents actually loaded into the run, so a
5-agent synthetic smoke test and a 78-agent real-CRSS run each get bounds
sized to their own physical ceiling. See
`examples/irrigation_abm/tests/test_coupling.py::
test_contract_bounds_against_faf1bb12_corpus` for these bounds checked
against a real 78-agent, 42-year corpus.

An OBSERVATION-side `CouplingViolation` (a corrupted world reading,
raised inside `advance_step()` before any agent decides) aborts the whole
run; a COMMIT-side `CouplingViolation` (raised while processing one
agent's approved step) is caught per-agent and recorded as one ABORTED
audit row, and the run continues.

With the contract on, `simulation_log.csv` is byte-identical to a
contract-off run at the same seed/years/agents, and every pre-existing
governance-audit-CSV column keeps the same values; the audit CSV gains
exactly two additional columns, `world_request` and
`world_contention_rule`, the same key-gated columns every coupled WAGF
domain gets from the shared audit hook, not an irrigation-specific
change. `run_integrity.json` then records `coupling_adapter: true` and
`reproducibility_manifest.json` carries a `coupling_provenance` block
with a `contract_sha256`. Because the contract's bounds are derived from
the loaded agents' `water_right` values (see below), `contract_sha256`
identifies the contract as built for THAT run's agent set, so a synthetic
5-agent run and a real 78-agent CRSS run hash differently even though
both use the exact same `coupling_modules.py` code.

**Workers and the v0.6 coupling layer**: the generic builder warns that
`workers>1` with coupling enabled is unsupported (AR-3,
`broker/INVARIANTS.md` "Accepted risks") because parallel steps can in
general interleave a coupled bundle's mutations. That risk does not
materialise for irrigation specifically: the commit path
(`IrrigationEnvironment.execute_skill`) writes only to a per-agent-keyed
dict entry using a generator derived fresh per `(seed, year, agent,
skill)` call, never a shared mutable stream, and
`EnvironmentCouplingAdapter` mutates its own state only inside
`advance_step()`, which runs once per year on the main thread before the
parallel agent phase begins. Confirmed empirically at `workers=4` (audit
CSV content, sorted to a stable key, is identical off vs on; see
`test_coupling_off_vs_on_byte_identical_workers_4`). The generic AR-3
warning still fires (it is accurate for the general case) and is not
suppressed.

This is a DIFFERENT, narrower boundary than the pre-existing
`global_config.coupling.context_contract` flag (see
`irrigation_coupling.py`), which fail-loud-guards the per-agent physical
state (Lake Mead elevation, curtailment, water right, etc.) that
`get_agent_context()` hands to the LLM prompt. The two flags compose
independently, and turning both on carries both sets of keys in
`run_integrity.json` side by side (`EnvironmentCouplingAdapter.__getattr__`
forwards `get_coupling_retrofit_metadata` to the wrapped environment when
it defines one, so wrapping does not make the context-contract guard's
own reporting disappear). See
`examples/irrigation_abm/tests/test_coupling.py` for the byte-identity
and violation checks.

---

## 2. Production Results (v21)

**Experiment**: 78 agents × 42 years, gemma3:4b, strict governance, seed 42.

| Metric | Value | CRSS Reference |
| :----- | :---- | :------------- |
| Mean demand | 5.87 MAF/yr | 5.86 MAF/yr (1.00×) |
| Steady-state CoV (Y6-42) | 5.3% | Target <10% |
| Within ±10% corridor | 88% (37/42 yr) | — |

### Governance Outcomes (3,276 decisions)

| Outcome | Count | Percentage |
| :------ | ----: | ---------: |
| Approved (1st attempt) | 1,236 | 37.7% |
| Retry success | 735 | 22.4% |
| Rejected → maintain_demand | 1,305 | 39.8% |

### Behavioral Diversity

| Condition | IBR | EHE |
| :-------- | --: | --: |
| Governed (with validators) | 38.2% | 0.687 |
| No-validator baseline | 61.1% | 0.848 |

Note: v20 results are deprecated due to the execute_skill base asymmetry bug. All analysis uses v21 data.

---

## 3. System Architecture

| Pillar | Name | Effect |
| :----- | :--- | :----- |
| 1 | **Strict Governance** | 12 configured validators (11 active; `compact_allocation_check` never fires because the `basin_allocation` context key is not injected — see docs/irrigation_model_caveats.md) block physically impossible or redundant actions |
| 2 | **Cognitive Memory** | `HumanCentricMemoryEngine` (basic ranking mode) + year-end reflection |
| 3 | **Reflection Loop** | Year-end consolidation with domain-specific guidance questions |

```mermaid
flowchart TD
    A["<b>Initialize</b><br/>78 CRSS agents<br/>Cluster assignment<br/>Water rights & diversions"] --> B

    subgraph YEAR ["For each year (1..42)"]
        B["<b>Pre-Year Hook</b><br/>advance_year() → precip, Lake Mead,<br/>drought index, shortage tier, curtailment<br/>Inject memories + action-outcome feedback"]

        B --> C["<b>Agent Decision</b><br/>(per agent, parallel)"]

        subgraph AGENT ["Agent Decision Loop"]
            C --> D["Retrieve memories<br/>(window + top-k)"]
            D --> E["Build prompt<br/>persona + WSA/ACA + env context"]
            E --> F["LLM call<br/>→ parse WSA, ACA, skill choice"]
            F --> G{"Governance<br/>validation<br/>(12 validators, 11 active)"}
            G -->|APPROVED| H["Execute skill<br/>Gaussian magnitude sampling"]
            G -->|ERROR| I{"Retry<br/>≤ 3 attempts?"}
            I -->|Yes| J["Re-prompt with<br/>rejection reason"]
            J --> F
            I -->|"No / EarlyExit<br/>(same rules re-trigger)"| K["REJECTED<br/>→ maintain_demand fallback"]
            K --> H
        end

        H --> L["<b>Post-Step Hook</b><br/>Record decision, constructs, magnitude"]
        L --> M["<b>Post-Year Hook</b><br/>Batch reflection<br/>Memory consolidation"]
        M --> B
    end

    M --> N["<b>Output</b><br/>simulation_log.csv<br/>governance_audit.csv<br/>governance_summary.json"]

    style A fill:#e1f5fe
    style H fill:#c8e6c9
    style K fill:#fff9c4
    style N fill:#f3e5f5
```

---

## 4. Water System Model

Simplified CRSS mass balance at annual resolution (same abstraction as Hung & Yang 2021). **[Full equations and derivations](docs/irrigation_physics.md)**.

### Key Parameters

| Parameter | Value | Source |
| :-------- | :---- | :----- |
| Natural flow baseline | 12.0 MAF/yr | CRSS historical average |
| Min Powell release | 7.0 MAF/yr | USBR DCP floor (2019) |
| UB infrastructure ceiling | 5.0 MAF/yr | Historical UB depletion capacity |
| Mexico treaty delivery | 1.5 MAF/yr | 1944 Treaty (before DCP reductions) |
| Initial elevation | 1081.46 ft | USBR observed December 2018 |
| Simulation period | 2019-2060 | Following Hung & Yang (2021) |

### Shortage Tiers

| Mead Elevation | Tier | Curtailment | Governance Effect |
| :------------- | :--- | :---------- | :---------------- |
| ≥ 1075 ft | 0 (Normal) | 0% | WARNING only |
| 1050-1075 ft | 1 | 5% | WARNING only |
| 1025-1050 ft | 2 | 10% | ERROR: blocks increase |
| < 1025 ft | 3 | 20% | ERROR: blocks increase |

---

## 5. Agent Design

### Behavioral Clusters

Three k-means clusters from Hung & Yang (2021), mapped from FQL parameters to LLM personas:

| Cluster | N (of 78) | LLM Persona | Magnitude default |
| :------ | --------: | :---------- | ----------------: |
| **Aggressive** | 67 | Bold, large demand swings | 10.0% |
| **Forward-Looking Conservative** | 5 | Cautious, future-oriented | 7.5% |
| **Myopic Conservative** | 6 | Tradition-oriented, slow updates | 4.0% |

The LLM arms use these realized clusters; `--rebalance-clusters` (target 50/30/20) is opt-in and was OFF in every LLM run. The FQL baseline exists in both variants (`fql_raw_faf1bb12` rebalanced, `fql_raw_norebalance_faf1bb12` matched).

### Action Space (5 Skills)

| Skill | Real-World Analog |
| :---- | :---------------- |
| `increase_large` | Major acreage expansion |
| `increase_small` | Marginal crop intensity increase |
| `maintain_demand` | Status quo under long-term contracts |
| `decrease_small` | Minor conservation adjustments |
| `decrease_large` | Fallowing fields, crop switching |

The LLM chooses the skill (qualitative direction); actual magnitude is sampled from persona-scaled Gaussian distributions at execution time (quantitative).

---

## 6. Governance System

12 validator functions are defined; 9 are wired into `ALL_IRRIGATION_CHECKS` and actually dispatch at runtime, in a priority-ordered rule chain. ERROR-level violations reject the action and re-prompt (up to 3 retries). WARNING-level rules log but allow.

F04 (2026-09-25 audit): `drought_severity_check`, `magnitude_cap_check` and `compact_allocation_check` are excluded from dispatch — each reads a context key nothing in the pipeline produces (`basin_allocation`, `proposed_magnitude`), or a threshold the real CRSS data never reaches (drought index tops out around 0.62-0.69 per run, below the 0.7 floor) — and fired zero times across 49,140 audited strict rows. The functions stay defined (tests call them directly) and are covered by `assert_validator_inputs_have_producers()`, a startup self-check in `irrigation_validators.py` that fails fast if a *dispatched* check reads a key with no producer.

| # | Validator | Blocks | Level | Category |
| - | :-------- | :----- | :---- | :------- |
| 1 | `water_right_cap_check` | increase (at cap) | ERROR | Physical |
| 2 | `non_negative_diversion_check` | decrease (diversion=0) | ERROR/WARN | Physical |
| 3 | `minimum_utilisation_check` | decrease (<10%) | ERROR | Physical |
| 4 | `demand_floor_stabilizer` | decrease (<50%) | ERROR | Economic |
| 5 | `demand_ceiling_stabilizer` | increase (basin >6.0 MAF) | ERROR | Economic |
| 6 | `drought_severity_check` | increase (drought>0.7) — excluded from dispatch, real index never reaches 0.7 | ERROR | Physical |
| 7 | `magnitude_cap_check` | increase (exceeds cap) — excluded from dispatch, `proposed_magnitude` never injected | WARNING | Physical |
| 8 | `supply_gap_block_increase` | increase (fulfil<70%) | ERROR | Physical |
| 9 | `curtailment_awareness_check` | increase (Tier 2+) | ERROR | Social |
| 10 | `compact_allocation_check` | increase (basin>Compact) — excluded from dispatch, `basin_allocation` never injected | WARNING | Social |
| 11 | `consecutive_increase_cap_check` | increase (3yr streak) | ERROR | Temporal |
| 12 | `zero_escape_check` | maintain (<15% util) | ERROR | Behavioral |

---

## 7. Assumptions and Simplifications

**Agent behavior**: No inter-agent communication; annual decision frequency; homogeneous curtailment (no prior appropriation doctrine); fixed persona assignment throughout simulation.

**Water system**: Single-reservoir model (Lake Mead only; Powell implicit via 7.0 MAF/yr minimum release); annual resolution; static non-agricultural demand (5.0 MAF/yr for CAP, MWD, and other M&I uses); no groundwater.

**LLM-specific**: Magnitude-reasoning decoupling (LLM chooses skill direction, not magnitude); results specific to gemma3:4b; ERROR-level governance cannot be overridden.

---

## 8. Data Availability

All data for `--real` mode (78 CRSS agents) is included in `ref/CRSS_DB/`:

- **Precipitation**: `HistoricalData/PrismWinterPrecip_ST_NOAA_Future.csv` (CRSS/NOAA PRISM, 2017-2060)
- **Agent water rights**: `annual_baseline_time_series.csv` (78 agents)
- **Elevation curves**: Hardcoded in `irrigation_env.py` (USBR 2009 area-capacity survey)

Synthetic mode requires no external data. Reproducibility: all production runs use `--seed 42`; config captured in `config_snapshot.yaml`.

---

## 9. References

Hung, F., & Yang, Y. C. E. (2021). Assessing adaptive irrigation impacts on water scarcity in nonstationary environments — A multi-agent reinforcement learning approach. *Water Resources Research*, 57, e2020WR029262. <https://doi.org/10.1029/2020WR029262>

Lazarus, R. S., & Folkman, S. (1984). *Stress, Appraisal, and Coping*. Springer.

Ostrom, E. (1990). *Governing the Commons: The Evolution of Institutions for Collective Action*. Cambridge University Press.
