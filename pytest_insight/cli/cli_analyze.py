import typer

from pytest_insight.core.storage import get_profile_manager

app = typer.Typer(help="Analyze test sessions and results", no_args_is_help=True)


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
def summary(profile: str = None):
    """Show summary analysis (health, pass/fail, etc.)."""
    profile = _resolve_profile(profile)
    # TODO: Implement summary analysis
    typer.echo(f"[analyze] Summary analysis for profile '{profile}'")


@app.command()
def reliability(profile: str = None):
    """Analyze test reliability (reliability index, formerly flakiness)."""
    profile = _resolve_profile(profile)
    # TODO: Implement reliability analysis
    typer.echo(f"[analyze] Reliability analysis for profile '{profile}'")


@app.command()
def trends(profile: str = None):
    """Show reliability/performance trends."""
    profile = _resolve_profile(profile)
    # TODO: Implement trend analysis
    typer.echo(f"[analyze] Trend analysis for profile '{profile}'")
