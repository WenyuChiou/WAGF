# cat_model

Catastrophe-model coupling worked example (Phase 6V). A governed LLM
insurer decides whether to pay flood claims from a shared pool; the
payout is coupled through the generic `broker.coupling` adapter and
governed by `insurer_payout_solvency_check` inside the retry loop.

## Files

- `cat_pack.py` — `CatModelDomainPack` (coupling OFF by default; opt in
  via `global_config.coupling.enable`).
- `run_cat.py` — single-agent: one insurer, one hazard model.
- `run_cat_ma.py` — multi-agent: 4 policyholders + insurer + government
  sharing one pool, settled once per period (see module docstring for
  why this differs from FLOODABM's instant per-claim payment).
- `bmi_flood_model.py`/`coupling_modules.py`/`ma_modules.py` — hazard
  chain + scripted arithmetic; `cat_validators.py`/`ma_validators.py` —
  solvency checks; `config/` — agent-type + skill-registry YAML.

## Run it

```bash
python examples/cat_model/run_cat.py --model mock --years 3
python examples/cat_model/run_cat_ma.py --model mock --years 2
```
