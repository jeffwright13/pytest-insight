#!/usr/bin/env python
"""CLI for pytest-insight."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

import typer
from rich.console import Console
from rich.table import Table

from pytest_insight.core.storage import (
    create_profile,
    get_active_profile,
    get_profile_manager,
    list_profiles,
    load_sessions,
    switch_profile,
)
from pytest_insight.utils.db_generator import PracticeDataGenerator

# Create the main app
app = typer.Typer(
    name="insight",
    help="pytest-insight: Test analytics and insights for pytest",
    add_completion=False,
    context_settings={"help_option_names": ["--help", "-h"]},
)

# Create subcommand groups
profile_app = typer.Typer(
    help="Manage storage profiles",
    context_settings={"help_option_names": ["--help", "-h"]},
)
generate_app = typer.Typer(
    help="Generate practice test data",
    context_settings={"help_option_names": ["--help", "-h"]},
)

# Add subcommands to main app
app.add_typer(profile_app, name="profile")
app.add_typer(generate_app, name="generate")


# Profile management commands
@profile_app.command("list")
def list_all_profiles():
    """List all available storage profiles."""
    profiles = list_profiles()
    active = get_active_profile().name

    typer.echo("Available storage profiles:")
    for name, profile in profiles.items():
        active_marker = "* " if name == active else "  "
        typer.echo(f"{active_marker}{name} ({profile.storage_type}): {profile.file_path}")


@profile_app.command("create")
def create_new_profile(
    name: str = typer.Argument(..., help="Name for the new profile"),
    storage_type: str = typer.Option("json", "--type", "-t", help="Storage type (json, memory)"),
    file_path: Optional[str] = typer.Option(None, "--path", "-p", help="Custom file path for storage"),
    activate: bool = typer.Option(False, "--activate", "-a", help="Set as active profile after creation"),
):
    """Create a new storage profile."""
    try:
        profile = create_profile(name, storage_type, file_path)
        typer.echo(f"Created profile '{name}' ({profile.storage_type}): {profile.file_path}")

        if activate:
            switch_profile(name)
            typer.echo(f"Activated profile '{name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@profile_app.command("switch")
def switch_to_profile(name: str = typer.Argument(..., help="Name of the profile to switch to")):
    """Switch to a different storage profile."""
    try:
        profile = switch_profile(name)
        typer.echo(f"Switched to profile '{profile.name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


@profile_app.command("active")
def show_active_profile():
    """Show the currently active storage profile."""
    profile = get_active_profile()
    typer.echo(f"Active profile: {profile.name} ({profile.storage_type})")
    typer.echo(f"Storage path: {profile.file_path}")


@profile_app.command("delete")
def delete_existing_profile(
    name: str = typer.Argument(..., help="Name of the profile to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
):
    """Delete a storage profile."""
    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete profile '{name}'?")
        if not confirm:
            typer.echo("Operation cancelled.")
            return

    try:
        profile_manager = get_profile_manager()
        profile_manager.delete_profile(name)
        typer.echo(f"Deleted profile '{name}'")
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# Generate data commands
@generate_app.command("practice")
def generate_practice_data(
    storage_profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Storage profile to use for data generation (preferred over output path)",
    ),
    output: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output file path for generated data (ignored if profile is specified)",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days to generate data for",
    ),
    targets: int = typer.Option(
        5,
        "--targets",
        "-t",
        help="Number of test targets per base",
    ),
    start_date: Optional[str] = typer.Option(
        None,
        "--start-date",
        "-s",
        help="Start date for generated data (YYYY-MM-DD format)",
    ),
    pass_rate: float = typer.Option(
        0.85,
        "--pass-rate",
        help="Target pass rate for generated tests (0.0-1.0)",
    ),
    flaky_rate: float = typer.Option(
        0.05,
        "--flaky-rate",
        help="Target flaky rate for generated tests (0.0-1.0)",
    ),
    warning_rate: float = typer.Option(
        0.1,
        "--warning-rate",
        help="Target warning rate for generated tests (0.0-1.0)",
    ),
    sut_filter: Optional[str] = typer.Option(
        None,
        "--sut-filter",
        help="System under test filter pattern",
    ),
    categories: Optional[str] = typer.Option(
        None,
        "--categories",
        "-c",
        help="Comma-separated list of test categories to include (api,ui,db,auth,integration,performance)",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Suppress detailed output, only show essential information",
    ),
):
    """Generate practice test data with configurable parameters."""
    try:
        # Parse start date if provided
        parsed_start_date = None
        if start_date:
            try:
                # Use datetime(2023, 1, 1) as base like conftest.py
                base = datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC"))
                parsed_date = datetime.strptime(start_date, "%Y-%m-%d")
                parsed_start_date = base + timedelta(days=(parsed_date - datetime(2023, 1, 1)).days)
            except ValueError as e:
                if "format" in str(e):
                    raise typer.BadParameter("Start date must be in YYYY-MM-DD format")
                raise typer.BadParameter(str(e))

        # Parse test categories if provided
        test_categories = None
        if categories:
            test_categories = [cat.strip() for cat in categories.split(",")]
            valid_categories = {"api", "ui", "db", "auth", "integration", "performance"}
            invalid = set(test_categories) - valid_categories
            if invalid:
                raise typer.BadParameter(
                    f"Invalid categories: {', '.join(invalid)}. "
                    f"Valid categories are: {', '.join(sorted(valid_categories))}"
                )

        # Create generator instance
        generator = PracticeDataGenerator(
            storage_profile=storage_profile,
            target_path=Path(output) if output else None,
            days=days,
            targets_per_base=targets,
            start_date=parsed_start_date,
            pass_rate=pass_rate,
            flaky_rate=flaky_rate,
            warning_rate=warning_rate,
            sut_filter=sut_filter,
            test_categories=test_categories,
        )

        # Generate practice data
        generator.generate_practice_data()

        if not quiet:
            if storage_profile:
                typer.echo(f"Generated practice data for {days} days using profile '{storage_profile}'")
            else:
                typer.echo(f"Generated practice data for {days} days")
            typer.echo(f"Data saved to: {generator.target_path}")

    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(code=1)


# Make analyze a direct command on the main app
@app.command(
    help="Analyze test sessions",
    context_settings={"help_option_names": ["--help", "-h"]},
)
def analyze(
    profile: str = typer.Option("default", "--profile", "-p", help="Storage profile to use"),
    days: Optional[int] = typer.Option(None, "--days", "-d", help="Number of days to analyze"),
    output: str = typer.Option("text", "--output", "-o", help="Output format (text, json)"),
    chunk_size: int = typer.Option(1000, "--chunk-size", "-c", help="Chunk size for processing large datasets"),
    no_progress: bool = typer.Option(False, "--no-progress", help="Disable progress bars"),
    analysis_type: str = typer.Option(
        "standard",
        "--type",
        "-t",
        help="Analysis type (standard, comprehensive, health, relationships, trends)",
    ),
    flaky_threshold: float = typer.Option(
        0.1,
        "--flaky-threshold",
        help="Threshold for considering a test flaky (0.0-1.0)",
    ),
    slow_threshold: float = typer.Option(
        0.0,
        "--slow-threshold",
        help="Threshold for considering a test slow (in seconds, 0.0 means auto-detect)",
    ),
    export_path: Optional[str] = typer.Option(None, "--export", "-e", help="Export analysis results to file path"),
    sut_name: Optional[str] = typer.Option(None, "--sut", "-s", help="Filter analysis to specific SUT name"),
):
    """Analyze test sessions."""
    try:
        # Import analysis components here to avoid circular imports
        import json

        from pytest_insight.core.analysis import Analysis
        from pytest_insight.core.insights import Insights

        console = Console()

        # Display profile information
        typer.echo(f"Using profile: {profile}")

        # Load sessions from storage
        sessions = load_sessions(profile_name=profile, show_progress=not no_progress)

        if not sessions:
            typer.echo("[bold red]No sessions found in storage.[/bold red]")
            return

        # Apply SUT filter if specified
        if sut_name:
            typer.echo(f"Filtering sessions for SUT: {sut_name}")
            sessions = [s for s in sessions if s.sut == sut_name]
            if not sessions:
                typer.echo(f"[bold red]No sessions found for SUT: {sut_name}[/bold red]")
                return

        # Create analysis instance with progress configuration
        analysis = Analysis(profile_name=profile, sessions=sessions, show_progress=not no_progress)

        # Create insights instance
        insights = Insights(profile_name=profile)

        # Load sessions with pagination if needed
        if days:
            typer.echo(f"Limiting analysis to {days} days")

        # Show progress for large datasets
        typer.echo("Loading and processing test sessions...")

        # Get session metrics with optimized processing
        session_metrics = analysis.sessions.test_metrics(days, chunk_size=chunk_size)

        # Get failure rate (this is a lightweight calculation)
        failure_rate = analysis.sessions.failure_rate(days)

        # Print summary statistics
        typer.echo("\n=== Test Session Summary ===")
        typer.echo(f"Total sessions: {len(analysis._sessions) if analysis._sessions else 'Unknown'}")
        typer.echo(f"Total tests: {session_metrics.get('total_tests', 0)}")
        typer.echo(f"Unique tests: {session_metrics.get('unique_tests', 0)}")
        typer.echo(f"Average duration: {session_metrics.get('avg_duration', 0):.2f} seconds")

        # Add session start/end time range
        if analysis._sessions:
            start_times = [
                s.session_start_time
                for s in analysis._sessions
                if hasattr(s, "session_start_time") and s.session_start_time is not None
            ]

            # Use session_stop_time if available, otherwise use timestamp
            end_times = []
            for s in analysis._sessions:
                if hasattr(s, "session_stop_time") and s.session_stop_time is not None:
                    end_times.append(s.session_stop_time)
                elif hasattr(s, "session_start_time") and s.session_start_time is not None:
                    # Fallback to session_start_time if end_time not available
                    end_times.append(s.session_start_time)
                elif hasattr(s, "timestamp") and s.timestamp is not None:
                    # Fallback to timestamp
                    end_times.append(s.timestamp)

            if start_times and end_times:
                earliest = min(start_times)
                latest = max(end_times)
                typer.echo(f"Time range: {earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}")

        typer.echo("\n=== Test Health ===")
        typer.echo(f"Session failure rate: {failure_rate:.1%}")

        # Add outcome distribution
        outcome_distribution = analysis.sessions.outcome_distribution(days)
        if outcome_distribution:
            typer.echo("\n=== Outcome Distribution ===")
            table = Table(show_header=True)
            table.add_column("Outcome")
            table.add_column("Count")
            table.add_column("Percentage")

            for outcome, count in outcome_distribution.items():
                percentage = count / session_metrics.get("total_tests", 1) * 100
                table.add_row(outcome, str(count), f"{percentage:.1f}%")

            console.print(table)

        # Get trends with progress indicator
        if analysis_type in ["standard", "comprehensive", "trends"]:
            typer.echo("\nCalculating trends...")
            trends = analysis.sessions.detect_trends(days)

            # Get test stability metrics with progress indicator
            typer.echo("Analyzing test stability...")
            stability = analysis.tests.stability(chunk_size=chunk_size)

            typer.echo(f"Flaky tests: {len(stability.get('flaky_tests', []))}")

            # Print trend information
            typer.echo("\n=== Trends ===")
            duration_trend = trends.get("duration", {})
            typer.echo(f"Duration trend: {duration_trend.get('direction', 'stable')}")
            if duration_trend.get("significant", False):
                typer.echo(f"  * Significant change detected: {duration_trend.get('change_percent', 0):.1f}%")

            failure_trend = trends.get("failures", {})
            typer.echo(f"Failure trend: {failure_trend.get('direction', 'stable')}")
            if failure_trend.get("significant", False):
                typer.echo(f"  * Significant change detected: {failure_trend.get('change_percent', 0):.1f}%")

            warning_trend = trends.get("warnings", {})
            if warning_trend:
                typer.echo(f"Warning trend: {warning_trend.get('direction', 'stable')}")
                if warning_trend.get("significant", False):
                    typer.echo(f"  * Significant change detected: {warning_trend.get('change_percent', 0):.1f}%")

        # Print top flaky tests if available
        flaky_tests = stability.get("flaky_tests", [])
        if flaky_tests:
            typer.echo("\n=== Top Flaky Tests ===")
            # Show top 10 instead of just 5
            max_flaky_to_show = min(10, len(flaky_tests))
            for i, test in enumerate(flaky_tests[:max_flaky_to_show], 1):
                typer.echo(f"{i}. {test.get('nodeid', 'Unknown')}")
                typer.echo(f"   Flakiness rate: {test.get('flakiness_rate', 0):.1%}")

                # Show outcome distribution for each flaky test
                outcomes = test.get("outcomes", [])
                if outcomes and len(outcomes) > 0:
                    outcome_str = ", ".join(
                        [f"{o.get('outcome', '').split('.')[-1]}: {o.get('count', 0)}" for o in outcomes[:3]]
                    )
                    typer.echo(f"   Outcomes: {outcome_str}...")

        # Print test execution metrics
        if "test_execution_metrics" in session_metrics:
            metrics = session_metrics["test_execution_metrics"]
            typer.echo("\n=== Test Execution Metrics ===")
            typer.echo(f"Slowest tests average duration: {metrics.get('slowest_avg_duration', 0):.2f}s")
            typer.echo(f"Fastest tests average duration: {metrics.get('fastest_avg_duration', 0):.2f}s")

            # Show top 5 slowest tests
            slow_tests = metrics.get("slowest_tests", [])
            if slow_tests:
                typer.echo("\nTop 5 Slowest Tests:")
                for i, test in enumerate(slow_tests[:5], 1):
                    typer.echo(f"{i}. {test.get('nodeid', 'Unknown')}: {test.get('avg_duration', 0):.2f}s")

        # Add test relationship analysis
        if analysis_type in ["comprehensive", "relationships"]:
            typer.echo("\n=== Test Relationship Analysis ===")
            typer.echo("Analyzing co-failures...")

            # Calculate co-failures (tests that tend to fail together)
            co_failures = analysis.tests.co_failures(min_correlation=0.7)

            if co_failures:
                typer.echo("\n=== Co-Failure Clusters ===")
                for i, cluster in enumerate(co_failures[:5], 1):
                    typer.echo(f"Cluster {i} (Correlation: {cluster.get('correlation', 0):.2f}):")
                    for test in cluster.get("tests", [])[:3]:
                        typer.echo(f"  - {test}")
                    if len(cluster.get("tests", [])) > 3:
                        typer.echo(f"  - ... and {len(cluster.get('tests', [])) - 3} more")
            else:
                typer.echo("No significant co-failure patterns detected.")

        # Add health score analysis
        if analysis_type in ["comprehensive", "health"]:
            typer.echo("\n=== Test Health Score Analysis ===")

            # Calculate overall health score
            health_score = analysis.tests.health_score()

            if health_score:
                overall_score = health_score.get("overall_score", 0)
                stability_score = health_score.get("stability_score", 0)
                performance_score = health_score.get("performance_score", 0)

                typer.echo(f"Overall Health Score: {overall_score:.1f}/100")
                typer.echo(f"Stability Score: {stability_score:.1f}/100")
                typer.echo(f"Performance Score: {performance_score:.1f}/100")

                # Show health score breakdown by test category
                categories = health_score.get("categories", {})
                if categories:
                    typer.echo("\nHealth Score by Category:")
                    for category, score in categories.items():
                        typer.echo(f"  {category}: {score:.1f}/100")

        # Add recently failing/passing tests analysis
        if analysis_type in ["comprehensive", "standard"]:
            typer.echo("\n=== Recent Test Behavior Changes ===")

            # Get recently failing and recently passing tests
            behavior_changes = analysis.tests.behavior_changes(days=days or 30)

            if behavior_changes:
                # Recently failing tests (were passing, now failing)
                recently_failing = behavior_changes.get("recently_failing", [])
                if recently_failing:
                    typer.echo("\nRecently Failing Tests:")
                    for i, test in enumerate(recently_failing[:5], 1):
                        typer.echo(f"{i}. {test.get('nodeid', 'Unknown')}")
                        typer.echo(f"   Last passed: {test.get('last_passed', 'Unknown')}")
                        typer.echo(f"   Failure streak: {test.get('failure_streak', 0)} runs")

                # Recently passing tests (were failing, now passing)
                recently_passing = behavior_changes.get("recently_passing", [])
                if recently_passing:
                    typer.echo("\nRecently Fixed Tests:")
                    for i, test in enumerate(recently_passing[:5], 1):
                        typer.echo(f"{i}. {test.get('nodeid', 'Unknown')}")
                        typer.echo(f"   Last failed: {test.get('last_failed', 'Unknown')}")
                        typer.echo(f"   Success streak: {test.get('success_streak', 0)} runs")

        # Export results if requested
        if export_path:
            # Prepare data for serialization
            export_data = {
                "timestamp": datetime.now().isoformat(),
                "profile": profile,
                "session_summary": {
                    "total_sessions": (len(analysis._sessions) if analysis._sessions else 0),
                    "total_tests": session_metrics.get("total_tests", 0),
                    "unique_tests": session_metrics.get("unique_tests", 0),
                    "avg_duration": session_metrics.get("avg_duration", 0),
                    "failure_rate": failure_rate,
                },
                "trends": trends if "trends" in locals() else {},
                "flaky_tests": flaky_tests if "flaky_tests" in locals() else [],
                "execution_metrics": session_metrics.get("test_execution_metrics", {}),
            }

            # Add relationship data if available
            if "co_failures" in locals() and co_failures:
                export_data["co_failures"] = co_failures

            # Add health score if available
            if "health_score" in locals() and health_score:
                export_data["health_score"] = health_score

            # Add behavior changes if available
            if "behavior_changes" in locals() and behavior_changes:
                export_data["behavior_changes"] = behavior_changes

            # Write to file
            with open(export_path, "w") as f:
                json.dump(export_data, f, indent=2)

            typer.echo(f"\nAnalysis results exported to: {export_path}")

    except Exception as e:
        typer.echo(f"[bold red]Error during analysis: {str(e)}[/bold red]")
        import traceback

        typer.echo(traceback.format_exc())


# Main entry point
if __name__ == "__main__":
    app()
