@echo off
setlocal

set BASE=C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework
cd /d %BASE%\examples\multi_agent\flood

echo ============================================
echo   Paper 3: Gemma 4 e4b MA Flood (1 seed)
echo   400 agents x 13 years, Full condition
echo   Thinking mode: disabled
echo ============================================

echo.
echo [1/1] gemma4:e4b Full condition seed 42
python run_unified_experiment.py --model gemma4:e4b --seed 42 --years 13 --per-agent-depth --mode balanced --agent-profiles data/agent_profiles_balanced.csv --gossip --enable-news-media --enable-social-media --enable-communication --enable-custom-affordability --enable-financial-constraints --load-initial-memories --thinking-mode disabled --output paper3/results/paper3_gemma4_e4b/seed_42

if errorlevel 1 (
    echo ============================================
    echo   FAILED
    echo ============================================
    exit /b %errorlevel%
)

if not exist "paper3\results\paper3_gemma4_e4b\seed_42\gemma4_e4b_strict\reproducibility_manifest.json" (
    echo ============================================
    echo   FAILED: missing final manifest
    echo ============================================
    exit /b 1
)

echo ============================================
echo   DONE
echo ============================================
pause
