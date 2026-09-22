# SUBMISSION_2026 — workspace index

One line per top-level file/directory under `SUBMISSION_2026/`, plus the
related workspace at the repo root. This file only describes what is
already there — it does not edit or re-date any of the files it points
to. Status is read off each item's own banners/headers, cross-checked
where a banner points elsewhere (e.g. `TAE/BACKLOG.md` naming which
earlier documents its venue decision supersedes). Written 2026-09-06.

Status legend: **CURRENT** (live, in-use) · **SUPERSEDED by …** (content
stands historically, a later decision overrides its plan/framing) ·
**RETRACTED (see banner)** (the file itself disclaims its own claims) ·
**DATA-unreleased** (on disk, not yet a released/citable arm) ·
**DEFERRED** (paused by an explicit user decision, not abandoned).

| Path | What it is | Status | Last relevant date |
|---|---|---|---|
| `audit/` | Synthesis-lane `MATERIALS_VERDICT.md` + 3 audit scripts (data-selection, synthesis-checks, claim-traceability) verifying the 14-cell workshop corpus | SUPERSEDED by `TAE/` — the verdict addressed `papers/workshop_skeleton.md`, which is now retracted; the audit's underlying defect findings are still cited from `TAE/BACKLOG.md` | 2026-07-30 |
| `CAMPAIGN_PLAN.md` | Master run-matrix / pre-registration from the original 7-agent campaign workflow (two-track workshop + AAMAS 2027 plan; flood-vs-irrigation decomposition choice) | SUPERSEDED by `TAE/` — venue, page-limit and flood-primary decisions overridden (`TAE/BACKLOG.md` rows D8, X5, X6); `TAE/` is itself superseded by `ICLR2027/` | 2026-07-29 |
| `decomposition/` | e1–e6 estimator scripts: how much of the published irrigation IBR gap survives once the post-treatment self-report conditioning is removed | CURRENT — mirrored on `origin/main` as `reproduction/` | 2026-07-30 |
| `evidence/` | Zero-GPU evidence scripts for the appraisal-composition finding (self-report shift under enforcement), fallback-semantics and executed-vs-proposed corrections | CURRENT — pipeline explicitly carried forward into `TAE/` (`TAE/BACKLOG.md` row D6: "the pipeline exists and is the thing to run") | 2026-07-30 |
| `ops/` | Environment reconnaissance (installed models, per-run costs) + archived raw lane outputs from the original campaign workflow | CURRENT (reference); one archived file is self-named superseded (`_lane_prereg_v1_superseded.md`) — does not affect the rest of the directory | 2026-07-29 |
| `PAPER_CLAIM_CONSTRAINTS_2026-09-03.md` | Ledger of what the `main` framework code can/cannot support, for paper-claim discipline (governance, coupling, calibration, deciders, ablation) | CURRENT — 2026-09-06 correction in §2 (world/state-conditioned rules exist beyond label rules) and a 2026-09-06 fix in §4 (benchmark-disagreement count), both logged in its own §8 | 2026-09-06 |
| `papers/` | 4-page workshop paper skeleton + supporting figure/table scripts (`workshop_evidence.py`, `fig1_regime_separation.png`) | RETRACTED (see banner) — `workshop_skeleton.md`'s own banner: the premise-revision mechanism and the flood-control framing were both falsified 2026-07-30; kept only for its section plan | 2026-07-30 |
| `README.md` | Top-level campaign overview: two-track venue table, appraisal-composition finding summary, non-negotiables | SUPERSEDED by `TAE/` — its venue table and Tier-1 framing are dead per `TAE/BACKLOG.md`'s sweep list (which names this file alongside `CAMPAIGN_PLAN.md` and `workshop_skeleton.md`); `TAE/` is itself superseded by `ICLR2027/` | 2026-07-30 |
| `reviewer_prep_2026-09-05/` | Pre-computed answers (r0–r34 scripts + CSVs landed, r35–r38 pending) to the questions a water-journal reviewer will ask about the framework paper | CURRENT — independently verified 2026-09-06 (opus review), 4 provenance defects found and fixed the same day (see its own README) — **DATA STATUS 2026-09-15: underlying corpora lost (`out/r18_restore_verification_2026-09-15.md`); numbers are pre-loss 2026-09-05...09-10 values, not currently re-verifiable against the original corpora. Regeneration landed (`faf1bb12` for gemma3:4b arms, `c3391a53` for gemma4:12b and initprop, `83fa97e1` for the 2026-09-22 extras); this package now carries both the frozen-corpus record and the regenerated set side by side (see `out/r25_table1_regen.md`)** | 2026-09-22 |
| `runs/` | `config_flood/` — a copy of the single-agent flood config surface (YAML + prompts); not run output despite the directory name | CURRENT (reference config, not data) | 2026-07-29 |
| `TAE/` | Full submission workspace for the TAE workshop: paper, evidence pipeline, run traces, plus 4 untracked `runs/firstattempt_gov_seed{43,44,45,46}/` dirs | SUPERSEDED by `ICLR2027/` — `TAE/README.md`'s own banner: venue withdrawn 2026-08-05 (organiser pulled out); the 4 `firstattempt_gov_seed*` dirs are **DATA-unreleased** — inventoried but no matched no-validator arm exists and provenance is flagged RED (`ICLR2027/LIVE_STATE.md`) | 2026-08-20 |
| `TODO_2026-08-21.md` | Ordered open-work list: PII history purge, `v0.6.0` push, then a ranked experiment backlog | CURRENT — no supersession banner; postdates the TAE withdrawal by two weeks and is not referenced as dead by anything read for this pass | 2026-08-21 |
| `../ICLR2027/` (repo root, related workspace — not under `SUBMISSION_2026/`) | Active ICLR 2027 submission package: manuscript, figures, handoff docs | PAUSED 2026-09-22, all conference submissions paused; see `TAE/DECISION.md` | 2026-08-11 |

13 rows (12 top-level `SUBMISSION_2026/` entries + 1 related-workspace row
for `ICLR2027/`).

## Notes found while indexing, not corrected here

- The multi-agent flood case (Paper 3) is **DEFERRED** per the 2026-09-06
  scope decision (`.research/experiment_plan_framework_paper_2026-09-06.md`
  Tier 2) — it does not have its own row above because no top-level
  `SUBMISSION_2026/` file or directory is specifically the Paper-3/MA-flood
  workspace; the deferral is a fact about the run plan, not about a
  document in this folder.
- `README.md` line 3 says "Gitignored (`.gitignore:291`). This repo is
  public; nothing here is for the public tree." That claim is stale: the
  current `.gitignore` does not exclude `SUBMISSION_2026/` wholesale, only
  specific patterns under it (`**/runs/**` minus config dirs, `__pycache__`,
  `**/paper/*.log|*.out|*.pdf`, etc. — see `.gitignore` lines 373–435).
  Consistent with that, `git status` shows most of this tree tracked:
  `PAPER_CLAIM_CONSTRAINTS_2026-09-03.md` is modified (not ignored), and
  `TAE/runs/firstattempt_gov_seed{43..46}/` and `reviewer_prep_2026-09-05/`
  are untracked-but-visible (not ignored either, or `git status` would not
  list them). Not corrected here per the no-edit-those-files instruction;
  flagged for whoever next touches `README.md`.
