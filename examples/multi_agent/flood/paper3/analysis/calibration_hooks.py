"""
Flood Domain Calibration Hooks.

Provides the domain-specific callbacks required by the generic
CalibrationProtocol:

    - ``compute_flood_metrics(df)`` — extracts flood-domain metrics
      from simulation trace DataFrames
    - ``create_directional_prompt_builder(archetypes_path)`` — builds
      prompts for directional sensitivity probing
    - ``create_probe_parse_fn()`` — parses LLM probe responses

These hooks bridge the generic broker calibration engine with the
flood-specific experiment configuration.

Usage::

    from paper3.analysis.calibration_hooks import (
        compute_flood_metrics,
        create_directional_prompt_builder,
        create_probe_parse_fn,
    )
    from broker.validators.calibration import CalibrationProtocol

    protocol = CalibrationProtocol.from_yaml("configs/calibration.yaml")

    # Register domain callbacks on the directional validator
    protocol._validator.register_prompt_builder(
        create_directional_prompt_builder()
    )
    protocol._validator.register_parse_fn(create_probe_parse_fn())

    report = protocol.run(
        simulate_fn=my_simulation,
        compute_metrics_fn=compute_flood_metrics,
        invoke_llm_fn=my_llm_invoke,
    )
"""

from __future__ import annotations

import json
import re
from typing import Any, Callable, Dict, Tuple

import pandas as pd


# ---------------------------------------------------------------------------
# Metric computation (SimulateFn callback)
# ---------------------------------------------------------------------------

def compute_flood_metrics(df: pd.DataFrame) -> Dict[str, float]:
    """Extract flood-domain metrics from a simulation trace DataFrame.

    This function reuses the logic from ``empirical_benchmarks.py``
    but is structured as a standalone callback for the calibration
    protocol.

    Parameters
    ----------
    df : DataFrame
        CVRunner-compatible simulation trace with columns:
        agent_id, year, yearly_decision, insured, elevated, relocated,
        mg_status, agent_type, and optionally flood_depth_ft.

    Returns
    -------
    dict
        Mapping of metric name -> observed value.
    """
    if df.empty:
        return {}

    decision_col = "yearly_decision"
    n_total = df["agent_id"].nunique()
    if n_total == 0:
        return {}

    last_year = df["year"].max()
    last_df = df[df["year"] == last_year]
    rates: Dict[str, float] = {}

    # Insurance rate (cumulative at last year)
    if "insured" in last_df.columns:
        rates["insurance_rate"] = float(last_df["insured"].astype(bool).mean())
        rates["insurance_rate_all"] = rates["insurance_rate"]

    # Elevation rate (homeowners only)
    if "elevated" in last_df.columns:
        owners = last_df[last_df.get("agent_type", pd.Series()) == "household_owner"]
        if len(owners) > 0:
            rates["elevation_rate"] = float(owners["elevated"].astype(bool).mean())
        else:
            rates["elevation_rate"] = float(last_df["elevated"].astype(bool).mean())

    # Buyout rate
    if "relocated" in last_df.columns:
        rates["buyout_rate"] = float(last_df["relocated"].astype(bool).mean())

    # Post-flood inaction rate
    if "flood_depth_ft" in df.columns:
        flooded = df[df["flood_depth_ft"] > 0]
        if len(flooded) > 0:
            action = flooded[decision_col].str.lower()
            rates["do_nothing_rate_postflood"] = float((action == "do_nothing").mean())
    else:
        action = df[decision_col].str.lower()
        rates["do_nothing_rate_postflood"] = float((action == "do_nothing").mean())

    # Repetitive loss uninsured rate
    if "insured" in last_df.columns and "flood_depth_ft" in df.columns:
        flood_counts = df[df["flood_depth_ft"] > 0].groupby("agent_id").size()
        rl_agents_ids = flood_counts[flood_counts >= 2].index
        rl_last = last_df[last_df["agent_id"].isin(rl_agents_ids)]
        if len(rl_last) > 0:
            rates["rl_uninsured_rate"] = float(
                (~rl_last["insured"].astype(bool)).mean()
            )

    # Insurance lapse rate
    if "insured" in df.columns and df["year"].nunique() > 1:
        years_sorted = sorted(df["year"].unique())
        lapse_events = 0
        insured_years = 0
        for i in range(len(years_sorted) - 1):
            y1 = df[df["year"] == years_sorted[i]]
            y2 = df[df["year"] == years_sorted[i + 1]]
            merged = y1[["agent_id", "insured"]].merge(
                y2[["agent_id", "insured"]],
                on="agent_id",
                suffixes=("_prev", "_next"),
            )
            was = merged["insured_prev"].astype(bool)
            now = merged["insured_next"].astype(bool)
            lapse_events += int((was & ~now).sum())
            insured_years += int(was.sum())
        if insured_years > 0:
            rates["insurance_lapse_rate"] = lapse_events / insured_years

    # MG-NMG adaptation gap
    if "mg_status" in last_df.columns:
        mg = last_df[last_df["mg_status"] == "MG"]
        nmg = last_df[last_df["mg_status"] == "NMG"]

        def _adapted(sub: pd.DataFrame) -> float:
            if len(sub) == 0:
                return 0.0
            return float(
                (
                    sub["elevated"].astype(bool)
                    | sub.get("insured", pd.Series(False)).astype(bool)
                    | sub.get("relocated", pd.Series(False)).astype(bool)
                ).mean()
            )

        rates["mg_adaptation_gap"] = _adapted(nmg) - _adapted(mg)

    return rates


# ---------------------------------------------------------------------------
# Directional prompt builder
# ---------------------------------------------------------------------------

DIRECTIONAL_PROMPT_TEMPLATE = """\
You are a homeowner in the Passaic River Basin, New Jersey.

### YOUR SITUATION
- Income: $50,000 - $74,999
- Flood Zone: AE (high risk)
- Property Value: $280,000
- You currently do not have flood insurance.
- You have not elevated your home.

### SCENARIO
{stimulus_value}

### ADAPTATION OPTIONS
Choose ONE primary action:
1. buy_insurance - Purchase NFIP flood insurance
2. elevate_house - Elevate your home above Base Flood Elevation
3. buyout_program - Accept the Blue Acres government buyout
4. do_nothing - Take no protective action this year

### EVALUATION CRITERIA
- TP (Threat Perception): How serious do you perceive the flood risk?
- CP (Coping Perception): How confident are you that you can take effective action?
- SC (Social Capital): How much do your neighbors' actions influence you?

Rating Scale: VL=Very Low, L=Low, M=Medium, H=High, VH=Very High

Based on the scenario, evaluate your threat and coping perceptions, then choose an action.

Respond ONLY with valid JSON:
{{"TP_LABEL": "VL|L|M|H|VH", "CP_LABEL": "VL|L|M|H|VH", "SC_LABEL": "VL|L|M|H|VH", "decision": "your_action", "reasoning": "brief explanation"}}"""


def create_directional_prompt_builder() -> Callable:
    """Create a prompt builder for directional sensitivity tests.

    Returns a function matching the DirectionalValidator callback
    protocol: ``(context: dict, stimulus_value: str) -> str``.
    """

    def builder(context: Dict[str, Any], stimulus_value: str) -> str:
        return DIRECTIONAL_PROMPT_TEMPLATE.format(
            stimulus_value=stimulus_value,
        )

    return builder


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------

def create_probe_parse_fn() -> Callable:
    """Create a response parser for directional probes.

    Returns a function matching the DirectionalValidator callback
    protocol: ``(raw_output: str) -> dict``.
    """

    def parse_fn(raw: str) -> Dict[str, str]:
        # Try direct JSON parse
        try:
            d = json.loads(raw)
            return {str(k): str(v) for k, v in d.items()}
        except (json.JSONDecodeError, TypeError):
            pass

        # Try extracting JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                d = json.loads(json_match.group(1))
                return {str(k): str(v) for k, v in d.items()}
            except (json.JSONDecodeError, TypeError):
                pass

        # Try extracting JSON from raw text
        json_match = re.search(r"\{[^{}]+\}", raw)
        if json_match:
            try:
                d = json.loads(json_match.group(0))
                return {str(k): str(v) for k, v in d.items()}
            except (json.JSONDecodeError, TypeError):
                pass

        return {}

    return parse_fn


# ---------------------------------------------------------------------------
# LLM invoke factory
# ---------------------------------------------------------------------------

def create_calibration_invoke(
    model: str = "gemma3:4b",
    temperature: float = 0.7,
    num_ctx: int = 8192,
) -> Callable[[str], Tuple[str, bool]]:
    """Create an LLM invoke function for calibration probes.

    Parameters
    ----------
    model : str
        Ollama model name.
    temperature : float
        Sampling temperature.
    num_ctx : int
        Context window size.

    Returns
    -------
    callable
        ``(prompt: str) -> (raw_output: str, success: bool)``
    """

    def invoke(prompt: str) -> Tuple[str, bool]:
        try:
            import requests

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": temperature,
                        "num_ctx": num_ctx,
                    },
                },
                timeout=120,
            )

            if response.status_code == 200:
                result = response.json()
                text = result.get("response", "")
                return text, bool(text.strip())
            else:
                return "", False
        except Exception:
            return "", False

    return invoke
