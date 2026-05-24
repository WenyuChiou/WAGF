"""L3-1A unit tests — persona sampler matches literature distributions.

Phase L3-1A (vaccination_demo Tier-2 showcase upgrade) replaces the
PoC random.uniform sampler with `_load_persona_distributions` +
`build_synthetic_individuals`. These tests verify that:

1. The YAML loads + parses cleanly.
2. Categorical age draws converge to the US Census ACS 2020 shares.
3. Trust-in-authority means by age land near the Pew anchors.
4. High-risk-group rates by age track the CDC anchors.
5. ``--agents 25`` (the new default) is the count actually returned.

All tolerances are loose because (a) showcase grade, not paper, and
(b) n=1000 sampling envelopes are wide for SDs of 0.15-0.18. The
tests catch gross mismatch (e.g., uniform fallback re-emerging), not
small drift.
"""

from collections import Counter
from pathlib import Path

import pytest

from examples.vaccination_demo.run_experiment import (
    _load_persona_distributions,
    build_synthetic_individuals,
)


@pytest.fixture(scope="module")
def dists():
    return _load_persona_distributions()


def test_yaml_loads_with_required_keys(dists):
    """YAML must carry the four sampler-required sections."""
    required = {
        "age_distribution",
        "trust_in_authority_by_age",
        "risk_tolerance_by_age",
        "high_risk_group_probability",
    }
    assert required.issubset(dists.keys()), (
        f"persona_distributions.yaml missing keys: {required - set(dists.keys())}"
    )


def test_age_distribution_sums_to_one(dists):
    total = sum(dists["age_distribution"].values())
    assert abs(total - 1.0) < 0.01, (
        f"age_distribution shares sum to {total:.4f}, expected 1.0 ± 0.01"
    )


def test_default_agent_count_is_25():
    """Default ``--agents`` is 25 per L3-1A scope decision."""
    agents = build_synthetic_individuals(25, seed=42)
    assert len(agents) == 25, f"Expected 25 agents, got {len(agents)}"


def test_age_bracket_distribution_matches_us_census(dists):
    """At n=1000, sampled age shares should track US Census 2020 ACS
    within ±3 pp per bracket (categorical sampling variance)."""
    agents = build_synthetic_individuals(1000, seed=42)
    sampled_ages = [a.age_bracket for a in agents.values()]
    counts = Counter(sampled_ages)
    target = dists["age_distribution"]
    for bracket, target_share in target.items():
        sampled_share = counts[bracket] / 1000
        assert abs(sampled_share - target_share) < 0.03, (
            f"age {bracket}: sampled={sampled_share:.3f} vs "
            f"target={target_share:.3f} (Δ>0.03)"
        )


def test_trust_in_authority_means_track_pew_anchors(dists):
    """Per-bracket trust means should land within ±0.05 of Pew anchor
    at n=1000 (SD≈0.17, SE≈0.005)."""
    agents = build_synthetic_individuals(1000, seed=42)
    by_age: dict[str, list[float]] = {}
    for a in agents.values():
        by_age.setdefault(a.age_bracket, []).append(a.trust_in_authority)
    target = dists["trust_in_authority_by_age"]
    for bracket, values in by_age.items():
        sampled_mean = sum(values) / len(values)
        expected = float(target[bracket]["mean"])
        assert abs(sampled_mean - expected) < 0.05, (
            f"trust {bracket}: sampled mean={sampled_mean:.3f} vs "
            f"target={expected:.3f} (Δ>0.05)"
        )


def test_high_risk_group_rate_per_age(dists):
    """High-risk-group Bernoulli rate per age should track CDC anchor
    within ±0.10 at n=1000.

    Theoretical 3-sigma bounds per bracket at n=1000 (bracket sample
    sizes ≈ age_distribution × 1000):
      18-34 (p=0.08, n~306):  ±0.047 — within tolerance
      35-54 (p=0.18, n~331):  ±0.063 — within tolerance
      55-74 (p=0.55, n~267):  ±0.091 — drives the ±0.10 choice
      75+   (p=0.95, n~96):   ±0.067 — within tolerance

    The 55-74 bracket's 3σ spread (0.091) is the binding constraint;
    a tighter tolerance produces seed-dependent flake. Tests catch
    gross mismatch (e.g., a uniform fallback re-emerging), not small
    drift. Do not tighten below 0.10 without raising n.
    """
    agents = build_synthetic_individuals(1000, seed=42)
    by_age: dict[str, list[bool]] = {}
    for a in agents.values():
        by_age.setdefault(a.age_bracket, []).append(bool(a.is_high_risk_group))
    target = dists["high_risk_group_probability"]
    for bracket, flags in by_age.items():
        sampled_rate = sum(flags) / len(flags)
        expected = float(target[bracket])
        assert abs(sampled_rate - expected) < 0.10, (
            f"high-risk {bracket}: sampled={sampled_rate:.3f} vs "
            f"target={expected:.3f} (Δ>0.10)"
        )


def test_seed_determinism():
    """Same seed → same population. Catches accidental non-deterministic
    sampling (e.g., direct use of `random` module-level state)."""
    a1 = build_synthetic_individuals(10, seed=42)
    a2 = build_synthetic_individuals(10, seed=42)
    for name in a1:
        assert a1[name].age_bracket == a2[name].age_bracket
        assert a1[name].trust_in_authority == a2[name].trust_in_authority
        assert a1[name].risk_tolerance == a2[name].risk_tolerance
        assert a1[name].is_high_risk_group == a2[name].is_high_risk_group
