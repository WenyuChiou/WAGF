param (
    [int]$Agents = 100,
    [int]$Years = 10,
    [int]$Runs = 3
)

$SmallModels = @("llama3.2:3b", "gemma3:4b")
$LargeModels = @("gpt-oss-safeguard:20b", "deepseek-r1:8b")

Write-Host "--- JOH Benchmark Marathon: Parallel & Sequential Execution ---" -ForegroundColor Cyan
Write-Host "Configuration: $Agents Agents, $Years Years, $Runs Runs per Group"
Write-Host ""

$StartTime = Get-Date

# 1. Process Small Models in Parallel (Max 2)
Write-Host ">>> Starting Small Models Parallel Group: [ $($SmallModels -join ', ') ]" -ForegroundColor Magenta
$Jobs = @()
foreach ($Model in $SmallModels) {
    $Jobs += Start-Job -ScriptBlock {
        param($m, $a, $y, $r, $dir)
        Set-Location $dir
        .\run_joh_triple.ps1 -Model $m -Agents $a -Years $y -Runs $r
    } -ArgumentList $Model, $Agents, $Years, $Runs, $PWD
}

Write-Host "Waiting for small models to complete..." -ForegroundColor Gray
Receive-Job -Job $Jobs -Wait | Out-Default
Remove-Job $Jobs

# 2. Process Large Models Sequentially
foreach ($Model in $LargeModels) {
    Write-Host "`n>>> Processing Large Model Sequentially: [ $Model ]" -ForegroundColor Magenta
    .\run_joh_triple.ps1 -Model $Model -Agents $Agents -Years $Years -Runs $Runs
    
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Marathon failed at large model $Model"
        exit 1
    }
}

$EndTime = Get-Date
$Duration = $EndTime - $StartTime
Write-Host "`n--- JOH Benchmark Marathon Complete! ---" -ForegroundColor Green
Write-Host "Total Duration: $($Duration.TotalMinutes) minutes"
