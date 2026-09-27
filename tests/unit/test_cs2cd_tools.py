import json
import tempfile
import unittest
from pathlib import Path

from scripts.index_cs2cd import index_dataset


class TestCS2CDIndexing(unittest.TestCase):
    def test_index_dataset_writes_manifest_and_creates_output_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "dataset"
            output = Path(temp_dir) / "generated" / "manifest.csv"

            for label in ("with_cheater_present", "no_cheater_present"):
                label_dir = root / label
                label_dir.mkdir(parents=True)
                for index in range(8):
                    (label_dir / f"match_{index}.parquet").touch()
                    metadata = {"cheaters": [{"steamid": "player_1"}]} if label == "with_cheater_present" else {}
                    (label_dir / f"match_{index}.json").write_text(
                        json.dumps(metadata), encoding="utf-8"
                    )

            result = index_dataset(root, output)

            self.assertEqual(result, output.resolve())
            self.assertTrue(output.is_file())
            rows = output.read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(rows), 17)
            self.assertIn("parquet_path", rows[0])

    def test_index_dataset_reports_missing_pairs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError):
                index_dataset(Path(temp_dir), Path(temp_dir) / "manifest.csv")


if __name__ == "__main__":
    unittest.main()
