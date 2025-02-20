from datetime import datetime, timedelta
import pytest
from colorama import Fore, Style
from typer.testing import CliRunner

from pytest_insight.cli.commands import format_metrics, format_trend_direction, show_trends, app
from pytest_insight.core.analyzer import InsightAnalyzer
from pytest_insight.models import TestResult

runner = CliRunner()

def test_format_metrics():
    """Test metrics formatting."""
    metrics = {
        "total_count": 10,
        "failure_rate": 0.2,
        "avg_duration": 1.5
    }

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

def test_show_trends(capsys):
    """Test trends display output."""
    now = datetime.now()
    results = [
        TestResult(
            nodeid="test_example.py::test_case",
            outcome="passed",
            start_time=now + timedelta(minutes=i),
            duration=1.0 + i * 0.5
        )
        for i in range(5)
    ]

    analyzer = InsightAnalyzer(None)
    show_trends(analyzer, results)

    captured = capsys.readouterr()
    assert "=== Test Execution Trends ===" in captured.out
    assert "Duration Trend:" in captured.out
    assert "Total Executions: 5" in captured.out

def test_show_session_latest(storage, test_session):
    """Test showing latest session with no filters."""
    # Setup
    storage.save_session(test_session)

    # Execute
    result = runner.invoke(app, ["session", "show"])

    # Verify
    assert result.exit_code == 0
    assert "metrics" in result.output
    assert "trends" in result.output

def test_show_session_with_filters(storage, test_session):
    """Test showing sessions with filters."""
    # Setup
    test_session.test_results[0].outcome = "failed"  # Ensure at least one failure
    storage.save_session(test_session)

    # Execute
    result = runner.invoke(app, [
        "session", "show",
        "--sut", test_session.sut_name,
        "--outcome", "failed"
    ])

    # Verify
    assert result.exit_code == 0
    assert "failure_rate" in result.output

def test_show_session_by_id(storage, test_session):
    """Test showing specific session by ID."""
    # Setup - Save test session to storage
    storage.save_session(test_session)

    # Execute command
    result = runner.invoke(app, [
        "session", "show",
        "--id", test_session.session_id  # Use actual session ID from fixture
    ])

    # Verify
    assert result.exit_code == 0
    assert test_session.session_id in result.output
    assert "metrics" in result.output
    assert "trends" in result.output
