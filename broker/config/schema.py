from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Literal, Any

import yaml
from pydantic import BaseModel, Field, validator


class MemoryConfig(BaseModel):
    """Memory engine configuration."""
    engine_type: Literal[
        "window",
        "importance",
        "humancentric",
        "hierarchical",
        "universal",
        "unified",
        "human_centric",
    ] = "window"
    window_size: int = Field(default=5, ge=1, le=20)
    decay_rate: float = Field(default=0.1, ge=0.0, le=1.0)
    consolidation_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    consolidation_probability: float = Field(default=0.7, ge=0.0, le=1.0)
    top_k_significant: int = Field(default=2, ge=1)
    arousal_threshold: float = Field(default=0.5, ge=0.0, le=1.0)

    class Config:
        extra = "allow"

    @validator("engine_type", pre=True)
    def normalize_engine_type(cls, value: str) -> str:
        if value == "human_centric":
            return "humancentric"
        return value


class GovernanceRule(BaseModel):
    """Single governance rule."""
    id: str
    construct: Optional[str] = None
    conditions: Optional[List[Dict[str, Any]]] = None
    when_above: Optional[List[str]] = None
    blocked_skills: List[str] = []
    level: Literal["ERROR", "WARNING"] = "ERROR"
    message: Optional[str] = None

    class Config:
        extra = "allow"


class GovernanceProfile(BaseModel):
    """Governance profile (strict/relaxed/disabled)."""
    thinking_rules: List[GovernanceRule] = []
    identity_rules: List[GovernanceRule] = []

    class Config:
        extra = "allow"


class GovernanceProfiles(BaseModel):
    """Governance profiles container."""
    strict: Optional[GovernanceProfile] = None
    relaxed: Optional[GovernanceProfile] = None
    disabled: Optional[GovernanceProfile] = None

    class Config:
        extra = "allow"


class GlobalConfig(BaseModel):
    """Global experiment configuration."""
    memory: MemoryConfig = MemoryConfig()
    reflection: Optional[Dict[str, Any]] = None
    llm: Optional[Dict[str, Any]] = None
    governance: Optional[Dict[str, Any]] = None

    class Config:
        extra = "allow"


class AgentTypeConfig(BaseModel):
    """Full agent_types.yaml configuration."""
    global_config: GlobalConfig
    shared: Optional[Dict[str, Any]] = None
    household: Optional[Dict[str, Any]] = None
    governance: Optional[GovernanceProfiles] = None

    class Config:
        extra = "allow"


def load_agent_config(config_path: Path) -> AgentTypeConfig:
    """Load and validate agent_types.yaml configuration."""
    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return AgentTypeConfig(**raw)
