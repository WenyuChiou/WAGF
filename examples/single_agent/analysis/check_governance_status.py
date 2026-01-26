import os
import yaml
import glob

BASE_DIR = r"c:\Users\wenyu\Desktop\Lehigh\governed_broker_framework\examples\single_agent\results\JOH_FINAL"

def check_governance():
    print(f"{'Model':<20} | {'Group':<10} | {'Profile':<15} | {'Thinking Rules':<5} | {'Identity Rules':<5} | {'Intv Enabled?'}")
    print("-" * 90)
    
    # Walk through all subdirectories
    for model_dir in os.listdir(BASE_DIR):
        model_path = os.path.join(BASE_DIR, model_dir)
        if not os.path.isdir(model_path) or "deepseek" not in model_dir:
            continue
            
        for group in ["Group_A", "Group_B", "Group_C"]:
            group_path = os.path.join(model_path, group, "Run_1")
            
            # Find any config_snapshot.yaml using glob because subfolder names vary (disabled/strict/etc)
            # Pattern: model_path/group/Run_1/**/config_snapshot.yaml
            configs = glob.glob(os.path.join(group_path, "**", "config_snapshot.yaml"), recursive=True)
            
            if not configs:
                # 14B Flat structure check
                flat_config = os.path.join(group_path, "config_snapshot.yaml")
                if os.path.exists(flat_config):
                    configs = [flat_config]
            
            if not configs:
                print(f"{model_dir:<20} | {group:<10} | {'MISSING':<15} | {'-':<5} | {'-':<5} | ?")
                continue
                
            # Use the first one found
            config_file = configs[0]
            
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                    
                meta = data.get('metadata', {})
                profile = meta.get('governance_profile', 'unknown')
                
                # Check actual rules in the active profile
                gov_config = data.get('governance', {})
                active_rules = gov_config.get(profile, {}) if profile in gov_config else {}
                
                # If profile is 'disabled', active_rules usually empty or key doesn't exist deep down
                # Let's try to find where rules are defined explicitly for the active profile
                # Format: governance -> [profile] -> thinking_rules
                
                thinking = active_rules.get('thinking_rules', [])
                identity = active_rules.get('identity_rules', [])
                
                n_thinking = len(thinking) if thinking else 0
                n_identity = len(identity) if identity else 0
                
                is_enabled = n_thinking > 0 or n_identity > 0
                enabled_str = "YES" if is_enabled else "NO"
                
                print(f"{model_dir:<20} | {group:<10} | {profile:<15} | {n_thinking:<14} | {n_identity:<14} | {enabled_str}")
                
            except Exception as e:
                print(f"{model_dir:<20} | {group:<10} | Error: {str(e)}")

check_governance()
