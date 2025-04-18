"""CLI command for launching the pytest-insight API Explorer dashboard.

This module provides a command-line interface for launching the pytest-insight
REST API Explorer dashboard for exploring and documenting the API.
"""

import importlib.util
import os
import sys
from typing import Optional

import typer
from rich.console import Console

app = typer.Typer(help="Launch the pytest-insight API Explorer dashboard")


@app.command("launch")
def launch_api_explorer(
    port: int = typer.Option(8000, help="Port to run the API Explorer on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(
        True,
        "--browser/--no-browser",
        help="Open API Explorer in browser automatically",
    ),
):
    """Launch the pytest-insight API Explorer dashboard and open it in a browser.

    This command starts a FastAPI server to host the pytest-insight API Explorer,
    which provides interactive documentation and exploration of the pytest-insight API.
    By default, it will open the API Explorer in your default web browser.

    Examples:
        insight api-explorer launch
        insight api-explorer launch --port 8080
        insight api-explorer launch --profile production
        insight api-explorer launch --no-browser
    """
    _run_api_explorer(port, profile, browser)


@app.command("create")
def create_api_explorer(
    port: int = typer.Option(8000, help="Port to run the API Explorer on"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
    browser: bool = typer.Option(
        False,
        "--browser/--no-browser",
        help="Open API Explorer in browser automatically",
    ),
):
    """Create the pytest-insight API Explorer dashboard without opening a browser.

    This command starts a FastAPI server to host the pytest-insight API Explorer,
    which provides interactive documentation and exploration of the pytest-insight API.
    Unlike 'launch', this command will NOT open the API Explorer in a browser by default.

    Examples:
        insight api-explorer create
        insight api-explorer create --port 8080
        insight api-explorer create --profile production
        insight api-explorer create --browser
    """
    _run_api_explorer(port, profile, browser)


def _run_api_explorer(port: int, profile: Optional[str], browser: bool):
    """Internal function to run the API Explorer with the specified options.

    Args:
        port: Port to run the API Explorer on
        profile: Storage profile to use
        browser: Whether to open the API Explorer in a browser
    """
    console = Console()

    try:
        # Check for required API Explorer dependencies
        missing_deps = []
        for package in ["fastapi", "uvicorn"]:
            if importlib.util.find_spec(package) is None:
                missing_deps.append(package)

        if missing_deps:
            console.print(f"[bold red]Error: Missing required dependencies: {', '.join(missing_deps)}[/bold red]")
            console.print("API Explorer functionality requires additional dependencies.")
            console.print("Install them with: [bold]uv pip install 'pytest-insight[visualize]'[/bold]")
            sys.exit(1)

        # Set profile if specified
        if profile:
            os.environ["PYTEST_INSIGHT_PROFILE"] = profile

        # Import the create_introspected_api function
        from pytest_insight.rest_api.introspective_api import create_introspected_api

        # Build the URL
        url = f"http://localhost:{port}"
        dashboard_url = f"{url}/dashboard"
        docs_url = f"{url}/docs"

        # Print startup message
        console.print(
            f"[bold green]{'Launching' if browser else 'Creating'} pytest-insight API Explorer on port {port}...[/bold green]"
        )
        console.print(f"[bold]API Explorer URL:[/bold] {url}")
        console.print(f"[bold]API Dashboard:[/bold] {dashboard_url}")
        console.print(f"[bold]API Documentation:[/bold] {docs_url}")
        console.print("[yellow]Press Ctrl+C to stop the API Explorer[/yellow]")

        # Open browser if requested
        if browser:
            import webbrowser

            webbrowser.open(dashboard_url)

        # Create and run the FastAPI app
        app = create_introspected_api()
        import uvicorn

        uvicorn.run(app, host="0.0.0.0", port=port)

    except Exception as e:
        console.print(f"[bold red]Error {'launching' if browser else 'creating'} API Explorer: {str(e)}[/bold red]")
        import traceback

        console.print(traceback.format_exc(), style="red")
        sys.exit(1)


if __name__ == "__main__":
    app()
