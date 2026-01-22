"""
Test FloodSurveyLoader (MA-specific extension).
"""

import unittest
import sys
from pathlib import Path

# Adjust path to import packages
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from examples.multi_agent.survey.flood_survey_loader import (
    FloodSurveyRecord,
    FloodSurveyLoader,
    FLOOD_COLUMN_MAPPING
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

    def test_agent_initializer_creates_flood_extension(self):
        """AgentInitializer should auto-detect and create flood extensions."""
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

        # Create extensions
        extensions = initializer._create_extensions(flood_record)

        # Should have flood extension
        self.assertIn("flood", extensions)
        self.assertTrue(hasattr(extensions["flood"], "flood_experience"))
        self.assertTrue(extensions["flood"].flood_experience)
        self.assertFalse(extensions["flood"].financial_loss)

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


if __name__ == "__main__":
    unittest.main()
