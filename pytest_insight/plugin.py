from datetime import datetime
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

    # Initialize both test history and current session
    if insight_enabled():
        config._insight_test_history = TestHistory()

    # Initialize persistent storage at the beginning of the pytest session and ensure a single instance is used
    global storage
    if storage is None:
        storage = JSONTestResultStorage()


@pytest.hookimpl
def pytest_sessionstart(session: Session) -> None:
    """Initialize test session tracking."""
    if not insight_enabled():
        print("[pytest-insight] pytest_sessionstart: Insight not enabled, skipping log report.")
        return

    session.config._insight_test_session = TestSession(
        sut_name="default_sut",
        session_id=f"session-{int(datetime.utcnow().timestamp())}",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow(),
    )
    session.config._insight_start_time = datetime.utcnow()


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Capture individual test results and store them in the session."""
    if not insight_enabled():
        print("[pytest-insight] pytest_runtest_makereport: Insight not enabled, skipping log report.")
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
        print("[pytest-insight] pytest_runtest_protocol: Insight not enabled, skipping log report.")
        return None

    insight_test_session = item.config._insight_test_session
    current_test = TestResult(
        nodeid=item.nodeid,
        outcome="UNKNOWN",  # Will be updated in runtest_logreport
        start_time=datetime.utcnow(),
        duration=0.0,
    )

    # Store test result in item, so we can retrieve it in pytest_runtest_logreport
    item.user_properties.append(("current_test", current_test))
    # Also store config explicitly for later use
    item.user_properties.append(("config", item.config))

    # Check if this is a rerun
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
        print("[pytest-insight] pytest_runtest_logreport: Insight not enabled, skipping log report.")
        return

    # ✅ Extract `config` and `current_test` from user properties
    config = None
    current_test = None
    for name, value in getattr(report, "user_properties", []):
        if name == "current_test":
            current_test = value
        elif name == "config":
            config = value

    if not config:
        print("[pytest-insight] ❌ ERROR: No config found in report. Skipping test result.")
        return

    insight_test_session = config._insight_test_session

    if not current_test:
        print(f"[pytest-insight] ⚠️ WARNING: _current_test not found for {report.nodeid}")
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

        insight_test_session.add_test_result(current_test)

    # Check if rerun info was set in runtest_protocol
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
        print("[pytest-insight] pytest_sessionfinish: Insight not enabled, skipping log report.")
        return

    test_session = session.config._insight_test_session
    if not test_session:
        print("[pytest-insight] ERROR: No test session found at finish.")
        return
    test_session.session_stop_time = datetime.utcnow()
    storage.save_session(test_session)


@pytest.hookimpl
def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """Extract test results summary and store in insight_test_session."""
    if not insight_enabled():
        print("[pytest-insight] pytest_terminal_summary: Insight not enabled, skipping log report.")
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
