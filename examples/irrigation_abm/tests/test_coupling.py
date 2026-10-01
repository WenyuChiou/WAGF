"""Tests for the v0.6 coupling-layer wiring (examples/irrigation_abm/coupling_modules.py).

Verifies:
1. Contract-off vs contract-on mock runs are byte-identical on
   simulation_log.csv, and identical on the governance audit CSV once the
   two EXPECTED, framework-level "world_*" columns are excluded (see
   coupling_modules.py's module docstring for why those two columns are
   an unavoidable, key-gated addition from broker/coupling/adapter.py plus
   broker/components/analytics/audit.py, shared by every coupled domain,
   not something IrrigationBundle can or should suppress). Checked for
   both a strict and a disabled governance profile, at workers=1 and at
   workers=4. Row order across worker counts has been deterministic since
   feat/v3-parallel-determinism (GenericAuditWriter._export_csv sorts by
   step_id at export); the workers=4 check below still sorts rows to a
   stable key before comparing, which predates that fix and is now a
   no-op, kept for defense in depth.
2. A contract-on run's run_integrity.json records coupling_adapter=True
   and the reproducibility manifest carries coupling_provenance with a
   contract_sha256 and derived_from_config pointing at the original file.
3. Turning on BOTH coupling.enable and coupling.context_contract carries
   BOTH sets of run_integrity.json keys, forwarded from the wrapped real
   engine via EnvironmentCouplingAdapter.__getattr__ (the finding-1 fix).
4. run_ungoverned_experiment.py's own --coupling flag is likewise
   byte-identical off vs on.
5. Feeding an out-of-bounds committed value, or a NaN world observation,
   through EnvironmentCouplingAdapter raises CouplingViolation
   (fail-loud), on both the commit side and the observation side.
6. The derived config copy rewrites prompt_template_file to an absolute
   path that still resolves.
7. The contract's derived bounds hold against the real 78-agent
   faf1bb12 seed-42 corpus, when present locally.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PROJECT_ROOT))

from broker.coupling import CouplingContract, EnvironmentCouplingAdapter, CouplingViolation, VarSpec
from broker.interfaces.skill_types import ApprovedSkill
from broker.tools.compare_audit_csv import compare
from examples.irrigation_abm.coupling_modules import (
    IrrigationBundle,
    build_irrigation_coupling_contract,
)
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig

RUN_EXPERIMENT = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_experiment.py"
RUN_UNGOVERNED = PROJECT_ROOT / "examples" / "irrigation_abm" / "run_ungoverned_experiment.py"
AUDIT_CSV_NAME = "irrigation_farmer_governance_audit.csv"
WORLD_COLUMNS = ("world_request", "world_contention_rule")
# Overridable via WAGF_IRRIGATION_CORPUS_SIMLOG (the corpus is a real-LLM
# results directory, gitignored and worktree-local, so it will not exist in
# a fresh clone or a fresh worktree; the repo-relative fallback below skips
# cleanly in that case, same as the env-var path would if it is unset).
CORPUS_SIMLOG = Path(
    os.environ.get(
        "WAGF_IRRIGATION_CORPUS_SIMLOG",
        str(
            PROJECT_ROOT / "examples" / "irrigation_abm" / "results"
            / "strict_42yr_gemma3_4b_faf1bb12_seed42" / "simulation_log.csv"
        ),
    )
)


def _run(script: Path, output_dir: Path, extra_args: list, timeout: int = 90) -> None:
    args = [sys.executable, str(script), *extra_args, "--output", str(output_dir)]
    result = subprocess.run(
        args, cwd=str(PROJECT_ROOT), capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, (
        f"{script.name} failed (args={extra_args}):\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


def _run_experiment(output_dir: Path, governance_mode: str, coupling: bool, workers: int = 1):
    extra = [
        "--model", "mock", "--agents", "5", "--years", "3", "--seed", "42",
        "--governance-mode", governance_mode, "--workers", str(workers),
    ]
    if coupling:
        extra.append("--coupling")
    return _run(RUN_EXPERIMENT, output_dir, extra)


def _run_ungoverned(output_dir: Path, coupling: bool):
    extra = ["--model", "mock", "--agents", "5", "--years", "3", "--seed", "42"]
    if coupling:
        extra.append("--coupling")
    return _run(RUN_UNGOVERNED, output_dir, extra)


def _sorted_copy(src: Path, dst: Path) -> None:
    """Write a row-order-stabilised copy of an audit CSV: sorted by
    (year, agent_id), which is stable across both coupling on/off AND
    across the ThreadPoolExecutor completion-order non-determinism that
    workers>1 already exhibits independently of coupling.

    (year, agent_id) must be unique for this sort to be a meaningful
    stand-in for "the same decision, wherever it landed" - a duplicate
    pair would let two DIFFERENT rows swap identity between the off and
    on files while still comparing as a false match, silently defeating
    the point of sorting before comparing.
    """
    df = pd.read_csv(src, encoding="utf-8-sig")
    dupes = df.duplicated(subset=["year", "agent_id"], keep=False)
    assert not dupes.any(), (
        f"{src} has {int(dupes.sum())} row(s) sharing a (year, agent_id) "
        f"pair - _sorted_copy's stable-key comparison is not valid here: "
        f"{df.loc[dupes, ['year', 'agent_id']].to_dict('records')}"
    )
    df = df.sort_values(["year", "agent_id"]).reset_index(drop=True)
    df.to_csv(dst, index=False)


def _make_config_dir_with_context_contract(tmp_path: Path) -> Path:
    """A full isolated copy of examples/irrigation_abm/config (required by
    --config-dir) with global_config.coupling.context_contract: true added,
    so a test can turn on BOTH coupling flags at once without touching the
    frozen in-tree config."""
    src = PROJECT_ROOT / "examples" / "irrigation_abm" / "config"
    dst = tmp_path / "config_both"
    shutil.copytree(src, dst)
    agent_types_path = dst / "agent_types.yaml"
    cfg = yaml.safe_load(agent_types_path.read_text(encoding="utf-8"))
    cfg.setdefault("global_config", {}).setdefault("coupling", {})["context_contract"] = True
    agent_types_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    return dst


@pytest.mark.parametrize("governance_mode", ["strict", "disabled"])
def test_coupling_off_vs_on_byte_identical(tmp_path: Path, governance_mode: str):
    off_dir = tmp_path / f"off_{governance_mode}"
    on_dir = tmp_path / f"on_{governance_mode}"
    _run_experiment(off_dir, governance_mode, coupling=False)
    _run_experiment(on_dir, governance_mode, coupling=True)

    # simulation_log.csv: fully byte-identical, no exceptions.
    sim_rc = compare(off_dir / "simulation_log.csv", on_dir / "simulation_log.csv")
    assert sim_rc == 0, "simulation_log.csv must be byte-identical with coupling on vs off"

    # governance audit CSV: identical once the two key-gated world_* columns
    # (an unavoidable, generic broker.coupling side effect, see
    # coupling_modules.py's module docstring) are excluded.
    audit_rc = compare(
        off_dir / AUDIT_CSV_NAME, on_dir / AUDIT_CSV_NAME,
        drop_columns=WORLD_COLUMNS,
    )
    assert audit_rc == 0, "governance audit CSV must be identical aside from the world_* columns"

    # The two world_* columns ARE present on the coupled run and absent OFF
    # (documents the exact, bounded scope of the schema addition).
    off_header = (off_dir / AUDIT_CSV_NAME).read_text(encoding="utf-8-sig").splitlines()[0]
    on_header = (on_dir / AUDIT_CSV_NAME).read_text(encoding="utf-8-sig").splitlines()[0]
    for col in WORLD_COLUMNS:
        assert col not in off_header
        assert col in on_header


def test_coupling_off_vs_on_byte_identical_workers_4(tmp_path: Path):
    """AR-3 (broker/INVARIANTS.md "Accepted risks") warns that workers>1
    with coupling is generically unsupported. This test is the empirical
    check backing coupling_modules.py's "WORKERS" section: content is
    identical for irrigation specifically. Row order across worker counts
    has been deterministic since feat/v3-parallel-determinism
    (GenericAuditWriter._export_csv sorts by step_id at export); before
    that fix two coupling-OFF runs at workers=4 produced different row
    orders from each other (verified by hand while writing this test)
    because the audit writer appended rows in ThreadPoolExecutor
    completion order, a property of workers>1 that had nothing to do with
    coupling. The stable-key sort below predates that fix and is now a
    no-op, kept for defense in depth.
    """
    off_dir = tmp_path / "off_w4"
    on_dir = tmp_path / "on_w4"
    _run_experiment(off_dir, "strict", coupling=False, workers=4)
    _run_experiment(on_dir, "strict", coupling=True, workers=4)

    sim_rc = compare(off_dir / "simulation_log.csv", on_dir / "simulation_log.csv")
    assert sim_rc == 0, "simulation_log.csv must be byte-identical at workers=4 too"

    off_sorted = tmp_path / "off_w4_audit_sorted.csv"
    on_sorted = tmp_path / "on_w4_audit_sorted.csv"
    _sorted_copy(off_dir / AUDIT_CSV_NAME, off_sorted)
    _sorted_copy(on_dir / AUDIT_CSV_NAME, on_sorted)
    audit_rc = compare(off_sorted, on_sorted, drop_columns=WORLD_COLUMNS)
    assert audit_rc == 0, (
        "governance audit CSV content (sorted by year, agent_id) must be "
        "identical at workers=4, aside from the world_* columns"
    )


def test_coupling_on_manifest_and_integrity_provenance(tmp_path: Path):
    on_dir = tmp_path / "on_provenance"
    _run_experiment(on_dir, "strict", coupling=True)

    integrity = json.loads((on_dir / "run_integrity.json").read_text(encoding="utf-8"))
    assert integrity.get("coupling_adapter") is True
    assert integrity.get("sim_engine_class") == "EnvironmentCouplingAdapter"

    manifest = json.loads((on_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    prov = manifest.get("coupling_provenance")
    assert isinstance(prov, dict)
    assert prov.get("bundle_class") == "IrrigationBundle"
    assert isinstance(prov.get("contract_sha256"), str) and prov["contract_sha256"]

    # derived_from_config: original path recorded next to agent_types_config
    # (the derived copy), item 2's manifest hook.
    original_path = str(PROJECT_ROOT / "examples" / "irrigation_abm" / "config" / "agent_types.yaml")
    assert manifest.get("derived_from_config") == original_path
    derived_path = Path(manifest["agent_types_config"])
    assert derived_path == on_dir / "agent_types.coupling.yaml"
    assert derived_path.exists(), "the derived config must be a PERSISTENT file, not deleted at exit"


def test_coupling_off_default_has_no_coupling_provenance(tmp_path: Path):
    off_dir = tmp_path / "off_default"
    _run_experiment(off_dir, "strict", coupling=False)
    integrity = json.loads((off_dir / "run_integrity.json").read_text(encoding="utf-8"))
    assert "coupling_adapter" not in integrity
    manifest = json.loads((off_dir / "reproducibility_manifest.json").read_text(encoding="utf-8"))
    assert "coupling_provenance" not in manifest
    assert manifest.get("derived_from_config") is None
    assert not (off_dir / "agent_types.coupling.yaml").exists()


def test_coupling_and_context_contract_both_on_manifest_keys(tmp_path: Path):
    """Finding-1 regression: EnvironmentCouplingAdapter.__getattr__ forwards
    get_coupling_retrofit_metadata to the wrapped IrrigationEnvironment, so
    a run with BOTH coupling.enable and coupling.context_contract on
    carries both sets of run_integrity.json keys, not just the adapter's."""
    config_dir = _make_config_dir_with_context_contract(tmp_path)
    on_dir = tmp_path / "both_on"
    _run(
        RUN_EXPERIMENT, on_dir,
        ["--model", "mock", "--agents", "5", "--years", "3", "--seed", "42",
         "--governance-mode", "strict", "--coupling", "--config-dir", str(config_dir)],
    )
    integrity = json.loads((on_dir / "run_integrity.json").read_text(encoding="utf-8"))
    # Adapter-side keys (coupling.enable).
    assert integrity.get("coupling_adapter") is True
    assert integrity.get("sim_engine_class") == "EnvironmentCouplingAdapter"
    # Context-contract-side keys (coupling.context_contract), forwarded
    # THROUGH the adapter by __getattr__ rather than lost behind it.
    assert integrity.get("coupling_contract_active") is True
    assert isinstance(integrity.get("coupling_contract_fields"), dict)
    assert integrity.get("coupling_contract_fields")
    assert integrity.get("coupling_guard_calls", 0) > 0


def test_ungoverned_coupling_off_vs_on_byte_identical(tmp_path: Path):
    off_dir = tmp_path / "ungov_off"
    on_dir = tmp_path / "ungov_on"
    _run_ungoverned(off_dir, coupling=False)
    _run_ungoverned(on_dir, coupling=True)

    sim_rc = compare(off_dir / "simulation_log.csv", on_dir / "simulation_log.csv")
    assert sim_rc == 0

    audit_rc = compare(
        off_dir / AUDIT_CSV_NAME, on_dir / AUDIT_CSV_NAME, drop_columns=WORLD_COLUMNS,
    )
    assert audit_rc == 0


def test_coupling_derived_config_has_absolute_prompt_template_file(tmp_path: Path):
    """The derived config copy lives under the run's output directory, a
    different directory than the original agent_types.yaml, so a relative
    prompt_template_file reference must be rewritten to an absolute path
    that still resolves. Checked directly against the written file, AND
    against the run's captured stdout+stderr for the absence of a
    "template file not found" / "Failed to read prompt file" warning."""
    on_dir = tmp_path / "on_template_check"
    result = _run_experiment(on_dir, "strict", coupling=True)

    combined_output = (result.stdout or "") + (result.stderr or "")
    assert "template file not found" not in combined_output.lower()
    assert "failed to read prompt file" not in combined_output.lower()
    assert "left relative" not in combined_output, (
        "prompt_template_file should have resolved against the default "
        "(non --config-dir) layout; a 'left relative' line here means the "
        "absolutize fallback did not fire the way this test expects"
    )

    derived = on_dir / "agent_types.coupling.yaml"
    assert derived.exists()
    cfg = yaml.safe_load(derived.read_text(encoding="utf-8"))
    template_ref = cfg["irrigation_farmer"]["prompt_template_file"]
    assert Path(template_ref).is_absolute()
    assert Path(template_ref).exists()


def test_violation_out_of_bounds_committed_request_raises():
    """Feed a real committed demand value through the adapter under a
    deliberately tight contract bound (production IrrigationBundle,
    unmodified) and assert the fail-loud CouplingViolation fires."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_synthetic(n_agents=2)
    aid = env.agent_ids[0]

    base_contract = build_irrigation_coupling_contract(env)
    tight_contract = CouplingContract(
        observations=base_contract.observations,
        inputs=(
            VarSpec(
                "request", float, "acre_ft",
                lo=0.0, hi=1.0,  # deliberately far below any real committed request
                direction="agent_to_world",
            ),
        ),
        decision_cadence="annual",
        solver_cadence="annual",
    )
    bundle = IrrigationBundle(env)
    adapter = EnvironmentCouplingAdapter(real_engine=env, contract=tight_contract, sources=bundle)
    adapter.advance_step()

    approved = ApprovedSkill(
        skill_name="increase_large", agent_id=aid, approval_status="APPROVED", parameters={},
    )
    with pytest.raises(CouplingViolation):
        adapter.execute_skill(approved)


def test_violation_commit_world_delta_failure_is_fail_loud():
    """A commit for an unknown agent must raise CouplingViolation rather
    than silently succeeding (IrrigationEnvironment.execute_skill returns
    success=False for an unknown agent id)."""
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_synthetic(n_agents=2)
    bundle = IrrigationBundle(env)

    approved = ApprovedSkill(
        skill_name="increase_large", agent_id="NOT_A_REAL_AGENT",
        approval_status="APPROVED", parameters={},
    )
    with pytest.raises(CouplingViolation):
        bundle.commit_world_delta(approved)


def test_violation_observation_side_nan_drought_index_raises(monkeypatch):
    """A corrupted world reading (NaN drought_index) must raise
    CouplingViolation from advance_step(), the OBSERVATION-side failure
    mode documented in coupling_modules.py's "FAILURE MODE" section (this
    one aborts the whole run, unlike the commit-side violation above).

    advance_year() recomputes drought_index internally every call, so
    setting env._global["drought_index"] directly before calling
    advance_step() would just be overwritten; the real engine's own
    advance_year() is called and then its RETURNED dict is poisoned,
    simulating a corrupted world reading reaching the adapter.
    """
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    env.initialize_synthetic(n_agents=2)
    bundle = IrrigationBundle(env)
    contract = build_irrigation_coupling_contract(env)
    adapter = EnvironmentCouplingAdapter(real_engine=env, contract=contract, sources=bundle)

    real_advance_year = env.advance_year

    def _poisoned_advance_year():
        out = real_advance_year()
        out["drought_index"] = float("nan")
        return out

    monkeypatch.setattr(env, "advance_year", _poisoned_advance_year)

    with pytest.raises(CouplingViolation):
        adapter.advance_step()


def test_contract_bounds_against_faf1bb12_corpus():
    """The derived bounds (build_irrigation_coupling_contract) must not
    reject any value the real 78-agent, 42-year faf1bb12 seed-42 corpus
    actually produced. Skips when the corpus is not present locally (it
    lives in the primary clone, not this worktree, and is not required
    for the rest of this test module to pass)."""
    if not CORPUS_SIMLOG.exists():
        pytest.skip(f"corpus not present at {CORPUS_SIMLOG}")

    df = pd.read_csv(CORPUS_SIMLOG)

    # Seed a minimal env whose per-agent water_right values come straight
    # from the corpus (only water_right feeds the bounds this test checks;
    # the rest of the env's initialise-agent bookkeeping is irrelevant).
    env = IrrigationEnvironment(WaterSystemConfig(seed=42))
    per_agent_water_right = df.groupby("agent_id")["water_right"].max()
    for aid, water_right in per_agent_water_right.items():
        env._agents[aid] = {
            "basin": "lower_basin", "diversion": 0.0, "request": 0.0,
            "water_right": float(water_right), "curtailment_ratio": 0.0,
            "at_allocation_cap": False, "has_efficient_system": False,
            "below_minimum_utilisation": False, "cluster": "unknown",
        }
    contract = build_irrigation_coupling_contract(env)

    request_spec = contract.input_specs()["request"]
    bad_request = [v for v in df["request"] if request_spec.range_violation(v)]
    assert not bad_request, (
        f"{len(bad_request)} corpus request values violate the derived "
        f"bound (hi={request_spec.hi}, corpus max={df['request'].max()})"
    )

    drought_spec = contract.observation_specs()["drought_index"]
    bad_drought = [v for v in df["drought_index"] if drought_spec.range_violation(v)]
    assert not bad_drought

    tbd_spec = contract.observation_specs()["total_basin_demand"]
    per_year_demand = df.groupby("year")["request"].sum()
    bad_tbd = [v for v in per_year_demand if tbd_spec.range_violation(v)]
    assert not bad_tbd, (
        f"per-year total demand violates the derived bound "
        f"(hi={tbd_spec.hi}, corpus max={per_year_demand.max()})"
    )

    # total_available_water is not logged per row in simulation_log.csv (it
    # is a global-per-year value, not a per-agent one); its bound is
    # verified analytically instead, from the SAME formula advance_year()
    # itself uses: variability = 1 - drought_index * 0.3 with drought_index
    # in [0, 1] (clamped by _compute_drought_index) is always in [0.7, 1.0],
    # which is exactly the bound build_irrigation_coupling_contract derives.
    taw_spec = contract.observation_specs()["total_available_water"]
    base = env.config.upper_basin_allocation + env.config.lower_basin_allocation
    for drought_index in df["drought_index"]:
        implied_taw = base * (1.0 - drought_index * 0.3)
        assert not taw_spec.range_violation(implied_taw)
