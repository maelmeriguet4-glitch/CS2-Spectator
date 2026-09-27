# CS2 Anti-Cheat - Analyzers Package
from src.analyzers.aimbot import (
    AimAnalysisResult,
    AimbotResult,
    analyser_aimbot,
    analyze_aimbot,
)
from src.analyzers.bhop import (
    BhopAnalysisResult,
    BhopResult,
    analyser_bhop,
    analyze_bhop,
)
from src.analyzers.spinbot import (
    SpinbotAnalysisResult,
    SpinbotResult,
    analyser_spinbot,
    analyze_spinbot,
)
from src.analyzers.triggerbot import (
    TriggerbotAnalysisResult,
    TriggerbotResult,
    analyser_triggerbot,
    analyze_triggerbot,
)
from src.analyzers.wallhack import (
    WallhackAnalysisResult,
    WallhackResult,
    analyser_wallhack,
    analyze_wallhack,
)

__all__ = [
    "AimAnalysisResult",
    "AimbotResult",
    "BhopAnalysisResult",
    "BhopResult",
    "SpinbotAnalysisResult",
    "SpinbotResult",
    "TriggerbotAnalysisResult",
    "TriggerbotResult",
    "WallhackAnalysisResult",
    "WallhackResult",
    "analyser_aimbot",
    "analyser_bhop",
    "analyser_spinbot",
    "analyser_triggerbot",
    "analyser_wallhack",
    "analyze_aimbot",
    "analyze_bhop",
    "analyze_spinbot",
    "analyze_triggerbot",
    "analyze_wallhack",
]
