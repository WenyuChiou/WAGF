"""
Replay Engine - Replay runs from audit trace.

Enables deterministic reproduction of past simulations.
"""
import json
from pathlib import Path
from typing import Dict, Any, Optional


class ReplayEngine:
    """
    Replays a simulation run from audit traces.
    
    Usage:
    ```python
    replay = ReplayEngine("audit_output/audit_trace.jsonl")
    final_state = replay.run()
    assert final_state == expected_state
    ```
    """
    
    def __init__(self, audit_path: str, simulation_engine: Any = None):
        self.audit_path = Path(audit_path)
        self.simulation_engine = simulation_engine
        self.traces = []
        
        self._load_traces()
    
    def _load_traces(self) -> None:
        """Load audit traces from JSONL file."""
        if not self.audit_path.exists():
            raise FileNotFoundError(f"Audit file not found: {self.audit_path}")
        
        with open(self.audit_path, 'r', encoding='utf-8') as f:
            for line in f:
                self.traces.append(json.loads(line))
        
        print(f"Loaded {len(self.traces)} audit traces")
    
    def get_run_info(self) -> Dict[str, Any]:
        """Get information about the recorded run."""
        if not self.traces:
            return {}
        
        first = self.traces[0]
        last = self.traces[-1]
        
        return {
            "run_id": first.get("run_id"),
            "seed": first.get("seed"),
            "total_steps": len(self.traces),
            "first_timestamp": first.get("timestamp"),
            "last_timestamp": last.get("timestamp"),
            "agents": list(set(t.get("agent_id") for t in self.traces))
        }
    
    def replay_step(self, step_index: int) -> Dict[str, Any]:
        """Replay a single step from the trace."""
        if step_index >= len(self.traces):
            raise IndexError(f"Step {step_index} out of range")
        
        trace = self.traces[step_index]
        
        # Get the recorded action
        action_request = trace.get("action_request")
        admissible_command = trace.get("admissible_command")
        
        if self.simulation_engine and admissible_command:
            # Re-execute using the recorded command
            from interfaces.execution_interface import AdmissibleCommand
            
            cmd = AdmissibleCommand(
                agent_id=admissible_command["agent_id"],
                action_name=admissible_command["action_name"],
                parameters=admissible_command.get("parameters", {}),
                admissibility_check=admissible_command.get("admissibility_check", "PASSED")
            )
            
            result = self.simulation_engine.execute(cmd)
            
            return {
                "step": step_index,
                "agent_id": trace["agent_id"],
                "action": action_request,
                "execution_result": result.__dict__,
                "expected_result": trace.get("execution_result"),
                "match": result.__dict__ == trace.get("execution_result")
            }
        
        return {
            "step": step_index,
            "trace": trace
        }
    
    def run(self) -> Dict[str, Any]:
        """Run full replay and return final state."""
        results = []
        mismatches = 0
        
        for i, trace in enumerate(self.traces):
            result = self.replay_step(i)
            results.append(result)
            
            if not result.get("match", True):
                mismatches += 1
        
        final_state = None
        if self.simulation_engine:
            final_state = {
                agent_id: self.simulation_engine.get_agent_state(agent_id)
                for agent_id in self.simulation_engine.agents
            }
        
        return {
            "total_steps": len(results),
            "mismatches": mismatches,
            "replay_success": mismatches == 0,
            "final_state": final_state
        }
    
    def verify_determinism(self, expected_final_state_path: str) -> bool:
        """Verify replay produces same final state."""
        with open(expected_final_state_path, 'r') as f:
            expected = json.load(f)
        
        result = self.run()
        
        return result["final_state"] == expected.get("agents")
