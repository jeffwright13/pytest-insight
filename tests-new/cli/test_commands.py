from colorama import Fore, Style
from pytest_insight.cli.commands import app, format_metrics, format_trend_direction
from typer.testing import CliRunner

runner = CliRunner()


def test_format_metrics():
    """Test metrics formatting."""
    metrics = {"total_count": 10, "failure_rate": 0.2, "avg_duration": 1.5}

    output = format_metrics(metrics)
    assert "total_count: 10" in output
    assert "failure_rate: 0.20" in output
    assert "avg_duration: 1.50" in output


def test_format_trend_direction():
    """Test trend direction formatting with colors."""
    assert Fore.RED in format_trend_direction("increasing")
    assert Fore.GREEN in format_trend_direction("decreasing")
    assert Fore.YELLOW in format_trend_direction("stable")
    assert Style.RESET_ALL in format_trend_direction("increasing")


def test_show_trends(storage, test_session):
    """Test trends display output."""
    # Setup
    storage.save_session(test_session)

    # Execute using CLI which uses API
    result = runner.invoke(app, ["analytics", "trends", "--days", "1"])

    # Verify
    assert result.exit_code == 0
    assert "Test Execution Trends" in result.output
    assert "Duration Trend" in result.output


def test_show_session_latest(storage, test_session):
    """Test showing latest session with no filters."""
    # Setup
    storage.save_session(test_session)

    # Execute - Update command path
    result = runner.invoke(app, ["analytics", "session"])  # Changed: add 'analytics'

    # Verify
    assert result.exit_code == 0
    assert "metrics" in result.output
    assert "trends" in result.output


def test_show_session_with_filters(storage, test_session):
    """Test showing sessions with filters."""
    # Setup
    test_session.test_results[0].outcome = "failed"
    storage.save_session(test_session)

    # Execute - Update command path
    result = runner.invoke(
        app,
        [
            "analytics",
            "session",  # Changed: add 'analytics'
            "--sut",
            test_session.sut_name,
            "--outcome",
            "failed",
        ],
    )

    # Verify
    assert result.exit_code == 0
    assert "failure_rate" in result.output


def test_show_session_by_id(storage, test_session):
    """Test showing specific session by ID."""
    # Setup
    storage.save_session(test_session)

    # Execute - Update command path
    result = runner.invoke(
        app,
        [
            "analytics",
            "session",  # Changed: add 'analytics'
            "--id",
            test_session.session_id,
        ],
    )

    # Verify
    assert result.exit_code == 0
    assert test_session.session_id in result.output
    assert "metrics" in result.output
    assert "trends" in result.output
