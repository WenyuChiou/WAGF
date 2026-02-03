"""
Paper 3 — C&V Runner: Master orchestration for Calibration & Validation.

Three modes:
    icc       — Psychometric ICC probing (requires LLM, no experiment data)
    posthoc   — Post-hoc L1/L2 validation (no LLM, requires experiment CSVs)
    aggregate — Cross-seed comparison table (no LLM, requires posthoc reports)

Usage:
    # ICC probing (run AFTER experiment finishes, uses same LLM)
    python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30

    # Post-hoc validation for one seed
    python paper3/run_cv.py --mode posthoc --trace-dir paper3/results/seed_42/

    # Aggregate across seeds
    python paper3/run_cv.py --mode aggregate --results-dir paper3/results/
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

# Ensure project root is on sys.path (find by marker directory)
def _find_project_root() -> Path:
    """Walk upward from this file to find the directory containing ``broker/``."""
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "broker").is_dir():
            return current
        current = current.parent
    # Fallback to fixed depth
    return Path(__file__).resolve().parents[4]


PROJECT_ROOT = _find_project_root()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Also add the multi-agent flood dir so ``paper3`` is importable
FLOOD_DIR = Path(__file__).resolve().parent.parent
if str(FLOOD_DIR) not in sys.path:
    sys.path.insert(0, str(FLOOD_DIR))

from broker.validators.calibration.cv_runner import CVRunner, CVReport
from broker.validators.calibration.psychometric_battery import (
    PsychometricBattery,
    ProbeResponse,
    Vignette,
)

# Local imports
from paper3.analysis.audit_to_cv import load_audit_for_cv, load_audit_all_seeds
from paper3.analysis.empirical_benchmarks import compare_with_benchmarks


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VIGNETTE_DIR = FLOOD_DIR / "paper3" / "configs" / "vignettes"
DEFAULT_MODEL = "gemma3:4b"
DEFAULT_REPLICATES = 30

# PMT response format template (matches ma_agent_types.yaml household format)
RESPONSE_FORMAT_HINT = """\
Respond ONLY with valid JSON. Pick exactly ONE value for each label.
{
  "TP_LABEL": "VL or L or M or H or VH",
  "CP_LABEL": "VL or L or M or H or VH",
  "decision": "your chosen action name",
  "reasoning": "Brief explanation of your decision"
}"""

RATING_SCALE = "VL=Very Low, L=Low, M=Medium, H=High, VH=Very High"

CRITERIA_DEFS = """\
- TP (Threat Perception): How serious do you perceive the flood risk?
- CP (Coping Perception): How confident are you that you can take effective protective action?"""

# Owner action options
OWNER_OPTIONS = """\
Choose ONE primary action:
1. buy_insurance — Purchase NFIP flood insurance
2. elevate_house — Elevate your home above Base Flood Elevation
3. buyout_program — Accept the Blue Acres government buyout (irreversible)
4. do_nothing — Take no protective action this year"""

# Renter action options
RENTER_OPTIONS = """\
Choose ONE primary action:
1. buy_contents_insurance — Purchase contents-only flood insurance
2. relocate — Move to a different area
3. do_nothing — Take no protective action this year"""


# ---------------------------------------------------------------------------
# LLM invocation (lightweight, for ICC probing only)
# ---------------------------------------------------------------------------

def create_probe_invoke(
    model: str,
    temperature: float = 0.7,
) -> Callable[[str], Tuple[str, Any]]:
    """Create a lightweight LLM invoke function for ICC probing.

    Uses the same Ollama direct API as the main experiment.
    """
    import requests

    url = "http://localhost:11434/api/generate"

    def invoke(prompt: str) -> Tuple[str, bool]:
        data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "keep_alive": "120m",
            "options": {
                "temperature": temperature,
                "num_predict": 256,
                "num_ctx": 4096,
            },
        }
        try:
            resp = requests.post(url, json=data, timeout=90)
            if resp.status_code == 200:
                content = resp.json().get("response", "")
                return content, True
            return "", False
        except Exception:
            return "", False

    return invoke


def parse_probe_response(raw: str) -> Dict[str, str]:
    """Parse LLM response into structured fields.

    Handles both clean JSON and JSON embedded in markdown/text.
    Uses balanced-brace extraction to support nested JSON objects.
    """
    # Try direct JSON parse first
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Extract JSON from markdown code block
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Extract first balanced { ... } block (handles nested braces)
    json_str = _extract_balanced_braces(raw)
    if json_str:
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            pass

    return {}


def _extract_balanced_braces(text: str) -> Optional[str]:
    """Extract the first balanced ``{...}`` substring from *text*."""
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


# ---------------------------------------------------------------------------
# Mode 1: ICC Probing
# ---------------------------------------------------------------------------

def build_probe_prompt(
    archetype: Dict[str, Any],
    vignette: Vignette,
) -> str:
    """Build a prompt for ICC probing from archetype + vignette.

    Mirrors the structure of the actual experiment prompts but substitutes
    the vignette scenario for the real environment.
    """
    persona = archetype["persona"]
    atype = archetype["agent_type"]
    memory = archetype.get("memory_seed", "No prior memories.")
    state = archetype.get("state_overrides", {})

    # Base identity
    if atype == "household_owner":
        identity = f"You are a homeowner in the Passaic River Basin, New Jersey."
        options = OWNER_OPTIONS
    else:
        identity = f"You are a renter in the Passaic River Basin, New Jersey."
        options = RENTER_OPTIONS

    # Build situation section
    situation_lines = [f"- Income: {persona.get('income_range', 'Unknown')}"]
    situation_lines.append(f"- Household Size: {persona.get('household_size', 'Unknown')} people")
    if atype == "household_owner":
        situation_lines.append(f"- Property Value: ${persona.get('rcv_building', 0):,.0f}")
    situation_lines.append(f"- Flood Zone: {persona.get('flood_zone', 'Unknown')}")
    situation_lines.append(f"- Flood Experience: {persona.get('flood_experience_summary', 'None')}")
    situation_lines.append(f"- Insurance: You currently {persona.get('insurance_status', 'do not have')} flood insurance.")

    situation = "\n".join(situation_lines)

    # Vignette scenario replaces the normal environment update
    prompt = f"""{identity}

### YOUR SITUATION
{situation}

### SCENARIO (for this assessment)
{vignette.scenario}

### RELEVANT MEMORIES
{memory}

### ADAPTATION OPTIONS
{options}

### EVALUATION CRITERIA
{CRITERIA_DEFS}

Rating Scale: {RATING_SCALE}

Based on the scenario, your situation, and your memories, evaluate the threat and your coping capacity, then choose an action.
{RESPONSE_FORMAT_HINT}"""

    return prompt


def run_icc_probing(
    archetypes_path: str | Path,
    model: str = DEFAULT_MODEL,
    replicates: int = DEFAULT_REPLICATES,
    output_dir: str | Path = "paper3/results/cv",
    governed: bool = True,
) -> None:
    """Run ICC psychometric probing.

    Parameters
    ----------
    archetypes_path : Path
        Path to icc_archetypes.yaml.
    model : str
        Ollama model name.
    replicates : int
        Number of replicates per archetype-vignette pair.
    output_dir : Path
        Where to save results.
    governed : bool
        Whether to apply SAGE governance to responses.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load archetypes
    with open(archetypes_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    archetypes = config.get("archetypes", {})
    probing_config = config.get("probing", {})
    replicates = probing_config.get("replicates", replicates)
    temperature = probing_config.get("temperature", 0.7)

    # Load vignettes
    battery = PsychometricBattery(vignette_dir=VIGNETTE_DIR)
    vignettes = battery.load_vignettes()
    print(f"Loaded {len(vignettes)} vignettes, {len(archetypes)} archetypes")
    print(f"Total probes: {len(vignettes)} x {len(archetypes)} x {replicates} = "
          f"{len(vignettes) * len(archetypes) * replicates}")

    # Create LLM invoke function
    invoke = create_probe_invoke(model, temperature=temperature)

    # Run probing
    total = len(archetypes) * len(vignettes) * replicates
    completed = 0
    failed = 0

    for arch_name, arch_data in archetypes.items():
        for vignette in vignettes:
            prompt = build_probe_prompt(arch_data, vignette)

            for rep in range(1, replicates + 1):
                raw, success = invoke(prompt)
                completed += 1

                if not success or not raw:
                    failed += 1
                    print(f"  [{completed}/{total}] FAILED: {arch_name} x {vignette.id} rep {rep}")
                    continue

                parsed = parse_probe_response(raw)

                # Extract construct labels (clean multi-value like "H | VH")
                tp_raw = parsed.get("TP_LABEL", parsed.get("tp_label", "M"))
                cp_raw = parsed.get("CP_LABEL", parsed.get("cp_label", "M"))
                tp = tp_raw.split("|")[0].split("/")[0].strip().upper()
                cp = cp_raw.split("|")[0].split("/")[0].strip().upper()
                # Clean decision (remove leading numbers like "1. ")
                decision = re.sub(r"^\d+\.\s*", "", str(parsed.get("decision", "do_nothing"))).lower().strip()
                reasoning = parsed.get("reasoning", "")

                response = ProbeResponse(
                    vignette_id=vignette.id,
                    archetype=arch_name,
                    replicate=rep,
                    tp_label=tp,
                    cp_label=cp,
                    decision=decision,
                    reasoning=reasoning,
                    governed=governed,
                    raw_response=raw,
                )
                battery.add_response(response)

                if completed % 50 == 0 or completed == total:
                    print(f"  [{completed}/{total}] {arch_name} x {vignette.id} "
                          f"rep {rep}: TP={tp}, CP={cp}, action={decision}")

                # Incremental save every 500 calls (prevent data loss on crash)
                if completed % 500 == 0:
                    try:
                        inc_df = battery.responses_to_dataframe()
                        if not inc_df.empty:
                            inc_path = output_dir / "icc_responses_partial.csv"
                            inc_df.to_csv(inc_path, index=False)
                    except Exception:
                        pass  # Non-critical

    # Compute results
    print(f"\nProbing complete. {completed - failed}/{completed} successful.")
    report = battery.compute_full_report(governed=governed)

    # Print summary
    print("\n=== ICC Probing Results ===")
    if report.overall_tp_icc:
        icc_tp = report.overall_tp_icc.icc_value
        print(f"  TP ICC(2,1): {icc_tp:.3f} "
              f"[{report.overall_tp_icc.ci_lower:.3f}, {report.overall_tp_icc.ci_upper:.3f}]"
              f" {'PASS' if icc_tp >= 0.60 else 'FAIL'}")
    if report.overall_cp_icc:
        icc_cp = report.overall_cp_icc.icc_value
        print(f"  CP ICC(2,1): {icc_cp:.3f} "
              f"[{report.overall_cp_icc.ci_lower:.3f}, {report.overall_cp_icc.ci_upper:.3f}]"
              f" {'PASS' if icc_cp >= 0.60 else 'FAIL'}")
    if report.consistency:
        print(f"  Cronbach's alpha: {report.consistency.alpha:.3f}")

    # Effect size (eta-squared)
    if report.tp_effect_size:
        eta_tp = report.tp_effect_size.eta_squared
        print(f"  TP eta^2: {eta_tp:.3f} "
              f"{'PASS' if eta_tp >= 0.25 else 'FAIL'} (target >= 0.25)")
    if report.cp_effect_size:
        eta_cp = report.cp_effect_size.eta_squared
        print(f"  CP eta^2: {eta_cp:.3f}")

    # Convergent validity
    if report.convergent_validity:
        cv = report.convergent_validity
        print(f"  Convergent validity (TP vs severity): rho={cv.spearman_rho:.3f}, "
              f"p={cv.p_value:.4f} (n={cv.n_observations})")

    # TP-CP discriminant
    if report.tp_cp_discriminant != 0.0:
        disc = report.tp_cp_discriminant
        warn = " WARNING: constructs not discriminated" if abs(disc) > 0.8 else ""
        print(f"  TP-CP discriminant r: {disc:.3f}{warn}")

    for vr in report.vignette_reports:
        print(f"\n  Vignette: {vr.vignette_id} ({vr.severity})")
        print(f"    Responses: {vr.n_responses}")
        print(f"    Coherence: {vr.coherence_rate:.1%}")
        print(f"    Incoherence: {vr.incoherence_rate:.1%}")
        if vr.tp_icc:
            print(f"    TP ICC: {vr.tp_icc.icc_value:.3f}")
        if vr.cp_icc:
            print(f"    CP ICC: {vr.cp_icc.icc_value:.3f}")
        print(f"    Decision agreement (Fleiss' kappa): {vr.decision_agreement:.3f}")

    # Save report
    report_dict = report.to_dict()
    report_dict["metadata"] = {
        "model": model,
        "replicates": replicates,
        "n_archetypes": len(archetypes),
        "n_vignettes": len(vignettes),
        "total_probes": completed,
        "failed_probes": failed,
        "governed": governed,
    }

    report_path = output_dir / "icc_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=2, default=str)
    print(f"\nReport saved: {report_path}")

    # Save raw responses as CSV for analysis
    responses_df = battery.responses_to_dataframe()
    if not responses_df.empty:
        responses_path = output_dir / "icc_responses.csv"
        responses_df.to_csv(responses_path, index=False)
        print(f"Raw responses: {responses_path}")


# ---------------------------------------------------------------------------
# Mode 2: Post-Hoc Validation
# ---------------------------------------------------------------------------

def run_posthoc(
    trace_dir: str | Path,
    output_dir: Optional[str | Path] = None,
    start_year: int = 2,
) -> CVReport:
    """Run post-hoc C&V on experiment output from one seed.

    Parameters
    ----------
    trace_dir : Path
        Directory containing audit CSVs (e.g., paper3/results/seed_42/).
    output_dir : Path, optional
        Where to save report. Default: trace_dir/cv/.
    start_year : int
        First year to include in validation.

    Returns
    -------
    CVReport
    """
    trace_dir = Path(trace_dir)
    if output_dir is None:
        output_dir = trace_dir / "cv"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading audit data from: {trace_dir}")
    df = load_audit_for_cv(trace_dir)
    print(f"  Loaded {len(df)} observations, {df['agent_id'].nunique()} agents, "
          f"years {df['year'].min()}-{df['year'].max()}")

    # Initialize CVRunner (explicit mode, PMT framework)
    runner = CVRunner(
        framework="pmt",
        ta_col="threat_appraisal",
        ca_col="coping_appraisal",
        decision_col="yearly_decision",
        reasoning_col="reasoning",
        group="primary",
        start_year=start_year,
    )

    # Run L1 + L2
    print("Running Level 1 (CACR, R_H, EBE) + Level 2 (BRC)...")
    report = runner.run_posthoc(df=df, levels=[1, 2])

    # Also run BRC explicitly (may not be in plan-based routing)
    if report.brc is None:
        try:
            report.brc = runner.run_brc(df=df)
        except (KeyError, ValueError) as e:
            print(f"  BRC computation failed (data issue): {e}")
        except AttributeError as e:
            print(f"  BRC computation failed (missing framework method): {e}")

    # Print summary
    print("\n=== Post-Hoc C&V Results ===")
    summary = report.summary
    for k, v in summary.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")

    # Rename BRC → GCR (Governance Concordance Rate) in output
    if report.brc is not None:
        brc_val = report.brc.brc if hasattr(report.brc, 'brc') else report.brc
        print(f"\n  GCR (Governance Concordance Rate): {brc_val:.3f} "
              f"(internal PMT concordance, target >= 0.90)")

    # Run empirical benchmark comparison → EPI (primary L2 metric)
    print("\nRunning EPI (Empirical Plausibility Index)...")
    bench_report = compare_with_benchmarks(df)
    epi = bench_report.plausibility_score
    epi_pass = epi >= 0.60
    print(f"  EPI: {epi:.1%} "
          f"({bench_report.n_within_range}/{bench_report.n_total} benchmarks within range) "
          f"{'PASS' if epi_pass else 'FAIL'} (threshold >= 0.60)")

    for comp in bench_report.comparisons:
        status = "OK" if comp.within_range else "OUT"
        print(f"  [{status}] {comp.benchmark_name}: "
              f"observed={comp.observed:.3f}, "
              f"expected=[{comp.expected_low:.2f}, {comp.expected_high:.2f}]")

    # Save reports
    report.save_json(output_dir / "posthoc_report.json")

    bench_path = output_dir / "benchmark_report.json"
    with open(bench_path, "w", encoding="utf-8") as f:
        json.dump(bench_report.to_dict(), f, indent=2, default=str)

    bench_report.to_dataframe().to_csv(
        output_dir / "benchmark_comparison.csv", index=False
    )

    # R5-B: Convergent validity — TP ordinal vs objective flood risk
    print("\nRunning convergent validity (TP vs objective risk)...")
    convergent_validity = {}
    try:
        from scipy import stats as sp_stats

        tp_col = "ta_level" if "ta_level" in df.columns else "threat_appraisal"
        tp_ordinal_map = {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}

        cv_df = df.copy()
        cv_df["tp_ordinal"] = cv_df[tp_col].map(tp_ordinal_map)

        # TP vs flood_depth_ft
        depth_col = None
        for col in ["flood_depth_ft", "flood_depth", "depth_ft"]:
            if col in cv_df.columns:
                depth_col = col
                break

        if depth_col and cv_df["tp_ordinal"].notna().sum() >= 5:
            valid = cv_df.dropna(subset=["tp_ordinal", depth_col])
            if len(valid) >= 5:
                rho_depth, p_depth = sp_stats.spearmanr(
                    valid["tp_ordinal"].values, valid[depth_col].values
                )
                convergent_validity["tp_vs_flood_depth"] = {
                    "spearman_rho": round(float(rho_depth), 4),
                    "p_value": round(float(p_depth), 6),
                    "n": int(len(valid)),
                    "column": depth_col,
                }
                print(f"  TP vs flood_depth: rho={rho_depth:.3f}, p={p_depth:.4f}")
            else:
                print("  TP vs flood_depth: insufficient data")
        else:
            print("  TP vs flood_depth: column not found or insufficient data")

        # TP vs cumulative_damage (if available)
        damage_col = None
        for col in ["cumulative_damage", "damage_cost", "total_damage"]:
            if col in cv_df.columns:
                damage_col = col
                break

        if damage_col and cv_df["tp_ordinal"].notna().sum() >= 5:
            valid = cv_df.dropna(subset=["tp_ordinal", damage_col])
            if len(valid) >= 5:
                rho_dmg, p_dmg = sp_stats.spearmanr(
                    valid["tp_ordinal"].values, valid[damage_col].values
                )
                convergent_validity["tp_vs_cumulative_damage"] = {
                    "spearman_rho": round(float(rho_dmg), 4),
                    "p_value": round(float(p_dmg), 6),
                    "n": int(len(valid)),
                    "column": damage_col,
                }
                print(f"  TP vs {damage_col}: rho={rho_dmg:.3f}, p={p_dmg:.4f}")
    except ImportError:
        print("  scipy not available — skipping convergent validity")
    except Exception as e:
        print(f"  Convergent validity failed: {e}")

    # Save convergent validity results to JSON alongside other reports
    if convergent_validity:
        cv_path = output_dir / "convergent_validity.json"
        try:
            with open(cv_path, "w", encoding="utf-8") as f:
                json.dump(convergent_validity, f, indent=2)
            print(f"  Convergent validity saved to: {cv_path}")
        except IOError as e:
            print(f"  WARNING: Failed to save convergent validity: {e}")

    print(f"\nReports saved to: {output_dir}")
    return report


# ---------------------------------------------------------------------------
# Mode 3: Aggregate
# ---------------------------------------------------------------------------

def run_aggregate(
    results_dir: str | Path,
    output_dir: Optional[str | Path] = None,
) -> pd.DataFrame:
    """Aggregate C&V reports across seeds.

    Parameters
    ----------
    results_dir : Path
        Parent directory containing seed_*/ subdirectories.
    output_dir : Path, optional
        Where to save aggregate table. Default: results_dir/cv/.

    Returns
    -------
    DataFrame
        Comparison table with one row per seed.
    """
    results_dir = Path(results_dir)
    if output_dir is None:
        output_dir = results_dir / "cv"
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load all post-hoc reports
    reports: Dict[str, CVReport] = {}
    for seed_dir in sorted(results_dir.iterdir()):
        if not seed_dir.is_dir() or not seed_dir.name.startswith("seed_"):
            continue
        report_path = seed_dir / "cv" / "posthoc_report.json"
        if not report_path.exists():
            # Try running post-hoc for this seed
            print(f"No report found for {seed_dir.name}, running post-hoc...")
            try:
                report = run_posthoc(seed_dir)
                reports[seed_dir.name] = report
            except Exception as e:
                print(f"  Failed: {e}")
                continue
        else:
            # Load existing report
            with open(report_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Reconstruct minimal CVReport for summary
            report = CVReport(metadata=data.get("metadata", {}))
            # Populate summary fields from saved data
            if "level1_micro" in data:
                from broker.validators.calibration.micro_validator import MicroReport
                report.micro = MicroReport(
                    cacr=data["level1_micro"].get("cacr", 0),
                    egs=data["level1_micro"].get("egs", 0),
                    n_observations=data["level1_micro"].get("n_observations", 0),
                )
            if "level2_brc" in data:
                from broker.validators.calibration.micro_validator import BRCResult
                report.brc = BRCResult(
                    brc=data["level2_brc"].get("brc", 0),
                    concordant=data["level2_brc"].get("concordant", 0),
                    total=data["level2_brc"].get("total", 0),
                )
            if "level1_rh" in data:
                report.rh_metrics = data["level1_rh"]
            reports[seed_dir.name] = report

    if not reports:
        print("No seed reports found.")
        return pd.DataFrame()

    # Build comparison table
    comparison = CVRunner.compare_groups(reports)

    # Compute aggregate statistics
    print(f"\n=== Aggregate C&V Across {len(reports)} Seeds ===")
    numeric_cols = comparison.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        vals = comparison[col].dropna()
        if len(vals) > 0:
            print(f"  {col}: {vals.mean():.3f} +/- {vals.std():.3f} "
                  f"[{vals.min():.3f}, {vals.max():.3f}]")

    # Save
    comparison.to_csv(output_dir / "aggregate_cv_table.csv", index=False)

    # Save summary stats
    summary_stats = {}
    for col in numeric_cols:
        vals = comparison[col].dropna()
        if len(vals) > 0:
            summary_stats[col] = {
                "mean": round(float(vals.mean()), 4),
                "std": round(float(vals.std()), 4),
                "min": round(float(vals.min()), 4),
                "max": round(float(vals.max()), 4),
                "n_seeds": int(len(vals)),
            }

    with open(output_dir / "aggregate_stats.json", "w", encoding="utf-8") as f:
        json.dump(summary_stats, f, indent=2)

    print(f"\nAggregate results saved to: {output_dir}")
    return comparison


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Paper 3 — C&V Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--mode",
        choices=["icc", "posthoc", "aggregate"],
        required=True,
        help="Validation mode",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Ollama model for ICC probing (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--replicates",
        type=int,
        default=DEFAULT_REPLICATES,
        help=f"ICC replicates per archetype-vignette (default: {DEFAULT_REPLICATES})",
    )
    parser.add_argument(
        "--trace-dir",
        type=str,
        help="Path to seed output directory (posthoc mode)",
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        help="Path to results directory (aggregate mode)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        help="Output directory for reports",
    )
    parser.add_argument(
        "--archetypes",
        type=str,
        default=str(Path(__file__).parent / "configs" / "icc_archetypes.yaml"),
        help="Path to ICC archetypes YAML",
    )
    parser.add_argument(
        "--start-year",
        type=int,
        default=2,
        help="First year to include in post-hoc analysis (default: 2)",
    )

    args = parser.parse_args()

    if args.mode == "icc":
        run_icc_probing(
            archetypes_path=args.archetypes,
            model=args.model,
            replicates=args.replicates,
            output_dir=args.output_dir or "paper3/results/cv",
        )

    elif args.mode == "posthoc":
        if not args.trace_dir:
            parser.error("--trace-dir is required for posthoc mode")
        run_posthoc(
            trace_dir=args.trace_dir,
            output_dir=args.output_dir,
            start_year=args.start_year,
        )

    elif args.mode == "aggregate":
        if not args.results_dir:
            parser.error("--results-dir is required for aggregate mode")
        run_aggregate(
            results_dir=args.results_dir,
            output_dir=args.output_dir,
        )


if __name__ == "__main__":
    main()
