@echo off
setlocal

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv

cd /d %BASE%

echo ============================================
echo   Gemma 4 Remaining Seeds: e2b + e4b
echo   Seeds 43, 44, 45, 46 (seed 42 already done)
echo   4 seeds x 2 models x 2 conditions = 16 runs
echo ============================================

REM ── gemma4:e2b governed seeds 43-46 ─────────────
echo.
echo [1/16] gemma4:e2b governed seed 43
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e2b\Group_C\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536

echo.
echo [2/16] gemma4:e2b governed seed 44
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e2b\Group_C\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [3/16] gemma4:e2b governed seed 45
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e2b\Group_C\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [4/16] gemma4:e2b governed seed 46
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e2b\Group_C\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536

REM ── gemma4:e2b no-validator seeds 43-46 ─────────
echo.
echo [5/16] gemma4:e2b no-validator seed 43
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536

echo.
echo [6/16] gemma4:e2b no-validator seed 44
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [7/16] gemma4:e2b no-validator seed 45
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [8/16] gemma4:e2b no-validator seed 46
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536

REM ── gemma4:e4b governed seeds 43-46 ─────────────
echo.
echo [9/16] gemma4:e4b governed seed 43
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e4b\Group_C\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536

echo.
echo [10/16] gemma4:e4b governed seed 44
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e4b\Group_C\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [11/16] gemma4:e4b governed seed 45
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e4b\Group_C\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [12/16] gemma4:e4b governed seed 46
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e4b\Group_C\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536

REM ── gemma4:e4b no-validator seeds 43-46 ─────────
echo.
echo [13/16] gemma4:e4b no-validator seed 43
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536

echo.
echo [14/16] gemma4:e4b no-validator seed 44
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [15/16] gemma4:e4b no-validator seed 45
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [16/16] gemma4:e4b no-validator seed 46
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536

echo ============================================
echo   ALL 16 RUNS DONE
echo ============================================
pause
