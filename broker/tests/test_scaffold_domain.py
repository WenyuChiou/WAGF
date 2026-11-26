"""Tests for broker.tools.scaffold_domain CLI (Phase 6C-v4 cycle 4 Part B).

The acid test: a freshly scaffolded skeleton must pass validate_prompt
without ANY edits — proving the templates are correct and the new-domain
onboarding cost is genuinely one command.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

from broker.tools.scaffold_domain import (
    gen_agent_types_yaml,
    gen_domain_pack,
    gen_skill_registry,
    main,
    scaffold,
)
from broker.tools.validate_prompt import main as validate_main
from broker.utils.agent_config import AgentTypeConfig, PMT_TEXT_MARKERS


REPO_ROOT = Path(__file__).resolve().parents[2]
LEGACY_RUNNER = Path(__file__).with_name("fixtures") / "legacy_scaffold" / "run_experiment.py"


def _yaml_keys(node):
    if isinstance(node, dict):
        yield from node
        for value in node.values():
            yield from _yaml_keys(value)
    elif isinstance(node, list):
        for item in node:
            yield from _yaml_keys(item)


def _assert_mock_smoke(root: Path, entry_point: list[str]) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(REPO_ROOT), env.get("PYTHONPATH")) if part
    )
    result = subprocess.run(
        [sys.executable, *entry_point, "--model", "mock", "--years", "1", "--agents", "1"],
        capture_output=True,
        text=True,
        cwd=root,
        env=env,
        timeout=240,
    )
    assert result.returncode == 0, (
        f"{entry_point} failed mock smoke:\n"
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    assert (root / "results" / "smoke" / "governance_summary.json").exists()


# ---------------------------------------------------------------------------
# Per-generator tests
# ---------------------------------------------------------------------------

class TestGenAgentTypesYaml:
    def test_produces_valid_yaml(self):
        text = gen_agent_types_yaml(
            "energy_consumer",
            ["increase_use", "maintain_use", "decrease_use"],
            "pmt",
        )
        data = yaml.safe_load(text)
        assert "global_config" in data
        assert "shared" in data
        assert "agent" in data
        assert data["global_config"]["audit"] == {
            "initial_proposal_columns": True,
            "attempt_columns": True,
            "corrected_status_columns": True,
        }

    def test_includes_all_required_blocks(self):
        text = gen_agent_types_yaml(
            "energy_consumer",
            ["increase_use", "maintain_use", "decrease_use"],
            "pmt",
        )
        data = yaml.safe_load(text)
        agent = data["agent"]
        # The 6-BLOCKER inventory says these must all exist:
        assert "actions" in agent
        assert isinstance(agent["actions"], list)
        assert len(agent["actions"]) == 3
        assert "parsing" in agent
        assert "constructs" in agent["parsing"]
        assert "log_fields" in agent
        assert "prompt_template_file" in agent
        # response_format must declare construct for the appraisal field
        fields = data["shared"]["response_format"]["fields"]
        construct_fields = [f for f in fields if f.get("construct")]
        assert construct_fields, "must declare at least one appraisal field"
        # parsing.constructs must cover those constructs
        for f in construct_fields:
            assert f["construct"] in agent["parsing"]["constructs"]

    def test_custom_framework_uses_domain_framework_name(self):
        text = gen_agent_types_yaml("traffic", ["drive", "transit"], "custom")
        data = yaml.safe_load(text)
        assert data["agent"]["psychological_framework"] == "traffic_framework"

    def test_pmt_framework_uses_pmt(self):
        text = gen_agent_types_yaml("energy", ["a", "b"], "pmt")
        data = yaml.safe_load(text)
        assert data["agent"]["psychological_framework"] == "pmt"

    @pytest.mark.parametrize("framework,physical_only", [("pmt", False), ("custom", False), ("pmt", True)])
    def test_memory_engine_and_reflection_switch_are_scaffolded_with_reflection_off(self, framework, physical_only):
        # python -m broker.run reads both blocks; reflection stays off until
        # the author sets enabled: true.
        data = yaml.safe_load(gen_agent_types_yaml(
            "energy", ["a", "b"], framework, physical_only=physical_only))
        assert data["global_config"]["memory"]["engine_type"] == "window"
        assert data["global_config"]["reflection"] == {"enabled": False, "interval": 1, "importance_boost": 0.9}
        assert "llm" in data["global_config"]


class TestGenSkillRegistry:
    def test_valid_yaml(self):
        text = gen_skill_registry("energy", ["a", "b"])
        data = yaml.safe_load(text)
        assert data["domain"] == "energy"
        assert data["default_skill"] == "a"
        assert len(data["skills"]) == 2

    def test_uses_skill_id_field(self):
        """Phase 6E Finding #2 regression: skill_registry.yaml MUST use
        `skill_id:` to match broker/components/governance/registry.py:70's
        `skill_data['skill_id']` lookup. Earlier versions used `id:` which
        broker rejected with KeyError at runtime."""
        text = gen_skill_registry("energy", ["a", "b", "c"])
        data = yaml.safe_load(text)
        for entry in data["skills"]:
            assert "skill_id" in entry, (
                f"scaffolded skill_registry entry must use 'skill_id' key, "
                f"got keys: {list(entry.keys())}"
            )
            assert "id" not in entry, (
                "scaffolded skill_registry must NOT use bare 'id' key — "
                "that's the actions block convention, not the skill registry"
            )

    def test_parses_via_skill_registry(self, tmp_path):
        """End-to-end: scaffold YAML → write to disk → load via the same
        parser broker uses at experiment build time. Catches the exact
        Finding #2 KeyError class of bugs."""
        from broker.components.governance.registry import SkillRegistry

        text = gen_skill_registry("energy", ["a", "b"])
        p = tmp_path / "skill_registry.yaml"
        p.write_text(text, encoding="utf-8")

        reg = SkillRegistry()
        reg.register_from_yaml(str(p))  # raises if scaffold output is invalid


class TestGenDomainPack:
    def test_class_name_camelcase(self):
        text = gen_domain_pack("energy_consumer")
        assert "class EnergyConsumerDomainPack" in text
        assert "DefaultDomainPack" in text

    def test_emits_psychological_framework_override(self):
        """P1: the generated pack MUST override psychological_framework() so a
        YAML-declared framework is not silently ignored — dispatch reads the
        PACK, and DefaultDomainPack's default is the "" escape-hatch."""
        pmt = gen_domain_pack("energy", "pmt")
        assert "def psychological_framework" in pmt
        assert 'return "pmt"' in pmt
        custom = gen_domain_pack("traffic", "custom")
        assert 'return "traffic_framework"' in custom


# ---------------------------------------------------------------------------
# End-to-end: scaffold → validate
# ---------------------------------------------------------------------------

class TestScaffoldEndToEnd:
    """The acid test: scaffolded output passes validate_prompt clean."""

    def test_scaffolded_yaml_validates_clean(self, tmp_path: Path, capsys):
        scaffold(
            "energy_consumer",
            tmp_path / "energy",
            ["increase_use", "maintain_use", "decrease_use"],
            framework="pmt",
        )
        yaml_path = tmp_path / "energy" / "config" / "agent_types.yaml"
        # validate_prompt should exit 0 (clean)
        rc = validate_main([str(yaml_path)])
        captured = capsys.readouterr()
        assert rc == 0, (
            f"scaffolded YAML failed validate_prompt:\n{captured.out}"
        )

    def test_custom_framework_also_validates(self, tmp_path: Path, capsys):
        scaffold(
            "traffic_commuter",
            tmp_path / "traffic",
            ["drive", "transit", "bike"],
            framework="custom",
        )
        yaml_path = tmp_path / "traffic" / "config" / "agent_types.yaml"
        rc = validate_main([str(yaml_path)])
        captured = capsys.readouterr()
        assert rc == 0, (
            f"custom-framework scaffolded YAML failed validate_prompt:\n"
            f"{captured.out}"
        )

    def test_pmt_default_has_no_cognition_dir(self, tmp_path: Path):
        scaffold("energy", tmp_path / "energy", ["a", "b"], framework="pmt")
        assert not (tmp_path / "energy" / "cognition").exists()

    def test_custom_framework_creates_cognition_dir(self, tmp_path: Path):
        scaffold("traffic", tmp_path / "traffic", ["a", "b"],
                 framework="custom")
        cognition_dir = tmp_path / "traffic" / "cognition"
        assert cognition_dir.exists()
        assert (cognition_dir / "__init__.py").exists()
        assert (cognition_dir / "traffic_framework.py").exists()

    def test_all_required_files_created(self, tmp_path: Path):
        scaffold("energy", tmp_path / "energy", ["a", "b"], framework="pmt")
        root = tmp_path / "energy"
        required = [
            "__init__.py",
            "README.md",
            "config/skill_registry.yaml",
            "config/agent_types.yaml",
            "config/prompts/agent.txt",
            "validators/__init__.py",
            "validators/energy_validators.py",
            "adapters/__init__.py",
            "adapters/energy_pack.py",
            "world.py",
        ]
        for rel in required:
            assert (root / rel).exists(), f"missing scaffolded file: {rel}"
        assert not (root / "run_experiment.py").exists()

    def test_overwrite_protection(self, tmp_path: Path):
        target = tmp_path / "energy"
        scaffold("energy", target, ["a"], framework="pmt")
        with pytest.raises(FileExistsError):
            scaffold("energy", target, ["b"], framework="pmt", force=False)

    def test_force_overwrites(self, tmp_path: Path):
        target = tmp_path / "energy"
        scaffold("energy", target, ["a"], framework="pmt")
        scaffold("energy", target, ["b", "c"], framework="pmt", force=True)
        # Re-loaded YAML should reflect new skills
        data = yaml.safe_load(
            (target / "config" / "agent_types.yaml").read_text(encoding="utf-8")
        )
        ids = [a["id"] for a in data["agent"]["actions"]]
        assert ids == ["b", "c"]

    @staticmethod
    def _assert_scaffold_imports(root: Path, framework_label: str):
        """Import a scaffolded package in a subprocess and assert
        the DomainPack + physical validators registered. The YAML acid-tests
        never import the package, so a broken validators/__init__.py or top
        __init__.py (nonexistent module import, wrong register signature,
        dedent IndentationError) would otherwise ship green — the exact P0
        class this guards. Subprocess so registry side-effects don't leak."""
        domain = root.name
        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(root.parent)!r})\n"
            f"import {domain}  # triggers cognition + validator + DomainPack registration\n"
            "from broker.domains.registry import DomainPackRegistry\n"
            "from broker.components.governance.validator_registry import ValidatorRegistry\n"
            "from broker.validators.governance.thinking_validator import FRAMEWORK_LABEL_ORDERS\n"
            f"pack = DomainPackRegistry.get({domain!r})\n"
            "assert pack is not None, 'DomainPack not registered'\n"
            f"assert pack.psychological_framework() == {framework_label!r}\n"
            f"assert ValidatorRegistry.get_checks({domain!r}, 'physical'), 'physical checks not registered'\n"
            f"assert {framework_label!r} in FRAMEWORK_LABEL_ORDERS, 'framework metadata not registered'\n"
            "print('IMPORT_OK')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0 and "IMPORT_OK" in r.stdout, (
            f"scaffolded {framework_label} package failed to import/register:\n"
            f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
        )

    def test_scaffolded_pmt_package_imports_and_registers(self, tmp_path: Path):
        root = tmp_path / "energy"
        scaffold("energy", root, ["increase", "maintain", "decrease"], framework="pmt")
        self._assert_scaffold_imports(root, "pmt")

    def test_scaffolded_custom_package_imports_and_registers(self, tmp_path: Path):
        # Exercises the custom-framework path (cognition module + the dedent
        # indentation that previously emitted a broken __init__.py).
        root = tmp_path / "traffic"
        scaffold("traffic", root, ["drive", "transit", "bike"], framework="custom")
        self._assert_scaffold_imports(root, "traffic_framework")

    def test_physical_only_scaffold_is_theory_free(self, tmp_path: Path):
        root = tmp_path / "energy"
        assert main(["energy", "--output", str(root), "--physical-only"]) == 0

        yaml_path = root / "config" / "agent_types.yaml"
        yaml_text = yaml_path.read_text(encoding="utf-8")
        data = yaml.safe_load(yaml_text)
        keys = list(_yaml_keys(data))
        agent = data["agent"]
        assert agent["psychological_framework"] == "none"
        assert "rating_scale" not in yaml_text
        assert "constructs" not in keys
        assert data["global_config"]["reflection"]["enabled"] is False
        assert "preprocessor" not in agent["parsing"]
        assert "proximity_window" not in agent["parsing"]
        assert agent["log_fields"] == []
        fields = data["shared"]["response_format"]["fields"]
        assert [(field["key"], field["type"], field["required"]) for field in fields] == [
            ("reasoning", "text", True),
            ("decision", "choice", True),
        ]
        assert keys.count("max_retries") == 1
        assert data["global_config"]["governance"]["max_retries"] == 3
        assert "max_reports_per_retry" not in keys

        # R5 walk findings 7 and 9: the README speaks to a physical-only case
        # and points at the integrity check.
        readme = (root / "README.md").read_text(encoding="utf-8")
        assert "[Broker:Retry]" not in readme
        assert "physical-only" in readme
        assert "check_run_integrity" in readme

        prompt = (root / "config" / "prompts" / "agent.txt").read_text(encoding="utf-8")
        assert "{rating_scale}" not in prompt
        assert not any(term in prompt.casefold() for term in PMT_TEXT_MARKERS)
        for placeholder in ("narrative_persona", "memory", "options_text", "response_format"):
            assert "{" + placeholder + "}" in prompt
        assert not (root / "cognition").exists()

        AgentTypeConfig.clear_cache()
        try:
            assert AgentTypeConfig.load(str(yaml_path)).check_theory_free("agent") == []
            assert validate_main([str(yaml_path)]) == 0
        finally:
            AgentTypeConfig.clear_cache()
        self._assert_scaffold_imports(root, "none")

    def test_scaffolded_pack_consumer_calls_and_physical_dispatch_flag(
        self, tmp_path: Path
    ):
        scaffold(
            "energy",
            tmp_path / "energy",
            ["increase", "maintain", "decrease"],
            framework="pmt",
        )
        agent_types = (
            tmp_path / "energy" / "config" / "agent_types.yaml"
        ).read_text(encoding="utf-8")
        assert "dispatch_domain_physical: true" in agent_types
        assert "summary_counts_python_checks: true" in agent_types

        code = (
            "import sys\n"
            f"sys.path.insert(0, {str(tmp_path)!r})\n"
            "import energy\n"
            "from broker.domains.registry import DomainPackRegistry\n"
            "pack = DomainPackRegistry.get('energy')\n"
            "assert isinstance(pack.compute_importance({'event_type': 'x'}, 0.7), float)\n"
            "assert isinstance(pack.classify_emotion('some_skill', {'k': 1}), str)\n"
            "assert isinstance(pack.skill_emotion_metadata('any_skill'), dict)\n"
            "print('PACK_CALLS_OK')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, timeout=120,
        )
        assert r.returncode == 0 and "PACK_CALLS_OK" in r.stdout, (
            "scaffolded DomainPack consumer-shape calls failed:\n"
            f"STDOUT:\n{r.stdout}\nSTDERR:\n{r.stderr}"
        )

    def test_scaffolded_runner_completes_mock_smoke(self, tmp_path: Path):
        root = tmp_path / "energy"
        scaffold(
            "energy",
            root,
            ["increase", "maintain", "decrease"],
            framework="pmt",
        )
        config = root / "config" / "agent_types.yaml"
        _assert_mock_smoke(root, ["-m", "broker.run", str(config)])

    def test_legacy_scaffold_runner_completes_mock_smoke(self, tmp_path: Path):
        root = tmp_path / "energy"
        assert main(["energy", "--output", str(root)]) == 0
        runner = root / "run_experiment.py"
        shutil.copyfile(LEGACY_RUNNER, runner)
        _assert_mock_smoke(root, [str(runner)])


# ---------------------------------------------------------------------------
# CLI argument handling
# ---------------------------------------------------------------------------

class TestCLI:
    def test_rejects_physical_only_with_explicit_framework(self, tmp_path: Path, capsys):
        rc = main([
            "energy", "--output", str(tmp_path / "energy"),
            "--physical-only", "--framework", "pmt",
        ])
        assert rc == 1
        assert "--physical-only cannot be combined with --framework" in capsys.readouterr().err

    @pytest.mark.parametrize("folder", ["energy-demo", "2energy", "énergie"])
    def test_rejects_output_folder_broker_run_cannot_import(
        self, tmp_path: Path, capsys, folder
    ):
        rc = main(["energy", "--output", str(tmp_path / folder)])
        assert rc == 1
        assert "must be a Python identifier" in capsys.readouterr().err
        assert not (tmp_path / folder).exists()

    def test_rejects_uppercase_domain(self, tmp_path: Path, capsys):
        rc = main(["MyDomain", "--output", str(tmp_path / "x")])
        captured = capsys.readouterr()
        assert rc == 1
        assert "lowercase snake_case" in captured.err

    def test_rejects_empty_skills(self, tmp_path: Path, capsys):
        rc = main([
            "energy", "--output", str(tmp_path / "x"), "--skills", ",,,",
        ])
        captured = capsys.readouterr()
        assert rc == 1
        assert "at least one skill" in captured.err

    def test_successful_run_returns_zero(self, tmp_path: Path, capsys):
        rc = main([
            "energy", "--output", str(tmp_path / "energy"),
            "--skills", "increase,maintain,decrease",
        ])
        captured = capsys.readouterr()
        assert rc == 0
        assert "Scaffolded" in captured.out
        assert (tmp_path / "energy" / "config" / "agent_types.yaml").exists()
        # R5 walk findings 7 and 9
        assert "check_run_integrity" in captured.out
        readme = (tmp_path / "energy" / "README.md").read_text(encoding="utf-8")
        assert "check_run_integrity" in readme and "[Broker:Retry]" in readme
        registry = (tmp_path / "energy" / "config" / "skill_registry.yaml").read_text(
            encoding="utf-8")
        assert "maintain_* or hold action" in registry
        checks = (tmp_path / "energy" / "validators" / "energy_validators.py").read_text(
            encoding="utf-8")
        assert "(proposal, context, skill_registry)" in checks



class TestMagnitudeFlag:
    """--magnitude adds the [0, 1] action number; without it nothing changes."""

    def test_default_output_has_no_magnitude_and_no_mock_file(self, tmp_path: Path):
        written = scaffold("probe", tmp_path / "probe", ["a", "b"], "pmt")
        names = {p.relative_to(tmp_path / "probe").as_posix() for p in written}
        assert "mock_llm.py" not in names
        text = (tmp_path / "probe" / "config" / "agent_types.yaml").read_text(encoding="utf-8")
        assert "magnitude" not in text and "mock:" not in text
        assert gen_agent_types_yaml("probe", ["a", "b"], "pmt") == gen_agent_types_yaml(
            "probe", ["a", "b"], "pmt", magnitude=False)
        assert "--magnitude" not in (tmp_path / "probe" / "README.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("physical_only", [False, True])
    def test_flag_writes_a_zero_to_one_field(self, tmp_path: Path, physical_only: bool):
        written = scaffold("probe", tmp_path / "probe", ["a", "b"], "pmt",
                           physical_only=physical_only, magnitude=True)
        names = {p.relative_to(tmp_path / "probe").as_posix() for p in written}
        assert "mock_llm.py" in names
        cfg = yaml.safe_load((tmp_path / "probe" / "config" / "agent_types.yaml").read_text(encoding="utf-8"))
        field = next(f for f in cfg["shared"]["response_format"]["fields"] if f["key"] == "magnitude")
        assert (field["type"], field["min"], field["max"]) == ("numeric", 0, 1)
        assert "fraction" in field["description"].lower()
        assert cfg["global_config"]["run"]["mock"] == "mock_llm:build_mock"
        prompt = (tmp_path / "probe" / "config" / "prompts" / "agent.txt").read_text(encoding="utf-8")
        assert "0.5 means half" in prompt
        world = (tmp_path / "probe" / "world.py").read_text(encoding="utf-8")
        assert 'parameters.get("magnitude_pct")' in world
        assert "--magnitude" in (tmp_path / "probe" / "README.md").read_text(encoding="utf-8")
        assert validate_main([str(tmp_path / "probe" / "config" / "agent_types.yaml"), "--strict"]) == 0
        for name in ("world.py", "mock_llm.py"):
            compile((tmp_path / "probe" / name).read_text(encoding="utf-8"), name, "exec")

    def test_cli_flag(self, tmp_path: Path):
        assert main(["probe", "--output", str(tmp_path / "probe"), "--magnitude"]) == 0
        assert (tmp_path / "probe" / "mock_llm.py").is_file()
