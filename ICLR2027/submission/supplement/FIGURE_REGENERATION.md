# Figure regeneration

## Figure 1

From the repository root:

```powershell
python ICLR2027\submission\source\figure1_agent_paper.py
python ICLR2027\submission\checks\figure1_geometry_check.py
```

Figure 1 is the reviewed generated shared-condition composition based on the
rendered agent-paper architecture audit. It uses a compact Agent response, a
Validator with explicit black/amber ports, a direct accepted-action route to
Environment, a final-record route into Decision log, and a separate
condition-to-Counted-records route. The builder stages
`figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`;
it does not redraw or edit the image. The retry/default-action branch is shown
because the primary paper reading counts the action that executed; the frozen
corpus still lacks the first response before a retry. The geometry check verifies
the generated asset and dimensions, while text/arrow separation requires the
documented visual review because those pixels are not machine-addressable
geometry.

## Figures 2--4

Figure 2 is a two-panel rule-layer decomposition rebuilt from the frozen WAGF
CSV. Figure 3 is a deterministic two-panel output: the yearly condition-share
contrast and the arm-specific reservoir trajectories for the anchor irrigation
cell. Figure 4 is an executed-action dumbbell plot with paired intervals for
both endpoints and for their conditional-minus-all gap. Flood remains a
secondary cross-testbed boundary check in Table 3, not a same-status mechanism
panel.

Run from the repository root:

```powershell
python ICLR2027\submission\source\figure2_rule_layers.py
python ICLR2027\submission\source\cross_testbed_summary.py
python ICLR2027\submission\source\figure4_denominator_gap.py
```

The cross-testbed builder reads the frozen
`supplement\cross_testbed_release_cells.csv`, the copied irrigation mechanism
CSV, and the release audit metadata. It checks the historical
`ICLR2027\flood_control_contrasts.csv` for exact agreement but never rewrites
the canonical release cells. It writes the
active two-panel Figure 3 PNG/PDF, `supplement\cross_testbed_summary.csv`, the
paper Table 3 TeX fragment, and `supplement\cross_testbed_provenance.json`. It
is idempotent and retains nine Flood configurations. The gemma3:4b Flood cell
excludes one divergent governed run, leaving four governed versus five
no-validator runs; including it changes that cell from +0.35 pp to -1.16 pp.
Flood is therefore a descriptive boundary check, not a paired or causal
comparison. Both settings use H/VH labels from the shared five-level appraisal
instrument. The enforcement-pressure range shown in the summary CSV is pinned
in `supplement\enforcement_pressure_source.json`, with its source recorded
there.

The Figure 4 builder reads `supplement\fig4_per_seed.csv`, rejects duplicate,
missing, non-finite, or algebraically inconsistent seed rows, and checks all
three endpoint means against the frozen display CSV before writing
`supplement\fig4_gap_intervals.csv`. It does not import a live historical
evidence script.

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

To refresh the exact package manifest, use
`python ICLR2027\submission\checks\release_manifest.py --write`. If reviewed
release paths were intentionally added or removed, append
`--allow-inventory-change`; otherwise an inventory change fails closed. The command
first rebuilds all figures and the PDF, runs the geometry, text, evidence, page,
and font gates, and hashes the package only if every dependency passes. Running
the command without `--write` is a read-only verification. Each multi-file
figure generation also writes a SHA-256 group marker last, so an interrupted
promotion cannot pass package verification.
