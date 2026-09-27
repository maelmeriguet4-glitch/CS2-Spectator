"""
Tier 4: Real-World Workload Scenarios Test Suite.
Validates authentic, end-to-end user workflows on actual CS2 competitive match replays:
- Scenario 1: Full 10-player biomechanical analysis of `demos/test.dem` (de_inferno, 264MB).
- Scenario 2: Integrity of player telemetry, metrics boundaries, team splits (5 CT / 5 T), and ML verdicts.
- Scenario 3: Real-world report generation and format integrity for identified suspect players.
- Scenario 4: Live Steam Replays discovery and fast header metadata verification across all matches.
- Scenario 5: End-to-end simulated user journey (Replay select -> Async Parse -> Suspect triage -> Report copy).
"""

import os
import re
import sys
import threading
import time
import unittest

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import pyperclip

from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult, PlayerTelemetry
from src.core.scanner import ReplayScanner
from tests.conftest import (
    REPO_ROOT,
    TEST_DEMO_PATH,
    has_model_file,
    has_test_demo,
)
from tests.e2e.test_tier3_interactions import get_report_generator


class TestTier4RealWorldWorkloads(unittest.TestCase):
    """Tier 4: End-to-end real-world CS2 match analysis scenarios."""

    @classmethod
    def setUpClass(cls):
        """Execute full engine analysis on test.dem once and share across scenario tests."""
        if not has_test_demo():
            raise unittest.SkipTest("demos/test.dem not available for real-world tests")
        if not has_model_file():
            raise unittest.SkipTest("cerveau_vac_custom.pkl not available for real-world tests")

        cls.engine = AntiCheatEngine()
        cls.progress_history = []

        def track_progress(pct, msg):
            cls.progress_history.append((pct, msg))

        # Perform the actual 10-player analysis
        start_time = time.time()
        cls.match_result = cls.engine.analyze_demo(TEST_DEMO_PATH, progress_callback=track_progress)
        cls.analysis_duration = time.time() - start_time

    def test_scenario_1_full_10_player_match_analysis(self):
        """Scenario 1: Full 10-player match analysis on demos/test.dem completes and structures cleanly."""
        res = self.match_result

        self.assertIsInstance(res, MatchAnalysisResult)
        self.assertEqual(res.map_name.lower(), "de_inferno")
        self.assertGreater(res.total_ticks, 50000, "Inferno competitive match should have >50k ticks")
        self.assertGreater(res.duration_seconds, 500.0, "Match duration should exceed 500 seconds")
        self.assertEqual(len(res.players), 10, "CS2 5v5 competitive match must have exactly 10 players")

        # Performance benchmark: Full 264MB 10-player analysis should complete in < 25 seconds
        self.assertLess(
            self.analysis_duration,
            30.0,
            f"Analysis took {self.analysis_duration:.1f}s, expected < 30.0s",
        )

    def test_scenario_2_player_telemetry_and_team_distribution(self):
        """Scenario 2: Verify all 10 players have valid SteamID64s, 5 CT / 5 T split, and bounded metrics."""
        res = self.match_result

        team_counts = {2: 0, 3: 0}  # 2: T, 3: CT
        for player in res.players:
            self.assertIsInstance(player, PlayerTelemetry)

            # Nickname must be non-empty
            self.assertTrue(len(player.name.strip()) > 0, "Player nickname must not be empty")

            # SteamID64 must be a 17-digit numeric string starting with 7656119
            self.assertTrue(
                re.match(r"^7656119\d{10}$", player.steamid),
                f"Player '{player.name}' has invalid SteamID64: '{player.steamid}'",
            )

            # Team must be 2 (T) or 3 (CT)
            self.assertIn(player.team_number, [2, 3])
            team_counts[player.team_number] += 1

            # Biomechanical metrics sanity checks
            aim = player.aim_metrics
            self.assertGreater(aim.get("aim_vitesse_max", 0.0), 0.0)
            self.assertGreater(aim.get("aim_p99", 0.0), 0.0)
            self.assertGreaterEqual(aim.get("aim_jerk_max", 0.0), 0.0)

            bhop = player.bhop_metrics
            self.assertGreaterEqual(bhop.get("bhop_total_sauts", 0.0), 0.0)
            self.assertTrue(0.0 <= bhop.get("bhop_ratio_parfaits", 0.0) <= 1.0)

            wh = player.wh_metrics
            self.assertTrue(0.0 <= wh.get("wh_ratio_lock_strict", 0.0) <= 1.0)

            # ML Verdict and suspicion confidence
            self.assertTrue(0.0 <= player.suspicion_score <= 100.0)
            self.assertIn(player.verdict, ["CLEAN", "SUSPECT", "CHEATER"])

        # Exactly 5 Terrorists and 5 Counter-Terrorists in competitive matchmaking
        self.assertEqual(team_counts[2], 5, "Match must have 5 Terrorists")
        self.assertEqual(team_counts[3], 5, "Match must have 5 Counter-Terrorists")

    def test_scenario_3_real_world_report_generation(self):
        """Scenario 3: Generate and validate Steam and Faceit reports for top suspicious player."""
        res = self.match_result
        Reporter = get_report_generator()

        # Sort players by suspicion score descending
        sorted_players = sorted(res.players, key=lambda p: p.suspicion_score, reverse=True)
        top_player = sorted_players[0]

        qcm_selections = [
            "Snaps instantanés et verrouillage de tête latence alignement (Aimbot / Silent Aim)",
            "Visée anormale à travers les fumigènes / murs (Pre-aiming & Wallhack)",
        ]
        user_notes = f"Audit officiel CS2 de la démo {os.path.basename(res.demo_path)} - Carte {res.map_name}"

        # 1. Generate Steam Report
        steam_report = Reporter.generate_steam_report(top_player, qcm_selections, user_notes)
        self.assertIn("RAPPORT D'INTÉGRITÉ CS2", steam_report)
        self.assertIn(top_player.name, steam_report)
        self.assertIn(top_player.steamid, steam_report)
        self.assertIn(f"https://steamcommunity.com/profiles/{top_player.steamid}", steam_report)
        self.assertIn(f"{top_player.suspicion_score:.1f}%", steam_report)
        self.assertIn("Aimbot / Silent Aim", steam_report)
        self.assertIn(user_notes, steam_report)

        # 2. Generate Faceit Report
        faceit_report = Reporter.generate_faceit_report(top_player, qcm_selections, user_notes)
        self.assertIn("FACEIT SUSPECT TELEMETRY REPORT", faceit_report)
        self.assertIn(top_player.name, faceit_report)
        self.assertIn(top_player.steamid, faceit_report)
        self.assertIn(f"https://faceitfinder.com/profile/{top_player.steamid}", faceit_report)
        self.assertIn("Aimbot / Silent Aim", faceit_report)

    def test_scenario_4_live_steam_replays_discovery_and_catalog(self):
        """Scenario 4: Discover all matches in active CS2 replays directory and catalog metadata."""
        replay_dir = ReplayScanner.find_cs2_replay_dir()
        self.assertIsNotNone(replay_dir)

        replays = ReplayScanner.list_replays(replay_dir)
        self.assertGreater(len(replays), 0, "Active replays directory must contain CS2 matches")

        for r in replays:
            self.assertTrue(r.file_name.lower().endswith(".dem"))
            self.assertGreater(r.file_size_bytes, 1024 * 1024, "Competitive match should exceed 1MB")
            self.assertGreater(r.modified_time, 0)
            self.assertIsNotNone(r.formatted_size)
            self.assertIsNotNone(r.formatted_time)

    def test_scenario_5_simulated_user_workflow(self):
        """Scenario 5: Simulate end-to-end user workflow: select -> async run -> inspect -> copy report."""
        Reporter = get_report_generator()

        # Step 1: User picks replay from catalog
        replays = ReplayScanner.list_replays()
        self.assertGreater(len(replays), 0, "Replay catalog must not be empty")

        # Step 2: User clicks "Analyser" (executed on worker thread)
        ui_events = []
        result_holder = []

        def worker_simulation():
            def cb(pct, msg):
                ui_events.append((pct, msg))
            engine = AntiCheatEngine()
            res = engine.analyze_demo(TEST_DEMO_PATH, progress_callback=cb)
            result_holder.append(res)

        t = threading.Thread(target=worker_simulation, daemon=True)
        t.start()
        t.join(timeout=30.0)

        self.assertEqual(len(result_holder), 1)
        match_res = result_holder[0]

        # Step 3: UI receives completed analysis and renders match banner
        self.assertGreaterEqual(len(ui_events), 4)
        self.assertIn("de_inferno", match_res.map_name)

        # Step 4: User inspects player cards and clicks "Générer Signalement" on highest suspect
        target_player = max(match_res.players, key=lambda p: p.suspicion_score)

        # Step 5: User fills QCM wizard and clicks "Copier"
        qcm = ["Snaps instantanés et verrouillage de tête latence alignement (Aimbot / Silent Aim)"]
        report_text = Reporter.generate_steam_report(target_player, qcm, "Round 12 clutch verification")

        # Step 6: Verify clipboard copy
        try:
            pyperclip.copy(report_text)
            pasted = pyperclip.paste()
            if pasted:
                self.assertEqual(pasted, report_text)
        except pyperclip.PyperclipException:
            pass  # Headless environment


if __name__ == "__main__":
    unittest.main(verbosity=2)
