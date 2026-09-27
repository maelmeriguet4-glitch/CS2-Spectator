"""
Scanner module for Counter-Strike 2 replays and Steam library discovery.
Locates CS2 installations across multi-drive configurations and lists replays.
"""

import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple

from .models import ReplayInfo

# Optional demoparser2 import for fast header metadata extraction
try:
    import demoparser2
    HAS_DEMOPARSER = True
except ImportError:
    HAS_DEMOPARSER = False


class ReplayScanner:
    """Discovers CS2 replay directories and catalogs recorded match demos."""

    CS2_APP_ID = "730"
    CS2_RELATIVE_REPLAY_PATH = os.path.join(
        "steamapps", "common", "Counter-Strike Global Offensive", "game", "csgo", "replays"
    )
    CSGO_LEGACY_RELATIVE_PATH = os.path.join(
        "steamapps", "common", "Counter-Strike Global Offensive", "csgo", "replays"
    )  # Legacy CSGO avant 'game/' (même chemin post-migration, gardé pour compat)

    COMMON_DRIVES = ["C", "D", "E", "F", "G", "H"]

    @classmethod
    def get_available_drives(cls) -> List[str]:
        """Detects available drives on Windows dynamically with fallback."""
        drives: List[str] = []
        if sys.platform == "win32":
            if hasattr(os, "listdrives"):
                try:
                    for d in os.listdrives():
                        drive_letter = d.rstrip(":\\/").upper()
                        if drive_letter and drive_letter not in drives:
                            drives.append(drive_letter)
                except Exception:
                    pass
            if not drives:
                try:
                    import ctypes
                    bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                    for letter_code in range(26):
                        if bitmask & (1 << letter_code):
                            drives.append(chr(ord('A') + letter_code))
                except Exception:
                    pass
        if not drives:
            drives = ["C", "D", "E", "F", "G", "H"]
        ordered: List[str] = []
        for p in ["C", "D"]:
            if p in drives:
                ordered.append(p)
        for d in drives:
            if d not in ordered:
                ordered.append(d)
        return ordered

    @classmethod
    def get_steam_install_path(cls) -> Optional[str]:
        """
        Retrieves Steam installation root path using Windows Registry or common fallbacks.
        Checks HKCU\\Software\\Valve\\Steam\\SteamPath, then HKLM InstallPath.
        """
        if sys.platform == "win32":
            try:
                import winreg

                # Try HKCU first
                for subkey in [r"Software\Valve\Steam", r"SOFTWARE\Valve\Steam"]:
                    try:
                        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
                            val, _ = winreg.QueryValueEx(key, "SteamPath")
                            if val and os.path.isdir(val):
                                return os.path.normpath(val)
                    except OSError:
                        pass

                # Try HKLM
                for subkey in [
                    r"SOFTWARE\Valve\Steam",
                    r"SOFTWARE\WOW6432Node\Valve\Steam",
                ]:
                    try:
                        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, subkey) as key:
                            val, _ = winreg.QueryValueEx(key, "InstallPath")
                            if val and os.path.isdir(val):
                                return os.path.normpath(val)
                    except OSError:
                        pass
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

        # Check default Windows folder locations
        default_paths = [
            r"C:\Program Files (x86)\Steam",
            r"C:\Program Files\Steam",
            os.path.expandvars(r"%ProgramFiles(x86)%\Steam"),
            os.path.expandvars(r"%ProgramFiles%\Steam"),
        ]
        for p in default_paths:
            if p and os.path.isdir(p):
                return os.path.normpath(p)

        return None

    @classmethod
    def parse_libraryfolders_vdf(cls, vdf_path: str) -> List[Dict[str, Any]]:
        """
        Parses Steam's libraryfolders.vdf file to extract all configured library roots
        and their installed App IDs.
        """
        if not os.path.isfile(vdf_path):
            return []

        libraries: List[Dict[str, Any]] = []
        try:
            with open(vdf_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            raw_tokens = re.findall(r'(\{|\}|"[^"]*")', content)
            clean_tokens = [t[1:-1] if t.startswith('"') else t for t in raw_tokens]

            i = 0
            n = len(clean_tokens)
            while i < n:
                token = clean_tokens[i]
                if token.isdigit() and i + 1 < n and clean_tokens[i + 1] == "{":
                    lib_dict: Dict[str, Any] = {"path": "", "apps": set(), "has_cs2": False}
                    i += 2
                    depth = 1
                    current_key = None
                    in_apps = False

                    while i < n and depth > 0:
                        tok = clean_tokens[i]
                        if tok == "{":
                            depth += 1
                            if current_key == "apps":
                                in_apps = True
                            current_key = None
                            i += 1
                        elif tok == "}":
                            depth -= 1
                            if depth == 1:
                                in_apps = False
                            current_key = None
                            i += 1
                        else:
                            if not in_apps:
                                if current_key is None:
                                    current_key = tok
                                    i += 1
                                else:
                                    if current_key == "path":
                                        raw_p = tok.replace("\\\\", "\\")
                                        lib_dict["path"] = os.path.normpath(raw_p)
                                    current_key = None
                                    i += 1
                            else:
                                if current_key is None:
                                    app_id = tok
                                    lib_dict["apps"].add(app_id)
                                    if app_id == cls.CS2_APP_ID:
                                        lib_dict["has_cs2"] = True
                                    current_key = app_id
                                    i += 1
                                else:
                                    # Value for app (size), discard
                                    current_key = None
                                    i += 1

                    if lib_dict["path"]:
                        libraries.append(lib_dict)
                    continue
                i += 1

            # Fallback if state machine yielded no libraries
            if not libraries:
                paths = re.findall(r'"path"\s+"([^"]+)"', content)
                for p in paths:
                    norm = os.path.normpath(p.replace("\\\\", "\\"))
                    libraries.append({
                        "path": norm,
                        "apps": set(),
                        "has_cs2": cls.CS2_APP_ID in content,
                    })

        except Exception as _e:
                import logging
                logging.debug(f"Ignored error: {_e}")

        return libraries

    @classmethod
    def get_steam_library_paths(cls) -> List[str]:
        """
        Returns all detected Steam library root paths across all drives,
        with libraries containing CS2 (AppID 730) prioritized first.
        """
        library_paths: List[str] = []
        steam_path = cls.get_steam_install_path()

        if steam_path:
            vdf_path = os.path.join(steam_path, "steamapps", "libraryfolders.vdf")
            parsed_libs = cls.parse_libraryfolders_vdf(vdf_path)
            
            # Prioritize libraries known to have CS2
            cs2_libs = [lib["path"] for lib in parsed_libs if lib.get("has_cs2") and os.path.isdir(lib["path"])]
            other_libs = [lib["path"] for lib in parsed_libs if not lib.get("has_cs2") and os.path.isdir(lib["path"])]

            for lib in cs2_libs + other_libs:
                if lib not in library_paths:
                    library_paths.append(lib)

            if steam_path not in library_paths and os.path.isdir(steam_path):
                library_paths.append(steam_path)

        # Fallback drive checks
        for drive in cls.get_available_drives():
            drive_libs = [
                f"{drive}:\\SteamLibrary",
                f"{drive}:\\Program Files (x86)\\Steam",
                f"{drive}:\\Program Files\\Steam",
                f"{drive}:\\Steam",
            ]
            for candidate in drive_libs:
                if os.path.isdir(candidate) and candidate not in library_paths:
                    library_paths.append(candidate)

        return library_paths

    @classmethod
    def find_all_replay_dirs(cls) -> List[str]:
        """
        Returns all valid, existing CS2 replay directories found on the system.
        """
        found_dirs: List[str] = []

        for lib_path in cls.get_steam_library_paths():
            # Check primary CS2 path: game/csgo/replays
            cs2_replay = os.path.join(lib_path, cls.CS2_RELATIVE_REPLAY_PATH)
            if os.path.isdir(cs2_replay) and cs2_replay not in found_dirs:
                found_dirs.append(cs2_replay)

            # Check legacy CS:GO path – évite double check si identique à CS2
            if cls.CSGO_LEGACY_RELATIVE_PATH != cls.CS2_RELATIVE_REPLAY_PATH:
                csgo_replay = os.path.join(lib_path, cls.CSGO_LEGACY_RELATIVE_PATH)
                if os.path.isdir(csgo_replay) and csgo_replay not in found_dirs:
                    found_dirs.append(csgo_replay)

        # Local project demos folder fallback
        local_demos = os.path.abspath("demos")
        if os.path.isdir(local_demos) and local_demos not in found_dirs:
            found_dirs.append(local_demos)

        return found_dirs

    @staticmethod
    def find_cs2_replay_dir() -> Optional[str]:
        """
        Finds the primary active Counter-Strike 2 replays directory.
        Returns the first existing path with replays, or first existing directory,
        or None if no replay folder is found.
        """
        all_dirs = ReplayScanner.find_all_replay_dirs()
        if not all_dirs:
            return None

        # Prioritize directories that actually contain .dem files
        for d in all_dirs:
            try:
                if any(f.lower().endswith(".dem") for f in os.listdir(d)):
                    return d
            except OSError:
                continue

        # Otherwise return the first discovered directory
        return all_dirs[0]

    @staticmethod
    def extract_replay_metadata(file_path: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extracts map_name and server_name from a demo file.
        Uses demoparser2 header parsing when available, falling back to
        companion .info files and filename pattern matching.
        """
        map_name: Optional[str] = None
        server_name: Optional[str] = None

        # Method 1: High-speed demoparser2 header extraction (< 10ms)
        if HAS_DEMOPARSER and os.path.isfile(file_path) and os.path.getsize(file_path) > 16:
            try:
                parser = demoparser2.DemoParser(file_path)
                header = parser.parse_header()
                if isinstance(header, dict):
                    raw_map = header.get("map_name")
                    if raw_map and isinstance(raw_map, str) and raw_map.strip():
                        map_name = raw_map.strip()
                    raw_server = header.get("server_name")
                    if raw_server and isinstance(raw_server, str) and raw_server.strip():
                        server_name = raw_server.strip()
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")

        # Method 2: Companion .dem.info file inspection
        if not map_name:
            info_path = file_path + ".info"
            if os.path.isfile(info_path):
                try:
                    with open(info_path, "rb") as f:
                        data = f.read(8192)
                    match = re.search(rb"(de_[a-zA-Z0-9_]+|cs_[a-zA-Z0-9_]+)", data)
                    if match:
                        map_name = match.group(0).decode("utf-8", errors="ignore")
                except Exception as _e:
                        import logging
                        logging.debug(f"Ignored error: {_e}")

        # Method 3: Filename pattern matching
        if not map_name:
            base_name = os.path.basename(file_path)
            match = re.search(r"(de_[a-zA-Z0-9_]+|cs_[a-zA-Z0-9_]+)", base_name, re.IGNORECASE)
            if match:
                map_name = match.group(0).lower()

        return map_name, server_name

    @staticmethod
    def list_replays(directory: Optional[str] = None) -> List[ReplayInfo]:
        """
        Scans a directory for CS2 match demos (.dem) and returns a catalog of ReplayInfo
        objects sorted in descending order of modification time (newest first).
        """
        target_dir = directory or ReplayScanner.find_cs2_replay_dir()
        if not target_dir or not os.path.isdir(target_dir):
            return []

        replays: List[ReplayInfo] = []
        try:
            entries = os.listdir(target_dir)
        except OSError:
            return []

        for entry in entries:
            # Match .dem files only, ignoring .dem.info and other extensions
            if not entry.lower().endswith(".dem"):
                continue

            file_path = os.path.join(target_dir, entry)
            if not os.path.isfile(file_path):
                continue

            try:
                stat = os.stat(file_path)
                file_size = stat.st_size
                mtime = stat.st_mtime
            except OSError:
                continue

            map_name, server_name = ReplayScanner.extract_replay_metadata(file_path)

            replays.append(
                ReplayInfo(
                    file_path=file_path,
                    file_name=entry,
                    file_size_bytes=file_size,
                    modified_time=mtime,
                    map_name=map_name,
                    server_name=server_name,
                )
            )

        # Sort descending by modified_time (most recent match first)
        replays.sort(key=lambda r: r.modified_time, reverse=True)
        return replays
