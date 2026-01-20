# 任務交接 (Handoff) - Task 002

> **日期**：2026-01-16
> **AI 代理**：Gemini (Antigravity)
> **任務 ID**：task-002
> **類型**：experiment
> **範圍**：examples/single_agent/run_flood.py
> **父任務**：task-001 (延續其 Gemma 分析)

## 任務摘要

解決 Gemma (Window Engine) 在非洪水年份表現出極度靜態行為（全選 Do Nothing）的問題。
經分析，原因為 `run_flood.py` 每年生成的記憶項目過多，且更重要的是 **Trust Score Reset Bug** 導致代理人無法累積信任。

## 已完成

- [x] **根因分析**：
  1. Memory Consolidation: 確認 Reference 實作與 Current 實作的記憶密度差異。
  2. **Trust Persistence**: 發現 `InteractionHub` 覆蓋了運行時的 Trust Score，導致代理人每年重置為初始狀態 (0.2-0.5)，永遠無法學會信任。
- [x] **方案設計**：
  1. 合併 Memory Items。
  2. 修正 `InteractionHub` 屬性優先級。
- [x] **驗證計畫**：Unit Test (`verify_fix.py`) + Interim Log Analysis。
- [x] **全面模擬**：正在執行 100-Agent 10-Year Gemma 模擬 (`run_gemma_window.ps1`)。

## 關鍵修改（已套用）

- `examples/single_agent/run_flood.py`:
  - `FinalParityHook.pre_year`: 合併記憶項目以減少窗口消耗。
  - `FinalParityHook.post_year`: 新增中間日誌 `simulation_log_interim.csv` 儲存功能。
- `broker/components/interaction_hub.py` (CRITICAL FIX):
  - 修正屬性載入順序，確保 `trust_in_insurance` 等動態屬性不被初始化數據覆蓋。

## 待完成

- [x] 等待 100-Agent 模擬完成
- [x] 檢查結果分佈是否恢復動態性
  - **驗證成功**: Year 3 Entropy 從 ~1.0 提升至 ~1.4 (Do Nothing 下降至 13%)。
- [x] 更新 `registry.json`

## 產物

- `examples/single_agent/results_window/gemma3_4b_strict/simulation_log.csv` (Running)
- `examples/single_agent/simulation_log_interim.csv` (Verification Log)
- `gemma_diversity_fix_report.md` (詳細報告)

## 上下文

Trust Score 的重置 Bug 導致代理人每年都回到初始的不信任狀態，Memory Fix 雖然有幫助但不足以解決根本問題。兩者結合後模擬表現符合預期。
