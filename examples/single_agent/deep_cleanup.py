import os
import shutil

ROOTS = [
    r"results/JOH_FINAL",
    r"results/JOH_STRESS"
]
EXPECTED_LINES = 1001

def is_run_folder(dirpath):
    # Matches folders like Run_1, Run_2 etc.
    return os.path.basename(dirpath).startswith("Run_")

for root in ROOTS:
    if not os.path.exists(root):
        continue
    
    print(f"Scanning {root}...")
    for dirpath, dirnames, filenames in os.walk(root):
        if is_run_folder(dirpath):
            log_path = os.path.join(dirpath, "simulation_log.csv")
            is_complete = False
            
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'rb') as f:
                        count = sum(1 for _ in f)
                    if count >= EXPECTED_LINES:
                        is_complete = True
                    else:
                        print(f"  [Incomplete] {dirpath} (Lines: {count})")
                except Exception as e:
                    print(f"  [Error] {dirpath}: {e}")
            else:
                print(f"  [Incomplete] {dirpath} (No simulation_log.csv)")
            
            if not is_complete:
                print(f"  [Action] Deleting: {dirpath}")
                try:
                    shutil.rmtree(dirpath)
                except Exception as e:
                    print(f"  [Failed] Could not delete {dirpath}: {e}")

print("Cleanup script finished.")
