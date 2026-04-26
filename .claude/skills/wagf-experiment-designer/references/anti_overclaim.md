# Anti-overclaim and clarification patterns

Use these patterns to keep the experiment matrix honest and the
research question testable.

## Refusal triggers

Refuse to add the row to the matrix and ask for clarification when:

| Trigger | Response template |
|---------|-------------------|
| User says "all available models" | "Please list specific Ollama tags. I will not enumerate `ollama list` and decide for you. Pasting that list back to me is the cleanest path." |
| User says "default seeds" | "Confirm seeds. Paper convention is 42–46 (n=5). Smaller seed budgets weaken paired-t inference." |
| User asks for a metric not in `metrics_catalog.md` | "I cannot include `<metric>` because it has no canonical implementation in the catalogue. Either choose an existing metric, or implement the formula in `examples/<domain>/analysis/` first and update `metrics_catalog.md`." |
| User asks to compare flood and irrigation in the same matrix | "These are separate domains with different action vocabularies and time horizons. I will produce two matrices and a separate cross-domain comparison plan." |
| User says "just figure out the right design" | "I will not auto-design without your inputs. Please answer: question, hypothesis, domain, models, conditions, seeds, horizon, agent count, metrics." |
| Time horizon is shorter than the domain default | "Reduced horizon weakens long-run dynamics (irrigation drought tier accumulation, flood event spacing). Confirm this is intentional." |
| Seed budget < 3 | "Paired-t at n<3 is unreliable. Confirm this is exploratory and the matrix will be re-run at n=5 before publication." |

## Hypothesis-shaping patterns

When the user supplies only a research question, the skill should
propose a directional hypothesis and ask for confirmation, NOT lock it
in silently. Pattern:

> Your research question is `<Q>`. A directional hypothesis I would
> assume is `<H>`. Should I lock this in, or would you like to
> rephrase the expected effect direction?

## Acceptance-criterion fishing

If the user's research question allows multiple effect signs, name
them and ask:

> "Does governance reduce IBR" admits three outcomes: significant
> reduction, no effect, or significant increase (governance hurts).
> Which of these would constitute confirmation, refutation, and
> surprise? I will encode each as an acceptance criterion in
> `metrics_plan.md`.

## Power-vs-effort negotiation

If the user wants more conditions than seed budget supports:

> 5 models × 4 conditions × 5 seeds = 100 runs. At ~9 hr/run for
> Gemma-3 4B that is ~37 days wall-clock single-stream. Suggest
> reducing to 3 conditions or 3 seeds to cut to ~22 days. Which
> trade-off should I bake into the matrix?

## Pre-registration nudge

After the matrix is written, prompt the user:

> The matrix is ready. Before running, recommend logging the matrix
> hash (`sha256` of `wagf_experiment_matrix.yml`) in your lab notebook
> as a soft pre-registration. Re-runs that produce a different matrix
> hash should be treated as a separate experiment rather than a
> repeated trial.

## Caveats section in the design doc

`metrics_plan.md` MUST include a Caveats section listing:

- Effect-size threshold (what magnitude counts as "real").
- Multiple-comparisons risk (number of paired-t tests; Bonferroni or
  not).
- Data-pooling boundary (no mixing of code commits without flagging).
- Reproducibility prerequisite (run via the standard bat with
  manifest writes ON; otherwise `abm-reproducibility-checker` will
  flag at submission time).

If any of these is unclear, the skill must ask, not guess.
