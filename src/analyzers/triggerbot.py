"""
CS2 Anti-Cheat — Analyseur Triggerbot
Détection d'anomalies statistiques de temps de réaction entre l'alignement du viseur et le tir.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.core.parser import charger_demo


@dataclass
class TriggerbotResult:
    metrics: Dict[str, float] = field(default_factory=dict)
    flagged_events: List[Dict[str, Any]] = field(default_factory=list)

TriggerbotAnalysisResult = TriggerbotResult

PROFIL_TB_VIDE = {
    "triggerbot_rt_median": 0.0,
    "triggerbot_rt_std": 0.0,
    "triggerbot_rt_min": 0.0,
    "triggerbot_burst_count": 0,
    "triggerbot_total_shots_analyzed": 0,
}

def _resolve_name_triggerbot(demo_data, identifier: str) -> str:
    try:
        if hasattr(demo_data, 'joueurs') and identifier in getattr(demo_data, 'joueurs', []):
            return identifier
        if hasattr(demo_data, 'players') and identifier in getattr(demo_data, 'players', []):
            return identifier
        infos = getattr(demo_data, 'joueurs_info', None) or getattr(demo_data, 'players_info', None)
        if isinstance(infos, dict):
            for nom, info in infos.items():
                if str(info.get("steamid")) == str(identifier):
                    return nom
        if isinstance(infos, list):
            for p in infos:
                if str(p.get("steamid")) == str(identifier):
                    return p.get("name", identifier)
    except Exception as _e:
            import logging
            logging.debug(f"Ignored error: {_e}")
    return identifier

def _get_player_ticks_triggerbot(demo_data, identifier: str):
    ticks = demo_data.ticks
    user_ticks = ticks[(ticks['steamid'].astype(str) == str(identifier)) | (ticks['name'].astype(str) == str(identifier))]
    if user_ticks.empty:
        name = _resolve_name_triggerbot(demo_data, identifier)
        user_ticks = ticks[ticks['name'] == name]
    return user_ticks

def _check_intersection(xj, yj, zj, yaw, pitch, xe, ye, ze, radius=16.0):
    # Sphere center is head (ze + 64 as approximation if ze is feet, but we will just use ze + 64)
    # We will assume ze is feet, so head is ze + 64. If ze is already center, it's fine.
    cx, cy, cz = xe, ye, ze + 64.0
    
    # Direction vector from player (xj, yj, zj + 64 for eye position)
    ex, ey, ez = xj, yj, zj + 64.0
    
    yaw_rad = np.radians(yaw)
    pitch_rad = np.radians(pitch)
    
    dx = np.cos(pitch_rad) * np.cos(yaw_rad)
    dy = np.cos(pitch_rad) * np.sin(yaw_rad)
    dz = -np.sin(pitch_rad)
    
    # Vector from eye to center of sphere
    vx = cx - ex
    vy = cy - ey
    vz = cz - ez
    
    # Projection of v onto d
    t = vx * dx + vy * dy + vz * dz
    if t < 0:
        return False
        
    # Closest point on line
    px = ex + t * dx
    py = ey + t * dy
    pz = ez + t * dz
    
    # Distance from closest point to sphere center
    dist = np.sqrt((px - cx)**2 + (py - cy)**2 + (pz - cz)**2)
    return dist <= radius

def _get_weapon_fires(demo_data, user_name):
    fires = []
    # Utilize the correct interface for weapon_fire events (Correction AUD-02)
    if hasattr(demo_data, 'get_player_events'):
        tirs_df = demo_data.get_player_events(user_name, "weapon_fire")
        if not tirs_df.empty and 'tick' in tirs_df.columns:
            fires = tirs_df['tick'].tolist()
    elif hasattr(demo_data, 'tirs'):
        tirs_df = demo_data.tirs
        if not tirs_df.empty:
            cols_name = [c for c in ["user_name", "attacker_name", "name"] if c in tirs_df.columns]
            for c in cols_name:
                user_fires = tirs_df[tirs_df[c] == user_name]
                if not user_fires.empty and 'tick' in user_fires.columns:
                    fires.extend(user_fires['tick'].tolist())

    if fires:
        return sorted(list(set(fires)))

    if hasattr(demo_data, 'events'):
        events = demo_data.events
        if not events.empty and 'event_name' in events.columns:
            user_fires = events[(events['event_name'] == 'weapon_fire') & (events['user_name'] == user_name)]
            if not user_fires.empty:
                fires = user_fires['tick'].tolist()
    
    if not fires and hasattr(demo_data, 'weapon_fires'):
        wf = demo_data.weapon_fires
        user_fires = wf[wf['user_name'] == user_name]
        if not user_fires.empty:
            fires = user_fires['tick'].tolist()
            
    # Fallback to is_firing in ticks if available
    if not fires and hasattr(demo_data, 'ticks') and 'is_firing' in demo_data.ticks.columns:
        ticks = demo_data.ticks
        user_ticks = ticks[ticks['name'] == user_name]
        firing_ticks = user_ticks[user_ticks['is_firing'] == True]
        
        # Get only the first tick of each burst
        if not firing_ticks.empty:
            diffs = firing_ticks['tick'].diff()
            starts = firing_ticks[diffs > 1]['tick'].tolist()
            if not starts and not firing_ticks.empty:
                starts = [firing_ticks.iloc[0]['tick']]
            fires = starts

    return sorted(list(set(fires)))

def analyser_triggerbot(demo_ou_chemin, joueur_cible):
    """
    Détecte les temps de réaction inhumains caractéristiques d'un triggerbot.
    """
    demo_data = charger_demo(demo_ou_chemin) if not hasattr(demo_ou_chemin, 'ticks') else demo_ou_chemin
    if not getattr(demo_data, 'valide', True) and not getattr(demo_data, 'is_valid', True):
        return PROFIL_TB_VIDE.copy()

    ticks = getattr(demo_data, 'ticks', pd.DataFrame())
    if ticks.empty:
        return PROFIL_TB_VIDE.copy()

    nom_joueur = _resolve_name_triggerbot(demo_data, joueur_cible)
    donnees_joueur = ticks[(ticks['name'] == nom_joueur) & (ticks['health'] > 0)]
    if donnees_joueur.empty:
        return PROFIL_TB_VIDE.copy()

    tirs = _get_weapon_fires(demo_data, nom_joueur)
    if not tirs:
        return PROFIL_TB_VIDE.copy()

    autres_joueurs = ticks[(ticks['name'] != nom_joueur) & (ticks['health'] > 0)]
    if autres_joueurs.empty:
        return PROFIL_TB_VIDE.copy()

    reaction_times = []
    
    team_j = donnees_joueur.iloc[0]['team_num'] if 'team_num' in donnees_joueur.columns else None

    for tir_tick in tirs:
        # Trouver les ennemis vivants à ce tick
        ennemis_tick = autres_joueurs[autres_joueurs['tick'] == tir_tick]
        if team_j is not None and 'team_num' in ennemis_tick.columns:
            ennemis_tick = ennemis_tick[ennemis_tick['team_num'] != team_j]
            
        if ennemis_tick.empty:
            continue
            
        etat_joueur = donnees_joueur[donnees_joueur['tick'] == tir_tick]
        if etat_joueur.empty:
            continue
            
        j_row = etat_joueur.iloc[0]
        xj, yj, zj = j_row['X'], j_row['Y'], j_row['Z']
        yaw, pitch = j_row['yaw'], j_row['pitch']
        
        cible_touchee = None
        for _, e_row in ennemis_tick.iterrows():
            xe, ye, ze = e_row['X'], e_row['Y'], e_row['Z']
            if _check_intersection(xj, yj, zj, yaw, pitch, xe, ye, ze, radius=16.0):
                cible_touchee = e_row
                break
                
        if cible_touchee is not None:
            # Look backwards in time to find first tick of alignment
            # Limite à 64 ticks (1 sec)
            historique = donnees_joueur[(donnees_joueur['tick'] <= tir_tick) & (donnees_joueur['tick'] > tir_tick - 64)].sort_values('tick', ascending=False)
            historique_ennemis = autres_joueurs[(autres_joueurs['name'] == cible_touchee['name']) & (autres_joueurs['tick'] <= tir_tick) & (autres_joueurs['tick'] > tir_tick - 64)]
            
            historique_idx = historique.set_index('tick')
            historique_ennemis_idx = historique_ennemis.set_index('tick')
            
            first_aligned_tick = tir_tick
            for t_hist in historique['tick']:
                if t_hist not in historique_idx.index or t_hist not in historique_ennemis_idx.index:
                    break
                    
                hj_row = historique_idx.loc[t_hist]
                he_row = historique_ennemis_idx.loc[t_hist]
                
                if isinstance(hj_row, pd.DataFrame): hj_row = hj_row.iloc[0]
                if isinstance(he_row, pd.DataFrame): he_row = he_row.iloc[0]
                
                if _check_intersection(hj_row['X'], hj_row['Y'], hj_row['Z'], hj_row['yaw'], hj_row['pitch'], he_row['X'], he_row['Y'], he_row['Z'], radius=16.0):
                    first_aligned_tick = t_hist
                else:
                    break
                    
            tickrate = float(getattr(demo_data, 'tickrate', 64.0) or 64.0)
            tick_delta = tir_tick - first_aligned_tick
            rt_ms = (tick_delta / tickrate) * 1000.0
            reaction_times.append(rt_ms)
            
    if not reaction_times:
        return PROFIL_TB_VIDE.copy()
        
    rt_array = np.array(reaction_times)
    median_rt = float(np.median(rt_array))
    std_rt = float(np.std(rt_array)) if len(rt_array) > 1 else 0.0
    min_rt = float(np.min(rt_array))
    
    # Burst sequences (3+ shots where RT < 30ms)
    burst_count = 0
    consecutive = 0
    for rt in reaction_times:
        if rt < 30.0:
            consecutive += 1
            if consecutive == 3:
                burst_count += 1
        else:
            consecutive = 0
            
    metrics = {
        "triggerbot_rt_median": round(median_rt, 2),
        "triggerbot_rt_std": round(std_rt, 2),
        "triggerbot_rt_min": round(min_rt, 2),
        "triggerbot_burst_count": burst_count,
        "triggerbot_total_shots_analyzed": len(reaction_times),
    }
    
    return metrics

def analyze_triggerbot(demo_data_or_path, identifier: str) -> TriggerbotResult:
    demo_data = demo_data_or_path if hasattr(demo_data_or_path, 'ticks') else charger_demo(demo_data_or_path)
    
    metrics = analyser_triggerbot(demo_data, identifier)
    
    flagged = []
    
    if metrics.get("triggerbot_total_shots_analyzed", 0) > 0:
        if metrics["triggerbot_rt_median"] < 50.0:
            flagged.append({"reason": "Anomalously fast median reaction time", "value": metrics["triggerbot_rt_median"]})
        if metrics["triggerbot_total_shots_analyzed"] >= 3 and metrics["triggerbot_rt_std"] < 15.0:
            flagged.append({"reason": "Statistically improbable consistency (std dev)", "value": metrics["triggerbot_rt_std"]})
        if metrics["triggerbot_burst_count"] > 0:
            flagged.append({"reason": "Sub-tick burst reaction pattern detected", "value": metrics["triggerbot_burst_count"]})
            
    return TriggerbotResult(metrics=metrics, flagged_events=flagged)
