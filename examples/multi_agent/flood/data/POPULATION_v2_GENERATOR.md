# Paper 3 v2 Population Generator

Regenerate from `examples/multi_agent/flood`:

```bash
python paper3/prepare_agents_v2.py --seed 42 --n-per-cell 200
```

`--large-n` sets `--n-per-cell 1000` for the parametric reference population.

## Sources by Variable

| Variable(s) | Source | Method |
|---|---|---|
| `agent_id` | Generated | Sequential `H0001...` after tenure-balanced sampling. |
| `survey_id` | Survey marginal | Carried from the sampled survey respondent for demographic traceability. |
| `tract_id` | Generated | Fixed to `PRB` for the Passaic River Basin setup. |
| `tenure` | Survey marginal, design-balanced | Samples exactly `n_per_cell` `Owner` and `n_per_cell` `Renter` rows. |
| `income_bracket` | Survey marginal | Carried from the sampled respondent. |
| `income` | Survey marginal plus generated jitter | Starts from the bracket midpoint and adds seeded within-bracket uniform jitter, clamped to bracket bounds. |
| `household_size`, `generations`, `has_vehicle`, `has_children`, `has_elderly`, `housing_cost_burden`, `zipcode` | Survey marginal | Carried from the sampled respondent. |
| `flood_experience`, `flood_frequency`, `sfha_awareness`, `recent_flood_text`, `insurance_type`, `post_flood_action` | Survey marginal | Carried from the sampled respondent. |
| `sc_score`, `pa_score`, `tp_score`, `cp_score`, `sp_score` | Survey conditional | Drawn jointly from one survey row conditional on tenure, income tertile, and flood-experience status. |
| `mg`, `mg_criteria_met` | Generated reference | Recomputed from legacy 2-of-3 criteria for backward compatibility only. MG is not a v2 design variable. |
| `rcv_building`, `rcv_contents` | Generated | Existing `generate_rcv` helper. |
| `grid_x`, `grid_y`, `flood_zone`, `flood_depth`, `longitude`, `latitude` | Generated from PRB raster | Existing `assign_flood_zones` helper and PRB raster cell pools. |
| `elevated`, `has_insurance`, `relocated`, `cumulative_damage`, `cumulative_oop` | Generated/initialized | Existing profile initialization conventions; insurance is inferred from survey insurance text. |

## Conditional Construct Draw

The generator computes income tertile cuts from `cleaned_survey_full.csv`, then
builds survey-row pools for:

`tenure (Owner/Renter) x income tertile (low/mid/high) x flood_experience (False/True)`.

For each synthetic household, the five construct scores are drawn together from
one survey row in the matching pool. This preserves the within-respondent
correlation among SC, PA, TP, CP, and SP rather than drawing each construct
independently.

Fallback ladder for sparse pools:

1. Full pool: `tenure x income_tertile x flood_experience`, if at least 5 survey rows.
2. Wider pool: `tenure x flood_experience`, if the full pool has fewer than 5 rows.
3. Widest pool: `tenure`, if the tenure/flood pool is also sparse.

The script prints fallback counts and the full conditional strata with fewer
than 5 survey rows. The minimum-pool threshold is 5 (review W4): below this the
draw would repeat the same survey row excessively for a 200-agent cell, so the
stratum is widened one level to preserve construct diversity. Tertile cuts are
computed from the survey bracket-midpoint `income` distribution; each synthetic
agent's tertile is then looked up on its JITTERED income (boundary cases near a
cut are negligible given the small within-bracket jitter).

## Flood-zone assignment note (review C2)

Flood zones reuse the existing `assign_flood_zones` helper. For agents WITHOUT
flood experience, that helper still applies a 70% / 50% flood-prone split keyed
on the `mg` reference column (mg=70%, non-mg=50%). So although MG is retired as a
sampling axis, it still conditions the no-experience flood-zone draw via the
retained reference column. This is intentional (keeps the spatial exposure
structure comparable to v1) but is NOT a design variable in the cognitive/
behavioral layer.

## MG Note

MG/NMG is retired as a v2 population axis. The `mg` column remains in the CSV
only so unchanged downstream code and older analysis scripts can read the same
`HouseholdProfile` schema. The generator does not use MG to sample the
population or to stratify the construct draw.
