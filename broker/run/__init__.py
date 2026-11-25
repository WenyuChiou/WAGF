"""Public CLI and Python entry point for running a governed WAGF case.

Run a case from the repository root::

    python -m broker.run examples/reservoir_control/config/reservoir_agent_types.yaml --model mock
    python -m broker.run path/to/config/agent_types.yaml --model gemma3:4b --years 5 --output results/run1

Configuration slots (declared under ``global_config.run`` in the YAML or
overridden via ``--slot NAME=module:attr``)::

    world       -> Factory returning a simulation world or ``Coupled(...)`` instance
    agents      -> Factory returning ``{agent_name: BaseAgent}`` (optional if 1 agent type)
    hooks       -> Factory returning lifecycle hook callables (e.g. ``pre_year``, ``post_step``, ``after_run``)
    validators  -> Factory returning a sequence of domain validator callables
    mock        -> Factory returning a mock LLM callable (or ``{agent_type: callable}``) under ``--model mock``

When ``CONFIG`` lives inside a ``config/`` subdirectory, ``case_dir`` resolves to
its parent directory so case modules can use local imports (e.g. ``world:build_world``).

Exported symbols (``__all__``):
    - ``Coupled``: Wrapper pairing a coupling contract, source registry, and domain name.
    - ``Prepared``: Dataclass holding a built runner, ``RunContext``, hooks, and loaded slot metadata.
    - ``RunContext``: Resolved case paths, YAML config, CLI overrides, world, and agent dict.
    - ``RunError`` / ``SlotError``: Validation errors raised for invalid CLI, YAML, or slot targets.
    - ``prepare(argv)`` / ``main(argv)``: Two-phase build helper and CLI entry point.
"""

from ._entry import Coupled, Prepared, RunContext, RunError, main, prepare
from ._imports import SlotError

__all__ = ["Coupled", "Prepared", "RunContext", "RunError", "SlotError", "main", "prepare"]
