# Figure 1 operational design contract

## Active version

The active Figure 1 is the generated shared-condition agent-paper architecture candidate v3:

`figures/assets/figure1_architecture_agentpaper_v3.png`

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
RUNTIME: Agent response[action, condition] --> Validator --> Environment
                         condition --------> Validator
MEASUREMENT: Validator --accepted decision--> Decision log --records--> filter --> conditional rate
                         condition -----------------------> filter
```

The top dashed `observation` route returns from Environment to Agent. It is
conceptual and is routed outside the solid measurement paths so that no arrow
crosses another arrow.

`RUNTIME` and `MEASUREMENT` in the sentence above name the two conceptual
roles; they are not printed as full-canvas headers in the image.

## Required visible relationships

1. The blue `Agent` boundary contains a small `LLM` chip cue and the
   `response` object with separate `action` and amber `condition` fields.
2. The black `proposed action` arrow visibly begins at the `action` field and
   enters `Validator`.
3. The amber `rule input` arrow begins at `condition` and enters `Validator`.
4. The black `accepted` arrow leaves `Validator` and enters `Environment`.
5. A separate black `accepted decision` arrow leaves `Validator` and
   terminates on `Decision log`; the black `records` arrow carries logged
   records to `filter`.
6. The amber `selects records` arrow bypasses `Decision log` and enters
   `filter` directly from the condition field.
7. The black `records` and amber `selects records` routes remain distinct.
8. The dashed `observation` route has clear endpoints and no intersections
   with solid routes, labels, icons, or node interiors.

## Visual constraints

- Compact grid composition for the full-width ICLR figure, using local
  semantic nodes and one Agent ownership boundary rather than full-canvas lane
  frames or header banners.
- Pale blue-gray background; pale blue Agent response, orange Validator,
  green Environment, amber condition, and violet measurement fills.
- Near-black borders and primary arrows; amber condition routes; one thin
  black dashed observation route.
- Small semantic icons only: LLM chip, validator check, environment/simulator,
  log/list, filter, and rate gauge.
- No gradients, large mascots, screenshots, pure-white label cards, title
  banner, or sentence-length text inside the image.
- All visible labels are short and exact: `Agent`, `LLM`, `response`, `action`,
  `condition`, `Validator`, `proposed action`, `rule input`, `accepted`,
  `Environment`, `observation`, `accepted decision`, `Decision log`,
  `records`, `filter`, `conditional rate`, and
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
