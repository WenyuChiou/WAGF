#!/usr/bin/env python
"""corpus_inventory.py -- what is on disk, what is paired, what each analysis covers.

    python SUBMISSION_2026/TAE/evidence/corpus_inventory.py

WHY THIS EXISTS
    "Which cells, which seeds, is it enough" was answered three separate times by
    ad-hoc directory queries, and the same table was re-derived by hand each time.
    Prose goes stale silently; a directory listing does not. Everything printed
    below is READ OFF DISK at the moment of the run. Nothing here is asserted.

    Four stale claims were caught by accident rather than by a check on
    2026-08-03. This command is the check. It is meant to be run before touching
    NUMBERS.md, STATUS.md or SUBMISSION_READINESS.md, and it is meant to be
    runnable WHILE AN EXPERIMENT IS WRITING -- a directory with a growing trace
    file and no simulation_log.csv is a legitimate state, reported as IN PROGRESS,
    not as missing and not as a crash.

WHAT IT PRINTS
    1. INVENTORY        one row per cell x arm: seeds, decision rows per seed,
                        required columns, COMPLETE / IN PROGRESS / PARTIAL
    2. PAIRING          governed seeds against no-validator seeds, per cell
    3. COVERAGE         cell x analysis matrix, derived from the scripts
    4. GAPS             the specific runs that would close each gap
    5. CROSS-CHECK      this file's discovery against _data.py's own rules
    6. VERDICT          one line, and an exit code

CROSS-CHECK, AND WHY IT IS SECTION 5 RATHER THAN A FOOTNOTE
    This script discovers runs INDEPENDENTLY of ``_data.py``: its own regex, its
    own filesystem walk, no allow-list filtering during discovery. It then asks
    ``_data.py`` the same questions and DIFFS the two answers. A disagreement is
    not an inconvenience to be smoothed over -- it is the finding. The specific
    defect anticipated: ``_data.IRRIGATION_UNBALANCED_PREFIXES`` is a hardcoded
    exclusion whose stated reason ("3 governed seeds vs 2 no-validator") stops
    being true the moment the missing no-validator run lands. A hardcoded
    exclusion that outlives its reason silently drops a cell from every paired
    contrast in the paper. This section is what notices.

EXIT CODE
    0  every cell COMPLETE and BALANCED, and no disagreement with _data.py
    2  the ONLY outstanding item is a run IN PROGRESS -- not a failure, come back
       when it lands
    1  anything else: a PARTIAL or STALLED run, an unbalanced cell, a stale
       exclusion, a model on disk that no allow-list knows, or _data.py refusing
       a cell this script can see

    Exit 1 while a run is in progress is possible and is NOT a bug in this
    script: an in-progress run can BREAK an analysis module that was written to
    refuse partial cells, and that breakage outranks "come back later".

NO PERSONAL DATA. This script reads CSV headers, counts rows, and stats files.
It never prints a cell value from any respondent-derived column.
Standard library only. Python 3.
"""

from __future__ import annotations

import ast
import csv
import os
import re
import sys
import time

csv.field_size_limit(min(2**31 - 1, sys.maxsize))

HERE = os.path.abspath(os.path.dirname(__file__))
TAE = os.path.dirname(HERE)
REPO = os.path.abspath(os.path.join(TAE, "..", ".."))

sys.path.insert(0, HERE)
import _data as D  # noqa: E402  the module under cross-check, imported deliberately

# --------------------------------------------------------------------------- knobs
#: A run directory with no simulation_log.csv but a trace file touched more
#: recently than this is IN PROGRESS. Older than this and nothing is writing to
#: it, so it is STALLED -- the silent-death mode this corpus has hit before
#: (exit 0, empty output). Stated rather than tuned.
IN_PROGRESS_MAX_AGE_MIN = 45.0

#: Relative path of the streaming trace, taken from _data so it cannot drift.
IRRIGATION_TRACES = D.IRRIGATION_TRACES

#: Design row counts, taken from _data so they cannot drift.
IRRIGATION_EXPECTED_ROWS = D.IRRIGATION_EXPECTED_ROWS   # 78 agents x 42 years
FLOOD_EXPECTED_SIM_ROWS = D.FLOOD_EXPECTED_SIM_ROWS     # 100 agents x 10 years

#: Irrigation run-directory names, discovered INDEPENDENTLY of _data.py: any
#: arm token, any model infix, any seed. Deliberately looser than _data.py's
#: pattern so that a cell _data.py cannot see still shows up here.
IRR_DIR_RE = re.compile(r"^(production|ungoverned)_v21_42yr_(.*?)seed(\d+)$")
IRR_ARM_OF_TOKEN = {v: k for k, v in D._IRRIGATION_ARM_TOKEN.items()}

FLOOD_RUN_RE = re.compile(r"^Run_(\d+)$")

STATUS_COMPLETE = "COMPLETE"
STATUS_IN_PROGRESS = "IN PROGRESS"
STATUS_STALLED = "STALLED"
STATUS_PARTIAL = "PARTIAL"


# =============================================================================
# Required columns -- derived from _data.py's accessors, never retyped
# =============================================================================
def _required_columns() -> dict[str, dict[str, tuple[tuple[str, ...], ...]]]:
    """What each file must carry for the analyses to run, read out of _data.py.

    Each entry is a tuple of ALTERNATIVE GROUPS: the group is satisfied when ANY
    of its names is present. That is not a loosening -- it is exactly the
    semantics of ``_data._APPRAISAL_COLS`` and ``_data._ACTION_COLS``, which are
    RESOLUTION ORDERS, first match wins. The two files genuinely differ: the
    irrigation simulation_log carries ``yearly_decision`` and the audit carries
    ``final_skill``, and ``_data.action()`` reads whichever is there. Requiring
    both would fail every run in the corpus while nothing is actually wrong.

    ``join_sim_audit`` keys on (agent_id, year); ``status()`` is audit-only.
    Reading the accessors here means a column rename in _data.py changes this
    check automatically instead of leaving it asserting a stale set.
    """
    def appraisal(tb):
        return tuple(c for c, t in D._APPRAISAL_COLS if t == tb)
    action = (tuple(D._ACTION_COLS),)
    join = (("agent_id",), ("year",))
    return {
        "irrigation": {
            # the sim log's appraisal column is the first irrigation entry
            "sim": join + ((appraisal("irrigation")[0],),) + action,
            "audit": join + (("status",),) + (appraisal("irrigation"),) + action,
        },
        "flood": {
            "sim": join + action,
            "audit": join + (("status",),) + (appraisal("flood"),) + action,
        },
    }


REQUIRED = _required_columns()


def _header(path: str) -> list[str]:
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for row in csv.reader(fh):
            return [c.strip() for c in row]
    return []


def _count_decision_rows(path: str, action_cols: tuple[str, ...]) -> tuple[int, list[str]]:
    """(rows with a non-blank action cell, header). One streaming pass, csv-aware.

    csv-aware because the reasoning columns contain embedded newlines; counting
    b'\\n' would over-count by a large and varying margin.
    """
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rd = csv.reader(fh)
        try:
            head = [c.strip() for c in next(rd)]
        except StopIteration:
            return 0, []
        idx = next((head.index(c) for c in action_cols if c in head), None)
        if idx is None:
            return sum(1 for _ in rd), head
        n = 0
        for row in rd:
            if len(row) > idx and row[idx].strip():
                n += 1
        return n, head


def _age_minutes(path: str) -> float:
    return (time.time() - os.path.getmtime(path)) / 60.0


def _missing(head: list[str], required) -> list[str]:
    """Groups with no member present. A group of one prints as itself."""
    have = set(head)
    return ["|".join(g) for g in required if not (set(g) & have)]


# =============================================================================
# 1. Independent discovery
# =============================================================================
class Run:
    __slots__ = ("testbed", "cell", "arm", "key", "path", "status", "rows",
                 "expected", "missing_cols", "note", "audit_rows")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


def scan_irrigation() -> list[Run]:
    root = D.IRRIGATION_RESULTS
    known = {m.prefix: m.label for m in D.IRRIGATION_MODELS}
    out: list[Run] = []
    if not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        path = os.path.join(root, name)
        if not os.path.isdir(path):
            continue
        m = IRR_DIR_RE.fullmatch(name)
        if not m:
            continue
        token, infix, seed = m.group(1), m.group(2), int(m.group(3))
        cell = known.get(infix, "UNKNOWN<%s>" % (infix or "(anchor infix)"))
        arm = IRR_ARM_OF_TOKEN[token]
        sim = os.path.join(path, D.IRRIGATION_SIM)
        aud = os.path.join(path, D.IRRIGATION_AUDIT)
        trace = os.path.join(path, IRRIGATION_TRACES)

        rows, miss, note, audit_rows = None, [], "", None
        if os.path.isfile(sim):
            rows, head = _count_decision_rows(sim, tuple(D._ACTION_COLS))
            miss = _missing(head, REQUIRED["irrigation"]["sim"])
            if os.path.isfile(aud):
                miss += ["audit:" + c for c in
                         _missing(_header(aud), REQUIRED["irrigation"]["audit"])]
            else:
                miss += ["audit:<file absent>"]
            if rows == IRRIGATION_EXPECTED_ROWS and not miss:
                status = STATUS_COMPLETE
            else:
                status = STATUS_PARTIAL
                note = "rows %s/%s" % (rows, IRRIGATION_EXPECTED_ROWS)
        elif os.path.isfile(trace):
            age = _age_minutes(trace)
            mb = os.path.getsize(trace) / 1e6
            if age <= IN_PROGRESS_MAX_AGE_MIN:
                status = STATUS_IN_PROGRESS
                note = "trace %.1f MB, touched %.0f min ago; no %s yet" % (
                    mb, age, D.IRRIGATION_SIM)
            else:
                status = STATUS_STALLED
                note = "trace %.1f MB, LAST TOUCHED %.0f min ago, no %s" % (
                    mb, age, D.IRRIGATION_SIM)
        else:
            status = STATUS_PARTIAL
            note = "no %s and no %s" % (D.IRRIGATION_SIM, IRRIGATION_TRACES)

        out.append(Run(testbed="irrigation", cell=cell, arm=arm, key=seed,
                       path=path, status=status, rows=rows,
                       expected=IRRIGATION_EXPECTED_ROWS, missing_cols=miss,
                       note=note, audit_rows=audit_rows))
    return out


def scan_flood() -> list[Run]:
    out: list[Run] = []
    if not os.path.isdir(D.FLOOD_RESULTS):
        return out
    for spec in D.FLOOD_MODELS:
        for arm in D.ARMS:
            base = spec.gov_base if arm == "gov" else spec.noval_base
            group = D._FLOOD_ARM_GROUP[arm]
            gdir = os.path.join(D.FLOOD_RESULTS, base, spec.model_dir, group)
            if not os.path.isdir(gdir):
                out.append(Run(testbed="flood", cell=spec.label, arm=arm, key=0,
                               path=gdir, status=STATUS_PARTIAL, rows=None,
                               expected=FLOOD_EXPECTED_SIM_ROWS, missing_cols=[],
                               note="group directory absent", audit_rows=None))
                continue
            for name in sorted(os.listdir(gdir)):
                mm = FLOOD_RUN_RE.fullmatch(name)
                if not mm:
                    continue
                path = os.path.join(gdir, name)
                if not os.path.isdir(path):
                    continue
                sim = os.path.join(path, D.FLOOD_SIM)
                aud = os.path.join(path, D.FLOOD_AUDIT)
                rows, miss, note, arows = None, [], "", None
                if os.path.isfile(sim):
                    rows, head = _count_decision_rows(sim, tuple(D._ACTION_COLS))
                    miss = _missing(head, REQUIRED["flood"]["sim"])
                    if os.path.isfile(aud):
                        arows, ahead = _count_decision_rows(aud, tuple(D._ACTION_COLS))
                        miss += ["audit:" + c for c in
                                 _missing(ahead, REQUIRED["flood"]["audit"])]
                    else:
                        miss += ["audit:<file absent>"]
                    if rows == FLOOD_EXPECTED_SIM_ROWS and not miss:
                        status = STATUS_COMPLETE
                    else:
                        status = STATUS_PARTIAL
                        note = "sim rows %s/%s" % (rows, FLOOD_EXPECTED_SIM_ROWS)
                else:
                    status = STATUS_PARTIAL
                    note = "no %s" % D.FLOOD_SIM
                out.append(Run(testbed="flood", cell=spec.label, arm=arm,
                               key=int(mm.group(1)), path=path, status=status,
                               rows=rows, expected=FLOOD_EXPECTED_SIM_ROWS,
                               missing_cols=miss, note=note, audit_rows=arows))
    return out


# =============================================================================
# 3. Analysis coverage -- derived from the scripts, not from a list kept by hand
# =============================================================================
COVERAGE_RULES = """\
    R0  TESTBED first. Five model labels (gemma3:4b, gemma3:12b, gemma4:e2b,
        gemma4:e4b, ministral3:8b) name BOTH an irrigation cell and a flood cell,
        so a label alone cannot say which. A script counts as touching a testbed
        only if it references one of _data.py's own irrigation*/flood* symbols,
        or names that testbed's results directory in a string. Rules R1-R4 are
        then intersected with the testbeds R0 found.
    R1  a module-level dict literal named CELLS whose keys are model labels
        -> exactly those cells                    (e4, _verify_pipeline)
    R2  else, the name IRRIGATION_MODELS / FLOOD_MODELS appears
        -> every cell of that testbed's allow-list
    R3  else, the name IRRIGATION_ANCHOR appears  -> the anchor cell only
    R4  else, a non-docstring string literal equal to a model label
        -> that cell
    R5  else, a non-docstring string literal carrying a run-directory pattern
        "_v21_42yr_<infix>seed" with a LITERAL infix -> the cell that infix names.
        This is what catches the scripts that glob the results directory
        themselves instead of importing _data.py; an empty infix is the anchor.
        An infix interpolated at runtime is not resolvable here and does not match.
    R6  else                                      -> no cell dependency"""

#: The run-directory shape, built from _data.py's own arm token so the literal
#: "v21_42yr" is not retyped here. Used only to read other scripts' source.
_INFIX_RE = re.compile(r"_v21_42yr_(\w*?)seed")

#: _data.py's own public symbols, split by the testbed their name declares.
#: Read from the module rather than typed out, so a new accessor is picked up.
_IRR_SYMBOLS = frozenset(n for n in dir(D) if n.lower().startswith("irrigation"))
_FLOOD_SYMBOLS = frozenset(n for n in dir(D) if n.lower().startswith("flood"))

#: For the scripts that do not import _data.py and build their own paths.
_IRR_PATH_TOKEN = os.path.basename(os.path.dirname(D.IRRIGATION_RESULTS))  # irrigation_abm
_FLOOD_PATH_TOKEN = os.path.basename(os.path.dirname(D.FLOOD_RESULTS))     # single_agent

SKIP_SCRIPTS = {"_data.py", "corpus_inventory.py", "run_all.py"}


def _module_cells_dict(tree: ast.AST, labels: set[str]) -> set[str] | None:
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        names = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "CELLS" not in names or not isinstance(node.value, ast.Dict):
            continue
        keys = {k.value for k in node.value.keys
                if isinstance(k, ast.Constant) and isinstance(k.value, str)}
        hit = keys & labels
        if hit:
            return hit
    return None


def _docstring_nodes(tree: ast.AST) -> set[int]:
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _testbeds_touched(names: set[str], strings: set[str]) -> set[str]:
    """R0. Which testbed(s) a script actually reaches, independent of labels."""
    out = set()
    if (names & _IRR_SYMBOLS) or any(_IRR_PATH_TOKEN in s for s in strings):
        out.add("irrigation")
    if (names & _FLOOD_SYMBOLS) or any(_FLOOD_PATH_TOKEN in s for s in strings):
        out.add("flood")
    return out


def analysis_coverage():
    """(scripts, {script: {(testbed, label)}}, {script: rule}, {script: testbeds})."""
    irr_labels = [m.label for m in D.IRRIGATION_MODELS]
    flood_labels = [m.label for m in D.FLOOD_MODELS]
    labels = set(irr_labels) | set(flood_labels)
    scripts, covers, rule_used, tbs = [], {}, {}, {}
    for fn in sorted(os.listdir(HERE)):
        if not fn.endswith(".py") or fn in SKIP_SCRIPTS:
            continue
        src = open(os.path.join(HERE, fn), encoding="utf-8").read()
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        scripts.append(fn)
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        docs = _docstring_nodes(tree)
        strings = {n.value for n in ast.walk(tree)
                   if isinstance(n, ast.Constant) and isinstance(n.value, str)
                   and id(n) not in docs}
        touched = _testbeds_touched(names, strings)
        tbs[fn] = touched

        def keep(pairs):
            return {(tb, lab) for tb, lab in pairs if tb in touched}

        hit = _module_cells_dict(tree, labels)
        if hit is not None:
            covers[fn] = keep({(tb, lab) for lab in hit
                               for tb in ("irrigation", "flood")
                               if lab in (irr_labels if tb == "irrigation" else flood_labels)})
            rule_used[fn] = "R1 CELLS dict"
            continue
        got = set()
        if "IRRIGATION_MODELS" in names:
            got |= {("irrigation", lab) for lab in irr_labels}
        if "FLOOD_MODELS" in names:
            got |= {("flood", lab) for lab in flood_labels}
        if got:
            covers[fn], rule_used[fn] = keep(got), "R2 allow-list iteration"
            continue
        if "IRRIGATION_ANCHOR" in names:
            covers[fn] = keep({("irrigation", D.IRRIGATION_ANCHOR.label)})
            rule_used[fn] = "R3 anchor"
            continue
        lit = {s for s in strings if s in labels}
        if lit:
            covers[fn] = keep({(tb, lab) for lab in lit
                               for tb in ("irrigation", "flood")
                               if lab in (irr_labels if tb == "irrigation" else flood_labels)})
            rule_used[fn] = "R4 literal label"
            continue
        by_infix = {m.prefix: m.label for m in D.IRRIGATION_MODELS}
        infixes = {mm.group(1) for s in strings for mm in _INFIX_RE.finditer(s)}
        pat = {("irrigation", by_infix[i]) for i in infixes if i in by_infix}
        if pat:
            covers[fn], rule_used[fn] = keep(pat), "R5 run-dir pattern"
            continue
        covers[fn], rule_used[fn] = set(), "R6 none"
    return scripts, covers, rule_used, tbs


# =============================================================================
# printing helpers
# =============================================================================
def rule(ch="-", n=100):
    print(ch * n)


def head(title):
    print()
    rule("=")
    print(title)
    rule("=")


def _seedlist(xs) -> str:
    return ",".join(str(x) for x in sorted(xs)) if xs else "-"


# =============================================================================
# main
# =============================================================================
USAGE = """\
corpus_inventory.py -- is the experimental material enough?

Reads both results trees and reports what is actually on disk: which runs exist,
how many decision rows each holds, whether the required columns are present,
whether every cell has the same number of governed and no-validator runs, which
analyses have been run on which cell, and exactly which runs would close a gap.
It also cross-checks its own discovery against _data.py's allow-lists, so a
disagreement between the two is reported rather than smoothed over.

Takes no arguments. Writes nothing, anywhere. Never prints a respondent value.
A run that is still being written is detected as such and reported as IN
PROGRESS, not as damage.

Exit codes:
  0   every cell complete, balanced, and agreeing with _data.py
  2   nothing failed, but a run is still being written
  1   anything else -- the reason is printed above the verdict line
"""


def main() -> int:
    if any(a in ("-h", "--help") for a in sys.argv[1:]):
        print(USAGE, end="")
        return 0

    problems: list[str] = []          # -> exit 1
    in_progress: list[str] = []       # -> exit 2 if it is the only thing

    runs = scan_irrigation() + scan_flood()
    print("corpus inventory -- every number below was read off disk at %s"
          % time.strftime("%Y-%m-%d %H:%M:%S"))
    print("irrigation root : %s" % D.IRRIGATION_RESULTS)
    print("flood root      : %s" % D.FLOOD_RESULTS)
    print("run dirs seen   : %d irrigation, %d flood"
          % (sum(1 for r in runs if r.testbed == "irrigation"),
             sum(1 for r in runs if r.testbed == "flood")))

    # ---------------------------------------------------------------- 1. INVENTORY
    head("1. INVENTORY -- one row per cell x arm")
    print("looked at: <run dir>/%s row count (rows with a non-blank action cell),"
          % D.IRRIGATION_SIM)
    print("           the header of both csvs against the columns _data.py's")
    print("           accessors resolve, and mtime of %s for a run with no sim log."
          % IRRIGATION_TRACES)
    print("cols OK    = every required column present in BOTH csvs of EVERY listed seed.")
    for testbed, keyname, expected in (("irrigation", "seeds", IRRIGATION_EXPECTED_ROWS),
                                       ("flood", "runs", FLOOD_EXPECTED_SIM_ROWS)):
        sub = [r for r in runs if r.testbed == testbed]
        if not sub:
            continue
        print()
        print("%s  (expected %d decision rows per run)" % (testbed.upper(), expected))
        rule()
        print("%-14s %-16s %-14s %-22s %-7s %s"
              % ("cell", "arm", keyname, "rows/" + keyname[:-1], "cols OK", "state"))
        rule()
        cells = sorted({r.cell for r in sub})
        for cell in cells:
            for arm in D.ARMS:
                rs = sorted([r for r in sub if r.cell == cell and r.arm == arm],
                            key=lambda r: r.key)
                if not rs:
                    print("%-14s %-16s %-14s %-22s %-7s %s"
                          % (cell, D.ARM_DISPLAY[arm], "-", "-", "-", "ABSENT"))
                    problems.append("%s / %s / %s: arm absent entirely"
                                    % (testbed, cell, D.ARM_DISPLAY[arm]))
                    continue
                ok = [r for r in rs if r.status == STATUS_COMPLETE]
                bad = [r for r in rs if r.status != STATUS_COMPLETE]
                rowset = sorted({r.rows for r in ok if r.rows is not None})
                rowtxt = (",".join(str(x) for x in rowset) if rowset else "-")
                colsok = "yes" if all(not r.missing_cols for r in rs) else "NO"
                state = STATUS_COMPLETE if not bad else ", ".join(
                    "%s %s" % (r.status, r.key) for r in bad)
                print("%-14s %-16s %-14s %-22s %-7s %s"
                      % (cell, D.ARM_DISPLAY[arm], _seedlist(r.key for r in ok),
                         rowtxt, colsok, state))
                for r in bad:
                    print("%-14s %-16s   -> %s %s: %s"
                          % ("", "", keyname[:-1], r.key, r.note))
                    if r.missing_cols:
                        print("%-14s %-16s      missing columns: %s"
                              % ("", "", ", ".join(r.missing_cols)))
                    tag = "%s / %s / %s / %s %s" % (testbed, cell,
                                                    D.ARM_DISPLAY[arm],
                                                    keyname[:-1], r.key)
                    if r.status == STATUS_IN_PROGRESS:
                        in_progress.append(tag + " -- " + r.note)
                    else:
                        problems.append(tag + " is " + r.status + ": " + r.note)
                for r in ok:
                    if r.missing_cols:
                        problems.append("%s / %s / %s / %s %s missing columns: %s"
                                        % (testbed, cell, D.ARM_DISPLAY[arm],
                                           keyname[:-1], r.key,
                                           ", ".join(r.missing_cols)))
        if testbed == "flood":
            print()
            print("flood audit coverage (audit rows / %d design rows). The shortfall is"
                  % FLOOD_EXPECTED_SIM_ROWS)
            print("the documented F1 silent-drop, not a fault found here; printed so the")
            print("per-run denominator every flood rate uses stays visible.")
            rule()
            print("%-14s %-16s %s" % ("cell", "arm", "coverage per run"))
            rule()
            for cell in cells:
                for arm in D.ARMS:
                    rs = sorted([r for r in sub if r.cell == cell and r.arm == arm],
                                key=lambda r: r.key)
                    cov = ["%d%%" % round(100.0 * r.audit_rows / FLOOD_EXPECTED_SIM_ROWS)
                           if r.audit_rows is not None else "?" for r in rs]
                    print("%-14s %-16s %s" % (cell, D.ARM_DISPLAY[arm], " ".join(cov)))

    # ------------------------------------------------------------------ 2. PAIRING
    head("2. PAIRING -- governed against no-validator, per cell")
    print("looked at: the COMPLETE runs from section 1 only. A run IN PROGRESS is")
    print("           counted in the 'pending' column, never in 'paired'.")
    balance: dict[tuple[str, str], tuple[set, set, set, set]] = {}
    for testbed, keyname in (("irrigation", "seeds"), ("flood", "runs")):
        sub = [r for r in runs if r.testbed == testbed]
        if not sub:
            continue
        print()
        print("%s" % testbed.upper())
        rule()
        print("%-14s %-22s %-22s %-7s %-18s %s"
              % ("cell", "gov " + keyname, "noval " + keyname, "paired",
                 "pending", "balance"))
        rule()
        for cell in sorted({r.cell for r in sub}):
            g = {r.key for r in sub if r.cell == cell and r.arm == "gov"
                 and r.status == STATUS_COMPLETE}
            n = {r.key for r in sub if r.cell == cell and r.arm == "noval"
                 and r.status == STATUS_COMPLETE}
            pend = {(r.arm, r.key) for r in sub if r.cell == cell
                    and r.status == STATUS_IN_PROGRESS}
            paired = g & n
            bal = "BALANCED" if g == n and g else "UNBALANCED (%d gov vs %d noval)" % (
                len(g), len(n))
            balance[(testbed, cell)] = (g, n, paired, pend)
            pendtxt = " ".join("%s %s" % (D.ARM_DISPLAY[a], k)
                               for a, k in sorted(pend)) if pend else "-"
            print("%-14s %-22s %-22s %-7d %-18s %s"
                  % (cell, _seedlist(g), _seedlist(n), len(paired), pendtxt, bal))
            if g != n or not g:
                # An unbalance that the in-progress runs would close on their own
                # is a "come back later", not a defect. An unbalance they would
                # NOT close is a defect even while something else is writing.
                wg = g | {k for a, k in pend if a == "gov"}
                wn = n | {k for a, k in pend if a == "noval"}
                if pend and wg == wn and wg:
                    in_progress.append(
                        "%s / %s is UNBALANCED (%d gov vs %d noval) and the run(s) IN "
                        "PROGRESS would close it exactly" % (testbed, cell, len(g), len(n)))
                elif pend:
                    problems.append(
                        "%s / %s is UNBALANCED (%d gov vs %d noval) and the run(s) IN "
                        "PROGRESS would NOT close it (%s vs %s once they land)"
                        % (testbed, cell, len(g), len(n), _seedlist(wg), _seedlist(wn)))
                else:
                    problems.append("%s / %s is UNBALANCED (%d gov vs %d noval)"
                                    % (testbed, cell, len(g), len(n)))

    # ----------------------------------------------------------------- 3. COVERAGE
    head("3. ANALYSIS COVERAGE -- which analyses have actually been run on which cell")
    print("looked at: the source of every .py in %s, parsed with ast." % HERE)
    print("Derivation rules, applied in order, first hit wins:")
    print(COVERAGE_RULES)
    scripts, covers, rule_used, tbs = analysis_coverage()
    print()
    print("%-32s %-24s %s" % ("script", "testbeds reached (R0)", "rule that decided its cells"))
    rule()
    for fn in scripts:
        print("%-32s %-24s %s"
              % (fn, ", ".join(sorted(tbs[fn])) or "none", rule_used[fn]))
    for testbed, labels in (("irrigation", [m.label for m in D.IRRIGATION_MODELS]),
                            ("flood", [m.label for m in D.FLOOD_MODELS])):
        rel = [fn for fn in scripts if any(tb == testbed for tb, _ in covers[fn])]
        if not rel:
            continue
        cov = {fn: {lab for tb, lab in covers[fn] if tb == testbed} for fn in rel}
        usable = set()
        for c in labels:
            g, n, _p, _pd = balance.get((testbed, c), (set(), set(), set(), set()))
            if g and g == n:
                usable.add(c)
        print()
        print("%s cells x analyses" % testbed.upper())
        print("  x = the script names this cell AND section 2 says the cell is balanced")
        print("  ! = the script names this cell but the cell is NOT usable yet "
              "(unbalanced / a run still writing)")
        print("      -- naming a cell is not the same as having run on it")
        print("  blank = the script does not reach this cell at all")
        rule()
        w = max(len(f) for f in rel)
        print("%-*s | %s" % (w, "analysis", " ".join("%-13s" % c for c in labels)))
        rule()
        for fn in rel:
            marks = " ".join(
                "%-13s" % ("" if c not in cov[fn] else ("x" if c in usable else "!"))
                for c in labels)
            print("%-*s | %s" % (w, fn, marks))
        rule()
        uncovered = [c for c in labels if not any(c in cov[fn] for fn in rel)]
        if uncovered:
            print("cells NO analysis touches: %s" % ", ".join(uncovered))
        thin = {c: [fn for fn in rel if c in cov[fn]] for c in labels}
        worst = min(thin, key=lambda c: len(thin[c]))
        best = max(thin, key=lambda c: len(thin[c]))
        print("thinnest cell: %s (%d of %d analyses)   fullest: %s (%d of %d)"
              % (worst, len(thin[worst]), len(rel), best, len(thin[best]), len(rel)))
        for c in labels:
            if 0 < len(thin[c]) < len(rel):
                print("  %-14s not covered by: %s"
                      % (c, ", ".join(fn for fn in rel if c not in cov[fn])))

    # --------------------------------------------------------------------- 4. GAPS
    head("4. GAPS -- the specific runs that would close them")
    print("looked at: the seed sets in section 2. Tier A closes a PAIRING gap and")
    print("           changes what the paper may claim. Tier B raises a cell to the")
    print("           largest seed count any cell in that testbed already reaches")
    print("           (%d for irrigation), which is a power question, not a validity one."
          % max((len(g | n) for (tb, _c), (g, n, _p, _pd) in balance.items()
                 if tb == "irrigation"), default=0))
    tierA, tierB = [], []
    for (testbed, cell), (g, n, paired, pend) in sorted(balance.items()):
        target_here = g | n
        arm_dir = D._IRRIGATION_ARM_TOKEN if testbed == "irrigation" else None
        for arm, have in (("gov", g), ("noval", n)):
            for k in sorted(target_here - have):
                pending = (arm, k) in pend
                if testbed == "irrigation":
                    infix = D.irrigation_model(cell).prefix if not cell.startswith("UNKNOWN") else ""
                    name = "%s_v21_42yr_%sseed%d" % (arm_dir[arm], infix, k)
                else:
                    name = "%s Run_%d" % (cell, k)
                tierA.append("%-10s %-14s %-16s seed/run %-4s %s%s"
                             % (testbed, cell, D.ARM_DISPLAY[arm], k, name,
                                "   [IN PROGRESS NOW]" if pending else ""))
    for testbed in ("irrigation", "flood"):
        sizes = [len(g | n) for (tb, _c), (g, n, _p, _pd) in balance.items() if tb == testbed]
        if not sizes:
            continue
        target = max(sizes)
        # the seed labels the fullest cell uses -- what a thin cell would have to match
        full_keys: set = set()
        for (tb, _c), (g, n, _p, _pd) in balance.items():
            if tb == testbed and len(g | n) == target:
                full_keys |= (g | n)
        for (tb, cell), (g, n, _p, _pd) in sorted(balance.items()):
            if tb != testbed:
                continue
            for k in sorted(full_keys - (g | n)):
                for arm in D.ARMS:
                    if testbed == "irrigation":
                        infix = D.irrigation_model(cell).prefix if not cell.startswith("UNKNOWN") else ""
                        name = "%s_v21_42yr_%sseed%d" % (D._IRRIGATION_ARM_TOKEN[arm], infix, k)
                    else:
                        name = "%s Run_%d" % (cell, k)
                    tierB.append("%-10s %-14s %-16s seed/run %-4s %s"
                                 % (testbed, cell, D.ARM_DISPLAY[arm], k, name))
    print()
    print("TIER A -- required to balance a cell (%d run%s)"
          % (len(tierA), "" if len(tierA) == 1 else "s"))
    rule()
    print("\n".join(tierA) if tierA else "  none -- every cell present is balanced")
    print()
    print("TIER B -- optional, raises a thin cell to the fullest cell's seed set (%d runs)"
          % len(tierB))
    rule()
    print("\n".join(tierB) if tierB else "  none")

    # ---------------------------------------------------------------- 5. CROSS-CHECK
    head("5. CROSS-CHECK -- this file's discovery against _data.py's own rules")
    print("looked at: _data.irrigation_runs / flood_runs for every cell x arm, and")
    print("           _data.IRRIGATION_UNBALANCED_PREFIXES against the measured balance.")
    print("A disagreement here IS the finding; it is not smoothed over.")
    print()
    print("%-14s %-16s %-24s %-24s %s"
          % ("cell", "arm", "this file (COMPLETE)", "_data.py", "agree"))
    rule()
    disagree = 0
    for m in D.IRRIGATION_MODELS:
        for arm in D.ARMS:
            mine = {r.key for r in runs if r.testbed == "irrigation"
                    and r.cell == m.label and r.arm == arm
                    and r.status == STATUS_COMPLETE}
            try:
                theirs = set(D.irrigation_runs(arm, m.prefix))
                ttxt = _seedlist(theirs)
                ok = mine == theirs
            except D.DataError as e:
                theirs, ttxt, ok = None, "RAISES DataError", False
                msg = str(e).replace(REPO, "<repo>")
            print("%-14s %-16s %-24s %-24s %s"
                  % (m.label, D.ARM_DISPLAY[arm], _seedlist(mine), ttxt,
                     "yes" if ok else "NO <<<"))
            if not ok:
                disagree += 1
                if theirs is None:
                    for chunk in (msg[i:i + 88] for i in range(0, len(msg), 88)):
                        print("      _data.py: %s" % chunk)
                    problems.append(
                        "_data.py CANNOT READ %s / %s -- every script that imports it "
                        "fails on this cell" % (m.label, D.ARM_DISPLAY[arm]))
                else:
                    problems.append("_data.py disagrees on %s / %s: %s vs %s"
                                    % (m.label, D.ARM_DISPLAY[arm],
                                       _seedlist(mine), _seedlist(theirs)))
    for spec in D.FLOOD_MODELS:
        for arm in D.ARMS:
            mine = {r.key for r in runs if r.testbed == "flood"
                    and r.cell == spec.label and r.arm == arm
                    and r.status == STATUS_COMPLETE}
            try:
                theirs = set(D.flood_runs(arm, spec))
                ttxt, ok = _seedlist(theirs), mine == theirs
            except D.DataError as e:
                theirs, ttxt, ok = None, "RAISES DataError", False
                msg = str(e).replace(REPO, "<repo>")
            if not ok:
                disagree += 1
                print("%-14s %-16s %-24s %-24s %s"
                      % (spec.label, D.ARM_DISPLAY[arm], _seedlist(mine), ttxt, "NO <<<"))
                problems.append("_data.py disagrees on flood %s / %s"
                                % (spec.label, D.ARM_DISPLAY[arm]))
    print("(flood rows printed only on disagreement; %d flood cell x arm checked)"
          % (len(D.FLOOD_MODELS) * len(D.ARMS)))

    print()
    print("models on disk vs the IRRIGATION_MODELS allow-list")
    rule()
    unknown = sorted({r.cell for r in runs if r.cell.startswith("UNKNOWN")})
    if unknown:
        for u in unknown:
            print("  %s  <<< on disk, no allow-list entry -- invisible to every analysis" % u)
            problems.append("run directory for %s exists but no IRRIGATION_MODELS entry" % u)
    else:
        print("  every irrigation run directory on disk maps to an allow-list model.")

    print()
    print("IRRIGATION_UNBALANCED_PREFIXES -- is the hardcoded exclusion still true?")
    rule()
    for prefix in sorted(D.IRRIGATION_UNBALANCED_PREFIXES):
        label = D.irrigation_model(prefix).label
        g, n, paired, pend = balance.get(("irrigation", label), (set(), set(), set(), set()))
        if g == n and g:
            print("  %-14s excluded, but the cell is BALANCED (%s) <<< STALE EXCLUSION"
                  % (label, _seedlist(g)))
            problems.append(
                "STALE EXCLUSION: %s is in IRRIGATION_UNBALANCED_PREFIXES but its arms "
                "are balanced (%s); every paired contrast is dropping a usable cell"
                % (label, _seedlist(g)))
        elif pend:
            print("  %-14s excluded, %d gov vs %d noval -- still true, but a run is IN "
                  "PROGRESS (%s)" % (label, len(g), len(n),
                                     ",".join("%s %s" % (a, k) for a, k in sorted(pend))))
            print("  %-14s  -> the exclusion and its stated reason expire when that run "
                  "lands; re-run this command then." % "")
            in_progress.append(
                "IRRIGATION_UNBALANCED_PREFIXES entry for %s expires when the in-progress "
                "run lands" % label)
        else:
            print("  %-14s excluded, %d gov vs %d noval -- exclusion still earns its keep"
                  % (label, len(g), len(n)))
    for (tb, cell), (g, n, _p, _pd) in sorted(balance.items()):
        if tb != "irrigation" or cell.startswith("UNKNOWN"):
            continue
        if g != n and not D.excluded_from_paired(D.irrigation_model(cell).prefix):
            print("  %-14s UNBALANCED (%d vs %d) and NOT in the exclusion set <<<"
                  % (cell, len(g), len(n)))
            problems.append("%s is unbalanced but not in IRRIGATION_UNBALANCED_PREFIXES"
                            % cell)

    # ------------------------------------------------------------------ 6. VERDICT
    head("6. VERDICT")
    if in_progress:
        print("IN PROGRESS (%d):" % len(in_progress))
        for t in in_progress:
            print("  - %s" % t)
    # Severity order, so the verdict line names the worst thing rather than the
    # alphabetically first. A cell _data.py cannot read breaks every script that
    # imports it, which outranks a cell that is merely short a seed.
    def sev(p: str) -> int:
        if p.startswith("_data.py CANNOT READ"):
            return 0
        if p.startswith("STALE EXCLUSION"):
            return 1
        if p.startswith("_data.py disagrees"):
            return 2
        if "STALLED" in p or "missing columns" in p or "arm absent" in p:
            return 3
        if "is PARTIAL" in p:
            return 4
        return 5

    seen = []
    for p in problems:
        if p not in seen:
            seen.append(p)
    seen.sort(key=sev)
    if seen:
        print("PROBLEMS (%d):" % len(seen))
        for p in seen:
            print("  - %s" % p)
    print()
    if seen:
        print("VERDICT: FAIL -- %d problem%s; the first is: %s"
              % (len(seen), "" if len(seen) == 1 else "s", seen[0]))
        return 1
    if in_progress:
        print("VERDICT: NOT YET -- nothing is wrong; %d run%s still writing. Re-run when "
              "it lands." % (len(in_progress), "" if len(in_progress) == 1 else "s"))
        return 2
    print("VERDICT: PASS -- every cell COMPLETE and BALANCED, every column present, "
          "and _data.py agrees on every cell.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
