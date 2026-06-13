"""Phase 6W-B7 — DomainPack for the multi-dimensional reservoir worked example."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from broker.domains.default import DefaultDomainPack


class ReservoirMultidimDomainPack(DefaultDomainPack):
    """Coupled, multi-setpoint reservoir operator. Declares per-skill numeric
    setpoint specs (read from this example's OWN skill_registry) — never a frozen one."""

    def coupling_enabled_default(self) -> bool:
        return True

    def param_specs(self) -> Dict[str, List["object"]]:
        # lazy import keeps broker.coupling off any default import path
        from broker.interfaces.param_spec import load_param_specs_from_skill_registry

        yaml_path = Path(__file__).resolve().parent / "config" / "multidim_skill_registry.yaml"
        return load_param_specs_from_skill_registry(yaml_path)
