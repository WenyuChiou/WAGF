# Old and new commit ids (history rewrite of 2026-11-21)

On 2026-11-21 the repository history was rewritten with `git filter-repo` to remove
personal survey data that had been committed by mistake. Every commit id changed. The
files in commits that never held the removed data are unchanged.

Run records written before that date still name the old ids. They are not edited. Use
the files here to find the new commit for an old id.

| File | What it holds |
|---|---|
| `commit-map.txt` | Every rewritten commit: `old new`, one pair per line, as written by `git filter-repo` (header line first). No commit was dropped. |
| `paper_commits.tsv` | The commits the paper relies on, with their role, the tag that marks the new commit, and where the old id is used. |
| `paper_manifest_commits.tsv` | The commit fields of the 30 paper runs (15 flood, 15 irrigation), copied from their `reproducibility_manifest.json`. The run folders themselves are not in git. |

To look up an old id (full or a prefix of 7 or more characters):

```bash
grep '^9c4ba160' reproduction/history_rewrite/commit-map.txt
```

## The paper's commits

| Role | Old | New | Tag |
|---|---|---|---|
| Flood runs (15) | `9c4ba160` | `98b54298` | `paper-flood-runs` |
| Irrigation runs (15) | `6d06739e` | `25897813` | `paper-irrigation-runs` |
| Rule-based flood reference | `186abb29` | `24d62cb9` | `paper-flood-rulebased` |
| FQL irrigation reference | `6027deaa` | `28b34862` | `paper-irrigation-fql` |

- All 15 flood runs record `git_dirty: true` at launch and at finalize, with no list of
  the changed files. The tag marks the commit they started from, not an exact copy of the
  code that ran.
- The 15 irrigation runs record `git_dirty: false`.
- Each of the four commits has the same files before and after the rewrite.

`tests/test_history_rewrite_map.py` checks that every commit named in the 30 manifests
resolves through `commit-map.txt` to a commit in this repository. When the run folders
are present (on the machine that ran them), it also checks the manifests against
`paper_manifest_commits.tsv`. Set `WAGF_RESULTS_ROOT` to the checkout that holds them if
it is not this one.
