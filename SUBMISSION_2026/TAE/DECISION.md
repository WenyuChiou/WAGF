# 定案 — TAE submission, 8 pages, deadline 29 Aug 2026 AoE

> ## ⚠ VENUE WITHDRAWN — 2026-08-05. THIS DECISION NO LONGER HOLDS.
>
> **The TAE workshop route is closed.** Per `HANDOVER.md` (written 2026-08-05 22:25): the
> organisers withdrew the workshop on 2026-08-05 over an AGU date-line conflict, and
> `HANDOVER.md:1-30` records that "the TAE route is closed, and it is not negotiable". The
> main-conference route is explicitly cleared by the organisers (`HANDOVER.md:37`).
>
> **The 29 August 2026 deadline in the heading and throughout this file is dead.** Everything
> below is kept unedited because it is the correct record of a real decision taken on
> 2026-08-03 — do not rewrite it.
>
> **No destination is confirmed.** The leading candidate is ICLR 2027 main track (deadline
> 25 September 2026 AoE, 9 pages, unlimited appendix, double-blind), verified from `iclr.cc`
> on 2026-08-05 — but `HANDOVER.md:55-57` states the venue assessment's conclusion "is not
> recorded in this repository yet", and **whoever confirms the destination must write it into
> this file**. Until then, no file in this project records where the paper is going.
>
> Two things depend on the answer and are blocked on it:
> `paper/submission_gate.py:127-129, 835-864` still validates the TAE contract and reports
> **PASS**; and the RED-reproducibility waiver rests on TAE being non-archival
> (`SUBMISSION_READINESS.md:264`, `HANDOVER.md:111` — "that waiver does not transfer to an
> archival venue").
>
> Banner added by the 2026-08-05 records adjudication:
> `analysis/cleanup_2026-08-05.md`. Nothing below this line was changed.

> ## ✅ DESTINATION CONFIRMED — ICLR 2027 main track. Author's decision, 2026-08-06.
>
> **The paper is going to ICLR 2027 main track.** This is the entry the banner above asked
> for; the "no destination is confirmed" state ends here.
>
> | | |
> |---|---|
> | deadline | **25 September 2026, AoE** |
> | decision | 16 December 2026 |
> | conference | 26–30 April 2027, California |
> | length | **9 pages excluding references**, 10 at rebuttal, unlimited appendix |
> | review | double-blind |
> | arXiv | permitted, including during review |
>
> Verified from `iclr.cc` on 2026-08-05. The organisers of the withdrawn workshop explicitly
> cleared this route in writing (`HANDOVER.md:37`): "It is perfectly acceptable to submit work
> that you intend to further develop into a full paper for a future main conference submission."
>
> **The migration is already substantially done.** `ICLR2027/submission/` holds a real,
> buildable, self-consistent package: a 9-page anonymous PDF, its own style files, three
> self-checks that pass. Its manuscript is **a different paper** from the TAE one — measured,
> not assumed: 43 of roughly 2,500 shared eight-grams (Jaccard 0.0086) and one shared sentence,
> different titles, 12 sections against 7. *When Guardrails Change What Gets Counted* became
> *When Governance Changes What Gets Counted: Measurement Validity for LLM Agent Evaluation*.
>
> ### What this unblocks, and what it now obliges
>
> **Unblocked** — both items the banner listed as waiting on this decision:
>
> 1. `paper/submission_gate.py:127-129, 835-864` may now be re-pointed or retired. As it stands
>    it hardcodes `BODY_PAGE_LIMIT = 8`, TAE's CFP URL and workshop title, and reads **only**
>    `SUBMISSION_2026/TAE/paper/manuscript.tex` — so it reports PASS for a venue that no longer
>    exists and has never looked at the live manuscript. **A passing check that validates the
>    wrong specification is the exact defect this paper is about**, so leaving it is not neutral.
>    Note the replacement is not a one-line edit: the ICLR side currently has **no page gate at
>    all**, and the live PDF is 9 pages against a 9-page limit with nothing watching it.
> 2. The RED-reproducibility waiver **does not transfer.** It was granted because TAE was
>    non-archival and PDF-only. ICLR is archival. This needs a real answer in the paper, not the
>    same sentence — and it is currently carried over unbannered.
>
> **Obliged, and new:** the 9-page limit **excludes references**, which changes the shape of the
> remaining work. The current PDF is 9 pages *including* its bibliography
> (`manuscript.tex:211`), so the counted body is not yet full, and expanding the bibliography
> from its present **six entries** frees body space rather than consuming it. Six references is
> the largest acceptance risk in the draft and it is now also the cheapest thing to fix.
>
> ### What this does NOT change
>
> Everything below the original banner stays unedited. The 2026-08-03 TAE decision was correct
> on its own terms and is the record of a real choice; the destination moved, the reasoning did
> not become wrong. The eight-page structure in §8, the figure plan in §9 and the claims
> discipline in §10 were written for a shorter paper and must be re-read against nine pages
> before being followed — but they are not deleted, and they are not to be quietly rewritten.
>
> Written 2026-08-06 on the author's explicit instruction, during the seed-42 first-attempt run.

> ## ✅ SCOPE CONFIRMED — LLM arms only. No rule-based comparator. Author, 2026-08-06.
>
> **The ICLR paper uses the LLM experiments only: validator-on against validator-off, and
> nothing else.** No rule-based agent, no fuzzy-Q, no non-LLM comparator of any kind.
>
> **This confirms the status quo — there is nothing to build or remove.** Verified 2026-08-06:
> `manuscript.tex` returns **zero** matches for `rule-based|rulebased|fuzzy|q-learning|FQL|non-LLM`,
> and `_data.py:173-176` already raises on any arm name other than `gov`/`noval`. The two audit
> scripts under `SUBMISSION_2026/audit/` list `rulebased` in their *exclusion* tuples. Three
> independent places in this repository already encode the refusal.
>
> ### Why the comparator is not merely absent but undefined
>
> This is worth recording so it is not re-opened. The paper's headline number is a rate whose
> **denominator is written by the agent itself** — the share of decisions in which the agent
> *reported* high scarcity. A non-LLM policy files no such report.
>
> The rule-based flood corpus (`examples/single_agent/results/rulebased/`) carries nine columns
> and **not one of them is an appraisal**: `agent_id, year, decision, flooded_this_year, elevated,
> has_insurance, relocated, trust_in_insurance, trust_in_neighbors`. The appraisal reader at
> `_data.py:585-589` recognises only `wsa_label`, `construct_WSA_LABEL` and `construct_TP_LABEL`,
> and would raise on every row. The Nature Water analysis hit the same wall and wrote it down:
> `examples/single_agent/analysis/compute_flood_metrics.py:172-173`,
> `# No threat_appraisal in rulebased` → `ibr_val = float("nan")`.
>
> So the answer to "should we add one" is not "not worth the effort". **It is that the quantity
> does not exist for that arm.**
>
> ### What Nature Water does, and why it is not a precedent here
>
> NW gives **both** its cases a third non-LLM arm, but they are two different kinds of thing and
> only one is rule-based:
>
> **There are three levels of governance in play, not two.** Corrected 2026-08-06 after checking the
> runner and the shipped columns rather than the docstrings:
>
> | arm | the 12 validators | **the retry loop** | what it produces |
> |---|---|---|---|
> | `Group_C` (governed LLM) | ✅ | ✅ **blocked → the model is re-asked** | full audit trail |
> | **`fql_raw`** (irrigation's third arm) | ✅ **71.1% of actions blocked** | ❌ **blocked → no second attempt** | `simulation_log.csv` only |
> | **`rulebased`** (flood's third arm) | ❌ never enters the pipeline | ❌ | `simulation_log.csv` only |
>
> **The middle row is the interesting one, and it is exactly what this paper is about.** The retry
> loop is the mechanism by which enforcement rewrites its own antecedent: a blocked LLM re-answers
> the whole prompt, appraisal included. A blocked FQL action is simply blocked — the agent does not
> revise anything, because there is nothing to revise. `run_fql_baseline.py:148` states the
> asymmetry outright: "*The LLM path uses broker's RejectionHandler which re-invokes the LLM*".
> Measured: `fql_blocked` is true on **23,291 of 32,760 rows across all ten seeds, 71.1%**.
>
> Two things to check rather than assume:
>
> - **NW's footnote says 84–89% of FQL actions were rejected; pooled over ten seeds I measure 71.1%.**
>   The denominators may differ (per-cell, or per-metric), but the gap is large enough to reconcile
>   before either number is quoted again.
> - **FQL's log carries `wsa_label` and `aca_label`; `rulebased`'s carries no appraisal at all.** They
>   are not the same kind of quantity as an LLM's self-report: a Q-learning agent's labels are
>   *computed from environment state*, which is precisely the case this paper calls sound — a
>   predicate with an observation channel independent of the generation being governed.
>
> **The first row is the one that is easy to get wrong, and I got it wrong once before correcting it
> here.** "Rule-based" is not the flood ablation with governance switched off — that is
> `Group_C_disabled`, which *does* run through the broker (`--governance-mode disabled`) and
> therefore emits a full `household_governance_audit.csv` that can be compared row-for-row against
> `Group_C`. The `rulebased/` arm is a **separate program outside the framework**. Its run
> directories hold `simulation_log.csv` and a plot, and nothing else: no audit CSV, no
> `governance_summary.json`, no `config_snapshot.yaml`, no `reproducibility_manifest.json`, no
> reflection log. Verified by directory listing, 2026-08-06.
>
> That single fact explains the rest of its behaviour: it carries no appraisal column because nothing
> ever asked it for one; it has no manifest because `experiment_runner.py` did not produce it; and
> two of its three runs reproduce from no seed.
>
> **The two arms therefore answer different questions and are not parallel.** FQL asks *"replace the
> LLM with a Q-table, hold governance fixed — what changes?"*, isolating the contribution of the
> reasoning format. The rule-based agent asks *"how does the whole LLM-plus-governance stack compare
> with conventional ABM practice?"* Both are legitimate. Calling both of them "baseline" in one paper
> invites a reader to compare them with each other, which is meaningless — they share neither a code
> path nor a governance condition.
>
> `run_fql_baseline.py:7` states it: "Everything else is identical: ... **same 12 governance
> validators**", and the shipped logs carry an `fql_blocked` column confirming enforcement was
> active. NW's own Extended Data Table 1 footnote says two of its four behavioural metrics "are
> not computed because 84–89% of FQL actions were rejected by governance".
>
> **A correction to a claim made during this audit:** a subagent reported that NW's Discussion
> calls the FQL arm "a conservative rule-based baseline". **That is not reproducible in the
> current drafts** — `rule-based` there refers consistently to the flood PMT agent, and Results
> and SI Table 11 both label the irrigation arm "FQL baseline". The mislabel lives in
> `run_fql_baseline.py:9` ("This produces a published rule-based baseline"), i.e. in code, not in
> the paper. Worth fixing in the docstring; the manuscript needs nothing.
>
> ### One question this decision leaves open
>
> **The ICLR manuscript reports no flood result number at all.** `flood` appears four times and
> every one is descriptive: the setting (`:28`), irrigation-is-primary (`:76`), an irrigation
> result (`:93`), and a limitation (`:193`). The pipeline reaches **18 flood arm-cells** and the
> manuscript reports none of them. That may be deliberate — flood as portability, not evidence —
> but it is not stated anywhere, and a reviewer will ask why nine configurations were run and
> none reported. **Not part of this decision; flagged for the next one.**

Supersedes `workshop_skeleton.md` (which carries a retraction banner). Written 2026-07-31 after the
materials audit, the mechanism falsification, and the psych-framing prior-art check.

---


## VENUE DECIDED — 2026-08-03

**Target: the TAE workshop at NeurIPS 2026. Deadline 29 August 2026, AoE. Author submits.**
Decided by the author on 2026-08-03 after weighing it against going straight to a main conference.

The reasoning, recorded because the same question will come back when the fuller version is planned:

- **Timing is what decided it.** The goal is a 2027 summer internship, and those applications are read
  in autumn 2026. A workshop notification arrives in time to appear on the application; a main-track
  paper submitted in October would not be decided until early 2027, after the fact.
- **It costs nothing.** TAE is non-archival, so the work is not spent and a fuller main-track version
  remains available.
- **The paper is workshop-strong, not yet main-track-strong.** The limitations this file records ---
  one governance stack, one simulator, all models at or under 27B open weights, and gemma4:e2b not
  reproducing the fine-grained residual --- are acceptable disclosures at a workshop and would be
  pressed hard at a main track. Closing them needs a second governance stack or a second measurement
  domain, which is months rather than weeks.
- **Fit.** The workshop's question is whether AI evaluation can be trusted; this paper argues a
  governance metric can fail to measure what it claims. At a main track it competes with method
  papers for attention.

**SENT 2026-08-03 16:55 UTC, awaiting reply.** The author sent the dual-submission question
themselves, from wec324@lehigh.edu to aiteval2026@gmail.com -- the address the CFP designates
verbatim ("Please email any inquiries to aiteval2026@gmail.com"). If no reply by 2026-08-10, follow up
to hanxun@unimelb.edu.au (Hanxun Huang, University of Melbourne, first-listed organiser and the
contact published on the OpenReview venue page); that still leaves over two weeks before the deadline.
Record the reply here with its date when it arrives.

**Two dates confirmed from the OpenReview venue page on 2026-08-03**, which are more authoritative
than the CFP prose because they are what the submission form enforces: submission opened
**29 Jul 2026** and the deadline displays as **30 Aug 2026, 07:59 local (US Eastern)**, which is
29 Aug 23:59 AoE and therefore consistent with the CFP. The submission button is live and the
author's OpenReview account reaches it, so the profile is not blocked pending manual activation.

**Superseded, kept for the record:** the dual-submission question. The CFP states that accepted papers
are non-archival but states no dual-submission policy at all --- absence of a rule is not permission.
A draft asking the organisers sits in the author's Gmail; the author sends it and records the reply
here with its date. If the answer forbids a later main-track version, this decision is revisited.

**Not in the paper, by the author's instruction (2026-08-03):** nothing that changes what the paper
claims is added at this stage. The gemma4 replication numbers stay in NUMBERS.md as traceable
evidence and do not enter the manuscript. The one edit made under that instruction NARROWED an
existing claim rather than adding one: section 5's "leaves a residual near zero at every resolution"
was unscoped and now reads "leaves on this cell", because the decomposition run on gemma4:e2b shows
the unscoped form is false for that cell and shipping it knowingly was not an option.

---

## 1. Venue

**TAE (Trust-AI-Eval): "Can We Trust AI Evaluation?"** — https://tai-eval.github.io/
NeurIPS 2026, Sydney. Submission **29 Aug 2026 AoE**, notification **22 Sep 2026** (earliest of every
candidate). **≤8 pages**, references excluded, appendices unlimited but reviewers need not read them.
**Non-archival. Double-blind.** OpenReview `NeurIPS.cc/2026/Workshop/TAE`.

Chosen because three of its nine listed topics describe this paper almost verbatim: *measurement
validity*, *benchmark auditing*, *deployment risk and governance*. It is the only candidate that is
both best-fit and 8 pages.

**Dual-submission policy is UNCONFIRMED on its CFP.** Check before submitting, because a main-track
version is planned. Every other candidate explicitly welcomes work under review elsewhere.

**Double-blind is a hard constraint that is easy to forget.** The group's own WRR 2026 predecessor
and the Nature Water manuscript must be cited in the third person throughout. Put this on the
pre-submission checklist.

---

## 2. What we concede, and what we claim

The prior-art check produced one finding that decides the whole framing: **there are two papers
hiding inside this material, and we must pick one.**

**CONCEDE, explicitly and early — this is not a systems contribution.** Behavioural-theory coherence
is not a new class of runtime enforcement. AgentSpec's DSL places no constraint on what a predicate
may read, so `appraisal == high AND action == increase → REJECT` is a well-formed rule anyone could
write today. Worse, SAVeR (arXiv:2604.08401) already enforces verification over an agent's *internal
belief states* before action commitment. Fighting this loses a reviewer for nothing.

**CLAIM — this is an evaluation contribution.** And the property that does the work is **not**
endogeneity. Endogeneity alone does not separate us: an AgentSpec predicate over program state after
the agent has edited files is also treatment-affected, and Gao et al. (arXiv:2607.24604) already name
"post-treatment risk-set bias" in agentic code repair. Argue on endogeneity alone and a reviewer
produces Gao et al. and we lose the paragraph.

The defensible separation is this:

> For a world predicate there is an observation channel independent of the agent's generation — you
> can stat the filesystem, read the budget, freeze the state and re-branch from it. For a
> self-reported appraisal predicate the *only* channel is the generation being governed. There is no
> ground truth to validate the antecedent against; antecedent and regulated action share every latent
> cause by construction; and the enforcement loop **rewrites the distribution of its own antecedent
> and cannot be made not to**, because freezing the appraisal destroys the thing being measured.

That last clause is what no near-neighbour has. Gao et al.'s remedy — branch from frozen common
states — is available *precisely because* their conditioning variable is external. Ours is
unavailable **in principle**. That is the sentence the paper is built on.

### The one-sentence novelty claim

**Write this:**

> When a governance layer's norm conditions on a state the agent itself reports, the conformance
> statistic has no observation channel independent of the process it governs, so enforcement rewrites
> the distribution of its own conditioning variable and the reported gain cannot be separated into
> behaviour and composition by that statistic.

**Do not write this** (it dies to AgentSpec + SAVeR in one reviewer comment):

> We introduce behavioural-feasibility governance, a new class of runtime enforcement in which rules
> encode a behavioural theory and condition on the agent's self-reported cognitive state.

---

## 3. Terminology hazard — verified, act on it

**arXiv:2603.21435, Taejin Park, "Behavioural feasible set: Value alignment constraints on AI
decision support" (22 Mar 2026)** already uses "behavioural feasible set" for something else entirely
— the range of recommendations reachable under vendor alignment constraints. It is a **term
collision, not a preemption**, but it is four months old, sits in the AI-governance literature, and
is the first thing a reviewer searching our term will find.

**Do not use "behavioural feasibility" as an unqualified coined term.** Either pick another label or
disambiguate in a footnote on first use. The internal `world feasibility / behavioural feasibility`
distinction stays as *our* working vocabulary; it just cannot be presented as a coined contribution
without that fence.

---

## 4. Mechanism — the corrected story

The original claim (agents revise their premise so the rule stops applying) is **falsified by this
corpus**, three ways, all re-derived independently:

| evidence | result |
|---|---|
| Year 1, worlds provably identical (`evidence/e0_year1_exogeneity.py`: year-1 exact equality **1.0 on every pre-decision column, in all five irrigation cells, over 1,560 matched year-1 pairs**; first divergence year 2) | shift ≈ 0, despite **82.1%** of governed year-1 decisions having been rejected and re-prompted at least once, **70.5%** of them all the way to the retry budget (anchor cell; the "68–88%" figure quoted earlier is the range of per-cell means for *retried at least once*, not budget exhaustion — do not write "exhausted" for it) |
| Decisions the agent was **never retried on** — no validator ever spoke to it | shift is **larger**: +48.21 pp vs +40.02 pooled, **5 of 5** irrigation cells (+49.09 vs +40.45 before the pool grew to 21 paired units on 2026-08-03) |
| Trajectory | shift tracks the reservoir; governed arm ends **+106.57 ft** higher on Mead (**final-year gap**), **+102.25 ft** averaged over the 42 years. Two different quantities — this row previously conflated them by calling the mean "ends". The manuscript prints both, correctly labelled. *(The "1.84 shortage tiers lower" figure that used to sit here is produced by no script — backlog W2; do not print it.)* |

**What "the world" means in row 1, and a correction.** The cornerstone is now re-derived inside this
folder by `evidence/e0_year1_exogeneity.py` (2026-08-01), which takes its run directories from
`_data.py`, joins the two arms on (seed, agent_id, year), and tests **exact string equality** on the
raw csv cell — no tolerance, no numeric coercion. It gates on **nine** pre-decision columns: four
static agent attributes (`cluster`, `basin`, `water_right`, `has_efficient_system`) and five
environment/institution fields the agent is shown when it is asked (`drought_index`, `shortage_tier`,
`curtailment_ratio`, `lake_mead_level`, `mead_storage_maf`). All nine are equal on **100%** of year-1
pairs in every cell, and the first year any of them disagrees is **2**.

`utilisation_pct` and `below_minimum_utilisation` are **not** pre-decision and are excluded from that
gate: `simulation_log.csv` is written in `post_year`, and `utilisation_pct` is
`request / water_right`, where `request` is the demand the year's skill has just set
(`examples/irrigation_abm/run_experiment.py:307, 344-347`). The script prints them anyway, with a
control that settles it on the data: restricted to year-1 pairs where both arms applied the same
skill **and** the same `magnitude_pct`, both columns are exactly equal (43/43, 39/39, 37/37, 8/8,
27/27), and every disagreement sits on a pair whose demand change differed. Anything written earlier
that counted those two as evidence of world-identity was counting a post-treatment column; nothing in
the mechanism argument depends on them.

**The appraisal moves mainly because the intervention changed the world and the agent reported the
changed world accurately.**

This is a stronger result than premise revision, because it requires no assumption that the agent
games anything. Lead with it:

> Even a perfectly honest agent breaks the statistic. The metric is most misleading exactly when the
> intervention is most effective.

---

## 5. A hazard we must state ourselves — verified this session

For a governed decision that was retried and eventually approved, the appraisal we observe is the one
from the **accepted** generation. That is not merely post-treatment conditioning; it is conditioning
on the acceptance event, i.e. **selection on the rule itself**. **23.3%** of governed decisions are
in that category **on the anchor cell, seed 42 alone** (763 of 3,276: 2,030 retried, 1,267 of them
ending REJECTED).

**Do not read this as disagreeing with the 24.3% quoted in §12.** They are different strata, and
both are right: 23.3% is seed 42 on its own, 24.3% is the anchor cell pooled across all five seeds
(n = 16,380), which is the figure the manuscript prints. This is exactly the failure mode backlog
item W3 was raised for — **name the stratum with every retry number**, because three different true
retry figures are in circulation and have been read as contradictions.

**Is the unselected first-attempt appraisal recoverable? No — checked three ways, all negative:**
- audit CSV `raw_output` holds a single generation (708 chars, one `"reasoning"` block) on a
  `retry_count = 3` row;
- `proposed_skill == final_skill` on 2,007 of 2,030 retried rows, so that column is the *last*
  proposal, not the first;
- `raw/irrigation_farmer_traces.jsonl` (49 MB) holds **3,276 records for 3,276 distinct
  (agent, year) pairs, maximum one each** — one record per decision, not per attempt.

An adjudicating agent asserted the first-attempt distribution "exists on disk". It does not. State
the limitation; do not promise the correction.

What partly rescues the argument: the **never-retried** stratum had no appraisal rewritten at all,
and the shift there is *larger*. So acceptance-selection is not what produces the effect. Say that
explicitly — it converts a hole into a controlled comparison.

---

## 6. Do not lead with mediation

The appraisal-as-mediator argument holds but is the wrong opening, and it costs more than it pays.
"Mediator" commits us to the claim that the appraisal *transmits* the governance effect to the
action — which we do not need and probably cannot support: Paul et al. (2024, Findings of EMNLP,
DOI 10.18653/v1/2024.findings-emnlp.882) run causal mediation over twelve LLMs and find they "do not
reliably use their intermediate reasoning steps."

Three fair attacks a reviewer who knows appraisal theory will make: PMT's appraisal mediates a *fear
appeal*, not a validator (close it by drawing the path governance → world state → reported appraisal
→ action, and noting the intervention enters PMT's own environmental-information box); appraisal is
also a *moderator* (does not matter — a post-treatment moderator is equally fatal); Lazarus's
transactional model is not a linear chain (concede it, it strengthens us — jointly determined means
not merely post-treatment but unidentified).

Use appraisal theory as a **one-paragraph grounding**, not as the spine.

---

## 7. The two-layer distinction must be a result, not a framing sentence

"World feasibility vs behavioural feasibility" is presentational philosophy **unless the two layers
demonstrably behave differently in the data.** They do, and this has to be a numbered result with a
figure. **Corrected 2026-07-31 — an earlier draft of this section overstated it and would have been
caught in review.**

What is true is disjointness at the LAYER level:

| arm | rejections (5 seeds, anchor) | what fired |
|---|---|---|
| no-validator | 4,757 / 16,380 (29.0%) | **100% bare precondition** — the water-right allocation cap. No validator rule was evaluated at all. |
| with validators | 6,469 / 16,380 (39.5%) | **100% named a validator rule.** Zero bare preconditions. |

What is NOT true is that the governed rejections are all behavioural theory. The validator stack
contains **both** kinds of rule, and only two of the six that fire read the self-reported appraisal:

| rule | fires | reads |
|---|---:|---|
| `demand_ceiling_stabilizer` | 5,592 | world state |
| `high_threat_high_cope_no_increase` | 3,672 | **self-reported appraisal** |
| `curtailment_awareness` | 1,740 | world state |
| `supply_gap_block_increase` | 672 | world state |
| `demand_floor_stabilizer` | 621 | world state |
| `low_threat_no_increase` | 210 | **self-reported appraisal** |

So **3,840 of 6,469 governed rejections (59.4%) name an appraisal-conditioned rule**; the other
2,629 (40.6%) name only world-conditioned validator rules. Claim the 59.4%, not 100%. A reviewer who
opens the rule list sees `demand_ceiling_stabilizer` is a world constraint, and an overstatement here
would cost us the reader for the whole paper.

**This is an opportunity, not just a correction.** Because both rule kinds live in the SAME stack,
the same arm and the same run, there is a **within-system contrast** available — appraisal-conditioned
rules against world-conditioned rules, with no cross-testbed comparison and therefore none of the
regime/testbed confounding. That is a tighter comparison than irrigation-versus-flood and it is what
Figure 1 should carry.

Two scope corrections that go with it:
- "The no-validator rejections are all on increase proposals" is **99.95%** (6,168 / 6,171), not 100%.
  The three exceptions are retry-exhausted fallback rows with a blank `proposed_skill` whose error
  message is still the allocation cap. Prefer the structural argument, which is exact: the
  precondition exists only on the two increase skills, so that layer cannot block anything else.
- "Both arms reject a substantial share" holds for the **anchor cell only**. No-validator rejection
  rates are 29.0% (gemma3:4b), 5.3% (12b), 3.6% (e2b), 1.5% (e4b), 1.0% (ministral3:8b). Scope the
  "the water right still binds" sentence to the anchor or the per-model panel falsifies it.

---

## 8. Eight-page structure

> **⚠ STALE — the manuscript has moved past this table; it is a planning artefact, not a
> description.** Three things changed after it was written. There are now **nine** numbered sections
> plus an unnumbered "Artifact availability" (a §9 Conclusion was added on 2 August so the paper
> would not end on its own limitations). §3 was **renamed** on 3 August, from "The two rule layers
> separate" to **"Which rules read what the agent says"**, precisely because it is setup and the old
> heading promised a result it does not deliver. And the page budget below sums to 8.0 against a
> structure the paper no longer has.
>
> **`paper/manuscript.md` is the authority on structure**, and
> `python SUBMISSION_2026/TAE/paper/submission_gate.py` is the authority on whether it fits — it
> measures the page the References heading is typeset on, cross-checks `manuscript.aux`, and reports
> the remaining slack in body lines. This file remains the decision of record for **content**: what
> the paper claims and what it may not (§2, §3, §5, §6, §7, §10, §12). It is no longer a reliable
> description of the paper's shape.

| § | pages | content |
|---|---|---|
| 1 Introduction | 1.0 | Guardrail layers proliferate; all are detect → tell → retry. State the gap: nobody asks what the conformance number measures when the norm's antecedent is model-authored. **Concede systems novelty here**, in one sentence, before a reviewer has to. |
| 2 Setup | 0.75 | The instrument. Two testbeds, 9 LLM configs, validators-on/off. Keep factual and short; it is not the contribution. Flood is introduced as a **cross-theory portability demonstration**, which is what it was built as. |
| 3 The two rule layers separate | 1.0 | §7 above, with the figure. Establishes that the behavioural layer is a distinct, measurable thing before any claim rests on it. |
| 4 The conditioning variable moves | **1.25** | The per-cell table, complete regime separation, corrected numbers. Report both arms' prevalence — the one extra number nobody reports. **Reduced from 1.5 to fund §7 (revised 2026-08-01).** Once §5 decomposes the shift directly, §4 has only to establish that the conditioning variable moves and by how much in each cell, which the table does on its own; the interpretive work this section was carrying moves to §5. |
| 5 Why it moves — the mechanism | 1.75 | **The core, and as of 2026-08-01 a direct decomposition rather than an inference from three indirect signs.** Lead with the world-fixed result. The raw HIGH-appraisal shift is **+45.73 pp**; standardising both arms on a common world-state distribution removes it — residual **−2.53 pp** on shortage tier alone at **100% coverage**, **+0.21 pp** at the finest stratification (tier + Mead + drought + agent cluster) at **43.4% coverage**, and no resolution produces a residual above **4.47 pp**. Quote the coverage beside every residual; a stratum needs 40 rows in both arms, so fine strata cover roughly half the corpus and coarse strata all of it. Then give the composition that is left as the explanation: the governed arm spends **64.8%** of its decisions in shortage tier 0 and the no-validator arm **76.7%** of its decisions in tier 3. The two arms occupy different worlds, and within a world they report the same thing. **Year 1 and the never-retried stratum are now corroboration, in that order and in roughly half the space they were going to take.** Year 1: the arms' worlds are exactly equal on all nine pre-decision columns (390 matched anchor pairs, first divergence year 2) and the shift is **+3.33 pp** (95% CI −3.75, +10.42; p = 0.261), although 82.1% of governed year-1 decisions were rejected and re-prompted and 70.5% of all year-1 decisions ran to the retry budget. Never-retried: on decisions the loop never spoke to the shift is *larger*, **5 of 5 cells** (+48.21 vs +40.02 pooled — +49.09 vs +40.45 before 2026-08-03, when the pool grew from 20 paired units to 21; anchor +53.46, unchanged), so acceptance-selection is not what produces it — and the stratum-asymmetry caveat travels attached to that number (anchor 36.2% of governed decisions against 64.6% of no-validator ones). Close on the reservoir as the thing that made the worlds differ: **+106.57 ft** final gap, **+102.25 ft** mean over 42 years, the no-validator arm first touching the 895 ft floor in year 17–18 in all five seeds and the governed arm in none. Conclusion unchanged and now demonstrated instead of argued: a perfectly honest agent breaks the statistic, and the metric is most misleading exactly when the intervention works best. **Space: no increase.** The decomposition table costs about a quarter page and retires more hedged prose than it costs — the old plan had to argue from three converging indirect signs and pre-empt the reading that the agent games the rule, and the decomposition closes that reading outright. **Figure 2 must be re-planned around the decomposition: §9 still calls the per-year-shift-plus-reservoir panel "the paper's argument in one panel", and that panel is now corroboration, not the argument.** |
| 6 What it does to the statistic | 1.0 | Conditional vs unconditional across five irrigation cells, including **Gemma-3 12B: +11.4 conditional → +0.2 unconditional**, where the whole apparent effect is composition. |
| 7 What to do instead | **0.75** | **Revised 2026-08-01: the world-state recommendation is falsified by our own test and is replaced. One prescription survives, one is reported as a tested failure.** Report the falsified repair rather than dropping it. The obvious fix — condition the norm on world state instead of on what the agent says — is false on this corpus, and we tested it: world antecedents shift as much or more than the self-reported one, `shortage_tier >= 2` by **+64.29 pp** against the self-report's **+45.73 pp**, `tier >= 1 and curtailment > 0` by **+55.71 pp**, drought index ≥ 0.5 by **+25.71 pp**. In a coupled system the world is downstream of the treatment as well, so moving the antecedent does not buy an unmoved conditioning variable. Testing the obvious repair and reporting that it fails is worth more than never raising it, and it stops a reviewer proposing it as though it were free. **The surviving recommendation:** if a norm reads a state the agent reports, log the independent world state alongside it, because that is what makes the conformance number decomposable at all — with the world recorded, §5's stratification runs and the reported gain separates into behaviour and composition; without it, no separation is available at any resolution. What survives is not which variable the norm reads but whether the shift can be decomposed. Keep the two prescriptions the falsification does not touch: report the conditioning variable's prevalence in both arms next to every conformance rate, and prefer a design-fixed denominator to a data-dependent one where the choice exists. **Space: 0.5 → 0.75 pg, paid for by §4.** This section states the prescription and the one negative result; it does not re-argue §5. |
| 8 Limitations & what would settle it | 0.5 | Acceptance-selection with the first-attempt limitation; provenance; two open-weight families ≤27B; regime confounded with testbed, which is why identification is within-irrigation. |

Sections 3, 5 and 6 are the paper. Sections 1, 2, 8 must be ruthless. **§7 is no longer purely
prescriptive** — it carries the falsified world-antecedent repair, which is a result, and that is what
its extra quarter page buys.

**Budget check after the 2026-08-01 revision:** 1.0 + 0.75 + 1.0 + 1.25 + 1.75 + 1.0 + 0.75 + 0.5 =
**8.0**. §7 gains 0.25 and §4 loses 0.25; nothing else moves. If a further overrun appears, the order
of cuts is unchanged from `PLAN.md` §3: cut §7 to the surviving recommendation plus one sentence of
the negative result, then cut the appendix, before touching the buffer.

---

## 9. Figures

> **⚠ STALE — there are FOUR figures, not three.** A problem schematic was added as Figure 1 after
> this list was written, which pushed every figure below it up by one. This is the same class of
> defect as the artifact statement that promised "the plotted values behind all three figures" when
> there were four. **The manuscript's `<!-- FIGURE n -->` markers are the authority**, and
> `submission_gate.py` checks the count in the prose against the files on disk.
>
> Current numbering — note the filenames are one lower than the figure numbers:
> **Fig 1** `fig0_problem_schematic` · **Fig 2** `fig1_rule_layers` ·
> **Fig 3** `fig2_mechanism` · **Fig 4** `fig3_consequence`.

- **Fig 2 (`fig1_rule_layers`) — the two rule layers.** §7's separation. New; replaces nothing.
- **Fig 3 (`fig2_mechanism`) — mechanism.** Per-year appraisal shift with the year-1 point marked,
  alongside the reservoir divergence on a twin axis. Since the 2026-08-01 revision this is
  **corroboration, not the argument** — §5 leads on the direct decomposition. The "paper's argument
  in one panel" description below is superseded, and §8's own note above flags it.
- **Fig 4 (`fig3_consequence`) — consequence.** Conditional vs unconditional gap, five irrigation
  cells, 12B highlighted.
- **KILLED: the old Figure 1** (x = % rejected, y = shift, 14 cells). It implies a pressure→shift
  relationship that is not identified — enforcement regime is perfectly confounded with testbed
  (all 5 high cells irrigation, all 9 low cells flood; within-testbed Pearson is **−0.514** in
  irrigation, the wrong sign). The 14-cell table stays in the text as evidence that the effect is
  not a single-model artifact; it does not become a scatter plot.

---

## 10. Claims discipline — additions to the skeleton's list

Everything on the skeleton's original list still applies. Add:

- ❌ Any assertion of premise revision. Our data falsifies it.
- ❌ Flood as a "low enforcement pressure" control. It is a portability demo with no
  action→environment feedback (`run_flood.py:285-291`).
- ❌ "Behavioural feasibility" unqualified (term collision, §3).
- ❌ "The appraisal mediates the governance effect" (we cannot support transmission).
- ❌ Any claim that the first-attempt appraisal can be recovered from this corpus.
- ❌ Endogeneity as the differentiator. Use the no-independent-channel argument instead.
- ✅ Concede systems novelty in §1, in our own words, before review does it for us.

---

## 11. Schedule to 29 Aug (30 days)

| | work | days |
|---|---|---|
| now | remaining material fixes: adopt the new framing in the evidence scripts, restate flood, kill the three unfixed globs, pick the analysis set | 1.5 |
| then | §3–§6 drafted from the frozen numbers | 4 |
| then | §1–§2, §7–§8 | 2 |
| then | abstract last | 0.5 |
| then | red-team against §10 + citation re-verification + double-blind sweep | 1.5 |
| | **total** | **~9.5** |

Leaves roughly three weeks of slack. Zero GPU throughout.

---

## 12. The strongest attack, and whether we have an answer

**Attack:** "You have shown that in a coupled simulation the environment diverges between arms and
the agent reports the divergence. That is a property of coupled simulations, not of LLM agents. Any
ABM conditioning a statistic on a state variable has this problem, and it has been known for decades."

**Answer, and as of 2026-08-01 it is measured rather than argued.** Concede the reviewer's premise
outright, because our own decomposition establishes it: holding the world fixed removes the shift
(residual −2.53 pp on shortage tier at 100% coverage, +0.21 pp at the finest stratification, never
above 4.47 pp against a raw +45.73 pp), and the arms differ because they occupy different worlds —
64.8% of governed decisions in shortage tier 0 against 76.7% of no-validator decisions in tier 3. The
shift is composition. We agree with the reviewer and we have the number, which is a far better
position than arguing the point.

The disagreement is about what follows, and the decomposition sharpens all three parts of it.

1. **The classical remedy does not exist here.** In a conventional ABM the appraisal is a fixed
   function of the world state, so the analyst recomputes it from the world state and conditions on
   *that*; the decomposition is always available and the failure is repairable. Here the appraisal is
   generated by the same model call that chooses the action. There is no function to invert and no
   independent channel to recompute it from.
2. **What we did instead is contingent, not general — and this is the part the decomposition adds.**
   The stratification ran only because this simulation writes shortage tier, Mead elevation, drought
   index and agent cluster to a log that is not produced by the generation. That record is what made
   the shift separable. A deployed governance layer keeps the rule fires, the retries and the outcome,
   and normally nothing playing the role of `shortage_tier`; the identical shift would then be present
   and undecomposable at every resolution. The problem is not that a state variable moved. It is that
   the only observation of the conditioning variable is produced by the process under governance, and
   recovering the separation required a second record that a language-agent deployment has no reason
   to keep. That is the same sentence as §2, now with a demonstration attached.
3. **The remedy the attack implies also fails, and we tested it.** If this were only a
   coupled-simulation artifact the fix would be to condition the norm on world state instead.
   `shortage_tier >= 2` shifts +64.29 pp against the self-report's +45.73 pp. The coupling framing
   yields no repair, which is why §7 reports it as a negative result.

State the stratification's own limit in the same breath, before a reviewer does: a stratum needs 40
rows in both arms, so the finest resolution covers 43.4% of the corpus, and the resolution that covers
all of it is coarse.

**Weakest point remaining, restated.** The decomposition tightens the old bound rather than closing
it. Any residual gaming component in the *cross-arm* comparison must sit within 4.47 pp of a 45.73 pp
shift. It says nothing about the *within-decision* channel — what the first attempt reported before
the retry loop rewrote it, on the 24.3% of governed decisions approved after at least one retry — and
that attempt is not in the shipped corpus (§5). Say both in §8, and do not let the decomposition be
read as covering both quantities.
