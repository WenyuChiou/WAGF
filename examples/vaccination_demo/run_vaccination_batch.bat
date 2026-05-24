@echo off
REM vaccination_demo Tier-2 showcase batch runner (Phase L3-1E, 2026-05-24).
REM Windows companion to run_vaccination_batch.sh.
REM
REM Runs 3 seeds x 2 models = 6 runs producing per-run audit CSVs +
REM reproducibility_manifest.json under
REM examples\vaccination_demo\results\showcase_v1_seed<S>_<M>\.
REM
REM Run from the repo root:
REM   examples\vaccination_demo\run_vaccination_batch.bat
REM
REM Total wall time: ~30-40 min on RTX 4080 SUPER + ollama 0.23.3 (GPU).

setlocal enabledelayedexpansion

REM Resolve repo root (one level up from examples\vaccination_demo\)
set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%..\.."
pushd "%REPO_ROOT%"

set "SEEDS=42 43 44"
set "MODELS=gemma3:4b gemma4:e4b"
set "YEARS=5"
set "AGENTS=25"
set "OUTPUT_ROOT=examples\vaccination_demo\results"

echo === vaccination_demo Tier-2 batch ===
echo   seeds  : %SEEDS%
echo   models : %MODELS%
echo   years  : %YEARS%
echo   agents : %AGENTS%
echo   output : %OUTPUT_ROOT%\showcase_v1_seed^<S^>_^<M^>
echo.

for %%s in (%SEEDS%) do (
    for %%m in (%MODELS%) do (
        REM Build filesystem-friendly model slug (replace ':' with '_')
        set "model_slug=%%m"
        set "model_slug=!model_slug::=_!"
        set "run_dir=%OUTPUT_ROOT%\showcase_v1_seed%%s_!model_slug!"

        echo --- launching seed=%%s model=%%m -^> !run_dir! ---
        python examples\vaccination_demo\run_experiment.py ^
            --model "%%m" ^
            --years %YEARS% ^
            --agents %AGENTS% ^
            --seed %%s ^
            --output "!run_dir!"
        echo.
    )
)

echo === batch complete; results under %OUTPUT_ROOT%\showcase_v1_seed* ===
echo Run summary: python examples\vaccination_demo\summary.py

popd
endlocal
