"""Tests for broker.tools.gen_test_fixture CLI (Phase 6R-A).

The generator must:
1. Produce a 2-file package (__init__.py + pack.py) under the output
   directory.
2. Generate a syntactically valid DomainPack subclass that imports cleanly
   when added to sys.path.
3. Register the pack with DomainPackRegistry at import time.
4. Refuse to overwrite an existing fixture directory unless --overwrite
   is passed.
5. Reject invalid --domain (non-identifier) and --sub-pack (unknown name).
"""
from __future__ import annotations

import importlib
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from broker.tools.gen_test_fixture import (
    _VALID_SUB_PACKS,
    _class_name,
    gen_package_init,
    gen_pack,
    main,
    write_fixture,
)


# ---------------------------------------------------------------------------
# Pure-template generator tests (no I/O)
# ---------------------------------------------------------------------------

class TestClassName:
    def test_simple_lowercase(self):
        assert _class_name("traffic") == "TrafficDomainPack"

    def test_underscores_become_camel(self):
        assert _class_name("test_reflection_x") == "TestReflectionXDomainPack"

    def test_already_camel(self):
        # We always Capitalize each underscore-segment; mixed case input
        # is normalised.
        assert _class_name("foo_bar") == "FooBarDomainPack"


class TestGenPackageInit:
    def test_contains_register_call(self):
        text = gen_package_init("test_x", "reflection")
        assert "DomainPackRegistry.register(" in text
        assert '"test_x"' in text
        assert "TestXDomainPack" in text

    def test_silent_skip_on_import_error(self):
        text = gen_package_init("test_x", "any")
        assert "except ImportError" in text


class TestGenPack:
    def test_subclasses_default_domain_pack(self):
        text = gen_pack("test_x", "memory")
        assert "from broker.domains.default import DefaultDomainPack" in text
        assert "class TestXDomainPack(DefaultDomainPack):" in text

    def test_carries_sub_pack_tag(self):
        text = gen_pack("test_x", "memory")
        # Tag appears in the docstring so a maintainer can grep it.
        assert "memory" in text

    def test_sets_name_attribute(self):
        text = gen_pack("test_x", "any")
        assert 'name: str = "test_x"' in text


# ---------------------------------------------------------------------------
# I/O orchestration tests
# ---------------------------------------------------------------------------

class TestWriteFixture:
    def test_creates_package_directory_with_2_files(self, tmp_path: Path):
        pkg = write_fixture("test_a", tmp_path, "any")
        assert pkg == tmp_path / "test_a"
        assert (pkg / "__init__.py").exists()
        assert (pkg / "pack.py").exists()

    def test_refuses_existing_dir_by_default(self, tmp_path: Path):
        write_fixture("test_b", tmp_path, "any")
        with pytest.raises(FileExistsError):
            write_fixture("test_b", tmp_path, "any")

    def test_overwrite_replaces_existing(self, tmp_path: Path):
        pkg = write_fixture("test_c", tmp_path, "any")
        # Mutate then overwrite — file must come back to canonical content.
        (pkg / "pack.py").write_text("# corrupted", encoding="utf-8")
        write_fixture("test_c", tmp_path, "any", overwrite=True)
        text = (pkg / "pack.py").read_text(encoding="utf-8")
        assert "class TestCDomainPack(DefaultDomainPack):" in text

    def test_rejects_invalid_domain_name(self, tmp_path: Path):
        with pytest.raises(ValueError, match="must be a valid Python identifier"):
            write_fixture("123_bad_name", tmp_path, "any")

    def test_rejects_python_keyword_domain(self, tmp_path: Path):
        # `str.isidentifier()` returns True for keywords like 'class',
        # 'def', 'import' — but the resulting package can't be imported.
        # Phase 6R-A reviewer must-fix #1.
        for kw in ("class", "def", "import", "return"):
            with pytest.raises(ValueError, match="must not be a Python keyword"):
                write_fixture(kw, tmp_path, "any")

    def test_rejects_unknown_sub_pack(self, tmp_path: Path):
        with pytest.raises(ValueError, match="must be one of"):
            write_fixture("test_d", tmp_path, "nonsense_pack")


class TestGeneratedFixtureImports:
    """Acid test: the generated package must actually import + register."""

    def test_generated_pack_imports_and_registers(self, tmp_path: Path):
        # Generate at tmp_path/_test_fixtures/test_e/
        fixtures_root = tmp_path / "_test_fixtures"
        fixtures_root.mkdir()
        # Make tmp_path a fake "package root" by adding an empty
        # _test_fixtures/__init__.py so the generated package is importable.
        (fixtures_root / "__init__.py").touch()
        pkg = write_fixture("test_e", fixtures_root, "reflection")

        # Snapshot registry + sys.path so we can roll back after.
        # ``DomainPackRegistry.clear()`` wipes both ``_packs`` and
        # ``_missing_warned``; save/restore both to keep the contract
        # symmetric (per Phase 6R-A reviewer must-fix #2).
        from broker.domains.registry import DomainPackRegistry
        saved_packs = dict(DomainPackRegistry._packs)
        saved_warned = set(DomainPackRegistry._missing_warned)
        saved_path = list(sys.path)

        try:
            sys.path.insert(0, str(tmp_path))
            mod = importlib.import_module("_test_fixtures.test_e")
            # Pack should have registered itself.
            pack = DomainPackRegistry.get("test_e")
            assert pack is not None
            assert pack.name == "test_e"
            # And inherits from DefaultDomainPack — exercising the inheritance.
            from broker.domains.default import DefaultDomainPack
            assert isinstance(pack, DefaultDomainPack)
        finally:
            sys.path = saved_path
            DomainPackRegistry.clear()
            for name, p in saved_packs.items():
                DomainPackRegistry._packs[name] = p
            DomainPackRegistry._missing_warned.update(saved_warned)
            # Remove the imported module so subsequent test runs are clean.
            for key in list(sys.modules):
                if key.startswith("_test_fixtures"):
                    del sys.modules[key]


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class TestCLI:
    def test_main_happy_path(self, tmp_path: Path, capsys):
        rc = main([
            "--domain", "test_cli_a",
            "--output", str(tmp_path),
        ])
        assert rc == 0
        assert (tmp_path / "test_cli_a" / "pack.py").exists()
        captured = capsys.readouterr()
        assert "Generated test fixture at:" in captured.out

    def test_main_invalid_domain_returns_nonzero(self, tmp_path: Path, capsys):
        rc = main([
            "--domain", "123_bad",
            "--output", str(tmp_path),
        ])
        assert rc == 1
        captured = capsys.readouterr()
        assert "ERROR" in captured.err

    def test_main_existing_dir_without_overwrite_fails(
        self, tmp_path: Path, capsys,
    ):
        main(["--domain", "test_cli_b", "--output", str(tmp_path)])
        rc = main(["--domain", "test_cli_b", "--output", str(tmp_path)])
        assert rc == 1
        captured = capsys.readouterr()
        assert "already exists" in captured.err

    def test_main_overwrite_succeeds(self, tmp_path: Path):
        main(["--domain", "test_cli_c", "--output", str(tmp_path)])
        rc = main([
            "--domain", "test_cli_c",
            "--output", str(tmp_path),
            "--overwrite",
        ])
        assert rc == 0


class TestSubPackEnumeration:
    def test_all_7_proposed_sub_packs_plus_any_are_valid(self):
        # Phase 6R-D will define 7 sub-protocols + 'any' fallback.
        expected = {
            "reflection", "memory", "skill", "event",
            "perception", "governance", "setup", "any",
        }
        assert _VALID_SUB_PACKS == expected
