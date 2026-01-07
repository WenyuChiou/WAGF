"""
Context Engineering Data Structures

Based on GSSC (Gather-Select-Structure-Compress) pipeline pattern.
Reference: Chapter 9 Context Engineering (hello-agents)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, Optional, List


@dataclass
class ContextPacket:
    """
    Candidate information package.
    
    Each piece of context (memory, observation, construct) is wrapped in a ContextPacket.
    """
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    token_count: int = 0
    relevance_score: float = 0.5  # 0.0-1.0
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        # Clamp relevance score
        self.relevance_score = max(0.0, min(1.0, self.relevance_score))
        # Estimate tokens if not provided
        if self.token_count == 0:
            self.token_count = estimate_tokens(self.content)


@dataclass
class ContextConfig:
    """
    Configuration for context building.
    """
    max_tokens: int = 3000
    reserve_ratio: float = 0.2      # Reserved for system prompt
    min_relevance: float = 0.1
    enable_compression: bool = True
    recency_weight: float = 0.3
    relevance_weight: float = 0.7
    
    def __post_init__(self):
        assert 0.0 <= self.reserve_ratio <= 1.0
        assert 0.0 <= self.min_relevance <= 1.0
        assert abs(self.recency_weight + self.relevance_weight - 1.0) < 1e-6


def estimate_tokens(text: str) -> int:
    """
    Estimate token count.
    Simple heuristic: ~4 chars per token for English, ~1.5 for Chinese.
    """
    if not text:
        return 0
    chinese_chars = sum(1 for ch in text if '\u4e00' <= ch <= '\u9fff')
    other_chars = len(text) - chinese_chars
    return int(chinese_chars * 1.0 + other_chars / 4)


# ============================================================================
# GSSC Pipeline Functions
# ============================================================================

def gather_context(
    agent_state: Dict[str, Any],
    environment: Dict[str, Any],
    memory: Optional[str] = None,
    constructs: Optional[Dict[str, str]] = None,
    system_prompt: Optional[str] = None
) -> List[ContextPacket]:
    """
    GATHER: Collect all candidate context packets.
    """
    packets = []
    now = datetime.now()
    
    # 1. System prompt (highest priority)
    if system_prompt:
        packets.append(ContextPacket(
            content=system_prompt,
            timestamp=now,
            relevance_score=1.0,
            metadata={"type": "system", "priority": "high"}
        ))
    
    # 2. Agent state
    state_str = " ".join(f"{k}={v:.2f}" if isinstance(v, float) else f"{k}={v}" 
                         for k, v in agent_state.items() if not callable(v))
    packets.append(ContextPacket(
        content=state_str,
        timestamp=now,
        relevance_score=0.9,
        metadata={"type": "state"}
    ))
    
    # 3. Environment
    env_str = " ".join(f"{k}={v}" for k, v in environment.items())
    packets.append(ContextPacket(
        content=env_str,
        timestamp=now,
        relevance_score=0.8,
        metadata={"type": "environment"}
    ))
    
    # 4. Memory
    if memory:
        packets.append(ContextPacket(
            content=memory,
            timestamp=now,
            relevance_score=0.7,
            metadata={"type": "memory"}
        ))
    
    # 5. Constructs (PMT or other theory)
    if constructs:
        for name, value in constructs.items():
            packets.append(ContextPacket(
                content=f"{name}={value}",
                timestamp=now,
                relevance_score=0.85,
                metadata={"type": "construct", "name": name}
            ))
    
    return packets


def select_context(
    packets: List[ContextPacket],
    config: ContextConfig
) -> List[ContextPacket]:
    """
    SELECT: Score and filter packets within token budget.
    """
    import math
    
    available_tokens = int(config.max_tokens * (1 - config.reserve_ratio))
    
    # Separate system packets (always included)
    system_packets = [p for p in packets if p.metadata.get("type") == "system"]
    other_packets = [p for p in packets if p.metadata.get("type") != "system"]
    
    system_tokens = sum(p.token_count for p in system_packets)
    remaining_tokens = available_tokens - system_tokens
    
    if remaining_tokens <= 0:
        return system_packets
    
    # Score other packets
    scored = []
    for p in other_packets:
        if p.relevance_score < config.min_relevance:
            continue
        # Recency score (exponential decay)
        age_hours = (datetime.now() - p.timestamp).total_seconds() / 3600
        recency = math.exp(-0.1 * age_hours / 24)
        recency = max(0.1, min(1.0, recency))
        
        score = config.relevance_weight * p.relevance_score + config.recency_weight * recency
        scored.append((score, p))
    
    # Sort by score descending
    scored.sort(key=lambda x: x[0], reverse=True)
    
    # Greedy fill
    selected = system_packets.copy()
    current_tokens = system_tokens
    
    for score, p in scored:
        if current_tokens + p.token_count <= remaining_tokens:
            selected.append(p)
            current_tokens += p.token_count
    
    return selected


def structure_context(
    packets: List[ContextPacket],
    template_sections: Optional[Dict[str, str]] = None
) -> str:
    """
    STRUCTURE: Organize packets into sectioned template.
    """
    sections = {
        "system": [],
        "state": [],
        "environment": [],
        "memory": [],
        "construct": [],
        "evidence": [],
        "other": []
    }
    
    for p in packets:
        ptype = p.metadata.get("type", "other")
        if ptype in sections:
            sections[ptype].append(p.content)
        else:
            sections["other"].append(p.content)
    
    # Build output
    output_parts = []
    
    if sections["system"]:
        output_parts.append("[Role & Policies]\n" + "\n".join(sections["system"]))
    
    if sections["state"]:
        output_parts.append("[State]\n" + "\n".join(sections["state"]))
    
    if sections["environment"]:
        output_parts.append("[Environment]\n" + "\n".join(sections["environment"]))
    
    if sections["construct"]:
        output_parts.append("[Constructs]\n" + " ".join(sections["construct"]))
    
    if sections["memory"]:
        output_parts.append("[Memory]\n" + "\n".join(sections["memory"]))
    
    if sections["evidence"]:
        output_parts.append("[Evidence]\n" + "\n---\n".join(sections["evidence"]))
    
    if sections["other"]:
        output_parts.append("[Context]\n" + "\n".join(sections["other"]))
    
    return "\n\n".join(output_parts)


def compress_context(context: str, max_tokens: int) -> str:
    """
    COMPRESS: Truncate if over limit.
    """
    current_tokens = estimate_tokens(context)
    if current_tokens <= max_tokens:
        return context
    
    # Simple truncation by section
    sections = context.split("\n\n")
    compressed = []
    total = 0
    
    for section in sections:
        section_tokens = estimate_tokens(section)
        if total + section_tokens <= max_tokens:
            compressed.append(section)
            total += section_tokens
        else:
            remaining = max_tokens - total
            if remaining > 50:
                # Truncate section
                ratio = remaining / section_tokens
                truncated = section[:int(len(section) * ratio)]
                compressed.append(truncated + "\n[... compressed ...]")
            break
    
    return "\n\n".join(compressed)


# ============================================================================
# Main Builder Class
# ============================================================================

class ContextBuilder:
    """
    GSSC Context Builder.
    
    Usage:
        builder = ContextBuilder(config)
        context = builder.build(agent_state, environment, memory)
    """
    
    def __init__(self, config: Optional[ContextConfig] = None):
        self.config = config or ContextConfig()
    
    def build(
        self,
        agent_state: Dict[str, Any],
        environment: Dict[str, Any],
        memory: Optional[str] = None,
        constructs: Optional[Dict[str, str]] = None,
        system_prompt: Optional[str] = None
    ) -> str:
        """
        Build context using GSSC pipeline.
        """
        # 1. Gather
        packets = gather_context(
            agent_state=agent_state,
            environment=environment,
            memory=memory,
            constructs=constructs,
            system_prompt=system_prompt
        )
        
        # 2. Select
        selected = select_context(packets, self.config)
        
        # 3. Structure
        context = structure_context(selected)
        
        # 4. Compress (if enabled)
        if self.config.enable_compression:
            context = compress_context(context, self.config.max_tokens)
        
        return context
