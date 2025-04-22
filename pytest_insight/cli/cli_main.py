import typer

from pytest_insight.cli import cli_analyze, cli_data, cli_profile, cli_report, cli_web

app = typer.Typer(help="Pytest Insight: Unified analytics CLI", no_args_is_help=True)

app.add_typer(
    cli_profile.app,
    name="profile",
    help="Manage storage profiles",
    no_args_is_help=True,
)
app.add_typer(
    cli_data.app,
    name="data",
    help="Manage test data for profiles",
    no_args_is_help=True,
)
app.add_typer(
    cli_analyze.app,
    name="analyze",
    help="Analyze test sessions and results",
    no_args_is_help=True,
)
app.add_typer(
    cli_report.app,
    name="report",
    help="Reporting tools for pytest-insight",
    no_args_is_help=True,
)
app.add_typer(
    cli_web.app,
    name="web",
    help="Web-based tools (API Explorer, Dashboard, etc.)",
    no_args_is_help=True,
)

if __name__ == "__main__":
    app()
