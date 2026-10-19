# 5. Resume from an irrigation journal

The irrigation runner can record every model call and replay completed years
after a crash. First make a normal two-year journal with the same small mock run
used by the repository quickstart:

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --agents 2 --workers 1 --seed 42 --governance-mode strict --coupling --llm-journal --output .tmp/tutorial-irrigation-resume-source
```

For a deterministic tutorial fixture, copy the journal only through the first
`step_end` record. This represents a process that stopped immediately after
year 1. It leaves the completed source journal unchanged:

```bash
python -c "from pathlib import Path; import json; src=Path('.tmp/tutorial-irrigation-resume-source/llm_journal.jsonl'); dst=Path('.tmp/tutorial-irrigation-resume-checkpoint/llm_journal.jsonl'); dst.parent.mkdir(parents=True,exist_ok=True); lines=src.read_text(encoding='utf-8').splitlines(); end=next(i for i,s in enumerate(lines) if json.loads(s).get('type')=='step_end' and json.loads(s).get('step')==1); dst.write_text('\n'.join(lines[:end+1])+'\n',encoding='utf-8'); print(f'copied {end+1} records through step_end 1 to {dst}')"
```

Resume into a new output directory. Keep all prompt-affecting options identical:

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --agents 2 --workers 1 --seed 42 --governance-mode strict --coupling --output .tmp/tutorial-irrigation-resume-result --resume-from .tmp/tutorial-irrigation-resume-checkpoint/llm_journal.jsonl
```

The resume replays year 1 from the 16 recorded calls and runs year 2 normally.
Confirm the provenance written to the new run:

```bash
python -c "import json; from pathlib import Path; m=json.loads(Path('.tmp/tutorial-irrigation-resume-result/reproducibility_manifest.json').read_text()); print({k:m[k] for k in ('resumed_from','source_journal_sha256','source_workers','replayed_steps','replayed_calls')})"
```

`replayed_steps` is `1` and `replayed_calls` is `16`. The source path and its
SHA-256 make the replay auditable. The runner also compares the journal header
with the current model, seed, governance settings, configuration hashes, and
source diff. A mismatch is refused rather than silently mixed into the run, so
keep the entire tracked worktree unchanged between the first and third commands;
even an unrelated tracked documentation edit changes the source-diff identity.

Next: [compute IBR and EHE](06-measures.md).
