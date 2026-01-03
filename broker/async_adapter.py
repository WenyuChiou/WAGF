"""
Async Adapter - Asynchronous model adapter methods.

Provides async versions of model adapter operations for:
- Concurrent agent processing
- Non-blocking I/O during LLM calls
- Better throughput in batch scenarios
"""
import asyncio
from typing import Dict, Any, Optional, List, Callable
import re

from interfaces.llm_provider import LLMProvider, LLMResponse
from .skill_types import SkillProposal


class AsyncModelAdapter:
    """
    Asynchronous model adapter for concurrent LLM processing.
    
    Wraps LLMProvider and provides async parsing/formatting.
    
    Usage:
        provider = OllamaProvider(config)
        adapter = AsyncModelAdapter(provider)
        
        # Single agent
        proposal = await adapter.parse_output_async(raw_output, context)
        
        # Batch processing
        proposals = await adapter.batch_invoke(prompts, contexts)
    """
    
    DEFAULT_VALID_SKILLS = {"buy_insurance", "elevate_house", "relocate", "do_nothing"}
    
    SKILL_MAP_NON_ELEVATED = {
        "1": "buy_insurance",
        "2": "elevate_house",
        "3": "relocate",
        "4": "do_nothing"
    }
    
    SKILL_MAP_ELEVATED = {
        "1": "buy_insurance",
        "2": "relocate",
        "3": "do_nothing"
    }
    
    def __init__(
        self,
        provider: LLMProvider,
        preprocessor: Optional[Callable[[str], str]] = None,
        valid_skills: Optional[set] = None
    ):
        self.provider = provider
        self.preprocessor = preprocessor or (lambda x: x)
        self.valid_skills = valid_skills or self.DEFAULT_VALID_SKILLS
    
    async def invoke_async(self, prompt: str, **kwargs) -> str:
        """Async invoke LLM and return content."""
        response = await self.provider.ainvoke(prompt, **kwargs)
        return response.content
    
    async def parse_output_async(
        self,
        raw_output: str,
        context: Dict[str, Any]
    ) -> Optional[SkillProposal]:
        """
        Async parse LLM output into SkillProposal.
        
        Same logic as sync version but runs in async context.
        """
        # Preprocessing is sync (just string manipulation)
        cleaned_output = self.preprocessor(raw_output)
        
        agent_id = context.get("agent_id", "unknown")
        is_elevated = context.get("is_elevated", False)
        
        # Extract reasoning
        threat_appraisal = ""
        coping_appraisal = ""
        skill_name = None
        
        lines = cleaned_output.strip().split('\n')
        for line in lines:
            line = line.strip()
            
            if line.lower().startswith("skill:") or (line.lower().startswith("decision:") and not skill_name):
                decision_text = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                for skill in self.valid_skills:
                    if skill in decision_text:
                        skill_name = skill
                        break
            
            elif line.lower().startswith("threat appraisal:"):
                threat_appraisal = line.split(":", 1)[1].strip() if ":" in line else ""
            elif line.lower().startswith("coping appraisal:"):
                coping_appraisal = line.split(":", 1)[1].strip() if ":" in line else ""
            
            elif line.lower().startswith("final decision:") and not skill_name:
                decision_text = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                
                for skill in self.valid_skills:
                    if skill in decision_text:
                        skill_name = skill
                        break
                
                if not skill_name:
                    for char in decision_text:
                        if char.isdigit():
                            skill_map = self.SKILL_MAP_ELEVATED if is_elevated else self.SKILL_MAP_NON_ELEVATED
                            skill_name = skill_map.get(char, "do_nothing")
                            break
        
        if not skill_name:
            skill_name = "do_nothing"
        
        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            reasoning={
                "threat": threat_appraisal,
                "coping": coping_appraisal
            },
            confidence=1.0,
            raw_output=raw_output
        )
    
    async def batch_invoke(
        self,
        prompts: List[str],
        contexts: List[Dict[str, Any]],
        max_concurrent: int = 5
    ) -> List[SkillProposal]:
        """
        Process multiple agents concurrently.
        
        Args:
            prompts: List of prompts for each agent
            contexts: List of contexts for each agent
            max_concurrent: Maximum concurrent requests
            
        Returns:
            List of SkillProposals in same order as inputs
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_one(prompt: str, context: Dict) -> SkillProposal:
            async with semaphore:
                raw_output = await self.invoke_async(prompt)
                return await self.parse_output_async(raw_output, context)
        
        tasks = [
            process_one(prompt, context)
            for prompt, context in zip(prompts, contexts)
        ]
        
        return await asyncio.gather(*tasks)
    
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """Format retry prompt with validation errors."""
        error_text = ", ".join(errors)
        return f"""Your previous response was flagged for the following issues:
{error_text}

Please reconsider your decision and respond again.

{original_prompt}"""


async def run_batch_agents(
    adapter: AsyncModelAdapter,
    agent_data: List[Dict[str, Any]],
    prompt_builder: Callable[[Dict], str],
    max_concurrent: int = 5
) -> List[SkillProposal]:
    """
    Convenience function to run batch agent processing.
    
    Args:
        adapter: AsyncModelAdapter instance
        agent_data: List of agent state dictionaries
        prompt_builder: Function to build prompt from agent data
        max_concurrent: Max concurrent requests
        
    Returns:
        List of SkillProposals
    """
    prompts = [prompt_builder(data) for data in agent_data]
    contexts = [{"agent_id": data.get("agent_id", f"agent_{i}")} for i, data in enumerate(agent_data)]
    
    return await adapter.batch_invoke(prompts, contexts, max_concurrent)
