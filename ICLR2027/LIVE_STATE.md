# LIVE STATE — read before editing anything. Claude → Codex, 2026-08-06.

**This file exists because of a pointer problem, and the pointer problem is worth one paragraph.**

`submission/HANDOFF.md:11-13` says `SUBMISSION_2026\TAE\HANDOVER.md` "is historical TAE material and
must not be used as the current venue or figure instruction." **That was correct when you wrote it at
21:46 and it is still correct for venue and figures.** But since ~01:00 on 2026-08-06 that file also
carries the live operational state — a running experiment, a write boundary between us, and a read
receipt. A rule that was right when written, still applied after its premise moved, is the exact
defect this paper is about; this file is the cheap fix rather than editing yours.

**Full detail: `SUBMISSION_2026/TAE/HANDOVER.md`, the `LIVE STATE` section at the top.** Everything
below is the part that cannot wait for you to get there.

---

## 1. 🔴 An 11-hour real-LLM experiment is running. Four prohibitions.

Started 2026-08-05 23:20, expected ~10:30 today. At the time of writing it is at year 13 of 42.

| do not | consequence |
|---|---|
| **edit anything under `broker/`** | the runner re-imports the package in subprocesses; an edit can kill it at hour 9 |
| **touch `SUBMISSION_2026/TAE/runs/`** | the process is reading its config and writing its output there |
| **start another GPU job** | a second model evicts the resident one and inference silently falls back to CPU — 12× slower, four hours lost to this on 2026-05-13 |
| **let Windows Update reboot** | paused to 2026-08-10; a reboot killed a run at year 10 once |

Read progress without touching anything:
`SUBMISSION_2026/TAE/runs/_logs/seed42.log` — grep `^--- Year`.

**Why it matters to your paper:** it records the appraisal the agent wrote at attempt 0, before the
retry loop reassigned it. That is what §8 admits is absent from the shipped corpus. Early signal at
262 traces: `initial_labels` non-empty on 99.6% of rows and **100% of retried rows**, against a >95%
gate.

**Do not write anything that depends on its answer until the results section of the main handover is
filled in.** `PLAN.md` §5 already pre-authorises the extra writing day, so there is no schedule
reason to guess.

## 2. Write boundary — you keep the paper, I keep the plumbing

| | owner |
|---|---|
| `ICLR2027/submission/**` — manuscript, figures, checks, your working `.md` files | **Codex** |
| `broker/`, `examples/`, `.gitignore`, repository plumbing | **Claude** |
| `SUBMISSION_2026/TAE/evidence/**` | **shared** — say in writing which file you changed and why |
| `SUBMISSION_2026/TAE/runs/**` | **nobody, until the run finishes** |

I have not written to `ICLR2027/submission/` and will not. This file, at the `ICLR2027/` root, is the
one exception and it is a pointer, not content.

## 3. Three things settled since your last handoff

- **Destination confirmed: ICLR 2027 main track**, written into `SUBMISSION_2026/TAE/DECISION.md`.
  Deadline 25 September 2026 AoE. **9 pages excluding references.**
- **Scope confirmed: LLM arms only** — validator-on against validator-off. No rule-based, no
  fuzzy-Q, no non-LLM comparator. Not a preference: the paper's denominator is agent-written and a
  non-LLM policy files no such report, so the quantity is undefined for that arm. `_data.py:173-176`
  already raises on any other arm name.
- **The Nature Water baseline's label was corrected in code**, not in either paper — it is fuzzy
  Q-learning, and `run_fql_baseline.py`'s docstring had called it "rule-based". Irrelevant to your
  manuscript; noted so you do not inherit the wrong word.

## 4. What I think is worth your next hour, in order

1. **The bibliography: 6 entries.** This is the largest acceptance risk in the draft and it is **free
   in pages** — ICLR's 9-page limit excludes references, and the current PDF is 9 pages *including*
   its bibliography, so entries displace nothing. The field norm is 30–60.
   **Every entry must resolve to a DOI or arXiv ID you have actually retrieved.** This repository has
   a recorded incident of a subagent fabricating 30% of the references it added — 12 of 14 — despite
   being told to stop when a source could not be found.
2. **Report the flood result. It is the paper's answer to the most damaging objection available, and
   right now it is being paid for and not used.** Expanded in §6 below — numbers, the blocker, and
   the three disclosures that must travel with them.
3. **Nothing watches the page count.** `SUBMISSION_2026/TAE/paper/submission_gate.py` hardcodes 8
   pages and TAE's CFP, reads only the TAE manuscript, and reports PASS for a venue that no longer
   exists. `submission/checks/manuscript_static_check.py` counts pages per figure, not for the
   document. I can add a document-level page gate on the ICLR side if you would rather not — say so
   in your handoff and I will treat `submission/checks/` as mine for that one file.

## 4b. The framing point the author raised, 2026-08-06 — worth a sentence in §1 and one in §5

**You have the flood numbers in the abstract already, using the B6-excluded figures. Good.** This is
a different thing, and it is about what the validators are *for*.

The abstract opens: *"Runtime validators are intended to make language-model agents follow rules."*
That is the **compliance** framing. In an agent-based model it is not the main one.

**The author's account, and it is the design rationale of the framework this corpus comes from:** an
agent that reports "I am worried about scarcity" and then asks for more water is not *breaking a
rule*. It is **not behaving like a person**. Thousands of such decisions make the simulated reservoir
trajectory a model of nothing. **The validator's first job is model fidelity — keeping agents inside
what the behavioural theory says humans do — so that the world the model produces means something.**

**Why this needs to be in the paper.** As written, a reviewer who builds water models — or the
advisor whose group built this framework — can read the paper as attacking the design rationale of
its own apparatus. It is not. **The paper criticises using the governed-versus-ungoverned contrast as
an evaluation score. It does not criticise using validators as a modelling device**, and one sentence
in §1 separating the two uses removes the misreading entirely.

**And it converts an apology into a claim.** The abstract currently says:

> *"Since governance changes world state, the comparison is descriptive."*

That reads defensive, as though world divergence were a confound you were caught by. Under the
author's framing it is the opposite:

> Governance changes world state **because that is what it is for**. Blocking incoherent extraction is
> why the governed reservoir holds at 989 ft while the no-validator reservoir reaches dead pool at
> 895 ft in every seed. **That is the mechanism working.** And it is precisely why a cross-arm
> conditional rate is not an evaluation of the agent: the two arms have been made, deliberately, into
> different worlds.

Same facts, same numbers, no new claim. It stops being a limitation you concede and becomes the
reason your own decomposition in §5 is the right analysis rather than a rescue.

**One consequence for §5's residual.** After reweighting to the same recorded world state the gap is
−2.53 pp at full coverage and +0.21 pp in the finest grouping — near zero but not zero. Under this
framing that residual has a clean interpretation: it is what is left after the *legitimate* channel
(governance changed the world, agents reported the changed world accurately) has been removed. **The
running experiment measures whether any of it is a within-decision revision channel instead.** Same
agent, same moment, same world state — no divergence possible. That is the one measurement that can
separate the two, and it is why the results slot is empty rather than guessed at.

## 5. One small suggestion about your own gate

`checks/figure1_geometry_report.json` reports `status: "PASS_MANUAL_VISUAL_REVIEW_REQUIRED"` while
`text_overlap_count` and `route_intersection_count` are both `null`. Labelling it that way rather
than plain `PASS` was the right instinct — but anything grepping for `PASS` still matches it, and in
a paper about checks that report success while validating the wrong thing, that is a poor field
value. `NEEDS_VISUAL_REVIEW` would read correctly to both a human and a grep.

The visual review itself is done: the figure reads correctly, the circularity is legible, and
omitting the retry branch was the right call. One minor note — the Validator orange and the condition
amber are close in hue for a colourblind reader, mitigated by their spatial separation.

---

## 6. The flood arm — keep it, and start reporting it

**The author asked whether flood should be dropped from ICLR. The answer is no, and the reason is
that flood is the control that makes the irrigation result defensible.**

### The objection flood answers

A reviewer's cheapest attack on this paper is:

> *Your +45.73 pp shift is an artefact of your framework. Of course a system that blocks a proposal
> and re-asks produces different reports.*

Flood is the same harness, the same governance code, the same audit path, the same appraisal column,
on nine models in a different setting. **If the shift were an instrument artefact, flood would show
it.** Measured, per-run-mean basis, `construct_TP_LABEL` in {H, VH}:

**The numbers are below, under "from one source" — one table, not two.** An earlier draft of this
file carried a second copy here and the two drifted apart within the hour when BACKLOG B6 was
settled. Duplicating a table is how that happens; there is now one.

**Flood spans −3.66 to +6.24, mean +0.75. Irrigation spans +21.27 to +47.53, mean +37.80.**
The ranges do not touch; the gap is **15.03 pp**.

And the mechanism is visible rather than asserted: flood's enforcement blocks 0–0.85% of actions,
irrigation's blocks 28–63%. **The shift tracks enforcement pressure, not the instrument.**

### Why the current state is the worst of both

The abstract already claims flood — `manuscript.tex:28`, *"across nine models … in irrigation and
flood settings"*. **Note that "nine models" is the flood count; irrigation has five.** So dropping
flood costs the model-diversity claim as well, and `:193` already concedes "the model set is small".

Meanwhile the body reports no flood number. So the paper currently pays the *"why were nine
configurations run and none reported"* question **and** forgoes the control's benefit. Either
direction is better than where it sits.

### The instrument gate, and BACKLOG B6 — settled

`e2_flood_instrument.py` — the B5 gate deciding whether the two flood arms measured with the same
instrument — returns **IDENTICAL INSTRUMENT** and rules that *"flood deltas MAY be printed, on the
per-run-mean basis"*. Everything here is on that basis. **A pooled-row computation over the same
corpus gives different figures and must not be used** — I made that mistake once and it moved the
gemma3:4b cell by 0.08 pp before anyone would have noticed.

Its closing line flagged B6 as blocking: *"B6 FLIPS THE SIGN of the gemma3:4b flood cell (−1.16
with Run_1, +0.35 without) — decide it BEFORE any flood number is printed."*

**Decided by the author, 2026-08-06: the run is EXCLUDED.** `JOH_FINAL/gemma3_4b/Group_C/Run_1`
(`BACKLOG.md:70`) ran a different prompt — four response fields, no MULTI-ACTION block, 2,480
characters against 2,972 in its four siblings — so it is not a replicate of the same condition and
is not averaged into a per-run mean. The cell is **+0.35**.

The separation was never at stake: −1.16 and +0.35 both sit well inside the flood range, whose
extremes are ministral3:8b and gemma4:e4b either way.

### Three disclosures the gate says must travel with any flood number

Its words, not mine:

- **(a)** the with-validators arm censors the appraisal on retry-exhausted rows — blank
  `construct_TP_LABEL`, 100% `REJECTED_FALLBACK`. **Blanks are not HIGH and stay in the denominator.**
- **(b)** the arms are **not contemporaneous** and some runs pin no commit. A provenance defect for
  §8, already bounded in the gate's own §5.
- **(c)** every label statistic must case-normalise. `_data.appraisal()` already does.

### What I suggest, in one paragraph you can adapt

> The same validator stack, applied in a setting where enforcement rarely binds, produces no
> comparable shift. Across nine flood configurations the high-appraisal share contrast spans −3.66 to
> +6.24 pp (mean +0.75), against +21.27 to +47.53 pp across the five irrigation configurations; the
> ranges do not overlap. Flood governance rejects 0–0.85% of proposed actions and irrigation
> governance rejects 28–63%. The shift therefore scales with enforcement pressure rather than with
> the measuring apparatus, which the two settings share.

### Where flood goes visually — checked, and only one of the three figures can take it

All three data figures are irrigation-only: `flood` appears **zero** times in `fig1_rule_layers.py`,
`fig2_mechanism.py` and `fig3_consequence.py`.

**`fig3_consequence` cannot take flood, and this is not a layout problem.** It plots conditional
against unconditional **increase-rate** deltas. Flood's action set is
`do_nothing / buy_insurance / elevate_house / relocate` — **there is no "increase".** The quantity
does not exist in that setting. Do not try.

**`fig2_mechanism` can.** Its panel (A) already plots exactly the quantity that transfers: the
per-year Δ in HIGH-appraisal prevalence. That measure is about the *appraisal*, not the action, so it
is defined identically in both settings — which is precisely why it works as a control. And fig2 is
the paper's core figure, so the control would sit beside the claim it defends, where a reviewer looks
for it.

**My recommendation, in order of what I would do first:**

1. **A table, or a two-line addition to Table 1.** The claim is a *separation of ranges*, and a table
   states ranges more precisely than a plot: flood −3.66 to +6.24 (n=9), irrigation +21.27 to +47.53
   (n=5), no overlap. **Costs no display item**, which matters while the body is at the page limit —
   though see §4.1: that constraint loosens as the bibliography grows, since references do not count.
2. **Then, if space allows, a fourth panel on fig2** — the fourteen cells on one axis, irrigation
   clustered far from zero, flood clustered on it. The separation is visually stark and a strip plot
   would land harder than a table. fig2's layout is `gs[0,0] / gs[1,0] / gs[:,1]`, so this is a grid
   change rather than a redesign.
3. **Not a standalone fifth figure.** It would separate the control from the claim it exists to
   defend, and cost a display item to do so.

### The numbers, from one source, on the one permitted basis

**`ICLR2027/flood_control_contrasts.py` → `flood_control_contrasts.csv`.** Read the CSV; do not
recompute. The gate permits flood deltas **on the per-run-mean basis only**, and a pooled-row
computation over the same corpus gives different figures — I made exactly that mistake before writing
the script, and it moved the gemma3:4b flood cell from −1.16 to −1.24.

Cross-checked: the script's irrigation anchor is **+45.73**, matching `manuscript.tex:93` to the
digit, and its B6-excluded flood figure is **+0.35**, matching what `e2_flood_instrument.py` reports
independently. Two computations, same answers.

| setting | model | with validators | no validator | contrast |
|---|---|---|---|---|
| irrigation | gemma3:4b | 37.08% | 82.80% | **+45.73** |
| irrigation | gemma3:12b | 5.49% | 26.76% | +21.27 |
| irrigation | gemma4:e2b | 18.26% | 65.79% | +47.53 |
| irrigation | gemma4:e4b | 45.27% | 88.65% | +43.38 |
| irrigation | ministral3:8b | 13.56% | 44.69% | +31.13 |
| flood | gemma3:4b | 30.95% | 31.30% | **+0.35** † B6 run excluded |
| flood | gemma3:12b | 2.55% | 0.93% | −1.63 |
| flood | gemma3:27b | 19.16% | 20.38% | +1.22 |
| flood | ministral3:3b | 31.19% | 31.04% | −0.15 |
| flood | ministral3:8b | 30.54% | 26.88% | **−3.66** |
| flood | ministral3:14b | 19.45% | 19.92% | +0.47 |
| flood | gemma4:e2b | 27.42% | 28.39% | +0.97 |
| flood | gemma4:e4b | 43.48% | 49.71% | **+6.24** |
| flood | gemma4:26b | 17.44% | 20.36% | +2.92 |

**irrigation n=5, +21.27 to +47.53, mean +37.80 · flood n=9, −3.66 to +6.24, mean +0.75**
**Separation COMPLETE. Gap between min(irrigation) and max(flood): 15.03 pp.**

### Option 1 — the table, if that is all you want

Two rows appended to Table 1, or a standalone four-row block:

| setting | n | with validators | no validator | contrast range | mean |
|---|---|---|---|---|---|
| irrigation | 5 | 5.49–45.27% | 26.76–88.65% | +21.27 to +47.53 | +37.80 |
| flood | 9 | 2.55–43.48% | 0.93–49.71% | **−3.66 to +6.24** | **+0.75** |

One sentence beneath it does the work: *the ranges do not overlap; flood governance rejects 0–0.85%
of proposed actions and irrigation governance rejects 28–63%.*

### Option 2 — the fig2 panel, specified so it needs no decisions

**Panel (D), one axis, fourteen points.**

- **x**: contrast in percentage points, symmetric enough to show zero clearly — roughly −10 to +55.
- **y**: the fourteen cells, **flood first (top), irrigation below**, each group sorted ascending by
  contrast. Grouping beats interleaving here: the eye should read two clusters, not fourteen labels.
- **markers**: reuse fig2's existing arm colours rather than inventing a scheme. One filled marker
  per cell; a horizontal whisker is not needed — these are per-run means and the spread is a separate
  claim.
- **a vertical rule at x = 0**, thin and grey. The flood cluster straddles it; that *is* the result.
- **the gap**: a light band spanning **+6.24 to +21.27** with the label `15.03 pp, no overlap`. This
  is the single most informative mark on the panel — the reader should be able to take the finding
  from it without reading an axis value.
- **the B6 cell**: **settled 2026-08-06 — the divergent run is excluded.** Plot flood gemma3:4b at
  **+0.35** and mark it with a footnote symbol keyed to the caption. Two things must be disclosed
  wherever that cell appears: its governed arm has **4 runs against the no-validator arm's 5**, so it
  is not a paired comparison and must not be called one; and any *other* flood statistic drawn from
  that cell elsewhere in the paper must apply the same exclusion or say that it does not.
- **do not annotate every point.** Label the two extremes of each group and leave the rest.

### Draft caption for the panel

> **(d) The same measure, in a setting where enforcement rarely binds.** Contrast in the prevalence of
> the high-appraisal report that the conditional rate selects on, computed per run and averaged, as
> $\Delta = \text{no-validator} - \text{with-validators}$. Nine flood configurations span
> $-3.66$ to $+6.24\pp$; five irrigation configurations span $+21.27$ to $+47.53\pp$. The ranges do
> not overlap. Both settings share the harness, the governance code, the audit path and this measure;
> they differ in how often enforcement binds — flood governance rejects 0–0.85\% of proposed actions,
> irrigation governance 28–63\%. $\dagger$ one governed run of this cell used a different prompt and
> is excluded, leaving four governed runs against five no-validator runs; including it moves the cell
> from $+0.35$ to $-1.16\pp$, inside the same range either way.

**I have built neither the table nor the panel. The figures are yours.** If you would rather I
produced the panel, say so in your handoff and I will treat `fig2_mechanism.py` as mine for that one
change — and I will not touch anything else in `submission/`.

---

**When you have read this, tick the receipt at the top of `SUBMISSION_2026/TAE/HANDOVER.md` and carry
on.** You do not need to wait for a reply. If you disagree with anything here, write it in your
handoff rather than working around it silently.
