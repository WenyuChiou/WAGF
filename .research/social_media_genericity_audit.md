# Social-media subsystem genericity audit (pre-6T-D)

**Status**: pre-implementation audit doc. Written 2026-05-27 before
Phase 6T-D opens the follower-network social graph + sets the
stage for 6T-E/F.

**Trigger**: user-mandated genericity check during Phase 6T
kickoff. Reviewer concern: the Phase 6T-E plan as written puts
`Post.credibility_tier` enum literals (`OFFICIAL / VERIFIED /
INFLUENCER / PEER / BOT`) directly in
`broker/components/social/post.py`. Those tier labels are
formally generic (no flood/water words) but **semantically
US-media-shaped** — they encode the structure of US social-media
trust hierarchies (verified blue check, influencer follower
counts, bot accounts). Other domains may want different tier
vocabularies:

| Domain candidate | Plausible tier vocabulary |
|---|---|
| Vaccination ABM | `cdc / clinician / health_influencer / community_elder / whatsapp_rumor` |
| Traffic / commuter ABM | `transport_authority / news_outlet / commuter_forum / waze_user / unverified_tip` |
| Disaster early warning | `noaa / local_emergency_office / news / community_radio / streamer / rumor` |
| Misinformation research | `mainstream_journalist / activist / partisan_influencer / anonymous_account / coordinated_bot` |

If the tier labels live in `broker/`, every new domain must:

1. Bend its tier vocabulary to fit the US-media five (uncomfortable
   for vaccination ABM where "INFLUENCER" doesn't map cleanly).
2. Or fork `broker/components/social/post.py`, breaking the
   single-source-of-truth invariant.
3. Or write a translation layer between its native tiers and the
   broker's tier enum, doubling state.

None of those are acceptable. The audit's job is to lay out a
design rule that prevents the leak before 6T-E lands.

---

## Audit findings — what's generic vs US-media-shaped

### 6T-D scope (THIS sub-phase — opens follower graph primitives)

| Element | Generic? | Notes |
|---|---|---|
| `SocialGraphSpec.graph_type = "follower_network"` | ✅ generic | Just a string; the followed_by relation is universal. |
| `FollowerNetwork.add_edge(author, follower, weight)` | ✅ generic | Floats + agent IDs; no semantic tagging. |
| `FollowerNetwork.get_followers / get_followed` | ✅ generic | Directed-graph query primitives. |
| `follower_seed_fn(author_id, rng) -> List[AgentID]` | ✅ generic | Caller-provided callable; broker doesn't constrain shape. |
| `weight_fn(author_id, follower_id) -> float` | ✅ generic | Caller-provided callable. |

**6T-D is safe to ship as-is.** None of the new abstractions
introduce credibility-tier vocabulary.

### 6T-E scope (next sub-phase — Pattern B social-media propagation)

| Element | Generic risk | Required guardrail |
|---|---|---|
| `Post` dataclass fields `text / author_id / event_year / event_type / engagement_score` | ✅ generic | Standard message-channel fields. |
| **`Post.credibility_tier: Enum[OFFICIAL/VERIFIED/INFLUENCER/PEER/BOT]`** | ❌ **US-media-shaped** | **Replace with `tier_id: str`** — domain-pluggable. |
| Verbalisation strings (`"The Department of Insurance announced: ..."` for OFFICIAL etc.) | ❌ US-media-shaped | Move templates to pack (`PerceptionPack.social_media_post_verbalisation(post) -> str`). |
| `credibility_weight(tier) -> float` mapping | ⚠️ depends | Either pack-provided OR generic-default-with-override. |
| `social_media_post_filter(agent, post) -> Optional[Post]` | ✅ generic | Hook signature is fine; semantics live in pack. |

### 6T-F scope (Pattern A — influencer agent_type)

| Element | Generic risk | Required guardrail |
|---|---|---|
| New `social_media_influencer` agent_type registered in flood YAML | ✅ generic | Domain-specific agent_type in a domain config — correct location. |
| New `narrative_diffusion` framework (constructs: salience, virality, audience_fit, narrative_consistency) | ⚠️ US-discourse-shaped | These constructs ARE somewhat universal (any narrative-amplification context has them) but the construct labels are paper-3-flavoured. Acceptable if the framework registration goes through the same `register_framework_metadata` path 6T-B uses — then a vaccination_ma can register `vaccine_narrative_diffusion` with its own constructs. |
| `narrative_truthfulness`, `narrative_whiplash`, `audience_appropriateness` validators | ⚠️ paper-3-flavoured | Live in `broker/validators/governance/narrative_validators.py` per plan — move to `examples/multi_agent/flood/validators/narrative_validators.py` instead. |

---

## Design rule for 6T-E (canonical — must be followed when 6T-E lands)

**Rule**: `broker/components/social/post.py` MUST NOT carry a
hardcoded credibility-tier enum. The `Post` dataclass uses a
generic `tier_id: str` field whose vocabulary is owned by the
DomainPack.

### Required API for 6T-E

```python
# broker/components/social/post.py
@dataclass
class Post:
    text: str
    author_id: str
    author_role: str
    event_year: int
    event_type: str
    engagement_score: float
    tier_id: str  # opaque to broker — pack interprets
    # broker provides:
    #   - field shape
    #   - age_weight computation via event_year
    # broker does NOT provide:
    #   - tier vocabulary
    #   - tier → credibility_weight mapping
    #   - tier → verbalisation template
```

### New PerceptionPack methods (6T-E adds these)

```python
def credibility_tiers(self) -> List[str]:
    """Ordered tier vocabulary, highest-credibility first.
    e.g. flood: ["official_authority", "verified_account",
    "influencer", "peer", "bot"]
    Default: []
    """

def credibility_weight(self, tier_id: str) -> float:
    """Weight in [0.0, 1.0] for the perception filter's
    weighted sampling. Default: 1.0 for all known tiers,
    0.0 for unknown (so unknown tiers are filtered out).
    """

def verbalise_post(self, post: Post) -> str:
    """Domain-specific natural-language rendering for the
    {social_media_feed} prompt placeholder. Pack owns the
    template (e.g. flood: "The Department of Insurance
    announced: ..." for tier_id='official_authority').
    Default: f"[{post.tier_id}] {post.text}"
    """

def suppressed_tiers(self) -> Set[str]:
    """Tier IDs whose posts the perception filter drops by
    default (e.g. flood domain suppresses 'bot' tier).
    Operator can override per-experiment via YAML.
    Default: set()
    """
```

### Required `broker/tests/test_framework_invariants.py` addition (post-6T-E)

Add a test that AST-scans
`broker/components/social/post.py` for the forbidden literals
`"OFFICIAL" / "VERIFIED" / "INFLUENCER" / "PEER" / "BOT"`.
If any appear as enum literals, fail the build — they belong
in `examples/governed_flood/adapters/flood_perception.py` (or
wherever the FloodPerceptionMixin gets the tier list from).

---

## Why this matters — the existing pattern lives in the codebase

This audit isn't theoretical. WAGF has already paid for the
opposite design choice three times:

1. **Phase 6P-A**: `validate_all` dispatcher used to live in
   `broker/domains/water/validator_bundles.py` so generic
   broker had to reverse-import the water namespace. Phase 6P-A
   moved it to `broker/components/governance/domain_validator_dispatch.py`
   and made dispatch registry-driven.
2. **Phase 6P-E + 6Q-B**: `HazardEventGenerator` had flood-shaped
   payload schema (`depth_m`, `depth_ft`, `m → ft` conversion)
   baked into `broker/`. The Phase 6P-E follow-up audit
   relocated it to `broker.domains.water.event_generators.hazard_per_agent`
   instead of trying to fake it generic.
3. **Phase 6R-B / 6R-C**: `agent_type="household"` silent
   fallbacks in `PerceptionAwareProvider`, `get_social_spec`,
   `AgentReflectionContext` — all closed by either raising on
   missing agent_type or moving the assumption into a pack.

The `Post.credibility_tier = Enum[OFFICIAL/.../BOT]` design
would be a fourth instance of the same anti-pattern. Audit
catches it before 6T-E lands.

---

## Verification plan (Phase 6T+)

This audit doesn't generate test code by itself. It generates
**design rules** for 6T-E. The verification steps are:

1. **6T-E pre-commit checkpoint**: re-read this doc. Verify
   `broker/components/social/post.py` uses `tier_id: str` not
   an enum. Verify the four new `PerceptionPack` methods exist
   with the signatures above (or document the deviation with
   justification).
2. **6T-E post-commit AST gate**: add the
   `broker/tests/test_framework_invariants.py` rule scanning
   for the forbidden literals.
3. **Phase 6T+ (out of current scope)**: build a `fake_traffic`
   pack that overrides `credibility_tiers()` with
   `["transport_authority", "news_outlet", "commuter_forum",
   "waze_user", "unverified_tip"]` and runs through the
   propagation channel end-to-end. Proves the abstraction
   generalises beyond flood.

---

## Out-of-scope (intentionally deferred)

- **Cross-cultural trust models** (e.g. high-context vs
  low-context media trust). 6T-E tiers are a flat list; cultural
  trust modulation can layer on later via `credibility_weight`
  override per (agent_type, tier_id) pair.
- **Network-derived credibility** (e.g. inferred trust from
  follower-graph centrality, sentiment-graph echo chambers). 6T
  scope is static / pack-declared credibility. Dynamic / inferred
  trust is Phase 6U+.
- **Coordinated-inauthentic-behavior detection** (bot networks,
  astroturfing). Out of scope for the propagation substrate;
  6T-F's influencer agent_type can model SOME of this via
  `dismiss_risk` + `post_counter_narrative` skills, but a
  separate `bot_account` agent_type with high-volume
  low-credibility output is Phase 6U.
