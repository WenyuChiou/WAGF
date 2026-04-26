# WAGF environment-check rubric

Phase 1 of the quickstart. Validates that the researcher's machine
can run any WAGF script at all.

## What `scripts/check_env.py` validates

| Check | Pass criterion | If fail |
|-------|----------------|---------|
| Python version | `>= 3.10` | RED — bump Python via pyenv / conda. |
| Required imports | `numpy, pandas, scipy, pyyaml, ollama` resolve | YELLOW — `pip install -r requirements.txt`. |
| Ollama daemon | `GET http://localhost:11434/api/version` returns 200 | RED on Linux/Mac — start daemon. RED on Windows — open Ollama app. |
| Recommended model | `ollama list` contains `gemma3:4b` | YELLOW — `ollama pull gemma3:4b`. |
| GPU (informational) | `nvidia-smi` returns 0 OR `mps` available OR CPU only | INFO — note expected throughput. |
| Free disk | `>= 10 GB` under repo dir | YELLOW — clean `_archive*` dirs. |

## Recommended onboarding model

`gemma3:4b` is the default for onboarding because:

- Small enough to load on a 16 GB consumer GPU (~3.5 GB VRAM).
- Large enough to produce sensible WAGF behaviour (cited as the
  baseline in the Nature Water paper).
- Available via `ollama pull gemma3:4b` (~2.4 GB download).

Other supported tags (load any one for Phase 2 to succeed; for
research use, see `wagf-experiment-designer`):

- `gemma4:e2b` — efficient 2B variant
- `gemma4:e4b` — efficient 4B variant
- `ministral-3:3b`, `ministral-3:8b`
- `gemma3:12b`, `gemma3:27b` (heavier; need 12+ GB VRAM)
- `gemma4:26b` (heaviest; needs 16+ GB VRAM)

## Per-platform install commands

### macOS / Linux

```bash
# Python
pyenv install 3.11.9 && pyenv local 3.11.9    # if needed
pip install -r requirements.txt

# Ollama
brew install ollama                             # macOS
curl -fsSL https://ollama.com/install.sh | sh   # Linux
ollama serve &                                  # start daemon
ollama pull gemma3:4b
```

### Windows

```powershell
# Python: install from python.org or via winget
winget install Python.Python.3.11
pip install -r requirements.txt

# Ollama: download installer from https://ollama.com/download/windows
# After install, the daemon runs automatically.
ollama pull gemma3:4b
```

## After remediation

Re-run `python .claude/skills/wagf-quickstart/scripts/check_env.py`.
Verdict should flip to GREEN before Phase 2 begins. The skill MUST
refuse Phase 2 if verdict is not GREEN.

## What env check does NOT validate

- LLM accuracy / quality (that's domain-specific; use Phase 2 to spot
  gross failures).
- Production paper-replication parameters (tested in `wagf-experiment-designer`).
- Reproducibility manifests (tested in `abm-reproducibility-checker`).
- Coupling contract integrity (tested in `model-coupling-contract-checker`).

This is a minimal "can the machine run anything" check, by design.
