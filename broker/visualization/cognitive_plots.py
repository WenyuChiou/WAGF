"""
Cognitive Visualization Tools for XAI-ABM Integration.

Provides plotting functions for cognitive trace analysis following
traditional ABM visualization patterns (NetLogo-style).

Part of Task-031C: Explainable Memory Retrieval.
"""
from typing import List, Dict, Optional, TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from broker.components.cognitive_trace import CognitiveTrace
    from broker.components.symbolic_context import SymbolicContextMonitor


def plot_cognitive_timeline(
    traces: List["CognitiveTrace"],
    save_path: Optional[str] = None,
    figsize: tuple = (12, 8)
):
    """
    Plot cognitive state over time for an agent.

    Creates a 3-panel figure showing:
    1. Surprise level vs threshold (with System 2 regions highlighted)
    2. System state (System 1 vs System 2)
    3. Novelty markers (when new states are encountered)

    Args:
        traces: List of CognitiveTrace objects from an agent
        save_path: Optional path to save the figure
        figsize: Figure size tuple

    Returns:
        matplotlib Figure object
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        raise ImportError("matplotlib is required for visualization. Install with: pip install matplotlib")

    if not traces:
        raise ValueError("No traces provided")

    # Convert traces to DataFrame
    df = pd.DataFrame([t.to_dict() for t in traces])

    fig, axes = plt.subplots(3, 1, figsize=figsize, sharex=True)

    # Panel 1: Surprise over time
    ax1 = axes[0]
    ax1.plot(df["tick"], df["surprise"], "b-", linewidth=2, label="Surprise")
    ax1.axhline(y=df["arousal_threshold"].iloc[0], color="r", linestyle="--", 
                linewidth=1.5, label="Threshold")
    ax1.fill_between(df["tick"], df["surprise"], df["arousal_threshold"],
                     where=df["surprise"] > df["arousal_threshold"], 
                     alpha=0.3, color="red", label="System 2 Active")
    ax1.set_ylabel("Surprise")
    ax1.legend(loc="upper right")
    ax1.set_title(f"Cognitive Timeline: Agent {traces[0].agent_id}")
    ax1.set_ylim(0, 1.1)
    ax1.grid(True, alpha=0.3)

    # Panel 2: System state
    ax2 = axes[1]
    system_numeric = [1 if s == "SYSTEM_2" else 0 for s in df["system"]]
    ax2.fill_between(df["tick"], system_numeric, step="post", alpha=0.5, color="steelblue")
    ax2.set_ylabel("System")
    ax2.set_yticks([0, 1])
    ax2.set_yticklabels(["System 1\n(Routine)", "System 2\n(Crisis)"])
    ax2.set_ylim(-0.1, 1.1)
    ax2.grid(True, alpha=0.3)

    # Panel 3: Novelty markers
    ax3 = axes[2]
    if "is_novel" in df.columns:
        novel_ticks = df[df["is_novel"] == True]["tick"]
        ax3.scatter(novel_ticks, [1]*len(novel_ticks), marker="*", s=100, c="gold", 
                   edgecolors="darkorange", linewidth=1, label="Novel State", zorder=5)
    ax3.set_ylabel("Novel Events")
    ax3.set_xlabel("Tick")
    ax3.set_yticks([0, 1])
    ax3.set_yticklabels(["", "Novel"])
    ax3.set_ylim(-0.1, 1.5)
    ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def plot_signature_frequency(
    frequency_map: Dict[str, int],
    top_n: int = 10,
    save_path: Optional[str] = None,
    figsize: tuple = (10, 6)
):
    """
    Visualize most common state signatures as horizontal bar chart.

    Args:
        frequency_map: Dict mapping signature hashes to counts
        top_n: Number of top signatures to show
        save_path: Optional path to save the figure
        figsize: Figure size tuple

    Returns:
        matplotlib Figure object
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        raise ImportError("matplotlib is required for visualization")

    if not frequency_map:
        raise ValueError("Empty frequency map")

    sorted_sigs = sorted(frequency_map.items(), key=lambda x: x[1], reverse=True)[:top_n]

    labels = [sig[:8] + "..." for sig, _ in sorted_sigs]
    counts = [count for _, count in sorted_sigs]

    fig, ax = plt.subplots(figsize=figsize)
    bars = ax.barh(labels, counts, color="steelblue", edgecolor="navy")
    
    # Add count labels
    for bar, count in zip(bars, counts):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                str(count), va="center", fontsize=10)

    ax.set_xlabel("Frequency")
    ax.set_title("Most Common State Signatures")
    ax.invert_yaxis()  # Top signature at top
    ax.grid(True, axis="x", alpha=0.3)

    plt.tight_layout()

    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches="tight")

    return fig


def export_traces_to_csv(
    traces: List["CognitiveTrace"],
    output_path: str
) -> str:
    """
    Export cognitive traces to CSV for external analysis.

    Args:
        traces: List of CognitiveTrace objects
        output_path: Path to save the CSV file

    Returns:
        Path to the saved file
    """
    df = pd.DataFrame([t.to_dict() for t in traces])
    df.to_csv(output_path, index=False)
    return output_path


def print_trace_summary(traces: List["CognitiveTrace"]) -> str:
    """
    Generate a text summary of cognitive traces for console output.

    Args:
        traces: List of CognitiveTrace objects

    Returns:
        Formatted summary string
    """
    if not traces:
        return "No traces to summarize."

    total = len(traces)
    s2_count = sum(1 for t in traces if t.system == "SYSTEM_2")
    novel_count = sum(1 for t in traces if t.is_novel)
    avg_surprise = sum(t.surprise for t in traces) / total

    lines = [
        "=" * 50,
        "COGNITIVE TRACE SUMMARY",
        "=" * 50,
        f"Total Observations: {total}",
        f"System 2 Activations: {s2_count} ({s2_count/total:.1%})",
        f"Novel States Encountered: {novel_count} ({novel_count/total:.1%})",
        f"Average Surprise: {avg_surprise:.2f}",
        f"Agent ID: {traces[0].agent_id}",
        f"Tick Range: {traces[0].tick} - {traces[-1].tick}",
        "=" * 50,
    ]

    return "\n".join(lines)
