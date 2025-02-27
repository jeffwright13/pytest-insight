import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.storage import JSONStorage, get_storage_instance

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
    """Add pytest-insight specific options."""
    group = parser.getgroup("insight", "pytest-insight")
    group.addoption("--insight", action="store_true", help="Enable pytest-insight")
    group.addoption(
        "--insight-sut",
        default="default_sut",
        dest="insight_sut",  # Add dest to make option accessible
        help="Specify the System Under Test (SUT) name",
    )


@pytest.hookimpl
def pytest_configure(config: Config):
    """Configure the plugin if enabled."""
    insight_enabled(config)

    # Initialize persistent storage at the beginning of the pytest session and ensure a single instance is used
    global storage
    if storage is None:
        storage = JSONStorage()


@pytest.hookimpl
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
    """Process test results and store in TestSession."""
    if not insight_enabled(config):
        return

    storage = get_storage_instance()
    sut_name = config.getoption("insight_sut", "default_sut")  # Get SUT name from pytest option

    stats = terminalreporter.stats
    test_results = []
    session_start = None
    session_end = None

    # Process all test reports
    for outcome, reports in stats.items():
        if outcome == "warnings":
            continue  # Handle warnings separately

        for report in reports:
            if not isinstance(report, TestReport):
                continue

            # Capture only call-phase or error failures from setup/teardown
            if report.when == "call" or (
                report.when in ("setup", "teardown") and report.outcome in ("failed", "error")
            ):
                report_time = datetime.fromtimestamp(report.start)

                if session_start is None or report_time < session_start:
                    session_start = report_time
                report_end = report_time + timedelta(seconds=report.duration)
                if session_end is None or report_end > session_end:
                    session_end = report_end

                test_results.append(
                    TestResult(
                        nodeid=report.nodeid,
                        outcome=TestOutcome.from_str(outcome.upper()),  # Convert string to enum
                        start_time=report_time,
                        duration=report.duration,
                        caplog=getattr(report, "caplog", ""),
                        capstderr=getattr(report, "capstderr", ""),
                        capstdout=getattr(report, "capstdout", ""),
                        longreprtext=str(report.longrepr) if report.longrepr else "",
                        has_warning=bool(getattr(report, "warning_messages", [])),
                    )
                )

    # Try to match individual WarningReport instances to TestResult instances, setting 'has_warning' to True if found
    if "warnings" in stats:
        for report in stats["warnings"]:
            if isinstance(report, WarningReport):
                # Find the corresponding TestResult instance
                for test_result in test_results:
                    if test_result.nodeid == report.nodeid:
                        test_result.has_warning = True
                        break

    # Fallback for session timing
    session_start = session_start or datetime.now()
    session_end = session_end or datetime.now()

    # Generate unique session ID
    session_id = f"session-{session_start.strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}"

    # # Process rerun groups
    rerun_test_group_list = group_rerun_tests(test_results)

    # Create and store session with SUT name
    session = TestSession(
        # session_id=f"session-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')[:13]}",
        session_id=session_id,
        sut_name=sut_name,  # Use the SUT name from pytest option
        session_start_time=session_start or datetime.now(),
        session_stop_time=session_end or datetime.now(),
        test_results=test_results,
        rerun_test_groups=rerun_test_group_list,
        session_tags={
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "environment": config.getoption("environment", "test"),
        },
    )

    storage.save_session(session)

    # Print summary
    terminalreporter.write_sep("=", "pytest-insight summary", cyan=True)
    outcome_counts = Counter(result.outcome.to_str() for result in test_results)  # Convert to strings
    for outcome, count in sorted(outcome_counts.items()):
        terminalreporter.write_line(f"  {outcome}: {count}")
    print()


def group_rerun_tests(test_results: List[TestResult]) -> List[RerunTestGroup]:
    """Sort rerun tests into groups and determine final outcome."""
    rerun_groups = {}

    # Collect rerun instances
    for test in test_results:
        if test.outcome == TestOutcome.RERUN:  # Compare with enum value directly
            if test.nodeid not in rerun_groups:
                rerun_groups[test.nodeid] = RerunTestGroup(nodeid=test.nodeid, final_outcome="UNKNOWN")
            rerun_groups[test.nodeid].add_rerun(test)

    # Assign final outcomes
    for test in test_results:
        if test.outcome != TestOutcome.RERUN and test.nodeid in rerun_groups:
            rerun_groups[test.nodeid].final_outcome = test.outcome.to_str()  # Convert enum to string
            rerun_groups[test.nodeid].add_test(test)

    return list(rerun_groups.values())


def populate_rerun_groups(test_session: TestSession) -> None:
    """Attach rerun test groups to the test session."""
    rerun_groups = group_rerun_tests(test_session.test_results)
    test_session.rerun_test_groups = rerun_groups  # Store groups in session
