@echo off
REM ============================================================================
REM Paper 3 Re-Run: Memory + Social + Reflection Fixes
REM
REM Fixes applied:
REM   1. Memory: ranking_mode=weighted now passed from YAML (was legacy bug)
REM   2. Social: --enable-news-media --enable-social-media --enable-communication added
REM   3. Reflection: reads YAML interval config + FloodHouseholdAdapter wired in
REM   4. YAML: cognitive_config engine=humancentric (was universal, mismatch)
REM
REM Previous results archived at: paper3/results/_archive_legacy_memory/
REM
REM Estimated time: ~6-8hr per experiment x 6 = ~36-48hr total
REM ============================================================================

cd /d "%~dp0\.."

echo [%date% %time%] Starting Paper 3 re-run with weighted memory mode...

REM === Full hybrid_v2 seed_42 ===
if exist "paper3\results\paper3_hybrid_v2\seed_42\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Full seed_42 already exists
) else (
    echo [%date% %time%] START: Full seed_42
    python run_unified_experiment.py --model gemma3:4b --seed 42 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --output paper3/results/paper3_hybrid_v2/seed_42
    echo [%date% %time%] DONE: Full seed_42
)

REM === Full hybrid_v2 seed_123 ===
if exist "paper3\results\paper3_hybrid_v2\seed_123\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Full seed_123 already exists
) else (
    echo [%date% %time%] START: Full seed_123
    python run_unified_experiment.py --model gemma3:4b --seed 123 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --output paper3/results/paper3_hybrid_v2/seed_123
    echo [%date% %time%] DONE: Full seed_123
)

REM === Full hybrid_v2 seed_456 ===
if exist "paper3\results\paper3_hybrid_v2\seed_456\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Full seed_456 already exists
) else (
    echo [%date% %time%] START: Full seed_456
    python run_unified_experiment.py --model gemma3:4b --seed 456 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --output paper3/results/paper3_hybrid_v2/seed_456
    echo [%date% %time%] DONE: Full seed_456
)

REM === Ablation B seed_42 ===
if exist "paper3\results\paper3_ablation_flat_baseline\seed_42\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Ablation B seed_42 already exists
) else (
    echo [%date% %time%] START: Ablation B seed_42
    python run_unified_experiment.py --model gemma3:4b --seed 42 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-custom-affordability --enable-financial-constraints --load-initial-memories --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_ablation_flat_baseline/seed_42
    echo [%date% %time%] DONE: Ablation B seed_42
)

REM === Ablation B seed_123 ===
if exist "paper3\results\paper3_ablation_flat_baseline\seed_123\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Ablation B seed_123 already exists
) else (
    echo [%date% %time%] START: Ablation B seed_123
    python run_unified_experiment.py --model gemma3:4b --seed 123 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-custom-affordability --enable-financial-constraints --load-initial-memories --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_ablation_flat_baseline/seed_123
    echo [%date% %time%] DONE: Ablation B seed_123
)

REM === Ablation B seed_456 ===
if exist "paper3\results\paper3_ablation_flat_baseline\seed_456\gemma3_4b_strict\simulation_log.csv" (
    echo [%date% %time%] SKIP: Ablation B seed_456 already exists
) else (
    echo [%date% %time%] START: Ablation B seed_456
    python run_unified_experiment.py --model gemma3:4b --seed 456 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-custom-affordability --enable-financial-constraints --load-initial-memories --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_ablation_flat_baseline/seed_456
    echo [%date% %time%] DONE: Ablation B seed_456
)

echo [%date% %time%] === ALL 6 EXPERIMENTS COMPLETE ===
pause
