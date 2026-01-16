#!/usr/bin/env python3
"""
Test script for survey-based agent initialization.

Tests:
1. Survey loading and validation
2. MG classification
3. Position assignment (depth sampling)
4. RCV generation
5. Full agent profile creation
"""

import sys
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def test_survey_loader():
    """Test survey data loading."""
    from survey.survey_loader import SurveyLoader, load_survey_data

    survey_path = Path(__file__).parent.parent / "multi_agent" / "input" / "initial_household data.xlsx"

    if not survey_path.exists():
        logger.warning(f"Survey file not found: {survey_path}")
        return False

    logger.info("=== Testing Survey Loader ===")

    loader = SurveyLoader()
    records = loader.load(survey_path, max_records=50)

    logger.info(f"Loaded {len(records)} records")
    logger.info(f"Validation errors: {len(loader.validation_errors)}")

    if records:
        r = records[0]
        logger.info(f"Sample record: {r.record_id}")
        logger.info(f"  Family size: {r.family_size}")
        logger.info(f"  Income: {r.income_bracket}")
        logger.info(f"  Housing: {r.housing_status}")
        logger.info(f"  Flood experience: {r.flood_experience}")
        logger.info(f"  Has children: {r.has_children}")

    return len(records) > 0


def test_mg_classifier():
    """Test MG classification."""
    from survey.survey_loader import SurveyLoader
    from survey.mg_classifier import MGClassifier

    survey_path = Path(__file__).parent.parent / "multi_agent" / "input" / "initial_household data.xlsx"

    if not survey_path.exists():
        logger.warning(f"Survey file not found: {survey_path}")
        return False

    logger.info("=== Testing MG Classifier ===")

    loader = SurveyLoader()
    records = loader.load(survey_path, max_records=100)

    classifier = MGClassifier()
    results, stats = classifier.classify_batch(records)

    logger.info(f"Classification results:")
    logger.info(f"  Total: {stats['total']}")
    logger.info(f"  MG: {stats['mg_count']} ({stats['mg_ratio']:.1%})")
    logger.info(f"  NMG: {stats['nmg_count']}")
    logger.info(f"  Criteria breakdown:")
    logger.info(f"    Housing burden: {stats['housing_burden_count']}")
    logger.info(f"    No vehicle: {stats['no_vehicle_count']}")
    logger.info(f"    Below poverty: {stats['below_poverty_count']}")

    return stats['total'] > 0


def test_depth_sampler():
    """Test depth sampling for position assignment."""
    from survey.survey_loader import SurveyLoader
    from hazard.depth_sampler import DepthSampler

    survey_path = Path(__file__).parent.parent / "multi_agent" / "input" / "initial_household data.xlsx"

    if not survey_path.exists():
        logger.warning(f"Survey file not found: {survey_path}")
        return False

    logger.info("=== Testing Depth Sampler ===")

    loader = SurveyLoader()
    records = loader.load(survey_path, max_records=50)

    sampler = DepthSampler(seed=42)
    assignments, zone_counts = sampler.assign_batch(records)

    logger.info(f"Position assignments:")
    for zone, count in zone_counts.items():
        logger.info(f"  {zone}: {count}")

    if assignments:
        a = assignments[0]
        logger.info(f"Sample assignment:")
        logger.info(f"  Zone: {a.zone_name}")
        logger.info(f"  Base depth: {a.base_depth_m:.3f}m")
        logger.info(f"  Flood probability: {a.flood_probability:.2f}")

    return len(assignments) > 0


def test_rcv_generator():
    """Test RCV generation."""
    from hazard.rcv_generator import RCVGenerator

    logger.info("=== Testing RCV Generator ===")

    gen = RCVGenerator(seed=42)

    # Test owner, high income
    rcv1 = gen.generate(
        income_bracket="75k_or_more",
        is_owner=True,
        is_mg=False,
        family_size=4,
    )
    logger.info(f"Owner (high income, NMG):")
    logger.info(f"  Building: ${rcv1.building_rcv_usd:,.0f}")
    logger.info(f"  Contents: ${rcv1.contents_rcv_usd:,.0f}")

    # Test owner, low income, MG
    rcv2 = gen.generate(
        income_bracket="less_than_25k",
        is_owner=True,
        is_mg=True,
        family_size=3,
    )
    logger.info(f"Owner (low income, MG):")
    logger.info(f"  Building: ${rcv2.building_rcv_usd:,.0f}")
    logger.info(f"  Contents: ${rcv2.contents_rcv_usd:,.0f}")

    # Test renter
    rcv3 = gen.generate(
        income_bracket="50k_to_60k",
        is_owner=False,
        is_mg=False,
        family_size=2,
    )
    logger.info(f"Renter (mid income):")
    logger.info(f"  Building: ${rcv3.building_rcv_usd:,.0f}")
    logger.info(f"  Contents: ${rcv3.contents_rcv_usd:,.0f}")

    return True


def test_vulnerability():
    """Test vulnerability calculation."""
    from hazard.vulnerability import VulnerabilityCalculator

    logger.info("=== Testing Vulnerability Calculator ===")

    calc = VulnerabilityCalculator(ffe_ft=0.5)

    # Test at different depths
    depths_m = [0.0, 0.5, 1.0, 2.0, 3.0]
    rcv = 300_000
    contents = 150_000

    for depth in depths_m:
        result = calc.calculate_damage(
            depth_m=depth,
            rcv_usd=rcv,
            contents_usd=contents,
            is_owner=True,
        )
        logger.info(
            f"Depth {depth:.1f}m: "
            f"Structure ${result.structure_damage_usd:,.0f} ({result.structure_damage_ratio:.1%}), "
            f"Contents ${result.contents_damage_usd:,.0f} ({result.contents_damage_ratio:.1%})"
        )

    return True


def test_full_integration():
    """Test full agent initialization pipeline."""
    from survey.agent_initializer import initialize_agents_from_survey

    survey_path = Path(__file__).parent.parent / "multi_agent" / "input" / "initial_household data.xlsx"

    if not survey_path.exists():
        logger.warning(f"Survey file not found: {survey_path}")
        return False

    logger.info("=== Testing Full Integration ===")

    profiles, stats = initialize_agents_from_survey(
        survey_path=survey_path,
        max_agents=20,
        seed=42,
        include_hazard=True,
        include_rcv=True,
    )

    logger.info(f"Statistics:")
    for key, value in stats.items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.3f}")
        else:
            logger.info(f"  {key}: {value}")

    if profiles:
        p = profiles[0]
        logger.info(f"\nSample agent profile ({p.agent_id}):")
        logger.info(f"  Group: {p.group_label}")
        logger.info(f"  Identity: {p.identity}")
        logger.info(f"  Family size: {p.family_size}")
        logger.info(f"  Income: {p.income_bracket}")
        logger.info(f"  Flood zone: {p.flood_zone}")
        logger.info(f"  Base depth: {p.base_depth_m:.3f}m")
        logger.info(f"  Building RCV: ${p.building_rcv_usd:,.0f}")
        logger.info(f"  Contents RCV: ${p.contents_rcv_usd:,.0f}")
        logger.info(f"\nNarrative persona:")
        logger.info(f"  {p.generate_narrative_persona()}")
        logger.info(f"\nFlood experience:")
        logger.info(f"  {p.generate_flood_experience_summary()}")

    return len(profiles) > 0


def main():
    """Run all tests."""
    logger.info("=" * 60)
    logger.info("Survey-Based Agent Initialization Tests")
    logger.info("=" * 60)

    results = {}

    # Run tests
    results["survey_loader"] = test_survey_loader()
    results["mg_classifier"] = test_mg_classifier()
    results["depth_sampler"] = test_depth_sampler()
    results["rcv_generator"] = test_rcv_generator()
    results["vulnerability"] = test_vulnerability()
    results["full_integration"] = test_full_integration()

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Test Summary")
    logger.info("=" * 60)

    all_passed = True
    for test, passed in results.items():
        status = "PASS" if passed else "FAIL"
        logger.info(f"  {test}: {status}")
        if not passed:
            all_passed = False

    logger.info("=" * 60)
    logger.info(f"Overall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    logger.info("=" * 60)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
