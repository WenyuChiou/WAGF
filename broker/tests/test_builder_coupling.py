"""Tests for ExperimentBuilder.with_coupling (Wave 3 item 3-1, review P1-4).

The builder-level coupling entry replaces the hand-rolled assembly every
coupled runner previously copy-pasted (run_cat.py:112-120). Locks:
(1) flag ON -> sim engine wrapped in EnvironmentCouplingAdapter (raw engine
preserved as real_engine); (2) flag OFF / undeclared -> engine untouched;
(3) NOT calling with_coupling never imports broker.coupling (the frozen-path
no-import property); (4) domain defaults from governance.domain in the YAML.
Follows the builder-state test idiom of test_experiment_builder_policy.py
(no full runner construction needed).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
import yaml as _yaml

from broker.core.experiment_builder import ExperimentBuilder

REPO = Path(__file__).resolve().parents[2]


def _write_yaml(tmp_path: Path, enable: bool | None, domain: str | None = "cat_model") -> Path:
    cfg: dict = {"global_config": {"governance": {}}}
    if domain:
        cfg["global_config"]["governance"]["domain"] = domain
    if enable is not None:
        cfg["global_config"]["coupling"] = {"enable": enable}
    p = tmp_path / "agent_types.yaml"
    p.write_text(_yaml.safe_dump(cfg), encoding="utf-8")
    return p


def _contract_and_bundle():
    import examples.cat_model  # noqa: F401 — registers the cat pack
    from broker.coupling import CouplingContract, VarSpec
    from examples.cat_model.coupling_modules import CatBundle, FloodFootprintSource, PortfolioLedger

    contract = CouplingContract(
        observations=(VarSpec("flood_depth_ft", float, "ft", lo=0.0, hi=100.0),),
    )
    bundle = CatBundle(FloodFootprintSource({1: 2.0}), PortfolioLedger(10_000.0))
    return contract, bundle


class _RawEngine:
    def advance_step(self):
        return {"current_year": 1}


def test_flag_on_wraps_sim_engine(tmp_path):
    from broker.coupling import EnvironmentCouplingAdapter

    contract, bundle = _contract_and_bundle()
    raw = _RawEngine()
    b = ExperimentBuilder().with_simulation(raw).with_coupling(contract, bundle)
    b.agent_types_path = str(_write_yaml(tmp_path, enable=True))
    b._apply_coupling()
    assert isinstance(b.sim_engine, EnvironmentCouplingAdapter)
    assert b.sim_engine.real_engine is raw  # raw engine preserved underneath


def test_flag_off_leaves_engine_untouched(tmp_path):
    contract, bundle = _contract_and_bundle()
    raw = _RawEngine()
    b = ExperimentBuilder().with_simulation(raw).with_coupling(contract, bundle)
    # enable absent + cat pack default OFF -> unwrapped
    b.agent_types_path = str(_write_yaml(tmp_path, enable=None))
    b._apply_coupling()
    assert b.sim_engine is raw


def test_explicit_disable_wins(tmp_path):
    contract, bundle = _contract_and_bundle()
    raw = _RawEngine()
    b = ExperimentBuilder().with_simulation(raw).with_coupling(contract, bundle)
    b.agent_types_path = str(_write_yaml(tmp_path, enable=False))
    b._apply_coupling()
    assert b.sim_engine is raw


def test_no_with_coupling_is_total_noop(tmp_path):
    raw = _RawEngine()
    b = ExperimentBuilder().with_simulation(raw)
    b.agent_types_path = str(_write_yaml(tmp_path, enable=True))  # flag set but undeclared
    b._apply_coupling()
    assert b.sim_engine is raw


def test_fluent_chain_returns_self():
    contract, bundle = _contract_and_bundle()
    b = ExperimentBuilder()
    assert b.with_coupling(contract, bundle) is b


def test_frozen_path_never_imports_coupling():
    """The lazy-import contract: importing the builder and building WITHOUT
    with_coupling must not load broker.coupling (subprocess so this session's
    own imports don't pollute the check)."""
    code = (
        "import sys\n"
        "from broker.core.experiment_builder import ExperimentBuilder\n"
        "b = ExperimentBuilder()\n"
        "b._apply_coupling()\n"  # undeclared -> returns before any coupling import
        "assert 'broker.coupling' not in sys.modules, 'coupling leaked into frozen path'\n"
        "print('NO_COUPLING_IMPORT_OK')\n"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0 and "NO_COUPLING_IMPORT_OK" in r.stdout, r.stderr


def test_unreadable_yaml_with_declared_coupling_raises():
    """Review W1: with_coupling is an EXPLICIT intent — an unreadable config
    must raise, never silently downgrade to an unwrapped engine."""
    contract, bundle = _contract_and_bundle()
    b = ExperimentBuilder().with_simulation(_RawEngine()).with_coupling(contract, bundle)
    b.agent_types_path = "Z:/definitely/not/a/real/path/agent_types.yaml"
    with pytest.raises(RuntimeError, match="unreadable"):
        b._apply_coupling()


def test_double_apply_does_not_double_wrap(tmp_path):
    """Review W2: build() has no one-shot contract — a second _apply_coupling
    must be idempotent (no adapter-wrapping-adapter)."""
    from broker.coupling import EnvironmentCouplingAdapter

    contract, bundle = _contract_and_bundle()
    raw = _RawEngine()
    b = ExperimentBuilder().with_simulation(raw).with_coupling(contract, bundle)
    b.agent_types_path = str(_write_yaml(tmp_path, enable=True))
    b._apply_coupling()
    b._apply_coupling()  # second call: no-op
    assert isinstance(b.sim_engine, EnvironmentCouplingAdapter)
    assert b.sim_engine.real_engine is raw  # NOT another adapter
