import os
import json

root = r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework"
results = []

for dirpath, dirnames, filenames in os.walk(root):
    if "Group_B" in dirpath or "Group_C" in dirpath:
        results.append(dirpath)
    for f in filenames:
        if "Group_B" in f or "Group_C" in f:
            results.append(os.path.join(dirpath, f))

with open(r"C:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\global_search.json", "w") as f:
    json.dump(results, f, indent=2)
