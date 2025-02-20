from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from click import Choice  # Add this import
from colorama import Fore, Style
from pytest_insight.core.analyzer import InsightAnalyzer
from pytest_insight.models import TestResult
from pytest_insight.cli.formatters import format_metrics, format_trend_direction
from pytest_insight.core.api import InsightAPI
from pytest_insight.core.analyzer import SessionFilter
from pytest_insight.storage import get_storage_instance
import typer
from rich.console import Console
from pytest_insight.cli.display import ResultsDisplay

app = typer.Typer()
analytics_app = typer.Typer(help="Generate test analytics and reports")
app.add_typer(analytics_app, name="analytics")

console = Console()
display = ResultsDisplay()

def get_api() -> InsightAPI:
    """Get API instance with configured storage."""
    return InsightAPI(get_storage_instance())

@analytics_app.command("session")
def show_session(
    session_id: Optional[str] = typer.Option(None, "--id", help="Show specific session"),
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by SUT name"),
    days: int = typer.Option(1, "--days", "-d", help="Days to look back")
):
    """Show session analytics."""
    api = get_api()

    if session_id:
        summary = api.get_session_summary(session_id)
        if not summary:
            typer.echo(f"Session {session_id} not found")
            raise typer.Exit(1)
    else:
        filters = SessionFilter(
            sut=sut,
            timespan=timedelta(days=days)
        )
        sessions = api.get_sessions(filters)
        if not sessions:
            typer.echo("No matching sessions found")
            raise typer.Exit(1)
        summary = sessions[0]

    display.show_session_summary(summary)

@analytics_app.command("trends")
def show_trends(
    days: int = typer.Option(7, "--days", "-d", help="Days to analyze"),
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by SUT")
):
    """Show test execution trends."""
    api = get_api()
    analysis = api.get_trend_analysis(timedelta(days=days))
    display.show_trend_analysis(analysis)

@analytics_app.command("compare")
def compare_tests(
    base: str = typer.Argument(..., help="Base SUT or date (YYYY-MM-DD)"),
    target: str = typer.Argument(..., help="Target SUT or date (YYYY-MM-DD)"),
    mode: str = typer.Option("sut", "--mode", "-m", help="Compare mode: sut or date")
):
    """Compare test results."""
    api = get_api()

    if mode == "sut":
        results = api.compare_suts(base, target)
        display.show_sut_comparison(results, base, target)
    else:
        try:
            base_date = datetime.strptime(base, "%Y-%m-%d")
            target_date = datetime.strptime(target, "%Y-%m-%d")
            results = api.compare_periods(base_date, target_date, days=7)
            display.show_period_comparison(results)
        except ValueError:
            typer.echo("Invalid date format. Use YYYY-MM-DD")
            raise typer.Exit(1)

@analytics_app.command("health")
def show_health(sut: str = typer.Argument(..., help="SUT to analyze")):
    """Show test suite health metrics."""
    api = get_api()
    health = api.analyze_health(sut)
    display.show_health_analysis(health)
