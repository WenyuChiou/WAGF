"""
Response Format Builder - Generates LLM response format instructions from YAML config.

This module enables modular, YAML-driven response format generation,
allowing experiments to define their own output structures without code changes.
"""

from typing import Dict, Any, List, Optional


class ResponseFormatBuilder:
    """
    Generates response format instructions from YAML config.
    
    Usage:
        config = load_agent_config().get("household")
        rfb = ResponseFormatBuilder(config)
        format_block = rfb.build(valid_choices_text="1, 2, or 3")
    """
    
    def __init__(self, config: Dict[str, Any], shared_config: Dict[str, Any] = None):
        """
        Initialize with agent-type config.
        
        Args:
            config: Agent-type specific config (e.g., household)
            shared_config: Shared config section for defaults
        """
        self.config = config
        self.shared = shared_config or {}
    
    def build(self, valid_choices_text: str = "1, 2, or 3") -> str:
        """
        Generate the response format block for prompt injection.
        
        Returns a formatted string like:
            <<<DECISION_START>>>
            {
              "threat_appraisal": {"label": "VL/L/M/H/VH", "reason": "..."},
              ...
            }
            <<<DECISION_END>>>
        """
        # Get format config (agent-specific overrides shared)
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        
        if not fmt:
            return ""  # No response format defined, use template as-is
        
        delimiter_start = fmt.get("delimiter_start", "<<<DECISION_START>>>")
        delimiter_end = fmt.get("delimiter_end", "<<<DECISION_END>>>")
        fields = fmt.get("fields", [])
        
        if not fields:
            return ""
        
        # Build JSON structure
        lines = [delimiter_start, "{"]
        
        for i, field in enumerate(fields):
            key = field["key"]
            ftype = field.get("type", "text")
            is_last = (i == len(fields) - 1)
            comma = "" if is_last else ","
            
            if ftype == "appraisal":
                # Use custom reason hint if provided
                reason_hint = field.get("reason_hint", "...")
                lines.append(f'  "{key}": {{"label": "VL/L/M/H/VH", "reason": "{reason_hint}"}}{comma}')
            elif ftype == "choice":
                lines.append(f'  "{key}": {valid_choices_text}{comma}')
            else:  # text
                lines.append(f'  "{key}": "..."{comma}')
        
        lines.append("}")
        lines.append(delimiter_end)
        
        return "\n".join(lines)
    
    def get_required_fields(self) -> List[str]:
        """Get list of required field keys for validation."""
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        fields = fmt.get("fields", [])
        return [f["key"] for f in fields if f.get("required", False)]
    
    def get_construct_mapping(self) -> Dict[str, str]:
        """
        Map response field keys to construct names for validation.
        
        Example: {"threat_appraisal": "TP_LABEL", "coping_appraisal": "CP_LABEL"}
        """
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        fields = fmt.get("fields", [])
        mapping = {}
        for f in fields:
            if f.get("construct"):
                mapping[f["key"]] = f["construct"]
        return mapping
    
    def get_delimiters(self) -> tuple:
        """Get start and end delimiters for parsing."""
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        return (
            fmt.get("delimiter_start", "<<<DECISION_START>>>"),
            fmt.get("delimiter_end", "<<<DECISION_END>>>")
        )


def create_response_format_builder(agent_type: str, config_path: str = None) -> ResponseFormatBuilder:
    """
    Factory function to create ResponseFormatBuilder from agent type.
    
    Args:
        agent_type: The agent type (e.g., "household")
        config_path: Optional path to agent_types.yaml
    
    Returns:
        Configured ResponseFormatBuilder instance
    """
    from broker.utils.agent_config import load_agent_config
    
    cfg = load_agent_config(config_path)
    agent_config = cfg.get(agent_type)
    shared_config = {"response_format": cfg.get_shared("response_format", {})}
    
    return ResponseFormatBuilder(agent_config, shared_config)
