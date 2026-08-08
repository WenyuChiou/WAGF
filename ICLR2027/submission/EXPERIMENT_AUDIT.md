# First-attempt experiment audit

Updated 2026-08-08. This is an evidence-boundary record for the ICLR package;
it is not a manuscript result section. The active manuscript remains based on
the frozen corpus and does not use the runs below.

## What is present

Five governed-only first-attempt runs are on disk for the `gemma3:4b`
irrigation configuration, seeds 42--46. Their snapshots request both
`initial_proposal_columns: true` and `executed_skill_columns: true`, so the
new audit fields needed to inspect retry-time appraisal drift are present. The
decision-row counts are 3,276, 3,276, 3,275, 3,275, and 3,276 respectively.
The E7 appraisal-drift self-test passes all four mutation checks.

The read-only governed-only diagnostic is:

| seed | retried decisions | comparable initial/final labels | changed | entered HIGH | left HIGH | drift among comparable |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 42 | 2,010 | 1,865 | 845 | 323 | 263 | 45.31% |
| 43 | 2,104 | 1,949 | 860 | 330 | 257 | 44.13% |
| 44 | 2,068 | 1,928 | 815 | 317 | 263 | 42.27% |
| 45 | 1,969 | 1,836 | 796 | 294 | 259 | 43.36% |
| 46 | 1,827 | 1,694 | 677 | 259 | 205 | 39.96% |

These are descriptive properties of the governed-only branch. They cannot
answer whether validation changes appraisal drift, because the corresponding
no-validator first-attempt arm is absent. They are therefore not a new paper
claim, a new figure, or a reason to change the title or contribution statement.

## Provenance gate

The reproducibility checker returns **RED** for all five runs because every
manifest records `git_dirty=true`. Additional release issues are visible in
the artifacts:

- seed 42 has no `LAUNCH_COMMAND.txt`, no `memory_seed`, and no final commit
  field;
- seeds 43--46 have launch-command files, but the recorded start/final commits
  differ across runs;
- seeds 44 and 45 are each one decision row short of the expected 3,276;
- the configuration is recorded by a run-local snapshot and absolute path, but
  the exact clean, versioned configuration/runner state has not been released;
- all five manifests report the same model family and strict profile, but that
  does not repair the dirty-worktree boundary.

The integrity files say `integrity_ok: true`; that is a useful schema and
runtime check, not a substitute for clean source provenance. The two checks
answer different questions and are kept separate here.

## Decision for the manuscript and figures

Do not merge these diagnostics into the ICLR paper. In particular:

1. Figure 1 continues to show the retry/default-action route because the
   frozen paper's primary statistic uses the executed action. The new fields do
   not make the frozen corpus preserve its historical first response.
2. Figure 2 remains the irrigation rule-layer audit; it does not become an
   appraisal-drift chart without a matched arm and a pre-registered question.
3. Figure 3 remains the irrigation world-state diagnosis, and Figure 4 remains
   the executed conditional-versus-all-decision comparison.
4. Flood remains a secondary Table 3 boundary check. The first-attempt branch
   does not change the example hierarchy or justify a Flood mechanism panel.

## Required release path

Cloud can request a manuscript update only after all of the following are
available and independently checked:

1. a matching no-validator first-attempt arm for seeds 42--46 with the same
   model, prompt/config snapshot, initial/executed fields, and row contract;
2. clean start and final commits, launch commands, model identity, and
   manifests for both arms;
3. a paired per-seed comparison of appraisal changes, with missing-label and
   retry denominators reported explicitly;
4. an updated handoff decision saying whether the result is descriptive
   support, a limitation, or a new estimand; and
5. a fresh manuscript, figure, and TeX review if and only if the result changes
   a claim.

Until then, the correct paper-level statement remains the narrower one: the
frozen corpus lacks the first response before a retry, so it cannot separate
within-decision report revision from selection into the observed accepted set.
