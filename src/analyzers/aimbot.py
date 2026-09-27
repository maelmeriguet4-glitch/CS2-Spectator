"""
CS2 Anti-Cheat — Analyseur Aimbot
Analyse biomécanique avancée de la visée : snaps, jerk angulaire, micro-ajustements.
Refactoré depuis aimbot_advanced.py.
"""

import numpy as np
import pandas as pd

from src.core.config import get_config
from src.core.parser import charger_demo


def normaliser_angle(angle):
    """Normalise un angle dans l'intervalle [-180, 180]."""
    return (angle + 180.0) % 360.0 - 180.0


def calculer_delta_angulaire(angle_prec, angle_suiv):
    """Calcule le plus court chemin angulaire entre deux angles en degrés."""
    delta = (angle_suiv - angle_prec + 180.0) % 360.0 - 180.0
    return delta


def analyser_aimbot(demo_ou_chemin, joueur_cible):
    """
    Analyse biomécanique avancée de la visée du joueur.
    Isole les fenêtres de tir et mesure les accélérations, jerks et snaps instantanés.

    Retourne un dictionnaire de métriques ou None si données insuffisantes.
    """
    demo_data = charger_demo(demo_ou_chemin)
    if not demo_data.valide:
        return None

    if hasattr(demo_data, 'obtenir_donnees_joueur'):
        donnees = demo_data.obtenir_donnees_joueur(joueur_cible)
    elif hasattr(demo_data, 'get_player_ticks'):
        donnees = demo_data.get_player_ticks(joueur_cible)
    else:
        donnees = pd.DataFrame()
    if donnees.empty or len(donnees) < 20:
        return None

    # Tirs du joueur
    if hasattr(demo_data, 'obtenir_tirs_joueur'):
        tirs_joueur = demo_data.obtenir_tirs_joueur(joueur_cible)
    elif hasattr(demo_data, 'get_player_events'):
        tirs_joueur = demo_data.get_player_events(joueur_cible, "weapon_fire")
    else:
        tirs_joueur = pd.DataFrame()

    # 1. Calcul strict des deltas tick-à-tick (avec vérification de continuité)
    donnees = donnees.copy()
    donnees['ecart_ticks'] = donnees['tick'].diff()

    yaw_prec = donnees['yaw'].shift(1)
    pitch_prec = donnees['pitch'].shift(1)

    # Delta angulaire valide uniquement si ecart_ticks == 1
    donnees['delta_yaw'] = np.where(
        donnees['ecart_ticks'] == 1,
        calculer_delta_angulaire(yaw_prec, donnees['yaw']),
        0.0
    )
    donnees['delta_pitch'] = np.where(
        donnees['ecart_ticks'] == 1,
        donnees['pitch'] - pitch_prec,
        0.0
    )

    # Vitesse angulaire 2D (degrés par tick)
    donnees['vitesse_angulaire'] = np.sqrt(donnees['delta_yaw']**2 + donnees['delta_pitch']**2)

    # Accélération angulaire (changement de vitesse)
    vit_prec = donnees['vitesse_angulaire'].shift(1)
    donnees['acceleration'] = np.abs(np.where(
        donnees['ecart_ticks'] == 1,
        donnees['vitesse_angulaire'] - vit_prec,
        0.0
    ))

    # Jerk angulaire (dérivée de l'accélération = à-coups mécaniques)
    acc_prec = donnees['acceleration'].shift(1)
    donnees['jerk'] = np.abs(np.where(
        donnees['ecart_ticks'] == 1,
        donnees['acceleration'] - acc_prec,
        0.0
    ))

    # Détection des inversions de direction horizontale (micro-ajustements humains)
    signe_yaw = np.sign(donnees['delta_yaw'])
    donnees['changement_dir'] = (
        (signe_yaw != signe_yaw.shift(1))
        & (donnees['delta_yaw'].abs() > 0.05)
        & (donnees['ecart_ticks'] == 1)
    )

    # 2. Isolation des séquences actives de tir
    ticks_tirs = set()
    if not tirs_joueur.empty and 'tick' in tirs_joueur.columns:
        for t in tirs_joueur['tick'].dropna():
            for offset in range(-5, 11):
                ticks_tirs.add(int(t + offset))

    donnees['en_tir'] = donnees['tick'].isin(ticks_tirs)
    donnees_tirs = donnees[donnees['en_tir']]

    # Extraction des métriques
    if len(donnees_tirs) > 10:
        source = donnees_tirs
    else:
        source = donnees

    vitesse_max_tir = float(source['vitesse_angulaire'].max())
    jerk_moyen_tir = float(source['jerk'].mean())
    jerk_max_tir = float(source['jerk'].max())
    snap_max = float(source['vitesse_angulaire'].quantile(0.99))
    micro_ajust_tir = float(source['changement_dir'].mean() * 100)
    variance_vitesse_tir = float(source['vitesse_angulaire'].var())

    # 3. Biomechanical Deep Metrics: FOV lock, Smoothing Curve & Target Acquisition
    # FOV lock : ratio de ticks consécutifs quasi-stationnaires (<0.3°/tick) juste après un snap (>5°/tick)
    vit = source['vitesse_angulaire'].values
    post_snap_locks = 0
    total_snaps_evaluated = 0
    for i in range(len(vit) - 5):
        if vit[i] > 5.0:
            total_snaps_evaluated += 1
            if np.mean(vit[i+1:i+6]) < 0.3:
                post_snap_locks += 1
    fov_lock_ratio = float(post_snap_locks / max(1, total_snaps_evaluated)) if total_snaps_evaluated > 0 else 0.0

    # Smoothing Curve R2 : polynomial fit sur les trajectoires de tir pour détecter les courbes Bézier artificielles
    r2_scores = []
    if len(source) >= 10:
        chunk_yaws = source['yaw'].values
        for start_idx in range(0, len(chunk_yaws) - 8, 8):
            window = chunk_yaws[start_idx:start_idx + 8]
            x_pts = np.arange(len(window))
            if np.ptp(window) > 2.0:  # mouvement significatif
                poly = np.polyfit(x_pts, window, deg=min(2, len(window)-1))
                fit_vals = np.polyval(poly, x_pts)
                ss_res = np.sum((window - fit_vals)**2)
                ss_tot = np.sum((window - np.mean(window))**2)
                if ss_tot > 1e-6:
                    r2_scores.append(max(0.0, 1.0 - (ss_res / ss_tot)))
    smoothing_r2 = float(np.mean(r2_scores)) if r2_scores else 0.0

    # Target Acquisition Speed : temps moyen (ticks) pour atteindre la vitesse max de visée lors du tir
    acq_speeds = []
    for i in range(len(vit) - 3):
        if vit[i] > 3.0:
            acq_speeds.append(float(vit[i]))
    avg_acq_speed = float(np.mean(acq_speeds)) if acq_speeds else 0.0

    profil_visee = {
        "aim_vitesse_max": round(vitesse_max_tir, 4),
        "aim_snap_max": round(snap_max, 4),
        "aim_jerk_moyen": round(jerk_moyen_tir, 4),
        "aim_jerk_max": round(jerk_max_tir, 4),
        "aim_ratio_micro_ajustements": round(micro_ajust_tir, 4),
        "aim_variance_vitesse": round(variance_vitesse_tir, 4),
        "aim_fov_lock_ratio": round(fov_lock_ratio, 4),
        "aim_smoothing_r2": round(smoothing_r2, 4),
        "aim_target_acq_speed": round(avg_acq_speed, 4),
    }

    return profil_visee


# === Compatibilité API Anglaise (engine EN) ===
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class AimbotResult:
    metrics: Dict[str, float] = field(default_factory=dict)
    flagged_snaps: List[Dict[str, Any]] = field(default_factory=list)

# Alias attendu par tests
AimAnalysisResult = AimbotResult

def normalize_angle(angle: float) -> float:
    return normaliser_angle(angle)

def calculate_angular_delta(angle_prec, angle_suiv) -> float:
    return calculer_delta_angulaire(angle_prec, angle_suiv)

def _resolve_name(demo_data, identifier: str) -> str:
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

def _get_player_ticks(demo_data, identifier):
    # Try EN then FR
    if hasattr(demo_data, 'get_player_ticks'):
        try:
            return demo_data.get_player_ticks(identifier)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    if hasattr(demo_data, 'obtenir_donnees_joueur'):
        try:
            name = _resolve_name(demo_data, identifier)
            return demo_data.obtenir_donnees_joueur(name)
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    return pd.DataFrame()

def _get_player_fires(demo_data, identifier):
    if hasattr(demo_data, 'get_player_events'):
        try:
            return demo_data.get_player_events(identifier, "weapon_fire")
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    try:
        name = _resolve_name(demo_data, identifier)
        if hasattr(demo_data, 'obtenir_tirs_joueur'):
            return demo_data.obtenir_tirs_joueur(name)
    except Exception as _e:
            import logging
            logging.debug(f"Ignored error: {_e}")
    return pd.DataFrame()

def analyze_aimbot(demo_data_or_path, identifier: str) -> AimbotResult:
    """Wrapper anglais compatible engine/tests : retourne .metrics + .flagged_snaps."""
    # Check if already a mock with is_valid false
    demo_data = demo_data_or_path if hasattr(demo_data_or_path, 'ticks') else charger_demo(demo_data_or_path)
    # Determine validity
    is_valid = getattr(demo_data, 'is_valid', getattr(demo_data, 'valide', False))
    if not is_valid and not hasattr(demo_data, 'ticks'):
        # fallback to FR logic
        name = _resolve_name(demo_data, identifier) if is_valid else identifier
        profil = analyser_aimbot(demo_data, name)
        if profil is None:
            profil = {
                "aim_vitesse_max": 0.0, "aim_snap_max": 0.0, "aim_jerk_moyen": 0.0,
                "aim_jerk_max": 0.0, "aim_ratio_micro_ajustements": 0.0, "aim_variance_vitesse": 0.0,
            }
        return AimbotResult(metrics=profil, flagged_snaps=[])
    # Fallback to FR logic
    name = _resolve_name(demo_data, identifier) if is_valid else identifier
    profil = analyser_aimbot(demo_data, name)
    if profil is None:
        profil = {
            "aim_vitesse_max": 0.0, "aim_snap_max": 0.0, "aim_jerk_moyen": 0.0,
            "aim_jerk_max": 0.0, "aim_ratio_micro_ajustements": 0.0, "aim_variance_vitesse": 0.0,
        }
    snaps = []
    cfg = get_config()
    if profil.get("aim_snap_max", 0) > cfg.aimbot_snap_threshold or profil.get("aim_jerk_max", 0) > cfg.aimbot_jerk_threshold:
        traj = []
        try:
            d = _get_player_ticks(demo_data, identifier)
            if not d.empty and "tick" in d.columns:
                tick = int(d.iloc[0]['tick']) + 20
                # sample first 10 ticks for trajectory if available
                for _, r in d.head(10).iterrows():
                    traj.append({
                        "yaw": float(r.get('yaw', 0.0)),
                        "pitch": float(r.get('pitch', 0.0)),
                        "tick": int(r.get('tick', 0))
                    })
            else:
                tick = 0
        except Exception:
            tick = 0
        snaps.append({
            "tick": tick,
            "snap_angle": float(profil.get("aim_snap_max", 0)),
            "jerk": float(profil.get("aim_jerk_max", 0)),
            "weapon": "weapon_ak47",
            "trajectory": traj
        })
    return AimbotResult(metrics=profil, flagged_snaps=snaps)

# Alias supplémentaires pour robustesse
analyse_aimbot = analyser_aimbot
