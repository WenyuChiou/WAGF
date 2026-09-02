"""PR-5 — ablation metrics against distributions with known answers.

Every assertion here is a number worked out by hand, not a snapshot of
what the code happened to return. The pure-python Wilcoxon fallback is
checked against scipy on the same data, so the fallback cannot quietly
become a different test when scipy is absent.
"""
from __future__ import annotations

import math

import pytest

from broker.experiments import metrics as m


class TestActionDistribution:
    def test_counts_become_probabilities(self):
        dist = m.action_distribution(["a", "a", "b", "c"], ["a", "b", "c"])
        assert dist == {"a": 0.5, "b": 0.25, "c": 0.25}

    def test_vocabulary_entries_with_no_observations_are_zero(self):
        dist = m.action_distribution(["a", "a"], ["a", "b"])
        assert dist == {"a": 1.0, "b": 0.0}

    def test_unparsable_replies_are_their_own_outcome(self):
        """A mask that makes the model stop producing a valid decision
        HAS changed the behaviour; dropping those rows would hide it."""
        dist = m.action_distribution(["a", None], ["a"])
        assert dist["a"] == 0.5
        assert dist["__unparsed__"] == 0.5

    def test_observed_labels_outside_the_vocabulary_are_added(self):
        dist = m.action_distribution(["a", "z"], ["a"])
        assert set(dist) == {"a", "z"}


class TestJensenShannon:
    def test_identical_distributions_are_zero(self):
        p = {"a": 0.3, "b": 0.7}
        assert m.jensen_shannon_divergence(p, dict(p)) == pytest.approx(0.0, abs=1e-12)

    def test_disjoint_point_masses_are_one(self):
        """Base 2 puts the maximum at exactly 1.0 — the value a
        deterministic decider produces whenever it flips."""
        assert m.jensen_shannon_divergence({"a": 1.0}, {"b": 1.0}) == pytest.approx(1.0)

    def test_hand_worked_intermediate_case(self):
        # p = point mass on a; q = uniform over {a, b}; m = {a: .75, b: .25}
        # JSD = .5 * log2(1/.75) + .5 * (.5*log2(.5/.75) + .5*log2(.5/.25))
        expected = 0.5 * math.log2(1 / 0.75) + 0.5 * (
            0.5 * math.log2(0.5 / 0.75) + 0.5 * math.log2(0.5 / 0.25)
        )
        got = m.jensen_shannon_divergence({"a": 1.0}, {"a": 0.5, "b": 0.5})
        assert got == pytest.approx(expected)
        assert got == pytest.approx(0.3112781, abs=1e-6)

    def test_is_symmetric(self):
        p, q = {"a": 0.9, "b": 0.1}, {"a": 0.2, "b": 0.8}
        assert m.jensen_shannon_divergence(p, q) == pytest.approx(
            m.jensen_shannon_divergence(q, p))

    def test_missing_keys_are_treated_as_zero_probability(self):
        assert m.jensen_shannon_divergence({"a": 1.0}, {"b": 1.0}) == pytest.approx(
            m.jensen_shannon_divergence({"a": 1.0, "b": 0.0}, {"a": 0.0, "b": 1.0}))

    def test_a_degenerate_side_is_none_not_zero(self):
        """P2: 0.0 is the value for "identical", and a cell that produced
        no replies is not identical to anything. Returning 0.0 put
        "nothing happened" and "nothing ran" in the same column."""
        assert m.jensen_shannon_divergence({"a": 0.0, "b": 0.0}, {"a": 1.0}) is None
        assert m.jensen_shannon_divergence({}, {}) is None
        assert m.jensen_shannon_divergence({"a": 1.0}, {"a": 0.0}) is None

    def test_an_empty_replay_set_produces_a_degenerate_distribution(self):
        empty = m.action_distribution([], ["a", "b"])
        assert empty == {"a": 0.0, "b": 0.0}
        assert m.jensen_shannon_divergence(empty, {"a": 1.0, "b": 0.0}) is None
        assert m.kl_divergence(empty, {"a": 1.0, "b": 0.0}) is None


class TestKullbackLeibler:
    def test_identical_distributions_are_zero(self):
        p = {"a": 0.4, "b": 0.6}
        assert m.kl_divergence(p, dict(p)) == pytest.approx(0.0, abs=1e-9)

    def test_hand_worked_case(self):
        # KL(point mass on a || uniform over {a,b}) = log2(1/0.5) = 1
        assert m.kl_divergence({"a": 1.0, "b": 0.0},
                               {"a": 0.5, "b": 0.5}) == pytest.approx(1.0, abs=1e-6)

    def test_smoothing_keeps_a_zero_in_the_reference_finite(self):
        value = m.kl_divergence({"a": 0.5, "b": 0.5}, {"a": 1.0, "b": 0.0})
        assert math.isfinite(value)
        assert value > 0

    def test_is_not_symmetric(self):
        p, q = {"a": 0.9, "b": 0.1}, {"a": 0.2, "b": 0.8}
        assert m.kl_divergence(p, q) != pytest.approx(m.kl_divergence(q, p))

    def test_a_degenerate_side_is_none_not_zero(self):
        assert m.kl_divergence({"a": 0.0}, {"a": 1.0}) is None
        assert m.kl_divergence({"a": 1.0}, {"a": 0.0}) is None


class TestMinimumPairs:
    def test_the_floor_is_the_smallest_p_the_test_can_return(self):
        """With k non-zero pairs all moving the same way, the two-sided
        exact test returns 2 / 2**k = 2**-(k-1). Nothing below it is
        reachable, so a p at the floor is the design's limit rather than
        a measurement."""
        for k in (3, 5, 6, 7, 8):
            data = [float(i + 1) for i in range(k)]
            result = m.wilcoxon_signed_rank(data, prefer_scipy=False)
            assert result["p_value"] == pytest.approx(m.attainable_p_floor(k))

    def test_the_minimum_is_the_first_k_whose_floor_clears_one_percent(self):
        assert m.attainable_p_floor(m.MIN_PAIRS - 1) > 0.01
        assert m.attainable_p_floor(m.MIN_PAIRS) < 0.01

    def test_no_pairs_has_no_floor(self):
        assert m.attainable_p_floor(0) is None


class TestWilcoxonSignedRank:
    def test_all_positive_differences_hand_worked(self):
        """n=5, every difference positive: W- = 0 and the exact
        two-sided p is 2/2**5 = 0.0625."""
        result = m.wilcoxon_signed_rank([1.0, 2.0, 3.0, 4.0, 5.0])
        assert result["statistic"] == pytest.approx(0.0)
        assert result["p_value"] == pytest.approx(0.0625)
        assert result["n_nonzero"] == 5

    def test_perfectly_symmetric_data_gives_p_one(self):
        result = m.wilcoxon_signed_rank([1.0, -1.0, 2.0, -2.0])
        assert result["p_value"] == pytest.approx(1.0)

    def test_paired_form_matches_the_difference_form(self):
        x = [0.5, 0.4, 0.9, 0.1, 0.3]
        y = [0.1, 0.2, 0.2, 0.05, 0.1]
        paired = m.wilcoxon_signed_rank(x, y)
        diffs = m.wilcoxon_signed_rank([a - b for a, b in zip(x, y)])
        assert paired["p_value"] == pytest.approx(diffs["p_value"])
        assert paired["statistic"] == pytest.approx(diffs["statistic"])

    def test_all_zero_differences_is_reported_not_silently_passed(self):
        """The one case where a test cannot run. It must be visible as
        'undefined', never as a p-value of 1.0 that reads like a null."""
        result = m.wilcoxon_signed_rank([0.0, 0.0, 0.0])
        assert result["p_value"] is None
        assert result["method"] == "undefined"
        assert "nothing to rank" in result["note"]

    def test_zero_differences_are_dropped_from_the_ranking(self):
        result = m.wilcoxon_signed_rank([0.0, 1.0, 2.0, 3.0, 0.0])
        assert result["n_pairs"] == 5
        assert result["n_nonzero"] == 3

    def test_mismatched_pair_lengths_raise(self):
        with pytest.raises(ValueError, match="equal-length"):
            m.wilcoxon_signed_rank([1.0, 2.0], [1.0])

    def test_pure_python_fallback_matches_scipy(self):
        """The fallback is not an approximation of convenience — on
        tie-free small samples it is the same exact test."""
        pytest.importorskip("scipy")
        data = [0.4, -0.1, 0.7, 0.2, -0.3, 0.9, 0.15]
        with_scipy = m.wilcoxon_signed_rank(data, prefer_scipy=True)
        without = m.wilcoxon_signed_rank(data, prefer_scipy=False)
        assert "scipy" in with_scipy["method"]
        assert "exact" in without["method"]
        assert without["statistic"] == pytest.approx(with_scipy["statistic"])
        assert without["p_value"] == pytest.approx(with_scipy["p_value"], abs=1e-9)

    def test_fallback_names_itself_and_says_how_to_get_scipy(self):
        result = m.wilcoxon_signed_rank([1.0, 2.0, 3.0], prefer_scipy=False)
        assert "scipy unavailable" in result["method"]
        assert "analysis" in result["note"]

    def test_large_tied_sample_uses_the_normal_approximation(self):
        data = [1.0] * 12 + [-1.0] * 12
        result = m.wilcoxon_signed_rank(data, prefer_scipy=False)
        assert "normal approximation" in result["method"]
        assert result["p_value"] == pytest.approx(1.0, abs=0.05)


class TestDirectionalConsistency:
    def test_counts_only_the_snapshots_that_moved(self):
        result = m.directional_consistency([-0.5, -0.2, 0.3, 0.0])
        assert result["n"] == 4
        assert result["n_moved"] == 3
        assert result["consistent"] == 2
        assert result["consistency"] == pytest.approx(2 / 3)

    def test_all_in_the_predicted_direction(self):
        result = m.directional_consistency([-0.5, -0.25, -1.0])
        assert result["consistency"] == pytest.approx(1.0)

    def test_nothing_moved_is_undefined_not_zero(self):
        result = m.directional_consistency([0.0, 0.0])
        assert result["consistency"] is None
        assert "undefined" in result["note"]

    def test_expected_sign_can_be_flipped(self):
        result = m.directional_consistency([0.4, 0.6], expected_sign=1)
        assert result["consistency"] == pytest.approx(1.0)

    def test_the_assumed_sign_is_returned_with_the_count(self):
        """W1: the number is a count against an assumption, and means
        nothing without the assumption beside it."""
        assert m.directional_consistency([-0.5])["expected_sign"] == -1
        assert m.directional_consistency(
            [-0.5], expected_sign=1)["expected_sign"] == 1


class TestSeverityMatch:
    def test_comparable_edits_match(self):
        result = m.severity_match(30.0, 48.0)
        assert result["ratio"] == pytest.approx(30 / 48)
        assert result["matched"] is True
        assert result["note"] == ""

    def test_wildly_different_edits_do_not_match_and_say_why(self):
        result = m.severity_match(10.0, 100.0)
        assert result["matched"] is False
        assert "edit-size difference" in result["note"]

    def test_an_arm_that_edited_nothing_is_incomparable(self):
        result = m.severity_match(30.0, 0.0)
        assert result["ratio"] is None
        assert result["matched"] is False


class TestSeverityMatchPaired:
    def test_means_can_agree_while_no_pair_does(self):
        """S3: the reason severity is scored per snapshot. These two
        columns have identical means (55) and not one matched pair, so
        the mean-of-means form reported ratio 1.0 on a run where every
        single comparison was confounded by edit size."""
        pairs = [(100.0, 10.0), (10.0, 100.0)]
        means = m.severity_match(
            sum(p[0] for p in pairs) / 2, sum(p[1] for p in pairs) / 2)
        assert means["matched"] is True          # what the old form said
        paired = m.severity_match_paired(pairs)
        assert paired["matched"] is False        # what is actually true
        assert paired["n_below_floor"] == 2
        assert paired["min_ratio"] == pytest.approx(0.1)

    def test_matched_when_every_pair_clears_the_floor(self):
        result = m.severity_match_paired([(30.0, 48.0), (40.0, 44.0)])
        assert result["matched"] is True
        assert result["n_below_floor"] == 0
        assert result["min_ratio"] == pytest.approx(30 / 48)
        assert result["mean_ratio"] == pytest.approx(((30 / 48) + (40 / 44)) / 2)

    def test_a_pair_with_one_empty_arm_is_excluded_and_counted(self):
        result = m.severity_match_paired([(30.0, 48.0), (25.0, 0.0)])
        assert result["n_incomparable"] == 1
        assert result["matched"] is False
        assert "only one arm" in result["note"]

    def test_no_usable_pair_is_reported_not_scored(self):
        result = m.severity_match_paired([(0.0, 0.0)])
        assert result["min_ratio"] is None
        assert result["matched"] is False
        assert "not comparable" in result["note"]
