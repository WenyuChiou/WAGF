import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


PACKAGE_DIR = (
    Path(__file__).resolve().parents[1]
    / "broker"
    / "components"
    / "prompt_templates"
)
MODULE_PATH = PACKAGE_DIR / "memory_templates.py"
SPEC = importlib.util.spec_from_file_location("prompt_templates_memory_templates_under_test", MODULE_PATH)
MEMORY_TEMPLATES_MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MEMORY_TEMPLATES_MODULE)

MemoryTemplate = MEMORY_TEMPLATES_MODULE.MemoryTemplate
# Phase 6B-2: MemoryTemplateProvider was relocated to
# broker.domains.water.flood_memory_templates and is exposed at the
# canonical memory_templates module via PEP 562 __getattr__. The
# spec-loaded module above triggers __getattr__ from the loaded copy,
# but the resolved class returns instances of the *canonical*
# MemoryTemplate, not the spec-loaded one. Use the canonical class
# for isinstance checks.
MemoryTemplateProvider = MEMORY_TEMPLATES_MODULE.MemoryTemplateProvider
from broker.components.prompt_templates.memory_templates import MemoryTemplate as _CanonicalMemoryTemplate


def test_prompt_templates_public_exports_are_declared():
    init_text = (PACKAGE_DIR / "__init__.py").read_text(encoding="utf-8")

    assert "MemoryTemplateProvider" in init_text
    assert "MemoryTemplate" in init_text
    assert "__all__" in init_text


def test_memory_template_defaults_are_stable():
    template = MemoryTemplate(content="Seed memory", category="flood_event")

    assert template.content == "Seed memory"
    assert template.category == "flood_event"
    assert template.emotion == "neutral"
    assert template.source == "personal"


def test_generate_all_returns_non_empty_templates_for_defaultish_profile():
    profile = {}

    memories = MemoryTemplateProvider.generate_all(profile)

    assert len(memories) == 6
    # Phase 6B-2: provider returns canonical MemoryTemplate instances
    assert all(isinstance(memory, _CanonicalMemoryTemplate) for memory in memories)
    assert all(memory.content.strip() for memory in memories)


def test_flood_experience_content_reflects_profile_fields():
    profile = {
        "flood_experience": True,
        "flood_frequency": 2,
        "recent_flood_text": "last year",
        "flood_zone": "HIGH",
    }

    memory = MemoryTemplateProvider.flood_experience(profile)

    assert memory.category == "flood_event"
    assert "twice" in memory.content
    assert "last year" in memory.content
    assert "high risk zone" in memory.content


def test_insurance_interaction_varies_by_profile():
    nfip_profile = {"insurance_type": "NFIP", "tenure": "Owner"}
    renter_profile = {"sfha_awareness": True, "tenure": "Renter"}

    nfip_memory = MemoryTemplateProvider.insurance_interaction(nfip_profile)
    renter_memory = MemoryTemplateProvider.insurance_interaction(renter_profile)

    assert nfip_memory.content != renter_memory.content
    assert "National Flood Insurance Program" in nfip_memory.content
    assert "renters flood insurance" in renter_memory.content


def test_generated_memory_can_be_written_to_memory_store():
    profile = {"flood_zone": "MEDIUM"}
    memory_store = MagicMock()

    memory = MemoryTemplateProvider.risk_awareness(profile)
    memory_store.add_memory(
        "agent-7",
        memory.content,
        {"category": memory.category, "emotion": memory.emotion, "source": memory.source},
    )

    memory_store.add_memory.assert_called_once_with(
        "agent-7",
        memory.content,
        {"category": "risk_awareness", "emotion": "neutral", "source": "community"},
    )
