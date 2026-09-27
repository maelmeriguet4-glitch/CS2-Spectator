"""
Tactical Dark Cyber Theme Configuration and Styling Helpers.
Defines color palettes, typography hierarchies, status badge styles, and helper functions
for the CS2 Anti-Cheat Desktop Application.
"""

from typing import Any, Dict, Tuple

import customtkinter as ctk

# ==============================================================================
# 🎨 COLOR PALETTE (DARK MINIMALIST / GLASSMORPHISM / XENO-LIKE)
# ==============================================================================
THEME = {
    # Base Layout & Containers
    "bg_main": "#000000",          # Pure Black Background
    "bg_card": "#0A0A0A",          # Very Dark Gray (Glassmorphism base)
    "bg_card_hover": "#111111",    # Hover state for interactive cards
    "bg_secondary": "#0A0A0A",     # Secondary surface
    "bg_panel": "#050505",         # Deep slate panel background
    "border": "#1A1A1A",           # Thin subtle borders
    "border_focus": "#333333",     # Lighter subtle gray for focus
    "divider": "#151515",          # Extremely subtle dividers

    # Brand & Tactical Accents (Monochrome)
    "accent_cyan": "#FFFFFF",      # Replaced with Pure White for minimalism
    "accent_cyan_hover": "#E5E5E5",
    "accent_blue": "#D1D5DB",      # Light gray for links/IDs
    "accent_purple": "#A3A3A3",    # Muted gray for highlights
    "accent_magenta": "#A3A3A3",   # Muted gray

    # Status Indicators (Muted but functional for Anti-Cheat)
    "clean_green": "#10B981",      # Keep functional green but muted in UI
    "clean_green_bg": "#021c13",   # Barely visible green glass
    "clean_green_text": "#6EE7B7", 
    "clean_border": "#03291c",     

    "suspect_amber": "#F59E0B",    
    "suspect_amber_bg": "#1c1103", 
    "suspect_amber_text": "#FDE68A",
    "suspect_border": "#2b1903",   

    "cheater_red": "#EF4444",      
    "cheater_red_bg": "#1c0707",   
    "cheater_red_text": "#FCA5A5", 
    "cheater_border": "#2b0a0a",   

    # Cheat Categories (Muted monochrome or subtle colors)
    "cheat_aimbot": "#525252",      
    "cheat_aimbot_bg": "#0f0f0f",
    "cheat_wallhack": "#525252",    
    "cheat_wallhack_bg": "#0f0f0f",
    "cheat_bhop": "#525252",        
    "cheat_bhop_bg": "#0f0f0f",
    "cheat_spinbot": "#525252",     
    "cheat_spinbot_bg": "#0f0f0f",
    "cheat_trigger": "#525252",     
    "cheat_trigger_bg": "#0f0f0f",

    # Typography & Content
    "text_white": "#FFFFFF",       # Pure white for high contrast titles
    "text_muted": "#A3A3A3",       # Light gray for body
    "text_dim": "#525252",         # Dim gray for metadata

    # Team Badges
    "team_ct_bg": "#05111f",       
    "team_ct_text": "#93C5FD",     
    "team_t_bg": "#1a0b04",        
    "team_t_text": "#FDBA74",      
    "team_spec_bg": "#0a0a0a",     
    "team_spec_text": "#737373",   

    # Action Buttons (Pill shaped, minimalist)
    "btn_primary_bg": "#FFFFFF",   # White button for primary action
    "btn_primary_hover": "#E5E5E5",
    "btn_primary_text": "#000000", # Black text on white button

    "btn_flick_bg": "#111111",     
    "btn_flick_hover": "#1A1A1A",
    "btn_flick_text": "#FFFFFF",

    "btn_diagnostic_bg": "#111111",
    "btn_diagnostic_hover": "#1A1A1A",
    "btn_diagnostic_text": "#FFFFFF",

    "btn_secondary_bg": "#111111", 
    "btn_secondary_hover": "#1A1A1A",
    "btn_secondary_text": "#FFFFFF",

    "btn_steam_bg": "#111111",     
    "btn_steam_hover": "#1A1A1A",
    "btn_steam_text": "#D1D5DB",

    "btn_faceit_bg": "#111111",    
    "btn_faceit_hover": "#1A1A1A",
    "btn_faceit_text": "#D1D5DB",

    # Progress & Meters
    "progress_bg": "#111111",
}

# ==============================================================================
# 🔤 TYPOGRAPHY HIERARCHY
# ==============================================================================
FONT_FAMILY_PRIMARY = "Inter" # Minimalist modern font
FONT_FAMILY_MONO = "Consolas"


def get_font(
    family: str = FONT_FAMILY_PRIMARY,
    size: int = 12,
    weight: str = "normal",
    slant: str = "roman",
) -> ctk.CTkFont:
    """
    Factory function returning a configured CustomTkinter CTkFont.
    """
    return ctk.CTkFont(family=family, size=size, weight=weight, slant=slant)


def title_font() -> ctk.CTkFont:
    """Large modern title font (28pt medium/bold)."""
    return get_font(FONT_FAMILY_PRIMARY, 28, "bold")


def header_font() -> ctk.CTkFont:
    """Section / card header font (16pt bold)."""
    return get_font(FONT_FAMILY_PRIMARY, 16, "bold")


def body_font() -> ctk.CTkFont:
    """Standard body text font (14pt regular)."""
    return get_font(FONT_FAMILY_PRIMARY, 14, "normal")


def small_font() -> ctk.CTkFont:
    """Small subtitle / footnote font (12pt regular)."""
    return get_font(FONT_FAMILY_PRIMARY, 12, "normal")


def mono_font(size: int = 12, bold: bool = False) -> ctk.CTkFont:
    """Monospace font for SteamIDs, ticks, coordinates, and angles."""
    return get_font(FONT_FAMILY_MONO, size, "bold" if bold else "normal")


def badge_font() -> ctk.CTkFont:
    """Bold compact font for status badges and pills (11pt bold)."""
    return get_font(FONT_FAMILY_PRIMARY, 11, "bold")


def pill_font() -> ctk.CTkFont:
    """Compact monospace font for violation pills (10pt bold)."""
    return get_font(FONT_FAMILY_MONO, 10, "bold")


# ==============================================================================
# 🛠️ STYLING HELPERS
# ==============================================================================
def apply_dark_theme() -> None:
    """
    Initializes global CustomTkinter appearance mode to 'Dark'
    and applies base color defaults.
    """
    ctk.set_appearance_mode("Dark")
    ctk.set_default_color_theme("blue")


def format_suspicion_color(score: float) -> str:
    """
    Returns hex color code corresponding to player suspicion percentage:
    - 0% - 34%: Emerald Green (#10B981)
    - 35% - 69%: Amber Yellow (#F59E0B)
    - 70% - 100%: Crimson Red (#EF4444)
    """
    if score < 35.0:
        return THEME["clean_green"]
    elif score < 70.0:
        return THEME["suspect_amber"]
    return THEME["cheater_red"]


def get_status_colors(verdict: str, suspicion_score: float = 0.0) -> Dict[str, str]:
    """
    Returns styling dictionary for player status badges, card borders, and progress meters.
    """
    norm_verdict = (verdict or "").upper()

    if norm_verdict == "CHEATER" or suspicion_score >= 70.0:
        return {
            "badge_bg": THEME["cheater_red_bg"],
            "badge_text": THEME["cheater_red_text"],
            "status_text": "🔴 SUSPICION ÉLEVÉE",
            "status_short": "CHEATER",
            "progress_color": THEME["cheater_red"],
            "border_color": THEME["cheater_border"],
            "why_title": "Anomalies biomécaniques détectées :",
        }
    elif norm_verdict == "SUSPECT" or suspicion_score >= 35.0:
        return {
            "badge_bg": THEME["suspect_amber_bg"],
            "badge_text": THEME["suspect_amber_text"],
            "status_text": "🟡 COMPORTEMENT SUSPECT",
            "status_short": "SUSPECT",
            "progress_color": THEME["suspect_amber"],
            "border_color": THEME["suspect_border"],
            "why_title": "Anomalies télémétriques à vérifier :",
        }
    else:
        return {
            "badge_bg": THEME["clean_green_bg"],
            "badge_text": THEME["clean_green_text"],
            "status_text": "🟢 NON DÉTECTÉ",
            "status_short": "CLEAN",
            "progress_color": THEME["clean_green"],
            "border_color": THEME["clean_border"],
            "why_title": "Conformité biomécanique validée :",
        }


def generate_player_verdict_summary(player: Any) -> str:
    """
    Generates a concise, plain-text French explanation of why this verdict was attributed.
    """
    verdict = getattr(player, "verdict", "CLEAN")
    aim = getattr(player, "aim_metrics", {}) or {}
    bhop = getattr(player, "bhop_metrics", {}) or {}
    wh = getattr(player, "wh_metrics", {}) or {}
    flags = getattr(player, "violation_flags", []) or []

    if verdict == "CHEATER":
        reasons = []
        snap = float(aim.get("aim_p99", 0.0))
        if snap > 25.0:
            reasons.append(f"Snap robotique violent de {snap:.1f}°/tick")
        wh_ratio = float(wh.get("wh_ratio_lock_strict", 0.0)) * 100
        if wh_ratio > 10.0:
            reasons.append(f"Tracking occlus ({wh_ratio:.1f}% locks à travers les murs)")
        bhop_ratio = float(bhop.get("bhop_ratio_parfaits", 0.0)) * 100
        if bhop_ratio > 60.0:
            reasons.append(f"Script de BunnyHop ({bhop_ratio:.0f}% sauts parfaits en 1 tick)")
        if not reasons and flags:
            return " | ".join(flags[:2])
        return "Triche avérée : " + (", ".join(reasons) if reasons else "Anomalies biomécaniques multiples détectées.")

    elif verdict == "SUSPECT":
        reasons = []
        snap = float(aim.get("aim_p99", 0.0))
        if snap > 15.0:
            reasons.append(f"Flick angulaire de {snap:.1f}°/tick à la limite humaine")
        wh_locks = int(wh.get("wh_nb_locks", 0))
        if wh_locks > 3:
            reasons.append(f"{wh_locks} visées suspectes à travers des surfaces opaques")
        bhop_chain = int(bhop.get("bhop_chaine_max", 0))
        if bhop_chain >= 3:
            reasons.append(f"Chaîne de {bhop_chain} sauts synchronisés")
        return "Anomalies à vérifier : " + (", ".join(reasons) if reasons else "Mouvements atypiques au-dessus des moyennes pros.")

    else:
        return "✓ Visée humaine naturelle, accélération fluide, aucun lock à travers les murs ni script de saut."


def format_team_badge(team_number: int) -> Tuple[str, str, str]:
    """
    Returns (label, bg_color, text_color) based on CS2 team number:
    - 2: Terrorist (T)
    - 3: Counter-Terrorist (CT)
    - other: Spectator / Unassigned
    """
    if team_number == 3:
        return ("CT", THEME["team_ct_bg"], THEME["team_ct_text"])
    elif team_number == 2:
        return ("T", THEME["team_t_bg"], THEME["team_t_text"])
    return ("SPEC", THEME["team_spec_bg"], THEME["team_spec_text"])
