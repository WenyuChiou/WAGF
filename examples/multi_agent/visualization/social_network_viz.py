"""
Social Network Visualization

Visualizes the social network graph showing:
1. Node positions (based on grid coordinates)
2. Edges (neighbor connections within radius)
3. Node colors (MG vs NMG classification)
4. Node sizes (based on income level)

Usage:
    python social_network_viz.py --max-agents 20 --radius 3.0 --output social_graph.png
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import matplotlib.pyplot as plt
import numpy as np

# Try to import networkx, fall back gracefully if not installed
try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("[WARNING] networkx not installed. Install with: pip install networkx")

# Add parent paths for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from broker.components.social_graph import (
    SocialGraph,
    SpatialNeighborhoodGraph,
    create_social_graph,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MockAgent:
    """Mock agent for visualization testing."""

    def __init__(
        self,
        agent_id: str,
        grid_x: float,
        grid_y: float,
        is_mg: bool = False,
        income_midpoint: float = 50000,
        identity: str = "owner",
    ):
        self.agent_id = agent_id
        self.grid_x = grid_x
        self.grid_y = grid_y
        self.is_mg = is_mg
        self.income_midpoint = income_midpoint
        self.identity = identity


def create_mock_agents(
    n_agents: int = 20,
    grid_size: int = 10,
    mg_ratio: float = 0.3,
    seed: int = 42,
) -> List[MockAgent]:
    """
    Create mock agents with spatial positions for visualization.

    Args:
        n_agents: Number of agents to create
        grid_size: Size of the grid (grid_size x grid_size)
        mg_ratio: Proportion of MG agents
        seed: Random seed

    Returns:
        List of MockAgent objects
    """
    np.random.seed(seed)
    agents = []

    for i in range(n_agents):
        agent_id = f"H{i+1:04d}"
        grid_x = np.random.uniform(0, grid_size)
        grid_y = np.random.uniform(0, grid_size)
        is_mg = np.random.random() < mg_ratio
        income_midpoint = np.random.choice([25000, 45000, 65000, 85000])
        identity = np.random.choice(["owner", "renter"], p=[0.7, 0.3])

        agents.append(MockAgent(
            agent_id=agent_id,
            grid_x=grid_x,
            grid_y=grid_y,
            is_mg=is_mg,
            income_midpoint=income_midpoint,
            identity=identity,
        ))

    return agents


def build_networkx_graph(
    social_graph: SocialGraph,
    agents: List[Any],
) -> "nx.Graph":
    """
    Build a NetworkX graph from a SocialGraph.

    Args:
        social_graph: SocialGraph instance
        agents: List of agent objects with grid_x, grid_y, is_mg, income_midpoint

    Returns:
        NetworkX Graph object
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for visualization")

    G = nx.Graph()

    # Create agent lookup
    agent_lookup = {a.agent_id: a for a in agents}

    # Add nodes with attributes
    for agent in agents:
        G.add_node(
            agent.agent_id,
            pos=(agent.grid_x, agent.grid_y),
            is_mg=getattr(agent, "is_mg", False),
            income=getattr(agent, "income_midpoint", 50000),
            identity=getattr(agent, "identity", "owner"),
        )

    # Add edges from social graph
    for agent_id in social_graph.agent_ids:
        neighbors = social_graph.get_neighbors(agent_id)
        for neighbor_id in neighbors:
            if not G.has_edge(agent_id, neighbor_id):
                G.add_edge(agent_id, neighbor_id)

    return G


def visualize_social_graph(
    social_graph: SocialGraph,
    agents: List[Any],
    output_path: Optional[Path] = None,
    title: str = "Social Network: Spatial Neighborhood Graph",
    figsize: Tuple[int, int] = (12, 10),
    show_labels: bool = False,
) -> "nx.Graph":
    """
    Generate social network visualization.

    Args:
        social_graph: SocialGraph instance
        agents: List of agent objects
        output_path: Path to save the figure (None to skip saving)
        title: Figure title
        figsize: Figure size (width, height)
        show_labels: Whether to show agent ID labels

    Returns:
        NetworkX Graph object
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required for visualization")

    G = build_networkx_graph(social_graph, agents)

    # Get positions
    pos = nx.get_node_attributes(G, "pos")

    # Node colors: Red for MG, Blue for NMG
    colors = ["#e74c3c" if G.nodes[n]["is_mg"] else "#3498db" for n in G.nodes]

    # Node sizes: Based on income (normalized)
    incomes = [G.nodes[n]["income"] for n in G.nodes]
    min_income, max_income = min(incomes), max(incomes)
    if max_income > min_income:
        sizes = [100 + 200 * (inc - min_income) / (max_income - min_income) for inc in incomes]
    else:
        sizes = [150] * len(incomes)

    # Node shapes: Different for owner vs renter (approximated with alpha)
    alphas = [0.9 if G.nodes[n]["identity"] == "owner" else 0.6 for n in G.nodes]

    # Create figure
    fig, ax = plt.subplots(figsize=figsize)

    # Draw edges
    nx.draw_networkx_edges(G, pos, alpha=0.3, edge_color="gray", ax=ax)

    # Draw nodes with varying alpha
    for i, node in enumerate(G.nodes):
        nx.draw_networkx_nodes(
            G, pos,
            nodelist=[node],
            node_color=[colors[i]],
            node_size=[sizes[i]],
            alpha=alphas[i],
            ax=ax,
        )

    # Draw labels if requested
    if show_labels:
        nx.draw_networkx_labels(G, pos, font_size=6, ax=ax)

    # Add legend
    mg_patch = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#e74c3c',
                          markersize=10, label='MG (Marginalized)')
    nmg_patch = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='#3498db',
                           markersize=10, label='NMG (Non-Marginalized)')
    owner_patch = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                             markersize=10, alpha=0.9, label='Owner (solid)')
    renter_patch = plt.Line2D([0], [0], marker='o', color='w', markerfacecolor='gray',
                              markersize=10, alpha=0.5, label='Renter (faded)')
    ax.legend(handles=[mg_patch, nmg_patch, owner_patch, renter_patch],
              loc='upper left', fontsize=9)

    ax.set_title(title, fontsize=14)
    ax.set_xlabel("Grid X (cells)", fontsize=10)
    ax.set_ylabel("Grid Y (cells)", fontsize=10)

    plt.tight_layout()

    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info(f"Saved visualization to {output_path}")

    return G


def compute_network_statistics(G: "nx.Graph") -> Dict[str, Any]:
    """
    Compute network statistics.

    Args:
        G: NetworkX Graph

    Returns:
        Dictionary of statistics
    """
    if not HAS_NETWORKX:
        return {}

    degrees = [d for n, d in G.degree()]
    mg_nodes = [n for n in G.nodes if G.nodes[n]["is_mg"]]
    nmg_nodes = [n for n in G.nodes if not G.nodes[n]["is_mg"]]

    stats = {
        "n_nodes": G.number_of_nodes(),
        "n_edges": G.number_of_edges(),
        "avg_degree": np.mean(degrees) if degrees else 0,
        "max_degree": max(degrees) if degrees else 0,
        "min_degree": min(degrees) if degrees else 0,
        "density": nx.density(G),
        "n_mg": len(mg_nodes),
        "n_nmg": len(nmg_nodes),
        "mg_ratio": len(mg_nodes) / G.number_of_nodes() if G.number_of_nodes() > 0 else 0,
    }

    # Clustering coefficient
    try:
        stats["avg_clustering"] = nx.average_clustering(G)
    except Exception:
        stats["avg_clustering"] = None

    # Connected components
    try:
        stats["n_components"] = nx.number_connected_components(G)
    except Exception:
        stats["n_components"] = None

    return stats


def print_statistics(stats: Dict[str, Any]) -> None:
    """Print network statistics in a formatted way."""
    print("\n" + "=" * 50)
    print("SOCIAL NETWORK STATISTICS")
    print("=" * 50)
    print(f"  Nodes: {stats['n_nodes']}")
    print(f"  Edges: {stats['n_edges']}")
    print(f"  Density: {stats['density']:.4f}")
    print(f"  Average Degree: {stats['avg_degree']:.2f}")
    print(f"  Degree Range: [{stats['min_degree']}, {stats['max_degree']}]")
    if stats.get("avg_clustering") is not None:
        print(f"  Avg Clustering: {stats['avg_clustering']:.4f}")
    if stats.get("n_components") is not None:
        print(f"  Connected Components: {stats['n_components']}")
    print("-" * 50)
    print(f"  MG Agents: {stats['n_mg']} ({stats['mg_ratio']:.1%})")
    print(f"  NMG Agents: {stats['n_nmg']} ({1 - stats['mg_ratio']:.1%})")
    print("=" * 50 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize social network graph"
    )
    parser.add_argument(
        "--max-agents", type=int, default=20,
        help="Number of agents to visualize"
    )
    parser.add_argument(
        "--radius", type=float, default=3.0,
        help="Neighbor radius (in grid cells)"
    )
    parser.add_argument(
        "--grid-size", type=int, default=10,
        help="Grid size for mock agents"
    )
    parser.add_argument(
        "--mg-ratio", type=float, default=0.3,
        help="MG ratio for mock agents"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed"
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output path for PNG file"
    )
    parser.add_argument(
        "--show-labels", action="store_true",
        help="Show agent ID labels on nodes"
    )
    parser.add_argument(
        "--no-show", action="store_true",
        help="Don't display the plot (just save)"
    )

    args = parser.parse_args()

    if not HAS_NETWORKX:
        print("[ERROR] networkx is required. Install with: pip install networkx")
        sys.exit(1)

    # Create mock agents
    logger.info(f"Creating {args.max_agents} mock agents...")
    agents = create_mock_agents(
        n_agents=args.max_agents,
        grid_size=args.grid_size,
        mg_ratio=args.mg_ratio,
        seed=args.seed,
    )

    # Create social graph
    logger.info(f"Building SpatialNeighborhoodGraph with radius={args.radius}...")

    # Build agent_ids and positions dict
    agent_ids = [a.agent_id for a in agents]
    positions = {a.agent_id: (a.grid_x, a.grid_y) for a in agents}

    social_graph = SpatialNeighborhoodGraph(
        agent_ids=agent_ids,
        positions=positions,
        radius=args.radius,
        metric="euclidean",
        fallback_k=2,
    )

    # Determine output path
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = Path(__file__).parent.parent / "results_unified" / "social_graph.png"

    # Visualize
    logger.info("Generating visualization...")
    G = visualize_social_graph(
        social_graph,
        agents,
        output_path=output_path,
        title=f"Social Network (radius={args.radius}, n={args.max_agents})",
        show_labels=args.show_labels,
    )

    # Compute and print statistics
    stats = compute_network_statistics(G)
    print_statistics(stats)

    # Show plot if not suppressed
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
