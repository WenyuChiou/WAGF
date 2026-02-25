# PMT Single-Agent Validator Literature Requirements

## Purpose

整理 Validator 驗證規則所需的實證文獻，聚焦於 **威脅感知如何影響洪水調適行為**。

---

## 核心構念 (Constructs) 與調適行為關係

### 研究問題框架

```
研究問題：TP/CP/SP 如何影響具體調適行為？

調適行為 (Actions):
├── buy_insurance    → 購買洪水保險
├── elevate_house    → 房屋墊高
├── relocate         → 遷居
└── do_nothing       → 不採取行動
```

---

## 1. Threat Perception (TP) → Adaptation Behavior

### 文獻方向

| 研究問題 | 需要找的文獻類型 | 對應 Validator Rule |
|----------|------------------|---------------------|
| HIGH TP → 何種行動？ | 迴歸分析、調查研究 | R1, R3 |
| LOW TP → do_nothing 合理？ | 行為預測模型 | R3 |
| TP 單獨作用 vs TP×CP 交互 | Meta-analysis | R1 |

### 關鍵發現 (已收集)

**Bamberg et al. (2017) Meta-analysis:**
- TP 與保護行為相關: r = 0.23
- 較 CP (r = 0.30) 弱
- **意涵**: TP 單獨不足以預測行為

**Grothmann & Reusswig (2006):**
- HIGH TP + LOW CP → Non-protective responses (denial/fatalism)
- **意涵**: HIGH TP + do_nothing 可能是 VALID 路徑

**Insurance Purchase Studies (MDPI, Princeton, UPenn):**
- Perceived damages, risk tolerance, wealth exposure → 保險購買正向預測
- Flood zone status → 顯著增加保險購買機率
- 1% premium increase → 19% 保險購買下降 (價格敏感)
- Past flood experience → 暫時增加購買，但效果隨時間衰減

### 需要補充的文獻

- [x] TP 對 insurance purchase 的具體迴歸係數 ✅
- [ ] TP threshold 效應 (多高算 HIGH?)
- [ ] TP 動態變化 (flood 後如何衰減?)

---

## 2. Coping Perception (CP) → Adaptation Behavior

### 文獻方向

| 研究問題 | 需要找的文獻類型 | 對應 Validator Rule |
|----------|------------------|---------------------|
| LOW CP → 不能做昂貴行動？ | 經濟可行性研究 | R2 |
| CP 子成分哪個最重要？ | 結構方程模型 | R2 |
| CP 如何影響不同行動？ | 比較研究 | R2 |

### 關鍵發現 (已收集)

**Bamberg et al. (2017):**
- CP 是更強預測因子: r = 0.30
- **意涵**: LOW CP → expensive action 高度不一致

**CP 子成分:**
- Response Efficacy (行動有效性)
- Self-Efficacy (自我效能)
- Response Cost (行動成本)

**House Elevation Studies (NIH, LSU, Frontiers):**
- High response efficacy + high self-efficacy → 顯著增加 elevation 採納
- Perceived response cost 對採納無顯著負向影響 (意外發現)
- 1-2 feet freeboard → 保險費節省顯著，高效益成本比
- Subsidies availability → 顯著增加 elevation decision
- **意涵**: LOW self-efficacy 預測不會選擇昂貴 elevation

### 需要補充的文獻

- [x] CP 與 elevate_house 決策的關係 ✅
- [ ] 財務能力 (affordability) 如何量化 CP
- [x] CP 與保險購買決策的關係 ✅

---

## 3. Stakeholder Perception (SP) → Adaptation Behavior

### 文獻方向

| 研究問題 | 需要找的文獻類型 | 對應 Validator Rule |
|----------|------------------|---------------------|
| LOW SP → 不買保險？ | 信任與保險研究 | R4, R5 |
| SP 如何影響政府計畫參與？ | 公共政策研究 | R4 |
| SP×TP 交互作用？ | PADM 實證研究 | R4, R5 |

### 關鍵發現 (已收集)

**PADM (Lindell & Perry, 2012):**
- SP = 對利益相關者的信任
- Low SP + Low TP → 無動機採取行動
- High trust may lower risk perception

**Flood Insurance Studies:**
- Trust in government/insurers 影響購買決策
- "Charity hazard": 預期政府救助 → 不買保險

### 需要補充的文獻

- [ ] SP 對 government buyout program 參與的影響
- [ ] LOW SP 情況下 fear override distrust 的實證
- [ ] Insurance company trust vs government trust 的差異

---

## 4. 現有 PMTConsistencyValidator Rules 與文獻對應

### 實際使用的 5 個驗證器 (v2_skill_governed)

```python
def create_default_validators():
    return [
        SkillAdmissibilityValidator(),    # 技術驗證
        ContextFeasibilityValidator(),     # 技術驗證
        InstitutionalConstraintValidator(), # 技術驗證
        EffectSafetyValidator(),           # 技術驗證
        PMTConsistencyValidator(),         # ← 需要 PMT 文獻支持
    ]
```

### PMTConsistencyValidator Rules 與文獻對應

| Rule # | Code Logic | 文獻支持 | 狀態 |
|--------|------------|----------|------|
| **Rule 1** | HIGH_THREAT + HIGH_EFFICACY + do_nothing = Error | Grothmann & Reusswig (2006) | ✅ |
| **Rule 2** | LOW_THREAT + relocate = Error | Rogers (1983) PMT | ✅ |
| **Rule 3** | Flood occurred + claims safe = Error | Germany/NZ/China flood experience studies | ✅ |
| **Rule 4** | CANNOT_AFFORD + expensive = Error | Bamberg (2017) CP as predictor | ✅ |

### Rule 詳細對應

**Rule 1: High threat + High efficacy + Do Nothing**
```python
HIGH_THREAT_KEYWORDS = ["worried", "concerned", "scared", "at risk", "dangerous", "vulnerable", "threatened"]
HIGH_EFFICACY_KEYWORDS = ["can protect", "effective", "would help", "prevent damage", "reduce risk"]
```
- **文獻**: Grothmann & Reusswig (2006) - HIGH TP + HIGH CP → Protection Motivation → Action
- **狀態**: ✅ 已有文獻支持

**Rule 2: Low threat + Relocate**
```python
LOW_THREAT_KEYWORDS = ["not worried", "safe", "no risk", "unlikely", "minimal"]
```
- **文獻**: Rogers (1983) PMT - Threat Appraisal 是採取極端行動的必要條件
- **狀態**: ✅ 已有文獻支持

**Rule 3: Flood occurred + Claims safe**
```python
if "flood occurred" in flood_status.lower():
    if any(kw in threat for kw in ["feel safe", "not worried", "no concern"]):
        errors.append(...)
```
- **文獻**: 
  - Germany (Saxony): 2200+ 居民調查 - 經歷洪水者更可能視洪水為威脅 (preventionweb.net)
  - NZ (Hutt Valley): 洪水經驗 → 風險感知上升 + 準備度提高 (REPEC)
  - China case study: "flood experience was strongly related to risk perception" (NIH)
- **狀態**: ✅ 已有文獻支持

**Rule 4: Cannot afford + Expensive option**
```python
CANNOT_AFFORD_KEYWORDS = ["cannot afford", "too expensive", "not enough money", "high cost", "financial burden"]
is_expensive = skill in ["elevate_house", "relocate"]
```
- **文獻**: Bamberg et al. (2017) - CP (r=0.30) 是行為預測因子
- **狀態**: ✅ 已有文獻支持

---

## 5. TP × CP 交互作用 → Validator Rules

### 驗證規則理論基礎

| Rule | Logic | 理論來源 | Severity |
|------|-------|----------|----------|
| **R1** | HIGH TP + HIGH CP → should act | Grothmann 2006 | Error |
| **R2** | LOW CP → cannot afford expensive | Bamberg 2017 | Error |
| **R3** | LOW TP → no extreme action | Rogers 1983 | Error |
| **R4** | LOW SP + LOW TP → no insurance | PADM | Error |
| **R5** | LOW SP + insurance (with threat) | Trust lit. | Warning |

### VALID 路徑 (非錯誤)

| TP | CP | Action | 理論解釋 |
|----|----|----|----------|
| HIGH | LOW | do_nothing | Fatalism/Denial (Grothmann 2006) |
| LOW | LOW | do_nothing | Rational non-action |
| MODERATE | MODERATE | any | Contextual decision |

---

## 5. 行動別文獻需求

### buy_insurance

**需要找：**
- Risk perception → insurance uptake 迴歸
- Trust → insurance decision
- Past flood experience → insurance purchase
- Premium affordability → uptake

**已知：**
- Perceived risk 正向影響保險購買
- Past flood experience 效果隨時間衰減
- Charity hazard 負向影響

### elevate_house

**需要找：**
- Cost-benefit analysis of elevation
- Subsidies → elevation decision
- Property characteristics → elevation choice

**已知：**
- 高成本行動需要 HIGH CP
- FEMA BFE 建議但實際需更高

### relocate

**需要找：**
- Place attachment → relocation decision
- Risk perception → willingness to relocate
- Government buyout participation factors

**已知 (NEW from empirical studies):**
- Extreme action 需要 HIGH TP
- **Place attachment 顯著負向減少遷居意願** (多國研究確認)
- 強 place attachment + high risk perception → 可能選擇其他保護行動
- Age, race, negative emotions → willingness to relocate 顯著
- Place attachment 多維度：genealogical, economic, social ties

### do_nothing

**需要找：**
- Non-protective responses 實證
- Denial/fatalism pathway 條件
- Inaction 的合理性條件

**已知：**
- HIGH TP + LOW CP → do_nothing 是 VALID
- LOW TP + LOW CP → do_nothing 是 Rational

---

## 6. 文獻搜尋關鍵詞

### English Keywords

```
PMT:
- "Protection Motivation Theory" flood adaptation behavior
- threat appraisal coping appraisal flood insurance
- self-efficacy response efficacy flood mitigation

Behavior-specific:
- flood insurance purchase determinants regression
- house elevation decision-making household
- relocation flood risk willingness survey
- non-protective responses flood denial fatalism

Trust/SP:
- trust government flood insurance uptake
- stakeholder perception protective action
- charity hazard disaster relief insurance
```

---

## 7. 下一步

1. [x] 使用 web search / Claude Code 搜尋上述關鍵詞 ✅
2. [x] 整理找到的實證研究結果 ✅
3. [ ] 更新 exp3_multi_agent_design.md 中的 Validator Rules
4. [ ] 確認每條 Rule 都有實證支持後再進入 EXECUTION

---

## 8. 實證支持總結

| Rule | 實證支持狀態 |
|------|-------------|
| R1: HIGH TP + HIGH CP + do_nothing | ✅ Grothmann 2006 |
| R2: LOW CP + expensive action | ✅ Bamberg 2017 + NIH elevation study |
| R3: LOW TP + extreme action | ✅ Rogers 1983 PMT |
| R4: LOW SP + LOW TP + insurance | ✅ PADM + charity hazard studies |
| R5: LOW SP + insurance (warning) | ✅ Trust literature |
| VALID: HIGH TP + LOW CP + do_nothing | ✅ Grothmann 2006 fatalism |

