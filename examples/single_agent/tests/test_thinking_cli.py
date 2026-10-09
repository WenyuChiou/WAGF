"""Static CLI contract checks for every model CLI runner under examples.

The runners build their parsers inside ``__main__``/``main`` and importing
them to parse arguments would execute substantial experiment setup. AST checks
pin the switch and its pre-run assignment without starting Ollama or an LLM.
"""

import ast
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[3]


def _model_cli_runners():
    runners = []
    for path in (ROOT / "examples").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        flags = {
            node.args[0].value
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_argument"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        }
        if flags.intersection({"--model", "--llm-model", "--ollama-model", "--provider"}):
            runners.append(path)
    return tuple(sorted(runners))


RUNNERS = _model_cli_runners()


def _thinking_argument(tree: ast.AST) -> ast.Call:
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "add_argument" or not node.args:
            continue
        if isinstance(node.args[0], ast.Constant) and node.args[0].value == "--thinking-mode":
            return node
    raise AssertionError("runner does not declare --thinking-mode")


@pytest.mark.parametrize("runner_path", RUNNERS, ids=lambda path: str(path.relative_to(ROOT)))
def test_every_model_cli_inherits_and_accepts_all_thinking_modes(runner_path):
    tree = ast.parse(runner_path.read_text(encoding="utf-8-sig"), filename=str(runner_path))
    argument = _thinking_argument(tree)
    keywords = {keyword.arg: keyword.value for keyword in argument.keywords}

    assert isinstance(keywords["default"], ast.Constant)
    assert keywords["default"].value is None
    assert isinstance(keywords["choices"], (ast.List, ast.Tuple))
    assert [item.value for item in keywords["choices"].elts] == [
        "auto", "disabled", "enabled"
    ]

    assignments = [
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "LLM_CONFIG"
            and target.attr == "thinking_mode"
            for target in node.targets
        )
    ]
    if runner_path.name == "run_ungoverned_experiment.py":
        forwarding = next(
            node for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_build_forwarding_argv"
        )
        forwarded_literals = {
            node.value for node in ast.walk(forwarding)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        }
        assert "--thinking-mode" in forwarded_literals
        assert not assignments
        return

    assert len(assignments) == 1
    value = assignments[0].value
    assert isinstance(value, ast.Attribute)
    assert isinstance(value.value, ast.Name) and value.value.id == "args"
    assert value.attr == "thinking_mode"
