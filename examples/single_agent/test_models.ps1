$ErrorActionPreference = "Continue"

$Models = @(
    "qwen3:1.7b",
    "qwen3:4b",
    "qwen3:8b",
    "qwen3:14b", 
    "qwen3:30b"
)

foreach ($model in $Models) {
    Write-Host "`n>>> TESTING MODEL: $model <<<" -ForegroundColor Cyan
    $modelSafe = $model -replace ":","_" -replace "-","_"
    try {
        python run_flood.py --model $model --years 1 --agents 1 --workers 1 --memory-engine humancentric --output "results/TEST_MODELS/$modelSafe" --seed 42
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ $model PASSED" -ForegroundColor Green
        } else {
            Write-Host "❌ $model FAILED (Exit Code: $LASTEXITCODE)" -ForegroundColor Red
        }
    } catch {
        Write-Host "❌ $model CRASHED: $_" -ForegroundColor Red
    }
}
Write-Host "`nModel Verification Complete"
