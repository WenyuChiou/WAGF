@echo off
REM =============================================================================
REM Irrigation ABM Ensemble Runner for Nature Water Article
REM =============================================================================
REM This script runs the complete experiment ensemble:
REM - 3 ungoverned runs (seeds 42, 43, 44)
REM - 2 governed runs (seeds 43, 44; seed 42 already exists)
REM - Analysis for all completed runs
REM
REM Estimated total time: ~31 hours
REM =============================================================================

setlocal enabledelayedexpansion

REM Set working directory to script location
cd /d %~dp0

REM Initialize log file
set LOGFILE=ensemble_log.txt
echo ============================================================================= > %LOGFILE%
echo Irrigation ABM Ensemble Run Started >> %LOGFILE%
echo Start Time: %DATE% %TIME% >> %LOGFILE%
echo ============================================================================= >> %LOGFILE%
echo.

echo ============================================================================
echo PRE-FLIGHT CHECKS
echo ============================================================================

REM Check 1: Verify Ollama is running
echo [CHECK 1/4] Verifying Ollama is running...
echo [CHECK 1/4] Verifying Ollama is running... >> %LOGFILE%
ollama list >nul 2>&1
if errorlevel 1 (
    echo ERROR: Ollama is not running. Please start Ollama first.
    echo ERROR: Ollama is not running. >> %LOGFILE%
    pause
    exit /b 1
)
echo   ✓ Ollama is running >> %LOGFILE%
echo   ✓ Ollama is running
echo.

REM Check 2: Verify gemma3:4b model is available
echo [CHECK 2/4] Verifying gemma3:4b model is available...
echo [CHECK 2/4] Verifying gemma3:4b model is available... >> %LOGFILE%
ollama list | find "gemma3:4b" >nul 2>&1
if errorlevel 1 (
    echo ERROR: gemma3:4b model not found. Please pull it first: ollama pull gemma3:4b
    echo ERROR: gemma3:4b model not found. >> %LOGFILE%
    pause
    exit /b 1
)
echo   ✓ gemma3:4b model found >> %LOGFILE%
echo   ✓ gemma3:4b model found
echo.

REM Check 3: Verify Python is available
echo [CHECK 3/4] Verifying Python installation...
echo [CHECK 3/4] Verifying Python installation... >> %LOGFILE%
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python not found. Please install Python or add to PATH.
    echo ERROR: Python not found. >> %LOGFILE%
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('python --version 2^>^&1') do set PYVER=%%i
echo   ✓ %PYVER% >> %LOGFILE%
echo   ✓ %PYVER%
echo.

REM Check 4: Check GPU availability (informational only)
echo [CHECK 4/4] Checking GPU availability (informational)...
echo [CHECK 4/4] Checking GPU availability... >> %LOGFILE%
nvidia-smi >nul 2>&1
if errorlevel 1 (
    echo   ! GPU not detected or nvidia-smi not available
    echo   ! GPU not detected or nvidia-smi not available >> %LOGFILE%
) else (
    echo   ✓ NVIDIA GPU detected >> %LOGFILE%
    echo   ✓ NVIDIA GPU detected
    nvidia-smi --query-gpu=name,memory.total --format=csv,noheader >> %LOGFILE% 2>&1
)
echo.

echo ============================================================================
echo DISABLING WINDOWS SLEEP DURING RUN
echo ============================================================================
echo Disabling sleep and hibernation...
echo Disabling sleep and hibernation... >> %LOGFILE%
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
echo   ✓ Power settings updated (AC: no sleep/hibernate)
echo   ✓ Power settings updated >> %LOGFILE%
echo.

echo ============================================================================
echo STARTING ENSEMBLE RUNS (Estimated: ~31 hours total)
echo ============================================================================
echo.

REM =============================================================================
REM PHASE 1: UNGOVERNED EXPERIMENTS (faster, parallel workers)
REM =============================================================================

echo ============================================================================
echo PHASE 1: UNGOVERNED EXPERIMENTS (3 runs, ~4 workers each)
echo ============================================================================
echo.

REM --- Ungoverned Run 1: Seed 42 ---
set RUN_NAME=Ungoverned Seed 42
set RUN_START=%DATE% %TIME%
echo [RUN 1/5] %RUN_NAME%
echo [RUN 1/5] %RUN_NAME% >> %LOGFILE%
echo   Start: %RUN_START% >> %LOGFILE%
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 42 --workers 4 --num-ctx 8192 --num-predict 4096
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 42 --workers 4 --num-ctx 8192 --num-predict 4096 >> %LOGFILE%
echo.

CALL python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 42 --workers 4 --num-ctx 8192 --num-predict 4096
set RUN_EXIT=%errorlevel%
set RUN_END=%DATE% %TIME%

echo   End: %RUN_END% >> %LOGFILE%
if %RUN_EXIT% neq 0 (
    echo   ERROR: Run failed with exit code %RUN_EXIT% >> %LOGFILE%
    echo   ERROR: %RUN_NAME% failed with exit code %RUN_EXIT%
) else (
    echo   ✓ SUCCESS >> %LOGFILE%
    echo   ✓ SUCCESS
)
echo. >> %LOGFILE%
echo.

REM --- Ungoverned Run 2: Seed 43 ---
set RUN_NAME=Ungoverned Seed 43
set RUN_START=%DATE% %TIME%
echo [RUN 2/5] %RUN_NAME%
echo [RUN 2/5] %RUN_NAME% >> %LOGFILE%
echo   Start: %RUN_START% >> %LOGFILE%
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 43 --workers 4 --num-ctx 8192 --num-predict 4096
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 43 --workers 4 --num-ctx 8192 --num-predict 4096 >> %LOGFILE%
echo.

CALL python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 43 --workers 4 --num-ctx 8192 --num-predict 4096
set RUN_EXIT=%errorlevel%
set RUN_END=%DATE% %TIME%

echo   End: %RUN_END% >> %LOGFILE%
if %RUN_EXIT% neq 0 (
    echo   ERROR: Run failed with exit code %RUN_EXIT% >> %LOGFILE%
    echo   ERROR: %RUN_NAME% failed with exit code %RUN_EXIT%
) else (
    echo   ✓ SUCCESS >> %LOGFILE%
    echo   ✓ SUCCESS
)
echo. >> %LOGFILE%
echo.

REM --- Ungoverned Run 3: Seed 44 ---
set RUN_NAME=Ungoverned Seed 44
set RUN_START=%DATE% %TIME%
echo [RUN 3/5] %RUN_NAME%
echo [RUN 3/5] %RUN_NAME% >> %LOGFILE%
echo   Start: %RUN_START% >> %LOGFILE%
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 44 --workers 4 --num-ctx 8192 --num-predict 4096
echo   Command: python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 44 --workers 4 --num-ctx 8192 --num-predict 4096 >> %LOGFILE%
echo.

CALL python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed 44 --workers 4 --num-ctx 8192 --num-predict 4096
set RUN_EXIT=%errorlevel%
set RUN_END=%DATE% %TIME%

echo   End: %RUN_END% >> %LOGFILE%
if %RUN_EXIT% neq 0 (
    echo   ERROR: Run failed with exit code %RUN_EXIT% >> %LOGFILE%
    echo   ERROR: %RUN_NAME% failed with exit code %RUN_EXIT%
) else (
    echo   ✓ SUCCESS >> %LOGFILE%
    echo   ✓ SUCCESS
)
echo. >> %LOGFILE%
echo.

REM =============================================================================
REM PHASE 2: GOVERNED EXPERIMENTS (slower, single worker)
REM =============================================================================

echo ============================================================================
echo PHASE 2: GOVERNED EXPERIMENTS (2 runs, single worker each)
echo Note: Seed 42 already exists in production_v20_42yr_seed42
echo ============================================================================
echo.

REM --- Governed Run 1: Seed 43 ---
set RUN_NAME=Governed Seed 43
set RUN_START=%DATE% %TIME%
echo [RUN 4/5] %RUN_NAME%
echo [RUN 4/5] %RUN_NAME% >> %LOGFILE%
echo   Start: %RUN_START% >> %LOGFILE%
echo   Command: python run_experiment.py --model gemma3:4b --years 42 --real --seed 43 --num-ctx 8192 --num-predict 4096 --workers 1
echo   Command: python run_experiment.py --model gemma3:4b --years 42 --real --seed 43 --num-ctx 8192 --num-predict 4096 --workers 1 >> %LOGFILE%
echo.

CALL python run_experiment.py --model gemma3:4b --years 42 --real --seed 43 --num-ctx 8192 --num-predict 4096 --workers 1
set RUN_EXIT=%errorlevel%
set RUN_END=%DATE% %TIME%

echo   End: %RUN_END% >> %LOGFILE%
if %RUN_EXIT% neq 0 (
    echo   ERROR: Run failed with exit code %RUN_EXIT% >> %LOGFILE%
    echo   ERROR: %RUN_NAME% failed with exit code %RUN_EXIT%
) else (
    echo   ✓ SUCCESS >> %LOGFILE%
    echo   ✓ SUCCESS
)
echo. >> %LOGFILE%
echo.

REM --- Governed Run 2: Seed 44 ---
set RUN_NAME=Governed Seed 44
set RUN_START=%DATE% %TIME%
echo [RUN 5/5] %RUN_NAME%
echo [RUN 5/5] %RUN_NAME% >> %LOGFILE%
echo   Start: %RUN_START% >> %LOGFILE%
echo   Command: python run_experiment.py --model gemma3:4b --years 42 --real --seed 44 --num-ctx 8192 --num-predict 4096 --workers 1
echo   Command: python run_experiment.py --model gemma3:4b --years 42 --real --seed 44 --num-ctx 8192 --num-predict 4096 --workers 1 >> %LOGFILE%
echo.

CALL python run_experiment.py --model gemma3:4b --years 42 --real --seed 44 --num-ctx 8192 --num-predict 4096 --workers 1
set RUN_EXIT=%errorlevel%
set RUN_END=%DATE% %TIME%

echo   End: %RUN_END% >> %LOGFILE%
if %RUN_EXIT% neq 0 (
    echo   ERROR: Run failed with exit code %RUN_EXIT% >> %LOGFILE%
    echo   ERROR: %RUN_NAME% failed with exit code %RUN_EXIT%
) else (
    echo   ✓ SUCCESS >> %LOGFILE%
    echo   ✓ SUCCESS
)
echo. >> %LOGFILE%
echo.

REM =============================================================================
REM PHASE 3: ANALYSIS
REM =============================================================================

echo ============================================================================
echo PHASE 3: ANALYSIS (Computing IBR/EHE metrics)
echo ============================================================================
echo.
echo Computing metrics for all completed runs...
echo Computing metrics for all completed runs... >> %LOGFILE%
echo.

REM --- Analysis for Seed 42 (governed) ---
if exist "results\production_v20_42yr_seed42" (
    echo [ANALYSIS 1/5] Governed Seed 42 (existing run)
    echo [ANALYSIS 1/5] Governed Seed 42 >> %LOGFILE%
    CALL python analysis\compute_ibr.py --results-dir results\production_v20_42yr_seed42 --output analysis\ibr_governed_seed42.json
    if errorlevel 1 (
        echo   ERROR: Analysis failed >> %LOGFILE%
        echo   ERROR: Analysis failed
    ) else (
        echo   ✓ SUCCESS: analysis\ibr_governed_seed42.json >> %LOGFILE%
        echo   ✓ SUCCESS: analysis\ibr_governed_seed42.json
    )
    echo.
)

REM --- Analysis for Seed 43 (governed) ---
if exist "results\production_v20_42yr_seed43" (
    echo [ANALYSIS 2/5] Governed Seed 43
    echo [ANALYSIS 2/5] Governed Seed 43 >> %LOGFILE%
    CALL python analysis\compute_ibr.py --results-dir results\production_v20_42yr_seed43 --output analysis\ibr_governed_seed43.json
    if errorlevel 1 (
        echo   ERROR: Analysis failed >> %LOGFILE%
        echo   ERROR: Analysis failed
    ) else (
        echo   ✓ SUCCESS: analysis\ibr_governed_seed43.json >> %LOGFILE%
        echo   ✓ SUCCESS: analysis\ibr_governed_seed43.json
    )
    echo.
)

REM --- Analysis for Seed 44 (governed) ---
if exist "results\production_v20_42yr_seed44" (
    echo [ANALYSIS 3/5] Governed Seed 44
    echo [ANALYSIS 3/5] Governed Seed 44 >> %LOGFILE%
    CALL python analysis\compute_ibr.py --results-dir results\production_v20_42yr_seed44 --output analysis\ibr_governed_seed44.json
    if errorlevel 1 (
        echo   ERROR: Analysis failed >> %LOGFILE%
        echo   ERROR: Analysis failed
    ) else (
        echo   ✓ SUCCESS: analysis\ibr_governed_seed44.json >> %LOGFILE%
        echo   ✓ SUCCESS: analysis\ibr_governed_seed44.json
    )
    echo.
)

REM --- Analysis for ungoverned runs (check for typical naming patterns) ---
for %%s in (42 43 44) do (
    REM Check common ungoverned directory naming patterns
    if exist "results\ungoverned_42yr_seed%%s" (
        echo [ANALYSIS] Ungoverned Seed %%s
        echo [ANALYSIS] Ungoverned Seed %%s >> %LOGFILE%
        CALL python analysis\compute_ibr.py --results-dir results\ungoverned_42yr_seed%%s --output analysis\ibr_ungoverned_seed%%s.json
        if errorlevel 1 (
            echo   ERROR: Analysis failed >> %LOGFILE%
            echo   ERROR: Analysis failed
        ) else (
            echo   ✓ SUCCESS: analysis\ibr_ungoverned_seed%%s.json >> %LOGFILE%
            echo   ✓ SUCCESS: analysis\ibr_ungoverned_seed%%s.json
        )
        echo.
    )
)

REM =============================================================================
REM RESTORE POWER SETTINGS
REM =============================================================================

echo ============================================================================
echo RESTORING POWER SETTINGS
echo ============================================================================
echo Restoring default sleep/hibernation settings...
echo Restoring default sleep/hibernation settings... >> %LOGFILE%
powercfg /change standby-timeout-ac 30
powercfg /change hibernate-timeout-ac 60
echo   ✓ Power settings restored (AC: 30min sleep, 60min hibernate)
echo   ✓ Power settings restored >> %LOGFILE%
echo.

REM =============================================================================
REM FINAL SUMMARY
REM =============================================================================

echo ============================================================================
echo ENSEMBLE RUN COMPLETE
echo ============================================================================
set FINAL_TIME=%DATE% %TIME%
echo End Time: %FINAL_TIME%
echo End Time: %FINAL_TIME% >> %LOGFILE%
echo.
echo Check ensemble_log.txt for detailed timestamps and error logs.
echo Results are in the results\ directory.
echo Analysis outputs are in the analysis\ directory.
echo.
echo ============================================================================= >> %LOGFILE%
echo.

pause
endlocal
