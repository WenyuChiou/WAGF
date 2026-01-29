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

from providers.llm_provider import LLMProvider, LLMResponse
from ..interfaces.skill_types import SkillProposal
from .model_adapter import UnifiedAdapter


class AsyncModelAdapter:
    """
    Asynchronous model adapter for concurrent LLM processing.
    
    Wraps LLMProvider and UnifiedAdapter to provide async parsing/formatting.
    NO domain logic should exist here.
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        agent_type: str,
        preprocessor: Optional[Callable[[str], str]] = None,
        config_path: str = None
    ):
        """
        Initialize async adapter.

        Args:
            provider: LLM provider
            agent_type: Type of agent for parsing config (e.g., "household", "trader").
                        Required - must match a type defined in agent_types.yaml.
            preprocessor: Optional preprocessor
            config_path: Path to agent_types.yaml
        """
        self.provider = provider
        # Use UnifiedAdapter internally for parsing logic
        self.inner_adapter = UnifiedAdapter(
            agent_type=agent_type,
            preprocessor=preprocessor,
            config_path=config_path
        )
    
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
        Delegates to UnifiedAdapter.parse_output.
        """
        # Parsing is typically CPU bound and string manipulation, can run in thread if needed
        # but for now we call it directly as it's efficient.
        return self.inner_adapter.parse_output(raw_output, context)
    
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
        """Format retry prompt via inner adapter."""
        return self.inner_adapter.format_retry_prompt(original_prompt, errors)


async def run_batch_agents(
    adapter: AsyncModelAdapter,
    agent_data: List[Dict[str, Any]],
    prompt_builder: Callable[[Dict], str],
    max_concurrent: int = 5
) -> List[SkillProposal]:
    """
    Convenience function to run batch agent processing.
    """
    prompts = [prompt_builder(data) for data in agent_data]
    contexts = [{"agent_id": data.get("agent_id", f"agent_{i}")} for i, data in enumerate(agent_data)]
    
    return await adapter.batch_invoke(prompts, contexts, max_concurrent)
