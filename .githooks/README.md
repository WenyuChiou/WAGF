# `.githooks/` — repo-tracked git hooks

This directory holds **shared git hooks** that live in the repo (so they
follow the code) rather than under `.git/hooks/` (which is per-clone
local-only and disappears on re-clone).

## Active hooks

| Hook | What it does | Severity |
|---|---|---|
| `pre-commit` | Secret-scan: rejects commits whose **staged content** contains hardcoded API keys (Zotero / OpenAI / Anthropic / GitHub PAT / AWS / generic). | BLOCK |

## One-time installation (per clone)

After cloning the repo, point git at this directory:

```bash
# from the repo root
git config core.hooksPath .githooks
```

That writes a single line into `.git/config`. The hook fires on every
subsequent `git commit` in this clone. No `pip install` needed — the
scanner uses only Python stdlib.

To **verify** the hook is wired up correctly:

```bash
echo 'ZOTERO_API_KEY = "AAAABBBBCCCCDDDDEEEEFFFF"' > _smoke.txt
git add _smoke.txt
git commit -m "smoke" --dry-run
#  → expect "SECRET-SCAN HOOK — commit BLOCKED" + exit non-zero
rm _smoke.txt   # discard
```

## What's scanned

Only the **staged diff content** of files in the index (added /
modified / renamed / copied; not deletions). The hook does NOT scan
the working tree, does NOT scan git history, does NOT scan remote, and
does NOT make any network calls.

Patterns checked (all BLOCK on match):

| Class | Pattern (simplified) |
|---|---|
| Zotero API key (quoted) | `ZOTERO_API_KEY = "<20+ alphanumeric>"` |
| Unquoted credential (`.env`-style) | `(ZOTERO\|OPENAI\|ANTHROPIC\|API\|SECRET\|PASSWORD\|TOKEN\|ACCESS)_KEY = <20+ alnum>` at line start |
| OpenAI `sk-proj-` (modern) | `sk-proj-[A-Za-z0-9_-]{20,}` |
| OpenAI legacy | `sk-[A-Za-z0-9]{20,}` |
| Anthropic | `sk-ant-[A-Za-z0-9_-]{20,}` |
| GitHub PAT | `ghp_[A-Za-z0-9]{30,}` |
| GitHub OAuth | `gho_[A-Za-z0-9]{30,}` |
| AWS access key | `AKIA[A-Z0-9]{16}` |
| Generic quoted credential | `(api_key\|secret\|password\|token\|access_key) = "<20+ alnum>"` |

False-positive handling has **two tiers** (see `_line_excepted` in the hook):

1. **Env-var lookup markers** (`os.environ`, `os.getenv`, `process.env.`,
   `ENV[`, `getenv(`) — substring match anywhere on the line. Safe
   because these strings cannot appear inside a real secret value.
2. **Placeholder-value tokens** (`REDACTED`, `EXAMPLE_KEY`, `REPLACE_ME`,
   `PLACEHOLDER`, `<your-`, `your-api-key`, `fake_key`, `dummy_key`)
   — checked **only inside quoted strings on the line**. A line like
   `KEY = "real-secret"  # was REDACTED, now set` will still trigger
   the hook because `REDACTED` lives in the comment, not in the value.

Path-level skip rules (`_SKIP_PATH_PATTERNS`):
- `.githooks/` itself (so this README + the hook source don't trip on
  their own examples).
- `CHANGELOG.md` (anchored to root only — historical incident notes
  are intentional documentation).
- `tests/fixtures/` and `test/fixture/` subdirectories specifically —
  not every test file with "fixture" in its name.

## Handling a legitimate false positive

If the hook blocks a commit that's genuinely fine (e.g. a doc example
showing what a key *looks like*):

1. **Preferred** — defang the literal in-file: replace the example with
   `<your-key>` / `REDACTED` / `EXAMPLE_KEY`, or use `os.environ.get(...)`.
2. **If the example must stay literal** — add a per-line marker word
   from `_LINE_EXCEPTIONS`, or add a per-path entry to
   `_SKIP_PATH_PATTERNS` in the hook source.

## Bypass (last resort)

```bash
git commit --no-verify   # skips ALL git hooks for this one commit
```

`--no-verify` should be **rare and intentional**. The bypass is not
silent — it leaves a `--no-verify` trace that PR review can flag. If
you need to use it, mention the reason in the commit body so future
readers understand.

## Why this hook exists

A Zotero API key (`hLGhkxO20sXiKpMF62mGDeG2`) was committed to this
repo's history across 8 commits between 2026-02 and 2026-05 before
being scrubbed from current `HEAD` in commit `8c6e48c` (env-var swap).
The key is still in `git log -p` history; the only true mitigation is
**rotation** at the Zotero account level (committed in the
`8c6e48c` commit body).

This hook prevents the same pattern from happening again by catching
hardcoded credentials at commit-time, before they reach the remote.
See `CHANGELOG.md` Phase 6N-F-6 for the full incident close-out.

## Not a substitute for

- **Key rotation when leaks happen** — the hook can only prevent
  future leaks, not undo past ones.
- **Repository-wide secret scanning** — for that, install
  [gitleaks](https://github.com/gitleaks/gitleaks) or
  [detect-secrets](https://github.com/Yelp/detect-secrets) which scan
  full history with a much larger pattern catalogue. The pre-commit
  hook here is a fast, dependency-free first line of defence; a
  CI-side scanner is the canonical second line.
- **Reviewing `--no-verify` commits in PR review** — bypasses are
  intentional; reviewers must confirm they're justified.
