# 6. Compute IBR and EHE

The two examples use domain-specific definitions of the same summary measures.
IBR is the share of executed decisions that violate the study's counted rules.
Effective Heterogeneity Entropy (EHE) shows how evenly executed decisions spread
across the available actions. An EHE of 0 means everyone does the same thing;
the score rises as decisions spread more evenly across three irrigation actions
or four flood actions.

Score the irrigation run from [chapter 4](04-water-model.md) with the irrigation
analysis module:

```bash
python -m examples.irrigation_abm.analysis.paper_measures projection --runs .tmp/tutorial-irrigation-tier --out .tmp/tutorial-irrigation-measures-final.csv
```

Score the flood run from [chapter 1](01-first-run.md) with the separate flood
analysis module:

```bash
python -m examples.single_agent.analysis.paper_measures projection --runs .tmp/readme-flood --out .tmp/tutorial-flood-measures-final.csv
```

Read the comparable fields and the domain-specific action shares:

```bash
python -c "import csv; from pathlib import Path; paths=[Path('.tmp/tutorial-irrigation-measures-final.csv'),Path('.tmp/tutorial-flood-measures-final.csv')]; rows=[next(csv.DictReader(p.open(encoding='utf-8-sig'))) for p in paths]; print('irrigation', {k:rows[0][k] for k in ('n','ibr_pct','ehe','increase_share','keep_share','decrease_share')}); print('flood', {k:rows[1][k] for k in ('n','ibr_executed_pct','ehe','buy_insurance_share','elevate_house_share','relocate_share','do_nothing_share')})"
```

Both built-in mock runs have IBR `0.0` and EHE `-0.0`. These values need the
run context: every irrigation decision executes `maintain_demand`, and every
flood decision executes the fallback `do_nothing`, so each action distribution
has zero entropy. The mock never states the required appraisals. The analysis
therefore reports zero counted violations from the available executed-decision
evidence; it does not establish realistic, compliant behaviour. In the flood
CSV, `n_threat_never_stated=2` and `n_coping_never_stated=2` make that limitation
explicit.

The two analysis modules intentionally have different IBR scopes. Irrigation
scores its six rules; flood scores enforced R1/R3/R4/R5. Keep each output CSV
outside its input run directory so it cannot be mistaken for original run
evidence.

Return to the [tutorial index](README.md) or continue with the
[example gallery](../../examples/README.md).
