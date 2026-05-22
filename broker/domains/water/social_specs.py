"""Water-domain social graph specifications."""
from broker.components.social.config import SocialGraphSpec, register_social_spec


def register_water_social_specs() -> None:
    """Register flood household and institution social graph specs."""
    # Phase 6J-C (2026-05-22): relocated from generic social config.
    register_social_spec(
        "household_nmg_owner",
        SocialGraphSpec(graph_type="spatial", radius=2),
        overwrite=True,
    )
    register_social_spec(
        "household_nmg_renter",
        SocialGraphSpec(graph_type="spatial", radius=2),
        overwrite=True,
    )
    register_social_spec(
        "household_mg_owner",
        SocialGraphSpec(graph_type="spatial", radius=1),
        overwrite=True,
    )
    register_social_spec(
        "household_mg_renter",
        SocialGraphSpec(graph_type="spatial", radius=1),
        overwrite=True,
    )
    register_social_spec(
        "government",
        SocialGraphSpec(graph_type="global"),
        overwrite=True,
    )
    register_social_spec(
        "insurance",
        SocialGraphSpec(graph_type="filtered_global", filter_fn="has_insurance"),
        overwrite=True,
    )
