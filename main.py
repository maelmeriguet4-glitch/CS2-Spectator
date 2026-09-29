"""
CS2 Anti-Cheat Dashboard — Point d'entrée principal
Lance l'interface graphique CustomTkinter ou mode console.
"""

import argparse
import ctypes
import os
import sys
from typing import Any, Optional

# Configuration UTF-8 pour la console Windows
if sys.platform == "win32":
    try:
        stdout_reconfigure = getattr(sys.stdout, "reconfigure", None)
        stderr_reconfigure = getattr(sys.stderr, "reconfigure", None)
        if stdout_reconfigure is not None:
            stdout_reconfigure(encoding="utf-8")
        if stderr_reconfigure is not None:
            stderr_reconfigure(encoding="utf-8")
    except Exception as e:
        print(f"Failed to reconfigure streams: {e}", file=sys.stderr)

DIR_RACINE = os.path.dirname(os.path.abspath(__file__))

VERSION = "2.5.3"


def _write_version_message(message: str) -> None:
    if sys.stdout is not None:
        sys.stdout.write(f"{message}\n")
        return
    if os.name != "nt":
        return

    kernel32: Any = ctypes.WinDLL("kernel32", use_last_error=True)
    get_std_handle = kernel32.GetStdHandle
    get_std_handle.argtypes = [ctypes.c_ulong]
    get_std_handle.restype = ctypes.c_void_p
    handle = get_std_handle(ctypes.c_ulong(-11 & 0xFFFFFFFF))
    if handle in (None, ctypes.c_void_p(-1).value):
        return

    write_file = kernel32.WriteFile
    write_file.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_ulong,
        ctypes.POINTER(ctypes.c_ulong),
        ctypes.c_void_p,
    ]
    write_file.restype = ctypes.c_int
    encoded_message = f"{message}\r\n".encode("utf-8")
    buffer = ctypes.create_string_buffer(encoded_message)
    written = ctypes.c_ulong()
    if not write_file(handle, buffer, len(encoded_message), ctypes.byref(written), None):
        raise ctypes.WinError(ctypes.get_last_error())


class _VersionAction(argparse.Action):
    def __init__(self, option_strings: list[str], version: str, **kwargs: Any) -> None:
        self.version = version
        super().__init__(option_strings, nargs=0, **kwargs)

    def __call__(
        self,
        parser: argparse.ArgumentParser,
        namespace: argparse.Namespace,
        values: Any,
        option_string: Optional[str] = None,
    ) -> None:
        _write_version_message(self.version)
        parser.exit()


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
    parser.add_argument(
        "--version",
        action=_VersionAction,
        version=f"CS2 Anti-Cheat Replay Auditor v{VERSION}",
    )
    return parser


def run_console_analysis(demo_path: str, model_path: Optional[str] = None, model_type: str = "cs2cd") -> int:
    """Analyse console synchrone, retourne 0 succès, 1 erreur."""
    if not demo_path or not os.path.isfile(demo_path):
        print(f"[ERREUR] Fichier de démo introuvable : {demo_path}", file=sys.stderr)
        return 1
    if model_path and not os.path.isfile(model_path):
        print(f"[ERREUR] Modèle ML introuvable : {model_path}.", file=sys.stderr)
        return 1
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