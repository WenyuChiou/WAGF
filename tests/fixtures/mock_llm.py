"""
Mock LLM for deterministic testing.
Task-038: Integration Test Suite

Provides predictable responses for testing parsing, validation, and audit logic.
"""
from typing import Dict, List, Optional, Any, Callable
import json


class MockLLMResponse:
    """Represents a mock LLM response with metadata."""

    def __init__(
        self,
        content: str,
        model: str = "mock-llm",
        usage: Optional[Dict[str, int]] = None
    ):
        self.content = content
        self.model = model
        self.usage = usage or {"prompt_tokens": 100, "completion_tokens": 50}

    def __str__(self) -> str:
        return self.content


class MockLLM:
    """
    Deterministic mock LLM for testing.

    Features:
    - Configurable responses by agent_id, year, or pattern
    - Call tracking for verification
    - Support for retry scenarios
    """

    def __init__(
        self,
        responses: Optional[Dict[str, str]] = None,
        default_response: Optional[str] = None
    ):
        """
        Initialize mock LLM.

        Args:
            responses: Dict mapping keys to response strings.
                Keys can be: "agent_id", "year_N", "agent_id_year_N", or patterns.
            default_response: Fallback response if no key matches.
        """
        self.responses = responses or {}
        self.default_response = default_response or self._create_default_response()
        self.call_history: List[Dict[str, Any]] = []
        self._call_count = 0

    def _create_default_response(self) -> str:
        """Create a valid default response."""
        return '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "M", "reason": "Moderate flood risk"},
    "coping_appraisal": {"label": "M", "reason": "Some resources available"}
}
<<<DECISION_END>>>'''

    def invoke(
        self,
        prompt: str,
        agent_id: Optional[str] = None,
        year: Optional[int] = None,
        **kwargs
    ) -> MockLLMResponse:
        """
        Invoke mock LLM.

        Args:
            prompt: The prompt text (ignored for response selection).
            agent_id: Optional agent identifier for response lookup.
            year: Optional year for response lookup.
            **kwargs: Additional context.

        Returns:
            MockLLMResponse with deterministic content.
        """
        self._call_count += 1

        # Record call for verification
        self.call_history.append({
            "call_number": self._call_count,
            "prompt": prompt,
            "agent_id": agent_id,
            "year": year,
            "kwargs": kwargs
        })

        # Try to find matching response
        response_content = self._find_response(agent_id, year)

        return MockLLMResponse(content=response_content)

    def _find_response(
        self,
        agent_id: Optional[str],
        year: Optional[int]
    ) -> str:
        """Find matching response for given context."""
        # Try specific combinations first
        if agent_id and year:
            key = f"{agent_id}_year_{year}"
            if key in self.responses:
                return self.responses[key]

        # Try year-based lookup
        if year:
            key = f"year_{year}"
            if key in self.responses:
                return self.responses[key]

        # Try agent-based lookup (with wildcard support)
        if agent_id:
            if agent_id in self.responses:
                return self.responses[agent_id]
            # Check for wildcard patterns like "household_*"
            for pattern, response in self.responses.items():
                if pattern.endswith("_*") and agent_id.startswith(pattern[:-2]):
                    return response

        return self.default_response

    @property
    def call_count(self) -> int:
        """Number of times invoke was called."""
        return self._call_count

    def get_last_call(self) -> Optional[Dict[str, Any]]:
        """Get the most recent call details."""
        return self.call_history[-1] if self.call_history else None

    def reset(self) -> None:
        """Reset call history and count."""
        self.call_history.clear()
        self._call_count = 0


class MockLLMWithRetryBehavior(MockLLM):
    """
    Mock LLM that simulates retry scenarios.

    Returns different responses based on retry count.
    """

    def __init__(
        self,
        first_response: str,
        retry_response: str,
        fail_count: int = 1
    ):
        """
        Initialize mock LLM with retry behavior.

        Args:
            first_response: Response for initial attempts (may be invalid).
            retry_response: Response after fail_count failures.
            fail_count: Number of failed attempts before success.
        """
        super().__init__()
        self.first_response = first_response
        self.retry_response = retry_response
        self.fail_count = fail_count
        self._agent_retry_counts: Dict[str, int] = {}

    def invoke(
        self,
        prompt: str,
        agent_id: Optional[str] = None,
        year: Optional[int] = None,
        **kwargs
    ) -> MockLLMResponse:
        """Invoke with retry-aware response selection."""
        self._call_count += 1

        # Track per-agent retries
        key = agent_id or "default"
        current_count = self._agent_retry_counts.get(key, 0)
        self._agent_retry_counts[key] = current_count + 1

        self.call_history.append({
            "call_number": self._call_count,
            "prompt": prompt,
            "agent_id": agent_id,
            "year": year,
            "retry_count": current_count,
            "kwargs": kwargs
        })

        # Return success response after fail_count failures
        if current_count >= self.fail_count:
            return MockLLMResponse(content=self.retry_response)
        return MockLLMResponse(content=self.first_response)


# Pre-built response templates
SAMPLE_RESPONSES = {
    "valid_json_decision_1": '''<<<DECISION_START>>>
{
    "decision": 1,
    "threat_appraisal": {"label": "H", "reason": "High flood risk"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources"}
}
<<<DECISION_END>>>''',

    "valid_json_decision_2": '''<<<DECISION_START>>>
{
    "decision": 2,
    "threat_appraisal": {"label": "VH", "reason": "Very high flood risk"},
    "coping_appraisal": {"label": "H", "reason": "Good resources available"}
}
<<<DECISION_END>>>''',

    "valid_json_decision_3": '''<<<DECISION_START>>>
{
    "decision": 3,
    "threat_appraisal": {"label": "VH", "reason": "Extreme flood risk"},
    "coping_appraisal": {"label": "L", "reason": "Limited resources"}
}
<<<DECISION_END>>>''',

    "valid_json_decision_4": '''<<<DECISION_START>>>
{
    "decision": 4,
    "threat_appraisal": {"label": "L", "reason": "Low flood risk"},
    "coping_appraisal": {"label": "M", "reason": "Adequate resources"}
}
<<<DECISION_END>>>''',

    "invalid_json": '''I think I should buy insurance because the flood risk is high.
Let me analyze the situation...
My decision is 1.''',

    "qwen3_think_tags": '''<think>
Let me analyze the flood risk and my options...
The threat seems high but I have some resources.
</think>
<<<DECISION_START>>>
{"decision": 1, "threat_appraisal": {"label": "H", "reason": "High risk"}}
<<<DECISION_END>>>''',

    "naked_digit_only": '''After careful consideration of the flood risk,
I believe buying insurance is the best option.

1''',

    "uppercase_keys": '''<<<DECISION_START>>>
{
    "DECISION": 2,
    "THREAT_APPRAISAL": {"LABEL": "H", "REASON": "High risk"}
}
<<<DECISION_END>>>''',

    "keyword_fallback": '''I have decided to elevate my house because the
flood risk is very high and I want to protect my family.
elevate_house is my choice.''',

    "missing_appraisal": '''<<<DECISION_START>>>
{
    "decision": 1
}
<<<DECISION_END>>>''',

    "vl_threat_appraisal": '''<<<DECISION_START>>>
{
    "decision": 4,
    "threat_appraisal": {"label": "VL", "reason": "Very low risk"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources"}
}
<<<DECISION_END>>>''',

    "vh_threat_do_nothing": '''<<<DECISION_START>>>
{
    "decision": 4,
    "threat_appraisal": {"label": "VH", "reason": "Very high risk"},
    "coping_appraisal": {"label": "M", "reason": "Moderate resources"}
}
<<<DECISION_END>>>''',
}


def create_year_based_responses(
    years: int = 3,
    decisions: Optional[List[int]] = None,
    threat_levels: Optional[List[str]] = None
) -> Dict[str, str]:
    """
    Create year-based mock responses.

    Args:
        years: Number of years to create responses for.
        decisions: List of decision numbers (1-4) per year.
        threat_levels: List of threat levels (VL/L/M/H/VH) per year.

    Returns:
        Dict mapping "year_N" to response strings.
    """
    decisions = decisions or [1, 2, 4][:years]
    threat_levels = threat_levels or ["H", "VH", "L"][:years]

    responses = {}
    for i in range(years):
        year = i + 1
        decision = decisions[i] if i < len(decisions) else 4
        threat = threat_levels[i] if i < len(threat_levels) else "M"

        responses[f"year_{year}"] = f'''<<<DECISION_START>>>
{{
    "decision": {decision},
    "threat_appraisal": {{"label": "{threat}", "reason": "Year {year} assessment"}},
    "coping_appraisal": {{"label": "M", "reason": "Moderate resources"}}
}}
<<<DECISION_END>>>'''

    return responses
