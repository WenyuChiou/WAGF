@echo off
setlocal

REM Paper 3 Gemma 4 e4b — Ablation B ONLY (flat institutional policy, CLEAN memory)
REM
REM Runs 5-7 of the original full experiment batch, split out because
REM the earlier batch halted on CLEAN seed_456 interruption.
REM
REM Flat baseline = subsidy pinned at 50%% (50), CRS class 10 (0%% discount).
REM Same memory_write_policy CLEAN applied to all 3 seeds.
REM
REM Total: 3 runs x ~17 hr = ~51 hr (~2.1 days)

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set COMMON_ARGS=--model gemma4:e4b --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --thinking-mode disabled

cd /d %BASE%\examples\multi_agent\flood

echo ============================================
echo   Paper 3 Gemma 4 Ablation B ONLY
echo   3 runs: flat institutional x seed {42, 123, 456}
echo   CLEAN memory policy applied throughout
echo ============================================

echo.
echo [1/3] CLEAN Ablation B (flat policy) seed 42
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_42
if errorlevel 1 ( echo FAILED CLEAN ablation seed_42 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_42 missing manifest & exit /b 1 )

echo.
echo [2/3] CLEAN Ablation B (flat policy) seed 123
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_123
if errorlevel 1 ( echo FAILED CLEAN ablation seed_123 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_123 missing manifest & exit /b 1 )

echo.
echo [3/3] CLEAN Ablation B (flat policy) seed 456
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_456
if errorlevel 1 ( echo FAILED CLEAN ablation seed_456 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_456 missing manifest & exit /b 1 )

echo.
echo ============================================
echo   Ablation B complete (all 3 seeds)
echo ============================================

endlocal
