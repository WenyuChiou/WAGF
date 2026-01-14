import subprocess
import time
import sys
import os

# Configuration
models = ['llama3.2:3b', 'gemma3:4b', 'deepseek-r1:8b', 'gpt-oss:latest']
engines = ['window', 'importance', 'humancentric']
agents = 100
years = 10
base_output_dir = "results_batch_v2"

def run_command(cmd):
    print(f"[{time.strftime('%H:%M:%S')}] Running: {cmd}")
    try:
        # Run and stream output to verify progress
        result = subprocess.run(cmd, shell=True, check=True)
        return result.returncode == 0
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {cmd}")
        print(e)
        return False

def main():
    print("=== Starting Batch Experiments (12 Runs) ===")
    
    # Ensure base output dir exists
    if not os.path.exists(base_output_dir):
        os.makedirs(base_output_dir)
    
    for model in models:
        for engine in engines:
            model_safe = model.replace(':','_').replace('.','_')
            folder_name = f"{model_safe}_{engine}_strict"
            
            # Check if already exists to skip
            target_path = os.path.join(base_output_dir, folder_name)
            if os.path.exists(target_path) and os.path.exists(os.path.join(target_path, "audit_summary.json")):
                print(f"Skipping completed experiment: {model} + {engine}")
                continue

            print(f"\n----------------------------------------------------------------")
            print(f" Experiment: Model={model} | Memory={engine}")
            print(f"----------------------------------------------------------------")
            
            # Construct command
            # Each engine now has its own folder
            cmd = f"python run_flood.py --model {model} --agents {agents} --years {years} --memory-engine {engine} --output {target_path}"
            
            success = run_command(cmd)
            
            if not success:
                print(f"!!! Experiment Failed: {model} + {engine} !!!")
                # User said "接續跑" (continue running), so we don't break
            else:
                print(f">>> Experiment Success: {model} + {engine}")
            
            # Small cooldown
            time.sleep(5)

    print("\n=== All Experiments Completed ===")
    print("Preparing Git Commit...")
    
    # Git operations
    run_command('git add -A')
    run_command('git commit -m "chore: batch run results for 12 experiments (4 models x 3 engines)"')
    run_command('git push')
    print("=== Batch Process Finished ===")

if __name__ == "__main__":
    main()
