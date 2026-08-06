# Provenance release decision — 2026-08-04

## Scope

This decision covers the 42 irrigation runs used by the active TAE manuscript,
not every historical directory under `examples/irrigation_abm/results/`.

## Evidence checked

- `reproducibility_inventory.py` selected 42 runs and found 27 enriched manifests
  and 15 minimal manifests.
- The WAGF reproducibility checker found 27 manifests with `git_dirty=true` and
  15 manifests missing historic `git_commit`, `config_hash`, and/or `timestamp`
  fields. These facts cannot be reconstructed from the output files without
  inventing provenance, so they remain RED.
- The checker invoked the console `pytest` executable and received an import-path
  collection error (`ModuleNotFoundError: examples`). The canonical module
  invocation `python -m pytest broker/ tests/ -q` completed with exit code 0.
  This invocation issue is not treated as a WAGF test failure.
- The current evidence pipeline still regenerates the manuscript's tables and
  figures from the selected run files: 15/15 scripts pass in the submission gate.

## Release decision

The historical run provenance is **not reproducible-GREEN**. It is also **not an
upload blocker for this venue**. The official TAE CFP requires one anonymized PDF
through OpenReview, allows up to eight body pages, and describes the accepted
work as non-archival; the CFP does not list a code, data, or manifest upload
requirement:
<https://tai-eval.github.io/cfp/>.

The manuscript therefore keeps the limitation in its Artifact Availability
paragraph and makes no bitwise-reproducibility claim. The project-state issue is
recorded as `WAIVED`, not `RESOLVED`: the waiver is limited to the TAE upload
decision, and the remaining scientific provenance risk is visible to reviewers.

## What is and is not being claimed

- **Claim supported:** the current evidence scripts reproduce the displayed
  tables and figures from the run files on disk.
- **Claim not supported:** every historic LLM run can be regenerated from a clean
  source commit, configuration hash, model digest, and timestamp.
- **No action taken:** no missing commit, hash, timestamp, or `git_dirty=false`
  value was written into historic manifests.

## Functional decision

For the named TAE workshop PDF, provenance is a disclosed limitation rather than
a submission-format blocker. The CFP also does not state a dual-submission
permission or prohibition, so this decision does not infer one. For a venue
requiring clean artifact provenance, this same corpus would remain **not ready**
until the affected runs are reproduced or replaced with cleanly recorded runs.
