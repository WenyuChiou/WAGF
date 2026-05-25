"""Phase 6O-B — Action taxonomy interface (P4 of the codex Phase 6O plan).

Lets `DomainPack` implementations declare per-skill structural metadata
that the generic readiness reporter (Phase 6O-C) can use to compute
**action coverage** / **category coverage** / **intensity coverage**
without knowing the skill names of any particular domain.

The taxonomy is **opt-in**. A domain pack that returns an empty mapping
from `action_taxonomy()` (the default in
`broker/domains/default.py::DefaultDomainPack.action_taxonomy`) gets
reported under `unknown` category by the readiness layer — never a
hard error.

The 3 fields are inspired by the codex P4 proposal and validated
against the existing irrigation skill_registry.yaml shape:

- ``category``: a domain-defined grouping (e.g. ``"increase"`` /
  ``"maintain"`` / ``"decrease"`` for irrigation magnitude; ``"adopt"``
  / ``"delay"`` / ``"refuse"`` for vaccination).
- ``intensity``: a magnitude / strength ranking within a category
  (e.g. ``"small"`` / ``"large"`` / ``"none"``). Optional — categorical
  domains without a magnitude axis leave this `None`.
- ``reversibility``: how easily an action can be undone. Free-form
  string; common values used in the water domain are ``"annual"`` (next
  year's decision overrides this year's), ``"permanent"`` (one-shot
  capital investment), ``"instant"`` (no lasting state change).

Phase 6O-B-1 ships protocol + default + irrigation. 6O-B-2 wires
flood and vaccination DomainPacks (deferred to keep the first commit
under the byte-identical paper-1b regression gate manageable).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


@dataclass(frozen=True)
class ActionTaxonomyEntry:
    """Phase 6O-B per-skill taxonomy.

    All fields optional. Consumers (Phase 6O-C readiness reporter +
    Phase 6Q scenario harness) MUST treat missing fields as "feature
    not declared for this skill" — never raise.
    """

    category: Optional[str] = None
    intensity: Optional[str] = None
    reversibility: Optional[str] = None


def load_action_taxonomy_from_skill_registry(
    yaml_path: Path,
) -> Dict[str, ActionTaxonomyEntry]:
    """Read action-taxonomy fields from a skill_registry.yaml.

    The function looks for the optional top-level keys ``category`` /
    ``intensity`` / ``reversibility`` on every `skills:` entry. Skills
    that declare ZERO of these get an empty `ActionTaxonomyEntry`
    (all fields `None`); skills that declare some subset get the
    matching fields populated and the rest `None`.

    Returns the empty dict if the YAML file does not exist OR has no
    `skills:` block — never raises FileNotFoundError. Caller can
    treat empty as "this domain pack opted out of action taxonomy".
    """
    if not yaml_path.is_file():
        return {}
    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}

    skills = data.get("skills")
    if not isinstance(skills, list):
        return {}

    result: Dict[str, ActionTaxonomyEntry] = {}
    for entry in skills:
        if not isinstance(entry, dict):
            continue
        skill_id = entry.get("skill_id")
        if not isinstance(skill_id, str) or not skill_id:
            continue
        result[skill_id] = ActionTaxonomyEntry(
            category=entry.get("category") if isinstance(entry.get("category"), str) else None,
            intensity=entry.get("intensity") if isinstance(entry.get("intensity"), str) else None,
            reversibility=(
                entry.get("reversibility")
                if isinstance(entry.get("reversibility"), str)
                else None
            ),
        )
    return result
