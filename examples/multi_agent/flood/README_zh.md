# LLM 治理多代理洪水調適模擬 (Paper 3)

> **目標期刊**：Water Resources Research (WRR)
> **框架**：SAGE (Simulated Agent Governance Engine) 搭配 SAGA 三層排序
> **研究區域**：Passaic River Basin (PRB), 美國紐澤西州
> **狀態**：ICC 驗證完成 (TP ICC=0.964, CP ICC=0.947)，主要實驗進行中

---

## 目錄

1. [專案概述](#1-專案概述)
2. [理論基礎](#2-理論基礎)
3. [研究問題與假設](#3-研究問題與假設)
4. [模擬架構](#4-模擬架構)
5. [代理初始化流程](#5-代理初始化流程)
6. [PMT 構面設計](#6-pmt-構面設計)
7. [記憶架構](#7-記憶架構)
8. [治理框架](#8-治理框架)
9. [機構代理](#9-機構代理)
10. [社交網路與資訊管道](#10-社交網路與資訊管道)
11. [災害與深度損害模型](#11-災害與深度損害模型)
12. [驗證框架](#12-驗證框架)
13. [經驗基準](#13-經驗基準)
14. [ICC 探測協議](#14-icc-探測協議)
15. [如何執行](#15-如何執行)
16. [輸出結構](#16-輸出結構)
17. [與傳統 ABM 的關鍵差異](#17-與傳統-abm-的關鍵差異)
18. [計算需求](#18-計算需求)
19. [詞彙表](#19-詞彙表)
20. [參考文獻](#20-參考文獻)

---

## 1. 專案概述

### 核心主張

我們主張**結構合理性 (structural plausibility)**，而非預測準確性。LLM-ABM 產生個體異質的調適軌跡，落在經驗可辯護的總體範圍內——這是傳統方程式 ABM 在沒有大幅增加規格複雜度的情況下無法達成的。

### 本框架展示的能力

1. **記憶中介認知** 取代參數化威脅感知 (TP) 衰減方程式
2. **湧現式構面** — PMT 評估是 LLM 輸出，非預設輸入
3. **個體異質性** — 每個代理累積獨特的經驗與記憶
4. **內生機構** — 政府與保險代理由 LLM 驅動
5. **多管道社會影響** — 觀察、八卦、新聞媒體、社群媒體

### 研究區域

- **Passaic River Basin (PRB)**，紐澤西州
- 27 個普查區，涵蓋都市、郊區及鄉村洪氾區
- 真實洪災資料：13 個 ESRI ASCII 柵格檔案 (2011-2023)
- 網格大小：約 457 × 411 格，30m 解析度
- 歷史事件：颶風艾琳 (2011)、超級風暴珊迪 (2012)、艾達 (2021)

---

## 2. 理論基礎

### 保護動機理論 (PMT)

本框架以 **保護動機理論** (Rogers, 1983; Grothmann & Reusswig, 2006) 為基礎，該理論指出保護行為源於兩個認知評估過程：

| 評估類型 | 構面 | 評估內容 |
|----------|------|----------|
| **威脅評估** | TP (威脅感知) | 洪災損害的感知機率與嚴重性 |
| **因應評估** | CP (因應感知) | 保護行動的自我效能與反應效能 |

我們從文獻中擴展 PMT，加入三個額外構面：

| 構面 | 來源 | 框架中的角色 |
|------|------|-------------|
| **SP (利害關係人感知)** | PADM (Lindell & Perry, 2012) | 對機構的信任 (NJDEP, FEMA) |
| **SC (社會資本)** | Adger (2003); Aldrich (2012) | 社交網路資源與社區連結 |
| **PA (地方依附)** | Bonaiuto et al. (2016) | 對家園/社區的情感連結 |

### 保護行動決策模型 (PADM)

本框架也整合了 **PADM** (Lindell & Perry, 2012) 的概念：

- **資訊搜尋行為**：代理透過多個管道接收資訊
- **利害關係人感知**：對政府/保險的信任影響行動採納
- **社會線索**：鄰居行動影響風險感知

### PMT/PADM 整合方式

```
                    ┌─────────────────────────────────────────┐
                    │            資訊管道                      │
                    │  觀察 | 八卦 | 新聞 | 社群媒體           │
                    └─────────────────┬───────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LLM 推理                                   │
│  人設 + 記憶 + 環境情境 + 政策資訊                               │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ 威脅        │  │ 因應        │  │ 利害關係人   │             │
│  │ 評估        │  │ 評估        │  │ 感知         │             │
│  │ (TP)        │  │ (CP)        │  │ (SP)        │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         │                │                │                     │
│  ┌──────┴──────┐  ┌──────┴──────┐                              │
│  │ 社會        │  │ 地方        │                              │
│  │ 資本        │  │ 依附        │                              │
│  │ (SC)        │  │ (PA)        │                              │
│  └─────────────┘  └─────────────┘                              │
└─────────────────────────┬───────────────────────────────────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │      治理層           │
              │  驗證 TP×CP→行動     │
              └───────────┬───────────┘
                          │
                          ▼
              ┌───────────────────────┐
              │      決策輸出         │
              │  buy_insurance,       │
              │  elevate_house 等     │
              └───────────────────────┘
```

---

## 3. 研究問題與假設

三個 RQ 皆由**單一統合實驗**（全功能 LLM-ABM）回答。敘事進程：**個體 → 機構 → 集體**。

### RQ1：個體記憶與路徑分歧

> **個人洪災損害記憶的差異累積如何造成群組內調適時機的分歧，且這種分歧是否不成比例地延遲財務受限家戶的調適？**

**重要澄清**：RQ1 是關於**同一人口統計群組內不同代理**因不同個人經歷而分歧——並非讓同一個代理跑很多次。

**範例**：
- H0023 (MG-Owner) 住在高風險區 → 第1年經歷 $85K 損害 → TP 上升 → 購買保險
- H0047 (MG-Owner) 住在低風險區 → 無洪災損害 → TP 不變 → do_nothing
- 兩者都是 MG-Owner，有相似的初始特徵，但**個人洪災經歷**（由空間位置決定）創造了分歧的調適軌跡

**假設 H1**：累積個人洪災損害記憶的家戶，比具有相同初始特徵但僅有間接暴露的家戶展現更快的調適採納。此「經驗-調適差距」在 MG 家戶中因財務限制而更大。

**否證標準**：
- Cox PH 交互項 (personal_damage × MG_status) 在 α=0.05 顯著
- MG 的風險比 ≥ NMG 的 1.5 倍
- 若否證：記憶-調適路徑未受 MG 調節

**關鍵指標**：
- 每年群組內 TP 變異數（傳統 ABM 建構上 = 0）
- Cox PH 存活分析（首次調適時間）
- 路徑熵（行動序列的夏農熵）
- 記憶顯著性分數（決策時的 top-k 記憶）

### RQ2：機構回饋與保護不平等

> **反應式機構政策——補助調整與 CRS 中介的保費折扣——是否在十年尺度上縮小或擴大邊緣化與非邊緣化家戶之間的累積保護差距？**

**假設 H2a**：高 MG 損害洪水事件後的政府補助增加來得太遲，無法阻止累積損害差距擴大。
- 否證：補助-調適延遲 < 2 年且 MG-NMG 差距縮小

**假設 H2b**：高損失年度後的 CRS 折扣削減對最低收入家戶產生「可負擔性螺旋」。
- 否證：有效保費增加 1 個百分點 → 最低收入四分位的 P(流失) 增加 ≥5%

**關鍵指標**：
- 補助-調適延遲（交叉相關，以年為單位）
- 保費-退保相關（panel 迴歸）
- 累積損害基尼係數
- 保護差距（每年無調適的 MG 比例 vs NMG）

### RQ3：社會資訊與調適擴散

> **哪些資訊管道最有效地加速洪氾社區的持續保護行動擴散？**

**假設 H3a**：具有活躍社群媒體的社區展現較快的初期調適採納，但與觀察+新聞相比，持續採納較慢。
- 否證：第3年採納超過僅觀察 >10%；到第10年差異反轉

**假設 H3b**：八卦中介的推理傳播比簡單觀察產生更強的調適聚集。

**關鍵指標**：
- 資訊-行動引用率（推理文本引用各管道的比例）
- 調適聚集（社交網路上的 Moran's I）
- 社會傳染半衰期（受災代理 50% 鄰居調適的時間）
- 推理傳播深度（透過八卦鏈追蹤片語）

---

## 4. 模擬架構

### 高階架構

```
┌─────────────────────────────────────────────────────────────────┐
│                    SAGE 治理框架                                 │
├─────────────────────────────────────────────────────────────────┤
│  第1層：提示詞      │  人設 + 記憶 + 情境                        │
│  第2層：LLM        │  Gemma 3 4B (temp=0.7, ctx=8192)          │
│  第3層：治理       │  SAGA 規則 + 財務限制                      │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    SAGA 三層排序                                 │
├─────────────────────────────────────────────────────────────────┤
│  第1層：政府       │  NJDEP Blue Acres (補助決策)               │
│  第2層：保險       │  FEMA/NFIP CRS (保費決策)                  │
│  第3層：家戶       │  400 個代理 (屋主/租客決策)                │
└─────────────────────────────────────────────────────────────────┘
```

### 模擬時間線

- **期間**：13 年 (2011-2023)
- **災害**：每年真實 PRB 洪水柵格資料
- **代理數量**：400（平衡 4 格設計）
- **種子**：10 次獨立執行以確保隨機穩健性

### 年度循環

```
年前鉤子：
  1. 載入當年洪水柵格
  2. 解決待處理行動（抬升完成、收購定案）
  3. 計算每代理洪水深度

SAGA 第1層（政府）：
  4. NJDEP 接收：損害報告、MG/NMG 採納率、預算
  5. NJDEP 決定：增加/減少/維持補助 (±5%)

SAGA 第2層（保險）：
  6. FEMA 接收：理賠紀錄、投保率、損失率
  7. FEMA 決定：改善/削減/維持 CRS 折扣 (±5%)

SAGA 第3層（家戶）：
  8. 對每個家戶代理：
     a. 擷取相關記憶
     b. 建構提示詞（人設 + 情境 + 政策資訊）
     c. LLM 產生決策 + PMT 構面標籤
     d. 治理驗證構面-行動一致性
     e. 驗證失敗時重試（最多 3 次）
     f. 記錄到審計 CSV
     g. 將決策編碼為新記憶

年後鉤子：
  9. 使用 HAZUS 曲線計算洪災損害
  10. 處理保險理賠與給付
  11. 產生洪災經歷記憶
  12. 透過社交網路傳播八卦
  13. 對每個代理執行年度反思
```

---

## 5. 代理初始化流程

### 概述

此流程將原始問卷資料轉換為 400 個可模擬的代理，具有真實人設、空間分配和初始記憶。

```
977 份 Qualtrics 回應
        │
        ▼ (NJ 郵遞區號過濾：07xxx, 08xxx)
755 位 NJ 受訪者
        │
        ▼ (BalancedSampler：每格 100 人)
400 個代理（平衡 4 格設計）
        │
        ▼ (RCV 生成 + 空間分配)
400 個具有財產 + 位置的代理
        │
        ▼ (記憶種子：6 範本 × 400)
2,400 個初始記憶
```

### 步驟 1：問卷清理

**腳本**：`paper3/process_qualtrics_full.py`

**輸入**：`cleaned_complete_data_977.xlsx`（Qualtrics 清理後 920 個有效列）

**處理**：
1. 以郵遞區號過濾至 NJ 居民 (07xxx, 08xxx)
2. 解析 PMT 構面項目（Likert 1-5 量表）：
   - SC：6 題 (Q21_1-6) — 社會資本
   - PA：9 題 (Q21_7-15) — 地方依附
   - TP：11 題 (Q22_1-11) — 威脅感知
   - CP：8 題 (Q24_1-2, Q25_1-2,4-5,7-8) — 因應感知
   - SP：3 題 (Q25_3,6,9) — 利害關係人感知
3. 分類 MG 狀態（符合 3 項中的 2 項以上）
4. 提取人口統計、洪災歷史、保險狀態

**輸出**：`data/cleaned_survey_full.csv`（約 755 位 NJ 受訪者）

**為何是 755 而非 920？** 原始 Qualtrics 資料包含多州受訪者。我們過濾至僅 NJ，因為研究區域是 Passaic River Basin。

### 步驟 2：平衡抽樣

**腳本**：`paper3/prepare_balanced_agents.py`

**設計**：4 格因子設計 (MG × 房屋權屬)

| 格 | MG 狀態 | 權屬 | N | 洪氾區 % |
|----|---------|------|---|----------|
| A | MG | 屋主 | 100 | 70% |
| B | MG | 租客 | 100 | 70% |
| C | NMG | 屋主 | 100 | 50% |
| D | NMG | 租客 | 100 | 50% |

**為何每格 100 人？** Cox PH 存活分析（含交互項）的統計檢定力分析要求每子群 N≥50。每格 100 提供退出（遷移、收購）的緩衝。

**抽樣方法**：分層隨機抽樣，若層數不足 100 則放回抽樣。

### 步驟 3：RCV 生成

**重置成本價值 (RCV)** 決定洪災損害規模與保險覆蓋。

**屋主建築 RCV**：
```python
# 對數常態分布
mu_MG = $280,000   # MG 屋主：較低房產價值
mu_NMG = $400,000  # NMG 屋主：較高房產價值
sigma = 0.3        # 對數尺度標準差

rcv = np.random.lognormal(np.log(mu), sigma)
rcv = np.clip(rcv, 100_000, 1_000_000)  # 邊界
```

**屋主內容物 RCV**：建築 RCV 的 30-50%（均勻分布）

**租客**：無建築 RCV（結構由房東擁有）
```python
# 僅內容物，按收入縮放
base = 20_000
income_factor = income / 100_000 * 40_000
rcv_contents = np.random.normal(base + income_factor, 5_000)
rcv_contents = np.clip(rcv_contents, 10_000, 80_000)
```

### 步驟 4：空間分配

**資料**：真實 PRB ESRI ASCII 柵格（2021 參考年）

**分配邏輯**：
1. 解析網格 metadata：`ncols`, `nrows`, `xllcorner`, `yllcorner`, `cellsize`
2. 依洪水深度分層格子：
   - `dry`：深度 = 0
   - `shallow`：0 < 深度 ≤ 0.3m
   - `moderate`：0.3m < 深度 ≤ 1.0m
   - `deep`：1.0m < 深度 ≤ 4.0m
   - `very_deep`：深度 > 4.0m
3. 依洪災歷史分配代理：
   - 問卷 flood_experience=True + flood_freq≥2 → deep/very_deep 格子
   - 問卷 flood_experience=True + flood_freq<2 → shallow/moderate 格子
   - 問卷 flood_experience=False → MG 70% / NMG 50% 在洪氾區，其餘在乾燥區
4. 將網格 (row, col) 轉換為經緯度：
   ```python
   lon = xllcorner + col * cellsize
   lat = yllcorner + (nrows - 1 - row) * cellsize
   ```

**輸出欄位**：`grid_x`, `grid_y`, `latitude`, `longitude`, `zone_label` (LOW/MEDIUM/HIGH)

### 步驟 5：記憶種子

**每代理 6 個標準範本**（總計：2,400 個初始記憶）：

| 範本 | 內容模式 | 來源 |
|------|----------|------|
| `flood_experience` | 「我在過去 [X] 年經歷了 [N] 次洪水...」 | 問卷 Q14, Q17 |
| `insurance_history` | 「我[有/沒有]洪水保險，因為...」 | 問卷 Q26 |
| `social_connections` | 「我的鄰居[依 SC 分數描述]...」 | 問卷 Q21_1-6 |
| `government_trust` | 「我[信任/不信任]政府洪水計畫，因為...」 | 問卷 Q25_3,6,9 |
| `place_attachment` | 「我在這裡住了 [X] 年，感覺[依附/準備離開]...」 | 問卷 Q21_7-15 |
| `flood_zone` | 「我的房產位於 [區域]，年洪水機率 [X]%...」 | 空間分配 |

**輸出**：`data/initial_memories_balanced.json`

---

## 6. PMT 構面設計

### 構面作為輸出，而非輸入

**關鍵設計原則**：在傳統 ABM 中，PMT 構面是**輸入**（從分布預先初始化）。在我們的 LLM-ABM 中，構面是推理的**輸出**。

```
傳統 ABM：
  TP_initial ~ Beta(α, β)  →  Decision = f(TP, CP, ...)

LLM-ABM：
  人設 + 記憶 + 情境  →  LLM 推理  →  TP, CP, SP, SC, PA 標籤
                                    →  決策
```

### 五個 PMT 構面

| 構面 | 標籤量表 | 治理角色 | 分析角色 |
|------|----------|----------|----------|
| **TP** (威脅感知) | VL/L/M/H/VH | **強制執行** via thinking_rules | RQ1：記憶-TP 路徑 |
| **CP** (因應感知) | VL/L/M/H/VH | **強制執行** via thinking_rules | RQ1：財務限制 |
| **SP** (利害關係人感知) | VL/L/M/H/VH | 記錄，不強制 | RQ2：機構信任 |
| **SC** (社會資本) | VL/L/M/H/VH | 記錄，不強制 | RQ3：社會影響 |
| **PA** (地方依附) | VL/L/M/H/VH | 記錄，不強制 | RQ3：遷移抗拒 |

### 為何 SC 和 PA 不強制治理

**設計理由**：
1. **TP + CP 是 PMT 核心驅動** — 直接決定保護動機
2. **SC 調節社會影響** — 影響代理如何權衡鄰居資訊，但不應阻擋決策
3. **PA 調節遷移抗拒** — 情境調節因子，非硬性限制

**SC 和 PA 的處理方式**：
- 從每個 LLM 回應解析（必要構面）
- 記錄在每個代理-年的審計 CSV
- 用於 ICC 驗證（信度測試）
- 在 RQ3 分析（高 SC 代理是否因社會影響而更快採納？）

### 治理規則（僅 TP/CP）

**屋主 thinking_rules**：

| 規則 ID | 條件 | 封鎖技能 | 等級 |
|---------|------|----------|------|
| `owner_inaction_high_threat` | TP∈{H,VH} AND CP∈{M,H,VH} | do_nothing | ERROR |
| `owner_fatalism_allowed` | TP∈{H,VH} AND CP∈{VL,L} | do_nothing | WARNING |
| `owner_complex_action_low_coping` | CP∈{VL,L} | elevate_house, buyout_program | ERROR |

**租客 thinking_rules**：

| 規則 ID | 條件 | 封鎖技能 | 等級 |
|---------|------|----------|------|
| `renter_inaction_high_threat` | TP∈{H,VH} AND CP∈{M,H,VH} | do_nothing | ERROR |
| `renter_fatalism_allowed` | TP∈{H,VH} AND CP∈{VL,L} | do_nothing | WARNING |
| `renter_complex_action_low_coping` | CP∈{VL,L} | relocate | ERROR |

**「fatalism_allowed」規則保留了風險感知矛盾**：具有高威脅感知但低因應能力的代理，可能因資源限制而理性選擇不行動。這是 WARNING（記錄）而非 ERROR（封鎖）。

---

## 7. 記憶架構

### UnifiedCognitiveEngine

取代傳統 ABM 的參數化 TP 衰減方程式。

**關鍵參數**（來自 `ma_agent_types.yaml`）：

| 參數 | 值 | 用途 |
|------|-----|------|
| `importance_decay` | 0.1/年 | 記憶隨時間衰減 |
| `window_size` | 5 年 | 提示詞的擷取視窗 |
| `consolidation_threshold` | 0.6 | 合併相似記憶 |
| `ranking_mode` | weighted | 重要性 × 新近性 × 相關性 |

**情緒權重**：

| 類別 | 權重 | 範例 |
|------|------|------|
| 重大威脅 | 1.2 | 洪災損害、財務損失 |
| 輕微正面 | 0.8 | 收到補助、鄰居抬升 |
| 中性 | 0.3 | 政策公告、無洪水 |

**來源權重**：

| 來源 | 權重 | 理由 |
|------|------|------|
| 個人經驗 | 1.0 | 直接經驗最顯著 |
| 鄰居（八卦）| 0.7 | 社會證據，但二手 |
| 新聞媒體 | 0.5 | 總體資訊，較不個人 |
| 社群媒體 | 0.4-0.8 | 可變可靠性 |

### 記憶中介 TP（vs. 參數衰減）

**傳統 ABM**（SCC 論文）：
```python
# 同一普查區的所有代理有相同 TP 軌跡
TP(t) = tau_inf + (tau_0 - tau_inf) * exp(-alpha * t)
```

**LLM-ABM**：
```python
# 每個代理基於個人記憶有獨特 TP
memories = retrieve_top_k(agent_id, k=5)
prompt = construct_prompt(persona, memories, context)
response = llm.generate(prompt)
TP_label = parse_construct(response, "TP")  # 從推理湧現
```

**結果**：群組內 TP 變異數 > 0（傳統 ABM 建構上不可能）。

---

## 8. 治理框架

### SAGA (SAGE Agent Governance Architecture)

**三層排序**確保機構決策在同一年影響家戶提示詞：

```
第 N 年：
  1. 政府代理決定 subsidy_rate
  2. 保險代理決定 crs_discount
  3. 家戶代理在提示詞中收到更新的費率
```

### 驗證管線

對每個家戶決策：

```
LLM 回應
     │
     ▼
┌─────────────────────────────────────────┐
│         結構驗證                        │
│  - JSON 格式正確？                      │
│  - 所有必要欄位存在？                   │
│  - 構面標籤有效 (VL/L/M/H/VH)？        │
└─────────────────┬───────────────────────┘
                  │ 通過
                  ▼
┌─────────────────────────────────────────┐
│         身分規則                        │
│  - 已抬升？封鎖 elevate                │
│  - 已遷移？封鎖全部                     │
│  - 租客？封鎖 elevate/buyout           │
└─────────────────┬───────────────────────┘
                  │ 通過
                  ▼
┌─────────────────────────────────────────┐
│         思維規則                        │
│  - 高 TP + 高 CP + do_nothing？        │
│  - 低 CP + 昂貴行動？                  │
└─────────────────┬───────────────────────┘
                  │ 通過
                  ▼
┌─────────────────────────────────────────┐
│         財務限制                        │
│  - 負擔得起抬升費用？                   │
│  - 負擔得起保費？                       │
└─────────────────┬───────────────────────┘
                  │ 通過
                  ▼
            決策接受
```

### 重試機制

若驗證失敗：
1. 產生說明錯誤的介入訊息
2. 附加到提示詞並重新查詢 LLM
3. 最多 3 次重試
4. 若所有重試失敗：記錄為「REJECTED」並繼續（保留供分析）

---

## 9. 機構代理

### NJ 政府（NJDEP Blue Acres 管理員）

**角色**：管理洪水收購補助

**接收的情境**：
- 社區洪災損害報告（總金額，依 MG/NMG）
- 當前調適率（依格）
- 預算狀態與使用率
- 歷史補助效果

**行動**：

| 行動 | 效果 | 觸發邏輯 |
|------|------|----------|
| `increase_subsidy` | +5% 補助率 | 高 MG 損害，低 MG 採納 |
| `decrease_subsidy` | -5% 補助率 | 預算限制，高採納 |
| `maintain_subsidy` | 無變化 | 穩定狀況 |

**補助範圍**：20%-95%

### FEMA/NFIP CRS 管理員

**角色**：管理社區評級系統折扣

**接收的情境**：
- 理賠紀錄與損失率
- 保險採納率
- CRS 活動分數
- 償付能力指標

**行動**：

| 行動 | 效果 | 觸發邏輯 |
|------|------|----------|
| `improve_crs` | +5% CRS 折扣 | 良好損失率，有投資能力 |
| `reduce_crs` | -5% CRS 折扣 | 高損失率，償付能力問題 |
| `maintain_crs` | 無變化 | 穩定狀況 |

**有效保費**：`base_premium × (1 - crs_discount)`

**CRS 折扣範圍**：0%-45%

---

## 10. 社交網路與資訊管道

### 網路結構

- **每代理鄰居數**：5
- **同區域權重**：70%（代理更可能在其洪水區內連結）
- **網路類型**：小世界（高聚集、短路徑長度）

### 四個資訊管道

| 管道 | 延遲 | 可靠性 | 最大項目 | 內容 |
|------|------|--------|----------|------|
| **觀察** | 0 | 1.0 | 5 鄰居 | 抬升/投保/遷移狀態 |
| **八卦** | 0 | 變動 | 2 則訊息 | 決策推理 + 洪災經歷 |
| **新聞媒體** | 1 年 | 0.9 | — | 社區調適率、政策變化 |
| **社群媒體** | 0 | 0.4-0.8 | 3 則貼文 | 抽樣貼文，誇大因子=0.3 |

### 八卦過濾

並非所有資訊都會傳播：
- **重要性門檻**：0.5（僅分享重要經歷）
- **類別**：decision_reasoning, flood_experience, adaptation_outcome
- **衰減**：八卦重要性隨網路距離衰減

### 提示詞中的資訊

代理收到結構化的資訊區塊：

```
## 社會資訊

### 你觀察到的
- 鄰居 H0042 去年抬升了房屋
- 鄰居 H0089 購買了洪水保險

### 你聽到的（八卦）
- 「我的鄰居抬升是因為去年洪水損壞了他們的地下室。
   他們說補助讓這變得負擔得起。」（來自 H0042）

### 近期新聞
- 社區整體：35% 的家戶現在有洪水保險（從 28% 上升）
- 政府宣布抬升補助增加 5%

### 社群媒體（可靠性：變動）
- 貼文：「又一次洪水警報！他們什麼時候要修排水系統？」（12 讚）
- 貼文：「剛收到保險理賠，花了 3 個月但值得」（8 讚）
```

---

## 11. 災害與深度損害模型

### 災害資料

**來源**：13 個 ESRI ASCII 柵格檔案 (2011-2023)，來自 PRB 洪水模型

**格式**：`.asc` 檔案含標頭：
```
ncols         457
nrows         411
xllcorner     -74.5
yllcorner     40.6
cellsize      0.00027778
NODATA_value  -9999
```

**每代理深度**：每個代理的洪水深度從其 (grid_x, grid_y) 格子讀取。

### HAZUS-MH 深度損害曲線

**來源**：FEMA HAZUS-MH 技術手冊 (2022)

**曲線類型**：住宅結構的 20 點分段線性曲線

**結構類型**：
- 1 層有地下室
- 2 層有地下室
- 錯層式
- 1 層無地下室
- 2 層無地下室

**範例曲線**（1 層有地下室，結構）：

| 深度 (ft) | 損害 % |
|-----------|--------|
| -2 | 8% |
| 0 | 16% |
| 1 | 23% |
| 2 | 33% |
| 4 | 47% |
| 8 | 68% |
| 12+ | 75% |

### 一樓高程 (FFE) 調整

```python
effective_depth = flood_depth - elevation_ft

if effective_depth <= 0:
    damage = 0  # 洪水低於一樓
else:
    damage = hazus_curve(effective_depth) * RCV
```

**範例**：代理抬升 5ft，洪水深度 4ft → effective_depth = -1ft → $0 損害

### 保險給付計算

```python
# NFIP 覆蓋限額
STRUCTURE_LIMIT = 250_000
CONTENTS_LIMIT = 100_000
DEDUCTIBLE = 2_000  # 預設

# 計算覆蓋金額
covered_structure = min(structure_damage, STRUCTURE_LIMIT)
covered_contents = min(contents_damage, CONTENTS_LIMIT)
gross_claim = covered_structure + covered_contents

# 扣除自負額
payout = max(0, gross_claim - DEDUCTIBLE)
out_of_pocket = total_damage - payout
```

---

## 12. 驗證框架

### 三層驗證

| 層級 | 焦點 | 時機 | 需要 LLM？ |
|------|------|------|:----------:|
| **L1 微觀** | 每決策一致性 | 事後 | 否 |
| **L2 宏觀** | 總體合理性 | 事後 | 否 |
| **L3 認知** | LLM 信度 | 實驗前 | 是 |

### L1 微觀指標

| 指標 | 門檻 | 測試內容 |
|------|------|----------|
| **CACR** (構面-行動一致率) | ≥ 0.80 | TP/CP 標籤是否符合 PMT 的選擇行動？ |
| **R_H** (幻覺率) | ≤ 0.10 | 物理不可能（重複抬升等） |
| **EBE** (有效行為熵) | > 0 | 決策是多樣還是崩塌？ |

**CACR 計算**：

```python
for each (agent, year) observation:
    if PMT_coherent(TP_label, CP_label, action):
        coherent_count += 1
CACR = coherent_count / total_observations
```

### L2 宏觀指標

| 指標 | 門檻 | 測試內容 |
|------|------|----------|
| **EPI** (經驗合理性指數) | ≥ 0.60 | 8 個基準中在經驗範圍內的比例 |

**EPI 計算**：

```python
for each benchmark in 8_benchmarks:
    observed = compute_from_audit_csv(benchmark)
    if within_range(observed, benchmark.low, benchmark.high, tolerance=0.30):
        score += benchmark.weight
EPI = score / total_weight
```

### L3 認知指標

| 指標 | 門檻 | 測試內容 |
|------|------|----------|
| **ICC(2,1)** | ≥ 0.60 | 重測信度（相同人設，30 次重複） |
| **eta-squared** | ≥ 0.25 | 原型間效應量 |
| **方向通過率** | ≥ 75% | 人設/刺激驅動行為 |

#### ICC(2,1) 計算方法

**組內相關係數（雙向隨機，單一測量）**：

```python
# 資料結構：15 原型 × 6 情境 × 30 重複 = 2,700 回應
# 每個 (原型, 情境) 單元：30 次重複測量

# 將 TP/CP 標籤轉為數值：VL=1, L=2, M=3, H=4, VH=5
def label_to_numeric(label):
    return {"VL": 1, "L": 2, "M": 3, "H": 4, "VH": 5}[label]

# 雙向 ANOVA 分解
# Y_ijk = μ + α_i + β_j + ε_ijk
# 其中：i = 原型×情境單元, j = 重複次數, k = 觀察值

MS_between = variance_between_cells      # 單元間變異
MS_within = variance_within_replicates   # 單元內（殘差）變異

# ICC(2,1) 公式：單一評分者的一致性
ICC_21 = (MS_between - MS_within) / (MS_between + (k-1)*MS_within)
# 其中 k = 重複次數 (30)

# 95% CI 透過 F 分布
F_value = MS_between / MS_within
df_between = n_cells - 1      # 90 - 1 = 89
df_within = n_cells * (k - 1) # 90 * 29 = 2610
```

**解釋門檻** (Koo & Li, 2016)：

- ICC < 0.50：信度差
- 0.50 ≤ ICC < 0.75：中等信度
- 0.75 ≤ ICC < 0.90：良好信度
- ICC ≥ 0.90：優秀信度

**我們的結果**：TP ICC = 0.964, CP ICC = 0.947 → **優秀信度**

#### Eta-Squared (η²) 計算方法

**測量原型間變異的效應量**：

```python
# 單向 ANOVA：原型是否解釋 TP/CP 變異？
# 依原型分組（此測試忽略情境）

SS_between = sum(n_i * (mean_i - grand_mean)^2)  # 原型間平方和
SS_total = sum((Y_ij - grand_mean)^2)            # 總平方和

eta_squared = SS_between / SS_total

# 解釋：
# η² ≥ 0.01：小效應
# η² ≥ 0.06：中效應
# η² ≥ 0.14：大效應
# η² ≥ 0.25：非常大效應（我們的門檻）
```

**我們的結果**：TP η² = 0.330, CP η² = 0.544 → **非常大效應量**

這確認了原型差異（MG vs NMG、屋主 vs 租客、洪災歷史）驅動 LLM 輸出的有意義變異。

#### 人設敏感度測試

**目的**：驗證改變人設屬性會按預期方向改變 LLM 行為。

```python
# 設計：4 個交換測試，每個 2 原型 × 10 重複 = 80 次 LLM 呼叫

swap_tests = {
    "income_swap": {
        "base": "mg_owner_floodprone",
        "swap": {"income": "$75K-$100K"},  # MG → NMG 收入
        "expected": "CP 增加"               # 較高收入 → 較佳應對能力
    },
    "zone_swap": {
        "base": "mg_owner_floodprone",
        "swap": {
            "flood_zone": "X (最小風險)",
            "flood_count": 0,
            "years_since_flood": -1,
            "memory_seed": "我住這裡 10 年了，從未淹過水..."
        },
        "expected": "TP 減少"               # 安全區域 → 較低威脅
    },
    "history_swap": {
        "base": "nmg_renter_safe",
        "swap": {
            "flood_count": 3,
            "years_since_flood": 1,
            "memory_seed": "我們已經被淹了 3 次..."
        },
        "expected": "TP 增加"               # 洪災歷史 → 較高威脅
    }
}

# 通過標準：≥75% 的交換配對顯示預期方向變化
pass_rate = passed_tests / total_tests
```

**我們的結果**：75% (3/4 測試通過) → **符合門檻**

#### 提示詞敏感度測試

**目的**：確保 LLM 不受表面提示詞特徵的偏差影響。

```python
# 測試 1：選項重排序 (40 次 LLM 呼叫)
# 打亂提示詞中的行動選項，檢查決策是否改變

for archetype in ["mg_owner", "nmg_renter", "vulnerable"]:
    original_order = ["do_nothing", "buy_insurance", "elevate", ...]
    shuffled_order = random.shuffle(original_order)

    response_original = llm.generate(prompt_with(original_order))
    response_shuffled = llm.generate(prompt_with(shuffled_order))

    # 若決策因選項位置而改變則 FAIL
    positional_bias = (response_original != response_shuffled)

# 測試 2：框架效應 (80 次 LLM 呼叫)
# 重新框架洪水機率："10% 機率" vs "每 10 年 1 次"

for archetype in sample_archetypes:
    neutral_frame = "您的房產有 10% 的年度洪水機率"
    loss_frame = "您的房產大約每 10 年會淹一次"

    tp_neutral = llm.generate(prompt_with(neutral_frame))["TP"]
    tp_loss = llm.generate(prompt_with(loss_frame))["TP"]

    # 若損失框架使 TP 膨脹 >1 級則 WARNING
    framing_effect = abs(label_to_numeric(tp_loss) - label_to_numeric(tp_neutral))
```

**我們的結果**：無系統性位置偏差，框架效應在可接受範圍內 → **OK**

---

## 13. 經驗基準

### 4 類 8 個基準

| # | 指標 | 範圍 | 權重 | 類別 | 來源 |
|---|------|------|------|------|------|
| B1 | NFIP 保險 (SFHA) | 0.30-0.50 | 1.0 | AGGREGATE | Kousky (2017) |
| B2 | 保險（所有區域）| 0.15-0.40 | 0.8 | AGGREGATE | Gallagher (2014) |
| B3 | 抬升率 | 0.03-0.12 | 1.0 | AGGREGATE | Haer et al. (2017) |
| B4 | 收購率 | 0.02-0.15 | 0.8 | AGGREGATE | NJ DEP Blue Acres |
| B5 | 洪後不行動 | 0.35-0.65 | 1.5 | CONDITIONAL | Grothmann & Reusswig (2006) |
| B6 | MG-NMG 差距 | 0.10-0.30 | 2.0 | DEMOGRAPHIC | Choi et al. (2024) |
| B7 | RL 無保險 | 0.15-0.40 | 1.0 | CONDITIONAL | FEMA RL 統計 |
| B8 | 流失率 | 0.05-0.15 | 1.0 | TEMPORAL | Gallagher (2014, AER) |

### 計算方法

| 方法 | 基準 | 如何 |
|------|------|------|
| **年末快照** | B1, B2, B3, B4 | 第 13 年的代理狀態 |
| **事件條件** | B5, B7 | 過濾經歷洪水的代理 |
| **年度流量** | B8 | 年度投保 → 未投保 |
| **群組差異** | B6 | NMG 調適率 - MG 調適率 |

---

## 14. ICC 探測協議

### 設計

**目的**：在執行實驗前驗證 LLM 信度

**協議**：15 原型 × 6 情境 × 30 重複 = **2,700 次 LLM 呼叫**

### 15 個原型

| # | ID | 特徵 |
|---|-----|------|
| 1 | `mg_owner_floodprone` | MG 屋主，AE 區，2 次洪水，$25K-$45K |
| 2 | `mg_renter_floodprone` | MG 租客，AE 區，1 次洪水，$15K-$25K |
| 3 | `nmg_owner_floodprone` | NMG 屋主，AE 區，1 次洪水，$75K-$100K |
| 4 | `nmg_renter_safe` | NMG 租客，Zone X，0 次洪水，$45K-$75K |
| 5 | `resilient_veteran` | NMG 屋主，4 次洪水，已抬升+投保，$100K+ |
| 6 | `vulnerable_newcomer` | MG 租客，6 個月，0 次洪水，<$15K |
| 7-15 | ... | 額外邊緣案例與人口統計變化 |

### 6 個情境

| # | ID | 嚴重性 | 預期 TP |
|---|-----|--------|---------|
| 1 | `high_severity_flood` | 4.5 ft 洪水，$42K 損害 | H 或 VH |
| 2 | `medium_severity_flood` | 1.2 ft 輕微洪水 | M |
| 3 | `low_severity_flood` | Zone X，30 年無洪水 | VL 或 L |
| 4 | `extreme_compound` | 8ft + 預算耗盡 + 保險失效 | VH |
| 5 | `contradictory_signals` | FEMA 說低風險但剛被淹 | M 到 H |
| 6 | `post_adaptation` | 已抬升 + 投保 | L 到 M |

### ICC 結果（已完成）

| 構面 | ICC(2,1) | 解釋 |
|------|----------|------|
| TP | **0.964** | 優異信度 |
| CP | **0.947** | 優異信度 |

兩者皆超過 0.60 門檻，驗證 LLM 產生一致、人設驅動的回應。

---

## 15. 如何執行

### 前置條件

```bash
# 1. 安裝 Ollama 並拉取模型
ollama pull gemma3:4b

# 2. 確認 PRB 柵格資料存在
ls examples/multi_agent/flood/input/PRB/*.asc
# 應顯示 13 個檔案 (2011-2023)

# 3. 確認代理設定檔已生成
ls examples/multi_agent/flood/data/agent_profiles_balanced.csv
ls examples/multi_agent/flood/data/initial_memories_balanced.json
```

### 步驟 1：ICC 探測（先驗證 LLM）

```bash
python paper3/run_cv.py --mode icc --model gemma3:4b --replicates 30
```

**檢查**：TP 和 CP 的 ICC(2,1) ≥ 0.60

### 步驟 2：主要實驗

```bash
# 單一種子
python paper3/run_paper3.py \
    --config paper3/configs/primary_experiment.yaml \
    --seed 42

# 全部 10 個種子
python paper3/run_paper3.py \
    --config paper3/configs/primary_experiment.yaml \
    --all-seeds
```

### 步驟 3：事後驗證

```bash
python paper3/run_cv.py \
    --mode posthoc \
    --trace-dir paper3/results/paper3_primary/seed_42/
```

**檢查**：CACR ≥ 0.80, R_H ≤ 0.10, EPI ≥ 0.60

### 步驟 4：消融研究 (SI)

```bash
python paper3/run_paper3.py \
    --config paper3/configs/si_ablations.yaml \
    --ablation si1_window_memory \
    --all-seeds
```

---

## 16. 輸出結構

```
paper3/results/
├── cv/                                    # ICC 探測結果
│   ├── icc_report.json                   # ICC(2,1), eta-squared 等
│   ├── icc_responses.csv                 # 全部 2,700 個回應
│   ├── persona_sensitivity_report.json   # 交換測試結果
│   └── prompt_sensitivity_report.json    # 重排測試結果
│
└── paper3_primary/
    └── seed_42/
        └── gemma3_4b_strict/
            └── raw/
                ├── household_owner_traces.jsonl   # 200 屋主 × 13 年
                ├── household_renter_traces.jsonl  # 200 租客 × 13 年
                ├── government_traces.jsonl        # 1 代理 × 13 年
                └── insurance_traces.jsonl         # 1 代理 × 13 年
```

### 軌跡檔案格式 (JSONL)

每行是一個 JSON 物件：

```json
{
  "run_id": "paper3_primary_seed42",
  "year": 3,
  "agent_id": "H0042",
  "agent_type": "household_owner",
  "validated": true,
  "input": "...(完整提示詞)...",
  "raw_output": "...(LLM 回應)...",
  "skill_proposal": "buy_insurance",
  "approved_skill": "buy_insurance",
  "TP_LABEL": "H",
  "CP_LABEL": "M",
  "SP_LABEL": "L",
  "SC_LABEL": "M",
  "PA_LABEL": "H",
  "retry_count": 0,
  "validation_issues": [],
  "memory_pre": ["...", "..."],
  "memory_post": ["...", "...", "(新決策記憶)"],
  "state_before": {"insured": false, "elevated": false},
  "state_after": {"insured": true, "elevated": false}
}
```

---

## 17. 與傳統 ABM 的關鍵差異

| 能力 | 傳統 ABM (SCC 論文) | LLM-ABM (Paper 3) |
|------|---------------------|-------------------|
| **TP 衰減** | 參數方程式（普查區層級，MG/NMG 統一）| 記憶中介（個體，經驗依賴）|
| **決策** | 貝葉斯迴歸查表 | LLM 推理 + 人設 + 記憶 |
| **構面** | 從 Beta 分布預初始化（輸入）| 從推理湧現（輸出）|
| **社會影響** | 總體 % 觀察（普查區層級）| 直接鄰居觀察 + 八卦 + 媒體 |
| **機構代理** | 外生（固定補助/保費）| 內生 LLM 代理 (NJDEP + FEMA) |
| **行動粒度** | 二元（採納/不採納）| 子選項（抬升 ft、保險類型）|
| **個體異質性** | 群組內代理相同 | 每代理有獨特記憶+推理+歷史 |
| **規格負擔** | 數十個參數方程式 | 單一自然語言人設 + 記憶系統 |
| **可解釋性** | 係數 | 自然語言推理軌跡 |

---

## 18. 計算需求

### LLM 呼叫估計

| 組件 | LLM 呼叫 | 時間估計 |
|------|----------|----------|
| 主要實驗 (400 × 13 × 10 種子) | 52,000 | ~7.2 小時 |
| ICC 探測 (15 × 6 × 30) | 2,700 | ~22 分鐘 |
| 人設 + 提示敏感度 | ~5,000 | ~42 分鐘 |
| SI 消融 (200 × 13 × 3 × 10 配置) | 78,000 | ~10.8 小時 |
| **總計** | **~138,000** | **~19 小時** |

### 硬體配置

- **推論**：本地 Ollama 伺服器
- **模型**：Gemma 3 4B（記錄特定量化）
- **情境視窗**：8,192 tokens
- **溫度**：0.7（ICC 與實驗統一）
- **GPU**：建議 NVIDIA RTX 3090 或同等級

### 記憶體需求

- **模型**：~4GB VRAM
- **模擬狀態**：每種子 ~500MB RAM
- **輸出軌跡**：每種子 ~50MB（壓縮後）

---

## 19. 詞彙表

| 術語 | 定義 |
|------|------|
| **ABM** | 代理基模型 (Agent-Based Model) |
| **BFE** | 基準洪水高程 (Base Flood Elevation) |
| **CACR** | 構面-行動一致率 (Construct-Action Coherence Rate) |
| **CP** | 因應感知 (Coping Perception, PMT 構面) |
| **CRS** | 社區評級系統 (Community Rating System, NFIP 折扣計畫) |
| **EBE** | 有效行為熵 (Effective Behavioral Entropy) |
| **EPI** | 經驗合理性指數 (Empirical Plausibility Index) |
| **FFE** | 一樓高程 (First Floor Elevation) |
| **ICC** | 組內相關係數 (Intraclass Correlation Coefficient) |
| **MG** | 邊緣群體 (Marginalized Group, 符合 3 項脆弱性標準中 2 項以上) |
| **NFIP** | 國家洪水保險計畫 (National Flood Insurance Program) |
| **NMG** | 非邊緣群體 (Non-Marginalized Group) |
| **PA** | 地方依附 (Place Attachment, PMT 構面) |
| **PADM** | 保護行動決策模型 (Protective Action Decision Model, Lindell & Perry, 2012) |
| **PMT** | 保護動機理論 (Protection Motivation Theory, Rogers, 1983) |
| **PRB** | Passaic River Basin |
| **R_H** | 幻覺率 (Hallucination Rate) |
| **RCV** | 重置成本價值 (Replacement Cost Value) |
| **RL** | 重複損失 (Repetitive Loss, ≥2 次洪水) |
| **SAGA** | SAGE 代理治理架構 (SAGE Agent Governance Architecture, 三層) |
| **SAGE** | 模擬代理治理引擎 (Simulated Agent Governance Engine) |
| **SC** | 社會資本 (Social Capital, PMT 構面) |
| **SFHA** | 特殊洪氾區 (Special Flood Hazard Area) |
| **SP** | 利害關係人感知 (Stakeholder Perception, PMT/PADM 構面) |
| **TP** | 威脅感知 (Threat Perception, PMT 構面) |
| **WRR** | Water Resources Research（期刊）|

---

## 20. 參考文獻

### 洪水調適與 PMT

- Grothmann, T., & Reusswig, F. (2006). People at risk of flooding: Why some residents take precautionary action while others do not. *Natural Hazards*, 38(1-2), 101-120.
- Lindell, M. K., & Perry, R. W. (2012). The protective action decision model: Theoretical modifications and additional evidence. *Risk Analysis*, 32(4), 616-632.
- Rogers, R. W. (1983). Cognitive and psychological processes in fear appeals and attitude change: A revised theory of protection motivation. *Social Psychophysiology: A Sourcebook*, 153-176.

### 環境正義

- Choi, D., et al. (2024). Flood adaptation disparities among marginalized communities in New Jersey. *Environmental Research Letters*.
- Collins, T. W., et al. (2018). Environmental injustice and flood risk: A conceptual model and case study. *Environmental Science & Policy*, 83, 74-83.

### NFIP 與保險

- Gallagher, J. (2014). Learning about an infrequent event: Evidence from flood insurance take-up in the United States. *American Economic Review*, 104(11), 3484-3508.
- Kousky, C. (2017). Disasters as learning experiences or disasters as policy opportunities: Examining flood insurance purchases after hurricanes. *Risk Analysis*, 37(3), 517-530.

### 代理基模型

- Haer, T., et al. (2017). Integrating household risk mitigation behavior in flood risk analysis: An agent-based model approach. *Risk Analysis*, 37(10), 1977-1992.
- de Ruig, L. T., et al. (2022). An agent-based model for evaluating reforms of the National Flood Insurance Program. *Risk Analysis*, 42(5), 1112-1127.

### LLM 代理

- Park, J. S., et al. (2023). Generative agents: Interactive simulacra of human behavior. *UIST 2023*.
- Horton, J. J. (2023). Large language models as simulated economic agents: What can we learn from homo silicus? *NBER Working Paper*.
- Vezhnevets, A. S., et al. (2023). Generative agent-based modeling with actions grounded in physical, social, or digital space using Concordia. *arXiv preprint*.

---

*最後更新：2026-02-05*
