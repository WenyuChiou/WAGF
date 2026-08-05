# Figure 1 operational design contract

## Active version

The active Figure 1 is the generated nested-interface candidate:

`figures/assets/figure1_architecture_agentpaper_nested_v3.png`

It is staged into `figures/active/figure1_concept.png` by
`source/figure1_agent_paper.py`. The older shared-condition bridge v3 remains
in `figures/assets/` as a historical comparison and is not active.

## Paper role

Figure 1 is a conceptual architecture/dataflow figure. Its single reader task
is to see that one response contains an action and a condition; a governance
interface reads both before execution; and the same condition later helps
select the records used by a conditional rate.

It is not a quantitative result, a component inventory, or evidence that the
frozen corpus preserves every retry attempt.

## Why this figure grammar

The redesign follows the visual grammar of the rendered primary figures in
ReAct, Reflexion, SWE-agent, and AgentSpec:

- ReAct makes an observable agent trajectory readable with a small vocabulary.
- Reflexion uses a bounded agent boundary and a few semantic modules.
- SWE-agent places a compact interface between the LM agent and its environment.
- AgentSpec makes the enforcement insertion point explicit with a nested
  boundary and short decision paths.

WAGF combines those conventions into one nested interface: the Agent owns the
response, the governance boundary owns the Validator, and the lower path makes
the counted population explicit. The figure does not copy a mascot, a chat
transcript, or an algorithm block.

## Visual sentence

```text
Agent(response[action, condition]) -> Validator -> Environment
                                      |
                                      +-> Decision log -> Counted set -> Conditional rate
condition ---------------------------> Counted set
Environment -- observation (dashed) -> Agent
```

The amber condition is the only deliberately reused field. Its two routes have
different meanings: `rule input` enters Validator, while `selects` enters
Counted set. The black `records` route supplies the other input to Counted set.

## Visible structure

1. A black dashed `Agent` boundary contains a small `LLM` chip and a response
   card with blue `action` and amber `condition` rows.
2. A black dashed `governance` boundary encloses the orange `Validator` and
   its checklist icon. It is visibly between the response and Environment.
3. The accepted action goes directly from Validator to the green Environment.
   A thin dashed `observation` route returns from Environment to Agent.
4. A separate black `final record` arrow goes from Validator to the violet
   `Decision log`.
5. The lower violet `Counted set` receives two distinct inputs: black
   `records` from Decision log and amber `selects` from the condition row. It
   then feeds `Conditional rate`.
6. The retry path is omitted. The caption states that the frozen corpus does
   not preserve the first response before a retry.

## Visual constraints

- Warm light-gray paper background; no gradient, shadow, title banner, legend,
  equation, paragraph, watermark, or decorative mascot.
- Black or near-black borders and arrows; flat colored fills only: blue for the
  Agent/response, amber for condition, orange for Validator, green for
  Environment, and violet for measurement modules.
- Small functional icons identify the LLM, Validator, Environment, log, counted
  set, and rate. Icons remain subordinate to labels.
- Labels are short and exact. Explanations belong in the caption and body.
- Every arrow has a visible origin, arrowhead, and destination. No connector
  crosses a label, icon, boundary, or another connector.
- The condition-to-Counted-set route must bypass Decision log visibly; it must
  not terminate at the log or appear to be a second records route.
- The image must remain legible at full size, manuscript width, thumbnail size,
  and grayscale.

## Caption contract

The caption must say, in plain language, that the allowed action reaches the
environment, the final record enters Decision log, and the same condition
selects the Counted set while records from the log enter that set. It must
state that the dashed observation path is conceptual and that the retry path
is omitted because the first response is unavailable. It must not imply a
causal effect, a correction, or complete logging of rejected attempts.

## Regeneration and checks

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```

The generated-raster geometry check verifies the active asset, dimensions,
hashes, and label manifest. Pixel-level arrow and text separation still
requires full-size, print-width, thumbnail, grayscale, and adversarial visual
review before release.
