"""
Wait for Run_2 to finish (poll simulation_log.csv), then run batch for remaining runs.
Usage: python examples/single_agent/run_b1_after_run2.py
"""
import time
import subprocess
import sys
from pathlib import Path
from datetime import datetime

RUN2_LOG = Path(__file__).resolve().parent / "results" / "B1_doubled_premium" / "gemma3_4b" / "Group_A" / "Run_2" / "simulation_log.csv"
BATCH_SCRIPT = Path(__file__).resolve().parent / "run_b1_batch.py"

def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    log("Waiting for Group_A/Run_2 to complete...")

    while True:
        if RUN2_LOG.exists():
            lines = sum(1 for _ in open(RUN2_LOG, encoding='utf-8'))
            if lines >= 1000:
                log(f"Run_2 complete ({lines} lines). Starting batch...")
                break
            else:
                log(f"Run_2 in progress ({lines} lines)")
        else:
            log("Run_2 log not yet created")
        time.sleep(120)  # check every 2 min

    # Run batch (will skip completed runs automatically)
    subprocess.run([sys.executable, str(BATCH_SCRIPT)])

if __name__ == "__main__":
    main()
