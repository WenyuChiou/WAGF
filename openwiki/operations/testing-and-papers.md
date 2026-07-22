# Testing and paper tooling

Short pointer page: how to run the test suite, what CI runs, and where the paper/analysis orchestration scripts live. Conventions (commit prefixes, PR flow, when to run which tests) are in [CONTRIBUTING.md](../../CONTRIBUTING.md); per-file test descriptions are in [tests/README.md](../../tests/README.md).

## Running the test suite

Pytest is configured in [pyproject.toml](../../pyproject.toml) (`[tool.pytest.ini_options]`): `testpaths = ["tests"]`, `--strict-markers --tb=short -q`, and four registered markers — `slow`, `integration`, `unit`, `benchmark` (`-m "not slow"` deselects slow tests; unregistered markers fail under `--strict-markers`). Install with `pip install -e .[dev]` (pytest is the only dev dependency).

Layout under `tests/`:

- `tests/*.py` — the bulk of the suite (~110 flat `test_*.py` files): broker core, adapter parsing, governance/audit components, config schemas, domain genericity, and more. See [tests/README.md](../../tests/README.md) for the category map.
- `tests/core/` — fast framework-core tests (cognitive cache, experiment runner); this is the subset CONTRIBUTING recommends before committing: `pytest tests/core/ -v --tb=short`.
- `tests/sdk/`, `tests/integration/` — SDK and end-to-end tests; anything matching `real_llm` needs a live Ollama and is excluded in CI via `-k "not real_llm"`.
- `tests/flood/` — flood-domain tests (memory scorer, social network, FloodABM alignment).
- `tests/manual/` — scripts run by hand, not collected in CI.
- `tests/conftest.py`, `tests/fixtures/` — shared fixtures.

## CI

[.github/workflows/test.yml](../../.github/workflows/test.yml) runs on push to `main` and `refactor/**` and on PRs to `main`, across a Python 3.10/3.11/3.12 matrix on `ubuntu-latest`. It installs `requirements.txt` plus `-e .[dev,web]`, then runs three steps: `tests/core/` (must pass), then `tests/sdk/` (ignoring `tests/sdk/test_domain_packs.py`) and `tests/integration/`, both with `-k "not real_llm"` and with pytest exit code 5 (no tests collected) tolerated. Note the flat `tests/*.py` files are NOT run by CI — run them locally.

## Paper / analysis tooling (pointers only)

Experiment and analysis orchestration lives inside `examples/` next to the domain it serves (see [examples/README.md](../../examples/README.md) for the example map). One line each — no manuscript content is documented here:

- `examples/single_agent/run_flood.py` (+ `run_flood_extra_seeds.py`, `run_flood_rulebased.py`, and the `run_*.bat`/`.ps1` batch queues) — single-agent flood-adaptation experiment runner and its per-model/per-seed rerun wrappers; post-run analysis scripts in `examples/single_agent/analysis/`.
- `examples/governed_flood/run_experiment.py` — standalone governed flood example exercising the full governance pipeline (governance rules + cognitive memory + priority schema).
- `examples/irrigation_abm/run_experiment.py` — irrigation ABM runner; multi-seed ensemble figures and comparisons in `examples/irrigation_abm/analysis/`.
- `examples/vaccination_demo/run_experiment.py` — vaccination-domain demo runner (cross-domain genericity example).
- `examples/multi_agent/flood/run_unified_experiment.py` — the unified multi-agent flood runner; `examples/multi_agent/flood/paper3/run_paper3.py` wraps it, translating YAML configs (`paper3/configs/`) into CLI arguments for single-seed, all-seeds, or ablation runs. Analysis and figure scripts sit in `paper3/analysis/` and `paper3/figures/scripts/`.

`pip install -e .[analysis]` pulls the plotting/stats stack (matplotlib, seaborn, scipy, openpyxl) these analysis scripts need; the packaged distribution itself excludes `examples/`, `tests/`, and paper material (`[tool.setuptools.packages.find]` includes only `broker*` and `providers*`).
