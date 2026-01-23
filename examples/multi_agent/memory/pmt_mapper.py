from typing import Tuple

import pandas as pd


def get_pmt_scores(agent_row: pd.Series) -> Tuple[float, float, float]:
    """Return (sc_score, pa_score, sp_score) with defaults."""
    sc_score = float(agent_row.get("sc_score", 3.0))
    pa_score = float(agent_row.get("pa_score", 3.0))
    sp_score = float(agent_row.get("sp_score", 3.0))
    return sc_score, pa_score, sp_score
