from pytest_insight.cli.formatters import format_metrics, format_trend_direction
from colorama import Fore, Style

def test_format_metrics():
    """Test metrics formatting."""
    metrics = {"failure_rate": 0.5}
    assert "failure_rate: 0.50" in format_metrics(metrics)

def test_format_trend_direction():
    """Test trend direction formatting."""
    assert Fore.RED in format_trend_direction("increasing")
    assert Fore.GREEN in format_trend_direction("decreasing")
    assert Fore.YELLOW in format_trend_direction("stable")
    assert Style.RESET_ALL in format_trend_direction("increasing")
