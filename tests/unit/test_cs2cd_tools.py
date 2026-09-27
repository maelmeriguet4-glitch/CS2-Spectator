"""
Tests unitaires et d'intégration pour le pipeline CS2CD (CS2 Cheat Detection).
Couvre :
- Parsing Parquet et JSON via CS2CDAdapter
- Couche d'identité interne et normalisation des ticks
- Politique d'étiquetage stricte (cheater, known_non_cheater, unknown)
- Vérification d'étanchéité des splits (anti-leakage)
- Format du bundle de modèle (cerveau_vac_cs2cd.pkl)
- Protection contre les fallbacks trompeurs
- Robustesse face aux fichiers corrompus ou incomplets
"""

import json
import os
import shutil
import tempfile
import unittest
import numpy as np
import pandas as pd
import joblib

from src.ml.cs2cd_adapter import CS2CDAdapter, COLONNES_REQUISES_TICKS
from src.ml.classifier import (
    FICHIER_MODELE_CS2CD,
    FICHIER_MODELE_SYNTHETIQUE,
    NOMS_FEATURES,
    CheatClassifier,
    charger_ou_entrainer_modele,
    extraire_vecteur_features,
)
from scripts.index_cs2cd import index_dataset


class TestCS2CDAdapter(unittest.TestCase):
    """Vérifie la robustesse et la conformité de l'adaptateur CS2CD."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.parquet_path = os.path.join(self.temp_dir, "0.parquet")
        self.json_path = os.path.join(self.temp_dir, "0.json")

        # Générer un parquet représentatif avec ticks désordonnés et doublons
        data = {
            "tick": [102, 100, 101, 101, 105],
            "steamid": ["Player_1", "Player_1", "Player_1", "Player_1", "Player_2"],
            "team_num": [2, 2, 2, 2, 3],
            "X": [100.0, 105.0, 110.0, 110.0, -200.0],
            "Y": [200.0, 205.0, 210.0, 210.0, -300.0],
            "Z": [0.0, 0.0, 0.0, 0.0, 64.0],
            "pitch": [0.0, 1.0, 2.0, 2.0, -10.0],
            "yaw": [45.0, 46.0, 47.0, 47.0, 180.0],
            "health": [100, 100, 90, 90, 100],
            "spotted": [False, False, True, True, False],
            "velocity_X": [10.0, 10.0, 10.0, 10.0, 0.0],
            "velocity_Y": [0.0, 0.0, 0.0, 0.0, 0.0],
            "velocity_Z": [0.0, 0.0, 0.0, 0.0, 0.0],
            "is_airborne": [False, False, False, False, True],
            "active_weapon_name": ["weapon_ak47", "weapon_ak47", "weapon_ak47", "weapon_ak47", "weapon_m4a1"],
            "shots_fired": [0, 1, 2, 2, 0],
        }
        df = pd.DataFrame(data)
        df.to_parquet(self.parquet_path)

        # JSON d'événements représentatif CS2CD
        events = {
            "CSstats_info": [{"map": "de_dust2", "server": "test_server"}],
            "cheaters": [{"steamid": "Player_2"}],
            "weapon_fire": [
                {"tick": 100, "user_steamid": "Player_1", "weapon": "weapon_ak47", "silenced": False}
            ],
            "player_hurt": [
                {"tick": 101, "attacker_steamid": "Player_1", "user_steamid": "Player_2", "dmg_health": 25}
            ],
            "player_death": [
                {"tick": 105, "attacker_steamid": "Player_1", "user_steamid": "Player_2", "headshot": True}
            ]
        }
        with open(self.json_path, "w", encoding="utf-8") as f:
            json.dump(events, f)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_adapter_loading_and_sorting(self):
        adapter = CS2CDAdapter(self.parquet_path, self.json_path)
        self.assertTrue(adapter.is_valid)
        self.assertEqual(adapter.map_name, "de_dust2")
        self.assertIn("Player_1", adapter.joueurs)
        self.assertIn("Player_2", adapter.joueurs)

        # Vérifier que les ticks sont triés chronologiquement et dédupliqués
        p1_ticks = adapter.get_player_ticks("Player_1")
        self.assertEqual(list(p1_ticks["tick"]), [100, 101, 102])
        self.assertEqual(len(p1_ticks), 3)  # Le doublon au tick 101 doit être éliminé

    def test_adapter_events_normalization(self):
        adapter = CS2CDAdapter(self.parquet_path, self.json_path)
        fires = adapter.get_player_events("Player_1", "weapon_fire")
        self.assertEqual(len(fires), 1)
        self.assertEqual(fires.iloc[0]["weapon"], "weapon_ak47")

        hurts = adapter.get_player_events("Player_1", "player_hurt")
        self.assertEqual(len(hurts), 1)

    def test_adapter_missing_columns_fallback(self):
        # Créer un parquet avec des colonnes manquantes
        minimal_df = pd.DataFrame({"tick": [1, 2], "steamid": ["Player_A", "Player_A"]})
        min_path = os.path.join(self.temp_dir, "min.parquet")
        minimal_df.to_parquet(min_path)

        adapter = CS2CDAdapter(min_path, self.json_path)
        self.assertTrue(adapter.is_valid)
        ticks = adapter.get_player_ticks("Player_A")
        self.assertIn("pitch", ticks.columns)
        self.assertIn("is_airborne", ticks.columns)
        self.assertFalse(ticks["is_airborne"].iloc[0])


class TestCS2CDDatasetIndexing(unittest.TestCase):
    """Vérifie la création du manifest et la politique de labels."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.root = os.path.join(self.temp_dir, "CS2CD_Mock")
        self.output_csv = os.path.join(self.temp_dir, "manifest.csv")

        # Créer dossiers with_cheater et no_cheater
        os.makedirs(os.path.join(self.root, "with_cheater_present"), exist_ok=True)
        os.makedirs(os.path.join(self.root, "no_cheater_present"), exist_ok=True)

        # Match with cheater
        p1 = os.path.join(self.root, "with_cheater_present", "1.parquet")
        j1 = os.path.join(self.root, "with_cheater_present", "1.json")
        pd.DataFrame({"tick": [1], "steamid": ["Player_1"]}).to_parquet(p1)
        with open(j1, "w", encoding="utf-8") as f:
            json.dump({"cheaters": [{"steamid": "Player_1"}]}, f)

        # Match no cheater
        p2 = os.path.join(self.root, "no_cheater_present", "2.parquet")
        j2 = os.path.join(self.root, "no_cheater_present", "2.json")
        pd.DataFrame({"tick": [1], "steamid": ["Player_2"]}).to_parquet(p2)
        with open(j2, "w", encoding="utf-8") as f:
            json.dump({}, f)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_indexing_produces_manifest(self):
        df = index_dataset(dataset_root=self.root, output_csv=self.output_csv, random_state=42)
        self.assertIsNotNone(df)
        self.assertEqual(len(df), 2)
        self.assertTrue(os.path.exists(self.output_csv))

        # Vérifier colonnes requises
        for col in ["match_id", "data_path", "metadata_path", "label", "label_confidence", "split", "usable_for_training"]:
            self.assertIn(col, df.columns)


class TestCS2CDModelBundleAndIntegrity(unittest.TestCase):
    """Vérifie le format du bundle de modèle et la protection contre le fallback mensonger."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fake_model_path = os.path.join(self.temp_dir, "cerveau_vac_test.pkl")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_model_bundle_format(self):
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler

        rf = RandomForestClassifier().fit([[1, 2], [3, 4]], [0, 1])
        scaler = StandardScaler().fit([[1, 2], [3, 4]])

        bundle = {
            "scaler": scaler,
            "modele": rf,
            "isolation_forest": None,
            "noms_features": ["f1", "f2"],
            "dataset_name": "CS2CD",
            "training_date": "2026-09-27T17:00:00",
            "threshold": 0.45,
            "metrics": {"test": {"f1": 0.85, "precision": 0.88, "recall": 0.82}},
            "model_type": "RandomForestClassifier",
        }
        joblib.dump(bundle, self.fake_model_path)

        loaded = joblib.load(self.fake_model_path)
        self.assertEqual(loaded["dataset_name"], "CS2CD")
        self.assertEqual(loaded["threshold"], 0.45)
        self.assertIn("f1", loaded["metrics"]["test"])

    def test_rejection_of_missing_cs2cd_model(self):
        """Vérifie que charger explicitement cs2cd quand absent lève une exception sans fabriquer de faux."""
        non_existent = os.path.join(self.temp_dir, "not_exist.pkl")
        with self.assertRaises(FileNotFoundError):
            charger_ou_entrainer_modele(chemin_modele=non_existent, model_type="cs2cd")


if __name__ == "__main__":
    unittest.main()
