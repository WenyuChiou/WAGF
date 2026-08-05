# ICLR 2027 submission checklist

## Current package

- [x] Anonymous title and empty author block in `paper/manuscript.tex`.
- [x] ICLR 2027 style files are staged under
      `source\iclr_style\iclr2027`; the build command below supplies that path.
- [x] Main text uses the ICLR 2027 conference style and has no final-copy switch.
- [x] Abstract, introduction, methods, results, limitations, conclusion,
      bibliography, AI-use, ethics, and reproducibility sections are present.
- [x] Figure 1 agent-paper v2 has short labels, an action-aligned `proposed action`
      route, an explicit `accepted decision` arrow that terminates on the
      aligned log, a direct condition-to-filter route, and a non-crossing
      observation loop.
      Its generated-asset integrity check plus full-size, paper-width,
      grayscale, and thumbnail visual reviews pass. Its manuscript-facing
      output is under `figures/active/`; official typeset print-width PDF
      inspection remains open.
- [x] Figures 2--4 are copied from the existing deterministic evidence outputs
      under `figures/active/`; no generated image is used for a quantitative
      chart.
- [x] Citation keys, figure paths, one-page quantitative figure PDFs, placeholder tokens,
      Unicode surprises, and LaTeX environment balance pass static checks.
- [x] Frozen evidence-source presence, key reported values, marginal-versus-
      conjunction wording, and scope-limiting language pass the evidence-boundary check.
- [x] The WAGF reproducibility audit is preserved under
      `checks\reproducibility`; it is **RED** for three historical smoke
      manifests marked `git_dirty=true`, and the manuscript does not claim
      bitwise historic reproducibility.
- [x] The paper states the seed-level inferential unit, final-action reading,
      missing first-attempt field, descriptive status of reweighting, and
      testbed limitations.

## Still required before upload

- [ ] Run the official ICLR TeX build in an environment with a TeX engine and
      inspect the resulting PDF at 100% and print size. From
      `submission\paper`, use the staged style directory explicitly:

      ```powershell
      $iclrTexInputs = "..\source\iclr_style\iclr2027;$env:TEXINPUTS"
      $env:TEXINPUTS = $iclrTexInputs
      pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex
      ```
- [ ] Verify the rendered page count is within the ICLR limit and that no
      overfull boxes, clipped captions, or anonymization leaks remain.
- [ ] Fill the actual OpenReview author metadata only at submission time.
- [ ] Complete the ICLR profile, reciprocal-review, and quota requirements for
      every author before the paper deadline.
- [ ] Make the final dual-submission decision after checking the live policy.

## Evidence and science gate

- [x] Re-run the frozen evidence inventory and table/figure crosschecks in the
      isolated ICLR package; do not modify the historical TAE snapshot.
- [x] Confirm every number in the ICLR manuscript is still present in the
      current source-of-truth evidence files.
- [x] Have an adversarial reviewer check the denominator logic, the distinction
      between the marginal scarcity report and the full conjunction, the
      post-governance world-state reweighting caveat, and the first-attempt gap.
- [x] The manuscript does not describe the paper as showing deception, gaming,
      a causal effect, universal behavior, or a corrected effect estimate.
