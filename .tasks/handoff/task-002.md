# 任務交接 (Handoff) - Task 002

> **日期**：2026-01-16
> **AI 代理**：Gemini (Antigravity)
> **任務 ID**：task-002
> **類型**：experiment
> **範圍**：examples/single_agent/run_flood.py
> **父任務**：task-001 (延續其 Gemma 分析)

## 任務摘要

解決 Gemma (Window Engine) 在非洪水年份表現出極度靜態行為（全選 Do Nothing）的問題。
經分析，原因為 `run_flood.py` 每年生成的記憶項目過多（平均 4 項），導致 Window Size=5 的窗口在一兩年內完全喪失歷史上下文（如「洪水頻率增加」的初始記憶）。

## 已完成

- [x] **根因分析**：確認 Reference 實作在關鍵年份（無 Grant）僅生成 3 項記憶，允許上下文存活。Current 實作因 Grant 機率與 Observ 拆分導致生成過多。
- [x] **方案設計**：提出合併 `run_flood.py` 中觀察記憶（Elevated + Relocated）為單行以降低記憶消耗。
- [x] **驗證計畫**：規劃 5-Agent 3-Year 測試與 100-Agent 10-Year 全量跑法。
- [x] **全面模擬**：正在執行 100-Agent 10-Year Gemma 模擬 (`examples/single_agent/results_window`) 以生成最終數據。

## 關鍵修改（尚未套用）

- `examples/single_agent/run_flood.py`（提案）：
  - `FinalParityHook.pre_year`: 合併兩行 `I observe % ...` 為一行。
  - `FinalParityHook.post_year`: 新增 `memory` 欄位記錄至 CSV 以供分析。

## 待完成

- [ ] 等待 100-Agent 模擬完成
- [ ] 檢查結果分佈是否恢復動態性
- [ ] 更新 `registry.json`

## 產物

- `examples/single_agent/results_window/gemma3_4b_strict/simulation_log.csv` (Running)

## 上下文

此修復不需更換 Memory Engine 即可恢復 Window 版的動態行為，符合 "Parity" 目標。
