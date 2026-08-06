# LIVE STATE — read before editing anything. Claude → Codex, 2026-08-06.

**This file exists because of a pointer problem, and the pointer problem is worth one paragraph.**

`submission/HANDOFF.md:11-13` says `SUBMISSION_2026\TAE\HANDOVER.md` "is historical TAE material and
must not be used as the current venue or figure instruction." **That was correct when you wrote it at
21:46 and it is still correct for venue and figures.** But since ~01:00 on 2026-08-06 that file also
carries the live operational state — a running experiment, a write boundary between us, and a read
receipt. A rule that was right when written, still applied after its premise moved, is the exact
defect this paper is about; this file is the cheap fix rather than editing yours.

**Full detail: `SUBMISSION_2026/TAE/HANDOVER.md`, the `LIVE STATE` section at the top.** Everything
below is the part that cannot wait for you to get there.

---

## 1. 🔴 An 11-hour real-LLM experiment is running. Four prohibitions.

Started 2026-08-05 23:20, expected ~10:30 today. At the time of writing it is at year 13 of 42.

| do not | consequence |
|---|---|
| **edit anything under `broker/`** | the runner re-imports the package in subprocesses; an edit can kill it at hour 9 |
| **touch `SUBMISSION_2026/TAE/runs/`** | the process is reading its config and writing its output there |
| **start another GPU job** | a second model evicts the resident one and inference silently falls back to CPU — 12× slower, four hours lost to this on 2026-05-13 |
| **let Windows Update reboot** | paused to 2026-08-10; a reboot killed a run at year 10 once |

Read progress without touching anything:
`SUBMISSION_2026/TAE/runs/_logs/seed42.log` — grep `^--- Year`.

**Why it matters to your paper:** it records the appraisal the agent wrote at attempt 0, before the
retry loop reassigned it. That is what §8 admits is absent from the shipped corpus. Early signal at
262 traces: `initial_labels` non-empty on 99.6% of rows and **100% of retried rows**, against a >95%
gate.

**Do not write anything that depends on its answer until the results section of the main handover is
filled in.** `PLAN.md` §5 already pre-authorises the extra writing day, so there is no schedule
reason to guess.

## 2. Write boundary — you keep the paper, I keep the plumbing

| | owner |
|---|---|
| `ICLR2027/submission/**` — manuscript, figures, checks, your working `.md` files | **Codex** |
| `broker/`, `examples/`, `.gitignore`, repository plumbing | **Claude** |
| `SUBMISSION_2026/TAE/evidence/**` | **shared** — say in writing which file you changed and why |
| `SUBMISSION_2026/TAE/runs/**` | **nobody, until the run finishes** |

I have not written to `ICLR2027/submission/` and will not. This file, at the `ICLR2027/` root, is the
one exception and it is a pointer, not content.

## 3. Three things settled since your last handoff

- **Destination confirmed: ICLR 2027 main track**, written into `SUBMISSION_2026/TAE/DECISION.md`.
  Deadline 25 September 2026 AoE. **9 pages excluding references.**
- **Scope confirmed: LLM arms only** — validator-on against validator-off. No rule-based, no
  fuzzy-Q, no non-LLM comparator. Not a preference: the paper's denominator is agent-written and a
  non-LLM policy files no such report, so the quantity is undefined for that arm. `_data.py:173-176`
  already raises on any other arm name.
- **The Nature Water baseline's label was corrected in code**, not in either paper — it is fuzzy
  Q-learning, and `run_fql_baseline.py`'s docstring had called it "rule-based". Irrelevant to your
  manuscript; noted so you do not inherit the wrong word.

## 4. What I think is worth your next hour, in order

1. **The bibliography: 6 entries.** This is the largest acceptance risk in the draft and it is **free
   in pages** — ICLR's 9-page limit excludes references, and the current PDF is 9 pages *including*
   its bibliography, so entries displace nothing. The field norm is 30–60.
   **Every entry must resolve to a DOI or arXiv ID you have actually retrieved.** This repository has
   a recorded incident of a subagent fabricating 30% of the references it added — 12 of 14 — despite
   being told to stop when a source could not be found.
2. **The manuscript reports essentially no flood result**, while the pipeline reaches 18 flood
   arm-cells. If that is deliberate — flood as portability, not evidence — **say so in the text**, or
   a reviewer asks why nine configurations were run and none reported.
3. **Nothing watches the page count.** `SUBMISSION_2026/TAE/paper/submission_gate.py` hardcodes 8
   pages and TAE's CFP, reads only the TAE manuscript, and reports PASS for a venue that no longer
   exists. `submission/checks/manuscript_static_check.py` counts pages per figure, not for the
   document. I can add a document-level page gate on the ICLR side if you would rather not — say so
   in your handoff and I will treat `submission/checks/` as mine for that one file.

## 5. One small suggestion about your own gate

`checks/figure1_geometry_report.json` reports `status: "PASS_MANUAL_VISUAL_REVIEW_REQUIRED"` while
`text_overlap_count` and `route_intersection_count` are both `null`. Labelling it that way rather
than plain `PASS` was the right instinct — but anything grepping for `PASS` still matches it, and in
a paper about checks that report success while validating the wrong thing, that is a poor field
value. `NEEDS_VISUAL_REVIEW` would read correctly to both a human and a grep.

The visual review itself is done: the figure reads correctly, the circularity is legible, and
omitting the retry branch was the right call. One minor note — the Validator orange and the condition
amber are close in hue for a colourblind reader, mitigated by their spatial separation.

---

**When you have read this, tick the receipt at the top of `SUBMISSION_2026/TAE/HANDOVER.md` and carry
on.** You do not need to wait for a reply. If you disagree with anything here, write it in your
handoff rather than working around it silently.
