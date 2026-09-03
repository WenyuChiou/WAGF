# Factor ablation: testing what a decision actually used

## The question this answers

A WAGF agent's reasoning trace usually names a reason:

> "Because 25% of my neighbours elevated and grants are available, I
> elevate my house."

That sentence is a self-report. It tells you what the model *said*; it
does not tell you what the model *used*. Since 2023 the
chain-of-thought faithfulness literature has repeatedly shown the two
come apart in both directions — models act on cues they never mention,
and mention cues that make no difference when removed.

This tool turns the sentence into a testable claim. Take the same
recorded decision, replace the neighbour sentence with a documented
neutral rendering, re-run the same decider at the same seed, and measure
whether the probability of the reported action moves. That is an
intervention on one component of the agent's context — every other word
of the prompt held fixed — rather than a reading of the model's prose.

## The question it does NOT answer

It does not tell you whether the reasoning text was honest. A factor can
be causal and unmentioned; it can be mentioned and inert. The ablation
measures behaviour under intervention. The reasoning text stays a
separate observable, and nothing in this pipeline treats it as evidence
for the mechanism.

It also does not establish that the factor matters in the world. It
establishes that this decider, on these recorded decisions, moved when
that part of its prompt changed.

## What it refuses to do, and why to read that first

Four refusals fire before any number is printed. Each one exists because
the alternative was a plausible-looking table nobody could tell from a
real result.

| Refusal | What it stops |
|---|---|
| No `--model` and none in the manifest → the tool stops. | A silent fallback to `mock`. The mock decider returns the first numbered option whatever the prompt says, so every factor comes back at exactly zero and the table reads like a finding. |
| `--with-governance` without `--validators-module` → the tool stops. | Replaying irrigation with **zero** domain validators while every row says `governance_evaluated=true`. A run directory records the agent config but not the `custom_validators` the experiment passed to `ExperimentBuilder.with_custom_validators()`. |
| `--with-governance` on any trace WAGF writes today → the replay stops. | Re-offering one-way skills. The audit writer does not record `context["available_skills"]`, so the rebuilt context has none, and `SkillBrokerEngine._inject_filtered_skills` falls back to the domain's full action list — offering elevation to a household that already elevated, which is the R5 re-elevation term the project's IBR definition excludes on purpose. |
| `--action-stage executed` without `--with-governance` → the tool stops. | Anchoring on the post-governance action in a mode where no validator ran, so every executed-stage distribution would be a column of `__unparsed__`. |

The third one means `--with-governance` is **unavailable in practice**
until the audit writer records the option set. Parse-only replay — the
default — is unaffected: it reports the model's proposal, and marks
`validator_verdict` as `not_evaluated` rather than inventing one.

## Running it

```bash
python -m broker.tools.ablate_factor <run_dir> \
    --masks examples.single_agent.flood_factor_masks:FLOOD_FACTOR_MASKS \
    --factor neighbor_adoption_history,grant_availability_history \
    --control paraphrase \
    --seeds 42,43 --replicates 3 \
    --model mock \
    --out results/ablation
```

Three files land in `--out`:

| File | What it holds |
|---|---|
| `ablation_samples.csv` | One row per replay. The raw data; every row carries its fidelity regime and the determinism verdict. |
| `ablation_summary.json` | Per-factor delta-P, JSD, KL, the paired tests, and a one-sentence verdict. |
| `determinism_report.json` | The gate: whether the decider returns the same answer to the same question. |

To see what a domain declares before running anything:

```bash
python -m broker.tools.ablate_factor <run_dir> \
    --masks examples.single_agent.flood_factor_masks:FLOOD_FACTOR_MASKS \
    --list-factors
```

`--domain <name>` reads the factors from a registered DomainPack
instead. An unregistered name is an error, not an empty list: falling
through to `DefaultDomainPack` would answer "this domain declares no
factors", which reads as a fact about the domain rather than a
misspelling.

## The three arms

Each factor is replayed in up to three arms, all at the same seeds:

| Arm | Prompt | What it is for |
|---|---|---|
| `baseline` | Exactly what the agent saw. | The reference distribution, and a check that the replay reproduces the recorded decision. |
| `masked` | The factor replaced by its neutral rendering. | The intervention. |
| `paraphrase_control` | The factor reworded, information preserved. | The severity-matched control. |

**The control arm is the part people leave out, and it is the part that
makes the number mean something.** Suppose masking the neighbour
sentence flips 40% of decisions. That is consistent with two very
different stories: the model uses neighbour information, or the model is
simply unsettled by any edit of that size in that position. The
paraphrase arm changes the same span by roughly the same number of
characters and keeps the information. If the paraphrase flips 40% too,
the factor explains nothing that a generic perturbation would not.

`effect_vs_control` is `delta_p_masked - delta_p_control`. Read that,
not `delta_p_masked` alone.

An arm whose mask changed nothing — the factor is absent from this
prompt, or the factor declares no paraphrase — never reaches the
decider. Its prompt would be byte-identical to the baseline the cell
already holds, so the call buys a duplicate of a result the run has, and
on a real backend it is the largest avoidable cost in the grid. The row
is still written, with `decider_called=false` and the reason, so a
skipped cell is visible rather than missing.

### Severity is scored per snapshot, not on the means

The summary reports a `severity` block per factor: the ratio of the
smaller edit to the larger, computed **inside each snapshot**, plus the
worst pair (`min_ratio`), the mean, and how many pairs fell below the
0.5 floor. `matched` is true only when every pair clears it.

Comparing the mean masked edit against the mean control edit hides the
case the check exists to catch. A factor whose pattern matches one
memory bullet in half the snapshots and five in the other half can have
two means within a few characters of each other while not one individual
snapshot is matched: the means cancel, the ratio reads 0.98, and the run
claims a severity match it does not have.

## The determinism gate

Before any grid runs, the tool replays a **sample** of the unmasked
snapshots several times each at a fixed seed (`--determinism-snapshots`,
five by default; `0` gates every snapshot). The gate is a question about
the backend, not about any one prompt, and gating all 3,276 snapshots of
a real corpus costs more than the grid it guards.

Passing needs three things at once:

1. every reply identical — the parsed skill *and* the raw text;
2. no reply empty;
3. at least one reply that parsed.

The reason for (1) is simple. A delta-P is a difference between two
conditions. If replaying one condition twice already produces two
answers, the difference between conditions cannot be attributed to the
intervention. This is not hypothetical for WAGF: Phase 6R-D-4 measured
`gemma4:e4b` on Ollama producing a ~166-line diff between two runs at
the same code commit and the same seed.

The reason for (2) and (3) is the failure that looks like success. When
the Ollama server is not running, `create_llm_invoke`'s `invoke`
exhausts its retries and returns `("", stats)`; the parser returns
`None` for empty text. Every replay then comes back identical —
identically empty. On identity alone that is the most consistent backend
imaginable and the least informative, and the whole grid downstream
would report exact zeros for every factor. The gate counts
`n_empty_raw` and `n_unparsed` and says
*"identical but not a decision — check the backend"*.

When the gate fails, the tool still writes the sample table — the
replays happened and are data — but:

* `AblationResult.delta_p` is `None`,
* every summary block reads `ΔP withheld: …`,
* **every effect quantity in every factor block is `null`** —
  `delta_p_masked_mean`, `delta_p_control_mean`, `effect_vs_control`,
  all three `wilcoxon_*` blocks, `jsd_masked_mean`, `jsd_control_mean`,
  `kl_masked_mean`, `kl_control_mean` and `directional_consistency` —
  with `withheld: true` on the block. JSD, KL and directional
  consistency come from the same replays as delta-P and mean exactly as
  little; leaving them populated left three numbers a reader could quote
  out of a table whose headline had just been refused.
* every CSV row carries `determinism_verified = False`.

The counts that explain the withholding survive:
`n_snapshots_with_factor`, `n_snapshots_factor_absent`, the `severity`
block and `matches_mean` / `matches_max` are diagnosis, not effect.

There is no flag to override this.

Determinism is also checked *during* the run: `--replicates N` repeats
each cell, and if two replicates of the same prompt at the same seed
disagree, the run fails the same way. On a decider that passes the gate,
replicates are redundant by construction — that is exactly what makes
them a useful monitor.

A factor is withheld on its own account too: if any of the **baseline,
masked or control** replays it is measured against came back empty or
unparsable, its verdict reads `verdict withheld: N of M replays
(baseline K, masked/control J) returned no decision` and its effect
quantities are nulled. A no-decision reply saturates delta-P at -1.000
wherever it lands — baseline or arm — so both sides of the pair are
counted; checking only the baseline side let a masked or control arm's
missing decision through as though it were a real -1.000 effect.

## Fidelity: one regime, and why the column stays

Every row carries a `fidelity` column, and today it has exactly one
value: `prompt_only`. The trace records the rendered prompt but not the
context that produced it, so the replay edits the prompt text with a
regular expression. Everything downstream is unchanged — the same
`ModelAdapter`, the same parser.

`GenericAuditWriter` records `input` (the rendered prompt), `memory_pre`,
`social_audit`, `environment_context` and `state_before`. Those are
derived summaries. It does not record `context` as
`TieredContextBuilder.build` returned it, and several branches of that
dict — `local.spatial`, `institutional`, `global`, `system_prompt`,
`available_skills`, the rendered options text — cannot be recovered from
the summaries.

A context-level replay — edit the context where the model builder
declared the factor, then re-render through the domain's own template —
is **not implemented**, and no code path pretends otherwise. A trace
that already carries a `context_snapshot` key is logged
(*"context_snapshot present but context-level replay is not implemented;
using prompt_only"*) and replayed as `prompt_only` like everything else.

The column stays anyway, single-valued, so the schema is
forward-compatible: when the audit writer starts recording the builder's
context, a second value can be added without changing the shape of any
table already published.

What `prompt_only` costs you: the intervention is a string substitution
rather than an edit at the point where the model builder declared the
factor.

## Masks substitute; they never delete

A `MaskSpec` replaces the factor's span with a documented neutral
rendering:

> `I observe 25% of neighbors elevated and 0% relocated.`
> → `No information about neighbours is available.`

It does not delete the sentence. Deleting changes the prompt's shape as
well as its content, the model sees a stimulus unlike anything in the
run, and a behaviour change no longer isolates the factor. An empty
neutral rendering is refused at declaration time.

**Every occurrence is replaced.** A flood household in year 6 sees five
"Year N: Elevation grants are available." bullets, one per remembered
year, and the mask replaces all five. So the factor being removed is
"everything this agent remembers about grants", not "this year's grant
signal" — which is why three of the four shipped flood factors are named
`*_history`. Each row records `n_matches`, and each factor block reports
`matches_mean` and `matches_max`, so one masked bullet and five masked
bullets are distinguishable in the table.

If a factor's pattern matches nothing in a given prompt — an agent with
no neighbours, a year with no grant — that snapshot is counted under
`n_snapshots_factor_absent` and excluded from the factor's statistics,
rather than scored as a null effect.

If a rendering *callable* raises — the flood `insurance_trust`
paraphrase raises when `FloodContextBuilder._verbalize_trust` emits a
phrase it does not know — the failure is caught, that arm's row is
written with `applied=false` and the reason, and the rest of the grid
continues. One factor's stale vocabulary does not throw away every other
factor's rows.

## Declaring factors for your own domain

Implement `context_mask_defaults()` on your DomainPack (the default
returns `{}`):

```python
from broker.experiments.replay import MaskSpec

class MyDomainPack(DefaultDomainPack):
    def context_mask_defaults(self):
        return {
            "neighbour_uptake_history": MaskSpec(
                provider="SocialProvider",
                key="local.neighbor_action_summary",
                pattern=r"I observe (\d+)% of neighbors elevated",
                neutral="No information about neighbours is available.",
                paraphrase=r"Neighbour uptake stands at \1% elevated.",
                expected_sign=-1,
                description=(
                    "Every neighbour-observation bullet the agent "
                    "remembers, not only the most recent."
                ),
            ),
        }
```

Five rules for writing one:

1. **Match the string the pipeline actually emits**, not one you wrote
   from memory. A pattern that matches nothing produces a null result
   indistinguishable from a null finding. The worked example at
   `examples/single_agent/flood_factor_masks.py` enumerates the exact
   phrases `FloodContextBuilder._verbalize_trust` can produce, and its
   tests assert all four patterns match a real prompt.
2. **Name the factor for the span it covers.** Every occurrence is
   replaced, so a pattern that matches a yearly memory bullet removes
   every remembered year. `grant_availability_history` and
   `grant_availability_current` are different factors and should not
   share a name — and if the prompt has no current-year line to anchor
   the `_current` variant on, do not declare one. Say so in the
   docstring instead, as the flood example does.
3. **The neutral rendering must be a plausible sentence**, phrased the
   way the domain would phrase an absence of information.
4. **The paraphrase must keep the information and change only the
   wording**, by roughly the number of characters the neutral rendering
   changes. If it drops a number, it is a second mask, not a control.
   `paraphrase=None` is allowed and means the factor has no control; the
   summary then reports the masked arm with an explicit statement that
   it cannot be separated from generic edit-sensitivity.
5. **Declare `expected_sign` if the usual direction is wrong for this
   factor.** The default `-1` says removing the factor should make the
   recorded action *less* likely. A deterrent — a factor whose removal
   should make the action *more* likely — declares `+1`, and
   `directional_consistency` is then scored against the direction your
   domain actually claims.

Do not add the hook to a frozen production pack. Register a subclass
under a second domain name, as `flood_factor_masks.register()` does —
re-registering `"flood"` would swap the production pack out from under
every run in the process, and the helper refuses to.

## Reading `ablation_summary.json`

Beyond the per-factor blocks, these run-level fields decide whether the
per-factor numbers are worth reading at all:

| Field | Read it as |
|---|---|
| `determinism_verified` | False means every effect quantity in the file is `null`. |
| `decision_quality` | `n_decider_calls`, `n_empty_outputs`, `n_unparsed`, `n_errors`, and how many arms were skipped because nothing was edited. A high empty count with a "verified" gate is impossible by construction; a high empty count at all means the backend was intermittently unreachable. |
| `trace_intake` | How many trace rows the JSONL files held, how many were malformed, how many carried no prompt, and how many became snapshots. `n_snapshots` without this has no denominator. |
| `model_used` / `model_source` | The one model this run used, and where the name came from (`cli --model` or the run manifest). Never inferred, never defaulted. |
| `validators_source` | Which validators ran. `none (parse-only: no validator ran)` on the default path. |
| `baseline_reproduces_trace` | The unmasked replay's agreement with the recorded decision, plus `n_recorded_missing` — baseline replays whose trace recorded no action at all. Those are excluded from the rate, not counted as agreement. Well below 1.0 means the reconstruction is not reproducing the original, and the masked arms are measuring something else. |
| `decider_prompt_sensitivity` | How often any edit **that actually happened** changed a decision. Arms whose factor was absent are excluded from the denominator (`n_arms_excluded_factor_absent` counts them) — otherwise a factor missing from most prompts reports a reassuringly low sensitivity that is an artefact of the denominator. Zero changes means either no factor is used or the decider does not read the edited text; the built-in `mock` decider returns the first numbered option whatever the prompt says and produces exactly this pattern. When the determinism gate did not pass, this block carries `withheld: true` and its `note` says so — the replays are the same non-deterministic (or empty) backend calls the gate already flagged, not an independent measurement of prompt sensitivity. |
| `seeds_applied_to_decider` | False means the decider takes no seed, so the seed column holds repeats of one call. The rows are still paired; the seeds are labels, not draws. **This is False for every backend `create_llm_invoke` exposes today** — the mock, the Ollama direct path and the cloud provider wrappers all have the signature `invoke(prompt)`. A `**kwargs` catch-all does not count: it may forward the seed to something that ignores it. |

Inside a factor block:

| Field | Read it as |
|---|---|
| `delta_p_masked_mean` | Mean change in the probability of the recorded action when the factor is neutralised. Negative = removing the factor made the reported action less likely, the direction `expected_sign` assumes. |
| `delta_p_control_mean` | The same for the paraphrase arm. Should be near zero if the factor, not the edit, is doing the work. |
| `effect_vs_control` | The headline. Masked minus control. |
| `wilcoxon_masked_vs_control` | Paired Wilcoxon signed-rank across snapshots on the two arms' delta-P. `p_value: null` with `method: "undefined"` means every pair tied exactly — a real result, not a skipped test. `p_value: null` with `p_value_below_minimum` set means the sample was too small; see below. |
| `p_value_withheld` | Non-null when fewer than `min_pairs_for_p` (8) pairs moved. |
| `jsd_masked_mean` | **The primary distributional number.** Distance between the baseline and masked action distributions per snapshot, in [0, 1]. On a deterministic decider these are 0 or 1 by construction; the inference lives in the across-snapshot paired test. |
| `kl_masked_mean` | Secondary, and misleading if read as a distance. Between two point masses — which is what every cell is on a verified-deterministic decider — KL is `log2(1/KL_EPSILON)` when they differ and 0 when they agree: a flip indicator times a constant that depends only on the smoothing term, not on how far apart the distributions are. Read JSD. |
| `directional_consistency` | Fraction of the snapshots that moved that moved in the **assumed** direction. `expected_sign` is returned beside it; the count means nothing without it. |
| `matches_mean`, `matches_max` | How many spans the mask replaced per snapshot. One and five are different interventions. |
| `severity` | Per-snapshot edit-size matching; see above. |
| `n_snapshots_baseline_never_produced_the_recorded_action` | Snapshots where the anchor is an action this decider does not choose. A large number makes the delta-P near-meaningless and the verdict says so. |
| `withheld` | True when this factor's numbers were refused — by the run-level determinism gate, or by its own baselines returning no decision. |

### Why a p-value is withheld below eight moving pairs

The two-sided exact signed-rank test on *k* non-zero pairs cannot return
anything below `2**-(k-1)` — every pair moving the same way is the most
extreme arrangement the test has. At k=7 that floor is 0.0156, so a
"p = 0.016" from seven snapshots is the smallest number the design can
produce rather than a measurement of anything. At k=8 the floor is
0.0078, the first value under the 0.01 a reader treats as strong.

Below that the verdict prints

> `p withheld: n_nonzero=6 below minimum 8 (attainable floor 2^-(6-1) = 0.03125; the smallest p this many pairs can produce, reached whenever they all move the same way)`

and the Wilcoxon block moves the number from `p_value` to
`p_value_below_minimum`, with `p_withheld` beside it. The number is kept
— an auditor should be able to see it — it just stops being the field a
reader quotes by reflex.

## Which action is `A`

`delta_p` is measured against the action the trace recorded, because
that is the decision whose stated reason is under test. By default that
is the *proposed* skill — the model's own choice, the one the reasoning
text explains. `--action-stage executed` switches both the anchor and
the replay distributions to the post-governance action, and requires
`--with-governance` for the reason in the refusals table above.

The project's EXECUTED-ONLY rule for headline governance metrics is a
different question and still applies there. A mechanism probe anchored
on the executed action would be measuring the validators as much as the
model, which is why `proposed` is the default here.

## Governance

By default the CLI reports the *proposal* the decider produced and marks
`validator_verdict` as `not_evaluated`. That is what a run directory
alone supports: a run records its agent config but not its skill
registry or its custom validators, and a verdict from a guessed registry
would be fiction.

`--with-governance` would rebuild the validators and the skill registry
and replay through `SkillBrokerEngine.process_step` — the same parser,
the same validators, the same governance retry loop, with
`simulation_engine=None` and `audit_writer=None` so nothing executes and
nothing is written. It requires:

* `--validators-module <import path>`, a module exposing
  `build_custom_validators(config) -> list` and returning the same list
  the experiment passed to `ExperimentBuilder.with_custom_validators()`;
* `skill_registry.yaml` beside the agent config;
* a trace that records `context["available_skills"]` — which **no WAGF
  run does today**, so the replay refuses at the first snapshot and says
  so.

`enable_financial_constraints` is read from the agent config
(`global_config.governance.financial_constraints`) rather than left at
the constructor default, so a replay of a run that had the affordability
rules does not quietly drop them. The value is reported as
`financial_constraints` in the summary.

## Statistics

`scipy.stats.wilcoxon` is used when scipy is importable; it ships in the
`analysis` extra:

```bash
pip install 'water-agent-governance-framework[analysis]'
```

Without scipy the test is computed here — exact for small tie-free
samples, normal approximation with a tie correction above that — and the
`method` field names which ran, in the verdict as well as the JSON. What
never happens is a silent `p = 1.0`: a test that quietly becomes a no-op
reads exactly like a null result, and a reader has no way to tell the
two apart.

## Related

* `docs/AUDIT_SCHEMA.md` — the `ablation_samples.csv` column reference.
* `broker/experiments/replay.py` — snapshots, masks, the determinism gate.
* `broker/experiments/ablation.py` — the grid and the withholding rule.
* `broker/experiments/metrics.py` — JSD, KL, paired Wilcoxon.
* `examples/single_agent/flood_factor_masks.py` — four worked factors.
