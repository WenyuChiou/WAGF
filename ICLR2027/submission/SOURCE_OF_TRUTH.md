# ICLR package source of truth

## Active release

The active release is the directory containing this file:
`ICLR2027\submission`.

- Manuscript source: `paper\manuscript.tex`
- Bibliography: `paper\references.bib`
- Figure 1 generated asset: `figures\assets\figure1_architecture_compact_v1.png`
- Figure 1 staging builder: `source\figure1_agent_paper.py`
- Figure 1 compatibility entry point: `source\figure1_overlay.py`
- Figure 1 contract: `AGENT_ARCHITECTURE_FIGURE_RESET.md`
- Manuscript-facing figures: `figures\active\`
- Figure 1 manifest: `figures\active\figure1_concept.json`
- Figure 1 is a complete generated raster composition with an explicit
  Validator insertion point, a direct condition-to-filter route, near-black
  arrows, restrained colored fills, and a warm light-gray background
- Legacy vector and intermediate Figure 1 files:
  `figures\candidates\legacy\figure1\`
- Non-active figure candidates: `figures\candidates\`
- Static checks: `checks\figure1_geometry_check.py` and
  `checks\manuscript_static_check.py`
- Official style source: `source\iclr_style\iclr2027`

## File layout rule

There is one canonical location for every artifact that the manuscript can
include:

```text
submission/
  README.md              start here
  HANDOFF.md             current agent handoff
  paper/                 manuscript and bibliography
  figures/active/        only figures referenced by manuscript.tex
  figures/assets/        canonical generated source asset plus historical assets;
                          only the named compact v1 asset feeds the active builder
  figures/candidates/    non-submission alternatives; never referenced by TeX
  source/                deterministic figure builder and ICLR style files
  checks/                static, geometry, evidence, and reproducibility checks
  supplement/            non-identifying machine-readable release material
```

Do not put a new manuscript-facing figure in the figures root or in
`figures\candidates`. Add the manuscript-facing copy to `figures\active`, keep
the canonical generated source asset named in the artifact map, update the
manuscript, and rerun the static check. The historical TAE package remains
outside this active release and must not be edited as part of ICLR work.

## Authority hierarchy

1. Frozen evidence and deterministic evidence scripts in
   `SUBMISSION_2026\TAE\evidence`.
2. The corresponding source CSVs and figure-generation outputs in the same
   historical package.
3. This ICLR manuscript and its captions, which must not introduce a number or
   stronger claim absent from the evidence.
4. Review notes and handoff prose, which explain decisions but cannot override
   a measured artifact.

The TAE manuscript and handoff are historical documents. They contain useful
review history, but any older title, venue, figure instruction, or readiness
claim is superseded by this package and the live ICLR author guidelines.

## Evidence boundary

The ICLR draft relies on the existing frozen corpus rather than a new model or
simulation run. The central quantities are the irrigation prevalence and
conditional-rate contrasts, the world-state reweighting diagnostics, the
year-one check, and the fixed-denominator sensitivity. The manuscript must
retain these boundaries:

- reweighting to recorded world state is descriptive, not causal, because world
  state is downstream of governance;
- the corpus does not preserve the first response before a retry;
- the paper does not establish deception or within-world reporting revision;
- flood is a portability check, not an identification control;
- the result is scoped to the evaluated governance loop and open-weight model
  configurations.

## Semantic locks

- `\lastproposed` is the primary action reading.
- The scarcity report is a marginal conditioning variable; it is not silently
  relabeled as the full scarcity-and-coping conjunction.
- Figure 1 is conceptual. Figure 2 onward carries quantitative evidence.
- Figure 1 omits a retry endpoint because the frozen corpus lacks the
  first-attempt report; the limitation is documented in the caption and
  supplement. The dashed route is the conceptual next-context loop, not a
  measured retry trace.
