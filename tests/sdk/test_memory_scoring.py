"""
Tests for Task-034 Phase 9: Memory Scoring System.

Tests domain-aware memory scoring for flood, finance, education, and health domains.
"""

import pytest
from cognitive_governance.v1_prototype.memory.scoring import (
    MemoryScore,
    MemoryScorer,
    GenericMemoryScorer,
    FloodMemoryScorer,
    FinanceMemoryScorer,
    EducationMemoryScorer,
    HealthMemoryScorer,
    get_memory_scorer,
    register_memory_scorer,
    MEMORY_SCORERS,
)


class TestMemoryScore:
    """Tests for MemoryScore dataclass."""

    def test_memory_score_creation(self):
        """MemoryScore can be created with required fields."""
        score = MemoryScore(total=0.75)
        assert score.total == 0.75
        assert score.components == {}
        assert score.explanation == ""
        assert score.rank is None

    def test_memory_score_with_components(self):
        """MemoryScore stores component breakdown."""
        score = MemoryScore(
            total=0.8,
            components={"recency": 0.5, "importance": 0.3},
            explanation="Test explanation"
        )
        assert score.components["recency"] == 0.5
        assert score.components["importance"] == 0.3
        assert score.explanation == "Test explanation"

    def test_memory_score_clamping(self):
        """MemoryScore clamps total to [0, 1]."""
        score_high = MemoryScore(total=1.5)
        assert score_high.total == 1.0

        score_low = MemoryScore(total=-0.5)
        assert score_low.total == 0.0


class TestGenericMemoryScorer:
    """Tests for GenericMemoryScorer."""

    def test_domain_property(self):
        """GenericMemoryScorer has correct domain."""
        scorer = GenericMemoryScorer()
        assert scorer.domain == "generic"

    def test_score_basic_memory(self):
        """GenericMemoryScorer scores basic memory."""
        scorer = GenericMemoryScorer()
        memory = {"content": "Test memory", "recency_score": 0.8, "importance": 0.6}
        context = {}
        agent_state = {}

        score = scorer.score(memory, context, agent_state)

        assert isinstance(score, MemoryScore)
        assert 0 <= score.total <= 1
        assert "recency" in score.components
        assert "importance" in score.components

    def test_score_batch(self):
        """GenericMemoryScorer can score multiple memories."""
        scorer = GenericMemoryScorer()
        memories = [
            {"content": "Memory 1", "importance": 0.9},
            {"content": "Memory 2", "importance": 0.5},
            {"content": "Memory 3", "importance": 0.7},
        ]

        scores = scorer.score_batch(memories, {}, {})

        assert len(scores) == 3
        # Should be sorted by total score descending
        assert scores[0].total >= scores[1].total >= scores[2].total
        # Should have ranks assigned
        assert scores[0].rank == 1
        assert scores[1].rank == 2
        assert scores[2].rank == 3


class TestFloodMemoryScorer:
    """Tests for FloodMemoryScorer."""

    def test_domain_property(self):
        """FloodMemoryScorer has correct domain."""
        scorer = FloodMemoryScorer()
        assert scorer.domain == "flood"

    def test_keyword_boosting(self):
        """FloodMemoryScorer boosts flood-related keywords."""
        scorer = FloodMemoryScorer()

        memory_with_keywords = {
            "content": "The flood damaged my house and I had to evacuate",
            "importance": 0.5
        }
        memory_without_keywords = {
            "content": "I went shopping yesterday",
            "importance": 0.5
        }

        score_with = scorer.score(memory_with_keywords, {}, {})
        score_without = scorer.score(memory_without_keywords, {}, {})

        assert score_with.total > score_without.total
        assert score_with.components["keyword_relevance"] > 0

    def test_trauma_boost(self):
        """FloodMemoryScorer applies trauma boost for flood-experienced agents."""
        scorer = FloodMemoryScorer()
        memory = {"content": "The flood was terrible", "importance": 0.5}

        score_trauma = scorer.score(memory, {}, {"flood_experience": True})
        score_no_trauma = scorer.score(memory, {}, {"flood_experience": False})

        assert score_trauma.components["trauma_boost"] > 0
        assert score_no_trauma.components["trauma_boost"] == 0
        assert score_trauma.total > score_no_trauma.total

    def test_crisis_boost(self):
        """FloodMemoryScorer applies crisis boost during active flood."""
        scorer = FloodMemoryScorer()
        memory = {"content": "Remember the evacuation route", "importance": 0.5}

        score_crisis = scorer.score(memory, {"flood_active": True}, {})
        score_normal = scorer.score(memory, {"flood_active": False}, {})

        assert score_crisis.components["crisis_boost"] > 0
        assert score_normal.components["crisis_boost"] == 0


class TestFinanceMemoryScorer:
    """Tests for FinanceMemoryScorer."""

    def test_domain_property(self):
        """FinanceMemoryScorer has correct domain."""
        scorer = FinanceMemoryScorer()
        assert scorer.domain == "finance"

    def test_keyword_boosting(self):
        """FinanceMemoryScorer boosts finance-related keywords."""
        scorer = FinanceMemoryScorer()

        memory_with_keywords = {
            "content": "My savings account helped during the debt crisis",
            "importance": 0.5
        }
        memory_without_keywords = {
            "content": "I went hiking yesterday",
            "importance": 0.5
        }

        score_with = scorer.score(memory_with_keywords, {}, {})
        score_without = scorer.score(memory_without_keywords, {}, {})

        assert score_with.total > score_without.total

    def test_financial_stress_boost(self):
        """FinanceMemoryScorer applies stress boost for high debt."""
        scorer = FinanceMemoryScorer()
        memory = {"content": "Budget planning is important", "importance": 0.5}

        score_stressed = scorer.score(memory, {}, {"debt_ratio": 0.5})
        score_stable = scorer.score(memory, {}, {"debt_ratio": 0.2})

        assert score_stressed.components["stress_boost"] > 0
        assert score_stable.components["stress_boost"] == 0


class TestEducationMemoryScorer:
    """Tests for EducationMemoryScorer."""

    def test_domain_property(self):
        """EducationMemoryScorer has correct domain."""
        scorer = EducationMemoryScorer()
        assert scorer.domain == "education"

    def test_keyword_boosting(self):
        """EducationMemoryScorer boosts education-related keywords."""
        scorer = EducationMemoryScorer()

        memory_with_keywords = {
            "content": "I need to study for my exam to improve my grade",
            "importance": 0.5
        }
        score = scorer.score(memory_with_keywords, {}, {})

        assert score.components["keyword_relevance"] > 0

    def test_motivation_boost_low_gpa(self):
        """EducationMemoryScorer applies motivation boost for struggling students."""
        scorer = EducationMemoryScorer()
        memory = {"content": "Study harder next semester", "importance": 0.5}

        score_low_gpa = scorer.score(memory, {}, {"gpa": 1.5})
        score_mid_gpa = scorer.score(memory, {}, {"gpa": 2.5})

        assert score_low_gpa.components["motivation_boost"] > 0
        assert score_mid_gpa.components["motivation_boost"] == 0


class TestHealthMemoryScorer:
    """Tests for HealthMemoryScorer."""

    def test_domain_property(self):
        """HealthMemoryScorer has correct domain."""
        scorer = HealthMemoryScorer()
        assert scorer.domain == "health"

    def test_keyword_boosting(self):
        """HealthMemoryScorer boosts health-related keywords."""
        scorer = HealthMemoryScorer()

        memory_with_keywords = {
            "content": "I started exercising and improved my diet",
            "importance": 0.5
        }
        score = scorer.score(memory_with_keywords, {}, {})

        assert score.components["keyword_relevance"] > 0

    def test_readiness_boost(self):
        """HealthMemoryScorer applies readiness boost based on change stage."""
        scorer = HealthMemoryScorer()
        memory = {"content": "Start a new fitness routine", "importance": 0.5}

        score_action = scorer.score(memory, {}, {"stage_of_change": "action"})
        score_precontemplation = scorer.score(memory, {}, {"stage_of_change": "precontemplation"})

        assert score_action.components["readiness_boost"] > 0
        assert score_precontemplation.components["readiness_boost"] == 0


class TestScorerRegistry:
    """Tests for scorer registry functions."""

    def test_get_memory_scorer_flood(self):
        """get_memory_scorer returns FloodMemoryScorer for 'flood'."""
        scorer = get_memory_scorer("flood")
        assert isinstance(scorer, FloodMemoryScorer)
        assert scorer.domain == "flood"

    def test_get_memory_scorer_finance(self):
        """get_memory_scorer returns FinanceMemoryScorer for 'finance'."""
        scorer = get_memory_scorer("finance")
        assert isinstance(scorer, FinanceMemoryScorer)

    def test_get_memory_scorer_education(self):
        """get_memory_scorer returns EducationMemoryScorer for 'education'."""
        scorer = get_memory_scorer("education")
        assert isinstance(scorer, EducationMemoryScorer)

    def test_get_memory_scorer_health(self):
        """get_memory_scorer returns HealthMemoryScorer for 'health'."""
        scorer = get_memory_scorer("health")
        assert isinstance(scorer, HealthMemoryScorer)

    def test_get_memory_scorer_unknown_fallback(self):
        """get_memory_scorer returns GenericMemoryScorer for unknown domain."""
        scorer = get_memory_scorer("unknown_domain")
        assert isinstance(scorer, GenericMemoryScorer)

    def test_get_memory_scorer_case_insensitive(self):
        """get_memory_scorer is case insensitive."""
        scorer_upper = get_memory_scorer("FLOOD")
        scorer_lower = get_memory_scorer("flood")
        assert type(scorer_upper) == type(scorer_lower)

    def test_register_custom_scorer(self):
        """register_memory_scorer adds custom scorer to registry."""
        class CustomScorer(MemoryScorer):
            @property
            def domain(self) -> str:
                return "custom"

            def score(self, memory, context, agent_state):
                return MemoryScore(total=1.0, explanation="Custom scorer")

        register_memory_scorer("custom", CustomScorer)
        scorer = get_memory_scorer("custom")
        assert isinstance(scorer, CustomScorer)

        # Cleanup
        del MEMORY_SCORERS["custom"]

    def test_register_invalid_scorer_raises(self):
        """register_memory_scorer raises TypeError for non-MemoryScorer class."""
        class NotAScorer:
            pass

        with pytest.raises(TypeError):
            register_memory_scorer("invalid", NotAScorer)
