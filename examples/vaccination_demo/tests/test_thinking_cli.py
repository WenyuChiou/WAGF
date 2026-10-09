"""CLI coverage for the vaccination runner's Ollama thinking override."""

import sys

from examples.vaccination_demo import run_experiment


def test_thinking_mode_defaults_to_inherited_framework_setting(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["run_experiment.py"])

    args = run_experiment.parse_args()

    assert args.thinking_mode is None


def test_thinking_mode_accepts_explicit_override(monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["run_experiment.py", "--thinking-mode", "auto"]
    )

    args = run_experiment.parse_args()

    assert args.thinking_mode == "auto"
