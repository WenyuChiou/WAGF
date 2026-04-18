@echo off
setlocal

REM NW paper flood SA — fill gemma4:26b Group_C (WITH-validator) gap (5 seeds).
REM Mirror of run_gemma4_26b_disabled.bat but with --governance-mode strict
REM and output JOH_FINAL/... instead of JOH_ABLATION_DISABLED/...
REM
REM Seeds 42-46 mirror the DISABLED batch so the paired comparison is clean.
REM Expected wall time ~17 hr (3-4 hr/seed on 26B with GPU+CPU split).

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv

cd /d %BASE%

echo ============================================
echo   gemma4:26b Group_C (WITH-validator) x 5 seeds
echo   Expected wall time ~17 hr
echo ============================================

echo.
echo [1/5] seed 42 (Run_1)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 42 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_1\reproducibility_manifest.json" ( echo FAILED seed 42 missing manifest & exit /b 1 )

echo.
echo [2/5] seed 43 (Run_2)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 43 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_2\reproducibility_manifest.json" ( echo FAILED seed 43 missing manifest & exit /b 1 )

echo.
echo [3/5] seed 44 (Run_3)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 44 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_3\reproducibility_manifest.json" ( echo FAILED seed 44 missing manifest & exit /b 1 )

echo.
echo [4/5] seed 45 (Run_4)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 45 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_4\reproducibility_manifest.json" ( echo FAILED seed 45 missing manifest & exit /b 1 )

echo.
echo [5/5] seed 46 (Run_5)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 46 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_5\reproducibility_manifest.json" ( echo FAILED seed 46 missing manifest & exit /b 1 )

echo.
echo ============================================
echo   gemma4:26b Group_C (WITH-validator) complete (5 seeds)
echo ============================================

endlocal
