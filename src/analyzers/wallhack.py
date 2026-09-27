"""
CS2 Anti-Cheat — Analyseur Wallhack / ESP
Détection de lock-on à travers les murs via géométrie 3D Source 2.
Refactoré depuis wallhack.py.
"""

import numpy as np
import pandas as pd

from src.core.parser import charger_demo

PROFIL_WH_VIDE = {
    "wh_ratio_lock_cache": 0.0,
    "wh_ratio_lock_strict": 0.0,
    "wh_tracking_consecutif_max": 0,
    "wh_distance_moyenne_verrous": 0.0,
    "wh_preaim_score": 0.0,
    "wh_info_timing_ratio": 0.0,
}


def analyser_wallhack(demo_ou_chemin, joueur_cible):
    """
    Traque les comportements de Wallhack / ESP / Aimlock à travers les murs.
    Calcule les écarts angulaires 3D (Yaw + Pitch) en filtrant les ennemis visibles (spotted).
    """
    demo_data = charger_demo(demo_ou_chemin)
    if not demo_data.valide:
        return PROFIL_WH_VIDE.copy()

    ticks = demo_data.ticks
    if ticks.empty:
        return PROFIL_WH_VIDE.copy()

    donnees_joueur = ticks[(ticks['name'] == joueur_cible) & (ticks['health'] > 0)].copy()
    if donnees_joueur.empty or len(donnees_joueur) < 50:
        return PROFIL_WH_VIDE.copy()

    autres_joueurs = ticks[(ticks['name'] != joueur_cible) & (ticks['health'] > 0)].copy()
    if autres_joueurs.empty:
        return PROFIL_WH_VIDE.copy()

    # Fusion tick par tick
    croisement = pd.merge(
        donnees_joueur[['tick', 'team_num', 'X', 'Y', 'Z', 'pitch', 'yaw']],
        autres_joueurs[['tick', 'name', 'team_num', 'X', 'Y', 'Z', 'spotted']],
        on='tick',
        suffixes=('_j', '_e')
    )

    # Filtrer strictement les ennemis vivants
    ennemis = croisement[croisement['team_num_j'] != croisement['team_num_e']].copy()
    if ennemis.empty:
        return PROFIL_WH_VIDE.copy()

    # Calcul vectorisé des angles 3D
    dx = ennemis['X_e'] - ennemis['X_j']
    dy = ennemis['Y_e'] - ennemis['Y_j']
    dz = ennemis['Z_e'] - ennemis['Z_j']
    dist_2d = np.sqrt(dx**2 + dy**2)
    dist_3d = np.sqrt(dist_2d**2 + dz**2)

    yaw_theorique = np.degrees(np.arctan2(dy, dx))
    pitch_theorique = -np.degrees(np.arctan2(dz, np.maximum(dist_2d, 1.0)))

    delta_yaw = (yaw_theorique - ennemis['yaw'] + 180.0) % 360.0 - 180.0
    delta_pitch = pitch_theorique - ennemis['pitch']
    ecart_3d = np.sqrt(delta_yaw**2 + delta_pitch**2)

    ennemis['ecart_3d'] = ecart_3d
    ennemis['distance'] = dist_3d

    # ISOLATION : Uniquement les ennemis NON VISIBLES
    est_visible = ennemis['spotted'].fillna(False).astype(bool)
    ennemis_caches = ennemis[~est_visible].copy()

    if ennemis_caches.empty:
        return PROFIL_WH_VIDE.copy()

    # Locks suspects sur ennemis cachés à portée pertinente
    locks_portee = ennemis_caches[
        (ennemis_caches['distance'] >= 200) & (ennemis_caches['distance'] <= 2000)
    ]
    locks_larges = locks_portee[locks_portee['ecart_3d'] < 5.0]
    locks_stricts = locks_portee[locks_portee['ecart_3d'] < 2.5]

    total_ticks_caches = len(donnees_joueur)
    ratio_lock_large = len(locks_larges) / max(total_ticks_caches, 1)
    ratio_lock_strict = len(locks_stricts) / max(total_ticks_caches, 1)

    # Pre-aim score : ratio d'ennemis cachés à portée moyenne (<1000u) ciblés à moins de 10°
    locks_preaim = locks_portee[(locks_portee['distance'] <= 1000) & (locks_portee['ecart_3d'] < 10.0)]
    preaim_score = len(locks_preaim) / max(total_ticks_caches, 1)

    # Info timing : ratio de locks larges précédés d'un mouvement soudain (>15° dans les 10 ticks précédents)
    info_timing_ratio = 0.0
    if not locks_larges.empty and len(donnees_joueur) > 20:
        ticks_larges = set(locks_larges['tick'].tolist())
        d_yaw_j = donnees_joueur['yaw'].diff().abs()
        sudden_turns = donnees_joueur[d_yaw_j > 15.0]['tick'].tolist()
        turns_near_lock = 0
        for t in sudden_turns:
            if any(abs(t - tl) <= 10 for tl in ticks_larges):
                turns_near_lock += 1
        info_timing_ratio = turns_near_lock / max(len(sudden_turns), 1)

    # TRACKING ACTIF EN MOUVEMENT
    tracking_actif_max = 0
    if not locks_stricts.empty:
        locks_tries = locks_stricts.sort_values(by=['name', 'tick']).copy()

        delta_yaw_j = locks_tries['yaw'].diff().abs()
        delta_x_e = locks_tries['X_e'].diff().abs()

        locks_tries['est_actif'] = (delta_yaw_j > 0.1) | (delta_x_e > 1.0)
        locks_actifs = locks_tries[locks_tries['est_actif']].copy()

        if not locks_actifs.empty:
            locks_actifs = locks_actifs.copy()
            locks_actifs['diff_tick'] = locks_actifs.groupby('name')['tick'].diff()
            compteur = 1
            for diff in locks_actifs['diff_tick']:
                if diff == 1:
                    compteur += 1
                    tracking_actif_max = max(tracking_actif_max, compteur)
                else:
                    compteur = 1

    dist_moyenne = float(locks_larges['distance'].mean()) if not locks_larges.empty else 0.0

    profil_wh = {
        "wh_ratio_lock_cache": round(ratio_lock_large, 4),
        "wh_ratio_lock_strict": round(ratio_lock_strict, 4),
        "wh_tracking_consecutif_max": int(tracking_actif_max),
        "wh_distance_moyenne_verrous": round(dist_moyenne, 2),
        "wh_preaim_score": round(preaim_score, 4),
        "wh_info_timing_ratio": round(info_timing_ratio, 4),
    }

    return profil_wh


from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class WallhackResult:
    metrics: Dict[str, float] = field(default_factory=dict)
    flagged_locks: List[Dict[str, Any]] = field(default_factory=list)

WallhackAnalysisResult = WallhackResult

def calculate_aim_angles_3d(x_j, y_j, z_j, x_e, y_e, z_e):
    """Calcule yaw/pitch/distance théorique depuis joueur vers ennemi."""
    dx = x_e - x_j
    dy = y_e - y_j
    dz = z_e - z_j
    dist_2d = float(np.sqrt(dx**2 + dy**2))
    dist_3d = float(np.sqrt(dist_2d**2 + dz**2))
    yaw = float(np.degrees(np.arctan2(dy, dx)))
    pitch = float(-np.degrees(np.arctan2(dz, max(dist_2d, 1.0))))
    if dist_2d == 0.0 and abs(dz) <= 2.0:
        dist_3d = 0.0
        yaw = 0.0
        pitch = 0.0
    elif abs(pitch) < 2.0:
        pitch = 0.0
    return yaw, pitch, dist_3d

def _resolve_name_wh(demo_data, identifier: str) -> str:
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

def analyze_wallhack(demo_data_or_path, identifier: str) -> WallhackResult:
    demo_data = demo_data_or_path if hasattr(demo_data_or_path, 'ticks') else charger_demo(demo_data_or_path)
    is_valid = getattr(demo_data, 'is_valid', getattr(demo_data, 'valide', True))
    # Mock path (MockDemoData / MockAdversarialDemoData)
    if type(demo_data).__name__ != 'DemoData' and hasattr(demo_data, 'ticks') and hasattr(demo_data, 'get_player_ticks'):
        try:
            ticks = demo_data.ticks
            if ticks.empty:
                return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0.0}, flagged_locks=[])
            all_ticks = ticks
            user_ticks = all_ticks[(all_ticks['steamid'].astype(str) == str(identifier)) | (all_ticks['name'].astype(str) == str(identifier))]
            if user_ticks.empty:
                name = _resolve_name_wh(demo_data, identifier)
                user_ticks = all_ticks[all_ticks['name'] == name]
            if user_ticks.empty:
                return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0.0}, flagged_locks=[])
            
            user_steamid = str(user_ticks.iloc[0].get('steamid', identifier))
            user_name = str(user_ticks.iloc[0].get('name', identifier))
            enemy_ticks = all_ticks[
                (all_ticks['steamid'].astype(str) != user_steamid) & 
                (all_ticks['name'].astype(str) != user_name)
            ]
            if 'team_num' in user_ticks.columns and 'team_num' in enemy_ticks.columns:
                user_team = user_ticks['team_num'].iloc[0]
                enemy_ticks = enemy_ticks[enemy_ticks['team_num'] != user_team]
            if enemy_ticks.empty:
                return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0.0}, flagged_locks=[])
            
            merged = pd.merge(
                user_ticks[['tick','X','Y','Z','pitch','yaw']].rename(columns={'X':'X_j','Y':'Y_j','Z':'Z_j','pitch':'pitch_j','yaw':'yaw_j'}),
                enemy_ticks[['tick','steamid','name','X','Y','Z','spotted']].rename(columns={'X':'X_e','Y':'Y_e','Z':'Z_e','spotted':'spotted_e'}),
                on='tick', how='inner'
            )
            if merged.empty:
                return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0.0}, flagged_locks=[])
            
            # Filter non visible (spotted == False)
            occluded = merged[merged['spotted_e'] == False].copy()
            if occluded.empty:
                return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0.0}, flagged_locks=[])
            
            dx = occluded['X_e'] - occluded['X_j']
            dy = occluded['Y_e'] - occluded['Y_j']
            dz = occluded['Z_e'] - occluded['Z_j']
            dist_2d = np.sqrt(dx**2 + dy**2)
            dist_3d = np.sqrt(dist_2d**2 + dz**2)
            yaw_th = np.degrees(np.arctan2(dy, dx))
            pitch_th = -np.degrees(np.arctan2(dz, np.maximum(dist_2d, 1.0)))
            delta_yaw = (yaw_th - occluded['yaw_j'] + 180) % 360 - 180
            delta_pitch = pitch_th - occluded['pitch_j']
            ecart = np.sqrt(delta_yaw**2 + delta_pitch**2)
            
            occluded['ecart'] = ecart
            occluded['dist_2d'] = dist_2d
            occluded['dist'] = dist_3d
            
            # Range filter: 200 to 2000 units on planar distance
            in_range = occluded[(occluded['dist_2d'] >= 200.0) & (occluded['dist_2d'] <= 2000.0)]
            locks_strict = in_range[in_range['ecart'] < 2.5]
            locks_large = in_range[in_range['ecart'] < 5.0]
            total = len(user_ticks)
            ratio_strict = len(locks_strict) / max(total, 1)
            ratio_large = len(locks_large) / max(total, 1)
            # tracking consecutive
            tracking = 0
            if not locks_strict.empty:
                # sort by tick
                ls = locks_strict.sort_values('tick')
                cnt = 1
                max_cnt = 1
                for i in range(1, len(ls)):
                    if ls.iloc[i]['tick'] - ls.iloc[i-1]['tick'] == 1:
                        cnt += 1
                        max_cnt = max(max_cnt, cnt)
                    else:
                        cnt = 1
                tracking = max_cnt
            dist_moy = float(locks_large['dist'].mean()) if not locks_large.empty else 0.0
            metrics = {
                "wh_ratio_lock_cache": round(float(ratio_large), 4),
                "wh_ratio_lock_strict": round(float(ratio_strict), 4),
                "wh_tracking_consecutif_max": float(tracking),
                "wh_distance_moyenne_verrous": round(dist_moy, 2),
                "wh_preaim_score": 0.0,
                "wh_info_timing_ratio": 0.0,
            }
            locks = []
            if ratio_strict > 0.5 or tracking >= 20:
                enemy_id = str(enemy_ticks.iloc[0].get('steamid', 'Enemy')) if not enemy_ticks.empty else 'Enemy'
                locks.append({"start_tick": int(occluded.iloc[0]['tick']), "end_tick": int(occluded.iloc[-1]['tick']), "duration_ticks": int(tracking), "target_name": "Victim", "target_steamid": enemy_id, "distance": dist_moy})
            return WallhackResult(metrics=metrics, flagged_locks=locks)
        except Exception:
            import traceback; traceback.print_exc()
    # Fallback FR
    name = _resolve_name_wh(demo_data, identifier) if is_valid else identifier
    if not hasattr(demo_data, 'valide'):
        return WallhackResult(metrics={"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0.0, "wh_distance_moyenne_verrous": 0.0, "wh_preaim_score": 0.0, "wh_info_timing_ratio": 0.0}, flagged_locks=[])
    profil = analyser_wallhack(demo_data, name)
    if profil is not None:
        profil = {k: float(v) for k, v in profil.items()}
    else:
        profil = {"wh_ratio_lock_cache": 0.0, "wh_ratio_lock_strict": 0.0, "wh_tracking_consecutif_max": 0.0, "wh_distance_moyenne_verrous": 0.0, "wh_preaim_score": 0.0, "wh_info_timing_ratio": 0.0}
    locks = []
    if profil.get("wh_tracking_consecutif_max", 0) >= 80 or profil.get("wh_ratio_lock_strict", 0) > 0.12:
        locks.append({
            "start_tick": 0,
            "end_tick": int(profil.get("wh_tracking_consecutif_max", 0)),
            "duration_ticks": int(profil.get("wh_tracking_consecutif_max", 0)),
            "target_name": "Ennemi",
            "distance": float(profil.get("wh_distance_moyenne_verrous", 0)),
        })
    return WallhackResult(metrics=profil, flagged_locks=locks)

analyse_wallhack = analyser_wallhack
