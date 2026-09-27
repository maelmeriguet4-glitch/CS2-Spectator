import os
import pandas as pd
import numpy as np
import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.ml.cs2cd_adapter import CS2CDAdapter
from src.analyzers.aimbot import analyser_aimbot
from src.analyzers.wallhack import analyser_wallhack
# Fallbacks for bhop (if bhop is available)
try:
    from src.analyzers.bhop import analyser_bhop
except ImportError:
    def analyser_bhop(demo, p): return {}

from src.ml.classifier import extraire_vecteur_features, FICHIER_MODELE

MANIFEST = r"data\anti_cheat_dataset.csv"
NEW_MODEL_FILE = r"cerveau_vac_cs2cd.pkl"
FEATURES_CACHE = r"data\features_cache.csv"

def extract_all_features():
    df = pd.read_csv(MANIFEST)
    
    if os.path.exists(FEATURES_CACHE):
        print(f"Loading cached features from {FEATURES_CACHE}...")
        return pd.read_csv(FEATURES_CACHE)

    print("Extracting features from raw dataset. This may take a while...")
    records = []
    
    for idx, row in df.iterrows():
        print(f"Processing {row['match_id']} ({idx+1}/{len(df)})...")
        try:
            adapter = CS2CDAdapter(row['parquet_path'], row['json_path'])
            cheaters = str(row['cheaters']).split(',') if pd.notna(row['cheaters']) and row['cheaters'] != '' else []
            
            for player in adapter.joueurs:
                p_aim = analyser_aimbot(adapter, player)
                p_wh = analyser_wallhack(adapter, player)
                p_bhop = analyser_bhop(adapter, player)
                
                vec = extraire_vecteur_features(p_aim, p_bhop, p_wh)
                
                is_cheater = 1 if player in cheaters else 0
                
                rec = {
                    "match_id": row["match_id"],
                    "player": player,
                    "split": row["split"],
                    "label": is_cheater
                }
                for i, v in enumerate(vec):
                    rec[f"f_{i}"] = v
                    
                records.append(rec)
        except Exception as e:
            import traceback
            print(f"Failed on {row['match_id']}: {e}")
            traceback.print_exc()
            
    features_df = pd.DataFrame(records)
    features_df.to_csv(FEATURES_CACHE, index=False)
    return features_df

def evaluate_model(model_name, y_true, y_pred, y_prob):
    print(f"\n{'='*50}\nResults for {model_name}:\n{'='*50}")
    print(classification_report(y_true, y_pred, zero_division=0))
    print("Confusion Matrix:")
    print(confusion_matrix(y_true, y_pred))
    if len(np.unique(y_true)) > 1:
        auc = roc_auc_score(y_true, y_prob)
        print(f"ROC-AUC: {auc:.4f}")
    else:
        print("ROC-AUC: Not defined (only one class in test set)")

def main():
    if not os.path.exists(MANIFEST):
        print(f"Manifest {MANIFEST} not found. Please run index_cs2cd.py first.")
        return
        
    df = extract_all_features()
    
    train_df = df[df['split'] == 'train']
    test_df = df[df['split'] == 'test']
    
    feature_cols = [c for c in df.columns if c.startswith("f_")]
    
    X_train = train_df[feature_cols].values
    y_train = train_df['label'].values
    
    X_test = test_df[feature_cols].values
    y_test = test_df['label'].values
    
    print(f"\nDataset size: {len(df)} players.")
    print(f"Train: {len(X_train)} (Cheaters: {sum(y_train)})")
    print(f"Test: {len(X_test)} (Cheaters: {sum(y_test)})")
    
    # 1. Train new model on CS2CD data
    print("\nTraining Model B (Real Data - CS2CD)...")
    scaler_cs2cd = StandardScaler()
    X_train_scaled = scaler_cs2cd.fit_transform(X_train)
    X_test_scaled_B = scaler_cs2cd.transform(X_test)
    
    rf_cs2cd = RandomForestClassifier(n_estimators=100, max_depth=10, random_state=42)
    rf_cs2cd.fit(X_train_scaled, y_train)
    
    joblib.dump({"scaler": scaler_cs2cd, "modele": rf_cs2cd}, NEW_MODEL_FILE)
    
    preds_B = rf_cs2cd.predict(X_test_scaled_B)
    probs_B = rf_cs2cd.predict_proba(X_test_scaled_B)[:, 1]
    
    # 2. Evaluate current synthetic model (Model A)
    print("\nLoading Model A (Synthetic Data)...")
    if os.path.exists(FICHIER_MODELE):
        try:
            paquet = joblib.load(FICHIER_MODELE)
            scaler_synth = paquet['scaler']
            rf_synth = paquet['modele']
            
            X_test_scaled_A = scaler_synth.transform(X_test)
            preds_A = rf_synth.predict(X_test_scaled_A)
            probs_A = rf_synth.predict_proba(X_test_scaled_A)[:, 1]
            
            evaluate_model("Model A (Synthetic Data)", y_test, preds_A, probs_A)
        except Exception as e:
            print(f"Could not evaluate Model A: {e}")
    else:
        print("Model A not found.")
        
    evaluate_model("Model B (Real CS2CD Data)", y_test, preds_B, probs_B)
    
    # Summary Report
    print("\n" + "="*50)
    print("REPORT: CS2CD DATASET INTEGRATION")
    print("="*50)
    print(f"1. Total Matches processed: {len(pd.read_csv(MANIFEST))}")
    print(f"2. Total Players extracted: {len(df)}")
    print(f"3. Train/Val/Test Split: {len(train_df)} / {len(df[df['split']=='validation'])} / {len(test_df)}")
    print(f"4. Features used: {len(feature_cols)} (Aim, Wallhack, Bhop)")
    print(f"5. New model saved as: {NEW_MODEL_FILE}")
    print("6. To train on more matches, modify 'sample_size' in scripts/index_cs2cd.py and delete data/features_cache.csv")
    print("="*50)

if __name__ == "__main__":
    main()
