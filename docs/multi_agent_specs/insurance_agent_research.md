# Insurance Company Agent: Deep Research Summary

## 研究概述

本文整理洪水保險市場 ABM 研究，為 Insurance Company Agent 設計提供參考。

---

## 1. 核心概念

### 1.1 NFIP Risk Rating 2.0 (FEMA 2021)

美國洪水保險改革的核心變革：

| 項目 | 舊制度 | Risk Rating 2.0 |
|------|--------|-----------------|
| **定價方式** | Zone-based (洪水區) | Property-specific (個別風險) |
| **考量因素** | 洪氾區位置 | 距水體距離、建築類型、高程、重建成本 |
| **更新頻率** | 靜態 | 動態調整 |
| **目標** | 簡單 | 公平性 + 財務穩定 |

**關鍵影響:**
- 96% 保戶: 保費變化 ≤ $20/月
- 年度漲幅上限: 主要住宅 18%, 其他 25%
- 高風險物件保費上漲誘因 → 鼓勵減災

---

### 1.2 ABM 文獻核心發現

**來源**: JASSS, ResearchGate, LSE, Cambridge

| 發現 | 說明 | 來源 |
|------|------|------|
| **動態風險評估** | 保費隨時間變化，反映風險演變 | jasss.org |
| **行為偏誤** | Salience bias: 災後保險購買率↑，效果隨時間衰減 | upenn.edu |
| **社會傳播** | 社交網絡影響保險購買決策 | efmaefm.org |
| **反饋循環** | 高保費 → 低 uptake → 更高保費 (潛在螺旋) | jasss.org |
| **政策評估** | ABM 可評估 Flood Re 等補貼計劃 | cam.ac.uk |

---

## 2. Insurance Agent 如何影響其他主體

### 2.1 對 Household 行為的影響

```
Insurance Premium Decision
        │
        ▼
┌───────────────────────────────────┐
│  Impact on Household Decision     │
├───────────────────────────────────┤
│ 1. 保費上漲 → Coping Perception ↓ │
│    - "Too expensive, cannot afford"│
│    - 低收入戶更敏感               │
│                                   │
│ 2. 保費上漲 → Do Nothing ↑        │
│    - 尤其無近期洪水經驗者         │
│                                   │
│ 3. 保費下降 → Insurance Uptake ↑  │
│    - 但 salience 仍是關鍵因素     │
└───────────────────────────────────┘
```

### 2.2 對 Government 政策的影響

| Insurance 行為 | Government 反應 |
|----------------|-----------------|
| 保費過高 → MG uptake 低 | 可能增加補助 |
| Loss ratio 高 | 可能介入補貼計劃 |
| 市場退出威脅 | 公私合作 (如 Flood Re) |

### 2.3 反饋循環 (Feedback Loops)

**潛在「死亡螺旋」:**
```
高洪水損失 → 高理賠 → 高保費 
    ↓
低風險戶退出 → 剩餘池風險更高
    ↓
更高保費 → 更多退出 → ...
```

**穩定機制:**
- Risk Rating 2.0 年度漲幅上限 (18%/25%)
- 政府補貼計劃 (NFIP, Flood Re)
- 減災誘因 (升高後保費降低)

---

## 3. 新視角: Insurance Agent 能解決的問題

### 3.1 動態過程模擬

**傳統 ABM 缺失:**
- 保費通常是靜態參數
- 未考慮保險公司反應

**加入 Insurance Agent 後可模擬:**
1. **保費-需求動態**: 保費變化如何影響 uptake
2. **風險調整**: 災後保費如何反應
3. **市場失靈**: 何時會出現「保險沙漠」

### 3.2 政策實驗

| 實驗 | 問題 |
|------|------|
| Risk-based vs Flat pricing | 哪種更促進減災？ |
| Premium cap 效果 | 上限如何影響市場穩定？ |
| MG-specific subsidy | 補助應該給誰？多少？ |

### 3.3 行為經濟學視角

**Prospect Theory 整合:**
- 損失 (premium) 被放大感知
- 保費漲幅比絕對值更重要
- Insurance Agent 可模擬「框架效應」

---

## 4. Insurance Agent 設計建議

### 4.1 State 設計

```python
@dataclass
class InsuranceAgent:
    id: str = "InsuranceCo"
    
    # === 核心指標 ===
    premium_rate: float = 0.05       # 基礎保費率
    loss_ratio: float = 0.0          # 理賠/收入
    
    # === 財務狀態 ===
    premium_collected: float = 0     # 本年保費收入
    claims_paid: float = 0           # 本年理賠
    risk_pool: float = 1_000_000     # 風險池
    
    # === 市場狀態 ===
    total_policies: int = 0          # 有效保單
    uptake_rate: float = 0.0         # 投保率
    
    # === 歷史記錄 ===
    premium_history: List[float] = field(default_factory=list)
    claims_history: List[float] = field(default_factory=list)
```

### 4.2 Skills 設計

| Skill | 條件 | 效果 | 約束 |
|-------|------|------|------|
| `raise_premium` | loss_ratio > 0.80 | +5-15% | 年上限 18% |
| `lower_premium` | loss_ratio < 0.30 | -5-10% | 留收益空間 |
| `maintain_premium` | 0.30 ≤ loss_ratio ≤ 0.80 | 不變 | 默認 |
| `adjust_payout_ratio` | 池餘額變化 | 80-100% | 高風險時考慮 |

### 4.3 決策觸發器

```python
def insurance_decision(self, context: dict) -> str:
    """Insurance agent 年度決策"""
    loss_ratio = self.claims_paid / max(self.premium_collected, 1)
    
    # Rule-based with LLM explanation
    if loss_ratio > 0.80:
        return "raise_premium"
    elif loss_ratio < 0.30 and self.uptake_rate < 0.40:
        # 低 uptake + 低 loss → 可降價吸引客戶
        return "lower_premium"
    else:
        return "maintain_premium"
```

---

## 5. 研究問題

### 5.1 可探索的問題

1. **保費彈性**: 保費上漲 X% → uptake 下降多少?
2. **MG 敏感度**: MG vs NMG 對保費變化反應差異?
3. **災後效應**: 災後 uptake spike 持續幾年?
4. **螺旋臨界點**: 何時會觸發「死亡螺旋」?

### 5.2 模型創新

| 現有 ABM | 本模型新增 |
|----------|-----------|
| 靜態保費 | 動態保費調整 |
| 外生 uptake | 內生 uptake (受保費影響) |
| 無保險公司 Agent | 有 Insurance Agent |
| 單向影響 | 雙向反饋 |

---

## 6. 參考文獻

1. FEMA Risk Rating 2.0 - fema.gov, floodsmart.gov
2. ABM Flood Insurance - JASSS (jasss.org)
3. Behavioral Economics - UPenn, Cambridge
4. Flood Re Evaluation - LSE, ResearchGate
