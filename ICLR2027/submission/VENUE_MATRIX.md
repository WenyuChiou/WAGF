# Venue decision matrix

Last official-source check: 2026-08-08.

## Active decision

**Primary target: ICLR 2027.** The paper is framed as an AI-agent evaluation and
measurement-validity contribution, with runtime governance as the mechanism and
WAGF as the empirical setting.

**Fallback: AAMAS 2027, only after the ICLR decision or an explicit withdrawal.**
Do not submit substantially similar versions to both venues at the same time.

TAE is historical in this repository and is not the active target because its
schedule conflicts with the author's AGU commitment. The existing
`SUBMISSION_2026\TAE` package is preserved as a snapshot and is not overwritten
by this ICLR package.

The current official ICLR 2027 author guidance places the abstract deadline
on 18 September 2026 AoE and the full-paper deadline on 25 September 2026 AoE.
The author's AGU26 commitment is 7--11 December 2026, so these dates do not
conflict. TAE remains closed as an operational target because of the prior
commitment decision, not because the historical package is deleted.
The Call for Papers and Author Guidelines now agree on these dates; recheck the
live Author Guidelines at submission time for any later revision.

## Comparison

| Venue | Fit | Current requirements / dates | Decision |
| --- | --- | --- | --- |
| [ICLR 2027](https://iclr.cc/Conferences/2027/AuthorGuidelines) | Strong fit for agent evaluation, safety, benchmarks, infrastructure, and hybrid AI | Abstract Sep 18 2026 AoE; paper Sep 25 2026 AoE; main text <=9 pages, references excluded; double blind; required AI-use statement | Primary |
| [AAMAS 2027](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/) | Strong multi-agent fit, especially agent governance and simulation | Abstract Oct 1 2026; paper Oct 8 2026; 8-page main paper; mandatory LaTeX; double blind | Later fallback |
| TAE / NeurIPS workshop | Thematic fit, but schedule conflict and no longer the operational target | Historical package only | Do not target now |

## Important policy difference

ICLR requires an AI-use statement and recommends ethics and reproducibility
statements. The manuscript includes all three. AAMAS's current instructions
also impose a stricter restriction on AI-generated images: an image is allowed
only when generative AI is the topic or the image is qualitative evidence. If
AAMAS becomes the target, re-check that policy before submission. The active
ICLR Figure 1 is a reviewed generated full composition; it should not be
silently reused for another venue without that policy check. Earlier vector and
generated intermediates remain outside the active figure path.

## Current paper-shape decision

The ICLR package uses one conceptual figure, three irrigation-led quantitative
figures, and three tables. Flood appears in one secondary boundary-check table.
This is a paper-design choice rather than a venue quota: it keeps the visual
and quantitative emphasis on the coupled feedback loop that motivates the
paper's measurement claim. AAMAS remains a later fallback, and its current
image-generation policy must be rechecked before any venue switch.

## Official sources

- [ICLR 2027 Author Guidelines](https://iclr.cc/Conferences/2027/AuthorGuidelines)
- [AGU Annual Meeting](https://www.agu.org/annual-meeting)
- [AAMAS 2027 Calls](https://warwick.ac.uk/fac/sci/dcs/aamas2027/calls/)
