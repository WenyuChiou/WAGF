"""Check income distribution in agent profiles."""
import sys, csv
sys.stdout.reconfigure(encoding='utf-8', errors='replace')

with open('examples/multi_agent/flood/data/agent_profiles_balanced.csv', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f'Total agents: {len(rows)}')
print(f'Columns: {list(rows[0].keys())}')

# Income distribution
incomes = [float(r['income']) for r in rows]
incomes.sort()
print(f'\nIncome distribution:')
print(f'  Min: ${min(incomes):,.0f}')
print(f'  Max: ${max(incomes):,.0f}')
print(f'  Mean: ${sum(incomes)/len(incomes):,.0f}')
print(f'  Median: ${incomes[len(incomes)//2]:,.0f}')

# Percentiles
for p in [5, 10, 25, 50, 75, 90, 95]:
    idx = int(len(incomes) * p / 100)
    print(f'  P{p}: ${incomes[idx]:,.0f}')

# Count by bracket
brackets = {}
for r in rows:
    b = r.get('income_bracket', '?')
    brackets[b] = brackets.get(b, 0) + 1
print(f'\nIncome brackets:')
for b, c in sorted(brackets.items()):
    print(f'  {b}: {c} agents')

# Show agents with income <= 5000
low = [r for r in rows if float(r['income']) <= 5000]
print(f'\nAgents with income <= $5,000: {len(low)} ({len(low)/len(rows)*100:.1f}%)')
for r in low[:15]:
    print(f"  {r['agent_id']}: income=${float(r['income']):,.0f}, bracket={r.get('income_bracket','?')}, mg={r.get('mg','?')}, tenure={r.get('tenure','?')}")
if len(low) > 15:
    print(f'  ... and {len(low)-15} more')

# MG vs NMG income comparison
mg_inc = [float(r['income']) for r in rows if r.get('mg') == '1' or r.get('mg') == 'True']
nmg_inc = [float(r['income']) for r in rows if r.get('mg') == '0' or r.get('mg') == 'False']
if mg_inc:
    print(f'\nMG income: mean=${sum(mg_inc)/len(mg_inc):,.0f}, min=${min(mg_inc):,.0f}, n={len(mg_inc)}')
if nmg_inc:
    print(f'NMG income: mean=${sum(nmg_inc)/len(nmg_inc):,.0f}, min=${min(nmg_inc):,.0f}, n={len(nmg_inc)}')
