"""Regression lock for the influencer full_disclosure menu fix (commit 6d11f62).

THE BUG (Phase 6T-F, 2026-06-03): the social_media_influencer's prompt
``{options_text}`` menu rendered only 1-3 of its 4 mutually-exclusive
post-actions (amplify_event / post_counter_narrative / share_success_story /
maintain_silence), varying per year. Cause: the always-on ``SkillRetriever``
(top_n=3, min_score=0.05) relevance-truncated the four skills under the runner's
default humancentric (non-Window) memory engine — amplify_event scored highest,
maintain_silence ~0 and was dropped. With the menu missing "stay silent", a
low-salience year had no coherent option and the LLM was boxed into amplify.

THE FIX: ``parsing.full_disclosure: true`` on the influencer config, which
triggers the bypass in ``SkillRetriever.retrieve()``
(``if agent_type in self.full_disclosure_agent_types: return available_skills``).

Why this test and not a YAML-key-presence assert: a key-presence check is
brittle and never proves the bypass actually fires. These tests drive the real
``SkillRetriever`` with ``full_disclosure_agent_types`` resolved from the REAL
config, so removing the key (or breaking the retriever bypass / the config
loader) re-collapses the menu and FAILS ``test_full_disclosure_yields_all_four``
— the exact silent-regression class the fix targets, which the pre-fix suite
could not catch.
"""
from __future__ import annotations

from pathlib import Path

from broker.components.governance.registry import SkillRegistry
from broker.components.governance.retriever import SkillRetriever
from broker.utils.agent_config import AgentTypeConfig

REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_DIR = REPO_ROOT / "examples" / "multi_agent" / "flood" / "config"
INFLUENCER_CONFIG = _CONFIG_DIR / "ma_agent_types_influencer.yaml"
INFLUENCER_SKILLS = _CONFIG_DIR / "skill_registry_influencer.yaml"

# The four mutually-exclusive post-actions; ALL must reach the menu so the
# influencer can make an appraisal-driven choice (especially maintain_silence,
# the safety valve a low-salience year needs).
POST_SKILLS = [
    "amplify_event",
    "post_counter_narrative",
    "share_success_story",
    "maintain_silence",
]

# The real defaults that caused the collapse (broker/utils/agent_config.py
# get_retrieval_config) — top_n=3 alone means 4 skills CANNOT all survive
# unless the full_disclosure bypass fires first.
TOP_N = 3
MIN_SCORE = 0.05

# A flood-salient context — exactly the situation in which amplify_event
# out-scores maintain_silence, reproducing the original truncation.
FLOOD_CONTEXT = {
    "agent_type": "social_media_influencer",
    "state": {"flood_occurred": 1.0, "flood_severity": 0.9, "year": 3},
    "perception": {"threat_intensity": 0.9, "flood_event": 1.0},
}


def _post_skill_defs():
    reg = SkillRegistry()
    reg.register_from_yaml(str(INFLUENCER_SKILLS))
    defs = [reg.get(sid) for sid in POST_SKILLS]
    assert all(d is not None for d in defs), (
        "influencer skill registry must define all four post-actions"
    )
    return defs


def test_config_wires_influencer_into_full_disclosure():
    """The config-level half: the influencer agent_type must be discovered as a
    full-disclosure type. Breaks immediately if ``parsing.full_disclosure`` is
    dropped from the influencer block."""
    cfg = AgentTypeConfig.load(str(INFLUENCER_CONFIG))
    assert "social_media_influencer" in cfg.get_full_disclosure_agent_types()


def test_full_disclosure_yields_all_four():
    """The behavioral lock: with full_disclosure resolved FROM THE REAL CONFIG,
    the retriever returns ALL four post-skills despite top_n=3. If the config
    key is removed, the retriever bypass is broken, or the loader stops scanning
    ``parsing.full_disclosure``, this assertion fails — re-collapsing the menu."""
    cfg = AgentTypeConfig.load(str(INFLUENCER_CONFIG))
    retriever = SkillRetriever(
        top_n=TOP_N,
        min_score=MIN_SCORE,
        global_skills=[],
        full_disclosure_agent_types=cfg.get_full_disclosure_agent_types(),
    )
    result = retriever.retrieve(FLOOD_CONTEXT, _post_skill_defs())
    assert {s.skill_id for s in result} == set(POST_SKILLS), (
        "full_disclosure must surface all four mutually-exclusive post-actions; "
        f"got {[s.skill_id for s in result]}"
    )


def test_without_full_disclosure_menu_collapses():
    """The negative companion — proves the collapse the fix prevents is REAL (so
    ``test_full_disclosure_yields_all_four`` is genuinely exercising the bypass,
    not a no-op). On the SAME context the bypass returns 4 but the plain
    retriever returns strictly fewer: top_n=3 structurally caps a 4-skill menu.
    WHICH option is dropped is scoring/context-dependent (here
    share_success_story; in a low-salience year, maintain_silence) — that silent
    per-year variation in the menu IS the bug; full_disclosure removes it."""
    retriever = SkillRetriever(
        top_n=TOP_N,
        min_score=MIN_SCORE,
        global_skills=[],
        full_disclosure_agent_types=[],  # bypass disabled
    )
    result = retriever.retrieve(FLOOD_CONTEXT, _post_skill_defs())
    ids = {s.skill_id for s in result}
    assert len(ids) < len(POST_SKILLS), (
        "without full_disclosure the 4-skill menu must collapse (top_n=3); "
        f"got {ids}"
    )
    assert len(ids) <= TOP_N, (
        f"top_n={TOP_N} must cap the un-disclosed menu; got {len(ids)}: {ids}"
    )
