"""Water-domain (flood) InteractionHub configuration.

The generic :class:`broker.components.analytics.interaction.InteractionHub`
carries no domain vocabulary (Phase 6I-C de-flood). A flood experiment
passes these two structures to the hub constructor so neighbour
observation and the neighbour-action summary read in flood terms:

- ``FLOOD_ACTION_LABELS`` — maps a flood ``skill_id`` to a past-tense
  prose label, used by ``InteractionHub.get_neighbor_action_summary``.
- ``FLOOD_VISIBLE_ACTION_SPECS`` — declares which neighbour state
  attributes are physically observable (elevation, relocation,
  insurance) and how to describe them, used by
  ``InteractionHub.get_visible_neighbor_actions``.
"""

# skill_id -> human-readable past-tense label
FLOOD_ACTION_LABELS = {
    "do_nothing": "took no action",
    "buy_insurance": "bought flood insurance",
    "buy_contents_insurance": "bought contents insurance",
    "elevate_house": "elevated their home",
    "buyout_program": "applied for buyout",
    "relocate": "relocated",
}

# Each spec: a neighbour is flagged for the action when ANY of `state_keys`
# is truthy on its dynamic_state or as a direct attribute. `description`
# is a template formatted with the neighbour id as `nid`.
FLOOD_VISIBLE_ACTION_SPECS = [
    {
        "state_keys": ["elevated"],
        "action": "elevated_house",
        "description": "Neighbor {nid} has elevated their house",
    },
    {
        "state_keys": ["relocated"],
        "action": "relocated",
        "description": "Neighbor {nid} has moved away",
    },
    {
        "state_keys": ["has_insurance", "has_flood_insurance"],
        "action": "insured",
        "description": "Neighbor {nid} appears to have flood insurance",
    },
]

__all__ = ["FLOOD_ACTION_LABELS", "FLOOD_VISIBLE_ACTION_SPECS"]
