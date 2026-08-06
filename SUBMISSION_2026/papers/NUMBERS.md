# NUMBERS.md — every quantitative claim the workshop paper makes, and where it comes from

One command regenerates all of it:

```bash
python SUBMISSION_2026/papers/workshop_evidence.py
```

Outputs, all beside this file in `SUBMISSION_2026/papers/`:
`per_cell_table.csv` · `fig1_data.csv` · `fig1_regime_separation.png` (300 dpi) · stdout.

Provenance below is given as **section** + the exact greppable stdout line. Every `CLAIM …` line is
emitted by section E. Line numbers are deliberately not used — they move; the CLAIM keys do not.

Environment of the frozen run: Python 3.14.0, matplotlib 3.10.7, Windows.
Repo root `C:/Users/wenyu/Desktop/Lehigh/governed_broker_framework`. Read-only w.r.t. `examples/`.

---

## 0. Read this first — four things that disagree with the skeleton

| # | What the skeleton says | What the data says | Severity |
|---|---|---|---|
| D1 | `flood ministral3:3b   0.09 % rejected, +2.04 pp shift` | **0.11 % rejected, −0.22 pp shift.** The prior-art script pools **903 rows from `examples/single_agent/results/JOH_FINAL/ministral3_3b/Group_A/Run_1_bak_broker/household_governance_audit.csv`** — a `Group_A` backup, a *different* experiment (no structured prompts) — into that cell's **governed** arm. It is the only directory outside `Group_C` in the whole flood corpus that carries a governance audit CSV, so it contaminates exactly one cell. Removing it flips the sign of that cell's shift. | **must fix before submitting** |
| D2 | abstract: "**432,083** logged decisions across 14 model×testbed cells" | **216,020** logged decision rows in the 14 cells (215,898 with a parsed appraisal). Candidate counts that were tried and none of which reproduce 432,083: 216,923 (all audit CSVs under both testbed trees, prior-art glob, incl. the Group_A backup); 370,383 (`Σ 1 + retry_count`, i.e. LLM proposal attempts); 370,928 (`Σ 1 + retry_count + format_retries`); 460,239 (audit rows + every `simulation_log.csv`, incl. Group_A). **The abstract number is not reproducible from this corpus and must be replaced with 216,020.** | **must fix before submitting** |
| D3 | limitations: "a seed-labelling mismatch affects paired tests on **6 of 9 flood** configurations" | Confirmed exactly — and **7 of 14 cells overall are unbalanced**, because `irrigation ministral3:8b` also is (3 governed seeds `42,43,44` vs 2 ungoverned `42,43`). That cell is the **top row of the paper's per-cell table** (the highest enforcement pressure, 62.63 %). Its shift moves +32.97 → **+31.07 pp** on the 2 shared seeds. The limitation as written implies irrigation is clean. | **must extend the sentence** |
| D4 | low regime: "mean **+0.8** pp (−3.7 … +6.3)" | **mean +0.56 pp (−3.69 … +6.25)** once D1 is fixed. Range endpoints match; the mean moves because ministral3:3b flips. | **update the abstract and Table 1** |

Everything else in the skeleton reproduces. In particular the anchor gate passes exactly
(`CLAIM anchor_gate: PASS`), and all five irrigation per-cell values, all four irrigation-side
regime statistics, and eight of nine flood cells are unchanged.

---

## 1. Corpus and cell inventory

| Claim | Value | Where |
|---|---|---|
| model × testbed cells | 14 | §A `CLAIM n_cells: 14` |
| — irrigation | 5 | §A `CLAIM n_cells_irrigation: 5` |
| — flood | 9 | §A `CLAIM n_cells_flood: 9` |
| logged decision rows | **216,020** | §A `CLAIM corpus_decision_rows: 216020` |
| rows with a parsed appraisal (rate denominator) | 215,898 | §A `CLAIM corpus_rows_with_appraisal: 215898` |
| rows dropped for a blank appraisal cell | 119 governed + 3 ungoverned | §A "rows with a blank appraisal cell" |
| unbalanced cells (arms carry different seed sets) | **7 of 14** | §A `CLAIM n_unbalanced_cells: 7` |
| cells differing from the committed `evidence/appraisal_composition.csv` | 1 (`flood ministral3:3b`) | §A `CLAIM cells_differing_from_prior_art_csv: 1` |
| flood cells contaminated by the prior-art recursive glob | 1 | §A `CLAIM flood_cells_contaminated_by_prior_art_glob: 1` |

LLM configurations: 5 distinct in irrigation (`gemma3:4b`, `gemma3:12b`, `gemma4:e2b`,
`gemma4:e4b`, `ministral3:8b`) and 9 in flood, union **9 configurations** across 3 B–27 B in two
open-weight families. The skeleton's "9 LLM configurations, 3B–27B, two open-weight families"
is consistent with the directory inventory.

**Seeds are not 5 everywhere.** Per-cell seed sets are printed in §A and stored in
`per_cell_table.csv` (`seeds_governed`, `seeds_ungoverned`, `balanced`, `paired_seeds`). The
skeleton's flat "5 seeds" is wrong for `irrigation gemma3:12b` (3+3),
`irrigation ministral3:8b` (3+2), and for the six flood cells whose governed arm carries seeds
`42, 4202, 4203, 45, 46` against an ungoverned `42, 43, 44, 45, 46`.

---

## 2. Table 1 — per-cell (paper §3)

Enforcement pressure = share of **governed** decisions with a terminal `REJECTED*` status
(`REJECTED` + `REJECTED_FALLBACK`). Shift = ungoverned − governed prevalence of the appraisal in
the rule's antecedent (`construct_WSA_LABEL ∈ {H,VH}` for irrigation, `construct_TP_LABEL ∈ {H,VH}`
for flood). Source: §A table, `per_cell_table.csv`, and one `CLAIM cell_<cell>_*` pair each.

| cell | % rejected | shift (pp) | shift on shared seeds | balance |
|---|---:|---:|---:|---|
| irrigation ministral3:8b | 62.63 | +32.97 | **+31.07** | UNBALANCED (3 v 2) |
| irrigation gemma4:e4b | 56.29 | +43.38 | +43.38 | balanced |
| irrigation gemma3:12b | 49.52 | +21.26 | +21.26 | balanced (3 v 3) |
| irrigation gemma3:4b | 39.10 | +45.50 | +45.50 | balanced |
| irrigation gemma4:e2b | 28.08 | +47.53 | +47.53 | balanced |
| flood gemma3:4b | 0.85 | −1.24 | −4.04 | UNBALANCED |
| flood gemma4:e4b | 0.47 | +6.25 | +6.25 | balanced |
| flood gemma4:26b | 0.12 | +2.92 | +2.92 | balanced |
| **flood ministral3:3b** | **0.11** | **−0.22** | +1.18 | UNBALANCED |
| flood ministral3:8b | 0.02 | −3.69 | −3.27 | UNBALANCED |
| flood gemma3:12b | 0.02 | −1.64 | −0.69 | UNBALANCED |
| flood gemma3:27b | 0.00 | +1.22 | +1.70 | UNBALANCED |
| flood ministral3:14b | 0.00 | +0.48 | +1.03 | UNBALANCED |
| flood gemma4:e2b | 0.00 | +0.97 | +0.97 | balanced |

Greppable, e.g. `CLAIM cell_flood_ministral33b_shift_pp: -0.22`.

Diagnostic printed but **not** used as pressure: the ungoverned arm's own `REJECTED` rate
(§A column `%rej ung`). It is 0.00 % in all nine flood cells and 0.99–29.03 % in irrigation,
where those rows are skill-*precondition* failures (a world affordance), not enforcement.
The anchor's 29.03 % is the same quantity `decomposition/linkage_check.py` reports as 29.04 %;
the 0.01 pp difference is the three blank-appraisal ungoverned rows this script excludes.

---

## 3. Regime summary (paper §3, Table 1 top block)

| Claim | Value | Where |
|---|---|---|
| high-pressure cells | 5 | `CLAIM high_n_cells: 5` |
| high-pressure range | 28.08 % … 62.63 % | `CLAIM high_pressure_min_pct / high_pressure_max_pct` |
| high-pressure mean shift | **+38.13 pp** | `CLAIM high_shift_mean_pp: 38.13` |
| high-pressure shift range | +21.26 … +47.53 | `CLAIM high_shift_min_pp / high_shift_max_pp` |
| high-pressure cells with a positive shift | 5/5 | `CLAIM high_shift_positive_count: 5/5` |
| low-pressure cells | 9 | `CLAIM low_n_cells: 9` |
| low-pressure range | 0.00 % … 0.85 % | `CLAIM low_pressure_min_pct / low_pressure_max_pct` |
| low-pressure mean shift | **+0.56 pp** (skeleton says +0.8 — see D1/D4) | `CLAIM low_shift_mean_pp: 0.56` |
| low-pressure shift range | −3.69 … +6.25 | `CLAIM low_shift_min_pp / low_shift_max_pp` |
| low-pressure cells with a positive shift | 5/9 | `CLAIM low_shift_positive_count: 5/9` |
| separation on the shift | **COMPLETE**, margin +15.01 pp | `CLAIM separation_shift: COMPLETE`, `CLAIM separation_margin_pp: 15.01` |
| separation on pressure | COMPLETE (28.08 % vs 0.85 %) | `CLAIM separation_pressure: COMPLETE` |
| monotone within the high group? | **no** | `CLAIM high_group_monotone: no` |

Two things the script prints that the paper must carry:

1. **The 5 % threshold is not load-bearing.** No cell lies between 0.85 % and 28.08 %, so any cut
   in that interval gives the same partition (§B, "the 5% threshold is not load-bearing").
2. **The pressure split is *identical* to the testbed split** (§B, "the pressure split is IDENTICAL
   to the testbed split"). Regime and testbed are perfectly confounded in this corpus. The flood
   null is still a valid control against a harness artifact — same framework, same governance code,
   same audit writer — but the paper may not present enforcement pressure as an independent
   continuous predictor, and must not claim a dose–response. The skeleton already forbids the dose
   claim; this makes the reason concrete.

---

## 4. Conditional vs unconditional, irrigation (paper §4)

Conditional = increases ÷ decisions self-reporting `WSA ∈ {H,VH}`. Unconditional = increases ÷ every
decision (denominator fixed by design at 78 agents × 42 years = 3,276 rows per run). Action variable
= `simulation_log.yearly_decision`, the last **proposed** action. Rates are the **mean of per-seed
rates**, on seeds present in both arms — that convention is what reproduces the published pair.
Sign convention: gap = governed − ungoverned, so negative = governance lowered the rate.

| cell | cond gov | cond ung | cond gap | unc gov | unc ung | unc gap | survives |
|---|---:|---:|---:|---:|---:|---:|---:|
| gemma3:4b (anchor) | **36.05** | **59.07** | −23.02 | **40.90** | **62.52** | −21.62 | 93.9 % |
| gemma3:12b | 5.45 | 16.89 | −11.44 | 41.36 | 41.52 | −0.16 | 1.4 % |
| gemma4:e2b | 12.71 | 31.65 | −18.94 | 22.80 | 38.05 | −15.25 | 80.5 % |
| gemma4:e4b | 23.67 | 41.08 | −17.41 | 36.36 | 44.87 | −8.52 | 48.9 % |
| ministral3:8b | 2.69 | 5.10 | −2.41 | 52.01 | 30.89 | **+21.12** | **sign flip** |

Greppable, e.g. `CLAIM irrigation_gemma34b_conditional_governed_pct: 36.05`,
`CLAIM irrigation_gemma34b_unconditional_gap_pp: -21.62`.

**Anchor gate: PASS** — `CLAIM anchor_gate: PASS`. The brief pre-committed 36.05 / 59.07 and
40.90 / 62.52; the script asserts all four at 2 dp and prints MISMATCH otherwise
(§C "ANCHOR GATE"). Raw values 36.0521 / 59.0700 / 40.8974 / 62.5214.

Cross-checks against `SUBMISSION_2026/decomposition/RESULTS.md`, which is independently verified:
−21.62 pp anchor unconditional gap (§2 of that memo), 93.9 % survival (§2), 1.4 % on gemma3:12b and
+21.12 pp sign flip on ministral3:8b (§4). All four reproduce here to 2 dp.

**Do not quote `CLAIM irrigation_ministral38b_gap_survival_pct: 877.3`.** It is
|+21.12| / |−2.41| across a sign change and is meaningless as a "survival" fraction; the script
tags the row `<- SIGN FLIP` for exactly this reason. Report the sign flip, not the ratio.

### 4b. The same statistic on the executed action (paper §4, "two defensible definitions")

A rejected proposal never moved the water request; the registry default `maintain_demand` executed.
Recomputing on the executed action (§C "EXECUTED-ACTION recomputation"):

| cell | exec cond gov | exec cond ung | exec unc gov | exec unc ung |
|---|---:|---:|---:|---:|
| gemma3:4b | **0.86** | **26.77** | 3.60 | 33.50 |
| gemma3:12b | 0.17 | 13.13 | 8.37 | 36.19 |
| gemma4:e2b | 0.00 | 27.96 | 5.63 | 34.47 |
| gemma4:e4b | 0.11 | 40.06 | 6.84 | 43.41 |
| ministral3:8b | 0.60 | 4.79 | 11.34 | 29.90 |

`CLAIM anchor_executed_conditional_governed_pct: 0.86` /
`CLAIM anchor_executed_conditional_ungoverned_pct: 26.77`. Matches `RESULTS.md` §7 M2
(0.86 % vs 26.77 %; unconditional 3.60 % vs 33.50 %) exactly. This is the skeleton's
"36.05 % to 0.86 %" claim — **verified**.

### 4c. Retry-stratified appraisal (paper §5)

Anchor governed arm, prevalence of `WSA ∈ {H,VH}` by `retry_count`
(`CLAIM retry_stratified_high_pct_parsed: 0:23.9 1:57.6 2:58.1 3:39.4`):

| retries | rows | % high (parsed denominator) | % high (all rows) |
|---:|---:|---:|---:|
| 0 | 5,930 | 23.88 | 23.88 |
| 1 | 1,940 | 57.58 | 57.58 |
| 2 | 1,231 | 58.08 | 58.08 |
| 3 | 7,279 | **39.38** | 38.81 |

The skeleton's `23.9 / 57.6 / 58.1 / 39.4` **reproduces**, on the parsed-row denominator. The
all-rows denominator gives 38.81 at 3 retries because the 105 unparseable governed rows all sit in
that stratum. Non-monotone either way, which is the skeleton's point. State the denominator.

---

## 5. Figure 1

`fig1_regime_separation.png`, 300 dpi, produced (`CLAIM figure1_png: fig1_regime_separation.png`).
matplotlib **is** installed here (3.10.7); if it were not, the script writes `fig1_data.csv`, prints
the drawing code, and says the PNG was not produced.

- x = enforcement pressure (% of governed decisions rejected), **symlog with a linear threshold at
  1 %** so the nine sub-1 % flood cells stay visible. Say this in the caption.
- y = appraisal shift in pp; horizontal line at 0.
- marker/colour by testbed; circles = irrigation, triangles = flood.
- The 5 cells below 0.1 % pressure are drawn but not labelled — they overlap. They are named in
  `fig1_data.csv`, which holds every plotted point plus `shift_pp_paired`, `n_governed`,
  `n_ungoverned` and the balance flag, so the figure is auditable without rerunning anything.

---

## 6. Claims the paper should NOT make, on this evidence

- Any dose–response inside the high group (`CLAIM high_group_monotone: no`).
- Enforcement pressure as a predictor separable from testbed (§B: the two splits are identical).
- A corrected effect size for the conformance gain — this script computes none.
- "5 seeds" as a blanket description (§1 above).
- The 877.3 % survival ratio for ministral3:8b (§4).
- `+2.04 pp` for flood ministral3:3b, or any number derived from the committed
  `appraisal_composition.csv` row for that cell, until D1 is fixed upstream.
- **432,083** logged decisions (D2).

## 7. Known limits of this script itself

- It measures **terminal** rejection only. `RESULTS.md` §3 e6 records that flood's *rule-firing*
  dose is 6× to 75× the terminal-rejection figure, so "0.00 % rejected" does **not** mean the
  validators never fired. The paper's phrase must be "terminally rejected", not "rule never fired".
- The flood no-validator arm's threat appraisal is inferred by a keyword classifier with a
  *relaxed* threshold, i.e. the conditioning variable is measured with a **different instrument**
  in the two flood arms (`RESULTS.md` §7 S5). The flood shifts in Table 1 inherit that threat to
  validity. This script cannot detect or correct it; the paper must disclose it.
- Rates are pooled over runs within an arm; no per-seed confidence interval or paired test is
  computed here. Inference for the anchor lives in `decomposition/e1_total_effect.py`.
- `_loader.py`'s convention differs from `appraisal_composition.py`'s on blank appraisal rows.
  This script follows the prior-art (skip-blank) convention in §A so the two are comparable, and
  reports the blank counts; §C follows `_loader`'s all-rows convention because that is what
  reproduces the published pair. Both conventions are named at every use.
