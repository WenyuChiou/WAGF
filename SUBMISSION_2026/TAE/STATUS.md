# STATUS — the plan of record

> **Entry point is [HANDOVER.md](HANDOVER.md).** This file is a working record and its status
> claims go stale. Anything about whether something passes, is complete or is ready is measured
> by `evidence/corpus_inventory.py`, `evidence/run_all.py` and `paper/submission_gate.py` --
> prefer those three to any sentence here.

> **The NeurIPS 2026 TAE workshop named in this file was withdrawn by its organisers on 2026-08-05.**
> The 29 August 2026 deadline is dead. As of 2026-09-22 all top-conference submissions are paused;
> see `DECISION.md`.

**Written 2026-08-03. Replaces whatever was here before.**
Deadline: **29 August 2026, AoE** (end of day anywhere on earth). **26 days from today.**

This file is for you, not for an agent. It says where the paper is, what five reviews found,
what only you can do, and when. `DECISION.md` remains the decision of record for what the paper
claims. **`PLAN.md`'s day-by-day calendar is roughly two weeks overtaken — do not follow it**;
its forbidden-claims block and experiment fences are still live. This file is what to read first
each morning.

**Before trusting any status in this file, run the three checks.** They read the files on disk and
cannot go out of date the way this prose can:

```
python SUBMISSION_2026/TAE/evidence/corpus_inventory.py     # is the experimental material enough?
python SUBMISSION_2026/TAE/evidence/run_all.py              # are all the numbers still right?
python SUBMISSION_2026/TAE/paper/submission_gate.py         # is this ready to submit?
```

Counts that those three measure — how many scripts pass, how many pages, how many figures, how
many references, which fonts, which runs exist — have been **removed from this file on purpose**.
Earlier revisions carried three different pipeline pass counts on a single day. If you want a
number, run the command that produces it.

Facts marked **[checked today]** were confirmed by running the command or opening the file on
**3 August**. Several were later overtaken by fixes made the same day; where that happened the item
now says so. Treat the tag as "checked on 3 Aug", not as "true now".

---

## 1. Where the paper stands, in five sentences

1. **The argument.** A "guardrail" is software that checks an agent's proposed action against a
   rule and blocks it if the rule is broken; the field grades guardrails with a *conformance
   rate*, the share of actions that followed the rules. This paper shows that when the rule's
   condition reads something the agent itself reported, enforcement changes how often that
   condition is even true, so the conformance rate is measuring a moving target — and it is
   least trustworthy on exactly the runs where the guardrail worked best.
2. **The state.** The paper is fully written — sections, figures, tables, abstract, title and
   references are all real. Nothing is a placeholder any more. (The exact counts are deliberately
   not written here; `paper/submission_gate.py` measures every one of them against the built PDF,
   which is how the artifact statement's "all three figures" was caught when there were four.)
3. **The evidence.** Every number in the paper is produced by a script. The pipeline is **currently
   red**, for one reason: at 09:03 on 3 August a simulation run started writing a new, half-finished
   result folder into `examples/irrigation_abm/results/`. Several scripts read that folder, find it
   incomplete, and stop rather than compute a number from half a run. Nothing is wrong with the
   paper or the scripts — the guard is working as designed, and the moment that run finishes or is
   moved aside they go back to passing. Deciding what to do about that run is yours, not an
   agent's; it is item 1a in section 3.
   **Do not trust a pass count written in this file or any other.** Two commands measure it:
   `python SUBMISSION_2026/TAE/evidence/corpus_inventory.py` says whether the run has landed, and
   `python SUBMISSION_2026/TAE/evidence/run_all.py` says how many scripts pass right now. Both print
   the count themselves. Earlier revisions of this file carried three different counts on the same
   day, which is why none is recorded here any more.
4. **What is left.** Almost nothing on the paper itself. This item originally listed four
   defects — fourteen lines over length, a broken Figure 1, a font the venue rejects, and about
   six sentences that overclaimed or pointed at the wrong work. **All four were fixed the same
   day, after this file was first written, and each was re-verified on the built PDF rather than
   assumed [checked today]:** the body now ends on page 8, with the References heading and the
   first entry also on page 8 and page 9 carrying the remaining entries and nothing else;
   Figure 1's arm labels render and its caption describes the layout the figure actually has;
   the bitmap font the venue rejects is gone (though not every font ended up Type 1 — see the
   font item in section 2, which the submission gate corrected on 3 August); and the sentence about what
   guardrail papers report no longer claims anything unsupported about any of the four systems.
   **Later the same day a second pass added three things and paid for all of them [checked
   today]:** the paper now has a short Conclusion instead of ending on its own limitations; §3's
   heading no longer promises a result it does not deliver, and §1 now says what §3 is for; and
   §1 has a new paragraph placing the work in the measurement-validity literature, with three
   references, each one fetched and read twice by two people who did not share notes. The body
   still ends on page 8. It is now one typeset line longer than it was this morning, so anything
   further has to be paid for line by line.
   **Do not trust a slack figure written in prose.** This item once said "no slack left at all" and
   a note elsewhere claimed about nine spare lines; both were guesses, and they disagreed.
   `paper/submission_gate.py` derives it from the PDF's own text geometry — the last body baseline,
   the text block's bottom edge, and the body leading — and prints it as a number of body lines with
   its assumptions stated. Run it and read that number.
   **A third pass on 3 August reworked the two data figures and rebuilt the paper [checked today].**
   Figure 2's first panel had a middle bar that read like a third experimental arm when it is a
   subset of the bar above it; it is now indented, thinner, italic and separated by a rule, so it
   reads as belonging to the arm above. Its second panel now says in the title which bar is which
   arm, which it previously left to the reader. Its third panel had two numbers per row competing
   for attention and now has one. Figure 3 lost a grey half-panel that marked nothing and was named
   in no caption, and its third panel's heading now sits on the panel instead of floating beside it;
   the arrow in that panel, which had no explanation anywhere, is now named in the legend. Both were
   paid for in width, not height — **neither figure grew, and the body still ends on page 8**, which
   I checked on the rebuilt PDF rather than assuming. The underlying data files are unchanged, and I
   verified that by hash rather than by eye: all four are byte-for-byte identical to before the
   figures were touched, so nothing plotted or computed moved.
   Five decisions are now open, and all five are about **what the paper claims**, so no agent made
   them. They are listed in section 3 below, the two new ones first. No new experiments and no new
   data were commissioned — though one is running anyway, which is item 1a.
5. **The thing most likely to go wrong** is not in the paper at all. Submissions go through
   OpenReview, and the call for papers warns that creating an OpenReview account "can take up to
   two weeks." Our own plan schedules the first OpenReview test for **28 August — one day before
   the deadline.** If you do not already have an account, that is a two-week problem discovered
   with one day left.

---

## 2. The five things you asked about

> **Read this first.** The five reviews below ran at the same time as the repairs, so each one
> describes the paper as it was that morning. Everything they marked as blocking has since been
> fixed and re-verified on the built PDF. Where a finding is now closed it says **FIXED** on the
> spot. The findings are kept in full rather than deleted, because what was wrong is the record
> of why the paper now says what it says.

### Is the format right? — **Mostly, with two things that must change**

The paper uses the correct official NeurIPS template, unmodified, with the correct
double-blind workshop setting. Page size, column width, fonts, line numbers, section
numbering, figure captions, page numbers: all correct and checked against the template file
itself, not from memory.

Two problems:

**It was too long. FIXED.** The workshop allows 8 pages, not counting references and appendices.
The paper ran fourteen typeset lines past that — the tail of §8 plus the whole "Artifact
availability" statement, which is neither a reference nor an appendix and so counts. The fourteen
lines were taken back out of duplication rather than disclosure. **The body now ends on page 8 and
page 9 carries References only [re-checked on the built PDF].**

**One font is the wrong kind.** The PDF contains five letters — a, e, i, l, m, which spell the
word "email" — stored as a 600-dot-per-inch *picture* of letters rather than as letter shapes.
That kind of font is called Type 3, and the NeurIPS template says in plain words: "If your file
contains type 3 fonts... we will ask you to fix it." The five letters come from the template's
own anonymous author block, not from anything you wrote. **FIXED** with one line that changes the
typewriter family only — not `\usepackage{lmodern}`, the common shortcut, which would also have
changed the body font away from the Times the template requires. **The Type 3 font is gone — that
is the kind the venue actually blocks on, and the fix worked.**

**But "every font is now Type 1" was an overstatement, and the check caught it on 3 August.**
`paper/submission_gate.py` reads the fonts out of the built PDF and reports three that are
TrueType, not Type 1: DejaVu Sans in regular, bold and oblique, coming from the three matplotlib
figures. Matplotlib's `pdf.fonttype=42` — the setting used to kill the Type 3 — produces TrueType,
so the fix traded one non-Type-1 kind for another. **Nothing here is venue-blocking**, but the
project's own stated standard is not met. Two ways out, both in the gate's `WHAT TO DO`: set
`pdf.use14corefonts=True` in the figure scripts so they use Times and embed nothing, or accept
TrueType deliberately by running the gate with `--allow-truetype`, which prints the waiver rather
than hiding it. **Run the gate for the current answer; do not read it from this paragraph.**

Two smaller things: Figure 1 was never mentioned anywhere in the prose — **FIXED**, it is now
cited in §2's worked example. And every cross-reference in the paper ("Figure 3b", "Table 1", "§5") is a
hand-typed string rather than an automatic link. Every one is currently correct. But they are
fragile precisely while you are cutting fourteen lines out from under them.

### Is the section structure right? — **Yes. Do not restructure.**

The 1-to-8 sequence is the standard shape for this kind of paper, and it lines up almost exactly
with the closest published comparison (a 2025 paper auditing a well-known AI leaderboard). Four
sections each carrying one finding, under headings that state the finding rather than the method,
is the right architecture.

You asked specifically whether the missing "Related Work" section is a problem. It is not. The
prior-work material is in §1, where it is doing argumentative work rather than surveying — the
paragraph that distinguishes this paper from Gao et al. *is* the contribution claim, and it would
stop working if moved. At eight pages a separate section would cost half a page and buy nothing.

Three improvements worth making, in order of value:

- **§1 says "This paper reports four results" and then lists four — but the paper has five
  sections that report a result.** §3 is not on the list, and is not in the abstract either.
  Changing "four" to "five" and adding one clause looked like the highest value-per-line edit
  available.
  **RESOLVED the opposite way, and deliberately — see section 3, item 9.** §3 was judged to be
  setup rather than a fifth result, so its heading was changed instead (it now reads "Which rules
  read what the agent says") and §1 was given a clause saying what §3 is for. `manuscript.md`
  correctly still says **four**. Do not "fix" it to five; that would undo a decision, not a
  defect. The "[checked today]" tag this item used to carry predates the resolution.
- **The paper currently ends on its own limitations.** None of the four comparable papers does
  that. The fix is nearly free: the closing sentences are already written, in the wrong place, at
  the end of §7 ("The point outlasts this testbed..."). Move that paragraph to after §8.
- Several facts are stated three, four, even five times — the excluded configuration is explained
  in five separate places. That duplication is where the fourteen lines should come from. Not
  from §4, which the file's own notes name as the "sanctioned donor" but which is already *under*
  its planned length.

### Are the figures right? — **Yes, now. All four were repaired, the last two on 3 August.**

No figure ever disagreed with a number in the text — the review checked all four against their data
files and the prose and found zero wrong numbers. What was wrong was that three of them were hard to
read correctly, in ways that could mislead an honest reader. All of it is now **FIXED** and each fix
was re-checked on the built PDF rather than assumed.

**Where each figure stands today [checked today]:**

- **Figure 1** — the two defects described below are fixed: the arm labels render, and the caption
  now describes the layout the figure actually has.
- **Figure 2** — reworked on 3 August. Its middle bar in panel (a) looked like a third experimental
  arm when it is really a subset of the bar above it; it is now indented, thinner, italic, and cut
  off by a rule, so it reads as belonging to the arm above. Panel (b) never said which of each pair
  of bars was the validators-on run; the title now says so. Panel (c) had two numbers per row and
  now has one, so each row reads as a single figure.
- **Figure 3** — reworked on 3 August. A grey block covering half of panel (a) was removed: it was
  checked against the script, the layout note and both captions, named in none of them, and encoded
  no threshold or significance region, so it was decoration sitting on top of data. Panel (c)'s
  heading was floating loose beside the panel and now sits on it. The arrow inside panel (c) was
  explained nowhere at all — a reader's most natural guess, that it was an interval running off the
  axis, was simply wrong — and it now has its own entry in the legend.
- **Figure 4** — unchanged. It was already the strongest of the four.

Two things worth knowing about how those repairs were paid for. **Neither figure was allowed to grow
taller**, because the body ends on page 8 with nothing to spare; both were paid for in width
instead, and one attempt at a taller canvas was measured, seen to push References onto page 9, and
reverted. And **the underlying data did not move**: all four data files are byte-for-byte identical
to what they were before, verified by hash, so every repair was to how the picture reads and none to
what it reports.

The panel-(b) caption problem described at the foot of this section is also **FIXED** — the caption
now reads "band = per-seed min–max range and not a confidence interval" (`manuscript.md` line 373).

The original findings are kept below, because what was wrong is the record of why the figures now
look the way they do.

Best to worst: **Figure 4** is excellent — one claim, delivered instantly, every honesty caveat
visible inside the picture rather than hidden in the caption. **Figure 3** carries the paper's
central mechanism and gets the hard parts right. **Figure 2** is accurate and readable.

**Figure 1 does not work. — FIXED the same day; this is the record of the review, not a live
defect.** Both problems below were repaired and re-checked on the rebuilt PDF (section 3, item 6,
and the third-pass note in section 1). **Two warnings before you read it:** the "Figure 1" here is
the figure generated by `fig1_rule_layers.py`, which the manuscript now numbers **Figure 2** — the
schematic `fig0_problem_schematic.py` was inserted ahead of it afterwards and took the number 1.
And do not re-apply anything from this list; check the manuscript, or run
`paper/submission_gate.py`, which verifies figure count and freshness against the built PDF.

The two problems were:

1. **The labels that say which bar is which arm are invisible.** They exist in the file, but they
   are drawn underneath the bars and then painted over. So the figure ships with two bars, four
   percentages, and no way at all to tell which one is the governed run. It has no legend either.
   That is the whole point of a two-arm picture.
2. **The caption describes a figure that does not exist.** It talks about "the shaded part of each
   upper bar" and "the lower bars" — a two-tier layout the figure does not have — and it swaps
   which element carries which quantity. The figure's own printed annotation contradicts its own
   caption.

One more that is close to blocking: **Figure 3, panel (b)** shows shaded bands around two lines.
The caption says "band = 95% CI" (a confidence interval) for panel (a) and says nothing about
panel (b), while the shared legend displays a "95% CI" swatch. But panel (b)'s bands are not
confidence intervals — the data file records them as "lo/hi = seed range", the plain minimum and
maximum across runs. A reader is being shown one thing and told another. The caption must say so.

No figure disagrees with any number in the text. Every plotted value reconciles.

### Are the references right? — **Yes. One sentence about them is not.**

All eleven references were independently re-verified this pass, each against a freshly fetched
source page, several deliberately using different databases than the first check so the two
passes are not correlated. Nothing is fabricated. No field is wrong. Nothing cited is missing
from the bibliography and nothing in the bibliography goes uncited. **Three more were added later
the same day (see section 3, item 10) and were held to the same standard: fetched, read, and then
checked a second time by a pass that searched by title rather than by identifier. The list now
runs to fourteen and every entry is still cited, with nothing cited that is missing.**

The PolicyGuard question is **resolved**. Three different 2026 papers carry that name. All three
abstracts were read rather than guessed from titles: one reviews static contract documents, one
defends a reinforcement-learning controller (the word "policy" means something else there — that
is where the name collision comes from), and only the one we cite is a runtime verifier for
language-model agents. The citation is correct.

**The defect was in the paper, not the bibliography — and it is now FIXED.** The repair suggested
at the end of this item was applied; `manuscript.md:76` now reads "and the field scores success
with a conformance number, violations under enforcement against violations without it." The
"[checked today]" tag below was written before the fix landed and is wrong; the analysis is kept
because it is the reason the sentence reads as it does.

§1's opening paragraph used to say four guardrail systems "all report success as a conformance
number, violations before enforcement against violations after". That is false for three of the
four. NeMo Guardrails
reports no number at all — it is a demonstration paper whose only result sentence is "initial
results show that the proposed approach can be used with several LLM providers." PolicyGuard
reports task success and violation recall. SAVeR reports a faithfulness score. Only AgentSpec
reports conformance figures, and only after enforcement, never a before-and-after pair. An
NLP reviewer will know this. The suggested repair is the same length as the original: change
"and all report success as a conformance number" to "and the field scores success with a
conformance number."

### Is the author information handled? — **Yes. This one is clean.**

The author field is empty, the correct blind setting is on, and the compiled PDF prints
"Anonymous Author(s)". A full sweep found nothing: no name, no university, no email, no file path,
no repository link in the PDF text, in the PDF's hidden metadata, in any of the four figure PDFs,
or in any of the five figure images. No acknowledgements and no funding section, both of which
must stay absent until acceptance.

A switch has also been built into `build.py` for later. One line, `CAMERA_READY = False`, controls
whether the paper builds blind or with your name on it. ("Camera-ready" is the final version you
send *after* a paper is accepted — that one does carry your name.) It is set to `False`, and it
stays `False` until the day the paper is accepted.

One thing was deliberately not done: the Word version, `manuscript.docx`, still has your Windows
account name in its hidden properties. That file is your own reading copy and is not what gets
submitted — the submission is built straight from LaTeX to PDF. It only matters if you ever email
that .docx to someone. The command to blank it is written down in `ANONYMITY.md` §4.

---

## 3. What only you can do

Nothing on this list can be done by an agent. Dates are the latest they should happen. Items marked
**DONE** are finished work kept here so you can see what changed; items **9 and 10** were done today
by the second pass. Items **11 and 12** are new and both are decisions about what the paper claims —
they were deliberately left undone, because an agent must not quietly change what a paper asserts.

**Two new items were added at 09:10 on 3 August and are placed first because both change what the
paper is allowed to say.** Item 1a is now **DONE** — the run it was about finished, the cell is
balanced, and the paper has been updated; it is kept below as a record. Item 1 — the private data
in the public repository — is the one to do first.

### 1a. DONE — the ministral3:8b cell is balanced, and the paper no longer says it is not

**This is finished. Nothing here is waiting on you.** It is written up because it changed Table 1
and six other places in the paper.

**What happened.** A simulation run was writing into the results folder at 09:04 on 3 August. It has
since finished: `examples/irrigation_abm/results/ungoverned_v21_42yr_ministral3_8b_seed44`, 3,276
rows, 42 years, 78 agents, every required column present.

**What it changed.** A *cell* is one model in one testbed. A cell is *balanced* when both arms — the
runs with validators switched on and the runs with them off — used the same random seeds, so the
runs can be compared in matched pairs. ministral3:8b had three seeds on and two off. It now has
three and three.

Because it was unbalanced, the paper had excluded it from every paired test, drawn it as an empty
outlined bar, marked it with an asterisk, and explained why in about ten places. All of that has
been removed. The cell is now drawn and tested like the other four. **This removes a caveat that
stopped being true. It does not add a claim.**

**The numbers that moved.** Table 1's ministral row was *n* = 2, 15.46, 46.54, +31.07, 2.69, 5.10,
+2.41. It is now *n* = 3, 13.56, 44.69, +31.13, 3.25, 6.05, +2.80. Two pooled figures moved because
the pool grew from 20 matched pairs to 21: +40.45 to +40.02, and +49.09 to +48.21. Two ranges moved
by a tenth of a point. Nothing else changed, no direction reversed, and the abstract did not need
editing.

**One result is new in kind, not just in value.** The cell's two statistics now disagree in sign,
and both carry a confidence interval. With validators on, the agents proposed an increase on 54.35%
of all decisions against 32.18% with them off — validators *raised* it by 22 pp. Counting only the
decisions where the agent itself said scarcity was high, validators *lowered* it by 2.80 pp. The
first is solid (p = 0.005). The second barely clears zero: its interval runs from +0.02 to +5.58,
which is wider than the effect itself, and it is significant by two hundredths of a point. The paper
now reports the interval and says the width out loud rather than calling it significant.

Note the direction of that surprise. The old explanation for the sign reversal was that it came from
comparing unequal seed counts. Balancing the cell **falsified** that: the reversal survived and got
slightly bigger, from −21.12 to −22.17, and all three seeds show it.

**One new caveat had to be added, and it is the only thing added anywhere.** The new run was
produced on a later version of the simulation code than the other twenty irrigation runs. That
version writes a different label into the audit file for the same event: where the older runs record
`Unknown` for a rejection caused by the water-right cap, the new one records
`precondition_violation`. These are the same 19 rejections either way — identical error text,
identical affected actions — but the analysis code initially read the new label as "a behavioural
rule fired", which would have broken the paper's §3 claim that the two rule layers never overlap.

**The figure's own self-test caught this rather than it passing silently.** `fig1_rule_layers.py`
printed three explicit falsification messages. The fix was to teach the analysis that the two labels
mean the same thing. The purity result is back to 10 of 10 cells, which is what it was before. §8 of
the paper now discloses the mixed-code-version fact, in the same way it already discloses that one
run used a shorter prompt.

**One check was passing when it should not have been.** `evidence/_verify_pipeline.py` is the
independent re-derivation — it recomputes the headline numbers without importing the main analysis
code, so the two can disagree. It had the seed list typed into it by hand, and that list said
ministral3:8b had two no-validator seeds. So it recomputed the old two-seed answer and agreed with
the old two-seed record. It reported PASS. That was a false green, and it is fixed; it now reads
three seeds and agrees with the corpus.

**One gate was failing when it should not have been.** `submission_gate.py` measures whether the
body fits in 8 pages. It counted the References page as a body page, so a body that ended exactly on
page 8 was reported as running to page 9. Its own cross-check printed the right answer two lines
above the wrong verdict. It now measures whether any body text sits on the References page. Tested:
it still fails correctly if the limit is set to 7 or 6, so this is an off-by-one fix and not a
loosened gate.

**Where things stand.** `run_all.py` 13 of 13. `corpus_inventory.py` exits 0. `submission_gate.py`
passes 6 of 7 — the one failure is fonts, described in the font item in section 2, which is a
separate decision and not a defect in the paper.

### 1b. The mechanism replicates on one gemma4 model and fails its own test on the other

The world-fixed decomposition — the §5 result that the appraisal shift is composition of world
states rather than the agent changing its story — was re-run on the two gemma4 irrigation cells. I
verified every number a second time rather than trusting the first pass.

- **gemma4:e4b passes cleanly.** Residual 4.08 pp against a raw shift of 43.38 pp, negative at the
  coarse rung exactly as on the anchor. Script exits 0.
- **gemma4:e2b fails the script's own pre-registered gate.** Residual 13.52 pp against a raw shift of
  47.53 pp; the gate requires under a quarter, which is 11.88. Script exits 1.

The coarse claim — the one covering 100% of the data — replicates in all three cells: ~+45 pp falls
under +6 pp once the world is held fixed. The *stronger* claim, that the residual stays near zero at
every resolution, holds on the anchor and on e4b and does not hold on e2b, where the residual grows
as the strata get finer and is positive at all five rungs.

This is not thin-strata noise, and I checked the three obvious ways it could be: e2b's finest rung is
better supported than the anchor's (25 strata at 49.7% coverage against 19 at 43.4%), its per-seed
interval excludes zero at both fine rungs, and its sign is positive everywhere.

**Nothing was added to the paper.** §5 and Table 2 are anchor-only and their present wording stays
correct, so there is no error to fix — the question is only whether to say more. **The decision is
yours**, and it is a decision about what §5 may claim:
(a) say nothing, leaving §5 anchor-only as it is now;
(b) add one sentence reporting both cells honestly, which costs a line that has to be paid for;
(c) report e4b only — **I would not do this.** Both cells come off the same command on the same data,
and a reviewer who runs the script finds e2b in one command.

Full numbers, per-seed intervals and reproduce commands: `NUMBERS.md` section 13b.

1. **TODAY — the private data in the public repository.** This is not a paper item and it outranks
   the paper. The GitHub repository `WenyuChiou/WAGF` is still public, and the survey data is still
   retrievable from its history: I pulled a row today containing a Qualtrics response ID, a
   household income, a zip code, and exact latitude and longitude **[checked today]**. It was
   supposed to be gone on 1 August. Take the repository private first — that takes ten seconds and
   stops the bleeding — then purge the history across all branches **and all seven tags**, then
   force-push. The force-push must be you: your global settings block any agent from running it.
   Put the IRB approval number, or the exemption, on file in parallel.

2. **TODAY — check whether you have an OpenReview account.** Log in at `openreview.net`. If you do
   not have a profile, create it today. The call for papers says profile creation "can take up to
   two weeks," and our plan does not test OpenReview until 28 August. This is a five-minute check
   that removes the single largest schedule risk in the project.

3. **This week — email the organisers about dual submission.** I read the full call for papers
   today. It states **no dual-submission policy at all** — the words do not appear anywhere. That
   is not the same as permission. You plan a main-track version of this work later, so you need an
   answer in writing, not an inference from "non-archival". Ask `aiteval2026@gmail.com`, one
   sentence, and paste the reply into `DECISION.md` with the date. `README.md` currently records
   this as "unconfirmed — check before submitting"; that line can only be closed by you.

4. **By Thursday 6 August — the GPU experiment: yes or no.** `PLAN.md` §5 set a hard rule: if the
   extra run has not started by the end of 6 August, it is abandoned permanently and never
   rescheduled. It has not started — only smoke tests exist **[checked today]**. My read: the paper
   is fully drafted, it is already over the page limit, and this run's bad branch would force a
   rewrite of §5, §8 and the abstract. Saying no is defensible and the fence was written to make
   that easy. But it is your call, not mine, and 6 August is when it expires.

5. **DONE 2026-08-03, but read what the paper stopped saying.** Items 5, 6 and 7 on this list were
   all executed the same day this file was written. They are no longer work; they are things to
   glance at and confirm. The fourteen lines came out of duplication, not disclosure: the excluded
   configuration was explained in five places and is now explained in one, the first-attempt
   limitation was stated in both §5 and §8 and is now stated once with a pointer, and two
   definitional sentences moved out of the artifact statement. Nothing the paper discloses was
   removed. The body ends on page 8 and page 9 carries only References **[checked today]**.

6. **DONE 2026-08-03 — Figure 1.** Two separate defects, both fixed and both re-checked on the
   built PDF. The arm labels "with validators" and "no validator" were in the drawing code but were
   being painted over by the bars themselves, so the first figure in the paper shipped with no way
   to tell the two arms apart; they now render. The caption described a two-tier layout of upper
   and lower bars that the figure does not have, and named the wrong element for each quantity; it
   now describes the bars that exist. Worth thirty seconds of your eyes on page 3.

7. **DONE 2026-08-03 — the §1 sentence.** It used to say the four cited guardrail systems "all
   report success as a conformance number, violations before enforcement against violations after".
   That is false for three of the four: NeMo Guardrails reports no numeric result at all, and the
   other two report different quantities. It now reads "the field scores success with a conformance
   number", which is a claim about the field rather than about those four papers. Same length, and
   the point of the paragraph is unchanged.

8. **By Friday 7 August — confirm the PolicyGuard citation.** The evidence work is finished and the
   answer is that the citation is correct. This is a two-minute read of the note in `references.bib`
   and a yes. It is listed separately only because your files still carry it as an open author
   decision and it should be closed rather than left dangling.

9. **DONE 2026-08-03, second pass — the paper now has a conclusion, and §3 stopped overpromising.**
   Two structural things, both re-checked on the built PDF. The paragraph that ended §7 ("The point
   outlasts this testbed…") is now a numbered §9 Conclusion sitting after the limitations, so the
   paper no longer ends on what is wrong with it. And §3's heading, which used to announce a
   finding ("The two rule layers separate"), now asks a question of fact ("Which rules read what the
   agent says"), because §3 is setup for the four results and not a fifth result — its own first and
   last sentences say so, and no other section refers back to it. §1 now says out loud what §3 is
   for. Thirty seconds of your eyes on pages 2 and 8 is enough to confirm both.

10. **DONE 2026-08-03, second pass — the paper now cites the literature this workshop is about.**
   §1 gained one paragraph. The workshop's own topic list names "measurement and causal validity",
   and until today the paper cited nothing from that field, which reads to a reviewer as a paper
   sent to a community it has not read. Three new references, [12] [13] [14]. Every one was
   checked twice on the same day by two separate passes that did not share notes, and the second
   pass deliberately searched by **title**, not by the identifier it was handed — so an invented
   title would have come back empty. All three came back real. Two of the three are preprints and
   the paper says so in the reference list rather than implying a journal. This matters more here
   than usual: the record on this project includes an incident where an assistant asked for
   citations made up about a third of them, and a made-up citation in a paper about measurement
   integrity would end it.

11. **Your call — the abstract says the paper cannot do the thing the paper then does.** A
   simulated reviewer reading the built PDF flagged this as the single thing most likely to sink
   it, and it is a decision about what you are claiming, so nothing was changed. The abstract says
   the rule "has no observation channel independent of the process it governs". Eight lines later
   it reports the headline result by holding the simulator's record of the world fixed — which is
   an independent channel. §7 answers this on page 8: the stratification only worked because *this*
   simulator kept such a record and a real deployment has no reason to. The answer is right; it
   arrives too late. Pick one: (a) name the escape hatch in the abstract itself, wording drafted in
   the manuscript's own note block, item H; (b) leave it. Related question you have to answer
   either way: is the claim "there is no independent channel", or "there is none in deployment"?
   Those are two different papers, and the data supports the second.

12. **Your call — the abstract sells a three-seed result harder than the interval allows.** "On one
   configuration the whole apparent gain is composition" comes from three seeds with a confidence
   interval running from −13.92 to +14.25, which is wide enough to contain both the full effect and
   its opposite. Half of the reviewer's fix was applied today, because it was a reordering and not
   a claim: §6 now states the alternative action reading (+27.82 pp) in the same paragraph as the
   result instead of seventeen lines later, so that cell reads as an existence proof tied to one
   reading. The abstract half was left for you, with the reviewer's replacement wording in the
   manuscript note block, item I. A third, smaller version of the same question is there too: §5
   says the residual is "near zero at every resolution", where the table shows two of four
   intervals excluding zero, both negative. The paper prints that fact two sentences later either
   way — the question is only which one leads.

13. **On submission day (aim 27 August) — the author fields go in the web form, not in the PDF.**
   OpenReview asks for author names and affiliations in its own submission form. That is correct
   and expected; it is how double-blind works — the system knows who you are, the reviewers do not.
   **Do not add your name to the PDF.** Leave `CAMERA_READY = False`. The name goes on the paper
   only if it is accepted, in September.

---

## 4. What happens without you

You do not need to think about any of these.

- **Every number regenerates from raw data with one command.** `python
  SUBMISSION_2026/TAE/evidence/run_all.py` rebuilds every figure, every CSV and the table from the
  original run directories. If a number ever drifts, this catches it rather than printing something
  plausible. It prints its own pass count and its own runtime; both are deliberately absent from
  this file, because a count written here would be wrong within a day. It is red today for the one
  reason in item 1a.
- **The build refuses to produce a broken paper.** Three separate guards stop it: an unmatched or
  unused number-marker fails the build, an unmapped special character fails the build, and LaTeX
  must exit cleanly. None of these will be worked around.
- **The paper stays anonymous by default.** Blind mode is the default state of the build; making it
  non-anonymous requires deliberately editing a line that is commented to say so.
- **The mechanical fixes are all applied — nothing is waiting on your word.** This bullet used to
  list seven of them as pending: the font fix, Figure 1's labels, shrinking Figure 1, correcting
  "all three figures" to four, adding Table 2 to the released data list, the missing in-text
  mention of Figure 1, and the seed-range clarification. Every one is in the manuscript. The font
  fix removed the Type 3 but left three TrueType fonts, which is the one part not fully closed —
  see the font item in section 2. **Do not re-apply any of these from this list**; check the
  manuscript, or run `paper/submission_gate.py`, which verifies the figure/table counts, the fonts
  and the page limit directly against the built PDF.
- **The bibliography is finished.** All fourteen entries verified twice, no orphans, no leaks, and
  the two predecessor studies are not cited at all, so there is nothing that could break anonymity.

---

## 5. The schedule to 29 August

| when | what | who |
|---|---|---|
| **Mon 3 Aug — today** | Repo private + PII purged. OpenReview account checked. Organisers emailed. | **You** |
| Tue 4 – Thu 6 Aug | Mechanical fixes applied and rebuilt. **6 Aug: GPU run go/no-go expires.** | Agent + your call |
| Fri 7 – Sat 8 Aug | Your seven decisions land; the cut is executed; body back to 8 pages. | You, then agent |
| Sun 9 – Sun 16 Aug | Structure improvements: §3 into the results list, conclusion moved, duplication trimmed. | Agent |
| Mon 17 – Thu 20 Aug | Red team: forbidden-claims sweep, references re-verified, anonymity sweep, figures re-read at print size. | Agent |
| Fri 21 – Thu 27 Aug | **Buffer. Do not schedule work here.** Submit on 27 Aug if all is clean. | — |

**28 August** is held for an OpenReview problem. **29 August** is held for a submission-system
failure only. That is a **seven-day buffer**, which is unusually healthy — the paper was drafted
about ten days ahead of `PLAN.md`'s original schedule, and the buffer is where that gain went.
Protect it. If any week slips by more than two days, cut §7 to three sentences and drop the
duplication trims, in that order, before you touch the buffer.

---

## 6. The five risks

1. **You have no OpenReview account and creating one takes two weeks.** — Triggered the moment
   you try to submit and discover the profile is still pending; removed today by a five-minute
   login check.
2. **The private survey data stays in the public repository.** — Already triggered and running
   now; every day the repository stays public is another day the data is downloadable, and this
   is the one item on this page that could matter more than the paper.
3. **The workshop turns out to forbid a later main-track version.** — Triggered by an organiser
   reply saying the work may not be resubmitted elsewhere; the call for papers is silent, so only
   the email in item 3 above closes it.
4. **The paper is desk-rejected on format before anyone reads it.** — Triggered by shipping over
   the page limit or with a Type 3 bitmap font embedded. Both are fixed. **Neither may be taken on
   trust again:** `paper/submission_gate.py` re-measures the page limit and every embedded font
   on the built PDF each time it runs, which is exactly how the "every font is Type 1" claim was
   found to be an overstatement. Re-run it on the final PDF.
5. **A reviewer opens the paper's first figure and it does not work.** — This was triggered by the
   version in which the reader could not tell which bar was the governed run and the caption
   described a different picture. **Both were fixed** (section 3, item 6). The figure concerned is
   now numbered Figure 2; Figure 1 is the schematic. The risk stays on the register because the
   opening image is worth re-reading at print size before submitting, not because the defect is
   still there.

---

## 7. Recommendation you have not acted on: cut ten tracking documents to four

**Recorded, not applied.** An audit on 3 August checked all ten tracking documents in this folder
against what is actually on disk and found roughly forty stale or false claims. The factual ones are
now corrected in place. **The consolidation below is a judgement call about your own working system,
so nothing was deleted** — and `SUBMISSION_2026/` is not in git, so a deletion here is permanent and
unrecoverable. That is the main reason to decide it deliberately rather than let an agent do it.

**The diagnosis.** Nine of the ten worst findings were the same mistake: *a fact a script could have
determined was written down in prose instead* — script count, pass count, page count, figure count,
reference count, marker count, wall-clock, and every `file:line` reference. All twenty-two
`manuscript.md:NNN` pointers in `SUBMISSION_READINESS.md` had rotted; not one landed on the line it
named. Five documents carried six different pipeline pass counts. This file carried three on a
single day.

**The fix already applied:** those quantities have been removed from all ten documents and replaced
with pointers to the three commands at the top of this file. Prose now says "run the check", not
"the answer is 9/9".

**The proposed target — four live files:**

| keep | why it earns its place |
|---|---|
| `README.md` | The entry point: what this is, the three commands, and the data-hygiene rules no script can enforce on a human. |
| `STATUS.md` | Today's state and open decisions. Rewritten each pass, dated, with the checks' output pasted in. |
| `DECISION.md` | Claims and forbidden claims **only** — no schedule, no structure table, no figure list. Those are the parts that went stale. |
| `NUMBERS.md` | Claim → value → script → stdout, and nothing else. Its tables are sound; its status blocks were the rotten part and are now gone. |

**The six proposed for merge or deletion, and what must survive each:**

- **`SUBMISSION_READINESS.md`** — its verdict was false and its references had all rotted. **Must
  survive:** §3's weakest-link analysis (that §5 standardises on a variable §7 declares
  treatment-affected, and that the never-retried stratum is filtered on the *outcome* in one arm and
  on *action* in the other). That is the sharpest criticism anyone has written of this paper and it
  appears in no other file. Risks R2, R7 and R12 are still live. §6 is career strategy, not a
  submission document.
- **`PLAN.md`** — the calendar is two weeks overtaken. **Must survive:** §2's forbidden-claims table
  (eleven rows, each with the incident that earned it) → fold into `DECISION.md` §10; and §5's
  experiment fences → fold into `RUN_DECISION.md` §4.
- **`BACKLOG.md`** — every B and W item is closed. **Must survive:** the P0.1 PII row (already
  item 1 here, and still the thing that outranks the paper) and its "where two documents disagree —
  and which one is right" table.
- **`EXPERIMENT_OPTIONS.md`** — merge into `RUN_DECISION.md`. Only §1a and §1e are still live; §1e
  holds the only measured GPU cost basis in the project.
- **`RUN_DECISION.md`** — keep until 6 Aug. After the go/no-go expires it stops being a decision and
  becomes a record of what was deliberately not run; freeze it as an appendix then.
- **`BOUNDARY.md`** — §1–§4 (the read/write contract and the vendoring table) fold into `README.md`.
  §5 and the venue/toolchain block were the stale parts and are both now script-checkable.

**What would be lost, and how not to lose it.** The audit trail. `BACKLOG.md`'s discipline of naming
the verification method in every row, and `DECISION.md` §7's self-correction, are the record of *why*
a number is what it is; without them a future reader cannot tell a considered number from a lucky
one. The fix is a single append-only `CLOSED.md` that rows move into and that is **never read for
status**. The distinction that matters is not delete-versus-keep, it is **live document versus
archive** — the real failure was that all ten were being read as live, which is how a 31 July
assertion about a non-existent manuscript survived in the file that called itself the plan of record.
Pending your decision, the archives are now labelled as archives in their own headers.
