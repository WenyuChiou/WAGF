@echo off
REM ============================================================================
REM Gemma-4 e4b Irrigation Cross-Model Batch Runner (Windows CMD)
REM 10 experiments: 5 seeds x (governed + ungoverned), seeds 42..46
REM Output convention: results/{production,ungoverned}_v21_42yr_gemma4_e4b_seedN
REM Expected per seed: ~8 h governed + ~6 h ungoverned (efficient 4B variant)
REM ============================================================================

cd /d "%~dp0"

echo [%date% %time%] Starting Gemma-4 e4b irrigation batch...

for %%S in (42 43 44 45 46) do (
    if exist "results\production_v21_42yr_gemma4_e4b_seed%%S\simulation_log.csv" (
        echo [%date% %time%] SKIP: production_gemma4_e4b_seed%%S already exists
    ) else (
        echo [%date% %time%] START: governed gemma4:e4b seed=%%S
        python run_experiment.py --model gemma4:e4b --years 42 --real --seed %%S --output results/production_v21_42yr_gemma4_e4b_seed%%S --num-ctx 8192 --num-predict 4096
        echo [%date% %time%] DONE: governed gemma4:e4b seed=%%S
    )

    if exist "results\ungoverned_v21_42yr_gemma4_e4b_seed%%S\simulation_log.csv" (
        echo [%date% %time%] SKIP: ungoverned_gemma4_e4b_seed%%S already exists
    ) else (
        echo [%date% %time%] START: ungoverned gemma4:e4b seed=%%S
        python run_ungoverned_experiment.py --model gemma4:e4b --years 42 --real --seed %%S --output results/ungoverned_v21_42yr_gemma4_e4b_seed%%S --num-ctx 8192 --num-predict 4096
        echo [%date% %time%] DONE: ungoverned gemma4:e4b seed=%%S
    )
)

echo [%date% %time%] === ALL GEMMA-4 e4b IRRIGATION RUNS COMPLETE ===
