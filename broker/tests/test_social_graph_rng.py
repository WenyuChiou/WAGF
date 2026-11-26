"""Tests for RandomGraph RNG determinism and global state isolation."""
from __future__ import annotations

import random

from broker.components.social.graph import RandomGraph


def test_random_graph_is_deterministic_for_given_seed():
    ids = [f"A_{i}" for i in range(10)]
    g1 = RandomGraph(ids, p=0.4, seed=42)
    g2 = RandomGraph(ids, p=0.4, seed=42)

    edges1 = {aid: sorted(g1.get_neighbors(aid)) for aid in ids}
    edges2 = {aid: sorted(g2.get_neighbors(aid)) for aid in ids}
    assert edges1 == edges2


def test_random_graph_seed_does_not_mutate_global_random_state():
    ids = [f"A_{i}" for i in range(12)]

    random.seed(999)
    expected_next = random.random()

    random.seed(999)
    _ = RandomGraph(ids, p=0.5, seed=12345)
    actual_next = random.random()

    assert actual_next == expected_next
