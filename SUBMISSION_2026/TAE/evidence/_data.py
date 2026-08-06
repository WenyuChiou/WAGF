"""SINGLE SOURCE OF TRUTH for the TAE workshop submission.

Every figure and table script under ``SUBMISSION_2026/TAE/`` imports this module so
that all of them discover runs, read files, and compute rates IDENTICALLY.

Nothing here has side effects on import. Run it directly for a full self-test::

    python SUBMISSION_2026/TAE/evidence/_data.py


-------------------------------------------------------------------------------
DESIGN RULE 1 -- the safe path is the ONLY path
-------------------------------------------------------------------------------
This module exports NO glob patterns and NO directory-name templates. A caller
cannot construct a path; it can only ask for one. Discovery is done by

  * an ALLOW-LIST of models, written out literally (``IRRIGATION_MODELS`` /
    ``FLOOD_MODELS``);
  * ``re.fullmatch`` on ANCHORED patterns, so ``Run_1_bak_broker`` cannot match
    ``^Run_(\\d+)$`` and ``production_v21_42yr_seed42_old`` cannot match
    ``^production_v21_42yr_seed(\\d+)$``;
  * a literal group-directory name per flood arm (``Group_C`` /
    ``Group_C_disabled``) -- never a bare ``**`` descent from the model dir;
  * ``_reject_contaminated()``, a belt-and-braces check applied to EVERY path
    segment this module ever returns.

Concretely blocked, and asserted in the self-test: ``Group_A`` (a different
experiment with no structured prompts), ``*_bak*``, ``_QUARANTINE_*``, ``_dead_*``,
``_logs``, and anything whose basename starts with ``_``.

DESIGN RULE 2 -- both arms are selected at the SAME strictness
An asymmetric pair is a silent bias. Irrigation arms differ ONLY in the leading
token (``production`` vs ``ungoverned``) and are resolved through one function,
``_irrigation_seed_map``. Flood arms differ ONLY in the base directory and the
group name and are resolved through one function, ``_flood_run_map``. There is no
second code path anywhere.

DESIGN RULE 3 -- never silently empty
Every discovery function raises ``DataError`` if it finds nothing, if a run
directory lacks its data file, or if a requested seed/run does not exist. An
empty list is never returned.


-------------------------------------------------------------------------------
SIGN CONVENTION -- hard-coded, and there is no way around it
-------------------------------------------------------------------------------
    DELTA = (no-validator value) MINUS (with-validators value)
    POSITIVE means the validators LOWERED the quantity.

Use ``DELTA(noval=..., gov=...)``. Both arguments are KEYWORD-ONLY precisely so a
caller cannot swap them by writing them in the wrong order. ``DELTA_LABEL`` is the
string every figure axis and table header must carry.


-------------------------------------------------------------------------------
DEFINITIONS (from the brief; do not invent variants downstream)
-------------------------------------------------------------------------------
    INCREASE        {"increase_large", "increase_small"}          (irrigation only)
    HIGH appraisal  label in {"H", "VH"}                          (both testbeds)

    irrigation appraisal   simulation_log.wsa_label  ==  audit construct_WSA_LABEL
    flood appraisal        audit construct_TP_LABEL
    action                 simulation_log.yearly_decision == audit final_skill
                           == the agent's LAST PROPOSED action.

    conditional rate    increases / decisions whose appraisal is HIGH   (published)
    unconditional rate  increases / ALL decisions (denominator fixed by design at
                        78 agents x 42 years = 3,276)

THE TWO ACTION READINGS. ``yearly_decision`` is the LAST PROPOSED action, not the
one that ran. On a REJECTED row the registry default ``maintain_demand`` executed
instead. VERIFIED on this corpus (anchor seed 42, governed): of 1,267 rejected
rows, 1,244 carry status ``REJECTED`` with ``yearly_decision`` still naming the
blocked proposal (401 increase_large, 798 increase_small, 39 decrease_small,
6 decrease_large) while 23 carry ``REJECTED_FALLBACK`` and already read
``maintain_demand``. Use ``executed_action()`` for the executed reading and label
EVERY number with which reading produced it. The published statistics
(36.05 / 59.07 conditional) are the LAST-PROPOSED reading.

CELL STATISTIC CONVENTION. The seed is the inferential unit. A cell value is the
MEAN OF THE PER-SEED RATES, not the pooled rate. This matters: pooled conditional
for the anchor governed arm is 36.26, the mean of per-seed rates is 36.05, and
36.05 is the published number. ``cell_mean()`` implements the published one.
"""
from __future__ import annotations

import csv
import json
import math
import os
import re
import sys
from typing import Callable, Iterable, NamedTuple

# =============================================================================
# Paths
# =============================================================================
HERE = os.path.abspath(os.path.dirname(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

IRRIGATION_RESULTS = os.path.join(REPO, "examples", "irrigation_abm", "results")
FLOOD_RESULTS = os.path.join(REPO, "examples", "single_agent", "results")

IRRIGATION_SIM = "simulation_log.csv"
IRRIGATION_AUDIT = "irrigation_farmer_governance_audit.csv"

#: Raw per-decision trace stream, relative to an irrigation run directory. One
#: JSON object per line. Reached only through ``irrigation_traces_path()`` so
#: that no analysis script builds this path itself.
IRRIGATION_TRACES = os.path.join("raw", "irrigation_farmer_traces.jsonl")

FLOOD_SIM = "simulation_log.csv"
FLOOD_AUDIT = "household_governance_audit.csv"


class DataError(RuntimeError):
    """Raised loudly whenever the corpus is not what the analysis assumes.

    This module never degrades to a warning. Silence is the exact failure mode
    the paper is about.
    """


# =============================================================================
# Definitions
# =============================================================================
INCREASE = frozenset({"increase_large", "increase_small"})
HIGH = frozenset({"H", "VH"})

#: The five legal appraisal levels, shared by both testbeds. Anything else
#: (irrigation writes the literal string "N/A" on parse-failure rows; the flood
#: audit writes an empty cell) is UNPARSED. Unparsed rows count in the
#: denominator of ``high_share`` and are simply not HIGH -- that is the published
#: convention and it is what reproduces 37.08 / 82.80. ``unparsed_share()``
#: reports them so the choice is visible rather than hidden.
LABEL_LEVELS = frozenset({"VL", "L", "M", "H", "VH"})

#: irrigation registry default: what actually executes when a proposal is REJECTED
IRRIGATION_DEFAULT_SKILL = "maintain_demand"

#: Statuses that mean "the proposal did not stand as proposed".
REJECTED_STATUSES = frozenset({"REJECTED", "REJECTED_FALLBACK"})

#: irrigation design constant: 78 agents x 42 years
IRRIGATION_EXPECTED_ROWS = 78 * 42          # 3276

#: flood design constant: 100 agents x 10 years in simulation_log.csv.
#: The flood AUDIT csv is known-partial (documented at
#: examples/single_agent/results/_DATA_DEFECTS_2026-05-30.md section B, the F1
#: silent-drop). Flood rates must therefore be per-run rates over the audit rows
#: that exist, NEVER pooled over a 1000 denominator. ``flood_audit_coverage()``
#: reports the shortfall per run.
FLOOD_EXPECTED_SIM_ROWS = 1000

DELTA_LABEL = "Delta = no-validator MINUS with-validators (positive = validators lowered it)"


# =============================================================================
# Arms
# =============================================================================
#: Canonical arm names. "gov" = validators ON, "noval" = no-validator arm.
ARMS = ("gov", "noval")

_IRRIGATION_ARM_TOKEN = {"gov": "production", "noval": "ungoverned"}

#: (base results directory suffix, group directory) per flood arm. The group
#: directory is a LITERAL, named explicitly, per the contamination rules.
_FLOOD_ARM_GROUP = {"gov": "Group_C", "noval": "Group_C_disabled"}

ARM_DISPLAY = {"gov": "with-validators", "noval": "no-validator"}


def _check_arm(arm: str) -> str:
    if arm not in ARMS:
        raise DataError(f"unknown arm {arm!r}; expected one of {ARMS}")
    return arm


# =============================================================================
# Model allow-lists -- written out literally, never discovered
# =============================================================================
class IrrigationModel(NamedTuple):
    label: str          # human-readable model name
    prefix: str         # directory infix; "" is the anchor, gemma3:4b
    anchor: bool


IRRIGATION_MODELS: list[IrrigationModel] = [
    IrrigationModel("gemma3:4b", "", True),
    IrrigationModel("gemma3:12b", "gemma3_12b_", False),
    IrrigationModel("gemma4:e2b", "gemma4_e2b_", False),
    IrrigationModel("gemma4:e4b", "gemma4_e4b_", False),
    IrrigationModel("ministral3:8b", "ministral3_8b_", False),
]

IRRIGATION_ANCHOR = IRRIGATION_MODELS[0]

#: Cells barred from every paired contrast because their two arms hold different
#: seeds. EMPTY as of 2026-08-03: ministral3:8b was the only member (3 governed
#: seeds against 2 no-validator) until its no-validator seed 44 run landed and
#: balanced the cell at 3 against 3. The mechanism is kept, not deleted, because
#: it is the guard that would catch the next unbalanced cell; ``corpus_inventory``
#: cross-checks this set against what is actually on disk and fails on a stale
#: entry, which is how the removal was triggered rather than remembered.
IRRIGATION_UNBALANCED_PREFIXES: frozenset[str] = frozenset()


class FloodModel(NamedTuple):
    label: str          # human-readable model name
    model_dir: str      # directory name under the base
    gov_base: str       # base results dir for the with-validators arm
    noval_base: str     # base results dir for the no-validator arm


FLOOD_MODELS: list[FloodModel] = [
    FloodModel("gemma3:4b", "gemma3_4b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("gemma3:12b", "gemma3_12b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("gemma3:27b", "gemma3_27b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("ministral3:3b", "ministral3_3b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("ministral3:8b", "ministral3_8b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("ministral3:14b", "ministral3_14b", "JOH_FINAL", "JOH_ABLATION_DISABLED"),
    FloodModel("gemma4:e2b", "gemma4_e2b", "JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2"),
    FloodModel("gemma4:e4b", "gemma4_e4b", "JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2"),
    FloodModel("gemma4:26b", "gemma4_26b", "JOH_FINAL_v2", "JOH_ABLATION_DISABLED_v2"),
]

_FLOOD_BY_LABEL = {m.label: m for m in FLOOD_MODELS}
_FLOOD_BY_DIR = {m.model_dir: m for m in FLOOD_MODELS}


def flood_model(model) -> FloodModel:
    """Resolve a FloodModel from a FloodModel, a label, or a directory name."""
    if isinstance(model, FloodModel):
        return model
    if model in _FLOOD_BY_LABEL:
        return _FLOOD_BY_LABEL[model]
    if model in _FLOOD_BY_DIR:
        return _FLOOD_BY_DIR[model]
    raise DataError(
        f"unknown flood model {model!r}; expected one of "
        f"{sorted(_FLOOD_BY_LABEL)} or {sorted(_FLOOD_BY_DIR)}"
    )


def irrigation_model(prefix) -> IrrigationModel:
    """Resolve an IrrigationModel from an IrrigationModel, a label, or a prefix."""
    if isinstance(prefix, IrrigationModel):
        return prefix
    for m in IRRIGATION_MODELS:
        if prefix == m.prefix or prefix == m.label:
            return m
    raise DataError(
        f"unknown irrigation model {prefix!r}; expected one of "
        f"{[m.label for m in IRRIGATION_MODELS]} "
        f"or a prefix in {[m.prefix for m in IRRIGATION_MODELS]}"
    )


# =============================================================================
# Contamination guard
# =============================================================================
#: Substring tokens that mark a directory as never-usable. Case-insensitive.
#: Verified not to occur in any legitimate name this module returns.
_CONTAMINATED_TOKENS = (
    "bak", "backup", "dead", "quarantine", "archive", "old", "copy",
    "tmp", "temp", "scratch", "group_a", "_logs", "defect", "orphan",
)


def _reject_contaminated(path: str) -> str:
    """Raise if ANY segment of ``path`` below the results roots looks contaminated.

    Applied to every path this module hands out. This is redundant with the
    anchored regexes and the literal allow-lists -- deliberately so. A future
    caller who edits one layer still hits the other.
    """
    abs_path = os.path.abspath(path)
    for root in (IRRIGATION_RESULTS, FLOOD_RESULTS):
        if abs_path.startswith(os.path.abspath(root) + os.sep):
            rel = os.path.relpath(abs_path, root)
            break
    else:
        raise DataError(
            f"path escapes both results roots, refusing to return it: {abs_path}"
        )
    for seg in rel.replace("\\", "/").split("/"):
        if seg.startswith("_"):
            raise DataError(
                f"CONTAMINATION GUARD: path segment {seg!r} starts with '_' "
                f"(quarantine / logs / scratch convention) in {abs_path}"
            )
        low = seg.lower()
        for tok in _CONTAMINATED_TOKENS:
            if tok in low:
                raise DataError(
                    f"CONTAMINATION GUARD: path segment {seg!r} contains "
                    f"forbidden token {tok!r} in {abs_path}"
                )
    return abs_path


# =============================================================================
# Irrigation discovery
# =============================================================================
def _irrigation_seed_map(arm: str, prefix: str) -> dict[int, str]:
    """The ONE irrigation discovery function. Both arms go through it.

    Matching is ``re.fullmatch`` on an anchored pattern built from the arm token
    and the model prefix, so nothing with a suffix (``_bak``, ``_old``, ``_dead``)
    and nothing with an extra infix can be reached.
    """
    _check_arm(arm)
    token = _IRRIGATION_ARM_TOKEN[arm]
    if not os.path.isdir(IRRIGATION_RESULTS):
        raise DataError(f"missing irrigation results root {IRRIGATION_RESULTS}")
    pat = re.compile(
        r"^" + re.escape(f"{token}_v21_42yr_{prefix}seed") + r"(\d+)$"
    )
    out: dict[int, str] = {}
    for name in sorted(os.listdir(IRRIGATION_RESULTS)):
        m = pat.fullmatch(name)
        if not m:
            continue
        d = os.path.join(IRRIGATION_RESULTS, name)
        if not os.path.isdir(d):
            continue
        _reject_contaminated(d)
        for fname in (IRRIGATION_SIM, IRRIGATION_AUDIT):
            f = os.path.join(d, fname)
            if not os.path.isfile(f):
                raise DataError(
                    f"run directory {d} matched but is missing {fname}; "
                    "refusing to return a partial cell"
                )
        out[int(m.group(1))] = d
    if not out:
        raise DataError(
            f"no irrigation runs found for arm={arm!r} prefix={prefix!r} "
            f"(pattern {pat.pattern!r} under {IRRIGATION_RESULTS})"
        )
    return dict(sorted(out.items()))


def irrigation_runs(arm: str, prefix="") -> dict[int, str]:
    """``{seed: absolute run directory}`` for one irrigation cell.

    ``arm`` is "gov" or "noval". ``prefix`` is an IrrigationModel, a model label,
    or a directory prefix ("" = the anchor, gemma3:4b).

    Both arms are selected by the identical mechanism. Raises rather than
    returning an empty dict.
    """
    return _irrigation_seed_map(_check_arm(arm), irrigation_model(prefix).prefix)


def irrigation_run(arm: str, prefix, seed: int) -> str:
    """One irrigation run directory. Raises if that seed is absent in that arm."""
    runs = irrigation_runs(arm, prefix)
    if int(seed) not in runs:
        raise DataError(
            f"seed {seed} is absent for arm={arm!r} model="
            f"{irrigation_model(prefix).label!r}; present: {sorted(runs)}"
        )
    return runs[int(seed)]


class Balance(NamedTuple):
    balanced: bool
    gov_seeds: tuple[int, ...]
    noval_seeds: tuple[int, ...]
    paired_seeds: tuple[int, ...]


def seed_sets(prefix="") -> Balance:
    """The two seed sets and the paired intersection for an irrigation cell."""
    g = tuple(sorted(irrigation_runs("gov", prefix)))
    n = tuple(sorted(irrigation_runs("noval", prefix)))
    return Balance(g == n, g, n, tuple(sorted(set(g) & set(n))))


def balanced(prefix="") -> bool:
    """True iff both irrigation arms carry exactly the same seed set."""
    return seed_sets(prefix).balanced


def paired_seeds(prefix="") -> tuple[int, ...]:
    """Seeds present in BOTH irrigation arms. Every paired contrast uses these."""
    return seed_sets(prefix).paired_seeds


def excluded_from_paired(prefix) -> bool:
    """True for cells the brief bars from paired contrasts (ministral3:8b)."""
    return irrigation_model(prefix).prefix in IRRIGATION_UNBALANCED_PREFIXES


# =============================================================================
# Flood discovery
# =============================================================================
def _flood_run_map(arm: str, model) -> dict[int, str]:
    """The ONE flood discovery function. Both arms go through it.

    The group directory is a LITERAL per arm ("Group_C" / "Group_C_disabled") --
    it is never reached by a wildcard from the model directory, so ``Group_A``
    is structurally unreachable. Run directories must ``fullmatch`` ``^Run_(\\d+)$``,
    so ``Run_1_bak_broker`` cannot be selected.
    """
    _check_arm(arm)
    spec = flood_model(model)
    base = spec.gov_base if arm == "gov" else spec.noval_base
    group = _FLOOD_ARM_GROUP[arm]
    model_dir = os.path.join(FLOOD_RESULTS, base, spec.model_dir, group)
    if not os.path.isdir(model_dir):
        raise DataError(
            f"missing flood group directory {model_dir} "
            f"(arm={arm!r}, model={spec.label!r})"
        )
    pat = re.compile(r"^Run_(\d+)$")
    out: dict[int, str] = {}
    for name in sorted(os.listdir(model_dir)):
        m = pat.fullmatch(name)
        if not m:
            continue
        d = os.path.join(model_dir, name)
        if not os.path.isdir(d):
            continue
        _reject_contaminated(d)
        f = os.path.join(d, FLOOD_AUDIT)
        if not os.path.isfile(f):
            raise DataError(
                f"run directory {d} matched but is missing {FLOOD_AUDIT}; "
                "refusing to return a partial cell"
            )
        out[int(m.group(1))] = d
    if not out:
        raise DataError(f"no flood runs found under {model_dir}")
    return dict(sorted(out.items()))


def flood_runs(arm: str, model) -> dict[int, str]:
    """``{run index: absolute run directory}`` for one flood cell.

    KEY SEMANTICS -- READ THIS. The key is the RUN INDEX (1..5), not the RNG seed
    recorded in ``reproducibility_manifest.json``. Pairing is Run_N to Run_N,
    which is this project's published convention.

    That distinction is load-bearing here because the manifests do NOT agree
    across arms. VERIFIED on this corpus: in all six JOH_FINAL (v1) models the
    with-validators arm records seeds ``[42, 4202, 4203, 45, 46]`` for Run_1..Run_5
    while the no-validator arm records ``[42, 43, 44, 45, 46]``. The three
    JOH_FINAL_v2 models agree on ``[42, 43, 44, 45, 46]``. Keying on the manifest
    seed would silently drop or mis-pair Run_2 and Run_3 for two thirds of the
    flood corpus. ``flood_seed_alignment()`` reports this per model; the self-test
    prints it.
    """
    return _flood_run_map(_check_arm(arm), model)


def flood_run(arm: str, model, run: int) -> str:
    runs = flood_runs(arm, model)
    if int(run) not in runs:
        raise DataError(
            f"Run_{run} absent for arm={arm!r} model={flood_model(model).label!r}; "
            f"present: {sorted(runs)}"
        )
    return runs[int(run)]


def flood_seed_sets(model) -> Balance:
    g = tuple(sorted(flood_runs("gov", model)))
    n = tuple(sorted(flood_runs("noval", model)))
    return Balance(g == n, g, n, tuple(sorted(set(g) & set(n))))


def flood_balanced(model) -> bool:
    return flood_seed_sets(model).balanced


def flood_manifest_seed(run_dir: str):
    """The RNG seed recorded in a flood run's reproducibility manifest, or None."""
    p = os.path.join(run_dir, "reproducibility_manifest.json")
    if not os.path.isfile(p):
        raise DataError(f"missing manifest {p}")
    with open(p, encoding="utf-8") as fh:
        return json.load(fh).get("seed")


class SeedAlignment(NamedTuple):
    label: str
    gov_manifest_seeds: tuple
    noval_manifest_seeds: tuple
    aligned: bool


def flood_seed_alignment(model) -> SeedAlignment:
    """Compare the two arms' manifest seeds run-by-run. Reports, never repairs."""
    spec = flood_model(model)
    g = tuple(flood_manifest_seed(p) for _, p in sorted(flood_runs("gov", spec).items()))
    n = tuple(flood_manifest_seed(p) for _, p in sorted(flood_runs("noval", spec).items()))
    return SeedAlignment(spec.label, g, n, g == n)


# =============================================================================
# Loading
# =============================================================================
_CACHE: dict[str, list[dict]] = {}


def _read_csv(path: str) -> list[dict]:
    if not os.path.isfile(path):
        raise DataError(f"missing file {path}")
    cached = _CACHE.get(path)
    if cached is not None:
        return cached
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    if not rows:
        raise DataError(f"file exists but has zero data rows: {path}")
    _CACHE[path] = rows
    return rows


def _which_testbed(run_dir: str) -> str:
    ap = os.path.abspath(run_dir)
    if ap.startswith(os.path.abspath(IRRIGATION_RESULTS) + os.sep):
        return "irrigation"
    if ap.startswith(os.path.abspath(FLOOD_RESULTS) + os.sep):
        return "flood"
    raise DataError(f"cannot tell which testbed this path belongs to: {run_dir}")


def load_sim(path: str) -> list[dict]:
    """Rows of ``simulation_log.csv``. ``path`` may be a run dir or the csv itself.

    Read as utf-8-sig (these files carry a BOM). Never returns an empty list.
    """
    if path.lower().endswith(".csv"):
        return _read_csv(path)
    _reject_contaminated(path)
    name = IRRIGATION_SIM if _which_testbed(path) == "irrigation" else FLOOD_SIM
    return _read_csv(os.path.join(path, name))


def load_audit(path: str) -> list[dict]:
    """Rows of the governance audit csv. ``path`` may be a run dir or the csv.

    NOTE: the irrigation audit header contains ``construct_completeness`` TWICE.
    ``csv.DictReader`` keeps the last occurrence. No column used here is affected,
    but downstream code must not assume header uniqueness.
    """
    if path.lower().endswith(".csv"):
        return _read_csv(path)
    _reject_contaminated(path)
    name = IRRIGATION_AUDIT if _which_testbed(path) == "irrigation" else FLOOD_AUDIT
    return _read_csv(os.path.join(path, name))


def irrigation_traces_path(run_dir: str) -> str:
    """Absolute path to one irrigation run's raw per-decision trace stream.

    The trace JSONL is ~50 MB per run, so this module hands out the PATH and
    lets the caller stream it; there is no ``load_`` variant and no cache.

    ``run_dir`` must be a directory this module already handed out
    (``irrigation_run`` / ``irrigation_runs``). It is re-run through the
    contamination guard and the testbed check here anyway, so a caller cannot
    reach a quarantined or flood directory by passing a hand-built string --
    the same reason ``load_sim`` and ``load_audit`` re-check.
    """
    _reject_contaminated(run_dir)
    tb = _which_testbed(run_dir)
    if tb != "irrigation":
        raise DataError(
            f"irrigation_traces_path called on a {tb} run directory: {run_dir}"
        )
    p = os.path.join(os.path.abspath(run_dir), IRRIGATION_TRACES)
    if not os.path.isfile(p):
        raise DataError(f"missing trace stream {p}")
    return p


# =============================================================================
# Field accessors -- the single place normalisation happens
# =============================================================================
#: appraisal column, in resolution order
_APPRAISAL_COLS = (
    ("wsa_label", "irrigation"),            # irrigation simulation_log
    ("construct_WSA_LABEL", "irrigation"),  # irrigation audit
    ("construct_TP_LABEL", "flood"),        # flood audit
)

#: action column, in resolution order
_ACTION_COLS = ("yearly_decision", "final_skill")


def _row_testbed(row: dict) -> str:
    for col, tb in _APPRAISAL_COLS:
        if col in row:
            return tb
    raise DataError(
        "row carries no recognised appraisal column; expected one of "
        f"{[c for c, _ in _APPRAISAL_COLS]}, saw {sorted(row)[:12]}..."
    )


def appraisal(row: dict) -> str:
    """Self-reported appraisal label, stripped and upper-cased.

    POST-TREATMENT by construction. This is the conditioning variable the paper
    is about; never treat it as a covariate.
    """
    for col, _ in _APPRAISAL_COLS:
        if col in row:
            return (row.get(col) or "").strip().upper()
    raise DataError(
        "row carries no recognised appraisal column; expected one of "
        f"{[c for c, _ in _APPRAISAL_COLS]}"
    )


def action(row: dict) -> str:
    """The LAST PROPOSED action (``yearly_decision`` / ``final_skill``).

    This is NOT necessarily what executed -- see ``executed_action``.
    """
    for col in _ACTION_COLS:
        if col in row:
            return (row.get(col) or "").strip()
    raise DataError(
        f"row carries no recognised action column; expected one of {_ACTION_COLS}"
    )


def status(row: dict) -> str:
    if "status" not in row:
        raise DataError("row carries no 'status' column (audit rows only)")
    return (row.get("status") or "").strip().upper()


def is_high(row: dict) -> bool:
    return appraisal(row) in HIGH


def is_increase(row: dict) -> bool:
    return action(row) in INCREASE


def is_rejected(audit_status: str) -> bool:
    return (audit_status or "").strip().upper() in REJECTED_STATUSES


def executed_action(sim_row: dict, audit_status: str) -> str:
    """The action that ACTUALLY RAN, applying the ``maintain_demand`` substitution.

    ``sim_row``      an irrigation ``simulation_log.csv`` row (or audit row)
    ``audit_status`` the joined audit ``status`` for the same (agent_id, year)

    On APPROVED the proposal ran, so this is ``yearly_decision`` unchanged. On
    REJECTED / REJECTED_FALLBACK the registry default ``maintain_demand`` ran
    instead, and ``yearly_decision`` still names the blocked proposal.

    Irrigation only. The flood pack applies its own default INSIDE the audit
    writer (flood REJECTED rows already read ``final_skill = do_nothing``), so
    applying a second substitution there would double-count; this function
    refuses flood rows rather than guessing.
    """
    if _row_testbed(sim_row) != "irrigation":
        raise DataError(
            "executed_action() is irrigation-only: the flood audit already "
            "records the post-substitution action on REJECTED rows"
        )
    return IRRIGATION_DEFAULT_SKILL if is_rejected(audit_status) else action(sim_row)


def join_sim_audit(run_dir: str) -> list[tuple[dict, dict]]:
    """``(sim_row, audit_row)`` pairs joined on (agent_id, year).

    Raises unless the join is exact and one-to-one in both directions. VERIFIED
    on all ten anchor irrigation runs: 3,276 = 3,276, zero unmatched, and
    ``sim.yearly_decision == audit.final_skill`` on every row.
    """
    sim = load_sim(run_dir)
    aud = load_audit(run_dir)
    key = lambda r: (r.get("agent_id", ""), r.get("year", ""))
    amap = {key(r): r for r in aud}
    if len(amap) != len(aud):
        raise DataError(f"audit (agent_id, year) keys are not unique in {run_dir}")
    smap = {key(r): r for r in sim}
    if len(smap) != len(sim):
        raise DataError(f"sim (agent_id, year) keys are not unique in {run_dir}")
    missing = set(smap) - set(amap)
    extra = set(amap) - set(smap)
    if missing or extra:
        raise DataError(
            f"sim/audit join is not exact in {run_dir}: "
            f"{len(missing)} sim rows unmatched, {len(extra)} audit rows unmatched"
        )
    return [(smap[k], amap[k]) for k in smap]


# =============================================================================
# Rates. All return float PERCENTAGES (0-100). Empty base -> DataError, not nan.
# =============================================================================
def _require_irrigation(rows: list[dict], fn: str) -> None:
    if not rows:
        raise DataError(f"{fn}() called on zero rows")
    tb = _row_testbed(rows[0])
    if tb != "irrigation":
        raise DataError(
            f"{fn}() is irrigation-only (INCREASE = {sorted(INCREASE)} is an "
            f"irrigation action vocabulary); these rows are {tb}"
        )


def conditional_rate(rows: list[dict], action_fn: Callable[[dict], str] | None = None) -> float:
    """PUBLISHED statistic: increases / decisions whose appraisal is HIGH.

    The denominator is post-treatment. That is the defect under study, not a bug
    in this function. Irrigation only.
    """
    _require_irrigation(rows, "conditional_rate")
    act = action_fn or action
    den = [r for r in rows if is_high(r)]
    if not den:
        raise DataError("conditional_rate(): no HIGH-appraisal rows in the base")
    return 100.0 * sum(1 for r in den if act(r) in INCREASE) / len(den)


def unconditional_rate(rows: list[dict], action_fn: Callable[[dict], str] | None = None) -> float:
    """increases / ALL decisions. Denominator fixed by design, so not post-treatment.

    Irrigation only.
    """
    _require_irrigation(rows, "unconditional_rate")
    act = action_fn or action
    return 100.0 * sum(1 for r in rows if act(r) in INCREASE) / len(rows)


def high_share(rows: list[dict]) -> float:
    """Prevalence of the conditioning variable: % of rows with a HIGH appraisal.

    This is the number nobody reports and the paper argues everybody should.
    Works on both testbeds. Unparsed labels sit in the denominator and are not
    HIGH -- the published convention; see ``unparsed_share``.
    """
    if not rows:
        raise DataError("high_share(): called on zero rows")
    return 100.0 * sum(1 for r in rows if is_high(r)) / len(rows)


def unparsed_share(rows: list[dict]) -> float:
    """% of rows whose appraisal label is not one of the five legal levels."""
    if not rows:
        raise DataError("unparsed_share(): called on zero rows")
    return 100.0 * sum(1 for r in rows if appraisal(r) not in LABEL_LEVELS) / len(rows)


def rejection_pressure(audit_rows: list[dict]) -> float:
    """Enforcement pressure: % of audit rows whose proposal did not stand."""
    if not audit_rows:
        raise DataError("rejection_pressure(): called on zero rows")
    return 100.0 * sum(1 for r in audit_rows if is_rejected(status(r))) / len(audit_rows)


def flood_audit_coverage(run_dir: str) -> float:
    """% of the 1,000 design-expected flood decisions that reached the audit csv.

    The flood audit is known-partial (the F1 silent-drop, documented at
    ``examples/single_agent/results/_DATA_DEFECTS_2026-05-30.md`` section B).
    Flood rates must be per-run rates over the rows that exist.
    """
    if _which_testbed(run_dir) != "flood":
        raise DataError("flood_audit_coverage() is flood-only")
    return 100.0 * len(load_audit(run_dir)) / FLOOD_EXPECTED_SIM_ROWS


# =============================================================================
# Rejection cause -- the two rule layers
# =============================================================================
#: a failed_rules cell equal to one of these names no rule at all
#:
#: Several literals mean the same thing here because the corpus spans two broker
#: revisions. Runs written before broker commit ``0b17c367`` leave ``failed_rules``
#: as the bare ``Unknown`` from the format check; that commit
#: ("fix(audit): name output_schema/precondition violations in failed_rules",
#: 2026-06-10) makes the producer explicit and writes ``precondition_violation``
#: and ``output_schema_violation``
#: (``broker/core/skill_broker_engine.py:829`` and ``:824``).
#:
#: ``0b17c367`` IS ON ``origin/main``. Staying on main does not avoid these
#: literals -- every run produced after 2026-06-10 emits them, which is why this
#: set must be complete rather than grown one incident at a time. (An earlier
#: version of this comment attributed ``precondition_violation`` to ``10e190cf``,
#: a branch-only commit of 2026-07-30; that was wrong, and it understated the
#: affected window by seven weeks. Corrected 2026-08-05 against ``git log -S``.)
#:
#: ``precondition_violation``: one irrigation run is on the later revision --
#: ``ungoverned_v21_42yr_ministral3_8b_seed44``, 22 rows -- and it is the only
#: occurrence of the string in the corpus. That it and ``Unknown`` are the same
#: event is not an assumption: all 19 of its rejections carry the identical
#: ``error_messages`` value as the 65 ``Unknown`` rejections in its two cell-mates,
#: ``Precondition failed: 'not at_allocation_cap' (field is True)``, and hit only
#: increase_large / increase_small, the two skills the cap is attached to.
#:
#: ``output_schema_violation``: ZERO occurrences in the corpus, verified
#: 2026-08-05 across all 42 irrigation audit CSVs. It is listed anyway, and that
#: is the point. It is written unconditionally with no feature flag
#: (``skill_broker_engine.py:824``), ``output_schema:`` is declared 5x in the
#: irrigation skill registry, so it is reachable in any new run -- and a token
#: this set does not know is silently counted as a named validator-rule hit by
#: ``rejection_cause()`` below. That is exactly the 2026-08-03 defect, one literal
#: over: the ministral seed-44 run rewrote a string this set did not carry, 19
#: world-feasibility blocks were recounted as behavioural-theory blocks, and a
#: section-3 claim was false until a figure's own gate caught it. Adding this
#: token changes no published number precisely because it has never fired; it
#: stops the next run from repeating the incident.
#: Sibling scripts already carry the complete set --
#: ``SUBMISSION_2026/evidence/fallback_scenarios.py:47`` and
#: ``AAMAS2027/experiments/fallback_scenarios.py:47``. This copy was the odd one out.
_NO_RULE_TOKENS = frozenset(
    {"", "unknown", "none", "n/a", "nan",
     "precondition_violation", "output_schema_violation"}
)


def rejection_cause(audit_row: dict) -> str | None:
    """``"theory"`` | ``"precondition"`` | ``None``.

    ``None``           the proposal stood (not a rejection).
    ``"precondition"`` rejected with NO behavioural rule named -- ``failed_rules``
                       is empty or ``Unknown``. In this corpus that is the water-right
                       allocation-cap precondition: a WORLD-feasibility block, evaluated
                       before any behavioural rule runs.
                       As of 2026-08-05 this bucket also absorbs
                       ``output_schema_violation``, a malformed model response --
                       a FORMAT failure, not a world-feasibility one. The claim the
                       bucket actually makes ("no behavioural rule fired") holds for
                       both members; its NAME holds only for the first. Zero such
                       rows exist in the corpus today, so nothing published is
                       affected. Split the key if the distinction ever becomes
                       load-bearing rather than hypothetical.
    ``"theory"``       rejected with at least one named behavioural-theory rule
                       (e.g. ``high_threat_high_cope_no_increase``,
                       ``demand_ceiling_stabilizer``).

    Pipe-separated cells are split; a cell naming a real rule alongside the
    literal ``Unknown`` counts as "theory", because a behavioural rule did fire.
    VERIFIED to partition cleanly with zero exceptions on the anchor irrigation
    corpus (5 seeds, both arms): no-validator 4,757/16,380 rejections are all bare
    preconditions; with-validators 6,469/16,380 all name a validator rule.

    The internal key stays "theory" for compatibility, but the LABEL is
    "named a validator rule" and the two are not synonyms: the validator stack
    contains world-conditioned rules as well as appraisal-conditioned ones, and
    only 3,840/6,469 (59.4%) of governed rejections name an appraisal-conditioned
    rule. Claiming "100% behavioural theory" was retracted on 2026-07-31.
    """
    st = status(audit_row)
    if not is_rejected(st):
        return None
    raw = (audit_row.get("failed_rules") or "").strip()
    named = [t.strip() for t in raw.split("|") if t.strip().lower() not in _NO_RULE_TOKENS]
    return "theory" if named else "precondition"


# =============================================================================
# Sign convention -- keyword-only so it cannot be inverted by argument order
# =============================================================================
def DELTA(*, noval: float, gov: float) -> float:
    """The project's ONLY delta. ``noval - gov``. Positive = validators lowered it.

    Keyword-only by design: ``DELTA(a, b)`` is a TypeError, so the sign error
    that has already been published once cannot recur by transposition.
    """
    return float(noval) - float(gov)


# =============================================================================
# Statistics. Seed is the inferential unit.
# =============================================================================
def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    if not xs:
        raise DataError("mean(): empty sequence")
    return sum(xs) / len(xs)


def sd(xs: Iterable[float]) -> float:
    """Sample standard deviation (n-1)."""
    xs = list(xs)
    if len(xs) < 2:
        raise DataError("sd(): needs at least 2 values")
    m = mean(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


class PairedT(NamedTuple):
    mean: float
    ci_lo: float
    ci_hi: float
    t: float
    df: int


def paired_t(deltas: Iterable[float]) -> PairedT:
    """One-sample t on the per-seed deltas. Returns (mean, ci_lo, ci_hi, t, df).

    The input must ALREADY be per-seed ``DELTA(noval=..., gov=...)`` values, so the
    sign convention is inherited rather than re-decided here. n seeds -> df = n-1
    (5 seeds -> df 4; the 3-seed cells -> df 2). CI is the two-sided 95% interval.

    Pure stdlib: the t quantile is obtained by bisecting the regularised
    incomplete beta, so this module has no third-party dependency.
    """
    d = [float(x) for x in deltas]
    n = len(d)
    if n < 2:
        raise DataError(f"paired_t(): needs at least 2 seeds, got {n}")
    df = n - 1
    m = mean(d)
    s = sd(d)
    se = s / math.sqrt(n)
    if se == 0.0:
        # Zero dispersion. If the mean is also zero every delta was EXACTLY zero
        # and the statistic is undefined (nan), not significant. If the mean is
        # non-zero the deltas were identical and non-zero: t is infinite and the
        # interval is degenerate at the mean. Both are reported as they are.
        t = math.inf if m > 0 else (-math.inf if m < 0 else float("nan"))
        return PairedT(m, m, m, t, df)
    t = m / se
    crit = t_ppf_two_sided(0.95, df)
    return PairedT(m, m - crit * se, m + crit * se, t, df)


def t_two_sided_p(t: float, df: int) -> float:
    """Two-sided p for Student's t via the regularised incomplete beta.

    Returns nan when ``t`` is nan. That is not an error state: ``paired_t``
    produces a nan t when every per-seed delta is EXACTLY zero, so both the mean
    and the variance vanish and the statistic is undefined rather than
    unmeasured. It happens in this corpus -- flood gemma3:27b, ministral3:14b and
    gemma4:e2b record zero rejections in every run of BOTH arms, so enforcement
    pressure is identically 0.00 and its delta has no dispersion to test. Report
    it as undefined; do not substitute a p of 1.
    """
    if df <= 0:
        raise DataError(f"t_two_sided_p(): df must be >= 1, got {df}")
    if t != t:
        return float("nan")
    if math.isinf(t):
        return 0.0
    x = df / (df + t * t)
    return _betainc(df / 2.0, 0.5, x)


def t_ppf_two_sided(conf: float, df: int) -> float:
    """Critical t for a two-sided interval of coverage ``conf`` (e.g. 0.95)."""
    if not 0.0 < conf < 1.0:
        raise DataError(f"t_ppf_two_sided(): conf must be in (0,1), got {conf}")
    target = 1.0 - conf
    lo, hi = 0.0, 1e3
    for _ in range(300):
        mid = 0.5 * (lo + hi)
        if t_two_sided_p(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _betainc(a: float, b: float, x: float) -> float:
    """Regularised incomplete beta I_x(a, b), Lentz continued fraction."""
    if x <= 0:
        return 0.0
    if x >= 1:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1 - x) * b - lbeta) / a
    f, c, d = 1.0, 1.0, 0.0
    for i in range(300):
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
    return min(max(front * (f - 1.0), 0.0), 1.0)


def cell_mean(per_seed: dict[int, float]) -> float:
    """A cell statistic = the MEAN OF THE PER-SEED RATES, not the pooled rate.

    This is the published convention and the two differ. VERIFIED on the anchor
    governed arm: pooled conditional = 36.26, mean of per-seed rates = 36.05, and
    36.05 is the number in the paper.
    """
    if not per_seed:
        raise DataError("cell_mean(): empty per-seed map")
    return mean(per_seed.values())


# =============================================================================
# Per-seed / per-run statistic helpers
# =============================================================================
def irrigation_per_seed(
    arm: str,
    prefix,
    stat: Callable[[list[dict]], float],
    source: str = "sim",
) -> dict[int, float]:
    """``{seed: stat(rows)}`` for one irrigation cell. ``source`` is "sim" or "audit"."""
    loader = {"sim": load_sim, "audit": load_audit}.get(source)
    if loader is None:
        raise DataError(f"source must be 'sim' or 'audit', got {source!r}")
    return {s: stat(loader(d)) for s, d in irrigation_runs(arm, prefix).items()}


def irrigation_per_seed_executed(arm: str, prefix, stat_name: str) -> dict[int, float]:
    """Per-seed conditional/unconditional rate under the EXECUTED action reading.

    ``stat_name`` is "conditional" or "unconditional". Joins each run's sim and
    audit csv and applies the ``maintain_demand`` substitution on rejected rows.
    """
    if stat_name not in ("conditional", "unconditional"):
        raise DataError(f"stat_name must be conditional|unconditional, got {stat_name!r}")
    out = {}
    for seed, d in irrigation_runs(arm, prefix).items():
        pairs = join_sim_audit(d)
        base = pairs if stat_name == "unconditional" else [p for p in pairs if is_high(p[0])]
        if not base:
            raise DataError(f"empty base for {stat_name} in {d}")
        hits = sum(
            1 for s_row, a_row in base
            if executed_action(s_row, status(a_row)) in INCREASE
        )
        out[seed] = 100.0 * hits / len(base)
    return out


def flood_per_run(arm: str, model, stat: Callable[[list[dict]], float]) -> dict[int, float]:
    """``{run index: stat(audit rows)}`` for one flood cell. Audit csv only."""
    return {r: stat(load_audit(d)) for r, d in flood_runs(arm, model).items()}


# =============================================================================
# Self-test
# =============================================================================
def _fmt(x, w=8, p=2):
    if x is None:
        return " " * (w - 1) + "-"
    if isinstance(x, float) and (x != x):
        return " " * (w - 3) + "nan"
    return f"{x:{w}.{p}f}"


def _selftest_guards() -> list[str]:
    """Actively try to reach every forbidden thing. Each MUST fail."""
    problems = []

    def must_raise(desc, fn):
        try:
            fn()
        except DataError:
            return
        except Exception as exc:                      # noqa: BLE001
            problems.append(f"{desc}: raised {type(exc).__name__}, expected DataError")
            return
        problems.append(f"GUARD FAILED -- {desc} did NOT raise")

    must_raise(
        "Group_A reachable via _reject_contaminated",
        lambda: _reject_contaminated(
            os.path.join(FLOOD_RESULTS, "JOH_FINAL", "gemma3_4b", "Group_A", "Run_1")),
    )
    must_raise(
        "Run_1_bak_broker reachable",
        lambda: _reject_contaminated(
            os.path.join(FLOOD_RESULTS, "JOH_FINAL", "ministral3_3b", "Group_A",
                         "Run_1_bak_broker")),
    )
    must_raise(
        "_QUARANTINE_* reachable",
        lambda: _reject_contaminated(
            os.path.join(FLOOD_RESULTS, "_QUARANTINE_reflection_missing_2026-05-30",
                         "gemma3_4b", "Run_1")),
    )
    must_raise(
        "_logs reachable",
        lambda: _reject_contaminated(os.path.join(FLOOD_RESULTS, "JOH_FINAL", "_logs")),
    )
    must_raise(
        "path outside both results roots returned",
        lambda: _reject_contaminated(os.path.join(REPO, "broker")),
    )
    must_raise("unknown arm accepted", lambda: irrigation_runs("governed", ""))
    must_raise("unknown irrigation model accepted", lambda: irrigation_runs("gov", "llama_"))
    must_raise("unknown flood model accepted", lambda: flood_runs("gov", "gpt4"))
    # Seed 999, not seed 44. This case asserts that asking for a seed that does not
    # exist raises rather than silently returning nothing, and it used to name
    # ministral3:8b no-validator seed 44 -- a seed that was absent when the check was
    # written and was RUN on 2026-08-03, at which point the guard began failing. It
    # was a correct failure: the check had quietly stopped testing what it claimed.
    # The replacement is outside the design's seed range (42-46) and no run will ever
    # be named for it, so the case cannot expire the same way.
    must_raise("absent irrigation seed accepted", lambda: irrigation_run("noval", "ministral3_8b_", 999))
    must_raise("absent flood run accepted", lambda: flood_run("gov", "gemma3:4b", 9))
    must_raise(
        "conditional_rate accepted flood rows",
        lambda: conditional_rate(load_audit(flood_run("gov", "gemma3:4b", 1))),
    )
    must_raise(
        "executed_action accepted a flood row",
        lambda: executed_action(load_audit(flood_run("gov", "gemma3:4b", 1))[0], "APPROVED"),
    )
    must_raise("paired_t accepted n=1", lambda: paired_t([1.0]))

    # DELTA must be keyword-only
    try:
        DELTA(1.0, 2.0)                                # type: ignore[misc]
        problems.append("GUARD FAILED -- DELTA accepted positional arguments")
    except TypeError:
        pass

    # No run directory this module returns may contain a forbidden segment.
    for m in IRRIGATION_MODELS:
        for arm in ARMS:
            for d in irrigation_runs(arm, m.prefix).values():
                _reject_contaminated(d)
    for fm in FLOOD_MODELS:
        for arm in ARMS:
            for d in flood_runs(arm, fm).values():
                _reject_contaminated(d)
                if os.path.basename(os.path.dirname(d)) != _FLOOD_ARM_GROUP[arm]:
                    problems.append(f"GUARD FAILED -- {d} is not under {_FLOOD_ARM_GROUP[arm]}")
    return problems


def _main() -> int:
    print("=" * 100)
    print("_data.py SELF-TEST")
    print("=" * 100)
    print(f"REPO               = {REPO}")
    print(f"IRRIGATION_RESULTS = {IRRIGATION_RESULTS}")
    print(f"FLOOD_RESULTS      = {FLOOD_RESULTS}")
    print(f"SIGN CONVENTION    : {DELTA_LABEL}")
    print()

    # ---- 1. contamination guards -------------------------------------------
    print("-" * 100)
    print("1. CONTAMINATION GUARDS (every one of these MUST refuse)")
    print("-" * 100)
    probs = _selftest_guards()
    if probs:
        for p in probs:
            print("  !!", p)
    else:
        print("  all 15 guards refused as required; all returned run dirs are clean")
    print()

    # ---- 2. irrigation inventory -------------------------------------------
    print("-" * 100)
    print("2. IRRIGATION INVENTORY (both arms selected by the identical mechanism)")
    print("-" * 100)
    hdr = f"{'model':14s} {'arm':16s} {'seeds':18s} {'n':>2s} {'rows/run':>9s} {'unparsed%':>10s} {'bal':>6s}"
    print(hdr)
    print("-" * len(hdr))
    ok = True
    for m in IRRIGATION_MODELS:
        bal = seed_sets(m.prefix)
        for arm in ARMS:
            runs = irrigation_runs(arm, m.prefix)
            counts = sorted({len(load_sim(d)) for d in runs.values()})
            unp = mean(irrigation_per_seed(arm, m.prefix, unparsed_share).values())
            flag = "" if counts == [IRRIGATION_EXPECTED_ROWS] else "   <- NOT 3276"
            if counts != [IRRIGATION_EXPECTED_ROWS]:
                ok = False
            print(f"{m.label:14s} {ARM_DISPLAY[arm]:16s} "
                  f"{','.join(str(s) for s in sorted(runs)):18s} {len(runs):>2d} "
                  f"{','.join(str(c) for c in counts):>9s} {unp:>10.2f} "
                  f"{str(bal.balanced):>6s}{flag}")
        if not bal.balanced:
            print(f"{'':14s} {'UNBALANCED':16s} gov={list(bal.gov_seeds)} "
                  f"noval={list(bal.noval_seeds)} -> excluded from paired contrasts"
                  f" ({excluded_from_paired(m.prefix)})")
    print()

    # ---- 3. flood inventory -------------------------------------------------
    print("-" * 100)
    print("3. FLOOD INVENTORY (Group_C / Group_C_disabled named literally)")
    print("-" * 100)
    hdr = (f"{'model':14s} {'arm':16s} {'runs':14s} {'audit rows':>22s} "
           f"{'coverage% of 1000':>19s} {'bal':>5s}")
    print(hdr)
    print("-" * len(hdr))
    for fm in FLOOD_MODELS:
        bal = flood_seed_sets(fm)
        for arm in ARMS:
            runs = flood_runs(arm, fm)
            rc = [len(load_audit(d)) for _, d in sorted(runs.items())]
            cov = [flood_audit_coverage(d) for _, d in sorted(runs.items())]
            print(f"{fm.label:14s} {ARM_DISPLAY[arm]:16s} "
                  f"{','.join(str(r) for r in sorted(runs)):14s} "
                  f"{','.join(str(c) for c in rc):>22s} "
                  f"{min(cov):>8.1f}-{max(cov):<10.1f} {str(bal.balanced):>5s}")
    print()
    print("  flood manifest-seed alignment (arms compared run-by-run):")
    for fm in FLOOD_MODELS:
        al = flood_seed_alignment(fm)
        mark = "" if al.aligned else "   <== MANIFEST SEEDS DISAGREE ACROSS ARMS"
        print(f"    {al.label:14s} gov={list(al.gov_manifest_seeds)} "
              f"noval={list(al.noval_manifest_seeds)}{mark}")
    print("  -> flood_runs() keys on the RUN INDEX, not the manifest seed. See its docstring.")
    print()

    # ---- 4. sim/audit join --------------------------------------------------
    print("-" * 100)
    print("4. SIM/AUDIT JOIN + ACTION-COLUMN IDENTITY (anchor irrigation, both arms)")
    print("-" * 100)
    for arm in ARMS:
        tot = mism = 0
        for seed, d in irrigation_runs(arm, "").items():
            for s_row, a_row in join_sim_audit(d):
                tot += 1
                if s_row["yearly_decision"].strip() != a_row["final_skill"].strip():
                    mism += 1
        print(f"  {ARM_DISPLAY[arm]:16s} joined rows {tot:6d}   "
              f"sim.yearly_decision != audit.final_skill : {mism}")
        if mism:
            ok = False
    print()

    # ---- 5. rejection taxonomy ---------------------------------------------
    print("-" * 100)
    print("5. REJECTION TAXONOMY -- the two rule layers (anchor irrigation, 5 seeds)")
    print("-" * 100)
    print(f"  {'arm':18s} {'rejected':>10s} {'/ total':>9s} {'rate%':>7s} "
          f"{'named rule':>11s} {'precond':>9s}")
    for arm in ARMS:
        tot = rej = th = pc = 0
        for seed, d in irrigation_runs(arm, "").items():
            for r in load_audit(d):
                tot += 1
                c = rejection_cause(r)
                if c is None:
                    continue
                rej += 1
                th += c == "theory"
                pc += c == "precondition"
        print(f"  {ARM_DISPLAY[arm]:18s} {rej:>10d} {tot:>9d} {100*rej/tot:>7.1f} "
              f"{th:>11d} {pc:>9d}   "
              f"({100*th/rej:.0f}% named a validator rule"
              f" / {100*pc/rej:.0f}% bare precondition)")
    print("  expected: no-validator 4,757/16,380 (29.0%) all bare precondition;"
          " with-validators 6,469/16,380 (39.5%) all named a validator rule.")
    print("  NOTE: 'named a validator rule' is NOT 'behavioural theory'. The stack holds")
    print("        both kinds; only 3,840/6,469 (59.4%) of governed rejections name an")
    print("        APPRAISAL-conditioned rule, 2,629 (40.6%) name only world-conditioned")
    print("        ones. The '100% behavioural theory' form was retracted 2026-07-31.")
    print()

    # ---- 6. anchor rates ----------------------------------------------------
    print("-" * 100)
    print("6. ANCHOR CELL gemma3:4b -- cell means over 5 seeds, LAST-PROPOSED reading")
    print("-" * 100)
    print(f"  {'statistic':26s} {'with-valid':>11s} {'no-valid':>11s} "
          f"{'Delta':>9s} {'brief':>24s}")
    expect = {
        "conditional rate": (36.05, 59.07, 23.02),
        "unconditional rate": (40.90, 62.52, 21.62),
        "HIGH-appraisal prevalence": (37.08, 82.80, 45.73),
    }
    fns = {
        "conditional rate": conditional_rate,
        "unconditional rate": unconditional_rate,
        "HIGH-appraisal prevalence": high_share,
    }
    for name, fn in fns.items():
        g = cell_mean(irrigation_per_seed("gov", "", fn))
        n = cell_mean(irrigation_per_seed("noval", "", fn))
        d = DELTA(noval=n, gov=g)
        eg, en, ed = expect[name]
        bad = any(abs(a - b) > 0.005 for a, b in ((g, eg), (n, en), (d, ed)))
        print(f"  {name:26s} {g:>11.2f} {n:>11.2f} {d:>9.2f} "
              f"{eg:>8.2f}/{en:.2f}/{ed:+.2f}{'   <== MISMATCH' if bad else ''}")
        if bad:
            ok = False
    print()

    # ---- 7. paired_t machinery ---------------------------------------------
    print("-" * 100)
    print("7. paired_t() VALIDATION -- anchor, YEAR 1 only (pre-decision state columns match exactly)")
    print("-" * 100)
    print("   brief expects ALL NULL: HIGH prevalence +3.33 (-3.75, +10.42);")
    print("   conditional -1.15 (-7.00, +4.71); unconditional +1.28 (-0.31, +2.87)")
    y1 = lambda rows: [r for r in rows if str(r.get("year", "")).strip() == "1"]
    for name, fn, exp in (
        ("HIGH prevalence", high_share, (3.33, -3.75, 10.42)),
        ("conditional", conditional_rate, (-1.15, -7.00, 4.71)),
        ("unconditional", unconditional_rate, (1.28, -0.31, 2.87)),
    ):
        deltas = []
        for seed in paired_seeds(""):
            g = fn(y1(load_sim(irrigation_run("gov", "", seed))))
            n = fn(y1(load_sim(irrigation_run("noval", "", seed))))
            deltas.append(DELTA(noval=n, gov=g))
        res = paired_t(deltas)
        bad = any(abs(a - b) > 0.02 for a, b in zip((res.mean, res.ci_lo, res.ci_hi), exp))
        print(f"  {name:18s} mean {res.mean:+7.2f}  95% CI ({res.ci_lo:+7.2f}, "
              f"{res.ci_hi:+7.2f})  t={res.t:+6.2f} df={res.df}  "
              f"p={t_two_sided_p(res.t, res.df):.3f}"
              f"{'   <== MISMATCH vs brief' if bad else ''}")
        if bad:
            ok = False
    print(f"  t_ppf_two_sided(0.95, 4) = {t_ppf_two_sided(0.95, 4):.6f}  (textbook 2.776445)")
    print()

    print("=" * 100)
    verdict = "CLEAN" if (ok and not probs) else "ANOMALIES ABOVE -- READ THEM"
    print(f"SELF-TEST: {verdict}")
    print("=" * 100)
    return 0 if (ok and not probs) else 1


if __name__ == "__main__":
    sys.exit(_main())
