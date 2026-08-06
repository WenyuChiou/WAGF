# One-time history rewrite before the first push — commands for the repository owner

**Why you and not an agent:** `git filter-branch`, `git filter-repo` and `git push` are all blocked
by this workspace's permission floor. Everything below has been prepared and verified read-only; the
three commands that change anything have to be typed by you.

**Why now:** the branch `p0-1-governance-instrumentation` **does not exist on the remote yet**
(`git ls-remote --heads origin` lists only `main` and three `feat/coupling-*`). Rewriting it today
needs no force-push and disturbs nobody. After the first push it does. **This is the only free
window.**

---

## What is being removed, and what is not

| | files | size |
|---|---|---|
| **removed from history** | 48 rasters under `ICLR2027/submission/figures/candidates/` | **49.4 MB** |
| **kept in history** | the 4 `README.md` files beside them | 7 KB |
| **kept on disk, both** | all 52 | 50 MB |

The branch currently adds **80.1 MB**; 49.4 MB of it — **62%** — is rejected Figure 1 candidates.

**The READMEs are deliberately kept.** They record why each generation round was refused, and
removing the reasoning while keeping nothing is the same inversion this repository has had to undo
three times already. A `.gitignore` rule landed alongside this file so new rasters cannot come back;
`.md` beside them is still tracked.

**Not touched:** `figures/active/` (the four figures the manuscript includes) and `figures/assets/`
(≈10 MB, the generation sources for the active Figure 1). Assets may or may not be worth trimming;
that needs someone to establish which are still inputs, and it was not established here.

---

## Before you start

A backup branch already exists, pointing at the current tip:

```
backup-before-filter-2026-08-06  ->  aaf7b604
```

**Nothing below can lose work while that branch exists.** Delete it only after the push succeeds and
you have looked at the result.

Recorded baseline, to compare against afterwards:

| | |
|---|---|
| HEAD | `aaf7b604` |
| commits ahead of `origin/main` | 49 |
| files changed vs `origin/main` | 355 |
| tag `firstattempt-launch-2026-08-05` | `50247de3` — **inside the rewrite range** |
| md5 of the 49 commit subjects | `84d64dd6b5a4` |

---

## The commands

Run from the repository root. In this session, prefix each with `! ` to run it here.

### 1. Rewrite the range

```bash
FILTER_BRANCH_SQUELCH_WARNING=1 git filter-branch -f --index-filter \
  'git ls-files -z "ICLR2027/submission/figures/candidates" | \
   grep -zvE "\.md$" | xargs -0 -r git rm --cached --ignore-unmatch --' \
  origin/main..HEAD
```

`--index-filter` touches only the index, so it never checks files out — it is the fast form and it
cannot disturb your working tree. `origin/main..HEAD` limits it to your 49 commits; `main` and the
three `feat/coupling-*` branches are untouched. **`--prune-empty` is deliberately omitted**: a commit
that only added candidates becomes empty rather than disappearing, and its message is part of the
record.

### 2. Re-point the tag

The tag points into the rewritten range, so after step 1 it still names the old commit.

```bash
git tag -f firstattempt-launch-2026-08-05 \
  "$(git log --format=%H --grep='track the submission workspace' origin/main..HEAD | tail -1)"
```

Check it landed on the right commit before continuing:

```bash
git log -1 --oneline firstattempt-launch-2026-08-05
```

It should be the *"chore(provenance): track the submission workspace…"* commit.

### 3. Verify before pushing

```bash
# 49 commits, same subjects
git rev-list --count origin/main..HEAD          # expect 49
git log --format=%s origin/main..HEAD | md5sum  # expect 84d64dd6b5a4

# the rasters are gone from history, the READMEs are not
git log --all --name-only --format= origin/main..HEAD | grep -c 'candidates.*\.png'   # expect 0
git ls-files 'ICLR2027/submission/figures/candidates' | wc -l                          # expect 4

# nothing else moved
git diff --name-only origin/main..HEAD | wc -l  # expect 307  (355 - 48)

# the files are still on disk
find ICLR2027/submission/figures/candidates -type f | wc -l   # expect 52
```

**If any of these disagrees, stop.** `git reset --hard backup-before-filter-2026-08-06` restores the
prior state exactly — though note that command is on this workspace's deny list, so it is also one
you run rather than an agent.

### 4. Push

```bash
git push -u origin p0-1-governance-instrumentation
git push --tags
```

### 5. Afterwards

```bash
git branch -D backup-before-filter-2026-08-06   # only once you are satisfied
git reflog expire --expire=now --all && git gc --prune=now --aggressive
```

The `gc` reclaims the 49.4 MB locally. Without it the objects remain in your clone, unreachable,
until the reflog expires on its own.

---

## What this does NOT fix

**The PII already in `main`'s history.** `SUBMISSION_2026/ops/_lane_risk_register.md` records that
those blobs are reachable from **six of seven tags** (`v0.2.1` → `v0.6.0`), not only from `main`.
That needs `git filter-repo` across all refs plus a force-push, and it is a separate operation on a
repository that has already been made private for exactly this reason.

**Nothing in this rewrite makes that job harder or easier.** It touches only commits that have never
left this machine.
