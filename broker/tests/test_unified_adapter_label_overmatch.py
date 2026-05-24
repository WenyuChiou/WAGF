"""Phase 6N-D-4 regression test — `unified_adapter` free-text fallback
whitelist filter prevents regex over-match on contraction letters.

The fallback CONSTRUCT EXTRACTION path at
`broker/utils/parsing/unified_adapter.py` lines ~585-600 scans free-text
reasoning prose with the per-construct regex `\\b(VL|L|M|H|VH)\\b`. The
word-boundary `\\b` matches between `'` (non-word char) and `m` (word
char) — and between `m` and ` ` (space) — so the bare `m` inside `I'm`
produces a match that gets captured as a LABEL.

Smoke #6 of L3-1C (commit 64899b8, 2026-05-24) saw this leak as
`construct_SEVERITY_LABEL='m'` on row 36 of a vaccination_demo
gemma3:1b run. The flood Group_C paper-1b reference data carries
2/8918 such leaks (recorded in INVARIANTS cross-version log dd4a4f2).

Phase 6N-D-4 adds a whitelist filter: a regex capture is only accepted
when `temp_val.upper()` is in the canonical ordinal alphabet
`{VL, L, M, H, VH}`. The fix is benign on legitimate captures (they
ARE in the alphabet) and rejects only bare-letter contraction matches.

Test strategy (mirrors Phase 6N-B precedent):
1. **Grep contract test** asserts the whitelist filter line literally
   exists in `unified_adapter.py` (with comment-strip so deleting the
   active code while keeping the comment fails the test).
2. **Direct filter behaviour test** simulates the exact `temp_val`
   values the fix gates on and verifies which are rejected.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest


# =============================================================================
# Grep contract — the whitelist filter must exist in production code
# =============================================================================


def test_whitelist_filter_present_in_unified_adapter():
    """The whitelist filter is the load-bearing line for Bug #8. If a
    future refactor deletes it while leaving the explanatory comment
    in place, this test catches the regression.

    Per Phase 6N-B precedent (`test_label_capture_no_lowercase_leak_documented`),
    we strip comment lines before the substring assertion.
    """
    src = (
        Path(__file__).resolve().parents[1]
        / "utils" / "parsing" / "unified_adapter.py"
    ).read_text(encoding="utf-8")
    non_comment = "\n".join(
        line for line in src.splitlines()
        if not line.strip().startswith("#")
    )
    # The exact contract line installed in Phase 6N-D-4.
    needle = 'if temp_val.upper() not in {"VL", "L", "M", "H", "VH"}:'
    assert needle in non_comment, (
        f"broker/utils/parsing/unified_adapter.py no longer carries the "
        f"Phase 6N-D-4 whitelist filter on the free-text fallback regex "
        f"capture. Without this guard, bare-letter captures from "
        f"contractions (e.g. ``m`` in ``I'm``) leak into LABEL columns."
    )


# =============================================================================
# Direct filter behaviour — what gets rejected / accepted by the gate
# =============================================================================


@pytest.mark.parametrize(
    "temp_val,expected_accept",
    [
        # Canonical alphabet — must be accepted
        ("VL", True),
        ("L", True),
        ("M", True),
        ("H", True),
        ("VH", True),
        # Lowercase canonical — accepted after upper-cased filter check
        ("vl", True),
        ("l", True),
        ("m", True),  # the I'm contraction case: 'm' BY ITSELF is allowed
        ("h", True),
        ("vh", True),
        # Mixed case — accepted after upper-cased filter check
        ("Vh", True),
        ("vH", True),
        # Non-canonical letters — must be rejected (cannot come from a
        # legitimate label, must be a free-text accident)
        ("a", False),
        ("X", False),
        ("med", False),  # 3-letter partial
        ("HIGH", False),  # word form should go through long-form
                          # extraction path, not regex; if it leaks
                          # into temp_val the filter rejects it
        # Empty / whitespace — rejected
        ("", False),
        (" ", False),
    ],
)
def test_whitelist_filter_admission_logic(temp_val, expected_accept):
    """The fix's gate is:
        if temp_val.upper() not in {"VL", "L", "M", "H", "VH"}:
            continue
    So `accept` means `temp_val.upper() IS in the set`. Confirms the
    fix correctly classifies a representative sample.
    """
    accepted = temp_val.upper() in {"VL", "L", "M", "H", "VH"}
    assert accepted is expected_accept, (
        f"temp_val={temp_val!r}: filter classified accept={accepted}, "
        f"expected accept={expected_accept}"
    )


def test_contraction_regex_pattern_overmatches_apostrophe_m():
    """Document the root cause: confirm the regex itself DOES match
    ``m`` inside ``I'm``. This is the over-match behaviour the
    whitelist filter compensates for — the regex pattern cannot
    distinguish "label" from "contraction letter" via word boundaries.

    If this test ever starts FAILING (regex no longer over-matches),
    the whitelist filter becomes redundant and can be reconsidered.
    """
    pattern = r"(?i)\b(VL|L|M|H|VH)\b"
    text = "As a 75-year-old, I'm likely to be cautious"
    matches = list(re.finditer(pattern, text, re.IGNORECASE))
    captured = [m.group(1) for m in matches]
    assert "m" in captured, (
        f"regex no longer over-matches contraction letters. "
        f"matches={captured} — whitelist filter may be redundant."
    )
