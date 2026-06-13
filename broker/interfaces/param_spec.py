"""Phase 6W-B3 — per-skill parameter-spec loader.

Lets a DomainPack declare, per skill, the named numeric setpoints that skill
authors (multi-dimensional actions, e.g. a reservoir operator's
{release, hydropower, flood_pool}). Each spec is an ordinary coupling-layer
``VarSpec``, so the bounds vocabulary is shared with the coupling contract — NO
second bounds registry (INVARIANTS.md AR-6). The ``ParameterBoundsValidator`` (B4)
reads these and calls ``VarSpec.range_violation``.

Opt-in + fail-soft: returns ``{}`` if the YAML is absent or no skill declares a
``param_specs:`` block. A MALFORMED spec (numeric VarSpec with an empty unit, or
lo > hi) fails LOUD at load via ``VarSpec.__post_init__`` — and only for the
domain that declares it.

``VarSpec`` is imported INSIDE the function so a frozen flag-OFF run (whose
``DefaultDomainPack.param_specs`` returns ``{}`` without calling this loader)
never pulls ``broker.coupling`` onto the default import path — keeping
``test_builder_coupling.py::test_frozen_path_never_imports_coupling`` green.

Mirrors ``broker.interfaces.action_taxonomy.load_action_taxonomy_from_skill_registry``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, TYPE_CHECKING

import yaml

if TYPE_CHECKING:  # never imported at runtime on the default path
    from broker.coupling.contract import VarSpec


def load_param_specs_from_skill_registry(yaml_path: Path) -> "Dict[str, List[VarSpec]]":
    """Read an OPTIONAL per-skill ``param_specs:`` block from a skill_registry.yaml.

    Each entry under a skill's ``param_specs:`` becomes a proposal-side ``VarSpec``
    (``direction='agent_to_world'``, ``value_source='proposal'`` so the coupling
    adapter's execution-sampling guard validates the round-trip). Returns
    ``{skill_id: [VarSpec, ...]}`` for skills that declare specs; ``{}`` otherwise.
    Never raises ``FileNotFoundError``.
    """
    from broker.coupling.contract import VarSpec  # lazy: keep broker.coupling off the default path

    path = Path(yaml_path)
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError:
        return {}

    skills = data.get("skills")
    if not isinstance(skills, list):
        return {}

    result: Dict[str, List[VarSpec]] = {}
    for entry in skills:
        if not isinstance(entry, dict):
            continue
        skill_id = entry.get("skill_id")
        specs = entry.get("param_specs")
        if not isinstance(skill_id, str) or not skill_id or not isinstance(specs, list):
            continue
        built: List[VarSpec] = []
        for p in specs:
            # name must be a non-empty STRING (YAML would auto-cast `name: 1` to int,
            # which would silently build a VarSpec with an int name that B4's
            # string-keyed lookup could never match).
            if not isinstance(p, dict) or not isinstance(p.get("name"), str) or not p["name"]:
                continue
            # VarSpec.__post_init__ fail-louds a numeric spec with empty unit / lo>hi.
            built.append(
                VarSpec(
                    name=p["name"],
                    dtype=float,
                    unit=p.get("unit", ""),
                    lo=p.get("lo"),
                    hi=p.get("hi"),
                    direction="agent_to_world",
                    value_source="proposal",
                )
            )
        if built:
            result[skill_id] = built
    return result
