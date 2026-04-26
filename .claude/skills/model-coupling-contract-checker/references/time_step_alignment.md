# Time-step alignment patterns

WAGF agents typically decide at coarse intervals (annual). External
models often run at finer intervals (daily reservoir, hourly weather,
episodic flood). The alignment rule must be explicit.

## Pattern 1: Coarse agent ↔ fine external (most common)

Example: irrigation ABM (annual decisions) ↔ Lake Mead reservoir
mass balance (daily volume update).

Required documentation:
- **Aggregation rule per field**: e.g.,
  `delivered_volume = sum(daily_diversion[year])`,
  `lake_elevation_at_year_end = lake_elevation[year_last_day]`.
- **Order of operations within agent step**:
  1. Agent reads `env.lake_mead_level` (year-start snapshot).
  2. Agent decides `request` for the year.
  3. Reservoir module runs 365 daily steps with curtailment
     applied to `request`.
  4. Agent reads `actual_diversion` (post-year-end aggregate).
  5. Reflection / memory update.

Anti-pattern (the 2026-03-03 v21 bug): step 4's `actual_diversion`
fed back into step 2's base for next year's decision in an
asymmetric way (only some skills).

## Pattern 2: Coarse agent ↔ episodic external

Example: flood ABM (annual decisions) ↔ stochastic flood events.

Required documentation:
- **Trigger model**: how event occurrence is decided (e.g., poisson
  with rate λ per year; pre-baked schedule from a flood frequency
  curve).
- **Within-year ordering**: does the agent decide BEFORE knowing
  whether a flood occurred this year, or AFTER?
- **Damage attribution**: when an event occurs, is damage debited
  to the agent's ledger or the env aggregate? (NOT both.)

WAGF flood convention: agent decides AT START of year; flood
realised AT END of year; damage applies to agent's `flooded` flag
for the NEXT year's reflection.

## Pattern 3: Coarse agent ↔ asynchronous external query

Example: agent makes a one-shot call to an external risk-rating
service mid-decision.

Required documentation:
- **Latency model**: synchronous (blocks the agent) vs asynchronous
  (queue-based).
- **Idempotency**: does retrying the agent re-trigger the call?
  Costs (financial, computational, RNG-state) of duplicate calls.
- **Caching**: are external responses cached per (agent, year, query
  hash)?

WAGF currently has NO async external services in production; if one
is added, the coupling skill must verify all three above.

## Read-after-write within step (forbidden)

**DEFINITION**: an external-model output is consumed by the same
agent decision that produced its input.

**EXAMPLE (forbidden)**:
1. Agent decides `request_t = 100`.
2. External model returns `delivery_t = 80`.
3. Agent's SAME-STEP decision uses `delivery_t` to revise
   `request_t` to 120 (anticipatory).

This causes phantom acceleration: the agent "knows" the future
delivery and gaming the system before the decision is closed.

**ALLOWED**:
1. Agent decides `request_t = 100`.
2. External returns `delivery_t = 80`.
3. Agent stores `delivery_t` for NEXT step.
4. Agent's `request_{t+1}` decision uses `delivery_t`.

## Aggregation rule cheat-sheet

| External signal | Daily → Annual aggregation |
|-----------------|----------------------------|
| Reservoir volume | last (year-end snapshot) |
| Inflow / outflow | sum (annual total) |
| Drought index | mean (year-average) OR max (peak severity) |
| Shortage tier | max (worst tier hit) |
| Flood depth | max (per agent over event window) |
| Damage cost | sum (cumulative over events) |
| Probability of failure | 1 - prod(1 - daily_prob) |

The choice is domain-specific; document the choice in
`coupling_contract_report.md`.

## When the agent step is finer than the external step

Example: agent decides daily; external model only produces monthly
flood probabilities.

Required documentation:
- **Forward-fill rule**: agent re-uses last-known external value for
  daily steps until next external update (vs interpolation, vs
  re-running external each agent step).
- **Risk underestimate flag**: forward-filled stale external values
  may underestimate variance; document this caveat in any results
  table.
