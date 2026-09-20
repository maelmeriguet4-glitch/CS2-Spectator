from src.core.export import export_player_report

class PlayerMock:
    def __init__(self):
        self.name = "Xx_Sniper_xX"
        self.steamid = "STEAM_0:1:98765432"
        self.verdict = "CHEATER"
        self.suspicion_score = 92.4
        self.violation_flags = ["[AIMBOT: Snap 22.4°/tick]"]

filepath = export_player_report(PlayerMock())
print(f"OK {filepath}")
