#!/usr/bin/env python
"""CLI for pytest-insight."""

import io
import json
import sys
import traceback
from datetime import datetime
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from pytest_insight.core.analysis import Analysis
from pytest_insight.core.insights import Insights
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
    console = Console()
    profiles = list_profiles()
    active = get_active_profile().name

    console.print("[bold]Available storage profiles:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Active", style="dim", width=6)
    table.add_column("Name", style="cyan")
    table.add_column("Type", style="green")
    table.add_column("Path", style="blue")

    for name, profile in profiles.items():
        active_marker = "✓" if name == active else ""
        table.add_row(active_marker, name, profile.storage_type, str(profile.file_path))

    console.print(table)


@profile_app.command("create")
def create_new_profile(
    name: str = typer.Argument(..., help="Name for the new profile"),
    storage_type: str = typer.Option("json", "--type", "-t", help="Storage type (json, memory)"),
    file_path: Optional[str] = typer.Option(None, "--path", "-p", help="Custom file path for storage"),
    activate: bool = typer.Option(False, "--activate", "-a", help="Set as active profile after creation"),
):
    """Create a new storage profile."""
    console = Console()
    try:
        profile = create_profile(name, storage_type, file_path)

        success_msg = f"Created profile [cyan]'{name}'[/cyan] ([green]{profile.storage_type}[/green]): [blue]{profile.file_path}[/blue]"

        if activate:
            switch_profile(name)
            success_msg += f"\nActivated profile [cyan]'{name}'[/cyan]"

        console.print(Panel(success_msg, title="Profile Created", border_style="green"))
    except ValueError as e:
        console.print(Panel(f"[bold red]{str(e)}[/bold red]", title="Error", border_style="red"))
        raise typer.Exit(code=1)


@profile_app.command("switch")
def switch_to_profile(name: str = typer.Argument(..., help="Name of the profile to switch to")):
    """Switch to a different storage profile."""
    console = Console()
    try:
        profile = switch_profile(name)
        console.print(
            Panel(
                f"Switched to profile [cyan]'{profile.name}'[/cyan]",
                title="Profile Activated",
                border_style="green",
            )
        )
    except ValueError as e:
        console.print(Panel(f"[bold red]{str(e)}[/bold red]", title="Error", border_style="red"))
        raise typer.Exit(code=1)


@profile_app.command("active")
def show_active_profile():
    """Show the currently active storage profile."""
    console = Console()
    profile = get_active_profile()

    table = Table(title="Active Profile", show_header=True, header_style="bold magenta")
    table.add_column("Property", style="dim")
    table.add_column("Value", style="cyan")

    table.add_row("Name", profile.name)
    table.add_row("Type", profile.storage_type)
    table.add_row("Storage path", str(profile.file_path))

    console.print(table)


@profile_app.command("delete")
def delete_existing_profile(
    name: str = typer.Argument(..., help="Name of the profile to delete"),
    force: bool = typer.Option(False, "--force", "-f", help="Force deletion without confirmation"),
):
    """Delete a storage profile."""
    console = Console()

    if not force:
        confirm = typer.confirm(f"Are you sure you want to delete profile '{name}'?")
        if not confirm:
            console.print("[yellow]Operation cancelled.[/yellow]")
            return

    try:
        profile_manager = get_profile_manager()
        profile_manager.delete_profile(name)
        console.print(
            Panel(
                f"Deleted profile [cyan]'{name}'[/cyan]",
                title="Profile Deleted",
                border_style="green",
            )
        )
    except ValueError as e:
        console.print(Panel(f"[bold red]{str(e)}[/bold red]", title="Error", border_style="red"))
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
    output_path: Optional[str] = typer.Option(
        None,
        "--output",
        "-o",
        help="Output path for generated data (only used if profile not specified)",
    ),
    days: int = typer.Option(
        7,
        "--days",
        "-d",
        help="Number of days to generate data for",
    ),
    targets_per_base: int = typer.Option(
        3,
        "--targets",
        "-t",
        help="Number of test targets per base",
    ),
    pass_rate: float = typer.Option(
        0.45,
        "--pass-rate",
        help="Target pass rate for generated tests (0.0-1.0)",
    ),
    flaky_rate: float = typer.Option(
        0.17,
        "--flaky-rate",
        help="Target flaky rate for generated tests (0.0-1.0)",
    ),
    warning_rate: float = typer.Option(
        0.085,
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
    console = Console()

    # Determine storage target
    if storage_profile:
        try:
            profile = get_profile_manager().get_profile(storage_profile)
            target = f"profile '[cyan]{profile.name}[/cyan]'"
            output_type = "profile"
        except ValueError:
            console.print(
                Panel(
                    f"[bold red]Profile '{storage_profile}' not found[/bold red]",
                    title="Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)
    elif output_path:
        target = f"file '[cyan]{output_path}[/cyan]'"
        output_type = "file"
    else:
        # Default to the active profile
        profile = get_active_profile()
        storage_profile = profile.name
        target = f"profile '[cyan]{profile.name}[/cyan]'"
        output_type = "profile"

    try:
        # Parse test categories if provided
        test_categories = None
        if categories:
            test_categories = [cat.strip() for cat in categories.split(",")]
            valid_categories = {"api", "ui", "db", "auth", "integration", "performance"}
            invalid = set(test_categories) - valid_categories
            if invalid:
                console.print(
                    Panel(
                        f"[bold red]Invalid categories: {', '.join(invalid)}. Valid categories are: {', '.join(sorted(valid_categories))}[/bold red]",
                        title="Error",
                        border_style="red",
                    )
                )
                raise typer.Exit(code=1)

        # Ensure we have a valid output path if not using a profile
        if not storage_profile and not output_path:
            # Create a default output path
            output_path = str(Path.home() / ".pytest_insight" / "practice_data.json")
            target = f"file '[cyan]{output_path}[/cyan]'"
            output_type = "file"
            console.print(f"[yellow]No profile or output path specified. Using default: {output_path}[/yellow]")

        # Always ensure output_path is a string if provided
        if output_path is not None:
            output_path = str(output_path)

        # Create generator
        with console.status("[bold green]Setting up data generator...[/bold green]", spinner="dots") as _:
            # Always provide a valid target_path to avoid NoneType errors
            target_path = None
            if output_type == "file" and output_path:
                target_path = Path(output_path)
            elif output_type == "profile":
                # For profiles, we'll let the generator handle it
                target_path = None
            elif not storage_profile and not output_path:
                # Fallback to a default path
                target_path = Path.home() / ".pytest_insight" / "practice_data.json"

            generator = PracticeDataGenerator(
                storage_profile=storage_profile if output_type == "profile" else None,
                target_path=target_path,
                days=days,
                targets_per_base=targets_per_base,
                pass_rate=pass_rate,
                flaky_rate=flaky_rate,
                warning_rate=warning_rate,
                sut_filter=sut_filter,
                test_categories=test_categories,
            )

        # Display generation parameters
        if not quiet:
            console.print(f"[bold]Generating practice test data for {target}[/bold]")

            params_table = Table(
                title="Generation Parameters",
                show_header=True,
                header_style="bold magenta",
            )
            params_table.add_column("Parameter", style="dim")
            params_table.add_column("Value", style="cyan")

            params_table.add_row("Days", str(days))
            params_table.add_row("Targets per base", str(targets_per_base))
            params_table.add_row("Pass rate", f"{pass_rate:.1%}")
            params_table.add_row("Flaky rate", f"{flaky_rate:.1%}")
            params_table.add_row("Warning rate", f"{warning_rate:.1%}")
            if sut_filter:
                params_table.add_row("SUT filter", sut_filter)
            if test_categories:
                params_table.add_row("Categories", ", ".join(test_categories))

            console.print(params_table)

        # Generate the data
        try:
            with console.status("[bold green]Generating practice data...[/bold green]", spinner="dots") as _:
                # Capture print output from the generator
                original_stdout = sys.stdout
                sys.stdout = io.StringIO()

                try:
                    generator.generate_practice_data()
                finally:
                    # Restore stdout
                    captured_output = sys.stdout.getvalue()
                    sys.stdout = original_stdout

                # Log any important messages from the generator
                if captured_output and not quiet:
                    console.print("[dim]Generator output:[/dim]")
                    for line in captured_output.strip().split("\n"):
                        if "Error" in line:
                            console.print(f"[yellow]{line}[/yellow]")
        except Exception as e:
            console.print(
                Panel(
                    f"[bold red]Error generating data: {str(e)}[/bold red]",
                    title="Generation Error",
                    border_style="red",
                )
            )
            raise typer.Exit(code=1)

        # Show success message
        if hasattr(generator, "target_path") and generator.target_path:
            path_str = str(generator.target_path)
            console.print(
                Panel(
                    f"Generated practice data for [bold]{days}[/bold] days\nSaved to: [cyan]{path_str}[/cyan]",
                    title="Success",
                    border_style="green",
                )
            )
        elif output_type == "profile":
            console.print(
                Panel(
                    f"Generated practice data for [bold]{days}[/bold] days in profile '[cyan]{storage_profile}[/cyan]'",
                    title="Success",
                    border_style="green",
                )
            )
        else:
            console.print(
                Panel(
                    f"Generated practice data for [bold]{days}[/bold] days in file '[cyan]{output_path}[/cyan]'",
                    title="Success",
                    border_style="green",
                )
            )

    except Exception as e:
        console.print(
            Panel(
                f"[bold red]Error: {str(e)}[/bold red]",
                title="Error",
                border_style="red",
            )
        )
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
        console = Console()

        # Display profile information
        console.print(f"[bold blue]Using profile:[/bold blue] [cyan]{profile}[/cyan]")

        # Load sessions from storage
        sessions = load_sessions(profile_name=profile, show_progress=not no_progress)

        if not sessions:
            console.print(
                Panel(
                    "[bold red]No sessions found in storage.[/bold red]",
                    title="Error",
                    border_style="red",
                )
            )
            return

        # Apply SUT filter if specified
        if sut_name:
            console.print(f"[bold]Filtering sessions for SUT:[/bold] [cyan]{sut_name}[/cyan]")
            sessions = [s for s in sessions if s.sut == sut_name]
            if not sessions:
                console.print(
                    Panel(
                        f"[bold red]No sessions found for SUT: {sut_name}[/bold red]",
                        title="Error",
                        border_style="red",
                    )
                )
                return

        # Create analysis instance with progress configuration
        analysis = Analysis(profile_name=profile, sessions=sessions, show_progress=not no_progress)

        # Create insights instance
        insights = Insights(profile_name=profile)

        # Load sessions with pagination if needed
        if days:
            console.print(f"[bold]Limiting analysis to[/bold] [cyan]{days}[/cyan] days")

        # Show progress for large datasets
        console.print(f"[bold]Loading and processing test sessions from profile[/bold] [cyan]'{profile}'[/cyan]...")

        # Get session metrics with optimized processing
        session_metrics = analysis.sessions.test_metrics(days, chunk_size=chunk_size)

        # Get failure rate (this is a lightweight calculation)
        failure_rate = analysis.sessions.failure_rate(days)

        # Print summary statistics
        summary_table = Table(title="Test Session Summary", show_header=True, header_style="bold magenta")
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Value", style="cyan")

        summary_table.add_row(
            "Total sessions",
            str(len(analysis._sessions) if analysis._sessions else "Unknown"),
        )
        summary_table.add_row("Total tests", str(session_metrics.get("total_tests", 0)))
        summary_table.add_row("Unique tests", str(session_metrics.get("unique_tests", 0)))
        summary_table.add_row("Average duration", f"{session_metrics.get('avg_duration', 0):.2f} seconds")

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
                summary_table.add_row(
                    "Time range",
                    f"{earliest.strftime('%Y-%m-%d %H:%M')} to {latest.strftime('%Y-%m-%d %H:%M')}",
                )

        console.print(summary_table)

        # Test Health section
        health_table = Table(title="Test Health", show_header=True, header_style="bold magenta")
        health_table.add_column("Metric", style="dim")
        health_table.add_column("Value", style="cyan")
        health_table.add_row("Session failure rate", f"{failure_rate:.1%}")
        console.print(health_table)

        # Add outcome distribution
        outcome_distribution = analysis.sessions.outcome_distribution(days)
        if outcome_distribution:
            outcome_table = Table(
                title="Outcome Distribution",
                show_header=True,
                header_style="bold magenta",
            )
            outcome_table.add_column("Outcome", style="dim")
            outcome_table.add_column("Count", style="cyan")
            outcome_table.add_column("Percentage", style="green")

            for outcome, count in outcome_distribution.items():
                percentage = count / session_metrics.get("total_tests", 1) * 100
                outcome_table.add_row(outcome, str(count), f"{percentage:.1f}%")

            console.print(outcome_table)

        # Initialize stability with a default empty dictionary
        stability = {"flaky_tests": []}

        # Get trends with progress indicator
        if analysis_type in ["standard", "comprehensive", "trends"]:
            console.print("[bold]Calculating trends...[/bold]")
            trends = analysis.sessions.detect_trends(days)

            # Get test stability metrics with progress indicator
            console.print("[bold]Analyzing test stability...[/bold]")
            stability = analysis.tests.stability(chunk_size=chunk_size)

            console.print(f"[bold]Flaky tests:[/bold] [cyan]{len(stability.get('flaky_tests', []))}")

            # Print trend information
            trends_table = Table(title="Trends", show_header=True, header_style="bold magenta")
            trends_table.add_column("Trend Type", style="dim")
            trends_table.add_column("Direction", style="cyan")
            trends_table.add_column("Change", style="green")

            duration_trend = trends.get("duration", {})
            direction = duration_trend.get("direction", "stable")
            direction_style = "green" if direction == "improving" else "red" if direction == "worsening" else "yellow"

            change_text = ""
            if duration_trend.get("significant", False):
                change_text = f"Significant: {duration_trend.get('change_percent', 0):.1f}%"

            trends_table.add_row(
                "Duration",
                f"[{direction_style}]{direction}[/{direction_style}]",
                change_text,
            )

            failure_trend = trends.get("failures", {})
            direction = failure_trend.get("direction", "stable")
            direction_style = "green" if direction == "improving" else "red" if direction == "worsening" else "yellow"

            change_text = ""
            if failure_trend.get("significant", False):
                change_text = f"Significant: {failure_trend.get('change_percent', 0):.1f}%"

            trends_table.add_row(
                "Failures",
                f"[{direction_style}]{direction}[/{direction_style}]",
                change_text,
            )

            warning_trend = trends.get("warnings", {})
            if warning_trend:
                direction = warning_trend.get("direction", "stable")
                direction_style = (
                    "green" if direction == "improving" else "red" if direction == "worsening" else "yellow"
                )

                change_text = ""
                if warning_trend.get("significant", False):
                    change_text = f"Significant: {warning_trend.get('change_percent', 0):.1f}%"

                trends_table.add_row(
                    "Warnings",
                    f"[{direction_style}]{direction}[/{direction_style}]",
                    change_text,
                )

            console.print(trends_table)

        # Print top flaky tests if available
        flaky_tests = stability.get("flaky_tests", [])
        if flaky_tests:
            flaky_table = Table(title="Top Flaky Tests", show_header=True, header_style="bold magenta")
            flaky_table.add_column("#", style="dim")
            flaky_table.add_column("Test ID", style="cyan")
            flaky_table.add_column("Flakiness Rate", style="red")
            flaky_table.add_column("Outcomes", style="yellow")

            # Show top 10 instead of just 5
            max_flaky_to_show = min(10, len(flaky_tests))
            for i, test in enumerate(flaky_tests[:max_flaky_to_show], 1):
                # Show outcome distribution for each flaky test
                outcomes = test.get("outcomes", [])
                outcome_str = ""
                if outcomes and len(outcomes) > 0:
                    outcome_str = ", ".join(
                        [f"{o.get('outcome', '').split('.')[-1]}: {o.get('count', 0)}" for o in outcomes[:3]]
                    )
                    if len(outcomes) > 3:
                        outcome_str += "..."

                flaky_table.add_row(
                    str(i),
                    test.get("nodeid", "Unknown"),
                    f"{test.get('flakiness_rate', 0):.1%}",
                    outcome_str,
                )

            console.print(flaky_table)

        # Print test execution metrics
        if "test_execution_metrics" in session_metrics:
            metrics = session_metrics["test_execution_metrics"]

            execution_table = Table(
                title="Test Execution Metrics",
                show_header=True,
                header_style="bold magenta",
            )
            execution_table.add_column("Metric", style="dim")
            execution_table.add_column("Value", style="cyan")

            execution_table.add_row(
                "Slowest tests average duration",
                f"{metrics.get('slowest_avg_duration', 0):.2f}s",
            )
            execution_table.add_row(
                "Fastest tests average duration",
                f"{metrics.get('fastest_avg_duration', 0):.2f}s",
            )

            console.print(execution_table)

            # Show top 5 slowest tests
            slow_tests = metrics.get("slowest_tests", [])
            if slow_tests:
                slow_table = Table(
                    title="Top 5 Slowest Tests",
                    show_header=True,
                    header_style="bold magenta",
                )
                slow_table.add_column("#", style="dim")
                slow_table.add_column("Test ID", style="cyan")
                slow_table.add_column("Average Duration", style="yellow")

                for i, test in enumerate(slow_tests[:5], 1):
                    slow_table.add_row(
                        str(i),
                        test.get("nodeid", "Unknown"),
                        f"{test.get('avg_duration', 0):.2f}s",
                    )

                console.print(slow_table)

        # Add test relationship analysis
        if analysis_type in ["comprehensive", "relationships"]:
            console.print("[bold]Analyzing co-failures...[/bold]")

            # Calculate co-failures (tests that tend to fail together)
            co_failures = analysis.tests.co_failures(min_correlation=0.7)

            if co_failures:
                co_failure_table = Table(
                    title="Co-Failure Clusters",
                    show_header=True,
                    header_style="bold magenta",
                )
                co_failure_table.add_column("Cluster", style="dim")
                co_failure_table.add_column("Correlation", style="cyan")
                co_failure_table.add_column("Tests", style="yellow")

                for i, cluster in enumerate(co_failures[:5], 1):
                    tests_str = "\n".join([f"- {test}" for test in cluster.get("tests", [])[:3]])
                    if len(cluster.get("tests", [])) > 3:
                        tests_str += f"\n- ... and {len(cluster.get('tests', [])) - 3} more"

                    co_failure_table.add_row(
                        f"Cluster {i}",
                        f"{cluster.get('correlation', 0):.2f}",
                        tests_str,
                    )

                console.print(co_failure_table)
            else:
                console.print(
                    Panel(
                        "No significant co-failure patterns detected.",
                        title="Co-Failure Analysis",
                        border_style="yellow",
                    )
                )

        # Add health score analysis
        if analysis_type in ["comprehensive", "health"]:
            # Calculate overall health score
            health_score = analysis.tests.health_score()

            if health_score:
                overall_score = health_score.get("overall_score", 0)
                stability_score = health_score.get("stability_score", 0)
                performance_score = health_score.get("performance_score", 0)

                health_score_table = Table(
                    title="Test Health Score Analysis",
                    show_header=True,
                    header_style="bold magenta",
                )
                health_score_table.add_column("Score Type", style="dim")
                health_score_table.add_column("Score", style="cyan")

                # Determine color based on score value
                overall_color = "green" if overall_score >= 80 else "yellow" if overall_score >= 60 else "red"
                stability_color = "green" if stability_score >= 80 else "yellow" if stability_score >= 60 else "red"
                performance_color = (
                    "green" if performance_score >= 80 else "yellow" if performance_score >= 60 else "red"
                )

                health_score_table.add_row(
                    "Overall Health Score",
                    f"[{overall_color}]{overall_score:.1f}/100[/{overall_color}]",
                )
                health_score_table.add_row(
                    "Stability Score",
                    f"[{stability_color}]{stability_score:.1f}/100[/{stability_color}]",
                )
                health_score_table.add_row(
                    "Performance Score",
                    f"[{performance_color}]{performance_score:.1f}/100[/{performance_color}]",
                )

                console.print(health_score_table)

                # Show health score breakdown by test category
                categories = health_score.get("categories", {})
                if categories:
                    category_table = Table(
                        title="Health Score by Category",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    category_table.add_column("Category", style="dim")
                    category_table.add_column("Score", style="cyan")

                    for category, score in categories.items():
                        category_color = "green" if score >= 80 else "yellow" if score >= 60 else "red"
                        category_table.add_row(
                            category,
                            f"[{category_color}]{score:.1f}/100[/{category_color}]",
                        )

                    console.print(category_table)

        # Add recently failing/passing tests analysis
        if analysis_type in ["comprehensive", "standard"]:
            # Get recently failing and recently passing tests
            behavior_changes = analysis.tests.behavior_changes(days=days or 30)

            if behavior_changes:
                # Recently failing tests (were passing, now failing)
                recently_failing = behavior_changes.get("recently_failing", [])
                if recently_failing:
                    failing_table = Table(
                        title="Recently Failing Tests",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    failing_table.add_column("#", style="dim")
                    failing_table.add_column("Test ID", style="cyan")
                    failing_table.add_column("Last Passed", style="yellow")
                    failing_table.add_column("Failure Streak", style="red")

                    for i, test in enumerate(recently_failing[:5], 1):
                        failing_table.add_row(
                            str(i),
                            test.get("nodeid", "Unknown"),
                            test.get("last_passed", "Unknown"),
                            str(test.get("failure_streak", 0)) + " runs",
                        )

                    console.print(failing_table)

                # Recently passing tests (were failing, now passing)
                recently_passing = behavior_changes.get("recently_passing", [])
                if recently_passing:
                    passing_table = Table(
                        title="Recently Fixed Tests",
                        show_header=True,
                        header_style="bold magenta",
                    )
                    passing_table.add_column("#", style="dim")
                    passing_table.add_column("Test ID", style="cyan")
                    passing_table.add_column("Last Failed", style="yellow")
                    passing_table.add_column("Success Streak", style="green")

                    for i, test in enumerate(recently_passing[:5], 1):
                        passing_table.add_row(
                            str(i),
                            test.get("nodeid", "Unknown"),
                            test.get("last_failed", "Unknown"),
                            str(test.get("success_streak", 0)) + " runs",
                        )

                    console.print(passing_table)

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

            console.print(
                Panel(
                    f"Analysis results exported to: {export_path}",
                    title="Export Complete",
                    border_style="green",
                )
            )

    except Exception as e:
        console.print(
            Panel(
                f"[bold red]Error during analysis: {str(e)}[/bold red]",
                title="Error",
                border_style="red",
            )
        )
        console.print(traceback.format_exc(), style="red")


# Main entry point
if __name__ == "__main__":
    app()
