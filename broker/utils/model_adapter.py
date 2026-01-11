"""
Model Adapter - Thin layer for multi-LLM support.

The Model Adapter has ONLY two responsibilities:
1. Parse LLM output → SkillProposal
2. Format rejection/retry → LLM prompt

NO domain logic should exist in adapters!

v0.3: Unified adapter with optional preprocessor for model-specific quirks.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
import re
import json

from ..interfaces.skill_types import SkillProposal


class ModelAdapter(ABC):
    """
    Abstract base class for model adapters.
    
    Each LLM type (Ollama, OpenAI, Anthropic) has its own adapter
    that normalizes output into SkillProposal format.
    """
    
    @abstractmethod
    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        
        Args:
            raw_output: Raw text output from LLM
            context: Current context (for skill mapping)
            
        Returns:
            SkillProposal or None if parsing fails
        """
        pass
    
    @abstractmethod
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """
        Format retry prompt with validation errors.
        
        Args:
            original_prompt: The original prompt sent to LLM
            errors: List of validation errors
            
        Returns:
            Formatted retry prompt
        """
        pass


from .agent_config import load_agent_config

class UnifiedAdapter(ModelAdapter):
    """
    Unified adapter supporting all models AND all agent types.
    
    Skills, decision keywords, and default settings are loaded from agent_types.yaml.
    Model-specific quirks (like DeepSeek's <think> tags) are handled via preprocessor.
    """
    
    def __init__(
        self,
        agent_type: str = "household",
        preprocessor: Optional[Callable[[str], str]] = None,
        valid_skills: Optional[set] = None,
        config_path: str = None
    ):
        """
        Initialize unified adapter.
        
        Args:
            agent_type: Type of agent (household, insurance, government)
            preprocessor: Optional function to preprocess raw output
            valid_skills: Optional set of valid skill names (overrides agent_type config)
            config_path: Optional path to agent_types.yaml
        """
        self.agent_type = agent_type
        self.agent_config = load_agent_config(config_path)
        
        # Load parsing config and actual actions/aliases
        parsing_cfg = self.agent_config.get_parsing_config(agent_type)
        if not parsing_cfg:
            # Smart defaults if 'parsing' block is missing from YAML
            parsing_cfg = {
                "decision_keywords": ["final decision:", "decision:", "decide:"],
                "default_skill": "do_nothing",
                "constructs": {}
            }
        
        actions = self.agent_config.get_valid_actions(agent_type)
        
        self.config = parsing_cfg
        self.preprocessor = preprocessor or (lambda x: x)
        
        # Build alias map for canonical ID resolution
        self.alias_map = {}
        # Get raw action config to access IDs and aliases
        raw_actions = self.agent_config.get(agent_type).get("actions", [])
        for action in raw_actions:
            canonical_id = action["id"]
            self.alias_map[canonical_id.lower()] = canonical_id
            for alias in action.get("aliases", []):
                self.alias_map[alias.lower()] = canonical_id
                
        # If valid_skills provided, just use them (no mapping assumed/possible without config)
        if valid_skills:
            self.valid_skills = valid_skills
        else:
            self.valid_skills = set(self.alias_map.keys())
    
    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        
        Supports:
        - JSON-formatted output (Preferred)
        - Structured text (Fallback)
        """
        # Apply preprocessor (e.g., remove <think> tags)
        cleaned_output = self.preprocessor(raw_output)
        
        agent_id = context.get("agent_id", "unknown")
        agent_type = context.get("agent_type", "default")
        
        # Initialize results
        skill_name = None
        reasoning = {}
        adjustment = None
        
        # 1. ATTEMPT PURE JSON PARSING
        try:
            # Look for JSON block in case model added text around it
            json_text = cleaned_output.strip()
            if "```json" in json_text:
                json_text = json_text.split("```json")[1].split("```")[0].strip()
            elif "{" in json_text:
                json_text = json_text[json_text.find("{"):json_text.rfind("}")+1]
                
            data = json.loads(json_text)
            if isinstance(data, dict):
                # Extract skills/decisions
                raw_decision = str(data.get("decision", data.get("Final Decision", ""))).lower()
                for skill in self.valid_skills:
                    if skill.lower() in raw_decision:
                        skill_name = skill
                        break
                
                # Skill mapping logic: Smart Resolution
                if not skill_name:
                    skill_map = self.agent_config.get_skill_map(self.agent_type, context)
                    
                    # Try to find a numeric match in the map
                    for char in raw_decision:
                        if char.isdigit() and char in skill_map:
                            skill_name = skill_map.get(char)
                            break
                    
                    # Universal Numeric Mapper (Fallback if no map or match found)
                    if not skill_name:
                        # Fallback: Use index of actions list in YAML (1-indexed)
                        raw_actions = self.agent_config.get(self.agent_type).get("actions", [])
                        for char in raw_decision:
                            if char.isdigit():
                                idx = int(char) - 1
                                if 0 <= idx < len(raw_actions):
                                    skill_name = raw_actions[idx]["id"]
                                    break
                
                # Extract dynamic constructs (Config-driven)
                constructs = self.config.get("constructs", {})
                for key, construct_cfg in constructs.items():
                    # keywords are keys in JSON
                    for kw in construct_cfg.get("keywords", []):
                        if kw in data:
                            reasoning[key] = data[kw]
                            break
                
                if skill_name:
                    if "adj" in data:
                        reasoning["adjustment"] = data["adj"]
                    return SkillProposal(
                        skill_name=skill_name,
                        agent_id=agent_id,
                        reasoning=reasoning,
                        raw_output=raw_output
                    )
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. FALLBACK TO REGEX PARSING (Existing logic)
        lines = cleaned_output.strip().split('\n')
        keywords = self.config.get("decision_keywords", ["decide:", "decision:"])
        
        for line in lines:
            line_lower = line.strip().lower()
            
            # Check for decision keywords from config
            for keyword in keywords:
                if line_lower.startswith(keyword):
                    decision_text = line.split(":", 1)[1].strip() if ":" in line else ""
                    decision_lower = decision_text.lower()
                    
                    # Try to match a skill from config
                    for skill in self.valid_skills:
                        if skill.lower() in decision_lower:
                            skill_name = skill
                            break
                    break
            
            # Parse ADJ: for adjustment percentage
            adj_match = re.search(r"adj:\s*([0-9.]+%?)", line_lower)
            if adj_match:
                adj_text = adj_match.group(1)
                try:
                    adj_clean = adj_text.replace("%", "").strip()
                    adj_val = float(adj_clean)
                    adjustment = adj_val / 100 if adj_val > 1 else adj_val
                except ValueError:
                    pass
            
            # Parse REASON: or JUSTIFICATION:
            reason_match = re.search(r"(?:reason|justification):\s*(.+)", line_lower)
            if reason_match:
                reasoning["reason"] = reason_match.group(1).strip()
            
            
            # Parse INTERPRET (usually standalone)
            if line_lower.startswith("interpret:"):
                reasoning["interpret"] = line.split(":", 1)[1].strip() if ":" in line else ""
            
            # Parse PMT_EVAL: TP=X CP=Y ...
            elif line_lower.startswith("pmt_eval:"):
                content = line.split(":", 1)[1].strip()
                # Split by spaces to find assignments like TP=H
                parts = content.split()
                for part in parts:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        reasoning[k.upper()] = v
                reasoning["pmt_eval_raw"] = content


            # Config-driven Construct Parsing (Generic)
            constructs = self.config.get("constructs", {})

            for key, construct_cfg in constructs.items():
                # Check for keywords
                has_keyword = any(k in line_lower for k in construct_cfg.get("keywords", []))
                if has_keyword:
                    # Apply regex
                    pattern = construct_cfg.get("regex", "")
                    if pattern:
                        match = re.search(pattern, line, re.IGNORECASE)
                        if match:
                            reasoning[key] = match.group(1).strip()
            
            # Legacy: "Final Decision:" for household
            if (line_lower.startswith("final decision:") or line_lower.startswith("decision:")) and not skill_name:
                parts = line.split(":", 1)
                decision_text = parts[1].strip() if len(parts) > 1 else ""
                decision_lower = decision_text.lower()
                
                for skill in self.valid_skills:
                    if skill.lower() in decision_lower:
                        skill_name = skill
                        break
                
                # Skill mapping logic: Smart Resolution
                if not skill_name:
                    skill_map = self.agent_config.get_skill_map(self.agent_type, context)
                    
                    # Try map
                    for char in decision_text:
                        if char.isdigit() and char in skill_map:
                            skill_name = skill_map.get(char)
                            break
                            
                    # Universal Fallback
                    if not skill_name:
                        raw_actions = self.agent_config.get(self.agent_type).get("actions", [])
                        for char in decision_text:
                            if char.isdigit():
                                idx = int(char) - 1
                                if 0 <= idx < len(raw_actions):
                                    skill_name = raw_actions[idx]["id"]
                                    break
        
        # Default skill from config
        if not skill_name:
            skill_name = self.config.get("default_skill", "do_nothing")
            
        # Resolve to canonical ID
        if skill_name:
            skill_name = self.alias_map.get(skill_name.lower(), skill_name)
        
        # Add adjustment to reasoning if present
        if adjustment is not None:
            reasoning["adjustment"] = adjustment
        
        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            reasoning=reasoning,
            confidence=1.0,
            raw_output=raw_output
        )
    
    def format_retry_prompt(self, original_prompt: str, errors: List[str]) -> str:
        """Format retry prompt with validation errors."""
        error_text = ", ".join(errors)
        return f"""Your previous response was flagged for the following issues:
{error_text}

Please reconsider your decision and respond again.

{original_prompt}"""


# =============================================================================
# PREPROCESSORS for model-specific quirks
# =============================================================================
def deepseek_preprocessor(text: str) -> str:
    """
    Preprocessor for DeepSeek models.
    Removes <think>...</think> reasoning tags, but PRESERVES content
    if the model put the entire decision inside the think tag.
    """
    # 1. Try to get content outside tags
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # 2. If cleaned is too short, look inside tags
    if len(cleaned) < 20:
        match = re.search(r'<think>(.*?)</think>', text, flags=re.DOTALL)
        if match:
            inner = match.group(1).strip()
            if "decision" in inner.lower():
                return inner
    return cleaned


def json_preprocessor(text: str) -> str:
    """
    Preprocessor for models that may return JSON.
    Extracts text content from JSON if present.
    """
    import json
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            # Look for common fields
            for key in ['response', 'output', 'text', 'content']:
                if key in data:
                    return str(data[key])
        return text
    except json.JSONDecodeError:
        return text


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_adapter(model_name: str) -> ModelAdapter:
    """
    Get the appropriate adapter for a model.
    
    Uses UnifiedAdapter with model-specific preprocessor if needed.
    """
    model_lower = model_name.lower()
    
    # DeepSeek models use <think> tags
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor)
    
    # All other models use standard adapter
    # (Llama, Gemma, GPT-OSS, OpenAI, Anthropic, etc.)
    return UnifiedAdapter()


# =============================================================================
# LEGACY ALIASES (for backward compatibility)
# =============================================================================

class OllamaAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass


class OpenAIAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass
