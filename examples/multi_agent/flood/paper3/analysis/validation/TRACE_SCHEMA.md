# Trace Schema Reference

This document defines the expected structure of decision trace dicts consumed
by the C&V validation package. Traces are JSONL records — one JSON object per
line, one line per agent-year decision.

## Minimal Required Fields

Every trace **must** include at minimum:

```json
{
  "agent_id": "H001",
  "year": 1,
  "approved_skill": {"skill_name": "buy_insurance"},
  "outcome": "APPROVED"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `agent_id` | `str` | Yes | Unique agent identifier. Empty strings are skipped. |
| `year` | `int` | Yes | Simulation year (1-indexed). Used for temporal ordering. |
| `approved_skill` | `dict` or `str` | Yes | Governance-approved action. Dict with `skill_name` key preferred. |
| `outcome` | `str` | Yes | `"APPROVED"`, `"REJECTED"`, `"UNCERTAIN"`, or `""`. |

## Full Trace Structure

```json
{
  "agent_id": "H001",
  "year": 3,

  "skill_proposal": {
    "skill_name": "buy_insurance",
    "reasoning": {
      "TP_LABEL": "H",
      "CP_LABEL": "M"
    }
  },

  "approved_skill": {
    "skill_name": "buy_insurance"
  },

  "outcome": "APPROVED",
  "validated": true,

  "flooded_this_year": true,

  "state_before": {
    "flood_zone": "HIGH",
    "flood_count": 2,
    "years_since_flood": 0,
    "flooded_this_year": true,
    "mg": true,
    "income": 35000,
    "elevated": false,
    "bought_out": false,
    "tenure": "Owner"
  },

  "state_after": {}
}
```

## Field Reference

### Top-Level Fields

| Field | Type | Default | Used By | Description |
|-------|------|---------|---------|-------------|
| `agent_id` | `str` | `""` | All modules | Unique agent identifier |
| `year` | `int` | `0` | state_inference, benchmarks | Simulation year |
| `outcome` | `str` | `""` | state_inference, l2_macro, benchmarks | Governance verdict |
| `validated` | `bool` | `True` | state_inference | Whether trace passed runtime validation |
| `flooded_this_year` | `bool` | `False` | benchmarks (do_nothing_postflood) | Hazard occurrence flag |
| `skill_proposal` | `dict`/`str` | `{}` | trace_reader, l1_micro, cgr | LLM's proposed action + reasoning |
| `approved_skill` | `dict`/`str` | `{}` | trace_reader | Governance-approved action |
| `state_before` | `dict` | `{}` | cgr, hallucinations | Agent state before decision |
| `state_after` | `dict` | `{}` | state_inference | Agent state after decision (often sparse) |

### skill_proposal (nested dict)

| Field | Type | Used By | Description |
|-------|------|---------|-------------|
| `skill_name` | `str` | trace_reader, l2_macro | Proposed action name |
| `reasoning` | `dict` | trace_reader, theories | Contains construct labels |
| `reasoning.TP_LABEL` | `str` | trace_reader, cgr | Threat Perception: `VL`/`L`/`M`/`H`/`VH`/`UNKNOWN` |
| `reasoning.CP_LABEL` | `str` | trace_reader, cgr | Coping Perception: `VL`/`L`/`M`/`H`/`VH`/`UNKNOWN` |

For custom domains, `reasoning` can contain any construct labels. The
`BehavioralTheory.extract_constructs()` method controls which fields are read.

### approved_skill (nested dict or string)

| Field | Type | Description |
|-------|------|-------------|
| `skill_name` | `str` | Approved action name |

Falls back to bare string if not a dict. If missing, `trace_reader._extract_action()`
falls back to `skill_proposal`, then `"do_nothing"`.

### state_before (nested dict)

These fields are used by CGR grounding and hallucination checking. For flood domain:

| Field | Type | Default | Used By | Description |
|-------|------|---------|---------|-------------|
| `flood_zone` | `str` | `"LOW"` | cgr (TP grounding) | `"HIGH"`, `"MODERATE"`, `"LOW"` |
| `flood_count` | `int` | `0` | cgr (TP grounding) | Cumulative flood events experienced |
| `years_since_flood` | `int`/`None` | `None` | cgr (TP grounding) | Years since last flood; None if never flooded |
| `flooded_this_year` | `bool` | `False` | cgr, benchmarks | Whether flooded this year |
| `mg` | `bool` | `False` | cgr (CP grounding), null_model | Marginalized group flag |
| `income` | `float` | `50000` | cgr (CP grounding) | Household income |
| `elevated` | `bool` | `False` | cgr, hallucinations | Whether home is elevated |
| `bought_out` | `bool` | `False` | hallucinations | Whether buyout completed |
| `tenure` | `str` | `"Owner"` | null_model | `"Owner"` or `"Renter"` |

**For custom domains**: `state_before` can contain any fields. The
`GroundingStrategy.ground_constructs()` method controls which fields are read.

## Outcome Values

| Value | Meaning | Treatment in Validation |
|-------|---------|------------------------|
| `"APPROVED"` | Governance approved the proposal | Included in all analyses |
| `"REJECTED"` | Governance rejected the proposal | Excluded from state inference; counted as `do_nothing` in benchmarks |
| `"UNCERTAIN"` | Governance uncertain | Excluded from state inference |
| `""` (empty) | Missing/default | Treated as approved (included) |

## Action Normalization

Raw action names are normalized via `_normalize_action()`. Default flood aliases:

| Canonical | Aliases |
|-----------|---------|
| `buy_insurance` | `purchase_insurance`, `get_insurance`, `insurance`, `buy_contents_insurance`, `buy_structure_insurance`, `contents_insurance` |
| `elevate` | `elevate_home`, `home_elevation`, `raise_home`, `elevate_house` |
| `buyout` | `voluntary_buyout`, `accept_buyout`, `buyout_program` |
| `relocate` | `move`, `relocation` |
| `retrofit` | `floodproof`, `flood_retrofit` |
| `do_nothing` | `no_action`, `wait`, `none` |

Custom domains can provide their own aliases via the `action_aliases` parameter.

## Inferred State Fields

These are NOT in raw traces — they are computed by `_extract_final_states_from_decisions()`
and merged into the agent profiles DataFrame as `final_*` columns:

| Inferred Field | DataFrame Column | Rule |
|----------------|-----------------|------|
| `has_insurance` | `final_has_insurance` | `"last"` — True if last action == `buy_insurance` |
| `elevated` | `final_elevated` | `"ever"` — True if agent ever chose `elevate` |
| `bought_out` | `final_bought_out` | `"ever"` — True if agent ever chose `buyout` |
| `relocated` | `final_relocated` | `"ever"` — True if agent ever chose `relocate` |

Custom domains can define their own rules via the `state_rules` parameter.

## Which Modules Use Which Fields

| Module | Required Fields | Optional Fields |
|--------|----------------|-----------------|
| **L1 (CACR, R_H, EBE)** | `skill_proposal`, `approved_skill` | `state_before` (for hallucination check) |
| **CGR** | `skill_proposal.reasoning`, `state_before` | — |
| **L2 (EPI)** | `agent_id`, `year`, `approved_skill`, `outcome` | `flooded_this_year`, `state_before` |
| **State inference** | `agent_id`, `year`, `approved_skill`, `outcome`, `validated` | `state_after` |
| **Null model** | (generates traces, doesn't consume) | — |

## Agent Profiles CSV

The `agent_profiles` DataFrame (separate from traces) must include:

| Column | Type | Required By |
|--------|------|-------------|
| `agent_id` | `str` | L2 metrics (join key) |
| `tenure` | `str` | Flood benchmarks (elevation_rate, renter_uninsured) |
| `flood_zone` | `str` | Flood benchmarks (insurance_sfha, renter_uninsured) |
| `mg` | `bool` | Flood benchmarks (mg_adaptation_gap), L2 supplementary |

Custom domains may have different required columns depending on their benchmarks.

## Example: Minimal Irrigation Trace

```json
{
  "agent_id": "CRSS_42",
  "year": 15,
  "skill_proposal": {
    "skill_name": "decrease_small",
    "reasoning": {
      "WSA_LABEL": "H",
      "ACA_LABEL": "M"
    }
  },
  "approved_skill": {"skill_name": "decrease_small"},
  "outcome": "APPROVED",
  "validated": true,
  "state_before": {
    "lake_mead_level": 1040,
    "income": 45000,
    "current_demand": 0.35
  }
}
```
