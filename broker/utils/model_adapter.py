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

# Pre-compiled regex patterns for hot-path operations
_THINK_TAG_RE = re.compile(r'<think>.*?</think>', re.DOTALL)

from ..interfaces.skill_types import SkillProposal
from ..utils.logging import logger
from .preprocessors import GenericRegexPreprocessor, SmartRepairPreprocessor, get_preprocessor
from .adapters.deepseek import deepseek_preprocessor

# Universal framework-level normalization defaults
# (Domain-independent mappings only)
# Universal framework-level normalization defaults
# (Domain-independent mappings only)
FRAMEWORK_NORMALIZATION_MAP = {
    # PMT Scale (Threat/Coping Perception) - Embedded per User Request
    "very low": "VL", "verylow": "VL", "v low": "VL", "v.low": "VL",
    "low": "L",
    "medium": "M", "med": "M", "moderate": "M", "mid": "M", "middle": "M",
    "high": "H", "hi": "H",
    "very high": "VH", "veryhigh": "VH", "v high": "VH", "v.high": "VH",

    # Boolean variations
    "true": "True", "yes": "True", "1": "True", "on": "True",
    "false": "False", "no": "False", "0": "False", "off": "False",
}

def normalize_construct_value(value: str, allowed_values: Optional[List[str]] = None, custom_mapping: Optional[Dict[str, str]] = None) -> str:
    """
    Normalize common LLM output variations to canonical forms.

    Args:
        value: Raw value from LLM
        allowed_values: Optional list of allowed values to check against
        custom_mapping: Optional agent-specific mapping (e.g., from config)

    Returns:
        Normalized value if found in mappings, otherwise original value
    """
    if not isinstance(value, str):
        return value

    normalized = value.strip()
    lower_val = normalized.lower()

    # 1. Try agent-specific custom mapping (highest priority)
    if custom_mapping and lower_val in custom_mapping:
        normalized = custom_mapping[lower_val]
    # 2. Try universal framework defaults
    elif lower_val in FRAMEWORK_NORMALIZATION_MAP:
        normalized = FRAMEWORK_NORMALIZATION_MAP[lower_val]

    # 3. If allowed_values provided, check case-insensitive match
    if allowed_values:
        for allowed in allowed_values:
            if normalized.lower() == allowed.lower():
                return allowed

    return normalized


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
            agent_type: Type of agent (e.g., "trader", "manager", "consumer")
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
        # Build alias map from config (e.g., "ACT1" -> "action_alpha", "ACT2" -> "action_beta")
        self.alias_map = self.agent_config.get_action_alias_map(agent_type)
            
    def _get_preprocessor_for_type(self, agent_type: str) -> Callable[[str], str]:
        """Get preprocessor for a specific agent type."""
        try:
            is_identity = (self._preprocessor.__name__ == "<lambda>" and self._preprocessor("") == "")
        except (AttributeError, TypeError):
            is_identity = False
            
        if not is_identity:
            return self._preprocessor
                
        p_cfg = self.agent_config.get_parsing_config(agent_type).get("preprocessor", {})
        if p_cfg:
            return get_preprocessor(p_cfg)
        return self._preprocessor

    def _is_list_item(self, text: str, start: int, end: int) -> bool:
        """Helper to determine if a matched token is part of an option list like VL/L/M."""
        if start < 0 or end > len(text):
            return False

        # Load delimiters from config (framework default if missing)
        list_chars = self.config.get("list_delimiters", ['/', '|', '\\'])

        # Check trailing context (ignoring spaces AND optional quotes from preprocessor)
        next_char_idx = end
        while next_char_idx < len(text) and (text[next_char_idx].isspace() or text[next_char_idx] in ['"', "'"]):
            next_char_idx += 1

        # Check preceding context
        prev_char_idx = start - 1
        while prev_char_idx >= 0 and (text[prev_char_idx].isspace() or text[prev_char_idx] in ['"', "'"]):
            prev_char_idx -= 1

        # Indicators of a list: slashes or pipes
        if next_char_idx < len(text) and text[next_char_idx] in list_chars:
            return True
        if prev_char_idx >= 0 and text[prev_char_idx] in list_chars:
            return True
        return False

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
        # Dynamic alias map per agent_type (not self.alias_map which may be stale)
        alias_map = self.agent_config.get_action_alias_map(agent_type)
        
        # 0. Initialize results
        skill_name = None
        reasoning = {}
        parsing_warnings = []
        # Phase 0.3: Retrieve agent-specific normalization map
        custom_mapping = parsing_cfg.get("normalization", {})
        proximity_window = parsing_cfg.get("proximity_window", 35)

        # Track which parsing method succeeded (enclosure/json/keyword/digit/default)
        parse_layer = ""
        parse_confidence = 0.0
        construct_completeness = 0.0
        parse_metadata = {
            "parse_layer": "",
            "parse_confidence": 0.0,
            "construct_completeness": 0.0,
        }

        # Phase 15: Early return for empty output
        if not raw_output:
            return None

        # Phase 46: Strip Qwen3 thinking tokens before parsing
        # Qwen3 models wrap reasoning in <think>...</think> tags
        import re
        raw_output = _THINK_TAG_RE.sub('', raw_output).strip()
        if not raw_output:
            return None  # Only thinking tokens, no actual response

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
        except (ImportError, AttributeError, Exception):
            dynamic_pattern = None

        patterns = [
            dynamic_pattern,
            r"<<<DECISION_START>>>\s*(.*?)\s*<<<DECISION_END>>>",
            r"<decision>\s*(.*?)\s*</decision>",
            r"(?:decision|choice|selected_action)[:\s]*({.*?})", # Find JSON-like block after keyword
            r"({.*})", # Final fallback: Find any JSON-like block
        ]
        
        target_content = raw_output
        is_enclosed = False
        for pattern in [p for p in patterns if p]:
            match = re.search(pattern, raw_output, re.DOTALL | re.IGNORECASE)
            if match:
                target_content = match.group(1)
                parse_layer = "enclosure"
                is_enclosed = True
                break

        # 2. Preprocess target
        cleaned_target = preprocessor(target_content)
        
        # 3. ATTEMPT JSON PARSING
        _magnitude_pct = None  # Optional magnitude for Group D experiments
        found_json = False
        try:
            json_text = cleaned_target.strip()
            if "{" in json_text:
                json_text = json_text[json_text.find("{"):json_text.rfind("}")+1]
            
            # Preprocessor Failsafe: Handle double-braces mimicry from small models
            if json_text.startswith("{{") and json_text.endswith("}}"):
                json_text = json_text[1:-1]
            
            json_text = json_text.replace("{{", "{").replace("}}", "}")
            json_text = re.sub(r',\s*([\]}])', r'\1', json_text)
                
            data = json.loads(json_text)
            if isinstance(data, dict):
                found_json = True
                parse_layer = f"{parse_layer}+json" if is_enclosed else "json"
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

                    # Case 0b: List/array (small models like gemma3:1b output [2, 3, 4])
                    # Take the first element as the primary decision
                    if isinstance(decision_val, list) and decision_val:
                        decision_val = decision_val[0]

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
                
                # Extract magnitude (optional, for irrigation Group D)
                magnitude_raw = data_lowered.get("magnitude") or data_lowered.get("magnitude_pct")
                if magnitude_raw is not None:
                    try:
                        _mag = float(magnitude_raw)
                        if _mag < 0:
                            parsing_warnings.append(f"Negative magnitude {_mag}% ignored")
                        else:
                            _magnitude_pct = min(_mag, 100.0)
                            if _mag > 100:
                                parsing_warnings.append(f"Magnitude {_mag}% clamped to 100%")
                    except (ValueError, TypeError):
                        parsing_warnings.append(f"Non-numeric magnitude: {magnitude_raw}")

                # RECOVERY: If JSON parsed but no decision found, look for "Naked Digit" after the JSON block
                if not skill_name:
                    after_json = cleaned_target[cleaned_target.rfind("}")+1:].strip()
                    # Look for digits at start OR with some context (like "Decision: 4")
                    digit_match = re.search(r'(?:decision|choice|id|:)?\s*(\d)\b', after_json, re.IGNORECASE)
                    if digit_match and digit_match.group(1) in skill_map:
                        skill_name = skill_map[digit_match.group(1)]
                        parse_layer = "json_plus_digit"





                    
                if skill_name:
                    # Reset warnings if JSON parsing succeeded (even with digit recovery)
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
                                    reasoning[name] = normalize_construct_value(sub_v, custom_mapping=custom_mapping)
                            elif any(rk in sub_k_lower for rk in ["reason", "why", "explanation", "because"]):
                                for name in [n for n in matched_names if "_REASON" in n]:
                                    reasoning[name] = sub_v
                            else:
                                reasoning[f"{k}_{sub_k}"] = normalize_construct_value(sub_v, custom_mapping=custom_mapping)
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

                                                    # First try direct match
                                                    matched = False
                                                    for alt in alternatives:
                                                        if alt.lower() in v.lower():
                                                            reasoning[name] = alt
                                                            matched = True
                                                            break

                                                    # If not matched, try normalization
                                                    if not matched:
                                                        normalized = normalize_construct_value(v, alternatives, custom_mapping=custom_mapping)
                                                        if normalized.upper() in [a.upper() for a in alternatives]:
                                                            reasoning[name] = normalized
                                                        # else: Leave empty, let CONSTRUCT EXTRACTION handle it
                                                else:
                                                    # No alternatives to match against, try normalization
                                                    reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                            except Exception:
                                                reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                    else:
                                        reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                                else:
                                    reasoning[name] = normalize_construct_value(v, custom_mapping=custom_mapping)
                        else:
                            # Fallback: direct name match
                            k_upper = k.upper()
                            if k_upper in construct_mapping:
                                reasoning[k_upper] = normalize_construct_value(v, custom_mapping=custom_mapping)
                            else:
                                reasoning[k] = normalize_construct_value(v, custom_mapping=custom_mapping)
        except (json.JSONDecodeError, AttributeError):
            pass

        # 4. KEYWORD SEARCH (Fallback if JSON resolution failed)
        if not skill_name:
            kw_res = self._parse_keywords(cleaned_target, agent_type, context)
            if kw_res:
                skill_name = kw_res.get("skill_name")
                # Merge keyword reasoning if json failed
                if not reasoning.get("strategy"):
                    reasoning.update(kw_res.get("reasoning", {}))
                parse_layer = f"{parse_layer}+keyword" if is_enclosed else "keyword"

        # 5. NAKED DIGIT SEARCH (Last Resort)
        if not skill_name:
            digit_match = re.search(r'\b(\d)\b', cleaned_target)
            if digit_match and digit_match.group(1) in skill_map:
                skill_name = skill_map[digit_match.group(1)]
                parse_layer = f"{parse_layer}+digit" if is_enclosed else "digit"

        # 6. CONSTRUCT EXTRACTION (Regex based, applied to cleaned_target)
        constructs_cfg = parsing_cfg.get("constructs", {})
        if constructs_cfg and cleaned_target:
            for key, cfg in constructs_cfg.items():
                if key not in reasoning or not reasoning[key]:
                    regex = cfg.get("regex")

                    keywords = cfg.get("keywords", [])
                    if regex and keywords:
                        # 1. Find all keywords and their positions
                        kw_pattern = "|".join([re.escape(kw) for kw in keywords])
                        # Look for keyword with word boundaries
                        kw_matches = list(re.finditer(rf"(?i)\b(?:{kw_pattern})\b", cleaned_target))
                        
                        # Process keywords in reverse (prioritize mentions near the end)
                        found = False
                        for kw_match in reversed(kw_matches):
                            # 2. Look at text following the keyword (up to proximity_window chars gap)
                            start_search = kw_match.end()
                            end_search = min(start_search + proximity_window, len(cleaned_target))
                            gap_text = cleaned_target[start_search:end_search]
                            
                            # 3. Check for values in this gap - pick the FIRST match which is most adjacent
                            # Attempt 1: Exact code match (VL, L, M, H, VH) 
                            val_matches = list(re.finditer(regex, gap_text, re.IGNORECASE | re.DOTALL))
                            for val_match in val_matches:
                                temp_val = val_match.group(1).strip() if val_match.groups() else val_match.group(0).strip()
                                g_start = start_search + val_match.start()
                                g_end = start_search + val_match.end()
                                
                                # Only accept if it's NOT just an item in an echoed list
                                if not self._is_list_item(cleaned_target, g_start, g_end):
                                    reasoning[key] = normalize_construct_value(temp_val, custom_mapping=custom_mapping)
                                    found = True
                                    break
                            
                            if not found:
                                # Attempt 2: Search for long-form names (e.g. "Medium") in this gap
                                # Collect all matches to pick the one closest to the keyword
                                word_matches = []
                                for word, code in custom_mapping.items():
                                    if len(word) > 2: # Stick to descriptive labels
                                        for m in re.finditer(rf"\b{re.escape(word)}\b", gap_text, re.IGNORECASE):
                                            word_matches.append((m.start(), m.end(), code))
                                
                                if word_matches:
                                    # Sort by start index and pick the first one that passes the list guard
                                    word_matches.sort()
                                    for w_start, w_end, code in word_matches:
                                        g_start = start_search + w_start
                                        g_end = start_search + w_end
                                        if not self._is_list_item(cleaned_target, g_start, g_end):
                                            reasoning[key] = code
                                            found = True
                                            break
                                            
                            if found: break



        # 6. LAST RESORT: Search for bracketed numbers [1-7] in cleaned_target
        # STRICT MODE: If enabled, do NOT use digit extraction (prevents bias from reasoning text)
        # This forces the system to retry with clearer instructions instead of guessing.
        strict_mode = parsing_cfg.get("strict_mode", True)
        
        if not skill_name:
            bracket_matches = re.findall(r'\[(\d)\]', cleaned_target)
            digit_matches = re.findall(r'(\d)', cleaned_target)
            candidates = bracket_matches if bracket_matches else digit_matches
            
            # Allow digit extraction as last resort during retries even in strict mode
            is_retry = context.get("retry_attempt", 0) > 0
            
            if candidates and (not strict_mode or is_retry):
                last_digit = candidates[-1]
                if last_digit in skill_map:
                    skill_name = skill_name or skill_map[last_digit]
                    parse_layer = parse_layer or "digit_fallback"
                    parsing_warnings.append(f"Retry-based extraction from digit: {last_digit}")
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

        # Resolve to canonical ID via alias map (dynamic per agent_type)
        skill_name = alias_map.get(skill_name.lower(), skill_name)

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
            year = context.get("current_year", "?")
            logger.info(f" [Year {year}] [Adapter:Audit] Agent {agent_id} | Layer: {parse_layer} | Warnings: {len(parsing_warnings)}")
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

        # 7. Final Polish: Ensure all _LABEL values are normalized before returning
        for k in list(reasoning.keys()):
            if "_LABEL" in k:
                reasoning[k] = normalize_construct_value(str(reasoning[k]), custom_mapping=custom_mapping)

        # 8. Skill Name Normalization (Cross-Model Fix)
        # Convert aliases like "HE", "FI", "insurance" to canonical names
        if skill_name:
            normalized = alias_map.get(skill_name.lower())
            if normalized:
                if normalized != skill_name:
                    logger.debug(f" [Adapter:Normalize] {skill_name} -> {normalized}")
                skill_name = normalized

        # 9. Parse metadata (confidence + construct completeness)
        base_layer = "fallback"
        if "json" in parse_layer:
            base_layer = "json"
            parse_confidence = 0.95
        elif "keyword" in parse_layer:
            base_layer = "keyword"
            parse_confidence = 0.70
        elif "digit" in parse_layer:
            base_layer = "digit"
            parse_confidence = 0.50
        elif parse_layer == "default":
            base_layer = "fallback"
            parse_confidence = 0.20

        required_constructs = ["TP_LABEL", "CP_LABEL", "decision"]
        found = 0
        for construct in required_constructs:
            if construct in reasoning:
                found += 1
                continue
            if construct == "decision" and skill_name:
                found += 1
                continue
        construct_completeness = found / len(required_constructs)

        parse_metadata["parse_layer"] = base_layer
        parse_metadata["parse_confidence"] = parse_confidence
        parse_metadata["construct_completeness"] = construct_completeness
        reasoning["_parse_metadata"] = parse_metadata

        return SkillProposal(
            agent_id=agent_id,
            skill_name=skill_name,
            reasoning=reasoning,
            raw_output=raw_output,
            parsing_warnings=parsing_warnings,
            parse_layer=parse_layer,
            parse_confidence=parse_confidence,
            construct_completeness=construct_completeness,
            magnitude_pct=_magnitude_pct,
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

        # Short-circuit: skip keyword extraction if all sources are empty/N/A
        if not any(v and v != "[N/A]" for v in sources.values()):
            return {"score": 0.0, "details": "No anchors found in context"}

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

    def _parse_keywords(self, text: str, agent_type: str, context: Dict[str, Any] = None) -> Optional[Dict[str, Any]]:
        """
        Fallback keyword/regex based parsing.
        """
        parsing_cfg = self.agent_config.get_parsing_config(agent_type)
        if not parsing_cfg: return None

        keywords = parsing_cfg.get("decision_keywords", ["decision:", "choice:", "selected_action:"])
        valid_skills = self.agent_config.get_valid_actions(agent_type)
        skill_map = self.agent_config.get_skill_map(agent_type, context)
        
        lines = text.split('\n')
        for line in lines:
            line_lower = line.strip().lower()
            for kw in keywords:
                if kw.lower() in line_lower:
                    raw_val = line_lower.split(kw.lower())[1].strip()
                    # 1. Try Digit in keyword line
                    digit_match = re.search(r'(\d)', raw_val)
                    if digit_match and digit_match.group(1) in skill_map:
                        return {"skill_name": skill_map[digit_match.group(1)], "reasoning": {}}
                    # 2. Try mapping
                    for s in valid_skills:
                        if s.lower() in raw_val:
                            return {"skill_name": s, "reasoning": {}}
        return None

    
    def format_retry_prompt(self, original_prompt: str, errors: List[Any], max_reports: Optional[int] = None) -> str:
        """
        Format retry prompt with validation errors or InterventionReports.
        
        Supports both legacy List[str] errors and new List[InterventionReport] for XAI.
        """
        from ..interfaces.skill_types import InterventionReport
        
        if max_reports and len(errors) > max_reports:
            logger.warning(f" [Adapter] Truncating retry reports from {len(errors)} to {max_reports} to save context.")
            errors = errors[:max_reports]
            truncated = True
        else:
            truncated = False

        error_lines = []
        for e in errors:
            if isinstance(e, InterventionReport):
                error_lines.append(e.to_prompt_string())
            elif isinstance(e, str):
                error_lines.append(f"- {e}")
            else:
                error_lines.append(f"- {str(e)}")
        
        if truncated:
            error_lines.append(f"\n[!NOTE] There were more issues detected, but only the top {max_reports} are shown for brevity. Please fix these first.")
        
        error_text = "\n".join(error_lines)
        return f"""Your previous response was flagged by the governance layer.

**Issues Detected:**
{error_text}

Please reconsider your decision. Ensure your new response addresses the violations above.

{original_prompt}"""


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def get_adapter(model_name: str, config_path: str = None) -> ModelAdapter:
    """
    Get the appropriate adapter for a model.
    
    Uses UnifiedAdapter with model-specific preprocessor if needed.
    """
    model_lower = model_name.lower()
    
    # DeepSeek models use <think> tags
    if 'deepseek' in model_lower:
        return UnifiedAdapter(preprocessor=deepseek_preprocessor, config_path=config_path)
    
    # All other models use standard adapter
    # (Llama, Gemma, GPT-OSS, OpenAI, Anthropic, etc.)
    return UnifiedAdapter(config_path=config_path)



# =============================================================================
# LEGACY ALIASES (for backward compatibility)
# =============================================================================

class OllamaAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass


class OpenAIAdapter(UnifiedAdapter):
    """Alias for UnifiedAdapter (backward compatibility)."""
    pass
