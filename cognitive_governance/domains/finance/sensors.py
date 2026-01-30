"""
Finance Domain Sensors.

SensorConfig definitions for financial variables with
domain-specific quantization based on literature.

References:
- CFPB Consumer Financial Protection Bureau
- Federal Reserve Survey of Consumer Finances
- Financial literacy research
"""

from typing import List, Dict
from cognitive_governance.v1_prototype.types import SensorConfig


# Savings ratio sensor (savings / income)
SAVINGS_RATIO_SENSOR = SensorConfig(
    domain="finance",
    variable_name="savings_ratio",
    sensor_name="SAVINGS_RATIO",
    path="agent.savings_ratio",
    data_type="numeric",
    units="ratio",
    quantization_type="threshold_bins",
    bins=[
        {"label": "CRITICAL", "max": 0.1},
        {"label": "LOW", "max": 0.3},
        {"label": "MODERATE", "max": 0.5},
        {"label": "ADEQUATE", "max": 0.7},
        {"label": "STRONG", "max": 1.0},
    ],
    bin_rationale="Emergency fund guidelines (3-6 months expenses)",
    literature_reference="CFPB Emergency Savings Guidelines",
)

# Debt-to-income ratio sensor
DEBT_RATIO_SENSOR = SensorConfig(
    domain="finance",
    variable_name="debt_ratio",
    sensor_name="DEBT_RATIO",
    path="agent.debt_ratio",
    data_type="numeric",
    units="ratio",
    quantization_type="threshold_bins",
    bins=[
        {"label": "HEALTHY", "max": 0.2},
        {"label": "MANAGEABLE", "max": 0.35},
        {"label": "CONCERNING", "max": 0.43},
        {"label": "HIGH", "max": 0.5},
        {"label": "CRITICAL", "max": 1.0},
    ],
    bin_rationale="Mortgage qualification thresholds (43% DTI limit)",
    literature_reference="Consumer Financial Protection Bureau",
)

# Credit score sensor
CREDIT_SCORE_SENSOR = SensorConfig(
    domain="finance",
    variable_name="credit_score",
    sensor_name="CREDIT_SCORE",
    path="agent.credit_score",
    data_type="numeric",
    units="points",
    quantization_type="threshold_bins",
    bins=[
        {"label": "POOR", "max": 580},
        {"label": "FAIR", "max": 670},
        {"label": "GOOD", "max": 740},
        {"label": "VERY_GOOD", "max": 800},
        {"label": "EXCEPTIONAL", "max": 850},
    ],
    bin_rationale="FICO score ranges",
    literature_reference="FICO Score Classification",
)

# Financial literacy sensor
FINANCIAL_LITERACY_SENSOR = SensorConfig(
    domain="finance",
    variable_name="financial_literacy",
    sensor_name="FINANCIAL_LITERACY",
    path="agent.financial_literacy",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 0.33},
        {"label": "MODERATE", "max": 0.66},
        {"label": "HIGH", "max": 1.0},
    ],
    bin_rationale="Based on standard financial literacy assessment",
    literature_reference="Lusardi & Mitchell Financial Literacy Scale",
)

# Risk tolerance sensor
RISK_TOLERANCE_SENSOR = SensorConfig(
    domain="finance",
    variable_name="risk_tolerance",
    sensor_name="RISK_TOLERANCE",
    path="agent.risk_tolerance",
    data_type="numeric",
    units="score",
    quantization_type="threshold_bins",
    bins=[
        {"label": "CONSERVATIVE", "max": 0.3},
        {"label": "MODERATE", "max": 0.6},
        {"label": "AGGRESSIVE", "max": 1.0},
    ],
    bin_rationale="Investment risk profile categories",
    literature_reference="Standard investment risk questionnaires",
)

# Investment allocation sensor
INVESTMENT_ALLOCATION_SENSOR = SensorConfig(
    domain="finance",
    variable_name="investment_allocation",
    sensor_name="INVESTMENT_ALLOCATION",
    path="agent.investment_allocation",
    data_type="categorical",
    categories=[
        "cash_only",
        "bonds_heavy",
        "balanced",
        "stocks_heavy",
        "aggressive_growth",
    ],
    bin_rationale="Common portfolio allocation strategies",
    literature_reference="Modern Portfolio Theory",
)

# Income level sensor
INCOME_LEVEL_SENSOR = SensorConfig(
    domain="finance",
    variable_name="income",
    sensor_name="INCOME",
    path="agent.income",
    data_type="numeric",
    units="USD",
    quantization_type="threshold_bins",
    bins=[
        {"label": "LOW", "max": 30000},
        {"label": "LOWER_MIDDLE", "max": 50000},
        {"label": "MIDDLE", "max": 75000},
        {"label": "UPPER_MIDDLE", "max": 125000},
        {"label": "HIGH", "max": float("inf")},
    ],
    bin_rationale="US Census income distribution",
    literature_reference="US Census Bureau",
)

# Market sentiment sensor
MARKET_SENTIMENT_SENSOR = SensorConfig(
    domain="finance",
    variable_name="market_sentiment",
    sensor_name="MARKET_SENTIMENT",
    path="environment.market_sentiment",
    data_type="categorical",
    categories=[
        "panic",
        "fearful",
        "neutral",
        "optimistic",
        "euphoric",
    ],
    bin_rationale="Fear and Greed Index categories",
    literature_reference="CNN Fear & Greed Index",
)


# All sensors in a list
FINANCE_SENSORS: List[str] = [
    "SAVINGS_RATIO",
    "DEBT_RATIO",
    "CREDIT_SCORE",
    "FINANCIAL_LITERACY",
    "RISK_TOLERANCE",
    "INVESTMENT_ALLOCATION",
    "INCOME",
    "MARKET_SENTIMENT",
]

# SensorConfig objects
FINANCE_SENSOR_CONFIGS: Dict[str, SensorConfig] = {
    "SAVINGS_RATIO": SAVINGS_RATIO_SENSOR,
    "DEBT_RATIO": DEBT_RATIO_SENSOR,
    "CREDIT_SCORE": CREDIT_SCORE_SENSOR,
    "FINANCIAL_LITERACY": FINANCIAL_LITERACY_SENSOR,
    "RISK_TOLERANCE": RISK_TOLERANCE_SENSOR,
    "INVESTMENT_ALLOCATION": INVESTMENT_ALLOCATION_SENSOR,
    "INCOME": INCOME_LEVEL_SENSOR,
    "MARKET_SENTIMENT": MARKET_SENTIMENT_SENSOR,
}


def get_sensor(name: str) -> SensorConfig:
    """Get a sensor configuration by name."""
    return FINANCE_SENSOR_CONFIGS.get(name)


def list_sensors() -> List[str]:
    """List available finance sensors."""
    return FINANCE_SENSORS.copy()
