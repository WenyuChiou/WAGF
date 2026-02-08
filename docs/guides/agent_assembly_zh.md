# 如何組裝代理人："堆疊積木" 指南

**🌐 Language: [English](agent_assembly.md) | [中文](agent_assembly_zh.md)**

Water Agent Governance Framework 將認知能力視為模組化的「積木」。本指南說明如何切換這些功能，以創建不同智能與治理等級的代理人，主要用於消融研究 (Ablation Studies)。

## 🧱 認知積木 (The Building Blocks)

您可以使用 `run_flood.py` 的命令行參數來啟用或禁用這些積木。

### 1. 身體 Body (執行引擎)

_始終開啟 (Always On)。_
這是與世界互動的基礎能力（例如 `do_nothing`）。如果沒有其他積木，代理人就像是一個隨機漫步者或純粹的反應機器。

### 2. 眼睛 Eyes (感知透鏡)

_指令參數：_ `--memory-engine window`
_功能：_ 將歷史紀錄過濾為嚴格的視窗（例如：最近 5 個事件）。
_效果：_ 防止上下文溢出錯誤，但會導致「金魚失憶症 (Goldfish Amnesia)」(忘記過去的災難)。

### 3. 海馬迴 Hippo (記憶引擎)

_指令參數：_ `--memory-engine humancentric`
_功能：_ 啟用 **分層記憶 (Tiered Memory)** (視窗 + 顯著性 + 長期)。
_效果：_ 允許代理人優先保留高影響力的記憶（如洪水），即使它們發生在多年前，從而解決失憶問題。

### 4. 超我 Superego (技能仲裁)

_指令參數：_ `--governance-mode strict`
_功能：_ 強制執行「思考規則 (Thinking Rules)」。驗證代理人的思维過程 (TP) 是否與其行動相符。
_效果：_ 防止「幻覺 (Hallucination)」(非法動作) 與「邏輯漂移 (Logical Drift)」(言行不一)。

---

## 🏗️ 常見組裝模式 (Benchmarks)

### Type A: "天真" 代理人 (Baseline)

沒有治理或特殊記憶加持的標準 LLM 代理人。

```bash
python run_flood.py --memory-engine window --governance-mode monitor
```

**行為特徵**：高度不穩定。通常在幾年後就會忘記購買保險。

### Type B: "受治" 代理人 (Governed)

修正邏輯錯誤，但仍受制於記憶力限制。

```bash
python run_flood.py --memory-engine window --governance-mode strict
```

**行為特徵**：決策合法，但缺乏遠見。

### Type C: "理性" 代理人 (Full Stack)

完整的認知架構。

```bash
python run_flood.py --memory-engine humancentric --governance-mode strict
```

**行為特徵**：展現長期適應性特徵（例如：維持數十年的保險覆蓋）。
