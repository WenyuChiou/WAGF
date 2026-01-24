# Task-033 Phase 6: Social Observation Abstraction

**Assignee**: Gemini CLI
**Branch**: `task-033-phase6-social` (create from `task-033-phase1-types` after Phase 1 merges)
**Dependencies**: Phase 1 must be complete first

---

## Objective

Create an abstract social observation layer that can be adapted to any domain where peer influence matters (flood adaptation, financial decisions, educational choices, health behaviors).

---

## Deliverables

### 6.1 Social Observer Protocol

**File**: `governed_ai_sdk/v1_prototype/social/__init__.py`

```python
"""Social observation abstraction module."""
from .observer import SocialObserver, ObservationResult
from .registry import ObserverRegistry

__all__ = [
    "SocialObserver",
    "ObservationResult",
    "ObserverRegistry",
]
```

**File**: `governed_ai_sdk/v1_prototype/social/observer.py`

```python
"""Abstract base for domain-specific social observation."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime


@dataclass
class ObservationResult:
    """Result of observing a neighbor."""
    observer_id: str
    observed_id: str
    timestamp: datetime = field(default_factory=datetime.now)

    # Observable attributes (what can be seen)
    visible_attributes: Dict[str, Any] = field(default_factory=dict)

    # Observable actions (recent visible behavioral changes)
    visible_actions: List[Dict[str, Any]] = field(default_factory=list)

    # Gossip content (shared memory/stories)
    gossip: Optional[str] = None

    # Observation metadata
    relationship_strength: float = 1.0  # 0-1: how close are they?
    observation_quality: float = 1.0  # 0-1: how accurate is this observation?


class SocialObserver(ABC):
    """
    Abstract base for domain-specific social observation.

    Implement this for each domain to define what neighbors can see
    about each other. This enables peer influence modeling without
    exposing internal state.
    """

    @property
    @abstractmethod
    def domain(self) -> str:
        """Return the domain this observer handles (e.g., 'flood', 'finance')."""
        ...

    @abstractmethod
    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """
        Return attributes that neighbors can observe.

        These should be externally visible characteristics, not internal state.
        Examples:
            - Flood: house_elevated, has_insurance (visible), NOT savings amount
            - Finance: drives_new_car, owns_home (visible), NOT exact income
            - Education: enrolled_in_school, graduated (visible), NOT GPA

        Args:
            agent: The agent being observed

        Returns:
            Dictionary of observable attribute names to values
        """
        ...

    @abstractmethod
    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """
        Return recent visible behavioral changes.

        These are actions that neighbors would notice.
        Examples:
            - Flood: elevated_house, purchased_flood_insurance
            - Finance: bought_new_car, moved_to_new_house
            - Education: changed_schools, graduated

        Args:
            agent: The agent whose actions are observed

        Returns:
            List of action dictionaries with keys: action, description, timestamp
        """
        ...

    @abstractmethod
    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """
        Return shareable memory content (gossip).

        This is information the agent might share in conversation.
        Should be filtered for privacy/realism.

        Args:
            agent: The agent sharing information
            memory: Optional memory system for context

        Returns:
            Gossip string or None if nothing to share
        """
        ...

    def observe(
        self,
        observer: Any,
        observed: Any,
        relationship_strength: float = 1.0
    ) -> ObservationResult:
        """
        Perform observation of one agent by another.

        Args:
            observer: The agent doing the observing
            observed: The agent being observed
            relationship_strength: How close they are (0-1)

        Returns:
            ObservationResult with all observable information
        """
        observer_id = getattr(observer, "id", str(id(observer)))
        observed_id = getattr(observed, "id", str(id(observed)))

        return ObservationResult(
            observer_id=observer_id,
            observed_id=observed_id,
            visible_attributes=self.get_observable_attributes(observed),
            visible_actions=self.get_visible_actions(observed),
            gossip=self.get_gossip_content(observed),
            relationship_strength=relationship_strength,
        )

    def observe_neighborhood(
        self,
        observer: Any,
        neighbors: List[Any],
        relationship_map: Optional[Dict[str, float]] = None
    ) -> List[ObservationResult]:
        """
        Observe all neighbors.

        Args:
            observer: The agent doing the observing
            neighbors: List of neighbor agents
            relationship_map: Optional map of neighbor_id -> relationship_strength

        Returns:
            List of ObservationResults
        """
        results = []
        for neighbor in neighbors:
            neighbor_id = getattr(neighbor, "id", str(id(neighbor)))
            strength = 1.0
            if relationship_map:
                strength = relationship_map.get(neighbor_id, 1.0)
            results.append(self.observe(observer, neighbor, strength))
        return results
```

### 6.2 Observer Registry

**File**: `governed_ai_sdk/v1_prototype/social/registry.py`

```python
"""Registry for domain-specific social observers."""
from typing import Dict, Optional, Type
from .observer import SocialObserver


class ObserverRegistry:
    """Global registry for social observers by domain."""

    _observers: Dict[str, SocialObserver] = {}

    @classmethod
    def register(cls, observer: SocialObserver) -> None:
        """Register an observer for its domain."""
        cls._observers[observer.domain] = observer

    @classmethod
    def get(cls, domain: str) -> Optional[SocialObserver]:
        """Get observer for domain."""
        return cls._observers.get(domain)

    @classmethod
    def has(cls, domain: str) -> bool:
        """Check if domain has a registered observer."""
        return domain in cls._observers

    @classmethod
    def list_domains(cls) -> list[str]:
        """List all registered domains."""
        return list(cls._observers.keys())

    @classmethod
    def clear(cls) -> None:
        """Clear all observers (useful for testing)."""
        cls._observers.clear()
```

### 6.3 Example Domain Observers

**File**: `governed_ai_sdk/v1_prototype/social/observers/__init__.py`

```python
"""Domain-specific social observer implementations."""
from .flood_observer import FloodObserver
from .finance_observer import FinanceObserver
from .education_observer import EducationObserver

__all__ = [
    "FloodObserver",
    "FinanceObserver",
    "EducationObserver",
]
```

**File**: `governed_ai_sdk/v1_prototype/social/observers/flood_observer.py`

```python
"""Flood domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class FloodObserver(SocialObserver):
    """
    Social observer for flood adaptation domain.

    Neighbors can observe:
    - Physical changes (house elevation, flood barriers)
    - Insurance status (visible through conversations/behavior)
    - Recent flood-related actions
    """

    @property
    def domain(self) -> str:
        return "flood"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return flood-relevant visible attributes."""
        attrs = {}

        # Physical characteristics (visible)
        if hasattr(agent, "house_elevated"):
            attrs["house_elevated"] = agent.house_elevated
        if hasattr(agent, "has_flood_barriers"):
            attrs["has_flood_barriers"] = agent.has_flood_barriers
        if hasattr(agent, "flood_zone"):
            attrs["flood_zone"] = agent.flood_zone

        # Insurance status (often known in communities)
        if hasattr(agent, "has_flood_insurance"):
            attrs["has_flood_insurance"] = agent.has_flood_insurance

        # Damage history (visible after floods)
        if hasattr(agent, "flood_damage_visible"):
            attrs["flood_damage_visible"] = agent.flood_damage_visible

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent flood-related visible actions."""
        actions = []

        # Check for recent actions
        if getattr(agent, "recently_elevated", False):
            actions.append({
                "action": "elevated_house",
                "description": f"{getattr(agent, 'id', 'Agent')} elevated their house",
            })

        if getattr(agent, "recently_purchased_insurance", False):
            actions.append({
                "action": "purchased_insurance",
                "description": f"{getattr(agent, 'id', 'Agent')} purchased flood insurance",
            })

        if getattr(agent, "recently_evacuated", False):
            actions.append({
                "action": "evacuated",
                "description": f"{getattr(agent, 'id', 'Agent')} evacuated during flood warning",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return flood-related shareable content."""
        # Check for memorable flood experiences
        if hasattr(agent, "flood_experience") and agent.flood_experience:
            return f"I remember when the flood hit in {agent.flood_experience.year}..."

        if hasattr(agent, "insurance_claim_story") and agent.insurance_claim_story:
            return agent.insurance_claim_story

        return None
```

**File**: `governed_ai_sdk/v1_prototype/social/observers/finance_observer.py`

```python
"""Finance domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class FinanceObserver(SocialObserver):
    """
    Social observer for financial psychology domain.

    Neighbors can observe:
    - Lifestyle indicators (car, house, visible spending)
    - Major financial events (bankruptcy, new home, new car)
    - NOT: actual income, savings, debt amounts
    """

    @property
    def domain(self) -> str:
        return "finance"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return finance-relevant visible attributes."""
        attrs = {}

        # Lifestyle indicators (visible)
        if hasattr(agent, "owns_home"):
            attrs["owns_home"] = agent.owns_home
        if hasattr(agent, "car_type"):
            attrs["car_type"] = agent.car_type  # "luxury", "economy", "none"
        if hasattr(agent, "visible_spending_level"):
            attrs["visible_spending_level"] = agent.visible_spending_level

        # Employment status (often known)
        if hasattr(agent, "employment_status"):
            attrs["employed"] = agent.employment_status == "employed"

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent finance-related visible actions."""
        actions = []

        if getattr(agent, "recently_bought_house", False):
            actions.append({
                "action": "bought_house",
                "description": f"{getattr(agent, 'id', 'Agent')} bought a new house",
            })

        if getattr(agent, "recently_bought_car", False):
            actions.append({
                "action": "bought_car",
                "description": f"{getattr(agent, 'id', 'Agent')} bought a new car",
            })

        if getattr(agent, "declared_bankruptcy", False):
            actions.append({
                "action": "bankruptcy",
                "description": f"{getattr(agent, 'id', 'Agent')} declared bankruptcy",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return finance-related shareable content."""
        if hasattr(agent, "financial_tip") and agent.financial_tip:
            return agent.financial_tip
        return None
```

**File**: `governed_ai_sdk/v1_prototype/social/observers/education_observer.py`

```python
"""Education domain social observer."""
from typing import Any, Dict, List, Optional
from ..observer import SocialObserver


class EducationObserver(SocialObserver):
    """
    Social observer for educational psychology domain.

    Neighbors can observe:
    - Educational milestones (graduation, enrollment)
    - School choice
    - NOT: grades, test scores, internal motivation
    """

    @property
    def domain(self) -> str:
        return "education"

    def get_observable_attributes(self, agent: Any) -> Dict[str, Any]:
        """Return education-relevant visible attributes."""
        attrs = {}

        if hasattr(agent, "enrolled_in_school"):
            attrs["enrolled"] = agent.enrolled_in_school
        if hasattr(agent, "school_name"):
            attrs["school_name"] = agent.school_name
        if hasattr(agent, "highest_degree"):
            attrs["highest_degree"] = agent.highest_degree
        if hasattr(agent, "currently_studying"):
            attrs["currently_studying"] = agent.currently_studying

        return attrs

    def get_visible_actions(self, agent: Any) -> List[Dict[str, Any]]:
        """Return recent education-related visible actions."""
        actions = []

        if getattr(agent, "recently_graduated", False):
            actions.append({
                "action": "graduated",
                "description": f"{getattr(agent, 'id', 'Agent')} graduated",
            })

        if getattr(agent, "changed_major", False):
            actions.append({
                "action": "changed_major",
                "description": f"{getattr(agent, 'id', 'Agent')} changed their major",
            })

        if getattr(agent, "dropped_out", False):
            actions.append({
                "action": "dropped_out",
                "description": f"{getattr(agent, 'id', 'Agent')} dropped out of school",
            })

        return actions

    def get_gossip_content(
        self,
        agent: Any,
        memory: Optional[Any] = None
    ) -> Optional[str]:
        """Return education-related shareable content."""
        if hasattr(agent, "study_tip") and agent.study_tip:
            return agent.study_tip
        return None
```

---

## Tests

**File**: `governed_ai_sdk/tests/test_social.py`

```python
"""Tests for social observation abstraction."""
import pytest
from governed_ai_sdk.v1_prototype.social.observer import SocialObserver, ObservationResult
from governed_ai_sdk.v1_prototype.social.registry import ObserverRegistry
from governed_ai_sdk.v1_prototype.social.observers import (
    FloodObserver,
    FinanceObserver,
    EducationObserver,
)


class MockAgent:
    """Mock agent for testing."""
    def __init__(self, id: str, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)


class TestSocialObserver:
    """Tests for SocialObserver base class."""

    def test_flood_observer_attributes(self):
        """FloodObserver returns correct attributes."""
        observer = FloodObserver()
        agent = MockAgent(
            "agent1",
            house_elevated=True,
            has_flood_insurance=True,
            flood_zone="AE",
        )

        attrs = observer.get_observable_attributes(agent)
        assert attrs["house_elevated"] is True
        assert attrs["has_flood_insurance"] is True
        assert attrs["flood_zone"] == "AE"

    def test_flood_observer_actions(self):
        """FloodObserver returns visible actions."""
        observer = FloodObserver()
        agent = MockAgent(
            "agent1",
            recently_elevated=True,
            recently_purchased_insurance=False,
        )

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 1
        assert actions[0]["action"] == "elevated_house"

    def test_finance_observer(self):
        """FinanceObserver works correctly."""
        observer = FinanceObserver()
        agent = MockAgent(
            "agent1",
            owns_home=True,
            car_type="luxury",
            recently_bought_house=True,
        )

        attrs = observer.get_observable_attributes(agent)
        assert attrs["owns_home"] is True
        assert attrs["car_type"] == "luxury"

        actions = observer.get_visible_actions(agent)
        assert len(actions) == 1
        assert actions[0]["action"] == "bought_house"

    def test_observe_returns_result(self):
        """observe() returns complete ObservationResult."""
        observer = FloodObserver()
        observer_agent = MockAgent("observer1")
        observed_agent = MockAgent(
            "observed1",
            house_elevated=True,
            has_flood_insurance=False,
        )

        result = observer.observe(observer_agent, observed_agent, relationship_strength=0.8)

        assert isinstance(result, ObservationResult)
        assert result.observer_id == "observer1"
        assert result.observed_id == "observed1"
        assert result.relationship_strength == 0.8
        assert result.visible_attributes["house_elevated"] is True

    def test_observe_neighborhood(self):
        """observe_neighborhood processes multiple neighbors."""
        observer = FloodObserver()
        me = MockAgent("me")
        neighbors = [
            MockAgent("n1", house_elevated=True),
            MockAgent("n2", house_elevated=False),
            MockAgent("n3", has_flood_insurance=True),
        ]

        results = observer.observe_neighborhood(me, neighbors)
        assert len(results) == 3


class TestObserverRegistry:
    """Tests for ObserverRegistry."""

    def setup_method(self):
        """Clear registry before each test."""
        ObserverRegistry.clear()

    def test_register_and_get(self):
        """Can register and retrieve observers."""
        observer = FloodObserver()
        ObserverRegistry.register(observer)

        retrieved = ObserverRegistry.get("flood")
        assert retrieved is observer

    def test_list_domains(self):
        """Can list registered domains."""
        ObserverRegistry.register(FloodObserver())
        ObserverRegistry.register(FinanceObserver())

        domains = ObserverRegistry.list_domains()
        assert "flood" in domains
        assert "finance" in domains

    def test_has_domain(self):
        """has() works correctly."""
        assert not ObserverRegistry.has("flood")
        ObserverRegistry.register(FloodObserver())
        assert ObserverRegistry.has("flood")


class TestDomainProperty:
    """Test domain property on observers."""

    def test_flood_domain(self):
        assert FloodObserver().domain == "flood"

    def test_finance_domain(self):
        assert FinanceObserver().domain == "finance"

    def test_education_domain(self):
        assert EducationObserver().domain == "education"
```

---

## Verification

```bash
# Create branch
git checkout task-033-phase1-types
git pull
git checkout -b task-033-phase6-social

# Run tests
python -m pytest governed_ai_sdk/tests/test_social.py -v

# Verify observer pattern
python -c "
from governed_ai_sdk.v1_prototype.social import ObserverRegistry
from governed_ai_sdk.v1_prototype.social.observers import FloodObserver, FinanceObserver

# Register observers
ObserverRegistry.register(FloodObserver())
ObserverRegistry.register(FinanceObserver())

print('Registered domains:', ObserverRegistry.list_domains())

# Test observation
class Agent:
    def __init__(self, id, **kwargs):
        self.id = id
        for k, v in kwargs.items():
            setattr(self, k, v)

flood_obs = ObserverRegistry.get('flood')
agent = Agent('A1', house_elevated=True, has_flood_insurance=True)
result = flood_obs.observe(Agent('observer'), agent)
print(f'Observed {result.observed_id}: {result.visible_attributes}')
"
```

---

## Report Format

After completion, add to `.tasks/handoff/current-session.md`:

```
---
REPORT
agent: Gemini CLI
task_id: task-033-phase6
scope: governed_ai_sdk/v1_prototype/social
status: done
changes:
- governed_ai_sdk/v1_prototype/social/__init__.py (created)
- governed_ai_sdk/v1_prototype/social/observer.py (created)
- governed_ai_sdk/v1_prototype/social/registry.py (created)
- governed_ai_sdk/v1_prototype/social/observers/ (created with 3 domain observers)
tests: pytest governed_ai_sdk/tests/test_social.py -v (X passed)
artifacts: none
issues: <any issues encountered>
next: merge into task-033-phase1-types
---
```
