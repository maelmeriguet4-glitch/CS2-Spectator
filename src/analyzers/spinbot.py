"""
CS2 Anti-Cheat — Analyseur Spinbot / Anti-Aim
Détection de mouvements non naturels de la caméra : spins, pitch invalide, jitter, desync.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from src.core.config import get_config
from src.core.parser import charger_demo


def calculer_delta_angulaire(angle_prec, angle_suiv):
    """Calcule le plus court chemin angulaire entre deux angles en degrés (yaw)."""
    delta = (angle_suiv - angle_prec + 180.0) % 360.0 - 180.0
    return delta

def analyser_spinbot(demo_ou_chemin, joueur_cible):
    """
    Analyse les données du joueur pour détecter l'utilisation de Spinbot et Anti-Aim.
    
    Retourne un dictionnaire de métriques et les événements suspects.
    """
    cfg = get_config()
    demo_data = charger_demo(demo_ou_chemin)
    if not demo_data.valide:
        return None

    donnees = demo_data.obtenir_donnees_joueur(joueur_cible)
    if donnees.empty or len(donnees) < 32:
        return None

    donnees = donnees.copy()
    donnees['ecart_ticks'] = donnees['tick'].diff()

    # 1. Continuous Yaw Spin (16 ticks)
    yaw_prec = donnees['yaw'].shift(1)
    donnees['delta_yaw'] = np.where(
        donnees['ecart_ticks'] == 1,
        calculer_delta_angulaire(yaw_prec, donnees['yaw']),
        0.0
    )
    donnees['yaw_speed'] = donnees['delta_yaw'].abs()
    # Sliding window of 16 ticks for mean yaw speed
    donnees['mean_yaw_speed_16'] = donnees['yaw_speed'].rolling(window=cfg.spinbot_window_size, min_periods=cfg.spinbot_window_size).mean()
    spinbot_yaw_speed_max = float(donnees['mean_yaw_speed_16'].max())
    if np.isnan(spinbot_yaw_speed_max):
        spinbot_yaw_speed_max = 0.0
    spinbot_yaw_spin_windows = int((donnees['mean_yaw_speed_16'] > cfg.spinbot_yaw_speed_threshold).sum())

    # 2. Invalid Pitch
    pitch_out = ((donnees['pitch'] < -89.5) | (donnees['pitch'] > 89.5)).sum()
    spinbot_pitch_violations = int(pitch_out)

    # 3. Jitter Anti-Aim (8 ticks)
    donnees['pitch_var_8'] = donnees['pitch'].rolling(window=cfg.spinbot_jitter_window, min_periods=cfg.spinbot_jitter_window).var()
    
    pitch_prec = donnees['pitch'].shift(1)
    donnees['delta_pitch'] = np.where(donnees['ecart_ticks'] == 1, donnees['pitch'] - pitch_prec, 0.0)
    signe_pitch = np.sign(donnees['delta_pitch'])
    donnees['changement_signe_pitch'] = (signe_pitch != signe_pitch.shift(1)) & (donnees['ecart_ticks'] == 1)
    # Rapid sign changes (sum over 8 ticks)
    donnees['pitch_sign_changes_8'] = donnees['changement_signe_pitch'].rolling(window=cfg.spinbot_jitter_window, min_periods=cfg.spinbot_jitter_window).sum()
    
    spinbot_jitter_score = float(donnees['pitch_var_8'].max())
    if np.isnan(spinbot_jitter_score):
        spinbot_jitter_score = 0.0

    # 4. Anti-Aim Rapid Yaw Oscillation / Jitter (True Desync)
    # Les anti-aims alternent les angles de vue de ~180° d'un tick à l'autre pour fausser le hitbox
    yaw_flick = (donnees['delta_yaw'].abs() > cfg.spinbot_desync_angle) & (donnees['ecart_ticks'] == 1)
    sign_flips = (np.sign(donnees['delta_yaw']) != np.sign(donnees['delta_yaw'].shift(1))) & yaw_flick
    desync_groups = (~sign_flips).cumsum()
    desync_streaks = sign_flips.groupby(desync_groups).sum()
    spinbot_desync_max_ticks = int(desync_streaks.max()) if not desync_streaks.empty else 0

    metrics = {
        "spinbot_yaw_speed_max": round(spinbot_yaw_speed_max, 4),
        "spinbot_pitch_violations": spinbot_pitch_violations,
        "spinbot_jitter_score": round(spinbot_jitter_score, 4),
        "spinbot_desync_max_ticks": spinbot_desync_max_ticks,
        "spinbot_yaw_spin_windows": spinbot_yaw_spin_windows,
    }

    return metrics


# === Compatibilité API Anglaise (engine EN) ===

@dataclass
class SpinbotResult:
    metrics: Dict[str, float] = field(default_factory=dict)
    flagged_events: List[Dict[str, Any]] = field(default_factory=list)

SpinbotAnalysisResult = SpinbotResult

def _resolve_name_spinbot(demo_data, identifier: str) -> str:
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

def _get_player_ticks_spinbot(demo_data, identifier):
    if hasattr(demo_data, 'get_player_ticks'):
        try:
            return demo_data.get_player_ticks(identifier)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    if hasattr(demo_data, 'obtenir_donnees_joueur'):
        try:
            name = _resolve_name_spinbot(demo_data, identifier)
            return demo_data.obtenir_donnees_joueur(name)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    return pd.DataFrame()


def analyze_spinbot(demo_data_or_path, identifier: str) -> SpinbotResult:
    cfg = get_config()
    demo_data = demo_data_or_path if hasattr(demo_data_or_path, 'ticks') else charger_demo(demo_data_or_path)
    is_valid = getattr(demo_data, 'is_valid', getattr(demo_data, 'valide', False))
    
    default_metrics = {
        "spinbot_yaw_speed_max": 0.0,
        "spinbot_pitch_violations": 0,
        "spinbot_jitter_score": 0.0,
        "spinbot_desync_max_ticks": 0,
        "spinbot_yaw_spin_windows": 0
    }

    if not is_valid and not hasattr(demo_data, 'ticks'):
        name = _resolve_name_spinbot(demo_data, identifier) if is_valid else identifier
        profil = analyser_spinbot(demo_data, name)
        if profil is None:
            profil = default_metrics
        return SpinbotResult(metrics=profil, flagged_events=[])

    name = _resolve_name_spinbot(demo_data, identifier) if is_valid else identifier
    profil = analyser_spinbot(demo_data, name)
    if profil is None:
        profil = default_metrics

    events = []
    jitter_threshold = float(getattr(cfg, "spinbot_jitter_variance", 2000.0))
    desync_threshold = int(getattr(cfg, "spinbot_desync_min_ticks", 6))
    if (
        profil.get("spinbot_yaw_spin_windows", 0) > 0
        or profil.get("spinbot_pitch_violations", 0) > 0
        or profil.get("spinbot_jitter_score", 0) > jitter_threshold
        or profil.get("spinbot_desync_max_ticks", 0) >= desync_threshold
    ):
        events.append({"type": "spinbot_detected", "metrics": profil})

    return SpinbotResult(metrics=profil, flagged_events=events)

# Alias supplémentaires pour robustesse
analyse_spinbot = analyser_spinbot
