"""Tests for the de-flooded InteractionHub domain-vocabulary API (Phase 6I-C).

InteractionHub carries no flood vocabulary by default; a domain supplies
`action_labels` and `visible_action_specs` at construction. These tests
cover both the generic (no-spec) default and the flood-configured path.
"""
from broker.components.analytics.interaction import InteractionHub
from broker.components.social.graph import RandomGraph
from broker.domains.water.interaction_specs import (
    FLOOD_ACTION_LABELS,
    FLOOD_VISIBLE_ACTION_SPECS,
)


class _Agent:
    def __init__(self, **dynamic_state):
        self.dynamic_state = dynamic_state


def _hub(agents, **kwargs):
    graph = RandomGraph(list(agents.keys()), p=1.0)
    return InteractionHub(graph=graph, **kwargs)


def test_visible_actions_with_flood_specs():
    """A flood-configured hub flags elevated / relocated / insured neighbours."""
    agents = {
        "A": _Agent(elevated=True),
        "B": _Agent(relocated=True),
        "C": _Agent(has_insurance=True),
        "EGO": _Agent(),
    }
    hub = _hub(agents, visible_action_specs=FLOOD_VISIBLE_ACTION_SPECS)
    actions = hub.get_visible_neighbor_actions("EGO", agents)
    found = {a["action"] for a in actions}
    assert found == {"elevated_house", "relocated", "insured"}
    # description template is rendered with the neighbour id
    elev = next(a for a in actions if a["action"] == "elevated_house")
    assert elev["description"] == "Neighbor A has elevated their house"


def test_visible_actions_empty_specs_returns_empty():
    """With no specs (domain-neutral default) no neighbour actions surface,
    even when neighbours carry flood-named attributes."""
    agents = {"A": _Agent(elevated=True), "EGO": _Agent()}
    hub = _hub(agents)  # no visible_action_specs
    assert hub.get_visible_neighbor_actions("EGO", agents) == []


def test_neighbor_action_summary_uses_domain_label_map():
    """get_neighbor_action_summary maps skill ids through action_labels."""
    agents = {
        "A": _Agent(last_decision="buy_insurance"),
        "B": _Agent(last_decision="buy_insurance"),
        "EGO": _Agent(),
    }
    hub = _hub(agents, action_labels=FLOOD_ACTION_LABELS)
    summary = hub.get_neighbor_action_summary("EGO", agents)
    assert "bought flood insurance" in summary


def test_neighbor_action_summary_falls_back_to_prettified_id():
    """Without a label map the skill id is prettified (underscores -> spaces)."""
    agents = {
        "A": _Agent(last_decision="take_action"),
        "EGO": _Agent(),
    }
    hub = _hub(agents)  # no action_labels
    summary = hub.get_neighbor_action_summary("EGO", agents)
    assert "take action" in summary
