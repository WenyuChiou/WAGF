"""Regression tests for social behavior plumbing and audit visibility."""
from broker.components.coordination.provider import MessagePoolProvider
from broker.components.coordination.messages import MessagePool
from broker.components.social.graph import create_social_graph
from broker.core._audit_helpers import _safe_social_audit
from broker.interfaces.coordination import AgentMessage
from broker.interfaces.event_generator import EventScope


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
