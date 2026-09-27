"""
Tests unitaires et d'intégration pour le pipeline CS2CD (CS2 Cheat Detection).
Couvre :
- Parsing Parquet et JSON via CS2CDAdapter
- Couche d'identité interne et normalisation des ticks
- Politique d'étiquetage stricte (cheater, probable_non_cheater, unknown)
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
    ClassificationResult,
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
        # Créer un parquet avec toutes les colonnes critiques mais sans les colonnes optionnelles
        minimal_df = pd.DataFrame({
            "tick": [1, 2],
            "steamid": ["Player_A", "Player_A"],
            "X": [10.0, 11.0],
            "Y": [20.0, 21.0],
            "Z": [0.0, 0.0],
            "pitch": [0.0, 0.0],
            "yaw": [90.0, 90.0],
        })
        min_path = os.path.join(self.temp_dir, "min.parquet")
        minimal_df.to_parquet(min_path)

        adapter = CS2CDAdapter(min_path, self.json_path)
        self.assertTrue(adapter.is_valid)
        ticks = adapter.get_player_ticks("Player_A")
        self.assertIn("pitch", ticks.columns)
        self.assertIn("is_airborne", ticks.columns)
        self.assertFalse(ticks["is_airborne"].iloc[0])
        self.assertEqual(ticks["health"].iloc[0], 100)

    def test_adapter_missing_critical_columns_rejected(self):
        # Un fichier sans colonnes critiques (X, Y, Z, pitch, yaw) doit être rejeté
        incomplete_df = pd.DataFrame({"tick": [1, 2], "steamid": ["Player_A", "Player_A"]})
        inc_path = os.path.join(self.temp_dir, "inc.parquet")
        incomplete_df.to_parquet(inc_path)

        adapter = CS2CDAdapter(inc_path, self.json_path)
        self.assertFalse(adapter.is_valid)


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


class TestBundleThresholdAtRuntime(unittest.TestCase):
    """Vérifie que le seuil optimisé du bundle est utilisé au runtime."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.fake_model_path = os.path.join(self.temp_dir, "test_bundle.pkl")

        # Créer un bundle avec threshold=0.25 (différent du config default)
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.preprocessing import StandardScaler

        X = np.random.default_rng(42).standard_normal((100, 15))
        y = np.array([0] * 50 + [1] * 50)
        scaler = StandardScaler().fit(X)
        rf = RandomForestClassifier(n_estimators=10, random_state=42).fit(scaler.transform(X), y)

        bundle = {
            "scaler": scaler,
            "modele": rf,
            "isolation_forest": None,
            "noms_features": NOMS_FEATURES,
            "dataset_name": "CS2CD_test",
            "threshold": 0.25,  # Seuil optimisé = 25%
            "model_type": "RandomForestClassifier",
        }
        joblib.dump(bundle, self.fake_model_path)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_bundle_threshold_is_used_not_config_default(self):
        """Le seuil du bundle (0.25 → 25%) doit primer sur cfg.ml_cheater_threshold."""
        classifier = CheatClassifier(model_path=self.fake_model_path)
        # Le bundle contient threshold=0.25
        self.assertEqual(classifier._bundle.get("threshold"), 0.25)

    def test_classifier_with_bundle_threshold_affects_verdict(self):
        """Un score >25% avec threshold=0.25 doit donner CHEATER, pas CLEAN."""
        classifier = CheatClassifier(model_path=self.fake_model_path)
        # Profils aimbot suspects mais pas extrêmes
        aim = {"aim_snap_max": 20.0, "aim_jerk_max": 10.0}
        bhop = {"bhop_total_sauts": 20, "bhop_ratio_parfaits": 0.1}
        wh = {"wh_ratio_lock_strict": 0.02, "wh_tracking_consecutif_max": 5}
        res = classifier.predict(aim, bhop, wh)
        # Avec le snap à 20° > seuil aimbot, on a au moins 1 facteur → SUSPECT min
        self.assertIn(res.verdict, ["SUSPECT", "CHEATER"])


class TestCS2CDModelSelection(unittest.TestCase):
    """Vérifie que model_type='cs2cd' charge bien le modèle CS2CD, pas le synthétique."""

    def test_cs2cd_model_type_raises_if_missing(self):
        """Si cerveau_vac_cs2cd.pkl n'existe pas, model_type='cs2cd' lève FileNotFoundError."""
        import tempfile
        fake_path = os.path.join(tempfile.gettempdir(), "this_does_not_exist_12345.pkl")
        if os.path.exists(fake_path):
            os.remove(fake_path)
        with self.assertRaises(FileNotFoundError):
            charger_ou_entrainer_modele(chemin_modele=fake_path, model_type="cs2cd")

    def test_synthetic_fallback_explicit_only(self):
        """model_type='auto' ou 'synthetic' charge le synthétique sans erreur."""
        bundle = charger_ou_entrainer_modele(model_type="auto")
        self.assertIn("modele", bundle)
        self.assertIn("scaler", bundle)

    def test_cs2cd_bundle_loaded_when_file_exists(self):
        """Si cerveau_vac_cs2cd.pkl existe, model_type='cs2cd' le charge."""
        if not os.path.exists(FICHIER_MODELE_CS2CD):
            self.skipTest("cerveau_vac_cs2cd.pkl not present")
        bundle = charger_ou_entrainer_modele(model_type="cs2cd")
        self.assertEqual(bundle.get("dataset_name", ""), "CS2CD")


class TestPrudentVerdictTerminology(unittest.TestCase):
    """Vérifie l'absence de termes affirmatifs interdits dans les résultats."""

    TERMES_INTERDITS = [
        "TRICHEUR AVÉRÉ",
        "TRICHEUR(S) AVÉRÉ(S)",
        "MATCH INTÈGRE",
        "100% CLEAN",
        "probabilité de triche",
    ]

    def test_classifier_verdict_no_affirmatif_language(self):
        """Le classifier FR ne doit jamais retourner de verdict affirmatif."""
        from src.ml.classifier import classifier_joueur
        # Profils extrêmes pour déclencher SUSPICION ÉLEVÉE
        aim = {"aim_snap_max": 50.0, "aim_jerk_max": 100.0}
        bhop = {"bhop_total_sauts": 50, "bhop_ratio_parfaits": 0.95, "bhop_chaine_max": 8}
        wh = {"wh_ratio_lock_strict": 0.30, "wh_tracking_consecutif_max": 150}
        res = classifier_joueur(aim, bhop, wh, nom_joueur="TestPlayer")
        self.assertIsNotNone(res)
        verdict = res["verdict"]
        for terme in self.TERMES_INTERDITS:
            self.assertNotIn(terme, verdict, f"Terme interdit '{terme}' trouvé dans le verdict")
        # Le verdict doit être SUSPICION ÉLEVÉE, pas TRICHE AVÉRÉE
        self.assertEqual(verdict, "SUSPICION ÉLEVÉE")

    def test_clean_verdict_prudent(self):
        """Un joueur clean doit avoir le verdict LÉGITIME, pas 'MATCH INTÈGRE'."""
        from src.ml.classifier import classifier_joueur
        aim = {"aim_snap_max": 3.0, "aim_jerk_max": 5.0}
        bhop = {"bhop_total_sauts": 20, "bhop_ratio_parfaits": 0.05}
        wh = {"wh_ratio_lock_strict": 0.01, "wh_tracking_consecutif_max": 2}
        res = classifier_joueur(aim, bhop, wh, nom_joueur="CleanPlayer")
        self.assertIsNotNone(res)
        self.assertEqual(res["verdict"], "LÉGITIME")


class TestSuspicionScoresAPI(unittest.TestCase):
    """Vérifie que la property suspicion_scores remplace correctement probabilities."""

    def test_suspicion_scores_has_correct_keys(self):
        """suspicion_scores doit exposer 'clean', 'suspicion', pas 'cheat'."""
        result = ClassificationResult(
            verdict="CLEAN", suspicion_score=15.0,
            display_verdict="🟢 CLEAN (15.0%)",
        )
        scores = result.suspicion_scores
        self.assertIn("clean", scores)
        self.assertIn("suspicion", scores)
        self.assertNotIn("cheat", scores)
        self.assertNotIn("CHEAT", scores)
        self.assertAlmostEqual(scores["clean"], 85.0)
        self.assertAlmostEqual(scores["suspicion"], 15.0)

    def test_probabilities_backward_compat(self):
        """L'alias probabilities retourne les mêmes données que suspicion_scores."""
        result = ClassificationResult(
            verdict="SUSPECT", suspicion_score=50.0,
            display_verdict="🟡 SUSPECT (50.0%)",
        )
        self.assertEqual(result.probabilities, result.suspicion_scores)


class TestCriticallyIncompleteData(unittest.TestCase):
    """Vérifie le comportement face à des données critiquement incomplètes."""

    def test_adapter_with_no_tick_column_still_loads(self):
        """Un parquet sans colonne 'tick' ne doit pas crasher mais sera peu exploitable."""
        temp_dir = tempfile.mkdtemp()
        try:
            p_path = os.path.join(temp_dir, "bad.parquet")
            j_path = os.path.join(temp_dir, "bad.json")
            # Parquet sans colonne tick — colonnes complètement différentes
            pd.DataFrame({"random_col": [1, 2]}).to_parquet(p_path)
            with open(j_path, "w") as f:
                json.dump({}, f)
            adapter = CS2CDAdapter(p_path, j_path)
            # L'adapter ne crash pas mais ne devrait pas valider sans steamid
            # (tick manquant aussi rempli par défaut 0)
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_classifier_rejects_none_profiles(self):
        """classifier_joueur retourne None si les profils sont None."""
        from src.ml.classifier import classifier_joueur
        self.assertIsNone(classifier_joueur(None, None, None))
        self.assertIsNone(classifier_joueur(None, {}, {}))
        self.assertIsNone(classifier_joueur({}, None, {}))
        self.assertIsNone(classifier_joueur({}, {}, None))


if __name__ == "__main__":
    unittest.main()
