"""
Unit tests for CognitiveConstraints (Task-050E).

Tests the cognitive capacity configuration based on Miller (1956) and Cowan (2001).

Reference:
- Miller, G. A. (1956). The magical number seven, plus or minus two.
  Psychological Review, 63(2), 81-97. DOI: 10.1037/h0043158
- Cowan, N. (2001). The magical number 4 in short-term memory.
  Behavioral and Brain Sciences, 24(1), 87-114. DOI: 10.1017/S0140525X01003922
"""
import pytest

from cognitive_governance.memory.config.cognitive_constraints import (
    CognitiveConstraints,
    MILLER_STANDARD,
    COWAN_CONSERVATIVE,
    EXTENDED_CONTEXT,
    MINIMAL,
)


class TestCognitiveConstraintsDefaults:
    """Test default values based on psychological literature."""

    def test_miller_standard_defaults(self):
        """Verify Miller's Law defaults (7±2)."""
        c = MILLER_STANDARD
        assert c.system1_memory_count == 5, "System 1 should use Cowan's upper bound (4+1)"
        assert c.system2_memory_count == 7, "System 2 should use Miller's median"
        assert c.working_capacity == 10
        assert c.top_k_significant == 2

    def test_default_constructor_matches_miller(self):
        """Default constructor should match MILLER_STANDARD."""
        c = CognitiveConstraints()
        assert c.system1_memory_count == MILLER_STANDARD.system1_memory_count
        assert c.system2_memory_count == MILLER_STANDARD.system2_memory_count

    def test_cowan_conservative_profile(self):
        """Verify Cowan's conservative profile (4±1)."""
        c = COWAN_CONSERVATIVE
        assert c.system1_memory_count == 3, "Should be Cowan's lower bound"
        assert c.system2_memory_count == 5, "Should be Cowan's upper bound"
        assert c.working_capacity == 7

    def test_extended_context_profile(self):
        """Verify extended context for complex reasoning."""
        c = EXTENDED_CONTEXT
        assert c.system1_memory_count == 7, "Miller's median for S1"
        assert c.system2_memory_count == 9, "Miller's upper bound for S2"
        assert c.working_capacity == 15

    def test_minimal_profile(self):
        """Verify minimal profile for fast inference."""
        c = MINIMAL
        assert c.system1_memory_count == 3
        assert c.system2_memory_count == 4
        assert c.working_capacity == 5


class TestCognitiveConstraintsDynamicMemoryCount:
    """Test arousal-based memory count interpolation."""

    def test_low_arousal_uses_system1(self):
        """Low arousal (< threshold/2) should use System 1 count."""
        c = CognitiveConstraints()
        # With default threshold=0.5, arousal < 0.25 is pure S1
        assert c.get_memory_count(arousal=0.0) == 5
        assert c.get_memory_count(arousal=0.1) == 5
        assert c.get_memory_count(arousal=0.24) == 5

    def test_high_arousal_uses_system2(self):
        """High arousal (>= threshold) should use System 2 count."""
        c = CognitiveConstraints()
        # With default threshold=0.5, arousal >= 0.5 is pure S2
        assert c.get_memory_count(arousal=0.5) == 7
        assert c.get_memory_count(arousal=0.8) == 7
        assert c.get_memory_count(arousal=1.0) == 7

    def test_mid_arousal_interpolates(self):
        """Mid arousal (threshold/2 to threshold) should interpolate."""
        c = CognitiveConstraints()
        # With default threshold=0.5, range 0.25-0.5 interpolates
        mid = c.get_memory_count(arousal=0.375)  # Midpoint of transition
        assert 5 <= mid <= 7, f"Expected 5-7, got {mid}"

    def test_custom_threshold(self):
        """Test with custom arousal threshold."""
        c = CognitiveConstraints()
        # With threshold=0.8, arousal < 0.4 is pure S1
        assert c.get_memory_count(arousal=0.3, threshold=0.8) == 5
        # With threshold=0.8, arousal >= 0.8 is pure S2
        assert c.get_memory_count(arousal=0.8, threshold=0.8) == 7

    def test_interpolation_is_monotonic(self):
        """Memory count should increase monotonically with arousal."""
        c = CognitiveConstraints()
        counts = [c.get_memory_count(arousal=a/10) for a in range(11)]
        for i in range(len(counts) - 1):
            assert counts[i] <= counts[i + 1], f"Non-monotonic at {i}"


class TestCognitiveConstraintsTotalContext:
    """Test total context size calculations."""

    def test_system1_total_context(self):
        """System 1 total = recent + significant = 5 + 2 = 7 (Miller's median)."""
        c = CognitiveConstraints()
        total = c.get_total_context_size(arousal=0.0)
        assert total == 7, "S1: 5 recent + 2 significant = 7"

    def test_system2_total_context(self):
        """System 2 total = recent + significant = 7 + 2 = 9 (Miller's upper)."""
        c = CognitiveConstraints()
        total = c.get_total_context_size(arousal=1.0)
        assert total == 9, "S2: 7 recent + 2 significant = 9"


class TestCognitiveConstraintsUserConfig:
    """Test user-defined custom configurations."""

    def test_custom_system1_count(self):
        """User can set custom System 1 count."""
        c = CognitiveConstraints(system1_memory_count=4)
        assert c.system1_memory_count == 4
        assert c.get_memory_count(arousal=0.0) == 4

    def test_custom_system2_count(self):
        """User can set custom System 2 count."""
        c = CognitiveConstraints(system2_memory_count=9)
        assert c.system2_memory_count == 9
        assert c.get_memory_count(arousal=1.0) == 9

    def test_custom_top_k_significant(self):
        """User can set custom significant memory count."""
        c = CognitiveConstraints(top_k_significant=3)
        assert c.top_k_significant == 3
        total = c.get_total_context_size(arousal=0.0)
        assert total == 8, "5 recent + 3 significant = 8"

    def test_fully_custom_config(self):
        """User can fully customize all parameters."""
        c = CognitiveConstraints(
            system1_memory_count=4,
            system2_memory_count=10,
            working_capacity=20,
            top_k_significant=5,
        )
        assert c.system1_memory_count == 4
        assert c.system2_memory_count == 10
        assert c.working_capacity == 20
        assert c.top_k_significant == 5


class TestCognitiveConstraintsValidation:
    """Test validation of constraints."""

    def test_valid_constraints(self):
        """Valid constraints should pass validation."""
        c = CognitiveConstraints()
        assert c.validate() is True

    def test_invalid_system1_count(self):
        """System 1 count < 1 should fail."""
        c = CognitiveConstraints(system1_memory_count=0)
        with pytest.raises(ValueError, match="system1_memory_count must be >= 1"):
            c.validate()

    def test_invalid_system2_less_than_system1(self):
        """System 2 count < System 1 count should fail."""
        c = CognitiveConstraints(system1_memory_count=5, system2_memory_count=3)
        with pytest.raises(ValueError, match="system2_memory_count must be >= system1_memory_count"):
            c.validate()

    def test_invalid_working_capacity(self):
        """Working capacity < System 2 count should fail."""
        c = CognitiveConstraints(system2_memory_count=7, working_capacity=5)
        with pytest.raises(ValueError, match="working_capacity must be >= system2_memory_count"):
            c.validate()

    def test_invalid_negative_top_k(self):
        """Negative top_k_significant should fail."""
        c = CognitiveConstraints(top_k_significant=-1)
        with pytest.raises(ValueError, match="top_k_significant must be >= 0"):
            c.validate()


class TestCognitiveConstraintsReferences:
    """Test literature reference metadata."""

    def test_references_present(self):
        """Default should have Miller and Cowan references."""
        c = CognitiveConstraints()
        assert len(c.references) == 2
        assert any("Miller" in ref for ref in c.references)
        assert any("Cowan" in ref for ref in c.references)

    def test_doi_constants(self):
        """DOI constants should be set."""
        c = CognitiveConstraints()
        assert c.MILLER_1956_DOI == "10.1037/h0043158"
        assert c.COWAN_2001_DOI == "10.1017/S0140525X01003922"


class TestAdaptiveRetrievalEngineIntegration:
    """Test integration with AdaptiveRetrievalEngine."""

    def test_engine_accepts_cognitive_constraints(self):
        """AdaptiveRetrievalEngine should accept cognitive_constraints."""
        from cognitive_governance.memory.retrieval import AdaptiveRetrievalEngine

        constraints = CognitiveConstraints(
            system1_memory_count=4,
            system2_memory_count=8,
        )
        engine = AdaptiveRetrievalEngine(cognitive_constraints=constraints)
        assert engine.constraints.system1_memory_count == 4
        assert engine.constraints.system2_memory_count == 8

    def test_engine_uses_miller_standard_by_default(self):
        """AdaptiveRetrievalEngine should use MILLER_STANDARD by default."""
        from cognitive_governance.memory.retrieval import AdaptiveRetrievalEngine

        engine = AdaptiveRetrievalEngine()
        assert engine.constraints.system1_memory_count == MILLER_STANDARD.system1_memory_count
        assert engine.constraints.system2_memory_count == MILLER_STANDARD.system2_memory_count


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
