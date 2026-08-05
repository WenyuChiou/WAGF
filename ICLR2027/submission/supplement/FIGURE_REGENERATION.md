# Figure regeneration

## Figure 1

From the repository root:

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
```

Figure 1 is the reviewed compact v1 generated composition based on the reset
agent-paper architecture audit. It uses local semantic nodes, an explicit
Validator insertion point, an accepted-decision arrow aligned to Decision log,
and a direct condition-to-filter route. The builder stages
`figures/assets/figure1_architecture_compact_v1.png`; it does not redraw or edit
the image. The geometry check verifies the generated asset and dimensions,
while text/arrow separation requires the documented visual review because
those pixels are not machine-addressable geometry.

## Figures 2--4

The three quantitative figures are deterministic outputs from the frozen WAGF
evidence layer. Their copied CSVs are included here for inspection. The source
scripts remain in the historical evidence package:

```powershell
python SUBMISSION_2026\TAE\evidence\fig1_rule_layers.py
python SUBMISSION_2026\TAE\evidence\fig2_mechanism.py
python SUBMISSION_2026\TAE\evidence\fig3_consequence.py
```

Those commands write to the historical TAE evidence directory. For a release,
run them only in a disposable copy or update the output root first; do not
silently overwrite the historical TAE snapshot. The ICLR package itself uses
the copied PDFs under `ICLR2027\submission\figures\active`.

## Text and evidence checks

```powershell
python ICLR2027\submission\checks\manuscript_static_check.py
python ICLR2027\submission\checks\evidence_boundary_check.py
```

These checks do not rerun a model or claim causal identification.
