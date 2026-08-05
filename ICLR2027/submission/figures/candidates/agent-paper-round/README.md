# Agent-paper Figure 1 candidate round

These candidates were generated after comparing the rendered figures in
ReAct, Reflexion, AutoGen, and AgentSpec. This is a historical candidate round
only; none of the files below is active and none is a regeneration source for
the current compact v1 figure.

- `figure1_candidate_A_loop.png`: rejected; the `rule input` label was placed
  on the wrong downstream arrow and the condition-to-Validator relation was
  not explicit.
- `figure1_candidate_B_dual_use.png`: semantic baseline; correct two-use
  condition routing.
- `figure1_candidate_C_nested.png`: rejected; nested boundaries made the
  measurement lane visually heavier than the execution path.
- `figure1_candidate_D_refined.png`: selected; B was regenerated with a small
  LLM chip, a water-reservoir environment cue, and a neutral-gray background.
- `figure1_candidate_E_emits.png`: selected replacement for D; it adds one
  short `emits` arrow so the Agent-to-response relation is explicit while
  preserving D's routes, labels, icons, and compact background.
- `figure1_candidate_F_accepted_decision.png`: selected replacement for E;
  it changes only the Validator-to-Decision-log label to `accepted decision`
  so the log cannot be read as containing rejected decisions.

The historical F image was copied to
`figures/assets/figure1_generated_full_final.png` and staged by an earlier
builder. All labels, arrows, and icons remain part of the generated raster,
but the D-v3 source is now historical. The active source is
`figures/assets/figure1_architecture_compact_v1.png`, documented in the
submission-level reset contract.
