# JOH Experiment 2: Stress Test (Qualitative Case Study)
# Focus: Explainability & Trace Generation (The "Impulsive Relocator" Scenario)
# Output Directory: results/JOH_Stress

$Model = "llama3.2:3b"
$Agents = 20  # Smaller batch to focus on trace quality
$Years = 5    # Shorter duration

Write-Host "--- Starting JOH Stress Test (Micro Case Study) ---" -ForegroundColor Cyan

# Group C Configuration with VERBOSE logging enabled
# We need verbose logs to see the "Reject -> Hint -> Correct" dialogue
Write-Host "Running Stress Test: Collecting Explainability Traces..."
python run_flood.py --model $Model --years $Years --agents $Agents --memory-engine humancentric --governance-mode strict --use-priority-schema --output results/JOH_Stress --survey-mode --verbose

Write-Host "Stress Test Complete. Check logs in results/JOH_Stress for 'Intervention' traces." -ForegroundColor Green
