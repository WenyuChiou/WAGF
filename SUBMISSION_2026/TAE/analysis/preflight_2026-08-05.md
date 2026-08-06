# Pre-flight — first-attempt appraisal logging (E1) — 2026-08-05

# VERDICT: **GO WITH CONDITIONS** — for the *authorised* run only (governed arm, 5 seeds, 52 GPU-h). **NO-GO on the brief as written (110 GPU-h, two arms, flood, ADVISE).**

Four conditions, all resolvable today, listed in §2. Three of them are decisions, not code.

The single most important sentence in this report: **the run described in the pre-flight brief is
not the run this project authorised.** `PLAN.md:231` says **"RUN OPTION 1, AND NOTHING ELSE"** —
governed arm only, `gemma3:4b`, seeds 42–46, **52 GPU-h**. The brief describes ~110 GPU-h across
two arms plus a flood arm plus the ADVISE disposition. Each of the three extras is separately
blocked by a missing runner flag or a missing config (§3). The authorised 52-hour run is in good
shape and can start. The 110-hour version cannot start today at any level of effort.

Read §2 (blockers), then §5 (your two questions), then §6 (the command).

---

## 1. What I actually checked, and where the lanes disagreed

I re-verified every load-bearing claim from the four upstream lanes rather than relaying them.
That mattered: **the four lanes contradicted each other on the single most important fact in the
report**, and three of the four were wrong.

Lane A reported that `output_schema_violation` is missing from the analysis classifier's
`_NO_RULE_TOKENS`. Lanes B, C and D each independently reported that this set was "PATCHED" and
"holds both literals". I read the file. Lane A is correct:

`SUBMISSION_2026/TAE/evidence/_data.py:793-795`
```python
_NO_RULE_TOKENS = frozenset(
    {"", "unknown", "none", "n/a", "nan", "precondition_violation"}
)
```

`output_schema_violation` is **not there.** Three lanes read the neighbouring literal, saw a fix,
and reported a clean bill of health on a set that is still one element short. This is the same
reading error, made three times independently, on the exact defect class that falsified §3 on
2026-08-03. It is why this report treats a clean lane report as a claim to check, not a result.

Lane-by-lane disposition, so "checked and clean" is distinguishable from "not checked":

| lane | blocking findings I confirmed | findings I could not confirm |
|---|---|---|
| A — instrumentation | 3 of 4 confirmed (see B2, B3, §3) | — |
| B — config parity | 1 of 4 confirmed; 2 apply only to unauthorised scope | `output_schema_violation` "PATCHED" — **false** |
| C — code state | 0 blocking for the authorised run; provenance comment error confirmed | `_NO_RULE_TOKENS` "PATCHED" — **false** |
| D — validators/schema | 2 confirmed (B2, B3); 1 applies only to unauthorised scope | `_NO_RULE_TOKENS` "both literals" — **false** |

---

## 2. BLOCKING — must be resolved before the queue starts

### B1. The scope in the brief is not the authorised scope
**What it is.** The brief specifies E1 across "5 seeds × 2 arms; and the flood governed arm", plus
E2 (ADVISE), at ~110 GPU-h. The decision of record, `SUBMISSION_2026/TAE/PLAN.md:231-233`, is:

> **RUN OPTION 1, AND NOTHING ELSE** … first-attempt appraisal logging, **governed arm only**,
> `gemma3:4b` anchor cell, `--real`, 42 years, strict, seeds 42–46. **52 GPU-h, 2.5 days
> wall-clock, zero code changes**

The both-arms add-on is **conditionally** approved and its condition is not yet checkable —
`PLAN.md:265`: "take it only if all five governed seeds have passed integrity by **12 Aug**."
Flood and ADVISE appear in `EXPERIMENT_OPTIONS.md` as options but are **not** authorised by
`PLAN.md` §5.

**What breaks if ignored.** You spend roughly double the authorised GPU budget on three arms that
cannot currently be produced (§3), and the two that could eventually run would be launched outside
the decision record — which is the governance defect the TAE folder exists to fix.

**Cheapest resolution.** Confirm in one line which you are running. If it is Option 1 (recommended),
everything below applies and you can start today. If you want the extras, they need §3 resolved
first and a fresh written decision — and they cannot make the 6 Aug fence.

---

### B2. `output_schema_violation` is missing from the rejection classifier
**What it is.** `_data.py:793-795`, quoted above. Two sibling scripts already carry the complete
set — `SUBMISSION_2026/evidence/fallback_scenarios.py:47` and
`AAMAS2027/experiments/fallback_scenarios.py:47` both use
`{"Unknown", "precondition_violation", "output_schema_violation"}`. The TAE copy is the odd one out.
`fig1_rule_layers.py:348` delegates to `D._NO_RULE_TOKENS`, so it **inherits the gap** rather than
being independently patched.

The literal is live and reachable in the arm you are about to run. It is written unconditionally,
with no feature flag, at `broker/core/skill_broker_engine.py:824` and `:829`, and `output_schema:`
is declared 5× in the irrigation skill registry.

**What breaks if ignored.** `rejection_cause()` (`_data.py:826`) classifies any such rejection as
`"theory"` — a named validator-rule hit. That is the 2026-08-03 defect exactly, one literal over:
world-feasibility blocks silently recounted as behavioural-theory blocks, inflating the governed
arm's rule-attribution. It has never fired in the frozen corpus, which is precisely why nobody has
seen it — the same "nothing looked wrong" signature as the incident.

**Cheapest resolution.** Add the one string to the frozenset, and re-run whatever evidence scripts
consume it. One-word edit; no run depends on it being done before launch, but it must be done
before any §3/§4 number is regenerated from the new corpus.

---

### B3. Two isolated config trees exist and the *wrong one* was smoke-tested
**What it is.** Both of these are on disk:

| tree | `initial_proposal_columns` | `executed_skill_columns` |
|---|---|---|
| `ICLR2027/experiments/config_firstattempt/` | ✅ | ❌ **absent** |
| `SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/` | ✅ | ✅ |

The brief says the smoke used the ICLR2027 copy. I confirmed the consequence in the smoke output:
`executed_skill` is **absent** from
`ICLR2027/experiments/_smoke_firstattempt/irrigation_farmer_governance_audit.csv`.

The launch doc of record (`SUBMISSION_2026/TAE/runs/launch_firstattempt.md` §2) points at the
**SUBMISSION_2026 tree**, and so does the integrity gate:
`SUBMISSION_2026/TAE/evidence/e3_run_integrity.py:85`
```python
ISOLATED_CONFIG_MARKER = "config_irrigation_firstattempt"
```
`:391` raises `IntegrityError` when the manifest's config path does not contain that substring.

**What breaks if ignored.** Launching against the ICLR2027 tree fails the integrity gate on **every
seed** — after the GPU time is spent, not before. And you silently lose `executed_skill_columns`,
which `_lane_prereg_v1_superseded.md:98` prices at **up to 35 pp of level** and which cannot be
added retroactively. Given this project's EXECUTED-ONLY rule for headline numbers, that is the
expensive half of the loss.

**Cheapest resolution.** Use `SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt` — as the
launch doc already specifies. Nothing to build. Then delete or clearly mark the ICLR2027 copy as
superseded so the next session does not pick the wrong one.

---

### B4. The launch prerequisite is not met: dirty tree, no tag, and the run folder is untracked
**What it is.** `launch_firstattempt.md` §1a and `PLAN.md`'s 1 Aug fence require
`git status --porcelain` to be empty and the tree tagged. Right now it returns **21 entries**, and
no `tae-*` tag exists. Two entries are new since the launch doc was written and matter more than
the flood paths it lists:

- `?? SUBMISSION_2026/` — **the entire TAE folder is untracked.** The isolated config you are about
  to run, `e3_run_integrity.py`, `e7_appraisal_drift.py` and the launch doc itself are all outside
  version control.
- `?? figures/`, `?? .coord/`, `?? DATA_OWNERSHIP.md`

**What breaks if ignored.** The manifest records a commit that does not describe the config the run
actually read. That is the "0 of 131 runs have clean provenance" defect this run was partly designed
to stop repeating — reproduced, deliberately, on the run meant to fix it.

**Cheapest resolution.** Commit `SUBMISSION_2026/` and the other untracked paths (or stash the flood
work), then `git tag tae-firstattempt-2026-08-05`. This is your call, not a TAE session's —
`BOUNDARY.md` §1 puts `examples/` edits out of scope for this folder. **Note the tag date: use
today's date, not the doc's stale `2026-08-01`.**

---

### B5. The hard fence is tomorrow
`PLAN.md:134` and `launch_firstattempt.md` §4: **HARD GO/NO-GO 6 Aug — if the queue has not started
by end of 6 Aug, abandon the run permanently.** Today is 5 Aug. Five sequential seeds at ~10.4 h is
2.5 days; the 14 Aug freeze needs n ≥ 3 to report at all. Starting seed 42 tonight leaves adequate
margin. Starting on 7 Aug is not a slip, it is a NO-GO by the project's own rule.

---

## 3. Blocked *only* if you expand scope beyond Option 1

These are hard blockers on the brief's extra arms. None affects the authorised run. I list them so
the scope decision in B1 is made with the costs visible.

**The no-validator arm cannot produce the E1 columns at all.**
`examples/irrigation_abm/run_ungoverned_experiment.py` has **no `--config-dir` argument** — its full
argparse surface is lines 319-329 (`--model --years --agents --real --workers --seed --memory-seed
--window-size --output --num-ctx --num-predict`) and it hardcodes `config_dir = base / "config"` at
`:110`. It would silently read the frozen config, where `global_config.audit` is absent, so the flag
defaults False (`broker/utils/agent_config.py:341`) and none of the three columns would ever be
written. You would discover this only after ~41 GPU-h. The governed runner has the flag
(`run_experiment.py:776`); the no-validator runner was never given it. **Do not resolve this by
editing `examples/irrigation_abm/config/`** — 41 corpus runs depend on that file.

**The multi-agent flood runner cannot be pointed at an isolated config.**
`examples/multi_agent/flood/run_unified_experiment.py:1119-1121` hardcodes its config path, and a
grep for `config_root|config_dir` in that file returns **0**. Commit `10e190cf` gave `--config-root`
to single-agent flood (`run_flood.py:1370`) and `--config-dir` to irrigation, but not to this
runner. Single-agent flood *is* unblocked — but no isolated flood config tree exists yet, and I
could not determine from the brief which flood was meant. Both write
`household_governance_audit.csv`, so the filename does not disambiguate.

**ADVISE has no arm config anywhere on disk.** Neither isolated tree sets
`global_config.governance.advise` or `audit.advise_columns`. The machinery is present and
well-guarded, but there is nothing to run. Separately, **E7 as written would mis-measure an advise
arm**: `initial_labels` is snapshotted at `skill_broker_engine.py:365`, *before* `_advisory_pass`
runs at `:372`, and E7 filters on `retry_count > 0` — so a decision where advice moved the appraisal
and no retry followed is excluded entirely. That is the exact stratum E2 exists to study.

---

## 4. ADVISORY — real, but they do not invalidate the run

1. **`--num-ctx 8192 --num-predict 4096` is a deliberate divergence from the decision text, and it
   needs your sign-off today.** `launch_firstattempt.md` flags this itself: `performance_tuner.py`
   would auto-tune `gemma3:4b` to `num_ctx=4096, num_predict=2048` — **half** what every archival
   batch script for this exact cell passes. Without the override you get a different retry/parse
   profile than the anchor cell, and the 10.4 h/run costing basis (measured *with* the override)
   no longer holds. I agree with the launch doc's choice; it just needs confirming rather than
   discovering mid-run.
2. **`--memory-seed <S>` matching `--seed` diverges from the archival scripts**, which leave it at
   the default 42. `EXPERIMENT_OPTIONS.md` §7 is the decision of record and specifies per-seed.
   Recorded so it is a decision, not a surprise.
3. **The §1e isolation diff now prints two lines, not one.** The second is `DIFF_AGAINST_FROZEN.md`,
   a documentation file inside the isolated tree. Benign — but the launch doc says "exactly one
   line", so update the expectation or you will read a pass as a fail.
4. **`_data.py:783-785` names the wrong commit.** It attributes the `precondition_violation` literal
   to `10e190cf`; it came from `0b17c367` (2026-06-10), which is on `origin/main`. The affected
   window is seven weeks wider than documented, and the comment implies staying on main avoids the
   literal. It does not — every new run emits it. This is the project's written memory of the
   incident; leaving it wrong misdirects the next reader.
5. **New runs will carry a `shadow_blocked` column the 10 anchor runs lack** (written
   unconditionally, `audit.py:322`). Harmless for E1, which is a within-new-arm analysis and reads
   by column name via `DictReader`. It is *not* harmless for any comparison of rejection rates or
   `failed_rules` taxonomy against the frozen corpus. If your plan contains no such comparison,
   write that down — the next reader will assume it does.
6. **Line-ending drift makes `config_hash` uninformative.** It is a raw-bytes sha256
   (`experiment_runner.py:542`), the isolated `agent_types.yaml` is LF while the frozen file is
   CRLF, so the hash differs for two reasons at once and cannot attribute the change. Compare the
   parsed governance block instead.
7. **Seeds 45 and 46 in the frozen corpus have no provenance at all** — 5 manifest keys against 19,
   no commit, no timestamp, no config hash. Not an E1 blocker (E1 is within-run), but if any pairing
   against the old corpus is planned, two of five pairs rest on unknowable code states.
8. **`governance_summary.json` undercounts the validator stack** — it records only the YAML thinking
   rules and omits the four Python builtin checks, including `demand_ceiling_stabilizer`, the most
   frequent rule in the corpus. Characterise the stack from the audit CSV, never from that file.

---

## 5. Your two questions, in plain language

### Is the WAGF instrumentation complete enough?

**Yes, with one named gap — and the gap does not block the question you are asking.**

The code records the agent's *first* appraisal and its *final* appraisal on every governed decision.
That is exactly what "did the recorded appraisal change after the system pushed back?" needs. I
confirmed the analysis script that computes it passes its own self-test, including its deliberate
mutation checks.

The gap: when a decision is retried several times, the appraisal is recorded only at the **start and
the end**. The middle attempts record the *action* the agent chose but not the *appraisal* it
reported. Two consequences you should state in the paper rather than discover in review:

- You cannot say whether the appraisal moves on the first push-back or only after repeated pressure.
  Any "more enforcement produced more revision" claim is not available from this data.
- A label that moves away and comes back — medium, then high, then medium again — records as
  *unchanged*. So your measured drift is a **floor, not a point estimate**. Report it that way.

Closing the gap is about two lines of code in two files. It is not worth delaying the 6 Aug fence
for, but it is worth knowing you chose not to do it.

One more thing worth being precise about in Methods: "first attempt" means the first attempt that
the system could *read*. If the model produced unparseable output and was asked to reformat, only
the last of those is captured (`broker/core/_retry_loop.py:144`). That is arguably the right
boundary for your question — but it is not literally "the first thing the agent wrote".

### Do the previous experiment settings line up, so a new run is a comparable arm?

**Yes for the run you are actually authorised to do — because it does not need to be comparable.**

This is the reassuring part, and it is worth understanding why. Option 1 measures something
*inside* each new run: on a single decision, did the appraisal at the start differ from the
appraisal at the end? That comparison never touches the old corpus. So the fact that the old runs
came from six different code versions, four of them with no recorded version at all, does not
matter here. `PLAN.md:239-241` makes exactly this argument, and it is sound.

**No, if you compare the new runs to the frozen corpus.** Three things have changed underneath, and
they stack:

1. A rejection that the old runs labelled `Unknown` will be labelled `precondition_violation` in the
   new runs. Same event, different word — in roughly a third of rows on a no-validator run.
2. New runs get an extra column (`shadow_blocked`) that the ten anchor runs do not have.
3. Two config files picked up small additions since the corpus was frozen. I checked both: neither
   is read at run time, so neither changes behaviour. That one is genuinely clean.

None of this affects Option 1. All of it affects the both-arms add-on, which is the arm where a
cross-corpus comparison would be tempting. If you take that add-on on 12 Aug, this list is the
pre-flight for it.

---

## 6. The command

**Do not run this until B1, B3 and B4 are resolved and the §4.1 context-size choice is confirmed.**

### Pre-launch checks — all must pass

```bash
# 1. Clean tree and tag (B4) — you do this, not an agent
git status --porcelain            # must be empty
git tag tae-firstattempt-2026-08-05

# 2. Isolation intact (B3) — must name agent_types.yaml + DIFF_AGAINST_FROZEN.md, nothing else
diff -rq examples/irrigation_abm/config SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt

# 3. The right tree is the one with BOTH keys
grep -A2 "audit:" SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt/agent_types.yaml
#   expect: initial_proposal_columns: true  AND  executed_skill_columns: true

# 4. GPU not on CPU fallback — the 2026-05-13 incident, 4 hours lost
nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv
ollama ps                          # PROCESSOR column MUST read 100% GPU
#   verified 2026-08-05 12:4x: RTX 4080 SUPER, 3612/16376 MiB; gemma3:1b at 100% GPU — healthy

# 5. Windows Update paused ≥ 4 days — the 2026-05-13 auto-reboot killed a run at year 10
#    Settings -> Windows Update -> Pause updates -> date >= 2026-08-09

# 6. Output collision — the runner does NOT refuse to overwrite (run_experiment.py:665)
ls SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42   # MUST fail: No such file or directory
```

### Seed 42 — launch this one only, then stop and read §7

```bash
python examples/irrigation_abm/run_experiment.py \
  --model gemma3:4b --real --years 42 --seed 42 --memory-seed 42 --workers 1 \
  --governance-mode strict \
  --num-ctx 8192 --num-predict 4096 \
  --config-dir SUBMISSION_2026/TAE/runs/config_irrigation_firstattempt \
  --output      SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
```

Seeds 43–46 are identical with `--seed`, `--memory-seed` and the `--output` suffix incremented.
Run them **sequentially**, one at a time, never in parallel — the 10.4 h/run costing assumes it, and
a parallel queue makes a silent death much harder to spot.

`--output` is explicit and under `SUBMISSION_2026/TAE/runs/`. Never omit it: a governed `gemma3:4b`
run without it writes next to the frozen `production_v21_42yr_seed<S>` corpus.

---

## 7. After seed 42 — before you launch the other four

This is the 11-hours-versus-110-hours checkpoint. Run all of it.

### The one most likely to fail — check it first

**`initial_labels` fill rate.** The integrity gate requires >95% non-empty on *all* rows **and**
>95% on the *retried* rows (`e3_run_integrity.py:91-92`). The only smoke evidence available comes in
**below both bars**:

| stratum | smoke (`gemma3:1b`, 15 rows) | gate |
|---|---|---|
| all rows | **93.33%** (14/15) | > 95% ❌ |
| retried rows | **80.00%** (4/5) | > 95% ❌ |

The empty row is not a parse failure — it has `status=APPROVED`, `retry_count=3` and a fully
populated `attempt_skills='maintain_demand\|maintain_demand\|increase_small\|maintain_demand'`. The
model produced an action and no appraisal labels.

Two caveats, stated honestly: n=15 rows and n=5 retried is far too small to be predictive, and
`gemma3:1b` is a much weaker model than the `gemma3:4b` you will run. The rate on 4b will very
likely be higher. But it is the only measurement that exists, it points the wrong way, and it lands
hardest on the retried stratum — which is the entire point of the experiment. **If seed 42 comes in
under 95% on retried rows, stop. Do not spend the remaining 41 GPU-hours.** The failure is not
random: a construct-less attempt-0 is exactly the low-quality generation most likely to be rewritten,
so dropping those biases measured drift *downward*.

```bash
python - <<'PY'
import csv
p='SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42/irrigation_farmer_governance_audit.csv'
rows=list(csv.DictReader(open(p,encoding='utf-8')))
ne=lambda rs:sum(1 for r in rs if (r.get('initial_labels') or '').strip())
rt=[r for r in rows if (r.get('retry_count') or '0').strip() not in ('','0')]
print('rows          %d   (expect 3276)'%len(rows))
print('ALL     %6.2f%%  (gate >95)'%(100*ne(rows)/len(rows)))
print('RETRIED %6.2f%%  (gate >95)  n=%d'%(100*ne(rt)/len(rt) if rt else 0,len(rt)))
print('executed_skill present:', 'executed_skill' in rows[0])
print('cols:', [c for c in ('initial_skill','initial_labels','attempt_skills','executed_skill') if c in rows[0]])
PY
```

### Then, in order

1. **The integrity gate itself** — the authoritative check, and the thing that will catch a silent
   death or a CPU-fallback run:
   ```bash
   python SUBMISSION_2026/TAE/evidence/e3_run_integrity.py \
     SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
   ```
   Exit 0 is necessary, not sufficient — read its output. It also enforces the config-isolation
   marker, so a wrong-tree launch surfaces here.

2. **Wall clock.** Expect ~10.4 h. Materially faster means something did not run; materially slower
   (≳2×) is the CPU-fallback signature — kill it rather than letting it finish 12× slow.

3. **`failed_rules` literal census** — the incident check, on real data for the first time:
   ```bash
   python - <<'PY'
   import csv,collections
   p='SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42/irrigation_farmer_governance_audit.csv'
   c=collections.Counter()
   for r in csv.DictReader(open(p,encoding='utf-8')):
       for t in (r.get('failed_rules') or '').split('|'):
           if t.strip(): c[t.strip()]+=1
   for k,v in c.most_common(): print('%8d  %s'%(v,k))
   PY
   ```
   Expect `precondition_violation`, **not** `Unknown` — that confirms the new-literal behaviour is
   live and understood rather than discovered later. **If `output_schema_violation` appears at all,
   B2 becomes urgent** — it is currently misclassified as a validator-rule hit.

4. **Row count and joins** — 3,276 audit rows and 3,276 sim rows, zero `(agent_id, year)` gaps or
   duplicates. e3 covers this; confirm you read it.

5. **The analysis actually runs on real data:**
   ```bash
   python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py --self-test
   python SUBMISSION_2026/TAE/evidence/e7_appraisal_drift.py \
     SUBMISSION_2026/TAE/runs/firstattempt_gov_seed42
   ```
   Check `comparable > 0` and that the no-initial-label count is small. A `comparable` of zero with
   a nonzero row count means the columns are present but empty — the failure mode in the fill-rate
   check above, surfacing a second way.

6. **GPU still on GPU.** Re-run `ollama ps` mid-queue at least once. The 2026-05-13 fallback was
   silent and cost four hours.

7. **Manifest sanity** — open `reproducibility_manifest.json` and confirm `agent_types_config`
   contains `config_irrigation_firstattempt`, and that `git_commit` matches the tag from B4.

---

## 8. What I could not establish

- **Whether `output_schema_violation` will actually fire** in this arm. It is reachable and has
  never been observed. I could not bound its rate — hence check 3 above.
- **The `initial_labels` fill rate at production scale.** Only the 15-row `gemma3:1b` smoke exists.
  This is the largest open risk in the plan and it is only measurable by running seed 42.
- **Which flood domain the brief's flood arm meant.** Single-agent and multi-agent both write
  `household_governance_audit.csv`. Moot unless B1 expands scope.
- **Whether the seven branch commits are byte-neutral with flags OFF on *irrigation*.** The
  commits' own evidence is a flood mock baseline, which proves `10e190cf ≡ origin/main` — a
  different claim from `10e190cf ≡ the frozen irrigation corpus`. Reading says neutral; no
  irrigation mock A/B has been run. Not load-bearing for Option 1, which is within-run.
- **The cause of 13 unexplained missing flood rows** (0.15%) across 8 runs, all
  `yearly_decision='N/A'`. Consistent with the pre-F1 drop path; no log confirms it.

---

*Read-only pre-flight. No file outside this report was created or modified, no run launched, no git
write performed, `.git/index.lock` untouched. Every quoted path and line number was read at
`p0-1-governance-instrumentation` @ `5ada0822` on 2026-08-05.*
