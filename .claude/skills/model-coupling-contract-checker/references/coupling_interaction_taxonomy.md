# Coupling interaction-complexity taxonomy

When a WAGF agent layer is coupled to an external model, the model does
not just "return numbers". Its outputs **re-enter the agent's decision
context** and, in multi-agent runs, **feed a shared state that loops
back to every agent**. That feedback creates a small, fixed set of ways
the coupling can be silently wrong. This document enumerates them so
`model-coupling-contract-checker` (audit), `wagf-coupling-designer`
(design), and `wagf-domain-builder` (multi-agent build) all reason from
one shared list instead of rediscovering them per domain.

Every coupling has the same five exposure points (E1–E5). They are
written domain-general; the **disaster / catastrophe model** is the
running worked example because it is the hardest common case (a model
that returns per-agent loss *and* drives a shared fiscal pool).

## Running example: a catastrophe (flood-damage) model

Per simulated year the external CAT model consumes each agent's
protective state (insured? elevated? relocated?) and a hazard draw, and
returns, **per agent**:

- `flood_damage` — gross structural + contents loss this year (USD)
- `insurance_payout` — what the policy paid (0 if uninsured; depends on
  coverage, deductible)
- `oop_cost` — out-of-pocket = `flood_damage − insurance_payout +
  premium_paid + deductible`

and, **aggregated across agents**, a shared-state update:

- `pool_loss_ratio` — total payouts / total premiums → resets next
  year's premium for **every** agent
- `condemned[agent]` — structures the model flags unrepairable

`oop_cost` and "was I flooded" feed next year's risk perception →
next year's protective decision. That is the loop. The five exposure
points are where that loop breaks.

---

## E1 — Temporal sync

**Definition.** The agent deciding at year *t+1* must see the model
outputs *produced for year t*, not year *t−1* (or, worse, not year
*t+1*'s own not-yet-computed outputs).

**Disaster-model instance.** Owner is flooded in year 5: `flood_damage`
= \$80k, uninsured, `oop_cost` = \$80k. If the env-sync is off by one
year, the year-6 decision context still shows year-4's `oop_cost` = \$0
("no recent loss"). The agent rationally declines insurance — on
*stale* evidence. Across the run this produces a systematically
under-adapting population that looks like a behavioural finding but is a
coupling bug. **This is the Paper-3 stale-flood-depth bug
([T7](feedback_loop_traps.md), `lifecycle_hooks.py` dual-dict), restated
as a general coupling failure, not a flood-specific one.** (Note: T3
"phantom acceleration" is the opposite direction — reading an output
*too early*, same-step; E1 here is reading it *too late*, stale by a
step.)

**Detection question.** Trace the per-step order. Does
`agent.read(oop_cost)` for the year-*t+1* prompt happen *after* the CAT
model wrote year-*t*'s `oop_cost` into the same dict the agent reads?
Is there an explicit ordering guarantee, or does it rely on the
`pre_year` `self.env = env` aliasing convention?

**Multi-agent amplification.** Same failure, ×N agents, and harder to
spot: aggregate metrics still "look reasonable" while every agent
decides on stale evidence.

## E2 — Double-count

**Definition.** One physical quantity credited to two ledgers that both
appear in summary outputs.

**Disaster-model instance.** `flood_damage` is debited from the agent's
private asset register *and* added to an `env.total_damage` aggregate;
both surface in the results. The loss is counted twice. Or:
`insurance_payout` reduces agent `oop_cost` *and* is separately summed
into a municipal recovery ledger that also nets it out — the payout is
double-credited.

**Detection question.** For every `(damage, payout, cost)` field,
enumerate *every* downstream consumer. Exactly one consumer-of-record
per ledger field; all others must be explicitly marked
"diagnostic-only, excluded from paper totals". (Generic recipe:
[T2](feedback_loop_traps.md).)

**Multi-agent amplification.** `pool_loss_ratio` is computed from total
payouts; if individual payouts were already double-credited, the pool
ratio — and therefore *next year's premium for everyone* — inherits the
error and compounds.

## E3 — Intra-step operation ordering

**Definition.** Within one year, the model-side operations
(`flood_damage` → `insurance_payout` → `oop_cost` → risk-perception
input → memory write) must occur in a fixed order, and **the governance
layer must read the same vintage of state the agent's context shows**.

**Disaster-model instance.** A validator checks
appraisal-action consistency: "high financial-stress appraisal but
proposes drop-insurance". If the validator reads `oop_cost` *before*
`insurance_payout` is applied (= the gross \$80k) while the agent's
prompt showed `oop_cost` *after* payout (= \$5k deductible only), the
validator and the agent are judging different numbers. The consistency
check is incoherent — it may reject coherent behaviour or pass
incoherent behaviour.

**Detection question.** Is the sequence
`damage → payout → oop → appraisal-input → memory` pinned and
documented? Does every consumer (agent prompt, each validator, audit
trace) read the *post*-payout vintage, or is the cut-point unspecified?

**Multi-agent amplification.** The per-agent order must fully resolve
*before* cross-agent aggregation (E4) runs, otherwise the pool ratio
mixes pre- and post-payout numbers across agents.

## E4 — Multi-agent shared-state resolution

**Definition.** When N agents' actions feed one external model that
maintains a shared resource (insurance pool, government budget, aquifer
head, reservoir storage), the rule for resolving contention — who gets
paid when claims exceed the pool, how the budget is rationed, what
order agents' draws apply — must be **explicit and auditable**.

**Disaster-model instance.** Year 8: total claims \$12M, pool holds
\$9M. Who is made whole? Pro-rata? First-come by agent index? Does the
government backstop fire, and at what cap? In WAGF today this is
resolved by **ordered mutation of a shared `env` dict in
`lifecycle_hooks.py`** — agent 1's payout reduces the pool the model
sees for agent 400, *within the same year*, as an artefact of
processing order, and the resolution decision is **not routed through
the governance/audit pipeline**. The framework's core claim is
auditable governance; this is the one decision the audit does not see.

**Detection question.** Is there a declared, order-independent
conflict-resolution rule, recorded in the audit trace? Or is shared
state mutated in agent-loop order with no record? **Refuse to approve
any >1-agent coupling whose shared-state resolution is implicit
env-dict mutation.**

**Single-agent.** Not applicable (no contention).

## E5 — Validator depends on model state

**Definition.** A feasibility validator's verdict depends on a value
the external model produces. Then a stale or mis-scoped model output
corrupts **the governance layer itself**, not merely the agent's
reasoning.

**Disaster-model instance.** Rule: "cannot purchase insurance if the
structure was `condemned` by last year's flood." `condemned[agent]` is
a CAT-model output. If E1 (stale sync) is present, the validator
enforces condemnation on the wrong year's flags — blocking valid
proposals or admitting invalid ones. Compounding: WAGF's *builtin*
(Python) checks are **not agent-type-scoped** (only YAML rules are
scoped via `get_base_type`); a renter (cannot elevate at all) can be
judged by an owner-elevation feasibility check whose `blocked_skills`
name collides.

**Detection question.** List every validator whose verdict reads a
model-produced field. For each: is that field guaranteed current
(E1)? Is the validator scoped to the correct agent type?

**Multi-agent amplification.** Cross-type misfire is invisible at the
aggregate; one agent-type's governance can be silently wrong while the
batch looks healthy.

---

## The domain-general skeleton

Every coupled domain instantiates the same loop, so E1–E5 always apply:

```
agent decision ─▶ external model (has state) ─▶ per-agent outcome
                                              └▶ shared aggregate state
per-agent outcome ─▶ updates private context (next decision)
shared aggregate ─▶ loops back to ALL agents' context
validators ─▶ may read model-produced state to judge feasibility
memory/reflection ─▶ consolidates the outcome
```

| Domain | External model | Per-agent outcome | Shared state (E4) | Validator-depends-on-model (E5) |
|---|---|---|---|---|
| Flood adaptation | CAT / flood-depth | damage, payout, OOP | insurance pool, gov budget, CRS class | condemned, floodplain status |
| Irrigation | reservoir mass-balance | delivered diversion, curtailment | reservoir storage, shortage tier | water-right cap vs tier |
| Groundwater | aquifer drawdown | well yield, pumping cost | aquifer head (common pool) | well-failure threshold |
| Seismic | structural-damage | retrofit benefit, loss | recovery fund | red-tagged structure |
| Epidemic | transmission | infection, health cost | population susceptibility (herd) | quarantine eligibility |

If a new domain cannot answer the E1–E5 detection questions, the
coupling is not ready, regardless of how clean the unit/time-step
contract looks.

## Convention vs framework-enforced (honesty box)

As of 2026-05-16 (Paper-1b freeze), most of E1–E5 are guarded by
**convention and review, not by framework code**. Be explicit about
this with anyone reusing WAGF:

| Exposure | Today | Becomes framework-enforced |
|---|---|---|
| E1 temporal sync | `pre_year` `self.env = env` aliasing **convention** + this checker's refusal gate | Gate-3 (env-sync as asserted contract in `experiment_runner`/lifecycle) — post-Paper-1b |
| E2 double-count | reviewer + [T2](feedback_loop_traps.md) recipe | no structural guard planned; stays review-gated |
| E3 ordering | per-domain hook code, unspecified cut-point | Gate-3 (declared operation order in the coupling contract) |
| E4 shared-state resolution | ad-hoc ordered `env`-dict mutation, **not audited** | Gate-4 (activate + audit the coordination layer) — post-Paper-1b |
| E5 validator-depends-on-model + scoping | YAML rules scoped; **builtin checks NOT agent-type-scoped** | Gate-2/3 (builtin agent-type scoping) — post-Paper-1b |

"Framework-enforced in Gate-N" means: today it is your responsibility
as the integrator to get it right; the framework will not stop you from
getting it wrong until that gate ships. The checker skill's job is to
catch it at audit time in the meantime.

## How the skills use this document

- `model-coupling-contract-checker` — its Workflow E3/E4/E5 steps and
  Refusal Protocol cite this taxonomy; the disaster instances above are
  the worked examples.
- `wagf-coupling-designer` — its contract template forces the designer
  to answer the E1–E5 detection questions; the scaffolded adapter emits
  the E1 sync assertion.
- `wagf-domain-builder` (`multi_agent_walkthrough.md`) — its
  disaster-coupling worked example is the multi-agent (E4) instance of
  this taxonomy.
