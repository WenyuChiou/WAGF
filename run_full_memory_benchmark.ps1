# Memory System Benchmark (Full 4-Model Suite)
# Goal: Compare Window vs Importance Memory across Llama, Gemma, DeepSeek, GPT

$Models = @("llama3.2:3b", "gemma3:4b", "deepseek-r1:8b", "gpt-oss")
$Engines = @("window", "importance")
$Agents = 100
$Years = 10

Write-Host "🚀 Starting Full Memory Benchmark (4 Models x 2 Engines)" -ForegroundColor Cyan
Write-Host "=======================================================" -ForegroundColor Cyan

foreach ($Model in $Models) {
    Write-Host "`n📌 Model: $Model" -ForegroundColor Yellow
    foreach ($Engine in $Engines) {
        Write-Host "   ► Engine: $Engine" -ForegroundColor Green
        
        # Sanitize model name for directory check (approximate)
        $SafeModel = $Model -replace ":","_" -replace "\.","_"
        $OutputDir = "examples/single_agent/results_$Engine/${SafeModel}_strict"
        
        if (Test-Path "$OutputDir/simulation_log.csv") {
            Write-Host "     [Skipping] Results already exist in $OutputDir" -ForegroundColor DarkGray
        } else {
            Write-Host "     [Running] Executing simulation..." -ForegroundColor White
            python examples/single_agent/run_flood.py `
                --model $Model `
                --years $Years `
                --agents $Agents `
                --memory-engine $Engine `
                --output "examples/single_agent/results_$Engine"
        }
    }
}

Write-Host "`n✅ Benchmark Suite Complete!" -ForegroundColor Green
