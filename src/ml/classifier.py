"""
CS2 Anti-Cheat — Features & Classification ML
Extraction de vecteurs de features et classification via le modèle pré-entraîné.
Refactoré depuis ia_advanced.py.
"""

import os

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

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

# Chemin du modèle : chercher à la racine du projet
_DIR_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FICHIER_MODELE = os.path.join(_DIR_RACINE, "cerveau_vac_cs2cd.pkl")


def extraire_vecteur_features(profil_aim, profil_bhop, profil_wh):
    """Convertit les dictionnaires de métriques en vecteur numérique ordonné."""
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
        # Init defaults (clean-like) avec rng pour reproductibilité
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
            snap_max = rng.uniform(15.0, 60.0)
            jerk_max = rng.uniform(25.0, 120.0)
            micro_adj = rng.uniform(0.0, 1.5) if rng.random() > 0.5 else rng.uniform(20.0, 50.0)
        elif type_cheat == "bhop":
            bhop_perf = rng.uniform(0.70, 1.0)
            bhop_var = rng.uniform(0.0, 1.2)
            bhop_chain = rng.integers(4, 15)
            bhop_spd = rng.uniform(260.0, 340.0)
        elif type_cheat == "wallhack":
            wh_lock = rng.uniform(0.28, 0.70)
            wh_strict = rng.uniform(0.12, 0.40)
            wh_track = rng.integers(25, 120)
        elif type_cheat == "rage":
            v_max = rng.uniform(80.0, 180.0)
            snap_max = rng.uniform(50.0, 150.0)
            jerk_max = rng.uniform(100.0, 300.0)
            bhop_perf = rng.uniform(0.8, 1.0)
            bhop_var = rng.uniform(0.0, 0.5)
            wh_lock = rng.uniform(0.4, 0.8)

        X.append([v_max, snap_max, jerk_mean, jerk_max, micro_adj, var_v,
                  sauts, bhop_perf, bhop_var, bhop_chain, bhop_spd,
                  wh_lock, wh_strict, wh_track, wh_dist])
        y.append(1)

    return np.array(X), np.array(y)


def entrainer_le_modele():
    """Entraîne et sauvegarde le package d'IA anti-cheat complet."""
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
    }

    joblib.dump(paquet_ia, FICHIER_MODELE)
    return paquet_ia


def charger_ou_entrainer_modele():
    """Charge le modèle existant ou l'entraîne s'il n'existe pas."""
    if os.path.exists(FICHIER_MODELE):
        try:
            # TRUST BOUNDARY (AUD-09): joblib.load exécute du code arbitraire (pickle).
            # NE CHARGER QUE DES MODÈLES LOCAUX DE CONFIANCE. Ne jamais charger un
            # modèle téléchargé ou fourni par un utilisateur sans vérifier sa signature
            # (HMAC / RSA) au préalable.
            paquet = joblib.load(FICHIER_MODELE)
            if isinstance(paquet, dict) and "modele" in paquet and "scaler" in paquet:
                return paquet
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")
    return entrainer_le_modele()


def classifier_joueur(
    profil_aim, profil_bhop, profil_wh,
    nom_joueur="Joueur",
    profil_spin=None,
    profil_trigger=None,
    paquet_existant=None
):
    """
    Évalue un joueur via le modèle ML et génère un diagnostic précis.
    Supporte les analyseurs Aimbot, Bhop, Wallhack, Spinbot et Triggerbot.
    Retourne un dictionnaire avec le verdict, la probabilité et les facteurs suspects.
    """
    if not profil_aim or not profil_bhop or not profil_wh:
        return None

    from src.core.config import get_config
    cfg = get_config()

    # AUD-08: Use injected bundle if provided, avoiding unnecessary reload
    paquet = paquet_existant or charger_ou_entrainer_modele()
    scaler = paquet["scaler"]
    modele = paquet["modele"]
    iso = paquet.get("isolation_forest")

    vecteur = extraire_vecteur_features(profil_aim, profil_bhop, profil_wh)
    vecteur_scaled = scaler.transform(vecteur.reshape(1, -1))

    proba_triche = float(modele.predict_proba(vecteur_scaled)[0][1] * 100)

    # Détection d'anomalie multidimensionnelle via IsolationForest
    if iso is not None:
        try:
            score_ano = float(iso.decision_function(vecteur_scaled)[0])
            if score_ano < -0.10:
                proba_triche = max(proba_triche, min(95.0, proba_triche + 25.0))
        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

    # Analyse des facteurs déclencheurs critiques
    facteurs = []
    cheats_detectes = []

    # Aimbot
    if profil_aim.get("aim_snap_max", 0) > cfg.aimbot_snap_threshold:
        facteurs.append(f"Snap instantané anormal ({profil_aim['aim_snap_max']:.1f}°/tick)")
        cheats_detectes.append(f"AIMBOT: Snap {profil_aim['aim_snap_max']:.1f}°/tick")
    if profil_aim.get("aim_snap_max", 0) > 15.0 and profil_aim.get("aim_jerk_max", 0) > cfg.aimbot_jerk_threshold:
        facteurs.append(f"À-coups mécaniques suspects ({profil_aim['aim_jerk_max']:.1f})")
        if "AIMBOT" not in str(cheats_detectes):
            cheats_detectes.append(f"AIMBOT: Jerk {profil_aim['aim_jerk_max']:.1f}")

    # BunnyHop
    if profil_bhop.get("bhop_ratio_parfaits", 0) > cfg.bhop_script_ratio and profil_bhop.get("bhop_total_sauts", 0) >= cfg.bhop_min_jumps_for_flag:
        facteurs.append(f"Bhop scripté ({profil_bhop['bhop_ratio_parfaits']*100:.1f}% parfaits)")
        cheats_detectes.append(f"BHOP: Script {profil_bhop['bhop_ratio_parfaits']*100:.0f}%")
    if profil_bhop.get("bhop_chaine_max", 0) >= cfg.bhop_chain_threshold and profil_bhop.get("bhop_ratio_parfaits", 0) > 0.40:
        facteurs.append(f"Chaîne de BunnyHop inhumaine ({profil_bhop['bhop_chaine_max']} consécutifs)")
        if "BHOP" not in str(cheats_detectes):
            cheats_detectes.append(f"BHOP: Chaîne {profil_bhop['bhop_chaine_max']}")

    # Wallhack
    if profil_wh.get("wh_ratio_lock_strict", 0) > 0.12 and profil_wh.get("wh_tracking_consecutif_max", 0) >= cfg.wh_tracking_threshold:
        facteurs.append(f"Alignement mur ({profil_wh['wh_ratio_lock_strict']*100:.1f}%)")
        cheats_detectes.append(f"WALLHACK: {profil_wh['wh_tracking_consecutif_max']} Locks")
    if profil_wh.get("wh_tracking_consecutif_max", 0) >= cfg.wh_continuous_tracking:
        facteurs.append(f"Suivi continu anormal ({profil_wh['wh_tracking_consecutif_max']} ticks)")
        if "WALLHACK" not in str(cheats_detectes):
            cheats_detectes.append(f"WALLHACK: Track {profil_wh['wh_tracking_consecutif_max']}t")

    # Spinbot / Anti-Aim
    spin = profil_spin or {}
    if spin.get("spinbot_yaw_speed_max", 0) > cfg.spinbot_yaw_speed_threshold or spin.get("spinbot_yaw_spin_windows", 0) > 0:
        val = spin.get("spinbot_yaw_speed_max", 0)
        facteurs.append(f"Rotation spinbot violente ({val:.1f}°/tick)")
        cheats_detectes.append(f"SPINBOT: Spin {val:.1f}°/tick")
    if spin.get("spinbot_pitch_violations", 0) > 0:
        facteurs.append("Pitch anti-aim hors limites Source 2")
        cheats_detectes.append("[ANTI-AIM: Pitch invalide]")
    if spin.get("spinbot_jitter_score", 0) > cfg.spinbot_jitter_variance:
        facteurs.append("Jitter anti-aim détecté")
        cheats_detectes.append("[ANTI-AIM: Jitter]")
    if spin.get("spinbot_desync_max_ticks", 0) >= cfg.spinbot_desync_min_ticks:
        d_ticks = spin.get("spinbot_desync_max_ticks", 0)
        facteurs.append(f"Oscillation anti-aim ({d_ticks} flips)")
        cheats_detectes.append(f"[ANTI-AIM: Flip {d_ticks}t]")

    # Triggerbot
    tb = profil_trigger or {}
    shots = tb.get("triggerbot_total_shots_analyzed", 0)
    if shots >= 3 and tb.get("triggerbot_rt_median", 999.0) < cfg.triggerbot_rt_median_threshold:
        rt_med = tb.get("triggerbot_rt_median", 0.0)
        facteurs.append(f"Temps de réaction inhumain triggerbot ({rt_med:.1f}ms)")
        cheats_detectes.append(f"TRIGGERBOT: Réaction {rt_med:.0f}ms")
    if shots >= 3 and tb.get("triggerbot_rt_std", 999.0) < cfg.triggerbot_rt_std_threshold:
        rt_std = tb.get("triggerbot_rt_std", 0.0)
        facteurs.append(f"Consistance de tir surhumaine (σ {rt_std:.1f}ms)")
        cheats_detectes.append(f"TRIGGERBOT: Régularité {rt_std:.0f}ms")
    if tb.get("triggerbot_burst_count", 0) >= 1:
        b_cnt = tb.get("triggerbot_burst_count", 0)
        facteurs.append(f"Rafales triggerbot instantanées ({b_cnt}x)")
        cheats_detectes.append(f"TRIGGERBOT: Burst x{b_cnt}")

    # Détermination du verdict
    has_rage = any("SPINBOT" in c or "Pitch invalide" in c for c in cheats_detectes)
    if has_rage or proba_triche >= (cfg.ml_cheater_threshold * 100) or len(facteurs) >= cfg.ml_critical_factors_cheater:
        verdict = "TRICHE AVÉRÉE"
        statut = "ban"
    elif proba_triche >= (cfg.ml_suspect_threshold * 100) or len(facteurs) >= cfg.ml_critical_factors_suspect:
        verdict = "SUSPECT"
        statut = "suspect"
    else:
        verdict = "LÉGITIME"
        statut = "clean"

    return {
        "joueur": nom_joueur,
        "probabilite_triche": round(proba_triche, 2),
        "verdict": verdict,
        "statut": statut,
        "facteurs_suspects": facteurs,
        "cheats_detectes": cheats_detectes,
        "profil_aim": profil_aim,
        "profil_bhop": profil_bhop,
        "profil_wh": profil_wh,
        "profil_spin": spin,
        "profil_trigger": tb,
    }


# === Compatibilité API Anglaise (tests EN + engine) ===
from dataclasses import dataclass, field
from typing import List

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
    def probabilities(self):
        # Compat tier3: {"clean": ..., "cheat"/"cheater": ...}
        cheat = max(0.0, min(100.0, self.suspicion_score))
        clean = 100.0 - cheat
        return {"clean": clean, "cheat": cheat, "suspect": cheat if 35 <= cheat < 70 else 0, "cheater": cheat if cheat >= 70 else 0, "CLEAN": clean, "CHEATER": cheat, "CHEAT": cheat}

class CheatClassifier:
    """Wrapper anglais compatible tests.unit.test_ml + engine."""
    def __init__(self, model_path: str = None):
        path = model_path or FICHIER_MODELE
        # Charger ou entraîner
        if path and os.path.exists(path):
            try:
                paquet = joblib.load(path)
                if isinstance(paquet, dict) and "modele" in paquet:
                    self._bundle = paquet
                else:
                    self._bundle = charger_ou_entrainer_modele()
            except Exception:
                self._bundle = charger_ou_entrainer_modele()
        else:
            self._bundle = charger_ou_entrainer_modele()
        self.scaler = self._bundle["scaler"]
        self.model = self._bundle["modele"]
        self.feature_names = self._bundle.get("noms_features", NOMS_FEATURES)
        self._isolation = self._bundle.get("isolation_forest")
        self.is_loaded = True

    def predict(
        self,
        aim_metrics=None,
        bhop_metrics=None,
        wh_metrics=None,
        spinbot_metrics=None,
        triggerbot_metrics=None
    ) -> ClassificationResult:
        aim = aim_metrics or {}
        bhop = bhop_metrics or {}
        wh = wh_metrics or {}
        spin = spinbot_metrics or {}
        tb = triggerbot_metrics or {}

        # Utiliser logique FR pour obtenir facteurs
        res_fr = classifier_joueur(
            aim if aim else {"aim_snap_max": 0, "aim_jerk_max": 0, "aim_jerk_moyen": 0, "aim_vitesse_max": 0, "aim_ratio_micro_ajustements": 0, "aim_variance_vitesse": 0},
            bhop if bhop else {"bhop_total_sauts": 0, "bhop_ratio_parfaits": 0, "bhop_variance_sol": 50, "bhop_chaine_max": 0, "bhop_vitesse_moyenne": 0},
            wh if wh else {"wh_ratio_lock_cache": 0, "wh_ratio_lock_strict": 0, "wh_tracking_consecutif_max": 0, "wh_distance_moyenne_verrous": 0},
            nom_joueur="Player",
            profil_spin=spin,
            profil_trigger=tb,
            paquet_existant=self._bundle
        )
        if res_fr is None:
            res_fr = {"probabilite_triche": 0, "verdict": "LÉGITIME", "facteurs_suspects": [], "cheats_detectes": []}
        score = float(res_fr.get("probabilite_triche", 0))
        verdict_fr = res_fr.get("verdict", "LÉGITIME")

        # Mapper verdict FR -> EN
        if "TRICHE" in verdict_fr or verdict_fr == "CHEATER":
            verdict_en = "CHEATER"
            display = f"🔴 TRICHEUR AVÉRÉ ({score:.1f}%)"
        elif "SUSPECT" in verdict_fr:
            verdict_en = "SUSPECT"
            display = f"🟡 SUSPECT ({score:.1f}%)"
        else:
            verdict_en = "CLEAN"
            display = f"🟢 LÉGITIME ({score:.1f}%)"

        facteurs = res_fr.get("facteurs_suspects", [])
        cheats = res_fr.get("cheats_detectes", [])

        # Générer pills attendus
        pills = []
        # Snap
        snap = float(aim.get("aim_snap_max", 0))
        if snap > 18.0:
            pills.append(f"[AIMBOT: Snap {snap:.1f}°/tick]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        # Jerk
        jerk = float(aim.get("aim_jerk_max", 0))
        if jerk > 35.0:
            pills.append(f"[AIMBOT: Jerk {jerk:.1f}]")
            if snap > 15.0 and jerk > 40.0 and verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        # Bhop script
        bhop_ratio = float(bhop.get("bhop_ratio_parfaits", 0))
        bhop_total = int(bhop.get("bhop_total_sauts", 0))
        if bhop_ratio > 0.60 and bhop_total >= 15:
            pills.append(f"[BHOP: Script {bhop_ratio*100:.0f}%]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        # Bhop chain
        chain = int(bhop.get("bhop_chaine_max", 0))
        if chain >= 4:
            pills.append(f"[BHOP: Chaîne x{chain}]")
            if chain >= 6 and bhop_ratio > 0.40 and verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        # Wallhack lock (AUD-05: Renamed to avoid claiming through-wall without geometry)
        wh_strict = float(wh.get("wh_ratio_lock_strict", 0))
        wh_track = int(wh.get("wh_tracking_consecutif_max", 0))
        if wh_strict > 0.15 and wh_track >= 80:
            pills.append(f"[INFO-ESP: {wh_strict*100:.1f}% Lock Non-Vu]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        if wh_track >= 180:
            pills.append(f"[INFO-ESP: Track {wh_track} ticks]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"

        # Spinbot pills
        spin_yaw = float(spin.get("spinbot_yaw_speed_max", 0))
        if spin_yaw > 90.0 or spin.get("spinbot_yaw_spin_windows", 0) > 0:
            pills.append(f"[SPINBOT: Spin {spin_yaw:.1f}°/tick]")
            verdict_en = "CHEATER"
        if spin.get("spinbot_pitch_violations", 0) > 0:
            pills.append("[ANTI-AIM: Pitch invalide]")
            verdict_en = "CHEATER"
        if spin.get("spinbot_jitter_score", 0) > 2000.0:
            pills.append("[ANTI-AIM: Jitter]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        if spin.get("spinbot_desync_max_ticks", 0) >= 6:
            pills.append(f"[ANTI-AIM: Flip {spin.get('spinbot_desync_max_ticks', 0)}t]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"

        # Triggerbot pills
        tb_shots = int(tb.get("triggerbot_total_shots_analyzed", 0))
        tb_rt = float(tb.get("triggerbot_rt_median", 999.0))
        if tb_shots >= 3 and tb_rt < 50.0:
            pills.append(f"[TRIGGERBOT: Réaction {tb_rt:.0f}ms]")
            verdict_en = "CHEATER"
        elif tb_shots >= 3 and float(tb.get("triggerbot_rt_std", 999.0)) < 15.0:
            pills.append(f"[TRIGGERBOT: Régularité {tb.get('triggerbot_rt_std', 0):.0f}ms]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"
        if tb.get("triggerbot_burst_count", 0) >= 1:
            pills.append(f"[TRIGGERBOT: Burst x{tb.get('triggerbot_burst_count', 0)}]")
            if verdict_en == "CLEAN":
                verdict_en = "SUSPECT"

        # Si cheats FR génère des pills non capturés, les ajouter
        for c in cheats:
            pill_fmt = f"[{c}]" if not c.startswith("[") else c
            if pill_fmt not in pills and c not in pills:
                pills.append(pill_fmt)

        # Re-évaluer display si verdict a changé via règles
        if verdict_en == "CHEATER":
            display = f"🔴 TRICHEUR AVÉRÉ ({score:.1f}%)"
        elif verdict_en == "SUSPECT" and "🟢" in display:
            display = f"🟡 SUSPECT ({score:.1f}%)"

        return ClassificationResult(
            verdict=verdict_en,
            suspicion_score=score,
            display_verdict=display,
            critical_factors=facteurs,
            violation_flags=facteurs,
            pills=pills,
        )

