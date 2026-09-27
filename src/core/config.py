"""
CS2 Anti-Cheat — Configuration Centralisée
Tous les seuils de détection, paramètres ML et limites moteur.
Version moteur utilisée pour l'invalidation du cache.
"""

from dataclasses import dataclass

ENGINE_VERSION = "3.1.0"

@dataclass
class AnalysisConfig:
    """Configuration globale du moteur anti-triche. Tous les seuils sont ici."""
    
    # === Aimbot ===
    aimbot_snap_threshold: float = 18.0          # °/tick - seuil de snap instantané
    aimbot_jerk_threshold: float = 45.0          # seuil de jerk angulaire (à-coups)
    aimbot_firing_window_before: int = 5         # ticks avant weapon_fire
    aimbot_firing_window_after: int = 10         # ticks après weapon_fire
    aimbot_micro_adj_threshold: float = 0.05     # ° minimum pour compter comme micro-ajustement
    aimbot_min_ticks: int = 20                   # minimum de ticks pour analyser
    aimbot_fov_lock_angle: float = 5.0           # ° - angle FOV lock sur cible
    aimbot_fov_lock_min_ticks: int = 10          # ticks minimum de lock continu
    aimbot_smoothing_degree: int = 3             # degré polynomial pour smoothing curve
    
    # === BunnyHop ===
    bhop_perfect_tick_max: int = 1               # ticks max au sol pour jump "parfait"
    bhop_script_ratio: float = 0.55              # ratio parfaits pour flag script
    bhop_min_jumps_for_flag: int = 12            # minimum de sauts pour flag script
    bhop_chain_threshold: int = 6                # chaîne max pour flag (6+ consécutifs)
    bhop_min_ticks: int = 50                     # minimum de ticks pour analyser
    bhop_autostrafe_threshold: float = 0.85      # corrélation yaw-velocity pour autostrafe
    bhop_velocity_cap: float = 300.0             # u/s limite moteur Source 2
    
    # === Wallhack ===
    wh_strict_angle: float = 2.5                 # ° angle strict lock
    wh_wide_angle: float = 5.0                   # ° angle large lock
    wh_distance_min: float = 200.0               # units min pour analyse
    wh_distance_max: float = 2000.0              # units max pour analyse
    wh_tracking_threshold: int = 90              # ticks tracking pour flag
    wh_continuous_tracking: int = 180            # ticks tracking continu
    wh_motion_yaw_threshold: float = 0.1         # ° mouvement yaw minimum
    wh_motion_pos_threshold: float = 1.0         # units mouvement position minimum
    wh_preaim_window_before: float = 2.0         # secondes avant contact visuel pour pre-aim
    wh_preaim_angle_threshold: float = 10.0      # ° angle de pre-aim
    
    # === Spinbot / Anti-Aim ===
    spinbot_yaw_speed_threshold: float = 90.0    # °/tick - vitesse yaw continue
    spinbot_pitch_limit: float = 89.5            # ° pitch hors bornes Source 2
    spinbot_jitter_variance: float = 2000.0      # variance pitch pour jitter
    spinbot_desync_angle: float = 140.0          # ° oscillation anti-aim
    spinbot_desync_min_ticks: int = 6            # ticks minimum oscillation 180° continue
    spinbot_window_size: int = 16                # taille fenêtre glissante
    spinbot_jitter_window: int = 8               # taille fenêtre jitter
    
    # === Triggerbot ===
    triggerbot_rt_median_threshold: float = 50.0  # ms - temps réaction médiane
    triggerbot_rt_std_threshold: float = 15.0     # ms - écart-type trop bas
    triggerbot_burst_rt: float = 30.0             # ms - tirs rafale instantanés
    triggerbot_burst_min_count: int = 3           # nombre minimum de burst
    triggerbot_hitbox_radius: float = 16.0        # units - approximation sphérique hitbox
    triggerbot_tickrate: float = 64.0             # tickrate du serveur
    
    # === ML / Classifier ===
    default_model_type: str = "cs2cd"            # "cs2cd" (production) ou "synthetic" (baseline/dev)
    feature_schema_version: str = "1.0"          # version canonique du schéma des 15 features
    ml_suspect_threshold: float = 0.60           # probabilité ML pour SUSPECT (60%)
    ml_cheater_threshold: float = 0.80           # probabilité ML pour CHEATER (80%)
    ml_n_estimators: int = 200                   # arbres Random Forest
    ml_max_depth: int = 12                       # profondeur max RF
    ml_critical_factors_cheater: int = 2          # facteurs critiques pour CHEATER
    ml_critical_factors_suspect: int = 1          # facteurs critiques pour SUSPECT
    ml_isolation_contamination: float = 0.03     # contamination IsolationForest
    
    # === Engine ===
    engine_max_workers: int = 4                  # threads parallèles max
    engine_version: str = ENGINE_VERSION         # version pour invalidation cache
    
    # === Cache ===
    cache_max_entries: int = 500                 # limite LRU cache SQLite
    
    # === Watcher ===
    watcher_poll_interval: float = 0.1           # secondes entre checks
    watcher_stability_checks: int = 2            # nombre de checks stabilité
    watcher_timeout: float = 2.0                 # secondes timeout écriture
    watcher_min_size: int = 8                    # bytes taille minimum demo


# Instance globale singleton
_config = AnalysisConfig()

def get_config() -> AnalysisConfig:
    """Retourne la configuration globale du moteur."""
    return _config

def set_config(config: AnalysisConfig) -> None:
    """Remplace la configuration globale."""
    global _config
    _config = config
