"""
Logging configuration module.

This module handles all logging setup and configuration for the application.

Author: Vadim Kalinin
Email: vadimakalin@gmail.com
"""
import logging
from logging.handlers import RotatingFileHandler
from config import (
    LOG_DIR, LOG_FILE, LOG_LEVEL, LOG_FORMAT, LOG_DATE_FORMAT,
    LOG_MAX_BYTES, LOG_BACKUP_COUNT
)


def setup_logging():
    """
    Configure logging to both file and console.
    
    Sets up:
    - Rotating file handler for log files
    - Console handler for stdout
    - Configures log levels and formatters
    - Suppresses verbose logs from third-party libraries
    """
    # Create logs directory if it doesn't exist
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Warning: Could not create log directory {LOG_DIR}: {e}")
    
    # Get log level
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    
    # File handler with rotation
    file_handler = None
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding='utf-8'
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
    except Exception as e:
        print(f"Warning: Could not create log file {LOG_FILE}: {e}")
        print("Logging will continue to console only")
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add file handler only if it was created successfully
    if file_handler:
        root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    
    # Suppress verbose logs from uvicorn and other libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    # Log successful configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")
    logger.info(f"Log file: {LOG_FILE}")
    logger.info(f"Log directory exists: {LOG_DIR.exists()}")
    
    # Test file write - try direct write
    try:
        test_file = LOG_FILE.parent / "test_write.log"
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("Test write successful\n")
        print(f"Test file write successful: {test_file}")
    except Exception as e:
        print(f"Warning: Could not write test file: {e}")
    
    # Test file write via logger
    if file_handler:
        try:
            logger.info("Test log message - logging to file works!")
            # Force flush and sync
            file_handler.flush()
            import os
            if hasattr(file_handler, 'stream') and file_handler.stream:
                file_handler.stream.flush()
                os.fsync(file_handler.stream.fileno())
            print(f"Logger file handler test successful")
        except Exception as e:
            print(f"Warning: Could not write test log: {e}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__)
        
    Returns:
        Logger instance
    """
    return logging.getLogger(name)

