import unittest

import pandas as pd

from src.analyzers.triggerbot import (
    TriggerbotResult,
    analyze_triggerbot,
)


class MockTriggerbotDemoData:
    def __init__(self, ticks_df: pd.DataFrame, events_df: pd.DataFrame = None, is_valid: bool = True):
        self.ticks = ticks_df
        self.events = events_df if events_df is not None else pd.DataFrame()
        self.is_valid = is_valid
        self.valide = is_valid
        self.players = ['Suspect', 'Target']

    def get_player_ticks(self, identifier: str) -> pd.DataFrame:
        if self.ticks.empty:
            return pd.DataFrame()
        return self.ticks[self.ticks['name'] == identifier].copy()

    def obtenir_donnees_joueur(self, identifier: str) -> pd.DataFrame:
        return self.get_player_ticks(identifier)

class TestTriggerbotAnalyzer(unittest.TestCase):
    def test_no_shots_returns_empty_metrics(self):
        ticks = pd.DataFrame({
            'tick': range(50),
            'name': ['CleanPlayer'] * 50,
            'steamid': ['76561198000000001'] * 50,
            'health': [100] * 50,
            'team_num': [2] * 50,
            'X': [0.0] * 50, 'Y': [0.0] * 50, 'Z': [0.0] * 50,
            'yaw': [0.0] * 50, 'pitch': [0.0] * 50,
        })
        demo = MockTriggerbotDemoData(ticks)
        result = analyze_triggerbot(demo, 'CleanPlayer')
        self.assertIsInstance(result, TriggerbotResult)
        self.assertEqual(result.metrics['triggerbot_total_shots_analyzed'], 0)
        self.assertEqual(len(result.flagged_events), 0)

    def test_empty_ticks_graceful(self):
        demo = MockTriggerbotDemoData(pd.DataFrame(), is_valid=False)
        result = analyze_triggerbot(demo, 'NonExistent')
        self.assertIsInstance(result, TriggerbotResult)
        self.assertEqual(result.metrics['triggerbot_total_shots_analyzed'], 0)

if __name__ == '__main__':
    unittest.main()
