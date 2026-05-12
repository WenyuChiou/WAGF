@echo off
REM ============================================================
REM   e4b irrigation recovery — task #62 finale (2026-05-12)
REM ============================================================
REM
REM Targets 3 runs that coordinator either skipped or that died
REM on reboot:
REM   1. ungoverned_v21_42yr_gemma4_e4b_seed45 (rerun if killed by reboot)
REM   2. production_v21_42yr_gemma4_e4b_seed46 (new — coordinator skipped)
REM   3. ungoverned_v21_42yr_gemma4_e4b_seed46 (new — coordinator skipped)
REM
REM Idempotent: skips any run whose target dir has
REM reproducibility_manifest.json (= clean completion marker).
REM Auto-archives partial dirs to *_killed_<date>_partial.
REM
REM Usage:
REM   Double-click in Windows Explorer, OR run from cmd:
REM     cd /d C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
REM     examples\irrigation_abm\run_e4b_recovery_2026-05-12.bat
REM
REM Estimated wall time (sequential): ~4-5 days
REM   - Run 1 (ungov seed45): ~1 day if reboot killed it
REM   - Run 2 (gov seed46):   ~3 days
REM   - Run 3 (ungov seed46): ~1 day
REM ============================================================

setlocal EnableDelayedExpansion

SET "REPO=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
SET "RESULTS=%REPO%\examples\irrigation_abm\results"
SET "MODEL=gemma4:e4b"
SET "YEARS=42"
SET "TODAY=2026-05-12"
SET "LOG_DIR=%RESULTS%\_recovery_logs_%TODAY%"

cd /d "%REPO%" || (echo [FATAL] Cannot cd to %REPO% & pause & exit /b 1)
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%"

echo.
echo ============================================================
echo  e4b recovery batch — %DATE% %TIME%
echo ============================================================
echo  Repo:    %REPO%
echo  Results: %RESULTS%
echo  Logs:    %LOG_DIR%
echo ============================================================
echo.

REM ============================================================
REM SAFETY: detect running e4b experiments (will conflict)
REM ============================================================
echo [SAFETY] Checking for active e4b python processes...
tasklist /FI "IMAGENAME eq python.exe" /FO CSV /NH 2>nul | findstr python >nul
if not errorlevel 1 (
  echo.
  echo [WARN] python.exe process detected. If an e4b run is in progress,
  echo        this recovery batch will ARCHIVE its working dir and break it.
  echo.
  echo Run BEFORE launching: tasklist ^| findstr python
  echo Confirm no e4b run is active. If safe, press any key to continue.
  echo To abort: press Ctrl+C now.
  pause
)

REM ============================================================
REM Pre-flight: Ollama health check
REM ============================================================
echo [PRE-FLIGHT] Checking Ollama...
ollama list >nul 2>&1
if errorlevel 1 (
  echo [FATAL] Ollama not responding. Start the Ollama service then retry.
  pause
  exit /b 1
)
ollama list | findstr /C:"gemma4:e4b" >nul
if errorlevel 1 (
  echo [WARN] gemma4:e4b not pulled. Pulling now...
  ollama pull gemma4:e4b
)
echo [PRE-FLIGHT] OK
echo.

REM ============================================================
REM RUN 1: ungoverned seed45
REM ============================================================
call :run_one ungoverned 45 run_ungoverned_experiment.py "--num-ctx 8192 --num-predict 4096"
if errorlevel 1 goto :failed

REM ============================================================
REM RUN 2: governed seed46
REM ============================================================
call :run_one production 46 run_experiment.py "--num-ctx 8192 --num-predict 4096"
if errorlevel 1 goto :failed

REM ============================================================
REM RUN 3: ungoverned seed46
REM ============================================================
call :run_one ungoverned 46 run_ungoverned_experiment.py "--num-ctx 8192 --num-predict 4096"
if errorlevel 1 goto :failed

REM ============================================================
REM Done
REM ============================================================
echo.
echo ============================================================
echo  ALL DONE  %DATE% %TIME%
echo ============================================================
echo  Logs:    %LOG_DIR%
echo  Verify:  type "%RESULTS%\ungoverned_v21_42yr_gemma4_e4b_seed45\governance_summary.json"
echo           type "%RESULTS%\production_v21_42yr_gemma4_e4b_seed46\governance_summary.json"
echo           type "%RESULTS%\ungoverned_v21_42yr_gemma4_e4b_seed46\governance_summary.json"
echo ============================================================
pause
exit /b 0

:failed
echo.
echo ============================================================
echo  FAILED  %DATE% %TIME%  — check log dir
echo ============================================================
pause
exit /b 1


REM ============================================================
REM Subroutine: run_one <condition> <seed> <script> <extra_args>
REM   condition: "production" or "ungoverned"
REM   seed:      42-46
REM   script:    "run_pipeline.py" or "run_ungoverned_experiment.py"
REM   extra_args: extra cli flags (or "" for none)
REM ============================================================
:run_one
SET "COND=%~1"
SET "SEED=%~2"
SET "SCRIPT=%~3"
SET "EXTRA=%~4"
SET "RUN_NAME=%COND%_v21_42yr_gemma4_e4b_seed%SEED%"
SET "RUN_DIR=%RESULTS%\%RUN_NAME%"

echo ------------------------------------------------------------
echo  Run target: %RUN_NAME%
echo ------------------------------------------------------------

REM Skip if already complete (manifest present)
if exist "%RUN_DIR%\reproducibility_manifest.json" (
  echo [SKIP] %RUN_NAME% already complete ^(manifest found^)
  echo.
  goto :eof
)

REM Archive partial dir if present
if exist "%RUN_DIR%" (
  echo [ARCHIVE] Found partial %RUN_NAME%, moving to _killed_%TODAY%_partial
  move "%RUN_DIR%" "%RESULTS%\%RUN_NAME%_killed_%TODAY%_partial" >nul 2>&1
  if errorlevel 1 (
    echo [ERROR] Could not archive partial dir. Manual cleanup needed.
    exit /b 1
  )
)

REM Launch
echo [START] %DATE% %TIME%  %RUN_NAME%
echo         log: %LOG_DIR%\%RUN_NAME%.log
echo.

python examples\irrigation_abm\%SCRIPT% ^
  --model %MODEL% --years %YEARS% --real --seed %SEED% ^
  --output "%RUN_DIR%" ^
  %EXTRA% > "%LOG_DIR%\%RUN_NAME%.log" 2>&1

if errorlevel 1 (
  echo [FAIL]  %DATE% %TIME%  %RUN_NAME% exit code %ERRORLEVEL%
  echo         Inspect: %LOG_DIR%\%RUN_NAME%.log
  exit /b 1
)

REM Verify completion
if not exist "%RUN_DIR%\reproducibility_manifest.json" (
  echo [WARN]  %DATE% %TIME%  %RUN_NAME% finished but no manifest written
  echo         Run may be incomplete — inspect %RUN_DIR%
  exit /b 1
)

echo [DONE]  %DATE% %TIME%  %RUN_NAME%
echo.
goto :eof
