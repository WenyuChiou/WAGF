# Supplementary Material: Calibration vs Emergence in LLM-ABM Design

## S1. Design Inputs vs Emergent Outputs

We distinguish between **design inputs** (parameters and constraints specified by the modeler) and **emergent outputs** (patterns that arise from agent interactions without being explicitly targeted). This distinction is critical for interpreting RQ1–RQ3 findings.

### S1.1 Design Inputs (Calibrated)

| Component | Design Choice | Calibration Method |
|-----------|--------------|-------------------|
| Household prompts | Natural-language persona descriptions including flood zone, income, tenure, and available actions | Iterative refinement (v5→v7d) against L2 empirical benchmarks |
| Validators (12) | Rule-based constraints: affordability (cost > 3× income), flood zone appropriateness, income gate (<$40K), elevation experience (flood_count ≥ 2) | Derived from FEMA program eligibility criteria and empirical thresholds |
| Agent profiles (400) | Balanced design: 200 owners + 200 renters, income/MG distribution from PRB Census data | Survey-based initialization |
| Institutional initial conditions | Starting subsidy = 50% (FEMA HMGP standard), CRS = 15% | FEMA program defaults |
| Flood scenario | Per-agent depth grids from PRB hydrological simulation (2011–2023) | Historical reconstruction |
| Action space | 4 owner skills (insurance, elevation, buyout, do_nothing) + 3 renter skills (contents insurance, relocate, do_nothing) | Matched to Traditional ABM action set |

### S1.2 Emergent Outputs (Not Calibration Targets)

| Output | Why It Is Emergent |
|--------|-------------------|
| TP accumulation (3.06→3.37 over 13yr) | No instruction to accumulate threat perception; agents re-evaluate TP each year from context |
| CP ceiling at M (~2.79) | No upper bound on CP; agents independently assess coping as moderate regardless of flood count |
| TP-CP gap MG > NMG (0.66 vs 0.50) | No target gap; emerges from income differences → CP variation + flood exposure → TP variation |
| Action exhaustion (do_nothing 46%→67%) | No instruction to stop adapting; emerges from agents exhausting affordable options |
| Government subsidy trajectory (52%→65%) | Government LLM agent decides autonomously; no target trajectory specified |
| Insurance CRS oscillation (15–20%) | Insurance LLM agent decides autonomously |
| MG affordability blocking differential (+33%) | Not a calibration target; emerges from validator × income × subsidy interaction |
| Renter RL ~2% (vs Traditional ABM ~24%) | Not calibrated to any target; agents reason about relocation costs independently |

### S1.3 Calibration Analogy with Traditional ABMs

The calibration process in LLM-ABMs is analogous to parameter estimation in Traditional ABMs:

| Aspect | Traditional ABM (FLOODABM) | LLM-ABM (This Study) |
|--------|---------------------------|---------------------|
| Calibration medium | Bayesian posterior coefficients from survey data | Prompt text + validator thresholds |
| Number of free parameters | ~20 regression coefficients + TP shock/decay parameters | Prompt text (qualitative) + 12 validator thresholds |
| Calibration targets | Survey response distributions | L2 empirical benchmarks (EPI) |
| Degrees of freedom in output | ~52K agents × 13yr × 4 actions | 400 agents × 13yr × 7 actions |
| Ratio (output DOF / calibration targets) | ~170,000 : ~20 | ~36,400 : 8 |

In both approaches, calibration targets represent a small fraction of the model's output space. The findings reported in RQ1–RQ3 are drawn from the uncalibrated output space.

## S2. Empirical Basis for Low-Frequency Action Rates

Three household actions exhibit low adoption rates in the LLM-ABM (elevation ~1.9%, buyout ~1.3%, renter relocation ~2%). We document that these rates are consistent with empirical evidence, and that the constraints described in agent prompts reflect documented real-world barriers rather than artificial restrictions.

### S2.1 Home Elevation (EH): LLM = 1.9%, Traditional ABM cumulative ~7%

**Cost barriers.** Residential elevation costs range from $37,000 to $250,000 depending on structure type and location (FEMA P-312, "Above the Flood"; St. Charles Parish reports average project cost of $185,000 including construction, engineering, and temporary relocation). Under FEMA HMGP, the federal cost-share is 75%, leaving homeowners responsible for 25% ($9,000–$60,000+). For households earning less than $40,000, this out-of-pocket cost exceeds annual income.

**Non-economic barriers.** Elevation projects require:
- Building permits and engineering assessments (weeks to months)
- Licensed contractors with specialized equipment (limited availability in post-disaster periods)
- Temporary relocation during construction (6–18 months)
- Grant application through state/local government intermediaries (homeowners cannot apply directly to FEMA)
- Competition for limited HMGP funds (typically 7.5–15% of total disaster assistance)

**Market disincentive.** Buyer aversion research documents that home buyers show negative preference for elevated homes despite lower flood damage risk, creating a market disincentive for voluntary elevation (UC Davis working paper, "Buyer aversion to flood-resistant homes").

**Uncertainty.** Zarekarizi et al. (2020, Nature Communications) demonstrate that neglecting cost and flood depth uncertainties systematically biases elevation decisions, and that while 68% of homeowners could benefit financially from elevation, actual adoption rates remain far lower.

**Key references:**
- FEMA P-312, "Above the Flood: Elevating Your Floodprone House" (2000)
- Zarekarizi, M., Srikrishnan, V., & Keller, K. (2020). Neglecting uncertainties biases house-elevation decisions to manage riverine flood risks. Nature Communications, 11, 5361.
- FEMA Hazard Mitigation Grant Program documentation (fema.gov/grants/mitigation)

### S2.2 Buyout Programs (BP): LLM = 1.3%, empirical < 3%

**Low national participation.** Since the late 1990s, approximately 40,000 homes have been purchased through FEMA-funded buyout programs across 49 states — a small fraction of the millions of properties in flood-prone areas. Most counties have used buyout programs only once or twice (Mach et al., 2019).

**Process barriers.** Buyout programs typically require 2–5 years from application to completion. Local governments must navigate FEMA grant applications, procure matching funds, administer the process, and relocate participants. Financial complexities such as existing mortgages and out-of-pocket expenses further limit participation.

**Place attachment.** Homeowners in historically nonwhite communities often resist buyouts due to deep place attachment, distrust in government, and lack of affordable housing nearby (The Conversation, 2023; McGhee et al., 2020). Research shows that unless homeowners can stay close to their original community, find similar neighborhoods, and reduce flood risk, most will not participate voluntarily.

**Equity concerns.** FEMA-funded buyouts have been concentrated in neighborhoods with lower income and greater social vulnerability, while being more likely to occur in counties with higher overall population and income (Mach et al., 2019).

**Key references:**
- Mach, K. J., Kraan, C. M., Hino, M., Siders, A. R., Johnston, E. M., & Field, C. B. (2019). Managed retreat through voluntary buyouts of flood-prone properties. Science Advances, 5(10), eaax8995.
- McGhee, D. J., Binder, S. B., & Albrecht, E. A. (2020). Promoting equity in retreat through voluntary property buyout programs. Journal of Environmental Studies and Sciences, 10, 401–413.
- Binder, S. B., & Greer, A. (2024). Barriers to Coastal Managed Retreat: Evidence from New Jersey's Blue Acres Program. Marine Resource Economics, 39(3).

### S2.3 Renter Relocation (RL): LLM = 2%, Traditional ABM = 24%

The divergence in renter relocation rates is the largest between the two frameworks (MAD = 21.9 percentage points). We argue that the LLM rate better reflects empirical barriers to renter mobility.

**Financial barriers.** Relocation requires security deposits, first/last month rent, and moving costs ($3,000–$8,000). For low-income renters, these costs represent a substantial fraction of annual income. Screening requirements (credit checks, background checks, verifiable income) further exclude vulnerable renters from replacement housing (Desmond & Shollenberger, 2015).

**Insurance coverage gap.** Only 0.2% of all residential NFIP policies cover renter contents, and approximately 45% of renter households lack even standard renters insurance (FEMA FloodSmart; Harvard JCHS, 2024). Without insurance payouts, renters lack the financial buffer to support relocation after a flood event.

**Shelter-in-place tendency.** Low-income renters who experience forced displacement typically relocate to poorer, higher-crime neighborhoods (Desmond & Shollenberger, 2015). Awareness of this outcome may discourage voluntary relocation, particularly when social networks and community ties are concentrated in the current location.

**Why the Traditional ABM overestimates RL.** The Traditional ABM models renter relocation as a Bernoulli trial with probability ~24%, calibrated from survey responses about relocation *intention*. This probability does not account for the financial and logistical barriers that prevent intention from translating to action. The LLM-ABM's reasoning process explicitly considers these barriers (moving costs, lease constraints, housing availability), producing a rate (~2%) closer to observed post-disaster relocation behavior.

**Key references:**
- Desmond, M., & Shollenberger, T. (2015). Forced Relocation and Residential Instability among Urban Renters. Social Service Review, 89(2), 227–262.
- Harvard Joint Center for Housing Studies. (2024). Renters Vulnerable to Climate Disasters Amid Insurance Gaps.
- FEMA FloodSmart. Understanding Flood Insurance for Renters (agents.floodsmart.gov).

## S3. Intention-Action Gap: Renter Relocation (22% vs 2%)

The largest divergence between the Traditional ABM and the LLM-ABM is in renter relocation (MAD = 21.9 percentage points). In the Traditional ABM (published in [Paper 2 reference]), approximately 22% of renters choose relocation in a given year, a rate calibrated from survey-measured relocation intention probabilities through Bayesian posterior estimation. In the LLM-ABM, only 2% of renters relocate.

We argue that these two rates measure different constructs, and that the gap between them quantifies the **intention-action gap** for renter relocation in flood contexts.

### S3.1 What the Traditional ABM measures

The Traditional ABM models renter relocation as a Bernoulli trial with probability derived from PMT constructs (TP, CP, SP, SC, PA). The Bayesian posteriors are estimated from household survey responses, which capture **stated intention** ("Would you consider relocating if flooded?"). Survey-calibrated probabilities reflect what respondents say they would do, not what they actually do when faced with the decision.

### S3.2 What the LLM-ABM measures

The LLM-ABM agent receives the same decision context (flood experience, financial status, neighborhood information) and reasons through the decision in natural language. The reasoning process explicitly considers:
- Moving costs (security deposits, first/last month rent, moving expenses: $3,000–$8,000)
- Lease constraints and penalties
- Housing search difficulty (credit/background checks, limited affordable inventory)
- Loss of social networks and community ties
- Uncertainty about replacement housing quality

These barriers are documented in empirical literature (Desmond & Shollenberger, 2015; Harvard JCHS, 2024) and represent real constraints that prevent relocation intention from translating to action.

### S3.3 The intention-action gap as a finding

The 20 percentage-point gap between the two frameworks is consistent with the broader intention-action gap documented in protective action research. Bubeck et al. (2012) distinguish between *adaptation motivation* (the intention to protect) and *adaptation capacity* (the ability to act on that intention), noting that capacity constraints can suppress action even when motivation is high. Grothmann and Reusswig (2006) similarly note that PMT-based models predict intention, not behavior, and that post-intentional barriers (cost, access, feasibility) mediate the relationship.

For renter relocation specifically, the gap is expected to be large because:
1. Only 0.2% of NFIP policies cover renter contents (FEMA FloodSmart), leaving most renters without financial buffer for relocation
2. Low-income renters face screening barriers (credit checks, verifiable income) that exclude them from replacement housing (Desmond & Shollenberger, 2015)
3. Post-disaster housing markets tighten, reducing available inventory precisely when demand peaks

### S3.4 Implications for both models

This finding does not invalidate the Traditional ABM's 22% rate. That rate correctly represents the survey-calibrated probability of relocation *consideration*. However, it does suggest that probability-based models that do not explicitly represent post-intentional barriers may systematically overestimate realized relocation rates. The LLM-ABM's contribution is not that it produces a "better" number, but that its reasoning process makes the intention-action gap **visible and interpretable** through agent-level reasoning traces.

### Key references
- Bubeck, P., Botzen, W. J. W., & Aerts, J. C. J. H. (2012). A review of risk perceptions and other factors that influence flood mitigation behavior. Risk Analysis, 32(9), 1481–1495.
- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. Natural Hazards, 38, 101–120.
- Desmond, M., & Shollenberger, T. (2015). Forced Relocation and Residential Instability among Urban Renters. Social Service Review, 89(2), 227–262.
- Harvard Joint Center for Housing Studies. (2024). Renters Vulnerable to Climate Disasters Amid Insurance Gaps.

## S4. Summary

The low adoption rates for elevation, buyout, and relocation in the LLM-ABM are consistent with empirical evidence and reflect documented barriers. The prompt descriptions of these barriers are factual representations of program constraints, not artificial limitations imposed to achieve specific model outcomes. The key difference from the Traditional ABM is that the LLM reasoning process explicitly incorporates these barriers into each agent's decision calculus, while the Traditional ABM encodes only the aggregate probability of adoption without representing the underlying mechanisms.
