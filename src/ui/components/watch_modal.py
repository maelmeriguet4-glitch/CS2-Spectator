"""CS2 In-Game Replay Inspection Modal.

Provides an interactive dialog allowing users to either:
1. Automatically launch CS2 directly on the suspect replay & tick.
2. Force restart CS2 if it is already open.
3. Switch to the running CS2 game with the command pre-copied to clipboard.
"""

from __future__ import annotations

import logging
from typing import Any

import customtkinter as ctk

try:
    import pyperclip
except ImportError:
    pyperclip = None

from src.core.cs2_launcher import (
    bring_cs2_to_foreground,
    execute_cs2_launch,
    is_cs2_running,
)
from src.core.models import PlayerTelemetry
from src.ui.theme import (
    THEME,
    badge_font,
    header_font,
    mono_font,
    small_font,
)

logger = logging.getLogger(__name__)


class WatchCS2Modal(ctk.CTkToplevel):
    """Modal dialog to launch CS2 and inspect suspicious player moments."""

    def __init__(
        self,
        parent: Any,
        player: PlayerTelemetry,
        demo_path: str,
        target_tick: int,
        *args,
        **kwargs,
    ):
        super().__init__(parent)
        self.parent = parent
        self.player = player
        self.demo_path = demo_path
        self.target_tick = target_tick

        self.title(f"INSPECTION EN JEU // {self.player.name}")
        self.geometry("620x520")
        self.minsize(560, 460)
        self.configure(fg_color=THEME["bg_main"])

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

        self._build_ui()

    def _build_ui(self) -> None:
        cs2_running = is_cs2_running()

        container = ctk.CTkFrame(self, fg_color=THEME["bg_main"], corner_radius=0)
        container.pack(fill="both", expand=True, padx=24, pady=24)

        # Header Title
        lbl_title = ctk.CTkLabel(
            container,
            text="INSPECTION REPLAY // CS2",
            font=header_font(),
            text_color=THEME["text_white"],
            anchor="w",
        )
        lbl_title.pack(fill="x", pady=(0, 4))

        lbl_subtitle = ctk.CTkLabel(
            container,
            text=f"Analyse de l'action suspecte de {self.player.name} (Tick: {self.target_tick})",
            font=small_font(),
            text_color=THEME["text_muted"],
            anchor="w",
        )
        lbl_subtitle.pack(fill="x", pady=(0, 16))

        # Status Banner
        if cs2_running:
            status_bg = "#2D1B00"
            status_border = "#B45309"
            status_text = "⚠️ CS2 EST ACTUELLEMENT EN COURS D'EXÉCUTION"
            status_desc = (
                "Le moteur de CS2 ne permet pas de recharger une nouvelle démo sans passer par la console "
                "lorsque le jeu est déjà ouvert. L'Anti-Cheat a configuré les fichiers et préparé la commande !"
            )
        else:
            status_bg = "#062817"
            status_border = "#059669"
            status_text = "✅ CS2 EST PRÊT À ÊTRE LANCÉ DIRECTEMENT"
            status_desc = (
                "L'Anti-Cheat va démarrer Counter-Strike 2 via Steam et ouvrir directement "
                "le replay au moment suspect."
            )

        status_box = ctk.CTkFrame(
            container,
            fg_color=status_bg,
            border_width=1,
            border_color=status_border,
            corner_radius=10,
        )
        status_box.pack(fill="x", pady=(0, 16), padx=2)

        lbl_status = ctk.CTkLabel(
            status_box,
            text=status_text,
            font=badge_font(),
            text_color="#F3F4F6",
            anchor="w",
        )
        lbl_status.pack(fill="x", padx=14, pady=(10, 4))

        lbl_desc = ctk.CTkLabel(
            status_box,
            text=status_desc,
            font=small_font(),
            text_color="#D1D5DB",
            anchor="w",
            wraplength=520,
            justify="left",
        )
        lbl_desc.pack(fill="x", padx=14, pady=(0, 10))

        # Command & Instructions Box
        card_box = ctk.CTkFrame(
            container,
            fg_color=THEME["bg_secondary"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=10,
        )
        card_box.pack(fill="both", expand=True, pady=(0, 16), padx=2)

        lbl_card_title = ctk.CTkLabel(
            card_box,
            text="COMMANDE DE CONSOLE PRÉPARÉE :",
            font=badge_font(),
            text_color=THEME["text_muted"],
            anchor="w",
        )
        lbl_card_title.pack(fill="x", padx=16, pady=(14, 6))

        # Command row with copy button
        cmd_row = ctk.CTkFrame(card_box, fg_color=THEME["bg_panel"], corner_radius=8)
        cmd_row.pack(fill="x", padx=16, pady=(0, 12))

        self.cmd_str = "exec anticheat_watch"
        lbl_cmd = ctk.CTkLabel(
            cmd_row,
            text=self.cmd_str,
            font=mono_font(),
            text_color="#34D399",
            anchor="w",
        )
        lbl_cmd.pack(side="left", padx=12, pady=8, fill="x", expand=True)

        self.btn_copy = ctk.CTkButton(
            cmd_row,
            text="Copier",
            font=badge_font(),
            fg_color=THEME["btn_primary_bg"],
            hover_color=THEME["btn_primary_hover"],
            text_color=THEME["btn_primary_text"],
            height=28,
            width=70,
            corner_radius=6,
            command=self._copy_command,
        )
        self.btn_copy.pack(side="right", padx=8, pady=6)

        # Quick tip
        instructions = (
            "📌 Instructions en jeu :\n"
            "1. Ouvrez la console CS2 avec la touche ² (ou ~)\n"
            "2. Collez la commande (Ctrl + V) et appuyez sur Entrée\n"
            f"3. Appuyez sur F8 en jeu pour sauter directement au Tick {self.target_tick}"
        )
        lbl_inst = ctk.CTkLabel(
            card_box,
            text=instructions,
            font=small_font(),
            text_color=THEME["text_white"],
            anchor="w",
            justify="left",
        )
        lbl_inst.pack(fill="x", padx=16, pady=(0, 14))

        # Error status label (hidden until error occurs)
        self.lbl_error = ctk.CTkLabel(
            container,
            text="",
            font=small_font(),
            text_color="#ef4444",
            anchor="w",
        )
        self.lbl_error.pack(fill="x", side="bottom", pady=(0, 6))

        # Bottom Action Buttons
        actions_row = ctk.CTkFrame(container, fg_color="transparent")
        actions_row.pack(fill="x", side="bottom")

        if cs2_running:
            # Switch to CS2 button
            btn_switch = ctk.CTkButton(
                actions_row,
                text="🎮 Aller sur CS2",
                font=badge_font(),
                fg_color="#059669",
                hover_color="#047857",
                text_color="#FFFFFF",
                height=36,
                corner_radius=8,
                command=self._switch_to_cs2,
            )
            btn_switch.pack(side="left", padx=(0, 8))

            # Force restart button
            btn_restart = ctk.CTkButton(
                actions_row,
                text="🔄 Relancer CS2 sur la démo",
                font=badge_font(),
                fg_color=THEME["btn_secondary_bg"],
                hover_color=THEME["btn_secondary_hover"],
                text_color=THEME["btn_secondary_text"],
                height=36,
                corner_radius=8,
                command=self._force_restart_cs2,
            )
            btn_restart.pack(side="left", padx=(0, 8))
        else:
            # Direct Launch
            btn_launch = ctk.CTkButton(
                actions_row,
                text="🚀 Lancer CS2 maintenant",
                font=badge_font(),
                fg_color="#059669",
                hover_color="#047857",
                text_color="#FFFFFF",
                height=36,
                corner_radius=8,
                command=self._launch_fresh_cs2,
            )
            btn_launch.pack(side="left", padx=(0, 8))

        btn_close = ctk.CTkButton(
            actions_row,
            text="Fermer",
            font=badge_font(),
            fg_color="transparent",
            border_width=1,
            border_color=THEME["border"],
            text_color=THEME["text_muted"],
            hover_color=THEME["bg_secondary"],
            height=36,
            width=80,
            corner_radius=8,
            command=self.destroy,
        )
        btn_close.pack(side="right")

    def _copy_command(self) -> None:
        try:
            if pyperclip:
                pyperclip.copy(self.cmd_str)
            else:
                self.clipboard_clear()
                self.clipboard_append(self.cmd_str)
            self.btn_copy.configure(text="Copié !")
            self.after(1500, lambda: self.btn_copy.configure(text="Copier"))
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def _show_launch_error(self, message: str) -> None:
        if hasattr(self, "lbl_error") and self.lbl_error:
            self.lbl_error.configure(text=f"⚠️ {message}")

    def _switch_to_cs2(self) -> None:
        self._copy_command()
        bring_cs2_to_foreground()
        self.destroy()

    def _force_restart_cs2(self) -> None:
        self._copy_command()
        success, msg = execute_cs2_launch(self.demo_path, self.target_tick, force_restart=True)
        if success:
            self.destroy()
        else:
            self._show_launch_error(msg)

    def _launch_fresh_cs2(self) -> None:
        self._copy_command()
        success, msg = execute_cs2_launch(self.demo_path, self.target_tick, force_restart=False)
        if success:
            self.destroy()
        else:
            self._show_launch_error(msg)
