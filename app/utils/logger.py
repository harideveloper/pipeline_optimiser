"""
Logging utility for the Pipeline Optimiser application.
"""

import logging
import sys
import os
from typing import Optional
from pathlib import Path
from datetime import datetime


class CorrelationIdFormatter(logging.Formatter):
    """
    Custom log format: timestamp | level | class | correlation_id | message
    """
    
    def formatTime(self, record, datefmt=None):
        """
        Format: YYYY-MM-DD HH:MM:SS.mmm
        """
        ct = datetime.fromtimestamp(record.created)
        if datefmt:
            s = ct.strftime(datefmt)
            s = f"{s}.{int(record.msecs):03d}"
        else:
            s = ct.strftime("%Y-%m-%d %H:%M:%S")
            s = f"{s}.{int(record.msecs):03d}"
        return s
    
    def format(self, record: logging.LogRecord) -> str:
        correlation_id = getattr(record, 'correlation_id', 'N/A')
        class_name = getattr(record, 'class_name', 'N/A')
        timestamp = self.formatTime(record, self.datefmt)
        parts = [
            timestamp,
            record.levelname,
            class_name,
            str(correlation_id),
            record.getMessage()
        ]
        
        log_line = " | ".join(parts)
        
        if record.exc_info:
            log_line += "\n" + self.formatException(record.exc_info)
        
        return log_line


def setup_logging(
    level: Optional[str] = None,
    log_file: Optional[str] = None,
    log_to_console: bool = True,
    include_timestamp: bool = True
) -> None:
    """
    Log Format: timestamp | level | class | correlation_id | message
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
               If None, reads from LOG_LEVEL env var (default: INFO)
        log_file: Optional file path to write logs to.
                  If None, reads from LOG_FILE env var
        log_to_console: Whether to output logs to console (default: True)
        include_timestamp: Whether to include timestamps in logs (default: True)
    """
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO").upper()
    else:
        level = level.upper()
    
    if log_file is None:
        log_file = os.getenv("LOG_FILE")
    
    # Date format now with milliseconds support
    date_format = "%Y-%m-%d %H:%M:%S" if include_timestamp else None
    formatter = CorrelationIdFormatter(datefmt=date_format)
    
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level))
    root_logger.handlers.clear()

    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(getattr(logging, level))
        root_logger.addHandler(console_handler)
    
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, mode='a', encoding='utf-8')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, level))
        root_logger.addHandler(file_handler)
    
    _configure_third_party_loggers()
    
    logger = logging.getLogger(__name__)
    logger.info(
        "Logging configured: level=%s, console=%s, file=%s", 
        level, log_to_console, log_file or "None",
        extra={'correlation_id': 'SYSTEM', 'class_name': 'LoggingConfig'}
    )


def _configure_third_party_loggers():
    """Configure log levels for noisy third-party libraries."""
    noisy_loggers = {
        "httpx": logging.WARNING,
        "httpcore": logging.WARNING,
        "urllib3": logging.WARNING,
        "openai": logging.WARNING,
        "anthropic._base_client": logging.WARNING,
        "uvicorn.access": logging.WARNING,
        "uvicorn.error": logging.INFO,
        "git": logging.WARNING,
        "github": logging.WARNING,
    }
    
    for logger_name, log_level in noisy_loggers.items():
        logging.getLogger(logger_name).setLevel(log_level)


class ContextLogger:
    """
    Logger wrapper for class context.
    
    Usage:
        logger = ContextLogger(__name__, self.__class__.__name__)
        logger.info("Message", correlation_id="12345678")
    """
    
    def __init__(self, name: str, class_name: str = "N/A"):
        self.logger = logging.getLogger(name)
        self.class_name = class_name
    
    def _log(self, level: int, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        """Internal logging method with context."""
        extra = kwargs.pop('extra', {})
        extra['correlation_id'] = correlation_id or 'N/A'
        extra['class_name'] = self.class_name
        
        self.logger.log(level, msg, *args, extra=extra, **kwargs)
    
    def debug(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        self._log(logging.DEBUG, msg, correlation_id, *args, **kwargs)
    
    def info(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        self._log(logging.INFO, msg, correlation_id, *args, **kwargs)
    
    def warning(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        self._log(logging.WARNING, msg, correlation_id, *args, **kwargs)
    
    def error(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        self._log(logging.ERROR, msg, correlation_id, *args, **kwargs)
    
    def exception(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        kwargs['exc_info'] = True
        self._log(logging.ERROR, msg, correlation_id, *args, **kwargs)
    
    def critical(self, msg: str, correlation_id: Optional[str] = None, *args, **kwargs):
        self._log(logging.CRITICAL, msg, correlation_id, *args, **kwargs)


def get_logger(name: str, class_name: str = "N/A") -> ContextLogger:
    """
    Get a context-aware logger instance.
    
    Args:
        name: Logger name (typically __name__ of the module)
        class_name: Name of the class using the logger
        
    Returns:
        ContextLogger instance with correlation_id support
    """
    return ContextLogger(name, class_name)


def set_log_level(level: str) -> None:
    """
    Change the log level at runtime.
    
    Args:
        level: New log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    level = level.upper()
    logging.getLogger().setLevel(getattr(logging, level))
    
    logger = get_logger(__name__, "LoggingConfig")
    logger.info("Log level changed to: %s" % level, correlation_id="SYSTEM")


def enable_debug_mode():
    """Enable debug mode with verbose logging."""
    set_log_level("DEBUG")
    
    logging.getLogger("anthropic").setLevel(logging.WARNING)
    logging.getLogger("anthropic._base_client").setLevel(logging.WARNING)
    logging.getLogger("stainless").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.INFO)
    logging.getLogger("git").setLevel(logging.INFO)
    
    logger = get_logger(__name__, "LoggingConfig")
    logger.debug("Debug mode enabled", correlation_id="SYSTEM")


def disable_debug_mode():
    """Disable debug mode, return to INFO level."""
    set_log_level("INFO")
    _configure_third_party_loggers()
    
    logger = get_logger(__name__, "LoggingConfig")
    logger.info("Debug mode disabled", correlation_id="SYSTEM")