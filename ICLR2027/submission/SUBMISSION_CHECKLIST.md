# ICLR 2027 submission checklist

## Current package

- [x] Anonymous title and empty author block in `paper/manuscript.tex`.
- [x] ICLR 2027 style files are staged under
      `source\iclr_style\iclr2027`; the build command below supplies that path.
- [x] Main text uses the ICLR 2027 conference style and has no final-copy switch.
- [x] Abstract, introduction, methods, results, limitations, conclusion,
      bibliography, AI-use, ethics, and reproducibility sections are present.
- [x] Figure 1 shared-condition design has short labels, explicit black and
      amber ports, a `final record` arrow that terminates on Decision log,
      separate condition and records inputs to Counted records, and no
      ambiguous observation route. Its generated-asset integrity check plus
      full-size, paper-width, grayscale, thumbnail, and independent adversarial
      visual reviews pass. Its manuscript-facing output is under
      `figures/active/`; the official typeset PDF inspection passes at paper
      width and in the rendered manuscript. Its color contract is explicit:
      blue agent output, orange validation, green environment, violet
      measurement, amber shared condition, and black flow/borders.
- [x] Figures 2--4 are deterministic evidence outputs under `figures/active/`;
      Figure 3 is a three-panel primary irrigation mechanism figure, while
      Flood remains a secondary Table 2/cross-testbed summary; no generated
      image is used for a quantitative chart.
- [x] Citation keys, figure paths, one-page quantitative figure PDFs, placeholder tokens,
      Unicode surprises, and LaTeX environment balance pass static checks.
- [x] Frozen evidence-source presence, key reported values, scarcity-report
      versus two-condition wording, and scope-limiting language pass the
      evidence-boundary check.
- [x] The WAGF reproducibility audit is preserved under
      `checks\reproducibility`; it is **RED** for three historical smoke
      manifests marked `git_dirty=true`, and the manuscript does not claim
      bitwise historic reproducibility.
- [x] The paper states the seed-level inferential unit, final-action reading,
      missing first-attempt field, descriptive status of reweighting, and
      testbed limitations.

## Still required before upload

- [x] Run the official ICLR TeX build with MiKTeX 25.12 and inspect the
      resulting PDF at 100% and print size. From
      `submission\paper`, use the staged style directory explicitly:

      ```powershell
      $miktexBin = Join-Path $env:LOCALAPPDATA 'Programs\MiKTeX\miktex\bin\x64'
      $env:Path = "$miktexBin;$env:Path"
      $iclrTexInputs = "..\source\iclr_style\iclr2027;$env:TEXINPUTS"
      $env:TEXINPUTS = $iclrTexInputs
      $env:BSTINPUTS = $iclrTexInputs
      bibtex manuscript
      pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex
      pdflatex -interaction=nonstopmode -halt-on-error manuscript.tex
      ```
- [x] Verify the rendered PDF has 10 pages total (8 pages of main text plus 2
      reference pages), no overfull boxes, no clipped captions, and no
      visible author metadata. The official ICLR 2027 author guidelines allow
      up to 9 pages of main text and exclude references from the limit.
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
      between the scarcity report and the two-condition rule, the
      post-governance world-state reweighting caveat, and the first-attempt gap.
- [x] The manuscript does not describe the paper as showing deception, gaming,
      a causal effect, universal behavior, or a corrected effect estimate.
