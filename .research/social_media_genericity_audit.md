# Social-media subsystem genericity audit + layering reference

**Status**: pre-implementation audit (genericity sections),
amended 2026-05-27 with the layering + Post-FollowerNetwork
join sections after Phase 6T-D + 6T-E shipped.

**Original purpose** (genericity): written 2026-05-27 before
Phase 6T-D opened the follower-network social graph, to lock in
the design rule that tier vocabulary lives in the DomainPack not
in broker/. Verified by `TestNoUSMediaTierLiteralsInBrokerSocial`
AST gate.

**Amendment** (2026-05-27, same day): tensions C + D from the
design-rationale review surfaced two doc gaps — (1) how
social-media propagation fits with the existing 3-tier social
model from `.research/social_tier_injection_reference.md`, and
(2) the join semantics between `Post.author_id` and
`FollowerNetwork`. Both sections added below.

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

## Layering — how social-media fits into the existing 3-tier model

The pre-Phase-6T social subsystem already defines a 3-tier
context-injection model (documented in
`.research/social_tier_injection_reference.md`):

| Tier | Scope | Topology | Example placeholders |
|---|---|---|---|
| T1 Personal | self | n/a | `{narrative_persona}`, identity block |
| T2 Local | spatial neighbours / social graph | symmetric, radius-bounded | `{neighbor_actions}`, `{gossip}` |
| T3 Global | environment-wide broadcast | flat global (one-to-all) | `{govt_message}`, `{community_status}` |

**Where does social-media propagation fit?** It is neither T2 nor T3:

| Property | T2 | T3 | Social-media propagation |
|---|---|---|---|
| Topology | symmetric spatial | flat global | **directed asymmetric** (author→follower) |
| Source weighting | uniform | single-source per channel | **per-author + per-tier credibility** |
| Retrieval | proximity-bounded | always present | **top-K weighted by `engagement × credibility × age_decay`** |
| Persistence | per-step gossip / per-year | per-step institutional state | **STICKY_YEAR_DECAY** (multi-year decay) |
| Cardinality | bounded (radius) | one channel per institution | **N-source per agent (many authors)** |

**Decision**: social-media propagation is a **new T4 tier**, NOT a
T3 sub-channel. Reasoning:

1. **Topology mismatch**: T3 is flat (every agent sees every
   global message). Follower-network requires per-agent filtering
   that doesn't fit the T3 broadcast contract.
2. **Retrieval mismatch**: T3 placeholders are unconditional
   (`{govt_message}` always renders if set). T4 retrieval is
   weighted-sampling top-K — operator chooses K, weights compose
   credibility × age × engagement.
3. **Persistence mismatch**: T3 events default EPHEMERAL
   (per-year). T4 default STICKY_YEAR_DECAY — posts survive year
   boundaries with weighted decay (per Phase 6T-D design).

**Implication for the 6T-E SocialMediaProvider** (deferred-commit
work): the provider lives ALONGSIDE the existing T3 providers
(`InstitutionalProvider`, `ObservableStateProvider`) rather than
REPLACING any. The `{social_media_feed}` placeholder is a new T4
placeholder, parallel to `{govt_message}` (T3) and `{gossip}` (T2).

**The composite prompt layout** post-6T-E.B will look roughly:

```
### IDENTITY (T1)
You are a household owner ...

### NEIGHBOURS (T2)
{neighbor_actions}
{gossip}

### COMMUNITY + INSTITUTIONS (T3)
{community_status}
{govt_message}
{insurance_message}

### SOCIAL MEDIA (T4 — Phase 6T-E.B)
{social_media_feed}
```

Domains that don't run a social-media channel return empty
`credibility_tiers()` from their PerceptionPack — the T4 layer
no-ops + the placeholder renders empty.

**Migration note**: `.research/social_tier_injection_reference.md`
should be updated to reflect the 4-tier model when 6T-E.B lands.
This audit doc is the authoritative source until then; updating the
tier reference is part of the 6T-E.B follow-up acceptance criteria.

---

## Post ↔ FollowerNetwork: ownership + join semantics

Phase 6T-E ships the `Post` dataclass (with `author_id: str`) and
Phase 6T-D shipped `FollowerNetwork` (storing `(author, follower)`
edges). These are SEPARATE primitives — broker does not enforce
that every Post's `author_id` is registered in the
FollowerNetwork. The join happens at retrieval time, when the
deferred-commit `SocialMediaProvider` walks
`env.social_feeds[author_id]` → `FollowerNetwork.get_followed(agent_id)`
→ filters to followed authors.

### Default retrieval semantics (Phase 6T-E.B target)

```python
def get_social_media_feed(agent_id: str, env, network, top_k: int = 3):
    """Phase 6T-E.B (deferred). Returns top-K posts visible to
    this agent under follower-only semantics."""
    followed_authors = set(network.get_followed(agent_id))
    candidates = []
    for author_id, posts in env.social_feeds.items():
        if author_id not in followed_authors:
            continue  # follower-only filter
        for post in posts:
            weight = (
                post.engagement_score
                * pack.credibility_weight(post.tier_id)
                * age_weight(post.event_year, env["current_year"])
            )
            if weight > 0:
                candidates.append((weight, post))
    candidates.sort(reverse=True)
    return [p for _, p in candidates[:top_k]]
```

### Three modes the operator may want

| Mode | Definition | How to express in current API |
|---|---|---|
| **Follower-only** (default) | Agent sees Posts only from authors it follows | `FollowerNetwork` has the (author, agent) edge |
| **Broadcast** | Agent sees Posts from designated "broadcast" authors regardless of follower edges (e.g. emergency-alert account) | **Domain explicitly adds the broadcast author as a follower of every agent at init** — no special API |
| **Algorithmic feed** | Agent sees Posts ranked by an engagement model that may surface non-followed content | **Future Phase 6T+ work** — not in current API. Would require a separate `algorithmic_post_score(agent, post)` PerceptionPack hook |

### Why no `broadcast: bool` flag on Post

Plausible alternative design: `Post(broadcast=True)` bypasses the
follower filter. Rejected because:

1. **Semantic creep**: `broadcast` becomes a magic field that some
   consumers honour and others don't. Easy to forget.
2. **Author-level intent**: "this author broadcasts to everyone" is
   a property of the author's role, not the individual post.
   Better expressed at the FollowerNetwork init time
   (`for agent in agents: network.add_edge(broadcast_author_id, agent.id)`).
3. **Symmetric with traditional ABM**: T3 govt_message ALSO uses
   the "always-visible to all households" pattern; it doesn't have
   a `broadcast` flag, it just IS broadcast by virtue of being in
   the T3 layer.

### What broker does NOT enforce (deliberate gaps)

1. **`Post.author_id` does NOT need to be in `FollowerNetwork`.**
   A Post with an unfollowed author_id will silently fail to reach
   anyone — this is correct semantic ("nobody follows that
   account"). The operator's domain pack is responsible for
   registering the FollowerNetwork edges that match the authors
   their event handlers emit Posts for.
2. **No author identity validation.** The same `author_id` can
   appear in multiple Post emissions; broker does not enforce that
   it corresponds to a real agent. This is by design — a domain
   may want "anonymous" or "bot account" author IDs that aren't
   real simulation agents.
3. **No duplicate detection.** If an event handler accidentally
   pushes the same Post twice into `env.social_feeds[author_id]`,
   broker treats them as two distinct posts. Domain handlers are
   responsible for idempotency.

### Cross-channel deduplication (Phase 6T-G concern)

The same underlying event (e.g. `subsidy_change`) may surface in:

1. `{inst_subsidy_rate}` (T3 institutional raw field)
2. `{govt_message}` (T3 prose narrative)
3. `{social_media_feed}` (T4 social-media post)

Phase 6T-G is planned to add `event_id` annotation + canonical
de-dup so the prompt doesn't show the same event three independent
times. The audit's "Out of scope (Phase 6U)" section called out
"Cross-channel deduplication" — but it's actually IN scope for
6T-G per the original plan. This audit doc previously did not
clarify; updated here for completeness.

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
