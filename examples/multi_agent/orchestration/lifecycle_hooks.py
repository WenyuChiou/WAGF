from typing import Dict, Any, Optional

from cognitive_governance.agents import BaseAgent
from broker import MemoryEngine
from examples.multi_agent.environment.hazard import HazardModule, VulnerabilityModule, YearMapping
from components.media_channels import MediaHub
from orchestration.disaster_sim import depth_to_qualitative_description
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
    ):
        self.env = environment
        self.memory_engine = memory_engine
        self.hazard = hazard_module or HazardModule()
        self.vuln = VulnerabilityModule()
        self.media_hub = media_hub
        self.per_agent_depth = per_agent_depth
        self.year_mapping = year_mapping or YearMapping()
        self.agent_flood_depths: Dict[str, float] = {}

        # NEW: Initialize game_master, message_pool, and memory_bridge
        self.game_master = game_master
        self.message_pool = message_pool
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
    def post_year(self, year, agents, memory_engine):
        """Apply damage and consolidation."""
        if not self.env["flood_occurred"]:
            return

        community_depth_ft = self.env.get("flood_depth_ft", 0.0)
        if community_depth_ft <= 0 and not self.agent_flood_depths:
            return

        total_damage = 0
        flooded_agents = 0

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

        if self.per_agent_depth:
            print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f} ({flooded_agents} households flooded)")
        else:
            print(f" [YEAR-END] Total Community Damage: ${total_damage:,.0f}")
