# Examples - Framework Version Guide

## ⚠️ 重要：新舊版框架分離

本目錄包含兩個不同版本的框架實驗範例，**請勿混用**！

---

## 📁 目錄結構

| 目錄 | 框架版本 | 實驗編號 | 狀態 |
|------|---------|---------|------|
| `v2_skill_governed/` | **新版 Skill-Governed** | Exp 10 | ✅ 推薦使用 |
| `v1_mcp_flood/` | 舊版 MCP | Exp 9 | ⚠️ DEPRECATED |

---

## 🆕 新版 Skill-Governed (`v2_skill_governed/`)

**推薦用於所有新實驗**

### 核心特徵
- **5層驗證管線**: Admissibility → Feasibility → Institutional → EffectSafety → PMTConsistency
- **財務一致性規則**: 防止 "cannot afford + relocate" 矛盾
- **結構化輸出**: SkillProposal JSON 格式
- **完整審計**: skill_audit.jsonl

### 運行方式
```bash
cd v2_skill_governed
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

### 關鍵檔案
- `run_experiment.py` - 主要實驗入口
- `skill_registry.yaml` - 技能定義

---

## ⚠️ 舊版 MCP (`v1_mcp_flood/`) - DEPRECATED

**僅供參考比較，不建議用於新實驗**

### 限制
- 僅單層 PMT 關鍵字驗證
- 無財務一致性檢查
- 無結構化輸出

### 關鍵檔案
- `run.py` - 舊版入口 (使用 `parse_llm_output()`)
- `run_skill_governed.py` - 過渡版本

---

## 版本識別方法

| 特徵 | 舊版 MCP (v1) | 新版 Skill-Governed (v2) |
|------|-------------|-------------------------|
| 目錄 | `v1_mcp_flood/` | `v2_skill_governed/` |
| 主要入口 | `run.py` | `run_experiment.py` |
| Broker | `broker.legacy.BrokerEngine` | `broker.SkillBrokerEngine` |
| 驗證層數 | 1 層 | 5+ 層 |
| 輸出格式 | 文本解析 | SkillProposal JSON |
