import json
import pandas as pd
from src.core.parser import DemoData

class CS2CDAdapter:
    """
    Adapter to mimic DemoData for the existing analyzers using CS2CD Parquet & JSON files.
    """
    def __init__(self, parquet_path, json_path):
        self.valide = True
        self.chemin_demo = parquet_path
        self.header = {}
        
        import pyarrow.parquet as pq
        
        required_cols = ['tick', 'steamid', 'team_num', 'X', 'Y', 'Z', 'pitch', 'yaw', 'health', 'spotted', 'velocity_X', 'velocity_Y', 'velocity_Z', 'is_alive', 'active_weapon_name', 'shots_fired', 'is_airborne']
        schema = pq.read_schema(parquet_path)
        cols_to_read = [c for c in required_cols if c in schema.names]
        
        # Load only necessary ticks
        self.ticks = pd.read_parquet(parquet_path, columns=cols_to_read)
        
        # Ensure all required columns exist
        for c in required_cols:
            if c not in self.ticks.columns:
                self.ticks[c] = 0.0 if c != 'active_weapon_name' else 'unknown'
        
        # Load JSON events
        with open(json_path, 'r', encoding='utf-8') as f:
            j = json.load(f)
            
        # Parse weapon fires
        tirs_list = j.get('weapon_fire', [])
        # weapon_fire event might have user_name or similar. Let's see. 
        # Typically CS2CD JSON has 'user_name' or just 'steamid'.
        # We need to map it to what the analyzers expect: user_name / user_steamid.
        self.tirs = pd.DataFrame(tirs_list)
        if not self.tirs.empty:
            if 'steamid' in self.tirs.columns:
                self.tirs['user_name'] = self.tirs['steamid']
            elif 'user_name' not in self.tirs.columns:
                self.tirs['user_name'] = "unknown"
                
        # Others
        self.touches = pd.DataFrame(j.get('player_hurt', []))
        self.morts = pd.DataFrame(j.get('player_death', []))
        
        # Determine players (CS2CD uses steamid like 'Player_8')
        if 'steamid' in self.ticks.columns:
            self.ticks['name'] = self.ticks['steamid']
            self.joueurs = self.ticks['steamid'].dropna().unique().tolist()
        else:
            self.joueurs = []
            
        self.joueurs_info = {p: {"steamid": p, "team": 0} for p in self.joueurs}

        # Setup teams
        if 'team_num' in self.ticks.columns:
            for p in self.joueurs:
                teams = self.ticks[self.ticks['steamid'] == p]['team_num'].dropna()
                if not teams.empty:
                    self.joueurs_info[p]["team"] = int(teams.mode().iloc[0])

    def get_player_ticks(self, player_identifier):
        if self.ticks.empty:
            return self.ticks
        mask = (self.ticks.get("steamid", pd.Series(dtype=str)).astype(str) == str(player_identifier))
        df = self.ticks[mask].copy()
        
        # Drop complex list columns that crash pandas .replace(np.inf)
        for col in ['inventory', 'usercmd_input_history', 'inventory_as_ids', 'approximate_spotted_by']:
            if col in df.columns:
                df = df.drop(columns=[col])
                
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
        
        cols = [c for c in ["user_name", "steamid", "attacker_steamid"] if c in df.columns]
        if not cols:
            return pd.DataFrame()
            
        mask = df[cols[0]].astype(str) == str(player_identifier)
        for c in cols[1:]:
            mask = mask | (df[c].astype(str) == str(player_identifier))
            
        return df[mask].reset_index(drop=True)
    
    def obtenir_donnees_joueur(self, nom_joueur):
        return self.get_player_ticks(nom_joueur)
        
    def obtenir_tirs_joueur(self, nom_joueur):
        return self.get_player_events(nom_joueur, "weapon_fire")
