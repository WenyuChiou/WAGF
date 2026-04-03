@echo off
REM ============================================================================
REM Gemma-3 12B Irrigation Cross-Model Batch Runner (Windows CMD)
REM 6 experiments: 3 seeds x (governed + ungoverned)
REM Expected: ~15h governed + ~12h ungoverned per seed = ~81h total
REM ============================================================================

cd /d "%~dp0"

echo [%date% %time%] Starting Gemma-3 12B batch...

REM === Seed 42 ===
if exist "results\production_v21_42yr_gemma3_12b_seed42\simulation_log.csv" (
    echo [%date% %time%] SKIP: production_gemma3_12b_seed42 already exists
) else (
    echo [%date% %time%] START: governed gemma3:12b seed=42
    python run_experiment.py --model gemma3:12b --years 42 --real --seed 42 --output results/production_v21_42yr_gemma3_12b_seed42 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: governed gemma3:12b seed=42
)

if exist "results\ungoverned_v21_42yr_gemma3_12b_seed42\simulation_log.csv" (
    echo [%date% %time%] SKIP: ungoverned_gemma3_12b_seed42 already exists
) else (
    echo [%date% %time%] START: ungoverned gemma3:12b seed=42
    python run_ungoverned_experiment.py --model gemma3:12b --years 42 --real --seed 42 --output results/ungoverned_v21_42yr_gemma3_12b_seed42 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: ungoverned gemma3:12b seed=42
)

REM === Seed 43 ===
if exist "results\production_v21_42yr_gemma3_12b_seed43\simulation_log.csv" (
    echo [%date% %time%] SKIP: production_gemma3_12b_seed43 already exists
) else (
    echo [%date% %time%] START: governed gemma3:12b seed=43
    python run_experiment.py --model gemma3:12b --years 42 --real --seed 43 --output results/production_v21_42yr_gemma3_12b_seed43 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: governed gemma3:12b seed=43
)

if exist "results\ungoverned_v21_42yr_gemma3_12b_seed43\simulation_log.csv" (
    echo [%date% %time%] SKIP: ungoverned_gemma3_12b_seed43 already exists
) else (
    echo [%date% %time%] START: ungoverned gemma3:12b seed=43
    python run_ungoverned_experiment.py --model gemma3:12b --years 42 --real --seed 43 --output results/ungoverned_v21_42yr_gemma3_12b_seed43 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: ungoverned gemma3:12b seed=43
)

REM === Seed 44 ===
if exist "results\production_v21_42yr_gemma3_12b_seed44\simulation_log.csv" (
    echo [%date% %time%] SKIP: production_gemma3_12b_seed44 already exists
) else (
    echo [%date% %time%] START: governed gemma3:12b seed=44
    python run_experiment.py --model gemma3:12b --years 42 --real --seed 44 --output results/production_v21_42yr_gemma3_12b_seed44 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: governed gemma3:12b seed=44
)

if exist "results\ungoverned_v21_42yr_gemma3_12b_seed44\simulation_log.csv" (
    echo [%date% %time%] SKIP: ungoverned_gemma3_12b_seed44 already exists
) else (
    echo [%date% %time%] START: ungoverned gemma3:12b seed=44
    python run_ungoverned_experiment.py --model gemma3:12b --years 42 --real --seed 44 --output results/ungoverned_v21_42yr_gemma3_12b_seed44 --num-ctx 8192 --num-predict 4096
    echo [%date% %time%] DONE: ungoverned gemma3:12b seed=44
)

echo [%date% %time%] === ALL GEMMA-3 12B RUNS COMPLETE ===
pause
