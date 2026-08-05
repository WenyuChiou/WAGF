# Figure 1 operational design contract

## Active version

The active Figure 1 is generated reset candidate D-v3:

`figures/assets/figure1_architecture_reset_D_final_v3.png`

The research and design rationale for the reset is recorded in
`AGENT_ARCHITECTURE_FIGURE_RESET.md`. Earlier two-lane/dashboard-like
compositions are historical and must not be used as the active direction.

## Paper role

Figure 1 is a conceptual architecture/dataflow figure. Its single reader task
is to see that an Agent response contains an action and an agent-written
condition; the Validator consumes the action and condition before execution;
and the same condition later selects records for a conditional rate.

It is not a quantitative result, a component inventory, or evidence that the
frozen corpus preserves every retry attempt.

## Active visual sentence

```text
Agent response[action, condition] --proposed action--> Validator --accepted--> Environment
                                      | rule input                         |
                                      +--> filter <-- records <-- Decision log
                                            |
                                      conditional rate
```

The top dashed `observation` route returns from Environment to Agent. It is
conceptual and is routed outside the solid measurement paths so that no arrow
crosses another arrow.

## Required visible relationships

1. The blue `Agent` boundary contains a small `LLM` chip cue and the
   `response` object with separate `action` and amber `condition` fields.
2. The black `proposed action` arrow visibly begins at the `action` field and
   enters `Validator`.
3. The amber `rule input` arrow begins at `condition` and enters `Validator`.
4. The black `accepted` arrow leaves `Validator` and enters `Environment`.
5. The black `accepted decision` arrow enters `Decision log`; the black
   `records` arrow carries logged records to `filter`.
6. The amber `selects records` arrow bypasses `Decision log` and enters
   `filter` directly from the condition field.
7. The black `records` and amber `selects records` routes remain distinct.
8. The dashed `observation` route has clear endpoints and no intersections
   with solid routes, labels, icons, or node interiors.

## Visual constraints

- Compact landscape composition for the full-width ICLR figure.
- Warm light-gray background; pale blue, amber, green, and violet fills.
- Near-black primary outlines and arrows; one thin gray dashed observation
  route.
- Small semantic icons only: LLM chip, validator check, environment/simulator,
  database, filter, and rate gauge.
- No gradients, mascots, screenshots, white label pills, title banner, or
  sentence-length text inside the image.
- All visible labels are short and exact: `Agent`, `LLM`, `response`, `action`,
  `condition`, `Validator`, `check`, `proposed action`, `accepted`,
  `Environment`, `observation`, `accepted decision`, `Decision log`,
  `records`, `filter`, `conditional rate`, `rule input`, and
  `selects records`.

## Caption contract

The caption must explain, in plain language, that the accepted action reaches
the environment and log, while the same condition independently selects the
logged records used by the conditional rate. It must state that the dashed
observation path is conceptual and that the frozen corpus does not preserve
the first response before a retry. It must not imply a causal effect, a
correction, or complete logging of rejected/retry attempts.

## Regeneration and checks

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```

The generated-raster geometry check cannot prove pixel-level separation;
full-size, paper-width, grayscale, thumbnail, and adversarial visual review
remain required before release.
