"""
Skill Retriever - Implements RAG-based skill selection.

This component selects the most relevant skills for an agent based on its
current context (state, memory, perception) to avoid prompt bloat.
"""
import re
from typing import List, Dict, Any, Optional
from ..interfaces.skill_types import SkillDefinition

class SkillRetriever:
    """
    Retrieves a subset of skills based on their relevance to the current context.
    
    Currently uses a robust keyword-based similarity score.
    Future versions can integrate embeddings for semantic retrieval.
    """
    
    def __init__(self, top_n: int = 5, min_score: float = 0.05, global_skills: Optional[List[str]] = None):
        self.top_n = top_n
        self.min_score = min_score
        self.global_skills = global_skills or ["do_nothing"]
        # Weights for different context sources
        self.source_weights = {
            "state": 1.0,      # Direct internal state (e.g. 'elevated')
            "perception": 1.2, # Immediate external signals (e.g. 'flood_intensity')
            "memory": 0.8      # Historical context
        }

    def retrieve(
        self, 
        query_context: Dict[str, Any], 
        available_skills: List[SkillDefinition]
    ) -> List[SkillDefinition]:
        """
        Select top-N skills relevant to the provided context.
        
        Args:
            query_context: The bounded context built for the agent.
            available_skills: List of skills the agent is eligible to use.
            
        Returns:
            A prioritized list of SkillDefinitions.
        """
        if not available_skills:
            return []
            
        # 1. Extract searchable terms from context
        keywords = self._extract_keywords(query_context)
        
        # 2. Score each skill
        scored_skills = []
        for skill in available_skills:
            score = self._calculate_score(skill, keywords)
            scored_skills.append((score, skill))
            
        # 3. Sort by score
        scored_skills.sort(key=lambda x: x[0], reverse=True)
        
        # 4. Filter and truncate
        # Always include the global skills if they exist in the available set
        top_skills = [s for score, s in scored_skills[:self.top_n] if score >= self.min_score]
        
        # Merge Top-N with Global Skills (avoiding duplicates)
        for gid in self.global_skills:
            g_skill = next((s for s in available_skills if s.skill_id == gid), None)
            if g_skill and g_skill not in top_skills:
                top_skills.append(g_skill)
            
        return top_skills

    def _extract_keywords(self, context: Dict[str, Any]) -> Dict[str, float]:
        """Convert context into a weighted keyword dictionary."""
        keywords = {}
        
        # Process state (e.g. 'elevated': 0.8 -> key 'elevated' weight 0.8)
        state = context.get("state", {})
        for k, v in state.items():
            if isinstance(v, (int, float)):
                keywords[k.lower()] = v * self.source_weights["state"]
            elif isinstance(v, str):
                keywords[v.lower()] = 1.0 * self.source_weights["state"]
                
        # Process perception (e.g. 'flood_intensity': 0.9 -> key 'flood' weight 1.08)
        perception = context.get("perception", {})
        for k, v in perception.items():
            if isinstance(v, (int, float)):
                # Split key name to find tokens like 'flood'
                for part in k.lower().replace('_', ' ').split():
                    keywords[part] = max(keywords.get(part, 0), v * self.source_weights["perception"])

        # Process memory (text search)
        memory = context.get("memory", [])
        mems_to_process = []
        if isinstance(memory, dict):
            # Aggregate all text tiers
            mems_to_process.extend(memory.get("episodic", []))
            mems_to_process.extend(memory.get("semantic", []))
            # Core values can also be keywords
            core = memory.get("core", {})
            for k, v in core.items():
                keywords[str(k).lower()] = keywords.get(str(k).lower(), 0) + 0.5
                keywords[str(v).lower()] = keywords.get(str(v).lower(), 0) + 0.5
        elif isinstance(memory, list):
            mems_to_process = memory

        if mems_to_process:
            mem_text = " ".join(map(str, mems_to_process)).lower()
            tokens = re.findall(r'\b\w{3,}\b', mem_text) # Only words > 2 chars
            for t in tokens:
                keywords[t] = keywords.get(t, 0) + (0.1 * self.source_weights["memory"])

        return keywords

    def _calculate_score(self, skill: SkillDefinition, keywords: Dict[str, float]) -> float:
        """Calculate relevance score for a skill against keywords."""
        score = 0.0
        
        # Search targets: skill_id and description
        search_target = f"{skill.skill_id} {skill.description}".lower().replace('_', ' ')
        
        for k, weight in keywords.items():
            if k in search_target:
                # Direct match weight
                score += weight
                
        # Bonus for exact skill_id match in query (unlikely but possible)
        if skill.skill_id.lower() in keywords:
            score += 2.0
            
        return score
