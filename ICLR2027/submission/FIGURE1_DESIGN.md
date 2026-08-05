# Figure 1 design contract

## Paper role

Figure 1 is a conceptual agent/evaluation diagram. Its one job is to show the
measurement problem before the equations:

> An LLM agent writes an action and a condition. Runtime governance consumes
> both, while evaluation uses the same condition to choose the records counted
> by a conditional rate.

The figure is not a WAGF component inventory, a quantitative result, or a
claim that the frozen corpus contains every intermediate retry response.

## Agent-paper grammar

The current composition was redesigned after inspecting the rendered figures
in ReAct, Reflexion, AutoGen, and AgentSpec. The adopted grammar is:

- expose one observable response and one trajectory, as in ReAct;
- use a compact bounded agent loop with a small number of semantic modules,
  as in Reflexion;
- use one small LLM cue and direct message ownership, as in AutoGen;
- show where enforcement intercepts the action, as in AgentSpec.

The figure therefore has two aligned lanes rather than six equally weighted
cards. The upper lane is execution. The lower lane is measurement. The
highlighted condition is the only field that deliberately has two outgoing
uses.

## Visual sentence and modules

```text
Agent (LLM) -> response[action, condition] -> Validator -> Environment
                                      \           |             |
                                       \          +-> Decision log
                                        +-> Filter -> Conditional rate
Environment -- next context (dashed) --> Agent (LLM)
```

The generated composition contains these semantic modules:

1. `Agent (LLM)`: a small circuit/LLM icon marks the AI producer.
2. `response`: one message containing `action` and the highlighted `condition`.
3. `Validator`: the runtime gate that receives the proposed action and rule
   input.
4. `Environment`: the external simulator state changed by an accepted action.
5. `Decision log`: the accepted decision record used by evaluation.
6. `Filter`: the operation that selects records using the shared condition.
7. `Conditional rate`: the downstream score over the selected records.

The arrows carry only short relations: `emits`, `proposed action`, `rule input`,
`accepted`, `accepted decision`, `recorded set`, `selects records`, and
`next context`. No paragraph, equation, or numerical result belongs inside
the image.

## Geometry and style rules

- Use a compact landscape canvas that fills the paper figure width.
- Use a uniform light neutral-gray background; avoid a large empty white field
  and avoid white label pills.
- Use near-black solid arrows for observed/control/data relations.
- Use one thin gray dashed arrow for the conceptual next-context return.
- Use amber only for the shared condition and its two outgoing branches.
- Use muted blue for the agent/response, green for the environment, and violet
  for the conditional rate.
- Keep the LLM icon small and functional. It must identify the AI producer,
  not act as decoration or a mascot.
- Keep every label short and readable at thumbnail size.
- Make the producer relation explicit: a short `emits` arrow must connect
  `Agent (LLM)` to `response`; adjacency alone is not enough.
- Do not let an arrow cross text, an icon, or a node border.
- Keep the condition-to-Validator and condition-to-Filter routes visibly
  distinct; keep the Validator-to-log and log-to-Filter routes distinct.
- Do not draw a retry endpoint in Figure 1. The caption states that the frozen
  corpus does not preserve the first response before a retry.

## Active source and review outputs

The active generated source is:

`figures/assets/figure1_generated_full_final.png`

The compatibility builder `source/figure1_overlay.py` stages it into:

- `figures/active/figure1_concept.png` for the manuscript;
- `figures/active/figure1_concept_print.png` for print-width inspection;
- `figures/active/figure1_concept.json` for semantic and asset metadata.

Earlier generation rounds, including the retired v11 composition and the
three external-paper-inspired candidates, remain under
`figures/candidates/` and are not referenced by TeX.

Because the active artwork is a generated raster, the geometry checker can
verify the asset and dimensions but cannot prove pixel-level arrow/text
separation. Full-size, print-width, thumbnail, and adversarial visual review
are required.

## Caption contract

The caption must state the following in plain language:

1. the response contains an action and an agent-written condition;
2. the validator reads both before execution;
3. accepted actions change the environment and enter the decision log;
4. the same condition selects records for the conditional rate; and
5. the dashed loop is conceptual because the first response before a retry is
   missing from the frozen corpus.

The caption must not call the fixed-denominator rate a correction or imply a
causal effect.

## Build and review order

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```
