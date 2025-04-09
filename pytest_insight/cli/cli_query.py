"""CLI command for querying test data.

This module provides a command-line interface for querying test data
and filtering test sessions.
"""

import typer
from typing import Optional, List

app = typer.Typer(help="Query test data")


@app.command("sessions")
def query_sessions(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to query"),
    days: int = typer.Option(30, help="Number of days to include in query"),
    pattern: Optional[str] = typer.Option(None, help="Pattern to match test nodeids"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Query test sessions.

    This command queries test sessions based on various filters and displays
    the results.

    Examples:
        insight query sessions --sut my-service
        insight query sessions --days 60
        insight query sessions --pattern "test_api*"
        insight query sessions --profile production
    """
    from pytest_insight.cli.cli_dev import cli_query
    cli_query(sut=sut, days=days, pattern=pattern, profile=profile)


@app.command("tests")
def query_tests(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to query"),
    days: int = typer.Option(30, help="Number of days to include in query"),
    pattern: Optional[str] = typer.Option(None, help="Pattern to match test nodeids"),
    outcome: Optional[str] = typer.Option(None, help="Filter by test outcome (PASSED, FAILED, etc.)"),
    min_duration: Optional[float] = typer.Option(None, help="Minimum test duration in seconds"),
    max_duration: Optional[float] = typer.Option(None, help="Maximum test duration in seconds"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Query individual tests.

    This command queries individual tests based on various filters and displays
    the results.

    Examples:
        insight query tests --sut my-service
        insight query tests --outcome FAILED
        insight query tests --min-duration 5.0
        insight query tests --pattern "test_api*" --outcome FAILED
    """
    from pytest_insight.cli.cli_dev import cli_query_tests
    cli_query_tests(
        sut=sut, 
        days=days, 
        pattern=pattern, 
        outcome=outcome,
        min_duration=min_duration,
        max_duration=max_duration,
        profile=profile
    )


if __name__ == "__main__":
    app()
