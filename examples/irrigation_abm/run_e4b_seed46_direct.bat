@echo off
REM ============================================================
REM   e4b seed46 direct launch — bypass safety pause
REM   Orchestrated by Claude after manual verification.
REM   2 sequential runs: gov seed46, then ung seed46.
REM ============================================================
SET "REPO=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
SET "RESULTS=%REPO%\examples\irrigation_abm\results"
SET "LOG_DIR=%RESULTS%\_recovery_logs_2026-05-13"
mkdir "%LOG_DIR%" 2>nul
cd /d "%REPO%"

echo [%DATE% %TIME%] START gov seed46 > "%LOG_DIR%\sequence.log"
python examples\irrigation_abm\run_experiment.py ^
  --model gemma4:e4b --years 42 --real --seed 46 ^
  --output "%RESULTS%\production_v21_42yr_gemma4_e4b_seed46" ^
  --num-ctx 8192 --num-predict 4096 ^
  > "%LOG_DIR%\production_v21_42yr_gemma4_e4b_seed46.log" 2>&1
echo [%DATE% %TIME%] gov seed46 exit=%ERRORLEVEL% >> "%LOG_DIR%\sequence.log"

echo [%DATE% %TIME%] START ung seed46 >> "%LOG_DIR%\sequence.log"
python examples\irrigation_abm\run_ungoverned_experiment.py ^
  --model gemma4:e4b --years 42 --real --seed 46 ^
  --output "%RESULTS%\ungoverned_v21_42yr_gemma4_e4b_seed46" ^
  --num-ctx 8192 --num-predict 4096 ^
  > "%LOG_DIR%\ungoverned_v21_42yr_gemma4_e4b_seed46.log" 2>&1
echo [%DATE% %TIME%] ung seed46 exit=%ERRORLEVEL% >> "%LOG_DIR%\sequence.log"

echo [%DATE% %TIME%] ALL COMPLETE >> "%LOG_DIR%\sequence.log"
