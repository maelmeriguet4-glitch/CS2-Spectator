"""
Reporting Wizard and Telemetry Proof Generator for CS2 Anti-Cheat.
Compiles quantitative biomechanical evidence and formats dual reports
tailored for Steam Community/In-Game reports and Faceit Support Tickets.
"""

import os
from typing import Any, Dict, List, Optional, Union

from src.core.models import MatchAnalysisResult, PlayerTelemetry, ReplayInfo

QCM_OPTIONS: List[str] = [
    "Visée anormale à travers les fumigènes / murs (Pre-aiming & Wallhack)",
    "Snaps instantanés et verrouillage de tête latence alignement (Aimbot / Silent Aim)",
    "Compensations de recul parfaites sans dispersion (No-Recoil / Macro)",
    "Sauts parfaits 1-tick en chaîne et prises de vitesse (Bunnyhop Script)",
    "Prises d'informations impossibles et pré-tirs systématiques (Radar / ESP)",
    "Mouvement de caméra désynchronisé / toupie (Anti-Aim / Spinbot)",
]


class ReportGenerator:
    """
    Utility class generating Steam and Faceit report templates,
    telemetry proof summaries, and external profile URLs.
    """

    QCM_OPTIONS: List[str] = QCM_OPTIONS

    @staticmethod
    def get_steam_profile_url(steamid: str) -> str:
        """
        Generates official Steam Community profile URL for given SteamID64.
        Handles edge cases such as BOT identifiers and invalid/empty IDs gracefully.
        """
        sid = str(steamid).strip() if steamid is not None else ""
        return f"https://steamcommunity.com/profiles/{sid}"

    @staticmethod
    def get_faceit_url(steamid: str) -> str:
        """
        Generates FaceitFinder URL for given SteamID64.
        Allows instant inspection of Faceit profile, Elo rating, and match rooms.
        """
        sid = str(steamid).strip() if steamid is not None else ""
        return f"https://faceitfinder.com/profile/{sid}"

    @staticmethod
    def _extract_replay_context(
        demo_info: Optional[Union[ReplayInfo, MatchAnalysisResult]] = None
    ) -> Dict[str, str]:
        """Extracts sanitized map name and demo filename from demo_info or MatchAnalysisResult."""
        if demo_info is None:
            return {"map_name": "N/A", "demo_filename": "N/A", "server_name": "N/A"}

        map_name = getattr(demo_info, "map_name", None) or "Inconnue"
        server_name = getattr(demo_info, "server_name", None) or "Serveur Inconnu"

        demo_filename = getattr(demo_info, "file_name", None)
        if not demo_filename:
            demo_path = getattr(demo_info, "demo_path", None) or getattr(demo_info, "file_path", None)
            if demo_path:
                demo_filename = os.path.basename(demo_path)
        demo_filename = demo_filename or "demo_inconnue.dem"

        return {
            "map_name": str(map_name),
            "demo_filename": str(demo_filename),
            "server_name": str(server_name),
        }

    @staticmethod
    def _extract_numeric_metrics(player: PlayerTelemetry) -> Dict[str, Any]:
        """Extracts and normalizes biomechanical metrics from player telemetry."""
        aim = player.aim_metrics or {}
        bhop = player.bhop_metrics or {}
        wh = player.wh_metrics or {}

        # Aim metrics
        aim_p99 = float(aim.get("aim_p99", 0.0))
        aim_jerk_max = float(aim.get("aim_jerk_max", 0.0))
        aim_jerk_moyen = float(aim.get("aim_jerk_moyen", 0.0))
        aim_vitesse_max = float(aim.get("aim_vitesse_max", 0.0))

        # Bhop metrics (handle ratio as 0.0-1.0 or 0-100)
        bhop_ratio_val = float(bhop.get("bhop_ratio_parfaits", 0.0))
        bhop_ratio = bhop_ratio_val * 100.0 if 0.0 < bhop_ratio_val <= 1.0 else bhop_ratio_val
        bhop_total = int(bhop.get("bhop_total_sauts", 0))
        bhop_chain = int(bhop.get("bhop_chaine_max", 0))
        bhop_spd = float(bhop.get("bhop_vitesse_moyenne", 0.0))

        # Wallhack metrics (handle ratios as 0.0-1.0 or 0-100)
        wh_strict_val = float(wh.get("wh_ratio_lock_strict", 0.0))
        wh_lock_strict = wh_strict_val * 100.0 if 0.0 < wh_strict_val <= 1.0 else wh_strict_val
        wh_cache_val = float(wh.get("wh_ratio_lock_cache", 0.0))
        wh_lock_cache = wh_cache_val * 100.0 if 0.0 < wh_cache_val <= 1.0 else wh_cache_val
        wh_track_max = int(wh.get("wh_tracking_consecutif_max", 0))
        wh_dist_avg = float(wh.get("wh_distance_moyenne_verrous", 0.0))

        return {
            "aim_p99": aim_p99,
            "aim_jerk_max": aim_jerk_max,
            "aim_jerk_moyen": aim_jerk_moyen,
            "aim_vitesse_max": aim_vitesse_max,
            "bhop_ratio": bhop_ratio,
            "bhop_total": bhop_total,
            "bhop_chain": bhop_chain,
            "bhop_spd": bhop_spd,
            "wh_lock_strict": wh_lock_strict,
            "wh_lock_cache": wh_lock_cache,
            "wh_track_max": wh_track_max,
            "wh_dist_avg": wh_dist_avg,
        }

    @classmethod
    def compile_telemetry_proof(
        cls,
        player: PlayerTelemetry,
        demo_info: Optional[Union[ReplayInfo, MatchAnalysisResult]] = None,
    ) -> str:
        """
        Compiles objective, quantitative telemetry proof extracted from Source 2 demo ticks:
        tick indices, angular snap velocities, jerk index, bhop chains, wall locks, and SteamID64.
        """
        ctx = cls._extract_replay_context(demo_info)
        m = cls._extract_numeric_metrics(player)

        lines = [
            f"=== DOSSIER DE PREUVES TÉLÉMÉTRIQUES // {player.name} ===",
            f"Joueur suspecté : {player.name}",
            f"SteamID64 : {player.steamid}",
            f"Verdict IA : {player.verdict} (Score de suspicion : {player.suspicion_score:.1f}%)",
            f"Contexte : Carte {ctx['map_name']} | Démo : {ctx['demo_filename']}",
            "",
            "1. CINÉTIQUE DE VISÉE (AIMBOT TELEMETRY) :",
            f"  • Vitesse angulaire max (Snap) : {m['aim_p99']:.1f}°/tick [Humain réf. 10-15°/tick]",
            f"  • Vitesse angulaire brute max  : {m['aim_vitesse_max']:.1f}°/s",
            f"  • Jerk angulaire max           : {m['aim_jerk_max']:.1f} (Moyen : {m['aim_jerk_moyen']:.1f})",
            "",
            "2. CINÉTIQUE DE DÉPLACEMENT (BUNNYHOP TELEMETRY) :",
            f"  • Ratio de sauts 1-tick au sol : {m['bhop_ratio']:.1f}% sur {m['bhop_total']} sauts",
            f"  • Chaîne maximale de sauts     : {m['bhop_chain']} sauts consécutifs",
            f"  • Vitesse moyenne en l'air     : {m['bhop_spd']:.1f} u/s",
            "",
            "3. ALIGNEMENT GÉOMÉTRIQUE 3D (WALLHACK / ESP TELEMETRY) :",
            f"  • Lock strict à travers murs   : {m['wh_lock_strict']:.1f}% des ticks ennemis masqués",
            f"  • Lock étendu à travers murs   : {m['wh_lock_cache']:.1f}%",
            f"  • Suivi dynamique continu max  : {m['wh_track_max']} ticks consécutifs",
            f"  • Distance moyenne des verrous : {m['wh_dist_avg']:.1f} unités Source 2",
        ]

        # Detailed event logs (up to 6 events)
        if player.combat_events:
            lines.append("")
            lines.append("4. EXTRAITS DES TICKS INCIDENTS RÉPERTORIÉS :")
            for ev in player.combat_events[:8]:
                ev_type = ev.get("type", "")
                if ev_type == "aim_snap":
                    tick = ev.get("tick", "N/A")
                    snap = ev.get("snap_angle", 0.0)
                    jerk = ev.get("jerk", 0.0)
                    wpn = ev.get("weapon", "inconnu")
                    lines.append(f"  - [Tick {tick}] SNAP DE VISÉE : {snap:.1f}°/tick (Jerk: {jerk:.1f}, Arme: {wpn})")
                elif ev_type == "bhop_chain":
                    st = ev.get("start_tick", "N/A")
                    et = ev.get("end_tick", "N/A")
                    cl = ev.get("chain_length", 0)
                    spd = ev.get("avg_speed", 0.0)
                    lines.append(f"  - [Ticks {st}-{et}] ENCHAÎNEMENT BHOP : {cl} sauts parfaits (Vitesse: {spd:.1f} u/s)")
                elif ev_type == "wh_lock":
                    st = ev.get("start_tick", "N/A")
                    et = ev.get("end_tick", "N/A")
                    dur = ev.get("duration_ticks", 0)
                    target = ev.get("target_name", "Ennemi")
                    dist = ev.get("distance", 0.0)
                    lines.append(f"  - [Ticks {st}-{et}] LOCK GÉOMÉTRIE : Suivi de {target} ({dur} ticks, {dist:.1f} u)")
                else:
                    lines.append(f"  - Événement suspect : {ev}")
        else:
            lines.append("")
            lines.append("4. ÉVÉNEMENTS SPÉCIFIQUES : Aucun micro-incident isolé.")

        return "\n".join(lines)

    @classmethod
    def generate_steam_report(
        cls,
        player: PlayerTelemetry,
        qcm_options: List[str],
        comments: str = "",
        demo_info: Optional[Union[ReplayInfo, MatchAnalysisResult]] = None,
    ) -> str:
        """
        Generates a structured, authoritative report formatted for Steam In-Game
        and Steam Community ticket submissions.
        """
        ctx = cls._extract_replay_context(demo_info)
        m = cls._extract_numeric_metrics(player)
        steam_url = cls.get_steam_profile_url(player.steamid)

        # Violation flags formatting
        if player.violation_flags:
            flags_text = "\n".join([f"  • {flag}" for flag in player.violation_flags])
        else:
            flags_text = "  • Aucune anomalie critique automatique (Comportement intègre)"

        # QCM observations formatting
        if qcm_options:
            qcm_text = "\n".join([f"• {opt}" for opt in qcm_options])
        else:
            qcm_text = "• Aucune observation manuelle sélectionnée"

        # User notes formatting
        clean_comments = comments.strip() if comments else "Aucun commentaire additionnel fourni."

        # Incident ticks preview
        incident_lines = []
        if player.combat_events:
            for ev in player.combat_events[:5]:
                ev_type = ev.get("type", "")
                if ev_type == "aim_snap":
                    incident_lines.append(f"  - Tick {ev.get('tick')}: Snap {ev.get('snap_angle', 0.0):.1f}°/tick [{ev.get('weapon', 'unknown')}]")
                elif ev_type == "bhop_chain":
                    incident_lines.append(f"  - Ticks {ev.get('start_tick')}-{ev.get('end_tick')}: Chaîne de {ev.get('chain_length')} sauts 1-tick")
                elif ev_type == "wh_lock":
                    incident_lines.append(f"  - Ticks {ev.get('start_tick')}-{ev.get('end_tick')}: Suivi masqué de {ev.get('target_name', 'target')} ({ev.get('duration_ticks')} ticks)")

        incident_section = ""
        if incident_lines:
            incident_section = "\nINCIDENTS MARQUANTS RÉPERTORIÉS :\n" + "\n".join(incident_lines)

        report = f"""[RAPPORT D'INTÉGRITÉ CS2 - AUDIT BIOMÉCANIQUE OFFICIEL]
Joueur suspecté : {player.name}
SteamID64 : {player.steamid}
Profil Steam : {steam_url}
Match / Carte : {ctx['map_name']} | Démo : {ctx['demo_filename']}

DIAGNOSTIC MOTEUR ANTI-CHEAT :
• Indice de suspicion IA : {player.suspicion_score:.1f}% [{player.verdict}]
• Facteurs anormaux détectés :
{flags_text}

OBSERVATIONS EN MATCH :
{qcm_text}

PREUVES TÉLÉMÉTRIQUES OBJECTIVES (Source 2 DemoParser) :
- Vitesse angulaire max (Snap) : {m['aim_p99']:.1f}°/tick (Seuil humain : 10-15°/tick)
- À-coups mécaniques (Jerk max) : {m['aim_jerk_max']:.1f}
- Ratio de BunnyHop parfait 1-tick : {m['bhop_ratio']:.1f}% sur {m['bhop_total']} sauts (Chaîne max : {m['bhop_chain']})
- Lock de visée à travers les murs (alignement cible non visible) : {m['wh_lock_strict']:.1f}% du temps caché
- Suivi continu à travers géométrie : {m['wh_track_max']} ticks consécutifs{incident_section}

Commentaires de l'auditeur :
{clean_comments}

Généré via CS2 Tactical Replay Auditor (Local Biomechanical Analysis)."""

        return report

    @classmethod
    def generate_faceit_report(
        cls,
        player: PlayerTelemetry,
        qcm_options: List[str],
        comments: str = "",
        demo_info: Optional[Union[ReplayInfo, MatchAnalysisResult]] = None,
    ) -> str:
        """
        Generates a concise, high-credibility ticket formatted specifically
        for Faceit Support Tickets (support.faceit.com) and Faceit Anti-Cheat staff.
        """
        ctx = cls._extract_replay_context(demo_info)
        m = cls._extract_numeric_metrics(player)
        faceit_url = cls.get_faceit_url(player.steamid)

        # Violation categories / QCM observations
        if qcm_options:
            qcm_text = "\n".join([f"• {opt}" for opt in qcm_options])
        else:
            qcm_text = "• Unspecified / Telemetry flag investigation"

        # System flags
        if player.violation_flags:
            flags_text = "\n".join([f"• {flag}" for flag in player.violation_flags])
        else:
            flags_text = "• No automated critical flags (Legitimate profile)"

        clean_comments = comments.strip() if comments else "None provided."

        # Incident ticks preview
        incident_lines = []
        if player.combat_events:
            for ev in player.combat_events[:5]:
                ev_type = ev.get("type", "")
                if ev_type == "aim_snap":
                    incident_lines.append(f"  - Tick {ev.get('tick')}: Snap {ev.get('snap_angle', 0.0):.1f} deg/tick [{ev.get('weapon', 'unknown')}]")
                elif ev_type == "bhop_chain":
                    incident_lines.append(f"  - Ticks {ev.get('start_tick')}-{ev.get('end_tick')}: Chained {ev.get('chain_length')} 1-tick jumps")
                elif ev_type == "wh_lock":
                    incident_lines.append(f"  - Ticks {ev.get('start_tick')}-{ev.get('end_tick')}: Occluded target lock on {ev.get('target_name', 'target')} ({ev.get('duration_ticks')} ticks)")

        incident_section = ""
        if incident_lines:
            incident_section = "\nEVIDENCE TICKS LOG:\n" + "\n".join(incident_lines)

        report = f"""=== FACEIT SUSPECT TELEMETRY REPORT / AC TICKET ===
Suspect Nickname: {player.name}
Suspect SteamID64: {player.steamid}
FaceitFinder: {faceit_url}
Match Map: {ctx['map_name']}
Replay File: {ctx['demo_filename']}

1. VIOLATION CATEGORY:
{qcm_text}

2. QUANTITATIVE BIOMECHANICAL AUDIT:
- Score de Suspicion: {player.suspicion_score:.1f}% ({player.verdict})
- Max Angular Snap Velocity: {m['aim_p99']:.1f} deg/tick (Standard: 10-15 deg/tick)
- Angular Jerk Index: {m['aim_jerk_max']:.1f} (Mean: {m['aim_jerk_moyen']:.1f})
- Perfect 1-Tick Ground Jump Transition: {m['bhop_ratio']:.1f}% on {m['bhop_total']} jumps (Max Chain: {m['bhop_chain']})
- Alignement proxy d'occlusion: {m['wh_lock_strict']:.1f}% of unspotted ticks
- Continuous Occluded Target Tracking: {m['wh_track_max']} consecutive ticks (Avg Distance: {m['wh_dist_avg']:.1f} units){incident_section}

3. SYSTEM FLAGS:
{flags_text}

4. AUDITOR CONTEXT:
{clean_comments}

Ticket generated automatically via CS2 Anti-Cheat Replay Auditor."""

        return report
