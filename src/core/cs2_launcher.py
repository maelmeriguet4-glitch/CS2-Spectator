"""CS2 Game Launcher and In-Game Replay Inspector.

Handles automatic detection of Steam and CS2 installations,
hard-linking / copying demos to the game directory, creating automated
execution scripts (.cfg), and launching Counter-Strike 2 with launch arguments.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
from typing import Any, Dict, Optional, Tuple

try:
    import winreg  # type: ignore
except ImportError:
    winreg = None  # type: ignore

logger = logging.getLogger(__name__)


def find_steam_and_cs2() -> Tuple[Optional[str], Optional[str]]:
    """Locates the steam.exe path and CS2 'game/csgo' directory from Windows Registry."""
    steam_exe = None
    csgo_dir = None

    if winreg is None or sys.platform != "win32":
        return steam_exe, csgo_dir

    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
        steam_path, _ = winreg.QueryValueEx(key, "SteamPath")
        winreg.CloseKey(key)

        candidate_exe = os.path.join(steam_path, "steam.exe")
        if os.path.exists(candidate_exe):
            steam_exe = candidate_exe

        # Read libraryfolders.vdf to find all Steam library paths
        vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
        library_paths = [steam_path]

        if os.path.exists(vdf_path):
            try:
                with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                    vdf_content = f.read()
                found_paths = re.findall(r'"path"\s+"([^"]+)"', vdf_content)
                for p in found_paths:
                    norm = p.replace("\\\\", "\\")
                    if norm not in library_paths and os.path.exists(norm):
                        library_paths.append(norm)
            except Exception as e:
                logger.warning(f"Error parsing libraryfolders.vdf: {e}")

        # Search for CS2 in all detected library paths
        for lib in library_paths:
            candidate_csgo = os.path.join(
                lib, "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo"
            )
            if os.path.exists(candidate_csgo):
                csgo_dir = candidate_csgo
                break

    except Exception as e:
        logger.error(f"Failed to locate Steam/CS2 via registry: {e}")

    return steam_exe, csgo_dir


def is_cs2_running() -> bool:
    """Checks if cs2.exe is currently running on the system."""
    try:
        output = subprocess.check_output(
            ["tasklist", "/FI", "IMAGENAME eq cs2.exe", "/NH"],
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        return "cs2.exe" in output.lower()
    except Exception as e:
        logger.warning(f"Failed to check if CS2 is running: {e}")
        return False


def bring_cs2_to_foreground() -> bool:
    """Attempts to bring the Counter-Strike 2 window to the front."""
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.FindWindowW(None, "Counter-Strike 2")
        if hwnd:
            user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            user32.SetForegroundWindow(hwnd)
            return True
    except Exception as _e:
            import logging
            logging.debug(f"Ignored error: {_e}")
    return False


def prepare_replay_files(demo_path: str, target_tick: int, csgo_dir: str) -> Tuple[bool, str]:
    """Prepares the demo file and autoexec .cfg script inside CS2's csgo directory.

    Uses hardlinks to avoid copying large files when on the same drive.
    Returns (success, message).
    """
    try:
        if not os.path.exists(demo_path):
            return False, f"Le fichier démo n'existe pas : {demo_path}"

        dest_demo = os.path.join(csgo_dir, "anticheat_inspect.dem")
        cfg_dir = os.path.join(csgo_dir, "cfg")
        os.makedirs(cfg_dir, exist_ok=True)
        dest_cfg = os.path.join(cfg_dir, "anticheat_watch.cfg")

        # Copy or hardlink the demo
        if os.path.exists(dest_demo):
            try:
                os.remove(dest_demo)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

        try:
            # Hard link is instantaneous and takes 0 extra disk space
            os.link(demo_path, dest_demo)
            logger.info("Demo hardlinked successfully.")
        except Exception:
            # Fallback to copy if cross-drive
            shutil.copyfile(demo_path, dest_demo)
            logger.info("Demo copied successfully.")

        # Write anticheat_watch.cfg
        cfg_content = (
            f"// CS2 Anti-Cheat Auto-Inspector\n"
            f"sv_cheats 1\n"
            f"spec_show_xray 1\n"
            f"playdemo anticheat_inspect\n"
            f'bind "F8" "demo_gototick {target_tick}; echo [ANTICHEAT] Saut au tick {target_tick}"\n'
            f'echo "=== CS2 Anti-Cheat : Appuyez sur F8 pour aller au moment suspect ({target_tick}) ==="\n'
        )

        with open(dest_cfg, "w", encoding="utf-8") as f:
            f.write(cfg_content)

        return True, "Replay et script configurés avec succès."
    except Exception as e:
        logger.error(f"Error preparing replay files: {e}")
        return False, str(e)


def execute_cs2_launch(
    demo_path: str,
    target_tick: int = 0,
    force_restart: bool = False,
) -> Dict[str, Any]:
    """Main orchestration function to inspect a suspicious action inside CS2.

    Returns a status dict:
        - status: "launched" | "already_running" | "error"
        - message: Human-readable message
        - command: CS2 console command to run manually if needed
        - tick: Target tick
    """
    steam_exe, csgo_dir = find_steam_and_cs2()

    if not csgo_dir or not os.path.exists(csgo_dir):
        return {
            "status": "error",
            "message": "Impossible de trouver le dossier d'installation de Counter-Strike 2.",
            "command": f'playdemo "{demo_path}"; demo_gototick {target_tick}',
            "tick": target_tick,
        }

    # Prepare files (anticheat_inspect.dem & anticheat_watch.cfg)
    ok, err = prepare_replay_files(demo_path, target_tick, csgo_dir)
    if not ok:
        return {
            "status": "error",
            "message": f"Erreur de préparation du replay : {err}",
            "command": f'playdemo "{demo_path}"; demo_gototick {target_tick}',
            "tick": target_tick,
        }

    console_cmd = "exec anticheat_watch"
    running = is_cs2_running()

    if running and not force_restart:
        # Bring CS2 to front and inform user
        bring_cs2_to_foreground()
        return {
            "status": "already_running",
            "message": "CS2 est déjà lancé ! La commande a été préparée.",
            "command": console_cmd,
            "tick": target_tick,
        }

    if running and force_restart:
        # Close running CS2
        try:
            subprocess.run(["taskkill", "/F", "/IM", "cs2.exe"], capture_output=True)
            time.sleep(1.5)
        except Exception as e:
            logger.warning(f"Failed to kill cs2.exe: {e}")

    # Launch CS2 through Steam with arguments
    try:
        if steam_exe and os.path.exists(steam_exe):
            # Official Steam launch parameter with game console command
            subprocess.Popen(
                [steam_exe, "-applaunch", "730", "+exec", "anticheat_watch"],
                creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
            )
        else:
            # Fallback direct cs2.exe execution
            cs2_exe = os.path.join(
                os.path.dirname(os.path.dirname(csgo_dir)), "bin", "win64", "cs2.exe"
            )
            if os.path.exists(cs2_exe):
                subprocess.Popen(
                    [cs2_exe, "+exec", "anticheat_watch"],
                    creationflags=subprocess.DETACHED_PROCESS if os.name == "nt" else 0,
                )
            else:
                return {
                    "status": "error",
                    "message": "Fichier exécutable Steam ou CS2 introuvable.",
                    "command": console_cmd,
                    "tick": target_tick,
                }

        return {
            "status": "launched",
            "message": "Counter-Strike 2 a été lancé avec le replay suspect !",
            "command": console_cmd,
            "tick": target_tick,
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Erreur lors du lancement de CS2 : {e}",
            "command": console_cmd,
            "tick": target_tick,
        }
