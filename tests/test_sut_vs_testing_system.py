"""Tests for the relationship between SUT name and testing system."""

import os
import re
import socket
from unittest.mock import MagicMock, patch

from pytest_insight.plugin import pytest_terminal_summary


def test_sut_name_defaults_to_directory_name():
    """Test that SUT name defaults to the current directory name when not specified."""

    # Mock the necessary objects and functions
    class MockConfig:
        def __init__(self):
            self.pluginmanager = MagicMock()
            self.pluginmanager.get_plugins.return_value = []

        def getoption(self, option, default=None):
            return None if option == "insight_sut" else default

    class MockTerminalReporter:
        stats = {}

        def write_line(self, line, **kwargs):
            pass

        def write_sep(self, sep, title, **kwargs):
            pass

    # Get the expected directory name
    expected_dir_name = os.path.basename(os.getcwd())
    expected_dir_name = re.sub(r"[^a-zA-Z0-9_-]", "-", expected_dir_name).lower()

    # Mock the TestSession creation to capture the arguments
    with (
        patch("pytest_insight.plugin.TestSession") as mock_test_session,
        patch("pytest_insight.plugin.storage"),
        patch("pytest_insight.plugin.insight_enabled", return_value=True),
        patch(
            "pytest_insight.plugin.group_tests_into_rerun_test_groups", return_value=[]
        ),
        patch("pytest_insight.plugin.datetime") as mock_datetime,
        patch("pytest_insight.core.analysis.Analysis"),
        patch("pytest_insight.core.insights.Insights"),
    ):
        # Mock datetime.now() to return a consistent value
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp.return_value = mock_now

        # Call the function under test
        pytest_terminal_summary(MockTerminalReporter(), 0, MockConfig())

        # Verify that TestSession was called with the expected SUT name
        call_kwargs = mock_test_session.call_args.kwargs
        assert call_kwargs["sut_name"] == expected_dir_name

        # Verify that hostname is in the testing_system dict, not used as SUT name
        hostname = socket.gethostname()
        assert call_kwargs["testing_system"]["hostname"] == hostname


def test_sut_name_uses_custom_value_when_specified():
    """Test that SUT name uses the custom value when specified."""

    # Mock the necessary objects and functions
    class MockConfig:
        def __init__(self):
            self.pluginmanager = MagicMock()
            self.pluginmanager.get_plugins.return_value = []

        def getoption(self, option, default=None):
            return "custom-sut-name" if option == "insight_sut" else default

    class MockTerminalReporter:
        stats = {}

        def write_line(self, line, **kwargs):
            pass

        def write_sep(self, sep, title, **kwargs):
            pass

    # Mock the TestSession creation to capture the arguments
    with (
        patch("pytest_insight.plugin.TestSession") as mock_test_session,
        patch("pytest_insight.plugin.storage"),
        patch("pytest_insight.plugin.insight_enabled", return_value=True),
        patch(
            "pytest_insight.plugin.group_tests_into_rerun_test_groups", return_value=[]
        ),
        patch("pytest_insight.plugin.datetime") as mock_datetime,
        patch("pytest_insight.core.analysis.Analysis"),
        patch("pytest_insight.core.insights.Insights"),
    ):
        # Mock datetime.now() to return a consistent value
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp.return_value = mock_now

        # Call the function under test
        pytest_terminal_summary(MockTerminalReporter(), 0, MockConfig())

        # Verify that TestSession was called with the expected SUT name
        call_kwargs = mock_test_session.call_args.kwargs
        assert call_kwargs["sut_name"] == "custom-sut-name"

        # Verify that hostname is in the testing_system dict, not used as SUT name
        hostname = socket.gethostname()
        assert call_kwargs["testing_system"]["hostname"] == hostname


def test_sut_name_fallback_when_directory_name_fails():
    """Test that SUT name falls back to 'unknown-sut' when directory name retrieval fails."""

    # Mock the necessary objects and functions
    class MockConfig:
        def __init__(self):
            self.pluginmanager = MagicMock()
            self.pluginmanager.get_plugins.return_value = []

        def getoption(self, option, default=None):
            return None if option == "insight_sut" else default

    class MockTerminalReporter:
        stats = {}

        def write_line(self, line, **kwargs):
            pass

        def write_sep(self, sep, title, **kwargs):
            pass

    # Mock the TestSession creation to capture the arguments
    with (
        patch("pytest_insight.plugin.TestSession") as mock_test_session,
        patch("pytest_insight.plugin.storage"),
        patch("pytest_insight.plugin.insight_enabled", return_value=True),
        patch(
            "pytest_insight.plugin.group_tests_into_rerun_test_groups", return_value=[]
        ),
        patch("os.path.basename", side_effect=OSError("Mocked error")),
        patch("pytest_insight.plugin.datetime") as mock_datetime,
        patch("pytest_insight.core.analysis.Analysis"),
        patch("pytest_insight.core.insights.Insights"),
    ):
        # Mock datetime.now() to return a consistent value
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp.return_value = mock_now

        # Call the function under test
        pytest_terminal_summary(MockTerminalReporter(), 0, MockConfig())

        # Verify that TestSession was called with the fallback SUT name
        call_kwargs = mock_test_session.call_args.kwargs
        assert call_kwargs["sut_name"] == "unknown-sut"

        # Verify that hostname is in the testing_system dict, not used as SUT name
        hostname = socket.gethostname()
        assert call_kwargs["testing_system"]["hostname"] == hostname


def test_test_system_name_override():
    """Test that --insight-test-system-name overrides the default hostname."""

    # Mock the necessary objects and functions
    class MockConfig:
        def __init__(self):
            self.pluginmanager = MagicMock()
            self.pluginmanager.get_plugins.return_value = []

        def getoption(self, option, default=None):
            if option == "insight_test_system_name":
                return "custom-test-system"
            return default if option != "insight_sut" else None

    class MockTerminalReporter:
        stats = {}

        def write_line(self, line, **kwargs):
            pass

        def write_sep(self, sep, title, **kwargs):
            pass

    # Mock the TestSession creation to capture the arguments
    with (
        patch("pytest_insight.plugin.TestSession") as mock_test_session,
        patch("pytest_insight.plugin.storage"),
        patch("pytest_insight.plugin.insight_enabled", return_value=True),
        patch(
            "pytest_insight.plugin.group_tests_into_rerun_test_groups", return_value=[]
        ),
        patch("pytest_insight.plugin.datetime") as mock_datetime,
        patch("pytest_insight.core.analysis.Analysis"),
        patch("pytest_insight.core.insights.Insights"),
    ):
        # Mock datetime.now() to return a consistent value
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        mock_datetime.fromtimestamp.return_value = mock_now

        # Call the function under test
        pytest_terminal_summary(MockTerminalReporter(), 0, MockConfig())

        # Verify that TestSession was called with the custom testing system name
        call_kwargs = mock_test_session.call_args.kwargs
        assert call_kwargs["testing_system"]["name"] == "custom-test-system"

        # Verify that hostname is still present
        hostname = socket.gethostname()
        assert call_kwargs["testing_system"]["hostname"] == hostname
