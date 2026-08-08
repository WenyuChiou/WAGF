# Figure 1 operational design contract

## Active version

The active Figure 1 is the generated shared-condition architecture:

`figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`

It is staged into `figures/active/figure1_concept.png` by
`source/figure1_agent_paper.py`. Earlier nested-interface and bridge images
remain historical candidates and are not active.

## Paper role

Figure 1 has one reader task: see why a runtime validator can change a
conditional evaluation score through the records that enter its denominator.
The agent response contains an action and an agent-written condition. The
response enters the Validator; an accepted action reaches the Environment;
a rejected proposal returns to the Agent response for a retry or reaches a
retry-exhausted default action; the Validator's final record enters the Decision log. The same
condition enters the Validator as a rule input and selects records in the
conditional-rate path. The primary paper statistics count the executed action.

This is a conceptual dataflow figure, not a quantitative result, a component
inventory, or evidence that the frozen corpus preserves every retry attempt.

## Reference-paper visual audit

The new composition was rebuilt after inspecting the rendered primary figures
in ReAct, Reflexion, SWE-agent, AutoGen, and AgentSpec. The relevant shared
grammar is:

- a small number of semantic modules rather than a dashboard of equal-weight
  boxes;
- one dominant left-to-right agent/environment path;
- a compact interface or gate where the agent meets execution;
- short operation labels on connectors and short names inside nodes;
- functional icons as subordinate cues, with explanations in the caption.

WAGF uses that grammar without copying any artwork. The black/amber ports are
an intentional addition: they make the two uses of the same condition and the
four record-flow endpoints explicit at paper width.

## Visual sentence

```text
Agent response --propose--> Validator --accepted--> Environment
       ^                     |
       +--retry / re-ask-----+
                             +--final record--> Decision log --records-->
condition --rule input-----> Validator                         Counted records --> Conditional rate
condition --selects-------------------------------------------> Counted records
```

The amber condition is the only reused field. Its `rule input` route ends at
Validator's amber input port; its `selects` route bypasses Decision log and
ends at Counted records' amber input port. The black `final record` and
`records` routes are separate and have their own ports.

## Visible structure

1. A blue Agent response card contains a restrained AI-chip icon and two
   fields: `action` and amber `condition`.
2. The orange Validator card has distinct black and amber input ports, a black
   output port for the accepted action, and a black bottom port for the final
   record.
3. The green Environment card receives only the accepted action path.
4. The violet Decision log receives the Validator's final record. It sends
   black `records` to Counted records.
5. The violet Counted records card receives both black records and the amber
   condition selector, then feeds Conditional rate.
6. The direct retry/default-action branch is shown because the executed action
   is the primary reading. Observation-to-next-context remains omitted to keep
   the shared condition relationship legible. The caption and Evaluation
   Setting state that the frozen corpus lacks the first response before a retry.

## Visual constraints

- Warm very-light-gray paper background; black borders and black arrows;
  colored flat fills for action, condition, Validator, Environment, and the
  measurement path.
- Color contract: blue marks the agent response, orange the runtime
  Validator, green the Environment/simulator, violet the measurement and
  record path, amber the shared agent-written condition, and black the
  execution or record-flow connectors and module borders. The warm gray canvas
  is neutral and carries no semantic data role.
- No gradients, drop shadows, title banner, legend, equations, paragraphs,
  watermark, or floating white label plates.
- Labels are short and exact: no label exceeds the short-figure limit in the
  manifest.
- Every connector has one visible origin, one arrowhead endpoint, and clearance
  from text, icons, borders, and other connectors.
- The condition route is amber and the records route is black; the two routes
  remain distinguishable in color and by their separate ports.
- The image must remain legible at full size, manuscript width, thumbnail size,
  and grayscale.

## Caption contract

The caption must state that the action is checked before execution, that a
rejected proposal can be re-asked or fall back to a default action, that the
final executed record enters Decision log, and that the same condition selects
the Counted records used by Conditional rate. It must use the exact visible
term `Counted records`, state that the observation loop is omitted, and state
that the first response before a retry is unavailable in the frozen corpus. It
must not imply a causal effect, a correction, or complete logging of rejected
attempts.

## Regeneration and checks

```powershell
python ICLR2027\submission\source\figure1_agent_paper.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```

The generated-raster geometry check verifies the staged asset, dimensions,
hashes, and label manifest. Pixel-level separation is additionally reviewed
at full size, manuscript width, thumbnail size, and grayscale, with an
independent adversarial visual review before release.
