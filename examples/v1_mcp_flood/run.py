"""
Run Flood Adaptation Simulation

Example usage of the Governed Broker Framework for 
PMT-based flood adaptation ABM.
"""
import sys
import json
import argparse
import random
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Framework imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from broker.audit_writer import AuditWriter, AuditConfig
from broker.legacy.types import DecisionRequest, OutcomeType

# Domain imports
from prompts import build_prompt, verbalize_trust
from validators import UnbiasedValidator
from memory import update_memory_after_step, PAST_EVENTS
from trust_update import update_trust_after_step


# =============================================================================
# AGENT & ENVIRONMENT
# =============================================================================

@dataclass
class FloodAgent:
    """Agent in flood adaptation simulation."""
    id: str
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    memory: List[str] = field(default_factory=list)
    trust_in_insurance: float = 0.3
    trust_in_neighbors: float = 0.4
    flood_threshold: float = 0.5
    
    @property
    def is_active(self) -> bool:
        return not self.relocated
    
    def get_options(self) -> Dict[str, str]:
        if self.elevated:
            return {"1": "Buy flood insurance", "2": "Relocate", "3": "Do nothing"}
        return {"1": "Buy flood insurance", "2": "Elevate house", "3": "Relocate", "4": "Do nothing"}


@dataclass
class FloodEnvironment:
    """Environment state."""
    year: int = 0
    flood_event: bool = False
    flood_severity: float = 0.0


# =============================================================================
# SIMULATION ENGINE
# =============================================================================

class FloodSimulation:
    """Flood adaptation simulation engine."""
    
    def __init__(self, num_agents: int = 100, seed: int = 42, flood_years: List[int] = None):
        self.seed = seed
        random.seed(seed)
        
        # Initialize agents
        self.agents: Dict[str, FloodAgent] = {}
        for i in range(1, num_agents + 1):
            self.agents[f"Agent_{i}"] = FloodAgent(
                id=f"Agent_{i}",
                trust_in_insurance=random.uniform(0.2, 0.5),
                trust_in_neighbors=random.uniform(0.3, 0.5),
                flood_threshold=random.uniform(0.3, 0.7)
            )
        
        self.environment = FloodEnvironment()
        self.flood_years = flood_years or [3, 4, 9]  # Default from original
    
    def advance_year(self) -> FloodEnvironment:
        self.environment.year += 1
        self.environment.flood_event = self.environment.year in self.flood_years
        if self.environment.flood_event:
            self.environment.flood_severity = random.uniform(0.5, 1.0)
        return self.environment
    
    def execute_decision(self, agent_id: str, decision: str) -> Dict[str, Any]:
        agent = self.agents.get(agent_id)
        if not agent or agent.relocated:
            return {}
        
        state_changes = {}
        if agent.elevated:
            # Elevated: 1=FI, 2=Relocate, 3=DN
            if decision == "1":
                agent.has_insurance = True
                state_changes["has_insurance"] = True
            else:
                # Reset insurance if not specifically renewed
                agent.has_insurance = False
                state_changes["has_insurance"] = False
                
                if decision == "2":
                    agent.relocated = True
                    state_changes["relocated"] = True
        else:
            # Not elevated: 1=FI, 2=HE, 3=Relocate, 4=DN
            if decision == "1":
                agent.has_insurance = True
                state_changes["has_insurance"] = True
            else:
                # Reset insurance if not specifically renewed
                agent.has_insurance = False
                state_changes["has_insurance"] = False
                
                if decision == "2":
                    agent.elevated = True
                    state_changes["elevated"] = True
                elif decision == "3":
                    agent.relocated = True
                    state_changes["relocated"] = True
        
        return state_changes
    
    def get_community_action_rate(self) -> float:
        total = len(self.agents)
        actions = sum(1 for a in self.agents.values() if a.elevated or a.relocated)
        return actions / total if total > 0 else 0


# =============================================================================
# LLM INTERFACE
# =============================================================================

def create_llm_invoke(model: str):
    """Create LLM invoke function."""
    try:
        from langchain_ollama import ChatOllama
        llm = ChatOllama(model=model, temperature=0.3)
        
        def invoke(prompt: str) -> str:
            response = llm.invoke(prompt)
            return response.content
        
        return invoke
    except ImportError:
        print("Warning: langchain_ollama not installed. Using mock LLM.")
        return lambda p: '{"decision": "4", "threat_appraisal": "Low risk", "coping_appraisal": "Can handle"}'


def parse_llm_output(raw: str, is_elevated: bool) -> Optional[DecisionRequest]:
    """Parse LLM output into structured request."""
    lines = raw.strip().split('\n')
    
    threat = coping = decision = ""
    for line in lines:
        if line.startswith("Threat Appraisal:"):
            threat = line.replace("Threat Appraisal:", "").strip()
        elif line.startswith("Coping Appraisal:"):
            coping = line.replace("Coping Appraisal:", "").strip()
        elif line.startswith("Final Decision:"):
            decision = line.replace("Final Decision:", "").strip()
    
    # Extract decision code
    for char in decision:
        if char.isdigit():
            code = char
            break
    else:
        code = "4" if not is_elevated else "3"  # Default to Do Nothing
    
    return DecisionRequest(
        action_code=code,
        reasoning={"threat": threat, "coping": coping},
        raw_output=raw
    )


# =============================================================================
# MAIN
# =============================================================================

def run_experiment(args):
    """Run the flood adaptation experiment."""
    print("=" * 60)
    print("Governed Broker Framework - Flood Adaptation")
    print("=" * 60)
    print(f"Model: {args.model}")
    print(f"Agents: {args.num_agents}, Years: {args.num_years}")
    print("=" * 60)
    
    # Initialize
    sim = FloodSimulation(num_agents=args.num_agents, seed=args.seed)
    llm_invoke = create_llm_invoke(args.model)
    validator = UnbiasedValidator()
    
    # Audit
    output_dir = Path(args.output_dir) / args.model.replace(":", "_")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    audit = AuditWriter(AuditConfig(output_dir=str(output_dir), log_level="full"))
    
    run_id = f"flood_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    step_counter = 0
    logs = []
    
    # Main loop
    for year in range(1, args.num_years + 1):
        env = sim.advance_year()
        print(f"\n--- Year {year} ---")
        if env.flood_event:
            print("🌊 FLOOD EVENT!")
        
        active_agents = [a for a in sim.agents.values() if a.is_active]
        
        for agent in active_agents:
            step_counter += 1
            
            # Build context
            agent_state = {
                "elevated": agent.elevated,
                "has_insurance": agent.has_insurance,
                "trust_in_insurance": agent.trust_in_insurance,
                "trust_in_neighbors": agent.trust_in_neighbors,
                "memory": agent.memory
            }
            
            env_state = {
                "flood_event": env.flood_event,
                "year": env.year
            }
            
            memory_pre = agent.memory.copy()
            
            # Get LLM decision
            prompt = build_prompt(agent_state, env_state)
            raw_output = llm_invoke(prompt)
            request = parse_llm_output(raw_output, agent.elevated)
            
            # Validate
            context = {
                "is_elevated": agent.elevated,
                "flood_status": "Flood occurred" if env.flood_event else "No flood"
            }
            result = validator.validate(request, context)
            
            # Retry if needed
            retry_count = 0
            while not result.valid and retry_count < 2:
                retry_count += 1
                raw_output = llm_invoke(prompt)
                request = parse_llm_output(raw_output, agent.elevated)
                result = validator.validate(request, context)
            
            # Determine outcome
            if result.valid:
                outcome = OutcomeType.RETRY_SUCCESS if retry_count > 0 else OutcomeType.EXECUTED
            else:
                outcome = OutcomeType.UNCERTAIN
                request.action_code = "4" if not agent.elevated else "3"
            
            # Execute
            state_changes = sim.execute_decision(agent.id, request.action_code)
            
            # Update trust
            flooded = env.flood_event and not agent.elevated and random.random() < agent.flood_threshold
            trust_changes = update_trust_after_step(
                {"trust_in_insurance": agent.trust_in_insurance, "trust_in_neighbors": agent.trust_in_neighbors, "has_insurance": agent.has_insurance},
                flooded,
                sim.get_community_action_rate()
            )
            agent.trust_in_insurance = trust_changes["trust_in_insurance"]
            agent.trust_in_neighbors = trust_changes["trust_in_neighbors"]
            
            # Update memory
            agent.memory = update_memory_after_step(agent.memory, year, env.flood_event, request.action_code, args.seed + step_counter)
            
            # Log
            logs.append({
                "agent_id": agent.id,
                "year": year,
                "decision": request.action_code,
                "outcome": outcome.value
            })
            
            # Audit
            audit.write_trace({
                "run_id": run_id,
                "step_id": step_counter,
                "agent_id": agent.id,
                "year": year,
                "memory_pre": memory_pre,
                "llm_output": request.to_dict(),
                "validator_results": [{"valid": result.valid, "errors": result.errors}],
                "outcome": outcome.value,
                "retry_count": retry_count
            })
    
    # Finalize
    summary = audit.finalize()
    
    print("\n" + "=" * 60)
    print("EXPERIMENT COMPLETE")
    print("=" * 60)
    print(f"Total decisions: {summary['total_steps']}")
    print(f"Executed: {summary['executed']}")
    print(f"Retry Success: {summary['retry_success']}")
    print(f"Uncertain: {summary['uncertain']}")
    print(f"Consistency: {summary['consistency_rate']}")
    
    # Save logs
    import pandas as pd
    pd.DataFrame(logs).to_csv(output_dir / "simulation_log.csv", index=False)
    print(f"\nResults saved to: {output_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Flood Adaptation ABM")
    parser.add_argument("--model", default="llama3.2:3b", help="LLM model")
    parser.add_argument("--num-agents", type=int, default=100)
    parser.add_argument("--num-years", type=int, default=10)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", default="output")
    
    args = parser.parse_args()
    run_experiment(args)
