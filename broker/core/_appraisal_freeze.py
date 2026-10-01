"""Appraisal freeze: label-conditioned rules read each label as first stated.

``global_config.governance.appraisal_freeze`` (default ``false``). When it is
true, every validation pass inside ONE decision -- the first attempt, each
governance retry, the feasible-set probe of a retry prompt, and the advisory
re-validations -- evaluates the proposal against each construct label as the
agent FIRST STATED it in that decision, never against a later restatement.
The attempt's own skill, magnitude, parameters and every non-label reasoning
field are left as they are, so only rules that read a construct label are
affected.

Why it exists: a rule conditioned on a label the model writes itself can be
passed on retry by rewriting the label, with no new information about the
world. With the freeze on, a rewritten label is still recorded in the audit
trail (``final_labels`` / ``appraisal_drift`` under
``audit.initial_proposal_columns``, ``attempt_labels`` /
``appraisal_relabeled`` under ``audit.attempt_columns``) but no rule reads
it.

"First stated", precisely: the frozen set starts as the labels of the
decision's first PARSED attempt (format retries carry no rule content), and
every later attempt that is validated adds any label it states for the
first time (a non-blank value; ``freeze_first_stated_labels``). A label,
once stated, is never replaced, so relabelling cannot pass a rule; a label
the first parsed attempt did not state is taken from the first attempt that
does, so an omitted label never becomes unrecoverable. The frozen value of a
label therefore equals its ``initial_labels`` audit value whenever the first
parsed attempt carried that label with a non-blank value; otherwise it is
the first NON-BLANK value of that label in ``attempt_labels`` (a blank is
recorded there as ``KEY=`` and is not a statement).

Construct labels are the reasoning keys containing ``_LABEL`` -- the test the
parser applies to its required labels and to label normalisation
(``UnifiedAdapter``, ``"_LABEL" in k``). The ``initial_labels`` audit column
(``_audit_helpers._extract_construct_labels``) records the keys ENDING in
``_LABEL``; the two sets are the same for every construct name that ends in
``_LABEL``, which is every shipped one. ``SkillBrokerEngine`` refuses to
start with the freeze on when a thinking rule reads a reasoning field outside
this set (it would silently escape the freeze), and when a feature that
validates proposals outside one decision's retry sequence is on (multi-skill
secondary proposals, the ExperimentRunner cognitive cache).

The frozen labels travel inside the decision's own validation context under
``FROZEN_LABELS_CONTEXT_KEY`` (set once per decision by
``SkillBrokerEngine.process_step``) and are applied in one place,
``SkillBrokerEngine._run_validators``. The engine is shared across worker
threads, so it holds no per-decision state of its own.

Default off: the key is never set, ``_run_validators`` sees the proposal it
was given, and output is byte-identical to a run without this module.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Dict, Iterable, Optional

# Private key in the per-decision validation context. The leading underscore
# keeps it clear of every agent-state / environment key the context also
# carries (both are flattened into the same dict).
FROZEN_LABELS_CONTEXT_KEY = "_frozen_construct_labels"

# The marker of a construct label key, as the parser tests it ("_LABEL" in k).
LABEL_MARKER = "_LABEL"


def is_construct_label_key(key: Any) -> bool:
    """True for a reasoning key that holds a construct label (the parser's
    own test, ``"_LABEL" in k``)."""
    return isinstance(key, str) and LABEL_MARKER in key


def construct_label_dict(proposal: Any) -> Dict[str, Any]:
    """Every construct label ``proposal`` wrote, as a new ``{key: value}``
    dict -- blank values included, since this is what the audit records.

    ``{}`` for a missing proposal or a proposal whose reasoning is not a dict
    (or carries no label).
    """
    reasoning = getattr(proposal, "reasoning", None)
    if not isinstance(reasoning, dict):
        return {}
    return {k: v for k, v in reasoning.items() if is_construct_label_key(k)}


def _is_stated(value: Any) -> bool:
    """A label counts as stated when it carries a non-blank value."""
    return value is not None and str(value).strip() != ""


def stated_construct_labels(proposal: Any) -> Dict[str, Any]:
    """The construct labels ``proposal`` actually states (non-blank)."""
    return {k: v for k, v in construct_label_dict(proposal).items() if _is_stated(v)}


def freeze_first_stated_labels(frozen: Dict[str, Any], proposal: Any) -> Dict[str, Any]:
    """Add to ``frozen``, in place, every label ``proposal`` states that is not
    frozen yet (``setdefault``: a label already frozen is never replaced).
    Returns ``frozen``."""
    for key, value in stated_construct_labels(proposal).items():
        frozen.setdefault(key, value)
    return frozen


def relabeled_after_first_statement(
    attempt_labels: Iterable[Optional[Dict[str, Any]]],
) -> bool:
    """True when some attempt states a construct label with a value other
    than the one that label was FIRST STATED with in the decision -- the value
    the freeze holds. ``attempt_labels`` holds each attempt's
    ``construct_label_dict`` in attempt order (``None`` for an attempt that
    did not parse). Stating a label for the first time is not a relabel, and
    neither is leaving one out (a blank value or a missing key); the freeze
    reads neither as a change."""
    first: Dict[str, str] = {}
    for labels in attempt_labels:
        for key, value in (labels or {}).items():
            if not _is_stated(value):
                continue
            if first.setdefault(key, str(value)) != str(value):
                return True
    return False


def frozen_label_view(proposal: Any, frozen_labels: Dict[str, Any]) -> Any:
    """A copy of ``proposal`` in which every frozen label replaces the
    attempt's own value (``{**reasoning, **frozen_labels}``).

    A label the attempt restated differently reads as first stated; a label
    the attempt omitted but an earlier attempt stated is still read; a label
    nobody has stated keeps whatever the attempt wrote (a blank, or nothing).
    Callers merge the attempt's own first statements into ``frozen_labels``
    before building the view (``freeze_first_stated_labels``). The original
    proposal object is not modified: the audit trail keeps recording what the
    model actually wrote.
    """
    reasoning = getattr(proposal, "reasoning", None)
    if not isinstance(reasoning, dict):
        # An attempt with no reasoning dict carries no label to read. With
        # nothing frozen either, the attempt is validated exactly as given;
        # otherwise the frozen labels become its only reasoning.
        if not frozen_labels:
            return proposal
        return dataclasses.replace(proposal, reasoning=dict(frozen_labels))
    return dataclasses.replace(proposal, reasoning={**reasoning, **frozen_labels})
