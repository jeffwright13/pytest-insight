import logging
import os
import platform
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
from pytest_insight.insight_api import InsightAPI
from pytest_insight.dashboard_formatter import build_dashboard_from_api
from pytest_insight.utils.console_insights import populate_terminal_section

logger = logging.getLogger(__name__)

storage = None


def insight_enabled(config: Optional[Config] = None) -> bool:
    if config is not None:
        return bool(getattr(config.option, "insight", False))
    return False


def pytest_addoption(parser):
    group = parser.getgroup("insight", "pytest-insight: test insights and analytics")
    group.addoption(
        "--insight",
        action="store_true",
        default=False,
        help="Enable pytest-insight plugin",
    )
    group.addoption(
        "--insight-profile",
        action="store",
        default=None,
        help="Specify the storage profile to use",
    )
    group.addoption(
        "--insight-sut-name",
        action="store",
        default=None,
        help="Specify the System Under Test (SUT) name",
    )
    group.addoption(
        "--insight-testing-system",
        action="store",
        default=None,
        help="Specify the testing system name (overrides hostname)",
    )


def get_config_values(config: Config, option_defaults: Dict[str, Optional[str]]):
    resolved = {}
    for key, default in option_defaults.items():
        cmdline_val = config.getoption(key, None)
        env_var = f"PYTEST_INSIGHT_{key.upper()}"
        env_val = os.environ.get(env_var)
        resolved[key] = cmdline_val or env_val or default
    return resolved


@pytest.hookimpl
def pytest_configure(config: Config):
    global storage
    if not insight_enabled(config):
        return

    insight_config_values = get_config_values(
        config,
        {
            "insight_profile": "default",
            "insight_system_under_test_name": None,
            "insight_testing_system": None,
        },
    )

    try:
        profile_manager = get_profile_manager()
        try:
            profile_manager.get_profile(insight_config_values["insight_profile"])
        except ValueError:
            create_profile(insight_config_values["insight_profile"], "json", None)
            print(
                f"[pytest-insight] Created new profile '{insight_config_values['insight_profile']}'",
                file=sys.stderr,
            )
        storage = get_storage_instance(profile_name=insight_config_values["insight_profile"])
    except Exception as e:
        print(f"[pytest-insight] Error initializing storage: {e}", file=sys.stderr)
        return


@pytest.hookimpl
def pytest_terminal_summary(terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config):
    if not insight_enabled(config):
        return

    global storage

    config_values = get_config_values(
        config,
        {
            "insight_profile": None,
            "insight_sut_name": None,
            "insight_testing_system": None,
        },
    )
    sut_name = config_values["insight_sut_name"] or "unknown-sut"
    hostname = socket.gethostname()
    testing_system_name = config_values["insight_testing_system"] or hostname

    stats = terminalreporter.stats
    test_results = []
    session_start = None
    session_end = None

    # Process all test reports
    for outcome, reports in stats.items():
        if not outcome:
            continue
        if outcome == "warnings":
            continue  # Handle warnings separately

        for report in reports:
            if not isinstance(report, TestReport):
                continue

            # Capture only call-phase or error failures from setup/teardown
            if report.when == "call" or (
                report.when in ("setup", "teardown")
                and report.outcome in ("failed", "error")
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
                        outcome=(
                            TestOutcome.from_str(outcome)
                            if outcome
                            else TestOutcome.SKIPPED
                        ),
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
    session_id = (f"{session_start.strftime('%Y%m%d-%H%M%S')}-"f"{str(uuid.uuid4())[:8]}").lower()

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
            "plugins": [
                p.name for p in config.pluginmanager.get_plugins() if hasattr(p, "name")
            ],
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
        terminalreporter.write_line(
            f"[pytest-insight] Error: Failed to save session - {str(e)}", red=True
        )
        terminalreporter.write_line(
            f"[pytest-insight] Error details: {str(e)}", red=True
        )
        return

    api = InsightAPI([session])
    dashboard_str = build_dashboard_from_api(api)
    terminalreporter.write_sep("=", "pytest-insight")
    terminalreporter.write_line(dashboard_str)


def group_tests_into_rerun_test_groups(
    test_results: List[TestResult],
) -> List[RerunTestGroup]:
    rerun_test_groups: Dict[str, RerunTestGroup] = {}
    for test_result in test_results:
        if test_result.nodeid not in rerun_test_groups:
            rerun_test_groups[test_result.nodeid] = RerunTestGroup(nodeid=test_result.nodeid)
        rerun_test_groups[test_result.nodeid].add_test(test_result)
    return [group for group in rerun_test_groups.values() if len(group.tests) > 1]
