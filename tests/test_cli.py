from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from pytest_mock import MockerFixture

from pytest_insight.plugin import pytest_configure, pytest_terminal_summary


def test_terminal_summary(mocker: MockerFixture):
    """Mock terminal reporter and ensure pytest-insight summary hook runs."""
    terminal_reporter = mocker.Mock(spec=TerminalReporter)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)

    pytest_terminal_summary(terminal_reporter, exitstatus=0)
    terminal_reporter.write_line.assert_called_with(
        "\n[pytest-insight] Test history updated."
    )


def test_pytest_configure(mocker: MockerFixture):
    """Ensure pytest_configure initializes storage when insight is enabled."""
    config = mocker.Mock(spec=Config)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)
    mock_storage = mocker.patch("pytest_insight.storage.JSONTestResultStorage")

    pytest_configure(config)
    mock_storage.assert_called_once()
