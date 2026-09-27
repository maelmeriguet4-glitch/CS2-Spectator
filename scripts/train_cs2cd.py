import argparse
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

from src.ml.classifier import extraire_vecteur_features

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join(REPO_ROOT, "data", "anti_cheat_dataset.csv")
NEW_MODEL_FILE = os.path.join(REPO_ROOT, "cerveau_vac_cs2cd.pkl")
FEATURES_CACHE = os.path.join(REPO_ROOT, "data", "features_cache.csv")
BASELINE_MODEL = os.path.join(REPO_ROOT, "cerveau_vac_custom.pkl")


def extract_all_features(manifest=MANIFEST, features_cache=FEATURES_CACHE):
    df = pd.read_csv(manifest)
    
    if os.path.exists(features_cache):
        print(f"Loading cached features from {features_cache}...")
        return pd.read_csv(features_cache)

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
    if features_df.empty:
        raise ValueError("No player features were extracted from the manifest.")
    os.makedirs(os.path.dirname(os.path.abspath(features_cache)), exist_ok=True)
    features_df.to_csv(features_cache, index=False)
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

def main(argv=None):
    parser = argparse.ArgumentParser(description="Train and evaluate the CS2CD classification model.")
    parser.add_argument("--manifest", default=MANIFEST, help="CS2CD manifest CSV.")
    parser.add_argument("--features-cache", default=FEATURES_CACHE, help="Cached extracted feature CSV.")
    parser.add_argument("--model-output", default=NEW_MODEL_FILE, help="Path for the trained model bundle.")
    parser.add_argument(
        "--baseline-model",
        default=BASELINE_MODEL,
        help="Existing model to compare against (never overwritten by this script).",
    )
    args = parser.parse_args(argv)

    if not os.path.exists(args.manifest):
        raise FileNotFoundError(
            f"Manifest not found: {args.manifest}. Run scripts/index_cs2cd.py first."
        )
        
    df = extract_all_features(args.manifest, args.features_cache)
    if "split" not in df.columns or "label" not in df.columns:
        raise ValueError("Feature data must contain 'split' and 'label' columns.")
    
    train_df = df[df['split'] == 'train']
    test_df = df[df['split'] == 'test']
    
    feature_cols = [c for c in df.columns if c.startswith("f_")]
    if train_df.empty or test_df.empty or not feature_cols:
        raise ValueError("The manifest must produce train and test examples with extracted features.")
    
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
    
    model_output = os.path.abspath(args.model_output)
    os.makedirs(os.path.dirname(model_output), exist_ok=True)
    joblib.dump({"scaler": scaler_cs2cd, "modele": rf_cs2cd}, model_output)
    
    preds_B = rf_cs2cd.predict(X_test_scaled_B)
    probs_B = rf_cs2cd.predict_proba(X_test_scaled_B)[:, 1]
    
    # 2. Evaluate current synthetic model (Model A)
    print("\nLoading Model A (Synthetic Data)...")
    if os.path.exists(args.baseline_model):
        try:
            paquet = joblib.load(args.baseline_model)
            scaler_synth = paquet['scaler']
            rf_synth = paquet['modele']
            
            X_test_scaled_A = scaler_synth.transform(X_test)
            preds_A = rf_synth.predict(X_test_scaled_A)
            probs_A = rf_synth.predict_proba(X_test_scaled_A)[:, 1]
            
            evaluate_model("Model A (Synthetic Data)", y_test, preds_A, probs_A)
        except Exception as e:
            print(f"Could not evaluate baseline model {args.baseline_model}: {e}")
    else:
        print(f"Baseline model not found: {args.baseline_model}")
        
    evaluate_model("Model B (Real CS2CD Data)", y_test, preds_B, probs_B)
    
    # Summary Report
    print("\n" + "="*50)
    print("REPORT: CS2CD DATASET INTEGRATION")
    print("="*50)
    print(f"1. Total Matches processed: {len(pd.read_csv(MANIFEST))}")
    print(f"2. Total Players extracted: {len(df)}")
    print(f"3. Train/Val/Test Split: {len(train_df)} / {len(df[df['split']=='validation'])} / {len(test_df)}")
    print(f"4. Features used: {len(feature_cols)} (Aim, Wallhack, Bhop)")
    print(f"5. New model saved as: {model_output}")
    print("6. To train on more matches, modify 'sample_size' in scripts/index_cs2cd.py and delete data/features_cache.csv")
    print("="*50)

if __name__ == "__main__":
    main()
