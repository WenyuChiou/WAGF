"""Backwards-compat shim — relocated in Phase 6P-A (2026-05-25).

The implementation now lives at
`broker.components.governance.domain_validator_dispatch`. This file
re-exports the public surface so legacy callers (including
`tests/test_validator_shadow_mode.py` and any user-side
`from broker.domains.water.validator_bundles import build_domain_validators`)
keep working without change.

Move rationale: the function body has been registry-driven and
domain-agnostic since Phase 6C-v2 (2026-05-10) — only its address was
still under `broker.domains.water.`, which forced
`broker/validators/governance/__init__.py::validate_all()` to reach
into a water-specific module to dispatch validators for ANY domain.
Phase 6P-A removes that runtime cross-namespace coupling for the
generic governance entrypoint.
"""

from broker.components.governance.domain_validator_dispatch import (
    build_domain_validators,
)

__all__ = ["build_domain_validators"]
