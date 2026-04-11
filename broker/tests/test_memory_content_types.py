"""Unit tests for MemoryContentType enum and policy_classifier."""

import pytest

from broker.components.memory.content_types import MemoryContentType
from broker.components.memory.policy_classifier import classify


class TestMemoryContentTypeEnum:
    def test_enum_values_are_snake_case_strings(self):
        for ct in MemoryContentType:
            assert isinstance(ct.value, str)
            assert ct.value == ct.value.lower()
            assert " " not in ct.value

    def test_all_expected_members_exist(self):
        expected = {
            "EXTERNAL_EVENT",
            "AGENT_ACTION",
            "SOCIAL_OBSERVATION",
            "INSTITUTIONAL_STATE",
            "INSTITUTIONAL_REFLECTION",
            "INITIAL_FACTUAL",
            "AGENT_SELF_REPORT",
            "AGENT_REFLECTION_QUOTE",
            "INITIAL_NARRATIVE",
        }
        actual = {ct.name for ct in MemoryContentType}
        assert expected == actual, f"Missing: {expected - actual}, Extra: {actual - expected}"

    def test_string_round_trip(self):
        for ct in MemoryContentType:
            assert MemoryContentType(ct.value) is ct

    def test_enum_is_subclass_of_str(self):
        assert issubclass(MemoryContentType, str)
        assert MemoryContentType.EXTERNAL_EVENT == "external_event"

    def test_enum_values_are_unique(self):
        values = [ct.value for ct in MemoryContentType]
        assert len(values) == len(set(values))


class TestClassifyExplicit:
    def test_explicit_content_type_string(self):
        assert classify({"content_type": "agent_self_report"}) == MemoryContentType.AGENT_SELF_REPORT

    def test_explicit_content_type_enum(self):
        assert classify({"content_type": MemoryContentType.EXTERNAL_EVENT}) == MemoryContentType.EXTERNAL_EVENT

    def test_explicit_content_type_wins_over_category(self):
        md = {"content_type": "institutional_state", "category": "flood_event"}
        assert classify(md) == MemoryContentType.INSTITUTIONAL_STATE

    def test_explicit_content_type_wins_over_type_hint(self):
        md = {"content_type": "initial_factual", "type": "reasoning"}
        assert classify(md) == MemoryContentType.INITIAL_FACTUAL

    def test_invalid_explicit_falls_through_to_category(self):
        md = {"content_type": "bogus", "category": "flood_event"}
        assert classify(md) == MemoryContentType.EXTERNAL_EVENT

    def test_invalid_explicit_falls_through_to_type_hint(self):
        md = {"content_type": "bogus", "type": "reflection"}
        assert classify(md) == MemoryContentType.AGENT_REFLECTION_QUOTE


class TestClassifyCategory:
    @pytest.mark.parametrize(
        ("category", "expected"),
        [
            ("flood_experience", MemoryContentType.EXTERNAL_EVENT),
            ("flood_event", MemoryContentType.EXTERNAL_EVENT),
            ("damage", MemoryContentType.EXTERNAL_EVENT),
            ("insurance_claim", MemoryContentType.INITIAL_FACTUAL),
            ("insurance_history", MemoryContentType.INITIAL_FACTUAL),
            ("social_observation", MemoryContentType.SOCIAL_OBSERVATION),
            ("neighbor_observation", MemoryContentType.SOCIAL_OBSERVATION),
            ("policy_decision", MemoryContentType.INSTITUTIONAL_STATE),
            ("institutional_event", MemoryContentType.INSTITUTIONAL_STATE),
        ],
    )
    def test_default_rules(self, category, expected):
        assert classify({"category": category}) == expected

    def test_domain_mapping_overrides_default(self):
        domain = {"flood_event": MemoryContentType.AGENT_SELF_REPORT}
        assert classify({"category": "flood_event"}, domain_mapping=domain) == MemoryContentType.AGENT_SELF_REPORT

    def test_domain_mapping_handles_non_default_categories(self):
        domain = {"bespoke": MemoryContentType.INSTITUTIONAL_REFLECTION}
        assert classify({"category": "bespoke"}, domain_mapping=domain) == MemoryContentType.INSTITUTIONAL_REFLECTION

    def test_unknown_category_falls_through(self):
        assert classify({"category": "unknown"}) == MemoryContentType.EXTERNAL_EVENT


class TestClassifyTypeHeuristic:
    def test_type_reasoning(self):
        assert classify({"type": "reasoning"}) == MemoryContentType.AGENT_SELF_REPORT

    def test_type_self_report(self):
        assert classify({"type": "self_report"}) == MemoryContentType.AGENT_SELF_REPORT

    def test_type_reflection(self):
        assert classify({"type": "reflection"}) == MemoryContentType.AGENT_REFLECTION_QUOTE

    def test_type_event(self):
        assert classify({"type": "event"}) == MemoryContentType.EXTERNAL_EVENT

    def test_type_action(self):
        assert classify({"type": "action"}) == MemoryContentType.AGENT_ACTION

    def test_unknown_type_falls_back(self):
        assert classify({"type": "mystery"}) == MemoryContentType.EXTERNAL_EVENT


class TestClassifyFallback:
    def test_empty_metadata(self):
        assert classify({}) == MemoryContentType.EXTERNAL_EVENT

    def test_none_metadata(self):
        assert classify(None) == MemoryContentType.EXTERNAL_EVENT

    def test_unknown_category_and_type(self):
        md = {"category": "unknown_thing", "type": "mystery"}
        assert classify(md) == MemoryContentType.EXTERNAL_EVENT

    def test_safe_fallback_is_external_event_not_self_report(self):
        assert classify({}) != MemoryContentType.AGENT_SELF_REPORT
        assert classify({}) == MemoryContentType.EXTERNAL_EVENT

    def test_domain_mapping_takes_priority_over_type_hint(self):
        domain = {"reflection": MemoryContentType.INITIAL_NARRATIVE}
        md = {"category": "reflection", "type": "reflection"}
        assert classify(md, domain_mapping=domain) == MemoryContentType.INITIAL_NARRATIVE
