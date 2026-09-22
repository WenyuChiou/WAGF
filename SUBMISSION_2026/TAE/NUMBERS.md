# NUMBERS.md — every numeric claim, and the line of stdout it comes from

> **DATA STATUS - 2026-09-15.** The numbers in this table are pre-2026-09-15
> corpus values. The corpus was lost and regenerated on 2026-09-15 with fresh
> seeds. The regenerated values pass the pre-registered band check but differ
> in point value from the numbers below (irrigation IBR 36.05 / 59.07 old vs
> 31.41 / 56.64 regenerated, per
> `SUBMISSION_2026/reviewer_prep_2026-09-05/out/r25_table1_regen.md`). The
> current table for any paper is
> `SUBMISSION_2026/reviewer_prep_2026-09-05/out/r25_table1_regen.md`, not this
> file. All conference submissions are paused as of 2026-09-22.

This is the red-team's file. One row per number the paper may print. If a number is in the
manuscript and not in this table, it is unsourced and must not ship.

**Regenerate everything, then check any row against the captured output:**

```
python SUBMISSION_2026/TAE/evidence/run_all.py
```

**Locator convention.** The "where in stdout" column names the script's own section heading and then
quotes a distinguishing fragment of the line, verbatim. Fragments are grep-able:

```
python SUBMISSION_2026/TAE/evidence/fig3_consequence.py | grep "gemma3:12b"
```

Line *numbers* are deliberately not used — they shift whenever a caveat is reworded, and a stale
line number is worse than no locator.

**Sign convention, on every Delta in this file:** `Delta = (no-validator) MINUS (with-validators)`.
Positive means the validators **lowered** the quantity. This convention has been got backwards once
before in this project's history; every row below is in it, and every figure axis carries it.

**Two action readings.** `LAST-PROPOSED` = `yearly_decision` as written = the reading every published
number uses. `EXECUTED` = `maintain_demand` substituted on `REJECTED` / `REJECTED_FALLBACK` rows.
Every rate row below is labelled. They are not interchangeable — see §7.

---

## 0. Status of the pipeline as captured

| script | exit | meaning |
|---|---|---|
| `_data.py` | 0 | `SELF-TEST: CLEAN` — 15 contamination guards all refuse, join checks pass |
| `e0_year1_exogeneity.py` | 0 | `YEAR-1 EXOGENEITY: HOLDS` — the cornerstone premise, re-derived locally |
| `e1_first_attempt_limits.py` | 0 | `e1: VERIFIED -- all four inspections reproduce, on all five anchor seeds.` — the §5/§8 first-attempt limitation, now scripted |
| `table1_cells.py` | 0 | every checkable cell agrees with the brief to <0.005 pp |
| `fig1_rule_layers.py` | 0 | `FIG 1: VERIFIED` |
| `fig2_mechanism.py` | **0** | PASS. (The pooled all-decisions cross-check was resolved 2026-08-01 — see §12. The value itself moved +40.45 → +40.02 on 2026-08-03 when the pool grew to 21 paired units.) |
| `fig3_consequence.py` | 0 | `AGREEMENT: every plotted value matches the brief's verified list to within 0.005 pp` |
| `_verify_pipeline.py` | 0 | `INDEPENDENT VERIFICATION: EVERY VALUE AGREES` — a second implementation, importing nothing from `_data.py`, reproduces the §2/§3 headline rates; `41 run directories read; forbidden-token hits: 0` |

**The table above does not list every script, and the pipeline keeps growing.** `e2`, `e3`, `e4`,
`e5` and `e6` were all added after it was written; `e4`/`e5`/`e6` source §13, §14 and §15 below, and
`e3` is deliberately **not** in `run_all.py`.

**No script count and no pass count is recorded in this file any more.** Three different counts
(9/9, 11/11, 12/12) were live in this file on the same day, in a document whose own contract is that
an unsourced number must not ship. `run_all.py` prints both itself:

```
python SUBMISSION_2026/TAE/evidence/run_all.py
```

A non-zero exit is the intended behaviour for a real disagreement — it stops the pipeline so it
cannot be skimmed past. The one historical disagreement is resolved and recorded in §12.

**If the pipeline is red, check the corpus before suspecting a number.** A half-written run
directory makes `_data.py` refuse the whole cell, which surfaces as several scripts failing on one
cause:

```
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py
```

---

## 1. The two rule layers separate — paper §3, Figure 1

Anchor cell `gemma3:4b`, irrigation, 5 seeds, pooled counts (this is a decomposition, not a paired
contrast, so no CI is attached).

| claim | value | script | where in stdout |
|---|---|---|---|
| no-validator rejections | 4,757 / 16,380 = **29.0%** | `fig1_rule_layers.py` | PANEL A · `no-validator       16,380     11,623     4,757          0           0     4,757   29.0` |
| …all of them the water-right precondition | **4,757 precondition, 0 behavioural rules (100%)** | `fig1_rule_layers.py` | PANEL A, same line: `precond` column 4,757, `rule:appr` 0, `rule:world` 0 |
| with-validators rejections | 6,469 / 16,380 = **39.5%** | `fig1_rule_layers.py` | PANEL A · `with-validators    16,380      9,911         0      3,840       2,629     6,469   39.5` |
| …all of them naming a validator rule (NOT all behavioural theory — see below) | **0 bare precondition, 6,469 named a rule (100%); of those, 3,840 (59.4%) appraisal-conditioned, 2,629 (40.6%) world-conditioned** | `fig1_rule_layers.py` | PANEL A, same line: `precond` column 0 |
| same two counts, independently recomputed | 39.5% / 29.0%, `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` | `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` | §C · `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` |
| " | " | `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` | §C · `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` |
| same two counts, third recomputation | 39.5% / 29.0% | `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` | §5 · `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` |
| behavioural rejections whose antecedent is the **self-reported appraisal** | **3,840 of 6,469 = 59.4%** | `fig1_rule_layers.py` | PANEL A · `-> of the 6,469 with-validators rejections, 3,840 (59.4%) name at least one rule whose` |
| purity of the split across all irrigation cells | **10 / 10 cells pure**, zero exceptions | `fig1_rule_layers.py` | VERIFICATION · `10/10 irrigation cells pure: no-validator rejections name ZERO behavioural` ; PANEL B `pure?` column all `True` |
| rejection rate range, with validators | **28.1 – 62.6%** | `fig1_rule_layers.py` | PANEL B, `rej%` column (`gemma4:e2b …  28.1`, `ministral3:8b … 62.6`) |
| rejection rate range, no validator | **0.9 – 29.0%** | `fig1_rule_layers.py` | PANEL B, `rej%` column (`ministral3:8b …  0.9`, `gemma3:4b …  29.0`) |

> **⚠ OPEN ITEM — three rows in the table above are UNSOURCED.** The rows for *"same two counts,
> independently recomputed"* and *"same two counts, third recomputation"* carry
> `[locator superseded by the 2026-07-31 rule-kind correction — regenerate on the 4 Aug freeze]` in
> place of both their script and their stdout columns, and have done since 31 July. The values
> (39.5% / 29.0%) may well be right, but **nothing points at the line that produces them, so nobody
> can check** — which is exactly what this file's own contract forbids. Treat it as an open item,
> not a formatting note: regenerate the locators from live `run_all.py` output, or delete the rows.

**Per-model breakdown of the row above** — every cell that makes up the 1.0–29.0% range, not just its
two endpoints. `fig1_rule_layers.py` PANEL B, `no-validator` rows, `rejected`/`total`/`rej%` columns:

| model | no-validator rejections | script | where in stdout (`fig1_rule_layers.py` PANEL B) |
|---|---|---|---|
| gemma3:4b (anchor) | 4,757 / 16,380 = **29.0%** | `fig1_rule_layers.py` | `gemma3:4b      no-validator       5  16,380     4,757   29.0     4,757          0           0   True` |
| gemma3:12b | 524 / 9,828 = **5.3%** | `fig1_rule_layers.py` | `gemma3:12b     no-validator       3   9,828       524    5.3       524          0           0   True` |
| gemma4:e2b | 586 / 16,380 = **3.6%** | `fig1_rule_layers.py` | `gemma4:e2b     no-validator       5  16,380       586    3.6       586          0           0   True` |
| gemma4:e4b | 239 / 16,380 = **1.5%** | `fig1_rule_layers.py` | `gemma4:e4b     no-validator       5  16,380       239    1.5       239          0           0   True` |
| ministral3:8b | 84 / 9,828 = **0.9%** | `fig1_rule_layers.py` | `ministral3:8b  no-validator       3   9,828        84    0.9        84          0           0   True` |

All 84 are the bare allocation-cap precondition. 19 of them, the ones in seed 44, write
`failed_rules = precondition_violation` where the other 65 write `Unknown`; the run is on a later
broker revision. `_data._NO_RULE_TOKENS` maps both literals to the precondition layer, which is
why the `pure?` column reads `True` and the purity row above still reads 10 / 10. Both literals
carry the identical `error_messages` value, `Precondition failed: 'not at_allocation_cap'
(field is True)`, and hit only `increase_large` / `increase_small`.

| claim | value | script | where in stdout |
|---|---|---|---|
| no-validator rejection rate, excluding the anchor cell (the other four configurations) | **0.9 – 5.3%** | `fig1_rule_layers.py` | derived: min/max of the four non-anchor rows in the table above (ministral3:8b 0.9%, gemma3:12b 5.3%) |

Also cross-checked directly against `figures/fig1_rule_layers.csv` panel b rows (`category = world-feasibility
precondition`, `arm = no-validator`): `gemma3:12b,no-validator,3,...,524,9828,5.3317` — 524/9,828 = 5.3317%,
rounds to the 5.3% used above and in §3 of the manuscript.

| no-validator rejections that are increase proposals | **6,187 / 6,190 = 99.95%** | `fig1_rule_layers.py` | PANEL C · `no-validator          6,190      6,187          0          3     99.95%` |
| with-validator rejections that are increase proposals | **21,251 / 31,313 = 67.87%** | `fig1_rule_layers.py` | PANEL C · `with-validators      31,313     21,251      9,953        109     67.87%` |
| …so the behavioural layer also blocks decreases | 9,953 / 31,313 = **31.8%** | *derived in the caption from the PANEL C line above; no line prints 31.8 itself* |
| agent-years sitting at ≥99% of the water right, no-validator anchor | **43.21%** | `fig1_rule_layers.py` | SUPPORTING · `gemma3:4b                 0.04%         43.21%` |
| …with validators | **0.04%** | `fig1_rule_layers.py` | same line |

**Structural fact, not a statistic** (read from `examples/irrigation_abm/config/skill_registry.yaml`,
printed by `fig1_rule_layers.py` under PANEL C): the precondition `not at_allocation_cap` is attached
to `increase_large` and `increase_small` **and to no other skill**, so the world layer cannot block
anything else. That is why the 99.95% above is near-total by construction, and the paper must say so
rather than present it as an empirical surprise.

---

## 2. The anchor cell — paper §4

`gemma3:4b`, irrigation, 5 paired seeds, cell value = **mean of per-seed rates**, LAST-PROPOSED.

| claim | value | script | where in stdout |
|---|---|---|---|
| conditional rate, with validators | **36.05** | `table1_cells.py` | §B · `gemma3:4b      LAST-PROPOSED  |    36.05    59.07   23.02` |
| conditional rate, no validator | **59.07** | `table1_cells.py` | §B, same line |
| conditional Delta | **+23.02** (95% CI +19.06, +26.98; p = 0.0001) | `fig3_consequence.py` | PLOTTED VALUES · `gemma3:4b       5    Y      +23.02      (+19.06,+26.98)  0.0001` |
| unconditional rate, with validators | **40.90** | `table1_cells.py` | §B, same line, `unc.gov` column |
| unconditional rate, no validator | **62.52** | `table1_cells.py` | §B, same line, `unc.nov` column |
| unconditional Delta | **+21.62** (95% CI +16.45, +26.80; p = 0.0003) | `fig3_consequence.py` | PLOTTED VALUES, same line |
| HIGH-appraisal prevalence, with validators | **37.08** | `table1_cells.py` | §A · `irrigation gemma3:4b        5      5    Y     5 |     39.49     29.04  -10.45 |    37.08    82.80   45.73   ( +40.24, +51.21)  0.000` |
| HIGH-appraisal prevalence, no validator | **82.80** | `table1_cells.py` | §A, same line |
| HIGH-appraisal prevalence Delta | **+45.73** (95% CI +40.24, +51.21; p < 0.001) | `table1_cells.py` | §A, same line |
| all three, independently recomputed | 36.05 / 59.07 / 40.90 / 62.52 / 37.08 / 82.80 | `_data.py` | §6 · `conditional rate                 36.05       59.07     23.02` and the two lines under it |

---

## 3. Every cell — paper §4 and §6, Table 1 and Figure 3

LAST-PROPOSED reading, paired seed basis. All 35 of these agree with the brief to <0.005 pp; the
agreement itself is printed line by line in `table1_cells.py` §C and `fig3_consequence.py` SELF-CHECK.

| model | n | cond gov | cond nov | cond Δ | unc gov | unc nov | unc Δ | where in stdout (`table1_cells.py` §B) |
|---|---|---|---|---|---|---|---|---|
| gemma3:4b | 5 | 36.05 | 59.07 | **+23.02** | 40.90 | 62.52 | **+21.62** | `gemma3:4b      LAST-PROPOSED  |    36.05    59.07   23.02` |
| gemma3:12b | 3 | 5.45 | 16.89 | **+11.44** | 41.36 | 41.52 | **+0.16** | `gemma3:12b     LAST-PROPOSED  |     5.45    16.89   11.44` |
| gemma4:e2b | 5 | 12.71 | 31.65 | **+18.94** | 22.80 | 38.05 | **+15.25** | `gemma4:e2b     LAST-PROPOSED  |    12.71    31.65   18.94` |
| gemma4:e4b | 5 | 23.67 | 41.08 | **+17.41** | 36.36 | 44.87 | **+8.52** | `gemma4:e4b     LAST-PROPOSED  |    23.67    41.08   17.41` |
| ministral3:8b | 3 | 3.25 | 6.05 | **+2.80** | 54.35 | 32.18 | **−22.17** | `ministral3:8b  LAST-PROPOSED  |     3.25     6.05    2.80` |

p-values and CIs for all five cells: `fig3_consequence.py` PLOTTED VALUES section, one line per
model. `ministral3:8b` was unbalanced (3 governed seeds against 2 no-validator) and excluded from
every paired contrast until its no-validator seed 44 run landed on 2026-08-03. It is now balanced
at 3 against 3 and carries an interval like the other four, on df = 2:
`ministral3:8b   3    Y       +2.80      ( +0.02, +5.58)  0.0492       -22.17      (-29.02,-15.32)  0.0051    +24.97`.
The conditional interval is 5.56 pp wide around a 2.80 pp estimate and its lower bound is +0.0246,
so it clears zero by less than the increment everything else here is printed at. The unconditional
delta is the robust one (p = 0.005; per-seed −19.05, −23.20, −24.27, all the same sign).

**The §6 headline — gemma3:12b.** `+11.44` conditional (95% CI +3.19, +19.69; p = 0.027) becomes
`+0.16` unconditional (95% CI −13.92, +14.25; p = 0.965). Source line, `fig3_consequence.py`
PLOTTED VALUES: `gemma3:12b      3    Y      +11.44      ( +3.19,+19.69)  0.0269        +0.16      (-13.92,+14.25)  0.9649    +11.28`.

**This claim is reading-specific and the paper must say so.** Under the EXECUTED reading the same
cell's unconditional Delta is **+27.82 (p = 0.004)**, not +0.16 — see §7 below.

**Conditional-minus-unconditional gap** (the part of the reported gain carried by the conditioning
variable's own distribution moving), `fig3_consequence.py` PLOTTED VALUES, `gap` column:
+1.39 (4b), +11.28 (12b), +3.69 (e2b), +8.89 (e4b), +24.97 (ministral3:8b). ministral3:8b is now
the largest of the five, displacing gemma3:12b’s +11.28; it was +23.53 on the 2-seed basis.

**HIGH-appraisal prevalence per irrigation cell** — "the denominator that moved", printed under
CONTEXT in `fig3_consequence.py` and in §A of `table1_cells.py`:

| model | HIGH gov | HIGH nov | Δ | p |
|---|---|---|---|---|
| gemma3:4b | 37.08 | 82.80 | +45.73 | 0.000 |
| gemma3:12b | 5.49 | 26.76 | +21.27 | 0.030 |
| gemma4:e2b | 18.26 | 65.79 | +47.53 | 0.000 |
| gemma4:e4b | 45.27 | 88.65 | +43.38 | 0.000 |
| ministral3:8b | 13.56 | 44.69 | +31.13 | 0.000 |

---

## 4. Year 1 — the controlled comparison, paper §5, Figure 2a

Anchor, 5 seeds, paired t, df = 4. Worlds provably identical at year 1 — **and that premise is now
produced inside this folder**, by `e0_year1_exogeneity.py`, not cited from outside it.

### 4a. The premise itself — exact equality of the two arms' year-1 world

`e0_year1_exogeneity.py` takes its run directories from `_data.py`, joins the arms on
(seed, agent_id, year) over the paired seeds, and tests **exact string equality on the raw csv cell**.
No tolerance is applied. It exits 1 if any pre-decision column is not 1.0 at year 1.

| claim | value | where in stdout (`e0_year1_exogeneity.py`) |
|---|---|---|
| year-1 exact-equality rate, every pre-decision column, every irrigation cell | **1.0 (100.0000%)** | per-cell tables, e.g. `  drought_index                env-state           390/390     100.0000` |
| first year at which any pre-decision column disagrees | **2**, in all five cells | `  -> FIRST year at which ANY pre-decision column disagrees: 2` |
| matched pairs compared | **65,520** across 5 cells, of which **1,560** at year 1 | `compared 65,520 matched (seed, agent_id, year) pairs across 5 irrigation cells; 1,560 of them at year 1` |
| year-1 pairs, anchor cell alone | **390** (5 seeds × 78 agents) | `paired seeds [42, 43, 44, 45, 46]   matched (seed, agent_id, year) pairs compared: 16,380   of which year 1: 390` |
| pre-decision columns gating the check | **9** — `cluster`, `basin`, `water_right`, `has_efficient_system`, `drought_index`, `shortage_tier`, `curtailment_ratio`, `lake_mead_level`, `mead_storage_maf` | header line `Pre-decision columns (gate the exit code), 9:` |
| which columns first diverge at year 2 | `drought_index`, `lake_mead_level`, `mead_storage_maf` in every cell; `shortage_tier` / `curtailment_ratio` at year 2 (gemma3:4b, gemma4:e2b, gemma4:e4b), 13 (gemma3:12b), 5 (ministral3:8b) | `first year != ` column of each per-cell table |
| static attributes never diverge, all 42 years | `cluster`, `basin`, `water_right`, `has_efficient_system` | `first year != ` column reads `none` |
| verdict | `YEAR-1 EXOGENEITY: HOLDS` | final block |

**Correction — two columns are post-decision and must not be quoted as world-identity evidence.**
`utilisation_pct` and `below_minimum_utilisation` are *not* pre-decision: `simulation_log.csv` is
written in `post_year` and `utilisation_pct` is `request / water_right`, where `request` is the demand
the year's skill has just set (`examples/irrigation_abm/run_experiment.py:307, 344-347`). Their year-1
equality rates are correspondingly **not** 1.0 (anchor: 46/390 = 11.79% and 388/390 = 99.49%). The
script prints them, excluded from its gate, with a control that settles the classification on the
data rather than on the code comment.

| claim | value | where in stdout (`e0_year1_exogeneity.py`, CONTROL) |
|---|---|---|
| year-1 pairs where both arms applied the SAME skill **and** the same `magnitude_pct` | 43 / 39 / 37 / 8 / 27 (gemma3:4b, gemma3:12b, gemma4:e2b, gemma4:e4b, ministral3:8b) | `same-change pairs` column |
| both post-decision columns equal on every one of those pairs | **43/43, 39/39, 37/37, 8/8, 27/27** | `equal` column |
| `maintain_demand`-only subset (no demand moved at all), both columns equal | **32/32, 22/22, 27/27, 8/8, 13/13** | `neutral pairs` / `equal` columns |
| year-1 disagreements left over after the same-change pairs are removed | **0** — every disagreement sits on a pair whose demand change differed | `unequal, change differed` column reconciles with the per-cell year-1 counts |

Same *skill* alone is not sufficient: `magnitude_pct` is drawn when the skill executes, so both arms
can choose `increase_small` and still move demand by different amounts. That is post-decision
variation too, and the control separates the two cases rather than lumping them.

### 4b. The year-1 appraisal comparison itself

| claim | value | script | where in stdout |
|---|---|---|---|
| HIGH-appraisal prevalence Delta | **+3.33** (95% CI −3.75, +10.42; p = 0.261) — **null** | `fig2_mechanism.py` | PANEL A · `    1   34.10   37.44    +3.33 (  -3.75, +10.42)   0.261  <== YEAR 1, worlds identical` |
| " (independent recomputation) | +3.33 (−3.75, +10.42), p = 0.261 | `_data.py` | §7 · `HIGH prevalence    mean   +3.33  95% CI (  -3.75,  +10.42)  t= +1.31 df=4  p=0.261` |
| conditional-rate Delta | **−1.15** (95% CI −7.00, +4.71; p = 0.616) — **null** | `_data.py` | §7 · `conditional        mean   -1.15  95% CI (  -7.00,   +4.71)  t= -0.54 df=4  p=0.616` |
| unconditional-rate Delta | **+1.28** (95% CI −0.31, +2.87; p = 0.089) — **null** | `_data.py` | §7 · `unconditional      mean   +1.28  95% CI (  -0.31,   +2.87)  t= +2.24 df=4  p=0.089` |
| year-1 arm levels | gov 34.10%, noval 37.44% | `fig2_mechanism.py` | PANEL A year-1 line above |
| the shift appears from year 2 | +27.18 (95% CI +21.97, +32.39; p<0.001) | `fig2_mechanism.py` | PANEL A · `    2   64.62   91.79   +27.18 ( +21.97, +32.39)   0.000` |
| all 42 per-year Deltas | 42 rows | `fig2_mechanism.py` | PANEL A table; also `figures/fig2_mechanism.csv` |
| **year 4, significantly the OTHER way** | **−18.46 pp (p = 0.004)** | `fig2_mechanism.py` | PANEL A row `4`; `figures/fig2_mechanism.csv` · `A,delta_high_appraisal_prevalence,4,-18.4615,-27.0783,-9.8448,...,p=0.0040 df=4`; annotated on the figure |
| **year 7, significantly the OTHER way** | **−6.41 pp (p = 0.001)** | `fig2_mechanism.py` | PANEL A row `7`; `figures/fig2_mechanism.csv` · `A,delta_high_appraisal_prevalence,7,-6.4103,-8.3599,-4.4606,...,p=0.0008 df=4` — the figure and the manuscript both print `p = 0.001` at 3 dp; annotated on the figure |
| sign split over years 2–11 / 12–42 | 4 sig +, 2 sig −, 3 n.s., 1 zero-variance / 29 sig +, 0 sig −, 2 n.s. | `fig2_mechanism.py` | figure footer text, computed by `classify_years()` |

**These two negative years must not stay figure-only.** They were drawn and annotated but unremarked
in the prose until 2026-08-02, when §5 was given a sentence naming both. A significant reversal
larger in magnitude than any residual in Table 2, visible on the figure and absent from the text, is
the kind of omission a reviewer reads as concealment.
| CI machinery validated | `t_ppf_two_sided(0.95, 4) = 2.776445` vs textbook 2.776445 | `_data.py` | §7 · `t_ppf_two_sided(0.95, 4) = 2.776445  (textbook 2.776445)` |

**Year-1 retry pressure — a correction the paper must adopt.** DECISION.md §4 says "68–88% of
governed year-1 decisions exhausting their retries". `fig2_mechanism.py` shows that number is the
**retried** share (`retry_count > 0`), reported as the range of per-cell means, **not** the exhausted
share.

| claim | value | where in stdout (`fig2_mechanism.py`, YEAR-1 RETRY PRESSURE) |
|---|---|---|
| anchor, retried (`retry_count > 0`) | 79.5–84.6%, **mean 82.1%** | `anchor, retried (retry_count > 0), per seed: ['80.8', '82.1', '83.3', '79.5', '84.6']  -> 79.5-84.6%, mean 82.1%` |
| anchor, **exhausted** (`retry_count == 3`) | 69.2–74.4%, **mean 70.5%** | `anchor, EXHAUSTED the budget (retry_count == 3), per seed: ['69.2', '69.2', '74.4', '70.5', '69.2']  -> 69.2-74.4%, mean 70.5%` |
| the "68–88" range | **67.95 – 87.95%**, and it is *retried*, not exhausted | `       gemma3:12b      67.95%` … `       gemma4:e4b      87.95%` |

**Both rates are over the GOVERNED arm only.** `year1_retry_pressure()` iterates
`D.irrigation_run("gov", ...)`; the no-validator arm has no retry loop. Write **"82.1% of governed
year-1 decisions were rejected and re-prompted at least once, and 70.5% of governed year-1 decisions
ran to the end of the retry budget"**. Do **not** write "68–88% exhausted", do **not** write "of all
year-1 decisions" (roughly halves the true rate by pulling in the untreated arm), and do **not** write
"71% **of them**" (reads as 71% of the 82.1%, which would be 86%). The earlier `PLAN.md` C4(a)
instruction to write "of all year-1 decisions" is superseded by this row.

All-years comparison denominator, same governed anchor arm: **63.8% retried** (§5a), so year 1 runs
well above the run mean rather than at an unmeasured maximum — the paper must not call it "the
highest of the run", which no row here supports.

---

## 5. Never-retried stratum — paper §5, Figure 2c

`retry_count == 0`: decisions the governance loop never spoke to. Delta in HIGH-appraisal prevalence.

| cell | Δ all decisions | Δ never-retried | difference | larger? | where in stdout (`fig2_mechanism.py` PANEL C) |
|---|---|---|---|---|---|
| gemma3:4b | +45.73 | **+53.46** | +7.74 | yes | `  gemma3:4b       5    37.08    82.80   +45.73    23.96    77.43   +53.46    +7.74` |
| gemma3:12b | +21.27 | **+24.31** | +3.05 | yes | `  gemma3:12b      3     5.49    26.76   +21.27     2.69    27.01   +24.31    +3.05` |
| gemma4:e2b | +47.53 | **+50.93** | +3.40 | yes | `  gemma4:e2b      5    18.26    65.79   +47.53    13.62    64.54   +50.93    +3.40` |
| gemma4:e4b | +43.38 | **+63.05** | +19.68 | yes | `  gemma4:e4b      5    45.27    88.65   +43.38    25.77    88.83   +63.05   +19.68` |
| ministral3:8b | +31.13 | **+34.09** | +2.97 | yes | `  ministral3:8b   3    13.56    44.69   +31.13    10.82    44.91   +34.09    +2.97` |
| **pooled** | **+40.02** ⚠ | **+48.21** | +8.20 | — | `  pooled         21    26.68    66.69   +40.02    17.01    65.23   +48.21    +8.20` |

**5 of 5 cells larger** — `fig2_mechanism.py` CROSS-CHECK · `OK  never-retried Delta LARGER in k of 5 cells                got        +5  brief        +5`.

✅ **RESOLVED 2026-08-01: +40.45 computed is correct; the +40.40 in the prose was a 1 dp rounding of it, and the prose was corrected.**
See §12.

**Stratum asymmetry, which the paper must disclose.** The never-retried stratum covers a far larger
share of the no-validator arm than of the governed arm — anchor `36.2% / 64.6%`, and up to
`13.5% / 93.5%` on gemma4:e4b (`fig2_mechanism.py` PANEL C, `NR share gov/nov` column). The two
strata are not the same population; that asymmetry is itself a consequence of enforcement.

### 5a. The retried stratum, and why its first attempt is not in the corpus — paper §5 and §8

The complement of §5, and the paper's acceptance-selection limitation. Four inspections that were
previously done **by hand, on seed 42 only, and never scripted** (they were four rows of §11) are now
recomputed over **all five anchor seeds** by `e1_first_attempt_limits.py`, which takes its run
directories from `_data.py` and exits 1 if any of them stops holding. Checks 1–3 are the governed
arm; check 4 sweeps **both** arms. The script computes no rate, no Delta and no test statistic.

**Retry structure**, governed anchor arm, `e1_first_attempt_limits.py` section 1. Counts, not rates:

| claim | value | where in stdout |
|---|---|---|
| decisions per run | **3,276**, every seed | per-seed table, `rows` column |
| retry budget, read from the data | **3** (`max retry_count`) | `retry budget observed (max retry_count) : [3]` |
| retried at least once (`retry_count > 0`), all years | per seed 62.0 / 60.8 / 63.4 / 62.5 / 70.3%, **pooled 10,450 / 16,380 = 63.8%** | `pooled  16,380    10,450    63.8` |
| exhausted the budget (`retry_count == 3`), all years | **pooled 7,279 / 16,380 = 44.4%** | same pooled line, `exhausted` column |
| **approved after at least one retry** — the selected stratum | 763 / 800 / 859 / 814 / 745 per seed; **pooled 3,981 / 16,380 = 24.3%** | `approved-after-retry stratum, pooled    : 3,981 / 16,380 = 24.3%` |
| rejected after retry | pooled **6,469 / 16,380 = 39.5%** | pooled line, `rej.after` column |
| never retried | pooled **5,930 / 16,380 = 36.2%** | pooled line, `never` column |

Seed 42 alone reproduces DECISION.md §5 exactly: **3,276 rows / 2,030 retried / 763 approved after
retry (23.3%) / 1,267 ending REJECTED** — VERIFICATION block, first five `OK` lines.

**These are ALL-YEARS numbers and must be labelled as such.** The paper's year-1 retry figures
(82.1% retried, 70.5% exhausted) are a different stratum and come from `fig2_mechanism.py` (§4).

**The first attempt is not recoverable from this corpus** — three separate attempts to find it, all
negative, all five seeds:

| claim | value | where in stdout |
|---|---|---|
| generations per stored `raw_output`, audit csv, retried rows | **exactly 1** on all **10,450** retried rows; no marker ever reaches 2 | section 2(a) · `"reasoning"                      n=10,450  max=1  distribution {1: 10450}` |
| …same, trace JSONL `skill_proposal.raw_output` | **max 1**, 10,345 of 10,450 (the 105 exceptions are retry-exhausted fallback records with no proposal object) | section 2(b) · `record.skill_proposal.raw_output  (the full generation), 10,450 retried records:` |
| the record's two `raw_output` fields are ONE generation, not two | **32,652 / 32,652** top-level copies are a literal prefix of the full text, cut at 500 chars and closed with `...[truncated]` | VERIFICATION · `the two raw_output fields are one generation, not two (32,652/32,652 top-level copies are a literal prefix of the full text)` |
| `proposed_skill == final_skill` on retried rows | 2,007/2,030 (seed 42) … **pooled 10,345 / 10,450 = 99.00%** | section 3 pooled line · `pooled    10,450            10,345    99.00      105              105` |
| …and every disagreement is a blank proposal, not a different action | **105 rows, all** `proposed=<blank> final=maintain_demand status=REJECTED_FALLBACK`; disagreements with a proposal actually recorded: **0** | section 3 · `Disagreements where a proposal was actually recorded: 0` |
| **one trace record per (agent_id, year)** — the load-bearing claim | **3,276 records / 3,276 distinct keys / max 1 per key, in all 10 runs** (5 seeds × 2 arms), 0 duplicate keys, 0 blank lines | section 4 table, `records` / `distinct keys` / `max per key` columns |
| no attempt-history field in the trace schema | `attempt-history fields present: NONE` (29 fields inventoried) | section 4 · `attempt-history fields present: NONE` |
| trace `retry_count` agrees with the audit csv | every governed seed | VERIFICATION · `trace retry_count agrees with the audit csv on every governed seed` |
| verdict | `e1: VERIFIED -- all four inspections reproduce, on all five anchor seeds.` | final block |

**Scope, and the paper must not blur it.** This says the first attempt is unrecoverable **from the
shipped corpus**. The code at HEAD *does* persist attempt-0 appraisal labels behind a default-OFF
audit option; these runs predate it and did not have it on. The script prints that distinction itself
(section 4, SCOPE NOTE).

**Provenance observation printed by the same script, not a failure.** The trace fields `model` and
`decision_source` are on every record of seeds 42–44 in **both** arms and on **no** record of seeds
45–46 in either arm. The identity fields the check depends on (`agent_id`, `year`, `retry_count`) are
present everywhere, so nothing above is affected — but a field that splits the runs is a
writer-version marker, and it belongs in the paper's provenance paragraph alongside the flood
mixed-vintage defects in §8. Source: section 4 · `PROVENANCE OBSERVATION (does not bear on the claim above, does not fail):`.

---

## 6. Reservoir trajectory — paper §5, Figure 2b

Lake Mead elevation, **levels in feet per arm, not a Delta**. Anchor, mean of 5 seeds.

| claim | value | where in stdout (`fig2_mechanism.py` PANEL B) |
|---|---|---|
| year-1 gap | **+0.0000 ft** — the two arms start on the identical value | `  year-1 gap        +0.0000 ft   (the two arms start on the identical value)` |
| final-year gap | **+106.57 ft** | `  final-year gap    +106.57 ft` |
| 42-year mean gap | **+102.25 ft** | `  42-year mean gap  +102.25 ft` |
| no-validator arm first reaches the 895 ft floor | **year 17–18, in all 5 seeds** | per-seed table, `noval first yr` column: `17,17,18,18,17` |
| years spent on the floor | **6–12 of 42** | `noval yrs on floor` column: `12,6,6,7,8` |
| ends the run on the floor | **5 / 5 seeds** | `noval ends on it` column, all `True` |
| governed arm reaches the floor | **0 / 5 seeds** | `    governed arm reaches the floor in 0/5 seeds` |
| governed minimum elevation | **964.01 ft** (worst seed) | `gov min ft` column: `997.62, 994.36, 996.97, 996.03, 964.01` |

**Wording caution printed by the script itself:** the no-validator arm does *not* stay on the floor
once it reaches it — it recovers and returns. "Reaches 895 ft and stays there" is **false**.

---

## 7. Both action readings — paper §6 and §8

EXECUTED = `maintain_demand` substituted on rejected rows. Source: `table1_cells.py` §B, the
`EXECUTED` line under each model; also `fig3_consequence.py` CONTEXT.

| model | cond Δ LAST-PROPOSED | cond Δ EXECUTED | unc Δ LAST-PROPOSED | unc Δ EXECUTED |
|---|---|---|---|---|
| gemma3:4b | +23.02 | +25.90 | +21.62 | +29.90 |
| gemma3:12b | +11.44 | +12.96 | **+0.16 (p=0.965)** | **+27.82 (p=0.004)** |
| gemma4:e2b | +18.94 | +27.96 | +15.25 | +28.84 |
| gemma4:e4b | +17.41 | +39.95 | +8.52 | +36.57 |
| ministral3:8b | +2.80 | +4.20 | −22.17 | +20.26 |

Anchor governed conditional rate under the two readings: **36.05 → 0.86**
(`table1_cells.py` §B · `gemma3:4b      EXECUTED       |     0.86    26.77   25.90`).

---

## 8. Flood — portability demonstration only, paper §2

**Flood is not a control and must never be called one.** No action→environment feedback exists in it
(`run_flood.py:285-291`). Every flood number below is descriptive and supports no within-flood
identification claim.

| claim | value | script | where in stdout |
|---|---|---|---|
| enforcement pressure, governed arm | **0.00 – 1.07%** across 9 models | `table1_cells.py` | §A, `press.gov` column, flood rows |
| enforcement pressure, no-validator arm | **exactly 0.00% in every flood cell** | `table1_cells.py` | §A, `press.nov` column, all nine flood rows read `0.00` |
| three cells have zero rejections in **both** arms | gemma3:27b, ministral3:14b, gemma4:e2b | `table1_cells.py` | §A, rows where `press.gov` and `press.nov` are both `0.00` |
| flood HIGH-prevalence Deltas | **−3.66 to +6.24**, mostly null | `table1_cells.py` | §A, `Delta` column, flood rows |
| …only one reaches p<0.05 | gemma4:26b, **+2.92 (95% CI +0.71, +5.12; p = 0.021)** | `table1_cells.py` | §A · `flood      gemma4:26b        5      5    Y     5 |      0.12      0.00   -0.12 |    17.44    20.36    2.92   (  +0.71,  +5.12)  0.021` |
| …sign split across the nine flood Deltas | **5 of 9 positive, 4 of 9 negative** | `table1_cells.py` | §A, `Delta` column, flood rows: negative on gemma3:4b (−1.16), gemma3:12b (−1.63), ministral3:3b (−0.15), ministral3:8b (−3.66); positive on gemma3:27b (+1.22), ministral3:14b (+0.47), gemma4:e2b (+0.97), gemma4:e4b (+6.24), gemma4:26b (+2.92) |
| flood audit-CSV coverage of the 1,000 design-expected decisions | **70.5 – 100.0%** | `_data.py` | §3 coverage table, `70.5-76.4` (worst, ministral3:3b) through `100.0-100.0` (gemma4:26b) |

**Irrigation enforcement-pressure range on the PER-SEED-MEAN basis (not the pooled-count basis of §1).**
§1's `28.1 – 62.6%` is a pooled-count `rej%` from `fig1_rule_layers.py`. Table 1 / §4 of the manuscript
instead reports Table 1's own basis — mean-of-per-seed-rates from `table1_cells.py` §A, `press.gov`
column — which is a close but **not identical** number and must not be quoted under the §1 locator.

| claim | value | script | where in stdout |
|---|---|---|---|
| governed enforcement-pressure range, irrigation, PER-SEED-MEAN basis | **28.09 – 62.63%** | `table1_cells.py` | §A, `press.gov` column, irrigation rows: min `gemma4:e2b … 28.09`, max `ministral3:8b … 62.63` (62.19 on the 2-seed basis, before seed 44 joined) |

**Two provenance defects, both printed, both must appear in §8 of the paper:**

1. **Flood manifest seeds disagree across arms in 6 of 9 models.** Governed `Run_2`/`Run_3` record
   seeds 4202/4203 where the no-validator arm records 43/44.
   `_data.py` §3 · `gemma3:4b      gov=[42, 4202, 4203, 45, 46] noval=[42, 43, 44, 45, 46]   <== MANIFEST SEEDS DISAGREE ACROSS ARMS`.
   Pairing is by **run index**, this project's published convention;
   `_data.py` prints `-> flood_runs() keys on the RUN INDEX, not the manifest seed.`
2. **The flood audit CSV covers 70.5–100.0% of the nominal 1,000 (100 agents × 10 years)
   design-expected decisions. This is not damage — it is not F1 silent-drop.** Relocation is a
   designed absorbing state that ends an agent's participation in the simulation; an agent that
   relocates in year *y* generates no further rows for years after *y*. Verified exactly on 5/5
   `ministral3:3b` `Group_C` runs (`examples/single_agent/results/JOH_FINAL/ministral3_3b/Group_C/`):
   audit rows = 1,000 − (relocated-agent-years-lost), exactly — Run_1 764/236, Run_2 705/295,
   Run_3 714/286, Run_4 735/265, Run_5 756/244. Every flood rate is a per-run rate over rows that
   exist; none is pooled over a 1,000 denominator.
3. **`JOH_FINAL/gemma3_4b/Group_C/Run_1` ran a different prompt from the other four runs in its
   cell.** Its `raw/household_traces.jsonl` input omits the "MULTI-ACTION OPTION" block and the
   `magnitude_pct` / `secondary_decision` / `secondary_magnitude_pct` output fields that Run_2–5 all
   carry (prompt length 2,480 chars vs 2,930–2,972 chars for its siblings); `config_snapshot.yaml`
   confirms the same gap — Run_1 lacks the `magnitude_pct`/`secondary_decision`/
   `secondary_magnitude_pct` construct-schema entries and the `multi_skill` section entirely, while
   Run_2–5 all carry them. Governed `gemma3:4b`/flood therefore mixes a single-action-prompt seed
   with four multi-action-prompt seeds. The seed is **not dropped**; it is disclosed here instead.
   This affects **flood only** — no other model/arm/testbed cell has a config or prompt mismatch
   across its own runs.

---

## 9. Data-integrity numbers the red-team will want

| claim | value | script | where in stdout |
|---|---|---|---|
| `sim.yearly_decision` == `audit.final_skill` | **0 mismatches / 16,380 rows, each arm** | `_data.py` | §4 · `with-validators  joined rows  16380   sim.yearly_decision != audit.final_skill : 0` |
| contamination guards all refuse | **15 / 15** (`Group_A`, `*_bak*`, `_QUARANTINE_*`, `_logs`, transposed `DELTA`) | `_data.py` | closing line `SELF-TEST: CLEAN` |
| every rule name is covered by the taxonomy | exhaustive, no unclassified rule | `fig1_rule_layers.py` | VERIFICATION · `Every rule name seen in failed_rules is covered by the rule taxonomy, so` |
| appraisal column agreement, sim vs audit | 32,652 / 32,760 anchor rows; the 108 exceptions are unparsed labels, HIGH under neither encoding | `fig2_mechanism.py` | SUGGESTED CAPTION, sentence beginning `Panel c is computed on the audit records` |
| unparsed appraisal labels (`"N/A"`) | 0.64% governed, 0.02% no-validator (anchor) — in the denominator, not HIGH | `_data.py` | §2 · `gemma3:4b      with-validators  42,43,44,45,46      5      3276       0.64   True` and the `no-validator` line under it, `unparsed%` column |
| decisions per run | **3,276** = 78 agents × 42 years, every irrigation run, both arms | `_data.py` | §2, `rows/run` column — identical on all ten rows |
| anchor decisions per arm | 5 × 3,276 = **16,380** | `fig1_rule_layers.py` | PANEL A, `total` column |

---

## 10. Descriptive-only, printed but explicitly NOT to be plotted or claimed

`fig2_mechanism.py`, section `DESCRIPTIVE ONLY -- NOT DRAWN ON THE FIGURE`:

| quantity | value | line |
|---|---|---|
| Spearman(per-year Delta, reservoir gap) | rho = **+0.552** | `  Spearman(per-year Delta, reservoir gap)          rho = +0.552` |
| Spearman(per-year Delta, governed rejection %) | rho = **−0.170** | `  Spearman(per-year Delta, governed rejection %)   rho = -0.170` |

The script prints its own prohibition: the 42 years are strongly autocorrelated, these are not
inferential, and DECISION.md §9 killed the pressure-vs-shift scatter — **do not reintroduce it as a
correlation claim.**

---

> ## ⚠ LOCATOR COLUMN IS STALE AS OF 2026-08-01
>
> The C1–C4 figure and label edits, and the `_data.py` rule-kind relabel, changed several printed
> lines verbatim. The **values** in this file are current and were re-verified by a full clean
> `run_all.py` pass. The **stdout locators** — the backticked snippets naming the
> line a value appears on — were written against the earlier output and a detector found 29 that no
> longer match live output; most are false positives (file paths, prose), but the column as a whole
> can no longer be trusted as a pointer.
>
> **Locators are regenerated on the 4 Aug number-freeze day**, which is already in `PLAN.md`'s
> schedule for exactly this purpose. Until then, trust the values, re-grep for the lines.
> Three locators that quoted the retracted "theory … 100%" formulation were neutralised on
> 2026-08-01 rather than left to be copied.

## 11. ⚠ Claims NO script in this folder produces

Any of these in the manuscript is currently unsourced by this pipeline. Either cite the external
artefact explicitly, or drop the number.

**Gate 0 disposition, set 2026-08-01.** `PLAN.md` section 8 requires that every surviving row here
"carries no number". Both numeric rows below are hereby marked **DROP — DO NOT WRITE**: the
1.84-shortage-tier figure and the −0.514 Pearson must not appear in the manuscript in any form. The
1.84 has no producing script, and the −0.514 belongs to the figure that was killed for implying a
relationship that is not identified. The elevation contrast (102 ft) IS produced and may be used in
its place. The remaining two rows carry no number and are prose-only by construction.

| claim (source) | status |
|---|---|
| "governed arm ends 1.84 shortage tiers lower" (DECISION.md §4) | **Not produced.** No script reads a shortage-tier column. The 102 ft / 106.6 ft elevation numbers ARE produced (§6). |
| "within-irrigation Pearson −0.514 between enforcement pressure and shift" (DECISION.md §9, the killed figure) | **Not produced.** `fig2_mechanism.py` prints a *Spearman over years* (−0.170), which is a different quantity on a different unit. Do not substitute one for the other. |
| "the precondition is attached to increase_large / increase_small and no other skill" | Read from `skill_registry.yaml` and asserted in `fig1_rule_layers.py`'s PANEL C prose, but it is a config fact, not a computed statistic. |
| prior-art claims: AgentSpec, SAVeR (arXiv:2604.08401), Gao et al. (arXiv:2607.24604), Park (arXiv:2603.21435), Paul et al. 2024 (DOI 10.18653/v1/2024.findings-emnlp.882) | **Not data claims.** Re-verify every one at the citation-check stage; the double-blind sweep must also third-person the group's own WRR 2026 and Nature Water predecessors. |

**Closed since this list was written — do not re-add:**

| former row | now produced by |
|---|---|
| "year-1 exact-equality 1.0, first divergence year 2" | `e0_year1_exogeneity.py` → **§4a** |
| "≈23% of governed decisions are retried-and-approved: 763 of 3,276 on seed 42; 2,030 retried; 1,267 ending REJECTED" | `e1_first_attempt_limits.py` → **§5a**, over all 5 seeds |
| "`raw_output` holds a single generation on a `retry_count = 3` row" | `e1_first_attempt_limits.py` → **§5a**, counted over all 10,450 retried rows rather than one row (the 708-char length was one row of one seed and should not be quoted; the reproducible claim is *one generation, max 1 by every marker*) |
| "`proposed_skill == final_skill` on 2,007 of 2,030 retried rows" | `e1_first_attempt_limits.py` → **§5a**, all 5 seeds (pooled 10,345 / 10,450) |
| "the traces JSONL holds 3,276 records for 3,276 distinct (agent, year) pairs, max one each" | `e1_first_attempt_limits.py` → **§5a**, verified on all 5 seeds in **both** arms (10 runs), not one |

---

## 12. ⚠ The one disagreement with the brief — do not tune it away

> **RESOLVED 2026-08-01.** The computed +40.45 was correct; `DECISION.md` was written to 1 dp against a 2 dp tolerance. The prose was corrected, never the script. This banner has carried two different pass counts ("9/9", then "11/11") as the pipeline grew; **neither is recorded any more** — `run_all.py` prints its own.
>
> **Superseded value, 2026-08-03.** The pooled all-decisions Delta is now **+40.02** and the
> never-retried counterpart **+48.21**, because the pool grew from 20 paired (cell, seed) units to
> 21 when ministral3:8b’s third pair landed. The adjudication above — which basis is the right one
> — is untouched by that; only the arithmetic moved.

The block below is the failure **as it stood before that resolution**, kept for the audit trail.
`fig2_mechanism.py` now exits **0** and `run_all.py` propagates nothing:

```
  !!  all-decisions Delta, pooled                              got    +40.45  brief    +40.40  diff  +0.055   <== DISAGREES WITH THE BRIEF
```

| | |
|---|---|
| **quantity** | pooled Delta in HIGH-appraisal prevalence over **all** decisions, 5 irrigation cells |
| **computed** | **+40.45** (pooled gov 27.52, noval 67.98, n = 20 paired seeds) |
| **brief states** | +40.40 |
| **magnitude** | 0.055 pp |
| **every neighbouring value** | agrees to <0.005 pp, including the never-retried counterpart (+49.09) that this number is contrasted against |

**Assessment.** Small, and almost certainly a pooling-basis difference — a mean of per-cell deltas
weights the 3-seed and 2-seed cells differently from a mean over all 20 paired seeds, and the brief
does not state which it used. **It has not been chased down, and nothing was changed to make it go
away.** The contrast the paper draws (never-retried **larger** than all-decisions, 5/5 cells) is
unaffected at any plausible resolution of it.

**If the paper prints the pooled pair, print `+49.1 vs +40.5` from this pipeline, not `+40.4`, and
say which pooling basis is used.** Alternatively print only the per-cell values in §5, all of which
reproduce exactly.

---

## 12a. Reproduce any single row

*(This section was numbered "13" and collided with the World-fixed decomposition section below,
which is also numbered 13. Renumbered 12a so both can be referred to.)*

```
python SUBMISSION_2026/TAE/evidence/_data.py             # self-test + §1–§9 integrity rows
python SUBMISSION_2026/TAE/evidence/e1_first_attempt_limits.py   # §5a
python SUBMISSION_2026/TAE/evidence/table1_cells.py      # §1–§3, §7, §8
python SUBMISSION_2026/TAE/evidence/fig1_rule_layers.py  # §1
python SUBMISSION_2026/TAE/evidence/fig2_mechanism.py    # §4, §5, §6, §10, §12
python SUBMISSION_2026/TAE/evidence/fig3_consequence.py  # §2, §3, §7
python SUBMISSION_2026/TAE/evidence/_verify_pipeline.py  # §2, §3 re-derived independently
```

The `(exits 1)` note that used to sit against `fig2_mechanism.py` is **removed**: that failure was
resolved on 2026-08-01 (§12), and the same fact was already recorded as resolved twice elsewhere in
this file. This list is also not the full pipeline — `run_all.py` is authoritative on what runs.

Machine-readable copies of every plotted value: `figures/fig{0,1,2,3}_*.csv` (**four**, not three —
`fig0_problem_schematic.csv` was added with the schematic) and `evidence/table1_cells.csv`.

## 13. World-fixed decomposition (`e4_world_fixed_decomposition.py`, added 2026-08-01)

The mechanism, by direct decomposition instead of inference. Replaces the section 7 recommendation
that was drafted as advice and is now demonstrated.

| claim | value | script | where |
|---|---|---|---|
| raw appraisal-prevalence shift, anchor | **+45.73 pp** (gov 37.08% vs noval 82.80%) | `e4` | PART 1, `SELF-REPORT WSA in {H,VH}` |
| **world antecedents shift TOO — the "condition on world state" repair is FALSE** | shortage_tier ≥ 2 shifts **+64.29 pp**, ≥ 1 and curtailment > 0 shift +55.71, drought ≥ 0.5 shifts +25.71 | `e4` | PART 1 |
| residual after holding the world fixed, coarse (100% coverage) | **−2.53 pp** | `e4` | PART 2, `shortage tier` |
| residual, finest (43.4% coverage) | **+0.21 pp** | `e4` | PART 2, last row |
| largest residual at any resolution | **4.47 pp**, against a raw shift of 45.73 | `e4` | PART 2 CLAIM line |
| governed arm share of decisions in tier 0 (no shortage) | **64.8%** (10,608 / 16,380) | `e4` | PART 3 |
| no-validator arm share in tier 3 (severe shortage) | **76.7%** (12,558 / 16,380) | `e4` | PART 3 |

**Full stratification ladder (Table 2 of the manuscript).** The two rows above are the coarsest and
finest rungs only. All five rungs the manuscript's Table 2 prints, verbatim from `e4` PART 2. The
`strata`, `coverage` and `residual` columns are unchanged by the 2026-08-02 upgrade; the per-arm cell
counts, the two alternative weightings and the intervals are new and are tabled underneath.

Locators below quote PART **2b**, which carries the strata label and the residual. `strata` and
`coverage` now print in PART **2a** (`strata` and `cov|gov` columns) and are locatored in §13a.

| world held fixed at | strata | coverage | residual | where in stdout (`e4_world_fixed_decomposition.py` PART 2b) |
|---|---:|---:|---:|---|
| shortage tier | 4 | 100.0% | −2.53 pp | `shortage tier                               -2.53    -2.49     -2.58        [-5.7 .. +4.1]           -3.12  [  -5.56,  -0.68]  5/5` |
| tier + curtailment | 4 | 100.0% | −2.53 pp | `tier + curtailment                          -2.53    -2.49     -2.58` |
| tier + Mead elevation (25 ft) | 7 | 81.9% | −4.47 pp | `tier + Mead elevation (25 ft)               -4.47    -4.17     -4.83` |
| tier + Mead (10 ft) + drought decile | 19 | 50.5% | +0.57 pp | `tier + Mead (10 ft) + drought decile        +0.57    +1.02     +0.02` |
| tier + Mead + drought + agent cluster | 19 | 43.4% | +0.21 pp | `tier + Mead + drought + agent cluster       +0.21    +0.86     -0.57` |

The row the manuscript's prose calls "coarse" is `shortage tier`; the row it calls "finest" is
`tier + Mead + drought + agent cluster`. `tier + Mead elevation (25 ft)` (−4.47 pp) is where the
**largest residual at any resolution** row above comes from — it is not the coarse or the finest row,
so its own locator is given here rather than implied.

### 13a. What Table 2 carries beside the residual (added 2026-08-02)

A residual quoted against a raw gap that has an interval needs the same furniture the raw gap has.
`e4` PART 2 now prints the per-stratum n, the weighting scheme by name with two alternatives, and a
95% interval on every rung. **No previously published value moved:** the five `strata`, `coverage`
and `residual` figures above are byte-identical to the pre-upgrade run, as are PART 1 and PART 3.

**Per-arm cell counts** — `e4` PART **2a**, one line per rung, `n|gov min/med/max` and
`n|noval min/med/max` columns. `cov|nov` is new alongside the pre-existing `cov|gov`.

| world held fixed at | strata | n per stratum, gov (min/med/max) | n per stratum, noval (min/med/max) | cov gov | cov noval |
|---|---:|---:|---:|---:|---:|
| shortage tier | 4 | 1,482 / 2,145 / 10,608 | 858 / 1,482 / 12,558 | 100.0% | 100.0% |
| tier + curtailment | 4 | 1,482 / 2,145 / 10,608 | 858 / 1,482 / 12,558 | 100.0% | 100.0% |
| tier + Mead elevation (25 ft) | 7 | 78 / 1,482 / 4,602 | 390 / 1,482 / 3,978 | 81.9% | 70.5% |
| tier + Mead (10 ft) + drought decile | 19 | 78 / 390 / 1,170 | 78 / 234 / 1,326 | 50.5% | 42.4% |
| tier + Mead + drought + agent cluster | 19 | 67 / 335 / 1,005 | 67 / 201 / 1,139 | 43.4% | 36.4% |

Locator, first row: `shortage tier                               4     1,482 / 2,145 / 10,608       858 / 1,482 / 12,558   100.0%   100.0%`.
The **min–max across BOTH arms**, which is the range the manuscript's Table 2 prints in one column:
858–12,558 (tier), 78–4,602 (Mead 25 ft), 78–1,326 (drought decile), 67–1,139 (finest).

**Weighting scheme, named.** Every residual is **direct standardisation**: each arm's within-stratum
HIGH-appraisal rate is recombined under one common stratum distribution. The published column
weights by the **pooled** distribution (both arms' rows in the comparable strata). `e4` PART 2b now
prints the same calculation under the **governed arm's own** distribution and the **no-validator
arm's**, so the index-number ambiguity is on the page.

| world held fixed at | pooled weights (published) | governed-arm weights | no-validator weights | largest move from pooled |
|---|---:|---:|---:|---:|
| shortage tier, and tier + curtailment | −2.53 pp | −2.49 pp | −2.58 pp | 0.05 pp |
| tier + Mead elevation (25 ft) | −4.47 pp | −4.17 pp | −4.83 pp | 0.36 pp |
| tier + Mead (10 ft) + drought decile | +0.57 pp | +1.02 pp | +0.02 pp | 0.55 pp |
| tier + Mead + drought + agent cluster | +0.21 pp | +0.86 pp | −0.57 pp | 0.78 pp |

| claim | value | where in stdout (`e4` PART 2b) |
|---|---|---|
| largest residual under **any** of the three standards, any rung | **4.83 pp** (no-validator weights, Mead 25 ft) | `CLAIM world_fixed_residual_any_weighting:` and the line under it |
| largest move caused by switching the standard | **0.78 pp**, on the finest rung | `CLAIM world_fixed_weighting_sensitivity:` and the line under it |

**Intervals.** The seed is the inferential unit. `e4` recomputes each rung's residual **inside each
seed**, standardising that seed on its own pooled stratum distribution over strata clearing
`MIN_CELL_SEED = 8` rows per arm (the per-seed analogue of the pooled 40), then takes a paired t
interval across the five, df = n−1 = 4, t = 2.776.

| world held fixed at | per-seed mean | 95% CI | seeds used | interval's own coverage (gov) |
|---|---:|---:|---:|---:|
| shortage tier, and tier + curtailment | −3.12 pp | (−5.56, −0.68) | 5/5 | 100.0–100.0% |
| tier + Mead elevation (25 ft) | −4.95 pp | (−8.29, −1.62) | 5/5 | 78.6–83.3% |
| tier + Mead (10 ft) + drought decile | −0.53 pp | (−4.32, +3.25) | 5/5 | 26.2–38.1% |
| tier + Mead + drought + agent cluster | −0.87 pp | (−4.94, +3.19) | 5/5 | 23.2–32.7% |

Locators: the rung line itself, e.g. `shortage tier                               -2.53    -2.49     -2.58        [-5.7 .. +4.1]           -3.12  [  -5.56,  -0.68]  5/5`,
and the `-> the interval's own coverage, seed by seed:` line under each rung.

**Three things this table must be read with, all of them printed by the script:**

1. **The per-seed mean is a different estimator from the pooled-weight residual, not a bootstrap of
   it.** Each seed is standardised on its own distribution over its own comparable strata, so the two
   columns agree where the strata are thick (−2.53 vs −3.12) and part where they are thin
   (+0.21 vs −0.87). Print both, or print the pooled residual and say the interval belongs to the
   per-seed recomputation. Do not centre the interval on the pooled figure.
2. **The interval at the fine rungs is computed on less of the corpus than the residual beside it.**
   A stratum can clear 40 pooled rows per arm and still miss 8 within a single seed, so the per-seed
   coverage at the two finest rungs is 23–38%, against the pooled row's 43.4–50.5%.
3. **Three of the five intervals exclude zero, and all three lie BELOW it** — `CLAIM
   world_fixed_residual_ci_signs`. The manuscript's Table 2 merges `shortage tier` with
   `tier + curtailment`, which are the same numbers, so **its** count is two of four; both files are
   describing the same three script rows. A residual below zero means the governed arm reports **more**
   scarcity than the no-validator arm for the same recorded world. That is the opposite direction
   from premise revision, which predicts a large positive residual. The paper must not describe
   every rung as "indistinguishable from zero"; the defensible reading is that **no residual
   approaches the raw shift**, and the two that are significant run the wrong way for the rival
   explanation.

**Verdict gate, widened 2026-08-02.** `e4` still exits 1 unless the largest pooled residual is below
a quarter of the raw shift (4.47 < 11.43). Two conditions were added on the same bar: the largest
residual under **any** of the three weighting schemes must clear it too (4.83 < 11.43), and every
rung must carry an interval (5 of 5). Exit is still 0.

**World antecedents, full table (Table `e4` PART 1), not just the two headline rows above:**

| antecedent | prevalence, governed | prevalence, no-validator | shift | 95% CI | where in stdout (`e4` PART 1) |
|---|---:|---:|---:|---|---|
| self-report, WSA in {H,VH} | 37.08% | 82.80% | **+45.73 pp** | [+40.25, +51.21] | `SELF-REPORT  WSA in {H,VH}        37.08%      82.80%   +45.73   [+40.25, +51.21]` |
| world, shortage_tier ≥ 1 | 35.24% | 90.95% | **+55.71 pp** | [+48.60, +62.83] | `world  shortage_tier >= 1         35.24%      90.95%   +55.71   [+48.60, +62.83]` |
| world, shortage_tier ≥ 2 | 21.43% | 85.71% | **+64.29 pp** | [+64.29, +64.29] | `world  shortage_tier >= 2         21.43%      85.71%   +64.29   [+64.29, +64.29]` |
| world, curtailment_ratio > 0 | 35.24% | 90.95% | **+55.71 pp** | [+48.60, +62.83] | `world  curtailment_ratio > 0      35.24%      90.95%   +55.71   [+48.60, +62.83]` |
| world, drought_index ≥ 0.5 | 4.76% | 30.48% | **+25.71 pp** | [+16.51, +34.92] | `world  drought_index >= 0.5        4.76%      30.48%   +25.71   [+16.51, +34.92]` |

Note the self-report row's shift printed here (+45.73 pp, 95% CI [+40.25, +51.21]) from `e4` differs by
0.01 pp on the CI lower bound from the `table1_cells.py`-sourced §2 row (+45.73 pp, 95% CI +40.24 to
+51.21) — both scripts recompute the same paired t-test independently and round at the second decimal;
this is rounding noise on the CI bound, not a disagreement on the point estimate or on significance.

**Reading.** Within any given world state the two arms report scarcity almost identically. The entire
shift is composition: the two arms occupy different worlds. Premise revision predicts a large residual
of consistent sign; there is none, and at coarse strata it runs slightly the other way.

**Coverage must be quoted with the residual.** A stratum needs ≥40 rows in BOTH arms, so fine strata
cover 43–50% of the corpus. Coarse strata cover 100% and give −2.53 pp. Both are far below +45.73.

**Section 7 wording this supports** (and the wording it kills):
- ❌ "Prefer norms conditioned on world state" — FALSIFIED, world antecedents shift as much or more.
- ✅ "If a norm reads a state the agent reports, log the independent world state alongside it, or the
  conformance number cannot be decomposed into behaviour and composition at all."

### 13b. The same decomposition on the two gemma4 cells (added 2026-08-03)

`e4_world_fixed_decomposition.py` was parameterised on 2026-08-03 so the anchor's decomposition can be
re-run on another model without editing it. The anchor path is unchanged and proven so: with no
argument the script's stdout is byte-identical to before the change (md5 `02536fe93f2798b4ab2b65717cd8d7ef`
on both sides, diff empty).

    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py            # anchor, gemma3:4b
    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py gemma4:e4b
    python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py gemma4:e2b

All three cells use five paired seeds (42–46). Every value below was re-run and confirmed on
2026-08-03 by a second pass that did not share notes with the pass that first produced them.

| rung (coverage) | anchor gemma3:4b | gemma4:e4b | gemma4:e2b |
|---|---|---|---|
| raw appraisal shift | **+45.73** [+40.24, +51.21] | **+43.38** [+41.47, +45.28] | **+47.53** [+39.87, +55.18] |
| HIGH prevalence, gov vs noval | 37.08 / 82.80 | 45.27 / 88.65 | 18.26 / 65.79 |
| shortage tier (100%) | −2.53 | **−3.33** | **+5.18** |
| tier + curtailment (100%) | −2.53 | −3.33 | +5.18 |
| tier + Mead 25 ft | −4.47 (81.9%) | −0.51 (58.1%) | +5.97 (88.1%) |
| tier + Mead 10 ft + drought | +0.57 (50.5%) | +3.87 (35.2%) | **+12.06** (57.6%) |
| finest, + agent cluster | +0.21 (43.4%) | +4.08 (30.7%) | **+13.52** (49.7%) |
| strata, coarse → finest | 4 → 19 | 4 → 15 | 4 → 25 |
| largest residual, any of 3 weightings | 4.83 | 6.76 | **13.97** |
| gate: largest residual < ¼ raw shift | HOLDS | **HOLDS** (4.08 < 10.85) | **FAILS** (13.52 > 11.88) |
| script exit code | 0 | **0** | **1** |

Per-seed 95% intervals, 5 of 5 rungs in both cells:

| rung | gemma4:e4b | gemma4:e2b |
|---|---|---|
| shortage tier | −3.30 (−4.77, −1.84) | +4.25 (−0.53, +9.03) |
| tier + Mead 25 ft | −0.48 (−1.95, +0.98) | +4.49 (−0.81, +9.78) |
| tier + Mead 10 ft + drought | +4.33 (+0.12, +8.55) | +8.78 (+5.09, +12.47) |
| finest | +4.51 (+0.09, +8.92) | +9.88 (+5.54, +14.22) |
| intervals excluding zero | 4 of 5, **2 of them below** | 2 of 5, **0 below** |

Composition (PART 3), same qualitative structure in all three cells — the governed arm parked in
no-shortage, the no-validator arm in severe shortage:

| cell | gov share, tier 0 | noval share, tier 3 |
|---|---|---|
| gemma3:4b | 64.8% | 76.7% |
| gemma4:e4b | **79.0%** | **64.8%** |
| gemma4:e2b | 73.8% | 58.6% |

**What this does and does not license.** The coarse, 100%-coverage claim replicates in all three
cells: a raw shift near +45 pp falls below +6 pp once the recorded world is held fixed. The stronger
form — a residual near zero at *every* resolution the data supports — replicates on gemma4:e4b and
**does not** replicate on gemma4:e2b, where the residual instead *grows* with resolution, is positive
at all five rungs, and leaves +13.52 pp of a +47.53 pp shift unexplained at 49.7% coverage. Three
reasons that is not dismissible as thin-strata noise: e2b's finest rung is better supported than the
anchor's (25 strata at 49.7% coverage against 19 at 43.4%); its per-seed interval excludes zero
decisively at both fine rungs; and its sign is positive everywhere, whereas the negative coarse
residual that the manuscript leans on as evidence *against* premise revision is an anchor-and-e4b
property, not a universal one.

**Nothing from this subsection is in the paper.** §5 and Table 2 remain anchor-only, which is why
their existing wording stays correct as written. Whether to add a cross-model sentence is open — see
`STATUS.md` section 3 item 1b.

## 14. The uniform-random null (`e5_uniform_null.py`, added 2026-08-01)

Closes the last unsourced numbers in the manuscript. Before this script existed, section 6's closing
paragraph carried the 40% null, t = 42.7 and the 95% CI as hand-typed values produced by nothing.

| claim | value | script | where in stdout |
|---|---|---|---|
| action set composition | 5 skills, 2 of them increases | `e5` | `action set read from skill_registry.yaml: 5 skills, 2 of them increases` |
| uniform-random null | **40%** (derived from the registry, not assumed) | `e5` | `CLAIM uniform_null` line |
| no-validator unconditional rate | **62.52%**, sd 1.18 | `e5` | `no-validator ... unconditional rate  62.52%` |
| no-validator t against the null | **+42.658** (df = 4) | `e5` | same line, `t vs 40% =` |
| no-validator 95% CI | **[61.06, 63.99]**, EXCLUDES the null | `e5` | the `95% CI` line under it |
| with-validators unconditional rate | **40.90%**, sd 4.39 | `e5` | `with validators ... unconditional rate  40.90%` |
| with-validators t against the null | **+0.457** (df = 4) | `e5` | same line |
| with-validators 95% CI | **[35.45, 46.35]**, CONTAINS the null | `e5` | the `95% CI` line under it |

**The point of the section, and the reason the null belongs only here.** A null model is
interpretable only when the denominator is fixed independently of the treatment. The unconditional
rate's denominator is 78 agents x 42 years, fixed by the design. The conditional rate's denominator
is written by the model and differs between arms, so there is no fixed reference to test it against.

**Weak-null caveat that must travel with these numbers.** A uniformly random agent is a weak null. A
governed marginal rate at chance means no net directional pull, NOT that governed behaviour is
random: the same marginal is consistent with many policies. The manuscript confines the claim to
direction and must not be edited into anything stronger.

## 15. The antecedent is a conjunction (`e6_antecedent_conjunction.py`, added 2026-08-02)

The rule under study, `high_threat_high_cope_no_increase` (R4) in
`examples/irrigation_abm/config/agent_types.yaml`, fires on **two** conditions, `WSA_LABEL in {H, VH}`
**and** `ACA_LABEL in {H, VH}`. Both labels are written by the agent in the generation being judged.
A second enforced theory rule, `low_threat_no_increase` (R2), fires on `WSA_LABEL == VL`, whose
antecedent is **disjoint** from the scarcity-high set.

Every prevalence and conditional rate elsewhere in this file is measured on the **scarcity marginal**,
`WSA_LABEL in {H, VH}`, which is a strict **superset** of R4's antecedent. That marginal is the
quantity the published statistics on this corpus condition on and is the paper's **primary** quantity;
it is **not** the rule's antecedent and no sentence may call it that.

Anchor cell `gemma3:4b`, irrigation, 5 paired seeds (42–46), 16,380 decisions per arm. Prevalence
figures are means of per-seed rates; the shift CI is a paired t interval, df = 4. `SHIFT` and `GAP`
are both `(no-validator) − (with-validators)` per the file-wide sign convention.

| antecedent | prevalence, governed | prevalence, no-validator | shift | 95% CI | rate gov | rate nov | rate gap | where in stdout (`e6`) |
|---|---:|---:|---:|---|---:|---:|---:|---|
| scarcity marginal, `WSA in {H,VH}` (**primary**) | 37.08% | 82.80% | **+45.73 pp** | — | 36.05% | 59.07% | **+23.02 pp** | `scarcity marginal  WSA in {H,VH}              37.08%    82.80%   +45.73    36.05%    59.07%   +23.02` |
| coping marginal, `ACA in {H,VH}` | 70.66% | 83.06% | **+12.41 pp** | [+9.78, +15.03] | 55.28% | 73.21% | +17.92 pp | `coping marginal    ACA in {H,VH}              70.66%    83.06%   +12.41    55.28%    73.21%   +17.92` |
| **R4 antecedent, both conjuncts high** | **25.46%** | **68.61%** | **+43.15 pp** | [+39.06, +47.24] | 49.42% | 69.28% | **+19.86 pp** | `R4 antecedent      WSA and ACA both high      25.46%    68.61%   +43.15    49.42%    69.28%   +19.86` |
| R2 antecedent, `WSA == VL` | 3.36% | 0.09% | **−3.27 pp** | — | 6.00% | 10.00% | +4.00 pp | `R2 antecedent      WSA == VL                   3.36%     0.09%    -3.27     6.00%    10.00%    +4.00` |
| R2 or R4 fires | 28.82% | 68.70% | **+39.88 pp** | — | 44.30% | 69.21% | **+24.91 pp** | `R2 or R4 fires                                28.82%    68.70%   +39.88    44.30%    69.21%   +24.91` |

The two CIs above are the only ones `e6` prints; they are on the two rows the script's own CLAIM
lines carry:

| claim | value | where in stdout (`e6`) |
|---|---|---|
| the coping conjunct moves, and is not a fixed covariate | **+12.41 pp** (95% CI +9.78, +15.03) | `CLAIM both_conjuncts_move:` line and the line under it |
| the conjunction's own prevalence shift | **+43.15 pp** (95% CI +39.06, +47.24) | `CLAIM conjunction_shift:` line |
| the conditional rate on the conjunction | gap **+19.86 pp** | same `CLAIM conjunction_shift:` block, second line |
| verdict | `VERDICT: HOLDS` | last block |

**Reading.** Both conjuncts of the antecedent are agent-written and **both** move between arms. That
is a second instance of the paper's own claim rather than a caveat on it: there is no conjunct
available to hold fixed. The conjunction shifts +43.15 pp against the scarcity marginal's +45.73 pp,
so the correction changes what the denominator is **called**, not the magnitude class of the finding.

**What would falsify it.** A coping conjunct whose paired CI contained zero. The script exits 1 in
that case, and in the case where the conjunction's shift departs from the scarcity marginal's by more
than 10 pp. It exits 0 on this corpus.

**Wording this supports (and the wording it kills).**
- ❌ "the decisions whose self-reported appraisal falls inside the rule's antecedent" for the scarcity
  marginal — it is one conjunct of two, a superset of R4's antecedent and disjoint from R2's.
- ✅ "the scarcity conjunct of the rule's antecedent", with the coping conjunct and the conjunction
  reported beside it.

---

## 16. The ministral3:8b cell became balanced (2026-08-03) — what moved

> **STATUS: APPLIED 2026-08-03.** This section was written as a read-only survey before anything
> was changed. Everything it recommends has since been applied: the frozen brief tuples, the
> `IRRIGATION_UNBALANCED_PREFIXES` removal, the `precondition_violation` token, the
> `_verify_pipeline.py` inventory, the manuscript, the CLAIM definitions, and the tables above in
> this file. Where the text below says something is "stale", "pending" or "a false green", read it
> as the state on the morning of 2026-08-03, not as an open item. `run_all.py` is 13/13,
> `corpus_inventory.py` exits 0, and `submission_gate.py` fails on the font item only.

**What happened.** The irrigation `ministral3:8b` no-validator seed 44 run landed
(`examples/irrigation_abm/results/ungoverned_v21_42yr_ministral3_8b_seed44`, 3,276 rows, 42 years,
78 agents). The cell is now **3 governed seeds against 3 no-validator seeds — balanced**. It had been
3 governed against 2 no-validator, and on that basis the manuscript excluded it from every paired
test, drew it open and unfilled, and said so in about ten places.

Everything below is **computed from the corpus**, quoted from real stdout. Nothing here has been
written into the manuscript, and item 16d says why the decomposition in particular must not be.

Commands (all run 2026-08-03, `PYTHONIOENCODING=utf-8`, from the repo root):

```
python SUBMISSION_2026/TAE/evidence/table1_cells.py                                     # exit 1 (7 disagreements, all ministral)
python SUBMISSION_2026/TAE/evidence/fig1_rule_layers.py                                 # exit 1 (3 FALSIFIED lines, all ministral no-validator)
python SUBMISSION_2026/TAE/evidence/fig2_mechanism.py                                   # exit 1 (3 disagreements)
python SUBMISSION_2026/TAE/evidence/fig3_consequence.py                                 # exit 1 (7 disagreements, all ministral)
python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py                     # exit 0, md5 02536fe93f2798b4ab2b65717cd8d7ef (anchor UNCHANGED)
python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py "ministral3:8b"     # exit 0, VERDICT: HOLDS
```

### 16a. The cell's own numbers, 2 paired seeds -> 3 paired seeds

`Delta = (no-validator) - (with-validators)`, cell value = mean of per-seed rates, seed the
inferential unit, LAST-PROPOSED action reading, paired t on the per-seed deltas (df = 2).

| quantity | frozen 2-seed record | computed, 3 seeds | move | 95% CI (new) | p (new) |
|---|---:|---:|---:|---|---:|
| *n* paired | 2 | **3** | +1 | — | — |
| HIGH prevalence, on | 15.46 | **13.56** | −1.90 | — | — |
| HIGH prevalence, off | 46.54 | **44.69** | −1.85 | — | — |
| Delta HIGH | +31.07 | **+31.13** | +0.06 | (+28.69, +33.56) | 0.000 |
| conditional, on | 2.69 | **3.25** | +0.56 | — | — |
| conditional, off | 5.10 | **6.05** | +0.95 | — | — |
| Delta conditional | +2.41 | **+2.80** | +0.39 | (+0.02, +5.58) | **0.049** |
| unconditional, on | 52.01 | **54.35** | +2.34 | — | — |
| unconditional, off | 30.89 | **32.18** | +1.29 | — | — |
| Delta unconditional | −21.12 | **−22.17** | −1.05 | (−29.02, −15.32) | **0.005** |
| Delta unconditional, EXECUTED reading | (not recorded) | **+20.26** | — | (+11.69, +28.83) | 0.010 |
| never-retried Delta HIGH | +35.86 | **+34.09** | −1.77 | — | — |
| governed rejection pressure (per-seed mean) | 62.19 | **62.63** | +0.44 | — | — |

Per-seed deltas, from `figures/fig3_consequence.csv`:
conditional `42:1.522928; 43:3.292479; 44:3.592238`; unconditional
`42:-19.047619; 43:-23.199023; 44:-24.267399`.

Source lines (`table1_cells.py` section B):

```
ministral3:8b  LAST-PROPOSED  |     3.25     6.05    2.80   (  +0.02,  +5.58)  0.049 |    54.35    32.18  -22.17   ( -29.02, -15.32)  0.005  *EXCL
ministral3:8b  EXECUTED       |     1.65     5.85    4.20   (  +4.15,  +4.25)  0.000 |    11.07    31.33   20.26   ( +11.69, +28.83)  0.010  *EXCL
```

The `*EXCL` flag is now **stale**: `_data.IRRIGATION_UNBALANCED_PREFIXES` still names
`ministral3_8b_` by hand, while `_data.seed_sets("ministral3_8b_")` reports `balanced True`. The
exclusion is no longer a criterion the data satisfies; it is a literal.

### 16b. Where the cell sits beside the other four

| cell | *n* | Delta HIGH | Delta cond. | Delta uncond. | gap (cond − uncond) |
|---|---:|---:|---:|---:|---:|
| gemma3:4b (anchor) | 5 | +45.73 | +23.02 | +21.62 | +1.39 |
| gemma3:12b | 3 | +21.27 | +11.44 | +0.16 | +11.28 |
| gemma4:e2b | 5 | +47.53 | +18.94 | +15.25 | +3.69 |
| gemma4:e4b | 5 | +43.38 | +17.41 | +8.52 | +8.89 |
| **ministral3:8b** | **3** | **+31.13** | **+2.80** | **−22.17** | **+24.97** |

**It is not an outlier on the paper's pattern; it is the extreme case of it.**
- Delta HIGH positive in all five, and `+31.13` sits inside the already-published range
  `+21.27 to +47.53`. The range endpoints do not move.
- `fig3_consequence.py`'s stated falsifier is *"a balanced cell whose unconditional Delta EXCEEDS its
  conditional Delta"*. `+2.80 > −22.17`, so the decomposition claim survives, on five of five
  balanced cells rather than four of four, and the conditional–unconditional gap is more than twice
  the previous maximum.
- **The negative sign was already visible** when the cell was excluded: the frozen record carried
  `−21.12` and Figure 4 drew it as an open bar below zero. What is new is that it now carries an
  interval, and that interval excludes zero (`−29.02, −15.32`; p = 0.005). It is no longer a point
  estimate a reader may discount; on this cell the validators **raised** the increase-proposal rate
  over the design-fixed denominator by about 22 pp while **lowering** it by about 3 pp over the
  agent-written one. The two statistics disagree in sign, not merely in size.

Two honest caveats that travel with it:
1. The conditional delta is significant only marginally (p = 0.049, CI lower bound +0.02).
2. The unconditional sign **flips with the action reading**: LAST-PROPOSED `−22.17`, EXECUTED
   `+20.26` (p = 0.010). This is the same reading-dependence §6 already discloses for gemma3:12b
   (`+0.16` -> `+27.82`), in a stronger form. The governed arm proposes an increase on 54.35% of its
   decisions and executes one on 11.07%, at 62.63% rejection pressure — the gap between the two
   readings *is* the retry loop.

### 16c. Corpus-level numbers that moved because one seed entered the pool

| quantity | recorded | computed 2026-08-03 | source |
|---|---:|---:|---|
| pooled never-retried Delta | +49.09 | **+48.21** | `fig2_mechanism.py` panel C, `pooled` row |
| pooled all-decisions Delta | +40.45 | **+40.02** | same |
| paired seeds pooled | 20 | **21** | same (`pooled 21`) |
| no-validator rejection range, pooled per arm | 1.0% to 29.0% | **0.9% to 29.0%** | `fig1_rule_layers.py` panel B (ministral no-validator 84 / 9,828 = 0.9%) |
| the same range excluding the anchor | 1.0% to 5.3% | **0.9% to 5.3%** | same |
| governed rejection range, Table 1 per-seed-mean basis | 28.09% to 62.19% | **28.09% to 62.63%** | `table1_cells.py` section A, `press.gov` column |
| irrigation cells with balanced seeds | four | **five** | `_data.seed_sets`, `balanced True` on all five |
| rule-layer purity | 10/10 | **9/10 as the code currently classifies** — see 16e | `fig1_rule_layers.py` panel B, `pure?` column |

Unchanged, checked and confirmed: `irrigation_high_delta_range` (+21.27 to +47.53), `govrej_range`
(28.1% to 62.6%), `novrej_increase_pct` (99.95%), `govrej_increase_pct` (67.87%),
`govrej_decrease_pct` (31.8%), `appraisal_conditioned_pct` / `world_conditioned_pct` (59.4 / 40.6,
anchor only), `atcap_*` (anchor only), `neverretried_larger_cells` (5 of 5), `n_seeds` ("five in most
and fewer in two irrigation cells" — still exactly two cells at 3 seeds), `n_model_configs` (nine),
every flood number, and every anchor-cell number in §2, §5, §7 and §13.

### 16d. World-fixed decomposition on ministral3:8b — RUN, RECORDED, NOT FOR THE MANUSCRIPT

Anchor integrity first. The no-argument run is byte-identical to its frozen state:

```
$ python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py | md5sum
02536fe93f2798b4ab2b65717cd8d7ef
```

`python SUBMISSION_2026/TAE/evidence/e4_world_fixed_decomposition.py "ministral3:8b"`, exit 0,
paired seeds 42, 43, 44. Raw shift, world **not** held fixed: gov 13.56% vs noval 44.69%,
**+31.13 pp**.

| world held fixed at | strata | coverage gov / nov | residual (pooled wt) | gov-wt | nov-wt | per-seed mean (95% CI) |
|---|---:|---:|---:|---:|---:|---|
| shortage tier | 4 | 100.0% / 100.0% | **−4.44** | −2.90 | −5.97 | −5.14 (−11.80, +1.52) |
| tier + curtailment | 4 | 100.0% / 100.0% | **−4.44** | −2.90 | −5.97 | −5.14 (−11.80, +1.52) |
| tier + Mead elevation, 25 ft | 8 | 96.0% / 100.0% | **−4.63** | −2.96 | −6.24 | −4.71 (−12.13, +2.71) |
| tier + Mead 10 ft + drought decile | 20 | 61.9% / 55.6% | **+0.01** | −0.09 | +0.13 | −0.33 (−2.70, +2.03) |
| tier + Mead + drought + agent cluster | 20 | 53.2% / 47.7% | **+0.60** | +0.20 | +1.05 | +0.33 (−2.03, +2.69) |

- largest |residual| at any resolution: **4.63 pp**, against a raw shift of **+31.13 pp**
- largest under any of the three weighting schemes: **6.24 pp**; weighting swing at most 1.67 pp
- 5 of 5 rungs carry a per-seed 95% interval; **0 of 5 exclude zero**
- composition (PART 3): governed arm **79.4%** of its decisions in shortage tier 0, no-validator arm
  **34.1%** in tier 3
- PART 1, the §7 negative result replicated on a second cell: the world antecedents shift **more**
  than the self-report — `shortage_tier >= 1` and `curtailment_ratio > 0` each **+57.14 pp**,
  `shortage_tier >= 2` **+45.24 pp**, against the self-report's +31.13 pp
- `VERDICT: HOLDS — the largest residual (4.63 pp) is below a quarter of the raw shift (31.13 pp).`

**Where that leaves the five cells**, by the script's own pre-registered gate (largest residual at
any rung < one quarter of the raw shift):

| cell | raw shift | coarse residual | largest residual, any rung | verdict | exit |
|---|---:|---:|---:|---|---:|
| gemma3:4b (anchor) | +45.73 | −2.53 | 4.47 | **HOLDS** | 0 |
| gemma4:e4b | +43.38 | −3.33 | 4.08 | **HOLDS** | 0 |
| ministral3:8b | +31.13 | −4.44 | 4.63 | **HOLDS** | 0 |
| gemma3:12b | +21.27 | −4.94 | 5.86 | FAILS | 1 |
| gemma4:e2b | +47.53 | +5.18 | 13.52 | FAILS | 1 |

**Three of five**, up from two of four. Read honestly in both directions: on the **coarse rung
alone**, which is the rung the manuscript quotes and the only one at 100% coverage, all five cells
sit under the same bar (residual / raw shift = 5.5%, 7.7%, 14.3%, 23.2%, 10.9%). Both failures are
driven by fine rungs at roughly half coverage. Neither reading is in the manuscript and neither
should be.

**Why none of this goes into the manuscript.** §5 scopes its mechanism claim to the anchor cell by
name ("In the anchor cell the shift in the conditioning variable is composition of world states"),
and Table 2 is captioned "Anchor cell, five paired seeds". No manuscript sentence generalises the
decomposition across cells, so nothing here makes an existing sentence false, and a fifth
decomposition cell would be a **new claim**. The standing instruction (2026-08-03) forbids adding
one. Recorded here for traceability only.

### 16e. The fig1 falsification is a schema artefact, not a behavioural finding — DO NOT NARROW §3 ON IT

`fig1_rule_layers.py` now prints three FALSIFIED lines:

```
  !! FALSIFIED: rule names appear in failed_rules that are in neither taxonomy list, so the appraisal/world split is incomplete: precondition_violation
  !! FALSIFIED: ministral3:8b no-validator: 19 rejections name a behavioural rule; the two layers are NOT disjoint
  !! FALSIFIED: ministral3:8b no-validator: 19 rejections are not the precondition
```

Diagnosed directly from the audit csv. All 19 rejections in
`ungoverned_v21_42yr_ministral3_8b_seed44/irrigation_farmer_governance_audit.csv` carry:

```
error_messages : "Precondition failed: 'not at_allocation_cap' (field is True)"
failed_rules   : precondition_violation        (19 of 19)
proposed skill : increase_large 10, increase_small 9     (19 of 19 increases)
status         : REJECTED 19, APPROVED 3,257
```

Seed 43 in the same arm carries the **identical** `error_messages` string on all 33 of its
rejections, and `failed_rules: Unknown` on all 33. `_data._NO_RULE_TOKENS` = `{"", "unknown",
"none", "n/a", "nan"}` treats an empty-or-`Unknown` cell as "no rule named" -> `precondition`;
`precondition_violation` is a real string, so `rejection_cause()` returns `"theory"`, and fig1 then
files it under world-conditioned because it is in neither rule list.

**These are the same water-right allocation-cap rejections the other seeds record. The two rule
layers have not stopped being disjoint; the newer audit writer names the precondition instead of
leaving it `Unknown`.** The fix is one token in `_data._NO_RULE_TOKENS`, after which purity returns
to 10/10 and `novrej_increase_pct` is 6,187 / 6,190 = 99.95% — the same 99.95% it is today.

Two related defects found while diagnosing this, neither in `SUBMISSION_2026/TAE/`:
- `fig1_rule_layers.py` builds its caption with a literal
  `f"{len(D.IRRIGATION_MODELS)*2} of {len(D.IRRIGATION_MODELS)*2} cells pure"`, so the generated
  caption prints **"10 of 10 cells pure"** while the table above it prints `pure? False`. The
  caption number is not computed from purity and cannot ever disagree with itself.
- `_verify_pipeline.py` hardcodes `"ministral3:8b": ("ministral3_8b_", [42, 43, 44], [42, 43])` and
  its own 2-seed brief row, so it **PASSES (exit 0) on the stale record** and reports
  `ministral3:8b n=2 cond 2.69/5.10/+2.41 unc 52.01/30.89/-21.12`. It is the one gate in the suite
  that does not see the new seed. A false green, not a real one.

### 16f. Provenance of the new run — flag, not a blocker

`ungoverned_v21_42yr_ministral3_8b_seed44/reproducibility_manifest.json` records
`git_commit: 10e190cf1f3805e2869e91b52d8c178a01b0f5f3`, `git_dirty: true`,
`timestamp: 2026-08-03T14:38:47`, and a full modern manifest (model digest, quantisation,
config hash, `run_integrity` block). The other five runs in the cell (governed 42/43/44,
no-validator 42/43) carry a five-key manifest with **no commit recorded at all**. The seed-44
directory also ships `run_integrity.json`, `validator_health.csv` and an audit schema file that its
cell-mates do not.

So the balanced cell pools one run from today's HEAD with five from an unrecorded earlier code
state, and the difference is **observable in the data** as the `failed_rules` naming change in 16e.
Nothing found so far suggests a behavioural difference — the rejections are the same rule with the
same message on the same skills — but the manuscript's Artifact-availability sentence ("the run
manifests record a modified working tree wherever they record one") remains exactly right and now
covers this run too.

Also stale, and in `examples/` so not touched here:
`production_v21_42yr_ministral3_8b_seed44/_DEFECT_unpaired_orphan.txt` still reads *"has NO matching
no-validator run ... ACTION: drop seed44 from the ministral3_8b paired analysis (report
n_pairs=2)"*. The condition it describes ended today.

### 16g. Manuscript sentences this makes FALSE — narrowing required, nothing added

Every item below **removes or corrects** a claim. None adds one. Line numbers are
`paper/manuscript.md` as of 2026-08-03.

| # | line | text | status |
|---|---:|---|---|
| 1 | 258 | Table 1 row `ministral3:8b \| 2 \| 15.46 \| 46.54 \| +31.07 \| 2.69 \| 5.10 \| +2.41` | **FALSE** — 3 / 13.56 / 44.69 / +31.13 / 3.25 / 6.05 / +2.80 |
| 2 | 249–250 | "ministral3:8b is unbalanced, excluded from every paired test, point estimates shown" | **FALSE** — balanced 3 v 3; it now carries intervals |
| 3 | 404–407 | "ministral3:8b stands outside all of this. Its arms are unbalanced, … excluded by a criterion applied in code … no interval, the sign reversal uninterpreted" | **FALSE** in every clause |
| 4 | 435 | Fig 4 caption, "ministral3:8b is unbalanced and drawn unfilled without an interval rather than dropped" | **FALSE** |
| 5 | 477–478 | §8, "One irrigation configuration is unbalanced, …, excluded from every paired interval and test" | **FALSE** |
| 6 | 204–205 | Fig 2 caption, "An asterisk marks ministral3:8b, whose arms are unbalanced" | **FALSE** |
| 7 | 355 | §5, "in 5 of 5 irrigation cells, **the unbalanced one included** since this comparison carries no interval" | count 5 of 5 still holds; the parenthetical is **FALSE** |
| 8 | 379–380 | Fig 3 caption, "ministral3:8b in panel c is unbalanced and drawn without an interval" | **FALSE** |
| 9 | 233 | §4, "*p* < 0.05 in each of the **four** with balanced seeds" | **FALSE** — five are balanced, and ministral's Delta HIGH is p < 0.001, so the corrected sentence is *stronger* while being narrower in nothing |
| 10 | 358–359 | §5, "+49.09 against +40.45 when pooled over all **20** paired seeds" | **FALSE** — +48.21, +40.02, 21 seeds |
| 11 | 376 | Fig 3 caption, "pooled over the 20 paired seeds" | **FALSE** — 21 |
| 12 | 166 | §3, "validators-off rates spanning 1.0% to 29.0%" | **FALSE** — 0.9% to 29.0% |
| 13 | 183 | §3, "the other four configurations reject 1.0% to 5.3%" | **FALSE** — 0.9% to 5.3% |
| 14 | 236 | §4, "28.09% to 62.19% of governed irrigation decisions rejected on Table 1's per-seed-mean basis" | **FALSE** — 62.63% |
| 15 | 164–165, 199 | §3 and Fig 2 caption, "exact in **10/10** irrigation model-arm cells" | **conditionally false** — 9/10 as the classifier stands, 10/10 once `_NO_RULE_TOKENS` learns `precondition_violation` (16e). Fix the classifier, not the sentence |

Two sentences to watch, neither yet false:

- **line 388**, "the reported effect shrinks in every irrigation cell and on one of them disappears".
  On ministral the effect goes `+2.80 -> −22.17`: it shrinks on the signed reading the Delta
  convention defines, and grows eightfold on the magnitude reading a reader will apply. The sentence
  was written when the cell was outside. It is now load-bearing over a cell whose estimate reverses
  sign, and "shrinks" should be made unambiguous.
- **lines 64 and 109 and 434**, "on one configuration the whole apparent gain is composition"
  (gemma3:12b). Still true of gemma3:12b. ministral is a second, stronger instance, so the sentence
  is now an **under**-claim rather than a false one. Leave it: correcting it would add a claim.
