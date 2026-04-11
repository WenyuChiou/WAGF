"""Verify FLOOD_CATEGORY_TO_CONTENT_TYPE integrity."""

import pytest

from broker.components.memory.content_types import MemoryContentType
from examples.multi_agent.flood.memory.content_type_mapping import FLOOD_CATEGORY_TO_CONTENT_TYPE


def test_mapping_nonempty():
    assert len(FLOOD_CATEGORY_TO_CONTENT_TYPE) > 0


def test_all_values_are_valid_content_types():
    for category, content_type in FLOOD_CATEGORY_TO_CONTENT_TYPE.items():
        assert isinstance(content_type, MemoryContentType), (
            f"{category} maps to {content_type}, which is not a MemoryContentType"
        )


def test_all_keys_are_strings():
    for category in FLOOD_CATEGORY_TO_CONTENT_TYPE:
        assert isinstance(category, str)
        assert len(category) > 0


def test_no_duplicate_category_names():
    keys = list(FLOOD_CATEGORY_TO_CONTENT_TYPE.keys())
    assert len(keys) == len(set(keys))


@pytest.mark.parametrize(
    ("ratchet_category", "expected_type"),
    [
        ("decision_reasoning", MemoryContentType.AGENT_SELF_REPORT),
        ("reflection", MemoryContentType.AGENT_REFLECTION_QUOTE),
        ("place_attachment", MemoryContentType.INITIAL_NARRATIVE),
        ("government_trust", MemoryContentType.INITIAL_NARRATIVE),
        ("adaptation_action", MemoryContentType.INITIAL_NARRATIVE),
        ("government_notice", MemoryContentType.INITIAL_NARRATIVE),
    ],
)
def test_known_ratchet_sources(ratchet_category, expected_type):
    assert FLOOD_CATEGORY_TO_CONTENT_TYPE[ratchet_category] == expected_type


@pytest.mark.parametrize(
    ("safe_category", "expected_type"),
    [
        ("flood_experience", MemoryContentType.EXTERNAL_EVENT),
        ("flood_event", MemoryContentType.EXTERNAL_EVENT),
        ("flood_zone", MemoryContentType.INITIAL_FACTUAL),
        ("insurance_history", MemoryContentType.INITIAL_FACTUAL),
        ("insurance_claim", MemoryContentType.INITIAL_FACTUAL),
        ("social_connections", MemoryContentType.INITIAL_FACTUAL),
        ("social_interaction", MemoryContentType.INITIAL_FACTUAL),
        ("risk_awareness", MemoryContentType.INITIAL_FACTUAL),
        ("policy_decision", MemoryContentType.INSTITUTIONAL_STATE),
        ("social_observation", MemoryContentType.SOCIAL_OBSERVATION),
    ],
)
def test_known_factual_sources(safe_category, expected_type):
    assert FLOOD_CATEGORY_TO_CONTENT_TYPE[safe_category] == expected_type
