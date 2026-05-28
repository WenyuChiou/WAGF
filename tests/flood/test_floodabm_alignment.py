"""
FLOODABM Parameter Alignment Tests.

Verifies that the framework parameters match the FLOODABM Supplementary Materials.

References:
- FLOODABM Supplementary Materials (Tables S1-S6)
- USACE (2006) CSVR Report
- FEMA Risk Rating 2.0 Documentation

Run with:
    pytest examples/multi_agent/tests/test_floodabm_alignment.py -v
"""

import pytest
import math


class TestCSRVConstant:
    """Test CSRV = 0.57 implementation."""

    def test_csrv_value(self):
        """Verify CSRV = 0.57 is correctly defined."""
        from examples.multi_agent.flood.environment.rcv_generator import CSRV
        assert CSRV == 0.57, f"CSRV should be 0.57, got {CSRV}"

    def test_csrv_in_contents_ratio(self):
        """Verify CSRV is used in CONTENTS_RATIO_RANGES."""
        from examples.multi_agent.flood.environment.rcv_generator import (
            CSRV,
            CONTENTS_RATIO_RANGES,
        )
        assert CONTENTS_RATIO_RANGES["owner"] == CSRV, (
            f"Owner contents ratio should be CSRV={CSRV}, "
            f"got {CONTENTS_RATIO_RANGES['owner']}"
        )

    def test_rcv_generation_uses_fixed_csrv(self):
        """Verify RCV generation uses fixed CSRV ratio."""
        from examples.multi_agent.flood.environment.rcv_generator import RCVGenerator, CSRV

        gen = RCVGenerator(seed=42)
        result = gen.generate(
            income_bracket="mid_income",
            is_owner=True,
            is_mg=False,
            family_size=3,
        )

        # Contents should be exactly CSRV * building for owners
        expected_ratio = result.contents_rcv_usd / result.building_rcv_usd
        assert abs(expected_ratio - CSRV) < 0.001, (
            f"Contents ratio should be {CSRV}, got {expected_ratio:.4f}"
        )


class TestRiskRating2Parameters:
    """Test Risk Rating 2.0 parameters."""

    def test_r1k_structure(self):
        """Verify base rate for structure coverage."""
        from examples.multi_agent.flood.environment.risk_rating import R1K_STRUCTURE
        assert R1K_STRUCTURE == 3.56, f"R1K_STRUCTURE should be 3.56, got {R1K_STRUCTURE}"

    def test_r1k_contents(self):
        """Verify base rate for contents coverage."""
        from examples.multi_agent.flood.environment.risk_rating import R1K_CONTENTS
        assert R1K_CONTENTS == 4.90, f"R1K_CONTENTS should be 4.90, got {R1K_CONTENTS}"

    def test_coverage_limits(self):
        """Verify NFIP coverage limits."""
        from examples.multi_agent.flood.environment.risk_rating import (
            LIMIT_STRUCTURE,
            LIMIT_CONTENTS,
        )
        assert LIMIT_STRUCTURE == 250_000, f"Structure limit should be $250K"
        assert LIMIT_CONTENTS == 100_000, f"Contents limit should be $100K"

    def test_deductibles(self):
        """Verify deductible amounts."""
        from examples.multi_agent.flood.environment.risk_rating import (
            DEDUCTIBLE_STRUCTURE,
            DEDUCTIBLE_CONTENTS,
        )
        assert DEDUCTIBLE_STRUCTURE == 1_000, f"Structure deductible should be $1,000"
        assert DEDUCTIBLE_CONTENTS == 1_000, f"Contents deductible should be $1,000"

    def test_reserve_and_fees(self):
        """Verify reserve fund factor and small fee."""
        from examples.multi_agent.flood.environment.risk_rating import (
            RESERVE_FUND_FACTOR,
            SMALL_FEE,
        )
        assert RESERVE_FUND_FACTOR == 1.15, f"Reserve factor should be 1.15"
        assert SMALL_FEE == 100, f"Small fee should be $100"


class TestInitialUptakeRates:
    """Test initial insurance uptake rates (Table S1)."""

    def test_flood_prone_owner(self):
        """Verify 25% uptake for flood-prone homeowners."""
        from examples.multi_agent.flood.environment.risk_rating import INITIAL_UPTAKE
        assert INITIAL_UPTAKE["flood_prone"]["owner"] == 0.25

    def test_flood_prone_renter(self):
        """Verify 8% uptake for flood-prone renters."""
        from examples.multi_agent.flood.environment.risk_rating import INITIAL_UPTAKE
        assert INITIAL_UPTAKE["flood_prone"]["renter"] == 0.08

    def test_non_flood_prone_owner(self):
        """Verify 3% uptake for non-flood-prone homeowners."""
        from examples.multi_agent.flood.environment.risk_rating import INITIAL_UPTAKE
        assert INITIAL_UPTAKE["non_flood_prone"]["owner"] == 0.03

    def test_non_flood_prone_renter(self):
        """Verify 1% uptake for non-flood-prone renters."""
        from examples.multi_agent.flood.environment.risk_rating import INITIAL_UPTAKE
        assert INITIAL_UPTAKE["non_flood_prone"]["renter"] == 0.01

    def test_get_initial_uptake_probability(self):
        """Test helper function."""
        from examples.multi_agent.flood.environment.risk_rating import (
            get_initial_uptake_probability,
        )
        assert get_initial_uptake_probability(True, True) == 0.25
        assert get_initial_uptake_probability(True, False) == 0.08
        assert get_initial_uptake_probability(False, True) == 0.03
        assert get_initial_uptake_probability(False, False) == 0.01


class TestCoreConfigParameters:
    """Test core.py ENV_CONFIG parameters."""

    def test_default_deductible(self):
        """Verify default deductible is $1,000."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["insurance"]["default_deductible"] == 1_000

    def test_deductible_by_type(self):
        """Verify separate deductibles for structure and contents."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["insurance"]["default_deductible_structure"] == 1_000
        assert ENV_CONFIG["insurance"]["default_deductible_contents"] == 1_000

    def test_r1k_rates_in_config(self):
        """Verify r1k rates are in config."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["insurance"]["r1k_structure"] == 3.56
        assert ENV_CONFIG["insurance"]["r1k_contents"] == 4.90

    def test_reserve_and_fee_in_config(self):
        """Verify reserve factor and small fee in config."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["insurance"]["reserve_fund_factor"] == 1.15
        assert ENV_CONFIG["insurance"]["small_fee"] == 100

    def test_damage_threshold(self):
        """Verify damage ratio threshold (theta)."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["damage"]["damage_ratio_threshold"] == 0.5

    def test_shock_scale(self):
        """Verify shock scale (cs)."""
        from examples.multi_agent.flood.environment.core import ENV_CONFIG
        assert ENV_CONFIG["damage"]["shock_scale"] == 0.3


class TestPremiumCalculation:
    """Test premium calculation produces expected values."""

    def test_basic_premium_calculation(self):
        """Test basic premium calculation."""
        from examples.multi_agent.flood.environment.risk_rating import RiskRating2Calculator

        calc = RiskRating2Calculator()
        result = calc.calculate_premium(
            rcv_structure=250_000,
            rcv_contents=142_500,  # 250K * 0.57 (CSRV)
            flood_zone="AE",
            is_elevated=False,
            is_owner=True,
        )

        # Note: Contents is capped at LIMIT_CONTENTS = $100,000
        # Base: structure = 250 * 3.56 = 890
        #       contents = min(142.5, 100) * 4.90 = 490 (capped!)
        # Zone AE multiplier = 1.5
        # Gross = (890 + 490) * 1.5 = 2070
        # No discounts, add fee = 2070 + 100 = 2170
        expected_approx = 2170.00

        assert abs(result.annual_premium - expected_approx) < 5.0, (
            f"Premium should be ~${expected_approx:.2f}, got ${result.annual_premium:.2f}"
        )

    def test_elevation_discount(self):
        """Test elevation discount is 50%."""
        from examples.multi_agent.flood.environment.risk_rating import RiskRating2Calculator

        calc = RiskRating2Calculator()

        premium_not_elevated = calc.calculate_premium(
            rcv_structure=250_000,
            rcv_contents=100_000,
            flood_zone="AE",
            is_elevated=False,
        )

        premium_elevated = calc.calculate_premium(
            rcv_structure=250_000,
            rcv_contents=100_000,
            flood_zone="AE",
            is_elevated=True,
        )

        # Elevated premium should be roughly 50% lower (before fee)
        # (gross * 0.5) vs gross
        ratio = premium_elevated.annual_premium / premium_not_elevated.annual_premium
        assert ratio < 0.60, f"Elevated premium ratio should be <0.6, got {ratio:.2f}"

    def test_zone_multipliers(self):
        """Test zone multipliers are applied correctly."""
        from examples.multi_agent.flood.environment.risk_rating import RiskRating2Calculator

        calc = RiskRating2Calculator()

        # High risk zone (VE = 2.5x)
        premium_ve = calc.calculate_premium(
            rcv_structure=200_000,
            rcv_contents=100_000,
            flood_zone="VE",
        )

        # Low risk zone (X = 0.5x)
        premium_x = calc.calculate_premium(
            rcv_structure=200_000,
            rcv_contents=100_000,
            flood_zone="X",
        )

        # VE should be 5x more than X (2.5 / 0.5)
        ratio = premium_ve.annual_premium / premium_x.annual_premium
        assert 4.0 < ratio < 6.0, f"VE/X premium ratio should be ~5, got {ratio:.2f}"


class TestYAMLConfiguration:
    """Test YAML configuration has FLOODABM parameters."""

    def test_floodabm_parameters_section_exists(self):
        """Verify floodabm_parameters section exists in YAML."""
        import yaml
        yaml_path = "examples/multi_agent/flood/config/parameters/floodabm_params.yaml"

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert "floodabm_parameters" in config, "Missing floodabm_parameters section"

    def test_beta_distribution_params(self):
        """Verify Beta distribution parameters are present."""
        import yaml
        yaml_path = "examples/multi_agent/flood/config/parameters/floodabm_params.yaml"

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        params = config["floodabm_parameters"]

        # Check TP distribution
        assert "tp_distribution" in params
        assert params["tp_distribution"]["mg"]["alpha"] == 4.44
        assert params["tp_distribution"]["mg"]["beta"] == 2.89
        assert params["tp_distribution"]["nmg"]["alpha"] == 5.35
        assert params["tp_distribution"]["nmg"]["beta"] == 3.62

    def test_tp_decay_params_in_yaml(self):
        """Verify TP decay calibrated parameters in YAML."""
        import yaml
        yaml_path = "examples/multi_agent/flood/config/parameters/floodabm_params.yaml"

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        decay = config["floodabm_parameters"]["tp_decay"]

        # MG parameters
        assert decay["mg"]["tau_0"] == 1.00
        assert decay["mg"]["tau_inf"] == 32.19
        assert decay["mg"]["k"] == 0.03

        # NMG parameters
        assert decay["nmg"]["tau_0"] == 2.72
        assert decay["nmg"]["tau_inf"] == 50.10
        assert decay["nmg"]["k"] == 0.01

    def test_csrv_in_yaml(self):
        """Verify CSRV in YAML config."""
        import yaml
        yaml_path = "examples/multi_agent/flood/config/parameters/floodabm_params.yaml"

        with open(yaml_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        assert config["floodabm_parameters"]["csrv"] == 0.57


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
