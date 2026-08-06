# Agent-paper figure style audit

This file records the external figure references used for the active Figure 1
redesign. It is a design record, not part of the anonymous manuscript.

## Primary references

| Paper | What its figure makes easy to read | Rule adopted for WAGF | Rule rejected for WAGF |
| --- | --- | --- | --- |
| [ReAct, ICLR 2023](https://arxiv.org/abs/2210.03629), Fig. 1 | The observable `Thought / Action / Observation` trajectory and the comparison between prompting strategies | Put the agent response and its two fields in the reader's first visual path | A long benchmark transcript is not needed for this mechanism |
| [Reflexion, NeurIPS 2023](https://arxiv.org/abs/2303.11366), Fig. 2 | A bounded loop connecting Actor, Environment, Evaluator, and memory; arrows state the relation | Use one compact execution loop and short edge labels | Do not add an algorithm block beside the diagram |
| [AutoGen](https://arxiv.org/abs/2308.08155), Fig. 1 | Agent roles, small capability cues, and message ownership | Show one small LLM cue inside the agent and make direction explicit | Do not reproduce its multi-application collage or long chat example |
| [AgentSpec, ICSE 2026](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf), Fig. 4 | The enforcement insertion point between an agent's planned action and tools | Put Validator between the response and Environment, with an explicit rule-input edge | Do not make a shield icon stand in for the whole mechanism |
| [SWE-agent, NeurIPS 2024](https://arxiv.org/abs/2405.15793), Fig. 1 | A compact agent--interface--computer composition with short command labels | Use a compact response/interface/environment path and avoid dashboard-like modules | Do not copy software-specific commands or file lists |

## Common paper conventions

The comparison shows four common conventions that matter for this paper:

1. A figure has one visual sentence, not a catalogue of every implementation
   component.
2. A node represents a semantic operation or state, and an arrow carries the
   relationship between nodes.
3. Labels are short enough to read at the paper's actual size; explanation is
   placed in the caption and body text.
4. Icons identify agent roles or external entities but do not replace the
   label or add an unsupported claim.

## Historical Figure 1 decision

The previous large generated composition was retired because it behaved like a
dashboard: equal-weight modules, a long perimeter feedback route, and a weak
connection between the agent and the evaluation denominator.

The earlier replacement was a compact two-lane composition:

```text
EXECUTION:  Agent (LLM) -> response -> Validator -> Environment
                                      Validator -> Decision log
MEASUREMENT: response condition + Decision log -> Filter -> Conditional rate
FEEDBACK:   Environment -- next context (dashed) --> Agent (LLM)
```

The amber condition field is the only duplicated semantic use. Its upper
branch is `rule input`; its lower branch is `selects`. The accepted action goes
directly to Environment, and the final decision goes directly to Decision log.
The log and condition then enter Counted records through separate,
unambiguous arrows.

That earlier artwork is retained only as a historical style audit. The current
active artwork is documented in
`submission/FIGURE1_DESIGN.md` and uses the current shared-condition
composition
`submission/figures/assets/figure1_architecture_agentpaper_shared_condition_v5_retry.png`.

## Acceptance criteria

- A reviewer can identify the agent response, shared condition, Validator,
  Environment, log, Filter, and Conditional rate at thumbnail size.
- The condition-to-Validator and condition-to-Filter arrows are both visible
  and have distinct meanings.
- The accepted-action and recorded-decision arrows do not merge or cross.
- The observation-to-next-context loop remains omitted; the retry/default-action
  branch is represented because executed action is the primary reading.
- No text overlaps an arrow, icon, border, or another label.
- The image contains no title banner, legend, paragraph, equation, or
  decorative robot.
- The caption supplies the missing-first-attempt boundary.
