from typing import Dict, Any, List, Optional
from broker.context_builder import BaseAgentContextBuilder, load_prompt_templates

class Exp3ContextBuilder(BaseAgentContextBuilder):
    """
    Experiment 3 specific ContextBuilder.
    
    Adds domain-specific logic for:
    - Deriving Subsidy Perception (SP) from raw subsidy rates
    - Formatting specific environment signals for Exp3 agents
    """
    
    def build(
        self, 
        agent_id: str,
        observable: Optional[List[str]] = None,
        include_memory: bool = True,
        include_raw: bool = False
    ) -> Dict[str, Any]:
        """
        Build context and inject experiment-specific derived metrics.
        """
        # 1. Get base context (Standard State, Perception, Memory)
        ctx = super().build(
            agent_id, 
            observable=observable, 
            include_memory=include_memory, 
            include_raw=include_raw
        )
        
        # 2. Inject Experiment-Specific Derived Metrics
        # This encapsulates the "Business Logic" of how agents view this specific world
        if self.environment:
            # Subsidy Perception (SP) Calculation
            # Logic: High subsidy (>0.7) -> High Perception
            sub_rate = self.environment.get("subsidy_rate", 0.0)
            
            if sub_rate >= 0.7:
                sp_level = "H"
            elif sub_rate >= 0.4:
                sp_level = "M"
            else:
                sp_level = "L"
                
            ctx["sp"] = sp_level
            
            # 3. Inject Skill Mapping Variant
            # This allows UnifiedAdapter to pick the correct digit mapping (1, 2, 3...)
            # without hardcoding tenure/elevation into the core framework.
            agent_obj = self.agents.get(agent_id)
            is_elevated = ctx.get("is_elevated", False)
            tenure = getattr(agent_obj.state, 'tenure', None) if agent_obj else None
            
            if tenure == "Renter":
                ctx["skill_variant"] = "renter"
            elif is_elevated:
                ctx["skill_variant"] = "elevated"
            else:
                ctx["skill_variant"] = "non_elevated"

            # Flood signal formatting 
            if self.environment.get("flood") == "YES":
                ctx["flood_warning"] = "ACTIVE"
            else:
                ctx["flood_warning"] = "NONE"

        return ctx

def create_exp3_context_builder(
    agents: Dict[str, Any],
    environment: Dict[str, float] = None,
    custom_templates: Dict[str, str] = None,
    load_yaml: bool = True,
    yaml_path: str = None
) -> Exp3ContextBuilder:
    """
    Factory to create Exp3ContextBuilder with templates loaded.
    """
    templates = {}
    if load_yaml:
        templates = load_prompt_templates(yaml_path)
    
    if custom_templates:
        templates.update(custom_templates)
        
    return Exp3ContextBuilder(
        agents=agents,
        environment=environment,
        prompt_templates=templates
    )
