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
        agent_type: str = "default",
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
        agent_type = context.get("agent_type", self.agent_type)
        
        # Determine valid skills for THIS specific agent type
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        config_parsing = self.agent_config.get_parsing_config(agent_type) or self.config
        
        # Initialize results
        skill_name = None
        reasoning = {}
        adjustment = None
        parsing_warnings = []
        
        if not raw_output or not raw_output.strip():
            parsing_warnings.append("Empty raw output from model")
        
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
                for skill in valid_skills:
                    if skill.lower() in raw_decision:
                        skill_name = skill
                        break
                
                # Skill mapping logic: Smart Resolution
                if not skill_name:
                    skill_map = self.agent_config.get_skill_map(agent_type, context)
                    
                    # Try to find a numeric match in the map
                    for char in raw_decision:
                        if char.isdigit() and char in skill_map:
                            skill_name = skill_map.get(char)
                            break
                    
                    # Universal Numeric Mapper (Fallback if no map or match found)
                    if not skill_name:
                        # Fallback: Use index of actions list in YAML (1-indexed)
                        raw_actions = self.agent_config.get(agent_type).get("actions", [])
                        for char in raw_decision:
                            if char.isdigit():
                                idx = int(char) - 1
                                if 0 <= idx < len(raw_actions):
                                    skill_name = raw_actions[idx]["id"]
                                    break
                
                # Extract dynamic constructs (Config-driven)
                constructs = self.agent_config.get(agent_type).get("parsing", {}).get("constructs", {})
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
                        agent_type=agent_type,
                        reasoning=reasoning,
                        raw_output=raw_output,
                        parsing_warnings=parsing_warnings
                    )
        except (json.JSONDecodeError, ValueError):
            pass

        # 2. FALLBACK TO REGEX PARSING (Existing logic)
        lines = cleaned_output.strip().split('\n')
        parsing_cfg = self.agent_config.get(agent_type).get("parsing", {})
        keywords = parsing_cfg.get("decision_keywords", ["decide:", "decision:"])
        
        # Update valid_skills for this specific type if not explicitly provided
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        
        # Use a more flexible detection for decision lines (handles truncation like "Final Decisi:")
        for line in lines:
            line_lower = line.strip().lower()
            
            # Use regex for keywords to handle truncation (e.g., "final decisi:")
            found_decision = False
            for keyword in keywords:
                # Create a regex that allows optional trailing chars or truncation
                # e.g., "final decision:" matches "final decisi:" or "decision:"
                kw_base = keyword.replace(":", "").strip()
                # If the line starts with a significant prefix of the keyword
                kw_pattern = rf"^(?:.*)?{re.escape(kw_base[:7])}.*?[:：]\s*(.*)"
                match = re.search(kw_pattern, line_lower)
                
                if match:
                    decision_text = match.group(1).strip()
                    decision_lower = decision_text.lower()
                    
                    # 1. Try to match a skill name from config aliases
                    decision_norm = decision_lower.replace("_", "").replace(" ", "")
                    for skill in valid_skills:
                        skill_norm = skill.lower().replace("_", "").replace(" ", "")
                        if skill_norm in decision_norm:
                            skill_name = skill
                            found_decision = True
                            break
                    
                    # 2. Try to match a numeric decision from skill map
                    if not skill_name:
                        skill_map = self.agent_config.get_skill_map(agent_type, context)
                        for char in decision_text:
                            if char.isdigit() and char in skill_map:
                                skill_name = skill_map.get(char)
                                found_decision = True
                                break
                    
                    if found_decision:
                        break
            if found_decision:
                break
        
        # 3. LAST RESORT: Search for any standalone number 1-4 or action name at the end of the text
        if not skill_name:
            skill_map = self.agent_config.get_skill_map(agent_type, context)
            # Find the LAST instance of a number 1-4 in the entire text
            # Often DeepSeek ends with "Final Decision: 4" but it's truncated
            digit_matches = re.findall(r'(\d)', cleaned_output)
            if digit_matches:
                last_digit = digit_matches[-1]
                if last_digit in skill_map:
                    skill_name = skill_map[last_digit]
                    parsing_warnings.append(f"Decision extracted via last-resort numeric search: {last_digit}")
            
            if not skill_name:
                # Try finding valid skill names in the entire text
                for skill in valid_skills:
                    if skill.lower() in cleaned_output.lower():
                        skill_name = skill
                        parsing_warnings.append(f"Decision extracted via keyword presence: {skill}")
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
            
            # Generic KV-style construct parsing (e.g., PSY_EVAL: A=1 B=2)
            eval_match = re.search(r"([a-z0-9_]+)_eval:\s*(.+)", line_lower)
            if eval_match:
                prefix = eval_match.group(1).upper()
                content = eval_match.group(2).strip()
                parts = content.split()
                for part in parts:
                    if "=" in part:
                        k, v = part.split("=", 1)
                        # We use prefix to avoid collisions across different schemas
                        reasoning[f"{prefix}_{k.upper()}"] = v
                reasoning[f"{prefix}_raw"] = content


            # Config-driven Construct Parsing (Generic)
            constructs = config_parsing.get("constructs", {})

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
            
        
        # Default skill from config
        if not skill_name:
            skill_name = config_parsing.get("default_skill", "do_nothing")
            msg = f"Could not parse decision for {agent_id}. Falling back to default: '{skill_name}'"
            parsing_warnings.append(msg)
            print(f"[ModelAdapter:Diagnostic] Warning: {msg}")
            # Log first 100 chars of output to help debug why it failed
            print(f"[ModelAdapter:Diagnostic] Raw Output Snippet: {repr(cleaned_output[:100])}...")
            
        # Resolve to canonical ID
        if skill_name:
            skill_name = self.alias_map.get(skill_name.lower(), skill_name)
        
        # Add adjustment to reasoning if present
        if adjustment is not None:
            reasoning["adjustment"] = adjustment
        
        # 3. Config-driven Construct Parsing (Generic Fallback for Text)
        config_parsing = self.agent_config.get(agent_type).get("parsing", {})
        constructs_cfg = config_parsing.get("constructs", {})
        for key, construct_cfg in constructs_cfg.items():
            if key in reasoning and reasoning[key]:
                continue
            
            pattern = construct_cfg.get("regex")
            if pattern:
                match = re.search(pattern, cleaned_output, re.IGNORECASE | re.MULTILINE)
                if match:
                    # If regex has a group, use it. Otherwise use the whole match.
                    reasoning[key] = match.group(1).strip() if match.groups() else match.group(0).strip()

        # 6. Post-Parsing Robustness: Completeness Check
        if config_parsing and "constructs" in config_parsing:
            expected = set(config_parsing["constructs"].keys())
            found = set(reasoning.keys())
            missing = expected - found
            if missing:
                msg = f"Missing constructs for '{agent_type}': {list(missing)}"
                parsing_warnings.append(msg)
                print(f"[ModelAdapter:Diagnostic] Warning: {msg}")

        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            agent_type=agent_type,
            reasoning=reasoning,
            confidence=1.0,  # Placeholder
            raw_output=raw_output,
            parsing_warnings=parsing_warnings
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
    
    Enhanced to handle:
    - Unclosed think tags
    - Content split between inside/outside tags
    - Very long think sections
    """
    if not text:
        return ""
    
    # Handle both <think> and <thinking> variations
    text = text.replace('<thinking>', '<think>').replace('</thinking>', '</think>')
    
    # 1. Try to get content AFTER </think> tag first (preferred)
    after_think_match = re.search(r'</think>\s*(.+)', text, flags=re.DOTALL)
    if after_think_match:
        after_content = after_think_match.group(1).strip()
        if len(after_content) > 30:  # Substantial content after tag
            return after_content
    
    # 2. Remove think tags and get what's left
    cleaned = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
    
    # 3. If cleaned is empty or very short, extract from inside think tags
    if not cleaned or len(cleaned) < 30:
        # Find think content
        think_match = re.search(r'<think>(.*?)(?:</think>|$)', text, flags=re.DOTALL)
        if think_match:
            inner = think_match.group(1).strip()
            
            # Look for the final answer section within think
            # DeepSeek often puts "Final Decision" or answer at the end of think block
            decision_patterns = [
                r'(threat appraisal.*?final decision.*)',  # Full answer block
                r'(final decision:?\s*.+)',  # Just decision
                r'(決策|decision)[:：]\s*(.+)',  # With Chinese
            ]
            for pattern in decision_patterns:
                match = re.search(pattern, inner, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(0).strip()
            
            # If inner has any decision-like content, use it
            keywords = ['decide', 'decision', 'appraisal', 'threat', 'coping', '1', '2', '3', '4']
            if any(kw in inner.lower() for kw in keywords):
                # Take last 500 chars where answer usually is
                return inner[-500:] if len(inner) > 500 else inner
            
            # Return inner if cleaned is empty
            if not cleaned:
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
