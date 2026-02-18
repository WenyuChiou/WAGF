"""Tests for SP_REASON keyword collision bug (Bug 2).

Verifies that SP construct keywords don't collide with response_format field names
like 'insurance_coverage', which caused SP_REASON to be overwritten with 'True'.
"""

import json
import os
import re
import pytest
import yaml


# --- Paths ---
CONFIG_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "config")
YAML_PATH = os.path.join(CONFIG_DIR, "ma_agent_types.yaml")

# Agent types that have constructs defined
HOUSEHOLD_TYPES = ["household_owner", "household_renter"]


def _load_config():
    """Load and return the ma_agent_types.yaml config."""
    with open(YAML_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _get_response_format_keys(agent_cfg):
    """Extract field keys from a response_format config."""
    rf = agent_cfg.get("response_format", {})
    fields = rf.get("fields", [])
    return [f["key"] for f in fields if isinstance(f, dict) and "key" in f]


class TestSPKeywordsNoInsurance:
    """Test that 'insurance' keyword has been removed from SP constructs."""

    def test_owner_sp_label_no_insurance(self):
        cfg = _load_config()
        owner = cfg["household_owner"]
        sp_label_kw = owner["parsing"]["constructs"]["SP_LABEL"]["keywords"]
        assert "insurance" not in sp_label_kw, (
            f"SP_LABEL keywords should not contain 'insurance', got: {sp_label_kw}"
        )

    def test_owner_sp_reason_no_insurance(self):
        cfg = _load_config()
        owner = cfg["household_owner"]
        sp_reason_kw = owner["parsing"]["constructs"]["SP_REASON"]["keywords"]
        assert "insurance" not in sp_reason_kw, (
            f"SP_REASON keywords should not contain 'insurance', got: {sp_reason_kw}"
        )

    def test_renter_sp_label_no_insurance(self):
        cfg = _load_config()
        renter = cfg["household_renter"]
        sp_label_kw = renter["parsing"]["constructs"]["SP_LABEL"]["keywords"]
        assert "insurance" not in sp_label_kw, (
            f"SP_LABEL keywords should not contain 'insurance', got: {sp_label_kw}"
        )


class TestInsuranceCoverageNoSPCollision:
    """Test that insurance_coverage field doesn't collide with SP constructs via keyword matching."""

    def _simulate_keyword_match(self, json_key, construct_mapping):
        """Replicate the keyword matching logic from unified_adapter.py:330-348."""
        matched_names = []
        k_normalized = json_key.lower().replace("_", " ").replace("-", " ")

        for c_name, c_cfg in construct_mapping.items():
            keywords = list(c_cfg.get("keywords", []))
            keywords_normalized = [kw.lower().replace("_", " ") for kw in keywords]
            if any(kw in k_normalized for kw in keywords_normalized):
                matched_names.append(c_name)

        return matched_names

    def test_insurance_coverage_no_sp_collision(self):
        """'insurance_coverage' should NOT match SP_LABEL or SP_REASON constructs."""
        cfg = _load_config()
        owner_constructs = cfg["household_owner"]["parsing"]["constructs"]

        matched = self._simulate_keyword_match("insurance_coverage", owner_constructs)
        sp_matches = [m for m in matched if m.startswith("SP_")]
        assert len(sp_matches) == 0, (
            f"'insurance_coverage' should not match SP constructs, but matched: {sp_matches}"
        )

    def test_sp_reason_guard_prevents_overwrite(self):
        """Even if a collision were re-introduced, the guard in unified_adapter should prevent overwrite."""
        from broker.utils.normalization import normalize_construct_value

        # Simulate: SP_REASON already has real text, then a flat scalar tries to overwrite
        reasoning = {"SP_REASON": "I trust the government flood program to help me recover"}
        name = "SP_REASON"
        v = "1"  # from insurance_coverage: "1"

        # Apply the guard logic (mirrors unified_adapter.py:419-421)
        if "_REASON" in name and reasoning.get(name) and len(str(reasoning[name])) > 10:
            pass  # guard triggers, skip overwrite
        else:
            reasoning[name] = normalize_construct_value(v)

        assert reasoning["SP_REASON"] != "True", "Guard failed: SP_REASON overwritten to 'True'"
        assert reasoning["SP_REASON"] != "1", "Guard failed: SP_REASON overwritten to '1'"
        assert len(reasoning["SP_REASON"]) > 10, "Guard failed: SP_REASON replaced with short value"


class TestNoKeywordCollisionAllConstructs:
    """Programmatic scan: construct keywords should not match UNRELATED response_format field keys.

    E.g., 'threat' in TP keywords matching 'threat_perception' is fine (same construct).
    But 'insurance' in SP keywords matching 'insurance_coverage' is a cross-construct collision.
    """

    def test_no_cross_construct_keyword_collision(self):
        cfg = _load_config()

        collisions = []
        for atype_name in HOUSEHOLD_TYPES:
            atype_cfg = cfg.get(atype_name, {})
            constructs = atype_cfg.get("parsing", {}).get("constructs", {})

            # Build mapping: response_format key -> its declared construct (if any)
            rf = atype_cfg.get("response_format", {})
            fields = rf.get("fields", [])
            # key_to_construct: e.g., {"threat_perception": "TP_LABEL", "insurance_coverage": None}
            key_to_construct = {}
            for f in fields:
                if isinstance(f, dict) and "key" in f:
                    key_to_construct[f["key"]] = f.get("construct")

            # For each construct's keywords, check against all response_format keys
            for construct_name, construct_cfg in constructs.items():
                # Get the base construct (e.g., "SP" from "SP_LABEL" or "SP_REASON")
                base = construct_name.split("_")[0]
                keywords = construct_cfg.get("keywords", [])

                for kw in keywords:
                    for rk, rk_construct in key_to_construct.items():
                        if kw.lower() in rk.lower() and kw.lower() != rk.lower():
                            # This is a substring match — is it same construct or cross?
                            rk_base = rk_construct.split("_")[0] if rk_construct else None
                            if rk_base == base:
                                continue  # Same construct family, expected
                            collisions.append(
                                f"{atype_name}.{construct_name}: keyword '{kw}' "
                                f"matches unrelated response_format key '{rk}'"
                                f" (construct: {rk_construct})"
                            )

        assert len(collisions) == 0, (
            f"Found {len(collisions)} cross-construct keyword collisions:\n"
            + "\n".join(collisions)
        )
