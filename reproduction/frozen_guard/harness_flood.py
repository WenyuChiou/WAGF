"""Subprocess harness for the frozen-case guard, flood single agent.

Runs examples/single_agent/run_flood.py (its own command line, so the flags are the
recipe's) with a mock LLM whose answer is a pure function of the prompt text, the same
idea as examples/irrigation_abm/tests/_hash_scripted_llm_harness.py. The stock mock
(`--model mock`) answers the first option with no appraisal labels, so no rule can fire
and no prompt change can show; this one states appraisal labels and an action taken
from the prompt's own menu, so a changed rule threshold or a changed prompt line changes
the run.

Patch point: broker.utils.llm_utils.create_llm_invoke. ExperimentRunner.get_llm_invoke
imports it inside the method on every call; run_flood's own `create_llm_invoke` is an
alias for create_legacy_invoke and is not what the simulation calls.

Every call is also appended to --guard-calls (one JSON line: kind, sha256 of the prompt),
so the guard can pin the retry and reflection prompts too.

Usage: python harness_flood.py --guard-calls <file> <run_flood.py arguments>
"""
from __future__ import annotations

import hashlib
import json
import re
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import broker.utils.llm_utils as llm_utils  # noqa: E402
from broker.utils.llm_utils import LLMStats  # noqa: E402

LABELS = ["VL", "L", "M", "H", "VH"]
# A retry prompt starts with the header of its framing: legacy, or plain
# (global_config.governance.intervention_framing; plain has no log labels).
RETRY_MARK = (
    "Your previous response was flagged by the governance layer.",
    "Your previous answer cannot be used in this decision.",
)
_CALLS_PATH = None


def _h(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _log(kind: str, prompt: str) -> None:
    if _CALLS_PATH is None:
        return
    rec = {"kind": kind, "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
    with open(_CALLS_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")


def _menu(prompt: str) -> dict:
    """skill kind -> numeric id, read from the prompt's own option list."""
    tail = prompt.split("Now, choose one of the following actions:", 1)
    tail = tail[1] if len(tail) > 1 else prompt
    tail = tail.split("Note:", 1)[0]
    menu = {}
    for m in re.finditer(r"^\s*(\d+)\.\s+(.*)$", tail, flags=re.M):
        text = m.group(2).lower()
        if "insurance" in text:
            kind = "insurance"
        elif "elevate" in text:
            kind = "elevate"
        elif "relocate" in text:
            kind = "relocate"
        elif "do nothing" in text:
            kind = "nothing"
        else:
            kind = "other%s" % m.group(1)
        menu[kind] = int(m.group(1))
    return menu


def _payload(tp: str, cp: str, decision_id: int) -> str:
    body = json.dumps({
        "reasoning": "Hash-scripted answer.",
        "threat_appraisal": {"label": tp, "reason": "Scripted."},
        "coping_appraisal": {"label": cp, "reason": "Scripted."},
        "decision": str(decision_id),
    })
    return "<<<DECISION_START>>>\n" + body + "\n<<<DECISION_END>>>"


def _reflection(prompt: str) -> str:
    """Per-household year-end reflection; a pure function of the prompt. A quarter of the
    households name a year on the first try (the grounding check then asks again), one
    in four make a claim their own listed years contradict, the rest are clean."""
    aid = re.search(r"^(.+?) Memories:", prompt, flags=re.M).group(1)
    year = re.search(r"\(Year (\d+)\)", prompt).group(1)
    retry = "### Correction" in prompt
    bucket = _h(f"{aid}|{year}") % 4
    listed = prompt.split("### Record", 1)[0]
    if bucket == 1 and not retry:
        lesson = f"In Year {year} I learned to watch the river closely."
    elif bucket == 2 and ("damage on my house" in listed or "severe enough to cause damage" in listed):
        lesson = "I learned that my house has never been damaged, so waiting is safe."
    elif bucket == 2:
        lesson = "I learned that a flood comes every year, so I must always be ready."
    else:
        lesson = "I learned that protecting my home before a flood matters more than reacting after one."
    return json.dumps({aid: lesson})


def hash_scripted_invoke(prompt: str):
    stats = LLMStats(retries=0, success=True)
    if "You are a Reflection Assistant" in prompt:
        _log("reflection_retry" if "### Correction" in prompt else "reflection", prompt)
        return _reflection(prompt), stats

    retry = prompt.lstrip().startswith(RETRY_MARK)
    _log("decision_retry" if retry else "decision", prompt)

    idx = prompt.find("You are a homeowner")
    core = prompt[idx:] if idx >= 0 else prompt
    menu = _menu(prompt)
    kinds = sorted(menu)
    hc = _h(core)
    tp = LABELS[hc % 5]
    cp = LABELS[(hc >> 8) % 5]
    # the action: from the core on a first attempt, from the whole prompt on a retry
    # (full mode adds a header, so the retry prompt differs from the first one)
    ha = _h(prompt) if retry else hc
    kind = kinds[(ha >> 16) % len(kinds)] if kinds else "nothing"

    special = (hc >> 24) % 12
    if special == 0 and "relocate" in menu:
        # stubborn: the same blocked answer on every attempt, whatever the retry says
        tp, cp, kind = "L", "M", "relocate"
    elif special == 1 and "nothing" in menu:
        # stubborn: severe threat, coping not low, does nothing
        tp, cp, kind = "H", "M", "nothing"
    elif special == 2 and "nothing" in menu and "insurance" in menu:
        # fixable: does nothing at first, takes insurance once a retry header is there.
        # With the header left out ("silent") the first answer repeats.
        tp, cp, kind = "H", "M", ("insurance" if retry else "nothing")
    elif special == 3 and "elevate" in menu and "insurance" in menu:
        tp, cp, kind = "L", "M", ("insurance" if retry else "elevate")

    return _payload(tp, cp, menu.get(kind, 1)), stats


def _patched(model, verbose=False, overrides=None):
    if str(model).lower().startswith("mock"):
        return hash_scripted_invoke
    raise RuntimeError(f"frozen-case guard harness refuses a real model: {model!r}")


def main(argv):
    global _CALLS_PATH
    if argv and argv[0] == "--guard-calls":
        _CALLS_PATH = argv[1]
        argv = argv[2:]
        Path(_CALLS_PATH).write_text("", encoding="utf-8")
    llm_utils.create_llm_invoke = _patched
    sys.argv = ["run_flood.py"] + list(argv)
    runpy.run_path(str(ROOT / "examples" / "single_agent" / "run_flood.py"), run_name="__main__")


if __name__ == "__main__":
    main(sys.argv[1:])
