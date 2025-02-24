from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from pytest_mock import MockerFixture

from pytest_insight.plugin import pytest_configure, pytest_terminal_summary


def test_terminal_summary(mocker: MockerFixture):
    """Mock terminal reporter and ensure pytest-insight summary hook runs."""
    # Create mock terminal reporter with required attributes
    terminal_reporter = mocker.Mock(spec=TerminalReporter)
    terminal_reporter.stats = {
        'passed': [],
        'failed': [],
        'skipped': [],
        'xfailed': [],
        'xpassed': [],
        'error': [],
        'rerun': []
    }

    # Mock config and plugin state
    config = mocker.Mock(spec=Config)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)

    # Run the hook
    pytest_terminal_summary(terminalreporter=terminal_reporter, exitstatus=0, config=config)
    terminal_reporter.write_line.assert_called_with(
        "\n[pytest-insight] Test history updated."
    )


def test_pytest_configure(mocker: MockerFixture):
    """Ensure pytest_configure initializes storage when insight is enabled."""
    config = mocker.Mock(spec=Config)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)
    mock_storage = mocker.patch("pytest_insight.plugin.JSONStorage")  # Updated path

    pytest_configure(config)
    mock_storage.assert_called_once()
