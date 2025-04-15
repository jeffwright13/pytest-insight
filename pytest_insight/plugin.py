import os
import platform
import re
import socket
import sys
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.core.insights import Insights
from pytest_insight.core.models import (
    RerunTestGroup,
    TestOutcome,
    TestResult,
    TestSession,
)
from pytest_insight.core.storage import (
    create_profile,
    get_profile_manager,
    get_storage_instance,
)

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
        # Check for the new --insight option instead of insight_enabled
        _INSIGHT_ENABLED = bool(getattr(config.option, "insight", False))
        _INSIGHT_INITIALIZED = True
    return _INSIGHT_ENABLED


def pytest_addoption(parser):
    """Add pytest-insight specific command line options."""
    group = parser.getgroup("insight", "pytest-insight: test insights and analytics")
    group.addoption(
        "--insight",
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin",
    )
    group.addoption(
        "--insight-sut",
        "--is",
        action="store",
        default=None,
        help="Specify the System Under Test (SUT) name",
    )
    group.addoption(
        "--insight-test-system-name",
        "--itsn",
        action="store",
        default=None,
        help="Specify the testing system name (overrides hostname)",
    )
    group.addoption(
        "--insight-profile",
        "--ip",
        action="store",
        default=None,
        help="Specify the storage profile to use",
    )


@pytest.hookimpl
def pytest_configure(config: Config):
    """Configure the plugin if enabled."""
    global storage

    if not insight_enabled(config):
        return

    # Get profile name, defaulting to 'default'
    profile_name = config.getoption("insight_profile", "default")

    try:
        # Try to get the profile
        profile_manager = get_profile_manager()
        try:
            profile_manager.get_profile(profile_name)
        except ValueError:
            # Profile doesn't exist, create it
            create_profile(profile_name, "json", None)  # None will use the default path
            print(
                f"[pytest-insight] Created new profile '{profile_name}'",
                file=sys.stderr,
            )

        # Now get the storage instance using the profile
        storage = get_storage_instance(profile_name=profile_name)
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

    # Get hostname for the testing system information
    hostname = socket.gethostname()

    # Get SUT name from pytest option '--insight-sut'
    # Use a more appropriate default if not specified (project name or 'unknown-sut')
    sut_name = config.getoption("insight_sut")
    if not sut_name:
        # Try to determine project name from current directory
        try:
            sut_name = os.path.basename(os.getcwd())
            # Clean up the name (remove special characters, etc.)
            sut_name = re.sub(r"[^a-zA-Z0-9_-]", "-", sut_name).lower()
        except OSError:  # Use specific exception type
            sut_name = "unknown-sut"

    # Get testing system name from pytest option '--insight-test-system-name'
    testing_system_name = config.getoption("insight_test_system_name") or os.environ.get(
        "PYTEST_INSIGHT_SYSTEM_NAME", hostname
    )

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
    rerun_test_groups = group_tests_into_rerun_test_groups(test_results)

    # Create TestSession instance
    session = TestSession(
        sut_name=sut_name,
        session_id=session_id,
        testing_system={
            "hostname": hostname,  # Use hostname here instead of as SUT name
            "name": testing_system_name,
            "type": os.environ.get("PYTEST_INSIGHT_SYSTEM_TYPE", "local"),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "pytest_version": pytest.__version__,
            "plugins": [p.name for p in config.pluginmanager.get_plugins() if hasattr(p, "name")],
        },
        session_start_time=session_start,
        session_stop_time=session_end,
        test_results=test_results,
        rerun_test_groups=rerun_test_groups,
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
    from pytest_insight.core.analysis import Analysis

    # Create an Analysis instance with the current session
    analysis = Analysis(storage=storage, sessions=[session])

    # Create an Insights instance with the analysis
    insights = Insights(analysis=analysis)

    # Get formatted console output
    try:
        outcome_counts = {}
        for test in session.test_results:
            outcome_name = test.outcome.value.lower() if hasattr(test.outcome, "value") else str(test.outcome).lower()
            outcome_counts[outcome_name] = outcome_counts.get(outcome_name, 0) + 1

        # Write the formatted header with terminal-width separators
        terminalreporter.write_line("")
        terminalreporter.write_sep("=", "pytest-insight", cyan=True)

        # Format and write the console output with session info
        output = insights.console_summary()
        terminalreporter.write_line(output)
    except Exception as e:
        # Only show error message if --insight flag is enabled
        if config.getoption("insight"):
            terminalreporter.write_line("")
            terminalreporter.write_sep("=", "pytest-insight", red=True)
            terminalreporter.write_line(f"[pytest-insight] Error generating summary: {str(e)}", red=True)
            terminalreporter.write_line(f"[pytest-insight] Error details: {str(e)}", red=True)


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
