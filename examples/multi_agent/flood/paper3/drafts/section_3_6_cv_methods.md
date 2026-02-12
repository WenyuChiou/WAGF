# Section 3.6: Calibration and Validation Protocol

Agent-based models face persistent credibility challenges in the absence of standardized validation protocols (Grimm et al., 2005; Windrum et al., 2007). LLM-governed ABMs introduce additional concerns: how do we distinguish genuine emergent behavior from LLM hallucination, and how do we ensure that system-level patterns arise from theoretically grounded micro-processes rather than statistical artifacts? We propose a three-level validation framework extending the Pattern-Oriented Modeling (POM) approach (Grimm et al., 2005) to address the unique challenges of LLM-ABMs in natural hazard contexts.

## Level 1: Micro-Level Action Coherence

L1 validation assesses whether individual agent decisions satisfy domain-theoretic constraints. We compute three metrics over all agent-timestep decisions:

**Construct-Action Coherence Rate (CACR)**: The proportion of decisions consistent with Protection Motivation Theory (Rogers, 1983; Grothmann & Reusswig, 2006) given the agent's threat perception (TP) and coping perception (CP) labels. We distinguish CACR_raw --- unassisted LLM coherence before governance filtering --- from CACR_final, the system-level coherence after validation. The gap between these measures quantifies governance impact. Governance validators function analogously to institutional constraints that enforce real-world feasibility barriers (e.g., affordability checks, eligibility requirements). We additionally report CACR by quadrant (TP_high/low x CP_high/low) to detect systematic reasoning failures in specific appraisal regions. We require CACR >= 0.75.

**Hallucination Rate (R_H)**: The fraction of decisions proposing physically impossible actions (e.g., re-elevating an already-elevated home, renters attempting structural modifications). We require R_H <= 0.10 to ensure that LLM outputs respect domain constraints.

**Effective Behavioral Entropy (EBE)**: Shannon entropy of the action distribution, normalized by the theoretical maximum log2(K) for K distinct actions. The resulting ratio (0 = degenerate single-action, 1 = uniform random) provides a reference distribution: a credible model should exhibit structured diversity (0.1 < EBE_ratio < 0.9), neither collapsing to a single dominant action nor behaving as a random number generator.

## Level 2: Macro-Level Empirical Plausibility

L2 validation evaluates whether aggregate system behavior reproduces known empirical patterns. Following Grimm et al. (2005), we adopt pattern-oriented validation: the model must simultaneously satisfy multiple independent structural benchmarks. We define the Empirical Plausibility Index (EPI) as the weighted proportion of eight benchmarks falling within empirically supported ranges:

| # | Benchmark | Range | Category | Source |
|---|-----------|-------|----------|--------|
| B1 | Insurance rate in SFHA | 0.30--0.60 | Calibration | Choi et al. (2024); de Ruig et al. (2023) |
| B2 | Overall insurance rate | 0.15--0.55 | Calibration | Gallagher (2014) |
| B3 | Elevation rate | 0.03--0.12 | Validation | FEMA P-312 |
| B4 | Buyout/relocation rate | 0.02--0.15 | Validation | Blue Acres program data |
| B5 | Post-flood inaction rate | 0.35--0.65 | Calibration | Grothmann & Reusswig (2006); Bubeck et al. (2012) |
| B6 | MG adaptation gap (composite) | 0.10--0.30 | Calibration | Environmental justice literature |
| B7 | Renter uninsured rate (SFHA) | 0.15--0.40 | Validation | Kousky (2017) |
| B8 | Insurance lapse rate | 0.05--0.15 | Validation | Gallagher (2014) |

We distinguish *calibration targets* (B1, B2, B5, B6) --- which informed prompt engineering and validator thresholds during iterative development --- from *validation targets* (B3, B4, B7, B8), which were held out and not used to tune model behavior. We require EPI >= 0.60 for structural plausibility. The MG adaptation gap (B6) uses a composite measure (any protective action: insurance, elevation, buyout, or relocation) rather than insurance alone, as structural adaptations better capture inequality in protective capacity.

REJECTED proposals are tracked as supplementary metrics (not benchmarks). When governance blocks a proposed action (e.g., elevation fails an affordability check), the agent's effective outcome is involuntary non-adaptation. This mirrors real-world institutional barriers and endogenously generates inequality between marginalized and non-marginalized groups without explicitly programming disparate outcomes.

## Level 3: Cognitive Consistency and Sensitivity

L3 validation examines whether LLM responses exhibit stable persona differentiation and theoretically expected sensitivity to risk drivers, independent of the primary experiment.

**Intraclass Correlation (ICC)**: We compute ICC(2,1) across 6 archetypes x 3 vignettes x 30 repetitions (Shrout & Fleiss, 1979). We observe ICC = 0.964, indicating that 96.4% of decision variance derives from between-archetype differences rather than within-archetype noise. This high value warrants a dimensionality caveat: with strong binary constraints (owner vs. renter, high-income vs. low-income), the effective dimensionality is low. ICC quantifies *consistency*, not *diversity*.

**Effect Size (eta-squared)**: Variance in risk appraisal scores explained by flood depth. We observe eta-squared = 0.33, indicating moderate sensitivity to hazard severity.

**Directional Sensitivity**: The proportion of agents who increase protective action probability following severe floods (depth >= 1.0m). We observe 75% directional consistency, satisfying the >= 75% threshold aligned with PMT predictions.

## Methodological Claims

To our knowledge, this represents the first quantitative multi-level validation framework for LLM-ABMs in natural hazard research. By anchoring micro-coherence to PMT, macro-patterns to empirical distributions, and cognitive stability to variance decomposition, we provide a replicable protocol for assessing LLM-ABM credibility beyond subjective plausibility judgments.

**Scope Conditions**: All results derive from Gemma 3 4B, a locally deployed open-source model representing a lower bound on model capacity. We interpret base rate ignorance (e.g., renters over-purchasing insurance relative to empirical rates) as bounded rationality rather than model deficiency: real households also exhibit salience-driven over-response (Kunreuther et al., 2013). The governance framework compensates for limited LLM capacity by enforcing hard constraints, demonstrating that smaller models can produce credible simulations when properly scaffolded.
