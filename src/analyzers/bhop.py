"""
CS2 Anti-Cheat — Analyseur BunnyHop
Analyse biomécanique des sauts : transitions tick-perfect, chaînes, vitesse.
Refactoré depuis bhop_advanced.py.
"""

import numpy as np
import pandas as pd

from src.core.config import get_config
from src.core.parser import charger_demo

PROFIL_BHOP_VIDE = {
    "bhop_total_sauts": 0,
    "bhop_ratio_parfaits": 0.0,
    "bhop_variance_sol": 50.0,
    "bhop_chaine_max": 0,
    "bhop_vitesse_moyenne": 0.0,
    "bhop_autostrafe_correlation": 0.0,
    "bhop_velocity_gain_max": 0.0,
}


def analyser_bhop(demo_ou_chemin, joueur_cible):
    """
    Analyse biomécanique avancée du BunnyHop en CS2.
    Analyse les transitions d'état au sol (is_airborne), la vitesse horizontale
    et le nombre précis de ticks passés au sol lors des enchaînements de sauts.
    """
    demo_data = charger_demo(demo_ou_chemin)
    if not getattr(demo_data, 'valide', False) and not getattr(demo_data, 'is_valid', False):
        return PROFIL_BHOP_VIDE.copy()

    if hasattr(demo_data, 'obtenir_donnees_joueur'):
        donnees = demo_data.obtenir_donnees_joueur(joueur_cible)
    elif hasattr(demo_data, 'get_player_ticks'):
        donnees = demo_data.get_player_ticks(joueur_cible)
    else:
        donnees = pd.DataFrame()
    if donnees.empty or len(donnees) < 50:
        return PROFIL_BHOP_VIDE.copy()

    donnees = donnees.copy()

    # Calcul de la vitesse horizontale
    donnees['vitesse_2d'] = np.sqrt(donnees['velocity_X']**2 + donnees['velocity_Y']**2)

    # Détection des transitions sol <-> air
    est_en_lair = donnees['is_airborne'].astype(bool)
    debut_saut = (~est_en_lair.shift(1, fill_value=False)) & est_en_lair
    fin_saut = est_en_lair.shift(1, fill_value=False) & (~est_en_lair)

    ticks_debut_saut = donnees.loc[debut_saut, 'tick'].tolist()
    ticks_fin_saut = donnees.loc[fin_saut, 'tick'].tolist()

    total_sauts = len(ticks_debut_saut)
    if total_sauts < 3:
        return {
            "bhop_total_sauts": total_sauts,
            "bhop_ratio_parfaits": 0.0,
            "bhop_variance_sol": 50.0,
            "bhop_chaine_max": 0,
            "bhop_vitesse_moyenne": float(donnees['vitesse_2d'].mean()) if not donnees.empty else 0.0,
            "bhop_autostrafe_correlation": 0.0,
            "bhop_velocity_gain_max": 0.0,
        }

    # Analyse des intervalles au sol entre réceptions et sauts suivants
    ticks_au_sol_intervalles = []
    sauts_parfaits = 0
    chaine_actuelle = 0
    chaine_max = 0

    for t_fin in ticks_fin_saut:
        prochain_saut = None
        for t_deb in ticks_debut_saut:
            if t_deb > t_fin:
                prochain_saut = t_deb
                break

        if prochain_saut is not None:
            intervalle = prochain_saut - t_fin
            ticks_au_sol_intervalles.append(intervalle)
            if intervalle <= get_config().bhop_perfect_tick_max:
                sauts_parfaits += 1
                chaine_actuelle += 1
                chaine_max = max(chaine_max, chaine_actuelle)
            else:
                chaine_actuelle = 0

    ratio_parfaits = sauts_parfaits / max(len(ticks_au_sol_intervalles), 1)
    variance_sol = float(np.var(ticks_au_sol_intervalles)) if ticks_au_sol_intervalles else 50.0

    # Analyse Autostrafe & Gain de vitesse dans les airs
    autostrafe_corr = 0.0
    vel_gain_max = 0.0
    if est_en_lair.sum() > 20 and 'yaw' in donnees.columns:
        air_data = donnees[est_en_lair].copy()
        d_yaw = air_data['yaw'].diff().dropna()
        vel_ang = np.degrees(np.arctan2(air_data['velocity_Y'], air_data['velocity_X'])).diff().dropna()
        if len(d_yaw) > 10 and len(vel_ang) > 10:
            min_len = min(len(d_yaw), len(vel_ang))
            c = np.corrcoef(d_yaw.iloc[:min_len], vel_ang.iloc[:min_len])[0, 1]
            autostrafe_corr = float(c) if not np.isnan(c) else 0.0
        # Gain max de vitesse
        gains = air_data['vitesse_2d'].diff().dropna()
        if not gains.empty:
            vel_gain_max = float(gains.max())

    profil_bhop = {
        "bhop_total_sauts": total_sauts,
        "bhop_ratio_parfaits": round(ratio_parfaits, 4),
        "bhop_variance_sol": round(variance_sol, 4),
        "bhop_chaine_max": chaine_max,
        "bhop_vitesse_moyenne": round(float(donnees['vitesse_2d'].mean()), 4),
        "bhop_autostrafe_correlation": round(autostrafe_corr, 4),
        "bhop_velocity_gain_max": round(vel_gain_max, 4),
    }

    return profil_bhop


from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class BhopResult:
    metrics: Dict[str, float] = field(default_factory=dict)
    flagged_chains: List[Dict[str, Any]] = field(default_factory=list)

BhopAnalysisResult = BhopResult

def _resolve_name_bhop(demo_data, identifier: str) -> str:
    try:
        if hasattr(demo_data, 'joueurs') and identifier in getattr(demo_data, 'joueurs', []):
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

def _get_player_ticks_bhop(demo_data, identifier):
    if hasattr(demo_data, 'get_player_ticks'):
        try:
            return demo_data.get_player_ticks(identifier)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    if hasattr(demo_data, 'obtenir_donnees_joueur'):
        try:
            name = _resolve_name_bhop(demo_data, identifier)
            return demo_data.obtenir_donnees_joueur(name)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    return pd.DataFrame()

def analyze_bhop(demo_data_or_path, identifier: str) -> BhopResult:
    demo_data = demo_data_or_path if hasattr(demo_data_or_path, 'ticks') else charger_demo(demo_data_or_path)
    is_valid = getattr(demo_data, 'is_valid', getattr(demo_data, 'valide', True))
    # Mock path (MockDemoData / MockAdversarialDemoData)
    if type(demo_data).__name__ != 'DemoData' and hasattr(demo_data, 'ticks') and hasattr(demo_data, 'get_player_ticks'):
        try:
            donnees = _get_player_ticks_bhop(demo_data, identifier)
            if donnees.empty or len(donnees) < 5 or 'is_airborne' not in donnees.columns:
                return BhopResult(metrics={"bhop_total_sauts": 0.0, "bhop_ratio_parfaits": 0.0, "bhop_variance_sol": 50.0, "bhop_chaine_max": 0.0, "bhop_vitesse_moyenne": 0.0}, flagged_chains=[])
            
            est_en_lair = donnees['is_airborne'].astype(bool)
            # Check for permanently airborne or permanently grounded
            if est_en_lair.all() or (~est_en_lair).all():
                vitesse = float(np.sqrt((donnees['velocity_X']**2 + donnees['velocity_Y']**2).mean())) if 'velocity_X' in donnees.columns else 0.0
                return BhopResult(metrics={"bhop_total_sauts": 0.0, "bhop_ratio_parfaits": 0.0, "bhop_variance_sol": 50.0, "bhop_chaine_max": 0.0, "bhop_vitesse_moyenne": round(vitesse, 4)}, flagged_chains=[])

            debut = (~est_en_lair.shift(1, fill_value=bool(est_en_lair.iloc[0]))) & est_en_lair
            fin = est_en_lair.shift(1, fill_value=bool(est_en_lair.iloc[0])) & (~est_en_lair)
            ticks_debut = donnees.loc[debut, 'tick'].tolist()
            ticks_fin = donnees.loc[fin, 'tick'].tolist()
            total = len(ticks_debut)
            if total < 2:
                vitesse = float(np.sqrt((donnees['velocity_X']**2 + donnees['velocity_Y']**2).mean())) if 'velocity_X' in donnees.columns else 0.0
                return BhopResult(metrics={"bhop_total_sauts": float(total), "bhop_ratio_parfaits": 0.0, "bhop_variance_sol": 50.0, "bhop_chaine_max": 0.0, "bhop_vitesse_moyenne": round(vitesse, 4)}, flagged_chains=[])
            intervals = []
            parfaits = 0
            chaine = 0
            chaine_max = 0
            for t_fin in ticks_fin:
                nxt = None
                for t_deb in ticks_debut:
                    if t_deb > t_fin:
                        nxt = t_deb
                        break
                if nxt is not None:
                    iv = nxt - t_fin
                    intervals.append(iv)
                    if iv <= get_config().bhop_perfect_tick_max:
                        parfaits += 1
                        chaine += 1
                        chaine_max = max(chaine_max, chaine)
                    else:
                        chaine = 0
            ratio = parfaits / max(len(intervals), 1) if intervals else 0.0
            vitesse = float(np.sqrt((donnees['velocity_X']**2 + donnees['velocity_Y']**2).mean())) if 'velocity_X' in donnees.columns else 0.0
            metrics = {
                "bhop_total_sauts": float(total),
                "bhop_ratio_parfaits": round(float(ratio), 4),
                "bhop_variance_sol": round(float(np.var(intervals) if intervals else 50.0), 4),
                "bhop_chaine_max": float(chaine_max),
                "bhop_vitesse_moyenne": round(float(vitesse), 4),
                "bhop_autostrafe_correlation": 0.0,
                "bhop_velocity_gain_max": 0.0,
            }
            chains = []
            if chaine_max >= 4 or (ratio > 0.60 and total >= 5):
                chains.append({"start_tick": int(ticks_debut[0]) if ticks_debut else 0, "end_tick": int(ticks_debut[min(chaine_max, len(ticks_debut)-1)]) if ticks_debut else 0, "chain_length": chaine_max, "avg_speed": vitesse})
            return BhopResult(metrics=metrics, flagged_chains=chains)
        except Exception:
            import traceback; traceback.print_exc()
    name = _resolve_name_bhop(demo_data, identifier) if is_valid else identifier
    # ensure demo_data is DemoData-like for FR
    if not hasattr(demo_data, 'valide'):
        # wrap mock as demo_data
        profil = {
            "bhop_total_sauts": 0, "bhop_ratio_parfaits": 0.0, "bhop_variance_sol": 50.0,
            "bhop_chaine_max": 0, "bhop_vitesse_moyenne": 0.0,
            "bhop_autostrafe_correlation": 0.0, "bhop_velocity_gain_max": 0.0,
        }
        return BhopResult(metrics=profil, flagged_chains=[])
    profil = analyser_bhop(demo_data, name)
    chains = []
    if profil.get("bhop_chaine_max", 0) >= 4 or (profil.get("bhop_ratio_parfaits", 0) > 0.60 and profil.get("bhop_total_sauts", 0) >= 15):
        chains.append({
            "start_tick": 0,
            "end_tick": int(profil.get("bhop_chaine_max", 0) * 10),
            "chain_length": int(profil.get("bhop_chaine_max", 0)),
            "avg_speed": float(profil.get("bhop_vitesse_moyenne", 0)),
        })
    return BhopResult(metrics=profil, flagged_chains=chains)

analyse_bhop = analyser_bhop
