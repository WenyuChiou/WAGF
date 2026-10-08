"""Composed event memory must refuse incompatible engine selectors at startup."""

import pytest


@pytest.mark.parametrize("engine_type", ["importance", "hierarchical", "universal", "unknown"])
def test_event_memory_5_2_1_refuses_other_selectors_before_llm(tmp_path, monkeypatch, engine_type):
    import examples.single_agent.run_flood as rf

    def unexpected_llm(*args, **kwargs):
        pytest.fail("The incompatible memory selector reached LLM setup")

    monkeypatch.setattr(rf, "create_llm_invoke", unexpected_llm)
    with pytest.raises(ValueError, match=r"event_memory_5_2_1.*window.*humancentric"):
        rf.run_parity_benchmark(
            model="mock", years=1, agents_count=1,
            custom_output=str(tmp_path / "out"), memory_engine_type=engine_type,
        )
    assert not (tmp_path / "out").exists()
