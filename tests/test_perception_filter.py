"""Tests for Perception Filter Implementation."""
import pytest
from broker.components.social.perception import (
    HouseholdPerceptionFilter,
    GovernmentPerceptionFilter,
    InsurancePerceptionFilter,
    PerceptionFilterRegistry,
    DOLLAR_AMOUNT_FIELDS,
    PERCENTAGE_FIELDS,
)


class TestFloodDepthToQualitative:
    """Test flood depth conversion to qualitative descriptors."""

    def test_ankle_deep_water(self):
        """Depth 0.0-0.5 ft converts to ankle-deep water."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 0.3, "property_value": 100000}
        result = filter.filter(context)

        assert "flood_depth_description" in result
        assert result["flood_depth_description"] == "ankle-deep water"
        assert "depth_ft" not in result

    def test_knee_deep_water(self):
        """Depth 0.5-2.0 ft converts to knee-deep water."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 1.5, "property_value": 100000}
        result = filter.filter(context)

        assert result["flood_depth_description"] == "knee-deep water"

    def test_waist_deep_water(self):
        """Depth 2.0-4.0 ft converts to waist-deep water."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 3.2, "property_value": 100000}
        result = filter.filter(context)

        assert result["flood_depth_description"] == "waist-deep water"

    def test_chest_deep_water(self):
        """Depth 4.0-8.0 ft converts to chest-deep water."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 6.0, "property_value": 100000}
        result = filter.filter(context)

        assert result["flood_depth_description"] == "chest-deep water"

    def test_over_head_water(self):
        """Depth 8.0+ ft converts to over-head water."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 10.5, "property_value": 100000}
        result = filter.filter(context)

        assert result["flood_depth_description"] == "over-head water"

    def test_boundary_values(self):
        """Test boundary values between ranges."""
        filter = HouseholdPerceptionFilter()

        # Exactly 0.5 should be knee-deep (range is [0.5, 2.0))
        result = filter.filter({"depth_ft": 0.5, "property_value": 100000})
        assert result["flood_depth_description"] == "knee-deep water"

        # Exactly 2.0 should be waist-deep
        result = filter.filter({"depth_ft": 2.0, "property_value": 100000})
        assert result["flood_depth_description"] == "waist-deep water"


class TestDamageRatioToQualitative:
    """Test damage ratio conversion to severity descriptors."""

    def test_minimal_damage(self):
        """Ratio 0.0-0.05 converts to minimal damage."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 2000, "property_value": 100000}  # 2%
        result = filter.filter(context)

        assert result["damage_severity"] == "minimal damage"

    def test_minor_damage(self):
        """Ratio 0.05-0.15 converts to minor damage."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 10000, "property_value": 100000}  # 10%
        result = filter.filter(context)

        assert result["damage_severity"] == "minor damage"

    def test_moderate_damage(self):
        """Ratio 0.15-0.30 converts to moderate damage."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 22000, "property_value": 100000}  # 22%
        result = filter.filter(context)

        assert result["damage_severity"] == "moderate damage"

    def test_significant_damage(self):
        """Ratio 0.30-0.50 converts to significant damage."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 40000, "property_value": 100000}  # 40%
        result = filter.filter(context)

        assert result["damage_severity"] == "significant damage"

    def test_devastating_damage(self):
        """Ratio 0.50+ converts to devastating damage."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 75000, "property_value": 100000}  # 75%
        result = filter.filter(context)

        assert result["damage_severity"] == "devastating damage"

    def test_dollar_amounts_removed(self):
        """Exact dollar amounts are removed from household context."""
        filter = HouseholdPerceptionFilter()

        context = {
            "damage_amount": 25000,
            "property_value": 100000,
            "payout_amount": 20000,
            "oop_cost": 5000,
            "premium_cost": 1200,
            "elevation_cost": 30000,
        }
        result = filter.filter(context)

        for field in DOLLAR_AMOUNT_FIELDS:
            assert field not in result, f"{field} should be removed"


class TestMgHasLimitedObservables:
    """Test that MG agents have limited access to community observables."""

    def test_mg_agent_loses_community_stats(self):
        """MG agents cannot see community-wide statistics."""
        filter = HouseholdPerceptionFilter()

        # Create MG agent
        agent = type('Agent', (), {'is_mg': True})()

        context = {
            "my_property_value": 100000,
            "my_flood_history": 2,
            "insurance_penetration_rate": 0.45,
            "elevation_penetration_rate": 0.30,
            "adaptation_rate": 0.55,
            "relocation_rate": 0.05,
            "avg_community_damage": 15000,
        }
        result = filter.filter(context, agent)

        # Should keep personal observables
        assert "my_property_value" in result
        assert "my_flood_history" in result

        # Should NOT have community observables
        assert "insurance_penetration_rate" not in result
        assert "elevation_penetration_rate" not in result
        assert "adaptation_rate" not in result
        assert "relocation_rate" not in result
        assert "avg_community_damage" not in result

    def test_non_mg_agent_sees_all(self):
        """Non-MG agents see community observables."""
        filter = HouseholdPerceptionFilter()

        # Create non-MG agent
        agent = type('Agent', (), {'is_mg': False})()

        context = {
            "my_property_value": 100000,
            "adaptation_rate": 0.55,
            "year": 5,
        }
        result = filter.filter(context, agent)

        # Should keep adaptation_rate for non-MG
        assert "adaptation_rate" in result
        assert result["adaptation_rate"] == 0.55

    def test_mg_via_marginalized_group_attribute(self):
        """MG status detected via marginalized_group attribute."""
        filter = HouseholdPerceptionFilter()

        agent = type('Agent', (), {'marginalized_group': True})()

        context = {
            "my_data": 100,
            "community_flood_history": [1, 2, 3],
        }
        result = filter.filter(context, agent)

        assert "my_data" in result
        assert "community_flood_history" not in result

    def test_mg_agent_as_dict(self):
        """MG status detected when agent is a dict."""
        filter = HouseholdPerceptionFilter()

        agent = {"is_mg": True, "agent_id": "a1"}

        context = {
            "my_income": 50000,
            "neighbor_insurance_rate": 0.40,
        }
        result = filter.filter(context, agent)

        assert "my_income" in result
        assert "neighbor_insurance_rate" not in result


class TestNeighborActionsQualitative:
    """Test neighbor action count conversion to qualitative descriptions."""

    def test_none_of_neighbors(self):
        """Count 0 converts to 'none of your neighbors'."""
        filter = HouseholdPerceptionFilter()

        context = {"neighbors_insured": 0, "property_value": 100000}
        result = filter.filter(context)

        assert result["neighbors_insured_description"] == "none of your neighbors"
        assert "neighbors_insured" not in result

    def test_few_neighbors(self):
        """Count 1-2 converts to 'a few of your neighbors'."""
        filter = HouseholdPerceptionFilter()

        context = {"neighbors_elevated": 2, "property_value": 100000}
        result = filter.filter(context)

        assert result["neighbors_elevated_description"] == "a few of your neighbors"

    def test_some_neighbors(self):
        """Count 3-5 converts to 'some of your neighbors'."""
        filter = HouseholdPerceptionFilter()

        context = {"neighbors_relocated": 4, "property_value": 100000}
        result = filter.filter(context)

        assert result["neighbors_relocated_description"] == "some of your neighbors"

    def test_many_neighbors(self):
        """Count 6-10 converts to 'many of your neighbors'."""
        filter = HouseholdPerceptionFilter()

        context = {"neighbors_insured": 8, "property_value": 100000}
        result = filter.filter(context)

        assert result["neighbors_insured_description"] == "many of your neighbors"

    def test_most_neighbors(self):
        """Count 11+ converts to 'most of your neighbors'."""
        filter = HouseholdPerceptionFilter()

        context = {"neighbors_elevated": 15, "property_value": 100000}
        result = filter.filter(context)

        assert result["neighbors_elevated_description"] == "most of your neighbors"


class TestGovernmentSeesAllNumbers:
    """Test that government agents see full numerical data."""

    def test_government_keeps_all_numbers(self):
        """Government filter preserves all numerical data."""
        filter = GovernmentPerceptionFilter()

        context = {
            "depth_ft": 3.2,
            "damage_amount": 35000,
            "property_value": 100000,
            "payout_amount": 28000,
            "insurance_penetration_rate": 0.45,
            "elevation_penetration_rate": 0.30,
            "neighbors_insured": 5,
        }
        result = filter.filter(context)

        # All original fields should be preserved
        assert result["depth_ft"] == 3.2
        assert result["damage_amount"] == 35000
        assert result["property_value"] == 100000
        assert result["payout_amount"] == 28000
        assert result["insurance_penetration_rate"] == 0.45
        assert result["elevation_penetration_rate"] == 0.30
        assert result["neighbors_insured"] == 5

    def test_government_adds_perception_note(self):
        """Government filter adds perception note."""
        filter = GovernmentPerceptionFilter()

        context = {"depth_ft": 2.5}
        result = filter.filter(context)

        assert "_perception_note" in result
        assert "Full numerical data" in result["_perception_note"]

    def test_government_agent_type(self):
        """Government filter reports correct agent type."""
        filter = GovernmentPerceptionFilter()
        assert filter.agent_type == "government"


class TestInsuranceSeesAllNumbers:
    """Test that insurance agents see full numerical data."""

    def test_insurance_keeps_all_numbers(self):
        """Insurance filter preserves all numerical data."""
        filter = InsurancePerceptionFilter()

        context = {
            "damage_amount": 50000,
            "property_value": 200000,
            "premium_cost": 2400,
            "payout_amount": 45000,
            "insurance_penetration_rate": 0.65,
        }
        result = filter.filter(context)

        # All original fields should be preserved
        assert result["damage_amount"] == 50000
        assert result["property_value"] == 200000
        assert result["premium_cost"] == 2400
        assert result["payout_amount"] == 45000
        assert result["insurance_penetration_rate"] == 0.65

    def test_insurance_adds_perception_note(self):
        """Insurance filter adds perception note."""
        filter = InsurancePerceptionFilter()

        context = {"premium_cost": 1800}
        result = filter.filter(context)

        assert "_perception_note" in result
        assert "Policyholder" in result["_perception_note"] or "actuarial" in result["_perception_note"]

    def test_insurance_agent_type(self):
        """Insurance filter reports correct agent type."""
        filter = InsurancePerceptionFilter()
        assert filter.agent_type == "insurance"


class TestRegistryDefaultFilters:
    """Test PerceptionFilterRegistry default filter registration."""

    def test_default_filters_registered(self):
        """Registry registers default filters on initialization."""
        registry = PerceptionFilterRegistry()

        assert registry.get("household") is not None
        assert registry.get("government") is not None
        assert registry.get("insurance") is not None

    def test_registered_types_list(self):
        """Registry provides list of registered agent types."""
        registry = PerceptionFilterRegistry()

        types = registry.registered_types
        assert "household" in types
        assert "government" in types
        assert "insurance" in types

    def test_can_disable_default_registration(self):
        """Registry can be created without default filters."""
        registry = PerceptionFilterRegistry(register_defaults=False)

        assert registry.get("household") is None
        assert registry.get("government") is None
        assert len(registry.registered_types) == 0

    def test_custom_filter_registration(self):
        """Custom filters can be registered."""
        registry = PerceptionFilterRegistry(register_defaults=False)

        class CustomFilter:
            agent_type = "custom"

            def filter(self, context, agent=None):
                return {"custom": True}

        registry.register("custom", CustomFilter())

        assert registry.get("custom") is not None
        result = registry.filter_context("custom", {"data": 1})
        assert result == {"custom": True}


class TestUnknownTypeDefaultsToHousehold:
    """Test fallback behavior for unknown agent types."""

    def test_unknown_type_uses_household_filter(self):
        """Unknown agent type defaults to household perception."""
        registry = PerceptionFilterRegistry()

        context = {
            "depth_ft": 2.5,
            "damage_amount": 30000,
            "property_value": 100000,
        }

        # Filter for unknown type
        result = registry.filter_context("alien_observer", context)

        # Should have qualitative descriptors like household
        assert "flood_depth_description" in result
        assert "depth_ft" not in result
        assert "damage_severity" in result
        assert "damage_amount" not in result

    def test_unknown_type_no_default_filter(self):
        """Unknown type with no defaults still uses household pattern."""
        registry = PerceptionFilterRegistry(register_defaults=False)

        context = {
            "depth_ft": 1.0,
            "damage_amount": 5000,
            "property_value": 100000,
        }

        # Should create a household filter as fallback
        result = registry.filter_context("unknown", context)

        assert "flood_depth_description" in result
        assert result["flood_depth_description"] == "knee-deep water"


class TestHouseholdFilterEdgeCases:
    """Test edge cases for household perception filter."""

    def test_empty_context(self):
        """Empty context returns empty result."""
        filter = HouseholdPerceptionFilter()
        result = filter.filter({})
        # Empty context has no fields to transform
        assert result == {}

    def test_no_agent_provided(self):
        """Filter works without agent parameter."""
        filter = HouseholdPerceptionFilter()

        context = {"depth_ft": 1.5, "property_value": 100000}
        result = filter.filter(context)

        assert "flood_depth_description" in result

    def test_zero_property_value(self):
        """Handles zero property value without division error."""
        filter = HouseholdPerceptionFilter()

        context = {"damage_amount": 5000, "property_value": 0}
        # Should not raise ZeroDivisionError
        result = filter.filter(context)

        # When property_value is 0, damage_severity is skipped (undefined ratio)
        # The filter should not crash
        assert "damage_amount" not in result  # dollar amount removed
        assert "property_value" not in result  # dollar amount removed

    def test_preserves_unknown_fields(self):
        """Fields not in removal lists are preserved."""
        filter = HouseholdPerceptionFilter()

        context = {
            "year": 5,
            "agent_id": "a1",
            "custom_field": "value",
            "property_value": 100000,
        }
        result = filter.filter(context)

        assert result["year"] == 5
        assert result["agent_id"] == "a1"
        assert result["custom_field"] == "value"

    def test_household_agent_type_property(self):
        """Household filter reports correct agent type."""
        filter = HouseholdPerceptionFilter()
        assert filter.agent_type == "household"


class TestRegistryFilterContext:
    """Test registry's filter_context method."""

    def test_filter_context_household(self):
        """filter_context applies household filter correctly."""
        registry = PerceptionFilterRegistry()

        context = {"depth_ft": 5.0, "property_value": 100000}
        result = registry.filter_context("household", context)

        assert result["flood_depth_description"] == "chest-deep water"

    def test_filter_context_government(self):
        """filter_context applies government filter correctly."""
        registry = PerceptionFilterRegistry()

        context = {"depth_ft": 5.0, "damage_amount": 50000}
        result = registry.filter_context("government", context)

        assert result["depth_ft"] == 5.0
        assert result["damage_amount"] == 50000

    def test_filter_context_with_agent(self):
        """filter_context passes agent to filter."""
        registry = PerceptionFilterRegistry()

        agent = type('Agent', (), {'is_mg': True})()
        context = {"adaptation_rate": 0.5, "my_data": 100}

        result = registry.filter_context("household", context, agent)

        assert "my_data" in result
        assert "adaptation_rate" not in result


class TestPercentageFieldsRemoval:
    """Test that percentage fields are removed for household perception."""

    def test_percentage_fields_removed(self):
        """Exact percentage fields are removed from household context."""
        filter = HouseholdPerceptionFilter()

        context = {
            "insurance_penetration_rate": 0.45,
            "elevation_penetration_rate": 0.30,
            "property_value": 100000,
        }
        result = filter.filter(context)

        for field in PERCENTAGE_FIELDS:
            assert field not in result, f"{field} should be removed"
