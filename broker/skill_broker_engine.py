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

from .skill_types import (
    SkillProposal, SkillDefinition, ApprovedSkill, 
    ExecutionResult, SkillBrokerResult, SkillOutcome, ValidationResult
)
from .skill_registry import SkillRegistry
from .model_adapter import ModelAdapter
from validators.skill_validators import SkillValidator


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
        validators: List[SkillValidator],
        simulation_engine: Any,
        context_builder: Any,
        audit_writer: Optional[Any] = None,
        max_retries: int = 2
    ):
        self.skill_registry = skill_registry
        self.model_adapter = model_adapter
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.context_builder = context_builder
        self.audit_writer = audit_writer
        self.max_retries = max_retries
        
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
        agent_type: str = "default"
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
        context = self.context_builder.build(agent_id)
        context_hash = self._hash_context(context)
        memory_pre = context.get("memory", []).copy() if context.get("memory") else []
        
        # ② LLM output → ModelAdapter → SkillProposal
        prompt = self.context_builder.format_prompt(context)
        raw_output = llm_invoke(prompt)
        
        skill_proposal = self.model_adapter.parse_output(raw_output, context)
        
        if skill_proposal is None:
            self.stats["aborted"] += 1
            return self._create_result(SkillOutcome.ABORTED, None, None, None, ["Parse error"])
        
        # ③ Skill validation
        validation_context = {
            "agent_state": context,
            "agent_type": agent_type
        }
        
        validation_results = self._run_validators(skill_proposal, validation_context)
        all_valid = all(v.valid for v in validation_results)
        
        # Retry loop
        retry_count = 0
        while not all_valid and retry_count < self.max_retries:
            retry_count += 1
            errors = [e for v in validation_results for e in v.errors]
            retry_prompt = self.model_adapter.format_retry_prompt(prompt, errors)
            raw_output = llm_invoke(retry_prompt)
            
            skill_proposal = self.model_adapter.parse_output(raw_output, context)
            
            if skill_proposal:
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
        else:
            # Use fallback skill
            fallback = self.skill_registry.get_default_skill()
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
        
        # ⑤ Execution (simulation engine ONLY)
        execution_result = self.simulation_engine.execute_skill(approved_skill)
        
        # ⑥ Audit trace
        if self.audit_writer:
            self.audit_writer.write_trace({
                "run_id": run_id,
                "step_id": step_id,
                "timestamp": timestamp,
                "seed": seed,
                "agent_id": agent_id,
                "context_hash": context_hash,
                "memory_pre": memory_pre,
                "skill_proposal": skill_proposal.to_dict() if skill_proposal else None,
                "validator_results": [
                    {"validator": v.validator_name, "valid": v.valid, "errors": v.errors}
                    for v in validation_results
                ],
                "approved_skill": {
                    "skill_name": approved_skill.skill_name,
                    "status": approved_skill.approval_status,
                    "mapping": approved_skill.execution_mapping
                } if approved_skill else None,
                "execution_result": execution_result.__dict__ if execution_result else None,
                "outcome": outcome.value,
                "retry_count": retry_count
            })
        
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
