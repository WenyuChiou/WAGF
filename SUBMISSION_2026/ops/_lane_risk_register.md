## Verified ground truth (checked this session, not inherited from the docs)

Five things I confirmed directly, because they change the plan rather than decorate it:

**There is no resume. At all.** `grep` for resume/checkpoint/start-year across `broker/core/experiment_runner.py` and the irrigation runners returns nothing. A run is an atomic unit: it completes or it is lost. The largest atomic unit in the proposed queue is gemma3:27b × irrigation = 3.28 × 10.6h ≈ **35 GPU-hours with zero crash tolerance**. Per-decision JSONL *is* fsynced (Phase 6G, `0e3187c`) and `broker/tools/recover_csv_from_jsonl.py` can rebuild a CSV from a partial file — but that recovers *data*, not *trajectory*. A 42-year irrigation panel truncated at year 30 is scientifically useless for a mixed-effects model over the full horizon. Recovery ≠ resumption.

**`run_integrity.py` cannot detect the failure modes you are worried about.** I read the body. It checks exactly one thing: humancentric memory engine ⇒ reflection log non-empty. It does **not** check row count, capture rate, GPU-vs-CPU, or wall-clock plausibility. And by explicit design (line 5, line 9) it **FLAGS, never aborts** — chosen to protect byte-identity on the v21/paper-3 corpus. So today a truncated run writes `run_integrity.json` with `integrity_ok: true` and enters the analysis looking healthy. This is the single largest engineering gap between you and an unattended campaign.

**The PII is worse-placed than the docs say.** The blobs are reachable from **6 of 7 tags** (v0.2.1 → v0.6.0), not just from `main`. Header row confirms `survey_id` (Qualtrics ResponseID), `income`, `household_size`, `longitude`, `latitude`, `zipcode`, `flood_depth`. Lat/long + zipcode + income + household composition is a re-identifiable record set for real respondents on a public GitHub repo. A purge must rewrite every tag and every remote branch, and the global settings floor denies `git push --force`, so **you must run the force-push personally** — it cannot be delegated to an agent.

**The calibration-band edit is uncommitted and live right now.** `git diff` on `paper3/configs/calibration.yaml` shows `insurance_lapse_rate` moved `0.05–0.15 → 0.15–0.30` with the `source: "Gallagher (2014, AER); Michel-Kerjan et al. (2012)"` line **untouched**. That is a goalpost moved on the band the headline model fails worst, still attributed to papers that do not support the new range. It sits in the working tree alongside `empirical_benchmarks.py` and `l1_micro.py`. This is a research-integrity exposure, not a code-style nit.

**The mitigation script the risk docs point at does not exist.** `.codex_tmp/RESTORE_AS_ADMIN.bat`, cited in memory as the recovery path for the 2026-05-14 scheduled-task protection, is **missing**. R3's stated mitigation is currently vapour.

Disk, by contrast, is a **non-risk** and I can close it now: 2.4 TB free; irrigation runs measure 67 MB / 3,276 decisions ≈ 20 KB per decision; even a generous 400-run new corpus lands at **~25–35 GB**, roughly 1.5% of free space. Stop worrying about disk; it is two orders of magnitude from binding.

---

## The calendar arithmetic, done honestly

The plan doc says full P0 = 656 GPU-h ≈ 36 days at 18–19 h/day. Start 5 Aug → finish ~10 Sep → 4–5 days of slack before a 15 Sep freeze. That is **12% slack against a workload with two recorded multi-hour incidents in its own history**. Price those in at a conservative 15% loss and the requirement becomes 772 h ≈ 43 days, which demands a **3 Aug start** — five days from now, with the P0-1 tag, pre-registration, and the retry-exhaustion decision all still open.

So the honest statement is: **the full plan does not fit, and it did not fit before anything slipped.** The trimmed plan (236 h P0-2 + 71 h P0-3 = 307 h ≈ 17 days) fits with three weeks to spare and could start as late as **29 Aug**.

The latest defensible start for a 15 Sep freeze is therefore **8 Aug for the trimmed plan** (matching the existing hard gate) and the full plan should be treated as already cut. Decide the cut order now, in this order, as the plan doc already recommends: drop ministral-3:14b, then reduce gemma3:27b to a 2-arm anchor, then P0-3 to 3 seeds. **Never cut arms A′/B′** — they are the entire methodological contribution.

One structural point the week-by-week table hides: **author registration on 17 Sep is mandatory, financial, and lands two days after the freeze.** Two days is not enough to decide whether you have a paper. Pull the real go/no-go to **8 Sep**, one week earlier, and treat 8 Sep as the date the campaign's outcome must be legible.

**Abort criterion, as a burn-down rather than a vibe:** by 24 Aug you must have ≥40% of planned GPU-hours *banked as integrity-passing runs* (not merely elapsed); by 4 Sep, ≥75%. Miss either checkpoint and cut the next item off the pre-decided list the same day — do not wait to see if it recovers. Two consecutive missed checkpoints means the AAMAS submission converts to the AAAI-28 fallback and the queue re-targets that deadline. Deciding this now is what stops it from being a panic decision in September.

---

## Queue design: make the abort point publishable

Since runs are atomic and unresumable, the only checkpointing available to you is **at the queue level**, and the design choice that matters most is ordering.

Run the grid **breadth-first over seeds, not depth-first over cells.** Complete seed 1 for every model × arm cell, then seed 2, then seed 3. Depth-first gives you, at any abort point, a partial grid with entire cells missing — unanalysable. Breadth-first gives you a *complete but underpowered* design at every abort point, which is a paper with wide error bars rather than no paper. This single ordering decision converts calendar risk from binary to graceful.

Within that, order cheapest-model-first (ministral3:3b → gemma3:4b → ministral3:8b → gemma3:12b → ministral3:14b → gemma3:27b) so that the core A′/B′ contrast is banked in the first 48 hours, and cap the atomic unit: **no single unresumable run should exceed ~12 h.** gemma3:27b × irrigation at 35 h violates this by 3×. Either drop 27b-irrigation, or accept that it is a coin-flip you re-toss on every failure — and if you keep it, schedule it in the *first* week when there is still time to re-run it, never in the last.

Drive the queue from a manifest worklist with a per-run status file (`queued / running / passed / failed_integrity / aborted`), so the *queue* is resumable across reboots even though runs are not. A crash then costs exactly one run — bounded, known, and automatically re-enqueued.

---

## Detection: the three assertions that must exist before 5 Aug

The two recorded incidents and the silent-death class all share one property — **the process exits 0 and the output looks plausible.** Exit codes are therefore worthless as a signal, and every mitigation below is an assertion on observable state, not on return values.

**Pre-run GPU assertion.** Before each run, `ollama ps` and assert the output contains `100% GPU`; abort the run and alert if it shows any CPU share. This is the exact signature of the 2026-05-13 incident and it is a one-line check that would have saved four hours. Pair it with the recorded fix (`setx CUDA_VISIBLE_DEVICES 0`, kill ollama, relaunch) as an automated remediation attempt before escalating.

**In-run throughput assertion (the CPU-fallback and stall detector).** Measure decisions/minute over the first five minutes and compare against a per-model recorded baseline; abort if below 50% of expected. A 12× slowdown trips this instantly. Then run a heartbeat watchdog on the streaming JSONL: if `mtime` has not advanced in 15 minutes, the run is stalled — kill, flag, re-enqueue. This is the detector that turns "four silent hours" into "five silent minutes".

**Post-run integrity gate — and this one requires a code change.** `run_integrity.py` must gain, *for the new campaign path only*, an assertion that row count equals `agents × years` exactly (irrigation 3,276; flood 1,000), that capture rate clears a floor, that the manifest exists and records `git_dirty: false`, and that `llm_calls` is present and sane for call-matched arms. Critically, the new campaign path must **fail loudly** rather than flag. Do not change the flag-only behaviour on the existing v21/paper-3 path — that would break the byte-identity guarantees the module was written to protect. Add a strict mode; leave the legacy default alone. A run that fails the gate must be *renamed or quarantined* so it cannot be globbed into an analysis, which is precisely how the 2026-05-30 reflection-confound entered the corpus.

Provenance is the fourth assertion and it is free: **refuse to start any run from a dirty tree or a detached/feature branch.** Right now the repo is dirty *and* on `p0-1-governance-instrumentation`, not `main`. D9 records that zero clean-tree runs exist in the entire 347-run corpus. If the new campaign repeats that, the code-vintage confound is not a legacy defect you inherited — it is one you chose, and a reviewer will read it that way.

---

## Where the writing actually collides with the queue

The collision is not "writing versus running", because the queue is unattended. It is **attention versus attention**, and it lands in two places.

The first is **12 Aug – 1 Sep**. That window is simultaneously peak queue-babysitting (both recorded incidents needed a human to notice) and the entire workshop-paper drafting window for a 22 or 29 Aug deadline. The resolution is that the assertions above must be *automated before 5 Aug*, not written during that window — every hour of monitoring you have to do by hand in late August is an hour stolen from the workshop paper. Build the watchdog first; it pays for itself in attention, not just in GPU-hours. Given the workshop paper needs zero GPU, **prefer the 29 Aug deadline over 22 Aug** — the extra week costs nothing and buys the whole buffer.

The second collision is the one that actually decides whether AAMAS happens: **15 Sep freeze → 8 Oct paper is 23 days**, and the timeline doc itself budgets a full week for the first draft alone. That only works if the analysis and figure code is written *before* the freeze, against mock or partial data, so that 15 Sep is a `make figures` command rather than the start of an analysis project. Writing analysis code against the first completed seed in mid-August is the highest-leverage scheduling move available, and it is also free — it needs no GPU and it doubles as a test of whether the integrity gate is producing analysable output.

Note also that the workshop paper is non-archival and shares the composition finding with Tier 2. It is a rehearsal of the framing for an agents audience, not a detour — but only if you resist widening it. It is 4 pages and needs no new data.

---

## Risk register, ranked by expected damage

| # | Risk | L | I | Detection signal | Mitigation | Who / When |
|---|---|---|---|---|---|---|
| 1 | **Human-subjects PII live in public git history** — re-identifiable (lat/long + zip + income + household), reachable from 6 of 7 tags | Certain (present now) | Catastrophic — IRB/institutional, ethics desk-reject, real-world disclosure | Already confirmed: `git show 3c244f39^:…` returns full header | Take repo **private today**; `git filter-repo` across all branches **and 6 tags**; force-push (**Wenyu personally** — global deny blocks the agent); obtain IRB protocol no./exemption in parallel; if consent excludes redistribution, release synthetic-population runs only | Wenyu, **by 1 Aug**, independent of any deadline |
| 2 | **Full plan has negative slack once incidents are priced** (656 h needs 43 realistic days; 41 available) | High (~70%) | Miss AAMAS entirely | Burn-down: <40% banked by 24 Aug; <75% by 4 Sep | Start **trimmed (307 h)**, not full. Pre-commit cut order: m3:14b → 27b to 2-arm anchor → P0-3 to 3 seeds. Never cut A′/B′ | Wenyu, decide **by 4 Aug**; checkpoints 24 Aug / 4 Sep |
| 3 | **Silent-death run enters analysis undetected** — `run_integrity.py` flags-never-aborts and checks only reflection count | High (3 recorded cases; 9–30% capture loss in one family) | Dead arm discovered in late Sept = unrecoverable | New strict gate: row count == agents×years, capture floor, manifest present, `git_dirty==false` | Add **strict mode** to `run_integrity.py` (leave legacy flag-only path untouched for byte-identity); quarantine failures so they cannot be globbed. **Before 5 Aug** |
| 4 | **Unresumable 35 h atomic unit** (27b × irrigation); no resume exists anywhere | Moderate-high over 41 days | 35 GPU-h per crash, repeatable | Heartbeat: JSONL `mtime` stalled >15 min | Cap atomic units at ~12 h; drop or early-schedule 27b-irrigation; manifest-driven worklist so the **queue** resumes even though runs don't; `recover_csv_from_jsonl` for partial salvage (data only, not trajectory) | Before 5 Aug |
| 5 | **Ollama silent CPU fallback** (recorded: 4 h at 12× slower, no error) | Moderate (recurred after driver/boot changes) | ~1 week of budget if undetected once | `ollama ps` lacks `100% GPU`; throughput <50% of per-model baseline in first 5 min | Pre-run GPU assert + auto-remediate (`setx CUDA_VISIBLE_DEVICES 0`, kill, relaunch) then escalate; in-run throughput assert aborts loudly | Before 5 Aug |
| 6 | **`on_retry_exhausted` semantics undecided** (A vs B vs C) — diverges on **45.4%** of irrigation governed corpus | Moderate | Total — arms defined wrong ⇒ entire queue invalid | `fallback_scenarios.py` already quantifies each choice | **Decide before the queue starts**, record in pre-registration. Recommend C (hard/soft split); A0 reproduces published pair but lets agents take water they have no right to — not defensible | Wenyu, **by 4 Aug** |
| 7 | **git_dirty / wrong-branch runs repeat the D9 code-vintage confound** (zero clean-tree runs in 347) | High — tree is dirty *now*, on a feature branch | Reviewer-fatal provenance; unfixable post-hoc | Runner refuses to start unless tree clean and on tagged commit | Tag P0-1 release; hard precondition in the run wrapper; no exceptions | Before first run |
| 8 | **Uncommitted calibration band widened 0.05–0.15 → 0.15–0.30 with citation untouched** | Certain (in tree now) | Research-integrity finding if it ships | `git diff paper3/configs/calibration.yaml` | Revert, **or** justify in writing with a new citation. Freeze one sourced benchmark file, hash it, report the EPI it yields including failure. Also fix `empirical_benchmarks.py:169-170` (B1-SFHA and B2-all-zones assigned identical unfiltered mean) | Wenyu, **by 4 Aug** |
| 9 | **Windows Update auto-reboot** (recorded: killed a run at year 10) | Moderate over 41 days | 1 run + restart latency | Uptime reset; queue status file shows `running` with no live process | Pause WU for the full window (renew — max pause is 5 weeks, so **renew ~8 Sep**); disable the 4 contending scheduled tasks; **recreate the missing `RESTORE_AS_ADMIN.bat`**; auto-resume queue on boot | Before 5 Aug; renew 8 Sep |
| 10 | **Writing/monitoring collision, 12 Aug – 1 Sep** | High | Workshop paper slips or queue goes unwatched | Self-evident in the week grid | Automate detection *before* 5 Aug so monitoring is a daily 10-min check; choose the **29 Aug** workshop over 22 Aug; write analysis/figure code against the first completed seed in mid-Aug so 15 Sep is `make figures` | Wenyu, ongoing |
| 11 | **17 Sep mandatory registration lands 2 days after freeze** | Certain (structural) | Pay-and-commit without knowing the result, or miss it as AAAI-27 was missed | — | Pull real go/no-go to **8 Sep**; calendar alarms on 8 Sep, 17 Sep, 1 Oct, 8 Oct | Now |
| 12 | Disk exhaustion | **Negligible** | — | — | **Closed.** 2.4 TB free; new corpus ~25–35 GB (~20 KB/decision, measured). No action | — |

---

## The one thing I would change about the plan

The existing docs treat the GPU budget as the binding constraint. It isn't — the GPU is free now, and disk is a non-issue. **The binding constraints are attention and provenance.** Both recorded incidents were detected by a human noticing something felt slow, and the corpus's most damaging defects (zero clean-tree runs, seed-label mismatch, reflection-confound, 9–30% capture loss) are all provenance failures that no amount of GPU time fixes and that a reviewer can find in an afternoon.

That inverts the pre-5-Aug priority list. The instrument is built and tested; the thing that is *not* built is the harness that proves the instrument ran correctly. Spending the next five days on the strict integrity gate, the GPU/throughput assertions, the clean-tree precondition, and the pre-registration — rather than on more experiment design — is what converts 41 unattended days into 41 usable ones.

And risk 1 is not on that critical path at all. It is a live disclosure of identifiable human-subjects data on a public repository, it has been live since June, and it should be resolved this week whether or not any of these papers ever get written.