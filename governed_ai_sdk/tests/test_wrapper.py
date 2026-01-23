from pathlib import Path

from governed_ai_sdk.v1_prototype.types import GovernanceTrace, PolicyRule


def test_governed_agent_passthrough():
    from governed_ai_sdk.v1_prototype.core.wrapper import (
        GovernedAgent,
        CognitiveInterceptor,
        AuditConfig,
    )

    class DummyAgent:
        def decide(self, _context):
            return {"action": "noop"}

    agent = DummyAgent()
    governed = GovernedAgent(
        backend=agent,
        interceptors=[CognitiveInterceptor()],
        state_mapping_fn=lambda a: {"id": id(a)},
        audit_config=AuditConfig(enabled=False),
    )

    result = governed.execute(context={})
    assert result.action == {"action": "noop"}
    assert result.trace.valid is True
    assert result.trace.rule_id in ("passthrough", "none")


def test_governed_agent_state_extraction():
    from governed_ai_sdk.v1_prototype.core.wrapper import GovernedAgent, CognitiveInterceptor

    class DummyAgent:
        def __init__(self):
            self.value = 42

        def decide(self, _context):
            return {"action": "noop"}

    agent = DummyAgent()
    governed = GovernedAgent(
        backend=agent,
        interceptors=[CognitiveInterceptor()],
        state_mapping_fn=lambda a: {"value": a.value},
    )

    assert governed.get_state() == {"value": 42}


def test_audit_writer_creates_file(tmp_path):
    from governed_ai_sdk.v1_prototype.audit.replay import AuditWriter

    output = tmp_path / "audit.jsonl"
    writer = AuditWriter(output_path=str(output), buffer_size=1)
    trace = GovernanceTrace(valid=True, rule_id="r1", rule_message="ok")
    writer.log(action={"action": "noop"}, state={"x": 1}, trace=trace)
    writer.close()

    assert output.exists()
    assert output.read_text(encoding="utf-8").strip()


def test_audit_reader_filters(tmp_path):
    from governed_ai_sdk.v1_prototype.audit.replay import AuditWriter, AuditReader

    output = tmp_path / "audit.jsonl"
    writer = AuditWriter(output_path=str(output), buffer_size=1, include_timestamp=False)
    writer.log(
        action={"action": "ok"},
        state={"x": 1},
        trace=GovernanceTrace(valid=True, rule_id="rule-ok", rule_message="ok"),
    )
    writer.log(
        action={"action": "blocked"},
        state={"x": 0},
        trace=GovernanceTrace(valid=False, rule_id="rule-block", rule_message="blocked"),
    )
    writer.close()

    reader = AuditReader(str(output))
    blocked = reader.filter_blocked()
    assert len(blocked) == 1
    assert blocked[0]["trace"]["rule_id"] == "rule-block"

    by_rule = reader.filter_by_rule("rule-ok")
    assert len(by_rule) == 1


def test_policy_rule_still_validates():
    rule = PolicyRule(
        id="min_savings",
        param="savings",
        operator=">=",
        value=500,
        message="Need $500",
        level="ERROR",
    )
    assert rule.id == "min_savings"
