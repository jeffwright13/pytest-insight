from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from pytest_insight.plugin import pytest_configure, pytest_terminal_summary
from pytest_mock import MockerFixture


def test_terminal_summary(mocker: MockerFixture):
    """Mock terminal reporter and ensure pytest-insight summary hook runs."""
    # Create mock terminal reporter with required attributes
    terminal_reporter = mocker.Mock(spec=TerminalReporter)
    terminal_reporter.stats = {
        "passed": [],
        "failed": [],
        "skipped": [],
        "xfailed": [],
        "xpassed": [],
        "error": [],
        "rerun": [],
    }

    # Mock config and plugin state
    config = mocker.Mock(spec=Config)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)

    # Run the hook
    pytest_terminal_summary(terminalreporter=terminal_reporter, exitstatus=0, config=config)
    terminal_reporter.write_line.assert_called_with("\n[pytest-insight] Test history updated.")


def test_pytest_configure(mocker: MockerFixture):
    """Ensure pytest_configure initializes storage when insight is enabled."""
    config = mocker.Mock(spec=Config)
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)
    mock_storage = mocker.patch("pytest_insight.plugin.JSONStorage")  # Updated path


from datetime import datetime

import pytest
from pytest_insight.models import TestResult
from pytest_insight.storage import JSONStorage
from pytest_mock import MockerFixture


@pytest.fixture
def mock_terminal_reporter(mocker: MockerFixture):
    """Create a mock terminal reporter with standard attributes."""
    reporter = mocker.Mock()
    reporter.stats = {"passed": [], "failed": [], "skipped": [], "xfailed": [], "xpassed": [], "error": [], "rerun": []}
    return reporter


@pytest.fixture
def mock_config(mocker: MockerFixture):
    """Create a mock pytest config."""
    config = mocker.Mock()
    mocker.patch("pytest_insight.plugin.insight_enabled", return_value=True)
    return config


@pytest.fixture
def sample_test_result():
    """Create a sample test result."""
    return TestResult(
        nodeid="test_example.py::test_something",
        outcome="PASSED",
        start_time=datetime.utcnow(),
        duration=1.5,
        has_warning=False,
    )


@pytest.fixture
def temp_storage(tmp_path):
    """Create temporary storage for tests."""
    storage_file = tmp_path / "test_sessions.json"
    return JSONStorage(storage_file)
    pytest_configure(config)
    mock_storage.assert_called_once()
