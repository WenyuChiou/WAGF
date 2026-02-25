# Water Agent Governance Framework: 記憶系統設計

## 概述

本文檔設計適用於 Water Agent Governance Framework 的記憶與檢索系統，基於 Hello-Agents 第八章概念。

**設計原則:**
1. 模擬人類認知記憶層次
2. "Everything is a Tool" 哲學
3. 與 Skill-Governed Architecture 整合

---

## 1. 記憶系統架構

### 1.1 層次結構 (認知科學啟發)

```
┌─────────────────────────────────────────────────────────────┐
│                    Memory System                            │
│  ┌─────────────────────────────────────────────────────┐    │
│  │              Working Memory (工作記憶)               │    │
│  │  - 短期、有限容量                                    │    │
│  │  - 當前任務處理                                      │    │
│  │  - TTL 過期機制                                      │    │
│  │  - 容量: 10 items                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                  Consolidation (整合)                        │
│                   重要性 > 閾值                              │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │             Episodic Memory (情景記憶)               │    │
│  │  - 長期、持久存儲                                    │    │
│  │  - 個人經歷與事件                                    │    │
│  │  - 時間衰減機制                                      │    │
│  │  - 向量相似度檢索                                    │    │
│  └─────────────────────────────────────────────────────┘    │
│                          │                                   │
│                   Retrieval (檢索)                           │
│                          ▼                                   │
│  ┌─────────────────────────────────────────────────────┐    │
│  │                 RAG Module                           │    │
│  │  - 外部知識檢索                                      │    │
│  │  - 語義搜索                                          │    │
│  │  - 政策文檔、歷史資料                                │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

### 1.2 與 Agent 類型對應

| 記憶類型 | Household | Insurance | Government |
|----------|-----------|-----------|------------|
| **Working** | 當年決策資訊 | 當年統計 | 當年政策 |
| **Episodic** | 洪水經歷、行動 | 年度表現 | 政策效果 |
| **RAG** | 政策公告 | 市場研究 | 法規、研究 |

---

## 2. 核心類別設計

### 2.1 MemoryItem (記憶項目)

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"

@dataclass
class MemoryItem:
    """單一記憶項目"""
    id: str
    content: str
    memory_type: MemoryType
    timestamp: datetime = field(default_factory=datetime.now)
    
    # 元數據
    year: int = 0                      # 模擬年份
    importance: float = 0.5            # 重要性 0-1
    agent_id: str = ""                 # 所屬 Agent
    tags: List[str] = field(default_factory=list)
    
    # 用於向量檢索
    embedding: Optional[List[float]] = None
    
    def is_expired(self, ttl_seconds: int) -> bool:
        """檢查是否過期 (適用於 Working Memory)"""
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > ttl_seconds
    
    def decay_score(self, current_year: int, decay_rate: float = 0.95) -> float:
        """計算時間衰減分數"""
        years_passed = max(0, current_year - self.year)
        return decay_rate ** years_passed
```

### 2.2 WorkingMemory (工作記憶)

```python
@dataclass
class WorkingMemoryConfig:
    capacity: int = 10          # 最大容量
    ttl_seconds: int = 300      # 5 分鐘過期

class WorkingMemory:
    """
    工作記憶: 短期、有限容量
    
    特點:
    - FIFO + 重要性排序
    - TTL 過期機制
    - 用於當前決策
    """
    
    def __init__(self, agent_id: str, config: Optional[WorkingMemoryConfig] = None):
        self.agent_id = agent_id
        self.config = config or WorkingMemoryConfig()
        self._items: List[MemoryItem] = []
    
    def add(self, content: str, importance: float = 0.5, 
            year: int = 0, tags: List[str] = None) -> MemoryItem:
        """添加記憶"""
        # 容量檢查
        self._evict_if_needed()
        
        item = MemoryItem(
            id=f"wm_{self.agent_id}_{datetime.now().timestamp()}",
            content=content,
            memory_type=MemoryType.WORKING,
            importance=importance,
            year=year,
            agent_id=self.agent_id,
            tags=tags or []
        )
        self._items.append(item)
        return item
    
    def _evict_if_needed(self) -> None:
        """容量滿時移除最不重要的"""
        # 先移除過期的
        self._items = [
            item for item in self._items 
            if not item.is_expired(self.config.ttl_seconds)
        ]
        
        # 容量仍超過則移除最不重要的
        if len(self._items) >= self.config.capacity:
            self._items.sort(key=lambda x: x.importance)
            self._items.pop(0)
    
    def get_all(self) -> List[MemoryItem]:
        """獲取所有未過期記憶"""
        return [
            item for item in self._items 
            if not item.is_expired(self.config.ttl_seconds)
        ]
    
    def get_high_importance(self, threshold: float = 0.7) -> List[MemoryItem]:
        """獲取高重要性記憶 (用於 consolidation)"""
        return [item for item in self.get_all() if item.importance >= threshold]
    
    def format_for_prompt(self, max_items: int = 5) -> str:
        """格式化為 prompt"""
        items = sorted(self.get_all(), 
                      key=lambda x: x.importance, reverse=True)[:max_items]
        if not items:
            return "No recent memories."
        return "\n".join(f"- {item.content}" for item in items)
```

### 2.3 EpisodicMemory (情景記憶)

```python
@dataclass
class EpisodicMemoryConfig:
    decay_rate: float = 0.95       # 年度衰減
    max_items: int = 100           # 最大容量
    similarity_weight: float = 0.6  # 相似度權重
    importance_weight: float = 0.4  # 重要性權重

class EpisodicMemory:
    """
    情景記憶: 長期、持久存儲
    
    特點:
    - 存儲重要經歷
    - 時間衰減
    - 向量相似度檢索
    
    檢索評分公式 (Hello-Agents 啟發):
    score = (similarity * time_decay) * (0.8 + importance * 0.4)
    """
    
    def __init__(self, agent_id: str, 
                 embedding_fn: Optional[callable] = None,
                 config: Optional[EpisodicMemoryConfig] = None):
        self.agent_id = agent_id
        self.config = config or EpisodicMemoryConfig()
        self.embedding_fn = embedding_fn
        self._items: List[MemoryItem] = []
    
    def add(self, content: str, importance: float = 0.7,
            year: int = 0, tags: List[str] = None) -> MemoryItem:
        """添加情景記憶"""
        embedding = None
        if self.embedding_fn:
            embedding = self.embedding_fn(content)
        
        item = MemoryItem(
            id=f"em_{self.agent_id}_{datetime.now().timestamp()}",
            content=content,
            memory_type=MemoryType.EPISODIC,
            importance=importance,
            year=year,
            agent_id=self.agent_id,
            tags=tags or [],
            embedding=embedding
        )
        self._items.append(item)
        
        # 容量控制
        if len(self._items) > self.config.max_items:
            self._items.sort(key=lambda x: x.importance)
            self._items.pop(0)
        
        return item
    
    def retrieve(self, query: str = None, current_year: int = 0,
                 top_k: int = 5) -> List[MemoryItem]:
        """
        檢索相關記憶
        
        評分公式:
        score = (similarity * time_decay) * (0.8 + importance * 0.4)
        """
        scored_items = []
        
        query_embedding = None
        if query and self.embedding_fn:
            query_embedding = self.embedding_fn(query)
        
        for item in self._items:
            # 時間衰減
            time_decay = item.decay_score(current_year, self.config.decay_rate)
            
            # 相似度
            if query_embedding and item.embedding:
                similarity = self._cosine_similarity(query_embedding, item.embedding)
            else:
                similarity = 1.0  # 無 embedding 時默認滿分
            
            # 評分公式 (Hello-Agents 啟發)
            score = (similarity * time_decay) * (0.8 + item.importance * 0.4)
            scored_items.append((score, item))
        
        # 排序取 top_k
        scored_items.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored_items[:top_k]]
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """計算餘弦相似度"""
        import math
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    
    def format_for_prompt(self, current_year: int, top_k: int = 3) -> str:
        """格式化為 prompt"""
        items = self.retrieve(current_year=current_year, top_k=top_k)
        if not items:
            return "No past experiences recalled."
        return "\n".join(f"- {item.content}" for item in items)
```

### 2.4 MemoryManager (記憶管理器)

```python
@dataclass
class ConsolidationConfig:
    importance_threshold: float = 0.7  # 整合閾值

class MemoryManager:
    """
    記憶管理器: 統一管理 Working + Episodic Memory
    
    職責:
    - 創建與管理記憶
    - Consolidation (工作 → 情景)
    - 統一檢索接口
    """
    
    def __init__(self, agent_id: str, 
                 embedding_fn: Optional[callable] = None):
        self.agent_id = agent_id
        self.working = WorkingMemory(agent_id)
        self.episodic = EpisodicMemory(agent_id, embedding_fn)
        self.consolidation_config = ConsolidationConfig()
    
    # ===== 添加記憶 =====
    
    def add_experience(self, content: str, importance: float = 0.5,
                       year: int = 0, tags: List[str] = None) -> MemoryItem:
        """添加經驗 (自動決定存入 Working 還是 Episodic)"""
        if importance >= self.consolidation_config.importance_threshold:
            return self.episodic.add(content, importance, year, tags)
        else:
            return self.working.add(content, importance, year, tags)
    
    def add_flood_experience(self, damage: float, year: int) -> MemoryItem:
        """添加洪水經歷 (高重要性 → Episodic)"""
        content = f"Year {year}: A flood occurred causing ${damage:,.0f} in damages"
        return self.episodic.add(content, importance=0.9, year=year, 
                                 tags=["flood", "damage"])
    
    def add_decision(self, decision: str, year: int) -> MemoryItem:
        """添加決策記錄"""
        content = f"Year {year}: I decided to {decision}"
        importance = 0.7 if decision != "do_nothing" else 0.3
        return self.working.add(content, importance, year, tags=["decision"])
    
    def add_policy_info(self, content: str, year: int) -> MemoryItem:
        """添加政策資訊"""
        return self.working.add(content, importance=0.5, year=year, 
                                tags=["policy"])
    
    # ===== 整合 =====
    
    def consolidate(self) -> int:
        """
        整合: 將高重要性 Working Memory 轉移到 Episodic Memory
        
        Returns: 整合數量
        """
        high_importance = self.working.get_high_importance(
            self.consolidation_config.importance_threshold
        )
        
        count = 0
        for item in high_importance:
            self.episodic.add(
                content=item.content,
                importance=item.importance,
                year=item.year,
                tags=item.tags
            )
            count += 1
        
        return count
    
    # ===== 檢索 =====
    
    def retrieve(self, query: str = None, current_year: int = 0,
                 top_k: int = 5) -> List[str]:
        """
        統一檢索: 優先 Working，補充 Episodic
        """
        results = []
        
        # Working Memory (最近)
        working_items = self.working.get_all()
        for item in working_items[:top_k]:
            results.append(item.content)
        
        # Episodic Memory (補充)
        remaining = top_k - len(results)
        if remaining > 0:
            episodic_items = self.episodic.retrieve(
                query, current_year, remaining
            )
            for item in episodic_items:
                if item.content not in results:
                    results.append(item.content)
        
        return results[:top_k]
    
    def format_for_prompt(self, current_year: int) -> str:
        """格式化為 prompt"""
        memories = self.retrieve(current_year=current_year, top_k=5)
        if not memories:
            return "No memories recalled."
        return "\n".join(f"- {m}" for m in memories)
```

---

## 3. Agent-Specific Memory 設計

### 3.1 Household Memory

```python
class HouseholdMemory(MemoryManager):
    """Household Agent 專用記憶"""
    
    PAST_EVENTS = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support",
        "News outlets have reported increasing flood frequency and severity"
    ]
    
    def __init__(self, agent_id: str, agent_type: str,
                 embedding_fn: Optional[callable] = None):
        super().__init__(agent_id, embedding_fn)
        self.agent_type = agent_type
        self._initialize_background()
    
    def _initialize_background(self) -> None:
        """初始化背景記憶"""
        import random
        # 隨機選 2 個歷史事件
        for event in random.sample(self.PAST_EVENTS, 2):
            self.episodic.add(event, importance=0.4, year=0, 
                             tags=["background"])
    
    def add_neighbor_action(self, neighbor_id: str, action: str, 
                            year: int) -> MemoryItem:
        """添加鄰居行為記憶"""
        content = f"Year {year}: Neighbor {neighbor_id} chose to {action}"
        return self.working.add(content, importance=0.4, year=year,
                                tags=["neighbor", "social"])
```

### 3.2 Insurance Memory

```python
class InsuranceMemory(MemoryManager):
    """Insurance Agent 專用記憶"""
    
    def __init__(self, embedding_fn: Optional[callable] = None):
        super().__init__("InsuranceCo", embedding_fn)
    
    def add_year_performance(self, year: int, loss_ratio: float,
                             claims: float, uptake: float) -> MemoryItem:
        """添加年度表現"""
        content = (f"Year {year}: Loss ratio {loss_ratio:.1%}, "
                  f"Claims ${claims:,.0f}, Uptake {uptake:.1%}")
        importance = 0.8 if loss_ratio > 1.0 else 0.5
        return self.episodic.add(content, importance, year, 
                                 tags=["performance"])
    
    def add_significant_event(self, content: str, year: int) -> MemoryItem:
        """添加重大事件 (例如: Loss ratio 超過 100%)"""
        return self.episodic.add(content, importance=0.9, year=year,
                                 tags=["significant", "alert"])
```

### 3.3 Government Memory

```python
class GovernmentMemory(MemoryManager):
    """Government Agent 專用記憶"""
    
    def __init__(self, embedding_fn: Optional[callable] = None):
        super().__init__("Government", embedding_fn)
    
    def add_policy_record(self, year: int, subsidy_rate: float,
                          mg_adoption: float, budget_used: float,
                          flood_occurred: bool) -> MemoryItem:
        """添加政策記錄"""
        flood_str = " [FLOOD YEAR]" if flood_occurred else ""
        content = (f"Year {year}{flood_str}: Subsidy {subsidy_rate:.0%}, "
                  f"MG adoption {mg_adoption:.0%}, Spent ${budget_used:,.0f}")
        importance = 0.8 if flood_occurred else 0.5
        return self.episodic.add(content, importance, year,
                                 tags=["policy"])
    
    def add_policy_event(self, content: str, year: int) -> MemoryItem:
        """添加政策事件 (例如: 緊急增加補助)"""
        return self.episodic.add(content, importance=0.9, year=year,
                                 tags=["policy", "significant"])
```

---

## 4. 與 ContextBuilder 整合

```python
class MemoryAwareContextBuilder:
    """整合記憶的 Context Builder"""
    
    def __init__(self, simulation, memory_manager: MemoryManager):
        self.simulation = simulation
        self.memory = memory_manager
    
    def build(self, agent_id: str, current_year: int) -> Dict[str, Any]:
        """構建含記憶的 context"""
        base_context = self._build_base_context(agent_id)
        
        # 添加記憶
        base_context["memory"] = self.memory.format_for_prompt(current_year)
        
        return base_context
    
    def format_prompt(self, context: Dict[str, Any]) -> str:
        """格式化為 prompt"""
        memory_section = context.get("memory", "No memories.")
        
        return f"""...
Your memory includes:
{memory_section}
..."""
```

---

## 5. 記憶工具 (Everything is a Tool)

```python
class MemoryTool:
    """記憶工具: 符合 "Everything is a Tool" 哲學"""
    
    name = "memory_tool"
    description = "Store and retrieve agent memories"
    
    def __init__(self, memory_manager: MemoryManager):
        self.memory = memory_manager
    
    def invoke(self, action: str, **kwargs) -> Dict[str, Any]:
        """統一調用接口"""
        if action == "add":
            item = self.memory.add_experience(**kwargs)
            return {"status": "added", "id": item.id}
        
        elif action == "retrieve":
            items = self.memory.retrieve(**kwargs)
            return {"status": "retrieved", "items": items}
        
        elif action == "consolidate":
            count = self.memory.consolidate()
            return {"status": "consolidated", "count": count}
        
        else:
            return {"status": "error", "message": f"Unknown action: {action}"}
```

---

## 6. 配置

```yaml
# memory_config.yaml
memory:
  working:
    capacity: 10
    ttl_seconds: 300
  
  episodic:
    decay_rate: 0.95
    max_items: 100
    similarity_weight: 0.6
    importance_weight: 0.4
  
  consolidation:
    importance_threshold: 0.7
  
  embedding:
    provider: "sentence-transformers"  # or "openai"
    model: "all-MiniLM-L6-v2"
```

---

## 7. 使用範例

```python
# 創建 Household Memory
memory = HouseholdMemory("Agent_1", "MG_Owner")

# 年初: 收到政策公告
memory.add_policy_info("Government increased subsidy to 75%", year=3)

# 洪水發生
memory.add_flood_experience(damage=15000, year=3)

# 決策
memory.add_decision("elevate_house", year=3)

# 觀察鄰居
memory.add_neighbor_action("Agent_2", "buy_insurance", year=3)

# 年末: 整合記憶
memory.consolidate()

# 下一年: 檢索記憶 for prompt
memories = memory.format_for_prompt(current_year=4)
```
