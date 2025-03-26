import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.constants import DEFAULT_STORAGE_TYPE, StorageType
from pytest_insight.insights import Insights
from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.storage import get_storage_instance

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
    """Add pytest-insight specific command line options."""
    group = parser.getgroup("pytest-insight")  # Use same name as header
    group.addoption("--insight", action="store_true", help="Enable pytest-insight")
    group.addoption(
        "--insight-sut",
        action="store",
        default="default_sut",
        help="Name of the system under test",
    )
    group.addoption(
        "--insight-storage-type",
        action="store",
        default=DEFAULT_STORAGE_TYPE.value,
        choices=[t.value for t in StorageType],
        help=f"Storage type for test data (default: {DEFAULT_STORAGE_TYPE.value})",
    )
    group.addoption(
        "--insight-storage-path",
        action="store",
        default=None,
        help="Path to storage directory/file (default: ~/.pytest_insight)",
    )
    group.addoption(
        "--insight-environment",
        action="store",
        default="test",
        help="Environment name (e.g., dev, test, prod)",
    )


@pytest.hookimpl
def pytest_configure(config: Config):
    """Configure the plugin if enabled."""
    global storage

    if not insight_enabled(config):
        return

    # Initialize storage
    storage_type_str = config.getoption("insight_storage_type", DEFAULT_STORAGE_TYPE.value)
    storage_type = StorageType(storage_type_str)
    storage_path = config.getoption("insight_storage_path", None)

    try:
        storage = get_storage_instance(storage_type.value, storage_path)
    except Exception as e:
        # Log error but don't fail the test run
        print(f"[pytest-insight] Error initializing storage: {e}", file=sys.stderr)
        return

    # Register additional markers
    config.addinivalue_line(
        "markers",
        "insight_tag(name, value): add a tag to the test session",
    )


@pytest.hookimpl
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
    """Process test results and show useful insights in terminal summary."""
    if not insight_enabled(config):
        return

    if not storage:  # Ensure storage is initialized
        return

    sut_name = config.getoption("insight_sut", "default_sut")  # Get SUT name from pytest option
    stats = terminalreporter.stats
    test_results = []
    session_start = None
    session_end = None

    # Process all test reports
    for outcome, reports in stats.items():
        if not outcome:  # looking for empty string "", only populated with 'setup' and 'teardown' reports
            continue

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
                        outcome=(TestOutcome.from_str(outcome) if outcome else TestOutcome.SKIPPED),
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
    session_id = (f"{sut_name}-{session_start.strftime('%Y%m%d-%H%M%S')}-" f"{str(uuid.uuid4())[:8]}").lower()

    # Create/process rerun test groups
    rerun_test_group_list = group_tests_into_rerun_test_groups(test_results)

    # Create and store session with SUT name
    session = TestSession(
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

    try:
        storage.save_session(session)
    except Exception as e:
        terminalreporter.write_line(f"[pytest-insight] Error: Failed to save session - {str(e)}", red=True)
        terminalreporter.write_line(f"[pytest-insight] Error details: {str(e)}", red=True)

    # Import Analysis class here to avoid circular imports
    from pytest_insight.analysis import Analysis

    # Create an Analysis instance with the current session
    analysis = Analysis(storage=storage, sessions=[session])

    # Create an Insights instance with the analysis
    insights = Insights(analysis=analysis)

    # Get console-friendly summary
    try:
        summary = insights.console_summary()
    except Exception as e:
        terminalreporter.write_line(f"[pytest-insight] Error generating summary: {str(e)}", red=True)
        return

    # Helper functions for terminal output
    def write_section_header(terminalreporter, text):
        """Write a section header with dashes."""
        terminalreporter.write_line("")
        terminalreporter.write_line(f"--- {text} ---", yellow=True)

    def write_stat_line(terminalreporter, label, value, **color_kwargs):
        """Write an indented stat line with colored value."""
        terminalreporter.write("    ")  # 4-space indentation
        terminalreporter.write(f"{label}: ")
        terminalreporter.write_line(f"{value}", **color_kwargs)

    # Add screen-wide header only for main plugin section
    terminalreporter.write_sep("=", "pytest-insight summary", cyan=True)
    terminalreporter.write_line("")  # Add spacing

    # Main sections
    write_section_header(terminalreporter, "Test Session Info")
    write_stat_line(terminalreporter, "SUT Name", sut_name)
    write_stat_line(terminalreporter, "Session ID", session_id)
    write_stat_line(terminalreporter, "Storage Path", storage.file_path)

    # Health score from insights
    write_section_header(terminalreporter, "Test Health")
    write_stat_line(
        terminalreporter,
        "Health Score",
        f"{summary['health_score']:.2f}/100",
        green=summary["health_score"] >= 80,
        yellow=60 <= summary["health_score"] < 80,
        red=summary["health_score"] < 60,
    )

    # Test execution summary
    write_section_header(terminalreporter, "Test Execution Summary")
    write_stat_line(terminalreporter, "Total Tests", str(summary["outcome_distribution"][0][1]), green=True)
    write_stat_line(terminalreporter, "Total Duration", f"{session.session_duration:.2f}s", green=True)
    write_stat_line(terminalreporter, "Start Time", session_start.isoformat())
    write_stat_line(terminalreporter, "Stop Time", session_end.isoformat())

    # Outcome distribution from insights
    write_section_header(terminalreporter, "Outcome Distribution")
    for outcome, count in summary["outcome_distribution"]:
        percentage = (count / len(test_results)) * 100 if test_results else 0
        value = f"{count} ({percentage:.1f}%)"
        outcome_str = outcome.to_str() if hasattr(outcome, "to_str") else str(outcome)
        color_kwargs = {
            "passed": {"green": True},
            "failed": {"red": True},
            "error": {"red": True},
            "skipped": {"yellow": True},
            "xfailed": {"yellow": True},
            "xpassed": {"yellow": True},
            "rerun": {"cyan": True},
        }.get(outcome_str.lower(), {})
        write_stat_line(terminalreporter, f"{outcome_str.capitalize()}", value, **color_kwargs)

    # Flaky test information from insights
    if summary["flaky_test_count"] > 0:
        write_section_header(terminalreporter, "Flaky Tests")
        write_stat_line(
            terminalreporter,
            "Tests Requiring Reruns",
            str(summary["flaky_test_count"]),
            cyan=True,
        )

        # Display most flaky tests
        if summary["most_flaky"]:
            write_section_header(terminalreporter, "Most Flaky Tests")
            for nodeid, data in summary["most_flaky"][:3]:
                write_stat_line(
                    terminalreporter,
                    nodeid,
                    f"{data['reruns']} reruns (Pass rate: {data['pass_rate']*100:.1f}%)",
                    yellow=True,
                )

    # Slowest tests from insights
    if summary["slowest_tests"]:
        write_section_header(terminalreporter, "Longest Running Tests")
        for nodeid, duration in summary["slowest_tests"]:
            # Find the test outcome for coloring
            test_outcome = None
            for test in test_results:
                if test.nodeid == nodeid:
                    test_outcome = test.outcome
                    break

            color_kwargs = {
                TestOutcome.PASSED: {"green": True},
                TestOutcome.FAILED: {"red": True},
                TestOutcome.ERROR: {"red": True},
                TestOutcome.SKIPPED: {"yellow": True},
            }.get(test_outcome, {})

            write_stat_line(
                terminalreporter,
                nodeid,
                f"{duration:.2f}s ({test_outcome.to_str().capitalize() if test_outcome else 'Unknown'})",
                **color_kwargs,
            )

    # Failure trend information if available
    if summary["failure_trend"]["change"] != 0:
        write_section_header(terminalreporter, "Trend Analysis")
        trend_text = f"{abs(summary['failure_trend']['change']):.1f}% "
        if summary["failure_trend"]["improving"]:
            trend_text += "decrease in failures"
            color_kwargs = {"green": True}
        else:
            trend_text += "increase in failures"
            color_kwargs = {"red": True}

        write_stat_line(terminalreporter, "Failure Trend", trend_text, **color_kwargs)

    # Add final spacing
    terminalreporter.write_line("")


def group_tests_into_rerun_test_groups(
    test_results: List[TestResult],
) -> List[RerunTestGroup]:
    """Group test results by nodeid into RerunTestGroups.

    A valid rerun group must have:
    - Multiple test results for the same nodeid
    - All tests except the last must have outcome = RERUN
    - Last test (chronologically) must have any outcome except RERUN
    - Tests ordered by start_time
    """
    rerun_test_groups: Dict[str, RerunTestGroup] = {}

    # First pass: group by nodeid
    for test_result in test_results:
        if test_result.nodeid not in rerun_test_groups:
            rerun_test_groups[test_result.nodeid] = RerunTestGroup(nodeid=test_result.nodeid)
        rerun_test_groups[test_result.nodeid].add_test(test_result)

    # Return only groups with reruns (more than one test)
    # RerunTestGroup's add_test handles chronological ordering and validation
    return [group for group in rerun_test_groups.values() if len(group.tests) > 1]
