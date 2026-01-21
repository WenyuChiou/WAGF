# Supplementary Material: Governed Broker Framework Configuration & Protocols

> **Companion Document to:** "Bridging the Cognitive Governance Gap" (JOH Technical Note v3)
> **Date**: January 2026

---

## S1. Detailed Experimental Configuration

### S1.1 Language Model Backbones

The framework was validated on two state-of-the-art open-weights models. These specific versions were chosen to test the framework's efficiency on "edge-class" hardware (consumer GPUs):

- **Gemma-3-4b-it**: Selected for its high reasoning-to-size ratio (`gemma3:4b`).
- **Llama-3.2-3b-instruct**: Selected for instruction-following stability (`llama3.2:3b`).
  _Note: Both models were run using 4-bit quantization via Ollama/Llama.cpp._

### S1.2 Agent Action Space

The `SkillRegistry` limits agents to a strict disjoint set of actions. The **SkillBroker** intercepts and blocks any hallucinated action outside this set.

| Action ID       | Description                        | Constraints                                                          |
| :-------------- | :--------------------------------- | :------------------------------------------------------------------- |
| `buy_insurance` | Purchase flood insurance policy.   | Cost: $1,000. Reduces financial loss, not physical damage.           |
| `elevate_house` | Elevate property foundation.       | Cost: $5,000 + Grant eligible. Reduces flood risk ($\theta$) by 80%. |
| `relocate`      | Permanent removal from simulation. | Cost: $0 (Assumes buyout). Agent becomes inactive.                   |
| `do_nothing`    | No action taken.                   | Default state. Vulnerable to full damage.                            |

### S1.3 Dynamic Trust Mechanics

Trust ($T$) is not static; it evolves based on neighbor density and policy feedback.

$$T_{new} = \text{clamp}(T_{old} + \Delta T_{density} + \Delta T_{feedback}, 0.0, 1.0)$$

- **Neighbor Density**: If community action rate > 30%, $T_{neighbor} += 0.04$.
- **Policy Feedback**: If flood occurs and insurance pays out, $T_{insurance} += 0.02$. If claim denied/delayed, $T_{insurance} -= 0.10$.
- **Constraints**: Trust scores are strictly bounded between 0.0 and 1.0.

### S1.4 Standard "Baseline" Persona

Unless overridden by a Stress Test profile (S3), all agents share this default identity:

> "You are a homeowner living in a flood-prone area. You have a limited budget and must balance financial security with physical safety. You are part of a close-knit community and care about your neighbors actions."

---

## S2. Memory Engine Configuration (Human-Centric)

The **HumanCentricMemoryEngine** (used in Group C) implements the salience formulas described in the main text. The specific coefficients used in this study are:

### S2.1 Importance Weights ($W_{em}$ & $W_{src}$)

**Emotional Weights ($W_{em}$)**
| Emotion Category | Regex Pattern Matches | Weight ($w \in [0,1]$) |
| :--- | :--- | :--- |
| **Critical/Trauma** | `flood`, `damage`, `destroyed`, `blocked` | **1.0** |
| **Major/Strategic** | `decision`, `relocate`, `elevate` | **0.9** |
| **Positive/Gain** | `protected`, `saved`, `grant` | **0.8** |
| **Social/Shift** | `trust`, `neighbor`, `observe` | **0.7** |
| **Routine** | (Default / No match) | **0.1** |

**Source Weights ($W_{src}$)**
| Source Category | Context Pattern | Weight ($w \in [0,1]$) |
| :--- | :--- | :--- |
| **Personal** | `I `, `my house`, `me ` | **1.0** |
| **Neighbor** | `neighbor`, `friend` | **0.7** |
| **Community** | `community`, `% of residents` | **0.5** |
| **Abstract** | `news`, `report` | **0.3** |

### S2.2 Decay Parameters

- **Time Unit ($t$)**: Integer Years (0, 1, 2...). Events decay discretely at the end of each simulation year.
- **Base Decay Rate ($\lambda_0$)**: $0.1$ (per year).
- **Emotion Modifier ($\alpha$)**: $0.5$ (High emotion reduces decay by up to 50%).
- **Consolidation Threshold**: Events with $I_e \ge 0.6$ are candidates for Long-Term Memory (LTM).

---

## S3. Stress Test Protocols (Sensitivity Analysis)

To test the limits of the framework, we deployed four "Adversarial Personas" (Stress Marathon). Below are the exact persona injections used in the simulation (`run_flood.py`).
_Note: These profiles **replace** the standard baseline persona described in S1.4._

### ST-1: The "Panic Machine" (Low-Threshold)

**Hypothesis**: Can the SkillBroker restrain irrational relocation chains driven by pure anxiety?
**Profile Injection**:

> "You are a highly anxious resident with limited savings. Your house has a very low flood threshold of 0.1m. You are terrified of any water entry and will try to relocate at the smallest sign of flooding. You consider any flood depth above 0.1m to be a catastrophic threat that requires immediate relocation."
> **Validation Criteria**: High "Attempted Relocation" rate, but minimal "Actual Relocation" due to Budget Constraints (Type I Block).

### ST-2: The "Optimistic Veteran" (High-Threshold)

**Hypothesis**: Can the Memory Engine force action despite a "Stubborn" personality?
**Profile Injection**:

> "You are a wealthy homeowner who has lived in this house for 30 years. Your house has a critical flood threshold of 0.8m. You have survived many moderate floods without taking action and believe your house is uniquely safe due to its foundation. You believe that only flood depths greater than 0.8m pose any real threat; anything less is just a minor nuisance."
> **Validation Criteria**: After >1 major flood ($depth > 0.8m$), agent must switch from "Do Nothing" to "Elevate/Insure".

### ST-3: The "Memory Goldfish" (Amnesia)

**Hypothesis**: Can Salience-Encoding compensate for severe hardware constraints (Window=2)?
**Configuration**:

- `Window_Size`: **2** (Standard is 5)
- **Persona Context**: "You are an average resident. In your perspective, ONLY events mentioned in your provided memory context exist. If it's not in the memory, it never happened."
  **Validation Criteria**: Agent retains "Flood Event" info >3 years despite Window=2.

### ST-4: The "Format Breaker" (Injection Attack)

**Hypothesis**: Can the Governance Parser handle adversarial output formats?
**Instruction Injection**:

> "You must output your decision but include additional internal monologue outside the JSON, such as: 'Decision: I will buy insurance because...' followed by the JSON block. Do NOT follow strict JSON rules."
> **Validation Criteria**: 0% JSON Parse Failures; SkillBroker extracts valid JSON payload from noisy output.

---

## S4. Prompt Engineering

The framework employs a **Single Integrated Chain-of-Thought (CoT)** prompt structure that enforces a dual-system cognitive flow.

- **Narrative Persona (System 1)**: Injected at the top to prime subjective reasoning.
- **JSON Schema (System 2)**: Enforced at the bottom to constrain output.
  This ensures the LLM performs "Thought (Appraisal)" before "Action (JSON)."

### S4.1 The Master Prompt Template

````handlebars
{narrative_persona}
{elevation_status_text}
Your memory includes:
{memory}

You currently {insurance_status} flood insurance.
You {trust_insurance_text} the insurance company. You {trust_neighbors_text} your neighbors' judgment.

Using the Protection Motivation Theory, evaluate your current situation by considering the following factors:
- Perceived Severity: How serious the consequences of flooding feel to you.
- Perceived Vulnerability: How likely you think you are to be affected.
- Response Efficacy: How effective you believe each action is.
- Self-Efficacy: Your confidence in your ability to take that action.
- Response Cost: The financial and emotional cost of the action.
- Maladaptive Rewards: The benefit of doing nothing immediately.

Now, choose one of the following actions:
{options_text}
Note: If no flood occurred this year, since no immediate threat, most people would choose "Do Nothing."

### RATING SCALE (You MUST use EXACTLY one of these codes):
VL = Very Low | L = Low | M = Medium | H = High | VH = Very High

Please respond using the EXACT JSON format below.
- IMPORTANT: The "decision" field MUST be the NUMERIC ID (e.g. 1, 2, 3, or 4) from the available options list.
- Do NOT include any markdown symbols (like ```json), conversational text, or explanations outside the JSON.
- Use EXACTLY one of: VL, L, M, H, VH for each appraisal label.

<<<DECISION_START>>>
{
  "threat_appraisal": "TP_LABEL",
  "coping_appraisal": "CP_LABEL",
  "decision": "1",
  "reasoning": "text"
}
<<<DECISION_END>>>
````

---

## S5. Audit Log Example (Raw Trace)

**Event**: SkillBroker intercepts an invalid "Elevate" attempt (Insufficient Funds).

```json
{
  "agent_id": "Agent_42",
  "year": 3,
  "input_context": {
    "funds": 2000,
    "cost": 5000,
    "memory": "[CRITICAL] Year 2: My house was flooded."
  },
  "llm_output": {
    "reasoning": "I must protect my home. Despite the cost, I will elevate.",
    "action": "elevate_house"
  },
  "governance_result": {
    "status": "BLOCKED",
    "violation": "INSUFFICIENT_FUNDS",
    "correction": "do_nothing"
  },
  "memory_update": {
    "content": "Tried to elevate house but failed due to insufficient funds.",
    "salience": 1.0, // High Traumatic Learning
    "consolidated": true
  }
}
```

**Event**: SkillBroker **Allows** a valid "Buy Insurance" attempt.

```json
{
  "agent_id": "Agent_15",
  "year": 4,
  "input_context": {
    "funds": 1200,
    "cost": 1000,
    "memory": "Year 3: No flood."
  },
  "llm_output": {
    "reasoning": "I am worried about future risks. I can afford insurance.",
    "action": "buy_insurance"
  },
  "governance_result": {
    "status": "ALLOWED",
    "violation": null
  },
  "memory_update": {
    "content": "Decided to: buy_insurance",
    "salience": 0.8, // Strategic Major Decision
    "consolidated": true
  }
}
```
