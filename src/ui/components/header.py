"""
Match Summary Header Component.
Displays map name, server name, ticks, duration, and global match verdict badge.
"""

from typing import Optional

import customtkinter as ctk

from src.core.models import MatchAnalysisResult
from src.ui.theme import (
    THEME,
    badge_font,
    header_font,
    mono_font,
    small_font,
)


class MatchHeader(ctk.CTkFrame):
    """
    Header bar presenting metadata of the analyzed CS2 match and the overall integrity verdict.
    """

    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
            **kwargs,
        )

        # Internal state
        self._current_result: Optional[MatchAnalysisResult] = None

        # Setup layout: 2 columns (Left: metadata, Right: verdict badge)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=0)
        self.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # Left container: Metadata (Map, Server, Duration)
        # ----------------------------------------------------------------------
        self.meta_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.meta_frame.grid(row=0, column=0, padx=20, pady=14, sticky="nsew")

        # Top row: Map name & Category title
        self.top_row = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        self.top_row.pack(fill="x", anchor="w")

        self.title_icon = ctk.CTkLabel(
            self.top_row,
            text="🛡️ CS2 REPLAY AUDIT //",
            font=mono_font(size=12, bold=True),
            text_color=THEME["accent_cyan"],
        )
        self.title_icon.pack(side="left", padx=(0, 8))

        self.lbl_map = ctk.CTkLabel(
            self.top_row,
            text="CARTE : AUCUN REPLAY",
            font=header_font(),
            text_color=THEME["text_white"],
        )
        self.lbl_map.pack(side="left")

        # Bottom row: Server name & Ticks / Duration
        self.bottom_row = ctk.CTkFrame(self.meta_frame, fg_color="transparent")
        self.bottom_row.pack(fill="x", anchor="w", pady=(4, 0))

        self.lbl_server = ctk.CTkLabel(
            self.bottom_row,
            text="Serveur : -",
            font=small_font(),
            text_color=THEME["text_muted"],
        )
        self.lbl_server.pack(side="left", padx=(0, 16))

        self.lbl_duration = ctk.CTkLabel(
            self.bottom_row,
            text="Durée : - | Ticks : -",
            font=mono_font(size=10),
            text_color=THEME["text_dim"],
        )
        self.lbl_duration.pack(side="left")

        # ----------------------------------------------------------------------
        # Right container: Global Verdict Badge
        # ----------------------------------------------------------------------
        self.verdict_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.verdict_frame.grid(row=0, column=1, padx=20, pady=14, sticky="e")

        self.verdict_badge = ctk.CTkLabel(
            self.verdict_frame,
            text="EN ATTENTE D'ANALYSE",
            font=badge_font(),
            text_color=THEME["text_muted"],
            fg_color=THEME["bg_secondary"],
            corner_radius=12,
            padx=16,
            pady=8,
        )
        self.verdict_badge.pack(side="right")

    # ==========================================================================
    # Public API
    # ==========================================================================
    def update_match_result(self, result: MatchAnalysisResult) -> None:
        """
        Updates header displays from an analyzed MatchAnalysisResult.
        """
        self._current_result = result

        # 1. Map name
        map_name = result.map_name or "Carte Inconnue"
        self.lbl_map.configure(text=f"CARTE : {map_name.upper()}")

        # 2. Server name
        server_display = result.server_name if result.server_name and result.server_name != "unknown" else "Serveur CS2"
        self.lbl_server.configure(text=f"Serveur : {server_display}")

        # 3. Ticks & Duration
        total_ticks = result.total_ticks
        duration_sec = result.duration_seconds
        mins = int(duration_sec // 60)
        secs = int(duration_sec % 60)
        self.lbl_duration.configure(
            text=f"Durée : {mins:02d}m {secs:02d}s | {total_ticks:,} ticks | {len(result.players)} joueurs"
        )

        # 4. Global Verdict Badge
        cheaters = [p for p in result.players if p.verdict == "CHEATER"]
        suspects = [p for p in result.players if p.verdict == "SUSPECT"]

        if cheaters:
            badge_text = f"🔴 {len(cheaters)} SUSPICION(S) ÉLEVÉE(S)"
            badge_fg = THEME["cheater_red_bg"]
            badge_color = THEME["cheater_red_text"]
        elif suspects:
            badge_text = f"🟡 {len(suspects)} JOUEUR(S) SUSPECT(S)"
            badge_fg = THEME["suspect_amber_bg"]
            badge_color = THEME["suspect_amber_text"]
        elif result.players:
            badge_text = "🟢 AUCUN SIGNAL FORT DÉTECTÉ"
            badge_fg = THEME["clean_green_bg"]
            badge_color = THEME["clean_green_text"]
        else:
            badge_text = result.global_verdict or "AUCUN JOUEUR"
            badge_fg = THEME["bg_secondary"]
            badge_color = THEME["text_muted"]

        self.verdict_badge.configure(
            text=badge_text,
            fg_color=badge_fg,
            text_color=badge_color,
        )

    def set_loading(self, demo_name: str) -> None:
        """
        Sets header into analyzing/loading state.
        """
        self.lbl_map.configure(text="ANALYSE EN COURS...")
        self.lbl_server.configure(text=f"Fichier : {demo_name}")
        self.lbl_duration.configure(text="Extraction des ticks et analyse biomécanique...")
        self.verdict_badge.configure(
            text="⚡ ANALYSE EN COURS",
            fg_color=THEME["bg_secondary"],
            text_color=THEME["accent_cyan"],
        )

    def reset(self) -> None:
        """
        Resets header to empty default state.
        """
        self._current_result = None
        self.lbl_map.configure(text="CARTE : AUCUN REPLAY")
        self.lbl_server.configure(text="Serveur : -")
        self.lbl_duration.configure(text="Durée : - | Ticks : -")
        self.verdict_badge.configure(
            text="EN ATTENTE D'ANALYSE",
            fg_color=THEME["bg_secondary"],
            text_color=THEME["text_muted"],
        )
