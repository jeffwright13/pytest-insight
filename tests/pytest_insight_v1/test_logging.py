"""Test module to verify UTC timestamp logging."""

import logging
import os
import re

import pytest
from pytest_insight.utils.logging_setup import UTCFormatter, setup_logging


def test_utc_formatter():
    """Test that UTCFormatter correctly formats timestamps in UTC."""
    # Create a test formatter
    formatter = UTCFormatter("%(asctime)s [UTC] - %(name)s - %(levelname)s - %(message)s")

    # Create a log record with a known timestamp
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="Test message",
        args=(),
        exc_info=None,
    )

    # Format the record
    formatted = formatter.format(record)

    # Verify the timestamp is in UTC format (ISO 8601 with UTC indicator)
    timestamp_pattern = r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+\+00:00 \[UTC\]"
    assert re.search(timestamp_pattern, formatted), f"Timestamp not in UTC format: {formatted}"


def test_logger_uses_utc():
    """Test that the logger uses UTC timestamps."""
    # Set up a test logger
    test_logger = setup_logging(logger_name="test_utc_logger", log_level="DEBUG")

    # Log a test message
    test_logger.info("Test message with UTC timestamp")

    # Verify the logger is configured with our UTCFormatter
    for handler in test_logger.handlers:
        assert isinstance(handler.formatter, UTCFormatter), "Logger not using UTCFormatter"


def test_environment_variables():
    """Test that the logger respects environment variables."""
    # Save original environment variables
    original_log_level = os.environ.get("PYTEST_INSIGHT_LOG_LEVEL")
    original_log_file = os.environ.get("PYTEST_INSIGHT_LOG_FILE")

    try:
        # Set environment variables
        os.environ["PYTEST_INSIGHT_LOG_LEVEL"] = "ERROR"
        os.environ["PYTEST_INSIGHT_LOG_FILE"] = "/tmp/test_log.txt"

        # Create a new logger
        test_logger = setup_logging(logger_name="test_env_logger")

        # Check log level
        assert test_logger.level == logging.ERROR, "Logger did not respect PYTEST_INSIGHT_LOG_LEVEL"

        # Check for file handler
        has_file_handler = any(isinstance(handler, logging.FileHandler) for handler in test_logger.handlers)
        assert has_file_handler, "Logger did not respect PYTEST_INSIGHT_LOG_FILE"

    finally:
        # Restore original environment variables
        if original_log_level:
            os.environ["PYTEST_INSIGHT_LOG_LEVEL"] = original_log_level
        else:
            os.environ.pop("PYTEST_INSIGHT_LOG_LEVEL", None)

        if original_log_file:
            os.environ["PYTEST_INSIGHT_LOG_FILE"] = original_log_file
        else:
            os.environ.pop("PYTEST_INSIGHT_LOG_FILE", None)


@pytest.mark.parametrize(
    "log_level,expected_level",
    [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
        ("invalid", logging.INFO),  # Default to INFO for invalid levels
    ],
)
def test_log_level_parsing(log_level, expected_level):
    """Test that log levels are correctly parsed."""
    # Set up logger with specific log level
    test_logger = setup_logging(logger_name=f"test_level_{log_level}", log_level=log_level)

    # Check that the logger has the expected level
    assert test_logger.level == expected_level, f"Expected level {expected_level} for '{log_level}'"
