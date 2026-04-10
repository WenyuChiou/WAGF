@echo off
setlocal

REM Paper 3 full pivot to Gemma 4 e4b
REM Runs 5 experiments for complete 3-seed pooled Full + 3-seed Ablation B
REM seed_42 Full already exists (do not rerun)
REM Total estimated time: ~85 hr (~3.5 days)
REM thinking_mode=disabled now correctly routes top-level (fc6c599)
REM PA criteria added (145198c) — does NOT fully fix G4 saturation but keeps latest prompt

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set COMMON_ARGS=--model gemma4:e4b --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --thinking-mode disabled

cd /d %BASE%\examples\multi_agent\flood

echo ============================================
echo   Paper 3 Gemma 4 FULL PIVOT
echo   5 runs: seed 123/456 Full + seed 42/123/456 Ablation B
echo ============================================

echo.
echo [1/5] Full condition seed 123
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --output paper3/results/paper3_gemma4_e4b/seed_123
if errorlevel 1 ( echo FAILED seed_123 Full & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED seed_123 missing manifest & exit /b 1 )

echo.
echo [2/5] Full condition seed 456
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --output paper3/results/paper3_gemma4_e4b/seed_456
if errorlevel 1 ( echo FAILED seed_456 Full & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED seed_456 missing manifest & exit /b 1 )

echo.
echo [3/5] Ablation B (Flat policy) seed 42
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat/seed_42
if errorlevel 1 ( echo FAILED ablation seed_42 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_42 missing manifest & exit /b 1 )

echo.
echo [4/5] Ablation B (Flat policy) seed 123
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat/seed_123
if errorlevel 1 ( echo FAILED ablation seed_123 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_123 missing manifest & exit /b 1 )

echo.
echo [5/5] Ablation B (Flat policy) seed 456
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat/seed_456
if errorlevel 1 ( echo FAILED ablation seed_456 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_456 missing manifest & exit /b 1 )

echo ============================================
echo   ALL 5 RUNS COMPLETE
echo ============================================
pause
