import logging
import logging.handlers
import os
import traceback
from datetime import datetime


def setup_logging(log_level="INFO"):
    """
    Configure application-wide logging
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create logs directory if it doesn't exist
    os_log_dir = "logs"
    if not os.path.exists(os_log_dir):
        os.makedirs(os_log_dir)
        
    # Convert string log level to logging constant
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid log level: {log_level}")
        
    # Get current date for log filename
    current_date = datetime.now().strftime("%Y-%m-%d")
    log_file = os.path.join(os_log_dir, f"vr_interview_{current_date}.log")
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    # Create handlers
    console_handler = logging.StreamHandler()
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5
    )
    
    # Create formatter
    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] - %(message)s"
    )
    
    # Set formatter for handlers
    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)
    
    # Add handlers to root logger
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Set specific levels for noisy libraries
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    # Log initial message
    logging.info(f"Logging initialized at level {log_level}")


def get_logger(name):
    """
    Get a logger with the specified name
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    return logging.getLogger(name)


def log_exception(e, logger=None):
    """
    Format exception for logging
    
    Args:
        e: Exception object
        logger: Logger to use, or None for root logger
    """
    if logger is None:
        logger = logging.getLogger()
        
    logger.error(f"Exception: {type(e).__name__}: {str(e)}")
    logger.debug(f"Exception traceback: {''.join(traceback.format_exception(None, e, e.__traceback__))}")
