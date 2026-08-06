# Workshop paper skeleton — 4 pages, zero GPU

> ## ⚠ RETRACTION BANNER — 2026-07-30. DO NOT COPY NUMBERS OR CLAIMS FROM BELOW WITHOUT READING THIS.
>
> This skeleton was written 2026-07-29. A materials audit and an independent recomputation have since
> falsified parts of it. It is kept for its section plan; its abstract and its mechanism claim are dead.
>
> **Falsified — the mechanism.** The paper assumed enforcement makes the agent revise its self-reported
> appraisal ("premise revision"), and title candidate 1 asserts it. The corpus says otherwise:
> at year 1, where both arms' worlds are provably identical, the shift is ~0 despite 68–88% of governed
> decisions having exhausted their retries; and on decisions the agent was **never retried on** the shift
> is *larger* (+49.1 pp vs +40.4 pooled, 5/5 cells). The appraisal moves because the intervention changed
> the world and the agent reported it accurately (governed Lake Mead ends 102 ft higher).
> **Title candidate 1 is dead. Title candidate 2 survives and gets stronger.**
>
> **Falsified — the flood control.** Flood was built as a cross-theory portability demonstration, not a
> control, and `run_flood.py:285-291` gives it no action→environment feedback at all. It is not a
> "low enforcement pressure" arm. The identifying evidence is within irrigation and needs no
> cross-testbed comparison.
>
> **Wrong numbers.** "432,083 logged decisions across 14 cells" → the 14 cells hold **216,020**
> (432,083 is a whole-corpus figure over 347 runs). Low-regime mean "0.8 pp" → **+0.56 pp**.
> "9/9 cells" → only **5 of 9** low cells are positive, largest **+6.25 pp**; "vanishes" overstates it.
> One cell was contaminated by 903 rows from a `Group_A` backup: flood ministral3:3b was +2.04 pp,
> is **−0.22 pp**. Fixed in `evidence/appraisal_composition.py` and its CSV on 2026-07-30.
>
> **Still valid:** the section plan, the claims-discipline list, the artifact policy, the partition
> against the other manuscripts, and the per-cell table apart from the one corrected cell.
> Separation remains COMPLETE under every hygiene standard tested — but it BREAKS at year 1, which is
> the finding, not a defect.
>
> Venue decided 2026-07-30: **TAE (Trust-AI-Eval), 8 pages**, not the 4-page plan below.


**Target**: a NeurIPS 2026 workshop, **29 Aug 2026 AoE**, notification **29 Sep 2026**.
Primary: *Evaluation of Interactive Agents*. Backup same date: *Climate Change AI*.
Non-archival, so it does not burn a later archival submission. **Confirm scope + page limit on the
workshop's own page before writing — deadlines here are from a 2026-07 scan.**

**Why this one first**: every number below is already on disk. It costs zero GPU-hours and does not
depend on a single new run finishing. If the whole GPU campaign slips, this is unaffected — and its
notification lands before internship screening.

---

## The finding, in one sentence

> Enforcing a behavioural-theory norm on an LLM agent changes what the agent **says about the world**
> as much as what it **does** — and because the standard conformance metric conditions on exactly
> that self-reported state, the reported effect is part behaviour and part composition.

## Title candidates

1. *Governed agents revise the premise, not the policy* — direct, and states the mechanism.
2. *Conditioning on a post-treatment variable: what governance metrics for LLM agents actually measure*
3. *Enforcement moves the appraisal: a measurement failure in governed LLM agent-based models*

Prefer (1) for a workshop — it is the memorable claim. Keep (2)'s phrasing in the abstract.

---

## Abstract (draft — tighten to ~150 words)

> Runtime governance layers for LLM agents reject a proposed action, tell the agent which rule it
> violated, and ask it to choose again. Conformance gains from such layers are reported as evidence
> that the agent revised its action. We show that under sustained enforcement the agent also revises
> the **self-reported state the rule conditions on**. In a governed agent-based model with 432,083
> logged decisions across 14 model×testbed cells (9 LLM configurations, 3B–27B, two domains), we find
> that where enforcement pressure is high the governed and ungoverned arms differ by a mean of
> **38.1 percentage points in the prevalence of the appraisal the rule conditions on** — the same
> variable that forms the denominator of the standard conditional conformance statistic. Where
> enforcement pressure is negligible the difference vanishes (mean 0.8 pp, 9/9 cells). The metric
> therefore conditions on a post-treatment variable, and a published +23.0 pp conformance gain in
> this system cannot be attributed to behaviour alone. We identify what evidence would separate
> premise revision from selection, and note that our own logs cannot.

---

## Section plan (4 pages)

### 1. Introduction (~0.5 p)
Set up: governance/guardrail layers for LLM agents are proliferating (AgentSpec ICSE'26, agent
behavioural contracts), and the pattern is always **detect → tell the agent → let it retry**. Note
the 25-year normative-MAS lineage (regimentation vs enforcement; AMELI, OperA, MOISE+) so the
reviewer knows we know. State the gap: nobody has asked what the resulting conformance number
measures when the norm's antecedent is **something the agent itself reports**.

**Do not** claim the mechanism is new. Claim the measurement problem is.

### 2. Setup (~0.5 p)
- Governed LLM-ABM: agent proposes an action + a self-reported appraisal; validators screen it;
  ERROR ⇒ inject the violated rule and re-prompt, up to 3 attempts.
- Two testbeds, deliberately different in how tightly rules bind: irrigation (78 agents × 42 yr,
  dual-appraisal theory, 5-action space, tight allocation constraints) and household flood
  adaptation (PMT, 4-action space, loose constraints).
- 9 LLM configurations, 3B–27B, two open-weight families, 5 seeds, validators-on vs validators-off.
- The rule under study is of the form *IF self-reported scarcity is high AND capacity is high THEN
  the increase action is forbidden.* **Its antecedent is a variable the agent authors.**

Keep this section short and factual. It is not the contribution.

### 3. Result 1 — the appraisal moves (~0.75 p) ← **the paper**

**Table 1** (the whole argument, verified):

| regime | cells | enforcement pressure (% decisions rejected) | appraisal shift (pp) |
|---|---|---|---|
| high | 5 | 28.1 – 62.6 | **+38.1 mean** (+21.3 … +47.5, 5/5 positive) |
| low | 9 | 0.00 – 0.85 | **+0.8 mean** (−3.7 … +6.3) |

Per-cell numbers verified on disk:

| cell | % rejected | shift (pp) |
|---|---:|---:|
| irrigation ministral3:8b | 62.63 | +32.97 |
| irrigation gemma4:e4b | 56.29 | +43.38 |
| irrigation gemma3:12b | 49.52 | +21.26 |
| irrigation gemma3:4b | 39.10 | +45.50 |
| irrigation gemma4:e2b | 28.08 | +47.53 |
| flood gemma3:4b | 0.85 | −1.24 |
| flood gemma4:e4b | 0.47 | +6.25 |
| flood gemma4:26b | 0.12 | +2.92 |
| flood ministral3:3b | 0.09 | +2.04 |
| flood ministral3:8b | 0.02 | −3.69 |
| flood gemma3:12b | 0.02 | −1.64 |
| flood gemma3:27b | 0.00 | +1.22 |
| flood ministral3:14b | 0.00 | +0.48 |
| flood gemma4:e2b | 0.00 | +0.97 |

**Separation is complete** — every high-pressure cell exceeds every low-pressure cell. Say exactly
that, and **do not** claim a monotone dose–response: within irrigation the ordering is not monotone
(gemma4:e2b has the lowest pressure and the largest shift). The claim is a **regime separation**,
not a dose curve. Overclaiming here is the easiest way to lose the reviewer.

**Figure 1**: scatter, x = % rejected (log or split axis), y = appraisal shift, one point per cell,
marker by testbed. Two clusters, no overlap. This single figure is the paper.

The flood testbed is the **natural control**: same framework, same governance machinery, same audit
code, same prompt scaffolding — only the rules bind loosely. Its null result is what rules out
"artifact of the harness / parser / prompt."

### 4. Result 2 — why it breaks the metric (~0.75 p)
The conventional statistic is a **conditional** rate: violating actions ÷ decisions whose
self-reported appraisal is in the rule's antecedent. Enforcement moves the denominator. Concretely,
in this system the published pair is governed 36.05% vs ungoverned 59.07%, Δ = **+23.02 pp** — and
the denominator's prevalence differs by 45.5 pp in the same cell.

State the consequence precisely and without overreach: this is **conditioning on a post-treatment
variable**; the reported gain is not decomposable into behaviour and composition by the statistic as
defined. **Do not** assert a corrected effect size — you do not have one.

Show the alternative framings and that they disagree, which is the honest way to make the point:
computing the same quantity on the executed action rather than the proposed one moves the governed
figure from 36.05% to 0.86%. Two defensible definitions, an order of magnitude apart.

### 5. What we cannot tell, and what would settle it (~0.75 p) ← **credibility section**
Two mechanisms produce the same table:
- **premise revision** — the agent, told its action violated a rule predicated on high scarcity,
  reports lower scarcity and the same action then passes;
- **selection** — agents that report high scarcity trip the rule more often, so those decisions
  retry more, and retried decisions are a non-random subsample.

Our retry-stratified appraisal is **non-monotone** (0 retries 23.9% high, 1 → 57.6%, 2 → 58.1%,
3 → 39.4%), which is consistent with both and decisive for neither.

Then state the reason plainly, because it is itself a finding about instrumentation:

> The first-attempt appraisal is not recoverable from our logs. The proposal object is overwritten on
> every retry, so the recorded appraisal is the **post-correction** one on 100% of rows in all three
> of our domains. We have since added first-attempt logging; the discriminating experiment is a
> sample-matched arm ladder in which consecutive arms differ in exactly one property.

This section is what turns a suggestive number into a credible paper. **Do not** hide it in
limitations — lead with it here.

### 6. Implications (~0.5 p)
1. Any governed-agent result whose norms condition on model-authored state must report the
   **prevalence of the conditioning variable in both arms**. That is one extra number and it is
   currently reported by nobody, including us.
2. Norms with model-authored antecedents cannot be regimented in the normative-MAS sense — you cannot
   make the forbidden action impossible without first fixing the premise, which is itself an output.
   So for language policies, the regimentation/enforcement dichotomy is only half-available, and the
   available half is the gameable one.
3. Practical: prefer norms conditioned on **world state** over norms conditioned on **self-report**,
   or measure both arms' composition.

---

## Claims discipline — what must NOT appear

- ❌ "WARNING-level rules produce ~0% behaviour change" — architecturally forced in this system, not
  measured (a WARNING has no channel to the model). Verified; do not repeat it.
- ❌ Any monotone dose–response claim.
- ❌ A corrected effect size for the conformance gain.
- ❌ "premise revision" asserted as the demonstrated mechanism — §5 exists precisely because it is not.
- ❌ Framework novelty of any kind. The framework is the instrument; AgentSpec and normative MAS own
  the mechanism.
- ❌ "first to…" anything.
- ❌ Frontier-model claims — the corpus is two open-weight families ≤27B. State it as a limitation.

## Limitations to state proactively
Two open-weight families, no frontier models; one governance implementation; local backend is
non-deterministic at fixed seed and commit (so N-seed aggregates, not single-run comparisons); a
seed-labelling mismatch affects paired tests on 6 of 9 flood configurations, so flood is used only
for the null/control result, which does not depend on pairing.

## Artifact
State that the arm configurations, the analysis scripts and the per-cell table will be released.
**Do not** promise the decision corpus — it is not currently released, has no DOI or license, and
has an unresolved PII issue in git history. Promise only what is deliverable.

---

## Build steps (est. 4 working days, zero GPU)

1. **Freeze the numbers.** Turn the two ad-hoc analyses into one committed script emitting the
   per-cell table + Figure 1, so every number in the paper is reproducible by one command.
2. Confirm workshop scope, page limit, format, and anonymity from its own page.
3. Draft §3–§5 first (the evidence), then §1–§2, then the abstract last.
4. Related work: AgentSpec (ICSE'26), agent behavioural contracts, and the normative-MAS lineage;
   plus the group's own WRR 2026 predecessor, cited in the first two paragraphs.
5. Internal red-team against the claims-discipline list above before submitting.

## Partition against the other manuscripts
This paper claims a **measurement** result about governed-agent metrics. The Nature Water manuscript
claims a **water-science** result from the same corpus (institutional rules change adaptation
behaviour), and the WRR 2026 predecessor claims the LLM-vs-traditional-ABM contrast. Different
claims from overlapping data is normal; declare the shared corpus in each, and do not let this paper
restate the water-science claim.
