# Figure style audit for the ICLR 2027 paper

This audit records the external figure references used to redesign Figure 1.
It is a design reference, not part of the anonymous submission.

## Reference figures

| Paper | Figure grammar | What we adopt | What we reject |
| --- | --- | --- | --- |
| [ReAct](https://arxiv.org/abs/2210.03629), Figure 1 | Four compact trajectory panels; the content of each step is the visual evidence | Directly show the action/observation sequence and use highlights only for the important distinction | Dense text panels are not appropriate for our one-mechanism schematic |
| [Reflexion](https://arxiv.org/abs/2303.11366), Figure 2 | A small module graph inside an Agent boundary, with Environment outside and feedback arrows | Semantic modules, external world node, thin black/gray connectors, direct labels | No decorative icon strip or large title pills |
| [AgentSpec](https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf), Figure 1 | A compact enforcement example: agent response, rule decision, tools/enforcements | Short functional labels, one compact decision branch, small functional symbols when they explain a role | Multiple nested cards and labels floating on colored backgrounds |
| [AutoGen](https://arxiv.org/abs/2308.08155), Figures 1--2 | Grouped layers for agents, developer control, and program execution; messages carry the flow | Explicit ownership of modules and separate control/data paths | Its overview collage is too dense for a 4.4-inch single-mechanism figure |
| Historical TAE Figure 1 | Agent answer -> same field -> validator/measurement -> conditional rate | The direct shared-field explanation and short arrow labels | The old domain-specific wording is replaced with the ICLR-general wording |

## Rules extracted from the references

1. The figure must have one visual sentence. For this paper: one response field
   is reused by governance and measurement.
2. Every box must represent a semantic operation or state. There are no
   decorative cards whose only purpose is to hold an icon.
3. Main routes are black. A dashed gray/black route means feedback or a
   conceptual retry, never a measured result.
4. Color is reserved for semantic grouping: the shared agent-written condition
   receives the only strong highlight; other nodes use restrained colored fills.
5. Labels are printed directly on nodes or in nearby whitespace. White label
   pills, colored arrow labels, and text laid over icons are prohibited.
6. The canvas is a uniform cool gray with compact colored fills inside the
   modules; there are no large white cards or empty white strips.
7. Generated icons are subordinate to their semantic labels and cannot carry a
   claim on their own.
8. The 100% view and the thumbnail must communicate the same relationship. If a
   label or arrow is needed only at full size, the layout is too dense.

## ICLR Figure 1 design decision

The active figure uses a compact generated icon-and-flow graph rather than a
decorative AI infographic:

```text
agent response --action--> validator --accept--> recorded decisions --> world state
       |                         |                    |
       +-- same condition -------+                    +--> record filter --> conditional rate
                                  future context returns to the agent response
```

The action and condition remain visibly inside one response packet. The
condition appears once, then forks at a small junction to the validator and
the record filter. The world-state feedback is a secondary dashed route;
retry is omitted because the frozen corpus lacks the first report before a
retry. The caption carries that limitation; the figure does not put the
paragraph inside a node.

The final figure is the reviewed generated asset
`submission/figures/assets/figure1_generated_full_final.png`. The retired vector composition
and intermediate image versions are kept under
`submission/figures/candidates/legacy/figure1/` and are not used by the manuscript.
