"""
Symbolic Context Engine - Re-exports from SDK for backward compatibility.

The core implementation has been moved to the SDK as part of Task-037
(SDK-Broker Architecture Separation). This module re-exports for backward
compatibility with existing broker code.

Canonical location: cognitive_governance.v1_prototype.memory.symbolic_core

Task-037: SDK Architecture Refactor
"""
import warnings

# Emit deprecation warning for direct imports
warnings.warn(
    "Importing from 'broker.components.symbolic_context' is deprecated. "
    "Please import from 'cognitive_governance.v1_prototype.memory.symbolic_core' instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from SDK canonical location
from cognitive_governance.v1_prototype.memory.symbolic_core import (
    Sensor,
    SignatureEngine,
    SymbolicContextMonitor,
    SensorConfig,  # Alias for backward compatibility
)

__all__ = [
    "Sensor",
    "SignatureEngine",
    "SymbolicContextMonitor",
    "SensorConfig",
]
