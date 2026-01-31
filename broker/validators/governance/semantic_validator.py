"""
Semantic Grounding Validator (Task-062)

Validates that agent reasoning is semantically grounded in the simulation state.
Prevents "Hallucinated Consensus" where agents invent social proof to justify actions.
"""

from typing import List, Dict, Any, Optional
from broker.interfaces.skill_types import ValidationResult, SkillProposal
from broker.validators.agent.agent_validator import ValidationLevel

class SemanticGroundingValidator:
    """
    Validates that the agent's reasoning is consistent with the ground truth environment state.
    """
    
    def __init__(self, simulation_engine=None):
        self.simulation_engine = simulation_engine

    def validate(self, proposal: SkillProposal, context: Dict[str, Any], registry=None) -> List[ValidationResult]:
        """
        Main validation entry point.
        Matches signature: (proposal, context, registry) -> List[ValidationResult]
        """
        results = []
        
        # 1. extract relevant data
        agent_id = proposal.agent_id
        decision = proposal.skill_name
        reasoning = proposal.reasoning or {}
        
        # Get ground truth from context
        # context structure: {'env_state': {...}, 'agent_state': {...}, 'social_network': ...}
        env_state = context.get('env_state', {})
        social_context = context.get('social_network', {}) # Heuristic: check specific keys
        
        # 2. Check for Hallucinated Social Proof
        # Rule: If agent claims "neighbors" or "community" influenced them, 
        # but they have NO neighbors or low adoption, flag it.
        
        # 2.1 Detect Social Reasoning
        social_keywords = ["neighbor", "community", "everyone", "others", "block", "street"]
        reasoning_text = str(reasoning).lower()
        has_social_reasoning = any(kw in reasoning_text for kw in social_keywords)
        
        if has_social_reasoning:
            # 2.2 Verify Ground Truth
            # Check interaction_hub or direct graph if available in context
            # In standard context_builder, 'visible_agents' or 'neighborhood' might be present
            # If not directly available, we might need to rely on 'social_context' features
            
            # Feature: neighbor_adoption_rate, neighbor_count
            # Note: The context passed here is the 'validation_context' built in SkillBrokerEngine.
            # In 'process_step', 'validation_context' = context (the full dict).
            
            # Let's look for specific constructs usually in the prompt context
            # The agent sees: "Social Network: You have 0 neighbors."
            
            # Logic: If isolated (Group A), neighbor_count should be 0.
            # We need to find where this info is stored.
            # Usually 'social_network' key in context or 'visible_agents'.
            
            # 2.2 Verify Ground Truth via Context Strings
            # The agent's context (SocialProvider) typically contains a textual description of the neighborhood.
            # We look for "0 neighbors" or "no neighbors" in the 'local' -> 'spatial' section.
            
            local_ctx = context.get('local', {})
            spatial_info = local_ctx.get('spatial', "")
            if isinstance(spatial_info, list):
                spatial_info = " ".join(str(x) for x in spatial_info)
            spatial_text = str(spatial_info).lower()
            
            # Indicators of isolation in the prompt
            is_isolated = "0 neighbors" in spatial_text or "no neighbors" in spatial_text or "alone" in spatial_text
            
            # Specific Check for Group A (Isolation)
            # If context says 0 neighbors, but agent reasoning cites them -> HALLUCINATION
            if is_isolated:
                results.append(ValidationResult(
                    valid=False,
                    validator_name="SemanticGroundingValidator",
                    errors=[f"Hallucinated Social Proof: Agent reasoning cites social influence ('{social_keywords[0]}...') but context confirms 0 neighbors."],
                    metadata={
                        "level": ValidationLevel.ERROR,
                        "rule": "grounding_social_hallucination",
                        "field": "reasoning",
                        "constraint": "cannot cite neighbors when isolated"
                    }
                ))
            
            # 2.3 Check for Consensus Exaggeration (Group B/C)
            # If claiming "everyone" or "high adoption", but actual rate is low.
            # This requires parsing the specific claim, which is hard.
            # For now, we enforce a weaker check: If strictly 0 neighbors adoption, yet claims "neighbors are doing X".
            
            # TODO: Improve with actual adoption rate check if available in context.
            
        return results
