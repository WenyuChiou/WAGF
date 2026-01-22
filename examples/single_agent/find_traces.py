import os
import json

root = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
traces = []

for dirpath, dirnames, filenames in os.walk(root):
    for f in filenames:
        if f == "household_traces.jsonl":
            traces.append(os.path.join(dirpath, f))

with open(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\traces_search.json", "w") as f:
    json.dump(traces, f, indent=2)
