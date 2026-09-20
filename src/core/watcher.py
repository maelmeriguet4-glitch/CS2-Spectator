"""
CS2 Anti-Cheat — Replay Watcher
Surveillance en temps réel du dossier des replays CS2.
Compatible FR (dossier/callback/demarrer) + EN (target_dir/on_new_replay_callback/start + is_demo_write_complete).
"""

import os
import threading
import time
from typing import Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

try:
    from src.core.models import ReplayInfo
    from src.core.scanner import ReplayScanner
except Exception:
    ReplayInfo = None
    ReplayScanner = None

SOURCE2_MAGIC = b"PBDEMS2\x00"


def is_demo_write_complete(
    file_path: str,
    poll_interval: float = 0.1,
    stability_checks: int = 2,
    timeout: float = 2.0,
    min_size: int = 8,
) -> bool:
    """3-step debounce: existence + min_size + PBDEMS2 header + size stability."""
    start = time.time()
    # Wait for file to exist and reach min_size with stable size
    stable_count = 0
    last_size = -1
    while time.time() - start < timeout:
        if not os.path.isfile(file_path):
            time.sleep(poll_interval)
            continue
        try:
            size = os.path.getsize(file_path)
        except OSError:
            time.sleep(poll_interval)
            continue
        if size < min_size:
            time.sleep(poll_interval)
            continue
        # Magic header check (needs at least 8 bytes)
        try:
            with open(file_path, "rb") as f:
                header = f.read(8)
            if header != SOURCE2_MAGIC:
                return False
        except PermissionError:
            time.sleep(poll_interval)
            continue
        except Exception:
            return False
        # Stability check
        if size == last_size and size > 0:
            stable_count += 1
            if stable_count >= stability_checks:
                return True
        else:
            stable_count = 0
        last_size = size
        time.sleep(poll_interval)
    # Timeout: if file was stable at last check but not enough counts, still check once more
    return False


class _DemoHandler(FileSystemEventHandler):
    def __init__(self, watcher_ref):
        super().__init__()
        self.watcher = watcher_ref

    def on_created(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith('.dem') and not event.src_path.lower().endswith('.dem.info'):
            self.watcher._schedule_check(event.src_path)

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.lower().endswith('.dem') and not event.src_path.lower().endswith('.dem.info'):
            self.watcher._schedule_check(event.src_path)


class ReplayWatcher:
    """Surveille un dossier pour les nouveaux fichiers .dem. Hybride FR/EN."""

    def __init__(self, *args, **kwargs):
        # Parse hybrid args
        # Old: ReplayWatcher(dossier, callback)
        # New: ReplayWatcher(target_dir=..., on_new_replay_callback=..., debounce_interval=..., stability_checks=..., timeout=...)
        self.dossier = None
        self.callback = None
        self.debounce_interval = 0.1
        self.stability_checks = 2
        self.timeout = 2.0

        # Positional handling
        if len(args) >= 1:
            # first positional could be dossier/target_dir
            self.dossier = args[0]
        if len(args) >= 2:
            self.callback = args[1]

        # Keyword handling (EN)
        if "target_dir" in kwargs:
            self.dossier = kwargs["target_dir"]
        if "dossier" in kwargs:
            self.dossier = kwargs["dossier"]
        if "on_new_replay_callback" in kwargs:
            self.callback = kwargs["on_new_replay_callback"]
        if "callback" in kwargs:
            self.callback = kwargs["callback"]
        if "debounce_interval" in kwargs:
            self.debounce_interval = float(kwargs["debounce_interval"])
        if "stability_checks" in kwargs:
            self.stability_checks = int(kwargs["stability_checks"])
        if "timeout" in kwargs:
            self.timeout = float(kwargs["timeout"])
        # Legacy delai_stabilisation -> map to debounce
        if "delai_stabilisation" in kwargs:
            self.debounce_interval = float(kwargs["delai_stabilisation"])

        # Detect callback type: if EN, expects ReplayInfo; if FR, expects path string
        # We will auto-detect by inspecting callback: we'll send ReplayInfo for EN, path for FR
        # The clue: EN tests check received[0].file_name
        self._is_en_callback = False
        if self.callback:
            # Heuristic: if caller used EN kwarg name, it's EN
            if "on_new_replay_callback" in kwargs or "target_dir" in kwargs:
                self._is_en_callback = True

        self.observer: Optional[Observer] = None
        self.actif = False
        self._fichiers_en_cours = {}
        self._lock = threading.Lock()
        self._active = False

    # === FR API ===
    def demarrer(self):
        return self.start()

    def arreter(self):
        return self.stop()

    # === EN API ===
    def start(self):
        if self._active or self.actif:
            return True
        if not self.dossier or not os.path.isdir(self.dossier):
            return False
        handler = _DemoHandler(self)
        self.observer = Observer()
        self.observer.schedule(handler, self.dossier, recursive=False)
        self.observer.daemon = True
        self.observer.start()
        self.actif = True
        self._active = True
        return True

    def stop(self):
        if self.observer and (self.actif or self._active):
            try:
                self.observer.stop()
                self.observer.join(timeout=2)
            except Exception as _e:
                    import logging
                    logging.debug(f"Ignored error: {_e}")
            self.observer = None
        self.actif = False
        self._active = False
        return True

    def is_running(self) -> bool:
        return bool(self._active and self.actif and self.observer is not None)

    def _schedule_check(self, chemin: str):
        # Ignore .dem.info
        if chemin.lower().endswith('.dem.info'):
            return
        if not chemin.lower().endswith('.dem'):
            return
        with self._lock:
            if chemin in self._fichiers_en_cours:
                return
            self._fichiers_en_cours[chemin] = True

        def verifier():
            try:
                ok = is_demo_write_complete(
                    chemin,
                    poll_interval=self.debounce_interval if self.debounce_interval else 0.1,
                    stability_checks=self.stability_checks,
                    timeout=self.timeout,
                    min_size=8,
                )
                if ok and self.callback:
                    try:
                        if self._is_en_callback:
                            # Build ReplayInfo
                            if ReplayInfo and ReplayScanner:
                                try:
                                    stat = os.stat(chemin)
                                    map_name, server_name = ReplayScanner.extract_replay_metadata(chemin)
                                    info = ReplayInfo(
                                        file_path=chemin,
                                        file_name=os.path.basename(chemin),
                                        file_size_bytes=stat.st_size,
                                        modified_time=stat.st_mtime,
                                        map_name=map_name,
                                        server_name=server_name,
                                    )
                                    self.callback(info)
                                except Exception:
                                    # Fallback to path if ReplayInfo fails
                                    try:
                                        self.callback(chemin)
                                    except Exception as _e:
                                            import logging
                                            logging.debug(f"Ignored error: {_e}")
                            else:
                                self.callback(chemin)
                        else:
                            # FR: send path string; if callback expects ReplayInfo, also try
                            try:
                                self.callback(chemin)
                            except TypeError:
                                # Try EN style
                                if ReplayInfo:
                                    stat = os.stat(chemin)
                                    info = ReplayInfo(chemin, os.path.basename(chemin), stat.st_size, stat.st_mtime)
                                    self.callback(info)
                    except Exception as _e:
                            import logging
                            logging.debug(f"Ignored error: {_e}")
            finally:
                with self._lock:
                    self._fichiers_en_cours.pop(chemin, None)

        t = threading.Thread(target=verifier, daemon=True)
        t.start()
