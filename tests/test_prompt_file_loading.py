"""Tests for file-based prompt template loading (Task-059C)."""
import os
import tempfile
from pathlib import Path

from broker.utils.agent_config import AgentTypeConfig


class TestPromptFileLoading:
    """Test prompt_template_file resolution."""

    def _make_config(self, yaml_content: str):
        """Create a temporary config from YAML string."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            f.flush()
            AgentTypeConfig._instance = None
            config = AgentTypeConfig.load(f.name)
        return config, f.name

    def test_inline_template_still_works(self):
        """Inline prompt_template (legacy) should still work."""
        config, path = self._make_config(
            """
            test_agent:
              prompt_template: "Hello {agent_id}"
            """
        )
        try:
            result = config.get_prompt_template("test_agent")
            assert "Hello" in result
        finally:
            os.unlink(path)
            AgentTypeConfig._instance = None

    def test_file_template_loading(self):
        """prompt_template_file should load from file."""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as prompt_f:
            prompt_f.write("You are {agent_id}, a test agent.")
            prompt_path = prompt_f.name

        yaml_content = f"""
        test_agent:
          prompt_template_file: '{prompt_path}'
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
        tmpdir = Path(tempfile.mkdtemp())
        prompt_dir = tmpdir / "prompts"
        prompt_dir.mkdir()

        prompt_file = prompt_dir / "test.txt"
        prompt_file.write_text("Test prompt content", encoding="utf-8")

        yaml_file = tmpdir / "config.yaml"
        yaml_file.write_text(
            """
            test_agent:
              prompt_template_file: prompts/test.txt
            """,
            encoding="utf-8",
        )

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
        config, path = self._make_config(
            """
            test_agent:
              prompt_template_file: nonexistent/path.txt
              prompt_template: "Fallback prompt"
            """
        )
        try:
            result = config.get_prompt_template("test_agent")
            assert result == "Fallback prompt"
        finally:
            os.unlink(path)
            AgentTypeConfig._instance = None
