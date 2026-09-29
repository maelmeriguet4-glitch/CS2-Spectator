"""
CS2 Anti-Cheat — Application Principale (Tactical Dashboard)
Intégration des composants modernes : MatchHeader, ReplaysPanel, PlayerCard,
engine AntiCheat + queue async.
Compatible tests.unit.test_ui expectations.
"""

import multiprocessing
import os
import queue
import sys

import customtkinter as ctk

_DIR_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _DIR_RACINE not in sys.path:
    sys.path.insert(0, _DIR_RACINE)

from src.core.batch_processor import BatchProcessor
from src.core.engine import AntiCheatEngine
from src.core.logger import setup_logger
from src.core.models import MatchAnalysisResult, PlayerTelemetry
from src.ui.components.header import MatchHeader
from src.ui.components.player_card import PlayerCard as NewPlayerCard
from src.ui.components.replays_panel import ReplaysPanel
from src.ui.components.report_modal import ReportModal
from src.ui.theme import THEME, apply_dark_theme

logger = setup_logger("ui")

def _analyze_worker(engine, demo_path, msg_queue):
    """Worker global function for multiprocessing."""
    try:
        result = engine.analyze_demo(demo_path, progress_queue=msg_queue)
        msg_queue.put(("COMPLETE", result))
    except Exception as e:
        logger.error(f"Erreur worker process d'analyse : {e}", exc_info=True)
        msg_queue.put(("ERROR", str(e)))

class CS2AntiCheatApp(ctk.CTk):
    """
    Main Application Window for CS2 Anti-Cheat Replay Inspection.
    Features modern dark cyber layout, async parsing, rich cards, and reporting modal.
    """

    def __init__(self, model_path=None, model_type=None):
        super().__init__()
        apply_dark_theme()
        self.title("CS2 Anti-Cheat // Tactical Replay Inspection")
        self.geometry("1280x860")
        self.minsize(1100, 700)
        self.configure(fg_color=THEME["bg_main"])

        self._msg_queue = queue.Queue()
        self._analysis_process = None
        self._current_result = None
        self._player_cards: list[NewPlayerCard] = []

        self.engine = AntiCheatEngine(model_path=model_path, model_type=model_type)
        self.batch_processor = BatchProcessor(self.engine)

        self._build_layout()
        self.after(100, self._check_queue)

    def _build_layout(self):
        # 1. Header (Top)
        self.header = MatchHeader(self)
        self.header.pack(fill="x", padx=16, pady=(16, 8))

        # 2. Main split (Left: Replays, Right: Players)
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=16, pady=8)
        self.main_container.grid_columnconfigure(0, weight=0, minsize=340)
        self.main_container.grid_columnconfigure(1, weight=1)
        self.main_container.grid_rowconfigure(0, weight=1)

        # Left: Replays Panel
        self.replays_panel = ReplaysPanel(
            self.main_container, 
            on_select_replay=self._on_replay_selected,
            on_batch_analyze=self._on_batch_analyze
        )
        self.replays_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # Right: Player Cards Area
        self.right_container = ctk.CTkFrame(self.main_container, fg_color=THEME["bg_panel"], corner_radius=10, border_width=1, border_color=THEME["border"])
        self.right_container.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        # Right Top Bar: Progress + Team Filter
        self.top_control_bar = ctk.CTkFrame(self.right_container, fg_color="transparent")
        self.top_control_bar.pack(fill="x", padx=12, pady=10)

        self.progress_bar = ctk.CTkProgressBar(self.top_control_bar, height=12, fg_color=THEME["bg_card"], progress_color=THEME["accent_cyan"])
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 16))
        self.progress_bar.set(0)

        self.team_filter = ctk.CTkSegmentedButton(
            self.top_control_bar,
            values=["Tous les joueurs", "🔵 CT", "🟠 T"],
            command=self._on_filter_changed,
            selected_color=THEME["accent_blue"],
            selected_hover_color=THEME["accent_cyan"],
            fg_color=THEME["bg_card"],
            text_color="#FFFFFF"
        )
        self.team_filter.set("Tous les joueurs")
        self.team_filter.pack(side="right")

        # Right Center: Scrollable Cards Container
        self.scroll_cards = ctk.CTkScrollableFrame(self.right_container, fg_color=THEME["bg_main"])
        self.scroll_cards.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # 3. Status Bar (Bottom)
        self.status_bar = ctk.CTkFrame(self, height=28, fg_color=THEME["bg_panel"], corner_radius=0)
        self.status_bar.pack(fill="x", side="bottom")

        self.lbl_status = ctk.CTkLabel(self.status_bar, text="Prêt — Sélectionnez une démo", font=ctk.CTkFont(size=11), text_color=THEME["text_muted"])
        self.lbl_status.pack(side="left", padx=12, pady=4)
        # Legacy aliases
        self.label_statut = self.lbl_status
        self.label_progress = self.lbl_status

    def _on_replay_selected(self, demo_path: str):
        self._run_analysis(demo_path)

    def _on_batch_analyze(self, demo_paths: list[str]):
        if not demo_paths:
            return
        
        self.progress_bar.set(0)
        self.lbl_status.configure(text=f"🔄 Lancement de l'analyse par lot ({len(demo_paths)} fichiers)...")
        
        for w in self.scroll_cards.winfo_children():
            w.destroy()
        self._player_cards.clear()
        
        self.batch_processor.start_batch(demo_paths)

    def _run_analysis(self, demo_path: str):
        if self._analysis_process and self._analysis_process.is_alive():
            logger.warning("Tentative d'analyse alors qu'une autre analyse est déjà en cours.")
            self.lbl_status.configure(text="⚠️ Analyse déjà en cours... Veuillez patienter.")
            return
        self.header.set_loading(os.path.basename(demo_path))
        self.progress_bar.set(0)
        self.lbl_status.configure(text="🔄 Analyse en cours...")
        # Clear old cards
        for w in self.scroll_cards.winfo_children():
            w.destroy()
        self._player_cards.clear()
        
        # multiprocessing.Queue for progress/result
        self._msg_queue = multiprocessing.Queue()

        self._analysis_process = multiprocessing.Process(
            target=_analyze_worker,
            args=(self.engine, demo_path, self._msg_queue),
            daemon=True
        )
        self._analysis_process.start()

    def _check_queue(self):
        try:
            if not self.winfo_exists():
                return
        except Exception:
            return
            
        # Check single analysis queue
        try:
            while not self._msg_queue.empty():
                msg = self._msg_queue.get_nowait()
                kind = msg[0]
                if kind == "PROGRESS":
                    _, pct, text = msg
                    try:
                        self.progress_bar.set(float(pct))
                    except Exception as _e:
                            import logging
                            logging.debug(f"Ignored error: {_e}")
                    try:
                        self.lbl_status.configure(text=text)
                    except Exception as _e:
                            import logging
                            logging.debug(f"Ignored error: {_e}")
                elif kind == "COMPLETE":
                    _, result = msg
                    self._display_match_result(result)
                elif kind == "ERROR":
                    _, err = msg
                    try:
                        self.lbl_status.configure(text=f"Échec de l'analyse : {err}")
                        self.progress_bar.set(0)
                    except Exception as _e:
                            import logging
                            logging.debug(f"Ignored error: {_e}")
        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Exception dans la boucle _check_queue (single) : {e}", exc_info=True)
            
        # Check batch processing queue
        try:
            while not self.batch_processor.msg_queue.empty():
                msg = self.batch_processor.msg_queue.get_nowait()
                kind = msg[0]
                
                if kind == "BATCH_PROGRESS":
                    _, demo_path, text = msg
                    self.lbl_status.configure(text=text)
                    
                elif kind == "BATCH_COMPLETE":
                    _, demo_path, result = msg
                    self.batch_processor.completed_files += 1
                    pct = self.batch_processor.completed_files / self.batch_processor.total_files
                    self.progress_bar.set(pct)
                    self.lbl_status.configure(text=f"✅ {self.batch_processor.completed_files}/{self.batch_processor.total_files} fichiers analysés")
                    
                    # Store result and show it
                    self.batch_processor.results.append(result)
                    
                    # Update UI for this latest match if it's the only one, or append it
                    # For simplicity, we just display the last result. 
                    # Real batch mode might want an aggregated view.
                    self._display_match_result(result)
                    
                elif kind == "BATCH_ERROR":
                    _, demo_path, err = msg
                    self.batch_processor.completed_files += 1
                    self.batch_processor.errors.append((demo_path, err))
                    pct = self.batch_processor.completed_files / self.batch_processor.total_files
                    self.progress_bar.set(pct)
                    self.lbl_status.configure(text=f"⚠️ {self.batch_processor.completed_files}/{self.batch_processor.total_files} (Erreur sur un fichier)")
                    
                elif kind == "BATCH_ALL_DONE":
                    total = self.batch_processor.total_files
                    errs = len(self.batch_processor.errors)
                    succ = total - errs
                    self.lbl_status.configure(text=f"Lot terminé : {succ} succès, {errs} erreurs.")
                    self.progress_bar.set(1.0)
                    
                    # Cacher le main_container
                    if hasattr(self, 'main_container') and self.main_container:
                        self.main_container.pack_forget()
                        
                    # Afficher le DashboardPanel
                    from src.ui.components.dashboard_panel import DashboardPanel
                    if hasattr(self, 'dashboard_panel') and self.dashboard_panel:
                        self.dashboard_panel.destroy()
                        
                    self.dashboard_panel = DashboardPanel(self, match_results=self.batch_processor.results)
                    self.dashboard_panel.pack(fill="both", expand=True)

        except queue.Empty:
            pass
        except Exception as e:
            logger.error(f"Exception dans la boucle _check_queue (batch) : {e}", exc_info=True)

        try:
            self.after(100, self._check_queue)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    def _on_filter_changed(self, value: str):
        self._render_player_cards()

    def _render_player_cards(self):
        if not hasattr(self, '_all_sorted_players'):
            return
        for w in self.scroll_cards.winfo_children():
            w.destroy()
        self._player_cards.clear()

        filter_val = self.team_filter.get() if hasattr(self, 'team_filter') else "Tous"
        
        for p in self._all_sorted_players:
            if "CT" in filter_val and p.team_number != 3:
                continue
            if "🟠" in filter_val and p.team_number != 2:
                continue
            try:
                card = NewPlayerCard(
                    self.scroll_cards,
                    player=p,
                    demo_path=getattr(self, '_current_result', None).demo_path if hasattr(self, '_current_result') and self._current_result else None,
                    on_report=self.on_player_report,
                    on_view_flick=self.on_player_view_flick,
                    on_view_diagnostic=self.on_player_view_diagnostic,
                )
                card.pack(fill="x", padx=8, pady=4)
                self._player_cards.append(card)
            except Exception as e:
                logger.error(f"Erreur rendu carte joueur {p.name}: {e}")

    def _display_match_result(self, result: MatchAnalysisResult):
        self._current_result = result
        try:
            self.header.update_match_result(result)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        # Sort cheaters first
        self._all_sorted_players = sorted(
            result.players,
            key=lambda p: ({"CHEATER": 0, "SUSPECT": 1, "CLEAN": 2}.get(p.verdict, 3), -p.suspicion_score)
        )

        ct_count = sum(1 for p in result.players if p.team_number == 3)
        t_count = sum(1 for p in result.players if p.team_number == 2)
        try:
            self.team_filter.configure(
                values=[f"Tous ({len(result.players)})", f"🔵 CT ({ct_count})", f"🟠 T ({t_count})"]
            )
            self.team_filter.set(f"Tous ({len(result.players)})")
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        self._render_player_cards()

        # Progress done
        self.progress_bar.set(1.0)
        nb_cheat = sum(1 for p in result.players if p.verdict == "CHEATER")
        nb_sus = sum(1 for p in result.players if p.verdict == "SUSPECT")
        if nb_cheat:
            self.lbl_status.configure(text=f"✅ Analyse terminée — {nb_cheat} suspicion(s) élevée(s) | {nb_sus} suspect(s)")
        elif nb_sus:
            self.lbl_status.configure(text=f"✅ Analyse terminée — {nb_sus} suspect(s)")
        else:
            self.lbl_status.configure(text="✅ Analyse terminée — Aucun signal fort détecté")
        # Legacy alias
        if hasattr(self, 'label_match_info'):
            self.label_match_info.configure(text=result.global_verdict)

    def on_player_report(self, player: PlayerTelemetry):
        # Open report modal
        try:
            # Pass current result for context
            ReportModal(self, player=player, match_result=self._current_result)
        except Exception:
            # Fallback simple toplevel if ReportModal fails headless
            try:
                top = ctk.CTkToplevel(self)
                top.title(f"SIGNALEMENT JOUEUR // {player.name}")
                ctk.CTkLabel(top, text=f"Signalement {player.name} - {player.verdict}").pack(pady=20)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def on_player_view_flick(self, player: PlayerTelemetry):
        """Directly launches the 2D Snap Trajectory analysis modal for the selected player."""
        try:
            ReportModal(
                self,
                player=player,
                match_result=self._current_result,
                initial_tab="📈 Tracé 2D du Snap",
            )
        except Exception:
            try:
                ReportModal(self, player=player, initial_tab="📈 Tracé 2D du Snap")
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def on_player_view_diagnostic(self, player: PlayerTelemetry):
        """Directly launches the Cheat Suspicion Diagnostic modal for the selected player."""
        try:
            ReportModal(
                self,
                player=player,
                match_result=self._current_result,
                initial_tab="🔍 Diagnostic des Suspicions",
            )
        except Exception:
            try:
                ReportModal(self, player=player, initial_tab="🔍 Diagnostic des Suspicions")
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def show_replays_panel(self):
        if hasattr(self, 'dashboard_panel') and self.dashboard_panel:
            self.dashboard_panel.pack_forget()
        self.main_container.pack(fill="both", expand=True, padx=16, pady=8)

# Legacy alias for old main
AntiCheatApp = CS2AntiCheatApp
