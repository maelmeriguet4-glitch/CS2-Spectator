import os
import re
from datetime import datetime

def _sanitize_filename(name: str) -> str:
    """Remplace les caractères invalides pour un nom de fichier Windows/Linux."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip() or "Joueur_Inconnu"

def export_player_report(player, demo_name: str = "Unknown_Demo", export_dir: str = "reports") -> str:
    """
    Génère un rapport texte détaillé pour un joueur suspect.
    Retourne le chemin complet du fichier généré.
    """
    if not os.path.exists(export_dir):
        os.makedirs(export_dir)

    safe_name = _sanitize_filename(getattr(player, "name", "Inconnu"))
    date_str = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"Report_{safe_name}_{date_str}.txt"
    filepath = os.path.join(export_dir, filename)

    verdict = getattr(player, "verdict", "CLEAN")
    score = getattr(player, "suspicion_score", 0.0)
    flags = getattr(player, "violation_flags", [])

    lines = []
    lines.append("="*50)
    lines.append("       CS2 ANTI-CHEAT : RAPPORT DE DIAGNOSTIC")
    lines.append("="*50)
    lines.append(f"Date de l'export : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Démo analysée    : {demo_name}")
    lines.append("-" * 50)
    lines.append(f"JOUEUR : {getattr(player, 'name', 'Inconnu')}")
    lines.append(f"STEAM ID : {getattr(player, 'steamid', 'Inconnu')}")
    lines.append(f"VERDICT GLOBAL : {verdict} ({score:.1f}%)")
    lines.append("-" * 50)
    
    lines.append("PREUVES DE TRICHE (FLAGS):")
    if flags:
        for flag in flags:
            lines.append(f"  > {flag}")
    else:
        lines.append("  > Aucune preuve formelle d'anomalie détectée.")
        
    lines.append("-" * 50)
    lines.append("Rapport généré automatiquement par le modèle ML d'analyse CS2.")
    lines.append("="*50)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath
