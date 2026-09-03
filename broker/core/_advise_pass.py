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
from ._advise import (
    build_intervention_reports,
    collect_soft_findings,
    count_unidentified_soft_findings,
    render_intervention_prompt,
    soft_finding_ids,
)


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


def _blank_soft_info(mode: str) -> Dict[str, Any]:
    """All PR-6 soft-rule audit fields, defaulted for the nothing-fired case."""
    # NOT named `advise_mode`: that key already belongs to the P0-1c arm payload
    # (:func:`_blank_info`), both dicts are spread into the same trace, and the
    # later spread would silently overwrite the earlier one — an arm's recorded
    # mode replaced by this channel's, in the one column an analyst uses to tell
    # the arms apart.
    return {
        "soft_advise_mode": mode,
        "advise_findings": "",
        "advise_shown": False,
        "advise_reports_shown": 0,
        "advise_skill_before": "",
        "advise_skill_after": "",
        # Which proposal actually executed. "pre" whenever the pre-advice
        # proposal stands — including `record`, where no advice was ever
        # rendered — and "post" only when the model's revised proposal was
        # adopted. Without it, `advise_skill_before` == `advise_skill_after`
        # cannot be read: it means "the model did not change its mind" on one
        # row and "the revised proposal was rejected and discarded" on another.
        "advise_executed_stage": "pre",
        "advise_parse_failed": False,
        # W1: the soft channel holds BLOCKING constant, so a post-advice
        # proposal that would have failed validation never opens the retry loop.
        # It is recorded instead: the run is still analysable, and an arm where
        # advice pushed the model into invalid territory is visible rather than
        # silently smoothed away.
        "advise_post_validation_invalid": False,
        "advise_post_validation_rules": "",
        # C2: WARNING results that carried no rule id, so `advise_findings`
        # could not name them. A non-zero count says the cell is short because
        # the findings were anonymous, not because nothing warned.
        "soft_findings_unidentified": 0,
    }


class AdviseMixin:
    """Provides :meth:`_advisory_pass` and :meth:`_soft_rule_pass`. Mixed into SkillBrokerEngine."""

    # ------------------------------------------------------------------
    # PR-6: the SOFT-RULE channel
    # ------------------------------------------------------------------
    def _soft_rule_pass(
        self, *, all_valid: bool, skill_proposal, validation_results: List,
        all_validation_history: List, validation_context: Dict,
        prompt: str, llm_invoke, context: Dict,
        agent_id: str, agent_type: str, env_context: Optional[Dict],
        raw_output: str, total_llm_stats: Dict,
        attempt_skills: Optional[List] = None,
    ):
        """Record — and under ``feedback``, show — the WARNING-level findings.

        Returns ``(skill_proposal, raw_output, validation_results, all_valid, info)``.
        ``info`` is ``{}`` when the channel is off, which is what keeps the
        audit row's key set (and therefore the CSV's column set) frozen.

        Three modes, and the difference between them is exactly the thing the
        paper claims to be able to separate:

        * ``off``      — nothing happens. No collection, no call, no columns.
        * ``record``   — the findings are written to the row and the model is
          never told. ZERO extra LLM calls, so this arm cannot change behaviour
          and measures the soft rules' firing rate on its own.
        * ``feedback`` — ONE extra prompt carrying the advice, and the proposal
          is NOT blocked either way.

        Under ``feedback`` the call is issued only when the proposal is
        otherwise APPROVED. With a blocking ERROR already outstanding, the
        governance retry loop is about to re-prompt anyway; adding an advisory
        call first would mix the two channels inside one decision and make the
        contrast unreadable. The findings are still recorded in that case, with
        ``advise_shown=False`` saying plainly that the model was not told.

        **Advice NEVER changes whether the decision blocks (W1).** The
        ``all_valid`` this returns is always the PRE-advice one; a post-advice
        proposal that would fail validation is discarded, never re-prompted.
        Full mechanism and rationale: ``docs/guides/governance_layers.md``
        §"Advice never blocks".
        """
        mode = getattr(self, "_soft_advise_mode", "off")
        if mode == "off":
            return skill_proposal, raw_output, validation_results, all_valid, {}

        info = _blank_soft_info(mode)
        findings = collect_soft_findings(validation_results)
        info["advise_findings"] = "|".join(soft_finding_ids(validation_results))
        info["soft_findings_unidentified"] = count_unidentified_soft_findings(
            validation_results)

        if mode != "feedback" or not findings or skill_proposal is None or not all_valid:
            return skill_proposal, raw_output, validation_results, all_valid, info

        info["advise_skill_before"] = skill_proposal.skill_name or ""
        reports = build_intervention_reports(
            findings, skill_proposal, source="warnings", severity="ADVICE",
        )
        advisory_prompt, _shown = render_intervention_prompt(
            self.model_adapter, prompt, reports,
            max_reports=self.max_reports,
            framing=getattr(self, "_intervention_framing", "legacy"),
        )
        # Set BEFORE the call and never cleared on failure: the claim the column
        # supports is "the model was shown this advice", and that became true at
        # the moment the prompt was sent, whatever came back. But it is set from
        # what the RENDERER actually delivered, not asserted — an adapter that
        # dropped every report (max_reports=0, a custom adapter that filtered
        # them) sends a prompt carrying no advice, and claiming the model was
        # shown advice it never saw is the one thing this column exists to stop.
        info["advise_reports_shown"] = _shown
        info["advise_shown"] = bool(_shown)
        if not _shown:
            logger.warning(
                f"[Governance:Soft] {len(reports)} advisory report(s) for "
                f"{agent_id} rendered to ZERO shown reports "
                f"(max_reports={self.max_reports}); the call still happens but "
                "carries no advice, so advise_shown is False and this decision "
                "is a resample, not an advice observation. Exclude it from the "
                "matched contrast."
            )
        if "llm_calls" in total_llm_stats:
            total_llm_stats["llm_calls"] += 1

        try:
            res = llm_invoke(advisory_prompt)
        except Exception as exc:
            info["advise_parse_failed"] = True
            info["advise_skill_after"] = info["advise_skill_before"]
            if attempt_skills is not None:
                # The attempt HAPPENED; leaving it out shortens attempt_skills
                # so a reader counting attempts under-counts exactly the
                # decisions where the advisory call failed.
                attempt_skills.append(None)
            logger.warning(
                f"[Governance:Soft] Advice call raised for {agent_id}: {exc!r}. "
                "Keeping the pre-advice proposal; advice never blocks."
            )
            return skill_proposal, raw_output, validation_results, all_valid, info

        if isinstance(res, tuple):
            new_raw, stats_obj = res
            total_llm_stats["llm_retries"] += getattr(stats_obj, "retries", 0)
            # Aggregate exactly as _advisory_pass and the governance retry loop
            # do — token totals accumulate, context fields take the running MAX.
            # The advisory prompt appends header + rule text to the longest
            # prompt in the decision, so leaving it out under-reports peak
            # context pressure on precisely the decisions where advice fired,
            # and under-reports the arm's token cost against the `record` arm it
            # is meant to be compared with.
            if getattr(stats_obj, "prompt_tokens", 0) > 0:
                total_llm_stats["prompt_tokens"] = (
                    total_llm_stats.get("prompt_tokens", 0) + stats_obj.prompt_tokens)
                total_llm_stats["response_tokens"] = (
                    total_llm_stats.get("response_tokens", 0) + stats_obj.response_tokens)
                total_llm_stats["num_ctx"] = getattr(
                    stats_obj, "num_ctx", total_llm_stats.get("num_ctx"))
                total_llm_stats["context_utilization"] = max(
                    total_llm_stats.get("context_utilization", 0.0),
                    round(getattr(stats_obj, "context_utilization", 0.0) or 0.0, 4),
                )
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
            info["advise_parse_failed"] = True
            info["advise_skill_after"] = info["advise_skill_before"]
            logger.warning(
                f"[Governance:Soft] Unparsable post-advice output for {agent_id}; "
                "keeping the pre-advice proposal."
            )
            return skill_proposal, raw_output, validation_results, all_valid, info

        if new_proposal.magnitude_pct is not None:
            validation_context["proposed_magnitude"] = new_proposal.magnitude_pct
        else:
            validation_context.pop("proposed_magnitude", None)
        if new_proposal.parameters:
            validation_context["proposed_parameters"] = dict(new_proposal.parameters)
        else:
            validation_context.pop("proposed_parameters", None)

        new_results = self._run_validators(new_proposal, validation_context)
        # The post-advice results ALWAYS land in the decision's history, whether
        # or not the proposal is adopted, so the trace records what the advice
        # actually produced.
        all_validation_history.extend(new_results)
        info["advise_skill_after"] = new_proposal.skill_name or ""

        if not all(getattr(v, "valid", True) for v in new_results):
            info["advise_post_validation_invalid"] = True
            info["advise_post_validation_rules"] = "|".join(sorted({
                ((getattr(v, "metadata", None) or {}).get("rules_hit")
                 or [(getattr(v, "metadata", None) or {}).get("rule_id") or "unknown_rule"])[0]
                for v in new_results if not getattr(v, "valid", True)
            }))
            logger.warning(
                f"[Governance:Soft] Post-advice proposal for {agent_id} "
                f"({info['advise_skill_after']}) failed validation "
                f"({info['advise_post_validation_rules']}). Discarding it and "
                "executing the pre-advice proposal; the soft channel never "
                "opens the retry loop."
            )
            # Restore the validation context to the PRE-advice proposal, or the
            # next validator pass in this decision would score the pre-advice
            # skill against the discarded proposal's magnitude/parameters.
            if getattr(skill_proposal, "magnitude_pct", None) is not None:
                validation_context["proposed_magnitude"] = skill_proposal.magnitude_pct
            else:
                validation_context.pop("proposed_magnitude", None)
            if getattr(skill_proposal, "parameters", None):
                validation_context["proposed_parameters"] = dict(skill_proposal.parameters)
            else:
                validation_context.pop("proposed_parameters", None)
            return skill_proposal, raw_output, validation_results, all_valid, info

        info["advise_executed_stage"] = "post"
        # `all_valid` is the PRE-advice value on purpose (it is True here — the
        # guard above returned early otherwise), so blocking is held constant.
        return new_proposal, new_raw, new_results, all_valid, info

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
