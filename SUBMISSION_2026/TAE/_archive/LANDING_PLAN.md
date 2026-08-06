# LANDING_PLAN.md — applying the ministral3:8b balancing run

**Written 2026-08-03 ~21:10.** Executable without re-deriving anything.

---

## 0. READ THIS FIRST — the run already landed, and most of this plan is already applied

This plan was commissioned while `ungoverned_v21_42yr_ministral3_8b_seed44` was still being
written, on the assumption that nothing could be applied yet. **That assumption is now false.**
Measured at 21:05:

```
$ ls -la examples/irrigation_abm/results/ungoverned_v21_42yr_ministral3_8b_seed44
simulation_log.csv   1929971   Aug  3 14:38          <-- exists; run finished 14:38
$ wc -l < .../simulation_log.csv
3277                                                  <-- 3,276 rows + header, the required count
```

and a concurrent session has already applied the code and manuscript changes. So this document is
**not** a from-scratch apply plan. It is a *state-detecting* plan: §1 tells you which stage you are
in, §2 gives the ordered sequence with each step's own detection check so that re-running an
already-applied step is a no-op rather than damage.

Every step below is written to be **idempotent**. If a detection check says a step is already done,
skip it — do not re-apply.

### The branch decision was made, and it was Branch A

The earlier analysis offered Branch A (admit the cell) and Branch B (keep it excluded on a new
code-vintage reason). **Branch A was taken.** `_data.py` now reads:

```python
IRRIGATION_UNBALANCED_PREFIXES: frozenset[str] = frozenset()
```

I did not make this choice and cannot reverse it on my own authority. §6 records the one fact that
would have argued for Branch B, so the decision stays visible rather than silently settled.

---

## 1. STAGE TABLE — what is done, what is left

All rows verified by command at 21:05–21:10 on 2026-08-03.

### Stage 1 — corpus, code, claims, manuscript: **DONE**

| item | verification | result |
|---|---|---|
| Run complete | `wc -l < .../seed44/simulation_log.csv` | `3277` = 3,276 + header |
| Header matches anchor | `head -1` both | byte-identical, 22 columns |
| Run integrity | `cat .../run_integrity.json` | `"integrity_ok": true` |
| Corpus balanced | `corpus_inventory.py` | exit 0, `VERDICT: PASS`, ministral 42,43,44 both arms |
| F1 frozenset cleared | `sed -n '198,205p' evidence/_data.py` | `frozenset()`, dated comment |
| F3 self-test inverted | `grep "absent irrigation seed accepted"` | now seed `999`, not `44` |
| F14 `_verify_pipeline` inventory | `sed -n '34,50p'` | `[42,43,44], [42,43,44]` |
| BRIEF tuples rewritten | `grep "ministral3:8b" evidence/_verify_pipeline.py` | `(3, 3.25, 6.05, +2.80, 54.35, 32.18, -22.17)` |
| Pipeline green | `run_all.py` | `13 PASS, 0 not-PASS` |
| Claims guard | `submission_gate.py` | `98 markers used, all sourced; 98 claims defined, all used` |
| Manuscript Table 1 row | `manuscript.md:257` | `\| irrigation \| ministral3:8b \| 3 \| 13.56 \| 44.69 \| +31.13 \| 3.25 \| 6.05 \| +2.80 \|` |
| Manuscript disclosures | `grep -n "unbalanc" paper/manuscript.md` | only in the §DECISION audit log (lines 729/735), which is *supposed* to be historical |
| `21 paired seeds` | `manuscript.md:358, 375` | both say 21 |

Note the claim count moved **99 → 98**: `ministral_balance` was deleted, which Branch A requires
because `substitute.py` fails on a defined-but-unused claim.

### Stage 2 — tracking / documentation layer: **NOT DONE**

Nine files still assert the exclusion in the present tense. None of them is built into the PDF, so
none blocks submission — but a future editor reading them would reintroduce a claim that is no
longer true. This is the bulk of the remaining work.

### Stage 3 — fonts: **NOT DONE, optional**

The only red gate. Cosmetic, venue-compliant either way. See §2 S7.

---

## 2. THE ORDERED SEQUENCE

### S0 — snapshot for rollback · APPLY-VERBATIM · **do this before anything else**

`SUBMISSION_2026/` is gitignored (`.gitignore:291`), so there is **no git history to revert to**.
A file copy is the only rollback that exists.

```bash
cd /c/Users/wenyu/Desktop/Lehigh/governed_broker_framework
cp -a SUBMISSION_2026/TAE SUBMISSION_2026/_TAE_snapshot_2026-08-03_2110
ls SUBMISSION_2026/_TAE_snapshot_2026-08-03_2110/paper/manuscript.pdf   # must exist
```

Put the snapshot **outside** `TAE/`, as above — `run_all.py` and `submission_gate.py` walk `TAE/`,
and a nested copy of the tree would be scanned as if it were live. I did not create this snapshot
myself: my write scope for this round was `SUBMISSION_2026/TAE/` only, and the correct destination
is outside it.

**If `cp -a` fails** (permissions, disk): stop. Do not proceed to any editing step. Everything
after S0 is recoverable only through this copy.

---

### S1 — confirm the corpus before anything reads it · APPLY-VERBATIM

```bash
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/corpus_inventory.py
```

**Expect:** exit 0 and

```
VERDICT: PASS -- every cell COMPLETE and BALANCED, every column present, and _data.py agrees on every cell.
```

with the cross-check table showing `ministral3:8b  no-validator  42,43,44 / 42,43,44 / yes`, and the
`IRRIGATION_UNBALANCED_PREFIXES` section printing **nothing** (an empty set has no rows to print).

**If instead** you see `<<< STALE EXCLUSION`, the frozenset has been restored — go to S2. If you see
`_data.py CANNOT READ` or `refusing to return a partial cell`, a run directory is incomplete; stop
and diagnose the corpus, not the code.

**Why first:** every other script imports `_data.py`, which globs the results directories. If the
corpus is not what you think it is, every number downstream is wrong in a way that still exits 0.

---

### S2 — the frozenset · APPLY-VERBATIM · *already applied; detection only*

```bash
sed -n '196,206p' SUBMISSION_2026/TAE/evidence/_data.py
```

**Expect:** `IRRIGATION_UNBALANCED_PREFIXES: frozenset[str] = frozenset()` above a comment dated
2026-08-03 explaining that the mechanism is kept rather than deleted.

**If it still reads** `frozenset({"ministral3_8b_"})`, apply Branch A verbatim:

```python
#: Cells barred from every paired contrast because their two arms hold different
#: seeds. EMPTY as of 2026-08-03: ministral3:8b was the only member (3 governed
#: seeds against 2 no-validator) until its no-validator seed 44 run landed and
#: balanced the cell at 3 against 3. The mechanism is kept, not deleted, because
#: it is the guard that would catch the next unbalanced cell; ``corpus_inventory``
#: cross-checks this set against what is actually on disk and fails on a stale
#: entry, which is how the removal was triggered rather than remembered.
IRRIGATION_UNBALANCED_PREFIXES: frozenset[str] = frozenset()
```

and also fix the self-test at `_data.py:1080` — `must_raise("absent irrigation seed accepted", ...)`
must use seed **999**, not 44. Seed 44 now exists, so leaving it turns a guard that asserts *an
absent seed is refused* into one asserting *a present seed is refused*; it would fail, and the
obvious "fix" is to delete the guard.

**Why before re-running the pipeline:** while the prefix is in the set, `excluded_from_paired()`
returns True and seven downstream scripts keep dropping the cell. You would read back the old
2-seed numbers and conclude nothing had changed.

---

### S3 — regenerate and harvest · NEEDS-A-NUMBER (already harvested; re-verify)

```bash
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/run_all.py
```

**Expect:** `total 13 script(s): 13 PASS, 0 not-PASS`.

**Command that produces each number**, if you are running this fresh and the BRIEF tuples still
disagree:

| number | produced by | lands in |
|---|---|---|
| Table 1 ministral row (n, HIGH on/off/Δ, cond on/off/Δ) | `table1_cells.py` sections A + B | `manuscript.md:257`, `NUMBERS.md`, BRIEF tuples |
| cond/uncond Δ + 95% CI + p | `fig3_consequence.py` PLOTTED VALUES | `substitute.py` `ministral_cond_delta` / `ministral_uncond_delta` |
| never-retried Δ, pooled 21-seed deltas | `fig2_mechanism.py` PANEL C | `substitute.py` `pooled_*_delta` |
| per-seed rejection ranges | `fig1_rule_layers.py` PANEL B | `substitute.py` range claims |

On a fresh run **steps 2–5 will exit 1 on the first pass.** That is the hardcoded BRIEF cross-checks
firing correctly, not a bug. Read the DISAGREES line, copy the *computed* value into the BRIEF tuple,
re-run, confirm exit 0. **Do not tune the computation to match the brief.**

Current harvested values, for cross-reference only — re-derive rather than trusting this table:

```
ministral3:8b  LAST-PROPOSED  3.25  6.05  +2.80 (+0.02,+5.58) p=0.049 | 54.35 32.18 -22.17 (-29.02,-15.32) p=0.005
Table 1 row:   n=3  HIGH on 13.56  off 44.69  Δ +31.13
pooled, 21 paired seeds:  all-decisions +40.02   never-retried +48.21   (were +40.45 / +49.09 at 20)
```

**Two things to notice in those numbers**, because both were open questions before the run landed:

1. The **sign reversal survived** balancing, and grew: −21.12 → −22.17, with all three per-seed
   deltas sharing the sign (−19.05, −23.20, −24.27). The old explanation in `substitute.py` —
   "what comparing unequal seed counts looks like" — is therefore **falsified**, not merely stale.
   It has already been replaced with a sourced note recording the falsification. Verify with
   `grep -n -A8 ministral_uncond_delta SUBMISSION_2026/TAE/paper/substitute.py`.
2. `neverretried_larger_cells` is **still `5 of 5`** — the count did not move, so §5's sentence
   needed only its parenthetical removed, not its number changed.

---

### S4 — the independent re-derivation · APPLY-VERBATIM

```bash
sed -n '34,50p' SUBMISSION_2026/TAE/evidence/_verify_pipeline.py
```

**Expect:** `"ministral3:8b": ("ministral3_8b_", [42, 43, 44], [42, 43, 44])` and a BRIEF row of
`(3, 3.25, 6.05, +2.80, 54.35, 32.18, -22.17)`.

**Why this step is called out separately even though `run_all.py` covers it:** `_verify_pipeline.py`
does not import `_data.py`. Its inventory is hardcoded, by design — the whole point is to agree with
`_data.py` by a different route. That means it is the one file in the pipeline that **will not fail
on its own** when the corpus changes: with a stale `[42, 43]` it keeps passing, keeps confirming the
old 2-seed numbers, and keeps printing `pooled(20)` while `_data.py` computes 21. Two
implementations would disagree about which corpus exists and the one reporting PASS would be the
wrong one. Check it by eye; do not rely on its exit code.

Also confirm the pooled labels moved: `grep -n "pooled(2" SUBMISSION_2026/TAE/evidence/_verify_pipeline.py`
should show **21**, not 20.

---

### S5 — manuscript and `substitute.py`, in ONE change · APPLY-VERBATIM · *already applied*

```bash
grep -n "unbalanc\|excluded from every paired\|20 paired seeds" SUBMISSION_2026/TAE/paper/manuscript.md
```

**Expect:** hits **only** at lines ~729 and ~735, which are inside the §DECISION audit log and are
deliberately historical (they narrate the change and are marked `SUPERSEDED LATER THE SAME DAY`).
No hit anywhere in the body, in a caption, or in Table 1's caption.

The eleven body sites are already resolved. Current state, spot-checked:

- Figure 2 caption (~204): asterisk sentence **gone** (`fig1_rule_layers.py` no longer draws one).
- Table 1 caption (~249): exclusion sentence **gone**; ends `...share one line and carry no conformance rate.`
- §5 (~355): parenthetical **gone**.
- §5/§6 (358, 375): `21 paired seeds`.
- Figure 3 caption (~379) and Figure 4 caption (~435): interval/unfilled sentences **gone**.
- §6 (402–406): rewritten to the sign disagreement, both deltas with intervals at df = 2, and the
  width caveat. Both CLAIM markers retained.
- §8 (~477): exclusion sentence **gone**.

**Why manuscript and `substitute.py` must move together:** `substitute.py` fails on an unmatched
marker *and* on an unused claim. Deleting `{{CLAIM:ministral_balance}}` from the manuscript without
deleting its definition fails the unused check; deleting the definition first fails the unmatched
check. Either half alone breaks the build. `ministral_balance` is now deleted from both — which is
why the guard reads 98/98 and not 99/99.

**If a marker error appears:** run `python SUBMISSION_2026/TAE/paper/substitute.py --check` and read
which side it names. Do not "fix" it by re-adding a claim whose reason no longer exists.

---

### S6 — the tracking layer · APPLY-VERBATIM · **THE REMAINING WORK**

Nine files still assert the exclusion in the present tense. None is built into the PDF
(`substitute.py:678` reads `MANUSCRIPT_MD` only; `sections/` feeds nothing), so **none of this
blocks submission**. It is correctness of the record, and protection against a future editor
reinstating a dead caveat.

| file : line | current text (stale) | action |
|---|---|---|
| `README.md:134` | "Any cell whose two arms have different seed counts is **excluded from every paired contrast**... the exclusion list is `_data.IRRIGATION_UNBALANCED_PREFIXES`" | keep the *rule* (it is still the policy), but it now covers no cell — say so |
| `README.md:137-141` | "As of the last check `ministral3:8b` was the only excluded cell, and the run that would balance it was still being written" | **delete this sentence.** The rest of the paragraph is self-updating and already correct |
| `README.md:44-46` | `> **Today (3 Aug):** checks 2 and 3 are red...` | delete the whole block — `run_all.py` is now 13/13 |
| `PLAN.md:103` | "`ministral3:8b` excluded from every paired contrast and shown separately" | delete or mark resolved |
| `PLAN.md:291` (R4 risk row) | "is 3 governed vs 2 no-validator and is excluded from every paired contrast" | rewrite: the risk retired when the cell balanced; keep the sentence about `corpus_inventory.py` checking both directions, which is what caught it |
| `NUMBERS.md:932-936` | `*EXCL` flags on both ministral rows, plus "The `*EXCL` flag is now **stale**: `_data.IRRIGATION_UNBALANCED_PREFIXES` still names `ministral3_8b_` by hand" | **stale about being stale** — the set is now empty. Drop the `*EXCL` flags and replace the note |
| `NUMBERS.md:548-560` (§12) | "+40.45 (pooled gov 27.52, noval 67.98, n = 20 paired seeds)" and "a mean over all 20 paired seeds" | §5 was updated to 21 / +40.02 but this adjudication section was not. Add the same note `substitute.py:534-536` carries: the 2026-08-01 adjudication stands, the value moved to +40.02 because the pool grew to 21 |
| `SUBMISSION_READINESS.md:53` (fix #7) | "Reconcile 'excluded from every paired contrast' with '5 of 5' and '20 paired seeds'" | mark **RESOLVED** — the contradiction dissolved when the cell was admitted |
| `SUBMISSION_READINESS.md:246` (R6) | "5+3+5+5+2 = 20 only if ministral3:8b is in" | now `5+3+5+5+3 = 21` and it *is* in; mark resolved |
| `EXPERIMENT_OPTIONS.md:27, 334-353` | §5 "Do not run. This one is actively harmful" | **do not delete.** This is the pre-registered refusal and it is the audit trail for §6 below. Append that the run was made anyway on 2026-08-03 and what that means |
| `RUN_DECISION.md:220` | "More seeds on unbalanced cells \| Manufactures the mixed-vintage defect..." | same — append, do not rewrite history |
| `STATUS.md:311-352` | item 1a | **already updated** and correct; it carries the right framing verbatim: "This removes a caveat that stopped being true. It does not add a claim." |
| `BACKLOG.md:132` (D4) | | **already updated** |
| `sections/s5.md:67` | "20 paired seeds" | `sections/` is not built. Either fix to 21 or add a superseded banner at the top of the directory |

Two stale **line-number** references, both pointing at `_data.py:195` when the constant is at
**201**: `BACKLOG.md:132` and `EXPERIMENT_OPTIONS.md:345`. `PLAN.md:291` already handles this
correctly — "currently `_data.py:201` — search the name, not the line". Adopt that phrasing in both
rather than updating the number, which will only go stale again.

**Not editable from here:**
`examples/irrigation_abm/results/production_v21_42yr_ministral3_8b_seed44/_DEFECT_unpaired_orphan.txt`
still says the no-validator run "does not exist". That is now false. The file is under `examples/`,
outside this round's write scope, and was left untouched. Text for the author to **append** (do not
overwrite — the original flag is the audit trail):

```
RESOLVED 2026-08-03. The matching no-validator run now exists:
ungoverned_v21_42yr_ministral3_8b_seed44, completed 2026-08-03 14:38, 3,276 rows,
run_integrity.json integrity_ok true. The sentence above -- "does not exist" --
was true when written on 2026-05-30 and is false now. The ministral3_8b cell is
seed-BALANCED at 3 v 3 and is included in every paired contrast.
A SEPARATE issue remains and is NOT this defect: the new no-validator run records
git_commit 10e190cf with git_dirty true, while the other five runs in this cell
record no git_commit field at all. See SUBMISSION_2026/TAE/LANDING_PLAN.md section 6.
```

This file does not poison the run directory: `_data.py:260-263` lists `"defect"` and `"orphan"` in
`_CONTAMINATED_TOKENS`, but the guard inspects directory **segments**, not filenames.

---

### S7 — fonts · APPLY-VERBATIM · **LAST, and optional**

The only failing gate:

```
fonts       FAIL   12 embedded: 9 Type 1, 3 TrueType, 0 Type 3
```

**The venue rule is not violated.** `template/neurips_2026.tex:376` — "Your PDF file must only
contain Type 1 or Embedded TrueType fonts." Line 416 blocks "type 3 fonts or non embedded TrueType".
The three DejaVu faces are embedded TrueType (`/FontFile2` present on each), which is explicitly
permitted, and there are **0 Type 3**. This gate is a house style rule, not a submission blocker.
You may ship with it red.

If you want it green, the prepared patch is `evidence/probe_figure_font.patch` — STIXGeneral +
`mathtext.fontset="stix"`, keeping `pdf.fonttype=42`. Verified still applies against the edited
figure scripts:

```
$ git apply --check -v SUBMISSION_2026/TAE/evidence/probe_figure_font.patch
Hunk #1 succeeded at 435 (offset 21 lines).
exit=0
```

**Do not take the other option.** Setting `pdf.use14corefonts=True` was measured to (i) reintroduce a
**Type 3** font — the class the venue actually blocks — because there is no AFM path for mathtext and
`$\Delta$` falls back to DejaVu drawn as Type 3, and (ii) silently corrupt negative tick labels,
emitting byte `0x3f` (`?`) for U+2212 under `/WinAnsiEncoding`, with no warning. Six such glyphs
exist in the current figures. That trades a permitted condition for a forbidden one.

```bash
cd /c/Users/wenyu/Desktop/Lehigh/governed_broker_framework
git apply SUBMISSION_2026/TAE/evidence/probe_figure_font.patch
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/fig1_rule_layers.py
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/fig2_mechanism.py
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/fig3_consequence.py
```

**Acceptance criterion — `TEXT OVERLAP CHECK: 0` from each of the three.** Not "looks fine". Each
script computes rendered text-box intersections and raises `RuntimeError("rendered text boxes
overlap")` on a non-zero count (`fig1:495/499`, `fig2:486/490`, `fig3:371/375`).

**If any prints non-zero:** revert the patch (`git apply -R`), regenerate, and leave the fonts gate
red. Changing the type family changes text metrics, which is exactly what can reintroduce the label
overlaps three earlier rounds removed. STIX is narrower than DejaVu Sans at equal point size so
pressure should *fall* — but that is a prediction, and the check is what settles it.

Then re-run `submission_gate.py`; FONTS should list 3 non-Type-1 entries, now STIXGeneral. The
gate's TrueType note is advisory and `--allow-truetype` is the intended switch.

**Why last:** its acceptance criterion is a text-overlap count that is only measurable once the
figures can render, which requires the corpus to be readable and `_data.py` to be settled. Ordering
it earlier means either measuring overlaps on figures you are about to regenerate anyway, or
discovering an overlap and being unable to tell whether the font or the new seed caused it.

---

## 3. WHY THIS ORDER

The sequence is forced by four real dependencies, not by preference:

1. **S1 before everything.** `corpus_inventory.py` is the only script that measures the corpus
   *against* `_data.py`'s own rules and reports disagreement instead of smoothing it. Running it
   after any edit means you no longer know whether a change in the numbers came from the run landing
   or from your edit.
2. **S2 before S3.** The frozenset gates `excluded_from_paired()`, which seven scripts key off. Edit
   it last and the pipeline keeps excluding the cell — you would re-run everything, see the old
   2-seed numbers, and conclude the run had not landed.
3. **S5 as one atomic change.** `substitute.py`'s two guards (unmatched marker / unused claim) fail
   in opposite directions, so splitting the manuscript edit from the claim-definition edit breaks the
   build whichever half you do first.
4. **S7 last.** Its acceptance criterion is unmeasurable until figures render again.

S6 sits between S5 and S7 only because it is the largest remaining block and touches nothing the
build reads; it could equally run after S7.

---

## 4. ROLLBACK

**The state to return to** — measured 21:05–21:10 on 2026-08-03, all by command:

| property | value |
|---|---|
| `corpus_inventory.py` | exit 0, `VERDICT: PASS` |
| `run_all.py` | `total 13 script(s): 13 PASS, 0 not-PASS` |
| `submission_gate.py` | exit 1, `NOT READY -- 1 of 7 gates FAILED (fonts)`; evidence/figures/build/pages/anonymity/citations all PASS |
| pages | 9 pp; body ends p8; References first thing on p9 |
| claims guard | `98 markers used, all sourced; 98 claims defined, all used` |
| bibliography | 14 references, 14 cited, `[1]..[14]` contiguous |
| `manuscript.log` | 0 LaTeX errors, **0 overfull**, 8 underfull, 9 pages, 230,043 bytes |
| e4 anchor | `md5 02536fe93f2798b4ab2b65717cd8d7ef`, `VERDICT: HOLDS` |
| `table1_cells.csv` | `md5 92d27e9ec23e91dbffe35c8fdd37b62f` |

**To restore:**

```bash
cd /c/Users/wenyu/Desktop/Lehigh/governed_broker_framework
rm -rf SUBMISSION_2026/TAE                     # prompts; this is the destructive step
cp -a SUBMISSION_2026/_TAE_snapshot_2026-08-03_2110 SUBMISSION_2026/TAE
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/paper/submission_gate.py
```

and confirm the table above reproduces. **There is no `git checkout` path** — `SUBMISSION_2026/` is
gitignored, so the snapshot from S0 is the only rollback that exists. If S0 was skipped, the code and
manuscript edits are unrecoverable; the corpus under `examples/` is untouched either way, so a full
re-derivation from raw runs is the fallback of last resort.

**Partial rollbacks that do work without the snapshot:**

- Font change only: `git apply -R SUBMISSION_2026/TAE/evidence/probe_figure_font.patch`, then
  regenerate the three figures. `git apply` operates on the worktree regardless of gitignore.
- Any single doc edit in S6: these are additive text changes with no build dependency; re-editing is
  as safe as reverting.

**Do not "roll back" by restoring `IRRIGATION_UNBALANCED_PREFIXES = {"ministral3_8b_"}` alone.**
`corpus_inventory.py` would then report `STALE EXCLUSION` and fail, and the manuscript would have no
disclosure to match it. Restoring the exclusion means restoring the manuscript prose and the
`ministral_balance` claim at the same time — i.e. the whole snapshot.

---

## 5. DEFINITION OF DONE

Checkable by command. Not one of these is a judgement call.

```bash
cd /c/Users/wenyu/Desktop/Lehigh/governed_broker_framework
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/corpus_inventory.py   # 1
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/evidence/run_all.py            # 2
PYTHONIOENCODING=utf-8 python SUBMISSION_2026/TAE/paper/submission_gate.py       # 3
grep -rn "unbalanc\|excluded from every paired\|20 paired seeds\|\*EXCL" \
     --include=*.md SUBMISSION_2026/TAE/                                          # 4
```

| # | criterion | passing output |
|---|---|---|
| 1 | corpus | exit 0, `VERDICT: PASS`, no `STALE EXCLUSION`, no `IN PROGRESS` |
| 2 | pipeline | `13 PASS, 0 not-PASS` |
| 3 | gates | **all seven PASS** — requires S7; 6/7 with fonts red is a deliberate, defensible stopping point (see §6) |
| 3a | pages | `pages PASS  9 pp; body ends p8, References from p9, limit 8` |
| 3b | build | 0 LaTeX errors, 0 overfull boxes, claims `N markers / N claims` balanced |
| 4 | consistency | every remaining hit is inside a section explicitly marked historical (the §DECISION log in `manuscript.md`, `EXPERIMENT_OPTIONS.md` §5, `RUN_DECISION.md:220`, `STATUS.md` item 1a). **Zero present-tense assertions that the cell is unbalanced or excluded.** |

Criterion 4 is the one that needs a human to read output rather than an exit code. The test is
tense: "was excluded until its seed 44 run landed" is correct and should stay; "is excluded" is not.

---

## 6. WHAT IS **NOT** IN THIS PLAN, AND WHY

### Nothing that changes what the paper claims

The author's standing instruction of 2026-08-03 is that nothing may be added to the manuscript that
changes what it claims. This plan adds nothing. Specifically excluded:

- **The gemma4 replication numbers.** They stay in `NUMBERS.md` as traceable evidence. They do not
  enter the manuscript.
- **Any ministral3:8b decomposition result.** `e4_world_fixed_decomposition.py` accepts a cell
  argument and can now run the ministral cell at 3 v 3, but **no non-anchor cell feeds any
  `{{CLAIM:...}}` marker** — `world_residual_coarse`, `world_residual_finest`, `world_coverage_*`,
  `world_residual_max`, `world_weighting_swing` and `world_min_cell_finest` are all sourced from the
  anchor cell in `NUMBERS.md` §13/§13a. A cross-model decomposition sentence would be a new claim.
  Record the result in the evidence layer; write nothing.
- **Any reinterpretation of the surviving sign reversal.** The reversal grew from −21.12 to −22.17
  and all three per-seed deltas share its sign. The manuscript states the disagreement and declines
  to interpret it. Explaining it now would be a new claim.

### Removing the exclusion is **not** a claim change — this is the point most likely to be misread

A future reader auditing this work may see eleven manuscript sites edited and conclude the standing
instruction was violated. It was not, and the distinction is worth stating plainly:

> The paper never claimed ministral3:8b was unbalanced as a *finding*. It disclosed the imbalance as
> a *limitation on its own evidence* — a caveat explaining why one cell carried no interval. The run
> landing made that caveat factually false. **Removing a caveat that has stopped being true is not
> adding a claim; leaving it in would be asserting something false about the corpus.**

The claims themselves are unchanged in kind and direction: same estimands, same paired-t on seeds,
same df = *n* − 1 rule, same five irrigation cells, same `5 of 5` never-retried count. What moved is
that one cell's *n* went 2 → 3 and it gained the interval every other cell already had. `STATUS.md`
item 1a states this in the same terms and should be treated as the canonical framing.

### The pre-registered refusal, and the one fact that argues the other way

`EXPERIMENT_OPTIONS.md` §5 and `RUN_DECISION.md:220` **pre-registered a refusal to run this exact
run**, on the grounds that it "manufactures the mixed-vintage defect in cells currently clean on that
axis, converting a disclosed exclusion into an invisible confound". The run was made anyway. That
tension is real and is not resolved by this plan.

The relevant measurement, which the earlier analysis could not make because it sampled only the old
runs:

```
production_v21_42yr_ministral3_8b_seed42   git_commit=ABSENT
production_v21_42yr_ministral3_8b_seed43   git_commit=ABSENT
production_v21_42yr_ministral3_8b_seed44   git_commit=ABSENT
ungoverned_v21_42yr_ministral3_8b_seed42   git_commit=ABSENT
ungoverned_v21_42yr_ministral3_8b_seed43   git_commit=ABSENT
ungoverned_v21_42yr_ministral3_8b_seed44   git_commit=10e190cf...  dirty=True  ts=2026-08-03
```

So the vintage gap is not merely "four months apart". Five of the six runs record **no commit at
all**, and the sixth records a **dirty** tree. The gap is unrecordable, which means it cannot be
audited later even in principle.

This is the fact that would have supported Branch B — keeping the cell excluded on a *code-vintage*
criterion rather than a *balance* criterion. **Branch A was taken instead**, and this plan implements
Branch A because that is the applied state. Two consequences the author should decide on explicitly,
neither of which I have authority to settle:

1. Whether §8's provenance-defect list should gain a sentence recording the mixed vintage. That
   **would** be adding a disclosure to the manuscript, so it engages the standing instruction and is
   the author's call — not a mechanical fix.
2. Whether `EXPERIMENT_OPTIONS.md` §5 should be marked overridden rather than silently left standing.
   My recommendation in S6 is to append, not rewrite: a pre-registration that gets quietly edited
   after the fact stops being a pre-registration.

### Not in scope for mechanical reasons

- `examples/`, `broker/`, `paper/nature_water/` — never written this round. The `_DEFECT` file
  correction in S6 is supplied as text for the author to paste, not applied.
- `sections/*.md` — not built into the PDF; listed in S6 for completeness only.
- The `--allow-truetype` switch as a way to green the fonts gate. It works, but it silences a
  measurement rather than changing a fact; S7's patch changes the fact.
