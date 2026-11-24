"""Resolve Python slots with a case-local origin check for YAML imports.

Importing a case module also runs the __init__.py files of the packages
containing the case on the import path (for example, examples/__init__.py),
as in a normal Python import. Case package and slot code executes as Python.
"""

import importlib
from importlib.machinery import PathFinder
import importlib.util
import os
from pathlib import Path
import re
import sys


class SlotError(ValueError):
    """Invalid slot specification, origin, or factory."""


_IDENTIFIER = r"[A-Za-z_][A-Za-z0-9_]*"
_DOTTED_NAME = re.compile(rf"{_IDENTIFIER}(?:\.{_IDENTIFIER})*", re.ASCII)
_ATTRIBUTE = re.compile(_IDENTIFIER, re.ASCII)


def valid_module_name(name):
    return _DOTTED_NAME.fullmatch(name) is not None


def parse_slot(slot_name, spec):
    if isinstance(spec, str) and spec.count(":") == 1:
        module, attr = spec.split(":")
        if valid_module_name(module) and _ATTRIBUTE.fullmatch(attr):
            return module, attr
    raise SlotError(f"run.{slot_name} must be module:attr with ASCII Python identifiers, got {spec!r}")


def _canonical(path):
    return os.path.normcase(os.path.realpath(path))


def _inside(path, root):
    try:
        return os.path.commonpath((path, root)) == root
    except ValueError:  # Paths on different Windows drives.
        return False


def _case_files(parts, case_dir, label):
    target = case_dir.joinpath(*parts)
    package = target / "__init__.py"
    candidates = [path for path in (package, target.with_suffix(".py")) if os.path.lexists(path)]
    if not candidates:
        return []

    parents = [case_dir.joinpath(*parts[:i], "__init__.py") for i in range(len(parts))]
    root = _canonical(case_dir)
    for path in (*parents, *candidates):
        real = os.path.realpath(path)
        if not _inside(os.path.normcase(real), root):
            raise SlotError(f"{label} resolves to {real}, outside the case folder {case_dir}")
    # Python may run a cached .pyc from __pycache__ instead of the source
    # (an unchecked-hash pyc is never compared with it), so every
    # __pycache__ on the import chain must also stay inside the case folder.
    folders = [case_dir.joinpath(*parts[:i]) for i in range(len(parts))]
    if candidates[0].name == "__init__.py":
        folders.append(target)
    for folder in folders:
        cache = folder / "__pycache__"
        if os.path.lexists(cache):
            real = os.path.realpath(cache)
            if not _inside(os.path.normcase(real), root):
                raise SlotError(
                    f"{label} has a __pycache__ folder that resolves to {real}, "
                    f"outside the case folder {case_dir}"
                )
    # The cached file itself may also be a link. Skipped when the operator set
    # sys.pycache_prefix (PYTHONPYCACHEPREFIX): that cache lives outside every
    # case folder by the operator's choice.
    if sys.pycache_prefix is None:
        for path in (*parents, candidates[0]):
            try:
                pyc = importlib.util.cache_from_source(str(path))  # follows the -O level
            except NotImplementedError:
                continue
            if os.path.lexists(pyc) and not _inside(_canonical(pyc), root):
                raise SlotError(
                    f"{label} has cached bytecode {pyc} that resolves to "
                    f"{os.path.realpath(pyc)}, outside the case folder {case_dir}"
                )
    for path in (*parents, *candidates):
        if not path.is_file():
            raise SlotError(f"{label} requires a file at {path} in the case folder {case_dir}")
    # Python searches for a regular package before a same-named source module.
    return [*parents, candidates[0]]


def _package_prefix(case_dir, label):
    root = _canonical(case_dir)
    for entry in sys.path:
        if not isinstance(entry, str):
            continue
        base = Path(os.path.realpath(entry or os.getcwd()))
        base_key = _canonical(base)
        if root == base_key or not _inside(root, base_key):
            continue
        parts = Path(os.path.relpath(case_dir, base)).parts
        if all(_ATTRIBUTE.fullmatch(part) for part in parts) and all(
            (base.joinpath(*parts[:i]) / "__init__.py").is_file()
            for i in range(1, len(parts) + 1)
        ):
            ancestor_files = [
                base.joinpath(*parts[:i], "__init__.py") for i in range(1, len(parts))
            ]
            return parts, ancestor_files, None

    if not _ATTRIBUTE.fullmatch(case_dir.name):
        raise SlotError(f"{label} requires a valid package name for the case folder {case_dir}")
    return (case_dir.name,), [], str(case_dir.parent)


def _check_origin(origin, expected, name, label):
    if origin is None:
        raise SlotError(
            f"{label}: Python found no module {name!r} at {expected} "
            f"(check the spelling and upper/lower case of the file name)"
        )
    if _canonical(origin) != _canonical(expected):
        raise SlotError(f"{label} found {name!r} at {origin}, expected {expected}")


def _load_case_module(parts, files, case_dir, label):
    prefix, ancestor_files, extra_path = _package_prefix(case_dir, label)
    names = prefix + parts
    chain = [
        (".".join(names[:i]), path)
        for i, path in enumerate((*ancestor_files, *files), start=1)
    ]
    # Appended, not prepended: the case's parent folder must not shadow the
    # standard library or installed packages for the rest of the process. If
    # an earlier entry holds a package of the same name, the origin checks
    # below refuse it.
    if extra_path is not None and not any(
        isinstance(entry, str) and entry and _canonical(entry) == _canonical(extra_path)
        for entry in sys.path
    ):
        sys.path.append(extra_path)

    # find_spec on a dotted name imports missing parents. Walk the filesystem
    # specs first so a shadowed parent or leaf can be refused without doing so.
    search_path = []
    for index, (name, expected) in enumerate(chain):
        if name in sys.modules:
            cached = sys.modules[name]
            _check_origin(getattr(cached, "__file__", None), expected, name, label)
            search_path = getattr(cached, "__path__", [])
        else:
            spec = importlib.util.find_spec(name) if index == 0 else PathFinder.find_spec(name, search_path)
            _check_origin(getattr(spec, "origin", None), expected, name, label)
            search_path = spec.submodule_search_locations or []

    # Check actual import resolution again after each verified parent loads.
    # Package initialization can change import paths or populate sys.modules.
    for name, expected in chain:
        if name not in sys.modules:
            spec = importlib.util.find_spec(name)
            _check_origin(getattr(spec, "origin", None), expected, name, label)
        else:
            _check_origin(getattr(sys.modules[name], "__file__", None), expected, name, label)
        module = importlib.import_module(name)
        _check_origin(getattr(module, "__file__", None), expected, name, label)
    return module


def vet_import_target(label, spec, case_dir, *, allowed_modules):
    """Apply the case-folder rule to a ``module:attr`` the YAML names outside ``run:``.

    The importing code (for example the parametric decider) imports the module
    by its own name later. A module allowed with --allow-module passes as is. A
    module of the case folder, named by its importable dotted name, is loaded
    here through the same origin checks as a slot, so the later import gets
    this vetted module from sys.modules. Anything else is refused.
    """
    module_name, _, attr = spec.partition(":") if isinstance(spec, str) else ("", "", "")
    module_name, attr = module_name.strip(), attr.strip()
    if not (valid_module_name(module_name) and _ATTRIBUTE.fullmatch(attr)):
        raise SlotError(f"{label} must be module:attr with ASCII Python identifiers, got {spec!r}")
    if module_name in allowed_modules:
        return
    case_dir = Path(os.path.realpath(case_dir))
    parts = tuple(module_name.split("."))
    prefix, _, _ = _package_prefix(case_dir, label)
    files = []
    if len(parts) > len(prefix) and parts[: len(prefix)] == tuple(prefix):
        relative = parts[len(prefix):]
        files = _case_files(relative, case_dir, label)
    if not files:
        case_name = ".".join(prefix)
        raise SlotError(
            f"{label} names module {module_name!r}, which is not a module of the case "
            f"folder {case_dir} (a case module is named {case_name}.<module>). A YAML "
            f"may import only modules from its own case folder; to use another module, "
            f"pass --allow-module {module_name} on the command line."
        )
    try:
        _load_case_module(relative, files, case_dir, label)
    except (ImportError, OSError, SyntaxError) as exc:
        raise SlotError(f"Could not import {label}: {exc}") from exc


def resolve_slot(slot_name, spec, case_dir, *, from_cli, allowed_modules):
    """Return the callable named by a vetted case or explicitly allowed import."""
    module_name, attr = parse_slot(slot_name, spec)
    case_dir = Path(os.path.realpath(case_dir))
    parts = tuple(module_name.split("."))
    label = f"run.{slot_name} module {module_name!r}"
    files = _case_files(parts, case_dir, label)
    try:
        if files:
            module = _load_case_module(parts, files, case_dir, label)
        elif from_cli or module_name in allowed_modules:
            module = importlib.import_module(module_name)
        else:
            raise SlotError(
                f"run.{slot_name} names module {module_name!r}, which is not inside "
                f"the case folder {case_dir}. A YAML may import only modules from "
                f"its own case folder; to use another module, pass --allow-module "
                f"{module_name} (or --slot {slot_name}={spec}) on the command line."
            )
    except (ImportError, OSError, SyntaxError) as exc:
        raise SlotError(f"Could not import {label}: {exc}") from exc

    factory = getattr(module, attr, None)
    if not callable(factory):
        raise SlotError(f"{label} must define a callable {attr!r}")
    return factory
