# Figure 1 reset: from nested interface to shared-condition dataflow

## Decision

The nested-interface candidate was retired after a fresh audit of agent
framework figures and a strict visual review. Its large dashed boundaries made
the reader decode containers before seeing the paper's measurement point.

The active replacement is:

`figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`

It is a newly generated compact dataflow figure with black borders, colored
fills, explicit input/output ports, short labels, and a subordinate
retry/default-action branch required by the executed-action primary reading.
Version v5 is retained only as a historical generation record; v6 routes the
retry arrow directly back to Agent response.

## Message to communicate

> One agent response contains an action and a condition. The Validator checks
> the response before execution; a rejected proposal can be re-asked or fall
> back to a default action, and the final decision is logged. The same condition
> selects the records used by the conditional rate, so governance can change
> what gets counted as well as what action executes.

This is a measurement-validity mechanism. It is not a claim that the agent is
deceptive, that validation has a causal effect, or that every retry is present
in the released corpus.

## Reference-paper audit

The rendered primary figures were rechecked in:

| Paper | Observed grammar | WAGF design implication |
| --- | --- | --- |
| ReAct (ICLR 2023) | short observable trajectory vocabulary | keep the main path readable left-to-right |
| Reflexion (NeurIPS 2023) | few semantic modules inside a bounded loop | show operations, not implementation detail |
| SWE-agent (NeurIPS 2024) | compact agent--interface--environment composition | treat Validator as a concise interface/gate |
| AgentSpec (ICSE 2026) | explicit enforcement insertion point | give Validator distinct ports and a direct decision path |
| AutoGen (2023) | small role/capability cues | use icons only as subordinate semantic cues |

The figure borrows conventions, not artwork. The central WAGF-specific visual
device is the amber condition token and its explicit two-port split.

## Candidate decision

The fresh round generated candidates A--F. A, B, and D had record-path errors;
C had an ambiguous observation origin; E had correct core routing but an
ambiguous Validator endpoint and an outdated caption contract. Candidate F
corrected those defects and was independently reviewed as image-level
`APPROVE` at full size, thumbnail size, and grayscale.

## Acceptance tests

Reject the active asset if any of these conditions is true:

- the black `propose` arrow does not enter Validator's black input port;
- the black `accepted` arrow does not run from Validator to Environment;
- the black `final record` arrow does not terminate at Decision log;
- the black `records` arrow does not start at Decision log and end at Counted
  records;
- the amber `rule input` arrow does not terminate at Validator's amber port;
- the amber `selects` arrow does not terminate at Counted records or appears to
  enter Decision log;
- an arrow lacks a clear endpoint or crosses text, an icon, a border, or
  another arrow;
- labels are malformed, clipped, or unreadable at paper width;
- the image implies that retry attempts are fully observed;
- decorative imagery has more visual weight than the mechanism.

## Primary references

- [ReAct (ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366)
- [AutoGen](https://arxiv.org/abs/2308.08155)
- [SWE-agent (NeurIPS 2024)](https://arxiv.org/abs/2405.15793)
- [AgentSpec (ICSE 2026)](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf)
