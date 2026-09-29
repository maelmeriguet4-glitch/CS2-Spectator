"""
Unit tests for Machine Learning Cheat Classifier and AntiCheatEngine Coordinator
using standard unittest.
"""

import unittest
from typing import List, Tuple

from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult
from src.ml.classifier import (
    FEATURE_NAMES,
    CheatClassifier,
    ClassificationResult,
    extract_feature_vector,
)
from tests.conftest import MODEL_PATH, TEST_DEMO_PATH, has_test_demo


class TestCheatClassifier(unittest.TestCase):
    """Tests for model loading, feature extraction, and ML inference."""

    def test_classifier_model_loading(self):
        classifier = CheatClassifier(model_path=MODEL_PATH)
        self.assertTrue(classifier.is_loaded)
        self.assertIsNotNone(classifier.scaler)
        self.assertIsNotNone(classifier.model)
        self.assertEqual(len(classifier.feature_names), 15)
        self.assertEqual(classifier.feature_names, FEATURE_NAMES)

    def test_feature_vector_extraction(self):
        aim = {"aim_vitesse_max": 15.0, "aim_p99": 4.5}
        bhop = {"bhop_total_sauts": 30, "bhop_ratio_parfaits": 0.1}
        wh = {"wh_ratio_lock_cache": 0.05}

        vec = extract_feature_vector(aim, bhop, wh)
        self.assertEqual(len(vec), 15)
        self.assertEqual(vec[0], 15.0)  # aim_vitesse_max
        self.assertEqual(vec[1], 4.5)   # aim_p99
        self.assertEqual(vec[6], 30.0)  # bhop_total_sauts
        self.assertEqual(vec[7], 0.1)   # bhop_ratio_parfaits
        self.assertEqual(vec[8], 50.0)  # bhop_variance_sol default
        self.assertEqual(vec[11], 0.05) # wh_ratio_lock_cache

    def test_clean_player_prediction(self):
        classifier = CheatClassifier()
        aim = {
            "aim_vitesse_max": 18.0,
            "aim_p99": 4.5,
            "aim_jerk_moyen": 0.15,
            "aim_jerk_max": 6.5,
            "aim_ratio_micro_ajustements": 5.0,
            "aim_variance_vitesse": 1.2,
        }
        bhop = {
            "bhop_total_sauts": 45,
            "bhop_ratio_parfaits": 0.12,
            "bhop_variance_sol": 20.0,
            "bhop_chaine_max": 1,
            "bhop_vitesse_moyenne": 140.0,
        }
        wh = {
            "wh_ratio_lock_cache": 0.06,
            "wh_ratio_lock_strict": 0.02,
            "wh_tracking_consecutif_max": 10,
            "wh_distance_moyenne_verrous": 1200.0,
        }

        res = classifier.predict(aim, bhop, wh)
        self.assertIsInstance(res, ClassificationResult)
        self.assertEqual(res.verdict, "CLEAN")
        self.assertIn("🟢", res.display_verdict)
        self.assertLess(res.suspicion_score, 40.0)
        self.assertEqual(len(res.critical_factors), 0)

    def test_suspect_player_one_critical_factor(self):
        classifier = CheatClassifier()
        aim = {"aim_p99": 22.5, "aim_jerk_max": 10.0}
        bhop = {"bhop_total_sauts": 20, "bhop_ratio_parfaits": 0.1}
        wh = {"wh_ratio_lock_strict": 0.02, "wh_tracking_consecutif_max": 10}

        res = classifier.predict(aim, bhop, wh)
        self.assertEqual(res.verdict, "SUSPECT")
        self.assertIn("🟡", res.display_verdict)
        self.assertGreaterEqual(res.suspicion_score, 40.0)
        self.assertLess(res.suspicion_score, 80.0)
        self.assertTrue(any("Snap instantané anormal" in f for f in res.violation_flags))
        self.assertTrue(any("[AIMBOT: Snap 22.5°/tick]" in p for p in res.pills))

    def test_cheater_player_multiple_critical_factors(self):
        classifier = CheatClassifier()
        aim = {"aim_p99": 34.0, "aim_jerk_max": 65.0}
        bhop = {"bhop_total_sauts": 25, "bhop_ratio_parfaits": 0.88, "bhop_chaine_max": 6}
        wh = {"wh_ratio_lock_strict": 0.22, "wh_tracking_consecutif_max": 90}

        res = classifier.predict(aim, bhop, wh)
        self.assertEqual(res.verdict, "CHEATER")
        self.assertIn("🔴", res.display_verdict)
        self.assertGreaterEqual(res.suspicion_score, 80.0)
        self.assertGreaterEqual(len(res.critical_factors), 2)

    def test_critical_factor_overrides(self):
        classifier = CheatClassifier()

        # Rule 1: Violent Snapbot
        res_snap = classifier.predict({"aim_p99": 25.0}, {}, {})
        self.assertTrue(any("[AIMBOT: Snap 25.0°/tick]" in p for p in res_snap.pills))

        # Rule 2: Inhuman Jerk
        res_jerk = classifier.predict({"aim_jerk_max": 48.0}, {}, {})
        self.assertTrue(any("[AIMBOT: Jerk 48.0]" in p for p in res_jerk.pills))

        # Rule 3: Scripted Bhop
        res_bhop = classifier.predict({}, {"bhop_ratio_parfaits": 0.75, "bhop_total_sauts": 20}, {})
        self.assertTrue(any("[BHOP: Script 75%]" in p for p in res_bhop.pills))

        # Rule 4: Inhuman Bhop Chain
        res_chain = classifier.predict({}, {"bhop_chaine_max": 5}, {})
        self.assertTrue(any("[BHOP: Chaîne x5]" in p for p in res_chain.pills))

        # Rule 5: Wallhack Excessive Alignment
        res_wh_align = classifier.predict({}, {}, {"wh_ratio_lock_strict": 0.18, "wh_tracking_consecutif_max": 85})
        self.assertTrue(any("[WALLHACK: 18.0% Lock Mur]" in p for p in res_wh_align.pills))

        # Rule 6: Wallhack Continuous Tracking
        res_wh_track = classifier.predict({}, {}, {"wh_tracking_consecutif_max": 195})
        self.assertTrue(any("[WALLHACK: Track 195 ticks]" in p for p in res_wh_track.pills))


class TestAntiCheatEngine(unittest.TestCase):
    """Tests for AntiCheatEngine orchestration and progress reporting."""

    def test_anticheat_engine_with_progress(self):
        if not has_test_demo():
            self.skipTest("demos/test.dem not found")

        engine = AntiCheatEngine()
        progress_log: List[Tuple[float, str]] = []

        def callback(pct: float, msg: str):
            progress_log.append((pct, msg))

        result = engine.analyze_demo(TEST_DEMO_PATH, progress_callback=callback)
        self.assertIsInstance(result, MatchAnalysisResult)
        self.assertEqual(result.map_name, "de_inferno")
        self.assertEqual(len(result.players), 10)
        self.assertGreater(result.total_ticks, 100000)
        self.assertGreater(result.duration_seconds, 0)
        self.assertIsInstance(result.global_verdict, str)

        self.assertGreaterEqual(len(progress_log), 5)
        self.assertEqual(progress_log[0][0], 0.05)
        self.assertEqual(progress_log[-1][0], 1.0)

    def test_anticheat_engine_invalid_demo(self):
        engine = AntiCheatEngine()
        result = engine.analyze_demo("nonexistent_demo.dem")
        self.assertIsInstance(result, MatchAnalysisResult)
        self.assertEqual(len(result.players), 0)
        self.assertIn("ERREUR", result.global_verdict)


if __name__ == "__main__":
    unittest.main()
