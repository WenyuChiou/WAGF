@echo off
setlocal

REM Master bat - chain Gemma-4 V2 rerun in order: e2b -> e4b -> 26b
REM (small-to-large so quick models validate pipeline before committing
REM the 35-hour 26b run). No --use-priority-schema on any.
REM
REM Total expected: ~48 hours wall-clock (e2b 5hr + e4b 8hr + 26b 35hr).
REM Progress log: each sub-bat's stdout will be captured.

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
cd /d %BASE%

echo ============================================
echo   Gemma-4 V2 RERUN MASTER (e2b -^> e4b -^> 26b)
echo   Start: %DATE% %TIME%
echo ============================================

echo.
echo ========== PHASE 1/3: gemma4:e2b (~5 hr) ==========
call examples\single_agent\run_rerun_gemma4_e2b_v2.bat
if errorlevel 1 (
    echo PHASE 1 FAILED - aborting master
    exit /b 1
)

echo.
echo ========== PHASE 2/3: gemma4:e4b (~8 hr) ==========
call examples\single_agent\run_rerun_gemma4_e4b_v2.bat
if errorlevel 1 (
    echo PHASE 2 FAILED - aborting master
    exit /b 1
)

echo.
echo ========== PHASE 3/3: gemma4:26b (~35 hr) ==========
call examples\single_agent\run_rerun_gemma4_26b_v2.bat
if errorlevel 1 (
    echo PHASE 3 FAILED - aborting master
    exit /b 1
)

echo.
echo ============================================
echo   Gemma-4 V2 RERUN MASTER COMPLETE
echo   End: %DATE% %TIME%
echo ============================================
endlocal
