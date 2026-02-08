"""
Governed AI SDK - Simulation Module.

Provides environment protocols for the water agent governance framework.

Note: Protocols are now defined in broker/interfaces/environment_protocols.py.
This module re-exports them for backward compatibility.
"""
# Canonical location: broker.interfaces.environment_protocols
# This module re-exports for backward compatibility
from broker.interfaces.environment_protocols import (
    EnvironmentProtocol,
    TieredEnvironmentProtocol,
    SocialEnvironmentProtocol,
)

__all__ = [
    # Protocols (re-exported from broker.interfaces)
    "EnvironmentProtocol",
    "TieredEnvironmentProtocol",
    "SocialEnvironmentProtocol",
]
