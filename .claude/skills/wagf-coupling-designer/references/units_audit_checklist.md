# Units audit checklist

Use this while drafting the coupling contract. The audit-side reference
is `model-coupling-contract-checker/references/unit_compatibility.md`.

## Unit traps

- Decimal vs whole percent
  - Trap: the agent emits `8` and the adapter treats it as `800%` instead of `8%`.
  - Detect: inspect one trace and compute both interpretations by hand.
  - Fix: declare decimal fraction `[0.0, 1.0]` or whole percent `[0, 100]` in every table row.

- Absolute vs delta
  - Trap: `$150000` property value is consumed as `$5000` annual change, or vice versa.
  - Detect: compare the value against prior state and expected magnitude.
  - Fix: suffix names with `_total`, `_delta`, `_per_year`, or `_one_time`.

- Time units
  - Trap: years become months silently because a model step counter is named `t`.
  - Detect: write the physical duration next to every loop index.
  - Fix: declare `agent_timestep`, `model_timestep`, and aggregation rule in the contract.

- Currency base
  - Trap: nominal USD and constant-year USD are mixed in the same loss table.
  - Detect: search inputs and outputs for `usd`, `cost`, `loss`, and `npv`.
  - Fix: declare base year, discount rate, and whether values are nominal, real, or NPV.

- Spatial length and volume
  - Trap: feet and meters, or acre-feet and cubic meters, are converted twice or not at all.
  - Detect: sanity-check known magnitudes such as Lake Mead elevation in feet and capacity in MAF.
  - Fix: convert exactly once at the adapter boundary and name the owning side.

- Temporal aggregation
  - Trap: annual demand is compared to monthly supply without sum, mean, max, first, or last.
  - Detect: compare row counts per year and inspect the aggregation code.
  - Fix: declare the aggregation rule per variable, not once for the whole model.

- Agent-level vs aggregate
  - Trap: per-household damage is compared with community-total damage.
  - Detect: check whether IDs are present and whether totals equal sums across IDs.
  - Fix: suffix variables with `_per_agent`, `_per_household`, `_aggregate`, or `_basin_total`.

- Categorical encoding
  - Trap: one-hot, ordinal, and string labels are treated as interchangeable.
  - Detect: inspect allowed values and ask whether order carries meaning.
  - Fix: declare encoding, allowed labels, and forbidden arithmetic on nominal categories.

- Rate vs stock
  - Trap: MAF/yr flow is added to MAF storage without multiplying by elapsed time.
  - Detect: dimensional analysis: every addition must share units.
  - Fix: separate `_maf`, `_maf_per_year`, and `_maf_this_step` variables.

- Probability horizon
  - Trap: per-event probability is read as annual probability or lifetime risk.
  - Detect: ask "probability over what interval and conditional on what event?"
  - Fix: encode horizon in the variable name, such as `flood_prob_annual`.

- Index vs physical value
  - Trap: a drought index in `[0, 1]` is treated as precipitation in inches or mm.
  - Detect: compare the variable name against its stated physical unit and range.
  - Fix: name indices as `_index` or `_score`; reserve physical units for measured quantities.

- Datum and reference frame
  - Trap: elevation above mean sea level is compared with flood depth at a parcel.
  - Detect: ask "relative to what reference surface?"
  - Fix: declare datum for elevation and local reference for depth.

If the source schema is silent, do not infer the unit from domain habit.
Ask the PhD to name it before drafting the adapter.
