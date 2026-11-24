"""Frozen-case guard, flood single agent: three paper arms on a prompt-hash mock.

A pass means the covered fixtures matched (reproduction/frozen_guard/fixtures/flood/): the
step prompts byte for byte, the governance audit, the executed actions and the simulation
state, for 12 agents over 4 years (flood years 3 and 4), seed 42, workers 1. It does not
mean every paper path is unchanged, and it says nothing about a real model.

The fixtures change only through reproduction/frozen_guard/regenerate.py --update; these
tests never write them. Design and limits: reproduction/README.md, "Frozen-case guard".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reproduction" / "frozen_guard"))
import frozen_guard_common as fg  # noqa: E402

ARMS = ["disabled", "strict", "silent"]
STRICT_ARMS = ["strict", "silent"]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    """Each arm runs once, in its own subprocess."""
    base = tmp_path_factory.mktemp("frozen_flood")
    return {arm: fg.run_arm("flood", arm, base / arm) for arm in ARMS}


def test_arms_are_the_recipes_three_arms():
    assert fg.arms("flood") == ARMS
    _, args = fg.harness_and_args("flood", "silent", Path("out"))
    assert args[args.index("--governance-mode") + 1] == "strict"
    assert args[args.index("--retry-feedback-mode") + 1] == "silent"
    _, args = fg.harness_and_args("flood", "disabled", Path("out"))
    assert args[args.index("--governance-mode") + 1] == "disabled"
    assert "--retry-feedback-mode" not in args


@pytest.mark.parametrize("arm", ARMS)
def test_arm_matches_golden_fixtures(runs, arm):
    diffs = fg.diff_artifacts(fg.read_golden("flood", arm), runs[arm])
    assert not diffs, (
        f"flood/{arm} differs from reproduction/frozen_guard/fixtures/flood/{arm}:\n  "
        + "\n  ".join(diffs)
        + "\nIf the change is intended, read it, then run "
          "python reproduction/frozen_guard/regenerate.py --case flood --update")


@pytest.mark.parametrize("arm", STRICT_ARMS)
def test_strict_arms_exercise_rejection_retry_and_default(runs, arm):
    """If a mock change stops these paths being reached, the guard would pass while
    guarding nothing: fail loudly instead."""
    s = runs[arm]["summary.json"][1]
    assert s["retried"] >= 1, f"{arm}: no decision was retried"
    assert s["rejected_after_retries"] >= 1, f"{arm}: no decision stayed rejected after its retries"
    assert s["default_after_retries"] >= 1, f"{arm}: no decision fell to the default after retries ran out"
    # and the fixture records the same, so the golden file itself shows it
    g = fg.read_golden("flood", arm)["summary.json"][1]
    assert g["retried"] >= 1 and g["rejected_after_retries"] >= 1 and g["default_after_retries"] >= 1


def test_disabled_arm_has_no_retries(runs):
    s = runs["disabled"]["summary.json"][1]
    assert s["retried"] == 0 and s["rejected_after_retries"] == 0 and s["default_after_retries"] == 0


@pytest.mark.parametrize("arm", ARMS)
def test_every_kind_of_prompt_is_pinned_and_none_unknown(runs, arm):
    calls = runs[arm]["prompts.json"][1]["calls"]
    assert set(calls) <= {"decision", "decision_retry", "reflection", "reflection_retry"}, calls.keys()
    assert calls["decision"]["n"] > 0 and calls["reflection"]["n"] > 0
    decisions = runs[arm]["summary.json"][1]["decisions"]
    if arm == "strict":
        assert calls["decision_retry"]["n"] > 0          # a retry prompt carries the rule text
    elif arm == "silent":
        # silent re-sends the original prompt byte for byte, so a retry is a repeated call
        assert "decision_retry" not in calls and calls["decision"]["n"] > decisions


def test_fixtures_are_portable():
    """LF (CRLF from a Windows checkout allowed), no BOM, no absolute path, each file well under 100 KB."""
    abs_path = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|\\Users\\")
    files = [f for f in (fg.FIXTURES / "flood").rglob("*") if f.is_file()]
    assert files, "no fixtures"
    for f in files:
        # a Windows checkout with core.autocrlf=true turns LF into CRLF; the loader undoes it
        raw = f.read_bytes().replace(b"\r\n", b"\n")
        assert len(raw) < 100_000, f"{f.name} is {len(raw)} bytes"
        assert b"\r" not in raw, f"{f} has a lone CR"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{f} has a BOM"
        assert not abs_path.search(raw.decode("utf-8")), f"{f} holds an absolute path"
