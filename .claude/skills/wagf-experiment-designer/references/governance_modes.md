# WAGF governance modes (per domain)

Read by `examples/<domain>/run_*.py` and selected via the
`--governance-mode` CLI flag. The skill must NOT include a mode in the
matrix that is not configured in the domain's `agent_types.yaml`.

## Single-agent flood (`examples/single_agent/`)

Source: `examples/single_agent/agent_types.yaml`

| Mode | Description | When to use |
|------|-------------|-------------|
| `strict` | Full governance: PMT R1/R3/R4 + epistemic guardrails + retry. Default for paper Group_C. | Headline experiment arm |
| `disabled` | All validators OFF; agent acts on first proposal. Used for paper Group_C_disabled (no validator). | Ablation baseline |

Result-tree convention:

```
JOH_FINAL_v2/
  <model_safe>/
    Group_C/
      Run_{42..46}/

JOH_ABLATION_DISABLED_v2/
  <model_safe>/
    Group_C_disabled/
      Run_{42..46}/
```

## Irrigation (`examples/irrigation_abm/`)

Source: `examples/irrigation_abm/config/agent_types.yaml`

| Mode | Description | When to use |
|------|-------------|-------------|
| `strict` | Full governance pipeline (12 validators per Methods). | Headline (production_v21_*) |
| `disabled` | Validators OFF. Run via `run_ungoverned_experiment.py`. | Baseline (ungoverned_v21_*) |

Result-tree convention:

```
production_v21_42yr_<model_safe>_seed{42..46}/
ungoverned_v21_42yr_<model_safe>_seed{42..46}/
```

Where `<model_safe>` is omitted for the Gemma-3 4B baseline (legacy
naming) and present for cross-model variants (e.g.,
`production_v21_42yr_gemma4_e4b_seed42`).

## Multi-agent flood (`examples/multi_agent/flood/`)

Source: `examples/multi_agent/flood/config/agent_types.yaml`

| Mode | Description |
|------|-------------|
| Group_A | Default-prompt baseline (no structured prompts). |
| Group_B | Window memory (ARCHIVED — never reference). |
| Group_C | Full governance pipeline. |
| Group_C_no_ETB | Ablation: extreme-threat block disabled. |
| Group_C_disabled | All validators OFF. |

Result-tree convention:

```
JOH_FINAL/<model>/Group_<X>/Run_{1..N}/
JOH_ABLATION_DISABLED/<model>/Group_C_disabled/Run_{1..N}/
JOH_ABLATION_NO_ETB/<model>/Group_C_no_ETB/Run_{1..N}/
```

## How the skill should pick modes

The minimum useful matrix is `[strict, disabled]` per model — this
gives the headline governance-effect contrast.

For an ablation study, add:
- `Group_C_no_ETB` (flood MA only) — isolates the ETB rule's
  contribution.
- domain-specific named ablations from the YAML's
  `ablation_modes` section.

For prompt-level ablation, do NOT include in this matrix; that is a
separate experiment (and 2026-04-19 confirmed it is sensitive to
silent flag drift). Refer the user to the paper's Methods Section
"Prompt-regime sensitivity" if asked.

## How to enumerate available modes for a domain

```bash
python -c "
import yaml
cfg = yaml.safe_load(open('examples/single_agent/agent_types.yaml'))
profiles = cfg.get('global_config', {}).get('governance_profiles', {})
print(list(profiles.keys()))
"
```

If the domain config does not declare an explicit profile list, fall
back to the in-code `--governance-mode` choices in
`examples/<domain>/run_*.py` argparse setup. Refuse to use any mode not
present in either source.
