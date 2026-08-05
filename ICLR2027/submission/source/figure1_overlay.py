"""Compatibility entry point for the active Figure 1 builder.

The paper-facing composition lives in :mod:`figure1_agent_paper`; this
wrapper preserves the original regeneration command used by the handoff and
submission checklist.
"""

from figure1_agent_paper import build


if __name__ == "__main__":
    for key, value in build().items():
        print(f"{key}: {value}")
