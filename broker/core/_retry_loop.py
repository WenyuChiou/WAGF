"""RetryMixin — LLM retry and governance retry loop logic.

Extracted from SkillBrokerEngine to reduce file size.  These methods
access ``self.*`` attributes defined on SkillBrokerEngine; this is the
standard Python mixin pattern where the mixin is always combined with
the host class via multiple inheritance.
"""
from typing import Callable, Dict, List, Optional

from ..interfaces.skill_types import (
    SkillProposal, InterventionReport, ValidationResult,
)
from ..utils.logging import logger


class RetryMixin:
    """Mixin providing LLM retry and governance retry loop logic."""

    # ------------------------------------------------------------------
    # Format / parse retry loop
    # ------------------------------------------------------------------
    def _invoke_llm_with_retries(
        self, prompt: str, llm_invoke: Callable, context: Dict,
        agent_id: str, agent_type: str, env_context: Optional[Dict]
    ):
        """Invoke LLM with format/parse retry loop.

        Returns (skill_proposal, raw_output, format_retry_count, total_llm_stats).
        """
        skill_proposal = None
        raw_output = ""
        initial_attempts = 0
        format_retry_count = 0
        max_initial_attempts = 2
        total_llm_stats = {"llm_retries": 0, "llm_success": False}

        while initial_attempts <= max_initial_attempts and not skill_proposal:
            initial_attempts += 1
            try:
                res = llm_invoke(prompt)
                if isinstance(res, tuple):
                    raw_output, llm_stats_obj = res
                    total_llm_stats["llm_retries"] += llm_stats_obj.retries
                    total_llm_stats["llm_success"] = llm_stats_obj.success
                    # R5-C: Accumulate token counts across retries
                    if getattr(llm_stats_obj, 'prompt_tokens', 0) > 0:
                        total_llm_stats["prompt_tokens"] = total_llm_stats.get("prompt_tokens", 0) + llm_stats_obj.prompt_tokens
                        total_llm_stats["response_tokens"] = total_llm_stats.get("response_tokens", 0) + llm_stats_obj.response_tokens
                        total_llm_stats["num_ctx"] = llm_stats_obj.num_ctx
                        # Keep the highest context utilization across calls
                        total_llm_stats["context_utilization"] = max(
                            total_llm_stats.get("context_utilization", 0.0),
                            round(llm_stats_obj.context_utilization, 4),
                        )
                    if hasattr(llm_stats_obj, 'empty_content_retries'):
                        for _ in range(llm_stats_obj.empty_content_retries):
                            self.auditor.log_empty_content_retry()
                        if getattr(llm_stats_obj, 'empty_content_failure', False):
                            self.auditor.log_empty_content_failure()
                else:
                    raw_output = res
                    from ..utils.llm_utils import get_llm_stats
                    stats = get_llm_stats()
                    total_llm_stats["llm_retries"] += stats.get("current_retries", 0)
                    total_llm_stats["llm_success"] = stats.get("current_success", True)

                if isinstance(raw_output, SkillProposal):
                    skill_proposal = raw_output
                else:
                    skill_proposal = self.model_adapter.parse_output(raw_output, {
                        "agent_id": agent_id,
                        "agent_type": agent_type,
                        "retry_attempt": initial_attempts - 1,
                        "current_year": env_context.get("current_year") if env_context else "?",
                        **context
                    })

                if skill_proposal is None:
                    msg = "Response was empty or unparsable. Please output a valid JSON decision."
                    logger.warning(f" [Broker:Retry] Empty/Null response received (Attempt {initial_attempts}/{max_initial_attempts})")
                    format_retry_count += 1
                    self.auditor.log_parse_error()
                    prompt = self.model_adapter.format_retry_prompt(prompt, [msg])
                    continue

                if skill_proposal and skill_proposal.reasoning:
                    reasoning = skill_proposal.reasoning
                    parsing_cfg = self.config.get(agent_type).get("parsing", {})
                    required_constructs = [k for k in parsing_cfg.get("constructs", {}).keys() if "_LABEL" in k]
                    missing_labels = [m for m in required_constructs if m not in reasoning]

                    if missing_labels and initial_attempts <= max_initial_attempts:
                        logger.warning(f" [Broker:Retry] Missing required constructs {missing_labels} for {agent_id} ({agent_type}), attempt {initial_attempts}/{max_initial_attempts}")
                        format_retry_count += 1
                        self.auditor.log_parse_error()
                        self.auditor.log_invalid_label_retry()
                        skill_proposal = None
                        prompt = self.model_adapter.format_retry_prompt(prompt, [f"Missing required constructs: {missing_labels}. Please ensure your response follows the requested JSON format."])
                        continue

            except Exception as e:
                if initial_attempts > max_initial_attempts:
                    logger.error(f" [Broker:Error] Failed to parse LLM output after {max_initial_attempts} attempts: {e}")
                    raise
                logger.warning(f" [Broker:Retry] Parsing failed ({initial_attempts}/{max_initial_attempts}): {e}")
                prompt = self.model_adapter.format_retry_prompt(prompt, [str(e)])

        return skill_proposal, raw_output, format_retry_count, total_llm_stats

    # ------------------------------------------------------------------
    # Helper statics for early-exit detection
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_blocking_rule_ids(validation_results: List) -> frozenset:
        """Extract the set of rule IDs causing validation failure.

        Config-level rules store IDs in metadata["rules_hit"] (list),
        custom validators store in metadata["rule_id"] (str).
        Returns a frozenset for easy comparison across retry attempts.
        """
        rule_ids: set = set()
        for v in validation_results:
            if v and hasattr(v, "valid") and not v.valid:
                meta = getattr(v, "metadata", None) or {}
                if meta.get("rules_hit"):
                    rule_ids.update(meta["rules_hit"])
                elif meta.get("rule_id"):
                    rule_ids.add(meta["rule_id"])
        return frozenset(rule_ids)

    @staticmethod
    def _all_blocking_deterministic(validation_results: List) -> bool:
        """Check if ALL blocking rules are deterministic (e.g. affordability).

        Deterministic rules depend on static agent attributes (income,
        property value) that don't change between retries, so retrying
        is futile.  Construct-based rules depend on LLM output which
        MAY change on retry, so EarlyExit should not apply to them.
        """
        has_any_blocking = False
        for v in validation_results:
            if v and hasattr(v, "valid") and not v.valid:
                has_any_blocking = True
                meta = getattr(v, "metadata", None) or {}
                if not meta.get("deterministic", False):
                    return False  # At least one non-deterministic rule
        return has_any_blocking

    # ------------------------------------------------------------------
    # Governance retry loop
    # ------------------------------------------------------------------
    def _governance_retry_loop(
        self, *, all_valid: bool, skill_proposal, validation_results: List,
        all_validation_history: List, validation_context: Dict,
        prompt: str, llm_invoke: Callable, context: Dict,
        agent_id: str, agent_type: str, env_context: Optional[Dict],
        raw_output: str, total_llm_stats: Dict,
    ):
        """Run governance validation retry loop.

        Re-invokes LLM with intervention reports when validation fails,
        up to self.max_retries attempts. Logs fallout diagnostics on
        exhaustion.

        Includes early-exit optimisation: if the first retry is blocked
        by the exact same rule IDs as the initial attempt, remaining
        retries are skipped (the blocking conditions are static and
        won't change).

        Returns (skill_proposal, raw_output, validation_results,
                 all_validation_history, all_valid, retry_count).
        Mutates total_llm_stats and all_validation_history in-place.
        """
        retry_count = 0
        prev_blocking_rules = self._extract_blocking_rule_ids(validation_results)
        while not all_valid and retry_count < self.max_retries:
            retry_count += 1

            # Build InterventionReports for explainable governance
            intervention_reports = []
            for v in validation_results:
                if v and hasattr(v, 'errors') and v.errors:
                    for error_msg in v.errors:
                        report = InterventionReport(
                            rule_id=v.metadata.get("rules_hit", ["unknown_rule"])[0] if v.metadata.get("rules_hit") else "unknown_rule",
                            blocked_skill=skill_proposal.skill_name if skill_proposal else "unknown",
                            violation_summary=error_msg,
                            suggested_correction=v.metadata.get("suggestion"),
                            severity="ERROR" if not v.valid else "WARNING",
                            domain_context=v.metadata,
                        )
                        intervention_reports.append(report)

            if not skill_proposal:
                errors_to_send = [InterventionReport(
                    rule_id="format_violation",
                    blocked_skill="parsing",
                    violation_summary="LLM output failed to match required delimiter or JSON structure.",
                    suggested_correction="Ensure your response follows the specified format including all required fields within the delimiters.",
                    severity="ERROR",
                )]
            else:
                errors_to_send = intervention_reports if intervention_reports else [
                    e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors
                ]

            retry_prompt = self.model_adapter.format_retry_prompt(prompt, errors_to_send, max_reports=self.max_reports)
            res = llm_invoke(retry_prompt)

            if isinstance(res, tuple):
                raw_output, llm_stats_obj = res
                total_llm_stats["llm_retries"] += llm_stats_obj.retries
                total_llm_stats["llm_success"] = llm_stats_obj.success
                # R5-C: Accumulate token counts across governance retries
                if getattr(llm_stats_obj, 'prompt_tokens', 0) > 0:
                    total_llm_stats["prompt_tokens"] = total_llm_stats.get("prompt_tokens", 0) + llm_stats_obj.prompt_tokens
                    total_llm_stats["response_tokens"] = total_llm_stats.get("response_tokens", 0) + llm_stats_obj.response_tokens
                    total_llm_stats["num_ctx"] = llm_stats_obj.num_ctx
                    total_llm_stats["context_utilization"] = max(
                        total_llm_stats.get("context_utilization", 0.0),
                        round(llm_stats_obj.context_utilization, 4),
                    )
            else:
                raw_output = res
                from ..utils.llm_utils import get_llm_stats
                stats = get_llm_stats()
                total_llm_stats["llm_retries"] += stats.get("current_retries", 0)
                total_llm_stats["llm_success"] = stats.get("current_success", True)

            skill_proposal = self.model_adapter.parse_output(raw_output, {
                **context,
                "agent_id": agent_id,
                "agent_type": agent_type,
                "retry_attempt": retry_count,
                "current_year": env_context.get("current_year") if env_context else "?",
            })

            if skill_proposal:
                validation_results = self._run_validators(skill_proposal, validation_context)
                all_validation_history.extend(validation_results)
                all_valid = all(v.valid for v in validation_results)
                if not all_valid:
                    errors_list = [e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors]
                    logger.warning(f"[Governance:Retry] Attempt {retry_count} failed validation for {agent_id}. Errors: {errors_list}")

                    # Early exit: only if ALL blocking rules are deterministic
                    # (e.g. affordability — agent income/property don't change
                    # on retry).  Construct-based rules (e.g. low_coping) depend
                    # on LLM output which may change, so allow full retries.
                    current_blocking = self._extract_blocking_rule_ids(validation_results)
                    all_deterministic = self._all_blocking_deterministic(validation_results)
                    if current_blocking and current_blocking == prev_blocking_rules and all_deterministic:
                        logger.info(
                            f"[Governance:EarlyExit] Deterministic rules blocked retry {retry_count} "
                            f"for {agent_id}: {sorted(current_blocking)}. "
                            f"Skipping remaining retries."
                        )
                        break
                    prev_blocking_rules = current_blocking
            else:
                self.auditor.log_parse_error()
                logger.warning(f"[Governance:Retry] Attempt {retry_count} produced unparsable output for {agent_id}.")

        # Fallout diagnostics on exhaustion
        if not all_valid and retry_count >= self.max_retries:
            errors = [e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors]
            logger.error(f"[Governance:Fallout] CRITICAL: Max retries ({self.max_retries}) reached for {agent_id}.")
            final_choice = skill_proposal.skill_name if skill_proposal else "Unknown"
            logger.error(f"  - Final Choice Rejected: '{final_choice}'")
            logger.error(f"  - Blocked By: {errors}")

            ratings = []
            if skill_proposal and skill_proposal.reasoning:
                for k, v in skill_proposal.reasoning.items():
                    if "_LABEL" in k:
                        ratings.append(f"{k}={v}")
            if ratings:
                logger.error(f"  - Ratings: {' | '.join(ratings)}")

            if skill_proposal and skill_proposal.reasoning:
                reason_keys = [k for k in skill_proposal.reasoning.keys() if "_REASON" in k.upper() or "REASON" in k.upper()]
                if reason_keys:
                    reason_text = skill_proposal.reasoning.get(reason_keys[0], "")
                    if isinstance(reason_text, dict):
                        reason_text = reason_text.get("reason", str(reason_text))
                    logger.error(f"  - Agent Motivation: {reason_text}")

            fallout_skill = (
                skill_proposal.skill_name
                if (skill_proposal and skill_proposal.parse_layer != "default")
                else self.skill_registry.get_default_skill()
            )
            logger.error(f"  - Action: Proceeding with '{fallout_skill}' (Result: REJECTED)")

        return skill_proposal, raw_output, validation_results, all_validation_history, all_valid, retry_count
