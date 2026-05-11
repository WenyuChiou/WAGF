# gossip_demo — social-media multi-agent reference (Phase 6F, 2026-05-11)

The third non-water reference example proving WAGF's multi-agent path
is domain-generic. Built using **only Paper 3's proven feature set** —
**zero broker changes required**.

| | |
|---|---|
| Pattern | Paper 3-style multi-agent: institutional → intermediary → citizen |
| Domain | Community social-media simulation (NextDoor / neighborhood Facebook model) |
| Agent types | 1× `platform_moderator` + K× `influencer` + N× `casual_user` |
| Cadence | Daily ("year" = day reinterpretation, weekly reflection interval) |
| Cross-agent channel | env-dict-whitelist (7 keys), Tier 1 broadcast |
| Coupling pattern | Phase 6E env-dict aliasing in pre_year (`self.env = env`) |

## Three agent types

| Type | Skills | Role |
|---|---|---|
| `platform_moderator` | `boost_signal`, `demote_misinfo`, `warn_community`, `do_nothing` | Sets platform-wide moderation signal each day |
| `influencer` | `post_neutral`, `post_polarizing`, `share_trending`, `stay_silent` | Produces today's content; the `focus_post_summary` casual_users see |
| `casual_user` | `share`, `like`, `ignore`, `report` | Aggregates today's engagement (reports → next-day moderator pressure) |

## Cross-agent state (the env-dict-whitelist)

`run_experiment.py:DYNAMIC_WHITELIST` declares 7 keys. `lifecycle_hooks.py`
writes them per-phase. Every prompt template references them as
`{placeholder}` substitutions. SafeFormatter auto-fills at runtime.

| Key | Producer phase | Consumed by |
|---|---|---|
| `year` | runner | all 3 prompts (shown as day) |
| `trending_topic_text` | post_year (yesterday's top post) | INF + USR |
| `sentiment_trend_label` | post_year aggregate | MOD + INF + USR |
| `moderator_warning_active` | MOD post_step | INF + USR |
| `prior_moderation_label` | MOD post_step | MOD reflection + INF |
| `focus_post_summary` | INF post_step | USR |
| `pending_reports_label` | USR post_step | MOD (next day) |

This is exactly the Phase 6E vaccination_ma_demo pattern, only the
domain semantics differ.

## Quick start

```bash
# Validate schema
python -m broker.tools.validate_prompt examples/gossip_demo/config/agent_types.yaml

# Smoke run (2 days, 1 MOD + 1 INF + 2 USR = 8 traces, ~2 min wallclock with gemma3:1b)
python examples/gossip_demo/run_experiment.py \
    --model gemma3:1b --days 2 --users 2 --influencers 1 --seed 42 \
    --output examples/gossip_demo/results/smoke_42

# Bigger smoke (5 days, 1 MOD + 2 INF + 5 USR = 40 traces, ~10 min)
python examples/gossip_demo/run_experiment.py \
    --model gemma3:1b --days 5 --users 5 --influencers 2 --seed 42
```

Expected output: audit CSVs auto-split per agent type, all APPROVED,
cross-agent state visible in prompts (verify via raw trace inspection).

## What this PROVES (Phase 6F verdict)

The Tier 1 envelope (institutional → intermediary → citizen, broadcast
comm, ≤200 agents, env-dict-whitelist) covers **community
social-media** as cleanly as it covered vaccination_ma_demo and Paper 3
flood. The pattern is genuinely domain-agnostic.

Specifically validated this build:
- 3 agent types via `with_phase_order` (proven generic since Phase 6E)
- Daily cadence (year→day) with weekly reflection interval (`interval=7`)
- Higher memory decay rate (0.15) for short news cycles
- No InteractionHub / no spatial graph (broadcast-only) — works for
  generic "all users see platform-wide signal" pattern

## What this does NOT prove (Tier 2/3 still open)

- Directed follower graph (A→B without B→A) — would need broker
  `DirectedSocialGraph` (~2-3 hr broker work; Phase 6G if pursued)
- Per-user feed visibility (each user sees different posts) —
  Tier 2 with InteractionHub + SpatialNeighborhoodGraph (proven for
  vaccination_ma but not yet for gossip)
- Power-law influencer reach (some influencers reach 10K, others 50) —
  needs per-agent radius (Phase 6E G1b API supports it; untested here)
- Dynamic follow/unfollow during simulation — runtime mutation API
  exists (proven by Paper 3's `_prune_agent_from_graph`) but not
  exercised here
- 30-day × 100-user scale — proven for vaccination_ma 4 days; this is
  a 2-day × 4-agent smoke. LLM cost analysis recommended before scale-up.

## Reference

- `.ai/` Phase 6F findings (gitignored, local working memo)
- `examples/vaccination_ma_demo/` — Phase 6E canonical multi-agent reference
- `examples/multi_agent/flood/` — Paper 3 production-scale flood
- `.claude/skills/wagf-domain-builder/references/multi_agent_walkthrough.md` —
  the canonical multi-agent S5 reference; this demo follows it exactly
