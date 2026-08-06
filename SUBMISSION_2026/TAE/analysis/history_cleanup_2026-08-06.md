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

## The commands — PowerShell

Paste one block at a time from the repository root. In this session, prefix a line with `! ` to run
it here.

### 1. Rewrite the range, and move the tag with it

```powershell
cd C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
$env:FILTER_BRANCH_SQUELCH_WARNING = "1"

git filter-branch -f --tag-name-filter cat --index-filter 'git rm -r --cached --ignore-unmatch ":(glob)ICLR2027/submission/figures/candidates/**/*.png" ":(glob)ICLR2027/submission/figures/candidates/**/*.pdf"' origin/main..HEAD
```

Three details, each deliberate:

- **`--index-filter`** touches only the index, so nothing is ever checked out. It is the fast form
  and it cannot disturb your working tree — the 52 files stay on disk throughout.
- **`--tag-name-filter cat`** moves `firstattempt-launch-2026-08-05` onto the rewritten commit.
  Without it the tag keeps pointing at the pre-rewrite object and is orphaned.
- **`origin/main..HEAD`** limits the rewrite to your 49 commits. `main` and the three
  `feat/coupling-*` branches are untouched. **`--prune-empty` is deliberately omitted**: a commit
  that only added candidates becomes empty rather than vanishing, and its message is part of the
  record.

The pathspec was verified read-only before this file was written: `**/*.png` matches 47,
`**/*.pdf` matches 1, and the four `README.md` files match neither. The outer quotes are PowerShell
single quotes (literal) and the inner are double quotes, because git hands the string to `sh`, not
to PowerShell.

### 2. Verify before pushing

```powershell
git rev-list --count origin/main..HEAD
#   expect 49

(git log --format=%s origin/main..HEAD | Out-String).Trim().Split("`n").Count
#   expect 49

(git ls-files 'ICLR2027/submission/figures/candidates').Count
#   expect 4   -- only the READMEs remain tracked

(git log --name-only --format= origin/main..HEAD | Select-String 'candidates.*\.png').Count
#   expect 0   -- the rasters are gone from history

(git diff --name-only origin/main..HEAD).Count
#   expect 307   (355 - 48)

(Get-ChildItem ICLR2027\submission\figures\candidates -Recurse -File).Count
#   expect 52   -- still on disk, which is the point

git log -1 --oneline firstattempt-launch-2026-08-05
#   expect the "chore(provenance): track the submission workspace..." commit
```

**If any of these disagrees, stop and restore:**

```powershell
git reset --hard backup-before-filter-2026-08-06
```

That command is on this workspace's deny list, so it is one you run rather than an agent — which is
also why the backup branch was made before anything else.

### 3. Push

```powershell
git push -u origin p0-1-governance-instrumentation
git push --tags
```

### 4. Afterwards, once you are satisfied

```powershell
git branch -D backup-before-filter-2026-08-06
git reflog expire --expire=now --all
git gc --prune=now --aggressive
```

The `gc` reclaims the 49.4 MB locally. Without it the objects stay in your clone, unreachable, until
the reflog expires on its own.

---

## What this does NOT fix

**The PII already in `main`'s history.** `SUBMISSION_2026/ops/_lane_risk_register.md` records that
those blobs are reachable from **six of seven tags** (`v0.2.1` → `v0.6.0`), not only from `main`.
That needs `git filter-repo` across all refs plus a force-push, and it is a separate operation on a
repository that has already been made private for exactly this reason.

**Nothing in this rewrite makes that job harder or easier.** It touches only commits that have never
left this machine.
