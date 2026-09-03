"""Distributional and paired-test metrics for a factor ablation.

Why not just count flips
------------------------
A flip count throws away everything except "did the answer change". Two
factors can produce the same flip rate while one shifts the whole action
distribution and the other only nudges a tie. So the per-snapshot
comparison here is between two distributions over the domain's action
vocabulary — Jensen-Shannon divergence and KL — and the flip is only one
of the numbers that come out.

JSD is the primary distributional number; KL is secondary
---------------------------------------------------------
On a decider that passes the determinism gate, each per-snapshot
distribution is a point mass: one seed, one answer, probability 1 on one
action. Between two point masses KL is not a graded distance at all — it
is ``log2(1/epsilon)`` when they differ and 0 when they agree, a flip
indicator multiplied by a constant that depends only on ``KL_EPSILON``.
JSD on the same pair is exactly 1.0 or 0.0, which is the same
information without the false precision, so report JSD and read KL only
when a cell actually holds a spread (several seeds that disagreed, which
on a verified-deterministic backend does not happen).

Why a paired nonparametric test
-------------------------------
Each snapshot contributes one delta-P under the masked arm and one under
the control arm, computed from the SAME decision at the SAME seeds. The
pairing is the design's whole point, and per-snapshot delta-P values are
bounded, discrete and nowhere near normal, so the test is a Wilcoxon
signed-rank on the pairs.

The scipy contract
------------------
``scipy.stats.wilcoxon`` is used when scipy is importable (it ships in
the ``analysis`` extra). When it is not, this module computes the test
itself — exact for small samples, normal approximation with a tie
correction above that — and says so in the ``method`` field. What it
never does is return ``p_value = 1.0`` and carry on: a test that quietly
becomes a no-op reads exactly like a null result, and a reader has no way
to tell the two apart.
"""
from __future__ import annotations

import itertools
import math
from typing import Any, Dict, Iterable, List, Optional, Sequence

#: Additive smoothing applied before KL so a zero in the reference
#: distribution does not send the divergence to infinity. Reported in the
#: result so the number is reproducible.
KL_EPSILON = 1e-9


# ─────────────────────────────────────────────────────────────────────
# Distributions
# ─────────────────────────────────────────────────────────────────────

def action_distribution(
    skills: Sequence[Optional[str]],
    vocabulary: Optional[Sequence[str]] = None,
    *,
    unparsed_label: str = "__unparsed__",
) -> Dict[str, float]:
    """Empirical action distribution over ``vocabulary``.

    An unparsable reply is its own outcome, not a missing value: a mask
    that makes the model stop producing a valid decision has changed the
    behaviour, and dropping those rows would hide it.
    """
    labels = [s if s is not None else unparsed_label for s in skills]
    vocab = list(vocabulary) if vocabulary else sorted(set(labels))
    for label in labels:
        if label not in vocab:
            vocab.append(label)
    total = len(labels) or 1
    return {label: labels.count(label) / total for label in vocab}


def _aligned(p: Dict[str, float], q: Dict[str, float]) -> tuple:
    keys = sorted(set(p) | set(q))
    return ([float(p.get(k, 0.0)) for k in keys],
            [float(q.get(k, 0.0)) for k in keys])


def _normalise(values: List[float]) -> List[float]:
    total = sum(values)
    if total <= 0:
        return [0.0 for _ in values]
    return [v / total for v in values]


def jensen_shannon_divergence(
    p: Dict[str, float], q: Dict[str, float], *, base: float = 2.0,
) -> Optional[float]:
    """JSD in ``base`` (default 2, so the value lies in [0, 1]).

    Two point masses on different actions give exactly 1.0 — which is
    what a deterministic decider that flipped produces, and the reason
    the across-snapshot Wilcoxon, not the per-snapshot JSD, carries the
    inference.

    Returns ``None``, not ``0.0``, when either side is empty or sums to
    zero. Zero is the value for "these two distributions are identical",
    and a cell that produced no replies is not that; reporting 0.0 for it
    put "nothing happened" and "nothing ran" in the same column.
    """
    pv, qv = _aligned(p, q)
    pv, qv = _normalise(pv), _normalise(qv)
    if not pv or sum(pv) == 0 or sum(qv) == 0:
        return None
    m = [(a + b) / 2.0 for a, b in zip(pv, qv)]

    def _kl(a: List[float], b: List[float]) -> float:
        total = 0.0
        for ai, bi in zip(a, b):
            if ai > 0 and bi > 0:
                total += ai * math.log(ai / bi, base)
        return total

    return max(0.0, 0.5 * _kl(pv, m) + 0.5 * _kl(qv, m))


def kl_divergence(
    p: Dict[str, float], q: Dict[str, float], *,
    base: float = 2.0, epsilon: float = KL_EPSILON,
) -> Optional[float]:
    """KL(p || q) with additive smoothing of ``epsilon`` on both sides.

    ``None`` when either side is empty or holds no mass — the smoothing
    would otherwise turn an empty cell into a finite-looking number.
    Read JSD first; see this module's docstring for why KL between two
    point masses is a flip indicator rather than a distance.
    """
    pv, qv = _aligned(p, q)
    if not pv or sum(pv) <= 0 or sum(qv) <= 0:
        return None
    pv = _normalise([v + epsilon for v in pv])
    qv = _normalise([v + epsilon for v in qv])
    total = 0.0
    for a, b in zip(pv, qv):
        if a > 0:
            total += a * math.log(a / b, base)
    return max(0.0, total)


def probability_of(distribution: Dict[str, float], action: Optional[str]) -> float:
    if action is None:
        return 0.0
    return float(distribution.get(action, 0.0))


# ─────────────────────────────────────────────────────────────────────
# Paired Wilcoxon signed-rank
# ─────────────────────────────────────────────────────────────────────

def _rank_with_ties(values: Sequence[float]) -> List[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        average = (i + j + 2) / 2.0   # ranks are 1-based
        for k in range(i, j + 1):
            ranks[order[k]] = average
        i = j + 1
    return ranks


def _normal_sf(z: float) -> float:
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def _exact_two_sided_p(ranks: Sequence[float], w_plus: float) -> float:
    """Exact two-sided p by enumerating every sign assignment."""
    n = len(ranks)
    total = float(sum(ranks))
    observed = min(w_plus, total - w_plus)
    count = 0
    for signs in itertools.product((0, 1), repeat=n):
        w = sum(r for r, s in zip(ranks, signs) if s)
        if min(w, total - w) <= observed + 1e-12:
            count += 1
    return min(1.0, count / (2 ** n))


#: Above this many non-zero pairs the pure-python fallback stops
#: enumerating 2**n sign assignments and switches to the normal
#: approximation. 2**18 = 262,144 terms is about a second; 2**25 is not.
EXACT_ENUMERATION_LIMIT = 18

#: Fewest non-zero pairs a reported p-value needs. The two-sided exact
#: signed-rank test on k non-zero pairs cannot return anything below
#: 2**-(k-1) — every pair moving the same way is the most extreme
#: arrangement there is. At k=7 that floor is 0.0156, so a "p = 0.016"
#: from seven snapshots is the smallest number the test can produce and
#: not a measurement of anything. At k=8 the floor is 0.0078, the first
#: value under the 0.01 a reader would treat as strong. Below this the
#: ablation withholds the p-value and prints the attainable floor
#: instead, so nobody quotes a number the design could not have missed.
MIN_PAIRS = 8


def attainable_p_floor(n_nonzero: int) -> Optional[float]:
    """Smallest two-sided exact p the signed-rank test can return.

    ``2 ** -(k - 1)`` for k non-zero pairs; ``None`` for k < 1, where the
    test is undefined rather than merely underpowered.
    """
    if n_nonzero < 1:
        return None
    return 2.0 ** -(n_nonzero - 1)


def wilcoxon_signed_rank(
    x: Sequence[float],
    y: Optional[Sequence[float]] = None,
    *,
    prefer_scipy: bool = True,
) -> Dict[str, Any]:
    """Two-sided paired Wilcoxon signed-rank test.

    Returns ``statistic``, ``p_value``, ``n_pairs``, ``n_nonzero``,
    ``method``, and ``note``. ``p_value`` is ``None`` only when the test
    is undefined (no non-zero differences), and ``note`` then says why —
    never a silent 1.0.
    """
    xs = [float(v) for v in x]
    if y is not None:
        ys = [float(v) for v in y]
        if len(xs) != len(ys):
            raise ValueError(
                f"wilcoxon_signed_rank needs equal-length paired samples; "
                f"got {len(xs)} and {len(ys)}."
            )
        diffs = [a - b for a, b in zip(xs, ys)]
    else:
        diffs = xs

    n_pairs = len(diffs)
    nonzero = [d for d in diffs if d != 0.0]
    n = len(nonzero)

    if n == 0:
        return {
            "statistic": 0.0,
            "p_value": None,
            "n_pairs": n_pairs,
            "n_nonzero": 0,
            "method": "undefined",
            "note": (
                "Every pair differed by exactly zero, so the signed-rank "
                "test has nothing to rank. This is a real result — the "
                "intervention moved nothing — not a test that was skipped."
            ),
        }

    if prefer_scipy:
        try:
            from scipy import stats as sp_stats
        except ImportError:
            sp_stats = None
        if sp_stats is not None:
            method = "exact" if n <= 25 else "approx"
            statistic, p_value = sp_stats.wilcoxon(
                nonzero, zero_method="wilcox", alternative="two-sided",
                method=method,
            )
            return {
                "statistic": float(statistic),
                "p_value": float(p_value),
                "n_pairs": n_pairs,
                "n_nonzero": n,
                "method": f"scipy.stats.wilcoxon({method})",
                "note": "",
            }

    magnitudes = [abs(d) for d in nonzero]
    ranks = _rank_with_ties(magnitudes)
    w_plus = sum(r for r, d in zip(ranks, nonzero) if d > 0)
    w_minus = sum(r for r, d in zip(ranks, nonzero) if d < 0)
    statistic = min(w_plus, w_minus)

    has_ties = len(set(magnitudes)) != len(magnitudes)
    if n <= EXACT_ENUMERATION_LIMIT and not has_ties:
        p_value = _exact_two_sided_p(ranks, w_plus)
        method = "pure-python exact (scipy unavailable)"
        note = ("scipy is not installed. Install the analysis extra "
                "(pip install 'water-agent-governance-framework[analysis]') "
                "to use scipy.stats.wilcoxon.")
    else:
        mean = n * (n + 1) / 4.0
        tie_correction = 0.0
        counts: Dict[float, int] = {}
        for magnitude in magnitudes:
            counts[magnitude] = counts.get(magnitude, 0) + 1
        for t in counts.values():
            if t > 1:
                tie_correction += (t ** 3 - t)
        variance = n * (n + 1) * (2 * n + 1) / 24.0 - tie_correction / 48.0
        if variance <= 0:
            p_value = 1.0
        else:
            z = (abs(statistic - mean) - 0.5) / math.sqrt(variance)
            p_value = min(1.0, 2.0 * _normal_sf(max(z, 0.0)))
        method = "pure-python normal approximation (scipy unavailable)"
        note = (
            "scipy is not installed, and this sample is too large or too "
            "tied for exact enumeration, so the p-value is a normal "
            "approximation with a tie correction. Install the analysis "
            "extra for the exact test."
        )

    return {
        "statistic": float(statistic),
        "p_value": float(p_value),
        "n_pairs": n_pairs,
        "n_nonzero": n,
        "method": method,
        "note": note,
    }


# ─────────────────────────────────────────────────────────────────────
# Direction
# ─────────────────────────────────────────────────────────────────────

def directional_consistency(
    deltas: Iterable[float], *, expected_sign: int = -1,
) -> Dict[str, Any]:
    """Fraction of snapshots that moved in the ASSUMED direction.

    The direction is an assumption the factor's declaration makes, not
    something the trace states. ``MaskSpec.expected_sign`` carries it,
    and the default ``-1`` encodes the usual reading: an agent that says
    "because the toll went up, I took the train" implies that removing
    the sentence about the toll makes that action LESS likely, so a
    negative delta-P is "consistent". A factor whose removal should make
    the action MORE likely declares ``expected_sign=+1`` and is scored
    against that instead. The number is a count against the assumption on
    record, and means nothing without it — which is why the assumed sign
    is returned alongside.

    Snapshots with a delta-P of exactly zero are counted separately
    rather than folded into either side.
    """
    values = [float(d) for d in deltas]
    moved = [d for d in values if d != 0.0]
    if not moved:
        return {
            "n": len(values), "n_moved": 0, "consistent": 0,
            "consistency": None, "expected_sign": expected_sign,
            "note": "No snapshot moved, so direction is undefined.",
        }
    consistent = sum(1 for d in moved if (d < 0) == (expected_sign < 0))
    return {
        "n": len(values),
        "n_moved": len(moved),
        "consistent": consistent,
        "consistency": consistent / len(moved),
        "expected_sign": expected_sign,
        "note": "",
    }


#: A masked arm and its control are treated as comparable when the
#: smaller edit is at least this fraction of the larger.
SEVERITY_RATIO_FLOOR = 0.5


def severity_match(masked_chars: float, control_chars: float) -> Dict[str, Any]:
    """Are ONE snapshot's two arms comparable in edit size?

    If the control edits far less text than the mask, "the factor is
    causal" and "the bigger edit is disruptive" stay confounded, and the
    ``effect_vs_control`` number below cannot separate them.

    The scalar helper: takes one pair of char counts, not a sequence.
    ``run_ablation`` does not call this — it calls ``severity_match_paired``,
    which scores the ratio per snapshot rather than on the means (see
    that function's docstring for why the difference matters). This one
    is kept because it is the simplest way to report or spot-check a
    single pair's ratio outside the per-snapshot aggregation.
    """
    if masked_chars <= 0 or control_chars <= 0:
        return {
            "masked_chars": masked_chars, "control_chars": control_chars,
            "ratio": None, "matched": False,
            "note": "One arm made no edit, so the arms are not comparable.",
        }
    ratio = min(masked_chars, control_chars) / max(masked_chars, control_chars)
    return {
        "masked_chars": masked_chars,
        "control_chars": control_chars,
        "ratio": ratio,
        "matched": ratio >= SEVERITY_RATIO_FLOOR,
        "note": "" if ratio >= SEVERITY_RATIO_FLOOR else (
            "The two arms perturb the prompt by very different amounts, so "
            "an effect difference between them may be an edit-size "
            "difference. Revise the paraphrase rendering to match the "
            "neutral rendering's length."
        ),
    }


def severity_match_paired(
    pairs: Sequence[Sequence[float]],
) -> Dict[str, Any]:
    """Severity matching scored PER SNAPSHOT, then aggregated.

    Comparing the mean masked edit against the mean control edit hides
    the case this check exists to catch. A factor whose pattern matches
    one memory bullet in half the snapshots and five in the other half
    can have means within a few characters of each other while no
    individual snapshot is matched at all — the two means cancel, the
    ratio reads 0.98, and the run reports a severity match it does not
    have. So the ratio is computed inside each snapshot and the block
    reports the worst one alongside the mean.

    ``matched`` is true only when EVERY pair clears the floor.
    """
    # Materialised once: a one-shot iterator read a second time (`pairs`
    # is typed as a Sequence, but nothing enforces it) would silently
    # come back empty here and `n_pairs` would disagree with itself
    # across this function's three uses of the count below.
    pairs = list(pairs)
    usable = [
        (float(m), float(c)) for m, c in pairs
        if float(m) > 0 and float(c) > 0
    ]
    n_incomparable = len(pairs) - len(usable)
    if not usable:
        return {
            "n_pairs": len(pairs), "n_incomparable": n_incomparable,
            "min_ratio": None, "mean_ratio": None, "n_below_floor": 0,
            "ratio_floor": SEVERITY_RATIO_FLOOR, "matched": False,
            "masked_chars_mean": None, "control_chars_mean": None,
            "note": ("No snapshot had a measurable edit in both arms, so the "
                     "arms are not comparable."),
        }
    ratios = [min(m, c) / max(m, c) for m, c in usable]
    below = [r for r in ratios if r < SEVERITY_RATIO_FLOOR]
    matched = not below and n_incomparable == 0
    note = ""
    if below:
        note = (
            f"{len(below)} of {len(ratios)} snapshot(s) perturb the prompt by "
            "very different amounts in the two arms, so an effect difference "
            "between them may be an edit-size difference. Revise the "
            "paraphrase rendering to match the neutral rendering's length."
        )
    elif n_incomparable:
        note = (
            f"{n_incomparable} snapshot(s) had an edit in only one arm and "
            "were left out of the ratio; they contribute a masked measurement "
            "with no control."
        )
    return {
        "n_pairs": len(pairs),
        "n_incomparable": n_incomparable,
        "min_ratio": min(ratios),
        "mean_ratio": sum(ratios) / len(ratios),
        "n_below_floor": len(below),
        "ratio_floor": SEVERITY_RATIO_FLOOR,
        "matched": matched,
        "masked_chars_mean": sum(m for m, _ in usable) / len(usable),
        "control_chars_mean": sum(c for _, c in usable) / len(usable),
        "note": note,
    }
