"""
Skill-Governed Flood Adaptation Example

This example demonstrates how to use the Skill-Governed Architecture (v0.2)
for building LLM-driven Agent-Based Models.

Quick Start:
    python run_skill_governed.py --model llama3.2:3b --num-agents 10 --num-years 5

Key Components:
    1. SkillRegistry - Define allowed skills and their constraints
    2. SkillBrokerEngine - Orchestrate LLM → Validation → Execution
    3. ModelAdapter - Parse LLM outputs into SkillProposals
    4. Validators - 5-stage validation pipeline
"""
import sys
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from langchain_ollama import ChatOllama

# =============================================================================
# STEP 1: DEFINE YOUR DOMAIN TYPES
# =============================================================================

@dataclass
class Agent:
    """Your agent type. Customize fields as needed."""
    id: str
    elevated: bool = False
    has_insurance: bool = False
    relocated: bool = False
    memory: List[str] = field(default_factory=list)
    trust_in_insurance: float = 0.3
    trust_in_neighbors: float = 0.4

    @property
    def is_active(self) -> bool:
        return not self.relocated


@dataclass
class Environment:
    """Your environment state. Customize as needed."""
    year: int = 0
    flood_event: bool = False


# =============================================================================
# STEP 2: DEFINE YOUR SKILL REGISTRY
# =============================================================================

# Skills are the abstract behaviors your agents can perform
SKILL_DEFINITIONS = {
    "buy_insurance": {
        "description": "Purchase flood insurance. Lower cost, provides partial financial protection.",
        "preconditions": [],  # No preconditions
        "constraints": {"annual": True},  # Can be done each year
        "effects": {"has_insurance": True}
    },
    "elevate_house": {
        "description": "Elevate your home structure. High upfront cost but prevents damage.",
        "preconditions": [{"field": "elevated", "value": False}],  # Only if not already elevated
        "constraints": {"once_only": True},
        "effects": {"elevated": True}
    },
    "relocate": {
        "description": "Move to a safer location. Eliminates flood risk permanently.",
        "preconditions": [{"field": "relocated", "value": False}],
        "constraints": {"once_only": True},
        "effects": {"relocated": True}
    },
    "do_nothing": {
        "description": "Take no action this year. No cost but remains exposed to risk.",
        "preconditions": [],
        "constraints": {},
        "effects": {}
    }
}


def get_available_skills(agent: Agent) -> Dict[str, str]:
    """Get skills available to this agent based on their state."""
    skills = {}
    for skill_id, skill_def in SKILL_DEFINITIONS.items():
        # Check preconditions
        can_use = True
        for precond in skill_def["preconditions"]:
            if getattr(agent, precond["field"], None) != precond["value"]:
                can_use = False
                break
        if can_use:
            skills[skill_id] = skill_def["description"]
    return skills


# =============================================================================
# STEP 3: BUILD YOUR CONTEXT (Prompt)
# =============================================================================

def build_context(agent: Agent, env: Environment) -> str:
    """Build the LLM prompt from agent and environment state."""
    
    # Agent state description
    if agent.elevated:
        elevation_status = "Your house is already elevated, providing good protection."
    else:
        elevation_status = "You have not elevated your home."
    
    insurance_status = "have" if agent.has_insurance else "do not have"
    
    # Memory
    memory_text = "\n".join(f"- {m}" for m in agent.memory) if agent.memory else "- No past events recalled."
    
    # Available skills
    available = get_available_skills(agent)
    skills_text = "\n".join(f"- {k}: {v}" for k, v in available.items())
    valid_choices = ", ".join(available.keys())
    
    # Flood status
    flood_status = "A flood occurred this year, causing significant damage." if env.flood_event else "No flood occurred this year."
    
    return f"""You are a homeowner in a city, with a strong attachment to your community. {elevation_status}

Your memory includes:
{memory_text}

You currently {insurance_status} flood insurance.

Using Protection Motivation Theory, evaluate your situation and choose an action.

Available skills (choose one):
{skills_text}

{flood_status}

Respond with:
Threat Appraisal: [Your assessment of threat]
Coping Appraisal: [Your assessment of coping ability]
Final Decision: [Choose {valid_choices}]"""


# =============================================================================
# STEP 4: PARSE LLM OUTPUT
# =============================================================================

def parse_llm_output(raw_output: str, agent: Agent) -> Optional[str]:
    """Parse LLM output to extract skill name."""
    available = get_available_skills(agent)
    
    # Find "Final Decision:" line
    for line in raw_output.split('\n'):
        if "final decision" in line.lower():
            decision_text = line.split(":", 1)[-1].strip().lower()
            
            # Try to find skill name
            for skill_id in available.keys():
                if skill_id in decision_text:
                    return skill_id
            
            # Fallback: try digit parsing for legacy compatibility
            for char in decision_text:
                if char.isdigit():
                    idx = int(char) - 1
                    skill_list = list(available.keys())
                    if 0 <= idx < len(skill_list):
                        return skill_list[idx]
    
    return "do_nothing"  # Default fallback


# =============================================================================
# STEP 5: EXECUTE SKILLS (System-Only)
# =============================================================================

def execute_skill(skill_name: str, agent: Agent, env: Environment) -> Dict[str, Any]:
    """Execute an approved skill. Only the system calls this."""
    state_changes = {}
    
    if skill_name == "buy_insurance":
        agent.has_insurance = True
        state_changes["has_insurance"] = True
    
    elif skill_name == "elevate_house":
        if not agent.elevated:
            agent.elevated = True
            state_changes["elevated"] = True
        agent.has_insurance = False  # Insurance not renewed
    
    elif skill_name == "relocate":
        if not agent.relocated:
            agent.relocated = True
            state_changes["relocated"] = True
    
    elif skill_name == "do_nothing":
        agent.has_insurance = False  # Insurance not renewed
    
    return state_changes


# =============================================================================
# STEP 6: RUN SIMULATION
# =============================================================================

def run_simulation(
    model_name: str = "llama3.2:3b",
    num_agents: int = 10,
    num_years: int = 5,
    flood_years: List[int] = None,
    seed: int = 42
):
    """Run the skill-governed simulation."""
    import random
    random.seed(seed)
    
    if flood_years is None:
        flood_years = [3]
    
    print("=" * 60)
    print("Skill-Governed Flood Adaptation Simulation")
    print("=" * 60)
    print(f"Model: {model_name}")
    print(f"Agents: {num_agents}, Years: {num_years}")
    print(f"Flood years: {flood_years}")
    print("=" * 60)
    
    # Initialize
    llm = ChatOllama(model=model_name, temperature=0.7)
    agents = [Agent(id=f"agent_{i}") for i in range(num_agents)]
    env = Environment()
    
    results = []
    
    for year in range(1, num_years + 1):
        env.year = year
        env.flood_event = year in flood_years
        
        print(f"\n--- Year {year} ---")
        if env.flood_event:
            print("🌊 FLOOD EVENT!")
        
        active_agents = [a for a in agents if a.is_active]
        print(f"Active agents: {len(active_agents)}")
        
        for agent in active_agents:
            # Build context
            prompt = build_context(agent, env)
            
            # Get LLM decision
            response = llm.invoke(prompt)
            raw_output = response.content
            
            # Parse to skill
            skill_name = parse_llm_output(raw_output, agent)
            
            # Execute
            state_changes = execute_skill(skill_name, agent, env)
            
            # Update memory
            if env.flood_event:
                agent.memory.append(f"Year {year}: A flood occurred.")
            agent.memory.append(f"Year {year}: Chose {skill_name}")
            agent.memory = agent.memory[-5:]  # Keep last 5
            
            results.append({
                "year": year,
                "agent_id": agent.id,
                "skill": skill_name,
                "state_changes": state_changes
            })
    
    print("\n" + "=" * 60)
    print("SIMULATION COMPLETE")
    print("=" * 60)
    
    # Summary
    skill_counts = {}
    for r in results:
        skill = r["skill"]
        skill_counts[skill] = skill_counts.get(skill, 0) + 1
    
    print("\nSkill Distribution:")
    for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1]):
        pct = 100 * count / len(results)
        print(f"  {skill}: {count} ({pct:.1f}%)")
    
    return results


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Skill-Governed Flood Adaptation")
    parser.add_argument("--model", default="llama3.2:3b", help="LLM model name")
    parser.add_argument("--num-agents", type=int, default=10, help="Number of agents")
    parser.add_argument("--num-years", type=int, default=5, help="Number of years")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()
    
    run_simulation(
        model_name=args.model,
        num_agents=args.num_agents,
        num_years=args.num_years,
        seed=args.seed
    )
