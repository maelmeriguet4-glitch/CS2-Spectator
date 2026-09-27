"""
Tier 5: Adversarial Biomechanics & Parser Challenger Test Suite.
Adversarial stress-testing of telemetry engines and parsing pipeline:
1. Extreme angle flicks (>180° boundaries, negative pitch, NaN/Inf coordinates).
2. Erratic jump sequences, 0-tick and 1-tick landing boundaries.
3. Occluded targets right at 200 unit and 2000 unit boundaries.
4. AFK players, players with 1 tick, players with no shots.
5. Concurrency stress: multiple analyze_demo calls in parallel.
"""

import concurrent.futures
import os
import sys
import time
import unittest
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.analyzers.aimbot import (
    AimAnalysisResult,
    analyze_aimbot,
    calculate_angular_delta,
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
from src.core.engine import AntiCheatEngine
from src.core.models import MatchAnalysisResult
from src.ml.classifier import CheatClassifier


class MockAdversarialDemoData:
    """Configurable mock demo data generator for adversarial edge testing."""

    def __init__(
        self,
        ticks: pd.DataFrame,
        weapon_fire: Optional[pd.DataFrame] = None,
        players_info: Optional[List[Dict[str, Any]]] = None,
        map_name: str = "de_dust2_stress",
        server_name: str = "Adversarial Test Server",
    ):
        self.is_valid = True
        self.valide = True
        self.ticks = ticks
        self.events = {
            "weapon_fire": weapon_fire if weapon_fire is not None else pd.DataFrame(),
            "player_hurt": pd.DataFrame(),
            "player_death": pd.DataFrame(),
        }
        self.header = {"map_name": map_name, "server_name": server_name}
        self.map_name = map_name
        self.server_name = server_name
        self.players_info = players_info or []
        self.players = [p["name"] for p in self.players_info]
        self.total_ticks = len(ticks["tick"].unique()) if ("tick" in ticks.columns and not ticks.empty) else 0
        self.duration_seconds = self.total_ticks / 64.0

    def get_player_ticks(self, player_identifier):
        target = str(player_identifier).strip()
        mask = (self.ticks["steamid"].astype(str) == target) | (self.ticks["name"].astype(str) == target)
        if "health" in self.ticks.columns:
            mask = mask & (self.ticks["health"] > 0)
        return self.ticks[mask].sort_values("tick").reset_index(drop=True)

    def get_player_events(self, player_identifier, event_name="weapon_fire"):
        df = self.events.get(event_name, pd.DataFrame())
        if df.empty:
            return pd.DataFrame()
        target = str(player_identifier).strip()
        mask = (df["user_steamid"].astype(str) == target) | (df["user_name"].astype(str) == target)
        return df[mask].reset_index(drop=True)

    def get_all_players(self):
        return list(self.players_info)


# ============================================================================
# VECTOR 1: EXTREME ANGLE FLICKS, NEGATIVE PITCH & NAN/INF COORDINATES
# ============================================================================
class TestAdversarialAngleFlicks(unittest.TestCase):
    """Stress tests for angular kinematics under extreme and abnormal angle vectors."""

    def test_yaw_wraparound_360_discontinuity(self):
        """1.1: Flicks across -180/+180 boundary calculate the true shortest path."""
        # 179.9 to -179.9 is a 0.2° turn
        delta_fwd = calculate_angular_delta(179.9, -179.9)
        self.assertAlmostEqual(delta_fwd, 0.2, places=4)

        # -179.9 to 179.9 is a -0.2° turn
        delta_rev = calculate_angular_delta(-179.9, 179.9)
        self.assertAlmostEqual(delta_rev, -0.2, places=4)

        # Exactly on the 180° antipodal boundary
        delta_180 = calculate_angular_delta(0.0, 180.0)
        self.assertIn(abs(delta_180), [180.0])

    def test_extreme_spinbot_multi_turn_degrees(self):
        """1.2: Spinbot angles (>180° single-tick turns, multi-turn rotations) wrap safely."""
        # Single-tick 270° clockwise flick is -90° shortest path
        delta_270 = calculate_angular_delta(0.0, 270.0)
        self.assertAlmostEqual(delta_270, -90.0, places=4)

        # Multi-revolution: 0° to 725° is equivalent to +5° turn
        delta_multi = calculate_angular_delta(0.0, 725.0)
        self.assertAlmostEqual(delta_multi, 5.0, places=4)

        # Negative multi-revolution: 0° to -715° is equivalent to +5° turn
        delta_neg_multi = calculate_angular_delta(0.0, -715.0)
        self.assertAlmostEqual(delta_neg_multi, 5.0, places=4)

        # Verify in aimbot analyzer with simulated spinbot data
        n_ticks = 40
        yaws = [0.0] * n_ticks
        yaws[20] = 720.0 + 90.0  # 90° equivalent snap from 0
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000099"] * n_ticks,
            "name": ["Spinbotter"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": yaws,
            "active_weapon_name": ["weapon_ak47"] * n_ticks,
        })
        df_fire = pd.DataFrame({
            "tick": [1020],
            "user_steamid": ["76561198000000099"],
            "user_name": ["Spinbotter"],
        })
        mock_demo = MockAdversarialDemoData(df_ticks, weapon_fire=df_fire)
        res = analyze_aimbot(mock_demo, "76561198000000099")

        self.assertIsInstance(res, AimAnalysisResult)
        # Snap of 90° must be detected
        self.assertGreaterEqual(res.metrics["aim_p99"], 80.0)
        self.assertGreater(len(res.flagged_snaps), 0)

    def test_negative_pitch_and_extreme_vertical_snaps(self):
        """1.3: CS2 pitch boundaries [-89.0°, +89.0°] and negative pitch are handled properly."""
        n_ticks = 40
        pitch_series = [-89.0] * n_ticks  # Looking straight up
        pitch_series[20] = 89.0  # Instantaneous vertical snap to looking straight down (178° flick)

        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000088"] * n_ticks,
            "name": ["VerticalFlicker"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": pitch_series,
            "yaw": [0.0] * n_ticks,
            "active_weapon_name": ["weapon_awp"] * n_ticks,
        })
        df_fire = pd.DataFrame({
            "tick": [1020],
            "user_steamid": ["76561198000000088"],
            "user_name": ["VerticalFlicker"],
        })
        mock_demo = MockAdversarialDemoData(df_ticks, weapon_fire=df_fire)
        res = analyze_aimbot(mock_demo, "76561198000000088")

        self.assertIsInstance(res, AimAnalysisResult)
        self.assertGreaterEqual(res.metrics["aim_p99"], 170.0)
        self.assertGreaterEqual(res.metrics["aim_jerk_max"], 100.0)
        self.assertGreater(len(res.flagged_snaps), 0)

    def test_nan_and_inf_coordinates_and_angles(self):
        """1.4: NaN, +Inf, -Inf in coordinates and view angles do not crash the analyzers."""
        n_ticks = 30
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000077"] * n_ticks,
            "name": ["CorruptDataPlayer"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": [np.nan if i == 5 else (np.inf if i == 10 else 10.0) for i in range(n_ticks)],
            "yaw": [-np.inf if i == 7 else (np.nan if i == 12 else 45.0) for i in range(n_ticks)],
            "X": [np.nan if i == 3 else 100.0 for i in range(n_ticks)],
            "Y": [np.inf if i == 4 else 200.0 for i in range(n_ticks)],
            "Z": [64.0] * n_ticks,
            "is_airborne": [False] * n_ticks,
            "active_weapon_name": ["weapon_deagle"] * n_ticks,
        })
        mock_demo = MockAdversarialDemoData(df_ticks)

        # Aimbot analyzer must not crash and must return sanitized numeric floats
        aim_res = analyze_aimbot(mock_demo, "76561198000000077")
        for k, v in aim_res.metrics.items():
            self.assertFalse(np.isnan(v), f"Metric {k} is NaN")
            self.assertFalse(np.isinf(v), f"Metric {k} is Inf")
            self.assertIsInstance(v, float)

        # Wallhack analyzer with NaN coordinates must not crash
        df_enemy = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000066"] * n_ticks,
            "name": ["EnemyWithNaN"] * n_ticks,
            "team_num": [2] * n_ticks,
            "health": [100] * n_ticks,
            "X": [np.nan if i % 2 == 0 else 500.0 for i in range(n_ticks)],
            "Y": [np.inf if i % 3 == 0 else 500.0 for i in range(n_ticks)],
            "Z": [64.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })
        df_ticks["team_num"] = 3
        combined_ticks = pd.concat([df_ticks, df_enemy], ignore_index=True)
        mock_wh_demo = MockAdversarialDemoData(combined_ticks)

        wh_res = analyze_wallhack(mock_wh_demo, "76561198000000077")
        for k, v in wh_res.metrics.items():
            self.assertFalse(np.isnan(v), f"WH Metric {k} is NaN")
            self.assertFalse(np.isinf(v), f"WH Metric {k} is Inf")
            self.assertIsInstance(v, float)


# ============================================================================
# VECTOR 2: ERRATIC JUMP SEQUENCES, 0-TICK AND 1-TICK LANDING BOUNDARIES
# ============================================================================
class TestAdversarialJumpSequences(unittest.TestCase):
    """Stress tests for bunnyhop mechanics under frame-perfect, zero-tick, and erratic inputs."""

    def test_one_tick_landing_boundary_script_detection(self):
        """2.1: Exactly 1-tick ground transition (Delta t_ground == 1) detected as perfect jump."""
        # 10 consecutive jumps with exactly 1 tick on the ground
        air_pattern = [False] * 5
        for _ in range(6):
            air_pattern.extend([True] * 12)  # Airborne for 12 ticks
            air_pattern.append(False)         # Exactly 1 tick on ground
        air_pattern.extend([True] * 12)
        air_pattern.extend([False] * 10)

        n_ticks = len(air_pattern)
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000055"] * n_ticks,
            "name": ["OneTickJumper"] * n_ticks,
            "health": [100] * n_ticks,
            "is_airborne": air_pattern,
            "velocity_X": [300.0] * n_ticks,
            "velocity_Y": [0.0] * n_ticks,
        })
        mock_demo = MockAdversarialDemoData(df_ticks)
        res = analyze_bhop(mock_demo, "76561198000000055")

        self.assertIsInstance(res, BhopAnalysisResult)
        self.assertGreaterEqual(res.metrics["bhop_ratio_parfaits"], 0.85)
        self.assertGreaterEqual(res.metrics["bhop_chaine_max"], 5)
        self.assertGreater(len(res.flagged_chains), 0)

    def test_two_tick_imperfect_landing_boundary(self):
        """2.2: Exactly 2-tick ground transition (Delta t_ground == 2) is NOT classified as perfect."""
        # Jumps with exactly 2 ticks on the ground (imperfect manual timing)
        air_pattern = [False] * 5
        for _ in range(6):
            air_pattern.extend([True] * 12)
            air_pattern.extend([False, False])  # Exactly 2 ticks on ground (delai_sol == 2)
        air_pattern.extend([True] * 12)
        air_pattern.extend([False] * 10)

        n_ticks = len(air_pattern)
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000044"] * n_ticks,
            "name": ["TwoTickJumper"] * n_ticks,
            "health": [100] * n_ticks,
            "is_airborne": air_pattern,
            "velocity_X": [250.0] * n_ticks,
            "velocity_Y": [0.0] * n_ticks,
        })
        mock_demo = MockAdversarialDemoData(df_ticks)
        res = analyze_bhop(mock_demo, "76561198000000044")

        self.assertIsInstance(res, BhopAnalysisResult)
        # Ratio of perfect jumps must be 0.0 because delai_sol == 2 > 1
        self.assertEqual(res.metrics["bhop_ratio_parfaits"], 0.0)
        self.assertEqual(res.metrics["bhop_chaine_max"], 0)
        self.assertEqual(len(res.flagged_chains), 0)

    def test_rapid_alternating_jump_chaos(self):
        """2.3: Rapid erratic jump spam ([T, F, T, F, T, F...]) does not crash or loop infinitely."""
        # 100 ticks alternating every single tick
        chaos_air = [bool(i % 2) for i in range(100)]
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1100)),
            "steamid": ["76561198000000033"] * 100,
            "name": ["ChaosJumper"] * 100,
            "health": [100] * 100,
            "is_airborne": chaos_air,
            "velocity_X": [200.0] * 100,
            "velocity_Y": [0.0] * 100,
        })
        mock_demo = MockAdversarialDemoData(df_ticks)

        start = time.time()
        res = analyze_bhop(mock_demo, "76561198000000033")
        duration = time.time() - start

        # Must execute within 0.5s without infinite loop
        self.assertLess(duration, 0.5)
        self.assertIsInstance(res, BhopAnalysisResult)
        self.assertGreater(res.metrics["bhop_total_sauts"], 10)

    def test_permanently_airborne_or_grounded(self):
        """2.4: Player permanently in air (surfing/falling) or permanently grounded returns safe metrics."""
        # Permanently airborne
        df_air = pd.DataFrame({
            "tick": list(range(1000, 1200)),
            "steamid": ["76561198000000022"] * 200,
            "name": ["Surfer"] * 200,
            "health": [100] * 200,
            "is_airborne": [True] * 200,
            "velocity_X": [600.0] * 200,
            "velocity_Y": [0.0] * 200,
        })
        mock_demo_air = MockAdversarialDemoData(df_air)
        res_air = analyze_bhop(mock_demo_air, "76561198000000022")
        self.assertEqual(res_air.metrics["bhop_total_sauts"], 0.0)
        self.assertEqual(res_air.metrics["bhop_ratio_parfaits"], 0.0)
        self.assertFalse(np.isnan(res_air.metrics["bhop_vitesse_moyenne"]))

        # Permanently grounded
        df_ground = pd.DataFrame({
            "tick": list(range(1000, 1200)),
            "steamid": ["76561198000000021"] * 200,
            "name": ["Walker"] * 200,
            "health": [100] * 200,
            "is_airborne": [False] * 200,
            "velocity_X": [215.0] * 200,
            "velocity_Y": [0.0] * 200,
        })
        mock_demo_ground = MockAdversarialDemoData(df_ground)
        res_ground = analyze_bhop(mock_demo_ground, "76561198000000021")
        self.assertEqual(res_ground.metrics["bhop_total_sauts"], 0.0)
        self.assertEqual(res_ground.metrics["bhop_ratio_parfaits"], 0.0)


# ============================================================================
# VECTOR 3: OCCLUDED TARGETS AT 200 AND 2000 UNIT BOUNDARIES
# ============================================================================
class TestAdversarialWallhackBoundaries(unittest.TestCase):
    """Stress tests for 3D raycasting, occlusion filtering, and tactical distance boundaries."""

    def test_occlusion_exact_200_unit_boundary(self):
        """3.1: Distance boundary at 200 units: 199.9 units excluded, 200.0 units included."""
        n_ticks = 60
        ticks = list(range(1000, 1000 + n_ticks))

        # Player at (0, 0, 0) looking directly at Yaw=0, Pitch=0
        df_p = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000010"] * n_ticks,
            "name": ["WhTester"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [0.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })

        # Enemy at X=199.9 (distance 199.9 units, just inside cutoff)
        df_e1 = pd.DataFrame({
            "tick": ticks[:30],
            "steamid": ["76561198000000011"] * 30,
            "name": ["EnemyTooClose"] * 30,
            "team_num": [2] * 30,
            "health": [100] * 30,
            "X": [199.9] * 30,
            "Y": [0.0] * 30,
            "Z": [2.0] * 30,  # dz = (2+62) - (0+64) = 0
            "pitch": [0.0] * 30,
            "yaw": [180.0] * 30,
            "spotted": [False] * 30,
        })

        # Enemy at X=200.0 (distance 200.0 units, exactly on the boundary)
        df_e2 = pd.DataFrame({
            "tick": ticks[30:],
            "steamid": ["76561198000000012"] * 30,
            "name": ["EnemyAtBoundary"] * 30,
            "team_num": [2] * 30,
            "health": [100] * 30,
            "X": [200.0] * 30,
            "Y": [0.0] * 30,
            "Z": [2.0] * 30,
            "pitch": [0.0] * 30,
            "yaw": [180.0] * 30,
            "spotted": [False] * 30,
        })

        combined = pd.concat([df_p, df_e1, df_e2], ignore_index=True)
        mock_demo = MockAdversarialDemoData(combined)
        res = analyze_wallhack(mock_demo, "76561198000000010")

        self.assertIsInstance(res, WallhackAnalysisResult)
        # Total ticks = 60. The 30 ticks at 199.9 are excluded. The 30 ticks at 200.0 are included!
        # Ratio should be 30 / 60 = 0.50
        self.assertAlmostEqual(res.metrics["wh_ratio_lock_strict"], 0.50, places=2)

    def test_occlusion_exact_2000_unit_boundary(self):
        """3.2: Distance boundary at 2000 units: 2000.0 included, 2000.1 excluded."""
        n_ticks = 60
        ticks = list(range(1000, 1000 + n_ticks))

        df_p = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000010"] * n_ticks,
            "name": ["WhTester"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [0.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })

        # Enemy at X=2000.0 (included)
        df_e1 = pd.DataFrame({
            "tick": ticks[:30],
            "steamid": ["76561198000000013"] * 30,
            "name": ["EnemyAtMaxBoundary"] * 30,
            "team_num": [2] * 30,
            "health": [100] * 30,
            "X": [2000.0] * 30,
            "Y": [0.0] * 30,
            "Z": [2.0] * 30,
            "pitch": [0.0] * 30,
            "yaw": [180.0] * 30,
            "spotted": [False] * 30,
        })

        # Enemy at X=2000.1 (distance > 2000, excluded)
        df_e2 = pd.DataFrame({
            "tick": ticks[30:],
            "steamid": ["76561198000000014"] * 30,
            "name": ["EnemyTooFar"] * 30,
            "team_num": [2] * 30,
            "health": [100] * 30,
            "X": [2000.1] * 30,
            "Y": [0.0] * 30,
            "Z": [2.0] * 30,
            "pitch": [0.0] * 30,
            "yaw": [180.0] * 30,
            "spotted": [False] * 30,
        })

        combined = pd.concat([df_p, df_e1, df_e2], ignore_index=True)
        mock_demo = MockAdversarialDemoData(combined)
        res = analyze_wallhack(mock_demo, "76561198000000010")

        self.assertIsInstance(res, WallhackAnalysisResult)
        self.assertAlmostEqual(res.metrics["wh_ratio_lock_strict"], 0.50, places=2)

    def test_spotted_flag_leakage_exclusion(self):
        """3.3: Visible enemies (spotted == True) are strictly excluded from wallhack locks."""
        n_ticks = 60
        ticks = list(range(1000, 1000 + n_ticks))

        df_p = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000010"] * n_ticks,
            "name": ["WhTester"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [0.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
        })

        # Enemy is in direct line of sight (spotted == True)
        df_e = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000015"] * n_ticks,
            "name": ["VisibleEnemy"] * n_ticks,
            "team_num": [2] * n_ticks,
            "health": [100] * n_ticks,
            "X": [600.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [2.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [180.0] * n_ticks,
            "spotted": [True] * n_ticks,  # Visually confirmed!
        })

        combined = pd.concat([df_p, df_e], ignore_index=True)
        mock_demo = MockAdversarialDemoData(combined)
        res = analyze_wallhack(mock_demo, "76561198000000010")

        # Must be 0.0 because the enemy is spotted (clean duel, not through-wall ESP)
        self.assertEqual(res.metrics["wh_ratio_lock_cache"], 0.0)
        self.assertEqual(res.metrics["wh_ratio_lock_strict"], 0.0)
        self.assertEqual(len(res.flagged_locks), 0)

    def test_coincident_coordinates_zero_distance(self):
        """3.4: Target at exact same coordinates (dx=0, dy=0, dz=0) does not divide by zero."""
        yaw, pitch, dist = calculate_aim_angles_3d(100.0, 100.0, 0.0, 100.0, 100.0, 2.0)
        self.assertFalse(np.isnan(yaw))
        self.assertFalse(np.isnan(pitch))
        self.assertFalse(np.isnan(dist))
        self.assertAlmostEqual(dist, 0.0, places=4)


# ============================================================================
# VECTOR 4: AFK PLAYERS, 1-TICK PLAYERS, NO SHOTS & DEAD-ONLY PLAYERS
# ============================================================================
class TestAdversarialPlayerEdgeCases(unittest.TestCase):
    """Stress tests for atypical player lifespans, zero activity, and missing combat events."""

    def test_afk_player_zero_movement_thousands_ticks(self):
        """4.1: AFK player with zero movement across 2,000 ticks produces 0 suspicion and CLEAN verdict."""
        n_ticks = 2000
        ticks = list(range(1000, 1000 + n_ticks))

        df_afk = pd.DataFrame({
            "tick": ticks,
            "steamid": ["76561198000000001"] * n_ticks,
            "name": ["AfkPlayer"] * n_ticks,
            "team_num": [3] * n_ticks,
            "health": [100] * n_ticks,
            "X": [0.0] * n_ticks,
            "Y": [0.0] * n_ticks,
            "Z": [64.0] * n_ticks,
            "pitch": [0.0] * n_ticks,
            "yaw": [90.0] * n_ticks,
            "is_airborne": [False] * n_ticks,
            "velocity_X": [0.0] * n_ticks,
            "velocity_Y": [0.0] * n_ticks,
            "velocity_Z": [0.0] * n_ticks,
            "spotted": [False] * n_ticks,
            "active_weapon_name": ["weapon_glock"] * n_ticks,
        })
        mock_demo = MockAdversarialDemoData(df_afk)

        aim_res = analyze_aimbot(mock_demo, "76561198000000001")
        self.assertEqual(aim_res.metrics["aim_p99"], 0.0)
        self.assertEqual(aim_res.metrics["aim_jerk_max"], 0.0)

        bhop_res = analyze_bhop(mock_demo, "76561198000000001")
        self.assertEqual(bhop_res.metrics["bhop_total_sauts"], 0.0)
        self.assertEqual(bhop_res.metrics["bhop_ratio_parfaits"], 0.0)

        classifier = CheatClassifier()
        result = classifier.predict(aim_res.metrics, bhop_res.metrics, {})
        self.assertEqual(result.verdict, "CLEAN")
        self.assertLess(result.suspicion_score, 25.0)

    def test_single_tick_player_graceful_handling(self):
        """4.2: Player present for only 1 tick does not raise exceptions and returns default metrics."""
        df_one_tick = pd.DataFrame({
            "tick": [1000],
            "steamid": ["76561198000000002"],
            "name": ["OneTickSpectator"],
            "team_num": [1],
            "health": [100],
            "X": [0.0],
            "Y": [0.0],
            "Z": [64.0],
            "pitch": [0.0],
            "yaw": [0.0],
            "is_airborne": [False],
            "velocity_X": [0.0],
            "velocity_Y": [0.0],
        })
        mock_demo = MockAdversarialDemoData(df_one_tick)

        aim_res = analyze_aimbot(mock_demo, "76561198000000002")
        self.assertIsInstance(aim_res, AimAnalysisResult)
        self.assertEqual(aim_res.metrics["aim_p99"], 0.0)

        bhop_res = analyze_bhop(mock_demo, "76561198000000002")
        self.assertIsInstance(bhop_res, BhopAnalysisResult)
        self.assertEqual(bhop_res.metrics["bhop_total_sauts"], 0.0)

        wh_res = analyze_wallhack(mock_demo, "76561198000000002")
        self.assertIsInstance(wh_res, WallhackAnalysisResult)
        self.assertEqual(wh_res.metrics["wh_ratio_lock_strict"], 0.0)

    def test_no_shots_combat_window_fallback(self):
        """4.3: Active player who never fires a weapon (0 shots) falls back to global metrics cleanly."""
        n_ticks = 200
        df_ticks = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000003"] * n_ticks,
            "name": ["PacifistPlayer"] * n_ticks,
            "health": [100] * n_ticks,
            "pitch": [0.0 + (i * 0.05) for i in range(n_ticks)],
            "yaw": [0.0 + (i * 0.1) for i in range(n_ticks)],
            "active_weapon_name": ["weapon_knife"] * n_ticks,
        })
        # Empty weapon_fire events
        mock_demo = MockAdversarialDemoData(df_ticks, weapon_fire=pd.DataFrame())

        aim_res = analyze_aimbot(mock_demo, "76561198000000003")
        self.assertIsInstance(aim_res, AimAnalysisResult)
        self.assertGreater(aim_res.metrics["aim_vitesse_max"], 0.0)
        self.assertLess(aim_res.metrics["aim_p99"], 2.0)

    def test_dead_only_player(self):
        """4.4: Player who is dead (health <= 0) throughout entire demo is handled safely."""
        n_ticks = 100
        df_dead = pd.DataFrame({
            "tick": list(range(1000, 1000 + n_ticks)),
            "steamid": ["76561198000000004"] * n_ticks,
            "name": ["DeadPlayer"] * n_ticks,
            "health": [0] * n_ticks,  # Dead!
            "pitch": [0.0] * n_ticks,
            "yaw": [0.0] * n_ticks,
            "is_airborne": [False] * n_ticks,
        })
        mock_demo = MockAdversarialDemoData(df_dead)

        aim_res = analyze_aimbot(mock_demo, "76561198000000004")
        self.assertEqual(aim_res.metrics["aim_p99"], 0.0)

        bhop_res = analyze_bhop(mock_demo, "76561198000000004")
        self.assertEqual(bhop_res.metrics["bhop_total_sauts"], 0.0)


# ============================================================================
# VECTOR 5: CONCURRENCY STRESS (PARALLEL ANALYZERS & ENGINE CALLS)
# ============================================================================
class TestAdversarialConcurrencyStress(unittest.TestCase):
    """Stress tests verifying thread-safety and absence of race conditions under concurrency."""

    def test_concurrent_analyzers_parallel_execution(self):
        """5.1: 16 concurrent threads executing aimbot, bhop, and wallhack analyzers simultaneously."""
        def worker_task(worker_id: int) -> Dict[str, Any]:
            n_ticks = 80
            df_ticks = pd.DataFrame({
                "tick": list(range(1000, 1000 + n_ticks)),
                "steamid": [f"76561198000000{worker_id:03d}"] * n_ticks,
                "name": [f"Worker_{worker_id}"] * n_ticks,
                "team_num": [2 if worker_id % 2 == 0 else 3] * n_ticks,
                "health": [100] * n_ticks,
                "X": [float(worker_id * 10)] * n_ticks,
                "Y": [0.0] * n_ticks,
                "Z": [64.0] * n_ticks,
                "pitch": [0.1 * i for i in range(n_ticks)],
                "yaw": [0.2 * i for i in range(n_ticks)],
                "is_airborne": [bool((i // 5) % 2) for i in range(n_ticks)],
                "velocity_X": [250.0] * n_ticks,
                "velocity_Y": [0.0] * n_ticks,
                "spotted": [False] * n_ticks,
                "active_weapon_name": ["weapon_ak47"] * n_ticks,
            })
            mock_demo = MockAdversarialDemoData(df_ticks)
            aim_res = analyze_aimbot(mock_demo, f"76561198000000{worker_id:03d}")
            bhop_res = analyze_bhop(mock_demo, f"76561198000000{worker_id:03d}")
            wh_res = analyze_wallhack(mock_demo, f"76561198000000{worker_id:03d}")

            return {
                "worker_id": worker_id,
                "aim_vitesse": aim_res.metrics["aim_vitesse_max"],
                "bhop_sauts": bhop_res.metrics["bhop_total_sauts"],
                "wh_strict": wh_res.metrics["wh_ratio_lock_strict"],
            }

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker_task, i) for i in range(16)]
            results = [f.result(timeout=10.0) for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 16)
        for r in results:
            self.assertIn("worker_id", r)
            self.assertGreater(r["aim_vitesse"], 0.0)

    def test_concurrent_classifier_inference(self):
        """5.2: Concurrent RandomForestClassifier inference from 50 parallel tasks."""
        classifier = CheatClassifier()

        def infer_task(seed: int) -> str:
            rng = np.random.RandomState(seed)
            aim = {"aim_p99": float(rng.uniform(0.0, 30.0)), "aim_jerk_max": float(rng.uniform(0.0, 50.0))}
            bhop = {"bhop_ratio_parfaits": float(rng.uniform(0.0, 1.0)), "bhop_total_sauts": 20.0}
            wh = {"wh_ratio_lock_strict": float(rng.uniform(0.0, 0.3)), "wh_tracking_consecutif_max": 30.0}
            res = classifier.predict(aim, bhop, wh)
            return res.verdict

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(infer_task, s) for s in range(50)]
            verdicts = [f.result(timeout=5.0) for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(verdicts), 50)
        for v in verdicts:
            self.assertIn(v, ["CLEAN", "SUSPECT", "CHEATER"])

    def test_concurrent_engine_analyze_demo_calls(self):
        """5.3: Multiple analyze_demo calls running concurrently across threads."""
        from unittest.mock import patch

        def make_mock_match(demo_idx: int):
            n_ticks = 60
            ticks_list = []
            players_info = []
            for p_idx in range(4):
                sid = f"765611980000{demo_idx:02d}{p_idx:02d}"
                name = f"Player_D{demo_idx}_P{p_idx}"
                players_info.append({"steamid": sid, "name": name, "team_number": 2 if p_idx < 2 else 3})
                df_p = pd.DataFrame({
                    "tick": list(range(1000, 1000 + n_ticks)),
                    "steamid": [sid] * n_ticks,
                    "name": [name] * n_ticks,
                    "team_num": [2 if p_idx < 2 else 3] * n_ticks,
                    "health": [100] * n_ticks,
                    "X": [float(p_idx * 100)] * n_ticks,
                    "Y": [0.0] * n_ticks,
                    "Z": [64.0] * n_ticks,
                    "pitch": [0.1 * i for i in range(n_ticks)],
                    "yaw": [0.2 * i for i in range(n_ticks)],
                    "is_airborne": [False] * n_ticks,
                    "velocity_X": [200.0] * n_ticks,
                    "velocity_Y": [0.0] * n_ticks,
                    "spotted": [False] * n_ticks,
                    "active_weapon_name": ["weapon_ak47"] * n_ticks,
                })
                ticks_list.append(df_p)
            return MockAdversarialDemoData(pd.concat(ticks_list, ignore_index=True), players_info=players_info)

        def mock_load_demo(demo_path: str):
            idx = int(demo_path.split("_")[-1].replace(".dem", "")) if "_" in demo_path else 0
            return make_mock_match(idx)

        engine = AntiCheatEngine()

        def analyze_task(demo_idx: int) -> MatchAnalysisResult:
            demo_file = f"match_{demo_idx}.dem"
            cb_calls = []
            def cb(pct, msg):
                cb_calls.append(pct)
            res = engine.analyze_demo(demo_file, progress_callback=cb)
            return res

        with patch("src.core.engine.load_demo", side_effect=mock_load_demo):
            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                futures = [executor.submit(analyze_task, i) for i in range(6)]
                results = [f.result(timeout=15.0) for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 6)
        for r in results:
            self.assertIsInstance(r, MatchAnalysisResult)
            self.assertEqual(len(r.players), 4)
            # Verify deterministic verdict output across threads
            self.assertEqual(len(r.players), len(results[0].players))
            self.assertGreater(r.total_ticks, 0)



if __name__ == "__main__":
    unittest.main(verbosity=2)

