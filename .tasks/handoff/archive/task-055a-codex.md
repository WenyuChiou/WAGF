# Task-055A: Fix `self.config` Stale Pattern in parse_output() (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED (commit `2b05b11`, verified by Claude Code)
**Priority**: Medium
**Estimated Scope**: ~10 lines changed, 1 file + 1 test file

---

## Objective

Fix the same class of bug as the alias_map issue (Task-055): `self.config` in `parse_output()` is set once at `__init__` time for the initial `agent_type`, but `parse_output()` is called with different `agent_type` values from `context`. Two fields (`normalization`, `proximity_window`) read from `self.config` should instead read from the dynamically-loaded `parsing_cfg`.

**Impact**: In Single-Agent experiments (one agent_type), this has no effect. In Multi-Agent experiments with different parsing configs per type (e.g., `household` has `proximity_window: 35` but `trader` has `proximity_window: 50`), the wrong config would be used for the second type.

---

## Context

In `broker/utils/model_adapter.py`, `parse_output()` already dynamically loads these per `agent_type`:
- Line 216: `valid_skills = self.agent_config.get_valid_actions(agent_type)`
- Line 218: `parsing_cfg = self.agent_config.get_parsing_config(agent_type) or {}`
- Line 219: `skill_map = self.agent_config.get_skill_map(agent_type, context)`
- Line 221: `alias_map = self.agent_config.get_action_alias_map(agent_type)` (just fixed)

But these two still use the stale `self.config`:
- Line 228: `custom_mapping = self.config.get("normalization", {})`
- Line 229: `proximity_window = self.config.get("proximity_window", 35)`

---

## Changes Required

### File: `broker/utils/model_adapter.py`

**Change 1** (line 228): Replace `self.config` with `parsing_cfg`

```python
# BEFORE (line 228):
custom_mapping = self.config.get("normalization", {})

# AFTER:
custom_mapping = parsing_cfg.get("normalization", {})
```

**Change 2** (line 229): Replace `self.config` with `parsing_cfg`

```python
# BEFORE (line 229):
proximity_window = self.config.get("proximity_window", 35)

# AFTER:
proximity_window = parsing_cfg.get("proximity_window", 35)
```

---

## Verification

### 1. Add test to `tests/test_alias_normalization.py`

Add a new test class at the end of the file:

```python
class TestDynamicParsingConfig:
    """Test that parse_output() uses dynamic parsing_cfg, not stale self.config."""

    def test_proximity_window_uses_dynamic_config(self, adapter, base_context):
        """Regression: proximity_window should come from parsing_cfg, not self.config."""
        # Overwrite self.config to prove parse_output doesn't use it
        adapter.config = {"proximity_window": 999, "normalization": {"FAKE": "VALUE"}}

        raw = '<<<DECISION_START>>>{"decision": 1, "threat_appraisal": "H", "coping_appraisal": "M"}<<<DECISION_END>>>'
        result = adapter.parse_output(raw, base_context)

        # Should still parse correctly (proximity_window=999 not used)
        assert result is not None
        assert result.skill_name == "buy_insurance"
```

### 2. Run existing tests

```bash
pytest tests/test_alias_normalization.py tests/test_parse_confidence.py -v
```

All tests must pass.

### 3. Run full test suite

```bash
pytest tests/ --ignore=tests/integration --ignore=tests/manual --ignore=tests/test_vector_db.py -v
```

No new failures introduced.

---

## DO NOT

- Do NOT modify any other lines in `parse_output()`
- Do NOT change `self.config` assignment in `__init__`
- Do NOT modify any file other than `broker/utils/model_adapter.py` and `tests/test_alias_normalization.py`
