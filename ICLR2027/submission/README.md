# ICLR 2027 submission package

This is the only active release directory for the ICLR version of the WAGF
paper. Read this file first when returning to the project.

## Start here

1. Read [`HANDOFF.md`](HANDOFF.md) for the current status and claim boundary.
2. Read [`SOURCE_OF_TRUTH.md`](SOURCE_OF_TRUTH.md) for authority and layout.
3. Open [`paper/manuscript.tex`](paper/manuscript.tex) for the anonymous paper.
4. Inspect only [`figures/active/`](figures/active/) for manuscript figures.
5. Run [`SUBMISSION_CHECKLIST.md`](SUBMISSION_CHECKLIST.md) before calling the
   package ready.

## Canonical artifact map

| Purpose | Canonical location |
| --- | --- |
| Manuscript | `paper/manuscript.tex` |
| Bibliography | `paper/references.bib` |
| Figures cited by the manuscript | `figures/active/` |
| Figure 1 generated asset | `figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png` |
| Figure and example-role audit | `PAPER_AUDIT.md` |
| Reference verification audit | `REFERENCE_AUDIT.md` |
| Figure 1 staging builder | `source/figure1_agent_paper.py` |
| Figure 1 builder entry point | `source/figure1_overlay.py` compatibility entry point |
| Figure 1 geometry check | `checks/figure1_geometry_check.py` |
| Manuscript static check | `checks/manuscript_static_check.py` |
| Machine-readable supplement | `supplement/` |

The files in `figures/candidates/` are alternatives only. They are not
submission figures and must never be referenced by `manuscript.tex`. The
active Figure 1 is the generated shared-condition composition staged from
`figures/assets/figure1_architecture_agentpaper_shared_condition_v6_retry_return.png`.

The design follows the rendered figure grammar of ReAct, Reflexion, SWE-agent,
and AgentSpec: a compact Agent response, an explicit Validator insertion point,
a direct Agent--Validator--Environment path, a subordinate retry/default-action
branch, and a lower Counted-records path with separate condition and records
inputs. It uses black borders and arrows, flat colored fills, and small
functional icons. The retry branch is shown because the primary action reading
is the executed action; the frozen corpus does not preserve the first response
before a retry.

## Figure workflow

```powershell
python ICLR2027\submission\source\figure1_overlay.py
python ICLR2027\submission\checks\figure1_geometry_check.py
python ICLR2027\submission\checks\manuscript_static_check.py
```

The first command stages Figure 1 to `figures/active/`. Figures 2--4 are
deterministic evidence outputs already stored in that same directory. Replace
the generated Figure 1 only with a new reviewed image-generation output, then
rerun the staging and checks.

## Venue boundary

The active target is ICLR 2027. AAMAS is a later fallback only after an ICLR
decision or an explicit withdrawal. The historical TAE handover is not an
instruction for this package.
