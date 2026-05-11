"""Re-export HBM framework registration from vaccination_demo.

The single-agent vaccination_demo registers `register_framework_metadata("hbm", ...)`
at import time. Importing it here triggers the same registration so the
individual agent type can use `psychological_framework: hbm` in YAML.

PMT is pre-registered globally; no extra step needed for health_authority
and community_org which use PMT.
"""
from examples.vaccination_demo import cognition  # noqa: F401  side-effect import
