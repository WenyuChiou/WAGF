import pandas as pd
from pathlib import Path

BASE_PATH = Path(r"H:\我的雲端硬碟\github\governed_broker_framework\examples\single_agent\results\JOH_FINAL\gemma3_4b\Group_C\Run_1")
LOG_PATH = BASE_PATH / "simulation_log.csv"

def extract_agent_001():
    df = pd.read_csv(LOG_PATH)
    agent_history = df[df['agent_id'] == 'Agent_001'][['year', 'elevated', 'yearly_decision', 'cumulative_state']]
    print("Agent_001 History:")
    print(agent_history)
    
    output_path = LOG_PATH.parent / "agent_001_sawtooth_data.csv"
    agent_history.to_csv(output_path, index=False)
    print(f"Data saved to {output_path}")

if __name__ == "__main__":
    extract_agent_001()
