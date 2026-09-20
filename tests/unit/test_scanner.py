"""
Unit tests for ReplayScanner, ReplayInfo, PlayerTelemetry, and MatchAnalysisResult.
"""

import os
import shutil
import tempfile
import time
import unittest

from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.core.scanner import ReplayScanner


class TestReplayModels(unittest.TestCase):
    """Tests for dataclasses and their helper methods."""

    def test_replay_info_dataclass_and_properties(self):
        info = ReplayInfo(
            file_path=r"D:\replays\match1.dem",
            file_name="match1.dem",
            file_size_bytes=1024 * 1024 * 150,  # 150 MB
            modified_time=1700000000.0,
            map_name="de_inferno",
            server_name="Valve Server",
        )
        self.assertEqual(info.file_path, r"D:\replays\match1.dem")
        self.assertEqual(info.file_name, "match1.dem")
        self.assertEqual(info.file_size_bytes, 157286400)
        self.assertEqual(info.file_size_mb, 150.0)
        self.assertIn("MB", info.formatted_size)
        self.assertEqual(info.map_name, "de_inferno")
        self.assertEqual(info.server_name, "Valve Server")
        self.assertTrue(isinstance(info.formatted_time, str))

    def test_replay_info_formatted_sizes(self):
        tiny = ReplayInfo("t.dem", "t.dem", 500, 0)
        self.assertEqual(tiny.formatted_size, "500 B")

        kb = ReplayInfo("t.dem", "t.dem", 1024 * 50, 0)
        self.assertEqual(kb.formatted_size, "50.0 KB")

        mb = ReplayInfo("t.dem", "t.dem", 1024 * 1024 * 25, 0)
        self.assertEqual(mb.formatted_size, "25.0 MB")

        gb = ReplayInfo("t.dem", "t.dem", 1024 * 1024 * 1024 * 2, 0)
        self.assertEqual(gb.formatted_size, "2.00 GB")

    def test_player_telemetry_dataclass(self):
        telemetry = PlayerTelemetry(
            steamid="76561198000000000",
            name="TestPlayer",
            team_number=3,
            aim_metrics={"snap_max": 22.5, "jerk_max": 18.0},
            bhop_metrics={"ratio_parfaits": 0.1},
            wh_metrics={"ratio_lock_strict": 0.02},
            suspicion_score=15.5,
            verdict="CLEAN",
            violation_flags=[],
        )
        self.assertEqual(telemetry.steamid, "76561198000000000")
        self.assertEqual(telemetry.name, "TestPlayer")
        self.assertEqual(telemetry.team_number, 3)
        self.assertEqual(telemetry.aim_metrics["snap_max"], 22.5)
        self.assertEqual(telemetry.verdict, "CLEAN")
        self.assertEqual(telemetry.combat_events, [])

    def test_match_analysis_result_dataclass(self):
        player = PlayerTelemetry(
            steamid="76561198000000001",
            name="Suspect1",
            team_number=2,
            aim_metrics={},
            bhop_metrics={},
            wh_metrics={},
            suspicion_score=88.5,
            verdict="CHEATER",
            violation_flags=["AIMBOT_SNAP"],
        )
        result = MatchAnalysisResult(
            demo_path="test.dem",
            map_name="de_dust2",
            server_name="Competitive Server",
            total_ticks=64000,
            duration_seconds=1200.5,
            players=[player],
            global_verdict="CHEATER",
        )
        self.assertEqual(result.demo_path, "test.dem")
        self.assertEqual(result.map_name, "de_dust2")
        self.assertEqual(len(result.players), 1)
        self.assertEqual(result.players[0].name, "Suspect1")


class TestReplayScanner(unittest.TestCase):
    """Tests for CS2 replay directory scanning and metadata extraction."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="cs2_scanner_test_")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_libraryfolders_vdf_with_cs2(self):
        vdf_content = '''"libraryfolders"
{
	"0"
	{
		"path"		"C:\\\\Program Files (x86)\\\\Steam"
		"apps"
		{
			"228980"		"421667378"
		}
	}
	"1"
	{
		"path"		"D:\\\\SteamLibrary"
		"apps"
		{
			"730"		"73750578125"
			"10"		"321373155"
		}
	}
}'''
        vdf_file = os.path.join(self.temp_dir, "libraryfolders.vdf")
        with open(vdf_file, "w", encoding="utf-8") as f:
            f.write(vdf_content)

        parsed = ReplayScanner.parse_libraryfolders_vdf(vdf_file)
        self.assertEqual(len(parsed), 2)

        # Check library with CS2 (AppID 730)
        lib_with_cs2 = next((lib for lib in parsed if lib.get("has_cs2")), None)
        self.assertIsNotNone(lib_with_cs2)
        self.assertIn("D:", lib_with_cs2["path"])
        self.assertIn("730", lib_with_cs2["apps"])

    def test_parse_libraryfolders_vdf_empty_or_invalid(self):
        empty_vdf = os.path.join(self.temp_dir, "empty.vdf")
        with open(empty_vdf, "w") as f:
            f.write("")
        self.assertEqual(ReplayScanner.parse_libraryfolders_vdf(empty_vdf), [])
        self.assertEqual(ReplayScanner.parse_libraryfolders_vdf("non_existent_file.vdf"), [])

    def test_find_cs2_replay_dir_finds_active_path(self):
        detected = ReplayScanner.find_cs2_replay_dir()
        self.assertIsNotNone(detected)
        self.assertTrue(os.path.isdir(detected))

    def test_list_replays_sorting_and_filtering(self):
        # Create 3 synthetic demo files with staggered modification times
        demo1 = os.path.join(self.temp_dir, "match_old.dem")
        demo2 = os.path.join(self.temp_dir, "match_mid_de_nuke.dem")
        demo3 = os.path.join(self.temp_dir, "match_new_de_mirage.dem")
        info_file = os.path.join(self.temp_dir, "match_old.dem.info")
        txt_file = os.path.join(self.temp_dir, "notes.txt")

        # Write dummy headers
        with open(demo1, "wb") as f:
            f.write(b"PBDEMS2\x00" + b"\x00" * 100)
        with open(demo2, "wb") as f:
            f.write(b"PBDEMS2\x00" + b"\x00" * 100)
        with open(demo3, "wb") as f:
            f.write(b"PBDEMS2\x00" + b"\x00" * 100)
        with open(info_file, "wb") as f:
            f.write(b"fake info file")
        with open(txt_file, "w") as f:
            f.write("text file")

        now = time.time()
        os.utime(demo1, (now - 300, now - 300))
        os.utime(demo2, (now - 150, now - 150))
        os.utime(demo3, (now, now))

        replays = ReplayScanner.list_replays(self.temp_dir)

        # Should only list the 3 .dem files (ignoring .info and .txt)
        self.assertEqual(len(replays), 3)

        # Must be ordered newest to oldest
        self.assertEqual(replays[0].file_name, "match_new_de_mirage.dem")
        self.assertEqual(replays[1].file_name, "match_mid_de_nuke.dem")
        self.assertEqual(replays[2].file_name, "match_old.dem")

        # Map name extracted via filename pattern
        self.assertEqual(replays[0].map_name, "de_mirage")
        self.assertEqual(replays[1].map_name, "de_nuke")

    def test_extract_replay_metadata_companion_info(self):
        demo_path = os.path.join(self.temp_dir, "match_custom.dem")
        info_path = demo_path + ".info"

        with open(demo_path, "wb") as f:
            f.write(b"PBDEMS2\x00" + b"\x00" * 100)
        with open(info_path, "wb") as f:
            f.write(b"\x08\x01\x12\x10ValveServer\x1a\ncs_office\x20")

        map_name, _ = ReplayScanner.extract_replay_metadata(demo_path)
        self.assertEqual(map_name, "cs_office")

    def test_extract_replay_metadata_real_demo(self):
        real_demo = os.path.join("demos", "test.dem")
        if os.path.isfile(real_demo):
            map_name, server_name = ReplayScanner.extract_replay_metadata(real_demo)
            self.assertEqual(map_name, "de_inferno")
            self.assertIsNotNone(server_name)
            self.assertIn("Valve", server_name)

    def test_find_all_replay_dirs_and_library_paths(self):
        libs = ReplayScanner.get_steam_library_paths()
        self.assertIsInstance(libs, list)
        self.assertGreater(len(libs), 0)

        all_dirs = ReplayScanner.find_all_replay_dirs()
        self.assertIsInstance(all_dirs, list)
        self.assertGreater(len(all_dirs), 0)
        for d in all_dirs:
            self.assertTrue(os.path.isdir(d))

    def test_list_replays_empty_and_nonexistent(self):
        empty_dir = os.path.join(self.temp_dir, "empty")
        os.makedirs(empty_dir)
        self.assertEqual(ReplayScanner.list_replays(empty_dir), [])
        self.assertEqual(ReplayScanner.list_replays(os.path.join(self.temp_dir, "missing")), [])


if __name__ == "__main__":
    unittest.main()
