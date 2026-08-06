# Figure regeneration

## Figure 1

From the repository root:

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
```

Figure 1 is the reviewed generated shared-condition composition based on the
rendered agent-paper architecture audit. It uses a compact Agent response, a
Validator with explicit black/amber ports, a direct accepted-action route to
Environment, a final-record route into Decision log, and a separate
condition-to-Counted-records route. The builder stages
`figures/assets/figure1_architecture_agentpaper_shared_condition_v4.png`; it
does not redraw or edit the image. Observation and retry paths are omitted for
clarity; the frozen corpus lacks the first response before a retry. The geometry
check verifies the generated asset and dimensions, while text/arrow separation
requires the documented visual review because those pixels are not
machine-addressable geometry.

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
