# Expert Q&A Script: Defending the SQ2 Analysis

_Use these answers if questioned by experts, reviewers, or scholars._

## Q1: "Is your Entropy calculation valid? Did you account for agents leaving?"

**Answer:**
"Yes. We used a rigorous **Active Agent Filter**.
We calculated Shannon Entropy ($H = -\sum p \log p$) **only** on the population active in that specific year.
We explicitly excluded agents who had 'Already Relocated' in previous years to prevent zero-inflation.
We _did_ include agents who chose to 'Relocate' in the current year, as that is a valid decision signal."

## Q2: "Why do the groups start with different values in Year 1? Shouldn't they be identical?"

**Answer:**
"This is the **Governance Observer Effect**.
Even before the first decision is made, the **System Prompt** for Group B is different (it contains the Governance Protocols).
This additional context acts as a 'Cognitive Brake,' forcing agents to deliberate more deeply rather than relying on the base model's greedy probability (Herding).
Thus, Governance increases diversity (+0.24 bits) **immediately** by breaking the initial instinct to panic."

## Q3: "Your 8B model has 0 Entropy. Are you saying it's broken?"

**Answer:**
"It indicates **Mode Collapse**, not a broken model.
Our audit showed that without governance, the 8B model converges to a **Monoculture of Elevation** (97% of agents doing the same thing).
This proves that 'Intelligence' (Scale) does not guarantee 'Diversity'. Without governance, even smarter models can get stuck in a single collective behavioral loop."

## Q4: "So, is Governance just forcing them to be random?"

**Answer:**

## Q5: "Why does the 1.5B model start with higher Entropy (1.85) than the 8B model (1.06)?"

**Answer:**
"This reflects the difference between **'Confusion'** and **'Confidence'**.

- **1.5B Model (Small/Confused):** H=1.85. It lacks a strong prior, so it splits its vote: 41% Relocate, 30% Elevate, 20% DoNothing. This look like 'diversity', but it's actually just noise/instability.
- **8B Model (Large/Confident):** H=1.06. It has a stronger prior for inaction. 72% choose 'DoNothing'. It is 'surer' of itself, which lowers the entropy.
- **Takeaway:** Higher entropy isn't always better _initially_. For 1.5B, high entropy meant chaos. For 8B, low entropy meant laziness."
