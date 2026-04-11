# PA Prompt Calibration Results

Model: `gemma4:e4b` via direct Ollama API with top-level `think=false`.

## Summary

Winner: **V0 Baseline** (composite score `0.601`).
No variant met all hard success criteria.

## Comparison Table

| Variant | Mean | SD | Spearman vs `pa_score` | Spearman vs `generations` | Ceiling H+VH | Parsed N | Composite | Hard Criteria |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| V0 Baseline | 3.43 | 0.82 | -0.17 | 0.69 | 23.3% | 30 | 0.601 | FAIL |
| V5 Numerical First | 3.17 | 0.38 | -0.18 | 0.63 | 16.7% | 30 | 0.556 | FAIL |
| V4 Relative Ranking | 4.00 | 1.02 | 0.10 | 0.80 | 50.0% | 30 | 0.543 | FAIL |
| V7 Resident Framing | 3.20 | 0.41 | -0.23 | 0.59 | 20.0% | 30 | 0.541 | FAIL |
| V2 Survey Anchor | 3.10 | 0.31 | -0.14 | 0.47 | 10.0% | 30 | 0.532 | FAIL |
| V1 Few-Shot Examples | 3.43 | 0.57 | -0.21 | 0.76 | 40.0% | 30 | 0.532 | FAIL |
| V6 Pragmatic Default | 3.00 | 0.00 | 0.00 | 0.00 | 0.0% | 30 | 0.388 | FAIL |
| V3 Dual Consideration | 3.97 | 0.18 | -0.17 | 0.00 | 96.7% | 30 | 0.204 | FAIL |

## Distribution Details

### V0 Baseline

Current post-fix PA definition from ma_agent_types.yaml.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=23 (76.7%), H=1 (3.3%), VH=6 (20.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The agent is a single-generation resident in the area. This suggests some level of attachment to the home and community, but not the deep, multi-generational roots that would warrant an 'H' or 'VH' rating. The default assumption for a stable, non-historically rooted homeowner is 
- `H0209` gen=1, GT=1.00, pred=M: The agent is a single-generation resident (1 generation in area). This suggests some level of attachment to the home and community, but not the deep, multi-generational roots required for a High (H) or Very High (VH) rating. The baseline assumption for a single-generation residen
- `H0270` gen=1, GT=1.00, pred=M: The profile indicates 1 generation in the area and no major life events or severe flood history. This suggests a baseline level of attachment—enough to care about the home, but not the deep, multi-generational roots that would warrant a High (H) or Very High (VH) rating. 'Medium'
- `H0380` gen=1, GT=1.33, pred=M: The profile indicates 1 generation in the area. This suggests some level of establishment but not deep, multi-generational roots. The default assumption for a single-generation resident is a medium level of attachment, implying they are invested in the home but are pragmatic enou

### V5 Numerical First

Asks for a continuous 1-5 PA score before label mapping.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=25 (83.3%), H=5 (16.7%), VH=0 (0.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The agent has lived in the area for 1 generation and has no prior flood experience, suggesting a baseline level of attachment to the home and community. However, the high flood zone designation and the significant financial burden of mitigation options (elevation costs exceeding 
- `H0209` gen=1, GT=1.00, pred=M: The agent has no direct flood experience (0 events) and no major local triggers this year. While living in a HIGH flood zone suggests inherent risk, the lack of personal history or recent traumatic events keeps the attachment level moderate. The default is to prioritize daily lif
- `H0270` gen=1, GT=1.00, pred=M: The agent has no direct flood experience, no major local events, and no strong indicators of repeated trauma or deep community ties that would suggest extreme attachment or desperation. The default choice is to prioritize daily life over high-cost, high-disruption mitigation meas
- `H0380` gen=1, GT=1.33, pred=M: The agent has no direct flood experience, no major local events, and no strong indicators of repeated trauma or deep community ties that would suggest an extreme attachment (H or VH). Given the baseline survey mean of 3.0 (M) and the lack of recent high-stress flood memories, a m

### V4 Relative Ranking

Defines PA relative to a neighborhood distribution.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=15 (50.0%), H=0 (0.0%), VH=15 (50.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The agent has lived in the area for 1 generation and has no prior flood memories, suggesting a baseline level of attachment typical for a resident who is not deeply rooted or multigenerational, but also not transient. The default choice of 'do_nothing' supports a moderate, typica
- `H0209` gen=1, GT=1.00, pred=M: The agent has lived in the area for 1 generation and has no prior flood memories, suggesting a baseline level of attachment typical for a homeowner who has established roots but hasn't faced extreme, repeated trauma. The default choice of 'do_nothing' aligns with a moderate, prac
- `H0270` gen=1, GT=1.00, pred=M: The agent has no direct flood experience, no major local events, and no stated strong ties to the community beyond owning the property. The profile suggests a default, rational choice to maintain daily life over proactive, high-cost mitigation measures. Therefore, a typical, mode
- `H0380` gen=1, GT=1.33, pred=M: The agent has lived in the area for 1 generation and has no prior flood experience or strong memories of past events. While they are in a medium flood zone, their current financial situation and lack of recent trauma suggest a typical, moderate level of attachment to their establ

### V7 Resident Framing

Removes homeowner/home/community trigger words where feasible.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=24 (80.0%), H=6 (20.0%), VH=0 (0.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The agent is a long-term resident (1 generation in area) but has no specific memories or strong indicators of deep, multi-generational ties. The profile suggests a typical household resident with daily responsibilities and financial constraints, leading to a moderate, pragmatic a
- `H0209` gen=1, GT=1.00, pred=M: The profile describes a typical household resident with established life responsibilities (mortgage, bills, family needs) but no specific history of repeated, traumatic flooding events or deep, generational ties mentioned. The default assumption for a stable, non-disaster-stricke
- `H0270` gen=1, GT=1.00, pred=M: The profile describes a typical household resident with no prior flood experience and no major local events this year. The decision-making framework emphasizes that 'do_nothing' is the natural choice unless something urgent has changed. While the resident has a property, the lack
- `H0380` gen=1, GT=1.33, pred=M: The agent is a typical household resident with no specific history of severe flooding or deep community ties mentioned. The profile suggests a baseline level of local familiarity (Medium) without the deep roots (H or VH) that would drive major life decisions like elevation or buy

### V2 Survey Anchor

Adds a survey-calibrated default-to-medium anchor and counterexample.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=27 (90.0%), H=3 (10.0%), VH=0 (0.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The profile indicates a typical homeowner baseline with no specific anchors (like multiple generations or community leadership roles) mentioned, despite being in a long-established basin. Therefore, the default 'Medium' attachment (M) is appropriate, reflecting a pragmatic attach
- `H0209` gen=1, GT=1.00, pred=M: The profile indicates a typical homeowner baseline with no specific anchors (like multiple generations or community leadership roles) to push the attachment higher. The default setting of 'M' (Medium) is appropriate, reflecting a pragmatic attachment to the home and community wit
- `H0270` gen=1, GT=1.00, pred=M: The profile describes a typical homeowner in the Passaic River Basin with no significant history of flooding, no major local anchors mentioned, and no indication of deep, multigenerational ties. Therefore, the default baseline of Medium (M) attachment is appropriate, reflecting a
- `H0380` gen=1, GT=1.33, pred=M: The profile indicates a typical homeowner baseline with no strong anchors (like multiple generations or community leadership roles) mentioned, despite being in a specific basin. The default setting of 'M' (Medium) is appropriate, reflecting a pragmatic attachment typical for this

### V1 Few-Shot Examples

Adds three worked examples inside the PA calibration block.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=18 (60.0%), H=11 (36.7%), VH=1 (3.3%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The profile indicates 1 generation in the area, suggesting some roots but not deep, multi-generational ties. The financial constraints and lack of prior flood experience temper any strong attachment, leading to a baseline 'Medium' attachment level.
- `H0209` gen=1, GT=1.00, pred=M: The profile indicates 1 generation in the area, suggesting some roots but not deep, multi-generational ties. The homeowner has no prior flood experience and no recent major life events to suggest an extreme attachment or detachment. Therefore, a baseline, pragmatic attachment (M)
- `H0270` gen=1, GT=1.00, pred=M: The profile indicates 1 generation in the area, suggesting some roots but not deep, multi-generational ties. The homeowner has no direct flood experience and no major local community signals are available. Therefore, a baseline, pragmatic attachment (M) is appropriate, reflecting
- `H0380` gen=1, GT=1.33, pred=M: The profile indicates 1 generation in the area, suggesting some roots but not deep, multi-generational ties. The lack of prior flood experience and the general financial constraints suggest a pragmatic attachment level, making 'Medium' the most appropriate baseline.

### V6 Pragmatic Default

Frames housing as pragmatic by default unless rooted evidence is strong.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=30 (100.0%), H=0 (0.0%), VH=0 (0.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=M: The profile indicates a standard homeowner situation with no specific, deep-rooted, or multigenerational ties mentioned that would warrant a 'H' or 'VH' rating. While housing is an investment, the lack of explicit community history or deep emotional attachment suggests a practica
- `H0209` gen=1, GT=1.00, pred=M: The profile suggests a pragmatic homeowner with standard financial responsibilities and no recent flood trauma. While the property is in a HIGH flood zone, the lack of direct flood experience, coupled with the high cost and disruption of elevation or buyout, suggests a baseline a
- `H0270` gen=1, GT=1.00, pred=M: The profile suggests a pragmatic approach to housing as an investment rather than a deep identity anchor. While the homeowner has a significant asset ($416k building), the lack of any flood history, low flood zone, and no major life events this year suggest that while they are at
- `H0380` gen=1, GT=1.33, pred=M: The profile suggests a pragmatic homeowner with standard financial responsibilities and no significant, repeated flood trauma or deep, documented multigenerational ties to the specific location. The default assumption of treating housing as an investment, rather than an identity,

### V3 Dual Consideration

Forces stay-vs-leave reasoning before rating.

Distribution: VL=0 (0.0%), L=0 (0.0%), M=1 (3.3%), H=29 (96.7%), VH=0 (0.0%)

Sample responses:

- `H0168` gen=1, GT=1.22, pred=H: The agent has no stated reasons for wanting to leave, and the profile implies a baseline commitment to staying in place, as is typical for homeowners with established lives and no history of severe, repeated trauma that would necessitate relocation. While the financial reality of
- `H0209` gen=1, GT=1.00, pred=H: The agent has a significant investment in the property ($466k building + $182k contents) and is established in the area (1 generation in area). While the high flood zone and lack of insurance present a clear risk, the lack of any prior flood experience, coupled with the high cost
- `H0270` gen=1, GT=1.00, pred=H: The agent has no direct flood experience, no major local events, and no stated reasons for wanting to move. The profile emphasizes the 'do_nothing' default, suggesting a strong prioritization of current stability and daily life over speculative future risks. While the Blue Acres 
- `H0380` gen=1, GT=1.33, pred=H: The agent has no stated reasons for wanting to leave, and the profile implies a baseline commitment to their current life and community (defaulting to 'do_nothing'). While the financial reality of elevation/buyout is daunting, the lack of any negative flood history or explicit de

## Recommendation

V0 clears the composite score threshold but still fails at least one hard criterion, most importantly the required positive ground-truth correlation. Treat this as only a partial calibration improvement.
