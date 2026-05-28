"""Phase 6T-E.B v0.5.1 byte-identity regression: with the social-feeds
flag OFF (paper-3 default), adding ``{social_media_feed}`` to the
flood household prompt templates produces a rendered prompt that is
byte-identical to the same template with the placeholder REMOVED
entirely.

The mechanism (v0.5.1):

* ``SocialMediaProvider`` writes ``context["social_media_feed"] = ""``
  when no posts survive filtering (or when the flag is OFF and no
  provider is in the chain at all).
* The household prompt template places ``{social_media_feed}`` FLUSH
  against the preceding placeholder (``{neighbor_action_summary}``)
  with NO template-side newlines, so ``str.format`` substituting an
  empty string at that position yields exactly the byte sequence the
  pre-v0.5.1 template (without the placeholder) produced.

This test reads the flood prompt template files, runs
``str.format`` once with ``social_media_feed=""`` and once with the
placeholder text removed entirely, and asserts the two renders are
byte-identical.
"""
from __future__ import annotations

from pathlib import Path

import pytest


PROMPT_DIR = (
    Path(__file__).resolve().parents[2]
    / "examples" / "multi_agent" / "flood" / "config" / "prompts"
)

PROMPT_FILES = ["household_owner.txt", "household_renter.txt"]


def _stub_format_kwargs(template_text: str) -> dict:
    """Build a kwargs dict that satisfies every ``{placeholder}`` in
    ``template_text`` with a deterministic dummy value. Placeholders
    whose format spec uses any of ``%``, ``d``, ``f``, ``g``, ``e``,
    ``n``, or ``,`` get a numeric default (0.0); all others get an
    empty string. This way the test stays robust as new placeholders
    are added — no hardcoded NUMERIC_HINTS set to keep in sync."""
    import re
    sanitized = template_text.replace("{{", "").replace("}}", "")
    placeholder_specs: dict = {}
    for match in re.finditer(
        r"\{([A-Za-z_][A-Za-z0-9_]*)(?::([^}]*))?\}", sanitized,
    ):
        name = match.group(1)
        spec = match.group(2) or ""
        # First-seen wins; format spec is consistent across uses in
        # these templates so this is safe.
        placeholder_specs.setdefault(name, spec)

    NUMERIC_FORMAT_CHARS = set("%dfgenx,")
    kwargs = {}
    for name, spec in placeholder_specs.items():
        if any(ch in NUMERIC_FORMAT_CHARS for ch in spec):
            kwargs[name] = 0.0
        else:
            kwargs[name] = ""
    return kwargs


@pytest.mark.parametrize("prompt_file", PROMPT_FILES)
def test_empty_social_media_feed_is_byte_identical_to_no_placeholder(prompt_file):
    """Rendering the v0.5.1 template with ``social_media_feed=""``
    produces the exact byte sequence the pre-v0.5.1 template (without
    the placeholder) would have produced. This is the load-bearing
    byte-identity guard for paper-3 v21 — any future v21 re-run under
    v0.5.1 code with the flag OFF MUST produce identical prompts."""
    path = PROMPT_DIR / prompt_file
    template = path.read_text(encoding="utf-8")

    assert "{social_media_feed}" in template, (
        f"{prompt_file}: social_media_feed placeholder missing — "
        f"v0.5.1 prompt-template change incomplete"
    )

    # Render 1: v0.5.1 template with placeholder substituted by ""
    kwargs = _stub_format_kwargs(template)
    v051_rendered = template.format(**kwargs)

    # Render 2: pre-v0.5.1 template (placeholder removed entirely)
    pre_v051_template = template.replace("{social_media_feed}", "")
    pre_v051_kwargs = _stub_format_kwargs(pre_v051_template)
    pre_v051_rendered = pre_v051_template.format(**pre_v051_kwargs)

    # Byte-identity gate
    assert v051_rendered == pre_v051_rendered, (
        f"{prompt_file}: v0.5.1 template with empty social_media_feed "
        f"is NOT byte-identical to pre-v0.5.1.\n"
        f"first diff at index "
        f"{next(i for i, (a, b) in enumerate(zip(v051_rendered, pre_v051_rendered)) if a != b)}\n"
        f"  v0.5.1 surrounding: {v051_rendered[max(0, _diff_idx(v051_rendered, pre_v051_rendered) - 30):_diff_idx(v051_rendered, pre_v051_rendered) + 30]!r}\n"
        f"  pre-v0.5.1 surrounding: {pre_v051_rendered[max(0, _diff_idx(v051_rendered, pre_v051_rendered) - 30):_diff_idx(v051_rendered, pre_v051_rendered) + 30]!r}"
    )


def _diff_idx(a: str, b: str) -> int:
    """First index where two strings differ (or min length if same prefix)."""
    for i, (ca, cb) in enumerate(zip(a, b)):
        if ca != cb:
            return i
    return min(len(a), len(b))


@pytest.mark.parametrize("prompt_file", PROMPT_FILES)
def test_non_empty_social_media_feed_injects_cleanly(prompt_file):
    """With a non-empty social_media_feed, the rendered prompt contains
    the section header + posts inline. Sanity check that the placeholder
    is wired correctly when populated."""
    path = PROMPT_DIR / prompt_file
    template = path.read_text(encoding="utf-8")
    kwargs = _stub_format_kwargs(template)
    kwargs["social_media_feed"] = (
        "\n\n## Social media (recent posts):\n"
        "- [official_authority] gov 1: subsidy announcement"
    )
    rendered = template.format(**kwargs)
    assert "## Social media (recent posts):" in rendered
    assert "subsidy announcement" in rendered
