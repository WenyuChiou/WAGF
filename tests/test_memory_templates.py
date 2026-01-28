import pytest

from broker.components.prompt_templates import MemoryTemplateProvider


def test_memory_template_provider_generates_all():
    profile = {
        "flood_experience": True,
        "flood_frequency": 2,
        "recent_flood_text": "last year",
        "flood_zone": "HIGH",
        "insurance_type": "NFIP",
        "sfha_awareness": True,
        "tenure": "Owner",
        "sc_score": 4.0,
        "sp_score": 3.5,
        "pa_score": 3.8,
        "generations": 2,
        "mg": False,
        "post_flood_action": "raised my home",
    }

    memories = MemoryTemplateProvider.generate_all(profile)
    assert len(memories) == 6
    categories = {m.category for m in memories}
    assert categories == {
        "flood_event",
        "insurance_claim",
        "social_interaction",
        "government_notice",
        "adaptation_action",
        "risk_awareness",
    }
