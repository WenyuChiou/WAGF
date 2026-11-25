# WAGF 使用手冊（User Manual）

**語言：[English](index.md) | 繁體中文**

**Water Agent Governance Framework (WAGF)** 將語言模型（LLM）決策代理人、物理／社會／認知治理規則與水資源模擬環境串接起來，在代理人的提案真正改變模擬狀態前完成驗證、攔阻、重試說明與完整稽核記錄。

---

## 核心運作流程

每個決策時間步都會經過以下受治理迴圈（Governed Broker Loop）：

1. **推進環境與組裝 Prompt**：水資源環境推進一步（`advance_step()` 或耦合模型），將狀態寫入代理人並填入 `prompt_template_file`。
2. **提出決策**：LLM（或內建 `--model mock`）輸出結構化區塊（`<<<DECISION_START>>>...<<<DECISION_END>>>`），由 `ModelAdapter` 解析為行動與評估標籤。
3. **治理驗證**：驗證器依序檢查輸出格式、前置條件、物理／耦合邊界（`FeasibilityBound` / 運算式規則）與認知規則。
4. **攔阻與重試／預設回退**：若觸發 `ERROR` 規則，將具體原因加入重試 prompt（最多 `max_retries` 次）；通過則執行並推進模型，重試耗盡則退回 `default_skill`。
5. **稽核記錄**：所有嘗試、重試次數、違反規則與執行前後狀態變化皆輸出至 `*_governance_audit.csv`、`raw/*.jsonl`、`governance_summary.json` 與 `reproducibility_manifest.json`。

---

## 三條學習與開發路徑

| 你的目標 | 建議起點 |
|---|---|
| **建立自己的受治理水資源案例** | 複製 `templates/water_starter/` 或執行 `python -m broker.tools.scaffold_domain` |
| **循序學習 WAGF 核心元件** | 閱讀 [六章教學目錄](tutorial/README.md) 與執行 `examples/quickstart/` |
| **重現洪水／灌溉論文實驗** | 參考 `examples/single_agent/`、`examples/irrigation_abm/` 與 `DATA.md` |

---

## 路徑一：用 `python -m broker.run` 建立新案例

建議新案例作者依序閱讀下列指南（不含舊論文專用旗標）：

1. **乾淨範本快速上手**：複製 `templates/water_starter/`（說明見 `templates/README.md`），先用 `--model mock` 體驗一次完整的水庫死庫容攔阻（`dead_pool_guard`）→ 重試 → 修正流程；並閱讀 [Quickstart Guide](guides/quickstart_guide.md)。
2. **建立案例目錄與骨架**：參考 [How to Add a New Domain](guides/HOW_TO_ADD_A_NEW_DOMAIN.md) 或使用 `python -m broker.tools.scaffold_domain`。
3. **設定檔與變數定義**：閱讀 [Agent Type Specification Guide](guides/agent_type_specification_guide.md)、[Customization Guide（中文）](guides/customization_guide_zh.md) 與 [YAML Configuration Reference](references/yaml_configuration_reference.md)。
4. **連接水資源模型狀態與規則**：閱讀 [Model State in Prompts and Checks](guides/model_state_in_prompt_and_checks.md)、[Coupling Connectors](COUPLING_CONNECTORS.md) 與 [Governance Layers](guides/governance_layers.md)。
5. **檢視稽核欄位與常見問題**：對照 [Audit Schema](AUDIT_SCHEMA.md)、[Troubleshooting Guide](guides/troubleshooting_guide.md) 與 [CLI Reference](guides/readme_reference.md)。

---

## 路徑二：核心教學與中文模組參考

- **英文六章實作教學**：[Tutorial Overview](tutorial/README.md)（[01](tutorial/01-first-run.md) · [02](tutorial/02-rules-and-retries.md) · [03](tutorial/03-audit.md) · [04](tutorial/04-water-model.md) · [05](tutorial/05-resume.md) · [06](tutorial/06-measures.md)）
- **繁體中文模組與組裝文件**：
  - [Agent 組裝指南](guides/agent_assembly_zh.md)
  - [客製化與延伸指南](guides/customization_guide_zh.md)
  - [理論基礎總覽](modules/00_theoretical_basis_overview_zh.md)
  - [Context 系統](modules/context_system_zh.md) · [Governance 核心](modules/governance_core_zh.md) · [Skill Registry](modules/skill_registry_zh.md)
  - [Memory 元件](modules/memory_components_zh.md) · [Reflection 引擎](modules/reflection_engine_zh.md) · [Simulation 引擎](modules/simulation_engine_zh.md)

---

## 路徑三：論文案例與外部資料（與教學分離）

`examples/single_agent/`、`examples/irrigation_abm/` 與 `examples/multi_agent/flood/` 包含特定論文的校準表格與實驗參數；學習框架時建議先從 `templates/water_starter/` 與 `examples/reservoir_control/` 開始，需要重現論文時再對照 `DATA.md` 與 `reproduction/README.md`。完整目錄分工請見 [Repository Map](REPO_MAP.md)。

---

## 在本機離線瀏覽與建置靜態網頁手冊

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

或建置純靜態 HTML 到 `site/` 目錄：

```bash
mkdocs build
python -m http.server --directory site 8000
```
