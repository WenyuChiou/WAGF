@echo off
setlocal

REM Paper 3 Gemma 4 e4b CLEAN POLICY pivot batch
REM
REM Runs under the new memory_write_policy (ratchet fix, commit in progress).
REM Produces the clean-policy dataset that will back the main Paper 3 results.
REM
REM Scope:
REM   [1/6] seed_42  Full (CLEAN) -- matched ablation to legacy seed_42 baseline
REM   [2/6] seed_123 Full (CLEAN) -- primary pivot data
REM   [3/6] seed_456 Full (CLEAN) -- primary pivot data
REM   [4/6] seed_42  Ablation B (CLEAN, flat baseline policy)
REM   [5/6] seed_123 Ablation B (CLEAN)
REM   [6/6] seed_456 Ablation B (CLEAN)
REM
REM Preserved (DO NOT RERUN):
REM   paper3/results/paper3_gemma4_e4b/seed_42/ -- LEGACY policy, used for
REM   the ratchet ablation comparison in Paper 3 Appendix.
REM
REM Output layout:
REM   paper3/results/paper3_gemma4_e4b_clean/seed_{42,123,456}/
REM   paper3/results/paper3_gemma4_ablation_flat_clean/seed_{42,123,456}/
REM
REM Total estimated wall clock: 6 x 17 hr = ~102 hr (~4.25 days)
REM
REM Pre-flight checklist:
REM   1. broker/config/memory_policy.py exists
REM   2. ma_agent_types.yaml ships memory_write_policy block with CLEAN defaults
REM   3. lifecycle_hooks.py gates sites 3/7/8 on self._mem_policy
REM   4. run_unified_experiment.py loads policy and forwards to MultiAgentHooks
REM   5. pytest paper3/tests/test_memory_write_policy.py passes (33 tests)
REM   6. Legacy paper3_gemma4_e4b/seed_42/ exists and is untouched

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set COMMON_ARGS=--model gemma4:e4b --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --thinking-mode disabled

cd /d %BASE%\examples\multi_agent\flood

echo ============================================
echo   Paper 3 Gemma 4 CLEAN POLICY PIVOT
echo   6 runs under memory_write_policy: CLEAN
echo   Legacy seed_42 (paper3_gemma4_e4b/) preserved
echo ============================================

echo.
echo [1/6] Full condition seed 42 (CLEAN) - ablation match to legacy
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --output paper3/results/paper3_gemma4_e4b_clean/seed_42
if errorlevel 1 ( echo FAILED seed_42 Full CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED seed_42 missing manifest & exit /b 1 )

echo.
echo [2/6] Full condition seed 123 (CLEAN)
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --output paper3/results/paper3_gemma4_e4b_clean/seed_123
if errorlevel 1 ( echo FAILED seed_123 Full CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED seed_123 missing manifest & exit /b 1 )

echo.
echo [3/6] Full condition seed 456 (CLEAN)
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --output paper3/results/paper3_gemma4_e4b_clean/seed_456
if errorlevel 1 ( echo FAILED seed_456 Full CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_e4b_clean\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED seed_456 missing manifest & exit /b 1 )

echo.
echo [4/6] Ablation B (Flat policy) seed 42 (CLEAN)
python run_unified_experiment.py %COMMON_ARGS% --seed 42 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_42
if errorlevel 1 ( echo FAILED ablation seed_42 CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_42 missing manifest & exit /b 1 )

echo.
echo [5/6] Ablation B (Flat policy) seed 123 (CLEAN)
python run_unified_experiment.py %COMMON_ARGS% --seed 123 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_123
if errorlevel 1 ( echo FAILED ablation seed_123 CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_123\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_123 missing manifest & exit /b 1 )

echo.
echo [6/6] Ablation B (Flat policy) seed 456 (CLEAN)
python run_unified_experiment.py %COMMON_ARGS% --seed 456 --fixed-institutional-policy paper3/configs/fixed_policies/flat_baseline_traditional.yaml --output paper3/results/paper3_gemma4_ablation_flat_clean/seed_456
if errorlevel 1 ( echo FAILED ablation seed_456 CLEAN & exit /b 1 )
if not exist "paper3\results\paper3_gemma4_ablation_flat_clean\seed_456\gemma4_e4b_strict\reproducibility_manifest.json" ( echo FAILED ablation seed_456 missing manifest & exit /b 1 )

echo ============================================
echo   ALL 6 CLEAN POLICY RUNS COMPLETE
echo ============================================
echo.
echo Ratchet ablation comparison is now possible:
echo   LEGACY: paper3/results/paper3_gemma4_e4b/seed_42/
echo   CLEAN:  paper3/results/paper3_gemma4_e4b_clean/seed_42/
echo Same seed, same config, only memory_write_policy differs.
pause
