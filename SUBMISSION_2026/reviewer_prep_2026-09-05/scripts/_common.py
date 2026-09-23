"""Shared plumbing for the reviewer-prep tables. NO new metric definitions live here.

Every irrigation definition is imported from the canonical loader
``SUBMISSION_2026/decomposition/_loader.py``. Every flood definition is transcribed
from the canonical published implementation
``examples/single_agent/analysis/gemma4_nw_crossmodel_analysis.py`` and the flood
sections of ``SUBMISSION_2026/decomposition/e6_flood_placebo.py``; where this module
restates one it says so in the docstring and names the source line.

FAIL-LOUD CONTRACT
  Missing directory, missing file, missing column, empty denominator -> raise.
  Nothing here ever substitutes 0 or NaN for data that should exist. A NaN that IS
  returned (empty denominator on a legitimately empty stratum) is written to the CSV
  as the literal string "NA" so it can never be read as a zero.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import os
import sys

HERE = os.path.abspath(os.path.dirname(__file__))
PKG = os.path.dirname(HERE)                     # SUBMISSION_2026/reviewer_prep_2026-09-05
SUB = os.path.dirname(PKG)                      # SUBMISSION_2026
REPO = os.path.dirname(SUB)
DECOMP = os.path.join(SUB, "decomposition")
OUT = os.path.join(PKG, "out")

if DECOMP not in sys.path:
    sys.path.insert(0, DECOMP)
import _loader as L  # noqa: E402  CANONICAL irrigation definitions


class PrepError(RuntimeError):
    """Raised whenever the corpus is not what a table assumes. Never swallowed."""


# ---------------------------------------------------------------------------
# irrigation: the executed remap (_loader.py:59-60 + reproduce_published.py:51-53)
# ---------------------------------------------------------------------------
IRR_DEFAULT_SKILL = L.DEFAULT_SKILL          # "maintain_demand"
IRR_SKILLS = [
    "increase_large", "increase_small", "maintain_demand",
    "decrease_small", "decrease_large",
]


def irr_proposal(audit_row: dict) -> str:
    """Proposal-level action: what the agent asked for, before any validator."""
    return (audit_row.get("proposed_skill") or "").strip()


def irr_final(audit_row: dict) -> str:
    """Post-validator action as the audit writer recorded it (no fallback applied)."""
    return (audit_row.get("final_skill") or "").strip()


def irr_executed(audit_row: dict) -> str:
    """Executed remap: a REJECTED proposal runs the registry default instead.

    Transcribed verbatim from reproduce_published.py:51-53.
    """
    st = (audit_row.get("status") or "").strip()
    return IRR_DEFAULT_SKILL if st.startswith("REJECTED") else irr_final(audit_row)


def irr_wsa_audit(audit_row: dict) -> str:
    return (audit_row.get("construct_WSA_LABEL") or "").strip().upper()


# ---------------------------------------------------------------------------
# flood: transcribed from gemma4_nw_crossmodel_analysis.py
# ---------------------------------------------------------------------------
FLOOD_RESULTS = os.path.join(REPO, "examples", "single_agent", "results")
FLOOD_AUDIT = "household_governance_audit.csv"
FLOOD_SIM = "simulation_log.csv"
FLOOD_ACTION_ORDER = ["buy_insurance", "elevate_house", "relocate", "do_nothing"]
FLOOD_TP_ORDER = ["VL", "L", "M", "H", "VH"]
FLOOD_DEFAULT_SKILL = "do_nothing"      # e6_flood_placebo.py:FLOOD_DEFAULT_SKILL
HIGH = frozenset({"H", "VH"})
LOW = frozenset({"VL", "L"})

#: gemma4_nw_crossmodel_analysis.py:normalize_action. NOTE the tail behaviour:
#: an action outside the mapping AND outside ACTION_ORDER silently becomes
#: "do_nothing". That is the PUBLISHED behaviour, so it is reproduced here, and
#: `flood_unmapped_count` reports how many rows it silently absorbed.
_FLOOD_ACTION_MAP = {
    "buy_insurance": "buy_insurance", "buy_insurace": "buy_insurance",
    "insurance": "buy_insurance", "only_flood_insurance": "buy_insurance",
    "elevate_house": "elevate_house", "elevate": "elevate_house",
    "only_house_elevation": "elevate_house",
    "relocate": "relocate", "relocated": "relocate", "already_relocated": "relocate",
    "do_nothing": "do_nothing", "nothing": "do_nothing", "do_nothing.": "do_nothing",
}


def flood_normalize_action(value) -> str:
    text = str(value).strip().lower().replace(" ", "_")
    return _FLOOD_ACTION_MAP.get(text, text if text in FLOOD_ACTION_ORDER else "do_nothing")


def flood_action_is_unmapped(value) -> bool:
    """True iff normalize_action would have silently coerced this to do_nothing."""
    text = str(value).strip().lower().replace(" ", "_")
    return text not in _FLOOD_ACTION_MAP and text not in FLOOD_ACTION_ORDER


def flood_normalize_tp(value) -> str:
    text = str(value).strip().upper()
    return text if text in FLOOD_TP_ORDER else "UNK"


def flood_proposal(audit_row: dict) -> str:
    return flood_normalize_action(audit_row.get("proposed_skill"))


def flood_final(audit_row: dict) -> str:
    return flood_normalize_action(audit_row.get("final_skill"))


def flood_executed(audit_row: dict) -> str:
    st = (audit_row.get("status") or "").strip()
    return FLOOD_DEFAULT_SKILL if st.startswith("REJECTED") else flood_final(audit_row)


def flood_ibr_components(rows, act_fn, elevated_fn=None):
    """IBR = (R1 + R3 + R4) / total * 100. R5 tracked, EXCLUDED per EDT2.

    Transcribed from gemma4_nw_crossmodel_analysis.py:compute_ibr_components
    (line ~100). `total` is EVERY row handed in: the canonical denominator is
    unconditional, not the high-TP subset.
    """
    total = len(rows)
    if total == 0:
        raise PrepError("flood_ibr_components called with zero rows")
    r1 = r3 = r4 = r5 = 0
    for r in rows:
        tp = flood_normalize_tp(r.get("construct_TP_LABEL"))
        a = act_fn(r)
        if tp in HIGH and a == "do_nothing":
            r1 += 1
        if tp in LOW and a == "relocate":
            r3 += 1
        if tp in LOW and a == "elevate_house":
            r4 += 1
        if elevated_fn is not None and elevated_fn(r) and a == "elevate_house":
            r5 += 1
    return {
        "R1": r1, "R3": r3, "R4": r4, "R5_excluded": r5, "total": total,
        "ibr_pct": 100.0 * (r1 + r3 + r4) / total,
    }


def normalized_entropy(counts: dict, k: int) -> float:
    """EHE. Pooled-once Shannon entropy of a distribution / log2(k).

    `counts` maps category -> count (or share). Zero-count categories drop out of
    the sum, exactly as gemma4_nw_crossmodel_analysis.py:normalized_entropy does.
    Raises on an empty base rather than returning 0.0 -- a genuinely empty year is
    a fact, not an entropy of zero.
    """
    tot = float(sum(counts.values()))
    if tot <= 0:
        raise PrepError("normalized_entropy called on an empty distribution")
    if k <= 1:
        raise PrepError(f"normalized_entropy needs k>1, got {k}")
    h = 0.0
    for v in counts.values():
        p = v / tot
        if p > 0:
            h -= p * math.log2(p)
    return h / math.log2(k)


# ---------------------------------------------------------------------------
# flood run discovery -- seed comes from the manifest, NEVER from the Run_N name
# (e6_flood_placebo.py:_seed_of / discover)
# ---------------------------------------------------------------------------
def flood_seed_of(run_dir: str) -> str:
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise PrepError(f"no reproducibility_manifest.json in {run_dir}")
    with open(p, encoding="utf-8") as fh:
        j = json.load(fh)
    found = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k.lower() == "seed":
                    found.append(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(j)
    if not found:
        raise PrepError(f"no seed key in {p}")
    if len({str(x) for x in found}) != 1:
        raise PrepError(f"conflicting seeds {found} in {p}")
    return str(found[0])


def flood_runs(root: str, model: str, group: str) -> dict:
    """{run_name: (seed, run_dir)} for results/<root>/<model>/<group>/Run_*."""
    d = os.path.join(FLOOD_RESULTS, root, model, group)
    if not os.path.isdir(d):
        raise PrepError(f"missing flood dir {d}")
    out = {}
    for run in sorted(os.listdir(d)):
        rd = os.path.join(d, run)
        if not os.path.isdir(rd):
            continue
        if not os.path.isfile(os.path.join(rd, FLOOD_SIM)):
            continue
        out[run] = (flood_seed_of(rd), rd)
    if not out:
        raise PrepError(f"no runs with {FLOOD_SIM} under {d}")
    return out


# ---------------------------------------------------------------------------
# flood corpus routing -- v08 (the committed reviewer-prep default: explicit
# sampling temperature 0.8 / top_p 0.9 / top_k 40) vs defaults (2026-09-22
# re-run with NO sampling parameters sent, so the model's own modelfile
# defaults apply -- temperature 1 / top_p 0.95 / top_k 64 -- commit
# 83fa97e1). `FLOOD_CORPUS_DIRS` is the ONLY place a flood result-directory
# NAME is spelled out; every flood-reading script routes its directory
# lookups through `flood_corpus_dirs()` (never a local literal). Each entry
# is (root_dir_name, [seed, ...]) -- seed strings exactly as `Run_<seed>` is
# spelled on disk. The v08 sub-dict's values are transcribed verbatim from
# the literals each script already had; the defaults sub-dict's values are
# transcribed verbatim from the directory names named in the 2026-09-22 task
# brief that commissioned this switch.
#
# SCOPE NOTE: the real "defaults" strict/disabled batch lands as
# Run_{42..51} (10 seeds). This table's "strict"/"disabled" defaults entries
# intentionally cover only seeds 42-46 -- the same 5-seed shape every v08
# comparator (faf1bb12) and every existing pair/band-check template in
# r23/r24/r25/r26 already assumes (equal-length seed lists, 1:1 position
# pairing). Extending those templates to a genuine n=10 defaults analysis,
# the way r37 does for v08's faf1bb12+83fa97e1_ext split, is a follow-up,
# not silently absorbed here. r37 itself is the one script that legitimately
# wants all 10 defaults seeds in one flat corpus (no faf1bb12/ext split
# exists in the defaults world) -- it reads the "strict_n10"/"disabled_n10"
# keys below, defined only for corpus="defaults".
CORPUS_CHOICES = ("v08", "defaults")

_SEEDS2 = ["42", "43"]
_SEEDS5 = ["42", "43", "44", "45", "46"]
_SEEDS5_EXT = ["47", "48", "49", "50", "51"]
_SEEDS10 = _SEEDS5 + _SEEDS5_EXT

FLOOD_CORPUS_DIRS = {
    "v08": {
        "strict": ("JOH_strict_gemma3_4b_faf1bb12", _SEEDS5),
        "disabled": ("JOH_disabled_gemma3_4b_faf1bb12", _SEEDS5),
        "strict_ext": ("JOH_strict_gemma3_4b_83fa97e1_ext", _SEEDS5_EXT),
        "disabled_ext": ("JOH_disabled_gemma3_4b_83fa97e1_ext", _SEEDS5_EXT),
        "placebo": ("JOH_placebo_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_initprop": ("JOH_strict_initprop_gemma3_4b_83fa97e1", _SEEDS5),
        "strict_para1": ("JOH_strict_para1_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_para1": ("JOH_disabled_para1_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_para2": ("JOH_strict_para2_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_para2": ("JOH_disabled_para2_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_nonudge": ("JOH_strict_nonudge_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_nonudge": ("JOH_disabled_nonudge_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_gemma4_12b": ("JOH_strict_gemma4_12b_c3391a53", _SEEDS5),
        "disabled_gemma4_12b": ("JOH_disabled_gemma4_12b_c3391a53", _SEEDS5),
        "rulebased": ("rulebased_5seed_faf1bb12", _SEEDS5),
        "rulebased_old": ("rulebased_5seed_e75e390c", _SEEDS5),
    },
    "defaults": {
        "strict": ("JOH_strict_defaults_gemma3_4b_83fa97e1", _SEEDS5),
        "disabled": ("JOH_disabled_defaults_gemma3_4b_83fa97e1", _SEEDS5),
        "strict_n10": ("JOH_strict_defaults_gemma3_4b_83fa97e1", _SEEDS10),
        "disabled_n10": ("JOH_disabled_defaults_gemma3_4b_83fa97e1", _SEEDS10),
        "placebo": ("JOH_placebo_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_initprop": ("JOH_strict_initprop_defaults_gemma3_4b_83fa97e1", _SEEDS5),
        "strict_para1": ("JOH_strict_para1_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_para1": ("JOH_disabled_para1_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_para2": ("JOH_strict_para2_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_para2": ("JOH_disabled_para2_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_nonudge": ("JOH_strict_nonudge_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "disabled_nonudge": ("JOH_disabled_nonudge_defaults_gemma3_4b_83fa97e1", _SEEDS2),
        "strict_gemma4_12b": ("JOH_strict_defaults_gemma4_12b_83fa97e1", _SEEDS5),
        "disabled_gemma4_12b": ("JOH_disabled_defaults_gemma4_12b_83fa97e1", _SEEDS5),
        # rule-based has no LLM sampling at all -- deterministic, so there is
        # no separate "defaults" rule-based corpus; both corpora read the
        # same two dirs.
        "rulebased": ("rulebased_5seed_faf1bb12", _SEEDS5),
        "rulebased_old": ("rulebased_5seed_e75e390c", _SEEDS5),
    },
}


def flood_corpus_dirs(corpus: str) -> dict:
    """{'strict': (root_dir_name, [seed, ...]), ...} for the given corpus.

    The ONLY place flood result-directory names are spelled out. See the
    module comment above `FLOOD_CORPUS_DIRS` for what each key means and
    the SCOPE NOTE on why "strict"/"disabled" are 5 seeds even under
    corpus="defaults".
    """
    if corpus not in FLOOD_CORPUS_DIRS:
        raise PrepError(f"unknown corpus {corpus!r}, expected one of {CORPUS_CHOICES}")
    return FLOOD_CORPUS_DIRS[corpus]


def corpus_suffix(corpus: str) -> str:
    """'' for v08 (keeps every committed filename byte-identical), else
    '_<corpus>' (e.g. '_defaults')."""
    if corpus not in FLOOD_CORPUS_DIRS:
        raise PrepError(f"unknown corpus {corpus!r}, expected one of {CORPUS_CHOICES}")
    return "" if corpus == "v08" else f"_{corpus}"


def flood_sampling_method_text(corpus: str) -> str:
    """The exact Method-paragraph sentence each flood script states for its
    corpus, kept in one place so the wording can never drift between
    scripts or between a script's v08 and defaults runs."""
    if corpus == "v08":
        return "sampling: temperature 0.8 / top_p 0.9 / top_k 40"
    if corpus == "defaults":
        return ("sampling: none sent, modelfile defaults temperature 1 / top_p 0.95 / "
                "top_k 64")
    raise PrepError(f"unknown corpus {corpus!r}, expected one of {CORPUS_CHOICES}")


def add_corpus_arg(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Shared --corpus flag for every flood-reading reviewer-prep script.
    v08 (default) reproduces the committed output byte-for-byte; defaults
    reads the no-sampling-params re-run and writes a `_defaults`-suffixed
    output pair instead (never overwrites the v08 files)."""
    parser.add_argument(
        "--corpus", choices=CORPUS_CHOICES, default="v08",
        help="v08 (default) = committed corpus, explicit sampling 0.8/0.9/40. "
             "defaults = no sampling params sent (modelfile defaults temperature "
             "1/top_p 0.95/top_k 64), commit 83fa97e1; writes out/<name>_defaults.{md,csv} "
             "and never touches the v08 output files.")
    return parser


def flood_run_dir(corpus: str, key: str, seed: str) -> str:
    """Full path to results/<root>/Run_<seed> for one flood_corpus_dirs() entry."""
    root, seeds = flood_corpus_dirs(corpus)[key]
    if seed not in seeds:
        raise PrepError(f"corpus={corpus} key={key!r}: seed {seed!r} not in {seeds}")
    return os.path.join(FLOOD_RESULTS, root, f"Run_{seed}")


def flood_run_dir_ok(corpus: str, key: str, seed: str) -> bool:
    """True iff Run_<seed>'s directory exists on disk at all (a cheap,
    generic pre-check; callers still run their own real completeness gate
    -- audit CSV / simulation_log / run_integrity.json -- before trusting
    the run is actually usable)."""
    return os.path.isdir(flood_run_dir(corpus, key, seed))


def read_csv(path: str) -> list:
    if not os.path.isfile(path):
        raise PrepError(f"missing file {path}")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise PrepError(f"file present but zero data rows: {path}")
    return rows


def require_cols(rows, cols, where):
    have = set(rows[0].keys())
    missing = [c for c in cols if c not in have]
    if missing:
        raise PrepError(f"{where}: missing columns {missing}")


# ---------------------------------------------------------------------------
# stats + output
# ---------------------------------------------------------------------------
mean = L.mean
sd = L.sd
paired_t = L.paired_t
t_two_sided_p = L.t_two_sided_p


def exact_perm_p(diffs) -> float:
    """Exact two-sided sign-flip permutation p on paired differences.

    All 2^n sign assignments; p = share whose |mean| >= observed |mean|.
    For n = 5 the smallest attainable value is 2/32 = 0.0625 -- the floor quoted
    throughout this package. Returned so that "p = 0.0625" is visibly a FLOOR and
    not a measurement.
    """
    d = list(diffs)
    n = len(d)
    if n == 0:
        raise PrepError("exact_perm_p on empty input")
    obs = abs(sum(d) / n)
    hits = 0
    for mask in range(1 << n):
        s = sum(x if (mask >> i) & 1 else -x for i, x in enumerate(d))
        if abs(s / n) >= obs - 1e-12:
            hits += 1
    return hits / float(1 << n)


def fmt(x, nd=4):
    """NaN is written as the literal 'NA'. It is never written as 0."""
    if x is None:
        return "NA"
    if isinstance(x, float):
        if x != x or math.isinf(x):
            return "NA" if x != x else ("inf" if x > 0 else "-inf")
        return f"{x:.{nd}f}"
    return str(x)


def write_csv(name: str, fieldnames, rows):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="raise")
        w.writeheader()
        for r in rows:
            w.writerow({k: (fmt(v) if isinstance(v, float) else v) for k, v in r.items()})
    print(f"  wrote {os.path.relpath(path, REPO)}  ({len(rows)} rows)")
    return path


def banner(title):
    print("=" * 78)
    print(title)
    print("=" * 78)
