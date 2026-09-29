#!/usr/bin/env python3
"""
CS2 Spectator - Entraînement et évaluation du modèle ML sur le dataset réel CS2CD.
Gère l'extraction des features, l'étanchéité des splits (anti-leakage),
le filtrage strict des labels 'unknown', l'optimisation du seuil sur la validation,
et l'évaluation finale indépendante sur le jeu de test.
"""

import argparse
import json
import os
import sys
from datetime import datetime
from typing import Any, Dict, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from sklearn.preprocessing import StandardScaler

# Ajouter la racine du projet au sys.path
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.analyzers.aimbot import analyze_aimbot
from src.analyzers.bhop import analyze_bhop
from src.analyzers.wallhack import analyze_wallhack
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
MODEL_VERSION = "2.4.2"


def compute_strong_cache_hash(manifest_path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    h.update(FEATURE_SCHEMA_VERSION.encode('utf-8'))
    h.update(FEATURE_SCHEMA_HASH.encode('utf-8'))
    
    # Hash manifest
    if os.path.exists(manifest_path):
        with open(manifest_path, 'rb') as f:
            h.update(f.read())
            
    # Hash adapters and analyzers
    for p in ['src/ml/cs2cd_adapter.py', 'src/analyzers/aimbot.py', 'src/analyzers/wallhack.py', 'src/analyzers/bhop.py', 'src/ml/classifier.py']:
        if os.path.exists(p):
            with open(p, 'rb') as f:
                h.update(f.read())
    return h.hexdigest()

def verifier_absence_de_fuite(train_df: pd.DataFrame, val_df: pd.DataFrame, test_df: pd.DataFrame) -> None:
    """
    Vérifie formellement qu'aucune clé `match_id:player_key` n'est partagée
    entre les partitions Train / Validation / Test.

    Lève une RuntimeError au premier chevauchement détecté.
    """
    def _cles(df: pd.DataFrame) -> set:
        if df is None or df.empty:
            return set()
        match_col = df["match_id"] if "match_id" in df.columns else pd.Series([""] * len(df), index=df.index)
        player_col = df["player_key"] if "player_key" in df.columns else df["steamid"] if "steamid" in df.columns else pd.Series([""] * len(df), index=df.index)
        return {
            f"{m}:{p}" for m, p in zip(match_col.astype(str), player_col.astype(str))
        }

    cles_train = _cles(train_df)
    cles_val = _cles(val_df)
    cles_test = _cles(test_df)

    paires = [
        ("Train", "Validation", cles_train & cles_val),
        ("Train", "Test", cles_train & cles_test),
        ("Validation", "Test", cles_val & cles_test),
    ]
    for nom_a, nom_b, inter in paires:
        if inter:
            exemples = sorted(inter)[:5]
            raise RuntimeError(
                f"Fuite de données détectée entre {nom_a} et {nom_b} : "
                f"{len(inter)} clé(s) partagée(s) (ex: {exemples})."
            )

    print(
        f"[ÉTANCHÉITÉ] Aucune fuite match_id:player_key "
        f"(Train={len(cles_train)}, Validation={len(cles_val)}, Test={len(cles_test)})."
    )


def calculer_metriques(y_true, y_pred, y_proba=None) -> Dict[str, Any]:
    """Calcule les métriques binaires de classification (robuste aux classes absentes)."""
    y_true = np.asarray(y_true).astype(int).ravel()
    y_pred = np.asarray(y_pred).astype(int).ravel()

    tp = int(np.sum((y_pred == 1) & (y_true == 1)))
    fp = int(np.sum((y_pred == 1) & (y_true == 0)))
    tn = int(np.sum((y_pred == 0) & (y_true == 0)))
    fn = int(np.sum((y_pred == 0) & (y_true == 1)))

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0

    roc_auc = None
    if y_proba is not None:
        y_proba = np.asarray(y_proba, dtype=float).ravel()
        if len(np.unique(y_true)) > 1:
            try:
                roc_auc = float(roc_auc_score(y_true, y_proba))
            except ValueError:
                roc_auc = None

    return {
        "precision": round(float(precision), 4),
        "recall": round(float(recall), 4),
        "f1": round(float(f1), 4),
        "fpr": round(float(fpr), 4),
        "fnr": round(float(fnr), 4),
        "roc_auc": round(roc_auc, 4) if roc_auc is not None else None,
        "confusion_matrix": [[tn, fp], [fn, tp]],
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "n_samples": len(y_true),
    }


def optimiser_seuil_validation(y_val, probs_val) -> Tuple[float, Dict[str, Any]]:
    """
    Sélectionne le seuil de décision maximisant le F1 sur la VALIDATION.
    Le seuil retenu ne doit jamais rendre l'étiquette "suspicion élevée" vide :
    si le F1 est identique, on privilégie le seuil le plus élevé (moins de faux positifs).
    """
    y_val = np.asarray(y_val).astype(int).ravel()
    probs_val = np.asarray(probs_val, dtype=float).ravel()

    if len(y_val) == 0:
        raise RuntimeError("Jeu de validation vide : impossible d'optimiser le seuil.")
    if len(np.unique(y_val)) < 2:
        metriques = calculer_metriques(y_val, (probs_val >= 0.5).astype(int), probs_val)
        print("[VALIDATION] Une seule classe présente sur la validation : seuil neutre 0.50 retenu.")
        return 0.50, metriques

    meilleur_seuil = 0.50
    meilleur_f1 = -1.0
    meilleures_metriques = None

    for seuil in np.arange(0.05, 0.96, 0.05):
        preds = (probs_val >= seuil).astype(int)
        metriques = calculer_metriques(y_val, preds, probs_val)
        f1 = metriques["f1"]
        if f1 > meilleur_f1 or (f1 == meilleur_f1 and seuil > meilleur_seuil):
            meilleur_f1 = f1
            meilleur_seuil = float(round(seuil, 2))
            meilleures_metriques = metriques

    # Sécurité : ne jamais publier un seuil qui empêcherait la détection de tout tricheur
    if meilleures_metriques is None or meilleures_metriques["recall"] == 0.0:
        print("[VALIDATION] Rappel nul au seuil optimal : repli sur 0.50.")
        meilleur_seuil = 0.50
        meilleures_metriques = calculer_metriques(y_val, (probs_val >= 0.50).astype(int), probs_val)

    return meilleur_seuil, meilleures_metriques


def afficher_rapport_metriques(titre: str, metriques: Dict[str, Any]) -> None:
    """Affiche un rapport de métriques lisible en console."""
    print("-" * 60)
    print(titre)
    print("-" * 60)
    if not metriques:
        print("  (aucune métrique disponible)")
        return
    print(f"  Échantillons : {metriques.get('n_samples')}")
    print(f"  Précision    : {metriques.get('precision')}")
    print(f"  Rappel       : {metriques.get('recall')}")
    print(f"  F1           : {metriques.get('f1')}")
    print(f"  FPR / FNR    : {metriques.get('fpr')} / {metriques.get('fnr')}")
    print(f"  ROC AUC      : {metriques.get('roc_auc')}")
    print(f"  Matrice      : {metriques.get('confusion_matrix')}  (TN, FP / FN, TP)")
    print("-" * 60)


def extraire_features_dataset(
    manifest_path: str,
    cache_path: str,
    force_extract: bool = False
) -> pd.DataFrame:
    cache_meta_path = cache_path + ".meta.json"
    current_hash = compute_strong_cache_hash(manifest_path)
    
    if os.path.exists(cache_path) and os.path.exists(cache_meta_path) and not force_extract:
        try:
            with open(cache_meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            
            if meta.get("hash") == current_hash and meta.get("schema_version") == FEATURE_SCHEMA_VERSION:
                print(f"[CACHE] Hash fort validé. Chargement depuis : {cache_path}")
                df_cache = pd.read_csv(cache_path)
                if not df_cache.empty and "player_key" in df_cache.columns:
                    if all(col in df_cache.columns for col in NOMS_FEATURES):
                        print(f"[CACHE] {len(df_cache)} profils chargés.")
                        return df_cache
            else:
                print("[CACHE] Hash invalide ou schéma obsolète. Ré-extraction...")
        except Exception as e:
            print(f"[CACHE] Cache invalide ou corrompu ({e}), ré-extraction...")

    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"Manifest introuvable: {manifest_path}.")

    manifest_df = pd.read_csv(manifest_path)
    total_matches = len(manifest_df)
    print(f"[EXTRACTION] Traitement de {total_matches} matches depuis {manifest_path}...")

    records = []
    rejected_count = 0
    error_count = 0

    for idx, row in manifest_df.iterrows():
        match_id = str(row["match_id"])
        data_path = str(row["data_path"])
        metadata_path = str(row["metadata_path"])
        match_category = str(row.get("match_category", row.get("label", "")))
        split = str(row.get("split", "train"))

        raw_cheaters = str(row.get("cheaters", ""))
        cheaters_list = [c.strip() for c in raw_cheaters.split(",") if c.strip() and c.strip() != "nan"]

        if not os.path.exists(data_path) or not os.path.exists(metadata_path):
            rejected_count += 1
            continue

        try:
            adapter = CS2CDAdapter(data_path, metadata_path)
            if not getattr(adapter, "valide", False):
                rejected_count += 1
                continue
            joueurs = list(getattr(adapter, "joueurs", []) or [])
            if not joueurs:
                rejected_count += 1
                continue

            for player in joueurs:
                try:
                    p_aim = analyze_aimbot(adapter, player).metrics or {}
                    p_wh = analyze_wallhack(adapter, player).metrics or {}
                    p_bhop = analyze_bhop(adapter, player).metrics or {}
                    vec = extraire_vecteur_features(p_aim, p_bhop, p_wh)
                except Exception as player_error:
                    print(f"[AVERTISSEMENT] Joueur {player} ignoré dans {match_id} : {player_error}")
                    continue

                if match_category == "with_cheater_present":
                    if player in cheaters_list:
                        label_val = 1
                        label_text = "verified_cheater"
                        label_conf = "high"
                    else:
                        label_val = -1
                        label_text = "unknown"
                        label_conf = "low"
                elif match_category == "no_cheater_present":
                    label_val = 0
                    label_text = "probable_non_cheater"
                    label_conf = "high"
                else:
                    label_val = -1
                    label_text = "unknown"
                    label_conf = "low"

                rec = {
                    "player_key": f"{match_id}_{player}",
                    "match_id": match_id,
                    "steamid": player,
                    "split": split,
                    "match_category": match_category,
                    "label": label_val,
                    "label_text": label_text,
                    "label_confidence": label_conf,
                    "usable_for_training": label_val in [0, 1]
                }
                # `extraire_vecteur_features` retourne un vecteur numpy : on le
                # projette explicitement sur le schéma canonique des features.
                rec.update({nom: float(val) for nom, val in zip(NOMS_FEATURES, np.asarray(vec).ravel())})
                records.append(rec)
        except Exception as e:
            error_count += 1
            print(f"[EXTRACTION] Match {match_id} en erreur : {type(e).__name__} - {e}")
            if os.environ.get("CS2CD_TRAIN_DEBUG"):
                import traceback
                traceback.print_exc()

    df_features = pd.DataFrame(records)
    if df_features.empty:
        raise RuntimeError(
            "Aucune caractéristique extraite : le manifeste, les chemins de données ou le schéma "
            "CS2CD sont invalides. Vérifier le manifest et le dataset avant l'entraînement."
        )
    
    # P0-7: Enforce dataset coverage thresholds
    total_failures = rejected_count + error_count
    failure_rate = total_failures / total_matches if total_matches > 0 else 1.0
    n_players = len(records)
    print(f"[EXTRACTION] Matches lus: {total_matches}, Rejetés: {rejected_count}, Erreurs: {error_count}, Profils extraits: {n_players}")
    if failure_rate > 0.3:  # using 30% max failure tolerance since datasets can be messy
        raise RuntimeError(f"Taux d'échec d'extraction trop élevé ({failure_rate:.1%}). Seuil max = 30%.")

    cache_dir = os.path.dirname(cache_path)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    df_features.to_csv(cache_path, index=False, encoding="utf-8")
    
    with open(cache_meta_path, 'w', encoding='utf-8') as f:
        json.dump({"hash": current_hash, "schema_version": FEATURE_SCHEMA_VERSION}, f)
        
    print(f"[CACHE] Features sauvegardées dans : {cache_path} ({len(df_features)} lignes)")
    return df_features

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
    df_supervised = df[df["usable_for_training"].astype(bool)].copy()

    train_df = df_supervised[df_supervised["split"] == "train"]
    val_df = df_supervised[df_supervised["split"] == "validation"]
    test_df = df_supervised[df_supervised["split"] == "test"]

    print("\n[SPLIT SUPERVISÉ]")
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
    # Seuil suspect volontairement plus bas que le seuil haut : le premier déclenche
    # l'étiquette SUSPECT, le second l'étiquette de suspicion élevée.
    threshold_suspect = round(min(0.40, max(0.05, float(optimal_threshold) - 0.10)), 2)
    bundle = {
        "scaler": scaler,
        "modele": rf,
        "isolation_forest": iso,
        "noms_features": NOMS_FEATURES,
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_schema_hash": FEATURE_SCHEMA_HASH,
        "dataset_name": "CS2CD",
        "dataset_revision": "CS2CD-Zenodo-2024",
        "model_version": MODEL_VERSION,
        "git_commit": "unknown", # Could be fetched via subprocess if needed
        "seed": 42,
        "dataset_version": "v1.0-anonymized",
        "training_date": datetime.now().isoformat(),
        "train_count": len(X_train),
        "validation_count": len(X_val),
        "test_count": len(X_test),
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
