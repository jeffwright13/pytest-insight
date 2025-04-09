"""CLI command for launching the pytest-insight dashboard.

This module provides a command-line interface for launching the pytest-insight
web dashboard for visualizing test insights and predictive analytics.
"""

import os
import sys
import subprocess
import typer
from typing import Optional

app = typer.Typer(help="Launch the pytest-insight web dashboard")


@app.command("launch")
def launch_dashboard(
    port: int = typer.Option(8501, help="Port to run the dashboard on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(True, help="Open dashboard in browser automatically"),
):
    """Launch the pytest-insight web dashboard.

    This command starts a Streamlit server to host the pytest-insight dashboard,
    which provides visualizations of test insights and predictive analytics.

    Examples:
        insight dashboard launch
        insight dashboard launch --port 8502
        insight dashboard launch --profile production
        insight dashboard launch --no-browser
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
