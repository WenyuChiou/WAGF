import logging
import os

# Define a custom log format that matches the existing style but allows level control
LOG_FORMAT = "%(message)s"

def setup_logger(name: str, level: int = logging.INFO):
    """Setup a standard logger with a clean format."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(LOG_FORMAT)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    # Allow environment override for log level
    env_level = os.environ.get("BROKER_LOG_LEVEL")
    if env_level:
        level = getattr(logging, env_level.upper(), level)
        
    logger.setLevel(level)
    return logger

# Shared logger instance
logger = setup_logger("broker")
