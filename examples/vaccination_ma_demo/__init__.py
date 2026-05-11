"""Multi-agent vaccination demo — Phase 6E target.

Import order:
  1. cognition: triggers HBM framework metadata registration via
     vaccination_demo's existing cognition package
  2. validators: registers physical checks under domain "vaccination_ma"
  3. DomainPackRegistry.register("vaccination_ma", VaccinationMADomainPack())
"""
# 1. Register HBM framework (reused from single-agent vaccination_demo)
from examples.vaccination_ma_demo import cognition  # noqa: F401  side-effect

# 2. Register validators
from examples.vaccination_ma_demo import validators  # noqa: F401  side-effect

# 3. Register DomainPack
try:
    from broker.domains.registry import DomainPackRegistry
    from examples.vaccination_ma_demo.adapters.vaccination_ma_pack import (
        VaccinationMADomainPack,
    )
    DomainPackRegistry.register("vaccination_ma", VaccinationMADomainPack())
except ImportError:
    pass

# 4. Register social specs (Tier 2 — spatial gossip).
# Tier 1 demo (broadcast-only) works via DEFAULT_SOCIAL_SPEC fallback;
# Tier 2 (run_experiment.py constructs InteractionHub +
# SpatialNeighborhoodGraph) needs explicit per-type specs so every agent
# type has a known graph topology. Phase 6C-v4 G1b register_social_spec
# API.
try:
    from broker.components.social.config import (
        register_social_spec, SocialGraphSpec,
    )
    # Individuals: see neighbors within 3 grid cells (spatial gossip).
    register_social_spec(
        "individual",
        SocialGraphSpec(graph_type="spatial", radius=3),
        overwrite=True,
    )
    # Institutional types: global view (aggregate, not local).
    register_social_spec(
        "health_authority",
        SocialGraphSpec(graph_type="global"),
        overwrite=True,
    )
    register_social_spec(
        "community_org",
        SocialGraphSpec(graph_type="global"),
        overwrite=True,
    )
except ImportError:
    pass
