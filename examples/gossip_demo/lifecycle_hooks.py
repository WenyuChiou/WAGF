"""Cross-agent state management for gossip_demo (Phase 6F).

Same env-dict-whitelist pattern as vaccination_ma_demo, adapted for a
social-media cycle:

    pre_year (day boundary):
      - moderator_warning_active reset
      - select today's focus_post / trending_topic from yesterday's posts
      - sync self.env -> runner env via aliasing (Phase 6E Finding #3)
        ↓
    [phase 1] platform_moderator decides → post_step writes
              moderator_warning_active + prior_moderation_label
        ↓
    [phase 2] influencer decides → post_step writes
              this cycle's posts into self._cycle_posts + sentiment
        ↓
    [phase 3] casual_user decides → post_step counts shares/likes/reports
        ↓
    post_year:
      - aggregate sentiment_trend_label
      - count pending_reports
      - pick tomorrow's trending_topic
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from broker.interfaces.skill_types import SkillOutcome


class GossipHooks:
    """Lifecycle hooks for the 3-agent-type gossip social-media demo."""

    def __init__(
        self,
        environment: Dict[str, Any],
        memory_engine: Optional[Any] = None,
    ):
        self.env = environment
        self.memory_engine = memory_engine

        # --- Cross-agent state defaults ----------------------------
        # All keys here are the SOURCE OF TRUTH for cross-agent prompt
        # placeholders. They MUST be in run_experiment.py's
        # dynamic_whitelist.
        self.env.setdefault("trending_topic_text", "no clear trend yet today")
        self.env.setdefault("sentiment_trend_label", "neutral")
        self.env.setdefault("moderator_warning_active", "no")
        self.env.setdefault("prior_moderation_label", "none")
        self.env.setdefault("focus_post_summary", "no notable post yet")
        self.env.setdefault("pending_reports_label", "none")

        # Per-cycle accumulators (reset every pre_year)
        self._cycle_posts: list[dict[str, Any]] = []
        self._cycle_reports_count = 0
        self._cycle_shares_count = 0
        self._cycle_likes_count = 0

    # ------------------------------------------------------------------
    # pre_year (day boundary)
    # ------------------------------------------------------------------

    def pre_year(self, year: int, env: Dict[str, Any], agents: Dict[str, Any]) -> None:
        """Boundary between cycles. Reset transient signals + alias env."""
        # CRITICAL — Phase 6E Finding #3 dual-dict aliasing pattern.
        # Without this, post_step writes to self.env don't reach
        # context_builder reads for later phases in the same cycle.
        env.update(self.env)
        self.env = env
        self.env["year"] = year

        # Reset per-cycle accumulators
        self._cycle_posts = []
        self._cycle_reports_count = 0
        self._cycle_shares_count = 0
        self._cycle_likes_count = 0

        # Reset transient signals that only mean something during their
        # producing phase. Yesterday's moderator_warning expires.
        self.env["moderator_warning_active"] = "no"
        self.env["focus_post_summary"] = (
            self.env.get("yesterday_top_post_summary", "no notable post from yesterday")
        )

    # ------------------------------------------------------------------
    # post_step
    # ------------------------------------------------------------------

    def post_step(self, agent: Any, result: Any) -> None:
        """Route by agent_type. Reads EXECUTED decision (Phase 6E P1)."""
        if result.outcome not in (SkillOutcome.APPROVED, SkillOutcome.RETRY_SUCCESS):
            if hasattr(agent, "dynamic_state"):
                agent.dynamic_state["last_decision"] = "fallback"
            return

        decision = result.approved_skill.skill_name

        if agent.agent_type == "platform_moderator":
            self._handle_moderator(decision, agent)
        elif agent.agent_type == "influencer":
            self._handle_influencer(decision, agent)
        elif agent.agent_type == "casual_user":
            self._handle_user(decision, agent)

    def _handle_moderator(self, decision: str, agent: Any) -> None:
        """Moderator decisions set platform-wide signal."""
        if decision == "warn_community":
            self.env["moderator_warning_active"] = "yes"
            self.env["prior_moderation_label"] = "warning_issued"
        elif decision == "boost_signal":
            self.env["prior_moderation_label"] = "boosted_trending"
        elif decision == "demote_misinfo":
            self.env["prior_moderation_label"] = "demoted_misinformation"
        else:
            self.env["prior_moderation_label"] = "none"

        if hasattr(agent, "dynamic_state"):
            agent.dynamic_state["last_decision"] = decision

    def _handle_influencer(self, decision: str, agent: Any) -> None:
        """Influencer decisions create today's content pool."""
        if decision == "post_polarizing":
            self._cycle_posts.append({
                "author": agent.id, "type": "polarizing",
                "summary": f"{agent.id} posted polarizing content",
            })
            # Polarizing posts push sentiment to extreme
            self.env["sentiment_trend_label"] = "polarized"
        elif decision == "post_neutral":
            self._cycle_posts.append({
                "author": agent.id, "type": "neutral",
                "summary": f"{agent.id} posted neutral content",
            })
        elif decision == "share_trending":
            self._cycle_posts.append({
                "author": agent.id, "type": "share",
                "summary": f"{agent.id} amplified trending topic",
            })

        # Update focus_post_summary so casual_users see something this cycle
        if self._cycle_posts:
            latest = self._cycle_posts[-1]
            self.env["focus_post_summary"] = (
                f"A {latest['type']} post by {latest['author']} is gaining traction."
            )

        if hasattr(agent, "dynamic_state"):
            agent.dynamic_state["last_decision"] = decision

    def _handle_user(self, decision: str, agent: Any) -> None:
        """Casual user engagement aggregates into report/share/like counts."""
        if decision == "share":
            self._cycle_shares_count += 1
        elif decision == "like":
            self._cycle_likes_count += 1
        elif decision == "report":
            self._cycle_reports_count += 1

        # Update pending_reports_label so moderator next cycle sees aggregate
        if self._cycle_reports_count >= 3:
            self.env["pending_reports_label"] = "high"
        elif self._cycle_reports_count >= 1:
            self.env["pending_reports_label"] = "low"

        if hasattr(agent, "dynamic_state"):
            agent.dynamic_state["last_decision"] = decision

    # ------------------------------------------------------------------
    # post_year — aggregate for next cycle
    # ------------------------------------------------------------------

    def post_year(
        self, year: int, agents: Dict[str, Any], memory_engine: Optional[Any] = None
    ) -> None:
        """End-of-cycle aggregation. Picks tomorrow's trending topic."""
        # Aggregate sentiment from posts + engagement
        polarizing = sum(1 for p in self._cycle_posts if p["type"] == "polarizing")
        neutral = sum(1 for p in self._cycle_posts if p["type"] == "neutral")
        shares = self._cycle_shares_count
        likes = self._cycle_likes_count

        if polarizing >= 2 and self._cycle_reports_count >= 2:
            self.env["sentiment_trend_label"] = "polarized"
        elif likes > shares * 2:
            self.env["sentiment_trend_label"] = "warm"
        elif shares >= 3:
            self.env["sentiment_trend_label"] = "amplifying"
        else:
            self.env["sentiment_trend_label"] = "neutral"

        # Pick tomorrow's trending topic from today's most-shared/liked
        if self._cycle_posts:
            top = self._cycle_posts[0]  # naive: first post wins
            self.env["yesterday_top_post_summary"] = top["summary"]
            self.env["trending_topic_text"] = (
                f"a {top['type']} post by {top['author']}"
            )
        else:
            self.env["yesterday_top_post_summary"] = "no posts yesterday"
            self.env["trending_topic_text"] = "no clear trend today"
