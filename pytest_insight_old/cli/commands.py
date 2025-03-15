from datetime import datetime, timedelta
from enum import Enum  # Updated import
from pathlib import Path
from typing import Optional

import requests
import typer
import uvicorn
from pytest_insight.cli.display import ResultsDisplay
from pytest_insight.core.analyzer import SessionFilter
from pytest_insight.core.api import InsightAPI
from pytest_insight.storage import get_storage_instance
from rich.console import Console

# Define the command groups with proper settings
app = typer.Typer(help="Test history and analytics tool for pytest", no_args_is_help=True)

analytics_app = typer.Typer(help="Generate test analytics and reports", no_args_is_help=True)

setup_app = typer.Typer(help="Setup and configure components", no_args_is_help=True)

server_app = typer.Typer(help="Manage metrics server", no_args_is_help=True)

# Register sub-commands with explicit names
app.add_typer(analytics_app, name="analytics")
app.add_typer(setup_app, name="setup")
app.add_typer(server_app, name="server")

console = Console()
display = ResultsDisplay()


def get_api() -> InsightAPI:
    """Get API instance with configured storage."""
    return InsightAPI(get_storage_instance())


@analytics_app.command("session")
def show_session(
    session_id: Optional[str] = typer.Option(None, "--id", help="Show specific session"),
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by SUT name"),
    days: int = typer.Option(1, "--days", "-d", help="Days to look back"),
):
    """Show session analytics."""
    api = get_api()

    if session_id:
        summary = api.get_session_summary(session_id)
        if not summary:
            typer.echo(f"Session {session_id} not found")
            raise typer.Exit(1)
    else:
        filters = SessionFilter(sut=sut, timespan=timedelta(days=days))
        sessions = api.get_sessions(filters)
        if not sessions:
            typer.echo("No matching sessions found")
            raise typer.Exit(1)
        summary = sessions[0]

    display.show_session_summary(summary)


@analytics_app.command("trends")
def show_trends(
    days: int = typer.Option(7, "--days", "-d", help="Days to analyze"),
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by SUT"),
):
    """Show test execution trends."""
    api = get_api()
    analysis = api.get_trend_analysis(timedelta(days=days))
    display.show_trend_analysis(analysis)


@analytics_app.command("compare")
def compare_tests(
    base: str = typer.Argument(..., help="Base SUT or date (YYYY-MM-DD)"),
    target: str = typer.Argument(..., help="Target SUT or date (YYYY-MM-DD)"),
    mode: str = typer.Option("sut", "--mode", "-m", help="Compare mode: sut or date"),
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


@server_app.command()
def start(
    port: int = typer.Option(8000, "--port", "-p", help="Port to serve metrics on"),
    reload: bool = typer.Option(True, "--reload", help="Enable auto-reload"),
):
    """Start the metrics server."""
    typer.echo(f"Starting metrics server on port {port}")
    uvicorn.run("pytest_insight.server:app", port=port, reload=reload)


@server_app.command()
def status():
    """Check server status."""
    try:
        response = requests.get("http://localhost:8000/health")
        if response.status_code == 200:
            typer.echo("✓ Server is running")
        else:
            typer.echo("✗ Server is not responding correctly")
    except requests.ConnectionError:
        typer.echo("✗ Server is not running")


# Move ComponentType enum before commands
class ComponentType(str, Enum):
    GRAFANA = "grafana"


# Update setup command to use setup_app
@setup_app.callback()
def setup():
    """Setup pytest-insight components."""


# Make sure the Grafana command is properly registered
@setup_app.command("grafana")
def setup_grafana():
    """Install Grafana dashboard and configuration."""
    setup_grafana_dashboard()


def setup_grafana_dashboard():
    """Setup Grafana dashboards and configuration."""
    import shutil
    from pathlib import Path

    # Define paths
    package_dir = Path(__file__).parent.parent
    grafana_dir = Path("/usr/local/var/lib/grafana")
    dashboard_dir = grafana_dir / "dashboards"

    try:
        # Create dashboard directory
        dashboard_dir.mkdir(parents=True, exist_ok=True)

        # Copy dashboard definition
        src_dashboard = package_dir / "grafana/dashboards/test_metrics.json"
        if not src_dashboard.exists():
            typer.echo("Dashboard template not found. Creating default...")
            create_default_dashboard(src_dashboard)

        shutil.copy(src_dashboard, dashboard_dir / "test_metrics.json")

        typer.echo(f"✓ Grafana dashboard installed to {dashboard_dir}")
        typer.echo("\nNext steps:")
        typer.echo("1. Start Grafana:    brew services start grafana")
        typer.echo("2. Start metrics:     insight serve")
        typer.echo("3. Open dashboard:    http://localhost:3000")

    except PermissionError:
        typer.echo("Error: Permission denied. Try running with sudo.", err=True)
        raise typer.Exit(1)
    except Exception as e:
        typer.echo(f"Error: {str(e)}", err=True)
        raise typer.Exit(1)


def create_default_dashboard(dashboard_path: Path) -> None:
    """Create default Grafana dashboard configuration."""
    default_dashboard = {
        "annotations": {"list": []},
        "editable": True,
        "graphTooltip": 0,
        "links": [],
        "panels": [
            {
                "datasource": {"type": "simpod-json-datasource", "uid": "json"},
                "fieldConfig": {
                    "defaults": {
                        "color": {"mode": "palette-classic"},
                        "custom": {
                            "axisCenteredZero": False,
                            "axisColorMode": "text",
                            "axisLabel": "Duration (s)",
                            "axisPlacement": "auto",
                            "drawStyle": "line",
                            "fillOpacity": 20,
                            "gradientMode": "none",
                            "lineInterpolation": "linear",
                            "lineWidth": 2,
                            "pointSize": 5,
                            "showPoints": "auto",
                        },
                    }
                },
                "gridPos": {"h": 8, "w": 12, "x": 0, "y": 0},
                "id": 1,
                "targets": [
                    {
                        "datasource": {"type": "simpod-json-datasource", "uid": "json"},
                        "target": "test.duration",
                        "type": "timeseries",
                    }
                ],
                "title": "Test Duration Trends",
                "type": "timeseries",
            }
        ],
        "refresh": "5s",
        "schemaVersion": 38,
        "style": "dark",
        "tags": ["pytest-insight"],
        "title": "Test Metrics Dashboard",
        "version": 1,
        "time": {"from": "now-6h", "to": "now"},
    }

    import json

    dashboard_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dashboard_path, "w") as f:
        json.dump(default_dashboard, f, indent=2)
