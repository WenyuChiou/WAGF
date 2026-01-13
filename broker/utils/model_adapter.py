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

class GenericRegexPreprocessor:
    """Configurable regex-based preprocessor."""
    def __init__(self, patterns: List[Dict[str, Any]]):
        self.patterns = patterns
    def __call__(self, text: str) -> str:
        if not text: return ""
        for p in self.patterns:
            pattern = p.get("pattern", "")
            repl = p.get("repl", "")
            if pattern:
                text = re.sub(pattern, repl, text, flags=re.DOTALL)
        return text.strip()

def get_preprocessor(p_cfg: Dict[str, Any]) -> Callable[[str], str]:
    """Factory for preprocessors based on config."""
    p_type = p_cfg.get("type", "identity").lower()
    if p_type == "deepseek":
        return deepseek_preprocessor
    elif p_type == "json":
        return json_preprocessor
    elif p_type == "regex":
        return GenericRegexPreprocessor(p_cfg.get("patterns", []))
    return lambda x: x

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
        
        # Determine preprocessor (Order: Explicit argument > YAML Config > Identity)
        if preprocessor:
            self._preprocessor = preprocessor
        else:
            p_cfg = parsing_cfg.get("preprocessor", {})
            self._preprocessor = get_preprocessor(p_cfg)
        
        self._preprocessor = preprocessor or (lambda x: x)
        
        # Load valid skills for the agent type to build alias map
        self.valid_skills = self.agent_config.get_valid_actions(agent_type)
        self.alias_map = {}
        for skill in self.valid_skills:
            # Add self
            self.alias_map[skill.lower()] = skill
            # Add aliases from config if they exist
            # Note: Aliases are handled within SkillRegistry usually, 
            # but ModelAdapter needs them for direct string matching
            
    def _get_preprocessor_for_type(self, agent_type: str) -> Callable[[str], str]:
        """Get preprocessor for a specific agent type."""
        try:
            is_identity = (self._preprocessor.__name__ == "<lambda>" and self._preprocessor("") == "")
        except:
            is_identity = False
            
        if not is_identity:
            return self._preprocessor
                
        p_cfg = self.agent_config.get_parsing_config(agent_type).get("preprocessor", {})
        if p_cfg:
            return get_preprocessor(p_cfg)
        return self._preprocessor

    def parse_output(self, raw_output: str, context: Dict[str, Any]) -> Optional[SkillProposal]:
        """
        Parse LLM output into SkillProposal.
        Supports: Enclosure blocks (Phase 15), JSON, and Structured Text.
        """
        agent_id = context.get("agent_id", "unknown")
        agent_type = context.get("agent_type", self.agent_type)
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        preprocessor = self._get_preprocessor_for_type(agent_type)
        parsing_cfg = self.agent_config.get_parsing_config(agent_type) or {}
        skill_map = self.agent_config.get_skill_map(agent_type, context)
        
        # 0. Initialize results
        skill_name = None
        reasoning = {}
        parsing_warnings = []
        adjustment = None

        # 1. Phase 15: Enclosure Extraction (Priority)
        # Support both triple-bracket and XML-style tags for maximum model compatibility
        patterns = [
            r"<<<DECISION_START>>>+?\s*(.*?)\s*<<<DECISION_END>>>+?",
            r"<decision>\s*(.*?)\s*</decision>"
        ]
        
        target_content = raw_output
        for pattern in patterns:
            match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            if match:
                target_content = match.group(1)
                break

        # 2. Preprocess target
        cleaned_target = preprocessor(target_content)
        
        # 3. ATTEMPT JSON PARSING
        try:
            json_text = cleaned_target.strip()
            if "{" in json_text:
                json_text = json_text[json_text.find("{"):json_text.rfind("}")+1]
                
            data = json.loads(json_text)
            if isinstance(data, dict):
                # Extract decision
                decision_val = data.get("decision") or data.get("choice") or data.get("action")
                
                # Resolve decision
                if isinstance(decision_val, (int, str)) and str(decision_val) in skill_map:
                    skill_name = skill_map[str(decision_val)]
                elif isinstance(decision_val, str):
                    for skill in valid_skills:
                        if skill.lower() == decision_val.lower():
                            skill_name = skill
                            break
                
                # Extract Reasoning & Constructs
                reasoning = {
                    "strategy": data.get("strategy", ""),
                    "confidence": data.get("confidence", 1.0)
                }
                for k, v in data.items():
                    if k not in ["decision", "choice", "action", "strategy", "confidence"]:
                        reasoning[k] = v
        except (json.JSONDecodeError, AttributeError):
            pass

        # 4. FALLBACK TO REGEX/KEYWORD (if skill_name still None)
        if not skill_name:
            lines = cleaned_target.split('\n')
            keywords = parsing_cfg.get("decision_keywords", ["decide:", "decision:", "choice:", "selected_action:"])
            
            for line in lines:
                line_lower = line.strip().lower()
                for kw in keywords:
                    if kw.lower() in line_lower:
                        raw_val = line_lower.split(kw.lower())[1].strip()
                        digit_match = re.search(r'(\d)', raw_val)
                        if digit_match and digit_match.group(1) in skill_map:
                            skill_name = skill_map[digit_match.group(1)]
                            break
                        for s in valid_skills:
                            if s.lower() in raw_val:
                                skill_name = s
                                break
                if skill_name: break

        # 5. CONSTRUCT EXTRACTION (Regex based, applied to cleaned_target)
        constructs_cfg = parsing_cfg.get("constructs", {})
        for key, cfg in constructs_cfg.items():
            if key not in reasoning or not reasoning[key]:
                regex = cfg.get("regex")
                if regex:
                    match = re.search(regex, cleaned_target, re.IGNORECASE | re.DOTALL)
                    if match:
                        reasoning[key] = match.group(1).strip() if match.groups() else match.group(0).strip()

        # 6. LAST RESORT: Search for bracketed numbers [1-7] in cleaned_target
        if not skill_name:
            bracket_matches = re.findall(r'\[(\d)\]', cleaned_target)
            digit_matches = re.findall(r'(\d)', cleaned_target)
            candidates = bracket_matches if bracket_matches else digit_matches
            if candidates:
                last_digit = candidates[-1]
                if last_digit in skill_map:
                    skill_name = skill_name or skill_map[last_digit]
                    parsing_warnings.append(f"Last-resort extraction from digit: {last_digit}")

        # 7. Final Cleanup & Defaulting
        if not skill_name:
            skill_name = parsing_cfg.get("default_skill", "do_nothing")
            parsing_warnings.append(f"Default skill '{skill_name}' used.")

        # Resolve to canonical ID via alias map
        skill_name = self.alias_map.get(skill_name.lower(), skill_name)

        return SkillProposal(
            agent_id=agent_id,
            skill_name=skill_name,
            reasoning=reasoning,
            raw_output=raw_output,
            parsing_warnings=parsing_warnings
        )

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
    if not cleaned or len(cleaned) < 20:
        # Find think content
        think_match = re.search(r'<think>(.*?)(?:</think>|$)', text, flags=re.DOTALL)
        if think_match:
            inner = think_match.group(1).strip()
            
            # Look for the final answer section within think
            decision_patterns = [
                r'(threat appraisal.*?final decision:?\s*\d+.*)',  # Numerical decision
                r'(threat appraisal.*?final decision:?\s*\w+.*)',  # Named decision
                r'(final decision:?\s*.+)',  # Just decision
                r'(決策|decision)[:：]\s*(.+)',  # With Chinese
            ]
            for pattern in decision_patterns:
                match = re.search(pattern, inner, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(0).strip()
            
            # If inner has any decision-like content, take the end of it
            keywords = ['decide', 'decision', 'appraisal', 'threat', 'coping', '1', '2', '3', '4']
            if any(kw in inner.lower() for kw in keywords):
                return inner[-800:] if len(inner) > 800 else inner
            
            # Return inner if cleaned is empty
            if not cleaned and inner:
                return inner
    
    return cleaned if cleaned else text # Fallback to original text if everything failed


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
