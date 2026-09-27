"""
CS2 Spectator - Adaptateur CS2CD (Counter-Strike 2 Cheat Detection)
Permet d'ingérer les fichiers Parquet (ticks) et JSON (événements) de CS2CD
en exposant strictement l'interface attendue par les analyseurs de CS2 Spectator (DemoData).
"""

import json
import logging
import os
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Colonnes minimales requises pour alimenter l'ensemble des analyseurs
COLONNES_REQUISES_TICKS = [
    "tick",
    "steamid",
    "team_num",
    "X",
    "Y",
    "Z",
    "pitch",
    "yaw",
    "health",
    "spotted",
    "velocity_X",
    "velocity_Y",
    "velocity_Z",
    "is_airborne",
    "active_weapon_name",
    "shots_fired",
]


class CS2CDAdapter:
    """
    Adaptateur haute performance pour les replays CS2CD.
    Lit les ticks (Parquet) par projection de colonnes (économie RAM)
    et structure les événements (JSON) pour compatibilité avec DemoData.
    """

    def __init__(self, parquet_path: str, json_path: str):
        self.chemin_demo = parquet_path
        self.chemin_json = json_path
        self.valide = False
        self.header: Dict[str, Any] = {
            "map_name": "unknown",
            "server_name": "CS2CD_Server",
            "playback_time": 0.0,
        }

        self.ticks = pd.DataFrame()
        self.tirs = pd.DataFrame()
        self.touches = pd.DataFrame()
        self.morts = pd.DataFrame()

        self.joueurs: List[str] = []
        self.joueurs_info: Dict[str, Dict[str, Any]] = {}

        if not os.path.exists(parquet_path) or not os.path.exists(json_path):
            logger.warning(f"[CS2CDAdapter] Fichier introuvable: {parquet_path} ou {json_path}")
            return

        self._charger_ticks(parquet_path)
        self._charger_evenements(json_path)

        if not self.ticks.empty and len(self.joueurs) > 0:
            self.valide = True

    def _charger_ticks(self, parquet_path: str):
        """Charge uniquement les colonnes nécessaires via PyArrow et nettoie les données."""
        try:
            import pyarrow.parquet as pq

            schema = pq.read_schema(parquet_path)
            cols_dispos = set(schema.names)
            cols_a_lire = [c for c in COLONNES_REQUISES_TICKS if c in cols_dispos]

            # Charger uniquement les colonnes utiles
            df = pd.read_parquet(parquet_path, columns=cols_a_lire)

            if df.empty:
                return

            # Garantir la présence de toutes les colonnes requises avec valeurs par défaut
            for col in COLONNES_REQUISES_TICKS:
                if col not in df.columns:
                    if col == "active_weapon_name":
                        df[col] = "weapon_unknown"
                    elif col == "is_airborne":
                        df[col] = False
                    elif col == "spotted":
                        df[col] = False
                    elif col == "health":
                        df[col] = 100
                    elif col == "steamid":
                        df[col] = "Player_Unknown"
                    else:
                        df[col] = 0.0

            # Normaliser types et valeurs
            df["tick"] = pd.to_numeric(df["tick"], errors="coerce").fillna(0).astype(int)
            df["steamid"] = df["steamid"].astype(str).str.strip()
            df["name"] = df["steamid"]  # Couche identité interne cohérente
            df["health"] = pd.to_numeric(df["health"], errors="coerce").fillna(0)
            df["team_num"] = pd.to_numeric(df["team_num"], errors="coerce").fillna(0).astype(int)

            # Nettoyer Inf / NaN dans les colonnes numériques
            num_cols = df.select_dtypes(include=[np.number]).columns
            df[num_cols] = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

            # Ordonnancement chronologique strict & déduplication tick-joueur
            df = df.sort_values(by=["tick", "steamid"]).drop_duplicates(subset=["tick", "steamid"]).reset_index(drop=True)

            self.ticks = df

            # Extraire les joueurs uniques
            joueurs_trouves = sorted(df["steamid"].dropna().unique().tolist())
            self.joueurs = [j for j in joueurs_trouves if j and j != "0" and j != "Player_Unknown"]

            # Extraire équipes représentatives
            for p in self.joueurs:
                p_teams = df[df["steamid"] == p]["team_num"]
                team_val = int(p_teams.mode().iloc[0]) if not p_teams.empty and not p_teams.mode().empty else 0
                self.joueurs_info[p] = {
                    "steamid": p,
                    "name": p,
                    "team": team_val,
                }

        except Exception as e:
            logger.error(f"[CS2CDAdapter] Erreur chargement ticks Parquet {parquet_path}: {e}")
            self.ticks = pd.DataFrame()

    def _charger_evenements(self, json_path: str):
        """Charge et normalise les événements JSON (weapon_fire, player_hurt, player_death)."""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Récupérer métadonnées de match si disponibles
            csstats = data.get("CSstats_info", [])
            if isinstance(csstats, list) and csstats:
                meta = csstats[0]
                self.header["map_name"] = meta.get("map", "unknown")
                self.header["server_name"] = meta.get("server", "CS2CD_Server")

            # 1. Tirs (weapon_fire)
            raw_tirs = data.get("weapon_fire", [])
            if raw_tirs:
                df_tirs = pd.DataFrame(raw_tirs)
                # Normalisation des colonnes de tir pour CS2CD ('user_steamid' -> 'user_name' et 'user_steamid')
                if "user_steamid" in df_tirs.columns:
                    df_tirs["user_name"] = df_tirs["user_steamid"].astype(str)
                    df_tirs["steamid"] = df_tirs["user_steamid"].astype(str)
                elif "user_name" not in df_tirs.columns:
                    df_tirs["user_name"] = "unknown"
                    df_tirs["steamid"] = "unknown"
                if "weapon" not in df_tirs.columns:
                    df_tirs["weapon"] = "weapon_unknown"
                if "tick" in df_tirs.columns:
                    df_tirs["tick"] = pd.to_numeric(df_tirs["tick"], errors="coerce").fillna(0).astype(int)
                    df_tirs = df_tirs.sort_values(by="tick").reset_index(drop=True)
                self.tirs = df_tirs

            # 2. Dégâts (player_hurt)
            raw_hurt = data.get("player_hurt", [])
            if raw_hurt:
                df_hurt = pd.DataFrame(raw_hurt)
                if "attacker_steamid" in df_hurt.columns:
                    df_hurt["attacker_name"] = df_hurt["attacker_steamid"].astype(str)
                if "user_steamid" in df_hurt.columns:
                    df_hurt["user_name"] = df_hurt["user_steamid"].astype(str)
                if "tick" in df_hurt.columns:
                    df_hurt["tick"] = pd.to_numeric(df_hurt["tick"], errors="coerce").fillna(0).astype(int)
                    df_hurt = df_hurt.sort_values(by="tick").reset_index(drop=True)
                self.touches = df_hurt

            # 3. Morts (player_death)
            raw_death = data.get("player_death", [])
            if raw_death:
                df_death = pd.DataFrame(raw_death)
                if "attacker_steamid" in df_death.columns:
                    df_death["attacker_name"] = df_death["attacker_steamid"].astype(str)
                if "user_steamid" in df_death.columns:
                    df_death["user_name"] = df_death["user_steamid"].astype(str)
                if "tick" in df_death.columns:
                    df_death["tick"] = pd.to_numeric(df_death["tick"], errors="coerce").fillna(0).astype(int)
                    df_death = df_death.sort_values(by="tick").reset_index(drop=True)
                self.morts = df_death

        except Exception as e:
            logger.error(f"[CS2CDAdapter] Erreur chargement événements JSON {json_path}: {e}")

    # === API Compatible DemoData (Français) ===

    def obtenir_donnees_joueur(self, nom_joueur: str) -> pd.DataFrame:
        """Retourne les ticks vivants d'un joueur triés chronologiquement."""
        return self.get_player_ticks(nom_joueur)

    def obtenir_tirs_joueur(self, nom_joueur: str) -> pd.DataFrame:
        """Retourne les événements de tir d'un joueur."""
        return self.get_player_events(nom_joueur, "weapon_fire")

    def obtenir_steamid(self, nom_joueur: str) -> str:
        return self.joueurs_info.get(str(nom_joueur), {}).get("steamid", str(nom_joueur))

    def obtenir_equipe(self, nom_joueur: str) -> int:
        return self.joueurs_info.get(str(nom_joueur), {}).get("team", 0)

    # === API Compatible DemoData (Anglais & Mocks) ===

    @property
    def is_valid(self) -> bool:
        return self.valide

    @property
    def demo_path(self) -> str:
        return self.chemin_demo

    @property
    def map_name(self) -> str:
        return self.header.get("map_name") or "unknown"

    @property
    def server_name(self) -> str:
        return self.header.get("server_name") or "CS2CD_Server"

    @property
    def total_ticks(self) -> int:
        if not self.ticks.empty and "tick" in self.ticks.columns:
            return int(self.ticks["tick"].max() - self.ticks["tick"].min() + 1)
        return 0

    @property
    def duration_seconds(self) -> float:
        return float(self.total_ticks / 64.0) if self.total_ticks > 0 else 0.0

    @property
    def players(self) -> List[str]:
        return self.joueurs

    @property
    def players_info(self) -> List[Dict[str, Any]]:
        return [
            {"steamid": info.get("steamid", p), "name": p, "team_number": info.get("team", 0)}
            for p, info in self.joueurs_info.items()
        ]

    def get_player_ticks(self, player_identifier: Any) -> pd.DataFrame:
        """Filtre les ticks vivants pour un identifiant de joueur (steamid ou name)."""
        target = str(player_identifier).strip()
        if self.ticks.empty:
            return pd.DataFrame()

        mask = (self.ticks["steamid"] == target) | (self.ticks["name"] == target)
        df_p = self.ticks[mask]

        if df_p.empty:
            return pd.DataFrame()

        # Filtrer health > 0
        df_alive = df_p[df_p["health"] > 0].copy()
        if df_alive.empty:
            df_alive = df_p.copy()

        return df_alive.sort_values(by="tick").reset_index(drop=True)

    def get_player_events(self, player_identifier: Any, event_name: str = "weapon_fire") -> pd.DataFrame:
        """Retourne les événements associés à un joueur."""
        mapping = {
            "weapon_fire": self.tirs,
            "player_hurt": self.touches,
            "player_death": self.morts,
        }
        df = mapping.get(event_name, pd.DataFrame())
        if df.empty:
            return pd.DataFrame()

        target = str(player_identifier).strip()
        search_cols = ["user_steamid", "attacker_steamid", "user_name", "attacker_name", "steamid"]
        avail_cols = [c for c in search_cols if c in df.columns]

        if not avail_cols:
            return pd.DataFrame()

        mask = pd.Series(False, index=df.index)
        for c in avail_cols:
            mask = mask | (df[c].astype(str) == target)

        return df[mask].sort_values(by="tick").reset_index(drop=True)
