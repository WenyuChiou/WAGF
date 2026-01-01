# Governed Broker Framework

<div align="center">

**A governance middleware for LLM-driven Agent-Based Models**

[![English](https://img.shields.io/badge/lang-English-blue)](README.md#english) [![中文](https://img.shields.io/badge/lang-中文-red)](README.md#中文)

</div>

---

## English

### ✨ v0.3 Multi-LLM Extensibility

| v0.2 Skill-Governed | v0.3 Extensible |
|---------------------|-----------------|
| Single LLM adapter | Multi-LLM Provider Registry |
| Hardcoded validators | Dynamic validator loading |
| Sync only | Async + Rate limiting |

👉 See [`docs/skill_architecture.md`](docs/skill_architecture.md) for architecture details.

### Quick Start

#### Single LLM (Simple)
```bash
pip install -r requirements.txt
cd examples/skill_governed_flood
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

#### Multi-LLM (Advanced)
```python
from providers import OllamaProvider, OpenAIProvider
from interfaces import LLMProviderRegistry

# Register multiple providers
registry = LLMProviderRegistry()
registry.register("local", OllamaProvider(model="llama3.2:3b"))
registry.register("cloud", OpenAIProvider(api_key="..."))

# Use different LLMs for different tasks
local_response = registry.get("local").invoke(prompt)
cloud_response = registry.get("cloud").invoke(prompt)
```

### Architecture

| Single-Agent | Multi-Agent |
|--------------|-------------|
| ![Single-Agent](docs/single_agent_architecture.png) | ![Multi-Agent](docs/multi_agent_architecture.png) |

### Key Components

| Component | Purpose |
|-----------|---------|
| `SkillBrokerEngine` | Main orchestrator with agent_type support |
| `StateManager` | Individual/Shared/Institutional state |
| `SkillRegistry` | Skills with agent type eligibility |
| `LLMProviderRegistry` | Multi-LLM management (Ollama default) |
| `ValidatorFactory` | Dynamic validator loading |

### Validation Pipeline

1. **Admissibility** - Skill exists? Agent eligible?
2. **Feasibility** - Preconditions met?
3. **Constraints** - Once-only? Annual limit?
4. **Effect Safety** - Safe state changes?
5. **PMT Consistency** - Reasoning consistent?
6. **Uncertainty** - Response confident?

### License

MIT

---


## 中文

### ✨ v0.3 多 LLM 擴充性

| v0.2 技能治理 | v0.3 可擴充 |
|---------------|-------------|
| 單一 LLM 適配器 | Multi-LLM Provider Registry |
| 固定驗證器 | 動態驗證器載入 |
| 同步處理 | 非同步 + 速率限制 |

👉 詳見 [`docs/skill_architecture.md`](docs/skill_architecture.md)

### 快速開始

#### 單一 LLM（簡單）
```bash
pip install -r requirements.txt
cd examples/skill_governed_flood
python run_experiment.py --model llama3.2:3b --num-agents 100 --num-years 10
```

#### 多 LLM（進階）
```python
from providers import OllamaProvider, OpenAIProvider
from interfaces import LLMProviderRegistry

# 註冊多個 LLM 提供者
registry = LLMProviderRegistry()
registry.register("local", OllamaProvider(model="llama3.2:3b"))
registry.register("cloud", OpenAIProvider(api_key="..."))

# 根據需求使用不同 LLM
local_response = registry.get("local").invoke(prompt)
cloud_response = registry.get("cloud").invoke(prompt)
```

### 核心元件

| 元件 | 用途 |
|------|------|
| `SkillBrokerEngine` | 主協調器 |
| `LLMProviderRegistry` | 多 LLM 管理 |
| `DomainConfigLoader` | YAML 驅動配置 |
| `ValidatorFactory` | 動態驗證器載入 |
| `RateLimiter` | API 速率控制 |

### 驗證管線

1. **Admissibility** - 技能存在？代理有權限？
2. **Feasibility** - 前置條件滿足？
3. **Constraints** - 單次限制？年度限制？
4. **Effect Safety** - 狀態變更安全？
5. **PMT Consistency** - 推理一致？
6. **Uncertainty** - 回應確定？

### 授權

MIT

