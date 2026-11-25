"""Verification tests for the WAGF User Manual (mkdocs.yml) and starter template."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = ROOT / "docs"
MKDOCS_YML = ROOT / "mkdocs.yml"
STARTER_CFG = ROOT / "templates" / "water_starter" / "config" / "agent_types.yaml"


def _iter_nav_paths(node):
    if isinstance(node, list):
        for item in node:
            yield from _iter_nav_paths(item)
    elif isinstance(node, dict):
        for value in node.values():
            yield from _iter_nav_paths(value)
    elif isinstance(node, str):
        yield node


def _run_module(args: list[str], cwd: Path = ROOT) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    existing = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        str(ROOT) if not existing else str(ROOT) + os.pathsep + existing
    )
    return subprocess.run(
        [sys.executable, *args],
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def test_mkdocs_nav_targets_exist():
    """Every page referenced in mkdocs.yml nav must exist under docs/."""
    assert MKDOCS_YML.is_file(), f"missing {MKDOCS_YML}"
    cfg = yaml.safe_load(MKDOCS_YML.read_text(encoding="utf-8"))
    assert cfg.get("docs_dir") == "docs"
    nav_paths = list(_iter_nav_paths(cfg.get("nav", [])))
    assert nav_paths, "mkdocs.yml nav must not be empty"
    missing = [rel for rel in nav_paths if not (DOCS_DIR / rel).is_file()]
    assert not missing, f"mkdocs.yml references missing docs: {missing}"


def test_water_starter_validates_and_runs_mock(tmp_path):
    """templates/water_starter must validate strictly and show Year-2 block+repair."""
    val = _run_module(["-m", "broker.tools.validate_prompt", str(STARTER_CFG), "--strict"])
    assert val.returncode == 0, f"validate_prompt failed:\n{val.stdout}\n{val.stderr}"

    out_dir = tmp_path / "starter_run"
    run = _run_module(
        [
            "-m",
            "broker.run",
            str(STARTER_CFG),
            "--model",
            "mock",
            "--years",
            "2",
            "--output",
            str(out_dir),
        ]
    )
    assert run.returncode == 0, f"broker.run failed:\n{run.stdout}\n{run.stderr}"

    audit_csv = out_dir / "operator_governance_audit.csv"
    assert audit_csv.is_file(), f"missing starter audit CSV: {audit_csv}"
    with audit_csv.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2, f"expected 2 decision rows, got {len(rows)}"
    assert rows[1]["status"] == "APPROVED"
    assert int(rows[1]["retry_count"]) >= 1
    assert "dead_pool_guard" in rows[1]["failed_rules"]


def test_mkdocs_build_succeeds(tmp_path):
    """If mkdocs is installed, building static HTML into a temp dir succeeds."""
    pytest.importorskip("mkdocs")
    site_dir = tmp_path / "site"
    res = _run_module(["-m", "mkdocs", "build", "-d", str(site_dir)])
    assert res.returncode == 0, f"mkdocs build failed:\n{res.stdout}\n{res.stderr}"
    assert (site_dir / "index.html").is_file()
    assert (site_dir / "index_zh.html").is_file()
