# 洪水適應實驗範例 - Flood Adaptation Experiments

> **⚠️ 重要**: 本框架有兩個版本，請使用 **v2_skill_governed** (推薦)

---

## 架構總覽

![Example Flow](v2_skill_governed/example_flow.png)

**三層架構**: LLM Agent → Governed Broker → Simulation/World

| 層級 | 功能 | 對應模組 |
|------|------|---------|
| **LLM Agent** | 根據 PMT 評估產生決策 | ContextBuilder, Prompt |
| **Governed Broker** | 驗證決策一致性 | SkillBrokerEngine, Validators |
| **Simulation** | 執行狀態變更 | FloodSimulation |

---

## 版本比較

| 特徵 | V1 MCP (舊版) | V2 Skill-Governed (推薦) |
|------|--------------|-------------------------|
| **目錄** | `v1_mcp_flood/` | `v2_skill_governed/` |
| **驗證層數** | 1 層 (PMT keywords) | 5+ 層 |
| **財務一致性** | ❌ | ✅ Rule 4 |
| **結構化輸出** | 文本解析 | SkillProposal JSON |
| **Relocation Rate** | 高 (panic-driven) | 低 (rational) |

---

## 實驗設計

### 情境
- **100 agents** (homeowners) 在洪水易發區
- **10 年模擬** (洪水年份: 3, 4, 9)
- 每年根據 **Protection Motivation Theory (PMT)** 做決策

### Agent State (個體狀態)

```python
@dataclass
class FloodAgent:
    id: str
    elevated: bool = False           # 房屋已升高？
    has_insurance: bool = False      # 有洪水保險？
    relocated: bool = False          # 已遷移？
    
    # Trust attributes (影響 PMT 評估)
    trust_in_insurance: float = 0.3  # 對保險公司信任度
    trust_in_neighbors: float = 0.4  # 對鄰居判斷信任度
    
    memory: List[str] = []           # 最近 5 個記憶
    flood_threshold: float = 0.5     # 脆弱性感知
```

### 可用技能 (Skills)

| Skill | 描述 | 約束 | 狀態變更 |
|-------|------|------|---------|
| `buy_insurance` | 購買洪水保險 | 年度 (可續約) | `has_insurance = true` |
| `elevate_house` | 升高房屋 | **一次性** | `elevated = true` |
| `relocate` | 永久遷移 | **一次性, 永久** | `relocated = true` |
| `do_nothing` | 今年不採取行動 | 無 | 保險過期 |

---

## 驗證管線 (V2)

```
SkillProposal → [Admissibility] → [Feasibility] → [Constraints] → [EffectSafety] → [PMTConsistency] → Execution
                     ↓                ↓               ↓               ↓                ↓
                If FAIL → Reject with reason → Retry up to 2 times → Fallback to do_nothing
```

### 關鍵規則

| 規則 | 檢查內容 | 範例 |
|------|---------|------|
| **Rule 1** | High Threat + High Efficacy + Do Nothing | ❌ 矛盾 |
| **Rule 2** | Low Threat + Relocate | ❌ 過度反應 |
| **Rule 3** | Flood Occurred + Claims Safe | ❌ 認知不一致 |
| **Rule 4** ⭐ | Cannot Afford + Expensive Option | ❌ 財務矛盾 |

---

## 實驗結果

### 決策分佈比較

![Comparison Results](v2_skill_governed/comparison_results.png)

| Model | Total | Elevation | Insurance | Relocate | Do Nothing |
|-------|-------|-----------|-----------|----------|------------|
| Llama 3.2 | 814 | **587** (72%) | 192 (24%) | 47 (6%) | 153 (19%) |
| Gemma 3 | 999 | **799** (80%) | 206 (21%) | 1 (<1%) | 177 (18%) |
| GPT-OSS | 976 | **859** (88%) | 459 (47%) | 4 (<1%) | 51 (5%) |
| DeepSeek | 945 | **679** (72%) | 384 (41%) | 22 (2%) | 164 (17%) |

### Relocation Rate 改進

| Model | No MCP | Old MCP | **Skill-Governed** | 改進 |
|-------|--------|---------|-------------------|------|
| Llama 3.2 | 95% | 99% | **6%** | ↓ 93pp |
| Gemma 3 | 6% | 13% | **<1%** | ↓ 12pp |
| GPT-OSS | 0% | 2% | **<1%** | - |
| DeepSeek | 14% | 39% | **2%** | ↓ 37pp |

### Approval Rate

| Model | First-Pass | Retry Success | Rejected | Total |
|-------|------------|---------------|----------|-------|
| Llama | 752 (92%) | 58 (7%) | 4 (<1%) | **99.5%** |
| Gemma | 941 (94%) | 56 (6%) | 2 (<1%) | **99.8%** |
| GPT-OSS | 900 (92%) | 74 (8%) | 2 (<1%) | **99.8%** |
| DeepSeek | 876 (93%) | 67 (7%) | 2 (<1%) | **99.8%** |

---

## 結果分析

### 為什麼 Skill-Governed 更有效？

**問題 (舊版 MCP):**
```
LLM: "I'm scared and it's too expensive, but I'll relocate anyway"
Old MCP: ✅ PASS (無財務檢查)
→ 99% relocation rate (panic-driven, 非理性)
```

**解決方案 (Skill-Governed):**
```
LLM: "I'm scared and it's too expensive, but I'll relocate anyway"
Rule 4: ❌ REJECT ("Claims cannot afford but chose expensive option")
LLM Retry: "Given my budget, I'll elevate my house instead"
Skill-Governed: ✅ PASS
→ 6% relocation, 72% elevation (rational, budget-aware)
```

### Model-Specific 分析

| Model | 特性 | Without Framework | With Skill-Governed |
|-------|------|-------------------|---------------------|
| **Llama 3.2** | Panic-prone | 95% relocation | 6% relocation + 72% elevation |
| **Gemma 3** | Conservative | 6% relocation | <1% relocation + 80% elevation |
| **GPT-OSS** | Balanced | 0% relocation | 88% elevation + 47% insurance |
| **DeepSeek** | Moderate | 39% (worsened by old MCP) | 2% relocation + 72% elevation |

---

## Trust 動態更新

| 情境 | 保險信任 Δ | 鄰居信任 Δ |
|------|-----------|-----------|
| 有保險 + 受災 | -0.10 (理賠麻煩) | 依社區 |
| 有保險 + 安全 | +0.02 (安心) | - |
| 無保險 + 受災 | +0.05 (教訓) | -0.05 (若社區行動率低) |
| 無保險 + 安全 | -0.02 (僥倖) | - |

社區行動率 > 30% → 鄰居信任 +0.04

---

## 使用問卷資料

框架支援從 CSV 載入真實問卷資料：

```csv
id,elevated,has_insurance,trust_in_insurance,trust_in_neighbors,age,income,education
Agent_1,False,False,0.35,0.45,45,high,master
Agent_2,False,True,0.52,0.38,32,middle,bachelor
```

將 `agent_initial_profiles.csv` 放在框架根目錄，自動載入。

---

## 運行實驗

```bash
# V2 推薦
cd examples/v2_skill_governed
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10

# V1 (僅供比較)
cd examples/v1_mcp_flood
python run.py --model llama3.2:3b --num-agents 100 --num-years 10
```

---

## 輸出檔案

```
results/
├── simulation_log.csv      # 所有決策與狀態
├── skill_audit.jsonl       # 完整審計追蹤 (每步)
└── audit_summary.json      # 彙總統計
```
