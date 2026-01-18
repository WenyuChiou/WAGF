# Design Document: Multi-Agent Social Constructs (The "5 Pillars")

To simulate realistic social dynamics and policy impacts, the framework adopts 5 core psychological constructs. These act as "Lego bricks" that provide standardized reasoning inputs for the LLM agents.

## 1. Threat Perception (TP)
*   **Definition**: Composed of **preparedness**, **worry**, and **awareness**. Similar to threat appraisal but focused on the subjective feeling of vulnerability.
*   **Data Sources**: Past flood frequency, news reports, neighbor gossip.
*   **Impact**: High TP accelerates adaptation (Insurance/Elevation); Extreme TP triggers Relocation.

## 2. Coping Perception (CP)
*   **Definition**: Composed of **self-efficiency** (self-efficacy), **mitigation-cost**, and **mitigation-efficiency** (response efficacy).
*   **Data Sources**: Household income, government subsidy rates, skill costs.
*   **Impact**: Low CP blocks expensive actions like Elevation, even if TP is High.

## 3. Stakeholder Perception (SP)
*   **Definition**: Considers how individuals view the **trustworthiness**, **expertise**, **involvement**, and **influence** of other stakeholders, such as governments, insurance companies, or community organizations, in the adaptation process.
*   **Data Sources**: Payout speed/success (from Memory), subsidy availability, policy transparency.
*   **Impact**: High SP increases insurance uptake and government program participation; Low SP leads to "Do Nothing" or non-institutional adaptation (Elevation).

## 4. Social Capital (SC)
*   **Definition**: A form of capital embedded in **social networks**, **trust**, and **norms**.
*   **Data Sources**: Social Observation (e.g., "30% of neighbors have elevated").
*   **Impact**: Peer pressure logic—agents are more likely to adapt if they observe successful neighbors doing the same.

## 5. Place Attachment (PA) - *Emotional Bond*
*   **Definition**: Emotional connection to the community and past investment in the home.
*   **Data Sources**: Tenure (years in community), existing adaptations (sunk cost logic).
*   **Impact**: High PA significantly delays Relocation, even under moderate flood threat.

---

## Implementation Status
*   **Single-Agent Phase**: TP and CP are fully implemented.
*   **Multi-Agent Phase**: SP, SC, and PA will be integrated via the `SocialModule` and `InteractionHub` in upcoming releases.
