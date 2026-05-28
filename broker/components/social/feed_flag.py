"""Phase 6T-E.B (2026-05-28): two-layer feature-flag resolver for the
SocialMediaProvider.

Layer 1 — YAML primary: callers pass the parsed
``examples/<domain>/config/agent_types.yaml`` config dict (or the
nested ``global_config`` slice). The resolver looks for
``global_config.social_feeds.enable`` (bool). If present (including
explicit ``False``), YAML wins.

Layer 2 — DomainPack fallback: when the YAML key is absent, the
resolver consults ``pack.social_feeds_default_enabled()``. The
flood pack returns ``False`` to preserve paper-3 v21 byte-identity;
packs designed for social-media experiments return ``True``.

The resolver emits an INFO log line documenting the resolved value
AND its source (``"yaml"`` vs ``"pack-default"``) so audit traces
can explain why a particular run had the SocialMediaProvider live
or off — this is what the engineering-audit guard catches if a
future contributor wires it on by accident.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def _extract_yaml_value(yaml_cfg: Optional[Dict[str, Any]]) -> Optional[bool]:
    """Read ``global_config.social_feeds.enable`` from a parsed YAML
    config. Returns the bool if present, else ``None`` (key absent —
    fall back to pack default).

    Accepts EITHER the full agent_types.yaml dict (with
    ``global_config`` at the top level) OR a pre-extracted
    ``global_config`` slice. This dual-shape support keeps callers
    simple — the runner can pass whichever shape it already has."""
    if not isinstance(yaml_cfg, dict):
        return None

    # Try full-doc shape first
    block = yaml_cfg.get("global_config")
    if not isinstance(block, dict):
        # Maybe caller passed a pre-extracted global_config slice
        block = yaml_cfg

    social = block.get("social_feeds")
    if not isinstance(social, dict):
        return None

    val = social.get("enable")
    if val is None:
        return None
    # Coerce to strict bool so YAML's ``yes``/``no``/``"true"`` strings
    # behave consistently. PyYAML already maps unquoted ``true`` /
    # ``false`` to Python bool, so the common case is a no-op here.
    return bool(val)


def resolve_social_feeds_enabled(
    yaml_cfg: Optional[Dict[str, Any]],
    pack: Any,
) -> Tuple[bool, str]:
    """Resolve the effective social_feeds flag.

    Args:
        yaml_cfg: Parsed YAML (full agent_types.yaml dict or just its
            ``global_config`` slice). May be ``None`` — then YAML
            layer is skipped entirely.
        pack: The active ``DomainPack``. Must expose
            ``social_feeds_default_enabled() -> bool``; the resolver
            calls it ONLY when the YAML layer is absent. Packs that
            don't yet implement the method (older code paths) are
            treated as if they returned ``False`` (the safe default).

    Returns:
        ``(enabled, source)`` — ``source`` is ``"yaml"`` when the
        flag came from YAML (including explicit ``False``) or
        ``"pack-default"`` when it came from the pack hook. Useful
        for audit logging downstream.
    """
    yaml_val = _extract_yaml_value(yaml_cfg)
    if yaml_val is not None:
        logger.info(
            "[social_feeds] enable=%s (source=yaml)", yaml_val,
        )
        return (yaml_val, "yaml")

    # Pack default — graceful when method missing (older pack)
    get_default = getattr(pack, "social_feeds_default_enabled", None)
    if callable(get_default):
        pack_val = bool(get_default())
    else:
        pack_val = False
    logger.info(
        "[social_feeds] enable=%s (source=pack-default)", pack_val,
    )
    return (pack_val, "pack-default")


__all__ = [
    "resolve_social_feeds_enabled",
]
