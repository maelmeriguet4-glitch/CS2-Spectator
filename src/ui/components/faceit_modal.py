"""
Faceit Import Modal
Allows users to link their Faceit account and download recent replays.
"""
import json
import os
import threading
from datetime import datetime
from pathlib import Path

import customtkinter as ctk

from src.core.faceit import FaceitAPI
from src.ui.theme import THEME

FACEIT_CONFIG_PATH = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "CS2AntiCheat" / "faceit.json"

class FaceitModal(ctk.CTkToplevel):
    def __init__(self, master, target_folder: str, on_download_complete=None):
        super().__init__(master)
        self.title("Faceit // Synchronisation")
        self.geometry("600x650")
        self.minsize(500, 600)
        self.configure(fg_color=THEME["bg_main"])
        
        self.target_folder = target_folder
        self.on_download_complete = on_download_complete
        
        # Make it modal
        self.transient(master)
        self.grab_set()

        self.api_key = ""
        self.nickname = ""
        self.player_id = ""
        
        self._load_config()
        self._build_layout()
        
        if self.api_key and self.nickname:
            self._fetch_matches()

    def _load_config(self):
        if FACEIT_CONFIG_PATH.exists():
            try:
                with open(FACEIT_CONFIG_PATH, "r") as f:
                    data = json.load(f)
                    self.nickname = data.get("nickname", "")
                    self.player_id = data.get("player_id", "")
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

    def _save_config(self):
        FACEIT_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(FACEIT_CONFIG_PATH, "w") as f:
            json.dump({
                "nickname": self.nickname,
                "player_id": self.player_id
            }, f)

    def _build_layout(self):
        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # 1. Header (Settings)
        settings_frame = ctk.CTkFrame(self, fg_color=THEME["bg_panel"])
        settings_frame.grid(row=0, column=0, sticky="ew", padx=16, pady=16)
        
        ctk.CTkLabel(settings_frame, text="Paramètres Faceit", font=ctk.CTkFont(weight="bold", size=14)).pack(pady=(10, 5))
        
        input_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        input_frame.pack(fill="x", padx=10, pady=5)
        
        self.entry_key = ctk.CTkEntry(input_frame, placeholder_text="Faceit Developer API Key (Bearer Token)", show="*", width=300)
        self.entry_key.pack(side="left", padx=5, fill="x", expand=True)
        if self.api_key:
            self.entry_key.insert(0, self.api_key)
        
        self.entry_nick = ctk.CTkEntry(input_frame, placeholder_text="Pseudo Faceit", width=150)
        self.entry_nick.pack(side="left", padx=5)
        if self.nickname:
            self.entry_nick.insert(0, self.nickname)
        
        btn_save = ctk.CTkButton(settings_frame, text="Connecter", fg_color=THEME["accent_cyan"], text_color="#000000", command=self._on_connect)
        btn_save.pack(pady=10)

        # 2. Status Label
        self.lbl_status = ctk.CTkLabel(self, text="Entrez votre clé API et pseudo pour commencer.", text_color=THEME["text_muted"])
        self.lbl_status.grid(row=1, column=0, pady=5)

        # 3. Matches List
        self.scroll_matches = ctk.CTkScrollableFrame(self, fg_color=THEME["bg_panel"])
        self.scroll_matches.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def _on_connect(self):
        self.api_key = self.entry_key.get().strip()
        self.nickname = self.entry_nick.get().strip()
        
        if not self.api_key or not self.nickname:
            self.lbl_status.configure(text="Veuillez remplir tous les champs.", text_color=THEME["cheater_red"])
            return
            
        self.lbl_status.configure(text="Connexion en cours...", text_color=THEME["text_muted"])
        threading.Thread(target=self._verify_and_fetch, daemon=True).start()

    def _verify_and_fetch(self):
        api = FaceitAPI(self.api_key)
        try:
            # Get player info
            p_info = api.get_player_info(self.nickname)
            self.player_id = p_info["player_id"]
            self._save_config()
            
            self.after(0, lambda: self.lbl_status.configure(text=f"Connecté en tant que {self.nickname} ! Récupération des matchs...", text_color=THEME["accent_cyan"]))
            self.after(0, self._fetch_matches)
        except Exception as e:
            self.after(0, lambda err=e: self.lbl_status.configure(text=f"Erreur : {err}", text_color=THEME["cheater_red"]))

    def _fetch_matches(self):
        if not self.api_key or not self.player_id:
            return
            
        def worker():
            api = FaceitAPI(self.api_key)
            try:
                matches = api.get_recent_matches(self.player_id, limit=20)
                
                def update_ui():
                    # clear scroll
                    for w in self.scroll_matches.winfo_children():
                        w.destroy()
                    
                    if not matches:
                        lbl = ctk.CTkLabel(self.scroll_matches, text="Aucun match CS2 récent trouvé.")
                        lbl.pack(pady=20)
                    
                    for m in matches:
                        self._create_match_row(m)
                        
                    self.lbl_status.configure(text="Matchs chargés.", text_color=THEME["text_muted"])
                
                self.after(0, update_ui)
                
            except Exception as e:
                self.after(0, lambda err=e: self.lbl_status.configure(text=f"Erreur historique : {err}", text_color=THEME["cheater_red"]))
                
        threading.Thread(target=worker, daemon=True).start()

    def _create_match_row(self, match_data: dict):
        row = ctk.CTkFrame(self.scroll_matches, fg_color=THEME["bg_card"], corner_radius=8)
        row.pack(fill="x", padx=5, pady=5)
        
        # Extract basic info
        match_id = match_data.get("match_id", "")
        # convert timestamp
        ts = match_data.get("started_at", 0)
        date_str = datetime.fromtimestamp(ts).strftime("%d/%m/%Y %H:%M") if ts else "Date inconnue"
        
        # result (win/loss) -> need to check if our player's faction won.
        results = match_data.get("results", {})
        
        # We don't have faction info from the simple history endpoint easily without details, 
        # so we'll just show map and score if available.
        score = results.get("score", {})
        score_str = f"{score.get('faction1', 0)} - {score.get('faction2', 0)}" if score else "Score caché"
        
        lbl_date = ctk.CTkLabel(row, text=date_str, font=ctk.CTkFont(size=12, weight="bold"))
        lbl_date.pack(side="left", padx=10, pady=10)
        
        lbl_info = ctk.CTkLabel(row, text=f"Faceit Match | {score_str}", font=ctk.CTkFont(size=12))
        lbl_info.pack(side="left", padx=10)
        
        # Check if already downloaded
        dem_path = os.path.join(self.target_folder, f"faceit_{match_id}.dem")
        if os.path.exists(dem_path):
            btn = ctk.CTkButton(row, text="Déjà téléchargé", state="disabled", width=120)
            btn.pack(side="right", padx=10)
        else:
            btn = ctk.CTkButton(row, text="Télécharger", width=120, fg_color=THEME["accent_cyan"], text_color="#000",
                                command=lambda: self._download_match(match_id, btn, dem_path))
            btn.pack(side="right", padx=10)

    def _download_match(self, match_id: str, button: ctk.CTkButton, dest_path: str):
        button.configure(state="disabled", text="Préparation...")
        print(f"[DEBUG] _download_match started for match_id: {match_id}")
        
        def worker():
            print("[DEBUG] worker thread started")
            api = FaceitAPI(self.api_key)
            try:
                print("[DEBUG] fetching match details...")
                details = api.get_match_details(match_id)
                print(f"[DEBUG] details fetched, keys: {details.keys()}")
                demo_urls = details.get("demo_url", [])
                if not demo_urls:
                    print("[DEBUG] no demo URLs found!")
                    self.after(0, lambda: button.configure(text="Pas de démo", fg_color=THEME["cheater_red"]))
                    return
                
                url = demo_urls[0]
                print(f"[DEBUG] demo url selected: {url}")
                
                import time
                last_update = [0]
                
                def prog(pct, msg=""):
                    now = time.time()
                    if now - last_update[0] > 0.1 or pct >= 1.0:
                        last_update[0] = now
                        # We use try/except inside the lambda just in case
                        self.after(0, lambda p=pct, m=msg: button.configure(text=f"{int(p*100)}% {m}") if p else button.configure(text=m))
                    
                print("[DEBUG] starting FaceitAPI.download_and_extract_demo")
                FaceitAPI.download_and_extract_demo(url, dest_path, progress_callback=prog)
                print("[DEBUG] download_and_extract_demo finished successfully")
                
                self.after(0, lambda: button.configure(text="Terminé !", fg_color=THEME["clean_green"]))
                
                if getattr(self, 'on_download_complete', None):
                    self.after(0, self.on_download_complete)
                    
            except Exception as e:
                import traceback
                print(f"[DEBUG] EXCEPTION IN WORKER: {e}")
                traceback.print_exc()
                error_msg = str(e)
                if "getaddrinfo failed" in error_msg or "no host given" in error_msg:
                    error_msg = "Démo introuvable/expirée (serveur Faceit injoignable)."
                elif "HTTP Error 404" in error_msg or "HTTP Error 403" in error_msg:
                    error_msg = "Démo expirée ou supprimée par Faceit."
                
                self.after(0, lambda: button.configure(text="Erreur", fg_color=THEME["cheater_red"]))
                self.after(0, lambda err=error_msg: self.lbl_status.configure(text=f"Erreur : {err}", text_color=THEME["cheater_red"]))
                
        import threading
        threading.Thread(target=worker, daemon=True).start()
