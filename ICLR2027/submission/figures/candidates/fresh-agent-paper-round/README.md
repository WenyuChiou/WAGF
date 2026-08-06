# Fresh agent-paper Figure 1 candidate round

This round deliberately does not continue the previous nested-interface
composition. Each image was generated as a new raster figure after auditing
the rendered architecture figures in ReAct, Reflexion, SWE-agent, AutoGen,
and AgentSpec.

## What the reference figures contribute

The references consistently use a small number of semantic modules, short
operation labels, one dominant trajectory, and a compact interface between an
agent and an external environment. Explanatory prose belongs in the caption.
The useful design rule for WAGF is therefore:

```text
one response -> validator -> environment
       condition -> validator
       final record -> decision log -> counted records -> conditional rate
       condition -------------------------------> counted records
```

The amber condition route is the visual argument. It must be separate from the
black records route and must visibly terminate at both its runtime and
measurement destinations.

## Candidates

| Candidate | Composition | Strength | Rejection reason / open check |
| --- | --- | --- | --- |
| `candidate_A_two_lane.png` | compact top execution path with an audit rail | good use of icons and high visual density | generated `record` route incorrectly starts at Environment; not semantically acceptable |
| `candidate_B_trajectory.png` | ReAct-like trajectory with lower score path | clean and readable at full size | `final record` is attached to Environment rather than Validator; reject |
| `candidate_C_shared_condition.png` | response-centered split with an explicit amber junction | strongest shared-condition emphasis; mostly correct routes | dashed observation route has an ambiguous origin; do not activate unchanged |
| `candidate_D_split_lanes.png` | explicit execution/measurement lanes | makes the two purposes easy to scan | final-record path visually merges with the counted-record path; reject |
| `candidate_E_minimal_shared_condition.png` | minimal horizontal runtime path plus lower measurement path | clearest endpoint geometry and shortest vocabulary; no nonessential loop | candidate for adversarial visual review at paper width and thumbnail size |
| `candidate_F_black_border.png` | compact shared-condition path with explicit black/amber ports | black borders, colored fills, and all seven WAGF endpoints are unambiguous | selected active candidate; caption and manifest must stay synchronized |

## Selection rule

Do not select a candidate because it merely looks polished. The active figure
must pass all of these checks:

1. The black final-record arrow visibly ends at `Decision log`.
2. The black records arrow starts at `Decision log` and ends at `Counted records`.
3. The amber `rule input` arrow ends at `Validator`.
4. The amber `selects` arrow ends at `Counted records` and bypasses the log.
5. No connector crosses text, an icon, a border, or another connector.
6. Every label remains readable at manuscript width and in grayscale.
7. The image communicates the shared denominator issue without requiring a
   legend or a paragraph inside the figure.

Candidate F satisfied these checks in the independent adversarial review. Its
active source is copied to `figures/assets/figure1_architecture_agentpaper_shared_condition_v4.png` and staged by the deterministic builder.

## Source provenance

The PNGs in this directory are generated candidates. They are not traced from
the reference papers. The reference papers supply visual conventions only;
WAGF labels and routes are derived from the manuscript's governance-loop and
conditional-rate definitions.
