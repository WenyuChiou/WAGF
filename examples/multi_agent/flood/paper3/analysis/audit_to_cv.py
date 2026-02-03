"""
AuditWriter → CVRunner Data Adapter.

Transforms GenericAuditWriter CSV outputs into a CVRunner-compatible
DataFrame for post-hoc C&V validation.

Column mapping:
    AuditWriter CSV              →  CVRunner DataFrame
    ─────────────────────────────────────────────────────
    final_skill                  →  yearly_decision
    construct_TP_LABEL           →  threat_appraisal, ta_level
    construct_CP_LABEL           →  coping_appraisal, ca_level
    reason_text / raw_output     →  reasoning
    (derived cumulative)         →  elevated, relocated, insured

Usage:
    from paper3.analysis.audit_to_cv import load_audit_for_cv

    df = load_audit_for_cv("paper3/results/seed_42/")
    runner = CVRunner(framework="pmt", decision_col="yearly_decision")
    report = runner.run_posthoc(df=df)
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Union

import pandas as pd


# ---------------------------------------------------------------------------
# Column mappings
# ---------------------------------------------------------------------------

AUDIT_TO_CV_COLUMNS = {
    "final_skill": "yearly_decision",
    "construct_TP_LABEL": "threat_appraisal",
    "construct_CP_LABEL": "coping_appraisal",
}

# Actions that set cumulative state flags
ELEVATE_ACTIONS = {"elevate_house"}
RELOCATE_ACTIONS = {"relocate", "buyout_program"}
INSURE_ACTIONS = {"buy_insurance", "buy_contents_insurance"}

# Household agent types
HOUSEHOLD_TYPES = {"household_owner", "household_renter"}


# ---------------------------------------------------------------------------
# Core adapter
# ---------------------------------------------------------------------------

def load_single_audit_csv(
    path: Union[str, Path],
    agent_type: Optional[str] = None,
) -> pd.DataFrame:
    """Load a single audit CSV and apply column renaming.

    Parameters
    ----------
    path : str or Path
        Path to ``{agent_type}_governance_audit.csv``.
    agent_type : str, optional
        Agent type label (inferred from filename if not provided).

    Returns
    -------
    DataFrame
        Renamed columns; no cumulative state derivation yet.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Audit CSV not found: {path}")

    df = pd.read_csv(path)

    # Infer agent_type from filename if not provided
    if agent_type is None:
        stem = path.stem.replace("_governance_audit", "")
        agent_type = stem

    df["agent_type"] = agent_type

    # Rename columns
    rename_map = {}
    for old, new in AUDIT_TO_CV_COLUMNS.items():
        if old in df.columns:
            rename_map[old] = new
    df = df.rename(columns=rename_map)

    # Also copy construct labels to ta_level / ca_level for classifier bypass
    if "threat_appraisal" in df.columns:
        df["ta_level"] = df["threat_appraisal"]
    if "coping_appraisal" in df.columns:
        df["ca_level"] = df["coping_appraisal"]

    # Reasoning column: prefer reason_text, fallback to raw_output
    if "reasoning" not in df.columns:
        if "reason_text" in df.columns:
            df["reasoning"] = df["reason_text"]
        elif "raw_output" in df.columns:
            df["reasoning"] = df["raw_output"]
        else:
            df["reasoning"] = ""

    return df


def derive_cumulative_states(df: pd.DataFrame) -> pd.DataFrame:
    """Derive cumulative state columns (elevated, relocated, insured).

    Once an agent takes an irreversible action (elevate, relocate/buyout),
    the state flag stays True for all subsequent years.

    Insurance is treated as renewable: True when purchased in current year
    or maintained from prior year.

    Parameters
    ----------
    df : DataFrame
        Must have ``agent_id``, ``year``, ``yearly_decision`` columns.

    Returns
    -------
    DataFrame
        With ``elevated``, ``relocated``, ``insured`` boolean columns added.
    """
    df = df.sort_values(["agent_id", "year"]).copy()

    elevated = {}
    relocated = {}
    insured = {}

    elevated_col = []
    relocated_col = []
    insured_col = []

    for _, row in df.iterrows():
        aid = row["agent_id"]
        action = str(row.get("yearly_decision", "")).strip().lower()

        # Initialize tracking for new agents
        if aid not in elevated:
            elevated[aid] = False
            relocated[aid] = False
            insured[aid] = False

        # Irreversible: elevation
        if action in ELEVATE_ACTIONS:
            elevated[aid] = True

        # Irreversible: relocation / buyout
        if action in RELOCATE_ACTIONS:
            relocated[aid] = True

        # Renewable: insurance (active if purchased this year)
        if action in INSURE_ACTIONS:
            insured[aid] = True
        # If not purchasing this year, keep previous state
        # (simple model: insurance persists unless explicitly dropped)

        elevated_col.append(elevated[aid])
        relocated_col.append(relocated[aid])
        insured_col.append(insured[aid])

    df["elevated"] = elevated_col
    df["relocated"] = relocated_col
    df["insured"] = insured_col

    return df


def load_audit_for_cv(
    trace_dir: Union[str, Path],
    agent_types: Optional[List[str]] = None,
    agent_metadata: Optional[Dict[str, Dict]] = None,
) -> pd.DataFrame:
    """Load all household audit CSVs from a trace directory and merge.

    Parameters
    ----------
    trace_dir : str or Path
        Directory containing ``{agent_type}_governance_audit.csv`` files.
    agent_types : list of str, optional
        Which agent types to load. Default: household_owner, household_renter.
    agent_metadata : dict, optional
        ``{agent_id: {"mg_status": "MG"|"NMG", ...}}`` for adding demographics.

    Returns
    -------
    DataFrame
        Unified CVRunner-compatible DataFrame with all household agents.
    """
    trace_dir = Path(trace_dir)
    if agent_types is None:
        agent_types = list(HOUSEHOLD_TYPES)

    frames = []
    for atype in agent_types:
        csv_path = trace_dir / f"{atype}_governance_audit.csv"
        if csv_path.exists():
            df = load_single_audit_csv(csv_path, agent_type=atype)
            frames.append(df)

    if not frames:
        raise FileNotFoundError(
            f"No household audit CSVs found in {trace_dir}. "
            f"Expected: {[f'{t}_governance_audit.csv' for t in agent_types]}"
        )

    merged = pd.concat(frames, ignore_index=True)

    # Derive cumulative state flags
    merged = derive_cumulative_states(merged)

    # Add agent metadata (MG status, etc.) if provided
    if agent_metadata:
        merged["mg_status"] = merged["agent_id"].map(
            lambda aid: agent_metadata.get(str(aid), {}).get("mg_status", "UNKNOWN")
        )
    elif "mg_status" not in merged.columns:
        merged["mg_status"] = "UNKNOWN"

    # Ensure required columns exist
    for col in ["agent_id", "year", "yearly_decision", "elevated", "relocated"]:
        if col not in merged.columns:
            raise ValueError(f"Missing required column after merge: {col}")

    return merged


def load_audit_all_seeds(
    results_dir: Union[str, Path],
    seed_prefix: str = "seed_",
    agent_types: Optional[List[str]] = None,
) -> Dict[str, pd.DataFrame]:
    """Load audit data from all seed directories.

    Parameters
    ----------
    results_dir : str or Path
        Parent directory containing ``seed_42/``, ``seed_123/``, etc.
    seed_prefix : str
        Prefix for seed directories.
    agent_types : list of str, optional
        Which agent types to load.

    Returns
    -------
    dict
        ``{seed_label: DataFrame}`` for each seed.
    """
    results_dir = Path(results_dir)
    seed_dfs = {}

    for seed_dir in sorted(results_dir.iterdir()):
        if seed_dir.is_dir() and seed_dir.name.startswith(seed_prefix):
            try:
                df = load_audit_for_cv(seed_dir, agent_types=agent_types)
                df["seed"] = seed_dir.name
                seed_dfs[seed_dir.name] = df
            except FileNotFoundError:
                continue

    return seed_dfs
