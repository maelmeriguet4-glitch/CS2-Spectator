#!/usr/bin/env python3
"""
CS2 Spectator - Indexation du dataset CS2CD
Génère le manifest CSV répertoriant les matches sans copier les fichiers volumineux.
"""

import argparse
import glob
import json
import os
import sys
import pandas as pd
from sklearn.model_selection import train_test_split

DEFAULT_DATASET_ROOT = r"C:\Users\pc\CS2CD"
DEFAULT_OUTPUT_CSV = os.path.join("data", "anti_cheat_dataset.csv")
EXAMPLE_OUTPUT_CSV = os.path.join("data", "anti_cheat_dataset.example.csv")


def index_dataset(dataset_root=DEFAULT_DATASET_ROOT, output_csv=DEFAULT_OUTPUT_CSV, sample_size=None, random_state=42):
    """
    Scanne le dossier du dataset CS2CD et produit un manifest CSV structuré.
    """
    print(f"[INDEX] Racine du dataset: {dataset_root}")
    if not os.path.exists(dataset_root):
        print(f"[ERREUR] Le dossier {dataset_root} n'existe pas.", file=sys.stderr)
        return None

    records = []
    classes = ["with_cheater_present", "no_cheater_present"]
    stats = {
        "total_scanned": 0,
        "valid_matches": 0,
        "missing_json": 0,
        "corrupt_json": 0,
        "with_cheater": 0,
        "no_cheater": 0,
        "total_cheater_ids": 0,
    }

    for label in classes:
        folder_path = os.path.join(dataset_root, label)
        if not os.path.exists(folder_path):
            print(f"[AVERTISSEMENT] Dossier de classe introuvable: {folder_path}")
            continue

        parquet_files = sorted(glob.glob(os.path.join(folder_path, "*.parquet")))
        for p_file in parquet_files:
            stats["total_scanned"] += 1
            base_name = os.path.basename(p_file).replace(".parquet", "")
            j_file = os.path.join(folder_path, f"{base_name}.json")

            if not os.path.exists(j_file):
                stats["missing_json"] += 1
                continue

            cheaters = []
            is_corrupt = False
            try:
                with open(j_file, "r", encoding="utf-8") as f:
                    j_data = json.load(f)
                    if label == "with_cheater_present":
                        raw_cheaters = j_data.get("cheaters", [])
                        if isinstance(raw_cheaters, list):
                            for c in raw_cheaters:
                                if isinstance(c, dict) and "steamid" in c:
                                    cheaters.append(str(c["steamid"]).strip())
                                elif isinstance(c, str):
                                    cheaters.append(c.strip())
            except Exception as e:
                stats["corrupt_json"] += 1
                is_corrupt = True
                print(f"[AVERTISSEMENT] JSON corrompu {j_file}: {e}")

            if is_corrupt:
                continue

            stats["valid_matches"] += 1
            if label == "with_cheater_present":
                stats["with_cheater"] += 1
                stats["total_cheater_ids"] += len(cheaters)
                label_conf = "high" if cheaters else "uncertain"
                label_src = "cs2cd_vac_verified"
            else:
                stats["no_cheater"] += 1
                label_conf = "medium"  # 97.2% precision selon le papier CS2CD
                label_src = "cs2cd_unverified_no_vac"

            records.append({
                "match_id": f"{label}_{base_name}",
                "match_category": label,
                "data_path": p_file,
                "metadata_path": j_file,
                "label": label,
                "label_confidence": label_conf,
                "label_source": label_src,
                "cheaters": ",".join(sorted(list(set(cheaters)))),
                "num_cheaters": len(set(cheaters)),
                "usable_for_training": True,
            })

    if not records:
        print("[ERREUR] Aucun match valide trouvé dans le dataset.", file=sys.stderr)
        return None

    df = pd.DataFrame(records)

    # Échantillonnage déterministe si demandé
    if sample_size and sample_size < len(df):
        print(f"[INDEX] Échantillonnage équilibré de {sample_size} matches (seed={random_state})...")
        df_with = df[df["label"] == "with_cheater_present"]
        df_no = df[df["label"] == "no_cheater_present"]

        sample_w = min(sample_size // 2, len(df_with))
        sample_n = min(sample_size - sample_w, len(df_no))

        sample_with = df_with.sample(n=sample_w, random_state=random_state)
        sample_no = df_no.sample(n=sample_n, random_state=random_state)

        df = pd.concat([sample_with, sample_no], ignore_index=True)

    # Split Train (70%) / Validation (15%) / Test (15%) par match
    if len(df) < 3:
        train_df = df.copy()
        val_df = pd.DataFrame(columns=df.columns)
        test_df = pd.DataFrame(columns=df.columns)
    else:
        # Vérifier si la stratification est possible (nécessite au moins 2 membres par classe)
        can_stratify = False
        if len(df) >= 6:
            min_class_count = df["label"].value_counts().min()
            can_stratify = (min_class_count >= 2)

        strat_first = df["label"] if can_stratify else None
        train_df, temp_df = train_test_split(
            df, test_size=0.30, random_state=random_state, stratify=strat_first
        )

        strat_second = temp_df["label"] if (can_stratify and temp_df["label"].value_counts().min() >= 2) else None
        val_df, test_df = train_test_split(
            temp_df, test_size=0.50, random_state=random_state, stratify=strat_second
        )

    train_df = train_df.copy()
    val_df = val_df.copy()
    test_df = test_df.copy()

    train_df["split"] = "train"
    val_df["split"] = "validation"
    test_df["split"] = "test"

    final_df = pd.concat([train_df, val_df, test_df], ignore_index=True)
    final_df = final_df.sort_values("match_id").reset_index(drop=True)

    # Création du dossier cible si nécessaire
    out_dir = os.path.dirname(output_csv)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    final_df.to_csv(output_csv, index=False, encoding="utf-8")
    print(f"[INDEX] Manifeste enregistré: {output_csv} ({len(final_df)} matches)")

    # Créer un exemple anonymisé/relatif pour Git (sans exposer les chemins réels)
    create_example_manifest(final_df, EXAMPLE_OUTPUT_CSV)

    # Affichage des statistiques
    print("=" * 60)
    print("STATISTIQUES D'INDEXATION CS2CD")
    print("=" * 60)
    print(f"Total fichiers scannés : {stats['total_scanned']}")
    print(f"Matches valides        : {stats['valid_matches']}")
    print(f"JSON manquants         : {stats['missing_json']}")
    print(f"JSON corrompus         : {stats['corrupt_json']}")
    print(f"Matches avec tricheurs : {stats['with_cheater']}")
    print(f"Matches sans tricheur  : {stats['no_cheater']}")
    print(f"Total tricheurs uniques: {stats['total_cheater_ids']}")
    print("-" * 60)
    print(f"Split Train      : {len(train_df)} matches")
    print(f"Split Validation : {len(val_df)} matches")
    print(f"Split Test       : {len(test_df)} matches")
    print("=" * 60)

    return final_df


def create_example_manifest(df, output_example_csv):
    """Crée un fichier d'exemple pour Git avec des chemins anonymisés."""
    try:
        example_df = df.head(10).copy()
        example_df["data_path"] = example_df["match_id"].apply(lambda m: f"data/raw_examples/{m}.parquet")
        example_df["metadata_path"] = example_df["match_id"].apply(lambda m: f"data/raw_examples/{m}.json")
        out_dir = os.path.dirname(output_example_csv)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        example_df.to_csv(output_example_csv, index=False, encoding="utf-8")
        print(f"[INDEX] Exemple public généré: {output_example_csv}")
    except Exception as e:
        print(f"[AVERTISSEMENT] Impossible de créer {output_example_csv}: {e}")


def main():
    parser = argparse.ArgumentParser(description="Indexer le dataset local CS2CD pour CS2 Spectator.")
    parser.add_argument("--dataset-root", default=DEFAULT_DATASET_ROOT, help="Chemin vers la racine de CS2CD")
    parser.add_argument("--output", default=DEFAULT_OUTPUT_CSV, help="Chemin du CSV de manifest de sortie")
    parser.add_argument("--sample-size", type=int, default=None, help="Nombre max de matches à inclure (équilibré)")
    parser.add_argument("--random-state", type=int, default=42, help="Graine aléatoire pour reproductibilité")

    args = parser.parse_args()
    res = index_dataset(
        dataset_root=args.dataset_root,
        output_csv=args.output,
        sample_size=args.sample_size,
        random_state=args.random_state
    )
    if res is None:
        sys.exit(1)


if __name__ == "__main__":
    main()
