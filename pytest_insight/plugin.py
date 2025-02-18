from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pytest
import sys
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.models import RerunTestGroup, TestResult, TestSession
from pytest_insight.storage import JSONStorage

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
        storage = JSONStorage()





@pytest.hookimpl
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
    """Process test results and store in TestSession."""
    if not insight_enabled():
        print("[pytest-insight] Insight not enabled, skipping.")
        return

    # Get all test reports
    stats = terminalreporter.stats
    test_results = []
    session_start = None
    session_end = None

    # Mapping for pytest outcomes to our format
    outcome_map = {
        "passed": "PASSED",
        "failed": "FAILED",
        "skipped": "SKIPPED",
        "xfailed": "XFAILED",
        "xpassed": "XPASSED",
        "error": "ERROR",
        "rerun": "RERUN",
        "warnings": "WARNING"
    }

    # Process each report type
    for outcome, reports in stats.items():
        for report in reports:
            # Only process TestReport instances in 'call' phase
            if isinstance(report, TestReport) and report.when == "call":
                # Track session timing
                report_time = datetime.fromtimestamp(report.start)
                if session_start is None or report_time < session_start:
                    session_start = report_time
                report_end = report_time + timedelta(seconds=report.duration)
                if session_end is None or report_end > session_end:
                    session_end = report_end

                # Create TestResult with all available info
                test_result = TestResult(
                    nodeid=report.nodeid,
                    outcome=outcome_map.get(report.outcome, "UNKNOWN"),
                    start_time=report_time,
                    duration=report.duration,
                    caplog=getattr(report, "caplog", ""),
                    capstderr=getattr(report, "capstderr", ""),
                    capstdout=getattr(report, "capstdout", ""),
                    longreprtext=str(report.longrepr) if report.longrepr else "",
                    has_warning=bool(getattr(report, "warning_messages", []))
                )

                test_results.append(test_result)

            # Handle warning reports separately
            elif isinstance(report, WarningReport):
                test_results.append(TestResult(
                    nodeid=report.nodeid,
                    outcome="WARNING",
                    start_time=datetime.now(),
                    duration=0.0,
                    caplog=str(report.message),
                    has_warning=True
                ))

    # Fallback for session timing
    if not session_start:
        session_start = datetime.now()
    if not session_end:
        session_end = datetime.now()

    # Create TestSession with all results
    session = TestSession(
        sut_name=config.getoption("insight_sut_name", "default_sut"),
        session_id=f"session-{int(session_start.timestamp())}",
        session_start_time=session_start,
        session_stop_time=session_end,
        test_results=test_results,
        session_tags={
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "environment": config.getoption("environment", "test")
        }
    )

    # Process rerun groups if any
    populate_rerun_groups(session)

    # Store session
    storage.save_session(session)

    # Print summary
    terminalreporter.write_sep("=", "pytest-insight summary", cyan=True)
    outcome_counts = Counter(result.outcome for result in test_results)
    for outcome, count in outcome_counts.items():
        terminalreporter.write_line(f"  {outcome}: {count}")



# @pytest.hookimpl
# def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
#     """Extract test results summary and store in insight_test_session."""
#     if not insight_enabled():
#         print("[pytest-insight] pytest_terminal_summary: Insight not enabled, skipping log report.")
#         return

#     stats = terminalreporter.stats

#     items = dict(stats.items())

#     test_results = []

#     for outcome, reports in stats.items():
#         for report in reports:
#             if isinstance(report, TestReport):
#                 test_result = TestResult(
#                     nodeid=report.nodeid,
#                     outcome=report.outcome.upper(),
#                     start_time=datetime.fromtimestamp(report.start),
#                     duration=report.duration,
#                     caplog=getattr(report, "caplog", ""),
#                     capstderr=getattr(report, "capstderr", ""),
#                     capstdout=getattr(report, "capstdout", ""),
#                     longreprtext=str(report.longrepr) if report.longrepr else "",
#                     has_warning=bool(getattr(report, "warning_messages", [])),
#                 )
#                 test_results.append(test_result)
#             elif isinstance(report, WarningReport):
#                 test_result = TestResult(
#                     nodeid=report.nodeid,
#                     outcome="WARNING",
#                     start_time=datetime.now(),
#                     duration=0.0,
#                     caplog=str(report.message),
#                     capstderr="",
#                     capstdout="",
#                     longreprtext="",
#                     has_warning=True,
#                 )
#                 test_results.append(test_result)

#     # Convert raw dictionary into a proper TestSession object
#     session = TestSession(
#         sut_name="default_sut",
#         session_id=str(datetime.now().timestamp()),  # Unique session ID
#         session_start_time=datetime.now(),
#         session_stop_time=datetime.now(),
#         test_results=test_results,  # Include the list of TestResult objects
#     )

#     # Group reruns
#     populate_rerun_groups(session)

#     # Save session
#     storage.save_session(session)

#     # Print summary to console in its own "insight summary" section
#     terminalreporter.write_sep("=", "insight summary info", cyan=True)
#     summary = {outcome: len(reports) for outcome, reports in stats.items()}
#     for outcome, count in summary.items():
#         terminalreporter.write_line(f"  {outcome.upper()}: {count} tests")

#     print()


def _group_rerun_tests(test_results: List[TestResult]) -> Dict[str, RerunTestGroup]:
    """Sort rerun tests into groups and determine final outcome efficiently."""

    rerun_groups = {}

    for test in test_results:
        if test.nodeid not in rerun_groups:
            rerun_groups[test.nodeid] = RerunTestGroup(nodeid=test.nodeid, final_outcome="UNKNOWN")

        group = rerun_groups[test.nodeid]

        if test.outcome == "RERUN":
            group.add_rerun(test)  # Store rerun attempts
        else:
            group.final_outcome = test.outcome  # Set final outcome
            group.add_test(test)  # Store final test attempt

    for group in rerun_groups.values():
        group._full_test_list = group._reruns + [group.final_test] if group.final_test else []

    return {groupname: group for groupname, group in rerun_groups.items() if group.reruns}

def populate_rerun_groups(test_session: TestSession) -> None:
    """Attach rerun test groups to the test session."""
    rerun_groups = _group_rerun_tests(test_session.test_results)
    test_session.rerun_test_groups = list(rerun_groups.values())
