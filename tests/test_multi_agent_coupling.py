"""Phase 6E integration tests — multi-agent coupling generic behavior.

These tests prove (without an LLM smoke run) that the multi-agent path's
load-bearing primitives work for ANY agent_type vocabulary, not just
flood's household_*/government/insurance triple.

Reference: `.ai/ma_vaccination_findings_2026-05-10.md` Findings #1-3.
"""
from __future__ import annotations

import pytest

from broker.components.context.tiered import TieredContextBuilder


# ---------------------------------------------------------------------------
# Finding #1 regression: TieredContextBuilder accepts hub=None
# ---------------------------------------------------------------------------


class TestContextBuilderHubOptional:
    """Phase 6E Finding #1: TieredContextBuilder must construct without
    InteractionHub for multi-agent domains that don't need spatial gossip."""

    def test_construct_without_hub(self):
        """Caller omitting hub kwarg must succeed (was: TypeError)."""
        ctx = TieredContextBuilder(agents={})
        assert ctx.hub is None

    def test_construct_with_explicit_hub_none(self):
        """Explicit hub=None must also succeed."""
        ctx = TieredContextBuilder(agents={}, hub=None)
        assert ctx.hub is None

    def test_construct_with_dynamic_whitelist_only(self):
        """The hubless path — env→whitelist→template_vars→prompt — works
        in isolation. This is the coupling channel for non-spatial
        multi-agent domains (vaccination_ma, etc.)."""
        ctx = TieredContextBuilder(
            agents={},
            dynamic_whitelist=["custom_var_a", "custom_var_b"],
        )
        # The DynamicStateProvider in providers must exist and carry the
        # whitelist (Phase 1 verdict — broker provides env→whitelist
        # passthrough generically, no agent-type branching).
        # We only check construction succeeds; full data-flow test is the
        # smoke run (examples/vaccination_ma_demo/).
        assert ctx is not None


# ---------------------------------------------------------------------------
# Finding #3 regression: env dict mutation propagation pattern
# ---------------------------------------------------------------------------


class TestEnvDictAliasingPattern:
    """Phase 6E Finding #3: the dual-dict pitfall.

    When no simulation engine is provided, ExperimentRunner creates a
    fresh `env = {}` each year. A lifecycle hook that keeps its own
    `self.env` dict will see mid-year writes diverge from what
    ctx_builder reads.

    Recommended pattern: alias `self.env = env` in pre_year so
    post_step writes land directly in the dict ctx_builder consumes.

    These tests document the pattern is sound (no broker change needed;
    docs fix only).
    """

    def test_aliasing_preserves_post_step_writes(self):
        """Verify that aliasing self.env = env makes post_step mutations
        visible to anyone holding a reference to either dict."""

        class MockHook:
            def __init__(self):
                self.env = {"persistent_key": "carryover_from_last_year"}

            def pre_year(self, year, env, agents):
                # Pattern from vaccination_ma_demo/lifecycle_hooks.py:
                env.update(self.env)
                self.env = env   # alias
                self.env["year"] = year

            def post_step(self, agent_type, decision):
                # Simulated cross-agent write
                if agent_type == "phase_1_actor":
                    self.env["phase_1_output"] = decision

        hook = MockHook()
        runner_env: dict = {}   # mimics ExperimentRunner's fresh dict
        hook.pre_year(1, runner_env, {})
        hook.post_step("phase_1_actor", "decision_X")

        # Both views see phase_1_output (the goal):
        assert runner_env["phase_1_output"] == "decision_X"
        assert hook.env["phase_1_output"] == "decision_X"
        # Year was set during pre_year:
        assert runner_env["year"] == 1
        # Carryover from initial self.env was synced into runner_env:
        assert runner_env["persistent_key"] == "carryover_from_last_year"

    def test_naive_pattern_loses_mid_year_writes(self):
        """Negative case: without aliasing, post_step writes don't reach
        runner_env. This documents WHY the aliasing pattern is needed."""

        class NaiveHook:
            def __init__(self):
                self.env = {"foo": "bar"}

            def pre_year(self, year, env, agents):
                env.update(self.env)   # one-shot sync, no aliasing
                # self.env stays as a separate dict
                self.env["year"] = year

            def post_step(self, decision):
                self.env["mid_year_write"] = decision   # only mutates self.env

        hook = NaiveHook()
        runner_env: dict = {}
        hook.pre_year(1, runner_env, {})
        hook.post_step("decision_Y")

        # runner_env did NOT see the mid-year write — the bug Phase 6E
        # Finding #3 documents:
        assert "mid_year_write" not in runner_env
        assert hook.env["mid_year_write"] == "decision_Y"


# ---------------------------------------------------------------------------
# Phase 1 trace verdict: cross-agent state pipeline is domain-generic
# ---------------------------------------------------------------------------


class TestDynamicWhitelistIsDomainGeneric:
    """Phase 1 trace agent verdict (.ai/ma_vaccination_findings_2026-05-10.md):
    `env dict → dynamic_whitelist → top-level context → template_vars →
    SafeFormatter` has no flood-specific branching in broker.

    These tests assert the broker pieces of that pipeline accept arbitrary
    domain vocabularies (vaccination_ma, energy, traffic, etc.)."""

    def test_whitelist_accepts_arbitrary_keys(self):
        """DynamicStateProvider must accept any string key, not just
        flood-domain keys (govt_message, subsidy_rate, etc.)."""
        from broker.components.context.providers import DynamicStateProvider

        # Vaccination_ma keys
        p1 = DynamicStateProvider([
            "advisory_strength_label",
            "community_support_text",
            "outbreak_severity_label",
        ])
        # Energy_consumer keys
        p2 = DynamicStateProvider([
            "grid_load_label",
            "tariff_signal",
            "neighbor_avg_usage",
        ])
        # Traffic_commuter keys
        p3 = DynamicStateProvider([
            "commute_congestion_label",
            "transit_advisory",
        ])

        # Substantive check: each provider must actually accept its
        # respective env_context payload and propagate the whitelisted
        # keys into the context dict — not just have the right method
        # signature.
        for provider, env, expected_keys in [
            (p1, {"advisory_strength_label": "strong",
                  "community_support_text": "clinic open",
                  "outbreak_severity_label": "severe"},
             {"advisory_strength_label", "community_support_text",
              "outbreak_severity_label"}),
            (p2, {"grid_load_label": "high",
                  "tariff_signal": "peak",
                  "neighbor_avg_usage": "above avg"},
             {"grid_load_label", "tariff_signal", "neighbor_avg_usage"}),
            (p3, {"commute_congestion_label": "heavy",
                  "transit_advisory": "delayed"},
             {"commute_congestion_label", "transit_advisory"}),
        ]:
            context: dict = {}
            provider.provide("agent_id", {}, context, env_context=env)
            assert set(context.keys()) >= expected_keys, (
                f"provider {provider.whitelist} did not propagate "
                f"all expected keys: got {sorted(context.keys())}"
            )

    def test_whitelist_provider_passes_keys_through(self):
        """The env-context-to-template-var path is identity for whitelisted
        keys — verifies the Phase 1 verdict claim line by line."""
        from broker.components.context.providers import DynamicStateProvider

        whitelist = ["advisory_strength_label", "outbreak_severity_label"]
        provider = DynamicStateProvider(whitelist)

        env_context = {
            "advisory_strength_label": "strong",
            "outbreak_severity_label": "severe",
            "irrelevant_key": "should_not_propagate",
        }
        context: dict = {}

        # DynamicStateProvider.provide(agent_id, agents, context, env_context=...)
        provider.provide(
            "test_agent_id",
            {},  # agents dict
            context,
            env_context=env_context,
        )

        # Whitelisted keys propagated into context
        assert context.get("advisory_strength_label") == "strong"
        assert context.get("outbreak_severity_label") == "severe"
        # Non-whitelisted key did NOT propagate
        assert "irrelevant_key" not in context
