"""
CS2 Anti-Cheat — Demo Parser
Wrapper robuste pour demoparser2 avec extraction des SteamID64 et des données de jeu.
"""

import os

import pandas as pd
from demoparser2 import DemoParser

REQUIRED_TICK_PROPERTIES = [
    'X', 'Y', 'Z',
    'pitch', 'yaw',
    'health', 'team_num',
    'is_airborne', 'spotted',
    'velocity_X', 'velocity_Y', 'velocity_Z',
    'steamid', 'name',
]


class DemoData:
    """Conteneur des données d'une démo CS2 parsée en une passe unique."""

    def __init__(self, chemin_demo):
        self.chemin_demo = chemin_demo
        self.valide = False
        self.header = {}
        self.ticks = pd.DataFrame()
        self.tirs = pd.DataFrame()
        self.touches = pd.DataFrame()
        self.morts = pd.DataFrame()
        self.joueurs = []
        self.joueurs_info = {}  # {nom: {"steamid": str, "team": int}}
        self._charger()

    def _charger(self):
        if not os.path.exists(self.chemin_demo):
            return

        parser = DemoParser(self.chemin_demo)

        try:
            self.header = parser.parse_header()
        except Exception:
            self.header = {}

        try:
            champs_ticks = [
                'X', 'Y', 'Z',
                'pitch', 'yaw',
                'health', 'team_num',
                'is_airborne', 'spotted',
                'velocity_X', 'velocity_Y', 'velocity_Z',
                'steamid',
            ]
            self.ticks = parser.parse_ticks(champs_ticks)
        except Exception:
            # Fallback sans steamid si le champ n'est pas supporté
            try:
                champs_ticks_fallback = [
                    'X', 'Y', 'Z',
                    'pitch', 'yaw',
                    'health', 'team_num',
                    'is_airborne', 'spotted',
                    'velocity_X', 'velocity_Y', 'velocity_Z',
                ]
                self.ticks = parser.parse_ticks(champs_ticks_fallback)
            except Exception:
                return

        try:
            tirs = parser.parse_event("weapon_fire")
            self.tirs = pd.DataFrame(tirs) if tirs is not None and len(tirs) > 0 else pd.DataFrame()
        except Exception:
            self.tirs = pd.DataFrame()

        try:
            touches = parser.parse_event("player_hurt")
            self.touches = pd.DataFrame(touches) if touches is not None and len(touches) > 0 else pd.DataFrame()
        except Exception:
            self.touches = pd.DataFrame()

        try:
            morts = parser.parse_event("player_death")
            self.morts = pd.DataFrame(morts) if morts is not None and len(morts) > 0 else pd.DataFrame()
        except Exception:
            self.morts = pd.DataFrame()

        # Tentative d'extraction player_info via demoparser2 direct (plus fiable pour SteamID)
        try:
            df_players = parser.parse_player_info()
            if df_players is not None and not df_players.empty:
                # Eviter la perte de précision float64 lors de iterrows()
                if 'steamid' in df_players.columns:
                    df_players['steamid'] = df_players['steamid'].astype(str)
                    
                # construire map name->steamid/team
                for _, row in df_players.iterrows():
                    try:
                        name = str(row.get("name", "")).strip()
                        steamid = str(row.get("steamid", "0")).strip()
                        team = int(row.get("team_number", 0)) if row.get("team_number") is not None else 0
                        if name and name != "None":
                            # Normaliser steamid
                            if steamid and steamid != "0" and steamid != "nan":
                                steamid = steamid.removesuffix(".0")
                                if len(steamid) >= 5:
                                    self.joueurs_info[name] = {"steamid": steamid, "team": team}
                                    if name not in self.joueurs:
                                        self.joueurs.append(name)
                    except Exception:
                        continue
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        if not self.ticks.empty and 'name' in self.ticks.columns:
            joueurs_bruts = self.ticks['name'].dropna().unique()
            for j in joueurs_bruts:
                name = str(j).strip()
                if name and name != 'None' and name not in self.joueurs:
                    self.joueurs.append(name)
            self.valide = len(self.joueurs) > 0

            # Extraction des SteamID64 et équipe pour chaque joueur (complément ticks)
            self._extraire_infos_joueurs()
            # Fallback: si info manquante, garantir entrée
            for n in self.joueurs:
                if n not in self.joueurs_info:
                    self.joueurs_info[n] = {"steamid": "0", "team": 0}

            # Full resolution is required for tick-sensitive analyzers (aimbot, bhop, etc)
            # Sous-échantillonnage supprimé (Correction AUD-01)

    def _extraire_infos_joueurs(self):
        """Extrait SteamID64 et équipe pour chaque joueur."""
        for nom in self.joueurs:
            info = {"steamid": "0", "team": 0}
            joueur_df = self.ticks[self.ticks['name'] == nom]

            if 'steamid' in joueur_df.columns:
                # Convertir en str avant toute opération pour éviter la conversion implicite en float64
                steamids = joueur_df['steamid'].dropna().astype(str).unique()
                for sid_str in steamids:
                    sid_str = sid_str.removesuffix(".0")
                    if sid_str and sid_str != '0' and sid_str != 'nan' and len(sid_str) > 5:
                        info["steamid"] = sid_str
                        break

            if 'team_num' in joueur_df.columns:
                teams = joueur_df['team_num'].dropna()
                if not teams.empty:
                    # L'équipe la plus fréquente (2=CT, 3=T)
                    info["team"] = int(teams.mode().iloc[0]) if not teams.mode().empty else 0

            self.joueurs_info[nom] = info

    def obtenir_donnees_joueur(self, nom_joueur):
        """Retourne les ticks vivants d'un joueur triés par tick."""
        if self.ticks.empty or 'name' not in self.ticks.columns:
            return pd.DataFrame()

        df = self.ticks[(self.ticks['name'] == nom_joueur) & (self.ticks['health'] > 0)].copy()
        if not df.empty:
            df = df.sort_values(by='tick').reset_index(drop=True)
        return df

    def obtenir_tirs_joueur(self, nom_joueur):
        """Retourne les événements de tir d'un joueur."""
        if self.tirs.empty or 'user_name' not in self.tirs.columns:
            return pd.DataFrame()
        return self.tirs[self.tirs['user_name'] == nom_joueur].copy()

    def obtenir_steamid(self, nom_joueur):
        """Retourne le SteamID64 d'un joueur."""
        return self.joueurs_info.get(nom_joueur, {}).get("steamid", "0")

    def obtenir_equipe(self, nom_joueur):
        """Retourne l'équipe d'un joueur (2=CT, 3=T)."""
        return self.joueurs_info.get(nom_joueur, {}).get("team", 0)

    # === Compatibilité API Anglaise (engine + tests EN) ===
    @property
    def is_valid(self) -> bool:
        return self.valide

    @property
    def demo_path(self) -> str:
        return self.chemin_demo

    @property
    def map_name(self) -> str:
        return self.header.get("map_name") or ""

    @property
    def server_name(self) -> str:
        return self.header.get("server_name") or ""

    @property
    def total_ticks(self) -> int:
        if not self.ticks.empty and "tick" in self.ticks.columns:
            try:
                return int(self.ticks["tick"].max() - self.ticks["tick"].min() + 1)
            except Exception:
                return len(self.ticks)
        return len(self.ticks)

    @property
    def duration_seconds(self) -> float:
        # Header playback_time si dispo, sinon estimation tickrate 64
        try:
            pt = self.header.get("playback_time")
            if pt and float(pt) > 0:
                return float(pt)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
        return float(self.total_ticks / 64.0) if self.total_ticks else 0.0

    @property
    def players(self) -> list:
        return self.joueurs

    @players.setter
    def players(self, value):
        self.joueurs = value

    @property
    def players_info(self):
        # EN alias: list of dicts {steamid, name, team_number}
        return self.get_all_players()

    @players_info.setter
    def players_info(self, value):
        # allow test mock style assignment
        if isinstance(value, list):
            self.joueurs = [p.get("name", "") for p in value if p.get("name")]
            self.joueurs_info = {p.get("name", ""): {"steamid": p.get("steamid", "0"), "team": p.get("team_number", 0)} for p in value if p.get("name")}

    def get_all_players(self):
        """Retourne liste dicts {steamid, name, team_number} pour engine EN."""
        result = []
        for nom in self.joueurs:
            info = self.joueurs_info.get(nom, {})
            result.append({
                "steamid": info.get("steamid", "0"),
                "name": nom,
                "team_number": info.get("team", 0),
            })
        return result

    # English tick/event helpers for MockDemoData compatibility
    def get_player_ticks(self, player_identifier):
        target = str(player_identifier).strip()
        if self.ticks.empty:
            return self.ticks
        mask = (self.ticks.get("steamid", pd.Series(dtype=str)).astype(str) == target) | (self.ticks.get("name", pd.Series(dtype=str)).astype(str) == target)
        df = self.ticks[mask].copy()
        if "health" in df.columns:
            df = df[df["health"] > 0].copy()
        if not df.empty and "tick" in df.columns:
            df = df.sort_values("tick").reset_index(drop=True)
        return df

    def get_player_events(self, player_identifier, event_name="weapon_fire"):
        mapping = {"weapon_fire": self.tirs, "player_hurt": self.touches, "player_death": self.morts}
        df = mapping.get(event_name, pd.DataFrame())
        if df.empty:
            return pd.DataFrame()
        target = str(player_identifier).strip()
        # Try multiple column names
        cols_steam = [c for c in ["user_steamid", "attacker_steamid", "steamid"] if c in df.columns]
        cols_name = [c for c in ["user_name", "attacker_name", "name"] if c in df.columns]
        mask = pd.Series([False]*len(df))
        for c in cols_steam:
            mask = mask | (df[c].astype(str) == target)
        for c in cols_name:
            mask = mask | (df[c].astype(str) == target)
        return df[mask].reset_index(drop=True)


def charger_demo(chemin_demo_ou_obj):
    """Accepte soit un chemin de fichier soit déjà une instance DemoData ou mock."""
    if isinstance(chemin_demo_ou_obj, DemoData) or hasattr(chemin_demo_ou_obj, 'ticks') or hasattr(chemin_demo_ou_obj, 'valide'):
        return chemin_demo_ou_obj
    return DemoData(chemin_demo_ou_obj)


# Alias anglais pour compatibilité engine/tests
load_demo = charger_demo
