"""Tests for broker.tools.scaffold_domain CLI (Phase 6C-v4 cycle 4 Part B).

The acid test: a freshly scaffolded skeleton must pass validate_prompt
without ANY edits — proving the templates are correct and the new-domain
onboarding cost is genuinely one command.
"""
from __future__ import annotations

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
            "run_experiment.py",
        ]
        for rel in required:
            assert (root / rel).exists(), f"missing scaffolded file: {rel}"

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


# ---------------------------------------------------------------------------
# CLI argument handling
# ---------------------------------------------------------------------------

class TestCLI:
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
