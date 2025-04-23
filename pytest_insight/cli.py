"""
pytest-insight CLI entrypoint (Typer-based)

Usage:
    python -m pytest_insight.cli [COMMAND]
"""

import typer
from rich import print

from pytest_insight.core.storage import ProfileManager
from pytest_insight.insight_api import InsightAPI

# Main app
app = typer.Typer(help="Pytest Insight: Unified analytics CLI")

@app.command()
def dev_shell(profile: str = typer.Option(None, help="Profile name to load")):
    """Start an interactive developer shell with InsightAPI and profile manager loaded (IPython preferred)."""
    try:
        from pytest_insight.core.storage import ProfileManager
        from pytest_insight.insight_api import InsightAPI
    except ImportError as e:
        print(f"[red]Error importing dependencies: {e}")
        raise typer.Exit(1)
    print("[bold green]Launching dev shell...[/bold green]")
    profile_manager = ProfileManager()
    api = InsightAPI(profile=profile)

    def load_profile(name):
        """Switch to a different profile and return a new InsightAPI instance."""
        return InsightAPI(profile=name)

    def list_profiles():
        """List all available profiles."""
        print("Available profiles:")
        for pname in profile_manager.profiles:
            print(f"  - {pname}")

    banner = (
        "\n[Pytest Insight Dev Shell]\n"
        f"Profile: {profile or 'default'}\n"
        "Objects: api (InsightAPI), profile_manager (ProfileManager), load_profile(name), list_profiles()\n"
        "Type help(api), help(profile_manager), or list_profiles() to get started.\n"
    )
    local_ns = {
        "api": api,
        "profile_manager": profile_manager,
        "load_profile": load_profile,
        "list_profiles": list_profiles,
    }
    try:
        import sys

        from IPython import start_ipython

        class DummyMod:
            pass

        # IPython expects __main__ to be a module with __file__
        sys.modules["__main__"].__file__ = "pytest_insight/cli.py"
        from traitlets.config import Config

        c = Config()
        c.TerminalInteractiveShell.banner1 = banner
        start_ipython(argv=[], user_ns=local_ns, config=c)
    except ImportError:
        print(
            "[yellow]IPython not installed. Falling back to standard Python REPL.[/yellow]"
        )
        import code

        code.interact(local=local_ns, banner=banner)


@app.command()
def api_explorer(
    host: str = typer.Option("127.0.0.1", help="Host to serve the API Explorer UI on"),
    port: int = typer.Option(8001, help="Port to serve the API Explorer UI on"),
    reload: bool = typer.Option(True, help="Enable auto-reload for development"),
):
    """Launch the self-discovering API Explorer UI (Swagger-like, chainable)."""
    try:
        from importlib.util import find_spec

        import uvicorn

        # Check if the explorer app exists
        if not find_spec("pytest_insight.web_api.explorer.explorer_app"):
            print("[red]Explorer app not found. Please ensure it is installed.")
            raise typer.Exit(1)
        print(
            f"[bold green]Launching API Explorer UI at http://{host}:{port} ...[/bold green]"
        )
        uvicorn.run(
            "pytest_insight.web_api.explorer.explorer_app:app",
            host=host,
            port=port,
            reload=reload,
        )
    except ImportError as e:
        print(f"[red]Error: {e}. Did you install with the [explorer] extra?")
        raise typer.Exit(1)


# Report app (for standalone demo)
report_app = typer.Typer(help="Run analytics reports")

def get_api(profile: str) -> InsightAPI:
    """Helper to load InsightAPI with the given profile."""
    return InsightAPI(profile=profile)

@report_app.command("summary")
def summary(profile: str = typer.Option(None, help="Profile to use")):
    """Print session summary metrics."""
    api = get_api(profile)
    print(api.summary().as_text())

@report_app.command("flakiest")
def flakiest(profile: str = typer.Option(None, help="Profile to use")):
    """Show top flaky tests."""
    api = get_api(profile)
    print(api.test().flakiest_tests().as_text())

@report_app.command("slowest")
def slowest(profile: str = typer.Option(None, help="Profile to use")):
    """Show slowest tests."""
    api = get_api(profile)
    print(api.test().slowest_tests().as_text())




if __name__ == "__main__":
    app()
