# nonudge config variant (2026-10, WRR26 rerun)

## What this is

A tracked, isolated `--config-root` for `examples/single_agent/run_flood.py`
that is byte-identical to the rebuilt `examples/single_agent/` config
(commit on `prep/flood-wrr-rerun`), with exactly one line removed from
`config/prompts/household.txt`.

## Author decision this implements

Flood design record PI decisions 2026-09-29 item 3 and 2026-10-06 item 5
("11 flood silent n = 5 added" list; the no-nudge arm itself approved
2026-09-29 item 3): a no-nudge arm that drops the WRR26 "Do Nothing" note
(design record row D4), as promised in the WRR26 response to reviewers
("a strong behavioral nudge ... ideally tested with ablation").

## The removed line

`config/prompts/household.txt`, between the options block and the rating
scale:

```
Note: If no flood occurred this year, since no immediate threat, most people would choose "Do Nothing."
```

Nothing else differs from the base `examples/single_agent/` config at the
same commit: `agent_types.yaml`, `skill_registry.yaml`,
`agent_initial_profiles.csv`, `flood_years.csv` are plain copies. Re-verify
with `diff -q` against the base files whenever the base config changes.

**Resync history**: `agent_types.yaml` drifted once (2026-10, same session)
-- `rule_id_prefix: false` and `initial_proposal_columns: true` were added
to the base config AFTER this variant's first copy, and the copy was not
updated at the same time. Caught because `flood_ibr_v2.py` raised `KeyError`
on a no-nudge run's audit CSV (missing `initial_skill`/`initial_labels`).
Re-copied and re-verified (`diff` reports no difference, 2026-10). Anyone
editing the base `agent_types.yaml` going forward MUST re-copy it here in
the same change -- this is the second time a `--config-root` variant has
needed this (see `wagf-main-runs/examples/single_agent/config_variants/
defaults_nonudge/NOTES.md` for the first, 2026-09-23).

## Commit note (P2-c / P3-11, opus review): `*.csv` is gitignored repo-wide, now negated

`.gitignore`'s blanket `*.csv` rule used to silently exclude
`agent_initial_profiles.csv` and `flood_years.csv` in THIS directory from
any ordinary `git add`/`git commit` of `config_variants/nonudge/` -- a plain
`git add examples/single_agent/config_variants/nonudge/` would add
`agent_types.yaml`, `skill_registry.yaml`, `config/prompts/household.txt`
and this `NOTES.md`, but SILENTLY DROP both CSVs, leaving a `--config-root`
that fails `_preflight_isolated_root`'s required-file check the first time
anyone actually runs it. Fixed at the root cause (P3-11): `.gitignore` now
has `!examples/single_agent/config_variants/**/*.csv` next to the other
`*.csv` negations (irrigation's own data-file negations, same section), so
an ordinary `git add` of this directory (or of any future
`--config-root` variant under `config_variants/`) picks up its CSVs
automatically. No `git add -f` step needed at commit time; verified with
`git add --dry-run -v examples/single_agent/config_variants/` listing both
CSVs (2026-10, this session). The test
`examples/single_agent/tests/test_config_variants.py` checks file CONTENT
(byte-for-byte against the base, modulo the one removed line); it does not
check `.gitignore`, which is why this note exists separately.

## Usage

```
python examples/single_agent/run_flood.py --model gemma3:4b --seed <N> --workers 1 \
  --governance-mode <strict|disabled> --thinking-mode disabled \
  --config-root examples/single_agent/config_variants/nonudge \
  --output examples/single_agent/results/JOH_<strict|disabled>_nonudge_<sha>/Run_<N>
```

See `examples/single_agent/docs/flood_wrr_rerun_runbook.md` for the full
command set (seeds, both governance modes).

## Predecessor

An earlier, untracked version of this idea lived at
`wagf-main-runs/examples/single_agent/config_variants/{nonudge,defaults_nonudge}`
(2026-09-23), built against the pre-rerun prompt (still carrying the 4
leading blank lines, the MULTI-ACTION block, etc.). This directory replaces
it for the WRR26 rerun; the old one is untracked and unaffected.
