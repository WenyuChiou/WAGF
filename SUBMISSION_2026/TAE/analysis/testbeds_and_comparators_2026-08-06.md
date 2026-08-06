# Testbeds and comparison arms: Nature Water vs. the ICLR paper

2026-08-06. Read-only audit. Every claim below is traceable to a path and line.

## The answer

The conference paper uses the same two testbeds as Nature Water — **irrigation** (78 farms, 42 years, 5 model configurations) and **flood** (100 households, 10 years, 9 model configurations) — but it uses them for different jobs: irrigation carries the argument, flood is a portability check only, and no flood number appears anywhere in the manuscript (`ICLR2027/submission/paper/manuscript.tex:76`, `:93`). The paper has exactly **two arms, validator-on and validator-off**, stated at `manuscript.tex:78` ("arm $a$ (validator-on or validator-off)") and `:84` ("The contrast is always $\Delta=\text{off}-\text{on}$"). **There is no rule-based comparator, and no non-LLM comparator of any kind**: a grep of `manuscript.tex` for rule-based / rulebased / FQL / fuzzy / Hung / null / uniform / random returns nothing, and the single hit for "baseline" (`:35`) is prose about prior work, not an arm in this paper.

## Side by side

| Paper | Case | Arm | What it is | Corpus |
|---|---|---|---|---|
| **Nature Water** | Irrigation | with validators | LLM, 5 seeds | `examples/irrigation_abm/results/production_v21_42yr_seed42..46/` |
| | | without validators | LLM, 5 seeds | `examples/irrigation_abm/results/ungoverned_v21_42yr_seed42..46/` |
| | | **FQL baseline** | non-LLM fuzzy Q-learning kernel, 10 seeds, run **inside** WAGF with all 12 validators on | `examples/irrigation_abm/results/fql_raw/seed42..51/` (10 dirs verified on disk) |
| | Flood | with validators | LLM, 5 runs | `examples/single_agent/results/JOH_FINAL/gemma3_4b/Group_C/Run_1..5/` |
| | | without validators | LLM, 5 runs | `.../JOH_ABLATION_DISABLED/gemma3_4b/Group_C_disabled/Run_1..5/` |
| | | **rule-based PMT** | non-LLM softmax utility agent, no validators, 3 runs | `examples/single_agent/results/rulebased/Run_1..3/` (3 dirs verified) |
| **ICLR 2027** | Irrigation (primary) | with validators | LLM, 5 model cells, 5 seeds each (2 cells use 3) | `IRRIGATION_MODELS`, `SUBMISSION_2026/TAE/evidence/_data.py:188-194`; dir token `production`, `:164` |
| | | without validators | same 5 cells, seed-paired | same allow-list; dir token `ungoverned`, `:164` |
| | | *third arm* | **none** | — |
| | Flood (portability only) | with validators | LLM, 9 model cells | `FLOOD_MODELS`, `_data.py:215-225`; group `Group_C`, `:168` |
| | | without validators | same 9 cells | group `Group_C_disabled`, `:168` |
| | | *third arm* | **none** | — |

The gap is the two "none" rows. Nature Water has a third, non-LLM arm in both cases; the conference paper has none in either. This is enforced, not accidental: `_data.py:173-176` raises on any arm name other than `gov`/`noval`, and the two audit scripts under `SUBMISSION_2026/audit/` list `rulebased` in their *exclusion* tuples alongside `Group_A` and the quarantine dirs (`audit_claim_traceability.py:64`, `audit_synthesis_checks.py:5`). Nothing in `SUBMISSION_2026/TAE/evidence/` reads the rule-based corpus at all.

## Is the recollection right?

Half right, and the half that is wrong matters.

Nature Water does give **both** cases a third non-LLM arm, so the shape of the memory is correct. But only the **flood** arm is genuinely rule-based: a standalone softmax-utility agent, no validators, described at `paper/nature_water/drafts/methods_v7.md:83` ("Establishes the traditional ABM baseline") and reported in Extended Data Table 2 (`section2_v19_results.md:77`).

The **irrigation** arm is a different animal. It is the Fuzzy Q-Learning kernel of Hung and Yang, i.e. a reinforcement-learning agent, and it is run **through WAGF with all twelve validators switched on** (`examples/irrigation_abm/run_fql_baseline.py:7-8`, "same 12 governance validators"; the shipped logs carry an `fql_blocked` column, confirming enforcement was active). It is therefore not a rule-based baseline and not an ungoverned one. The paper's own Extended Data Table 1 footnote says so plainly: inconsistency and diversity "are not computed because 84–89% of FQL actions were rejected by governance" (`section2_v19_results.md:39`).

The likely source of the recollection is one stale word: the Discussion calls it "a conservative rule-based baseline" (`section3_v17_discussion.md:31`), and the runner's own docstring repeats it (`run_fql_baseline.py:10`). The Results section and the table use the correct label, "Fuzzy Q-Learning (FQL) baseline" (`section2_v19_results.md:23`, `:29`).

Why the distinction matters: a reviewer told "each case is anchored to a rule-based baseline" will read the two arms as parallel. They are not. One is an outside-the-framework traditional ABM with a full metric row; the other is a dumb kernel inside the framework whose two behavioural metrics are blank by admission.

## Should the ICLR paper add a rule-based arm?

**No. Recommend against, and the reason is definitional, not practical.**

The paper's headline number is a rate whose denominator is written by the agent itself — the share of decisions in which the agent *reported* high scarcity (`manuscript.tex:78`, and `_data.py:715-724`: "The denominator is post-treatment. That is the defect under study, not a bug"). A non-LLM policy files no such report. The rule-based flood log has nine columns and none of them is an appraisal (`agent_id, year, decision, flooded_this_year, elevated, has_insurance, relocated, trust_in_insurance, trust_in_neighbors`); the appraisal reader at `_data.py:585-589` recognises only `wsa_label`, `construct_WSA_LABEL`, `construct_TP_LABEL`, and would raise on every row. The Nature Water analysis hit the same wall and wrote it down: `examples/single_agent/analysis/compute_flood_metrics.py:172-173`, `# No threat_appraisal in rulebased` / `ibr_val = float("nan")`.

So the comparator is not merely missing. **It is undefined.** The rule-based agent does not have a biased denominator on the axis under study; it has no denominator. To place it in the table you would have to invent an appraisal from state variables — an analyst-authored, exogenous label, which is the opposite construct from the self-reported, post-treatment one the paper is about. It would also quietly imply a fix ("just use an external appraisal") that the paper's own argument says the trace cannot supply. A sharp reviewer would read that as the paper undercutting itself.

There is a cheap and honest alternative: **one sentence of prose**, no new data. Something to the effect that a non-LLM policy produces no self-reported condition and therefore cannot be scored on this metric at all — which is itself evidence for the paper's thesis that the metric depends on the governed process writing its own denominator. That converts the absence from a hole into a point.

Two smaller notes if the author wants them. First, the paper's predecessor draft did carry one non-LLM reference point — a 40% uniform-random null derived from the skill registry (`SUBMISSION_2026/TAE/evidence/e5_uniform_null.py:98-107`, reported at `SUBMISSION_2026/TAE/paper/manuscript.md:322-328`) — and the ICLR draft dropped it. That one *is* definable, because it applies to the design-fixed unconditional denominator rather than the agent-written one. Reinstating it costs nothing; the code still runs. Second, even if one wanted the flood rule-based arm, it would not survive scrutiny: 3 runs against 5, no reproducibility manifest, and its action labels are reconstructed from year-to-year state changes rather than recorded (`compute_flood_metrics.py:110-154`).

## What I could not establish

- **Whether the ICLR authors ever considered and rejected a rule-based arm.** The exclusion is enforced in code, but no design note states the reasoning. `SUBMISSION_2026/TAE/analysis/cleanup_2026-08-05.md:398` only records that the corpus's consumers were not audited.
- **Whether the flood rule-based runs are reproducible.** `Run_1` reproduces at seed 42; `Run_2` and `Run_3` match no seed tested, and there is no manifest. Their provenance is unrecoverable from the repo as it stands. This is a Nature Water exposure, not an ICLR one.
- **Whether the Nature Water Methods description of the rule-based agent is accurate.** Methods says it uses threat and coping appraisal derived from flood zone and income (`methods_v7.md:95`); the generator's header says "no PMT terms" (`examples/single_agent/run_flood_rulebased.py:3`) and the profile CSV has neither zone nor income. The *parameters* in Supplementary Note 9 do match the code. Flagged, not resolved — it needs a decision from the author, not an audit.
