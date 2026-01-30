#!/usr/bin/env python3
"""
Add Task-058 MAS Skill Architecture Literature to Zotero.

Creates a 'Task-058-MAS-Skill-Architecture' collection and adds/tags papers.

Usage:
    pip install pyzotero
    python .tasks/scripts/add_task058_literature.py
"""

import os
import sys
from typing import Dict, List, Optional

try:
    from pyzotero import zotero
except ImportError:
    print("Error: pyzotero not installed. Run: pip install pyzotero")
    sys.exit(1)


# Configuration
ZOTERO_API_KEY = os.environ.get("ZOTERO_API_KEY", "hLGhkxO20sXiKpMF62mGDeG2")
ZOTERO_LIBRARY_ID = os.environ.get("ZOTERO_LIBRARY_ID", "14772686")
ZOTERO_LIBRARY_TYPE = "user"

COLLECTION_NAME = "Task-058-MAS-Skill-Architecture"

# Existing papers to tag
EXISTING_PAPERS = {
    "U44MWXQC": {"name": "MetaGPT", "new_tags": ["Task-058", "MAS-architecture", "Phase-1-Artifacts"]},
    "HITVU4HK": {"name": "Concordia (Library)", "new_tags": ["Task-058", "MAS-architecture", "Phase-2-Validation"]},
    "7G736VMQ": {"name": "SagaLLM", "new_tags": ["Task-058", "MAS-architecture", "Phase-3-Sagas"]},
}


def create_zotero_client():
    """Create Zotero API client."""
    return zotero.Zotero(ZOTERO_LIBRARY_ID, ZOTERO_LIBRARY_TYPE, ZOTERO_API_KEY)


def create_collection(zot, name: str) -> Optional[str]:
    """Create a new Zotero collection and return its key."""
    # Check if collection already exists
    collections = zot.collections()
    for col in collections:
        if col["data"]["name"] == name:
            print(f"[EXISTS] Collection '{name}' already exists (key: {col['key']})")
            return col["key"]

    try:
        response = zot.create_collections([{"name": name}])
        if response.get("successful"):
            key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created collection '{name}' (key: {key})")
            return key
        else:
            print(f"[ERROR] Failed to create collection: {response.get('failed', {})}")
            return None
    except Exception as e:
        print(f"[ERROR] Collection creation failed: {e}")
        return None


def add_to_collection(zot, collection_key: str, item_keys: List[str]):
    """Add items to a collection."""
    for key in item_keys:
        try:
            # Get item, add collection, update
            item = zot.item(key)
            collections = item["data"].get("collections", [])
            if collection_key not in collections:
                collections.append(collection_key)
                item["data"]["collections"] = collections
                zot.update_item(item)
                print(f"       Added {key} to collection")
            else:
                print(f"       {key} already in collection")
        except Exception as e:
            print(f"       Error adding {key} to collection: {e}")


def tag_existing_papers(zot, collection_key: Optional[str]):
    """Add Task-058 tags to existing papers."""
    print("\n" + "=" * 60)
    print("STEP 2: Tagging Existing Papers")
    print("=" * 60)

    for item_key, info in EXISTING_PAPERS.items():
        try:
            item = zot.item(item_key)
            existing_tags = [t["tag"] for t in item["data"].get("tags", [])]
            new_tags = [t for t in info["new_tags"] if t not in existing_tags]

            if new_tags:
                tag_list = item["data"].get("tags", [])
                tag_list.extend([{"tag": t} for t in new_tags])
                item["data"]["tags"] = tag_list
                zot.update_item(item)
                print(f"[OK] Tagged {info['name']} ({item_key}): +{new_tags}")
            else:
                print(f"[SKIP] {info['name']} ({item_key}): tags already present")

            # Add to collection
            if collection_key:
                collections = item["data"].get("collections", [])
                if collection_key not in collections:
                    collections.append(collection_key)
                    item["data"]["collections"] = collections
                    zot.update_item(item)

        except Exception as e:
            print(f"[ERROR] Failed to tag {info['name']} ({item_key}): {e}")


def add_note_to_item(zot, item_key: str, note_content: str) -> bool:
    """Add a note to an existing Zotero item."""
    note_template = zot.item_template("note")
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


def add_new_papers(zot, collection_key: Optional[str]):
    """Add 4 new papers to Zotero."""
    print("\n" + "=" * 60)
    print("STEP 3: Adding New Papers")
    print("=" * 60)

    added_keys = []

    # 1. AgentSociety (Piao et al., 2025)
    print("\n--- 1. AgentSociety ---")
    template = zot.item_template("preprint")
    template["title"] = "AgentSociety: Large-Scale Simulation of LLM-Driven Generative Agents Advances Understanding of Human Behaviors and Society"
    template["repository"] = "arXiv"
    template["archiveID"] = "2502.08691"
    template["date"] = "2025"
    template["url"] = "https://arxiv.org/abs/2502.08691"
    template["abstractNote"] = (
        "This paper proposes AgentSociety, a large-scale social simulator that integrates "
        "LLM-driven agents, a realistic societal environment, and a powerful large-scale "
        "simulation engine. The agents are endowed with human-like 'minds,' including emotions, "
        "needs, motivations, and cognition. The authors generate social lives for over 10k agents, "
        "simulating 5 million interactions. The simulator successfully reproduces behaviors from "
        "four real-world social experiments: polarization, inflammatory message spread, universal "
        "basic income, and hurricane impact."
    )
    template["creators"] = [
        {"creatorType": "author", "firstName": "Jinghua", "lastName": "Piao"},
        {"creatorType": "author", "firstName": "Yuwei", "lastName": "Yan"},
        {"creatorType": "author", "firstName": "Jun", "lastName": "Zhang"},
        {"creatorType": "author", "firstName": "Nian", "lastName": "Li"},
        {"creatorType": "author", "firstName": "Junbo", "lastName": "Yan"},
        {"creatorType": "author", "firstName": "Xiaochong", "lastName": "Lan"},
        {"creatorType": "author", "firstName": "Zhihong", "lastName": "Lu"},
        {"creatorType": "author", "firstName": "Zhiheng", "lastName": "Zheng"},
        {"creatorType": "author", "firstName": "Jing Yi", "lastName": "Wang"},
        {"creatorType": "author", "firstName": "Di", "lastName": "Zhou"},
        {"creatorType": "author", "firstName": "Chen", "lastName": "Gao"},
        {"creatorType": "author", "firstName": "Fengli", "lastName": "Xu"},
        {"creatorType": "author", "firstName": "Fang", "lastName": "Zhang"},
        {"creatorType": "author", "firstName": "Ke", "lastName": "Rong"},
        {"creatorType": "author", "firstName": "Jun", "lastName": "Su"},
        {"creatorType": "author", "firstName": "Yong", "lastName": "Li"},
    ]
    template["tags"] = [
        {"tag": "Task-058"}, {"tag": "MAS-architecture"}, {"tag": "Phase-4-Drift"},
        {"tag": "governed-broker"}, {"tag": "LLM-Agent"}, {"tag": "Social-Simulation"},
    ]
    if collection_key:
        template["collections"] = [collection_key]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created AgentSociety (key: {key})")
            added_keys.append(key)
            add_note_to_item(zot, key, """<p><strong>Applied in Task-058:</strong> Phase 4 - Drift Detection & Social Norms</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>10k+ agent simulation with emotion, needs, motivation</li>
<li>Population-level behavior tracking (polarization, hurricane impact)</li>
<li>Character drift detection via internal mental states</li>
<li>Social experiment reproduction (UBI, inflammatory messages)</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>DriftDetector &rarr; Population-level entropy monitoring</li>
<li>AgentDriftReport &rarr; Individual stagnation detection</li>
<li>RoleEnforcer &rarr; Agent type permissions</li>
</ul>""")
        else:
            print(f"[ERROR] Failed: {response.get('failed', {})}")
    except Exception as e:
        print(f"[ERROR] {e}")

    # 2. Making Waves (Hosseini et al., 2025)
    print("\n--- 2. Making Waves ---")
    template = zot.item_template("journalArticle")
    template["title"] = "Making waves: A conceptual framework exploring how large language model-based multi-agent systems could reshape water engineering"
    template["publicationTitle"] = "Water Research"
    template["date"] = "2025"
    template["volume"] = "291"
    template["pages"] = "125157"
    template["DOI"] = "10.1016/j.watres.2025.125157"
    template["abstractNote"] = (
        "Large Language Model-based Multi-Agents (LLM-MAs) are emerging systems that manage "
        "complex tasks with specialized and coordinated agents. This paper presents new "
        "perspectives on the integration of LLM-MA systems into enhancing water engineering "
        "practices. LLM-MA systems can enhance water engineering by improving data integration, "
        "monitoring, and decision-making. Specialized agents can support groundwater monitoring, "
        "irrigation scheduling, reservoir management, and post-disaster response."
    )
    template["creators"] = [
        {"creatorType": "author", "firstName": "Seyed Hossein", "lastName": "Hosseini"},
        {"creatorType": "author", "firstName": "Babak", "lastName": "Zolghadr-Asli"},
        {"creatorType": "author", "firstName": "Henrikki", "lastName": "Tenkanen"},
        {"creatorType": "author", "firstName": "Kaveh", "lastName": "Madani"},
        {"creatorType": "author", "firstName": "Mir A.", "lastName": "Matin"},
        {"creatorType": "author", "firstName": "Ibrahim", "lastName": "Demir"},
        {"creatorType": "author", "firstName": "Avi", "lastName": "Ostfeld"},
        {"creatorType": "author", "firstName": "Vijay P.", "lastName": "Singh"},
        {"creatorType": "author", "firstName": "Dragan", "lastName": "Savic"},
    ]
    template["tags"] = [
        {"tag": "Task-058"}, {"tag": "MAS-architecture"}, {"tag": "Water-Resource-ABM"},
        {"tag": "governed-broker"}, {"tag": "LLM-Agent"}, {"tag": "Water-Engineering"},
    ]
    if collection_key:
        template["collections"] = [collection_key]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created Making Waves (key: {key})")
            added_keys.append(key)
            add_note_to_item(zot, key, """<p><strong>Applied in Task-058:</strong> Water Domain MAS Framework Reference</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Conceptual framework for LLM-MA in water engineering</li>
<li>Specialized agents: groundwater monitoring, irrigation, reservoir management</li>
<li>Post-disaster response via multi-agent coordination</li>
<li>Governance challenges: bias, hallucination, data access</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>Governed Broker &rarr; Governance layer for LLM agent validation</li>
<li>SkillRegistry &rarr; Specialized task definitions</li>
<li>GameMaster &rarr; Multi-agent coordination for water management</li>
</ul>""")
        else:
            print(f"[ERROR] Failed: {response.get('failed', {})}")
    except Exception as e:
        print(f"[ERROR] {e}")

    # 3. IWMS-LLM (He et al., 2025)
    print("\n--- 3. IWMS-LLM ---")
    template = zot.item_template("journalArticle")
    template["title"] = "IWMS-LLM: an intelligent water resources management system based on large language models"
    template["publicationTitle"] = "Journal of Hydroinformatics"
    template["date"] = "2025"
    template["volume"] = "27"
    template["issue"] = "11"
    template["pages"] = "1685-1702"
    template["DOI"] = "10.2166/hydro.2025.130"
    template["abstractNote"] = (
        "Water resources management is inherently complex and dynamic, characterized by strong "
        "time-sensitivity and uncertainty. Traditional water resources information systems rely on "
        "fixed-process decision-making, which often lack flexibility. This paper proposes IWMS-LLM, "
        "an Intelligent Water Resources Management System based on Large Language Models, introducing "
        "a visual workflow orchestration approach. The system uses an Agent-based approach leveraging "
        "LLM reasoning capabilities to refine operational requirements and select optimal workflows."
    )
    template["creators"] = [
        {"creatorType": "author", "firstName": "Guo", "lastName": "He"},
        {"creatorType": "author", "firstName": "Jungang", "lastName": "Luo"},
        {"creatorType": "author", "firstName": "Feixiong", "lastName": "Luo"},
        {"creatorType": "author", "firstName": "Xue", "lastName": "Yang"},
        {"creatorType": "author", "firstName": "Xin", "lastName": "Jing"},
        {"creatorType": "author", "firstName": "Huhu", "lastName": "Cui"},
    ]
    template["tags"] = [
        {"tag": "Task-058"}, {"tag": "MAS-architecture"}, {"tag": "Water-Resource-ABM"},
        {"tag": "governed-broker"}, {"tag": "LLM-Agent"}, {"tag": "Water-Management"},
    ]
    if collection_key:
        template["collections"] = [collection_key]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created IWMS-LLM (key: {key})")
            added_keys.append(key)
            add_note_to_item(zot, key, """<p><strong>Applied in Task-058:</strong> Water Domain Agent Architecture Reference</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>Agent-based workflow orchestration for water management</li>
<li>Visual workflow selection using LLM reasoning</li>
<li>Dynamic decision-making vs. fixed-process systems</li>
<li>Practical deployment: Linjiacun water condition query example</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>SagaCoordinator &rarr; Multi-step workflow orchestration</li>
<li>PhaseOrchestrator &rarr; Workflow execution phases</li>
<li>SkillBrokerEngine &rarr; Agent reasoning + skill selection</li>
</ul>""")
        else:
            print(f"[ERROR] Failed: {response.get('failed', {})}")
    except Exception as e:
        print(f"[ERROR] {e}")

    # 4. Hung & Yang (2021)
    print("\n--- 4. Hung & Yang (2021) ---")
    template = zot.item_template("journalArticle")
    template["title"] = "Assessing Adaptive Irrigation Impacts on Water Scarcity in Nonstationary Environments—A Multi-Agent Reinforcement Learning Approach"
    template["publicationTitle"] = "Water Resources Research"
    template["date"] = "2021"
    template["volume"] = "57"
    template["DOI"] = "10.1029/2020WR029262"
    template["abstractNote"] = (
        "This paper develops a reinforcement learning agent-based modeling (RL-ABM) framework "
        "where agents (agriculture water users) learn and adjust water demands based on their "
        "interactions with the water systems. The framework is illustrated in a case study "
        "coupled with the Colorado River Simulation System (CRSS). Seventy-eight intelligent "
        "agents are simulated in three categories: 'aggressive,' 'forward-looking conservative,' "
        "and 'myopic conservative.' Results show major reservoirs may experience more frequent "
        "water shortages due to increasing water uses."
    )
    template["creators"] = [
        {"creatorType": "author", "firstName": "Fengwei", "lastName": "Hung"},
        {"creatorType": "author", "firstName": "Y. C. Ethan", "lastName": "Yang"},
    ]
    template["tags"] = [
        {"tag": "Task-058"}, {"tag": "MAS-architecture"}, {"tag": "Water-Resource-ABM"},
        {"tag": "governed-broker"}, {"tag": "ABM"}, {"tag": "Reinforcement-Learning"},
        {"tag": "Colorado-River"},
    ]
    if collection_key:
        template["collections"] = [collection_key]

    try:
        response = zot.create_items([template])
        if response.get("successful"):
            key = list(response["successful"].values())[0]["key"]
            print(f"[OK] Created Hung & Yang 2021 (key: {key})")
            added_keys.append(key)
            add_note_to_item(zot, key, """<p><strong>Applied in Task-058:</strong> Water Domain ABM Baseline Reference</p>
<p><strong>Key Contributions:</strong></p>
<ul>
<li>RL-ABM framework: agents learn adaptive irrigation behavior</li>
<li>78 intelligent agents in 3 behavioral categories</li>
<li>Coupled with Colorado River Simulation System (CRSS)</li>
<li>Nonstationary environment handling</li>
</ul>
<p><strong>Framework Mapping:</strong></p>
<ul>
<li>HouseholdAgent behavioral types &rarr; aggressive/conservative categorization</li>
<li>DriftDetector &rarr; Tracking agent behavioral category shifts</li>
<li>Environment coupling &rarr; Water system feedback loop</li>
</ul>""")
        else:
            print(f"[ERROR] Failed: {response.get('failed', {})}")
    except Exception as e:
        print(f"[ERROR] {e}")

    return added_keys


def main():
    """Execute Task-058 Zotero literature additions."""
    zot = create_zotero_client()

    print("=" * 60)
    print("Task-058: Adding MAS Skill Architecture Literature to Zotero")
    print("=" * 60)

    # Step 1: Create collection
    print("\n" + "=" * 60)
    print("STEP 1: Creating Collection")
    print("=" * 60)
    collection_key = create_collection(zot, COLLECTION_NAME)

    # Step 2: Tag existing papers
    tag_existing_papers(zot, collection_key)

    # Step 3: Add new papers
    added_keys = add_new_papers(zot, collection_key)

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Collection: {COLLECTION_NAME} (key: {collection_key})")
    print(f"Existing papers tagged: {len(EXISTING_PAPERS)}")
    print(f"New papers added: {len(added_keys)}")
    print(f"Total papers in collection: {len(EXISTING_PAPERS) + len(added_keys)}")
    print("\nAll items tagged with: Task-058, MAS-architecture")


if __name__ == "__main__":
    main()
