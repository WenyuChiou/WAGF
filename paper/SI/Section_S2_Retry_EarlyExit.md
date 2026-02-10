# S2. Governance Retry Mechanism and EarlyExit

## S2.1 InterventionReport Structure

When governance validation fails, the broker generates an `InterventionReport` for each blocking rule. The report structure captures the violation context and provides optional guidance for retry attempts:

```python
@dataclass
class InterventionReport:
    rule_id: str                     # Unique identifier of the blocking rule
    blocked_skill: str               # The skill that triggered the violation
    violation_summary: str           # Human-readable explanation of the violation
    suggested_correction: str | None # Optional hint for LLM retry
    severity: str = "ERROR"          # Severity level (ERROR or WARNING)
    domain_context: dict             # Additional metadata for analysis
```

The report is serialized for LLM consumption via `to_prompt_string()`, which formats the violation information in natural language:

```
- [ERROR] Your proposed action 'increase_large' was BLOCKED.
  - Reason: Demand increase blocked: Tier 2 shortage (10% curtailment).
    Conservation is mandatory under DCP operations.
  - Suggestion: Tier 2 shortage blocks all increases. Remaining feasible:
    maintain_demand, decrease_small, decrease_large.
```

This format provides the LLM with explicit feedback on what failed, why the violation occurred, and which alternative actions remain valid under the current governance constraints.

## S2.2 Retry Prompt Injection

When validation fails with severity level ERROR, the broker constructs a retry prompt by prepending governance feedback to the original agent prompt. The retry prompt structure is:

```
Your previous response was flagged by the governance layer.

**Issues Detected:**
- [ERROR] Your proposed action 'increase_large' was BLOCKED.
  - Reason: [violation_summary]
  - Suggestion: [suggested_correction]

Please reconsider your decision. Ensure your new response addresses
the violations above.

[Original prompt repeated in full]
```

The broker then re-invokes the LLM with this augmented prompt, allowing the model to adjust its reasoning based on the governance feedback. Configuration parameters control the retry behavior: `max_retries: 3` limits the number of retry attempts per agent-year, while `max_reports_per_retry: 3` truncates the feedback to the top three most critical violations to conserve context window capacity. When more than three rules fire simultaneously, only the highest-priority reports are included, with a note indicating that additional issues exist but are omitted for brevity.

## S2.3 Three-Tier Suggestion Design

Governance suggestions are structured according to a three-tier framework designed to provide appropriate guidance while minimizing inadvertent behavioral steering. The tier classification is based on the nature of the constraint and the degree of agent autonomy required in the response:

| Tier | Content | Used By | Rationale |
|------|---------|---------|-----------|
| A | No suggestion | Physical impossibility rules (water_right_cap, non_negative_diversion, minimum_utilisation) | Violation reason is self-evident from hydrological constraints; no alternative guidance needed |
| B | Neutral skill enumeration | Institutional rules (curtailment_awareness, drought_severity, supply_gap, consecutive_increase_cap) | Lists all remaining feasible skills without preference ordering: "Remaining feasible: maintain_demand, decrease_small, decrease_large" |
| C | No suggestion | Behavioral rules (demand_floor_stabilizer, demand_ceiling_stabilizer, zero_escape) | Agent should decide autonomously based on internal reasoning and persona attributes |

The neutral enumeration approach in Tier B was adopted after empirical evidence revealed significant suggestion bias in early framework versions. In development iteration v14, suggestions employed directive language such as "Choose decrease_demand to reduce water stress." This phrasing caused the gemma3:4b model to select `decrease_demand` in more than 90% of retry attempts, regardless of the agent's configured persona (aggressive, forward-looking, or myopic) or the prevailing hydrological context. Neutralizing suggestions to factual skill enumeration in v15 reduced this steering effect substantially and restored persona-differentiated retry behavior.

This finding is consistent with the instruction-following bias documented in small language models, where explicit suggestions are interpreted as imperative commands rather than optional guidance. For models under 10 billion parameters, governance suggestions function as de facto directives, effectively overriding the agent's internal decision heuristics. The three-tier framework mitigates this bias by withholding suggestions for constraints where agent autonomy is theoretically critical (Tier C) or where the violation is physically unambiguous (Tier A), while providing neutral factual information for institutional constraints where the legal-regulatory landscape may not be immediately apparent to the agent (Tier B).

## S2.4 EarlyExit Algorithm

The governance retry loop includes an early-exit optimization designed to terminate futile retry attempts when blocking conditions are immutable. The algorithm distinguishes between *deterministic* rules, whose trigger conditions depend solely on static agent attributes that cannot change between retries, and *non-deterministic* rules, whose conditions depend on LLM-generated cognitive constructs that may change as the model reconsiders its reasoning.

**Algorithm: EarlyExit for Governance Retry Loop**

```
Input: initial_validation_results, max_retries
prev_blocking_rules ← extract_rule_ids(initial_validation_results)

FOR retry = 1 TO max_retries:
  1. Build InterventionReports from validation_results
  2. Format retry prompt with governance feedback
  3. Re-invoke LLM → new_output
  4. Parse new_output → new_proposal
  5. Validate new_proposal → new_validation_results

  IF new_validation_results all pass:
    RETURN (new_proposal, RETRY_SUCCESS)

  current_blocking ← extract_rule_ids(new_validation_results)
  all_deterministic ← check_all_deterministic(new_validation_results)

  IF current_blocking == prev_blocking_rules AND all_deterministic:
    LOG "EarlyExit: deterministic rules unchanged, skipping remaining retries"
    BREAK

  prev_blocking_rules ← current_blocking

RETURN (last_proposal, REJECTED)
```

**Deterministic vs. non-deterministic rules**: A rule is classified as deterministic if its trigger condition depends solely on static agent attributes—such as income, property value, water right allocation, or basin affiliation—that remain constant within a single agent-year. Examples include `water_right_cap` (triggered when `at_allocation_cap` attribute is true), `minimum_utilisation_floor` (triggered when `below_minimum_utilisation` attribute is true), and affordability validators in the flood ABM (triggered when action cost exceeds fixed income thresholds). Non-deterministic rules depend on LLM-generated constructs such as threat perception (TP), coping perception (CP), water scarcity assessment (WSA_LABEL), or adaptive capacity assessment (ACA_LABEL). These constructs may change on retry as the LLM reconsiders its cognitive appraisal in response to governance feedback.

The EarlyExit condition triggers when two criteria are simultaneously satisfied: (1) the set of blocking rule IDs is identical to the previous retry attempt, and (2) all blocking rules are deterministic. When both conditions hold, the blocking state is immutable—no amount of additional LLM invocations will produce a proposal that satisfies the governance constraints. The algorithm therefore terminates early and classifies the outcome as REJECTED, avoiding unnecessary computational cost.

**Empirical impact**: In smoke validation experiments (78 agents, partial 2.6-year run), EarlyExit reduced total LLM calls by 46.4%, corresponding to 282 avoided invocations. Critically, this efficiency gain was achieved with no degradation in retry success rate—the optimization skips only those retry attempts that are provably futile. Agents whose blocking conditions depend on non-deterministic constructs (which may change upon reconsideration) still receive the full allotment of retry attempts, preserving the framework's capacity for self-correction where it is theoretically possible.

## S2.5 REJECTED Fallback

When all retry attempts are exhausted without achieving a governance-compliant proposal, the agent's outcome is classified as `REJECTED`. To maintain simulation integrity, the framework executes a domain-specific fallback skill that is guaranteed to satisfy all governance constraints:

- **Irrigation ABM**: `maintain_demand` — preserves the agent's previous-year water request, preventing demand collapse from failed increase attempts. This fallback is critical for maintaining basin-wide demand stability, as REJECTED outcomes without fallback would cause compound decay in subsequent years when the zero request becomes the new baseline.

- **Flood ABM**: `do_nothing` — preserves the household's status quo protective action state. This fallback reflects the empirically dominant behavioral response (60-70% base rate in post-disaster surveys) and ensures that inaction is modeled as a deliberate choice rather than a simulation artifact.

The fallback skill is registered via the `default_skill` parameter in the skill parsing configuration and is exempted from construct-conditioned governance rules (e.g., rules that require consistency between threat perception and protective action choice). This exemption ensures that the fallback can always be executed successfully, even when the agent's cognitive state (as inferred from previous LLM outputs) would normally block all available skills.

The REJECTED fallback mechanism guarantees that every agent produces a valid executed action in every simulation year, eliminating the possibility of undefined state transitions due to governance enforcement. This design choice reflects a fundamental principle of the framework: governance should constrain agent behavior, not cause simulation failure. The fallback represents the minimum viable action—maintaining the status quo—when the LLM persistently generates proposals that violate governance constraints.
