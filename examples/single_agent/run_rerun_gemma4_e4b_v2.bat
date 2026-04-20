@echo off
setlocal

REM Gemma-4 e2b V2 rerun - 2 conditions x 5 seeds = 10 runs.
REM Fixes 2026-04-19 priority-schema confound: V1 Gemma-4 data had
REM [CRITICAL FACTORS] prompt block via --use-priority-schema;
REM other 6 models (Gemma-3 x 3 + Ministral x 3) did not. This
REM rerun drops the flag so all 9 models share one prompt regime.
REM
REM Expected wall time: ~8 hours (45 min/run x 10 runs).
REM Output: JOH_FINAL_v2/ and JOH_ABLATION_DISABLED_v2/
REM (V1 preserved at JOH_FINAL/ and JOH_ABLATION_DISABLED/).

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv
set MODEL=gemma4:e4b
set TAG=gemma4_e4b

cd /d %BASE%

echo ============================================
echo   V2 RERUN: %MODEL% x 5 seeds x 2 conditions
echo   No --use-priority-schema (V1-matching prompt regime)
echo ============================================

echo.
echo [1/10] governed seed 42 Run_1
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2\%TAG%\Group_C\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [2/10] governed seed 43 Run_2
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2\%TAG%\Group_C\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [3/10] governed seed 44 Run_3
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2\%TAG%\Group_C\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [4/10] governed seed 45 Run_4
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2\%TAG%\Group_C\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [5/10] governed seed 46 Run_5
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL_v2\%TAG%\Group_C\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [6/10] disabled seed 42 Run_1
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2\%TAG%\Group_C_disabled\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [7/10] disabled seed 43 Run_2
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2\%TAG%\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [8/10] disabled seed 44 Run_3
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2\%TAG%\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [9/10] disabled seed 45 Run_4
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2\%TAG%\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo [10/10] disabled seed 46 Run_5
python examples\single_agent\run_flood.py --model %MODEL% --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED_v2\%TAG%\Group_C_disabled\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED & exit /b 1 )

echo.
echo ============================================
echo   %MODEL% V2 rerun complete
echo ============================================
endlocal
