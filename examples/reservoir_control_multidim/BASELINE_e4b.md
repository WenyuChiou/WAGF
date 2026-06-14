# `reservoir_control_multidim` — gemma4:e4b worked-run baseline

Real-LLM validation of the Phase 6W multi-dimensional-action chain: the operator
proposes **three bounded setpoints in one decision** (`release_rate_cms`,
`hydropower_target_mw`, `flood_pool_pct`), each governed per-field by the generic
`ParameterBoundsValidator` (reject-and-retry) and committed verbatim to the hosted
`ToyMultiReservoir` through a plain `ContinuousBundle` (no derive layer).

## Run configuration

| | |
|---|---|
| Model | `gemma4:e4b` (Ollama, RTX 4080 SUPER) |
| Code commit | `b4a2dd6f` (post-#16, deferred-A merged) |
| Configs | `config/multidim_skill_registry.yaml` + `config/multidim_agent_types.yaml` |
| Skill | `set_release_multi` (3 setpoints); `maintain_release` (noop) available but not exercised in this run |
| Agents / horizon | 1 operator × 4 years |
| Seeds | 42, 43, 44, 45, 46 (5) → **20 decisions** |
| Governance | `strict`; `multi_param_action` ON; `audit.param_columns` ON |

### Reproduce

```bash
python examples/reservoir_control_multidim/run_reservoir_multidim.py \
  --model gemma4:e4b --years 4 --seed <SEED>
```

## Aggregate baseline (5 seeds × 4 years = 20 decisions)

| Metric | Value |
|---|---|
| Approved | **20 / 20 (100%)** — every decision `set_release_multi` APPROVED |
| Governance retries | mean **0.60** (8 decisions × 0, 12 × 1; all converge to APPROVED) |
| Fallback | `fallback_activated=False` on all 20 — governance never exhausted retries (no REJECTED_FALLBACK to a default skill) |
| Commit fidelity | `proposed_param_<x>` == `world_<x>` on all 20 (direct-commit, no derive) |

(`sd` below is **population** sd / `pstdev`; a re-runner using sample sd will see a slightly larger figure, e.g. flood_pool 5.10 vs 4.97 — not a mismatch.)

| Setpoint | bounds | min | max | mean ± sd (pop) | in-bounds |
|---|---|---|---|---|---|
| `release_rate_cms` | 0–850 | 250 | 450 | 363.5 ± 48.6 | ✓ all |
| `hydropower_target_mw` | 0–2000 | 600 | 1000 | 812.5 ± 92.0 | ✓ all |
| `flood_pool_pct` | 0–100 | 10 | 25 | 15.5 ± 5.0 | ✓ all |

The non-zero spreads (and the per-year / per-seed variation) confirm the LLM is
genuinely reasoning over the three setpoints rather than echoing a fixed default.

## Important: this is a BEHAVIOURAL baseline, not byte-identity

`gemma4:e4b` on Ollama is **non-deterministic** at the same commit + seed (Phase
6R-D-4). Re-runs will NOT reproduce identical setpoint values. Treat this as an
aggregate behavioural baseline: a healthy re-run should show ~100% APPROVED, low
mean retries, `magnitude_fallback=False`, all setpoints in-bounds, and setpoints
within (or near) the documented ranges — not the exact numbers. For byte-identity
regression use the mock path (`--model mock`, `broker/tests/test_reservoir_multidim_runner.py`).

## Data

Result CSVs/traces are git-ignored (`examples/reservoir_control_multidim/results_*/`);
regenerate with the reproduce command above.
