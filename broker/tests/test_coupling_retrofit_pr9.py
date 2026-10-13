"""PR-9 coupling-retrofit + archetype-C tests.

Covers three findings from the PR-9 audit:

F1 -- ``IrrigationEnvironment.get_agent_context()`` silently defaults every
missing physical-state field to 0/False/"unknown", bypassing
``VarSpec(on_missing="fail_loud")`` entirely. Gated behind
``global_config.coupling.context_contract`` (default OFF): flag OFF pins
the legacy silent-default behaviour byte-for-byte; flag ON pins that a
genuinely missing field raises ``CouplingViolation`` naming it, and that a
fully-populated (v21-shaped) run raises nothing.

Plus the PR-9 REVIEW round, whose findings all trace to one root cause and
its blast radius:

P0 -- ``VarSpec.range_violation`` (the primitive EVERY guard in the coupling
layer calls) was NaN-blind and type-blind. ``TestRangeViolationP0`` pins each
newly-rejected value AND falsifies it against a reconstruction of the
pre-fix function, so "this test would have passed before" is not a claim but
a check.

P1 -- ``SubprocessModelConnector`` hardening (parse-time non-finite refusal,
timeout audit written before raising, undeclared-key warning, indexed
``intensity_at``, non-numeric ``value_var`` refused at construction).

P1-a..e / P2 -- the flag reaching all three irrigation runners, the audit
CSV's Mead column joining the guarded path, per-field check reporting,
unknown-basin refusal, and NaN CRSS cells refused at load time.

F2 -- archetype C (subprocess service model) was documented with zero code.
``broker.coupling.SubprocessModelConnector`` closes that gap; tested here
against tiny inline Python scripts (no dependency on the worked example
files, so these tests do not depend on subprocess timing of the real
example).

F3 -- the coupling-designer templates/playbook no longer claim ``last_good``
/ ``quarantine`` are usable ``VarSpec.on_missing`` values. A regression guard
scans the edited docs for any literal ``on_missing=<value>`` example and
checks it against what ``VarSpec`` actually accepts.
"""
from __future__ import annotations

import json
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Optional

import pytest

from broker.coupling.adapter import CouplingViolation
from broker.coupling.contract import CouplingContract, VarSpec
from broker.coupling.subprocess_source import SubprocessModelConnector
from examples.irrigation_abm.irrigation_coupling import (
    IRRIGATION_CONTEXT_FIELD_SOURCES,
    IRRIGATION_CONTEXT_UNCOVERED_KEYS,
    build_irrigation_agent_context_contract,
    guard_agent_context_sources,
    irrigation_contract_field_checks,
    irrigation_contract_field_names,
)
from examples.irrigation_abm.irrigation_env import IrrigationEnvironment, WaterSystemConfig

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# The PRE-FIX primitive, reconstructed verbatim from git history, so every P0
# assertion below can be shown to be a real change rather than a restatement
# of behaviour that already held. Used ONLY by TestRangeViolationP0.
# ---------------------------------------------------------------------------
def _pre_fix_range_violation(vs: VarSpec, value: object) -> Optional[str]:
    """``VarSpec.range_violation`` exactly as it stood before PR-9's review."""
    if value is None:
        return None
    if vs.dtype in (int, float):
        try:
            num = float(value)
        except (TypeError, ValueError):
            return f"{vs.name}={value!r} not coercible to {vs.dtype.__name__} ({vs.unit})"
        if vs.lo is not None and num < vs.lo:
            return f"{vs.name}={num} below lo={vs.lo} ({vs.unit})"
        if vs.hi is not None and num > vs.hi:
            return f"{vs.name}={num} above hi={vs.hi} ({vs.unit})"
    return None


# ---------------------------------------------------------------------------
# F1: irrigation physical-state guard
# ---------------------------------------------------------------------------
def _minimal_synthetic_env(coupling_contract_active: bool) -> IrrigationEnvironment:
    env = IrrigationEnvironment(
        WaterSystemConfig(seed=42),
        coupling_contract_active=coupling_contract_active,
    )
    env.initialize_synthetic(n_agents=4, basin_split=(2, 2))
    return env


class TestFlagOffLegacyBehaviourPinned:
    """Flag OFF: byte-for-byte the pre-PR-9 ``.get(key, default)`` path."""

    def test_missing_agent_field_defaults_silently(self):
        env = _minimal_synthetic_env(coupling_contract_active=False)
        aid = next(iter(env.agent_ids))
        del env._agents[aid]["water_right"]  # simulate a genuinely missing field
        ctx = env.get_agent_context(aid)  # must NOT raise
        assert ctx["water_right"] == 0

    def test_missing_basin_field_defaults_silently(self):
        env = _minimal_synthetic_env(coupling_contract_active=False)
        aid = next(a for a in env.agent_ids if env._agents[a]["basin"] == "lower_basin")
        del env._basins["lower_basin"]["lake_mead_level"]
        ctx = env.get_agent_context(aid)
        assert ctx["lake_mead_level"] == 0

    def test_default_construction_is_flag_off(self):
        # Positional call, exactly the pre-PR-9 call signature.
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        assert env._coupling_contract_active is False
        assert env._irrigation_contract is None


class TestFlagOnFailsLoud:
    """Flag ON: the SAME missing fields above now raise, naming themselves."""

    def test_missing_agent_field_raises_named(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        aid = next(iter(env.agent_ids))
        del env._agents[aid]["water_right"]
        with pytest.raises(CouplingViolation, match="water_right"):
            env.get_agent_context(aid)

    def test_missing_basin_field_raises_named(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        aid = next(a for a in env.agent_ids if env._agents[a]["basin"] == "lower_basin")
        del env._basins["lower_basin"]["lake_mead_level"]
        with pytest.raises(CouplingViolation, match="lake_mead_level"):
            env.get_agent_context(aid)

    def test_missing_global_field_raises_named(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        aid = next(iter(env.agent_ids))
        del env._global["drought_index"]
        with pytest.raises(CouplingViolation, match="drought_index"):
            env.get_agent_context(aid)

    def test_out_of_range_value_raises(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        aid = next(iter(env.agent_ids))
        env._agents[aid]["curtailment_ratio"] = 1.5  # contract: [0, 1]
        with pytest.raises(CouplingViolation, match="curtailment_ratio"):
            env.get_agent_context(aid)

    def test_unknown_agent_id_raises_rather_than_zeroing_everything(self):
        """Pre-PR-9: an unknown agent_id silently produced an almost-entirely
        zeroed/defaulted context (agent = {}). Flag ON now fails loud instead
        of manufacturing a plausible-looking empty profile."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        with pytest.raises(CouplingViolation):
            env.get_agent_context("NO_SUCH_AGENT")


class TestHappyPathNoRaise:
    """The actual PROOF requested by the task: a v21-shaped mock run does
    NOT raise with the flag on, because nothing is genuinely missing."""

    def test_fully_populated_agent_context_no_raise(self):
        # advance_year() first, exactly like the real pipeline: the runner
        # always calls sim_engine.advance_year() before the pre_year hook
        # reads get_agent_context() (experiment_runner.py's iteration
        # sequence). Fields like total_basin_demand are populated INSIDE
        # advance_year(), not at __init__ -- calling get_agent_context()
        # before any advance_year() is not a scenario the real pipeline
        # exercises.
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        for aid in env.agent_ids:
            ctx = env.get_agent_context(aid)  # must not raise
            assert ctx["agent_id"] == aid

    def test_multi_year_synthetic_run_no_raise(self):
        """Advance several years (mutating precipitation / lake_mead_level /
        drought_index / curtailment / diversion each year, exactly the
        real run's data path) and read every agent's context every year."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        for _year in range(3):
            env.advance_year()
            for aid in env.agent_ids:
                env.get_agent_context(aid)  # must not raise for any agent, any year

    def test_basin_scoped_fields_do_not_false_alarm(self):
        """Real finding from the PR-9 verification run: a naive (non-basin-
        scoped) contract raised CouplingViolation on lake_mead_level for
        EVERY upper-basin agent on the very first smoke run, because
        upper_basin's dict never carries that key by design (and lower_basin
        never carries precipitation). This is not a bug -- it is the
        deliberate per-basin telemetry split in irrigation_env.py -- so the
        fix is basin-scoping the requirement, not adding the field. Confirm
        the fix: an upper-basin agent's basin dict may lack lake_mead_level,
        and a lower-basin agent's basin dict may lack precipitation, and
        neither raises."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        assert "lake_mead_level" not in env._basins["upper_basin"]
        assert "precipitation" not in env._basins["lower_basin"]
        env.advance_year()  # populate total_basin_demand etc., matching real pipeline order
        ub_agent = next(a for a in env.agent_ids if env._agents[a]["basin"] == "upper_basin")
        lb_agent = next(a for a in env.agent_ids if env._agents[a]["basin"] == "lower_basin")
        env.get_agent_context(ub_agent)  # must not raise despite no lake_mead_level key
        env.get_agent_context(lb_agent)  # must not raise despite no precipitation key

    def test_basin_scoping_does_not_hide_a_genuine_gap(self):
        """The scoping table is not a blanket exemption: an upper-basin
        agent missing ITS OWN applicable field (precipitation) still
        raises."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        ub_agent = next(a for a in env.agent_ids if env._agents[a]["basin"] == "upper_basin")
        del env._basins["upper_basin"]["precipitation"]
        with pytest.raises(CouplingViolation, match="precipitation"):
            env.get_agent_context(ub_agent)


class TestContractFieldEnumeration:
    def test_all_get_agent_context_default_fields_covered(self):
        """Every field IrrigationEnvironment.get_agent_context() defaults
        via .get(key, X) must be declared in the contract -- this is the
        enumeration the PR-9 report cites."""
        expected = {
            "current_diversion", "current_request", "water_right",
            "curtailment_ratio", "at_allocation_cap", "has_efficient_system",
            "below_minimum_utilisation", "cluster", "basin",
            "precipitation", "lake_mead_level", "preceding_factor",
            "drought_index", "total_available_water", "total_basin_demand",
            # supply-side redesign (2026-09-25)
            "delivery_ratio", "gap_reason", "basin_request_over_target",
            "natural_flow_maf", "powell_storage_maf",
            # WP1b re-review (LOW 9, 2026-09-29): special-cased like
            # precipitation (checked only when precip_group is set), not a
            # plain _BASIN_SCOPED_FIELDS entry.
            "supply_group", "ub_subbasin_member_count",
        }
        assert set(IRRIGATION_CONTEXT_FIELD_SOURCES.keys()) == expected
        contract = build_irrigation_agent_context_contract()
        assert {vs.name for vs in contract.observations} == expected

    def test_field_names_helper_sorted_and_matches(self):
        assert irrigation_contract_field_names() == sorted(IRRIGATION_CONTEXT_FIELD_SOURCES)


class TestCouplingRetrofitMetadata:
    def test_metadata_reports_active_and_field_list(self):
        env_off = _minimal_synthetic_env(coupling_contract_active=False)
        meta_off = env_off.get_coupling_retrofit_metadata()
        assert meta_off["coupling_contract_active"] is False
        assert sorted(meta_off["coupling_contract_fields"]) == irrigation_contract_field_names()

        env_on = _minimal_synthetic_env(coupling_contract_active=True)
        meta_on = env_on.get_coupling_retrofit_metadata()
        assert meta_on["coupling_contract_active"] is True
        assert sorted(meta_on["coupling_contract_fields"]) == irrigation_contract_field_names()

    def test_fields_report_per_field_check_kind(self):
        """Review P1-c: a flat list read as though all fifteen fields were
        range-guarded; five are bool/str and have no range. WP1b re-review
        (LOW 9, 2026-09-29) adds a sixth, supply_group (str)."""
        meta = _minimal_synthetic_env(coupling_contract_active=True).get_coupling_retrofit_metadata()
        checks = meta["coupling_contract_fields"]
        assert isinstance(checks, dict)
        assert checks == irrigation_contract_field_checks()
        assert set(checks.values()) == {"presence+range", "presence+type"}
        # The non-numeric fields, named so a rename cannot silently
        # reclassify one into the range bucket.
        type_only = {k for k, v in checks.items() if v == "presence+type"}
        assert type_only == {
            "at_allocation_cap", "has_efficient_system",
            "below_minimum_utilisation", "cluster", "basin", "gap_reason",
            "supply_group",
        }
        assert checks["lake_mead_level"] == "presence+range"
        assert checks["ub_subbasin_member_count"] == "presence+range"

    def test_metadata_names_the_uncovered_context_keys(self):
        """Review P2: 'the contract covers 15 of 18 context keys' is only
        checkable if the other three are in the artifact. v3 (spec 1.6,
        2026-09-28) adds one more uncovered key, precipitation_flag; the
        2026-09-29 re-review (HIGH 2) adds a second, lb_shortage_volume_maf;
        WP1b (item 20, 2026-09-29) adds two -- ub_subbasin_ratio,
        ub_subbasin_flow_share (see IRRIGATION_CONTEXT_UNCOVERED_KEYS's
        comment for why each carries none of the F1 risk the contract
        guards against). supply_group and ub_subbasin_member_count landed
        there too but moved to COVERED in the same-day re-review (LOW 9):
        special-cased in guard_agent_context_sources like "precipitation",
        checked only for an agent that claims a sub-basin at all.

        WP1c (item 22, 2026-09-29) adds four more uncovered keys --
        lb_senior_entitlement_af, lb_junior_entitlement_af,
        lb_junior_request_af, lb_junior_tier_cut_fraction (same
        IRRIGATION_CONTEXT_UNCOVERED_KEYS comment covers why each is safe:
        a checksum-verified table read or a derived value, never a bare
        source-dict read, and None/0 only in legitimate "not applicable"
        cases) -- moving this pin's uncovered count from 8 to 12; covered
        stays 22, since none of the four new keys is added to the coupling
        contract itself. Item 49 adds two optional derived context keys;
        enable it here to check the complete context against the metadata."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        from types import SimpleNamespace
        env.configure_beneficial_use_limit([
            SimpleNamespace(agent_id=aid, water_right=agent["water_right"],
                            peak_obs_af=0.8 * agent["water_right"])
            for aid, agent in env._agents.items()
        ], enabled=True, require_peak=True)
        env.advance_year()
        meta = env.get_coupling_retrofit_metadata()
        assert meta["coupling_contract_uncovered_keys"] == list(IRRIGATION_CONTEXT_UNCOVERED_KEYS)
        ctx_keys = set(env.get_agent_context(next(iter(env.agent_ids))))
        covered = set(meta["coupling_contract_fields"])
        uncovered = set(meta["coupling_contract_uncovered_keys"])
        # The two sets together account for EVERY key the context returns.
        assert covered | uncovered == ctx_keys
        assert not (covered & uncovered)
        # WP4 (spec 4.3) adds shortage_tier_threshold_ft, uncovered for the
        # reason IRRIGATION_CONTEXT_UNCOVERED_KEYS's comment gives: 12 -> 13.
        # Item 46 adds four derived entitlement-ceiling/config fields.
        # Item 47 adds a prompt toggle and three pure settlement outputs.
        # Item 49 adds the derived beneficial-use amount and at-limit flag.
        assert len(covered) == 22 and len(uncovered) == 23

    def test_guard_calls_separate_intent_from_evidence(self):
        """Review P2: flag ON with zero guard calls is a run the guard never
        touched, and must not read like a fully-guarded one."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        assert env.get_coupling_retrofit_metadata()["coupling_guard_calls"] == 0
        env.advance_year()
        n_agents = len(list(env.agent_ids))
        for aid in env.agent_ids:
            env.get_agent_context(aid)
        assert env.get_coupling_retrofit_metadata()["coupling_guard_calls"] == n_agents

    def test_guard_calls_stay_zero_with_flag_off(self):
        env = _minimal_synthetic_env(coupling_contract_active=False)
        env.advance_year()
        for aid in env.agent_ids:
            env.get_agent_context(aid)
        meta = env.get_coupling_retrofit_metadata()
        assert meta["coupling_contract_active"] is False
        assert meta["coupling_guard_calls"] == 0

    def test_runner_records_hook_failure_instead_of_swallowing_it(self):
        """Review P2: a hook that RAISES used to leave the manifest identical
        to an engine with no hook at all (logger.debug and nothing else)."""
        from broker.core.experiment_runner import ExperimentRunner

        class _ExplodingEngine:
            def get_coupling_retrofit_metadata(self):
                raise RuntimeError("hook is broken")

        runner = ExperimentRunner.__new__(ExperimentRunner)
        runner.sim_engine = _ExplodingEngine()
        metadata = {}
        retrofit_meta = None
        retrofit_error = None
        try:
            fn = getattr(runner.sim_engine, "get_coupling_retrofit_metadata", None)
            if callable(fn):
                candidate = fn()
                if isinstance(candidate, dict):
                    retrofit_meta = candidate
        except Exception as exc:
            retrofit_error = f"{type(exc).__name__}: {exc}"
        if retrofit_error is not None:
            metadata["coupling_retrofit_metadata_error"] = retrofit_error
        assert retrofit_meta is None
        assert metadata["coupling_retrofit_metadata_error"] == "RuntimeError: hook is broken"

    def test_runner_source_wires_the_error_key(self):
        """The block above mirrors the runner's logic; this pins that the
        runner really carries the key and the warning (a mirror test alone
        could pass against source that never changed)."""
        src = (ROOT / "broker/core/experiment_runner.py").read_text(encoding="utf-8")
        assert 'metadata["coupling_retrofit_metadata_error"] = retrofit_error' in src
        assert "logger.debug(f\"[Integrity] coupling retrofit metadata skipped" not in src

    def test_experiment_runner_picks_up_retrofit_metadata_not_provenance(self):
        """Duck-typed hook parity check: an engine exposing
        get_coupling_retrofit_metadata() but NOT get_provenance() must land
        under coupling_retrofit_metadata / merge into run_integrity's extra
        WITHOUT ever setting coupling_adapter=True (that flag means 'this
        engine IS an EnvironmentCouplingAdapter', which a raw
        IrrigationEnvironment never is)."""
        from broker.core.experiment_runner import ExperimentRunner

        class _FakeSimEngine:
            def get_coupling_retrofit_metadata(self):
                return {"coupling_contract_active": True, "coupling_contract_fields": ["x"]}

        runner = ExperimentRunner.__new__(ExperimentRunner)
        runner.sim_engine = _FakeSimEngine()
        # Exercise just the duck-typed detection block's logic directly
        # (constructing a full runner is out of scope for this unit test).
        prov_fn = getattr(runner.sim_engine, "get_provenance", None)
        assert prov_fn is None  # confirms this engine is NOT adapter-shaped
        retrofit_fn = getattr(runner.sim_engine, "get_coupling_retrofit_metadata", None)
        assert callable(retrofit_fn)
        assert retrofit_fn() == {
            "coupling_contract_active": True,
            "coupling_contract_fields": ["x"],
        }


class TestAgentConfigGetter:
    def test_default_false(self):
        from broker.utils.agent_config import AgentTypeConfig

        cfg = AgentTypeConfig()
        cfg._config = {"global_config": {}}
        assert cfg.get_coupling_context_contract() is False

    def test_true_when_set(self):
        from broker.utils.agent_config import AgentTypeConfig

        cfg = AgentTypeConfig()
        cfg._config = {"global_config": {"coupling": {"context_contract": True}}}
        assert cfg.get_coupling_context_contract() is True

    def test_non_dict_block_reads_false(self):
        from broker.utils.agent_config import AgentTypeConfig

        cfg = AgentTypeConfig()
        cfg._config = {"global_config": {"coupling": "not-a-dict"}}
        assert cfg.get_coupling_context_contract() is False

    def test_water_named_key_and_getter_are_gone(self):
        """Review W2: the flag guards a generic per-agent CONTEXT handoff, so
        neither the key nor the getter may carry a domain's name (broker/ is
        domain-vocab-free by invariant)."""
        from broker.utils.agent_config import AgentTypeConfig

        assert not hasattr(AgentTypeConfig, "get_coupling_irrigation_contract")
        cfg = AgentTypeConfig()
        # The OLD key name must no longer switch anything on.
        cfg._config = {"global_config": {"coupling": {"irrigation_contract": True}}}
        assert cfg.get_coupling_context_contract() is False


class TestValidatePromptKnownKeys:
    def test_context_contract_key_is_known(self):
        from broker.tools.validate_prompt import check_global_config_keys

        cfg = {"global_config": {"coupling": {"context_contract": True}}}
        issues = check_global_config_keys(cfg)
        assert not any("coupling" in i.location and "context_contract" in i.message for i in issues)

    def test_typo_still_warns(self):
        from broker.tools.validate_prompt import check_global_config_keys

        cfg = {"global_config": {"coupling": {"contex_contract": True}}}
        issues = check_global_config_keys(cfg)
        assert any(
            i.severity == "WARN" and "coupling" in i.location and "contex_contract" in i.message
            for i in issues
        )

    def test_old_water_named_key_now_warns(self):
        """The rename is only real if the retired key stops being allow-listed."""
        from broker.tools.validate_prompt import check_global_config_keys

        cfg = {"global_config": {"coupling": {"irrigation_contract": True}}}
        issues = check_global_config_keys(cfg)
        assert any(
            i.severity == "WARN" and "coupling" in i.location and "irrigation_contract" in i.message
            for i in issues
        )


# ---------------------------------------------------------------------------
# F2: SubprocessModelConnector (archetype C)
# ---------------------------------------------------------------------------
def _script(body: str) -> list:
    """A tiny inline Python script argv, run via ``python -c``."""
    return [sys.executable, "-c", textwrap.dedent(body)]


def _reading_contract() -> CouplingContract:
    return CouplingContract(
        observations=(VarSpec("reading", float, "unit_x", lo=0.0, hi=100.0),),
    )


class TestSubprocessModelConnector:
    def test_happy_path_emits_event(self):
        script = _script("""
            import json, sys
            req = json.loads(sys.stdin.read())
            sys.stdout.write(json.dumps({"reading": 10.0 + req["period"]}))
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        events = conn.draw_events(period=1)
        assert len(events) == 1
        assert events[0].payload["reading"] == 11.0
        assert conn.intensity_at("A1", events[0]) == 11.0
        prov = conn.get_provenance()
        assert prov["last_call_audit"]["exit_code"] == 0

    def test_below_threshold_emits_no_event(self):
        script = _script("""
            import json, sys
            json.loads(sys.stdin.read())
            sys.stdout.write(json.dumps({"reading": 0.0}))
        """)
        conn = SubprocessModelConnector(
            script, contract=_reading_contract(), value_var="reading", event_threshold=0.0,
        )
        assert conn.draw_events(period=1) == []

    def test_missing_reply_field_raises_named(self):
        script = _script("""
            import sys
            sys.stdout.write("{}")
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="reading"):
            conn.draw_events(period=1)

    def test_out_of_range_reply_raises(self):
        script = _script("""
            import json, sys
            sys.stdout.write(json.dumps({"reading": 999.0}))
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="reading"):
            conn.draw_events(period=1)

    def test_nonzero_exit_refused_with_stderr_tail(self):
        script = _script("""
            import sys
            sys.stderr.write("boom: sensor offline")
            sys.exit(3)
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="boom: sensor offline"):
            conn.draw_events(period=1)

    def test_timeout_refused(self):
        script = _script("""
            import sys, time
            sys.stdin.read()
            time.sleep(5)
        """)
        conn = SubprocessModelConnector(
            script, contract=_reading_contract(), value_var="reading", timeout_sec=0.5,
        )
        with pytest.raises(CouplingViolation, match="timed out"):
            conn.draw_events(period=1)

    def test_non_json_reply_refused(self):
        script = _script("""
            import sys
            sys.stdout.write("not json{")
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="not valid JSON"):
            conn.draw_events(period=1)

    def test_value_var_must_be_declared_observation(self):
        with pytest.raises(ValueError, match="not_declared"):
            SubprocessModelConnector(
                [sys.executable, "-c", "pass"],
                contract=_reading_contract(),
                value_var="not_declared",
            )


# ---------------------------------------------------------------------------
# F3: docs/templates on_missing allowlist regression guard
# ---------------------------------------------------------------------------
_SKILL = ROOT / ".claude/skills/wagf-coupling-designer"


def _scanned_doc_paths():
    """Every coupling-designer artefact an author might copy an
    ``on_missing`` example out of.

    Review C2: the original scan covered three markdown files and MISSED
    ``templates/adapter_A_file_replay.py.tmpl``, which is where the stale
    "Choose fail_loud or last_good in the coupling contract" line actually
    lived — the one file in the set that is code rather than prose, and so
    the one an author is most likely to paste from. Globbed, not listed, so a
    template added later is scanned without anyone remembering to add it.
    """
    paths = [
        _SKILL / "references/contract_template.md",
        _SKILL / "references/failure_mode_playbook.md",
    ]
    paths += sorted(_SKILL.glob("templates/*.tmpl"))
    paths += sorted(p for p in (_SKILL / "references/coupling_patterns").glob("*") if p.is_file())
    return paths


def _code_regions(path: Path, text: str):
    """The parts of ``path`` an author would read as usable code.

    For markdown (including ``*.md.tmpl``) that means fenced blocks only:
    these docs now legitimately NAME ``last_good`` / ``quarantine`` in prose
    to say VarSpec rejects them, and that honest text must not fail the
    guard. For a code template (``*.py.tmpl``) the whole file is code.
    """
    name = path.name
    if name.endswith(".md") or name.endswith(".md.tmpl"):
        return [m.group(1) for m in re.finditer(r"```(?:\w+)?\n(.*?)```", text, re.DOTALL)]
    return [text]


class TestOnMissingDocsAllowlist:
    def test_scan_covers_templates_and_pattern_references(self):
        """The scanner's reach is itself pinned: a doc set that silently
        shrank would make every assertion below vacuously pass."""
        names = {p.name for p in _scanned_doc_paths()}
        assert "adapter_A_file_replay.py.tmpl" in names
        assert "coupling_contract.md.tmpl" in names
        assert "failure_mode_playbook.md" in names
        assert "contract_template.md" in names
        # references/coupling_patterns/ is in scope and non-empty.
        assert any(p.parent.name == "coupling_patterns" for p in _scanned_doc_paths())
        for path in _scanned_doc_paths():
            assert path.exists(), path

    def test_file_replay_template_no_longer_points_at_the_contract(self):
        """Review C2: the TODO told an author to choose ``last_good`` IN THE
        COUPLING CONTRACT, which ``VarSpec.__post_init__`` rejects at
        construction. The policy is the ADAPTER's; the comment must say so."""
        text = (_SKILL / "templates/adapter_A_file_replay.py.tmpl").read_text(encoding="utf-8")
        assert "Choose fail_loud or last_good in the coupling contract" not in text
        assert "NOT in the coupling contract" in text

    def test_contract_py_accepts_only_fail_loud(self):
        accepted = []
        for candidate in ("fail_loud", "last_good", "quarantine", "quarantine_row"):
            try:
                VarSpec("x", float, "u", on_missing=candidate)
                accepted.append(candidate)
            except ValueError:
                pass
        assert accepted == ["fail_loud"]

    def test_edited_docs_name_no_other_on_missing_value_in_a_code_example(self):
        """Regression guard for F3: scan FENCED CODE BLOCKS (```...```) in
        the templates/playbook this PR edited for a literal
        ``on_missing=<value>`` construction example, and require every
        value found there to be one VarSpec actually accepts. Code fences
        (not inline prose) are the right scan target: these docs now
        legitimately NAME ``last_good`` / ``quarantine`` in prose to
        explain that VarSpec rejects them (e.g. "declaring
        `on_missing="last_good"` raises at construction") -- that is the
        correct, honest text this PR wrote, and must not itself fail this
        guard. A future edit that puts ``on_missing="last_good"`` inside a
        CODE EXAMPLE presented as usable would fail this test.
        """
        assign_pattern = re.compile(r'on_missing\s*=\s*"([A-Za-z_]+)"')
        for doc_path in _scanned_doc_paths():
            assert doc_path.exists(), doc_path
            text = doc_path.read_text(encoding="utf-8")
            for region in _code_regions(doc_path, text):
                for match in assign_pattern.finditer(region):
                    claimed = match.group(1)
                    assert claimed == "fail_loud", (
                        f"{doc_path} shows on_missing={claimed!r} inside a "
                        f"code example, which VarSpec.__post_init__ rejects "
                        f"at construction -- only 'fail_loud' has a runtime "
                        f"executor."
                    )

    def test_no_on_missing_value_besides_fail_loud_is_presented_as_currently_usable(self):
        """Weaker, whole-document companion check: every OTHER value this
        PR's docs mention alongside on_missing (last_good / quarantine) must
        appear only next to a rejection word on the same line -- i.e. never
        presented as something you can currently declare and have honoured.
        """
        rejection_words = ("reject", "raise", "not construct", "REJECT", "no runtime executor", "will not")
        doc_paths = _scanned_doc_paths()
        mention_pattern = re.compile(r'on_missing\s*[:=]\s*"?(last_good|quarantine|quarantine_row)"?')
        for doc_path in doc_paths:
            text = doc_path.read_text(encoding="utf-8")
            for line in text.splitlines():
                if mention_pattern.search(line):
                    assert any(w.lower() in line.lower() for w in rejection_words), (
                        f"{doc_path}: line names a non-fail_loud on_missing value "
                        f"without rejection language nearby: {line!r}"
                    )


# ===========================================================================
# PR-9 REVIEW ROUND
# ===========================================================================

# ---------------------------------------------------------------------------
# P0: VarSpec.range_violation -- the primitive every guard calls
# ---------------------------------------------------------------------------
_NUM = VarSpec("level", float, "ft", lo=0.0, hi=100.0)
_NUM_UNBOUNDED = VarSpec("delta", float, "ft")
_INT = VarSpec("flag_count", int, "count", lo=0, hi=10)
_BOOL = VarSpec("is_capped", bool, "")
_STR = VarSpec("cluster", str, "")


class TestRangeViolationP0:
    """Each case pins the NEW rejection and FALSIFIES it against the pre-fix
    function: ``_pre_fix_range_violation`` returning None where the current
    one returns a message is the proof that the check is new, not restated.
    """

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_rejected_and_was_not_before(self, bad):
        # BEFORE: None. `nan < 0.0` and `nan > 100.0` are both False, so a NaN
        # satisfied every bounded range; +/-inf failed only if bounds existed.
        before = _pre_fix_range_violation(_NUM, bad)
        after = _NUM.range_violation(bad)
        if math.isnan(bad):
            assert before is None
        assert after is not None and "not finite" in after and "level" in after

    def test_non_finite_rejected_even_with_no_bounds(self):
        """An UNBOUNDED numeric VarSpec had no check at all to fail."""
        assert _pre_fix_range_violation(_NUM_UNBOUNDED, float("nan")) is None
        assert _pre_fix_range_violation(_NUM_UNBOUNDED, float("inf")) is None
        assert "not finite" in (_NUM_UNBOUNDED.range_violation(float("nan")) or "")
        assert "not finite" in (_NUM_UNBOUNDED.range_violation(float("inf")) or "")

    @pytest.mark.parametrize("spec", [_NUM, _INT])
    def test_bool_in_a_numeric_slot_rejected_and_was_not_before(self, spec):
        # BEFORE: None. bool subclasses int, so float(True) == 1.0 sat inside
        # both ranges and a flag wired into a numeric variable read as a
        # perfectly ordinary measurement of 1.
        assert _pre_fix_range_violation(spec, True) is None
        assert _pre_fix_range_violation(spec, False) is None
        assert "is a bool" in (spec.range_violation(True) or "")
        assert "is a bool" in (spec.range_violation(False) or "")

    def test_numeric_string_in_a_numeric_slot_rejected_and_was_not_before(self):
        # BEFORE: None. float("55") == 55.0, inside [0, 100].
        assert _pre_fix_range_violation(_NUM, "55") is None
        after = _NUM.range_violation("55")
        assert after is not None and "is a str" in after

    def test_non_numeric_string_still_rejected_only_the_wording_moved(self):
        """A string that float() cannot parse was ALREADY rejected; the fix
        must not weaken that, only rename the reason."""
        assert _pre_fix_range_violation(_NUM, "abc") is not None
        assert _NUM.range_violation("abc") is not None

    def test_bool_dtype_requires_a_real_bool_and_had_no_check_before(self):
        # BEFORE: a bool VarSpec fell straight through to `return None`, so
        # declaring dtype=bool bought PRESENCE checking and nothing else.
        for bad in (1, 0, "true", "", 1.0, [], None if False else "yes"):
            assert _pre_fix_range_violation(_BOOL, bad) is None
            assert "is not a bool" in (_BOOL.range_violation(bad) or "")
        assert _BOOL.range_violation(True) is None
        assert _BOOL.range_violation(False) is None

    def test_str_dtype_requires_a_non_empty_str_and_had_no_check_before(self):
        for bad in (1, 1.5, True, [], {}):
            assert _pre_fix_range_violation(_STR, bad) is None
            assert "is not a str" in (_STR.range_violation(bad) or "")
        # An empty string is the string-shaped silent default.
        assert _pre_fix_range_violation(_STR, "") is None
        assert "empty str" in (_STR.range_violation("") or "")
        assert _STR.range_violation("aggressive") is None

    def test_none_is_still_the_adapters_job_not_a_range_violation(self):
        """Unchanged on purpose: on_missing owns absence, this owns value."""
        for spec in (_NUM, _INT, _BOOL, _STR):
            assert spec.range_violation(None) is None

    def test_ordinary_values_still_pass(self):
        """The whole point: nothing a PASSING run produces starts failing."""
        assert _NUM.range_violation(50.0) is None
        assert _NUM.range_violation(0.0) is None
        assert _NUM.range_violation(100) is None  # int into a float slot is fine
        assert _INT.range_violation(3) is None
        assert _BOOL.range_violation(True) is None
        assert _STR.range_violation("lower_basin") is None

    def test_nan_reaches_the_irrigation_guard_and_is_named(self):
        """The P0 primitive is only interesting through a real guard: inject
        a NaN into the env's own state and check the guard names the field."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        aid = next(a for a in env.agent_ids if env._agents[a]["basin"] == "lower_basin")
        env._basins["lower_basin"]["lake_mead_level"] = float("nan")
        with pytest.raises(CouplingViolation, match="lake_mead_level"):
            env.get_agent_context(aid)

    def test_nan_reached_the_prompt_before_the_fix(self):
        """Falsification for the case above: with the PRE-FIX primitive the
        same NaN produced no violation at all."""
        contract = build_irrigation_agent_context_contract()
        spec = contract.observation_specs()["lake_mead_level"]
        assert _pre_fix_range_violation(spec, float("nan")) is None
        assert spec.range_violation(float("nan")) is not None


# ---------------------------------------------------------------------------
# P1: SubprocessModelConnector hardening
# ---------------------------------------------------------------------------
class TestSubprocessConnectorReviewHardening:
    def test_nan_token_in_reply_refused_at_parse_time(self):
        """Python's json module emits and accepts bare NaN; strict JSON has no
        such literal. Refused before any field is looked at, so it is caught
        even in a field the contract does not declare."""
        script = _script("""
            import sys
            sys.stdout.write('{"reading": NaN}')
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="not valid JSON"):
            conn.draw_events(period=1)

    @pytest.mark.parametrize("token", ["Infinity", "-Infinity"])
    def test_infinity_tokens_refused_at_parse_time(self, token):
        script = _script(f"""
            import sys
            sys.stdout.write('{{"reading": {token}}}')
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="not valid JSON"):
            conn.draw_events(period=1)

    def test_nan_in_an_undeclared_field_also_refused(self):
        """The per-VarSpec loop never inspects an undeclared key, so the
        parse-time hook is the only layer that can see this one."""
        script = _script("""
            import sys
            sys.stdout.write('{"reading": 10.0, "diagnostic": NaN}')
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with pytest.raises(CouplingViolation, match="not valid JSON"):
            conn.draw_events(period=1)

    def test_timeout_records_the_audit_before_raising(self):
        """Review P1: _last_audit used to keep the LAST SUCCESSFUL call, so
        get_provenance() reported a success while the model was hanging."""
        ok_script = _script("""
            import json, sys
            sys.stdin.read()
            sys.stdout.write(json.dumps({"reading": 10.0}))
        """)
        conn = SubprocessModelConnector(
            ok_script, contract=_reading_contract(), value_var="reading", timeout_sec=10.0,
        )
        conn.draw_events(period=1)
        assert conn.get_provenance()["last_call_audit"]["exit_code"] == 0

        conn._command = tuple(_script("""
            import sys, time
            sys.stdin.read()
            time.sleep(5)
        """))
        conn._timeout_sec = 0.5
        with pytest.raises(CouplingViolation, match="timed out"):
            conn.draw_events(period=2)
        audit = conn.get_provenance()["last_call_audit"]
        assert audit["period"] == 2
        assert audit["exit_code"] is None        # killed, never exited
        assert audit["timed_out"] is True
        assert audit["wall_time_sec"] >= 0.0
        assert "stderr_tail" in audit

    def test_successful_call_reports_timed_out_false(self):
        script = _script("""
            import json, sys
            sys.stdin.read()
            sys.stdout.write(json.dumps({"reading": 10.0}))
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        conn.draw_events(period=1)
        assert conn.get_provenance()["last_call_audit"]["timed_out"] is False

    def test_undeclared_reply_keys_warn(self, caplog):
        script = _script("""
            import json, sys
            sys.stdin.read()
            sys.stdout.write(json.dumps({"reading": 10.0, "readng": 99.0}))
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        with caplog.at_level("WARNING", logger="broker.coupling.subprocess_source"):
            conn.draw_events(period=1)
        assert any("readng" in r.getMessage() for r in caplog.records)

    def test_no_warning_when_every_key_is_declared(self):
        """A warning on every ordinary call would be noise nobody reads."""
        import logging

        script = _script("""
            import json, sys
            sys.stdin.read()
            sys.stdout.write(json.dumps({"reading": 10.0}))
        """)
        conn = SubprocessModelConnector(script, contract=_reading_contract(), value_var="reading")
        records = []

        class _Collect(logging.Handler):
            def emit(self, record):
                records.append(record)

        logger = logging.getLogger("broker.coupling.subprocess_source")
        handler = _Collect()
        logger.addHandler(handler)
        try:
            conn.draw_events(period=1)
        finally:
            logger.removeHandler(handler)
        assert not [r for r in records if r.levelno >= logging.WARNING]

    def test_intensity_at_raises_on_a_foreign_event_instead_of_returning_zero(self):
        """Review P1: the .get(value_var, .get("intensity", 0.0)) chain gave a
        silent 0.0 intensity for an event the guard never validated."""
        from broker.coupling.interfaces import Event

        conn = SubprocessModelConnector(
            _script("import sys"), contract=_reading_contract(), value_var="reading",
        )
        foreign = Event(event_id="from_elsewhere", period=1, payload={"something_else": 5.0})
        with pytest.raises(KeyError):
            conn.intensity_at("A1", foreign)

    def test_non_numeric_value_var_refused_at_construction(self):
        """Review W4: value_var becomes an event INTENSITY (a float compared
        to event_threshold); a bool or str observation cannot be one."""
        contract = CouplingContract(
            observations=(
                VarSpec("reading", float, "unit_x", lo=0.0, hi=100.0),
                VarSpec("label", str, "", consumer_of_record=False),
                VarSpec("tripped", bool, "", consumer_of_record=False),
            ),
        )
        for bad in ("label", "tripped"):
            with pytest.raises(ValueError, match="must be numeric"):
                SubprocessModelConnector(
                    [sys.executable, "-c", "pass"], contract=contract, value_var=bad,
                )
        # The numeric one still constructs.
        SubprocessModelConnector(
            [sys.executable, "-c", "pass"], contract=contract, value_var="reading",
        )


# ---------------------------------------------------------------------------
# P1-a: the flag must reach every arm, and a mismatch must be flagged
# ---------------------------------------------------------------------------
class TestFlagReachesEveryIrrigationRunner:
    @pytest.mark.parametrize("runner", [
        "run_experiment.py", "run_fql_baseline.py",
    ])
    def test_runner_reads_the_getter_and_passes_it(self, runner):
        """Source-level check on purpose: these two ``main()`` functions each
        run a whole experiment and independently construct
        ``IrrigationEnvironment``, so the cheap and honest way to pin 'the
        flag reaches this arm' is that each one reads the same getter and
        hands the result to the environment directly. Before the original
        review only the governed runner did, which would have made a
        gov-vs-noval pair differ in something other than governance.

        ``run_ungoverned_experiment.py`` is intentionally NOT parametrized
        here (2026-09, irrigation case-alignment follow-up): it no longer
        runs its own pipeline at all -- it is a thin argv-forwarding wrapper
        around ``run_experiment.py``'s ``main()`` (see
        ``test_ungoverned_forwards_to_run_experiment_main`` below). Pinning
        these two literal fragments in ITS source would only be checking
        prose that happens to mention them, not the actual call, once the
        two scripts stopped duplicating the pipeline.
        """
        src = (ROOT / "examples/irrigation_abm" / runner).read_text(encoding="utf-8")
        assert "get_coupling_context_contract()" in src
        assert "coupling_contract_active=coupling_contract_active" in src

    def test_ungoverned_forwards_to_run_experiment_main(self):
        """run_ungoverned_experiment.py must delegate to run_experiment.py's
        main() -- the one remaining place get_coupling_context_contract() /
        coupling_contract_active= is called for the "ungoverned" path --
        rather than reimplementing environment construction itself. Checked
        two ways: (1) the wrapper's own source actually imports and calls
        run_experiment's main, not just mentions it; (2) the delegation
        target (run_experiment.py) still carries the wiring this class
        exists to pin, so a regression there is still caught by the test
        above."""
        wrapper_src = (
            ROOT / "examples/irrigation_abm" / "run_ungoverned_experiment.py"
        ).read_text(encoding="utf-8")
        assert "from examples.irrigation_abm.run_experiment import main" in wrapper_src
        assert "_run_experiment_main()" in wrapper_src

        target_src = (ROOT / "examples/irrigation_abm" / "run_experiment.py").read_text(
            encoding="utf-8"
        )
        assert "get_coupling_context_contract()" in target_src
        assert "coupling_contract_active=coupling_contract_active" in target_src

    @pytest.mark.parametrize("runner", [
        # run_ungoverned_experiment.py's case is vacuously true now
        # (irrigation case-alignment, 2026-09): it no longer constructs
        # IrrigationEnvironment at all, bare-positional or otherwise, since
        # it forwards to run_experiment.py's main(). Kept in the
        # parametrize list anyway -- harmless, and it still guards against
        # someone reintroducing a bare-positional construction directly in
        # this file in the future.
        "run_ungoverned_experiment.py", "run_fql_baseline.py",
    ])
    def test_bare_positional_construction_is_gone_from_the_other_arms(self, runner):
        src = (ROOT / "examples/irrigation_abm" / runner).read_text(encoding="utf-8")
        assert "IrrigationEnvironment(config)\n" not in src


class TestPairwiseCouplingParityFlag:
    """Invariant 6's NW gov-vs-noval pairwise checker must FLAG two compared
    runs whose recorded ``coupling_contract_active`` disagree."""

    @staticmethod
    def _checker():
        import importlib.util

        path = ROOT / "examples/single_agent/analysis/check_run_integrity.py"
        spec = importlib.util.spec_from_file_location("_nw_check_run_integrity", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _run_dir(tmp_path, name, active):
        d = tmp_path / name
        d.mkdir()
        payload = {"integrity_ok": True}
        if active is not None:
            payload["coupling_contract_active"] = active
        (d / "run_integrity.json").write_text(json.dumps(payload), encoding="utf-8")
        return d

    def test_mismatch_is_flagged(self, tmp_path):
        mod = self._checker()
        gov = [self._run_dir(tmp_path, "gov1", True)]
        nov = [self._run_dir(tmp_path, "nov1", False)]
        defect = mod._coupling_parity_defect("irrigation gemma3_4b", gov, nov)
        assert defect is not None
        assert "coupling_contract_active differs" in defect
        assert "irrigation gemma3_4b" in defect

    def test_matching_arms_are_not_flagged(self, tmp_path):
        mod = self._checker()
        for state in (True, False):
            gov = [self._run_dir(tmp_path, f"g_{state}", state)]
            nov = [self._run_dir(tmp_path, f"n_{state}", state)]
            assert mod._coupling_parity_defect("x", gov, nov) is None

    def test_within_arm_disagreement_is_also_flagged(self, tmp_path):
        """Two governed seeds that disagree with each other are just as
        uncomparable as two arms that do."""
        mod = self._checker()
        gov = [self._run_dir(tmp_path, "g1", True), self._run_dir(tmp_path, "g2", False)]
        nov = [self._run_dir(tmp_path, "n1", True)]
        assert mod._coupling_parity_defect("x", gov, nov) is not None

    def test_runs_predating_the_key_are_not_measured_rather_than_assumed_off(self, tmp_path):
        """An absent key means 'not recorded'. Reading it as False would
        invent a mismatch against every pre-PR-9 corpus."""
        mod = self._checker()
        gov = [self._run_dir(tmp_path, "old_g", None)]
        nov = [self._run_dir(tmp_path, "new_n", True)]
        assert mod._coupling_parity_defect("x", gov, nov) is None

    def test_missing_manifest_reads_as_none(self, tmp_path):
        mod = self._checker()
        empty = tmp_path / "no_manifest"
        empty.mkdir()
        assert mod._coupling_state(empty) is None


# ---------------------------------------------------------------------------
# P1-b: the audit CSV's Lake Mead column joins the guarded path
# ---------------------------------------------------------------------------
class TestLoggedMeadLevelUnderTheFlag:
    @staticmethod
    def _hooks(env):
        from examples.irrigation_abm.run_experiment import IrrigationLifecycleHooks

        hooks = IrrigationLifecycleHooks.__new__(IrrigationLifecycleHooks)
        hooks.env = env
        return hooks

    def test_flag_off_keeps_the_legacy_zero_default(self):
        env = _minimal_synthetic_env(coupling_contract_active=False)
        env.advance_year()
        hooks = self._hooks(env)
        assert hooks._log_lake_mead_level() == env.get_local("lower_basin", "lake_mead_level")
        del env._basins["lower_basin"]["lake_mead_level"]
        assert hooks._log_lake_mead_level() == 0  # byte-identical legacy behaviour

    def test_flag_on_returns_the_real_value_when_present(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        hooks = self._hooks(env)
        assert hooks._log_lake_mead_level() == env.get_local("lower_basin", "lake_mead_level")

    def test_flag_on_refuses_to_log_a_manufactured_zero(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        del env._basins["lower_basin"]["lake_mead_level"]
        with pytest.raises(KeyError, match="lake_mead_level"):
            self._hooks(env)._log_lake_mead_level()

    def test_shortage_tier_refuses_the_1100ft_default_under_the_flag(self):
        """Review P2: the default was above tier-1, so a missing reservoir
        level reported 'no shortage, no curtailment'."""
        env_off = _minimal_synthetic_env(coupling_contract_active=False)
        env_off.advance_year()
        del env_off._basins["lower_basin"]["lake_mead_level"]
        assert env_off._compute_shortage_tier() == 0  # the legacy silent answer

        env_on = _minimal_synthetic_env(coupling_contract_active=True)
        env_on.advance_year()
        del env_on._basins["lower_basin"]["lake_mead_level"]
        with pytest.raises(KeyError, match="lake_mead_level"):
            env_on._compute_shortage_tier()


# ---------------------------------------------------------------------------
# P1-d: an unrecognised basin must not silently skip both scoped fields
# ---------------------------------------------------------------------------
class TestUnknownBasinIsAViolation:
    def test_third_basin_is_named_rather_than_skipped(self):
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        aid = next(iter(env.agent_ids))
        env._agents[aid]["basin"] = "middle_basin"       # a basin nothing scopes
        env._basins["middle_basin"] = {"preceding_factor": 0}
        with pytest.raises(CouplingViolation, match="middle_basin"):
            env.get_agent_context(aid)

    def test_the_message_says_which_fields_went_unchecked(self):
        contract = build_irrigation_agent_context_contract()
        agent = {k: 1.0 for k in ("diversion", "request", "water_right")}
        agent.update({
            "curtailment_ratio": 0.0, "at_allocation_cap": False,
            "has_efficient_system": False, "below_minimum_utilisation": False,
            "cluster": "aggressive", "basin": "middle_basin",
        })
        with pytest.raises(CouplingViolation) as exc:
            guard_agent_context_sources(
                contract,
                agent=agent, basin_key="middle_basin",
                basin={"preceding_factor": 0},
                global_state={"drought_index": 0.5, "total_available_water": 1.0,
                              "total_basin_demand": 1.0},
                # Re-review 2026-09-29 (LOW E): agent has no precip_group,
                # so this falls through to the generic basin-level check
                # below (unaffected by this empty dict).
                precip_by_group={},
            )
        message = str(exc.value)
        assert "basin='middle_basin'" in message
        assert "lake_mead_level" in message and "precipitation" in message

    def test_the_two_known_basins_still_pass(self):
        """The new refusal must not fire on the design it was built around."""
        env = _minimal_synthetic_env(coupling_contract_active=True)
        env.advance_year()
        basins = {env._agents[a]["basin"] for a in env.agent_ids}
        assert basins == {"upper_basin", "lower_basin"}
        for aid in env.agent_ids:
            env.get_agent_context(aid)  # must not raise


# ---------------------------------------------------------------------------
# P1-e: a blank CRSS cell must fail the LOAD, not become 17 MAF
# ---------------------------------------------------------------------------
_CRSS_COLS = "WY,UT1,UT2,UT3,NM,CO1,CO2,CO3,AZ"


_UB_COLS = ["WY", "UT1", "UT2", "UT3", "CO1", "CO2", "CO3"]


def _crss_csv(tmp_path, blank_at=None, blank_row=None, name="PrismWinterPrecip.csv"):
    """Two-year PRISM-shaped file.

    ``blank_at`` = a single ``(year, column)`` cell to leave blank;
    ``blank_row`` = a year whose Upper Basin columns are ALL blank.
    """
    lines = ["Year," + _CRSS_COLS]
    for year in (2019, 2020):
        cells = []
        for col in _CRSS_COLS.split(","):
            blank = blank_at == (year, col) or (blank_row == year and col in _UB_COLS)
            cells.append("" if blank else "5.0")
        lines.append(f"{year}," + ",".join(cells))
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


class TestCrssPrecipitationNaNRefusedAtLoad:
    def test_clean_file_loads(self, tmp_path):
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.load_crss_precipitation(str(_crss_csv(tmp_path)))
        assert env._crss_precip is not None
        assert float(env._crss_precip.loc[2019, "WY"]) == pytest.approx(5.0 * 25.4)

    def test_one_blank_cell_fails_the_load_naming_year_and_column(self, tmp_path):
        path = _crss_csv(tmp_path, blank_at=(2020, "CO2"))
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        with pytest.raises(ValueError) as exc:
            env.load_crss_precipitation(str(path))
        message = str(exc.value)
        assert "2020/CO2" in message
        assert env._crss_precip is None  # nothing half-loaded

    def test_a_whole_blank_row_fails_the_load_too(self, tmp_path):
        path = _crss_csv(tmp_path, blank_row=2019)
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        with pytest.raises(ValueError) as exc:
            env.load_crss_precipitation(str(path))
        message = str(exc.value)
        for col in _UB_COLS:
            assert f"2019/{col}" in message

    def test_a_few_blanks_silently_shift_the_mean_if_allowed_through(self, tmp_path):
        """Falsification, case 1: pandas' mean SKIPS NaN, so one blank
        station does not error and does not go NaN -- it quietly reports the
        average of the stations that did report."""
        import pandas as pd

        clean = pd.read_csv(_crss_csv(tmp_path, name="clean.csv"), index_col=0) * 25.4
        holed = pd.read_csv(_crss_csv(tmp_path, blank_at=(2019, "WY"), name="holed.csv"),
                            index_col=0) * 25.4
        assert bool(holed.isna().to_numpy().any())
        clean_mean = float(clean.loc[2019, _UB_COLS].mean())
        holed_mean = float(holed.loc[2019, _UB_COLS].mean())
        assert not math.isnan(holed_mean)      # no NaN, no error
        assert holed_mean == pytest.approx(clean_mean)  # and here, not even a visible change

    def test_a_blank_row_becomes_max_drought_if_allowed_through(self, tmp_path):
        """Falsification, case 2 -- the shape the reviewer named: the mean of
        an all-blank row IS NaN, and because every comparison with NaN is
        False the drought clamp returns its extreme end rather than raising.

        Re-review 2026-09-29 (LOW 7): this test used to ALSO re-derive a
        natural-flow clamp via ``cfg.natural_flow_base_maf * (laundered /
        cfg.precip_baseline_mm)`` -- a RETIRED v3 formula that
        ``_natural_flow_for_year`` no longer uses at all (natural flow now
        comes from the committed USBR hydrology table, independent of
        precipitation); that half tested only its own re-derived arithmetic,
        never any current code path, so it is dropped along with the
        retired ``WaterSystemConfig.natural_flow_base_maf`` field itself.
        The drought clamp below still exercises live code
        (``_compute_drought_index`` is still called every year, even though
        its output is disclosed as unread by any prompt, rule or metric)."""
        import pandas as pd

        raw = pd.read_csv(_crss_csv(tmp_path, blank_row=2019), index_col=0) * 25.4
        laundered = float(raw.loc[2019, _UB_COLS].mean())
        assert math.isnan(laundered)

        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        # The drought clamp: max(0.0, min(1.0, 1.0 - NaN/baseline)) -> 1.0, MAX
        # drought -- indistinguishable from a year with ZERO precipitation.
        drought_from_nan = env._compute_drought_index(laundered, 1000.0)
        drought_from_zero_precip = env._compute_drought_index(0.0, 1000.0)
        assert not math.isnan(drought_from_nan)
        assert drought_from_nan == pytest.approx(drought_from_zero_precip)

    def test_mock_path_never_loads_crss_so_byte_identity_is_untouched(self):
        """The check is load-time only: a --model mock run leaves
        _crss_precip None and takes the synthetic branch."""
        env = IrrigationEnvironment(WaterSystemConfig(seed=42))
        env.initialize_synthetic(n_agents=2, basin_split=(1, 1))
        assert env._crss_precip is None
        env.advance_year()
        # v3 (spec 1.6, 2026-09-28): each entry is now a per-sub-basin-group
        # dict, not a bare float (the synthetic fallback replicates one
        # drying-trend value across all 9 groups -- see
        # _generate_precipitation).
        assert env._precip_history
        last = env._precip_history[-1]
        assert last and all(math.isfinite(v) for v in last.values())


class TestNumpyBoolScalars:
    """numpy.bool_ is not a bool subclass; the guard must treat it as one in
    BOTH directions (accepted by a bool spec, rejected in a numeric slot)."""

    def test_numpy_bool_accepted_by_a_bool_spec(self):
        np = pytest.importorskip("numpy")
        spec = VarSpec("at_cap", bool, "")
        assert spec.range_violation(np.bool_(True)) is None
        assert spec.range_violation(np.False_) is None

    def test_numpy_bool_rejected_in_a_numeric_slot(self):
        np = pytest.importorskip("numpy")
        spec = VarSpec("level", float, "ft", lo=0.0, hi=100.0)
        msg = spec.range_violation(np.bool_(True))
        assert msg is not None and "is a bool, not a float" in msg

    def test_rejection_message_names_the_module_not_a_contradiction(self):
        np = pytest.importorskip("numpy")
        spec = VarSpec("at_cap", bool, "")
        msg = spec.range_violation(np.int64(1))
        assert msg is not None and "numpy.int64" in msg
