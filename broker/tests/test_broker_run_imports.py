import os
import subprocess
import sys
from types import ModuleType
from uuid import uuid4

import pytest
import yaml

from broker.run import main
from broker.run._imports import SlotError, resolve_slot


@pytest.fixture
def case_dir(tmp_path, monkeypatch):
    folder = tmp_path / f"case_{uuid4().hex}"
    folder.mkdir()
    (folder / "__init__.py").touch()
    monkeypatch.setattr(sys, "path", sys.path.copy())
    yield folder
    for name in list(sys.modules):
        if name == folder.name or name.startswith(f"{folder.name}."):
            sys.modules.pop(name, None)


def _assert_cli_refuses(case_dir, capsys, spec, *options):
    config = case_dir / "agent_types.yaml"
    config.write_text(yaml.safe_dump({"global_config": {"run": {"world": spec}}}), encoding="utf-8")
    assert main([str(config), *options]) == 2
    error = capsys.readouterr().err
    assert error.startswith("broker.run: ")
    assert "run.world" in error
    return error


def test_yaml_requires_exact_allowlist_for_external_module(case_dir, tmp_path, monkeypatch, capsys):
    outside = tmp_path / "outside"
    outside.mkdir()
    name = f"external_{uuid4().hex}"
    (outside / f"{name}.py").write_text("def build(ctx): return 'external'\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(outside))
    spec = f"{name}:build"
    try:
        with pytest.raises(SlotError, match=f"--allow-module {name}"):
            resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules={f"{name}.other"})
        assert f"--allow-module {name}" in _assert_cli_refuses(case_dir, capsys, spec)
        assert name not in sys.modules
        assert resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules={name})(None) == "external"
        sys.modules.pop(name)
        assert resolve_slot("world", spec, case_dir, from_cli=True, allowed_modules=set())(None) == "external"
    finally:
        sys.modules.pop(name, None)


@pytest.mark.parametrize("spec", ["os:getcwd", "subprocess:run"])
def test_yaml_rejects_external_standard_library(case_dir, capsys, spec):
    with pytest.raises(SlotError, match="not inside the case folder"):
        resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules=set())
    assert spec.split(":")[0] in _assert_cli_refuses(case_dir, capsys, spec)


@pytest.mark.parametrize("spec", [
    "..x:fn", ".x:fn", "a..b:fn", "../x:fn", "a/b:fn", r"a\b:fn",
    r"C:\x:fn", "/x:fn", ":fn", "x:", "x::fn", "x:fn:extra",
    "x:pkg.fn", "x:f-n", "x:fn\n", "x", "é:fn",
])
def test_malformed_specs_are_rejected_before_lookup(case_dir, monkeypatch, capsys, spec):
    def unexpected_access(*args, **kwargs):
        pytest.fail("malformed slot reached import or case lookup")

    with monkeypatch.context() as patch:
        patch.setattr("broker.run._imports.os.path.lexists", unexpected_access)
        patch.setattr("broker.run._imports.os.path.realpath", unexpected_access)
        patch.setattr("broker.run._imports.importlib.import_module", unexpected_access)
        with pytest.raises(SlotError, match="module:attr"):
            resolve_slot("world", spec, case_dir, from_cli=True, allowed_modules=set())
    assert "module:attr" in _assert_cli_refuses(case_dir, capsys, spec)


def _link_dir(link, target):
    """A directory junction on Windows (no privilege needed), a symlink elsewhere."""
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)], check=True,
                       capture_output=True)
    else:
        os.symlink(target, link, target_is_directory=True)


def _unlink_dir(link):
    # Removes only the link, never what it points to.
    if os.name == "nt":
        os.rmdir(link)
    else:
        os.unlink(link)


@pytest.mark.parametrize("spec", ["sub.mod:build", "sub:build"])
def test_linked_package_outside_case_is_rejected(case_dir, tmp_path_factory, capsys, spec):
    target = tmp_path_factory.mktemp("junction_target")
    (target / "__init__.py").write_text("def build(ctx): return None\n", encoding="utf-8")
    (target / "mod.py").write_text("def build(ctx): return None\n", encoding="utf-8")
    link = case_dir / "sub"
    _link_dir(link, target)
    module = spec.split(":")[0]
    try:
        for allowed in (set(), {module}):
            with pytest.raises(SlotError) as refusal:
                resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules=allowed)
            assert str(target.resolve()) in str(refusal.value)
            assert str(case_dir.resolve()) in str(refusal.value)
        assert str(target.resolve()) in _assert_cli_refuses(case_dir, capsys, spec, "--allow-module", module)
        assert f"{case_dir.name}.sub" not in sys.modules
    finally:
        _unlink_dir(link)


@pytest.mark.parametrize("package", [False, True])
def test_linked_pycache_outside_case_is_rejected(case_dir, tmp_path_factory, capsys, package):
    outside = tmp_path_factory.mktemp("pycache_target")
    folder, spec = case_dir, "mod:build"
    if package:
        folder, spec = case_dir / "pkg", "pkg.mod:build"
        folder.mkdir()
        (folder / "__init__.py").touch()
    (folder / "mod.py").write_text("def build(ctx): return 'source'\n", encoding="utf-8")
    link = folder / "__pycache__"
    _link_dir(link, outside)
    try:
        with pytest.raises(SlotError, match="__pycache__") as refusal:
            resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules=set())
        assert str(outside.resolve()) in str(refusal.value)
        assert "__pycache__" in _assert_cli_refuses(case_dir, capsys, spec)
        assert f"{case_dir.name}.mod" not in sys.modules
    finally:
        _unlink_dir(link)


def _outside_bytecode(tmp_path_factory, case_dir):
    """An unchecked-hash .pyc built from code that must never run."""
    import importlib.util
    import py_compile

    outside = tmp_path_factory.mktemp("pyc_target")
    source = outside / "mod.py"
    source.write_text('raise AssertionError("OUTSIDE BYTECODE RAN")\n', encoding="utf-8")
    compiled = outside / "mod.pyc"
    py_compile.compile(str(source), cfile=str(compiled), doraise=True,
                       invalidation_mode=py_compile.PycInvalidationMode.UNCHECKED_HASH)
    (case_dir / "mod.py").write_text("def build(ctx): return 'source'\n", encoding="utf-8")
    return compiled, importlib.util.cache_from_source(str(case_dir / "mod.py"))


def test_linked_pyc_file_outside_case_is_rejected(case_dir, tmp_path_factory, monkeypatch, capsys):
    monkeypatch.setattr(sys, "pycache_prefix", None)
    compiled, cached = _outside_bytecode(tmp_path_factory, case_dir)
    os.makedirs(os.path.dirname(cached), exist_ok=True)
    try:
        os.symlink(compiled, cached)
    except OSError as error:
        pytest.skip(f"file symlinks unavailable: {error}")
    try:
        with pytest.raises(SlotError, match="cached bytecode") as refusal:
            resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
        assert str(compiled.resolve()) in str(refusal.value)
        assert "cached bytecode" in _assert_cli_refuses(case_dir, capsys, "mod:build")
        assert f"{case_dir.name}.mod" not in sys.modules
    finally:
        os.unlink(cached)


def test_cached_bytecode_outside_case_is_rejected_by_path(case_dir, tmp_path_factory, monkeypatch):
    # The same check without needing a file-symlink privilege: the cache
    # path Python would read resolves outside the case folder.
    import importlib.util

    monkeypatch.setattr(sys, "pycache_prefix", None)
    compiled, _ = _outside_bytecode(tmp_path_factory, case_dir)
    real = importlib.util.cache_from_source
    monkeypatch.setattr(
        "broker.run._imports.importlib.util.cache_from_source",
        lambda path, *a, **k: str(compiled) if path.endswith("mod.py") else real(path, *a, **k),
    )
    with pytest.raises(SlotError, match="cached bytecode"):
        resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
    assert f"{case_dir.name}.mod" not in sys.modules


def test_operator_pycache_prefix_is_not_refused(case_dir, tmp_path_factory, monkeypatch):
    monkeypatch.setattr(sys, "pycache_prefix", str(tmp_path_factory.mktemp("prefix")))
    (case_dir / "mod.py").write_text("def build(ctx): return 'source'\n", encoding="utf-8")
    factory = resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
    assert factory(None) == "source"


def test_pycache_inside_case_is_accepted(case_dir):
    (case_dir / "mod.py").write_text("def build(ctx): return 'source'\n", encoding="utf-8")
    (case_dir / "__pycache__").mkdir()
    factory = resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
    assert factory(None) == "source"


@pytest.mark.skipif(os.name != "nt", reason="needs a case-insensitive file system")
def test_case_mismatch_names_the_likely_cause(case_dir):
    (case_dir / "mod.py").write_text("def build(ctx): return None\n", encoding="utf-8")
    with pytest.raises(SlotError, match="upper/lower case"):
        resolve_slot("world", "Mod:build", case_dir, from_cli=False, allowed_modules=set())


@pytest.mark.parametrize("linked_name", ["linked.py", "__init__.py"])
def test_linked_file_outside_case_is_rejected(case_dir, tmp_path_factory, capsys, linked_name):
    target = tmp_path_factory.mktemp("symlink_target") / "target.py"
    target.write_text("def build(ctx): return None\n", encoding="utf-8")
    link = case_dir / linked_name
    if link.exists():
        link.unlink()
    try:
        os.symlink(target, link)
    except OSError as error:
        pytest.skip(f"file symlinks unavailable: {error}")
    try:
        if linked_name == "__init__.py":
            (case_dir / "linked.py").write_text("def build(ctx): return None\n", encoding="utf-8")
        with pytest.raises(SlotError) as refusal:
            resolve_slot("world", "linked:build", case_dir, from_cli=False, allowed_modules=set())
        assert str(target.resolve()) in str(refusal.value)
        assert str(target.resolve()) in _assert_cli_refuses(case_dir, capsys, "linked:build")
    finally:
        os.unlink(link)


@pytest.mark.parametrize("suffix, filename", [("", "__init__.py"), (".mod", "mod.py")])
def test_cached_shadow_is_rejected(case_dir, tmp_path, monkeypatch, capsys, suffix, filename):
    (case_dir / "mod.py").write_text("def build(ctx): return None\n", encoding="utf-8")
    shadow = ModuleType(case_dir.name + suffix)
    shadow.__file__ = str(tmp_path / "shadow" / filename)
    monkeypatch.setitem(sys.modules, shadow.__name__, shadow)
    with pytest.raises(SlotError) as refusal:
        resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
    assert shadow.__file__ in str(refusal.value)
    assert shadow.__file__ in _assert_cli_refuses(case_dir, capsys, "mod:build")
    assert sys.modules[shadow.__name__] is shadow


def test_shadowed_origin_is_rejected_before_package_code_runs(case_dir, tmp_path, monkeypatch, capsys):
    shadow_root = tmp_path / "shadow"
    shadow_dir = shadow_root / case_dir.name
    shadow_dir.mkdir(parents=True)
    shadow_init = shadow_dir / "__init__.py"
    shadow_init.write_text('raise AssertionError("shadow package executed")\n', encoding="utf-8")
    (case_dir / "mod.py").write_text("def build(ctx): return None\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(case_dir.parent))
    monkeypatch.syspath_prepend(str(shadow_root))
    with pytest.raises(SlotError) as refusal:
        resolve_slot("world", "mod:build", case_dir, from_cli=False, allowed_modules=set())
    assert str(shadow_init) in str(refusal.value)
    assert str(shadow_init) in _assert_cli_refuses(case_dir, capsys, "mod:build")
    assert case_dir.name not in sys.modules


def test_nested_module_uses_first_package_root_in_sys_path(case_dir, monkeypatch):
    outer = case_dir.parent
    (outer / "__init__.py").write_text("marker = 17\n", encoding="utf-8")
    package = case_dir / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("from ... import marker\n", encoding="utf-8")
    (package / "sub.py").write_text("from . import marker\ndef fn(ctx): return marker\n", encoding="utf-8")
    monkeypatch.syspath_prepend(str(outer))
    monkeypatch.syspath_prepend(str(outer.parent))
    try:
        factory = resolve_slot("world", "pkg.sub:fn", case_dir, from_cli=False, allowed_modules=set())
        assert factory(None) == 17
        assert factory.__module__ == f"{outer.name}.{case_dir.name}.pkg.sub"
    finally:
        for name in list(sys.modules):
            if name == outer.name or name.startswith(f"{outer.name}."):
                sys.modules.pop(name, None)


def test_case_module_requires_package_init(case_dir, capsys):
    (case_dir / "__init__.py").unlink()
    (case_dir / "mod.py").write_text("def fn(ctx): return None\n", encoding="utf-8")
    with pytest.raises(SlotError, match="__init__"):
        resolve_slot("world", "mod:fn", case_dir, from_cli=False, allowed_modules=set())
    assert "__init__.py" in _assert_cli_refuses(case_dir, capsys, "mod:fn")


@pytest.mark.parametrize("attr", ["missing", "value"])
def test_case_slot_requires_callable(case_dir, capsys, attr):
    (case_dir / "mod.py").write_text("value = 1\n", encoding="utf-8")
    spec = f"mod:{attr}"
    with pytest.raises(SlotError, match="callable"):
        resolve_slot("world", spec, case_dir, from_cli=False, allowed_modules=set())
    assert "callable" in _assert_cli_refuses(case_dir, capsys, spec)
