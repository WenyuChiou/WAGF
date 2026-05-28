"""Phase 6T-E.B regression: subprocess gate confirming that with the
``social_feeds`` flag OFF, the SocialMediaProvider module + dedup
module are NOT loaded into ``sys.modules``.

This is the load-bearing byte-identity guard for paper-3:

1. ``UnifiedContextBuilder`` lazy-imports ``SocialMediaProvider`` inside
   ``_build_providers`` only when ``enable_social_feeds`` is True.
2. The dedup module is imported only by SocialMediaProvider + the
   Phase 6T-G test suite — never by any default broker path.

If either module loads when the flag is OFF, downstream consumers
could trigger their side effects (most notably the AST genericity
guards in ``broker/components/social/dedup.py`` could be evaluated
out of order). This test fires a fresh Python interpreter, runs a
minimal broker initialisation with flag OFF, and inspects
``sys.modules`` after the fact.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


GATE_SCRIPT = r"""
import sys

# Step 1: import broker minimally. UnifiedContextBuilder is the entry
# point that *could* import SocialMediaProvider — so importing it must
# NOT pull the provider in.
from broker.core.unified_context_builder import UnifiedContextBuilder

# Step 2: construct a builder with the flag OFF (the default).
builder = UnifiedContextBuilder(
    agents={},
    mode="single_agent",
    enable_social_feeds=False,  # explicit for clarity
)

# Step 3: collect the names of any social-media modules that landed
# in sys.modules. We DO allow:
#   - broker.components.social.post (the Post dataclass is interface
#     surface, shipped Phase 6T-E; importable freely)
#   - broker.components.social.feed_flag (the resolver is tiny + has
#     no domain coupling; safe to import even when flag OFF)
#   - broker.components.social.graph (NeighborhoodGraph / SocialGraph
#     are core social infrastructure, not 6T-E.B-specific)
#   - broker.components.social.perception (Phase 6T-E perception filter)
#   - broker.components.social.filter_registry (Phase 6B-4 social-graph filter plugins)
#   - broker.components.social.follower_network (Phase 6T-D primitive)
#   - broker.components.social.config (legacy social config — base infrastructure)
ALLOWED = {
    "broker.components.social",
    "broker.components.social.post",
    "broker.components.social.feed_flag",
    "broker.components.social.graph",
    "broker.components.social.perception",
    "broker.components.social.filter_registry",
    "broker.components.social.follower_network",
    "broker.components.social.config",
}

social_modules = sorted(
    m for m in sys.modules
    if m.startswith("broker.components.social")
)

# Step 4: assert no UNEXPECTED social module loaded. The two we
# explicitly DO NOT want to see when the flag is OFF:
#   - broker.components.social.dedup
#   - broker.components.context.providers's SocialMediaProvider class
#     (we can't easily check class-level import, but if the dedup
#     module hasn't loaded that's a strong signal)
forbidden_loaded = [m for m in social_modules if m not in ALLOWED]
assert not forbidden_loaded, (
    f"social-media modules loaded when flag OFF: {forbidden_loaded}"
)

# Step 5: confirm SocialMediaProvider class is NOT in the builder's
# provider list.
provider_class_names = [type(p).__name__ for p in builder.providers]
assert "SocialMediaProvider" not in provider_class_names, (
    f"SocialMediaProvider in providers when flag OFF: {provider_class_names}"
)

print("OK")
"""


def test_no_import_when_off():
    """Subprocess test isolates the import-state check from the rest
    of pytest's session. If this passes from a fresh interpreter,
    no other test in the suite could have pre-loaded the modules."""
    repo = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", GATE_SCRIPT],
        capture_output=True,
        text=True,
        cwd=str(repo),
        timeout=60,
    )
    assert result.returncode == 0, (
        f"gate failed (rc={result.returncode}):\n"
        f"STDOUT:\n{result.stdout}\n"
        f"STDERR:\n{result.stderr}"
    )
    # Just verify the final line is "OK" — full-success marker.
    last_nonempty = next(
        (ln for ln in reversed(result.stdout.splitlines()) if ln.strip()),
        "",
    )
    assert last_nonempty == "OK", (
        f"gate didn't print final OK; got: {result.stdout!r}"
    )
