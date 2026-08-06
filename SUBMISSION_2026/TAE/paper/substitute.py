#!/usr/bin/env python3
"""
substitute.py -- the mechanism that stops a stale number reaching the page.

Replaces every {{CLAIM:name}} marker in manuscript.md with the value recorded
below, and FAILS (exit 1, nothing written) if:

    (a) a marker appears in manuscript.md with no matching entry in CLAIMS, or
    (b) an entry in CLAIMS is never referenced by any marker in manuscript.md.

Both directions matter: (a) catches a typo'd or newly-added marker that
nobody has sourced yet; (b) catches a stale claim left behind after a section
was rewritten, which is exactly the "reaches the page anyway" failure mode
this file exists to prevent.

CLAIMS is a hand-maintained transcription of TAE/NUMBERS.md, not a markdown
parser over it -- NUMBERS.md is prose-and-tables for a human red-team, not a
machine format, so each entry below carries an explicit `source` string
pointing at the exact NUMBERS.md row/section it was copied from. Keeping this
dict in sync with NUMBERS.md when the evidence pipeline's numbers move is a
manual step, same as PLAN.md's "NUMBER FREEZE" day (4 Aug) already assumes.

This script never invents, rounds, or "corrects" a value -- see the one
flagged entry below (world_conditioned_pct) for the one case in this set that
is an arithmetic derivation rather than a value copied verbatim from a single
NUMBERS.md row, and why that is still honest.

Usage:
    python substitute.py                  # writes manuscript.substituted.md
    python substitute.py --check           # validation only, writes nothing
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANUSCRIPT_MD = HERE / "manuscript.md"
OUT_SUBSTITUTED = HERE / "manuscript.substituted.md"

CLAIM_RE = re.compile(r"\{\{CLAIM:([a-zA-Z0-9_]+)\}\}")

# ---------------------------------------------------------------------------
# CLAIMS -- one entry per {{CLAIM:name}} marker used in manuscript.md.
# `value`  : the exact text that replaces the marker.
# `source` : NUMBERS.md section + the distinguishing stdout fragment it is
#            transcribed from (NUMBERS.md's own "locator convention").
# ---------------------------------------------------------------------------

CLAIMS: dict[str, dict[str, str]] = {
    # -- Section 6 closing: the uniform-random null (e5_uniform_null.py) -------
    # These were hand-typed until 2026-08-01, when e5 was written so they have a
    # producing script. The null is DERIVED from skill_registry.yaml, not assumed.
    "uniform_null": {
        "value": "40%",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `uniform-random null | 40% (derived from the registry, not assumed)`",
    },
    "action_set_shape": {
        "value": "five skills, two of them increases",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `action set composition | 5 skills, 2 of them increases`",
    },
    "nov_null_t": {
        "value": "t = 42.66, df = 4",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `no-validator t against the null | +42.658 (df = 4)`",
    },
    "nov_null_ci": {
        "value": "61.06 to 63.99",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `no-validator 95% CI | [61.06, 63.99], EXCLUDES the null`",
    },
    "gov_null_t": {
        "value": "t = 0.46, df = 4",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `with-validators t against the null | +0.457 (df = 4)`",
    },
    "gov_null_ci": {
        "value": "35.45 to 46.35",
        "source": "NUMBERS.md section 14 (the uniform-random null table), row `with-validators 95% CI | [35.45, 46.35], CONTAINS the null`",
    },


    # -- Section 2 (Setup) ---------------------------------------------------
    "decisions_per_run": {
        "value": "3,276",
        "source": "NUMBERS.md §9 · `decisions per run | 3,276 = 78 agents × 42 years, "
                   "every irrigation run, both arms`",
    },
    "anchor_arm_n": {
        "value": "16,380",
        "source": "NUMBERS.md §9 · `anchor decisions per arm | 5 × 3,276 = 16,380`",
    },
    "retry_budget": {
        "value": "three",
        "source": "NUMBERS.md §5a, retry-structure table · `retry budget, read from the data | 3 "
                   "(max retry_count)`, e1_first_attempt_limits.py section 1 · "
                   "`retry budget observed (max retry_count) : [3]`",
    },
    "n_model_configs": {
        "value": "nine",
        "source": "DERIVED count, not a printed NUMBERS.md row: the nine distinct model names the "
                   "corpus contains, read off NUMBERS.md §8's sign-split row (gemma3:4b, gemma3:12b, "
                   "gemma3:27b, ministral3:3b, ministral3:8b, ministral3:14b, gemma4:e2b, gemma4:e4b, "
                   "gemma4:26b -- the nine flood cells) of which the five in NUMBERS.md §3's "
                   "per-model irrigation table are a subset. 9 configurations x 2 testbeds where both "
                   "were run = the fourteen model x testbed cells §4 reports. Same honesty flag as "
                   "world_conditioned_pct: no single line prints the number nine.",
    },
    # NOTE: the family count and parameter-size span live in "model_scope" further
    # down (added by the section-8 pass, same DERIVED honesty flag). Section 2 uses
    # that entry rather than defining a second near-duplicate of it.
    "n_seeds": {
        "value": "five",
        "source": "NUMBERS.md §2 (`gemma3:4b, irrigation, 5 paired seeds`), §3 per-model table `n` "
                   "column (5 for gemma3:4b, gemma4:e2b, gemma4:e4b) and §8's flood rows (5). The "
                   "prose that uses this marker says 'in most cells and fewer in two irrigation "
                   "cells' because the same §3 table gives gemma3:12b n = 3 and ministral3:8b n = 3 "
                   "paired. Both are still fewer than five, so the prose is unchanged.",
    },
    "irrigation_action_count": {
        "value": "five",
        "source": "CONFIG FACT, not a computed statistic -- the category NUMBERS.md §11 uses for "
                   "skill_registry.yaml reads ('it is a config fact, not a computed statistic'). "
                   "examples/irrigation_abm/config/skill_registry.yaml lists five skill_ids "
                   "(increase_large, increase_small, maintain_demand, decrease_small, "
                   "decrease_large) and default_skill: maintain_demand, which is the domain default "
                   "the same sentence-group refers to. NUMBERS.md §1's structural-fact paragraph "
                   "reads the same file for the increase_large/increase_small precondition. Section 6 "
                   "of the manuscript states the same five-skill composition and carries its own "
                   "sourcing flag for it.",
    },
    "flood_action_count": {
        "value": "four",
        "source": "CONFIG FACT, same category as irrigation_action_count above and not a NUMBERS.md "
                   "row: examples/single_agent/skill_registry.yaml lists four skill_ids "
                   "(buy_insurance, elevate_house, relocate, do_nothing) and default_skill: "
                   "do_nothing. NUMBERS.md §8 treats flood as descriptive-only and prints no action "
                   "count.",
    },


    # -- Section 6 (conditional vs unconditional / Figure 3) -----------------
    # Every value below is transcribed from the NUMBERS.md per-model table, whose own
    # locator column points at `table1_cells.py` section B, one line per model. The
    # `_bare` names are the same numbers without their CI, for use in running prose
    # where the interval is given separately or is not the point of the sentence.
    "anchor_cond_delta_bare": {
        "value": "+23.02 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:4b, `cond delta` column",
    },
    "anchor_uncond_delta_bare": {
        "value": "+21.62 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:4b, `unc delta` column",
    },
    "anchor_uncond_gov": {
        "value": "40.90%",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:4b, `unc gov` column",
    },
    "anchor_uncond_nov": {
        "value": "62.52%",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:4b, `unc nov` column",
    },
    "anchor_gap": {
        "value": "1.39 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:4b: 23.02 - 21.62, the amount the conditional reading "
                  "overstates the anchor contrast. Arithmetic on two tabled values, not a "
                  "separate measurement.",
    },
    "b12_cond_delta_bare": {
        "value": "+11.44 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma3:12b, `cond delta` column (n = 3 seeds, df = 2)",
    },
    # b12_uncond_delta_bare REMOVED 2026-08-02, reader-guidance pass. Section 6 used to give
    # gemma3:12b's pair of deltas twice, bare in the "widen from there" list and again with
    # intervals in the paragraph that follows. The bare pair went; the value itself is unchanged
    # and still on the page, as b12_uncond_delta (with its CI) in section 6 and in the abstract.
    "b12_uncond_exec_delta": {
        "value": "+27.82 pp (p = 0.004)",
        "source": "NUMBERS.md reading-specific table (`cond delta LAST-PROPOSED | cond delta "
                  "EXECUTED | unc delta LAST-PROPOSED | unc delta EXECUTED`), gemma3:12b row, "
                  "`unc delta EXECUTED` column. This is why the near-zero result is specific to "
                  "the published last-proposed reading and must be scoped as such.",
    },
    "e2b_cond_delta": {
        "value": "+18.94 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma4:e2b, `cond delta` column",
    },
    "e2b_uncond_delta": {
        "value": "+15.25 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma4:e2b, `unc delta` column",
    },
    "e4b_cond_delta": {
        "value": "+17.41 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma4:e4b, `cond delta` column",
    },
    "e4b_uncond_delta": {
        "value": "+8.52 pp",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row gemma4:e4b, `unc delta` column",
    },
    "ministral_cond_delta": {
        "value": "+2.80 pp (95% CI +0.02, +5.58; p = 0.049)",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row ministral3:8b, `cond delta` column, and the CI/p columns "
                  "beside it. Paired on 3 seeds (42, 43, 44), df = 2. The cell was excluded from "
                  "paired contrasts until 2026-08-03, when its no-validator seed 44 run balanced "
                  "it. The interval is 5.56 pp wide around a 2.80 pp estimate and its lower bound "
                  "is +0.0246, so this clears zero by less than the increment everything else is "
                  "printed at; the manuscript states the width rather than calling it significant.",
    },
    "ministral_uncond_delta": {
        "value": "−22.17 pp (95% CI −29.02, −15.32; p = 0.005)",
        "source": "NUMBERS.md per-model table (the `cond gov | cond nov | cond delta | unc gov | unc nov | unc delta` table) row ministral3:8b, `unc delta` column, and the CI/p columns beside it. "
                  "Paired on 3 seeds (42, 43, 44), df = 2. The sign is opposite to every other "
                  "irrigation cell. That was previously attributed to comparing unequal seed "
                  "counts; balancing the cell on 2026-08-03 FALSIFIED that explanation -- the "
                  "reversal survived and grew, from −21.12 to −22.17, and all three per-seed "
                  "deltas share the sign (−19.05, −23.20, −24.27).",
    },
    # -- Section 3 (the two rule layers separate / Figure 1) ----------------
    "novrej_pct": {
        "value": "29.0%",
        "source": "NUMBERS.md §1 · `no-validator rejections | 4,757 / 16,380 = 29.0%`",
    },
    "novrej_increase_pct": {
        "value": "99.95%",
        "source": "NUMBERS.md §1 · `no-validator rejections that are increase proposals | "
                   "6,187 / 6,190 = 99.95%` (6,168 / 6,171 before ministral3:8b's third "
                   "no-validator seed joined the pool on 2026-08-03; the rate is unchanged)",
    },
    "govrej_pct": {
        "value": "39.5%",
        "source": "NUMBERS.md §1 · `with-validators rejections | 6,469 / 16,380 = 39.5%`",
    },
    "appraisal_conditioned_pct": {
        "value": "59.4%",
        "source": "NUMBERS.md §1 · `behavioural rejections whose antecedent is the "
                   "self-reported appraisal | 3,840 of 6,469 = 59.4%`",
    },
    "world_conditioned_pct": {
        "value": "40.6%",
        "source": "DERIVED, not a direct NUMBERS.md row: 6,469 − 3,840 = 2,629; "
                   "2,629 / 6,469 = 40.6% (arithmetic complement of the appraisal_conditioned_pct "
                   "row above). Stated directly, not just derivable, in DECISION.md §7 "
                   "('2,629 (40.6%) name only world-conditioned validator rules') and in the "
                   "2026-07-31 corrections block. Flagged here per this script's own honesty "
                   "requirement -- NUMBERS.md §1 does not print 2,629 or 40.6% on their own line.",
    },
    "rule_purity": {
        "value": "10/10",
        "source": "NUMBERS.md §1 · `purity of the split across all irrigation cells | "
                   "10 / 10 cells pure, zero exceptions`",
    },
    "novrej_count": {
        "value": "4,757",
        "source": "NUMBERS.md §1 · `no-validator rejections | 4,757 / 16,380 = 29.0%`",
    },
    "govrej_count": {
        "value": "6,469",
        "source": "NUMBERS.md §1 · `with-validators rejections | 6,469 / 16,380 = 39.5%`",
    },
    "govrej_range": {
        "value": "28.1% to 62.6%",
        "source": "NUMBERS.md §1 · `rejection rate range, with validators | 28.1 - 62.6%` "
                   "(POOLED-COUNT basis, fig1_rule_layers.py PANEL B `rej%` column)",
    },
    "novrej_range": {
        "value": "0.9% to 29.0%",
        "source": "NUMBERS.md §1 · `rejection rate range, no validator | 0.9 - 29.0%` "
                   "(POOLED-COUNT basis, fig1_rule_layers.py PANEL B `rej%` column)",
    },
    "novrej_range_excl_anchor": {
        "value": "0.9% to 5.3%",
        "source": "NUMBERS.md §1, per-model breakdown table added under the rejection-rate-range row "
                   "-- min/max of the four non-anchor no-validator rows (ministral3:8b 0.9%, "
                   "gemma3:12b 5.3%), fig1_rule_layers.py PANEL B, cross-checked against "
                   "figures/fig1_rule_layers.csv panel b (gemma3:12b no-validator row: 524/9,828 "
                   "= 5.3317%, rounds to 5.3%)",
    },
    "atcap_noval_pct": {
        "value": "43.21%",
        "source": "NUMBERS.md §1 · `agent-years sitting at >=99% of the water right, no-validator "
                   "anchor | 43.21%`",
    },
    "atcap_gov_pct": {
        "value": "0.04%",
        "source": "NUMBERS.md §1 · `...with validators | 0.04%`",
    },
    "govrej_increase_pct": {
        "value": "67.87%",
        "source": "NUMBERS.md §1 · `with-validator rejections that are increase proposals | "
                   "21,251 / 31,313 = 67.87%`",
    },
    "govrej_decrease_pct": {
        "value": "31.8%",
        "source": "NUMBERS.md §1 · `...so the behavioural layer also blocks decreases | "
                   "9,953 / 31,313 = 31.8%` -- DERIVED (100% - 67.87%, on the same 31,313 "
                   "denominator), flagged in NUMBERS.md itself as not printed on its own line, same "
                   "honesty flag as world_conditioned_pct above.",
    },

    # -- Section 4 (the conditioning variable moves / anchor cell) ----------
    "anchor_high_gov": {
        "value": "37.08",
        "source": "NUMBERS.md §2 · `HIGH-appraisal prevalence, with validators | 37.08`",
    },
    "anchor_high_nov": {
        "value": "82.80",
        "source": "NUMBERS.md §2 · `HIGH-appraisal prevalence, no validator | 82.80`",
    },
    "anchor_high_delta": {
        "value": "+45.73 pp (95% CI +40.24, +51.21; p < 0.001)",
        "source": "NUMBERS.md §2 · `HIGH-appraisal prevalence Delta | +45.73 (95% CI +40.24, "
                   "+51.21; p < 0.001)`",
    },
    "anchor_cond_gov": {
        "value": "36.05",
        "source": "NUMBERS.md §2 · `conditional rate, with validators | 36.05`",
    },
    "anchor_cond_nov": {
        "value": "59.07",
        "source": "NUMBERS.md §2 · `conditional rate, no validator | 59.07`",
    },
    "anchor_cond_delta": {
        "value": "+23.02 pp (95% CI +19.06, +26.98; p = 0.0001)",
        "source": "NUMBERS.md §2 · `conditional Delta | +23.02 (95% CI +19.06, +26.98; "
                   "p = 0.0001)`",
    },

    # -- Section 2/4 (the antecedent is a CONJUNCTION -- e6_antecedent_conjunction.py) --
    # Added 2026-08-02. The rule high_threat_high_cope_no_increase fires on
    # WSA_LABEL in {H,VH} AND ACA_LABEL in {H,VH}; every other prevalence number in
    # this file is the scarcity conjunct alone, a strict SUPERSET of that antecedent.
    # The scarcity marginal remains the paper's PRIMARY quantity (it is the one the
    # published statistics on this corpus condition on), and these entries put the
    # coping conjunct and the conjunction beside it. No entry here may be described
    # in the manuscript as "the antecedent" unless it is the conjunction.
    "anchor_cope_gov": {
        "value": "70.66",
        "source": "NUMBERS.md §15, conjunction table · row `coping marginal, ACA in {H,VH}`, "
                  "`prevalence, governed` column; e6_antecedent_conjunction.py · "
                  "`coping marginal    ACA in {H,VH}              70.66%    83.06%   +12.41`",
    },
    "anchor_cope_nov": {
        "value": "83.06",
        "source": "NUMBERS.md §15, conjunction table · row `coping marginal, ACA in {H,VH}`, "
                  "`prevalence, no-validator` column; e6 · same stdout line, second percentage.",
    },
    "anchor_cope_delta": {
        "value": "+12.41 pp (95% CI +9.78, +15.03)",
        "source": "NUMBERS.md §15, CLAIM table · row `the coping conjunct moves, and is not a fixed "
                  "covariate | +12.41 pp (95% CI +9.78, +15.03)`; e6 · `CLAIM both_conjuncts_move:` "
                  "block, `coping conjunct shifts +12.41 pp (95% CI +9.78, +15.03)`. Paired t "
                  "interval over the five anchor seeds, df = 4.",
    },
    "anchor_conj_gov": {
        "value": "25.46",
        "source": "NUMBERS.md §15, conjunction table · row `R4 antecedent, both conjuncts high`, "
                  "`prevalence, governed` column; e6 · "
                  "`R4 antecedent      WSA and ACA both high      25.46%    68.61%   +43.15`",
    },
    "anchor_conj_nov": {
        "value": "68.61",
        "source": "NUMBERS.md §15, conjunction table · row `R4 antecedent, both conjuncts high`, "
                  "`prevalence, no-validator` column; e6 · same stdout line, second percentage.",
    },
    "anchor_conj_delta": {
        "value": "+43.15 pp (95% CI +39.06, +47.24)",
        "source": "NUMBERS.md §15, CLAIM table · row `the conjunction's own prevalence shift | "
                  "+43.15 pp (95% CI +39.06, +47.24)`; e6 · `CLAIM conjunction_shift: R4's actual "
                  "antecedent shifts +43.15 pp (95% CI +39.06, +47.24)`.",
    },
    # anchor_conj_delta_bare REMOVED 2026-08-03. It existed only to carry the
    # conjunction's shift into the abstract without its interval. The abstract now
    # names one construct rather than two -- a reviewer reported both numbers as
    # undefined-on-first-read -- so the entry had no remaining use and would have
    # tripped the unused-claim guard. anchor_conj_delta, with the interval, still
    # carries the same value in section 4 where the conjunction is actually defined.
    "anchor_conj_rate_gap": {
        "value": "+19.86 pp",
        "source": "NUMBERS.md §15, conjunction table · row `R4 antecedent, both conjuncts high`, "
                  "`rate gap` column; e6 · same stdout line, final column `+19.86`, and the "
                  "`CLAIM conjunction_shift:` block's second line, `the increase rate on it differs "
                  "by +19.86 pp between arms`.",
    },
    "anchor_r2_delta": {
        "value": "−3.27 pp",
        "source": "NUMBERS.md §15, conjunction table · row `R2 antecedent, WSA == VL`, `shift` "
                  "column; e6 · `R2 antecedent      WSA == VL                   3.36%     0.09%    "
                  "-3.27`. No CI is printed for this row and none is quoted in the manuscript.",
    },

    "irrigation_high_delta_range": {
        "value": "+21.27 pp to +47.53 pp",
        "source": "NUMBERS.md §3, HIGH-appraisal prevalence per irrigation cell table -- min "
                   "gemma3:12b (+21.27), max gemma4:e2b (+47.53); ministral3:8b's +31.13 falls "
                   "inside this range and does not change either bound.",
    },
    "flood_high_delta_range": {
        "value": "−3.66 to +6.24",
        "source": "NUMBERS.md §8 · `flood HIGH-prevalence Deltas | -3.66 to +6.24, mostly null`",
    },
    "flood_positive_count": {
        "value": "five of the nine",
        "source": "NUMBERS.md §8, new row added under the flood significance row: `sign split "
                   "across the nine flood Deltas | 5 of 9 positive, 4 of 9 negative`, "
                   "table1_cells.py §A Delta column, flood rows.",
    },
    "flood_sig_cell": {
        "value": "+2.92 pp (95% CI +0.71, +5.12; p = 0.021)",
        "source": "NUMBERS.md §8 · `...only one reaches p<0.05 | gemma4:26b, +2.92 (95% CI +0.71, "
                   "+5.12; p = 0.021)`",
    },
    "gov_rej_range_irrigation_perseed": {
        "value": "28.09% to 62.63%",
        "source": "NUMBERS.md §8, new row added after the flood sign-split row: `governed "
                   "enforcement-pressure range, irrigation, PER-SEED-MEAN basis | 28.09 - 62.63%`, "
                   "table1_cells.py §A press.gov column. The max is ministral3:8b, which joined the "
                   "paired basis on 2026-08-03 and moved the bound from 62.19 to 62.63. NOT the same "
                   "basis as govrej_range above (that one is fig1_rule_layers.py's POOLED-COUNT "
                   "28.1-62.6%) -- the two are close but not identical and must not be swapped.",
    },
    "flood_pressure_range": {
        "value": "0.00% to 1.07%",
        "source": "NUMBERS.md §8 · `enforcement pressure, governed arm | 0.00 - 1.07% across 9 "
                   "models`",
    },
    "flood_pressure_noval": {
        "value": "0.00%",
        "source": "NUMBERS.md §8 · `enforcement pressure, no-validator arm | exactly 0.00% in every "
                   "flood cell`",
    },

    # -- Section 5 (why it moves / Figure 2) ---------------------------------
    "year1_retried_pct": {
        "value": "82.1%",
        "source": "NUMBERS.md §4 · `anchor, retried (retry_count > 0) | 79.5-84.6%, mean 82.1%`",
    },
    "year1_exhausted_pct": {
        "value": "70.5%",
        "source": "NUMBERS.md §4 · `anchor, EXHAUSTED the budget (retry_count == 3) | "
                   "69.2-74.4%, mean 70.5%`. BOTH this and year1_retried_pct are computed over the "
                   "GOVERNED arm only (fig2_mechanism.py:year1_retry_pressure() iterates "
                   "D.irrigation_run(\"gov\", ...)), so the prose denominator must read 'governed "
                   "year-1 decisions', never 'all year-1 decisions'.",
    },
    "allyears_retried_pct": {
        "value": "63.8%",
        "source": "NUMBERS.md §5a, retry-structure table · `retried at least once (retry_count > 0), "
                   "all years | ... pooled 10,450 / 16,380 = 63.8%`, e1_first_attempt_limits.py "
                   "section 1 pooled line. Governed anchor arm, all 42 years -- the comparison "
                   "denominator for the year-1 82.1% figure, which NUMBERS.md §5a itself insists be "
                   "labelled as a different stratum.",
    },
    "postyear1_reversals": {
        "value": "two of the 41 later years run significantly the other way, year 4 at −18.46 pp "
                 "(p = 0.004) and year 7 at −6.41 pp (p = 0.001)",
        "source": "figures/fig2_mechanism.csv, panel A rows x=4 and x=7 "
                  "(`A,delta_high_appraisal_prevalence,4,-18.4615,...,p=0.0040` and "
                  "`A,delta_high_appraisal_prevalence,7,-6.4103,...,p=0.0008`), drawn and annotated "
                  "on Figure 2 panel A itself. Covered in NUMBERS.md §4b only by the generic `all 42 "
                  "per-year Deltas | 42 rows` row; a per-year row for these two was added there on "
                  "2026-08-02 because the manuscript now names them. p = 0.001 is 0.0008 at the "
                  "figure's own 3 dp, which is what the annotation prints.",
    },
    "world_residual_coarse": {
        "value": "−2.53 pp",
        "source": "NUMBERS.md §13 · `residual after holding the world fixed, coarse (100% "
                   "coverage) | -2.53 pp`",
    },
    "world_coverage_coarse": {
        "value": "100%",
        "source": "NUMBERS.md §13, same row, `(100% coverage)` in the claim text and the full "
                   "ladder table's `shortage tier` row, `coverage` column, `100.0%`",
    },
    "world_residual_finest": {
        "value": "+0.21 pp",
        "source": "NUMBERS.md §13 · `residual, finest (43.4% coverage) | +0.21 pp`",
    },
    "world_coverage_finest": {
        "value": "43.4%",
        "source": "NUMBERS.md §13, same row, `(43.4% coverage)` in the claim text and the full "
                   "ladder table's last row, `coverage` column, `43.4%`",
    },
    # -- Table 2's new statistical furniture (e4 PART 2a/2b, added 2026-08-02) --
    # The third reviewer's objection was that Table 2 carried residuals with no n,
    # no named weighting scheme and no interval, against a raw gap that has one.
    # These two markers carry the parts of the answer that live in prose; the
    # counts, coverages and intervals themselves are cells of the table.
    "world_min_cell_finest": {
        "value": "67",
        "source": "NUMBERS.md §13a, per-arm cell-count table, `tier + Mead + drought + agent "
                   "cluster` row -- min is 67 in BOTH arms (`67 / 335 / 1,005` governed, "
                   "`67 / 201 / 1,139` no-validator). e4 PART 2a, that row's "
                   "`n|gov min/med/max` and `n|noval min/med/max` columns.",
    },
    "world_weighting_swing": {
        "value": "0.78 pp",
        "source": "NUMBERS.md §13a · `largest move caused by switching the standard | 0.78 pp, on "
                   "the finest rung`, e4 PART 2b `CLAIM world_fixed_weighting_sensitivity:` and the "
                   "line under it. The largest gap between the published pooled-weight residual and "
                   "the same rung standardised on either arm's own distribution, over all five rungs.",
    },
    "world_residual_max": {
        "value": "4.47 pp",
        "source": "NUMBERS.md §13 · `largest residual at any resolution | 4.47 pp, against a raw "
                   "shift of 45.73` -- this is the `tier + Mead elevation (25 ft)` row of the full "
                   "ladder table, not the coarse or finest row.",
    },
    "tier0_gov_share": {
        "value": "64.8%",
        "source": "NUMBERS.md §13 · `governed arm share of decisions in tier 0 (no shortage) | "
                   "64.8% (10,608 / 16,380)`",
    },
    "tier3_noval_share": {
        "value": "76.7%",
        "source": "NUMBERS.md §13 · `no-validator arm share in tier 3 (severe shortage) | 76.7% "
                   "(12,558 / 16,380)`",
    },
    "year1_matched_pairs": {
        "value": "390",
        "source": "NUMBERS.md §4a · `year-1 pairs, anchor cell alone | 390 (5 seeds x 78 agents)`",
    },
    "year1_divergence_year": {
        "value": "2",
        "source": "NUMBERS.md §4a · `first year at which any pre-decision column disagrees | 2, "
                   "in all five cells`",
    },
    "pooled_neverretried_delta": {
        "value": "+48.21 pp",
        "source": "NUMBERS.md §5, pooled row of the never-retried-stratum table · `pooled  21  "
                   "26.68  66.69  +40.02  17.01  65.23  +48.21  +8.20` (never-retried Delta column, "
                   "21 paired seeds -- 20 until ministral3:8b's third pair landed 2026-08-03)",
    },
    "pooled_alldecisions_delta": {
        "value": "+40.02 pp",
        "source": "NUMBERS.md §5, same pooled row (all-decisions Delta column) and §12. The "
                   "2026-08-01 adjudication against the brief's +40.40 stands; the value moved "
                   "from +40.45 to +40.02 on 2026-08-03 because the pool grew from 20 paired "
                   "(cell, seed) units to 21, not because the basis changed.",
    },
    "anchor_high_delta_bare": {
        "value": "+45.73 pp",
        "source": "NUMBERS.md §2 · `HIGH-appraisal prevalence Delta | +45.73 (95% CI +40.24, "
                   "+51.21; p < 0.001)`, bare figure without the CI/p for use where the interval is "
                   "not being restated (e.g. inside a sentence that already carries its own "
                   "residual figures). Same value as anchor_high_delta, formatted without the "
                   "parenthetical.",
    },
    "year1_high_delta": {
        "value": "+3.33 pp (95% CI −3.75, +10.42; p = 0.261)",
        "source": "NUMBERS.md §4b · `HIGH-appraisal prevalence Delta | +3.33 (95% CI -3.75, "
                   "+10.42; p = 0.261) -- null`",
    },
    "year1_high_delta_bare": {
        "value": "+3.33 pp (p = 0.261)",
        "source": "NUMBERS.md §4b · `HIGH-appraisal prevalence Delta | +3.33 (95% CI -3.75, "
                   "+10.42; p = 0.261) -- null`, bare figure (point estimate + p only, no CI) for "
                   "the figure caption's tighter space. Same value as year1_high_delta.",
    },
    "neverretried_larger_cells": {
        "value": "5 of 5",
        "source": "NUMBERS.md §5 · `OK  never-retried Delta LARGER in k of 5 cells   got  +5  "
                   "brief  +5`",
    },
    "neverretried_delta_anchor": {
        "value": "+53.46 pp",
        "source": "NUMBERS.md §5, per-cell table · `gemma3:4b  5  37.08  82.80  +45.73  23.96  "
                   "77.43  +53.46  +7.74` (never-retried Δ column)",
    },
    "neverretried_share_gov": {
        "value": "36.2%",
        "source": "NUMBERS.md §5, 'Stratum asymmetry' paragraph · `the never-retried stratum "
                   "covers a far larger share of the no-validator arm than of the governed arm -- "
                   "anchor 36.2% / 64.6%`, fig2_mechanism.py PANEL C, `NR share gov/nov` column.",
    },
    "neverretried_share_noval": {
        "value": "64.6%",
        "source": "NUMBERS.md §5, same 'Stratum asymmetry' paragraph and column, the no-validator "
                   "half of the anchor 36.2% / 64.6% pair.",
    },
    "reservoir_final_gap": {
        "value": "+106.57 ft",
        "source": "NUMBERS.md §6 · `final-year gap | +106.57 ft`",
    },
    "reservoir_mean_gap": {
        "value": "+102.25 ft",
        "source": "NUMBERS.md §6 · `42-year mean gap | +102.25 ft`",
    },
    "noval_floor_years": {
        "value": "17–18",
        "source": "NUMBERS.md §6 · `no-validator arm first reaches the 895 ft floor | "
                   "year 17-18, in all 5 seeds`",
    },

    # -- Section 6 (what it does to the statistic / Figure 3) ---------------
    "b12_cond_delta": {
        "value": "+11.44 pp (95% CI +3.19, +19.69; p = 0.027)",
        "source": "NUMBERS.md §3 · `+11.44 conditional (95% CI +3.19, +19.69; p = 0.027) "
                   "becomes +0.16 unconditional...`",
    },
    "b12_uncond_delta": {
        "value": "+0.16 pp (95% CI −13.92, +14.25; p = 0.965)",
        "source": "NUMBERS.md §3 · same line, unconditional figure "
                   "`(-13.92,+14.25)  0.9649`",
    },

    # -- Section 7 (what to do instead / the falsified world-antecedent repair)
    # These three are the tested negative result: swapping the self-reported
    # antecedent for a simulator-written one does NOT give an unmoved
    # conditioning variable. Compared in the prose against anchor_high_delta_bare
    # (+45.73 pp), the self-report's own shift, which is defined above and shared
    # with §5 rather than duplicated here.
    "world_tier2_shift": {
        "value": "+64.29 pp",
        "source": "NUMBERS.md §13, world-antecedents table · `world  shortage_tier >= 2         "
                   "21.43%      85.71%   +64.29   [+64.29, +64.29]` (e4_world_fixed_decomposition.py "
                   "PART 1)",
    },
    "world_tier1_curtail_shift": {
        "value": "+55.71 pp",
        "source": "NUMBERS.md §13, world-antecedents table · `world  shortage_tier >= 1         "
                   "35.24%      90.95%   +55.71   [+48.60, +62.83]` and the identical "
                   "`world  curtailment_ratio > 0      35.24%      90.95%   +55.71` row. The two "
                   "antecedents coincide on this corpus, which is why one value is quoted for both.",
    },
    "world_drought_shift": {
        "value": "+25.71 pp",
        "source": "NUMBERS.md §13, world-antecedents table · `world  drought_index >= 0.5        "
                   "4.76%      30.48%   +25.71   [+16.51, +34.92]` (e4_world_fixed_decomposition.py "
                   "PART 1)",
    },

    # -- Section 8 (limitations) ---------------------------------------------
    "acceptance_selection_pct": {
        "value": "24.3%",
        "source": "NUMBERS.md §5a · `approved after at least one retry -- the selected stratum "
                   "| ... pooled 3,981 / 16,380 = 24.3%`",
    },
    "flood_manifest_disagree": {
        "value": "six of the nine flood models",
        "source": "NUMBERS.md §8, provenance defect 1 · `Flood manifest seeds disagree across arms "
                  "in 6 of 9 models`, _data.py §3 · `gemma3:4b  gov=[42, 4202, 4203, 45, 46] "
                  "noval=[42, 43, 44, 45, 46]   <== MANIFEST SEEDS DISAGREE ACROSS ARMS` and the "
                  "same marker on five further models; `-> flood_runs() keys on the RUN INDEX, not "
                  "the manifest seed.`",
    },
    "flood_coverage_range": {
        "value": "70.5–100.0%",
        "source": "NUMBERS.md §8 · `flood audit-CSV coverage of the 1,000 design-expected "
                   "decisions | 70.5 - 100.0%`",
    },
    "model_scope": {
        "value": "three open-weight model families spanning 3B to 27B",
        "source": "DERIVED, not a direct NUMBERS.md row: a count and a range over the nine model "
                   "configurations NUMBERS.md §8 enumerates by name in its flood sign-split row "
                   "(gemma3:4b, gemma3:12b, gemma3:27b, ministral3:3b, ministral3:8b, "
                   "ministral3:14b, gemma4:e2b, gemma4:e4b, gemma4:26b) -- three families "
                   "(gemma3, gemma4, ministral3), smallest ministral3:3b, largest gemma3:27b. "
                   "Flagged here per this script's own honesty requirement, same as "
                   "world_conditioned_pct: NUMBERS.md prints no single line reading '3B to 27B'. "
                   "This SUPERSEDES DECISION.md §8's stale 'two open-weight families <=27B', "
                   "which undercounts the families against the model list actually analysed.",
    },
}


def marker_names_in(text: str) -> set[str]:
    return set(CLAIM_RE.findall(text))


def main() -> int:
    # Windows consoles are frequently on a legacy codepage (cp950/cp1252)
    # that cannot encode U+2212 MINUS SIGN, U+00A7 SECTION SIGN, etc. -- both
    # of which appear in NUMBERS.md-transcribed values/sources above. Force
    # UTF-8 stdout so a print() never crashes the run after the file has
    # already been written correctly.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass  # stdout without reconfigure() (rare); best-effort only

    check_only = "--check" in sys.argv[1:]

    if not MANUSCRIPT_MD.exists():
        print(f"FAIL: source not found: {MANUSCRIPT_MD}")
        return 1

    text = MANUSCRIPT_MD.read_text(encoding="utf-8")
    used = marker_names_in(text)
    defined = set(CLAIMS.keys())

    missing_definitions = sorted(used - defined)
    unused_claims = sorted(defined - used)

    ok = True

    if missing_definitions:
        ok = False
        print(f"FAIL: {len(missing_definitions)} marker(s) in manuscript.md have no CLAIMS entry:")
        for name in missing_definitions:
            print(f"  - {{{{CLAIM:{name}}}}}  <- add a CLAIMS[\"{name}\"] entry sourced from NUMBERS.md")

    if unused_claims:
        ok = False
        print(f"FAIL: {len(unused_claims)} CLAIMS entr{'y is' if len(unused_claims)==1 else 'ies are'} "
              f"defined but never referenced by manuscript.md:")
        for name in unused_claims:
            print(f"  - \"{name}\"  <- remove it, or add {{{{CLAIM:{name}}}}} where it belongs")

    if not ok:
        print(f"\n{len(used)} distinct markers used, {len(defined)} claims defined, "
              f"{len(used & defined)} matched. Nothing written.")
        return 1

    print(f"OK: {len(used)} markers used, all sourced; {len(defined)} claims defined, all used.")

    if check_only:
        print("(--check: validation only, manuscript.substituted.md not written)")
        return 0

    def replace(m: re.Match) -> str:
        return CLAIMS[m.group(1)]["value"]

    substituted = CLAIM_RE.sub(replace, text)
    OUT_SUBSTITUTED.write_text(substituted, encoding="utf-8")
    print(f"wrote {OUT_SUBSTITUTED}")
    print("\nSubstitutions applied (name -> value, source):")
    for name in sorted(used):
        entry = CLAIMS[name]
        print(f"  {name} -> {entry['value']}")
        print(f"      {entry['source']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
