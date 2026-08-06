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

Figure 2 is the copied rule-layer decomposition from the frozen WAGF evidence
package. Figure 4 is the copied denominator consequence plot. Figure 3 is a
deterministic four-panel output: panels A--C use the anchor irrigation cell,
and panel D is the descriptive Flood cross-testbed check. The active ICLR
package owns the cross-testbed builder so that the Flood eligibility decision
and the plotted values are recorded together:

```powershell
python ICLR2027\submission\source\cross_testbed_summary.py
```

The builder reads only `ICLR2027\flood_control_contrasts.csv` and the copied
irrigation mechanism CSV. It writes the active Figure 3 PNG/PDF, the
machine-readable `supplement\cross_testbed_summary.csv`, the Table 2 TeX
fragment, and the panel-D rows in `supplement\fig2_mechanism.csv`. It is
idempotent and retains nine Flood configurations. The gemma3:4b Flood cell
excludes one divergent governed run, leaving four governed versus five
no-validator runs; including it changes that cell from +0.35 pp to -1.16 pp.
Flood is therefore a descriptive portability check, not a paired or causal
comparison. Panel D calls the quantity a high-threat-appraisal contrast: the
irrigation CSV uses `construct_WSA_LABEL`, while Flood uses
`construct_TP_LABEL`; both use the H/VH labels from the shared five-level
appraisal instrument. The enforcement-pressure range shown in the summary CSV
is pinned in `supplement\enforcement_pressure_source.json`, with its source
lines recorded there; it is not silently recomputed from the Flood contrast
CSV.

The historical evidence scripts remain available for provenance, but their
default output roots are under the TAE snapshot and must not be overwritten:

```powershell
python SUBMISSION_2026\TAE\evidence\fig1_rule_layers.py
python SUBMISSION_2026\TAE\evidence\fig2_mechanism.py
python SUBMISSION_2026\TAE\evidence\fig3_consequence.py
```

Those commands should be run only in a disposable copy or with an explicit
output-root override. The ICLR package itself uses the copied PDFs under
`ICLR2027\submission\figures\active`.

## Text and evidence checks

```powershell
python ICLR2027\submission\checks\manuscript_static_check.py
python ICLR2027\submission\checks\evidence_boundary_check.py
```

These checks do not rerun a model or claim causal identification.
