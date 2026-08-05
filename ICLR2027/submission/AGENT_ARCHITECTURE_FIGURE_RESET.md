# Figure 1 reset: architecture grammar from agent papers

## Why the earlier direction is discarded

The earlier D-v3 checkpoint is retired as a design direction. It still reads
like a colorful inventory of modules: the execution path, measurement path,
icons, and feedback loop have comparable visual weight. A reviewer must decode
the layout before seeing the paper's point. The selected agent-paper v2 figure
is a new compact composition designed from the architecture grammars used in
agent papers, not a recolor of the old composition.

## Message to communicate

Figure 1 has one reader task:

> The agent writes one response containing an action and a condition. A
> runtime interface reads the condition before the action is executed. The
> same condition later selects records for a conditional score, so governance
> can change the population being measured.

This is a conceptual dataflow. It is not a result figure, a component
inventory, or a claim that the frozen corpus preserves every retry attempt.

## Reference-paper audit

The following primary papers were inspected from their rendered figures.

| Paper | What its figure makes visible | Rule adopted here |
| --- | --- | --- |
| [ReAct](https://arxiv.org/abs/2210.03629), Fig. 1 | A short observable agent trajectory with a small vocabulary of labels | Show one response/trajectory directly; do not make the reader infer the sequence from a module catalog |
| [Reflexion](https://arxiv.org/abs/2303.11366), Fig. 2 | A bounded agent loop, a few semantic modules, and relation labels on arrows | Use one compact loop and let connectors carry the meaning |
| [AutoGen](https://arxiv.org/abs/2308.08155), Fig. 1 | Role modules with small capability cues | Use a small LLM cue only to mark the producer; icons remain subordinate to the semantic label |
| [AgentSpec](https://arxiv.org/abs/2503.18666), Fig. 4 | An explicit enforcement boundary between agent output and tools | Make the validator's insertion point the structural center of the figure |
| [SWE-agent](https://arxiv.org/abs/2405.15793), Fig. 1 | A compact interface box between an LM agent and a computer, with short sublabels | Treat validation as an interface, not as a decorative shield; keep action and feedback routes orthogonal |
| [Voyager](https://arxiv.org/abs/2305.16291), Fig. 2 | Three named components, sparse arrows, and icons that denote concrete objects | Use color and icons to group concrete roles, but do not add screenshots or narrative detail that the claim does not need |
| [Magentic-One](https://arxiv.org/abs/2411.04468), Fig. 1 | A numbered task trajectory with concrete intermediate artifacts | Borrow the idea of a readable sequence only; this paper's multi-agent example is not our mechanism |

The common grammar is flat, bounded, and semantic: a few colored regions,
black outlines, short labels, direct arrows, and a caption that supplies the
interpretation. The papers do not rely on a large robot mascot, a title banner,
gradients, or sentence-length labels inside the diagram.

## Selected information architecture

The selected design is a **two-role, aligned-log** architecture:

```text
  RUNTIME: Agent(response[action, condition]) --> Validator --> Environment
                         condition ----------> Validator
  MEASUREMENT: Validator --accepted decision--> Decision log --records--> Filter --> conditional rate
                         condition -----------------------> Filter
  Environment --observation (dashed)----------------------> Agent
```

The generated artwork may use a more compact geometry, but it must preserve
these ownership relationships:

The `RUNTIME` and `MEASUREMENT` prefixes in the schematic are conceptual
annotations for the audit; the generated figure does not print them as lane
headers.

1. `Agent / LLM` owns the response; the response visibly contains `action`
   and `condition`.
2. `Validator` is between the proposed action and `Environment`. It reads the
   action and condition before execution.
3. Only an accepted action changes `Environment`; the observation returns to
   the agent as the next context.
4. The accepted decision is recorded in `Decision log`.
5. The same highlighted condition enters `filter`, which selects the records
   used by `conditional rate`.

The condition is the only deliberately repeated field. Its two uses must be
visually linked but must not share a junction with the accepted-action or
observation arrows. A retry/validation-message branch is omitted from the
main figure unless it can be shown as a subordinate conceptual path without
looking like a measured record.

## Candidate layouts considered

Each candidate is a genuinely new composition, not a recolor of the retired
checkpoint.

1. **Interface-first horizontal:** a compact AgentSpec/SWE-agent-style
   interface boundary sits between the response and environment; the
   evaluation fork is a narrow lower route.
2. **Trajectory pair:** panel (a) shows the runtime trajectory in the
   ReAct/Reflexion style; panel (b) shows the same response field selecting
   the logged population. The shared condition is the visual bridge.
3. **Nested boundary:** a Reflexion-style Agent boundary encloses the LLM and
   response, while a smaller governance boundary intercepts the action; the
   log/filter route sits outside the loop.
4. **Single shared-field graph:** one central response object exposes the
   highlighted condition to two clearly separated consumers, validator and
   filter, while the action path remains the primary left-to-right trajectory.

The active agent-paper v2 asset is the compact ownership-boundary form: the
response remains inside the Agent boundary, the `proposed action` arrow starts
at the `action` field, the accepted-decision arrow lands directly on the
Decision log, and the condition route passes below the log before entering the
filter. The upper and lower paths are expressed by placement and connectors,
not by full-canvas lane frames or header banners.

## Visual constraints

- Use a compact landscape composition intended for a full-width ICLR figure;
  use local semantic nodes and ownership boundaries, with no full-canvas lane
  frames, header banners, or title inside the image.
- Use a warm light-gray or paper-toned background, pale colored fills, and
  near-black outlines/arrows. Avoid pure-white cards and gradients.
- Use five semantic colors: blue for the agent/response, orange for the
  validator, amber for the shared condition, green for the environment, and
  violet for the score.
- Use a small, non-mascot LLM/chip icon inside the agent module; other icons
  should identify validator, environment, log, filter, or score at a glance.
- Use short labels only: `Agent`, `LLM`, `response`, `action`, `condition`,
  `proposed action`, `rule input`, `accepted`,
  `Environment`, `observation`, `accepted decision`, `Decision log`,
  `records`, `filter`, `selects records`, and `conditional rate`.
- Every arrow must have a visible start and end, be orthogonal or gently
  curved, and avoid every label, icon, and border. Relation labels sit in
  dedicated whitespace beside the connector, never on top of it.
- No arrow may cross another arrow. The condition-to-validator and
  condition-to-filter routes must be separate and traceable.
- Text must remain legible at the manuscript's one-column thumbnail scale;
  the caption, not the artwork, carries corpus limitations and caveats.

## Acceptance tests

A candidate fails if any of these is true:

- the reader cannot follow Agent → interface → Environment without the
  caption;
- the validator looks like a post-hoc evaluator rather than an insertion
  point before execution;
- the filter appears to score all decisions rather than a selected population;
- the two uses of `condition` are not visibly the same field;
- an arrow touches or crosses text, icon, or a node border;
- any generated label is malformed, clipped, or unreadable at print width;
- decorative imagery has more visual weight than the action/interface/score
  relation.

The selected asset must pass full-size, paper-width, thumbnail, semantic
adversarial, and manuscript static checks. It will then replace the active
checkpoint and trigger a caption/introduction synchronization pass.
