"""Tests for trace_reader extensibility (custom action aliases)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "analysis"))

from validation.io.trace_reader import _normalize_action, _FLOOD_ACTION_ALIASES


def test_default_flood_aliases_unchanged():
    """Existing flood aliases still work with no argument."""
    assert _normalize_action("purchase_insurance") == "buy_insurance"
    assert _normalize_action("elevate_home") == "elevate"
    assert _normalize_action("voluntary_buyout") == "buyout"
    assert _normalize_action("no_action") == "do_nothing"


def test_custom_irrigation_aliases():
    """Custom domain aliases override flood defaults."""
    irrigation_aliases = {
        "decrease_large": ["decrease_large", "reduce_water", "cut_water"],
        "increase_small": ["increase_small", "boost_water"],
        "maintain": ["maintain", "keep_current", "no_change"],
    }
    assert _normalize_action("reduce_water", action_aliases=irrigation_aliases) == "decrease_large"
    assert _normalize_action("boost_water", action_aliases=irrigation_aliases) == "increase_small"
    assert _normalize_action("no_change", action_aliases=irrigation_aliases) == "maintain"
    # Unknown action passes through
    assert _normalize_action("buy_insurance", action_aliases=irrigation_aliases) == "buy_insurance"


def test_dict_action_with_custom_aliases():
    """Dict-form action works with custom aliases."""
    aliases = {"stop": ["stop", "halt", "cease"]}
    assert _normalize_action({"skill_name": "halt"}, action_aliases=aliases) == "stop"


def test_flood_aliases_constant_is_exported():
    """_FLOOD_ACTION_ALIASES is accessible for inspection."""
    assert "buy_insurance" in _FLOOD_ACTION_ALIASES
    assert "elevate" in _FLOOD_ACTION_ALIASES
    assert isinstance(_FLOOD_ACTION_ALIASES["buy_insurance"], list)
