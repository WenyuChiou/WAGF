"""
Performance Tuner - Adaptive configuration for LLM experiments.

This module provides automatic parameter tuning based on:
1. Model size (extracted from model tag)
2. Available GPU VRAM
3. Experiment requirements

Usage:
    from broker.utils.performance_tuner import get_optimal_config
    config = get_optimal_config(model_tag="qwen3:1.7b")
    # Returns: PerformanceConfig(num_ctx=4096, workers=2, num_predict=512)
"""
import re
import subprocess
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

_LOGGER = logging.getLogger(__name__)

# =============================================================================
# Configuration Presets based on Model Size Tiers
# =============================================================================
# Format: (max_params_billions, num_ctx, num_predict, base_workers)
# NOTE: Small models need higher num_predict because they output more tokens
#       to express the same idea (less compression efficiency).
MODEL_TIER_PRESETS = [
    (2.0,   4096,  2048, 4),  # Tiny: 0-2B (e.g., Qwen 1.7B) - Unified 2048 for Fairness
    (5.0,   4096,  2048, 2),  # Small: 2-5B (e.g., Qwen 4B) - 2048 for Thinking + JSON
    (10.0,  8192,  2048, 2),  # Base: 5-10B (e.g., Qwen 8B, DeepSeek 8B)
    (20.0,  8192,  2048, 1),  # Mid: 10-20B (e.g., Qwen 14B)
    (30.0,  8192,  2048, 1),  # Large: 30B (User Custom) - Standardized Buffer
    (50.0,  4096,  2048, 1),  # Large: 32B-50B (e.g., Qwen 32B)
    (100.0, 2048,  2048, 1),  # XL: 50-100B (e.g., Qwen 72B)
]

# VRAM thresholds for worker scaling (in GB)
VRAM_THRESHOLDS = {
    "low": 8,      # < 8GB: Aggressive throttling
    "medium": 16,  # 8-16GB: Standard
    "high": 24,    # 16-24GB: Allow parallelism
    "ultra": 48,   # 24GB+: Full speed
}


@dataclass
class PerformanceConfig:
    """Optimal configuration for a specific model/hardware combination."""
    num_ctx: int
    num_predict: int
    workers: int
    model_size_b: float  # Estimated model size in billions
    vram_available_gb: float  # Detected VRAM
    tuning_reason: str  # Human-readable explanation


def parse_model_size(model_tag: str) -> float:
    """
    Extract model size (in billions) from model tag.
    
    Examples:
        "qwen3:1.7b" -> 1.7
        "llama3.2:3b" -> 3.0
        "deepseek-r1:8b" -> 8.0
        "gpt-oss:latest" -> 20.0 (fallback heuristic)
    """
    tag_lower = model_tag.lower()
    
    # Pattern 1: Explicit "Xb" or "X.Yb" suffix
    match = re.search(r'(\d+(?:\.\d+)?)\s*b\b', tag_lower)
    if match:
        return float(match.group(1))
    
    # Pattern 2: Size in model name like "7b-instruct"
    match = re.search(r'(\d+)b[-_]', tag_lower)
    if match:
        return float(match.group(1))
    
    # Pattern 3: Known model heuristics
    known_sizes = {
        "gpt-oss": 20.0,
        "mistral-small": 22.0,
        "phi-3-mini": 3.8,
        "gemma-2": 9.0,
    }
    for prefix, size in known_sizes.items():
        if prefix in tag_lower:
            return size
    
    # Fallback: Assume 7B (common default)
    _LOGGER.warning(f"Could not parse model size from '{model_tag}', defaulting to 7B")
    return 7.0


def get_available_vram() -> float:
    """
    Query available GPU VRAM in GB.
    
    Uses nvidia-smi for NVIDIA GPUs. Falls back to 8GB if detection fails.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            # Get first GPU's free memory (in MiB)
            free_mib = float(result.stdout.strip().split('\n')[0])
            free_gb = free_mib / 1024
            return round(free_gb, 1)
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError) as e:
        _LOGGER.warning(f"Could not query VRAM: {e}")
    
    # Fallback: Assume 8GB (common consumer card)
    return 8.0


def _get_tier_preset(model_size_b: float) -> Tuple[int, int, int]:
    """Get (num_ctx, num_predict, base_workers) for model size."""
    for max_size, ctx, predict, workers in MODEL_TIER_PRESETS:
        if model_size_b <= max_size:
            return ctx, predict, workers
    # XL fallback
    return 2048, 256, 1


def _adjust_workers_for_vram(base_workers: int, vram_gb: float, model_size_b: float) -> int:
    """
    Adjust worker count based on available VRAM and model size.
    
    Heuristic: Each worker needs roughly (model_size * 0.5 + ctx_overhead) GB
    """
    # Estimate per-worker memory footprint (rough)
    # Model weights: ~0.5GB per billion params (int4 quantization)
    # KV Cache: ~0.5-1GB per 4k context
    per_worker_gb = model_size_b * 0.5 + 1.0  # Conservative estimate
    
    max_workers = max(1, int(vram_gb / per_worker_gb))
    
    # Apply VRAM tier limits
    if vram_gb < VRAM_THRESHOLDS["low"]:
        max_workers = min(max_workers, 1)
    elif vram_gb < VRAM_THRESHOLDS["medium"]:
        max_workers = min(max_workers, 2)
    elif vram_gb < VRAM_THRESHOLDS["high"]:
        max_workers = min(max_workers, 3)
    # Ultra: No additional limit
    
    return min(base_workers, max_workers)


def get_optimal_config(
    model_tag: str,
    override_vram_gb: Optional[float] = None,
    min_workers: int = 1,
    max_workers: int = 8
) -> PerformanceConfig:
    """
    Get optimal performance configuration for a model.
    
    Args:
        model_tag: Ollama model tag (e.g., "qwen3:1.7b")
        override_vram_gb: Override detected VRAM (for testing)
        min_workers: Minimum parallel workers
        max_workers: Maximum parallel workers
        
    Returns:
        PerformanceConfig with tuned parameters
    """
    # 1. Detect model size
    model_size_b = parse_model_size(model_tag)
    
    # 2. Detect VRAM
    vram_gb = override_vram_gb if override_vram_gb else get_available_vram()
    
    # 3. Get tier preset
    num_ctx, num_predict, base_workers = _get_tier_preset(model_size_b)
    
    # 4. Adjust workers for VRAM
    optimal_workers = _adjust_workers_for_vram(base_workers, vram_gb, model_size_b)
    optimal_workers = max(min_workers, min(optimal_workers, max_workers))
    
    # 5. Build explanation
    reason = (
        f"Model: {model_size_b:.1f}B params | "
        f"VRAM: {vram_gb:.1f}GB | "
        f"Preset: ctx={num_ctx}, predict={num_predict} | "
        f"Workers: {optimal_workers} (adjusted from {base_workers})"
    )
    
    _LOGGER.info(f"[PerformanceTuner] {reason}")
    
    return PerformanceConfig(
        num_ctx=num_ctx,
        num_predict=num_predict,
        workers=optimal_workers,
        model_size_b=model_size_b,
        vram_available_gb=vram_gb,
        tuning_reason=reason
    )


# =============================================================================
# Convenience Functions
# =============================================================================
def apply_to_llm_config(config: PerformanceConfig):
    """
    Apply performance config to the global LLM_CONFIG.
    
    Usage:
        from broker.utils.performance_tuner import get_optimal_config, apply_to_llm_config
        perf = get_optimal_config("qwen3:1.7b")
        apply_to_llm_config(perf)
    """
    from broker.utils.llm_utils import LLM_CONFIG
    LLM_CONFIG.num_ctx = config.num_ctx
    LLM_CONFIG.num_predict = config.num_predict
    _LOGGER.info(f"[PerformanceTuner] Applied: num_ctx={config.num_ctx}, num_predict={config.num_predict}")


def print_config_summary(model_tag: str):
    """Print a human-readable summary of optimal config."""
    config = get_optimal_config(model_tag)
    print(f"""
╔══════════════════════════════════════════════════════════════╗
║  PERFORMANCE TUNER - Auto-Configuration                      ║
╠══════════════════════════════════════════════════════════════╣
║  Model:           {model_tag:<40} ║
║  Estimated Size:  {config.model_size_b:<5.1f}B parameters                           ║
║  Detected VRAM:   {config.vram_available_gb:<5.1f}GB                                    ║
╠══════════════════════════════════════════════════════════════╣
║  RECOMMENDED SETTINGS:                                        ║
║    Context Window: {config.num_ctx:<6} tokens                            ║
║    Max Predict:    {config.num_predict:<6} tokens                            ║
║    Parallel Workers: {config.workers:<4}                                    ║
╚══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    # Quick test
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:1.7b"
    print_config_summary(model)
