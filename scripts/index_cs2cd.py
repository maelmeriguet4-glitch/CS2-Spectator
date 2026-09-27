import argparse
import glob
import json
import os
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

REPO_ROOT = Path(__file__).resolve().parents[1]
DATASET_ROOT = Path(os.environ.get("CS2CD_DATASET_ROOT", Path.home() / "CS2CD"))
OUTPUT_CSV = REPO_ROOT / "data" / "anti_cheat_dataset.csv"


def index_dataset(dataset_root=DATASET_ROOT, output_csv=OUTPUT_CSV, sample_size=None):
    dataset_root = Path(dataset_root).expanduser().resolve()
    output_csv = Path(output_csv).expanduser().resolve()
    records = []

    # Process both classes
    classes = ["with_cheater_present", "no_cheater_present"]
    for label in classes:
        folder_path = dataset_root / label
        if not os.path.exists(folder_path):
            continue

        parquet_files = glob.glob(str(folder_path / "*.parquet"))
        for p_file in parquet_files:
            base_name = Path(p_file).stem
            j_file = folder_path / f"{base_name}.json"

            if os.path.exists(j_file):
                cheaters = []
                if label == "with_cheater_present":
                    try:
                        with open(j_file, "r", encoding="utf-8") as f:
                            j_data = json.load(f)
                            raw_cheaters = j_data.get("cheaters", [])
                            cheaters = [c.get("steamid") for c in raw_cheaters if isinstance(c, dict) and "steamid" in c]
                    except Exception as e:
                        print(f"Warning: error reading {j_file}: {e}")

                records.append({
                    "match_id": f"{label}_{base_name}",
                    "parquet_path": str(Path(p_file).resolve()),
                    "json_path": str(j_file.resolve()),
                    "label": label,
                    "cheaters": ",".join(map(str, cheaters)),
                    "label_confidence": "high" if cheaters else ("high" if label == "no_cheater_present" else "uncertain")
                })

    if not records:
        raise FileNotFoundError(
            f"No matching .parquet/.json pairs found under {dataset_root}. "
            "Expected with_cheater_present and no_cheater_present subfolders."
        )

    df = pd.DataFrame(records)

    if sample_size:
        if sample_size < 2:
            raise ValueError("sample_size must be at least 2.")
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

    try:
        train, temp = train_test_split(df, test_size=0.3, random_state=42, stratify=df['label'])
        val, test = train_test_split(temp, test_size=0.5, random_state=42, stratify=temp['label'])
    except ValueError as exc:
        raise ValueError(
            "The dataset needs enough matches in both classes for a stratified train/validation/test split."
        ) from exc

    train.loc[:, 'split'] = 'train'
    val.loc[:, 'split'] = 'validation'
    test.loc[:, 'split'] = 'test'

    final_df = pd.concat([train, val, test]).sort_values("match_id")
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    final_df.to_csv(output_csv, index=False)
    print(f"Manifest written to {output_csv} with {len(final_df)} matches.")
    return output_csv

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Index a local CS2CD dataset.")
    parser.add_argument(
        "--dataset-root",
        type=Path,
        default=DATASET_ROOT,
        help="Dataset directory containing with_cheater_present/ and no_cheater_present/ (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_CSV,
        help=f"Manifest output path (default: {OUTPUT_CSV})",
    )
    parser.add_argument("--sample-size", type=int, help="Optional balanced sample size.")
    args = parser.parse_args()
    index_dataset(args.dataset_root, args.output, args.sample_size)
