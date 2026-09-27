"""
CS2 Anti-Cheat — Infrastructure de Logging Structuré
Logger avec rotation de fichier et sortie console.
"""

import logging
import os
from logging.handlers import RotatingFileHandler

_DIR_RACINE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_LOG_DIR = os.path.join(_DIR_RACINE, "data")
_LOG_FILE = os.path.join(_LOG_DIR, "cs2_anticheat.log")

_loggers = {}

def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Crée ou retourne un logger structuré avec rotation de fichier.
    
    Args:
        name: Nom du module (ex: 'engine', 'aimbot', 'classifier')
        level: Niveau de log (DEBUG, INFO, WARNING, ERROR)
    
    Returns:
        Logger configuré avec handler fichier rotatif et console.
    """
    if name in _loggers:
        return _loggers[name]
    
    logger = logging.getLogger(f"cs2ac.{name}")
    logger.setLevel(level)
    
    # Éviter la duplication de handlers
    if logger.handlers:
        _loggers[name] = logger
        return logger
    
    # Format structuré
    fmt = logging.Formatter(
        "[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Handler console
    console = logging.StreamHandler()
    console.setLevel(logging.WARNING)  # Console = WARNING+ seulement
    console.setFormatter(fmt)
    logger.addHandler(console)
    
    # Handler fichier rotatif (5 MB, 3 backups)
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        file_handler = RotatingFileHandler(
            _LOG_FILE,
            maxBytes=5 * 1024 * 1024,  # 5 MB
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except (OSError, PermissionError):
        # Si impossible d'écrire dans le fichier, on continue avec la console
        pass
    
    logger.propagate = False
    _loggers[name] = logger
    return logger
