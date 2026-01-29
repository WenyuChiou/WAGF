"""
Tests for context_types module.

Tests UniversalContext, MemoryContext, PromptVariables, and their integration
with UnifiedContextBuilder.

Part of Task-041: Universal Prompt/Context/Governance Framework
"""
import pytest
from typing import Dict, Any, List

from broker.interfaces.context_types import (
    PsychologicalFrameworkType,
    MemoryContext,
    ConstructAppraisal,
    UniversalContext,
    PromptVariables,
)


# =============================================================================
# MemoryContext Tests
# =============================================================================

class TestMemoryContext:
    """Tests for MemoryContext dataclass."""

    def test_empty_memory_context(self):
        """Test creating an empty MemoryContext."""
        ctx = MemoryContext()
        assert ctx.core == {}
        assert ctx.episodic == []
        assert ctx.semantic == []
        assert ctx.retrieval_info == {}

    def test_memory_context_with_data(self):
        """Test MemoryContext with populated data."""
        ctx = MemoryContext(
            core={"elevated": True, "savings": 50000},
            episodic=["Last year I bought insurance", "Flood damaged my property"],
            semantic=["Flooding is common in this area"],
            retrieval_info={"source": "test", "count": 3},
        )
        assert ctx.core["elevated"] is True
        assert len(ctx.episodic) == 2
        assert len(ctx.semantic) == 1

    def test_format_for_prompt_structured(self):
        """Test structured format for prompt."""
        ctx = MemoryContext(
            core={"elevated": True, "insured": False},
            semantic=["Historical flood patterns show increasing frequency"],
            episodic=["Year 5: Major flood event caused $20,000 damage"],
        )
        formatted = ctx.format_for_prompt(style="structured")

        assert "CORE STATE:" in formatted
        assert "elevated=True" in formatted
        assert "HISTORICAL KNOWLEDGE:" in formatted
        assert "RECENT EVENTS:" in formatted

    def test_format_for_prompt_flat(self):
        """Test flat format for prompt (legacy)."""
        ctx = MemoryContext(
            semantic=["Memory 1"],
            episodic=["Memory 2", "Memory 3"],
        )
        formatted = ctx.format_for_prompt(style="flat")

        assert "- Memory 1" in formatted
        assert "- Memory 2" in formatted
        assert "- Memory 3" in formatted

    def test_format_empty_memory(self):
        """Test formatting empty memory."""
        ctx = MemoryContext()
        formatted = ctx.format_for_prompt()
        assert formatted == "No memory available"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        ctx = MemoryContext(
            core={"key": "value"},
            episodic=["event1"],
            semantic=["knowledge1"],
            retrieval_info={"count": 2},
        )
        d = ctx.to_dict()

        assert d["core"] == {"key": "value"}
        assert d["episodic"] == ["event1"]
        assert d["semantic"] == ["knowledge1"]
        assert d["retrieval_info"] == {"count": 2}

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "core": {"elevated": True},
            "episodic": ["event1", "event2"],
            "semantic": [],
            "retrieval_info": {},
        }
        ctx = MemoryContext.from_dict(data)

        assert ctx.core["elevated"] is True
        assert len(ctx.episodic) == 2

    def test_from_legacy_list(self):
        """Test creation from legacy memory list."""
        memories = ["Memory 1", "Memory 2", "Memory 3"]
        core_state = {"elevated": False}

        ctx = MemoryContext.from_legacy_list(memories, core_state)

        assert ctx.core == core_state
        assert ctx.episodic == memories
        assert ctx.retrieval_info["source"] == "legacy_list"


# =============================================================================
# ConstructAppraisal Tests
# =============================================================================

class TestConstructAppraisal:
    """Tests for ConstructAppraisal dataclass."""

    def test_basic_appraisal(self):
        """Test basic appraisal creation."""
        appraisal = ConstructAppraisal(
            construct_key="TP_LABEL",
            label="H",
            reason="Recent flood experience",
        )
        assert appraisal.construct_key == "TP_LABEL"
        assert appraisal.label == "H"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        appraisal = ConstructAppraisal(
            construct_key="CP_LABEL",
            label="VH",
            reason="High self-efficacy",
        )
        d = appraisal.to_dict()

        assert d["construct_key"] == "CP_LABEL"
        assert d["label"] == "VH"
        assert d["reason"] == "High self-efficacy"


# =============================================================================
# UniversalContext Tests
# =============================================================================

class TestUniversalContext:
    """Tests for UniversalContext dataclass."""

    def test_minimal_context(self):
        """Test creating minimal UniversalContext."""
        ctx = UniversalContext(agent_id="agent_001")

        assert ctx.agent_id == "agent_001"
        assert ctx.agent_type == "default"
        assert ctx.framework == PsychologicalFrameworkType.PMT

    def test_full_context(self):
        """Test creating fully populated context."""
        memory = MemoryContext(
            core={"elevated": True},
            episodic=["Event 1"],
        )

        ctx = UniversalContext(
            agent_id="household_001",
            agent_type="household",
            agent_name="John Smith",
            framework=PsychologicalFrameworkType.PMT,
            constructs={"TP_LABEL": {"values": ["VL", "L", "M", "H", "VH"]}},
            state={"income": 75000, "savings": 50000},
            personal={"narrative": "I am a homeowner in a flood-prone area"},
            local={"spatial": "Zone A", "social": ["Neighbor 1"]},
            institutional={"policy_rate": 0.3},
            global_context=["Year 5 flood event"],
            memory=memory,
            available_skills=["buy_insurance", "elevate_house", "do_nothing"],
            eligible_skills=["buy_insurance", "elevate_house", "do_nothing"],
            year=5,
        )

        assert ctx.agent_id == "household_001"
        assert ctx.agent_name == "John Smith"
        assert ctx.framework == PsychologicalFrameworkType.PMT
        assert ctx.year == 5
        assert len(ctx.available_skills) == 3

    def test_get_framework_name(self):
        """Test getting framework name as string."""
        ctx = UniversalContext(
            agent_id="gov_001",
            framework=PsychologicalFrameworkType.UTILITY,
        )
        assert ctx.get_framework_name() == "utility"

    def test_get_personal_summary(self):
        """Test personal context summary."""
        ctx = UniversalContext(
            agent_id="agent_001",
            personal={
                "income": 75000,
                "elevated": True,
                "narrative": "Test narrative",  # Should be excluded
            },
        )
        summary = ctx.get_personal_summary()

        assert "income: 75000" in summary
        assert "elevated: True" in summary
        assert "narrative" not in summary  # Excluded from summary

    def test_get_local_summary(self):
        """Test local context summary."""
        ctx = UniversalContext(
            agent_id="agent_001",
            local={
                "spatial": "Zone A, Tract 12",
                "social": ["Neighbor 1", "Neighbor 2"],
                "visible_actions": ["elevate_house", "buy_insurance"],
            },
        )
        summary = ctx.get_local_summary()

        assert "Location: Zone A" in summary
        assert "Social: 2 interactions" in summary
        assert "Observed: 2 actions" in summary

    def test_to_dict(self):
        """Test conversion to dictionary."""
        ctx = UniversalContext(
            agent_id="agent_001",
            agent_type="household",
            year=5,
            retry_attempt=1,
        )
        d = ctx.to_dict()

        assert d["agent_id"] == "agent_001"
        assert d["agent_type"] == "household"
        assert d["year"] == 5
        assert d["retry_attempt"] == 1

    def test_from_dict_basic(self):
        """Test creation from dictionary."""
        data = {
            "agent_id": "agent_001",
            "agent_type": "household",
            "framework": "pmt",
            "year": 5,
        }
        ctx = UniversalContext.from_dict(data)

        assert ctx.agent_id == "agent_001"
        assert ctx.agent_type == "household"
        assert ctx.framework == PsychologicalFrameworkType.PMT
        assert ctx.year == 5

    def test_from_dict_with_legacy_memory(self):
        """Test from_dict with legacy memory list."""
        data = {
            "agent_id": "agent_001",
            "memory": ["Memory 1", "Memory 2"],  # Legacy format
        }
        ctx = UniversalContext.from_dict(data)

        assert isinstance(ctx.memory, MemoryContext)
        assert len(ctx.memory.episodic) == 2

    def test_from_dict_with_structured_memory(self):
        """Test from_dict with structured memory."""
        data = {
            "agent_id": "agent_001",
            "memory": {
                "core": {"elevated": True},
                "episodic": ["Event 1"],
                "semantic": ["Knowledge 1"],
            },
        }
        ctx = UniversalContext.from_dict(data)

        assert ctx.memory.core["elevated"] is True
        assert len(ctx.memory.episodic) == 1

    def test_with_retry_context(self):
        """Test creating context with retry information."""
        ctx = UniversalContext(agent_id="agent_001", retry_attempt=0)
        retry_ctx = ctx.with_retry_context(attempt=2)

        assert retry_ctx.retry_attempt == 2
        assert ctx.retry_attempt == 0  # Original unchanged

    def test_framework_types(self):
        """Test all framework types."""
        for fw in PsychologicalFrameworkType:
            ctx = UniversalContext(agent_id="test", framework=fw)
            assert ctx.framework == fw
            assert ctx.get_framework_name() == fw.value


# =============================================================================
# PromptVariables Tests
# =============================================================================

class TestPromptVariables:
    """Tests for PromptVariables dataclass."""

    def test_empty_variables(self):
        """Test creating empty PromptVariables."""
        pv = PromptVariables()

        assert pv.narrative_persona == ""
        assert pv.memory_text == ""
        assert pv.options_text == ""

    def test_to_dict(self):
        """Test conversion to dictionary for template rendering."""
        pv = PromptVariables(
            narrative_persona="You are a homeowner...",
            memory_text="Last year flood damage...",
            options_text="1. Buy insurance\n2. Do nothing",
            rating_scale="VL/L/M/H/VH",
            year="5",
        )
        d = pv.to_dict()

        # Check main keys
        assert d["narrative_persona"] == "You are a homeowner..."
        assert d["memory_text"] == "Last year flood damage..."
        assert d["options_text"] == "1. Buy insurance\n2. Do nothing"

        # Check aliases
        assert d["memory"] == d["memory_text"]
        assert d["options"] == d["options_text"]

    def test_to_dict_with_extra(self):
        """Test extra variables are merged."""
        pv = PromptVariables(
            narrative_persona="Test",
            extra={"custom_var": "custom_value", "another": 123},
        )
        d = pv.to_dict()

        assert d["custom_var"] == "custom_value"
        assert d["another"] == 123

    def test_from_universal_context(self):
        """Test creation from UniversalContext."""
        memory = MemoryContext(
            core={"elevated": True},
            episodic=["Flood damage last year"],
        )
        ctx = UniversalContext(
            agent_id="agent_001",
            agent_type="household",
            agent_name="John Smith",
            personal={"narrative": "I am a cautious homeowner."},
            memory=memory,
            options_text="1. Buy insurance\n2. Elevate house",
            valid_choices_text="1 or 2",
            year=5,
        )

        pv = PromptVariables.from_universal_context(
            ctx,
            rating_scale="VL/L/M/H/VH",
            response_format="<<<DECISION_START>>>\n...\n<<<DECISION_END>>>",
        )

        assert pv.narrative_persona == "I am a cautious homeowner."
        assert "elevated=True" in pv.memory_text or "CORE STATE" in pv.memory_text
        assert pv.options_text == "1. Buy insurance\n2. Elevate house"
        assert pv.valid_choices_text == "1 or 2"
        assert pv.rating_scale == "VL/L/M/H/VH"
        assert "<<<DECISION_START>>>" in pv.response_format
        assert pv.year == "5"

    def test_from_universal_context_fallback_narrative(self):
        """Test fallback narrative generation when not provided."""
        ctx = UniversalContext(
            agent_id="gov_001",
            agent_type="government",
            agent_name="City Council",
            personal={},  # No narrative
        )

        pv = PromptVariables.from_universal_context(ctx)

        # Should generate fallback narrative
        assert "City Council" in pv.narrative_persona
        assert "government" in pv.narrative_persona


# =============================================================================
# Integration Tests
# =============================================================================

class TestContextTypesIntegration:
    """Integration tests for context types."""

    def test_full_workflow(self):
        """Test complete context building workflow."""
        # 1. Create memory
        memory = MemoryContext(
            core={"elevated": False, "insured": True, "savings": 45000},
            episodic=[
                "Year 3: Minor flooding, no damage due to insurance",
                "Year 4: Neighbor elevated their house",
            ],
            semantic=["Flood risk is increasing in this area"],
        )

        # 2. Create context
        ctx = UniversalContext(
            agent_id="household_042",
            agent_type="household",
            agent_name="Maria Garcia",
            framework=PsychologicalFrameworkType.PMT,
            constructs={
                "TP_LABEL": {"values": ["VL", "L", "M", "H", "VH"]},
                "CP_LABEL": {"values": ["VL", "L", "M", "H", "VH"]},
            },
            state={"income": 65000, "property_value": 250000},
            personal={"narrative": "I am a single mother with two children."},
            local={
                "spatial": "Zone B, Tract 15",
                "social": ["Neighbor elevated", "Community meeting discussed flood prep"],
            },
            institutional={"subsidy_rate": 0.3, "policy_active": True},
            global_context=["Year 5: Major flood warning issued"],
            memory=memory,
            available_skills=["buy_insurance", "elevate_house", "relocate", "do_nothing"],
            eligible_skills=["elevate_house", "do_nothing"],  # Already insured
            options_text="1. Elevate house ($15,000 with subsidy)\n2. Do nothing",
            valid_choices_text="1 or 2",
            year=5,
        )

        # 3. Generate prompt variables
        pv = PromptVariables.from_universal_context(
            ctx,
            rating_scale="VL = Very Low | L = Low | M = Medium | H = High | VH = Very High",
            response_format='<<<DECISION_START>>>\n{"decision": 1 or 2}\n<<<DECISION_END>>>',
        )

        # 4. Verify workflow
        template_vars = pv.to_dict()

        assert template_vars["narrative_persona"]
        assert template_vars["memory"]
        assert "1. Elevate house" in template_vars["options"]
        assert "<<<DECISION_START>>>" in template_vars["response_format"]
        assert template_vars["year"] == "5"
        assert template_vars["agent_id"] == "household_042"

    def test_context_serialization_roundtrip(self):
        """Test that context survives serialization roundtrip."""
        original = UniversalContext(
            agent_id="test_001",
            agent_type="household",
            framework=PsychologicalFrameworkType.PMT,
            memory=MemoryContext(
                core={"key": "value"},
                episodic=["event1"],
            ),
            year=10,
            retry_attempt=2,
        )

        # Serialize
        d = original.to_dict()

        # Deserialize
        restored = UniversalContext.from_dict(d)

        # Verify
        assert restored.agent_id == original.agent_id
        assert restored.agent_type == original.agent_type
        assert restored.framework == original.framework
        assert restored.memory.core == original.memory.core
        assert restored.year == original.year
        assert restored.retry_attempt == original.retry_attempt


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unknown_framework_defaults_to_generic(self):
        """Test that unknown framework string defaults to generic."""
        ctx = UniversalContext.from_dict({
            "agent_id": "test",
            "framework": "unknown_framework",
        })
        assert ctx.framework == PsychologicalFrameworkType.GENERIC

    def test_missing_fields_have_defaults(self):
        """Test that missing fields use sensible defaults."""
        ctx = UniversalContext.from_dict({"agent_id": "minimal"})

        assert ctx.agent_type == "default"
        assert ctx.state == {}
        assert ctx.personal == {}
        assert ctx.available_skills == []
        assert ctx.retry_attempt == 0
        assert ctx.max_retries == 3

    def test_empty_memory_format(self):
        """Test formatting completely empty memory."""
        memory = MemoryContext()
        assert memory.format_for_prompt() == "No memory available"
        assert memory.format_for_prompt(style="flat") == "No memory available"

    def test_context_with_none_values(self):
        """Test context handles None values gracefully."""
        ctx = UniversalContext(
            agent_id="test",
            year=None,
            agent_type_definition=None,
        )
        d = ctx.to_dict()
        assert d["year"] is None
        assert d["agent_type_definition"] is None
