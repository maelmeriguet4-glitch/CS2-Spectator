"""
Report Modal Dialog for CS2 Anti-Cheat.
Provides interactive QCM checklist, user commentary input, dual tabs
with real-time Steam & Faceit report preview, clipboard copying, and profile links.
"""

import webbrowser
from typing import Any, Dict, List, Optional, Union

import customtkinter as ctk
import pyperclip

from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo
from src.core.reporter import QCM_OPTIONS, ReportGenerator
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
)


class ReportModal(ctk.CTkToplevel):
    """
    Interactive modal dialog for generating and previewing Steam and Faceit reports.
    """

    def __init__(
        self,
        parent: Any,
        player: PlayerTelemetry,
        match_result: Optional[Union[MatchAnalysisResult, ReplayInfo]] = None,
        demo_info: Optional[Union[MatchAnalysisResult, ReplayInfo]] = None,
        initial_tab: Optional[str] = None,
        *args,
        **kwargs,
    ):
        super().__init__(parent)

        self.parent = parent
        self.player = player
        self.match_result = match_result if match_result is not None else demo_info
        self.initial_tab = initial_tab

        # Window configuration
        self.title(f"SIGNALEMENT JOUEUR // {self.player.name}")
        self.geometry("960x750")
        self.minsize(820, 620)
        self.configure(fg_color=THEME["bg_main"])

        # Attempt transient and grab for modal behavior (safely handle headless mode)
        try:
            self.transient(parent)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        try:
            self.grab_set()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        # Data structures for QCM and timers
        self.qcm_vars: Dict[str, ctk.BooleanVar] = {}
        self._reset_timer_id: Optional[str] = None
        self._draw_timer_id: Optional[str] = None

        # Build UI layout
        self._build_ui()

        # Initial report rendering
        self._update_reports()

        # Switch to requested initial tab if provided
        if self.initial_tab:
            try:
                self.tabview.set(self.initial_tab)
                if self.initial_tab == "📈 Tracé 2D du Snap":
                    self._draw_timer_id = self.after(100, self._draw_flick_trajectory)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _build_ui(self) -> None:
        """Constructs the tactical cyber modal interface."""
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=0)  # Header
        self.grid_rowconfigure(1, weight=1)  # Split Content Area
        self.grid_rowconfigure(2, weight=0)  # Bottom Action Buttons

        # ======================================================================
        # 1. HEADER CARD (Target Player, Team, SteamID, Verdict Badge)
        # ======================================================================
        header_frame = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        header_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 10))
        header_frame.grid_columnconfigure(1, weight=1)

        # Team tag pill
        team_text, team_bg, team_fg = format_team_badge(self.player.team_number)
        lbl_team = ctk.CTkLabel(
            header_frame,
            text=f" {team_text} ",
            font=badge_font(),
            fg_color=team_bg,
            text_color=team_fg,
            corner_radius=12,
        )
        lbl_team.grid(row=0, column=0, rowspan=2, padx=(16, 12), pady=14)

        # Player nickname & SteamID64
        title_box = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_box.grid(row=0, column=1, rowspan=2, sticky="w", pady=12)

        lbl_name = ctk.CTkLabel(
            title_box,
            text=self.player.name,
            font=header_font(),
            text_color=THEME["text_white"],
        )
        lbl_name.pack(anchor="w")

        # Map and Replay Context
        map_text = "N/A"
        demo_text = "N/A"
        if self.match_result is not None:
            map_text = getattr(self.match_result, "map_name", "N/A")
            demo_text = getattr(self.match_result, "file_name", None)
            if not demo_text:
                demo_path = getattr(self.match_result, "demo_path", None) or getattr(self.match_result, "file_path", None)
                if demo_path:
                    import os
                    demo_text = os.path.basename(demo_path)
            demo_text = demo_text or "N/A"

        lbl_meta = ctk.CTkLabel(
            title_box,
            text=f"SteamID64 : {self.player.steamid}  |  Carte : {map_text}  |  Démo : {demo_text}",
            font=mono_font(size=11),
            text_color=THEME["text_muted"],
        )
        lbl_meta.pack(anchor="w", pady=(2, 0))

        # Status badge (Clean / Suspect / Cheater)
        status_info = get_status_colors(
            self.player.verdict,
            self.player.suspicion_score,
        )
        badge_frame = ctk.CTkFrame(
            header_frame,
            fg_color=status_info["badge_bg"],
            corner_radius=12,
            border_width=1,
            border_color=status_info.get("border_color", status_info["badge_text"]),
        )
        badge_frame.grid(row=0, column=2, rowspan=2, padx=16, pady=14, sticky="e")

        lbl_badge = ctk.CTkLabel(
            badge_frame,
            text=f" {status_info['status_text']}  ({self.player.suspicion_score:.1f}%) ",
            font=badge_font(),
            text_color=status_info["badge_text"],
        )
        lbl_badge.pack(padx=8, pady=6)

        # ======================================================================
        # 2. MAIN SPLIT AREA: Left (QCM & Notes) | Right (Dual Tabview Preview)
        # ======================================================================
        split_frame = ctk.CTkFrame(self, fg_color="transparent")
        split_frame.grid(row=1, column=0, sticky="nsew", padx=16, pady=(0, 10))
        split_frame.grid_columnconfigure(0, weight=4, minsize=320)  # Left column
        split_frame.grid_columnconfigure(1, weight=6, minsize=420)  # Right column
        split_frame.grid_rowconfigure(0, weight=1)

        # ----------------------------------------------------------------------
        # LEFT COLUMN: Interactive QCM & Auditor Commentary
        # ----------------------------------------------------------------------
        left_box = ctk.CTkFrame(
            split_frame,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        left_box.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=0)
        left_box.grid_columnconfigure(0, weight=1)
        left_box.grid_rowconfigure(1, weight=1)  # QCM list
        left_box.grid_rowconfigure(3, weight=0)  # Notes

        # QCM Title
        lbl_qcm_title = ctk.CTkLabel(
            left_box,
            text="OBSERVATIONS EN MATCH (QCM INTERACTIF) :",
            font=badge_font(),
            text_color=THEME["accent_cyan"],
        )
        lbl_qcm_title.grid(row=0, column=0, sticky="w", padx=14, pady=(12, 6))

        # QCM Checkbox Scrollable Frame
        qcm_scroll = ctk.CTkScrollableFrame(
            left_box,
            fg_color="transparent",
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["accent_cyan"],
        )
        qcm_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        qcm_scroll.grid_columnconfigure(0, weight=1)

        for opt in QCM_OPTIONS:
            var = ctk.BooleanVar(value=False)
            chk = ctk.CTkCheckBox(
                qcm_scroll,
                text=opt,
                variable=var,
                command=self._on_inputs_changed,
                fg_color=THEME["accent_cyan"],
                hover_color=THEME["accent_cyan"],
                checkmark_color=THEME["bg_main"],
                text_color=THEME["text_white"],
                font=body_font(),
                border_color=THEME["border"],
                corner_radius=12,
            )
            chk.pack(anchor="w", fill="x", padx=4, pady=5)
            self.qcm_vars[opt] = var

        # Commentary Title
        lbl_notes_title = ctk.CTkLabel(
            left_box,
            text="COMMENTAIRES DE L'AUDITEUR (CONTEXTE DES ROUNDS) :",
            font=badge_font(),
            text_color=THEME["accent_cyan"],
        )
        lbl_notes_title.grid(row=2, column=0, sticky="w", padx=14, pady=(6, 4))

        # Commentary Textbox
        self.txt_comments = ctk.CTkTextbox(
            left_box,
            height=95,
            fg_color=THEME["bg_secondary"],
            text_color=THEME["text_white"],
            font=body_font(),
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
            wrap="word",
        )
        self.txt_comments.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 12))
        self.txt_comments.bind("<KeyRelease>", lambda e: self._on_inputs_changed())

        # ----------------------------------------------------------------------
        # RIGHT COLUMN: Dual Tabview (Steam & Faceit Report Preview)
        # ----------------------------------------------------------------------
        right_box = ctk.CTkFrame(
            split_frame,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
        )
        right_box.grid(row=0, column=1, sticky="nsew", padx=(8, 0), pady=0)
        right_box.grid_columnconfigure(0, weight=1)
        right_box.grid_rowconfigure(0, weight=1)

        self.tabview = ctk.CTkTabview(
            right_box,
            fg_color=THEME["bg_card"],
            segmented_button_selected_color=THEME["accent_cyan"],
            segmented_button_selected_hover_color=THEME["accent_cyan"],
            segmented_button_unselected_color=THEME["bg_secondary"],
            segmented_button_unselected_hover_color=THEME["bg_secondary"],
            text_color=THEME["text_white"],
            command=self._on_tab_changed,
        )
        self.tabview.grid(row=0, column=0, sticky="nsew", padx=8, pady=6)

        # Tab 1: Steam Report
        self.tab_steam = self.tabview.add("Signalement Steam")
        self.tab_steam.grid_columnconfigure(0, weight=1)
        self.tab_steam.grid_rowconfigure(0, weight=1)

        self.txt_steam = ctk.CTkTextbox(
            self.tab_steam,
            fg_color=THEME["bg_secondary"],
            text_color=THEME["text_white"],
            font=mono_font(size=10),
            corner_radius=12,
            wrap="word",
        )
        self.txt_steam.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 2: Faceit Ticket
        self.tab_faceit = self.tabview.add("Ticket Support Faceit")
        self.tab_faceit.grid_columnconfigure(0, weight=1)
        self.tab_faceit.grid_rowconfigure(0, weight=1)

        self.txt_faceit = ctk.CTkTextbox(
            self.tab_faceit,
            fg_color=THEME["bg_secondary"],
            text_color=THEME["text_white"],
            font=mono_font(size=10),
            corner_radius=12,
            wrap="word",
        )
        self.txt_faceit.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # Tab 3: 2D Flick Trajectory Visualizer
        self.tab_visualizer = self.tabview.add("📈 Tracé 2D du Snap")
        self.tab_visualizer.grid_columnconfigure(0, weight=1)
        self.tab_visualizer.grid_rowconfigure(1, weight=1)

        self.lbl_vis_title = ctk.CTkLabel(
            self.tab_visualizer,
            text="ANALYSE VECTORIELLE DES FLICKS (Source 2 ViewAngles)",
            font=mono_font(size=10, bold=True),
            text_color=THEME["accent_cyan"],
        )
        self.lbl_vis_title.grid(row=0, column=0, sticky="w", padx=10, pady=(6, 2))

        import tkinter as tk
        self.canvas_flick = tk.Canvas(
            self.tab_visualizer,
            bg=THEME["bg_secondary"],
            highlightthickness=1,
            highlightbackground=THEME["border"],
        )
        self.canvas_flick.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        self.canvas_flick.bind("<Configure>", lambda e: self.after_idle(self._draw_flick_trajectory))

        self.lbl_vis_info = ctk.CTkLabel(
            self.tab_visualizer,
            text="",
            font=mono_font(size=9),
            text_color=THEME["text_muted"],
        )
        self.lbl_vis_info.grid(row=2, column=0, sticky="w", padx=10, pady=(2, 6))

        # Render flick trajectory initially
        self._draw_timer_id = self.after(200, self._draw_flick_trajectory)

        # Tab 4: Diagnostic des Suspicions
        self.tab_diagnostic = self.tabview.add("🔍 Diagnostic des Suspicions")
        self._build_diagnostic_tab()

        # ======================================================================
        # 3. DIRECT ACTION BUTTONS (Bottom Bar)
        # ======================================================================
        action_bar = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            corner_radius=12,
            border_width=1,
            border_color=THEME["border"],
            height=54,
        )
        action_bar.grid(row=2, column=0, sticky="ew", padx=16, pady=(0, 16))
        action_bar.grid_columnconfigure(0, weight=0)
        action_bar.grid_columnconfigure(1, weight=0)
        action_bar.grid_columnconfigure(2, weight=0)
        action_bar.grid_columnconfigure(3, weight=1)
        action_bar.grid_columnconfigure(4, weight=0)

        # Button: Copy current tab text
        self.btn_copy = ctk.CTkButton(
            action_bar,
            text="📋 Copier le signalement",
            command=self.copy_current_report,
            font=badge_font(),
            fg_color=THEME["accent_cyan"],
            hover_color="#00D2DF",
            text_color=THEME["bg_main"],
            height=34,
            corner_radius=12,
        )
        self.btn_copy.grid(row=0, column=0, padx=(14, 8), pady=10)

        # Button: Open Steam Profile in Browser
        self.btn_steam = ctk.CTkButton(
            action_bar,
            text="🌐 Profil Steam",
            command=self.open_steam_profile,
            font=body_font(),
            fg_color=THEME["bg_secondary"],
            hover_color=THEME["border"],
            text_color=THEME["text_white"],
            border_width=1,
            border_color=THEME["border"],
            height=34,
            corner_radius=12,
        )
        self.btn_steam.grid(row=0, column=1, padx=6, pady=10)

        # Button: Open Faceit / FaceitFinder in Browser
        self.btn_faceit = ctk.CTkButton(
            action_bar,
            text="🎯 Ouvrir Faceit / FaceitFinder",
            command=self.open_faceit,
            font=body_font(),
            fg_color=THEME["bg_secondary"],
            hover_color=THEME["border"],
            text_color=THEME["text_white"],
            border_width=1,
            border_color=THEME["border"],
            height=34,
            corner_radius=12,
        )
        self.btn_faceit.grid(row=0, column=2, padx=6, pady=10)

        # Button: Close Dialog
        self.btn_close = ctk.CTkButton(
            action_bar,
            text="✕ Fermer",
            command=self.destroy,
            font=body_font(),
            fg_color="transparent",
            hover_color=THEME["bg_secondary"],
            text_color=THEME["text_muted"],
            height=34,
            corner_radius=12,
        )
        self.btn_close.grid(row=0, column=4, padx=14, pady=10, sticky="e")

    # ==========================================================================
    # Interactive Event Handlers & Dynamic Report Generation
    # ==========================================================================
    def _on_inputs_changed(self) -> None:
        """Called whenever a QCM checkbox or the commentary field changes."""
        self._update_reports()

    def _update_reports(self) -> None:
        """
        Gathers user inputs and regenerates the pre-formatted report text
        for both Steam and Faceit tabs in real-time.
        """
        selected_qcm = self.get_selected_qcm()
        comments = self.get_comments()

        steam_report = ReportGenerator.generate_steam_report(
            player=self.player,
            qcm_options=selected_qcm,
            comments=comments,
            demo_info=self.match_result,
        )

        faceit_report = ReportGenerator.generate_faceit_report(
            player=self.player,
            qcm_options=selected_qcm,
            comments=comments,
            demo_info=self.match_result,
        )

        # Update Steam preview
        self.txt_steam.configure(state="normal")
        self.txt_steam.delete("1.0", "end")
        self.txt_steam.insert("1.0", steam_report)
        self.txt_steam.configure(state="disabled")

        # Update Faceit preview
        self.txt_faceit.configure(state="normal")
        self.txt_faceit.delete("1.0", "end")
        self.txt_faceit.insert("1.0", faceit_report)
        self.txt_faceit.configure(state="disabled")

    def get_selected_qcm(self) -> List[str]:
        """Returns the list of currently selected QCM observation strings."""
        return [opt for opt, var in self.qcm_vars.items() if var.get()]

    def set_qcm_option(self, option: str, value: bool) -> None:
        """Sets the checked state for a specific QCM option and updates reports."""
        if option in self.qcm_vars:
            self.qcm_vars[option].set(value)
            self._update_reports()

    def get_comments(self) -> str:
        """Returns user commentary text stripped of trailing newline."""
        try:
            return self.txt_comments.get("1.0", "end-1c").strip()
        except Exception:
            return ""

    def set_comments(self, text: str) -> None:
        """Sets the commentary text and updates reports."""
        try:
            self.txt_comments.delete("1.0", "end")
            self.txt_comments.insert("1.0", text)
            self._update_reports()
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def _build_diagnostic_tab(self) -> None:
        """Constructs the dedicated Cheat Suspicion Diagnostic tab with color-coded cheat cards."""
        self.tab_diagnostic.grid_columnconfigure(0, weight=1)
        self.tab_diagnostic.grid_rowconfigure(0, weight=1)

        scroll = ctk.CTkScrollableFrame(
            self.tab_diagnostic,
            fg_color="transparent",
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["accent_cyan"],
        )
        scroll.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)
        scroll.grid_columnconfigure(0, weight=1)

        # 1. Overall Summary Banner
        p = self.player
        status_info = get_status_colors(p.verdict, p.suspicion_score)
        summary_text = generate_player_verdict_summary(p)

        banner = ctk.CTkFrame(
            scroll,
            fg_color=status_info["badge_bg"],
            corner_radius=12,
            border_width=1,
            border_color=status_info["border_color"],
        )
        banner.grid(row=0, column=0, sticky="ew", padx=4, pady=(2, 10))
        banner.grid_columnconfigure(0, weight=1)

        lbl_status_title = ctk.CTkLabel(
            banner,
            text=f"VERDICT GLOBAL : {status_info['status_text']}",
            font=header_font(),
            text_color=status_info["badge_text"],
        )
        lbl_status_title.grid(row=0, column=0, sticky="w", padx=12, pady=(8, 2))

        lbl_status_desc = ctk.CTkLabel(
            banner,
            text=f"📌 Diagnostic de synthèse : {summary_text}",
            font=body_font(),
            text_color=THEME["text_white"],
            wraplength=480,
            justify="left",
        )
        lbl_status_desc.grid(row=1, column=0, sticky="w", padx=12, pady=(0, 10))

        # Metrics extraction
        aim = p.aim_metrics or {}
        bhop = p.bhop_metrics or {}
        wh = p.wh_metrics or {}
        spin = getattr(p, "spinbot_metrics", {}) or {}
        tb = getattr(p, "triggerbot_metrics", {}) or {}

        aim_snap = float(aim.get("aim_snap_max", 0.0))
        aim_jerk = float(aim.get("aim_jerk_max", 0.0))
        aim_vitesse = float(aim.get("aim_vitesse_max", 0.0))

        bhop_ratio_raw = float(bhop.get("bhop_ratio_parfaits", 0.0))
        bhop_ratio = bhop_ratio_raw * 100.0 if 0.0 < bhop_ratio_raw <= 1.0 else bhop_ratio_raw
        bhop_chain = int(bhop.get("bhop_chaine_max", 0))
        bhop_total = int(bhop.get("bhop_total_sauts", 0))

        wh_strict_raw = float(wh.get("wh_ratio_lock_strict", 0.0))
        wh_strict = wh_strict_raw * 100.0 if 0.0 < wh_strict_raw <= 1.0 else wh_strict_raw
        wh_cache_raw = float(wh.get("wh_ratio_lock_cache", 0.0))
        wh_cache = wh_cache_raw * 100.0 if 0.0 < wh_cache_raw <= 1.0 else wh_cache_raw
        wh_track = int(wh.get("wh_tracking_consecutif_max", 0))

        # Spinbot metrics
        spin_speed = float(spin.get("spinbot_yaw_speed_max", 0.0))
        spin_pitch_viol = int(spin.get("spinbot_pitch_violations", 0))
        spin_jitter = float(spin.get("spinbot_jitter_score", 0.0))
        spin_desync = int(spin.get("spinbot_desync_max_ticks", 0))
        spin_windows = int(spin.get("spinbot_yaw_spin_windows", 0))

        # Triggerbot metrics
        tb_rt_med = float(tb.get("triggerbot_rt_median", 0.0))
        tb_rt_std = float(tb.get("triggerbot_rt_std", 0.0))
        tb_burst = int(tb.get("triggerbot_burst_count", 0))
        tb_shots = int(tb.get("triggerbot_total_shots_analyzed", 0))

        flags_str = " ".join(p.violation_flags).upper()

        # Definitions of the 5 cheat cards:
        cheats_config = [
            {
                "title": "🎯 AIMBOT & VISÉE ROBOTIQUE",
                "accent_color": THEME["cheat_aimbot"],
                "bg_color": THEME["cheat_aimbot_bg"],
                "is_cheat": (aim_snap > 18.0 or aim_jerk > 30.0 or "AIMBOT" in flags_str),
                "is_suspect": (aim_snap > 10.0 or aim_jerk > 18.0),
                "metrics": [
                    f"• Snap instantané max : {aim_snap:.1f}°/tick (Seuil humain normal : < 8.0°)",
                    f"• Jerk angulaire max : {aim_jerk:.1f} (Seuil d'accélération brutale : > 25.0)",
                    f"• Vitesse angulaire max : {aim_vitesse:.1f}°/tick",
                ],
                "reason_cheat": "Snaps angulaires violents et instantanés sur la tête. Déviation en 1 tick incompatible avec la biomécanique musculaire humaine.",
                "reason_suspect": "Accélérations et micro-corrections vives détectées lors des tirs. Se situe à la limite des réflexes de haut niveau.",
                "reason_clean": "Accélérations angulaires et décélérations progressives. Trajectoires de visée naturelles et continues.",
            },
            {
                "title": "👁️ WALLHACK / ESP (VISION TRANSPARENTE)",
                "accent_color": THEME["cheat_wallhack"],
                "bg_color": THEME["cheat_wallhack_bg"],
                "is_cheat": (wh_cache > 15.0 or wh_track >= 10 or "WALLHACK" in flags_str or "LOCK" in flags_str),
                "is_suspect": (wh_cache > 5.0 or wh_track >= 5),
                "metrics": [
                    f"• Ratio verrous à travers murs : {wh_cache:.1f}% (Distribution normale : < 3.0%)",
                    f"• Verrous stricts centrés (±5°) : {wh_strict:.1f}%",
                    f"• Suivi (tracking) continu masqué : {wh_track} ticks",
                ],
                "reason_cheat": "Verrouillage et alignement persistant du réticule sur des ennemis non-spotted (masqués par des parois opaques). Triche de vision avérée.",
                "reason_suspect": "Pré-visées rapprochées sur des positions ennemies avant contact visuel. Nécessite une vérification des lignes classiques.",
                "reason_clean": "Aucune anomalie d'alignement sur les ennemis cachés. Balayage des angles et vérification de positions conformes.",
            },
            {
                "title": "🐰 BUNNYHOP & SCRIPTS DE SAUT (AUTOMATION)",
                "accent_color": THEME["cheat_bhop"],
                "bg_color": THEME["cheat_bhop_bg"],
                "is_cheat": ((bhop_ratio > 70.0 and bhop_chain >= 4) or "BHOP" in flags_str),
                "is_suspect": (bhop_ratio > 40.0 and bhop_chain >= 3),
                "metrics": [
                    f"• Ratio sauts parfaits (1-tick) : {bhop_ratio:.1f}% (Plafond humain régulier : < 35%)",
                    f"• Chaîne maximale de sauts parfaits : {bhop_chain} sauts",
                    f"• Volume total de sauts analysés : {bhop_total}",
                ],
                "reason_cheat": "Enchaînement de sauts avec 0 à 1 tick au sol à répétition. Impossible sans script externe, macro ou assist automatique.",
                "reason_suspect": "Fréquence élevée de sauts parfaitement cadencés. Possibilité de scrolls molette très réguliers.",
                "reason_clean": "Intervalles au sol variables et sauts non-synchronisés au tick près. Utilisation standard du clavier/molette.",
            },
            {
                "title": "🌪️ SPINBOT & ANTI-AIM (DÉSYNCHRONISATION)",
                "accent_color": THEME["cheat_spinbot"],
                "bg_color": THEME["cheat_spinbot_bg"],
                "is_cheat": (spin_speed > 90.0 or spin_pitch_viol > 0 or "SPINBOT" in flags_str or "PITCH" in flags_str),
                "is_suspect": (spin_jitter > 2000.0 or spin_desync >= 32 or "ANTI-AIM" in flags_str),
                "metrics": [
                    f"• Vitesse rotation Yaw continue : {spin_speed:.1f}°/tick (Seuil spin : > 90°/tick)",
                    f"• Violations Pitch hors-bornes : {spin_pitch_viol} tick(s)",
                    f"• Désynchronisation continue max : {spin_desync} ticks (Jitter : {spin_jitter:.0f})",
                ],
                "reason_cheat": "Modèle de vue artificiellement inversé ou rotation continue à 360° masquant le hitbox. Détection formelle de cheat Rage.",
                "reason_suspect": "Mouvements erratiques de caméra ou désynchronisation prolongée du modèle.",
                "reason_clean": "Orientation de vue stable et cohérente. Modèle de joueur parfaitement synchronisé sur le serveur.",
            },
            {
                "title": "⚡ TRIGGERBOT & RÉFLEXES INHUMAINS (SUB-TICK)",
                "accent_color": THEME["cheat_trigger"],
                "bg_color": THEME["cheat_trigger_bg"],
                "is_cheat": ((tb_shots >= 3 and tb_rt_med < 50.0) or "TRIGGERBOT" in flags_str),
                "is_suspect": ((tb_shots >= 3 and tb_rt_std < 15.0) or tb_burst >= 1 or "TRIGGER" in flags_str),
                "metrics": [
                    f"• Temps de réaction médian : {tb_rt_med:.1f} ms (Plafond humain : > 150 ms)" if tb_shots > 0 else "• Temps de réaction médian : Aucun tir ciblé",
                    f"• Écart-type des réactions : σ {tb_rt_std:.1f} ms (Régularité suspecte : < 15 ms)" if tb_shots > 0 else "• Écart-type : Données insuffisantes",
                    f"• Rafales automatiques (bursts) : {tb_burst} ({tb_shots} tirs analysés)",
                ],
                "reason_cheat": "Tir déclenché en moins de 50 ms dès que le réticule croise un pixel ennemi. Absence totale de temps de réaction neuronal.",
                "reason_suspect": "Temps de réaction extrêmement bas ou régularité surhumaine à la limite de la perception compétitive.",
                "reason_clean": "Délais de tir humains (200-280 ms) avec variations physiologiques normales.",
            },
        ]

        row_idx = 1
        for cinfo in cheats_config:
            if cinfo["is_cheat"]:
                badge_lbl = "🔴 ANOMALIE CRITIQUE"
                badge_bg = THEME["cheater_red_bg"]
                badge_fg = cinfo["accent_color"]
                reason = cinfo["reason_cheat"]
            elif cinfo["is_suspect"]:
                badge_lbl = "🟡 SUSPICION MODÉRÉE"
                badge_bg = THEME["suspect_amber_bg"]
                badge_fg = THEME["suspect_amber"]
                reason = cinfo["reason_suspect"]
            else:
                badge_lbl = "🟢 CONFORME"
                badge_bg = THEME["clean_green_bg"]
                badge_fg = THEME["clean_green"]
                reason = cinfo["reason_clean"]

            card = ctk.CTkFrame(
                scroll,
                fg_color=THEME["bg_card"],
                corner_radius=12,
                border_width=1,
                border_color=badge_fg if (cinfo["is_cheat"] or cinfo["is_suspect"]) else THEME["border"],
            )
            card.grid(row=row_idx, column=0, sticky="ew", padx=4, pady=5)
            card.grid_columnconfigure(0, weight=1)

            # Header row inside card
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 4))
            hdr.grid_columnconfigure(0, weight=1)

            lbl_t = ctk.CTkLabel(
                hdr,
                text=cinfo["title"],
                font=mono_font(size=11, bold=True),
                text_color=cinfo["accent_color"],
            )
            lbl_t.grid(row=0, column=0, sticky="w")

            badge = ctk.CTkLabel(
                hdr,
                text=badge_lbl,
                font=pill_font(),
                fg_color=badge_bg,
                text_color=badge_fg,
                corner_radius=12,
                padx=8,
                pady=2,
            )
            badge.grid(row=0, column=1, sticky="e")

            # Metrics frame
            met_frame = ctk.CTkFrame(card, fg_color=THEME["bg_secondary"], corner_radius=12)
            met_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=4)
            met_frame.grid_columnconfigure(0, weight=1)

            for m_i, m_text in enumerate(cinfo["metrics"]):
                lbl_m = ctk.CTkLabel(
                    met_frame,
                    text=m_text,
                    font=mono_font(size=9),
                    text_color=THEME["text_white"],
                    justify="left",
                )
                lbl_m.grid(row=m_i, column=0, sticky="w", padx=8, pady=2)

            # Reason description
            lbl_r = ctk.CTkLabel(
                card,
                text=f"👉 Motif d'analyse : {reason}",
                font=body_font(),
                text_color=THEME["text_muted"] if not (cinfo["is_cheat"] or cinfo["is_suspect"]) else badge_fg,
                wraplength=480,
                justify="left",
            )
            lbl_r.grid(row=2, column=0, sticky="w", padx=10, pady=(4, 8))

            row_idx += 1

    def get_current_report_text(self) -> str:
        """Returns the text currently active in the selected tab."""
        active_tab = self.tabview.get()
        if active_tab == "Ticket Support Faceit":
            return self.txt_faceit.get("1.0", "end-1c")
        elif active_tab == "🔍 Diagnostic des Suspicions":
            summary = generate_player_verdict_summary(self.player)
            status_info = get_status_colors(self.player.verdict, self.player.suspicion_score)
            return (
                f"=== RAPPORT DE DIAGNOSTIC BIOMÉCANIQUE CS2 ===\n"
                f"Joueur : {self.player.name} (SteamID: {self.player.steamid})\n"
                f"Verdict : {status_info['status_text']}\n"
                f"Motif : {summary}\n"
                f"Drapeaux d'infraction : {', '.join(self.player.violation_flags) if self.player.violation_flags else 'Aucun'}\n"
                f"================================================"
            )
        return self.txt_steam.get("1.0", "end-1c")

    def copy_current_report(self) -> str:
        """
        Copies the report text of the currently selected tab to the system clipboard
        and displays temporary button confirmation feedback.
        """
        text = self.get_current_report_text()

        try:
            pyperclip.copy(text)
        except Exception:
            try:
                self.clipboard_clear()
                self.clipboard_append(text)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

        # Visual feedback: update button text and color temporarily
        self.btn_copy.configure(
            text="✓ Copié !",
            fg_color=THEME["clean_green"],
            hover_color=THEME["clean_green"],
        )
        if self._reset_timer_id is not None:
            try:
                self.after_cancel(self._reset_timer_id)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
        self._reset_timer_id = self.after(2000, self._reset_copy_button)
        return text

    def _reset_copy_button(self) -> None:
        """Restores the copy button to its default state."""
        self._reset_timer_id = None
        try:
            if self.winfo_exists() and self.btn_copy.winfo_exists():
                self.btn_copy.configure(
                    text="📋 Copier le signalement",
                    fg_color=THEME["accent_cyan"],
                    hover_color="#00D2DF",
                )
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def _on_tab_changed(self) -> None:
        """Invoked when the active tab changes (Steam, Faceit, or 2D Snap)."""
        try:
            if self.tabview.get() == "📈 Tracé 2D du Snap":
                if self._draw_timer_id is not None:
                    try:
                        self.after_cancel(self._draw_timer_id)
                    except Exception as _e:
                            import logging
                            logging.debug(f"Ignored error: {_e}")
                self._draw_timer_id = self.after(50, self._draw_flick_trajectory)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def open_steam_profile(self) -> None:
        """Opens suspect's official Steam Community profile in the default browser."""
        url = ReportGenerator.get_steam_profile_url(self.player.steamid)
        try:
            webbrowser.open(url)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def _draw_flick_trajectory(self) -> None:
        """Draws the 2D viewangle flick trajectory on the canvas."""
        self._draw_timer_id = None
        try:
            if not self.winfo_exists():
                return
            if not hasattr(self, "canvas_flick") or not self.canvas_flick.winfo_exists():
                return
            canvas = self.canvas_flick
            canvas.delete("all")

            w = canvas.winfo_width()
            h = canvas.winfo_height()
            if w <= 10 or h <= 10:
                w, h = 420, 260

            # Draw dark cyber grid
            grid_color = "#151c2c"
            for gx in range(0, w, 40):
                canvas.create_line(gx, 0, gx, h, fill=grid_color, width=1)
            for gy in range(0, h, 40):
                canvas.create_line(0, gy, w, gy, fill=grid_color, width=1)

            # Look for aim snap events
            snap_event = None
            if hasattr(self.player, "combat_events") and self.player.combat_events:
                for ev in self.player.combat_events:
                    if ev.get("type") == "aim_snap":
                        if snap_event is None or ev.get("snap_angle", 0) > snap_event.get("snap_angle", 0):
                            snap_event = ev

            # Fallback to aim_metrics if no combat_event object was stored
            if not snap_event and hasattr(self.player, "aim_metrics") and self.player.aim_metrics:
                aim_snap = float(self.player.aim_metrics.get("aim_snap_max", 0.0))
                aim_jerk = float(self.player.aim_metrics.get("aim_jerk_max", 0.0))
                if aim_snap >= 5.0:
                    snap_event = {
                        "type": "aim_snap",
                        "snap_angle": aim_snap,
                        "jerk": aim_jerk,
                        "weapon": "weapon_ak47",
                        "tick": 12800,
                        "trajectory": [],
                    }

            if not snap_event or snap_event.get("snap_angle", 0) < 5.0:
                # Draw clean radar target
                cx, cy = w // 2, h // 2
                for r in [80, 50, 20]:
                    canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline="#1a3a2a", width=1)
                canvas.create_line(cx - 90, cy, cx + 90, cy, fill="#1a3a2a", width=1)
                canvas.create_line(cx, cy - 90, cx, cy + 90, fill="#1a3a2a", width=1)
                canvas.create_text(
                    cx, cy,
                    text="Visée biomécaniquement naturelle\nAucun snap robotique détecté",
                    fill="#10b981",
                    font=("Consolas", 10, "bold"),
                    justify="center"
                )
                self.lbl_vis_info.configure(text="Statut : Trajectoire fluide et conforme aux distributions humaines.")
                return

            # Trajectory points
            traj = snap_event.get("trajectory", [])
            snap_deg = snap_event.get("snap_angle", 0.0)
            jerk_val = snap_event.get("jerk", 0.0)
            weapon = snap_event.get("weapon", "weapon_ak47")
            tick_val = snap_event.get("tick", 0)

            self.lbl_vis_info.configure(
                text=f"Snap : {snap_deg:.1f}°/tick  |  Jerk : {jerk_val:.1f}  |  Arme : {weapon}  |  Tick : {tick_val}"
            )

            if len(traj) < 2:
                # Synthesize visual interpolation if points array was empty
                traj = [
                    {"yaw": 0.0, "pitch": 0.0, "tick": tick_val - 1},
                    {"yaw": snap_deg * 0.95, "pitch": snap_deg * 0.28, "tick": tick_val},
                    {"yaw": snap_deg, "pitch": snap_deg * 0.30, "tick": tick_val + 1}
                ]

            yaws = [pt["yaw"] for pt in traj]
            pitches = [pt["pitch"] for pt in traj]

            min_y, max_y = min(yaws), max(yaws)
            min_p, max_p = min(pitches), max(pitches)

            span_y = max(abs(max_y - min_y), 0.1)
            span_p = max(abs(max_p - min_p), 0.1)

            pad = 45
            def to_canvas(y_val, p_val):
                cx = pad + (y_val - min_y) / span_y * (w - 2 * pad)
                cy = h - (pad + (p_val - min_p) / span_p * (h - 2 * pad))
                return cx, cy

            # Direct interpolation line (dashed amber)
            p0_x, p0_y = to_canvas(yaws[0], pitches[0])
            p1_x, p1_y = to_canvas(yaws[-1], pitches[-1])
            canvas.create_line(p0_x, p0_y, p1_x, p1_y, fill="#f59e0b", dash=(3, 3), width=1)

            # Actual trajectory
            for i in range(1, len(traj)):
                x1, y1 = to_canvas(yaws[i-1], pitches[i-1])
                x2, y2 = to_canvas(yaws[i], pitches[i])
                seg_color = "#ef4444" if abs(yaws[i] - yaws[i-1]) > snap_deg * 0.4 else "#00f0ff"
                canvas.create_line(x1, y1, x2, y2, fill=seg_color, width=2)
                canvas.create_oval(x1 - 3, y1 - 3, x1 + 3, y1 + 3, fill="#00f0ff", outline="")

            # Markers
            canvas.create_oval(p0_x - 5, p0_y - 5, p0_x + 5, p0_y + 5, fill="#10b981", outline="#ffffff", width=1)
            canvas.create_text(p0_x, p0_y - 12, text="T0 (Start)", fill="#10b981", font=("Consolas", 8, "bold"))

            canvas.create_oval(p1_x - 6, p1_y - 6, p1_x + 6, p1_y + 6, fill="#ef4444", outline="#ffffff", width=1)
            canvas.create_text(p1_x, p1_y + 12, text=f"Snap {snap_deg:.1f}°", fill="#ef4444", font=("Consolas", 8, "bold"))
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def open_faceit(self) -> None:
        """Opens suspect's FaceitFinder profile in the default browser."""
        url = ReportGenerator.get_faceit_url(self.player.steamid)
        try:
            webbrowser.open(url)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def destroy(self) -> None:
        """Cleans up active timers and destroys the dialog."""
        if self._reset_timer_id is not None:
            try:
                self.after_cancel(self._reset_timer_id)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
            self._reset_timer_id = None
        if self._draw_timer_id is not None:
            try:
                self.after_cancel(self._draw_timer_id)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
            self._draw_timer_id = None
        super().destroy()
