# R32 — contribution stress test (three red-team reviews), 2026-09-21

**Purpose.** Before any writing, test whether the intended central claim
survives adversarial review with the evidence package as it stands
(r19–r28, Fig 2, Fig 3, Table 1, the 2026-09-17 literature sweep). Three
independent reviewers, each given the same files and the author's claim:
a socio-hydrology / coupled human–water ABM reviewer (opus), an ABM
methods reviewer (sonnet), an LLM-agent simulation reviewer (sonnet).

**Intended claim (author, 2026-09-20).** Not realism against real water
users. Each case is compared against a traditional ABM: the governed LLM
agents should catch trajectories similar to the traditional model, and
the validator's core contribution is behavioural coherence.

## Verdicts

| reviewer | verdict | one-sentence reframing |
|---|---|---|
| socio-hydrology | HOLDS WITH REFRAMING | The governance layer keeps the coupled system inside the operating envelope the traditional model also respects (remove it: demand ≈ 2.3× allocation, Mead at dead pool in 5/5 runs); the validator's measurable effect is on consistency of individual decisions with the agent's stated situation, in both domains and both model sizes, but it bounds only the actions the rules cover. |
| ABM methods | HOLDS WITH REFRAMING | Governance (validator + rule-specific retry) as a package reduces measured inconsistency; the near-zero governed IBR is partly definitional and the 0.95 KGE is on the easier series. |
| LLM-agent | HOLDS WITH REFRAMING | The validator's contribution is coherence of the final negotiated proposal, most pronounced on smaller open-weight models, not yet separated from a generic retry effect. |

## Objections, ranked by how many reviewers raised them and how damaging

1. **The coherence metric is scored partly on the validator's own output** (all three). `proposed_skill` is the last attempt (AUDIT_SCHEMA accepted gap); the strict rules gate exactly the appraisal–action pairs IBR counts; on gemma4:12b the governed IBR saturates at 0.000 while 73.6 % of decisions were sent back at least once. Package status: disclosed (r27 Method block), not resolved.
   Fixes: (a) reframe every governed-arm IBR as "last recorded proposal after validator-mediated retries"; (b) promote retry rate and terminal fallback share as the non-circular governance signal (note: gemma3:4b strict ends in fallback on ≈1.2 % of decisions, not the 38 % rejection rate one reviewer quoted); (c) one seed rerun with `initial_proposal_columns` on to quantify first-attempt vs last-attempt IBR (GPU, ≈3 h); (d) an environment-grounded coherence rate that does not depend on the self-report (CPU, r30).
2. **The Mead KGE is bought by the demand ceiling, not earned by agent behaviour** (socio-hydrology, strongest single objection; ABM methods in weaker form). Governed total basin demand is nearly constant (seed 42: sd 0.8 % of mean; max 6.071 MAF = the r22 breach maximum), both models share the seed-matched forcing, so the reservoir series correlate at r 0.998 regardless; basin-demand KGE is 0.18 (gemma3:4b) and −0.06 (gemma4:12b) against an FQL-vs-FQL floor of 0.38. Missing: a constant-demand, no-LLM null row.
   Fixes: constant-demand replay null (CPU, r29); basin-demand KGE and per-arm demand statistics into Table 1; if the null also scores ≈0.95, adopt the envelope reframing above.
3. **No control separating rule-specific feedback from a generic extra attempt** (ABM methods, LLM-agent). 100 % of strict-arm retries are validator-triggered; the ungoverned arm never retries; nothing shows that content-free "reconsider" feedback would not produce the same drop.
   Fix: a placebo-retry arm (flood gemma3:4b, 1–2 seeds, ≈1 h each) sending a generic reconsider message on the same schedule; needs a small, reviewed broker change. Otherwise the claim must be stated as governance-as-a-package.
4. **The conditioning population differs between arms** (socio-hydrology). Share of agent-years with self-reported high WSA: 37 % governed vs 82 % ungoverned (gemma3:4b), 28 % vs 76 % (gemma4:12b); several Fig 2b/3b cells are n<30 in one arm only. The reviewer's own cut on `drought_index ≥ 0.35` keeps the gap (39 vs 58 %; 2.4 vs 12.8 %). Fix: r30 with denominators shown.
5. **Flood relocation is implausible and uncovered by any rule** (socio-hydrology). 15.7 % (governed) and 13.8 % (no-validator) of agent-years relocated, 0.3 % in rule-based; ≈25 households of 100 leave within a decade, one to two orders above managed-retreat rates; governed relocates slightly more. Fix: report relocation share in the main text as the framework's own demonstration that validators bound only what they cover; recompute flood coherence and JS with relocate excluded (CPU, r31); a common-action-set diversity number or an explicit sentence that no diversity comparison is made.
6. **Scale claim rests on two points; no frontier model** (LLM-agent). Fix: state as an observation between two models, not a trend; optional third open-weight size (e.g. a 27B-class run, one seed per arm) or the reframing "governance value for compute-constrained open-weight deployments".
7. **Literature gap wording** (socio-hydrology). The five closest works are "unclear / not stated" on pre-execution validation, from abstracts under rate-limited APIs. Write "not reported", not "not done", or read the five methods sections.
8. **Venue** (socio-hydrology). A WRR-class methods paper on this evidence, yes; a Nature Water paper needs a water-science result the reference model does not already give.

## What all three would praise

Pre-registered acceptance bands stated before regeneration and the one
miss reported; the destroyed corpus and the old seed labelling disclosed;
the FQL-vs-FQL self-comparison as the metric's noise floor; the r22 model
review and its ten Methods sentences; 8/8 irrigation contrasts and the
cross-model direction reproduced on a regenerated corpus; the review
rounds that caught overclaims (r23 hand-typed cells, r28 "never
relocates").

## Decisions taken 2026-09-21

- CPU analyses r29 (constant-demand null, demand statistics, basin-demand
  KGE), r30 (environment-grounded coherence with denominators), r31
  (flood without relocate; common-action-set diversity) commissioned.
- Reframing adopted provisionally: envelope rather than trajectory;
  coherence of the last negotiated proposal; validators bound only what
  they cover; transfer across two domains and a 3× model-size change.
- GPU items (first-attempt rerun; placebo-retry arm) await the author's
  decision.
