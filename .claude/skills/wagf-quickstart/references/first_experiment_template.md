# Phase 3 — first-experiment defaults (handed to wagf-experiment-designer)

When the user reaches Phase 3, the quickstart skill should pre-fill
sensible defaults that map to the smallest meaningful WAGF
experiment, then hand off to `wagf-experiment-designer` for the full
matrix.

The user MUST supply the research question and hypothesis; everything
else can be defaulted (and overridden).

## Default bundle per domain

### Irrigation (`irrigation_abm`)

```yaml
research_question: |
  <USER PROVIDES — do NOT auto-fill>
hypothesis: |
  <USER PROVIDES — do NOT auto-fill>
domain: irrigation
agent_count: 78        # CRSS demand-node baseline
time_horizon_years: 42 # paper convention; lower bound 10 for laptop run
models:
  - tag: gemma3:4b     # smallest model that produces sensible behaviour
    governance: [strict, disabled]
    seeds: [42, 43, 44]   # 3 seeds = smallest meaningful paired-t
metrics:
  - name: ibr
  - name: ehe
  - name: rejection_rate
  - name: retry_rate
statistical_comparisons:
  - name: governed_vs_disabled
    test: paired_t
    metric: ibr
    df_per_model: 2
llm_params:
  num_ctx: 8192
  num_predict: 4096
  thinking_mode: disabled
```

Approximate runtime on a 16 GB consumer GPU with `gemma3:4b`:
~9 hr per governed run × 3 seeds × 2 conditions = **~50-55 hr** for
the full first experiment. Smaller subsets recommended for true
laptop-only runs (drop `time_horizon_years` to 10 → ~5 hr total).

### Flood (`single_agent`)

```yaml
research_question: |
  <USER PROVIDES — do NOT auto-fill>
hypothesis: |
  <USER PROVIDES — do NOT auto-fill>
domain: flood
agent_count: 100
time_horizon_years: 10
models:
  - tag: gemma3:4b
    governance: [strict, disabled]
    seeds: [42, 43, 44]
metrics:
  - name: ibr
  - name: ehe
  - name: rejection_rate
  - name: retry_rate
statistical_comparisons:
  - name: governed_vs_disabled
    test: paired_t
    metric: ibr
    df_per_model: 2
llm_params:
  num_ctx: 8192
  num_predict: 1536
  thinking_mode: disabled
```

Approximate runtime: ~3 hr per governed run × 3 seeds × 2 conditions
= **~18-22 hr**.

## Why these defaults

- **Single model**: a cross-model matrix is intimidating for a first
  run. After completing this experiment the user can re-invoke
  `wagf-experiment-designer` to expand to N models.
- **3 seeds**: smallest n that supports a paired-t with df = 2;
  paper convention is 5 seeds and `wagf-experiment-designer` will
  prompt the user to bump to 5 before submission.
- **`gemma3:4b`**: the paper's baseline model; produces reproducible
  results and is the smallest that ships sensible WAGF behaviour.
- **`[strict, disabled]`**: the canonical governance contrast (matches
  paper EDT1 / EDT2 design). Other modes (relaxed, no_ETB) are
  domain-specific ablations; deferred to follow-up runs.

## Hand-off prompt template

```
Phase 3 ready. Defaults to fill in:

  domain:         <ask: irrigation OR flood>
  agent_count:    <auto from domain>
  models:         gemma3:4b
  conditions:     [strict, disabled]
  seeds:          [42, 43, 44]
  time_horizon:   <auto from domain>

What is your research question? Example: "Does governance reduce
the rate of high-WSA agents proposing demand increases?"

After you confirm, I will hand off to `wagf-experiment-designer`.
```

## Refusal triggers

The quickstart skill MUST refuse to advance if:

- The user does not supply a research question (even a one-sentence
  one).
- The user picks a model not on the supported list (defer to
  `wagf-experiment-designer`'s clarification flow).
- The user requests a domain not in `examples/<domain>/`.
- The user picks `seeds < 3` without explicitly saying "exploratory".

## What this template does NOT cover

- Cross-model design (let
  `wagf-experiment-designer` handle that with the user's chosen model
  list).
- Custom metric definitions (out of scope for first run; the four
  default metrics are sufficient).
- External-model coupling additions (separate skill:
  `model-coupling-contract-checker`).
