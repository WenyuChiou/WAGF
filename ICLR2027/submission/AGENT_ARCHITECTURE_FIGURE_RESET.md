# Figure 1 reset: from module dashboard to nested agent interface

## Decision

The former shared-condition bridge v3 is retired as the active direction. It
was semantically correct, but its large equal-weight modules made the reader
decode a dashboard before seeing the paper's point.

The active replacement is
`figures/assets/figure1_architecture_agentpaper_nested_v3.png`. It is a new
generated composition selected from the agent-paper candidate round. It uses a
bounded Agent, an explicit governance boundary around Validator, a direct
Agent--Validator--Environment path, and a compact lower counted-set path.

## Message to communicate

> The agent writes an action and a condition in one response. Governance reads
> both before execution. The final record is logged, and the same condition
> selects which logged records enter the conditional rate.

This is a measurement-validity mechanism. It is not a claim that the agent is
deceptive, that validation has a causal effect, or that every retry is present
in the released corpus.

## Reference-paper audit

The design was reset after inspecting the rendered primary figures in:

| Paper | Adopted grammar | Deliberately not copied |
| --- | --- | --- |
| ReAct, ICLR 2023 | short observable agent trajectory | long benchmark transcripts |
| Reflexion, NeurIPS 2023 | bounded loop with a few semantic modules | the adjacent algorithm block |
| SWE-agent, NeurIPS 2024 | compact interface between LM agent and computer | software-specific file lists |
| AgentSpec, ICSE 2026 | nested enforcement insertion point | a shield icon standing for the mechanism |
| AutoGen, 2023 | small role/capability cues | the multi-application collage |

The common rule is that a node names an operation or state and an arrow names
the relation. The active figure follows that rule with short labels, black
outlines, flat fills, and small functional icons.

## Candidate decision

The generated candidate round tested three distinct compositions:

1. A dual-panel runtime/measurement figure was clear but left the shared
   condition bridge without a fully explicit endpoint.
2. An interface-first single canvas was compact but its condition branch could
   be read as entering the log rather than the counted set.
3. The nested-interface candidate makes the governance insertion point and the
   two distinct Counted-set inputs explicit; it is active after removing an
   ambiguous conceptual retry connector.

The candidate files remain under
`figures/candidates/agent-paper-round/` for audit, but only the generated asset
named above feeds the active builder.

## Acceptance tests

Reject the active asset if any of these conditions is true:

- the action path cannot be followed left to right;
- the Validator does not visibly sit between response and Environment;
- the condition-to-Counted-set arrow terminates at or crosses Decision log;
- the lower Counted set appears to receive only a condition or only records;
- an arrow lacks a clear endpoint or crosses text, an icon, or another arrow;
- labels are malformed, clipped, or unreadable at paper width;
- the figure implies that retry attempts are fully observed;
- decorative imagery has more visual weight than the mechanism.

## Primary references

- [ReAct (ICLR 2023)](https://arxiv.org/abs/2210.03629)
- [Reflexion (NeurIPS 2023)](https://arxiv.org/abs/2303.11366)
- [AutoGen](https://arxiv.org/abs/2308.08155)
- [SWE-agent (NeurIPS 2024)](https://arxiv.org/abs/2405.15793)
- [AgentSpec (ICSE 2026)](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf)
