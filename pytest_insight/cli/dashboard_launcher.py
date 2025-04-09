#!/usr/bin/env python
"""Standalone launcher for the pytest-insight dashboard.

This script provides a simple way to launch the dashboard without
depending on the full CLI infrastructure.
"""

import os
import subprocess
import sys
from typing import Optional

import typer

app = typer.Typer(help="Launch the pytest-insight dashboard")


@app.command()
def launch(
    port: int = typer.Option(8501, help="Port to run the dashboard on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(True, help="Open dashboard in browser automatically"),
):
    """Launch the pytest-insight web dashboard.

    This command starts a Streamlit server to host the pytest-insight dashboard,
    which provides visualizations of test insights and predictive analytics.

    Examples:
        python -m pytest_insight.cli.dashboard_launcher
        python -m pytest_insight.cli.dashboard_launcher --port 8502
        python -m pytest_insight.cli.dashboard_launcher --profile production
        python -m pytest_insight.cli.dashboard_launcher --no-browser
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
        print(f"Launching pytest-insight dashboard on port {port}...")
        print(f"Dashboard URL: http://localhost:{port}")
        print("Press Ctrl+C to stop the dashboard")

        subprocess.run(cmd)

    except Exception as e:
        print(f"Error launching dashboard: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    app()
