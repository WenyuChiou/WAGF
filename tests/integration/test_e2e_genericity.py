"""Phase 6Q-F-2 (2026-05-26) — End-to-end genericity gate for a
non-water domain.

Phase 6Q-F-1 (commit fdd0dcf) landed the structural + sys-modules
gates using an inline ``FakeTrafficDomainPack`` defined in the test
file itself. That gate proves the **dispatcher** path stays
water-module-free for a non-water domain.

This file (Phase 6Q-F-2) promotes the fixture to a proper package at
``examples/_test_fixtures/fake_traffic/`` with YAML configs +
MockTrafficLLM responses, then exercises **deeper layers** of the
broker pipeline that the 6Q-F-1 gate didn't touch:

  - Skill registry YAML parsing for a non-water domain
  - Agent-type YAML parsing with `psychological_framework: ""`
    (FRAMEWORK_ESCAPE_HATCH path)
  - DomainPack registration via the explicit-import contract
    (Phase 6Q-G)
  - Mock LLM responses produce parseable broker payloads
  - sys.modules cleanliness under the new package import

**Scope: 6Q-F-2-a (foundation, this commit)** — fixture package +
construct-time assertions. The 1-year synthetic ``ExperimentRunner.run``
+ audit-CSV assertions land in **6Q-F-2-b** (next session).

Why split:
  - 6Q-F-2-a is read-only verification of the fixture package
    structure + import graph; ~150 LOC test, ~250 LOC fixtures.
  - 6Q-F-2-b is full runtime trace exercise that needs broker
    `ExperimentBuilder` config knobs + lifecycle hook wiring,
    closer to ~400 LOC + ~2 hr.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


# ─────────────────────────────────────────────────────────────────────
# Fixture package import gate
# ─────────────────────────────────────────────────────────────────────

class TestFakeTrafficPackageImport:
    """The fixture package must import + register cleanly."""

    def test_package_importable(self):
        # If the package __init__ has an unhandled exception this would
        # raise — assertion via successful import.
        import examples._test_fixtures.fake_traffic  # noqa: F401

    def test_domain_pack_registered(self):
        import examples._test_fixtures.fake_traffic  # noqa: F401
        from broker.domains.registry import DomainPackRegistry
        from examples._test_fixtures.fake_traffic.pack import (
            FakeTrafficDomainPack,
        )

        pack = DomainPackRegistry.get("traffic")
        assert pack is not None, (
            "FakeTrafficDomainPack not registered after package import"
        )
        assert isinstance(pack, FakeTrafficDomainPack)

    def test_pack_uses_escape_hatch_framework(self):
        """The fixture's psychological_framework() must return the
        FRAMEWORK_ESCAPE_HATCH sentinel — this domain has no
        registered psychometric framework, by design."""
        import examples._test_fixtures.fake_traffic  # noqa: F401
        from broker.domains.registry import DomainPackRegistry
        from broker.validators.governance.thinking_validator import (
            FRAMEWORK_ESCAPE_HATCH,
        )

        pack = DomainPackRegistry.get_or_default("traffic")
        assert pack.psychological_framework() == FRAMEWORK_ESCAPE_HATCH


# ─────────────────────────────────────────────────────────────────────
# YAML config parse gate
# ─────────────────────────────────────────────────────────────────────

class TestTrafficYAMLConfigs:
    """YAML files parse + contain the expected non-water structure."""

    FIXTURE_DIR = (
        Path(__file__).resolve().parents[2]
        / "examples" / "_test_fixtures" / "fake_traffic"
    )

    def test_skill_registry_parses(self):
        import yaml
        path = self.FIXTURE_DIR / "traffic_skill_registry.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        assert data["domain"] == "traffic"
        skill_ids = [s["skill_id"] for s in data["skills"]]
        # 5 commuter skills + 1 dispatcher skill = 6 total.
        assert len(skill_ids) == 6
        assert "take_alternate_route" in skill_ids
        assert "switch_to_transit" in skill_ids
        assert "announce_advisory" in skill_ids
        # Sanity: no flood-domain skill names leaked.
        assert "elevate_house" not in skill_ids
        assert "buy_insurance" not in skill_ids
        assert "relocate" not in skill_ids

    def test_agent_types_parses_with_escape_hatch_framework(self):
        import yaml
        path = self.FIXTURE_DIR / "traffic_agent_types.yaml"
        data = yaml.safe_load(path.read_text(encoding="utf-8"))

        assert data["global_config"]["governance"]["domain"] == "traffic"
        # Phase 6Q-D contract: framework="" is the escape hatch sentinel.
        assert data["commuter"]["psychological_framework"] == ""
        assert data["dispatcher"]["psychological_framework"] == ""
        # Phase 6Q-C contract: stimulus_key is required for memory engine.
        assert data["global_config"]["memory"]["stimulus_key"] == "congestion_level"


# ─────────────────────────────────────────────────────────────────────
# Mock LLM response gate
# ─────────────────────────────────────────────────────────────────────

class TestMockTrafficLLM:
    """Mock responses parse as valid broker JSON payloads."""

    def test_responses_parse_as_json(self):
        from examples._test_fixtures.fake_traffic.mock_responses import (
            MOCK_TRAFFIC_RESPONSES,
        )
        for key, response in MOCK_TRAFFIC_RESPONSES.items():
            # Extract JSON between the broker's standard delimiters.
            start = response.index("<<<DECISION_START>>>") + len(
                "<<<DECISION_START>>>"
            )
            end = response.index("<<<DECISION_END>>>")
            payload = json.loads(response[start:end].strip())
            assert "reasoning" in payload, f"{key}: missing reasoning"
            assert "decision" in payload, f"{key}: missing decision"
            assert isinstance(payload["decision"], int)
            assert 1 <= payload["decision"] <= 5

    def test_mock_llm_class_year_dispatch(self):
        from examples._test_fixtures.fake_traffic.mock_responses import MockTrafficLLM
        mock = MockTrafficLLM()
        # Commuter responses are year-keyed.
        for year in [1, 2, 3]:
            response = mock.invoke("ignored prompt", year=year)
            assert "<<<DECISION_START>>>" in response
            assert "<<<DECISION_END>>>" in response
        # Dispatcher gets its own response.
        dispatcher_response = mock.invoke(
            "ignored prompt", year=1, agent_type="dispatcher"
        )
        assert "<<<DECISION_START>>>" in dispatcher_response

    def test_responses_contain_no_flood_vocabulary(self):
        from examples._test_fixtures.fake_traffic.mock_responses import (
            MOCK_TRAFFIC_RESPONSES,
        )
        # Regression guard — fake_traffic mocks must use traffic
        # vocabulary only. If a future copy-paste leaks flood words
        # into these canned responses, this fires.
        for key, response in MOCK_TRAFFIC_RESPONSES.items():
            low = response.lower()
            assert "flood" not in low, (
                f"{key}: flood vocabulary leaked into traffic mock"
            )
            assert "elevate_house" not in low
            assert "buy_insurance" not in low


# ─────────────────────────────────────────────────────────────────────
# sys.modules cleanliness (subprocess gate)
# ─────────────────────────────────────────────────────────────────────

# The structural runtime gate added in Phase 6Q-F-1 already proves
# `broker.components.governance.domain_validator_dispatch.build_domain_validators("traffic")`
# doesn't load `broker.domains.water.*`. Phase 6Q-F-2-a EXTENDS that
# to the new fixture-package import path: importing
# `examples._test_fixtures.fake_traffic` should NOT pull water in.
# (The fixture package explicitly does NOT import broker.domains.water
# — only governed_flood / irrigation_abm do, per Phase 6Q-G.)

_SUBPROCESS_SCRIPT = r"""
import sys, json
from broker.domains.registry import DomainPackRegistry
import examples._test_fixtures.fake_traffic  # noqa: F401 — registers traffic pack
# Verify registration succeeded.
assert DomainPackRegistry.get("traffic") is not None
# Dump water modules in sys.modules.
water = sorted(m for m in sys.modules if m.startswith("broker.domains.water"))
print(json.dumps({"water_modules": water}))
"""


class TestFakeTrafficSysModulesCleanliness:
    """Importing the traffic fixture package must NOT pull water
    modules into sys.modules. Subprocess-isolated."""

    def test_traffic_fixture_does_not_load_water(self):
        repo = Path(__file__).resolve().parents[2]
        result = subprocess.run(
            [sys.executable, "-c", _SUBPROCESS_SCRIPT],
            capture_output=True,
            text=True,
            cwd=str(repo),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"gate script failed (rc={result.returncode}):\n"
            f"STDOUT:\n{result.stdout}\n"
            f"STDERR:\n{result.stderr}"
        )
        payload = json.loads(result.stdout.strip().split("\n")[-1])
        assert not payload["water_modules"], (
            f"importing fake_traffic fixture leaked water modules: "
            f"{payload['water_modules']}"
        )
