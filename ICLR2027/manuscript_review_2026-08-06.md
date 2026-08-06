# Revision plan — ICLR 2027 manuscript, 2026-08-06

One ordered list. Written for the author and for Codex. Read-only session: nothing under
`ICLR2027/submission/` was edited, `broker/` was not touched, `SUBMISSION_2026/TAE/runs/` was not
opened.

Every number below was re-derived in this session from the shipped supplement or the evidence layer,
except where marked **[not independently verified]**.

---

## 0. The page budget, measured before anything is recommended

The instruction was to establish where the bibliography starts before recommending additions. It is
measured, not estimated.

| fact | source |
|---|---|
| PDF is 10 pages | `paper/manuscript.log:593` — `Output written on manuscript.pdf (10 pages, ...)` |
| bibliography begins on page **9** | `paper/manuscript.log:571` — `(manuscript.bbl [9]) [10]` |
| last body line sits at baseline **y = 259.0** on page 9 | text extraction, page 9 (`...paper does not claim bitwise reproduction of the historic runs.`) |
| text block bottom baseline is **y = 62.1** | identical on pages 1, 4, 8 and 9 |
| line pitch is **10.9 pt** | consecutive baselines on every page |
| page 10 has **37 lines free** (ends y = 463.1) | text extraction, page 10 |

**The paper is currently compliant.** Main text ends part-way down page 9; the ten bibliography
entries fill the rest of page 9 and the top of page 10. References do not count, so the extra PDF
page is not a violation.

**Slack = (259.0 − 62.1) / 10.9 = 18.1 typeset lines ≈ 270 words of body text.** Past that, body
spills onto page 10 and the paper is 10 pages of main text. References pushed off page 9 land on
page 10, which has room, and may run to page 11 at no cost.

**Working budget: 14 lines net (~210 words).** Four lines held back, because three of the six floats
are `figure*`/`table*` and adding text upstream can move a float onto a fresh page. Every item below
is costed in lines against this budget.

**Author check worth ~18 more lines.** ICLR 2024–2026 excluded the Ethics Statement and
Reproducibility Statement from the page limit. Nothing in this repository records whether ICLR 2027
does — `submission/SUBMISSION_CHECKLIST.md:56`, `submission/HANDOFF.md:161`,
`submission/VENUE_MATRIX.md:21` and `SUBMISSION_2026/TAE/DECISION.md:39` all say "9 pages excluding
references" and stop there. Those two statements occupy y = 453.1 → 259.0 on page 9, **17.8 lines**.
If they are exempt the budget roughly doubles. Verify against the CFP before spending it.

**Bibliography growth is free.** Ten entries today (`paper/references.bib`, 10 `@` records). Adding
20–30 pushes references onto page 11 and costs zero body lines.

**Net effect of this plan: about −2 lines.** Adds ≈ +7 (items 3, 5, 7, 15, 17), cuts ≈ −9 (items 9,
10). It fits with the whole 18-line slack still in hand for whatever the running experiment needs.

---

## 1. The author's question, answered

**No. The paper does not need a change of direction. It needs one clause of purpose and one change
of estimand, and those are different things.**

The model-fidelity argument is correct and it is already 80% written. The mechanism it depends on —
that governance moves the world state the later records are drawn from — appears five times:
`manuscript.tex:41` ("Governance can therefore alter the sequence of states from which later records
are drawn"), `:43`, `:149` ("These variables are outside the response being judged, but they are
downstream of governance"), `:205` and `:209`. What is missing is that all five are phrased as
contingencies — *can also change*, *can therefore alter*, *is downstream of* — and none says the
change is **intended**. The only purpose statement in the paper is the compliance one at `:26`:
"Runtime validators are intended to make language-model agents follow rules." The fidelity rationale
is absent from the entire submission tree, not just the body: a case-insensitive search for
`fidelit|plausib|behavioural theor|behavioral theor|protection motivation` across every `.tex` and
`.md` under `ICLR2027/submission/` returns zero files. So the fix is small, and it is worth making —
it separates "the governed-vs-ungoverned contrast is a bad score" from "validators are a bad
modelling device", and only the first is the paper's claim.

**But the framing is not free, and this is the part worth the author's attention.** It opens a
question the paper currently answers three times and never next to the question: *if governance must
change the world, does any cross-arm comparison survive?* Today the paper never asserts that
governance must, so the question is only implicit at `:41`. Assert it in the abstract and the
question moves to §1, where the answer has to be adjacent — it is the year-1 result at `:153`
(+3.33 pp, p = 0.261, nine matched pre-decision columns, 390 paired agent-years), which currently
sits mid-paragraph as mechanism evidence and is never labelled as the thing that survives.

**And the framing collides with the paper's primary estimand.** The fidelity argument is a claim
about what reaches the world. The paper's headline metric is a rate over `last-proposed` actions
(`manuscript.tex:70`), and in the anchor irrigation cell **39.49% of governed decisions were
rejected** (`supplement/table1_cells.csv`, `pressure_gov = 39.4933`), on which
`SUBMISSION_2026/TAE/evidence/_data.py:651-671` is explicit: the registry default `maintain_demand`
ran instead and `yearly_decision` still names the blocked proposal. So on roughly two in five
governed records the primary reading names an action the world never saw. Adopt the fidelity framing
as prose alone and a reviewer gets to say: your validator's job is the world trajectory, and your
headline number is a rate over actions that never reached it. Adopt it together with item 3 below
and the objection disappears, because the executed reading is then on the page.

Short version: **one clause of purpose (item 4), plus report the executed contrast (item 3). Nothing
moves, no section is rewritten, no result is dropped.**

---

## 2. The ordered list — before the run lands

Ordered by value per hour, not by section. Everything here is stable under whatever the running
experiment returns.

---

### 1. Fix the flood enforcement range `0--0.85%`
**Where** `manuscript.tex:97`; `supplement/enforcement_pressure_source.json`;
`source/cross_testbed_summary.py:81-83`.
**Cost** 0 lines. **Time** ~30 min. **Why first:** it is contradicted by the paper's own shipped
supplement, and a reviewer who opens one CSV finds it.

`manuscript.tex:97` says "Flood governance rejects 0--0.85\% of proposed actions". The shipped
`supplement/table1_cells.csv` gives flood `pressure_gov` of `1.0707, 0.4898, 0.1201, 0.1086, 0.0242,
0.0205, 0.0, 0.0, 0.0` — **max 1.0707%, not 0.85%** (that maximum is the gemma3:4b cell with the B6
run included). Lane 2 recomputed the B6-excluded maximum as **0.638%** — **[not independently
verified in this session]**, but either basis contradicts 0.85.

The pinned value is not a computation. `supplement/enforcement_pressure_source.json` states
`"flood": [0.0, 0.85]` and, in its own `note`, *"this metric is not recomputed from
flood_control_contrasts.csv"*; its cited source is `ICLR2027/LIVE_STATE.md`, which is prose.
`cross_testbed_summary.py:81-83` then asserts the pinned pair, so the guard enforces the unverified
number instead of checking it.

**Do:** recompute `rejection_pressure` on the B6-excluded governed run set — the same exclusion
`flood_control_contrasts.py:50-58` requires of any flood statistic — print the value, put it at
`:97`, and rewrite `enforcement_pressure_source.json` to record the computation rather than the pin.
The irrigation half is fine: `pressure_gov` spans 28.09–62.63, so `28--63\%` stands.

**One clause to add while there.** `:97` compares two validator-on rejection shares but does not say
so. The *no-validator* irrigation arm rejects a comparable fraction on a separate eligibility check
— Lane 2 measured 29.04% in the anchor cell **[not independently verified]** — and
`source/fig1_rule_layers.py:30-36` already warns that any "the water right still binds" sentence must
be scoped or panel B falsifies it. Say "validator-on arm" in the sentence.

---

### 2. Fix the Reproducibility Statement
**Where** `manuscript.tex:226`. **Cost** 0 lines (sentence for sentence). **Time** ~30 min.
**Why second:** two of the three simulated reviewers found it in under a minute, and it is in a
formal ICLR section.

The manuscript says a pre-submission audit "flags three historical smoke manifests as
`git_dirty=true`". Those three are smoke runs; no paper number comes from them. The paper's actual
corpus is the file it ships: `supplement/reproducibility_inventory.csv`, 42 rows (21 governed + 21
no-validator irrigation runs). Counted this session: **27 rows `git_dirty=True`, 15 rows with no
manifest fields at all (`git_commit` absent), zero clean.** Every headline number comes from runs in
that table.

**Do:** replace with the true counts. Suggested, same length:

> The supplement's run inventory records 27 of 42 irrigation runs with a dirty working tree at
> execution and 15 with no recorded commit, so this paper does not claim bitwise reproduction of the
> historic runs.

Understating this is the cheapest credibility loss available in the draft. Correcting it costs
nothing and pre-empts the "self-audit that did not audit itself" reading.

---

### 3. Report the executed all-decision contrast for all five irrigation cells
**Where** `manuscript.tex:184`; Table 1 at `:105-116`; abstract `:28`.
**Cost** +0 to +2 lines. **Time** ~1.5 h. **Why third:** highest-value substantive change per hour
in the plan, and it does not require demoting anything.

The paper already reports **one** executed number, for one cell, in one clause (`:184`, "the
gemma3:12b all-decision contrast becomes $+27.82\pp$") and draws no conclusion. All five are already
computed and shipped in `supplement/table1_cells.csv`. Verified this session:

| cell | all-decision Δ, `last-proposed` | all-decision Δ, executed |
|---|---:|---:|
| gemma3:4b | +21.62 | **+29.90** |
| gemma3:12b | **+0.16** | **+27.82** |
| gemma4:e2b | +15.25 | +28.84 |
| gemma4:e4b | +8.52 | +36.57 |
| ministral3:8b | **−22.17** | **+20.26** |

The abstract's two most dramatic claims — "changes one contrast from $+11.44$ to $+0.16$" and
"reverses its sign in another" — are both properties of the `last-proposed` reading. Under the
executed reading every cell is positive and the five sit in a 16-point band.

**Do the cheap version, not the expensive one.** Add one Δ column to Table 1 (`Executed all-decision
Δ`) — the table has room in width and its height does not change — and rewrite `:184` so the
sequence is: the conditional contrast, the `last-proposed` all-decision contrast (including the
collapse and the reversal, which stay), then the executed contrast for all five. Two sentences.

This neutralises the strongest objection any measurement-literate reviewer can raise, and it
strengthens the paper's own thesis rather than weakening it: *three readings of the same corpus, three
different answers, and the one whose denominator and numerator are both fixed by the world is the
stable one.*

**Machinery note for Codex.** `SUBMISSION_2026/TAE/evidence/table1_cells.py:122-128` already computes
the executed blocks through the same `_stat_block` as every other statistic — CIs, t, df and p exist
in memory. Lines 465-466 write them with `full=False`, which drops those columns. Changing `full=False`
→ `full=True` on those two lines and re-running gives per-seed CIs and p-values for the executed
contrasts with no new data. That script reads the corpus and writes `table1_cells.csv` in the
**shared** evidence tree (`LIVE_STATE.md:44`), not `broker/` and not `runs/`; announce the change in
writing, as that boundary requires.

**Whether to go further — make executed *primary* — is the author's call.** See §5, item 1.

---

### 4. The purpose clause — the author's framing
**Where** `manuscript.tex:26`, `:28`, `:41`, `:72`. **Cost** net **−10 words** (see funding below).
**Time** ~1 h.

Four small edits, no new paragraph, nothing reordered.

**(a) `:26`, abstract, sentence 1.** Add the fidelity purpose beside the compliance purpose. ~12
words. The current sentence gives only "intended to make language-model agents follow rules".

**(b) `:28`, abstract.** Split, do not swap. The sentence "Since governance changes world state, the
comparison is descriptive." is the abstract's *only* statement that the reweighting is not a causal
adjustment, and §4 at `:149`/`:151` leans on the reader having it. Replacing it with a claim removes
the disclaimer while §4 still assumes it. So: the claim (*governance changes world state because
that is what the validator is for*), **then** the retained "the reweighting is descriptive, not a
causal adjustment." ~15 words.

**(c) `:41`, the Rosenbaum paragraph.** This is where "by construction rather than by accident"
belongs — it is already the Rosenbaum paragraph, so no new paragraph is created. Purpose clause plus
a forward pointer to what survives (item 5). ~25 words.

**(d) `:72`, §2.** One clause naming what the studied rule encodes. Today the rule is described
purely mechanically ("It blocks an increase in demand only when the agent reports both high or very
high water scarcity and high or very high coping capacity") and justified structurally. If the
fidelity claim is asserted in the abstract it has to be grounded in the actual rule here, or it is an
assertion with no referent. ~15 words.

**Funding: cut the two sentences at `:39` that the Figure 1 caption already carries.**

- `:39` — "The diagram abstracts the rule logic; it does not mean that a high-scarcity report alone
  is blocked." vs `:61` caption — "a high-scarcity report alone is not a blocking condition."
- `:39` — "The conceptual diagram omits the retry and next-context paths for clarity; the Evaluation
  Setting and limitations describe their role, including the missing first response before a retry."
  vs `:61` caption — "The observation-to-next-context loop and retry branch are omitted for clarity;
  the Evaluation Setting describes them, and the frozen corpus does not preserve the first response
  before a retry."

Both are near-verbatim duplicates. Cutting the body copies frees ~45 words and loses nothing.

**Citations.** "Governance changes world state because that is its function" is a design statement,
not an empirical one. No number in this corpus can establish design intent, and none needs to — but
`references.bib` contains no ABM or behavioural-theory entry, so at ICLR it will read as an
unsupported assertion. 1–2 entries required. This is the one part of item 4 that cannot be done in
an hour; see item 14 and the fabrication warning there.

---

### 5. Label the year-1 result as the comparison that survives
**Where** `manuscript.tex:153`. **Cost** ~+0.5 line (≤8 words). **Time** ~20 min.

`:153` reports that at year 1, before actions separate the worlds, the arms match on nine
pre-decision columns across 390 paired agent-years, with a +3.33 pp share contrast (p = 0.261). I
re-derived this from `supplement/fig2_mechanism.csv:2` (`value 3.3333, lo −3.7501, hi 10.4167,
p=0.2614, n=5`).

This is the paper's only falsification test and the only cross-arm comparison the fidelity framing
cannot undermine — at year 1 the worlds are identical by construction. It currently appears
unlabelled, mid-paragraph, doing service as support for "the large later gap is therefore consistent
with accumulated world-state composition." Once item 4 asserts that governance *must* change the
world, this sentence is the answer to the question that assertion raises, and it has to read as one.

Add a naming clause. Do not add a sentence — the budget does not need it and the paragraph does not
want it.

---

### 6. `up to three attempts` is off by one
**Where** `manuscript.tex:70`. **Cost** 0 lines. **Time** 5 min.

`examples/irrigation_abm/config/agent_types.yaml:52` sets `governance.max_retries: 3`, and
`broker/core/_retry_loop.py:236` is `while not all_valid and retry_count < self.max_retries` — three
retries *after* the initial proposal, so up to **four responses**. Lane 2 reports `retry_count ∈
{0,1,2,3}` in the governed anchor arm from `e1` **[not independently verified]**; the config and the
loop condition were verified here.

Write "up to three retries" or "up to four responses". In a paper about a measurement pipeline, an
off-by-one in the description of that pipeline is expensive out of proportion to its size.

---

### 7. The two significant reversals drawn in Figure 3a and absent from the text
**Where** `manuscript.tex:153` or `:155`. **Cost** +2 lines. **Time** ~30 min.

`supplement/fig2_mechanism.csv`, panel A, verified this session:

- year 4: Δ = **−18.46 pp**, CI [−27.08, −9.84], **p = 0.0040** (gov 82.82%, noval 64.36%)
- year 7: Δ = **−6.41 pp**, CI [−8.36, −4.46], **p = 0.0008** (gov 6.92%, noval 0.51%)

Both are plotted in Figure 3a. Grepping `manuscript.tex` for `18.46`, `6.41`, `year 4`, `year 7`,
`reversal` returns nothing. The year-4 reversal is roughly four times the largest residual in
Table 3, which the paper reports to two decimals.

A reviewer who reads the figure sees a significant reversal the text does not mention. One sentence
naming both and saying the yearly series is non-monotonic — which is exactly what "accumulated
world-state composition" predicts — turns a concealment risk into supporting evidence.

---

### 8. Soften or defend the dose-response clause at `:97`
**Where** `manuscript.tex:97`. **Cost** 0 lines (rewording). **Time** ~30 min.

`:97` says the cross-testbed gap is "consistent with the difference being tied to how often the rule
stack changes the record stream". The natural within-setting version of that check goes the other
way. Computed this session across the five irrigation cells in `supplement/table1_cells.csv`:

| pair | Pearson r (n = 5) |
|---|---:|
| `pressure_gov` × `high_delta` | **−0.55** |
| `pressure_gov` × `cond_delta` | **−0.72** |
| `pressure_gov` × `uncond_delta` (last-proposed) | **−0.78** |
| `pressure_gov` × `uncond_exec_delta` | −0.23 |

Higher enforcement, smaller contrast. n = 5 and nothing is significant, so this refutes nothing — but
it is 30 seconds of work from a file the paper ships, and the sentence invites it.

Two honest options: (a) narrow the clause to the cross-*setting* comparison it is actually about
(flood's rule stack rarely binds at all; the within-irrigation range 28–63% is a different regime),
or (b) state the within-setting check and its n. Option (a) is cheaper and sufficient.

**Aside worth one clause somewhere.** The last row above also defends item 3: if the executed
all-decision contrast were mechanically produced by the `maintain_demand` substitution, it would
track enforcement pressure. At r = −0.23 it does not.

---

### 9. Cull the hedge stack
**Where** `:50`, `:120`, `:151`, `:160`, `:189`, `:211`. **Cost** **−4 lines**. **Time** ~1 h.

*descriptive* appears 14 times and *causal* 10, almost always inside a denial. The scope condition is
restated at `:41`, `:45`, `:50`, `:54`, `:97`, `:120`, `:149`, `:151`, `:153`, `:155`, `:160`, `:189`,
`:211`, `:215` — three of those in figure captions alone. Past the third restatement the hedge stops
reading as precision about scope and starts reading as uncertainty about the finding, which is
backwards: the finding is not uncertain.

State it once and in full at `:54`, where it already lives. Delete the restatements at `:50`, `:120`,
`:151`, `:160`, `:189`, `:211`. Keep `:97` and `:215`.

This is the single largest page saving in the plan and it improves the register at the same time.

---

### 10. Cut the Figure 1 caption
**Where** `manuscript.tex:61`. **Cost** **−6 lines**. **Time** ~30 min.

Measured on page 3: the caption occupies 13 typeset lines (baselines 495.2 → 363.7) for a
non-data conceptual figure. It carries four separate disclaimers, three semicolons and two colons.
Cutting to ~95 words gives ~7 lines and removes three of the fourteen hedge restatements counted in
item 9.

Second-cheapest page win available, and it does not touch a claim.

---

### 11. Unify the terminology
**Where** throughout. **Cost** 0 lines. **Time** ~1.5 h. **Good Codex task** — mechanical, verifiable
by grep.

Three drifts, all of which a reviewer reads as carelessness:

- **The paper's central concept has five names.** `agent-written` (`:37, :39, :45, :61`),
  `agent-authored` (`:72` ×2, `:144`, `:198`), `agent-reported` (`:70, :100, :138, :205, :215`),
  `self-report`-conditioned (`:74` ×2, `:138`), `reported` (`:70, :74, :138, :144`). Only the first
  is defined — in italics at `:37`. The Reporting Protocol at `:198`, which is the paper's actual
  deliverable, uses `agent-authored`, which is never defined. Pick `agent-written` and replace
  globally.
- **Two arms have four names**: `validator-on`/`validator-off` (`:28, :78, :80`), `no-validator`
  (13 uses), `governed` (13 uses), and `on`/`off` in the Table 1 header (`:107-108`) against
  "governed / no-validator" in Table 3 (`:165`). The abstract switches within three sentences.
- **`cell` (22 uses) and `configuration` (12 uses)** denote the same object. `cell` is spreadsheet
  vocabulary from the experiment matrix; `configuration` is what an ICLR reviewer writes.

Also abstract-only strings the body never uses: "seed-paired" (body: "paired by seed"), "finest
grouping" (body `:151`: "A finer grouping"; Table 3 `:174`: "Finest reported rung"), "full coverage"
(body: "100\% coverage").

---

### 12. Banned words and register
**Where** as listed. **Cost** 0 lines. **Time** ~30 min.

The word pass has largely been run: zero em-dashes, and none of *yet / Critically / Crucially /
Importantly / Ultimately / Together / Although / Moreover / Furthermore / delve / leverage / robust /
novel / paradigm*. Remaining hits:

| line | fix |
|---|---|
| `:26` | sentence-initial **Because** → split into two sentences |
| `:155` | sentence-initial **Because** → "Governance affects retries, and the filtering can…" |
| `:72` | sentence-initial **Thus,** → "A block therefore marks…" |
| `:43` | sentence-initial **However,** → delete; the contrast is already carried |
| `:211` | **Finally,** → delete |
| `:50` | "the **large** raw contrast is **greatly** reduced" → use the numbers: "+45.73 pp to −2.53 pp" |
| `:95` | "a **substantially** different population" → "a population 45.73 pp larger" |
| `:151` | "**small relative to** the raw contrast" → "−2.53 pp against a raw +45.73 pp" |
| `:155` | "a **useful** but limited sensitivity check" → "one sensitivity check" |

Also: six `, so ` constructions meaning "as a result" (`:37, :54, :86` ×2, `:209, :226`) read
conversational at that density; and `:39`, `:72`, `:78`, `:182` each exceed one colon **and** one
semicolon per paragraph.

---

### 13. Trim and repurpose the abstract
**Where** `manuscript.tex:26-30`. **Cost** net 0. **Time** ~45 min. **Do this after items 1–8** —
several of them change what the abstract should say.

Fourteen quantities in ~250 words, one every 18 words. Two specific cuts:

- **Drop `43.4\%` and `36.4\%`.** These are coverage figures for a secondary estimate under a
  stratification the abstract never defines. A reader cannot use them. "…and +0.21 pp in a finer
  grouping covering under half the decisions" does the same work.
- **Round the four range endpoints.** `−3.66 / +6.24 / +21.27 / +47.53` spends four two-decimal
  numbers to make one point — no overlap. Table 2 has the precision.

That frees ~25 words. Spend them on the two things the abstract omits, both of which change how a
reviewer reads it: **the year-1 matched-world check** (item 5 — it answers the first objection anyone
will raise), and the **enforcement-pressure scope condition** as corrected in item 1 (it tells a
reader whether the problem is theirs).

One inconsistency to fix while there: the abstract gives one decimal for coverage but withholds the
number for the sign reversal ("and reverses its sign in another"). That reversal is −22.17 pp against
a conditional +2.80. Give the number or drop the clause.

---

### 14. Expand the bibliography
**Where** `paper/references.bib`. **Cost** **0 body lines** — references are excluded and page 10 has
37 free lines. **Time** 2–4 h.

Ten entries. The field norm is 30–60. Two of the ten (ReAct, SWE-agent) appear only inside the
seven-citation sweep at `:35` and do no work. This is the item the simulated area chair reacted to
most strongly, and the gap is substantive rather than decorative:

- **No behavioural-theory / ABM-fidelity entry**, which item 4 requires or its claim is unsupported.
- **No principal stratification** (Frangakis & Rubin 2002) — the standard tool for exactly the
  counterfactual the paper leaves open at `:50` ("whether the agent would report the same condition
  in the same world").
- **No selection-bias or collider literature beyond Rosenbaum.**
- **No published benchmark or leaderboard that actually conditions on a model-authored field.** This
  is the load-bearing absence. `:72` justifies the target metric with "the condition used by the
  frozen analysis" — the authors' own prior pipeline. Without an external example the practice being
  critiqued exists only in this project's prior work. See §5, item 3: if no such example exists, the
  claim should be scoped rather than propped up.

**Hard constraint.** Every entry must resolve to a DOI or arXiv ID that was actually retrieved. This
repository has a recorded incident of a subagent fabricating 12 of 14 added references despite being
told to stop when a source could not be found. Run the `verify-references` skill on the result, and
do not let a delegate add entries unverified.

---

### 15. Disclose the flood corpus defects
**Where** `manuscript.tex:211` (the provenance paragraph). **Cost** +2 lines. **Time** ~45 min.
**Partly the author's call — see §5, item 5.**

Flood is the paper's only evidence that the irrigation effect is not an instrument artefact. Two
documented defects sit under it and appear nowhere in the manuscript.

**(a) Reflection confound, repo-graded CRITICAL.**
`examples/single_agent/results/_DATA_DEFECTS_2026-05-30.md` §A, verified this session:

> "No-validator flood Run_1/2/3 (seeds 42/43/44) for 6 models lack reflection while all governed runs
> have it. Affected: gemma3_4b, gemma3_12b, gemma3_27b, ministral3_3b, ministral3_8b, ministral3_14b."

In six of nine flood cells the arms differ in a **second** way besides the validator toggle, on three
of five no-validator runs. The lower endpoint of the paper's flood range, **−3.66** (ministral3:8b,
`:97`, `:130`, `:160`), comes from an affected cell. Only the three gemma4 cells are clean per the
same file. For a paper about comparisons whose arms differ in more than the treatment, an undisclosed
second arm difference in the control testbed is the first thing a reviewer will find.

**The same file also carries the paper's best defence, and it should be quoted rather than buried:**
"Irrigation ALL 5 models: reflection both arms, config diff = only governance_profile, audit 100% =
3276" and "Irrigation headline gemma3_4b: 5 matched pairs, fully clean." The defect is flood-only;
the identifying testbed is clean.

**(b) Flood audit coverage.** `supplement/table1_cells.csv`, `audit_coverage_pct_min` per flood cell:
`70.5, 73.6, 81.5, 85.7, 86.3, 95.2, 96.7, 99.1, 99.9`. Up to 29.5% of a run's decisions never reach
the audit CSV. The manuscript states irrigation's "3,276 decisions per run" (`:78`) but gives no
flood per-run n anywhere, so the reader cannot see this denominator at all. `:211`'s "the Flood
artifacts have source-history limitations" does not cover it.

One clause in favour of the paper, worth stating because it makes the disclosure cheaper: flood's
governed arm censors the appraisal on retry-exhausted rows (blank `construct_TP_LABEL`, counted as
not-HIGH — `LIVE_STATE.md`, disclosure (a)). That biases flood's governed high-share *down* and so
biases the flood contrast *up*, toward irrigation. At ≤1% enforcement pressure the effect is
negligible, but its direction makes the separation claim conservative rather than flattering.

---

### 16. Fix the supplement's paired statistics for flood
**Where** `supplement/table1_cells.csv`, via `SUBMISSION_2026/TAE/evidence/table1_cells.py`;
`supplement/README.md`. **Cost** 0 body lines. **Time** ~1 h.

Verified this session: all nine flood rows ship `n_paired = 5`, `paired_units = 1|2|3|4|5` and a
paired t-test p-value (`high_p` from 0.0214 to 0.9354), while six of those same rows record
`manifest_seeds_aligned = False`. The manuscript states twice that flood is "a descriptive
cross-testbed check rather than a paired causal comparison" (`:120`, `:211`). The supplement ships
paired inference for the comparison the paper says is not paired.

`supplement/README.md` flags only the gemma3:4b row, as a B6 sensitivity record, and says nothing
about the paired columns on the other eight.

Either suppress the paired columns for the six non-aligned cells or annotate them in the CSV and the
README. Body text unchanged.

---

### 17. Two accuracy repairs in §4
**Where** `manuscript.tex:151`, Table 3 at `:173-174`. **Cost** +1 line. **Time** ~30 min.

**(a) The sign of the residual is never explained.** `−2.53` means the **governed** arm reports *more*
high scarcity after reweighting, and Table 3's per-seed interval `−3.12 [−5.56, −0.68]` excludes
zero. The manuscript's hedge — "small relative to the raw contrast" — is true and does not tell the
reader that the full-coverage residual is significantly non-zero in the opposite direction. Six words
fix it.

**(b) The main text reports two of five rungs, and they are the two most favourable-looking.** Lane 2
reports the intermediate rung (tier + Mead elevation, 25 ft) at `−4.47` pooled / `−4.95 [−8.29,
−1.62]` per-seed at 81.9/70.5% coverage, present in
`supplement/WORLD_REWEIGHTING_DIAGNOSTICS.md` and absent from the body **[not independently
verified]**. `−4.47` does not threaten the argument against `+45.73`; selective rung reporting does.
One clause — "the intermediate rungs fall between these; all five are in the supplement" — removes
the appearance at no cost.

---

## 3. After the run — do not draft these twice

The 11-hour real-LLM run started 2026-08-05 23:20 and is expected ~10:30 today
(`LIVE_STATE.md:19`). It records the appraisal the agent wrote at attempt 0, before the retry loop
reassigned it — the field `manuscript.tex:207` says is absent from the frozen corpus. Early signal at
262 traces: `initial_labels` non-empty on 99.6% of rows and 100% of retried rows, against a >95%
gate (`LIVE_STATE.md:33-35`).

**Do not write any of the following until the results slot in the main handover is filled in.**
`LIVE_STATE.md:37` says `PLAN.md` §5 already pre-authorises the extra writing day, so there is no
schedule reason to guess.

| line | what it currently says | why it moves |
|---|---|---|
| `:30` | "Missing first responses prevent us from determining whether the agent would report the same condition in the same world" | the run measures exactly this |
| `:50` | contribution bullet 2, "…remains unresolved" | may become resolved, partly or wholly |
| `:51` / `:201` | protocol item 4, "store the first response before a retry" | goes from a recommendation to a demonstrated one |
| `:54` | scope disclaimer, "cannot identify within-decision report revision" | direct |
| `:151` last sentence | "the analysis does not show that an agent would report the same condition in an identical world" | this is the residual's interpretation |
| `:207` | the whole "main limitation" paragraph | rewritten or largely cut |

**Reserve 6 of the 18 slack lines for whatever the result needs.** A second mechanism — a
within-decision revision channel measured directly — is likely to want a short paragraph and possibly
a display item, and it should not have to be paid for by re-cutting text already tightened.

One framing note that will matter when the result lands, from `LIVE_STATE.md:117-121`: under the
fidelity framing the −2.53 pp residual has a clean reading — it is what is left after the *legitimate*
channel (governance changed the world; agents reported the changed world accurately) has been removed.
The run measures whether any of it is instead a within-decision revision channel. That sentence is
worth writing once, after the number exists.

**Interaction with item 4.** The purpose clause is safe to write now — it does not depend on the run.
The forward pointer inside it (item 4c) should point at the year-1 result, which is stable. Do not
make it point at the first-attempt result before that result exists.

---

## 4. What I would not do

The page budget makes cutting as valuable as adding, and several plausible-sounding items cost more
than they buy.

1. **Do not restructure §4 or §5, and do not move any section.** The mechanism is already stated five
   times; §4 supplies the evidence for the world-divergence half of the claim and §5 supplies the
   denominator half. A restructure would have to justify itself by relocating one of them, and
   neither needs to move. Every recommendation above is an in-place edit.

2. **Do not add a fifth figure for flood.** `LIVE_STATE.md:245-247` already reasons this out: it
   separates the control from the claim it exists to defend and costs a display item. Table 2 plus
   panel (d) is the right size, and both already exist.

3. **Do not put the remaining three reweighting rungs in the main text.** The supplement is the right
   place. Item 17(b) fixes the selective-reporting appearance with one clause; a rung table would cost
   4+ lines to say something the argument does not need.

4. **Do not fix the `+40.24` / `+40.25` rounding difference** between `table1_cells.py` and
   `e4_world_fixed_decomposition.py`. Cosmetic, invisible to a reviewer, and it costs attention that
   items 1–3 need.

5. **Do not manufacture a citation for "other people report conditional conformance rates."** If no
   published example exists, the honest move is to scope the claim (§5, item 3), not to prop it up.
   The repository's own fabrication incident is the reason to be explicit about this.

6. **Do not adopt the fidelity framing as prose alone while `last-proposed` remains the only reading
   on the page.** That combination is worse than either half: it asserts the validator's job is the
   world trajectory while the headline metric counts actions that, in 39.49% of governed anchor
   decisions, never reached the world. Items 3 and 4 travel together.

7. **Do not re-run any experiment, do not start a GPU job, and do not edit `broker/` or anything
   under `SUBMISSION_2026/TAE/runs/`** (`LIVE_STATE.md:21-26`). Nothing in this plan requires it.
   Figure regeneration via `source/cross_testbed_summary.py` reads only CSVs
   (`supplement/FIGURE_REGENERATION.md`) and is safe; `table1_cells.py` reads the corpus from disk and
   writes to the shared evidence tree, which is safe but must be announced in writing.

8. **Do not merge item 15's flood disclosure into the abstract.** It belongs in `:211`. The abstract
   is already at one quantity per 18 words and item 13 exists to reduce that.

---

## 5. The author's calls, not writing decisions

Seven. Each is a claim the author may not want made, or a framing they may reject. Codex should not
resolve any of these unilaterally.

**1. Should the executed reading become *primary*, or only be reported (item 3)?**
*For:* it removes the strongest available objection, it converts a negative result ("every
denominator gives a different answer") into a positive one ("here is the estimand that survives every
choice we tried"), and its stability is not an artefact of enforcement — r(pressure, executed
all-decision Δ) = −0.23 across the five cells.
*Against:* on rejected rows the executed action is `maintain_demand` **by construction**
(`_data.py:671`), so a large positive executed contrast is partly mechanical wherever enforcement
binds. It measures how often the validator fired at least as much as how the agent behaved. And the
paper's `:182` position — "Neither is automatically the corrected answer. They answer different
questions" — is a defensible one, not a dodge.
*My read:* report all five (item 3, cheap, no downside) and decide primacy separately. Reporting them
captures most of the value without committing to the harder claim.

**2. Is the paper willing to assert design intent — "governance changes world state because that is
what the validator is for"?** It is not derivable from this corpus and is not falsifiable by it. It is
a statement the authors are entitled to make about their own framework, and it needs 1–2 citations it
does not currently have (item 14). If the answer is no, item 4 shrinks to the compliance-vs-modelling
distinction alone, which is still worth writing and still removes the "attacking your own apparatus"
misreading.

**3. Should the paper name an external example of a conditional conformance rate, or scope the
claim?** `:72` justifies the target metric with "the condition used by the frozen analysis" — the
authors' own prior pipeline — and `references.bib` contains no governance-evaluation paper reporting
such a rate. Under the current framing this is a soft spot; under the fidelity framing it hardens,
because a reviewer will ask who ever thought the conditional rate *was* the evaluation. Either find a
real example or scope the contribution to "evaluations built this way", explicitly. Do not leave it
implicit.

**4. Disclose the irrigation provenance, or not?** Lane 2 reports 6 of 21 seed-pairs recording
different commits across arms and 8 of 21 with at least one arm unprovenanced; Lane 4 reports that the
anchor gemma3:4b cell is clean (paired commits differ only in `__pycache__`) while gemma4:e4b has
three pairs differing by thousands of lines including `broker/core/_retry_loop.py` and
`broker/validators/governance/base_validator.py` — **[neither independently verified in this
session]**; what I did verify is the 27/15/0 inventory counts behind item 2. The paper never claims
"same code state", but a paired design plus a paired t invites the reading, and `:211` currently
attributes non-contemporaneity to Flood only. Costs ~2 lines to disclose; costs credibility to omit.

**5. Disclose the flood reflection confound (item 15a)?** It is repo-graded CRITICAL and it touches
the cell supplying the flood range's lower endpoint. Disclosing weakens the control the paper needs
most; not disclosing leaves a finding that is one file away from any reviewer who looks. My read: the
honest version is also the stronger one, because the same file certifies irrigation clean and that
sentence is worth having on the page — but it is the author's judgement whether flood survives the
disclosure as a control.

**6. Disclose the ministral3:8b no-validator seed-44 provenance?** Lane 2 reports that run executed
2026-08-03 on an off-main branch commit, three months after its cell-mates, and that it supplies §5's
−22.17 pp sign reversal — **[not independently verified]**. Note the interaction with call 1: if the
executed reading is promoted, the sign reversal becomes a diagnostic rather than a headline and the
provenance issue shrinks with it.

**7. Do Ethics and Reproducibility statements count toward the 9 pages?** ~18 lines of budget turn on
it (§0). Nothing in this repository records the answer. One CFP check.

---

## 6. Honesty notes

**Verified in this session, from the shipped files:** the page and bibliography geometry in §0 (from
`manuscript.log` and PDF text extraction); the 27/15/0 reproducibility inventory counts; flood
`pressure_gov` max = 1.0707 in `supplement/table1_cells.csv` against the pinned 0.85 in
`enforcement_pressure_source.json`, including that file's own "not recomputed" note; all five executed
all-decision contrasts and their `last-proposed` counterparts; the year-4 and year-7 reversals with
their p-values; the year-1 result; flood `audit_coverage_pct_min` for all nine cells;
`manifest_seeds_aligned = False` on six flood rows that nonetheless ship `n_paired = 5` and a paired
p; 10 bibliography entries; `governance.max_retries: 3` and the loop condition at
`_retry_loop.py:236`; the absence of fidelity/behavioural-theory vocabulary anywhere under
`ICLR2027/submission/`; the `:39`-vs-`:61` duplication; the four correlations in item 8; the
`_DATA_DEFECTS_2026-05-30.md` §A text and its irrigation-clean certification;
`table1_cells.py:465-466` `full=False` as the reason executed CIs are missing from the shipped CSV.

**Taken from the lane reports and marked in place, not independently re-derived:** the 0.638%
B6-excluded flood rejection maximum; the 29.04% no-validator irrigation rejection share; the
`retry_count ∈ {0,1,2,3}` distribution; the 6-of-21 cross-arm commit mismatch and the gemma4:e4b diff
sizes; the ministral3:8b seed-44 branch provenance; the `−4.47` intermediate reweighting rung.

**Could not be traced to a machine-readable source inside `ICLR2027/submission/`:** the `+43.15\pp`
two-condition contrast at `:72` (25.46% / 68.61%). It appears only as prose in
`submission/REVIEW_ROUNDS.md:23`, described there as a frozen anchor value. It is recomputable —
`SUBMISSION_2026/TAE/evidence/e6_antecedent_conjunction.py` produces it — but it is not in the shipped
package, and `:72` is one of the lines item 4 edits. Worth pinning while that edit is made.

**No lane failed.** All four returned usable work; where two lanes disagreed on emphasis (Lane 1
argues the framing needs ~70 words of prose, Lane 4 argues it needs an estimand change) the
disagreement is resolved in §1 rather than averaged.

**Nothing was modified.** Read-only throughout, including `broker/`, `SUBMISSION_2026/TAE/runs/` (not
opened at all) and every file under `ICLR2027/submission/`. This plan is written to
`ICLR2027/manuscript_review_2026-08-06.md`, outside the `submission/` tree Codex owns.
