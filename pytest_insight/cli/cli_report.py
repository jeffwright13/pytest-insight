import typer

from pytest_insight.core.storage import get_profile_manager

app = typer.Typer(help="Reporting tools for pytest-insight", no_args_is_help=True)


def _resolve_profile(profile):
    if profile is None:
        pm = get_profile_manager()
        profile = pm.active_profile_name
    if not profile:
        typer.secho(
            "No profile specified and no active profile set. Use --profile or set an active profile.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(1)
    return profile


@app.command()
def terminal(profile: str = None):
    """Print a report to the terminal (identical to pytest --insight terminal output)."""
    profile = _resolve_profile(profile)
    # TODO: Implement terminal report
    typer.echo(f"[report] Terminal report for profile '{profile}'")
