"""Logging configuration for pytest-insight.

This module provides a consistent logging setup for all pytest-insight components.
It configures loggers with appropriate handlers and formatters.
"""

import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional


class UTCFormatter(logging.Formatter):
    """Logging formatter that uses UTC timestamps."""

    def formatTime(self, record, datefmt=None):
        """Format the time in UTC."""
        dt = datetime.fromtimestamp(record.created, tz=timezone.utc)
        if datefmt:
            return dt.strftime(datefmt)
        else:
            return dt.isoformat(timespec="milliseconds")


def setup_logging(
    logger_name: str = "pytest_insight",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
) -> logging.Logger:
    """Set up logging for pytest-insight.

    Args:
        logger_name: Name of the logger to configure
        log_level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  If None, uses PYTEST_INSIGHT_LOG_LEVEL env var or defaults to INFO
        log_file: Path to log file. If None, logs to stderr only.
                 Can be overridden with PYTEST_INSIGHT_LOG_FILE env var.

    Returns:
        Configured logger instance
    """
    # Get logger
    logger = logging.getLogger(logger_name)

    # If logger is already configured, return it
    if logger.handlers:
        return logger

    # Determine log level
    if log_level is None:
        log_level = os.environ.get("PYTEST_INSIGHT_LOG_LEVEL", "INFO")

    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    logger.setLevel(numeric_level)

    # Create formatter with UTC timestamps
    formatter = UTCFormatter(
        "%(asctime)s [UTC] - %(name)s - %(levelname)s - %(message)s"
    )

    # Console handler (stderr)
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (optional)
    if log_file is None:
        log_file = os.environ.get("PYTEST_INSIGHT_LOG_FILE", None)

    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except (IOError, PermissionError) as e:
            logger.warning(f"Could not create log file at {log_file}: {e}")

    return logger


# Create a default logger for import
logger = setup_logging()
