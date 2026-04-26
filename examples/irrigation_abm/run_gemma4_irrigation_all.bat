@echo off
REM ============================================================================
REM Master Gemma-4 Irrigation Cross-Model Launcher
REM Chains e2b -> e4b (20 runs total, ~5 days wall-clock).
REM 26B irrigation is deferred; launch separately if/when wanted.
REM ============================================================================

cd /d "%~dp0"

echo [%date% %time%] ============================================
echo [%date% %time%]  Gemma-4 irrigation batch master launcher
echo [%date% %time%]  Model order: e2b then e4b (5 seeds each, 2 conditions)
echo [%date% %time%] ============================================

REM --- Pre-flight: confirm priority-schema flag not present anywhere ---
REM (Irrigation run scripts do not implement the flag; sanity echo only)
echo [%date% %time%] Pre-flight: irrigation scripts have no priority-schema flag (verified 2026-04-23).

echo [%date% %time%] ========== PHASE 1/2: gemma4:e2b (~25 hr) ==========
call "%~dp0run_gemma4_e2b_batch.bat"
if errorlevel 1 (
    echo [%date% %time%] ERROR: e2b batch failed; aborting master launcher.
    exit /b 1
)

echo [%date% %time%] ========== PHASE 2/2: gemma4:e4b (~70 hr) ==========
call "%~dp0run_gemma4_e4b_batch.bat"
if errorlevel 1 (
    echo [%date% %time%] ERROR: e4b batch failed.
    exit /b 1
)

echo [%date% %time%] === ALL PHASES COMPLETE: e2b + e4b irrigation done ===
echo [%date% %time%] Expected outputs:
echo     results\production_v21_42yr_gemma4_e2b_seed{42..46}
echo     results\ungoverned_v21_42yr_gemma4_e2b_seed{42..46}
echo     results\production_v21_42yr_gemma4_e4b_seed{42..46}
echo     results\ungoverned_v21_42yr_gemma4_e4b_seed{42..46}
