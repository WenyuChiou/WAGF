"""
Flood Experiment Lifecycle Hooks.

Handles pre_year, post_step, post_year logic for flood simulation.
"""
import random
import pandas as pd
from pathlib import Path
from typing import Dict, Any, List, Optional

from .simulation import classify_adaptation_state

# Research Constants
RANDOM_MEMORY_RECALL_CHANCE = 0.2
PAST_EVENTS = [
    "A flood event about 15 years ago caused $500,000 in city-wide damages; my neighborhood was not impacted at all",
    "Some residents reported delays when processing their flood insurance claims",
    "A few households in the area elevated their homes before recent floods",
    "The city previously introduced a program offering elevation support to residents",
    "News outlets have reported a possible trend of increasing flood frequency and severity in recent years"
]


class FloodHooks:
    """
    Lifecycle hooks for flood adaptation experiment.

    Manages:
    - pre_year: Flood events, memories, social observation
    - post_step: State changes, decision logging
    - post_year: Trust updates, reflection, logging
    """

    def __init__(
        self,
        sim,
        runner,
        reflection_engine=None,
        output_dir=None
    ):
        self.sim = sim
        self.runner = runner
        self.reflection_engine = reflection_engine
        self.logs = []
        self.yearly_decisions = {}
        self.output_dir = Path(output_dir) if output_dir else Path(".")

    def pre_year(self, year: int, env, agents: Dict[str, Any]):
        """Pre-year hook: determine flood, add memories."""
        # Advance simulation
        self.sim.advance_year()
        flood_event = self.sim.flood_event

        # Calculate global stats
        active_agents = [a for a in self.sim.agents.values() if not getattr(a, 'relocated', False)]
        total_elevated = sum(1 for a in active_agents if getattr(a, 'elevated', False))
        total_relocated = len(self.sim.agents) - len(active_agents)

        for agent in self.sim.agents.values():
            if getattr(agent, 'relocated', False):
                if len(agent.flood_history) < year:
                    agent.flood_history.append(False)
                continue

            flooded = False
            if flood_event:
                if not getattr(agent, 'elevated', False):
                    if random.random() < getattr(agent, 'flood_threshold', 0.3):
                        flooded = True
                        mem = f"Year {year}: Got flooded with $10,000 damage on my house."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was spared damage."
                else:
                    if random.random() < getattr(agent, 'flood_threshold', 0.3):
                        flooded = True
                        mem = f"Year {year}: Despite elevation, the flood was severe enough to cause damage."
                    else:
                        mem = f"Year {year}: A flood occurred, but my house was protected by its elevation."
            else:
                mem = f"Year {year}: No flood occurred this year."

            agent.flood_history.append(flooded)
            yearly_memories = [mem]

            # Grant memory
            if self.sim.grant_available:
                yearly_memories.append(f"Year {year}: Elevation grants are available.")

            # Social observation
            num_others = len(self.sim.agents) - 1
            if num_others > 0:
                elev_pct = round(((total_elevated - (1 if getattr(agent, 'elevated', False) else 0)) / num_others) * 100)
                reloc_pct = round((total_relocated / num_others) * 100)
                yearly_memories.append(
                    f"Year {year}: I observe {elev_pct}% of neighbors elevated and {reloc_pct}% relocated."
                )

            # Stochastic recall
            if random.random() < RANDOM_MEMORY_RECALL_CHANCE:
                yearly_memories.append(f"Suddenly recalled: '{random.choice(PAST_EVENTS)}'.")

            # Add consolidated memory
            consolidated_mem = " | ".join(yearly_memories)
            if hasattr(self.runner, 'memory_engine') and self.runner.memory_engine:
                self.runner.memory_engine.add_memory(agent.id, consolidated_mem)

    def post_step(self, agent, result):
        """Post-step hook: log decision, apply state changes."""
        year = self.sim.current_year
        skill_name = None
        appraisals = {}

        if result and result.skill_proposal and result.skill_proposal.reasoning:
            reasoning = result.skill_proposal.reasoning
            for key in ["threat_appraisal", "THREAT_APPRAISAL_LABEL", "threat"]:
                if key in reasoning:
                    appraisals["threat_appraisal"] = reasoning[key]
                    break
            for key in ["coping_appraisal", "COPING_APPRAISAL_LABEL", "coping"]:
                if key in reasoning:
                    appraisals["coping_appraisal"] = reasoning[key]
                    break

        if result and result.approved_skill:
            skill_name = result.approved_skill.skill_name

        self.yearly_decisions[(agent.id, year)] = {
            "skill": skill_name,
            "appraisals": appraisals
        }

        # Apply state changes
        if result and hasattr(result, 'state_changes') and result.state_changes:
            agent.apply_delta(result.state_changes)

        # Update flood threshold on elevation
        if result and result.approved_skill and result.approved_skill.skill_name == "elevate_house":
            agent.flood_threshold = max(0.001, round(getattr(agent, 'flood_threshold', 0.3) * 0.2, 2))

    def post_year(self, year: int, agents: Dict[str, Any]):
        """Post-year hook: update trust, reflection, logging."""
        total_elevated = sum(1 for a in agents.values() if getattr(a, 'elevated', False))
        total_relocated = sum(1 for a in agents.values() if getattr(a, 'relocated', False))
        community_action_rate = (total_elevated + total_relocated) / len(agents)

        for agent in agents.values():
            if not getattr(agent, 'relocated', False):
                # Trust updates
                last_flood = agent.flood_history[-1] if agent.flood_history else False
                has_ins = getattr(agent, 'has_insurance', False)
                trust_ins = getattr(agent, 'trust_in_insurance', 0.5)

                if has_ins:
                    trust_ins += (-0.10 if last_flood else 0.02)
                else:
                    trust_ins += (0.05 if last_flood else -0.02)
                agent.trust_in_insurance = max(0.0, min(1.0, trust_ins))

                trust_nb = getattr(agent, 'trust_in_neighbors', 0.5)
                if community_action_rate > 0.30:
                    trust_nb += 0.04
                elif last_flood and community_action_rate < 0.10:
                    trust_nb -= 0.05
                else:
                    trust_nb -= 0.01
                agent.trust_in_neighbors = max(0.0, min(1.0, trust_nb))

            # Log entry
            mem_items = []
            if hasattr(self.runner, 'memory_engine') and self.runner.memory_engine:
                mem_items = self.runner.memory_engine.retrieve(agent, top_k=5)
            mem_str = " | ".join(mem_items) if mem_items else ""

            decision_data = self.yearly_decisions.get((agent.id, year), {})
            yearly_decision = decision_data.get("skill") if isinstance(decision_data, dict) else decision_data
            appraisals = decision_data.get("appraisals", {}) if isinstance(decision_data, dict) else {}

            if yearly_decision is None and getattr(agent, "relocated", False):
                yearly_decision = "relocated"

            self.logs.append({
                "agent_id": agent.id,
                "year": year,
                "cumulative_state": classify_adaptation_state(agent),
                "yearly_decision": yearly_decision or "N/A",
                "threat_appraisal": appraisals.get("threat_appraisal", "N/A"),
                "coping_appraisal": appraisals.get("coping_appraisal", "N/A"),
                "elevated": getattr(agent, 'elevated', False),
                "has_insurance": getattr(agent, 'has_insurance', False),
                "relocated": getattr(agent, 'relocated', False),
                "trust_insurance": getattr(agent, 'trust_in_insurance', 0),
                "trust_neighbors": getattr(agent, 'trust_in_neighbors', 0),
                "memory": mem_str
            })

        # Print stats
        df_year = pd.DataFrame([l for l in self.logs if l['year'] == year])
        if not df_year.empty:
            stats = df_year['cumulative_state'].value_counts()
            categories = [
                "Do Nothing", "Only Flood Insurance", "Only House Elevation",
                "Both Flood Insurance and House Elevation", "Relocate"
            ]
            stats_str = " | ".join([f"{cat}: {stats.get(cat, 0)}" for cat in categories])
            print(f"[Year {year}] Stats: {stats_str}")
            print(f"[Year {year}] Avg Trust: Ins={df_year['trust_insurance'].mean():.3f}, Nb={df_year['trust_neighbors'].mean():.3f}")

        # Batch reflection (if enabled)
        if self.reflection_engine and self.reflection_engine.should_reflect("any", year):
            self._run_batch_reflection(year)

    def _run_batch_reflection(self, year: int):
        """Run batch reflection for all agents."""
        if not hasattr(self.runner, 'broker') or not self.runner.broker:
            return

        refl_cfg = self.runner.broker.config.get_reflection_config()
        batch_size = refl_cfg.get("batch_size", 10)

        candidates = []
        for agent_id, agent in self.sim.agents.items():
            if getattr(agent, "relocated", False):
                continue
            if hasattr(self.runner, 'memory_engine') and self.runner.memory_engine:
                memories = self.runner.memory_engine.retrieve(agent, top_k=10)
                if memories:
                    candidates.append({"agent_id": agent_id, "memories": memories})

        if not candidates:
            return

        print(f" [Reflection:Batch] Processing {len(candidates)} agents in batches of {batch_size}...")
        llm_call = self.runner.get_llm_invoke("household")

        for i in range(0, len(candidates), batch_size):
            batch = candidates[i:i+batch_size]
            batch_ids = [c["agent_id"] for c in batch]
            prompt = self.reflection_engine.generate_batch_reflection_prompt(batch, year)

            try:
                raw_res = llm_call(prompt)
                response_text = raw_res[0] if isinstance(raw_res, tuple) else raw_res

                insights = self.reflection_engine.parse_batch_reflection_response(response_text, batch_ids, year)
                for agent_id, insight in insights.items():
                    if insight:
                        self.reflection_engine.store_insight(agent_id, insight)
                        self.runner.memory_engine.add_memory(
                            agent_id,
                            f"Consolidated Reflection: {insight.summary}",
                            {"significance": 0.9, "emotion": "major", "source": "personal"}
                        )
            except Exception as e:
                print(f" [Reflection:Batch:Error] Batch {i//batch_size+1} failed: {e}")

        print(f" [Reflection:Batch] Completed reflection for Year {year}.")
