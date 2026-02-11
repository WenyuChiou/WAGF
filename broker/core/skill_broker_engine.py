"""
Skill Broker Engine - Main orchestrator for Skill-Governed Architecture.

The Skill Broker retains the three-layer architecture:
  LLM Agent → Governed Broker → Simulation/World

Key changes from Action-based to Skill-based:
- LLM outputs SkillProposal (abstract behavior) instead of action/tool
- Broker validates skills through registry and validators
- Execution happens ONLY through simulation engine (system-only)

MCP Role (if used):
- MCP is ONLY for execution substrate (tool access, sandbox, logging)
- MCP does NOT participate in governance or decision-making
- MCP is NOT exposed to LLM agents
"""
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime

from ..interfaces.skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill, InterventionReport,
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from ..components.governance.registry import SkillRegistry
from ..utils.model_adapter import ModelAdapter
from ..validators import AgentValidator
from ..components.memory.engine import MemoryEngine
from ..components.context.builder import ContextBuilder, BaseAgentContextBuilder
from ..utils.agent_config import GovernanceAuditor, load_agent_config
from ..components.analytics.interaction import InteractionHub
from ..components.analytics.audit import AuditWriter
from ..components.governance.retriever import SkillRetriever
from ..utils.logging import logger

from ._retry_loop import RetryMixin
from ._audit_helpers import AuditMixin
from ._skill_filtering import SkillFilterMixin


class SkillBrokerEngine(RetryMixin, AuditMixin, SkillFilterMixin):
    """
    Skill-Governed Broker Engine.
    
    The Broker MUST:
    - Build bounded context (READ-ONLY)
    - Parse LLM output via ModelAdapter → SkillProposal
    - Validate skills through registry + validators
    - Produce ApprovedSkill (NOT execute directly)
    - Route to simulation engine for execution (SYSTEM-ONLY)
    - Write complete audit traces
    
    The Broker MUST NOT:
    - Make decisions (LLM does this)
    - Mutate state directly (Simulation does this)
    - Execute skills (Simulation does this)
    """
    
    def __init__(
        self,
        skill_registry: SkillRegistry,
        model_adapter: ModelAdapter,
        validators: List[AgentValidator],
        simulation_engine: Any,
        context_builder: Any,
        config: Optional[Any] = None,
        skill_retriever: Optional[SkillRetriever] = None,
        audit_writer: Optional[Any] = None,
        max_retries: int = 3,
        log_prompt: bool = False,
        custom_validators: Optional[List[Callable]] = None # New parameter
    ):
        self.skill_registry = skill_registry
        self.model_adapter = model_adapter
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.context_builder = context_builder
        self.config = config or load_agent_config()
        self.custom_validators = custom_validators or [] # Store custom validators
        
        if skill_retriever:
            self.skill_retriever = skill_retriever
        else:
            global_skills = self.config.get_global_skills("default")
            full_disclosure = self.config.get_full_disclosure_agent_types()
            self.skill_retriever = SkillRetriever(
                top_n=3, 
                global_skills=global_skills,
                full_disclosure_agent_types=full_disclosure
            )
            
        self.audit_writer = audit_writer
        self.max_retries = max_retries if max_retries != 3 else self.config.get_governance_retries(max_retries)
        self.max_reports = self.config.get_governance_max_reports()
        self.log_prompt = log_prompt
        
        self.stats = {
            "total": 0,
            "approved": 0,
            "retry_success": 0,
            "rejected": 0,
            "aborted": 0
        }
        self.auditor = GovernanceAuditor()

    
    def process_step(
        self,
        agent_id: str,
        step_id: int,
        run_id: str,
        seed: int,
        llm_invoke: Callable[[str], str],
        agent_type: str = "default",
        env_context: Dict[str, Any] = None
    ) -> SkillBrokerResult:
        """
        Process one complete decision step through skill governance.
        
        Flow:
        ① Build bounded context (READ-ONLY)
        ② LLM output → ModelAdapter → SkillProposal
        ③ Skill validation (registry + validators)
        ④ ApprovedSkill creation
        ⑤ Execution (simulation engine ONLY)
        ⑥ Audit trace
        """
        self.stats["total"] += 1
        timestamp = datetime.now().isoformat()
        
        # ① Build bounded context (READ-ONLY)
        context = self.context_builder.build(agent_id, step_id=step_id, run_id=run_id, env_context=env_context)
        self._inject_filtered_skills(context, agent_type)
        context_hash = self._hash_context(context)

        # Phase 28: Dynamic Skill Retrieval (RAG)
        # Re-alignment: Only apply RAG for advanced engines (Hierarchical, Importance, HumanCentric)
        # to maintain parity for the baseline WindowMemoryEngine benchmarks.
        should_rag = self.skill_retriever and context.get("available_skills")
        if should_rag:
            from broker.components.memory.engine import WindowMemoryEngine
            # Safely check for WindowMemoryEngine to maintain legacy parity
            mem_engine = getattr(self.context_builder, 'memory_engine', None)
            if not mem_engine and hasattr(self.context_builder, 'hub'):
                mem_engine = getattr(self.context_builder.hub, 'memory_engine', None)
            
            if isinstance(mem_engine, WindowMemoryEngine):
                should_rag = False
        
        if should_rag:
            raw_skill_ids = context["available_skills"]
            # Convert IDs to full definitions for retriever
            eligible_skills = []
            for sid in raw_skill_ids:
                s_def = self.skill_registry.get(sid)
                if s_def:
                    eligible_skills.append(s_def)
            
            # Retrieve top relevant skills
            retrieved_skills = self.skill_retriever.retrieve(context, eligible_skills)
            logger.debug(f" [RAG] Retrieved {len(retrieved_skills)} relevant skills for {agent_id}")
            
            # Update context with retrieved skill IDs
            context["available_skills"] = [s.skill_id for s in retrieved_skills]
            # Also store full definitions for ContextBuilder to show descriptions if needed
            context["retrieved_skill_definitions"] = retrieved_skills
            self._inject_options_text(context, [s.skill_id for s in retrieved_skills])

        # Robust memory extraction for audit (handles nesting and stringification)
        raw_mem = context.get("memory")
        if raw_mem is None and "personal" in context:
            raw_mem = context["personal"].get("memory")
            
        if isinstance(raw_mem, str):
            # Convert bulleted string back to list for cleaner JSON logs
            memory_pre = [m.lstrip("- ").strip() for m in raw_mem.split("\n") if m.strip()]
        else:
            memory_pre = list(raw_mem).copy() if raw_mem else []
        
        # ② LLM output → ModelAdapter → SkillProposal (with retry for empty/failed parse)
        prompt = self.context_builder.format_prompt(context)
        skill_proposal, raw_output, format_retry_count, total_llm_stats = (
            self._invoke_llm_with_retries(prompt, llm_invoke, context, agent_id, agent_type, env_context)
        )

        if skill_proposal is None:
            self.stats["aborted"] += 1
            self.auditor.log_parse_error()
            if format_retry_count > 0:
                self.auditor.log_structural_fault_terminal(format_retry_count)
            logger.error(f" [LLM:Error] Model returned unparsable output after retries for {agent_id}.")
            return self._create_result(SkillOutcome.ABORTED, None, None, None, ["Parse error after retries"], format_retries=format_retry_count)

        if format_retry_count > 0:
            self.auditor.log_structural_fault_resolved(format_retry_count)
            logger.info(f" [Broker:StructuralFault] {format_retry_count} format issue(s) fixed by retry for {agent_id}")

        # ③ Skill validation
        # Standardization (Phase 9/12): Decouple domain-specific keys
        if env_context is None:
            env_context = {}

        flat_state = context.get("state", {})
        flat_env = env_context

        # Diagnostic: warn on key collisions between agent state and env context
        if __debug__:
            collisions = set(flat_state.keys()) & set(flat_env.keys())
            if collisions:
                logger.warning(
                    f"[Governance:Diagnostic] Key collision in validation context: "
                    f"{collisions}. env_context takes precedence. "
                    f"Consider using distinct key names."
                )

        validation_context = {
            "agent_state": context,
            "agent_type": agent_type,
            "env_state": env_context,  # The "New Standard" source of truth
            **flat_state,              # Flatten agent state for custom validators
            **flat_env,                # Flat injection for legacy validator lookups
        }

        # Inject proposed magnitude into validation context (activates magnitude_cap_check)
        if skill_proposal and skill_proposal.magnitude_pct is not None:
            validation_context["proposed_magnitude"] = skill_proposal.magnitude_pct

        validation_results = self._run_validators(skill_proposal, validation_context)
        all_validation_history = list(validation_results)
        all_valid = all(v.valid for v in validation_results)
        
        # Track initial errors for audit summary
        initial_rule_ids = set()
        for v in validation_results:
            initial_rule_ids.update(v.metadata.get("rules_hit", []))
        
        # Diagnostic summary for User
        if self.log_prompt:
            reasoning = skill_proposal.reasoning or {}
            label_parts = []
            
            # Dynamic Label Extraction from reasoning
            # Try to get labels (config-driven)
            if self.config:
                log_fields = self.config.get_log_fields(agent_type)
                for field_name in log_fields:
                    val = None
                    # Try various casing and suffix variants
                    for variants in [field_name, field_name.upper(), f"{field_name}_LABEL", field_name.capitalize(), field_name.lower()]:
                        if variants in reasoning:
                            val = reasoning[variants]
                            break
                    if val:
                        label_parts.append(f"{field_name}: {val}")
            
            # Legacy Fallback for Strategy/Confidence if not in log_fields
            if not any("Strategy" in p for p in label_parts) and "Strategy" in reasoning:
                label_parts.append(f"Strategy: {reasoning['Strategy']}")
            if not any("Confidence" in p for p in label_parts) and "Confidence" in reasoning:
                label_parts.append(f"Confidence: {reasoning['Confidence']}")

        # Log initial validation failure (before retry loop) for diagnostic clarity
        if not all_valid:
            initial_errors = [e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors]
            choice_name = skill_proposal.skill_name if skill_proposal else "parsing_failed"
            logger.warning(f" [Governance:Initial] {agent_id} | Choice: '{choice_name}' | Validation FAILED | Errors: {initial_errors}")

        # Log WARNING-level observations (non-blocking)
        for v in validation_results:
            if v.valid and hasattr(v, 'warnings') and v.warnings:
                logger.info(f" [Governance:Warning] {agent_id} | {v.warnings[0]}")

        # Governance retry loop
        skill_proposal, raw_output, validation_results, all_validation_history, all_valid, retry_count = (
            self._governance_retry_loop(
                all_valid=all_valid, skill_proposal=skill_proposal,
                validation_results=validation_results,
                all_validation_history=all_validation_history,
                validation_context=validation_context,
                prompt=prompt, llm_invoke=llm_invoke, context=context,
                agent_id=agent_id, agent_type=agent_type,
                env_context=env_context, raw_output=raw_output,
                total_llm_stats=total_llm_stats,
            )
        )

        # ④ Create ApprovedSkill or use fallback
        approved_skill, outcome = self._build_approved_skill(
            all_valid=all_valid, skill_proposal=skill_proposal,
            agent_id=agent_id, agent_type=agent_type,
            retry_count=retry_count, validation_results=validation_results,
            initial_rule_ids=initial_rule_ids,
        )
        
        # FINAL STEP SUMMARY (Console)
        if retry_count > 0:
             pass # Already logged success above
        
        # ④b Multi-skill: validate + build secondary (if enabled)
        secondary_proposal = None
        secondary_approved = None
        secondary_execution = None
        composite_errors = []
        ms_cfg = self.config.get_multi_skill_config(agent_type) if self.config else {}
        if ms_cfg and skill_proposal and all_valid:
            sec_skill = skill_proposal.reasoning.get("_secondary_skill_name")
            sec_mag = skill_proposal.reasoning.get("_secondary_magnitude_pct")
            if sec_skill:
                secondary_proposal = SkillProposal(
                    skill_name=sec_skill,
                    agent_id=agent_id,
                    reasoning={"_source": "secondary"},
                    magnitude_pct=sec_mag,
                )
                # Composite conflict check
                comp_result = self.skill_registry.check_composite_conflicts(
                    [skill_proposal.skill_name, sec_skill]
                )
                if not comp_result.valid:
                    composite_errors.extend(comp_result.errors)
                    logger.warning(f" [Multi-Skill] {agent_id} | Composite conflict: {comp_result.errors}")
                    secondary_proposal = None  # Drop conflicting secondary
                elif sec_skill == skill_proposal.skill_name:
                    composite_errors.append(f"Primary and secondary are the same: '{sec_skill}'")
                    secondary_proposal = None
                else:
                    # Validate secondary individually
                    sec_validation = self._run_validators(
                        secondary_proposal, validation_context
                    )
                    sec_valid = all(v.valid for v in sec_validation if v)
                    if sec_valid:
                        sec_params = {}
                        if sec_mag is not None:
                            sec_params["magnitude_pct"] = sec_mag
                        secondary_approved = ApprovedSkill(
                            skill_name=sec_skill,
                            agent_id=agent_id,
                            approval_status="APPROVED",
                            validation_results=sec_validation,
                            execution_mapping=self.skill_registry.get_execution_mapping(sec_skill) or "",
                            parameters=sec_params,
                        )
                    else:
                        sec_errs = [e for v in sec_validation if v for e in v.errors]
                        composite_errors.extend(sec_errs)
                        logger.warning(f" [Multi-Skill] {agent_id} | Secondary '{sec_skill}' failed: {sec_errs}")
                        secondary_proposal = None

        # ⑤ Execution (simulation engine ONLY — skip if REJECTED)
        if self.simulation_engine and outcome not in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
            execution_result = self.simulation_engine.execute_skill(approved_skill)
            # ⑤b Sequential secondary execution
            if secondary_approved and execution_result.success:
                secondary_execution = self.simulation_engine.execute_skill(secondary_approved)
        elif outcome in (SkillOutcome.REJECTED, SkillOutcome.UNCERTAIN):
            # REJECTED: execute the registry's default skill as fallback so the
            # agent's state is recalculated (instead of a full no-op that
            # freezes state).
            if self.simulation_engine:
                fallback_skill = self.skill_registry.get_default_skill()
                if fallback_skill and self.skill_registry.exists(fallback_skill):
                    fallback = ApprovedSkill(
                        skill_name=fallback_skill,
                        agent_id=approved_skill.agent_id,
                        approval_status="REJECTED_FALLBACK",
                    )
                    execution_result = self.simulation_engine.execute_skill(fallback)
                else:
                    logger.warning(f"Default skill '{fallback_skill}' not in registry for {approved_skill.agent_id}")
                    execution_result = ExecutionResult(success=False, state_changes={})
            else:
                execution_result = ExecutionResult(success=False, state_changes={})
        else:
            # Standalone mode: Default to pseudo-execution
            execution_result = ExecutionResult(
                success=True,
                state_changes={}
            )

        # Capture memory state after execution (before experiment-layer updates)
        memory_post = self._get_memory_snapshot(agent_id)

        # ⑥ Audit trace
        if self.audit_writer:
            self._write_audit_trace(
                agent_type=agent_type, context=context,
                run_id=run_id, step_id=step_id, timestamp=timestamp,
                env_context=env_context, seed=seed, agent_id=agent_id,
                all_valid=all_valid, prompt=prompt, raw_output=raw_output,
                context_hash=context_hash, memory_pre=memory_pre,
                memory_post=memory_post, skill_proposal=skill_proposal,
                approved_skill=approved_skill, execution_result=execution_result,
                outcome=outcome, retry_count=retry_count,
                format_retry_count=format_retry_count,
                total_llm_stats=total_llm_stats,
                all_validation_history=all_validation_history,
            )

        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=skill_proposal,
            approved_skill=approved_skill,
            execution_result=execution_result,
            validation_errors=[e for v in validation_results if v and hasattr(v, 'errors') for e in v.errors],
            retry_count=retry_count,
            format_retries=format_retry_count,
            secondary_proposal=secondary_proposal,
            secondary_approved=secondary_approved,
            secondary_execution=secondary_execution,
            composite_validation_errors=composite_errors,
        )
    
    def _build_approved_skill(
        self, *, all_valid: bool, skill_proposal, agent_id: str,
        agent_type: str, retry_count: int, validation_results: List,
        initial_rule_ids: set,
    ):
        """Build ApprovedSkill for both approved and rejected paths.

        Returns (approved_skill, outcome). May mutate skill_proposal on
        the rejection path (clears magnitude_pct, sets magnitude_fallback).
        """
        _params = {}
        if skill_proposal and skill_proposal.magnitude_pct is not None:
            _params["magnitude_pct"] = skill_proposal.magnitude_pct
            _params["magnitude_fallback"] = skill_proposal.magnitude_fallback

        if all_valid and skill_proposal:
            approved_skill = ApprovedSkill(
                skill_name=skill_proposal.skill_name,
                agent_id=agent_id,
                approval_status="APPROVED",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(skill_proposal.skill_name) or "",
                parameters=_params,
            )
            outcome = SkillOutcome.RETRY_SUCCESS if retry_count > 0 else SkillOutcome.APPROVED
            if retry_count > 0:
                self.stats["retry_success"] += 1
                ratings = []
                for k, v in (skill_proposal.reasoning or {}).items():
                    if "_LABEL" in k:
                        ratings.append(f"{k}={v}")
                rating_str = f" | {' | '.join(ratings)}" if ratings else ""
                logger.warning(
                    f" [Governance:Success] {agent_id} | Fixed after {retry_count} retries"
                    f" | Choice: '{skill_proposal.skill_name}'{rating_str}"
                )
                for rule_id in initial_rule_ids:
                    self.auditor.log_intervention(rule_id, success=True, is_final=True)
            else:
                self.stats["approved"] += 1
        else:
            # RETRY EXHAUSTION: proceed with REJECTED status for audit
            is_generic_fallback = (skill_proposal is None or skill_proposal.parse_layer == "default")

            if skill_proposal and skill_proposal.magnitude_pct is not None:
                # Don't mutate the original SkillProposal — carry values via _params
                # (the proposal may be referenced by audit writer, memory, or cache)
                _params = {"magnitude_pct": None, "magnitude_fallback": True}

            fallout_skill = (
                skill_proposal.skill_name if not is_generic_fallback
                else self.config.get_parsing_config(agent_type).get(
                    "default_skill", self.skill_registry.get_default_skill()
                )
            )

            approved_skill = ApprovedSkill(
                skill_name=fallout_skill,
                agent_id=agent_id,
                approval_status="REJECTED" if not is_generic_fallback else "REJECTED_FALLBACK",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(fallout_skill) or "",
                parameters=_params,
            )
            outcome = SkillOutcome.REJECTED if not is_generic_fallback else SkillOutcome.UNCERTAIN

            if is_generic_fallback:
                logger.error(f" [Governance:Exhausted] {agent_id} | Parsing failed. Forcing fallback: '{fallout_skill}'")
            else:
                logger.error(f" [Governance:Exhausted] {agent_id} | Retries failed. Proceeding with REJECTED choice: '{fallout_skill}'")

            self.stats["rejected"] += 1
            for v in validation_results:
                for rule_id in v.metadata.get("rules_hit", []):
                    self.auditor.log_intervention(rule_id, success=False, is_final=True)

        return approved_skill, outcome

    def _run_validators(self, proposal: SkillProposal, context: Dict) -> List[ValidationResult]:
        """Run all validators on the skill proposal."""
        results = []
        for validator in self.validators:
            result = validator.validate(proposal, context, self.skill_registry)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)

        # Run custom validators
        for custom_validator_func in self.custom_validators:
            custom_results = custom_validator_func(proposal, context, self.skill_registry)
            if isinstance(custom_results, list):
                results.extend(custom_results)
            else:
                results.append(custom_results)

        # Registry-level: validate LLM output against skill's output_schema
        if (proposal and proposal.skill_name and self.skill_registry
                and self.skill_registry.exists(proposal.skill_name)):
            output_fields = {}
            if proposal.magnitude_pct is not None:
                output_fields["magnitude_pct"] = proposal.magnitude_pct
            # Reverse-lookup: find which numbered option maps to this skill_name
            # so the 'decision' field expected by output_schema is populated.
            agent_ctx = context.get("agent_state", {})
            personal = agent_ctx.get("personal", {}) if isinstance(agent_ctx, dict) else {}
            skill_map = personal.get("dynamic_skill_map", {})
            for num_str, sid in skill_map.items():
                if sid == proposal.skill_name:
                    try:
                        output_fields["decision"] = int(num_str)
                    except (ValueError, TypeError):
                        output_fields["decision"] = num_str
                    break
            schema_result = self.skill_registry.validate_output_schema(
                proposal.skill_name, output_fields
            )
            if schema_result:
                if not schema_result.valid:
                    schema_result.metadata["rules_hit"] = ["output_schema_violation"]
                    logger.debug(f"[OutputSchema] {proposal.skill_name}: {schema_result.errors}")
                results.append(schema_result)

        # Registry-level: check YAML preconditions against agent state
        if (proposal and proposal.skill_name and self.skill_registry
                and self.skill_registry.exists(proposal.skill_name)):
            agent_ctx = context.get("agent_state", {})
            state = agent_ctx.get("state", {}) if isinstance(agent_ctx, dict) else {}
            precond_result = self.skill_registry.check_preconditions(
                proposal.skill_name, state
            )
            if precond_result:
                if not precond_result.valid:
                    precond_result.metadata["rules_hit"] = ["precondition_violation"]
                    logger.debug(f"[Precondition] {proposal.skill_name}: {precond_result.errors}")
                results.append(precond_result)

        return results

    def _create_result(self, outcome, proposal, approved, execution, errors, format_retries: int = 0) -> SkillBrokerResult:
        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=proposal,
            approved_skill=approved,
            execution_result=execution,
            validation_errors=errors,
            retry_count=0,
            format_retries=format_retries
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        total = self.stats["total"]
        if total == 0:
            return {**self.stats, "approval_rate": "N/A"}
        
        approved = self.stats["approved"] + self.stats["retry_success"]
        return {
            **self.stats,
            "approval_rate": f"{approved/total*100:.1f}%",
            "first_pass_rate": f"{self.stats['approved']/total*100:.1f}%"
        }
