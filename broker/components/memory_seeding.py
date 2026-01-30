from typing import Dict
import logging

from cognitive_governance.agents import BaseAgent
from broker.components.memory_engine import MemoryEngine

logger = logging.getLogger(__name__)

def seed_memory_from_agents(memory_engine: MemoryEngine, agents: Dict[str, BaseAgent], overwrite: bool = False) -> None:
    """
    Seed memory engine storage from agent.profile memory lists.

    This avoids lazy-only initialization and provides a consistent startup path.
    """
    if not memory_engine or not agents:
        return

    seeded = getattr(memory_engine, "_seeded_agents", set())
    if not isinstance(seeded, set):
        seeded = set()

    def has_existing_memory(agent_id: str) -> bool:
        for attr in ("storage", "working", "longterm", "episodic", "semantic"):
            buf = getattr(memory_engine, attr, None)
            if isinstance(buf, dict) and buf.get(agent_id):
                return True
        return False

    for agent in agents.values():
        agent_id = getattr(agent, "id", None) or getattr(agent, "name", None)
        if not agent_id:
            continue
        if not overwrite and agent_id in seeded:
            continue
        if not overwrite and has_existing_memory(agent_id):
            seeded.add(agent_id)
            continue

        initial_mem = getattr(agent, "memory", None)
        if initial_mem is None:
            continue
        if not isinstance(initial_mem, list):
            logger.warning(f"[Memory:Warning] Agent {agent_id} memory not list; skipping seed.")
            continue
        if not initial_mem:
            continue

        for mem in initial_mem:
            if hasattr(memory_engine, "add_memory_for_agent"):
                try:
                    memory_engine.add_memory_for_agent(agent, mem)
                except TypeError:
                    memory_engine.add_memory(agent_id, mem)
            else:
                memory_engine.add_memory(agent_id, mem)

        seeded.add(agent_id)

    setattr(memory_engine, "_seeded_agents", seeded)
