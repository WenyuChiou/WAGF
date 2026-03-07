import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path("providers/smoke.py")
spec = importlib.util.spec_from_file_location("provider_smoke", MODULE_PATH)
provider_smoke = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = provider_smoke
spec.loader.exec_module(provider_smoke)


def test_cloud_provider_reports_missing_key():
    result = provider_smoke.check_provider(
        provider_name="openai",
        model="gpt-4o-mini",
        env={},
        importer=lambda _: object(),
        validator=lambda *_args, **_kwargs: True,
    )
    assert result.status == "missing_key"
    assert "OPENAI_API_KEY" in result.detail


def test_cloud_provider_reports_missing_dependency():
    result = provider_smoke.check_provider(
        provider_name="anthropic",
        model="claude-3-5-sonnet-latest",
        env={"ANTHROPIC_API_KEY": "x"},
        importer=lambda _name: (_ for _ in ()).throw(ImportError("missing")),
        validator=lambda *_args, **_kwargs: True,
    )
    assert result.status == "missing_dependency"
    assert "missing" in result.detail


def test_local_provider_uses_validator_result():
    result = provider_smoke.check_provider(
        provider_name="ollama",
        model="llama3.2:3b",
        env={},
        importer=lambda _: object(),
        validator=lambda *_args, **_kwargs: False,
    )
    assert result.status == "unreachable"


def test_local_provider_ready_when_validator_passes():
    result = provider_smoke.check_provider(
        provider_name="ollama",
        model="llama3.2:3b",
        env={},
        importer=lambda _: object(),
        validator=lambda *_args, **_kwargs: True,
    )
    assert result.status == "ready"
