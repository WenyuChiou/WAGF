"""
End-to-End Test for Exp3 Multi-Agent Pipeline

Tests: data_loader, prompts, parsers, audit_writer
"""

import sys
sys.path.insert(0, '.')

def test_pipeline():
    print('=== 1. Testing Data Loader ===')
    from examples.exp3_multi_agent.data_loader import load_households_from_csv
    households = load_households_from_csv()
    print(f'Loaded {len(households)} households')
    h1 = households[0]
    print(f'Agent: {h1.state.id}, MG={h1.state.mg}, Tenure={h1.state.tenure}')

    print('\n=== 2. Testing Prompt Generation ===')
    from examples.exp3_multi_agent.prompts import build_household_prompt
    state = {
        'mg': h1.state.mg,
        'tenure': h1.state.tenure,
        'elevated': h1.state.elevated,
        'has_insurance': h1.state.has_insurance,
        'cumulative_damage': 50000,
        'property_value': 240000
    }
    ctx = {
        'government_subsidy_rate': 0.5, 
        'insurance_premium_rate': 0.05, 
        'flood_occurred': True, 
        'year': 3
    }
    mem = ['Year 2: Flood caused damage']
    prompt = build_household_prompt(state, ctx, mem)
    print(f'Prompt generated: {len(prompt)} chars')
    print('First 200 chars:', prompt[:200])

    print('\n=== 3. Testing Parser ===')
    from examples.exp3_multi_agent.parsers import parse_household_response
    mock_response = """
TP Assessment: HIGH - I experienced significant damage and floods are recurring.
CP Assessment: MODERATE - My income is limited but subsidy helps.
SP Assessment: HIGH - 50% government subsidy available.
SC Assessment: MODERATE - I believe I can take action with support.
PA Assessment: NONE - No protections currently in place.
Final Decision: 2
Justification: Given my high threat perception and access to subsidies, elevation is the best choice.
"""
    output = parse_household_response(mock_response, h1.state.id, h1.state.mg, h1.state.tenure, 3, False)
    print(f'Parsed: validated={output.validated}, decision={output.decision_skill}')
    print(f'TP={output.tp_level}, justification={output.justification[:50]}...')

    print('\n=== 4. Testing Audit Writer ===')
    from examples.exp3_multi_agent.audit_writer import AuditWriter, AuditConfig
    config = AuditConfig(output_dir='examples/exp3_multi_agent/results/test_audit')
    audit = AuditWriter(config)
    audit.write_household_trace(output, state, ctx)
    summary = audit.finalize()
    print(f'Audit summary: {summary["total_household_decisions"]} decisions logged')
    print(f'Decision rates: {summary.get("decision_rates", {})}')

    print('\n=== ALL TESTS PASSED ===')

if __name__ == "__main__":
    test_pipeline()
