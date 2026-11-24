"""Physical governance checks for the reservoir-control example.

There are none registered any more. The dead-pool limit used to be a Python
check here that projected storage with a linear formula; it is now a
feasibility bound on the coupling contract (``dead_pool_violation`` in
``run_reservoir_ops._build_contract``), judged on the toy model's own what-if
run. The flood-control overflow limit is an ``expression:`` rule in the YAML.
The module stays so the registration in ``__init__`` and the DomainPack keep
importing; add a check to the tuple if the example needs one again.
"""
from __future__ import annotations

RESERVOIR_CONTROL_PHYSICAL_CHECKS = ()


__all__ = ["RESERVOIR_CONTROL_PHYSICAL_CHECKS"]
