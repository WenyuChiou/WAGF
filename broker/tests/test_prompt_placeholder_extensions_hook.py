"""Phase 6R-B-3 regression — DomainPack.prompt_placeholder_extensions() hook.

Audit cluster E item #16. Pre-fix the 3 water-domain narrative
placeholder names (``insurance_cost_text`` / ``mg_barrier_text`` /
``renewal_fatigue_text``) lived directly in
``broker/tools/validate_prompt.py::BROKER_FILLED_PLACEHOLDERS`` —
embedding flood-domain vocabulary in a generic CLI tool. Phase 6R-B-3
introduced a ``DomainPack.prompt_placeholder_extensions() -> Set[str]``
hook + a ``_resolve_domain_extensions(cfg)`` helper that unions the
base set with the registered DomainPack's extensions at validate-time.

Tests cover:
1. Hook contract — DefaultDomainPack returns empty set;
   FloodDomainPack returns exactly the 3 names.
2. `_resolve_domain_extensions(cfg)` — reads
   `global_config.governance.domain` from YAML, queries the
   registered pack, gracefully degrades when domain is missing /
   pack is unregistered / pack method raises.
3. Integration — flood YAML referencing
   ``{insurance_cost_text}`` triggers NO WARN when FloodDomainPack is
   registered, and DOES trigger a WARN when no flood pack is
   registered (proves the union is the real gate, not the static set).
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from broker.domains.default import DefaultDomainPack
from broker.domains.registry import DomainPackRegistry
from broker.tools.validate_prompt import (
    BROKER_FILLED_PLACEHOLDERS,
    _resolve_domain_extensions,
    validate_agent_type,
)


# ---------------------------------------------------------------------------
# Hook contract
# ---------------------------------------------------------------------------

class TestPromptPlaceholderExtensionsHook:
    """The hook's per-pack contract."""

    def test_default_pack_returns_empty(self):
        assert DefaultDomainPack().prompt_placeholder_extensions() == set()

    def test_flood_pack_returns_water_names(self):
        # Import the flood pack on demand so this test doesn't force
        # the import for unrelated runs.
        from examples.governed_flood.adapters.flood_pack import (
            FloodDomainPack,
        )
        ext = FloodDomainPack().prompt_placeholder_extensions()
        assert ext == {
            "insurance_cost_text",
            "mg_barrier_text",
            "renewal_fatigue_text",
            # Phase 6T-E.B v0.5.1 (2026-05-28): social_media_feed added
            # so validate_prompt accepts the new household-template
            # placeholder. Resolves to "" when feeds are off
            # (byte-identity preserved).
            "social_media_feed",
        }

    def test_base_broker_filled_set_no_longer_contains_water_names(self):
        """Critical Phase 6R-B-3 regression: the 3 water names must NOT
        be in the generic CLI's base allowlist any more. Their proper
        home is FloodDomainPack.prompt_placeholder_extensions()."""
        assert "insurance_cost_text" not in BROKER_FILLED_PLACEHOLDERS
        assert "mg_barrier_text" not in BROKER_FILLED_PLACEHOLDERS
        assert "renewal_fatigue_text" not in BROKER_FILLED_PLACEHOLDERS


# ---------------------------------------------------------------------------
# _resolve_domain_extensions — YAML -> pack lookup
# ---------------------------------------------------------------------------

class TestResolveDomainExtensions:
    """The helper that bridges YAML -> DomainPackRegistry -> hook."""

    @pytest.fixture(autouse=True)
    def _restore_registry(self):
        saved_packs = dict(DomainPackRegistry._packs)
        saved_warned = set(DomainPackRegistry._missing_warned)
        yield
        DomainPackRegistry.clear()
        for name, pack in saved_packs.items():
            DomainPackRegistry._packs[name] = pack
        DomainPackRegistry._missing_warned.update(saved_warned)

    def test_returns_empty_when_no_domain_field(self):
        cfg = {"global_config": {"governance": {}}}
        assert _resolve_domain_extensions(cfg) == set()

    def test_returns_empty_when_pack_unregistered(self):
        cfg = {"global_config": {"governance": {"domain": "unregistered_x"}}}
        assert _resolve_domain_extensions(cfg) == set()

    def test_returns_flood_extensions_when_flood_pack_registered(self):
        from examples.governed_flood.adapters.flood_pack import (
            FloodDomainPack,
        )
        DomainPackRegistry.register("flood", FloodDomainPack())
        cfg = {"global_config": {"governance": {"domain": "flood"}}}
        ext = _resolve_domain_extensions(cfg)
        assert "insurance_cost_text" in ext
        assert "mg_barrier_text" in ext
        assert "renewal_fatigue_text" in ext

    def test_returns_empty_when_broken_pack_method_raises(self):
        """Phase 6Q-D-4 graceful-degradation pattern: a broken
        ``prompt_placeholder_extensions()`` must not crash the CLI."""

        class _BrokenPack(DefaultDomainPack):
            name: str = "broken_test"

            def prompt_placeholder_extensions(self):
                raise RuntimeError("intentional break")

        DomainPackRegistry.register("broken_test", _BrokenPack())
        cfg = {"global_config": {"governance": {"domain": "broken_test"}}}
        # Must not raise; returns empty set as graceful fallback.
        assert _resolve_domain_extensions(cfg) == set()

    def test_handles_missing_global_config(self):
        cfg = {}
        assert _resolve_domain_extensions(cfg) == set()


# ---------------------------------------------------------------------------
# Integration — validate_agent_type uses the extension set
# ---------------------------------------------------------------------------

class TestValidateAgentTypeWithExtensions:
    """``validate_agent_type`` must union BROKER_FILLED_PLACEHOLDERS
    with the supplied domain_extensions before checking for unknown
    placeholders."""

    def _build_yaml_with_placeholder(self, placeholder: str) -> dict:
        """Minimal in-memory YAML config with one agent type whose
        prompt references the given placeholder."""
        return {
            "global_config": {
                "governance": {"domain": "test_x"},
                "memory": {"stimulus_key": "x"},
            },
            "shared": {
                "response_format": {
                    "fields": [{"key": "decision"}],
                },
            },
            "test_agent": {
                "agent_type": "test_agent",
                "prompt_template": (
                    "You are a test agent.\n"
                    "Custom field: {" + placeholder + "}\n"
                    "{response_format}\n"
                ),
                "parsing": {
                    "actions": [
                        {"id": "act1", "aliases": ["1"]},
                    ],
                },
                "actions": [
                    {"id": "act1", "aliases": ["1"]},
                ],
            },
        }

    def test_warn_fires_when_placeholder_not_in_extension(self):
        """No extensions supplied → custom placeholder generates WARN."""
        cfg = self._build_yaml_with_placeholder("insurance_cost_text")
        issues = validate_agent_type(
            cfg, "test_agent",
            yaml_path=Path("dummy.yaml"),
            domain_extensions=set(),  # explicit empty
        )
        unknowns = [
            i for i in issues
            if "placeholders not in broker-filled" in i.message
        ]
        assert unknowns, (
            "expected WARN about insurance_cost_text being unknown — "
            f"got issues: {[i.message for i in issues]}"
        )

    def test_warn_suppressed_when_placeholder_in_extension(self):
        """Extension supplied → custom placeholder is treated as known."""
        cfg = self._build_yaml_with_placeholder("insurance_cost_text")
        issues = validate_agent_type(
            cfg, "test_agent",
            yaml_path=Path("dummy.yaml"),
            domain_extensions={"insurance_cost_text"},
        )
        unknowns = [
            i for i in issues
            if "placeholders not in broker-filled" in i.message
        ]
        assert not unknowns, (
            f"expected NO WARN about insurance_cost_text, got: "
            f"{[i.message for i in unknowns]}"
        )

    def test_default_arg_extensions_is_empty_set(self):
        """``domain_extensions=None`` (the default) is normalised to
        empty set — backward-compat for any caller that doesn't pass
        the new kwarg."""
        cfg = self._build_yaml_with_placeholder("custom_placeholder")
        # No domain_extensions kwarg passed.
        issues = validate_agent_type(
            cfg, "test_agent",
            yaml_path=Path("dummy.yaml"),
        )
        unknowns = [
            i for i in issues
            if "placeholders not in broker-filled" in i.message
        ]
        # WARN should fire since custom_placeholder is not in any set.
        assert unknowns


# ---------------------------------------------------------------------------
# End-to-end main() test — the threading path from CLI to hook
# ---------------------------------------------------------------------------

class TestMainResolvesDomainExtensions:
    """``main()`` must call ``_resolve_domain_extensions`` and thread
    the result through ``validate_agent_type``. This closes the
    coverage gap for the threading path itself (the unit tests above
    test the helper + validate_agent_type independently).
    """

    @pytest.fixture(autouse=True)
    def _restore_registry(self):
        from broker.domains.registry import DomainPackRegistry
        saved_packs = dict(DomainPackRegistry._packs)
        saved_warned = set(DomainPackRegistry._missing_warned)
        yield
        DomainPackRegistry.clear()
        for name, pack in saved_packs.items():
            DomainPackRegistry._packs[name] = pack
        DomainPackRegistry._missing_warned.update(saved_warned)

    def test_main_suppresses_warn_when_flood_pack_registered(
        self, tmp_path: Path,
    ):
        """End-to-end: write a flood-shaped YAML referencing
        ``{insurance_cost_text}`` to disk, register FloodDomainPack,
        invoke ``main()`` — should exit 0 with no spurious WARN
        about the water placeholder. Pins the threading path from
        argparse → _resolve_domain_extensions → validate_agent_type.
        """
        from broker.domains.registry import DomainPackRegistry
        from broker.tools.validate_prompt import main
        from examples.governed_flood.adapters.flood_pack import (
            FloodDomainPack,
        )

        DomainPackRegistry.register("flood", FloodDomainPack())

        yaml_text = """
global_config:
  governance:
    domain: flood
  memory:
    stimulus_key: flood_depth
shared:
  response_format:
    fields:
      - { key: decision }

flood_household:
  agent_type: flood_household
  prompt_template: |
    You are a household facing flood risk.
    Insurance cost note: {insurance_cost_text}
    {response_format}
  parsing:
    actions:
      - { id: act_buy, aliases: ["1"] }
  actions:
    - { id: act_buy, aliases: ["1"] }
"""
        path = tmp_path / "flood_agent_types.yaml"
        path.write_text(yaml_text.strip(), encoding="utf-8")

        # main() returns 0 on no issues, 2 on WARN-only, 1 on ERROR.
        # The WARN we want to suppress is "{insurance_cost_text}
        # unknown placeholder". With FloodDomainPack registered, no
        # WARN should fire on that placeholder, so rc should be 0
        # (other validations on the minimal YAML are clean).
        rc = main([str(path)])
        assert rc == 0, (
            f"main() returned rc={rc} — expected 0. A WARN about "
            f"insurance_cost_text would mean the hook isn't being "
            f"queried via main()'s _resolve_domain_extensions threading."
        )
