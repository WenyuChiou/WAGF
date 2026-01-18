# NY/NJ FEMA 補助計畫研究

## 概述

本文整理 NY/NJ 真實洪水減災計畫，為 Government Agent 設計提供參數。

---

## 1. New York 計畫

### 1.1 NYC Build It Back (Sandy 後)

**資金與規模**
| 項目 | 數值 |
|------|------|
| 資金來源 | HUD CDBG-DR |
| 總預算 | $2.3 Billion (單戶) |
| 升高戶數 | ~4,000 homes |
| 受益家庭 | 12,500 families |

**Elevation 補助**
| 項目 | 內容 |
|------|------|
| 補助比例 | **100%** (全額補助) |
| 升高成本 | ~$200,000/戶 |
| NY 州承諾 | $300M 專款 |
| 資格 | 100-year flood zone 內 |
| 條件 | 須維持洪水保險 |

### 1.2 NY Buyout 激勵

**激勵結構**
| 激勵類型 | 比例 | 說明 |
|----------|------|------|
| 基礎購買 | 100% | 災前公平市價 |
| 高風險區獎勵 | +10% | 500-year floodplain 內 |
| 留在 NYC 獎勵 | +10% | 維持市內稅基 |
| 團體搬遷獎勵 | +5% | 已取消 |
| 其他費用 | 全額 | 評估/產權/調查 |

**總計: 最高可達災前市價 120%**

---

## 2. New Jersey Blue Acres

### 2.1 計畫概述

| 項目 | 內容 |
|------|------|
| 類型 | 自願收購 (Voluntary) |
| 管理 | NJ DEP |
| 土地用途 | 永久開放綠地 |
| 目標 | 洪水緩衝區 + 生態恢復 |

### 2.2 資金來源

| 來源 | 類型 |
|------|------|
| FEMA HMGP | 聯邦減災 |
| HUD CDBG-DR | 災後恢復 |
| 州企業稅 | 州資金 |

### 2.3 激勵機制

**Safe Housing Incentive**
- 條件: 搬遷至 SFHA (100-year floodplain) 外
- 用途: 協助搬遷費用
- 目標: 鼓勵永久脫離高風險區

---

## 3. FEMA 標準 Cost Share

### 3.1 HMGP (Hazard Mitigation Grant Program)

| 類別 | Federal | State/Local | 說明 |
|------|---------|-------------|------|
| 標準 | 75% | 25% | 一般申請 |
| Repetitive Loss | 90% | 10% | 多次理賠戶 |
| Severe Repetitive Loss | **100%** | 0% | 嚴重重複損失 |

### 3.2 FMA (Flood Mitigation Assistance)

| 類別 | Federal | State/Local |
|------|---------|-------------|
| 標準 | 75% | 25% |

### 3.3 年度漲幅上限

| 物件類型 | 上限 |
|----------|------|
| 主要住宅 | 18%/年 |
| 其他物件 | 25%/年 |

---

## 4. 對 Government Agent 的設計影響

### 4.1 Subsidy Rate 參數

基於真實計畫，建議:

| 情境 | 補助比例 | 參考 |
|------|----------|------|
| MG + Severe Loss | 100% | FEMA SRL |
| MG + Repetitive Loss | 90% | FEMA RL |
| MG 標準 | 75% | FEMA HMGP |
| NMG 標準 | 50% | 降低優先 |

### 4.2 Buyout 激勵參數

| 激勵 | 比例 | 參考 |
|------|------|------|
| 基礎市價 | 100% | NY/NJ |
| 高風險獎勵 | +10% | NY |
| 區內搬遷獎勵 | +10% | NY |
| 搬出 SFHA 獎勵 | Lump sum | NJ Blue Acres |

### 4.3 Skills 設計建議

| Skill | 參數 | 參考 |
|-------|------|------|
| `approve_elevation_subsidy` | 75-100% | FEMA HMGP |
| `approve_buyout` | 100%+激勵 | NY/NJ |
| `increase_subsidy` | +10-20% | 災後調整 |
| `target_repetitive_loss` | 優先 90-100% | FEMA RL/SRL |

---

## 5. 參考來源

1. NYC Build It Back - nyc.gov
2. NJ Blue Acres - nj.gov
3. FEMA HMGP - fema.gov
4. GAO Reports - gao.gov
5. HUD CDBG-DR - hud.gov
