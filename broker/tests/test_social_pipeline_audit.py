"""Regression tests for social behavior plumbing and audit visibility."""
from broker.components.coordination.provider import MessagePoolProvider
from broker.components.coordination.messages import MessagePool
from broker.components.social.graph import create_social_graph
from broker.core._audit_helpers import _safe_social_audit
from broker.interfaces.coordination import AgentMessage
from broker.interfaces.event_generator import EventScope


def test_audit_csv_fieldnames_do_not_duplicate_construct_completeness():
    from broker.components.analytics.audit import compute_csv_fieldnames

    fieldnames = compute_csv_fieldnames([
        {"step_id": 1, "agent_id": "H001", "construct_completeness": 0.5, "construct_tp": "H"}
    ])

    assert fieldnames.count("construct_completeness") == 1
    assert "construct_tp" in fieldnames


def test_ma_reflection_falls_back_for_window_memory_engine():
    from types import SimpleNamespace

    from broker.components.memory.engines.window import WindowMemoryEngine
    from examples.multi_agent.flood.orchestration.lifecycle_hooks import MultiAgentHooks

    engine = WindowMemoryEngine(window_size=3)
    agent = SimpleNamespace(
        id="H001",
        agent_type="household_owner",
        dynamic_state={
            "flooded_this_year": False,
            "last_decision": "do_nothing",
            "has_insurance": False,
            "elevated": False,
        },
    )
    engine.add_memory(agent.id, "Year 0: initial memory")
    hooks = MultiAgentHooks({}, memory_engine=engine)

    hooks._run_ma_reflection(agent.id, 1, {agent.id: agent}, engine, flood_occurred=False)

    assert "Year 1: No flood this year." in engine.storage[agent.id]


def test_ma_window_memory_engine_builds_without_scorer_argument():
    from broker.components.memory.engines.window import WindowMemoryEngine
    from examples.multi_agent.flood.run_unified_experiment import build_memory_engine

    engine = build_memory_engine({"window_size": 2}, "window")

    assert isinstance(engine, WindowMemoryEngine)
    assert engine.window_size == 2


def test_safe_social_audit_extracts_context_for_csv_columns():
    context = {
        "local": {
            "spatial": {"neighbor_count": 2, "network_density": 0.5},
            "social": ["Neighbor H001 mentioned: 'I bought insurance.'"],
            "visible_actions": [
                {"neighbor_id": "H001", "action": "buy_insurance"},
                {"neighbor_id": "H002", "action": "elevate_house"},
                {"neighbor_id": "H003", "action": "buy_insurance"},
            ],
            "observable_attrs": {"insured": 0.5},
            "neighbor_action_summary": "Among your 2 nearby neighbors last year: 1 bought insurance.",
        }
    }

    audit = _safe_social_audit(context)

    assert audit["neighbor_count"] == 2
    assert audit["network_density"] == 0.5
    assert audit["gossip_received"] == ["Neighbor H001 mentioned: 'I bought insurance.'"]
    assert audit["visible_actions"] == {"buy_insurance": 2, "elevate_house": 1}
    assert audit["observable_attrs"] == {"insured": 0.5}
    assert audit["neighbor_action_summary"].startswith("Among your 2")


def test_message_pool_provider_appends_messages_to_local_social_context():
    graph = create_social_graph("custom", ["gov", "H001"], edge_builder=lambda ids: [])
    pool = MessagePool(social_graph=graph)
    pool.register_agent("gov")
    pool.register_agent("H001")
    pool.publish(
        AgentMessage(
            sender_id="gov",
            sender_type="government",
            message_type="policy_announcement",
            content="Subsidies increased this year.",
            recipients=["H001"],
            scope=EventScope.AGENT,
            priority=5,
        )
    )

    context = {"local": {"social": ["Existing neighbor note."]}}
    MessagePoolProvider(pool).provide("H001", {"H001": object()}, context)

    assert context["messages"][0]["content"] == "Subsidies increased this year."
    assert context["local"]["social"] == [
        "Existing neighbor note.",
        "[government policy_announcement] Subsidies increased this year.",
    ]
