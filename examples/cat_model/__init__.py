"""Catastrophe-model coupling example (Phase 6V).

Worked example of WAGF's generic environment-coupling layer (``broker.coupling``):
a governed LLM insurer agent coupled to a hazard -> exposure -> vulnerability ->
financial loss chain (OASIS Loss Modelling Framework shape), where the insurer's
world-mutating payout action is governed (ERROR-block + retry) *before* it debits
the shared pool.

Importing this package registers BOTH cat domains (mirrors the
vaccination_demo pattern; no edit to broker/ source):
  1. ``ValidatorRegistry.register("cat_model", "physical", [payout-solvency check])``
     -- single-agent world-mutation governance check.
  2. ``DomainPackRegistry.register("cat_model", CatModelDomainPack())``
     -- single-agent pack (coupling default-OFF).
  3. ``ValidatorRegistry.register("cat_model_ma", "physical", MA checks)``
     -- multi-agent claim/settlement/relief checks (separate registry bucket;
     never clobbers the single-agent registration).
  4. ``DomainPackRegistry.register("cat_model_ma", CatModelDomainPack())``
     -- same pack class under the MA domain name (review C1: without this,
     ``DomainPackRegistry.get("cat_model_ma")`` returned None and any
     ``get_or_default`` would warn-and-default). Coupling stays default-OFF
     at the pack level; the MA YAML enables it explicitly.

Import is gated by the runner behind the coupling flag, so a flag-OFF run never
imports this module (paper-3 byte-identity is unaffected — nothing here touches
the frozen flood/irrigation paths).
"""
from __future__ import annotations

from examples.cat_model.cat_pack import CatModelDomainPack
from examples.cat_model.cat_validators import CAT_MODEL_PHYSICAL_CHECKS
from examples.cat_model.ma_validators import MA_CAT_PHYSICAL_CHECKS

# Direct (no try/except ImportError swallow): this package only loads when the
# coupling flag is ON, and a failure to register the world-mutation governance
# check or the pack is a HARD error — silently skipping it would run the cat
# model with NO solvency governance / no pack. Fail loud so it is caught, not
# masked. (broker is always importable in this repo.)
from broker.components.governance.validator_registry import ValidatorRegistry
from broker.domains.registry import DomainPackRegistry

ValidatorRegistry.register("cat_model", "physical", list(CAT_MODEL_PHYSICAL_CHECKS))
DomainPackRegistry.register("cat_model", CatModelDomainPack())
ValidatorRegistry.register("cat_model_ma", "physical", list(MA_CAT_PHYSICAL_CHECKS))
DomainPackRegistry.register("cat_model_ma", CatModelDomainPack())

__all__ = ["CatModelDomainPack"]
