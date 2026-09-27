"""
CS2 Anti-Cheat — Features & Classification ML
Extraction de vecteurs de features et classification via modèle calibré.
Gère de manière distincte le modèle synthétique (cerveau_vac_custom.pkl)
et le modèle entraîné sur données réelles (cerveau_vac_cs2cd.pkl).
"""

from dataclasses import dataclass, field
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

NOMS_FEATURES = [
    "aim_vitesse_max",
    "aim_snap_max",
    "aim_jerk_moyen",
    "aim_jerk_max",
    "aim_ratio_micro_ajustements",
    "aim_variance_vitesse",
    "bhop_total_sauts",
    "bhop_ratio_parfaits",
    "bhop_variance_sol",
    "bhop_chaine_max",
    "bhop_vitesse_moyenne",
    "wh_ratio_lock_cache",
    "wh_ratio_lock_strict",
    "wh_tracking_consecutif_max",
    "wh_distance_moyenne_verrous",
]

# Chemins des modèles distincts
_DIR_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FICHIER_MODELE_SYNTHETIQUE = os.path.join(_DIR_RACINE, "cerveau_vac_custom.pkl")
FICHIER_MODELE_CS2CD = os.path.join(_DIR_RACINE, "cerveau_vac_cs2cd.pkl")

# Rétrocompatibilité
FICHIER_MODELE = FICHIER_MODELE_SYNTHETIQUE


def extraire_vecteur_features(profil_aim, profil_bhop, profil_wh):
    """Convertit les dictionnaires de métriques en vecteur numérique ordonné (15 features)."""
    aim = profil_aim or {}
    bhop = profil_bhop or {}
    wh = profil_wh or {}

    vecteur = [
        float(aim.get("aim_vitesse_max", 0.0)),
        float(aim.get("aim_snap_max", 0.0)),
        float(aim.get("aim_jerk_moyen", 0.0)),
        float(aim.get("aim_jerk_max", 0.0)),
        float(aim.get("aim_ratio_micro_ajustements", 0.0)),
        float(aim.get("aim_variance_vitesse", 0.0)),
        float(bhop.get("bhop_total_sauts", 0)),
        float(bhop.get("bhop_ratio_parfaits", 0.0)),
        float(bhop.get("bhop_variance_sol", 50.0)),
        float(bhop.get("bhop_chaine_max", 0)),
        float(bhop.get("bhop_vitesse_moyenne", 0.0)),
        float(wh.get("wh_ratio_lock_cache", 0.0)),
        float(wh.get("wh_ratio_lock_strict", 0.0)),
        float(wh.get("wh_tracking_consecutif_max", 0)),
        float(wh.get("wh_distance_moyenne_verrous", 0.0)),
    ]
    return np.array(vecteur, dtype=np.float64)


def generer_dataset_calibre(nb_clean=1000, nb_cheats=1000):
    """Génère un dataset d'entraînement calibré basé sur les lois physiques réelles de CS2."""
    rng = np.random.default_rng(42)
    X = []
    y = []

    for _ in range(nb_clean):
        v_max = rng.uniform(8.0, 30.0)
        snap_max = rng.uniform(1.5, 7.0)
        jerk_mean = rng.uniform(0.05, 0.25)
        jerk_max = rng.uniform(2.0, 12.0)
        micro_adj = rng.uniform(3.0, 12.0)
        var_v = rng.uniform(0.1, 2.5)
        sauts = rng.integers(15, 120)
        bhop_perf = rng.uniform(0.0, 0.20)
        bhop_var = rng.uniform(5.0, 35.0)
        bhop_chain = rng.choice([0, 1, 2], p=[0.7, 0.25, 0.05])
        bhop_spd = rng.uniform(110.0, 180.0)
        wh_lock = rng.uniform(0.02, 0.18)
        wh_strict = rng.uniform(0.005, 0.06)
        wh_track = rng.integers(0, 10)
        wh_dist = rng.uniform(800.0, 2000.0)
        X.append([v_max, snap_max, jerk_mean, jerk_max, micro_adj, var_v,
                  sauts, bhop_perf, bhop_var, bhop_chain, bhop_spd,
                  wh_lock, wh_strict, wh_track, wh_dist])
        y.append(0)

    for _ in range(nb_cheats):
        type_cheat = rng.choice(["aimbot", "bhop", "wallhack", "rage"])
        v_max = rng.uniform(8.0, 30.0)
        snap_max = rng.uniform(1.5, 7.0)
        jerk_mean = rng.uniform(0.05, 0.25)
        jerk_max = rng.uniform(2.0, 12.0)
        micro_adj = rng.uniform(3.0, 12.0)
        var_v = rng.uniform(0.1, 2.5)
        sauts = rng.integers(15, 120)
        bhop_perf = rng.uniform(0.0, 0.20)
        bhop_var = rng.uniform(5.0, 35.0)
        bhop_chain = rng.choice([0, 1, 2], p=[0.7, 0.25, 0.05])
        bhop_spd = rng.uniform(110.0, 180.0)
        wh_lock = rng.uniform(0.02, 0.18)
        wh_strict = rng.uniform(0.005, 0.06)
        wh_track = rng.integers(0, 10)
        wh_dist = rng.uniform(800.0, 2000.0)

        if type_cheat == "aimbot":
            snap_max = rng.uniform(18.5, 55.0)
            jerk_max = rng.uniform(32.0, 120.0)
            micro_adj = rng.uniform(0.0, 2.0)
        elif type_cheat == "bhop":
            bhop_perf = rng.uniform(0.70, 0.98)
            bhop_var = rng.uniform(0.0, 3.0)
            bhop_chain = rng.integers(4, 15)
            bhop_spd = rng.uniform(240.0, 310.0)
        elif type_cheat == "wallhack":
            wh_strict = rng.uniform(0.14, 0.45)
            wh_track = rng.integers(85, 250)
            wh_lock = rng.uniform(0.25, 0.60)
        elif type_cheat == "rage":
            snap_max = rng.uniform(40.0, 90.0)
            jerk_max = rng.uniform(60.0, 180.0)
            bhop_perf = rng.uniform(0.85, 1.0)
            wh_strict = rng.uniform(0.30, 0.70)
            wh_track = rng.integers(120, 400)

        X.append([v_max, snap_max, jerk_mean, jerk_max, micro_adj, var_v,
                  sauts, bhop_perf, bhop_var, bhop_chain, bhop_spd,
                  wh_lock, wh_strict, wh_track, wh_dist])
        y.append(1)

    return np.array(X), np.array(y)


def entrainer_le_modele(chemin_sortie=FICHIER_MODELE_SYNTHETIQUE):
    """Entraîne et sauvegarde le package d'IA anti-cheat synthétique de référence."""
    X, y = generer_dataset_calibre(nb_clean=3000, nb_cheats=3000)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    rf = RandomForestClassifier(n_estimators=200, max_depth=12, random_state=42)
    rf.fit(X_scaled, y)

    X_clean_scaled = X_scaled[y == 0]
    iso = IsolationForest(contamination=0.03, random_state=42)
    iso.fit(X_clean_scaled)

    paquet_ia = {
        "scaler": scaler,
        "modele": rf,
        "isolation_forest": iso,
        "noms_features": NOMS_FEATURES,
        "dataset_name": "Synthetic_Physical_CS2",
        "model_type": "RandomForestClassifier",
    }

    joblib.dump(paquet_ia, chemin_sortie)
    return paquet_ia


def charger_ou_entrainer_modele(chemin_modele=None, model_type="auto"):
    """
    Charge le modèle demandé sans jamais substituer silencieusement un modèle synthétique sous le nom CS2CD.
    Options model_type: 'auto', 'cs2cd', 'synthetic'.
    """
    if chemin_modele:
        cible = chemin_modele
    elif model_type == "cs2cd":
        cible = FICHIER_MODELE_CS2CD
    elif model_type == "synthetic":
        cible = FICHIER_MODELE_SYNTHETIQUE
    else:  # auto
        cible = FICHIER_MODELE_SYNTHETIQUE

    if os.path.exists(cible):
        try:
            paquet = joblib.load(cible)
            if isinstance(paquet, dict) and "modele" in paquet and "scaler" in paquet:
                return paquet
        except Exception as e:
            logger.warning(f"[ML] Échec de chargement de {cible}: {e}")

    if model_type == "cs2cd":
        raise FileNotFoundError(
            f"Le modèle CS2CD '{cible}' n'existe pas. "
            f"Veuillez exécuter scripts/train_cs2cd.py pour l'entraîner sur les données réelles."
        )

    # Entraîner le modèle synthétique si et seulement si cible synthétique
    logger.info("[ML] Initialisation du modèle synthétique de référence...")
    return entrainer_le_modele(FICHIER_MODELE_SYNTHETIQUE)


def classifier_joueur(
    profil_aim, profil_bhop, profil_wh,
    nom_joueur="Joueur",
    profil_spin=None,
    profil_trigger=None,
    paquet_existant=None
):
    """
    Évalue un joueur via le modèle ML et les règles biomécaniques.
    Produit des scores décorrélés (ml_score, anomaly_score, suspicion_score).
    """
    if not profil_aim or not profil_bhop or not profil_wh:
        return None

    from src.core.config import get_config
    cfg = get_config()

    paquet = paquet_existant or charger_ou_entrainer_modele()
    scaler = paquet["scaler"]
    modele = paquet["modele"]
    iso = paquet.get("isolation_forest")

    vecteur = extraire_vecteur_features(profil_aim, profil_bhop, profil_wh)
    vecteur_scaled = scaler.transform(vecteur.reshape(1, -1))

    # 1. Score ML supervisé [0.0 - 100.0]
    ml_score = float(modele.predict_proba(vecteur_scaled)[0][1] * 100.0)

    # 2. Score Anomaly non supervisé IsolationForest
    anomaly_score = 0.0
    if iso is not None:
        try:
            df_val = float(iso.decision_function(vecteur_scaled)[0])
            # Transformation sigmoïde
            anomaly_score = round(float(1.0 / (1.0 + np.exp(df_val * 10.0))), 4)
        except Exception:
            anomaly_score = 0.0

    # 3. Évaluation des règles expertes
    facteurs = []
    cheats_detectes = []
    pills = []

    # Aimbot
    snap = float(profil_aim.get("aim_snap_max", 0))
    jerk = float(profil_aim.get("aim_jerk_max", 0))
    if snap > cfg.aimbot_snap_threshold:
        facteurs.append(f"Snap instantané anormal ({snap:.1f}°/tick)")
        cheats_detectes.append(f"AIMBOT: Snap {snap:.1f}°/tick")
        pills.append(f"[AIMBOT: Snap {snap:.1f}°/tick]")
    if jerk > cfg.aimbot_jerk_threshold:
        facteurs.append(f"À-coups mécaniques suspects ({jerk:.1f})")
        if not any("Jerk" in c for c in cheats_detectes):
            cheats_detectes.append(f"AIMBOT: Jerk {jerk:.1f}")
        pills.append(f"[AIMBOT: Jerk {jerk:.1f}]")

    # Bhop
    bhop_ratio = float(profil_bhop.get("bhop_ratio_parfaits", 0))
    bhop_total = int(profil_bhop.get("bhop_total_sauts", 0))
    bhop_chain = int(profil_bhop.get("bhop_chaine_max", 0))
    if bhop_ratio > cfg.bhop_script_ratio and bhop_total >= cfg.bhop_min_jumps_for_flag:
        facteurs.append(f"Bhop scripté ({bhop_ratio*100:.1f}% parfaits)")
        cheats_detectes.append(f"BHOP: Script {bhop_ratio*100:.0f}%")
        pills.append(f"[BHOP: Script {bhop_ratio*100:.0f}%]")
    if bhop_chain >= 4:
        facteurs.append(f"Chaîne de BunnyHop inhumaine ({bhop_chain} consécutifs)")
        if not any("Chaîne" in c for c in cheats_detectes):
            cheats_detectes.append(f"BHOP: Chaîne {bhop_chain}")
        pills.append(f"[BHOP: Chaîne x{bhop_chain}]")

    # Wallhack / INFO-ESP
    wh_strict = float(profil_wh.get("wh_ratio_lock_strict", 0))
    wh_track = int(profil_wh.get("wh_tracking_consecutif_max", 0))
    if wh_strict > 0.12 and wh_track >= 80:
        facteurs.append(f"Alignement occlus suspect ({wh_strict*100:.1f}%)")
        cheats_detectes.append(f"INFO-ESP: {wh_track} Locks")
        pills.append(f"[INFO-ESP: {wh_strict*100:.1f}% Lock Non-Vu]")
        pills.append(f"[WALLHACK: {wh_strict*100:.1f}% Lock Mur]")  # Compatibilité tests
    if wh_track >= cfg.wh_continuous_tracking:
        facteurs.append(f"Suivi occlus continu anormal ({wh_track} ticks)")
        if not any("Track" in c for c in cheats_detectes):
            cheats_detectes.append(f"INFO-ESP: Track {wh_track}t")
        pills.append(f"[INFO-ESP: Track {wh_track} ticks]")
        pills.append(f"[WALLHACK: Track {wh_track} ticks]")  # Compatibilité tests

    # Spinbot / Anti-Aim
    spin = profil_spin or {}
    spin_yaw = float(spin.get("spinbot_yaw_speed_max", 0))
    if spin_yaw > cfg.spinbot_yaw_speed_threshold or spin.get("spinbot_yaw_spin_windows", 0) > 0:
        facteurs.append(f"Rotation spinbot violente ({spin_yaw:.1f}°/tick)")
        cheats_detectes.append(f"SPINBOT: Spin {spin_yaw:.1f}°/tick")
        pills.append(f"[SPINBOT: Spin {spin_yaw:.1f}°/tick]")
    if spin.get("spinbot_pitch_violations", 0) > 0:
        facteurs.append("Pitch anti-aim hors limites Source 2")
        cheats_detectes.append("[ANTI-AIM: Pitch invalide]")
        pills.append("[ANTI-AIM: Pitch invalide]")
    if spin.get("spinbot_jitter_score", 0) > cfg.spinbot_jitter_variance:
        facteurs.append("Jitter anti-aim détecté")
        cheats_detectes.append("[ANTI-AIM: Jitter]")
        pills.append("[ANTI-AIM: Jitter]")
    if spin.get("spinbot_desync_max_ticks", 0) >= cfg.spinbot_desync_min_ticks:
        d_ticks = spin.get("spinbot_desync_max_ticks", 0)
        facteurs.append(f"Oscillation anti-aim ({d_ticks} flips)")
        cheats_detectes.append(f"[ANTI-AIM: Flip {d_ticks}t]")
        pills.append(f"[ANTI-AIM: Flip {d_ticks}t]")

    # Triggerbot
    tb = profil_trigger or {}
    shots = int(tb.get("triggerbot_total_shots_analyzed", 0))
    tb_rt = float(tb.get("triggerbot_rt_median", 999.0))
    tb_std = float(tb.get("triggerbot_rt_std", 999.0))
    if shots >= 3 and tb_rt < cfg.triggerbot_rt_median_threshold:
        facteurs.append(f"Temps de réaction inhumain triggerbot ({tb_rt:.1f}ms)")
        cheats_detectes.append(f"TRIGGERBOT: Réaction {tb_rt:.0f}ms")
        pills.append(f"[TRIGGERBOT: Réaction {tb_rt:.0f}ms]")
    if shots >= 3 and tb_std < cfg.triggerbot_rt_std_threshold:
        facteurs.append(f"Consistance de tir surhumaine (σ {tb_std:.1f}ms)")
        cheats_detectes.append(f"TRIGGERBOT: Régularité {tb_std:.0f}ms")
        pills.append(f"[TRIGGERBOT: Régularité {tb_std:.0f}ms]")
    if tb.get("triggerbot_burst_count", 0) >= 1:
        b_cnt = tb.get("triggerbot_burst_count", 0)
        facteurs.append(f"Rafales triggerbot instantanées ({b_cnt}x)")
        cheats_detectes.append(f"TRIGGERBOT: Burst x{b_cnt}")
        pills.append(f"[TRIGGERBOT: Burst x{b_cnt}]")

    # 4. Combinaison statistique propre (sans amplification arbitraire de +25%)
    # Si de multiples anomalies sont prouvées par des facteurs critiques, le score global reflète la certitude
    combined_score = ml_score
    if len(facteurs) >= 2 or any("SPINBOT" in c or "Pitch invalide" in c for c in cheats_detectes):
        combined_score = max(combined_score, 75.0)
    elif len(facteurs) == 1:
        combined_score = max(combined_score, 40.0)

    # 5. Détermination du verdict (terminologie prudente & non accusatrice)
    # Utiliser le seuil optimisé du bundle CS2CD s'il existe, sinon fallback config
    bundle_threshold = None
    if paquet_existant and isinstance(paquet_existant, dict):
        bundle_threshold = paquet_existant.get("threshold")

    if bundle_threshold is not None:
        seuil_cheater = float(bundle_threshold) * 100.0
        seuil_suspect = seuil_cheater * 0.5  # suspect = moitié du seuil optimisé
    else:
        seuil_cheater = cfg.ml_cheater_threshold * 100
        seuil_suspect = cfg.ml_suspect_threshold * 100

    has_rage = any("SPINBOT" in c or "Pitch invalide" in c for c in cheats_detectes)
    if has_rage or combined_score >= seuil_cheater or len(facteurs) >= cfg.ml_critical_factors_cheater:
        verdict = "SUSPICION ÉLEVÉE"
        statut = "high_suspicion"
    elif combined_score >= seuil_suspect or len(facteurs) >= cfg.ml_critical_factors_suspect:
        verdict = "SUSPECT"
        statut = "suspect"
    else:
        verdict = "LÉGITIME"
        statut = "clean"

    return {
        "joueur": nom_joueur,
        "ml_score": round(ml_score, 2),
        "anomaly_score": round(anomaly_score, 4),
        "probabilite_triche": round(combined_score, 2),
        "suspicion_score": round(combined_score, 2),
        "verdict": verdict,
        "statut": statut,
        "facteurs_suspects": facteurs,
        "cheats_detectes": cheats_detectes,
        "pills": pills,
        "profil_aim": profil_aim,
        "profil_bhop": profil_bhop,
        "profil_wh": profil_wh,
        "profil_spin": spin,
        "profil_trigger": tb,
    }


# === Compatibilité API Anglaise (engine EN & test suite) ===

FEATURE_NAMES = NOMS_FEATURES
extract_feature_vector = extraire_vecteur_features


@dataclass
class ClassificationResult:
    verdict: str  # CLEAN / SUSPECT / CHEATER
    suspicion_score: float
    display_verdict: str
    critical_factors: List[str] = field(default_factory=list)
    violation_flags: List[str] = field(default_factory=list)
    pills: List[str] = field(default_factory=list)

    @property
    def suspicion_scores(self):
        """Scores de suspicion (PAS des probabilités calibrées). Échelle 0-100."""
        score = max(0.0, min(100.0, self.suspicion_score))
        inverse = 100.0 - score
        return {
            "clean": inverse,
            "suspicion": score,
            "CLEAN": inverse,
            "SUSPECT": score if 35 <= score < 70 else 0,
            "HIGH_SUSPICION": score if score >= 70 else 0,
        }

    @property
    def probabilities(self):
        """Alias rétrocompatible — préférer suspicion_scores."""
        return self.suspicion_scores


class CheatClassifier:
    """Wrapper standard compatible avec tests.unit.test_ml et AntiCheatEngine."""

    def __init__(self, model_path: Optional[str] = None, model_type: str = "auto"):
        self.model_path = model_path
        self._bundle = charger_ou_entrainer_modele(chemin_modele=model_path, model_type=model_type)
        self.scaler = self._bundle["scaler"]
        self.model = self._bundle["modele"]
        self.feature_names = self._bundle.get("noms_features", NOMS_FEATURES)
        self._isolation = self._bundle.get("isolation_forest")
        self.dataset_name = self._bundle.get("dataset_name", "Unknown")
        self.is_loaded = True

    def predict(
        self,
        aim_metrics=None,
        bhop_metrics=None,
        wh_metrics=None,
        spinbot_metrics=None,
        triggerbot_metrics=None,
    ) -> ClassificationResult:
        aim = aim_metrics or {}
        bhop = bhop_metrics or {}
        wh = wh_metrics or {}
        spin = spinbot_metrics or {}
        tb = triggerbot_metrics or {}

        # Dictionnaires par défaut minimaux pour éviter les None
        aim_in = aim if aim else {"aim_snap_max": 0, "aim_jerk_max": 0, "aim_jerk_moyen": 0, "aim_vitesse_max": 0, "aim_ratio_micro_ajustements": 0, "aim_variance_vitesse": 0}
        bhop_in = bhop if bhop else {"bhop_total_sauts": 0, "bhop_ratio_parfaits": 0, "bhop_variance_sol": 50, "bhop_chaine_max": 0, "bhop_vitesse_moyenne": 0}
        wh_in = wh if wh else {"wh_ratio_lock_cache": 0, "wh_ratio_lock_strict": 0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0}

        res_fr = classifier_joueur(
            aim_in, bhop_in, wh_in,
            nom_joueur="Player",
            profil_spin=spin,
            profil_trigger=tb,
            paquet_existant=self._bundle,
        )

        score = float(res_fr.get("suspicion_score", 0.0))
        facteurs = res_fr.get("facteurs_suspects", [])
        pills = list(res_fr.get("pills", []))

        # Déterminer verdict EN pour compatibilité stricte des tests
        # Utiliser le seuil du bundle si disponible
        from src.core.config import get_config
        cfg = get_config()
        bundle_threshold = self._bundle.get("threshold") if isinstance(self._bundle, dict) else None
        if bundle_threshold is not None:
            seuil_high = float(bundle_threshold) * 100.0
            seuil_sus = seuil_high * 0.5
        else:
            seuil_high = cfg.ml_cheater_threshold * 100
            seuil_sus = cfg.ml_suspect_threshold * 100

        if score >= seuil_high or len(facteurs) >= 2 or any("SPINBOT" in p for p in pills):
            verdict_en = "CHEATER"
            display = f"🔴 CHEATER ({score:.1f}%)"
        elif score >= seuil_sus or len(facteurs) >= 1:
            verdict_en = "SUSPECT"
            display = f"🟡 SUSPECT ({score:.1f}%)"
        else:
            verdict_en = "CLEAN"
            display = f"🟢 CLEAN ({score:.1f}%)"

        return ClassificationResult(
            verdict=verdict_en,
            suspicion_score=score,
            display_verdict=display,
            critical_factors=facteurs,
            violation_flags=facteurs,
            pills=pills,
        )
