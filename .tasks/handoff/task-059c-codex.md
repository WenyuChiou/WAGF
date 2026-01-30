# Task-059C: Config Prompt Extraction to Files (Codex Assignment)

**Assigned To**: Codex
**Status**: COMPLETED
**Priority**: High
**Estimated Scope**: ~15 lines new in agent_config.py, 4 prompt .txt files, YAML edits
**Depends On**: None (Phase 1 — can run in parallel with 059-B, 059-D)
**Branch**: `feat/memory-embedding-retrieval`

---

## Objective

Extract inline prompt templates from `ma_agent_types.yaml` into separate `.txt` files. The YAML currently has ~60% of its 621 lines as inline prompt text. After extraction, YAML will reference prompts by file path using a new `prompt_template_file` key, and `AgentTypeConfig.get_prompt_template()` will resolve file-based templates.

**SA Compatibility**: SA experiments use their own `agent_types.yaml` with inline `prompt_template:`. The fallback to inline `prompt_template` is preserved, so SA is unaffected.

---

## Context

### Current Code: `broker/utils/agent_config.py`

Line 353-356: `get_prompt_template()` only reads inline YAML:
```python
def get_prompt_template(self, agent_type: str) -> str:
    """Get prompt template."""
    cfg = self.get(agent_type)
    return cfg.get("prompt_template", "")
```

### Current YAML: `examples/multi_agent/ma_agent_types.yaml`

Each agent type has a multi-line `prompt_template:` block (typically 30-80 lines each):
```yaml
household_owner:
  prompt_template: |
    You are {agent_id}, a homeowner in a New Jersey coastal community...
    [60+ lines of prompt text]
```

There are 4 agent types with prompts: `household_owner`, `household_renter`, `government`, `insurance`.

### Problem

The YAML is hard to maintain at 621 lines with most content being prompt text. Prompt templates should be in separate files for:
1. Easier editing (IDE support for plain text, not YAML strings)
2. Version control clarity (prompt changes are separate commits)
3. Reuse across configurations

---

## Changes Required

### File: `broker/utils/agent_config.py`

**Change 1:** Update `get_prompt_template()` to support file-based templates (replace lines 353-356):

```python
    def get_prompt_template(self, agent_type: str) -> str:
        """Get prompt template, supporting both inline and file-based templates.

        Priority:
        1. prompt_template_file: Load from file path (relative to YAML location)
        2. prompt_template: Inline YAML string (legacy)
        """
        cfg = self.get(agent_type)

        # 1. Try file-based template
        template_file = cfg.get("prompt_template_file", "")
        if template_file:
            resolved = self._resolve_template_path(template_file)
            if resolved and resolved.exists():
                try:
                    return resolved.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Failed to read prompt file {resolved}: {e}")

        # 2. Fallback to inline template
        return cfg.get("prompt_template", "")
```

**Change 2:** Add `_resolve_template_path()` helper (after `get_prompt_template()`):

```python
    def _resolve_template_path(self, relative_path: str) -> Optional[Path]:
        """Resolve a template file path relative to the YAML config location.

        Args:
            relative_path: Path relative to the YAML file's directory

        Returns:
            Resolved Path object, or None if cannot resolve
        """
        if not relative_path:
            return None

        # If absolute path, use as-is
        p = Path(relative_path)
        if p.is_absolute():
            return p

        # Resolve relative to the YAML config file location
        if hasattr(self, '_yaml_path') and self._yaml_path:
            yaml_dir = Path(self._yaml_path).parent
            return yaml_dir / relative_path

        # Fallback: resolve relative to CWD
        return Path.cwd() / relative_path
```

**Change 3:** Store `_yaml_path` during loading. Update `_load_yaml()` (line 94-114) — add one line after `self._config = yaml.safe_load(f) or {}`:

```python
    def _load_yaml(self, yaml_path: str = None):
        """Load from YAML file."""
        if yaml_path is None:
            # 1. Try CWD
            cwd_path = Path.cwd() / "agent_types.yaml"
            if cwd_path.exists():
                yaml_path = cwd_path
            else:
                # 2. Fallback to package default
                yaml_path = Path(__file__).parent / "agent_types.yaml"

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            self._yaml_path = str(yaml_path)  # <-- ADD THIS LINE
        except FileNotFoundError:
            self._config = {}
            self._yaml_path = None  # <-- ADD THIS LINE
        except Exception as e:
            logger.warning(f"Failed to load config from {yaml_path}: {e}")
            self._config = {}
            self._yaml_path = None  # <-- ADD THIS LINE
```

### File: `examples/multi_agent/config/prompts/household_owner.txt` (NEW)

Extract the `prompt_template` content from `ma_agent_types.yaml` `household_owner` section. Copy the exact text between `prompt_template: |` and the next YAML key. Do NOT modify the prompt content.

### File: `examples/multi_agent/config/prompts/household_renter.txt` (NEW)

Extract from `household_renter.prompt_template`.

### File: `examples/multi_agent/config/prompts/government.txt` (NEW)

Extract from `government.prompt_template`.

### File: `examples/multi_agent/config/prompts/insurance.txt` (NEW)

Extract from `insurance.prompt_template`.

### File: `examples/multi_agent/ma_agent_types.yaml`

For each of the 4 agent types, replace:
```yaml
household_owner:
  prompt_template: |
    [60+ lines of text]
```

With:
```yaml
household_owner:
  prompt_template_file: config/prompts/household_owner.txt
```

Repeat for `household_renter`, `government`, `insurance`.

---

## Verification

### 1. Add test file

**File**: `tests/test_prompt_file_loading.py`

```python
"""Tests for file-based prompt template loading (Task-059C)."""
import pytest
import tempfile
import os
from pathlib import Path

from broker.utils.agent_config import AgentTypeConfig


class TestPromptFileLoading:
    """Test prompt_template_file resolution."""

    def _make_config(self, yaml_content: str) -> AgentTypeConfig:
        """Create a temporary config from YAML string."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            # Reset singleton
            AgentTypeConfig._instance = None
            config = AgentTypeConfig.load(f.name)
        return config, f.name

    def test_inline_template_still_works(self):
        """Inline prompt_template (legacy) should still work."""
        config, path = self._make_config("""
test_agent:
  prompt_template: "Hello {agent_id}"
""")
        try:
            result = config.get_prompt_template("test_agent")
            assert "Hello" in result
        finally:
            os.unlink(path)
            AgentTypeConfig._instance = None

    def test_file_template_loading(self):
        """prompt_template_file should load from file."""
        # Create prompt file
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as prompt_f:
            prompt_f.write("You are {agent_id}, a test agent.")
            prompt_path = prompt_f.name

        # Create YAML referencing prompt file
        yaml_content = f"""
test_agent:
  prompt_template_file: "{prompt_path}"
"""
        config, yaml_path = self._make_config(yaml_content)
        try:
            result = config.get_prompt_template("test_agent")
            assert "You are {agent_id}" in result
        finally:
            os.unlink(yaml_path)
            os.unlink(prompt_path)
            AgentTypeConfig._instance = None

    def test_file_template_relative_path(self):
        """Relative path should resolve from YAML directory."""
        tmpdir = tempfile.mkdtemp()
        prompt_dir = Path(tmpdir) / "prompts"
        prompt_dir.mkdir()

        # Write prompt file
        prompt_file = prompt_dir / "test.txt"
        prompt_file.write_text("Test prompt content", encoding="utf-8")

        # Write YAML referencing relative path
        yaml_file = Path(tmpdir) / "config.yaml"
        yaml_file.write_text("""
test_agent:
  prompt_template_file: prompts/test.txt
""", encoding="utf-8")

        AgentTypeConfig._instance = None
        config = AgentTypeConfig.load(str(yaml_file))
        try:
            result = config.get_prompt_template("test_agent")
            assert result == "Test prompt content"
        finally:
            AgentTypeConfig._instance = None
            import shutil
            shutil.rmtree(tmpdir)

    def test_file_fallback_to_inline(self):
        """If file not found, fall back to inline prompt_template."""
        config, path = self._make_config("""
test_agent:
  prompt_template_file: nonexistent/path.txt
  prompt_template: "Fallback prompt"
""")
        try:
            result = config.get_prompt_template("test_agent")
            assert result == "Fallback prompt"
        finally:
            os.unlink(path)
            AgentTypeConfig._instance = None
```

### 2. Run tests

```bash
pytest tests/test_prompt_file_loading.py -v
pytest tests/test_broker_core.py -v
pytest tests/test_memory_config.py -v
```

All tests must pass.

### 3. Verify MA prompts load correctly

```bash
python -c "
from broker.utils.agent_config import AgentTypeConfig
AgentTypeConfig._instance = None
config = AgentTypeConfig.load('examples/multi_agent/ma_agent_types.yaml')
for atype in ['household_owner', 'household_renter', 'government', 'insurance']:
    prompt = config.get_prompt_template(atype)
    print(f'{atype}: {len(prompt)} chars, starts with: {prompt[:60]}...')
    assert len(prompt) > 50, f'{atype} prompt too short!'
print('All prompts loaded successfully')
"
```

---

## Domain Wiring (Phase 3) — BOTH locations

### Location 1: `examples/multi_agent/` (MA flood case)

Steps C3-C4 as described above — extract 4 prompt files, update `ma_agent_types.yaml`.

### Location 2: `examples/governed_flood/` (SA flood case)

**C5**: `examples/governed_flood/config/prompts/household.txt` (NEW) — Extract the `household.prompt_template` from `examples/governed_flood/config/agent_types.yaml`.

**C6**: `examples/governed_flood/config/agent_types.yaml` — Replace:
```yaml
household:
  prompt_template: |
    [prompt text]
```
With:
```yaml
household:
  prompt_template_file: config/prompts/household.txt
```

**Verification**:
```bash
python -c "
from broker.utils.agent_config import AgentTypeConfig
AgentTypeConfig._instance = None
config = AgentTypeConfig.load('examples/governed_flood/config/agent_types.yaml')
prompt = config.get_prompt_template('household')
print(f'household: {len(prompt)} chars')
assert len(prompt) > 50
print('governed_flood prompt loaded successfully')
"
```

---

## DO NOT

- Do NOT modify the prompt text content — copy exactly as-is from YAML to .txt files
- Do NOT remove the `prompt_template` YAML key support — keep as fallback for other configs
- Do NOT change the singleton pattern of `AgentTypeConfig`
- Do NOT add any new dependencies

---

## Completion Notes

- **Commits**:
  - `4f0bbc2` (feat(config): load prompt templates from files)
  - `50600f2` (feat(config): extract governed_flood prompt file)
- **Files**:
  - `broker/utils/agent_config.py`
  - `examples/multi_agent/ma_agent_types.yaml`
  - `examples/multi_agent/config/prompts/household_owner.txt`
  - `examples/multi_agent/config/prompts/household_renter.txt`
  - `examples/multi_agent/config/prompts/government.txt`
  - `examples/multi_agent/config/prompts/insurance.txt`
  - `examples/governed_flood/config/agent_types.yaml`
  - `examples/governed_flood/config/prompts/household.txt`
  - `tests/test_prompt_file_loading.py`
- **Tests**: Not run in this session
