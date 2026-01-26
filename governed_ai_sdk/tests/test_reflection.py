"""
Tests for Task-034 Phase 10: Reflection System.

Tests reflection insights, templates, and memory integration.
"""

import pytest
from datetime import datetime

from governed_ai_sdk.v1_prototype.reflection import (
    ReflectionInsight,
    ReflectionTrace,
    ReflectionTemplate,
    GenericReflectionTemplate,
    FloodReflectionTemplate,
    FinanceReflectionTemplate,
    EducationReflectionTemplate,
    HealthReflectionTemplate,
    get_reflection_template,
    register_reflection_template,
    REFLECTION_TEMPLATES,
    ReflectionMemoryIntegrator,
    BatchReflectionProcessor,
)


class TestReflectionInsight:
    """Tests for ReflectionInsight dataclass."""

    def test_insight_creation(self):
        """ReflectionInsight can be created with required fields."""
        insight = ReflectionInsight(summary="Test insight")
        assert insight.summary == "Test insight"
        assert insight.importance == 0.8
        assert insight.domain == "generic"
        assert insight.source_memories == []

    def test_insight_with_all_fields(self):
        """ReflectionInsight accepts all optional fields."""
        insight = ReflectionInsight(
            summary="Flood insurance saved me money",
            source_memories=["memory_1", "memory_2"],
            importance=0.95,
            domain="flood",
            tags=["insurance", "savings"],
            confidence=0.9,
            action_implications="Should maintain insurance coverage",
        )
        assert insight.importance == 0.95
        assert insight.domain == "flood"
        assert len(insight.source_memories) == 2
        assert insight.action_implications is not None

    def test_importance_clamping(self):
        """ReflectionInsight clamps importance to [0, 1]."""
        insight_high = ReflectionInsight(summary="Test", importance=1.5)
        assert insight_high.importance == 1.0

        insight_low = ReflectionInsight(summary="Test", importance=-0.5)
        assert insight_low.importance == 0.0

    def test_to_memory_format(self):
        """ReflectionInsight converts to memory format."""
        insight = ReflectionInsight(
            summary="Important lesson learned",
            importance=0.9,
            domain="flood",
            tags=["adaptation"],
        )

        memory_dict = insight.to_memory_format()

        assert "[REFLECTION]" in memory_dict["content"]
        assert memory_dict["importance"] == 0.9
        assert memory_dict["source"] == "reflection"
        assert "reflection" in memory_dict["tags"]
        assert "insight" in memory_dict["tags"]

    def test_to_dict(self):
        """ReflectionInsight converts to full dictionary."""
        insight = ReflectionInsight(summary="Test insight", domain="flood")
        result = insight.to_dict()

        assert result["summary"] == "Test insight"
        assert result["domain"] == "flood"
        assert "created_at" in result

    def test_from_dict(self):
        """ReflectionInsight can be created from dictionary."""
        data = {
            "summary": "Restored insight",
            "importance": 0.85,
            "domain": "finance",
        }
        insight = ReflectionInsight.from_dict(data)

        assert insight.summary == "Restored insight"
        assert insight.importance == 0.85
        assert insight.domain == "finance"


class TestReflectionTrace:
    """Tests for ReflectionTrace dataclass."""

    def test_trace_creation(self):
        """ReflectionTrace can be created."""
        trace = ReflectionTrace(agent_id="agent_001")
        assert trace.agent_id == "agent_001"
        assert trace.template_name == "generic"

    def test_trace_to_dict(self):
        """ReflectionTrace converts to dictionary."""
        insight = ReflectionInsight(summary="Test", importance=0.8)
        trace = ReflectionTrace(
            agent_id="agent_001",
            input_memories=["m1", "m2"],
            insight=insight,
        )

        result = trace.to_dict()

        assert result["agent_id"] == "agent_001"
        assert result["input_memories_count"] == 2
        assert result["insight_importance"] == 0.8


class TestReflectionTemplates:
    """Tests for domain-specific reflection templates."""

    def test_generic_template(self):
        """GenericReflectionTemplate generates valid prompt."""
        template = GenericReflectionTemplate()
        assert template.domain == "generic"

        prompt = template.generate_prompt(
            "agent_001",
            ["Memory 1", "Memory 2"],
            {"period": "2024"}
        )

        assert "agent_001" in prompt
        assert "Memory 1" in prompt

    def test_generic_template_parse(self):
        """GenericReflectionTemplate parses response."""
        template = GenericReflectionTemplate()
        response = "I learned that preparation is key."

        insight = template.parse_response(response, ["m1"], {})

        assert insight.summary == response
        assert insight.domain == "generic"

    def test_flood_template(self):
        """FloodReflectionTemplate generates domain-specific prompt."""
        template = FloodReflectionTemplate()
        assert template.domain == "flood"

        prompt = template.generate_prompt(
            "agent_001",
            ["The flood damaged my basement"],
            {"year": 2024, "flood_occurred": True}
        )

        assert "flood" in prompt.lower()
        assert "adaptation" in prompt.lower()
        assert "A flood occurred" in prompt

    def test_flood_template_focus_areas(self):
        """FloodReflectionTemplate has domain-specific focus areas."""
        template = FloodReflectionTemplate()
        areas = template.get_focus_areas()

        assert "adaptation_effectiveness" in areas
        assert "risk_pattern_recognition" in areas

    def test_flood_template_increased_importance_after_flood(self):
        """FloodReflectionTemplate increases importance after flood event."""
        template = FloodReflectionTemplate()

        insight_with_flood = template.parse_response(
            "Insurance saved me", ["m1"], {"flood_occurred": True}
        )
        insight_without_flood = template.parse_response(
            "Insurance saved me", ["m1"], {"flood_occurred": False}
        )

        assert insight_with_flood.importance > insight_without_flood.importance

    def test_finance_template(self):
        """FinanceReflectionTemplate generates domain-specific prompt."""
        template = FinanceReflectionTemplate()
        assert template.domain == "finance"

        prompt = template.generate_prompt(
            "agent_001",
            ["Built emergency fund"],
            {"period": "Q1 2024", "savings_ratio": 0.3}
        )

        assert "financial" in prompt.lower()
        assert "savings" in prompt.lower()

    def test_education_template(self):
        """EducationReflectionTemplate generates domain-specific prompt."""
        template = EducationReflectionTemplate()
        assert template.domain == "education"

        prompt = template.generate_prompt(
            "agent_001",
            ["Studied harder for midterms"],
            {"semester": "Fall 2024", "gpa": 3.2}
        )

        assert "educational" in prompt.lower() or "study" in prompt.lower()
        assert "GPA" in prompt

    def test_health_template(self):
        """HealthReflectionTemplate generates domain-specific prompt."""
        template = HealthReflectionTemplate()
        assert template.domain == "health"

        prompt = template.generate_prompt(
            "agent_001",
            ["Started exercising regularly"],
            {"stage_of_change": "action"}
        )

        assert "health" in prompt.lower()
        assert "behavior" in prompt.lower() or "stage" in prompt.lower()


class TestTemplateRegistry:
    """Tests for template registry functions."""

    def test_get_reflection_template_flood(self):
        """get_reflection_template returns FloodReflectionTemplate."""
        template = get_reflection_template("flood")
        assert isinstance(template, FloodReflectionTemplate)

    def test_get_reflection_template_finance(self):
        """get_reflection_template returns FinanceReflectionTemplate."""
        template = get_reflection_template("finance")
        assert isinstance(template, FinanceReflectionTemplate)

    def test_get_reflection_template_education(self):
        """get_reflection_template returns EducationReflectionTemplate."""
        template = get_reflection_template("education")
        assert isinstance(template, EducationReflectionTemplate)

    def test_get_reflection_template_health(self):
        """get_reflection_template returns HealthReflectionTemplate."""
        template = get_reflection_template("health")
        assert isinstance(template, HealthReflectionTemplate)

    def test_get_reflection_template_unknown_fallback(self):
        """get_reflection_template returns GenericReflectionTemplate for unknown."""
        template = get_reflection_template("unknown_domain")
        assert isinstance(template, GenericReflectionTemplate)

    def test_get_reflection_template_case_insensitive(self):
        """get_reflection_template is case insensitive."""
        template_upper = get_reflection_template("FLOOD")
        template_lower = get_reflection_template("flood")
        assert type(template_upper) == type(template_lower)

    def test_register_custom_template(self):
        """register_reflection_template adds custom template."""
        class CustomTemplate(ReflectionTemplate):
            @property
            def domain(self) -> str:
                return "custom"

            def generate_prompt(self, agent_id, memories, context):
                return "Custom prompt"

            def parse_response(self, response, memories, context):
                return ReflectionInsight(summary=response, domain="custom")

        register_reflection_template("custom", CustomTemplate)
        template = get_reflection_template("custom")
        assert isinstance(template, CustomTemplate)

        # Cleanup
        del REFLECTION_TEMPLATES["custom"]


class TestReflectionMemoryIntegrator:
    """Tests for ReflectionMemoryIntegrator."""

    def test_integrator_creation(self):
        """ReflectionMemoryIntegrator can be created."""
        integrator = ReflectionMemoryIntegrator(domain="flood")
        assert integrator.domain == "flood"
        assert integrator.auto_promote is True

    def test_process_reflection(self):
        """ReflectionMemoryIntegrator processes reflection."""
        integrator = ReflectionMemoryIntegrator(domain="flood", auto_promote=False)

        insight = integrator.process_reflection(
            "agent_001",
            "Flood insurance was worth it",
            ["Memory about flood damage"],
            {"year": 2024}
        )

        assert isinstance(insight, ReflectionInsight)
        assert insight.domain == "flood"

    def test_auto_promote_above_threshold(self):
        """ReflectionMemoryIntegrator auto-promotes high-importance insights."""
        stored_memories = []

        def mock_store(agent_id, memory_dict):
            stored_memories.append((agent_id, memory_dict))

        integrator = ReflectionMemoryIntegrator(
            domain="flood",
            memory_store_fn=mock_store,
            auto_promote=True,
            promotion_threshold=0.5
        )

        # Parse a high-importance response
        insight = integrator.process_reflection(
            "agent_001",
            "Critical lesson about flood damage",
            ["Memory 1"],
            {"flood_occurred": True}  # This increases importance
        )

        assert len(stored_memories) == 1
        assert stored_memories[0][0] == "agent_001"

    def test_no_promote_below_threshold(self):
        """ReflectionMemoryIntegrator doesn't promote below threshold."""
        stored_memories = []

        def mock_store(agent_id, memory_dict):
            stored_memories.append((agent_id, memory_dict))

        integrator = ReflectionMemoryIntegrator(
            domain="generic",
            memory_store_fn=mock_store,
            auto_promote=True,
            promotion_threshold=0.9  # High threshold
        )

        insight = integrator.process_reflection(
            "agent_001",
            "Minor observation",
            ["Memory 1"],
            {}
        )

        # Generic template produces importance 0.75, below 0.9 threshold
        assert len(stored_memories) == 0

    def test_get_traces(self):
        """ReflectionMemoryIntegrator tracks traces."""
        integrator = ReflectionMemoryIntegrator(domain="flood")

        integrator.process_reflection("agent_001", "Response 1", ["m1"], {})
        integrator.process_reflection("agent_002", "Response 2", ["m2"], {})

        all_traces = integrator.get_traces()
        assert len(all_traces) == 2

        agent_1_traces = integrator.get_traces("agent_001")
        assert len(agent_1_traces) == 1

    def test_get_promotion_stats(self):
        """ReflectionMemoryIntegrator provides promotion statistics."""
        integrator = ReflectionMemoryIntegrator(
            domain="flood",
            promotion_threshold=0.5
        )

        integrator.process_reflection("agent_001", "Response", ["m1"], {"flood_occurred": True})

        stats = integrator.get_promotion_stats()

        assert "total_reflections" in stats
        assert "promoted_count" in stats
        assert "promotion_rate" in stats
        assert stats["total_reflections"] == 1


class TestBatchReflectionProcessor:
    """Tests for BatchReflectionProcessor."""

    def test_batch_processor_creation(self):
        """BatchReflectionProcessor can be created."""
        processor = BatchReflectionProcessor(domain="flood")
        assert processor.integrator.domain == "flood"

    def test_process_batch(self):
        """BatchReflectionProcessor processes multiple agents."""
        processor = BatchReflectionProcessor(domain="generic")

        def mock_llm(prompt):
            return "I learned something important."

        agents_data = [
            {"agent_id": "agent_001", "memories": ["m1"], "context": {}},
            {"agent_id": "agent_002", "memories": ["m2"], "context": {}},
        ]

        results = processor.process_batch(agents_data, mock_llm)

        assert len(results) == 2
        assert "agent_001" in results
        assert "agent_002" in results
        assert all(isinstance(v, ReflectionInsight) for v in results.values())

    def test_get_summary(self):
        """BatchReflectionProcessor provides summary statistics."""
        processor = BatchReflectionProcessor(domain="flood")
        summary = processor.get_summary()

        assert "total_reflections" in summary
        assert "promotion_threshold" in summary
