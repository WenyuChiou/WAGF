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
import hashlib
import json

from ..interfaces.skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill, 
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from ..components.skill_registry import SkillRegistry
from ..utils.model_adapter import ModelAdapter
from .governed_broker import SkillBrokerEngine as _LegacyBroker # For structural reference if needed
from ..validators import AgentValidator
from ..components.memory_engine import MemoryEngine
from ..components.context_builder import ContextBuilder, BaseAgentContextBuilder
from ..utils.agent_config import GovernanceAuditor, load_agent_config
from ..components.interaction_hub import InteractionHub
from ..components.audit_writer import AuditWriter
from ..components.skill_retriever import SkillRetriever
from ..utils.logging import logger


class SkillBrokerEngine:
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
        config: Optional[Any] = None, # Phase 12: Accept config for generic logging
        skill_retriever: Optional[SkillRetriever] = None, # Phase 28: Dynamic Skill Retrieval
        audit_writer: Optional[Any] = None,
        max_retries: int = 3,
        log_prompt: bool = False
    ):
        self.skill_registry = skill_registry
        self.model_adapter = model_adapter
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.context_builder = context_builder
        # Phase 28: Universal RAG support. If no retriever provided, use default.
        # Phase 32: Configure Global Skills (Always Available)
        self.config = config or load_agent_config() # Default if not provided
        
        if skill_retriever:
            self.skill_retriever = skill_retriever
        else:
            # Create a retriever with global skills from config
            global_skills = self.config.get_global_skills("default") # Base default
            full_disclosure = self.config.get_full_disclosure_agent_types()
            self.skill_retriever = SkillRetriever(
                top_n=3, 
                global_skills=global_skills,
                full_disclosure_agent_types=full_disclosure
            )
            
        self.audit_writer = audit_writer
        self.max_retries = max_retries
        self.log_prompt = log_prompt
        
        # Statistics
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
        context_hash = self._hash_context(context)

        # Phase 28: Dynamic Skill Retrieval (RAG)
        # Re-alignment: Only apply RAG for advanced engines (Hierarchical, Importance, HumanCentric)
        # to maintain parity for the baseline WindowMemoryEngine benchmarks.
        should_rag = self.skill_retriever and context.get("available_skills")
        if should_rag:
            from broker.components.memory_engine import WindowMemoryEngine
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
        
        skill_proposal = None
        raw_output = ""
        initial_attempts = 0
        max_initial_attempts = 2  # Retry up to 2 times for purely parsing/empty issues
        total_llm_stats = {"llm_retries": 0, "llm_success": False}
        
        while initial_attempts <= max_initial_attempts and not skill_proposal:
            initial_attempts += 1
            try:
                res = llm_invoke(prompt)
                # Handle both legacy (str) and new (content, stats) returns
                if isinstance(res, tuple):
                    raw_output, llm_stats_obj = res
                    total_llm_stats["llm_retries"] += llm_stats_obj.retries
                    total_llm_stats["llm_success"] = llm_stats_obj.success
                else:
                    raw_output = res
                    # Fallback to global stats if legacy
                    from ..utils.llm_utils import get_llm_stats
                    stats = get_llm_stats()
                    total_llm_stats["llm_retries"] += stats.get("current_retries", 0)
                    total_llm_stats["llm_success"] = stats.get("current_success", True)
                
                # Pass full context for audit access
                skill_proposal = self.model_adapter.parse_output(raw_output, {
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    **context
                })
                
                # Check for missing critical LABEL constructs - trigger retry if missing
                if skill_proposal and skill_proposal.reasoning:
                    reasoning = skill_proposal.reasoning
                    
                    # Generalized: Get required constructs from parsing config
                    # Filter for those that have '_LABEL' in them as they are usually critical
                    # but check if they are actually defined for this agent type
                    parsing_cfg = self.config.get(agent_type).get("parsing", {})
                    required_constructs = [k for k in parsing_cfg.get("constructs", {}).keys() if "_LABEL" in k]
                    
                    missing_labels = [m for m in required_constructs if m not in reasoning]
                    
                    if missing_labels and initial_attempts <= max_initial_attempts:
                        logger.warning(f" [Broker:Retry] Missing required constructs {missing_labels} for {agent_id} ({agent_type}), attempt {initial_attempts}/{max_initial_attempts}")
                        # Reset proposal to None to trigger retry
                        skill_proposal = None
                        prompt = self.model_adapter.format_retry_prompt(prompt, [f"Missing required constructs: {missing_labels}. Please ensure your response follows the requested JSON format."])
                        continue

                        
            except Exception as e:
                if initial_attempts > max_initial_attempts:
                    logger.error(f" [Broker:Error] Failed to parse LLM output after {max_initial_attempts} attempts: {e}")
                    raise
                logger.warning(f" [Broker:Retry] Parsing failed ({initial_attempts}/{max_initial_attempts}): {e}")
                # Build retry prompt
                prompt = self.model_adapter.format_retry_prompt(prompt, [str(e)])
            
        if skill_proposal is None:
            self.stats["aborted"] += 1
            self.auditor.log_parse_error()
            logger.error(f" [LLM:Error] Model returned unparsable output after {max_initial_attempts+1} attempts for {agent_id}.")
            return self._create_result(SkillOutcome.ABORTED, None, None, None, ["Parse error after retries"])
        
        # ③ Skill validation
        # Standardization (Phase 9/12): Decouple domain-specific keys
        if env_context is None:
            env_context = {}

        validation_context = {
            "agent_state": context,
            "agent_type": agent_type,
            "env_state": env_context, # The "New Standard" source of truth
            **env_context             # Flat injection for legacy validator lookups
        }
        
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

            # Determine governance summary (Moved to end for consolidated reporting)
            pass
        
        # Retry loop
        retry_count = 0
        while not all_valid and retry_count < self.max_retries:
            retry_count += 1
            errors = [e for v in validation_results for e in v.errors]
            
            # Real-time Console Feedback (Hidden for noise reduction as requested)
            # logger.warning(f"[Governance] Blocked '{skill_proposal.skill_name}' for {agent_id} (Attempt {retry_count}). Reasons: {errors}")
            
            retry_prompt = self.model_adapter.format_retry_prompt(prompt, errors)
            res = llm_invoke(retry_prompt)
            
            # Use same logic to handle tuple vs str for retry call
            if isinstance(res, tuple):
                raw_output, llm_stats_obj = res
                # Accumulate stats
                total_llm_stats["llm_retries"] += llm_stats_obj.retries
                total_llm_stats["llm_success"] = llm_stats_obj.success
            else:
                raw_output = res
                from ..utils.llm_utils import get_llm_stats
                stats = get_llm_stats()
                total_llm_stats["llm_retries"] += stats.get("current_retries", 0)
                total_llm_stats["llm_success"] = stats.get("current_success", True)
            
            skill_proposal = self.model_adapter.parse_output(raw_output, {
                **context,
                "agent_id": agent_id,
                "agent_type": agent_type
            })
            
            if skill_proposal:
                validation_results = self._run_validators(skill_proposal, validation_context)
                all_validation_history.extend(validation_results)
                all_valid = all(v.valid for v in validation_results)
                if not all_valid:
                    logger.warning(f"[Governance:Retry] Attempt {retry_count} failed validation for {agent_id}. Errors: {[e for v in validation_results for e in v.errors]}")
            else:
                logger.warning(f"[Governance:Retry] Attempt {retry_count} produced unparsable output for {agent_id}.")
        
        if not all_valid and retry_count >= self.max_retries:
             # Building diagnostic info for Fallout
             errors = [e for v in validation_results for e in v.errors]
             logger.error(f"[Governance:Fallout] CRITICAL: Max retries ({self.max_retries}) reached for {agent_id}.")
             logger.error(f"  - Final Choice Rejected: '{skill_proposal.skill_name}'")
             logger.error(f"  - Blocked By: {errors}")
             
             # Show reasoning/ratings for diagnosis
             ratings = []
             for k, v in skill_proposal.reasoning.items():
                 if "_LABEL" in k: ratings.append(f"{k}={v}")
             if ratings: logger.error(f"  - Ratings: {' | '.join(ratings)}")
             
             # Generic Reason Extraction (Look for keys ending in _REASON or naming 'Reason')
             reason_keys = [k for k in skill_proposal.reasoning.keys() if "_REASON" in k.upper() or "REASON" in k.upper()]
             if reason_keys:
                 reason_text = skill_proposal.reasoning.get(reason_keys[0], "")
                 if isinstance(reason_text, dict): 
                     reason_text = reason_text.get("reason", str(reason_text))
                 logger.error(f"  - Agent Motivation: {reason_text}")
             
             # Determine fallout action: prefer original choice if parsed, otherwise default
             fallout_skill = skill_proposal.skill_name if (skill_proposal and skill_proposal.parse_layer != "default") else self.skill_registry.get_default_skill()
             
             logger.error(f"  - Action: Proceeding with '{fallout_skill}' (Result: REJECTED)")

        
        # ④ Create ApprovedSkill or use fallback
        if all_valid:
            approved_skill = ApprovedSkill(
                skill_name=skill_proposal.skill_name,
                agent_id=agent_id,
                approval_status="APPROVED",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(skill_proposal.skill_name) or "",
                parameters={}
            )
            outcome = SkillOutcome.RETRY_SUCCESS if retry_count > 0 else SkillOutcome.APPROVED
            if retry_count > 0:
                self.stats["retry_success"] += 1
                # Final Success Log with Ratings
                ratings = []
                for k, v in skill_proposal.reasoning.items():
                    if "_LABEL" in k: ratings.append(f"{k}={v}")
                rating_str = f" | {' | '.join(ratings)}" if ratings else ""
                logger.warning(f" [Governance:Success] {agent_id} | Fixed after {retry_count} retries | Choice: '{skill_proposal.skill_name}'{rating_str}")
                
                # Log final success for initially hit rules
                for rule_id in initial_rule_ids:
                    self.auditor.log_intervention(rule_id, success=True, is_final=True)
            else:
                self.stats["approved"] += 1
        else:
            # RETRY EXHAUSTION: Return the model's desired behavior but with REJECTED status
            # As requested: "返回原本的行為才對 但是驗證的狀態要是Fail之類的"
            # We use the fallout skill determined above
            is_generic_fallback = (skill_proposal is None or skill_proposal.parse_layer == "default")
            
            # Re-fetch fallout skill if needed or use local var if I can restructure
            fallout_skill = skill_proposal.skill_name if not is_generic_fallback else self.config.get_parsing_config(agent_type).get("default_skill", self.skill_registry.get_default_skill())
            
            approved_skill = ApprovedSkill(
                skill_name=fallout_skill,
                agent_id=agent_id,
                approval_status="REJECTED" if not is_generic_fallback else "REJECTED_FALLBACK",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(fallout_skill) or "",
                parameters={}
            )
            outcome = SkillOutcome.REJECTED if not is_generic_fallback else SkillOutcome.UNCERTAIN
            
            if is_generic_fallback:
                logger.error(f" [Governance:Exhausted] {agent_id} | Parsing failed. Forcing fallback: '{fallout_skill}'")
            else:
                logger.error(f" [Governance:Exhausted] {agent_id} | Retries failed. Proceeding with REJECTED choice: '{fallout_skill}'")


            self.stats["rejected"] += 1
            # Log final failure for the rules that caused fallout
            for v in validation_results:
                for rule_id in v.metadata.get("rules_hit", []):
                    self.auditor.log_intervention(rule_id, success=False, is_final=True)
        
        # FINAL STEP SUMMARY (Console)
        if retry_count > 0:
             pass # Already logged success above
        
        # ⑤ Execution (simulation engine ONLY)
        if self.simulation_engine:
            execution_result = self.simulation_engine.execute_skill(approved_skill)
        else:
            # Standalone mode: Default to pseudo-execution
            execution_result = ExecutionResult(
                success=True,
                state_changes={}
            )
        
        # ⑥ Audit trace
        if self.audit_writer:
            # Robust agent_type extraction (Tiered or Flat)
            agent_type_final = agent_type
            if "personal" in context and isinstance(context["personal"], dict):
                agent_type_final = context["personal"].get("agent_type", agent_type_final)
            elif "agent_type" in context:
                agent_type_final = context.get("agent_type", agent_type_final)
            
            # Extract audit priority fields from config
            log_fields = self.config.get_log_fields(agent_type_final)
            audit_priority = [f"reason_{f.lower()}" for f in log_fields]

            self.audit_writer.write_trace(agent_type_final, {
                "run_id": run_id,
                "step_id": step_id,
                "timestamp": timestamp,
                "seed": seed,
                "agent_id": agent_id,
                "validated": all_valid,
                "_audit_priority": audit_priority, # Dynamically determined from config

                "input": prompt,
                "raw_output": raw_output,
                "context_hash": context_hash,

                "memory_pre": memory_pre,
                "skill_proposal": skill_proposal.to_dict() if skill_proposal else None,
                "approved_skill": {
                    "skill_name": approved_skill.skill_name,
                    "status": approved_skill.approval_status,
                    "mapping": approved_skill.execution_mapping
                } if approved_skill else None,
                "execution_result": execution_result.__dict__ if execution_result else None,
                "outcome": outcome.value,
                "retry_count": retry_count,
                "llm_stats": total_llm_stats  # New: Pass LLM-level stats to trace
            }, all_validation_history)
        
        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=skill_proposal,
            approved_skill=approved_skill,
            execution_result=execution_result,
            validation_errors=[e for v in validation_results for e in v.errors],
            retry_count=retry_count
        )
    
    def _run_validators(self, proposal: SkillProposal, context: Dict) -> List[ValidationResult]:
        """Run all validators on the skill proposal."""
        results = []
        for validator in self.validators:
            result = validator.validate(proposal, context, self.skill_registry)
            if isinstance(result, list):
                results.extend(result)
            else:
                results.append(result)
        return results
    
    def _hash_context(self, context: Dict) -> str:
        """Create hash of context for audit."""
        return hashlib.md5(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:16]
    
    def _create_result(self, outcome, proposal, approved, execution, errors) -> SkillBrokerResult:
        return SkillBrokerResult(
            outcome=outcome,
            skill_proposal=proposal,
            approved_skill=approved,
            execution_result=execution,
            validation_errors=errors,
            retry_count=0
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
