# Feedback-loop traps catalogue

Living catalogue of known coupling-layer bugs in WAGF and analogous
projects. Each entry has a detection recipe. Append new entries as
they are discovered.

## T1: Asymmetric base for action magnitudes

**Date discovered**: 2026-02-26 (suspected) → 2026-03-03 (fixed in
commit `4be5092`).

**System**: irrigation ABM ↔ Lake Mead reservoir.

**Bug**: In `irrigation_env.py:585`, the v20 code computed
`current = agent.get("diversion", agent["request"])`. After Powell
curtailment (which compresses `diversion` to ~55% of `request` in
shortage years), `increase_*` and `decrease_*` skills operated on the
compressed `diversion`, while `maintain_demand` preserved the full
`request`. Result: governed agents always proposed higher demand
than ungoverned for the same prompt — a code-level asymmetry, not a
behavioural difference.

**Detection recipe**:
1. For every action-magnitude rule in the env code, identify the
   `current` / `base` variable.
2. Confirm all action types use the SAME base.
3. If the base depends on `agent.get(..., default)`, walk the
   default chain and verify it doesn't introduce conditional
   asymmetry.

**Fix**: post-v21, all skills use `current = agent["request"]`. See
`irrigation_env.py:585-595` for the current canonical pattern.

## T2: Double-counting of damage / cost

**Pattern**: When an external CAT model returns a damage value AND
the agent also debits its own asset register, the same dollar gets
counted twice in aggregate metrics.

**Detection recipe**:
1. For every (cost, damage, exposure) field, identify EVERY
   downstream consumer.
2. If two consumers (agent.cost_ledger AND env.cost_aggregate) read
   the same field and both report it in summary outputs, the system
   double-counts.
3. Required guard: ONE consumer-of-record per ledger field; others
   must explicitly mark "for diagnostic only, not for paper totals".

**Anti-pattern in WAGF**: not currently observed in the irrigation /
flood single-agent path. Stay vigilant for the multi-agent flood
when buyout costs are shared between household ledger and
municipality ledger.

## T3: Phantom acceleration (read-after-write within step)

**Pattern**: Agent's same-step decision reads an external-model
output that depends on the same step's input.

**Detection recipe**: Walk the per-step ordering. Any time
`agent.read(field)` happens AFTER `external_model.compute(input that
depends on agent.previous_decision)` AND BEFORE `agent.commit_decision()`,
phantom acceleration is possible.

**Required guard**: pin all external-model outputs as `t-1`
references for `t`-step decisions, OR introduce an explicit
"perception lag" parameter that is documented in Methods.

## T4: Stale forward-fill bias

**Pattern**: When the agent step is finer than the external update
step, the agent forward-fills stale external values. This
underestimates variance.

**Detection recipe**: For every (agent, external) pair where step
durations differ, confirm the forward-fill rule is documented AND a
caveat is added to results.

**Anti-pattern in WAGF**: not currently a problem (agent step is
coarser than external step in both flood and irrigation). Stay
vigilant if a high-frequency agent decision is added (e.g., daily
trading agent).

## T5: Idempotency violation under retry

**Pattern**: Agent retries a decision; the external model runs
twice; state gets double-mutated.

**Detection recipe**:
1. Trace the retry loop in `examples/<domain>/run_*.py`.
2. Confirm that on retry, the external model is NOT re-invoked
   (or is invoked with explicit roll-back of the prior call).
3. Confirm the audit CSV records ONLY the final post-retry state,
   not intermediates.

**WAGF status**: validators are evaluated synchronously in the
broker layer; external models (reservoir, flood event) are invoked
ONLY after the validators approve. So retry loops do not double-run
the external model. Documented at
`broker/core/skill_broker_engine.py` (search for `retry`).

## T6: Random-seed leak across systems

**Pattern**: Agent and external model use the SAME global RNG.
A change in agent reasoning (e.g., one extra LLM call) shifts the
RNG state, producing a different external trajectory.

**Detection recipe**:
1. For every randomness consumer, identify the seeded RNG.
2. Confirm seeds are deterministic per (system, year, agent) tuple,
   not pulled from a shared global stream.

**WAGF status**: irrigation env_seed is derived from base seed; LLM
sampling uses Ollama's internal RNG. Document the seed derivation
in `_collect_reproducibility_metadata`.

## T7 (template — append new traps here)

**Date discovered**: YYYY-MM-DD
**System**: ...
**Bug**: ...
**Detection recipe**: ...
**Fix**: ...
