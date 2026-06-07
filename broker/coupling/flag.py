"""Two-layer feature-flag resolver for the environment-coupling layer
(mirrors ``broker/components/social/feed_flag.py``).

Layer 1 — YAML primary: ``global_config.coupling.enable`` (bool). If present
(including explicit ``False``), YAML wins.
Layer 2 — DomainPack fallback: ``pack.coupling_enabled_default()`` when the
YAML key is absent; packs default to ``False`` so frozen paper-3 configs (which
lack the key) keep the coupling layer OFF and byte-identical.

OFF means the domain injects the RAW sim engine (not the adapter), so the
``broker.coupling`` module is never even imported on a flag-OFF run.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _extract_yaml_value(yaml_cfg: Optional[Dict[str, Any]]) -> Optional[bool]:
    if not isinstance(yaml_cfg, dict):
        return None
    block = yaml_cfg.get("global_config")
    if not isinstance(block, dict):
        block = yaml_cfg  # caller may have passed the global_config slice directly
    coupling = block.get("coupling")
    if not isinstance(coupling, dict):
        return None
    val = coupling.get("enable")
    if val is None:
        return None
    return bool(val)


def resolve_coupling_enabled(
    yaml_cfg: Optional[Dict[str, Any]],
    pack: Any,
) -> Tuple[bool, str]:
    """Resolve the effective coupling flag.

    Returns ``(enabled, source)`` where source is ``"yaml"`` (incl. explicit
    False) or ``"pack-default"``. Packs lacking ``coupling_enabled_default``
    are treated as ``False`` (safe default)."""
    yaml_val = _extract_yaml_value(yaml_cfg)
    if yaml_val is not None:
        logger.info("[coupling] enable=%s (source=yaml)", yaml_val)
        return (yaml_val, "yaml")
    get_default = getattr(pack, "coupling_enabled_default", None)
    pack_val = bool(get_default()) if callable(get_default) else False
    logger.info("[coupling] enable=%s (source=pack-default)", pack_val)
    return (pack_val, "pack-default")


__all__ = ["resolve_coupling_enabled"]
