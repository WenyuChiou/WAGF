# 多代理基準測試：社會與制度動態

此基準測試將框架擴展為 **多代理系統（MAS）**，在 10 年期間讓 50+ 住戶代理彼此互動，並與機構代理（政府、保險）協作。

## 研究問題

本實驗探討租屋者與自住房屋在洪水調適上的差異，包含三個核心問題：

### RQ1：持續調適 vs 不採取行動

> **持續調適與不採取行動相比，對租屋者與自住房屋的長期洪水結果有何差異？**

**假設**：自住房屋因結構所有權在長期調適上受益較多；租屋者面臨移動限制，可能降低持續投資。

**指標**：
- 10 年累積損害（依房屋型態）
- 調適狀態分布（無/保險/抬升/兩者/遷移）
- 財務復原軌跡

### RQ2：洪後調適軌跡

> **重大洪水事件後，租屋者與自住房屋的調適軌跡有何差異？**

**假設**：重大洪水事件會讓自住房屋更快採取抬升或投保；租屋者偏向遷移。

**指標**：
- 洪水後一年內的調適行動
- 軌跡差異（自住 vs 租屋）
- 洪水事件的記憶顯著性

### RQ3：保險涵蓋與財務結果

> **不同房屋型態的保險涵蓋差異，如何影響長期財務結果？**

**假設**：租屋者的僅內容物保險較缺乏保護；自住房屋具有結構+內容物保障。

**指標**：
- 投保 vs 未投保損失（依房屋型態）
- 保險持續性（續保率）
- 自付費用比率

---

## 實驗設計

透過三種配置，分離 **社會互動** 與 **記憶系統** 的影響：

| 情境 | 記憶引擎 | 社會八卦 | 說明 |
| :--- | :------ | :------ | :--- |
| **1. Isolated** | Window（Size=1） | 停用 | **基準控制**。代理幾乎不共享記憶。 |
| **2. Window** | Window（Size=3） | 啟用 | **社會標準**。代理分享理由（例如「我為什麼抬升」），社會證據進入記憶。 |
| **3. Human-Centric** | Human-Centric | 啟用 | **進階認知**。使用重要性/新近性/關聯性分數保留關鍵記憶（如過往洪水）。 |

## 主要特性

### 1. 機構代理

與單代理不同，本環境包含動態機構：

- **州政府（NJ）**：依預算與採用率調整 **補助率**（Grant %）。
- **FEMA/NFIP**：依 Loss Ratio 調整 **保費**。
  - _效果_：代理需回應經濟誘因（例如保費上升可能導致遷移）。

### 2. 社交網路（八卦）

- **理由傳播**：代理決策（如抬升）後，理由會廣播給鄰居（k=4 網路）。
- **社會證據**：鄰居收到記憶痕跡：「鄰居 X 因為 [理由] 抬升」。影響其威脅/因應評估。

### 3. 生命週期掛鉤

- **Pre-Year**：洪水事件決定（$P=0.3$），待處理行動（例如抬升需 1 年）。
- **Post-Step**：機構全域狀態更新（補助/保費變動）。
- **Post-Year**：洪水損害計算（影響情緒記憶）與記憶整合。

### 4. 災害分析工具（PRB ASCII Grid）

使用 PRB 多年分析工具檢視災害歷史並產生圖表：

```powershell
# Run PRB multi-year analysis
python examples/multi_agent/hazard/prb_analysis.py --data-dir "C:\path\to\PRB" --output analysis_results/

# Generate visualizations
python examples/multi_agent/hazard/prb_visualize.py --data-dir "C:\path\to\PRB" --output plots/
```

### 5. Task-060 強化功能

- **保費揭露**：保險代理會將保費資訊揭露給住戶。
- **技能排序隨機化**：每位代理每年打亂行動選項，避免首因偏誤。
- **SC/PA 信任指標**：情境中顯示自信（SC）與防護行動信任（PA）分數。
- **通訊層**：以 `MessagePool` 與 `MessageProvider` 進行代理間訊息傳遞。
- **回音室偵測**：`DriftDetector` 以 Shannon entropy 與 Jaccard similarity 監測行為停滯。

## 如何執行

### 快速開始

```powershell
# 基本多代理實驗
python examples/multi_agent/run_unified_experiment.py --model gemma3:4b

# 開啟社會互動
python examples/multi_agent/run_unified_experiment.py --model gemma3:4b --enable-social
```

使用 PowerShell 腳本可跑完整基準測試：

```powershell
./examples/multi_agent/run_ma_benchmark.ps1
```

### 配置

- **Agents**：50（住戶/租戶混合）
- **Years**：10
- **Models**：Llama 3.2、Gemma 2、DeepSeek-R1（可於腳本中調整）

## 輸出結構

結果儲存在 `examples/multi_agent/results_benchmark/`：

```
results_benchmark/
  llama3_2_3b_isolated/
  llama3_2_3b_window/
  llama3_2_3b_humancentric/
  ...
```

每個資料夾包含：

- `simulation_log.csv`：決策與行動。
- `household_governance_audit.csv`：感知與治理驗證記錄。
- `institutional_log.csv`：政府/保險狀態變化。

## 災害模型公式

### 損害計算

洪水損害依 FEMA 深度-損害曲線計算：

```
Damage = f(depth_ft, RCV, elevation_status, insurance)
```

**建築損害比例**（USACE 深度-損害函數）：
```
if depth_ft <= 0:
    ratio = 0
elif depth_ft <= 1:
    ratio = 0.08 * depth_ft
elif depth_ft <= 4:
    ratio = 0.08 + (depth_ft - 1) * 0.12
elif depth_ft <= 8:
    ratio = 0.44 + (depth_ft - 4) * 0.10
else:
    ratio = min(0.84 + (depth_ft - 8) * 0.02, 1.0)
```

**抬升減損**：
- 抬升（BFE+1）：95% 損害降低
- 超越（severity > 0.9）：50% 損害降低

**總損害**：
```
building_damage = RCV_building * building_ratio * elevation_factor
contents_damage = RCV_contents * contents_ratio  # ~30% of building ratio
total_damage = building_damage + contents_damage
```

### 保險理賠

**NFIP 覆蓋上限**：
- 建築：$250,000
- 內容物：$100,000
- 自負額：$1,000-$10,000（預設：$2,000）

**理賠計算**：
```
covered_building = min(building_damage, 250_000)
covered_contents = min(contents_damage, 100_000)
gross_claim = covered_building + covered_contents
payout = max(0, gross_claim - deductible)
out_of_pocket = total_damage - payout
```

### 補助分配

**政府補助計畫（FEMA HMA）**：
```
base_cost = action_cost  # e.g., $150,000 for elevation
subsidy_amount = base_cost * subsidy_rate
net_cost = base_cost - subsidy_amount
```

**MG 優先加成**：
- MG 住戶：額外 +25% 補助（最高 75%）
- 補助範圍：20%-95%

### 保費調整

**保費邏輯**（Risk Rating 2.0）：
```
base_premium = property_value * base_rate  # ~0.4% typical
loss_ratio = total_claims / total_premiums  # Target: <0.70

if loss_ratio > 0.80:
    premium_rate += 0.5%  # Raise premium
elif loss_ratio < 0.60 and insured_rate < target:
    premium_rate -= 0.5%  # Lower to attract customers
```

**保費範圍**：1%-15%

## 代理人口統計

### 人口分布（N=50）

| 類別 | 數量 | 比例 |
|------|------|------|
| **自住房屋** | 32 | 64% |
| **租屋者** | 18 | 36% |
| **MG（邊緣群體）** | 17 | 35% |
| **NMG（非邊緣群體）** | 33 | 65% |

### MG 判定條件

滿足以下 2 項以上視為 **邊緣群體（MG）**：
1. **住房負擔**：住房費用占收入 >30%
2. **無車**：撤離能力受限
3. **低於貧窮線**

### 收入分層

| 層級 | 區間 | 比例 | 典型 RCV |
|------|------|------|----------|
| Low | <$35K | 30% | $150K 建築，$40K 內容 |
| Medium | $35K-$75K | 50% | $220K 建築，$55K 內容 |
| High | >$75K | 20% | $350K 建築，$85K 內容 |

### 初始調適狀態

| 狀態 | 自住房屋比例 | 租屋者比例 |
|------|--------------|-----------|
| 有保險 | 40% | 20% |
| 已抬升 | 15% | N/A |
| 皆無 | 45% | 80% |

## 分析工具

### 政策影響評估

分析政府/保險政策效果：

```powershell
python analysis/policy_impact.py --results results/window/simulation_log.csv
```

輸出：
- 補助敏感度分析（MG vs NMG 採用率）
- 保費敏感度分析（投保率）
- 行為變化門檻

### 公平性指標

追蹤人口群體公平性：

```powershell
python analysis/equity_metrics.py --results results/simulation_log.csv
```

輸出：
- MG/NMG 採用差距（目標：<15%）
- 自住房屋/租屋者差距
- 調適分配的基尼係數
- 脆弱性指數

### 研究問題實驗腳本

執行 RQ 實驗：

```powershell
# RQ1: Adaptation impact analysis
python experiments/run_rq1_adaptation_impact.py --results results/simulation_log.csv

# RQ2: Post-flood trajectory analysis
python experiments/run_rq2_postflood_trajectory.py --results results/simulation_log.csv

# RQ3: Insurance outcomes analysis
python experiments/run_rq3_insurance_outcomes.py --results results/simulation_log.csv

# Test with mock data
python experiments/run_rq1_adaptation_impact.py --model mock
```

每個腳本輸出：
- 控制台摘要
- JSON 報告（如 `rq1_results.json`）
