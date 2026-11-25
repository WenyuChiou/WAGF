# WAGF 使用手冊

**語言：[English](index.md) | 繁體中文**

**Water Agent Governance Framework（WAGF）** 把由 LLM 做決策的代理人、明確寫出的物理／認知／社會規則，以及水資源模型接在一起：不合規則的提案在改動任何模擬狀態之前，就會被擋下、說明原因、重試，並且留下記錄。

---

## WAGF 怎麼運作

每一個決策週期都走同一個受治理的 broker 迴圈：

1. **觀察並組出 prompt**：世界往前推一步（`advance_step()`，或耦合的 BMI／子程序模型），把變數同步到每個代理人身上，再填入 prompt 模板（`prompt_template_file`）。
2. **提案**：LLM（或內建的 `--model mock`）回傳一段結構化區塊（`<<<DECISION_START>>>...<<<DECISION_END>>>`），解析成 `SkillProposal`（行動，加上評估標籤／數值）。
3. **檢查**：已註冊的驗證器依序檢查輸出格式、前置條件、物理／耦合邊界（`FeasibilityBound`／運算式規則）、制度規則與思考規則。
4. **擋下重試，或執行**：違反 `ERROR` 規則時，把規則的說明加進重試的 prompt，最多 `max_retries` 次。通過的提案對世界執行；重試用完則改用 `default_skill`。
5. **記錄**：每一次嘗試、重試原因、標籤漂移與已執行的狀態變化，都寫進 `*_governance_audit.csv`、`raw/*.jsonl`、`governance_summary.json` 與 `reproducibility_manifest.json`。

---

## 選一個起點

| 你的目標 | 從哪裡開始 | 時間 |
|---|---|---|
| **建立一個新的受治理水資源模擬** | 複製 `templates/water_starter/`，或執行 `python -m broker.tools.scaffold_domain` | 約 5 分鐘 |
| **一步一步學 WAGF 的基本元件** | 閱讀 [教學總覽](tutorial/README.md)（`01-first-run.md` 到 `06-measures.md`） | 約 15 分鐘 |
| **執行獨立的程式範例** | 執行 `examples/quickstart/` 裡的腳本（`01_barebone.py`、`02_governance.py`） | 約 2 分鐘 |
| **重現洪水／灌溉論文** | 查看 `examples/single_agent/`、`examples/irrigation_abm/` 與 `DATA.md` | 視情況而定 |

---

## 路徑一：建立你自己的案例（`python -m broker.run`）

給要建立新案例、不用舊論文專用旗標的作者，建議的閱讀順序：

1. **從乾淨的範本開始**：閱讀 [Quickstart Guide](guides/quickstart_guide.md)，並查看 `templates/water_starter/`（說明在 `templates/README.md`）。它跑一個 2 年的小案例，實際示範 `dead_pool_guard`（死庫容）擋下 → 重試 → 修正。
2. **加入你的案例結構**：照 [How to Add a New Domain](guides/HOW_TO_ADD_A_NEW_DOMAIN.md) 做，或用 `python -m broker.tools.scaffold_domain` 產生骨架。
3. **定義設定檔與 prompt**：參考 [Agent Type Specification Guide](guides/agent_type_specification_guide.md) 與 [YAML Configuration Reference](references/yaml_configuration_reference.md)。
4. **接上狀態與物理規則**：閱讀 [Model State in Prompts and Checks](guides/model_state_in_prompt_and_checks.md) 與 [Coupling Connectors](COUPLING_CONNECTORS.md)。
5. **設定治理規則與重試**：閱讀 [Governance Layers](guides/governance_layers.md) 與 [Retry Feedback Guide](guides/retry_feedback_guide.md)。
6. **核對記錄與欄位**：查看 [Audit Schema](AUDIT_SCHEMA.md) 與 [CLI Reference & Paper Comparison](guides/readme_reference.md)。

---

## 路徑二：學基本元件（`docs/tutorial/` 與 `examples/quickstart/`）

- **Python SDK 與最精簡的 broker**：參考 [Quickstart Guide](guides/quickstart_guide.md)，並用 `--output .tmp/qs` 執行 `examples/quickstart/01_barebone.py`／`examples/quickstart/02_governance.py`。
- **六章 mock 教學**：照 [教學總覽](tutorial/README.md) 做：
  - [第 1 章：第一次執行](tutorial/01-first-run.md)
  - [第 2 章：規則與重試](tutorial/02-rules-and-retries.md)
  - [第 3 章：記錄](tutorial/03-audit.md)
  - [第 4 章：雙向耦合的水資源模型](tutorial/04-water-model.md)
  - [第 5 章：從 journal 接續](tutorial/05-resume.md)
  - [第 6 章：IBR 與 EHE 指標](tutorial/06-measures.md)

教學各章目前只有英文版。

---

## 路徑三：論文案例與重現（和入門學習分開）

`examples/` 底下的論文案例帶有各自領域的校準表和舊的命令列旗標。學框架的核心 API 時，先把它們放在一邊：

| 案例 | 路徑 | 內容 |
|---|---|---|
| 單代理人洪水（PMT） | `examples/single_agent/` | 舊的 100 戶洪水調適 runner（`run_flood.py`）、PMT 的 YAML 規則，以及 `agent_initial_profiles.csv` 的欄位格式 |
| 科羅拉多河灌溉 ABM | `examples/irrigation_abm/` | 78 個農戶的上／下游盆地模擬（`run_experiment.py`）、USBR 的 CSV 表（`examples/irrigation_abm/data/README.md`），以及可選的外部 CRSS 資料（`DATA.md`） |
| 多代理人洪水（PRB） | `examples/multi_agent/flood/` | Passaic River Basin 的空間研究（`DATA.md`） |
| 水庫操作（耦合） | `examples/reservoir_control/` 與 `examples/reservoir_control_multidim/` | 用 `python -m broker.run` 執行的單一數值與多設定值耦合範例 |
| 重現腳本 | `reproduction/README.md` | 執行後的指標擷取，以及凍結案例防護用的測試資料 |

完整的目錄說明見 [Repository Map](REPO_MAP.md)。安裝問題、模型旗標，以及 Windows／Python 環境的提示，見 [Troubleshooting Guide](guides/troubleshooting_guide.md) 與 [CLI Reference](guides/readme_reference.md)。

---

## 在本機瀏覽這份手冊（離線 MkDocs 建置）

在 repo 根目錄安裝選用的文件套件，然後在本機預覽，或建成靜態 HTML：

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

或把獨立的離線 HTML 建到 `site/`，用任何瀏覽器打開：

```bash
mkdocs build
python -m http.server --directory site 8000
```
