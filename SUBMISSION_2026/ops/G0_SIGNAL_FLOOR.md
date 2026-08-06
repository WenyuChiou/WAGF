# Gate 0 — signal floor. **PASS.** Decided 2026-07-29, zero GPU.

Reproduce: `python SUBMISSION_2026/evidence/gate0_signal_floor.py`

## The gate

The campaign decomposes a conformance gain into five terms, each a difference between two arms. The
whole decomposition is therefore bounded by how much violation exists in the **untreated** arm. If
that is small, every term is small, the arms are statistically indistinguishable, and 333 GPU-hours
buys a table of nulls. Thresholds were fixed before looking: PASS ≥ 30 pp · MARGINAL 15–30 · FAIL < 15,
judged on the **worst** comparable model, not the mean.

## Result

| model | arm | \|E\| | V_intent | V_world |
|---|---|---:|---:|---:|
| gemma3:4b | untreated | 11,253 | **69.23%** | 30.90% |
| gemma3:4b | enforced | 4,721 | 44.55% | **0.00%** |
| gemma3:12b | untreated | 3,126 | **37.11%** | 32.79% |
| gemma3:12b | enforced | 1,451 | 42.11% | **0.00%** |
| gemma4:e2b | untreated | 10,337 | **38.05%** | 33.97% |
| gemma4:e2b | enforced | 7,074 | 22.01% | **0.00%** |
| gemma4:e4b | untreated | 12,693 | **47.86%** | 46.62% |
| gemma4:e4b | enforced | 8,143 | 33.37% | **0.00%** |
| ~~ministral-3:8b~~ | untreated | 3,535 | 23.34% | 22.60% | ← excluded |
| ~~ministral-3:8b~~ | enforced | 5,749 | 67.73% | **0.00%** | ← excluded |

**Comparable cells: mean 48.06 pp, minimum 37.11 pp → PASS.** Run the five-term ladder as planned.

## Exclusion, and why it is not post-hoc convenience

`ministral-3:8b` ships **3 governed seeds {42,43,44} against 2 untreated {42,43}**. A cell whose arms
do not share a seed set is not a comparable pair and cannot enter a paired contrast. That criterion
is a property of the *design*, checkable without looking at any outcome, and it would fire whichever
way the cell's numbers pointed.

It matters that it was the only unbalanced cell, because it was also the only cell with all three of:
the lowest untreated V, an enforced V *above* its untreated V (a reversal no other cell shows), and
an enforced set *larger* than its untreated set (every balanced cell's is smaller). All three are
what comparing unequal run counts looks like. Reported here rather than dropped silently.

Without the exclusion the verdict reads MARGINAL on that one cell. The honest statement is: **PASS on
four balanced cells, with one non-comparable cell excluded on a pre-stated design criterion.** Both
readings belong in the pre-registration.

## Two findings the gate surfaced, neither of which it was looking for

**1. `V_world` in the enforced arm is exactly 0.00% in all five models.**

Not "low" — *zero*, five times. On the enforced set, after governance, the executed action is never
an increase, because every attempted increase was blocked and `maintain_demand` executed instead.

This is the circularity objection in its sharpest possible form: the rule forbids exactly the action
the metric counts, so the executed-action violation rate is **structurally** zero rather than
empirically small. A reviewer can derive that 0.00% from the rule definition without seeing any data.

It is also the decisive argument for `V_intent` as the pre-registered primary outcome: an outcome
whose value is fixed by the rule's own definition cannot measure whether the rule changed behaviour.
Report `V_world` beside it always, and label it for what it is.

**2. The enforced set itself shrinks under enforcement, in every balanced cell.**

|E| goes 11,253 → 4,721 (gemma3:4b), 3,126 → 1,451, 10,337 → 7,074, 12,693 → 8,143. The set of
decisions the rule *applies to* is 26–58% smaller in the enforced arm. That is the same composition
effect the workshop paper reports, seen from the denominator's side, and it is independent
corroboration of it on a different quantity.

## Consequence for the campaign

- Proceed with the five-term ladder on irrigation. Signal is ample.
- `V_intent` is primary; `V_world` is reported as a definitional bound, not a measurement.
- Seed-set equality across arms becomes a **hard precondition** in the queue, not a hope — this cell
  is what that rule exists to prevent, and the shipped corpus has the same defect in 6 of 9 flood
  configurations.
- The anchor model should be `gemma3:4b`: highest signal (69.23 pp), cheapest (3.60 h/run), balanced
  at 5 seeds, and it is the cell the published pair comes from.
