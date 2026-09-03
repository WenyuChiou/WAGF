"""Offline experiments over a finished WAGF run — replay and ablation.

A finished run leaves a directory of traces. Every trace carries the
prompt the agent saw and the action it chose, and the agent's own
reasoning text usually names a reason: "because the toll on my usual
route went up, I took the train". That sentence is a *self-report*, and
the 2023-2025 chain-of-thought faithfulness results say a self-report is
not evidence of the mechanism — models routinely act on cues they never
mention, and mention cues they never act on.

This package is the intervention that turns the self-report into a
testable claim. Take the same recorded decision, replace the sentence
about the toll with a documented neutral rendering, re-run the same
decider at the same seed, and see whether the probability of the
reported action moves. That is a do-operator on one component of the
agent's context, with the rest of the prompt held fixed.

Four things separate that from a demo:

1. A severity-matched control. The masked arm is compared against a
   paraphrase arm that preserves the factor's information and changes
   only its wording by a similar number of characters. Without it, a
   behaviour change means "the model noticed an edit", not "the model
   used the factor".
2. Paired seeds. Every arm of every snapshot is replayed at the same
   seeds, so the comparison is within-decision.
3. Per-sample distributions. The action distribution per snapshot is
   compared with Jensen-Shannon divergence and KL, not only a flip
   count, and the across-snapshot test is a paired Wilcoxon signed-rank.
4. A determinism gate. If the same prompt at the same seed does not
   return the same output, a difference between arms cannot be
   attributed to the intervention, so no delta-P is reported at all.
   Identical replies are not enough on their own: a stopped Ollama
   server returns the same empty string every time, and the gate counts
   empty and unparsable replies so that "perfectly consistent" cannot
   mean "perfectly unreachable".

Modules
-------
``replay``   Load a recorded decision, mask a factor, re-run the decider.
``ablation`` Run the full factor x arm x seed x replicate grid.
``metrics``  JSD, KL, paired Wilcoxon, directional consistency.

Nothing here touches a live run. Loading is read-only, replay writes no
audit rows (the replay engine is built with ``audit_writer=None``), and
no module in this package is imported by the broker pipeline.
"""
from __future__ import annotations

from broker.experiments.replay import (  # noqa: F401
    ARM_BASELINE,
    ARM_CONTROL,
    ARM_MASKED,
    ARMS,
    FIDELITY_PROMPT_ONLY,
    VALIDATORS_MODULE_CONTRACT,
    DecisionSnapshot,
    DeterminismReport,
    FactorMap,
    MaskApplication,
    MaskSpec,
    ReplayDecider,
    ReplayResult,
    apply_mask,
    build_replay_decider,
    determinism_check,
    load_snapshots,
    replay_decision,
    resolve_model,
)
from broker.experiments.ablation import (  # noqa: F401
    DEFAULT_DETERMINISM_SNAPSHOTS,
    AblationDesign,
    AblationResult,
    run_ablation,
)

__all__ = [
    "ARMS",
    "ARM_BASELINE",
    "ARM_CONTROL",
    "ARM_MASKED",
    "AblationDesign",
    "AblationResult",
    "DEFAULT_DETERMINISM_SNAPSHOTS",
    "DecisionSnapshot",
    "DeterminismReport",
    "FIDELITY_PROMPT_ONLY",
    "FactorMap",
    "MaskApplication",
    "MaskSpec",
    "ReplayDecider",
    "ReplayResult",
    "VALIDATORS_MODULE_CONTRACT",
    "apply_mask",
    "build_replay_decider",
    "determinism_check",
    "load_snapshots",
    "replay_decision",
    "resolve_model",
    "run_ablation",
]
