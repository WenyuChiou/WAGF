@echo off
setlocal

REM NW paper flood SA — fill gemma4:26b Group_C_disabled gap (5 seeds).
REM Same config as gemma4_e2b / gemma4_e4b Group_C_disabled runs from
REM run_gemma4_crossmodel.bat: 10 years, 100 agents, 1 worker, disabled
REM governance, humancentric memory, window size 5, priority schema,
REM thinking disabled, num_ctx 8192, num_predict 1536.
REM
REM Existing NW cross-model ablation has all 8 models except gemma4:26b.
REM This batch closes that gap so Paper 1b cross-model comparison can
REM report 9 models.

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
set PROFILES=examples\single_agent\agent_initial_profiles.csv

cd /d %BASE%

echo ============================================
echo   gemma4:26b Group_C_disabled x 5 seeds
echo   Expected wall time ~17 hr total (3-4 hr/seed)
echo ============================================

echo.
echo [1/5] seed 42 (Run_1)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_1" --seed 42 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 42 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_1\reproducibility_manifest.json" ( echo FAILED seed 42 missing manifest & exit /b 1 )

echo.
echo [2/5] seed 43 (Run_2)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_2" --seed 43 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 43 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_2\reproducibility_manifest.json" ( echo FAILED seed 43 missing manifest & exit /b 1 )

echo.
echo [3/5] seed 44 (Run_3)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_3" --seed 44 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 44 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_3\reproducibility_manifest.json" ( echo FAILED seed 44 missing manifest & exit /b 1 )

echo.
echo [4/5] seed 45 (Run_4)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_4" --seed 45 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 45 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_4\reproducibility_manifest.json" ( echo FAILED seed 45 missing manifest & exit /b 1 )

echo.
echo [5/5] seed 46 (Run_5)
python examples\single_agent\run_flood.py --model gemma4:26b --years 10 --agents 100 --workers 1 --governance-mode disabled --memory-engine humancentric --window-size 5 --use-priority-schema --thinking-mode disabled --initial-agents "%PROFILES%" --output "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_5" --seed 46 --num-ctx 8192 --num-predict 1536
if errorlevel 1 ( echo FAILED seed 46 & exit /b 1 )
if not exist "examples\single_agent\results\JOH_ABLATION_DISABLED\gemma4_26b\Group_C_disabled\Run_5\reproducibility_manifest.json" ( echo FAILED seed 46 missing manifest & exit /b 1 )

echo.
echo ============================================
echo   gemma4:26b Group_C_disabled complete (5 seeds)
echo ============================================

endlocal
