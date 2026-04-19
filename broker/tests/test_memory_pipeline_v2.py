from types import SimpleNamespace

from broker.components.context.tiered import BaseAgentContextBuilder
from broker.components.memory.engines.humancentric import HumanCentricMemoryEngine
from broker.core._audit_helpers import AuditMixin
from broker.interfaces.skill_types import SkillOutcome


def build_agent(agent_id: str = "Agent_1"):
    memory_config = {
        "emotion_keywords": {
            "critical": ["flood", "damage", "loss"],
            "major": ["decision", "elevate", "relocate"],
            "positive": ["insurance", "protected"],
            "routine": [],
        },
        "emotional_weights": {
            "critical": 1.0,
            "major": 0.7,
            "positive": 0.6,
            "routine": 0.1,
        },
        "source_weights": {
            "personal": 1.0,
            "neighbor": 0.8,
            "community": 0.6,
            "abstract": 0.3,
        },
    }
    return SimpleNamespace(id=agent_id, memory_config=memory_config, memory=[])


def build_engine(ranking_mode: str = "weighted"):
    return HumanCentricMemoryEngine(
        ranking_mode=ranking_mode,
        seed=42,
        consolidation_prob=1.0,
        consolidation_threshold=0.0,
        W_recency=0.1,
        W_importance=0.9,
        W_context=0.0,
    )


class DummyWriter:
    def __init__(self):
        self.calls = []

    def write_trace(self, agent_type, trace, validation_history):
        self.calls.append((agent_type, trace, validation_history))


class DummyConfig:
    def get_log_fields(self, _agent_type):
        return []


class DummyAuditHost(AuditMixin):
    def __init__(self):
        self.audit_writer = DummyWriter()
        self.config = DummyConfig()
        self._model_name = "test-model"


def test_humancentric_retrieve_returns_dict():
    agent = build_agent()
    engine = build_engine()
    engine.add_memory_for_agent(agent, "flood caused damage", {"emotion": "critical", "importance": 0.9})
    engine.add_memory_for_agent(agent, "routine observation", {"emotion": "routine", "importance": 0.1})

    result = engine.retrieve(agent, top_k=2)

    assert isinstance(result, list)
    assert isinstance(result[0], dict)
    assert {"content", "emotion", "importance", "timestamp", "final_score"} <= set(result[0].keys())


def test_memory_write_uses_explicit_metadata():
    engine = build_engine()
    engine.add_memory("Agent_1", "plain text with no keyword", {"emotion": "critical", "importance": 0.95})

    stored = engine.working["Agent_1"][0]
    assert stored["emotion"] == "critical"
    assert stored["importance"] == 0.95


def test_context_builder_injects_salience_markers():
    builder = BaseAgentContextBuilder(
        agents={},
        prompt_templates={"household": "Past experiences:\n{memory}"},
    )
    context = {
        "agent_type": "household",
        "agent_name": "Agent_1",
        "state": {},
        "perception": {},
        "objectives": {},
        "available_skills": [],
        "memory": [
            {"content": "flood damage", "emotion": "critical", "importance": 0.9, "final_score": 0.9},
            {"content": "bought insurance", "emotion": "positive", "importance": 0.6, "final_score": 0.6},
            {"content": "no flood this year", "emotion": "routine", "importance": 0.1, "final_score": 0.1},
        ],
    }

    prompt = builder.format_prompt(context)

    # Prompt must match V1 bare-bullet format (no [TAG] markers).
    # Rationale (2026-04-19): explicit salience tags drove Gemma-3 4B
    # Y1 elevate rate 25→70% with identical memory content — small LLMs
    # over-weight prompt-structure cues. Salience is preserved via
    # retrieval ORDERING (highest importance first), not text tags.
    assert "flood damage" in prompt
    assert "bought insurance" in prompt
    assert "no flood this year" in prompt
    # No bracket markers leak into prompt
    assert "[CRITICAL]" not in prompt
    assert "[POSITIVE]" not in prompt
    assert "[ROUTINE]" not in prompt
    # Salience preserved via ORDERING (critical first, routine last)
    assert (
        prompt.index("flood damage")
        < prompt.index("bought insurance")
        < prompt.index("no flood this year")
    )


def test_audit_reads_real_emotion_from_memory_dict():
    host = DummyAuditHost()
    host._write_audit_trace(
        agent_type="household",
        context={"state": {}, "personal": {"agent_type": "household"}},
        run_id="r1",
        step_id="s1",
        timestamp="2026-04-19T00:00:00",
        env_context={"current_year": 1},
        seed=42,
        agent_id="Agent_1",
        all_valid=True,
        prompt="prompt",
        raw_output="raw",
        context_hash="hash",
        memory_pre=[{"content": "flood damage", "emotion": "critical", "importance": 0.9, "source": "personal"}],
        memory_post=[],
        skill_proposal=None,
        approved_skill=None,
        execution_result=None,
        outcome=SkillOutcome.APPROVED,
        retry_count=0,
        format_retry_count=0,
        total_llm_stats={},
        all_validation_history=[],
    )

    trace = host.audit_writer.calls[0][1]
    assert trace["memory_audit"]["memories"][0]["emotion"] == "critical"
    assert trace["memory_audit"]["memories"][0]["importance"] == 0.9


def test_critical_event_ranked_first_in_topk():
    agent = build_agent()
    engine = build_engine()
    engine.add_memory_for_agent(agent, "routine year one", {"emotion": "routine", "importance": 0.1})
    engine.add_memory_for_agent(agent, "routine year two", {"emotion": "routine", "importance": 0.1})
    engine.add_memory_for_agent(agent, "routine year three", {"emotion": "routine", "importance": 0.1})
    engine.add_memory_for_agent(agent, "routine year four", {"emotion": "routine", "importance": 0.1})
    engine.add_memory_for_agent(agent, "major flood damage", {"emotion": "critical", "importance": 0.9})

    top = engine.retrieve(agent, top_k=3)

    assert top[0]["content"] == "major flood damage"
    assert top[0]["emotion"] == "critical"


def test_backwards_compat_legacy_retrieve_caller():
    agent = build_agent()
    engine = build_engine()
    engine.add_memory_for_agent(agent, "major flood damage", {"emotion": "critical", "importance": 0.9})
    engine.add_memory_for_agent(agent, "bought insurance", {"emotion": "positive", "importance": 0.6})

    result = engine.retrieve_content_only(agent, top_k=2)

    assert result == ["major flood damage", "bought insurance"]
