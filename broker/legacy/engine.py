"""
Broker Engine - Main orchestrator for governance layer.

Implements the 6-step decision lifecycle:
① Signal Read (bounded context)
② LLM Output (structured JSON)
③ Governance Validation
④ Action Request (intent only)
⑤ Admissibility Check
⑥ Execution (simulation engine only)
"""
from typing import Callable, Dict, List, Optional, Any
from datetime import datetime
import hashlib
import json

from .types import (
    DecisionRequest, ValidationResult, ActionRequest, 
    AdmissibleCommand, ExecutionResult, BrokerResult, OutcomeType
)
# Shared components from parent broker package
from broker.context_builder import ContextBuilder
from broker.audit_writer import AuditWriter


class BrokerEngine:
    """
    Central governance engine.
    
    The Broker MUST NOT:
    - Make decisions (LLM does this)
    - Mutate state directly (Simulation Engine does this)
    - Execute actions (Simulation Engine does this)
    
    The Broker MUST:
    - Build bounded context
    - Validate LLM outputs
    - Route to appropriate interfaces
    - Write audit traces
    - Handle retry/UNCERTAIN policy
    """
    
    def __init__(
        self,
        context_builder: ContextBuilder,
        llm_invoke: Callable[[str], str],
        validators: List[Any],
        simulation_engine: Any,
        audit_writer: Optional[AuditWriter] = None,
        max_retries: int = 2,
        uncertain_fallback: str = "do_nothing"
    ):
        self.context_builder = context_builder
        self.llm_invoke = llm_invoke
        self.validators = validators
        self.simulation_engine = simulation_engine
        self.audit_writer = audit_writer
        self.max_retries = max_retries
        self.uncertain_fallback = uncertain_fallback
        
        # Statistics
        self.stats = {
            "total": 0,
            "executed": 0,
            "retry_success": 0,
            "uncertain": 0,
            "aborted": 0
        }
    
    def process_step(
        self,
        agent_id: str,
        step_id: int,
        run_id: str,
        seed: int
    ) -> BrokerResult:
        """
        Process one complete decision step through the 6-stage lifecycle.
        """
        self.stats["total"] += 1
        timestamp = datetime.now().isoformat()
        
        # ① Build bounded context (READ-ONLY)
        context = self.context_builder.build(agent_id)
        context_hash = self._hash_context(context)
        memory_pre = context.get("memory", []).copy()
        
        # ② LLM structured output
        prompt = self.context_builder.format_prompt(context)
        raw_output = self.llm_invoke(prompt)
        decision_request = self._parse_llm_output(raw_output)
        
        if decision_request is None:
            self.stats["aborted"] += 1
            return self._create_result(OutcomeType.ABORTED, None, None, None, ["Parse error"])
        
        # ③ Governance validation
        validation_results = self._run_validators(decision_request, context)
        all_valid = all(v.valid for v in validation_results)
        
        retry_count = 0
        while not all_valid and retry_count < self.max_retries:
            retry_count += 1
            errors = [e for v in validation_results for e in v.errors]
            retry_prompt = self._create_retry_prompt(prompt, errors)
            raw_output = self.llm_invoke(retry_prompt)
            decision_request = self._parse_llm_output(raw_output)
            if decision_request:
                validation_results = self._run_validators(decision_request, context)
                all_valid = all(v.valid for v in validation_results)
        
        # Handle failed validation
        if not all_valid:
            self.stats["uncertain"] += 1
            # Use fallback action
            action_request = ActionRequest(
                agent_id=agent_id,
                action_name=self.uncertain_fallback,
                parameters={}
            )
            outcome = OutcomeType.UNCERTAIN
        else:
            # ④ Create action request (intent only)
            action_request = ActionRequest(
                agent_id=agent_id,
                action_name=self._map_action(decision_request.action_code, context),
                parameters={}
            )
            outcome = OutcomeType.RETRY_SUCCESS if retry_count > 0 else OutcomeType.EXECUTED
            if retry_count > 0:
                self.stats["retry_success"] += 1
            else:
                self.stats["executed"] += 1
        
        # ⑤ Admissibility check (simulation engine)
        admissible_command = self.simulation_engine.check_admissibility(action_request)
        
        # ⑥ Execution (simulation engine ONLY)
        execution_result = None
        if admissible_command and admissible_command.admissibility_check == "PASSED":
            execution_result = self.simulation_engine.execute(admissible_command)
        
        # Get memory after execution
        memory_post = self.context_builder.get_memory(agent_id)
        
        # Write audit trace
        if self.audit_writer:
            self.audit_writer.write_trace({
                "run_id": run_id,
                "step_id": step_id,
                "timestamp": timestamp,
                "seed": seed,
                "agent_id": agent_id,
                "context_hash": context_hash,
                "memory_pre": memory_pre,
                "llm_output": decision_request.to_dict() if decision_request else None,
                "validator_results": [{"valid": v.valid, "errors": v.errors} for v in validation_results],
                "action_request": action_request.__dict__ if action_request else None,
                "admissible_command": admissible_command.__dict__ if admissible_command else None,
                "execution_result": execution_result.__dict__ if execution_result else None,
                "memory_post": memory_post,
                "outcome": outcome.value,
                "retry_count": retry_count
            })
        
        return BrokerResult(
            outcome=outcome,
            action_request=action_request,
            admissible_command=admissible_command,
            execution_result=execution_result,
            validation_errors=[e for v in validation_results for e in v.errors],
            retry_count=retry_count
        )
    
    def _parse_llm_output(self, raw: str) -> Optional[DecisionRequest]:
        """Parse LLM output into structured request."""
        # This should be overridden by domain-specific parser
        # Default: expect JSON
        try:
            data = json.loads(raw)
            return DecisionRequest(
                action_code=str(data.get("decision", "")),
                reasoning={
                    "threat": data.get("threat_appraisal", ""),
                    "coping": data.get("coping_appraisal", "")
                },
                raw_output=raw
            )
        except:
            # Fallback to text parsing
            return None
    
    def _run_validators(self, request: DecisionRequest, context: Dict) -> List[ValidationResult]:
        """Run all validators on the request."""
        results = []
        for validator in self.validators:
            result = validator.validate(request, context)
            results.append(result)
        return results
    
    def _create_retry_prompt(self, original: str, errors: List[str]) -> str:
        """Create retry prompt with validation feedback."""
        return f"""Your previous response was flagged:
{', '.join(errors)}

Please reconsider and respond again.

{original}"""
    
    def _map_action(self, code: str, context: Dict) -> str:
        """Map action code to action name (domain-specific)."""
        # Override in domain implementation
        return f"action_{code}"
    
    def _hash_context(self, context: Dict) -> str:
        """Create hash of context for audit."""
        return hashlib.md5(json.dumps(context, sort_keys=True, default=str).encode()).hexdigest()[:16]
    
    def _create_result(self, outcome, action_request, admissible, execution, errors) -> BrokerResult:
        return BrokerResult(
            outcome=outcome,
            action_request=action_request,
            admissible_command=admissible,
            execution_result=execution,
            validation_errors=errors,
            retry_count=0
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get broker statistics."""
        total = self.stats["total"]
        return {
            **self.stats,
            "consistency_rate": f"{self.stats['executed']/total*100:.1f}%" if total > 0 else "N/A"
        }
