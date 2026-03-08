import inspect

from broker.interfaces import artifacts as artifacts_module


def test_artifacts_module_has_no_example_reexport_import():
    source = inspect.getsource(artifacts_module)
    assert "from examples.multi_agent.flood.protocols.artifacts" not in source


def test_broker_artifact_fallback_symbols_exist():
    assert hasattr(artifacts_module, "PolicyArtifact")
    assert hasattr(artifacts_module, "MarketArtifact")
    assert hasattr(artifacts_module, "HouseholdIntention")

    policy = artifacts_module.PolicyArtifact(
        agent_id="GOV",
        year=1,
        rationale="test",
        subsidy_rate=0.1,
    )
    assert policy.artifact_type() == "PolicyArtifact"
