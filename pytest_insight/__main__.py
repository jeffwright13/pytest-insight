from collections import Counter
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import pytest
import typer

from pytest_insight.analytics import SUTAnalytics
from pytest_insight.compare import ComparisonAnalyzer, SUTComparator
from pytest_insight.filters import TestFilter, common_filter_options
from pytest_insight.storage import get_storage_instance
from pytest_insight.time_utils import TimeSpanParser

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
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
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
    path: str = typer.Argument("tests", help="Path to test directory or file"),
    sut: str = typer.Option("default_sut", "--sut", help="System Under Test name"),
    pytest_args: List[str] = typer.Argument(
        None, help="Additional pytest options (after --)"
    ),
):
    """
    Run a new test session.

    All arguments after -- are passed directly to pytest.

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
    sut: Optional[str] = None,
    days: Optional[int] = None,
    outcome: Optional[str] = None,
    warnings: Optional[bool] = None,
    reruns: Optional[bool] = None,
    contains: Optional[str] = None,
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
        nodeid_contains=contains,
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
    unique_warnings = len(
        {test.nodeid for test in filtered_results if test.has_warning}
    )

    # Count rerun statistics
    rerun_stats = {
        "total_reruns": sum(len(group.reruns) for group in session.rerun_test_groups),
        "total_groups": len(session.rerun_test_groups),
        "passed_groups": sum(
            1
            for group in session.rerun_test_groups
            if group.final_outcome.upper() == "PASSED"
        ),
        "failed_groups": sum(
            1
            for group in session.rerun_test_groups
            if group.final_outcome.upper() == "FAILED"
        ),
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
def list_history(
    timespan: str = typer.Option(
        "7d", "--time", "-t", help="Time span to show (e.g., 7d, 24h, 30m, 1d12h)"
    ),
    by_sut: bool = typer.Option(False, "--by-sut", "-s", help="Group results by SUT"),
    sut: Optional[str] = typer.Option(None, help="Show history for specific SUT"),
):
    """List test session history, optionally grouped by SUT."""
    try:
        delta = TimeSpanParser.parse(timespan)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    sessions = storage.load_sessions()
    cutoff = datetime.now() - delta

    # Debug: Show available SUTs
    available_suts = {s.sut_name for s in sessions}
    typer.secho(
        f"Available SUTs: {', '.join(sorted(available_suts))}", fg=typer.colors.BLUE
    )

    # Filter by date and optionally by SUT (case-insensitive)
    recent = [s for s in sessions if s.session_start_time > cutoff]
    if sut:
        sut = sut.lower()  # Convert input to lowercase
        recent = [s for s in recent if s.sut_name.lower() == sut]

    if not recent:
        typer.secho(
            "No test sessions found for the specified criteria", fg=typer.colors.YELLOW
        )
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
            for session in sorted(
                sut_sessions, key=lambda s: s.session_start_time, reverse=True
            ):
                typer.echo(f"  {format_session_summary(session)}")
    else:
        # Show flat chronological list
        for session in sorted(recent, key=lambda s: s.session_start_time, reverse=True):
            typer.echo(
                f"{session.session_start_time.strftime('%Y-%m-%d %H:%M')} [{session.sut_name}]: {format_session_summary(session)}"
            )


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
    days: int = typer.Option(7, help="Show summary for last N days"),
):
    """Show comprehensive test execution summary."""
    storage = get_storage_instance()
    sessions = storage.load_sessions()

    # Filter sessions
    cutoff = datetime.now() - timedelta(days=days)
    if sut:
        sessions = [
            s for s in sessions if s.sut_name == sut and s.session_start_time > cutoff
        ]
    else:
        sessions = [s for s in sessions if s.session_start_time > cutoff]

    if not sessions:
        typer.secho(
            "No test data available for the specified criteria", fg=typer.colors.YELLOW
        )
        return

    # Calculate summary statistics
    total_sessions = len(sessions)
    total_duration = sum(
        (s.session_stop_time - s.session_start_time).total_seconds() for s in sessions
    )

    # Display summary
    typer.echo(f"\nTest Summary for past {days} days:")
    if sut:
        typer.echo(f"SUT: {sut}")
    typer.echo(f"Sessions: {total_sessions}")

    # Safely calculate and display duration statistics
    if total_sessions > 0:
        typer.echo(f"Total Duration: {timedelta(seconds=int(total_duration))}")
        typer.echo(
            f"Average Session Duration: {timedelta(seconds=int(total_duration/total_sessions))}"
        )

    # Aggregate test results across sessions
    all_tests = set()
    outcome_counts = Counter()
    warning_count = 0

    for session in sessions:
        for test in session.test_results:
            all_tests.add(test.nodeid)
            outcome_counts[test.outcome] += 1
            if test.has_warning:
                warning_count += 1

    typer.echo(f"Unique Tests: {len(all_tests)}")

    # Safely display outcome percentages
    total_outcomes = sum(outcome_counts.values())
    if total_outcomes > 0:
        typer.echo("\nTest Outcomes:")
        for outcome, count in sorted(outcome_counts.items()):
            percentage = (count / total_outcomes) * 100
            typer.echo(f"  {outcome}: {count} ({percentage:.1f}%)")

    if warning_count:
        typer.echo(f"\nWarnings: {warning_count}")

    # Process rerun statistics
    rerun_stats = {
        "total": 0,
        "to_pass": 0,
        "to_fail": 0,
        "groups": 0,
        "groups_passed": 0,
        "groups_failed": 0,
    }

    for session in sessions:
        for group in session.rerun_test_groups:
            rerun_stats["total"] += len(group.reruns)
            rerun_stats["groups"] += 1

            if group.final_outcome.upper() == "PASSED":
                rerun_stats["to_pass"] += len(group.reruns)
                rerun_stats["groups_passed"] += 1
            else:
                rerun_stats["to_fail"] += len(group.reruns)
                rerun_stats["groups_failed"] += 1

    if rerun_stats["total"]:
        typer.echo("\nRerun Analysis:")
        typer.echo(f"  Total Reruns: {rerun_stats['total']}")
        typer.echo(f"  ↳ Eventually Passed: {rerun_stats['to_pass']}")
        typer.echo(f"  ↳ Remained Failed: {rerun_stats['to_fail']}")
        typer.echo(f"\n  Rerun Groups: {rerun_stats['groups']}")
        typer.echo(f"  ↳ Groups that Passed: {rerun_stats['groups_passed']}")
        typer.echo(f"  ↳ Groups that Failed: {rerun_stats['groups_failed']}")

        # Safely calculate success rate
        if rerun_stats["groups"] > 0:
            group_success_rate = (
                rerun_stats["groups_passed"] / rerun_stats["groups"]
            ) * 100
            typer.echo(f"\n  Rerun Success Rate: {group_success_rate:.1f}%")


@analytics_app.command("analyze")
@common_filter_options
def analyze_sut(
    sut_name: str = typer.Argument(..., help="Name of SUT to analyze"),
    metric: str = typer.Option("all", help="Metric to analyze"),
    days: Optional[int] = None,
    outcome: Optional[str] = None,
    warnings: Optional[bool] = None,
    reruns: Optional[bool] = None,
    contains: Optional[str] = None,
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
        nodeid_contains=contains,
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
    nodeid: str = typer.Option(None, help="Show detailed history for specific test"),
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

        if history["transitions"]:
            typer.echo("\nState transitions:")
            for t in history["transitions"]:
                typer.echo(f"  {t['time']}: {t['from']} → {t['to']}")
                if t["error"]:
                    typer.echo(f"    Error: {t['error'][:100]}...")
    else:
        patterns = analytics.analyze_failure_patterns()
        typer.echo("\nMost Common Errors:")
        for msg, count in patterns["common_error_messages"]:
            typer.echo(f"  {count}x: {msg[:100]}...")

        typer.echo("\nCorrelated Failures:")
        for (test1, test2), count in patterns["correlated_failures"]:
            typer.echo(f"  {count}x: {test1} and {test2} failed together")

        typer.echo("\nMost Flaky Tests:")
        for test, flips in patterns["most_flaky"]:
            typer.echo(f"  {test}: {flips} state changes")


class ComparisonMode(str, Enum):
    """Comparison modes for analytics."""

    SESSION = "session"
    SUT = "sut"
    PERIOD = "period"


@analytics_app.command("compare")
def compare(
    base: str = typer.Argument(
        ..., help="Base session ID, SUT name, or date (YYYY-MM-DD)"
    ),
    target: str = typer.Argument(
        ..., help="Target session ID, SUT name, or date (YYYY-MM-DD)"
    ),
    mode: ComparisonMode = typer.Option(
        ComparisonMode.SESSION,
        "--mode",
        "-m",
        help="Comparison mode: session, sut, or period",
    ),
    timespan: str = typer.Option(
        "7d", "--time", "-t", help="Time span to include (e.g., 7d, 24h, 30m, 1d12h)"
    ),
):
    """Compare test results between sessions, SUTs, or time periods."""
    try:
        delta = TimeSpanParser.parse(timespan)
    except ValueError as e:
        typer.secho(str(e), fg=typer.colors.RED)
        raise typer.Exit(1)

    storage = get_storage_instance()
    sessions = storage.load_sessions()

    if mode == ComparisonMode.SESSION:
        base_session = next((s for s in sessions if s.session_id == base), None)
        target_session = next((s for s in sessions if s.session_id == target), None)

        if not base_session or not target_session:
            typer.secho("Session(s) not found", fg=typer.colors.RED)
            raise typer.Exit(1)

        results = ComparisonAnalyzer.compare_sessions(base_session, target_session)
        _display_session_comparison(
            results, base_session.session_id, target_session.session_id
        )

    elif mode == ComparisonMode.SUT:
        results = SUTComparator.compare_suts(sessions, base, target, delta.days)
        _display_sut_comparison(results, base, target, delta.days)

    elif mode == ComparisonMode.PERIOD:
        try:
            base_date = datetime.strptime(base, "%Y-%m-%d")
            target_date = datetime.strptime(target, "%Y-%m-%d")
        except ValueError:
            typer.secho("Invalid date format. Use YYYY-MM-DD", fg=typer.colors.RED)
            raise typer.Exit(1)

        results = ComparisonAnalyzer.compare_periods(
            sessions, base_date, target_date, delta.days
        )
        _display_period_comparison(results, base_date, target_date, delta.days)


def _display_session_comparison(results: Dict, base_id: str, target_id: str):
    """Display session comparison results."""
    typer.secho("\nComparing sessions:", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Base: {base_id}")
    typer.echo(f"  Target: {target_id}")

    typer.secho("\nTest Changes:", fg=typer.colors.GREEN)
    for change_type, test, from_state, to_state in results["changes"]:
        if change_type == "added":
            typer.secho(f"  [+] {test}: {to_state}", fg=typer.colors.GREEN)
        elif change_type == "removed":
            typer.secho(f"  [-] {test}: {from_state}", fg=typer.colors.RED)
        else:
            typer.secho(
                f"  [*] {test}: {from_state} → {to_state}", fg=typer.colors.YELLOW
            )

    if results["performance_changes"]:
        typer.secho("\nPerformance Changes:", fg=typer.colors.BLUE)
        for test, base_time, target_time in results["performance_changes"]:
            change = ((target_time - base_time) / base_time) * 100
            typer.echo(
                f"  {test}: {base_time:.2f}s → {target_time:.2f}s ({change:+.1f}%)"
            )


def _display_sut_comparison(results: Dict, sut1: str, sut2: str, days: int):
    """Display SUT comparison results."""
    coverage = results["test_coverage"]

    typer.secho(
        f"\nTest Coverage Comparison ({days} days):", fg=typer.colors.BLUE, bold=True
    )
    typer.echo(f"  {sut1}: {coverage['total_sut1']} total tests")
    typer.echo(f"  {sut2}: {coverage['total_sut2']} total tests")
    typer.echo(f"  Common tests: {len(coverage['common'])}")

    if coverage["unique_to_sut1"]:
        typer.secho(f"\nTests only in {sut1}:", fg=typer.colors.GREEN)
        for test in coverage["unique_to_sut1"][:5]:
            typer.echo(f"  {test}")
        if len(coverage["unique_to_sut1"]) > 5:
            typer.echo(f"  ... and {len(coverage['unique_to_sut1']) - 5} more")

    if coverage["unique_to_sut2"]:
        typer.secho(f"\nTests only in {sut2}:", fg=typer.colors.GREEN)
        for test in coverage["unique_to_sut2"][:5]:
            typer.echo(f"  {test}")
        if len(coverage["unique_to_sut2"]) > 5:
            typer.echo(f"  ... and {len(coverage['unique_to_sut2']) - 5} more")

    if results["stability"]["stability_differences"]:
        typer.secho("\nStability Differences:", fg=typer.colors.YELLOW)
        for test, rate1, rate2, diff in results["stability"]["stability_differences"]:
            typer.echo(f"  {test}:")
            typer.echo(f"    {sut1}: {rate1:.1%} failure rate")
            typer.echo(f"    {sut2}: {rate2:.1%} failure rate")
            typer.echo(f"    Difference: {diff:+.1f}%")


def _display_period_comparison(
    results: Dict, base_date: datetime, target_date: datetime, days: int
):
    """Display period comparison results."""
    typer.secho("\nComparing periods:", fg=typer.colors.BLUE, bold=True)
    typer.echo(f"  Base: {base_date.strftime('%Y-%m-%d')} (-{days} days)")
    typer.echo(f"  Target: {target_date.strftime('%Y-%m-%d')} (-{days} days)")

    # Display period comparison results (similar to session comparison)
    # ... implement period-specific display logic ...


if __name__ == "__main__":
    app()
