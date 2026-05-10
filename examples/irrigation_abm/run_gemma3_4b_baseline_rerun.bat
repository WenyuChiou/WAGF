@echo off
REM ============================================================================
REM Gemma-3 4B Irrigation Baseline RE-RUN (post-v21-fix)
REM
REM Purpose: re-run irrigation baseline seeds 42, 43, 44 (governed + ungoverned)
REM under the v21 fix (commit 4be5092, 2026-03-03 19:38) that changes
REM `current = agent["request"]` symmetric base.  The original seeds 42-44
REM were produced PRE-fix; pre-fix dirs are archived at
REM examples/irrigation_abm/results/_archive_pre_v21fix_2026-04-24/.
REM
REM Output convention (canonical, post-fix):
REM   results/production_v21_42yr_seed{42,43,44}
REM   results/ungoverned_v21_42yr_seed{42,43,44}
REM
REM Wall-clock: ~9 hr governed + ~6 hr ungoverned per seed = ~45 hr serial.
REM stdout/stderr captured per-run (lesson learned 2026-04-24).
REM ============================================================================

cd /d "%~dp0"

echo [%date% %time%] Starting Gemma-3 4B baseline re-run (v21-post-fix)...

for %%S in (42 43 44) do (
    if exist "results\production_v21_42yr_seed%%S\simulation_log.csv" (
        echo [%date% %time%] SKIP: production_seed%%S already exists
    ) else (
        echo [%date% %time%] START: governed gemma3:4b seed=%%S
        python run_experiment.py --model gemma3:4b --years 42 --real --seed %%S --output results/production_v21_42yr_seed%%S --num-ctx 8192 --num-predict 4096 > "results\production_v21_42yr_seed%%S.stdout.log" 2>&1
        echo [%date% %time%] DONE: governed gemma3:4b seed=%%S exit=%errorlevel%
    )

    if exist "results\ungoverned_v21_42yr_seed%%S\simulation_log.csv" (
        echo [%date% %time%] SKIP: ungoverned_seed%%S already exists
    ) else (
        echo [%date% %time%] START: ungoverned gemma3:4b seed=%%S
        python run_ungoverned_experiment.py --model gemma3:4b --years 42 --real --seed %%S --output results/ungoverned_v21_42yr_seed%%S --num-ctx 8192 --num-predict 4096 > "results\ungoverned_v21_42yr_seed%%S.stdout.log" 2>&1
        echo [%date% %time%] DONE: ungoverned gemma3:4b seed=%%S exit=%errorlevel%
    )
)

echo [%date% %time%] === GEMMA-3 4B BASELINE RE-RUN COMPLETE (seeds 42-44 post-fix) ===
