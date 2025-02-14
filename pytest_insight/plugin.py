from datetime import datetime, timedelta

import pytest
from _pytest.config import Config

from pytest_insight.models import (
    OutputFieldType,
    TestHistory,
    TestSession,
)


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


def insight_enabled(config: Config) -> bool:
    """Helper function to check if pytest-insight is enabled."""
    return bool(getattr(config.option, "insight", False))


@pytest.hookimpl
def pytest_configure(config):
    """Configure the plugin if enabled."""
    if insight_enabled(config):
        config._insight_test_history = TestHistory()


@pytest.hookimpl
def pytest_sessionstart(session):
    """Initialize test session tracking."""
    if not insight_enabled(session.config):
        return

    session.config._insight_test_session = TestSession(
        sut_name="default_sut",
        session_id=f"session-{int(datetime.utcnow().timestamp())}",
        session_start_time=datetime.utcnow(),
        session_stop_time=datetime.utcnow(),
        session_duration=timedelta(0),
    )
    session.config._insight_start_time = datetime.utcnow()


@pytest.hookimpl
def pytest_sessionfinish(session, exitstatus):
    """Store final session results in TestSession and add to TestHistory."""
    if not insight_enabled(session.config):
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
    """Extract reruns, warnings, errors, and pytest's final summary line."""
    if not insight_enabled(config):
        return

    session = config._insight_test_session
    output_fields = session.output_fields

    # Extract warnings
    warnings = terminalreporter.stats.get("warnings", [])
    if warnings:
        output_fields.set(
            OutputFieldType.WARNINGS_SUMMARY,
            "\n".join(str(w.message) for w in warnings),
        )

    # Extract errors
    errors = terminalreporter.stats.get("error", [])
    if errors:
        output_fields.set(OutputFieldType.ERRORS, "\n".join(str(e.longreprtext) for e in errors))

    # Extract reruns
    reruns = terminalreporter.stats.get("rerun", [])
    output_fields.set("reruns", "\n".join([str(r.nodeid) for r in reruns]))

    # Create summary from stats
    passed = len(terminalreporter.stats.get("passed", []))
    failed = len(terminalreporter.stats.get("failed", []))
    skipped = len(terminalreporter.stats.get("skipped", []))
    xfailed = len(terminalreporter.stats.get("xfailed", []))
    xpassed = len(terminalreporter.stats.get("xpassed", []))
    warnings = len(terminalreporter.stats.get("warnings", []))
    errors = len(terminalreporter.stats.get("error", []))
    reruns = len(terminalreporter.stats.get("rerun", []))
    summary = (
        f"=== {passed} passed, {failed} failed, {skipped} skipped, "
        f"{xfailed} xfailed, {xpassed} xpassed, {warnings} warnings, "
        f"{errors} errors, {reruns} reruns ==="
    )

    output_fields.set("summary_line", summary)

    # Print verification
    print("\n[pytest-insight] Summary:")
    print(f"Warnings: {output_fields.get('warnings', 'None')}")
    print(f"Errors: {output_fields.get('errors', 'None')}")
    print(f"Reruns: {output_fields.get('reruns', 'None')}")
    print(f"Summary: {output_fields.get('summary_line', 'Unknown')}")
    print()
