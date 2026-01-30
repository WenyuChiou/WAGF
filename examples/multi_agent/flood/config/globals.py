"""Centralized configuration loader for multi-agent flood simulation."""

import yaml
from pathlib import Path
from typing import Dict, Any

CONFIG_DIR = Path(__file__).parent

def load_yaml(filename: str, subdir: str = "") -> Dict[str, Any]:
    """Load a YAML config file."""
    path = CONFIG_DIR / subdir / filename if subdir else CONFIG_DIR / filename
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def load_floodabm_params() -> Dict[str, Any]:
    """Load FLOODABM parameters (Tables S1-S6)."""
    return load_yaml("floodabm_params.yaml", "parameters")

def load_agent_types() -> Dict[str, Any]:
    """Load agent type definitions."""
    return load_yaml("agent_types.yaml", "agents")

def load_skill_registry() -> Dict[str, Any]:
    """Load skill registry definitions."""
    return load_yaml("skill_registry.yaml", "skills")

def load_coherence_rules() -> Dict[str, Any]:
    """Load governance coherence rules."""
    return load_yaml("coherence_rules.yaml", "governance")

# Singleton cache
_CACHE: Dict[str, Any] = {}

def get_floodabm_params() -> Dict[str, Any]:
    """Load FLOODABM parameters (Tables S1-S6)."""
    if "floodabm" not in _CACHE:
        _CACHE["floodabm"] = load_floodabm_params()
    # Return the nested dictionary containing the actual parameters
    return _CACHE["floodabm"]["floodabm_parameters"]

def get_skill_registry() -> Dict[str, Any]:
    if "skills" not in _CACHE:
        _CACHE["skills"] = load_skill_registry()
    return _CACHE["skills"]

def clear_cache() -> None:
    _CACHE.clear()
