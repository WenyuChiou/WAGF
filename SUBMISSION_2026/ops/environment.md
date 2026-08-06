# Environment reconnaissance — 2026-07-29

Checked before planning the campaign, so the run matrix is built against what actually exists
rather than what the corpus happens to mention.

## Models: all 9 corpus configurations are installed and invocable

Verified two ways — `ollama list`, and the `model` field of every
`reproducibility_manifest.json` in the shipped corpus. The strings below are the **exact**
invocation strings; use them verbatim.

| model string | runs in shipped corpus | installed |
|---|---:|---|
| `gemma3:4b` | 23 | ✅ |
| `gemma4:e2b` | 20 | ✅ |
| `gemma4:e4b` | 20 | ✅ |
| `gemma3:12b` | 19 | ✅ |
| `ministral-3:8b` | 18 | ✅ |
| `ministral-3:3b` | 14 | ✅ |
| `gemma3:27b` | 13 | ✅ |
| `ministral-3:14b` | 13 | ✅ |
| `gemma4:26b` | 10 | ✅ |

**Naming trap, worth pinning:** the model tag is `ministral-3:8b` (hyphen) while the results
directories are named `ministral3_8b` (no hyphen, underscore). A script that derives one from the
other by naive string munging will silently look in the wrong place — a first pass of this recon
reported all three Ministral models "missing" for exactly that reason. Always take the model string
from the manifest, never from the directory name.

Also present and potentially useful as an extra capability tier, none of which appear in the corpus:
`gemma4:12b`, `mistral-small:24b`, `qwen3:8b`, `qwen3.5:4b`, `llama3.1:8b`, `olmo2:7b`,
`granite4.1:3b`, `phi4-mini`, `glm-4.7-flash`, plus a `kimi-k2.6:cloud` endpoint.
**A third model family would materially weaken the "two open-weight families" objection** — Qwen and
Llama are both present at small sizes and cost roughly the same as the existing small models.

## Hardware / capacity

- GPU: RTX 4080 SUPER, **now completely free** — the campaign is calendar-bound, not hardware-bound.
- Disk: **2.4 TB free of 3.7 TB (34% used)**. The existing corpus is 347 runs / 432,083 decisions;
  new runs are not a storage constraint at any plausible matrix size.

## Measured run costs (per 1,000 decisions, disabled arm)

`gemma3:4b` 1.1 h · `ministral-3:3b` 1.0 h · `ministral-3:8b` 1.9 h · `gemma3:12b` 1.9 h ·
`ministral-3:14b` 2.4 h · `gemma3:27b` 10.6 h

Arm multipliers: no-rules 1.0× · resample 1.0× · placebo/advise ~1.15× · enforce ~1.4×.
Testbed sizes: flood 100 agents × 10 yr = **1,000 decisions/run**;
irrigation 78 agents × 42 yr = **3,276 decisions/run** (3.28× flood).

`gemma3:27b` is ~10× the small models. Every hour spent on it is ~10 small-model runs not done —
treat its inclusion as an explicit trade, not a default.

## Operational hazards with recorded incidents

1. **Windows Update auto-reboot** killed a run at year 10 (~6h47m lost). Pause updates for the
   campaign window before starting the queue.
2. **Silent CPU fallback** — an Ollama/driver combination fell back to 100% CPU for four hours
   (~12× slower) *without erroring*. Detection must be throughput-based, not exception-based.
3. **Silent-death runs** — the corpus contains runs that exited 0 with empty or truncated output.
   A post-run integrity assertion is required before any run enters the analysis.
4. **Isolated config does NOT imply isolated output.** `--config-root` / `--config-dir` isolate what
   a run *reads*; the output directory still defaults to `results/<model>_<governance_mode>/`. A new
   arm sharing a model and governance mode with a frozen run will therefore write **into the frozen
   run's results folder** unless `--output` is passed. Pre-existing behaviour, not introduced by the
   isolation flags, and it would happen with or without them — which is exactly why it is easy to
   miss once the config side *feels* handled. **The queue must pass `--output` explicitly for every
   arm and refuse to start if the target directory already exists.**

## Config isolation (shipped 2026-07-30, commit `10e190cf`)

New arms never edit the frozen paper configs:

```
python examples/single_agent/run_flood.py        --config-root <DIR> --output <DIR>
python examples/irrigation_abm/run_experiment.py --config-dir  <DIR> --output <DIR>
```

An isolated tree must be a **complete** copy, not an overlay. Flood's root resolves data as well as
config — `agent_types.yaml`, `skill_registry.yaml`, `agent_initial_profiles.csv`, `flood_years.csv`,
plus the prompt template named by `household.prompt_template_file` (today `config/prompts/household.txt`).
Irrigation needs `agent_types.yaml`, `skill_registry.yaml`, `prompts/irrigation_farmer.txt`. Both
runners pre-flight this and exit naming the missing files, so a partial copy fails immediately rather
than part-way through setup.

Survey-mode's xlsx is deliberately **not** isolated — it is shared read-only input data and stays
anchored to `examples/`.

Default behaviour is unchanged and proven so: mock flood run vs pre-change HEAD is `IDENTICAL`,
canonical `sha256=034b41176d4b6cf01f06f6feb5eb97d2086dcf682182fee2eb6ad6907d7b889c`.

## Provenance requirement for every new run

Not one of the 347 existing runs has clean provenance: every manifest that records a commit records
`git_dirty=true`, and 94 of 171 record no commit at all. The campaign must run from a **tagged,
clean tree**, and the queue should refuse to start otherwise. This is cheap to enforce and is the
single easiest reviewer objection to remove.
