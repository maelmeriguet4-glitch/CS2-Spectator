"""Caching system for Match Analysis Results.

Prevents re-analyzing the same .dem file if it has already been processed.
Uses gzip compressed JSON to store cache data efficiently.
Invalidates automatically upon engine, feature schema, model, or file modification.
"""

import gzip
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Optional

from src.core.config import get_config
from src.core.models import MatchAnalysisResult

logger = logging.getLogger(__name__)

CACHE_DIR = Path(os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))) / "CS2AntiCheat" / "Cache"


def get_demo_hash(demo_path: str, model_fingerprint: Optional[str] = None) -> Optional[str]:
    """
    Génère une empreinte stricte et rapide pour un fichier de démo.
    Combine :
    - chemin absolu normalisé
    - taille du fichier et mtime_ns
    - version du moteur et version du schéma de features
    - empreinte du modèle de classification
    - premier bloc (1 Mo) et dernier bloc (64 Ko) du fichier
    """
    if not os.path.exists(demo_path):
        return None

    cfg = get_config()
    try:
        stat = os.stat(demo_path)
    except OSError:
        return None

    h = hashlib.sha256()

    # Paramètres de version et modèle
    h.update(str(getattr(cfg, "engine_version", "3.1.0")).encode("utf-8"))
    h.update(str(getattr(cfg, "feature_schema_version", "1.0")).encode("utf-8"))
    h.update(str(model_fingerprint or "default_cs2cd").encode("utf-8"))

    # Métadonnées fichier
    h.update(os.path.abspath(demo_path).encode("utf-8"))
    h.update(str(stat.st_size).encode("utf-8"))
    h.update(str(getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1e9))).encode("utf-8"))

    try:
        with open(demo_path, "rb") as f:
            # Hash du premier 1MB
            h.update(f.read(1024 * 1024))
            # Si le fichier est volumineux (>2MB), hash également des derniers 64 Ko
            if stat.st_size > 2 * 1024 * 1024:
                f.seek(max(0, stat.st_size - 64 * 1024))
                h.update(f.read(64 * 1024))
    except Exception as e:
        logger.warning(f"Could not read chunk of {demo_path} for hash: {e}")
        return None

    return h.hexdigest()[:32]


def get_cache_path(demo_hash: str) -> Path:
    """Returns the cache file path for a given demo hash."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{demo_hash}.cs2ac"


def _apply_lru_eviction(max_entries: int) -> None:
    """Nettoie les entrées de cache les plus anciennes si la limite max_entries est dépassée."""
    if not CACHE_DIR.exists():
        return
    try:
        cache_files = list(CACHE_DIR.glob("*.cs2ac"))
        if len(cache_files) > max_entries:
            # Trier par date d'accès/modification croissante
            cache_files.sort(key=lambda p: p.stat().st_mtime)
            surplus = len(cache_files) - max_entries
            for f in cache_files[:surplus]:
                try:
                    f.unlink()
                except OSError:
                    pass
    except Exception as e:
        logger.debug(f"Erreur lors du nettoyage LRU du cache : {e}")


def load_cached_analysis(demo_path: str, model_fingerprint: Optional[str] = None) -> Optional[MatchAnalysisResult]:
    """Loads a MatchAnalysisResult from the cache if it exists and is valid."""
    demo_hash = get_demo_hash(demo_path, model_fingerprint=model_fingerprint)
    if not demo_hash:
        return None

    cache_file = get_cache_path(demo_hash)
    if not cache_file.exists():
        return None

    try:
        with gzip.open(cache_file, "rt", encoding="utf-8") as f:
            data = json.load(f)

        result = MatchAnalysisResult.from_dict(data)
        result.demo_path = demo_path
        # Toucher le fichier pour maintenir le statut LRU
        try:
            cache_file.touch(exist_ok=True)
        except OSError:
            pass
        logger.info(f"Loaded cached analysis for {demo_path}")
        return result
    except Exception as e:
        logger.warning(f"Failed to load cache from {cache_file}: {e}")
        return None


def save_analysis_cache(demo_path: str, result: MatchAnalysisResult, model_fingerprint: Optional[str] = None) -> None:
    """Saves a MatchAnalysisResult to the cache and enforces LRU limits."""
    demo_hash = get_demo_hash(demo_path, model_fingerprint=model_fingerprint)
    if not demo_hash:
        return

    cache_file = get_cache_path(demo_hash)

    try:
        data = result.to_dict()
        with gzip.open(cache_file, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        logger.info(f"Saved analysis cache to {cache_file}")

        # Appliquer la politique LRU
        cfg = get_config()
        max_entries = getattr(cfg, "cache_max_entries", 500)
        _apply_lru_eviction(max_entries)
    except Exception as e:
        logger.error(f"Failed to save cache to {cache_file}: {e}")


def clear_cache() -> None:
    """Clears all cached analysis files."""
    try:
        if CACHE_DIR.exists():
            for f in CACHE_DIR.glob("*.cs2ac"):
                f.unlink()
            logger.info("Cache cleared.")
    except Exception as e:
        logger.error(f"Error clearing cache: {e}")

