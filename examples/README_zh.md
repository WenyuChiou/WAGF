# 兩個水資源案例，兩種耦合方向

**語言：[English](README.md) | [繁體中文](README_zh.md)**（下方連結的案例說明與教學目前只有英文版。）

完成[安裝步驟](../README_zh.md#快速開始)後，請在 repository 根目錄以 Python 3.10 或更新版本執行這些內建的 mock 案例。它們不需要任何模型服務。請使用新的輸出目錄。下方時間包含啟動與匯入，量測於一台 Windows/Python 3.14 電腦，只適用於這些小型檢查。

## 洪水調適：單向耦合

洪水災害驅動家戶的調適決策；家戶的決策不會改變災害。這個案例展示提案檢查、重試回饋、重試用盡後採用設定的預設行動，以及家戶 audit。

```bash
python examples/single_agent/run_flood.py --model mock --years 1 --agents 2 --workers 1 --seed 42 --governance-mode strict --output .tmp/readme-flood
```

實測執行時間：**在一台 Windows 電腦上約 5 秒**。`.tmp/readme-flood/` 中的輸出包括 `household_governance_audit.csv`（兩筆決策）、`simulation_log.csv`、`audit_summary.json`、`governance_summary.json` 與 `run_integrity.json`。mock 提出 `buy_insurance`，但沒有附上必要的評估，用盡重試後執行 `do_nothing`。它不儲存任何反思：對這個 mock 而言，完整性警告是預期中的結果，這次執行也不能與開啟反思功能的研究相比。

設定方式與本機真實模型執行，請閱讀[洪水 README](single_agent/README.md)。

## 科羅拉多河灌溉：雙向耦合

用水者的申請量會影響配水量與 Lake Mead 蓄水量。由此產生的水位與短缺等級會影響分配量，並寫入下一年的 prompt。這個案例展示耦合 adapter、每年的水資源狀態，以及每位用水者的 audit。

```bash
python examples/irrigation_abm/run_experiment.py --model mock --years 2 --agents 2 --workers 1 --seed 42 --governance-mode strict --coupling --output .tmp/readme-irrigation
```

實測執行時間：**在一台 Windows 電腦上約 5 秒**。`.tmp/readme-irrigation/` 中的輸出包括 `irrigation_farmer_governance_audit.csv`（四筆決策）、`simulation_log.csv`、`audit_summary.json`、`run_integrity.json`，以及一份會保留下來的衍生設定檔 `agent_types.coupling.yaml`。Lake Mead 年底蓄水量由 14.349 變為 15.776 million acre-feet（百萬英畝-英尺）；第 2 年起始水位為 1100.739 ft，高於第 1 年的 1081.460 ft。短缺等級（shortage tier）維持 0。

mock 不提供評估，用盡重試後執行設定的預設行動 `maintain_demand`。它也不儲存反思，完整性記錄會標出這項限制。[教學第 4 章](../docs/tutorial/04-water-model.md)使用既有的 78 位用水者資料，展示短缺等級的轉換，以及這次轉換造成的等級削減（tier cut），使用的仍是 mock model。

水資源系統假設、設定方式與本機真實模型執行，請閱讀[灌溉 README](irrigation_abm/README.md)。

## examples/ 裡的其他資料夾

上面兩個案例是主要案例。`governed_flood/` 提供 `single_agent/` 使用的洪水 domain pack；其餘資料夾是 demo、示範範例或測試用 fixture。

| 資料夾 | 用途 |
|---|---|
| `governed_flood/` | 共用的洪水 domain pack，加一個小型 runner。`single_agent/`、`multi_agent/` 與核心測試都會 import 它，請勿刪除。 |
| `multi_agent/flood/` | 獨立的多代理洪水研究，不屬於兩個主要案例。 |
| `reservoir_control/` | 示範如何透過 `broker/coupling/` 接上新的水資源模型；以 mock model 執行。 |
| `reservoir_control_multidim/` | 同上，但一次決策要訂三個操作設定值（setpoint）；以 mock model 執行。 |
| `coupling_examples/` | 耦合 archetype 的示範範例。 |
| `cat_model/` | 耦合層 demo（巨災保險），核心測試會用到。 |
| `vaccination_demo/` | 非水資源的 demo domain。 |
| `quickstart/` | 編號的教學腳本。 |
| `_test_fixtures/` | 測試用的 fixture domain，無法單獨執行。 |

哪些部分是通用模組、哪些是範例，請見 [`docs/REPO_MAP.md`](../docs/REPO_MAP.md)（只有英文版）。

接著閱讀[六章教學](../docs/tutorial/README.md)。
