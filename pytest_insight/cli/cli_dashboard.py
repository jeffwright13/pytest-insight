"""CLI command for launching the pytest-insight dashboard.

This module provides a command-line interface for launching the pytest-insight
web dashboard for visualizing test insights and predictive analytics.
"""

import os
import subprocess
import sys
from typing import Optional

import typer

app = typer.Typer(help="Launch the pytest-insight web dashboard")


@app.command("launch")
def launch_dashboard(
    port: int = typer.Option(8501, help="Port to run the dashboard on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(True, "--browser/--no-browser", help="Open dashboard in browser automatically"),
):
    """Launch the pytest-insight web dashboard and open it in a browser.

    This command starts a Streamlit server to host the pytest-insight dashboard,
    which provides visualizations of test insights and predictive analytics.
    By default, it will open the dashboard in your default web browser.

    Examples:
        insight dashboard launch
        insight dashboard launch --port 8502
        insight dashboard launch --profile production
        insight dashboard launch --no-browser
    """
    _run_dashboard(port, profile, browser)


@app.command("create")
def create_dashboard(
    port: int = typer.Option(8501, help="Port to run the dashboard on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(False, "--browser/--no-browser", help="Open dashboard in browser automatically"),
):
    """Create the pytest-insight web dashboard without opening a browser.

    This command starts a Streamlit server to host the pytest-insight dashboard,
    which provides visualizations of test insights and predictive analytics.
    Unlike 'launch', this command will NOT open the dashboard in a browser by default.

    Examples:
        insight dashboard create
        insight dashboard create --port 8502
        insight dashboard create --profile production
        insight dashboard create --browser
    """
    _run_dashboard(port, profile, browser)


def _run_dashboard(port: int, profile: Optional[str], browser: bool):
    """Internal function to run the dashboard with the specified options.

    Args:
        port: Port to run the dashboard on
        profile: Storage profile to use
        browser: Whether to open the dashboard in a browser
    """
    try:
        # Get the path to the dashboard.py file
        dashboard_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "web",
            "dashboard.py",
        )

        # Build the command
        cmd = [
            "streamlit",
            "run",
            dashboard_path,
            "--server.port",
            str(port),
        ]

        # Add profile if specified
        if profile:
            os.environ["PYTEST_INSIGHT_PROFILE"] = profile

        # Add browser flag
        if not browser:
            cmd.extend(["--server.headless", "true"])

        # Launch the dashboard
        print(f"{'Launching' if browser else 'Creating'} pytest-insight dashboard on port {port}...")
        print(f"Dashboard URL: http://localhost:{port}")
        print("Press Ctrl+C to stop the dashboard")

        subprocess.run(cmd)

    except Exception as e:
        print(f"Error {'launching' if browser else 'creating'} dashboard: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
