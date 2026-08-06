# Rejected image-generation attempts for Figure 1

Kept as provenance, not used by the paper. Nothing in `manuscript.md` references these.

| file | what it was | why it was rejected |
|---|---|---|
| `fig0_generated.png` | first attempt, the two-bar version | **geometry wrong**: the left bar's solid share measured 57.1% where the data says 36.05%. Every printed label was correct. The picture said the two arms were nearly equal while its own numbers said they differ by 23 points. |
| `fig0_panel_a_generated.png` | second attempt, concept diagram | **causality wrong**: the red feedback arrow did not originate at governance, `blocked - try again` was attached to the wrong arrow, and the action-to-governance arrow was missing entirely. All ten strings were spelled correctly. |
| `fig0_generated_v2.png` | third attempt, after being given both reference images | Closest of the three -- arrows and text all correct. Rejected for losing the three region tints (which carry meaning: written-by-the-agent vs computed-afterwards), for leaving one box without an icon, and for being a raster, so no label can ever be corrected without regenerating the whole image. |

**The pattern worth keeping.** In every attempt the model got the *text* right and something *structural*
wrong, and in two of the three it reported all its own checks as passing. That is the failure this paper
is about: a check can pass while the thing it claims to measure is wrong. The measurement that caught
each one was made outside the tool that produced it.

The shipped Figure 1 is `../fig0_problem_schematic.*`, drawn in TikZ from the data, with a directional
guard that exits non-zero if the corpus ever contradicts what the diagram shows.
