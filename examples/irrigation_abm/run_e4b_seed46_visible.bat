@echo off
title e4b seed46 VISIBLE RUN
SET "REPO=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
SET "RESULTS=%REPO%\examples\irrigation_abm\results"
cd /d "%REPO%"

echo ============================================================
echo  e4b seed46 — visible run, no stdout redirect
echo  %DATE% %TIME%
echo ============================================================
echo  All python output flows to THIS window.
echo  DO NOT close this window or the experiment dies.
echo ============================================================
echo.

echo === Run 1: governed seed46 (ETA ~28 hr, may be slower under GPU contention) ===
python examples\irrigation_abm\run_experiment.py ^
  --model gemma4:e4b --years 42 --real --seed 46 ^
  --output "%RESULTS%\production_v21_42yr_gemma4_e4b_seed46" ^
  --num-ctx 8192 --num-predict 4096

echo.
echo === Run 1 finished, exit=%ERRORLEVEL% ===
echo.
echo === Run 2: ungoverned seed46 (ETA ~14 hr) ===
python examples\irrigation_abm\run_ungoverned_experiment.py ^
  --model gemma4:e4b --years 42 --real --seed 46 ^
  --output "%RESULTS%\ungoverned_v21_42yr_gemma4_e4b_seed46" ^
  --num-ctx 8192 --num-predict 4096

echo.
echo === Run 2 finished, exit=%ERRORLEVEL% ===
echo.
echo ============================================================
echo  ALL DONE  %DATE% %TIME%
echo ============================================================
pause
