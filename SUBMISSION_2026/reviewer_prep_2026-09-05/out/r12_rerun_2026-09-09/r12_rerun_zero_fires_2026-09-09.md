# R12 follow-up — why zero HBM rule fires on the NEW arm (88c21542, seeds 42/43)

Read-only, no GPU/pytest, no edits under `examples/` or `broker/`. All numbers below
recomputed directly from the audit CSVs / JSON / YAML on disk (paths in each
section); nothing here is carried over from memory unverified.

Status: **COMPLETE** — all 5 points below, written incrementally as each was verified.

---

## 1. Construct label distributions + rule-precondition joint counts

Counts are out of 1000 rows per run. `other` lists any value outside VL/L/M/H/VH (none found, any arm).

### construct_SUSCEPTIBILITY_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 0 | 249 | 727 | 24 | 0 |
| NEW Run_43 | 2 | 241 | 737 | 20 | 0 |
| OLD-REJECTED Run_42 | 6 | 417 | 574 | 3 | 0 |
| OLD-REJECTED Run_43 | 7 | 393 | 590 | 10 | 0 |
| OLD-REJECTED Run_44 | 3 | 447 | 542 | 8 | 0 |

### construct_SEVERITY_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 18 | 451 | 291 | 240 | 0 |
| NEW Run_43 | 26 | 470 | 268 | 236 | 0 |
| OLD-REJECTED Run_42 | 26 | 404 | 365 | 205 | 0 |
| OLD-REJECTED Run_43 | 20 | 420 | 356 | 204 | 0 |
| OLD-REJECTED Run_44 | 37 | 434 | 340 | 189 | 0 |

### construct_BENEFITS_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 0 | 19 | 597 | 384 | 0 |
| NEW Run_43 | 0 | 20 | 567 | 413 | 0 |
| OLD-REJECTED Run_42 | 3 | 45 | 675 | 277 | 0 |
| OLD-REJECTED Run_43 | 2 | 48 | 625 | 325 | 0 |
| OLD-REJECTED Run_44 | 2 | 39 | 633 | 326 | 0 |

### construct_BARRIERS_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 47 | 209 | 230 | 512 | 2 |
| NEW Run_43 | 67 | 224 | 226 | 481 | 2 |
| OLD-REJECTED Run_42 | 58 | 107 | 397 | 435 | 3 |
| OLD-REJECTED Run_43 | 73 | 120 | 397 | 409 | 1 |
| OLD-REJECTED Run_44 | 77 | 133 | 401 | 386 | 3 |

### construct_SELF_EFFICACY_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 16 | 318 | 400 | 266 | 0 |
| NEW Run_43 | 14 | 294 | 407 | 285 | 0 |
| OLD-REJECTED Run_42 | 23 | 261 | 565 | 151 | 0 |
| OLD-REJECTED Run_43 | 21 | 258 | 543 | 178 | 0 |
| OLD-REJECTED Run_44 | 17 | 217 | 589 | 177 | 0 |

### construct_CUES_TO_ACTION_LABEL

| Run | VL | L | M | H | VH |
|---|---|---|---|---|---|
| NEW Run_42 | 73 | 364 | 437 | 126 | 0 |
| NEW Run_43 | 74 | 337 | 449 | 140 | 0 |
| OLD-REJECTED Run_42 | 49 | 395 | 505 | 51 | 0 |
| OLD-REJECTED Run_43 | 59 | 354 | 545 | 42 | 0 |
| OLD-REJECTED Run_44 | 35 | 380 | 530 | 55 | 0 |

**Labels did not vanish** — every label value the 5 rules key on (VL susceptibility, VL/L severity, VL/L benefits, H/VH barriers, H/VH self-efficacy, H/VH cues) still occurs in the NEW arm at broadly similar rates to OLD (e.g. NEW42 has 47 VL-barriers rows, OLD42 has 58; NEW43 has 2 VL-susceptibility rows, comparable order of magnitude to OLD's 6/7/3). `VH` is essentially absent in both arms for every column except BARRIERS (2-3 rows) — that is common to old and new, not a NEW-arm change.

### Joint precondition counts (label AND proposed_skill together, per rule)

| Run | R1 ERROR: sus∈{H,VH} ∧ sev∈{H,VH} ∧ eff∈{H,VH} ∧ proposed=refuse | R2 WARNING: sus=VL ∧ proposed=get_vaccinated | R3 WARNING: bar∈{H,VH} ∧ eff∈{H,VH} ∧ proposed∈{delay,refuse} | R4 WARNING: sev∈{VL,L} ∧ ben∈{VL,L} ∧ proposed=get_vaccinated | R5 ERROR: cue∈{H,VH} ∧ bar∈{VL,L} ∧ proposed=refuse |
|---|---|---|---|---|---|
| NEW Run_42 | 0 | 0 | 0 | 0 | 0 |
| NEW Run_43 | 0 | 0 | 0 | 0 | 0 |
| OLD-REJECTED Run_42 | 0 | 4 | 0 | 4 | 0 |
| OLD-REJECTED Run_43 | 0 | 6 | 0 | 2 | 0 |
| OLD-REJECTED Run_44 | 0 | 3 | 0 | 0 | 0 |

This matches the CSV's own `failed_rules`/`warning_rules` columns for R2 and R4 exactly (4/4, 6/2, 3/0 — the numbers reported in the prior interim report). **R3 never fires in any of the 5 runs, old or new** — it is chronically inert regardless of the fix; not a NEW-arm artifact.

**R1 and R5 (the two ERROR rules) are the one place the joint-precondition count does NOT explain everything.** OLD-REJECTED Run_44's own `failed_rules` column records 1 hit for `high_cues_low_barriers_refuse_inconsistent` (Agent_090, year 4, proposed=refuse, final=refuse, status=APPROVED — an ERROR-level rule that is logged but does not appear to have blocked here), yet that exact row's own `construct_CUES_TO_ACTION_LABEL`/`construct_BARRIERS_LABEL` values are **M / M** — neither satisfies the rule's own H/VH-cues + VL/L-barriers precondition. So for at least this one row, **the label values recorded in the final audit CSV do not match the label values the validator evaluated against** (rule fired against something other than what ended up in the row). This is checked directly (one concrete row, both fields printed above), not inferred, and it means: (a) the joint-precondition-count method above is a lower-bound / consistency check on the audit CSV's own columns, not proof of what the validator itself saw at evaluation time, and (b) it raises the same question for the NEW arm's zero fires — a precondition never being satisfied *in the final CSV columns* does not by itself prove the validator was never handed a satisfying label set. Point 2 below (governance counters + config diff) and point 3 (validator_health.csv) are the more direct way to answer whether the validator ran at all.

---

## 2. Was the validator actually running on the NEW arm?

### Run-level counters (`governance_summary.json`, `audit_summary.json`)

| Counter | NEW Run_42 | OLD-REJECTED Run_42 |
|---|---|---|
| `governance_summary.json: total_interventions` | 0 | 0 |
| `governance_summary.json: warnings.total_warnings` | 0 | 8 |
| `governance_summary.json: warnings.warning_rule_frequency` | `{}` | `{low_susceptibility_no_get_vaccinated: 4, low_severity_low_benefits_get_vaccinated: 4}` |
| `audit_summary.json: validation_errors` | 0 | 0 |
| `audit_summary.json: validation_warnings` | 0 | 8 |
| `audit_summary.json: validator_health` | `{}` | 2 rule_ids, each with `seen_count`/`fire_count`/`warn_count` |
| `audit_summary.json: total_traces` | 1000 | 1000 |
| `run_integrity.json: governance_mode` | `strict` | `strict` |

`validator_health` (both the summary JSON and, on OLD, `validator_health.csv`) only lists rule_ids with `seen_count > 0` — i.e. it is populated **from the same precondition-match events** as the joint counts in section 1, not an independent "the engine executed" signal. Its emptiness on NEW is consistent with, but does not independently prove more than, section 1's finding that 0/1000 rows satisfy any rule's precondition.

### Audit CSV validation-related columns, NEW42 vs OLD42 (all 1000/1000 unless noted)

| Column | NEW Run_42 | OLD-REJECTED Run_42 |
|---|---|---|
| `validated` | `True` ×1000 | `True` ×1000 |
| `parse_layer` | `enclosure+json` ×1000 | `enclosure+json` ×1000 |
| `rules_evaluated_count` | `0` ×1000 | `0` ×1000 |
| `rules_triggered` | `''` (blank) ×1000 | blank ×993, non-blank ×7 (matches the 4+4 warning-rule hits, one row double-triggers) |
| `shadow_blocked` | `''` ×1000 | `''` ×1000 |
| `condition_0/1/2_matched` | blank ×1000 (all three cols) | blank ×1000 (all three cols) |

**`rules_evaluated_count` is uninformative for this question** — it reads `0` on literally every row in *both* arms, old and new, so it is either a column the pipeline never populates or counts something unrelated to the 5 thinking-rules; it cannot be used to tell "validator ran and found nothing" apart from "validator did not run." `condition_0/1/2_matched` are likewise blank on every row in both arms (these appear to serve a different rule type not exercised in either vaccination batch). The one column that behaves as expected is `rules_triggered`, and it agrees exactly with `warning_rules`/`failed_rules` on OLD and is uniformly blank on NEW — i.e. every column in the audit CSV that IS observed to vary with rule activity says "zero activity" on NEW, consistent with (not independently additional to) section 1.

**No audit-CSV or summary-JSON counter in this schema distinguishes "validator executed and found 0 matches" from "validator did not execute."** That distinction would need instrumentation the pipeline doesn't currently write (a true per-row "rule engine invoked" counter) — not established by this read-only check.

### `config_snapshot.yaml` diff, NEW Run_42 vs OLD Run_42 (full-file diff, not just the `thinking_rules:` block)

```
91a92,93
>       description: 'Numeric ID, choose ONE from: 1, 2, or 3 (1=get_vaccinated, 2=delay,
>         3=refuse)'
151d152
<     full_disclosure: true
```

Only two differences in the entire file:
1. OLD has an extra `description:` field on the `decision` schema key spelling out the hardcoded digit legend (`1=get_vaccinated, 2=delay, 3=refuse`); NEW does not (matches "removed a hardcoded digit legend").
2. NEW has `full_disclosure: true` under `individual:` parsing config; OLD does not have this line at all (matches "set `parsing.full_disclosure: true`").

**The `thinking_rules:` block (all 5 rule ids, levels, `blocked_skills`, `conditions`, and message text) is byte-identical between the two files** — confirmed by its absence from the diff output above (a diff against the full file would surface any change in that block; none appears). `governance_mode: strict` is identical in both `run_integrity.json`s. **No `enabled`/threshold/governance-profile difference exists between the two snapshots** — the only two differences anywhere in the file are the ones the task already named as the intended fix.

---

## 3. Why is `validator_health.csv` absent on the NEW runs but present on OLD?

Grepped `validator_health` across `C:/Users/wenyu/Desktop/Lehigh/wagf-vax-runs/broker` (the worktree at commit `88c215429410`, same commit as the NEW arm). Writer is `broker/components/analytics/audit.py`.

**The write is conditional, not unconditional** (`audit.py:1208-1211`):

```python
vh = self.summary.get("validator_health", {})
if vh:
    ...
    vh_path = self.output_dir / "validator_health.csv"
    ...
```

`validator_health.csv` is only written when the in-memory `self.summary["validator_health"]` dict is non-empty. So its absence, by itself, is a direct restatement of `vh == {}` — the same fact `audit_summary.json`'s embedded `"validator_health": {}` already reports (section 2), not an independent signal on top of it.

**When does an entry get added to `vh`** (`audit.py:1041-1055`, the loop that runs once per row over that row's `validation_results`):

```python
for r in validation_results:
    metadata = getattr(r, "metadata", None) or {}
    rid = metadata.get("rule_id")
    if (
        not rid
        and r.valid
        and not getattr(r, "warnings", None)
        and not metadata.get("shadow_blocked")
    ):
        continue                      # <-- clean pass, no rule_id: not counted at all
    rid = rid or "Unknown"
    vh = self.summary["validator_health"].setdefault(rid, {
        "rule_id": rid, "seen_count": 0, "fire_count": 0,
        "warn_count": 0, "error_path_count": 0,
    })
    vh["seen_count"] += 1
    ...
```

A `validation_result` only increments `seen_count` for a rule if it carries a `rule_id` in its `metadata`, or is itself invalid/warned/shadow-blocked. A `validation_result` that is a clean pass with **no** `rule_id` (`r.valid=True`, no warnings, not shadow-blocked) is explicitly skipped by the `continue` and never touches `validator_health` at all.

**Answer to the question as posed:** the writer is **unconditional on file-write given `vh` is non-empty, but `vh` itself is populated only by precondition-matching events, not by "the rule was checked."** So:
- `validator_health.csv`'s absence *is* a signal — but it is the same signal as `audit_summary.json`'s embedded `validator_health: {}` and `governance_summary.json`'s `warning_rule_frequency: {}`: **zero rule-precondition-matching validation events occurred in the run.**
- It is **not**, by this code's own design, a signal that the validator engine failed to execute or was skipped. A hypothetical run where the rule engine genuinely evaluated all 5 rules against all 1000 rows and none of them ever matched a precondition would produce byte-identical output here (no file) to a run where the rule engine was never invoked at all. This code path cannot distinguish those two cases — nothing read in this investigation can, given what the pipeline currently logs (this was flagged as an open question in section 2 as well).

---

## 4. Rendered-prompt diff — same agent + year, OLD vs NEW

Agent_001, year 3, Run_42 both arms. Extracted `input` verbatim from each `raw/individual_traces.jsonl` (OLD 2887 chars, NEW 3273 chars) and diffed:

```diff
--- OLD Run_42 (e0eee08c)
+++ NEW Run_42 (88c21542)
@@ -15,7 +15,7 @@
   - Side-effect signal in your community: amplified

 Your memory of recent events:
-- Year 1: Decided to: Delay
+- Year 1: Decided to: Get vaccinated
 - Year 2: Decided to: Get vaccinated

 Using the **Health Belief Model**, weigh:
@@ -34,7 +34,10 @@
   6. CUES TO ACTION — whether external signals (outbreak news,
      doctor / family advice) are nudging you toward action.

-Available actions: [N/A]
+Available actions:
+1. Receive a single dose of the recommended vaccine this year. Provides partial-to-high protection against infection and severe outcomes.
+2. Postpone the vaccination decision this year — wait for more information about safety, efficacy, or outbreak conditions before acting.
+3. Decline vaccination this year. May be motivated by perceived low susceptibility, fear of side effects, or distrust of public health messaging.

 ### RATING SCALE (You MUST use EXACTLY one of these codes):
 VL = Very Low | L = Low | M = Medium | H = High | VH = Very High
@@ -53,6 +56,6 @@
   "barriers_assessment": ...
   "self_efficacy_assessment": ...
   "cues_to_action_assessment": ...
-  "decision": "<Numeric ID, choose ONE from: 1, 2, or 3 (1=get_vaccinated, 2=delay, 3=refuse)>"
+  "decision": "<Numeric ID, choose ONE from: 1, 2, or 3>"
 }
```

**Three regions differ, not two:**

1. **`Available actions: [N/A]` (OLD) → the actual 3-line menu (NEW).** This is the `{skills}`→`{options_text}` fix landing exactly as described — the OLD arm's year-3 prompt literally told the model the menu was `[N/A]` (the builder never filled the placeholder past year 1), while the model was still asked to answer with a numeric `decision`. This is the direct, visible mechanism behind the pre-fix 49-88%/year mismatch: from year 2 on, the model had no menu text to ground a digit choice in.
2. **The hardcoded digit legend in the `decision` field's schema description** — present in OLD (`1=get_vaccinated, 2=delay, 3=refuse`), removed in NEW. Matches the `config_snapshot.yaml` diff in section 2 exactly (that legend is the `description:` field removed there).
3. **"Your memory of recent events" — Year 1 line differs ("Delay" vs "Get vaccinated").** This is **not** a template/prompt-fix difference — it is content, verified directly: OLD Run_42's own audit CSV records Agent_001's year-1 `proposed_skill` as `delay` (OLD prompt memory says "Decided to: Delay"); NEW Run_42's records it as `get_vaccinated` (NEW prompt memory says "Decided to: Get vaccinated"); year 2 is `get_vaccinated` in both and both prompts agree on that line. The two arms are independent LLM runs (different commit, different actual model outputs from year 1 onward), so their own histories diverge — the memory line each prompt shows is exactly that run's own true history, not a template artifact.

**`parsing.full_disclosure: true` produces no visible difference in the rendered prompt** — expected, since it is a parser-side flag (sits under the `individual:` parsing/preprocessor block in `config_snapshot.yaml`, not the prompt-template block), so it would not be expected to change prompt text at all; nothing in this diff is unaccounted for.

So: the task's 3 named changes are confirmed as **2 visible prompt-text differences** (`options_text` menu, digit-legend removal) **+ 1 non-prompt-visible config flag** (`full_disclosure`), and there is exactly **one additional difference** in this diff (the memory recap line), fully explained as genuine cross-run content variance, not a residual template bug.

---

## 5. Where do `construct_*_LABEL` values come from?

**They are the model's own self-reported appraisal, parsed straight out of `raw_output`'s own JSON — not a post-hoc scorer.** Code path, `wagf-vax-runs` worktree (commit `88c215429410`, same as NEW arm):

1. `broker/utils/parsing/unified_adapter.py` (~lines 604-696) — the response parser. For each schema field whose YAML key contains `"label"` (e.g. `susceptibility_assessment.label`), it matches the field against the `*_LABEL` construct names declared in `config_snapshot.yaml`'s `response_format.fields` (the `construct: SUSCEPTIBILITY_LABEL` entries seen in section 2's config excerpt), regex-extracts/normalizes the value, and writes `reasoning["SUSCEPTIBILITY_LABEL"] = value.upper()` into the parsed `skill_proposal.reasoning` dict.
2. `broker/components/analytics/audit.py:757-758` — the audit-row builder copies every `reasoning` key ending in one of `_CONSTRUCT_SUFFIXES = ("_LABEL", "_UTIL", "_GAP", "_IMPACT", "_APPETITE")` (`audit.py:481`) straight into the CSV row as `construct_<key>` — i.e. `row["construct_SUSCEPTIBILITY_LABEL"] = reasoning["SUSCEPTIBILITY_LABEL"]`, verbatim, no rescoring.

So the pipeline is: model writes `{"susceptibility_assessment": {"label": "M", ...}}` in `raw_output` → parser lifts `.label` into `reasoning["SUSCEPTIBILITY_LABEL"]` (upper-cased) → audit writer copies it into the CSV column of the same name. No separate labelling model or heuristic scorer is involved.

### 3 raw_output excerpts, NEW arm, checked against their own CSV columns

| Run/Agent/Year | Construct | `raw_output`'s own `<x>_assessment.label` | CSV `construct_<X>_LABEL` | |
|---|---|---|---|---|
| 42/Agent_001/Y1 | SUSCEPTIBILITY / SEVERITY / BENEFITS / BARRIERS / SELF_EFFICACY / CUES_TO_ACTION | M / H / H / H / M / H | M / H / H / H / M / H | all match |
| 42/Agent_050/Y5 | same 6 | L / VL / M / L / M / M | L / VL / M / L / M / M | all match |
| 43/Agent_099/Y10 | same 6 | L / L / M / H / L / VL | L / L / M / H / L / VL | all match |

18/18 label values checked (3 rows × 6 constructs) match exactly between the model's own JSON and the audit CSV column — the labeller is reading the field it is supposed to. (`decision` digit also cross-checked in the same 3 rows against `proposed_skill`, consistent with section 1's 100% parity: 1→get_vaccinated, 1→get_vaccinated, 3→refuse, all matching.)

---

## Bottom line — why zero HBM rule fires on the NEW arm

1. **Not a missing-label artifact.** All label values the 5 rules key on still occur in the NEW arm at rates comparable to OLD (section 1); `VL`/`VH` did not disappear.
2. **It is a shifted joint distribution of (label, proposed action), verified directly, not inferred.** 0/1000 rows on either NEW seed satisfy any of the 5 rules' own precondition (label AND action together), versus 4-7 matching rows per OLD seed for the 2 WARNING rules that fired historically. The labels alone are present; the specific label+action combination the rules watch for is not, in this batch.
3. **The validator machinery itself is unchanged and, as far as this investigation's tools can tell, was exercised the same way in both arms** — identical `thinking_rules:` block, identical `governance_mode: strict`, identical `validated=True`/`parse_layer` columns. But no counter in this schema (`rules_evaluated_count` reads 0 on every row in both arms; `condition_0/1/2_matched` are blank in both) can distinguish "ran and found nothing" from "did not run" — `validator_health`/`validator_health.csv` and `rules_triggered` only populate on an actual precondition match, so their emptiness on NEW restates fact #2, it does not add independent confirmation the engine executed. This is a real instrumentation gap, stated as one, not closed by this check.
4. **One caveat on the audit CSV's own reliability for this kind of check**: OLD-REJECTED Run_44 has one row where `failed_rules` records an ERROR-rule fire whose own `construct_CUES_TO_ACTION_LABEL`/`construct_BARRIERS_LABEL` values (M/M) do not satisfy that rule's precondition — meaning the validator can evaluate against label values that differ from what ends up recorded in the same row. This is a single concrete example, not shown to recur elsewhere in this check, and is flagged rather than explained.
5. **The prompt fix itself is confirmed narrow.** Diffing the actual rendered prompt (section 4) for a matched agent+year shows exactly two template-level changes (the `options_text` menu replacing `[N/A]`, and the digit-legend removal) plus one non-prompt-visible parser flag (`full_disclosure`) — nothing in the fix touches the appraisal-label instructions, the HBM construct definitions, or the `thinking_rules:` block, so the shifted (label, action) joint distribution is not explained by anything in the diff itself; establishing *why* the model's own appraisal-to-action mapping shifted would require comparing model behavior pre/post fix, which is outside what a read-only audit-trace check can determine.
