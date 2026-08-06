# Arm: `<arm-name>` — <one line: what it measures>

**Write this file BEFORE launching.** Not as bureaucracy — writing it first is what forces the
question, the stop condition and the known limitations to be stated while they can still change the
design. A record written afterwards documents what was found, which is a different and much less
useful thing.

Copy this file to `<arm-name>_<YYYY-MM>.md` in this directory, fill it in, and add a row to
[`examples/EXPERIMENTS.md`](../../EXPERIMENTS.md).

| | |
|---|---|
| **run directories** | `examples/<domain>/results/<arm>_<model>_seed<S>` — must NOT contain `_v21_42yr_` (see EXPERIMENTS.md rule 2) |
| **model** | |
| **arm** | governed / no-validator / advise / … |
| **seeds** | |
| **isolated config** | never a frozen config; copy the tree and change one key |
| **cost** | GPU-hours, measured from this corpus's own run history, not estimated from model size |
| **decision of record** | the file and line that authorised this run |
| **design record status** | written before launch · results pending |

---

## 1. The question

One paragraph. What is being measured, and what makes it uncertain enough to be worth GPU time.

If the answer is already known and this run confirms it, say so plainly — confirmation has value, but
it should be labelled, because it changes how much the result can carry.

## 2. What changes, exactly

The config diff, in full. Which keys, which files, and what stays identical. State whether frozen
baselines remain byte-identical with the flag off, and how that was verified — reading is not
verification; `python -m broker.tools.compare_audit_csv` on a mock run is.

Then: what new columns or artefacts appear, and what each holds.

## 3. The gap in this instrument

**Every instrument has one. Name it here or a reviewer will name it for you.**

What this arm cannot see, and what claims are therefore unavailable. Be specific about direction: is
the measurement a floor, a ceiling, or unbiased? A limitation with a known sign is far more useful
than a hedge.

## 4. What would falsify the current account

The outcomes, and what each one costs. If every outcome supports the existing story, this is not an
experiment — reconsider before spending the GPU time.

## 5. The stop condition

The check that runs after the FIRST seed, before the rest are launched. This is the difference
between losing one run and losing the whole queue.

State the threshold, where it is implemented, and what evidence exists about whether it will pass.
If the only prior evidence points the wrong way, say so here rather than in a footnote.

## 6. Reuse — which other papers can use this, and under what conditions

The conditions that make an arm reusable are cheap to impose before a run and impossible after:
matched model, isolated config, clean manifest, pinned arm identity.

**Also state what the arm does NOT license.** An arm that supports a within-run comparison but not a
cross-corpus one must say so, because the next reader will assume it supports both.

## 7. What reads this arm

The integrity gate, the analysis scripts, and any paper pipeline. Note any script that **refuses**
rather than returning zero when the data is absent — that refusal is a feature and should survive
future edits.

## 8. Launch

Point at the pre-flight and its checks. At minimum, for this machine:

- `ollama ps` must read **100% GPU** (2026-05-13: a driver update silently moved inference to CPU,
  12× slower, four hours lost).
- Windows Update paused ≥ 4 days (an auto-reboot killed a run at year 10).
- `--output` explicit and pointing at a NEW directory (the runner does not refuse to overwrite).
- Runs sequential, never parallel — a parallel queue makes a silent death much harder to spot.

---

## Results

*Empty until the first run completes.* Then record: the stop-condition measurement, the headline
number **with its denominator**, wall-clock per run, and **any run excluded by the gate and why**.

An excluded run is part of the record. Removing it from this file is how a corpus quietly becomes
irreproducible.
