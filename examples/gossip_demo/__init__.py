"""Gossip social-media demo — Phase 6F target.

Import order:
  1. validators: registers any physical checks (none in v1)
  2. DomainPackRegistry.register("gossip", GossipDomainPack())
  3. register_social_spec for the 3 agent types
"""
# 1. Register validators (currently no-op — only YAML rules used)
from examples.gossip_demo import validators  # noqa: F401  side-effect

# 2. Register DomainPack
try:
    from broker.domains.registry import DomainPackRegistry
    from examples.gossip_demo.adapters.gossip_pack import GossipDomainPack
    DomainPackRegistry.register("gossip", GossipDomainPack())
except ImportError:
    pass

# 3. Register social specs (Phase 6E G1b)
try:
    from broker.components.social.config import (
        register_social_spec, SocialGraphSpec,
    )
    # casual_user: spatial radius=3 (neighborhood Facebook / NextDoor model)
    register_social_spec(
        "casual_user",
        SocialGraphSpec(graph_type="spatial", radius=3),
        overwrite=True,
    )
    # influencer: wider spatial reach (radius=5) — content reaches more users
    register_social_spec(
        "influencer",
        SocialGraphSpec(graph_type="spatial", radius=5),
        overwrite=True,
    )
    # platform_moderator: global view (sees all users)
    register_social_spec(
        "platform_moderator",
        SocialGraphSpec(graph_type="global"),
        overwrite=True,
    )
except ImportError:
    pass
