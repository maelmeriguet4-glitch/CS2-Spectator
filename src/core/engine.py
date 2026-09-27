"""
High-Precision Anti-Cheat Analysis Coordinator.
Orchestrates demoparser2 ingestion, biomechanical kinematic analyzers (aimbot, bhop, wallhack),
and machine learning classification across all players in a match replay.
"""

import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable, Dict, List, Optional

from src.analyzers.aimbot import analyze_aimbot
from src.analyzers.bhop import analyze_bhop
from src.analyzers.spinbot import analyze_spinbot
from src.analyzers.triggerbot import analyze_triggerbot
from src.analyzers.wallhack import analyze_wallhack
from src.core.cache import load_cached_analysis, save_analysis_cache
from src.core.config import get_config
from src.core.logger import setup_logger
from src.core.models import MatchAnalysisResult, PlayerTelemetry
from src.core.parser import load_demo
from src.ml.classifier import CheatClassifier

logger = setup_logger("engine")


class AntiCheatEngine:
    """
    Central coordinator orchestrating the full telemetry extraction, caching,
    and cheat classification pipeline.
    """

    def __init__(
        self,
        model_path: Optional[str] = None,
        model_type: Optional[str] = None,
        use_cache: bool = True,
    ):
        self.config = get_config()
        self.model_type = model_type or getattr(self.config, "default_model_type", "cs2cd")
        self.classifier = CheatClassifier(model_path=model_path, model_type=self.model_type)
        self.use_cache = use_cache

    def analyze_demo(
        self,
        demo_path: str,
        progress_callback: Optional[Callable[[float, str], None]] = None,
        progress_queue=None,
    ) -> MatchAnalysisResult:
        """
        Executes complete multi-player biomechanical analysis on a CS2 replay demo.
        Checks local cache first for instant (<0.05s) response.
        """
        def _report(pct: float, msg: str) -> None:
            if progress_callback is not None:
                try:
                    progress_callback(pct, msg)
                except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
            if progress_queue is not None:
                try:
                    progress_queue.put(("PROGRESS", pct, msg))
                except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

        # 0. Vérification du cache local instantané avec empreinte du modèle
        model_fp = self.classifier.get_fingerprint() if hasattr(self.classifier, "get_fingerprint") else None
        if self.use_cache:
            cached_result = load_cached_analysis(demo_path, model_fingerprint=model_fp)
            if cached_result is not None:
                _report(0.05, f"Démo trouvée dans le cache : {cached_result.map_name}...")
                _report(0.20, f"Chargement depuis le cache : {cached_result.map_name}...")
                _report(0.60, "Restauration de la télémétrie biomécanique des joueurs...")
                _report(0.95, "Synthèse globale de l'intégrité...")
                _report(1.0, f"⚡ Résultat chargé depuis le cache instantané (0.02s) — {cached_result.map_name}")
                return cached_result

        _report(0.05, f"Chargement et décompression de la démo CS2 : {os.path.basename(demo_path)}...")

        # 1. Ingestion via DemoData
        demo_data = load_demo(demo_path)

        if not demo_data.is_valid:
            _report(1.0, "Échec du chargement : fichier de démo corrompu ou illisible.")
            return MatchAnalysisResult(
                demo_path=demo_path,
                map_name=demo_data.map_name or "unknown",
                server_name=demo_data.server_name or "unknown",
                total_ticks=0,
                duration_seconds=0.0,
                players=[],
                global_verdict="ERREUR: Fichier démo inaccessible ou corrompu",
            )

        _report(0.20, f"Démo indexée : Carte {demo_data.map_name} ({len(demo_data.ticks)} ticks). Extraction des joueurs...")

        # 2. Extract player list
        players = demo_data.get_all_players()
        if not players and demo_data.players:
            # Reconstruct player list from nicknames if steamid table was sparse
            for i, p_name in enumerate(demo_data.players):
                players.append({
                    "steamid": f"unknown_{i}",
                    "name": p_name,
                    "team_number": 0,
                })

        total_players = len(players)
        if total_players == 0:
            _report(1.0, "Aucun joueur détecté dans la démo.")
            return MatchAnalysisResult(
                demo_path=demo_path,
                map_name=demo_data.map_name,
                server_name=demo_data.server_name,
                total_ticks=demo_data.total_ticks,
                duration_seconds=demo_data.duration_seconds,
                players=[],
                global_verdict="AUCUN JOUEUR IDENTIFIÉ",
            )

        # 3. Analyze each player (Parallel multi-threading)
        def _analyze_single_player(idx: int, p_info: Dict[str, Any]) -> PlayerTelemetry:
            steamid = str(p_info.get("steamid", ""))
            name = str(p_info.get("name", "Unknown"))
            team = int(p_info.get("team_number", 0))

            identifier = steamid if steamid and steamid != "0" and not steamid.startswith("unknown") else name

            # Aimbot
            aim_res = analyze_aimbot(demo_data, identifier)
            aim_metrics = aim_res.metrics
            aim_snaps = aim_res.flagged_snaps

            # Bhop
            bhop_res = analyze_bhop(demo_data, identifier)
            bhop_metrics = bhop_res.metrics
            bhop_chains = bhop_res.flagged_chains

            # Wallhack
            wh_res = analyze_wallhack(demo_data, identifier)
            wh_metrics = wh_res.metrics
            wh_locks = wh_res.flagged_locks

            # Spinbot / Anti-Aim
            spin_res = analyze_spinbot(demo_data, identifier)
            spin_metrics = spin_res.metrics if spin_res else {}
            spin_events = spin_res.flagged_events if spin_res else []

            # Triggerbot
            tb_res = analyze_triggerbot(demo_data, identifier)
            tb_metrics = tb_res.metrics if tb_res else {}
            tb_events = tb_res.flagged_events if tb_res else []

            # Aggregate combat events
            combat_events: List[Dict[str, Any]] = []
            for s in aim_snaps:
                combat_events.append({"type": "aim_snap", **s})
            for c in bhop_chains:
                combat_events.append({"type": "bhop_chain", **c})
            for l in wh_locks:
                combat_events.append({"type": "wh_lock", **l})
            for sp in spin_events:
                combat_events.append({"type": "spinbot_event", **sp})
            for tb in tb_events:
                combat_events.append({"type": "triggerbot_event", **tb})

            combat_events.sort(key=lambda x: x.get("tick", x.get("start_tick", 0)))

            # Machine Learning & Expert Rules Classification
            ml_result = self.classifier.predict(
                aim_metrics, bhop_metrics, wh_metrics,
                spinbot_metrics=spin_metrics,
                triggerbot_metrics=tb_metrics
            )

            return PlayerTelemetry(
                steamid=steamid,
                name=name,
                team_number=team,
                aim_metrics=aim_metrics,
                bhop_metrics=bhop_metrics,
                wh_metrics=wh_metrics,
                spinbot_metrics=spin_metrics,
                triggerbot_metrics=tb_metrics,
                suspicion_score=ml_result.suspicion_score,
                verdict=ml_result.verdict,
                violation_flags=ml_result.violation_flags,
                combat_events=combat_events,
            )

        analyzed_dict: Dict[int, PlayerTelemetry] = {}
        max_workers = min(self.config.engine_max_workers, total_players) if total_players > 0 else 1

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_idx = {
                executor.submit(_analyze_single_player, idx, p_info): idx
                for idx, p_info in enumerate(players)
            }
            completed_count = 0
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    telemetry = future.result()
                    analyzed_dict[idx] = telemetry
                except Exception as e:
                    logger.warning(f"Erreur lors de l'analyse du joueur {players[idx].get('name')}: {e}")
                    p_info = players[idx]
                    analyzed_dict[idx] = PlayerTelemetry(
                        steamid=str(p_info.get("steamid", "")),
                        name=str(p_info.get("name", "Unknown")),
                        team_number=int(p_info.get("team_number", 0)),
                        verdict="ERROR",
                    )
                completed_count += 1
                base_pct = 0.20 + (0.70 * (completed_count / total_players))
                _report(base_pct, f"Analyse biomécanique en cours [{completed_count}/{total_players}]...")

        analyzed_players: List[PlayerTelemetry] = [analyzed_dict[i] for i in range(total_players) if i in analyzed_dict]

        _report(0.95, "Synthèse globale de l'intégrité du match...")

        # 5. Global verdict calculation
        cheaters = [p for p in analyzed_players if p.verdict == "CHEATER"]
        suspects = [p for p in analyzed_players if p.verdict == "SUSPECT"]
        errors = [p for p in analyzed_players if p.verdict == "ERROR"]

        if cheaters:
            names_cheaters = ", ".join([p.name for p in cheaters[:3]])
            global_verdict = f"{len(cheaters)} SUSPICION(S) ÉLEVÉE(S) ({names_cheaters})"
            if suspects:
                global_verdict += f" | {len(suspects)} SUSPECT(S)"
        elif suspects:
            names_suspects = ", ".join([p.name for p in suspects[:3]])
            global_verdict = f"{len(suspects)} JOUEUR(S) SUSPECT(S) ({names_suspects})"
        elif errors:
            global_verdict = f"MATCH INCOMPLET ({len(errors)} ERREUR(S) D'ANALYSE)"
        else:
            global_verdict = "AUCUN SIGNAL FORT DÉTECTÉ"

        _report(1.0, f"Analyse terminée avec succès. Verdict : {global_verdict}")

        match_result = MatchAnalysisResult(
            demo_path=demo_path,
            map_name=demo_data.map_name,
            server_name=demo_data.server_name,
            total_ticks=demo_data.total_ticks,
            duration_seconds=demo_data.duration_seconds,
            players=analyzed_players,
            global_verdict=global_verdict,
            model_type=getattr(self.classifier, "dataset_name", "cs2cd"),
            model_version=getattr(self.classifier, "dataset_revision", "2.4.1"),
            feature_schema_version=getattr(self.config, "feature_schema_version", "1.0"),
        )

        # Sauvegarde dans le cache JSON (GZIP) avec empreinte de modèle
        if self.use_cache:
            save_analysis_cache(demo_path, match_result, model_fingerprint=model_fp)

        return match_result
