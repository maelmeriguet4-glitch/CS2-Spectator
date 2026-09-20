"""
Core data models and contracts for CS2 Anti-Cheat.
Defines ReplayInfo, PlayerTelemetry, and MatchAnalysisResult.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# Regex SteamID64 : exactement 17 chiffres commençant par 7656
_STEAMID64_PATTERN = re.compile(r"^\d{17}$")


@dataclass
class ReplayInfo:
    """Represents metadata for a discovered or imported CS2 demo file."""
    file_path: str
    file_name: str
    file_size_bytes: int
    modified_time: float
    map_name: Optional[str] = None
    server_name: Optional[str] = None

    @property
    def file_size_mb(self) -> float:
        """Returns file size in megabytes rounded to two decimal places."""
        return round(self.file_size_bytes / (1024 * 1024), 2)

    @property
    def formatted_size(self) -> str:
        """Returns human-readable formatted file size."""
        if self.file_size_bytes < 1024:
            return f"{self.file_size_bytes} B"
        elif self.file_size_bytes < 1024 * 1024:
            return f"{self.file_size_bytes / 1024:.1f} KB"
        elif self.file_size_bytes < 1024 * 1024 * 1024:
            return f"{self.file_size_bytes / (1024 * 1024):.1f} MB"
        return f"{self.file_size_bytes / (1024 * 1024 * 1024):.2f} GB"

    @property
    def formatted_time(self) -> str:
        """Returns ISO formatted modification timestamp (YYYY-MM-DD HH:MM:SS)."""
        try:
            return datetime.fromtimestamp(self.modified_time).strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return str(self.modified_time)


@dataclass
class PlayerTelemetry:
    """Biomechanical telemetry metrics, ML verdict, and violation flags for a player."""
    steamid: str = ""
    name: str = "Inconnu"
    team_number: int = 0  # 2: Terrorists (T), 3: Counter-Terrorists (CT)
    aim_metrics: Dict[str, float] = field(default_factory=dict)
    bhop_metrics: Dict[str, float] = field(default_factory=dict)
    wh_metrics: Dict[str, float] = field(default_factory=dict)
    spinbot_metrics: Dict[str, float] = field(default_factory=dict)
    triggerbot_metrics: Dict[str, float] = field(default_factory=dict)
    suspicion_score: float = 0.0  # 0.0 to 100.0
    verdict: str = "CLEAN"  # "CLEAN", "SUSPECT", "CHEATER"
    violation_flags: List[str] = field(default_factory=list)
    combat_events: List[Dict[str, Any]] = field(default_factory=list)

    def __post_init__(self):
        """Validation post-initialisation : clamp score, normaliser verdict."""
        # Clamp suspicion_score dans [0.0, 100.0]
        self.suspicion_score = max(0.0, min(100.0, float(self.suspicion_score)))
        # Normaliser le verdict
        valid_verdicts = {"CLEAN", "SUSPECT", "CHEATER"}
        if self.verdict not in valid_verdicts:
            self.verdict = "CLEAN"

    @property
    def is_valid_steamid(self) -> bool:
        """Vérifie si le SteamID64 est un identifiant numérique valide de 17 chiffres."""
        return bool(_STEAMID64_PATTERN.match(self.steamid))

    def to_dict(self) -> Dict[str, Any]:
        """Sérialise la télémétrie en dictionnaire JSON-compatible."""
        return {
            "steamid": self.steamid,
            "name": self.name,
            "team_number": self.team_number,
            "aim_metrics": dict(self.aim_metrics),
            "bhop_metrics": dict(self.bhop_metrics),
            "wh_metrics": dict(self.wh_metrics),
            "spinbot_metrics": dict(self.spinbot_metrics),
            "triggerbot_metrics": dict(self.triggerbot_metrics),
            "suspicion_score": self.suspicion_score,
            "verdict": self.verdict,
            "violation_flags": list(self.violation_flags),
            "combat_events": list(self.combat_events),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerTelemetry":
        """Désérialise un dictionnaire en PlayerTelemetry."""
        return cls(
            steamid=str(data.get("steamid", "")),
            name=str(data.get("name", "Inconnu")),
            team_number=int(data.get("team_number", 0)),
            aim_metrics=data.get("aim_metrics", {}),
            bhop_metrics=data.get("bhop_metrics", {}),
            wh_metrics=data.get("wh_metrics", {}),
            spinbot_metrics=data.get("spinbot_metrics", {}),
            triggerbot_metrics=data.get("triggerbot_metrics", {}),
            suspicion_score=float(data.get("suspicion_score", 0.0)),
            verdict=str(data.get("verdict", "CLEAN")),
            violation_flags=data.get("violation_flags", []),
            combat_events=data.get("combat_events", []),
        )


@dataclass
class MatchAnalysisResult:
    """Aggregated analysis report for an entire Counter-Strike 2 match demo."""
    demo_path: str
    map_name: str
    server_name: str
    total_ticks: int
    duration_seconds: float
    players: List[PlayerTelemetry]
    global_verdict: str
    engine_version: str = "3.1.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "demo_path": self.demo_path,
            "map_name": self.map_name,
            "server_name": self.server_name,
            "total_ticks": self.total_ticks,
            "duration_seconds": self.duration_seconds,
            "players": [p.to_dict() for p in self.players],
            "global_verdict": self.global_verdict,
            "engine_version": self.engine_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatchAnalysisResult":
        return cls(
            demo_path=data.get("demo_path", ""),
            map_name=data.get("map_name", "Unknown"),
            server_name=data.get("server_name", "Unknown"),
            total_ticks=data.get("total_ticks", 0),
            duration_seconds=data.get("duration_seconds", 0.0),
            players=[PlayerTelemetry.from_dict(p) for p in data.get("players", [])],
            global_verdict=data.get("global_verdict", "CLEAN"),
            engine_version=data.get("engine_version", "3.1.0"),
        )
