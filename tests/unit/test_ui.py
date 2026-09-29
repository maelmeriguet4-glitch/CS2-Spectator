"""
Unit Tests for CS2 Anti-Cheat CustomTkinter Tactical GUI.
Tests theme palettes, typography, MatchHeader, PlayerCard, ReplaysPanel,
CS2AntiCheatApp architecture, and async worker queue processing.
"""

import unittest
from unittest.mock import MagicMock, patch

import customtkinter as ctk

from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.ui.app import CS2AntiCheatApp
from src.ui.components.header import MatchHeader
from src.ui.components.player_card import PlayerCard
from src.ui.components.replays_panel import ReplaysPanel
from src.ui.theme import (
    THEME,
    badge_font,
    body_font,
    format_suspicion_color,
    format_team_badge,
    get_status_colors,
    header_font,
    mono_font,
    pill_font,
    title_font,
)


class TestUITheme(unittest.TestCase):
    """Tests tactical dark cyber palette, font factories, and color calculation functions."""

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

    def test_theme_palette_constants(self):
        required_keys = [
            "bg_main",
            "bg_card",
            "bg_card_hover",
            "bg_secondary",
            "border",
            "accent_cyan",
            "clean_green",
            "suspect_amber",
            "cheater_red",
            "text_white",
            "text_muted",
            "team_ct_bg",
            "team_t_bg",
        ]
        for key in required_keys:
            self.assertIn(key, THEME, f"Missing required theme key '{key}'")
            self.assertTrue(THEME[key].startswith("#"), f"Theme color {key} must be valid hex")

        self.assertEqual(THEME["bg_main"], "#000000")
        self.assertEqual(THEME["bg_card"], "#0A0A0A")
        self.assertEqual(THEME["accent_cyan"], "#FFFFFF")
        self.assertEqual(THEME["clean_green"], "#10B981")
        self.assertEqual(THEME["suspect_amber"], "#F59E0B")
        self.assertEqual(THEME["cheater_red"], "#EF4444")

    def test_font_helpers(self):
        f_title = title_font()
        self.assertEqual(f_title.cget("weight"), "bold")
        self.assertGreaterEqual(f_title.cget("size"), 16)

        f_header = header_font()
        self.assertEqual(f_header.cget("weight"), "bold")

        f_body = body_font()
        self.assertEqual(f_body.cget("size"), 14)

        f_mono = mono_font(size=11, bold=True)
        self.assertEqual(f_mono.cget("family"), "Consolas")
        self.assertEqual(f_mono.cget("weight"), "bold")

        f_badge = badge_font()
        self.assertEqual(f_badge.cget("weight"), "bold")

        f_pill = pill_font()
        self.assertEqual(f_pill.cget("family"), "Consolas")

    def test_format_suspicion_color(self):
        self.assertEqual(format_suspicion_color(15.0), THEME["clean_green"])
        self.assertEqual(format_suspicion_color(34.9), THEME["clean_green"])
        self.assertEqual(format_suspicion_color(35.0), THEME["suspect_amber"])
        self.assertEqual(format_suspicion_color(69.9), THEME["suspect_amber"])
        self.assertEqual(format_suspicion_color(70.0), THEME["cheater_red"])
        self.assertEqual(format_suspicion_color(98.5), THEME["cheater_red"])

    def test_get_status_colors(self):
        clean = get_status_colors("CLEAN", 12.0)
        self.assertEqual(clean["status_short"], "CLEAN")
        self.assertIn("NON DÉTECTÉ", clean["status_text"])
        self.assertEqual(clean["progress_color"], THEME["clean_green"])

        suspect = get_status_colors("SUSPECT", 55.0)
        self.assertEqual(suspect["status_short"], "SUSPECT")
        self.assertIn("SUSPECT", suspect["status_text"])
        self.assertEqual(suspect["progress_color"], THEME["suspect_amber"])

        cheater = get_status_colors("CHEATER", 92.0)
        self.assertEqual(cheater["status_short"], "CHEATER")
        self.assertIn("SUSPICION ÉLEVÉE", cheater["status_text"])
        self.assertEqual(cheater["progress_color"], THEME["cheater_red"])

    def test_format_team_badge(self):
        label, bg, text = format_team_badge(3)
        self.assertEqual(label, "CT")
        self.assertEqual(bg, THEME["team_ct_bg"])

        label, bg, text = format_team_badge(2)
        self.assertEqual(label, "T")
        self.assertEqual(bg, THEME["team_t_bg"])

        label, bg, text = format_team_badge(0)
        self.assertEqual(label, "SPEC")


class TestMatchHeader(unittest.TestCase):
    """Tests MatchHeader display logic and state updates."""

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
        self.header = MatchHeader(self.root)

    def tearDown(self):
        try:
            self.header.destroy()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def test_header_initial_state(self):
        self.assertIn("AUCUN REPLAY", self.header.lbl_map.cget("text"))
        self.assertIn("EN ATTENTE", self.header.verdict_badge.cget("text"))

    def test_header_update_match_result_clean(self):
        result = MatchAnalysisResult(
            demo_path="match.dem",
            map_name="de_inferno",
            server_name="Valve Dedicated Server",
            total_ticks=130000,
            duration_seconds=1625.0,
            players=[
                PlayerTelemetry(
                    steamid="76561198000000001",
                    name="CleanPlayer",
                    team_number=3,
                    aim_metrics={},
                    bhop_metrics={},
                    wh_metrics={},
                    suspicion_score=8.5,
                    verdict="CLEAN",
                    violation_flags=[],
                )
            ],
            global_verdict="MATCH INTÈGRE (AUCUN TRICHEUR DÉTECTÉ)",
        )

        self.header.update_match_result(result)
        self.assertIn("DE_INFERNO", self.header.lbl_map.cget("text"))
        self.assertIn("Valve Dedicated Server", self.header.lbl_server.cget("text"))
        self.assertIn("130,000", self.header.lbl_duration.cget("text"))
        self.assertIn("27m 05s", self.header.lbl_duration.cget("text"))
        self.assertIn("AUCUN SIGNAL FORT DÉTECTÉ", self.header.verdict_badge.cget("text"))

    def test_header_update_match_result_cheater(self):
        result = MatchAnalysisResult(
            demo_path="match.dem",
            map_name="de_mirage",
            server_name="Valve Server",
            total_ticks=95000,
            duration_seconds=1187.0,
            players=[
                PlayerTelemetry(
                    steamid="76561198000000002",
                    name="CheaterOne",
                    team_number=2,
                    aim_metrics={},
                    bhop_metrics={},
                    wh_metrics={},
                    suspicion_score=95.0,
                    verdict="CHEATER",
                    violation_flags=["[AIMBOT: Snap 42°/tick]"],
                )
            ],
            global_verdict="1 SUSPICION ÉLEVÉE",
        )

        self.header.update_match_result(result)
        self.assertIn("DE_MIRAGE", self.header.lbl_map.cget("text"))
        self.assertIn("SUSPICION(S) ÉLEVÉE(S)", self.header.verdict_badge.cget("text"))

    def test_header_loading_and_reset(self):
        self.header.set_loading("test_demo.dem")
        self.assertIn("ANALYSE EN COURS", self.header.lbl_map.cget("text"))
        self.assertIn("test_demo.dem", self.header.lbl_server.cget("text"))

        self.header.reset()
        self.assertIn("AUCUN REPLAY", self.header.lbl_map.cget("text"))


class TestPlayerCard(unittest.TestCase):
    """Tests PlayerCard widget construction, data mapping, action links, and violation pills."""

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

    def test_player_card_clean_rendering(self):
        player = PlayerTelemetry(
            steamid="76561198009233007",
            name="Sushyko",
            team_number=3,
            aim_metrics={"aim_p99": 6.2},
            bhop_metrics={"bhop_ratio_parfaits": 12.0},
            wh_metrics={"wh_ratio_lock_strict": 1.5},
            suspicion_score=4.2,
            verdict="CLEAN",
            violation_flags=[],
        )

        report_mock = MagicMock()
        card = PlayerCard(self.root, player=player, on_report=report_mock)

        self.assertEqual(card.lbl_name.cget("text"), "Sushyko")
        self.assertEqual(card.team_badge.cget("text"), "CT")
        self.assertIn("76561198009233007", card.lbl_steamid.cget("text"))
        self.assertIn("NON DÉTECTÉ", card.status_badge.cget("text"))
        self.assertEqual(card.progress_bar.get(), 1.0)
        self.assertIn("NON DÉTECTÉ", card.lbl_suspicion.cget("text"))
        self.assertIn("Motif", card.lbl_why.cget("text"))

        # Check clean pill
        children = card.pills_frame.winfo_children()
        self.assertEqual(len(children), 1)
        self.assertIn("NORMALISÉE", children[0].cget("text"))

        # Test report callback trigger
        card.btn_report.invoke()
        report_mock.assert_called_once_with(player)

        # Test trace 2d button existence and callback trigger
        flick_mock = MagicMock()
        card_with_flick = PlayerCard(self.root, player=player, on_view_flick=flick_mock)
        self.assertIn("Tracé 2D", card_with_flick.btn_trace_2d.cget("text"))
        card_with_flick.btn_trace_2d.invoke()
        flick_mock.assert_called_once_with(player)
        card_with_flick.destroy()

        # Test diagnostic button existence and callback trigger
        diag_mock = MagicMock()
        card_with_diag = PlayerCard(self.root, player=player, on_view_diagnostic=diag_mock)
        self.assertIn("Diagnostic", card_with_diag.btn_diagnostic.cget("text"))
        card_with_diag.btn_diagnostic.invoke()
        diag_mock.assert_called_once_with(player)
        card_with_diag.destroy()

        card.destroy()

    def test_player_card_cheater_violation_pills(self):
        flags = [
            "[AIMBOT: Snap 38.4°/tick]",
            "[WALLHACK: 28.5% Lock Mur]",
            "[BHOP: Script 87%]",
        ]
        player = PlayerTelemetry(
            steamid="76561199349501012",
            name="Jeffrey Epstein",
            team_number=2,
            aim_metrics={"aim_p99": 38.4},
            bhop_metrics={"bhop_ratio_parfaits": 87.0},
            wh_metrics={"wh_ratio_lock_strict": 28.5},
            suspicion_score=94.8,
            verdict="CHEATER",
            violation_flags=flags,
        )

        card = PlayerCard(self.root, player=player)

        self.assertEqual(card.lbl_name.cget("text"), "Jeffrey Epstein")
        self.assertEqual(card.team_badge.cget("text"), "T")
        self.assertIn("SUSPICION ÉLEVÉE", card.status_badge.cget("text"))
        self.assertAlmostEqual(card.progress_bar.get(), 0.948, places=2)

        # Check violation pills count and text
        children = card.pills_frame.winfo_children()
        self.assertEqual(len(children), 3)
        pill_texts = [c.cget("text") for c in children]
        for f in flags:
            self.assertIn(f, pill_texts)

        card.destroy()

    @patch("webbrowser.open")
    def test_player_card_action_buttons(self, mock_web_open):
        player = PlayerTelemetry(
            steamid="76561198009233007",
            name="TestActions",
            team_number=3,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=10.0,
            verdict="CLEAN",
            violation_flags=[],
        )

        card = PlayerCard(self.root, player=player)

        # Steam button click
        card.btn_steam.invoke()
        mock_web_open.assert_called_with("https://steamcommunity.com/profiles/76561198009233007")

        # Faceit button click
        card.btn_faceit.invoke()
        mock_web_open.assert_called_with("https://faceitfinder.com/profile/76561198009233007")

        card.destroy()

    def test_player_card_update_data(self):
        player1 = PlayerTelemetry(
            steamid="76561198000000001",
            name="Player1",
            team_number=3,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=10.0,
            verdict="CLEAN",
            violation_flags=[],
        )
        card = PlayerCard(self.root, player=player1)
        self.assertEqual(card.lbl_name.cget("text"), "Player1")

        player2 = PlayerTelemetry(
            steamid="76561198000000002",
            name="Player2_Suspect",
            team_number=2,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=58.0,
            verdict="SUSPECT",
            violation_flags=["[AIMBOT: Snap 22°/tick]"],
        )
        card.update_player(player2)
        self.assertEqual(card.lbl_name.cget("text"), "Player2_Suspect")
        self.assertEqual(card.team_badge.cget("text"), "T")
        self.assertIn("SUSPECT", card.status_badge.cget("text"))

        card.destroy()


class TestReplaysPanel(unittest.TestCase):
    """Tests ReplaysPanel listing, browsing, and watcher controls."""

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

    @patch("src.core.scanner.ReplayScanner.list_replays")
    @patch("src.core.scanner.ReplayScanner.find_cs2_replay_dir")
    def test_replays_panel_population(self, mock_find_dir, mock_list):
        mock_find_dir.return_value = "D:/FakeSteam/replays"
        mock_list.return_value = [
            ReplayInfo(
                file_path="D:/FakeSteam/replays/match1.dem",
                file_name="match1.dem",
                file_size_bytes=250 * 1024 * 1024,
                modified_time=1700000000.0,
                map_name="de_inferno",
            ),
            ReplayInfo(
                file_path="D:/FakeSteam/replays/match2.dem",
                file_name="match2.dem",
                file_size_bytes=180 * 1024 * 1024,
                modified_time=1700005000.0,
                map_name="de_mirage",
            ),
        ]

        cb_mock = MagicMock()
        panel = ReplaysPanel(self.root, on_select_replay=cb_mock)

        self.assertEqual(len(panel._item_widgets), 2)
        self.assertIn("2", panel.lbl_matches_count.cget("text"))

        # Click first replay item
        panel._item_widgets[0]._handle_click()
        cb_mock.assert_called_once_with("D:/FakeSteam/replays/match1.dem")
        self.assertEqual(panel.get_selected_replay(), "D:/FakeSteam/replays/match1.dem")

        panel.destroy()

    @patch("customtkinter.filedialog.askopenfilename")
    @patch("os.path.exists", return_value=True)
    def test_replays_panel_browse(self, mock_exists, mock_browse):
        mock_browse.return_value = "C:/tournament/pro_match.dem"
        cb_mock = MagicMock()
        panel = ReplaysPanel(self.root, on_select_replay=cb_mock)

        panel.browse_demo_file()
        cb_mock.assert_called_with("C:/tournament/pro_match.dem")
        self.assertEqual(panel.get_selected_replay(), "C:/tournament/pro_match.dem")

        panel.destroy()

    @patch("src.core.watcher.ReplayWatcher.start")
    @patch("src.core.scanner.ReplayScanner.find_cs2_replay_dir")
    @patch("os.path.exists", return_value=True)
    def test_replays_panel_watcher_toggle(self, mock_exists, mock_find, mock_start):
        mock_find.return_value = "D:/SteamLibrary/replays"
        panel = ReplaysPanel(self.root)

        self.assertFalse(panel.is_watcher_active())
        panel.toggle_watcher()
        self.assertIn("Active", panel.lbl_watcher_status.cget("text"))

        panel.toggle_watcher()
        self.assertIn("Inactive", panel.lbl_watcher_status.cget("text"))

        panel.destroy()


class TestCS2AntiCheatApp(unittest.TestCase):
    """Tests CS2AntiCheatApp main window, queue dispatching, and UI updates."""

    def setUp(self):
        # Initialize app with headless mode
        self.app = CS2AntiCheatApp()
        self.app.withdraw()

    def tearDown(self):
        try:
            self.app.destroy()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def test_app_layout_initialization(self):
        self.assertIsNotNone(self.app.header)
        self.assertIsNotNone(self.app.replays_panel)
        self.assertIsNotNone(self.app.scroll_cards)
        self.assertIsNotNone(self.app.status_bar)
        self.assertIn("Prêt", self.app.lbl_status.cget("text"))

    def test_app_display_match_result(self):
        players = [
            PlayerTelemetry(
                steamid=f"7656119800000000{i}",
                name=f"Player_{i}",
                team_number=3 if i < 5 else 2,
                aim_metrics={},
                bhop_metrics={},
                wh_metrics={},
                suspicion_score=85.0 if i == 0 else 10.0,
                verdict="CHEATER" if i == 0 else "CLEAN",
                violation_flags=["[AIMBOT: Snap 35°]"] if i == 0 else [],
            )
            for i in range(10)
        ]

        result = MatchAnalysisResult(
            demo_path="test_match.dem",
            map_name="de_dust2",
            server_name="Test Server",
            total_ticks=100000,
            duration_seconds=1250.0,
            players=players,
            global_verdict="1 TRICHEUR DÉTECTÉ",
        )

        self.app._display_match_result(result)

        # 10 player cards rendered
        self.assertEqual(len(self.app._player_cards), 10)
        # Cheater sorted to top
        self.assertEqual(self.app._player_cards[0].player.name, "Player_0")
        self.assertEqual(self.app._player_cards[0].player.verdict, "CHEATER")

        # Header updated
        self.assertIn("DE_DUST2", self.app.header.lbl_map.cget("text"))
        # Status bar updated
        self.assertIn("1 suspicion(s) élevée(s)", self.app.lbl_status.cget("text"))

    def test_app_queue_poller_messages(self):
        # 1. Put PROGRESS message in queue
        self.app._msg_queue.put(("PROGRESS", 0.45, "Extraction des ticks..."))
        self.app._check_queue()
        self.assertAlmostEqual(self.app.progress_bar.get(), 0.45, places=2)
        self.assertIn("Extraction des ticks", self.app.lbl_status.cget("text"))

        # 2. Put ERROR message in queue
        self.app._msg_queue.put(("ERROR", "Fichier démo corrompu"))
        self.app._check_queue()
        self.assertIn("Échec de l'analyse", self.app.lbl_status.cget("text"))

    def test_app_report_placeholder_dialog(self):
        player = PlayerTelemetry(
            steamid="76561198009233007",
            name="DialogTest",
            team_number=3,
            aim_metrics={"aim_p99": 30.0},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=80.0,
            verdict="CHEATER",
            violation_flags=["[AIMBOT: Snap 30°/tick]"],
        )

        # Trigger dialog
        self.app.on_player_report(player)
        # Find top level windows
        toplevels = [w for w in self.app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        self.assertGreaterEqual(len(toplevels), 1)
        dialog = toplevels[0]
        self.assertIn("DialogTest", dialog.title())
        dialog.destroy()

    def test_app_view_flick_dialog(self):
        player = PlayerTelemetry(
            steamid="76561198009233007",
            name="FlickPlayer",
            team_number=3,
            aim_metrics={"aim_p99": 25.0},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=75.0,
            verdict="SUSPECT",
            violation_flags=["[AIMBOT: Snap 25°/tick]"],
        )

        # Trigger 2D flick dialog
        self.app.on_player_view_flick(player)
        toplevels = [w for w in self.app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        self.assertGreaterEqual(len(toplevels), 1)
        dialog = toplevels[0]
        self.assertIn("FlickPlayer", dialog.title())
        self.assertEqual(dialog.tabview.get(), "📈 Tracé 2D du Snap")
        dialog.destroy()

    def test_app_view_diagnostic_dialog(self):
        player = PlayerTelemetry(
            steamid="76561198009233007",
            name="DiagPlayer",
            team_number=3,
            aim_metrics={"aim_p99": 22.0, "aim_jerk_max": 32.0},
            bhop_metrics={"bhop_ratio_parfaits": 85.0, "bhop_chaine_max": 5},
            wh_metrics={"wh_ratio_lock_cache": 18.0},
            suspicion_score=88.0,
            verdict="CHEATER",
            violation_flags=["[AIMBOT: Snap 22°/tick]", "[BHOP: Script 85%]"],
        )

        # Trigger diagnostic dialog
        self.app.on_player_view_diagnostic(player)
        toplevels = [w for w in self.app.winfo_children() if isinstance(w, ctk.CTkToplevel)]
        self.assertGreaterEqual(len(toplevels), 1)
        dialog = toplevels[0]
        self.assertIn("DiagPlayer", dialog.title())
        self.assertEqual(dialog.tabview.get(), "🔍 Diagnostic des Suspicions")
        # Verify text report for diagnostic tab
        diag_text = dialog.get_current_report_text()
        self.assertIn("RAPPORT DE DIAGNOSTIC BIOMÉCANIQUE CS2", diag_text)
        self.assertIn("DiagPlayer", diag_text)
        dialog.destroy()


if __name__ == "__main__":
    unittest.main()
