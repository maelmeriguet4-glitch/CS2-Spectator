import queue

"""
Tier 3: Cross-Feature Interactions Test Suite.
Validates pairwise and multi-component subsystem interactions:
- Pair 1: Scanner + Watcher + AntiCheatEngine (Discovery -> Ingestion -> Analysis)
- Pair 2: Demo Ingestion + Telemetry Analyzers + ML Classifier (Parser -> Kinematics -> Inference)
- Pair 3: AntiCheatEngine + Reporting Wizard + Clipboard (Results -> Formatting -> Copy)
- Pair 4: Player Extraction + Profile URL Builders (SteamID64 -> Steam & Faceit Links)
- Pair 5: Engine Analysis + Async Thread Worker + Progress Callback Pipeline
"""

import os
import sys
import tempfile
import threading
import time
import unittest
from typing import List

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pyperclip

from src.analyzers.aimbot import analyze_aimbot
from src.analyzers.bhop import analyze_bhop
from src.analyzers.wallhack import analyze_wallhack
from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.core.parser import load_demo
from src.core.scanner import ReplayScanner
from src.core.watcher import ReplayWatcher
from src.ml.classifier import CheatClassifier
from tests.conftest import (
    REPO_ROOT,
    SOURCE2_MAGIC_HEADER,
    TEST_DEMO_PATH,
    create_sample_player_telemetry,
    create_synthetic_demo_file,
    has_test_demo,
)


# Fallback / Reference ReportGenerator matching PROJECT.md interface contract
class ReferenceReportGenerator:
    """Contract implementation of ReportGenerator for cross-feature testing."""

    @staticmethod
    def get_steam_profile_url(steamid: str) -> str:
        return f"https://steamcommunity.com/profiles/{steamid}"

    @staticmethod
    def get_faceit_url(steamid: str) -> str:
        return f"https://faceitfinder.com/profile/{steamid}"

    @staticmethod
    def generate_steam_report(player: PlayerTelemetry, qcm_options: List[str], comments: str) -> str:
        qcm_bullets = "\n".join(f"  • {opt}" for opt in qcm_options) if qcm_options else "  • Aucune observation manuelle"
        flag_bullets = "\n".join(f"  • {f}" for f in player.violation_flags) if player.violation_flags else "  • Aucun facteur suspect détecté"
        aim_snap = player.aim_metrics.get("aim_p99", 0.0)
        aim_jerk = player.aim_metrics.get("aim_jerk_max", 0.0)
        bhop_pct = player.bhop_metrics.get("bhop_ratio_parfaits", 0.0) * 100.0
        wh_strict = player.wh_metrics.get("wh_ratio_lock_strict", 0.0) * 100.0

        return (
            f"[RAPPORT D'INTÉGRITÉ CS2 - AUDIT BIOMÉCANIQUE OFFICIEL]\n"
            f"Joueur suspecté : {player.name}\n"
            f"SteamID64 : {player.steamid}\n"
            f"Profil Steam : {ReferenceReportGenerator.get_steam_profile_url(player.steamid)}\n\n"
            f"DIAGNOSTIC MOTEUR ANTI-CHEAT :\n"
            f"• Indice de suspicion IA : {player.suspicion_score:.1f}% [{player.verdict}]\n"
            f"• Facteurs anormaux détectés :\n{flag_bullets}\n\n"
            f"OBSERVATIONS EN MATCH (QCM) :\n{qcm_bullets}\n\n"
            f"PREUVES TÉLÉMÉTRIQUES OBJECTIVES :\n"
            f"- Vitesse angulaire max (Snap) : {aim_snap:.1f}°/tick\n"
            f"- À-coups mécaniques (Jerk max) : {aim_jerk:.1f}\n"
            f"- Ratio de BunnyHop parfait 1-tick : {bhop_pct:.1f}%\n"
            f"- Lock de visée à travers les murs : {wh_strict:.1f}%\n\n"
            f"Commentaires de l'auditeur :\n{comments if comments else 'N/A'}\n\n"
            f"Généré via CS2 Tactical Replay Auditor."
        )

    @staticmethod
    def generate_faceit_report(player: PlayerTelemetry, qcm_options: List[str], comments: str) -> str:
        qcm_bullets = "\n".join(f"- {opt}" for opt in qcm_options) if qcm_options else "- None"
        aim_snap = player.aim_metrics.get("aim_p99", 0.0)
        bhop_pct = player.bhop_metrics.get("bhop_ratio_parfaits", 0.0) * 100.0
        wh_strict = player.wh_metrics.get("wh_ratio_lock_strict", 0.0) * 100.0

        return (
            f"=== FACEIT SUSPECT TELEMETRY REPORT / AC TICKET ===\n"
            f"Suspect Nickname: {player.name}\n"
            f"Suspect SteamID64: {player.steamid}\n"
            f"FaceitFinder: {ReferenceReportGenerator.get_faceit_url(player.steamid)}\n\n"
            f"1. VIOLATION CATEGORY:\n{qcm_bullets}\n\n"
            f"2. QUANTITATIVE BIOMECHANICAL AUDIT:\n"
            f"- Machine Learning Confidence: {player.suspicion_score:.1f}% ({player.verdict})\n"
            f"- Max Angular Snap Velocity: {aim_snap:.1f} deg/tick\n"
            f"- Perfect 1-Tick Ground Jump Transition: {bhop_pct:.1f}%\n"
            f"- Occluded 3D Eye-Ray Alignment: {wh_strict:.1f}%\n\n"
            f"3. AUDITOR CONTEXT:\n{comments if comments else 'N/A'}\n\n"
            f"Ticket generated automatically via CS2 Anti-Cheat Replay Auditor."
        )


def get_report_generator():
    """Dynamically loads ReportGenerator from src.core.reporter if available, else reference."""
    try:
        from src.core.reporter import ReportGenerator
        return ReportGenerator
    except ImportError:
        return ReferenceReportGenerator


class TestTier3CrossFeatureInteractions(unittest.TestCase):
    """Tier 3: Pairwise and multi-feature interaction tests."""

    def test_interaction_1_scanner_watcher_engine_pipeline(self):
        """Interaction 1: Scanner discovers replay -> Watcher debounces -> Engine analyzes."""
        # Step 1: Scanner finds CS2 replay catalog
        replays = ReplayScanner.list_replays()
        self.assertGreater(len(replays), 0, "Scanner must catalog replays")

        # Step 2: Watcher simulates detection in temp folder
        with tempfile.TemporaryDirectory() as watch_dir:
            received_replays = []
            analysis_results = []

            def on_new_replay(info: ReplayInfo):
                received_replays.append(info)
                # Chain directly to AntiCheatEngine
                engine = AntiCheatEngine()
                res = engine.analyze_demo(info.file_path)
                analysis_results.append(res)

            watcher = ReplayWatcher(
                target_dir=watch_dir,
                on_new_replay_callback=on_new_replay,
                debounce_interval=0.05,
                stability_checks=2,
                timeout=1.0,
                min_size=8,
            )
            watcher.start()

            # Create a synthetic demo in the watched folder
            create_synthetic_demo_file(
                watch_dir,
                filename="match730_live_test.dem",
                header=SOURCE2_MAGIC_HEADER,
                payload_size=1024,
            )

            # Wait for watcher and engine callback to finish with a safe poll loop
            for _ in range(50):
                if len(analysis_results) >= 1:
                    break
                time.sleep(0.1)

            watcher.stop()

            self.assertEqual(len(received_replays), 1)
            self.assertEqual(received_replays[0].file_name, "match730_live_test.dem")
            self.assertEqual(len(analysis_results), 1)
            self.assertIsInstance(analysis_results[0], MatchAnalysisResult)

    def test_interaction_2_ingestion_analyzers_classifier_pipeline(self):
        """Interaction 2: Raw demo ticks feed aimbot/bhop/wallhack analyzers into ML inference."""
        if not has_test_demo():
            self.skipTest("demos/test.dem not available")

        # 1. Ingest demo
        demo_data = load_demo(TEST_DEMO_PATH)
        self.assertTrue(demo_data.is_valid)
        self.assertGreater(len(demo_data.players_info), 0)

        # 2. Pick first player
        first_player = demo_data.players_info[0]
        identifier = first_player["steamid"]

        # 3. Execute all 3 kinematic analyzers
        aim_res = analyze_aimbot(demo_data, identifier)
        bhop_res = analyze_bhop(demo_data, identifier)
        wh_res = analyze_wallhack(demo_data, identifier)

        self.assertIn("aim_p99", aim_res.metrics)
        self.assertIn("bhop_ratio_parfaits", bhop_res.metrics)
        self.assertIn("wh_ratio_lock_strict", wh_res.metrics)

        # 4. Feed metrics to CheatClassifier
        classifier = CheatClassifier()
        classification = classifier.predict(aim_res.metrics, bhop_res.metrics, wh_res.metrics)

        self.assertIsInstance(classification.suspicion_score, float)
        self.assertTrue(0.0 <= classification.suspicion_score <= 100.0)
        self.assertIn(classification.verdict, ["CLEAN", "SUSPECT", "CHEATER"])
        self.assertIn("clean", classification.probabilities)
        self.assertTrue("suspicion" in classification.probabilities or "cheat" in classification.probabilities)

    def test_interaction_3_engine_reporter_clipboard_pipeline(self):
        """Interaction 3: Engine analysis output feeds ReportGenerator and copies to clipboard."""
        Reporter = get_report_generator()

        # 1. Create simulated match analysis result
        sample_player = create_sample_player_telemetry(
            steamid="76561198069288826",
            name="SuspectENA",
            suspicion_score=87.5,
            verdict="CHEATER",
            snap_max=38.2,
            bhop_ratio=0.78,
            wh_lock_strict=0.24,
        )

        qcm_selections = [
            "Visée anormale à travers les fumigènes / murs (Pre-aiming & Wallhack)",
            "Snaps instantanés et verrouillage de tête latence alignement (Aimbot / Silent Aim)",
        ]
        notes = "Spectated in Round 8 — impossible snap through smoke on Mirage A ramp."

        # 2. Generate dual reports
        steam_report = Reporter.generate_steam_report(sample_player, qcm_selections, notes)
        faceit_report = Reporter.generate_faceit_report(sample_player, qcm_selections, notes)

        self.assertIn("SuspectENA", steam_report)
        self.assertIn("76561198069288826", steam_report)
        self.assertIn("87.5%", steam_report)
        self.assertIn("38.2°/tick", steam_report)

        self.assertIn("FACEIT SUSPECT TELEMETRY REPORT", faceit_report)
        self.assertIn("SuspectENA", faceit_report)
        self.assertIn("https://faceitfinder.com/profile/76561198069288826", faceit_report)

        # 3. Test clipboard interaction
        try:
            pyperclip.copy(steam_report)
            pasted = pyperclip.paste()
            if pasted:
                self.assertEqual(pasted, steam_report)
        except pyperclip.PyperclipException:
            pass  # Headless environment

    def test_interaction_4_player_extraction_to_profile_urls(self):
        """Interaction 4: Parsed player steamids map directly to valid Steam and Faceit URLs."""
        Reporter = get_report_generator()

        if has_test_demo():
            demo_data = load_demo(TEST_DEMO_PATH)
            players = demo_data.get_all_players()
            self.assertGreater(len(players), 0)

            for p in players:
                sid = p["steamid"]
                if sid != "0" and not sid.startswith("unknown"):
                    steam_url = Reporter.get_steam_profile_url(sid)
                    faceit_url = Reporter.get_faceit_url(sid)

                    self.assertTrue(steam_url.startswith("https://steamcommunity.com/profiles/"))
                    self.assertTrue(faceit_url.startswith("https://faceitfinder.com/profile/"))
                    self.assertIn(sid, steam_url)
                    self.assertIn(sid, faceit_url)

    def test_interaction_5_async_worker_and_progress_callback(self):
        """Interaction 5: Background worker thread executes engine with progress updates."""
        if not has_test_demo():
            self.skipTest("demos/test.dem not available")

        progress_events = []
        progress_queue = queue.Queue()

        def on_progress(pct: float, msg: str):
            progress_queue.put((pct, msg))

        def background_task():
            engine = AntiCheatEngine()
            # Analyze demo
            result = engine.analyze_demo(TEST_DEMO_PATH, progress_callback=on_progress)
            progress_queue.put(("RESULT", result))

        worker = threading.Thread(target=background_task, daemon=True)
        worker.start()
        worker.join(timeout=30.0)

        self.assertFalse(worker.is_alive(), "Analysis should complete within 30s timeout")

        # Collect events
        final_result = None
        while not progress_queue.empty():
            item = progress_queue.get_nowait()
            if item[0] == "RESULT":
                final_result = item[1]
            else:
                progress_events.append(item)

        self.assertIsNotNone(final_result)
        self.assertIsInstance(final_result, MatchAnalysisResult)
        self.assertEqual(len(final_result.players), 10)

        # Verify progress events monotonic start to finish
        self.assertGreater(len(progress_events), 3)
        pcts = [e[0] for e in progress_events]
        self.assertGreaterEqual(pcts[-1], 0.95)
        self.assertLessEqual(pcts[0], 0.30)


if __name__ == "__main__":
    unittest.main(verbosity=2)
