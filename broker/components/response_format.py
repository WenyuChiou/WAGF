"""
Response Format Builder - Generates LLM response format instructions from YAML config.

This module enables modular, YAML-driven response format generation,
allowing experiments to define their own output structures without code changes.

Task-041: Added framework-aware rating scale support.
"""

from typing import Dict, Any, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from broker.interfaces.rating_scales import RatingScaleRegistry


class ResponseFormatBuilder:
    """
    Generates response format instructions from YAML config.

    Usage:
        config = load_agent_config().get("my_agent_type")
        rfb = ResponseFormatBuilder(config, framework="pmt")
        format_block = rfb.build(valid_choices_text="1, 2, or 3")
    """

    def __init__(
        self,
        config: Dict[str, Any],
        shared_config: Dict[str, Any] = None,
        framework: str = "pmt",
        scale_registry: Optional["RatingScaleRegistry"] = None,
    ):
        """
        Initialize with agent-type config.

        Args:
            config: Agent-type specific config from YAML
            shared_config: Shared config section for defaults
            framework: Psychological framework ("pmt", "utility", "financial")
            scale_registry: Optional custom RatingScaleRegistry
        """
        self.config = config
        self.shared = shared_config or {}
        self.framework = framework.lower()
        self._scale_registry = scale_registry

    @property
    def scale_registry(self):
        """Lazy-load RatingScaleRegistry to avoid circular imports."""
        if self._scale_registry is None:
            from broker.interfaces.rating_scales import RatingScaleRegistry
            self._scale_registry = RatingScaleRegistry
        return self._scale_registry

    def _get_labels_for_framework(self, framework_override: str = None) -> str:
        """
        Get rating scale labels for framework.

        Args:
            framework_override: Optional framework to use instead of default

        Returns:
            Label string like "VL/L/M/H/VH" or "L/M/H"
        """
        target_framework = framework_override or self.framework

        # 1. Try framework-specific from shared config
        scales = self.shared.get("rating_scales", {})
        if target_framework in scales:
            levels = scales[target_framework].get("levels", [])
            if levels:
                return "/".join(levels)

        # 2. Use registry
        from broker.interfaces.rating_scales import FrameworkType
        try:
            fw = FrameworkType(target_framework)
            scale = self.scale_registry.get(fw)
            return scale.format_labels()
        except (ValueError, KeyError):
            pass

        # 3. Default PMT fallback
        return "VL/L/M/H/VH"

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

        # Get framework-appropriate labels
        default_labels = self._get_labels_for_framework()

        # Build JSON structure
        lines = [delimiter_start, "{"]

        for i, field in enumerate(fields):
            key = field["key"]
            ftype = field.get("type", "text")
            is_last = (i == len(fields) - 1)
            comma = "" if is_last else ","
            desc = field.get("description", "")

            if ftype == "appraisal":
                # Use custom reason hint if provided
                reason_hint = field.get("reason_hint", "...")

                # Use per-field scale if specified, otherwise use framework default
                field_scale = field.get("scale")
                if field_scale and field_scale != self.framework:
                    # Field has a different scale (rare case)
                    field_labels = self._get_labels_for_framework(field_scale)
                else:
                    field_labels = default_labels

                lines.append(f'  "{key}": {{"label": "{field_labels}", "reason": "{reason_hint}"}}{comma}')

            elif ftype == "choice":
                # Emphasize numeric ID to guide model away from string labels
                # P2 fix: removed square brackets that misled small models (gemma3:1b)
                # into outputting JSON arrays instead of a single integer
                placeholder = desc if desc else f"Numeric ID, choose ONE from: {valid_choices_text}"
                lines.append(f'  "{key}": "<{placeholder}>"{comma}')

            elif ftype == "secondary_choice":
                # Multi-skill: optional secondary action (only rendered when multi_skill.enabled)
                placeholder = desc if desc else f"OPTIONAL: Numeric ID from: {valid_choices_text}, or 0 for none"
                lines.append(f'  "{key}": "<{placeholder}>"{comma}')

            elif ftype == "numeric":
                # Flexible numeric fields with unit, sign, and range support
                placeholder = self._build_numeric_placeholder(field)
                lines.append(f'  "{key}": "{placeholder}"{comma}')

            elif ftype == "text":
                placeholder = desc if desc else "..."
                lines.append(f'  "{key}": "{placeholder}"{comma}')

            else:  # fallback for unknown types
                lines.append(f'  "{key}": "..."{comma}')

        lines.append("}")
        lines.append(delimiter_end)

        return "\n".join(lines)

    def _build_numeric_placeholder(self, field: Dict[str, Any]) -> str:
        """
        Build a flexible placeholder string for numeric fields.
        
        Supports:
            - min/max: Range constraints (e.g., 1-30)
            - unit: Unit of measurement (e.g., "meters", "percent", "%")
            - sign: Allowed signs ("positive_only", "negative_only", "both")
            - description: Custom description to override auto-generated text
        
        Examples in YAML:
            # Simple percentage
            - { key: "magnitude_pct", type: "numeric", min: 1, max: 30, unit: "%" }
            # → "Enter a number: 1-30%"
            
            # Meters with sign
            - { key: "elevation_change", type: "numeric", min: 0, max: 5, unit: "meters", sign: "both" }
            # → "Enter a number: +/- 0-5 meters"
            
            # Custom description overrides everything
            - { key: "budget", type: "numeric", description: "Your budget in USD (1000-50000)" }
            # → "Your budget in USD (1000-50000)"
        """
        # 1. If explicit description is provided, use it directly
        desc = field.get("description")
        if desc:
            return desc
        
        # 2. Build auto-generated placeholder
        min_val = field.get("min")
        max_val = field.get("max")
        unit = field.get("unit", "")
        sign = field.get("sign", "positive_only")  # positive_only, negative_only, both
        
        # Build range string
        if min_val is not None and max_val is not None:
            range_str = f"{min_val}-{max_val}"
        elif min_val is not None:
            range_str = f">={min_val}"
        elif max_val is not None:
            range_str = f"<={max_val}"
        else:
            range_str = ""
        
        # Build sign prefix
        if sign == "both":
            sign_prefix = "+/- "
        elif sign == "negative_only":
            sign_prefix = "- "
        else:  # positive_only
            sign_prefix = ""
        
        # Build unit suffix
        unit_suffix = f" {unit}" if unit and unit not in ("%", "°", "°C", "°F") else unit
        
        # Compose final placeholder
        if range_str:
            return f"Enter a number: {sign_prefix}{range_str}{unit_suffix}"
        else:
            return f"Enter a number{unit_suffix}"

    def get_required_fields(self) -> List[str]:
        """Get list of required field keys for validation."""
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        fields = fmt.get("fields", [])
        return [f["key"] for f in fields if f.get("required", False)]

    def get_field_types(self) -> Dict[str, str]:
        """Get mapping of field key to field type (e.g. 'appraisal', 'text', 'numeric')."""
        fmt = self.config.get("response_format", self.shared.get("response_format", {}))
        fields = fmt.get("fields", [])
        return {f["key"]: f.get("type", "text") for f in fields}

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

    def get_valid_levels(self) -> List[str]:
        """Get valid rating levels for the current framework."""
        from broker.interfaces.rating_scales import FrameworkType
        try:
            fw = FrameworkType(self.framework)
            scale = self.scale_registry.get(fw)
            return scale.levels
        except (ValueError, KeyError):
            return ["VL", "L", "M", "H", "VH"]


def create_response_format_builder(
    agent_type: str,
    config_path: str = None,
    framework: str = None,
) -> ResponseFormatBuilder:
    """
    Factory function to create ResponseFormatBuilder from agent type.

    Args:
        agent_type: The agent type (e.g., "household")
        config_path: Optional path to agent_types.yaml
        framework: Optional framework override (defaults to agent type's framework)

    Returns:
        Configured ResponseFormatBuilder instance
    """
    from broker.utils.agent_config import load_agent_config

    cfg = load_agent_config(config_path)
    agent_config = cfg.get(agent_type)
    shared_config = {
        "response_format": cfg.get_shared("response_format", {}),
        "rating_scales": cfg._config.get("shared", {}).get("rating_scales", {})
    }

    # Determine framework
    if framework is None:
        framework = cfg.get_framework_for_agent_type(agent_type)

    return ResponseFormatBuilder(
        agent_config,
        shared_config,
        framework=framework
    )
