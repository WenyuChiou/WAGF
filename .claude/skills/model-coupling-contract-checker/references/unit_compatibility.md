# Unit compatibility cheatsheet

Common WAGF units and gotchas. The skill must NOT assume a convention
when the schema is silent — it must ask.

## Volume

| Unit | Symbol | Conversion |
|------|--------|------------|
| Cubic metre | m³ | base SI |
| Acre-foot | ac-ft | 1 ac-ft = 1233.48 m³ |
| Million acre-feet | MAF | 1 MAF = 1.23348 × 10⁹ m³ |
| Gallons (US) | gal | 1 gal = 0.003785 m³ |
| Litre | L | 1 L = 0.001 m³ |

WAGF irrigation uses **MAF** in irrigation_env.py and
agent_types.yaml. Mixing MAF with m³ silently is a Class-A bug.

## Flow rate

| Unit | Symbol | Conversion |
|------|--------|------------|
| Cubic metre per second | m³/s | base SI |
| Cubic metre per year | m³/yr | × 1 / (365.25 × 86400) |
| Acre-feet per year | ac-ft/yr | annual budget |
| MAF per year | MAF/yr | basin-scale |

WAGF irrigation flows are **MAF/yr**.

## Lake elevation

| Unit | Symbol | Conversion |
|------|--------|------------|
| Feet above mean sea level | ft | base for Lake Mead |
| Metres above mean sea level | m | 1 ft = 0.3048 m |

WAGF Lake Mead in **feet**. Tier 1 shortage = 1075 ft. Dead pool =
895 ft. Reference points must use the same datum.

## Cost / currency

| Convention | Notes |
|------------|-------|
| Nominal USD | year of dollar matters; document base year |
| Real USD (2020 base) | inflation-adjusted |
| Annualised cost | per-year stream over asset lifetime |
| One-shot cost | total at time of action |
| NPV | discounted lifetime; declare discount rate |

WAGF flood costs are typically **nominal USD**, one-shot at action
year. Document the base year for any cross-year comparison.

## Probability

| Convention | Notes |
|------------|-------|
| Per-event probability | conditional on realisation |
| Per-year probability | annualised |
| Return-period years | T years; per-year prob = 1/T |
| Lifetime probability | over multi-year horizon |

WAGF flood-event probabilities are **per-year**, derived from a
return-period curve. Be explicit when reporting "the agent estimated
30% flood probability" — over what horizon?

## Depth

| Unit | Symbol | Conversion |
|------|--------|------------|
| Metres | m | base SI |
| Feet | ft | 1 ft = 0.3048 m |
| Inches | in | 1 in = 0.0254 m |

WAGF flood depths are typically **feet** (US convention).
Ground-elevation vs water-surface-elevation distinction matters: a
flood depth of 3 ft AT THE HOUSE is different from a water surface
elevation of 1078 ft (which depends on house elevation).

## Coupled-system scaling

When values move between systems, conversion happens at one specific
boundary. That boundary must be documented:

```
Agent decides volume in MAF
    ↓ (no conversion — both sides use MAF)
Reservoir module updates in MAF
    ↓ (1 MAF = 1.234 × 10⁹ m³ if external CSV uses m³)
Hydrologic forcing in m³
```

Anti-pattern: convert in two places (one in the runner, one in the
adapter). Convert exactly once at the contract boundary; document
which side owns the conversion.

## Sanity-check magnitudes

If the user shows you a number, sanity-check the magnitude:

- Lake Mead total capacity: ~28 MAF
- Lake Mead annual flow: ~10 MAF
- Per-CRSS-agent water right: typically 0.001–1 MAF/yr
- US household water use: ~0.0003 MAF/yr (so household ABM in MAF
  would have absurdly small numbers)

A demand value of "1000 MAF/agent" is impossible; flag immediately.
