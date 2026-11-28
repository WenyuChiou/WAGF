"""Configuration contract for retry feedback and decision memory."""


def require_wording(key: str, value: object, supported: str) -> str:
    """Return ``supported``, ignoring case and surrounding spaces, or raise."""
    normalized = value.strip().lower() if isinstance(value, str) else value
    if normalized != supported:
        raise ValueError(
            f"{key} {value!r} is not supported: the only value is {supported!r} "
            "(the other values were retired on 2026-11-27; "
            "reproduce old runs from tag v0.7.0)."
        )
    return supported


def memory_line_style(memory) -> str:
    value = memory.get("rejection_line_style", "executed") if isinstance(memory, dict) else "executed"
    return require_wording("memory.rejection_line_style", value, "executed")
