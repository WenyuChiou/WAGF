"""P0-1c: the single-shot advisory pass.

Straight-line by construction: NO loop, NO recursion, NO except-and-reprompt. When
at least one validation result has been demoted to ``disposition == "ADVISE"``, this
issues EXACTLY ONE additional ``llm_invoke`` and adopts whatever comes back --
even if it still violates the advised rule, even if it is worse. Advice never
blocks; that is the entire semantic difference from enforcement.

WHY EXACTLY ONE CALL. The decomposition
``total = (A'-A) sampling + (B'-A') generic pressure + (B-B') rule content + (C-B) enforcement``
is only identified if the advise arm (B) and the placebo arm (B') are matched
call-for-call, differing solely in whether the prompt carries rule content. A loop
here would silently reintroduce the sampling term into (C-B).

WHY IT RUNS BEFORE THE GOVERNANCE RETRY LOOP. Placing it after the P0-1a snapshot
and before ``_governance_retry_loop`` means arm B's advisory prompt is built from
the SAME attempt-0 proposal and the SAME report objects that arm C's FIRST retry is
built from, so (C-B) compares like with like. The retry loop still runs afterwards
on the post-advisory proposal, so the Tier-0 floor (response format, affordability,
action membership) is fully preserved -- an advised decision that hallucinates a
skill name is still caught and still cannot execute.

The one-call guarantee is therefore scoped to THIS MECHANISM, not to the decision:
if the post-advisory proposal trips Tier-0, the governance loop fires and that
decision costs more than one extra call. That is deliberate; suppressing the floor
to keep a call budget would let unaffordable or hallucinated actions mutate world
state in one arm only.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from ..interfaces.skill_types import SkillProposal
from ..utils.logging import logger
from ._advise import build_intervention_reports, render_intervention_prompt


def _blank_info() -> Dict[str, Any]:
    """All advisory audit fields, defaulted for the not-fired case."""
    return {
        "advise_mode": "off",
        "advisory_fired": False,
        "advisory_llm_calls": 0,
        "advisory_rules": "",
        "advisory_skill_before": "",
        "advisory_skill_after": "",
        "advisory_changed_action": False,
        "advisory_parse_failed": False,
        "advisory_reports_shown": 0,
        "advisory_prompt_chars": 0,
        "post_advice_rules": "",
    }


class AdviseMixin:
    """Provides :meth:`_advisory_pass`. Mixed into SkillBrokerEngine."""

    def _advisory_pass(
        self, *, all_valid: bool, skill_proposal, validation_results: List,
        all_validation_history: List, validation_context: Dict,
        prompt: str, llm_invoke, context: Dict,
        agent_id: str, agent_type: str, env_context: Optional[Dict],
        raw_output: str, total_llm_stats: Dict,
        attempt_skills: Optional[List] = None,
    ):
        """Issue at most ONE advisory re-ask. Never blocks.

        Returns ``(skill_proposal, raw_output, validation_results, all_valid, info)``.
        ``info`` is the audit payload; it is surfaced only when the
        ``audit.advise_columns`` flag is on.
        """
        info = _blank_info()
        mode = getattr(self, "_advise_mode", "off")
        info["advise_mode"] = mode

        advised = [
            v for v in validation_results
            if (getattr(v, "metadata", None) or {}).get("disposition") == "ADVISE"
        ]
        if mode == "off" or not advised or skill_proposal is None:
            return skill_proposal, raw_output, validation_results, all_valid, info

        info["advisory_fired"] = True
        info["advisory_skill_before"] = skill_proposal.skill_name or ""
        info["advisory_rules"] = "|".join(sorted({
            ((getattr(v, "metadata", None) or {}).get("rules_hit") or ["unknown_rule"])[0]
            for v in advised
        }))

        # --- Build the arm-specific prompt -------------------------------------
        framing = getattr(self, "_intervention_framing", "legacy")
        spec = getattr(self, "_advise_spec", None) or {}

        if mode == "resample":
            # Arm A': re-sample on the ORIGINAL prompt. Zero added text -- isolates
            # the effect of drawing again from the same distribution.
            advisory_prompt, reports_shown = prompt, 0
        elif mode == "wrapper":
            # Arm A'': wrapper scaffolding only, no rules block.
            advisory_prompt, reports_shown = render_intervention_prompt(
                self.model_adapter, prompt, [], framing=framing, include_reports=False,
            )
        else:
            reports = build_intervention_reports(
                advised, skill_proposal, source="advisories", severity="RULE",
            )
            if mode == "placebo":
                # Arm B': same report COUNT, same shape, rule content stripped.
                placebo_text = spec.get(
                    "placebo_text", "A governance rule was triggered by this decision.")
                for r in reports:
                    r.violation_summary = placebo_text
                    r.suggested_correction = None
            advisory_prompt, reports_shown = render_intervention_prompt(
                self.model_adapter, prompt, reports,
                max_reports=self.max_reports, framing=framing,
            )
        info["advisory_reports_shown"] = reports_shown
        info["advisory_prompt_chars"] = len(advisory_prompt)

        # --- THE single call ----------------------------------------------------
        # Guarded, but deliberately NOT retried: a transient failure must not become
        # a second call, or the advise arm silently stops being call-matched to the
        # placebo arm and (C-B) reabsorbs the sampling term. On failure we keep
        # attempt 0 and record the fact, so the decision is still analysable and
        # can be filtered out of the matched contrast.
        info["advisory_llm_calls"] = 1
        if "llm_calls" in total_llm_stats:
            total_llm_stats["llm_calls"] += 1
        try:
            res = llm_invoke(advisory_prompt)
        except Exception as exc:
            info["advisory_parse_failed"] = True
            info["advisory_skill_after"] = info["advisory_skill_before"]
            if attempt_skills is not None:
                attempt_skills.append(None)
            logger.warning(
                f"[Governance:Advisory] Advisory call raised for {agent_id}: {exc!r}. "
                "Keeping the pre-advisory proposal; NOT retrying (one-call guarantee)."
            )
            return skill_proposal, raw_output, validation_results, all_valid, info

        if isinstance(res, tuple):
            new_raw, stats_obj = res
            total_llm_stats["llm_retries"] += getattr(stats_obj, "retries", 0)
            # Aggregate exactly as _invoke_llm_with_retries and the governance retry
            # loop do -- token totals accumulate, context fields take the running MAX.
            # The advisory prompt is by construction the LONGEST in the decision (it
            # appends header + rule text), so excluding it would under-report peak
            # context pressure on precisely the decisions where advice fired.
            if getattr(stats_obj, "prompt_tokens", 0) > 0:
                total_llm_stats["prompt_tokens"] = (
                    total_llm_stats.get("prompt_tokens", 0) + stats_obj.prompt_tokens)
                total_llm_stats["response_tokens"] = (
                    total_llm_stats.get("response_tokens", 0) + stats_obj.response_tokens)
                total_llm_stats["num_ctx"] = getattr(stats_obj, "num_ctx", total_llm_stats.get("num_ctx"))
                total_llm_stats["context_utilization"] = max(
                    total_llm_stats.get("context_utilization", 0.0),
                    round(getattr(stats_obj, "context_utilization", 0.0) or 0.0, 4),
                )
            # A failed advisory call must not be masked by attempt 0's success flag.
            if not getattr(stats_obj, "success", True):
                total_llm_stats["llm_success"] = False
        else:
            new_raw = res

        if isinstance(new_raw, SkillProposal):
            new_proposal = new_raw
        else:
            new_proposal = self.model_adapter.parse_output(new_raw, {
                **context,
                "agent_id": agent_id,
                "agent_type": agent_type,
                "retry_attempt": 0,
                "advisory": True,
                "current_year": env_context.get("current_year") if env_context else "?",
            })

        if attempt_skills is not None:
            attempt_skills.append(new_proposal.skill_name if new_proposal else None)

        if not new_proposal:
            # Unparsable advisory output: KEEP attempt 0 and do NOT re-ask -- a
            # second call here would break the one-call guarantee and silently
            # unbalance arm B against arm B'.
            info["advisory_parse_failed"] = True
            info["advisory_skill_after"] = info["advisory_skill_before"]
            logger.warning(
                f"[Governance:Advisory] Unparsable advisory output for {agent_id}; "
                "keeping the pre-advisory proposal (no second call by design)."
            )
            return skill_proposal, raw_output, validation_results, all_valid, info

        # --- Adopt, then re-validate for the audit trail ------------------------
        # Re-validation records what the post-advisory proposal WOULD have tripped;
        # because the advised rules are still demoted at _run_validators' return,
        # they cannot block here either.
        if new_proposal.magnitude_pct is not None:
            validation_context["proposed_magnitude"] = new_proposal.magnitude_pct
        else:
            validation_context.pop("proposed_magnitude", None)
        if new_proposal.parameters:
            validation_context["proposed_parameters"] = dict(new_proposal.parameters)
        else:
            validation_context.pop("proposed_parameters", None)

        new_results = self._run_validators(new_proposal, validation_context)
        all_validation_history.extend(new_results)
        new_all_valid = all(v.valid for v in new_results)

        info["advisory_skill_after"] = new_proposal.skill_name or ""
        info["advisory_changed_action"] = (
            info["advisory_skill_after"] != info["advisory_skill_before"])
        info["post_advice_rules"] = "|".join(sorted({
            ((getattr(v, "metadata", None) or {}).get("rules_hit") or ["unknown_rule"])[0]
            for v in new_results
            if (getattr(v, "metadata", None) or {}).get("disposition") == "ADVISE"
        }))

        return new_proposal, new_raw, new_results, new_all_valid, info
