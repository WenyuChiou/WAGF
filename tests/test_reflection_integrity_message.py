"""The missing-reflection diagnostic names the resolved reflection setting."""

import pytest

from broker.core.run_integrity import record_run_integrity


@pytest.mark.parametrize("engine_type", ["window", "humancentric"])
def test_reflection_integrity_message_names_enabled_expectation(tmp_path, capsys, engine_type):
    audit = record_run_integrity(
        tmp_path, memory_engine_type=engine_type, reflection_enabled=True,
    )
    assert audit["reflection_expected"] is True
    assert audit["integrity_ok"] is False
    assert "reflection_enabled" in capsys.readouterr().out
