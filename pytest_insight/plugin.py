import sys
import uuid
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union
from pathlib import Path

import pytest
from _pytest.config import Config
from _pytest.reports import TestReport
from _pytest.terminal import TerminalReporter, WarningReport
from pytest import ExitCode

from pytest_insight.constants import DEFAULT_STORAGE_TYPE, StorageType
from pytest_insight.models import RerunTestGroup, TestOutcome, TestResult, TestSession
from pytest_insight.storage import JSONStorage, get_storage_instance

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

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
    group = parser.getgroup('pytest-insight')
    group.addoption(
        '--insight-json',
        action='store',
        dest='insight_json_path',
        default=None,
        help='Path to output JSON file for test results'
    )
    group = parser.getgroup("insight", "pytest-insight")
    group.addoption("--insight", action="store_true", help="Enable pytest-insight")
    group.addoption(
        "--insight-sut",
        default="default_sut",
        dest="insight_sut",  # Add dest to make option accessible
        help="Specify the System Under Test (SUT) name",
    )
    group.addoption(
        "--insight-storage-type",
        choices=[st.value for st in StorageType],
        default=DEFAULT_STORAGE_TYPE.value,
        help="Storage backend to use"
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

        # Convert string path to Path object and ensure it's absolute
        if json_path:
            json_path = Path(json_path).resolve()
            # Create parent directories for custom path
            json_path.parent.mkdir(parents=True, exist_ok=True)

        # Create storage instance
        storage = get_storage_instance(storage_type, json_path)


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
    session_id = (
        f"{sut_name}-{session_start.strftime('%Y%m%d-%H%M%S')}-"
        f"{str(uuid.uuid4())[:8]}"
    ).lower()

    # Create/process rerun test groups
    rerun_test_group_list = group_tests_into_rerun_test_groups(test_results)

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
        """Write a section header in bold yellow."""
        terminalreporter.write_line(f"\n{text}", yellow=True, bold=True)

    def write_stat_line(terminalreporter, label, value, **color_kwargs):
        """Write a stat line with colored value."""
        terminalreporter.write(f"  {label}: ")
        terminalreporter.write_line(f"{value}", **color_kwargs)

    def write_insight_panel(title: str, content: str, style: str = "cyan"):
        """Write a rich panel with the given title and content."""
        console = Console()
        panel = Panel(
            content,
            title=title,
            border_style=style,
            padding=(1, 2)
        )
        console.print(panel)

    def format_stat_row(label: str, value: str, value_style: str = "none") -> Text:
        """Format a statistics row with styled value."""
        text = Text()
        text.append(f"{label}: ")
        text.append(value, style=value_style)
        return text

    # Replace existing terminal output with Rich panels
    console = Console()

    # Metadata panel
    metadata_content = Text()
    metadata_content.append_text(format_stat_row("SUT Name", sut_name))
    metadata_content.append("\n")
    metadata_content.append_text(format_stat_row("Session ID", session_id))
    console.print(Panel(metadata_content, title="Test Session Metadata", border_style="yellow"))

    # Execution Summary panel
    summary_content = Text()
    summary_content.append_text(format_stat_row("Total Tests", str(total_tests), "green"))
    summary_content.append("\n")
    summary_content.append_text(format_stat_row("Total Duration", f"{total_duration:.2f}s", "green"))
    summary_content.append("\n")
    summary_content.append_text(format_stat_row("Start Time", session_start.isoformat()))
    summary_content.append("\n")
    summary_content.append_text(format_stat_row("Stop Time", session_end.isoformat()))
    console.print(Panel(summary_content, title="Test Execution Summary", border_style="blue"))

    # Outcome Distribution table
    table = Table(title="Outcome Distribution", border_style="cyan")
    table.add_column("Outcome", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")

    for outcome, reports in sorted(terminalreporter.stats.items()):
        if outcome not in ["warnings", ""]:
            count = len(reports)
            percentage = (count / total_tests) * 100 if total_tests > 0 else 0
            outcome_style = {
                "passed": "green",
                "failed": "red",
                "error": "red",
                "skipped": "yellow",
                "xfailed": "yellow",
                "xpassed": "yellow",
                "rerun": "cyan"
            }.get(outcome, "white")

            table.add_row(
                outcome.capitalize(),
                str(count),
                f"{percentage:.1f}%" if outcome != "rerun" else "",
                style=outcome_style
            )
    console.print(table)

    # Rerun Analysis panel
    if rerun_groups:
        rerun_content = Text()
        rerun_content.append_text(format_stat_row("Tests Requiring Reruns", str(len(rerun_groups)), "cyan"))
        rerun_content.append("\n")
        rerun_content.append_text(format_stat_row("Eventually Passed", str(len(flaky_tests)), "green"))
        rerun_content.append("\n")
        rerun_content.append_text(format_stat_row("Remained Failed", str(len(unstable_tests)), "red"))
        console.print(Panel(rerun_content, title="Rerun Analysis", border_style="magenta"))

        # Most Retried Tests table
        if most_retried:
            retry_table = Table(title="Most Retried Tests", border_style="magenta")
            retry_table.add_column("Test", style="bold")
            retry_table.add_column("Attempts", justify="right")
            retry_table.add_column("Final Outcome", justify="right")

            for group in most_retried:
                outcome_style = "green" if group.final_outcome == TestOutcome.PASSED else "red"
                retry_table.add_row(
                    group.nodeid,
                    str(len(group.tests)),
                    group.final_outcome.to_str().capitalize(),
                    style=outcome_style
                )
            console.print(retry_table)

    # Longest Running Tests table
    if top_duration_tests:
        duration_table = Table(title="Longest Running Tests", border_style="blue")
        duration_table.add_column("Test", style="bold")
        duration_table.add_column("Duration", justify="right")
        duration_table.add_column("Outcome", justify="right")

        for test in top_duration_tests:
            outcome_style = {
                TestOutcome.PASSED: "green",
                TestOutcome.FAILED: "red",
                TestOutcome.ERROR: "red",
                TestOutcome.SKIPPED: "yellow"
            }.get(test.outcome, "white")

            duration_table.add_row(
                test.nodeid,
                f"{test.duration:.2f}s",
                test.outcome.to_str().capitalize(),
                style=outcome_style
            )
        console.print(duration_table)

    # Warnings panel
    if "warnings" in terminalreporter.stats:
        warning_content = Text()
        warning_count = len(terminalreporter.stats["warnings"])
        warning_content.append_text(format_stat_row("Total", str(warning_count), "yellow"))
        console.print(Panel(warning_content, title="Warnings Summary", border_style="yellow"))

    # Add final spacing
    console.print()


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
