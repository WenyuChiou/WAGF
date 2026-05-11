"""gossip validator registration.

v1 has no domain-specific physical/personal/social/etc validators.
Cross-agent coherence rules go in YAML rules: block (currently empty).
Future v2: e.g. block influencer from posting if they were warned twice
this week (temporal rule); block casual_user from reporting their own
posts (semantic rule).
"""
# No-op for v1 — all rules will live in agent_types.yaml rules: block
# if/when added. This file exists so __init__.py side-effect import
# doesn't fail.
