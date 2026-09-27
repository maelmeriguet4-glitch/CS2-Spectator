"""Caching system for Match Analysis Results.

Prevents re-analyzing the same .dem file if it has already been processed.
Uses gzip compressed JSON to store cache data efficiently.
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

def get_demo_hash(demo_path: str) -> Optional[str]:
    """Generates a fast hash for a demo file based on its path, size, and first 1MB chunk."""
    if not os.path.exists(demo_path):
        return None
    
    stat = os.stat(demo_path)
    h = hashlib.md5()
    # Invalidate results whenever analyzer or model behavior changes.
    h.update(get_config().engine_version.encode("utf-8"))
    h.update(os.path.abspath(demo_path).encode('utf-8'))
    h.update(str(stat.st_size).encode('utf-8'))
    
    try:
        with open(demo_path, "rb") as f:
            h.update(f.read(1024 * 1024))  # Hash first 1MB
    except Exception as e:
        logger.warning(f"Could not read chunk of {demo_path} for hash: {e}")
        return None
        
    return h.hexdigest()


def get_cache_path(demo_hash: str) -> Path:
    """Returns the cache file path for a given demo hash."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return CACHE_DIR / f"{demo_hash}.cs2ac"


def load_cached_analysis(demo_path: str) -> Optional[MatchAnalysisResult]:
    """Loads a MatchAnalysisResult from the cache if it exists and is valid."""
    demo_hash = get_demo_hash(demo_path)
    if not demo_hash:
        return None
        
    cache_file = get_cache_path(demo_hash)
    
    if not cache_file.exists():
        return None
        
    try:
        with gzip.open(cache_file, "rt", encoding="utf-8") as f:
            data = json.load(f)
            
        result = MatchAnalysisResult.from_dict(data)
        # Update demo path in case the file was moved
        result.demo_path = demo_path
        logger.info(f"Loaded cached analysis for {demo_path}")
        return result
    except Exception as e:
        logger.warning(f"Failed to load cache from {cache_file}: {e}")
        return None


def save_analysis_cache(demo_path: str, result: MatchAnalysisResult) -> None:
    """Saves a MatchAnalysisResult to the cache."""
    demo_hash = get_demo_hash(demo_path)
    if not demo_hash:
        return
        
    cache_file = get_cache_path(demo_hash)
    
    try:
        data = result.to_dict()
        with gzip.open(cache_file, "wt", encoding="utf-8") as f:
            json.dump(data, f)
        logger.info(f"Saved analysis cache to {cache_file}")
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
