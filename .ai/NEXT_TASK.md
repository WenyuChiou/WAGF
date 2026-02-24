# Next Task: Paper 3 — Institutional C&V Pilot (2026-02-24)

## Status: Pilot6 running — iterating government floor + insurance CRS cap

## Calibration History (This Session)
| Pilot | Gov Pattern | Ins Pattern | Issues |
|-------|-------------|-------------|--------|
| pilot2 | Monotonic 50→95% | CRS stuck 0% | PRB floods every year |
| pilot3 | 4 inc, 0 dec (no decrease) | 9 improve → CRS 45% | No decrease trigger; ins over-improves |
| pilot4 | Same (G7 threshold bug) | 5 improve → CRS 30% | G7: >0.55 vs =0.55; cooldown works |
| pilot5 | 4 inc, 6 dec → sub 25% | 5 improve → CRS 30% | Over-decrease; ins ignores prompt cap |
| pilot6 | G2 floor 45%, B.3 requires sub>50% | I6 soft cap 20% | TBD |

## Key Fixes Applied
1. Severity-gated prompts (SEVERE/MODERATE/NONE)
2. G5: require SEVERE for increase; G7: fiscal pullback (yssf≥4, sub>50%); G2: floor 45%
3. I6: CRS soft cap 20%; I7: 1-year cooldown between improvements
4. Community-mode flooded_household_count fix

## Files Modified
- `lifecycle_hooks.py`, `government.txt`, `insurance.txt`, `run_unified_experiment.py`

## NW Paper — Recent Session W Changes
- R1 rewritten: three-way comparison leads (Governed/Ungoverned/FQL), r defined with motivation
- Fig. 2 Panel (a) now has FQL line + expert review fixes applied
- Professor briefing tables + 10min talking points generated
- Word docs recompiled (v14)

## NW Paper — Remaining Tasks
1. Word count check (≤4,000)
2. Cover letter draft
3. Reference count verification
4. Additional seeds + Gemma-3 12B irrigation
