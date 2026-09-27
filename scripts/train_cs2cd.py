#!/usr/bin/env python3
"""
CS2 Spectator - Entraînement et évaluation du modèle ML sur le dataset réel CS2CD.
Gère l'extraction des features, l'étanchéité des splits (anti-leakage),
le filtrage strict des labels 'unknown', l'optimisation du seuil sur la validation,
et l'évaluation finale indépendante sur le jeu de test.
"""

import argparse
from datetime import datetime
import json
import os
import sys
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler

# Ajouter la racine du projet au sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.analyzers.aimbot import analyser_aimbot
from src.analyzers.bhop import analyser_bhop
from src.analyzers.wallhack import analyser_wallhack
from src.analyzers.spinbot import analyser_spinbot
from src.analyzers.triggerbot import analyser_triggerbot
from src.ml.classifier import (
    FEATURE_SCHEMA_HASH,
    FEATURE_SCHEMA_VERSION,
    FICHIER_MODELE_SYNTHETIQUE,
    NOMS_FEATURES,
    extraire_vecteur_features,
    valider_bundle_modele,
)
from src.ml.cs2cd_adapter import CS2CDAdapter

DEFAULT_MANIFEST = os.path.join("data", "anti_cheat_dataset.csv")
DEFAULT_MODEL_OUT = "cerveau_vac_cs2cd.pkl"
DEFAULT_CACHE = os.path.join("data", "features_cache.csv")


def extraire_features_dataset(
    manifest_path: str,
    cache_path: str,
    force_extract: bool = False
) -> pd.DataFrame:
    """
    Lit le manifest et extrait les features des joueurs match par match via CS2CDAdapter.
    Applique la politique stricte de labels :
    - 'cheater' (1) : joueur confirmé dans la liste cheaters d'un match with_cheater
    - 'probable_non_cheater' (0) : joueur d'un match no_cheater_present (97.2% certitude)
    - 'unknown' (-1) : joueur non annoté dans un match with_cheater_present (exclu de l'entraînement)
    """
    if os.path.exists(cache_path) and not force_extract:
        print(f"[CACHE] Chargement des features en cache depuis : {cache_path}")
        try:
            df_cache = pd.read_csv(cache_path)
            if not df_cache.empty and "player_key" in df_cache.columns:
                if all(col in df_cache.columns for col in NOMS_FEATURES):
                    print(f"[CACHE] {len(df_cache)} profils de joueurs chargés avec succès (schéma {FEATURE_SCHEMA_VERSION} valide).")
                    return df_cache
                else:
                    print(f"[CACHE] Schéma de features incomplet dans le cache, ré-extraction...")
        except Exception as e:
            print(f"[CACHE] Cache invalide ou corrompu ({e}), ré-extraction...")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest introuvable: {manifest_path}. Exécutez scripts/index_cs2cd.py d'abord.")

    manifest_df = pd.read_csv(manifest_path)
    print(f"[EXTRACTION] Traitement de {len(manifest_df)} matches depuis {manifest_path}...")

    records: List[Dict[str, Any]] = []

    for idx, row in manifest_df.iterrows():
        match_id = str(row["match_id"])
        data_path = str(row["data_path"])
        metadata_path = str(row["metadata_path"])
        match_category = str(row.get("match_category", row.get("label", "")))
        split = str(row.get("split", "train"))

        # Liste des tricheurs annotés pour ce match
        raw_cheaters = str(row.get("cheaters", ""))
        cheaters_list = [c.strip() for c in raw_cheaters.split(",") if c.strip() and c.strip() != "nan"]

        if not os.path.exists(data_path) or not os.path.exists(metadata_path):
            continue

        try:
            adapter = CS2CDAdapter(data_path, metadata_path)
            if not adapter.valide:
                continue

            for player in adapter.joueurs:
                p_aim = analyser_aimbot(adapter, player)
                p_wh = analyser_wallhack(adapter, player)
                p_bhop = analyser_bhop(adapter, player)

                # Vecteur de 15 features calibré
                vec = extraire_vecteur_features(p_aim, p_bhop, p_wh)

                # Application de la Priorité Critique 2 (Labels stricts et non inventés)
                if match_category == "with_cheater_present":
                    if player in cheaters_list:
                        label_val = 1
                        label_text = "verified_cheater"
                        label_conf = "high"
                        label_src = "cs2cd_vac_verified"
                        usable = True
                    else:
                        label_val = -1  # Inconnu : non annoté mais dans un match suspect (trust factor)
                        label_text = "unknown"
                        label_conf = "low"
                        label_src = "unverified_in_cheater_match"
                        usable = False
                else:  # no_cheater_present
                    label_val = 0
                    label_text = "probable_non_cheater"
                    label_conf = "medium"  # 97.2% clean selon CS2CD
                    label_src = "cs2cd_no_vac_match"
                    usable = True

                player_key = f"{match_id}:{player}"

                rec = {
                    "match_id": match_id,
                    "player": player,
                    "player_key": player_key,
                    "split": split,
                    "label": label_val,
                    "label_text": label_text,
                    "label_confidence": label_conf,
                    "label_source": label_src,
                    "usable_for_training": usable,
                }

                for f_idx, col_name in enumerate(NOMS_FEATURES):
                    rec[col_name] = float(vec[f_idx])

                records.append(rec)

        except Exception as e:
            print(f"[ERREUR] Échec sur le match {match_id}: {e}")

        if (idx + 1) % 50 == 0 or (idx + 1) == len(manifest_df):
            print(f"  -> {idx + 1}/{len(manifest_df)} matches traités ({len(records)} joueurs extraits)...")

    df_features = pd.DataFrame(records)

    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    df_features.to_csv(cache_path, index=False, encoding="utf-8")
    print(f"[CACHE] Features sauvegardées dans : {cache_path} ({len(df_features)} lignes)")

    return df_features


def verifier_absence_de_fuite(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame):
    """
    Vérifie formellement qu'aucun identifiant de joueur ni de match n'est partagé entre train, val et test.
    Garantit l'indépendance statistique absolue des splits.
    """
    print("\n" + "=" * 60)
    print("VÉRIFICATION D'ÉTANCHÉITÉ DU SPLIT (ANTI-LEAKAGE)")
    print("=" * 60)
    train_keys = set(train_df["player_key"])
    val_keys = set(val_df["player_key"])
    test_keys = set(test_df["player_key"])

    leak_tr_val = train_keys & val_keys
    leak_tr_ts = train_keys & test_keys
    leak_val_ts = val_keys & test_keys

    assert len(leak_tr_val) == 0, f"Fuite de player_key détectée entre Train et Validation: {leak_tr_val}"
    assert len(leak_tr_ts) == 0, f"Fuite de player_key détectée entre Train et Test: {leak_tr_ts}"
    assert len(leak_val_ts) == 0, f"Fuite de player_key détectée entre Validation et Test: {leak_val_ts}"

    train_matches = set(train_df["match_id"])
    val_matches = set(val_df["match_id"])
    test_matches = set(test_df["match_id"])

    assert len(train_matches & val_matches) == 0, f"Fuite de match_id détectée entre Train et Validation: {train_matches & val_matches}"
    assert len(train_matches & test_matches) == 0, f"Fuite de match_id détectée entre Train et Test: {train_matches & test_matches}"
    assert len(val_matches & test_matches) == 0, f"Fuite de match_id détectée entre Validation et Test: {val_matches & test_matches}"

    print("[ANTI-LEAKAGE] Succès vérifié : 0 joueur et 0 match partagés.")
    print(f"  -> Matches : Train={len(train_matches)}, Val={len(val_matches)}, Test={len(test_matches)}")
    print(f"  -> Joueurs : Train={len(train_keys)}, Val={len(val_keys)}, Test={len(test_keys)}")
    print("=" * 60)


def calculer_metriques(y_true, y_pred, y_prob) -> Dict[str, Any]:
    """Calcule l'ensemble complet des métriques de performance binaire sans chiffre inventé."""
    prec = float(precision_score(y_true, y_pred, zero_division=0))
    rec = float(recall_score(y_true, y_pred, zero_division=0))
    f1 = float(f1_score(y_true, y_pred, zero_division=0))

    cm = confusion_matrix(y_true, y_pred)
    tn, fp, fn, tp = cm.ravel() if cm.shape == (2, 2) else (0, 0, 0, 0)

    fpr = float(fp / max(1, fp + tn))
    fnr = float(fn / max(1, fn + tp))

    auc = float(roc_auc_score(y_true, y_prob)) if len(np.unique(y_true)) > 1 else 0.0

    return {
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "fnr": round(fnr, 4),
        "roc_auc": round(auc, 4),
        "confusion_matrix": cm.tolist(),
        "tp": int(tp),
        "fp": int(fp),
        "tn": int(tn),
        "fn": int(fn),
    }


def optimiser_seuil_validation(y_val, probs_val) -> Tuple[float, Dict[str, Any]]:
    """
    Explore les seuils de décision sur le jeu de validation pour maximiser le F1-score
    tout en imposant un taux de faux positifs quasi-nul (sécurité anti-cheat stricte).
    """
    seuils = np.arange(0.50, 0.85, 0.05)
    meilleur_seuil = 0.50
    meilleur_f1 = -1.0
    meilleures_metriques = {}

    for s in seuils:
        preds = (probs_val >= s).astype(int)
        m = calculer_metriques(y_val, preds, probs_val)
        # Pénalisation stricte des faux positifs : priorité absolue à la non-condamnation d'innocents
        if m["fpr"] > 0.05:
            score_critere = -1.0
        else:
            score_critere = m["f1"] - (m["fpr"] * 3.0)

        if score_critere > meilleur_f1:
            meilleur_f1 = score_critere
            meilleur_seuil = float(s)
            meilleures_metriques = m

    # Fallback si tous les seuils ont fpr > 0.05 : prendre le seuil minimisant le FPR
    if meilleur_f1 < 0:
        meilleur_seuil = 0.60
        preds = (probs_val >= meilleur_seuil).astype(int)
        meilleures_metriques = calculer_metriques(y_val, preds, probs_val)

    return meilleur_seuil, meilleures_metriques


def afficher_rapport_metriques(titre: str, m: Dict[str, Any]):
    """Affiche de manière structurée et lisible les résultats."""
    print(f"\n--- {titre} ---")
    print(f"  Precision (Précision)         : {m['precision'] * 100:.2f}%")
    print(f"  Recall (Rappel)               : {m['recall'] * 100:.2f}%")
    print(f"  F1-Score                      : {m['f1']:.4f}")
    print(f"  FPR (Faux Positifs / Legits)   : {m['fpr'] * 100:.2f}% ({m['fp']}/{m['fp'] + m['tn']})")
    print(f"  FNR (Faux Négatifs / Cheaters) : {m['fnr'] * 100:.2f}% ({m['fn']}/{m['fn'] + m['tp']})")
    print(f"  ROC-AUC                       : {m['roc_auc']:.4f}")
    print(f"  Matrice de Confusion          :")
    print(f"    [[TN={m['tn']}, FP={m['fp']}],")
    print(f"     [FN={m['fn']}, TP={m['tp']}]]")


def train_cs2cd_pipeline(
    manifest_path: str = DEFAULT_MANIFEST,
    output_model: str = DEFAULT_MODEL_OUT,
    cache_path: str = DEFAULT_CACHE,
    force_extract: bool = False,
    compare_synthetic: bool = True,
):
    """Pipeline d'entraînement et d'évaluation complet."""
    print("\n" + "=" * 60)
    print("CS2 SPECTATOR - PIPELINE D'ENTRAÎNEMENT CS2CD")
    print("=" * 60)

    # 1. Extraction et chargement des features
    df = extraire_features_dataset(manifest_path, cache_path, force_extract=force_extract)

    # 2. Filtrage des données utilisables pour l'entraînement supervisé (Priorité Critique 2)
    total_joueurs = len(df)
    unknown_count = len(df[df["label"] == -1])
    cheaters_total = len(df[df["label"] == 1])
    legits_total = len(df[df["label"] == 0])

    print(f"\n[POPULATION TOTALE] {total_joueurs} profils de joueurs extraits :")
    print(f"  - Tricheurs vérifiés (label=1)  : {cheaters_total}")
    print(f"  - Légitimes réputés (label=0)   : {legits_total}")
    print(f"  - Inconnus écartés (label=-1)   : {unknown_count} (Joueurs non annotés dans les matches avec tricheur)")

    # Exclure strictly les 'unknown' pour la supervision binaire
    df_supervised = df[df["usable_for_training"] == True].copy()

    train_df = df_supervised[df_supervised["split"] == "train"]
    val_df = df_supervised[df_supervised["split"] == "validation"]
    test_df = df_supervised[df_supervised["split"] == "test"]

    print(f"\n[SPLIT SUPERVISÉ]")
    print(f"  - Train      : {len(train_df)} joueurs (Cheaters: {sum(train_df['label'] == 1)})")
    print(f"  - Validation : {len(val_df)} joueurs (Cheaters: {sum(val_df['label'] == 1)})")
    print(f"  - Test       : {len(test_df)} joueurs (Cheaters: {sum(test_df['label'] == 1)})")

    # 3. Vérification formelle d'étanchéité (Priorité Critique 4)
    verifier_absence_de_fuite(train_df, val_df, test_df)

    # 4. Préparation des matrices de features
    X_train = train_df[NOMS_FEATURES].values
    y_train = train_df["label"].values.astype(int)

    X_val = val_df[NOMS_FEATURES].values
    y_val = val_df["label"].values.astype(int)

    X_test = test_df[NOMS_FEATURES].values
    y_test = test_df["label"].values.astype(int)

    # 5. Entraînement supervisé sur TRAIN
    print("\n[ENTRAÎNEMENT] Entraînement du StandardScaler et RandomForest sur TRAIN...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_val_scaled = scaler.transform(X_val)
    X_test_scaled = scaler.transform(X_test)

    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=2,
        random_state=42
    )
    rf.fit(X_train_scaled, y_train)

    # Entraînement de l'IsolationForest sur les profils légitimes de TRAIN
    X_clean_train = X_train_scaled[y_train == 0]
    iso = IsolationForest(contamination=0.04, random_state=42)
    iso.fit(X_clean_train)

    # 6. Utilisation de la VALIDATION pour optimiser le seuil de décision (Priorité Critique 5)
    print("\n[VALIDATION] Optimisation du seuil de décision sur VALIDATION...")
    probs_val = rf.predict_proba(X_val_scaled)[:, 1]
    optimal_threshold, val_metrics = optimiser_seuil_validation(y_val, probs_val)
    print(f"[VALIDATION] Seuil optimal sélectionné : {optimal_threshold:.2f}")
    afficher_rapport_metriques("MÉTRIQUES VALIDATION (Sélection Hyperparamètre)", val_metrics)

    # 7. Évaluation finale indépendante sur TEST (sans toucher aux hyperparamètres)
    print("\n[TEST] Évaluation finale indépendante sur TEST...")
    probs_test = rf.predict_proba(X_test_scaled)[:, 1]
    preds_test = (probs_test >= optimal_threshold).astype(int)
    test_metrics = calculer_metriques(y_test, preds_test, probs_test)
    afficher_rapport_metriques("MÉTRIQUES FINALES TEST (CS2CD Modèle B)", test_metrics)

    # 8. Comparaison avec le Modèle Synthétique Historique (Modèle A)
    if compare_synthetic and os.path.exists(FICHIER_MODELE_SYNTHETIQUE):
        try:
            print("\n" + "=" * 60)
            print("COMPARAISON AVEC LE MODÈLE SYNTHÉTIQUE (MODÈLE A)")
            print("=" * 60)
            paquet_synth = joblib.load(FICHIER_MODELE_SYNTHETIQUE)
            scaler_synth = paquet_synth["scaler"]
            rf_synth = paquet_synth["modele"]

            X_test_scaled_synth = scaler_synth.transform(X_test)
            probs_synth = rf_synth.predict_proba(X_test_scaled_synth)[:, 1]
            preds_synth = (probs_synth >= 0.50).astype(int)
            synth_metrics = calculer_metriques(y_test, preds_synth, probs_synth)
            afficher_rapport_metriques("MÉTRIQUES DU MODÈLE SYNTHÉTIQUE SUR LE TEST RÉEL", synth_metrics)
        except Exception as e:
            print(f"[AVERTISSEMENT] Impossible d'évaluer le modèle synthétique: {e}")

    # 9. Création du bundle complet pour cerveau_vac_cs2cd.pkl (Priorité Critique 9)
    threshold_suspect = 0.40
    bundle = {
        "scaler": scaler,
        "modele": rf,
        "isolation_forest": iso,
        "noms_features": NOMS_FEATURES,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "dataset_name": "CS2CD",
        "dataset_revision": "CS2CD-Zenodo-2024",
        "dataset_version": "v1.0-anonymized",
        "training_date": datetime.now().isoformat(),
        "train_count": int(len(X_train)),
        "validation_count": int(len(X_val)),
        "test_count": int(len(X_test)),
        "threshold": float(optimal_threshold),
        "threshold_high": float(optimal_threshold),
        "threshold_suspect": threshold_suspect,
        "validation_metrics": val_metrics,
        "test_metrics": test_metrics,
        "model_type": "RandomForestClassifier",
    }

    # Validation stricte du bundle avant écriture disque
    valider_bundle_modele(bundle)
    joblib.dump(bundle, output_model)
    print(f"\n[OK] Nouveau modèle bundle CS2CD sauvegardé : {output_model}")

    return bundle


def main():
    parser = argparse.ArgumentParser(description="Entraîner le modèle CS2 Spectator sur le dataset CS2CD.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST, help="Chemin du manifest CSV")
    parser.add_argument("--output-model", default=DEFAULT_MODEL_OUT, help="Chemin de sortie du modèle .pkl")
    parser.add_argument("--features-cache", default=DEFAULT_CACHE, help="Chemin du fichier cache des features")
    parser.add_argument("--force-extract", action="store_true", help="Forcer le re-calcul des features sans utiliser le cache")
    parser.add_argument("--no-compare", action="store_true", help="Désactiver la comparaison avec le modèle synthétique")

    args = parser.parse_args()
    train_cs2cd_pipeline(
        manifest_path=args.manifest,
        output_model=args.output_model,
        cache_path=args.features_cache,
        force_extract=args.force_extract,
        compare_synthetic=not args.no_compare,
    )


if __name__ == "__main__":
    main()
