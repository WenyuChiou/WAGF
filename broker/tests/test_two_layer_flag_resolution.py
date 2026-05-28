"""Phase 6T-E.B regression: two-layer ``social_feeds`` flag resolver.

The 4-cell truth table covered:
| YAML enable | Pack default | Resolved | Source |
|---|---|---|---|
| True   | False  | True   | yaml         |
| False  | True   | False  | yaml         |
| absent | True   | True   | pack-default |
| absent | False  | False  | pack-default |

Plus edge cases: explicit ``None`` treated as absent, full-doc vs
pre-extracted ``global_config`` slice both accepted, missing pack
hook treated as False.
"""
from __future__ import annotations

import logging
from typing import Any

import pytest

from broker.components.social.feed_flag import resolve_social_feeds_enabled


class _Pack:
    def __init__(self, default: bool):
        self._default = default

    def social_feeds_default_enabled(self) -> bool:
        return self._default


class _PackWithoutHook:
    """Older pack that hasn't yet implemented the Phase 6T-E.B hook."""
    pass


# ---------------------------------------------------------------------------
# The 4-cell truth table
# ---------------------------------------------------------------------------


def test_yaml_true_overrides_pack_false():
    cfg = {"global_config": {"social_feeds": {"enable": True}}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=False))
    assert enabled is True
    assert source == "yaml"


def test_yaml_false_overrides_pack_true():
    """Explicit YAML False must beat pack True — packs designed for
    social experiments can still be turned off per-run via config."""
    cfg = {"global_config": {"social_feeds": {"enable": False}}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=True))
    assert enabled is False
    assert source == "yaml"


def test_yaml_absent_uses_pack_true():
    cfg = {"global_config": {}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=True))
    assert enabled is True
    assert source == "pack-default"


def test_yaml_absent_uses_pack_false():
    cfg = {"global_config": {}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=False))
    assert enabled is False
    assert source == "pack-default"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_yaml_enable_explicitly_none_treated_as_absent():
    """YAML ``enable: ~`` parses to Python ``None`` — the resolver
    treats that as 'key absent' and falls back to pack default."""
    cfg = {"global_config": {"social_feeds": {"enable": None}}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=True))
    assert enabled is True
    assert source == "pack-default"


def test_yaml_can_be_global_config_slice_directly():
    """Callers that already extracted ``global_config`` may pass it
    directly — same resolution."""
    slice_only = {"social_feeds": {"enable": True}}
    enabled, source = resolve_social_feeds_enabled(slice_only, _Pack(default=False))
    assert enabled is True
    assert source == "yaml"


def test_pack_without_hook_treated_as_false():
    """Older packs without ``social_feeds_default_enabled`` get the
    safe default (off) — no AttributeError, no warning. Forward-compat
    for any non-water DomainPack that hasn't been updated yet."""
    enabled, source = resolve_social_feeds_enabled(None, _PackWithoutHook())
    assert enabled is False
    assert source == "pack-default"


def test_none_yaml_cfg_skips_yaml_layer():
    enabled, source = resolve_social_feeds_enabled(None, _Pack(default=True))
    assert enabled is True
    assert source == "pack-default"


def test_truthy_non_bool_coerced_to_bool():
    """YAML int 1 / string 'true' should coerce — but PyYAML normally
    maps unquoted true/false to Python bool. This test guards against
    the rare case of a non-bool sneaking through."""
    cfg = {"global_config": {"social_feeds": {"enable": 1}}}
    enabled, source = resolve_social_feeds_enabled(cfg, _Pack(default=False))
    assert enabled is True
    assert source == "yaml"


# ---------------------------------------------------------------------------
# Audit logging
# ---------------------------------------------------------------------------


def test_resolver_logs_source_for_audit(caplog):
    """The INFO log line documenting source is the audit-trail
    surface. Test that it fires + names the source."""
    cfg = {"global_config": {"social_feeds": {"enable": True}}}
    with caplog.at_level(logging.INFO, logger="broker.components.social.feed_flag"):
        resolve_social_feeds_enabled(cfg, _Pack(default=False))
    yaml_lines = [r for r in caplog.records if "source=yaml" in r.message]
    assert yaml_lines, f"expected 'source=yaml' INFO log; got {[r.message for r in caplog.records]}"
