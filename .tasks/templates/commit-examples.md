# Git Commit 訊息範例集

本文件提供各種情境的 commit 訊息範例，供 AI 代理參考。

---

## 新功能 (feat)

### 添加配置選項
```
feat(llm): Add configurable temperature parameter

- Add LLM_CONFIG dataclass for global configuration
- Support CLI arguments: --temperature, --top-p, --top-k
- Default to Ollama defaults when not specified

Why: Framework version had lower output diversity than original
because it explicitly set temperature=0.8

Refs: .tasks/handoff/current-session.md
```

### 添加新 API
```
feat(api): Add batch processing endpoint

- Add /api/v1/batch endpoint for bulk operations
- Support async processing with job tracking
- Add rate limiting (100 req/min)

Why: Users need to process multiple items efficiently

Breaking: None
```

### 添加 UI 組件
```
feat(ui): Add dark mode toggle

- Add ThemeProvider context
- Implement dark/light theme switching
- Persist preference to localStorage

Why: User request for dark mode support
```

---

## 修復 Bug (fix)

### 修復解析錯誤
```
fix(parser): Handle empty LLM response gracefully

- Add null check before parsing response
- Return default action when response is empty
- Add warning log for debugging

Why: Production errors when LLM returns empty string
Fixes: #123
```

### 修復邏輯錯誤
```
fix(agent): Correct decision mapping for elevated houses

- Fix skill_map_elevated to exclude 'elevate_house' option
- Update option numbering (1,2,3 instead of 1,2,4)

Why: Elevated houses were still seeing elevation option
```

### 修復性能問題
```
fix(perf): Reduce memory usage in large experiments

- Use generator instead of list for agent iteration
- Clear cache after each year
- Add gc.collect() at year boundaries

Why: OOM errors with 1000+ agents
```

---

## 重構 (refactor)

### 移除硬編碼
```
refactor(core): Remove domain-specific hardcoding from core modules

- Make Mock LLM domain-agnostic (extract options from prompt)
- Move audit field names to YAML config
- Move stopwords to config (audit_blacklist)

Why: Core modules should not contain experiment-specific code
to maintain framework generalizability

Breaking: None - backward compatible with flood experiment
```

### 提取公共邏輯
```
refactor(utils): Extract common validation logic

- Create ValidationMixin class
- Move duplicate validation code to mixin
- Update all validators to use mixin

Why: DRY principle - validation was duplicated in 5 places
```

### 重命名
```
refactor(api): Rename 'callback' to 'webhook' for clarity

- Rename CallbackConfig to WebhookConfig
- Update all references in codebase
- Add deprecation warning for old name

Why: 'webhook' is more accurate for external HTTP calls
```

---

## 文檔 (docs)

### 更新 README
```
docs(readme): Update installation instructions

- Add Python 3.10+ requirement
- Update pip install command
- Add troubleshooting section

Why: Users were confused by outdated instructions
```

### 添加 API 文檔
```
docs(api): Add OpenAPI specification

- Add openapi.yaml with all endpoints
- Include request/response examples
- Document error codes

Why: Enable API documentation generation
```

### 代碼註釋
```
docs(code): Add docstrings to core modules

- Add module-level docstrings
- Document public functions
- Add type hints

Why: Improve code maintainability
```

---

## 測試 (test)

### 添加單元測試
```
test(parser): Add unit tests for response parsing

- Test valid JSON parsing
- Test malformed JSON handling
- Test edge cases (empty, null, special chars)

Coverage: parser.py 85% -> 95%
```

### 添加整合測試
```
test(e2e): Add end-to-end experiment test

- Test full experiment run with mock LLM
- Verify output file generation
- Check audit log completeness

Why: Catch integration issues early
```

---

## 雜項 (chore)

### 更新依賴
```
chore(deps): Update langchain to v0.1.0

- Update langchain from 0.0.350 to 0.1.0
- Update langchain-community to 0.0.13
- Fix breaking changes in import paths

Why: Security updates and new features
```

### CI/CD 配置
```
chore(ci): Add GitHub Actions workflow

- Add test workflow on PR
- Add lint check
- Add coverage report

Why: Automate quality checks
```

---

## 複合變更

### 功能 + 測試
```
feat(agent): Add retry mechanism for LLM calls

- Add exponential backoff retry (3 attempts)
- Add configurable timeout
- Add unit tests for retry logic

Why: Intermittent LLM API failures causing experiment crashes

Test: pytest tests/test_retry.py -v
```

---

## 不良範例 (避免)

```
fix stuff                    ← 太模糊
update                       ← 沒有說明
WIP                          ← 不應 commit 未完成工作
changes                      ← 無意義
fix bug                      ← 沒說明修了什麼 bug
more changes                 ← 完全無用
asdfasdf                     ← ???
```

---

## Commit 訊息檢查清單

- [ ] 類型正確 (feat/fix/refactor/docs/test/chore)
- [ ] Scope 準確描述影響範圍
- [ ] Subject 簡潔明瞭 (< 50 字元)
- [ ] Body 解釋了「什麼」和「為什麼」
- [ ] 包含相關 issue/PR 引用
- [ ] 如有破壞性變更，已標註 Breaking

---

*最後更新：2025-01-15*
