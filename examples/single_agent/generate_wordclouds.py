import pandas as pd
import json
from pathlib import Path
from wordcloud import WordCloud
import matplotlib.pyplot as plt

def get_text_for_group(log_path, group_name="Group_A"):
    text = ""
    df = pd.read_csv(log_path)
    
    # Logic to extract textual justifications
    if "threat_appraisal" in df.columns and not df["threat_appraisal"].isna().all():
        text = " ".join(df["threat_appraisal"].astype(str).tolist())
    else:
        # Try finding JSONL traces
        trace_files = list(log_path.parent.rglob("household_traces.jsonl"))
        if trace_files:
            with open(trace_files[0], 'r', encoding='utf-8') as f:
                for line in f:
                    data = json.loads(line)
                    text += " " + data.get("raw_output", "")
    return text

def generate_wc(text, output_file, title):
    if not text.strip():
        print(f"Skipping {title}: No text found.")
        return
        
    wc = WordCloud(width=800, height=400, background_color='white', 
                  max_words=100, contour_width=3, contour_color='steelblue').generate(text)
    
    plt.figure(figsize=(10, 5))
    plt.imshow(wc, interpolation='bilinear')
    plt.axis('off')
    plt.title(title)
    plt.savefig(output_file)
    print(f"Saved {output_file}")

if __name__ == "__main__":
    logs = [
        ("results/JOH_FINAL/gemma3_4b/Group_A/Run_1/simulation_log.csv", "Gemma_GroupA_WordCloud.png", "Group A (Naive) Narrative"),
        ("results/JOH_FINAL/gemma3_4b/Group_B/Run_1/simulation_log.csv", "Gemma_GroupB_WordCloud.png", "Group B (Governed) Narrative")
    ]
    
    for log_p, out_p, title in logs:
        path = Path(log_p)
        if path.exists():
            txt = get_text_for_group(path)
            generate_wc(txt, out_p, title)
