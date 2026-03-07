from pathlib import Path

from broker.components.response_format import ResponseFormatBuilder
from broker.utils.agent_config import AgentTypeConfig


def main() -> int:
    base = Path(__file__).resolve().parent
    cfg = AgentTypeConfig.load(str(base / "agent_types.yaml"), force_reload=True)

    framework = cfg.get_framework_for_agent_type("analyst")
    actions = cfg.get_valid_actions("analyst")
    agent_cfg = cfg.get("analyst")
    shared_cfg = {"response_format": cfg.get_shared("response_format", {})}
    response_format = ResponseFormatBuilder(
        agent_cfg,
        shared_config=shared_cfg,
        framework=framework,
    ).build(valid_choices_text="1 or 2")

    print("minimal_nonwater")
    print(f"framework={framework}")
    print(f"actions={','.join(actions)}")
    print(f"has_risk_label={'RISK_LABEL' in response_format}")
    print(f"has_capacity_label={'CAPACITY_LABEL' in response_format}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
