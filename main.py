"""
CS2 Anti-Cheat Dashboard — Point d'entrée principal
Lance l'interface graphique CustomTkinter ou mode console.
"""

import os
import sys
import argparse

# Configuration UTF-8 pour la console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception as e:
        print(f"Failed to reconfigure streams: {e}", file=sys.stderr)

DIR_RACINE = os.path.dirname(os.path.abspath(__file__))

VERSION = "2.5.0"


def resource_path(relative_path: str) -> str:
    """Retourne chemin absolu ressource, compatible PyInstaller (sys._MEIPASS) et dev."""
    if getattr(sys, 'frozen', False):
        base = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
    else:
        base = DIR_RACINE
    return os.path.normpath(os.path.join(base, relative_path))


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="CS2AntiCheat", description="CS2 Anti-Cheat Dashboard")
    parser.add_argument("--demo", type=str, default=None, help="Chemin fichier .dem à analyser en mode console")
    parser.add_argument("--model", type=str, default=None, help="Chemin modèle custom .pkl")
    parser.add_argument(
        "--model-type",
        type=str,
        default="cs2cd",
        choices=["cs2cd", "synthetic", "custom"],
        help="Type de modèle ML ('cs2cd', 'synthetic', 'custom')",
    )
    parser.add_argument("--version", action="version", version=f"CS2 Anti-Cheat Replay Auditor v{VERSION}")
    return parser


def run_console_analysis(demo_path: str, model_path: str = None, model_type: str = "cs2cd") -> int:
    """Analyse console synchrone, retourne 0 succès, 1 erreur."""
    if not demo_path or not os.path.isfile(demo_path):
        print(f"[ERREUR] Fichier de démo introuvable : {demo_path}", file=sys.stderr)
        return 1
    if model_path and not os.path.isfile(model_path):
        print(f"[AVERTISSEMENT] Modèle ML introuvable : {model_path}. Repli sur l'heuristique experte.")
        model_path = None
    try:
        from src.core.engine import AntiCheatEngine
        engine = AntiCheatEngine(model_path=model_path, model_type=model_type)
        result = engine.analyze_demo(demo_path)
        print(f"Carte: {result.map_name} | Ticks: {result.total_ticks} | Joueurs: {len(result.players)}")
        for p in result.players:
            print(f"  {p.name} [{p.steamid}] {p.verdict} {p.suspicion_score:.1f}% - {p.violation_flags}")
        print(f"Verdict global: {result.global_verdict}")
        print(f"SYNTHÈSE : {result.global_verdict}")
        return 0
    except Exception as e:
        print(f"[ERREUR] Analyse échouée : {e}", file=sys.stderr)
        return 1


def main():
    """Lance l'application CS2 Anti-Cheat Dashboard (GUI ou console)."""
    parser = create_parser()
    args = parser.parse_args()
    if args.demo:
        sys.exit(run_console_analysis(args.demo, model_path=args.model, model_type=args.model_type))
    # Mode GUI
    try:
        from src.ui.app import CS2AntiCheatApp
        app = CS2AntiCheatApp()
        app.mainloop()
    except Exception as e:
        print(f"[ERREUR CRITIQUE] Impossible d'initialiser l'interface graphique : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    main()
