"""
pytest-insight CLI entrypoint (Typer-based)

Usage:
    python -m pytest_insight.cli [COMMAND]
"""
import typer
from rich import print

app = typer.Typer(help="Pytest Insight: Unified analytics CLI")

@app.command()
def dev_shell(profile: str = typer.Option(None, help="Profile name to load")):
    """Start an interactive developer shell with InsightAPI and profile manager loaded (IPython preferred)."""
    try:
        from pytest_insight.insight_api import InsightAPI
        from pytest_insight.core.storage import ProfileManager
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
        from IPython import start_ipython
        import sys
        class DummyMod:
            pass
        # IPython expects __main__ to be a module with __file__
        sys.modules["__main__"].__file__ = "pytest_insight/cli.py"
        from traitlets.config import Config
        c = Config()
        c.TerminalInteractiveShell.banner1 = banner
        start_ipython(argv=[], user_ns=local_ns, config=c)
    except ImportError:
        print("[yellow]IPython not installed. Falling back to standard Python REPL.[/yellow]")
        import code
        code.interact(local=local_ns, banner=banner)

@app.command()
def console(profile: str = typer.Option(None, help="Profile name to load")):
    """Shortcut: Launch the interactive developer shell (same as dev_shell)."""
    return dev_shell(profile=profile)

if __name__ == "__main__":
    app()
