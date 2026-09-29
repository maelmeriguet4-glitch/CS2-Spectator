from typing import Any, List

import customtkinter as ctk


class PlayerResultRow(ctk.CTkFrame):
    def __init__(self, master, player_telemetry: Any, **kwargs):
        super().__init__(master, **kwargs)
        self.player = player_telemetry
        self.is_expanded = False

        # Configurer les couleurs en fonction du verdict
        verdict = getattr(self.player, "verdict", "CLEAN")
        score = getattr(self.player, "suspicion_score", 0.0)
        
        bg_color = "transparent"
        text_color = "white"
        if verdict == "CHEATER":
            bg_color = "#3A1A1A"  # Dark red
            text_color = "#FF6B6B"
        elif verdict == "SUSPECT":
            bg_color = "#3A301A"  # Dark yellow/orange
            text_color = "#FFD166"

        self.configure(fg_color=bg_color)
        
        # Header (Ligne principale)
        self.header_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.header_frame.pack(fill="x", padx=5, pady=5)
        
        # Nom du joueur
        self.name_label = ctk.CTkLabel(
            self.header_frame, 
            text=f"{getattr(self.player, 'name', 'Inconnu')}", 
            font=("Roboto", 14, "bold"),
            text_color=text_color,
            width=150,
            anchor="w"
        )
        self.name_label.pack(side="left", padx=10)

        # Verdict et Score
        self.score_label = ctk.CTkLabel(
            self.header_frame, 
            text=f"Score: {score:.1f}%  |  {verdict}", 
            font=("Roboto", 12),
            text_color=text_color
        )
        self.score_label.pack(side="left", padx=20)

        # Bouton détails
        self.toggle_btn = ctk.CTkButton(
            self.header_frame, 
            text="▼ Détails", 
            width=80,
            fg_color="#333333",
            hover_color="#444444",
            command=self.toggle_details
        )
        self.toggle_btn.pack(side="right", padx=10)

        self.export_btn = ctk.CTkButton(
            self.header_frame, 
            text="📄 Exporter", 
            width=80,
            fg_color="#005C8A",
            hover_color="#0077B3",
            command=self.export_report
        )
        self.export_btn.pack(side="right", padx=10)

        # Contenu détaillé (Accordéon), masqué par défaut
        self.details_frame = ctk.CTkFrame(self, fg_color="#1E1E1E")
        
        # Extraire les pills ou flags
        flags = getattr(self.player, "violation_flags", [])
        if not flags:
            flags = ["Aucune anomalie détectée."]
            
        for flag in flags:
            flag_lbl = ctk.CTkLabel(
                self.details_frame, 
                text=f"• {flag}",
                font=("Roboto", 12),
                anchor="w",
                justify="left"
            )
            flag_lbl.pack(fill="x", padx=20, pady=2)

    def export_report(self):
        try:
            from src.core.export import export_player_report
            # Récupérer le demo_path si possible, sinon "Batch"
            export_player_report(self.player, demo_name="CS2_Analysis")
            
            # Change color briefly to indicate success
            self.export_btn.configure(text="✅ Exporté", fg_color="#28a745")
            self.after(2000, lambda: self.export_btn.configure(text="📄 Exporter", fg_color="#005C8A"))
        except Exception as e:
            self.export_btn.configure(text="❌ Erreur", fg_color="#dc3545")
            print(f"Erreur d'export: {e}")

    def toggle_details(self):
        if self.is_expanded:
            self.details_frame.pack_forget()
            self.toggle_btn.configure(text="▼ Détails")
            self.is_expanded = False
        else:
            self.details_frame.pack(fill="x", padx=10, pady=(0, 10))
            self.toggle_btn.configure(text="▲ Réduire")
            self.is_expanded = True


class DashboardPanel(ctk.CTkFrame):
    def __init__(self, master, match_results: List[Any], **kwargs):
        """
        match_results: Liste d'objets MatchAnalysisResult
        """
        super().__init__(master, **kwargs)
        self.match_results = match_results

        # Titre
        self.title_label = ctk.CTkLabel(
            self, 
            text="🏆 Résultats de l'analyse (Dashboard)", 
            font=("Roboto", 20, "bold")
        )
        self.title_label.pack(pady=20)

        # Liste scrollable pour les joueurs
        self.scroll_frame = ctk.CTkScrollableFrame(self, width=600, height=400)
        self.scroll_frame.pack(pady=10, padx=20, fill="both", expand=True)

        self._populate_results()

        # Bouton Retour
        self.back_btn = ctk.CTkButton(
            self, 
            text="⬅ Retour aux Démos", 
            command=self._go_back
        )
        self.back_btn.pack(pady=20)

    def _populate_results(self):
        # Flatten all players from all matches
        all_players = []
        for match in self.match_results:
            all_players.extend(getattr(match, "players", []))
            
        # Trier : CHEATER d'abord, puis SUSPECT, puis par score descendant
        def sort_key(p):
            v = getattr(p, "verdict", "CLEAN")
            s = getattr(p, "suspicion_score", 0.0)
            order = {"CHEATER": 0, "SUSPECT": 1, "CLEAN": 2}
            return (order.get(v, 2), -s)
            
        all_players.sort(key=sort_key)

        for p in all_players:
            row = PlayerResultRow(self.scroll_frame, p)
            row.pack(fill="x", pady=5)

    def _go_back(self):
        if hasattr(self.master, "show_replays_panel"):
            self.master.show_replays_panel()
        else:
            self.pack_forget()
