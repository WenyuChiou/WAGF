# Figure 1 design contract

## Paper role

Figure 1 is a conceptual dataflow. Its single job is to show the paper's
measurement problem before the equations:

> One agent-written condition is read by runtime governance and also selects
> the records used by a conditional rate.

It is not a WAGF architecture inventory, a quantitative result, or evidence
that every blocked response produces an observed retry. Figures 2--4 carry the
measured results.

## Reference grammar

The layout follows the compact conventions identified in
`..\FIGURE_STYLE_AUDIT.md`: AgentSpec's short enforcement path, Reflexion's
agent/environment loop, AutoGen's compact semantic modules, and ReAct's direct
trajectory labels. The final artwork is generated as one complete composition
so its icons, fills, borders, arrows, and typography share one visual language.

The paper-facing rules are:

- every module has a near-black outline and a restrained colored fill;
- the canvas is a uniform cool gray, with no large white cards or bottom white
  strip;
- labels are short, dark, and separated from arrows and icon strokes;
- the response contains one highlighted `Agent-written condition` field;
- the condition has one visible junction and two roles: validation input and
  record selection;
- `Recorded decisions` has an independent arrow into `Record filter`;
- the future-context route is thin gray and dashed, and stays outside modules;
- there are no decorative legends, equations, long prose blocks, or extra
  icons inside the figure.

## Visual sentence and modules

The generated figure shows this sentence:

```text
agent response --proposed action--> Validator --accept--> Recorded decisions
      |                                  |                         |
      +--same condition--> Record filter +----------recorded set---+
                                                        |
                                                 Conditional rate
```

The upper path makes runtime governance visible. The lower path makes the
moving evaluation population visible. The world-state globe is a secondary
consequence: the Validator sends the accepted action directly to world state,
and a dashed `future context` route returns that state to the next response.

The generated modules are:

1. `AGENT RESPONSE`, containing `Action` and `Agent-written condition`;
2. `Validator`, shown as a shield gate;
3. `Recorded decisions`, shown as a database;
4. `World state`, shown as a globe;
5. `Record filter`, shown as a funnel;
6. `Conditional rate`, shown as a compact gauge.

The arrows carry short explanations: `proposed action`, `rule input`,
`accepted action`, `accept`, `recorded set`, `same condition`, `selects records`,
and `future context`.

## Source and outputs

The active figure is the generated asset:

`figures/assets/figure1_generated_full_final.png`

The compatibility builder `source/figure1_overlay.py` stages that asset into:

- `figures/active/figure1_concept.png` for the manuscript;
- `figures/active/figure1_concept_print.png` for print-width inspection;
- `figures/active/figure1_concept.json` for semantic and asset metadata.

The old vector PDF and intermediate generated version are in
`figures/candidates/legacy/figure1/` and are not referenced by TeX.

Because the active artwork is a generated raster, the geometry checker verifies
asset existence and dimensions but cannot prove pixel-level text/arrow
separation. A human visual review at full size, print width, and thumbnail size
is mandatory.

## Build and review order

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```

The manuscript caption must explain the condition's two roles and the missing
first-attempt boundary; no paragraph text belongs inside the figure.
