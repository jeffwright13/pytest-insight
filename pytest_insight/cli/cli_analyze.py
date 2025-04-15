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
    nonreliability_rate rates, and overall health scores.

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


@app.command("top-failing")
def analyze_top_failing(
    limit: int = typer.Option(10, help="Number of top failing tests to show"),
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Identify tests that fail most frequently.

    This command finds and ranks tests by their failure frequency, helping identify
    systemic issues or brittle tests.

    Examples:
        insight analyze top-failing
        insight analyze top-failing --limit 20
        insight analyze top-failing --days 60 --profile production
    """
    from rich.console import Console
    from rich.table import Table

    from pytest_insight.core.core_api import InsightAPI

    console = Console()

    # Initialize API
    api = InsightAPI(profile_name=profile)

    # Get top failing tests
    analysis = api.analyze()
    if sut:
        analysis = analysis.for_sut(sut)

    results = analysis.sessions.top_failing_tests(days=days, limit=limit)

    # Display results
    console.print(f"\n[bold]Top {limit} Failing Tests[/bold] (past {days} days)")

    if not results["top_failing"]:
        console.print("[yellow]No failing tests found in the specified time period.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Test", style="cyan")
    table.add_column("Failures", style="red")
    table.add_column("Total Runs", style="blue")
    table.add_column("Failure Rate", style="magenta")

    for test in results["top_failing"]:
        failure_rate = f"{test['failure_rate'] * 100:.1f}%"
        table.add_row(test["nodeid"], str(test["failures"]), str(test["total_runs"]), failure_rate)

    console.print(table)
    console.print(f"\nTotal failures: {results['total_failures']}")


@app.command("regression-rate")
def analyze_regression_rate(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Calculate the regression rate of tests.

    Regression rate is the percentage of tests that were passing in previous sessions
    but failed in the most recent session. This helps identify newly introduced instability.

    Examples:
        insight analyze regression-rate
        insight analyze regression-rate --days 60
        insight analyze regression-rate --profile production
    """
    from rich.console import Console
    from rich.table import Table

    from pytest_insight.core.core_api import InsightAPI

    console = Console()

    # Initialize API
    api = InsightAPI(profile_name=profile)

    # Get regression rate
    analysis = api.analyze()
    if sut:
        analysis = analysis.for_sut(sut)

    results = analysis.sessions.regression_rate(days=days)

    # Display results
    console.print(f"\n[bold]Regression Rate Analysis[/bold] (past {days} days)")

    # Format the regression rate as a percentage
    regression_rate = f"{results['regression_rate'] * 100:.2f}%"

    # Create a table for the summary
    summary_table = Table(show_header=True)
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="magenta")

    summary_table.add_row("Regression Rate", regression_rate)
    summary_table.add_row("Total Regressions", str(results["total_regressions"]))

    console.print(summary_table)

    # Show regressed tests if available
    if results["regressed_tests"]:
        console.print("\n[bold]Recently Regressed Tests:[/bold]")

        regressed_table = Table(show_header=True)
        regressed_table.add_column("Test", style="cyan")
        regressed_table.add_column("Previous Outcomes", style="yellow")
        regressed_table.add_column("Latest Outcome", style="red")

        for test in results["regressed_tests"]:
            previous_outcomes = ", ".join([outcome.name for outcome in test["previous_outcomes"]])
            latest_outcome = test["latest_outcome"].name

            regressed_table.add_row(test["nodeid"], previous_outcomes, latest_outcome)

        console.print(regressed_table)
    else:
        console.print("[green]No regressions detected in the specified time period.[/green]")


@app.command("longest-tests")
def analyze_longest_tests(
    limit: int = typer.Option(10, help="Number of longest tests to show"),
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Identify the longest running tests.

    This command finds and ranks tests by their execution time, helping guide
    optimization efforts for slow tests.

    Examples:
        insight analyze longest-tests
        insight analyze longest-tests --limit 20
        insight analyze longest-tests --days 60 --profile production
    """
    from rich.console import Console
    from rich.table import Table

    from pytest_insight.core.core_api import InsightAPI

    console = Console()

    # Initialize API
    api = InsightAPI(profile_name=profile)

    # Get longest tests
    analysis = api.analyze()
    if sut:
        analysis = analysis.for_sut(sut)

    results = analysis.sessions.longest_running_tests(days=days, limit=limit)

    # Display results
    console.print(f"\n[bold]Top {limit} Longest Running Tests[/bold] (past {days} days)")

    if not results["longest_tests"]:
        console.print("[yellow]No tests found in the specified time period.[/yellow]")
        return

    table = Table(show_header=True)
    table.add_column("Test", style="cyan")
    table.add_column("Avg Duration", style="magenta")
    table.add_column("Max Duration", style="red")
    table.add_column("Min Duration", style="green")
    table.add_column("Runs", style="blue")

    for test in results["longest_tests"]:
        avg_duration = f"{test['avg_duration']:.2f}s"
        max_duration = f"{test['max_duration']:.2f}s"
        min_duration = f"{test['min_duration']:.2f}s"

        table.add_row(test["nodeid"], avg_duration, max_duration, min_duration, str(test["runs"]))

    console.print(table)
    console.print(f"\nTotal Duration: {results['total_duration']:.2f}s")
    console.print(f"Average Test Duration: {results['avg_duration']:.2f}s")


@app.command("duration-trend")
def analyze_duration_trend(
    sut: Optional[str] = typer.Option(None, help="System Under Test (SUT) to analyze"),
    days: int = typer.Option(30, help="Number of days to include in analysis"),
    window: int = typer.Option(7, help="Window size for trend analysis"),
    profile: Optional[str] = typer.Option(None, help="Storage profile to use"),
):
    """Analyze the trend in test suite duration over time.

    This command tracks how the total execution time changes over time,
    helping detect slow creep in runtime cost.

    Examples:
        insight analyze duration-trend
        insight analyze duration-trend --days 60
        insight analyze duration-trend --window 14
    """
    from rich.console import Console
    from rich.table import Table

    from pytest_insight.core.core_api import InsightAPI

    console = Console()

    # Initialize API
    api = InsightAPI(profile_name=profile)

    # Get duration trend
    analysis = api.analyze()
    if sut:
        analysis = analysis.for_sut(sut)

    results = analysis.sessions.test_suite_duration_trend(days=days, window_size=window)

    # Display results
    console.print(f"\n[bold]Test Suite Duration Trend[/bold] (past {days} days, window size: {window})")

    if not results["durations"]:
        console.print("[yellow]Not enough data to analyze duration trend.[/yellow]")
        return

    trend = results["trend"]
    change = trend["change"]
    direction = trend["direction"]

    # Format the trend information
    if direction == "stable":
        trend_text = f"[blue]Stable[/blue] (Change: {change:.1f}%)"
    elif direction == "increasing":
        trend_text = f"[red]Increasing[/red] (Change: +{change:.1f}%)"
    else:  # decreasing
        trend_text = f"[green]Decreasing[/green] (Change: {change:.1f}%)"

    console.print(f"Trend: {trend_text}")
    console.print(f"Significant: {'[red]Yes[/red]' if results['significant'] else '[blue]No[/blue]'}")

    # Show recent session durations
    console.print("\n[bold]Recent Session Durations:[/bold]")

    table = Table(show_header=True)
    table.add_column("Session ID", style="cyan")
    table.add_column("Timestamp", style="blue")
    table.add_column("Duration", style="magenta")

    # Show up to 10 most recent sessions
    for session in results["durations"][-10:]:
        duration = f"{session['duration']:.2f}s"
        timestamp = session["timestamp"].strftime("%Y-%m-%d %H:%M:%S")

        table.add_row(session["session_id"], timestamp, duration)

    console.print(table)


if __name__ == "__main__":
    app()
