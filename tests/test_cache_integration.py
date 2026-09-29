"""
Test d'intégration du cache SQLite et de la parallélisation de l'AntiCheatEngine.
"""

import os
import sys
import tempfile
import time
import unittest

DIR_RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if DIR_RACINE not in sys.path:
    sys.path.insert(0, DIR_RACINE)

from src.core.cache import load_cached_analysis, save_analysis_cache
from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult, PlayerTelemetry


class TestCacheIntegration(unittest.TestCase):

    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        # On va mocker src.core.cache.CACHE_DIR
        from pathlib import Path

        import src.core.cache
        self.original_cache_dir = src.core.cache.CACHE_DIR
        src.core.cache.CACHE_DIR = Path(self.tmp_dir.name)

    def tearDown(self):
        try:
            # Restaurer le CACHE_DIR
            import src.core.cache
            src.core.cache.CACHE_DIR = self.original_cache_dir
            self.tmp_dir.cleanup()
        except Exception as e:
            print(f"Error cleaning up: {e}")

    def test_cache_put_and_get(self):
        """Vérifie l'enregistrement et la restitution exacte du cache."""
        dummy_file = os.path.join(DIR_RACINE, "main.py")
        player = PlayerTelemetry(
            steamid="76561198000000001",
            name="TestBot",
            team_number=3,
            suspicion_score=85.5,
            verdict="CHEATER",
            violation_flags=["AIMBOT: Snap 45.0°/tick"],
            aim_metrics={"aim_p99": 45.0},
        )
        match_res = MatchAnalysisResult(
            demo_path=dummy_file,
            map_name="de_dust2",
            server_name="TestServer",
            total_ticks=5000,
            duration_seconds=78.1,
            players=[player],
            global_verdict="1 TRICHEUR DÉTECTÉ",
        )

        save_analysis_cache(dummy_file, match_res)

        cached = load_cached_analysis(dummy_file)
        self.assertIsNotNone(cached)
        self.assertEqual(cached.map_name, "de_dust2")
        self.assertEqual(cached.global_verdict, "1 TRICHEUR DÉTECTÉ")
        self.assertEqual(len(cached.players), 1)
        self.assertEqual(cached.players[0].name, "TestBot")
        self.assertEqual(cached.players[0].suspicion_score, 85.5)
        self.assertEqual(cached.players[0].verdict, "CHEATER")
        self.assertIn("AIMBOT: Snap 45.0°/tick", cached.players[0].violation_flags)

    def test_engine_instant_cache_hit(self):
        """Vérifie que l'AntiCheatEngine utilise le cache et répond en < 0.2s."""
        demo_path = os.path.join(DIR_RACINE, "demos", "test.dem")
        if not os.path.exists(demo_path):
            self.skipTest("demos/test.dem introuvable")

        engine = AntiCheatEngine(use_cache=True)
        # S'assurer que le cache contient une entrée en exécutant une fois
        res1 = engine.analyze_demo(demo_path)
        self.assertIsNotNone(res1)

        # Deuxième appel : DOIT être instantané (< 0.2s)
        start = time.time()
        res2 = engine.analyze_demo(demo_path)
        elapsed = time.time() - start

        self.assertIsNotNone(res2)
        self.assertLess(elapsed, 0.2, f"Le cache devait répondre en <0.2s, mais a pris {elapsed:.3f}s")
        self.assertEqual(len(res1.players), len(res2.players))
        self.assertEqual(res1.global_verdict, res2.global_verdict)


if __name__ == "__main__":
    unittest.main()
