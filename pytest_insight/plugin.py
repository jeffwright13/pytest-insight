from datetime import datetime, timedelta
from typing import Optional

import pytest
from _pytest.config import Config
from _pytest.main import Session
from _pytest.reports import TestReport

from pytest_insight.models import (
    OutputFields,
    OutputFieldType,
    RerunTestGroup,
    TestHistory,
    TestResult,
    TestSession,
)

_INSIGHT_INITIALIZED: bool = False
_INSIGHT_ENABLED: bool = False


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
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin for test history analysis",
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

    if insight_enabled():
        # Initialize both test history and current session
        config._insight_test_history = TestHistory()


@pytest.hookimpl
def pytest_sessionstart(session: Session) -> None:
    """Initialize test session tracking."""
    if not insight_enabled():
        return

    session.config._insight_test_session = TestSession(
        sut_name="default_sut",
        session_id=f"session-{int(datetime.utcnow().timestamp())}",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow(),
        session_duration=timedelta(0),
    )
    session.config._insight_start_time = datetime.utcnow()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture individual test results and store them in the session."""
    if not insight_enabled():
        yield
    else:
        outcome = yield
        report = outcome.get_result()

        # Determine outcome based on all phases
        if report.when in ("setup", "teardown") and report.outcome == "failed":
            test_outcome = "error"
        elif hasattr(report, "wasxfail"):
            test_outcome = "xpassed" if report.outcome in ("passed", "failed") else "xfailed"
        else:
            test_outcome = report.outcome

        # Create and store TestResult
        test_result = TestResult(
            nodeid=report.nodeid,
            outcome=test_outcome.upper(),
            start_time=datetime.utcnow(),
            duration=getattr(report, "duration", 0.0),
            capstderr=getattr(report, "capstderr", ""),
            capstdout=getattr(report, "capstdout", ""),
            longreprtext=str(report.longrepr) if report.longrepr else "",
            has_warning=report.outcome == "WARNING",
        )

        insight_test_session = item.session.config._insight_test_session
        insight_test_session.test_results.append(test_result)


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_protocol(item, nextitem):
    """Hook into test execution to track when tests start."""
    if not insight_enabled():
        return None

    insight_test_session = item.config._insight_test_session
    current_test = TestResult(
        nodeid=item.nodeid,
        outcome="UNKNOWN",  # Will be updated in runtest_logreport
        start_time=datetime.utcnow(),
        duration=0.0,
    )
    # Store temporarily to update later
    item.config._current_test = current_test

    if hasattr(item, "execution_count"):
        # This is a rerun
        rerun_group = next((g for g in insight_test_session.rerun_test_groups if g.nodeid == item.nodeid), None)
        if not rerun_group:
            rerun_group = RerunTestGroup(
                nodeid=item.nodeid,
                final_outcome="UNKNOWN",  # Will update in logreport
            )
            insight_test_session.rerun_test_groups.append(rerun_group)
        item.config._current_rerun_group = rerun_group

    return None


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_logreport(report: TestReport) -> None:
    """Capture test results from pytest's internal reports."""
    if not insight_enabled():
        return

    # Get session config through the pytest session
    try:
        # Get config through pytest's current session
        config = pytest.Session._current.config
    except (AttributeError, RuntimeError):
        return

    insight_test_session = config._insight_test_session
    current_test = getattr(config, "_current_test", None)

    if not current_test:
        return

    if report.when == "call" or (report.when == "setup" and report.outcome == "skipped"):
        # Update the current test with final results
        current_test.outcome = report.outcome.upper()
        current_test.duration = report.duration
        current_test.longreprtext = str(report.longrepr) if report.longrepr else ""
        current_test.caplog = report.caplog if hasattr(report, "caplog") else ""
        current_test.capstderr = report.capstderr if hasattr(report, "capstderr") else ""
        current_test.capstdout = report.capstdout if hasattr(report, "capstdout") else ""
        current_test.has_warning = bool(getattr(report, "warnings", False))

        # Add to insight_test_session
        insight_test_session.add_test_result(current_test)

    rerun_group = getattr(config, "_current_rerun_group", None)
    if rerun_group and report.when == "call":
        rerun_group.reruns.append(current_test)
        if not hasattr(report, "will_rerun"):
            # This is the final attempt
            rerun_group.final_outcome = report.outcome.upper()


@pytest.hookimpl
def pytest_sessionfinish(session: Session, exitstatus):
    """Store final session results in TestSession and add to TestHistory."""
    if not insight_enabled():
        return

    end_time = datetime.utcnow()
    duration = end_time - session.config._insight_start_time

    test_session = session.config._insight_test_session
    test_session.session_stop_time = end_time
    test_session.session_duration = duration

    # Store session in history
    session.config._insight_test_history.add_test_session(test_session)


@pytest.hookimpl
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Extract test results summary and store in insight_test_session."""
    if not insight_enabled():
        return

    insight_test_session = config._insight_test_session
    fields = OutputFields()

    # Extract stats with consistent field types
    stats_mapping = {
        "warnings": (OutputFieldType.WARNINGS_SUMMARY, lambda w: str(w.message)),
        "error": (OutputFieldType.ERRORS, lambda e: str(e.longreprtext)),
        "rerun": (OutputFieldType.RERUN_TEST_SUMMARY, lambda r: str(r.nodeid)),
    }

    # Process each stat type
    for stat_key, (field_type, formatter) in stats_mapping.items():
        items = terminalreporter.stats.get(stat_key, [])
        if items:
            fields.set(field_type, "\n".join(formatter(item) for item in items))  # Changed from set_field to set

    # Create and store summary line
    counts = insight_test_session.test_counts
    summary = f"=== {counts['passed']} passed, " f"{counts['failed']} failed, " f"{counts['skipped']} skipped ==="
    fields.set(OutputFieldType.SHORT_TEST_SUMMARY, summary)  # Changed from set_field to set

    insight_test_session.output_fields = fields
