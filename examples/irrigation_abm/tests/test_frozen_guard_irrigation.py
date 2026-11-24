"""Frozen-case guard, irrigation: the three paper arms on the prompt-hash harness.

This is the MANUAL irrigation row of the merge checklist (reproduction/README.md, "Frozen-case
guard"). It needs the optional CRSS bundle, so it is marked requires_crss_data and skips on
CI. Run it before every merge that touches broker/:

    python -m pytest examples/irrigation_abm/tests/test_frozen_guard_irrigation.py \
        --timeout=900 -p no:cacheprovider

Arms (reproduction/recipes/irrigation.yaml): without rules, with the use limit only, with
rules. 78 farmers, 2 years, seed 42, workers 1, the harness
examples/irrigation_abm/tests/_hash_scripted_llm_harness.py. A pass means the covered
fixtures matched (reproduction/frozen_guard/fixtures/irrigation/), nothing more.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "reproduction" / "frozen_guard"))
import frozen_guard_common as fg  # noqa: E402

ARMS = ["disabled", "disabled_withlimit", "strict"]

pytestmark = pytest.mark.requires_crss_data


@pytest.fixture(scope="module")
def runs(tmp_path_factory):
    base = tmp_path_factory.mktemp("frozen_irr")
    return {arm: fg.run_arm("irrigation", arm, base / arm) for arm in ARMS}


def test_arms_are_the_recipes_three_arms():
    assert fg.arms("irrigation") == ARMS


@pytest.mark.parametrize("arm", ARMS)
def test_arm_matches_golden_fixtures(runs, arm):
    diffs = fg.diff_artifacts(fg.read_golden("irrigation", arm), runs[arm])
    assert not diffs, (
        f"irrigation/{arm} differs from reproduction/frozen_guard/fixtures/irrigation/{arm}:\n  "
        + "\n  ".join(diffs)
        + "\nIf the change is intended, read it, then run "
          "python reproduction/frozen_guard/regenerate.py --case irrigation --update")


def test_strict_arm_exercises_rejection_retry_and_default(runs):
    s = runs["strict"]["summary.json"][1]
    assert s["retried"] >= 1 and s["rejected_after_retries"] >= 1 and s["default_after_retries"] >= 1, s
    g = fg.read_golden("irrigation", "strict")["summary.json"][1]
    assert g["retried"] >= 1 and g["rejected_after_retries"] >= 1 and g["default_after_retries"] >= 1


def test_fixtures_are_portable():
    abs_path = re.compile(r"[A-Za-z]:[\\/]|/Users/|/home/|\\Users\\")
    files = [f for f in (fg.FIXTURES / "irrigation").rglob("*") if f.is_file()]
    assert files, "no fixtures"
    for f in files:
        # a Windows checkout with core.autocrlf=true turns LF into CRLF; the loader undoes it
        raw = f.read_bytes().replace(b"\r\n", b"\n")
        assert len(raw) < 200_000, f"{f.name} is {len(raw)} bytes"
        assert b"\r" not in raw, f"{f} has a lone CR"
        assert not raw.startswith(b"\xef\xbb\xbf"), f"{f} has a BOM"
        assert not abs_path.search(raw.decode("utf-8")), f"{f} holds an absolute path"
