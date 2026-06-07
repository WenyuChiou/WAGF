"""Catastrophe-model coupling example (Phase 6V).

Worked example of WAGF's generic environment-coupling layer (``broker.coupling``):
a governed LLM insurer agent coupled to a hazard -> exposure -> vulnerability ->
financial loss chain (OASIS Loss Modelling Framework shape), where the insurer's
world-mutating payout action is governed (ERROR-block + retry) *before* it debits
the shared pool.

Importing this package has two registration side effects (mirrors the
vaccination_demo pattern; no edit to broker/ source):
  1. ``ValidatorRegistry.register("cat_model", "physical", [payout-solvency check])``
     -- wires the world-mutation governance check into the validator dispatch.
  2. ``DomainPackRegistry.register("cat_model", CatModelDomainPack())``
     -- registers the pack (coupling default-OFF).

Import is gated by the runner behind the coupling flag, so a flag-OFF run never
imports this module (paper-3 byte-identity is unaffected — nothing here touches
the frozen flood/irrigation paths).
"""
from __future__ import annotations

from examples.cat_model.cat_pack import CatModelDomainPack
from examples.cat_model.cat_validators import CAT_MODEL_PHYSICAL_CHECKS

# Direct (no try/except ImportError swallow): this package only loads when the
# coupling flag is ON, and a failure to register the world-mutation governance
# check or the pack is a HARD error — silently skipping it would run the cat
# model with NO solvency governance / no pack. Fail loud so it is caught, not
# masked. (broker is always importable in this repo.)
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.domains.registry import DomainPackRegistry

ValidatorRegistry.register("cat_model", "physical", list(CAT_MODEL_PHYSICAL_CHECKS))
DomainPackRegistry.register("cat_model", CatModelDomainPack())

__all__ = ["CatModelDomainPack"]
