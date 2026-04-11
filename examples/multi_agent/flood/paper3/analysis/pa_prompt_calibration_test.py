from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd
import requests
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[5]
FLOOD_ROOT = Path(__file__).resolve().parents[2]
DATA_PATH = FLOOD_ROOT / "data" / "agent_profiles_balanced.csv"
CONFIG_PATH = FLOOD_ROOT / "config" / "ma_agent_types.yaml"
PROMPT_PATH = FLOOD_ROOT / "config" / "prompts" / "household_owner.txt"
RESULTS_MD_PATH = FLOOD_ROOT / "paper3" / "analysis" / "pa_prompt_calibration_results.md"
RAW_CSV_PATH = FLOOD_ROOT / "paper3" / "analysis" / "tables" / "pa_prompt_calibration_raw.csv"

OLLAMA_URL = "http://localhost:11434/api/generate"
MODEL_DEFAULT = "gemma4:e4b"
TARGET_MEAN = 3.08
LABEL_TO_SCORE = {"VL": 1.0, "L": 2.0, "M": 3.0, "H": 4.0, "VH": 5.0}
SCORE_TO_LABEL = {v: k for k, v in LABEL_TO_SCORE.items()}
EXPECTED_OUTPUT_SCHEMA = """{
  "PA_LABEL": "VL | L | M | H | VH",
  "reasoning": "Brief explanation grounded in the agent profile"
}"""


@dataclass(frozen=True)
class PromptVariant:
    variant_id: str
    name: str
    description: str
    pa_section: str
    role_label: str = "homeowner"
    community_label: str = "community"
    neighborhood_label: str = "neighborhood"
    home_label: str = "home"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_config() -> Dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _extract_baseline_pa_section(criteria_definitions: str) -> str:
    match = re.search(
        r"(?ms)^\s*-\s*PA \(Place Attachment\):.*?(?=\n\s*$|\Z)",
        criteria_definitions,
    )
    if not match:
        raise ValueError("Could not extract baseline PA section from criteria_definitions.")
    return match.group(0).strip()


def _build_variants(baseline_pa_section: str) -> List[PromptVariant]:
    return [
        PromptVariant(
            variant_id="V0",
            name="Baseline",
            description="Current post-fix PA definition from ma_agent_types.yaml.",
            pa_section=baseline_pa_section,
        ),
        PromptVariant(
            variant_id="V1",
            name="Few-Shot Examples",
            description="Adds three worked examples inside the PA calibration block.",
            pa_section="""- PA (Place Attachment): How emotionally attached are you to your home AND COMMUNITY?
Attachment should reflect genuine roots, not just ownership.

  * VL: Recently moved, minimal local ties, would relocate easily
  * L: Established but could relocate without major loss
  * M: Baseline for typical residents; some attachment but pragmatic
  * H: Strong community roots and identity
  * VH: Deeply rooted identity, irreplaceable local heritage

  Place Attachment (PA) examples for calibration:
  * Agent A: 1 generation, recently moved, no community role -> PA=L
  * Agent B: 2 generations, typical suburban ties -> PA=M (baseline)
  * Agent C: 4 generations, family cemetery, church elder -> PA=H
""",
        ),
        PromptVariant(
            variant_id="V2",
            name="Survey Anchor",
            description="Adds a survey-calibrated default-to-medium anchor and counterexample.",
            pa_section="""- PA (Place Attachment): How emotionally attached are you to your home AND COMMUNITY?
Note: Most Passaic Basin homeowners (survey-calibrated) rate PA=M.
Only 15-20% report H+VH. Default to M unless multiple specific anchors
(3+ generations, verified community leadership role, extended family nearby)
push the rating higher.

  * VL: Recently moved, minimal local ties, would relocate easily
  * L: Established but could relocate without major loss
  * M: Typical homeowner baseline; some attachment but pragmatic
  * H: Strong rootedness with multiple concrete anchors
  * VH: Exceptional multigenerational heritage; leaving feels unthinkable
""",
        ),
        PromptVariant(
            variant_id="V3",
            name="Dual Consideration",
            description="Forces stay-vs-leave reasoning before rating.",
            pa_section="""- PA (Place Attachment): How emotionally attached are you to your home AND COMMUNITY?
Before rating PA, explicitly consider both sides:
  (a) 2+ concrete reasons this agent would STAY (attachment evidence)
  (b) 2+ concrete reasons this agent would be OPEN TO LEAVE (pragmatic evidence)
Then assign PA based on whether (a) outweighs (b). If roughly equal, rate M.

  * VL: Clear willingness to relocate; almost no place-based anchors
  * L: Some ties, but pragmatic reasons to leave dominate
  * M: Stay and leave reasons are roughly balanced
  * H: Attachment evidence clearly outweighs pragmatic reasons
  * VH: Overwhelming rootedness, identity, and heritage make leaving nearly impossible
""",
        ),
        PromptVariant(
            variant_id="V4",
            name="Relative Ranking",
            description="Defines PA relative to a neighborhood distribution.",
            pa_section="""- PA (Place Attachment): Rate this agent relative to a reference neighborhood distribution.
  * VL: bottom 10% (least attached in community)
  * L : 10-30% (below typical)
  * M : 30-70% (typical range; most residents here)
  * H : 70-90% (above typical)
  * VH: top 10% (most rooted, multigenerational heritage)
Use the median as the anchor; most agents should be M.
""",
        ),
        PromptVariant(
            variant_id="V5",
            name="Numerical First",
            description="Asks for a continuous 1-5 PA score before label mapping.",
            pa_section="""- PA (Place Attachment): Score PA on a 1-5 continuous scale
(1=not attached, 5=deeply rooted), then map:
  * 1.0-1.5 = VL
  * 1.5-2.5 = L
  * 2.5-3.5 = M
  * 3.5-4.5 = H
  * 4.5-5.0 = VH
Survey mean across the basin is ~3.0 (M).
""",
        ),
        PromptVariant(
            variant_id="V6",
            name="Pragmatic Default",
            description="Frames housing as pragmatic by default unless rooted evidence is strong.",
            pa_section="""- PA (Place Attachment): Most Americans treat housing as an investment, not an identity.
About 85% of homeowners would relocate if circumstances required it. Assume PRAGMATIC
by default; only rate H or VH with concrete multigenerational evidence.

  * VL: Easily relocates; little emotional loss
  * L: Mild attachment, but relocation is acceptable
  * M: Practical baseline; some attachment but relocation remains realistic
  * H: Concrete multigenerational evidence and meaningful local role
  * VH: Rare, exceptional rootedness and identity fusion with place
""",
        ),
        PromptVariant(
            variant_id="V7",
            name="Resident Framing",
            description="Removes homeowner/home/community trigger words where feasible.",
            pa_section="""- PA (Place Attachment): How emotionally rooted is this household resident in the local area?
Rate rootedness from pragmatic mobility to deep place-based identity.

  * VL: Recently arrived, few local ties, relocation would be easy
  * L: Some familiarity, but moving would not feel like a major loss
  * M: Typical resident baseline; moderate local familiarity with pragmatic flexibility
  * H: Strong local roots, repeated family presence, meaningful local role
  * VH: Deeply rooted lineage and identity tied to this area
""",
            role_label="household resident",
            community_label="local area",
            neighborhood_label="nearby area",
            home_label="residence",
        ),
    ]


def _income_bucket(value: Any) -> str:
    text = str(value)
    if "Less than" in text or "$25,000" in text or "$29,999" in text:
        return "low"
    if "$35,000" in text or "$39,999" in text or "$49,999" in text or "$74,999" in text:
        return "mid"
    return "high"


def _select_stratified_sample(df: pd.DataFrame, per_generation: int = 6) -> pd.DataFrame:
    rows: List[pd.Series] = []
    working = df.copy()
    working["generation_bin"] = working["generations"].round().astype(int).clip(lower=1, upper=5)
    working["income_bucket"] = working["income_bracket"].map(_income_bucket)
    working["mg_bucket"] = working["mg"].astype(str)
    working["flood_bucket"] = working["flood_zone"].astype(str)

    for generation in range(1, 6):
        group = working.loc[working["generation_bin"] == generation].copy()
        if len(group) < per_generation:
            raise ValueError(f"Generation bin {generation} has only {len(group)} rows.")

        selected: List[int] = []
        seen_income: set[str] = set()
        seen_mg: set[str] = set()
        seen_flood: set[str] = set()

        while len(selected) < per_generation:
            best_idx: Optional[int] = None
            best_key: Optional[Tuple[Any, ...]] = None
            for idx, candidate in group.iterrows():
                if idx in selected:
                    continue
                novelty = (
                    int(candidate["income_bucket"] not in seen_income),
                    int(candidate["mg_bucket"] not in seen_mg),
                    int(candidate["flood_bucket"] not in seen_flood),
                )
                score = abs(float(candidate["pa_score"]) - TARGET_MEAN)
                key = (sum(novelty), score, -float(candidate["income"]), str(candidate["agent_id"]))
                if best_key is None or key > best_key:
                    best_key = key
                    best_idx = idx
            assert best_idx is not None
            selected.append(best_idx)
            chosen = group.loc[best_idx]
            seen_income.add(chosen["income_bucket"])
            seen_mg.add(chosen["mg_bucket"])
            seen_flood.add(chosen["flood_bucket"])

        rows.extend(group.loc[selected].to_dict("records"))

    sample = pd.DataFrame(rows).sort_values(["generation_bin", "agent_id"]).reset_index(drop=True)
    return sample


def _safe_float(value: Any, default: float = 0.0) -> float:
    if pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _format_flood_experience(row: pd.Series) -> str:
    count = int(_safe_float(row["flood_frequency"], 0))
    if count <= 0:
        return "No direct flood experience."
    recent = row.get("recent_flood_text")
    if pd.isna(recent) or not str(recent).strip():
        return f"{count} prior flood event(s)."
    return f"{count} prior flood event(s), most recently {recent}."


def _render_prompt(row: pd.Series, variant: PromptVariant, template_text: str, baseline_pa: str) -> str:
    criteria = f"""Protection Motivation Theory (PMT) Constructs.

- TP (Threat Perception): Hold constant at your natural baseline for this profile.
- CP (Coping Perception): Hold constant at your natural baseline for this profile.
- SP (Stakeholder Perception): Hold constant at your natural baseline for this profile.
- SC (Social Capital): Hold constant at your natural baseline for this profile.
{variant.pa_section}
"""
    fixed_values = {
        "agent_id": row["agent_id"],
        "income_range": row["income_bracket"],
        "household_size": int(_safe_float(row["household_size"], 1)),
        "residency_generations": int(_safe_float(row["generations"], 1)),
        "flood_zone": row["flood_zone"],
        "flood_experience_summary": _format_flood_experience(row),
        "rcv_building": _safe_float(row["rcv_building"]),
        "rcv_contents": _safe_float(row["rcv_contents"]),
        "elevation_status_text": "not elevated",
        "insurance_status": "do not have" if not bool(row.get("has_insurance")) else "do have",
        "flood_count": int(_safe_float(row["flood_frequency"], 0)),
        "years_since_flood": "N/A" if int(_safe_float(row["flood_frequency"], 0)) == 0 else "unknown",
        "cumulative_damage": _safe_float(row["cumulative_damage"]),
        "cumulative_oop": _safe_float(row["cumulative_oop"]),
        "memory": "Year 1 baseline. No prior simulation memories.",
        "govt_message": "No new policy changes this year.",
        "insurance_message": "No new insurance updates this year.",
        "global_news": "No major flood-related news this year.",
        "flood_proximity_qualifier": "No new local flood events have occurred yet.",
        "social_gossip": "No social signals available.",
        "neighbor_action_summary": "Neighbors have not taken notable actions yet.",
        "current_premium": 1800.0 if bool(row.get("has_insurance")) else 0.0,
        "subsidy_rate": 0.0,
        "elevation_cost_3ft": 45000.0,
        "elevation_cost_5ft": 80000.0,
        "elevation_cost_8ft": 150000.0,
        "elevation_burden_pct": 45000.0 / max(_safe_float(row["income"], 1.0), 1.0) * 100.0,
        "buyout_offer": _safe_float(row["rcv_building"]) * 0.95,
        "insurance_cost_text": "",
        "mg_barrier_text": "",
        "renewal_fatigue_text": "",
        "cost_pressure_text": "",
        "options_text": "Choose only a conceptual action if you need one for context. The focus of this task is PA rating, not action selection.",
        "criteria_definitions": criteria,
        "rating_scale": "VL=Very Low, L=Low, M=Medium, H=High, VH=Very High",
        "response_format": EXPECTED_OUTPUT_SCHEMA,
    }

    prompt = template_text.format(**fixed_values)
    prompt = re.sub(r"(?s)### RELEVANT MEMORIES.*?### CRITICAL RISK ASSESSMENT", "### RELEVANT MEMORIES\nYear 1 baseline. No prior simulation memories.\n\n### CRITICAL RISK ASSESSMENT", prompt)
    prompt = re.sub(r"(?s)### POLICY UPDATES THIS YEAR.*?### WORLD EVENTS", "### POLICY UPDATES THIS YEAR\n- NJ Government (NJDEP Blue Acres): No new policy changes this year.\n- FEMA/NFIP Insurance: No new insurance updates this year.\n\n### WORLD EVENTS", prompt)
    prompt = re.sub(r"(?s)### WORLD EVENTS.*?### LOCAL NEIGHBORHOOD", "### WORLD EVENTS\nNo major flood-related news this year.\n\n### LOCAL NEIGHBORHOOD", prompt)
    prompt = re.sub(r"(?s)### LOCAL NEIGHBORHOOD.*?### FINANCIAL DETAILS", "### LOCAL NEIGHBORHOOD\nNo social signals available.\n\n### FINANCIAL DETAILS", prompt)
    prompt = re.sub(r"(?s)### ADAPTATION OPTIONS.*?### EVALUATION CRITERIA", "### ADAPTATION OPTIONS\nKeep the broader adaptation context in mind, but this calibration task only requires a PA rating.\n\n### EVALUATION CRITERIA", prompt)

    prompt = prompt.replace(baseline_pa, variant.pa_section)
    prompt = prompt.replace("You are a homeowner", f"You are a {variant.role_label}")
    prompt = prompt.replace("homeowner", variant.role_label)
    prompt = prompt.replace("home AND COMMUNITY", f"{variant.home_label} AND {variant.community_label.upper()}")
    prompt = prompt.replace("home and community", f"{variant.home_label} and {variant.community_label}")
    prompt = prompt.replace("community", variant.community_label)
    prompt = prompt.replace("neighborhood", variant.neighborhood_label)
    prompt = prompt.replace("home", variant.home_label)

    calibration_block = f"""

### CALIBRATION TASK
Focus on the profile-specific Place Attachment judgment only.
Return only a JSON object with `PA_LABEL` and `reasoning`.
Use the exact labels VL, L, M, H, VH.
"""
    prompt += calibration_block
    return prompt


def _invoke_ollama(prompt: str, model: str, timeout: int) -> Dict[str, Any]:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "think": False,
        "options": {
            "num_ctx": 16384,
            "num_predict": 512,
            "temperature": 0.2,
            "top_p": 0.9,
            "top_k": 40,
        },
    }
    response = requests.post(OLLAMA_URL, json=payload, timeout=timeout)
    response.raise_for_status()
    return response.json()


def _extract_json_block(text: str) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _parse_pa_label(text: str) -> Tuple[Optional[str], Optional[str]]:
    data = _extract_json_block(text)
    if isinstance(data, dict):
        for key in ("PA_LABEL", "place_attachment", "pa_label", "label"):
            value = data.get(key)
            if isinstance(value, str):
                candidate = value.strip().upper()
                if candidate in LABEL_TO_SCORE:
                    reasoning = data.get("reasoning")
                    return candidate, reasoning if isinstance(reasoning, str) else None

    patterns = [
        r'"PA_LABEL"\s*:\s*"?(VL|L|M|H|VH)"?',
        r"\bPA_LABEL\b\s*[:=]\s*(VL|L|M|H|VH)\b",
        r"\bplace_attachment\b\s*[:=]\s*(VL|L|M|H|VH)\b",
        r"\b(VL|L|M|H|VH)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1).upper(), None
    return None, None


def _rank(values: Iterable[float]) -> pd.Series:
    return pd.Series(list(values), dtype="float64").rank(method="average")


def _spearman(x: Iterable[float], y: Iterable[float]) -> float:
    x_series = pd.Series(list(x), dtype="float64")
    y_series = pd.Series(list(y), dtype="float64")
    valid = ~(x_series.isna() | y_series.isna())
    if valid.sum() < 2:
        return float("nan")
    x_valid = x_series[valid]
    y_valid = y_series[valid]
    if x_valid.nunique(dropna=True) < 2 or y_valid.nunique(dropna=True) < 2:
        return float("nan")
    return float(_rank(x_valid).corr(_rank(y_valid), method="pearson"))


def _compute_variant_metrics(df: pd.DataFrame) -> Dict[str, Any]:
    parsed = df.loc[df["parse_ok"]].copy()
    values = parsed["pa_score_pred"].tolist()
    mean = statistics.fmean(values) if values else float("nan")
    sd = statistics.stdev(values) if len(values) > 1 else 0.0
    corr_ground = _spearman(parsed["pa_score_pred"], parsed["pa_score_ground_truth"]) if len(parsed) > 1 else float("nan")
    corr_generations = _spearman(parsed["pa_score_pred"], parsed["generations"]) if len(parsed) > 1 else float("nan")
    ceiling_rate = float((parsed["pa_score_pred"] >= 4).mean()) if len(parsed) else float("nan")

    score = (
        0.30 * (1 - min(abs(mean - TARGET_MEAN) / 2.0, 1.0))
        + 0.20 * min(sd / 1.0, 1.0)
        + 0.20 * max(0.0, 0.0 if math.isnan(corr_ground) else corr_ground)
        + 0.20 * max(0.0, 0.0 if math.isnan(corr_generations) else corr_generations)
        + 0.10 * max(0.0, 1 - (0.0 if math.isnan(ceiling_rate) else ceiling_rate) / 0.5)
    )

    distribution = {
        label: int((parsed["pa_label"] == label).sum())
        for label in ("VL", "L", "M", "H", "VH")
    }
    return {
        "n_responses": int(len(parsed)),
        "mean": mean,
        "sd": sd,
        "corr_ground_truth": corr_ground,
        "corr_generations": corr_generations,
        "ceiling_rate": ceiling_rate,
        "composite_score": score,
        "distribution": distribution,
    }


def _format_pct(count: int, total: int) -> str:
    if total == 0:
        return "0 (0.0%)"
    return f"{count} ({100.0 * count / total:.1f}%)"


def _meets_success_criteria(row: pd.Series) -> bool:
    corr_ground = 0.0 if pd.isna(row["corr_ground_truth"]) else float(row["corr_ground_truth"])
    corr_generations = 0.0 if pd.isna(row["corr_generations"]) else float(row["corr_generations"])
    return (
        abs(float(row["mean"]) - TARGET_MEAN) <= 0.3
        and float(row["sd"]) > 0.7
        and corr_ground >= 0.3
        and float(row["ceiling_rate"]) < 0.5
        and corr_generations >= 0.2
    )


def _fmt_metric(value: Any, pct: bool = False) -> str:
    if pd.isna(value):
        value = 0.0
    value = float(value)
    return f"{100.0 * value:.1f}%" if pct else f"{value:.2f}"


def _write_markdown(
    results_md_path: Path,
    raw_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    variants: List[PromptVariant],
    model: str,
) -> None:
    winner = metrics_df.sort_values("composite_score", ascending=False).iloc[0]
    winner_row = winner.to_dict()
    variant_lookup = {variant.variant_id: variant for variant in variants}
    qualified = metrics_df.loc[metrics_df.apply(_meets_success_criteria, axis=1)].copy()
    lines: List[str] = []
    lines.append("# PA Prompt Calibration Results")
    lines.append("")
    lines.append(f"Model: `{model}` via direct Ollama API with top-level `think=false`.")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(
        f"Winner: **{winner_row['variant_id']} {winner_row['name']}** "
        f"(composite score `{winner_row['composite_score']:.3f}`)."
    )
    if qualified.empty:
        lines.append("No variant met all hard success criteria.")
    else:
        qualified_labels = ", ".join(
            f"{row['variant_id']} {row['name']}" for _, row in qualified.iterrows()
        )
        lines.append(f"Variants meeting all hard success criteria: {qualified_labels}.")
    lines.append("")
    lines.append("## Comparison Table")
    lines.append("")
    lines.append("| Variant | Mean | SD | Spearman vs `pa_score` | Spearman vs `generations` | Ceiling H+VH | Parsed N | Composite | Hard Criteria |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---|")
    for _, row in metrics_df.iterrows():
        lines.append(
            f"| {row['variant_id']} {row['name']} | {_fmt_metric(row['mean'])} | {_fmt_metric(row['sd'])} | "
            f"{_fmt_metric(row['corr_ground_truth'])} | {_fmt_metric(row['corr_generations'])} | "
            f"{_fmt_metric(row['ceiling_rate'], pct=True)} | {int(row['n_responses'])} | {row['composite_score']:.3f} | "
            f"{'PASS' if _meets_success_criteria(row) else 'FAIL'} |"
        )
    lines.append("")
    lines.append("## Distribution Details")
    lines.append("")
    for _, row in metrics_df.iterrows():
        total = int(row["n_responses"])
        lines.append(f"### {row['variant_id']} {row['name']}")
        lines.append("")
        lines.append(variant_lookup[row["variant_id"]].description)
        lines.append("")
        lines.append(
            "Distribution: "
            + ", ".join(
                f"{label}={_format_pct(int(row[f'dist_{label}']), total)}"
                for label in ("VL", "L", "M", "H", "VH")
            )
        )
        lines.append("")
        sample_rows = raw_df.loc[(raw_df["variant_id"] == row["variant_id"]) & (raw_df["parse_ok"])].head(4)
        if sample_rows.empty:
            lines.append("No parsed responses for this variant.")
            lines.append("")
            continue
        lines.append("Sample responses:")
        lines.append("")
        for _, sample in sample_rows.iterrows():
            reason = str(sample["reasoning"] or "").strip().replace("\n", " ")
            if not reason:
                reason = str(sample["raw_response"]).strip().replace("\n", " ")
            reason = reason[:280]
            lines.append(
                f"- `{sample['agent_id']}` gen={int(sample['generations'])}, "
                f"GT={sample['pa_score_ground_truth']:.2f}, pred={sample['pa_label']}: {reason}"
            )
        lines.append("")
    lines.append("## Recommendation")
    lines.append("")
    if not qualified.empty:
        lines.append(
            f"{qualified.iloc[0]['variant_id']} is the first variant that satisfies the hard criteria. "
            "Apply it to production and run the planned 10-agent MA smoke test."
        )
    elif float(winner_row["composite_score"]) > 0.6:
        lines.append(
            f"{winner_row['variant_id']} clears the composite score threshold but still fails at least one hard criterion, "
            "most importantly the required positive ground-truth correlation. Treat this as only a partial calibration improvement."
        )
    else:
        lines.append(
            "No variant exceeded the 0.6 target. This run supports documenting a persistent Gemma 4 e4b "
            "PA calibration bias and treating the calibration experiment itself as evidence."
        )
    lines.append("")
    results_md_path.write_text("\n".join(lines), encoding="utf-8")


def run(model: str, timeout: int, sleep_s: float) -> None:
    _ = str(PROJECT_ROOT)
    config = _load_config()
    template_text = _read_text(PROMPT_PATH)
    baseline_pa = _extract_baseline_pa_section(config["shared"]["criteria_definitions"])
    variants = _build_variants(baseline_pa)

    df = pd.read_csv(DATA_PATH)
    sample = _select_stratified_sample(df, per_generation=6)

    rows: List[Dict[str, Any]] = []
    total_calls = len(sample) * len(variants)
    call_index = 0
    for variant in variants:
        for _, agent in sample.iterrows():
            call_index += 1
            prompt = _render_prompt(agent, variant, template_text, baseline_pa)
            started = time.time()
            error = ""
            raw_response = ""
            prompt_tokens = None
            eval_tokens = None
            try:
                response_json = _invoke_ollama(prompt, model=model, timeout=timeout)
                raw_response = str(response_json.get("response", ""))
                prompt_tokens = response_json.get("prompt_eval_count")
                eval_tokens = response_json.get("eval_count")
            except Exception as exc:  # noqa: BLE001
                error = f"{type(exc).__name__}: {exc}"

            pa_label, reasoning = _parse_pa_label(raw_response)
            rows.append(
                {
                    "variant_id": variant.variant_id,
                    "variant_name": variant.name,
                    "agent_id": agent["agent_id"],
                    "income_bracket": agent["income_bracket"],
                    "income": _safe_float(agent["income"]),
                    "mg": bool(agent["mg"]),
                    "flood_zone": agent["flood_zone"],
                    "generations": int(_safe_float(agent["generations"], 1)),
                    "pa_score_ground_truth": _safe_float(agent["pa_score"]),
                    "pa_label": pa_label,
                    "pa_score_pred": LABEL_TO_SCORE.get(pa_label),
                    "parse_ok": pa_label is not None,
                    "reasoning": reasoning,
                    "raw_response": raw_response,
                    "error": error,
                    "latency_s": round(time.time() - started, 3),
                    "prompt_eval_count": prompt_tokens,
                    "eval_count": eval_tokens,
                }
            )
            print(
                f"[{call_index:03d}/{total_calls}] {variant.variant_id} {agent['agent_id']} -> "
                f"{pa_label or 'UNPARSED'}"
            )
            if sleep_s > 0:
                time.sleep(sleep_s)

    raw_df = pd.DataFrame(rows)
    RAW_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    raw_df.to_csv(RAW_CSV_PATH, index=False, encoding="utf-8")

    metrics_rows: List[Dict[str, Any]] = []
    for variant in variants:
        variant_df = raw_df.loc[raw_df["variant_id"] == variant.variant_id].copy()
        metrics = _compute_variant_metrics(variant_df)
        metrics_rows.append(
            {
                "variant_id": variant.variant_id,
                "name": variant.name,
                **metrics,
                **{f"dist_{label}": metrics["distribution"][label] for label in ("VL", "L", "M", "H", "VH")},
            }
        )
    metrics_df = pd.DataFrame(metrics_rows).sort_values("composite_score", ascending=False).reset_index(drop=True)
    _write_markdown(RESULTS_MD_PATH, raw_df, metrics_df, variants, model=model)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PA prompt calibration against Ollama.")
    parser.add_argument("--model", default=MODEL_DEFAULT)
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--sleep-s", type=float, default=0.0)
    args = parser.parse_args()
    run(model=args.model, timeout=args.timeout, sleep_s=args.sleep_s)


if __name__ == "__main__":
    main()
