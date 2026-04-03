@echo off
setlocal

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv
set SEED=42

cd /d %BASE%

echo ============================================
echo   Gemma 4 Cross-Model: 3 sizes x 2 conditions
echo ============================================

echo.
echo [1/6] gemma4:e2b governed
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e2b\Group_C\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo.
echo [2/6] gemma4:e2b no-validator
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo.
echo [3/6] gemma4:e4b governed
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_e4b\Group_C\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo.
echo [4/6] gemma4:e4b no-validator
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo.
echo [5/6] gemma4:26b governed
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode strict --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_FINAL\gemma4_26b\Group_C\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo.
echo [6/6] gemma4:26b no-validator
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_1" --seed %SEED% --num-ctx 8192 --num-predict 1536

echo ============================================
echo   ALL 6 RUNS DONE
echo ============================================
pause
