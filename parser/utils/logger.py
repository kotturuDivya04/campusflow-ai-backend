import logging
import sys
from config import LOG_FILE_PATH, LOG_LEVEL

def setup_logger(name: str = "campusflow_parser") -> logging.Logger:
    """Sets up a dual handler logger for stdout and file logging."""
    logger = logging.getLogger(name)
    
    # If logger is already configured, return it
    if logger.handlers:
        return logger
        
    logger.setLevel(LOG_LEVEL)
    
    # Create formatter
    formatter = logging.Formatter(
        "[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler
    try:
        file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not create file log handler at {LOG_FILE_PATH}: {e}")
        
    return logger

# Global package-level logger
logger = setup_logger()
