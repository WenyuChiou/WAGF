"""
Tests for Phase 4 XAI v2: Domain-Aware Feasibility Scoring.

Verifies CategoricalFeasibilityScorer and enhanced CounterfactualEngine.
"""

import pytest
from governed_ai_sdk.v1_prototype.types import (
    PolicyRule,
    CounterFactualResult,
    CounterFactualStrategy,
    CompositeRule,
)
from governed_ai_sdk.v1_prototype.xai.counterfactual import CounterfactualEngine
from governed_ai_sdk.v1_prototype.xai.feasibility import (
    CategoricalFeasibilityScorer,
    TransitionInfo,
    create_default_scorer,
    EDUCATION_FEASIBILITY,
    EDUCATION_RATIONALES,
    FINANCE_FEASIBILITY,
    FLOOD_FEASIBILITY,
    HEALTH_FEASIBILITY,
)


class TestTransitionInfo:
    """Tests for TransitionInfo dataclass."""

    def test_basic_transition(self):
        """TransitionInfo holds transition data."""
        info = TransitionInfo(
            from_value="high_school",
            to_value="bachelors",
            feasibility=0.4,
        )

        assert info.from_value == "high_school"
        assert info.to_value == "bachelors"
        assert info.feasibility == 0.4
        assert info.rationale is None

    def test_with_rationale(self):
        """TransitionInfo with rationale."""
        info = TransitionInfo(
            from_value="bachelors",
            to_value="masters",
            feasibility=0.4,
            rationale="Graduate school admission required",
        )

        assert info.rationale == "Graduate school admission required"


class TestCategoricalFeasibilityScorer:
    """Tests for CategoricalFeasibilityScorer."""

    def test_register_domain(self):
        """Can register domain-specific transitions."""
        scorer = CategoricalFeasibilityScorer()
        transitions = {
            ("A", "B"): 0.7,
            ("B", "C"): 0.5,
        }
        scorer.register_domain("test", transitions)

        assert scorer.score("param", "A", "B", "test") == 0.7
        assert scorer.score("param", "B", "C", "test") == 0.5

    def test_default_score(self):
        """Unknown transitions return default score (0.4)."""
        scorer = CategoricalFeasibilityScorer()

        score = scorer.score("param", "X", "Y", "unknown_domain")

        assert score == 0.4

    def test_same_value_returns_1(self):
        """No change needed returns 1.0."""
        scorer = CategoricalFeasibilityScorer()

        score = scorer.score("param", "A", "A", "any_domain")

        assert score == 1.0

    def test_get_rationale(self):
        """Can retrieve rationale for transitions."""
        scorer = CategoricalFeasibilityScorer()
        scorer.register_domain(
            "edu",
            {("high_school", "bachelors"): 0.4},
            {("high_school", "bachelors"): "4-year degree program"},
        )

        rationale = scorer.get_rationale("high_school", "bachelors", "edu")

        assert rationale == "4-year degree program"

    def test_rank_options(self):
        """rank_options returns sorted by feasibility."""
        scorer = CategoricalFeasibilityScorer()
        scorer.register_domain("test", {
            ("A", "B"): 0.8,
            ("A", "C"): 0.3,
            ("A", "D"): 0.6,
        })

        ranked = scorer.rank_options("param", "A", ["B", "C", "D"], "test")

        assert len(ranked) == 3
        assert ranked[0].to_value == "B"  # Highest feasibility
        assert ranked[0].feasibility == 0.8
        assert ranked[1].to_value == "D"
        assert ranked[2].to_value == "C"  # Lowest feasibility

    def test_get_easiest_transition(self):
        """get_easiest_transition returns most feasible option."""
        scorer = CategoricalFeasibilityScorer()
        scorer.register_domain("test", {
            ("X", "Y"): 0.2,
            ("X", "Z"): 0.9,
        })

        best = scorer.get_easiest_transition("param", "X", ["Y", "Z"], "test")

        assert best.to_value == "Z"
        assert best.feasibility == 0.9


class TestEducationFeasibility:
    """Tests for EDUCATION_FEASIBILITY matrix."""

    def test_natural_progression(self):
        """Natural degree progression has moderate feasibility."""
        scorer = create_default_scorer()

        # One step up
        assert scorer.score("degree", "high_school", "associate", "education") == 0.6
        assert scorer.score("degree", "associate", "bachelors", "education") == 0.5
        assert scorer.score("degree", "bachelors", "masters", "education") == 0.4

    def test_skip_levels(self):
        """Skipping levels is harder."""
        scorer = create_default_scorer()

        # Skip associate
        skip_score = scorer.score("degree", "high_school", "bachelors", "education")
        normal_score = scorer.score("degree", "high_school", "associate", "education")

        assert skip_score < normal_score

    def test_reverse_hard(self):
        """Reverse progression (credential loss) is very hard."""
        scorer = create_default_scorer()

        reverse = scorer.score("degree", "doctorate", "masters", "education")

        assert reverse == 0.1  # Very low

    def test_rationales(self):
        """Education rationales are available."""
        scorer = create_default_scorer()

        rationale = scorer.get_rationale("bachelors", "masters", "education")

        assert rationale == "Graduate school admission required"


class TestFinanceFeasibility:
    """Tests for FINANCE_FEASIBILITY matrix."""

    def test_improvement_moderate(self):
        """Financial improvement takes effort."""
        scorer = create_default_scorer()

        assert scorer.score("savings", "critical", "low", "finance") == 0.5
        assert scorer.score("savings", "low", "moderate", "finance") == 0.5

    def test_big_jumps_harder(self):
        """Large jumps in savings are harder."""
        scorer = create_default_scorer()

        big_jump = scorer.score("savings", "critical", "adequate", "finance")
        small_step = scorer.score("savings", "critical", "low", "finance")

        assert big_jump < small_step

    def test_decline_easier(self):
        """Financial decline is unfortunately easier."""
        scorer = create_default_scorer()

        decline = scorer.score("savings", "low", "critical", "finance")

        assert decline == 0.9  # Easy to lose money


class TestFloodFeasibility:
    """Tests for FLOOD_FEASIBILITY matrix."""

    def test_insurance_moderate(self):
        """Getting insurance is moderately feasible."""
        scorer = create_default_scorer()

        score = scorer.score("status", "unprotected", "insured", "flood")

        assert score == 0.6

    def test_elevation_hard(self):
        """Elevation is expensive and hard."""
        scorer = create_default_scorer()

        score = scorer.score("status", "unprotected", "elevated", "flood")

        assert score == 0.3

    def test_relocation_very_hard(self):
        """Relocation is very hard."""
        scorer = create_default_scorer()

        score = scorer.score("status", "unprotected", "relocated", "flood")

        assert score == 0.2

    def test_losing_insurance_easy(self):
        """Lapsing insurance is easy."""
        scorer = create_default_scorer()

        score = scorer.score("status", "insured", "unprotected", "flood")

        assert score == 0.8

    def test_cant_unelevate(self):
        """Can't un-elevate a house."""
        scorer = create_default_scorer()

        score = scorer.score("status", "elevated", "unprotected", "flood")

        assert score == 0.1  # Nearly impossible


class TestHealthFeasibility:
    """Tests for HEALTH_FEASIBILITY matrix."""

    def test_gradual_exercise_change(self):
        """Gradual exercise changes are feasible."""
        scorer = create_default_scorer()

        gradual = scorer.score("exercise", "sedentary", "light_active", "health")

        assert gradual == 0.5

    def test_drastic_change_hard(self):
        """Drastic behavior changes are very hard."""
        scorer = create_default_scorer()

        drastic = scorer.score("exercise", "sedentary", "very_active", "health")

        assert drastic == 0.1

    def test_smoking_cessation_hard(self):
        """Quitting smoking is difficult."""
        scorer = create_default_scorer()

        quit_score = scorer.score("smoking", "smoker", "non_smoker", "health")

        assert quit_score == 0.15


class TestCounterfactualEngineWithScorer:
    """Tests for CounterfactualEngine with CategoricalFeasibilityScorer."""

    def test_categorical_with_scorer(self):
        """Categorical explanation uses scorer for feasibility."""
        scorer = create_default_scorer()
        engine = CounterfactualEngine(feasibility_scorer=scorer)

        # Create rule with domain
        rule = PolicyRule.__new__(PolicyRule)
        rule.id = "r1"
        rule.param = "degree"
        rule.operator = "in"
        rule.value = ["associate", "bachelors", "masters"]
        rule.message = "Need higher education"
        rule.level = "ERROR"
        rule.xai_hint = None
        rule.domain = "education"

        result = engine.explain(rule, {"degree": "high_school"})

        assert result.strategy_used == CounterFactualStrategy.CATEGORICAL
        # Should suggest associate (0.6) as easiest from high_school
        assert result.delta_state["degree"] == "associate"
        assert result.feasibility_score == 0.6

    def test_categorical_without_scorer(self):
        """Without scorer, uses default 0.5."""
        engine = CounterfactualEngine()  # No scorer

        rule = PolicyRule(
            id="r1",
            param="status",
            operator="in",
            value=["active", "pending"],
            message="",
            level="ERROR",
        )

        result = engine.explain(rule, {"status": "inactive"})

        assert result.feasibility_score == 0.5  # Default

    def test_explanation_includes_rationale(self):
        """Explanation includes rationale when available."""
        scorer = create_default_scorer()
        engine = CounterfactualEngine(feasibility_scorer=scorer)

        rule = PolicyRule.__new__(PolicyRule)
        rule.id = "r1"
        rule.param = "degree"
        rule.operator = "in"
        rule.value = ["masters", "doctorate"]
        rule.message = ""
        rule.level = "ERROR"
        rule.xai_hint = None
        rule.domain = "education"

        result = engine.explain(rule, {"degree": "bachelors"})

        # Should include rationale in explanation
        assert "Graduate school" in result.explanation or "feasibility" in result.explanation

    def test_not_in_uses_default(self):
        """not_in operator uses default feasibility."""
        scorer = create_default_scorer()
        engine = CounterfactualEngine(feasibility_scorer=scorer)

        rule = PolicyRule(
            id="r1",
            param="status",
            operator="not_in",
            value=["banned", "suspended"],
            message="",
            level="ERROR",
        )

        result = engine.explain(rule, {"status": "banned"})

        assert result.feasibility_score == 0.4


class TestCompositeRuleExplanation:
    """Tests for CompositeRule explanation."""

    def test_or_rule_finds_easiest(self):
        """OR rule suggests easiest path."""
        engine = CounterfactualEngine()

        sub_rules = [
            PolicyRule(
                id="r1", param="savings", operator=">=",
                value=10000, message="", level="ERROR"
            ),
            PolicyRule(
                id="r2", param="income", operator=">=",
                value=100, message="", level="ERROR"
            ),
        ]

        composite = CompositeRule(
            id="c1",
            logic="OR",
            rules=sub_rules,
        )

        result = engine.explain_composite_rule(
            composite,
            {"savings": 100, "income": 50}
        )

        # Should suggest income change (smaller delta = higher feasibility)
        assert "income" in result.delta_state or result.feasibility_score > 0.5

    def test_and_rule_combines_all(self):
        """AND rule combines all changes."""
        engine = CounterfactualEngine()

        sub_rules = [
            PolicyRule(
                id="r1", param="a", operator=">=",
                value=10, message="", level="ERROR"
            ),
            PolicyRule(
                id="r2", param="b", operator=">=",
                value=20, message="", level="ERROR"
            ),
        ]

        composite = CompositeRule(
            id="c1",
            logic="AND",
            rules=sub_rules,
        )

        result = engine.explain_composite_rule(
            composite,
            {"a": 5, "b": 10}
        )

        # Should include both changes
        assert "a" in result.delta_state
        assert "b" in result.delta_state
        assert "AND" in result.explanation or "All" in result.explanation

    def test_if_then_rule(self):
        """IF_THEN rule explains consequent when condition met."""
        engine = CounterfactualEngine()

        condition = PolicyRule(
            id="cond", param="income", operator=">=",
            value=50000, message="", level="ERROR"
        )
        consequent = PolicyRule(
            id="conseq", param="savings", operator=">=",
            value=5000, message="", level="ERROR"
        )

        composite = CompositeRule(
            id="c1",
            logic="IF_THEN",
            rules=[consequent],  # consequent rules
            condition_rule=condition,  # IF_THEN requires condition_rule
        )

        # State where condition would pass (high income)
        result = engine.explain_composite_rule(
            composite,
            {"income": 60000, "savings": 1000}
        )

        # Should explain the consequent (savings requirement)
        assert result.strategy_used == CounterFactualStrategy.COMPOSITE

    def test_empty_composite(self):
        """Empty composite rule returns passed."""
        engine = CounterfactualEngine()

        composite = CompositeRule(
            id="c1",
            logic="AND",
            rules=[],
        )

        result = engine.explain_composite_rule(composite, {})

        assert result.passed is True
        assert result.feasibility_score == 1.0


class TestCreateDefaultScorer:
    """Tests for create_default_scorer factory."""

    def test_creates_all_domains(self):
        """Default scorer has all domain matrices."""
        scorer = create_default_scorer()

        # Education - use a transition defined in matrix
        assert scorer.score("x", "high_school", "associate", "education") == 0.6

        # Finance
        assert scorer.score("x", "critical", "low", "finance") == 0.5

        # Flood
        assert scorer.score("x", "unprotected", "insured", "flood") == 0.6

        # Health
        assert scorer.score("x", "sedentary", "light_active", "health") == 0.5

    def test_unknown_domain_uses_default(self):
        """Unknown domain uses default score."""
        scorer = create_default_scorer()

        score = scorer.score("x", "a", "b", "unknown_domain")

        assert score == 0.4


class TestFeasibilityIntegration:
    """Integration tests for feasibility scoring."""

    def test_flood_counterfactual_with_scorer(self):
        """Full integration: flood domain with scorer."""
        scorer = create_default_scorer()
        engine = CounterfactualEngine(feasibility_scorer=scorer)

        rule = PolicyRule.__new__(PolicyRule)
        rule.id = "protection"
        rule.param = "status"
        rule.operator = "in"
        rule.value = ["insured", "elevated", "insured_elevated"]
        rule.message = "Need protection"
        rule.level = "ERROR"
        rule.xai_hint = None
        rule.domain = "flood"

        result = engine.explain(rule, {"status": "unprotected"})

        # Should suggest insured (0.6) as easiest path
        assert result.delta_state["status"] == "insured"
        assert result.feasibility_score == 0.6
        assert "insured" in result.explanation

    def test_health_counterfactual_with_scorer(self):
        """Full integration: health domain with scorer."""
        scorer = create_default_scorer()
        engine = CounterfactualEngine(feasibility_scorer=scorer)

        rule = PolicyRule.__new__(PolicyRule)
        rule.id = "exercise"
        rule.param = "activity"
        rule.operator = "in"
        rule.value = ["light_active", "moderately_active", "very_active"]
        rule.message = "Need more exercise"
        rule.level = "ERROR"
        rule.xai_hint = None
        rule.domain = "health"

        result = engine.explain(rule, {"activity": "sedentary"})

        # Should suggest light_active (0.5) as easiest
        assert result.delta_state["activity"] == "light_active"
        assert result.feasibility_score == 0.5
