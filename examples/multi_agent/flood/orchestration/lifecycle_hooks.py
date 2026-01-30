from typing import Dict, Any, Optional
import logging

from cognitive_governance.agents import BaseAgent
from broker import MemoryEngine
from examples.multi_agent.flood.environment.hazard import HazardModule, VulnerabilityModule, YearMapping
from examples.multi_agent.flood.components.media_channels import MediaHub
from examples.multi_agent.flood.orchestration.disaster_sim import depth_to_qualitative_description
from broker.components.memory_bridge import MemoryBridge # Added import


class MultiAgentHooks:
    def __init__(
        self,
        environment: Dict,
        memory_engine: Optional[MemoryEngine] = None,
        hazard_module: Optional[HazardModule] = None,
        media_hub: Optional[MediaHub] = None,
        per_agent_depth: bool = False,
        year_mapping: Optional[YearMapping] = None,
        # NEW parameters:
        game_master: Optional[Any] = None,       # GameMaster instance
        message_pool: Optional[Any] = None,      # MessagePool instance
        drift_detector: Optional[Any] = None,
    ):
        self.env = environment
        self.memory_engine = memory_engine
        self.hazard = hazard_module or HazardModule()
        self.vuln = VulnerabilityModule()
        self.media_hub = media_hub
        self.per_agent_depth = per_agent_depth
        self.year_mapping = year_mapping or YearMapping()
        self.agent_flood_depths: Dict[str, float] = {}
        # Default env keys for test safety when caller doesn't prepopulate.
        self.env.setdefault("flood_occurred", True)
        self.env.setdefault("crisis_event", self.env.get("flood_occurred", False))
        self.env.setdefault(
            "crisis_boosters",
            {"emotion:fear": 1.5} if self.env.get("flood_occurred") else {}
        )

        # NEW: Initialize game_master, message_pool, and memory_bridge
        self.game_master = game_master
        self.message_pool = message_pool
        self.drift_detector = drift_detector
        self._memory_bridge = MemoryBridge(memory_engine) if memory_engine else None

    def pre_year(self, year, env, agents):
        """Randomly determine if flood occurs and resolve pending actions."""
        self.env["year"] = year

        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"]:
                continue
            pending = agent.dynamic_state.get("pending_action")
            completion_year = agent.dynamic_state.get("action_completion_year")

            if pending and completion_year and year >= completion_year:
                if pending == "elevation":
                    agent.dynamic_state["elevated"] = True
                    print(f" [LIFECYCLE] {agent.id} elevation COMPLETE.")
                elif pending == "buyout":
                    agent.dynamic_state["relocated"] = True
                    print(f" [LIFECYCLE] {agent.id} buyout FINALIZED (left community).")
                agent.dynamic_state["pending_action"] = None
                agent.dynamic_state["action_completion_year"] = None

        if self.per_agent_depth:
            households = [a for a in agents.values() if a.agent_type in ["household_owner", "household_renter"]]
            agent_positions = {}
            for agent in households:
                fixed = agent.fixed_attributes or {}
                grid_x = fixed.get("grid_x", 0)
                grid_y = fixed.get("grid_y", 0)
                agent_positions[agent.id] = (grid_x, grid_y)

            flood_events = self.hazard.get_flood_events_for_agents(
                sim_year=year,
                agent_positions=agent_positions,
                year_mapping=self.year_mapping
            )
            self.agent_flood_depths = {aid: ev.depth_m for aid, ev in flood_events.items()}

            max_depth_m = max(self.agent_flood_depths.values()) if self.agent_flood_depths else 0.0
            avg_depth_m = sum(self.agent_flood_depths.values()) / len(self.agent_flood_depths) if self.agent_flood_depths else 0.0
            flooded_count = sum(1 for d in self.agent_flood_depths.values() if d > 0)

            self.env["flood_occurred"] = max_depth_m > 0
            self.env["flood_depth_m"] = round(max_depth_m, 3)
            self.env["flood_depth_ft"] = round(max_depth_m * 3.28084, 3)
            self.env["avg_flood_depth_m"] = round(avg_depth_m, 3)
            self.env["flooded_household_count"] = flooded_count
            self.env["crisis_event"] = self.env["flood_occurred"]
            self.env["crisis_boosters"] = {"emotion:fear": 1.5} if self.env["flood_occurred"] else {}

            if self.env["flood_occurred"]:
                print(
                    f" [ENV] !!! FLOOD WARNING for Year {year} !!! max_depth={max_depth_m:.2f}m, avg={avg_depth_m:.2f}m, flooded={flooded_count}/{len(households)}"
                )
            else:
                print(f" [ENV] Year {year}: No flood events.")
        else:
            event = self.hazard.get_flood_event(year=year)
            self.env["flood_occurred"] = event.depth_m > 0
            self.env["flood_depth_m"] = round(event.depth_m, 3)
            self.env["flood_depth_ft"] = round(event.depth_ft, 3)
            self.agent_flood_depths = {}
            self.env["crisis_event"] = self.env["flood_occurred"]
            self.env["crisis_boosters"] = {"emotion:fear": 1.5} if self.env["flood_occurred"] else {}

            if self.env["flood_occurred"]:
                print(f" [ENV] !!! FLOOD WARNING for Year {year} !!! depth={event.depth_m:.2f}m")
            else:
                print(f" [ENV] Year {year}: No flood events.")

        if self.media_hub and self.env["flood_occurred"]:
            self.media_hub.broadcast_event({
                "flood_occurred": True,
                "flood_depth_m": self.env["flood_depth_m"],
                "affected_households": self.env.get("flooded_household_count", "multiple"),
            }, year)

        households = [a for a in agents.values() if a.agent_type in ["household_owner", "household_renter"]]
        self.env["total_households"] = len(households)
        self.env["elevated_count"] = sum(1 for a in households if a.dynamic_state.get("elevated"))
        self.env["insured_count"] = sum(1 for a in households if a.dynamic_state.get("has_insurance"))

    def post_step(self, agent, result):
        """Update global vars if institutional agent acted."""
        if result.outcome.name != "SUCCESS":
            return

        decision = result.skill_proposal.skill_name

        if agent.agent_type == "government":
            current = self.env["subsidy_rate"]
            if decision == "increase_subsidy":
                self.env["subsidy_rate"] = min(0.95, current + 0.05)
                self.env["govt_message"] = "The government has INCREASED the adaptation subsidy to support your safety."
            elif decision == "decrease_subsidy":
                self.env["subsidy_rate"] = max(0.20, current - 0.05)
                self.env["govt_message"] = "The government has DECREASED the subsidy due to budget constraints."
            else:
                self.env["govt_message"] = "The government is MAINTAINING the current subsidy rate."

        elif agent.agent_type == "insurance":
            current = self.env["premium_rate"]
            if decision == "raise_premium":
                self.env["premium_rate"] = min(0.15, current + 0.005)
                self.env["insurance_message"] = "Insurance premiums have been RAISED to ensure program solvency."
            elif decision == "lower_premium":
                self.env["premium_rate"] = max(0.01, current - 0.005)
                self.env["insurance_message"] = "Insurance premiums have been LOWERED due to favorable market conditions."
            else:
                self.env["insurance_message"] = "Insurance premiums remain UNCHANGED for now."

        elif agent.agent_type in ["household_owner", "household_renter"]:
            current_year = self.env.get("year", 1)

            if decision in ["buy_insurance", "buy_contents_insurance"]:
                agent.dynamic_state["has_insurance"] = True
            elif decision == "elevate_house":
                agent.dynamic_state["pending_action"] = "elevation"
                agent.dynamic_state["action_completion_year"] = current_year + 1
                print(f" [LIFECYCLE] {agent.id} started elevation (completes Year {current_year + 1})")
                agent.dynamic_state["pending_action"] = "buyout"
                agent.dynamic_state["action_completion_year"] = current_year + 2
                print(f" [LIFECYCLE] {agent.id} applied for buyout (finalizes Year {current_year + 2})")

            if result.skill_proposal and result.skill_proposal.reasoning:
                reason = result.skill_proposal.reasoning.get("reasoning", "")
                if not reason:
                    reason_key = next((k for k in result.skill_proposal.reasoning.keys() if "reason" in k.lower()), None)
                    reason = result.skill_proposal.reasoning.get(reason_key, "") if reason_key else ""

                if reason:
                    mem_engine = getattr(self, 'memory_engine', None)
                    if mem_engine:
                        mem_engine.add_memory(
                            agent.id,
                            f"I decided to {decision} because {reason}",
                            metadata={"source": "social", "type": "reasoning"}
                        )

            # Store GameMaster resolution as memory (if available)
            if self._memory_bridge and self.game_master:
                resolution = self.game_master.get_resolution(agent.id)
                if resolution:
                    self._memory_bridge.store_resolution(resolution, year=self.env.get("year", 0))

        # Drift detection (per-step)
        if self.drift_detector:
            decision_label = None
            if isinstance(result, dict):
                decision_label = result.get("skill") or result.get("decision")
                tp_label = result.get("TP_LABEL", "")
                cp_label = result.get("CP_LABEL", "")
            else:
                if getattr(result, "skill_proposal", None):
                    decision_label = getattr(result.skill_proposal, "skill_name", None)
                tp_label = getattr(result, "TP_LABEL", "")
                cp_label = getattr(result, "CP_LABEL", "")

            constructs = {"tp": tp_label, "cp": cp_label}
            if decision_label:
                self.drift_detector.record_agent_decision(agent.id, decision_label, constructs)
    def post_year(self, year, agents, memory_engine):
        """Apply damage and consolidation."""
        flood_occurred = self.env.get("flood_occurred", False)
        community_depth_ft = self.env.get("flood_depth_ft", 0.0)
        if not flood_occurred:
            community_depth_ft = 0.0

        total_damage = 0
        flooded_agents = 0

        if community_depth_ft > 0 or self.agent_flood_depths:
            for agent in agents.values():
                if agent.agent_type not in ["household_owner", "household_renter"] or agent.dynamic_state.get("relocated"):
                    continue

                if self.per_agent_depth and agent.id in self.agent_flood_depths:
                    depth_m = self.agent_flood_depths[agent.id]
                    depth_ft = depth_m * 3.28084
                else:
                    depth_ft = community_depth_ft
                    depth_m = depth_ft / 3.28084

                if depth_ft <= 0:
                    continue

                flooded_agents += 1
                rcv_building = agent.fixed_attributes["rcv_building"]
                rcv_contents = agent.fixed_attributes["rcv_contents"]
                damage_res = self.vuln.calculate_damage(
                    depth_ft=depth_ft,
                    rcv_building=rcv_building,
                    rcv_contents=rcv_contents,
                    is_elevated=agent.dynamic_state["elevated"],
                )
                damage = damage_res["total_damage"]

                agent.dynamic_state["cumulative_damage"] += damage
                total_damage += damage

                description = depth_to_qualitative_description(depth_ft)
                memory_engine.add_memory(
                    agent.id,
                    f"Year {year}: We experienced {description} which caused about ${damage:,.0f} in damages.",
                    metadata={"emotion": "fear", "source": "personal", "importance": 0.8}
                )

        # Store important messages as memories
        if self._memory_bridge and self.message_pool:
            for agent_id in agents:
                unread = self.message_pool.get_unread(agent_id)
                if unread:
                    self._memory_bridge.store_unread_messages(
                        agent_id, unread, year=year, max_store=3
                    )

        if community_depth_ft > 0 or self.agent_flood_depths:
            if self.per_agent_depth:
                print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f} ({flooded_agents} households flooded)")
            else:
                print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f}")

        # --- SC/PA Trust Re-derivation (Task-060C) ---
        for agent in agents.values():
            if agent.agent_type not in ["household_owner", "household_renter"]:
                continue
            fixed_attr = getattr(agent, "fixed_attributes", None)
            fixed = fixed_attr if isinstance(fixed_attr, dict) else {}
            sc_raw = fixed.get("sc_score", 3.0)
            pa_raw = fixed.get("pa_score", 3.0)
            try:
                sc = float(sc_raw)
            except (TypeError, ValueError):
                sc = 3.0
            try:
                pa = float(pa_raw)
            except (TypeError, ValueError):
                pa = 3.0
            sc_norm = min(1.0, sc / 5.0)
            pa_norm = min(1.0, pa / 5.0)
            ins_factor = 1.2 if agent.dynamic_state.get("has_insurance") else 0.8
            agent.dynamic_state["trust_in_neighbors"] = round(sc_norm, 3)
            agent.dynamic_state["trust_in_insurance"] = round(min(1.0, sc_norm * ins_factor), 3)
            agent.dynamic_state["community_rootedness"] = round(pa_norm, 3)

        # --- MA Reflection Integration (Task-057D) ---
        if self._memory_bridge and self.memory_engine:
            crisis_event = self.env.get("crisis_event", flood_occurred)
            if not flood_occurred:
                crisis_event = False
            # Trigger reflection at the end of the year, especially if there was a crisis
            if crisis_event or year % 5 == 0:
                for agent in agents.values():
                    if agent.agent_type in ["household_owner", "household_renter"]:
                        self._run_ma_reflection(agent.id, year, agents, self.memory_engine, flood_occurred)

                # Government/Insurance reflection (institutional trigger)
                from broker.components.reflection_engine import ReflectionEngine, ReflectionTrigger
                reflection_engine = ReflectionEngine()
                for agent in agents.values():
                    if getattr(agent, "agent_type", "") in ("government", "insurance"):
                        base_type = "government" if "government" in agent.agent_type else "insurance"
                        memories = (
                            memory_engine.retrieve(agent, top_k=5)
                            if hasattr(memory_engine, "retrieve")
                            else []
                        )
                        if not isinstance(memories, list):
                            memories = []
                        if memories:
                            context = ReflectionEngine.extract_agent_context(agent, year)
                            prompt = reflection_engine.generate_personalized_reflection_prompt(
                                context, memories, year
                            )
                            insight = reflection_engine.parse_reflection_response(
                                f"As a {base_type} agent, I observe: " + "; ".join(memories[:2]),
                                len(memories),
                                year,
                            )
                            if insight:
                                reflection_engine.store_insight(str(agent.unique_id), insight)
                                memory_engine.add_memory(
                                    str(agent.unique_id),
                                    f"[Reflection Y{year}] {insight.summary}",
                                    {"importance": insight.importance, "type": "reflection", "source": "reflection"},
                                )
        # --- End MA Reflection Integration ---

        # --- Echo Chamber Audit (Task-060E) ---
        if self.game_master and getattr(self.game_master, 'cross_validator', None):
            import math
            skill_counts = {}
            for agent in agents.values():
                if agent.agent_type in ["household_owner", "household_renter"]:
                    decision = agent.dynamic_state.get("last_decision", "do_nothing")
                    skill_counts[decision] = skill_counts.get(decision, 0) + 1
            total = sum(skill_counts.values())
            if total > 0:
                entropy = -sum((c / total) * math.log2(c / total) for c in skill_counts.values() if c > 0)
                logging.info(f"[Diversity:Year{year}] Entropy: {entropy:.3f} bits, Dist: {skill_counts}")
                self.env["decision_entropy"] = round(entropy, 3)
                self.env["decision_distribution"] = skill_counts

        # Drift detection (population)
        if self.drift_detector:
            decisions = {}
            agent_types = {}
            for agent_id, agent in agents.items():
                if getattr(agent, "relocated", False):
                    continue
                if agent.dynamic_state.get("relocated", False):
                    continue
                decisions[agent_id] = getattr(agent, "last_decision", "do_nothing")
                agent_types[agent_id] = getattr(agent, "agent_type", "household")

            self.drift_detector.record_population_snapshot(year, decisions, agent_types)
            alerts = self.drift_detector.get_alerts(year)
            for alert in alerts:
                logging.warning(f"[Drift:{alert.category}] {alert.message}")

    def _run_ma_reflection(
        self,
        agent_id: str,
        year: int,
        agents: Dict[str, BaseAgent],
        memory_engine: MemoryEngine,
        flood_occurred: bool,
    ):
        """Orchestrates the MA reflection process for a given agent."""
        
        # Define allocation for stratified retrieval (can be customized)
        # This ensures a mix of memory types are considered for reflection.
        retrieval_allocation = {
            "personal": 1,
            "neighbor": 1,
            "reflection": 3,
        }
        total_k = 5
        
        # Retrieve memories using stratified approach
        # Use context boosters if available (e.g., crisis emotion)
        stratified_memories = memory_engine.retrieve_stratified(
            agent_id,
            allocation=retrieval_allocation,
            total_k=total_k, # Retrieve up to 5 memories for reflection context
            contextual_boosters=self.env.get("crisis_boosters") if flood_occurred else None
        )

        if not stratified_memories:
            return # No memories to reflect on

        # --- Construct Reflection Prompt (Simplified) ---
        # In a full implementation, this would use LLM prompts and potentially 057-A's personalized prompts.
        # For now, we'll create a basic reflection summary.
        
        reflection_prompt = f"Reflecting on Year {year} for agent {agent_id}:\n"
        reflection_prompt += "Key events and context:\n"
        for i, mem in enumerate(stratified_memories[:3]): # Use top 3 memories for summary
            reflection_prompt += f"- {mem}\n"
        
        reflection_prompt += "\nBased on this context, what are the most important lessons learned or insights gained for the future?"
        
        # --- Generate Reflection Memory ---
        # In a real scenario, an LLM would generate the reflection content.
        # For now, we simulate by creating a generic reflection based on the prompt structure.
        generated_reflection = f"Year {year}: Consolidated Reflection: Learned valuable lessons from past events and community inputs. Importance of preparedness highlighted."

        # Add the generated reflection as a new memory
        memory_engine.add_memory(
            agent_id,
            generated_reflection,
            metadata={
                "source": "personal", # Reflections are personal insights derived from various sources
                "emotion": "major",   # Reflections often carry significant emotional weight
                "importance": 0.85,   # Reflections are typically important for future decisions
                "type": "reflection", # Explicitly mark as reflection
                "context": "year_end_review"
            }
        )
        print(f" [REFLECTION] Agent {agent_id} generated a year-end reflection.")

