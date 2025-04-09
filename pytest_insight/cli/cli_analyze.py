"""CLI command for analyzing test data.

This module provides a command-line interface for analyzing test data
and generating insights.
"""

from typing import Optional

import typer

app = typer.Typer(help="Analyze test data and generate insights")


@app.command("health")
def analyze_health(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Analyze test health metrics.

    This command generates health metrics for test sessions, including pass rates,
    flaky rates, and overall health scores.

    Examples:
        insight analyze health --sut my-service
        insight analyze health --days 60
        insight analyze health --profile production
    """
    from pytest_insight.cli.cli_dev import cli_analyze

    cli_analyze(sut=sut, days=days, profile=profile)


@app.command("patterns")
def analyze_patterns(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Analyze test patterns.

    This command identifies patterns in test data, such as common failure patterns,
    test dependencies, and test clusters.

    Examples:
        insight analyze patterns --sut my-service
        insight analyze patterns --days 60
        insight analyze patterns --profile production
    """
    from pytest_insight.cli.cli_dev import cli_analyze_patterns

    cli_analyze_patterns(sut=sut, days=days, profile=profile)


if __name__ == "__main__":
    app()
