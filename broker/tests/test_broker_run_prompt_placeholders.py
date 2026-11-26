"""Tests for startup prompt-placeholder warnings in broker.run."""

from __future__ import annotations

import shutil
import sys
import uuid
from pathlib import Path

import yaml

from broker.run import main
from broker.utils.agent_config import AgentTypeConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
WATER_STARTER = REPO_ROOT / "templates" / "water_starter"


def _copy_starter(tmp_path: Path, monkeypatch) -> Path:
    monkeypatch.setattr(sys, "path", sys.path.copy())
    case_dir = tmp_path / f"starter_{uuid.uuid4().hex[:8]}"
    shutil.copytree(WATER_STARTER, case_dir)
    return case_dir / "config" / "agent_types.yaml"


def test_undeclared_placeholder_warns_on_stderr_when_template_vars_declared(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _copy_starter(tmp_path, monkeypatch)
    prompt_path = cfg_path.parent / "prompts" / "operator.txt"
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8") + "\nForecast typo: {inflow_forcast}\n",
        encoding="utf-8",
    )
    AgentTypeConfig.clear_cache()
    try:
        rc = main([
            str(cfg_path), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "out"),
        ])
    finally:
        AgentTypeConfig.clear_cache()

    assert rc == 0
    err = capsys.readouterr().err
    assert "undeclared placeholder(s) ['inflow_forcast']" in err


def test_water_starter_declares_all_placeholders_with_zero_warnings(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _copy_starter(tmp_path, monkeypatch)
    AgentTypeConfig.clear_cache()
    try:
        rc = main([
            str(cfg_path), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "out"),
        ])
    finally:
        AgentTypeConfig.clear_cache()

    assert rc == 0
    err = capsys.readouterr().err
    assert "undeclared placeholder" not in err


def test_case_without_template_vars_skips_placeholder_warning(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _copy_starter(tmp_path, monkeypatch)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    raw.get("shared", {}).pop("template_vars", None)
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    prompt_path = cfg_path.parent / "prompts" / "operator.txt"
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8") + "\nRuntime var: {custom_runtime_var}\n",
        encoding="utf-8",
    )
    AgentTypeConfig.clear_cache()
    try:
        rc = main([
            str(cfg_path), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "out"),
        ])
    finally:
        AgentTypeConfig.clear_cache()

    assert rc == 0
    err = capsys.readouterr().err
    assert "undeclared placeholder" not in err


def test_inherit_shared_false_ignores_shared_template_vars(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _copy_starter(tmp_path, monkeypatch)
    raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    shared_vars = raw.get("shared", {}).get("template_vars", [])
    raw["operator"]["inherit_shared"] = False
    raw["operator"]["template_vars"] = [v for v in shared_vars if v != "inflow_forecast"]
    raw["operator"]["response_format"] = raw["shared"]["response_format"]
    cfg_path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")

    AgentTypeConfig.clear_cache()
    try:
        rc = main([
            str(cfg_path), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "out"),
        ])
    finally:
        AgentTypeConfig.clear_cache()

    assert rc == 0
    err = capsys.readouterr().err
    assert "undeclared placeholder(s) ['inflow_forecast']" in err


def test_formatted_and_converted_placeholders_warn_when_undeclared(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    cfg_path = _copy_starter(tmp_path, monkeypatch)
    prompt_path = cfg_path.parent / "prompts" / "operator.txt"
    prompt_path.write_text(
        prompt_path.read_text(encoding="utf-8")
        + "\nFormatted: {inflow_forcast:.2f} {conv_typo!s} {inflow_forecast:.2f} {{escaped_brace}}\n",
        encoding="utf-8",
    )
    AgentTypeConfig.clear_cache()
    try:
        rc = main([
            str(cfg_path), "--model", "mock", "--years", "1",
            "--output", str(tmp_path / "out"),
        ])
    finally:
        AgentTypeConfig.clear_cache()

    assert rc == 0
    err = capsys.readouterr().err
    assert "undeclared placeholder(s) ['conv_typo', 'inflow_forcast']" in err

