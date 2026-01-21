"""
Media Information Channels
Simulates information diffusion through news and social media.

Design based on literature review findings:
- News media: Delayed, simplified, high reliability, regional reach
- Social media: Immediate, exaggerated, variable reliability, local reach
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import random


@dataclass
class MediaMessage:
    """A message from a media channel."""
    source: str  # "news", "social_media", "gossip"
    content: str
    timestamp: int  # Year when message becomes available
    reliability: float  # 0-1 accuracy/trustworthiness
    reach: str  # "local", "regional", "global"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_prompt_string(self) -> str:
        """Format message for inclusion in agent prompts."""
        if self.source == "news":
            return f"[NEWS] {self.content}"
        if self.source == "social_media":
            return f"[SOCIAL] {self.content}"
        return self.content


class MediaChannel(ABC):
    """Abstract base class for media channels."""

    @abstractmethod
    def broadcast(self, event: Dict, year: int) -> List[MediaMessage]:
        """Generate messages based on event."""
        raise NotImplementedError

    @abstractmethod
    def get_messages_for_agent(self, agent_id: str, year: int) -> List[MediaMessage]:
        """Get relevant messages for an agent."""
        raise NotImplementedError


class NewsMediaChannel(MediaChannel):
    """Delayed, simplified news channel with high reliability."""

    def __init__(self, delay_turns: int = 1, seed: int = 42):
        self.delay_turns = delay_turns
        self.rng = random.Random(seed)
        self.message_queue: Dict[int, List[MediaMessage]] = {}

    def broadcast(self, event: Dict, year: int) -> List[MediaMessage]:
        messages = []

        if event.get("flood_occurred"):
            depth_m = event.get("flood_depth_m", 0)
            severity = self._classify_severity(depth_m)
            affected = event.get("affected_households", "multiple")

            msg = MediaMessage(
                source="news",
                content=self._generate_news_report(severity, depth_m, affected, year),
                timestamp=year + self.delay_turns,
                reliability=0.9,
                reach="regional",
                metadata={
                    "event_type": "flood",
                    "severity": severity,
                    "actual_depth_m": depth_m,
                    "source_year": year,
                }
            )
            messages.append(msg)

            delivery_year = year + self.delay_turns
            self.message_queue.setdefault(delivery_year, []).append(msg)

        if event.get("govt_message"):
            msg = MediaMessage(
                source="news",
                content=f"GOVERNMENT NOTICE: {event['govt_message']}",
                timestamp=year,
                reliability=0.95,
                reach="regional",
                metadata={"event_type": "government_announcement"}
            )
            messages.append(msg)
            self.message_queue.setdefault(year, []).append(msg)

        return messages

    def get_messages_for_agent(self, agent_id: str, year: int) -> List[MediaMessage]:
        return self.message_queue.get(year, [])

    def _classify_severity(self, depth_m: float) -> str:
        if depth_m >= 1.5:
            return "catastrophic"
        if depth_m >= 1.0:
            return "severe"
        if depth_m >= 0.5:
            return "moderate"
        if depth_m > 0:
            return "minor"
        return "none"

    def _generate_news_report(self, severity: str, depth_m: float, affected: Any, year: int) -> str:
        templates = {
            "catastrophic": [
                f"BREAKING: Catastrophic flooding hits Passaic River Basin. "
                f"Water levels exceeded {depth_m:.1f}m in some areas. "
                f"Emergency services urge immediate evacuation.",
                f"DISASTER ALERT: Record flooding devastates communities. "
                f"Officials declare state of emergency.",
            ],
            "severe": [
                f"FLOOD WARNING: Severe flooding reported across the region. "
                f"Water depths reaching {depth_m:.1f}m. Residents advised to move to higher ground.",
                f"Major flooding impacts {affected} households. "
                f"First-floor inundation reported in flood-prone areas.",
            ],
            "moderate": [
                f"FLOOD ADVISORY: Moderate flooding affecting low-lying areas. "
                f"Water levels at approximately {depth_m:.1f}m. Exercise caution.",
                f"Flood waters rising in the basin. {affected} properties impacted. "
                f"Residents encouraged to review flood preparedness plans.",
            ],
            "minor": [
                f"Weather Update: Minor flooding observed in some areas. "
                f"Water levels at {depth_m:.1f}m. Monitor local conditions.",
                f"Light flooding reported. Most roads remain passable. "
                f"Stay alert for changing conditions.",
            ],
        }
        return self.rng.choice(templates.get(severity, templates["minor"]))


class SocialMediaChannel(MediaChannel):
    """Immediate, variable reliability social media channel."""

    def __init__(self, reach_multiplier: float = 3.0, exaggeration_factor: float = 0.3, seed: int = 42):
        self.reach_multiplier = reach_multiplier
        self.exaggeration_factor = exaggeration_factor
        self.rng = random.Random(seed)
        self.current_messages: Dict[int, List[MediaMessage]] = {}
        self.agent_posts: Dict[str, List[MediaMessage]] = {}

    def broadcast(self, event: Dict, year: int) -> List[MediaMessage]:
        messages = []
        if event.get("flood_occurred"):
            base_depth = event.get("flood_depth_m", 0)
            num_posts = self.rng.randint(3, 7)
            for _ in range(num_posts):
                variation = 1.0 + self.rng.uniform(-self.exaggeration_factor, self.exaggeration_factor * 2)
                reported_depth = base_depth * variation
                tone = self.rng.choice(["alarming", "concerned", "matter-of-fact", "dismissive"])
                content = self._generate_social_post(reported_depth, tone)
                msg = MediaMessage(
                    source="social_media",
                    content=content,
                    timestamp=year,
                    reliability=self.rng.uniform(0.4, 0.8),
                    reach="local",
                    metadata={
                        "tone": tone,
                        "reported_depth_m": round(reported_depth, 2),
                        "actual_depth_m": base_depth,
                        "exaggeration_ratio": round(variation, 2),
                    }
                )
                messages.append(msg)
            self.current_messages[year] = messages
        return messages

    def add_agent_post(self, agent_id: str, content: str, year: int, importance: float = 0.5):
        if agent_id not in self.agent_posts:
            self.agent_posts[agent_id] = []
        msg = MediaMessage(
            source="social_media",
            content=f"A neighbor shared: {content}",
            timestamp=year,
            reliability=0.6,
            reach="local",
            metadata={"author": agent_id, "importance": importance}
        )
        self.agent_posts[agent_id].append(msg)
        self.current_messages.setdefault(year, []).append(msg)

    def get_messages_for_agent(self, agent_id: str, year: int, max_messages: int = 3) -> List[MediaMessage]:
        available = [m for m in self.current_messages.get(year, []) if m.metadata.get("author") != agent_id]
        if not available:
            return []
        return self.rng.sample(available, min(len(available), max_messages))

    def _generate_social_post(self, depth_m: float, tone: str) -> str:
        depth_ft = depth_m * 3.28084
        templates = {
            "alarming": [
                f"FLOODING EMERGENCY! Water levels reaching {depth_ft:.1f}ft! Stay safe everyone!",
                f"This is BAD. Never seen water this high ({depth_m:.1f}m). Evacuate if you can!",
                f"Our street is completely underwater! {depth_ft:.0f} feet of water at least!",
            ],
            "concerned": [
                f"Significant flooding in our area (~{depth_m:.1f}m). Check on elderly neighbors.",
                f"Water is rising, about {depth_ft:.1f}ft now. Time to move valuables upstairs.",
                f"Flooding worse than expected. Already {depth_m:.1f}m deep. Be careful out there.",
            ],
            "matter-of-fact": [
                f"Flood depth measured at {depth_m:.1f}m on my property. Documenting for insurance.",
                f"River flooding as expected. Current depth approximately {depth_ft:.1f}ft.",
                f"Monitoring water levels: {depth_m:.2f}m. Consistent with forecasts.",
            ],
            "dismissive": [
                f"Only about {depth_ft:.1f}ft of water. We've seen worse. Don't panic.",
                f"Minor flooding, maybe {depth_m:.1f}m. Media always overreacts.",
                f"Just a bit of water. Nothing my sandbags can't handle.",
            ],
        }
        return self.rng.choice(templates.get(tone, templates["matter-of-fact"]))


class MediaHub:
    """Central hub managing all media channels."""

    def __init__(self, enable_news: bool = True, enable_social: bool = True, news_delay: int = 1, seed: int = 42):
        self.channels: Dict[str, MediaChannel] = {}
        if enable_news:
            self.channels["news"] = NewsMediaChannel(delay_turns=news_delay, seed=seed)
        if enable_social:
            self.channels["social_media"] = SocialMediaChannel(seed=seed + 1)

    def broadcast_event(self, event: Dict, year: int) -> Dict[str, List[MediaMessage]]:
        results = {}
        for name, channel in self.channels.items():
            results[name] = channel.broadcast(event, year)
        return results

    def get_media_context(self, agent_id: str, year: int, channel_types: Optional[List[str]] = None, max_per_channel: int = 3) -> Dict[str, List[str]]:
        channel_types = channel_types or list(self.channels.keys())
        context = {}
        for ch_type in channel_types:
            if ch_type in self.channels:
                messages = self.channels[ch_type].get_messages_for_agent(agent_id, year)
                context[ch_type] = [m.to_prompt_string() for m in messages[:max_per_channel]]
            else:
                context[ch_type] = []
        return context

    def get_media_context_formatted(self, agent_id: str, year: int) -> str:
        context = self.get_media_context(agent_id, year)
        sections = []
        news = context.get("news", [])
        if news:
            sections.append("**Recent News:**")
            sections.extend([f"  - {msg}" for msg in news])
        social = context.get("social_media", [])
        if social:
            sections.append("**Social Media Posts:**")
            sections.extend([f"  - {msg}" for msg in social])
        return "\n".join(sections) if sections else "(No media updates)"

    def summary(self) -> Dict[str, Any]:
        return {
            "channels_enabled": list(self.channels.keys()),
            "news_enabled": "news" in self.channels,
            "social_enabled": "social_media" in self.channels,
        }
