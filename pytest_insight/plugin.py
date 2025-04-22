import logging
import os
import platform
import socket
import sys
from datetime import datetime
from typing import Dict, List, Optional, Union

import pytest
from _pytest.config import Config
from _pytest.terminal import TerminalReporter
from pytest import ExitCode

from pytest_insight.core.models import (
    RerunTestGroup,
    TestResult,
    TestSession,
)
from pytest_insight.core.storage import (
    create_profile,
    get_profile_manager,
    get_storage_instance,
)
from pytest_insight.insight_api import InsightAPI
from pytest_insight.utils.config import load_terminal_config, terminal_output_enabled
from pytest_insight.utils.terminal_output import render_insights_in_terminal

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
            "insight_sut_name": None,
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
        storage = get_storage_instance(
            profile_name=insight_config_values["insight_profile"]
        )
    except Exception as e:
        print(f"[pytest-insight] Error initializing storage: {e}", file=sys.stderr)
        return


@pytest.hookimpl
def pytest_terminal_summary(
    terminalreporter: TerminalReporter, exitstatus: Union[int, ExitCode], config: Config
):
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
    test_results = []
    session_start = None
    session_end = None
    now = datetime.now()
    session_start = session_start or now
    session_end = session_end or now
    # Always construct a session, even if no test results
    session = TestSession(
        sut_name=sut_name,  # Use config value
        testing_system={
            "hostname": hostname,
            "name": testing_system_name,  # Use config value
            "type": "local",
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "pytest_version": getattr(config, "version", "unknown"),
            # 'plugins' field removed for simplicity and serialization safety
        },
        session_id=f"{sut_name}-{now.strftime('%Y%m%d-%H%M%S')}",
        session_start_time=session_start,
        session_stop_time=session_end,
        session_duration=0.0,
        session_tags={
            "platform": sys.platform,
            "python_version": platform.python_version(),
            "environment": "test",
        },
        rerun_test_groups=[],
        test_results=test_results,
    )
    session.testing_system["name"] = testing_system_name
    try:
        storage.save_session(session)
    except Exception as e:
        msg = f"Error: Failed to save session - {str(e)}"
        terminalreporter.write_line(msg, red=True)
        print(f"[pytest-insight] {msg}", file=sys.stderr)
    # Print summary always including SUT and system name
    # === RESTORE INSIGHT RENDERING ===
    terminal_config = load_terminal_config()
    if terminal_output_enabled(terminal_config):
        api = InsightAPI([session])
        output_str = render_insights_in_terminal(api, terminal_config)
        terminalreporter.write_sep("=", "pytest-insight")
        terminalreporter.write_line(output_str)


def group_tests_into_rerun_test_groups(
    test_results: List[TestResult],
) -> List[RerunTestGroup]:
    rerun_test_groups: Dict[str, RerunTestGroup] = {}
    for test_result in test_results:
        if test_result.nodeid not in rerun_test_groups:
            rerun_test_groups[test_result.nodeid] = RerunTestGroup(
                nodeid=test_result.nodeid
            )
        rerun_test_groups[test_result.nodeid].add_test(test_result)
    return [group for group in rerun_test_groups.values() if len(group.tests) > 1]
