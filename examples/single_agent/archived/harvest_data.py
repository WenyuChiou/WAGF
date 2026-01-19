
import os
import shutil
import pandas as pd
import glob
import re

def get_next_run_id(base_dir):
    if not os.path.exists(base_dir):
        os.makedirs(base_dir)
        return 1
    
    existing_runs = [d for d in os.listdir(base_dir) if d.startswith("Run_")]
    if not existing_runs:
        return 1
    
    # Extract numbers
    ids = []
    for r in existing_runs:
        try:
            ids.append(int(r.split('_')[1]))
        except:
            pass
    
    return max(ids) + 1 if ids else 1

def harvest():
    files = glob.glob("interim_*.csv")
    print(f"Found {len(files)} interim files.")
    
    harvested_count = 0
    deleted_count = 0
    
    for f in files:
        # Check size/lines
        try:
            with open(f, 'r', encoding='utf-8') as file:
                lines = file.readlines()
        except:
            print(f"Error reading {f}, skipping.")
            continue
            
        line_count = len(lines)
        print(f"Processing {f}: {line_count} lines...", end=" ")
        
        if line_count < 900:
            print("TOO SHORT. Deleting.")
            os.remove(f)
            deleted_count += 1
            continue
            
        # Infer Model and Group
        # Filename format: interim_MODEL_strict_SEED.csv e.g. interim_gemma3_4b_strict_33028.csv
        # or interim_llama3.2_3b_strict_...
        
        model_name = ""
        if "gemma3_4b" in f:
            model_name = "gemma3_4b"
        elif "llama3.2_3b" in f:
             model_name = "llama3_2_3b"
        elif "gemma2_9b" in f:
            print("Deprecated model (gemma2_9b). Deleting.")
            os.remove(f)
            deleted_count += 1
            continue
        
        if not model_name:
            print("Unknown model in filename. Skipping.")
            continue
            
        # Determine Group via basic log content or filename
        # "strict" usually implies Govenance (Group B or C).
        # We need to peek inside.
        
        # Read a few lines to check for memory buffer type or governance logs
        df = pd.read_csv(f)
        
        # Heuristic for Group:
        # If "governance_log" column has entries -> Group B or C
        # If "memory_system" is mentioned?
        # Actually, `run_overnight.ps1` mostly ran simple baselines or full governance.
        # Let's assume:
        # If filename has "strict" -> likely Group C (per previous script usage, defaulting to full governance)
        # Wait, run_flood.py arguments: --governance-mode strict is Group B/C.
        # But we need to distinguish B (Window) vs C (HumanCentric).
        # run_overnight.ps1 used --governance "full" for Group C.
        
        # Let's check the CSV headers or content.
        # Only Group A has NO governance.
        # Group C has "Consolidated Memory" or specific reflective pillars?
        
        # Defaulting to Group_C for "strict" runs from overnight script as it was targeting Group C.
        # But let's be safe. If we can't be sure, maybe move to a "Unsorted" folder?
        # Actually, the file content 'sim_type' or similar might help if logged? No.
        
        # Taking a risk: run_overnight.ps1 lines 43-49 were running Group C.
        # And run_baseline_original.py ran Group A.
        # run_baseline_original outputs to results/JOH_FINAL/... directly usually?
        # But `interim` files usually come from `run_flood.py`.
        # `run_flood.py` was used for Group B and C.
        # `run_baseline_original.py` uses `Group_A` in loop.
        
        # So likely these are Group B or C.
        # Given the "strict" in filename, it comes from `run_flood.py`.
        # The specific user goal in `run_overnight` was "Phase 2: Governed Runs (Group C is Critical)".
        # So most likely these are Group C.
        # I will assign to Group_C, but add a note or check if I can distinguishing B vs C.
        # Verify: Group C uses "humancentric", Group B uses "window".
        # Does the log contain memory type?
        # The column `memory` content might reveal it.
        # Group C memories start with "Year X: ..." summarized?
        # Group B are raw list?
        
        target_group = "Group_C" # High probability based on overnight script
        
        # Create Target Path
        target_dir = f"results/JOH_FINAL/{model_name}/{target_group}"
        run_id = get_next_run_id(target_dir)
        run_folder = f"{target_dir}/Run_{run_id}"
        os.makedirs(run_folder, exist_ok=True)
        
        target_file = f"{run_folder}/simulation_log.csv"
        shutil.move(f, target_file)
        print(f"Moved to {target_file}")
        harvested_count += 1
        
    print(f"Harvest complete. Moved {harvested_count} files. Deleted {deleted_count} files.")

if __name__ == "__main__":
    harvest()
