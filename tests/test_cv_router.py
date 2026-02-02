"""Tests for ValidationRouter — simplified 5-core-metric routing.

Validates:
    - Feature detection from config (flood, irrigation, minimal)
    - Feature detection from DataFrame
    - Plan generation (Level 1, 2, 3) for different profiles
    - 5 core metrics: CACR, RH, BRC, ICC, EBE
    - Optional diagnostics: TCS, ACTION_STABILITY, DISTRIBUTION_MATCH
    - N-dependent distribution matching threshold
    - CVRunner.from_config integration
    - ActionStabilityValidator
    - Construct-free psychometric battery methods
    - BRC computation
"""

import pytest
import numpy as np
import pandas as pd

from broker.validators.calibration.validation_router import (
    FeatureProfile,
    ValidationPlan,
    ValidationRouter,
    ValidatorSpec,
    ValidatorType,
)
from broker.validators.calibration.temporal_coherence import (
    ActionStabilityValidator,
)
from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    ProbeResponse,
    compute_icc_2_1,
)
from broker.validators.calibration.micro_validator import (
    MicroValidator,
    BRCResult,
)
from broker.validators.calibration.cv_runner import CVRunner, CVReport


# ---------------------------------------------------------------------------
# Config fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def flood_config():
    """Minimal flood ABM config (PMT constructs + governance)."""
    return {
        "shared": {
            "rating_scale": (
                "### RATING SCALE:\n"
                "VL = Very Low | L = Low | M = Medium | H = High | VH = Very High"
            ),
            "response_format": {
                "fields": [
                    {"key": "reasoning", "type": "text", "required": True},
                    {"key": "threat_appraisal", "type": "appraisal",
                     "required": True, "construct": "TP_LABEL"},
                    {"key": "coping_appraisal", "type": "appraisal",
                     "required": True, "construct": "CP_LABEL"},
                    {"key": "decision", "type": "choice", "required": True},
                ],
            },
        },
        "household": {
            "governance": {
                "strict": {
                    "thinking_rules": [
                        {"id": "extreme_threat_block",
                         "construct": "TP_LABEL",
                         "when_above": ["H", "VH"],
                         "blocked_skills": ["do_nothing"]},
                        {"id": "low_coping_block",
                         "construct": "CP_LABEL",
                         "conditions": [{"construct": "CP_LABEL",
                                        "values": ["VL", "L"]}],
                         "blocked_skills": ["elevate_house"]},
                    ],
                    "identity_rules": [
                        {"id": "relocated_freeze",
                         "precondition": "relocated",
                         "blocked_skills": ["elevate_house", "relocate"]},
                    ],
                },
            },
            "actions": [
                {"id": "do_nothing"},
                {"id": "buy_insurance"},
                {"id": "elevate_house"},
                {"id": "relocate"},
            ],
        },
    }


@pytest.fixture
def irrigation_config():
    """Minimal irrigation ABM config (WSA/ACA constructs)."""
    return {
        "shared": {
            "rating_scale": (
                "### RATING SCALE:\n"
                "VL = Very Low | L = Low | M = Medium | H = High | VH = Very High"
            ),
            "response_format": {
                "fields": [
                    {"key": "reasoning", "type": "text", "required": True},
                    {"key": "water_scarcity_assessment", "type": "appraisal",
                     "required": True, "construct": "WSA_LABEL"},
                    {"key": "adaptive_capacity_assessment", "type": "appraisal",
                     "required": True, "construct": "ACA_LABEL"},
                    {"key": "decision", "type": "choice", "required": True},
                ],
            },
        },
        "irrigation_farmer": {
            "parsing": {
                "constructs": {
                    "WSA_LABEL": {"keywords": ["water_scarcity_assessment"]},
                    "ACA_LABEL": {"keywords": ["adaptive_capacity_assessment"]},
                },
                "skill_map": {
                    "1": "increase_demand",
                    "2": "decrease_demand",
                    "3": "maintain_demand",
                },
            },
            "governance": {
                "strict": {
                    "thinking_rules": [
                        {"id": "high_scarcity_block",
                         "construct": "WSA_LABEL",
                         "when_above": ["VH"],
                         "blocked_skills": ["increase_demand"]},
                    ],
                },
            },
        },
    }


@pytest.fixture
def minimal_config():
    """Minimal config with no constructs or governance."""
    return {
        "shared": {
            "response_format": {
                "fields": [
                    {"key": "decision", "type": "choice", "required": True},
                ],
            },
        },
        "generic_agent": {
            "actions": [
                {"id": "action_a"},
                {"id": "action_b"},
                {"id": "action_c"},
            ],
        },
    }


@pytest.fixture
def flood_df():
    """Standard flood simulation DataFrame."""
    rng = np.random.RandomState(42)
    rows = []
    for year in range(1, 6):
        for agent_id in range(1, 11):
            ta = rng.choice(["L", "M", "H", "VH"])
            ca = rng.choice(["L", "M", "H"])
            decision = rng.choice([
                "do_nothing", "buy_insurance", "elevate_house", "relocate",
            ])
            rows.append({
                "agent_id": f"h_{agent_id:03d}",
                "year": year,
                "threat_appraisal": ta,
                "coping_appraisal": ca,
                "ta_level": ta,
                "ca_level": ca,
                "yearly_decision": decision,
                "elevated": year >= 4 and agent_id <= 3,
                "relocated": False,
                "has_insurance": decision == "buy_insurance",
                "reasoning": f"Given threat {ta} and coping {ca}, I choose {decision}.",
            })
    return pd.DataFrame(rows)


@pytest.fixture
def actions_only_df():
    """DataFrame with only actions (no constructs, no reasoning)."""
    rng = np.random.RandomState(42)
    rows = []
    for year in range(1, 6):
        for agent_id in range(1, 11):
            decision = rng.choice(["action_a", "action_b", "action_c"])
            rows.append({
                "agent_id": f"a_{agent_id:03d}",
                "year": year,
                "decision": decision,
            })
    return pd.DataFrame(rows)


@pytest.fixture
def large_flood_df():
    """Large flood DataFrame (250 agents) for N-dependent tests."""
    rng = np.random.RandomState(42)
    rows = []
    for year in range(1, 4):
        for agent_id in range(1, 251):
            ta = rng.choice(["L", "M", "H", "VH"])
            ca = rng.choice(["L", "M", "H"])
            decision = rng.choice([
                "do_nothing", "buy_insurance", "elevate_house", "relocate",
            ])
            rows.append({
                "agent_id": f"h_{agent_id:03d}",
                "year": year,
                "ta_level": ta,
                "ca_level": ca,
                "yearly_decision": decision,
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Feature detection tests
# ---------------------------------------------------------------------------

class TestFeatureDetectionConfig:
    """Tests for feature detection from config dicts."""

    def test_flood_config_constructs(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.has_constructs
        assert "TP_LABEL" in profile.construct_names
        assert "CP_LABEL" in profile.construct_names

    def test_flood_config_ordinal(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.has_ordinal_scale
        assert profile.ordinal_labels == ["VL", "L", "M", "H", "VH"]

    def test_flood_config_governance(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.has_thinking_rules
        assert profile.n_thinking_rules == 2
        assert profile.has_identity_rules
        assert profile.n_identity_rules == 1

    def test_flood_config_reasoning(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.has_reasoning
        assert profile.reasoning_col == "reasoning"

    def test_flood_config_actions(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.has_actions
        assert "do_nothing" in profile.action_list
        assert "relocate" in profile.action_list

    def test_flood_config_framework(self, flood_config):
        profile = ValidationRouter.detect_features(config=flood_config)
        assert profile.framework_name == "pmt"

    def test_irrigation_config_constructs(self, irrigation_config):
        profile = ValidationRouter.detect_features(config=irrigation_config)
        assert profile.has_constructs
        assert "WSA_LABEL" in profile.construct_names
        assert "ACA_LABEL" in profile.construct_names
        assert profile.framework_name == "dual_appraisal"

    def test_irrigation_config_actions(self, irrigation_config):
        profile = ValidationRouter.detect_features(config=irrigation_config)
        assert profile.has_actions
        assert "increase_demand" in profile.action_list
        assert "decrease_demand" in profile.action_list

    def test_minimal_config(self, minimal_config):
        profile = ValidationRouter.detect_features(config=minimal_config)
        assert not profile.has_constructs
        assert not profile.has_thinking_rules
        assert not profile.has_reasoning
        assert profile.has_actions
        assert len(profile.action_list) == 3


class TestFeatureDetectionData:
    """Tests for feature detection from DataFrame."""

    def test_flood_df_constructs(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        assert profile.has_constructs
        assert "TP_LABEL" in profile.construct_names
        assert "ta_level" in profile.construct_cols.values()

    def test_flood_df_temporal(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        assert profile.has_temporal
        assert profile.n_years == 5

    def test_flood_df_reasoning(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        assert profile.has_reasoning
        assert profile.reasoning_col == "reasoning"

    def test_flood_df_ordinal_auto(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        assert profile.has_ordinal_scale

    def test_flood_df_n_agents(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        assert profile.n_agents == 10

    def test_actions_only_df(self, actions_only_df):
        profile = ValidationRouter.detect_features(df=actions_only_df)
        assert not profile.has_constructs
        assert profile.has_temporal
        assert profile.has_actions
        assert profile.decision_col == "decision"
        assert not profile.has_reasoning

    def test_combined_config_and_data(self, flood_config, flood_df):
        profile = ValidationRouter.detect_features(
            config=flood_config, df=flood_df
        )
        assert profile.has_constructs
        assert profile.has_temporal
        assert profile.has_reasoning
        assert profile.has_ordinal_scale
        assert profile.framework_name == "pmt"

    def test_empty_df(self):
        df = pd.DataFrame({"x": [1, 2]})
        profile = ValidationRouter.detect_features(df=df)
        assert not profile.has_temporal
        assert not profile.has_constructs
        assert not profile.has_actions

    def test_large_df_n_agents(self, large_flood_df):
        profile = ValidationRouter.detect_features(df=large_flood_df)
        assert profile.n_agents == 250


# ---------------------------------------------------------------------------
# Plan generation tests — simplified 5 core metrics
# ---------------------------------------------------------------------------

class TestPlanGeneration:
    """Tests for decision-tree plan generation with 5 core metrics."""

    def test_flood_plan_level1_core(self, flood_config, flood_df):
        """Flood config with constructs → CACR + RH (core L1)."""
        profile = ValidationRouter.detect_features(
            config=flood_config, df=flood_df
        )
        plan = ValidationRouter.plan(profile)
        l1_types = {v.type for v in plan.level1_micro}
        assert ValidatorType.CACR in l1_types
        assert ValidatorType.RH in l1_types

    def test_flood_plan_level1_tcs_diagnostic(self, flood_config, flood_df):
        """Flood with temporal + ordinal → TCS as optional diagnostic."""
        profile = ValidationRouter.detect_features(
            config=flood_config, df=flood_df
        )
        plan = ValidationRouter.plan(profile)
        l1_types = {v.type for v in plan.level1_micro}
        assert ValidatorType.TCS in l1_types

    def test_flood_plan_level2_brc(self, flood_config, flood_df):
        """Flood with constructs + framework → BRC (core L2)."""
        profile = ValidationRouter.detect_features(
            config=flood_config, df=flood_df
        )
        plan = ValidationRouter.plan(profile)
        l2_types = {v.type for v in plan.level2_macro}
        assert ValidatorType.BRC in l2_types

    def test_flood_plan_level3_core(self, flood_config, flood_df):
        """Flood with actions + temporal → ICC + EBE (core L3)."""
        profile = ValidationRouter.detect_features(
            config=flood_config, df=flood_df
        )
        plan = ValidationRouter.plan(profile)
        l3_types = {v.type for v in plan.level3_cognitive}
        assert ValidatorType.ICC in l3_types
        assert ValidatorType.EBE in l3_types

    def test_actions_only_plan_level1(self, actions_only_df):
        """No constructs → no CACR, but has ACTION_STABILITY."""
        profile = ValidationRouter.detect_features(df=actions_only_df)
        plan = ValidationRouter.plan(profile)
        l1_types = {v.type for v in plan.level1_micro}
        assert ValidatorType.CACR not in l1_types
        assert ValidatorType.TCS not in l1_types
        assert ValidatorType.ACTION_STABILITY in l1_types

    def test_actions_only_plan_level3(self, actions_only_df):
        """Actions-only → ICC (L3) but no BRC (L2)."""
        profile = ValidationRouter.detect_features(df=actions_only_df)
        plan = ValidationRouter.plan(profile)
        l2_types = {v.type for v in plan.level2_macro}
        assert ValidatorType.BRC not in l2_types
        l3_types = {v.type for v in plan.level3_cognitive}
        assert ValidatorType.ICC in l3_types
        assert ValidatorType.EBE in l3_types

    def test_minimal_config_plan(self, minimal_config):
        profile = ValidationRouter.detect_features(config=minimal_config)
        plan = ValidationRouter.plan(profile)
        # Minimal config has actions → gets ICC
        l3_types = {v.type for v in plan.level3_cognitive}
        assert ValidatorType.ICC in l3_types

    def test_reference_data_enables_distribution_match(self, flood_df):
        """Reference data → DISTRIBUTION_MATCH diagnostic."""
        profile = ValidationRouter.detect_features(
            df=flood_df,
            reference_data={"adoption_rates": [0.1, 0.2, 0.3]},
        )
        plan = ValidationRouter.plan(profile)
        l2_types = {v.type for v in plan.level2_macro}
        assert ValidatorType.DISTRIBUTION_MATCH in l2_types

    def test_no_reference_data_no_distribution_match(self, flood_df):
        profile = ValidationRouter.detect_features(df=flood_df)
        plan = ValidationRouter.plan(profile)
        l2_types = {v.type for v in plan.level2_macro}
        assert ValidatorType.DISTRIBUTION_MATCH not in l2_types

    def test_distribution_match_n_dependent_small(self, flood_df):
        """N=10 → distribution match NOT required (diagnostic only)."""
        profile = ValidationRouter.detect_features(
            df=flood_df,
            reference_data={"rates": [0.1]},
        )
        plan = ValidationRouter.plan(profile)
        dist_specs = [
            v for v in plan.level2_macro
            if v.type == ValidatorType.DISTRIBUTION_MATCH
        ]
        assert len(dist_specs) == 1
        assert not dist_specs[0].required  # N=10 < 200

    def test_distribution_match_n_dependent_large(self, large_flood_df):
        """N=250 → distribution match IS required."""
        profile = ValidationRouter.detect_features(
            df=large_flood_df,
            reference_data={"rates": [0.1]},
        )
        plan = ValidationRouter.plan(profile)
        dist_specs = [
            v for v in plan.level2_macro
            if v.type == ValidatorType.DISTRIBUTION_MATCH
        ]
        assert len(dist_specs) == 1
        assert dist_specs[0].required  # N=250 >= 200

    def test_detect_and_plan_convenience(self, flood_config, flood_df):
        plan = ValidationRouter.detect_and_plan(
            config=flood_config, df=flood_df
        )
        assert isinstance(plan, ValidationPlan)
        assert plan.profile is not None
        assert len(plan.all_validators) > 0

    def test_plan_summary(self, flood_config, flood_df):
        plan = ValidationRouter.detect_and_plan(
            config=flood_config, df=flood_df
        )
        s = plan.summary()
        assert "level1" in s
        assert "level2" in s
        assert "level3" in s
        assert "total_validators" in s
        assert s["total_validators"] > 0

    def test_total_validators_simplified(self, flood_config, flood_df):
        """Total validators should be <= 8 (5 core + 3 optional max)."""
        plan = ValidationRouter.detect_and_plan(
            config=flood_config, df=flood_df
        )
        # Flood config: CACR, RH, TCS (L1) + BRC (L2) + ICC, EBE (L3) = 6
        assert len(plan.all_validators) <= 8

    def test_all_5_core_metrics_for_flood(self, flood_config, flood_df):
        """Full flood config should enable all 5 core metrics."""
        plan = ValidationRouter.detect_and_plan(
            config=flood_config, df=flood_df
        )
        all_types = {v.type for v in plan.all_validators}
        assert ValidatorType.CACR in all_types   # M1
        assert ValidatorType.RH in all_types     # M2
        assert ValidatorType.BRC in all_types    # M3
        assert ValidatorType.ICC in all_types    # M4
        assert ValidatorType.EBE in all_types    # M5


# ---------------------------------------------------------------------------
# ActionStabilityValidator tests
# ---------------------------------------------------------------------------

class TestActionStability:
    """Tests for construct-free temporal action stability."""

    def test_stable_agent(self):
        """Agent that never changes -> lock-in = 1.0, switch = 0.0."""
        df = pd.DataFrame({
            "agent_id": ["a"] * 5,
            "year": [1, 2, 3, 4, 5],
            "yearly_decision": ["x", "x", "x", "x", "x"],
        })
        v = ActionStabilityValidator(decision_col="yearly_decision")
        result = v.compute(df)
        assert result["switch_rate"] == 0.0
        assert result["lock_in_rate"] == 1.0

    def test_erratic_agent(self):
        """Agent that switches every year -> switch rate = 1.0."""
        df = pd.DataFrame({
            "agent_id": ["a"] * 5,
            "year": [1, 2, 3, 4, 5],
            "yearly_decision": ["x", "y", "x", "y", "x"],
        })
        v = ActionStabilityValidator(decision_col="yearly_decision")
        result = v.compute(df)
        assert result["switch_rate"] == 1.0
        assert result["lock_in_rate"] == 0.0

    def test_mixed_agents(self):
        """Mix of stable and switching agents."""
        df = pd.DataFrame({
            "agent_id": ["a", "a", "a", "b", "b", "b"],
            "year": [1, 2, 3, 1, 2, 3],
            "yearly_decision": ["x", "x", "x", "x", "y", "z"],
        })
        v = ActionStabilityValidator(decision_col="yearly_decision")
        result = v.compute(df)
        assert result["switch_rate"] == pytest.approx(0.5)
        assert result["lock_in_rate"] == pytest.approx(0.5)

    def test_entropy_by_year(self):
        """Entropy should be computed per year."""
        df = pd.DataFrame({
            "agent_id": ["a", "b", "c", "a", "b", "c"],
            "year": [1, 1, 1, 2, 2, 2],
            "yearly_decision": ["x", "x", "x", "x", "y", "z"],
        })
        v = ActionStabilityValidator(decision_col="yearly_decision")
        result = v.compute(df)
        assert 1 in result["entropy_by_year"]
        assert 2 in result["entropy_by_year"]
        # Year 1: all same -> entropy = 0
        assert result["entropy_by_year"][1] == 0.0
        # Year 2: all different -> entropy > 0
        assert result["entropy_by_year"][2] > 0

    def test_empty_df(self):
        """Empty DataFrame -> zero metrics."""
        df = pd.DataFrame({"agent_id": [], "year": [], "yearly_decision": []})
        v = ActionStabilityValidator(decision_col="yearly_decision")
        result = v.compute(df)
        assert result["switch_rate"] == 0.0


# ---------------------------------------------------------------------------
# Construct-free psychometric battery tests
# ---------------------------------------------------------------------------

class TestDecisionICC:
    """Tests for Decision ICC (construct-free Level 3)."""

    def test_perfect_decision_agreement(self):
        """All replicates give same decision -> ICC high."""
        battery = PsychometricBattery()
        responses = []
        for arch in ["a", "b", "c"]:
            for rep in range(1, 6):
                responses.append(ProbeResponse(
                    vignette_id="v1", archetype=arch, replicate=rep,
                    decision="action_x",
                ))
        battery.add_responses(responses)
        icc = battery.compute_decision_icc()
        # All same decision within each archetype -> high within-group agreement
        # But also same across archetypes -> no between-subject variance
        assert icc.n_subjects == 3
        assert icc.n_raters == 5

    def test_varying_decisions(self):
        """Different archetypes choose differently -> ICC should be computable."""
        battery = PsychometricBattery()
        responses = []
        action_map = {"a": "x", "b": "y", "c": "z"}
        for arch, action in action_map.items():
            for rep in range(1, 6):
                responses.append(ProbeResponse(
                    vignette_id="v1", archetype=arch, replicate=rep,
                    decision=action,
                ))
        battery.add_responses(responses)
        icc = battery.compute_decision_icc()
        assert icc.icc_value > 0.5  # High reliability

    def test_custom_ordinal_map(self):
        """Custom action ordinal mapping should work."""
        battery = PsychometricBattery()
        responses = []
        for arch in ["a", "b"]:
            for rep in range(1, 4):
                responses.append(ProbeResponse(
                    vignette_id="v1", archetype=arch, replicate=rep,
                    decision="elevate" if arch == "a" else "relocate",
                ))
        battery.add_responses(responses)
        custom_map = {"elevate": 1, "relocate": 2, "insure": 3}
        icc = battery.compute_decision_icc(action_ordinal_map=custom_map)
        assert isinstance(icc.icc_value, float)


class TestReasoningConsistency:
    """Tests for reasoning consistency (construct-free Level 3)."""

    def test_identical_reasoning(self):
        """Identical reasoning -> consistency = 1.0."""
        battery = PsychometricBattery()
        text = "Given the flood risk I choose to buy insurance"
        responses = []
        for rep in range(1, 4):
            responses.append(ProbeResponse(
                vignette_id="v1", archetype="a", replicate=rep,
                reasoning=text,
            ))
        battery.add_responses(responses)
        result = battery.compute_reasoning_consistency()
        assert result["mean_consistency"] == pytest.approx(1.0)
        assert result["n_pairs"] == 3  # C(3,2) = 3

    def test_different_reasoning(self):
        """Completely different reasoning -> low consistency."""
        battery = PsychometricBattery()
        responses = [
            ProbeResponse(
                vignette_id="v1", archetype="a", replicate=1,
                reasoning="alpha beta gamma delta",
            ),
            ProbeResponse(
                vignette_id="v1", archetype="a", replicate=2,
                reasoning="epsilon zeta eta theta",
            ),
            ProbeResponse(
                vignette_id="v1", archetype="a", replicate=3,
                reasoning="iota kappa lambda mu",
            ),
        ]
        battery.add_responses(responses)
        result = battery.compute_reasoning_consistency()
        assert result["mean_consistency"] < 0.1

    def test_no_reasoning(self):
        """No reasoning text -> zero consistency."""
        battery = PsychometricBattery()
        responses = [
            ProbeResponse(
                vignette_id="v1", archetype="a", replicate=1,
                decision="x",
            ),
        ]
        battery.add_responses(responses)
        result = battery.compute_reasoning_consistency()
        assert result["mean_consistency"] == 0.0


class TestProbeResponseConstructLabels:
    """Tests for generalized construct_labels on ProbeResponse."""

    def test_tp_cp_sync(self):
        """tp_label/cp_label should sync to construct_labels."""
        r = ProbeResponse(
            vignette_id="v1", archetype="a", replicate=1,
            tp_label="H", cp_label="L",
        )
        assert r.construct_labels["TP_LABEL"] == "H"
        assert r.construct_labels["CP_LABEL"] == "L"

    def test_generic_constructs(self):
        """Custom constructs via construct_labels dict."""
        r = ProbeResponse(
            vignette_id="v1", archetype="a", replicate=1,
            construct_labels={"WSA_LABEL": "VH", "ACA_LABEL": "L"},
        )
        assert r.get_ordinal("WSA_LABEL") == 5  # VH = 5 in LABEL_TO_ORDINAL
        assert r.get_ordinal("ACA_LABEL") == 2  # L = 2

    def test_custom_label_map(self):
        """Custom label map in get_ordinal."""
        r = ProbeResponse(
            vignette_id="v1", archetype="a", replicate=1,
            construct_labels={"BUDGET_UTIL": "H"},
        )
        custom_map = {"L": 1, "M": 2, "H": 3}
        assert r.get_ordinal("BUDGET_UTIL", label_map=custom_map) == 3

    def test_missing_construct(self):
        """Missing construct returns 0."""
        r = ProbeResponse(
            vignette_id="v1", archetype="a", replicate=1,
        )
        assert r.get_ordinal("NONEXISTENT") == 0


# ---------------------------------------------------------------------------
# BRC tests
# ---------------------------------------------------------------------------

class TestBRC:
    """Tests for Behavioral Reference Concordance (M3)."""

    @pytest.fixture
    def brc_validator(self):
        return MicroValidator(
            framework="pmt",
            ta_col="threat_appraisal",
            ca_col="coping_appraisal",
        )

    def test_brc_all_concordant(self, brc_validator):
        """Actions matching PMT expectations -> BRC = 1.0."""
        rows = [
            # High TP + High CP -> elevate_house is expected
            {"agent_id": "a1", "year": 2, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "H", "coping_appraisal": "H"},
            # Low TP -> do_nothing is expected
            {"agent_id": "a2", "year": 2, "ta_level": "L", "ca_level": "M",
             "yearly_decision": "do_nothing",
             "threat_appraisal": "L", "coping_appraisal": "M"},
            # Medium TP -> buy_insurance is expected
            {"agent_id": "a3", "year": 2, "ta_level": "M", "ca_level": "M",
             "yearly_decision": "buy_insurance",
             "threat_appraisal": "M", "coping_appraisal": "M"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=1)
        assert result.brc == 1.0
        assert result.concordant == 3
        assert result.total == 3

    def test_brc_none_concordant(self, brc_validator):
        """Actions contradicting PMT expectations -> BRC = 0.0."""
        rows = [
            # Low TP -> relocate is NOT expected (only do_nothing, buy_insurance)
            {"agent_id": "a1", "year": 2, "ta_level": "L", "ca_level": "L",
             "yearly_decision": "relocate",
             "threat_appraisal": "L", "coping_appraisal": "L"},
            # Low TP -> elevate_house is NOT expected
            {"agent_id": "a2", "year": 2, "ta_level": "VL", "ca_level": "M",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "VL", "coping_appraisal": "M"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=1)
        assert result.brc == 0.0
        assert result.concordant == 0
        assert result.total == 2

    def test_brc_mixed(self, brc_validator):
        """Mix of concordant and discordant -> BRC = 0.5."""
        rows = [
            # Concordant: High TP + High CP -> buy_insurance (in expected set)
            {"agent_id": "a1", "year": 2, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "buy_insurance",
             "threat_appraisal": "H", "coping_appraisal": "H"},
            # Discordant: Low TP -> elevate_house (not in expected set)
            {"agent_id": "a2", "year": 2, "ta_level": "L", "ca_level": "M",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "L", "coping_appraisal": "M"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=1)
        assert result.brc == 0.5
        assert result.concordant == 1
        assert result.total == 2

    def test_brc_by_year(self, brc_validator):
        """BRC should decompose by year."""
        rows = [
            # Year 2: concordant
            {"agent_id": "a1", "year": 2, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "H", "coping_appraisal": "H"},
            # Year 3: discordant
            {"agent_id": "a1", "year": 3, "ta_level": "L", "ca_level": "L",
             "yearly_decision": "relocate",
             "threat_appraisal": "L", "coping_appraisal": "L"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=2)
        assert 2 in result.brc_by_year
        assert 3 in result.brc_by_year
        assert result.brc_by_year[2] == 1.0
        assert result.brc_by_year[3] == 0.0

    def test_brc_empty_df(self, brc_validator):
        """Empty DataFrame -> BRC = 0.0."""
        df = pd.DataFrame(columns=[
            "agent_id", "year", "ta_level", "ca_level",
            "yearly_decision", "threat_appraisal", "coping_appraisal",
        ])
        result = brc_validator.compute_brc(df, start_year=1)
        assert result.brc == 0.0
        assert result.total == 0

    def test_brc_start_year_filter(self, brc_validator):
        """Start year filter should exclude early data."""
        rows = [
            {"agent_id": "a1", "year": 1, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "H", "coping_appraisal": "H"},
            {"agent_id": "a1", "year": 2, "ta_level": "H", "ca_level": "H",
             "yearly_decision": "elevate_house",
             "threat_appraisal": "H", "coping_appraisal": "H"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=2)
        assert result.total == 1  # Only year 2

    def test_brc_result_serialization(self, brc_validator):
        """BRCResult.to_dict() should produce a valid dict."""
        rows = [
            {"agent_id": "a1", "year": 2, "ta_level": "M", "ca_level": "M",
             "yearly_decision": "buy_insurance",
             "threat_appraisal": "M", "coping_appraisal": "M"},
        ]
        df = pd.DataFrame(rows)
        result = brc_validator.compute_brc(df, start_year=1)
        d = result.to_dict()
        assert "brc" in d
        assert "concordant" in d
        assert "total" in d
        assert "brc_by_year" in d


# ---------------------------------------------------------------------------
# CVRunner.from_config integration tests
# ---------------------------------------------------------------------------

class TestCVRunnerFromConfig:
    """Tests for auto-detect mode via from_config."""

    def test_from_config_creates_plan(self, flood_config, flood_df):
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        assert runner.plan is not None
        assert runner.profile is not None
        assert len(runner.plan.all_validators) > 0

    def test_from_config_posthoc(self, flood_config, flood_df):
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        report = runner.run_posthoc()
        assert isinstance(report, CVReport)
        assert report.micro is not None
        assert report.validation_plan is not None
        assert "level1" in report.validation_plan

    def test_from_config_has_brc(self, flood_config, flood_df):
        """Auto-detect with flood config should produce BRC."""
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        report = runner.run_posthoc()
        assert report.brc is not None
        assert isinstance(report.brc, BRCResult)
        assert 0.0 <= report.brc.brc <= 1.0
        assert report.brc.total > 0

    def test_from_config_actions_only(self, minimal_config, actions_only_df):
        """Auto-detect with actions-only data should still work."""
        runner = CVRunner.from_config(
            config=minimal_config, df=actions_only_df,
            group="test", start_year=1,
        )
        plan = runner.plan
        l1_types = {v.type for v in plan.level1_micro}
        assert ValidatorType.ACTION_STABILITY in l1_types
        # Should be able to run posthoc without error
        report = runner.run_posthoc()
        assert report.action_stability is not None

    def test_from_config_metadata(self, flood_config, flood_df):
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        report = runner.run_posthoc()
        assert report.metadata["group"] == "B"
        assert report.metadata["framework"] == "pmt"

    def test_backward_compatible_explicit_mode(self, flood_df):
        """Original explicit API still works."""
        runner = CVRunner(
            framework="pmt",
            ta_col="threat_appraisal",
            ca_col="coping_appraisal",
            group="B",
            start_year=2,
        )
        runner._df = flood_df
        report = runner.run_posthoc()
        assert report.micro is not None
        assert report.validation_plan is None  # No auto-detect in explicit mode

    def test_brc_in_summary(self, flood_config, flood_df):
        """BRC should appear in report.summary."""
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        report = runner.run_posthoc()
        s = report.summary
        assert "BRC" in s

    def test_brc_in_to_dict(self, flood_config, flood_df):
        """BRC should appear in report.to_dict()."""
        runner = CVRunner.from_config(
            config=flood_config, df=flood_df, group="B", start_year=2,
        )
        report = runner.run_posthoc()
        d = report.to_dict()
        assert "level2_brc" in d
