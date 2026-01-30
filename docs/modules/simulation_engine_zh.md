# 模擬引擎：世界的物理法則 (Simulation Engine)

**🌐 Language: [English](README.md) | [中文](README_zh.md)**

`simulation/` 目錄處理世界的「基本真理 (Ground Truth)」。它管理時間步進、環境狀態（洪水），並執行代理人行動的物理後果。

## 🌍 模擬引擎 (`simulation_engine.py`)

此引擎是 **計時器 (Timekeeper)** 與 **物理裁決者 (Physics Resolver)**。

### 主要職責

1.  **時間步進**：逐年推進模擬 ($t \rightarrow t+1$)。
2.  **外部衝擊**：基於機率分佈或外部數據注入洪水事件。
3.  **行動決議**：
    - _範例_：如果 Agent A 選擇 `relocate`，引擎會將其從活躍地圖中移除並更新統計數據。
    - _沙盒機制_：引擎確保代理人無法修改其他代理人的財產，除非獲得明確許可（例如：社會影響）。

---

## 🔌 外部模型整合 (External Model Integration)

本框架設計用於與嚴謹的水文模型進行耦合。

### HEC-RAS / SWMM 耦合介面

若要連接即時洪水模型：

1.  **輸入**：引擎導出 `state_vector_t.json`（代理人位置與海拔）。
2.  **處理**：使用此向量運行您的 HEC-RAS 腳本。
3.  **輸出**：導入生成的 `flood_depth_map.csv`。
4.  **更新**：`ContextBuilder` 讀取此地圖以生成下一年的觀察結果。

```python
# 耦合偽代碼範例
def step_environment(self, year):
    # 1. 導出代理人狀態
    self.export_agent_states(f"outputs/year_{year}/agents.json")

    # 2. 呼叫外部模型 (如 HEC-RAS Wrapper)
    call_hec_ras(input="agents.json", return_map="depths.csv")

    # 3. 更新模擬上下文
    self.flood_map = load_flood_map("depths.csv")
```

---

## ⚙️ 配置與參數指南 (Configuration & Parameters)

物理法則與迴圈設定。

| 參數                | 類型    | 預設值      | 建議值 | 說明                                                 |
| :------------------ | :------ | :---------- | :----- | :--------------------------------------------------- |
| `simulation_years`  | `int`   | `10`        | `20+`  | 實驗運行的時長。較長的運行時間能讓「反思」穩定行為。 |
| `flood_probability` | `float` | `0.1`       | `0.1`  | 任何給定年份發生災害的機率（若使用隨機模式）。       |
| `output_dir`        | `str`   | `./results` | -      | 儲存 `simulation_log.csv` 與審計軌跡的路徑。         |

## 🔌 實驗連接器：如何組裝 (Connector Guide)

這是如何將 **記憶**、**治理** 與 **模擬** 串連成一個可執行實驗的方法。

### 「主迴圈」模式 (The Main Loop Pattern)

`run.py` 腳本看起來很複雜嗎？它其實只是一個迴圈：

```python
# 1. 設定組件
memory = HumanCentricMemoryEngine()
broker = SkillBroker()
sim = SimulationEngine()

# 2. 初始化代理人
agents = [Agent(id=i, memory=memory) for i in range(100)]

# 3. 主時間迴圈
for year in range(params.years):

    # A. 環境步進 (Environment Step)
    flood_depth = sim.get_flood_depth(year)

    # B. 代理人迴圈 (Agent Loop)
    for agent in agents:
        # i. 觀察 (ContextBuilder)
        observation = context_builder.build(agent, flood_depth)

        # ii. 決策 (Broker + LLM)
        action = broker.negotiate_action(agent, observation)

        # iii. 行動 (Simulation)
        sim.execute_action(agent, action)

    # C. 反思 (Reflection - 年末)
    if memory.type == 'human_centric':
        memory.run_reflection(agents)
```

## 多階段執行 (Multi-Phase Execution)

在多 Agent 模擬中，扁平的 `for agent in agents` 迴圈被 `PhaseOrchestrator` (`broker/components/phase_orchestrator.py`) 取代，根據角色與依賴順序協調 Agent。

### 預設階段順序

| 階段 | 角色 | 說明 |
| :--- | :--- | :--- |
| 1. **INSTITUTIONAL** | 政府、保險 | 在家戶決策前設定政策、調整保費/補貼 |
| 2. **HOUSEHOLD** | 家戶 Agent | 做出個人決策 (抬升、投保、遷移、不行動) |
| 3. **RESOLUTION** | GameMaster | 偵測並解決衝突 (資源過度分配) |
| 4. **OBSERVATION** | 全部 | 觀察結果，更新社會網絡 |

### GameMaster 協調

`GameMaster` (`broker/components/coordinator.py`) 管理 RESOLUTION 階段，支援可插拔策略：

- **Passthrough**：接受所有提案 (單 Agent 預設)
- **ConflictAware**：使用 `ConflictDetector` 偵測資源衝突，透過優先級或比例分配解決
- **Custom**：用戶自定義解決邏輯

### 衝突解決

`ConflictDetector` (`broker/components/conflict_resolver.py`) 偵測資源過度分配（例如申請政府補助的 Agent 超過預算）。解決策略包括 `PriorityResolution` (最需要的 Agent 優先) 與 `ProportionalResolution` (按比例分配)。

---

## 📝 輸入/輸出範例 (Input / Output Examples)

### 輸入：初始配置

```yaml
n_agents: 50
years: 10
agent_distribution:
  subsidized_owners: 0.3
  regular_owners: 0.7
```

### 輸出：模擬日誌 (`simulation_log.csv`)

| Year | AgentID | Event            | Action         | Outcome     | Wealth |
| :--- | :------ | :--------------- | :------------- | :---------- | :----- |
| 1    | 001     | No Flood         | do_nothing     | Stable      | 1000   |
| 2    | 001     | **FLOOD (1.5m)** | buy_insurance  | **Insured** | 900    |
| 3    | 001     | No Flood         | invest_measure | Protected   | 850    |

> **分析師筆記**：此 CSV 是您計算「適應率 (Adaptation Rates)」與「財富保存 (Wealth Preservation)」的主要資料集。
