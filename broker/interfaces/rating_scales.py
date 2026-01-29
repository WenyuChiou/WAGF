"""
Framework-Aware Rating Scale System.

Provides dataclasses and registry for psychological framework-specific rating scales.
Supports PMT (5-level), Utility (3-level), and Financial (3-level) frameworks.

Task-041: Universal Prompt/Context/Governance Framework
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from enum import Enum


class FrameworkType(str, Enum):
    """Supported psychological frameworks."""
    PMT = "pmt"
    UTILITY = "utility"
    FINANCIAL = "financial"
    GENERIC = "generic"


@dataclass
class RatingScale:
    """
    Framework-specific rating scale definition.

    Attributes:
        framework: The psychological framework this scale belongs to
        levels: Valid rating levels (e.g., ["VL", "L", "M", "H", "VH"])
        labels: Human-readable descriptions for each level
        template: Full text template for prompt injection
        numeric_range: Optional numeric range for utility/financial frameworks
    """
    framework: FrameworkType
    levels: List[str]
    labels: Dict[str, str]
    template: str
    numeric_range: Optional[Tuple[float, float]] = None

    def format_labels(self) -> str:
        """
        Format labels for prompt injection.

        Returns:
            Label string like "VL/L/M/H/VH" or "L/M/H"
        """
        return "/".join(self.levels)

    def validate_value(self, value: str) -> bool:
        """
        Check if value is valid for this scale.

        Args:
            value: The value to validate (case-insensitive)

        Returns:
            True if value is a valid level for this scale
        """
        return value.upper() in [level.upper() for level in self.levels]

    def get_label_description(self, level: str) -> str:
        """
        Get human-readable description for a level.

        Args:
            level: The level code (e.g., "VH")

        Returns:
            Human-readable description (e.g., "Very High")
        """
        return self.labels.get(level.upper(), level)

    def get_level_index(self, level: str) -> int:
        """
        Get numeric index for a level (0-based).

        Args:
            level: The level code

        Returns:
            Index position, or -1 if not found
        """
        level_upper = level.upper()
        for i, l in enumerate(self.levels):
            if l.upper() == level_upper:
                return i
        return -1

    def is_above_threshold(self, value: str, threshold: str) -> bool:
        """
        Check if value is at or above a threshold level.

        Args:
            value: The value to check
            threshold: The threshold level

        Returns:
            True if value >= threshold in the scale ordering
        """
        val_idx = self.get_level_index(value)
        threshold_idx = self.get_level_index(threshold)
        if val_idx < 0 or threshold_idx < 0:
            return False
        return val_idx >= threshold_idx


class RatingScaleRegistry:
    """
    Central registry for framework rating scales.

    Provides default scales for PMT, Utility, and Financial frameworks,
    with support for custom scales loaded from YAML configuration.
    """

    _scales: Dict[FrameworkType, RatingScale] = {}
    _initialized: bool = False

    @classmethod
    def _ensure_defaults(cls):
        """Register default scales if not initialized."""
        if cls._initialized:
            return

        # PMT: Protection Motivation Theory (5-level)
        cls._scales[FrameworkType.PMT] = RatingScale(
            framework=FrameworkType.PMT,
            levels=["VL", "L", "M", "H", "VH"],
            labels={
                "VL": "Very Low",
                "L": "Low",
                "M": "Medium",
                "H": "High",
                "VH": "Very High"
            },
            template="""### RATING SCALE:
VL = Very Low | L = Low | M = Medium | H = High | VH = Very High"""
        )

        # Utility: Government policy decisions (3-level + numeric)
        cls._scales[FrameworkType.UTILITY] = RatingScale(
            framework=FrameworkType.UTILITY,
            levels=["L", "M", "H"],
            labels={
                "L": "Low Priority",
                "M": "Medium Priority",
                "H": "High Priority"
            },
            template="""### PRIORITY SCALE:
L = Low Priority | M = Medium Priority | H = High Priority
Use numeric scores (0.0-1.0) for budget allocation.""",
            numeric_range=(0.0, 1.0)
        )

        # Financial: Insurance risk appetite (3-level)
        cls._scales[FrameworkType.FINANCIAL] = RatingScale(
            framework=FrameworkType.FINANCIAL,
            levels=["C", "M", "A"],
            labels={
                "C": "Conservative",
                "M": "Moderate",
                "A": "Aggressive"
            },
            template="""### RISK APPETITE:
C = Conservative | M = Moderate | A = Aggressive"""
        )

        # Generic fallback (same as PMT for backward compatibility)
        cls._scales[FrameworkType.GENERIC] = cls._scales[FrameworkType.PMT]

        cls._initialized = True

    @classmethod
    def register(cls, scale: RatingScale):
        """
        Register a custom rating scale.

        Args:
            scale: The RatingScale to register
        """
        cls._ensure_defaults()
        cls._scales[scale.framework] = scale

    @classmethod
    def get(cls, framework: FrameworkType) -> RatingScale:
        """
        Get rating scale for framework, defaulting to PMT.

        Args:
            framework: The framework type

        Returns:
            RatingScale for the framework
        """
        cls._ensure_defaults()
        return cls._scales.get(framework, cls._scales[FrameworkType.PMT])

    @classmethod
    def get_by_name(cls, framework_name: str) -> RatingScale:
        """
        Get rating scale by framework name string.

        Args:
            framework_name: Framework name (e.g., "pmt", "utility")

        Returns:
            RatingScale for the framework, defaulting to PMT
        """
        cls._ensure_defaults()
        try:
            framework = FrameworkType(framework_name.lower())
            return cls.get(framework)
        except ValueError:
            return cls.get(FrameworkType.PMT)

    @classmethod
    def load_from_yaml(cls, yaml_config: Dict):
        """
        Load scales from shared.rating_scales YAML section.

        Args:
            yaml_config: Dictionary containing "rating_scales" key

        Example YAML structure:
            rating_scales:
              pmt:
                levels: ["VL", "L", "M", "H", "VH"]
                labels:
                  VL: "Very Low"
                  ...
                template: "### RATING SCALE: ..."
        """
        cls._ensure_defaults()
        rating_scales = yaml_config.get("rating_scales", {})

        for framework_name, scale_config in rating_scales.items():
            try:
                framework = FrameworkType(framework_name.lower())
            except ValueError:
                continue  # Skip unknown frameworks

            scale = RatingScale(
                framework=framework,
                levels=scale_config.get("levels", []),
                labels=scale_config.get("labels", {}),
                template=scale_config.get("template", ""),
                numeric_range=tuple(scale_config["numeric_range"]) if "numeric_range" in scale_config else None
            )
            cls.register(scale)

    @classmethod
    def get_all_frameworks(cls) -> List[FrameworkType]:
        """
        Get list of all registered frameworks.

        Returns:
            List of FrameworkType values
        """
        cls._ensure_defaults()
        return list(cls._scales.keys())

    @classmethod
    def reset(cls):
        """Reset registry to defaults (for testing)."""
        cls._scales = {}
        cls._initialized = False


# Convenience functions
def get_scale_for_framework(framework: str) -> RatingScale:
    """
    Get rating scale for a framework by name.

    Args:
        framework: Framework name string

    Returns:
        RatingScale instance
    """
    return RatingScaleRegistry.get_by_name(framework)


def validate_rating_value(value: str, framework: str) -> bool:
    """
    Validate a rating value against a framework's scale.

    Args:
        value: The value to validate
        framework: The framework name

    Returns:
        True if value is valid for the framework
    """
    scale = RatingScaleRegistry.get_by_name(framework)
    return scale.validate_value(value)
