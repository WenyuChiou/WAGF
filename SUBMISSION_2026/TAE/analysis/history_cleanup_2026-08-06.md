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
| **removed from history** | 48 rasters under `ICLR2027/submission/figures/candidates/` | 49.4 MB of file, **35.0 MB of branch** |
| **kept in history** | the 4 `README.md` files beside them | 7 KB |
| **put back on disk afterwards** | all 52, by an explicit step | 50 MB |

**Two different numbers, and the smaller one is the real one.** Summing the 48 files gives 49.4 MB.
The branch shrinks by **35.0 MB** — measured, `origin/main..HEAD` before and after: 70.9 MB (976
objects) → 35.9 MB (936 objects). Git stores content once, and the 48 paths resolve to 45 distinct
blobs; **9 of those 45 (10.8 MB) are byte-identical to files still tracked** under
`figures/assets/` and `figures/active/` — the candidates that were promoted to real figures. Those 9
still ship, under their production filenames. One of them,
`candidates/legacy/figure1/figure1_concept_print600_legacy.png`, is byte-identical to
`figures/active/figure1_concept.png`: the image filed as a retired candidate **is** the Figure 1 the
manuscript uses.

That is correct scoping — those paths were never targeted — but if the intent had been to purge the
*content* rather than untrack the *path*, this operation does not achieve it.

**The READMEs are deliberately kept.** They record why each generation round was refused, and
removing the reasoning while keeping nothing is the same inversion this repository has had to undo
three times already. A `.gitignore` rule landed alongside this file so new rasters cannot come back;
`.md` beside them is still tracked. They reference the purged filenames as backticked prose and
table cells rather than `![...]` embeds, so nothing renders as a broken image.

**The design covers three of the four subdirectories.** `candidates/legacy/figure1/` held 11 files,
all images, and **no README** — so that round leaves no record in git at all once
`backup-before-filter-2026-08-06` is deleted. The 11 files remain on disk, ignored, in this working
copy only. If any of them is worth keeping a reason for, write that README before dropping the
backup branch.

**Not touched:** `figures/active/` (the four figures the manuscript includes) and `figures/assets/`
(≈10 MB, the generation sources for the active Figure 1). Assets may or may not be worth trimming;
that needs someone to establish which are still inputs, and it was not established here.

---

## Before you start

A backup branch already exists, pointing at the current tip:

```
backup-before-filter-2026-08-06  ->  13456687
```

**Nothing below can lose work while that branch exists.** Delete it only after the push succeeds and
you have looked at the result.

Recorded baseline, to compare against afterwards:

| | |
|---|---|
| HEAD | `13456687` |
| commits ahead of `origin/main` | 52 |
| files changed vs `origin/main` | 356 |
| modified tracked files in the working tree | 12 — **filter-branch will not start until these are parked; see block 1** |
| tag `firstattempt-launch-2026-08-05` | `50247de3` — **inside the rewrite range** |
| md5 of the 52 commit subjects | `71739886ed44` |

The branch was at `aaf7b604` with 49 commits when this file was first drafted; the three since are
this file's own corrections. `aaf7b604` is an ancestor of `13456687`, so moving the backup forward
discarded nothing.

---

## Two things filter-branch does that this file originally got wrong

Both were found by rehearsing the whole sequence on a throwaway repository before writing this
version. Neither is guesswork.

**1. It refuses to start while the working tree is dirty.** Not a warning — it exits with
`Cannot rewrite branches: You have unstaged changes.` and does nothing. This tree has 12 modified
tracked files, and two of them are `ICLR2027/submission/paper/manuscript.tex` and its check report,
**which Codex was writing minutes before this was drafted**.

That rules out `git stash`. Stashing reverts those two files on disk to their committed content; if
Codex reads one during the rewrite he sees a stale version and writes over his own work. The park
step in block 1 uses a **temporary commit** instead, which never touches the working tree — verified
by md5 on a stand-in file edited to look exactly like Codex's.

**2. It deletes the filtered files from your working tree.** filter-branch ends with
`git read-tree -u -m HEAD`, and after the rewrite HEAD no longer lists the 48 rasters, so they are
removed from disk. An earlier version of this file claimed the opposite and told you to expect 52
files afterwards. Block 3 puts them back, and the verification checks for it.

They round-trip byte-exact: all 48 were compared on disk against their blobs (`sha256`), 48 matched,
0 differed, so restoring them cannot corrupt a PDF through line-ending conversion.

---

## The commands — PowerShell

Paste one block at a time from the repository root. In this session, prefix a line with `! ` to run
it here. Blocks 1–3 are **one operation** — do not stop between them.

### 1. Park the working tree, rewrite, unpark

```powershell
cd C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
$env:FILTER_BRANCH_SQUELCH_WARNING = "1"

git add -u
git commit -m "TEMP: park working tree for history rewrite"

git filter-branch -f --tag-name-filter cat --index-filter 'git rm -r --cached --ignore-unmatch ":(glob)ICLR2027/submission/figures/candidates/**/*.png" ":(glob)ICLR2027/submission/figures/candidates/**/*.pdf"' origin/main..HEAD

git reset --mixed HEAD~1
```

- **`git add -u`** stages the 12 modified tracked files and nothing else. The 11 untracked
  directories are left alone — untracked files do not block filter-branch, and `add -A` would sweep
  `results_ops_e4b/` into a commit for no reason.
- **The temporary commit is thrown away four lines later** and never reaches the remote, so it is
  not a shipping commit and needs no review. The one active hook is
  `.githooks/pre-commit`, a secret scanner over the staged diff; these 12 files carry no
  credentials, so no `--no-verify` is needed. If it *does* fire, that is a finding — read it, do not
  bypass it.
- **`git reset --mixed HEAD~1`** undoes the temporary commit and returns the 12 files to unstaged.
  `--mixed` is spelled out rather than left implicit so it cannot be misread as `--hard`; it never
  touches the working tree.
- **`--index-filter`** rewrites only the index, so nothing is checked out per commit. It is the fast
  form.
- **`--tag-name-filter cat`** moves `firstattempt-launch-2026-08-05` onto the rewritten commit.
  Without it the tag keeps pointing at the pre-rewrite object and is orphaned.
- **`origin/main..HEAD`** limits the rewrite to your commits, plus the temporary one while it
  exists. `main` and the three `feat/coupling-*` branches are untouched. **`--prune-empty` is
  deliberately omitted**: a commit that only added candidates becomes empty rather than vanishing,
  and its message is part of the record.

The pathspec was verified read-only before this file was written: `**/*.png` matches 47,
`**/*.pdf` matches 1, and the four `README.md` files match neither. The outer quotes are PowerShell
single quotes (literal) and the inner are double quotes, because git hands the string to `sh`, not
to PowerShell.

### 2. Put the candidate images back on disk

```powershell
git restore --source=backup-before-filter-2026-08-06 -- ICLR2027/submission/figures/candidates/
```

`git restore --source` writes the working tree **without** staging, so the rasters land on disk and
stay untracked — which is what the `.gitignore` rule added alongside this file intends. `git checkout
<branch> -- <path>` would stage them and undo the whole exercise; it is also on this workspace's
deny list.

### 0. Record the baseline first

Every commit to this repository moves the numbers below, so read them off the repository rather than
trusting the table above. Run this **before block 1** and keep the window open:

```powershell
$before = @{
  commits = (git rev-list --count origin/main..HEAD)
  files   = (git diff --name-only origin/main..HEAD).Count
  dirty   = (git status --porcelain | Where-Object { $_ -match '^ M' }).Count
  ondisk  = (Get-ChildItem ICLR2027\submission\figures\candidates -Recurse -File).Count
}
$before
```

Block 3 compares against `$before`, so it stays correct no matter how much the branch has moved.

### 3. Verify before pushing

```powershell
git rev-list --count origin/main..HEAD
#   must equal $before.commits
#   one MORE means the temporary commit is still in; rerun 'git reset --mixed HEAD~1'

(git status --porcelain | Where-Object { $_ -match '^ M' }).Count
#   must equal $before.dirty   -- the parked changes are back, unstaged

(git status --porcelain | Where-Object { $_ -match '^M ' }).Count
#   expect 0    -- nothing left staged

(git ls-files 'ICLR2027/submission/figures/candidates').Count
#   expect 4    -- only the READMEs remain tracked

(git log --name-only --format= origin/main..HEAD |
   Select-String '^ICLR2027/submission/figures/candidates/.*\.(png|pdf)$').Count
#   expect 0    -- the rasters are gone from history
#
#   The pattern MUST be anchored. An earlier version of this file used
#   'candidates.*\.png', which also matches
#   SUBMISSION_2026/TAE/figures/_candidates/fig1_WAGF_imagegen_paper_release_source.png
#   -- a different directory that was never in scope. It returns 1 on a PERFECTLY CORRECT
#   rewrite, and the instruction below is "stop and restore". That check would have destroyed
#   a good rewrite. It also missed the one .pdf, so it under-tested in the other direction.

(git diff --name-only origin/main..HEAD).Count
#   must equal $before.files - 48

(Get-ChildItem ICLR2027\submission\figures\candidates -Recurse -File).Count
#   must equal $before.ondisk  -- back on disk after block 2
#   4 between blocks 1 and 2 is the expected intermediate, not a failure

git log -1 --oneline firstattempt-launch-2026-08-05
#   expect the "chore(provenance): track the submission workspace..." commit
```

**If any of these disagrees, stop and restore:**

```powershell
git reset --hard backup-before-filter-2026-08-06
```

That command is on this workspace's deny list, so it is one you run rather than an agent — which is
also why the backup branch was made before anything else. It discards the working-tree state too, so
if Codex has written since block 1, copy `ICLR2027/submission/paper/manuscript.tex` aside first.

### 4. Push

```powershell
git push -u origin p0-1-governance-instrumentation
git push origin refs/tags/firstattempt-launch-2026-08-05
```

**Push the tag by name. Not `--tags`.** The remote carries five tags (`v0.2.1` … `v0.5.1`); this
clone has eight. `--tags` would create **three** remote tags, not one: the intended
`firstattempt-launch-2026-08-05`, plus `v0.29.0` and `v0.6.0`. Both of those are ancestors of
`origin/main`, so they add no bytes — they add two more refs that the still-pending PII
`filter-repo` purge would have to rewrite. `v0.6.0`'s tree carries both survey CSVs.

**Never `git push --all` or `--mirror` from this clone.** `backup-before-filter-2026-08-06` still
holds all 48 images at its tip and lives under `refs/heads`, so `--all` would publish them and undo
this entire operation in one command. `--mirror` additionally reaches
`refs/original/refs/heads/p0-1-governance-instrumentation`, the temporary park commit. The explicit
refspecs above send neither.

### 5. Afterwards, once you are satisfied

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
