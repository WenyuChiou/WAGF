# Which data belongs to which paper

Written 2026-08-05. **Every row was resolved by asking the analysis code, not by reading a
directory name.** The irrigation and flood run sets were enumerated by importing
`SUBMISSION_2026/TAE/evidence/_data.py` and calling its own discovery functions; the Nature Water
side was resolved by grepping the corpus names its analysis scripts actually reference.

> **This file covers the corpora that already existed on 2026-08-05.** Everything produced from that
> date onward carries its own design record written *before* the run, and is indexed in
> [`examples/EXPERIMENTS.md`](examples/EXPERIMENTS.md) — which is where you should start if you are
> planning a new arm or writing a paper against a recent one. This file remains the authority on the
> older corpora, whose intent had to be reconstructed rather than recorded.

Re-derive this rather than trusting it:

```
python - <<'EOF'
import sys, os; sys.path.insert(0, "SUBMISSION_2026/TAE/evidence")
import _data as D
for m in D.IRRIGATION_MODELS:
    for arm in ("gov","noval"): print(arm, m.label, len(D.irrigation_runs(arm, m.prefix)))
for m in D.FLOOD_MODELS:
    for arm in ("gov","noval"): print(arm, m.label, len(D.flood_runs(arm, m.label)))
EOF
```

---

## The short version

`examples/` is **9.1 GB** and holds six results roots. Two of them carry both papers, one carries a
third paper, one is quarantined evidence, and three are inert.

| root | size | owner |
|---|---|---|
| `examples/irrigation_abm/results` | — | **TAE/ICLR paper**, 42 run dirs, all live |
| `examples/single_agent/results` | 1.6 G | **Nature Water and the TAE/ICLR paper share this** |
| `examples/multi_agent/flood/results` | 177 M | **Paper 3** (multi-agent flood) |
| `examples/governed_flood/results` | 1.6 M | inert |
| `examples/quickstart/results` | 43 K | inert |
| `examples/cat_model/results` | 35 K | inert |

**Nothing here should be deleted.** The reasons are given below, per item.

---

## 1. Irrigation — the conference paper's identification data

`examples/irrigation_abm/results`, 43 entries. **42 are live and 1 is an orphan of a different
analysis.**

Five model cells, two arms each, resolved by the allow-list in `_data.py` — a directory is reachable
only by being named there, never by globbing:

| cell | governed seeds | no-validator seeds |
|---|---|---|
| `gemma3:4b` (anchor) | 42–46 | 42–46 |
| `gemma3:12b` | 42, 43, 44 | 42, 43, 44 |
| `gemma4:e2b` | 42–46 | 42–46 |
| `gemma4:e4b` | 42–46 | 42–46 |
| `ministral3:8b` | 42, 43, 44 | 42, 43, 44 |

All balanced. Every run is 3,276 decisions (78 agents × 42 years).

**`fql_raw/` (seeds 42–44) is not part of this.** It belongs to the FQL baseline comparison, read by
`examples/irrigation_abm/analysis/fql_comparison_figure.py` and `fql_comparison_metrics.py` and
produced by `run_fql_baseline.py`. It is live for that analysis and invisible to the TAE pipeline.
Not an orphan — a different tenant.

## 2. Flood — shared by two papers, and this is the one to be careful with

`examples/single_agent/results`, 1.6 GB. **Four of its six subdirectories are read by both the
Nature Water paper and the conference paper.**

| directory | size | TAE resolves it | NW analysis names it |
|---|---|---|---|
| `JOH_FINAL` | 437 M | yes | 17 references |
| `JOH_ABLATION_DISABLED` | 431 M | yes | 12 references |
| `JOH_FINAL_v2` | 226 M | yes | 9 references |
| `JOH_ABLATION_DISABLED_v2` | 222 M | yes | 7 references |
| `rulebased` | 1.1 M | **no** | 13 references — **NW only** |
| `_QUARANTINE_reflection_missing_2026-05-30` | 226 M | no | no |

**Implication for any future cleanup: this directory has two owners.** A change made for the
conference paper can silently break the NW paper's numbers, and the NW paper is the one going to a
journal, where the reproducibility bar is higher. Treat it as read-only for both.

### The quarantine is evidence, not clutter

`_QUARANTINE_reflection_missing_2026-05-30/` is 226 MB that neither paper reads, which makes it look
like the obvious thing to delete. **It is not.**

`_DATA_DEFECTS_2026-05-30.md`, in the same directory, records why:

> "No-validator flood Run_1/2/3 (seeds 42/43/44) for 6 models **lack reflection** while all governed
> runs have it."

That is a confound that was caught, measured, and quarantined rather than silently pooled. The
quarantine is the record that it was caught. Deleting it destroys the evidence that the defect was
handled, in a project whose entire argument is about defects that pass unnoticed.

**Keep it. It costs 226 MB and it is the audit trail.**

## 3. Multi-agent flood — Paper 3, a third tenant

`examples/multi_agent/flood/results`, 177 MB, referenced by 14 analysis files under
`examples/multi_agent/flood/paper3/`. Nothing in the TAE/ICLR pipeline or the Nature Water analysis
touches it. It is neither orphaned nor shared — it belongs to a paper that is not in play right now.

## 4. The three inert roots

`governed_flood/results` (1.6 M), `quickstart/results` (43 K), `cat_model/results` (35 K). No
analysis file in either paper references them. Together they are **1.7 MB** — below the threshold at
which tidying them is worth the risk of being wrong about what reads them.

`quickstart/results` in particular is the output of the onboarding smoke test and is expected to be
regenerated by anyone following `wagf-quickstart`.

---

## 5. What "messy" actually was

Not disk. **9.1 GB across six roots, of which 226 MB is deliberately quarantined evidence and
1.7 MB is inert.** There is almost nothing to reclaim and nothing that should be reclaimed.

The real problem was that **no file said which corpus belonged to which paper**, so every question
about the data required re-deriving the answer from the code. That is what this document fixes.

## 6. Rules that follow from the above

1. **`examples/` is read-only for analysis work.** Both papers depend on it. The TAE evidence
   pipeline enforces this on its own side through an allow-list rather than globbing.
2. **New experiment arms write to a new root**, never into a frozen one. `10e190cf` on
   `p0-1-governance-instrumentation` adds isolated config roots for exactly this.
3. **Anything touching `single_agent/results` affects two papers.** Check the Nature Water analysis
   before assuming a change is local.
4. **Do not delete a quarantine.** It is the record that a defect was found.
5. When a new arm lands, add a row here rather than leaving the next reader to re-derive it.
