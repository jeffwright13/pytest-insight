from pytest import ExitCode
from _pytest.reports import CollectReport
from datetime import datetime
from typing import Optional, Union

import pytest
from _pytest.config import Config
from _pytest.terminal import TerminalReporter, WarningReport
from _pytest.reports import TestReport, CollectReport

from pytest_insight.models import TestResult, TestSession
from pytest_insight.storage import JSONTestResultStorage

_INSIGHT_INITIALIZED: bool = False
_INSIGHT_ENABLED: bool = False

# Initialize storage once, at the module level
storage = None

def insight_enabled(config: Optional[Config] = None) -> bool:
    """
    Helper function to set/check if pytest-insight is enabled.

    When called with config, sets the enabled state.
    When called without config, returns the current state.
    """
    global _INSIGHT_INITIALIZED, _INSIGHT_ENABLED

    if config is not None and not _INSIGHT_INITIALIZED:
        _INSIGHT_ENABLED = bool(getattr(config.option, "insight", False))
        _INSIGHT_INITIALIZED = True
    return _INSIGHT_ENABLED

def pytest_addoption(parser):
    """Add pytest-insight command line options."""
    group = parser.getgroup("insight")
    group.addoption(
        "--insight",
        dest="insight",
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin for test-run history analysis",
    )

    parser.addini(
        "insight",
        type="bool",
        help="Enable the insight plugin, providing test history analysis",
        default=False,
    )

@pytest.hookimpl
def pytest_configure(config: Config):
    """Configure the plugin if enabled."""
    insight_enabled(config)

    # Initialize persistent storage at the beginning of the pytest session and ensure a single instance is used
    global storage
    if storage is None:
        storage = JSONTestResultStorage()

@pytest.hookimpl
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
    """Extract test results summary and store in insight_test_session."""
    if not insight_enabled():
        print("[pytest-insight] pytest_terminal_summary: Insight not enabled, skipping log report.")
        return

    stats = terminalreporter.stats
    test_results = []

    for outcome, reports in stats.items():
        for report in reports:
            if isinstance(report, TestReport):
                test_result = TestResult(
                    nodeid=report.nodeid,
                    outcome=report.outcome.upper(),
                    start_time=datetime.fromtimestamp(report.start),
                    duration=report.duration,
                    caplog=getattr(report, "caplog", ""),
                    capstderr=getattr(report, "capstderr", ""),
                    capstdout=getattr(report, "capstdout", ""),
                    longreprtext=str(report.longrepr) if report.longrepr else "",
                    has_warning=bool(getattr(report, "warning_messages", [])),
                )
                test_results.append(test_result)
            elif isinstance(report, WarningReport):
                test_result = TestResult(
                    nodeid=report.nodeid,
                    outcome="WARNING",
                    start_time=datetime.now(),
                    duration=0.0,
                    caplog=str(report.message),
                    capstderr="",
                    capstdout="",
                    longreprtext="",
                    has_warning=True,
                )
                test_results.append(test_result)

    # Convert raw dictionary into a proper TestSession object
    session = TestSession(
        sut_name="default_sut",
        session_id=str(datetime.now().timestamp()),  # Unique session ID
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),
        test_results=test_results,  # Include the list of TestResult objects
    )
    storage.save_session(session)

    # Print summary
    terminalreporter.write_sep("=", "insight summary info")
    summary = {outcome: len(reports) for outcome, reports in stats.items()}
    for outcome, count in summary.items():
        terminalreporter.write_line(f"  {outcome.upper()}: {count} tests")
