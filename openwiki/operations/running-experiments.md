# Running experiments

Every experiment in WAGF is a plain Python script under `examples/` that builds a run with `broker.core.experiment.ExperimentBuilder` and executes it — there is no central experiment CLI. All scripts are run **from the repository root** (they `sys.path.insert` the project root themselves), take `--model`, `--years`, `--agents`-style argparse flags, and write results into a directory they own. [examples/README.md](../../examples/README.md) is the canonical catalog (roles, learning path, prerequisites); this page is the operational map: which script to run, where its configs live, and what it writes.

## Examples map

Priority per [examples/README.md](../../examples/README.md): `quickstart/` is the tutorial; `single_agent/`, `irrigation_abm/`, and `multi_agent/flood/` are the primary water-sector references; the rest are demos, showcases, or coupling test-beds. (`examples/README.md` also lists a `minimal/` template dir; it does not exist in the tree — code wins, so treat that row as stale.)

### quickstart/ — tutorial, no LLM needed

Two progressive scripts using a mock LLM: `python examples/quickstart/01_barebone.py` (propose → validate → execute loop) and `02_governance.py` (invalid proposal → rejection → retry with feedback). Configs sit beside them: `agent_types.yaml` (persona + governance rules + response format) and `skill_registry.yaml` (actions + preconditions).

### single_agent/ — primary single-agent flood reference

- Entry point: `python examples/single_agent/run_flood.py --model gemma3:4b --years 10 --agents 100 --memory-engine humancentric --governance-mode strict`. Rich flag surface: `--governance-mode {strict,relaxed,disabled,strict_no_etb}`, `--memory-engine {window,importance,humancentric}`, `--flood-mode {fixed,prob}` (fixed reads `flood_years.csv`), `--seed/--memory-seed`, `--stress-test`, sampling overrides.
- Companion runners: `run_flood_extra_seeds.py`, `run_flood_rulebased.py` (rule-based baseline), plus a set of `run_*.bat`/`run_wrr_*.ps1` batch queues that loop `run_flood.py` over model × seed grids.
- Configs: `agent_types.yaml` / `agent_types_stress.yaml` / `skill_registry.yaml` at the example root; prompt template in `config/prompts/household.txt`; agent seed data in `agent_initial_profiles.csv`.
- **Write behavior (caution):** without `--output`, results go to `examples/single_agent/results/<model>_<governance-mode>/` — the same directory on every rerun of that model+mode combo, and the script **deletes the previous `raw/household_traces.jsonl` at startup** before writing new traces. Pass `--output` to a fresh directory to preserve a prior run.
- Note it imports `examples.governed_flood` at module load purely to register the `FloodDomainPack` and its builtin validators (a load-bearing side-effect import — see the file-top comment in `run_flood.py`).

### irrigation_abm/ — primary single-agent irrigation reference

- Entry point: `python examples/irrigation_abm/run_experiment.py --model gemma3:1b --years 5 --agents 5` (`--real` switches from synthetic agents to the 78-agent CRSS dataset; `--ablation-mode`, `--pilot-phase`, `--rebalance-clusters` select variants). `run_ungoverned_experiment.py` is the ungoverned baseline, `run_fql_baseline.py` a fuzzy-Q-learning baseline, `validate_smoke.py` a quick check; `run_*.bat` files are model-batch queues.
- Configs: `config/agent_types.yaml`, `config/skill_registry.yaml`, `config/prompts/`, `config/policies/` (see `config/README.md`).
- Writes to `examples/irrigation_abm/results/` by default (`--output` overrides); emits `simulation_log.csv` and `reflection_log.jsonl` into that directory, reusing it across reruns.

### multi_agent/flood/ — primary multi-agent reference

- Entry point: `python examples/multi_agent/flood/run_unified_experiment.py --model gemma3:4b`. Modes `--mode {survey,random,balanced}` choose agent sourcing; other flags toggle gossip, news/social media channels, spatial vs ring neighborhoods, PRB flood grids (`--grid-dir/--grid-years`), subsidy/premium rates, and `--mock-response-file` for LLM-free runs.
- Configs: `config/` holds `ma_agent_types.yaml` (+ influencer variants), `skill_registry.yaml` (+ variants), `agents/agent_types.yaml`, `parameters/floodabm_params.yaml`, `governance/`, `prompts/`, `information_visibility.yaml` — see `config/README.md` and `config/presets.md`.
- Default output: `examples/multi_agent/flood/results_unified/` (overwritten in place on rerun; use `--output`).
- **paper3/** is a batch wrapper, not a separate engine: `python examples/multi_agent/flood/paper3/run_paper3.py --config examples/multi_agent/flood/paper3/configs/primary_experiment.yaml --seed 42` (or `--all-seeds`, `--ablation <name>` with `configs/si_ablations.yaml`, `--dry-run` to print commands). It reads a YAML from `paper3/configs/` (`primary_experiment.yaml`, `baseline_traditional.yaml`, `si_ablations.yaml`, `calibration.yaml`, `icc_archetypes.yaml`, plus `scenarios/` and `fixed_policies/`), translates it into `run_unified_experiment.py` CLI args via subprocess, and writes per-seed dirs `paper3/results/<experiment>/seed_<N>/`. Only run mechanics belong here — do not document the study's content.

### governed_flood/ — compact teaching demo + broker test fixture

`python examples/governed_flood/run_experiment.py --model gemma3:4b --years 3 --agents 10` — full three-pillar governance pipeline (strict rules, HumanCentric memory + reflection, priority schema) in one small script. Configs in `config/agent_types.yaml`, `config/skill_registry.yaml`, `config/prompts/`. Its package `__init__.py` is also the canonical `FloodDomainPack` registration imported by `single_agent/run_flood.py` and by broker tests (`broker/tests/test_initial_loader.py`, `test_memory_content_types.py`) — do not delete or rename it when reorganizing examples.

### vaccination_demo/ — non-water showcase

`python examples/vaccination_demo/run_experiment.py --model gemma3:1b --years 3 --agents 25` — Health-Belief-Model vaccination decisions proving the framework is not flood-specific. Configs in `config/`; batch drivers `run_vaccination_batch.bat`/`.sh`; `summary.py` post-processes. Default output `examples/vaccination_demo/results/smoke/` (`--output` overrides; reused across reruns).

### reservoir_control/ and reservoir_control_multidim/ — continuous-control demos

`python examples/reservoir_control/run_reservoir_ops.py --model mock --years 4` and `python examples/reservoir_control_multidim/run_reservoir_multidim.py --model mock --years 4`. Both default to `--model mock` so they run with no LLM at all; domain packs are defined in-example (`reservoir_pack.py`, `reservoir_multidim_pack.py`) with configs in each `config/`. Outputs: `results_ops/` and `results_multidim/` inside their own dirs (audit + traces; reused on rerun).

### cat_model/ — catastrophe-model coupling test-bed

`python examples/cat_model/run_cat.py --model llama3.1:8b --years 3` (single-agent, `--model mock` works) and `run_cat_ma.py` (multi-agent, default mock) — demonstrate BMI-style coupling of an external hazard/loss model (`bmi_flood_model.py`, `coupling_modules.py`, `cat_pack.py`) into the governed loop. Outputs `results/` and `results_ma/` under `examples/cat_model/`.

`examples/_test_fixtures/` is pytest support, not runnable examples.

## Choosing an LLM backend

Backend selection is by **model-string convention**, resolved in `broker/utils/llm_utils.py: create_llm_invoke` (most example scripts call it via `create_legacy_invoke`):

- `mock` / `mock*` — deterministic no-LLM stub (picks the first numbered option); what quickstart and the reservoir/cat defaults use.
- A prefix from `{gemini, openai, azure, anthropic, claude}` before the colon (e.g. `openai:gpt-4o-mini`) routes to the cloud provider factory `providers/factory.py: create_provider`, which reads API keys from config `${ENV_VAR}` references — set `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, or `GOOGLE_API_KEY` (the gemini path reads `GOOGLE_API_KEY` — `providers/gemini.py`; `examples/README.md` still says `GEMINI_API_KEY`, which is stale).
- Anything else (`gemma3:4b`, `llama3.2:3b`, ...) is treated as a local **Ollama** tag via langchain-ollama at `http://localhost:11434` — install Ollama and `ollama pull` the tag first; the colon here is part of the Ollama tag, not a provider prefix.

Preflight check: `python -m providers.smoke [--providers ollama openai ...]` prints ready/not-ready per configured provider and exits non-zero on failure. Provider setup detail: [README.md](../../README.md) (Cloud LLM providers section) and `providers/`.

## Further reading

- [examples/README.md](../../examples/README.md) — roles, learning path, per-example docs.
- [docs/guides/experiment_design_guide.md](../../docs/guides/experiment_design_guide.md) — designing a new experiment; [docs/references/yaml_configuration_reference.md](../../docs/references/yaml_configuration_reference.md) — full YAML parameter spec.
- [ARCHITECTURE.md](../../ARCHITECTURE.md) and [broker/INVARIANTS.md](../../broker/INVARIANTS.md) — what the governance loop guarantees during a run; [DATA.md](../../DATA.md) — data provenance rules for inputs/outputs.
