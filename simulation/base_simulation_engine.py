"""
Generic Base Simulation Engine.

Defines the contract for the "Running Model" layer in the framework.
"""
from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass

from broker.skill_types import ApprovedSkill, ExecutionResult

@dataclass
class BaseSimulationEngine(ABC):
    """
    Abstract Base Class for Simulation Engines.
    
    The Simulation Engine is responsible for:
    1. Managing World State (Time, Environment)
    2. Executing Approved Skills (State Transitions)
    3. Advancing Time Steps
    
    It serves as the execution substrate for the Governed Broker.
    """
    
    @abstractmethod
    def execute_skill(self, approved_skill: ApprovedSkill) -> ExecutionResult:
        """
        Execute an APPROVED skill.
        This is the only way state should change based on agent decisions.
        """
        pass
    
    @abstractmethod
    def advance_step(self) -> Any:
        """
        Advance the simulation by one step (e.g., year, tick).
        Updates environment, triggers events, etc.
        """
        pass
