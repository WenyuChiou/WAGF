# S1. Prompt Templates and Response Format

This section documents the complete prompt templates and structured response formats used in the Water Agent Governance Framework (WAGF). The framework implements two distinct agent-based models: (1) a flood adaptation model using Protection Motivation Theory (PMT) constructs, and (2) an irrigation demand management model using dual-appraisal cognitive constructs (Water Scarcity Assessment and Adaptive Capacity Assessment). Both models use large language models (LLMs) to generate agent decisions within governance-constrained environments.

## S1.1 Flood Homeowner Prompt Template

The flood homeowner prompt integrates multiple information sources to simulate realistic decision-making under uncertainty. The template combines personal situation awareness, historical flood experience, episodic memory retrieval, social influence, institutional messaging, and financial constraints.

### Complete Template

```
You are a homeowner (Agent ID: {agent_id}) in the Passaic River Basin, New Jersey.

### YOUR SITUATION
- Income: {income_range}
- Household Size: {household_size} people
- Generations in Area: {residency_generations}
- Flood Zone: {flood_zone}
- Flood Experience: {flood_experience_summary}
- Property Value: ${rcv_building:,.0f} (building) + ${rcv_contents:,.0f} (contents)
- Current Status: {elevation_status_text}
- Insurance: You currently {insurance_status} flood insurance.

### YOUR FLOOD HISTORY
- Total flood events experienced: {flood_count}
- Years since last flood: {years_since_flood}
- Cumulative damage to date: ${cumulative_damage:,.0f}
- Cumulative out-of-pocket costs: ${cumulative_oop:,.0f}

### RELEVANT MEMORIES
{memory}

### CRITICAL RISK ASSESSMENT
It is crucial to accurately assess your flood risk based on your personal flood history, memories, and current situation. Consider how recent or distant your flood experiences are — threat perceptions naturally evolve with time and new experiences. Your decisions must reflect a realistic understanding of potential dangers and your vulnerability.

### POLICY UPDATES THIS YEAR
- NJ Government (NJDEP Blue Acres): {govt_message}
- FEMA/NFIP Insurance: {insurance_message}

### WORLD EVENTS
{global_news}

### LOCAL NEIGHBORHOOD
{social_gossip}

### FINANCIAL DETAILS (YOUR SPECIFIC COSTS)
- Annual NFIP Premium: ${current_premium:,.0f}/year
- Elevation Subsidy Rate: {subsidy_rate:.0%}
- Elevation Cost Estimates (before subsidy):
  * 3 feet above BFE: ~$45,000 (your cost after subsidy: ~${elevation_cost_3ft:,.0f})
  * 5 feet above BFE: ~$80,000 (your cost after subsidy: ~${elevation_cost_5ft:,.0f})
  * 8 feet above BFE: ~$150,000 (your cost after subsidy: ~${elevation_cost_8ft:,.0f})
  * NOTE: Elevation requires 6-12 months of construction, temporary relocation, and significant disruption to daily life. Many homeowners find the process stressful and costly beyond the dollar amount.
- Blue Acres Buyout Offer: ~${buyout_offer:,.0f} (based on property value)
  * NOTE: Accepting a buyout means permanently leaving your home, neighborhood, and community ties. The process typically takes 1-3 years and involves considerable emotional stress.
- NFIP Deductible: $1,000 (structure) / $1,000 (contents)
- NFIP Coverage Limits: $250,000 (structure) / $100,000 (contents)
{insurance_cost_text}

### IMPORTANT: DECISION CALIBRATION CONTEXT
Consider these empirical base rates as context for your decision:
- **do_nothing is the most common choice.** 60-70% of homeowners choose do_nothing in any given year. This reflects status quo bias, financial constraints, and competing priorities.
- **Elevation is uncommon.** Only 3-12% of homeowners ever elevate over a full decade. Elevation is a major undertaking with significant costs and disruption.
- **Buyout is uncommon.** Fewer than 15% participate in buyout programs. However, severely affected homeowners with repeated flooding may rationally choose buyout.
- **If your flood zone is LOW:** Structural actions (elevation, buyout) are generally unnecessary. Prefer do_nothing or insurance.
- **Insurance uptake is moderate.** About 30-50% of homeowners in flood zones have insurance. If you have been personally flooded or are in a HIGH flood zone, insurance is a reasonable choice.
- **After a flood:** Many homeowners (35-65%) still choose do_nothing even after experiencing flooding — but those with severe damage and adequate resources may take action.

### ADAPTATION OPTIONS
{options_text}

**Sub-options** (include in your response if applicable):
- If choosing INSURANCE: specify coverage type (1=Structure+Contents, 2=Contents-only)
- If choosing ELEVATION: specify feet above Base Flood Elevation (3, 5, or 8 feet)
- If choosing BUYOUT: this is irreversible (you leave the community permanently)

**Secondary Action** (OPTIONAL):
You may propose ONE additional action this year if budget allows.
For example: elevate AND buy insurance, or buy insurance AND do nothing else.
Set "secondary_decision" to 0 if you only want one action.
Note: You cannot combine elevation with buyout.

### EVALUATION CRITERIA
{criteria_definitions}

Rating Scale: {rating_scale}

Based on your situation, memories, financial constraints, and PMT profile, evaluate each criterion and make your decision.
Respond ONLY with valid JSON in this format:
{response_format}
```

### Placeholder Variable Definitions

The template uses dynamic placeholders populated at runtime from agent profiles, simulation state, and memory systems.

| Placeholder | Source | Description |
|------------|--------|-------------|
| `{agent_id}` | Agent profile | Unique identifier (e.g., "HH_001") |
| `{income_range}` | Census ACS data | Income bracket label (e.g., "$50k-$75k") |
| `{household_size}` | Census data | Number of household members |
| `{residency_generations}` | Agent profile | Duration of community ties (1-5 generations) |
| `{flood_zone}` | FEMA flood maps | Risk category (LOW, MODERATE, HIGH) |
| `{flood_experience_summary}` | Simulation history | Qualitative summary of past flood exposure |
| `{rcv_building}`, `{rcv_contents}` | Property valuations | Replacement Cost Value for structure and contents |
| `{elevation_status_text}` | Agent state | Current elevation status (e.g., "Not elevated", "Elevated 5 ft above BFE") |
| `{insurance_status}` | Agent state | Insurance status text ("have" or "do not have") |
| `{flood_count}` | Event counter | Total flood events experienced by agent |
| `{years_since_flood}` | Temporal calculation | Time since most recent flood event |
| `{cumulative_damage}` | Financial tracking | Total property damage to date (dollars) |
| `{cumulative_oop}` | Financial tracking | Total out-of-pocket costs (deductibles, uninsured losses) |
| `{memory}` | HumanCentricMemoryEngine | Top-k retrieved episodic memories formatted as narrative text |
| `{govt_message}` | Institutional agent | NJDEP policy announcement (e.g., subsidy rate changes) |
| `{insurance_message}` | Institutional agent | FEMA/NFIP policy updates (e.g., premium adjustments) |
| `{global_news}` | News module | General climate/weather headlines |
| `{social_gossip}` | Social network module | Neighbor decision summaries (up to 2 contacts) |
| `{current_premium}` | Insurance calculator | Agent-specific annual NFIP premium |
| `{subsidy_rate}` | Policy parameter | Current government subsidy percentage for elevation |
| `{elevation_cost_3ft}`, `{elevation_cost_5ft}`, `{elevation_cost_8ft}` | Cost calculator | Agent-specific post-subsidy elevation costs |
| `{buyout_offer}` | Valuation formula | Blue Acres buyout offer based on property value |
| `{insurance_cost_text}` | Insurance module | Additional premium details if already insured |
| `{options_text}` | Skill registry | Formatted list of available actions (do_nothing, buy_insurance, elevate_house, buyout_program) |
| `{criteria_definitions}` | `ma_agent_types.yaml` | PMT construct definitions (TP, CP, SP, SC, PA) |
| `{rating_scale}` | Configuration | Five-point scale definition (VL, L, M, H, VH) |
| `{response_format}` | Configuration | JSON schema with field specifications and delimiter markers |

### Design Rationale

**Decision Calibration Context (lines 49-56).** This section injects empirical base rates from FEMA and NFIP literature to anchor LLM output distributions. Without this anchoring, small LLMs (under 12B parameters) tend to over-select dramatic actions (elevation, buyout) relative to observed human behavior. The calibration text explicitly states that do_nothing is the modal choice (60-70% annually) and that structural adaptations are uncommon (3-12% for elevation over a decade). This design addresses the known tendency of instruction-tuned models to generate "interesting" or "proactive" decisions that diverge from empirical distributions.

**Episodic Memory Integration (line 20).** The `{memory}` placeholder retrieves top-k significant memories using a weighted scoring function that combines recency, emotional valence, and relevance to current context. The HumanCentricMemoryEngine implements memory consolidation, decay, and arousal-based encoding to simulate realistic long-term memory effects on decision-making.

**Social Influence (line 33).** The `{social_gossip}` field implements peer effect mechanisms by including summaries of neighbors' recent decisions. This enables diffusion of adaptive behaviors through social networks, consistent with empirical observations of clustered adoption patterns in flood mitigation programs.

**Financial Transparency.** Lines 35-47 provide complete cost information specific to each agent's financial situation (post-subsidy costs, income-adjusted premiums). This transparency is critical for realistic cost-benefit reasoning by LLMs.

## S1.2 Irrigation Farmer Prompt Template

The irrigation farmer prompt uses a chain-of-thought structure that forces sequential appraisal steps before action selection. This design reflects the dual-appraisal framework from stress and coping theory (Lazarus & Folkman, 1984), operationalized as Water Scarcity Assessment (WSA) and Adaptive Capacity Assessment (ACA).

### Complete Template

```
{narrative_persona}
{water_situation_text}
{feedback_dashboard}
Your memory includes:
{memory}

You currently {conservation_status} water conservation practices.
Your ability to implement changes to your water management is {aca_hint}.
You {trust_forecasts_text} climate and hydrological forecasts. You {trust_neighbors_text} neighboring farmers' water management advice.

First, assess your WATER SUPPLY situation by considering:
- Water Supply Outlook: Is your water supply abundant, adequate, tight, or critically short this season?
- Demand-Supply Balance: Is your current water request well matched to the available supply, or is there a gap?
Then rate your water_scarcity_assessment.

Next, assess your ADAPTIVE CAPACITY by considering:
- Capacity to Adjust: How easily could you change your water demand (financial, technical, labor)?
- Cost of Change: What would it cost you (financially, operationally) to adjust your irrigation practices?
- Benefit of Current Path: What is the advantage of keeping your current water demand level unchanged?
Then rate your adaptive_capacity_assessment.

Now, choose one of the following water management actions:
{options_text}
Your decision should reflect your farming philosophy and risk tolerance.

{rating_scale}

Please respond using the EXACT JSON format below.
- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.
- "decision" MUST be the NUMERIC ID (1-5) from the options list.
- Ensure all keys match the format exactly.
{response_format}
```

### Placeholder Variable Definitions

| Placeholder | Source | Description |
|------------|--------|-------------|
| `{narrative_persona}` | `irrigation_personas.py` | Cluster-specific personality text (2-3 sentences describing behavioral archetype) |
| `{water_situation_text}` | `IrrigationEnvironment` | Current year signals: precipitation percentile, Lake Mead elevation, shortage tier (0-3), drought index |
| `{feedback_dashboard}` | `run_experiment.py` | Supply-demand gap assertion (e.g., "Last year you requested 95,000 AF but received 80,000 AF — a shortfall of 15,000 AF") |
| `{memory}` | HumanCentricMemoryEngine | Top-k retrieved memories from past water years |
| `{conservation_status}` | Agent state | Current conservation practice status ("use" or "do not use") |
| `{aca_hint}` | Persona configuration | Cluster-anchored capacity text ("limited", "moderate", or "strong") based on FQL-derived persona parameters |
| `{trust_forecasts_text}` | Agent profile | Trust level text for institutional forecasts ("trust" or "do not fully trust") |
| `{trust_neighbors_text}` | Social network | Trust level for peer advice |
| `{options_text}` | Skill registry | Five-skill menu: (1) increase_large, (2) increase_small, (3) maintain_demand, (4) decrease_small, (5) decrease_large |
| `{rating_scale}` | Configuration | Five-point scale definition (VL=Very Low, L=Low, M=Medium, H=High, VH=Very High) |
| `{response_format}` | `agent_types.yaml` | JSON schema with four fields: reasoning, water_scarcity_assessment, adaptive_capacity_assessment, decision |

### Design Rationale

**Chain-of-Thought Structure (lines 11-21).** The prompt explicitly instructs agents to perform appraisals before choosing actions, using sequential framing: "First assess... Then rate... Next assess... Now choose." This structure reduces impulsive action selection by forcing intermediate reasoning steps. The approach is theoretically grounded in dual-process theories of decision-making, where System 2 (deliberative) processing is activated through explicit prompting.

**Persona-Based Anchoring.** The `{narrative_persona}` text is cluster-specific and derived from k-means clustering of Fuzzy Q-Learning (FQL) parameters from Hung & Yang (2021). Three clusters emerge: (1) Aggressive (high exploration, low regret), (2) Forward-Looking Conservative (high discount factor, high regret), and (3) Myopic Conservative (low discount factor, low exploration). Each persona receives tailored framing that primes the LLM toward cluster-appropriate decision patterns.

**Adaptive Capacity Hint.** The `{aca_hint}` field provides a soft anchor for capacity assessment that correlates with persona risk tolerance. Aggressive agents receive "strong" capacity hints, enabling more volatile demand adjustments. Myopic agents receive "limited" hints, promoting status quo bias. This mechanism translates FQL parameter heterogeneity into LLM-compatible contextual cues.

**Field Count Constraint.** The irrigation response format is deliberately limited to four fields (reasoning, WSA, ACA, decision). Empirical testing with gemma3:4b revealed that response formats exceeding four fields frequently produce unparseable output due to model capacity constraints. The flood format includes more fields (9 total with PMT constructs and sub-options) because larger models (12B, 27B parameters) can handle the complexity without degradation.

## S1.3 Response Format Specification

Both agent types use delimited JSON responses with strict schema enforcement. The governance engine validates all responses against the schema before execution, blocking malformed outputs.

### Flood Response Format

**Delimiter Markers:**
- Start: `<<<DECISION_START>>>`
- End: `<<<DECISION_END>>>`

**Required Fields (in order):**

1. **threat_perception** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: TP_LABEL
   - Definition: "How serious do you perceive the flood risk? Consider likelihood and potential severity."

2. **coping_perception** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: CP_LABEL
   - Definition: "How confident are you that mitigation options (insurance, elevation, buyout) are effective and affordable?"

3. **stakeholder_perception** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: SP_LABEL
   - Definition: "How much do you trust institutions (NJDEP, FEMA/NFIP) to provide reliable support?"

4. **social_capital** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: SC_LABEL
   - Definition: "How connected are you with neighbors? Are they taking protective actions?"

5. **place_attachment** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: PA_LABEL
   - Definition: "How emotionally attached are you to your home and community?"

6. **decision** (choice, required)
   - Type: Numeric ID (1-4)
   - Options: 1=do_nothing, 2=buy_insurance, 3=elevate_house, 4=buyout_program

7. **elevation_feet** (numeric, optional)
   - Type: Integer {3, 5, 8}
   - Required if: decision=3 (elevate_house)
   - Description: Height above Base Flood Elevation

8. **insurance_coverage** (choice, optional)
   - Type: Integer {1, 2}
   - Required if: decision=2 (buy_insurance)
   - Options: 1=Structure+Contents, 2=Contents-only

9. **secondary_decision** (secondary_choice, optional)
   - Type: Numeric ID (0-4)
   - Default: 0 (no secondary action)
   - Constraints: Cannot combine elevation with buyout

10. **reasoning** (text, optional)
    - Type: Free text
    - Description: Explanation of decision rationale (2-3 sentences)

**Example Valid Response:**
```json
<<<DECISION_START>>>
{
  "threat_perception": "H",
  "coping_perception": "M",
  "stakeholder_perception": "L",
  "social_capital": "M",
  "place_attachment": "VH",
  "decision": 2,
  "insurance_coverage": 1,
  "secondary_decision": 0,
  "reasoning": "My flood zone is HIGH and I've been flooded twice in the past five years. Insurance provides financial protection without requiring me to leave my community. I can afford the premium given my income bracket."
}
<<<DECISION_END>>>
```

### Irrigation Response Format

**Delimiter Markers:**
- Start: `<<<DECISION_START>>>`
- End: `<<<DECISION_END>>>`

**Required Fields (in order - "Reasoning Before Rating"):**

1. **reasoning** (text, required)
   - Type: Free text
   - Description: Thought process explaining appraisals and decision (2-3 sentences)
   - Rationale: Forces deliberative processing before action selection

2. **water_scarcity_assessment** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: WSA_LABEL
   - Description: Assessment of water supply situation relative to demand
   - Hint: "One sentence on whether your water supply feels abundant, adequate, or tight."

3. **adaptive_capacity_assessment** (appraisal, required)
   - Type: Categorical (VL, L, M, H, VH)
   - Construct: ACA_LABEL
   - Description: Assessment of ability to adjust water use
   - Hint: "One sentence on how well you can adapt your water use."

4. **decision** (choice, required)
   - Type: Numeric ID (1-5)
   - Options: 1=increase_large, 2=increase_small, 3=maintain_demand, 4=decrease_small, 5=decrease_large

**Example Valid Response:**
```json
<<<DECISION_START>>>
{
  "reasoning": "Lake Mead is at 1045 feet, which is in Tier 2 shortage. My water allocation was cut by 15% last year. I need to be cautious about increasing demand given the persistent drought conditions.",
  "water_scarcity_assessment": "H",
  "adaptive_capacity_assessment": "M",
  "decision": 3
}
<<<DECISION_END>>>
```

### Key Design Differences

**Field Ordering.** The flood format follows a "Appraisal-Then-Reasoning" pattern (PMT constructs first, reasoning last), allowing agents to skip reasoning if desired. The irrigation format enforces "Reasoning-Before-Rating" (reasoning first, appraisals and decision after), which improves deliberation quality for small LLMs but requires all four fields.

**Field Count Constraint.** The irrigation format uses exactly four fields due to gemma3:4b's demonstrated failure mode with larger schemas. Beyond four fields, the model frequently generates nested structures (e.g., `{"label": "H", "reason": "..."}`) instead of the required flat format, resulting in parse failures. The flood format uses nine fields because validation testing used larger models (12B, 27B) capable of handling complex schemas.

**Sub-Option Handling.** The flood format includes conditional sub-fields (elevation_feet, insurance_coverage) that are required only when specific primary decisions are selected. The irrigation format has no sub-options because skill execution uses environment-controlled magnitude sampling (Gaussian per-skill distributions) rather than agent-specified values.

**Secondary Actions.** The flood format supports multi-skill execution (up to two actions per year) via the secondary_decision field. The irrigation format is single-skill only, reflecting the design constraint that water demand decisions are mutually exclusive within a given year.

### Schema Enforcement

The governance engine validates all responses using the following checks:

1. **Delimiter Presence.** Response must contain both start and end markers.
2. **JSON Validity.** Content between delimiters must parse as valid JSON.
3. **Required Fields.** All fields marked as required must be present with non-null values.
4. **Type Checking.** Appraisal fields must be one of {VL, L, M, H, VH}. Choice fields must be valid numeric IDs.
5. **Conditional Requirements.** Sub-fields (elevation_feet, insurance_coverage) must be present when their triggering decision is selected.
6. **Range Validation.** Numeric fields must satisfy min/max constraints (e.g., elevation_feet in {3, 5, 8}).

If validation fails, the governance engine generates an intervention report documenting the failure mode and triggers a retry (up to 3 attempts). If all retries fail, the agent is assigned the default skill (maintain_demand for irrigation, do_nothing for flood).
