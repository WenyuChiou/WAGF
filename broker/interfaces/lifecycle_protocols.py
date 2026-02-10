"""
Lifecycle Hook Protocols - Standardized signatures for experiment orchestration.

Lifecycle hooks allow domain-specific logic to be injected into the simulation
loop without modifying the core ExperimentRunner. Hooks are registered as a
Dict[str, Callable] and invoked at specific points in each simulation cycle.

Hook invocation order per cycle:
    1. pre_year(year, env, agents)    — before agent decisions
    2. post_step(agent, result)       — after EACH agent's decision (called N times)
    3. post_year(year, agents)        — after ALL agents have decided

Usage:
    class MyDomainHooks:
        def pre_year(self, year: int, env: Dict[str, Any],
                     agents: Dict[str, Any]) -> None:
            # Inject situation memories, update environment context
            pass

        def post_step(self, agent: Any, result: SkillBrokerResult) -> None:
            # Log decision, update agent-specific state
            pass

        def post_year(self, year: int, agents: Dict[str, Any]) -> None:
            # Trigger batch reflection, write yearly output files
            pass

    hooks = MyDomainHooks()
    runner.hooks = {
        "pre_year": hooks.pre_year,
        "post_step": hooks.post_step,
        "post_year": hooks.post_year,
    }
"""
from typing import Protocol, Dict, Any, runtime_checkable

from ..interfaces.skill_types import SkillBrokerResult


@runtime_checkable
class PreYearHook(Protocol):
    """Called before each simulation year/step.

    Args:
        year: Current simulation year (1-based).
        env: Environment state dict returned by sim_engine.advance_year().
        agents: All agents keyed by agent_id (active + inactive).
    """

    def __call__(
        self,
        year: int,
        env: Dict[str, Any],
        agents: Dict[str, Any],
    ) -> None: ...


@runtime_checkable
class PostStepHook(Protocol):
    """Called after each agent's decision is processed.

    Args:
        agent: The agent that just decided.
        result: Broker's validation + execution result.
    """

    def __call__(
        self,
        agent: Any,
        result: SkillBrokerResult,
    ) -> None: ...


@runtime_checkable
class PostYearHook(Protocol):
    """Called after all agents have decided for the year.

    Args:
        year: Completed simulation year (1-based).
        agents: All agents keyed by agent_id.
    """

    def __call__(
        self,
        year: int,
        agents: Dict[str, Any],
    ) -> None: ...


__all__ = [
    "PreYearHook",
    "PostStepHook",
    "PostYearHook",
]
