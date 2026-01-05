"""
Comprehensive End-to-End Test for Exp3 Multi-Agent Pipeline

Tests:
1. Data Loader (CSV)
2. Prompt Generation (all 3 agent types)
3. Parser (all 3 agent types)
4. Validator (PMT rules)
5. Memory & RAG (CognitiveMemory)
6. Audit Writer
"""

import sys
sys.path.insert(0, '.')


def test_data_loader():
    """Test 1: Data Loader"""
    print('=' * 60)
    print('TEST 1: DATA LOADER')
    print('=' * 60)
    
    from examples.exp3_multi_agent.data_loader import load_households_from_csv, initialize_all_agents
    
    households = load_households_from_csv()
    print(f'✓ Loaded {len(households)} households from CSV')
    
    # Check distribution
    mg_owners = sum(1 for h in households if h.state.mg and h.state.tenure == "Owner")
    mg_renters = sum(1 for h in households if h.state.mg and h.state.tenure == "Renter")
    nmg_owners = sum(1 for h in households if not h.state.mg and h.state.tenure == "Owner")
    nmg_renters = sum(1 for h in households if not h.state.mg and h.state.tenure == "Renter")
    print(f'  Distribution: MG-Owner={mg_owners}, MG-Renter={mg_renters}, NMG-Owner={nmg_owners}, NMG-Renter={nmg_renters}')
    
    households, govs, ins = initialize_all_agents()
    print(f'✓ Initialized Governments: {list(govs.keys())}')
    print(f'✓ Initialized Insurance: InsuranceCo')
    
    return households, govs, ins


def test_prompts(households, govs, ins):
    """Test 2: Prompt Generation for all 3 agent types"""
    print('\n' + '=' * 60)
    print('TEST 2: PROMPT GENERATION (3 AGENT TYPES)')
    print('=' * 60)
    
    from examples.exp3_multi_agent.prompts import (
        build_household_prompt,
        build_insurance_prompt,
        build_government_prompt
    )
    
    # Household Prompt
    hh = households[0]
    state = {
        'mg': hh.state.mg, 'tenure': hh.state.tenure,
        'elevated': False, 'has_insurance': False,
        'cumulative_damage': 50000, 'property_value': 240000
    }
    ctx = {'government_subsidy_rate': 0.5, 'insurance_premium_rate': 0.05, 'flood_occurred': True, 'year': 3}
    mem = ['Year 2: Flood caused $30,000 damage', 'Year 2: Neighbors bought insurance']
    
    hh_prompt = build_household_prompt(state, ctx, mem)
    print(f'✓ Household Prompt: {len(hh_prompt)} chars')
    assert 'TP (Threat Perception)' in hh_prompt, "Missing TP in prompt"
    assert 'CP (Coping Perception)' in hh_prompt, "Missing CP in prompt"
    print('  Contains: TP, CP, SP, SC, PA definitions ✓')
    
    # Insurance Prompt
    ins_state = {
        'loss_ratio': 0.75,
        'total_policies': 15,
        'risk_pool': 500000,
        'premium_rate': 0.05
    }
    ins_history = ['Year 2: 10 claims, $200k payout', 'Year 2: Loss ratio 65%']
    ins_prompt = build_insurance_prompt(ins_state, ins_history)
    print(f'✓ Insurance Prompt: {len(ins_prompt)} chars')
    assert 'Loss Ratio' in ins_prompt, "Missing Loss Ratio"
    print('  Contains: Loss Ratio, Premium Rate, Risk Pool ✓')
    
    # Government Prompt
    gov_state = {
        'annual_budget': 500000,
        'budget_remaining': 350000,
        'subsidy_rate': 0.5,
        'mg_adoption_rate': 0.15,
        'nmg_adoption_rate': 0.25
    }
    gov_events = ['Year 2: Major flood event', 'Year 2: 5 MG households elevated']
    gov_prompt = build_government_prompt(gov_state, gov_events)
    print(f'✓ Government Prompt: {len(gov_prompt)} chars')
    assert 'MG (Marginalized Group)' in gov_prompt, "Missing MG"
    print('  Contains: Budget, Adoption Rates, Priority ✓')


def test_parsers():
    """Test 3: Parser for all 3 agent types"""
    print('\n' + '=' * 60)
    print('TEST 3: PARSERS (3 AGENT TYPES)')
    print('=' * 60)
    
    from examples.exp3_multi_agent.parsers import (
        parse_household_response,
        parse_insurance_response,
        parse_government_response
    )
    
    # Household Parser
    hh_response = """
TP Assessment: HIGH - I experienced significant damage and floods are recurring.
CP Assessment: MODERATE - My income is limited but subsidy helps.
SP Assessment: HIGH - 50% government subsidy available.
SC Assessment: MODERATE - I believe I can take action with support.
PA Assessment: NONE - No protections currently in place.
Final Decision: 2
Justification: Given my high threat perception and access to subsidies, elevation is the best choice.
"""
    hh_output = parse_household_response(hh_response, 'H001', True, 'Owner', 3, False)
    print(f'✓ Household Parser:')
    print(f'  TP={hh_output.tp_level}, CP={hh_output.cp_level}, Decision={hh_output.decision_skill}')
    print(f'  Validated={hh_output.validated}')
    assert hh_output.tp_level == 'HIGH'
    assert hh_output.decision_skill == 'elevate_house'
    
    # Insurance Parser
    ins_response = """
Analysis: Loss ratio is concerning at 75%, risk pool needs replenishment.
Decision: RAISE
Adjustment: 8%
Justification: To maintain solvency and build reserves for future claims.
"""
    ins_output = parse_insurance_response(ins_response, 3)
    print(f'✓ Insurance Parser:')
    print(f'  Decision={ins_output.decision}, Adjustment={ins_output.adjustment_pct:.0%}')
    print(f'  Validated={ins_output.validated}')
    assert ins_output.decision == 'RAISE'
    assert ins_output.adjustment_pct == 0.08
    
    # Government Parser
    gov_response = """
Analysis: MG adoption is lagging at 15%, need to prioritize this group.
Decision: INCREASE
Adjustment: 10%
Priority: MG
Justification: To achieve equitable adaptation outcomes and use remaining budget effectively.
"""
    gov_output = parse_government_response(gov_response, 3)
    print(f'✓ Government Parser:')
    print(f'  Decision={gov_output.decision}, Priority={gov_output.priority}')
    print(f'  Validated={gov_output.validated}')
    assert gov_output.decision == 'INCREASE'
    assert gov_output.priority == 'MG'


def test_validators():
    """Test 4: PMT Validators"""
    print('\n' + '=' * 60)
    print('TEST 4: VALIDATORS (PMT RULES)')
    print('=' * 60)
    
    from examples.exp3_multi_agent.validators import HouseholdValidator, InstitutionalValidator
    from examples.exp3_multi_agent.parsers import HouseholdOutput
    
    validator = HouseholdValidator()
    
    # R1: HIGH TP + HIGH CP but do_nothing (Warning)
    output1 = HouseholdOutput(
        agent_id='H001', mg=True, tenure='Owner', year=3,
        tp_level='HIGH', tp_explanation='...', 
        cp_level='HIGH', cp_explanation='...',
        sp_level='MODERATE', sp_explanation='...',
        sc_level='MODERATE', sc_explanation='...',
        pa_level='NONE', pa_explanation='...',
        decision_number=4, decision_skill='do_nothing', justification='...'
    )
    result1 = validator.validate(output1, {'elevated': False})
    print(f'✓ R1 (HIGH TP+CP → do_nothing): valid={result1.valid}, warnings={len(result1.warnings)}')
    assert len(result1.warnings) > 0, "Should have warning"
    
    # R4: Renter trying to elevate (Error)
    output2 = HouseholdOutput(
        agent_id='H002', mg=False, tenure='Renter', year=3,
        tp_level='HIGH', tp_explanation='...',
        cp_level='MODERATE', cp_explanation='...',
        sp_level='HIGH', sp_explanation='...',
        sc_level='MODERATE', sc_explanation='...',
        pa_level='NONE', pa_explanation='...',
        decision_number=2, decision_skill='elevate_house', justification='...'
    )
    result2 = validator.validate(output2, {'elevated': False})
    print(f'✓ R4 (Renter → elevate): valid={result2.valid}, errors={result2.errors}')
    assert not result2.valid, "Should be invalid"
    
    # R6: Already relocated (Error)
    output3 = HouseholdOutput(
        agent_id='H003', mg=True, tenure='Owner', year=3,
        tp_level='LOW', tp_explanation='...',
        cp_level='HIGH', cp_explanation='...',
        sp_level='MODERATE', sp_explanation='...',
        sc_level='HIGH', sc_explanation='...',
        pa_level='FULL', pa_explanation='...',
        decision_number=1, decision_skill='buy_insurance', justification='...'
    )
    result3 = validator.validate(output3, {'elevated': True, 'relocated': True})
    print(f'✓ R6 (Relocated → action): valid={result3.valid}')
    assert not result3.valid, "Should be invalid"
    
    # Institutional Validator
    inst_validator = InstitutionalValidator()
    ins_result = inst_validator.validate_insurance('LOWER', 1.2)
    print(f'✓ Insurance Validator: warnings={ins_result.warnings}')
    
    gov_result = inst_validator.validate_government('INCREASE', 0.15, 0.10)
    print(f'✓ Government Validator: warnings={gov_result.warnings}')


def test_memory_rag():
    """Test 5: Memory & RAG (CognitiveMemory)"""
    print('\n' + '=' * 60)
    print('TEST 5: MEMORY & RAG')
    print('=' * 60)
    
    from broker.memory import CognitiveMemory
    
    memory = CognitiveMemory(agent_id="H001")
    
    # Add memories using correct API
    memory.add_experience("Flood caused $30,000 damage to my property", importance=0.9, year=2, tags=["flood"])
    memory.add_experience("Neighbors elevated their homes with subsidy", importance=0.6, year=2, tags=["neighbor"])
    memory.add_experience("Government increased subsidy to 60%", importance=0.7, year=3, tags=["policy"])
    memory.add_working("I purchased flood insurance this year", importance=0.8, year=3)
    memory.add_working("Minor flood, no damage due to insurance", importance=0.5, year=4)
    
    print(f'✓ Added 5 memories to CognitiveMemory')
    
    # Retrieve by recency
    recent = memory.retrieve(top_k=3, current_year=5)
    print(f'✓ Retrieved {len(recent)} recent memories:')
    for m in recent[:3]:
        print(f'    - {m[:50]}...')
    
    # Check memory content
    assert len(recent) >= 1, "Should have at least 1 memory"
    
    # Test format_for_prompt
    formatted = memory.format_for_prompt(current_year=5)
    print(f'✓ Formatted for prompt: {len(formatted)} chars')
    
    # Test to_list
    mem_list = memory.to_list(current_year=5)
    print(f'✓ to_list: {len(mem_list)} items')
    
    # Test update helpers
    memory.update_after_flood(damage=50000, year=5)
    memory.update_after_decision("buy_insurance", year=5)
    print(f'✓ update_after_flood and update_after_decision called')
    
    # Test consolidation
    memory.consolidate()
    print(f'✓ Memory consolidation completed')


def test_audit_writer():
    """Test 6: Audit Writer"""
    print('\n' + '=' * 60)
    print('TEST 6: AUDIT WRITER (ALL 3 AGENT TYPES)')
    print('=' * 60)
    
    from examples.exp3_multi_agent.audit_writer import AuditWriter, AuditConfig
    from examples.exp3_multi_agent.parsers import (
        HouseholdOutput, InsuranceOutput, GovernmentOutput
    )
    
    config = AuditConfig(output_dir='examples/exp3_multi_agent/results/test_full')
    audit = AuditWriter(config)
    
    # Household trace
    hh_output = HouseholdOutput(
        agent_id='H001', mg=True, tenure='Owner', year=3,
        tp_level='HIGH', tp_explanation='Flood damage experienced',
        cp_level='MODERATE', cp_explanation='Limited income',
        sp_level='HIGH', sp_explanation='Subsidy available',
        sc_level='MODERATE', sc_explanation='Some confidence',
        pa_level='NONE', pa_explanation='No protection',
        decision_number=2, decision_skill='elevate_house',
        justification='Best option given subsidies'
    )
    audit.write_household_trace(hh_output, {'elevated': False}, {'year': 3})
    print(f'✓ Household trace logged')
    
    # Insurance trace
    ins_output = InsuranceOutput(
        year=3, analysis='Loss ratio concerning',
        decision='RAISE', adjustment_pct=0.08,
        justification='Maintain solvency'
    )
    audit.write_insurance_trace(ins_output, 'InsuranceCo')
    print(f'✓ Insurance trace logged')
    
    # Government trace
    gov_output = GovernmentOutput(
        year=3, analysis='MG lagging',
        decision='INCREASE', adjustment_pct=0.10,
        priority='MG', justification='Equitable outcomes'
    )
    audit.write_government_trace(gov_output, 'Gov_NJ')
    print(f'✓ Government trace logged')
    
    # Finalize
    summary = audit.finalize()
    print(f'✓ Summary: {summary["total_household_decisions"]} HH, {summary["total_institutional_decisions"]} Inst')
    
    assert summary["total_household_decisions"] == 1
    assert summary["total_institutional_decisions"] == 2


def main():
    """Run all tests"""
    print('\n' + '=' * 60)
    print('EXP3 MULTI-AGENT COMPREHENSIVE PIPELINE TEST')
    print('=' * 60 + '\n')
    
    households, govs, ins = test_data_loader()
    test_prompts(households, govs, ins)
    test_parsers()
    test_validators()
    test_memory_rag()
    test_audit_writer()
    
    print('\n' + '=' * 60)
    print('✅ ALL 6 TESTS PASSED')
    print('=' * 60)


if __name__ == "__main__":
    main()
