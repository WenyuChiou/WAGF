# Missing reproducibility steps and rerun decision

## Required before claiming exact historical reproducibility

- [ ] Do not claim GREEN or bitwise reproducibility: 15 runs lack a manifest commit, and legacy Git fields were sampled at finalization rather than launch.
- [ ] Release the generated `artifact_inventory.yml` with the paper artifact so current files are checksum-frozen.
- [ ] Add a concise Methods/Reproducibility disclosure distinguishing the full 21-pair retrospective corpus from the 10-pair observable-alignment sensitivity subset.
- [ ] Preserve the six unresolved constant-column sentinel findings as an audit limitation; do not relabel them reserved without a versioned declaration.
- [ ] Audit manuscript estimand dependencies before stating whether any sentinel column is unused; this generator deliberately makes no such claim.

## Sensitivity-only cells

- [ ] Sensitivity disclosure: `gemma3:4b` seed 42 — nearest-pretrace shared-runtime fingerprints differ; worker setting is not launch-attested in both arms.
- [ ] Sensitivity disclosure: `gemma3:4b` seed 43 — worker mismatch: strict=1, no-validator=4.
- [ ] Sensitivity disclosure: `gemma3:4b` seed 44 — nearest-pretrace shared-runtime fingerprints differ; worker mismatch: strict=1, no-validator=4.
- [ ] Sensitivity disclosure: `gemma3:4b` seed 45 — worker setting is not launch-attested in both arms.
- [ ] Sensitivity disclosure: `gemma3:4b` seed 46 — worker setting is not launch-attested in both arms.
- [ ] Sensitivity disclosure: `gemma4:e2b` seed 42 — nearest-pretrace shared-runtime fingerprints differ.
- [ ] Sensitivity disclosure: `gemma4:e2b` seed 43 — nearest-pretrace shared-runtime fingerprints differ.
- [ ] Sensitivity disclosure: `gemma4:e4b` seed 42 — nearest-pretrace shared-runtime fingerprints differ.
- [ ] Sensitivity disclosure: `gemma4:e4b` seed 45 — nearest-pretrace shared-runtime fingerprints differ.
- [ ] Sensitivity disclosure: `gemma4:e4b` seed 46 — nearest-pretrace shared-runtime fingerprints differ.
- [ ] Sensitivity disclosure: `ministral-3:8b` seed 44 — normalized config snapshots differ; nearest-pretrace shared-runtime fingerprints differ.

## Experiment rerun decision

- **Current descriptive trace-audit paper:** zero experiment reruns required to report the observed association. Integrate the observable-alignment subset as sensitivity and disclose all other pairs as provenance-limited.
- **If adding a first-attempt appraisal-revision claim:** a matched no-validator first-attempt arm and clean provenance become required; that is a different estimand and is not authorized by this audit.
- **If a reviewer requires clean-launch confirmation:** design the smallest prospective confirmation after review. Do not pre-emptively rerun all 50 cells.
