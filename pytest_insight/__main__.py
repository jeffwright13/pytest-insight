import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pytest
import typer
from fastapi.testclient import TestClient

from pytest_insight.analytics import SUTAnalytics
from pytest_insight.cli.commands import get_api
from pytest_insight.cli.display import ResultsDisplay
from pytest_insight.dimensional_comparator import DimensionalComparator
from pytest_insight.dimensions import DurationDimension, ModuleDimension, OutcomeDimension, SUTDimension, TimeDimension
# from pytest_insight.filters import TestFilter  # Old
from pytest_insight.compat import FilterAdapter as TestFilter  # New
from pytest_insight.storage import get_storage_instance
from pytest_insight.time_utils import TimeSpanParser

from .server import app

# Create typer apps with rich help enabled and showing help on ambiguous commands
app = typer.Typer(
    help="Test history and analytics tool for pytest",
    rich_markup_mode="rich",
    no_args_is_help=True,  # Show help when no args provided
    add_completion=True,  # Enable completion support
    context_settings={"help_option_names": ["-h", "--help"]},  # Enable -h as help alias
)

# Update all sub-apps to use the same context settings
session_app = typer.Typer(
    help="Manage test sessions",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
history_app = typer.Typer(
    help="View and analyze test history",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
sut_app = typer.Typer(
    help="Manage Systems Under Test",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)
analytics_app = typer.Typer(
    help="Generate test analytics and reports",
    rich_markup_mode="rich",
    no_args_is_help=True,  # Show help when no args provided
    context_settings={
        "help_option_names": ["-h", "--help"]  # Support both -h and --help
    },
)
metrics_app = typer.Typer(
    help="Test and verify metrics",
    rich_markup_mode="rich",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)

# Add sub-applications
app.add_typer(session_app, name="session")
app.add_typer(history_app, name="history")
app.add_typer(sut_app, name="sut")
app.add_typer(analytics_app, name="analytics")
app.add_typer(metrics_app, name="metrics")

storage = get_storage_instance()

cli = typer.Typer()
client = TestClient(app)


@cli.command()
def test_metric(
    metric: str,
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty print output"),
):
    """Test a specific metric query."""
    response = client.post("/query", json={"target": metric})
    data = response.json()
    if pretty:
        print(json.dumps(data, indent=2))
    else:
        print(data)


@cli.command()
def list_metrics():
    """List all available metrics."""
    response = client.get("/search")
    metrics = response.json()
    for metric in metrics:
        print(metric)


# Add filter support to all relevant commands
@session_app.command("run")
def run_session(
    path: str = typer.Argument("tests", help="Path to test directory or file"),
    sut: str = typer.Option("default_sut", "--sut", help="System Under Test name"),
    pytest_args: List[str] = typer.Argument(None, help="Additional pytest options (after --)"),
):
    """
    Run a new pytest session. All arguments after -- are passed directly to pytest.

    Example:
        insight session run tests --sut my-api -- -v -k "test_api" --tb=short
    """
    # Build pytest arguments list
    pytest_opts = [path, "--insight", f"--insight-sut={sut}"]

    # Add any additional pytest options
    if pytest_args:
        pytest_opts.extend(pytest_args)

    # Run pytest with all options
    typer.echo(f"Running tests in {path} for SUT: {sut}")
    if pytest_args:
        typer.echo(f"Additional pytest options: {' '.join(pytest_args)}")

    pytest.main(pytest_opts)


@session_app.command("show")
@common_filter_options
def show_session(
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by System Under Test name"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Filter by test outcome"),
    warnings: Optional[bool] = typer.Option(None, "--warnings/--no-warnings", help="Filter tests with warnings"),
    reruns: Optional[bool] = typer.Option(None, "--reruns/--no-reruns", help="Filter tests with reruns"),
    contains: Optional[str] = typer.Option(None, "--contains", help="Filter by test name pattern"),
):
    """Show details of test sessions with optional filtering."""
    sessions = storage.load_sessions()

    # Apply filters
    test_filter = TestFilter(
        sut=sut,
        days=days,
        outcome=outcome,
        has_warnings=warnings,
        has_reruns=reruns,
        nodeid_contains=contains,
    )
    filtered_sessions = test_filter.filter_sessions(sessions)

    if not filtered_sessions:
        typer.echo("No sessions found matching filters")
        return

    # Get latest session
    latest = max(filtered_sessions, key=lambda s: s.session_start_time)
    filtered_results = latest.test_results

    # Count outcomes
    outcomes = {}
    for test in filtered_results:
        outcome = test.outcome.value
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    # Count warnings
    warning_count = sum(1 for test in filtered_results if test.has_warning)

    # Display results
    typer.echo("\nTest Session Summary:")
    typer.echo(f"  SUT: {latest.sut_name}")
    typer.echo(f"  Session ID: {latest.session_id}")
    typer.echo(f"  Start Time: {latest.session_start_time}")
    typer.echo(f"  Duration: {latest.session_duration:.2f}s")

    typer.echo("\nTest Results:")
    typer.echo(f"  Total Tests: {len(filtered_results)}")
    for outcome, count in outcomes.items():
        typer.echo(f"  {outcome}: {count}")
    typer.echo(f"  Tests with Warnings: {warning_count}")


@history_app.command("list")
def list_history(
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by System Under Test name"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Filter by test outcome"),
    warnings: Optional[bool] = typer.Option(None, "--warnings/--no-warnings", help="Filter tests with warnings"),
    reruns: Optional[bool] = typer.Option(None, "--reruns/--no-reruns", help="Filter tests with reruns"),
    contains: Optional[str] = typer.Option(None, "--contains", help="Filter by test name pattern"),
    by_sut: bool = typer.Option(False, "--by-sut", "-s", help="Group results by SUT"),
    show_all: bool = typer.Option(False, "--all", "-a", help="Show all entries"),
):
    """List test session history with filtering support."""
    sessions = storage.load_sessions()
    cutoff = datetime.now() - timedelta(days=days)

    # Create filter from options
    test_filter = TestFilter(
        sut=sut, days=days, outcome=outcome, has_warnings=warnings, has_reruns=reruns, nodeid_contains=contains
    )

    # Filter sessions
    filtered_sessions = test_filter.filter_sessions(sessions)

    if not filtered_sessions:
        typer.secho("No test sessions found for the specified criteria", fg=typer.colors.YELLOW)
        return

    # Debug: Show available SUTs
    available_suts = {s.sut_name for s in sessions}
    typer.secho(f"Available SUTs: {', '.join(sorted(available_suts))}", fg=typer.colors.BLUE)

    # Filter by date and optionally by SUT (case-insensitive)
    recent = [s for s in sessions if s.session_start_time > cutoff]
    if sut:
        sut = sut.lower()  # Convert input to lowercase
        recent = [s for s in recent if s.sut_name.lower() == sut]

    if not recent:
        typer.secho("No test sessions found for the specified criteria", fg=typer.colors.YELLOW)
        return

    def format_session_summary(session):
        """Format session summary with safe percentage calculation."""
        passed = sum(1 for t in session.test_results if t.outcome == "PASSED")
        total = len(session.test_results)
        if total == 0:
            return (
                f"{session.session_start_time.strftime('%Y-%m-%d %H:%M')} "
                f"[{session.session_id}]: No tests run (Duration: {session.session_duration})"
            )

        percentage = (passed / total * 100) if total > 0 else 0
        return (
            f"{session.session_start_time.strftime('%Y-%m-%d %H:%M')} "
            f"[{session.session_id}]: "
            f"{passed}/{total} passed ({percentage:.1f}%) "
            f"Duration: {session.session_duration}"
        )

    if by_sut:
        # Group by SUT and show summary for each
        by_sut_dict = {}
        for session in recent:
            if session.sut_name not in by_sut_dict:
                by_sut_dict[session.sut_name] = []
            by_sut_dict[session.sut_name].append(session)

        for sut_name, sut_sessions in sorted(by_sut_dict.items()):
            typer.secho(f"\nSUT: {sut_name}", fg=typer.colors.BLUE, bold=True)
            sorted_sessions = sorted(sut_sessions, key=lambda s: s.session_start_time, reverse=True)

            # Apply truncation if not showing all
            if not show_all:
                sorted_sessions = sorted_sessions[:50]
                total = len(sut_sessions)
                if total > 50:
                    remaining = total - 50
                    typer.secho(
                        f"  Showing 50/{total} entries. Use --all to see {remaining} more.",
                        fg=typer.colors.YELLOW,
                    )

            for session in sorted_sessions:
                session_summary = format_session_summary(session)
                formatted_time = session.session_start_time.strftime("%Y-%m-%d %H:%M")
                typer.echo(f"{formatted_time} [{session.sut_name}]: {session_summary}")
    else:
        # Show flat chronological list
        sorted_sessions = sorted(recent, key=lambda s: s.session_start_time, reverse=True)

        # Apply truncation if not showing all
        if not show_all:
            total = len(sorted_sessions)
            sorted_sessions = sorted_sessions[:50]
            if total > 50:
                remaining = total - 50
                typer.secho(
                    f"Showing 50/{total} entries. Use --all to see {remaining} more.",
                    fg=typer.colors.YELLOW,
                )

        for session in sorted_sessions:
            session_summary = format_session_summary(session)
            formatted_time = session.session_start_time.strftime("%Y-%m-%d %H:%M")
            typer.echo(f"{formatted_time} [{session.sut_name}]: {session_summary}")


# SUT commands
@sut_app.command("list")
def list_suts():
    """List all known Systems Under Test."""
    sessions = storage.load_sessions()
    suts = {s.sut_name for s in sessions}
    for sut in sorted(suts):
        typer.echo(sut)


# Analytics commands
@analytics_app.command("summary")
def analytics_summary(
    sut: Optional[str] = typer.Option(None, "--sut", help="Filter by System Under Test name"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Filter by test outcome"),
    warnings: Optional[bool] = typer.Option(None, "--warnings/--no-warnings", help="Filter tests with warnings"),
    reruns: Optional[bool] = typer.Option(None, "--reruns/--no-reruns", help="Filter tests with reruns"),
    contains: Optional[str] = typer.Option(None, "--contains", help="Filter by test name pattern"),
):
    """Show summary of test analytics with filtering support."""
    api = get_api()

    # Create filter from options
    test_filter = TestFilter(
        sut=sut, days=days, outcome=outcome, has_warnings=warnings, has_reruns=reruns, nodeid_contains=contains
    )

    # Get filtered sessions and results
    sessions = api.get_sessions()
    filtered_sessions = test_filter.filter_sessions(sessions)

    if not filtered_sessions:
        typer.secho("No matching test sessions found.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)

    # Display summary header
    typer.secho("\n=== Test Analytics Summary ===", fg=typer.colors.BLUE, bold=True)

    # Display filter info
    if any([sut, outcome, warnings, reruns, contains]):
        typer.secho("\nActive Filters:", fg=typer.colors.GREEN)
        if sut:
            typer.echo(f"  SUT: {sut}")
        if outcome:
            typer.echo(f"  Outcome: {outcome}")
        if warnings is not None:
            typer.echo(f"  Warnings: {warnings}")
        if reruns is not None:
            typer.echo(f"  Reruns: {reruns}")
        if contains:
            typer.echo(f"  Contains: {contains}")

    # Display statistics
    typer.secho(f"\nTime Range: Last {days} days", fg=typer.colors.BLUE)
    typer.echo(f"Total Sessions: {len(filtered_sessions)}")

    total_tests = sum(len(session.test_results) for session in filtered_sessions)
    typer.echo(f"Total Tests: {total_tests}")

    # Calculate and display outcome distribution
    outcomes = defaultdict(int)
    for session in filtered_sessions:
        for result in session.test_results:
            if test_filter.matches(result):
                outcomes[result.outcome] += 1

    # typer.secho("\nOutcome Distribution:", fg=typer.colors.BLUE)
    # for outcome, count in sorted(outcomes.items()):
    #     percentage = (count / total_tests * 100) if total_tests else 0
    #     typer.echo(f"  {outcome}: {count} ({percentage:.1f}%)")


@analytics_app.command("analyze")
def analyze_sut(
    sut_name: str = typer.Argument(..., help="Name of SUT to analyze"),
    metric: str = typer.Option("all", help="Metric to analyze"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Filter by test outcome"),
    warnings: Optional[bool] = typer.Option(None, "--warnings/--no-warnings", help="Filter tests with warnings"),
    reruns: Optional[bool] = typer.Option(None, "--reruns/--no-reruns", help="Filter tests with reruns"),
    contains: Optional[str] = typer.Option(None, "--contains", help="Filter by test name pattern"),
):
    """Analyze test suite health and patterns with filtering."""
    api = get_api()
    display = ResultsDisplay()

    analysis = api.analyze_health(sut_name)

    if metric in ("all", "health"):
        display.show_health_scores(analysis["health_scores"])

    if metric in ("all", "warnings"):
        display.show_warning_patterns(analysis["warning_patterns"])

    if metric in ("all", "failures"):
        patterns = api.get_failure_patterns(SessionFilter(sut=sut_name))
        display.show_failure_patterns(patterns)


@analytics_app.command("failures")
def analyze_failures(
    sut_name: str = typer.Argument(..., help="Name of SUT to analyze"),
    nodeid: str = typer.Option(None, help="Show detailed history for specific test"),
    days: int = typer.Option(30, "--days", help="Number of days to look back"),
    outcome: Optional[str] = typer.Option(None, "--outcome", help="Filter by test outcome"),
    warnings: Optional[bool] = typer.Option(None, "--warnings/--no-warnings", help="Filter tests with warnings"),
    reruns: Optional[bool] = typer.Option(None, "--reruns/--no-reruns", help="Filter tests with reruns"),
    contains: Optional[str] = typer.Option(None, "--contains", help="Filter by test name pattern"),
):
    """Analyze test failure patterns with filtering."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Create filter with sut_name and any provided filter options
    test_filter = TestFilter(
        sut=sut_name,
        nodeid_contains=nodeid,
    )

    filtered_sessions = test_filter.filter_sessions(sessions)

    if not filtered_sessions:
        typer.echo(f"No sessions found for SUT: {sut_name}")
        raise typer.Exit(1)

    analytics = SUTAnalytics(filtered_sessions)

    if nodeid:
        history = analytics.get_test_history_summary(nodeid)
        display_test_history(history)
    else:
        patterns = analytics.analyze_failure_patterns()
        display_failure_patterns(patterns)


def display_failure_patterns(patterns: Dict[str, Any]) -> None:
    """Display failure pattern analysis."""
    typer.echo("\n=== Failure Pattern Analysis ===\n")

    typer.echo("Most Failed Tests:")
    for test in patterns["most_failed"]:
        typer.echo(f"  • {test['nodeid']} ({test['failure_count']} failures)")

    typer.echo("\nTiming Related Failures:")
    for test in patterns["timing_related"]:
        typer.echo(f"  • {test['nodeid']} (avg duration: {test['avg_duration']:.2f}s)")


def display_test_history(history: Dict[str, Any]) -> None:
    """Display test execution history."""
    typer.echo(f"\n=== Test History: {history['nodeid']} ===\n")
    typer.echo(f"Total Executions: {history['total_runs']}")
    typer.echo(f"Failure Rate: {history['failure_rate']:.2%}")


@app.command("compare", help="Compare test results between two targets (SUTs or time windows)")
def compare(
    base: str = typer.Argument(..., help="Base target (SUT name, time, outcome, etc.)"),
    target: str = typer.Argument(..., help="Target to compare against"),
    dimension: str = typer.Option(
        "sut", "--dimension", "-d", help="Dimension to compare (sut/time/outcome/duration/module)"
    ),
    window: str = typer.Option("1d", "--window", "-w", help="Time window size for time dimension"),
    duration_threshold: float = typer.Option(
        None, "--duration-threshold", "-t", help="Duration threshold in seconds for duration dimension"
    ),
):
    """Compare test results along a dimension."""
    sessions = storage.load_sessions()

    # Create appropriate dimension
    if dimension == "sut":
        dim = SUTDimension()
    elif dimension == "time":
        window_td = TimeSpanParser.parse(window)
        dim = TimeDimension(window_td)
    elif dimension == "outcome":
        dim = OutcomeDimension()
    elif dimension == "duration":
        if duration_threshold:
            ranges = [(duration_threshold, "FAST"), (float("inf"), "SLOW")]
            dim = DurationDimension(ranges)
        else:
            dim = DurationDimension()
    elif dimension == "module":
        dim = ModuleDimension()
    else:
        typer.echo(f"Error: Unknown dimension '{dimension}'", err=True)
        raise typer.Exit(1)

    # Compare using dimension
    comparator = DimensionalComparator(dim)
    results = comparator.compare(sessions, base, target)

    if "error" in results:
        typer.echo(f"Error: {results['error']}", err=True)
        raise typer.Exit(1)

    # Display results
    typer.echo(f"\nComparing {dimension} {base} vs {target}:\n")

    # Show summary stats
    typer.echo("Summary:")
    for side in ["base", "target"]:
        stats = results[side]
        typer.echo(f"  {side.title()}:")
        typer.echo(f"    Total Tests: {stats['total_tests']}")
        typer.echo(f"    Passed: {stats['passed']}")
        typer.echo(f"    Failed: {stats['failed']}")
        typer.echo(f"    Skipped: {stats['skipped']}")
        typer.echo(f"    Duration: {stats['duration']:.2f}s")

    # Show differences
    diffs = results["differences"]
    typer.echo("\nDifferences:")

    if diffs["new_tests"]:
        typer.echo("\n  New Tests:")
        for test in diffs["new_tests"]:
            typer.echo(f"    + {test}")

    if diffs["removed_tests"]:
        typer.echo("\n  Removed Tests:")
        for test in diffs["removed_tests"]:
            typer.echo(f"    - {test}")

    if diffs["status_changes"]:
        typer.echo("\n  Status Changes:")
        for change in diffs["status_changes"]:
            typer.echo(f"    {change['nodeid']}: {change['base_status']} -> {change['target_status']}")

    if diffs["duration_changes"]:
        typer.echo("\n  Significant Duration Changes:")
        for change in diffs["duration_changes"]:
            typer.echo(
                f"    {change['nodeid']}: {change['base_duration']:.2f}s -> "
                f"{change['target_duration']:.2f}s ({change['percent_change']:.1f}% change)"
            )


@metrics_app.command("list")
def list_metrics():
    """List all available metrics following style guide."""
    client = TestClient(app)
    response = client.get("/search")
    metrics = response.json()

    # Group metrics by category for better readability
    categories = {}
    for metric in metrics:
        category = metric.split(".")[1]
        if category not in categories:
            categories[category] = []
        categories[category].append(metric)

    for category, metrics in sorted(categories.items()):
        typer.secho(f"\n{category.upper()}", fg=typer.colors.BLUE, bold=True)
        for metric in sorted(metrics):
            typer.echo(f"  {metric}")


@metrics_app.command("test")
def test_metric(
    metric: str = typer.Argument(..., help="Metric to test"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Pretty print output"),
):
    """Test a specific metric query."""
    client = TestClient(app)
    response = client.post("/query", json={"target": metric})
    data = response.json()

    if pretty:
        typer.echo(json.dumps(data, indent=2))
    else:
        typer.echo(data)


if __name__ == "__main__":
    cli()
    app()
