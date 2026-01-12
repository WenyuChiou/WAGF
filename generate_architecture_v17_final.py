import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.font_manager import FontProperties
import os

# --- Configuration ---
ARTIFACT_DIR = r"C:\Users\wenyu\.gemini\antigravity\brain\f2b36be6-b9c6-4a3f-8a0e-010648b12f8f"
ARTIFACT_PATH = os.path.join(ARTIFACT_DIR, "unified_architecture_v17_python_definitive.png")

# Colors
COLOR_LLM_BG = "#E3F2FD"    # Soft Blue
COLOR_BROKER_BG = "#F5F5F5" # Soft Grey
COLOR_SIM_BG = "#E8F5E9"    # Soft Green

COLOR_BLUE = "#2196F3"
COLOR_GREEN = "#4CAF50"
COLOR_GREY = "#9E9E9E"
COLOR_RED = "#F44336"
COLOR_PURPLE = "#9C27B0"

COLOR_TEXT = "#212121"
COLOR_NODE_BORDER = "#000000"

# Font settings
plt.rcParams['font.sans-serif'] = ['Segoe UI', 'Arial', 'sans-serif']
font_title = FontProperties(size=26, weight='bold')
font_layer = FontProperties(size=18, weight='bold')
font_node = FontProperties(size=14, weight='bold')
font_label = FontProperties(size=12)
font_icon = FontProperties(fname="C:\\Windows\\Fonts\\seguiemj.ttf", size=24) if os.path.exists("C:\\Windows\\Fonts\\seguiemj.ttf") else FontProperties(size=24)

# --- Drawing ---
fig, ax = plt.subplots(figsize=(14, 14), facecolor="#FFFFFF")
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis('off')

# Title
ax.text(50, 98, "Governed Broker Framework - Unified Architecture (v17 Definitive)", 
        fontproperties=font_title, ha='center', va='center', color=COLOR_TEXT)

# 1. LLM Agent Layer (Top)
rect_llm = patches.Rectangle((2, 75), 96, 20, linewidth=1, edgecolor=COLOR_GREY, facecolor=COLOR_LLM_BG, alpha=1.0)
ax.add_patch(rect_llm)
ax.text(5, 93, "LLM Agent Layer", fontproperties=font_layer, color=COLOR_BLUE, ha='left', va='center')

# Agent Nodes
def add_agent_node(x, y, label):
    # Main box
    rect = patches.FancyBboxPatch((x, y), 18, 12, boxstyle="round,pad=0.2", linewidth=1.5, edgecolor=COLOR_NODE_BORDER, facecolor="white")
    ax.add_patch(rect)
    # Robot Icon
    ax.text(x + 9, y + 8, "🤖", fontproperties=font_icon, ha='center', va='center')
    # Label
    ax.text(x + 9, y + 3, label, fontproperties=font_node, ha='center', va='center')

add_agent_node(10, 78, "Agent 1")
add_agent_node(35, 78, "Agent 2")
add_agent_node(65, 78, "Agent N")

# 2. Governed Broker Layer (Middle)
rect_broker = patches.Rectangle((2, 35), 96, 35, linewidth=1, edgecolor=COLOR_GREY, facecolor=COLOR_BROKER_BG, alpha=1.0)
ax.add_patch(rect_broker)
ax.text(5, 67, "Governed Broker Layer", fontproperties=font_layer, color=COLOR_TEXT, ha='left', va='center')

# Broker Nodes
def add_broker_node(x, y, w, h, label, icon=""):
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1", linewidth=1.5, edgecolor=COLOR_NODE_BORDER, facecolor="white")
    ax.add_patch(rect)
    if icon:
        ax.text(x + w/2, y + h*0.65, icon, fontproperties=font_icon, ha='center', va='center')
        ax.text(x + w/2, y + h*0.25, label, fontproperties=font_node, ha='center', va='center')
    else:
        ax.text(x + w/2, y + h/2, label, fontproperties=font_node, ha='center', va='center')

add_broker_node(5, 48, 16, 14, "Context\nBuilder", "👁️")
add_broker_node(28, 48, 16, 14, "Model Adapter", "⚙️")
add_broker_node(51, 48, 16, 14, "Skill\nRegistry", "📖")
add_broker_node(74, 48, 14, 14, "Validators", "🛡️")
add_broker_node(42, 38, 16, 8, "Audit Writer", "📄")

# 3. Simulation Layer (Bottom)
rect_sim = patches.Rectangle((2, 5), 96, 25, linewidth=1, edgecolor=COLOR_GREY, facecolor=COLOR_SIM_BG, alpha=1.0)
ax.add_patch(rect_sim)
ax.text(5, 27, "Simulation Layer", fontproperties=font_layer, color=COLOR_GREEN, ha='left', va='center')

# Sim Nodes
def add_sim_node(x, y, w, h, label, icon=""):
    rect = patches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.1", linewidth=1.5, edgecolor=COLOR_NODE_BORDER, facecolor="white")
    ax.add_patch(rect)
    if icon:
        ax.text(x + w/2, y + h*0.65, icon, fontproperties=font_icon, ha='center', va='center')
        ax.text(x + w/2, y + h*0.25, label, fontproperties=font_node, ha='center', va='center')
    else:
        ax.text(x + w/2, y + h/2, label, fontproperties=font_node, ha='center', va='center')

add_sim_node(5, 8, 18, 15, "Tiered\nEnvironment", "🌍")
add_sim_node(38, 8, 24, 15, "Memory & Retrieval\nModule", "🧠")
add_sim_node(74, 8, 18, 15, "System\nExecution", "🔒")

# --- Arrows (Information Flow) ---

def draw_arrow(x1, y1, x2, y2, label="", color="black", ls='solid', label_pos=0.5):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->,head_width=0.6,head_length=0.8", lw=3.0, color=color, ls=ls))
    if label:
        ax.text(x1 + (x2-x1)*label_pos, y1 + (y2-y1)*label_pos, label, 
                fontproperties=font_label, color=color, ha='center', va='center', backgroundcolor="white")

# 1. Perception & Context (Simulation -> Broker)
draw_arrow(14, 23, 13, 48, "State", color=COLOR_GREEN, label_pos=0.4)
draw_arrow(50, 23, 15, 48, "History", color=COLOR_GREEN, label_pos=0.3)

# 2. Context -> Agent (Broker -> LLM)
draw_arrow(13, 62, 19, 78, "Bounded Context", color=COLOR_BLUE, label_pos=0.5)

# 3. Agent -> Proposal (LLM -> Broker)
# Combined proposal from agent nodes to Adapter
draw_arrow(36, 78, 36, 62, "Skill Proposal", color=COLOR_BLUE, label_pos=0.5)

# 4. Broker Internal Flow
# Decoupled Context Builder. No arrow to Adapter.
draw_arrow(44, 55, 51, 55, "", color=COLOR_GREY) # Adapter -> Registry
draw_arrow(67, 55, 74, 55, "", color=COLOR_GREY) # Registry -> Validator

# 5. Governance -> Execution (Broker -> Simulation)
draw_arrow(81, 48, 83, 23, "Approved Skill", color=COLOR_PURPLE, label_pos=0.5)

# 6. Audit Flow (One-way pointing to Audit Writer)
draw_arrow(37, 62, 43, 46, "Audit Trace", color=COLOR_GREY, ls='dashed', label_pos=0.6) # From Proposal stream
draw_arrow(81, 44, 58, 41, "Audit Trace", color=COLOR_GREY, ls='dashed', label_pos=0.5) # From Validator
draw_arrow(83, 23, 58, 40, "Audit Trace", color=COLOR_GREY, ls='dashed', label_pos=0.6) # From Execution

# 7. Simulation Feedback
# Mutation & Commit
draw_arrow(74, 15, 62, 15, "", color=COLOR_GREEN) # Execution -> Memory
draw_arrow(38, 15, 23, 15, "Mutation & Commit", color=COLOR_GREEN, label_pos=0.5) # Memory -> Env

plt.tight_layout()
plt.savefig(ARTIFACT_PATH, dpi=120, bbox_inches='tight')
print(f"Definitive V17 diagram saved to {ARTIFACT_PATH}")
