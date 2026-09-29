"""
Shared test configuration, fixtures, and constants for CS2 Anti-Cheat test suite.
"""

import os
import sys
from typing import Any

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

DEMOS_DIR = os.path.join(REPO_ROOT, "demos")
TEST_DEMO_PATH = os.path.join(DEMOS_DIR, "test.dem")
MODEL_PATH = os.path.join(REPO_ROOT, "cerveau_vac_custom.pkl")
STEAM_REPLAYS_PATH = r"D:\SteamLibrary\steamapps\common\Counter-Strike Global Offensive\game\csgo\replays"

# Source 2 Demo magic header
SOURCE2_MAGIC_HEADER = b"PBDEMS2\x00"


def has_test_demo() -> bool:
    """Returns True if the 264MB test.dem exists."""
    return os.path.isfile(TEST_DEMO_PATH) and os.path.getsize(TEST_DEMO_PATH) > 1024 * 1024


def has_model_file() -> bool:
    """Returns True if cerveau_vac_custom.pkl exists."""
    return os.path.isfile(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 1000


def create_synthetic_demo_file(
    directory: str,
    filename: str = "synthetic_match.dem",
    header: bytes = SOURCE2_MAGIC_HEADER,
    payload_size: int = 2048,
) -> str:
    """Creates a temporary synthetic demo file with valid magic header."""
    file_path = os.path.join(directory, filename)
    with open(file_path, "wb") as f:
        f.write(header)
        f.write(b"\x00" * payload_size)
    return file_path


def create_sample_player_telemetry(
    steamid: str = "76561198069288826",
    name: str = "ENA",
    team_number: int = 3,
    suspicion_score: float = 12.5,
    verdict: str = "CLEAN",
    snap_max: float = 8.4,
    bhop_ratio: float = 0.15,
    wh_lock_strict: float = 0.02,
) -> Any:
    """Creates a sample PlayerTelemetry instance."""
    from src.core.models import PlayerTelemetry

    aim_metrics = {
        "aim_vitesse_max": snap_max * 1.1,
        "aim_p99": snap_max,
        "aim_jerk_moyen": 4.2,
        "aim_jerk_max": 9.1,
        "aim_ratio_micro_ajustements": 0.45,
        "aim_variance_vitesse": 12.3,
    }
    bhop_metrics = {
        "bhop_total_sauts": 24,
        "bhop_ratio_parfaits": bhop_ratio,
        "bhop_variance_sol": 18.5,
        "bhop_chaine_max": 2,
        "bhop_vitesse_moyenne": 248.0,
    }
    wh_metrics = {
        "wh_ratio_lock_cache": wh_lock_strict * 1.5,
        "wh_ratio_lock_strict": wh_lock_strict,
        "wh_tracking_consecutif_max": 4,
        "wh_distance_moyenne_verrous": 750.0,
    }

    flags = []
    if verdict == "CHEATER":
        flags = ["[AIMBOT: Snap 42.1°/tick]", "[WALLHACK: 18 Locks Mur]"]
    elif verdict == "SUSPECT":
        flags = ["[AIMBOT: Snap 28.5°/tick]"]

    return PlayerTelemetry(
        steamid=steamid,
        name=name,
        team_number=team_number,
        aim_metrics=aim_metrics,
        bhop_metrics=bhop_metrics,
        wh_metrics=wh_metrics,
        suspicion_score=suspicion_score,
        verdict=verdict,
        violation_flags=flags,
        combat_events=[],
    )


def create_sample_match_result(
    demo_path: str = "demos/test.dem",
    map_name: str = "de_inferno",
    server_name: str = "Valve CS2 Matchmaking",
) -> Any:
    """Creates a sample MatchAnalysisResult instance with 10 players."""
    from src.core.models import MatchAnalysisResult

    players = [
        create_sample_player_telemetry(
            steamid=f"7656119800000000{i}",
            name=f"Player_{i}",
            team_number=2 if i < 5 else 3,
            suspicion_score=85.0 if i == 0 else (45.0 if i == 1 else 10.0),
            verdict="CHEATER" if i == 0 else ("SUSPECT" if i == 1 else "CLEAN"),
        )
        for i in range(10)
    ]

    return MatchAnalysisResult(
        demo_path=demo_path,
        map_name=map_name,
        server_name=server_name,
        total_ticks=64000,
        duration_seconds=984.5,
        players=players,
        global_verdict="1 CHEATER DETECTED (Player_0) | 1 SUSPECT",
    )
