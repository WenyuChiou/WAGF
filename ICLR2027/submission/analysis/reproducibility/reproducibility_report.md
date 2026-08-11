# Historical irrigation forensic reproducibility report

## Scope

- Input: `examples/irrigation_abm/results`, restricted to the 42 historical LLM irrigation runs used by the ICLR evidence pipeline.
- Runs surveyed: 42 (21 strict/no-validator seed pairs across five models).
- Observable artifacts checked: manifest, run-local config snapshot, raw JSONL, audit CSV, simulation CSV, recovered launcher or command evidence where available, pre-trace committed code fingerprint, realized year-1 prompt, and cross-file `(agent_id, year)` joins.
- This is a forensic salvage audit. It does not edit historical data or backfill missing launch metadata.

## Verdict

**RED for strict bitwise reproducibility; FORENSIC-SALVAGE PASS for the paper's bounded descriptive claim.** The legacy manifests cannot certify launch-time source because their Git fields were sampled at finalization. The full 21-pair observed corpus covers five models and all 21 pairs retain the same positive condition-share direction; a stricter 10-pair observable-alignment subset covers 4 models. No experiment rerun is required to report this retrospective association, provided that it is not presented as clean-launch reproduction or a first-attempt causal effect.

## Findings

1. **RED — historical manifest semantics were misread by the earlier audit.** All 42 runs predate `35c28291`, which moved Git sampling to construction time. In these historical manifests, `git_commit` and `git_dirty` were collected at finalization. Therefore the 27 `git_dirty=true` values do not establish that runtime files were dirty at launch; the 15 missing commits still prevent a GREEN reproducibility verdict. Fix: retain the legacy fields unchanged and publish this sidecar reconstruction.
2. **PASS — raw and tabular analysis rows are complete.** 42/42 runs contain exactly 3,276 audit rows, simulation rows, and valid raw `(agent_id, year)` records. Every raw-to-audit and raw-to-simulation key join is exact; every raw `state_after.request` matches `simulation_log.request` within `1e-6`. The parser separately records 2 metadata headers, 0 malformed JSON lines, 0 invalid data records, and 0 duplicate valid keys; metadata are not misclassified as observations.
3. **PASS — model-visible baseline parity is directly observed.** All 21/21 paired seeds have byte-identical year-1 prompts for all 78 agents. No irrigation prompt contains `[CRITICAL FACTORS`. This is stronger evidence for the realized model input than directory names or a reconstructed launcher alone.
4. **PASS with one declared sensitivity — run-local configuration identity and parity.** All 42/42 snapshots record the expected model, seed, and arm-specific governance profile. 20/21 pairs have identical normalized `config_snapshot.yaml` content after replacing only `metadata.governance_profile`. Ministral-3 8B seed 44 additionally records `shared.template_vars`; its realized year-1 prompts remain identical, but the pair is Tier B rather than silently pooled into the observable-alignment subset.
5. **PASS — an observable-alignment subset remains without new experiments.** 10/21 pairs align on normalized config, reconstructed nearest-pretrace shared-runtime fingerprint, launch-evidenced worker settings, exact year-1 prompts, and complete joins. This is not launch-attested provenance. The subset covers 4 of five models, and every included pair has `no-validator - strict > 0` for the recorded high-scarcity condition share.

| model | observable-alignment paired seeds | mean condition-share delta |
| --- | ---: | ---: |
| gemma3:12b | 3 | 21.27 pp |
| gemma4:e2b | 3 | 47.20 pp |
| gemma4:e4b | 2 | 43.93 pp |
| ministral-3:8b | 2 | 31.07 pp |

6. **YELLOW — 11 pairs remain sensitivity-only, not discarded.** Their raw artifacts are complete and their year-1 prompts match, but at least one reconstructed code-era, worker-evidence, or config criterion is unresolved or differs. They must not carry the observable-alignment robustness claim.

| model | seed | reason for Tier B |
| --- | ---: | --- |
| gemma3:4b | 42 | nearest-pretrace shared-runtime fingerprints differ; worker setting is not launch-attested in both arms |
| gemma3:4b | 43 | worker mismatch: strict=1, no-validator=4 |
| gemma3:4b | 44 | nearest-pretrace shared-runtime fingerprints differ; worker mismatch: strict=1, no-validator=4 |
| gemma3:4b | 45 | worker setting is not launch-attested in both arms |
| gemma3:4b | 46 | worker setting is not launch-attested in both arms |
| gemma4:e2b | 42 | nearest-pretrace shared-runtime fingerprints differ |
| gemma4:e2b | 43 | nearest-pretrace shared-runtime fingerprints differ |
| gemma4:e4b | 42 | nearest-pretrace shared-runtime fingerprints differ |
| gemma4:e4b | 45 | nearest-pretrace shared-runtime fingerprints differ |
| gemma4:e4b | 46 | nearest-pretrace shared-runtime fingerprints differ |
| ministral-3:8b | 44 | normalized config snapshots differ; nearest-pretrace shared-runtime fingerprints differ |

7. **PASS — the known v21 failure is not present by trace chronology.** 42/42 first-trace timestamps are after v21 fix `4be50921`. Where a manifest commit exists it remains useful as finalization evidence, not as an attested launch commit.
8. **YELLOW — Gemma-3 4B worker evidence is incomplete or mismatched.** No-validator seeds 42–44 explicitly used four workers in `run_ensemble.bat`; governed seeds 43–44 explicitly used one, while governed seed 42 was not launched by that script. Seeds 45–46 have no recovered versioned launcher. All five pairs therefore remain Tier B even though their realized year-1 prompts match and their deltas have the same sign.
9. **RED under the checker contract — constant sentinels remain unresolved.** The inventory records every column flagged by `detect_audit_sentinels_in_csv()`. No `reserved_columns.yaml` exists, so the audit does not label them benign. Whether these columns feed any manuscript estimand requires a separate dependency audit; this generator does not assert that result.
10. **Decision — do not start a full rerun.** For the current paper, report the full corpus as a retrospective descriptive association and use the observable-alignment subset only as a sensitivity check. Reconsider targeted reruns only if the paper is expanded to a first-attempt causal mechanism claim or a venue explicitly requires clean-launch confirmation.

## Reproducible Command List

```powershell
python ICLR2027/submission/checks/forensic_irrigation_provenance.py
python ICLR2027/submission/checks/forensic_irrigation_provenance.py --check
python SUBMISSION_2026/TAE/evidence/_verify_pipeline.py
python -m pytest broker/ tests/
```

## Caveats

- A nearest commit before the first trace is a time-bounded reconstruction, not an attested launch commit. The inventory labels it accordingly.
- Gemma-3 4B seeds 45–46 have no recovered versioned launcher. Their worker setting is treated as unknown, not inferred into the observable-alignment subset.
- Historical uncommitted runtime patches cannot be recovered from Git after the fact. Exact prompt parity, run-local configs, realized validation/audit fields, source-era fingerprints, and output joins reduce but do not erase that uncertainty.
- Ollama real-model inference is not bitwise deterministic at fixed seed; this report evaluates observable contracts and multi-seed direction, not byte-identical regeneration.
- CRSS reference data were gitignored and were not hashed at launch. The present artifact hashes freeze outputs, not the historical input-data checkout.
- First-attempt governed-only runs are outside this scope and remain excluded from the manuscript because no matched no-validator first-attempt arm exists.
