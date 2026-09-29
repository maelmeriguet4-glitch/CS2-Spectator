"""
Unit Tests for CS2 Anti-Cheat Steam & Faceit Reporting Wizard.
Tests URL generation, telemetry proof compilation, Steam and Faceit report templates,
and interactive ReportModal dialog in headless mode.
"""

import unittest
from unittest.mock import patch

import customtkinter as ctk

from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.core.reporter import QCM_OPTIONS, ReportGenerator
from src.ui.components.report_modal import ReportModal


class TestReportURLs(unittest.TestCase):
    """Tests Steam Profile and FaceitFinder URL generation for valid and edge-case SteamIDs."""

    def test_steam_profile_url_valid_steamid64(self):
        steamid = "76561198009233007"
        url = ReportGenerator.get_steam_profile_url(steamid)
        self.assertEqual(url, "https://steamcommunity.com/profiles/76561198009233007")

    def test_steam_profile_url_numeric_int(self):
        steamid_int = 76561198009233007
        url = ReportGenerator.get_steam_profile_url(steamid_int)
        self.assertEqual(url, "https://steamcommunity.com/profiles/76561198009233007")

    def test_steam_profile_url_edge_cases(self):
        # Empty string
        self.assertEqual(ReportGenerator.get_steam_profile_url(""), "")
        # BOT SteamID
        self.assertEqual(ReportGenerator.get_steam_profile_url("BOT_1"), "")
        # Zero SteamID
        self.assertEqual(ReportGenerator.get_steam_profile_url("0"), "")
        # None
        self.assertEqual(ReportGenerator.get_steam_profile_url(None), "")

    def test_faceit_url_valid_steamid64(self):
        steamid = "76561198009233007"
        url = ReportGenerator.get_faceit_url(steamid)
        self.assertEqual(url, "https://faceitfinder.com/profile/76561198009233007")

    def test_faceit_url_numeric_int(self):
        steamid_int = 76561198009233007
        url = ReportGenerator.get_faceit_url(steamid_int)
        self.assertEqual(url, "https://faceitfinder.com/profile/76561198009233007")

    def test_faceit_url_edge_cases(self):
        self.assertEqual(ReportGenerator.get_faceit_url(""), "")
        self.assertEqual(ReportGenerator.get_faceit_url("BOT_1"), "")
        self.assertEqual(ReportGenerator.get_faceit_url("0"), "")
        self.assertEqual(ReportGenerator.get_faceit_url(None), "")

    def test_qcm_options_constants(self):
        self.assertGreaterEqual(len(QCM_OPTIONS), 5)
        self.assertEqual(QCM_OPTIONS, ReportGenerator.QCM_OPTIONS)
        self.assertTrue(any("Aimbot" in opt or "Snaps" in opt for opt in QCM_OPTIONS))
        self.assertTrue(any("Wallhack" in opt or "fumigènes" in opt for opt in QCM_OPTIONS))
        self.assertTrue(any("Bunnyhop" in opt or "1-tick" in opt for opt in QCM_OPTIONS))


class TestTelemetryProofCompilation(unittest.TestCase):
    """Tests compilation of quantitative Source 2 biomechanical telemetry proofs."""

    def setUp(self):
        self.clean_player = PlayerTelemetry(
            steamid="76561198011111111",
            name="CleanPlayer",
            team_number=3,
            aim_metrics={
                "aim_vitesse_max": 220.0,
                "aim_p99": 9.5,
                "aim_jerk_moyen": 6.2,
                "aim_jerk_max": 14.0,
            },
            bhop_metrics={
                "bhop_total_sauts": 28,
                "bhop_ratio_parfaits": 0.08,
                "bhop_chaine_max": 1,
                "bhop_vitesse_moyenne": 248.5,
            },
            wh_metrics={
                "wh_ratio_lock_cache": 0.03,
                "wh_ratio_lock_strict": 0.01,
                "wh_tracking_consecutif_max": 4,
                "wh_distance_moyenne_verrous": 750.0,
            },
            suspicion_score=8.5,
            verdict="CLEAN",
            violation_flags=[],
            combat_events=[],
        )

        self.cheater_player = PlayerTelemetry(
            steamid="76561198099999999",
            name="RageHacker",
            team_number=2,
            aim_metrics={
                "aim_vitesse_max": 850.0,
                "aim_p99": 38.5,
                "aim_jerk_moyen": 28.5,
                "aim_jerk_max": 82.0,
            },
            bhop_metrics={
                "bhop_total_sauts": 45,
                "bhop_ratio_parfaits": 0.88,
                "bhop_chaine_max": 8,
                "bhop_vitesse_moyenne": 312.0,
            },
            wh_metrics={
                "wh_ratio_lock_cache": 0.42,
                "wh_ratio_lock_strict": 0.28,
                "wh_tracking_consecutif_max": 48,
                "wh_distance_moyenne_verrous": 620.0,
            },
            suspicion_score=96.0,
            verdict="CHEATER",
            violation_flags=[
                "[AIMBOT: Snap 38.5°/tick]",
                "[AIMBOT: Jerk Latence alignement 82.0]",
                "[BHOP: Script 88% Parfait]",
                "[WALLHACK: 48 Ticks Tracking Masqué]",
            ],
            combat_events=[
                {
                    "type": "aim_snap",
                    "tick": 14205,
                    "snap_angle": 38.5,
                    "jerk": 82.0,
                    "weapon": "ak47",
                },
                {
                    "type": "bhop_chain",
                    "start_tick": 22100,
                    "end_tick": 22180,
                    "chain_length": 8,
                    "avg_speed": 315.4,
                },
                {
                    "type": "wh_lock",
                    "start_tick": 34500,
                    "end_tick": 34548,
                    "duration_ticks": 48,
                    "target_name": "VictimTarget",
                    "distance": 620.0,
                },
            ],
        )

        self.replay_info = ReplayInfo(
            file_path="D:/SteamLibrary/csgo/replays/match_test_01.dem",
            file_name="match_test_01.dem",
            file_size_bytes=250000000,
            modified_time=1725530000.0,
            map_name="de_mirage",
            server_name="Valve Dedicated Server",
        )

    def test_compile_telemetry_proof_clean(self):
        proof = ReportGenerator.compile_telemetry_proof(self.clean_player, self.replay_info)
        self.assertIn("CleanPlayer", proof)
        self.assertIn("76561198011111111", proof)
        self.assertIn("CLEAN", proof)
        self.assertIn("8.5%", proof)
        self.assertIn("de_mirage", proof)
        self.assertIn("match_test_01.dem", proof)
        self.assertIn("9.5", proof)
        self.assertIn("8.0%", proof)  # 0.08 * 100
        self.assertIn("Aucun micro-incident", proof)

    def test_compile_telemetry_proof_cheater(self):
        proof = ReportGenerator.compile_telemetry_proof(self.cheater_player, self.replay_info)
        self.assertIn("RageHacker", proof)
        self.assertIn("76561198099999999", proof)
        self.assertIn("CHEATER", proof)
        self.assertIn("96.0%", proof)
        self.assertIn("38.5°/tick", proof)
        self.assertIn("82.0", proof)
        self.assertIn("88.0%", proof)
        self.assertIn("8 sauts consécutifs", proof)
        self.assertIn("48 ticks consécutifs", proof)
        # Incident extraction
        self.assertIn("Tick 14205", proof)
        self.assertIn("SNAP DE VISÉE", proof)
        self.assertIn("Ticks 22100-22180", proof)
        self.assertIn("ENCHAÎNEMENT BHOP", proof)
        self.assertIn("Ticks 34500-34548", proof)
        self.assertIn("VictimTarget", proof)

    def test_compile_telemetry_proof_without_demo_info(self):
        proof = ReportGenerator.compile_telemetry_proof(self.clean_player, demo_info=None)
        self.assertIn("Carte N/A", proof)
        self.assertIn("Démo : N/A", proof)
        self.assertIn("CleanPlayer", proof)

    def test_compile_telemetry_proof_with_match_analysis_result(self):
        match_result = MatchAnalysisResult(
            demo_path="C:/demos/pro_match.dem",
            map_name="de_inferno",
            server_name="Faceit Server 01",
            total_ticks=120000,
            duration_seconds=1500.0,
            players=[self.cheater_player],
            global_verdict="1 TRICHEUR DÉTECTÉ",
        )
        proof = ReportGenerator.compile_telemetry_proof(self.cheater_player, demo_info=match_result)
        self.assertIn("de_inferno", proof)
        self.assertIn("pro_match.dem", proof)


class TestSteamAndFaceitReports(unittest.TestCase):
    """Tests Steam In-Game and Faceit Support Ticket report generation."""

    def setUp(self):
        self.player = PlayerTelemetry(
            steamid="76561198099999999",
            name="SuspectTarget",
            team_number=2,
            aim_metrics={"aim_p99": 32.4, "aim_jerk_max": 75.0, "aim_jerk_moyen": 22.0},
            bhop_metrics={"bhop_ratio_parfaits": 0.85, "bhop_total_sauts": 30, "bhop_chaine_max": 6},
            wh_metrics={"wh_ratio_lock_strict": 0.25, "wh_tracking_consecutif_max": 35, "wh_distance_moyenne_verrous": 580.0},
            suspicion_score=89.5,
            verdict="CHEATER",
            violation_flags=["[AIMBOT: Snap 32.4°/tick]", "[BHOP: Script 85%]"],
            combat_events=[
                {"type": "aim_snap", "tick": 10500, "snap_angle": 32.4, "jerk": 75.0, "weapon": "deagle"},
                {"type": "bhop_chain", "start_tick": 18000, "end_tick": 18060, "chain_length": 6, "avg_speed": 310.0},
            ],
        )

        self.replay_info = ReplayInfo(
            file_path="match730_test.dem",
            file_name="match730_test.dem",
            file_size_bytes=240000000,
            modified_time=1725530000.0,
            map_name="de_dust2",
        )

    def test_steam_report_with_qcm_and_comments(self):
        selected_qcm = [
            QCM_OPTIONS[0],
            QCM_OPTIONS[1],
        ]
        comments = "Verrouillage de tête suspect au round 14 sur site A."

        report = ReportGenerator.generate_steam_report(
            player=self.player,
            qcm_options=selected_qcm,
            comments=comments,
            demo_info=self.replay_info,
        )

        # Verify key sections
        self.assertIn("[RAPPORT D'INTÉGRITÉ CS2 - AUDIT BIOMÉCANIQUE OFFICIEL]", report)
        self.assertIn("Joueur suspecté : SuspectTarget", report)
        self.assertIn("SteamID64 : 76561198099999999", report)
        self.assertIn("https://steamcommunity.com/profiles/76561198099999999", report)
        self.assertIn("Match / Carte : de_dust2 | Démo : match730_test.dem", report)
        self.assertIn("89.5% [CHEATER]", report)
        self.assertIn("[AIMBOT: Snap 32.4°/tick]", report)

        # Observations QCM
        self.assertIn(QCM_OPTIONS[0], report)
        self.assertIn(QCM_OPTIONS[1], report)

        # Telemetry metrics
        self.assertIn("32.4°/tick", report)
        self.assertIn("75.0", report)
        self.assertIn("85.0%", report)
        self.assertIn("25.0%", report)

        # Incidents
        self.assertIn("Tick 10500: Snap 32.4°/tick [deagle]", report)

        # User notes
        self.assertIn("Verrouillage de tête suspect au round 14 sur site A.", report)

    def test_steam_report_empty_options_and_clean_player(self):
        clean_player = PlayerTelemetry(
            steamid="76561198011111111",
            name="CleanGuy",
            team_number=3,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=5.0,
            verdict="CLEAN",
            violation_flags=[],
            combat_events=[],
        )

        report = ReportGenerator.generate_steam_report(
            player=clean_player,
            qcm_options=[],
            comments="",
            demo_info=None,
        )

        self.assertIn("CleanGuy", report)
        self.assertIn("Aucune observation manuelle sélectionnée", report)
        self.assertIn("Aucun commentaire additionnel fourni", report)
        self.assertIn("Comportement intègre", report)
        self.assertIn("Carte : N/A | Démo : N/A", report)

    def test_faceit_report_formatting(self):
        selected_qcm = [QCM_OPTIONS[3]]  # Bunnyhop
        comments = "Unnatural acceleration and consecutive bhop chains on catwalk."

        report = ReportGenerator.generate_faceit_report(
            player=self.player,
            qcm_options=selected_qcm,
            comments=comments,
            demo_info=self.replay_info,
        )

        self.assertIn("=== FACEIT SUSPECT TELEMETRY REPORT / AC TICKET ===", report)
        self.assertIn("Suspect Nickname: SuspectTarget", report)
        self.assertIn("Suspect SteamID64: 76561198099999999", report)
        self.assertIn("https://faceitfinder.com/profile/76561198099999999", report)
        self.assertIn("Match Map: de_dust2", report)
        self.assertIn("Replay File: match730_test.dem", report)

        # Sections
        self.assertIn("1. VIOLATION CATEGORY:", report)
        self.assertIn(QCM_OPTIONS[3], report)

        self.assertIn("2. QUANTITATIVE BIOMECHANICAL AUDIT:", report)
        self.assertIn("89.5% (CHEATER)", report)
        self.assertIn("32.4 deg/tick", report)
        self.assertIn("85.0%", report)

        self.assertIn("3. SYSTEM FLAGS:", report)
        self.assertIn("[AIMBOT: Snap 32.4°/tick]", report)

        self.assertIn("4. AUDITOR CONTEXT:", report)
        self.assertIn("Unnatural acceleration and consecutive bhop chains on catwalk.", report)

    def test_faceit_report_empty_options(self):
        report = ReportGenerator.generate_faceit_report(
            player=self.player,
            qcm_options=[],
            comments="",
            demo_info=None,
        )

        self.assertIn("Unspecified / Telemetry flag investigation", report)
        self.assertIn("None provided.", report)
        self.assertIn("Match Map: N/A", report)


class TestReportModalDialog(unittest.TestCase):
    """Tests ReportModal CustomTkinter dialog in headless environment."""

    @classmethod
    def setUpClass(cls):
        cls.root = ctk.CTk()
        cls.root.withdraw()

    @classmethod
    def tearDownClass(cls):
        try:
            cls.root.destroy()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def setUp(self):
        self.player = PlayerTelemetry(
            steamid="76561198009233007",
            name="ModalTester",
            team_number=3,
            aim_metrics={"aim_p99": 28.0, "aim_jerk_max": 65.0},
            bhop_metrics={"bhop_ratio_parfaits": 0.75, "bhop_total_sauts": 20, "bhop_chaine_max": 5},
            wh_metrics={"wh_ratio_lock_strict": 0.18, "wh_tracking_consecutif_max": 25},
            suspicion_score=82.0,
            verdict="CHEATER",
            violation_flags=["[AIMBOT: Snap 28°/tick]"],
            combat_events=[],
        )

        self.match_result = MatchAnalysisResult(
            demo_path="C:/demos/test_match.dem",
            map_name="de_dust2",
            server_name="Test Server",
            total_ticks=95000,
            duration_seconds=1200.0,
            players=[self.player],
            global_verdict="1 TRICHEUR DÉTECTÉ",
        )

        self.modal = ReportModal(self.root, player=self.player, match_result=self.match_result)
        self.modal.withdraw()

    def tearDown(self):
        try:
            self.modal.destroy()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def test_modal_initialization_and_title(self):
        self.assertIn("ModalTester", self.modal.title())
        self.assertEqual(len(self.modal.qcm_vars), len(QCM_OPTIONS))
        self.assertEqual(self.modal.get_selected_qcm(), [])
        self.assertEqual(self.modal.get_comments(), "")

    def test_modal_initial_tab_reports(self):
        steam_text = self.modal.txt_steam.get("1.0", "end-1c")
        faceit_text = self.modal.txt_faceit.get("1.0", "end-1c")

        self.assertIn("ModalTester", steam_text)
        self.assertIn("76561198009233007", steam_text)
        self.assertIn("de_dust2", steam_text)
        self.assertIn("82.0%", steam_text)

        self.assertIn("ModalTester", faceit_text)
        self.assertIn("76561198009233007", faceit_text)
        self.assertIn("de_dust2", faceit_text)

    def test_modal_realtime_qcm_update(self):
        test_opt = QCM_OPTIONS[0]
        # Check an option
        self.modal.set_qcm_option(test_opt, True)
        self.assertIn(test_opt, self.modal.get_selected_qcm())

        # Verify both tabs updated in real-time
        steam_text = self.modal.txt_steam.get("1.0", "end-1c")
        faceit_text = self.modal.txt_faceit.get("1.0", "end-1c")
        self.assertIn(test_opt, steam_text)
        self.assertIn(test_opt, faceit_text)

        # Uncheck option
        self.modal.set_qcm_option(test_opt, False)
        self.assertNotIn(test_opt, self.modal.get_selected_qcm())
        steam_text_after = self.modal.txt_steam.get("1.0", "end-1c")
        self.assertNotIn(test_opt, steam_text_after)

    def test_modal_realtime_comments_update(self):
        comment_text = "Suspect pre-firing cross-map smoke ticks 15000-16000."
        self.modal.set_comments(comment_text)
        self.assertEqual(self.modal.get_comments(), comment_text)

        steam_text = self.modal.txt_steam.get("1.0", "end-1c")
        faceit_text = self.modal.txt_faceit.get("1.0", "end-1c")
        self.assertIn(comment_text, steam_text)
        self.assertIn(comment_text, faceit_text)

    @patch("pyperclip.copy")
    def test_modal_copy_to_clipboard(self, mock_copy):
        copied = self.modal.copy_current_report()
        self.assertIn("ModalTester", copied)
        mock_copy.assert_called_once_with(copied)
        # Verify button text updated to "✓ Copié !"
        self.assertEqual(self.modal.btn_copy.cget("text"), "✓ Copié !")

    @patch("webbrowser.open")
    def test_modal_open_steam_profile(self, mock_open):
        self.modal.open_steam_profile()
        mock_open.assert_called_once_with("https://steamcommunity.com/profiles/76561198009233007")

    @patch("webbrowser.open")
    def test_modal_open_faceit(self, mock_open):
        self.modal.open_faceit()
        mock_open.assert_called_once_with("https://faceitfinder.com/profile/76561198009233007")


if __name__ == "__main__":
    unittest.main()
