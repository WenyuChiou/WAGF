param (
    [int]$Agents = 100,
    [int]$Years = 10
)

# Configuration
$Models = @("gemma3:4b", "llama3.2:3b")
$CommonArgs = "--agents $Agents --years $Years --survey-mode --workers 5"
$BaseSeed = 42
$ResultsRoot = "results/JOH_FINAL"

# Model Folder Mapping
$ModelFolders = @{
    "gemma3:4b"   = "gemma3_4b"
    "llama3.2:3b" = "llama3_2_3b"
}

Write-Host "--- JOH Full Gap-Filling Protocol ---" -ForegroundColor Cyan

foreach ($Model in $Models) {
    $ModelSafeName = $ModelFolders[$Model]
    
    Write-Host "Checking Model: $Model ($ModelSafeName)" -ForegroundColor Magenta
    
    for ($i = 1; $i -le 10; $i++) {
        $CurrentSeed = $BaseSeed + $i
        
        # --- Group A: Baseline (Disabled Gov, Window Mem) ---
        $PathA = "$ResultsRoot/$ModelSafeName/Group_A/Run_$i"
        if (-not (Test-Path $PathA)) {
            Write-Host "  > [Gap Found] Running Group A - Run $i..." -ForegroundColor Yellow
            New-Item -ItemType Directory -Force -Path $PathA | Out-Null
            Invoke-Expression "python -u run_flood.py --model $Model $CommonArgs --governance-mode disabled --memory-engine window --output $PathA --seed $CurrentSeed"
        }
        else {
            Write-Host "  > [Exists] Group A - Run $i (Skipping)" -ForegroundColor DarkGray
        }

        # --- Group B: Governance Only (Strict Gov, Window Mem) ---
        $PathB = "$ResultsRoot/$ModelSafeName/Group_B/Run_$i"
        if (-not (Test-Path $PathB)) {
            Write-Host "  > [Gap Found] Running Group B - Run $i..." -ForegroundColor Yellow
            New-Item -ItemType Directory -Force -Path $PathB | Out-Null
            Invoke-Expression "python -u run_flood.py --model $Model $CommonArgs --governance-mode strict --memory-engine window --output $PathB --seed $CurrentSeed"
        }
        else {
            Write-Host "  > [Exists] Group B - Run $i (Skipping)" -ForegroundColor DarkGray
        }

        # --- Group C: Full JOH (Strict Gov, Human-Centric Mem, Priority) ---
        if ($Model -eq "gemma3:4b") {
            Write-Host "  > [Skipping] Group C for Gemma (Handled by separate Extension Script)" -ForegroundColor DarkGray
        }
        else {
            $PathC = "$ResultsRoot/$ModelSafeName/Group_C/Run_$i"
            # Check carefully: Run_Extension struct uses "Run_$i".
            # If run_extension is currently creating it, we might race?
            # But Test-Path checks *folder existence*. If folder exists (created by other script), we skip.
            if (-not (Test-Path $PathC)) {
                Write-Host "  > [Gap Found] Running Group C - Run $i..." -ForegroundColor Yellow
                New-Item -ItemType Directory -Force -Path $PathC | Out-Null
                Invoke-Expression "python -u run_flood.py --model $Model $CommonArgs --governance-mode strict --memory-engine humancentric --use-priority-schema --output $PathC --seed $CurrentSeed"
            }
            else {
                Write-Host "  > [Exists] Group C - Run $i (Skipping)" -ForegroundColor DarkGray
            }
        }
    }
}

Write-Host "--- All Gaps Filled! ---" -ForegroundColor Green
