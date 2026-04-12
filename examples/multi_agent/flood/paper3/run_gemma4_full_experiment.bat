@echo off
setlocal

REM Paper 3 Gemma 4 e4b — FULL EXPERIMENT (LEGACY baseline + CLEAN pivot)
REM
REM ALL runs have initial memories loaded (path fix ceefcba).
REM
REM Run 1: LEGACY baseline seed_42 (ratchet ACTIVE, for ablation comparison)
REM Run 2-4: CLEAN Full seeds 42, 123, 456 (ratchet BLOCKED, primary data)
REM Run 5-7: CLEAN Ablation B seeds 42, 123, 456 (flat institutional policy)
REM
REM Total: 7 runs x ~17 hr = ~119 hr (~5 days)

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set COMMON_ARGS=--model gemma4:e4b --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --thinking-mode disabled

cd /d %BASE%\examples\multi_agent\flood

echo ============================================
echo   Paper 3 Gemma 4 FULL EXPERIMENT
echo   7 runs: 1 LEGACY + 3 CLEAN Full + 3 CLEAN Ablation B
echo   ALL runs have initial memories loaded
echo ============================================

echo.
echo [1/7] LEGACY baseline seed 42 (ratchet ACTIVE)
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --memory-policy-preset legacy --output paper3/results/paper3_gemma4_e4b_legacy/seed_42
if errorlevel 1 ( echo FAILED LEGACY seed_42 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_legacy\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED LEGACY seed_42 missing manifest & exit /b 1 )

echo.
echo [2/7] CLEAN Full seed 42 (ratchet BLOCKED — ablation match)
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --output paper3/results/paper3_gemma4_e4b_clean/seed_42
if errorlevel 1 ( echo FAILED CLEAN seed_42 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN seed_42 missing manifest & exit /b 1 )

echo.
echo [3/7] CLEAN Full seed 123
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --output paper3/results/paper3_gemma4_e4b_clean/seed_123
if errorlevel 1 ( echo FAILED CLEAN seed_123 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN seed_123 missing manifest & exit /b 1 )

echo.
echo [4/7] CLEAN Full seed 456
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --output paper3/results/paper3_gemma4_e4b_clean/seed_456
if errorlevel 1 ( echo FAILED CLEAN seed_456 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN seed_456 missing manifest & exit /b 1 )

echo.
echo [5/7] CLEAN Ablation B (flat policy) seed 42
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_42
if errorlevel 1 ( echo FAILED CLEAN ablation seed_42 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_42 missing manifest & exit /b 1 )

echo.
echo [6/7] CLEAN Ablation B (flat policy) seed 123
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_123
if errorlevel 1 ( echo FAILED CLEAN ablation seed_123 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_123 missing manifest & exit /b 1 )

echo.
echo [7/7] CLEAN Ablation B (flat policy) seed 456
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_456
if errorlevel 1 ( echo FAILED CLEAN ablation seed_456 & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED CLEAN ablation seed_456 missing manifest & exit /b 1 )

echo ============================================
echo   ALL 7 RUNS COMPLETE
echo ============================================
echo.
echo Ablation comparison (same seed, same initial memories, only policy differs):
echo   LEGACY: paper3/results/paper3_gemma4_e4b_legacy/seed_42/
echo   CLEAN:  paper3/results/paper3_gemma4_e4b_clean/seed_42/
pause
