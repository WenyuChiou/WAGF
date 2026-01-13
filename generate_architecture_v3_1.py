
from graphviz import Digraph
import os

def generate_architecture_v3_1():
    dot = Digraph(comment='Governed Broker Framework v3.1', format='png')
    dot.attr(rankdir='TB', splines='ortho', nodesep='0.8', ranksep='1.0')
    
    # ---------------------------
    # Global Style (Minimalist Black & White)
    # ---------------------------
    dot.attr('node', shape='box', style='rounded,filled', fillcolor='white', 
             color='black', fontname='Arial', fontsize='12', penwidth='2.0')
    dot.attr('edge', color='black', penwidth='2.0', arrowsize='1.0', fontname='Arial', fontsize='10')

    # ---------------------------
    # 1. Context Builder (Cluster)
    # ---------------------------
    with dot.subgraph(name='cluster_context') as c:
        c.attr(label='CONTEXT BUILDER', fontname='Arial-Bold', fontsize='14', style='rounded', penwidth='2.0', color='black')
        
        # Stacked inputs
        c.node('system_p', 'SYSTEM', shape='oval', width='1.5')
        c.node('personal_p', 'PERSONAL (Tier 0)', shape='oval', width='1.5')
        c.node('local_p', 'LOCAL (Tier 1)', shape='oval', width='1.5')
        c.node('global_p', 'GLOBAL (Tier 2)', shape='oval', width='1.5')
        c.node('inst_p', 'INSTITUTIONAL (Tier 3)', shape='oval', width='1.5')
        
        # Invisible edge to force stacking
        c.edge('system_p', 'personal_p', style='invis')
        c.edge('personal_p', 'local_p', style='invis')
        c.edge('local_p', 'global_p', style='invis')
        c.edge('global_p', 'inst_p', style='invis')

    # ---------------------------
    # 2. Main Components
    # ---------------------------
    # System Execution Loop (Central Hub)
    dot.node('system_exec', 'SYSTEM\nEXECUTION LOOP\n(Controls Flow)', shape='component', height='1.2', width='2.5', fontsize='14', fontname='Arial-Bold')

    # Memory Engine (Right)
    with dot.subgraph(name='cluster_memory') as m:
        m.attr(label='MEMORY ENGINE', fontname='Arial-Bold', fontsize='14', style='rounded', penwidth='2.0')
        m.node('mem_retrieve', 'RETRIEVE\nEXPERIENCE', shape='Mrecord')
        m.node('mem_store', 'STORE\nEXPERIENCE', shape='Mrecord')

    # Model Adapter (Center)
    dot.node('adapter', 'MODEL ADAPTER\n(Unified)', shape='box', height='1.0', width='2.0', fontsize='13', fontname='Arial-Bold')

    # Validator (Bottom)
    dot.node('validator', 'GOVERNANCE\nVALIDATOR', shape='doubleoctagon', height='1.0', fontsize='13', fontname='Arial-Bold')

    # Audit (Bottom Right)
    dot.node('audit', 'AUDIT WRITER\n(Log & Trace)', shape='folder', height='0.8')

    # ---------------------------
    # 3. Connections (Logic Flow)
    # ---------------------------
    
    # Execution <-> Context
    dot.edge('system_exec', 'system_p', label='Build Request', dir='forward')
    dot.edge('cluster_context', 'system_exec', label='Context Dict', dir='forward') # Abstract return from cluster

    # Execution <-> Memory
    dot.edge('system_exec', 'mem_retrieve', label='Get Memory')
    dot.edge('mem_retrieve', 'system_exec', label='History')
    dot.edge('system_exec', 'mem_store', label='Update State')

    # Execution -> Adapter
    dot.edge('system_exec', 'adapter', label='Prompt\n(+Context)')

    # Adapter -> Validator
    dot.edge('adapter', 'validator', label='Skill Proposal')

    # Validator -> Execution (User requested this arrow)
    dot.edge('validator', 'system_exec', label='Execution Result\n(Approved/Rejected)', constraint='false') 
    # constraint=false lets it loop back without messing up the hierarchy too much

    # Side outputs (Audit)
    dot.edge('adapter', 'audit', label='Trace Log') # Adapter -> Audit
    dot.edge('validator', 'audit', label='Validation Log')

    # NO Arrow from Context -> Adapter (User request 1)
    
    # Save
    output_path = 'docs/governed_broker_architecture_v3_1'
    dot.render(output_path, view=False, cleanup=True)
    print(f"Diagram generated at: {output_path}.png")

if __name__ == "__main__":
    generate_architecture_v3_1()
