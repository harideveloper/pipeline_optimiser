"""
Logging utility for the Pipeline Optimizer application.
Provides centralized logging configuration and management.
"""

import logging
import sys
import os
from typing import Optional
from pathlib import Path


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    include_timestamp: bool = True
) -> None:
    """
    Configure application-wide logging.
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from LOG_LEVEL env var (default: INFO)
        log_file: Optional file path to write logs to.
                  If None, reads from LOG_FILE env var
        log_to_console: Whether to output logs to console (default: True)
        include_timestamp: Whether to include timestamps in logs (default: True)
    """
    # Determine log level
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    else:
        level = level.upper()
    
    # Determine log file
    if log_file is None:
        log_file = os.getenv("LOG_FILE")
    
    # Create log format
    if include_timestamp:
        log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        date_format = "%Y-%m-%d %H:%M:%S"
    else:
        log_format = "%(name)s - %(levelname)s - %(message)s"
        date_format = None
    
    # Create formatter
    formatter = logging.Formatter(fmt=log_format, datefmt=date_format)
    
    # Get root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    
    # Remove existing handlers to avoid duplicates
    root_logger.handlers.clear()
    
    # Add console handler
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, level))
        root_logger.addHandler(console_handler)
    
    # Add file handler if specified
    if log_file:
        # Create directory if it doesn't exist
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, level))
        root_logger.addHandler(file_handler)
    
    # Reduce noise from third-party libraries
    _configure_third_party_loggers()
    
    # Log initialization
    logger = logging.getLogger(__name__)
    logger.info("Logging configured: level=%s, console=%s, file=%s", 
                level, log_to_console, log_file or "None")


def _configure_third_party_loggers():
    """Configure log levels for noisy third-party libraries."""
    noisy_loggers = {
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "urllib3": logging.WARNING,
        "openai": logging.WARNING,
        "uvicorn.access": logging.WARNING,
        "uvicorn.error": logging.INFO,
        "git": logging.WARNING,
        "github": logging.WARNING,
    }
    
    for logger_name, log_level in noisy_loggers.items():
        logging.getLogger(logger_name).setLevel(log_level)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance for the given name.
    
    Args:
        name: Logger name (typically __name__ of the module)
        
    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def set_log_level(level: str) -> None:
    """
    Change the log level at runtime.
    
    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level = level.upper()
    logging.getLogger().setLevel(getattr(logging, level))
    
    logger = logging.getLogger(__name__)
    logger.info("Log level changed to: %s", level)


def enable_debug_mode():
    """Enable debug mode with verbose logging."""
    set_log_level("DEBUG")
    
    # Also enable debug for some third-party libraries
    logging.getLogger("httpx").setLevel(logging.DEBUG)
    logging.getLogger("git").setLevel(logging.DEBUG)
    
    logger = logging.getLogger(__name__)
    logger.debug("Debug mode enabled")


def disable_debug_mode():
    """Disable debug mode, return to INFO level."""
    set_log_level("INFO")
    _configure_third_party_loggers()
    
    logger = logging.getLogger(__name__)
    logger.info("Debug mode disabled")