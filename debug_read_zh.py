
try:
    with open('README_zh.md', 'r', encoding='utf-8', errors='replace') as f:
        lines = f.readlines()
        for i, line in enumerate(lines):
            # Print lines starting from where the experiment section likely begins
            if i > 120: 
                print(f"{i+1}: {line.strip()}")
except Exception as e:
    print(f"Error: {e}")
