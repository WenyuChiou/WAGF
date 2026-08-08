# ICLR package source of truth

## Active release

The active release is the directory containing this file:
`ICLR2027\submission`.

- Manuscript source: `paper\manuscript.tex`
- Bibliography: `paper\references.bib`
- Figure 1 generated asset: `figures\assets\figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`
- Figure 1 staging builder: `source\figure1_agent_paper.py`
- Figure 1 compatibility entry point: `source\figure1_overlay.py`
- Figure 1 contract: `AGENT_ARCHITECTURE_FIGURE_RESET.md`
- Manuscript-facing figures: `figures\active\`
- Figure 1 manifest: `figures\active\figure1_concept.json`
- Figure and example-role audit: `PAPER_AUDIT.md`
- Reference verification audit: `REFERENCE_AUDIT.md`
- Figure 1 is a complete generated raster composition with an Agent response
  card, explicit black/amber Validator ports, a direct condition-to-Counted-
  records route, black borders, flat colored fills, and a warm light-gray
  background
- Legacy vector and intermediate Figure 1 files:
  `figures\candidates\legacy\figure1\`
- Non-active figure candidates: `figures\candidates\`
- Static checks: `checks\figure1_geometry_check.py` and
  `checks\manuscript_static_check.py`
- First-attempt experiment boundary: `EXPERIMENT_AUDIT.md`; it records
  governed-only diagnostics that are not released into the manuscript
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
                          only the named shared-condition asset feeds the active builder
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
simulation run. The central quantities are the irrigation condition shares and
conditional-rate contrasts, the world-state reweighting diagnostics, the
year-one check, and the all-decision sensitivity. The manuscript must
retain these boundaries:

- reweighting to recorded world state is descriptive, not causal, because world
  state is downstream of governance;
- the corpus does not preserve the first response before a retry;
- the paper does not establish deception or within-world reporting revision;
- flood is a transferability check and is not used to support causal claims;
- the result is scoped to the evaluated governance loop and models with
  publicly available weights.

## Semantic locks

- The executed action is the primary action reading; `\lastproposed` is a
  declared sensitivity analysis only.
- The scarcity report is broader than the two-condition rule; it is not
  silently relabeled as the full scarcity-and-coping condition.
- Figure 1 is conceptual. Figure 2 onward carries quantitative evidence.
- Figure 1 shows the retry/default-action protocol path because the executed
  action is primary, but it omits the observation-to-next-context loop. The
  frozen corpus lacks the first-attempt report; the limitation is documented in
  the caption and supplement.
