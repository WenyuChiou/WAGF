"""
Flood-Specific Context Builder.

Extends TieredContextBuilder with flood domain verbalization and skill filtering.
"""
from typing import Dict, Any
from broker.components.context_builder import TieredContextBuilder


def _get_flood_ext(profile):
    """Get flood extension from agent profile."""
    return getattr(profile, "extensions", {}).get("flood")


def _ext_value(ext, key, default=None):
    """Safely get value from extension dict or object."""
    if ext is None:
        return default
    if isinstance(ext, dict):
        return ext.get(key, default)
    return getattr(ext, key, default)


class FloodContextBuilder(TieredContextBuilder):
    """
    Context builder specialized for flood adaptation experiments.

    Features:
    - Verbalizes trust values into natural language
    - Filters skills based on agent state (e.g., no elevate if already elevated)
    - Formats memory for prompt compatibility
    - Generates dynamic skill maps for parser
    """

    def __init__(self, *args, sim=None, memory_top_k: int = 5, **kwargs):
        super().__init__(*args, **kwargs)
        self.sim = sim
        self.memory_top_k = memory_top_k

    def _verbalize_trust(self, trust_value: float, category: str = "insurance") -> str:
        """Convert numeric trust to natural language."""
        if category == "insurance":
            if trust_value >= 0.8:
                return "strongly trust"
            elif trust_value >= 0.5:
                return "moderately trust"
            elif trust_value >= 0.2:
                return "have slight doubts about"
            else:
                return "deeply distrust"
        elif category == "neighbors":
            if trust_value >= 0.8:
                return "highly rely on"
            elif trust_value >= 0.5:
                return "generally trust"
            elif trust_value >= 0.2:
                return "are skeptical of"
            else:
                return "completely ignore"
        return "trust"

    def build(self, agent_id: str, **kwargs) -> Dict[str, Any]:
        """Build context with flood-specific enhancements."""
        agent = self.agents[agent_id]

        # Retrieve memories with world state for surprise engine
        if hasattr(self.hub, 'memory_engine') and self.hub.memory_engine:
            current_depth = _ext_value(
                _get_flood_ext(agent), 'base_depth_m', 0.0
            ) if self.sim.flood_event else 0.0
            world_state = {"flood_depth": current_depth}

            personal_memory = self.hub.memory_engine.retrieve(
                agent,
                top_k=self.memory_top_k,
                world_state=world_state
            )
        else:
            personal_memory = []

        # Get base context
        context = super().build(agent_id, **kwargs)
        personal = context.get('personal', {})
        personal['memory'] = personal_memory

        # Extract live agent state
        elevated = getattr(agent, 'elevated', False)
        has_insurance = getattr(agent, 'has_insurance', False)
        trust_ins = getattr(agent, 'trust_in_insurance', 0.5)
        trust_nb = getattr(agent, 'trust_in_neighbors', 0.5)

        # Inject verbalized variables
        personal['elevation_status_text'] = (
            "Your house is already elevated, which provides very good protection."
            if elevated else "You have not elevated your home."
        )
        personal['insurance_status'] = "have" if has_insurance else "do not have"
        personal['trust_insurance_text'] = self._verbalize_trust(trust_ins, "insurance")
        personal['trust_neighbors_text'] = self._verbalize_trust(trust_nb, "neighbors")

        # Filter available skills
        available_skills = context.get('available_skills', [])
        filtered_skills = []
        for s in available_skills:
            skill_id = s.get('skill_name') if isinstance(s, dict) else s
            if skill_id == "elevate_house" and elevated:
                continue
            filtered_skills.append(s)
        context['available_skills'] = filtered_skills

        # Format memory for prompt
        mem_val = personal.get('memory', [])
        if isinstance(mem_val, dict):
            lines = []
            if mem_val.get("core"):
                core_str = " ".join([f"{k}={v}" for k, v in mem_val["core"].items()])
                lines.append(f"CORE: {core_str}")
            if mem_val.get("semantic"):
                lines.append("HISTORIC:")
                lines.extend([f"  - {m}" for m in mem_val["semantic"]])
            if mem_val.get("episodic"):
                lines.append("RECENT:")
                lines.extend([f"  - {m}" for m in mem_val["episodic"]])
            personal['memory'] = "\n".join(lines) if lines else "No memory available"
        elif isinstance(mem_val, list):
            personal['memory'] = "\n".join([f"- {m}" for m in mem_val])

        # Generate options text and skill map
        dynamic_skill_map = {}
        if elevated:
            personal['options_text'] = (
                "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                "2. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                "3. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
            )
            personal['valid_choices_text'] = "1, 2, or 3"
            dynamic_skill_map = {
                "1": "buy_insurance",
                "2": "relocate",
                "3": "do_nothing"
            }
        else:
            personal['options_text'] = (
                "1. Buy flood insurance (Lower cost, provides partial financial protection but does not reduce physical damage.)\n"
                "2. Elevate your house (High upfront cost but can prevent most physical damage.)\n"
                "3. Relocate (Requires leaving your neighborhood but eliminates flood risk permanently.)\n"
                "4. Do nothing (Require no financial investment or effort this year, but it might leave you exposed to future flood damage.)"
            )
            personal['valid_choices_text'] = "1, 2, 3, or 4"
            dynamic_skill_map = {
                "1": "buy_insurance",
                "2": "elevate_house",
                "3": "relocate",
                "4": "do_nothing"
            }

        personal['skills'] = personal['options_text']
        personal['dynamic_skill_map'] = dynamic_skill_map
        context["skill_variant"] = "elevated" if elevated else "non_elevated"

        return context
