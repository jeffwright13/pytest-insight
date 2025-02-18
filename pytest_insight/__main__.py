from datetime import datetime, timedelta

import typer
from typing_extensions import Annotated

from pytest_insight.storage import get_storage_instance
from pytest_insight.analytics import SUTAnalytics

# Create typer apps with rich help enabled and showing help on ambiguous commands
app = typer.Typer(
    help="Test history and analytics tool for pytest",
    rich_markup_mode="rich",
    no_args_is_help=True,  # Show help when no args provided
    add_completion=True  # Enable completion support
)

session_app = typer.Typer(
    help="Manage test sessions",
    rich_markup_mode="rich",
    no_args_is_help=True
)
history_app = typer.Typer(
    help="View and analyze test history",
    rich_markup_mode="rich",
    no_args_is_help=True
)
sut_app = typer.Typer(
    help="Manage Systems Under Test",
    rich_markup_mode="rich",
    no_args_is_help=True
)
analytics_app = typer.Typer(
    help="Generate test analytics and reports",
    rich_markup_mode="rich",
    no_args_is_help=True
)

# Add sub-applications
app.add_typer(session_app, name="session")
app.add_typer(history_app, name="history")
app.add_typer(sut_app, name="sut")
app.add_typer(analytics_app, name="analytics")

storage = get_storage_instance()


# Session commands
@session_app.command("run")
def run_session(
    path: str = typer.Argument("tests", help="Path to test directory or file")
):
    """Run a new test session."""
    pytest.main([path, "--insight"])




@session_app.command("show")
def show_session():
    """Show details of the most recent test session."""
    storage = get_storage_instance()
    session = storage.get_last_session()

    if not session:
        typer.echo("[pytest-insight] No test sessions found.")
        raise typer.Exit(code=1)

    # Unique test cases (removes duplicates)
    unique_tests = {test.nodeid: test for test in session.test_results}
    total_tests = len(unique_tests)

    # Count outcomes
    outcomes = {}
    for test in session.test_results:
        outcome = test.outcome.capitalize()
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    # Count warnings
    total_warnings = sum(test.has_warning for test in session.test_results)
    unique_warnings = len({test.nodeid for test in session.test_results if test.has_warning})

    # Count rerun statistics
    rerun_stats = {
        "total_reruns": sum(len(group.reruns) for group in session.rerun_test_groups),
        "total_groups": len(session.rerun_test_groups),
        "passed_groups": sum(1 for group in session.rerun_test_groups if group.final_outcome.upper() == "PASSED"),
        "failed_groups": sum(1 for group in session.rerun_test_groups if group.final_outcome.upper() == "FAILED")
    }

    # Print Session Info
    typer.echo("\nSession Info:")
    typer.echo(f"  Session ID: {session.session_id}")
    typer.echo(f"  SUT: {session.sut_name}")
    typer.echo(f"  Start time: {session.session_start_time}")
    typer.echo(f"  Duration: {session.session_duration}")

    # Print Test Statistics
    typer.echo("\nSession Stats:")
    typer.echo(f"  Total Tests: {total_tests}")
    for outcome, count in sorted(outcomes.items()):
        typer.echo(f"  {outcome}: {count}")

    # Print Warning Statistics
    typer.echo("\nWarning Statistics:")
    typer.echo(f"  Total Warnings: {total_warnings}")
    typer.echo(f"  Unique Tests With Warnings: {unique_warnings}")

    # Print Rerun Statistics
    typer.echo("\nRerun Statistics:")
    typer.echo(f"  Total Reruns: {rerun_stats['total_reruns']}")
    typer.echo(f"  Rerun Groups: {rerun_stats['total_groups']}")
    typer.echo(f"  ↳ Rerun Groups That Passed: {rerun_stats['passed_groups']}")
    typer.echo(f"  ↳ Rerun Groups That Failed: {rerun_stats['failed_groups']}")

# History commands
@history_app.command("list")
def list_history(days: int = typer.Option(7, help="Number of days of history to show")):
    """List test session history."""
    sessions = storage.load_sessions()
    cutoff = datetime.now() - timedelta(days=days)
    recent = [s for s in sessions if s.session_start_time > cutoff]
    for session in recent:
        typer.echo(f"{session.session_start_time}: {session.session_id}")


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
def show_summary(sut: str = typer.Argument(None, help="Show summary for specific SUT")):
    """Show test execution summary."""
    session = storage.get_last_session()
    if not session:
        typer.secho("No test data available", fg=typer.colors.YELLOW)
        return

    # Group test results by outcome
    outcomes = {}
    for test in session.test_results:
        if test.outcome not in outcomes:
            outcomes[test.outcome] = 0
        outcomes[test.outcome] += 1

    # Show summary
    typer.echo(f"\nTest Summary for {session.sut_name}")
    typer.echo(f"Session: {session.session_id}")
    typer.echo(f"Run at: {session.session_start_time}")
    typer.echo(f"Duration: {session.session_duration}\n")

    for outcome, count in outcomes.items():
        typer.echo(f"{outcome}: {count}")


@analytics_app.command("analyze")
def analyze_sut(
    sut_name: str = typer.Argument(
        ...,
        help="Name of SUT to analyze",
        autocompletion=lambda: [s.sut_name for s in storage.load_sessions()]
    ),
    metric: str = typer.Option(
        "all",
        help="Metric to analyze",
        autocompletion=lambda: ["all", "stability", "performance", "warnings", "health"]
    )
):
    """Analyze test history for a specific SUT."""
    sessions = storage.load_sessions()
    sut_sessions = [s for s in sessions if s.sut_name == sut_name]

    if not sut_sessions:
        typer.echo(f"No sessions found for SUT: {sut_name}")
        raise typer.Exit(1)

    analytics = SUTAnalytics(sut_sessions)

    if metric in ("all", "stability"):
        stability = analytics.stability_metrics()
        typer.echo("\nStability Metrics:")
        typer.echo(f"  Flaky Tests: {len(stability['flaky_tests'])}")
        typer.echo("\n  Most Unstable Tests:")
        for test, rate in stability["most_unstable"]:
            typer.echo(f"    {test}: {rate:.1%} failure rate")

    if metric in ("all", "performance"):
        perf = analytics.performance_metrics()
        typer.echo("\nPerformance Metrics:")
        typer.echo("\n  Slowest Tests:")
        for test, duration in perf["slowest_tests"]:
            typer.echo(f"    {test}: {duration:.2f}s avg")

    if metric in ("all", "warnings"):
        warnings = analytics.warning_metrics()
        typer.echo("\nWarning Metrics:")
        typer.echo("\n  Most Common Warnings:")
        for msg, count in warnings["common_warnings"]:
            typer.echo(f"    {count}x: {msg[:60]}...")

    if metric in ("all", "health"):
        health = analytics.health_score()
        typer.echo("\nTest Health Scores:")
        for test, score in sorted(health.items(), key=lambda x: x[1]):
            typer.echo(f"  {test}: {score:.0f}/100")


if __name__ == "__main__":
    app()
