# Task-059A: Context Window Token Budget Management (Codex Assignment)

**Assigned To**: Codex
**Status**: READY
**Priority**: High
**Estimated Scope**: ~120 lines new (token_utils.py), ~50 lines modified (tiered_builder.py), ~20 lines (context_providers.py), 1 test file
**Depends On**: 059-C (prompt file loading) should ideally land first, but not strictly required
**Branch**: `feat/memory-embedding-retrieval`

---

## Objective

Add intelligent context window management with per-section token budgets and graceful truncation. Currently, the system uses `len(formatted) // 4` for token estimation and hard-fails with `RuntimeError` when the prompt exceeds `max_prompt_tokens`. This task introduces:

1. A `TokenBudget` class with per-section allocation
2. A proper token counting utility (with `tiktoken` for OpenAI, `len//4` fallback for Ollama)
3. Graceful truncation instead of hard failure: truncate oldest memories first → compress social → abbreviate institutional

**Literature Basis**: MemGPT (Packer et al. 2023) — OS-inspired virtual context management with tiered memory paging. Our `TokenBudget` maps to memory page allocation.

**SA Compatibility**: SA experiments use `BaseAgentContextBuilder` which shares the same `format_prompt()` path. The change replaces the hard fail with graceful degradation — SA prompts that currently fit will continue to work identically. SA prompts that would overflow will now gracefully truncate instead of crashing.

---

## Context

### Current Code: `broker/components/tiered_builder.py`

Line 164-174: `BaseAgentContextBuilder.format_prompt()` — token estimation and hard fail:
```python
formatted = SafeFormatter().format(template, **template_vars)
token_estimate = len(formatted) // 4
if token_estimate > self.max_prompt_tokens:
    logger.warning(...)
    raise RuntimeError(
        f"Prompt token estimate {token_estimate} exceeds limit {self.max_prompt_tokens}"
    )
```

Line 440-449: `TieredContextBuilder.format_prompt()` — same pattern:
```python
formatted = SafeFormatter().format(template, **template_vars)
token_estimate = len(formatted) // 4
if token_estimate > self.max_prompt_tokens:
    logger.warning(...)
    raise RuntimeError(...)
```

### Current Code: `broker/components/context_providers.py`

Line 20-24: `ContextProvider` base class — no `max_tokens` awareness:
```python
class ContextProvider:
    def provide(self, agent_id, agents, context, **kwargs):
        pass
```

### Problem

1. `len//4` is inaccurate — can undercount by 30-50% for complex prompts
2. Hard fail is destructive — crashes the entire simulation for one agent
3. No section-level budget — all sections compete equally, causing memory to starve when institutional/social context is verbose

---

## Changes Required

### File: `broker/utils/token_utils.py` (NEW)

**Change 1:** Create token counting utility:

```python
"""Token counting and budget utilities for context window management.

Task-059A: Intelligent context window management.

References:
- MemGPT (Packer et al. 2023): OS-inspired virtual context paging
- Park et al. (2023): Importance-weighted memory retrieval under budget
"""
from typing import Dict, Optional
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

# Try tiktoken for accurate counting (OpenAI models)
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
except ImportError:
    _TIKTOKEN_AVAILABLE = False


def count_tokens(text: str, model: Optional[str] = None) -> int:
    """Count tokens in text.

    Uses tiktoken for OpenAI models, falls back to len//4 for others.

    Args:
        text: The text to count tokens for
        model: Optional model name for accurate counting

    Returns:
        Estimated token count
    """
    if not text:
        return 0

    if _TIKTOKEN_AVAILABLE and model:
        model_lower = model.lower()
        # Map model names to tiktoken encodings
        if any(k in model_lower for k in ("gpt-4", "gpt-3.5", "o1", "o3")):
            try:
                enc = tiktoken.encoding_for_model(model)
                return len(enc.encode(text))
            except Exception:
                pass

    # Fallback: len // 4 (conservative estimate for most tokenizers)
    return len(text) // 4


@dataclass
class TokenBudget:
    """Per-section token budget for context window management.

    Allocates the total token budget across context sections.
    Inspired by MemGPT's virtual memory paging concept.

    Default allocation:
    - prompt/format: 40% (base template, system prompt, response format)
    - memory: 25% (episodic + semantic memories)
    - social: 15% (neighbor gossip, social network)
    - institutional: 10% (policy, government actions)
    - reserve: 10% (buffer for template variables, safety margin)
    """
    total: int = 16384
    prompt_pct: float = 0.40
    memory_pct: float = 0.25
    social_pct: float = 0.15
    institutional_pct: float = 0.10
    reserve_pct: float = 0.10

    @property
    def prompt_budget(self) -> int:
        return int(self.total * self.prompt_pct)

    @property
    def memory_budget(self) -> int:
        return int(self.total * self.memory_pct)

    @property
    def social_budget(self) -> int:
        return int(self.total * self.social_pct)

    @property
    def institutional_budget(self) -> int:
        return int(self.total * self.institutional_pct)

    @property
    def reserve_budget(self) -> int:
        return int(self.total * self.reserve_pct)

    def section_budget(self, section: str) -> int:
        """Get budget for a named section."""
        budgets = {
            "prompt": self.prompt_budget,
            "memory": self.memory_budget,
            "social": self.social_budget,
            "institutional": self.institutional_budget,
            "reserve": self.reserve_budget,
        }
        return budgets.get(section, self.reserve_budget)


def truncate_to_budget(text: str, max_tokens: int, model: Optional[str] = None) -> str:
    """Truncate text to fit within token budget.

    Truncates from the end (preserving most recent/important content at start).

    Args:
        text: Text to truncate
        max_tokens: Maximum tokens allowed
        model: Optional model name for accurate counting

    Returns:
        Truncated text (with ... suffix if truncated)
    """
    if not text:
        return text

    current = count_tokens(text, model)
    if current <= max_tokens:
        return text

    # Binary search for optimal truncation point
    lines = text.split("\n")
    lo, hi = 0, len(lines)

    while lo < hi:
        mid = (lo + hi + 1) // 2
        candidate = "\n".join(lines[:mid])
        if count_tokens(candidate, model) <= max_tokens:
            lo = mid
        else:
            hi = mid - 1

    truncated = "\n".join(lines[:lo])
    if lo < len(lines):
        truncated += "\n... (truncated)"

    return truncated
```

### File: `broker/components/tiered_builder.py`

**Change 2:** Replace hard fail with graceful truncation in `TieredContextBuilder.format_prompt()` (lines 440-449). Replace:

```python
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Warning] Prompt exceeds limit for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens})"
            )
            raise RuntimeError(
                f"Prompt token estimate {token_estimate} exceeds limit {self.max_prompt_tokens}"
            )
        return formatted
```

With:

```python
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Budget] Prompt over budget for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens}). Truncating sections."
            )
            # Graceful truncation: trim sections in priority order
            formatted = self._truncate_to_budget(template, template_vars, self.max_prompt_tokens)
        return formatted
```

**Change 3:** Add `_truncate_to_budget()` method to `TieredContextBuilder` (after `format_prompt()`):

```python
    def _truncate_to_budget(
        self,
        template: str,
        template_vars: Dict[str, Any],
        max_tokens: int,
    ) -> str:
        """Graceful truncation when prompt exceeds budget.

        Truncation priority (least important first):
        1. social_gossip — trim to last 3 items
        2. global_news — trim to last 2 items
        3. personal_section — trim memory subsection
        4. institutional_section — abbreviate
        """
        from broker.utils.token_utils import truncate_to_budget, count_tokens

        # Stage 1: Trim social gossip
        gossip = template_vars.get("social_gossip", "")
        if gossip:
            lines = gossip.strip().split("\n")
            if len(lines) > 3:
                template_vars["social_gossip"] = "\n".join(lines[-3:])
                logger.debug("[Context:Budget] Trimmed social_gossip to 3 items")

        # Stage 2: Trim global news
        news = template_vars.get("global_news", "")
        if news:
            lines = news.strip().split("\n")
            if len(lines) > 2:
                template_vars["global_news"] = "\n".join(lines[-2:])
                logger.debug("[Context:Budget] Trimmed global_news to 2 items")

        # Stage 3: Trim institutional section
        inst = template_vars.get("institutional_section", "")
        if inst and len(inst) > 500:
            template_vars["institutional_section"] = truncate_to_budget(inst, 100)
            logger.debug("[Context:Budget] Truncated institutional section")

        # Re-format and check
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4

        if token_estimate <= max_tokens:
            return formatted

        # Stage 4: Hard truncate the formatted string
        logger.warning(
            f"[Context:Budget] Still over budget after section trimming "
            f"(~{token_estimate} tokens). Hard truncating."
        )
        # Truncate to max_tokens * 4 characters (approximate)
        max_chars = max_tokens * 4
        if len(formatted) > max_chars:
            formatted = formatted[:max_chars] + "\n... (context truncated)"

        return formatted
```

**Change 4:** Apply the same pattern to `BaseAgentContextBuilder.format_prompt()` (lines 163-174). Replace:

```python
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Warning] Prompt exceeds limit for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens})"
            )
            raise RuntimeError(
                f"Prompt token estimate {token_estimate} exceeds limit {self.max_prompt_tokens}"
            )

        return formatted
```

With:

```python
        formatted = SafeFormatter().format(template, **template_vars)
        token_estimate = len(formatted) // 4
        if token_estimate > self.max_prompt_tokens:
            logger.warning(
                f"[Context:Budget] Prompt over budget for {context.get('agent_id', 'unknown')}: "
                f"~{token_estimate} tokens (limit {self.max_prompt_tokens}). Hard truncating."
            )
            max_chars = self.max_prompt_tokens * 4
            if len(formatted) > max_chars:
                formatted = formatted[:max_chars] + "\n... (context truncated)"

        return formatted
```

### File: `broker/components/context_providers.py`

**Change 5:** Add `max_tokens` kwarg support to `MemoryProvider.provide()`. Find the `MemoryProvider` class and update its `provide()` method to accept and pass through `max_tokens`:

In the `provide()` method of `MemoryProvider`, after retrieving memories, add a budget check:

```python
        # Token budget: truncate memories if too many
        max_memory_tokens = kwargs.get("max_memory_tokens")
        if max_memory_tokens and isinstance(memory_val, list) and len(memory_val) > 3:
            from broker.utils.token_utils import count_tokens
            total_tokens = sum(count_tokens(m) for m in memory_val)
            while total_tokens > max_memory_tokens and len(memory_val) > 2:
                memory_val.pop(0)  # Remove oldest (first) memory
                total_tokens = sum(count_tokens(m) for m in memory_val)
```

---

## Verification

### 1. Add test file

**File**: `tests/test_token_budget.py`

```python
"""Tests for token counting and budget utilities (Task-059A)."""
import pytest

from broker.utils.token_utils import count_tokens, TokenBudget, truncate_to_budget


class TestCountTokens:
    """Test token counting."""

    def test_empty_string(self):
        assert count_tokens("") == 0

    def test_simple_string(self):
        tokens = count_tokens("Hello world")
        assert tokens > 0

    def test_len_div4_fallback(self):
        """Without tiktoken, should use len//4."""
        text = "a" * 100
        tokens = count_tokens(text)
        assert tokens == 25  # 100 // 4

    def test_model_none_uses_fallback(self):
        text = "Hello world, this is a test"
        tokens = count_tokens(text, model=None)
        assert tokens == len(text) // 4


class TestTokenBudget:
    """Test budget allocation."""

    def test_default_budget(self):
        budget = TokenBudget()
        assert budget.total == 16384
        assert budget.prompt_budget == 6553   # 40%
        assert budget.memory_budget == 4096   # 25%
        assert budget.social_budget == 2457   # 15%
        assert budget.institutional_budget == 1638  # 10%

    def test_custom_budget(self):
        budget = TokenBudget(total=8192, memory_pct=0.50)
        assert budget.memory_budget == 4096

    def test_section_budget_lookup(self):
        budget = TokenBudget(total=10000)
        assert budget.section_budget("memory") == 2500
        assert budget.section_budget("unknown") == budget.reserve_budget

    def test_percentages_sum_to_one(self):
        budget = TokenBudget()
        total_pct = (
            budget.prompt_pct + budget.memory_pct + budget.social_pct
            + budget.institutional_pct + budget.reserve_pct
        )
        assert abs(total_pct - 1.0) < 0.001


class TestTruncateToBudget:
    """Test truncation."""

    def test_short_text_unchanged(self):
        text = "Short text"
        result = truncate_to_budget(text, max_tokens=100)
        assert result == text

    def test_long_text_truncated(self):
        text = "\n".join([f"Line {i}" for i in range(100)])
        result = truncate_to_budget(text, max_tokens=10)
        assert len(result) < len(text)
        assert "truncated" in result

    def test_empty_text(self):
        assert truncate_to_budget("", max_tokens=10) == ""

    def test_preserves_beginning(self):
        text = "IMPORTANT FIRST LINE\n" + "\n".join([f"line {i}" for i in range(50)])
        result = truncate_to_budget(text, max_tokens=20)
        assert result.startswith("IMPORTANT FIRST LINE")


class TestGracefulTruncation:
    """Test that TieredContextBuilder no longer hard-fails."""

    def test_no_runtime_error_on_overflow(self):
        """Verify format_prompt doesn't raise RuntimeError on overflow."""
        from broker.components.tiered_builder import BaseAgentContextBuilder

        agents = {"a1": type("Agent", (), {"agent_type": "default", "name": "Test"})()}
        builder = BaseAgentContextBuilder(
            agents=agents,
            prompt_templates={"default": "{memory}"},
            max_prompt_tokens=10,  # Very small budget
        )

        context = {
            "agent_id": "a1",
            "agent_type": "default",
            "state": {},
            "perception": {},
            "objectives": {},
            "memory": ["Very long memory " * 100],
            "available_skills": [],
        }

        # Should NOT raise RuntimeError
        result = builder.format_prompt(context)
        assert isinstance(result, str)
```

### 2. Run tests

```bash
pytest tests/test_token_budget.py -v
pytest tests/test_broker_core.py -v
pytest tests/test_v3_2_features.py -v
```

All tests must pass.

---

## DO NOT

- Do NOT remove the `max_prompt_tokens` parameter from constructors — keep the interface
- Do NOT add `tiktoken` as a required dependency — it must be optional (try/except import)
- Do NOT change the provider pipeline order or KV cache optimization logic
- Do NOT modify `SystemPromptProvider` or `AttributeProvider` — only `MemoryProvider` gets the budget-aware change
- Do NOT touch SA-specific code or templates
- Do NOT change function signatures of `build()` or `format_prompt()` — only internal behavior changes
