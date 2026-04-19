@echo off
setlocal

REM V2 memory pipeline pilot — Gemma-4 26B × 2 conditions × 2 seeds.
REM Post-fix pipeline. Branch head b1d3deb.
REM
REM Expected wall time: ~14 hrs (3-4 hr/run × 4 runs).
REM Recommend running overnight AFTER gemma3_4b pilot completes.

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv

cd /d %BASE%

echo ============================================
echo   V2 pilot: gemma4:26b Group_C + Group_C_disabled x 2 seeds
echo ============================================

echo.
echo [1/4] Group_C seed 42 (Run_1)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2_pilot\gemma4_26b\Group_C\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED Group_C seed 42 & exit /b 1 )

echo.
echo [2/4] Group_C seed 43 (Run_2)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2_pilot\gemma4_26b\Group_C\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED Group_C seed 43 & exit /b 1 )

echo.
echo [3/4] Group_C_disabled seed 42 (Run_1)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2_pilot\gemma4_26b\Group_C_disabled\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED Group_C_disabled seed 42 & exit /b 1 )

echo.
echo [4/4] Group_C_disabled seed 43 (Run_2)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2_pilot\gemma4_26b\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED Group_C_disabled seed 43 & exit /b 1 )

echo.
echo ============================================
echo   gemma4:26b pilot complete
echo ============================================
endlocal
