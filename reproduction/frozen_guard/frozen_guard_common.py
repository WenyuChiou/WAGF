"""Frozen-case guard: run a paper case on a prompt-hash mock, reduce the run to small
artifacts, compare them with the golden fixtures.

What a pass means: the covered fixtures matched, on this machine, for the sizes and seeds
listed here. It says nothing about any path the fixtures do not reach, and nothing about
a real model.

Layout: reproduction/frozen_guard/fixtures/<case>/<arm>/ holds, per arm,
  prompts.json            sha256 of the step prompt of every (agent, year), plus the ordered
                          sha256 of each kind of call the mock received (retry and reflection
                          prompts included)
  prompt_sample_*.txt     the full text of a few prompts, so a diff is readable
  audit_<type>.csv        the governance audit CSV, normalised (see below)
  actions.csv             proposed / final / executed action per agent and year
  state.csv               the simulation state (flood, irrigation: simulation_log.csv;
                          multi-agent: each household's state at decision time)
  summary.json            counts of retries, rejections and defaults, which the tests assert

Normalisation: broker.tools.compare_audit_csv.normalise_rows (timestamp, elapsed-time
columns, set order), then any cell over 100 characters becomes <sha256:16 hex:length>,
so a changed long text still changes the file. Files are UTF-8, LF, no BOM, no absolute
path. Cells that parse as numbers are written to 10 significant digits and compared with
a relative tolerance of 1e-8 (absolute 1e-9), unless both are integers, which must match
exactly; every other cell is compared exactly.
That tolerance is the only slack; nothing else is compared loosely.
"""
from __future__ import annotations

import csv
import difflib
import hashlib
import io
import json
import math
import os
import subprocess
import sys
from pathlib import Path

import yaml

KIT = Path(__file__).resolve().parent
ROOT = KIT.parents[1]
FIXTURES = KIT / "fixtures"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from broker.tools.compare_audit_csv import normalise_rows  # noqa: E402

LONG_CELL = 100
REL_TOL = 1e-8
ABS_TOL = 1e-9

FLOOD_SIZE = {"--model": "mock", "--years": "4", "--agents": "12", "--workers": "1", "--seed": "42"}
IRR_YEARS = "2"
IRR_MODES = {"with_validator": "strict", "without_validator": "disabled"}
MA_COMMON = ["--mode", "random", "--agents", "8", "--years", "4", "--seed", "42",
             "--model", "mock", "--flood-years", "2:0.6,3:1.2"]
MA_ARMS = {"strict": []}

CASES = ("flood", "multi_agent", "irrigation")


# --------------------------------------------------------------------------- arms

def _recipe(name: str) -> dict:
    return yaml.safe_load((ROOT / "reproduction" / "recipes" / f"{name}.yaml").read_text(encoding="utf-8"))


def arms(case: str) -> list:
    if case == "flood":
        return [a["set"] for a in _recipe("flood")["arms"]]
    if case == "irrigation":
        return list(IRR_MODES)
    if case == "multi_agent":
        return list(MA_ARMS)
    raise KeyError(case)


def harness_and_args(case: str, arm: str, out_dir: Path) -> tuple:
    """Return the mock harness and flags for a working-tree guard arm."""
    if case == "flood":
        recipe = _recipe("flood")
        flags = next(a["flags"] for a in recipe["arms"] if a["set"] == arm)
        args = []
        for flag, value in recipe["common_flags"]:
            args += [flag, FLOOD_SIZE.get(flag, value)]
        args += ["--memory-seed", "42"]          # runner default, named in the recipe's not_recorded
        args += list(flags) + ["--output", str(out_dir)]
        return KIT / "harness_flood.py", args
    if case == "multi_agent":
        return KIT / "harness_multi_agent.py", MA_COMMON + MA_ARMS[arm] + ["--output", str(out_dir)]
    if case == "irrigation":
        args = ["--model", "mock", "--real", "--years", IRR_YEARS, "--seed", "42", "--memory-seed", "42",
                "--paper-water-margin", "0.4", "--cluster-method", "hy2021",
                "--governance-mode", IRR_MODES[arm],
                "--config-dir", f"examples/irrigation_abm/config_variants/{arm}",
                "--workers", "1", "--output", str(out_dir)]
        return ROOT / "examples" / "irrigation_abm" / "tests" / "_hash_scripted_llm_harness.py", args
    raise KeyError(case)


def crss_available() -> bool:
    return (ROOT / "ref" / "CRSS_DB" / "CRSS_DB").is_dir()


# --------------------------------------------------------------------------- run

def run_arm(case: str, arm: str, work: Path, timeout: int = 600) -> dict:
    """Run one arm as its own subprocess (no process-global singleton leaks between arms)
    and return its artifacts."""
    work.mkdir(parents=True, exist_ok=True)
    out = work / "run"
    calls = work / "calls.jsonl"
    harness, args = harness_and_args(case, arm, out)
    cmd = [sys.executable, str(harness)]
    if case != "irrigation":
        cmd += ["--guard-calls", str(calls)]
    cmd += args
    env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONHASHSEED="0")
    res = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8",
                         errors="replace", timeout=timeout, env=env)
    if res.returncode != 0:
        raise RuntimeError(f"{case}/{arm} harness failed (exit {res.returncode}):\n"
                           f"STDOUT tail:\n{res.stdout[-2500:]}\nSTDERR tail:\n{res.stderr[-2500:]}")
    return build_artifacts(case, out, calls if calls.exists() else None)


# --------------------------------------------------------------------------- reduce

def _run_dir(out: Path) -> Path:
    if list(out.glob("*_governance_audit.csv")):
        return out
    for sub in sorted(p for p in out.iterdir() if p.is_dir()):
        if list(sub.glob("*_governance_audit.csv")):
            return sub
    raise FileNotFoundError(f"no governance audit CSV under {out}")


def _fmt_cell(cell: str) -> str:
    if len(cell) > LONG_CELL:
        return "<sha256:%s:len%d>" % (hashlib.sha256(cell.encode("utf-8")).hexdigest()[:16], len(cell))
    t = cell.strip()
    if t and t.lower() not in ("nan", "inf", "-inf", "true", "false") and any(c in t for c in ".eE"):
        try:
            return format(float(t), ".10g")
        except ValueError:
            pass
    return cell


def _read_csv(path: Path) -> tuple:
    with open(path, "r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.reader(fh))
    return rows[0], rows[1:]


def _audit_artifact(path: Path) -> list:
    header, body = _read_csv(path)
    header, body = normalise_rows(header, body)
    return [header] + [[_fmt_cell(c) for c in row] for row in body]


def _sim_artifact(path: Path) -> list:
    header, body = _read_csv(path)
    return [header] + [[_fmt_cell(c) for c in row] for row in body]


def _traces(run: Path) -> list:
    out = []
    for f in sorted((run / "raw").glob("*_traces.jsonl")):
        for line in f.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if "agent_id" in rec and "input" in rec:
                out.append(rec)
    return out


def canonical_prompt(text: str) -> str:
    """Multi-agent only: the lines of the RELEVANT MEMORIES block sorted. The case's memory
    engine lists equal-scored memories in an order that changes from run to run (same seed,
    same PYTHONHASHSEED, from year 4 on), so the block is compared as a set; every other
    byte of the prompt is compared as it is. Kept identical to the copy in
    harness_multi_agent.py, which the mock uses for the same reason."""
    head, sep, rest = text.partition("### RELEVANT MEMORIES\n")
    if not sep:
        return text
    block, sep2, tail = rest.partition("\n\n###")
    if not sep2:
        raise ValueError("RELEVANT MEMORIES block is not followed by a ### section; "
                         "refusing to sort the rest of the prompt")
    return head + "### RELEVANT MEMORIES\n" + "\n".join(sorted(block.split("\n"))) + sep2 + tail


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


ACTION_COLS = ["agent_id", "year", "proposed_skill", "final_skill", "executed_skill", "status",
               "retry_count", "fallback_activated", "execution_path"]


def _actions(audit_rows: dict, sim_rows) -> list:
    """audit_rows: {type: [header]+rows}. One table of the actions per (type, agent, year)."""
    out = [["agent_type"] + ACTION_COLS + (["yearly_decision", "executed_decision"] if sim_rows else [])]
    sim = {}
    if sim_rows:
        h = sim_rows[0]
        ia, iy = h.index("agent_id"), h.index("year")
        iyd, ied = h.index("yearly_decision"), h.index("executed_decision")
        for r in sim_rows[1:]:
            sim[(r[ia], r[iy])] = [r[iyd], r[ied]]
    for typ in sorted(audit_rows):
        h = audit_rows[typ][0]
        idx = [h.index(c) if c in h else None for c in ACTION_COLS]
        for r in audit_rows[typ][1:]:
            row = [typ] + ["" if i is None else r[i] for i in idx]
            if sim_rows:
                row += sim.get((row[1], row[2]), ["", ""])
            out.append(row)
    return out


STATE_KEYS = ["elevated", "has_insurance", "relocated", "flood_count", "years_since_flood",
              "cumulative_damage", "cumulative_oop", "last_decision", "insured_years",
              "cumulative_premiums_paid", "insurance_coverage", "flooded_this_year"]


def _canon(obj) -> str:
    def norm(o):
        if isinstance(o, float):
            return float(format(o, ".10g"))
        if isinstance(o, dict):
            return {k: norm(v) for k, v in o.items()}
        if isinstance(o, list):
            return [norm(v) for v in o]
        return o
    return json.dumps(norm(obj), sort_keys=True, ensure_ascii=False)


def _household_state(traces: list) -> list:
    """Multi-agent: the household's state at decision time (the run writes no simulation_log)."""
    out = [["agent_id", "year"] + STATE_KEYS + ["state_sha256"]]
    for t in traces:
        s = t.get("state_before")
        if not isinstance(s, dict) or "tenure" not in s:
            continue
        out.append([t["agent_id"], str(t["year"])] + [_fmt_cell(str(s.get(k, ""))) for k in STATE_KEYS]
                   + [_sha(_canon(s))[:16]])
    return out


def build_artifacts(case: str, out: Path, calls: Path = None) -> dict:
    run = _run_dir(out)
    art = {}
    audits = {}
    for f in sorted(run.glob("*_governance_audit.csv")):
        typ = f.name[: -len("_governance_audit.csv")]
        audits[typ] = _audit_artifact(f)
        art[f"audit_{typ}.csv"] = ("csv", audits[typ])

    sim_rows = _sim_artifact(run / "simulation_log.csv") if (run / "simulation_log.csv").exists() else None
    art["actions.csv"] = ("csv", _actions(audits, sim_rows))
    traces = _traces(run)
    # the memory column of a simulation log is long text; _fmt_cell has already reduced it to a hash
    art["state.csv"] = ("csv", sim_rows if sim_rows is not None else _household_state(traces))

    canon = canonical_prompt if case == "multi_agent" else (lambda x: x)
    prompts = {"step_prompt_sha256": {}}
    for t in traces:
        prompts["step_prompt_sha256"].setdefault(f"{t['agent_id']}|{t['year']}", _sha(canon(t["input"])))
    if calls is not None:
        by_kind = {}
        for line in calls.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                by_kind.setdefault(rec["kind"], []).append(rec["sha256"])
        prompts["calls"] = {k: {"n": len(v), "sha256_of_ordered_prompt_shas": _sha("\n".join(v))}
                            for k, v in sorted(by_kind.items())}
    art["prompts.json"] = ("json", prompts)

    # Keep one complete one-agent prompt for wording review and the task report.
    # Multi-agent artifacts and their canonicalization remain byte-identical.
    if case == "flood":
        records = (json.loads(line) for line in calls.read_text(encoding="utf-8").splitlines()
                   if line.strip())
        reflection = next(row["prompt"] for row in records if row["kind"] == "reflection")
        art["prompt_sample_reflection.txt"] = ("text", reflection)
    elif case == "irrigation":
        records = (json.loads(line) for line in (run / "reflection_prompts.jsonl").read_text(
            encoding="utf-8").splitlines() if line.strip())
        reflection = next(row["prompt"] for row in records if int(row.get("attempt", 0)) == 0)
        art["prompt_sample_reflection.txt"] = ("text", reflection)

    # a few full prompts so a failing diff can be read: the first decision of each household
    # type (irrigation: of the farmer type), the first decision of year 3 (flood only), and
    # the first retry prompt
    seen = set()
    for t in traces:
        typ = t.get("agent_type", "agent")
        if typ in ("government", "insurance") or typ in seen:
            continue
        seen.add(typ)
        art[f"prompt_sample_{typ}_{t['agent_id']}_y{t['year']}.txt"] = ("text", canon(t["input"]))
    if case == "flood":
        y3 = next((t for t in traces if t["year"] == 3), None)
        if y3 is not None:
            art[f"prompt_sample_flood_year_{y3['agent_id']}_y3.txt"] = ("text", y3["input"])
    retry = next((t for t in traces if t.get("retry_prompts")), None)
    if retry is not None:
        art["prompt_sample_first_retry.txt"] = ("text", canon(retry["retry_prompts"][0]))

    art["summary.json"] = ("json", summarise(audits))
    return art


def summarise(audits: dict) -> dict:
    total = rejected = retried = defaulted = 0
    for rows in audits.values():
        h = rows[0]
        i_status, i_retry = h.index("status"), h.index("retry_count")
        i_path = h.index("execution_path") if "execution_path" in h else None
        for r in rows[1:]:
            total += 1
            if int(float(r[i_retry] or 0)) > 0:
                retried += 1
            if r[i_status] == "REJECTED":
                rejected += 1          # still rejected after the last allowed retry
            if i_path is not None and r[i_path] == "rejected_default":
                defaulted += 1
    return {"decisions": total, "retried": retried, "rejected_after_retries": rejected,
            "default_after_retries": defaulted}


# --------------------------------------------------------------------------- files

def _csv_text(rows: list) -> str:
    buf = io.StringIO()
    csv.writer(buf, lineterminator="\n").writerows(rows)
    return buf.getvalue()


def artifact_text(kind: str, value) -> str:
    if kind == "csv":
        return _csv_text(value)
    if kind == "json":
        return json.dumps(value, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    return value if value.endswith("\n") else value + "\n"


def golden_dir(case: str, arm: str) -> Path:
    return FIXTURES / case / arm


def write_golden(case: str, arm: str, art: dict) -> None:
    d = golden_dir(case, arm)
    d.mkdir(parents=True, exist_ok=True)
    for old in d.iterdir():
        if old.is_file() and old.name not in art:
            old.unlink()
    for name, (kind, value) in art.items():
        with open(d / name, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(artifact_text(kind, value))


def read_golden(case: str, arm: str) -> dict:
    d = golden_dir(case, arm)
    if not d.is_dir():
        raise FileNotFoundError(
            f"no golden fixtures at {d}; run: python reproduction/frozen_guard/regenerate.py --update")
    out = {}
    for f in sorted(d.iterdir()):
        text = f.read_bytes().decode("utf-8").replace(chr(13) + chr(10), chr(10))   # a Windows checkout with core.autocrlf=true may give CRLF
        if f.suffix == ".csv":
            out[f.name] = ("csv", list(csv.reader(io.StringIO(text, newline=""))))
        elif f.suffix == ".json":
            out[f.name] = ("json", json.loads(text))
        else:
            out[f.name] = ("text", text)
    return out


# --------------------------------------------------------------------------- compare

def _looks_decimal(cell: str) -> bool:
    return any(ch in cell for ch in ".eE") and not any(ch.isalpha() and ch not in "eE" for ch in cell)


def _cell_equal(g: str, a: str) -> bool:
    if g == a:
        return True
    if not (_looks_decimal(g) or _looks_decimal(a)):   # two integers: exact
        return False
    try:
        return math.isclose(float(g), float(a), rel_tol=REL_TOL, abs_tol=ABS_TOL)
    except ValueError:
        return False


def _diff_csv(name: str, g: list, a: list, limit: int) -> list:
    out = []
    if g[0] != a[0]:
        gs, as_ = set(g[0]), set(a[0])
        return [f"{name}: header differs; only in fixture {sorted(gs - as_)}, only in run {sorted(as_ - gs)}"]
    if len(g) != len(a):
        out.append(f"{name}: {len(g) - 1} rows in fixture, {len(a) - 1} in run")
    head = g[0]
    key_cols = [i for i, c in enumerate(head) if c in ("agent_type", "agent_id", "year")]
    for n, (gr, ar) in enumerate(zip(g[1:], a[1:]), 1):
        bad = [i for i in range(len(head)) if not _cell_equal(gr[i], ar[i])]
        if bad:
            key = "/".join(gr[i] for i in key_cols) or f"row {n}"
            cols = "; ".join(f"{head[i]}: {gr[i][:50]!r} -> {ar[i][:50]!r}" for i in bad[:3])
            out.append(f"{name}: {key}: {len(bad)} cells differ ({cols})")
            if len(out) >= limit:
                break
    return out


def diff_artifacts(golden: dict, actual: dict, limit: int = 8) -> list:
    """Differences, empty when the run matches the fixtures. At most `limit` lines per file."""
    out = []
    for name in sorted(set(golden) | set(actual)):
        if name not in golden:
            out.append(f"{name}: produced by the run, not in the fixtures")
            continue
        if name not in actual:
            out.append(f"{name}: in the fixtures, not produced by the run")
            continue
        (kind, gv), (_, av) = golden[name], actual[name]
        if kind == "csv":
            # compare after the same text round trip the fixture went through
            av = list(csv.reader(io.StringIO(_csv_text(av), newline="")))
            out += _diff_csv(name, gv, av, limit)
        elif kind == "json":
            if json.loads(artifact_text("json", gv)) != json.loads(artifact_text("json", av)):
                gd = artifact_text("json", gv).splitlines()
                ad = artifact_text("json", av).splitlines()
                lines = list(difflib.unified_diff(gd, ad, "fixture", "run", n=0, lineterm=""))[:limit]
                out.append(f"{name}: differs\n    " + "\n    ".join(lines))
        else:
            if gv.rstrip("\n") != av.rstrip("\n"):
                lines = list(difflib.unified_diff(gv.splitlines(), av.splitlines(), "fixture", "run",
                                                  n=0, lineterm=""))[:limit]
                out.append(f"{name}: differs\n    " + "\n    ".join(l[:160] for l in lines))
    return out
