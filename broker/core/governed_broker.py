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
from ..utils.logging import logger

from ..interfaces.skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill, 
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from ..components.skill_registry import SkillRegistry
from ..utils.model_adapter import ModelAdapter
from ..utils.llm_utils import get_llm_stats
from ..validators import AgentValidator
from ..interfaces.skill_types import ValidationResult


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
        audit_writer: Optional[Any] = None,
        max_retries: int = 2,
        log_prompt: bool = False
    ):
        self.skill_registry = skill_registry
        self.model_adapter = model_adapter
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.context_builder = context_builder
        self.audit_writer = audit_writer
        self.max_retries = max_retries
        self.log_prompt = log_prompt
        logger.debug("!!! HELLO FROM BROKER !!!")
        
        # Statistics
        self.stats = {
            "total": 0,
            "approved": 0,
            "retry_success": 0,
            "rejected": 0,
            "aborted": 0
        }
    
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
        logger.debug(f"DEBUG_BROKER: Processing {agent_id} with builder {type(self.context_builder)} instance {id(self.context_builder)}")
        context = self.context_builder.build(agent_id)
        context_hash = self._hash_context(context)
        
        # Robust memory extraction for audit (handles nesting and stringification)
        raw_mem = context.get("memory")
        if raw_mem is None and "personal" in context:
            raw_mem = context["personal"].get("memory")
            
        if isinstance(raw_mem, str):
            # Convert bulleted string back to list for cleaner JSON logs
            memory_pre = [m.lstrip("- ").strip() for m in raw_mem.split("\n") if m.strip()]
        else:
            memory_pre = list(raw_mem).copy() if raw_mem else []
        
        # ② LLM output → Parsing (with retry support)
        prompt = self.context_builder.format_prompt(context)
        raw_output = llm_invoke(prompt)
        
        # Handle legacy returns (stats)
        if isinstance(raw_output, tuple):
            raw_output, _ = raw_output
            
        parse_ctx = {
            "agent_id": agent_id,
            "agent_type": agent_type,
            **context
        }
        skill_proposal = self.model_adapter.parse_output(raw_output, parse_ctx)

        # ③ Retry Loop (Handles BOTH Parsing Errors and Validation Violations)
        retry_count = 0
        validation_context = {
            "agent_state": context,
            "agent_type": agent_type
        }
        for k, v in context.items():
            if k.endswith("_event") or k.endswith("_occurred"):
                validation_context[k] = v

        while retry_count < self.max_retries:
            # Case A: Parsing Failed
            if skill_proposal is None:
                retry_count += 1
                logger.warning(f" [Broker:Retry] Parse failure for {agent_id}. Retrying {retry_count}/{self.max_retries}...")
                retry_prompt = self.model_adapter.format_retry_prompt(prompt, ["Failed to parse decision. Please ensure you use the exact required JSON or Marker format."])
                raw_output = llm_invoke(retry_prompt)
                if isinstance(raw_output, tuple): raw_output = raw_output[0]
                skill_proposal = self.model_adapter.parse_output(raw_output, parse_ctx)
                continue # Re-evaluate the new proposal
            
            # Case B: Proposal exists, run validators
            validation_results = self._run_validators(skill_proposal, validation_context)
            if all(v.valid for v in validation_results):
                break # Success!
                
            # Case C: Validation Failed
            retry_count += 1
            logger.warning(f" [Broker:Retry] Validation failure for {agent_id}. Retrying {retry_count}/{self.max_retries}...")
            errors = [e for v in validation_results for e in v.errors]
            retry_prompt = self.model_adapter.format_retry_prompt(prompt, errors)
            raw_output = llm_invoke(retry_prompt)
            if isinstance(raw_output, tuple): raw_output = raw_output[0]
            skill_proposal = self.model_adapter.parse_output(raw_output, parse_ctx)

        # ④ Final Check after Loop
        if skill_proposal is None:
            self.stats["aborted"] += 1
            logger.error(f" [Adapter:Error] Failed to parse proposal for {agent_id} after {retry_count} retries.")
            return self._create_result(SkillOutcome.ABORTED, None, None, None, ["Persistent parse error"])

        validation_results = self._run_validators(skill_proposal, validation_context)
        all_valid = all(v.valid for v in validation_results)
        
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
            else:
                self.stats["approved"] += 1
            
            # Show any warnings
            warnings = [w for v in validation_results for w in v.warnings]
            if warnings:
                msg = "; ".join(warnings)
                logger.warning(f" [Governance:Warning] {agent_id}: {msg}")
        else:
            # Use fallback skill
            fallback = self.skill_registry.get_default_skill()
            errors = [e for v in validation_results for e in v.errors]
            msg = "; ".join(errors)
            logger.warning(f" [Governance:Intervention] {agent_id}: Decision '{skill_proposal.skill_name}' REJECTED by logic rules. FALLBACK: {fallback}")
            logger.warning(f"  - Reasons: {msg}")
            
            approved_skill = ApprovedSkill(
                skill_name=fallback,
                agent_id=agent_id,
                approval_status="REJECTED_FALLBACK",
                validation_results=validation_results,
                execution_mapping=self.skill_registry.get_execution_mapping(fallback) or "",
                parameters={}
            )
            outcome = SkillOutcome.UNCERTAIN
            self.stats["rejected"] += 1
            
        logger.info(f" [Broker:Final] Agent {agent_id}: {approved_skill.skill_name} ({approved_skill.approval_status})")

        # ⑤ Execution (simulation engine ONLY)
        execution_result = self.simulation_engine.execute_skill(approved_skill)
        
        # ⑥ Audit trace
        if self.audit_writer:
            agent_type = context.get("agent_type", "default")
            self.audit_writer.write_trace(agent_type, {
                "run_id": run_id,
                "step_id": step_id,
                "timestamp": timestamp,
                "seed": seed,
                "agent_id": agent_id,
                "input": prompt if self.log_prompt else None,
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
                "llm_retries": get_llm_stats().get("current_retries", 0),
                "llm_success": get_llm_stats().get("current_success", True)
            }, validation_results)
        
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
