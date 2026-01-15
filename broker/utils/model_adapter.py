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
from ..utils.logging import logger


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
    elif p_type == "json_extract":
        return json_extract_preprocessor
    elif p_type == "smart_repair":
        return SmartRepairPreprocessor(p_cfg.get("quote_values"))
    elif p_type == "regex":
        return GenericRegexPreprocessor(p_cfg.get("patterns", []))
    return lambda x: x


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
        # Phase 12/28: Ensure explicit or config preprocessors are not overwritten
        if preprocessor:
            self._preprocessor = preprocessor
        else:
            p_cfg = parsing_cfg.get("preprocessor", {})
            if p_cfg:
                self._preprocessor = get_preprocessor(p_cfg)
            else:
                self._preprocessor = lambda x: x
        
        # Load valid skills for the agent type to build alias map
        self.valid_skills = self.agent_config.get_valid_actions(agent_type)
        # Build alias map from config (e.g., "HE" -> "elevate_house", "FI" -> "buy_insurance")
        self.alias_map = self.agent_config.get_action_alias_map(agent_type)
            
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
        parse_layer = ""  # Track which parsing method succeeded (enclosure/json/keyword/digit/default)

        # Phase 15: Early return for empty output
        if not raw_output:
            return None

        # 1. Phase 15: Enclosure Extraction (Priority)
        # Dynamic Delimiters (from YAML config) - Phase 23
        try:
            from broker.components.response_format import ResponseFormatBuilder
            cfg = self.agent_config
            agent_cfg = cfg.get(agent_type)
            shared_cfg = {"response_format": cfg._config.get("shared", {}).get("response_format", {})}
            rfb = ResponseFormatBuilder(agent_cfg, shared_cfg)
            d_start, d_end = rfb.get_delimiters()
            # Use non-greedy match to handle multiple blocks if present
            dynamic_pattern = rf"{re.escape(d_start)}\s*(.*?)\s*{re.escape(d_end)}"
        except:
            dynamic_pattern = None

        patterns = [
            dynamic_pattern,
            r"<<<DECISION_START>>>\s*(.*?)\s*<<<DECISION_END>>>",
            r"<decision>\s*(.*?)\s*</decision>",
            r"(?:decision|choice|selected_action)[:\s]*({.*?})", # Find JSON-like block after keyword
            r"({.*})", # Final fallback: Find any JSON-like block
        ]
        
        target_content = raw_output
        for pattern in [p for p in patterns if p]:
            match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            if match:
                target_content = match.group(1)
                parse_layer = "enclosure"
                break


        # 2. Preprocess target
        cleaned_target = preprocessor(target_content)
        
        # 3. ATTEMPT JSON PARSING
        try:
            json_text = cleaned_target.strip()
            if "{" in json_text:
                json_text = json_text[json_text.find("{"):json_text.rfind("}")+1]
            
            # Preprocessor Failsafe: Handle double-braces mimicry from small models
            # Specifically: {{ ... }} -> { ... } and "{{": "{" -> "{": "{"
            if json_text.startswith("{{") and json_text.endswith("}}"):
                json_text = json_text[1:-1]
            
            # Replace recurring double braces inside the object
            json_text = json_text.replace("{{", "{").replace("}}", "}")
            
            # Clean trailing commas (common in LLM output)
            json_text = re.sub(r',\s*([\]}])', r'\1', json_text)
                
            data = json.loads(json_text)
            if isinstance(data, dict):
                # Robust case-insensitive key lookup
                data_lowered = {k.lower(): v for k, v in data.items()}
                
                # Extract decision (Generalized: Use keywords from config)
                decision_kws = parsing_cfg.get("decision_keywords", ["decision", "choice", "action"])
                decision_val = None
                for kw in decision_kws:
                    decision_val = data_lowered.get(kw.lower())
                    if decision_val is not None: break


                
                # Resolve decision
                if decision_val is not None:
                    # Case 0: Nested dict (some models output {"action": {"choice": 1}})


                    if isinstance(decision_val, dict):
                        decision_val = decision_val.get("choice") or decision_val.get("id") or decision_val.get("value")
                    
                    if decision_val is not None:
                        # Case 1: Direct mapping (int or exact digit string)
                        if str(decision_val) in skill_map:
                            skill_name = skill_map[str(decision_val)]
                        # Case 2: String like "1. Buy Insurance" or "Option 1"
                        elif isinstance(decision_val, str):
                            digit_match = re.search(r'(\d+)', decision_val)
                            if digit_match and digit_match.group(1) in skill_map:
                                skill_name = skill_map[digit_match.group(1)]
                            else:
                                # Search for skill names in string (Fuzzy match)
                                decision_norm = decision_val.lower().replace("_", " ").replace("-", " ")
                                for skill in valid_skills:
                                    skill_norm = skill.lower().replace("_", " ").replace("-", " ")
                                    if skill_norm in decision_norm:
                                        skill_name = skill
                                        break
                                # Also check alias map directly
                                # This handles "Buy Insurance" -> "buy_insurance" or "DN" -> "do_nothing"
                                for alias, canonical in skill_map.items():
                                    alias_norm = alias.lower().replace("_", " ").replace("-", " ")
                                    if alias_norm in decision_norm:
                                        skill_name = canonical
                                        break
                
                # RECOVERY: If JSON parsed but no decision found, look for "Naked Digit" after the JSON block
                if not skill_name:
                    after_json = cleaned_target[cleaned_target.rfind("}")+1:].strip()
                    # Look for digits at start OR with some context (like "Decision: 4")
                    digit_match = re.search(r'(?:decision|choice|id|:)?\s*(\d)\b', after_json, re.IGNORECASE)
                    if digit_match and digit_match.group(1) in skill_map:
                        skill_name = skill_map[digit_match.group(1)]
                        parse_layer = "json_plus_digit"





                    
                    if skill_name:
                        parse_layer = "json"
                        # Reset warnings if JSON parsing succeeded
                        parsing_warnings = [w for w in parsing_warnings if "STRICT_MODE" not in w]
                
                # Extract Reasoning & Constructs
                reasoning = {
                    "strategy": data.get("strategy", ""),
                    "confidence": data.get("confidence", 1.0)
                }
                # Get construct mapping from config for dynamic matching
                construct_mapping = parsing_cfg.get("constructs", {}) if parsing_cfg else {}

                # Synonym Mapping (Now purely config-driven)
                # If 'synonyms' is defined in YAML, use it. Otherwise, no synonym expansion.
                SYNONYM_MAP = parsing_cfg.get("synonyms", {})




                for k, v in data.items():
                    if k.lower() in ["decision", "choice", "action", "strategy", "confidence"]:
                        continue
                    
                    # 1. Identify which constructs this JSON key 'k' might relate to
                    matched_names = []
                    k_normalized = k.lower().replace("_", " ").replace("-", " ")

                    for c_name, c_cfg in construct_mapping.items():
                        keywords = list(c_cfg.get("keywords", []))
                        
                        # Add internal synonyms for standard constructs
                        # Check if any synonym base (e.g., 'tp', 'sp') is in the construct name
                        for base_name, synonyms in SYNONYM_MAP.items():
                            if base_name.lower() in c_name.lower():
                                keywords.extend(synonyms)
                        
                        # Normalize keywords for matching
                        keywords_normalized = [kw.lower().replace("_", " ") for kw in keywords]
                        
                        # Check if JSON key matches any keyword
                        if any(kw in k_normalized for kw in keywords_normalized):
                            matched_names.append(c_name)
                    
                    # Also check if the key directly matches a construct name (case-insensitive)
                    for c_name in construct_mapping.keys():
                        c_name_norm = c_name.lower().replace("_", " ")
                        if c_name_norm in k_normalized or k_normalized in c_name_norm:
                            if c_name not in matched_names:
                                matched_names.append(c_name)


                    
                    # 2. Extract values based on structure
                    if isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            sub_k_lower = sub_k.lower()
                            # Nested mapping: check if sub-key is a label or reason
                            if "label" in sub_k_lower:
                                for name in [n for n in matched_names if "_LABEL" in n]:
                                    reasoning[name] = sub_v
                            elif any(rk in sub_k_lower for rk in ["reason", "why", "explanation", "because"]):
                                for name in [n for n in matched_names if "_REASON" in n]:
                                    reasoning[name] = sub_v
                            else:
                                reasoning[f"{k}_{sub_k}"] = sub_v
                    elif isinstance(v, (str, int, float)):
                        # Flattened string or value: assign to matched constructs
                        if matched_names:
                            for name in matched_names:
                                # For labels, if it's a string, we might want to extract just the label part
                                if "_LABEL" in name and isinstance(v, str):
                                    # Robust extraction using regex from config if available
                                    regex = construct_mapping[name].get("regex")
                                    if regex:
                                        # 1. Try full regex match (prefix + label)
                                        match = re.search(regex, v, re.IGNORECASE)
                                        if match and match.groups():
                                            reasoning[name] = match.group(1)
                                        else:
                                            # 2. Try to find any of the labels from the capture group alternatives
                                            # This handles cases where the key is already identified, but the value is a string containing the label
                                            # e.g. Regex: "(?:threat)[:\s]* (High|Low)" -> look for "High" or "Low" in v
                                            try:
                                                # Extract the alternatives from the first capture group if possible
                                                # Pattern usually looks like (A|B|C)
                                                inner_pattern = re.search(r'\(([^?].+?)\)', regex)
                                                if inner_pattern:
                                                    alternatives = [alt.strip() for alt in inner_pattern.group(1).split('|')]
                                                    # Sort by length descending to match "Very High" before "High"
                                                    alternatives.sort(key=len, reverse=True)
                                                    for alt in alternatives:
                                                        if alt.lower() in v.lower():
                                                            reasoning[name] = alt
                                                            break
                                                    else:
                                                        reasoning[name] = v
                                                else:
                                                    reasoning[name] = v
                                            except Exception:
                                                reasoning[name] = v
                                    else:
                                        reasoning[name] = v
                                else:
                                    reasoning[name] = v
                        else:
                            # Fallback: direct name match
                            k_upper = k.upper()
                            if k_upper in construct_mapping:
                                reasoning[k_upper] = v
                            else:
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
                            parse_layer = "keyword"
                            break
                        for s in valid_skills:
                            if s.lower() in raw_val:
                                skill_name = s
                                parse_layer = "keyword"
                                break
                if skill_name: break

        # 5. CONSTRUCT EXTRACTION (Regex based, applied to cleaned_target)
        constructs_cfg = parsing_cfg.get("constructs", {})
        if constructs_cfg and cleaned_target:
            for key, cfg in constructs_cfg.items():
                if key not in reasoning or not reasoning[key]:
                    regex = cfg.get("regex")
                    if regex:
                        match = re.search(regex, cleaned_target, re.IGNORECASE | re.DOTALL)
                        if match:
                            reasoning[key] = match.group(1).strip() if match.groups() else match.group(0).strip()

        # 6. LAST RESORT: Search for bracketed numbers [1-7] in cleaned_target
        # STRICT MODE: If enabled, do NOT use digit extraction (prevents bias from reasoning text)
        # This forces the system to retry with clearer instructions instead of guessing.
        strict_mode = parsing_cfg.get("strict_mode", True)
        
        if not skill_name:
            bracket_matches = re.findall(r'\[(\d)\]', cleaned_target)
            digit_matches = re.findall(r'(\d)', cleaned_target)
            candidates = bracket_matches if bracket_matches else digit_matches
            
            if candidates and not strict_mode:
                last_digit = candidates[-1]
                if last_digit in skill_map:
                    skill_name = skill_name or skill_map[last_digit]
                    parse_layer = parse_layer or "digit"
                    parsing_warnings.append(f"Last-resort extraction from digit: {last_digit}")
            elif candidates and strict_mode and not skill_name:
                # Log the failed parse attempt for audit but do NOT use the digit
                parsing_warnings.append(f"STRICT_MODE: Rejected digit extraction ({candidates[-1]}). Will trigger retry.")

        if not skill_name:
            if strict_mode:
                msg = f"STRICT_MODE: Failed to parse any valid decision for agent '{agent_id}'. Default fallback disabled."
                parsing_warnings.append(msg)
                logger.error(f" [Adapter:Error] {msg}")
                return None # Return None to trigger retry/abort in Broker
            else:
                skill_name = parsing_cfg.get("default_skill", "do_nothing")
                parse_layer = "default"
                parsing_warnings.append(f"Default skill '{skill_name}' used.")

        # Resolve to canonical ID via alias map
        skill_name = self.alias_map.get(skill_name.lower(), skill_name)

        # 7. Semantic Correlation Audit (Phase 20)
        # Check both T1 and T2/T3 memory storage patterns
        retrieved_memories = context.get("retrieved_memories") or context.get("memory")
        if not retrieved_memories and "personal" in context:
            retrieved_memories = context["personal"].get("memory")
            
        combined_reasoning = str(reasoning) + cleaned_target
        
        # 6. Correlation Audit (Standard)
        # ... (Existing logic) ...
        
        # 7. Demographic Grounding Audit (Phase 21)
        # Checks if qualitative anchors (Persona/History) are cited in reasoning
        demo_audit = self._audit_demographic_grounding(reasoning, context, parsing_cfg)
        reasoning["demographic_audit"] = demo_audit

        
        correlation_score = 0.0
        details = []
        if retrieved_memories and isinstance(retrieved_memories, list):
            # Domain-agnostic audit keywords
            audit_kws = list(parsing_cfg.get("audit_keywords", []))
            # Fallback if empty
            if not audit_kws:
                audit_kws = ["choice", "decision", "action", "reason", "because"]
            
            kws_pattern = r'\b(' + '|'.join([re.escape(k) for k in audit_kws]) + r')\b'
            
            for i, mem in enumerate(retrieved_memories):
                mem_text = str(mem).lower()
                # Focus on configured keywords
                kws = re.findall(kws_pattern, mem_text, re.IGNORECASE)
                if kws:
                    hits = [kw for kw in set(kws) if kw.lower() in combined_reasoning.lower()]
                    if hits:
                        correlation_score += (len(hits) / len(set(kws))) * (1.0 / len(retrieved_memories))
                        details.append(f"Mem[{i}] hits: {hits}")

        
        reasoning["semantic_correlation_audit"] = {
            "score": round(correlation_score, 2),
            "details": details[:3]
        }

        # 6. Post-Parsing Robustness: Completeness Check
        missing_labels = []
        if parsing_cfg and "constructs" in parsing_cfg:
            expected = set(parsing_cfg["constructs"].keys())
            found = set(reasoning.keys())
            missing = expected - found
            if missing:
                msg = f"Missing constructs for '{agent_type}': {list(missing)}"
                parsing_warnings.append(msg)
                logger.warning(f" [Adapter:Diagnostic] Warning: {msg}")
                # Check if any critical LABEL fields are missing - these should trigger retry
                missing_labels = [m for m in missing if "_LABEL" in m]
                if missing_labels:
                    parsing_warnings.append(f"CRITICAL: Missing LABEL constructs {missing_labels}. Triggering retry.")
        if parse_layer:
            logger.info(f" [Adapter:Audit] Agent {agent_id} | Layer: {parse_layer} | Warnings: {len(parsing_warnings)}")
            # Show reasoning summary
            strat = reasoning.get("strategy", "") or reasoning.get("reason", "")
            if strat:
                logger.debug(f"  - Reasoning: {strat[:120]}...")
            
            # Show construct classification (Generic)
            construct_parts = []
            for k, v in reasoning.items():
                if "_LABEL" in k:
                    construct_parts.append(f"{k.split('_')[0]}={v}")
            if construct_parts:
                logger.info(f"  - Constructs: {' | '.join(construct_parts)}")

        # 8. Skill Name Normalization (Cross-Model Fix)
        # Convert aliases like "HE", "FI", "insurance" to canonical names
        if skill_name:
            normalized = self.alias_map.get(skill_name.lower())
            if normalized:
                if normalized != skill_name:
                    logger.debug(f" [Adapter:Normalize] {skill_name} -> {normalized}")
                skill_name = normalized

        return SkillProposal(
            agent_id=agent_id,
            skill_name=skill_name,
            reasoning=reasoning,
            raw_output=raw_output,
            parsing_warnings=parsing_warnings,
            parse_layer=parse_layer
        )
        
    def _audit_demographic_grounding(self, reasoning: Dict, context: Dict, parsing_cfg: Dict = None) -> Dict:
        """
        Audit if the LLM cites the qualitative demographic anchors provided in context.
        Generic implementation: Looks for overlap between qualitative persona/history
        and the 'reasoning' fields.
        """

        if parsing_cfg is None:
            parsing_cfg = self.config
            
        score = 0.0
        cited_anchors = []
        
        # 1. Extract Target Anchors from Context
        # Source fields are configurable via 'audit_context_fields' in parsing config
        # Default fields are domain-agnostic
        default_fields = ["narrative_persona", "experience_summary"]
        context_fields = parsing_cfg.get("audit_context_fields", default_fields)
        sources = {field: context.get(field, "") for field in context_fields}

        # 2. Extract Keywords (Simple stopword filtering)
        # Generic English stopwords - domain-specific stopwords should be in config
        default_blacklist = {"you", "are", "a", "the", "in", "of", "to", "and", "with", "this", "that", "have", "from", "for", "on", "is", "it", "be", "as", "at", "by"}
        # Load additional stopwords from config (domain-specific terms)
        config_blacklist = set(parsing_cfg.get("audit_blacklist", []))
        blacklist = default_blacklist | config_blacklist
        # Topic words that are too generic to count as grounding
        # v1.1: Load from config 'audit_stopwords'
        topic_stopwords = set(parsing_cfg.get("audit_stopwords", ["decision", "choice", "action", "reason"]))
 
        
        anchors = set()
        
        for src_type, text in sources.items():
            if not text or text == "[N/A]": continue
            # Normalize and extract significant words
            clean_text = re.sub(r'[^\w\s]', ' ', text.lower()) 
            words = set(w for w in clean_text.split() if len(w) > 4 and w not in blacklist and w not in topic_stopwords)
            anchors.update(words)

        
        if not anchors:
            return {"score": 0.0, "details": "No anchors found in context"}
            
        # 3. Check Reasoning for Citations
        # Flatten reasoning to string
        reasoning_text = " ".join([str(v) for v in reasoning.values()]).lower()
        
        # Exact match or contained match? 
        # For years (2012), exact word boundary is needed: \b2012\b
        # For words, simple substring is risky ("income" in "outcome"). Use word boundaries.
        
        hit_anchors = []
        for a in anchors:
            if a and re.search(r'\b' + re.escape(str(a)) + r'\b', reasoning_text):
                hit_anchors.append(a)
        
        # 4. Scoring
        # 1 hit = 0.5 (Weak), 2+ hits = 1.0 (Strong)
        if len(hit_anchors) >= 2:
            score = 1.0
        elif len(hit_anchors) == 1:
            score = 0.5
            
        return {
            "score": score,
            "cited_anchors": hit_anchors,
            "total_anchors": list(anchors)
        }

    
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
    if not cleaned or len(cleaned) < 20 or re.match(r'^\[?N/A\]?$', cleaned, re.I):
        # Find think content
        think_match = re.search(r'<think>(.*?)(?:</think>|$)', text, flags=re.DOTALL)
        if think_match:
            inner = think_match.group(1).strip()
            
            # Look for the final answer section within think
            decision_patterns = [
                r'(final decision:?\s*\d+.*)',  # Numerical decision
                r'(final decision:?\s*\w+.*)',  # Named decision
                r'(selected action:?\s*.+)',     # Selected action
                r'(決策|decision)[:：]\s*(.+)',  # With Chinese/Global markers
            ]
            for pattern in decision_patterns:
                match = re.search(pattern, inner, re.IGNORECASE | re.DOTALL)
                if match:
                    return match.group(0).strip()
            
            # If inner has any decision-like content, take the end of it
            # This is a generic heuristic: look for trailing content that mentions decision keywords
            decision_kws = ['decide', 'decision', 'action', 'choice', 'id']
            if any(kw in inner.lower() for kw in decision_kws):
                return inner[-500:] if len(inner) > 500 else inner
            
            # Return inner if cleaned is empty
            if not cleaned and inner:
                return inner
    
    # Final check: if it's literally [N/A], try to keep it for the alias map to find
    return cleaned if cleaned else text # Fallback to original text if everything failed


class SmartRepairPreprocessor:
    """
    Generalized preprocessor to repair common LLM JSON errors.
    Automatically quotes unquoted string values and repairs common syntax issues.
    """
    def __init__(self, specific_values: List[str] = None):
        self.specific_values = [v.upper() for v in specific_values] if specific_values else None

    def __call__(self, text: str) -> str:
        if not text: return ""
        
        # 1. Quote unquoted string values (Generalized)
        # Pattern: "key": Value -> "key": "Value"
        # Excludes: true, false, null, and numbers
        if self.specific_values:
            # If specific labels are provided (like VL, L, M, H, VH)
            labels = "|".join(re.escape(v) for v in self.specific_values)
            text = re.sub(rf'([\'"]?\w+[\'"]?):\s*({labels})\b(?![@\w\'"])', r'\1: "\2"', text, flags=re.IGNORECASE)
        else:
            # Fully generic: Quote any word-like value that isn't true/false/null/number
            # Pattern looks for : followed by an identifier that isn't a known JSON constant or number
            def quote_match(match):
                key_part = match.group(1)
                val = match.group(2)
                if val.lower() in ["true", "false", "null"] or re.match(r'^-?\d+(\.\d+)?$', val):
                    return f'{key_part}: {val}'
                return f'{key_part}: "{val}"'
            
            text = re.sub(r'([\'"]?\w+[\'"]?):\s*([a-zA-Z_][\w-]*)\b(?![@\w\'"])', quote_match, text)

        # 2. Quote unquoted numeric IDs specifically for decision/choice keys
        # Some models use: decision: 4 (unquoted)
        text = re.sub(r'([\'"]?(?:decision|choice|action)[\'"]?):\s*(\d)\b(?![@\w\'"])', r'\1: "\2"', text, flags=re.IGNORECASE)
        
        # 3. Fix common missing commas
        text = re.sub(r'("[\'"]?)\s*\n\s*(["\'\w])', r'\1,\n\2', text)
        
        return text


def json_extract_preprocessor(text: str) -> str:



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
