"""
Rich Player Card Component.
Displays individual player biomechanical telemetry metrics, team identity, SteamID64,
suspicion gauge meter, categorized violation pills, and external profile/report actions.
"""

import webbrowser
from typing import Callable, Optional

import customtkinter as ctk

from src.core.cs2_launcher import find_steam_and_cs2, prepare_replay_files
from src.core.models import PlayerTelemetry
from src.ui.components.watch_modal import WatchCS2Modal
from src.ui.theme import (
    THEME,
    badge_font,
    body_font,
    format_team_badge,
    generate_player_verdict_summary,
    get_status_colors,
    header_font,
    mono_font,
    pill_font,
    small_font,
)


class PlayerCard(ctk.CTkFrame):
    """
    Tactical card rendering telemetry analysis and cheat indicators for an individual player.
    """

    def __init__(
        self,
        master,
        player: PlayerTelemetry,
        demo_path: Optional[str] = None,
        on_report: Optional[Callable[[PlayerTelemetry], None]] = None,
        on_view_flick: Optional[Callable[[PlayerTelemetry], None]] = None,
        on_view_diagnostic: Optional[Callable[[PlayerTelemetry], None]] = None,
        **kwargs,
    ):
        status_info = get_status_colors(player.verdict, player.suspicion_score)
        card_border = status_info.get("border_color", THEME["border"])

        super().__init__(
            master,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=2,
            border_color=card_border,
            **kwargs,
        )

        self.player = player
        self.demo_path = demo_path
        self.on_report_callback = on_report
        self.on_view_flick_callback = on_view_flick
        self.on_view_diagnostic_callback = on_view_diagnostic

        # Setup internal grid
        self.grid_columnconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # ROW 1: Header (Team, Name, SteamID64, Status Badge)
        # ----------------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=16, pady=(14, 8))

        # Left cluster: Team badge + Player Name + SteamID64
        self.left_cluster = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.left_cluster.pack(side="left", fill="y")

        # Team badge
        team_label, team_bg, team_text = format_team_badge(player.team_number)
        self.team_badge = ctk.CTkLabel(
            self.left_cluster,
            text=team_label,
            font=mono_font(size=11, bold=True),
            fg_color=team_bg,
            text_color=team_text,
            corner_radius=12,
            width=38,
            height=26,
        )
        self.team_badge.pack(side="left", padx=(0, 10))

        # Player Nickname
        display_name = player.name if player.name else "Joueur Inconnu"
        self.lbl_name = ctk.CTkLabel(
            self.left_cluster,
            text=display_name,
            font=header_font(),
            text_color=THEME["text_white"],
        )
        self.lbl_name.pack(side="left", padx=(0, 12))

        # SteamID64 badge / link
        display_steamid = str(player.steamid) if player.steamid else "N/A"
        self.lbl_steamid = ctk.CTkLabel(
            self.left_cluster,
            text=f"ID: {display_steamid}",
            font=mono_font(size=11),
            text_color=THEME["accent_blue"],
            cursor="hand2" if player.steamid and player.steamid != "0" else "",
        )
        self.lbl_steamid.pack(side="left")
        if player.steamid and player.steamid != "0":
            self.lbl_steamid.bind("<Button-1>", lambda e: self._copy_steamid())

        # Right cluster: Status Badge
        self.right_cluster = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        self.right_cluster.pack(side="right", fill="y")

        self.status_badge = ctk.CTkLabel(
            self.right_cluster,
            text=status_info["status_text"],
            font=badge_font(),
            fg_color=status_info["badge_bg"],
            text_color=status_info["badge_text"],
            corner_radius=12,
            padx=12,
            pady=4,
        )
        self.status_badge.pack(side="right")

        # ----------------------------------------------------------------------
        # ROW 2: Suspicion / Integrity Status Meter (No misleading percentages for clean)
        # ----------------------------------------------------------------------
        self.meter_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.meter_frame.pack(fill="x", padx=16, pady=(0, 6))

        verdict_norm = (player.verdict or "CLEAN").upper()
        if verdict_norm == "CLEAN":
            progress_val = 1.0
            prog_color = THEME["clean_green"]
            meter_text = "✓ NON DÉTECTÉ"
        elif verdict_norm == "SUSPECT":
            progress_val = max(0.40, min(0.69, player.suspicion_score / 100.0))
            prog_color = THEME["suspect_amber"]
            meter_text = "⚠️ ANOMALIES"
        else:
            progress_val = max(0.80, min(1.0, player.suspicion_score / 100.0))
            prog_color = THEME["cheater_red"]
            meter_text = "⛔ SUSPICION ÉLEVÉE"

        self.progress_bar = ctk.CTkProgressBar(
            self.meter_frame,
            orientation="horizontal",
            height=10,
            fg_color=THEME["progress_bg"],
            progress_color=prog_color,
            corner_radius=12,
        )
        self.progress_bar.set(progress_val)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 14))

        # Suspicion label
        self.lbl_suspicion = ctk.CTkLabel(
            self.meter_frame,
            text=meter_text,
            font=mono_font(size=11, bold=True),
            text_color=prog_color,
            width=130,
            anchor="e",
        )
        self.lbl_suspicion.pack(side="right")

        # ----------------------------------------------------------------------
        # ROW 2.5: Concrete Justification ("Pourquoi ce verdict")
        # ----------------------------------------------------------------------
        self.why_frame = ctk.CTkFrame(self, fg_color=THEME["bg_secondary"], corner_radius=12)
        self.why_frame.pack(fill="x", padx=16, pady=(0, 8))

        why_text = generate_player_verdict_summary(player)
        why_color = (
            THEME["clean_green_text"]
            if verdict_norm == "CLEAN"
            else (THEME["cheater_red_text"] if verdict_norm == "CHEATER" else THEME["suspect_amber_text"])
        )
        self.lbl_why = ctk.CTkLabel(
            self.why_frame,
            text=f"📌 Motif : {why_text}",
            font=body_font(),
            text_color=why_color,
            anchor="w",
            wraplength=760,
            justify="left",
            padx=10,
            pady=5,
        )
        self.lbl_why.pack(fill="x")

        # ----------------------------------------------------------------------
        # ROW 3: Categorized Violation Pills
        # ----------------------------------------------------------------------
        self.pills_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.pills_frame.pack(fill="x", padx=16, pady=(0, 10))

        self._render_violation_pills()

        # ----------------------------------------------------------------------
        # ROW 4: Action Buttons (Signaler, Tracé 2D, Diagnostic, Steam, Faceit)
        # ----------------------------------------------------------------------
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.pack(fill="x", padx=16, pady=(0, 14))

        # Action 1: Report Wizard (Alarme Rouge)
        self.btn_report = ctk.CTkButton(
            self.actions_frame,
            text="📝 Signaler",
            font=badge_font(),
            fg_color=THEME["btn_primary_bg"],
            hover_color=THEME["btn_primary_hover"],
            text_color=THEME["btn_primary_text"],
            height=30,
            corner_radius=12,
            command=self._on_report_clicked,
        )
        self.btn_report.pack(side="left", padx=(0, 8))

        # Action 2: 2D Flick / Snap Trajectory (Cyan Néon)
        self.btn_trace_2d = ctk.CTkButton(
            self.actions_frame,
            text="📈 Tracé 2D Snap",
            font=badge_font(),
            fg_color=THEME["btn_flick_bg"],
            hover_color=THEME["btn_flick_hover"],
            text_color=THEME["btn_flick_text"],
            height=30,
            corner_radius=12,
            command=self._on_trace_2d_clicked,
        )
        self.btn_trace_2d.pack(side="left", padx=(0, 8))

        # Action 3: Detailed Cheat Diagnostic (Violet Tactique)
        self.btn_diagnostic = ctk.CTkButton(
            self.actions_frame,
            text="🔬 Diagnostic",
            font=badge_font(),
            fg_color=THEME["btn_diagnostic_bg"],
            hover_color=THEME["btn_diagnostic_hover"],
            text_color=THEME["btn_diagnostic_text"],
            height=30,
            corner_radius=12,
            command=self._on_diagnostic_clicked,
        )
        self.btn_diagnostic.pack(side="left", padx=(0, 8))

        # Action 4: Lancer CS2
        self.btn_watch_ingame = ctk.CTkButton(
            self.actions_frame,
            text="🎬 Lancer CS2",
            font=badge_font(),
            fg_color="#047857", # Emerald Green
            hover_color="#065F46",
            text_color="#FFFFFF",
            height=30,
            corner_radius=12,
            state="normal" if self.demo_path else "disabled",
            command=self._launch_cs2_demo,
        )
        self.btn_watch_ingame.pack(side="left", padx=(0, 8))

        # Middle action: Steam Profile
        has_valid_steam = bool(player.steamid and player.steamid != "0" and not player.steamid.startswith("anonymousnknown"))
        self.btn_steam = ctk.CTkButton(
            self.actions_frame,
            text="🌐 Steam",
            font=small_font(),
            fg_color=THEME["btn_steam_bg"],
            hover_color=THEME["btn_steam_hover"],
            text_color=THEME["btn_steam_text"],
            height=30,
            corner_radius=12,
            state="normal" if has_valid_steam else "disabled",
            command=self._open_steam_profile,
        )
        self.btn_steam.pack(side="left", padx=(0, 8))

        # Right action: Faceit
        self.btn_faceit = ctk.CTkButton(
            self.actions_frame,
            text="🎯 Faceit",
            font=small_font(),
            fg_color=THEME["btn_faceit_bg"],
            hover_color=THEME["btn_faceit_hover"],
            text_color=THEME["btn_faceit_text"],
            height=30,
            corner_radius=12,
            state="normal" if has_valid_steam else "disabled",
            command=self._open_faceit_profile,
        )
        self.btn_faceit.pack(side="left")

    # ==========================================================================
    # Internal Rendering & Helpers
    # ==========================================================================
    def _render_violation_pills(self) -> None:
        """
        Renders styled tags/pills for detected biomechanical violations.
        """
        # Clear existing pills if re-rendering
        for w in self.pills_frame.winfo_children():
            w.destroy()

        flags = self.player.violation_flags or []

        if not flags:
            # Clean / Legit player pill
            pill = ctk.CTkLabel(
                self.pills_frame,
                text="✓ BIOMÉCANIQUE HUMAINE NORMALISÉE",
                font=pill_font(),
                fg_color=THEME["clean_green_bg"],
                text_color=THEME["clean_green_text"],
                corner_radius=12,
                padx=8,
                pady=2,
            )
            pill.pack(side="left", padx=(0, 6))
            return

        # Render each violation flag
        for flag in flags:
            fg_bg, fg_txt = self._get_pill_colors(flag)
            pill = ctk.CTkLabel(
                self.pills_frame,
                text=flag,
                font=pill_font(),
                fg_color=fg_bg,
                text_color=fg_txt,
                corner_radius=12,
                padx=8,
                pady=2,
            )
            pill.pack(side="left", padx=(0, 6), pady=(0, 4))

    def _get_pill_colors(self, flag: str) -> tuple[str, str]:
        """
        Determines pill background and text color based on cheat category signatures.
        """
        flag_upper = flag.upper()
        if "AIMBOT" in flag_upper or "SNAP" in flag_upper or "JERK" in flag_upper:
            return (THEME["cheat_aimbot_bg"], THEME["cheat_aimbot"])
        elif "WALLHACK" in flag_upper or "LOCK" in flag_upper or "ESP" in flag_upper:
            return (THEME["cheat_wallhack_bg"], THEME["cheat_wallhack"])
        elif "BHOP" in flag_upper or "SAUT" in flag_upper:
            return (THEME["cheat_bhop_bg"], THEME["cheat_bhop"])
        elif "SPIN" in flag_upper or "PITCH" in flag_upper:
            return (THEME["cheat_spinbot_bg"], THEME["cheat_spinbot"])
        elif "TRIGGER" in flag_upper or "RÉACTION" in flag_upper or "REACTION" in flag_upper:
            return (THEME["cheat_trigger_bg"], THEME["cheat_trigger"])
        elif "CRITIQUE" in flag_upper or "RAGE" in flag_upper:
            return (THEME["cheater_red_bg"], THEME["cheater_red_text"])
        return (THEME["bg_secondary"], THEME["text_muted"])

    def _on_report_clicked(self) -> None:
        """Invokes the report callback if registered."""
        if self.on_report_callback:
            self.on_report_callback(self.player)

    def _on_trace_2d_clicked(self) -> None:
        """Invokes the view flick callback or opens ReportModal focused on the 2D tab."""
        if self.on_view_flick_callback:
            self.on_view_flick_callback(self.player)
        else:
            try:
                from src.ui.components.report_modal import ReportModal
                ReportModal(self.winfo_toplevel(), player=self.player, initial_tab="📈 Tracé 2D du Snap")
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _on_diagnostic_clicked(self) -> None:
        """Invokes the diagnostic callback or opens ReportModal focused on the Diagnostic tab."""
        if self.on_view_diagnostic_callback:
            self.on_view_diagnostic_callback(self.player)
        else:
            try:
                from src.ui.components.report_modal import ReportModal
                ReportModal(self.winfo_toplevel(), player=self.player, initial_tab="🔍 Diagnostic des Suspicions")
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _open_steam_profile(self) -> None:
        """Opens Steam Community profile in default web browser."""
        steamid = self.player.steamid
        if steamid and steamid != "0":
            url = f"https://steamcommunity.com/profiles/{steamid}"
            try:
                webbrowser.open(url)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _open_faceit_profile(self) -> None:
        """Opens FaceitFinder profile in default web browser."""
        steamid = self.player.steamid
        if steamid and steamid != "0":
            url = f"https://faceitfinder.com/profile/{steamid}"
            try:
                webbrowser.open(url)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _copy_steamid(self) -> None:
        """Copies SteamID64 to clipboard."""
        steamid = self.player.steamid
        if steamid:
            try:
                self.clipboard_clear()
                self.clipboard_append(steamid)
                self.lbl_steamid.configure(text="ID Copié !")
                self.after(1200, lambda: self.lbl_steamid.configure(text=f"ID: {steamid}"))
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _launch_cs2_demo(self) -> None:
        """Prepares replay files and opens the CS2 inspection modal dialog."""
        if not self.demo_path:
            return

        # Find the earliest suspicious tick from combat_events
        target_tick = 0
        events = getattr(self.player, "combat_events", []) or []
        if events:
            first_event = events[0]
            tick = first_event.get("tick") or first_event.get("start_tick") or 0
            target_tick = max(0, int(tick) - 350)

        # Pre-prepare replay and cfg in CS2 directory in background
        _, csgo_dir = find_steam_and_cs2()
        if csgo_dir:
            prepare_replay_files(self.demo_path, target_tick, csgo_dir)

        # Open the interactive modal
        try:
            WatchCS2Modal(
                self.winfo_toplevel(),
                player=self.player,
                demo_path=self.demo_path,
                target_tick=target_tick,
            )
        except Exception:
            # Fallback
            from src.core.cs2_launcher import execute_cs2_launch
            execute_cs2_launch(self.demo_path, target_tick, force_restart=False)

    # ==========================================================================
    # Public API
    # ==========================================================================
    def update_player(self, player: PlayerTelemetry) -> None:
        """
        Updates the card with fresh PlayerTelemetry data.
        """
        self.player = player

        # Team
        team_label, team_bg, team_text = format_team_badge(player.team_number)
        self.team_badge.configure(text=team_label, fg_color=team_bg, text_color=team_text)

        # Name & SteamID
        self.lbl_name.configure(text=player.name or "Joueur Inconnu")
        steamid_str = str(player.steamid) if player.steamid else "N/A"
        self.lbl_steamid.configure(text=f"ID: {steamid_str}")

        # Status & Border
        status_info = get_status_colors(player.verdict, player.suspicion_score)
        self.configure(border_color=status_info.get("border_color", THEME["border"]))
        self.status_badge.configure(
            text=status_info["status_text"],
            fg_color=status_info["badge_bg"],
            text_color=status_info["badge_text"],
        )

        # Meter (Clear unambiguous assessment)
        verdict_norm = (player.verdict or "CLEAN").upper()
        if verdict_norm == "CLEAN":
            progress_val = 1.0
            prog_color = THEME["clean_green"]
            meter_text = "✓ NON DÉTECTÉ"
        elif verdict_norm == "SUSPECT":
            progress_val = max(0.40, min(0.69, player.suspicion_score / 100.0))
            prog_color = THEME["suspect_amber"]
            meter_text = "⚠️ ANOMALIES"
        else:
            progress_val = max(0.80, min(1.0, player.suspicion_score / 100.0))
            prog_color = THEME["cheater_red"]
            meter_text = "⛔ SUSPICION ÉLEVÉE"

        self.progress_bar.configure(progress_color=prog_color)
        self.progress_bar.set(progress_val)
        self.lbl_suspicion.configure(text=meter_text, text_color=prog_color)

        # Why verdict text
        why_text = generate_player_verdict_summary(player)
        why_color = (
            THEME["clean_green_text"]
            if verdict_norm == "CLEAN"
            else (THEME["cheater_red_text"] if verdict_norm == "CHEATER" else THEME["suspect_amber_text"])
        )
        self.lbl_why.configure(text=f"📌 Motif : {why_text}", text_color=why_color)

        # Pills
        self._render_violation_pills()

        # Buttons
        has_valid_steam = bool(player.steamid and player.steamid != "0" and not player.steamid.startswith("anonymousnknown"))
        self.btn_steam.configure(state="normal" if has_valid_steam else "disabled")
        self.btn_faceit.configure(state="normal" if has_valid_steam else "disabled")
        
        if hasattr(self, 'btn_watch_ingame'):
            self.btn_watch_ingame.configure(state="normal" if getattr(self, 'demo_path', None) else "disabled")
