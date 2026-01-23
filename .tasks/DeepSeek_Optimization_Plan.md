# DeepSeek R1 8B Performance Optimization Plan

## 1. Problem Summary

DeepSeek R1 8B's "Reasoning Mode" generates extensive internal Chain-of-Thought (`<think>...</think>`) tokens, leading to:

- **Long inference times** (2-5 minutes per agent step).
- **HTTP timeouts** (Fixed: Extended to 600s).
- **High VRAM consumption** during long thinking phases.

---

## 2. Optimization Levers

### 2.1 Model-Level (Ollama Side)

| Parameter     | Current                | Recommended | Impact                                                            |
| ------------- | ---------------------- | ----------- | ----------------------------------------------------------------- |
| `num_ctx`     | 16384 (Auto)           | **4096**    | Reduces KV Cache size. Faster per-token generation.               |
| `num_predict` | -1 (Unlimited)         | **4096**    | Caps total thinking + answer tokens. Prevents runaway generation. |
| Quantization  | Q8 (if using original) | **Q4_K_M**  | ~40% faster, <5% quality loss.                                    |

**Action**: Add to `agent_types.yaml` under `global_config`:

```yaml
global_config:
  llm:
    num_ctx: 4096
    num_predict: 4096
    temperature: 0.1 # Already in use
```

### 2.2 Client-Level (Python Side)

| Optimization                 | Status         | Notes                                                                 |
| ---------------------------- | -------------- | --------------------------------------------------------------------- |
| **Timeout Extension**        | ✅ Fixed       | Extended to 600s for DeepSeek.                                        |
| **Thinking Token Stripping** | ✅ Implemented | `<think>` blocks are removed post-generation.                         |
| **Prompt Compression**       | 🟡 Optional    | For stress tests, use a "Lite Prompt" mode without verbose narrative. |

**Action (Prompt Compression)**: Add a flag `--lite-prompt` to scripts that triggers a shorter system prompt for benchmarking speed.

### 2.3 I/O-Level (Log Storage)

**Problem**: Writing JSONL to OneDrive causes file lock delays.

| Optimization         | Implementation                                     | Impact                                             |
| -------------------- | -------------------------------------------------- | -------------------------------------------------- |
| **Buffered Writes**  | Accumulate traces in memory, flush every N traces. | Reduces syscall overhead.                          |
| **Local Disk First** | Write to `C:\Temp\...`, sync to OneDrive later.    | Avoids cloud sync latency.                         |
| **Async I/O**        | Use `aiofiles` for non-blocking writes.            | Overkill for single-agent, useful for 100+ agents. |

**Action**: Patch `broker/components/audit_writer.py` to buffer traces:

```python
# In GenericAuditWriter.__init__
self._buffer_size = 10 # Flush every 10 traces
self._buffer_count = 0

# In write_trace (after adding to buffer)
self._buffer_count += 1
if self._buffer_count >= self._buffer_size:
    self._flush_buffer()
    self._buffer_count = 0
```

---

## 3. Hardware Recommendations

| Check               | Command                                           | Expected                                    |
| ------------------- | ------------------------------------------------- | ------------------------------------------- |
| **GPU Offloading**  | `ollama show deepseek-r1:8b`                      | Should show CUDA layers.                    |
| **VRAM Allocated**  | `nvidia-smi --query-gpu=memory.used --format=csv` | Should be ~6-8GB for 8B model.              |
| **Flash Attention** | N/A                                               | Enabled by default in recent Ollama builds. |

---

## 4. Summary: Top 3 Quick Wins

1.  **Set `num_predict: 4096`** in YAML. This immediately caps runaway thinking.
2.  **Run experiments on LOCAL disk** (e.g., `C:\Temp\JOH_RUNS\`). Sync to Desktop/OneDrive after completion.
3.  **Use Q4_K_M quantization** if model is currently Q8. Command: `ollama pull deepseek-r1:8b-q4_k_m`.

---

## 5. Future Considerations

- **DeepSeek R1 Distilled Models**: If speed is critical, consider using a smaller "distilled" variant (if available).
- **vLLM Serving**: For production-scale ABM (10,000+ agents), consider switching from Ollama to vLLM for batched inference.
