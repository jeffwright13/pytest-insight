import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.constants import DEFAULT_STORAGE_TYPE, StorageType
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
    group.addoption("--insight-sut", action="store", default="default_sut", help="Name of the system under test")
    group.addoption(
        "--insight-storage-type",
        action="store",
        choices=[t.value for t in StorageType],
        default=DEFAULT_STORAGE_TYPE.value,
        help=f"Storage type for test sessions (default: {DEFAULT_STORAGE_TYPE.value})",
    )
    group.addoption(
        "--insight-json-path",
        action="store",
        default=None,  # Make path optional, use default from JSONStorage if not specified
        help="Path to JSON storage file for test sessions (use 'none' to disable saving results)",
    )


@pytest.hookimpl
def pytest_configure(config: Config):
    """Configure the plugin if enabled."""
    if not insight_enabled(config):
        return

    global storage
    if storage is None:
        storage_type = config.getoption("insight_storage_type")
        json_path = config.getoption("insight_json_path")

        # Don't initialize storage if JSON output is disabled
        if json_path and json_path.lower() == "none":
            return

        # Convert string path to Path object only if path is specified
        if json_path:
            json_path = Path(json_path).resolve()
            json_path.parent.mkdir(parents=True, exist_ok=True)

        # Create storage instance (will use default path if json_path is None)
        storage = get_storage_instance(storage_type, json_path)

    # Initialize session with empty metadata
    sut_name = config.getoption("insight_sut", "default_sut")
    config._insight_session = TestSession(
        sut_name=sut_name,
        session_id=f"{sut_name}-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{str(uuid.uuid4())[:8]}".lower(),
        session_start_time=datetime.now(),
        session_stop_time=datetime.now(),  # Will be updated later
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
        if not outcome: # looking for empty string "", only populated with 'setup' and 'teardown' reports
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
                        outcome=TestOutcome.from_str(outcome) if outcome else TestOutcome.SKIPPED,
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

    # Calculate insights
    total_tests = len(test_results)
    total_duration = sum(t.duration for t in test_results)
    rerun_groups = group_tests_into_rerun_test_groups(test_results)
    flaky_tests = [g for g in rerun_groups if g.final_outcome == TestOutcome.PASSED]
    unstable_tests = [g for g in rerun_groups if g.final_outcome == TestOutcome.FAILED]

    # Sort tests by duration
    sorted_by_duration = sorted(test_results, key=lambda t: t.duration, reverse=True)
    top_duration_tests = sorted_by_duration[:3]

    # Sort rerun groups by number of attempts
    most_retried = sorted(rerun_groups, key=lambda g: len(g.tests), reverse=True)[:3]

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

    write_section_header(terminalreporter, "Test Session Metadata")
    write_stat_line(terminalreporter, "Metadata", terminalreporter.config._metadata)

    write_section_header(terminalreporter, "Test Execution Summary")
    write_stat_line(terminalreporter, "Total Tests", str(total_tests), green=True)
    write_stat_line(terminalreporter, "Total Duration", f"{total_duration:.2f}s", green=True)
    write_stat_line(terminalreporter, "Start Time", session_start.isoformat())
    write_stat_line(terminalreporter, "Stop Time", session_end.isoformat())

    write_section_header(terminalreporter, "Outcome Distribution")
    for outcome, reports in sorted(terminalreporter.stats.items()):
        if outcome not in ["warnings", ""]:
            count = len(reports)
            percentage = (count / total_tests) * 100 if total_tests > 0 else 0
            value = f"{count} ({percentage:.1f}%)" if outcome != "rerun" else str(count)
            color_kwargs = {
                "passed": {"green": True},
                "failed": {"red": True},
                "error": {"red": True},
                "skipped": {"yellow": True},
                "xfailed": {"yellow": True},
                "xpassed": {"yellow": True},
                "rerun": {"cyan": True},
            }.get(outcome, {})
            write_stat_line(terminalreporter, f"{outcome.capitalize()}", value, **color_kwargs)

    if rerun_groups:
        write_section_header(terminalreporter, "Rerun Analysis")
        write_stat_line(terminalreporter, "Tests Requiring Reruns", str(len(rerun_groups)), cyan=True)
        write_stat_line(terminalreporter, "Eventually Passed", str(len(flaky_tests)), green=True)
        write_stat_line(terminalreporter, "Remained Failed", str(len(unstable_tests)), red=True)

        if most_retried:
            write_section_header(terminalreporter, "Most Retried Tests")
            for group in most_retried:
                color_kwargs = {"green": True} if group.final_outcome == TestOutcome.PASSED else {"red": True}
                write_stat_line(
                    terminalreporter,
                    group.nodeid,
                    f"{len(group.tests)} attempts ({group.final_outcome.to_str().capitalize()})",
                    **color_kwargs,
                )

    if top_duration_tests:
        write_section_header(terminalreporter, "Longest Running Tests")
        for test in top_duration_tests:
            color_kwargs = {
                TestOutcome.PASSED: {"green": True},
                TestOutcome.FAILED: {"red": True},
                TestOutcome.ERROR: {"red": True},
                TestOutcome.SKIPPED: {"yellow": True},
            }.get(test.outcome, {})
            write_stat_line(
                terminalreporter,
                test.nodeid,
                f"{test.duration:.2f}s ({test.outcome.to_str().capitalize()})",
                **color_kwargs,
            )

    if "warnings" in terminalreporter.stats:
        write_section_header(terminalreporter, "Warnings Summary")
        write_stat_line(terminalreporter, "Total", str(len(terminalreporter.stats["warnings"])), yellow=True)

    # Add final spacing
    terminalreporter.write_line("")


def group_tests_into_rerun_test_groups(test_results: List[TestResult]) -> List[RerunTestGroup]:
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
