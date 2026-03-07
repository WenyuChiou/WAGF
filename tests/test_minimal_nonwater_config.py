import subprocess
import sys
from pathlib import Path

from broker.components.response_format import ResponseFormatBuilder
from broker.utils.agent_config import AgentTypeConfig


EXAMPLE_DIR = Path(__file__).resolve().parents[1] / "examples" / "minimal_nonwater"


def test_minimal_nonwater_config_loads_and_renders():
    cfg = AgentTypeConfig.load(str(EXAMPLE_DIR / "agent_types.yaml"))

    assert cfg.get_framework_for_agent_type("analyst") == "generic"
    actions = cfg.get_valid_actions("analyst")
    assert "adapt_strategy" in actions
    assert "hold_position" in actions

    agent_cfg = cfg.get("analyst")
    shared_cfg = {"response_format": cfg.get_shared("response_format", {})}
    output = ResponseFormatBuilder(agent_cfg, shared_config=shared_cfg, framework="generic").build(
        valid_choices_text="1 or 2"
    )

    assert "risk_appraisal" in output
    assert "capacity_appraisal" in output
    assert "decision" in output


def test_minimal_nonwater_demo_runs():
    result = subprocess.run(
        [sys.executable, str(EXAMPLE_DIR / "run_demo.py")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "minimal_nonwater" in result.stdout
