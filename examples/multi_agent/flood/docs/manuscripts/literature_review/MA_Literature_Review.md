# Literature Review: Multi-Agent Flood Adaptation Simulation

**Date:** 2026-01-19
**Status:** Comprehensive Review (N=73 papers)

## 1. Introduction

This literature review supports the design and validation of the Multi-Agent Flood Adaptation Simulation. The simulation models the interactions between households, government, and insurance providers in a flood-prone coastal community. Our review focuses on three critical domains that drive agent behavior and system dynamics:

1.  **Household Flood Risk Perception & Bounded Rationality**: Investigating how individuals process qualitative risk information and social signals.
2.  **Government Resource Allocation & Equity**: Analyzing the trade-offs between relief and resilience, and the impact on marginalized groups.
3.  **Flood Insurance Markets**: Examining the implications of risk-based pricing (Risk Rating 2.0) and adverse selection.

---

## 2. Topic 1: Household Risk Perception & Social Influence

### 2.1 Qualitative vs. Quantitative Risk Perception

Traditional economic models assume agents act on precise probability data. However, empirical research confirms that households rely heavily on qualitative, experiential, and heuristic information.

- **Heuristics & Biases**: Individuals often rely on "heuristics" (mental shortcuts) rather than complex calculations. **Botzen et al. (2015)** and **Bubeck et al. (2012)** demonstrate that perceived probability is often disregarded if it is below a certain "threshold of concern," consistent with Prospect Theory.
- **Experiential Learning**: **Bradford et al. (2012)** and **Burningham et al. (2008)** highlight that direct experience with flooding is a stronger driver of adaptation than statistical maps. "Ankle-deep" vs "knee-deep" descriptions are more salient than "1% AEP".
- **Protection Motivation Theory (PMT)**: **Grothmann & Reusswig (2006)** established PMT as the dominant framework for flood adaptation, separating "Threat Appraisal" (risk perception) from "Coping Appraisal" (ability to act). This supports our agent architecture's split between risk sensing and decision-making.

### 2.2 Social Networks & Information Diffusion

Information does not exist in a vacuum; it spreads through social networks, creating "social amplification" of risk.

- **Social Contagion**: **Lo (2013)** and **Baber et al. (2016)** show that the decision to buy insurance or elevate a home is significantly influenced by neighbors. Observing a neighbor adapt acts as "social proof".
- **The "Hub" Effect**: **Houston et al. (2015)** and **Kaewkitipong et al. (2016)** identify that certain agents (community leaders or hyper-connected individuals) act as "hubs," accelerating information diffusion.
- **Misinformation**: **Starbird et al. (2014)** warn that social networks can also spread misinformation, leading to maladaptive behaviors (e.g., underestimating risk due to a neighbor's "lucky escape").

---

## 3. Topic 2: Government Resource Allocation & Equity

### 3.1 The Relief vs. Resilience Trade-off

Governments face a temporal dilemma: spending on immediate relief creates political capital, while resilience investment pays off only in the long term (and often invisibly).

- **The "Reactive" Bias**: **Healy & Malhotra (2009)** provide seminal evidence that voters reward politicians for relief spending but punish them for prevention spending (tax cost). This explains the persistent under-investment in mitigation.
- **Economic ROI**: Despite the political bias, **Headwaters Economics (2018)** and the **National Institute of Building Sciences (2019)** report a 6:1 to 13:1 return on investment for pre-disaster mitigation.
- **Budgetary Friction**: **Michel-Kerjan (2010)** notes that disaster relief is often funded by "emergency supplemental" appropriations, while resilience must compete in the standard tight budget cycle.

### 3.2 Equity & Marginalized Groups (MG)

Resource allocation mechanisms often inadvertently exacerbate existing inequalities.

- **Disparate Impact**: **Fothergill & Peek (2004)** and **Tate et al. (2016)** document how socially vulnerable populations (low income, minorities) suffer disproportionately higher losses and have slower recovery trajectories.
- **Bureaucratic Barriers**: **Begley et al. (2012)** found that grant allocation processes often favor communities with higher administrative capacity (wealthier), leaving marginalized groups behind.
- **Cost-Benefit Bias**: **Thaler et al. (2018)** argue that standard Cost-Benefit Analysis (CBA) favors protecting high-value assets (wealthy districts), implicitly deprioritizing low-income neighborhoods where property values—and thus "avoided damages"—are lower.

---

## 4. Topic 3: Flood Insurance Markets & Risk Rating 2.0

### 4.1 From Subsidy to Actuarial Rates (Risk Rating 2.0)

The transition of the National Flood Insurance Program (NFIP) to Risk Rating 2.0 represents a paradigm shift from broad zones to individual structural ratings.

- **Correction of Cross-Subsidies**: **Kousky et al. (2018)** and **Startz (2020)** explain that the old system (pre-2.0) forced low-risk inland homes to subsidize high-risk coastal homes. Risk Rating 2.0 aims to fix this.
- **Affordability Crisis**: **Dixon et al. (2006)** and **Horn (2022)** warn that "true risk pricing" makes insurance unaffordable for many low-income residents in flood zones, creating a "market penetration gap".

### 4.2 Adverse Selection & Market Stability

As prices rise to reflect true risk, the insurance pool faces stability threats.

- **Adverse Selection**: **Browne & Hoyt (2000)** and **Wagner (2022)** provide empirical evidence that as premiums rise, lower-risk individuals drop out, leaving a "worse" risk pool, necessitating further rate hikes—a potential "death spiral".
- **The "Protection Gap"**: **Bin & Landry (2013)** show that even with mandatory purchase requirements (e.g., for mortgages), compliance is often low, and voluntary uptake drops sharply as prices increase.

---

## 5. Bibliography

See `references.bib` for the complete list of 73 cited works in BibTeX format.
