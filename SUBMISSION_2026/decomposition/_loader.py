"""CANONICAL LOADER for the irrigation post-treatment-conditioning decomposition.

Every estimator in this campaign must import this module so that all of them load,
filter, and count the corpus IDENTICALLY. Nothing here has side effects on import.

WHAT THIS MODULE DELIBERATELY DOES NOT DO
  * It does not drop rows. If a row has an empty appraisal label, that is a fact about
    the corpus and is surfaced by `label_missing_share`, not silently swallowed.
    (Note: this is a DIFFERENT convention from the prior-art scripts
    SUBMISSION_2026/evidence/appraisal_composition.py and gate0_signal_floor.py, which
    `continue` past rows with an empty construct label. Those scripts read the AUDIT
    csv, where blank labels do occur; this module's primary file is simulation_log.csv.
    Any divergence between the two is reported, never absorbed.)
  * It does not repair, interpolate, or infer missing runs. A missing directory or file
    raises. Silence is the failure mode this whole analysis exists to catch.

SIGN CONVENTIONS (stated in words, because every downstream table depends on them)
  * `ibr`            higher = MORE decisions that claimed high water scarcity nevertheless
                     increased their diversion request. Higher is WORSE behaviour.
  * `gap = governed - ungoverned` for any rate. The published headline is
    36.05 - 59.07 = -23.02 pp, i.e. NEGATIVE means governance LOWERED the rate,
    which is the direction the paper claims as the governance benefit.
    (The paper text quotes the same magnitude as "+23.0 pp improvement"; this module
    never uses that flipped convention.)

Usage as a self-test:  python SUBMISSION_2026/decomposition/_loader.py
"""
from __future__ import annotations

import csv
import glob
import os
import re
import sys

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
RESULTS = os.path.join(REPO, "examples", "irrigation_abm", "results")

SIM_LOG = "simulation_log.csv"
AUDIT_LOG = "irrigation_farmer_governance_audit.csv"

# ---------------------------------------------------------------------------
# Definitions from the brief. Do not invent variants of these anywhere downstream.
# ---------------------------------------------------------------------------
INCREASE = frozenset({"increase_large", "increase_small"})
HIGH = frozenset({"H", "VH"})

#: The five legal appraisal levels. MEASURED, not assumed: across all 41 irrigation runs
#: the wsa_label column takes exactly these five values plus "N/A" (112 rows, every one of
#: them a REJECTED_FALLBACK row) plus two junk singletons "T" and "A" (3 rows total, parse
#: debris). Anything outside this set is UNPARSED and is reported by
#: `label_unparsed_share`, never silently deleted.
LABEL_LEVELS = frozenset({"VL", "L", "M", "H", "VH"})

#: irrigation registry default; this is what executes when a proposal is REJECTED
DEFAULT_SKILL = "maintain_demand"

#: (label, directory prefix segment). "" is the anchor model, gemma3:4b.
MODELS = [
    ("gemma3:4b", ""),
    ("gemma3:12b", "gemma3_12b_"),
    ("gemma4:e2b", "gemma4_e2b_"),
    ("gemma4:e4b", "gemma4_e4b_"),
    ("ministral-3:8b", "ministral3_8b_"),
]

ANCHOR = ("gemma3:4b", "")

ARMS = {
    "governed": "production",     # validators ON
    "ungoverned": "ungoverned",   # no-validator arm
}

#: expected rows per run: 78 agents x 42 years
EXPECTED_ROWS = 3276

# Column classification. Downstream estimators must import these rather than
# re-typing column names, so that "did anyone condition on a post-treatment
# variable?" is answerable by grep.
PRE_TREATMENT_COLS = [
    "water_right", "cluster", "basin", "has_efficient_system", "drought_index",
    "shortage_tier", "curtailment_ratio", "lake_mead_level", "mead_storage_maf",
    "utilisation_pct", "below_minimum_utilisation", "year",
]
POST_TREATMENT_COLS = ["wsa_label", "aca_label", "yearly_decision"]
OUTCOME_COL = "yearly_decision"
MEDIATOR_COL = "wsa_label"


class DataError(RuntimeError):
    """Raised loudly whenever the corpus is not what the analysis assumes."""


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------
def _arm_prefix(arm: str) -> str:
    if arm in ARMS:
        return ARMS[arm]
    if arm in ARMS.values():
        return arm
    raise DataError(f"unknown arm {arm!r}; expected one of {sorted(ARMS)}")


def run_dirs(arm: str, prefix: str) -> list[str]:
    """Sorted absolute paths of every EXISTING run dir for (arm, model prefix).

    A directory only counts if it actually contains simulation_log.csv. Raises if
    the glob matches nothing at all -- an empty list is never returned silently.
    """
    pat = os.path.join(RESULTS, f"{_arm_prefix(arm)}_v21_42yr_{prefix}seed*")
    hits = sorted(d for d in glob.glob(pat) if os.path.isdir(d))
    if not hits:
        raise DataError(f"no run directories matched {pat}")
    good, bad = [], []
    for d in hits:
        (good if os.path.isfile(os.path.join(d, SIM_LOG)) else bad).append(d)
    if bad:
        raise DataError(
            f"{len(bad)} run dir(s) matched {pat} but have no {SIM_LOG}: "
            + ", ".join(os.path.basename(b) for b in bad)
        )
    return good


def seeds(arm: str, prefix: str) -> list[str]:
    """Sorted seed strings present for (arm, model prefix)."""
    out = []
    for d in run_dirs(arm, prefix):
        m = re.search(r"seed(\d+)$", os.path.basename(d))
        if not m:
            raise DataError(f"cannot parse a seed out of {d}")
        out.append(m.group(1))
    return sorted(out)


def balanced(prefix: str) -> bool:
    """True iff both arms carry exactly the same seed set for this model."""
    return seeds("governed", prefix) == seeds("ungoverned", prefix)


def run_dir(arm: str, prefix: str, seed: str) -> str:
    d = os.path.join(RESULTS, f"{_arm_prefix(arm)}_v21_42yr_{prefix}seed{seed}")
    if not os.path.isdir(d):
        raise DataError(f"missing run directory {d}")
    return d


def paired_seeds(prefix: str) -> list[str]:
    """Seeds present in BOTH arms, sorted. Used for every paired contrast."""
    return sorted(set(seeds("governed", prefix)) & set(seeds("ungoverned", prefix)))


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------
def _read_csv(path: str) -> list[dict]:
    if not os.path.isfile(path):
        raise DataError(f"missing file {path}")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise DataError(f"file is present but has zero data rows: {path}")
    return rows


def load_run(path: str) -> list[dict]:
    """Rows of simulation_log.csv. `path` may be the run dir or the csv itself."""
    csv_path = path if path.lower().endswith(".csv") else os.path.join(path, SIM_LOG)
    return _read_csv(csv_path)


def load_audit(path: str) -> list[dict]:
    """Rows of irrigation_farmer_governance_audit.csv (70 cols, governance detail).

    NOTE: the audit header contains the column `construct_completeness` TWICE.
    csv.DictReader keeps the last occurrence. No column used by this analysis is
    affected, but downstream code must not assume header uniqueness.
    """
    csv_path = path if path.lower().endswith(".csv") else os.path.join(path, AUDIT_LOG)
    return _read_csv(csv_path)


# ---------------------------------------------------------------------------
# Field accessors -- one place where normalisation happens
# ---------------------------------------------------------------------------
def action(row: dict) -> str:
    """The EXECUTED action, per project rule. simulation_log.yearly_decision."""
    return (row.get(OUTCOME_COL) or "").strip()


def wsa(row: dict) -> str:
    """Self-reported water-scarcity appraisal, uppercased and stripped.

    POST-TREATMENT. This is the mediator. Never condition a causal estimator on it.
    """
    return (row.get(MEDIATOR_COL) or "").strip().upper()


def aca(row: dict) -> str:
    return (row.get("aca_label") or "").strip().upper()


def is_high(row: dict) -> bool:
    return wsa(row) in HIGH


def is_increase(row: dict) -> bool:
    return action(row) in INCREASE


# ---------------------------------------------------------------------------
# Rates. All return float PERCENTAGES (0-100), or float('nan') on an empty base.
# ---------------------------------------------------------------------------
def ibr(rows: list[dict]) -> float:
    """PUBLISHED conditional statistic (a.k.a. AAI).

    numerator   rows with HIGH self-reported scarcity whose EXECUTED action increased
    denominator rows with HIGH self-reported scarcity

    Higher = worse. The denominator is post-treatment; that is the defect under study.
    """
    den = [r for r in rows if is_high(r)]
    if not den:
        return float("nan")
    return 100.0 * sum(1 for r in den if is_increase(r)) / len(den)


def increase_rate(rows: list[dict]) -> float:
    """UNCONDITIONAL executed-increase rate over ALL rows. Denominator is fixed by
    design (agents x years), so it is not post-treatment. Higher = more increases."""
    if not rows:
        return float("nan")
    return 100.0 * sum(1 for r in rows if is_increase(r)) / len(rows)


def high_share(rows: list[dict]) -> float:
    """Prevalence of the conditioning variable: % of rows with HIGH appraisal.
    This is the composition channel. Higher = the IBR denominator is bigger."""
    if not rows:
        return float("nan")
    return 100.0 * sum(1 for r in rows if is_high(r)) / len(rows)


def label_unparsed_share(rows: list[dict]) -> float:
    """% of rows whose wsa_label is NOT one of the five legal levels.

    In simulation_log.csv these appear as the literal string "N/A" (never as a blank
    cell), which is why a naive `if not value` emptiness test reports 0.00 % and hides
    them. Every N/A row in this corpus carries status REJECTED_FALLBACK.
    """
    if not rows:
        return float("nan")
    return 100.0 * sum(1 for r in rows if wsa(r) not in LABEL_LEVELS) / len(rows)


def high_share_parsed(rows: list[dict]) -> float:
    """`high_share` restricted to rows with a legal appraisal level.

    This is the convention used by SUBMISSION_2026/evidence/appraisal_composition.py,
    which reads the AUDIT csv where the same rows appear as blanks and are skipped.
    Reported alongside `high_share` so the two prior-art numbers can be reconciled
    instead of argued about.
    """
    den = [r for r in rows if wsa(r) in LABEL_LEVELS]
    if not den:
        return float("nan")
    return 100.0 * sum(1 for r in den if is_high(r)) / len(den)


# ---------------------------------------------------------------------------
# Small stats helpers (kept here so every estimator uses the same ones)
# ---------------------------------------------------------------------------
def mean(xs) -> float:
    xs = list(xs)
    return sum(xs) / len(xs) if xs else float("nan")


def sd(xs) -> float:
    """Sample standard deviation (n-1)."""
    xs = list(xs)
    if len(xs) < 2:
        return float("nan")
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def paired_t(diffs) -> tuple[float, int]:
    """(t statistic, df) for a one-sample t on the per-seed differences."""
    d = list(diffs)
    n = len(d)
    if n < 2:
        return float("nan"), max(n - 1, 0)
    s = sd(d)
    if s == 0:
        return float("inf") if mean(d) else float("nan"), n - 1
    return mean(d) / (s / n ** 0.5), n - 1


def t_two_sided_p(t: float, df: int) -> float:
    """Two-sided p for Student's t, via the regularised incomplete beta.
    Pure stdlib so this module has no third-party dependency."""
    import math
    if df <= 0 or t != t:            # nan
        return float("nan")
    if math.isinf(t):
        return 0.0
    x = df / (df + t * t)
    return _betainc(df / 2.0, 0.5, x)


def _betainc(a: float, b: float, x: float) -> float:
    import math
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    # Lentz continued fraction
    f, c, d = 1.0, 1.0, 0.0
    for i in range(0, 300):
        m = i // 2
        if i == 0:
            num = 1.0
        elif i % 2 == 0:
            num = (m * (b - m) * x) / ((a + 2 * m - 1) * (a + 2 * m))
        else:
            num = -((a + m) * (a + b + m) * x) / ((a + 2 * m) * (a + 2 * m + 1))
        d = 1.0 + num * d
        if abs(d) < 1e-30:
            d = 1e-30
        d = 1.0 / d
        c = 1.0 + num / c
        if abs(c) < 1e-30:
            c = 1e-30
        f *= c * d
        if abs(1.0 - c * d) < 1e-12:
            break
    r = front * (f - 1.0)
    return min(max(r, 0.0), 1.0)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------
def _main() -> int:
    print(f"REPO    = {REPO}")
    print(f"RESULTS = {RESULTS}\n")
    print(f"{'model':16s} {'arm':11s} {'seeds':22s} {'runs':>5s} {'rows/run':>12s} "
          f"{'unparsed wsa':>13s} {'bal':>5s}")
    print("-" * 96)
    ok = True
    for label, prefix in MODELS:
        try:
            bal = balanced(prefix)
        except DataError as exc:
            print(f"{label:16s} !! {exc}")
            ok = False
            continue
        for arm in ("governed", "ungoverned"):
            ss = seeds(arm, prefix)
            counts, unp = [], 0
            for s in ss:
                rows = load_run(run_dir(arm, prefix, s))
                counts.append(len(rows))
                unp += sum(1 for r in rows if wsa(r) not in LABEL_LEVELS)
            uniq = sorted(set(counts))
            shown = ",".join(str(c) for c in uniq)
            flag = "" if uniq == [EXPECTED_ROWS] else "  <- NOT 3276"
            print(f"{label:16s} {arm:11s} {','.join(ss):22s} {len(ss):>5d} "
                  f"{shown:>12s} {unp:>13d} {str(bal):>5s}{flag}")
            if uniq != [EXPECTED_ROWS]:
                ok = False
        print()
    print("balanced models:", [l for l, p in MODELS if balanced(p)])
    print("self-test:", "clean" if ok else "ANOMALIES ABOVE")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
