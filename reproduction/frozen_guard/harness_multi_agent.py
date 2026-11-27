"""Subprocess harness for the frozen-case guard, multi-agent flood.

Runs examples/multi_agent/flood/run_unified_experiment.py with a mock LLM whose answer is
a pure function of the prompt text (see harness_flood.py for why the stock mock is not
enough). Input: `--mode random`, the repo's own synthetic household generator
(generate_agents_random). No survey file is read: the survey, balanced and initial-memory
paths are not taken in this mode.

generate_agents_random draws part of its profile from numpy's global generator, which
run_unified_experiment.py does not seed (it seeds only `random`). The harness seeds numpy
with the same value as --seed so the synthetic agents are the same on every run. That is
the one thing the harness adds to the case's own setup.

Patch point: broker.utils.llm_utils.create_llm_invoke (ExperimentRunner.get_llm_invoke
imports it inside the method on every call).

Every call is appended to --guard-calls (one JSON line: kind, sha256 of the prompt).

Usage: python harness_multi_agent.py --guard-calls <file> <run_unified_experiment.py arguments>
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
HOUSEHOLD_MARKERS = ("You are a homeowner (Agent ID", "You are a renter (Agent ID")
_CALLS_PATH = None


def canonical_prompt(text: str) -> str:
    """The prompt with the lines of its RELEVANT MEMORIES block sorted.

    The order in which the case's memory engine lists equal-scored memories is not the same
    from one run to the next (two runs, same seed, same PYTHONHASHSEED, differ in it from
    year 4 on). The set of memories is what the case decides, so the guard compares the
    block as a set: same lines, any order. Everything else in the prompt stays byte for
    byte. Kept identical to frozen_guard_common.canonical_prompt.
    """
    head, sep, rest = text.partition("### RELEVANT MEMORIES\n")
    if not sep:
        return text
    block, sep2, tail = rest.partition("\n\n###")
    if not sep2:
        raise ValueError("RELEVANT MEMORIES block is not followed by a ### section; "
                         "refusing to sort the rest of the prompt")
    return head + "### RELEVANT MEMORIES\n" + "\n".join(sorted(block.split("\n"))) + sep2 + tail


def _h(text: str) -> int:
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")


def _log(kind: str, prompt: str) -> None:
    if _CALLS_PATH is None:
        return
    prompt = canonical_prompt(prompt)
    rec = {"kind": kind, "sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest()}
    with open(_CALLS_PATH, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(rec) + "\n")


def _household_menu(prompt: str) -> dict:
    sect = prompt.split("### ADAPTATION OPTIONS", 1)
    if len(sect) < 2:
        return {}
    block = sect[1].split("\n\n", 1)[0]
    menu = {}
    for m in re.finditer(r"^\s*(\d+)\.\s+(.*)$", block, flags=re.M):
        text = m.group(2).lower()
        if "no protective action" in text:
            kind = "nothing"
        elif "insurance" in text:
            kind = "insurance"
        elif "elevate" in text:
            kind = "elevate"
        elif "buyout" in text:
            kind = "buyout"
        elif "relocate" in text:
            kind = "relocate"
        else:
            kind = "other%s" % m.group(1)
        menu[kind] = int(m.group(1))
    return menu


def _institution_options(prompt: str) -> list:
    sect = prompt.split("### YOUR OPTIONS", 1)
    if len(sect) < 2:
        return []
    block = sect[1].split("### RESPONSE FORMAT", 1)[0]
    return re.findall(r"^- \*\*([a-z_]+)\*\*", block, flags=re.M)


def hash_scripted_invoke(prompt: str):
    stats = LLMStats(retries=0, success=True)
    prompt = canonical_prompt(prompt)   # the answer must not depend on the memory order
    retry = prompt.lstrip().startswith(RETRY_MARK)
    start = -1
    for marker in HOUSEHOLD_MARKERS:
        start = prompt.find(marker)
        if start >= 0:
            break

    if start >= 0:  # a household
        _log("household_retry" if retry else "household", prompt)
        core = prompt[start:]
        menu = _household_menu(prompt)
        kinds = sorted(menu)
        hc = _h(core)
        labels = [LABELS[(hc >> (8 * i)) % 5] for i in range(5)]
        ha = _h(prompt) if retry else hc
        kind = kinds[(ha >> 16) % len(kinds)] if kinds else "nothing"
        special = (hc >> 40) % 10
        if special == 0 and "elevate" in menu:
            kind = "elevate"            # stubborn: the same answer on every attempt
        elif special == 1 and "relocate" in menu:
            kind = "relocate"
        elif special == 2 and "nothing" in menu and "insurance" in menu:
            labels[0], labels[1] = "VH", "VH"   # severe threat, strong coping, does nothing
            kind = "insurance" if retry else "nothing"
        body = {
            "threat_perception": {"label": labels[0], "reason": "Scripted."},
            "coping_perception": {"label": labels[1], "reason": "Scripted."},
            "stakeholder_perception": {"label": labels[2], "reason": "Scripted."},
            "social_capital": {"label": labels[3], "reason": "Scripted."},
            "place_attachment": {"label": labels[4], "reason": "Scripted."},
            "decision": str(menu.get(kind, 1)),
            "elevation_feet": "3",
            "insurance_coverage": "1",
            "secondary_decision": "0",
            "reasoning": "Hash-scripted answer.",
        }
        return "<<<DECISION_START>>>\n" + json.dumps(body) + "\n<<<DECISION_END>>>", stats

    options = _institution_options(prompt)
    if options:  # government or insurance
        _log("institution_retry" if retry else "institution", prompt)
        idx = prompt.find("### IDENTITY")
        core = prompt[idx:] if idx >= 0 else prompt
        hc = _h(core)
        ha = _h(prompt) if retry else hc
        choice = options[(ha >> 16) % len(options)]
        return json.dumps({"reasoning": "Hash-scripted answer.", "decision": choice}), stats

    _log("other", prompt)
    return json.dumps({"decision": 1}), stats


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
    seed = None
    if "--seed" in argv:
        seed = int(argv[argv.index("--seed") + 1])
    if seed is not None:
        import numpy as np
        np.random.seed(seed)
    llm_utils.create_llm_invoke = _patched
    sys.argv = ["run_unified_experiment.py"] + list(argv)
    runpy.run_path(
        str(ROOT / "examples" / "multi_agent" / "flood" / "run_unified_experiment.py"),
        run_name="__main__",
    )


if __name__ == "__main__":
    main(sys.argv[1:])
