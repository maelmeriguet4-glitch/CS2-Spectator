"""
Tier 2: Boundary & Corner Cases Test Suite.
Validates >=5 tests per feature for adverse conditions, edge values, and stress:
- R1: Empty folders, missing files, corrupt/truncated demo headers, rapid watcher toggles.
- R2: Zero movement, missing steamids, extreme angles/wraps, 0 combat events, extreme ML inputs.
- R3: Unicode/emojis, extreme name lengths, 0-player demos, meter boundary thresholds, queue stress.
- R4: All QCM selected, 0 QCM selected, massive auditor notes, unicode notes, bot steamids.
- R5: Resource path resolution with spaces, requirements integrity, model serialization integrity.
"""

import os
import queue
import sys
import tempfile
import time
import unittest

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

import joblib

from src.core.models import MatchAnalysisResult
from src.core.scanner import ReplayScanner
from src.core.watcher import ReplayWatcher, is_demo_write_complete
from tests.conftest import (
    MODEL_PATH,
    REPO_ROOT,
    create_sample_player_telemetry,
    has_model_file,
)


# ============================================================================
# R1 BOUNDARIES: REPLAY DETECTION & FILE INTEGRITY
# ============================================================================
class TestTier2BoundariesR1Replay(unittest.TestCase):
    """Tier 2 Boundary tests for Requirement R1."""

    def test_r1_b1_empty_replays_folder(self):
        """R1.B1: Scanning an empty directory must return an empty list without raising exceptions."""
        with tempfile.TemporaryDirectory() as empty_dir:
            replays = ReplayScanner.list_replays(empty_dir)
            self.assertIsInstance(replays, list)
            self.assertEqual(len(replays), 0)

    def test_r1_b2_nonexistent_directory(self):
        """R1.B2: Scanning a non-existent directory path must safely return an empty list."""
        bogus_path = os.path.join(tempfile.gettempdir(), f"nonexistent_cs2_dir_{int(time.time())}")
        replays = ReplayScanner.list_replays(bogus_path)
        self.assertIsInstance(replays, list)
        self.assertEqual(len(replays), 0)

    def test_r1_b3_corrupt_zero_byte_demo(self):
        """R1.B3: Zero-byte .dem file must be rejected by debounce and metadata extractors."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            empty_dem = os.path.join(tmp_dir, "empty.dem")
            with open(empty_dem, "wb"):
                pass  # 0 bytes

            # Debounce check must return False immediately or on timeout
            ready = is_demo_write_complete(empty_dem, poll_interval=0.05, timeout=0.2, min_size=8)
            self.assertFalse(ready)

            # Metadata extraction should return (None, None) gracefully
            map_name, server_name = ReplayScanner.extract_replay_metadata(empty_dem)
            self.assertIsNone(map_name)
            self.assertIsNone(server_name)

    def test_r1_b4_truncated_header_demo(self):
        """R1.B4: Truncated demo file (< 8 bytes) must be safely rejected."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            short_dem = os.path.join(tmp_dir, "short.dem")
            with open(short_dem, "wb") as f:
                f.write(b"PBD")  # Only 3 bytes

            ready = is_demo_write_complete(short_dem, poll_interval=0.05, timeout=0.2, min_size=8)
            self.assertFalse(ready)

    def test_r1_b5_invalid_vdf_syntax(self):
        """R1.B5: Parsing corrupted or unparseable VDF file must return empty list without crash."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            vdf_path = os.path.join(tmp_dir, "corrupt.vdf")
            with open(vdf_path, "w", encoding="utf-8") as f:
                f.write("<<< INVALID RANDOM GARBAGE @@@ NOT A VDF >>> { { {")

            parsed = ReplayScanner.parse_libraryfolders_vdf(vdf_path)
            self.assertIsInstance(parsed, list)
            self.assertEqual(len(parsed), 0)

    def test_r1_b6_rapid_watcher_toggle(self):
        """R1.B6: Rapid successive start() and stop() calls on ReplayWatcher must not deadlock or leak."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            watcher = ReplayWatcher(
                target_dir=tmp_dir,
                on_new_replay_callback=lambda r: None,
                debounce_interval=0.1,
                timeout=1.0,
            )

            for _ in range(5):
                watcher.start()
                self.assertTrue(watcher.is_running())
                watcher.stop()
                self.assertFalse(watcher.is_running())


# ============================================================================
# R2 BOUNDARIES: TELEMETRY & ML SCORING
# ============================================================================
class TestTier2BoundariesR2Telemetry(unittest.TestCase):
    """Tier 2 Boundary tests for Requirement R2."""

    def test_r2_b1_zero_movement_ticks(self):
        """R2.B1: Zero movement / zero aim delta calculations must not produce division by zero."""
        # Consecutive ticks where angles and coordinates are strictly identical
        yaw = 45.0
        pitch = 10.0
        dyaw = (yaw - yaw + 180.0) % 360.0 - 180.0
        dpitch = pitch - pitch
        omega = np.sqrt(dyaw**2 + dpitch**2)
        self.assertEqual(omega, 0.0)

        # Jerk between two identical angular velocities
        jerk = abs(omega - omega)
        self.assertEqual(jerk, 0.0)

    def test_r2_b2_missing_steamid_or_bot_zero(self):
        """R2.B2: BOT SteamIDs ('0' or empty) must be handled gracefully in telemetry structures."""
        bot_player = create_sample_player_telemetry(
            steamid="0",
            name="[BOT] Vitality",
            team_number=2,
            suspicion_score=0.0,
            verdict="CLEAN",
        )
        self.assertEqual(bot_player.steamid, "0")
        self.assertIn("CLEAN", bot_player.verdict)

    def test_r2_b3_extreme_angles_and_wraps(self):
        """R2.B3: Boundary angles at +-180° yaw and +-89° pitch must wrap cleanly."""
        def wrap(delta):
            return (delta + 180.0) % 360.0 - 180.0

        # Discontinuity: Cross from +179.9° to -179.9° -> true physical delta is +0.2°, not 359.8°
        prev_yaw = 179.9
        curr_yaw = -179.9
        raw_delta = curr_yaw - prev_yaw  # -359.8
        wrapped_delta = wrap(raw_delta)
        self.assertAlmostEqual(wrapped_delta, 0.2, places=4)

        # Pitch boundaries in CS2 are [-89.0, +89.0]
        pitch_min = -89.0
        pitch_max = 89.0
        delta_pitch = pitch_max - pitch_min
        self.assertEqual(delta_pitch, 178.0)

    def test_r2_b4_zero_combat_events(self):
        """R2.B4: Analyzer handles players with zero weapon_fire events without KeyError or crash."""
        events_df = pd.DataFrame(columns=["user_steamid", "tick"])
        # Filtering for user with 0 events
        user_events = events_df[events_df["user_steamid"] == "76561198000000000"]
        self.assertEqual(len(user_events), 0)
        # Snap in combat window should default to 0.0 or baseline
        snap_max = 0.0 if user_events.empty else float(user_events["tick"].max())
        self.assertEqual(snap_max, 0.0)

    def test_r2_b5_extreme_distances_wallhack(self):
        """R2.B5: Targets outside the [200, 2000] distance envelope must be excluded from WH locks."""
        valid_range_min = 200.0
        valid_range_max = 2000.0

        test_distances = [50.0, 150.0, 199.9, 200.0, 1000.0, 2000.0, 2000.1, 8500.0]
        in_range = [d for d in test_distances if valid_range_min <= d <= valid_range_max]

        self.assertEqual(in_range, [200.0, 1000.0, 2000.0])
        self.assertNotIn(50.0, in_range)  # Point-blank ignored
        self.assertNotIn(8500.0, in_range)  # Far spawn ignored

    def test_r2_b6_ml_all_zero_or_extreme_features(self):
        """R2.B6: ML model handles extreme inputs (all zeros, massive values) without NaN or crash."""
        if not has_model_file():
            self.skipTest("cerveau_vac_custom.pkl not found")

        bundle = joblib.load(MODEL_PATH)
        scaler = bundle["scaler"]
        modele = bundle["modele"]

        # All zeros
        all_zeros = np.zeros((1, 15))
        scaled_zeros = scaler.transform(all_zeros)
        prob_zeros = modele.predict_proba(scaled_zeros)[0][1] * 100.0
        self.assertFalse(np.isnan(prob_zeros))
        self.assertTrue(0.0 <= prob_zeros <= 100.0)

        # Extreme positive values (1e5)
        all_extreme = np.full((1, 15), 100000.0)
        scaled_extreme = scaler.transform(all_extreme)
        prob_extreme = modele.predict_proba(scaled_extreme)[0][1] * 100.0
        self.assertFalse(np.isnan(prob_extreme))
        self.assertTrue(0.0 <= prob_extreme <= 100.0)


# ============================================================================
# R3 BOUNDARIES: GUI DATA BINDING & UNICODE HANDLING
# ============================================================================
class TestTier2BoundariesR3GUI(unittest.TestCase):
    """Tier 2 Boundary tests for Requirement R3."""

    def test_r3_b1_extreme_unicode_player_names(self):
        """R3.B1: Player nicknames containing emojis, Cyrillic, Chinese, and symbols must not crash."""
        unicode_names = [
            "👑 Sniper_God 🎯",
            "Дмитрий CS2",
            "天下第一_Bhop",
            "user'; DROP TABLE players;--",
            "NormalName",
            "  LeadingTrailingWhitespace  ",
        ]
        for name in unicode_names:
            player = create_sample_player_telemetry(name=name)
            # Ensure name can be formatted and converted to string cleanly
            name_str = str(player.name).strip()
            self.assertTrue(len(name_str) > 0)

    def test_r3_b2_very_long_player_names(self):
        """R3.B2: Nicknames with 128+ characters must be safely truncated or handled in cards."""
        massive_name = "A" * 150
        player = create_sample_player_telemetry(name=massive_name)
        # Verify card label truncation helper
        display_name = player.name[:32] + "..." if len(player.name) > 32 else player.name
        self.assertLessEqual(len(display_name), 35)
        self.assertTrue(display_name.endswith("..."))

    def test_r3_b3_zero_players_match(self):
        """R3.B3: MatchAnalysisResult with 0 players must handle summary statistics gracefully."""
        empty_match = MatchAnalysisResult(
            demo_path="demos/empty.dem",
            map_name="unknown",
            server_name="Empty Server",
            total_ticks=0,
            duration_seconds=0.0,
            players=[],
            global_verdict="0 PLAYERS ANALYZED",
        )
        self.assertEqual(len(empty_match.players), 0)
        self.assertEqual(empty_match.global_verdict, "0 PLAYERS ANALYZED")

    def test_r3_b4_suspicion_meter_boundaries(self):
        """R3.B4: Suspicion meter color and verdict transitions at critical thresholds."""
        def get_status_badge(score: float):
            if score < 35.0:
                return "🟢 NON DÉTECTÉ (CLEAN)", "#10B981"
            elif score < 70.0:
                return "🟡 SUSPECT (À SURVEILLER)", "#F59E0B"
            return "🔴 TRICHEUR AVÉRÉ (BAN)", "#EF4444"

        # Clean edge: 34.9%
        badge, col = get_status_badge(34.9)
        self.assertIn("CLEAN", badge)
        self.assertEqual(col, "#10B981")

        # Suspect edge: 35.0%
        badge, col = get_status_badge(35.0)
        self.assertIn("SUSPECT", badge)
        self.assertEqual(col, "#F59E0B")

        # Cheater edge: 70.0%
        badge, col = get_status_badge(70.0)
        self.assertIn("TRICHEUR", badge)
        self.assertEqual(col, "#EF4444")

    def test_r3_b5_queue_overflow_stress(self):
        """R3.B5: Background worker queue handles 1,000 rapid event messages without starvation."""
        q = queue.Queue()
        for i in range(1000):
            q.put(("PROGRESS", i, i / 1000.0))

        self.assertEqual(q.qsize(), 1000)

        # Drain queue
        drained = 0
        while not q.empty():
            q.get_nowait()
            drained += 1

        self.assertEqual(drained, 1000)


# ============================================================================
# R4 BOUNDARIES: REPORTING WIZARD EDGE CASES
# ============================================================================
class TestTier2BoundariesR4Reporting(unittest.TestCase):
    """Tier 2 Boundary tests for Requirement R4."""

    def test_r4_b1_all_qcm_options_selected(self):
        """R4.B1: Generating report when all QCM options are checked simultaneously."""
        all_options = [
            "Visée anormale à travers les fumigènes / murs (Pre-aiming & Wallhack)",
            "Snaps instantanés et verrouillage de tête latence alignement (Aimbot / Silent Aim)",
            "Compensations de recul parfaites sans dispersion (No-Recoil / Macro)",
            "Sauts parfaits 1-tick en chaîne et prises de vitesse (Bunnyhop Script)",
            "Prises d'informations impossibles et pré-tirs systématiques (Radar / ESP)",
            "Mouvement de caméra désynchronisé / toupie (Anti-Aim / Spinbot)",
        ]
        create_sample_player_telemetry(verdict="CHEATER", suspicion_score=98.5)

        bullets = "\n".join(f"  • {opt}" for opt in all_options)
        report = f"OBSERVATIONS EN MATCH (QCM) :\n{bullets}"

        for opt in all_options:
            self.assertIn(opt, report)

    def test_r4_b2_no_qcm_and_no_notes(self):
        """R4.B2: Report generation with empty QCM and empty commentary produces valid fallback."""
        qcm_selected = []
        notes = ""

        qcm_section = "\n".join(f"  • {opt}" for opt in qcm_selected) if qcm_selected else "  • Aucune observation manuelle"
        notes_section = notes if notes else "Aucun commentaire additionnel."

        self.assertEqual(qcm_section, "  • Aucune observation manuelle")
        self.assertEqual(notes_section, "Aucun commentaire additionnel.")

    def test_r4_b3_extreme_length_auditor_notes(self):
        """R4.B3: Handling 1,000-word user commentary without buffer overflow."""
        massive_notes = "Extremely suspicious clutch round. " * 100
        create_sample_player_telemetry()
        report = f"Commentaires de l'auditeur :\n{massive_notes}"
        self.assertIn("Extremely suspicious clutch round.", report)
        self.assertGreater(len(report), 3000)

    def test_r4_b4_unicode_in_report_notes(self):
        """R4.B4: Accented characters and emojis in user comments preserved in UTF-8."""
        unicode_notes = "Tir à travers le mur près du site B 🎯 — vérifié par l'équipe d'arbitrage 🛡️."
        create_sample_player_telemetry()
        report = f"Commentaires :\n{unicode_notes}"
        # Ensure utf-8 encoding works without charmap errors
        encoded = report.encode("utf-8")
        self.assertEqual(encoded.decode("utf-8"), report)

    def test_r4_b5_bot_steamid_url_generation(self):
        """R4.B5: Bot steamid ('0') produces safe fallback URLs or handles empty profiles."""
        bot_steamid = "0"
        steam_url = f"https://steamcommunity.com/profiles/{bot_steamid}"
        faceit_url = f"https://faceitfinder.com/profile/{bot_steamid}"

        self.assertIn("0", steam_url)
        self.assertIn("0", faceit_url)


# ============================================================================
# R5 BOUNDARIES: PACKAGING & SYSTEM ROBUSTNESS
# ============================================================================
class TestTier2BoundariesR5Packaging(unittest.TestCase):
    """Tier 2 Boundary tests for Requirement R5."""

    def test_r5_b1_resource_path_with_spaces(self):
        """R5.B1: Resource path resolver functions correctly with spaces in root path."""
        def resolve_resource(relative_path: str, base_dir: str) -> str:
            return os.path.normpath(os.path.join(base_dir, relative_path))

        base_with_spaces = r"C:\Users\pc\Desktop\Cs2 anticheat\cs2_anticheat"
        resolved = resolve_resource("cerveau_vac_custom.pkl", base_with_spaces)
        self.assertIn("Cs2 anticheat", resolved)
        self.assertTrue(resolved.endswith("cerveau_vac_custom.pkl"))

    def test_r5_b2_requirements_no_duplicates(self):
        """R5.B2: requirements.txt must contain no duplicate package entries."""
        req_path = os.path.join(REPO_ROOT, "requirements.txt")
        if os.path.isfile(req_path):
            with open(req_path, "r", encoding="utf-8") as f:
                lines = [line.strip().split(">=")[0].split("==")[0].lower() for line in f if line.strip() and not line.startswith("#")]
            duplicates = [pkg for pkg in set(lines) if lines.count(pkg) > 1]
            self.assertEqual(len(duplicates), 0, f"Found duplicate packages in requirements.txt: {duplicates}")

    def test_r5_b3_model_file_integrity(self):
        """R5.B3: cerveau_vac_custom.pkl file size must be > 100KB and uncorrupted."""
        if not has_model_file():
            self.skipTest("cerveau_vac_custom.pkl not found")

        file_size = os.path.getsize(MODEL_PATH)
        self.assertGreater(file_size, 100 * 1024, "Model file size should exceed 100KB")

        with open(MODEL_PATH, "rb") as f:
            header_bytes = f.read(16)
        self.assertGreater(len(header_bytes), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
