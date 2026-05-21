"""Flood-domain perception values.

Phase 6H Item 5: relocated out of generic broker code
(`broker/interfaces/perception.py` held `FLOOD_DEPTH_DESCRIPTORS`;
`broker/components/social/perception.py` held the flood field-lists).
Consumed by ``FloodDomainPack.perception_descriptors()`` and
``.perception_field_policy()``; the broker's
``PerceptionFilterRegistry`` injects them into
``HouseholdPerceptionFilter`` at construction.

The generic ``DAMAGE_SEVERITY_DESCRIPTORS`` / ``NEIGHBOR_COUNT_DESCRIPTORS``
stay in ``broker/interfaces/perception.py`` — they are domain-neutral and
reusable; only the flood-specific depth descriptor moved here.
"""
from broker.interfaces.perception import DescriptorMapping


# Numeric flood depth (ft) → qualitative descriptor.
FLOOD_DEPTH_DESCRIPTORS = DescriptorMapping(
    field_name="flood_depth",
    ranges=[
        (0.0, 0.5, "ankle-deep water"),
        (0.5, 2.0, "knee-deep water"),
        (2.0, 4.0, "waist-deep water"),
        (4.0, 8.0, "chest-deep water"),
        (8.0, float("inf"), "over-head water"),
    ],
    unit="ft",
)

# Exact dollar amounts stripped from household perception.
DOLLAR_AMOUNT_FIELDS = [
    "damage_amount",
    "payout_amount",
    "oop_cost",
    "property_value",
    "premium_cost",
    "elevation_cost",
]

# Exact percentages stripped from household perception.
PERCENTAGE_FIELDS = [
    "insurance_penetration_rate",
    "elevation_penetration_rate",
]

# Community-wide observables removed for marginalised-group agents.
COMMUNITY_OBSERVABLE_FIELDS = [
    "insurance_penetration_rate",
    "elevation_penetration_rate",
    "adaptation_rate",
    "relocation_rate",
    "community_flood_history",
    "avg_community_damage",
    "neighbor_insurance_rate",
    "neighbor_elevation_rate",
    "neighbors_insured",
    "neighbors_elevated",
    "neighbors_relocated",
]

# Neighbour-action counts converted to qualitative descriptions.
NEIGHBOR_ACTION_FIELDS = [
    "neighbors_insured",
    "neighbors_elevated",
    "neighbors_relocated",
]


__all__ = [
    "FLOOD_DEPTH_DESCRIPTORS",
    "DOLLAR_AMOUNT_FIELDS",
    "PERCENTAGE_FIELDS",
    "COMMUNITY_OBSERVABLE_FIELDS",
    "NEIGHBOR_ACTION_FIELDS",
]
