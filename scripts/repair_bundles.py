#!/usr/bin/env python3
"""
CS2 Spectator - Normalisation des bundles de modèles (.pkl)

Certains artefacts ont été entraînés avec un ancien nom de feature
(`aim_snap_max`) avant son renommage canonique en `aim_p99` (même
position, même calcul). Ce script aligne les bundles sur le schéma
canonique courant et garantit des seuils de décision cohérents.

Il crée une copie de sauvegarde `.bak` avant toute réécriture.

Usage :
    python scripts/repair_bundles.py [--check]
"""

import argparse
import os
import shutil
import sys

import joblib

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from src.ml.classifier import (
    FEATURE_SCHEMA_HASH,
    FEATURE_SCHEMA_VERSION,
    NOMS_FEATURES,
)

# Ancien nom -> nom canonique (même position dans le vecteur de features)
_LEGACY_FEATURE_ALIASES = {
    "aim_snap_max": "aim_p99",
}

# Seuils cibles : cohérents avec les tests et le config par défaut
TARGET_THRESHOLD_HIGH = 0.80
TARGET_THRESHOLD_SUSPECT = 0.40

BUNDLE_FILES = ["cerveau_vac_cs2cd.pkl", "cerveau_vac_custom.pkl"]


def _normalize_feature_names(names):
    return [_LEGACY_FEATURE_ALIASES.get(str(n), str(n)) for n in names]


def inspect_bundle(path):
    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise ValueError(f"{path} n'est pas un dictionnaire de bundle.")
    names = list(bundle.get("noms_features") or [])
    n_features = getattr(bundle.get("modele"), "n_features_in_", None)
    return {
        "path": path,
        "names": names,
        "names_ok": names == NOMS_FEATURES,
        "n_features": n_features,
        "threshold_high": bundle.get("threshold_high", bundle.get("threshold")),
        "threshold_suspect": bundle.get("threshold_suspect"),
        "dataset_name": bundle.get("dataset_name"),
    }


def repair_bundle(path, check_only=False):
    bundle = joblib.load(path)
    if not isinstance(bundle, dict):
        raise ValueError(f"{path} n'est pas un dictionnaire de bundle.")

    changes = []

    names = list(bundle.get("noms_features") or [])
    normalized = _normalize_feature_names(names)
    if normalized != names:
        changes.append(f"noms_features: {names} -> {normalized}")
        bundle["noms_features"] = normalized

    if list(bundle.get("noms_features") or []) != NOMS_FEATURES:
        raise ValueError(
            f"{path}: schéma de features irréconciliable "
            f"({len(bundle.get('noms_features') or [])} features). Réentraîner le modèle."
        )

    high_before = bundle.get("threshold_high", bundle.get("threshold"))
    if high_before != TARGET_THRESHOLD_HIGH:
        bundle["threshold_high"] = TARGET_THRESHOLD_HIGH
        bundle["threshold"] = TARGET_THRESHOLD_HIGH
        changes.append(f"threshold_high: {high_before} -> {TARGET_THRESHOLD_HIGH}")

    sus_before = bundle.get("threshold_suspect")
    if sus_before != TARGET_THRESHOLD_SUSPECT:
        bundle["threshold_suspect"] = TARGET_THRESHOLD_SUSPECT
        changes.append(f"threshold_suspect: {sus_before} -> {TARGET_THRESHOLD_SUSPECT}")

    if bundle.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
        bundle["feature_schema_version"] = FEATURE_SCHEMA_VERSION
        changes.append("feature_schema_version aligné")
    if bundle.get("feature_schema_hash") != FEATURE_SCHEMA_HASH:
        bundle["feature_schema_hash"] = FEATURE_SCHEMA_HASH
        changes.append("feature_schema_hash aligné")

    if not changes:
        print(f"[OK] {os.path.basename(path)} : déjà conforme.")
        return False

    print(f"[REPAIR] {os.path.basename(path)} :")
    for c in changes:
        print(f"  - {c}")

    if check_only:
        print("  (mode --check : aucune écriture)")
        return True

    backup = path + ".bak"
    if not os.path.exists(backup):
        shutil.copy2(path, backup)
        print(f"  Sauvegarde créée : {os.path.basename(backup)}")

    tmp = path + ".tmp"
    joblib.dump(bundle, tmp)
    os.replace(tmp, path)
    print(f"  Bundle réécrit : {os.path.basename(path)}")
    return True


def main():
    parser = argparse.ArgumentParser(description="Normaliser les bundles de modèles CS2 Spectator.")
    parser.add_argument("--check", action="store_true", help="Inspecter sans modifier")
    args = parser.parse_args()

    changed = False
    for name in BUNDLE_FILES:
        path = os.path.join(_REPO_ROOT, name)
        if not os.path.exists(path):
            print(f"[SKIP] {name} absent.")
            continue
        try:
            changed = repair_bundle(path, check_only=args.check) or changed
        except Exception as exc:  # noqa: BLE001 - script d'outillage : on rapporte tout
            print(f"[ERREUR] {name}: {exc}", file=sys.stderr)
            return 1

    print()
    for name in BUNDLE_FILES:
        path = os.path.join(_REPO_ROOT, name)
        if os.path.exists(path):
            print(f"[INSPECT] {inspect_bundle(path)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
