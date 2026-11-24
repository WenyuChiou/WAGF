"""Frozen-case guard, multi-agent flood: the frozen config on a prompt-hash mock.

Input is the repo's own synthetic generator (run_unified_experiment.py --mode random); the
survey, balanced and initial-memory paths are not taken and no survey-derived file is read.
8 households plus the two institutions, 4 years, deterministic floods in years 2 and 3,
seed 42. One arm: the frozen config (ma_agent_types.yaml), neighbour gossip off. Not covered:
gossip on (two identical runs list neighbour counts and pick gossip differently), the
mixed-population and influencer configs (not paper-3 configs), and --disable-governance
(the config declares only the strict profile, so the runner refuses to start).

A pass means the covered fixtures matched (reproduction/frozen_guard/fixtures/multi_agent/),
nothing more. Design and limits: reproduction/README.md, "Frozen-case guard".
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reproduction" / "frozen_guard"))
import frozen_guard_common as fg  # noqa: E402

ARMS = ["strict"]


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("frozen_ma")
    return {arm: fg.run_arm("multi_agent", arm, base / arm) for arm in ARMS}


def test_arms_are_declared():
    assert fg.arms("multi_agent") == ARMS


@pytest.mark.parametrize("arm", ARMS)
def test_arm_matches_golden_fixtures(runs, arm):
    diffs = fg.diff_artifacts(fg.read_golden("multi_agent", arm), runs[arm])
    assert not diffs, (
        f"multi_agent/{arm} differs from reproduction/frozen_guard/fixtures/multi_agent/{arm}:\n  "
        + "\n  ".join(diffs)
        + "\nIf the change is intended, read it, then run "
          "python reproduction/frozen_guard/regenerate.py --case multi_agent --update")


@pytest.mark.parametrize("arm", ARMS)
def test_arm_exercises_rejection_and_retry(runs, arm):
    s = runs[arm]["summary.json"][1]
    assert s["retried"] >= 1, f"{arm}: no decision was retried"
    assert s["rejected_after_retries"] >= 1, f"{arm}: no decision stayed rejected after its retries"
    g = fg.read_golden("multi_agent", arm)["summary.json"][1]
    assert g["retried"] >= 1 and g["rejected_after_retries"] >= 1


@pytest.mark.parametrize("arm", ARMS)
def test_every_kind_of_prompt_is_pinned_and_none_unknown(runs, arm):
    calls = runs[arm]["prompts.json"][1]["calls"]
    assert set(calls) <= {"household", "household_retry", "institution", "institution_retry"}, calls.keys()
    assert calls["household"]["n"] > 0 and calls["institution"]["n"] > 0 and calls["household_retry"]["n"] > 0


def test_fixtures_are_portable():
    abs_path = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|\\Users\\")
    files = [f for f in (fg.FIXTURES / "multi_agent").rglob("*") if f.is_file()]
    assert files, "no fixtures"
    for f in files:
        # a Windows checkout with core.autocrlf=true turns LF into CRLF; the loader undoes it
        raw = f.read_bytes().replace(b"\r\n", b"\n")
        assert len(raw) < 100_000, f"{f.name} is {len(raw)} bytes"
        assert b"\r" not in raw, f"{f} has a lone CR"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{f} has a BOM"
        assert not abs_path.search(raw.decode("utf-8")), f"{f} holds an absolute path"
