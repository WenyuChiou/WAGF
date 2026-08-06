# Arm: `fql_nogov` — the same decision kernel with the validators switched off

**Run 2026-08-06.** Ten seeds, about ten seconds of CPU, no GPU, no LLM.

> ## ⚠ NOT PART OF THE NATURE WATER CORPUS
>
> **This arm is not used by any paper.** It was run to answer one question during an audit and the
> answer is below. It is kept because the result is informative and cost ten seconds; it is labelled
> because this repository has been bitten before by a directory that looked like paper data and was
> not.
>
> Nature Water's irrigation baseline is `examples/irrigation_abm/results/fql_raw/seed{42-51}`, the
> arm **with** validators. Nothing here replaces it.

| | |
|---|---|
| **run directories** | `examples/irrigation_abm/results/fql_nogov/seed42` … `seed51` |
| **kernel** | Fuzzy Q-Learning, Hung & Yang (2021), via `examples/irrigation_abm/run_fql_baseline.py` |
| **the one difference** | `--no-governance` — all 12 irrigation validators skipped |
| **command** | `--real --years 42 --seed <S> --rebalance-clusters --no-governance --from-logs examples/irrigation_abm/results/production_v21_42yr_seed42` |
| **cost** | ~1 s per seed. No LLM inference at any point. |
| **read by** | nothing |

---

## 1. The question

Nature Water's Extended Data Table 1 reports the FQL arm with the best water-system numbers in the
table — minimum Lake Mead 999 ft, against 988 for the with-validators LLM and 895 for the
no-validator LLM. That arm runs **through WAGF with all twelve validators active**
(`run_fql_baseline.py:7`), and 71% of its proposed actions are blocked.

So: **how much of the FQL arm's conservatism is the decision kernel, and how much is the validator
stack?** The runner already had a `--no-governance` flag; nobody had used it.

## 2. Result

Ten paired seeds, same runner, same `--real --years 42 --rebalance-clusters`, differing only in the
flag.

| | validators ON (the shipped arm) | validators OFF |
|---|---|---|
| actions blocked | **71.1% ± 4.1** | 0% |
| demand ratio | 0.352 ± 0.013 | **0.583 ± 0.028** |
| demand-increase decisions | 24.7% | **57.4%** |
| minimum Lake Mead | **999.3 ft ± 4.7** | **895.0 ft ± 0.000** |
| seeds ever reaching dead pool | **0 of 10** | **10 of 10**, for 8–23 years each |

All three behavioural differences carry the same sign on all ten seeds. Per-seed demand ratio moves
+0.181 to +0.251, never overlapping.

**895 ft is the dead-pool floor** — `supplementary_information_v15.md:590`, "the 2.0 MAF floor
corresponds to the 895 ft dead-pool elevation". The `± 0.000` is that floor, not a coincidence.

## 3. What it means, stated carefully

**The FQL kernel is not a conservative agent. It is a constrained one.** Left to itself it drives the
reservoir to dead pool in every seed, in the same way the no-validator LLM does. The 999 ft in
Extended Data Table 1 is produced by the validator stack, not by Q-learning.

Two things this does **not** say:

- It does not say the shipped FQL arm is wrong. That arm answers "what does governance do to a simple
  kernel", and it answers it correctly. This one answers a different question.
- It does not say the two ungoverned conditions behave identically. They do not: mean absolute
  difference between the ungoverned-FQL and no-validator-LLM Lake Mead traces is 45.6 ft across the
  42 years, maximum 111.9 ft. They differ in path and agree only in destination — both end at the
  floor.

## 4. The limitation that stops this being publishable as it stands

**The initial condition is not matched.** Year-1 Lake Mead is 1,085.7 ft here against 1,052.8 ft in
all three shipped conditions. The likely cause is `--from-logs`: this arm reconstructs agent profiles
from `production_v21_42yr_seed42` for every seed, and **the shipped `fql_raw` arm carries no
`reproducibility_manifest.json`, so what it used cannot be established from the artefacts.**

That gap does not threaten the qualitative finding — a 33-foot difference in year 1 does not explain
ten seeds sitting at the floor for 8 to 23 years — but it does mean **no number here should be quoted
against the shipped arm** until the initial condition is aligned. Anyone picking this up should fix
that first.

## 5. Why it was not used

The author's decision, 2026-08-06: **Nature Water is a paper about LLM agents.** The FQL row is a
reference point, not a subject, and Figure 2's claim is trajectory similarity rather than a ranking
of conditions. Adding a fourth trace, or expanding the footnote's account of the governance
condition, would spend the reader's attention on the arm that is not the subject.

Recorded here rather than argued further, with one observation left for whoever returns to it: the
trajectory similarity between the with-validators LLM and the FQL arm is **partly produced by their
shared validator stack**, which this experiment demonstrates by removing it. That reading supports
the paper's thesis — institutional rules dominate the outcome regardless of the reasoning substrate —
but it is a different sentence from the one the figure currently carries.

## 6. One number to reconcile before either is quoted again

Extended Data Table 1's footnote states that **84–89%** of FQL actions were rejected by governance.
Pooled over all ten seeds and all 32,760 rows, `fql_blocked` is true on **23,291 — 71.1%**. Per-seed
values range 63.7% to 76.2%; none reaches 84%.

The denominators may differ — the footnote may count per-cell, or restrict to a decision subset. It
is a small check, not a defect, but the two numbers should not both appear in circulation.

---

*Read-only against `fql_raw/`, which was not modified. Written before the arm was used for anything,
per the rule in [`examples/EXPERIMENTS.md`](../../EXPERIMENTS.md).*
