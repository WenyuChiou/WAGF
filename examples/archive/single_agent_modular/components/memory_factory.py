import warnings

warnings.warn(
    "Import from broker.components.memory_factory instead",
    DeprecationWarning,
    stacklevel=2,
)

from broker.components.memory_factory import create_memory_engine

__all__ = ["create_memory_engine"]
