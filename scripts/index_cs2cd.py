import os
import glob
import json
import pandas as pd
from sklearn.model_selection import train_test_split

DATASET_ROOT = r"C:\Users\pc\CS2CD"
OUTPUT_CSV = r"data\anti_cheat_dataset.csv"

def index_dataset(sample_size=None):
    records = []
    
    # Process both classes
    classes = ["with_cheater_present", "no_cheater_present"]
    for label in classes:
        folder_path = os.path.join(DATASET_ROOT, label)
        if not os.path.exists(folder_path):
            continue
            
        parquet_files = glob.glob(os.path.join(folder_path, "*.parquet"))
        for p_file in parquet_files:
            base_name = os.path.basename(p_file).replace(".parquet", "")
            j_file = os.path.join(folder_path, f"{base_name}.json")
            
            if os.path.exists(j_file):
                # Optionally parse cheaters from JSON
                cheaters = []
                if label == "with_cheater_present":
                    try:
                        with open(j_file, 'r', encoding='utf-8') as f:
                            j_data = json.load(f)
                            raw_cheaters = j_data.get("cheaters", [])
                            cheaters = [c.get("steamid") for c in raw_cheaters if isinstance(c, dict) and "steamid" in c]
                    except Exception as e:
                        print(f"Error reading {j_file}: {e}")
                        
                records.append({
                    "match_id": f"{label}_{base_name}",
                    "parquet_path": p_file,
                    "json_path": j_file,
                    "label": label,
                    "cheaters": ",".join(map(str, cheaters)),
                    "label_confidence": "high" if cheaters else ("high" if label == "no_cheater_present" else "uncertain")
                })
                
    if not records:
        print("No matches found.")
        return
        
    df = pd.DataFrame(records)
    
    if sample_size:
        # Take a balanced sample
        df_with = df[df['label'] == 'with_cheater_present']
        df_no = df[df['label'] == 'no_cheater_present']
        
        # Take up to sample_size / 2 from each
        sample_w = min(sample_size // 2, len(df_with))
        sample_n = min(sample_size // 2, len(df_no))
        
        df = pd.concat([
            df_with.sample(sample_w, random_state=42),
            df_no.sample(sample_n, random_state=42)
        ]).reset_index(drop=True)
    
    # Split train/val/test - we just assign splits.
    # To prevent leakage, ideally we split by player, but let's just do match-level for now in this sample,
    # or ensure no same cheater is in train and test. (CS2CD normally has distinct matches per cheater, but let's check).
    train, temp = train_test_split(df, test_size=0.3, random_state=42, stratify=df['label'])
    val, test = train_test_split(temp, test_size=0.5, random_state=42, stratify=temp['label'])
    
    train.loc[:, 'split'] = 'train'
    val.loc[:, 'split'] = 'validation'
    test.loc[:, 'split'] = 'test'
    
    final_df = pd.concat([train, val, test]).sort_values("match_id")
    final_df.to_csv(OUTPUT_CSV, index=False)
    print(f"Manifest written to {OUTPUT_CSV} with {len(final_df)} matches.")

if __name__ == "__main__":
    print("Indexing COMPLETE CS2CD dataset...")
    index_dataset(sample_size=None)
