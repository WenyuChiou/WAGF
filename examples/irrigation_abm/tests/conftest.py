"""Skip only real-reference tests when the optional CRSS bundle is absent.

The fixture/name inventory comes from running this suite in a source copy
without ref/. Existing per-test availability guards remain in effect.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
_DATA_AVAILABLE = (ROOT / "ref/CRSS_DB/CRSS_DB").is_dir()

# These fixtures (including transitive dependencies in item.fixturenames)
# load real CRSS profiles. Other fixtures in the same modules are synthetic.
_CRSS_FIXTURES = {
    "test_v3_hindcast_agents": {"inputs"},
    "test_simple_prompt": {"simple_runs"},
    "test_v3_keepfix": {"pilots"},
    "test_llm_journal_resume": {"run_a", "crashed_run"},
    "test_workers_resume_integration": {"run_a", "resumed_b_workers4", "resumed_b_workers1"},
}
_CRSS_TESTS = {
    "test_paper_measures": {"test_recorded_replay_regression", "test_constant_level_benchmark"},
    "test_simple_p5": {"test_p5b_real_simple_run_does_not_require_removed_flow_text"},
    "test_simple_prompt": {"test_default_mock_run_exercises_every_removed_family"},
    "test_simple_prompt_check": {"test_strict_simple_always_increase_run_separates_supply_rule_feedback"},
    "test_v3_hindcast_agents": {"test_t4_precip_pin_mapping_and_projection_overlap",
                                "test_t12_scoring_parts_units_and_benchmarks"},
    "test_v3_keepfix": {"test_K6_is_hidden_when_priority_mode_is_senior_all"},
    "test_v3_prompt": {"test_persona_claims_hold_for_cluster_means"},
    "test_v3_workers_determinism": {"test_workers_1_4_8_byte_identical"},
    "test_llm_journal_resume": {"test_item49_off_derived_config_resumes_with_source_config_hash"},
}


def pytest_configure(config):
    config.addinivalue_line("markers", "requires_crss_data: reads the optional ref/CRSS_DB bundle")


def pytest_collection_modifyitems(items):
    for item in items:
        if Path(item.path).parent != Path(__file__).parent:
            continue
        module = Path(item.path).stem
        needs_data = bool(_CRSS_FIXTURES.get(module, set()).intersection(item.fixturenames))
        # Every test in this module calls _run(), whose argv always has --real.
        needs_data |= module == "test_llm_journal_resume"
        needs_data |= item.originalname in _CRSS_TESTS.get(module, set())
        if needs_data:
            item.add_marker(pytest.mark.requires_crss_data)
        if item.get_closest_marker("requires_crss_data") and not _DATA_AVAILABLE:
            item.add_marker(pytest.mark.skip(reason=
                "Optional CRSS reference data is absent: obtain ref/CRSS_DB/CRSS_DB/ "
                "from the authors (see DATA.md); synthetic tests still run."))
