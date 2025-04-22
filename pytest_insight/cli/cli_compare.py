"""CLI command for comparing test sessions.

This module provides a command-line interface for comparing test sessions
and identifying differences between them.
"""

from typing import Optional

import typer

app = typer.Typer(help="Compare test sessions")


@app.command("suts")
def compare_suts(
    base_sut: str = typer.Option(..., help="Base SUT name"),
    target_sut: str = typer.Option(..., help="Target SUT name"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Compare test sessions between two SUTs.

    This command compares test sessions between two SUTs and identifies differences
    such as new failures, new passes, reliability_rate tests, and performance changes.

    Examples:
        insight compare suts --base-sut service-v1 --target-sut service-v2
        insight compare suts --base-sut service-v1 --target-sut service-v2 --days 60
        insight compare suts --base-sut service-v1 --target-sut service-v2 --profile production
    """
    from pytest_insight.cli.cli_dev import cli_compare

    cli_compare(base_sut=base_sut, target_sut=target_sut, days=days, profile=profile)


@app.command("sessions")
def compare_sessions(
    base_session: str = typer.Option(..., help="Base session ID"),
    target_session: str = typer.Option(..., help="Target session ID"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Compare two specific test sessions.

    This command compares two specific test sessions by their session IDs and
    identifies differences between them.

    Examples:
        insight compare sessions --base-session session-123 --target-session session-456
        insight compare sessions --base-session session-123 --target-session session-456 --profile production
    """
    from pytest_insight.cli.cli_dev import cli_compare_sessions

    cli_compare_sessions(base_session=base_session, target_session=target_session, profile=profile)


if __name__ == "__main__":
    app()
