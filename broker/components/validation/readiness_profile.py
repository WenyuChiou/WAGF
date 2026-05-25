"""Phase 6O-C — Readiness profile loader.

A **profile** is a named set of pass/fail thresholds the readiness
reporter evaluates an experiment's audit traces against. Profiles
correspond to lifecycle stages:

  - ``functional`` — does the pipeline run? Parse-success rate, schema
    integrity, no all-zero columns. Lowest bar; used during dev /
    bring-up of a new domain.
  - ``behavioral`` — does the pipeline produce diverse, coherent
    decisions? Adds construct-action coherence, action coverage,
    validator firing diversity. Used before reporting paper results.
  - ``stress`` — does governance correctly handle hard constraints,
    retries, terminal outcomes? Used for harness-engineering audits.

The ``production`` profile in the codex P0 proposal is intentionally
**not** shipped in 6O-C-1 (persona alignment undefined; user explicit
decision recorded at `.ai/2026/05/25/phase_6o_gap_matrix.md`).

Threshold values are loaded from `readiness_profile.yaml` in this
directory; callers may override the YAML path to load from a custom
profile file. The defaults shipped here are deliberately permissive —
each downstream user is expected to tune them for their domain.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

#: All profiles shipped in 6O-C-1. Order matters for default-cascade in
#: `load_readiness_profile` (functional < behavioral < stress).
PROFILE_NAMES = ("functional", "behavioral", "stress")


@dataclass(frozen=True)
class ReadinessThresholds:
    """Per-profile pass/fail thresholds.

    Each field is a numeric bound. All fields are optional — profiles
    that don't care about a metric leave it `None` and the consumer
    treats it as "not enforced".
    """

    #: Minimum acceptable governance-approval rate (APPROVED / total). 0..1.
    #: NOTE the rename in 6O-C-1 round-1: this is NOT a parse-quality metric.
    #: Parser failures are tracked separately via the terminal-outcome
    #: classifier (`parser_failure` category). A true parse_success_rate
    #: metric is deferred to 6O-C-2 alongside the format-retry analysis.
    min_approval_rate: Optional[float] = None

    #: Maximum allowed format-retry rate (format_retries / total). 0..1.
    max_format_retry_rate: Optional[float] = None

    #: Maximum allowed terminal-outcome rate (terminal / total). 0..1.
    #: "Terminal" = anything other than approved / retry_recovered.
    max_terminal_rate: Optional[float] = None

    #: Minimum number of distinct skills observed across all decisions.
    min_action_coverage: Optional[int] = None

    #: Minimum number of distinct rule_ids that fired at least once.
    min_validator_firing_diversity: Optional[int] = None

    #: Maximum number of dead validators (registered but never fired) the
    #: profile tolerates. None = not enforced; 0 = strict no-dead. Replaces
    #: the boolean `require_no_dead_validators` (6O-C-1 round-1 fix).
    #: Cross-domain audits where some validators are legitimately
    #: inapplicable will see false-positive dead detections — set this
    #: to a reasonable count > 0 instead of strict 0 in those cases.
    max_dead_validators: Optional[int] = None


@dataclass(frozen=True)
class ReadinessProfile:
    """Named profile = thresholds + per-profile metadata."""

    name: str
    description: str
    thresholds: ReadinessThresholds
    required_metrics: List[str] = field(default_factory=list)


def _profile_yaml_path() -> Path:
    """Default location of the shipped profile YAML."""
    return Path(__file__).resolve().parent / "readiness_profile.yaml"


def load_readiness_profile(
    name: str,
    *,
    yaml_path: Optional[Path] = None,
) -> ReadinessProfile:
    """Load a single profile by name from the YAML config.

    Args:
        name: Profile identifier; must be one of ``PROFILE_NAMES``
            (functional / behavioral / stress).
        yaml_path: Optional override for the YAML config path. Default
            resolves to the bundled `readiness_profile.yaml`.

    Returns:
        Immutable `ReadinessProfile` dataclass populated from the YAML.

    Raises:
        ValueError: If `name` is not one of the shipped profile names
            or the YAML lacks an entry for it.
        FileNotFoundError: If the override `yaml_path` does not exist.
    """
    if name not in PROFILE_NAMES:
        raise ValueError(
            f"Unknown profile {name!r}. Shipped: {PROFILE_NAMES}. "
            f"Production profile deferred per Phase 6O scope decision."
        )

    path = yaml_path or _profile_yaml_path()
    if not path.is_file():
        raise FileNotFoundError(f"Profile YAML not found: {path}")

    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    profiles = data.get("profiles") if isinstance(data, dict) else None
    if not isinstance(profiles, dict):
        raise ValueError(f"{path}: missing 'profiles' top-level mapping")

    raw = profiles.get(name)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: no entry for profile {name!r}")

    return _profile_from_dict(name, raw)


def _profile_from_dict(name: str, raw: Dict[str, Any]) -> ReadinessProfile:
    """Build a ReadinessProfile dataclass from a YAML-loaded dict.

    Tolerant of missing / unknown keys: missing threshold fields stay
    `None`; unknown keys ignored. Required: `description` string.
    """
    description = raw.get("description")
    if not isinstance(description, str):
        description = f"(profile {name}; no description)"

    thr_raw = raw.get("thresholds") if isinstance(raw.get("thresholds"), dict) else {}
    thresholds = ReadinessThresholds(
        # 6O-C-1 round-1 rename: the YAML key stays `min_parse_success_rate`
        # for now to preserve any user-shipped override files, but the
        # ReadinessThresholds field is `min_approval_rate` to match its
        # actual computation. A migration helper can land in 6O-C-2.
        min_approval_rate=_as_float_or_none(
            thr_raw.get("min_approval_rate") or thr_raw.get("min_parse_success_rate")
        ),
        max_format_retry_rate=_as_float_or_none(thr_raw.get("max_format_retry_rate")),
        max_terminal_rate=_as_float_or_none(thr_raw.get("max_terminal_rate")),
        min_action_coverage=_as_int_or_none(thr_raw.get("min_action_coverage")),
        min_validator_firing_diversity=_as_int_or_none(
            thr_raw.get("min_validator_firing_diversity")
        ),
        max_dead_validators=_as_int_or_none(
            # Accept new key OR legacy boolean (True -> 0, False -> not enforced)
            thr_raw.get("max_dead_validators")
            if "max_dead_validators" in thr_raw
            else (0 if thr_raw.get("require_no_dead_validators") else None)
        ),
    )
    required = raw.get("required_metrics") or []
    if not isinstance(required, list):
        required = []
    return ReadinessProfile(
        name=name,
        description=description,
        thresholds=thresholds,
        required_metrics=[str(m) for m in required if isinstance(m, (str, int))],
    )


def _as_float_or_none(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int_or_none(value: Any) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
