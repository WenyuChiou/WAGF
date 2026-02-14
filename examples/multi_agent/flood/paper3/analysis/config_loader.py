"""
Configuration Loader for C&V Validation Module

Loads theory rules, benchmarks, and hallucination rules from YAML files.
Falls back to hard-coded defaults when YAML files are not available.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

try:
    import yaml
except ImportError:
    yaml = None

CONFIGS_DIR = Path(__file__).parent / "configs"


# =============================================================================
# Data structures
# =============================================================================

@dataclass
class TheoryDimension:
    """A construct dimension (e.g., TP, CP)."""
    name: str
    label_field: str
    extraction_paths: List[str]
    fallback: str = "UNKNOWN"


@dataclass
class TheoryConfig:
    """Theory configuration loaded from YAML."""
    name: str
    full_name: str
    paradigm: str
    dimensions: List[TheoryDimension]
    quadrant_thresholds: Dict[str, List[str]]
    action_aliases: Dict[str, List[str]]
    owner_rules: Dict[Tuple[str, str], List[str]]
    renter_rules: Dict[Tuple[str, str], List[str]]


@dataclass
class BenchmarkSpec:
    """Single benchmark specification."""
    name: str
    range: Tuple[float, float]
    weight: float
    description: str
    computation: Optional[str] = None


@dataclass
class ThresholdSpec:
    """Threshold specification."""
    operator: str
    value: Optional[float] = None
    low: Optional[float] = None
    high: Optional[float] = None


@dataclass
class BenchmarkConfig:
    """Full benchmark configuration."""
    benchmarks: Dict[str, BenchmarkSpec]
    thresholds: Dict[str, Dict[str, ThresholdSpec]]


@dataclass
class HallucinationRule:
    """Single hallucination detection rule."""
    id: str
    type: str
    description: str = ""
    action: Optional[str] = None
    state_field: Optional[str] = None
    state_value: Optional[Any] = None
    agent_type_contains: Optional[str] = None


@dataclass
class ValidationConfig:
    """Complete validation configuration."""
    theory: TheoryConfig
    benchmarks: BenchmarkConfig
    hallucination_rules: List[HallucinationRule]


# =============================================================================
# YAML Loaders
# =============================================================================

def _parse_rule_key(key_str: str) -> Tuple[str, str]:
    """Convert 'VH_VH' string key to ('VH', 'VH') tuple."""
    parts = key_str.split("_", 1)
    if len(parts) == 2:
        return (parts[0], parts[1])
    raise ValueError(f"Invalid rule key format: {key_str}")


def _parse_rules_dict(raw: Dict[str, List[str]]) -> Dict[Tuple[str, str], List[str]]:
    """Convert YAML string keys to tuple keys."""
    result = {}
    for key_str, actions in raw.items():
        result[_parse_rule_key(key_str)] = actions
    return result


def load_theory_config(path: Optional[Path] = None) -> Optional[TheoryConfig]:
    """Load theory configuration from YAML.

    Args:
        path: Path to theory YAML file. Defaults to configs/theories/pmt_flood.yaml.

    Returns:
        TheoryConfig or None if file not found or yaml not available.
    """
    if yaml is None:
        return None

    if path is None:
        path = CONFIGS_DIR / "theories" / "pmt_flood.yaml"

    if not path.exists():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    theory = data["theory"]
    dimensions = [
        TheoryDimension(
            name=d["name"],
            label_field=d["label_field"],
            extraction_paths=d["extraction_paths"],
            fallback=d.get("fallback", "UNKNOWN"),
        )
        for d in theory["dimensions"]
    ]

    return TheoryConfig(
        name=theory["name"],
        full_name=theory["full_name"],
        paradigm=theory["paradigm"],
        dimensions=dimensions,
        quadrant_thresholds=theory["quadrant_thresholds"],
        action_aliases=theory["action_aliases"],
        owner_rules=_parse_rules_dict(theory["rules"]["owner"]),
        renter_rules=_parse_rules_dict(theory["rules"]["renter"]),
    )


def load_benchmark_config(path: Optional[Path] = None) -> Optional[BenchmarkConfig]:
    """Load benchmark configuration from YAML.

    Args:
        path: Path to benchmarks YAML file. Defaults to configs/benchmarks/flood_benchmarks.yaml.

    Returns:
        BenchmarkConfig or None if file not found or yaml not available.
    """
    if yaml is None:
        return None

    if path is None:
        path = CONFIGS_DIR / "benchmarks" / "flood_benchmarks.yaml"

    if not path.exists():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    benchmarks = {}
    for name, spec in data["benchmarks"].items():
        benchmarks[name] = BenchmarkSpec(
            name=name,
            range=tuple(spec["range"]),
            weight=spec["weight"],
            description=spec["description"],
            computation=spec.get("computation"),
        )

    thresholds = {}
    for level, level_thresholds in data.get("thresholds", {}).items():
        thresholds[level] = {}
        for metric, spec in level_thresholds.items():
            thresholds[level][metric] = ThresholdSpec(
                operator=spec["operator"],
                value=spec.get("value"),
                low=spec.get("low"),
                high=spec.get("high"),
            )

    return BenchmarkConfig(benchmarks=benchmarks, thresholds=thresholds)


def load_hallucination_rules(path: Optional[Path] = None) -> Optional[List[HallucinationRule]]:
    """Load hallucination detection rules from YAML.

    Args:
        path: Path to hallucination rules YAML file.

    Returns:
        List of HallucinationRule or None if file not found.
    """
    if yaml is None:
        return None

    if path is None:
        path = CONFIGS_DIR / "hallucinations" / "flood_rules.yaml"

    if not path.exists():
        return None

    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)

    rules = []
    for rule_data in data["hallucination_rules"]:
        state_value = rule_data.get("state_value")
        if isinstance(state_value, str) and state_value.lower() in ("true", "false"):
            state_value = state_value.lower() == "true"
        rules.append(HallucinationRule(
            id=rule_data["id"],
            type=rule_data["type"],
            description=rule_data.get("description", ""),
            action=rule_data.get("action"),
            state_field=rule_data.get("state_field"),
            state_value=state_value,
            agent_type_contains=rule_data.get("agent_type_contains"),
        ))

    return rules


# =============================================================================
# Default Config (fallback when YAML not available)
# =============================================================================

def load_default_config() -> ValidationConfig:
    """Load full validation configuration with YAML-first, hard-coded fallback.

    Returns:
        ValidationConfig with theory, benchmarks, and hallucination rules.
    """
    # Try YAML first
    theory = load_theory_config()
    benchmarks = load_benchmark_config()
    hallucination_rules = load_hallucination_rules()

    # Fallback to hard-coded defaults
    if theory is None:
        theory = _default_theory_config()
    if benchmarks is None:
        benchmarks = _default_benchmark_config()
    if hallucination_rules is None:
        hallucination_rules = _default_hallucination_rules()

    return ValidationConfig(
        theory=theory,
        benchmarks=benchmarks,
        hallucination_rules=hallucination_rules,
    )


def _default_theory_config() -> TheoryConfig:
    """Hard-coded PMT theory config (fallback)."""
    # Import from compute_validation_metrics to avoid duplication
    from compute_validation_metrics import PMT_OWNER_RULES, PMT_RENTER_RULES

    return TheoryConfig(
        name="pmt",
        full_name="Protection Motivation Theory",
        paradigm="construct_action_mapping",
        dimensions=[
            TheoryDimension(
                name="TP", label_field="TP_LABEL",
                extraction_paths=["skill_proposal.reasoning.TP_LABEL", "TP_LABEL"],
                fallback="UNKNOWN",
            ),
            TheoryDimension(
                name="CP", label_field="CP_LABEL",
                extraction_paths=["skill_proposal.reasoning.CP_LABEL", "CP_LABEL"],
                fallback="UNKNOWN",
            ),
        ],
        quadrant_thresholds={"high": ["H", "VH"], "low": ["VL", "L", "M"]},
        action_aliases={
            "buy_insurance": ["buy_insurance", "purchase_insurance", "get_insurance",
                              "insurance", "buy_contents_insurance",
                              "buy_structure_insurance", "contents_insurance"],
            "elevate": ["elevate", "elevate_home", "home_elevation",
                        "raise_home", "elevate_house"],
            "buyout": ["buyout", "voluntary_buyout", "accept_buyout", "buyout_program"],
            "relocate": ["relocate", "move", "relocation"],
            "retrofit": ["retrofit", "floodproof", "flood_retrofit"],
            "do_nothing": ["do_nothing", "no_action", "wait", "none"],
        },
        owner_rules=dict(PMT_OWNER_RULES),
        renter_rules=dict(PMT_RENTER_RULES),
    )


def _default_benchmark_config() -> BenchmarkConfig:
    """Hard-coded benchmark config (fallback)."""
    from compute_validation_metrics import EMPIRICAL_BENCHMARKS

    benchmarks = {}
    for name, spec in EMPIRICAL_BENCHMARKS.items():
        benchmarks[name] = BenchmarkSpec(
            name=name,
            range=spec["range"],
            weight=spec["weight"],
            description=spec["description"],
        )

    return BenchmarkConfig(
        benchmarks=benchmarks,
        thresholds={
            "l1": {
                "cacr": ThresholdSpec(operator=">=", value=0.75),
                "r_h": ThresholdSpec(operator="<=", value=0.10),
                "ebe_ratio": ThresholdSpec(operator="range", low=0.1, high=0.9),
            },
            "l2": {
                "epi": ThresholdSpec(operator=">=", value=0.60),
            },
        },
    )


def _default_hallucination_rules() -> List[HallucinationRule]:
    """Hard-coded hallucination rules (fallback)."""
    return [
        HallucinationRule(
            id="double_elevation",
            type="state_conflict",
            description="Already elevated home trying to elevate again",
            action="elevate",
            state_field="elevated",
            state_value=True,
        ),
        HallucinationRule(
            id="bought_out_acting",
            type="state_conflict",
            description="Already bought out but still making non-trivial decisions",
            state_field="bought_out",
            state_value=True,
            action="!do_nothing",
        ),
        HallucinationRule(
            id="renter_elevate",
            type="agent_type_conflict",
            description="Renter trying to elevate",
            agent_type_contains="renter",
            action="elevate",
        ),
    ]
