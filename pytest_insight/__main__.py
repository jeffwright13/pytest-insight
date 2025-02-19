from datetime import datetime, timedelta

import pytest
import typer
from typing_extensions import Annotated
from typing import Optional, List
from collections import Counter

from pytest_insight.storage import get_storage_instance
from pytest_insight.analytics import SUTAnalytics
from pytest_insight.filters import TestFilter, common_filter_options

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
@common_filter_options
def show_session(
    sut: Optional[str] = None,
    days: Optional[int] = None,
    outcome: Optional[str] = None,
    warnings: Optional[bool] = None,
    reruns: Optional[bool] = None,
    contains: Optional[str] = None
):
    """Show details of test sessions with optional filtering."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Apply filters
    test_filter = TestFilter(
        sut=sut,
        days=days,
        outcome=outcome,
        has_warnings=warnings,
        has_reruns=reruns,
        nodeid_contains=contains
    )

    filtered_sessions = test_filter.filter_sessions(sessions)
    if not filtered_sessions:
        typer.echo("No sessions match the specified filters.")
        raise typer.Exit(1)

    session = filtered_sessions[-1]  # Get most recent matching session
    filtered_results = test_filter.filter_results(session.test_results)

    # Update statistics for filtered results
    unique_tests = {test.nodeid: test for test in filtered_results}
    total_tests = len(unique_tests)

    # Count outcomes
    outcomes = {}
    for test in filtered_results:
        outcome = test.outcome.capitalize()
        outcomes[outcome] = outcomes.get(outcome, 0) + 1

    # Count warnings
    total_warnings = sum(test.has_warning for test in filtered_results)
    unique_warnings = len({test.nodeid for test in filtered_results if test.has_warning})

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
def show_summary(
    sut: str = typer.Argument(None, help="Show summary for specific SUT"),
    days: int = typer.Option(7, help="Show summary for last N days")
):
    """Show comprehensive test execution summary."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter sessions
    cutoff = datetime.now() - timedelta(days=days)
    if sut:
        sessions = [s for s in sessions if s.sut_name == sut and s.session_start_time > cutoff]
    else:
        sessions = [s for s in sessions if s.session_start_time > cutoff]

    if not sessions:
        typer.secho("No test data available for the specified criteria", fg=typer.colors.YELLOW)
        return

    # Calculate summary statistics
    total_sessions = len(sessions)
    total_duration = sum((s.session_stop_time - s.session_start_time).total_seconds() for s in sessions)

    # Aggregate test results across sessions
    all_tests = set()
    outcome_counts = Counter()
    warning_count = 0
    rerun_stats = {
        "total": 0,
        "to_pass": 0,
        "to_fail": 0,
        "groups": 0,
        "groups_passed": 0,
        "groups_failed": 0
    }

    for session in sessions:
        for test in session.test_results:
            all_tests.add(test.nodeid)
            outcome_counts[test.outcome] += 1
            if test.has_warning:
                warning_count += 1

        # Analyze rerun outcomes
        for group in session.rerun_test_groups:
            rerun_stats["total"] += len(group.reruns)
            rerun_stats["groups"] += 1

            if group.final_outcome.upper() == "PASSED":
                rerun_stats["to_pass"] += len(group.reruns)
                rerun_stats["groups_passed"] += 1
            else:
                rerun_stats["to_fail"] += len(group.reruns)
                rerun_stats["groups_failed"] += 1

    # Display summary
    typer.echo(f"\nTest Summary for past {days} days:")
    if sut:
        typer.echo(f"SUT: {sut}")
    typer.echo(f"Sessions: {total_sessions}")
    typer.echo(f"Unique Tests: {len(all_tests)}")
    typer.echo(f"Total Duration: {timedelta(seconds=int(total_duration))}")
    typer.echo(f"Average Session Duration: {timedelta(seconds=int(total_duration/total_sessions))}")

    typer.echo("\nTest Outcomes:")
    for outcome, count in sorted(outcome_counts.items()):
        percentage = (count / sum(outcome_counts.values())) * 100
        typer.echo(f"  {outcome}: {count} ({percentage:.1f}%)")

    if warning_count:
        typer.echo(f"\nWarnings: {warning_count}")

    if rerun_stats["total"]:
        typer.echo("\nRerun Analysis:")
        typer.echo(f"  Total Reruns: {rerun_stats['total']}")
        typer.echo(f"  ↳ Eventually Passed: {rerun_stats['to_pass']}")
        typer.echo(f"  ↳ Remained Failed: {rerun_stats['to_fail']}")
        typer.echo(f"\n  Rerun Groups: {rerun_stats['groups']}")
        typer.echo(f"  ↳ Groups that Passed: {rerun_stats['groups_passed']}")
        typer.echo(f"  ↳ Groups that Failed: {rerun_stats['groups_failed']}")

        # Add success rates
        if rerun_stats['groups'] > 0:
            group_success_rate = (rerun_stats['groups_passed'] / rerun_stats['groups']) * 100
            typer.echo(f"\n  Rerun Success Rate: {group_success_rate:.1f}%")

    # Show session trend
    typer.echo("\nRecent Sessions:")
    for session in sorted(sessions, key=lambda s: s.session_start_time, reverse=True)[:5]:
        passed = sum(1 for t in session.test_results if t.outcome == "PASSED")
        failed = sum(1 for t in session.test_results if t.outcome == "FAILED")
        total = len(session.test_results)
        typer.echo(
            f"  {session.session_start_time.strftime('%Y-%m-%d %H:%M')}: "
            f"{passed}/{total} passed ({(passed/total)*100:.1f}%) "
            f"Duration: {session.session_duration}"
        )


@analytics_app.command("analyze")
@common_filter_options
def analyze_sut(
    sut_name: str = typer.Argument(..., help="Name of SUT to analyze"),
    metric: str = typer.Option("all", help="Metric to analyze"),
    days: Optional[int] = None,
    outcome: Optional[str] = None,
    warnings: Optional[bool] = None,
    reruns: Optional[bool] = None,
    contains: Optional[str] = None
):
    """Analyze test history for a specific SUT."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Create filter with sut_name and any provided filter options
    test_filter = TestFilter(
        sut=sut_name,
        days=days,
        outcome=outcome,
        has_warnings=warnings,
        has_reruns=reruns,
        nodeid_contains=contains
    )

    filtered_sessions = test_filter.filter_sessions(sessions)

    if not filtered_sessions:
        typer.echo(f"No sessions found for SUT: {sut_name}")
        raise typer.Exit(1)

    # Continue with analysis...

    analytics = SUTAnalytics(filtered_sessions)

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


@analytics_app.command("failures")
@common_filter_options
def analyze_failures(
    sut_name: str = typer.Argument(..., help="Name of SUT to analyze"),
    nodeid: str = typer.Option(None, help="Show detailed history for specific test")
):
    """Analyze test failure patterns."""
    analytics = SUTAnalytics(filtered_sessions)

    if nodeid:
        history = analytics.get_test_history_summary(nodeid)
        typer.echo(f"\nHistory for {nodeid}:")
        typer.echo(f"  First seen: {history['first_seen']}")
        typer.echo(f"  Last seen: {history['last_seen']}")
        typer.echo(f"  Total runs: {history['total_runs']}")
        typer.echo(f"  Failure rate: {history['failure_rate']:.1%}")

        if history['transitions']:
            typer.echo("\nState transitions:")
            for t in history['transitions']:
                typer.echo(f"  {t['time']}: {t['from']} → {t['to']}")
                if t['error']:
                    typer.echo(f"    Error: {t['error'][:100]}...")
    else:
        patterns = analytics.analyze_failure_patterns()
        typer.echo("\nMost Common Errors:")
        for msg, count in patterns['common_error_messages']:
            typer.echo(f"  {count}x: {msg[:100]}...")

        typer.echo("\nCorrelated Failures:")
        for (test1, test2), count in patterns['correlated_failures']:
            typer.echo(f"  {count}x: {test1} and {test2} failed together")

        typer.echo("\nMost Flaky Tests:")
        for test, flips in patterns['most_flaky']:
            typer.echo(f"  {test}: {flips} state changes")


if __name__ == "__main__":
    app()
