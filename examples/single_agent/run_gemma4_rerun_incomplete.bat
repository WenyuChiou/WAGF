@echo off
setlocal

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv

cd /d %BASE%

echo ============================================
echo   Gemma 4 Rerun: incomplete runs only
echo ============================================

echo.
echo [1/6] gemma4:e2b no-validator seed 44 (Run_3)
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [2/6] gemma4:e2b no-validator seed 45 (Run_4)
python examples\single_agent\run_flood.py --model gemma4:e2b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e2b\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [3/6] gemma4:e4b no-validator seed 43 (Run_2)
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536

echo.
echo [4/6] gemma4:e4b no-validator seed 44 (Run_3)
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536

echo.
echo [5/6] gemma4:e4b no-validator seed 45 (Run_4)
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536

echo.
echo [6/6] gemma4:e4b no-validator seed 46 (Run_5)
python examples\single_agent\run_flood.py --model gemma4:e4b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_e4b\Group_C_disabled\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536

echo ============================================
echo   ALL 6 RUNS DONE
echo ============================================
pause
