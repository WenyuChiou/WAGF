# 多代理洪水 Reference Implementation

這個目錄是 WAGF 中主要的多代理水領域 reference implementation。

它展示如何建構一個由 LLM 治理的 ABM，並同時包含：

- 異質代理類型
- 制度代理與家戶代理的階段式決策
- 共享環境狀態
- 社會與媒體資訊通道
- 領域化治理與驗證機制

這份文件是給開發者看的入口 README。較長的研究敘事與 Passaic River Basin 研究包裝保留在：

- [README_research.md](README_research.md)
- [paper3/README.md](paper3/README.md)

---

## 這個案例包涵蓋什麼

主要 runtime 元件在這裡：

- [run_unified_experiment.py](run_unified_experiment.py)：主要執行入口
- [config/](config/)：agent types、skills、prompts、governance、parameters
- [orchestration/](orchestration/)：factories 與 lifecycle hooks
- [environment/](environment/)：hazard、depth 與環境邏輯
- [components/](components/)：media 與其他支援子系統
- [memory/](memory/)：記憶相關工具
- [ma_validators/](ma_validators/)：多代理驗證邏輯

多代理洪水論文的研究包裝位於：

- [paper3/](paper3/)

---

## 從哪裡開始

如果你是 ABM 開發者，建議按這個順序閱讀：

1. [config/skill_registry.yaml](config/skill_registry.yaml)
2. [config/ma_agent_types.yaml](config/ma_agent_types.yaml)
3. [orchestration/lifecycle_hooks.py](orchestration/lifecycle_hooks.py)
4. [run_unified_experiment.py](run_unified_experiment.py)

---

## 最小執行範例

```bash
python examples/multi_agent/flood/run_unified_experiment.py --mode random --agents 10 --years 3
```

預設輸出會保留在這個 workspace 內：

- `examples/multi_agent/flood/results_unified/`

---

## 設定介面

大多數使用者最先需要理解的是這幾個檔案：

| 檔案 | 作用 |
| :--- | :--- |
| `config/skill_registry.yaml` | 定義可用 actions |
| `config/ma_agent_types.yaml` | 定義 agent prompts、parsing 與 governance |
| `config/information_visibility.yaml` | 控制不同 agent type 的資訊可見性 |
| `config/prompts/*.txt` | 各 agent 類別的 domain prompts |
| `config/parameters/floodabm_params.yaml` | 洪水與環境模型參數 |

如果你要把這個案例改造成其他多代理 ABM，建議先改上面的 YAML，再去碰 runner。

---

## 執行模式

runner 目前支援多種初始化模式：

- `survey`：從 survey-derived agents 初始化
- `random`：快速用 synthetic agents 初始化
- `balanced`：從 prepared balanced profiles 初始化

`balanced` 與論文級工作流還會依賴以下支援資產：

- [paper3/output/](paper3/output/)
- [data/](data/)

---

## 邊界說明

這個目錄是可重用的水領域多代理案例包。

它不是 `Nature Water` 稿件 workspace，也不是單代理洪水基準案例。相關位置如下：

- 單代理洪水基準案例：[examples/single_agent/](../single_agent/)
- Nature Water 稿件 workspace：[paper/nature_water/](/c:/Users/wenyu/Desktop/Lehigh/governed_broker_framework/paper/nature_water)
- 多代理洪水論文 workspace：[paper3/](paper3/)

---

## 開發者備註

- 目前的 runner 仍帶有研究導向痕跡，體積也偏大。
- `paper3/` 包含主要的 WRR 實驗包、驗證流程與分析管線。
- [docs/](docs/) 下面仍有一些文件比較偏研究工作區，而不是教學導向。

如果你要看完整研究 framing、假說、研究區域與驗證敘事，請讀 [README_research.md](README_research.md)。
