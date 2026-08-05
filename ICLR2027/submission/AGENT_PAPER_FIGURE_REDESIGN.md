# Figure 1 redesign: agent-paper reference audit

> **Superseded as the active design.** This document records the prior reset
> contract and candidate logic. The active composition is D-v3, governed by
> [`AGENT_ARCHITECTURE_FIGURE_RESET.md`](AGENT_ARCHITECTURE_FIGURE_RESET.md)
> and [`FIGURE1_DESIGN.md`](FIGURE1_DESIGN.md).

## Decision

The current generated Figure 1 is retired as a design direction. It reads as
an illustrated component inventory: too many equal-size modules, a perimeter
feedback route, and a long chain of labels. The replacement must show one
agent trajectory and one measurement consequence. Its visual sentence is:

> An LLM agent produces an action and a condition; runtime governance uses the
> condition to decide what proceeds, while evaluation uses the same condition
> to choose which accepted decisions are counted.

The figure is conceptual. It does not report a numerical result and it does
not claim that the frozen corpus contains the first response before a retry.

## External paper audit

The following references were inspected as primary papers, including the
rendered figure pages rather than only secondary summaries.

| Reference | Figure grammar observed | Design rule for WAGF | What WAGF will not copy |
| --- | --- | --- | --- |
| ReAct, ICLR 2023, Fig. 1 | Short, observable `Thought / Action / Observation` trajectories; panels are organized around the comparison being made | Show the agent's response and the data path directly; make the key distinction visible in the trace | Dense example transcripts and benchmark-specific text |
| Reflexion, NeurIPS 2023, Fig. 2 | A compact loop with `Actor (LM)`, `Environment`, `Evaluator (LM)`, and short-/long-term memory; arrows carry the relation | Use a bounded agent loop, a small set of semantic modules, and short edge labels | An algorithm listing or a second panel that competes with the mechanism |
| AutoGen, arXiv 2023, Fig. 1 | A few agent-role modules, small capability icons, and message direction; the caption explains the abstraction | Include a small LLM/agent cue only inside the agent module; use icons as role markers, not decoration | Its multi-application collage and long example chat |
| AgentSpec, ICSE 2026, Fig. 4 | A nested `Agent` boundary with a compact `AgentSpec` enforcement boundary between action and tools; short decision branches | Make the enforcement insertion point explicit and keep control flow orthogonal | A generic shield/validator as the entire story |

These papers consistently prioritize the relation that supports the claim:
ReAct exposes the trajectory, Reflexion exposes the loop, AutoGen exposes
message ownership, and AgentSpec exposes where enforcement intercepts an
action. They do not use a large title, a decorative robot, a legend full of
sentences, or a long outer loop to make the reader infer the mechanism.

## New information architecture

The figure has two aligned lanes with one shared source:

```text
EXECUTION
Agent (LLM) -> Response [action + condition] -> Validator -> Environment
     ^                                      \
     |                                       -> Decision log
     +---------- next context -------------------------------

MEASUREMENT
Response condition ---------------------------> Filter
Decision log ---------------------------------> Filter -> Conditional rate
```

The exact semantic roles are:

1. `Agent (LLM)` produces one response containing `action` and the highlighted
   `condition`.
2. `Validator` reads the proposed action and the condition before execution.
   The accepted action changes the `Environment`; the next context returns to
   the agent.
3. The accepted decision enters `Decision log`.
4. The same condition and the logged decisions enter `Filter`; the filter
   defines the population used by `Conditional rate`.
5. A thin dashed `validation message` retry edge may be shown only if it is
   visually subordinate and explicitly marked as conceptual. It must not look
   like a measured data path.

The figure must not imply that the condition is an independent simulator
variable, that every validator outcome is logged as a first attempt, or that
the fixed-denominator rate is a corrected causal effect.

## Visual specification

- **Composition:** compact landscape figure, two lanes, no large perimeter
  loop, no title banner, no white label pills.
- **Background:** very light warm gray or paper white with enough fill to avoid
  a floating-icon collage; modules use only two or three pale semantic fills.
- **Agent cue:** one small generated LLM/agent icon inside `Agent (LLM)`;
  it is subordinate to the label and is not a mascot.
- **Boundaries:** no extra lane boundary or dashboard panel; alignment and
  spacing separate the execution path from the measurement lane, while the
  only dashed route is the conceptual `next context` return.
- **Connectors:** black solid arrows for action/data flow; one gray dashed
  arrow only for conceptual feedback or retry. Every arrow has a visible
  endpoint and a short nearby label.
- **Highlight:** amber is reserved for the shared `condition` field and its
  two outgoing uses. Blue identifies the agent response; muted green denotes
  environment/state; violet is reserved for the measured rate.
- **Text:** only short labels: `Agent (LLM)`, `emits`, `response`, `action`,
  `condition`, `Validator`, `accepted`, `accepted decision`, `Environment`,
  `next context`, `Decision log`, `Filter`, `Conditional rate`, `rule input`,
  `recorded set`,
  and at most one `validation message` label. No sentence-length text inside
  the image.
- **Geometry:** no connector crosses a label, icon, or node; no branch shares
  an ambiguous junction; the condition branch must originate visibly from the
  condition field; the accepted-action arrow must enter Environment directly;
  the log-to-filter and condition-to-filter arrows must be distinct.
- **Paper use:** the figure must remain legible when reduced to one ICLR
  two-column figure width and as a thumbnail. The caption carries the missing
  first-attempt limitation and the interpretation boundary.

## Review gate

A candidate is rejected if any reviewer must read the caption to discover the
two roles of `condition`, if the agent loop cannot be followed left-to-right,
if the filter appears to score all decisions, if a retry edge looks measured,
or if text is malformed or sits on an arrow. The selected candidate must pass
full-size inspection, print-width inspection, thumbnail inspection, and an
adversarial review that checks semantics independently of aesthetic preference.

## Primary references

- [ReAct (ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366)
- [AutoGen](https://arxiv.org/abs/2308.08155)
- [AgentSpec (ICSE 2026)](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf)
