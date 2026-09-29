"""
Unit tests for CS2 Biomechanical Telemetry Analyzers (Aimbot, BunnyHop, Wallhack)
and demoparser2 pipeline wrapper using standard unittest.
"""

import unittest
from typing import Optional

import numpy as np
import pandas as pd

from src.analyzers.aimbot import (
    AimAnalysisResult,
    analyze_aimbot,
    calculate_angular_delta,
    normalize_angle,
)
from src.analyzers.bhop import (
    BhopAnalysisResult,
    analyze_bhop,
)
from src.analyzers.wallhack import (
    WallhackAnalysisResult,
    analyze_wallhack,
    calculate_aim_angles_3d,
)
from src.core.parser import REQUIRED_TICK_PROPERTIES, DemoData
from tests.conftest import TEST_DEMO_PATH, has_test_demo


class MockDemoData:
    """Lightweight in-memory mock of DemoData for deterministic unit testing."""

    def __init__(
        self,
        ticks: pd.DataFrame,
        weapon_fire: Optional[pd.DataFrame] = None,
        players: Optional[list] = None,
    ):
        self.is_valid = True
        self.valide = True
        self.ticks = ticks
        self.events = {
            "weapon_fire": weapon_fire if weapon_fire is not None else pd.DataFrame(),
            "player_hurt": pd.DataFrame(),
            "player_death": pd.DataFrame(),
        }
        self.header = {"map_name": "de_mock", "server_name": "Mock Server"}
        self.map_name = "de_mock"
        self.server_name = "Mock Server"
        self.players_info = players or []
        self.players = [p["name"] for p in self.players_info]
        self.total_ticks = len(ticks["tick"].unique()) if "tick" in ticks.columns and not ticks.empty else 0
        self.duration_seconds = self.total_ticks / 64.0

    def get_player_ticks(self, player_identifier):
        target = str(player_identifier).strip()
        mask = (self.ticks["steamid"].astype(str) == target) | (self.ticks["name"].astype(str) == target)
        if "health" in self.ticks.columns:
            mask = mask & (self.ticks["health"] > 0)
        return self.ticks[mask].sort_values("tick").reset_index(drop=True)

    # Compat FR
    def obtenir_donnees_joueur(self, joueur):
        return self.get_player_ticks(joueur)

    def obtenir_tirs_joueur(self, joueur):
        return self.get_player_events(joueur, "weapon_fire")

    def get_player_events(self, player_identifier, event_name="weapon_fire"):
        df = self.events.get(event_name, pd.DataFrame())
        if df.empty:
            return pd.DataFrame()
        target = str(player_identifier).strip()
        mask = (df["user_steamid"].astype(str) == target) | (df["user_name"].astype(str) == target)
        return df[mask].reset_index(drop=True)

    def get_all_players(self):
        return self.players_info


class TestAngleMath(unittest.TestCase):
    """Tests for trigonometric normalization and circular differences."""

    def test_normalize_angle(self):
        self.assertEqual(normalize_angle(0.0), 0.0)
        self.assertEqual(normalize_angle(90.0), 90.0)
        self.assertEqual(normalize_angle(-90.0), -90.0)
        self.assertIn(normalize_angle(180.0), [-180.0, 180.0])
        self.assertEqual(normalize_angle(270.0), -90.0)
        self.assertEqual(normalize_angle(-280.0), 80.0)
        self.assertEqual(normalize_angle(360.0), 0.0)
        self.assertEqual(normalize_angle(720.0), 0.0)

    def test_calculate_angular_delta_wraparound(self):
        # Small forward step across boundary: from +179 to -179 is a +2 degree turn, NOT -358
        delta_pos = calculate_angular_delta(179.0, -179.0)
        self.assertTrue(np.isclose(delta_pos, 2.0))

        # Small backward step across boundary: from -179 to +179 is a -2 degree turn, NOT +358
        delta_neg = calculate_angular_delta(-179.0, 179.0)
        self.assertTrue(np.isclose(delta_neg, -2.0))

        # Regular delta
        delta_normal = calculate_angular_delta(45.0, 50.0)
        self.assertTrue(np.isclose(delta_normal, 5.0))


class TestAimbotAnalyzer(unittest.TestCase):
    """Tests for camera angular velocity, jerk, and snap detection."""

    def test_aimbot_smooth_human(self):
        n_ticks = 100
        ticks_data = {
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000001"] * n_ticks,
            "name": ["CleanPlayer"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": [0.0 + (i * 0.1) for i in range(n_ticks)],
            "yaw": [0.0 + (i * 0.2) for i in range(n_ticks)],
            "active_weapon_name": ["weapon_ak47"] * n_ticks,
        }
        df_ticks = pd.DataFrame(ticks_data)
        df_fire = pd.DataFrame({
            "tick": [1020, 1050],
            "user_steamid": ["76561198000000001", "76561198000000001"],
            "user_name": ["CleanPlayer", "CleanPlayer"],
            "weapon": ["weapon_ak47", "weapon_ak47"],
        })
        mock_demo = MockDemoData(df_ticks, weapon_fire=df_fire, players=[{"steamid": "76561198000000001", "name": "CleanPlayer", "team_number": 2}])

        result = analyze_aimbot(mock_demo, "76561198000000001")
        self.assertIsInstance(result, AimAnalysisResult)
        self.assertLess(result.metrics["aim_p99"], 5.0)
        self.assertLess(result.metrics["aim_jerk_max"], 5.0)
        self.assertEqual(len(result.flagged_snaps), 0)

    def test_aimbot_violent_snapbot(self):
        n_ticks = 60
        yaw_series = [10.0] * n_ticks
        yaw_series[20] = 45.0  # 35-degree instantaneous jump

        ticks_data = {
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000002"] * n_ticks,
            "name": ["AimbotUser"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": yaw_series,
            "active_weapon_name": ["weapon_ak47"] * n_ticks,
        }
        df_ticks = pd.DataFrame(ticks_data)
        df_fire = pd.DataFrame({
            "tick": [1020],
            "user_steamid": ["76561198000000002"],
            "user_name": ["AimbotUser"],
            "weapon": ["weapon_ak47"],
        })
        mock_demo = MockDemoData(df_ticks, weapon_fire=df_fire)

        result = analyze_aimbot(mock_demo, "76561198000000002")
        self.assertGreater(result.metrics["aim_p99"], 18.0)
        self.assertGreater(result.metrics["aim_jerk_max"], 30.0)
        self.assertGreater(len(result.flagged_snaps), 0)
        self.assertIn(result.flagged_snaps[0]["tick"], [1020, 1021])


class TestBhopAnalyzer(unittest.TestCase):
    """Tests for ground-air transition delays and bhop chains."""

    def test_bhop_spaced_human_jumps(self):
        air_pattern = [False] * 5 + ([True] * 10 + [False] * 10) * 4
        n_ticks = len(air_pattern)

        ticks_data = {
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000003"] * n_ticks,
            "name": ["NormalJumper"] * n_ticks,
            "health": [100] * n_ticks,
            "is_airborne": air_pattern,
            "velocity_X": [150.0] * n_ticks,
            "velocity_Y": [0.0] * n_ticks,
        }
        df_ticks = pd.DataFrame(ticks_data)
        mock_demo = MockDemoData(df_ticks)

        result = analyze_bhop(mock_demo, "76561198000000003")
        self.assertIsInstance(result, BhopAnalysisResult)
        self.assertEqual(result.metrics["bhop_ratio_parfaits"], 0.0)
        self.assertEqual(result.metrics["bhop_chaine_max"], 0)
        self.assertEqual(len(result.flagged_chains), 0)

    def test_bhop_scripted_macro(self):
        air_pattern = [False] * 2
        for _ in range(5):
            air_pattern.extend([True] * 8)
            air_pattern.append(False)  # exactly 1 tick at ground
        air_pattern.extend([True] * 8)
        air_pattern.extend([False] * 10)

        n_ticks = len(air_pattern)
        ticks_data = {
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000004"] * n_ticks,
            "name": ["ScriptKid"] * n_ticks,
            "health": [100] * n_ticks,
            "is_airborne": air_pattern,
            "velocity_X": [280.0] * n_ticks,
            "velocity_Y": [0.0] * n_ticks,
        }
        df_ticks = pd.DataFrame(ticks_data)
        mock_demo = MockDemoData(df_ticks)

        result = analyze_bhop(mock_demo, "76561198000000004")
        self.assertGreaterEqual(result.metrics["bhop_ratio_parfaits"], 0.80)
        self.assertGreaterEqual(result.metrics["bhop_chaine_max"], 4)
        self.assertGreater(len(result.flagged_chains), 0)
        self.assertGreaterEqual(result.flagged_chains[0]["chain_length"], 3)


class TestWallhackAnalyzer(unittest.TestCase):
    """Tests for 3D Source 2 eye-ray alignment and active wall tracking."""

    def test_calculate_aim_angles_3d(self):
        yaw, pitch, dist = calculate_aim_angles_3d(0, 0, 0, 100, 0, 2)
        self.assertTrue(np.isclose(yaw, 0.0))
        self.assertTrue(np.isclose(pitch, 0.0, atol=0.1))
        self.assertTrue(np.isclose(dist, 100.0, atol=0.1))

        yaw, pitch, dist = calculate_aim_angles_3d(0, 0, 0, 0, 100, 2)
        self.assertTrue(np.isclose(yaw, 90.0))

    def test_wallhack_occluded_lock_detection(self):
        n_ticks = 80
        ticks = list(range(1000, 1000 + n_ticks))

        player_yaw = [0.2 if i % 2 == 0 else -0.2 for i in range(n_ticks)]
        df_p1 = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000005"] * n_ticks,
            "name": ["WhUser"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [0.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": player_yaw,
            "spotted": [False] * n_ticks,
        })

        df_p2 = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000006"] * n_ticks,
            "name": ["Victim"] * n_ticks,
            "team_num": [2] * n_ticks,
            "health": [100] * n_ticks,
            "X": [500.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [2.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [180.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })

        mock_demo = MockDemoData(pd.concat([df_p1, df_p2], ignore_index=True))
        result = analyze_wallhack(mock_demo, "76561198000000005")

        self.assertIsInstance(result, WallhackAnalysisResult)
        self.assertGreater(result.metrics["wh_ratio_lock_strict"], 0.80)
        self.assertGreaterEqual(result.metrics["wh_tracking_consecutif_max"], 40)
        self.assertGreater(len(result.flagged_locks), 0)
        self.assertEqual(result.flagged_locks[0]["target_steamid"], "76561198000000006")

    def test_wallhack_spotted_enemies_ignored(self):
        n_ticks = 60
        ticks = list(range(1000, 1000 + n_ticks))

        df_p1 = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000007"] * n_ticks,
            "name": ["LegitUser"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [0.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })
        df_p2 = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000008"] * n_ticks,
            "name": ["VisibleEnemy"] * n_ticks,
            "team_num": [2] * n_ticks,
            "health": [100] * n_ticks,
            "X": [500.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [2.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [180.0] * n_ticks,
            "spotted": [True] * n_ticks,
        })

        mock_demo = MockDemoData(pd.concat([df_p1, df_p2], ignore_index=True))
        result = analyze_wallhack(mock_demo, "76561198000000007")

        self.assertEqual(result.metrics["wh_ratio_lock_strict"], 0.0)
        self.assertEqual(result.metrics["wh_tracking_consecutif_max"], 0)


class TestRealDemoAndEdgeCases(unittest.TestCase):
    """Tests against real CS2 demo file and edge error cases."""

    def test_real_demo_parsing(self):
        if not has_test_demo():
            self.skipTest("demos/test.dem not found")

        demo = DemoData(TEST_DEMO_PATH)
        self.assertTrue(demo.is_valid)
        self.assertEqual(demo.map_name, "de_inferno")
        self.assertEqual(len(demo.players_info), 10)

        for p in demo.players_info:
            sid = p["steamid"]
            self.assertIsInstance(sid, str)
            self.assertEqual(len(sid), 17)
            self.assertTrue(sid.startswith("7656119"))
            self.assertTrue(len(p["name"]) > 0)

        self.assertFalse(demo.ticks.empty)
        self.assertGreater(len(demo.ticks), 100000)
        for prop in REQUIRED_TICK_PROPERTIES:
            self.assertIn(prop, demo.ticks.columns)

        self.assertFalse(demo.tirs.empty)
        self.assertIn("user_steamid", demo.tirs.columns)

    def test_empty_or_missing_demo(self):
        demo = DemoData("nonexistent_demo_file.dem")
        self.assertFalse(demo.is_valid)
        self.assertTrue(demo.ticks.empty)

        aim = analyze_aimbot(demo, "123")
        self.assertEqual(aim.metrics["aim_p99"], 0.0)

        bhop = analyze_bhop(demo, "123")
        self.assertEqual(bhop.metrics["bhop_ratio_parfaits"], 0.0)

        wh = analyze_wallhack(demo, "123")
        self.assertEqual(wh.metrics["wh_ratio_lock_strict"], 0.0)


if __name__ == "__main__":
    unittest.main()
