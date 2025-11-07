"""
Configuration du système de logging
"""

import logging
import os
from datetime import datetime


def setup_logger(name: str = None, log_level: str = "INFO", log_file: str = None) -> logging.Logger:
    """Configure et retourne un logger"""
    
    logger = logging.getLogger(name or __name__)
    logger.setLevel(getattr(logging, log_level.upper()))
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    if log_file:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger