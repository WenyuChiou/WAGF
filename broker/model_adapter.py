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

from .skill_types import SkillProposal


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
        Multi-level parsing with graceful fallback.
        
        Level 1: Strict structured parsing (existing logic)
        Level 2: Flexible keyword extraction
        Level 3: Raw text storage with warning
        
        Args:
            raw_output: Raw text output from LLM
            context: Current context (for skill mapping)
            
        Returns:
            SkillProposal or None if parsing fails
        """
        import logging
        logger = logging.getLogger(__name__)
        
        # Validation: Ensure raw_output is string
        if not isinstance(raw_output, str):
            logger.error(f"Unexpected output type: {type(raw_output)}, forcing to str")
            raw_output = str(raw_output)
        
        if not raw_output or len(raw_output.strip()) == 0:
            logger.error("Empty raw_output received")
            raw_output = "[EMPTY OUTPUT]"
        
        # Apply preprocessor (e.g., remove <think> tags)
        cleaned_output = self.preprocessor(raw_output)
        
        agent_id = context.get("agent_id", "unknown")
        
        # ===== LEVEL 1: Strict Structured Parsing =====
        logger.debug(f"[{agent_id}] Attempting Level 1 (strict) parsing")
        skill_name, reasoning = self._parse_structured(cleaned_output, context)
        
        if skill_name:
            logger.info(f"[{agent_id}] Level 1 parsing succeeded: skill={skill_name}")
        else:
            logger.warning(f"[{agent_id}] Level 1 parsing failed (no skill found)")
        
        # ===== LEVEL 2: Flexible Keyword Extraction =====
        if not skill_name:
            logger.warning(f"[{agent_id}] Attempting Level 2 (flexible) parsing")
            skill_name = self._extract_skill_flexible(cleaned_output)
            
            if skill_name:
                logger.info(f"[{agent_id}] Level 2 parsing succeeded: skill={skill_name}")
            else:
                logger.warning(f"[{agent_id}] Level 2 parsing failed")
        
        if not reasoning or (isinstance(reasoning, dict) and len(reasoning) == 0):
            logger.warning(f"[{agent_id}] No structured reasoning found, attempting flexible extraction")
            reasoning = self._extract_reasoning_flexible(cleaned_output)
        
        # ===== LEVEL 3: Final Fallback =====
        if not skill_name:
            default_skill = self.config.get("default_skill", "do_nothing")
            logger.warning(f"[{agent_id}] All parsing failed, using default: {default_skill}")
            skill_name = default_skill
        
        # CRITICAL: Always preserve raw output
        if not reasoning or (isinstance(reasoning, dict) and len(reasoning) == 0):
            logger.warning(f"[{agent_id}] Storing raw output as reasoning (fallback)")
            reasoning = {
                "raw": cleaned_output.strip(),
                "parse_status": "fallback",
                "parser_version": "three_stage_v1"
            }
        elif isinstance(reasoning, str):
            # Wrap string reasoning in dict for consistency
            reasoning = {
                "text": reasoning,
                "parse_status": "flexible",
                "parser_version": "three_stage_v1"
            }
        else:
            # Add parse metadata to dict reasoning
            reasoning["parse_status"] = "structured"
            reasoning["parser_version"] = "three_stage_v1"
        
        # Resolve to canonical ID
        if skill_name:
            canonical_skill = self.alias_map.get(skill_name.lower(), skill_name)
            if canonical_skill != skill_name:
                logger.debug(f"[{agent_id}] Resolved '{skill_name}' → '{canonical_skill}'")
            skill_name = canonical_skill
        
        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            agent_type=self.agent_type,
            reasoning=reasoning,
            confidence=1.0,
            raw_output=cleaned_output
        )
    
    
    def _parse_structured(self, text: str, context: Dict) -> tuple:
        """
        Level 1: Strict structured parsing (existing logic).
        
        Returns:
            (skill_name, reasoning_dict)
        """
        # Initialize results
        skill_name = None
        reasoning = {}
        adjustment = None
        
        lines = text.strip().split('\n')
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
            
            # Parse PRIORITY: for government
            priority_match = re.search(r"priority:\s*(\w+)", line_lower)
            if priority_match:
                reasoning["priority"] = priority_match.group(1).strip()
            
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

            # Parse individual PMT evaluations with reasoning (EVAL_TP: [H] reason...)
            elif line_lower.startswith("eval_"):
                pmt_match = re.search(r"eval_(tp|cp|sp|sc|pa):\s*\[?([a-z]+)\]?\s*(.*)", line, re.IGNORECASE)
                if pmt_match:
                    construct = pmt_match.group(1).upper()
                    val = pmt_match.group(2).upper()
                    reason = pmt_match.group(3).strip()
                    reasoning[construct] = val
                    reasoning[f"{construct}_REASON"] = reason

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
                if len(parts) > 1:
                    decision_text = parts[1].strip()
                else:
                    decision_text = ""
                    
                decision_lower = decision_text.lower()
                
                for skill in self.valid_skills:
                    if skill.lower() in decision_lower:
                        skill_name = skill
                        break
                
                # Generic skill variant mapping from config
                if not skill_name:
                    variant = context.get("skill_variant")
                    
                    if variant:
                        # Variant-specific mapping (e.g., 'renter', 'elevated')
                        skill_map = self.config.get(f"skill_map_{variant}", {})
                    else:
                        # Default mapping
                        skill_map = self.config.get("skill_map_default", self.config.get("skill_map_non_elevated", {}))
                        
                    for char in decision_text:
                        if char.isdigit():
                            skill_name = skill_map.get(char, self.config.get("default_skill", "do_nothing"))
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
        
        return skill_name, reasoning
        
        # FIX: If reasoning is empty, store raw output for validation
        if not reasoning or (isinstance(reasoning, dict) and len(reasoning) == 0):
            reasoning = cleaned_output.strip()  # Store as string instead of empty dict
        
        return SkillProposal(
            skill_name=skill_name,
            agent_id=agent_id,
            reasoning=reasoning,
            confidence=1.0,
            raw_output=raw_output
        )
    
    
    def _extract_skill_flexible(self, text: str) -> Optional[str]:
        """
        Level 2: Flexible skill extraction.
        
        Searches for skill names anywhere in text, not just after keywords.
        Orders by specificity (longest first) to avoid partial matches.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        text_lower = text.lower()
        
        # Try to find skill names in order of specificity (longest first)
        for skill in sorted(self.valid_skills, key=len, reverse=True):
            if skill.lower() in text_lower:
                logger.info(f"Found skill '{skill}' via flexible matching")
                return skill
        
        return None
    
    
    def _extract_reasoning_flexible(self, text: str) -> Dict[str, Any]:
        """
        Level 2: Extract any reasoning-like text.
        
        Looks for common reasoning patterns even without strict formatting.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        reasoning = {}
        
        # Extract sentences that look like reasoning
        reasoning_patterns = [
            r"(?:because|since|due to|given that)\s+(.+)",
            r"(?:i think|i believe|i should)\s+(.+)",
            r"(?:risk|threat|concern)(?:s)?\s+(?:is|are)\s+(.+)",
            r"(?:consider|considering)\s+(.+)",
        ]
        
        for pattern in reasoning_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                reasoning["inferred_reason"] = " | ".join(matches[:3])
                logger.debug(f"Extracted reasoning via pattern")
                break
        
        # If still empty, store first 200 chars as summary
        if not reasoning:
            summary = text.strip()[:200]
            reasoning["summary"] = summary
            logger.debug(f"No reasoning patterns found, storing summary ({len(summary)} chars)")
        
        reasoning["extraction_method"] = "flexible"
        return reasoning
    
    
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
    Removes <think>...</think> reasoning tags.
    """
    return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()


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
