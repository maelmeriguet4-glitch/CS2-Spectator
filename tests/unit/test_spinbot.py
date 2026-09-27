import unittest

import pandas as pd

from src.analyzers.spinbot import SpinbotResult, analyze_spinbot


class MockDemoData:
    def __init__(self, ticks_df: pd.DataFrame, is_valid: bool = True):
        self.ticks = ticks_df
        self.is_valid = is_valid
        self.valide = is_valid
        self.players = ['Suspect', 'CleanPlayer']

    def get_player_ticks(self, identifier: str) -> pd.DataFrame:
        if self.ticks.empty:
            return pd.DataFrame()
        return self.ticks[self.ticks['name'] == identifier].copy()

    def obtenir_donnees_joueur(self, identifier: str) -> pd.DataFrame:
        return self.get_player_ticks(identifier)

class TestSpinbotAnalyzer(unittest.TestCase):
    def test_clean_player_no_spin(self):
        n_ticks = 100
        ticks = pd.DataFrame({
            'tick': range(n_ticks),
            'name': ['CleanPlayer'] * n_ticks,
            'steamid': ['76561198000000001'] * n_ticks,
            'yaw': [float(i * 0.5) for i in range(n_ticks)],
            'pitch': [0.0] * n_ticks,
            'velocity_X': [150.0] * n_ticks,
            'velocity_Y': [0.0] * n_ticks,
        })
        demo = MockDemoData(ticks)
        result = analyze_spinbot(demo, 'CleanPlayer')
        self.assertIsInstance(result, SpinbotResult)
        self.assertLess(result.metrics['spinbot_yaw_speed_max'], 10.0)
        self.assertEqual(result.metrics['spinbot_pitch_violations'], 0)
        self.assertEqual(result.metrics['spinbot_yaw_spin_windows'], 0)
        self.assertEqual(len(result.flagged_events), 0)

    def test_spinbot_continuous_yaw_rotation(self):
        n_ticks = 60
        ticks = pd.DataFrame({
            'tick': range(n_ticks),
            'name': ['Suspect'] * n_ticks,
            'steamid': ['76561198000000002'] * n_ticks,
            'yaw': [(i * 120.0) % 360.0 - 180.0 for i in range(n_ticks)],
            'pitch': [10.0] * n_ticks,
            'velocity_X': [50.0] * n_ticks,
            'velocity_Y': [50.0] * n_ticks,
        })
        demo = MockDemoData(ticks)
        result = analyze_spinbot(demo, 'Suspect')
        self.assertIsInstance(result, SpinbotResult)
        self.assertGreater(result.metrics['spinbot_yaw_speed_max'], 90.0)
        self.assertGreater(result.metrics['spinbot_yaw_spin_windows'], 0)

    def test_anti_aim_pitch_violation(self):
        n_ticks = 40
        pitches = [10.0] * 30 + [120.0, -120.0, 180.0] + [10.0] * 7
        ticks = pd.DataFrame({
            'tick': range(n_ticks),
            'name': ['Suspect'] * n_ticks,
            'steamid': ['76561198000000003'] * n_ticks,
            'yaw': [0.0] * n_ticks,
            'pitch': pitches,
            'velocity_X': [0.0] * n_ticks,
            'velocity_Y': [0.0] * n_ticks,
        })
        demo = MockDemoData(ticks)
        result = analyze_spinbot(demo, 'Suspect')
        self.assertEqual(result.metrics['spinbot_pitch_violations'], 3)

    def test_empty_or_short_ticks_graceful(self):
        ticks = pd.DataFrame({
            'tick': [1, 2],
            'name': ['Suspect', 'Suspect'],
            'steamid': ['123', '123'],
            'yaw': [0.0, 0.0],
            'pitch': [0.0, 0.0],
        })
        demo = MockDemoData(ticks)
        result = analyze_spinbot(demo, 'Suspect')
        self.assertIsInstance(result, SpinbotResult)
        self.assertEqual(result.metrics.get('spinbot_yaw_speed_max', 0.0), 0.0)

if __name__ == '__main__':
    unittest.main()
