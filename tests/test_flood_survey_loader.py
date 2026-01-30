"""
Test FloodSurveyLoader (MA-specific extension).
"""

import unittest
import sys
from pathlib import Path

# Adjust path to import packages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.multi_agent.flood.survey.flood_survey_loader import (
    FloodSurveyRecord,
    FloodSurveyLoader,
    FLOOD_COLUMN_MAPPING
)
from examples.multi_agent.flood.survey.ma_initializer import (
    MAAgentInitializer,
    MAAgentProfile,
    _create_flood_extension
)
from broker.modules.survey.survey_loader import SurveyRecord
from broker.modules.survey.agent_initializer import AgentInitializer


class TestFloodSurveyRecord(unittest.TestCase):
    """Test FloodSurveyRecord dataclass."""

    def test_flood_survey_record_inherits_from_survey_record(self):
        """FloodSurveyRecord should inherit from SurveyRecord."""
        record = FloodSurveyRecord(
            record_id="S0001",
            family_size=4,
            generations="2",
            income_bracket="50k_to_60k",
            housing_status="mortgage",
            house_type="single_family",
            housing_cost_burden=True,
            vehicle_ownership=True,
            children_under_6=True,
            children_6_18=False,
            elderly_over_65=False,
            raw_data={},
            flood_experience=True,
            financial_loss=False
        )

        # Should be instance of both FloodSurveyRecord and SurveyRecord
        self.assertIsInstance(record, FloodSurveyRecord)
        self.assertIsInstance(record, SurveyRecord)

        # Should have all base fields
        self.assertEqual(record.record_id, "S0001")
        self.assertEqual(record.family_size, 4)
        self.assertEqual(record.income_bracket, "50k_to_60k")

        # Should have flood-specific fields
        self.assertTrue(record.flood_experience)
        self.assertFalse(record.financial_loss)

    def test_flood_survey_record_defaults(self):
        """Flood fields should have defaults."""
        record = FloodSurveyRecord(
            record_id="S0001",
            family_size=4,
            generations="2",
            income_bracket="50k_to_60k",
            housing_status="mortgage",
            house_type="single_family",
            housing_cost_burden=True,
            vehicle_ownership=True,
            children_under_6=True,
            children_6_18=False,
            elderly_over_65=False,
            raw_data={}
        )

        # Flood fields should default to False
        self.assertFalse(record.flood_experience)
        self.assertFalse(record.financial_loss)


class TestFloodSurveyLoader(unittest.TestCase):
    """Test FloodSurveyLoader class."""

    def test_flood_column_mapping_includes_flood_fields(self):
        """FLOOD_COLUMN_MAPPING should include flood-specific fields."""
        self.assertIn("flood_experience", FLOOD_COLUMN_MAPPING)
        self.assertIn("financial_loss", FLOOD_COLUMN_MAPPING)

    def test_flood_survey_loader_uses_flood_mapping(self):
        """FloodSurveyLoader should use flood-specific mappings."""
        loader = FloodSurveyLoader()
        self.assertIn("flood_experience", loader.column_mapping)
        self.assertIn("financial_loss", loader.column_mapping)


class TestAgentInitializerIntegration(unittest.TestCase):
    """Test AgentInitializer integration with FloodSurveyRecord."""

    def test_generic_agent_initializer_returns_empty_extensions(self):
        """Generic AgentInitializer returns empty extensions (domain-agnostic design).

        As of Task-029, flood extensions are created by MAAgentInitializer,
        not the generic AgentInitializer.
        """
        initializer = AgentInitializer()

        # Create flood record
        flood_record = FloodSurveyRecord(
            record_id="S0001",
            family_size=4,
            generations="2",
            income_bracket="50k_to_60k",
            housing_status="mortgage",
            house_type="single_family",
            housing_cost_burden=True,
            vehicle_ownership=True,
            children_under_6=True,
            children_6_18=False,
            elderly_over_65=False,
            raw_data={},
            flood_experience=True,
            financial_loss=False
        )

        # Generic AgentInitializer returns empty extensions
        extensions = initializer._create_extensions(flood_record)

        # Should be empty (domain-agnostic)
        self.assertEqual(extensions, {})

    def test_agent_initializer_no_flood_extension_for_generic_record(self):
        """AgentInitializer should NOT create flood extension for generic records."""
        initializer = AgentInitializer()

        # Create generic record (no flood fields)
        generic_record = SurveyRecord(
            record_id="S0001",
            family_size=4,
            generations="2",
            income_bracket="50k_to_60k",
            housing_status="mortgage",
            house_type="single_family",
            housing_cost_burden=True,
            vehicle_ownership=True,
            children_under_6=True,
            children_6_18=False,
            elderly_over_65=False,
            raw_data={}
        )

        # Create extensions
        extensions = initializer._create_extensions(generic_record)

        # Should NOT have flood extension
        self.assertNotIn("flood", extensions)
        self.assertEqual(len(extensions), 0)


class TestMAAgentInitializer(unittest.TestCase):
    """Test MAAgentInitializer flood extension creation (Task-029 compliant)."""

    def test_ma_initializer_creates_flood_extension(self):
        """MAAgentInitializer should create flood extensions from FloodSurveyRecord."""
        # Create flood extension using the helper function
        flood_ext = _create_flood_extension(
            flood_experience=True,
            financial_loss=False
        )

        # Should have all required attributes
        self.assertTrue(flood_ext.flood_experience)
        self.assertFalse(flood_ext.financial_loss)
        self.assertEqual(flood_ext.flood_zone, "unknown")
        self.assertEqual(flood_ext.base_depth_m, 0.0)
        self.assertEqual(flood_ext.flood_probability, 0.0)
        self.assertEqual(flood_ext.building_rcv_usd, 0.0)
        self.assertEqual(flood_ext.contents_rcv_usd, 0.0)

    def test_ma_agent_profile_flattens_flood_extension(self):
        """MAAgentProfile.to_dict() should flatten flood extension."""
        # Create flood extension
        flood_ext = _create_flood_extension(
            flood_experience=True,
            financial_loss=True
        )

        # Create MAAgentProfile with flood extension
        profile = MAAgentProfile(
            agent_id="H0001",
            record_id="S0001",
            family_size=4,
            generations="2",
            income_bracket="50k_to_60k",
            income_midpoint=55000,
            housing_status="mortgage",
            house_type="single_family",
            is_classified=True,
            classification_score=2,
            classification_criteria={"housing_burden": True, "no_vehicle": True},
            has_children=True,
            has_elderly=False,
            has_vulnerable_members=True,
            extensions={"flood": flood_ext},
            raw_data={},
            narrative_fields=["income_bracket", "generations"],
            narrative_labels={"income_bracket": "Income", "generations": "Years in Area"},
        )

        # Convert to dict
        data = profile.to_dict()

        # Should have flattened flood fields
        self.assertTrue(data["flood_experience"])
        self.assertTrue(data["financial_loss"])
        self.assertEqual(data["flood_zone"], "unknown")
        self.assertEqual(data["base_depth_m"], 0.0)

        # Should have MG classification
        self.assertTrue(data["is_mg"])
        self.assertEqual(data["group"], "MG")
        self.assertEqual(data["mg_score"], 2)


if __name__ == "__main__":
    unittest.main()
