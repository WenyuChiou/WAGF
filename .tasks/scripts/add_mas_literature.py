#!/usr/bin/env python3
"""
Add MAS (Multi-Agent Systems) Five-Layer Architecture Literature to Zotero.

Task-052A: Literature supplementation for MAS framework verification.

Usage:
    pip install pyzotero
    python .tasks/scripts/add_mas_literature.py
"""

import os
from typing import Dict, List, Optional

try:
    from pyzotero import zotero
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero")
    exit(1)


# Configuration
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hLGhkxO20sXiKpMF62mGDeG2")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "14772686")
ZOTERO_LIBRARY_TYPE = "user"


def create_zotero_client():
    """Create Zotero API client."""
    return zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def add_journal_article(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    journal: str,
    year: str,
    volume: str = "",
    issue: str = "",
    pages: str = "",
    doi: str = "",
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
) -> Optional[str]:
    """Add a journal article to Zotero."""
    template = zot.item_template("journalArticle")

    template["title"] = title
    template["publicationTitle"] = journal
    template["date"] = year
    template["volume"] = volume
    template["issue"] = issue
    template["pages"] = pages
    template["DOI"] = doi
    template["abstractNote"] = abstract

    template["creators"] = [
        {"creatorType": "author", "firstName": a.get("firstName", ""), "lastName": a.get("lastName", "")}
        for a in authors
    ]

    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:60]}... (key: {item_key})")

            if note:
                add_note_to_item(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed to create: {title}")
            print(f"        {response.get('failed', {})}")
            return None
    except Exception as e:
        print(f"[ERROR] Exception: {e}")
        return None


def add_preprint(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    repository: str,
    archive_id: str,
    year: str,
    url: str = "",
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
) -> Optional[str]:
    """Add a preprint (arXiv, etc.) to Zotero."""
    template = zot.item_template("preprint")

    template["title"] = title
    template["repository"] = repository
    template["archiveID"] = archive_id
    template["date"] = year
    template["abstractNote"] = abstract
    template["url"] = url or (f"https://arxiv.org/abs/{archive_id}" if repository == "arXiv" else "")

    template["creators"] = [
        {"creatorType": "author", "firstName": a.get("firstName", ""), "lastName": a.get("lastName", "")}
        for a in authors
    ]

    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:60]}... (key: {item_key})")

            if note:
                add_note_to_item(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed to create: {title}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def add_book(
    zot,
    title: str,
    authors: List[Dict[str, str]],
    publisher: str,
    year: str,
    place: str = "",
    isbn: str = "",
    abstract: str = "",
    tags: List[str] = None,
    note: str = "",
) -> Optional[str]:
    """Add a book to Zotero."""
    template = zot.item_template("book")

    template["title"] = title
    template["publisher"] = publisher
    template["date"] = year
    template["place"] = place
    template["ISBN"] = isbn
    template["abstractNote"] = abstract

    template["creators"] = [
        {"creatorType": "author", "firstName": a.get("firstName", ""), "lastName": a.get("lastName", "")}
        for a in authors
    ]

    if tags:
        template["tags"] = [{"tag": t} for t in tags]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            item_key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created: {title[:60]}... (key: {item_key})")

            if note:
                add_note_to_item(zot, item_key, note)

            return item_key
        else:
            print(f"[ERROR] Failed to create: {title}")
            return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def add_note_to_item(zot, item_key: str, note_content: str) -> bool:
    """Add a note to an existing Zotero item."""
    note_template = zot.item_template("note")
    # Wrap in HTML if not already
    if not note_content.strip().startswith("<"):
        note_content = f"<p>{note_content}</p>"
    note_template["note"] = note_content
    note_template["parentItem"] = item_key

    try:
        response = zot.create_items([note_template])
        if response.get("successful"):
            print(f"       Note added to {item_key}")
            return True
        else:
            print(f"       Failed to add note: {response.get('failed', {})}")
            return False
    except Exception as e:
        print(f"       Note error: {e}")
        return False


# =============================================================================
# MAS Framework Literature
# =============================================================================

def add_action_layer_literature(zot):
    """Add Action Layer (Memory, Reflection, Planning) literature."""
    print("\n" + "=" * 60)
    print("ACTION LAYER Literature")
    print("=" * 60)

    # 1. Generative Agents (Park et al. 2023) - Core reference
    add_preprint(
        zot,
        title="Generative Agents: Interactive Simulacra of Human Behavior",
        authors=[
            {"firstName": "Joon Sung", "lastName": "Park"},
            {"firstName": "Joseph C.", "lastName": "O'Brien"},
            {"firstName": "Carrie J.", "lastName": "Cai"},
            {"firstName": "Meredith Ringel", "lastName": "Morris"},
            {"firstName": "Percy", "lastName": "Liang"},
            {"firstName": "Michael S.", "lastName": "Bernstein"},
        ],
        repository="arXiv",
        archive_id="2304.03442",
        year="2023",
        abstract="Believable proxies of human behavior can empower interactive applications. This paper introduces generative agents—computational software agents that simulate believable human behavior. We demonstrate an architecture that extends a large language model to store a complete record of the agent's experiences, synthesize those memories over time into higher-level reflections, and retrieve them dynamically to plan behavior.",
        tags=["Task-052", "MAS-Architecture", "Action-Layer", "Memory", "Reflection", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> Action Layer - Memory Stream, Reflection</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Memory Stream: Complete record of agent experiences</li>
<li>Reflection: Synthesize memories into higher-level insights</li>
<li>Retrieval: Recency × Importance × Relevance scoring</li>
<li>Planning: Daily plans with recursive decomposition</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>CognitiveMemory → Memory Stream</li>
<li>ReflectionEngine → Reflection mechanism</li>
<li>MemoryEngine.retrieve() → Retrieval function</li>
</ul>""",
    )

    # 2. A-MEM (2025) - Already added via Task-050
    # Key: MR5G4RII - just update tags if needed

    # 3. MemGPT (2023)
    add_preprint(
        zot,
        title="MemGPT: Towards LLMs as Operating Systems",
        authors=[
            {"firstName": "Charles", "lastName": "Packer"},
            {"firstName": "Vivian", "lastName": "Fang"},
            {"firstName": "Shishir G.", "lastName": "Patil"},
            {"firstName": "Kevin", "lastName": "Lin"},
            {"firstName": "Sarah", "lastName": "Wooders"},
            {"firstName": "Joseph E.", "lastName": "Gonzalez"},
        ],
        repository="arXiv",
        archive_id="2310.08560",
        year="2023",
        abstract="Large language models (LLMs) have revolutionized AI, but are constrained by limited context windows. We propose MemGPT, a system that intelligently manages memory tiers to provide the appearance of unbounded context within fixed context LLMs. MemGPT uses interrupts to manage control flow between itself and the user.",
        tags=["Task-052", "MAS-Architecture", "Action-Layer", "Memory", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> Action Layer - Hierarchical Memory</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Tiered Memory: Main context / Archival / Recall</li>
<li>Self-directed memory management</li>
<li>Paging mechanism (virtual memory analogy)</li>
<li>Function calling for memory operations</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>CognitiveMemory.working → Main context</li>
<li>CognitiveMemory.episodic → Archival storage</li>
<li>MemoryEngine.retrieve() → Recall mechanism</li>
</ul>""",
    )

    # 4. Toolformer / Tool Use (Schick et al. 2023)
    add_preprint(
        zot,
        title="Toolformer: Language Models Can Teach Themselves to Use Tools",
        authors=[
            {"firstName": "Timo", "lastName": "Schick"},
            {"firstName": "Jane", "lastName": "Dwivedi-Yu"},
            {"firstName": "Roberto", "lastName": "Dessì"},
            {"firstName": "Roberta", "lastName": "Raileanu"},
            {"firstName": "Maria", "lastName": "Lomeli"},
            {"firstName": "Luke", "lastName": "Zettlemoyer"},
            {"firstName": "Nicola", "lastName": "Cancedda"},
            {"firstName": "Thomas", "lastName": "Scialom"},
        ],
        repository="arXiv",
        archive_id="2302.04761",
        year="2023",
        abstract="Language models (LMs) exhibit remarkable abilities to solve new tasks from just a few examples. However, they still struggle with basic functionality, such as arithmetic or factual lookup. We show that LMs can teach themselves to use external tools via simple APIs, achieving substantially improved zero-shot performance.",
        tags=["Task-052", "MAS-Architecture", "Action-Layer", "Tool-Use", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> Action Layer - Skill/Tool Use</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Self-supervised tool learning</li>
<li>API-based tool integration</li>
<li>Tool selection based on context</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>SkillRegistry → Tool definitions</li>
<li>SkillRetriever → Tool selection</li>
<li>SkillBrokerEngine → Tool execution validation</li>
</ul>""",
    )


def add_state_layer_literature(zot):
    """Add State Layer literature."""
    print("\n" + "=" * 60)
    print("STATE LAYER Literature")
    print("=" * 60)

    # 1. AgentTorch (2024)
    add_preprint(
        zot,
        title="AgentTorch: A Framework for Agent-Based Modeling with Automatic Differentiation",
        authors=[
            {"firstName": "Ayush", "lastName": "Chopra"},
            {"firstName": "Ramesh", "lastName": "Raskar"},
        ],
        repository="arXiv",
        archive_id="2401.10345",
        year="2024",
        abstract="Agent-based models (ABMs) are a powerful tool for simulating complex systems. We introduce AgentTorch, a framework that combines ABMs with automatic differentiation, enabling gradient-based optimization of agent behaviors and system parameters.",
        tags=["Task-052", "MAS-Architecture", "State-Layer", "ABM", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> State Layer - Entity Separation</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>S_Ag (Agents), S_Ob (Objects), S_Env (Environment) separation</li>
<li>Differentiable agent-based modeling</li>
<li>Scalable simulation architecture</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>HouseholdAgentState, GovernmentAgentState → S_Ag</li>
<li>TPState, SocialNetwork → S_Ob</li>
<li>FloodEvent, DamageResult → S_Env</li>
</ul>""",
    )

    # 2. PMT (Rogers 1975)
    add_journal_article(
        zot,
        title="A protection motivation theory of fear appeals and attitude change",
        authors=[{"firstName": "Ronald W.", "lastName": "Rogers"}],
        journal="The Journal of Psychology",
        year="1975",
        volume="91",
        issue="1",
        pages="93-114",
        doi="10.1080/00223980.1975.9915803",
        abstract="Protection Motivation Theory proposes that the motivation to protect oneself from danger is determined by threat appraisal and coping appraisal processes.",
        tags=["Task-052", "MAS-Architecture", "State-Layer", "PMT", "Psychology", "Household"],
        note="""<p><strong>Applied in Task-052:</strong> State Layer - HouseholdAgentState</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Threat Appraisal (TP): Perceived vulnerability × severity</li>
<li>Coping Appraisal (CP): Self-efficacy × response efficacy - response costs</li>
<li>Protection Motivation → Adaptive behavior</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>TP_LABEL, CP_LABEL → PMT constructs in agent state</li>
<li>GovernanceRules → PMT-based decision validation</li>
<li>TPDecayEngine → Temporal dynamics of threat perception</li>
</ul>""",
    )

    # 3. Bubeck et al. (2012) - Flood risk perception
    add_journal_article(
        zot,
        title="A review of risk perceptions and other factors that influence flood mitigation behavior",
        authors=[
            {"firstName": "Philip", "lastName": "Bubeck"},
            {"firstName": "Willem J.W.", "lastName": "Botzen"},
            {"firstName": "Jeroen C.J.H.", "lastName": "Aerts"},
        ],
        journal="Risk Analysis",
        year="2012",
        volume="32",
        issue="9",
        pages="1481-1495",
        doi="10.1111/j.1539-6924.2012.01832.x",
        abstract="This paper reviews empirical studies on flood risk perceptions and their relation to flood mitigation behavior. We identify key factors that influence protective behavior and discuss implications for flood risk management.",
        tags=["Task-052", "MAS-Architecture", "State-Layer", "Flood-Risk", "PMT", "Behavior"],
        note="""<p><strong>Applied in Task-052:</strong> State Layer - TPState, Risk Perception</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Risk perception factors in flood contexts</li>
<li>PMT application to flood mitigation</li>
<li>Temporal decay of risk perception post-flood</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>TPDecayEngine → Risk perception decay curves</li>
<li>VulnerabilityCalculator → Perceived vulnerability</li>
</ul>""",
    )


def add_observation_layer_literature(zot):
    """Add Observation Layer literature."""
    print("\n" + "=" * 60)
    print("OBSERVATION LAYER Literature")
    print("=" * 60)

    # 1. Bounded Rationality (Simon 1955)
    add_journal_article(
        zot,
        title="A behavioral model of rational choice",
        authors=[{"firstName": "Herbert A.", "lastName": "Simon"}],
        journal="The Quarterly Journal of Economics",
        year="1955",
        volume="69",
        issue="1",
        pages="99-118",
        doi="10.2307/1884852",
        abstract="This paper presents a model of rational choice that takes into account the limitations of human cognitive capacity. The concept of 'satisficing' is introduced as an alternative to optimization under bounded rationality.",
        tags=["Task-052", "MAS-Architecture", "Observation-Layer", "Bounded-Rationality", "Psychology"],
        note="""<p><strong>Applied in Task-052:</strong> Observation Layer - PerceptionFilter</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Bounded rationality: Limited cognitive capacity</li>
<li>Satisficing: Acceptable vs. optimal solutions</li>
<li>Information filtering due to cognitive constraints</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>PerceptionFilter → Bounded observation</li>
<li>HouseholdPerceptionFilter → Qualitative vs. quantitative perception</li>
<li>CognitiveConstraints → Miller/Cowan memory limits</li>
</ul>""",
    )

    # 2. POMDP (Kaelbling et al. 1998)
    add_journal_article(
        zot,
        title="Planning and acting in partially observable stochastic domains",
        authors=[
            {"firstName": "Leslie Pack", "lastName": "Kaelbling"},
            {"firstName": "Michael L.", "lastName": "Littman"},
            {"firstName": "Anthony R.", "lastName": "Cassandra"},
        ],
        journal="Artificial Intelligence",
        year="1998",
        volume="101",
        issue="1-2",
        pages="99-134",
        doi="10.1016/S0004-3702(98)00023-X",
        abstract="This paper presents a comprehensive treatment of planning under uncertainty in partially observable stochastic domains (POMDPs). We describe the formal model and present algorithms for finding optimal policies.",
        tags=["Task-052", "MAS-Architecture", "Observation-Layer", "POMDP", "Partial-Observability"],
        note="""<p><strong>Applied in Task-052:</strong> Observation Layer - Partial Observability</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Partial observability formalization</li>
<li>Belief state representation</li>
<li>Observation function O(s, a, o)</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>ObservableScope → Observation constraints</li>
<li>ObservableStateManager → Belief state management</li>
<li>ContextBuilder → Observation to prompt conversion</li>
</ul>""",
    )


def add_transition_layer_literature(zot):
    """Add Transition Layer literature."""
    print("\n" + "=" * 60)
    print("TRANSITION LAYER Literature")
    print("=" * 60)

    # 1. Concordia (Google DeepMind 2023)
    add_preprint(
        zot,
        title="Concordia: A Library for Building Multi-agent Simulations",
        authors=[
            {"firstName": "Alexander", "lastName": "Vezhnevets"},
            {"firstName": "John P.", "lastName": "Agapiou"},
            {"firstName": "Joel Z.", "lastName": "Leibo"},
        ],
        repository="arXiv",
        archive_id="2312.03664",
        year="2023",
        url="https://arxiv.org/abs/2312.03664",
        abstract="Concordia is a library for building generative model-based multi-agent simulations. It provides a framework for creating agents with language-based cognition and a game master that mediates interactions between agents and the environment.",
        tags=["Task-052", "MAS-Architecture", "Transition-Layer", "Game-Master", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> Transition Layer - Game Master, Action Resolution</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Game Master (GM): Mediates agent-environment interactions</li>
<li>Action resolution: GM interprets and executes agent actions</li>
<li>Grounded variables: Code-maintained state vs. LLM-generated</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>SkillBrokerEngine → Action validation (partial GM)</li>
<li>SimulationEngine.execute_skill() → Action execution</li>
<li>ExperimentRunner._apply_state_changes() → State transition</li>
</ul>""",
    )

    # 2. ABM Methodology (Gilbert 2019)
    add_book(
        zot,
        title="Agent-Based Models",
        authors=[{"firstName": "Nigel", "lastName": "Gilbert"}],
        publisher="SAGE Publications",
        year="2019",
        place="London",
        isbn="978-1526403308",
        abstract="This book provides a comprehensive introduction to agent-based modeling, covering the methodology, implementation, and analysis of ABMs across various domains.",
        tags=["Task-052", "MAS-Architecture", "Transition-Layer", "ABM", "Methodology"],
        note="""<p><strong>Applied in Task-052:</strong> Transition Layer - Event-driven ABM</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>ABM design principles</li>
<li>Event-driven simulation patterns</li>
<li>Agent interaction protocols</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>EventGenerators → Event-driven architecture</li>
<li>ExperimentRunner → Simulation execution</li>
</ul>""",
    )


def add_communication_layer_literature(zot):
    """Add Communication Layer literature."""
    print("\n" + "=" * 60)
    print("COMMUNICATION LAYER Literature")
    print("=" * 60)

    # 1. MetaGPT (2023)
    add_preprint(
        zot,
        title="MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework",
        authors=[
            {"firstName": "Sirui", "lastName": "Hong"},
            {"firstName": "Mingchen", "lastName": "Zhuge"},
            {"firstName": "Jonathan", "lastName": "Chen"},
            {"firstName": "Xiawu", "lastName": "Zheng"},
            {"firstName": "Yuheng", "lastName": "Cheng"},
            {"firstName": "Ceyao", "lastName": "Zhang"},
        ],
        repository="arXiv",
        archive_id="2308.00352",
        year="2023",
        abstract="MetaGPT takes a one-line requirement as input and outputs user stories, competitive analysis, requirements, data structures, APIs, documents, etc. MetaGPT encodes SOPs into prompt sequences for more streamlined workflows.",
        tags=["Task-052", "MAS-Architecture", "Communication-Layer", "Multi-Agent", "LLM-Agent"],
        note="""<p><strong>Applied in Task-052:</strong> Communication Layer - Pub-Sub Messaging</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Shared Message Pool for multi-agent communication</li>
<li>Publish-Subscribe pattern</li>
<li>Role-based message routing</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>MAEventManager → Event broadcasting</li>
<li>EventScope → Message visibility</li>
<li>(Gap: No explicit Pub-Sub, events are pushed)</li>
</ul>""",
    )

    # 2. Social Learning (Bandura 1977)
    add_book(
        zot,
        title="Social Learning Theory",
        authors=[{"firstName": "Albert", "lastName": "Bandura"}],
        publisher="Prentice Hall",
        year="1977",
        place="Englewood Cliffs, NJ",
        isbn="978-0138167448",
        abstract="This book presents Bandura's social learning theory, which emphasizes the importance of observing and modeling the behaviors, attitudes, and emotional reactions of others.",
        tags=["Task-052", "MAS-Architecture", "Communication-Layer", "Social-Learning", "Psychology"],
        note="""<p><strong>Applied in Task-052:</strong> Communication Layer - Social Interaction</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Observational learning</li>
<li>Modeling behavior from others</li>
<li>Social reinforcement</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>InteractionHub.get_visible_neighbor_actions() → Observation of others</li>
<li>SocialGraph → Social network for learning</li>
<li>SocialProvider → Social context in prompts</li>
</ul>""",
    )

    # 3. Network Science (Barabási 2016)
    add_book(
        zot,
        title="Network Science",
        authors=[{"firstName": "Albert-László", "lastName": "Barabási"}],
        publisher="Cambridge University Press",
        year="2016",
        place="Cambridge",
        isbn="978-1107076266",
        abstract="This textbook introduces the science of networks, covering the mathematical foundations, real-world applications, and the structure and dynamics of complex networks.",
        tags=["Task-052", "MAS-Architecture", "Communication-Layer", "Network-Science", "Social-Network"],
        note="""<p><strong>Applied in Task-052:</strong> Communication Layer - Network Topology</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Network topology types (random, scale-free, small-world)</li>
<li>Network metrics (centrality, clustering)</li>
<li>Information diffusion on networks</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>SocialGraph topologies → Network types</li>
<li>SpatialNeighborhoodGraph → Spatial networks</li>
<li>neighbor_pct calculation → Network influence</li>
</ul>""",
    )

    # 4. Multi-Agent Systems (Wooldridge 2009)
    add_book(
        zot,
        title="An Introduction to MultiAgent Systems",
        authors=[{"firstName": "Michael", "lastName": "Wooldridge"}],
        publisher="Wiley",
        year="2009",
        place="Chichester",
        isbn="978-0470519462",
        abstract="This book provides a comprehensive introduction to multi-agent systems, covering agent architectures, multi-agent interactions, and applications.",
        tags=["Task-052", "MAS-Architecture", "Communication-Layer", "Multi-Agent", "Coordination"],
        note="""<p><strong>Applied in Task-052:</strong> Communication Layer - Multi-Agent Coordination</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Agent communication languages</li>
<li>Coordination mechanisms</li>
<li>Negotiation and cooperation</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>MAEventManager → Coordination mechanism</li>
<li>EventPhase → Synchronization</li>
<li>ThreadPoolExecutor → Parallel execution</li>
</ul>""",
    )


def main():
    """Add all MAS framework literature."""
    zot = create_zotero_client()

    print("=" * 60)
    print("Task-052A: Adding MAS Five-Layer Architecture Literature")
    print("=" * 60)

    # Add literature by layer
    add_state_layer_literature(zot)
    add_observation_layer_literature(zot)
    add_action_layer_literature(zot)
    add_transition_layer_literature(zot)
    add_communication_layer_literature(zot)

    print("\n" + "=" * 60)
    print("Task-052A Complete!")
    print("=" * 60)
    print("\nAll items tagged with: Task-052, MAS-Architecture")
    print("Each item includes notes explaining framework mapping.")


if __name__ == "__main__":
    main()
