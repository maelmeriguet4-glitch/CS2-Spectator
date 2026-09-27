"""
Replays Panel Component.
Provides CS2 replay auto-discovery, interactive match selector, manual demo browser,
and real-time folder watcher toggle.
"""

import os
from typing import Callable, List, Optional

import customtkinter as ctk

from src.core.models import ReplayInfo
from src.core.scanner import ReplayScanner
from src.core.watcher import ReplayWatcher
from src.ui.theme import (
    THEME,
    header_font,
    mono_font,
    small_font,
)


class ReplayItemWidget(ctk.CTkFrame):
    """
    Clickable list item representing an individual CS2 replay demo.
    """

    def __init__(
        self,
        master,
        replay: ReplayInfo,
        on_click: Callable[[ReplayInfo], None],
        is_selected: bool = False,
        **kwargs,
    ):
        self.replay = replay
        self.on_click_callback = on_click
        self.is_selected = is_selected

        bg_col = THEME["bg_secondary"] if is_selected else THEME["bg_card"]
        border_col = THEME["accent_cyan"] if is_selected else THEME["border"]

        super().__init__(
            master,
            fg_color=bg_col,
            border_width=1,
            border_color=border_col,
            corner_radius=12,
            cursor="hand2",
            **kwargs,
        )

        # Top row: Map name & Size badge
        self.top_row = ctk.CTkFrame(self, fg_color="transparent")
        self.top_row.pack(fill="x", padx=10, pady=(8, 2))

        map_name = (replay.map_name or "Carte Inconnue").upper()
        self.lbl_map = ctk.CTkLabel(
            self.top_row,
            text=map_name,
            font=mono_font(size=11, bold=True),
            text_color=THEME["accent_cyan"] if is_selected else THEME["text_white"],
        )
        self.lbl_map.pack(side="left")

        self.lbl_size = ctk.CTkLabel(
            self.top_row,
            text=replay.formatted_size,
            font=mono_font(size=10),
            text_color=THEME["text_muted"],
        )
        self.lbl_size.pack(side="right")

        # Bottom row: Date & Truncated filename
        self.bottom_row = ctk.CTkFrame(self, fg_color="transparent")
        self.bottom_row.pack(fill="x", padx=10, pady=(0, 8))

        self.lbl_date = ctk.CTkLabel(
            self.bottom_row,
            text=replay.formatted_time,
            font=small_font(),
            text_color=THEME["text_dim"],
        )
        self.lbl_date.pack(side="left")

        # Bind click events to all sub-elements
        self.bind("<Button-1>", self._handle_click)
        self.lbl_map.bind("<Button-1>", self._handle_click)
        self.lbl_size.bind("<Button-1>", self._handle_click)
        self.lbl_date.bind("<Button-1>", self._handle_click)
        self.top_row.bind("<Button-1>", self._handle_click)
        self.bottom_row.bind("<Button-1>", self._handle_click)

    def _handle_click(self, event=None):
        if self.on_click_callback:
            self.on_click_callback(self.replay)

    def set_selected(self, selected: bool):
        self.is_selected = selected
        bg_col = THEME["bg_secondary"] if selected else THEME["bg_card"]
        border_col = THEME["accent_cyan"] if selected else THEME["border"]
        text_col = THEME["accent_cyan"] if selected else THEME["text_white"]

        self.configure(fg_color=bg_col, border_color=border_col)
        self.lbl_map.configure(text_color=text_col)


class ReplaysPanel(ctk.CTkFrame):
    """
    Sidebar control panel containing the replay selector, folder watcher toggle,
    manual file browser, and replay listing.
    """

    def __init__(
        self,
        master,
        on_select_replay: Optional[Callable[[str], None]] = None,
        on_batch_analyze: Optional[Callable[[List[str]], None]] = None,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=THEME["bg_panel"],
            corner_radius=12,
            border_width=0,
            **kwargs,
        )

        self.on_select_replay = on_select_replay
        self.on_batch_analyze = on_batch_analyze
        self._watcher: Optional[ReplayWatcher] = None
        self._replays_list: List[ReplayInfo] = []
        self._selected_replay_path: Optional[str] = None
        self._item_widgets: List[ReplayItemWidget] = []
        self._replay_dir: Optional[str] = None

        # ----------------------------------------------------------------------
        # HEADER & SECTION TITLE
        # ----------------------------------------------------------------------
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=16, pady=(16, 12))

        self.lbl_title = ctk.CTkLabel(
            self.header_frame,
            text="⚡ REPLAYS & DÉMOS",
            font=header_font(),
            text_color=THEME["text_white"],
        )
        self.lbl_title.pack(anchor="w")

        self.lbl_subtitle = ctk.CTkLabel(
            self.header_frame,
            text="Détection automatique CS2",
            font=small_font(),
            text_color=THEME["text_muted"],
        )
        self.lbl_subtitle.pack(anchor="w")

        # ----------------------------------------------------------------------
        # WATCHER TOGGLE CARD
        # ----------------------------------------------------------------------
        self.watcher_card = ctk.CTkFrame(
            self,
            fg_color=THEME["bg_card"],
            border_width=1,
            border_color=THEME["border"],
            corner_radius=12,
        )
        self.watcher_card.pack(fill="x", padx=16, pady=(0, 12))

        self.watcher_header = ctk.CTkFrame(self.watcher_card, fg_color="transparent")
        self.watcher_header.pack(fill="x", padx=12, pady=(10, 6))

        self.lbl_watcher_status = ctk.CTkLabel(
            self.watcher_header,
            text="📡 Surveillance : Inactive",
            font=mono_font(size=11, bold=True),
            text_color=THEME["text_muted"],
        )
        self.lbl_watcher_status.pack(side="left")

        # Toggle Button
        self.btn_watcher_toggle = ctk.CTkButton(
            self.watcher_card,
            text="Armer la surveillance",
            font=small_font(),
            fg_color=THEME["btn_secondary_bg"],
            hover_color=THEME["btn_secondary_hover"],
            text_color=THEME["text_white"],
            height=28,
            corner_radius=12,
            command=self.toggle_watcher,
        )
        self.btn_watcher_toggle.pack(fill="x", padx=12, pady=(0, 10))

        # ----------------------------------------------------------------------
        # ACTION BUTTONS: BROWSE & REFRESH
        # ----------------------------------------------------------------------
        self.btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.btn_frame.pack(fill="x", padx=16, pady=(0, 12))

        self.btn_browse = ctk.CTkButton(
            self.btn_frame,
            text="📁 Parcourir...",
            font=small_font(),
            fg_color=THEME["btn_secondary_bg"],
            hover_color=THEME["btn_secondary_hover"],
            text_color=THEME["text_white"],
            height=32,
            corner_radius=12,
            command=self.browse_demo_file,
        )
        self.btn_browse.pack(side="left", fill="x", expand=True, padx=(0, 6))

        self.btn_refresh = ctk.CTkButton(
            self.btn_frame,
            text="🔄",
            width=36,
            height=32,
            font=small_font(),
            fg_color=THEME["btn_secondary_bg"],
            hover_color=THEME["btn_secondary_hover"],
            text_color=THEME["text_white"],
            corner_radius=12,
            command=self.refresh_replays,
        )
        self.btn_refresh.pack(side="right")

        self.btn_faceit = ctk.CTkButton(
            self,
            text="☁️ Importer depuis Faceit",
            font=small_font(),
            fg_color="#ff5500",  # Faceit orange
            hover_color="#e64c00",
            text_color="#ffffff",
            height=32,
            corner_radius=12,
            command=self._open_faceit_modal,
        )
        self.btn_faceit.pack(fill="x", padx=16, pady=(0, 12))

        self.btn_batch = ctk.CTkButton(
            self,
            text="⚙️ Analyser tout (Batch)",
            font=small_font(),
            fg_color=THEME.get("accent_cyan", "#00bcd4"),
            hover_color=THEME.get("accent_blue", "#2196f3"),
            text_color="#ffffff",
            height=32,
            corner_radius=12,
            command=self._handle_batch_analyze,
        )
        self.btn_batch.pack(fill="x", padx=16, pady=(0, 12))

        # ----------------------------------------------------------------------
        # REPLAYS LIST HEADER
        # ----------------------------------------------------------------------
        self.list_header = ctk.CTkFrame(self, fg_color="transparent")
        self.list_header.pack(fill="x", padx=16, pady=(0, 6))

        self.lbl_matches_count = ctk.CTkLabel(
            self.list_header,
            text="MATCHS RÉCENTS",
            font=mono_font(size=11, bold=True),
            text_color=THEME["text_muted"],
        )
        self.lbl_matches_count.pack(side="left")

        # ----------------------------------------------------------------------
        # SCROLLABLE REPLAYS CONTAINER
        # ----------------------------------------------------------------------
        self.scroll_replays = ctk.CTkScrollableFrame(
            self,
            fg_color=THEME["bg_panel"],
            corner_radius=12,
            scrollbar_button_color=THEME["border"],
            scrollbar_button_hover_color=THEME["accent_cyan"],
        )
        self.scroll_replays.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # Initial loading of replays
        self.refresh_replays()

    # ==========================================================================
    # Replay Discovery & Selection
    # ==========================================================================
    def refresh_replays(self) -> None:
        """
        Scans for CS2 replays and re-populates the scrollable list.
        """
        # Discover replay folder if not already cached
        if not self._replay_dir or not os.path.exists(self._replay_dir):
            self._replay_dir = ReplayScanner.find_cs2_replay_dir()

        self._replays_list = ReplayScanner.list_replays(self._replay_dir)[:50]

        # Clear existing widgets
        for widget in self._item_widgets:
            widget.destroy()
        self._item_widgets.clear()

        count = len(self._replays_list)
        self.lbl_matches_count.configure(text=f"MATCHS RÉCENTS ({count})")

        if count == 0:
            lbl_empty = ctk.CTkLabel(
                self.scroll_replays,
                text="Aucune démo trouvée.\nUtilisez 'Parcourir...' pour charger un fichier.",
                font=small_font(),
                text_color=THEME["text_dim"],
                justify="center",
            )
            lbl_empty.pack(pady=30)
            return

        for replay in self._replays_list:
            is_sel = (replay.file_path == self._selected_replay_path)
            item = ReplayItemWidget(
                self.scroll_replays,
                replay=replay,
                on_click=self._handle_replay_clicked,
                is_selected=is_sel,
            )
            item.pack(fill="x", pady=4)
            self._item_widgets.append(item)

    def _handle_replay_clicked(self, replay: ReplayInfo) -> None:
        """
        Handles user clicking a replay item in the list.
        """
        self._selected_replay_path = replay.file_path
        for widget in self._item_widgets:
            widget.set_selected(widget.replay.file_path == replay.file_path)

        if self.on_select_replay:
            self.on_select_replay(replay.file_path)

    def _handle_batch_analyze(self) -> None:
        """
        Handles user clicking the batch analyze button.
        """
        if self.on_batch_analyze and self._replays_list:
            paths = [r.file_path for r in self._replays_list]
            self.on_batch_analyze(paths)

    def browse_demo_file(self) -> None:
        """
        Opens Windows file dialog to browse for any external .dem file.
        """
        initial_dir = self._replay_dir if self._replay_dir and os.path.exists(self._replay_dir) else os.path.abspath(".")
        filepath = ctk.filedialog.askopenfilename(
            title="Sélectionner une démo CS2 (.dem)",
            initialdir=initial_dir,
            filetypes=[("CS2 Replay Demo", "*.dem"), ("Tous les fichiers", "*.*")],
        )

        if filepath and os.path.exists(filepath):
            self._selected_replay_path = filepath
            # Check if this file is in our current list
            found = False
            for w in self._item_widgets:
                if os.path.abspath(w.replay.file_path) == os.path.abspath(filepath):
                    w.set_selected(True)
                    found = True
                else:
                    w.set_selected(False)

            if not found:
                # Refresh list so it includes or highlights this demo
                self.refresh_replays()
                for w in self._item_widgets:
                    if os.path.abspath(w.replay.file_path) == os.path.abspath(filepath):
                        w.set_selected(True)

            if self.on_select_replay:
                self.on_select_replay(filepath)

    # ==========================================================================
    # Real-Time Watcher Integration
    # ==========================================================================
    def toggle_watcher(self) -> None:
        """
        Toggles the background ReplayWatcher on or off.
        """
        if self._watcher is not None:
            self.stop_watcher()
        else:
            self.start_watcher()

    def start_watcher(self) -> None:
        """
        Arms and starts the real-time directory watcher.
        """
        if not self._replay_dir or not os.path.exists(self._replay_dir):
            self._replay_dir = ReplayScanner.find_cs2_replay_dir()

        if not self._replay_dir or not os.path.exists(self._replay_dir):
            self.lbl_watcher_status.configure(
                text="❌ Dossier CS2 introuvable",
                text_color=THEME["cheater_red"],
            )
            return

        def _on_new_replay(new_replay: ReplayInfo):
            # Dispatch to main Tkinter thread safely
            self.after(0, lambda: self._handle_watcher_event(new_replay))

        try:
            self._watcher = ReplayWatcher(
                target_dir=self._replay_dir,
                on_new_replay_callback=_on_new_replay,
                debounce_interval=1.0,
            )
            self._watcher.start()

            self.lbl_watcher_status.configure(
                text="📡 Surveillance : Active",
                text_color=THEME["accent_cyan"],
            )
            self.btn_watcher_toggle.configure(
                text="Désarmer la surveillance",
                fg_color=THEME["cheater_red_bg"],
                hover_color=THEME["cheater_red"],
                text_color=THEME["cheater_red_text"],
            )
        except Exception as err:
            self.lbl_watcher_status.configure(
                text=f"❌ Erreur: {str(err)[:20]}",
                text_color=THEME["cheater_red"],
            )

    def stop_watcher(self) -> None:
        """
        Stops the real-time folder watcher.
        """
        if self._watcher:
            try:
                self._watcher.stop()
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
            self._watcher = None

        self.lbl_watcher_status.configure(
            text="📡 Surveillance : Inactive",
            text_color=THEME["text_muted"],
        )
        self.btn_watcher_toggle.configure(
            text="Armer la surveillance",
            fg_color=THEME["btn_secondary_bg"],
            hover_color=THEME["btn_secondary_hover"],
            text_color=THEME["text_white"],
        )

    def _handle_watcher_event(self, new_replay: ReplayInfo) -> None:
        """
        Called on main thread when watcher catches a new completely written demo.
        """
        self.refresh_replays()
        self._selected_replay_path = new_replay.file_path
        for w in self._item_widgets:
            w.set_selected(w.replay.file_path == new_replay.file_path)

        if self.on_select_replay:
            self.on_select_replay(new_replay.file_path)

    # ==========================================================================
    # Public API
    # ==========================================================================
    def _open_faceit_modal(self) -> None:
        """Opens the Faceit Import modal."""
        # Ensure we have a valid folder to save to
        import os

        from src.ui.components.faceit_modal import FaceitModal
        
        target_dir = self._replay_dir
        if not target_dir or not os.path.isdir(target_dir):
            target_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
            target_dir = os.path.join(target_dir, "CS2AntiCheat", "Demos")
            os.makedirs(target_dir, exist_ok=True)
            self._replay_dir = target_dir
            
        def on_done():
            self.refresh_replays()
            
        FaceitModal(self.winfo_toplevel(), target_folder=target_dir, on_download_complete=on_done)
    def get_selected_replay(self) -> Optional[str]:
        """Returns the absolute path to the currently selected replay demo."""
        return self._selected_replay_path

    def is_watcher_active(self) -> bool:
        """Returns True if the watcher is actively running."""
        return self._watcher is not None and self._watcher.is_running()
