
import subprocess
import os
import sys

def run_step(name, command):
    print(f"\n>>> Running: {name}")
    print(f"Command: {' '.join(command)}")
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        try:
            print(result.stdout)
        except UnicodeEncodeError:
            print(result.stdout.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    except subprocess.CalledProcessError as e:
        print(f"❌ Error in {name}:")
        print(e.stderr)
        return False
    return True

def main():
    base_dir = "results/JOH_FINAL"
    
    # Check if results exist
    if not os.path.exists(base_dir):
        print(f"Error: {base_dir} not found. Run simulations first.")
        return

    steps = [
        ("Internal Fidelity (IF) Analysis", 
         ["python", "analyze_joh_fidelity.py", "--base-dir", base_dir]),
        
        ("Rationality (MCC/Panic) Analysis", 
         ["python", "analysis_tools/analyze_joh_mcc.py", "--base-dir", base_dir]),
        
        ("Figure 5: Decision Integrity Plot", 
         ["python", "analysis_tools/plot_decision_integrity.py", "--base-dir", base_dir]),
        
        ("Figure 6: Hallucination Asymmetry Plot", 
         ["python", "analysis_tools/plot_asymmetry.py", "--base-dir", base_dir])
    ]

    success_count = 0
    for name, cmd in steps:
        if run_step(name, cmd):
            success_count += 1
        else:
            print(f"Skipping subsequent steps due to failure in {name}")
            break
            
    print(f"\n=== Analysis Pipeline Complete ({success_count}/{len(steps)} steps) ===")
    if success_count == len(steps):
        print(f"Final outputs available in: {os.path.join(base_dir, 'plots')}")

if __name__ == "__main__":
    main()
