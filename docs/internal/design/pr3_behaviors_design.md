# PR3 Behaviors: Agent Outputs & Memory Versions

## 概述

本文檔定義 Exp3 Multi-Agent 的：
1. 各 Agent 類型輸出結構
2. 兩個 Memory 版本設計

---

## 1. Agent Output 結構

### 1.1 Household Agent Output (對齊單 Agent)

**單 Agent 現有輸出格式:**
```
Threat Appraisal: [One sentence]
Coping Appraisal: [One sentence]
Final Decision: [1, 2, 3, or 4]
```

**Multi-Agent 擴展輸出 (5 Constructs):**
```
TP Assessment: [LOW/MODERATE/HIGH] - [One sentence]
CP Assessment: [LOW/MODERATE/HIGH] - [One sentence]
SP Assessment: [LOW/MODERATE/HIGH] - [One sentence]
SC Assessment: [LOW/MODERATE/HIGH] - [One sentence]
PA Assessment: [NONE/PARTIAL/FULL] - [One sentence]
Final Decision: [number only]
```

**Python 結構:**
```python
@dataclass
class HouseholdOutput:
    """Household agent LLM output"""
    agent_id: str
    agent_type: str  # MG_Owner, MG_Renter, NMG_Owner, NMG_Renter
    year: int
    
    # Construct assessments
    tp_level: Literal["LOW", "MODERATE", "HIGH"]
    tp_explanation: str
    cp_level: Literal["LOW", "MODERATE", "HIGH"]
    cp_explanation: str
    sp_level: Literal["LOW", "MODERATE", "HIGH"]
    sp_explanation: str
    sc_level: Literal["LOW", "MODERATE", "HIGH"]
    sc_explanation: str
    pa_level: Literal["NONE", "PARTIAL", "FULL"]
    pa_explanation: str
    
    # Decision
    decision_number: int
    decision_skill: str  # buy_insurance, elevate_house, etc.
    
    # Validation
    validated: bool
    validation_errors: List[str] = field(default_factory=list)
    validation_warnings: List[str] = field(default_factory=list)
    
    # Context snapshot (for audit)
    context_hash: str = ""
```

---

### 1.2 Insurance Agent Output

**輸出格式:**
```
Analysis: [One sentence about loss ratio]
Decision: [raise/lower/maintain]
Adjustment: [percentage, e.g., 5%]
Reason: [Brief explanation]
```

**Python 結構:**
```python
@dataclass
class InsuranceOutput:
    """Insurance agent LLM output"""
    year: int
    
    # Context
    loss_ratio: float
    total_policies: int
    claims_last_year: float
    
    # Decision
    decision: Literal["raise", "lower", "maintain"]
    adjustment_pct: float  # 0.05 = 5%
    reason: str
    
    # Result
    new_premium_rate: float
    validated: bool
```

---

### 1.3 Government Agent Output

**輸出格式:**
```
Analysis: [One sentence about adoption rates]
Decision: [increase/decrease/maintain]
Adjustment: [percentage, e.g., 10%]
Priority: [MG/all]
Reason: [Brief explanation]
```

**Python 結構:**
```python
@dataclass
class GovernmentOutput:
    """Government agent LLM output"""
    year: int
    
    # Context
    budget_remaining: float
    mg_adoption_rate: float
    nmg_adoption_rate: float
    flood_occurred: bool
    
    # Decision
    decision: Literal["increase", "decrease", "maintain"]
    adjustment_pct: float
    priority: Literal["MG", "all"]
    reason: str
    
    # Result
    new_subsidy_rate: float
    validated: bool
```

---

## 2. Memory 系統兩版本

### Version 1: Simple Memory (對齊單 Agent)

**特點:** 
- 使用 Python List 實現
- MEMORY_WINDOW = 5 (最多 5 條記憶)
- 固定容量，FIFO 替換
- 隨機 20% 機率回憶歷史事件

**程式碼:**
```python
class SimpleMemory:
    """Version 1: 對齊單 Agent 的簡單記憶"""
    
    MEMORY_WINDOW = 5
    RANDOM_RECALL_CHANCE = 0.2
    
    PAST_EVENTS = [
        "A flood event about 15 years ago caused $500,000 in city-wide damages",
        "Some residents reported delays when processing their flood insurance claims",
        "A few households in the area elevated their homes before recent floods",
        "The city previously introduced a program offering elevation support",
        "News outlets have reported increasing flood frequency and severity"
    ]
    
    def __init__(self):
        self._memories: List[str] = []
    
    def add(self, content: str) -> None:
        """添加記憶 (FIFO，超過 window 移除最舊)"""
        self._memories.append(content)
        if len(self._memories) > self.MEMORY_WINDOW:
            self._memories.pop(0)
    
    def retrieve(self) -> List[str]:
        """檢索記憶 (含隨機歷史事件)"""
        memories = self._memories.copy()
        
        # 20% 機率添加隨機歷史事件
        if random.random() < self.RANDOM_RECALL_CHANCE:
            random_event = random.choice(self.PAST_EVENTS)
            if random_event not in memories:
                memories.append(random_event)
        
        return memories
    
    def update_after_flood(self, damage: float) -> None:
        """洪水後更新記憶"""
        self.add(f"A flood occurred causing ${damage:,.0f} in damages")
    
    def update_after_decision(self, decision: str, year: int) -> None:
        """決策後更新記憶"""
        self.add(f"Year {year}: I chose to {decision}")
```

**使用範例:**
```python
# 創建
memory = SimpleMemory()

# 初始記憶
for event in random.sample(SimpleMemory.PAST_EVENTS, 2):
    memory.add(event)

# 決策後更新
memory.update_after_decision("buy insurance", year=1)

# 檢索 (for prompt)
memories = memory.retrieve()
```

---

### Version 2: Cognitive Memory (基於 Hello-Agents)

**特點:**
- 工作記憶 + 情景記憶 分層
- TTL 過期機制
- 重要性評分
- 評分公式: `(相似度 * 時間衰減) * (0.8 + 重要性 * 0.4)`
- Consolidation (工作→情景)

**程式碼:**
```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional
import threading

@dataclass
class MemoryItem:
    """記憶項目"""
    id: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    importance: float = 0.5  # 0-1
    memory_type: str = "working"  # working | episodic
    year: int = 0
    
    def is_expired(self, ttl_seconds: int) -> bool:
        age = (datetime.now() - self.timestamp).total_seconds()
        return age > ttl_seconds


class CognitiveMemory:
    """Version 2: 基於 Hello-Agents 的認知記憶系統"""
    
    # 配置
    WORKING_CAPACITY = 10
    WORKING_TTL = 300  # 5 分鐘 (模擬時可調整)
    CONSOLIDATION_THRESHOLD = 0.7  # 重要性 > 0.7 轉情景
    DECAY_RATE = 0.95  # 每年衰減
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._working: List[MemoryItem] = []
        self._episodic: List[MemoryItem] = []
        self._lock = threading.Lock()
    
    # ===== 工作記憶 =====
    
    def add_working(
        self, 
        content: str, 
        importance: float = 0.5,
        year: int = 0
    ) -> MemoryItem:
        """添加到工作記憶"""
        with self._lock:
            # 容量檢查
            if len(self._working) >= self.WORKING_CAPACITY:
                # 移除最不重要的
                self._working.sort(key=lambda x: x.importance)
                self._working.pop(0)
            
            item = MemoryItem(
                id=f"wm_{datetime.now().timestamp()}",
                content=content,
                importance=importance,
                memory_type="working",
                year=year
            )
            self._working.append(item)
            return item
    
    # ===== 情景記憶 =====
    
    def add_episodic(
        self, 
        content: str, 
        importance: float = 0.7,
        year: int = 0
    ) -> MemoryItem:
        """添加到情景記憶 (永久)"""
        item = MemoryItem(
            id=f"em_{datetime.now().timestamp()}",
            content=content,
            importance=importance,
            memory_type="episodic",
            year=year
        )
        self._episodic.append(item)
        return item
    
    # ===== 記憶整合 =====
    
    def consolidate(self) -> int:
        """
        整合記憶: 高重要性工作記憶 → 情景記憶
        
        Returns: 整合數量
        """
        with self._lock:
            to_consolidate = [
                m for m in self._working 
                if m.importance >= self.CONSOLIDATION_THRESHOLD
            ]
            
            for m in to_consolidate:
                self._episodic.append(MemoryItem(
                    id=m.id.replace("wm_", "em_"),
                    content=m.content,
                    timestamp=m.timestamp,
                    importance=m.importance,
                    memory_type="episodic",
                    year=m.year
                ))
            
            return len(to_consolidate)
    
    # ===== 記憶檢索 =====
    
    def retrieve(
        self, 
        top_k: int = 5,
        current_year: int = 0
    ) -> List[str]:
        """
        檢索記憶 (優先工作記憶，補充情景記憶)
        
        評分公式: (相似度 * 時間衰減) * (0.8 + 重要性 * 0.4)
        """
        # 工作記憶 (按 recency + importance)
        working_scored = []
        for m in self._working:
            recency = 1.0 / (1 + (datetime.now() - m.timestamp).total_seconds() / 60)
            score = recency * 0.6 + m.importance * 0.4
            working_scored.append((score, m))
        
        working_sorted = sorted(working_scored, key=lambda x: x[0], reverse=True)
        results = [m.content for _, m in working_sorted[:top_k]]
        
        # 補充情景記憶
        if len(results) < top_k:
            remaining = top_k - len(results)
            episodic_scored = []
            
            for m in self._episodic:
                # 時間衰減
                years_passed = max(0, current_year - m.year)
                time_decay = self.DECAY_RATE ** years_passed
                
                # 評分公式
                score = time_decay * (0.8 + m.importance * 0.4)
                episodic_scored.append((score, m))
            
            episodic_sorted = sorted(episodic_scored, key=lambda x: x[0], reverse=True)
            for _, m in episodic_sorted[:remaining]:
                if m.content not in results:
                    results.append(m.content)
        
        return results
    
    # ===== 便捷方法 =====
    
    def update_after_flood(self, damage: float, year: int) -> None:
        """洪水後更新 (高重要性 → 情景記憶)"""
        content = f"Year {year}: A flood occurred causing ${damage:,.0f} in damages"
        self.add_episodic(content, importance=0.9, year=year)
    
    def update_after_decision(self, decision: str, year: int) -> None:
        """決策後更新 (中等重要性 → 工作記憶)"""
        content = f"Year {year}: I decided to {decision}"
        importance = 0.7 if decision != "do_nothing" else 0.3
        self.add_working(content, importance=importance, year=year)
```

---

## 3. 使用場景對照

| 場景 | Simple Memory (V1) | Cognitive Memory (V2) |
|------|-------------------|----------------------|
| **初始化** | `memory = SimpleMemory()` | `memory = CognitiveMemory(agent_id)` |
| **添加記憶** | `memory.add(content)` | `memory.add_working(content, importance)` |
| **檢索** | `memory.retrieve()` | `memory.retrieve(top_k=5, current_year)` |
| **洪水後** | `memory.update_after_flood(damage)` | `memory.update_after_flood(damage, year)` |
| **決策後** | `memory.update_after_decision(dec, year)` | `memory.update_after_decision(dec, year)` |
| **年末整合** | N/A | `memory.consolidate()` |

---

## 4. 模擬終止條件

**終止 = 洪水事件結束**

```python
# 來自 flood_years.csv
flood_years = [3, 4, 9]  # 例如

# 模擬結束條件
max_year = max(flood_years) + 1  # 洪水後再跑一年
```

---

## 5. 年度輸出記錄

**JSONL 格式 (skill_audit.jsonl):**

```json
{
  "year": 3,
  "agent_id": "Agent_1",
  "agent_type": "MG_Owner",
  "constructs": {
    "TP": {"level": "HIGH", "explanation": "Flood just occurred"},
    "CP": {"level": "MODERATE", "explanation": "Limited income but subsidy available"},
    "SP": {"level": "HIGH", "explanation": "Government offers 50% subsidy"},
    "SC": {"level": "MODERATE", "explanation": "Moderate trust in insurance"},
    "PA": {"level": "NONE", "explanation": "No previous adaptation"}
  },
  "decision_number": 2,
  "decision_skill": "elevate_house",
  "validated": true,
  "validation_warnings": ["R5: LOW threat but chose insurance - precautionary behavior"],
  "memory_used": ["Year 2: A flood...", "News about increasing..."],
  "context_hash": "abc123"
}
```
